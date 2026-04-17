from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import ADACProviderDep
from app.schemas.agent_outputs import ADACIssuePattern, ADACVehicleInfo
from app.schemas.common import VehicleInfo
from app.utils.vehicle_normalizer import normalize_vehicle

router = APIRouter()


class VehicleLookupRequest(BaseModel):
    make: Optional[str] = Field(default=None, description="Vehicle make — typos accepted")
    model: str = Field(..., min_length=1, description="Vehicle model — typos accepted")
    year: Optional[int] = Field(default=None, ge=1900, le=2030)


class VehicleLookupResponse(BaseModel):
    # What we actually looked up (after normalization)
    normalized_make: str
    normalized_model: str
    year: Optional[int] = None
    corrections: list[str] = Field(default_factory=list, description="Typo corrections applied")

    # ADAC data
    vehicle_info: Optional[ADACVehicleInfo] = None
    issue_patterns: list[ADACIssuePattern] = Field(default_factory=list)

    found: bool = False
    elapsed_ms: float = 0.0


@router.post("/vehicle/lookup", response_model=VehicleLookupResponse, tags=["vehicle"])
async def vehicle_lookup(
    body: VehicleLookupRequest,
    adac: ADACProviderDep,
) -> VehicleLookupResponse:
    """
    Look up ADAC vehicle data with fuzzy make/model matching.

    Accepts imprecise input:
    - Typos:           "Vollkswagen Gollf" → VW Golf
    - Brand-less:      model="Polo"        → VW Polo
    - Swapped fields:  make="Golf"         → VW Golf
    """
    t0 = time.monotonic()

    norm = normalize_vehicle(make=body.make, model=body.model, year=body.year)

    vehicle = VehicleInfo(
        make=norm.make,
        model=norm.model,
        year=norm.year,
    )

    vehicle_info = await adac.fetch_vehicle_info(vehicle)
    issue_patterns = await adac.fetch_issue_patterns(vehicle)

    elapsed_ms = (time.monotonic() - t0) * 1000

    return VehicleLookupResponse(
        normalized_make=norm.make,
        normalized_model=norm.model,
        year=norm.year,
        corrections=norm.corrections,
        vehicle_info=vehicle_info,
        issue_patterns=issue_patterns,
        found=vehicle_info is not None,
        elapsed_ms=elapsed_ms,
    )
