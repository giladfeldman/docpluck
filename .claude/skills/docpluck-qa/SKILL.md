---
name: docpluck-qa
description: Comprehensive QA engineer for Docpluck App (PDF + DOCX + HTML extraction SaaS). Runs 211-test Python suite, ESCIcheck 10-PDF AI verification (library + local webapp + production), normalization spot-check, batch extraction, service health, DB, admin API, and deployment checks. When asked for a "DOCX benchmark" or "format parity benchmark" or "--benchmark-docx" or similar, runs the special cross-format benchmark suite (CitationGuard DOCX corpus + DOCX\u2192PDF + PDF\u2192DOCX). Use /docpluck-qa whenever testing, after changes, or before deployment.
tags: [python, nextjs, pdf, docx, fastapi, drizzle, neon, qa]
---

# Docpluck QA

## Before starting: read ~/.claude/skills/_shared/preflight.md and follow it for this skill.

You are a QA engineer for Docpluck App, a universal academic PDF text extraction SaaS.

## Project Context

- **App repo (private):** `C:\Users\filin\Dropbox\Vibe\PDFextractor` (GitHub: giladfeldman/docpluckapp)
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
cd C:\Users\filin\Dropbox\Vibe\PDFextractor\frontend && npm run build 2>&1 | tail -20
```
Must compile with **0 errors**. Warnings about middleware/turbopack are expected (Next.js 16).

---

### 2. Python Test Suite (CRITICAL — 364+ tests)

Run both the library repo and the service repo suites:

```bash
cd C:\Users\filin\Dropbox\Vibe\docpluck && python -m pytest tests/ -q --tb=short 2>&1 | tail -10
cd C:\Users\filin\Dropbox\Vibe\PDFextractor\service && python -m pytest tests/ -q --tb=short 2>&1 | tail -10
```
**All tests must pass.** Any failure indicates a regression.

Library test coverage (`docpluck/tests/`):
- `test_normalization.py` — All 15 pipeline steps (S0-S9, A1-A6)
- `test_d5_normalization_audit.py` — **153 tests** (D5 audit, 2026-04-12): comprehensive regression suite for every normalization regex. Covers D5 bug fix, safe regex guard isolation, all A1 sub-rules, A1/S9 interaction, S7/S8/S9 stat protection, A2-A6 edge cases, all 13 stat types near section boundaries, extreme edge cases (section numbers, page numbers, value formats, sequences, Unicode), moderate-risk regex coverage. **This file is the primary defense against silent data corruption — run it on every normalization change.**
- `test_quality.py` — Scoring, garbled detection, confidence levels
- `test_extraction.py` — Real PDFs, SMP recovery, 8 citation styles
- `test_edge_cases.py` — Cross-project lessons (dropped decimals, Unicode soup, column merges)
- `test_extract_html.py` — 46 tests, block/inline tree-walk, ChanORCID regression
- `test_extract_docx.py` — 18 tests, mammoth integration, soft breaks, smart quotes
- `test_benchmark_docx_html.py` — 12 tests, ground-truth passage survival for DOCX/HTML
- `test_metaesci_followups.py` — D3/D5/D6/D7 regression tests

Service test coverage (`PDFextractor/service/tests/`):
- `test_api_integration.py` — FastAPI /health and /extract endpoints
- `test_benchmark.py` — Ground truth regression, idempotency

---

### 2b. D5 Normalization Regression (CRITICAL — 153 tests)

This dedicated check runs the D5 audit test suite that guards against silent data
corruption in the normalization pipeline. Added 2026-04-12 after MetaESCI found
that a single regex destroyed ~800-1,200 stat lines across ~1,590 PDFs with zero
warnings. **This check is mandatory after ANY change to normalize.py.**

```bash
cd C:\Users\filin\Dropbox\Vibe\docpluck && python -m pytest tests/test_d5_normalization_audit.py -v --tb=short 2>&1 | tail -30
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

---

### 3. Normalization Spot-Check
```bash
cd C:\Users\filin\Dropbox\Vibe\PDFextractor\service && python -c "
from docpluck import normalize_text, NormalizationLevel

raw = 'The signi\ufb01cant result was r(261) = \u22120.73, 95%\nCI [\u22120.78; \u22120.67], p\n< .001, d = 484'
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
cd C:\Users\filin\Dropbox\Vibe\PDFextractor\service && python -c "
import os
pdf_path = '../test-pdfs/nature/nathumbeh_2.pdf'
if os.path.exists(pdf_path):
    from docpluck import extract_pdf
    with open(pdf_path, 'rb') as f:
        content = f.read()
    text, method = extract_pdf(content)
    assert text.count('\ufffd') == 0, f'SMP recovery failed: {text.count(chr(0xFFFD))} garbled'
    assert 'pdfplumber' in method, f'SMP recovery not triggered: {method}'
    print(f'SMP Recovery: PASS (method={method})')
else:
    print('SMP Recovery: SKIP (no test PDF)')
"
```

---

### 5. ESCIcheck 10-PDF Verification — Library (CRITICAL)

This check verifies the `docpluck` library works correctly on real APA psychology papers from the ESCIcheck corpus. You (the AI) must verify each output qualitatively.

```bash
python -c "
import os, re, sys
from docpluck import extract_pdf, normalize_text, NormalizationLevel, compute_quality_score

ESCI_DIR = r'C:\Users\filin\Dropbox\Vibe\ESCIcheck\testpdfs\Coded already'
pdfs = sorted(os.listdir(ESCI_DIR))[:10]  # First 10 alphabetically

results = []
for fname in pdfs:
    path = os.path.join(ESCI_DIR, fname)
    with open(path, 'rb') as f:
        content = f.read()
    text, method = extract_pdf(content)
    if text.startswith('ERROR:'):
        results.append({'file': fname, 'status': 'FAIL', 'error': text})
        continue
    normalized, report = normalize_text(text, NormalizationLevel.academic)
    quality = compute_quality_score(normalized)
    # Extract p-values as a basic sanity check
    pvalues = re.findall(r'[pP]\s*[<=>]\s*\.?\d+', normalized)
    # Also catch agreement/reliability stats (CCC, ICC, kappa, r =) for papers that don't use p-values
    other_stats = re.findall(r'(?:CCC|ICC|kappa|chi2|r)\s*[=<>]\s*[.0-9]+', normalized)
    has_stats = len(pvalues) >= 5 or len(other_stats) >= 3
    results.append({
        'file': fname[:60],
        'chars': len(normalized),
        'method': method,
        'quality': quality['score'],
        'garbled': quality['garbled'],
        'pvalues_found': len(pvalues),
        'other_stats': len(other_stats),
        'steps': len(report.steps_applied),
        'sample': normalized[500:900].replace('\n', ' ').strip(),
        'has_stats': has_stats,
    })

for r in results:
    if 'error' in r:
        print(f'FAIL {r[\"file\"]}: {r[\"error\"]}')
    else:
        status = 'FAIL' if r['garbled'] or r['chars'] < 5000 or not r['has_stats'] else 'PASS'
        print(f'{status} | {r[\"chars\"]:,}ch | q={r[\"quality\"]} | p={r[\"pvalues_found\"]} | other={r[\"other_stats\"]} | {r[\"method\"]}')
        print(f'  FILE: {r[\"file\"]}')
        print(f'  SAMPLE: ...{r[\"sample\"]}...')
        print()
"
```

**AI verification criteria** — for each PDF you must confirm:
- [ ] `chars` ≥ 5,000 (real content extracted, not empty)
- [ ] `quality` score ≥ 60 (not garbled)
- [ ] `garbled` = False
- [ ] `pvalues_found` ≥ 5 (statistical paper has findable stats)
- [ ] `method` = `pdftotext_default` (normal extraction, no SMP issues)
- [ ] `sample` text is coherent English academic prose (not jumbled)
- [ ] No obvious column interleaving in sample (words from two columns not merged)

If any PDF fails criteria: investigate and fix before proceeding.

---

### 6. ESCIcheck 10-PDF Verification — Local Webapp (CRITICAL)

Requires local service running on port 6117 AND frontend on port 6116. Test via the API endpoint.

First start the service (if not running):
```bash
cd C:\Users\filin\Dropbox\Vibe\PDFextractor\service && uvicorn app.main:app --port 6117 --reload &
```

Then run:
```bash
python -c "
import os, re, json, requests

ESCI_DIR = r'C:\Users\filin\Dropbox\Vibe\ESCIcheck\testpdfs\Coded already'
pdfs = sorted(os.listdir(ESCI_DIR))[:10]

# Test via the Python service directly (bypasses auth)
results = []
for fname in pdfs:
    path = os.path.join(ESCI_DIR, fname)
    with open(path, 'rb') as f:
        content = f.read()
    try:
        r = requests.post(
            'http://localhost:6117/extract?normalize=academic&quality=true',
            files={'file': (fname, content, 'application/pdf')},
            timeout=120
        )
        if r.status_code != 200:
            results.append({'file': fname[:50], 'status': 'FAIL', 'error': f'HTTP {r.status_code}: {r.text[:100]}'})
            continue
        d = r.json()
        pvalues = re.findall(r'[pP]\s*[<=>]\s*\.?\d+', d['text'])
        results.append({
            'file': fname[:50],
            'status': 'PASS' if d['quality']['score'] >= 60 and len(pvalues) >= 5 else 'FAIL',
            'chars': d['metadata']['chars'],
            'engine': d['metadata']['engine'],
            'quality': d['quality']['score'],
            'pvalues': len(pvalues),
            'time_ms': d['metadata']['extraction_time_ms'],
        })
    except Exception as e:
        results.append({'file': fname[:50], 'status': 'FAIL', 'error': str(e)})

for r in results:
    if 'error' in r:
        print(f\"FAIL | {r['file']} | {r['error']}\")
    else:
        print(f\"{r['status']} | {r['file']} | {r['chars']:,}ch | q={r['quality']} | p={r['pvalues']} | {r['time_ms']}ms\")

passed = sum(1 for r in results if r.get('status') == 'PASS')
print(f'Service: {passed}/{len(results)} passed')
"
```

**AI verification criteria** — same as Check 5 plus:
- [ ] HTTP 200 for all 10 PDFs
- [ ] `time_ms` < 30,000 (no timeout)
- [ ] `engine` field present

---

### 7. Batch Extraction Smoke Test (test-pdfs/)
```bash
cd C:\Users\filin\Dropbox\Vibe\PDFextractor\service && python -c "
import os
from docpluck import extract_pdf
base = '../test-pdfs'
if os.path.exists(base):
    failures = []
    count = 0
    for root, dirs, files in os.walk(base):
        for f in files:
            if f.endswith('.pdf'):
                count += 1
                with open(os.path.join(root, f), 'rb') as fh:
                    content = fh.read()
                try:
                    text, method = extract_pdf(content)
                    if text.startswith('ERROR:') or len(text) < 100:
                        failures.append(f'{f}: {text[:80] if text.startswith(\"ERROR:\") else len(text)+\" chars\"}')
                except Exception as e:
                    failures.append(f'{f}: {e}')
    if failures:
        print(f'Batch: FAIL ({len(failures)}/{count})')
        for f in failures: print(f'  {f}')
    else:
        print(f'Batch: PASS ({count}/{count} PDFs)')
else:
    print('Batch: SKIP (no test-pdfs/ directory)')
"
```

---

### 8. Service Health Endpoint
```bash
curl -s http://localhost:6117/health
```
Must return `{"status":"ok","pdftotext":"...","engines":["pdftotext_default"]}`.

---

### 9. Database Connectivity
```bash
cd C:\Users\filin\Dropbox\Vibe\PDFextractor\frontend && node -e "
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
```bash
cd C:\Users\filin\Dropbox\Vibe\PDFextractor\service && python -c "
import re

# Rule 1: No -layout flag in pdftotext calls (check library)
import docpluck.extract as ext_mod
import inspect
source = inspect.getsource(ext_mod)
calls = re.findall(r'subprocess\.run\(\s*\[.*?\]', source, re.DOTALL)
for call in calls:
    assert '-layout' not in call, f'BLOCKER: -layout in {call}'
print('Rule 1 (no -layout): PASS')

# Rule 2: No AGPL imports in library or service
import docpluck.normalize as norm_mod, docpluck.quality as qual_mod
for name, mod in [('normalize', norm_mod), ('quality', qual_mod), ('extract', ext_mod)]:
    src = inspect.getsource(mod)
    assert 'pymupdf4llm' not in src, f'AGPL import in {name}'
    assert 'column_boxes' not in src, f'AGPL method in {name}'
with open('app/main.py') as f:
    main_src = f.read()
assert 'pymupdf4llm' not in main_src, 'AGPL import in main.py'
print('Rule 2 (no AGPL): PASS')

# Rule 3: U+2212 normalization exists in library (check file bytes to avoid encoding issues)
import docpluck.normalize as _nm_mod
with open(_nm_mod.__file__, 'rb') as _f:
    _norm_bytes = _f.read()
assert b'\\u2212' in _norm_bytes or b'\xe2\x88\x92' in _norm_bytes, 'U+2212 normalization missing'
print('Rule 3 (U+2212 norm): PASS')

# Rule 4: Library version is consistent
import docpluck
assert docpluck.__version__ == '1.4.5', f'Version mismatch: {docpluck.__version__}'
print(f'Rule 4 (version=1.4.5): PASS')
"
```

---

### 12. Production Deployment (Vercel + Railway)
```bash
# Vercel frontend
curl -s -o /dev/null -w "Vercel: HTTP %{http_code}\n" https://docpluck.vercel.app/login

# Railway extraction service
curl -s https://extraction-service-production-d0e5.up.railway.app/health | python -c "import sys,json; d=json.load(sys.stdin); print('Railway:', d.get('status','error'), d.get('pdftotext','unknown'))"
```

---

### 13. ESCIcheck 10-PDF Verification — Production Webapp (CRITICAL)

Tests the full production stack end-to-end. Requires a valid API key from the live app.

```bash
python -c "
import os, re, json, requests

API_KEY = os.environ.get('DOCPLUCK_API_KEY', '')
if not API_KEY:
    print('SKIP: set DOCPLUCK_API_KEY env var to run production check')
    exit(0)

ESCI_DIR = r'C:\Users\filin\Dropbox\Vibe\ESCIcheck\testpdfs\Coded already'
pdfs = sorted(os.listdir(ESCI_DIR))[:10]

results = []
for fname in pdfs:
    path = os.path.join(ESCI_DIR, fname)
    with open(path, 'rb') as f:
        content = f.read()
    try:
        r = requests.post(
            'https://docpluck.vercel.app/api/extract?normalize=academic&quality=true',
            files={'file': (fname, content, 'application/pdf')},
            headers={'Authorization': f'Bearer {API_KEY}'},
            timeout=120
        )
        if r.status_code != 200:
            results.append({'file': fname[:50], 'status': 'FAIL', 'error': f'HTTP {r.status_code}'})
            continue
        d = r.json()
        pvalues = re.findall(r'[pP]\s*[<=>]\s*\.?\d+', d.get('text',''))
        results.append({
            'file': fname[:50],
            'status': 'PASS' if d.get('quality',{}).get('score',0) >= 60 and len(pvalues) >= 5 else 'FAIL',
            'chars': d.get('metadata',{}).get('chars',0),
            'quality': d.get('quality',{}).get('score',0),
            'pvalues': len(pvalues),
            'cached': d.get('metadata',{}).get('cached', False),
        })
    except Exception as e:
        results.append({'file': fname[:50], 'status': 'FAIL', 'error': str(e)})

for r in results:
    if 'error' in r:
        print(f\"FAIL | {r['file']} | {r['error']}\")
    else:
        cached_note = ' [cached]' if r.get('cached') else ''
        print(f\"{r['status']} | {r['file']} | {r['chars']:,}ch | q={r['quality']} | p={r['pvalues']}{cached_note}\")

passed = sum(1 for r in results if r.get('status') == 'PASS')
print(f'Production: {passed}/{len(results)} passed')
"
```

**AI verification criteria** — same as Check 5, plus:
- [ ] Auth accepted (not 401/403)
- [ ] Cache working on re-run (second run shows `[cached]`)

---

---

## Special Benchmark Mode: DOCX/PDF Parity + MetaESCI Regression

Trigger this mode when the user asks for any of:
- "DOCX benchmark", "format parity benchmark", "cross-format benchmark"
- "MetaESCI regression", "200-DOI benchmark", "docpluck shootout"
- "--benchmark-docx", "/docpluck-qa benchmark-docx"
- "test DOCX extraction", "compare DOCX to PDF", "DOCX vs PDF"
- "run the docpluck benchmarks" (without further qualification)

This mode runs the four comprehensive benchmark scripts in `docpluck/benchmarks/` that stress-test extraction against:
1. The CitationGuard DOCX validation corpus (20 real academic papers + 4 corrupted edge cases)
2. Cross-format parity via Microsoft Word (DOCX↔PDF) and pdf2docx (PDF↔DOCX)
3. The frozen 200-DOI MetaESCI regression corpus (seed=42, resolved via article-finder)

**Prerequisites for #3:** the `article-finder` skill's `corpus-query.py` must be runnable and the shared `ArticleRepository/fulltext/` must be populated with the `metaesci` source_project tag. Phase C.0.5 landed 2026-04-11; if the corpus resolution fails, run `python ~/.claude/skills/article-finder/corpus-query.py --benchmark metaesci_regression` manually to diagnose.

**Do NOT run this mode during normal QA checks** — it takes 5–15 minutes (Word COM is slow) and launches Microsoft Word. Only run it when explicitly asked or after significant DOCX/HTML extraction changes.

### Prerequisites

- Microsoft Word installed (for `docx2pdf`, accessed via COM)
- Python packages: `mammoth`, `beautifulsoup4`, `lxml`, `rapidfuzz`, `pdf2docx`, `docx2pdf`
- CitationGuard corpus present at `C:\Users\filin\Dropbox\Vibe\CitationGuard\apps\worker\testpdfs\validation\docx\`
- PDF test corpus at `C:\Users\filin\Dropbox\Vibe\PDFextractor\test-pdfs\`

### Running

Full benchmark (5–15 minutes, launches Word):
```bash
cd C:\Users\filin\Dropbox\Vibe\docpluck && python benchmarks/run_all.py
```

Quick mode (3 files per benchmark, 2–4 minutes):
```bash
cd C:\Users\filin\Dropbox\Vibe\docpluck && python benchmarks/run_all.py --quick
```

Skip Word-based conversion (if Word unavailable):
```bash
cd C:\Users\filin\Dropbox\Vibe\docpluck && python benchmarks/run_all.py --skip docx2pdf
```

Individual benchmarks:
```bash
# 1. DOCX corpus (24 files, ~45s)
python benchmarks/bench_docx_corpus.py --json benchmarks/results/docx_corpus.json

# 2. DOCX → PDF cross-format (20 files via Word COM, ~5-10 min)
python benchmarks/bench_docx_vs_pdf.py --json benchmarks/results/docx_vs_pdf.json

# 3. PDF → DOCX reverse cross-format (8 files via pdf2docx, ~2-4 min)
python benchmarks/bench_pdf_vs_docx.py --json benchmarks/results/pdf_vs_docx.json

# 4. MetaESCI regression baseline (200 frozen DOIs, ~70s)
python benchmarks/bench_metaesci_regression.py --json benchmarks/results/metaesci_regression.json
```

### What Each Benchmark Validates

**1. DOCX corpus benchmark** (`bench_docx_corpus.py`)
- Runs `extract_docx()` on all 24 CitationGuard DOCX files
- Validates: all 20 real papers extract successfully; all 4 corrupted files fail correctly
- Checks quality score ≥80 and "high" confidence for every real paper
- Detects garbled extractions (should be 0)
- Reports total chars, per-file times, aggregate stats

**2. DOCX → PDF cross-format benchmark** (`bench_docx_vs_pdf.py`)
- For each DOCX: extract text, convert DOCX→PDF via Word (`docx2pdf`), extract PDF text, compare
- Uses `rapidfuzz.token_set_ratio` to measure similarity (should be ≥ 80%)
- Uses char-count ratio to detect content loss (should be 0.7–1.3)
- Both extractors should produce "high" confidence quality scores
- This is the A/B gold-standard: same content, two extraction paths — asymmetry reveals bugs in either extractor

**3. PDF → DOCX reverse cross-format benchmark** (`bench_pdf_vs_docx.py`)
- For each PDF: extract text, convert PDF→DOCX via `pdf2docx` (pure Python), extract DOCX text, compare
- Default selection: 8 PDFs across APA, Vancouver, AMA, Harvard, IEEE, Nature styles
- Same pass criteria as #2

### Pass Criteria

Benchmark | Threshold
--- | ---
DOCX corpus extraction success | 20/20 real papers
DOCX corpus quality score | avg ≥ 80, all high confidence
DOCX corpus garbled count | 0
DOCX→PDF similarity (token_set_ratio) | avg ≥ 80%, min ≥ 80%
DOCX→PDF char ratio | 0.7–1.3
PDF→DOCX similarity | avg ≥ 80%, min ≥ 80%
PDF→DOCX char ratio | 0.7–1.3
MetaESCI extraction success | 200/200 (zero crashes, zero extraction errors)
MetaESCI high confidence | ≥ 99% (198/200+)
MetaESCI avg quality | ≥ 80 / 100
MetaESCI total U+FFFD | 0
MetaESCI stat linebreak survivors | 0
MetaESCI dropped decimal survivors | 0 (watch — current baseline has 21 in 3 files, real gaps pending A1/A2 enhancement)

### Interpreting Results

- **Similarity < 80%**: the two extractors are producing substantially different text for the same content. Investigate word-order or reading-order differences, soft-break handling, or table linearization.
- **Char ratio far from 1.0**: one extractor is missing content (images, equations, headers, tracked changes). Investigate which format is losing data.
- **DOCX quality score < PDF quality score**: something is wrong — DOCX should be cleaner than PDF (no column interleaving, no ligatures, no SMP Unicode). This is a red flag for mammoth configuration or the tree-walk.
- **OMML equations**: known limitation — mammoth drops Office Math objects. Papers with stats inside equations will show lower char counts in DOCX vs PDF.

### Output

Benchmark writes three files to `benchmarks/results/`:
- `docx_corpus.json` — per-file metrics
- `docx_vs_pdf.json` — cross-format comparison
- `pdf_vs_docx.json` — reverse comparison
- `REPORT.md` — consolidated markdown report

After running, read `benchmarks/results/REPORT.md` and report the summary to the user.

---

## Report Format

```
## Docpluck QA Report — [date]

| # | Check | Status | Details |
|---|-------|--------|---------|
| 1 | Frontend build | PASS/FAIL | 0 errors |
| 2 | Python test suite (151) | PASS/FAIL | 151/151 passed |
| 3 | Normalization spot-check | PASS/FAIL | 15 steps, N changes |
| 4 | SMP recovery | PASS/FAIL/SKIP | method used |
| 5 | ESCIcheck 10-PDF (library) | PASS/FAIL | X/10 passed |
| 6 | ESCIcheck 10-PDF (local webapp) | PASS/FAIL | X/10 passed |
| 7 | Batch extraction (test-pdfs/) | PASS/FAIL | X/47 succeeded |
| 8 | Service health | PASS/FAIL | pdftotext version |
| 9 | Database connectivity | PASS/FAIL | 7/7 tables |
| 10 | Admin API | PASS/FAIL | health + stats |
| 11 | Hard rules (4 checks) | PASS/FAIL | no -layout, no AGPL, U+2212, version |
| 12 | Production health | PASS/FAIL | HTTP codes |
| 13 | ESCIcheck 10-PDF (production) | PASS/FAIL/SKIP | X/10 passed |

**Overall: X/13 checks passed**

### Issues Found
- [list any failures with exact error messages and file:line]

### AI Verification Notes (Checks 5, 6, 13)
For each PDF: file name, chars, quality, p-values found, sample text judgment (coherent/garbled/column-interleaved)
```

## Final step: read ~/.claude/skills/_shared/postflight.md and follow it.
