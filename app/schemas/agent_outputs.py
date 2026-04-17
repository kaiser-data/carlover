from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import SourceInfo


# ------------------------------------------------------------------ #
# Base agent output
# ------------------------------------------------------------------ #


class AgentOutput(BaseModel):
    """Base class for all agent outputs."""

    agent_name: str
    success: bool = True
    error: Optional[str] = None
    partial: bool = False  # True when agent ran but data is incomplete
    sources: list[SourceInfo] = Field(default_factory=list)


# ------------------------------------------------------------------ #
# ADAC Agent
# ------------------------------------------------------------------ #


class ADACGeneration(BaseModel):
    name: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None  # None = still in production


class ADACClassThresholds(BaseModel):
    """ADAC segment-class average thresholds for a given year.
    Breakdowns/1000 below each value earns that rating."""
    sehr_gut: float   # ≤ this → "sehr gut"
    gut: float        # ≤ this → "gut"
    befriedigend: float
    ausreichend: float


class ADACReliabilityYear(BaseModel):
    year: int
    breakdowns_per_1000: float
    rating: str       # "sehr gut" | "gut" | "befriedigend" | "ausreichend" | "mangelhaft"
    rating_score: float = Field(ge=0.0, le=1.0)  # 0.95 / 0.80 / 0.60 / 0.35 / 0.15
    generation_name: Optional[str] = None        # e.g. "G01/F97"
    class_thresholds: Optional[ADACClassThresholds] = None
    annual_mileage_km: Optional[int] = None      # mileage assumption used by ADAC


class ADACVehicleInfo(BaseModel):
    make: str
    model: str
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    engine_types: list[str] = Field(default_factory=list)
    description: str = ""
    known_issues_summary: str = ""  # kept for backwards compat / answer agent
    generations: list[ADACGeneration] = Field(default_factory=list)
    reliability_by_year: list[ADACReliabilityYear] = Field(default_factory=list)
    image_url: Optional[str] = None      # primary vehicle photo extracted from ADAC page
    adac_page_url: str = ""              # canonical ADAC page URL — always populated


class ADACIssuePattern(BaseModel):
    pattern_name: str
    symptoms: list[str] = Field(default_factory=list)
    root_cause: str = ""
    solution: str = ""
    severity: str = "medium"  # low | medium | high | critical
    affected_years: Optional[str] = None


class ADACServiceGuidance(BaseModel):
    service_interval_km: Optional[int] = None
    service_interval_months: Optional[int] = None
    typical_cost_eur: Optional[float] = None
    notes: str = ""


class ADACAgentOutput(AgentOutput):
    agent_name: str = "adac"
    vehicle_info: Optional[ADACVehicleInfo] = None
    issue_patterns: list[ADACIssuePattern] = Field(default_factory=list)
    service_guidance: Optional[ADACServiceGuidance] = None


# ------------------------------------------------------------------ #
# Supabase Agent
# ------------------------------------------------------------------ #


class SupabaseWeakness(BaseModel):
    component: str
    description: str
    severity: str = "medium"
    source: str = "internal"


class SupabaseServiceCase(BaseModel):
    mileage: Optional[int] = None
    issue_type: str = ""
    resolution: str = ""
    cost_eur: Optional[float] = None


class SupabaseAgentOutput(AgentOutput):
    agent_name: str = "supabase"
    vehicle_found: bool = False
    weaknesses: list[SupabaseWeakness] = Field(default_factory=list)
    service_cases: list[SupabaseServiceCase] = Field(default_factory=list)
    issue_patterns: list[dict[str, Any]] = Field(default_factory=list)


# ------------------------------------------------------------------ #
# Final answer output
# ------------------------------------------------------------------ #


class FinalAnswerOutput(BaseModel):
    model_config = {"extra": "ignore"}

    answer: str = ""
    sources: list[SourceInfo] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        # Map common alternative field names to 'answer'
        if not data.get("answer"):
            for alt in ("summary", "response", "text", "message", "result"):
                if data.get(alt):
                    data["answer"] = data[alt]
                    break
        # Normalize sources: plain strings → SourceInfo dicts
        raw_sources = data.get("sources", [])
        normalized = []
        for s in raw_sources:
            if isinstance(s, str):
                normalized.append({"label": s, "type": "unknown", "confidence": 1.0})
            elif isinstance(s, dict):
                s.setdefault("type", "unknown")
                s.setdefault("confidence", 1.0)
                normalized.append(s)
            else:
                normalized.append(s)
        data["sources"] = normalized
        return data
