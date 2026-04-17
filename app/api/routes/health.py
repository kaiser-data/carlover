from fastapi import APIRouter

from app.config import get_settings
from app.schemas.responses import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health_check() -> HealthResponse:
    """Basic liveness check."""
    settings = get_settings()
    return HealthResponse(version=settings.APP_VERSION)
