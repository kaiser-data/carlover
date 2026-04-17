from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import VehicleInfo


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="User's question")
    vehicle: Optional[VehicleInfo] = Field(
        default=None,
        description="Pre-filled vehicle context, if known",
    )
    image_url: Optional[str] = Field(
        default=None,
        description="URL or base64 data URI of an image to analyze",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session identifier for conversation continuity",
    )


class ImageAnalysisRequest(BaseModel):
    image_url: Optional[str] = Field(
        default=None,
        description="URL or base64 data URI of the image",
    )
    context: Optional[str] = Field(
        default=None,
        description="Optional text context to guide analysis (e.g. 'dashboard warning lights')",
    )
    vehicle: Optional[VehicleInfo] = None
