"""
End-to-end chat flow tests with mocked LLM.
"""
import pytest


@pytest.mark.asyncio
async def test_chat_returns_200(async_test_client):
    resp = await async_test_client.post("/chat", json={
        "query": "Mein VW Golf 7 2017 macht ein Quietschgeräusch beim Bremsen",
        "vehicle": {"make": "VW", "model": "Golf", "year": 2017, "confidence": 0.9},
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_chat_response_schema(async_test_client):
    resp = await async_test_client.post("/chat", json={
        "query": "Bremsgeräusch beim VW Golf 7",
        "vehicle": {"make": "VW", "model": "Golf", "year": 2017, "confidence": 0.9},
    })
    data = resp.json()
    assert "answer" in data
    assert "confidence" in data
    assert "sources" in data
    assert "used_agents" in data
    assert "needs_clarification" in data
    assert "request_id" in data
    assert "elapsed_ms" in data


@pytest.mark.asyncio
async def test_chat_vague_query_triggers_clarification(async_test_client):
    """Vague query without vehicle should request clarification."""
    # Override mock to return low-confidence extraction
    from unittest.mock import patch, AsyncMock
    from app.schemas.common import VehicleCandidate

    class LowConfidenceLLM:
        def with_structured_output(self, schema, **kwargs):
            class _Mock:
                async def ainvoke(self, msgs):
                    name = schema.__name__
                    if name == "IntentClassification":
                        return schema(intent="diagnosis", confidence=0.8, reasoning="")
                    elif name == "EntityExtraction":
                        return schema(
                            vehicle_candidates=[],
                            best_match=None,
                            issue="macht Geräusche",
                            image_mentioned=False,
                        )
                    return schema()
            return _Mock()

    with patch("app.agents.orchestrator_agent.get_model", return_value=LowConfidenceLLM()):
        with patch("app.agents.answer_agent.get_model", return_value=LowConfidenceLLM()):
            resp = await async_test_client.post("/chat", json={
                "query": "mein Auto macht Geräusche",
            })
    assert resp.status_code == 200
    data = resp.json()
    assert data["needs_clarification"] is True


@pytest.mark.asyncio
async def test_chat_used_agents_populated(async_test_client):
    resp = await async_test_client.post("/chat", json={
        "query": "Was sind bekannte Probleme beim VW Golf 7?",
        "vehicle": {"make": "VW", "model": "Golf", "year": 2017, "confidence": 0.95},
    })
    data = resp.json()
    assert isinstance(data["used_agents"], list)
