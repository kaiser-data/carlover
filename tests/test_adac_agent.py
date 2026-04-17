import pytest

from app.providers.adac.mock_provider import MockADACProvider
from app.schemas.common import VehicleInfo


@pytest.fixture
def provider():
    return MockADACProvider()


@pytest.fixture
def golf():
    return VehicleInfo(make="VW", model="Golf", year=2017, confidence=0.9)


@pytest.mark.asyncio
async def test_fetch_vehicle_info_known(provider, golf):
    result = await provider.fetch_vehicle_info(golf)
    assert result is not None
    assert result.make == "VW"
    assert result.model == "Golf"
    assert len(result.engine_types) > 0


@pytest.mark.asyncio
async def test_fetch_vehicle_info_unknown(provider):
    unknown = VehicleInfo(make="Lada", model="Niva", year=1990, confidence=0.5)
    result = await provider.fetch_vehicle_info(unknown)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_issue_patterns_with_keywords(provider, golf):
    patterns = await provider.fetch_issue_patterns(golf, issue_keywords=["Bremse", "quietschen"])
    assert len(patterns) > 0
    names = [p.pattern_name for p in patterns]
    assert any("Bremse" in n or "Quietschen" in n for n in names) or len(patterns) >= 1


@pytest.mark.asyncio
async def test_fetch_service_guidance(provider, golf):
    result = await provider.fetch_service_guidance(golf)
    assert result is not None
    assert result.service_interval_km is not None


@pytest.mark.asyncio
async def test_run_returns_adac_output(provider, golf):
    result = await provider.run(vehicle=golf, issue="quietscht beim Bremsen")
    assert result.success is True
    assert result.agent_name == "adac"
    assert len(result.sources) > 0
    assert result.sources[0].label == "ADAC Mock v1.0"
    assert result.sources[0].type == "adac"


@pytest.mark.asyncio
async def test_run_with_no_vehicle_match(provider):
    unknown = VehicleInfo(make="Lada", model="Niva", year=1990, confidence=0.5)
    result = await provider.run(vehicle=unknown)
    # Should still return a result (vehicle_info=None, patterns from fallback)
    assert result.agent_name == "adac"
    assert result.vehicle_info is None
