"""
Shared test fixtures.

Key fixtures:
- mock_settings: Settings with fake API keys (no .env needed)
- mock_llm: Patches the LLM provider to return fixed structured outputs
- async_test_client: HTTPX AsyncClient against the FastAPI app
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ------------------------------------------------------------------ #
# Settings override
# ------------------------------------------------------------------ #

@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """Patch settings to avoid needing a real .env file in tests."""
    monkeypatch.setenv("FEATHERLESS_API_KEY", "test-key-123")
    monkeypatch.setenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_KEY", "")
    monkeypatch.setenv("ADAC_PROVIDER", "mock")
    monkeypatch.setenv("MCP_ENABLED", "false")
    monkeypatch.setenv("DEBUG", "true")

    # Clear lru_cache so patched env is picked up
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ------------------------------------------------------------------ #
# LLM mock
# ------------------------------------------------------------------ #

class MockStructuredLLM:
    """
    Mimics ChatOpenAI.with_structured_output(schema).
    Returns a fixed response based on the schema name.
    """

    def __init__(self, schema):
        self._schema = schema

    async def ainvoke(self, messages: list) -> Any:
        name = self._schema.__name__ if hasattr(self._schema, "__name__") else str(self._schema)

        if name == "IntentClassification":
            return self._schema(intent="diagnosis", confidence=0.9, reasoning="test")
        elif name == "EntityExtraction":
            from app.schemas.common import VehicleCandidate
            candidate = VehicleCandidate(make="VW", model="Golf", confidence=0.9, match_reason="test")
            return self._schema(
                vehicle_candidates=[candidate],
                best_match=candidate,
                issue="Bremsquietschen",
                image_mentioned=False,
            )
        elif name == "FinalAnswerOutput":
            from app.schemas.common import SourceInfo
            return self._schema(
                answer="Testantwort: Bremsbeläge prüfen.",
                sources=[SourceInfo(label="ADAC Mock v1.0", type="adac", confidence=0.85)],
                confidence=0.85,
                needs_clarification=False,
            )
        elif name == "ImageAnalysisResult":
            return self._schema(
                observations=["Motorwarnleuchte leuchtet orange"],
                possible_findings=["Lambdasonde defekt"],
                warning_lights_detected=["engine_warning"],
                damage_detected=False,
                limitations=[],
                confidence=0.8,
            )
        # Fallback
        return self._schema()


class MockChatModel:
    def with_structured_output(self, schema, **kwargs):
        return MockStructuredLLM(schema)


@pytest.fixture
def mock_llm():
    """Patch get_model to return MockChatModel."""
    with patch("app.providers.llm.model_router.get_model", return_value=MockChatModel()):
        # Also patch inside agent modules
        with patch("app.agents.orchestrator_agent.get_model", return_value=MockChatModel()):
            with patch("app.agents.answer_agent.get_model", return_value=MockChatModel()):
                with patch("app.agents.image_agent.get_model", return_value=MockChatModel()):
                    yield


# ------------------------------------------------------------------ #
# FastAPI test client
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture
async def async_test_client(mock_llm):
    from app.graph.graph import build_graph
    from app.main import create_app

    app = create_app()
    # ASGITransport does not trigger the FastAPI lifespan handler,
    # so app.state.graph is never set. Set it manually here.
    app.state.graph = build_graph()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
