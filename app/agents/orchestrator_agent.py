"""
Orchestrator Agent — implements three LangGraph node functions:
  1. classify_intent   → determines intent category
  2. extract_entities  → extracts vehicle candidates + issue
  3. route_agents      → pure logic, selects which subagents to run

These functions are wired directly as LangGraph nodes in graph.py.
"""
from __future__ import annotations

import difflib
import time
from typing import Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field

from app.graph.state import CarAssistantState
from app.providers.llm.model_router import get_model
from app.schemas.common import TraceEntry, VehicleCandidate, VehicleInfo
from app.skills.loader import get_skills_loader

# Common EU/German model → brand mapping for brand-less input (e.g. "Polo" → VW)
_MODEL_TO_BRAND: dict[str, str] = {
    "golf": "VW", "polo": "VW", "passat": "VW", "tiguan": "VW",
    "touareg": "VW", "arteon": "VW", "t-roc": "VW", "id.3": "VW", "id.4": "VW",
    "a3": "Audi", "a4": "Audi", "a6": "Audi", "a8": "Audi",
    "q3": "Audi", "q5": "Audi", "q7": "Audi",
    "3er": "BMW", "5er": "BMW", "7er": "BMW",
    "x1": "BMW", "x3": "BMW", "x5": "BMW",
    "c-klasse": "Mercedes-Benz", "e-klasse": "Mercedes-Benz",
    "a-klasse": "Mercedes-Benz", "s-klasse": "Mercedes-Benz",
    "gle": "Mercedes-Benz", "glc": "Mercedes-Benz", "gla": "Mercedes-Benz",
    "corsa": "Opel", "astra": "Opel", "insignia": "Opel", "mokka": "Opel",
    "fiesta": "Ford", "focus": "Ford", "kuga": "Ford", "puma": "Ford",
    "clio": "Renault", "megane": "Renault", "kadjar": "Renault", "captur": "Renault",
    "208": "Peugeot", "308": "Peugeot", "3008": "Peugeot", "5008": "Peugeot",
    "yaris": "Toyota", "corolla": "Toyota", "rav4": "Toyota", "camry": "Toyota",
    "civic": "Honda", "cr-v": "Honda", "jazz": "Honda",
    "octavia": "Škoda", "fabia": "Škoda", "superb": "Škoda", "karoq": "Škoda",
    "leon": "Seat", "ibiza": "Seat", "ateca": "Seat",
    "i20": "Hyundai", "i30": "Hyundai", "tucson": "Hyundai", "kona": "Hyundai",
    "ceed": "Kia", "sportage": "Kia", "stonic": "Kia",
    "qashqai": "Nissan", "juke": "Nissan", "leaf": "Nissan",
    "cx-5": "Mazda", "mazda3": "Mazda", "mazda6": "Mazda",
    "xc60": "Volvo", "xc90": "Volvo", "v60": "Volvo",
    "500": "Fiat", "punto": "Fiat", "tipo": "Fiat",
}

_KNOWN_MAKES = [
    "VW", "Volkswagen", "BMW", "Mercedes-Benz", "Mercedes", "Audi",
    "Opel", "Ford", "Renault", "Peugeot", "Toyota", "Honda", "Škoda",
    "Seat", "Hyundai", "Kia", "Nissan", "Mazda", "Volvo", "Fiat",
]


def _normalize_vehicle_candidate(candidate: VehicleCandidate) -> VehicleCandidate:
    """
    Fix common input errors:
    1. Brand-less model → infer brand from _MODEL_TO_BRAND
    2. Typo in make → fuzzy-correct via difflib
    """
    make = candidate.make or ""
    model = candidate.model or ""

    # 1. If make looks like a known model name, swap make ↔ model and infer brand
    if not make and model:
        inferred = _MODEL_TO_BRAND.get(model.lower())
        if inferred:
            make = inferred
    elif make and not model:
        inferred = _MODEL_TO_BRAND.get(make.lower())
        if inferred:
            model = make
            make = inferred
    elif make and _MODEL_TO_BRAND.get(make.lower()):
        # make field contains a model name (e.g. "Golf" as make, model empty)
        if not model:
            model = make
            make = _MODEL_TO_BRAND[make.lower()]

    # 2. Fuzzy make correction (handles typos like "Gollf" → "VW" won't match,
    #    but "Volkswaagen" → "Volkswagen" will)
    if make:
        known_lower = [m.lower() for m in _KNOWN_MAKES]
        close = difflib.get_close_matches(make.lower(), known_lower, n=1, cutoff=0.65)
        if close:
            idx = known_lower.index(close[0])
            make = _KNOWN_MAKES[idx]

    return candidate.model_copy(update={"make": make, "model": model})


# ------------------------------------------------------------------ #
# Structured output schemas for LLM calls
# ------------------------------------------------------------------ #


class IntentClassification(BaseModel):
    model_config = {"extra": "ignore"}
    intent: Literal["diagnosis", "lookup", "image_analysis", "code_execution", "general"]
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reasoning: str = ""


class EntityExtraction(BaseModel):
    model_config = {"extra": "ignore"}
    vehicle_candidates: list[VehicleCandidate] = Field(default_factory=list)
    best_match: Optional[VehicleCandidate] = None
    issue: Optional[str] = None
    image_mentioned: bool = False


# ------------------------------------------------------------------ #
# Node: classify_intent
# ------------------------------------------------------------------ #


async def classify_intent(state: CarAssistantState) -> dict:
    t0 = time.monotonic()
    skills = get_skills_loader()
    routing_rules = skills.get("routing_rules")

    system_prompt = (
        "You are an automotive assistant intent classifier.\n\n"
        f"## Routing Rules\n{routing_rules}\n\n"
        "Classify the user query into exactly one intent category.\n\n"
        "You MUST respond with valid JSON containing EXACTLY these fields:\n"
        "{\n"
        '  "intent": "diagnosis|lookup|image_analysis|code_execution|general",\n'
        '  "confidence": 0.9,\n'
        '  "reasoning": "<brief reason>"\n'
        "}"
    )

    try:
        llm = get_model("orchestrator")
        structured = llm.with_structured_output(IntentClassification, method="json_mode")
        result: IntentClassification = await structured.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=state["user_query"]),
        ])
        intent = result.intent
        note = f"intent={intent} confidence={result.confidence:.2f}"
        logger.debug(f"classify_intent: {note}")
    except Exception as exc:
        logger.warning(f"classify_intent LLM failed: {exc}, defaulting to 'diagnosis'")
        intent = "diagnosis"
        note = f"fallback to diagnosis (error: {exc})"

    elapsed = (time.monotonic() - t0) * 1000
    return {
        "intent": intent,
        "debug_trace": [TraceEntry(node="classify_intent", elapsed_ms=elapsed, note=note)],
    }


# ------------------------------------------------------------------ #
# Node: extract_entities
# ------------------------------------------------------------------ #


async def extract_entities(state: CarAssistantState) -> dict:
    t0 = time.monotonic()
    skills = get_skills_loader()
    vehicle_skill = skills.get("vehicle_lookup")

    system_prompt = (
        "You are a vehicle entity extractor for an automotive assistant.\n\n"
        f"## Vehicle Knowledge\n{vehicle_skill}\n\n"
        "Extract vehicle candidates, issue description, and image references "
        "from the user query. Rank candidates by confidence (descending).\n\n"
        "You MUST respond with valid JSON containing EXACTLY these fields:\n"
        "{\n"
        '  "vehicle_candidates": [{"make": "VW", "model": "Golf", "year_range": [2013, 2020], "variant": null, "confidence": 0.9, "match_reason": "year 2017 matches Golf 7"}],\n'
        '  "best_match": {"make": "VW", "model": "Golf", "year_range": [2013, 2020], "variant": null, "confidence": 0.9, "match_reason": "year 2017 matches Golf 7"},\n'
        '  "issue": "<issue description or null>",\n'
        '  "image_mentioned": false\n'
        "}"
    )

    vehicle: Optional[VehicleInfo] = state.get("vehicle")
    candidates: list[VehicleCandidate] = []
    issue: Optional[str] = state.get("issue")
    image_url: Optional[str] = state.get("image_url")

    try:
        llm = get_model("orchestrator")
        structured = llm.with_structured_output(EntityExtraction, method="json_mode")
        result: EntityExtraction = await structured.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=state["user_query"]),
        ])

        candidates = [_normalize_vehicle_candidate(c) for c in result.vehicle_candidates]
        best_match = (
            _normalize_vehicle_candidate(result.best_match) if result.best_match else None
        )
        if result.issue:
            issue = result.issue
        if result.image_mentioned and not image_url:
            image_url = state.get("image_url")

        # Resolve best vehicle from candidates or pre-filled context
        if not vehicle and best_match:
            best = best_match
            vehicle = VehicleInfo(
                make=best.make,
                model=best.model,
                year=best.year_range[0] if best.year_range else None,
                variant=best.variant,
                confidence=best.confidence,
            )

        note = (
            f"vehicle={vehicle.make if vehicle else 'None'} "
            f"candidates={len(candidates)} issue={issue!r}"
        )
    except Exception as exc:
        logger.warning(f"extract_entities LLM failed: {exc}")
        note = f"extraction error: {exc}"

    # Determine vehicle confidence for threshold check
    vehicle_confidence = 0.0
    if vehicle:
        vehicle_confidence = vehicle.confidence
    elif candidates:
        vehicle_confidence = candidates[0].confidence

    elapsed = (time.monotonic() - t0) * 1000
    return {
        "vehicle": vehicle,
        "vehicle_candidates": candidates,
        "vehicle_confidence": vehicle_confidence,
        "issue": issue,
        "image_url": image_url,
        "debug_trace": [TraceEntry(node="extract_entities", elapsed_ms=elapsed, note=note)],
    }


# ------------------------------------------------------------------ #
# Node: route_agents (pure logic — no LLM call)
# ------------------------------------------------------------------ #


async def route_agents(state: CarAssistantState) -> dict:
    t0 = time.monotonic()
    intent = state.get("intent", "diagnosis")
    image_url = state.get("image_url")
    vehicle = state.get("vehicle")

    selected: list[str] = []

    if intent == "diagnosis":
        if vehicle:
            selected.extend(["adac", "supabase", "sandbox"])
        else:
            selected.append("adac")
    elif intent == "lookup":
        selected.extend(["adac", "supabase"])
    elif intent == "image_analysis":
        selected.append("image")
    elif intent == "code_execution":
        selected.append("sandbox")
    elif intent == "general":
        selected.append("adac")

    # Always add image agent if there's an image URL (any intent)
    if image_url and "image" not in selected:
        selected.append("image")

    elapsed = (time.monotonic() - t0) * 1000
    return {
        "selected_agents": selected,
        "debug_trace": [
            TraceEntry(
                node="route_agents",
                elapsed_ms=elapsed,
                note=f"selected={selected}",
            )
        ],
    }
