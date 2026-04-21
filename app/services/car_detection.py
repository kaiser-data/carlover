"""
Car detection + classification via HuggingFace Inference API.

Two specialized models replace the VLM for identity/count so the pipeline
stays reliable when the VLM is down:

- Detection: facebook/detr-resnet-50 → count + bounding boxes
- Classification: dima806/car_models_image_detection → make/model

The VLM (Featherless) is called in parallel but only for enrichment:
observations, damage, warning lights.
"""
from __future__ import annotations

import asyncio
import base64
import io
from typing import Optional

import httpx
from loguru import logger
from PIL import Image

from app.config import get_settings
from app.schemas.image_outputs import VehicleBoundingBox

_COCO_VEHICLE_LABELS = {"car", "truck", "bus"}

# Multi-word brand labels from dima806/car_models_image_detection.
# Without this list the splitter would mis-parse "Mercedes-Benz C-Class" as
# make="Mercedes-Benz" (correct) but greedy first-space splits like
# "Aston Martin DB11" would fail.
_MULTI_WORD_BRANDS = {
    "Alfa Romeo",
    "Aston Martin",
    "Land Rover",
    "Mercedes-Benz",
    "Rolls-Royce",
}

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    """Lazy-init a module-level AsyncClient with pre-baked HF auth header."""
    global _client
    if _client is None:
        settings = get_settings()
        headers = {}
        if settings.HUGGINGFACE_API_KEY:
            headers["Authorization"] = f"Bearer {settings.HUGGINGFACE_API_KEY}"
        _client = httpx.AsyncClient(
            base_url=settings.HF_API_BASE,
            headers=headers,
            timeout=settings.HF_TIMEOUT,
        )
    return _client


async def close_client() -> None:
    """Close the shared AsyncClient. Call from app shutdown if needed."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def is_enabled() -> bool:
    """Return True if an HF API key is configured."""
    return bool(get_settings().HUGGINGFACE_API_KEY)


async def fetch_image_bytes(image_url: str) -> bytes:
    """Return raw image bytes from either an http(s) URL or a data URI."""
    if image_url.startswith("data:"):
        # data:image/jpeg;base64,<payload>
        _, _, b64 = image_url.partition(",")
        return base64.b64decode(b64)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        r = await c.get(image_url)
        r.raise_for_status()
        return r.content


def _parse_brand_model(label: str) -> tuple[str, str]:
    """Split a dima806 label like 'Volkswagen Beetle' into (make, model)."""
    label = label.strip()
    for brand in _MULTI_WORD_BRANDS:
        if label.startswith(brand + " "):
            return brand, label[len(brand) + 1 :].strip()
    parts = label.split(" ", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return label, ""


async def _hf_post(model: str, image_bytes: bytes, *, content_type: str = "image/jpeg") -> object:
    """POST raw image bytes to an HF model endpoint and return parsed JSON.

    Retries once on 503 with an `estimated_time` payload (model loading).
    All other errors bubble up to the caller.
    """
    client = _get_client()
    path = f"/models/{model}"
    for attempt in range(2):
        r = await client.post(path, content=image_bytes, headers={"Content-Type": content_type})
        if r.status_code == 200:
            return r.json()
        if r.status_code == 503 and attempt == 0:
            try:
                wait = min(30.0, float(r.json().get("estimated_time", 5)) + 1)
            except Exception:
                wait = 5.0
            logger.info(f"HF {model} loading, waiting {wait:.1f}s")
            await asyncio.sleep(wait)
            continue
        r.raise_for_status()
    r.raise_for_status()  # type: ignore[unreachable]
    return None  # pragma: no cover


async def detect_cars(image_bytes: bytes) -> tuple[list[VehicleBoundingBox], tuple[int, int]]:
    """Return (boxes, (width, height)).

    Boxes are filtered to COCO vehicle classes above the min score threshold
    and normalized to 0–1 coords to match VehicleBoundingBox.
    """
    settings = get_settings()
    # Pillow reads image dims in ~1 ms without decoding pixel data.
    with Image.open(io.BytesIO(image_bytes)) as im:
        w, h = im.size

    data = await _hf_post(settings.HF_DETECTION_MODEL, image_bytes)
    boxes: list[VehicleBoundingBox] = []
    if not isinstance(data, list):
        return boxes, (w, h)

    for det in data:
        label = det.get("label", "").lower()
        score = float(det.get("score", 0.0))
        if label not in _COCO_VEHICLE_LABELS or score < settings.HF_DETECTION_MIN_SCORE:
            continue
        box = det.get("box") or {}
        try:
            boxes.append(
                VehicleBoundingBox(
                    label=f"{label} #{len(boxes) + 1}",
                    x1=max(0.0, float(box["xmin"]) / w),
                    y1=max(0.0, float(box["ymin"]) / h),
                    x2=min(1.0, float(box["xmax"]) / w),
                    y2=min(1.0, float(box["ymax"]) / h),
                    confidence=score,
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(f"detect_cars: skipping malformed detection {det!r}: {exc}")

    return boxes, (w, h)


async def classify_car(image_bytes: bytes) -> tuple[Optional[str], Optional[str], float]:
    """Return (make, model, confidence).

    Returns (None, None, 0.0) if the top score is below the min threshold.
    """
    settings = get_settings()
    data = await _hf_post(settings.HF_CLASSIFICATION_MODEL, image_bytes)
    if not isinstance(data, list) or not data:
        return None, None, 0.0

    top = max(data, key=lambda d: float(d.get("score", 0.0)))
    score = float(top.get("score", 0.0))
    if score < settings.HF_CLASSIFICATION_MIN_SCORE:
        return None, None, score

    make, model = _parse_brand_model(str(top.get("label", "")))
    return make or None, model or None, score


# 1x1 white PNG for warm-up requests (68 bytes).
_WARMUP_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP8//8/AAX+Av7K2Y0tAAAAAElFTkSuQmCC"
)


async def warm_up() -> None:
    """Fire one tiny request to each HF model so the first user doesn't cold-start.

    Runs in parallel; swallows errors (warmup failure is non-fatal).
    """
    if not is_enabled():
        logger.info("HF warm-up skipped (no HUGGINGFACE_API_KEY configured)")
        return

    settings = get_settings()

    async def _warm(model: str) -> None:
        try:
            await _hf_post(model, _WARMUP_PNG, content_type="image/png")
            logger.info(f"HF warmup OK: {model}")
        except Exception as exc:
            logger.warning(f"HF warmup failed for {model}: {str(exc)[:120]}")

    await asyncio.gather(
        _warm(settings.HF_DETECTION_MODEL),
        _warm(settings.HF_CLASSIFICATION_MODEL),
        return_exceptions=True,
    )
