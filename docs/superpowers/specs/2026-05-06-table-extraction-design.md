# Design — Docpluck v2.0 Table & Figure Extraction

**Date:** 2026-05-06
**Source request:** User brainstorm — "docpluck loses all of the tables' structure right now. Identify tables and figures across academic styles (APA, Vancouver, Nature, IEEE, …); preserve as much table structure as possible; learn from GROBID's deterministic ideas without inheriting its problems."
**Version:** Docpluck `1.6.x` → `2.0.0`
**Status:** Design approved by user 2026-05-06 (this conversation). Implementation plan to follow.
**Coordination:** Blocked on Phase 4 of `2026-05-06-section-identification.md` landing on `main` (the `extract_pdf_layout()` / `LayoutDoc` piece). See §12.

---

## 1. Problem & motivation

Docpluck today has **zero structural awareness of tables or figures.** When `extract_pdf()` runs, every cell of a regression table flows into the linear `text` output as space-collapsed prose:

```
Variable     Age   28.4  12.1  −0.07  .42   ...
```

This causes three downstream pains:

1. **Statistical false positives.** Stat-extraction consumers (ESCIcheck, MetaESCI, Scimeto) match `p\s*[<=>]\s*\.?\d+` patterns against the linear text. Table cells produce phantom p-values, ds, rs, CIs that aren't real claims in the paper. `DESIGN.md` §1 explicitly notes the figure-axis-label false-positive problem (`r>1`, `r>2` axis ticks reported as 167-out-of-168 false positives in pymupdf4llm output) — table cells produce the same kind of garbage.
2. **Lost table content.** Tables in academic papers carry the most condensed claim density of the whole paper (descriptives, correlation matrices, regression coefficients with 95% CIs and footnote-marker p-values). Today docpluck loses all of it as structured information.
3. **Lost figure positional cue.** The same flowing-text problem hits figures (axis labels, legend text). And consumers can't even tell *where* the figures were in the paper.

GROBID is the obvious comparison point. The user explicitly asked us to "learn from GROBID's deterministic ideas." Research surfaced a hard fact: **GROBID is not deterministic for tables.** Its layout pipeline is a CRF cascade; the "rules" are layout features fed into a sequence labeler, not a clean rule layer we can port. Worse, GROBID is the *worst* table extractor on every recent benchmark (F1 0.23–0.43 on PubTables / Table-arXiv / Table-BRGM, behind Camelot, Tabula, and far behind Docling at 0.89–0.99). The bar GROBID sets is on the floor.

What's reusable from GROBID is conceptual, not code:
- The cascade idea: detect-then-substructure (caption-anchored region detection → cell clustering inside the region).
- The TEI markup convention `<figure type="table"><head><label>...</label></head><table><row><cell/>...</row></table><note/></figure>` — useful as a mental model for our schema.

The actual implementation foundation is **pdfplumber + pdfminer.six + caption regex + table-aware geometric clustering** — all MIT-licensed, all already in (or trivially reachable from) docpluck's existing dep set.

**Goal of this design:** add deterministic, MIT-licensed table and figure detection and structural extraction as a v2.0 feature, exposed through a new `extract_pdf_structured()` function that callers opt into. Existing `extract_pdf()` behavior stays bit-for-bit identical.

## 2. Scope

The brainstorm explicitly considered three ambition levels for tables (A/B/C) and three for figures (A/B/C). v2.0 ships:

- **Tables: level B** — detect every table; emit structured cells when ruling-line geometry or clean column-gap whitespace permits; isolate (raw text + bbox + caption + footnote) when structure can't be confidently recovered. See `TODO.md` for the deferred level-C items (multi-row header recovery, correlation-matrix awareness, footnote-marker linking, multi-page stitching, two-column-span detection, landscape rotation).
- **Figures: level A** — detect figure regions; emit `{label, page, bbox, caption}` metadata only. No image extraction, no axis-label OCR, no figure-content understanding. See `TODO.md` for the deferred level-C items.

### In scope (v2.0)

- New top-level public function `extract_pdf_structured(pdf_bytes, *, thorough=False, table_text_mode="raw") -> dict` returning the schema in §4.
- Tables: detection, structured cells when confident, HTML rendering for structured tables, JSON cell array, raw text + bbox always available.
- Figures: detection, label + caption + bbox.
- Two `text` modes: `"raw"` (default; backwards-compatible) and `"placeholder"` (opt-in; replaces table/figure regions with `[Table N: caption]` / `[Figure N: caption]` markers).
- Two detection scopes: default = caption-anchored page-scoped pdfplumber pass (typical ~1–2 s on a 30-page paper); `thorough=True` = full pdfplumber pass on every page (~9 s) for callers who suspect uncaptioned tables.
- Smoke test fixtures (~10–15 PDFs, per-PDF assertions on table count, row/col counts, key cell values, figure count + captions).
- Documentation: schema reference (this doc), behavioral notes, usage examples in `docs/README.md`.
- `TABLE_EXTRACTION_VERSION` constant, recorded on every result.

### Explicitly out of scope (deferred — see `TODO.md`)

1. Multi-row header recovery, correlation-matrix awareness, footnote-marker linking, multi-page table stitching, two-column-span detection, landscape rotation. (Tables level C.)
2. Figure image extraction, axis-label OCR, in-text figure-reference resolution, figure-type classification, subfigure detection. (Figures level C.)
3. Configurable text-modes beyond `"raw"` and `"placeholder"`: `"strip"`, `"inline_markdown"`, `"inline_html"`, per-table-type override, confidence-gated mode, custom placeholder template.
4. Formal accuracy benchmarks (TEDS, cell-exact-match) on a hand-labeled APA-psych corpus. (v2.1 milestone.)
5. DOCX and HTML structured table extraction. (PDF only for v2.0.)
6. Public `extract_pdf_layout()` API. Internal-only — owned by section-id v1.6.0; we *consume* it but don't promise anything about its shape externally.
7. PyMuPDF-based extraction. AGPL-incompatible with docpluck's MIT license. Hard rule.
8. Deep-learning table extractors (Docling/TableFormer, marker, TATR, unstructured.io hi_res). Heavy deps + model weights; revisit only if rule-based proves insufficient on the v2.1 eval corpus.

### Success criteria for v2.0

1. `extract_pdf()` is byte-identical to v1.6.x for the existing 153-test corpus.
2. `extract_pdf_structured()` returns a result conforming to the §4 schema for every PDF in the v1.6.x test corpus, never raises on malformed PDFs (mirrors `extract_pdf()` graceful-error contract).
3. Smoke fixtures pass: detect-rate 100% on lattice (full-grid) tables in fixtures; ≥80% structure-rate on lineless APA tables in fixtures; figure detection ≥95% on fixtures with `^Figure \d+` captions.
4. Hand-picked QA: stat-regex false positives produced by table-cell content disappear when downstream consumers call `extract_pdf_structured()` with `table_text_mode="placeholder"`.
5. SaaS service can opt in via `requirements.txt` git-pin bump without breaking existing extract endpoint.

## 3. Architecture

### 3.1 Dependency on section-id v1.6.0

`extract_pdf_structured()` consumes `LayoutDoc` from `docpluck/extract_layout.py`, the internal pdfplumber wrapper introduced by section-id v1.6.0 (Phase 4 of `2026-05-06-section-identification.md`). We do **not** introduce a competing pdfplumber abstraction.

If `LayoutDoc`'s shape needs minor extensions for tables (e.g., direct access to `.lines`, `.rects`, `.curves` per page — which pdfplumber exposes natively), those extensions go into the section-id codebase as small backward-compatible additions, not into a separate module. Coordination details in §12.

### 3.2 Module layout

```
docpluck/
  extract.py                ← unchanged
  extract_layout.py         ← from v1.6.0 — we consume; we may add page.lines/rects accessors
  extract_structured.py     ← NEW: top-level extract_pdf_structured() entry point
  tables/                   ← NEW package — table detection + structuring
    __init__.py             ← Table dataclass; public types only
    detect.py               ← caption-regex anchor + page-scope selection + bbox finalization
    cluster.py              ← lattice (ruling-line) cell clustering
    whitespace.py           ← lineless (column-gap) cell clustering
    render.py               ← cells → HTML, cells → markdown (future)
    confidence.py           ← scoring heuristic for structured-vs-isolated decision
  figures/                  ← NEW package — figure metadata extraction
    __init__.py             ← Figure dataclass; public types only
    detect.py               ← caption-regex anchor + bbox inference
  normalize.py              ← unchanged for v2.0
  quality.py                ← unchanged for v2.0
```

`tables/` is a package because the LOC estimate (~600–900) puts it above the comfortable single-file ceiling and the responsibilities (detection, lattice clustering, whitespace clustering, rendering, confidence scoring) split cleanly along file boundaries. `figures/` is a package mostly for symmetry with `tables/` — its v2.0 content is small enough to fit in one file, but levelling the two packages now means level-C work later doesn't need a refactor.

`extract_structured.py` is a thin orchestration file (~150 LOC) that runs `extract_pdf()` for the linear text, runs `extract_pdf_layout()` for the geometry, dispatches to `tables.detect.*` and `figures.detect.*`, applies the `table_text_mode` substitution, and assembles the result dict.

### 3.3 Pipeline composition

```
pdf_bytes
  │
  ▼  extract_pdf(pdf_bytes)                      → (raw_text, method)
  ▼  extract_pdf_layout(pdf_bytes)               → LayoutDoc          [v1.6.0 internal]
  │
  ▼  caption-regex pre-scan on raw_text          → set of pages with table/figure captions
  │  (skipped when thorough=True — all pages scanned)
  │
  ▼  for each candidate page:
  │     - tables.detect.find_tables(page)         → list[CandidateRegion]
  │     - figures.detect.find_figures(page)       → list[Figure]
  │
  ▼  for each table candidate region:
  │     - tables.cluster.lattice_cells(region)    → cells if ≥ N ruling lines
  │     - else tables.whitespace.text_cells(region) → cells if column-gap stable
  │     - else mark as kind="isolated", populate raw_text only
  │     - tables.render.cells_to_html(cells)      → html
  │     - tables.confidence.score(region, cells)  → 0.0..1.0
  │
  ▼  apply table_text_mode:
  │     "raw"         → text = raw_text unchanged
  │     "placeholder" → text = raw_text with table/figure regions substituted by markers
  │
  ▼  assemble result dict (§4)
```

Order matters: `extract_pdf()` runs *first* and unchanged so the SaaS app's existing call path continues working as if v2.0 didn't exist. `extract_pdf_layout()` runs *second* and produces the geometric data table/figure detection needs.

## 4. Data model

```python
# docpluck/extract_structured.py

from typing import Literal, Optional, TypedDict

class Cell(TypedDict):
    r: int                   # 0-indexed row
    c: int                   # 0-indexed column
    rowspan: int             # ≥ 1; v2.0 always emits 1 (level-C will set higher)
    colspan: int             # ≥ 1; v2.0 always emits 1 (level-C will set higher)
    text: str                # cell text, normalized via the same normalize.py subset
    is_header: bool          # heuristic flag; level-C will populate header_rows properly
    bbox: tuple[float, float, float, float]   # PDF points, origin bottom-left

TableKind = Literal["structured", "isolated"]
TableRendering = Literal["lattice", "whitespace", "isolated"]

class Table(TypedDict):
    id: str                  # stable per-doc ("t1", "t2", ...)
    label: Optional[str]     # "Table 1" parsed from caption; None if caption missing
    page: int                # 1-indexed
    bbox: tuple[float, float, float, float]
    caption: Optional[str]
    footnote: Optional[str]  # text below table matching footnote heuristics; None if absent
    kind: TableKind
    rendering: TableRendering
    confidence: Optional[float]   # 0.0..1.0 for "structured"; None for "isolated"
    n_rows: Optional[int]    # None for "isolated"
    n_cols: Optional[int]    # None for "isolated"
    header_rows: Optional[int]   # None for "isolated"; v2.0 always 1 when not None
    cells: list[Cell]        # empty list when kind="isolated"
    html: Optional[str]      # rendered from cells; None when "isolated"
    raw_text: str            # always populated — pdftotext slice of bbox region

class Figure(TypedDict):
    id: str                  # "f1", "f2", ...
    label: Optional[str]     # "Figure 3" parsed from caption; None if caption missing
    page: int
    bbox: tuple[float, float, float, float]
    caption: Optional[str]

class StructuredResult(TypedDict):
    text: str
    method: str              # extends existing method strings; see §4.1
    page_count: int
    tables: list[Table]
    figures: list[Figure]
    table_extraction_version: str   # = TABLE_EXTRACTION_VERSION
```

### 4.1 `method` string extension

`extract_pdf()` currently returns `method` ∈ {`"pdftotext_default"`, `"pdftotext_default+pdfplumber_recovery"`, `"error"`}. `extract_pdf_structured()` extends this:

| Path | `method` value |
|---|---|
| Normal text + table extraction | `"pdftotext_default+pdfplumber_tables"` |
| SMP-recovery + table extraction | `"pdftotext_default+pdfplumber_recovery+pdfplumber_tables"` |
| Thorough mode | suffix `+thorough` |
| Extraction error during table phase, text still recovered | `"pdftotext_default+pdfplumber_tables_failed"` |

Same `method` string convention as today: composable with `+` separators, parseable from left to right.

### 4.2 Decisions captured (so we can retrace later)

These decisions are baked into the schema. Documented here per the user's 2026-05-06 request:

- **Uniform schema with nullable fields, not tagged-union.** Every `Table` has the same fields; `kind="isolated"` rows just carry nulls/empties for the structured-only fields. Reason: easier to consume from JSON/Python without runtime type narrowing; matches the convention of `extract_pdf()` returning the same tuple shape regardless of which path ran. The `kind` field discriminates when consumers care.
- **`raw_text` always populated** — even for structured tables. Reason: cheap to compute (slice of pdftotext output by page region), gives consumers a fallback if our cell extraction is wrong, and is essential for "isolated" tables where it's the only content. Cost: ~10–50 KB extra per result for table-heavy papers; trivial.
- **PDF-native bbox coordinates** (points, origin bottom-left). Reason: native to pdfplumber/pdfminer, native to Mac PDF tools (Preview, Skim), native to TEI `<figure type="table" coords="...">`. Web/CSS conversion is a one-line transform if needed downstream.
- **1-indexed page numbers.** Reason: matches `pdftotext -f N -l N`, matches human convention, matches GROBID's TEI `coords="page,..."`. Internal pdfminer 0-indexing is converted at the boundary.
- **`confidence` is `Optional[float]`, not categorical.** Reason: a 0.0–1.0 score is more useful for filtering and lets us tune thresholds without an enum migration. Categorical could be derived later. `None` for `kind="isolated"` because confidence is meaningless when we explicitly didn't try to structure.
- **`html` rendered from `cells`, not from raw PDF.** Reason: single source of truth — if `cells` is wrong, `html` is wrong in the same way; consumers comparing the two never see a phantom mismatch. HTML rendering is deterministic table-of-cells → `<table><tr><td>` with no styling.
- **No `markdown` field in v2.0.** Reason: lossy on multi-row headers (level-C territory); easy to add later if a consumer asks; YAGNI.
- **No `figures` content beyond metadata at level A.** Reason: emitting raw_text from the figure region just *is* the false-positive content (axis labels, legend) we're removing from `text`. Better to drop it cleanly. Level-C revisits this with proper image extraction.
- **`TABLE_EXTRACTION_VERSION` recorded on every result**, mirroring `NORMALIZATION_VERSION` and the planned `SECTIONING_VERSION`. Bump policy in §9.

## 5. Detection algorithm

### 5.1 Caption-regex pre-scan (default `thorough=False` mode)

Run on `raw_text` (the linear pdftotext output). Match anchors per page using line-start regex:

```python
TABLE_CAPTION_RE = re.compile(
    r"^\s*Table\s+(?P<num>\d+)(?:[.:]|\s+[A-Z])",
    re.MULTILINE,
)
FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?:Figure|Fig\.?)\s+(?P<num>\d+)(?:[.:]|\s+[A-Z])",
    re.MULTILINE,
)
```

Use `LayoutDoc.page_offsets` (from section-id v1.6.0) to map each match back to a 1-indexed page number. The set of pages with at least one match is the candidate set passed to layout-aware detection. Pages without matches are skipped — saving roughly the linear fraction `pages_without_captions / total_pages` of pdfplumber cost.

When `thorough=True`, every page is a candidate.

**Why this regex shape:**
- `^\s*` — line-start, allowing for single-leading-space quirks of pdftotext output.
- `Table\s+\d+` / `Figure\s+\d+` / `Fig\.?\s+\d+` — the dominant academic conventions across APA, AMA, Vancouver, Nature, IEEE, Harvard, Chicago.
- `(?:[.:]|\s+[A-Z])` — must be followed by either punctuation (`Table 1.`, `Table 1:`) or a space + capitalized word (`Table 1 Descriptive…`). Excludes accidental matches in prose like "Table 1 was constructed by…" — wait, that *would* match. Acceptable: the prose match is rare and not harmful (it just adds a candidate page that would have been candidate anyway from the actual caption nearby).
- Does NOT match "Table" without a number, "Tabular", or table-of-contents leader-dot patterns.

**Known gap:** uncaptioned tables (rare in academic — one-off cases like a small data table embedded in methods text without a "Table N" prefix). Mitigated by `thorough=True` opt-in.

### 5.2 Table region detection per candidate page

For each candidate page in `LayoutDoc`:

1. **Caption anchoring.** Find the line(s) matching `TABLE_CAPTION_RE`. APA convention: caption *above* the table. Some publishers (Nature, Elsevier table-figure mixed conventions): caption may appear above or below. Search for table geometry both below (primary, ~250 PDF pt window) and above (secondary, ~150 pt window) the caption.
2. **Geometric clustering.** Within the search window, look for either:
   - **Lattice signal:** ≥ 2 horizontal ruling lines (`page.lines` filtered by `width / height` ratio > 5) with consistent left/right x-extent. Strong lattice signal: ≥ 4 horizontal lines OR any vertical lines at all (most academic tables don't use vertical rules; presence of any is decisive).
   - **Whitespace signal:** ≥ 3 consecutive y-clustered text rows where word-bbox column boundaries are stable within `0.5 × space-char-width` tolerance.
3. **Bbox finalization.** Union the bboxes of (a) the caption line, (b) any detected ruling lines, (c) the word-bbox cluster, (d) any text-block immediately below matching footnote heuristics (next paragraph). Pad ~5 pt for safety.
4. **Caption + footnote slicing.** From the linear `raw_text`, the caption is the matched line. The footnote is the run of text below the table matching `^\s*Note\.\s` OR `^\s*\*+p\s*[<>]` (APA footnote conventions) OR a smaller-font run (font-size < body × 0.92 per `LayoutDoc.chars`). Stops at the next paragraph break (≥ 2 blank lines).

If neither lattice nor whitespace signal is found inside the search window, but a caption matched: emit `kind="isolated"` with bbox = caption line bbox + 100 pt below, `raw_text` = the bbox slice of pdftotext output. Caller knows a table exists but we couldn't structure it.

### 5.3 Lattice cell clustering (`tables/cluster.py`)

When ≥ 2 horizontal ruling lines + (≥ 1 vertical line OR clean column-gap whitespace) exist:

1. Cluster horizontal segments by y-coordinate within 2-pt tolerance → row separators.
2. Cluster vertical segments by x-coordinate within 2-pt tolerance → column separators. If no vertical rules, derive column separators from word-cluster x-gaps inside the bbox.
3. Build a grid: cells are the rectangular regions bounded by adjacent row + column separators.
4. Assign each `LTChar` from `LayoutDoc.chars` (via pdfplumber's `.chars`) to the cell whose bbox contains its midpoint.
5. Concatenate chars within a cell, applying per-cell whitespace normalization (collapse runs of spaces, strip leading/trailing).
6. Emit `Cell(r, c, rowspan=1, colspan=1, text=..., is_header=heuristic, bbox=...)` for each grid cell.
7. Populate `Table.n_rows`, `Table.n_cols`, `Table.header_rows` from the grid (v2.0 always sets `header_rows=1` if any header detected, else `0`).

**Header heuristic for v2.0:** the first row whose font-weight average is bold OR whose font-size average is > body × 1.05 is marked `is_header=True`. v2.0 stops there. Level-C does proper multi-row header recovery with rowspan/colspan inference.

### 5.4 Whitespace cell clustering (`tables/whitespace.py`)

When no ruling lines but the caption matched and word-bbox column boundaries are stable across ≥ 3 rows:

1. Cluster words by y-coordinate (gap > 1.2 × line-height → new row).
2. Project all words in the row band onto the x-axis. Find the modal column boundaries by finding y-vertical "valleys" of zero-word density that persist across ≥ 60% of rows.
3. Assign each word to the column whose interval contains its x-midpoint.
4. Concatenate words within `(row, col)` to form cell text.
5. Emit `Cell(...)` per occupied `(row, col)`.
6. Populate `Table.n_rows`, `Table.n_cols`, `Table.header_rows` (= `1` if a bold/larger first row is detected, else `0`).

This is the path most APA tables take. It's also the most failure-prone — column boundaries can shift, words can straddle columns, footnote markers can attach to numbers ambiguously. The confidence score (§5.6) is calibrated to be cautious here.

### 5.5 HTML rendering (`tables/render.py`)

Trivial deterministic transform of `cells` to `<table>`:

```html
<table>
  <thead>  <!-- only if any cell has is_header=True -->
    <tr><th>...</th>...</tr>
  </thead>
  <tbody>
    <tr><td>...</td>...</tr>
    ...
  </tbody>
</table>
```

No styling, no class attributes, no inline style. Cell text is HTML-escaped (`&`, `<`, `>`). Empty cells render as `<td></td>`. v2.0 always emits `rowspan="1" colspan="1"` (omitted from output since they're the default).

### 5.6 Confidence scoring (`tables/confidence.py`)

Heuristic 0.0–1.0 score for structured tables. Inputs:

- `lattice` rendering: starts at 0.85; subtract 0.05 per row with cell count ≠ modal cell count; subtract 0.10 if any row has 0 cells; clamp to [0.5, 0.95].
- `whitespace` rendering: starts at 0.65; subtract 0.05 per row with cell count ≠ modal cell count; subtract 0.10 if column-boundary stability < 80% of rows; clamp to [0.4, 0.85].
- `isolated`: `confidence = None`.

Calibration target for v2.1: human spot-check correlation with TEDS on the eval corpus. v2.0 ships uncalibrated heuristic; consumers should treat it as a soft filter, not a probability.

**Decision threshold for "structured" vs. "isolated":** if the chosen rendering's pre-clamp score < 0.4, fall back to `kind="isolated"`. This biases toward isolation when the geometry is messy — explicitly preferred over emitting wrong-but-confident-looking cells (the GROBID failure mode we want to avoid).

### 5.7 Figure detection (`figures/detect.py`)

Simpler than tables. For each candidate page (caption regex hit on `^Figure \d+` / `^Fig\.? \d+`):

1. Caption is the matched line + continuation lines until next paragraph break.
2. Bbox: the union of (a) the caption line bbox, (b) the largest contiguous region of `LTRect` / `LTLine` / `LTCurve` graphics objects above the caption (figure typically renders above its caption in APA/most journals), capped at the column or page width.
3. Emit `Figure(id, label, page, bbox, caption)`.

If no graphics objects are found above the caption, search below (some publishers put figure above caption is dominant but not universal). If still nothing, set bbox to a 200 pt block above the caption line (best effort) and emit anyway — the bbox is approximate but the metadata (label, caption, page) is correct.

### 5.8 `table_text_mode` substitution

When `table_text_mode="raw"` (default): `text = raw_text` from `extract_pdf()`. Backwards-compatible.

When `table_text_mode="placeholder"`: starting from `raw_text`, for each detected table and figure in document order:
1. Find the bbox-corresponding char range in `raw_text`. Section-id v1.6.0 already needs a bbox→char-range function for its `F0` step (mapping page-bottom char clusters back to char offsets in `raw_text` via `LayoutDoc.page_offsets`); we reuse that. If section-id v1.6.0 internalizes it without a stable name, v2.0 lifts it into a small shared helper `extract_layout.bbox_to_char_range(layout, bbox, page) -> tuple[int, int]`.
2. Replace that range with `[Table N: caption]` (or `[Figure N: caption]`), terminated by `\n\n`.
3. If the caption is `None` or empty, use just `[Table N]` / `[Figure N]`.

Edge case: when a table region spans onto the *previous* page (rare — only happens for two-column papers where the bbox-to-text mapping can be off). v2.0 conservatively only replaces within the table's `page` field; cross-page bbox replacement is deferred (level C with multi-page stitching).

## 6. Public API

### 6.1 Python

```python
from docpluck import (
    extract_pdf,                 # unchanged
    extract_pdf_structured,      # NEW
    Table, Figure,               # NEW: TypedDict classes (also exported as types)
    TABLE_EXTRACTION_VERSION,    # NEW
)

# Default: caption-anchored fast path, raw text mode
result = extract_pdf_structured(pdf_bytes)
result["text"]            # str — same as extract_pdf()[0] in raw mode
result["method"]          # str — see §4.1
result["page_count"]
result["tables"]          # list[Table]
result["figures"]         # list[Figure]
result["table_extraction_version"]

# Opt in to placeholder text mode
result = extract_pdf_structured(pdf_bytes, table_text_mode="placeholder")

# Opt in to thorough scan (every page, no caption-anchoring shortcut)
result = extract_pdf_structured(pdf_bytes, thorough=True)

# Both
result = extract_pdf_structured(pdf_bytes, thorough=True, table_text_mode="placeholder")

# Filter to only high-confidence structured tables
high = [t for t in result["tables"]
        if t["kind"] == "structured" and (t["confidence"] or 0) >= 0.75]
```

### 6.2 CLI (additive)

```bash
# Existing
docpluck extract paper.pdf

# New
docpluck extract paper.pdf --structured                  # JSON to stdout
docpluck extract paper.pdf --structured --thorough
docpluck extract paper.pdf --structured --text-mode placeholder
docpluck extract paper.pdf --structured --tables-only    # omit figures
docpluck extract paper.pdf --structured --figures-only   # omit tables
docpluck extract paper.pdf --structured --html-tables-to ./out/  # write each table.html
```

CLI is additive only; existing flags unchanged.

### 6.3 No new top-level package exports beyond what's listed above

`Cell`, `TableKind`, `TableRendering` are exported from `docpluck.tables` for typing-deep consumers, but not from the top-level `docpluck`. Most callers won't need them.

## 7. Backwards-compatibility commitments

1. `extract_pdf(pdf_bytes) -> tuple[str, str]` — output byte-identical to v1.6.x for the entire test corpus.
2. `extract_docx(...)` and `extract_html(...)` — unchanged.
3. `normalize_text(...)` — unchanged.
4. CLI `docpluck extract paper.pdf` (no flags) — unchanged.
5. The SaaS app's `requirements.txt` git-pin can move from `@v1.6.x` to `@v2.0.0` and the existing extract endpoint must continue to work without code changes (only `extract_pdf()` is called from there at v2.0 launch).

Anything that breaks 1–5 is a bug, not a v2.0 migration.

## 8. Versioning

```python
# docpluck/extract_structured.py
TABLE_EXTRACTION_VERSION = "1.0.0"
```

Bump policy:

- **Major** — change that produces meaningfully different `tables` or `figures` output for the same input on a non-trivial set of papers.
- **Minor** — new fields added to the schema (forward-compatible — consumers ignoring unknown keys are unaffected); new caption regex variants matched.
- **Patch** — bug fixes that don't shift the dominant case.

Recorded on every `StructuredResult`. Independent of `__version__`, `NORMALIZATION_VERSION`, and `SECTIONING_VERSION`.

## 9. Performance budget

| Operation | Median target (30-page paper, 4 tables, 2 figures) |
|---|---|
| `extract_pdf()` (text-only, unchanged) | ≤ 0.4 s |
| `extract_pdf_layout()` (consumed from v1.6.0) | ≤ 1.5 s |
| Caption pre-scan + page-set selection | ≤ 0.05 s |
| Per-page table+figure detection (caption-anchored) | ≤ 0.3 s × 4 candidate pages = 1.2 s |
| `extract_pdf_structured()` end-to-end (default) | ≤ 3.5 s |
| `extract_pdf_structured()` end-to-end (thorough=True) | ≤ 12 s |

Slower than text-only — acceptable because (a) sectioning v1.6.0 already moves the SaaS pipeline into multi-second-per-paper territory, (b) structured extraction is opt-in (existing call sites get exactly today's performance), (c) batch processors typically run hundreds of papers in parallel where 3.5 s is well below the I/O bound.

If pdfplumber proves catastrophically slow on >100-pp papers, a per-table soft-cap fallback (emit `kind="isolated"` if structuring exceeds 0.5 s) is a known mitigation; deferred until QA surfaces a real case.

## 10. Error handling

- **Garbled-text PDF** (existing detection in `extract_pdf()` returning `"ERROR:"` prefix) — `extract_pdf_structured()` returns the same error in `text`/`method` and `tables=[]`, `figures=[]`.
- **PDF where pdfplumber fails to open** (e.g., encrypted, truly malformed) — text path may still succeed via pdftotext; `tables=[]`, `figures=[]`, `method` ends with `+pdfplumber_tables_failed`.
- **Per-table clustering exception** — caught in `tables/cluster.py` and `tables/whitespace.py`; the offending region falls back to `kind="isolated"`. One bad table doesn't poison the whole result.
- **Per-figure detection exception** — caught; that figure is omitted (we don't know its bounds enough to emit safely).
- **Missing pdfplumber** (extras not installed) — `extract_pdf_structured()` raises `ImportError` immediately with a message pointing to `pip install docpluck[all]`. We do *not* silently degrade to a degraded path because the caller explicitly chose the structured function.

No new exception classes. Failures degrade gracefully to `kind="isolated"` or empty lists rather than propagating.

## 11. Testing

### 11.1 Test corpus (committed under `tests/fixtures/structured/`)

**Smoke fixtures only for v2.0** (formal eval deferred to v2.1, see TODO.md):

- 4 lattice (full-grid) tables: 2 × Elsevier, 1 × IEEE, 1 × Springer/BMC.
- 4 APA-style lineless tables: 2 × descriptives (Table 1), 1 × correlation matrix (level-C target — v2.0 expected to fall back to `isolated`), 1 × regression (Table 3).
- 2 Nature-style minimal-rule tables.
- 2 figure-only fixtures (no tables, ≥ 1 figure with caption).
- 1 fixture with table-of-contents / list-of-tables (negative case — must NOT detect these as tables).
- 1 fixture with no tables and no figures (no false positives).
- 1 fixture with an uncaptioned data table (default mode misses it; `thorough=True` finds it).

Total ~15 PDFs. Hand-written per-PDF assertions (table count, figure count, n_rows / n_cols / specific cell values for at least one cell per structured table).

### 11.2 Test types

1. **Detection tests** — for each fixture, assert table count matches expected, figure count matches expected.
2. **Structure tests** — for fixtures with structured-expected tables, assert `n_rows`, `n_cols`, key cell values (`cells[r][c]["text"]`).
3. **Isolation tests** — for fixtures where structuring should fall back to isolated, assert `kind == "isolated"` and `raw_text` non-empty.
4. **Negative tests** — table-of-contents fixture asserts `len(tables) == 0`; clean-prose fixture asserts both lists empty.
5. **Schema tests** — every `StructuredResult` validates against the §4 schema (TypedDict + manual required-field check).
6. **Backwards-compat tests** — `extract_pdf(b)` byte-identical to v1.6.x output for the entire existing 153-test corpus.
7. **Text-mode tests** — `placeholder` mode produces `[Table 1: ...]` markers in the right positions; `raw` mode produces text identical to `extract_pdf()`.
8. **CLI tests** — invoke the new CLI flags, assert JSON shape.
9. **Regression snapshots** — golden JSON for each fixture, fail CI on drift if `TABLE_EXTRACTION_VERSION` is unchanged.

## 12. Coordination with section-id v1.6.0

Section-id (`docs/superpowers/specs/2026-05-06-section-identification-design.md`) is in active implementation per `docs/superpowers/plans/2026-05-06-section-identification.md`.

### 12.1 Hard dependency

Table extraction requires `LayoutDoc` from section-id Phase 4 (`docpluck/extract_layout.py`). We do not start implementing tables until that file exists on `main`.

### 12.2 Soft dependencies (parallelizable)

The non-LayoutDoc-dependent parts of v2.0 — caption regex constants, `Cell`/`Table`/`Figure` TypedDicts, HTML renderer, confidence scoring scaffold, smoke fixture corpus, CLI flag plumbing — can be built and tested in parallel with section-id phases 1–3 / 5–7 without conflict, since they don't touch `extract.py`, `normalize.py`, or any section-id-owned file.

### 12.3 F0 footnote-strip latent conflict

Section-id introduces an `F0` step in `normalize.py` that strips footnotes, running headers, and footers using `LayoutDoc`. The algorithm (per its spec §6.1) operates on "lines below the lowest body-text y-coordinate cluster on each page." Risk: a table sitting at the bottom of a page with its `Note. *p < .05.` footnote directly below could be mis-stripped — F0 would treat the table footnote as a page footnote and pull it into the document-level `footnotes` section.

This is a real bug in v1.6.0 in isolation. Mitigation:

- v1.6.0 ships with a known-issue note: "F0 may misclassify table-region footnotes; resolved when v2.0 lands."
- v2.0 patches F0 to skip stripping inside table bbox regions. Concretely: `normalize_text(text, layout=layout, table_regions=...)` accepts an optional list of table bboxes; F0 excludes lines inside those regions from its strip set. The table extraction pipeline can pre-compute table regions and pass them down.
- This is one ~30-line addition to `F0`, not a redesign.

### 12.4 LayoutDoc shape extensions

Section-id's `LayoutDoc.PageLayout` will minimally need:

- `page.lines` — `list[Line]` with `(x0, y0, x1, y1, width)` (pdfplumber exposes this directly).
- `page.rects` — `list[Rect]` with `(x0, y0, x1, y1)`.
- `page.curves` — `list[Curve]`.
- `page.chars` — `list[Char]` with `(x, y, font_name, font_size, weight, text)`.
- `page.words` — pre-clustered word boxes (pdfplumber's `extract_words()`).

If section-id doesn't already expose all of these (most are pdfplumber-native), table extraction adds them as small backward-compatible accessors. No structural change to `LayoutDoc`.

### 12.5 Coordination plan

1. Section-id ships v1.6.0 (target: per its plan).
2. v2.0 spec is approved (this doc).
3. v2.0 implementation begins after section-id Phase 4 commits (i.e., once `extract_pdf_layout` + `LayoutDoc` are on `main`).
4. v2.0 patches F0 to be table-region-aware.
5. v2.0 ships.

## 13. Implementation phases (rough — full plan via writing-plans skill)

Estimate: ~6–10 development days assuming a clean section-id Phase 4.

1. **Phase 1 — Data model + version constant.** `Cell`, `Table`, `Figure` TypedDicts; `TABLE_EXTRACTION_VERSION = "1.0.0"`; package skeleton. ~150 LOC. *No external deps; can ship before section-id Phase 4.*
2. **Phase 2 — Caption-regex pre-scan + page-set selection.** Pure regex on `raw_text`; no layout dependency yet. ~120 LOC. *No external deps; can ship before section-id Phase 4.*
3. **Phase 3 — Figure detection.** `figures/detect.py` end-to-end. ~200 LOC. *Requires section-id Phase 4 (LayoutDoc).*
4. **Phase 4 — Lattice cell clustering.** `tables/cluster.py` for ruling-line tables. ~250 LOC. *Requires section-id Phase 4 (LayoutDoc).*
5. **Phase 5 — Whitespace cell clustering.** `tables/whitespace.py` for lineless tables. ~300 LOC. *Requires section-id Phase 4 (LayoutDoc).*
6. **Phase 6 — Confidence + isolation fallback.** `tables/confidence.py` + integration. ~150 LOC. *Requires section-id Phase 4.*
7. **Phase 7 — HTML render + table_text_mode substitution.** `tables/render.py` + placeholder logic. ~150 LOC. *Requires section-id Phase 4 for bbox→char-range mapping.*
8. **Phase 8 — F0 patch.** Table-region awareness for section-id's footnote-strip step. ~50 LOC. *Requires section-id Phase 5 (the F0 step itself must exist on `main`).*
9. **Phase 9 — CLI + smoke fixtures + tests.** Build out smoke fixture corpus and CI. ~400 LOC including fixtures. *Fixture corpus can be assembled before section-id Phase 4.*
10. **Phase 10 — Documentation + release.** Update `README.md`, `DESIGN.md`, `BENCHMARKS.md` (preliminary numbers from smoke fixtures), `CHANGELOG.md`; tag `v2.0.0`; bump SaaS app `requirements.txt` git-pin per the two-repo release flow in `CLAUDE.md`. *Last step.*

Each phase is independently committable. Phases 1, 2, 9 (fixture-build sub-task) can land in parallel with section-id phases 1–7; phases 3–7 require section-id Phase 4 to have landed; phase 8 requires section-id Phase 5.

## 14. Open questions resolved during the brainstorm

For traceability — these are decisions made during the 2026-05-06 brainstorm, summarized here so future maintainers understand *why* the design is shaped this way:

| Q | Decision | Reason |
|---|---|---|
| Scope ambition for tables (A/B/C)? | **B** | Detect-only too thin; level-C delays v2.0 too long; B captures 80% of value with bounded risk. |
| Figure scope (A/B/C)? | **A** | We can't do much with figures right now (per user); detection is cheap and fixes axis-label false-positives flagged in DESIGN.md §1. Level-C deferred. |
| API surface? | **A — additive `extract_pdf_structured()`** | Existing 2-tuple contract is pinned by SaaS service; breaking it forces a coordinated bump across 4+ projects. Additive function lets new consumers opt in without disturbing old ones. |
| `text` field behavior? | **Default `"raw"`, opt-in `"placeholder"`** | Backwards-compatible default; placeholder mode is the explicit fix for stat-regex false positives. Other modes deferred to TODO.md. |
| Performance / detection scope? | **C — caption-anchored page scan default; opt-in `thorough=True`** | Typical paper drops from 9 s to ~1–2 s without sacrificing coverage on captioned tables (the dominant case). |
| Output schema details? | Locked per §4 | User delegated to author judgment with documented reasons; rationale captured in §4.2. |
| Validation corpus? | **D — smoke tests now, formal eval as v2.1** | Spec is already large; formal labeling is more valuable after seeing v2.0 output in production. |
| Coordination with v1.6.0? | **Sequence: v1.6.0 first, v2.0 after, share `LayoutDoc`** | Hard dependency on `LayoutDoc` makes parallel implementation unsafe; F0 latent conflict resolved in v2.0. |

## 15. Deferred items (TODO.md cross-reference)

All deferrals above are tracked in `TODO.md`. As of 2026-05-06 it captures:

- Tables level-C: multi-row headers, correlation matrices, footnote-marker linking, multi-page stitching, two-column-span detection, landscape rotation, 50-PDF eval corpus with TEDS target > 0.80.
- Figures level-C: image extraction, axis-label OCR, in-text reference resolution, type classification, subfigures.
- `table_text_mode` extensions: `"strip"`, `"inline_markdown"`, `"inline_html"`, per-type override, confidence-gated mode, custom template.
- Tables formal evaluation corpus (v2.1 milestone).

Add to TODO.md only when this doc is committed.
