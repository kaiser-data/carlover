from __future__ import annotations

from app.config import get_settings
from app.graph.state import CarAssistantState
from app.providers.adac.base import ADACBaseProvider
from app.providers.adac.mock_provider import MockADACProvider
from app.schemas.agent_outputs import ADACAgentOutput
from app.schemas.common import VehicleInfo


def _get_adac_provider() -> ADACBaseProvider:
    settings = get_settings()
    if settings.ADAC_PROVIDER == "real":
        # TODO: Import and return RealADACProvider() when implemented
        raise NotImplementedError("Real ADAC provider not yet implemented. Set ADAC_PROVIDER=mock.")
    return MockADACProvider()


async def run_adac_agent(state: CarAssistantState) -> ADACAgentOutput:
    """
    Fetch vehicle info and issue patterns from the ADAC provider.
    Returns ADACAgentOutput — always structured, never hallucinated.
    """
    vehicle: VehicleInfo | None = state.get("vehicle")

    if vehicle is None:
        return ADACAgentOutput(
            success=False,
            error="No vehicle information available for ADAC lookup.",
            partial=True,
        )

    provider = _get_adac_provider()
    return await provider.run(vehicle=vehicle, issue=state.get("issue"))
