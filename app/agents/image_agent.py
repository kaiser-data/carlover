from __future__ import annotations

import asyncio
import base64
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field, model_validator

from app.graph.state import CarAssistantState
from app.providers.llm.model_router import get_model
from app.schemas.common import VehicleInfo
from app.schemas.image_outputs import ImageAgentOutput, VehicleBoundingBox

_SYSTEM_PROMPT = """You are an automotive image analysis specialist.

STEP 1 — COUNT FOREGROUND VEHICLES FIRST (do this before anything else):
Scan the image and count only the PROMINENT, CLEARLY VISIBLE vehicles in the foreground —
cars that are large, close to camera, and the clear subject of the photo.
DO NOT count: distant cars in the background, parked cars far away, blurry traffic.
Two cars side by side as the main subjects = vehicle_count 2. One main car = 1.
Set vehicle_count to the correct integer. DO NOT default to 1 if you see two main cars.

STEP 2 — BRANCH on vehicle_count:

If vehicle_count >= 2:
  - Set needs_clarification = true
  - Set detected_make = null, detected_model = null
  - Write ONE clarification_question that names each car by color + position + body type.
    Good example: "Two cars: blue VW Golf hatchback (left) or white SEAT Leon hatchback (right)?"
    Bad example: "Which vehicle do you mean?" (too vague — rejected)
  - Add one observation per car describing it (color, make if visible, position)
  - Add one vehicle_boxes entry per car with normalized coordinates (0.0–1.0):
    x1,y1 = top-left corner of that car, x2,y2 = bottom-right corner.
    Label: "Car 1 – blue VW Golf (left)" etc.

If vehicle_count == 1:
  - Analyze fully: warning lights, damage, observations
  - Set detected_make / detected_model if you can identify the brand/model with confidence
  - Provide a bounding box for the single car in vehicle_boxes[]

If vehicle_count == 0:
  - Set vehicle_detected = false, needs_clarification = true
  - Add clarification_question: "No vehicle detected — please upload a car photo."

STEP 3 — Additional checks:
- image_quality: "good" = clear + well-lit | "poor" = partial | "unusable" = unreadable
- image_rotation_deg: clockwise degrees needed to make image upright (0 / 90 / 180 / 270)
- Never invent observations not visible in the image

Respond ONLY with valid JSON matching the ImageAnalysisResult schema."""


class _BBox(BaseModel):
    model_config = {"extra": "ignore"}
    label: str = ""
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 1.0
    y2: float = 1.0
    confidence: float = 0.8


class ImageAnalysisResult(BaseModel):
    model_config = {"extra": "ignore"}

    observations: list[str] = Field(default_factory=list)
    possible_findings: list[str] = Field(default_factory=list)
    warning_lights_detected: list[str] = Field(default_factory=list)
    damage_detected: bool = False
    limitations: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    raw_description: Optional[str] = None
    vehicle_detected: bool = True
    vehicle_count: int = Field(default=0, ge=0)
    image_quality: str = "good"
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    detected_make: Optional[str] = None
    detected_model: Optional[str] = None
    vehicle_boxes: list[_BBox] = Field(default_factory=list)
    image_rotation_deg: int = 0

    @model_validator(mode="before")
    @classmethod
    def _coerce_model_shapes(cls, data):
        # Qwen3-VL frequently returns shapes that don't match our schema verbatim.
        # Normalize them here so structured parsing succeeds.
        if not isinstance(data, dict):
            return data

        # observations: accept [{description: "..."}] or [{"text": "..."}]
        obs = data.get("observations")
        if isinstance(obs, list):
            coerced = []
            for item in obs:
                if isinstance(item, str):
                    coerced.append(item)
                elif isinstance(item, dict):
                    val = item.get("description") or item.get("text") or item.get("observation")
                    if isinstance(val, str):
                        coerced.append(val)
            data["observations"] = coerced

        # clarification_question (singular) → clarification_questions (list)
        if "clarification_question" in data and "clarification_questions" not in data:
            q = data.pop("clarification_question")
            if isinstance(q, str) and q.strip():
                data["clarification_questions"] = [q]
            elif isinstance(q, list):
                data["clarification_questions"] = [s for s in q if isinstance(s, str)]

        # warning_lights (model's name) → warning_lights_detected (our name)
        if "warning_lights" in data and "warning_lights_detected" not in data:
            wl = data.pop("warning_lights")
            if isinstance(wl, list):
                data["warning_lights_detected"] = [s for s in wl if isinstance(s, str)]

        # damage: [...] list form → damage_detected: bool
        if "damage" in data and "damage_detected" not in data:
            dmg = data.pop("damage")
            if isinstance(dmg, list):
                data["damage_detected"] = len(dmg) > 0
            elif isinstance(dmg, bool):
                data["damage_detected"] = dmg

        return data


async def _invoke_with_429_retry(structured, messages, max_attempts: int = 5):
    """Retry structured.ainvoke with exponential backoff on 429/503 transient errors."""
    delay = 3.0
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await structured.ainvoke(messages)
        except Exception as exc:
            msg = str(exc)
            transient = (
                "429" in msg
                or "503" in msg
                or "concurrency_limit_exceeded" in msg
                or "Concurrency limit" in msg
                or "temporarily unavailable" in msg
            )
            last_exc = exc
            if not transient or attempt == max_attempts:
                raise
            logger.warning(f"image_agent transient error on attempt {attempt}; retrying in {delay:.1f}s: {msg[:120]}")
            await asyncio.sleep(delay)
            delay *= 2
    raise last_exc  # pragma: no cover


def _count_distinct_car_boxes(boxes: list) -> int:
    """Count whole-car boxes, ignoring sub-car fragments and near-duplicates.

    A valid car box must:
      - cover ≥ 5% of image area (filters wheels/headlights/mirrors)
      - have its center ≥ 0.15 normalized units from every other valid box
        (filters overlapping fragments like body+front-panel)
    """
    valid = []
    for b in boxes:
        area = max(0.0, (b.x2 - b.x1)) * max(0.0, (b.y2 - b.y1))
        if area < 0.05:
            continue
        cx, cy = (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2
        # Skip if too close to an already-accepted box center
        too_close = any(
            ((cx - vc[0]) ** 2 + (cy - vc[1]) ** 2) ** 0.5 < 0.15
            for vc in valid
        )
        if too_close:
            continue
        valid.append((cx, cy))
    return len(valid)


def _build_image_content(image_url: str) -> dict:
    """Return the appropriate LangChain image content block."""
    if image_url.startswith("data:"):
        # Already a base64 data URI
        return {"type": "image_url", "image_url": {"url": image_url}}
    # Regular URL
    return {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}}


async def run_image_agent(state: CarAssistantState) -> ImageAgentOutput:
    """
    Analyze a vehicle image using a vision-capable LLM.
    Returns a structured ImageAgentOutput.
    """
    image_url: Optional[str] = state.get("image_url")

    if not image_url:
        return ImageAgentOutput(
            observations=[],
            limitations=["No image URL provided."],
            confidence=0.0,
        )

    try:
        llm = get_model("vision", max_tokens=2048)
        img_block = _build_image_content(image_url)

        structured = llm.with_structured_output(ImageAnalysisResult, method="json_mode")

        content = [
            {
                "type": "text",
                "text": (
                    "Analyze this image. Ignore distant background cars — focus only on "
                    "prominent foreground vehicles. If there are two or more main cars, "
                    "set vehicle_count accordingly and ask which one to analyze."
                ),
            },
            img_block,
        ]

        messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=content)]
        result: ImageAnalysisResult = await _invoke_with_429_retry(structured, messages)

        # ── Post-processing layer 1: bounding-box count override ──
        # Only counts *distinct* whole-car boxes (large, with centers spaced apart).
        # Prevents overcounting when the model returns sub-car boxes (wheels, lights,
        # door, etc.) or overlapping fragments.
        distinct_boxes = _count_distinct_car_boxes(result.vehicle_boxes)
        if distinct_boxes >= 2 and result.vehicle_count <= 1:
            logger.info(f"image_agent: {distinct_boxes} distinct car boxes override vehicle_count={result.vehicle_count}")
            result = result.model_copy(update={"vehicle_count": distinct_boxes, "needs_clarification": True})
        elif distinct_boxes == 1 and result.vehicle_count > 1:
            # Model hallucinated multiple cars but boxes prove it's one
            logger.info(f"image_agent: only 1 distinct car box — correcting vehicle_count from {result.vehicle_count}")
            result = result.model_copy(update={"vehicle_count": 1, "needs_clarification": False})

        # ── Post-processing layer 2: text heuristic scan ──
        # Catches models that describe multiple cars in observations but don't set vehicle_count
        _MULTI_CAR_PHRASES = [
            "two cars", "two vehicles", "both cars", "both vehicles",
            "car on the left", "car on the right", "left car", "right car",
            "left vehicle", "right vehicle", "first car", "second car",
            "another car", "another vehicle",
        ]
        _scan_text = " ".join(filter(None, [
            result.raw_description or "",
            " ".join(result.observations),
            " ".join(result.clarification_questions),
        ])).lower()
        _multi_hits = sum(1 for p in _MULTI_CAR_PHRASES if p in _scan_text)
        if _multi_hits >= 1 and result.vehicle_count <= 1:
            logger.info(f"image_agent: text heuristic found {_multi_hits} multi-car phrase(s), upgrading vehicle_count to 2")
            result = result.model_copy(update={"vehicle_count": 2, "needs_clarification": True})

        clarification_questions = list(result.clarification_questions)

        # Fallback only if model forgot to add a question for no-vehicle case
        if not result.vehicle_detected and not clarification_questions:
            clarification_questions.insert(
                0,
                "No vehicle detected in the image — please upload a photo of your vehicle.",
            )

        # Fallback only if model forgot unusable quality question
        if result.image_quality == "unusable" and not clarification_questions:
            clarification_questions.append(
                "The image cannot be analyzed — please take a clearer photo."
            )

        needs_clarification = bool(
            not result.vehicle_detected
            or result.vehicle_count > 1
            or result.image_quality == "unusable"
        )

        # With multiple cars we cannot reliably identify a single vehicle
        detected_make = None if result.vehicle_count > 1 else result.detected_make
        detected_model = None if result.vehicle_count > 1 else result.detected_model

        # Ensure multi-car fallback clarification question exists
        if result.vehicle_count > 1 and not clarification_questions:
            clarification_questions.append(
                f"{result.vehicle_count} vehicles detected — which car do you want analyzed? "
                "Describe it (e.g. 'the red one on the left') or upload a photo of just that car."
            )

        boxes = [
            VehicleBoundingBox(
                label=b.label, x1=b.x1, y1=b.y1, x2=b.x2, y2=b.y2, confidence=b.confidence
            )
            for b in result.vehicle_boxes
        ]

        return ImageAgentOutput(
            observations=result.observations,
            possible_findings=result.possible_findings,
            warning_lights_detected=result.warning_lights_detected,
            damage_detected=result.damage_detected,
            limitations=result.limitations,
            confidence=result.confidence,
            raw_description=result.raw_description,
            vehicle_detected=result.vehicle_detected,
            vehicle_count=result.vehicle_count,
            image_quality=result.image_quality,
            needs_clarification=needs_clarification,
            clarification_questions=clarification_questions,
            detected_make=detected_make,
            detected_model=detected_model,
            vehicle_boxes=boxes,
            image_rotation_deg=result.image_rotation_deg,
        )

    except Exception as exc:
        logger.error(f"image_agent failed: {exc}")
        return ImageAgentOutput(
            observations=[],
            limitations=[f"Image analysis failed: {exc}"],
            confidence=0.0,
        )


async def analyze_image_standalone(
    image_url: str,
    context: Optional[str] = None,
) -> ImageAgentOutput:
    """
    Standalone image analysis without a full graph state.
    If a vehicle make/model is identified, also fetches ADAC data.
    Used by the /image/analyze endpoint directly.
    """
    mock_state: CarAssistantState = {  # type: ignore[assignment]
        "image_url": image_url,
        "user_query": context or "Analyze this vehicle image.",
        "request_id": "",
        "session_id": None,
        "intent": "image_analysis",
        "vehicle": None,
        "vehicle_candidates": [],
        "vehicle_confidence": 0.0,
        "issue": context,
        "image_context": None,
        "missing_fields": [],
        "selected_agents": ["image"],
        "agent_results": {},
        "debug_trace": [],
        "sources": [],
        "merged_context": None,
        "final_answer": None,
        "final_output": None,
        "confidence": 0.0,
        "needs_clarification": False,
        "clarification_questions": [],
        "uncertainty_notes": [],
    }
    output = await run_image_agent(mock_state)

    # Enrich with ADAC data when the vision model identified the vehicle
    if output.detected_make and output.detected_model:
        try:
            from app.config import get_settings
            from app.providers.adac.real_provider import RealADACProvider
            from app.providers.adac.mock_provider import MockADACProvider

            settings = get_settings()
            provider = RealADACProvider() if settings.ADAC_PROVIDER == "real" else MockADACProvider()
            vehicle = VehicleInfo(make=output.detected_make, model=output.detected_model)

            vehicle_info, issue_patterns = await _fetch_adac_parallel(provider, vehicle)

            if vehicle_info:
                output.adac_summary = vehicle_info.known_issues_summary
            if issue_patterns:
                output.adac_issue_patterns = [p.model_dump() for p in issue_patterns[:3]]
        except Exception as exc:
            logger.warning(f"ADAC enrichment failed for image analysis: {exc}")

    return output


async def _fetch_adac_parallel(provider, vehicle: VehicleInfo):
    """Fetch vehicle info and issue patterns in parallel."""
    import asyncio
    results = await asyncio.gather(
        provider.fetch_vehicle_info(vehicle),
        provider.fetch_issue_patterns(vehicle),
        return_exceptions=True,
    )
    vehicle_info = results[0] if not isinstance(results[0], Exception) else None
    issue_patterns = results[1] if not isinstance(results[1], Exception) else []
    return vehicle_info, issue_patterns
