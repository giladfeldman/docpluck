# Table extraction re-architecture — research synthesis & plan (2026-06-28)

**Trigger:** the DP-1/DP-2 capture cycle hit a wall — geometry-only same-page
caption pairing is fragile because Camelot's *auto-detected* `_bbox`es routinely
absorb running headers or span multiple tables. User asked to go deep on the core
issue and long-term solution (research GROBID/ScienceArena/Camelot, "get these
working properly"). Three parallel research agents + local Camelot experiments.

## The decisive empirical finding (validated locally)

**Driving Camelot's `stream` flavor with docpluck's OWN caption-anchored region as
`table_areas` yields the correct table for each caption, deterministically** — on
every hard case (cog_emo T5/T6, plos_med T3/T4, 90203 T4/T5 including the
previously-0×0 classification grid). This *sidesteps the entire caption-pairing
problem*: each Camelot extraction is for ONE known caption by construction. No
header absorption (region is clipped to the caption band), no multi-table spanning,
no pairing ambiguity.

```python
# region.bbox is pdfplumber TOP-DOWN (x0, top, x1, bottom); Camelot wants PDF
# BOTTOM-UP "x1,y1,x2,y2" with (x1,y1)=top-left, (x2,y2)=bottom-right:
area = f"{x0},{H-top},{x1},{H-bottom}"     # H = page height
camelot.read_pdf(pdf, pages=str(pg), flavor="stream", table_areas=[area], ...)
# or batch: per_page={pg: {"table_areas": [areas_for_that_page]}}
```

**docpluck ALREADY computes exactly this region** — `detect.py::_region_for_caption`
returns `CandidateRegion(page, bbox, caption, …)` per caption — and then THROWS IT
AWAY, running blind `pages="all"` auto-detection and reconciling afterward by fuzzy
bbox overlap (`merge_camelot_with_docpluck`, `_pick_best_per_page`). That post-hoc
reconciliation (plus `_strip_running_header_rows`/`_trim_prose_tail`/
`_drop_caption_first_row`) is the SOURCE of the messy-bbox failures — all of it
exists to repair bad auto-detected boxes that region-driving avoids.

## Where docpluck actually stands (ScienceArena `pdf-table-extraction-v1`, real PMC)

Benchmarked head-to-head vs GROBID 0.8.1, Claude Haiku, LiteParse. docpluck pinned
at 2.4.88 (fairness), gold = publisher JATS XML. Per-axis on the common real set:

| Axis | docpluck | GROBID |
|---|---|---|
| detection_f1 | **0.784** | 0.654 |
| cell_f1 | 0.518 | 0.510 |
| struct_agree | 0.407 | **0.459** |
| caption_recall | **0.468** | **0.641** |

docpluck **wins detection** (4 phantom tables vs GROBID's 18) and many-table
robustness, but **loses on caption fidelity and header/span structure**. docpluck's
own error histogram: `table_missed` 39%, `cell_count_mismatch` 20%,
`header_rows_wrong` 17%, `caption_wrong` 16%, `merged_cell_lost` 6%. It scores WORSE
on multi-row-header tables (H2/H3 ≈ 0.40/0.50) than simple ones (H1 0.52), and
**crashed on 2 high-table-count papers** (PMC13136041: docpluck errored, GROBID got
24/24) — a robustness gap, not just quality.

Caption bleed is documented paper-by-paper: PMC13130281 T2 caption =
`"…between the two groups (points) Observation"` (the word "Observation" is the
column-header start, vacuumed in); PMC12081175 T1 = `"333 Sample demographic…"`
(stray page artifact). Root cause: `_extract_caption_text` (extract_structured.py
~707, seeded by captions.py `_line_at`) walks FORWARD bounded only by next
caption/`\f`/sentence-terminated `\n\n`/800-char cap — **no lower bound at the table
grid's top edge**, so it runs into the header row.

## Convergent root causes (all 3 agents agree)

1. **Caption bleed** — caption text absorbs column-header tokens. Fix: clip the
   caption's forward walk at the table-region TOP edge (the layout channel already
   computes it for cells). Keys on the invariant "caption never extends below the
   grid top" — exactly how JATS bounds `<caption>`.
2. **Region absorbs running header** — `_region_for_caption` grows `SEARCH_ABOVE_PT`
   = 150pt upward with NO header-band exclusion, even though
   `normalize.py::_f0_strip_running_and_footnotes` already detects running
   headers/footnotes in the TEXT channel. Fix: expose those y-bands (or re-run
   repeated-text + digit-masked edit-distance detection) to the LAYOUT channel and
   refuse to grow a region across them.
3. **Auto-detected bboxes are the wrong input** — drive Camelot with the
   caption-anchored region instead (the breakthrough above).

## Reference architecture (GROBID / PDFFigures 2.0 / TATR)

Keep the concerns **separate and ordered**:
**header-strip → table-detect/region → caption-associate → Camelot-structure.**

- **GROBID**: caption is a *sub-label of one `<figure type="table">` region* (co-membership in reading order), kept in bbox sync — not a faraway line paired later. Cells carry native `@cols`/`@rows` spans.
- **PDFFigures 2.0** (AI2, Apache-2.0, born-digital — the closest prior art): (a) caption-start consistency filters — when "Table N" matches twice, keep the one that *starts a line* / is *bold* / *font-size differs from following words*; (b) region = expand caption box until it hits **body text or margin** (body text NEVER belongs to a table); (c) **GLOBAL caption→region assignment** (brute-force all matchings, ≤4 tables/page) + **constraint propagation** for above/below (assign the unambiguous caption first, which forces the ambiguous middle one); (d) **split an over-grown region along its largest internal whitespace band** when two captions collide; (e) running headers/page-numbers detected by **cross-page repetition (digit-masked fuzzy match)** and labeled body-text so regions can't absorb them.
- **TATR / PubTables-1M**: "table caption"/"table footer" are co-detected spatial objects belonging to the table — reinforces the co-membership framing. (Reference only; image-based DETR is too heavy + the layout models are not deps.)

Do **NOT** adopt: PyMuPDF/`fitz`/`pymupdf4llm` (AGPL — forbidden); any runtime DETR/image model. Use as design references only.

## Camelot 2.0.0 capabilities docpluck under-uses (audit, all confirmed in installed source)

Installed is **camelot-py 2.0.0** (not the 0.x the code comments assume — pin is unbounded `>=0.11,<3`).

1. **`table_areas` (+ `per_page`)** — *the* highest-impact lever (the breakthrough). Bypasses auto-detection; one verbatim table per box. `table_regions` is the softer variant (filters text to region, then auto-detects inside).
2. **`columns=` (per-table interior x-separators)** — forces column boundaries for tight-kerned tables where whitespace-mode column inference fails (the cog_emo T5 "2 cols, should be 4" class). Must be paired 1:1 with `table_areas` (`_validate_columns` requires equal lengths). docpluck can compute separators from its own RC-T char-level analysis.
3. **`flavor="network"` / `"ml"`** — 2.0 borderless-table parsers, purpose-built for APA tables (`network` is dep-free; `ml` = Table Transformer, needs `[ml]`). Evaluate vs `stream`, pick by `confidence`. (Local test: network did NOT beat stream on the column-count cases — `columns=` or region-clip is the real fix there. Re-evaluate per-table.)
4. **Per-cell geometry + spans** — `cell.x1/y1/x2/y2`, `cell.hspan`/`cell.vspan`/`cell.bound`. docpluck hard-codes cell `bbox=(0,0,0,0)` and `colspan/rowspan=1`; lattice path could read REAL spans (fixes `merged_cell_lost` + `flatten.py:1376` "colspan is lost").
5. **`table.confidence`** = `(accuracy/100)*(1−whitespace/100)` in [0,1] — replaces docpluck's ad-hoc `accuracy/100` clip + separate threshold; folds in whitespace sparsity.
6. **`table.textlines`** (raw textline objects w/ coords) — cluster `y0` to detect inter-table gaps and split a merged detection; `find_columns_boundaries(tls, min_gap)` is the ready x-axis analogue.
7. **`edge_tol`** (default 50; Nurminen detector assumes tables are far apart vertically) — LOWER it to split stacked tables in auto-detect mode.
8. **`replace_text` dict** — collapse soft-broken words at the source (`{" \n":" "}`).

Cross-cutting: tighten the Camelot pin (local 2.0.0 vs possibly-stale prod image can diverge silently); keep per-FILE Camelot gating (cumulative-load flake, memory `feedback_camelot_flake_cumulative_load`).

## Ranked plan (impact ÷ cost; each AI-gold-verified, zero-regression bar)

**Tier 1 — fixes the reported bugs, low cost, high impact**
1. **Region-driven Camelot** — feed `_region_for_caption` bboxes as `per_page`/`table_areas`. One clean table per caption; eliminates pairing ambiguity, header absorption, multi-table spans. Retires most post-hoc reconciliation. *(The breakthrough — highest impact.)*
2. **Clip the caption at the table-region top edge** — bound `_extract_caption_text`'s forward walk at the grid top (layout channel). Directly attacks the #1 competitive deficit (caption_recall 0.47→target ≥0.64). *Generalizes — keys on a layout invariant.*
3. **Header-band exclusion in the layout channel** — expose `_f0` running-header/footer y-bands; clip regions so they can't grow into the banner. Fixes the cog_emo-T5-style header absorption at the source.

**Tier 2 — robustness / structure**
4. **`columns=` for tight-kerned tables** — pair per-table column separators (from RC-T analysis) with `table_areas` (fixes `cell_count_mismatch` / wrong column counts).
5. **Real per-cell spans (lattice)** — read `hspan`/`vspan` instead of forcing 1×1 (fixes `merged_cell_lost`, improves `struct_agree`).
6. **Multi-row-header detection** — emit `header_rows≥2` + merged header cells with real colspan (don't repeat spanned text). docpluck scores worse on H2/H3 than H1.
7. **Harden many-table papers** — docpluck *crashed* where GROBID got 24/24; investigate Camelot scaling / adapter timeout, degrade gracefully.

**Tier 3 — longer horizon**
8. **Global caption→region assignment + constraint propagation** (PDFFigures) — only if Tier 1 leaves residual multi-caption-page failures (region-driving may already resolve them).
9. **Caption-start consistency filters** (font/line-start) in `captions.py`.

**Verification bar (every change):** full 26-paper baseline + structured guard-diff
(working tree vs HEAD) + AI-gold canary re-verify against `reading`/`stats` golds
(NEVER pdftotext), ZERO regression (word-preservation is blind to reorder — memory
`word-preservation-gate-is-blind-to-reordering`). Re-run the ScienceArena
`pdf-table-extraction-v1` arena against current docpluck to refresh the scorecard.

## Source pointers
- ScienceArena: `MetaScienceProjects/ScienceArena/arenas/pdf-table-extraction-v1/` (scorer.py, runs/v1/reports/); adapters in `players/adapters/{docpluck,grobid,llm_pdf}_tables.py`; gold = JATS via `article-finder/_lib_jats.py::parse_tables`.
- PDFFigures 2.0: github.com/allenai/pdffigures2 ; paper ai2-website.s3.amazonaws.com/publications/pdf2.0.pdf
- GROBID: grobid.readthedocs.io/en/latest/Principles/ ; fulltext labels training/fulltext/
- TATR/PubTables-1M: github.com/microsoft/table-transformer
- Camelot 2.0: camelot-py.readthedocs.io ; installed `C:\Python314\Lib\site-packages\camelot\`
- docpluck files: `tables/detect.py` (_region_for_caption ~80, SEARCH_ABOVE_PT=150 @46), `extract_structured.py` (_extract_caption_text ~707, _assign_captions_by_geometry [this run's WIP]), `tables/captions.py` (_line_at @94), `tables/camelot_extract.py` (cell bbox zeroed @450, accuracy clip @486), `normalize.py` (_f0_strip_running_and_footnotes ~387).
</content>
</invoke>
