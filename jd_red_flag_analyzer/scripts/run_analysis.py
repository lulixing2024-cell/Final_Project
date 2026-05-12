"""End-to-end runner for the JD Red-Flag Analyzer.

Usage:
    # Analyze a JD file for a named company (default: include Tavily search)
    python scripts/run_analysis.py --jd data/jds/sample_buzzwordy_startup.txt --company "Acme Inc"

    # Skip Tavily (faster, no API key needed for external search)
    python scripts/run_analysis.py --jd data/jds/sample_buzzwordy_startup.txt --company "Acme Inc" --no-external

    # Pipe a JD from stdin
    cat my_jd.txt | python scripts/run_analysis.py --company "Acme Inc"

    # Save full JSON output
    python scripts/run_analysis.py --jd file.txt --company "Acme" --save-json data/eval_results/out.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pipeline import analyze_single  # noqa: E402
from core.schemas import Severity  # noqa: E402


SEVERITY_ICON = {
    Severity.GREEN: "🟢 GREEN ",
    Severity.YELLOW: "🟡 YELLOW",
    Severity.RED: "🔴 RED   ",
}


def _print_header(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jd", help="Path to a JD text file (if omitted, read from stdin)")
    parser.add_argument("--company", required=True, help="Company name (full, e.g. 'Anthropic')")
    parser.add_argument("--no-external", action="store_true", help="Skip Tavily external research")
    parser.add_argument("--jd-id", default=None, help="Optional stable id for the JD")
    parser.add_argument("--save-json", default=None, help="Optional path to dump the full RiskReport JSON")
    args = parser.parse_args()

    if args.jd:
        jd_text = Path(args.jd).read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            parser.error("provide --jd or pipe JD text via stdin")
        jd_text = sys.stdin.read()

    print(f"Analyzing JD for: {args.company}")
    print(f"External research: {'OFF (--no-external)' if args.no_external else 'ON (Tavily)'}")
    print(f"JD length: {len(jd_text)} chars")

    report = analyze_single(
        jd_text=jd_text,
        company_name=args.company,
        jd_id=args.jd_id,
        use_external=not args.no_external,
    )

    # ---------- Top-level scorecard ----------
    _print_header("RISK SCORECARD")
    print(f"Role:             {report.role_summary}")
    print(f"Overall risk:     {report.overall_risk_score} / 100")
    print(f"Red flags:        {report.red_flag_count}  "
          f"(double-confirmed by external news: {report.double_confirmed_red_count})")
    print(f"Yellow flags:     {report.yellow_flag_count}")
    print(f"Evidence faithful: {'✓ pass' if report.evidence_faithful else '✗ FAIL — some quotes do not appear in source'}")
    print(f"Run:              model={report.metadata.model}  "
          f"latency={report.metadata.latency_ms}ms  cost=${report.metadata.cost_usd:.6f}")

    # ---------- Query plan (Phase 3) ----------
    if report.query_plan is not None:
        _print_header("QUERY PLAN")
        qp = report.query_plan
        print(f"Role inferred:     {qp.role_title_inferred}")
        print(f"Industry inferred: {qp.industry_inferred}")
        print(f"\nQueries ({len(qp.queries)}):")
        for i, q in enumerate(qp.queries, 1):
            print(f"  {i}. [{q.purpose.value}] {q.query}")
            print(f"     → {q.rationale}")

    # ---------- Company context ----------
    _print_header("COMPANY CONTEXT")
    ctx = report.company_context
    if ctx.has_external_signal and ctx.summary:
        print(ctx.summary)
        print(f"\n[search latency: {ctx.search_latency_ms}ms]")
    elif not args.no_external:
        print("(no meaningful external signal found — analysis is based on JD text only)")
    else:
        print("(external research was disabled via --no-external)")

    # ---------- Per-category findings ----------
    _print_header("FINDINGS BY CATEGORY")
    for f in report.findings:
        title = f.category.value.replace("_", " ").title()
        confirm = "  [DOUBLE-CONFIRMED]" if f.is_double_confirmed else ""
        print(f"\n{SEVERITY_ICON[f.severity]}  {title}{confirm}")
        if f.jd_evidence:
            print(f"   JD quote:       \"{f.jd_evidence}\"")
        if f.external_evidence:
            print(f"   External quote: \"{f.external_evidence}\"")
        print(f"   → {f.explanation}")

    # ---------- Optional JSON dump ----------
    if args.save_json:
        out_path = Path(args.save_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nFull JSON written to {out_path}")

    return 0 if report.evidence_faithful else 2


if __name__ == "__main__":
    sys.exit(main())
