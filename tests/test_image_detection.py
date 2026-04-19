"""
Image detection scenario tests — covers vehicle counting, multi-car, warning lights,
rotation, and no-vehicle cases using mocked vision LLM (no real network calls).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_image_result(**kwargs):
    """Build a minimal ImageAnalysisResult-like object for mocking."""
    from app.agents.image_agent import ImageAnalysisResult, _BBox
    defaults = dict(
        observations=[],
        possible_findings=[],
        warning_lights_detected=[],
        damage_detected=False,
        limitations=[],
        confidence=0.85,
        raw_description=None,
        vehicle_detected=True,
        vehicle_count=1,
        image_quality="good",
        needs_clarification=False,
        clarification_questions=[],
        detected_make=None,
        detected_model=None,
        vehicle_boxes=[],
        image_rotation_deg=0,
    )
    defaults.update(kwargs)
    return ImageAnalysisResult(**defaults)


@pytest.mark.asyncio
async def test_single_car_identified(mock_llm, monkeypatch):
    """Single VW Golf → make/model set, no clarification."""
    from app.agents.image_agent import run_image_agent

    structured_result = _mock_image_result(
        vehicle_count=1,
        detected_make="VW",
        detected_model="Golf",
        observations=["Blue hatchback, clean exterior"],
        confidence=0.9,
    )

    mock_llm_instance = MagicMock()
    mock_llm_instance.ainvoke = AsyncMock(return_value=MagicMock(content="1"))
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=structured_result)
    mock_llm_instance.with_structured_output = MagicMock(return_value=mock_structured)
    mock_llm_instance.bind = MagicMock(return_value=mock_llm_instance)

    with patch("app.agents.image_agent.get_model", return_value=mock_llm_instance):
        result = await run_image_agent({"image_url": "https://example.com/golf.jpg"})

    assert result.detected_make == "VW"
    assert result.detected_model == "Golf"
    assert result.needs_clarification is False
    assert result.vehicle_count == 1


@pytest.mark.asyncio
async def test_two_foreground_cars_triggers_clarification(mock_llm, monkeypatch):
    """Two prominent cars → needs_clarification, clarification question, two boxes."""
    from app.agents.image_agent import _BBox, run_image_agent

    boxes = [
        _BBox(label="Car 1 – blue VW Golf (left)", x1=0.0, y1=0.1, x2=0.48, y2=0.9),
        _BBox(label="Car 2 – white SEAT Leon (right)", x1=0.52, y1=0.1, x2=1.0, y2=0.9),
    ]
    structured_result = _mock_image_result(
        vehicle_count=2,
        needs_clarification=True,
        detected_make=None,
        detected_model=None,
        observations=["Blue VW Golf (left)", "White SEAT Leon (right)"],
        clarification_questions=["Two cars: blue VW Golf (left) or white SEAT Leon (right)?"],
        vehicle_boxes=boxes,
    )

    mock_llm_instance = MagicMock()
    mock_llm_instance.ainvoke = AsyncMock(return_value=MagicMock(content="2"))
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=structured_result)
    mock_llm_instance.with_structured_output = MagicMock(return_value=mock_structured)
    mock_llm_instance.bind = MagicMock(return_value=mock_llm_instance)

    with patch("app.agents.image_agent.get_model", return_value=mock_llm_instance):
        result = await run_image_agent({"image_url": "https://example.com/two_cars.jpg"})

    assert result.vehicle_count == 2
    assert result.needs_clarification is True
    assert result.detected_make is None
    assert result.detected_model is None
    assert len(result.clarification_questions) >= 1
    assert len(result.vehicle_boxes) == 2


@pytest.mark.asyncio
async def test_pre_count_overrides_structured_vehicle_count(mock_llm, monkeypatch):
    """Pre-count returns 2 but structured output says 1 → agent enforces 2."""
    from app.agents.image_agent import run_image_agent

    # Structured model wrongly says 1
    structured_result = _mock_image_result(
        vehicle_count=1,
        detected_make="VW",
        detected_model="Golf",
        raw_description="I see a blue car on the left and a white car on the right side",
    )

    mock_llm_instance = MagicMock()
    # Plain-text count says 2
    mock_llm_instance.ainvoke = AsyncMock(return_value=MagicMock(content="2"))
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=structured_result)
    mock_llm_instance.with_structured_output = MagicMock(return_value=mock_structured)
    mock_llm_instance.bind = MagicMock(return_value=mock_llm_instance)

    with patch("app.agents.image_agent.get_model", return_value=mock_llm_instance):
        result = await run_image_agent({"image_url": "https://example.com/two_cars.jpg"})

    assert result.vehicle_count == 2
    assert result.needs_clarification is True
    assert result.detected_make is None  # nulled out for multi-car


@pytest.mark.asyncio
async def test_warning_lights_detected(mock_llm, monkeypatch):
    """Dashboard photo with two warning lights → both in response."""
    from app.agents.image_agent import run_image_agent

    structured_result = _mock_image_result(
        vehicle_count=1,
        warning_lights_detected=["engine_warning", "oil_pressure"],
        observations=["Engine warning light (amber)", "Oil pressure light (red)"],
        damage_detected=False,
        confidence=0.92,
    )

    mock_llm_instance = MagicMock()
    mock_llm_instance.ainvoke = AsyncMock(return_value=MagicMock(content="1"))
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=structured_result)
    mock_llm_instance.with_structured_output = MagicMock(return_value=mock_structured)
    mock_llm_instance.bind = MagicMock(return_value=mock_llm_instance)

    with patch("app.agents.image_agent.get_model", return_value=mock_llm_instance):
        result = await run_image_agent({"image_url": "https://example.com/dashboard.jpg"})

    assert "engine_warning" in result.warning_lights_detected
    assert "oil_pressure" in result.warning_lights_detected
    assert len(result.observations) == 2


@pytest.mark.asyncio
async def test_rotated_image_detected(mock_llm, monkeypatch):
    """Sideways photo → image_rotation_deg=90 in response."""
    from app.agents.image_agent import run_image_agent

    structured_result = _mock_image_result(
        vehicle_count=1,
        image_rotation_deg=90,
        observations=["Car appears rotated 90 degrees clockwise"],
        image_quality="good",
    )

    mock_llm_instance = MagicMock()
    mock_llm_instance.ainvoke = AsyncMock(return_value=MagicMock(content="1"))
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=structured_result)
    mock_llm_instance.with_structured_output = MagicMock(return_value=mock_structured)
    mock_llm_instance.bind = MagicMock(return_value=mock_llm_instance)

    with patch("app.agents.image_agent.get_model", return_value=mock_llm_instance):
        result = await run_image_agent({"image_url": "https://example.com/rotated.jpg"})

    assert result.image_rotation_deg == 90


@pytest.mark.asyncio
async def test_no_vehicle_triggers_clarification(mock_llm, monkeypatch):
    """Photo with no car → vehicle_detected=False, clarification question added."""
    from app.agents.image_agent import run_image_agent

    structured_result = _mock_image_result(
        vehicle_count=0,
        vehicle_detected=False,
        confidence=0.1,
        observations=[],
        clarification_questions=[],
    )

    mock_llm_instance = MagicMock()
    mock_llm_instance.ainvoke = AsyncMock(return_value=MagicMock(content="0"))
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=structured_result)
    mock_llm_instance.with_structured_output = MagicMock(return_value=mock_structured)
    mock_llm_instance.bind = MagicMock(return_value=mock_llm_instance)

    with patch("app.agents.image_agent.get_model", return_value=mock_llm_instance):
        result = await run_image_agent({"image_url": "https://example.com/landscape.jpg"})

    assert result.vehicle_detected is False
    assert result.needs_clarification is True
    assert len(result.clarification_questions) >= 1
    assert "vehicle" in result.clarification_questions[0].lower()


@pytest.mark.asyncio
async def test_no_image_url_returns_limitation(mock_llm, monkeypatch):
    """No image URL provided → confidence 0 with limitation message."""
    from app.agents.image_agent import run_image_agent

    result = await run_image_agent({"image_url": None})

    assert result.confidence == 0.0
    assert any("No image" in lim for lim in result.limitations)
