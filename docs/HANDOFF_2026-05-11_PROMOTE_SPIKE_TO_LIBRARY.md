# Handoff — Promote splice-spike fixes into the docpluck library + app

**For:** A fresh Claude session whose sole goal is to **port the iter-23 through iter-34 spike fixes into the `docpluck` library**, release a new version, and bump the PDFextractor app to consume it. This is a release-engineering task, not a heuristics-tuning task.

**Branch:** `main` at `9ee7cf5` (handoff doc commit). Working tree clean. **253 spike tests passing**; library tests separately green. Two-repo architecture: `docpluck/` (this repo, public, MIT) and `PDFextractor/` (separate repo `docpluckapp`, private SaaS).

---

## TL;DR

- **The spike works great** — 26 papers render beautifully end-to-end. See [HANDOFF_2026-05-11_table_rendering_iteration_8.md](./HANDOFF_2026-05-11_table_rendering_iteration_8.md) for the quality outcomes.
- **None of it is in the library.** The library still ships v2.1.0; the app's `requirements.txt` still pins `v2.1.0`; production gets none of the iter-23–34 improvements.
- **This handoff is the plan to fix that.** Port ~8 functions + 3 pattern lists from `docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py` into `docpluck/normalize.py`, `docpluck/sections/`, and a new `docpluck/render.py`. Bump version to v2.2.0. Bump the app's git pin. Re-deploy.

Time estimate: **1 full session (~3-5 hours)** for a careful, well-tested port + release + deploy verification. Most of the time is in test migration and the release-flow checklist, not the actual code copying.

---

## Why this matters

The spike's `render_pdf_to_markdown(pdf_path)` is the single best PDF-to-markdown renderer for academic papers I've seen in this codebase — it handles 26 diverse papers (Nature, JAMA, AOM, Sage, Chicago, Royal Society, IEEE, APA, ASA) and produces output that reads cleanly top-to-bottom in a markdown viewer.

**The PDFextractor app currently calls `extract_pdf` (raw text) + `normalize_text` + `extract_sections`** — but the normalization passes that strip banners/footers/TOC junk and the section detector's title-rescue / compound-heading-merge / numbered-subsection-promotion are all spike-only. The app's `.md` download endpoint (if it exists) or any user-facing rendered output will look notably worse than the spike does.

After this port:
- Every docpluck user (PyPI consumers + the PDFextractor app + future apps) gets the iter-23–34 quality improvements automatically.
- The app gains an optional `render_pdf_to_markdown` public API for a "Download as Markdown" UX.
- The spike file `splice_spike.py` becomes a thin demo / regression harness that imports from the library.

---

## Required reading before touching code

1. **[CLAUDE.md](../CLAUDE.md)** — particularly the "Two-Repo Architecture" + "Release flow (library → production)" sections. The release flow is the authoritative checklist; this handoff fills in the spike-specific details.
2. **[LESSONS.md](../LESSONS.md)** — L-001 through L-005, particularly:
   - L-001 (don't swap the text-extraction tool)
   - L-003 (don't use PyMuPDF / column_boxes() — AGPL)
   - L-004 (always normalize U+2212 → ASCII hyphen)
3. **[docs/HANDOFF_2026-05-11_table_rendering_iteration_8.md](./HANDOFF_2026-05-11_table_rendering_iteration_8.md)** — the iter-8 session summary; describes every function being ported and which paper class each one helps.
4. **[docs/TRIAGE_2026-05-10_corpus_assessment.md](./TRIAGE_2026-05-10_corpus_assessment.md)** — particularly the bottom "Promotion to library" section.
5. **`docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`** — the source of all the code being ported. ~3900 lines but only the helpers listed in the porting map below need to move.
6. **`docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`** — 253 tests; many can be migrated wholesale to `tests/` once the helpers move into library modules.

---

## Porting map: helper-by-helper

### A. Normalization-level (target: `docpluck/normalize.py`)

These passes operate on raw extracted text. They run BEFORE section detection and should be folded into `normalize_text()` — probably as opt-in via a new `NormalizationLevel.AGGRESSIVE` tier OR as auto-applied at the existing `NormalizationLevel.STANDARD` tier (decision below).

| Spike function | Spike pattern list | Lines |
|---|---|---|
| `_strip_document_header_banners` | `_HEADER_BANNER_PATTERNS` | ~60 |
| `_strip_toc_dot_leader_block` | `_TOC_DOT_LEADER_RE`, `_PURE_TOC_LEADER_RE`, `_TOC_HEADING_RE` | ~50 |
| `_strip_page_footer_lines` | `_PAGE_FOOTER_LINE_PATTERNS` | ~80 |
| `_fix_hyphenated_line_breaks` | — | ~20 |

**Design decision needed:** The spike runs these passes post-render (on the markdown). To move them into `normalize_text()`, they must run pre-render (on the raw text). The patterns are line-level so the conversion is mechanical — only the call site changes.

**Recommendation:** Add these as auto-applied in `NormalizationLevel.STANDARD` (the current default the app uses). Bump `NORMALIZATION_VERSION` from 1.7.0 → 1.8.0 to signal that cached results need regeneration. Add a `NormalizationReport` field documenting which patterns fired.

Edge case to watch: the spike runs `_strip_document_header_banners` ONLY in the document-header zone (before the first `## ` heading). When porting to `normalize_text()` (which runs BEFORE section detection adds headings), use the "first ~30 lines" heuristic instead.

### B. Section-level (target: `docpluck/sections/`)

These restructure headings. They run AT or AFTER section detection.

| Spike function | Spike pattern list | Lines | Target |
|---|---|---|---|
| `_merge_compound_heading_tails` | `_COMPOUND_HEADING_TAILS` | ~30 | `docpluck/sections/core.py` (post-process in `extract_sections`) |
| `_promote_numbered_subsection_headings` | `_NUMBERED_SUBSECTION_HEADING_RE` | ~60 | `docpluck/sections/core.py` |
| `_dedupe_h2_sections` | — | ~30 | `docpluck/sections/core.py` |

For `_merge_compound_heading_tails`: extend `_COMPOUND_HEADING_TAILS` to include the other JAMA structured-abstract headings (`OBJECTIVE`, `IMPORTANCE`, `DESIGN, SETTING, AND PARTICIPANTS`, `MAIN OUTCOMES AND MEASURES`, `INTERVENTIONS`). Currently it's just `CONCLUSIONS AND RELEVANCE` because that was the only real-world split observed; the library should be defensive against the others.

For `_promote_numbered_subsection_headings`: this emits `### N.N Title` h3 headings. Decide whether this is a SectionedDocument operation (creates new Section records with `SectionLabel.subsection`) or stays as a post-process markdown transformation. The cleaner library design is the former — promote them to first-class Sections with a parent reference.

Bump `SECTIONING_VERSION` to signal the API change.

### C. Title rescue (layout-channel) (target: `docpluck/sections/annotators/pdf.py` or new `docpluck/sections/annotators/title.py`)

These use `extract_pdf_layout` to identify the article title.

| Spike function | Spike pattern list | Lines |
|---|---|---|
| `_compute_layout_title` | `_TITLE_REJECT_PATTERNS` | ~120 |
| `_title_text_from_chars` | — | ~70 |
| `_apply_title_rescue` | — | ~80 |
| `_rescue_title_from_layout` | — | ~30 |
| `_is_banner_span_text` | `_BANNER_SPAN_PATTERNS` | ~40 |

**Design:** Add a new `docpluck/sections/annotators/title.py` annotator that runs on the layout channel and produces a synthetic `Section` with `SectionLabel.title` if a confident title is found. The text-channel section detector then knows to NOT sweep the title text into `## Abstract` (eliminating the post-process strip).

`_is_banner_span_text` and `_BANNER_SPAN_PATTERNS` are reusable across the layout channel — put them in `docpluck/sections/annotators/_banner.py` (private module) so both the title-rescue annotator and any future layout-aware passes can use them.

Critical: pdfplumber's `extract_words` default `x_tolerance=3` is unreliable for tight-kerned PDFs (JAMA, AOM). The char-level fallback `_title_text_from_chars` MUST be ported alongside `_compute_layout_title` — it's the difference between a usable title and `# EffectofTime-RestrictedEatingonWeightLoss` on JAMA papers. See auto-memory `feedback_pdfplumber_extract_words_unreliable.md`.

### D. JAMA Key Points sidebar (target: NEW `docpluck/sidebar.py` or `docpluck/sections/sidebars.py`)

| Spike function | Spike pattern list | Lines |
|---|---|---|
| `_reformat_jama_key_points_box` | `_KEY_POINTS_BLOCK_RE` | ~100 |

This is the only function that touches MARKDOWN output (emits a blockquote). It runs after `extract_sections` so it has the heading structure available.

**Design decision:** Should this run inside the library's section detector (and emit a Sidebar block in `SectionedDocument`), or stay as a markdown-render-time pass? Recommendation: detect during section parsing (so the structured output has it as a named block), then emit blockquote markdown only at render time.

The sentence-stitching logic (merge "compared with" / "daily calorie counting" across the sidebar wedge) is text-level; keep it but document why it lives in the section detector.

### E. Markdown render entry point (NEW: `docpluck/render.py`)

The spike's `render_pdf_to_markdown(pdf_path)` is the orchestrator. Port it to a new public function:

```python
# docpluck/render.py
def render_pdf_to_markdown(pdf_bytes: bytes, *, pdf_path: str | None = None) -> str:
    """Render a PDF as a complete markdown document.

    Pipeline:
      1. extract_pdf_structured → text + tables + figures.
      2. Layout-channel title annotator → # Title.
      3. extract_sections (uses normalized text + title annotation).
      4. Splice tables into section positions.
      5. Optional: reformat JAMA-style Key Points sidebar.
      6. Promote numbered subsections to ### N.N.
      7. Emit markdown with HTML <table> blocks.
    """
```

Also add it to `docpluck/__init__.py` exports and `docpluck/cli.py` so `python -m docpluck render foo.pdf > foo.md` works.

The PDFextractor app then calls `from docpluck import render_pdf_to_markdown` to add a `.md` download endpoint.

### F. Table-rendering helpers (already in spike)

Most of the spike's table-level helpers (`pdfplumber_table_to_markdown`, `_merge_continuation_rows`, `_strip_leader_dots`, `_is_header_like_row`, `_drop_running_header_rows`, `_merge_significance_marker_rows`, `_fold_suffix_continuation_columns`, `_fold_super_header_rows`, `_join_split_captions`, `_strip_orphan_caption_fragments_near_tables`, `_strip_redundant_caption_echo_before_tables`, `_strip_redundant_fragments_after_tables`, `_join_multiline_caption_paragraphs`, `_wrap_table_fragments`, `_dedupe_table_blocks`) belong in `docpluck/tables/render.py` (which already exists with `cells_to_html`). The current library `cells_to_html` is much more minimal than the spike's renderer — port the spike's logic, keeping the existing function signature where possible.

This is the LARGEST chunk of code to port (~1500 lines). Plan a separate iteration for table-render porting if the scope grows.

---

## Library files NOT to touch (safety list)

| File | Reason |
|---|---|
| `docpluck/extract.py` | Text-channel extractor (pdftotext). DO NOT swap text-extraction tools — see L-001. |
| `docpluck/extract_layout.py` | Layout-channel extractor (pdfplumber). The spike calls this; don't modify its default `x_tolerance`. |
| `docpluck/extract_pdf_file` | Public API; stable signature. |
| `docpluck/figures/` | Figure extraction; orthogonal to spike work. |
| `docpluck/tables/camelot_extract.py` | Camelot is the table source — DO NOT swap. Auto-memory `project_camelot_for_tables.md`. |
| `docpluck/extract_docx.py`, `docpluck/extract_html.py` | DOCX / HTML paths; unaffected by spike. |

---

## Test migration plan

The spike has **253 unit tests** in `test_splice_spike.py`. They are organized into clearly-labelled blocks per iteration (Iter-23 through Iter-34). Migration:

1. **Per spike helper that moves**: copy the corresponding test block into `tests/test_<target_module>.py`, change the `from splice_spike import _x` line to `from docpluck.<target_module> import x` (drop the underscore prefix where the function becomes part of the public-ish surface), run the tests, fix any import or path adjustments.

2. **Integration tests** — the 26-paper corpus rendering can become a slow integration test under `tests/test_render_pdf_to_markdown.py`. Skip it in regular CI (mark with `@pytest.mark.slow`); run it as a release-gate before tagging.

3. **Tests to KEEP in the spike** — none. After porting, `splice_spike.py` becomes a thin demo/CLI wrapper around `docpluck.render.render_pdf_to_markdown`. The 253 test cases all move to `tests/`.

Expected test count after port: ~253 + existing library tests (~check `pytest --collect-only -q | tail -1` on the library).

---

## Release-flow checklist (from CLAUDE.md, with this-port specifics)

Follow [CLAUDE.md "Release flow (library → production)"](../CLAUDE.md) exactly. Specifics for this release:

1. **Make + commit changes in this repo.** Bump version triple consistently:
   - `docpluck/__init__.py::__version__` 2.1.0 → **2.2.0**
   - `pyproject.toml::version` 2.1.0 → **2.2.0**
   - `docpluck/normalize.py::NORMALIZATION_VERSION` 1.7.0 → **1.8.0** (banner/footer/TOC strip changed)
   - `docpluck/sections/__init__.py::SECTIONING_VERSION` (current value) → bump minor (compound-heading-merge + numbered-subsection promotion + title-rescue annotator)
   - `docpluck/tables/__init__.py::TABLE_EXTRACTION_VERSION` 2.0.0 → 2.1.0 if any table-render porting happens this release; else leave at 2.0.0.

2. **Update `docs/CHANGELOG.md`** with the iter-23 through iter-34 summary (copy from `HANDOFF_2026-05-11_table_rendering_iteration_8.md` "Headline outcomes").

3. **Push to `main`**, then tag: `git tag v2.2.0 && git push --tags`.

4. **(Optional) Publish to PyPI:** `python -m build && twine upload dist/*`. Skip if the app's git-pin install works without PyPI.

5. **In `PDFextractor/service/requirements.txt`, bump the `@v2.1.0` git pin to `@v2.2.0`.** Also update any frozen version examples in `PDFextractor/API.md`.

6. **Run `/docpluck-deploy` from the docpluck repo** — pre-flight check 4 verifies the pin matches. Most common failure: forgetting step 5; the deploy skill catches it.

7. **Post-deploy verification:**
   - Hit the production extraction endpoint with one of the 26 corpus PDFs.
   - Confirm the response includes the v2.2.0 normalization improvements (e.g. no `HHS Public Access` text on a PMC paper's output).
   - Verify the rendered markdown matches the spike's output bit-for-bit for that paper (allowing for minor formatting differences).

8. **Run `/docpluck-qa` to confirm parity with spike on a sample of corpus PDFs.** The QA skill should add a new "library-vs-spike parity" check; if not present, add one as part of this port.

---

## App-side updates

After bumping the git pin in step 5, the PDFextractor app gets the improvements transparently — `extract_pdf` + `normalize_text` + `extract_sections` produce better output without any app-side code changes.

**Optional app enhancements** to expose the new capabilities:

1. **`render_pdf_to_markdown` endpoint** — add a new FastAPI route in `service/app/main.py`:
   ```python
   @app.post("/render/pdf/markdown")
   async def render_pdf_md(file: UploadFile = File(...), ...):
       content = await file.read()
       from docpluck import render_pdf_to_markdown
       md = render_pdf_to_markdown(content)
       return PlainTextResponse(md, media_type="text/markdown")
   ```
   Frontend gets a "Download as Markdown" button on each extracted document.

2. **Display structured sections** — if the section detector now identifies more sections (Title, Key Points, Subsection N.N), surface them in the API response shape. Bump app version (currently 1.4.2 in main.py L52) to 1.5.0.

3. **Re-run ESCIcheck on production** — `/docpluck-qa` includes a 10-PDF ESCIcheck verification; after the v2.2.0 deploy, expect quality scores to go up on Nature / JAMA / replication papers.

---

## What success looks like

After this port:
1. `pytest` in `docpluck/` reports the full library test count (existing + ported) all green.
2. `pip install docpluck==2.2.0` (or git-pin to v2.2.0) gives a user the same .md output the spike produced for the 26 corpus PDFs.
3. The PDFextractor production endpoint, when hit with `nature/sci_rep_1.pdf`, returns extracted text whose section structure includes a `Title` section (was missing pre-v2.2.0).
4. The PDFextractor production endpoint, when hit with `ama/jama_open_1.pdf`, returns a markdown render (if the new endpoint was added) with a clean `> **Key Points**` blockquote and a stitched CONCLUSIONS sentence.
5. `splice_spike.py` reduces from ~3900 lines to ~200 lines (a thin CLI wrapper around `docpluck.render.render_pdf_to_markdown`).

---

## Risk register

- **Library tests may fail in unexpected places after porting `_strip_document_header_banners` into `normalize_text`.** The library has its own normalize tests that might assert specific text was preserved. Run `pytest docpluck/` early and often. Mitigation: thread the new banner-strip via a `NormalizationLevel.STANDARD` opt-out parameter while the library tests are being audited.
- **Section detector reorganization may shift section char_offsets.** Downstream consumers (the app) may rely on offsets being stable. The two-version bump (`SECTIONING_VERSION`) signals this; check app code for offset-dependent logic before releasing.
- **PyMuPDF / column_boxes() temptation.** While porting layout-channel code, the next session might think "let me improve the title detection by also reading column boxes" — DO NOT. See L-003 (AGPL). pdfplumber is the only allowed PDF library alongside pdftotext.
- **App's frozen-in-test PDF outputs.** `PDFextractor/service/tests/test_benchmark.py` likely has frozen expected outputs for specific PDFs. After bumping the docpluck pin, those expected outputs need regeneration — that's a normal part of the deploy cycle, but plan time for it.

---

## Concrete starter checklist for the next session

1. `git pull` in both repos (`docpluck/` and `PDFextractor/`).
2. Run `pytest` in `docpluck/` to confirm the library is green before changes.
3. Read this handoff + the iter-8 handoff + CLAUDE.md release-flow section.
4. Decide opt-in vs auto-applied for normalization-level changes.
5. Port **Section A (normalization-level)** first — smallest, most contained. Run library tests after each helper moves.
6. Port **Section B (section-level)** next.
7. Port **Section C (layout-channel title rescue)** — requires the new annotator architecture.
8. Port **Section D (JAMA Key Points)** — touch point with markdown rendering.
9. Port **Section E (markdown render entry point)** — wires everything together.
10. Defer **Section F (table-rendering helpers)** to a follow-up release if scope grows.
11. Run the full corpus integration test against the new library code; compare with spike output bit-for-bit (or near-bit-for-bit allowing for whitespace).
12. Execute the release-flow checklist exactly as in CLAUDE.md.
13. After deploy: run `/docpluck-qa` on production to confirm parity.

---

## One-line summary

> Port ~8 helpers + 3 pattern lists from `splice_spike.py` into `docpluck/normalize.py`, `docpluck/sections/`, and new `docpluck/render.py`. Bump version triple. Bump app's git pin. Run `/docpluck-deploy`. Verify production matches spike output. Time: ~3-5 hours. Risk: medium (test parity + section-detector API change).
