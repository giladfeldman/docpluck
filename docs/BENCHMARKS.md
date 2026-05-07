# Benchmarks

Empirical validation of docpluck's extraction quality across academic PDF corpora.

---

## Phase 0: Engine Comparison (50 PDFs, 8 citation styles)

**Methodology:** Extract text from 50 academic PDFs covering 8 major citation styles. Compare three extraction engines. Verify against 29 manually typed ground-truth passages from PDF page images.

**Citation styles covered:**
- APA (American Psychological Association) — 2-column psychology papers
- AMA/JAMA (American Medical Association) — medical journals
- Vancouver/BMC — biomedical journals
- Nature/Science — two-column science journals with SMP fonts
- IEEE — engineering/computer science
- Harvard (BJPS) — business journals
- Chicago — social science
- AOM (Academy of Management) — management research

---

### Engine Comparison

| Engine | Speed | Ligatures | Reading order | Column handling | False positive risk | License |
|--------|:-----:|:---------:|:-------------:|:---------------:|:-------------------:|---------|
| **pdftotext default** | **0.4s** | 27.6 avg | Correct | Good | Low | MIT/GPL |
| pymupdf_raw | 0.9s | 27.6 avg | Interleaved | Poor | Low | AGPL v3 |
| pymupdf4llm | 9.4s | 0 | Correct | Best | **Very High** | AGPL v3 |

**Winner: pdftotext default mode.** 23× faster than pymupdf4llm, 100% ground-truth accuracy, no license restrictions.

---

### Ground Truth Verification (29 passages)

All passages manually typed from PDF page images, then matched against extracted text using fuzzy matching (rapidfuzz, partial_ratio ≥ 90%).

**Per-paper accuracy (APA psychology papers — highest-stakes use case):**

| Paper | Type | pdftotext default | pymupdf4llm | Notes |
|-------|------|:-----------------:|:-----------:|-------|
| chan_feldman_2025_cogemo | APA 2-column | **100%** | 100% | Tie |
| ip_feldman_2025_pspb | APA 2-column | **100%** | 100% | Tie |
| chandrashekar_meta_psych | APA 1-column | **100%** | ~40% | pymupdf4llm inflated by false positives |
| bmc_med_3 | Vancouver medical | 100% | 100% | Tie |

**Page-level deep verification (chan_feldman_2025_cogemo.pdf, page 12 — 8 correlation tests):**

| Engine | p-values found | 95% CIs found | Accuracy |
|--------|:--------------:|:-------------:|:--------:|
| pdftotext default | **8/8** | **8/8** | **100%** |
| pdftotext `-layout` | 6/8 | 8/8 | 75% |
| pymupdf_raw | 5/8 | 8/8 | 63% |
| pymupdf4llm | 8/8 | 8/8 | 100% |

**Conclusion:** pdftotext default mode = 100% accuracy on ground truth. The `-layout` flag causes 25% accuracy loss on two-column papers. pymupdf4llm matches quality but is AGPL-licensed and 23× slower.

---

### False Positive Analysis

**pymupdf4llm on IEEE paper (ieee_access_2.pdf):**
- Reported: 168 statistical patterns
- True positives: 1
- False positives: **167 (99.4%)**
- Cause: Figure axis labels `r>1`, `r>2` extracted as `<br>` HTML tags, misidentified as correlation coefficients

**pdftotext default on same paper:**
- Reported: 12 statistical patterns
- True positives: 11
- False positives: 1 (8.3%)

This false positive difference is what makes pymupdf4llm unsuitable for non-psychology papers.

---

## Cross-Project Artifact Rates

Artifact rates observed across real deployments. Sources: ESCIcheck (51 PDFs, ~475 statistical values), MetaESCI (8,456 PDFs, 121,000 results), MetaMisCitations (33 PDFs).

### Normalization artifacts (how often each pipeline step fires)

| Artifact | Rate | Step | Source |
|----------|------|------|--------|
| Dropped decimal p-values (`p = 484` → `p = .484`) | **4.88%** | A2 | MetaESCI 121K results |
| Statistical line breaks (`p =\n0.001`) | **0.77%** | A1 | MetaESCI |
| Column merge garbling | **0.65%** | Quality detection | MetaESCI |
| Page footer in p-value (`p = 806 U.S.`) | **0.25%** | Partial S9 | MetaESCI |
| Soft hyphen in words | Found in 14/50 test PDFs | S6 | PDFextractor corpus |
| SMP Unicode (Math Italic fonts) | Found in 2/50 test PDFs | pdfplumber recovery | PDFextractor corpus |
| Ligatures remaining after extraction | 27.6 avg per PDF | S3 | PDFextractor corpus |

### Statistical reporting artifacts (downstream consumer issues)

| Artifact | Rate | Notes |
|----------|------|-------|
| Effect sizes > 10 (likely line numbers) | 43 cases in MetaESCI corpus | `d=219`, `d=388` — line numbers adjacent to stats |
| Capital D/G effect sizes (`D = 0.44`) | 5 confirmed cases | Downstream regex must be case-insensitive |
| Generalized eta-squared false errors | 8 cases in MetaESCI | ηG² requires full ANOVA decomposition to verify |

---

## Idempotency Test

Normalization applied twice must produce identical output. Verified for all three levels across 10 test PDFs:

```python
text1, _ = normalize_text(raw, NormalizationLevel.academic)
text2, _ = normalize_text(text1, NormalizationLevel.academic)
assert text1 == text2  # Always passes
```

---

## Performance Benchmarks

| Operation | Typical | 95th percentile | Notes |
|-----------|:-------:|:---------------:|-------|
| `extract_pdf()` — normal | 400ms | 800ms | pdftotext, 10-30 page paper |
| `extract_pdf()` — SMP recovery | 9s | 15s | pdfplumber fallback |
| `normalize_text()` — standard | <1ms | 2ms | Pure Python |
| `normalize_text()` — academic | <1ms | 3ms | Pure Python |
| `compute_quality_score()` | <1ms | 1ms | Pure Python |
| `count_pages()` | <0.1ms | 0.1ms | Byte counting |

Normalization is fast enough to run on every PDF in a batch without throttling.

---

## Test Suite

211 tests across 9 files, all passing on Python 3.10-3.14:

| File | Tests | Coverage |
|------|:-----:|---------|
| `test_normalization.py` | 63 | All 15 pipeline steps (S0-S9, A1-A6), edge cases for each |
| `test_quality.py` | 10 | Score ranges, garbled detection, confidence levels |
| `test_edge_cases.py` | 30+ | Cross-project lessons (ESCIcheck, MetaESCI, PDFextractor, Unicode) |
| `test_extraction.py` | 15+ | Real PDFs, SMP recovery, 8 citation styles (skips if no poppler) |
| `test_extract_html.py` | 46 | Block/inline tree-walk, ChanORCID regression, whitespace, entities |
| `test_extract_docx.py` | 18 | Mammoth integration, soft breaks, smart quotes, ligatures |
| `test_benchmark_docx_html.py` | 12 | Ground truth survival, idempotency, quality, performance |
| `test_api_integration.py` | 12 | FastAPI endpoints (Docpluck App service) |
| `test_benchmark.py` | 10+ | Ground truth regression, idempotency, consistency |

Run the test suite:

```bash
cd docpluck && pip install -e ".[dev]" && pytest tests/ -v
```

---

## Phase 1: DOCX and HTML Extraction (v1.3.0)

**Methodology:** Port Scimeto's battle-tested DOCX/HTML extraction (in production since Dec 2025) to Python. Validate with a ground-truth passage set matching the PDF benchmark methodology (rapidfuzz `partial_ratio >= 90%`).

### Library Choices

| Format | Engine | License | Why |
|--------|--------|---------|-----|
| **DOCX** | mammoth 1.12.0 | BSD-2 | `convert_to_html()` preserves Shift+Enter soft breaks; `extract_raw_text()` loses them. Lightweight (1 dep: cobble). |
| **HTML** | beautifulsoup4 4.14.3 + lxml 6.0.2 | MIT + BSD-3 | Highest text recall (0.994) in benchmarks; lxml parser is 1.5–3× faster than html.parser with excellent error recovery. |

**Rejected alternatives:**

| Library | Why rejected |
|---------|--------------|
| `python-docx` | Only paragraph-level access; no soft-break handling |
| `docx2txt` | Effectively abandoned; flat string output |
| `docx2python` | Strong alternative but adds complexity; mammoth is battle-tested |
| `pypandoc` | Requires pandoc binary (deployment friction) |
| `unstructured` | Heavy dependency footprint, wrong optimization target (LLM/RAG) |
| `BeautifulSoup.get_text()` | [Cannot distinguish block/inline](https://bugs.launchpad.net/bugs/1768330) — produces `"ChanORCID"` merges |
| `inscriptis` | Focus on visual layout fidelity; our custom walker is simpler |
| `trafilatura` | Content extractor — would strip references and supplementary material |
| `html2text` | Outputs Markdown, which interferes with downstream regex matching |
| `selectolax` | Faster but has same block/inline limitation as BS4's `get_text()` |

### Critical Bug: the "ChanORCID" Regression

The HTML tree-walk must insert a space before **and** after every inline element. Without the pre-space, adjacent inline elements merge:

```html
<span>Chan</span><span>ORCID</span>
```

becomes `"ChanORCID"` — a real bug that went undetected in Scimeto production for weeks. The docpluck port is specifically regression-tested (`test_chan_orcid_regression`) against this failure mode.

### Block vs. Inline Element Handling

| Element type | Separator | Tags |
|--------------|-----------|------|
| **Block** | Newline before/after | `p div h1-h6 li tr td th header footer section article blockquote address dl dt dd fieldset legend table pre hr main nav aside` |
| **Inline** | Space before/after | everything else (a, span, em, strong, b, i, sup, sub, …) |
| **`<br>`** | Literal `\n` | Special case |
| **Ignored** | Stripped before walk | `script style meta link head noscript svg object embed iframe` |

### Whitespace Normalization (7-step cleanup)

Applied after the tree-walk to match Scimeto's production output:

1. `\r\n` → `\n`, `\r` → `\n`
2. Vertical tab, form feed, U+0085, U+2028, U+2029 → `\n`
3. Unicode spaces (NBSP, en/em/thin/hair/ideographic, BOM) → ASCII space
4. Collapse `[ \t]+` → single space
5. Strip trailing spaces on lines
6. Strip leading spaces on lines
7. Collapse `\n{3,}` → `\n\n`, then `.strip()`

### Ground Truth: 15 Statistical Passages

Mirrors the PDF benchmark: the exact kinds of patterns downstream consumers (ESCIcheck, MetaESCI) need to match after extraction.

Examples:
- `r(261) = -0.73, 95% CI [-0.78, -0.67], p < .001`
- `F(2, 58) = 12.15, p < .001, eta2 = .30`
- `t(98) = 2.15, p = .034, d = 0.43`
- `chi2(2, N = 250) = 8.42, p = .015`
- `OR = 2.34, 95% CI [1.45, 3.78], p = .001`

**Results:**

| Format | Passages | Match rate | Method |
|--------|:--------:|:----------:|--------|
| DOCX | 15/15 | **100%** | `mammoth` → `html_to_text()` |
| HTML | 15/15 | **100%** | `beautifulsoup` (lxml) tree-walk |

All passages survive extraction **and** academic normalization (smart quotes, ligatures, Unicode spaces all normalized correctly).

### Quality Scores

DOCX and HTML scores are equal to or higher than PDF scores because:

- No column-interleaving artifacts (DOCX/HTML don't have physical column layout)
- No ligature corruption (source already uses canonical characters in most cases)
- No SMP font issues (no PDF font encoding layer)
- No soft-hyphen invisibles (unless authored that way)

| Format | Synthetic fixture score | Confidence | Garbled chars |
|--------|:-----------------------:|:----------:|:-------------:|
| DOCX | ≥80 | high | 0 |
| HTML | ≥80 | high | 0 |

### Performance

| Operation | Typical | Notes |
|-----------|:-------:|-------|
| `extract_docx()` — small fixture | < 100ms | mammoth conversion + tree-walk |
| `extract_html()` — small fixture | < 50ms | lxml parse + tree-walk |
| Normalization | < 1ms | Same as PDF (text-level only) |

### Idempotency

`normalize_text(normalize_text(x)) == normalize_text(x)` verified for both DOCX and HTML output at all three normalization levels.

### Known Limitations

1. **OMML equations in DOCX**: Mammoth silently drops Office Math objects. Rare in social science (stats are usually plain text) but critical to know for STEM papers with equation-embedded results.
2. **Tracked changes in DOCX**: Only deleted paragraphs are handled minimally by mammoth. Documents with extensive tracked changes may include stale content.
3. **No page counting**: `pages` is `None` for DOCX and HTML. DOCX has no intrinsic page concept without rendering; HTML is unpaginated.
4. **Memory for large DOCX**: Mammoth uses 3–5× file size in peak memory. Not a concern for single-file processing but worth noting for batch pipelines on memory-constrained workers.

---

## Phase 2: Real Corpus and Cross-Format Benchmarks (v1.3.0)

The Phase 1 tests above use synthetic fixtures. Phase 2 exercises the real DOCX extractor on a private 24-file validation corpus and cross-validates against the PDF extractor using bidirectional format conversion (DOCX↔PDF via Microsoft Word, PDF→DOCX via `pdf2docx`).

> The Phase 2 benchmark scripts and per-file results are **maintained privately** because they reference specific academic papers in an internal corpus. Results below summarize aggregate metrics from the latest run.

### Result 1: DOCX Corpus (validation suite, 24 files)

20 real academic papers in DOCX format, plus 4 intentionally corrupted edge cases (truncated, random bytes, invalid ZIP).

| Metric | Result |
|--------|:------:|
| Real papers extracted | **20 / 20** |
| Corrupted files correctly rejected | **4 / 4** |
| Avg quality score | **100.0 / 100** |
| High-confidence extractions | **20 / 20** |
| Garbled detected | **0** |
| Total chars extracted | **1,495,519** |
| Total time | **45.6 s** (avg 2.3 s/file) |

**File size range:** 33 KB – 18 MB. The largest file (`33_FacialSocialMediaCreators.docx`, 18 MB) extracted successfully at 167,690 chars.

**Verdict:** Mammoth + `html_to_text` handles the full range of real academic DOCX files without a single failure, garble, or quality degradation.

### Result 2: DOCX → PDF Cross-Format Parity (20 files, via Word COM)

Each DOCX is extracted with `extract_docx()`, then converted to PDF via Microsoft Word (`docx2pdf` COM automation), then the PDF is extracted with `extract_pdf()`. Both outputs are normalized (academic level) and compared.

| Metric | Result |
|--------|:------:|
| Files compared | **20 / 20** |
| Avg similarity (`rapidfuzz.token_set_ratio`) | **98.8%** |
| Min similarity | **97.6%** |
| Avg char ratio (PDF/DOCX) | **1.02** |
| DOCX quality (all files) | 100 / 100 (high) |
| PDF quality (all files) | 100 / 100 (high) |

**Interpretation:** When given the exact same content, `extract_docx()` and `extract_pdf()` produce text that is **>97% identical** by fuzzy word-set matching, with char counts within **2%** of each other. The two extraction paths have format parity — the differences are whitespace and reading-order minutiae, not content loss.

One file (`35_EmpathyConflictingFeedback.docx`) showed a char ratio of 1.24 because Word rendered embedded figures into the PDF with extracted caption text; this is Word adding content, not DOCX losing content. Similarity was still 98.2%.

### Result 3: PDF → DOCX Reverse Cross-Format Parity (8 files, via pdf2docx)

8 PDFs spanning APA, Vancouver, AMA, Harvard, IEEE, Nature citation styles are extracted with `extract_pdf()`, converted to DOCX via `pdf2docx` (pure Python, layout-based reconstruction), then extracted with `extract_docx()`.

| Metric | Result |
|--------|:------:|
| Files compared | **8 / 8** |
| Avg similarity | **91.2%** |
| Min similarity | **63.3%** |
| Avg char ratio (DOCX/PDF) | **0.932** |
| PDF quality (all files) | 100 / 100 (high) |
| DOCX quality (all files) | 100 / 100 (high) |

**Per-file results:**

| File | Sim % | Char ratio | Notes |
|------|:-----:|:----------:|-------|
| chan_feldman_2025_cogemo.pdf | 97.7 | 1.00 | Clean APA |
| ip_feldman_2025_pspb.pdf | 97.1 | 0.99 | Clean APA |
| chen_2021_jesp.pdf | 95.3 | **0.63** | pdf2docx dropped ~50k chars (tables/figures) |
| bmc_med_1.pdf | 97.6 | 1.01 | Clean Vancouver |
| jama_open_1.pdf | 97.0 | 0.99 | Clean AMA |
| bjps_1.pdf | **63.3** | 0.91 | pdf2docx reading-order scramble |
| ieee_access_2.pdf | 99.6 | 0.98 | Excellent |
| nat_comms_1.pdf | 82.2 | 0.95 | Minor reading-order drift |

**Interpretation:** The two outliers (`chen_2021_jesp.pdf` char ratio 0.63, `bjps_1.pdf` similarity 63.3%) are **pdf2docx reconstruction failures**, not docpluck extraction failures. `pdf2docx` is a layout-based PDF→DOCX converter and struggles with:

- Complex multi-column layouts with figures (chen_2021_jesp)
- Unusual reading order or multi-zone pages (bjps_1)

Both PDF and DOCX extractors in docpluck scored **100 / 100** quality on their respective inputs for every file. The asymmetry lives entirely in the third-party conversion tool, not in our extractors.

### What Phase 2 Proves

1. **DOCX extraction matches PDF extraction quality** when given equivalent content (98.8% avg similarity).
2. **DOCX extraction is robust** across the full range of real academic files (20/20 success, 0 garbled, 100/100 avg quality).
3. **Error handling is correct** — all 4 corrupted files fail cleanly without crashing the extractor.
4. **The cross-format asymmetries are in the conversion tools, not docpluck** — both docpluck extractors consistently produce 100/100 quality output.

---

## Phase 3: MetaESCI Regression Benchmark (200-DOI frozen corpus, v1.3.1)

Extraction-only half of the ESCImate → Docpluck migration Phase C.3 shootout. Runs docpluck against a 200-DOI frozen MetaESCI regression corpus (seed=42) and collects extraction + normalization + residual-artifact metrics. The corpus and runner live in a private research repo.

### Results (v1.3.1, 2026-04-11) — all 9 criteria PASS

| Metric | Result |
|---|:---:|
| Files processed | **200 / 200** |
| Extraction crashes | **0** |
| High-confidence extractions | **200 / 200** (100%) |
| Avg quality score | **99.95 / 100** |
| Total chars extracted | **12,172,028** |
| Wall time | **73.4s** (avg 262ms/file) |
| SMP recovery triggered | 1 file (succeeded) |
| Garbled detected | **0** |

### Statistical patterns recovered

| Pattern | Total | Files |
|---|---:|---:|
| `p` values | 5,663 | 181 / 200 |
| `t(df) = x` | 1,161 | 99 / 200 |
| `F(df1, df2) = x` | 1,192 | 91 / 200 |
| `r(df) = x` | 157 | 24 / 200 |
| `chi2(df)` | 173 | 36 / 200 |
| Cohen's `d` | 743 | 73 / 200 |
| `eta2` | 915 | 67 / 200 |
| 95% CIs | 442 | 26 / 200 |
| Greek chars | 293 | — |

### Residual artifacts (all zero in v1.3.1)

| Artifact | v1.3.0 | v1.3.1 |
|---|:---:|:---:|
| U+FFFD | 0 | 0 |
| Soft hyphens | 0 | 0 |
| NBSP | 0 | 0 |
| Remaining ligatures | 0 | 0 |
| Unicode minus signs | 0 | 0 |
| Dropped decimal candidates | 21 (3 files) | **0** |
| Stat linebreak survivors | 3 (1 file) | **0** |

### What v1.3.1 fixed

The v1.3.0 baseline surfaced three real gaps. All three are addressed in v1.3.1.

1. **A1 column-bleed extension.** PSPB multi-column layouts produce patterns like `p\n\n01\n\n01\n\n= .28` where `01` lines are column-bleed fragments. The existing `p\s*\n\s*[=<>]` rule only handled whitespace between `p` and `=`. Two new rules tolerate up to 4 short digit-only fragment lines — one for `p\n...\n=`, one for `p =\n...\n value`. They run *before* the simple `p =\n digit` rule so the first fragment isn't mis-joined.

2. **A2 widening.** A2's threshold `val > 1.0` rejected `p = 01` (float value 1.0). Changed to `val >= 1.0`; the `\d{2,3}` prefix still prevents touching `p = 1`. The lookahead was also extended to accept a sentence-ending `.` but still reject genuine decimals like `p = 15.8` (via `\.(?!\d)`).

3. **Quality scorer corruption signal.** The PSS Reviewer Acknowledgment file is a valid 11K-char list of 600 reviewer names — zero prose, zero corruption, but low common-word ratio. v1.3.0 flagged it as garbled. v1.3.1 requires an independent corruption signal (U+FFFD / high non-ASCII / ≥20 ligatures / text < 500 chars) before flagging garbled. Real column-merge garbage still trips the signal (always retains ligatures from extraction); legitimate non-prose documents do not.

### Verdict

**v1.3.1: all 9 criteria PASS.** 200/200 files, 100% high confidence, avg quality 99.95/100, zero garbled, zero residual artifacts across the entire MetaESCI corpus. The `metaesci_regression` gate in Phase C.3 is now clear.

---

## Phase 4: Table & Figure Extraction (v2.0 — preliminary)

Smoke fixture corpus only (12 PDFs, hand-picked for category coverage). Formal TEDS / cell-exact-match benchmarks deferred to v2.1 (see `TODO.md`).

### Detection

| Category | Fixtures | All detect ≥ expected (±2)? |
|---|---|---|
| APA lineless | 4 | ✓ |
| Lattice (full-grid) | 4 | ✓ |
| Nature minimal-rule | 2 | ✓ |
| Figure-heavy | 2 | ✓ |

The smoke test asserts only that detected counts fall within ±2 of the manifest's expected counts — heuristic variance is expected at this stage; calibrated counts are recorded in `tests/fixtures/structured/MANIFEST.json`.

### Hard guarantees verified by smoke

- `extract_pdf_structured(pdf_bytes)` never raises — graceful degradation to empty `tables=[]`, `figures=[]` on extraction failures.
- Every `kind="structured"` table emits non-empty cells, non-null HTML, and a confidence ∈ [0.4, 0.95].
- Every `kind="isolated"` table has empty cells, null HTML, null confidence, and non-empty `raw_text`.
- `extract_pdf()` output is byte-identical to v1.6.x on all 12 fixtures (snapshot-based).

### Deferred to v2.1

Hand-labeled HTML ground truth + TEDS / cell-exact-match metrics on a 30-40 PDF APA-psych corpus. Target: TEDS > 0.80 on the APA-psych slice.
