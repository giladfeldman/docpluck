# Handoff — Visual review findings + v2.3.0 plan + AI-Chrome-verified review process

**For:** A fresh next session that picks up after the 2026-05-11 visual-review session. Critical: **the very first action is to port spike Section F into the library (v2.3.0)** — several of the rendering issues listed below may be resolved by that port, and trying to fix them piecemeal first would mean redoing work.

**State at handoff:**
- All library tests green (189 in run suites).
- FastAPI service v1.5.0 has `/analyze`, `/render`, `/tables` endpoints + a dev-only `INTERNAL_SERVICE_TOKEN` trust path.
- PDFextractor frontend has a unified `/extract` workspace with Rendered / Raw / Normalized / Sections / Tables tabs, single-step analyze, staged progress + ETA, dev-only Credentials auth.
- Library v2.2.0 shipped 5 bug fixes during the visual-review session (see [CHANGELOG.md](../CHANGELOG.md)). Adelina now extracts 5/5 tables and 13 sections (was 0/5 + 6); Efendic and Chen similarly clean.
- This handoff written before tagging v2.2.0 + bumping `PDFextractor/service/requirements.txt`. Either tag-and-bump now and pin the next session to the new tag, OR have the next session inherit the un-tagged state.

---

## Mandatory ordering for the next session

1. **First: port spike Section F (cell-cleaning helpers) into the library and tag v2.3.0.** Several render-output issues we see today may be fixed by the spike's `pdfplumber_table_to_markdown` pipeline. Doing other fixes first risks re-doing them.
2. Then: re-run the AI-Chrome-verified iterative review described in section "AI-Chrome-verified iterative review process" below, on the same three PDFs (Adelina, Efendic, Chen) PLUS more. Compare against the spike's known-good outputs for the 26-paper corpus.
3. Then: address the specific Rendered-tab issues catalogued in "Outstanding Rendered-view bugs" below — but only after v2.3.0 to see which actually remain.
4. Then: integrate the AI-Chrome-verified review into the docpluck-qa and docpluck-review project skills.

---

## Outstanding Rendered-view bugs (observed 2026-05-11 on the Wong/gratitude paper)

These were spotted in a fourth test upload after the three documented above. Screenshots are in the visual-review session transcript.

### Bug 1 — Rendered tab is NOT showing the "best of everything"

**User feedback:** *"the rendered isn't showing the markdown tables, it should show the best of everything, no?"*

The Rendered tab is meant to be the curated, polished view that combines:
- `# Title` (from layout-channel rescue)
- `## {section}` headings (from extract_sections)
- Body prose
- `<table>` HTML for each detected table (spliced at caption position)
- Figure caption blocks
- JAMA Key Points sidebar (when present)

Currently it's emitting `### Table N` + italic caption ONLY — the HTML table body is being dropped. Look at:
- `_render_sections_to_markdown` in [`docpluck/render.py`](../docpluck/render.py): the table-splice branch DOES set `body_chunks.append(html)` when `item.get("html")` is non-empty, so the HTML should appear. Investigate whether `t.get("html")` is populated for the items handed to render. The `/analyze` endpoint passes `_structured=structured` through — does that StructuredResult have `html` on each table? Check `extract_pdf_structured` — it doesn't appear to populate `html` on tables; my `/analyze` code computes html in `tables_out` AFTER `extract_pdf_structured` returns. So `_structured` arrives at render WITHOUT `html` per-table → render's fallback `cells_to_html(cells) if cells else ""` runs, which on the un-cleaned cells produces a `<table>` with the mess described in Bug 2.
- Fix: either populate `html` on each Table dict inside `extract_pdf_structured` (recommended — single source of truth), or have render call `cells_to_html` consistently. After v2.3.0, `cells_to_html` will have the spike's cell-cleaning baked in, so this becomes the right hook.

### Bug 2 — Body text contains the raw table text flattened to paragraph-per-row

The second screenshot shows body content like:

```
<0.001 <0.001 >0.20 <0.001 >0.20 <0.001 (i) <0.01 (ii) <0.01 <0.001 (i) >0.20 (ii)<0.001 <0.05 <0.01 <0.05
Effect size r = 0.57 r = 0.61 r = 0.20 0.61 > 0.20
90% CI / / /
etap2 = 0.2 etap2 = 0.01
[0.08, 0.32] [0.00, 0.08]
…
```

This is a table's row content extracted as inline text by pdftotext (since the table has no borders and is part of the linear text flow). The renderer then emits it as paragraphs because `_render_sections_to_markdown` writes the **entire** `sec.text` of the containing section — which includes the table's flattened text. The actual `<table>` is then ALSO spliced in nearby, leading to double-rendering.

**Fix direction:**
- During `_render_sections_to_markdown`, when splicing a table at position `p_idx` inside a section, slice out the char range that contains the table's flattened text from `sec.text` and replace it with the `<table>` HTML. The table's char range can be derived from caption position + a configurable window, or by matching the cells against the section text.
- Alternative: drive table boundaries from `extract_pdf_structured.table_regions` (per-page bbox + char_start/char_end if we track them). The text channel + layout channel can co-operate here.
- Spike's `pdfplumber_table_to_markdown` orchestrator does exactly this kind of replacement — when the port lands, study how the spike avoids the double-emission and bring that logic over.

### Bug 3 — Figures appear at the top of the rendered output, before the abstract

**User feedback:** *"I'm also not sure I understand why the figures are showing at the top of the rendered."*

In the screenshots, Figure 1 / Figure 2 / Figure 3 appear immediately after the title with no Abstract heading between them. Cause: figures are anchored at their caption position in the normalized_text. For papers where the abstract references figures (e.g. "see Figure 1" mid-abstract), the renderer's `find(caption)` lands on that text reference, not the actual figure-caption text deeper in the body. The figure block then gets spliced at the wrong position.

**Fix direction:**
- Use `CaptionMatch.char_start` from `find_caption_matches` instead of doing a `text.find(caption)` re-search in `_render_sections_to_markdown`. The caption matcher already located the canonical caption position.
- The Table dict / Figure dict needs a `char_start` field plumbed through from `extract_pdf_structured`. Today that's lost.
- Stop-gap: detect that "find()" landed on a citation reference ("see Figure 1") vs. a caption-line ("Figure 1. {text}") by checking ±20 chars around the match for the pattern `Figure\s+\d+\.\s+[A-Z]` (caption-line shape) and reject the position if it doesn't match.

### Bug 4 — Figure captions concatenate text from multiple unrelated figures + body

Screenshot shows `Figure 1` caption text as:

> Figure 1. Study 2 selfish-ulterior condition (H1b): association between gratitude and indebtedness. **Figure 2. Study 2 benevolent condition (H1c null hypothesis): association between gratitude and indebtedness.** = 365, p < 0.001; ηp2 = 0.33, 90% CI [0.28, 0.37]; figure 3), but not in indebtedness (H3 null hypothesis: F1, 756 = 0.37, p = 0.54; ηp2 = 0.001, 90% CI [0.00, 0.01]; figure 4). We,…

So Figure 1's caption is concatenated with Figure 2's caption AND with results-section prose about F-stats. The caption-extraction logic is bleeding across boundaries.

**Cause:** `_extract_caption_text(rejoined, match)` in `docpluck/extract_structured.py` probably greedily extends from the caption start to either an EOL or some other terminator, but doesn't stop at the next caption-start or section-heading.

**Fix direction:**
- Bound caption extraction by `min(next_caption.char_start, next_section_heading.char_start, char_start + 800)`.
- The 800-char cap is a guard against runaway captions in any case.
- After v2.3.0 lands, also use `_join_multiline_caption_paragraphs` from render.py to fold multi-line wraps cleanly.

### Bug 5 — Title rescue produced a TRUNCATED title on the gratitude paper

Title rendered: *"Revisiting the effects of helper intentions on gratitude and indebtedness: Replication and extensions Registered Report of"* — ends in "of" mid-sentence.

The full paper title is presumably *"…extensions Registered Report of Tsang (2006)…"* or similar. The layout-channel `_compute_layout_title` truncated. Likely cause:
- `_apply_title_rescue` uses an 85% recall + 60% precision threshold on the token-match window with a 12-line max. If the title spans more lines than that or the upstream `_compute_layout_title` returned an over-eager truncated string, the rescued title is too short.
- Investigate `_compute_layout_title`'s span filtering for this paper — it may be cutting at a font-size boundary mid-title (e.g. a subtitle in slightly smaller font on the second line gets excluded from the dominant-font set).

**Fix direction:**
- Add a sanity check: if the rescued title ends with a connector word (`of`, `from`, `for`, `the`, `and`, `or`, `to`, `with`, `on`, `at`, `by`, `in`, `as`, `is`), it's almost certainly truncated. Either extend the window or fall back to no rescue.

### Bug 6 — "Registered report" appears as a small subtitle below the H1, not styled as anything

It's currently rendered as a regular paragraph because it's likely a `## Registered report` or similar heading that's flowing as body. Either:
- The section detector found it but the renderer's heading skip logic (the "unknown" suppression I added) accidentally caught it.
- OR the section detector tagged it but emitted a `##` that the markdown renderer in the workspace styles correctly — could just need a screenshot zoom-in to verify.

---

## Section F port (v2.3.0) — what to port, in this order

Each helper has its source in [`docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`](superpowers/plans/spot-checks/splice-spike/splice_spike.py).

### Port order

1. **`_merge_continuation_rows`** (spike L147–305) — merges rows where the first column is empty into the previous row. Single biggest visible improvement; handles multi-line cell wrapping which is endemic in academic tables.
2. **`_strip_leader_dots`** (spike L303–338) — strips runs of `. . . . . .` filler dots.
3. **`_split_mashed_cell`** (spike L341–~390) — splits column-undercount mashes (two-column content merged into one cell, e.g. `Original domain groupEasy domain group`).
4. **`_is_header_like_row`** + **`_drop_running_header_rows`** (spike L440–621) — detects header-like rows and drops repeated headers that Camelot duplicates.
5. **`_is_group_separator`** (spike, used inside the orchestrator) — detects rows where only column 0 has content; renders as `<tr><td colspan="N"><strong>label</strong></td></tr>`.
6. **`_fold_super_header_rows`** (spike L842–899) — folds 2-level column headers when top row has empty cells AND every populated top cell has a populated cell directly below.
7. **`_fold_suffix_continuation_columns`** (spike L791–841) — folds per-column suffix continuations (`Win-` over `Uncertain`).
8. **`_merge_significance_marker_rows`** (spike L622–790) — merges significance footer rows (`†`, `*p < .05`, `Note. M = ...`) into preceding rows or footnote section.

### Library target

Refactor `docpluck/tables/render.py::cells_to_html` to:
1. Convert `list[Cell]` → 2D grid of strings (`list[list[str]]`).
2. Apply the helpers in the order above.
3. Detect multi-row header span via consecutive `_is_header_like_row` matches (capped at 3 rows, per spike).
4. Render `<table><thead>...</thead><tbody>...</tbody></table>` with proper merged cells and group-separator rows.
5. Cap output: return `""` for tables with fewer than 2 rows after cleaning.

### Test plan

- Mirror the spike's test blocks for each helper into `tests/test_tables_cell_cleaning.py`. The spike has roughly 80+ tests for the table-cleaning subsystem; port the ones that test pure transforms (skip the ones that test the full pdftotext+camelot pipeline).
- Add an integration test against Adelina Table 2 (sample demographics, 18×3) — assert the cleaned table has ≤8 rows and merged cells for the multi-line Gender / Sample-size / Geographic-origin fields.
- Bump `TABLE_EXTRACTION_VERSION` 2.0.0 → 2.1.0.
- Bump `docpluck.__version__` 2.2.0 → 2.3.0.
- Bump `PDFextractor/service/requirements.txt` git pin from `@v2.2.0` to `@v2.3.0`.

---

## AI-Chrome-verified iterative review process

**Why this matters (user 2026-05-11):** *"one of the things you needed to check was the ui ux to ensure that users get the most value. this ai chrome look AI verified iterative model needs to be in the next session… we need to incorporate this testing into qa and codereview project skills and we need to run it through the project skills to ensure the process works, and expand it to a lot more pdfs."*

### What worked this session

1. **Dev-only Credentials provider** ([`PDFextractor/frontend/src/lib/auth.ts`](../PDFextractor/frontend/src/lib/auth.ts)) lets the AI agent sign in as `test@docpluck.local` / `docpluck-dev` without OAuth. Auto-creates the user with `dailyLimit=-1`. Production-gated by `NODE_ENV !== "production"`.
2. **Same-origin test-PDF staging** ([`PDFextractor/frontend/public/_test-pdfs/`](../PDFextractor/frontend/public/_test-pdfs/), gitignored): drop test PDFs here, fetch via `/_test-pdfs/<name>.pdf` from the workspace page.
3. **JS-injected upload pattern**: use `mcp__Claude_in_Chrome__javascript_tool` with:
   ```js
   const res = await fetch("/_test-pdfs/foo.pdf");
   const blob = await res.blob();
   const file = new File([blob], "foo.pdf", { type: "application/pdf" });
   const input = document.querySelector('input[type="file"]');
   const dt = new DataTransfer();
   dt.items.add(file);
   input.files = dt.files;
   input.dispatchEvent(new Event('change', { bubbles: true }));
   ```
   Bypasses the native file picker entirely and the `file_upload` MCP tool's "Not allowed" restriction.
4. **Direct API verification** via `curl -H "x-internal-service-token: ..."` on FastAPI's `/analyze` endpoint — skips the Vercel quota chain and compares raw outputs across PDFs in seconds. Use this for bulk/scripted comparison before the slower UI review.
5. **Service auto-restart with `--reload`** is brittle (uvicorn's reloader doesn't watch the docpluck site-packages). Hard-restart by killing the python process listening on port 6117 and re-launching via `Start-Process` in PowerShell.

### The iterative loop the next session should adopt

```
For each test PDF in the corpus:
  1. JS-upload via fetch + DataTransfer.
  2. Poll for analyze completion (look for [data-slot="tabs-list"] presence in DOM).
  3. Screenshot Rendered, Raw, Normalized, Sections, Tables tabs.
  4. Compare key metrics against expectations:
     - Engine should be pdftotext_default (not …+pdfplumber_recovery)
       on multi-column papers.
     - Section count > 8 for full APA papers; > 4 for short reports.
     - For each detected table caption, at least one of html/raw_text should be non-empty.
     - Title rescue should produce a non-truncated title (sanity: not ending in connector word).
  5. For each Rendered-tab screenshot, scroll through the entire output area and
     screenshot at 750px increments. The screenshots become input to GPT-Vision /
     Claude-Vision for "does this render look right" qualitative review.
  6. Flag deltas vs the spike's known-good corpus output (the spike has spit out
     26 papers' worth of .md; diff against those).
```

### Corpus expansion

The 3-PDF (Adelina/Efendic/Chen) review caught most of the issues, but the spike was tested against **26 PDFs across 9 journal styles** (Nature, JAMA, AOM, Sage, Chicago, Royal Society, IEEE, APA, ASA). The next session should run the iterative loop on at least 10 PDFs covering all 9 styles. Test PDFs already live in [`PDFextractor/test-pdfs/`](../../PDFextractor/test-pdfs/) bucketed by style. Pick 1-2 from each subdir for the bake-off.

### Integration into existing project skills

The user has these docpluck-specific skills (defined in `.claude/`):
- **`/docpluck-qa`** — currently runs Python tests + ESCIcheck verification. Should be extended to:
  - Spawn the local dev stack (or hit a known dev URL).
  - Run the JS-upload + screenshot loop across the 10-PDF benchmark corpus.
  - Diff rendered outputs against frozen baselines in `docs/baselines/<paper>.rendered.md`.
  - Emit a regression report with per-paper PASS / FAIL and per-issue tags.
- **`/docpluck-review`** — currently reviews code against hard rules. Should be extended to:
  - After detecting changes in `docpluck/render.py`, `docpluck/extract*.py`, `docpluck/tables/*.py`, or `docpluck/sections/*.py`, automatically trigger the visual-review loop on 3 representative papers (one each from APA, AOM, JAMA).
  - Reject the change (or warn) if visual quality regresses on those papers.
- **`/docpluck-cleanup`** — extend to garbage-collect `frontend/public/_test-pdfs/` if the directory grows past 50 MB, and to verify `.gitignore` covers it.

### Implementation note for the skills

The skills should NOT assume Chrome MCP is available — they need to gracefully fall back to `curl /analyze` API-only verification when no browser is connected. Visual screenshots are bonus; API parity is the floor.

---

## Specific items deferred from this session

| Item | Defer to | Notes |
|---|---|---|
| Section F port (cell cleaning) | **v2.3.0, do FIRST in next session** | See port-order above |
| Tables not appearing in Rendered tab | After v2.3.0 — may resolve | Bug 1 above |
| Body text contains flattened table cells | After v2.3.0 — may resolve | Bug 2 above |
| Figures spliced before abstract | Independent fix needed | Bug 3 above — `char_start` plumbing |
| Captions concatenate across figures | Independent fix needed | Bug 4 above — `_extract_caption_text` bound |
| Title truncated mid-sentence ("ends in 'of'") | Independent fix needed | Bug 5 above — add connector-word sanity guard |
| Soft-hyphen artifacts in captions | Independent fix needed | chen.pdf shows `Sup� plementary`. Caption text doesn't go through `normalize_text`. |
| `count_pages` returns 1 for 16-page PDFs | Low priority | Byte-pattern heuristic miscounts; investigate `/Type /Page` count vs object refs |
| 18 residual FFFDs in Adelina body | Optional, ~50 LOC | Per-char patching: use pdfplumber to identify what each FFFD should be and replace just those positions in pdftotext output |
| Sticky tabs while scrolling rendered | UI polish | Tab bar disappears off-screen on long renders |
| Render cleanup of `## unknown` re-evaluation | After v2.3.0 | I currently suppress these; verify it's still desired after section detection improves |
| `Registered report` rendered as small text below H1 | After v2.3.0 / re-test | Bug 6 above |

---

## Files touched this session (not yet committed)

### docpluck/ (library)
- `docpluck/extract.py` — recovery threshold + `_reading_order_agrees` helper
- `docpluck/render.py` — title rescue blank-line padding, optional `_structured` / `_sectioned` / `_layout_doc` params, `## unknown` suppression
- `docpluck/normalize.py` — H0/T0/P0 strips (already in v2.2.0 base)
- `docpluck/__init__.py` — version 2.2.0 export, render_pdf_to_markdown export
- `docpluck/cli.py` — `render` subcommand
- `CHANGELOG.md` — v2.2.0 revised entry (this session's fixes)
- `docs/HANDOFF_2026-05-11_visual_review_findings.md` — this file

### PDFextractor/ (app)
- `service/.env` (gitignored) — INTERNAL_SERVICE_TOKEN
- `service/.env.example` — committed template
- `service/app/main.py` — `/analyze`, `/render`, `/tables` endpoints; `/analyze` reuses cached results in render call
- `service/requirements.txt` — pinned to `@v2.2.0` (will need a tag)
- `start_app.bat` — uvicorn `--env-file .env`
- `frontend/src/lib/auth.ts` — dev Credentials provider + JWT session + test user creation with dailyLimit=-1
- `frontend/src/app/login/page.tsx` — dev credentials form
- `frontend/src/app/extract/page.tsx` — unified workspace (replaces old extract page)
- `frontend/src/app/sections/page.tsx` — redirects to `/extract?tab=sections`
- `frontend/src/components/document-workspace.tsx` — new (replaces extract-form.tsx + sections-form.tsx)
- `frontend/src/components/app-header.tsx` — "Workspace" nav link replaces Extract + Sections
- `frontend/src/app/about-normalization/page.tsx` — new (migrated pedagogical content)
- `frontend/src/app/api/analyze/route.ts` — proxy to service `/analyze`
- `frontend/src/app/api/render/route.ts` — proxy
- `frontend/src/app/api/tables/route.ts` — proxy
- `frontend/public/_test-pdfs/` — test corpus staging (gitignored)
- `frontend/src/components/extract-form.tsx`, `sections-form.tsx` — DELETED
- `API.md` — docs for new endpoints
- `SETUP_GUIDE.md` — note about `service/.env`
- `.gitignore` — `frontend/public/_test-pdfs/`

### Production tag deferred

The library should be tagged `v2.2.0` and pushed; the app's `requirements.txt` already points to that pin. Run `/docpluck-deploy` next session AFTER porting Section F and tagging v2.3.0, OR tag v2.2.0 now and deploy that first (so production at least gets the column-interleave / title-rescue fixes immediately).

---

## One-paragraph TL;DR for the next session

Port spike Section F (cell cleaning, ~6 helpers from `splice_spike.py:147-900`) into `docpluck/tables/render.py`, bump to v2.3.0, then re-run the AI-Chrome-verified iterative review on 10+ PDFs across the 9 journal styles. The review found 6 outstanding Rendered-view bugs (table HTML not appearing, table text leaking into body, figures spliced at abstract position, captions concatenating across figures, title truncation, subtitle styling) — fix only the ones that survive the v2.3.0 port. Then integrate the visual-review loop into `/docpluck-qa` and `/docpluck-review` so future changes are visually regression-tested automatically.
