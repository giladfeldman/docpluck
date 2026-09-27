# docpluck — API reference

This page documents every public function, parameter and output field of the `docpluck`
Python library. For what docpluck is, why it exists, installation and a quickstart, start with
the [project README](../README.md).

All names below are importable from the package root: `from docpluck import <name>`.

Contents: [structured extraction](#structured-extraction-v20) ·
[function reference](#api-reference) · [output schemas](#output-schemas) ·
[command-line interface](#command-line-interface) · [environment variables](#environment-variables) ·
[integration examples](#integration-examples) · [what gets fixed](#what-gets-fixed)

---

## Scope — read this before you build on the output

> **docpluck extracts and normalizes ENGLISH-language science articles written in US numeric
> convention (`.` decimal, `,` thousands).**
>
> **It canonicalises NOTATION. It does not fix the paper.**

European numbers pass through exactly as printed, and the paper's own errors (`p = 38.`,
`p < 05`) reach you untouched: detecting and flagging them is the job of the tool that holds the
parsed statistic. What docpluck does fix is damage its own pipeline caused — a glyph the text
layer lost, a fused exponent, a `<` extracted as `b`. Full statement: **[SCOPE.md](SCOPE.md)**.

---

## Structured extraction (v2.0)

For consumers that need tables and figures as structured data — meta-analysis tooling, statistical-claim extraction, dashboards — call `extract_pdf_structured()`:

```python
from docpluck import extract_pdf_structured

with open("paper.pdf", "rb") as f:
    result = extract_pdf_structured(f.read())

print(f"{result['page_count']} pages")
print(f"{len(result['tables'])} tables, {len(result['figures'])} figures")

for t in result["tables"]:
    print(f"  {t['label']} on page {t['page']} ({t['kind']}, confidence={t['confidence']})")
    if t["kind"] == "structured":
        print(f"    {t['n_rows']} rows × {t['n_cols']} cols")
    # v2.4.135: is `cells[].bbox` real geometry, or why not?
    print(f"    cell_geometry: {t['cell_geometry']}")
```

**`cell_geometry` (new in v2.4.135)** tells you whether to trust `cells[].bbox`. Until v2.4.135
every Camelot cell shipped `(0.0, 0.0, 0.0, 0.0)`; they are now real pdfplumber-space rectangles
`(x0, top, x1, bottom)` — but only where this field says so.

| value | `cells[].bbox` |
|---|---|
| `verified:<fraction>` | real — round-trip-checked against the page's own characters |
| `whitespace_native` | real — built directly from pdfplumber words |
| `no_cells` | there is no grid (caption-only / isolated table) |
| anything else (`camelot_rotated_page:…`, `grid_shape_mismatch:…`, `roundtrip_failed:…`, `no_layout`) | zeros — we refused rather than guess |

**`caption_status` (new, 2026-09)** says how sure docpluck is that a table is a *captioned* table.
Filter on it; do not infer it from `label`.

| value | meaning |
|---|---|
| `matched` | paired with a detected `Table N` caption |
| `none_found` | no caption, but the table itself is certain — the file declares it (a DOCX `w:tbl`) |
| `uncaptioned_candidate` | a PDF grid found on a page where no caption matched it. **Kept, not discarded** — it may be a real uncaptioned table, or text laid out in columns (a title block, a running header, the inside of a figure). `label` and `caption` are `None`; the id starts with `u`. Rendered Markdown shows these in a separate "Uncaptioned table candidates (unverified)" section. A grid that is demonstrably a copy of its own page's running text — no cell carries a statistic, and every line is found on that page of `text` — is not kept a second time; each such skip is counted in `fallbacks` as `camelot_candidate_is_page_running_text` (page in `fallback_details`); likewise a page-1 grid without statistics that the body's masthead test would strip (`camelot_candidate_is_page_masthead`). A grid with statistics is always kept, even when `text` repeats it word for word. |

Until 2026-09 such grids were silently discarded. Across the 102-paper test corpus that was about
400 grids in 83 papers; a sample of those kept is roughly half real statistical tables.

**Trust the boxes only on `verified` or `whitespace_native`.** Every way of getting this wrong
produces coordinates that are plausible and off by a page, which is worse than none. Measured over
69 shipped tables: 81.2% verified, 91.6% of cells carrying a real box. A verified bbox is the GRID
RECTANGLE for that (row, column) — not a promise that `cells[i]["text"]` is exactly the text
standing inside it.

### `fallbacks` — what the library silently did instead (read this)

Every result carries a record of the fallback paths that fired for **that document**. This is the
half of the story the text cannot tell you: a table Camelot detected and we discarded, a glyph
repair we refused because the evidence was ambiguous, a font whose Greek letters are unreliable.

```python
result = extract_pdf_structured(pdf_bytes)

result["fallbacks"]
# {'camelot_table_failed_table_likeness_gate': 26,
#  'symbol_font_greek_corruption_detected': 13}

result["fallback_details"]          # which font, which exception, which token
# {'symbol_font_greek_corruption_detected': {'AdvPS7DA6': 13}}
```

`{}` means **every detector ran and found nothing** — never "we did not look". A detector that
cannot run says so explicitly (`symbol_font_scan_not_run`), because a silent instrument and a clean
result must not look alike.

The same channel exists on the other two entry points:

```python
text, report = normalize_text(raw, NormalizationLevel.academic)
report.fallbacks, report.fallback_details

from docpluck.render import RenderReport
rep = RenderReport()
md = render_pdf_to_markdown(pdf_bytes, report=rep)
rep.fallbacks
```

Batch runs get it per file in the `<stem>.json` sidecar.

**Keys worth acting on immediately:**

| key | meaning |
|---|---|
| `symbol_font_greek_corruption_detected` | Greek letters in this document are unreliable — a Cronbach's α can arrive as `a5(.93)` |
| `ci_upper_minus_inferred_from_containment` | a CI sign was inferred, not read off the page — treat as a hypothesis |
| `w0j_mstat_sign_inferred_from_variable_name` | likewise |
| `w0h_ambiguous_pairing_refused` / `w0m_…` | a repair was declined; the token is what the paper printed |
| `camelot_table_*` / `region_grid_*` / `cells_grid_to_html_*` | a table or its rows were dropped by us |
| `flatten_dropped_*` | a parsed statistic was dropped from the structured sidecar |

Repairs are labelled by the **evidence** they rest on: *typographic* (something the renderer put on
the page) is acted on; *inferential* (what a number ought to be) is properly your call, and where we
keep such a repair it is declared here rather than applied silently. See `docs/SCOPE.md`.

### Modes

```python
# Default: caption-anchored fast path.
extract_pdf_structured(pdf_bytes)

# Thorough: scan every page for uncaptioned tables (slower).
extract_pdf_structured(pdf_bytes, thorough=True)

# Strip table/figure regions from `text` and replace with [Label: caption] markers.
extract_pdf_structured(pdf_bytes, table_text_mode="placeholder")
```

### CLI

```
docpluck extract paper.pdf --structured > out.json
docpluck extract paper.pdf --structured --thorough --text-mode placeholder
docpluck extract paper.pdf --structured --html-tables-to ./out/
```

`extract_pdf()` (the v1 text-only path) is unchanged. New consumers opt in to the structured path; existing consumers see no behavioral change.

The full schema of every field is under [Output schemas](#output-schemas) below.

---

## API Reference

### `extract_pdf(pdf_bytes, *, sections=None, max_input_bytes=None, pdftotext_timeout_seconds=120) → tuple[str, str]`

Extract text from PDF bytes.

**Parameters:**
- `pdf_bytes` — Raw PDF file content as `bytes`
- `sections` — optional list of section labels (`["abstract", "methods"]`); only those sections' text is returned, in document order. Labels are `SectionLabel` values.
- `max_input_bytes` — optional size cap; a larger input raises `ValueError`
- `pdftotext_timeout_seconds` — timeout for the `pdftotext` subprocess

**Returns:** `(text, method)` tuple where:
- `text` — Extracted plain text. Check `text.startswith("ERROR:")` for failure.
- `method` — Engine used:
  - `"pdftotext_default"` — standard extraction
  - Optionally followed by `+column_corrected:<pages>` when two-column pages were re-extracted in reading order, or `+column_correction_failed:<exception>` when that re-extraction raised (the uncorrected text is returned).
  - `"error"` when extraction failed (the text then starts with `ERROR:`).
  - An undecodable glyph that pdftotext emits as `U+FFFD` is returned by `extract_pdf` **unchanged**. (The earlier
    `+pdfplumber_recovery` fallback was retired in 2026-09: it could substitute a plausible wrong token, such as
    turning a partial eta-squared into an R-squared.) `normalize_text` still rewrites `U+FFFD` in two narrow
    statistical contexts — step S5a (`eta` before `2 =`) and step S5b (`>=`/`<=` before a number) — and leaves it
    everywhere else.

**Requires:** `pdftotext` binary on PATH.

```python
with open("paper.pdf", "rb") as f:
    text, method = extract_pdf(f.read())

if text.startswith("ERROR:"):
    raise RuntimeError(f"Extraction failed: {text}")
```

### `extract_pdf_file(path) → tuple[str, str]`

`extract_pdf` for a file on disk: reads `path` (a `str` or `pathlib.Path`) and returns the same `(text, method)`.

### `extract_pdf_layout(pdf_bytes, *, pages=None) → LayoutDoc`

The **layout channel**: reads the PDF with pdfplumber and returns a `LayoutDoc` with `pages` (one `PageLayout` per page: `width`, `height`, text `spans`, `words`, and `chars` — pdfplumber's per-character dicts with font name, size and position), `raw_text`, `page_offsets` and `populated_pages`. `pages=` restricts it to some page indices. Tables, figures and the font-evidence glyph repairs read this channel; text for sections and normalization comes from `extract_pdf`, never from here.

---

### `extract_docx(docx_bytes, *, sections=None, max_input_bytes=None) → tuple[str, str]`

Extract text from DOCX (Word) file bytes via `mammoth`.

**Parameters:**
- `docx_bytes` — Raw DOCX file content as `bytes`

**Returns:** `(text, method)` tuple where `method` is always `"mammoth"`.

**How it works:** DOCX is converted to HTML first (preserving Shift+Enter soft breaks as `<br>` tags), then passed through the same block/inline-aware tree-walk used by `extract_html()`. This preserves paragraph structure, headings, lists, and soft breaks — which `mammoth.extract_raw_text()` would lose.

**Requires:** `pip install docpluck[docx]` (adds `mammoth>=1.8.0`).

**Known limitations:**
- **OMML equations** (Office Math) are silently dropped. Inline stats written as plain text survive; stats inside equation objects do not.
- **Tracked changes**: only deleted paragraphs are handled minimally.
- **Memory**: peak usage is ~3–5× file size.

```python
from docpluck import extract_docx

with open("paper.docx", "rb") as f:
    text, method = extract_docx(f.read())
```

---

### `extract_html(html_bytes, *, sections=None, max_input_bytes=None) → tuple[str, str]`

Extract text from HTML file bytes via `beautifulsoup4` + `lxml`.

**Parameters:**
- `html_bytes` — Raw HTML file content as `bytes` (UTF-8 decoded with error replacement)

**Returns:** `(text, method)` tuple where `method` is always `"beautifulsoup"`.

**How it works:** Custom tree-walk that distinguishes block from inline elements:
- **Block elements** (`<p>`, `<div>`, `<h1>`–`<h6>`, `<li>`, `<td>`, etc.) get newlines before and after.
- **Inline elements** (`<a>`, `<span>`, `<em>`, etc.) get spaces before and after — critical for preventing merged words like `"ChanORCID"` when adjacent inline elements have no whitespace between them.
- **Ignored tags** (`<script>`, `<style>`, `<meta>`, `<svg>`, `<iframe>`, etc.) are decomposed before walking.

**Why not `BeautifulSoup.get_text()`**: `get_text()` cannot distinguish block from inline elements — it applies a uniform separator everywhere, which either merges paragraphs or inserts spurious whitespace. The BeautifulSoup maintainer has [confirmed](https://bugs.launchpad.net/bugs/1768330) this will not be fixed. A custom tree-walk is required.

**Requires:** `pip install docpluck[html]` (adds `beautifulsoup4>=4.12.0` and `lxml>=5.0.0`).

```python
from docpluck import extract_html, html_to_text

# From bytes
with open("article.html", "rb") as f:
    text, method = extract_html(f.read())

# From an already-decoded string
text = html_to_text("<p>Hello <a>world</a></p>")
```

---

### `count_pages(pdf_bytes: bytes) → int`

Count pages in a PDF using byte pattern matching. No external binary required. **PDF only** — DOCX has no page model, and HTML has no pages.

```python
with open("paper.pdf", "rb") as f:
    content = f.read()
    n = count_pages(content)
print(f"{n} pages")
```

---

### `normalize_text(text, level, *, layout=None, table_regions=None, preserve_math_glyphs=False, dropped_minus_layout=None) → tuple[str, NormalizationReport]`

Apply the normalization pipeline at the specified level.

**Parameters:**
- `text` — Raw extracted text
- `level` — `NormalizationLevel.none` | `NormalizationLevel.standard` | `NormalizationLevel.academic`
- `layout` — optional `LayoutDoc` from `extract_pdf_layout`; enables the layout-aware strip of running headers, footers and footnotes (step F0) and fills `footnote_spans` / `page_offsets`
- `table_regions` — optional list of `{"page": int, "bbox": (x0, top, x1, bottom)}`; with `layout`, lines inside a table are never stripped as footnotes (keeps `Note. *p < .05.`)
- `preserve_math_glyphs` — `True` skips the Greek/math transliteration step (A5), keeping `β`, `η²`, `≥` as printed; this is what the Markdown renderer uses
- `dropped_minus_layout` — optional `LayoutDoc`; lets step W0h recover a minus sign the text layer lost by reading the surviving glyph from the layout channel

**Returns:** `(normalized_text, report)` tuple.

**Normalization levels:**

| Level | Steps | Use when |
|-------|-------|----------|
| `none` | — | You want raw text, no modifications |
| `standard` | Core cleanup (`S*`) + document-shape cleanup (`F0/H0/T0/P0/P1/W0`) + recovery/ref joins (`R2/R3/A7`) | General text processing (NLP, search indexing) |
| `academic` | `standard` + statistical repairs (`A*` and `W0*`) | Statistical pattern matching, meta-analysis |

```python
from docpluck import normalize_text, NormalizationLevel

# Raw text
text, _ = normalize_text(raw, NormalizationLevel.none)

# General cleanup
text, report = normalize_text(raw, NormalizationLevel.standard)

# Full statistical repair (recommended for academic PDFs)
text, report = normalize_text(raw, NormalizationLevel.academic)

print(report.version)          # e.g., "1.9.35"
print(report.steps_applied)    # ["S0_smp_to_ascii", "S1_encoding_validation", ...]
print(report.changes_made)     # {"ligatures_expanded": 27, "dashes_normalized": 3, ...}
```

**`NormalizationReport` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `level` | `str` | Level used: `"none"`, `"standard"`, or `"academic"` |
| `version` | `str` | Pipeline version (e.g. `"1.9.35"`) |
| `steps_applied` | `list[str]` | Step codes that ran, in order (e.g. `["S1_encoding_validation", "S3_ligature_expansion"]`) |
| `steps_changed` | `list[str]` | The subset of steps that actually changed the text |
| `changes_made` | `dict[str, int]` | Change counts per change type |
| `changes_made_by_step` | `dict[str, int]` | Characters changed per step |
| `footnote_spans` | `tuple[tuple[int, int], ...]` | Character spans of stripped footnotes (needs `layout`) |
| `footnote_texts` | `tuple[str, ...]` | The stripped footnote texts, so nothing is silently lost |
| `page_offsets` | `tuple[int, ...]` | Start offset of each page in the returned text |
| `residual_control_chars` | `int` | Non-space control characters still in the returned text |
| `column_interleave_pages` | `tuple[int, ...]` | Pages detected as read across both columns |
| `fallbacks` | `dict[str, int]` | Fallback events during normalization (see [`fallbacks`](#fallbacks--what-the-library-silently-did-instead-read-this)) |
| `fallback_details` | `dict[str, dict[str, int]]` | The specific font/token behind each event |

---

### `compute_quality_score(text: str) → dict`

Compute extraction quality metrics.

**Returns:**

```python
{
    "score": 85,                    # 0–100 composite score
    "common_word_ratio": 0.142,     # fraction of first 2000 words that are common English words
    "garbled": False,               # common_word_ratio < 0.02 AND (a corruption signal OR < 500 chars)
    "confidence": "high",           # "high" (≥80), "medium" (≥50), "low" (<50)
    "details": {
        "ligatures_remaining": 0,   # count of ff/fi/fl ligature chars not yet expanded
        "garbled_chars": 0,         # count of U+FFFD replacement characters
        "non_ascii_ratio": 0.031,   # fraction of non-ASCII characters
        "has_corruption_signal": False,  # any U+FFFD, > 20% non-ASCII, or >= 20 ligatures
    }
}
```

**Interpreting the score:**

| Score | Meaning |
|-------|---------|
| ≥ 80 | High quality — proceed with analysis |
| 50–79 | Medium — check manually if precision matters |
| < 50 | Low — likely garbled (column merge, encoding failure, or non-English) |

```python
quality = compute_quality_score(text)

if quality["garbled"]:
    print("Extraction likely failed — skipping this paper")
elif quality["score"] < 50:
    print(f"Low quality ({quality['score']}) — verify manually")
```

### `extract_sections(file_bytes=None, *, text=None, source_format=None, preserve_math_glyphs=False, normalization_level=None) → SectionedDocument`

Identify a paper's structure — abstract, introduction, methods, results, discussion,
references, and the endmatter around them. Works on PDF, DOCX and HTML.

```python
from docpluck import extract_sections, SectionLabel

with open("paper.pdf", "rb") as f:
    doc = extract_sections(f.read(), source_format="pdf")

for section in doc.sections:
    print(section.label, len(section.text))

results = [s for s in doc.sections if s.label == SectionLabel.RESULTS]
```

Pass `file_bytes` with `source_format` (`"pdf"`, `"docx"`, `"html"`), or `text=` for text you
already extracted. `normalization_level` overrides the level used before sectioning;
`preserve_math_glyphs` is passed to `normalize_text`.

Every character of the source belongs to exactly one section — the partition is total, so
nothing is silently dropped. Unrecognised spans carry `SectionLabel.unknown` rather than
being merged into a neighbour. Pipeline version: `SECTIONING_VERSION`.

**`SectionedDocument`**: `sections` (tuple of `Section`), `normalized_text` (the buffer the
offsets index into), `sectioning_version`, `source_format`, and `sectioning_text_id` — a
fingerprint from `sectioning_text_id(text, sectioning_version)` so a consumer can tell whether
stored offsets still refer to the same text and the same algorithm. Helpers:
`doc.abstract` / `.introduction` / `.methods` / `.results` / `.discussion` / `.references`
(first section with that canonical label, or `None`), `doc.all(label)` (every section with
that canonical label — `methods`, `methods_2`, ...), `doc.get(label)` (exact label),
`doc.text_for(*labels)` (their text joined in document order) and `doc.to_dict()`.

**`Section`**: `label` (`"methods"`, `"methods_2"`), `canonical_label` (`SectionLabel`),
`text`, `char_start` / `char_end` (offsets into `normalized_text`), `pages`, `confidence`
(`Confidence`: `high`, `medium`, `low`), `detected_via` (`DetectedVia`: `heading_match`,
`markup`, `layout_signal`, `text_pattern_fallback`, `position_inferred`), `heading_text`
(the heading as printed, if any) and `subheadings` (unrecognised headings inside it).

**`SectionLabel` values**: `title_block`, `abstract`, `keywords`, `author_note`,
`introduction`, `literature_review`, `methods`, `results`, `discussion`,
`general_discussion`, `conclusion`, `acknowledgments`, `funding`, `conflict_of_interest`,
`data_availability`, `author_contributions`, `references`, `appendix`, `supplementary`,
`footnotes`, `study_n_header`, `unknown`.

### `flatten_tables_for_paper(tables) → list[FlattenedRow]`

Turn structured tables into one record per cell-with-a-statistic, in document order —
suitable for direct JSONL emission. This is what the service exposes as
`?flatten_tables_inline=true`; the library API is documented here so a direct consumer
does not have to go through HTTP to reach it.

```python
from docpluck import extract_pdf_structured, flatten_tables_for_paper, render_flattened_inline

with open("paper.pdf", "rb") as f:
    result = extract_pdf_structured(f.read())

rows = flatten_tables_for_paper(result.tables)
for row in rows:
    print(row)                        # one dict per flattened cell

# Or render one table back into text for inline splicing:
md = render_flattened_inline(rows, table_id="T1", label="Table 1")
```

`flatten_table` handles a single `Table` when you do not want the whole paper.

**Every row carries `caption_status`** — the source table's (see the table above):
`matched`, `none_found`, or `uncaptioned_candidate`. Rows from an `uncaptioned_candidate`
table come from a grid no caption claimed. Roughly half of those are real statistical
tables and half are page furniture (running headers, title blocks, the insides of
figures), so **if you run statistical checks on these rows, decide explicitly what to do
with `uncaptioned_candidate`** — they are included so that real statistics are not lost,
and labelled so that you can filter them.
Watch `report.fallbacks` for `flatten_dropped_*` keys — they mean a parsed statistic did
not survive into the sidecar (see [`fallbacks`](#fallbacks--what-the-library-silently-did-instead-read-this)).

### `symbol_contract() → dict` and `explain_symbol(char) → str`

**If you parse docpluck's output, build your patterns from this rather than from samples.**
`symbol_contract()` returns the authoritative, machine-readable mapping of every Greek
letter and sub/superscript form docpluck emits at `normalize_level="academic"`.

```python
from docpluck import symbol_contract, explain_symbol, SYMBOL_CONTRACT_VERSION

contract = symbol_contract()          # {'greek': {'χ': 'chi', 'η': 'eta', ...}, ...}
explain_symbol("η")                   # 'eta'
```

Copying the tables into your own code is how two tools end up disagreeing about what
`chi2` means. Ask the contract. Full prose reference: [SYMBOL_CONTRACT.md](./SYMBOL_CONTRACT.md).

### `extract_pdf_structured(pdf_bytes, *, thorough=False, table_text_mode="raw", max_input_bytes=None, extract_timeout_seconds=120) → StructuredResult`

Text plus tables and figures from a PDF; see [Structured extraction](#structured-extraction-v20)
for the modes and [Output schemas](#output-schemas) for every field. `table_text_mode` is
`"raw"` (table text stays in `text`) or `"placeholder"` (table and figure regions are replaced
by `[Label: caption]` markers). `extract_timeout_seconds` bounds the text extraction.
`TABLE_EXTRACTION_VERSION` versions the table pipeline and is echoed as
`result["table_extraction_version"]`.

### `extract_docx_structured(docx_bytes, *, max_input_bytes=None) → StructuredResult`

Text plus tables from a DOCX, in the **same** `StructuredResult` shape as the PDF path, so one
consumer handles both. The grid is read from the document's own table markup (`w:tbl`), so
`rendering` is `"markup"`, `caption_status` is `matched` or `none_found`, and `method` is
`"mammoth+tables:mammoth"`. Two values are deliberate, not missing features: `page_count` is
`0` (a DOCX has no page model; pagination depends on the program that opens it) and `figures`
is `[]` (DOCX figure extraction is not implemented). Requires `[docx]`.

```python
from docpluck import extract_docx_structured

with open("paper.docx", "rb") as f:
    result = extract_docx_structured(f.read())
for t in result["tables"]:
    print(t["id"], t["label"], t["n_rows"], "x", t["n_cols"])
```

### `render_pdf_to_markdown(pdf_bytes, *, normalization_level=NormalizationLevel.academic, flatten_tables_inline=False, report=None) → str`

The whole paper as Markdown: title, section headings, body text with Greek letters and math
glyphs as printed, tables as HTML under their captions, figure captions, and a separate
"Uncaptioned table candidates (unverified)" section. `flatten_tables_inline=True` adds a
readable one-sentence-per-row block below each table, bounded by HTML-comment markers.

Pass a `RenderReport()` as `report` to learn what the post-processing did:

| field | meaning |
|---|---|
| `steps_applied` | post-processing steps that ran |
| `steps_changed` | the steps that changed the Markdown |
| `lines_removed` | each removed line, with the step that removed it |
| `chars_delta` | net characters added or removed by post-processing |
| `render_version` | version of the post-processing chain |
| `fallbacks`, `fallback_details` | every fallback event beneath the render, including table extraction and sectioning |

```python
from docpluck import render_pdf_to_markdown, RenderReport

rep = RenderReport()
md = render_pdf_to_markdown(pdf_bytes, report=rep)
print(rep.steps_changed, rep.fallbacks)
```

### `extract_to_dir(pdf_paths, out_dir, level=NormalizationLevel.academic, write_sidecar=True) → ExtractionReport`

Batch extraction. For each PDF it writes `<stem>.txt` (normalized text) and, unless
`write_sidecar=False`, a `<stem>.json` sidecar with that file's result. A failure on one file
is recorded, not raised.

**`ExtractionReport`** — the reproducibility receipt: `docpluck_version`, `normalize_version`,
`git_sha`, `git_state`, `level`, `out_dir`, `symbol_contract_version`, `sectioning_version`,
`table_extraction_version`, `python_version`, `unicodedata_version`, `pdftotext_path`,
`pdftotext_version`, `pdftotext_engine`, `poppler_version`, `pdfplumber_version`,
`pdfminer_six_version`, `camelot_version`, `pypdfium2_version`, `opencv_version`,
`mammoth_version`, `beautifulsoup4_version`, `lxml_version`, `n_total`, `n_ok`, `n_failed`,
`elapsed_seconds` and `results`. `report.to_dict()` serialises it; `report.write_receipt(path)`
writes it as JSON.

**`ExtractionFileResult`** (one per file in `results`):

| field | meaning |
|---|---|
| `path`, `ok`, `error` | the input, whether it succeeded, and the error if not |
| `method` | the `extract_pdf` method string |
| `n_chars_raw`, `n_chars_normalized` | length before and after normalization |
| `n_replacement_chars` | U+FFFD count in the output — glyphs lost before docpluck saw them |
| `n_greek_chars` | Greek letters in the output |
| `normalize_steps_changed` | normalization steps that changed this file |
| `layout_available`, `layout_error` | whether the layout channel could be read (needed for the font-evidence repairs) |
| `fallbacks`, `fallback_details` | fallback events for this file |
| `elapsed_seconds` | time taken |

`count_replacement_chars(text)` and `count_greek_chars(text)` compute the two counts on any
text.

### `get_version_info() → dict`

Every version input that can change docpluck's output; see
[Reproducibility receipts](#reproducibility-receipts) for the keys. This is what
`docpluck --version` prints.

---

## Output schemas

`StructuredResult`, `Table`, `Cell`, `Figure` and `FlattenedRow` are typed dictionaries: read
them with `result["tables"]`, not attribute access. They serialise to JSON as-is (this is
what `docpluck extract --structured` prints).

### `StructuredResult`

| key | type | meaning |
|---|---|---|
| `text` | `str` | the document text (tables replaced by markers when `table_text_mode="placeholder"`) |
| `method` | `str` | extraction path, as for `extract_pdf` / `"mammoth+tables:mammoth"` for DOCX |
| `page_count` | `int` | pages (`0` for DOCX) |
| `tables` | `list[Table]` | tables in document order |
| `figures` | `list[Figure]` | figures (`[]` for DOCX) |
| `table_extraction_version` | `str` | `TABLE_EXTRACTION_VERSION` |
| `fallbacks` | `dict[str, int]` | fallback events for this document |
| `fallback_details` | `dict[str, dict[str, int]]` | which font, token or exception each event names |

### `Table`

| key | type | meaning |
|---|---|---|
| `id` | `str` | id within the document, e.g. `t2` or `camelot_t5`; uncaptioned candidates are `u1`, `u2`, ... |
| `label` | `str \| None` | `"Table 1"`; `None` for an uncaptioned candidate |
| `page` | `int` | 1-based page (DOCX: `0`) |
| `bbox` | `(x0, top, x1, bottom)` | table region in pdfplumber page coordinates |
| `caption` | `str \| None` | caption text |
| `footnote` | `str \| None` | table note (`Note. ...`) |
| `kind` | `"structured"` \| `"isolated"` | a cell grid, or a caption-only table whose grid could not be captured |
| `rendering` | `"lattice"` \| `"whitespace"` \| `"isolated"` \| `"markup"` | how the grid was obtained: ruled lines, whitespace alignment, not at all, or DOCX markup |
| `confidence` | `float \| None` | capture quality in [0, 1]: `(accuracy/100) * (1 - whitespace/100)` |
| `accuracy` | `float \| None` | Camelot's structural accuracy, 0–100 |
| `whitespace` | `float \| None` | share of empty cells in the shipped grid, 0–100 |
| `camelot_flavor` | `"stream"` \| `"lattice"` \| `None` | which Camelot parser won; `None` when not from Camelot |
| `n_rows`, `n_cols`, `header_rows` | `int \| None` | grid dimensions and number of header rows |
| `cells` | `list[Cell]` | the grid |
| `html` | `str \| None` | the table as HTML |
| `raw_text` | `str` | the region's text as extracted |
| `cell_geometry` | `str \| None` | whether `cells[].bbox` is real — see the table under [Structured extraction](#structured-extraction-v20) |
| `caption_status` | `"matched"` \| `"none_found"` \| `"uncaptioned_candidate"` | how sure docpluck is this is a captioned table |

### `Cell`

| key | type | meaning |
|---|---|---|
| `r`, `c` | `int` | 0-based row and column |
| `rowspan`, `colspan` | `int` | spans |
| `text` | `str` | cell text |
| `is_header` | `bool` | part of the header rows |
| `bbox` | `(x0, top, x1, bottom)` | the cell's grid rectangle; zeros unless `cell_geometry` says it is real |

### `Figure`

| key | type | meaning |
|---|---|---|
| `id` | `str` | id within the document, e.g. `f1` |
| `label` | `str \| None` | `"Figure 1"` |
| `page` | `int` | 1-based page |
| `bbox` | `(x0, top, x1, bottom)` | figure region |
| `caption` | `str \| None` | caption text |

### `FlattenedRow`

| key | type | meaning |
|---|---|---|
| `table_id`, `page`, `label` | | the source table |
| `row_idx` | `int` | 0-based body-row index |
| `row_label` | `str` | the row's label cell (left-most non-numeric cell, else the first cell) |
| `header` | `list[str]` | column headers |
| `raw_cells` | `list[str]` | the row's cells, same length as `header` |
| `sentence` | `str` | the row as an English sentence, e.g. `"Importance: t(741) = 3.93, p < .001, d = 0.29"` |
| `fields` | `dict` | parsed statistical values (may be empty) |
| `caption_status` | `str` | the source table's `caption_status` |

`render_flattened_inline(records, *, table_id, label=None, version=None)` renders one table's
rows as a Markdown block bounded by HTML-comment markers.

---

## Command-line interface

`docpluck` (or `python -m docpluck`). The input type is chosen from the file extension
(`.pdf`, `.docx`, `.html`, `.htm`); output is UTF-8 on standard output.

```
docpluck --version                                   # JSON: get_version_info()
docpluck extract FILE [--sections L1,L2]             # text (all or some sections)
docpluck extract FILE --structured [--thorough] [--text-mode raw|placeholder]
                      [--tables-only | --figures-only] [--html-tables-to DIR]
docpluck sections FILE [--format json|summary]       # SectionedDocument
docpluck render FILE [--level none|standard|academic]
                     [--flatten-tables-inline] [--tables-jsonl PATH]
```

| option | applies to | effect |
|---|---|---|
| `--sections L1,L2` | `extract` | only those sections' text |
| `--structured` | `extract` | `StructuredResult` as JSON (PDF, DOCX) |
| `--thorough` | `extract --structured` | scan pages with no table caption too (PDF) |
| `--text-mode raw\|placeholder` | `extract --structured` | table regions in `text` (PDF) |
| `--tables-only`, `--figures-only` | `extract --structured` | omit the other list |
| `--html-tables-to DIR` | `extract --structured` | write each table's HTML to `DIR/<id>.html` |
| `--format json\|summary` | `sections` | full JSON, or one line per section |
| `--level` | `render` | normalization level (default `academic`) |
| `--flatten-tables-inline` | `render` | readable row sentences below each table |
| `--tables-jsonl PATH` | `render` | every `FlattenedRow` to `PATH` as JSON Lines |

---

## Environment variables

All default to off; set to `1` to enable.

| variable | effect |
|---|---|
| `DOCPLUCK_FALLBACK_LOG` | print each fallback event to standard error as it is recorded |
| `DOCPLUCK_DISABLE_CAMELOT` | do not run Camelot; tables come only from the non-Camelot capture paths |
| `DOCPLUCK_COLUMN_CORRECT_GENERAL` | experimental: two-column re-ordering on more pages, still only with a clean central gutter and every word preserved |
| `DOCPLUCK_COLUMN_CORRECT_BANDED` | experimental: per-band re-extraction for mixed-layout pages the whole-page corrector skips |
| `DOCPLUCK_RCT_L2_BYPASS` | diagnostic: turns off two table-region guards so their effect can be measured |

---

## Integration Examples

### Statistical-reporting checks

```python
from docpluck import extract_pdf, normalize_text, NormalizationLevel, compute_quality_score
import re

def extract_stats(pdf_path: str) -> list[dict]:
    with open(pdf_path, "rb") as f:
        text, method = extract_pdf(f.read())

    normalized, report = normalize_text(text, NormalizationLevel.academic)

    quality = compute_quality_score(normalized)
    if quality["garbled"]:
        return []  # Skip garbled papers

    # Now apply your statistical patterns to `normalized`
    # e.g. find t-tests, F-tests, correlations, p-values
    p_values = re.findall(r'p\s*[<=>]\s*\.?\d+', normalized)
    return p_values
```

### Batch processing

```python
from docpluck import extract_pdf, normalize_text, NormalizationLevel, compute_quality_score
from pathlib import Path

def process_corpus(pdf_dir: str) -> list[dict]:
    results = []
    for pdf_path in Path(pdf_dir).glob("**/*.pdf"):
        with open(pdf_path, "rb") as f:
            text, method = extract_pdf(f.read())

        if text.startswith("ERROR:"):
            results.append({"file": pdf_path.name, "error": text})
            continue

        normalized, report = normalize_text(text, NormalizationLevel.academic)
        quality = compute_quality_score(normalized)

        results.append({
            "file": pdf_path.name,
            "chars": len(normalized),
            "method": method,
            "quality": quality["score"],
            "garbled": quality["garbled"],
        })

    return results
```

### Reproducibility receipts

A docpluck version alone does **not** pin extraction. `pdftotext_default` shells
out to whatever poppler (or Xpdf) binary is on `PATH`; tables and layout run
through camelot and pdfplumber; DOCX runs through mammoth and HTML through
beautifulsoup4/lxml; and `normalize_text` applies `unicodedata.normalize`, whose
behaviour is fixed by the Unicode database your CPython shipped with. Every one
of those can change under a fixed docpluck SHA, so `get_version_info()` reports
all of them:

```python
from docpluck import get_version_info

get_version_info()
# {'version': '2.4.146',            # docpluck itself
#  'git_sha': '…',
#  'normalize_version': '1.9.69',   # in-repo pipeline versions, bumped
#  'sectioning_version': '1.2.5',   #   independently of the package version
#  'table_extraction_version': '2.4.17',
#  'python_version': '3.14.5',      # the interpreter…
#  'unicodedata_version': '16.0.0', #   …and its Unicode database
#  'pdftotext_path': 'C:/…/pdftotext.EXE',  # the exact binary extraction runs
#  'pdftotext_version': '24.08.0',  # the system binary, NOT pinned by the SHA
#  'pdftotext_engine': 'poppler',   # 'poppler' | 'xpdf' | 'unknown'
#  'poppler_version': '24.08.0',    # None when the engine is not poppler
#  'pdfplumber_version': '0.11.9',  # PDF layout channel…
#  'pdfminer_six_version': '…',     #   …and the text engine under it
#  'camelot_version': '2.0.0',      # tables…
#  'pypdfium2_version': '5.9.0',    #   …and what lattice rasterizes through
#  'opencv_version': '4.13.0.92',
#  'mammoth_version': '1.12.0',        # DOCX
#  'beautifulsoup4_version': '4.13.5', # HTML
#  'lxml_version': '6.1.1'}
```

Engines that are not installed report `"not installed"` rather than being
omitted, so an absent optional extra is visible instead of invisible.

`pdftotext_engine` is reported separately because poppler and Xpdf differ
*behaviourally*, not just in version number (Xpdf 4.x emits `\n\n` paragraph
breaks where poppler emits `\n`), and both banner themselves as
"pdftotext version N".

`extract_to_dir()` records the same fields on its `ExtractionReport`, plus
per-file quality signals measured on the normalized output:

```python
from docpluck import extract_to_dir

report = extract_to_dir(pdf_paths, out_dir="normalized_text")
report.write_receipt("normalized_text/_docpluck_receipt.json")

r = report.results[0]
r.n_replacement_chars   # U+FFFD count — a glyph was lost before docpluck saw it
r.n_greek_chars         # Greek letters; pair with n_chars_normalized for density
```

### From a URL

```python
import httpx
from docpluck import extract_pdf, normalize_text, NormalizationLevel

def extract_from_url(url: str) -> str:
    response = httpx.get(url, follow_redirects=True, timeout=30)
    response.raise_for_status()

    text, method = extract_pdf(response.content)
    normalized, _ = normalize_text(text, NormalizationLevel.academic)
    return normalized
```

---

## What Gets Fixed

### Standard normalization (`NormalizationLevel.standard`)

| Artifact | Example (before → after) |
|----------|--------------------------|
| Null bytes | `"Study\x00 results"` → `"Study results"` |
| Ligatures | `"signiﬁcant"` → `"significant"` |
| Unicode minus | `"r = −0.73"` → `"r = -0.73"` |
| Soft hyphen (invisible) | `"signifi\u00ADcant"` → `"significant"` |
| Non-breaking spaces | `"p\u00A0<\u00A0.001"` → `"p < .001"` |
| Full-width digits | `"ｐ ＝ ０.００１"` → `"p = 0.001"` |
| Curly quotes | `"the "effect""` → `"the "effect""` |
| Hyphenation | `"signi-\nficant"` → `"significant"` |
| Repeated headers | Journal name repeated on every page → stripped |
| Page numbers | Standalone `12` in a page **margin** → stripped |

> A bare integer in the **body** of a page is left alone. pdftotext emits a narrow
> numeric table column as one cell per line, so a printed coefficient of `0` has
> exactly the shape of a page number; only position on the page tells them apart.

### Academic normalization adds (`NormalizationLevel.academic`)

| Artifact | Example (before → after) |
|----------|--------------------------|
| Stat line breaks | `"p =\n.001"` → `"p = .001"` |
| CI delimiters | `"[0.81; 1.92]"` → `"[0.81, 1.92]"` |
| Greek letters | `"η² = 0.12"` → `"eta2 = 0.12"` |
| Superscripts | `"r² = 0.54"` → `"r2 = 0.54"` |
| Footnote markers | `"p < .001¹"` → `"p < .001"` |

### What normalization deliberately does NOT do

docpluck **extracts and canonicalises notation. It does not repair the paper.**
Scope is **English-language articles written in US numeric convention** (`.` decimal,
`,` thousands) — see [`SCOPE.md`](SCOPE.md) for the full consumer contract.

| Input | Output | Why |
|-------|--------|-----|
| `"p = 0,05"` | `"p = 0,05"` | European decimals **pass through as printed**. Every EU→US conversion rule was deleted in v2.4.129/130: over 297 English papers they fired 10 times and *not once correctly*. The source token stays intact so a consumer can still decide; once converted it could not. |
| `"N = 1,182"` | `"N = 1,182"` | The thousands separator is **preserved**. Stripping it turned a printed Satterthwaite df of `185,178` into `185178`, a 1000× error. |
| `"p = 484"` | `"p = 484"` | An author's dropped decimal is **the author's**. Both firing sites across 297 papers were the paper's own error, confirmed by rasterizing the page. |
| `"p < 05"` | `"p < 05"` | The same shape has opposite owners in two real papers; under irreducible ambiguity the default is pass-through, because pass-through is reversible for the consumer and a repair is not. |
| `"[5.37, 4.66]"` | `"[5.37, 4.66]"` | A reversed interval is passed through verbatim. Flagging it belongs to a tool that holds the parsed statistic and has a UI to report it; docpluck holds text and has no channel to announce a guess. |

---

## System Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | ≥ 3.10 | |
| pdfplumber | ≥ 0.11.0 | Core pip dependency — installed automatically |
| camelot-py[cv] | ≥ 0.11, < 3 | Core pip dependency — table detection; rasterizes through pypdfium2, so no Ghostscript needed |
| poppler-utils | any recent | System package — for `extract_pdf()` only |
| mammoth | ≥ 1.8.0 | Optional (`[docx]`) — pure Python, no system deps |
| beautifulsoup4 | ≥ 4.12.0 | Optional (`[html]`) — pure Python |
| lxml | ≥ 5.0.0 | Optional (`[html]`) — has prebuilt wheels |

The normalization and quality functions (`normalize_text`, `compute_quality_score`) have **no system requirements** — pure Python, no external binaries. DOCX and HTML extraction are pure Python too; only PDF needs a system binary.

---

## License

MIT. See [LICENSE](../LICENSE).

## Citation

See the [project README](../README.md#citing-docpluck) and [CITATION.cff](../CITATION.cff).
