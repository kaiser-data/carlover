from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.schemas.agent_outputs import (
    ADACAgentOutput,
    ADACIssuePattern,
    ADACServiceGuidance,
    ADACVehicleInfo,
)
from app.schemas.common import VehicleInfo


class ADACBaseProvider(ABC):
    """
    Abstract interface for ADAC-style vehicle data.

    Implement this with a real HTTP client once the actual ADAC
    data source / API credentials are available.
    The mock provider (MockADACProvider) satisfies this interface
    and can be used for development and testing.
    """

    SOURCE_LABEL: str = "ADAC"

    @abstractmethod
    async def fetch_vehicle_info(
        self, vehicle: VehicleInfo
    ) -> Optional[ADACVehicleInfo]:
        """Fetch general vehicle information for a given make/model/year."""
        ...

    @abstractmethod
    async def fetch_issue_patterns(
        self,
        vehicle: VehicleInfo,
        issue_keywords: Optional[list[str]] = None,
    ) -> list[ADACIssuePattern]:
        """Fetch known issue patterns, optionally filtered by keywords."""
        ...

    @abstractmethod
    async def fetch_service_guidance(
        self, vehicle: VehicleInfo
    ) -> Optional[ADACServiceGuidance]:
        """Fetch service interval and cost guidance."""
        ...

    async def run(self, vehicle: VehicleInfo, issue: Optional[str] = None) -> ADACAgentOutput:
        """
        Convenience method: runs all three fetches and assembles ADACAgentOutput.
        Handles individual failures gracefully.
        """
        from app.schemas.common import SourceInfo

        issue_keywords = issue.split() if issue else None
        errors: list[str] = []

        try:
            vehicle_info = await self.fetch_vehicle_info(vehicle)
        except Exception as e:
            vehicle_info = None
            errors.append(f"fetch_vehicle_info: {e}")

        try:
            issue_patterns = await self.fetch_issue_patterns(vehicle, issue_keywords)
        except Exception as e:
            issue_patterns = []
            errors.append(f"fetch_issue_patterns: {e}")

        try:
            service_guidance = await self.fetch_service_guidance(vehicle)
        except Exception as e:
            service_guidance = None
            errors.append(f"fetch_service_guidance: {e}")

        return ADACAgentOutput(
            success=len(errors) == 0,
            partial=len(errors) > 0,
            error="; ".join(errors) if errors else None,
            vehicle_info=vehicle_info,
            issue_patterns=issue_patterns,
            service_guidance=service_guidance,
            sources=[SourceInfo(label=self.SOURCE_LABEL, type="adac", confidence=0.9)],
        )
