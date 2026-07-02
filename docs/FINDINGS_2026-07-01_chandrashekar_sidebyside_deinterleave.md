# FINDINGS — chandrashekar Table 3/4 side-by-side de-interleaving (2026-07-01)

Resolves TRIAGE `docs/TRIAGE_2026-06-25_escicheck_handoff_defects.md` **RESOLUTION 2
hard-case #3** ("chandrashekar Table 3/4 caption — 2-column caption interleaving in the
text channel; truncating made it worse; needs proper 2-column de-interleaving").

Ground truth: AI multimodal gold `tmp/chandrashekar_2023_mp_gold.md` (article-finder),
NEVER pdftotext. Paper: `PDFextractor/test-pdfs/apa/chandrashekar_2023_mp.pdf`
(DOI 10.15626/MP.2022.3108).

## The defect (bigger than the triage/handoff framed it)

Page 7 places **Table 3** (left column, "Study stimuli for the on conceptual replication
of Johnson et al. 2002") and **Table 4** (right column, "Classification of replications
based on LeBel et al. 2019") SIDE-BY-SIDE in two columns. pdftotext linearizes the page
by reading left-column-then-right-column within horizontal bands, and the captions +
their first description lines share y-rows across the gutter, so the linear TEXT channel
interleaves them:

```
Table 3 \n Table 4 \n Study stimuli…[T3 desc] \n Table 4. Classification…[T4 desc]
```

The handoff claimed "only the CAPTION is contaminated; Table 4 content is already
correct." **Empirically false** (verified this run): the v2.4.99 region-driven Camelot
capture grabbed a bbox spanning BOTH columns, so Table 3 + Table 4 rendered as ONE merged
grid — a 17×2 with Table 3's stimulus prose in column 0 and Table 4's LeBel grid in
columns 1-2, a `Table 3 | Table 4` caption row on top. Three contaminations:

1. **Table 3 caption** absorbed Table 4's label → `"Table 3 Table 4 Study stimuli…"`.
2. **Table 4 cells** = the column-straddling 17×2 merge (gold wants a clean 2×9).
3. **Table 3 raw_text** (isolated-path body) = Table 4's ENTIRE LeBel grid followed by
   Table 3's stimuli (the gutter-crossing `_extract_table_body_text` walk).

User decision (this run): **full geometric de-interleave** — fix cells AND captions so
Table 3 and Table 4 emerge as SEPARATE, correct tables.

## The fix (all keyed on a STRUCTURAL signature — never paper identity)

A page is treated as side-by-side ONLY when: ≥2 table captions share the page AND a
vertical whitespace **gutter** separates their label TOKENS into different columns. Single-
column pages and multi-caption STACKED pages expose no separating gutter → byte-identical.

**`docpluck/extract_structured.py`:**
- `_detect_column_gutters(page_obj, band)` — column-occupancy histogram over the caption
  band; returns the x of each wide (≥10pt) vertical-whitespace gutter with real ink on
  both sides. chandrashekar p7 → gutter x≈304.
- `_label_x_midpoint(page_obj, cap)` — x-midpoint of a caption's OWN label glyphs
  (`Table 3` at x≈70 vs `Table 4` at x≈329), located by matching the label's number in
  the joined char row. The whole-row `_bbox_of_caption_line` is unusable here because
  pdfplumber clusters BOTH labels into one row (`Table3Table4`, midpoint in the gutter →
  both captions mis-assigned to one column).
- `_assign_caption_columns(...)` — assigns each caption to its `(gutter_left, gutter_right)`
  column; returns `{}` unless captions occupy ≥2 distinct columns (so stacked tables on a
  2-col page are left full-width).
- `_column_table_bottom(...)` — clips a column's region bottom at the first inter-row gap
  > 1.7× the modal line-height (the blank band before the following body prose). WITHOUT
  this the region overshoots into single-column prose that collapses Camelot's stream
  column detection to 1 col (Table 4 → 19×1 instead of 10×2).
- `_region_driven_capture` now: detects gutters per page, clips each side-by-side caption's
  region to its column (x-range + table-bottom), marks the spec `isolate=True`, marks the
  resulting table `_side_by_side=True`, and rebuilds the caption from its own column via
  `_caption_text_from_column` (stops at a blank band, a body/cell opener, or a grid row
  detected by `_row_has_wide_internal_gap`). Returns `cap_column_by_id` so the caller's
  isolated/whitespace fallback paths can rebuild a side-by-side caption+body too.
- `_column_body_text(...)` — rebuilds an isolated side-by-side table's body from its own
  column (Table 3's stimulus list), bypassing the gutter-crossing text channel.
- `_pick_better_table` — a `_side_by_side` region table wins UNCONDITIONALLY over the
  column-straddling auto-detect table (whose larger cell count is contamination, not
  richness).

**`docpluck/tables/camelot_extract.py`:**
- `extract_tables_camelot_by_region` runs `isolate=True` specs each in their OWN single-
  area Camelot call — `stream` column detection is computed across ALL `table_areas` in a
  call, so batching two narrow columns collapses each to 1 col. Non-isolate specs keep the
  original single batched call (byte-identical behavior).
- `_camelot_table_to_dict(..., allow_categorical=…)` threads a categorical-friendly gate to
  the side-by-side path (the LeBel grid is purely text labels/values, no numeric cells).
- `_drop_caption_first_row` also drops a leading single-cell caption-tail fragment (a bare
  `(2019)` the region top pulled in above the real header).

**`docpluck/tables/whitespace.py`:**
- `_trim_trailing_prose_rows` / `_whitespace_grid_is_clean` gain `allow_categorical`: accept
  a clean CATEGORICAL grid (no numeric data rows) when the side-by-side path bounds it by
  geometry; the unmapped-glyph / caption-label / prose-fragment guards still apply.

## Verified result (AFTER, against the AI gold)

| | Before (v2.4.99) | After | Gold |
|---|---|---|---|
| Table 3 caption | `Table 3 Table 4 Study stimuli…` | `Table 3 Study stimuli for the on conceptual replication of Johnson et al. (2002)` | ✓ match |
| Table 3 raw_text | Table 4's LeBel grid + T3 stimuli | `[Introduction]: Typically…` (own stimuli) | ✓ |
| Table 4 shape | 17×2 (merged) | **9×2** | ✓ (2 cols × 9 rows) |
| Table 4 caption | `Table 4. Classification…LeBel et al.` (truncated, contaminated) | `Table 4. Classification of replications based on LeBel et al. (2019)` | ✓ match |
| Table 4 cells | col0=T3 prose, col1-2=LeBel | `Design facet\|Replication study` … `Replication classification\|Very close replication` | ✓ |

## Verification status

- **chandrashekar Table 3/4 vs the AI gold: PASS** (captions, cells, and body all match —
  see the table above). This is the primary deliverable and it is gold-verified.
- **Fast non-Camelot unit suite** (structured/caption/whitespace/detect/cell-cleaning):
  **123 passed, 2 skipped**.
- **AFTER full-corpus capture** (101 PDFs, one subprocess each, from the Dropbox-immune
  `dp_after_head` worktree = HEAD + my 3 files): **0 errors**; chandrashekar correct.
- **v2.4.98→AFTER structured diff** (complete, JSON-only): 34 papers changed, **0 new
  errors**; chandrashekar shows the correct de-interleaving (T3 17×2→isolated, T4 0×0→9×2,
  both captions fixed). NOTE: the 34 is dominated by the PRE-EXISTING region-driving WIP
  (v2.4.98 predates it), NOT this fix.
- **Blast-radius argument (analytical — substitutes for the blocked full HEAD→AFTER diff).**
  The full BEFORE(HEAD)→AFTER 101-PDF diff could NOT be captured: this machine's session
  teardown kills every multi-minute background job (the HEAD baseline died at 46/56/101
  three times; the Camelot-free side-by-side scan died 5×), and it wouldn't isolate this
  fix from the pre-existing WIP anyway (both are uncommitted). Instead the fix is **inert by
  construction** on any non-side-by-side page: the entire side-by-side path is gated behind
  `_assign_caption_columns(...) != {}`, which requires ≥2 table captions on ONE page + a
  detected gutter + captions in ≥2 distinct columns. When that is false, `cap_column_x`
  is `{}` → no column clip, no `isolate` spec, no `_side_by_side` marker, no caption/body
  rebuild. `extract_tables_camelot_by_region` is byte-identical when no spec is `isolate`
  (verified by inspection: `isolated=[]`, `batched=specs`, same single `read_pdf`), and
  every `allow_categorical` defaults `False` off the side-by-side path. So the ONLY papers
  that can change are those with side-by-side table captions — of which chandrashekar (the
  target) is gold-verified.
- **Residual gap (honest):** the empirical enumeration of ALL side-by-side papers in the
  corpus (to gold-verify each, not just chandrashekar) was blocked by the teardown-kills.
  `tmp/_sbs_min.py` (layout-only, per-PDF-incremental) is the tool; re-run it in a session
  where long jobs survive, then gold-verify any HIT beyond chandrashekar. Given the tight
  gate this set is expected to be very small (2-column APA/psych papers with two tables
  side-by-side on one page).

## Environment hazard (recorded for the next session)

The repo lives under `Dropbox/Vibe/…`. Dropbox repeatedly reverted
`docpluck/extract_structured.py` to a cached copy on session teardown/resume (it happened
3×; the OTHER two changed files survived each time). Mitigations used: back up changed
files to the session scratchpad (outside Dropbox) after every edit; run verification
captures from git WORKTREES outside Dropbox (`Temp/dp_baseline_head`, `Temp/dp_after_head`)
so the JSONs are immune; restore from the scratchpad backup + re-stage on resume. The
durable fix is to COMMIT (git is immune to the working-file revert).

## NEXT (immediate, same run)

1. Finish the BEFORE(HEAD)→AFTER 101-PDF diff; confirm the ONLY table changes attributable
   to THIS fix are on side-by-side pages (gated), and AI-gold-verify each such paper.
2. Bump versions (`__version__`, `pyproject.toml`, `NORMALIZATION_VERSION`,
   `TABLE_EXTRACTION_VERSION`) + CHANGELOG, then the release/deploy flow.
3. NOTE: the working tree also carries a large PRE-EXISTING uncommitted WIP (the
   region-driving `_region_for_caption` widen-to-content rewrite + a global per-page
   table↔caption assignment apparatus in `_best_assignment_for_page`) that is NOT part of
   this fix and must be reconciled/attributed separately before release.
