# Changelog

## [1.4.2] — 2026-04-11

### Added (MetaESCI D3/D5/D6/D7 follow-ups)

Addresses the non-blocking items MetaESCI filed in
`REQUESTS_FROM_METAESCI.md` ahead of the full 8,455-PDF batch. No
normalization semantics changed — `NORMALIZATION_VERSION` is still
`"1.4.1"`, so outputs byte-identical against v1.4.1 except for the
diagnostics changes below.

- **`docpluck.extract_pdf_file(path)`** — path-based wrapper around
  `extract_pdf(bytes)` that raises a clean `FileNotFoundError` with the
  offending path when the file is missing or is not a regular file (D7.1).
  Keeps the bytes API untouched.
- **`docpluck.extract_to_dir(paths, out_dir, level)`** + new
  **`ExtractionReport`** dataclass in `docpluck/batch.py` (D6). Batch
  runner that writes `<stem>.txt` (+ optional `<stem>.json` sidecar) for
  each input PDF and returns a serializable receipt with the library
  version, normalize version, git SHA, per-file method, timings, and
  failure reasons. `report.write_receipt(path)` persists it for
  downstream reproducibility pinning. Exceptions inside the loop are
  recorded, not raised — batch runs never abort on a single bad file.
- **`docpluck.get_version_info()`** + `docpluck/cli.py` (D3). New console
  entry point `docpluck --version` (also `python -m docpluck --version`)
  prints a single JSON line
  `{"version": ..., "normalize_version": ..., "git_sha": ...}`. Batch
  runners can call this once per run and stash the output next to
  results as a "bundle receipt".
- **`NormalizationReport.steps_changed`** (D7.2). New list alongside the
  existing `steps_applied`, containing only pipeline steps that actually
  modified the text. `steps_applied` is unchanged for backward compat;
  `to_dict()` now exposes both. Use `steps_changed` when you want to
  know what the pipeline *did* on a given input vs. what it *ran*.

### Fixed

- `docpluck/__init__.py` `__version__` was stale at `"1.3.1"` despite
  `pyproject.toml` and `NORMALIZATION_VERSION` both advancing to
  `"1.4.1"`. Now synced to `"1.4.2"`.

### Docs

- `docs/NORMALIZATION.md` — A5 section clarifies that
  `NormalizationLevel.academic` intentionally transliterates Greek
  statistical letters (η²→eta2, χ²→chi2, etc.) and points callers who
  need Greek preserved at `NormalizationLevel.standard` (D5).

### Unchanged

- `NORMALIZATION_VERSION` stays at `"1.4.1"`. No regex, no A-rule
  thresholds, no tokenization changed. Fresh batch runs against v1.4.2
  produce identical `data/results` to v1.4.1 given the same corpus —
  only diagnostic fields differ.
- All 227 pre-existing tests continue to pass. New tests added for
  `extract_pdf_file`, `extract_to_dir`, `steps_changed`, and the CLI.

### Deferred (requires MetaESCI repro data)

- **D1** (classify 4 + 54 dropped rows vs checkPDFdir) — needs the two
  A/B CSVs per subset that MetaESCI references but that currently only
  exist as a single merged CSV in their `data/results/subset/` tree.
- **D2** (one lost source per subset) — same.
- **D4** (A4 CI harmonization regex audit) — read-only audit done; see
  `REPLY_FROM_DOCPLUCK.md` for the preliminary hypothesis. No regex
  change until a real repro lands.

## [1.3.1] — 2026-04-11

### Fixed (normalization + quality scoring)

Three gaps identified by the v1.3.0 MetaESCI 200-DOI regression baseline, all
closed in this release. After the fixes, the same benchmark passes 9/9 criteria
(200/200 files, 100% high confidence, avg quality 99.95/100, zero residual
artifacts). No regressions in the 27 pre-existing tests or in the DOCX/PDF
cross-format benchmarks.

1. **A1 column-bleed extension.** PSPB multi-column layouts produce patterns
   like `p\n\n01\n\n01\n\n= .28` where `01` lines are column-bleed fragments.
   Two new A1 rules tolerate up to 4 short digit-only fragment lines — one for
   `p\n...\n=`, one for `p =\n...\n value`. They run *before* the simple
   `p =\n digit` rule so the first fragment isn't mis-joined. Regression tests
   in `tests/test_normalization.py::TestA1_ColumnBleed`.

2. **A2 widening.** A2's `val > 1.0` threshold rejected `p = 01` (float value
   1.0). Changed to `val >= 1.0`; the `\d{2,3}` prefix still prevents touching
   `p = 1`. The lookahead was extended to accept a sentence-ending period via
   `\.(?!\d)` but still rejects real decimals like `p = 15.8`. Regression tests
   in `tests/test_normalization.py::TestA2_DroppedDecimalV2`.

3. **Quality scorer — corruption signal required for garbled flag.** The
   v1.3.0 scorer flagged non-prose documents (reviewer acknowledgment lists,
   reference dumps) as garbled because it only looked at common-word ratio.
   v1.3.1 requires at least one independent corruption signal (U+FFFD / non-ASCII
   ratio > 20% / ≥20 ligatures / text < 500 chars) before flagging. Real
   column-merge garbage still trips the signal (always retains ligatures);
   valid non-prose content does not. Regression tests in `test_quality.py`.

### Changed

- `NORMALIZATION_VERSION` bumped from `"1.2.0"` to `"1.3.1"` so downstream
  consumers can detect the new pipeline. `NormalizationReport.version` reflects
  the change.
- `compute_quality_score()` result dict gains a new field
  `details.has_corruption_signal` (bool).
- Internal dropped-decimal benchmark detection regex tightened to match A2's
  own lookahead so diagnostic candidates align with what A2 actually fixes
  (prevents false positives like `p = 15.8` from column-merged table cells).

### Compatibility

- No public API changes. `extract_pdf`, `extract_docx`, `extract_html`,
  `normalize_text`, and `compute_quality_score` signatures are unchanged.
- All 211 pre-existing tests continue to pass. 16 new regression tests added
  (total 227).
- Verified no regressions on Scimeto/CitationGuard DOCX corpus (20/20 real
  papers extract at 100/100 quality) or cross-format parity (99.0% similarity
  on the DOCX→PDF spot check, identical to v1.3.0).

## [1.3.0] — 2026-04-10

### Added
- **Private benchmark suite** stress-testing extraction on a 24-file real-world DOCX corpus and bidirectional cross-format comparisons (DOCX↔PDF via Word, PDF→DOCX via `pdf2docx`). Results: 20/20 DOCX real files extracted at 100/100 quality, 98.8% avg DOCX→PDF similarity, format parity between `extract_docx` and `extract_pdf` confirmed. Scripts and per-file results live in a private research repo.
- **Phase 2 benchmark section** in `docs/BENCHMARKS.md` documenting the aggregate results.
- **Benchmark mode** in the `docpluck-qa` skill: triggered by "DOCX benchmark", "--benchmark-docx", "format parity", etc. Does NOT run during normal QA (5–15 min; launches Word).
- **DOCX extraction** via `extract_docx()` — uses `mammoth` to convert DOCX to HTML
  (preserving Shift+Enter soft breaks as `<br>` tags) then runs the same tree-walk
  used for native HTML. Ported from Scimeto's production code (running since Dec 2025).
- **HTML extraction** via `extract_html()` and `html_to_text()` — uses `beautifulsoup4`
  + `lxml` with a custom block/inline-aware tree-walk. Specifically regression-tested
  against the "ChanORCID" bug (adjacent inline elements merging text).
- **Optional dependency groups** in `pyproject.toml`:
  - `docpluck[docx]` adds mammoth
  - `docpluck[html]` adds beautifulsoup4 + lxml
  - `docpluck[all]` adds everything
  Core `pip install docpluck` still installs only pdfplumber for PDF support.
- **60 new tests** (46 HTML + 18 DOCX + 12 benchmark + corrections), bringing total to 211:
  - `tests/test_extract_html.py` — block/inline handling, ChanORCID regression,
    whitespace normalization, HTML entities, academic patterns
  - `tests/test_extract_docx.py` — mammoth integration, soft breaks, smart quotes,
    statistical values, ligature normalization integration, error handling
  - `tests/test_benchmark_docx_html.py` — 15 ground-truth statistical passages survive
    extraction and normalization for both formats with rapidfuzz ≥ 90% matching.
    Idempotency, quality scoring, and performance verified.
- **FastAPI service updates** (`PDFextractor/service/app/main.py`):
  - File type detection (PDF, DOCX, HTML, HTM) with per-type magic-byte validation
  - Extraction routing to the correct engine
  - Response format adds `file_type` field; `pdf_hash` kept for backward compat
  - Health endpoint reports all engines and supported types
- **Documentation** updates to README, BENCHMARKS, and DESIGN covering the new formats,
  library choices, rejected alternatives, and known limitations (OMML equations,
  tracked changes, memory usage).

### Changed
- `extract_html` and `extract_docx` use lazy imports so the core library still works
  without the optional dependencies installed.
- Version bumped to 1.3.0.

### Known limitations (documented, not bugs)
- **OMML equations** in DOCX are silently dropped (mammoth limitation). Rare in social
  science where stats are written as plain text; affects STEM papers.
- **Tracked changes** in DOCX are only partially handled by mammoth.
- **No page counting** for DOCX/HTML — `pages` is `None` for non-PDF formats.

## [1.1.0] — 2026-04-06

### Added
- S6: Soft hyphen (U+00AD) removal — was silently breaking text search across 14/50 test PDFs
- S6: Full-width ASCII→ASCII (U+FF01-FF5E) — handles full-width digit/letter patterns
- S6: All Unicode space variants (U+2002-U+205F, U+3000, ZWJ/ZWNJ)
- A5: Greek statistical letters (η→eta, χ→chi, ω→omega, α→alpha, β→beta, δ→delta, σ→sigma, φ→phi, μ→mu)
- A5: Combined forms (η²→eta2, χ²→chi2, ω²→omega2) and all superscript/subscript digits
- A6 (new step): Footnote marker removal after statistical values ("p < .001¹" → "p < .001")
- 151 tests across 6 test files

### Fixed
- A1 now runs before S9 to prevent page-number stripping of statistical values split across lines
- Possessive quantifiers in all line-break joining regexes to prevent catastrophic backtracking

## [1.0.0] — 2026-03-15

Initial release. Extracted from the Docpluck academic PDF extraction service.

### Features
- `extract_pdf()` — pdftotext primary + pdfplumber SMP fallback
- `normalize_text()` — 14-step pipeline (S0-S9, A1-A5) at three levels: none/standard/academic
- `compute_quality_score()` — composite quality metric with garbled detection
- 122 tests across 6 test files
