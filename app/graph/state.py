from __future__ import annotations

import operator
from typing import Annotated, Any, Optional

from typing_extensions import TypedDict

from app.schemas.agent_outputs import FinalAnswerOutput
from app.schemas.common import SourceInfo, TraceEntry, VehicleCandidate, VehicleInfo
from app.schemas.image_outputs import ImageAgentOutput


class CarAssistantState(TypedDict):
    """
    Shared state flowing through the LangGraph graph.

    IMPORTANT — reducer annotations:
    Fields annotated with Annotated[..., reducer] are MERGED across node
    updates, not overwritten. This is critical for parallel agent execution:
    - agent_results: dict merge (later keys win within same agent, but agents don't conflict)
    - debug_trace: list append
    - sources: list append
    All other fields use default LangGraph behavior (last write wins).
    """

    # Core request fields
    request_id: str
    user_query: str
    session_id: Optional[str]

    # Intent and entities
    intent: Optional[str]  # "diagnosis" | "lookup" | "image_analysis" | "general"
    vehicle: Optional[VehicleInfo]
    vehicle_candidates: list[VehicleCandidate]
    vehicle_confidence: float
    issue: Optional[str]
    image_url: Optional[str]
    image_context: Optional[ImageAgentOutput]

    # Routing
    missing_fields: list[str]
    selected_agents: list[str]

    # Accumulation (reducers prevent overwrites across parallel nodes)
    agent_results: Annotated[dict[str, Any], lambda a, b: {**a, **b}]
    debug_trace: Annotated[list[TraceEntry], operator.add]
    sources: Annotated[list[SourceInfo], operator.add]

    # Synthesis
    merged_context: Optional[str]
    final_answer: Optional[str]
    final_output: Optional[FinalAnswerOutput]

    # Response metadata
    confidence: float
    needs_clarification: bool
    clarification_questions: list[str]
    uncertainty_notes: list[str]


def initial_state(
    user_query: str,
    request_id: str,
    vehicle: Optional[VehicleInfo] = None,
    image_url: Optional[str] = None,
    session_id: Optional[str] = None,
) -> CarAssistantState:
    """Factory for a clean initial state dict."""
    return CarAssistantState(
        request_id=request_id,
        user_query=user_query,
        session_id=session_id,
        intent=None,
        vehicle=vehicle,
        vehicle_candidates=[],
        vehicle_confidence=vehicle.confidence if vehicle else 0.0,
        issue=None,
        image_url=image_url,
        image_context=None,
        missing_fields=[],
        selected_agents=[],
        agent_results={},
        debug_trace=[],
        sources=[],
        merged_context=None,
        final_answer=None,
        final_output=None,
        confidence=0.0,
        needs_clarification=False,
        clarification_questions=[],
        uncertainty_notes=[],
    )
