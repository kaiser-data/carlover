"""
Image analysis flow tests with mocked vision LLM.
"""
import pytest


@pytest.mark.asyncio
async def test_image_analyze_with_url(async_test_client):
    resp = await async_test_client.post(
        "/image/analyze",
        data={"image_url": "https://example.com/dashboard.jpg"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "observations" in data
    assert "possible_findings" in data
    assert "warning_lights_detected" in data
    assert "confidence" in data
    assert "damage_detected" in data
    assert "limitations" in data


@pytest.mark.asyncio
async def test_image_analyze_no_input_returns_limitation(async_test_client):
    resp = await async_test_client.post("/image/analyze", data={})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["limitations"]) > 0
    assert data["confidence"] == 0.0


@pytest.mark.asyncio
async def test_image_analyze_standalone():
    """Test image agent directly, without HTTP layer."""
    from app.agents.image_agent import analyze_image_standalone

    result = await analyze_image_standalone(
        image_url="https://example.com/test.jpg",
        context="Dashboard Warnleuchten",
    )
    assert result is not None
    assert isinstance(result.observations, list)
    assert isinstance(result.confidence, float)
