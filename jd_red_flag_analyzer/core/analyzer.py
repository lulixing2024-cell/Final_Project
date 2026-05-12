"""The analyzer LLM call: (JD text + CompanyContext) -> JDAnalysis.

This is the SECOND LLM call in the Phase 3 pipeline. The first is the query
planner. Both share the same LLMClient (Gemini Flash by default).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.schemas import (
    CompanyContext,
    JDAnalysis,
    RedFlagCategory,
    RedFlagFinding,
    RunMetadata,
    Severity,
)
from prompts.analyze_jd import SYSTEM_PROMPT, build_user_prompt, PROMPT_VERSION

if TYPE_CHECKING:
    from core.llm_client import LLMClient


# Phase 3 default: real LLM on. Tests pass use_real=False to use the stub.
USE_REAL_LLM = True


def analyze_jd(
    jd_text: str,
    jd_id: str,
    company_context: CompanyContext,
    client: "LLMClient | None" = None,
    use_real: bool | None = None,
) -> tuple[JDAnalysis, RunMetadata]:
    """Analyze one JD against the 8-category taxonomy."""
    use_real_effective = USE_REAL_LLM if use_real is None else use_real

    if not use_real_effective:
        return _stub_analysis(jd_text, jd_id, company_context), RunMetadata(model="stub")

    from core.llm_client import LLMClient

    if client is None:
        client = LLMClient()

    system = SYSTEM_PROMPT
    user = build_user_prompt(jd_id, jd_text, company_context.summary)
    analysis, metadata = client.complete(
        system=system,
        user=user,
        response_schema=JDAnalysis,
        temperature=0.0,
        max_retries=2,
    )
    if analysis.jd_id != jd_id:
        analysis = analysis.model_copy(update={"jd_id": jd_id})
    metadata = metadata.model_copy(update={"prompt_version": PROMPT_VERSION})
    return analysis, metadata


# ----------------------------------------------------------------
# Offline stub — used by tests and the use_real=False code path
# ----------------------------------------------------------------

def _stub_analysis(
    jd_text: str,
    jd_id: str,
    company_context: CompanyContext,
) -> JDAnalysis:
    """Hardcoded fixture for offline development.

    Returns one finding per Phase 3 category. Demonstrates dual-evidence
    findings when company_context has a summary.
    """
    # Find a "scope dumping" phrase in the JD if present
    scope_phrase = None
    for needle in ("wear many hats", "do whatever it takes", "其他相关工作"):
        if needle in jd_text.lower() or needle in jd_text:
            scope_phrase = needle
            break

    # If company context exists, demonstrate external_evidence
    external_quote = None
    if company_context.summary and len(company_context.summary) >= 40:
        external_quote = company_context.summary[:60]

    findings = [
        # --- External-driven ---
        RedFlagFinding(
            category=RedFlagCategory.COMPANY_DISTRESS,
            severity=Severity.GREEN,
            jd_evidence=None,
            external_evidence=None,
            explanation="Stub: no distress signal found in research.",
        ),
        RedFlagFinding(
            category=RedFlagCategory.CULTURE_REPUTATION,
            severity=Severity.YELLOW if external_quote else Severity.GREEN,
            jd_evidence=None,
            external_evidence=external_quote,
            explanation=(
                "Stub: demonstrates external_evidence usage."
                if external_quote
                else "Stub: no culture signal."
            ),
        ),
        RedFlagFinding(
            category=RedFlagCategory.LEGAL_ETHICAL_FLAGS,
            severity=Severity.GREEN,
            jd_evidence=None,
            external_evidence=None,
            explanation="Stub: no legal flags.",
        ),
        RedFlagFinding(
            category=RedFlagCategory.INDUSTRY_ROLE_HEADWINDS,
            severity=Severity.GREEN,
            jd_evidence=None,
            external_evidence=None,
            explanation="Stub: no industry headwinds detected.",
        ),
        # --- JD-internal presence-based ---
        RedFlagFinding(
            category=RedFlagCategory.OVERWORK_GLORIFICATION,
            severity=Severity.GREEN,
            jd_evidence=None,
            external_evidence=None,
            explanation="Stub: no overwork-glorification phrases found.",
        ),
        RedFlagFinding(
            category=RedFlagCategory.SCOPE_DUMPING,
            severity=Severity.YELLOW if scope_phrase else Severity.GREEN,
            jd_evidence=scope_phrase,
            external_evidence=None,
            explanation=(
                f"Stub: scope-dumping phrase '{scope_phrase}' detected."
                if scope_phrase
                else "Stub: no scope-dumping phrases."
            ),
        ),
        RedFlagFinding(
            category=RedFlagCategory.HOLLOW_PROMISES,
            severity=Severity.GREEN,
            jd_evidence=None,
            external_evidence=None,
            explanation="Stub: no hollow superlative promises.",
        ),
        RedFlagFinding(
            category=RedFlagCategory.BUZZWORD_URGENCY,
            severity=Severity.GREEN,
            jd_evidence=None,
            external_evidence=None,
            explanation="Stub: no buzzword + urgency combination.",
        ),
    ]

    return JDAnalysis(
        jd_id=jd_id,
        role_summary="Stub role summary for offline development.",
        findings=findings,
    )
