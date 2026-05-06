# Structured-extraction smoke fixtures

This directory does NOT contain PDF files. PDFs are gitignored repo-wide.

The fixture corpus is referenced via `MANIFEST.json`, which lists each
fixture by category, expected table/figure counts, and `source_path` —
a path relative to `~/Dropbox/Vibe/` pointing at the real PDF in the
local Dropbox corpus (typically under
`MetaScienceTools/PDFextractor/test-pdfs/<style>/<filename>.pdf`).

Tests load PDFs via `MANIFEST.json` lookups. When a `source_path` is
not available on the running machine (CI, fresh clone, missing
Dropbox), the corresponding test SKIPs cleanly — same pattern as
`tests/conftest.py`'s `pdf_available()` helper for the existing
extraction tests.

## Coverage targets

- 4 lattice (full-grid) tables: 2× Elsevier-like (Springer/BMC), 1× IEEE, 1× JAMA
- 4 APA-style lineless tables (descriptives, regression, etc.)
- 2 Nature-style minimal-rule tables
- 2 figure-only fixtures (no tables, ≥1 figure with caption)
- 1 negative case (no tables, no figures, no captions)

Total target: ~12-15 fixtures.

## Why no PDFs committed

This repo is public on GitHub under MIT license. Closed-access journal
PDFs cannot be redistributed. Per project policy: never commit `*.pdf`
to docpluck or any other public sister repo.
