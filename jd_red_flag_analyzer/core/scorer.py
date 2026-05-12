"""Deterministic risk scoring (Phase 2). No LLM calls.

Same weighted-sum logic as Phase 1, plus:
  - Counts of YELLOW, RED, and DOUBLE-CONFIRMED RED findings.
  - Carries the CompanyContext through into the RiskReport so the UI can
    display the external information that informed the analysis.
"""

from core.schemas import (
    CompanyContext,
    JDAnalysis,
    MAX_POINTS_PER_CATEGORY,
    RedFlagCategory,
    RiskReport,
    RunMetadata,
    Severity,
    SEVERITY_POINTS,
)


def compute_risk_score(
    analysis: JDAnalysis,
    evidence_faithful: bool,
    metadata: RunMetadata,
    company_context: CompanyContext,
) -> RiskReport:
    """Convert a validated JDAnalysis into a RiskReport with a 0-100 score.

    Higher score = more risk. Maximum is when every category is RED
    (8 × 2 / 16 × 100 = 100).
    """
    findings = analysis.findings

    total_points = sum(SEVERITY_POINTS[f.severity] for f in findings)
    max_total = len(RedFlagCategory) * MAX_POINTS_PER_CATEGORY  # 8 × 2 = 16
    risk_score = round(100 * total_points / max_total, 1) if max_total else 0.0

    severity_by_category: dict[RedFlagCategory, Severity] = {
        f.category: f.severity for f in findings
    }

    red_count = sum(1 for f in findings if f.severity == Severity.RED)
    yellow_count = sum(1 for f in findings if f.severity == Severity.YELLOW)
    double_confirmed_red = sum(
        1 for f in findings
        if f.severity == Severity.RED and f.is_double_confirmed
    )

    return RiskReport(
        jd_id=analysis.jd_id,
        role_summary=analysis.role_summary,
        overall_risk_score=risk_score,
        severity_by_category=severity_by_category,
        findings=findings,
        red_flag_count=red_count,
        yellow_flag_count=yellow_count,
        double_confirmed_red_count=double_confirmed_red,
        evidence_faithful=evidence_faithful,
        company_context=company_context,
        metadata=metadata,
    )
