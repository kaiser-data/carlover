from __future__ import annotations

import base64
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field

from app.graph.state import CarAssistantState
from app.providers.llm.model_router import get_model
from app.schemas.common import VehicleInfo
from app.schemas.image_outputs import ImageAgentOutput

_SYSTEM_PROMPT = """You are an automotive image analysis specialist.
Analyze the provided vehicle image and extract structured observations.

Focus on:
- Warning lights visible on the dashboard (identify each by name/symbol)
- Visible damage (scratches, dents, rust, fluid leaks)
- Cockpit anomalies (unusual readings, warning indicators)
- Any other automotive-relevant observations

Be precise. Do not guess what is not visible. Note image quality limitations.

Additional rules:
- Count distinct vehicles visible and set vehicle_count. If 0, set vehicle_detected=false.
- If vehicle_count > 1: you MUST set needs_clarification=true, detected_make=null,
  detected_model=null, and write ONE clarification_question describing each car by its
  visible properties (color, position, body type). Example:
  "Two cars detected: the red hatchback on the left or the silver SUV on the right — which one?"
  Never write a generic "which vehicle" — always describe what you can actually see.
  Use observations[] to briefly describe each car you see.
- Rate image_quality: "good"=clear and well-lit, "poor"=partially readable, "unusable"=nothing determinable.
- If image_quality is "unusable": set confidence=0.0 and add clarification_question:
  "The image is too blurry or dark — please take a clearer photo."
- If image_quality is "poor": add clarification_question:
  "Image quality is limited — a clearer photo would improve the analysis."
- Never invent observations you cannot see.
- If you can identify the vehicle make and model from the image, set detected_make and
  detected_model (e.g. detected_make="BMW", detected_model="1 Series"). Only set these
  when you are reasonably confident — leave null if uncertain.

Respond in JSON matching the ImageAnalysisResult schema."""


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
        llm = get_model("vision")
        structured = llm.with_structured_output(ImageAnalysisResult, method="json_mode")

        content = [
            {"type": "text", "text": "Please analyze this vehicle image."},
            _build_image_content(image_url),
        ]

        result: ImageAnalysisResult = await structured.ainvoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=content),
        ])

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
