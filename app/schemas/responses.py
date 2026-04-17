from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.common import SourceInfo, TraceEntry
from app.schemas.image_outputs import ImageAgentOutput


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatResponse(BaseModel):
    request_id: str
    answer: str
    sources: list[SourceInfo] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    used_agents: list[str] = Field(default_factory=list)
    debug_trace: list[TraceEntry] = Field(default_factory=list)
    elapsed_ms: float = 0.0
    uncertainty_notes: list[str] = Field(default_factory=list)


class ImageAnalysisResponse(ImageAgentOutput):
    request_id: str = ""
    elapsed_ms: float = 0.0


class GraphDebugResponse(BaseModel):
    nodes: list[str]
    edges: list[dict[str, Any]]
    entry_point: Optional[str] = None
