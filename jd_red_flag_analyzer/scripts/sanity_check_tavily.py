"""Sanity check for Tavily setup.

Run this once after adding TAVILY_API_KEY to .env. It makes ONE live
search call to confirm:
  1. The API key is loaded
  2. The tavily-python SDK is installed
  3. The free tier is responding

Usage:
    python scripts/sanity_check_tavily.py [COMPANY_NAME]

Example:
    python scripts/sanity_check_tavily.py "Anthropic"

If no company is provided, uses 'Anthropic' as the test query.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    company = sys.argv[1] if len(sys.argv) > 1 else "Anthropic"

    print(f"Running Tavily sanity check for: {company}\n")

    try:
        from core.company_research import fetch_company_context
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return 1

    try:
        ctx = fetch_company_context(company)
    except RuntimeError as e:
        print(f"✗ {e}")
        return 1
    except Exception as e:
        print(f"✗ Search failed: {type(e).__name__}: {e}")
        return 1

    print(f"✓ Tavily call succeeded "
          f"(latency={ctx.search_latency_ms}ms, "
          f"signal_found={ctx.has_external_signal})")
    print()
    print("RAW ANSWERS:")
    print("=" * 60)
    for query_name, answer in ctx.raw_search_answers.items():
        print(f"\n[{query_name}]")
        print(answer[:300] + ("..." if len(answer) > 300 else ""))
    print()
    print("STITCHED SUMMARY:")
    print("=" * 60)
    if ctx.summary:
        print(ctx.summary)
    else:
        print("(no meaningful signal — pipeline will fall back to JD-only analysis)")

    print("\nReady for Phase 2 end-to-end run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
