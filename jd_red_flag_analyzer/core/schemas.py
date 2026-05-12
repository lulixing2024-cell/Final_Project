"""Pydantic schemas for the JD Red-Flag Analyzer (Phase 3).

Major changes from Phase 2:
  - NEW 8-category taxonomy. Four are EXTERNAL-driven (company / industry /
    role news + reviews); four are JD-INTERNAL but presence-based only —
    they trigger on explicit problematic phrases, not on absence of content.
  - NEW: SearchQuery + QueryPlan. A planner LLM call generates targeted
    searches per JD, instead of using fixed query templates.
  - CompanyContext gains executed_queries so the UI can show what was
    actually searched.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------- Enums ----------

class RedFlagCategory(str, Enum):
    """The 8 fixed dimensions every JD is scored against.

    Four EXTERNAL categories rely primarily on company/industry/role news +
    reviews. Four JD-INTERNAL categories trigger on explicit problematic
    language in the JD itself — NEVER on the absence of "expected" content.
    """

    # ---------- External-signal-driven ----------
    COMPANY_DISTRESS = "company_distress"
    CULTURE_REPUTATION = "culture_reputation"
    LEGAL_ETHICAL_FLAGS = "legal_ethical_flags"
    INDUSTRY_ROLE_HEADWINDS = "industry_role_headwinds"

    # ---------- JD-internal, presence-based ----------
    OVERWORK_GLORIFICATION = "overwork_glorification"
    SCOPE_DUMPING = "scope_dumping"
    HOLLOW_PROMISES = "hollow_promises"
    BUZZWORD_URGENCY = "buzzword_urgency"


# Convenience sets for downstream code that needs to know which is which
EXTERNAL_DRIVEN_CATEGORIES: frozenset[RedFlagCategory] = frozenset({
    RedFlagCategory.COMPANY_DISTRESS,
    RedFlagCategory.CULTURE_REPUTATION,
    RedFlagCategory.LEGAL_ETHICAL_FLAGS,
    RedFlagCategory.INDUSTRY_ROLE_HEADWINDS,
})
JD_INTERNAL_CATEGORIES: frozenset[RedFlagCategory] = frozenset({
    RedFlagCategory.OVERWORK_GLORIFICATION,
    RedFlagCategory.SCOPE_DUMPING,
    RedFlagCategory.HOLLOW_PROMISES,
    RedFlagCategory.BUZZWORD_URGENCY,
})
assert (
    EXTERNAL_DRIVEN_CATEGORIES | JD_INTERNAL_CATEGORIES == set(RedFlagCategory)
    and not (EXTERNAL_DRIVEN_CATEGORIES & JD_INTERNAL_CATEGORIES)
), "External/Internal partition must cover and not overlap"


class Severity(str, Enum):
    GREEN = "green"     # 0 risk points
    YELLOW = "yellow"   # 1 risk point
    RED = "red"         # 2 risk points


SEVERITY_POINTS: dict[Severity, int] = {
    Severity.GREEN: 0,
    Severity.YELLOW: 1,
    Severity.RED: 2,
}

MAX_POINTS_PER_CATEGORY = max(SEVERITY_POINTS.values())  # = 2


# ---------- Query Plan (NEW in Phase 3) ----------

class SearchQueryPurpose(str, Enum):
    """Which red-flag dimension a search targets. Used for routing the
    answer back to the analyzer and for UI grouping."""
    COMPANY_DISTRESS = "company_distress"
    CULTURE_REPUTATION = "culture_reputation"
    LEGAL_ETHICAL = "legal_ethical"
    INDUSTRY_HEADWINDS = "industry_headwinds"
    ROLE_SPECIFIC = "role_specific"


class SearchQuery(BaseModel):
    """One search the planner wants to run.

    The planner generates the actual query string (web-search style,
    4–10 words), tags it with the purpose, and gives a 1-line rationale.
    """
    query: str = Field(..., min_length=4, max_length=200)
    purpose: SearchQueryPurpose
    rationale: str = Field(
        ...,
        description="1-sentence reason this query is worth running for this JD.",
        max_length=300,
    )


class QueryPlan(BaseModel):
    """LLM output of the planner step.

    The planner reads the JD + company name and emits 3–6 targeted searches
    plus brief context fields used downstream by the UI.
    """
    role_title_inferred: str = Field(
        ...,
        description="The role title as the planner read it (e.g. 'Senior Product Manager — Growth').",
    )
    industry_inferred: str = Field(
        ...,
        description="Industry/sector inference (e.g. 'short-video / social media', 'investment banking').",
    )
    queries: list[SearchQuery] = Field(..., min_length=3, max_length=6)

    @field_validator("queries")
    @classmethod
    def _at_least_one_company_distress(cls, v: list[SearchQuery]) -> list[SearchQuery]:
        purposes = {q.purpose for q in v}
        if SearchQueryPurpose.COMPANY_DISTRESS not in purposes:
            raise ValueError(
                "Query plan must include at least one COMPANY_DISTRESS query "
                "(layoffs / restructuring / financial health)."
            )
        return v


# ---------- Company Context ----------

class ExecutedQuery(BaseModel):
    """Audit trail of one query that was actually run."""
    query: str
    purpose: SearchQueryPurpose
    answer: str = ""
    is_meaningful: bool = False
    latency_ms: int = 0


class CompanyContext(BaseModel):
    """External information gathered for the analyzer.

    In Phase 3 this is built from a planner-generated QueryPlan instead of
    fixed query templates. `summary` stitches together the meaningful
    answers; the analyzer's LLM call may quote substrings of `summary` as
    external_evidence.
    """
    company_name: str
    role_title_inferred: Optional[str] = None
    industry_inferred: Optional[str] = None
    summary: Optional[str] = Field(
        None,
        description=(
            "Stitched 1–3 paragraph summary of external findings, grouped "
            "by purpose section. May be quoted by the analyzer."
        ),
    )
    executed_queries: list[ExecutedQuery] = Field(default_factory=list)
    has_external_signal: bool = False
    search_latency_ms: int = 0
    search_cost_usd: float = 0.0

    @classmethod
    def empty(cls, company_name: str) -> "CompanyContext":
        """Used when external research is disabled or returns nothing."""
        return cls(
            company_name=company_name,
            summary=None,
            executed_queries=[],
            has_external_signal=False,
        )


# ---------- LLM analyzer output ----------

class RedFlagFinding(BaseModel):
    """One finding for one of the 8 categories.

    Same evidence-validation contract as Phase 2: non-GREEN severity requires
    at least one of jd_evidence / external_evidence; both filled = double-
    confirmed.

    Phase 3 semantic change: for EXTERNAL-driven categories, the natural
    evidence source is external_evidence (jd_evidence may be null). For
    JD-INTERNAL categories, it's the opposite. The analyzer prompt enforces
    this convention; the schema itself stays evidence-source-agnostic so
    a double-confirmed case (both filled) remains the most valuable signal.
    """
    category: RedFlagCategory
    severity: Severity
    jd_evidence: Optional[str] = Field(
        None,
        description="Verbatim contiguous substring of the JD text.",
    )
    external_evidence: Optional[str] = Field(
        None,
        description="Verbatim contiguous substring of the CompanyContext.summary.",
    )
    explanation: str = Field(
        ..., description="1–2 sentence explanation tying evidence to the criterion"
    )

    @model_validator(mode="after")
    def _evidence_consistency(self):
        # Normalize empty strings to None
        if self.jd_evidence == "":
            object.__setattr__(self, "jd_evidence", None)
        if self.external_evidence == "":
            object.__setattr__(self, "external_evidence", None)

        if self.severity in (Severity.YELLOW, Severity.RED):
            if not self.jd_evidence and not self.external_evidence:
                raise ValueError(
                    f"At least one of jd_evidence or external_evidence is "
                    f"required when severity is '{self.severity.value}'"
                )
        return self

    @property
    def is_double_confirmed(self) -> bool:
        return (
            self.severity != Severity.GREEN
            and bool(self.jd_evidence)
            and bool(self.external_evidence)
        )


class JDAnalysis(BaseModel):
    """LLM output — exactly one finding per category, 8 total."""
    jd_id: str
    role_summary: str = Field(..., description="One-sentence role abstraction")
    findings: list[RedFlagFinding]

    @field_validator("findings")
    @classmethod
    def _validate_complete_taxonomy(cls, v: list[RedFlagFinding]) -> list[RedFlagFinding]:
        if len(v) != len(RedFlagCategory):
            raise ValueError(
                f"Expected {len(RedFlagCategory)} findings (one per category), got {len(v)}"
            )
        present = {f.category for f in v}
        missing = set(RedFlagCategory) - present
        if missing:
            raise ValueError(
                f"Missing findings for categories: {sorted(c.value for c in missing)}"
            )
        if len(present) != len(v):
            raise ValueError("Each category must appear exactly once in findings")
        return v


# ---------- Deterministic scored output ----------

class RunMetadata(BaseModel):
    model: str
    prompt_version: str = "v3"
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class RiskReport(BaseModel):
    """The output of one full pipeline run for one JD."""
    jd_id: str
    role_summary: str
    overall_risk_score: float = Field(..., ge=0, le=100)
    severity_by_category: dict[RedFlagCategory, Severity]
    findings: list[RedFlagFinding]
    red_flag_count: int = Field(..., ge=0)
    yellow_flag_count: int = Field(..., ge=0)
    double_confirmed_red_count: int = Field(
        ...,
        ge=0,
        description="RED findings backed by BOTH JD and external evidence",
    )
    evidence_faithful: bool
    company_context: CompanyContext
    query_plan: Optional[QueryPlan] = None
    metadata: RunMetadata


# ---------- Batch ----------

class BatchRiskReport(BaseModel):
    """The output of analyzing one user's batch of JDs."""
    reports: list[RiskReport]
    ranking_safest_to_riskiest: list[str] = Field(
        ..., description="jd_ids ordered by overall_risk_score ascending"
    )
