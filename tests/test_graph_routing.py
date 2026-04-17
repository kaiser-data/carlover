"""
Unit tests for graph routing logic (no LLM required).
Tests the route_agents node and check_required_fields node in isolation.
"""
import pytest

from app.agents.orchestrator_agent import route_agents
from app.graph.nodes import check_required_fields
from app.graph.state import initial_state
from app.schemas.common import VehicleInfo


def _state_with(intent: str, vehicle=None, image_url=None):
    s = initial_state(user_query="test", request_id="test")
    s["intent"] = intent
    if vehicle:
        s["vehicle"] = vehicle
        s["vehicle_confidence"] = vehicle.confidence
    if image_url:
        s["image_url"] = image_url
    return s


# ------------------------------------------------------------------ #
# route_agents
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_diagnosis_with_vehicle_selects_adac_supabase():
    state = _state_with("diagnosis", vehicle=VehicleInfo(make="VW", model="Golf", year=2017, confidence=0.9))
    result = await route_agents(state)
    assert "adac" in result["selected_agents"]
    assert "supabase" in result["selected_agents"]


@pytest.mark.asyncio
async def test_diagnosis_without_vehicle_selects_only_adac():
    state = _state_with("diagnosis")
    result = await route_agents(state)
    assert "adac" in result["selected_agents"]
    assert "supabase" not in result["selected_agents"]


@pytest.mark.asyncio
async def test_image_analysis_selects_image_agent():
    state = _state_with("image_analysis", image_url="http://example.com/img.jpg")
    result = await route_agents(state)
    assert "image" in result["selected_agents"]


@pytest.mark.asyncio
async def test_image_url_always_adds_image_agent():
    """Any intent with an image_url should include the image agent."""
    state = _state_with("diagnosis", vehicle=VehicleInfo(make="VW", model="Golf", confidence=0.9), image_url="http://example.com/img.jpg")
    result = await route_agents(state)
    assert "image" in result["selected_agents"]
    assert "adac" in result["selected_agents"]


@pytest.mark.asyncio
async def test_general_intent_selects_adac():
    state = _state_with("general")
    result = await route_agents(state)
    assert "adac" in result["selected_agents"]
    assert "supabase" not in result["selected_agents"]


# ------------------------------------------------------------------ #
# check_required_fields
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_diagnosis_without_vehicle_triggers_clarification():
    state = _state_with("diagnosis")
    result = await check_required_fields(state)
    assert result["needs_clarification"] is True
    assert "vehicle" in result["missing_fields"]
    assert len(result["clarification_questions"]) > 0


@pytest.mark.asyncio
async def test_diagnosis_with_high_confidence_vehicle_no_clarification():
    state = _state_with("diagnosis", vehicle=VehicleInfo(make="VW", model="Golf", year=2017, confidence=0.95))
    result = await check_required_fields(state)
    assert result["needs_clarification"] is False
    assert result["missing_fields"] == []


@pytest.mark.asyncio
async def test_low_confidence_vehicle_triggers_clarification():
    state = _state_with("diagnosis", vehicle=VehicleInfo(make="VW", model="Golf", confidence=0.50))
    result = await check_required_fields(state)
    assert result["needs_clarification"] is True


@pytest.mark.asyncio
async def test_general_intent_no_vehicle_no_clarification():
    """General intent doesn't require vehicle info."""
    state = _state_with("general")
    result = await check_required_fields(state)
    assert result["needs_clarification"] is False
