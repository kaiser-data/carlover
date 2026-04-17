"""
LangGraph node functions that are NOT agent-specific.

Agent-specific classification/extraction/routing nodes are in
app/agents/orchestrator_agent.py and imported here for convenience.

This module contains:
  - intake
  - check_required_fields
  - clarify_if_needed
  - run_subagents          ← parallel execution with partial failure handling
  - merge_results
  - finalize
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.agents import get_registry
from app.agents.answer_agent import run_answer_agent
from app.config import get_settings
from app.graph.state import CarAssistantState
from app.schemas.common import TraceEntry
from app.schemas.agent_outputs import ADACAgentOutput, SupabaseAgentOutput
from app.schemas.image_outputs import ImageAgentOutput


# ------------------------------------------------------------------ #
# intake
# ------------------------------------------------------------------ #


async def intake(state: CarAssistantState) -> dict:
    t0 = time.monotonic()
    request_id = state.get("request_id") or str(uuid.uuid4())
    query = (state.get("user_query") or "").strip()
    elapsed = (time.monotonic() - t0) * 1000
    return {
        "request_id": request_id,
        "user_query": query,
        "debug_trace": [TraceEntry(node="intake", elapsed_ms=elapsed, note=f"rid={request_id[:8]}")],
    }


# ------------------------------------------------------------------ #
# check_required_fields
# ------------------------------------------------------------------ #


async def check_required_fields(state: CarAssistantState) -> dict:
    t0 = time.monotonic()
    settings = get_settings()
    intent = state.get("intent", "general")
    vehicle = state.get("vehicle")
    vehicle_confidence = state.get("vehicle_confidence", 0.0)
    candidates = state.get("vehicle_candidates", [])

    missing: list[str] = []
    needs_clarification = False
    clarification_questions: list[str] = []

    # Intents that require vehicle info
    if intent in ("diagnosis", "lookup"):
        if not vehicle:
            missing.append("vehicle")
            needs_clarification = True
            clarification_questions.append(
                "Please provide the make and model of your vehicle (e.g. VW Golf, BMW 3 Series)."
            )
        elif vehicle_confidence < settings.VEHICLE_DETECTION_MIN_CONFIDENCE:
            missing.append("vehicle_confirmation")
            needs_clarification = True
            if candidates:
                top3 = candidates[:3]
                options = "\n".join(
                    f"  • {c.make} {c.model}"
                    f"{' (' + str(c.year_range[0]) + '–' + str(c.year_range[1]) + ')' if c.year_range else ''}"
                    f"{' ' + c.variant if c.variant else ''}"
                    f" — match: {c.confidence:.0%}"
                    for c in top3
                )
                clarification_questions.append(
                    f"I found several possible vehicles — which one is yours?\n{options}"
                )
            else:
                clarification_questions.append(
                    "Please clarify your vehicle (make, model, year)."
                )
        elif (
            len(candidates) > 1
            and candidates[0].confidence - candidates[1].confidence
            < settings.VEHICLE_DETECTION_AMBIGUITY_GAP
        ):
            # Top-2 gap too small — disambiguate
            needs_clarification = True
            top2 = candidates[:2]
            options = " or ".join(
                f"{c.make} {c.model}"
                f"{' (' + str(c.year_range[0]) + '–' + str(c.year_range[1]) + ')' if c.year_range else ''}"
                for c in top2
            )
            clarification_questions.append(
                f"Did you mean {options}?"
            )

    elapsed = (time.monotonic() - t0) * 1000
    return {
        "missing_fields": missing,
        "needs_clarification": needs_clarification,
        "clarification_questions": clarification_questions,
        "debug_trace": [
            TraceEntry(
                node="check_required_fields",
                elapsed_ms=elapsed,
                note=f"missing={missing} clarify={needs_clarification}",
            )
        ],
    }


# ------------------------------------------------------------------ #
# clarify_if_needed
# ------------------------------------------------------------------ #


async def clarify_if_needed(state: CarAssistantState) -> dict:
    """
    This node is reached only when needs_clarification=True.
    It finalizes the clarification response — no LLM call needed
    since check_required_fields already built the questions.
    """
    t0 = time.monotonic()
    questions = state.get("clarification_questions", [])
    answer = (
        "To help you better, I need a bit more information:\n\n"
        + "\n".join(f"• {q}" for q in questions)
    )
    elapsed = (time.monotonic() - t0) * 1000
    return {
        "final_answer": answer,
        "confidence": 0.0,
        "debug_trace": [TraceEntry(node="clarify_if_needed", elapsed_ms=elapsed)],
    }


# ------------------------------------------------------------------ #
# run_subagents
# ------------------------------------------------------------------ #


async def run_subagents(state: CarAssistantState) -> dict:
    """
    Execute selected subagents in parallel.

    Uses asyncio.gather(return_exceptions=True) so that a single agent
    failure does not abort the entire pipeline. Failed agents are stored
    as {"error": ..., "partial": True} — the merge step handles them.
    """
    t0 = time.monotonic()
    registry = get_registry()
    selected = state.get("selected_agents", [])

    tasks = [registry[name](state) for name in selected if name in registry]
    unknown = [name for name in selected if name not in registry]
    if unknown:
        logger.warning(f"Unknown agents requested: {unknown}")

    results = await asyncio.gather(*tasks, return_exceptions=True)

    agent_results: dict[str, Any] = {}
    image_context = state.get("image_context")

    for name, result in zip(
        [n for n in selected if n in registry], results
    ):
        if isinstance(result, Exception):
            logger.error(f"Agent '{name}' failed: {result}")
            agent_results[name] = {"error": str(result), "partial": True, "success": False}
        else:
            agent_results[name] = result.model_dump()
            if name == "image":
                image_context = result  # type: ignore[assignment]

    elapsed = (time.monotonic() - t0) * 1000
    return {
        "agent_results": agent_results,
        "image_context": image_context,
        "debug_trace": [
            TraceEntry(
                node="run_subagents",
                elapsed_ms=elapsed,
                note=f"ran={list(agent_results.keys())}",
            )
        ],
    }


# ------------------------------------------------------------------ #
# merge_results
# ------------------------------------------------------------------ #


def _format_adac(data: dict) -> str:
    lines = ["### ADAC Data"]
    if vi := data.get("vehicle_info"):
        lines.append(f"**Vehicle:** {vi.get('make')} {vi.get('model')} ({vi.get('year_from')}–{vi.get('year_to', 'present')})")
        if summary := vi.get("known_issues_summary"):
            lines.append(f"**Known issues:** {summary}")
    for pattern in data.get("issue_patterns", [])[:3]:
        lines.append(
            f"- **{pattern.get('pattern_name')}**: {pattern.get('root_cause', '')} "
            f"→ {pattern.get('solution', '')} (severity: {pattern.get('severity', '?')})"
        )
    return "\n".join(lines)


def _format_supabase(data: dict) -> str:
    lines = ["### Internal Database"]
    if not data.get("vehicle_found"):
        lines.append("Vehicle not found in internal database.")
        return "\n".join(lines)
    for w in data.get("weaknesses", [])[:5]:
        lines.append(f"- **{w.get('component')}**: {w.get('description')} (severity: {w.get('severity')})")
    for sc in data.get("service_cases", [])[:3]:
        lines.append(f"- Service case: {sc.get('issue_type')} → {sc.get('resolution')}")
    return "\n".join(lines)


def _format_image(data: dict) -> str:
    parts = ["### Image Analysis"]
    for obs in data.get("observations", []):
        parts.append(f"- {obs}")
    for finding in data.get("possible_findings", []):
        parts.append(f"→ Possible cause: {finding}")
    if data.get("damage_detected"):
        parts.append("⚠️ Damage detected.")
    image_quality = data.get("image_quality", "good")
    if image_quality != "good":
        parts.append(f"*Image quality: {image_quality}*")
    clarification_qs = data.get("clarification_questions", [])
    if clarification_qs:
        parts.append("**Clarification needed:**")
        for q in clarification_qs:
            parts.append(f"- {q}")
    return "\n".join(parts)


async def merge_results(state: CarAssistantState) -> dict:
    t0 = time.monotonic()
    agent_results = state.get("agent_results", {})
    parts: list[str] = []
    uncertainty_notes: list[str] = []

    for agent_name, data in agent_results.items():
        if data.get("partial") or not data.get("success", True):
            uncertainty_notes.append(
                f"{agent_name} agent: data incomplete or error — {data.get('error', 'unknown')}"
            )

        if agent_name == "adac" and data.get("success", True):
            parts.append(_format_adac(data))
        elif agent_name == "supabase" and data.get("success", True):
            parts.append(_format_supabase(data))
        elif agent_name == "image" and data.get("success", True):
            parts.append(_format_image(data))

    merged = "\n\n".join(parts) if parts else "No usable data from agents."
    elapsed = (time.monotonic() - t0) * 1000
    return {
        "merged_context": merged,
        "uncertainty_notes": uncertainty_notes,
        "debug_trace": [TraceEntry(node="merge_results", elapsed_ms=elapsed)],
    }


# ------------------------------------------------------------------ #
# answer (calls answer_agent)
# ------------------------------------------------------------------ #


async def answer(state: CarAssistantState) -> dict:
    t0 = time.monotonic()
    result = await run_answer_agent(state)
    elapsed = (time.monotonic() - t0) * 1000
    return {
        "final_output": result,
        "final_answer": result.answer,
        "confidence": result.confidence,
        "needs_clarification": result.needs_clarification,
        "clarification_questions": result.clarification_questions,
        "sources": result.sources,
        "uncertainty_notes": result.uncertainty_notes,
        "debug_trace": [TraceEntry(node="answer", elapsed_ms=elapsed)],
    }


# ------------------------------------------------------------------ #
# finalize
# ------------------------------------------------------------------ #


async def finalize(state: CarAssistantState) -> dict:
    t0 = time.monotonic()
    elapsed = (time.monotonic() - t0) * 1000
    return {
        "debug_trace": [TraceEntry(node="finalize", elapsed_ms=elapsed, note="done")],
    }
