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

## UPDATE 2026-06-25 — Layer-1 recovery is the RC-1 BANDED-COLUMN work (probed, evidence below)

v2.4.96 (phantom-strip refinement) + v2.4.97 (Layer-2 raw_text prose-trim/suppress) shipped option (A)
clean-fail. At HEAD **v2.4.97** the residual is **4 data-losing caption-only stubs** across 3 canaries:
`ip_feldman` T10, `chan_feldman` T6 + T9, `chandrashekar` T2 (`### Table N` heading + caption, NO
`<table>`, data gone). Confirmed against the article-finder `reading` gold (e.g. ip_feldman T10 gold =
a real 7-row regression table; render drops all 7 rows).

**Probed two recovery angles; BOTH disproven as in-run wins (reproduce-before-trusting):**
1. **`whitespace_cells` on the tight `_region_for_caption` region** → still garbage. The region is
   `caption_only` + the 250pt below-window, and `_detect_geometry` finds no clean geometry, so the
   region overshoots into prose; the clusterer mashes prose into cells (3 rows × 8 cols of junk).
2. **Root cause is deeper than full-page-bbox: it is RC-1 interleave INSIDE the table region.** On
   ip_feldman p.15 the table rows and the Discussion prose share y-positions line-by-line (table in
   the LEFT x-band, Discussion in the RIGHT) — so ANY y-row clustering mixes them. Same shape on
   `chan_feldman` T6 (`r1c3`/`r2c3` = Discussion prose) and `chandrashekar` T2 (near-full-page bbox +
   survey-instructions prose). `chan_feldman` T9 is genuinely empty (`bbox 0,0,0,0`, 0 cells, 0 raw).

**KEY EVIDENCE — the table IS cleanly x-separable.** An x0 histogram of ip_feldman p.15's table y-band
(top 130–260) shows a clear column gutter at **x≈300–320** (table x≈60–300; Discussion densely
x≈320–560). Filtering chars to the left band recovers the clean grid:
```
Negative well-being
 Loneliness               .29***  −.21***  .07
 Rumination/brooding       .22***  −.10*    .04
 Depressive symptoms       .29***  −.20***  .07
Positive well-being
 Satisfaction with life   −.18***   .24***  .05
 Subjective happiness     −.28***   .34***  .10
 Number of confidants     −.07      .15**   .02
 Social orientation scale  .13**     .01    .02  (extension)
```
**Therefore Layer-1 recovery == the RC-1 region-aware BANDED-column architecture**
(`docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md`, ship-dark behind
`DOCPLUCK_COLUMN_CORRECT_BANDED`): detect the dominant gutter on the table's page-region, take the band
the caption x-sits in, re-run column detection on that band. NOT a safe drop-in — landscape Tables
6/7/8, genuinely single-column tables, and mid-table-gutter tables must NOT be split (the cycle-3
caption-follows revert proved this class is FP-prone on the long tail). Needs its own session with the
full ~48-paper guard-live-vs-bypassed diff + 7-canary AI-verify gate.

**Safe non-architectural increment available now (not yet taken):** when a Camelot table is
stripped-to-nothing as degenerate (`_strip_phantom_camelot_tables` removed the `<table>` and no cells/
raw_text remain), emit a machine-greppable `<!-- table-data-lost: degenerate region, no grid recovered -->`
completeness marker so the loss is HONEST to the harness + AI-verify (today it reads as clean because the
caption-only stub satisfies `table_parity`). Zero output-fidelity risk; keyed on the structural signature,
not paper identity.
