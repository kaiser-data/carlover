from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ImageAgentOutput(BaseModel):
    """Structured output from the image analysis agent."""

    observations: list[str] = Field(
        default_factory=list,
        description="Raw visual observations from the image",
    )
    possible_findings: list[str] = Field(
        default_factory=list,
        description="Possible diagnoses or issues inferred from observations",
    )
    warning_lights_detected: list[str] = Field(
        default_factory=list,
        description="Warning light identifiers found in image, e.g. 'engine_warning'",
    )
    damage_detected: bool = False
    limitations: list[str] = Field(
        default_factory=list,
        description="Limitations of the analysis (low resolution, partial view, etc.)",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    raw_description: Optional[str] = None

    # Edge case detection
    vehicle_detected: bool = True
    vehicle_count: int = Field(default=0, ge=0, description="0=unknown, 1=single, 2+=multiple")
    image_quality: str = Field(default="good", description="good | poor | unusable")
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)

    # Identified vehicle (extracted by vision model)
    detected_make: Optional[str] = Field(default=None, description="Vehicle make if identifiable")
    detected_model: Optional[str] = Field(default=None, description="Vehicle model if identifiable")

    # ADAC enrichment (populated after vehicle identification)
    adac_summary: Optional[str] = Field(default=None, description="ADAC known issues summary")
    adac_issue_patterns: list[dict] = Field(default_factory=list, description="ADAC breakdown patterns")
