# Changelog

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
