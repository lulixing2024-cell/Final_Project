"""Sanity check for Gemini setup.

Run this once after installing dependencies and adding your API key to .env.
It makes ONE live call to Gemini against a tiny structured-output schema
to confirm:
  1. The API key is loaded
  2. The SDK version supports response_schema with Pydantic
  3. The model name is valid for your API tier

Usage:
    python scripts/sanity_check_gemini.py

Expected output:
    ✓ API key loaded
    ✓ Gemini call succeeded (model=..., latency=...ms, cost=$...)
    ✓ Response parsed against Pydantic schema:
        {response printed here}
"""

import sys
from pathlib import Path

# Make `core` importable when running from project root or scripts/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pydantic import BaseModel  # noqa: E402

from core.llm_client import LLMClient  # noqa: E402


class _SanityResponse(BaseModel):
    """Tiny schema just to verify structured output works."""
    sentiment: str  # "positive" | "negative" | "neutral"
    confidence: float
    rationale: str


def main() -> int:
    print("Running Gemini sanity check...\n")

    try:
        client = LLMClient()
    except RuntimeError as e:
        print(f"✗ {e}")
        return 1
    print(f"✓ API key loaded (model={client.model_name})")

    try:
        result, meta = client.complete(
            system="You classify text sentiment. Return JSON only.",
            user="Classify this text: 'I love the new coffee shop on Main Street.'",
            response_schema=_SanityResponse,
        )
    except Exception as e:
        print(f"✗ Gemini call failed: {type(e).__name__}: {e}")
        return 1

    print(
        f"✓ Gemini call succeeded "
        f"(latency={meta.latency_ms}ms, "
        f"in_tokens={meta.input_tokens}, "
        f"out_tokens={meta.output_tokens}, "
        f"cost=${meta.cost_usd:.6f})"
    )
    print("✓ Response parsed against Pydantic schema:")
    print(f"    sentiment   = {result.sentiment}")
    print(f"    confidence  = {result.confidence}")
    print(f"    rationale   = {result.rationale}")
    print("\nAll good. Ready for Phase 2.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
