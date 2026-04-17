from __future__ import annotations

import base64
import time
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile
from loguru import logger

from app.agents.image_agent import analyze_image_standalone
from app.schemas.requests import ImageAnalysisRequest
from app.schemas.responses import ImageAnalysisResponse

router = APIRouter()


@router.post("/image/analyze", response_model=ImageAnalysisResponse, tags=["image"])
async def analyze_image(
    image_url: Optional[str] = Form(default=None),
    context: Optional[str] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
) -> ImageAnalysisResponse:
    """
    Analyze a vehicle image.

    Accepts either:
    - `image_url`: a URL or base64 data URI (form field)
    - `image`: an uploaded file (multipart/form-data)

    Returns structured observations, possible findings, and detected warning lights.
    """
    t0 = time.monotonic()
    request_id = str(uuid.uuid4())

    # Resolve image input
    resolved_url: Optional[str] = image_url

    if image is not None and resolved_url is None:
        # File upload: encode to base64 data URI
        content = await image.read()
        mime = image.content_type or "image/jpeg"
        b64 = base64.b64encode(content).decode("utf-8")
        resolved_url = f"data:{mime};base64,{b64}"
        logger.debug(f"[{request_id[:8]}] Image upload received: {len(content)} bytes, {mime}")

    if resolved_url is None:
        return ImageAnalysisResponse(
            request_id=request_id,
            observations=[],
            limitations=["No image provided. Supply 'image_url' or upload a file."],
            confidence=0.0,
            elapsed_ms=(time.monotonic() - t0) * 1000,
        )

    logger.info(f"[{request_id[:8]}] Image analysis request")

    result = await analyze_image_standalone(image_url=resolved_url, context=context)

    elapsed_ms = (time.monotonic() - t0) * 1000
    return ImageAnalysisResponse(
        **result.model_dump(),
        request_id=request_id,
        elapsed_ms=elapsed_ms,
    )
