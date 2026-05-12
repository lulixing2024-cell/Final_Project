"""External research via Tavily — Phase 3.

Given a QueryPlan (from the planner step), executes each SearchQuery against
Tavily and stitches the meaningful answers into a CompanyContext for the
analyzer step. The cache key is now (company_name, normalized_query_set) so
two JDs from the same company that need DIFFERENT queries don't collide.

Tavily free tier: 1000 searches/month → ~200 JDs/month at 5 searches each.
"""

from __future__ import annotations

import os
import time
import threading
from typing import TYPE_CHECKING

from dotenv import load_dotenv

from core.schemas import (
    CompanyContext,
    ExecutedQuery,
    QueryPlan,
    SearchQueryPurpose,
)

if TYPE_CHECKING:
    from tavily import TavilyClient  # noqa: F401

load_dotenv()


# Tavily free tier: cost is zero. Update if you upgrade.
_TAVILY_COST_PER_SEARCH_USD = 0.0

_NO_SIGNAL_PHRASES = (
    "no information",
    "could not find",
    "no relevant",
    "no results",
    "i don't have",
    "unable to find",
    "no specific information",
    "not enough information",
    "i cannot",
)
_MIN_MEANINGFUL_ANSWER_CHARS = 50


# Human-readable section labels for the stitched summary
_PURPOSE_LABELS: dict[SearchQueryPurpose, str] = {
    SearchQueryPurpose.COMPANY_DISTRESS: "Company distress signals",
    SearchQueryPurpose.CULTURE_REPUTATION: "Culture reputation",
    SearchQueryPurpose.LEGAL_ETHICAL: "Legal / ethical signals",
    SearchQueryPurpose.INDUSTRY_HEADWINDS: "Industry & role headwinds",
    SearchQueryPurpose.ROLE_SPECIFIC: "Role-specific signal",
}


def _is_meaningful_answer(answer: str | None) -> bool:
    if not answer:
        return False
    text = answer.strip()
    if len(text) < _MIN_MEANINGFUL_ANSWER_CHARS:
        return False
    lower = text.lower()
    return not any(p in lower for p in _NO_SIGNAL_PHRASES)


def _stitch_summary(executed: list[ExecutedQuery]) -> str | None:
    """Group meaningful answers by purpose, return a labeled summary string.

    If multiple queries share a purpose (e.g., bilingual culture queries),
    their answers are merged under the same section heading.
    """
    by_purpose: dict[SearchQueryPurpose, list[str]] = {}
    for eq in executed:
        if not eq.is_meaningful:
            continue
        by_purpose.setdefault(eq.purpose, []).append(eq.answer.strip())

    if not by_purpose:
        return None

    sections: list[str] = []
    # Preserve a canonical ordering for stable output
    for purpose in [
        SearchQueryPurpose.COMPANY_DISTRESS,
        SearchQueryPurpose.CULTURE_REPUTATION,
        SearchQueryPurpose.LEGAL_ETHICAL,
        SearchQueryPurpose.INDUSTRY_HEADWINDS,
        SearchQueryPurpose.ROLE_SPECIFIC,
    ]:
        answers = by_purpose.get(purpose, [])
        if not answers:
            continue
        label = _PURPOSE_LABELS[purpose]
        body = "\n\n".join(answers)
        sections.append(f"[{label}]\n{body}")

    return "\n\n".join(sections)


def execute_query_plan(
    plan: QueryPlan,
    company_name: str,
    *,
    api_key: str | None = None,
) -> CompanyContext:
    """Run every query in the plan, return a stitched CompanyContext.

    Raises RuntimeError if Tavily SDK or API key is missing — callers should
    check use_external before invoking this.
    """
    api_key = api_key or os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError(
            "TAVILY_API_KEY not set. Add it to .env, or call with "
            "use_external=False to skip company research."
        )

    try:
        from tavily import TavilyClient
    except ImportError as e:
        raise RuntimeError(
            "tavily-python is not installed. Run: pip install tavily-python"
        ) from e

    client = TavilyClient(api_key=api_key)

    t0 = time.time()
    executed: list[ExecutedQuery] = []

    for sq in plan.queries:
        q_t0 = time.time()
        try:
            resp = client.search(
                query=sq.query,
                include_answer=True,
                max_results=3,
                search_depth="basic",
            )
        except Exception as e:
            executed.append(
                ExecutedQuery(
                    query=sq.query,
                    purpose=sq.purpose,
                    answer=f"(search error: {e})",
                    is_meaningful=False,
                    latency_ms=int((time.time() - q_t0) * 1000),
                )
            )
            continue

        answer = (resp or {}).get("answer") or ""
        executed.append(
            ExecutedQuery(
                query=sq.query,
                purpose=sq.purpose,
                answer=answer,
                is_meaningful=_is_meaningful_answer(answer),
                latency_ms=int((time.time() - q_t0) * 1000),
            )
        )

    total_latency_ms = int((time.time() - t0) * 1000)
    summary = _stitch_summary(executed)

    return CompanyContext(
        company_name=company_name,
        role_title_inferred=plan.role_title_inferred,
        industry_inferred=plan.industry_inferred,
        summary=summary,
        executed_queries=executed,
        has_external_signal=summary is not None,
        search_latency_ms=total_latency_ms,
        search_cost_usd=_TAVILY_COST_PER_SEARCH_USD * len(plan.queries),
    )


# ---------- In-process cache ----------

class CompanyResearchCache:
    """Thread-safe cache.

    Cache key in Phase 3 is (company_name_lower, sorted_tuple_of_queries) so
    different plans for the same company don't conflict. Two JDs that happen
    to produce identical plans will share a result.
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[str, tuple[str, ...]], CompanyContext] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(company_name: str, plan: QueryPlan) -> tuple[str, tuple[str, ...]]:
        queries = tuple(sorted(q.query.strip().lower() for q in plan.queries))
        return (company_name.strip().lower(), queries)

    def get(self, company_name: str, plan: QueryPlan) -> CompanyContext | None:
        with self._lock:
            return self._cache.get(self._key(company_name, plan))

    def put(self, company_name: str, plan: QueryPlan, ctx: CompanyContext) -> None:
        with self._lock:
            self._cache[self._key(company_name, plan)] = ctx

    def get_or_execute(
        self,
        plan: QueryPlan,
        company_name: str,
        *,
        api_key: str | None = None,
    ) -> CompanyContext:
        existing = self.get(company_name, plan)
        if existing is not None:
            return existing
        ctx = execute_query_plan(plan, company_name, api_key=api_key)
        self.put(company_name, plan, ctx)
        return ctx
