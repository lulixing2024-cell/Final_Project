"""Streamlit UI for the JD Red-Flag Analyzer.

Aesthetic: editorial investigative report — paper-toned background, serif
display type, deep severity colors. Designed to look like a serious due-
diligence audit, not a generic dashboard.

Run:
    streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from core.pipeline import analyze_single  # noqa: E402
from core.schemas import Severity  # noqa: E402


# ============================================================
# Page config + custom CSS
# ============================================================

st.set_page_config(
    page_title="JD Red-Flag Analyzer",
    page_icon="🚩",
    layout="wide",
    initial_sidebar_state="expanded",
)


_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,700;9..144,900&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

:root {
    --paper:    #faf7f0;
    --paper-2:  #f3eedf;
    --ink:      #1a1815;
    --muted:    #6b6357;
    --rule:     #d4cebd;
    --green:    #15803d;
    --green-bg: #f0fdf4;
    --yellow:   #a16207;
    --yellow-bg:#fefce8;
    --red:      #b91c1c;
    --red-bg:   #fef2f2;
    --accent:   #7c2d12;
}

/* Page surface */
.stApp { background: var(--paper); color: var(--ink); font-family: 'IBM Plex Sans', sans-serif; }
[data-testid="stHeader"] { display: none; }
.block-container { padding-top: 2rem; max-width: 1180px; }

/* Headers use the display serif */
h1, h2, h3 { font-family: 'Fraunces', serif !important; color: var(--ink); letter-spacing: -0.02em; }

/* Brand block */
.brand-title {
    font-family: 'Fraunces', serif; font-weight: 900;
    font-size: 3rem; line-height: 1; margin: 0 0 .35rem 0;
    color: var(--ink); letter-spacing: -0.04em;
}
.brand-subtitle {
    font-family: 'IBM Plex Sans', sans-serif; font-weight: 300;
    font-size: 1.05rem; color: var(--muted); margin: 0 0 .25rem 0;
}
.brand-rule { border: 0; border-top: 2px solid var(--ink); margin: 1.25rem 0 1.75rem 0; }
.role-line {
    font-family: 'Fraunces', serif; font-style: italic;
    color: var(--muted); font-size: 1.05rem; margin: 0 0 2rem 0;
    border-left: 3px solid var(--rule); padding-left: 1rem;
}

/* Section eyebrows — small uppercase + rule below */
.eyebrow {
    font-family: 'IBM Plex Sans', sans-serif; text-transform: uppercase;
    letter-spacing: 0.18em; font-size: 0.72rem; font-weight: 600;
    color: var(--muted); margin: 2.5rem 0 .75rem 0;
    border-bottom: 1px solid var(--rule); padding-bottom: .5rem;
}

/* Scorecard */
.scorecard { display: flex; align-items: baseline; gap: 2rem; flex-wrap: wrap; margin: 1rem 0 1.5rem 0; }
.big-score {
    font-family: 'Fraunces', serif; font-weight: 900;
    font-size: 9rem; line-height: 1; letter-spacing: -0.06em;
}
.big-score-suffix {
    font-family: 'IBM Plex Sans', sans-serif; font-weight: 300;
    font-size: 1rem; color: var(--muted); margin-left: .5rem;
}
.score-red    { color: var(--red); }
.score-yellow { color: var(--yellow); }
.score-green  { color: var(--green); }

.metric-row { display: flex; gap: 2rem; flex-wrap: wrap; margin-left: auto; }
.metric { border-left: 2px solid var(--rule); padding-left: 1rem; min-width: 100px; }
.metric-num {
    font-family: 'Fraunces', serif; font-weight: 700;
    font-size: 2.75rem; line-height: 1; margin: 0;
}
.metric-label {
    font-family: 'IBM Plex Sans', sans-serif; text-transform: uppercase;
    letter-spacing: 0.12em; font-size: 0.68rem; color: var(--muted);
    margin-top: .35rem;
}

/* Audit/run-metadata strip */
.audit-row {
    font-family: 'JetBrains Mono', monospace; font-size: 0.72rem;
    color: var(--muted); margin: 1rem 0 0 0;
    padding: .55rem 0; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule);
}
.audit-row .ok  { color: var(--green); font-weight: 700; }
.audit-row .bad { color: var(--red); font-weight: 700; }
.audit-row .sep { color: var(--rule); margin: 0 .65rem; }

/* Company context blocks */
.context-block {
    background: rgba(255,255,255,0.55);
    border-left: 3px solid var(--accent);
    padding: .85rem 1.25rem; margin: .5rem 0;
    font-size: 0.95rem; line-height: 1.55;
}
.context-label {
    font-family: 'IBM Plex Sans', sans-serif; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.12em;
    font-size: 0.7rem; color: var(--accent); margin-bottom: .35rem;
}
.context-empty {
    background: rgba(255,255,255,0.55); border-left: 3px solid var(--rule);
    padding: .85rem 1.25rem; margin: .5rem 0; font-style: italic; color: var(--muted);
}

/* Finding cards */
.finding-card {
    background: rgba(255,255,255,0.55);
    border-left: 4px solid; padding: 1.1rem 1.35rem;
    margin-bottom: 1rem; position: relative;
}
.finding-card.green  { border-color: var(--green); }
.finding-card.yellow { border-color: var(--yellow); }
.finding-card.red    { border-color: var(--red); }
.finding-card.dc {
    box-shadow: 0 0 0 1px var(--red), 0 6px 16px rgba(185,28,28,0.18);
    background: #fff;
}

.finding-header {
    display: flex; align-items: center; gap: .65rem;
    margin-bottom: .6rem; flex-wrap: wrap;
}
.severity-badge {
    font-family: 'JetBrains Mono', monospace; text-transform: uppercase;
    letter-spacing: 0.1em; font-size: 0.68rem; font-weight: 700;
    padding: .22rem .55rem;
}
.severity-badge.green  { background: var(--green-bg);  color: var(--green); }
.severity-badge.yellow { background: var(--yellow-bg); color: var(--yellow); }
.severity-badge.red    { background: var(--red-bg);    color: var(--red); }

.category-name {
    font-family: 'Fraunces', serif; font-weight: 600;
    font-size: 1.15rem; color: var(--ink);
}

.dc-sticker {
    background: var(--red); color: var(--paper);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem; letter-spacing: 0.12em;
    padding: .2rem .55rem; text-transform: uppercase; font-weight: 700;
    margin-left: auto;
}

.evidence-row { margin: .65rem 0; padding-left: .85rem; border-left: 2px solid var(--rule); }
.evidence-label {
    font-family: 'JetBrains Mono', monospace; text-transform: uppercase;
    letter-spacing: 0.1em; font-size: 0.62rem; color: var(--muted);
}
.evidence-quote {
    font-family: 'Fraunces', serif; font-style: italic;
    font-size: 0.95rem; color: var(--ink); line-height: 1.55; margin-top: .2rem;
}

.explanation {
    margin-top: .7rem; font-size: 0.88rem; color: var(--ink);
    line-height: 1.55; opacity: 0.82;
    font-family: 'IBM Plex Sans', sans-serif;
}

/* Sidebar */
[data-testid="stSidebar"] { background: var(--paper-2); border-right: 1px solid var(--rule); }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { font-family: 'Fraunces', serif !important; }
.sidebar-help { font-size: 0.85rem; color: var(--muted); line-height: 1.55; }
.sidebar-tip { font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: var(--muted); }

/* Empty state */
.empty-state { text-align: center; padding: 5rem 2rem 4rem 2rem; color: var(--muted); }
.empty-state-icon { font-size: 4.5rem; margin-bottom: 1rem; opacity: 0.35; }
.empty-state h3 { color: var(--ink); font-weight: 500; }
</style>
"""

st.markdown(_CSS, unsafe_allow_html=True)


# ============================================================
# Helpers
# ============================================================

def _score_color_class(score: float) -> str:
    if score >= 60:
        return "score-red"
    if score >= 30:
        return "score-yellow"
    return "score-green"


def _esc(text: str) -> str:
    """Minimal HTML escaping for quotes injected into markup."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_finding_card(finding) -> str:
    sev = finding.severity.value
    is_dc = finding.is_double_confirmed
    category_name = finding.category.value.replace("_", " ").title()

    dc_sticker = '<span class="dc-sticker">Double-confirmed</span>' if is_dc else ""

    evidence_html = ""
    if finding.jd_evidence:
        evidence_html += (
            '<div class="evidence-row">'
            '<div class="evidence-label">From the job posting</div>'
            f'<div class="evidence-quote">&ldquo;{_esc(finding.jd_evidence)}&rdquo;</div>'
            "</div>"
        )
    if finding.external_evidence:
        evidence_html += (
            '<div class="evidence-row">'
            '<div class="evidence-label">From external research</div>'
            f'<div class="evidence-quote">&ldquo;{_esc(finding.external_evidence)}&rdquo;</div>'
            "</div>"
        )

    dc_class = " dc" if is_dc else ""

    return (
        f'<div class="finding-card {sev}{dc_class}">'
        '<div class="finding-header">'
        f'<span class="severity-badge {sev}">{sev}</span>'
        f'<span class="category-name">{category_name}</span>'
        f"{dc_sticker}"
        "</div>"
        f"{evidence_html}"
        f'<div class="explanation">{_esc(finding.explanation)}</div>'
        "</div>"
    )


# ============================================================
# Sidebar — inputs
# ============================================================

with st.sidebar:
    st.markdown(
        "<h2 style='font-family:Fraunces,serif; margin-top:0; font-size:1.5rem;'>🚩 The Red-Flag Audit</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p class='sidebar-help'>Audit one job posting against eight signal "
        "categories, cross-referenced with public information about the "
        "company.</p>",
        unsafe_allow_html=True,
    )

    company_name = st.text_input(
        "Company name",
        value=st.session_state.get("company_name", ""),
        placeholder="e.g. Anthropic",
    )

    jd_text = st.text_area(
        "Job posting",
        value=st.session_state.get("jd_text", ""),
        height=260,
        placeholder="Paste the full job description here…",
    )

    use_external = st.checkbox(
        "Include company research",
        value=True,
        help=(
            "Searches public sources for layoffs, lawsuits, and employee "
            "reviews. Disable for a JD-only analysis."
        ),
    )

    analyze_clicked = st.button(
        "Run analysis",
        type="primary",
        disabled=not (company_name and jd_text),
        use_container_width=True,
    )

    st.markdown(
        "<p class='sidebar-tip'>Try the sample JD at "
        "<code>data/jds/sample_buzzwordy_startup.txt</code></p>",
        unsafe_allow_html=True,
    )


# ============================================================
# Header
# ============================================================

st.markdown('<h1 class="brand-title">The Red-Flag Audit</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="brand-subtitle">An eight-category investigation of one job '
    "posting, with external corroboration.</p>",
    unsafe_allow_html=True,
)
st.markdown('<hr class="brand-rule" />', unsafe_allow_html=True)


# ============================================================
# Main pane logic
# ============================================================

if analyze_clicked:
    st.session_state["company_name"] = company_name
    st.session_state["jd_text"] = jd_text
    with st.spinner(f"Analyzing posting for {company_name}…"):
        try:
            report = analyze_single(
                jd_text=jd_text,
                company_name=company_name,
                use_external=use_external,
            )
            st.session_state["report"] = report
        except Exception as e:
            st.error(f"Analysis failed: {type(e).__name__}: {e}")
            st.session_state["report"] = None

report = st.session_state.get("report")

if report is None:
    st.markdown(
        '<div class="empty-state">'
        '<div class="empty-state-icon">📰</div>'
        '<h3>Paste a job posting to begin</h3>'
        '<p>Use the sidebar to enter a company name and job description, '
        'then click <em>Run analysis</em>.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.stop()


# ============================================================
# Role line
# ============================================================

st.markdown(
    f'<p class="role-line">{_esc(report.role_summary)}</p>',
    unsafe_allow_html=True,
)


# ============================================================
# Risk Scorecard
# ============================================================

st.markdown('<div class="eyebrow">Risk Scorecard</div>', unsafe_allow_html=True)

score_class = _score_color_class(report.overall_risk_score)
score_str = f"{report.overall_risk_score:g}"

st.markdown(
    f'<div class="scorecard">'
    f'<div>'
    f'<span class="big-score {score_class}">{score_str}</span>'
    f'<span class="big-score-suffix">/100 risk</span>'
    f'</div>'
    f'<div class="metric-row">'
    f'<div class="metric"><div class="metric-num" style="color:var(--red);">{report.red_flag_count}</div>'
    f'<div class="metric-label">Red flags</div></div>'
    f'<div class="metric"><div class="metric-num" style="color:var(--yellow);">{report.yellow_flag_count}</div>'
    f'<div class="metric-label">Yellow flags</div></div>'
    f'<div class="metric"><div class="metric-num" style="color:var(--red);">{report.double_confirmed_red_count}</div>'
    f'<div class="metric-label">Double-confirmed</div></div>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# Audit/metadata strip
faith_class = "ok" if report.evidence_faithful else "bad"
faith_mark = "✓" if report.evidence_faithful else "✗"
faith_text = (
    "all quotes verified against their source"
    if report.evidence_faithful
    else "warning — some quotes failed source verification"
)
st.markdown(
    '<div class="audit-row">'
    f'<span class="{faith_class}">{faith_mark}</span> {faith_text}'
    f'<span class="sep">·</span>Model: {report.metadata.model}'
    f'<span class="sep">·</span>Latency: {report.metadata.latency_ms}\u202fms'
    f'<span class="sep">·</span>Cost: ${report.metadata.cost_usd:.4f}'
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# Query Plan (Phase 3) — show what was searched
# ============================================================

if report.query_plan is not None:
    qp = report.query_plan
    st.markdown('<div class="eyebrow">What We Searched For</div>', unsafe_allow_html=True)

    role_industry_line = (
        f'<p style="font-family:JetBrains Mono,monospace; font-size:0.78rem; '
        f'color:var(--muted); margin: 0 0 .8rem 0;">'
        f'Role inferred: <strong style="color:var(--ink);">{_esc(qp.role_title_inferred)}</strong>'
        f'  ·  Industry: <strong style="color:var(--ink);">{_esc(qp.industry_inferred)}</strong>'
        f'</p>'
    )
    st.markdown(role_industry_line, unsafe_allow_html=True)

    with st.expander(f"View {len(qp.queries)} planned searches", expanded=False):
        for i, q in enumerate(qp.queries, 1):
            purpose_label = q.purpose.value.replace("_", " ").title()
            st.markdown(
                f'<div style="margin-bottom:.85rem;">'
                f'<div style="font-family:JetBrains Mono,monospace; font-size:0.72rem; '
                f'color:var(--accent); text-transform:uppercase; letter-spacing:.12em;">'
                f'{i}. {_esc(purpose_label)}</div>'
                f'<div style="font-family:JetBrains Mono,monospace; font-size:0.95rem; '
                f'color:var(--ink); margin-top:.15rem;">{_esc(q.query)}</div>'
                f'<div style="font-family:IBM Plex Sans,sans-serif; font-size:0.82rem; '
                f'color:var(--muted); font-style:italic; margin-top:.15rem;">{_esc(q.rationale)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ============================================================
# Company Background
# ============================================================

st.markdown('<div class="eyebrow">Company Background</div>', unsafe_allow_html=True)

ctx = report.company_context
if ctx.has_external_signal and ctx.summary:
    sections = [s for s in ctx.summary.split("\n\n") if s.strip()]
    for sec in sections:
        if sec.startswith("[") and "]" in sec:
            label, _, body = sec.partition("]")
            label = label.lstrip("[").strip()
            body = body.lstrip("\n").strip()
            st.markdown(
                '<div class="context-block">'
                f'<div class="context-label">{_esc(label)}</div>'
                f'<div>{_esc(body)}</div>'
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="context-block">{_esc(sec)}</div>',
                unsafe_allow_html=True,
            )
    st.markdown(
        f'<p style="font-family:JetBrains Mono,monospace; font-size:0.7rem; '
        f'color:var(--muted); margin-top:.5rem;">Search latency: {ctx.search_latency_ms}\u202fms</p>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="context-empty">No meaningful external information was '
        "found for this company. Findings rely on the job posting text alone."
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# Findings — sorted by severity, double-confirmed first
# ============================================================

st.markdown('<div class="eyebrow">Findings by Category</div>', unsafe_allow_html=True)

severity_order = {Severity.RED: 0, Severity.YELLOW: 1, Severity.GREEN: 2}
sorted_findings = sorted(
    report.findings,
    key=lambda f: (severity_order[f.severity], not f.is_double_confirmed),
)

for i in range(0, len(sorted_findings), 2):
    cols = st.columns(2, gap="medium")
    for j, finding in enumerate(sorted_findings[i : i + 2]):
        with cols[j]:
            st.markdown(_render_finding_card(finding), unsafe_allow_html=True)
