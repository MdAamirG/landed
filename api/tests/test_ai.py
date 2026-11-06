"""The AI reader's failure handling, with the Gemini call itself replaced."""

import json

from app import ai
from app.config import settings
from app.schemas import PodReading

GOOD_REPLY = {
    "lr_number": {"value": "48301", "confidence": 0.98},
    "consignee_stamp": {"value": "present", "confidence": 0.97},
    "quantity_received": {"number": 800, "unit": "bags", "confidence": 0.96},
    "remarks": {"text": "", "kind": "none", "confidence": 0.95},
    "delivery_date": {"value": "2026-11-06", "confidence": 0.94},
    "signature": {"value": "present", "confidence": 0.93},
    "image_quality": "ok",
}


def test_a_good_reply_becomes_a_validated_reading(monkeypatch):
    monkeypatch.setattr(ai, "ask_gemini", lambda image, media_type: json.dumps(GOOD_REPLY))

    result = ai.read_pod(b"photo", "image/jpeg")

    assert isinstance(result.reading, PodReading)
    assert result.reading.lr_number.value == "48301"
    assert result.raw == GOOD_REPLY
    assert result.model == settings.gemini_model


def test_a_reply_that_is_not_json_is_a_failure(monkeypatch):
    monkeypatch.setattr(ai, "ask_gemini", lambda image, media_type: "Sorry, I can't help.")

    result = ai.read_pod(b"photo", "image/jpeg")

    assert result.reading is None
    assert result.raw["reply"] == "Sorry, I can't help."


def test_a_reply_that_does_not_fit_the_schema_is_a_failure(monkeypatch):
    bad = GOOD_REPLY | {"lr_number": {"value": "48301", "confidence": 7}}
    monkeypatch.setattr(ai, "ask_gemini", lambda image, media_type: json.dumps(bad))

    assert ai.read_pod(b"photo", "image/jpeg").reading is None


def test_a_call_that_raises_is_a_failure(monkeypatch):
    def boom(image, media_type):
        raise TimeoutError

    monkeypatch.setattr(ai, "ask_gemini", boom)

    result = ai.read_pod(b"photo", "image/jpeg")

    assert result.reading is None
    assert result.raw["error"] == "TimeoutError"


def test_a_reply_past_the_time_limit_is_a_failure(monkeypatch):
    monkeypatch.setattr(ai, "ask_gemini", lambda image, media_type: json.dumps(GOOD_REPLY))
    times = iter([0.0, ai.TIME_LIMIT_SECONDS + 1.0])
    monkeypatch.setattr(ai, "monotonic", lambda: next(times))

    assert ai.read_pod(b"photo", "image/jpeg").reading is None
