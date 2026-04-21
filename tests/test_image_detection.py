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


# ────────────────────────────────────────────────────────────────────────────
# HF hybrid-path tests — mock car_detection module so no network calls happen
# ────────────────────────────────────────────────────────────────────────────


def _vlm_only_mocks(mock_llm_instance, structured_result):
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=structured_result)
    mock_llm_instance.ainvoke = AsyncMock(return_value=MagicMock(content="1"))
    mock_llm_instance.with_structured_output = MagicMock(return_value=mock_structured)
    mock_llm_instance.bind = MagicMock(return_value=mock_llm_instance)


@pytest.mark.asyncio
async def test_hf_detects_single_car_and_classifier_sets_make_model(mock_llm, monkeypatch):
    """HF detects 1 car + classifier returns Volkswagen Beetle → identity fields come from HF."""
    from app.agents import image_agent
    from app.schemas.image_outputs import VehicleBoundingBox

    box = VehicleBoundingBox(label="car #1", x1=0.1, y1=0.2, x2=0.9, y2=0.85, confidence=0.96)
    vlm_stub = _mock_image_result(
        vehicle_count=1,
        detected_make="WrongMake",   # should be overridden by HF classifier
        detected_model="WrongModel",
        observations=["Light green convertible, soft-top retracted"],
        confidence=0.82,
    )
    mock_llm_instance = MagicMock()
    _vlm_only_mocks(mock_llm_instance, vlm_stub)

    monkeypatch.setattr(image_agent.car_detection, "is_enabled", lambda: True)
    monkeypatch.setattr(image_agent.car_detection, "fetch_image_bytes", AsyncMock(return_value=b"\x89PNG"))
    monkeypatch.setattr(image_agent.car_detection, "detect_cars", AsyncMock(return_value=([box], (640, 480))))
    monkeypatch.setattr(
        image_agent.car_detection,
        "classify_car",
        AsyncMock(return_value=("Volkswagen", "Beetle", 0.92)),
    )

    with patch("app.agents.image_agent.get_model", return_value=mock_llm_instance):
        result = await image_agent.run_image_agent({"image_url": "https://example.com/beetle.jpg"})

    assert result.vehicle_count == 1
    assert result.detected_make == "Volkswagen"
    assert result.detected_model == "Beetle"
    assert result.needs_clarification is False
    assert len(result.vehicle_boxes) == 1
    # VLM observation preserved
    assert any("convertible" in o.lower() for o in result.observations)


@pytest.mark.asyncio
async def test_hf_detects_two_cars_skips_classifier_and_requests_clarification(mock_llm, monkeypatch):
    """HF detects 2 cars → classifier not called, clarification card rendered."""
    from app.agents import image_agent
    from app.schemas.image_outputs import VehicleBoundingBox

    boxes = [
        VehicleBoundingBox(label="car #1", x1=0.05, y1=0.3, x2=0.45, y2=0.8, confidence=0.95),
        VehicleBoundingBox(label="car #2", x1=0.55, y1=0.3, x2=0.95, y2=0.8, confidence=0.94),
    ]
    vlm_stub = _mock_image_result(vehicle_count=1, observations=["Two cars on a racetrack"])
    mock_llm_instance = MagicMock()
    _vlm_only_mocks(mock_llm_instance, vlm_stub)

    classify_mock = AsyncMock(return_value=("Volkswagen", "Golf", 0.8))
    monkeypatch.setattr(image_agent.car_detection, "is_enabled", lambda: True)
    monkeypatch.setattr(image_agent.car_detection, "fetch_image_bytes", AsyncMock(return_value=b"\x89PNG"))
    monkeypatch.setattr(image_agent.car_detection, "detect_cars", AsyncMock(return_value=(boxes, (800, 600))))
    monkeypatch.setattr(image_agent.car_detection, "classify_car", classify_mock)

    with patch("app.agents.image_agent.get_model", return_value=mock_llm_instance):
        result = await image_agent.run_image_agent({"image_url": "https://example.com/two.jpg"})

    assert result.vehicle_count == 2
    assert result.needs_clarification is True
    assert len(result.vehicle_boxes) == 2
    assert result.detected_make is None
    assert result.detected_model is None
    assert len(result.clarification_questions) >= 1
    # Classifier must NOT have been called for multi-car images
    classify_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_hf_detection_failure_falls_back_to_vlm(mock_llm, monkeypatch):
    """HF detect_cars raises → _merge returns VLM-only output."""
    from app.agents import image_agent

    vlm_stub = _mock_image_result(
        vehicle_count=1,
        detected_make="BMW",
        detected_model="3-Series",
        observations=["Blue sedan"],
        confidence=0.75,
    )
    mock_llm_instance = MagicMock()
    _vlm_only_mocks(mock_llm_instance, vlm_stub)

    monkeypatch.setattr(image_agent.car_detection, "is_enabled", lambda: True)
    monkeypatch.setattr(image_agent.car_detection, "fetch_image_bytes", AsyncMock(return_value=b"\x89PNG"))
    monkeypatch.setattr(
        image_agent.car_detection,
        "detect_cars",
        AsyncMock(side_effect=RuntimeError("HF 503 capacity_exhausted")),
    )

    with patch("app.agents.image_agent.get_model", return_value=mock_llm_instance):
        result = await image_agent.run_image_agent({"image_url": "https://example.com/bmw.jpg"})

    # VLM identity preserved when HF fails
    assert result.detected_make == "BMW"
    assert result.detected_model == "3-Series"


def test_brand_model_splitter_handles_hyphenated_and_multi_word_brands():
    """dima806 labels like 'Mercedes-Benz C-Class' split correctly."""
    from app.services.car_detection import _parse_brand_model

    assert _parse_brand_model("Volkswagen Beetle") == ("Volkswagen", "Beetle")
    assert _parse_brand_model("Mercedes-Benz C-Class") == ("Mercedes-Benz", "C-Class")
    assert _parse_brand_model("Aston Martin DB11") == ("Aston Martin", "DB11")
    assert _parse_brand_model("Land Rover Discovery") == ("Land Rover", "Discovery")
    assert _parse_brand_model("Tesla Model 3") == ("Tesla", "Model 3")
    assert _parse_brand_model("Ferrari") == ("Ferrari", "")
