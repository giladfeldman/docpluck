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

151 tests across 6 files, all passing on Python 3.10-3.14:

| File | Tests | Coverage |
|------|:-----:|---------|
| `test_normalization.py` | 63 | All 15 pipeline steps (S0-S9, A1-A6), edge cases for each |
| `test_quality.py` | 10 | Score ranges, garbled detection, confidence levels |
| `test_edge_cases.py` | 30+ | Cross-project lessons (ESCIcheck, MetaESCI, PDFextractor, Unicode) |
| `test_extraction.py` | 15+ | Real PDFs, SMP recovery, 8 citation styles (skips if no poppler) |
| `test_api_integration.py` | 12 | FastAPI endpoints (Docpluck App service) |
| `test_benchmark.py` | 10+ | Ground truth regression, idempotency, consistency |

Run the test suite:

```bash
cd docpluck && pip install -e ".[dev]" && pytest tests/ -v
```
