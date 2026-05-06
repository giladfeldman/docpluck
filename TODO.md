# Docpluck — Roadmap / Deferred Work

This file tracks future-aim items that are scoped out of the current milestone but should not be lost. See `docs/superpowers/specs/` for active specs.

## Tables — formal evaluation corpus (deferred to v2.1)

v2.0 ships with smoke tests only (`tests/fixtures/tables/`, ~10-15 hand-picked PDFs with per-PDF assertions on table count, row/col counts, specific cell values). No formal accuracy numbers.

v2.1 (or a dedicated eval milestone) should add:

- **30-40 hand-labeled APA-psych PDFs** with HTML ground truth for every table (and figure caption + bbox where checkable).
- Scoring with **TEDS** (Tree-Edit-Distance Similarity, ICDAR 2021) + **cell-exact-match rate** + **table-detection precision/recall**.
- Numbers added to `BENCHMARKS.md` alongside existing engine-comparison results.
- A separate Elsevier/Springer/Nature/IEEE slice (~10 PDFs) so we can also report on lattice (full-grid) tables, not just APA lineless.

This is the foundation for the level-C work below — without numbers we can't tell if a "best-in-class" claim is true. Best done after v2.0 ships, because real edge cases will surface in production use and inform what's worth labeling carefully.

## Tables — future "level C" aims (deferred from v2.0)

The current table-extraction milestone (see `docs/superpowers/specs/2026-05-06-table-extraction-design.md`) targets level **B**: detect every table, emit structured cells when there are ruling lines or clean column-gap whitespace, isolate (raw text + bbox) otherwise.

Deferred to a later release ("level C — best-in-class APA-psych structured extraction"):

- **Multi-row header recovery** with colspan/rowspan inference (e.g., "Pretest" / "Posttest" headers spanning 2-3 columns each, with "M (SD)" sub-headers below).
- **Correlation-matrix awareness** — recognize lower-triangular layout, handle diagonal blanks / "—" / "1.00", emit a `matrix: true` flag with row/col labels.
- **Footnote-marker linking** — attach `*`, `**`, `***`, `†`, `‡`, superscript-letter markers as cell metadata linked to a parsed footnote dictionary (`*p < .05` etc.), instead of dropping or concatenating into the number.
- **Multi-page table stitching** — detect "Table N (continued)" / repeated header rows on the next page, stitch into a single logical table.
- **Two-column-span table detection** in two-column papers — detect tables that span the full printable width before column-aware reading-order is applied.
- **Landscape (rotated 90°) table support** — read PDF page rotation + `LTChar` matrix orientation, rotate coordinates before clustering.
- **Build a 50-PDF APA-psych eval set** with hand-labeled HTML ground truth, scored with TEDS (Tree-Edit-Distance Similarity, ICDAR 2021) + cell-exact-match. Target: TEDS > 0.80 on the APA-psych slice.

These are real engineering items, not nice-to-haves — they're what would let docpluck claim best-in-class status against GROBID/Camelot/Docling on the APA-psych corpus specifically. Out of scope for v2.0 to keep the first release shippable.

## Figures — future "level C" aims (deferred from v2.0)

The current milestone targets figure level **A**: detect figure regions, emit `figures: [{page, bbox, label, caption}]`, strip/placeholder the figure region from the linear `text` output. No image extraction, no figure-content understanding.

Deferred to a later release if it proves valuable and doable:

- **Figure image extraction** — pull the actual figure rendering (vector graphics or rasterized image) and emit it as a separate asset (PNG/SVG path) alongside the metadata.
- **Axis-label / legend OCR** — for raster figures, OCR the in-figure text so downstream tools can search for variable names appearing only in figures.
- **In-text figure reference resolution** — link "(see Figure 3)" mentions in the prose back to the corresponding figure object.
- **Figure-type classification** — distinguish bar plot / scatter plot / forest plot / flowchart / schematic / photograph (useful for meta-analysis tooling that wants forest plots).
- **Subfigure detection** — handle "Figure 2a / 2b / 2c" panel layouts as a parent figure with child panels.

Worth revisiting once the table track is shipped and we know which figure-side capabilities downstream tools (ESCIcheck, MetaESCI, Scimeto) actually need.

## Section identification — future enhancements (deferred from v1.6.0)

The v1.6.0 milestone (`docs/superpowers/specs/2026-05-06-section-identification-design.md`) ships a flat sectioner with 18 canonical labels + `unknown` fallback, hardcoded taxonomy, and merged `title_block`. Deferred:

- **Hierarchical / tree section output.** Currently flat with numeric suffixes (`methods_2`). Add a tree mode (`Body → Study 1 → Methods/Results`, `Body → Study 2 → Methods/Results`) when a real consumer needs it. (Q2 option C from the brainstorm.)
- **Split `title_block` into `title` / `authors` / `affiliations`.** Currently merged because affiliation parsing is its own hard problem; consumers needing structured author metadata should use CrossRef/DOI lookup. Worth doing once we have a use case that can't be served by external APIs.
- **Custom heading-map / user-supplied taxonomy extension API.** Hardcoded taxonomy in v1; revisit after we collect real-world misses on Hebrew / non-English / domain-specific journals.
- **Validate the conflict-resolution rule** (text-pattern wins for canonical headings, layout wins for unknown headings — Q4.vi from the brainstorm). Test against the v1 corpus once MVP ships and adjust if there's a class of papers the rule fails on.
- **Public `extract_pdf_layout()` API.** Internal-only in v1.6.0. Promote to public API once the `LayoutDoc` shape stabilizes and an external consumer asks for it.
- **Section-aware quality scoring** in `quality.py` (e.g., flag a low-confidence `references` section that may need re-extraction).
- **Confidence calibration.** Current `high`/`medium`/`low` is heuristic. Real numeric calibration needs the v1 test corpus + manual gold labels.

## Table/figure text-mode — future configuration enhancements (deferred from v2.0)

The current milestone ships with two `text` modes for `extract_pdf_structured()`:
- `"raw"` (default) — flowing text including table contents, identical to `extract_pdf()` behavior. Backwards-compatible.
- `"placeholder"` — table/figure regions replaced with `[Table N: caption]` / `[Figure N: caption]` markers.

Deferred richer modes to consider once the two-mode default is in production and we have feedback:

- **`"strip"`** — remove the region entirely with no marker (cleanest for some consumers, but loses positional cue).
- **`"inline_markdown"`** — render structured tables as markdown pipe-tables inline in `text` (LLM-friendly; lossy on multi-row headers; reintroduces stat-regex false positives — careful).
- **`"inline_html"`** — same idea but HTML tables inline (preserves more structure than markdown).
- **Per-table-type override** — different mode for tables vs. figures, e.g. raw for tables, strip for figures.
- **Confidence-gated mode** — placeholder only when structured extraction confidence is high; raw fallback otherwise.
- **Custom placeholder template** — caller supplies `f"[{label}: {caption}]"` or similar.

Add only when a real downstream consumer asks for one. YAGNI until then.
