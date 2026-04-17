from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Request
from loguru import logger

from app.api.deps import SettingsDep
from app.evaluation.evaluation_service import get_evaluation_service
from app.graph.state import initial_state
from app.schemas.requests import ChatRequest
from app.schemas.responses import ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(
    body: ChatRequest,
    request: Request,
    settings: SettingsDep,
) -> ChatResponse:
    """
    Main chat endpoint. Runs the full LangGraph pipeline.

    Returns a structured response with answer, sources, confidence,
    clarification questions, and debug trace.
    """
    t0 = time.monotonic()
    request_id = str(uuid.uuid4())
    graph = request.app.state.graph

    state = initial_state(
        user_query=body.query,
        request_id=request_id,
        vehicle=body.vehicle,
        image_url=body.image_url,
        session_id=body.session_id,
    )

    logger.info(f"[{request_id[:8]}] Chat request: {body.query[:80]!r}")

    try:
        result = await graph.ainvoke(state)
    except Exception as exc:
        logger.error(f"[{request_id[:8]}] Graph invocation failed: {exc}")
        return ChatResponse(
            request_id=request_id,
            answer="Ein interner Fehler ist aufgetreten. Bitte versuchen Sie es erneut.",
            confidence=0.0,
            elapsed_ms=(time.monotonic() - t0) * 1000,
            uncertainty_notes=[str(exc)],
        )

    elapsed_ms = (time.monotonic() - t0) * 1000
    logger.info(f"[{request_id[:8]}] Completed in {elapsed_ms:.0f}ms")

    # Build response
    final_output = result.get("final_output")
    response = ChatResponse(
        request_id=request_id,
        answer=result.get("final_answer") or "Keine Antwort generiert.",
        sources=result.get("sources", []),
        confidence=result.get("confidence", 0.0),
        needs_clarification=result.get("needs_clarification", False),
        clarification_questions=result.get("clarification_questions", []),
        used_agents=list(result.get("agent_results", {}).keys()),
        debug_trace=result.get("debug_trace", []) if settings.DEBUG else [],
        elapsed_ms=elapsed_ms,
        uncertainty_notes=result.get("uncertainty_notes", []),
    )

    # Log for evaluation / fine-tuning data collection
    eval_svc = get_evaluation_service()
    await eval_svc.log(
        request_id=request_id,
        query=body.query,
        vehicle=result.get("vehicle"),
        intent=result.get("intent"),
        response=response.answer,
        agent_results=result.get("agent_results", {}),
        confidence=response.confidence,
    )

    return response
