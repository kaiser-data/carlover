"""
Supabase agent tests using a None client (no real Supabase required).
Verifies graceful degradation when credentials are absent.
"""
import pytest

from app.agents.supabase_agent import run_supabase_agent
from app.graph.state import initial_state
from app.providers.supabase.repository import SupabaseRepository
from app.schemas.common import VehicleInfo


@pytest.mark.asyncio
async def test_supabase_agent_no_vehicle():
    state = initial_state(user_query="test", request_id="test-1")
    result = await run_supabase_agent(state)
    assert result.success is False
    assert result.partial is True


@pytest.mark.asyncio
async def test_supabase_agent_no_client():
    """Without a real Supabase client, agent should return gracefully."""
    state = initial_state(
        user_query="test",
        request_id="test-2",
        vehicle=VehicleInfo(make="VW", model="Golf", year=2017, confidence=0.9),
    )
    result = await run_supabase_agent(state)
    # No real client → vehicle_found=False, but should not raise
    assert result.agent_name == "supabase"
    assert isinstance(result.weaknesses, list)
    assert isinstance(result.service_cases, list)


def test_repository_returns_empty_without_client():
    repo = SupabaseRepository(client=None)
    import asyncio
    vehicles = asyncio.run(repo.get_vehicles_by_make_model("VW", "Golf"))
    assert vehicles == []

    weaknesses = asyncio.run(repo.get_weaknesses_by_vehicle_id("fake-id"))
    assert weaknesses == []
