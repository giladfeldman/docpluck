
## CHANGELOG-documented public-API names must be in `__all__` (caught 2026-05-07, v2.0.0 release)

**What:** v2.0.0 CHANGELOG line "`Cell, Table, Figure, StructuredResult` TypedDicts and `TABLE_EXTRACTION_VERSION` re-exported from top-level `docpluck`" was inaccurate — `Cell` was importable via `docpluck.tables.Cell` but not from top-level `docpluck`. Caught by /ship Phase 3 cleanup against `docpluck.__all__`.

**Why:** When implementing a new public-surface CHANGELOG entry, it's easy to write the docs from intent ("we expose Cell, Table, Figure...") then only re-export the ones actually used by the orchestrator (extract_pdf_structured uses Table + Figure but doesn't return Cell directly — so Cell got missed in the import line).

**Fix:** Added `Cell` to `from .tables import` and to `__all__`. Added regression test `tests/test_v2_top_level_exports.py` asserting every CHANGELOG-documented v2.0 name is both importable AND in `__all__`.

**How to detect:**
1. After writing a CHANGELOG entry that mentions "re-exported from top-level <pkg>", run:
   `python -c "import <pkg>; print(set(<pkg>.__all__) ^ {<documented names>})"`
2. The symmetric difference should be empty (or only contain the legitimate non-public names).
3. The `tests/test_v2_top_level_exports.py` regression test is the durable version of this check.

## Hardcoded version-string assertions break every release-bump (caught 2026-05-09, v2.1.0 release)

**What:** v2.1.0 release bumped `SECTIONING_VERSION` 1.1.0 → 1.2.0 and `NORMALIZATION_VERSION` 1.6.0 → 1.7.0. Four tests had the OLD version strings hardcoded as bare equality assertions:
- `tests/test_sections_version.py::test_sectioning_version_is_v110` — `assert SECTIONING_VERSION == "1.1.0"`
- `tests/test_sections_public_api.py::test_sections_namespace_exports` — `assert SECTIONING_VERSION == "1.1.0"`
- `tests/test_cli_sections.py::test_cli_sections_json_output` — `assert payload["sectioning_version"] == "1.1.0"`
- `tests/test_d5_normalization_audit.py::TestVersionBumps` — `assert NORMALIZATION_VERSION == "1.6.0"` AND `assert report.version == "1.6.0"`

Plus three golden snapshot files (`tests/golden/sections/*.json`) had the version baked in as a JSON field, requiring `DOCPLUCK_REGEN_GOLDEN=1` to refresh.

**Why:** Each version-pin test was deliberately written to verify the constant is at the version the contributor expected — defensible as a tripwire. But that means EVERY release bump fails the full test suite until the pins are updated. The current pattern is a tax on every release rather than a meaningful invariant.

**Fix:** Updated all six call sites + 3 golden files to the new version. Renamed `test_sectioning_version_is_v110` → `test_sectioning_version_is_v120` so the function name doesn't lie about the assertion.

**How to detect (pre-tag):**
1. Before running the full suite post version-bump, grep the test tree:
   `grep -rn 'SECTIONING_VERSION\|NORMALIZATION_VERSION\|sectioning_version\|normalization_version' tests/ | grep -E '"[0-9]+\.[0-9]+\.[0-9]+"'`
2. Every match is a candidate for update. Update them in the same commit as the version bump so the release commit stays atomic.

**How to detect (durable):** Add a test in v2.2.0+ that asserts `SECTIONING_VERSION == docpluck.sections.SECTIONING_VERSION` (self-referential, never breaks) and replaces the hardcoded-version pin tests entirely. Deferred for now — the cost of updating 6 sites once per minor release is low enough that this isn't worth the complexity yet.

## Pdftotext serializes right-column metadata as orphan single-line paragraphs mid-Introduction (caught 2026-05-14, v2.4.16 release)

**What:** Four papers across four publishers (xiao APA/T&F, amj_1 + amle_1 AOM, ieee_access_2 IEEE) showed front-matter metadata (acknowledgments, license blocks, "previous version" notes, supplemental-data sidebars, truncated affiliations, running headers) bleeding mid-body in the rendered .md. The leak is invisible to char-ratio + Jaccard verifiers, to the 26-paper baseline regression gate, and to a 30-line eyeball check.

**Why:** pdftotext's reading-order serialization linearizes a two-column article by emitting the left-column (Abstract → Introduction body) first, then the right-column / inter-column metadata. The metadata fragments end up inlined as standalone single-line paragraphs between body paragraphs of the Introduction. pdftotext typically separates them from the body paragraph above with only a single `\n` (no blank line), so a `\n\n`-bounded paragraph-level view of the text absorbs the leak into the body paragraph and never sees it as a separate unit.

**Fix:** New `P1_frontmatter_metadata_leak_strip` step in `normalize.py` (NORMALIZATION_VERSION 1.8.4) operating at the **LINE level** (not paragraph level — that was a draft mistake) and position-gated to `max(8000, len(text) // 6)` chars. Plus three globally-safe additions to P0 (`_PAGE_FOOTER_LINE_PATTERNS`): bare uppercase running header (`^[A-Z]{2,}(?:\s+[A-Z]{2,}){0,3}\s+et\s+al\.?$`), T&F supplemental-data sidebar boilerplate, and truncated `Department of <X>, University of$` affiliation. Multi-sentence acknowledgments / license / correspondence / previous-version blocks stay in P1 with the position gate because they CAN legitimately appear in the late `## Acknowledgments` section.

**How to detect (next time):**
1. The leak shape: a single physical line (often very long — 200–700 chars), bounded by `\n` from a body paragraph above and `\n\n` from the next body paragraph below, that starts with a metadata-y opener.
2. Grep the rendered .md mid-body for: `^We (?:wish to )?thank `, `^Supplemental data for this article`, `^Department of [A-Z].*, University of\s*$`, `^[A-Z]{3,} et al\.?$`, `^This work is licensed under (a |the )?Creative Commons`, `^A previous version of this article was (?:presented|published)`, `^Correspondence concerning this article`.
3. **Never apply position-gated strips to the bare running-header class** — it recurs at every page break (`RECKELL et al.` shows up at 3% AND 18% of `ieee_access_2`'s rendered .md). Globally-safe patterns go in P0; only patterns with false-positive risk in the late Acknowledgments / Affiliations go in P1.

## Real-PDF regression tests must drive through the public library entrypoint, not the helper (caught 2026-05-14, v2.4.16 release)

**What:** A natural first instinct when writing the regression test for the P1 strip was to call `_strip_frontmatter_metadata_leaks(text)` directly with synthesized strings like `"Body.\n\nWe wish to thank X for feedback.\n\nBody 2."`. The handoff's rule 0d says every fix ships with a `*_real_pdf` test that exercises the **public** library entry point on an **actual** PDF fixture.

**Why:** The contract test against the helper passed in isolation, but a real pdftotext rendering of the same PDF revealed the leak appears separated by only a single `\n` (not `\n\n`), so the helper's paragraph-level view didn't isolate the leak. The contract test was a false-positive PASS: helper-correct, library-broken. The discovery only came from re-rendering an actual PDF and grepping the .md.

**Fix:** Per skill rule 0d, the regression test file is named `test_*_real_pdf.py` and uses `render_pdf_to_markdown(Path('../PDFextractor/test-pdfs/<style>/<paper>.pdf').read_bytes())` to drive the full pipeline. Contract tests with synthetic strings are useful as helpers but never substitute for a real-PDF regression test. Use `pytest.skip` when the fixture is unavailable locally (PDFs are gitignored per memory `feedback_no_pdfs_in_repo`).

**How to detect (next time):** If `bugs_fixed` in run-meta references a normalization-pipeline defect, grep the new tests for `render_pdf_to_markdown\|extract_pdf\b` AND `test-pdfs/` — a fix without that combination is a synthetic-only test and won't catch real pdftotext output quirks.
