# The Red Flag Audit

A Streamlit app that audits one job posting against eight kinds of red flags, with verified quotes from the job posting and from public news about the company.

Final project for BU.330.760 Generative AI (Johns Hopkins Carey, Spring 2026).

---

## 1. Context, user, problem

The user is a job seeker considering one specific posting: mid-career switchers and new grads doing pre-application due diligence, deciding whether to apply or whether to accept an offer.

The workflow this improves is pre-application due diligence. Today it is ad hoc. You Google the company, you check Glassdoor, you go with your gut. The process is different for every JD, the signals you find are inconsistent, and there is no way to compare two postings side by side.

It matters because a bad job decision costs months of salary and months of career time. The warning signs are usually present, both in the JD and in public information about the company, but they are invisible without a fixed method.

---

## 2. Solution and design

**What I built.** A Streamlit app. You paste a JD plus a company name. The system returns a risk score from 0 to 100 and one finding per category for eight categories total, with verified quotes as evidence.

**How it works.** Three steps, two Gemini calls.

1. **Plan.** A small Gemini call writes 3 to 6 search queries fitted to this JD's industry, role, and language.
2. **Search.** Tavily executes those queries and stitches the answers into a company-context summary.
3. **Audit.** The main Gemini call evaluates the JD plus the company context against the 8-category taxonomy.

**Three key design choices.**

- **Planner-driven research.** Queries are written per JD, not from a fixed template. A Chinese campus posting and a US startup posting get different searches.
- **External-first taxonomy.** Four categories rely on news and reviews (company distress, culture reputation, legal and ethical flags, industry headwinds). The other four trigger only on explicit problematic phrases in the JD (overwork glorification, scope dumping, hollow promises, buzzword urgency). Absence of content is never a red flag.
- **Verified evidence.** Every quote is substring-checked against its source. If the model invents a quote, the run is rejected. When both the JD and external research support the same finding, it is flagged Double-Confirmed.

---

## 3. Evaluation and results

**Baseline.** Gemini 2.5 Flash with one direct prompt: "here is a JD for company X, should I apply, any red flags?" This is what a user does when they paste a JD into ChatGPT.

**Test cases.** A US buzzwordy startup JD (included as `data/jds/sample_buzzwordy_startup.txt`), a Chinese campus posting from TikTok, and a Chinese-language algorithm engineer JD from Pinduoduo sourced from LinkedIn.

**Rubric.** The 8-category taxonomy above, applied consistently to every test case.

**What I found.** Given the same Pinduoduo JD, the two systems behave very differently. The baseline returns a four-row table with categories like Money, Growth, Freedom, and Health. No sources, no quotes, just a glossy summary. This system returns 3 RED on company risk (2026 layoffs and fines, employee reports of long working hours, active labor lawsuits), 1 YELLOW on industry headwinds, and 4 GREEN on the JD itself. The JD is professional. No overwork phrases, no scope dumping, no hollow promises.

The framework finding: when the JD is professional but the company has real problems, this system separates the two cleanly. The red flags are about the company, not the JD writing. A single-prompt baseline cannot do that.

---

## 4. Artifact snapshot

A working Streamlit app. The full report shows:

- A risk score from 0 to 100, color-coded.
- A "what we searched for" panel listing the planner's queries with rationale.
- A company-background panel with the stitched external research.
- Eight finding cards, color-coded by severity, with verbatim quotes from the JD and from external sources where applicable. Findings backed by both sources show a "Double-Confirmed" badge.

**Worked example for the grader:** paste the contents of `data/jds/sample_buzzwordy_startup.txt` into the JD box and use `Anthropic` as the company name. Expect three or more RED findings, at least one of them Double-Confirmed.

Cost and latency: roughly half a cent and 18 seconds per audit. 33 of 33 offline tests pass.

---

## Setup and usage

Prereqs: Python 3.10+, a Gemini API key, a Tavily API key. Both have free tiers (Tavily allows 1000 searches per month).

```bash
# 1. Install
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env: fill in GEMINI_API_KEY and TAVILY_API_KEY

# 3. Sanity check (optional)
python scripts/sanity_check_gemini.py
python scripts/sanity_check_tavily.py "Anthropic"

# 4. Run offline tests (33 should pass)
pytest tests/

# 5. Launch the app
streamlit run app.py
# Or run from the CLI:
python scripts/run_analysis.py \
    --jd data/jds/sample_buzzwordy_startup.txt \
    --company Anthropic
```

The Streamlit app opens at http://localhost:8501.

---

## Project structure

```
core/        Three-step pipeline: query planner, company research, analyzer, scorer, validators.
prompts/     System prompts and the 8-category taxonomy.
app.py       Streamlit UI.
scripts/     CLI runner and sanity checks.
tests/       33 offline tests.
data/jds/    Sample job postings.
```

Demo video Link:
https://youtu.be/lh4JMX9TfxQ
