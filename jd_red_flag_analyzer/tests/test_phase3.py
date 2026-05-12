"""Phase 3 tests.

Coverage:
  - Schema: new 8-category enum, QueryPlan validation, evidence requirements
  - Taxonomy: completeness, bilingual examples
  - Query planner: stub produces valid plan, real interface contract
  - Research: stitch_summary, _is_meaningful_answer
  - Validators: evidence verification still works
  - Scorer: deterministic scoring
  - Pipeline: end-to-end stub mode
  - Behavior assertions: NO absence-based penalties on minimal JDs;
    explicit-phrase JDs do trigger appropriate categories.
"""

from __future__ import annotations

import pytest

from core.schemas import (
    CompanyContext,
    ExecutedQuery,
    JDAnalysis,
    QueryPlan,
    RedFlagCategory,
    RedFlagFinding,
    RiskReport,
    RunMetadata,
    SearchQuery,
    SearchQueryPurpose,
    Severity,
    EXTERNAL_DRIVEN_CATEGORIES,
    JD_INTERNAL_CATEGORIES,
)
from prompts.red_flag_taxonomy import TAXONOMY, lookup


# =========================================================
# Taxonomy completeness
# =========================================================

class TestTaxonomy:
    def test_exactly_8_categories(self):
        assert len(TAXONOMY) == 8
        assert len(RedFlagCategory) == 8

    def test_every_enum_has_definition(self):
        defined = {cd.category for cd in TAXONOMY}
        assert defined == set(RedFlagCategory)

    def test_external_internal_partition(self):
        assert len(EXTERNAL_DRIVEN_CATEGORIES) == 4
        assert len(JD_INTERNAL_CATEGORIES) == 4
        assert (EXTERNAL_DRIVEN_CATEGORIES & JD_INTERNAL_CATEGORIES) == set()
        assert (EXTERNAL_DRIVEN_CATEGORIES | JD_INTERNAL_CATEGORIES) == set(RedFlagCategory)

    def test_routing_flag_matches_partition(self):
        for cd in TAXONOMY:
            if cd.is_external_driven:
                assert cd.category in EXTERNAL_DRIVEN_CATEGORIES
            else:
                assert cd.category in JD_INTERNAL_CATEGORIES

    def test_jd_internal_categories_have_chinese_examples(self):
        """Each JD-internal category must include Chinese phrase examples
        so the analyzer prompt grounds in zh as well as en."""
        for cat in JD_INTERNAL_CATEGORIES:
            cd = lookup(cat)
            has_zh = any(any(ord(c) > 127 for c in ex) for ex in cd.examples_red)
            assert has_zh, f"{cat.value} has no Chinese example phrases"

    def test_lookup_raises_for_unknown(self):
        with pytest.raises(KeyError):
            lookup("not_a_category")  # type: ignore[arg-type]


# =========================================================
# Schema: SearchQuery & QueryPlan
# =========================================================

class TestSearchQuery:
    def test_valid_query(self):
        q = SearchQuery(
            query="ByteDance layoffs 2026",
            purpose=SearchQueryPurpose.COMPANY_DISTRESS,
            rationale="Surface recent layoffs at ByteDance.",
        )
        assert q.query == "ByteDance layoffs 2026"

    def test_query_too_short_rejected(self):
        with pytest.raises(ValueError):
            SearchQuery(
                query="abc",
                purpose=SearchQueryPurpose.COMPANY_DISTRESS,
                rationale="test",
            )


class TestQueryPlan:
    def _good_query(self, purpose=SearchQueryPurpose.COMPANY_DISTRESS, query="company layoffs 2026"):
        return SearchQuery(query=query, purpose=purpose, rationale="reason here.")

    def test_valid_plan(self):
        plan = QueryPlan(
            role_title_inferred="Data Analyst",
            industry_inferred="social media",
            queries=[
                self._good_query(SearchQueryPurpose.COMPANY_DISTRESS, "TikTok layoffs 2026"),
                self._good_query(SearchQueryPurpose.CULTURE_REPUTATION, "TikTok culture reviews"),
                self._good_query(SearchQueryPurpose.INDUSTRY_HEADWINDS, "short video industry 2026"),
            ],
        )
        assert len(plan.queries) == 3

    def test_plan_must_include_company_distress(self):
        with pytest.raises(ValueError, match="COMPANY_DISTRESS"):
            QueryPlan(
                role_title_inferred="X",
                industry_inferred="Y",
                queries=[
                    self._good_query(SearchQueryPurpose.CULTURE_REPUTATION, "company culture reviews"),
                    self._good_query(SearchQueryPurpose.LEGAL_ETHICAL, "company lawsuit recent"),
                    self._good_query(SearchQueryPurpose.INDUSTRY_HEADWINDS, "industry trends 2026"),
                ],
            )

    def test_min_3_queries(self):
        with pytest.raises(ValueError):
            QueryPlan(
                role_title_inferred="X",
                industry_inferred="Y",
                queries=[self._good_query()],
            )

    def test_max_6_queries(self):
        with pytest.raises(ValueError):
            QueryPlan(
                role_title_inferred="X",
                industry_inferred="Y",
                queries=[self._good_query(query=f"q number {i} layoffs") for i in range(7)],
            )


# =========================================================
# Schema: RedFlagFinding evidence rules
# =========================================================

class TestRedFlagFinding:
    def test_green_with_no_evidence_ok(self):
        f = RedFlagFinding(
            category=RedFlagCategory.OVERWORK_GLORIFICATION,
            severity=Severity.GREEN,
            jd_evidence=None,
            external_evidence=None,
            explanation="No problematic phrases found.",
        )
        assert f.severity == Severity.GREEN
        assert not f.is_double_confirmed

    def test_red_requires_evidence(self):
        with pytest.raises(ValueError, match="At least one of"):
            RedFlagFinding(
                category=RedFlagCategory.COMPANY_DISTRESS,
                severity=Severity.RED,
                jd_evidence=None,
                external_evidence=None,
                explanation="No evidence — should reject.",
            )

    def test_red_with_jd_evidence_only(self):
        f = RedFlagFinding(
            category=RedFlagCategory.OVERWORK_GLORIFICATION,
            severity=Severity.RED,
            jd_evidence="we are a family",
            external_evidence=None,
            explanation="Explicit family framing.",
        )
        assert not f.is_double_confirmed

    def test_double_confirmed(self):
        f = RedFlagFinding(
            category=RedFlagCategory.CULTURE_REPUTATION,
            severity=Severity.RED,
            jd_evidence="we are a family that goes above and beyond",
            external_evidence="widespread reports of burnout",
            explanation="Both sources agree.",
        )
        assert f.is_double_confirmed

    def test_empty_strings_normalized_to_none(self):
        f = RedFlagFinding(
            category=RedFlagCategory.HOLLOW_PROMISES,
            severity=Severity.GREEN,
            jd_evidence="",
            external_evidence="",
            explanation="no signal",
        )
        assert f.jd_evidence is None
        assert f.external_evidence is None


# =========================================================
# Schema: JDAnalysis must have exactly 8 findings
# =========================================================

class TestJDAnalysisCompleteness:
    def _all_8_green_findings(self):
        return [
            RedFlagFinding(
                category=cat,
                severity=Severity.GREEN,
                explanation="ok",
            )
            for cat in RedFlagCategory
        ]

    def test_8_findings_one_per_category(self):
        a = JDAnalysis(
            jd_id="x",
            role_summary="A role.",
            findings=self._all_8_green_findings(),
        )
        assert len(a.findings) == 8

    def test_missing_category_rejected(self):
        findings = self._all_8_green_findings()[:7]
        with pytest.raises(ValueError, match="Expected 8 findings"):
            JDAnalysis(jd_id="x", role_summary="x", findings=findings)

    def test_duplicate_category_rejected(self):
        findings = self._all_8_green_findings()
        findings[0] = findings[1].model_copy()  # now two of category[1]
        with pytest.raises(ValueError):
            JDAnalysis(jd_id="x", role_summary="x", findings=findings)


# =========================================================
# Query planner stub
# =========================================================

class TestQueryPlannerStub:
    def test_stub_returns_valid_plan(self):
        from core.query_planner import plan_queries_stub

        plan, meta = plan_queries_stub("any jd text", "Acme Corp")
        assert isinstance(plan, QueryPlan)
        assert "Acme Corp" in plan.queries[0].query
        # Must satisfy the at-least-one-company-distress rule
        assert any(q.purpose == SearchQueryPurpose.COMPANY_DISTRESS for q in plan.queries)
        # Metadata records the planner prompt version
        assert "plan" in meta.prompt_version


# =========================================================
# Company research stitching
# =========================================================

class TestCompanyResearchStitching:
    def test_is_meaningful_filters_out_short_and_negative(self):
        from core.company_research import _is_meaningful_answer

        assert _is_meaningful_answer("a" * 200) is True
        assert _is_meaningful_answer("") is False
        assert _is_meaningful_answer("short") is False
        assert _is_meaningful_answer(None) is False
        # Negative phrase even at long length
        assert _is_meaningful_answer(
            "I don't have enough information to answer this question fully."
        ) is False

    def test_stitch_groups_by_purpose(self):
        from core.company_research import _stitch_summary

        executed = [
            ExecutedQuery(
                query="q1",
                purpose=SearchQueryPurpose.COMPANY_DISTRESS,
                answer="A" * 80,
                is_meaningful=True,
            ),
            ExecutedQuery(
                query="q2",
                purpose=SearchQueryPurpose.CULTURE_REPUTATION,
                answer="B" * 80,
                is_meaningful=True,
            ),
            ExecutedQuery(
                query="q3",
                purpose=SearchQueryPurpose.COMPANY_DISTRESS,
                answer="C" * 80,
                is_meaningful=True,
            ),
        ]
        summary = _stitch_summary(executed)
        assert summary is not None
        # Distress section appears once with both answers merged
        assert summary.count("[Company distress signals]") == 1
        assert "[Culture reputation]" in summary
        assert "A" * 80 in summary
        assert "C" * 80 in summary

    def test_stitch_returns_none_when_nothing_meaningful(self):
        from core.company_research import _stitch_summary

        executed = [
            ExecutedQuery(
                query="q",
                purpose=SearchQueryPurpose.COMPANY_DISTRESS,
                answer="too short",
                is_meaningful=False,
            ),
        ]
        assert _stitch_summary(executed) is None


# =========================================================
# Validators (still work with Phase 3 findings)
# =========================================================

class TestValidators:
    def test_jd_evidence_substring_accepted(self):
        from core.validators import validate_evidence

        jd = "We are a family that goes above and beyond."
        f = RedFlagFinding(
            category=RedFlagCategory.OVERWORK_GLORIFICATION,
            severity=Severity.RED,
            jd_evidence="we are a family",  # case-insensitive
            explanation="x",
        )
        assert validate_evidence(f, jd_text=jd, company_context_summary=None) is True

    def test_jd_evidence_invented_rejected(self):
        from core.validators import validate_evidence

        f = RedFlagFinding(
            category=RedFlagCategory.OVERWORK_GLORIFICATION,
            severity=Severity.RED,
            jd_evidence="phrase that is not in the source",
            explanation="x",
        )
        assert validate_evidence(f, jd_text="something else", company_context_summary=None) is False

    def test_external_evidence_substring_accepted(self):
        from core.validators import validate_evidence

        ctx = "Company has faced multiple lawsuits this year over labor issues."
        f = RedFlagFinding(
            category=RedFlagCategory.LEGAL_ETHICAL_FLAGS,
            severity=Severity.RED,
            external_evidence="multiple lawsuits",
            explanation="x",
        )
        assert validate_evidence(f, jd_text="", company_context_summary=ctx) is True


# =========================================================
# Scorer
# =========================================================

class TestScorer:
    def _make_analysis(self, severities: dict[RedFlagCategory, Severity]) -> JDAnalysis:
        findings = []
        for cat in RedFlagCategory:
            sev = severities.get(cat, Severity.GREEN)
            findings.append(RedFlagFinding(
                category=cat,
                severity=sev,
                jd_evidence="placeholder" if sev != Severity.GREEN else None,
                explanation="x",
            ))
        return JDAnalysis(jd_id="x", role_summary="r", findings=findings)

    def test_all_green_is_zero(self):
        from core.scorer import compute_risk_score

        analysis = self._make_analysis({})
        ctx = CompanyContext.empty("X")
        report = compute_risk_score(analysis, True, RunMetadata(model="stub"), ctx)
        assert report.overall_risk_score == 0.0
        assert report.red_flag_count == 0
        assert report.yellow_flag_count == 0

    def test_all_red_is_one_hundred(self):
        from core.scorer import compute_risk_score

        analysis = self._make_analysis({c: Severity.RED for c in RedFlagCategory})
        ctx = CompanyContext.empty("X")
        report = compute_risk_score(analysis, True, RunMetadata(model="stub"), ctx)
        assert report.overall_risk_score == 100.0
        assert report.red_flag_count == 8

    def test_score_proportional(self):
        from core.scorer import compute_risk_score

        # 4 RED + 4 GREEN = 8/16 = 50%
        sevs = {c: Severity.RED for c in list(RedFlagCategory)[:4]}
        analysis = self._make_analysis(sevs)
        ctx = CompanyContext.empty("X")
        report = compute_risk_score(analysis, True, RunMetadata(model="stub"), ctx)
        assert report.overall_risk_score == 50.0


# =========================================================
# Pipeline end-to-end (stub mode)
# =========================================================

class TestPipelineStub:
    def test_pipeline_offline(self):
        from core.pipeline import analyze_single

        jd = "Senior PM. Wear many hats. Build from scratch where needed."
        report = analyze_single(
            jd, "TestCo", use_real_llm=False, use_external=False
        )
        assert isinstance(report, RiskReport)
        assert len(report.findings) == 8
        # Stub should pick up "wear many hats" as scope dumping
        scope = next(f for f in report.findings
                     if f.category == RedFlagCategory.SCOPE_DUMPING)
        assert scope.severity == Severity.YELLOW

    def test_pipeline_with_plan_stub(self):
        """When use_real_llm=False but use_external=True, planner stub runs
        and plan is attached to the report (for UI dev)."""
        from core.pipeline import analyze_single

        report = analyze_single(
            "Some JD content", "TestCo",
            use_real_llm=False, use_external=True,
        )
        assert report.query_plan is not None
        assert len(report.query_plan.queries) >= 3

    def test_minimal_chinese_jd_no_absence_red_flags(self):
        """KEY ASSERTION for Phase 3: a clean minimal Chinese campus JD that
        omits salary, career path, team size etc. must NOT produce any
        non-GREEN finding in JD-internal categories from absence alone.

        Only relies on stub analyzer which is presence-based by construction;
        but this test guards against future regression in the stub."""
        from core.pipeline import analyze_single

        jd = (
            "数据分析师，2026 届校招。"
            "职责：1、参与用户增长指标体系建设；2、支持业务日常分析需要。"
            "要求：1、本科及以上学历；2、熟练使用 SQL/Python。"
        )
        report = analyze_single(
            jd, "TestCo", use_real_llm=False, use_external=False
        )
        # All 4 JD-internal categories must be GREEN (no problematic phrases)
        for cat in JD_INTERNAL_CATEGORIES:
            finding = next(f for f in report.findings if f.category == cat)
            assert finding.severity == Severity.GREEN, (
                f"{cat.value} should be GREEN for a clean Chinese campus JD"
                f" — got {finding.severity.value}"
            )
