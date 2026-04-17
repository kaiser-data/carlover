"""
LangGraph StateGraph definition for the Carlover automotive assistant.

Graph flow:
  intake
    → classify_intent
    → extract_entities
    → check_required_fields
    ↙                    ↘
clarify_if_needed     route_agents
    ↓                    ↓
  finalize           run_subagents
                         ↓
                    merge_results
                         ↓
                       answer
                         ↓
                      finalize
"""
from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.agents.orchestrator_agent import (
    classify_intent,
    extract_entities,
    route_agents,
)
from app.graph.nodes import (
    answer,
    check_required_fields,
    clarify_if_needed,
    finalize,
    intake,
    merge_results,
    run_subagents,
)
from app.graph.state import CarAssistantState


def _route_after_check(state: CarAssistantState) -> str:
    """Conditional edge: clarify if fields are missing, otherwise run agents."""
    return "clarify_if_needed" if state.get("needs_clarification") else "route_agents"


def build_graph() -> StateGraph:
    """Build and return the compiled LangGraph state graph."""
    builder = StateGraph(CarAssistantState)

    # --- Nodes ---
    builder.add_node("intake", intake)
    builder.add_node("classify_intent", classify_intent)
    builder.add_node("extract_entities", extract_entities)
    builder.add_node("check_required_fields", check_required_fields)
    builder.add_node("clarify_if_needed", clarify_if_needed)
    builder.add_node("route_agents", route_agents)
    builder.add_node("run_subagents", run_subagents)
    builder.add_node("merge_results", merge_results)
    builder.add_node("answer", answer)
    builder.add_node("finalize", finalize)

    # --- Edges: happy path ---
    builder.add_edge(START, "intake")
    builder.add_edge("intake", "classify_intent")
    builder.add_edge("classify_intent", "extract_entities")
    builder.add_edge("extract_entities", "check_required_fields")

    # --- Conditional edge: clarify vs. proceed ---
    builder.add_conditional_edges(
        "check_required_fields",
        _route_after_check,
        {
            "clarify_if_needed": "clarify_if_needed",
            "route_agents": "route_agents",
        },
    )

    builder.add_edge("clarify_if_needed", "finalize")
    builder.add_edge("route_agents", "run_subagents")
    builder.add_edge("run_subagents", "merge_results")
    builder.add_edge("merge_results", "answer")
    builder.add_edge("answer", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()


@lru_cache(maxsize=1)
def get_compiled_graph():
    """Return the compiled graph, built once and cached."""
    return build_graph()
