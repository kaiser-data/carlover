import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(async_test_client):
    resp = await async_test_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_version_matches_config(async_test_client):
    from app.config import get_settings
    settings = get_settings()
    resp = await async_test_client.get("/health")
    assert resp.json()["version"] == settings.APP_VERSION
