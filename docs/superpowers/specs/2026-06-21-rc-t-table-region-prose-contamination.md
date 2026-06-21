# RC-T — Table-region prose contamination (the "full-page-bbox" defect) · design + fix plan

**Status:** root cause confirmed (2026-06-21, cycle 4). Implementation = the immediate next
focused cycle. Resolves the bbox-computation decision open since 2026-05-22.

**Scope:** the single most pervasive v2.4.95 corpus defect — broken tables on **all 7** verified
canary papers (single- AND two-column). This spec covers the *region/bbox* failure that pollutes
table cells with prose + furniture. (RC-1 column-interleave is a separate spec.)

## Symptom (canonical case: ip_feldman Table 10)

`extract_pdf_structured` returns Table 10 as `kind=structured` with 12 cells that are **garbage**:
`'Ip and Feldman'` (running header), `'15'` (page number), `'Discussion'` (section heading),
`'ported and documented below p < .05, yet we strongly cau-'` (Discussion **body prose**), mixed
with one real data row `'Loneliness.29***−.21***.07'`. Every cell bbox `(0,0,0,0)`. The renderer
correctly refuses to emit this as a `<table>`, leaving an **orphan `### Table 10`** heading and
the real table data lost. Across the corpus the same root cause also yields: empty shells
(plos_med T5, chandrashekar T7/T8), wrong-content tables (plos_med T4 = journal header + T3 data),
garbled cells (maier T7 body text), missing column headers (maier T8/T9/T11), and duplicate
columnar dumps (xiao T7/T8).

## Root cause — TWO layers (both confirmed by instrumentation 2026-06-21)

**Layer 1 — Camelot runs free-form (no `table_areas`).** `camelot_extract.extract_tables_camelot`
calls `camelot.read_pdf(tmp, pages="all", flavor="stream")` with **no region constraint**. On a
text-heavy page, stream flavor groups whitespace-separated text and returns a **whole-page bbox**
(T10's Camelot bbox = `(53,53,577,800)` on a 792-pt page). The detect.py caption-anchored regions
are NOT passed to Camelot as `table_areas`.

**Layer 2 — the whitespace fallback region reaches into prose.** When Camelot's cells are empty/bad,
`extract_structured` falls back to `whitespace.whitespace_cells(layout, region=_region_for_caption(...))`.
That region is `caption_bbox ∪ _extend(caption, SEARCH_BELOW_PT=250, "down")` (detect.py:86,99).
For a **short** table the 250-pt window overshoots the table and captures the prose below it
(T10's region `(63,71,564,331)` includes "…negative emotional experiences…when conducting the
better-" at top≈322). `whitespace_cells._cluster_into_rows` then clusters those prose lines into
"rows," and `_find_stable_column_boundaries` can't find columns, so prose words land in cells.

**Net:** there is no **table-END boundary detection**. The region runs a fixed 250 pt past the
caption regardless of where the table actually stops, and nothing trims the prose tail.

## Fix plan (the next cycle) — region prose-trim, keyed on column-structure breakdown

Add a **table-end detector** to `whitespace_cells` (and/or `_region_for_caption`) that trims the
region at the row where tabular column structure breaks down into prose. General structural
signature (NOT paper/font identity):

- Cluster rows as today. Compute the table's stable column boundaries from the **header + first
  few data rows** (the rows immediately under the caption that DO have ≥2 stable column gaps).
- Walk rows downward; **stop** at the first run of rows that are **prose**: a row that spans
  (near) the full region width as a single continuous text run with **no** interior column gap
  aligned to the established boundaries, AND whose text is sentence-shaped (lowercase
  continuation, > N words, ends mid-clause). Trim that row and everything below it from the region.
- Re-emit cells from the trimmed region only.

**Degenerate-region guard (belt-and-suspenders, same cycle):** if after trimming the cells are
still dominated by furniture/prose (a running-header-pattern cell, a section-heading word like
`Discussion`/`Method`, > X% sentence-shaped cells), do **not** emit a `<table>` AND **suppress the
orphan `### Table N` heading** — route to the existing `<!-- table-unstructured -->` fallback so
the failure is clean (no fabricated structure, no orphan heading) instead of messy.

## Hard FP constraints (why this MUST gate on the full baseline)

1. **Do not truncate legitimate multi-row tables.** Tables with a genuine wide note/footnote row,
   merged spanning cells, or a sparse final row must survive. The trim fires only on
   *prose-shaped* rows, never on short/sparse *tabular* rows.
2. **Do not suppress legitimate landscape tables.** ip_feldman Tables 6/7/8 have tall bboxes on
   landscape pages (width 723) — **bbox-size is NOT a valid discriminator**; key on cell content.
3. **Byte-identical on currently-correct tables.** Tables 1–9 of ip_feldman, the PROSECCO default
   tables, and the v2.4.95 flatten outputs must not change.

## Verification gate (mandatory before ship)

- Real-PDF regression tests (`*_real_pdf`) on ip_feldman T10 (orphan-heading gone OR table
  recovered), plos_med T5, maier T7, chan_feldman T2 — each failing at HEAD, passing after.
- **Full 26-paper baseline** `scripts/verify_corpus.py` = 26/26, plus a guard-live-vs-bypassed
  corpus diff over ALL ~48 papers (the cycle-3 caption-follows revert proved a bounded sample
  gives false confidence — the FP lived in the long tail).
- AI-verify (Sonnet vs article-finder golds) on the 7 canaries: no NEW TEXT-LOSS / HALLUCINATION;
  the touched tables improve or fail-clean.
- Tier-1 == Tier-2 == Tier-3 parity.

## Out of scope (separate work)
- Actually **recovering** the lost table data via tight `table_areas` (passing detect.py regions to
  Camelot) is a larger Layer-1 change — a follow-on cycle once the prose-trim + clean-fallback land.
- RC-1 two-column / sidebar interleave (separate spec, 2026-06-08).
