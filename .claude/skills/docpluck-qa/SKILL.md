---
name: docpluck-qa
description: Comprehensive QA engineer for Docpluck App (PDF + DOCX + HTML extraction SaaS). Runs 500+ Python tests (library + service), ESCIcheck 10-PDF AI verification (library + local webapp + production), normalization spot-check, section-identification smoke, batch extraction, service health, DB, admin API, and deployment checks. When asked for a "DOCX benchmark" or "format parity benchmark" or "--benchmark-docx" or similar, runs the special cross-format benchmark suite (CitationGuard DOCX corpus + DOCX→PDF + PDF→DOCX). Use /docpluck-qa whenever testing, after changes, or before deployment.
tags: [python, nextjs, pdf, docx, fastapi, drizzle, neon, qa]
---

# Docpluck QA

## [MANDATORY FIRST ACTION] preflight (do NOT skip, even if orchestrated by /ship)

**Your very first action in this skill, BEFORE reading anything else, is:**

1. Run: `bash ~/.claude/skills/_shared/bin/preflight-filter.sh <this-skill-name>` and print its `🔧 skill-optimize pre-check · ...` heartbeat as your first visible output line.
2. Initialize `~/.claude/skills/_shared/run-meta/<this-skill-name>.json` per `~/.claude/skills/_shared/preflight.md` step 6 (include `phase_start_sha` from `git rev-parse HEAD`).
3. Load `~/.claude/skills/_shared/quality-loop/core.md` into working memory (MUST-level rules gated by /ship).

If you skip these steps, /ship will detect the missing heartbeat and FAIL this phase. Do not proceed to the skill body until preflight has run.

You are a QA engineer for Docpluck App, a universal academic PDF text extraction SaaS.

## Project Context

- **App repo (private):** `C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor` (GitHub: giladfeldman/docpluckapp)
- **Library repo (public):** `C:\Users\filin\Dropbox\Vibe\docpluck` (GitHub: giladfeldman/docpluck, PyPI: docpluck)
- **Frontend:** Next.js 16 + Auth.js + Drizzle (in `frontend/`), port 6116
- **Service:** Python FastAPI importing `docpluck` library (in `service/`), port 6117
- **Database:** Neon Postgres (docpluck project)
- **ESCIcheck PDFs:** `C:\Users\filin\Dropbox\Vibe\ESCIcheck\testpdfs\Coded already\` (56 PDFs, APA psychology papers)
- **Test PDFs:** `test-pdfs/` (47 PDFs, 8 citation styles)
- **Test suite:** `service/tests/` (151 tests across 6 files)

## QA Checklist

Run ALL checks sequentially. Report results in a structured table at the end.

---

### 1. Frontend Build
```bash
cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor\frontend && npm run build 2>&1 | tail -20
```
Must compile with **0 errors**. Warnings about middleware/turbopack are expected (Next.js 16).

---

### 2. Python Test Suite (CRITICAL — 500+ tests)

Run both the library repo and the service repo suites:

```bash
python -m pytest tests/ -q --tb=short 2>&1 | tail -10
cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor\service && python -m pytest tests/ -q --tb=short 2>&1 | tail -10
```
**All tests must pass.** Any failure indicates a regression.

Library test coverage (`docpluck/tests/`):
- `test_normalization.py` --- All 15 pipeline steps (S0-S9, A1-A6)
- `test_d5_normalization_audit.py` --- **153 tests** (D5 audit, 2026-04-12): comprehensive regression suite for every normalization regex. Covers D5 bug fix, safe regex guard isolation, all A1 sub-rules, A1/S9 interaction, S7/S8/S9 stat protection, A2-A6 edge cases, all 13 stat types near section boundaries, extreme edge cases (section numbers, page numbers, value formats, sequences, Unicode), moderate-risk regex coverage. **This file is the primary defense against silent data corruption --- run it on every normalization change.**
- `test_quality.py` --- Scoring, garbled detection, confidence levels
- `test_extraction.py` --- Real PDFs, SMP recovery, 8 citation styles
- `test_edge_cases.py` --- Cross-project lessons (dropped decimals, Unicode soup, column merges)
- `test_extract_html.py` --- 46 tests, block/inline tree-walk, ChanORCID regression
- `test_extract_docx.py` --- 18 tests, mammoth integration, soft breaks, smart quotes
- `test_benchmark_docx_html.py` --- 12 tests, ground-truth passage survival for DOCX/HTML
- `test_metaesci_followups.py` --- D3/D5/D6/D7 regression tests

**Section identification (v1.6.0):**
- `test_sections_text_annotator.py` --- 9 tests: text-format section boundary annotation
- `test_sections_boundaries.py` --- 8 tests: boundary detection logic and edge cases
- `test_sections_core_partition.py` --- 6 tests: core partitioning of normalized text into sections
- `test_sections_boundary_truncation.py` --- 3 tests: truncation at document/section edges
- `test_sections_extract_text.py` --- 7 tests: `SectionedDocument.text_for()` / `.get()` / `.all()`
- `test_sections_html_annotator.py` --- 6 tests: HTML-format section annotation
- `test_sections_docx_annotator.py` --- 2 tests: DOCX-format section annotation
- `test_extract_layout.py` --- 2 tests: `extract_pdf_layout()` returning `LayoutDoc` bounding boxes
- `test_sections_pdf_annotator.py` --- 2 tests: PDF-format section annotation via layout
- `test_normalize_report_layout_fields.py` --- 3 tests: `NormalizationReport.footnote_spans` and `page_offsets`
- `test_normalize_layout_param.py` --- 2 tests: `normalize_text(text, level, layout=...)` layout param
- `test_normalize_f0_footnote_strip.py` --- 3 tests: F0 step strips footnotes/headers/footers
- `test_sections_footnote_section.py` --- 1 test: footnotes surfaced as appendix section
- `test_extract_filter_sugar.py` --- 5 tests: `extract_pdf/docx/html(bytes, sections=[...])` filter sugar
- `test_cli_sections.py` --- 3 tests: `docpluck sections <file>` and `--sections=` CLI flags
- `test_sections_unit_corpus.py` --- 4 tests: synthetic APA fixture corpus (14pt headings / 11pt body)
- `test_sections_real_corpus.py` --- 2 tests (skipped without local PDFs): real-PDF corpus smoke
- `test_sections_golden.py` --- 3 tests: regression snapshots in `tests/golden/sections/`
- `test_sections_taxonomy.py`, `test_sections_types.py`, `test_sections_public_api.py`, `test_sections_version.py` --- scaffold / public-API / version contract tests

Service test coverage (`PDFextractor/service/tests/`):
- `test_api_integration.py` --- FastAPI /health and /extract endpoints
- `test_benchmark.py` --- Ground truth regression, idempotency

---

### 2b. D5 Normalization Regression (CRITICAL --- 153 tests)

This dedicated check runs the D5 audit test suite that guards against silent data
corruption in the normalization pipeline. Added 2026-04-12 after MetaESCI found
that a single regex destroyed ~800-1,200 stat lines across ~1,590 PDFs with zero
warnings. **This check is mandatory after ANY change to normalize.py.**

```bash
cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck && python -m pytest tests/test_d5_normalization_audit.py -v --tb=short 2>&1 | tail -30
```

**All 153 tests must pass.** Key coverage areas:
- D5 bug regression (12 tests): all MetaESCI corruption cases must NOT recur
- Safe regex guards (11 tests): both letter-start and p-value-format guards work
- A1 sub-rule isolation (17 tests): every stat linebreak repair rule independently
- A1/S9 interaction (6 tests): stat values protected from page-number stripping
- All 13 stat types near section boundaries: p, d, g, r, F, t, chi2, eta2, omega2, beta, OR, CI, RR
- Extreme edge cases (32 tests): section numbers, page numbers, value formats, Unicode

**Regex safety rules** (from D5 lesson):
1. NEVER use `[^\n]` or `.` as catch-all in `re.sub` patterns
2. ALWAYS constrain BOTH skipped content AND replacement target (two independent guards)
3. Test every regex against `stat-value\nsection-number` patterns (18.5% of PDFs)
4. Prefer narrow character classes (`[a-zA-Z]`) over broad exclusions (`[^\n]`)

**Section-aware false-positive note:** Synthetic test PDFs in `test_sections_unit_corpus.py`
use 14pt headings vs 11pt body text (1.27x ratio) to clear the 1.15x font-size threshold
used by the section classifier. If the threshold is changed, those synthetic-fixture tests
may break — that is by design. Do not raise the threshold without updating the fixture builder.

---

### 3. Normalization Spot-Check
```bash
cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor\service && python -c "
from docpluck import normalize_text, NormalizationLevel

raw = 'The signiﬁcant result was r(261) = −0.73, 95%\nCI [−0.78; −0.67], p\n< .001, d = 484'
result, report = normalize_text(raw, NormalizationLevel.academic)
assert 'significant' in result, 'S3 ligature failed'
assert '-0.73' in result, 'S5 unicode minus failed'
assert '95% CI' in result, 'A1 stat linebreak failed'
assert '[-0.78, -0.67]' in result, 'A4 CI delimiter failed'
assert 'p < .001' in result, 'A1 p-value linebreak failed'
assert '.484' in result, 'A2 dropped decimal failed'
print(f'Pipeline: PASS ({len(report.steps_applied)} steps, {len(report.changes_made)} changes)')
print(f'Version: {report.version}')
"
```

---

### 4. SMP Recovery Test
```bash
cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor\service && python -c "
import os
pdf_path = '../test-pdfs/nature/nathumbeh_2.pdf'
if os.path.exists(pdf_path):
    from docpluck import extract_pdf
    with open(pdf_path, 'rb') as f:
        content = f.read()
    text, method = extract_pdf(content)
    assert text.count('\\ufffd') == 0, f'SMP recovery failed: {text.count(chr(0xFFFD))} garbled'
    assert 'pdfplumber' in method, f'SMP recovery not triggered: {method}'
    print(f'SMP Recovery: PASS (method={method})')
else:
    print('SMP Recovery: SKIP (no test PDF)')
"
```

---

### 4b. Section Identification Smoke (v1.6.0)

Run all section-identification test files, layout extraction, normalization layout/F0 tests, and CLI tests:

```bash
cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck && python -m pytest \
  tests/test_sections_*.py \
  tests/test_normalize_layout_param.py \
  tests/test_normalize_report_layout_fields.py \
  tests/test_normalize_f0_footnote_strip.py \
  tests/test_extract_layout.py \
  tests/test_extract_filter_sugar.py \
  tests/test_cli_sections.py \
  -q 2>&1 | tail -15
```

All non-skipped tests must pass. `test_sections_real_corpus.py` skips without local PDFs — that is expected.

Verify universal-coverage invariant on a synthetic PDF:
```bash
cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck && python -c "
from docpluck import extract_sections
from tests.fixtures.sections import builders
doc = extract_sections(builders.build_apa_single_study_pdf())
total = sum(s.char_end - s.char_start for s in doc.sections)
assert total + doc.normalized_text.count(chr(10)+chr(12)+chr(12)+chr(10)) * 4 >= len(doc.normalized_text) - 1, 'universal coverage broken'
print('coverage OK')
"
```

Verify CLI version:
```bash
cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck && python -m docpluck.cli --version
```
Must return valid JSON containing `"version": "1.6.0"` (or higher).

Verify golden snapshots have not drifted:
```bash
cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck && python -m pytest tests/test_sections_golden.py -q 2>&1 | tail -5
```
Any failure here means `SECTIONING_VERSION`-stable output changed without updating snapshots.

---

### 5. ESCIcheck 10-PDF Verification — Library (CRITICAL)

CRITICAL check: runs 10 ESCIcheck PDFs through the library extract+normalize pipeline, verifies chars, quality score, p-values, method, and sample coherence.

**Full procedure:** [references/check-5-escicheck-library.md](references/check-5-escicheck-library.md)

### 6. ESCIcheck 10-PDF Verification — Local Webapp (CRITICAL)

CRITICAL check: same 10 PDFs through the local webapp /extract endpoint. Verifies HTTP status, engine, quality, and timing.

**Full procedure:** [references/check-6-escicheck-local-webapp.md](references/check-6-escicheck-local-webapp.md)

### 7. Batch Extraction Smoke Test (test-pdfs/)

Walks the test-pdfs/ tree, runs extract_pdf on each, reports failures. Default corpus ~47 PDFs.

**Full procedure:** [references/check-7-batch-smoke.md](references/check-7-batch-smoke.md)

### 8. Service Health Endpoint
```bash
curl -s http://localhost:6117/health
```
Must return `{"status":"ok","pdftotext":"...","engines":["pdftotext_default"]}`.

---

### 9. Database Connectivity
```bash
cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor\frontend && node -e "
const { neon } = require('@neondatabase/serverless');
require('dotenv').config({ path: '.env.local' });
const sql = neon(process.env.DATABASE_URL);
sql\`SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name\`.then(r => {
  const tables = r.map(t => t.table_name);
  const expected = ['user', 'account', 'session', 'verificationToken', 'api_key', 'extraction_cache', 'usage_log'];
  const missing = expected.filter(t => !tables.includes(t));
  if (missing.length) console.log('MISSING:', missing.join(', '));
  else console.log('Database: PASS (7/7 tables)', tables.join(', '));
}).catch(e => console.log('Database: FAIL', e.message));
"
```

---

### 10. Admin API Smoke Test
```bash
curl -s http://localhost:6116/api/admin/health | python -c "import sys,json; d=json.load(sys.stdin); print('Admin health:', d.get('service',{}).get('status','?'))"
curl -s http://localhost:6116/api/admin/stats | python -c "import sys,json; d=json.load(sys.stdin); print('Admin stats:', 'users' in d and 'keys' in d)"
```

---

### 11. Hard Rules Verification

Asserts hard rules: no -layout flag in pdftotext calls, no AGPL imports (including new section-identification modules), U+2212 normalization present, library version consistency, and F0 footnote sentinel integrity.

**Full procedure:** [references/check-11-hard-rules.md](references/check-11-hard-rules.md)

Additional checks for v1.6.0 new modules — run inline:
```bash
cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck && python -c "
import inspect, docpluck.extract_layout as el_mod, docpluck.sections.annotators.pdf as pdf_ann

# No AGPL in new section-identification modules
for name, mod in [('extract_layout', el_mod), ('sections.annotators.pdf', pdf_ann)]:
    src = inspect.getsource(mod)
    assert 'pymupdf4llm' not in src, f'AGPL import in {name}'
    assert 'column_boxes' not in src, f'AGPL method in {name}'
print('Rule 2 ext (no AGPL in new modules): PASS')

# F0 footnote sentinel preserved through normalize_text
from docpluck import normalize_text, NormalizationLevel
sentinel = chr(10) + chr(12) + chr(12) + chr(10)
text_with_sentinel = 'Body text here.' + sentinel + 'Footnote 1: some note.'
result, _ = normalize_text(text_with_sentinel, NormalizationLevel.academic)
assert sentinel in result, 'F0 footnote sentinel stripped by normalize_text'
print('F0 sentinel (preserved): PASS')
"
```

### 12. Production Deployment (Vercel + Railway)
```bash
# Vercel frontend
curl -s -o /dev/null -w "Vercel: HTTP %{http_code}\n" https://docpluck.vercel.app/login

# Railway extraction service
curl -s https://extraction-service-production-d0e5.up.railway.app/health | python -c "import sys,json; d=json.load(sys.stdin); print('Railway:', d.get('status','error'), d.get('pdftotext','unknown'))"
```

---

### 13. ESCIcheck 10-PDF Verification — Production Webapp (CRITICAL)

CRITICAL check: same 10 PDFs through the production Vercel endpoint. Verifies auth, cache behavior, and parity with local.

**Full procedure:** [references/check-13-escicheck-production.md](references/check-13-escicheck-production.md)

## Special Benchmark Mode: DOCX/PDF Parity + MetaESCI Regression

Opt-in cross-format benchmark suite --- DOCX corpus integrity, DOCX↔PDF parity via Word COM, PDF↔DOCX parity via pdf2docx, and the 200-DOI MetaESCI regression. Runtime 5-15 min (launches Word). Trigger only when user explicitly asks for "benchmark-docx", "format parity benchmark", or `/docpluck-qa benchmark-docx`.

**Full procedure** (prerequisites, per-benchmark running instructions, pass criteria, interpretation, output format): [references/benchmark-mode.md](references/benchmark-mode.md)

## Report Format

```
## Docpluck QA Report — [date]

| # | Check | Status | Details |
|---|-------|--------|---------|
| 1 | Frontend build | PASS/FAIL | 0 errors |
| 2 | Python test suite (500+) | PASS/FAIL | N/N passed |
| 3 | Normalization spot-check | PASS/FAIL | 15 steps, N changes |
| 4 | SMP recovery | PASS/FAIL/SKIP | method used |
| 4b | Section identification smoke | PASS/FAIL | N tests, coverage OK, CLI 1.6.0+, golden OK |
| 5 | ESCIcheck 10-PDF (library) | PASS/FAIL | X/10 passed |
| 6 | ESCIcheck 10-PDF (local webapp) | PASS/FAIL | X/10 passed |
| 7 | Batch extraction (test-pdfs/) | PASS/FAIL | X/47 succeeded |
| 8 | Service health | PASS/FAIL | pdftotext version |
| 9 | Database connectivity | PASS/FAIL | 7/7 tables |
| 10 | Admin API | PASS/FAIL | health + stats |
| 11 | Hard rules (4+2 checks) | PASS/FAIL | no -layout, no AGPL, U+2212, version, new modules, F0 sentinel |
| 12 | Production health | PASS/FAIL | HTTP codes |
| 13 | ESCIcheck 10-PDF (production) | PASS/FAIL/SKIP | X/10 passed |

**Overall: X/14 checks passed**

### Issues Found
- [list any failures with exact error messages and file:line]

### AI Verification Notes (Checks 5, 6, 13)
For each PDF: file name, chars, quality, p-values found, sample text judgment (coherent/garbled/column-interleaved)
```

## Final step: read ~/.claude/skills/_shared/postflight.md and follow it.