from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.graph.state import CarAssistantState
from app.providers.llm.model_router import get_model
from app.schemas.agent_outputs import FinalAnswerOutput
from app.schemas.common import SourceInfo
from app.skills.loader import get_skills_loader


async def run_answer_agent(state: CarAssistantState) -> FinalAnswerOutput:
    """
    Synthesize a final user-facing answer from merged agent context.

    - Combines all agent results into a coherent answer
    - Marks conflicts or uncertainty explicitly
    - Adds clarification questions if data is still missing
    - Always includes sources and confidence
    """
    skills = get_skills_loader()
    answer_style = skills.get("answer_style")
    diagnosis_skill = skills.get("diagnosis")

    vehicle = state.get("vehicle")
    vehicle_confidence = state.get("vehicle_confidence", 0.0)
    merged_context = state.get("merged_context") or ""
    needs_clarification = state.get("needs_clarification", False)
    clarification_questions = state.get("clarification_questions", [])

    # Build system prompt
    system_prompt = (
        "You are the final response synthesizer for an automotive assistant.\n\n"
        f"## Answer Style\n{answer_style}\n\n"
        f"## Diagnosis Heuristics\n{diagnosis_skill}\n\n"
        "Using the provided context from data sources, write a clear, helpful response "
        "to the user's question. Always cite your sources. Mark uncertainty explicitly. "
        "If the vehicle was inferred rather than stated, note this.\n\n"
        "You MUST respond with valid JSON containing EXACTLY these fields:\n"
        "{\n"
        '  "answer": "<full response text in English>",\n'
        '  "sources": [{"label": "<source name>", "type": "adac|supabase|image|internal|unknown", "confidence": 0.85}],\n'
        '  "confidence": 0.85,\n'
        '  "needs_clarification": false,\n'
        '  "clarification_questions": [],\n'
        '  "uncertainty_notes": []\n'
        "}"
    )

    # Build user context message
    vehicle_str = (
        f"{vehicle.make} {vehicle.model}"
        f"{' ' + str(vehicle.year) if vehicle.year else ''}"
        f"{' (' + vehicle.variant + ')' if vehicle.variant else ''}"
        if vehicle
        else "Unknown vehicle"
    )
    vehicle_note = (
        f"\n⚠️ Vehicle inferred with {vehicle_confidence:.0%} confidence — not explicitly stated."
        if vehicle and vehicle_confidence < 0.85
        else ""
    )

    user_message = (
        f"**User question:** {state['user_query']}\n\n"
        f"**Vehicle:** {vehicle_str}{vehicle_note}\n\n"
        f"**Collected information:**\n{merged_context or 'No data available.'}\n\n"
    )

    if needs_clarification and clarification_questions:
        user_message += (
            f"**Missing information:** The following clarification questions were identified:\n"
            + "\n".join(f"- {q}" for q in clarification_questions)
        )

    try:
        llm = get_model("response")
        structured = llm.with_structured_output(FinalAnswerOutput, method="json_mode")
        result: FinalAnswerOutput = await structured.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])

        # Merge sources from state
        all_sources = result.sources + state.get("sources", [])
        # Deduplicate by label
        seen = set()
        deduped_sources: list[SourceInfo] = []
        for s in all_sources:
            if s.label not in seen:
                seen.add(s.label)
                deduped_sources.append(s)
        result.sources = deduped_sources

        return result

    except Exception as exc:
        logger.error(f"answer_agent LLM failed: {exc}")
        return FinalAnswerOutput(
            answer=(
                "An internal error occurred. "
                "Please try again or contact support."
            ),
            confidence=0.0,
            uncertainty_notes=[f"Synthesis error: {exc}"],
            needs_clarification=False,
        )
