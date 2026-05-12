"""Gemini LLM client with structured-output enforcement.

Uses the current `google-genai` SDK (not the deprecated `google-generativeai`).
Default model is gemini-2.5-flash — the workhorse model for structured-output
production workloads.

Why we retry on Pydantic validation failure:
  - Gemini's response_schema enforcement isn't always perfect. Occasionally
    it emits subtly invalid JSON (missing required field, enum value
    mismatch, etc.). One retry with the validation error fed back to the
    model fixes most of these without paying for many calls.
"""

from __future__ import annotations

import os
import time
from typing import Type, TypeVar

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from core.schemas import RunMetadata

T = TypeVar("T", bound=BaseModel)

load_dotenv()

# Approx USD per 1M tokens. Update from https://ai.google.dev/pricing when
# Google changes pricing — these numbers affect the cost shown in
# RunMetadata only, never the actual API charge.
_COST_PER_1M_INPUT: dict[str, float] = {
    "gemini-2.5-flash": 0.30,
    "gemini-2.5-flash-lite": 0.10,
    "gemini-2.5-pro": 1.25,
    "gemini-3-pro-preview": 2.00,
    "gemini-3.1-flash-preview": 0.30,
}
_COST_PER_1M_OUTPUT: dict[str, float] = {
    "gemini-2.5-flash": 2.50,
    "gemini-2.5-flash-lite": 0.40,
    "gemini-2.5-pro": 10.00,
    "gemini-3-pro-preview": 12.00,
    "gemini-3.1-flash-preview": 2.50,
}

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


class LLMClient:
    """Wraps google-genai with our schema enforcement + retry + cost tracking."""

    def __init__(self, model: str | None = None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Copy .env.example to .env and add your key."
            )
        self.model_name = model or DEFAULT_MODEL
        self._client = genai.Client(api_key=api_key)
        self.total_cost_usd: float = 0.0
        self.total_calls: int = 0

    def complete(
        self,
        system: str,
        user: str,
        response_schema: Type[T],
        temperature: float = 0.0,
        max_retries: int = 2,
    ) -> tuple[T, RunMetadata]:
        """Send a prompt to Gemini and return a validated Pydantic instance.

        On Pydantic validation failure, retries once with the error message
        appended to the user prompt. After max_retries+1 attempts the final
        ValidationError is raised.
        """
        contents = user
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            config = types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=temperature,
            )

            t0 = time.time()
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config,
            )
            latency_ms = int((time.time() - t0) * 1000)

            try:
                # Validate response.text against the Pydantic schema. We use
                # explicit model_validate_json (rather than response.parsed)
                # so that retry-on-failure remains consistent across SDK
                # versions.
                parsed = response_schema.model_validate_json(response.text)
                metadata = self._build_metadata(response, latency_ms)
                self.total_cost_usd += metadata.cost_usd
                self.total_calls += 1
                return parsed, metadata

            except ValidationError as e:
                last_error = e
                if attempt < max_retries:
                    contents = (
                        f"{user}\n\n---\n\n"
                        f"Your previous response failed schema validation "
                        f"with this error:\n{e}\n\n"
                        f"Please correct the JSON and return only the valid object."
                    )
                    continue
                raise

        # Pleases the type checker; unreachable
        raise last_error  # type: ignore[misc]

    def _build_metadata(self, response, latency_ms: int) -> RunMetadata:
        usage = getattr(response, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", 0) if usage else 0
        out_tok = getattr(usage, "candidates_token_count", 0) if usage else 0

        in_rate = _COST_PER_1M_INPUT.get(self.model_name, 0.30)
        out_rate = _COST_PER_1M_OUTPUT.get(self.model_name, 2.50)
        cost = (in_tok * in_rate + out_tok * out_rate) / 1_000_000

        return RunMetadata(
            model=self.model_name,
            latency_ms=latency_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=round(cost, 6),
        )
