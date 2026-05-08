# Unified Extraction Design — One Markdown Output Per PDF

**Status:** Design / not yet implemented
**Date:** 2026-05-08
**Author:** Brainstorm session, archived from chat
**Supersedes:** `docs/HANDOFF_2026-05-09_unified_extraction_brainstorm.md` (the question)
**Related:** [LESSONS.md](../../../LESSONS.md) (especially L-001), [docs/DESIGN.md](../../DESIGN.md) §13

---

## 1. Problem

Today docpluck returns two parallel views of a PDF:

- A **text channel** — `extract_pdf` (pdftotext, default mode) — calibrated against ~250 unit tests and the strict-iteration corpus. Drives `extract_sections`, `normalize`, `batch`.
- A **layout channel** — `extract_pdf_layout` (pdfplumber) — drives tables and figures.

`extract_pdf_structured()` calls both and returns a combined dict, but its `text` field comes from pdftotext while `tables` / `figures` come from a separate pdfplumber parse. The two parses are **never reconciled**: a downstream consumer that wants to ask "which section does table 2 sit in?" has to align the streams itself.

The user wants ONE accurate, unified product per PDF — a single canonical artifact where the cleanest possible text and the structures (sections, tables, figures, footnotes) all reference the same underlying document. Speed cost is acceptable.

## 2. Constraint that defines the design space

Three sessions in a row have tried to unify by replacing pdftotext with pdfplumber's `extract_text()`. Each reverted within an hour because the ~250 calibrated heading regexes / paragraph heuristics / watermark patterns are tuned to pdftotext's exact word-spacing / line-wrapping output. See [LESSONS.md L-001](../../../LESSONS.md#l-001--never-swap-the-pdf-text-extraction-tool-as-a-fix-for-downstream-problems).

The text channel stays pdftotext. The layout channel stays pdfplumber. We are not relitigating that.

The architectural question is: **given two channels with different strengths and incompatible text formats, how do we produce one consistent external product where every section/table/figure is a faithful reference to the same document?**

## 3. Canonical product: Docpluck Markdown 1.0

A single `.md` string per PDF. Conventions:

| Element | Rendering |
|---|---|
| Sections | ATX headings (`# H1`, `## H2`, …). Heading level mirrors taxonomy depth. |
| Paragraphs | Plain text, blank line between paragraphs (pdftotext's reading order, after normalize). |
| Tables (default) | Pipe table — `\| col \| col \|` then `\|---\|---\|` then rows. |
| Tables (complex) | Caller-controlled. Default = best-effort pipe-table with merged cells flattened/empty + a leading caption note. Opt-in HTML `<table>` fallback when caller passes `complex_tables="html_fallback"`. |
| Figures | Italic caption-only line: `*Figure 3. Caption text.*`. No image extraction in v1. |
| Footnotes | Inline parenthetical `(1)` in body; consolidated `## Footnotes` section at end with `(1) text` entries. No `[^1]` extension syntax. |
| Page boundaries | Not preserved in v1. May be added later as HTML comments if a consumer requests. |

The default profile — `complex_tables="pipe_best_effort"` — never emits raw HTML. Consumers who parse the markdown can rely on a pipe-tables-only document.

The Markdown 1.0 profile is versioned. Additions are non-breaking (minor bumps); removals or syntax changes are major bumps.

## 4. Architecture

```
                 ┌─────────────────────────────────────────────────┐
pdftotext text ──┤                                                 │
                 │   internal pipeline: normalize → splice tables  ├──► extract_markdown(path) → str
pdfplumber ──────┤                                                 │
                 └──────────────────────┬──────────────────────────┘
                                        │
                                        ├──► strip_markdown(.md) → text  (serves extract_pdf, extract_sections)
                                        │
                                        └──► pdfplumber bboxes direct  (serves extract_pdf_layout, structured tables/figures)
```

- `extract_markdown(pdf_path, *, complex_tables="pipe_best_effort") -> str` is the new flagship API.
- `strip_markdown(md: str) -> str` is a public utility. It removes ATX heading prefixes, footnote markers, italic figure-caption asterisks, and pipe-table syntax (yielding cleaner cell text than today's garbled-table-region pdftotext output). It preserves the rest of the text byte-identical to pdftotext.
- Legacy text-only functions (`extract_pdf`, `extract_sections`) are routed through `strip_markdown(extract_markdown(path))`. This is a behavior change in **table regions only**: those regions become cleaner instead of garbled. Verified non-regressing on the 250+ test corpus during phase 3.
- Legacy geometry-bearing functions (`extract_pdf_layout`, `extract_structured`'s `tables` / `figures` fields) continue to use pdfplumber directly. No change to their call paths or return shapes.
- `extract_structured()` gains an additional `markdown` field in its returned dict (additive, backwards compatible).

The strip-back model means we do NOT need an in-memory IR object. The markdown string IS the IR for everything text-shaped; geometry runs alongside on the pdfplumber channel as today.

## 5. Public API

```python
extract_markdown(
    pdf_path: str | Path,
    *,
    complex_tables: Literal["pipe_best_effort", "html_fallback"] = "pipe_best_effort",
) -> str

strip_markdown(md: str) -> str

# extract_structured() return shape (additive change):
extract_structured(pdf_path) -> {
    "text": str,        # unchanged: pdftotext
    "tables": list,     # unchanged: pdfplumber-derived table objects
    "figures": list,    # unchanged: pdfplumber-derived figure objects
    "markdown": str,    # NEW: extract_markdown(pdf_path) result
}
```

`extract_pdf`, `extract_sections`, `extract_pdf_layout` keep their existing signatures and return shapes. Their internal call paths change in phase 3.

## 6. Engineering risk: table splicing

The hard problem is: **where in pdftotext's linear text does each pdfplumber table region map to?**

pdftotext linearizes a table as a sequence of garbled rows (cells separated by inconsistent spacing, often interleaved with adjacent column text). To produce a unified `.md`, we must detect those rows in the pdftotext output and replace them with a clean markdown table at the right reading-order position.

Approach:

1. Use form-feed (`\f`) page-break markers shared by both channels to align at page granularity.
2. For each pdfplumber-detected table, get its bbox (page index + y-bounds).
3. On the pdftotext side of that page, identify the contiguous block of lines whose text matches the table's cell content (line-content fingerprinting; tolerant to whitespace / column-interleaving artifacts).
4. Replace that block with a serialized markdown table of pdfplumber's parsed cells.
5. Where step 3 cannot find a unique block (e.g., dense multi-table page, table content also appears in body text), fall back to inserting the markdown table at the page boundary with a note, rather than guessing.

This is **coarse alignment**, not character-by-character. It is the only thing in this design that could derail the project. Phase 0 below is dedicated to de-risking it.

## 7. Phased migration

| Phase | Deliverable | Exit criterion |
|---|---|---|
| **0. Splice spike** | 5-PDF prototype script: given pdftotext text + pdfplumber tables, splice markdown tables in at the correct reading-order position. Eyeball-diff. No production code. | Splices look correct on ≥4 of 5 papers; failure modes are understood and bounded. If <4 of 5 succeed: revisit design before phase 1. |
| **1. Markdown serializer** | `extract_markdown(path)` (pipe-table only, no `complex_tables` parameter yet). Footnotes consolidated. Section headings emitted. | All 250+ existing tests still pass via legacy facades not yet wired in. New eyeball check on 10 APA papers from `PDFextractor/test-pdfs/apa/`. |
| **2. Complex-table fallback** | `complex_tables="html_fallback"` option. Curated 5-paper "complex tables" suite (merged cells, multi-row headers, rotated). | Both modes render correctly on the curated suite. Default path still emits pipe-only. |
| **3. Legacy facades** | `extract_pdf` / `extract_sections` re-routed through `strip_markdown(extract_markdown(path))`. `extract_structured` gains the `markdown` field. | On the 50-PDF benchmark corpus: outside table regions, byte-identical or whitespace-only diffs vs. prior outputs. Inside table regions, diffs are individually reviewed; each must be either no-op or a strict improvement (cleaner cell text, no information loss). |
| **4. Docs + release** | DESIGN.md update (§13 → "Three views: markdown canonical + text channel + layout channel"), NORMALIZATION.md note on stripping, CHANGELOG, version bump (semver decision deferred to phase 4 — minor if phase-3 diffs are no-op outside tables; major if any consumer-visible API behavior changes), Markdown 1.0 profile spec at `docs/MARKDOWN_PROFILE.md`. | PyPI release; `PDFextractor/service/requirements.txt` git pin bumped. |

Phases 0–2 are reversible (additive). Phase 3 is the breaking-behavior phase that needs corpus sign-off.

## 8. What could break

- **Splicing fails on dense layouts.** Mitigation: phase 0 spike. Fallback if it fails: tables appear at the end of the section they were found in (or in a `## Tables` appendix at the end of the document) rather than inline. Less elegant but still unified.
- **Markdown 1.0 profile turns out wrong.** E.g., a consumer wants `[^1]` footnotes after all. Mitigation: profile is versioned. Additions are minor; removals are major.
- **`strip_markdown()` changes section bodies in subtle ways.** E.g., a body line that happened to look like a heading gets unintentionally re-headed in markdown then stripped back to bare text minus the leading `#`. Mitigation: phase 3's byte-diff gate against prior outputs is the explicit guard. Heading detection in the markdown serializer must NOT mark body lines as headings.
- **Performance.** `extract_sections()` now goes through markdown then strips — additional pass per call. User accepted speed cost. Document in NORMALIZATION.md.
- **The PDFextractor app pin lag.** Every time the library releases, `service/requirements.txt` must bump or production runs the old library. The `/docpluck-deploy` skill catches this.

## 9. Out of scope for v1

- Image extraction (figures are captions only).
- Page-boundary markers in markdown.
- A `parse_markdown(md) -> dict` round-trip parser. Legacy functions are served by `strip_markdown` + the existing pdfplumber channel, not by re-parsing the markdown into structures.
- Any change to which PDF library is used. pdftotext + pdfplumber, period (license constraint, see [LESSONS.md L-003](../../../LESSONS.md#l-003--never-use-pymupdf4llm-pymupdf-fitz-column_boxes-or-other-agpl-licensed-pdf-tools)).
- Any change to the calibrated section-detection heuristics or normalize pipeline. Markdown is a presentation layer over pdftotext text + pdfplumber tables; the underlying calibration is preserved.

## 10. Open questions answered before implementation

These were resolved during the brainstorm and are recorded here so the implementation plan does not relitigate them:

- **Round-trip strategy:** strip markdown for legacy text APIs; do NOT parse markdown back into structures. Geometry-bearing legacy APIs continue on the pdfplumber channel.
- **Complex-table fallback:** parameter, two modes only (`pipe_best_effort` default, `html_fallback` opt-in). No placeholder mode.
- **Footnotes:** inline `(1)` + consolidated `## Footnotes` section at end. Not `[^1]` extension syntax.
- **Figures:** caption-only, italicized. No image extraction.
- **API name:** `extract_markdown(path)`. `extract_structured()` gains a `markdown` field.
- **Phase 0:** required before phase 1 — empirical splice spike on 5 PDFs.
