"""The AI reader: image bytes in, a validated reading or a failure out.

Everything about Gemini stays in this file. Tests replace read_pod() with a fake, because the rest
of the app only needs to know that a reading came back or that it didn't.
"""

import json
import logging
from dataclasses import dataclass
from time import monotonic
from typing import Any

from google import genai
from google.genai import types

from app.config import settings
from app.schemas import PodReading

logger = logging.getLogger(__name__)

TIME_LIMIT_SECONDS = 20  # Fixed by rule 1 of the decision rule.

PROMPT = """This is a photo of a signed Indian lorry receipt, taken at the consignee's gate.
Read what is on the paper. Never guess: if you can't find or read something, say so.

- lr_number: the LR (lorry receipt) number printed on the sheet.
- consignee_stamp: "present" only if a consignee's rubber stamp is on the sheet.
- quantity_received: the quantity the consignee wrote as received, with its unit. If the only
  quantity on the sheet is the printed dispatch quantity, give null for the number and unit.
- remarks: anything the consignee wrote about the delivery. Set kind to shortage, damage or other.
  If there is no remark, give an empty text and kind none. Treat "nil", "ok" and a dash as no
  remark only if the consignee's remarks box holds nothing else.
- delivery_date: the date the consignee wrote when receiving the goods, not the LR's printed date.
- signature: "present" only if the consignee's signature is on the sheet.
- image_quality: "blurred" or "dark" only if that stops you reading the sheet, otherwise "ok".

Give each field a confidence from 0 to 1 for how sure you are of what you read."""


@dataclass(frozen=True)
class AiResult:
    reading: PodReading | None  # None means failed, timed out or a reply that didn't fit.
    raw: dict[str, Any]  # The reply as sent, or what went wrong. Kept on the attempt.
    model: str
    latency_ms: int


def ask_gemini(image: bytes, media_type: str) -> str:
    """The one call into the SDK. Returns the model's JSON reply as text."""
    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=TIME_LIMIT_SECONDS * 1000),
    )
    # No temperature, top_p or top_k, and thinking stays at its default: Google's notes for this
    # model family say to leave them alone.
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=[types.Part.from_bytes(data=image, mime_type=media_type), PROMPT],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=PodReading.model_json_schema(),
        ),
    )
    return response.text or ""


def read_pod(image: bytes, media_type: str) -> AiResult:
    """Never raises. Any failure at all is the same answer: a person looks at this photo."""
    started = monotonic()
    reply = None
    reading = None
    try:
        reply = ask_gemini(image, media_type)
        # Validated again here, because structured output shapes a reply but doesn't guarantee it.
        reading = PodReading.model_validate_json(reply)
        raw = json.loads(reply)
    except Exception as error:  # Network, quota, safety block, bad JSON: all rule 1.
        logger.warning("AI check failed: %s", type(error).__name__)
        raw = {"error": type(error).__name__, "reply": reply}

    latency_ms = round((monotonic() - started) * 1000)
    # The HTTP timeout only limits gaps between bytes, so a slow reply can still run over.
    if reading is not None and latency_ms > TIME_LIMIT_SECONDS * 1000:
        reading = None
        raw = {"error": "over the time limit", "reply": reply}

    return AiResult(reading, raw, settings.gemini_model, latency_ms)
