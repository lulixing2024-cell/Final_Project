"""End-to-end pipeline orchestration (Phase 3).

Flow:
  Step 1: plan_queries(jd_text, company_name)        via Gemini (small call)
          → QueryPlan (3–6 targeted searches)
  Step 2: execute_query_plan(plan, company_name)     via Tavily
          → CompanyContext (may be empty if no signal)
  Step 3: analyze_jd(jd_text, jd_id, company_context) via Gemini (main call)
          → JDAnalysis (8 findings)
  Step 4: validate_all_evidence(findings, jd_text, company_context.summary)
          → bool (anti-hallucination check)
  Step 5: compute_risk_score(analysis, faithful, metadata, company_context)
          → RiskReport (with the QueryPlan attached for transparency)

Cost / latency budget (typical):
  - Planner: ~$0.001, ~3s
  - Tavily 5x: ~$0.003 (free tier), ~10s parallel-able
  - Analyzer: ~$0.0015, ~6s
  - Total: ~$0.0055, ~18-20s end-to-end

Batch mode shares a CompanyResearchCache so identical plans against the same
company hit the cache.
"""

from __future__ import annotations

import hashlib

from core.analyzer import analyze_jd
from core.query_planner import plan_queries, plan_queries_stub
from core.schemas import (
    BatchRiskReport,
    CompanyContext,
    QueryPlan,
    RiskReport,
    RunMetadata,
)
from core.scorer import compute_risk_score
from core.validators import validate_all_evidence


def _hash_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def analyze_single(
    jd_text: str,
    company_name: str,
    jd_id: str | None = None,
    *,
    use_real_llm: bool | None = None,
    use_external: bool = True,
    company_context: CompanyContext | None = None,
    query_plan: QueryPlan | None = None,
) -> RiskReport:
    """Run the full Phase 3 pipeline on one JD.

    Behavior matrix:
      use_real_llm  use_external  Result
      ────────────  ────────────  ──────────────────────────────────────────
      True (real)   True          Full real pipeline: planner + Tavily + analyzer
      True (real)   False         Real analyzer only, no external research
      False (stub)  True          Stub planner (for plan visibility), no Tavily
                                  call, empty context, stub analyzer
      False (stub)  False         Full offline: no planner, empty context, stub
                                  analyzer

    Args:
        jd_text:         the job posting text
        company_name:    user-provided full company name
        jd_id:           optional stable id; defaults to hash of jd_text
        use_real_llm:    override the analyzer/planner real-vs-stub mode
        use_external:    if False, skip Tavily entirely
        company_context: if provided, skip planner+Tavily and use this
        query_plan:      if provided (and company_context is None), skip the
                         planner step and execute this plan instead
    """
    from core.analyzer import USE_REAL_LLM as ANALYZER_DEFAULT

    jd_id = jd_id or _hash_text(jd_text)
    use_real = ANALYZER_DEFAULT if use_real_llm is None else use_real_llm
    do_external_api = use_external and use_real

    planner_metadata: RunMetadata | None = None
    plan: QueryPlan | None = None

    # -------- Step 1: build / receive QueryPlan --------
    if company_context is not None:
        # Caller already produced context (typically batch mode).
        plan = query_plan
    else:
        if query_plan is not None:
            plan = query_plan
        elif do_external_api:
            plan, planner_metadata = plan_queries(jd_text, company_name)
        elif use_external and not use_real:
            # Stub-LLM mode but caller wants to see the plan shape
            plan, planner_metadata = plan_queries_stub(jd_text, company_name)
        # else: no plan (use_external=False)

    # -------- Step 2: execute plan against Tavily, or build empty --------
    if company_context is None:
        if do_external_api and plan is not None:
            from core.company_research import execute_query_plan
            company_context = execute_query_plan(plan, company_name)
        else:
            company_context = CompanyContext.empty(company_name)
            if plan is not None:
                # Carry the planner's inferences into the empty context for
                # UI display, even though no Tavily call was made
                company_context = company_context.model_copy(update={
                    "role_title_inferred": plan.role_title_inferred,
                    "industry_inferred": plan.industry_inferred,
                })

    # -------- Step 3: analyzer (real or stub) --------
    analysis, analyzer_metadata = analyze_jd(
        jd_text, jd_id, company_context, use_real=use_real_llm
    )

    # -------- Step 4: anti-hallucination check --------
    faithful = validate_all_evidence(
        analysis.findings, jd_text, company_context.summary
    )

    # -------- Step 5: combine metadata + score --------
    combined_metadata = analyzer_metadata
    if planner_metadata is not None:
        combined_metadata = analyzer_metadata.model_copy(update={
            "latency_ms": (analyzer_metadata.latency_ms or 0) + (planner_metadata.latency_ms or 0),
            "input_tokens": (analyzer_metadata.input_tokens or 0) + (planner_metadata.input_tokens or 0),
            "output_tokens": (analyzer_metadata.output_tokens or 0) + (planner_metadata.output_tokens or 0),
            "cost_usd": (analyzer_metadata.cost_usd or 0.0) + (planner_metadata.cost_usd or 0.0),
        })

    report = compute_risk_score(analysis, faithful, combined_metadata, company_context)
    return report.model_copy(update={"query_plan": plan})


def analyze_batch(
    jds: list[tuple[str, str, str]],
    *,
    use_real_llm: bool | None = None,
    use_external: bool = True,
) -> BatchRiskReport:
    """Analyze multiple JDs and rank by risk (safest first).

    jds: list of (jd_id, jd_text, company_name) tuples.

    In Phase 3, each JD generates its OWN query plan (different roles at the
    same company benefit from different searches). The cache key includes
    the plan's queries, so identical plans against the same company share a
    research result.
    """
    from core.company_research import CompanyResearchCache

    cache = CompanyResearchCache()

    reports: list[RiskReport] = []
    for jd_id, jd_text, company_name in jds:
        # Build the plan (per-JD), then check cache, then execute
        if use_external:
            if use_real_llm is False:
                plan, _planner_meta = plan_queries_stub(jd_text, company_name)
            else:
                plan, _planner_meta = plan_queries(jd_text, company_name)
            ctx = cache.get_or_execute(plan, company_name)
        else:
            plan = None
            ctx = CompanyContext.empty(company_name)

        report = analyze_single(
            jd_text=jd_text,
            company_name=company_name,
            jd_id=jd_id,
            use_real_llm=use_real_llm,
            use_external=use_external,
            company_context=ctx,
            query_plan=plan,
        )
        reports.append(report)

    ranked = sorted(reports, key=lambda r: r.overall_risk_score)
    return BatchRiskReport(
        reports=reports,
        ranking_safest_to_riskiest=[r.jd_id for r in ranked],
    )
