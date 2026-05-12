"""Deterministic validators (Phase 2). No LLM calls.

Validates that every quoted evidence string is actually present in its
declared source:
  - jd_evidence       must be a substring of the JD text
  - external_evidence must be a substring of the CompanyContext.summary

If a finding has no external_evidence, the company_context_summary is
ignored for that finding. If a finding has external_evidence but the
context summary is None or empty, the finding fails validation.
"""

import re

from core.schemas import RedFlagFinding, Severity


def _normalize(text: str) -> str:
    """Lowercase + collapse whitespace + strip line-leading bullet markers.

    Bullet stripping handles the case where the model quotes a section
    header together with its first bullet (e.g. "Required: 7+ years ...")
    while the JD actually formats it as:
        Required:
        - 7+ years ...
    The bullet "- " is removed at line starts so the two normalize equal.
    """
    # Strip line-leading bullet markers: "- ", "* ", "• " (also at start of string)
    text = re.sub(r"(?:^|\n)\s*[-•*]\s+", "\n", text)
    # Collapse all whitespace to single spaces
    text = re.sub(r"\s+", " ", text)
    return text.lower().strip()


def _is_substring(quote: str, source: str) -> bool:
    """True if `quote` appears in `source` (case- and whitespace-insensitive).

    Ellipsis handling: if `quote` contains '...' (academic-style elision
    marking skipped text between two segments that ARE in the source),
    we split on the ellipsis and require EACH non-empty segment to appear
    as a substring of `source`. This accommodates legitimate multi-phrase
    quoting (e.g., "fast-paced ... rocketship ... URGENT") where the
    pattern of multiple phrases is itself the signal.
    """
    if "..." in quote:
        segments = [s.strip() for s in quote.split("...") if s.strip()]
        if not segments:
            return False
        normalized_source = _normalize(source)
        return all(_normalize(seg) in normalized_source for seg in segments)
    return _normalize(quote) in _normalize(source)


def validate_evidence(
    finding: RedFlagFinding,
    jd_text: str,
    company_context_summary: str | None = None,
) -> bool:
    """Check that every quoted evidence string appears in its source.

    Rules:
      - If jd_evidence is set: it must appear in jd_text.
      - If external_evidence is set: company_context_summary must be
        non-empty AND the quote must appear in it.
      - For YELLOW/RED severity: at least one evidence field must be set.
        (This is also enforced by the Pydantic model_validator at parse time,
        so re-checking here is belt-and-suspenders.)
    """
    # jd_evidence substring check
    if finding.jd_evidence:
        if not _is_substring(finding.jd_evidence, jd_text):
            return False

    # external_evidence substring check
    if finding.external_evidence:
        if not company_context_summary:
            # Claimed an external quote but there's no context to quote from
            return False
        if not _is_substring(finding.external_evidence, company_context_summary):
            return False

    # Severity-evidence consistency (already enforced by model_validator;
    # kept here as a defensive guard against future schema drift)
    if finding.severity in (Severity.YELLOW, Severity.RED):
        if not finding.jd_evidence and not finding.external_evidence:
            return False

    return True


def validate_all_evidence(
    findings: list[RedFlagFinding],
    jd_text: str,
    company_context_summary: str | None = None,
) -> bool:
    return all(
        validate_evidence(f, jd_text, company_context_summary) for f in findings
    )


def faithfulness_report(
    findings: list[RedFlagFinding],
    jd_text: str,
    company_context_summary: str | None = None,
) -> dict[str, bool]:
    """Per-finding faithfulness map keyed by category value, for UI display."""
    return {
        f.category.value: validate_evidence(f, jd_text, company_context_summary)
        for f in findings
    }
