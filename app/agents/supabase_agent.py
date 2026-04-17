from __future__ import annotations

from app.graph.state import CarAssistantState
from app.providers.supabase.client import get_supabase_client
from app.providers.supabase.repository import SupabaseRepository
from app.schemas.agent_outputs import SupabaseAgentOutput
from app.schemas.common import SourceInfo, VehicleInfo


async def run_supabase_agent(state: CarAssistantState) -> SupabaseAgentOutput:
    """
    Query internal Supabase data for the given vehicle.
    Returns partial results if client is unavailable or vehicle not found.
    """
    vehicle: VehicleInfo | None = state.get("vehicle")

    if vehicle is None:
        return SupabaseAgentOutput(
            success=False,
            partial=True,
            error="No vehicle information for Supabase query.",
        )

    client = get_supabase_client()
    repo = SupabaseRepository(client)

    # Fetch vehicle_id and associated weaknesses
    vehicle_id, weaknesses = await repo.vehicle_to_weaknesses(vehicle)

    if not vehicle_id:
        return SupabaseAgentOutput(
            success=True,
            vehicle_found=False,
            partial=True,
            error=f"Vehicle {vehicle.make} {vehicle.model} not found in database.",
            sources=[SourceInfo(label="Internal DB", type="supabase", confidence=0.0)],
        )

    # Fetch additional data
    service_cases = await repo.get_service_cases(vehicle_id)
    issue_patterns = await repo.get_issue_patterns(
        make=vehicle.make,
        model=vehicle.model,
    )

    return SupabaseAgentOutput(
        success=True,
        vehicle_found=True,
        weaknesses=weaknesses,
        service_cases=service_cases,
        issue_patterns=issue_patterns,
        sources=[SourceInfo(label="Internal DB", type="supabase", confidence=0.85)],
    )
