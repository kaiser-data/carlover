from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ #
# Vehicle
# ------------------------------------------------------------------ #


class VehicleInfo(BaseModel):
    """A resolved vehicle, potentially with a confidence score."""

    make: str
    model: str
    year: Optional[int] = None
    variant: Optional[str] = None  # e.g. "GTI", "TDI", "xDrive"
    vin: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class VehicleCandidate(BaseModel):
    """One ranked candidate from entity extraction."""

    model_config = {"extra": "ignore"}

    make: str
    model: str
    year_range: Optional[tuple[int, int]] = None  # e.g. (2013, 2020) for Golf 7
    variant: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    match_reason: str = ""


# ------------------------------------------------------------------ #
# Sources & Confidence
# ------------------------------------------------------------------ #

SourceType = Literal["adac", "supabase", "image", "internal", "unknown"]


class SourceInfo(BaseModel):
    label: str
    type: SourceType
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    url: Optional[str] = None


# ------------------------------------------------------------------ #
# Debug trace
# ------------------------------------------------------------------ #


class TraceEntry(BaseModel):
    node: str
    elapsed_ms: float
    note: Optional[str] = None
