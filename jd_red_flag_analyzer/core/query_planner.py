"""Query planner — Phase 3, Step 1 of the pipeline.

Reads a JD + company name, calls Gemini with the planner prompt, returns a
validated QueryPlan with 3–6 targeted search queries.

Cost / latency:
  - 1 small Gemini call, low input tokens (just the JD + company name).
  - Output is small JSON (a handful of short queries).
  - Typical: ~$0.0008 / ~2-3s.
"""

from __future__ import annotations

from core.llm_client import LLMClient
from core.schemas import QueryPlan, RunMetadata
from prompts.plan_queries import (
    PLANNER_PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)


def plan_queries(
    jd_text: str,
    company_name: str,
    *,
    client: LLMClient | None = None,
) -> tuple[QueryPlan, RunMetadata]:
    """Generate a QueryPlan for one JD via Gemini.

    Args:
        jd_text:      the full JD text
        company_name: the user-supplied company name
        client:       optional pre-built LLMClient (otherwise a default one
                      is constructed using env GEMINI_API_KEY)

    Returns:
        (plan, metadata) where plan is a validated QueryPlan and metadata
        records cost / latency / token usage for that planner call.
    """
    client = client or LLMClient()
    plan, metadata = client.complete(
        system=SYSTEM_PROMPT,
        user=build_user_prompt(company_name=company_name, jd_text=jd_text),
        response_schema=QueryPlan,
        temperature=0.0,
        max_retries=2,
    )
    metadata.prompt_version = PLANNER_PROMPT_VERSION
    return plan, metadata


# ---------------------------------------------------------------
# Offline stub (used by tests and the USE_REAL_LLM=False code path)
# ---------------------------------------------------------------

def plan_queries_stub(
    jd_text: str,
    company_name: str,
) -> tuple[QueryPlan, RunMetadata]:
    """Deterministic stub that returns a generic 4-query plan.

    Used by tests and the offline fixture path so the pipeline can be
    exercised end-to-end without hitting the API.
    """
    from core.schemas import SearchQuery, SearchQueryPurpose

    plan = QueryPlan(
        role_title_inferred="Unknown Role",
        industry_inferred="general",
        queries=[
            SearchQuery(
                query=f"{company_name} layoffs restructuring 2026",
                purpose=SearchQueryPurpose.COMPANY_DISTRESS,
                rationale="Surface any recent organizational distress signals.",
            ),
            SearchQuery(
                query=f"{company_name} employee reviews work culture",
                purpose=SearchQueryPurpose.CULTURE_REPUTATION,
                rationale="Public review signals on culture and work-life.",
            ),
            SearchQuery(
                query=f"{company_name} lawsuit regulation settlement",
                purpose=SearchQueryPurpose.LEGAL_ETHICAL,
                rationale="Recent legal or regulatory issues.",
            ),
            SearchQuery(
                query="industry trends challenges 2026",
                purpose=SearchQueryPurpose.INDUSTRY_HEADWINDS,
                rationale="Broader industry-level pressure check (stub).",
            ),
        ],
    )
    metadata = RunMetadata(
        model="stub-planner",
        prompt_version=PLANNER_PROMPT_VERSION,
        latency_ms=0,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
    )
    return plan, metadata
