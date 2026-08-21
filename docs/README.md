# docpluck

**PDF, DOCX, and HTML text extraction and normalization for academic papers.**

Built from cross-project experience across 8,000+ PDFs spanning psychology, medicine, economics, physics, and biology. Achieves 100% accuracy on 29 manually verified ground-truth passages (see [BENCHMARKS.md](BENCHMARKS.md)).

Supports three input formats:
- **PDF** via `pdftotext` default mode (with `pdfplumber` SMP recovery)
- **DOCX** via `mammoth` (DOCX → HTML → text, preserving Shift+Enter soft breaks)
- **HTML** via `beautifulsoup4` + `lxml` (block/inline-aware tree-walk)

All three formats feed into the same normalization pipeline and quality scoring.

---

## Scope — read this before you build on the output

> **docpluck extracts and normalizes ENGLISH-language science articles written in US numeric
> convention (`.` decimal, `,` thousands).**
>
> **It canonicalises NOTATION. It does not fix the paper.**

Two consequences that are deliberate limits, not bugs:

1. **European numbers pass through exactly as printed.** `d = 0,45` stays `d = 0,45`; `N = 1,182`
   keeps its comma. We do not convert them, because the source token is the only evidence you have
   of what the paper meant — once converted, that evidence is gone. `.replace(",", "")` is one line
   on your side and irreversible on ours.
2. **The paper's own errors reach you untouched.** `p = 38.`, `p < 05` and `p = 001` are what those
   pages actually print (each verified by rasterizing the page). Silently repairing them would
   launder a real defect into your analysis: you would validate a number the paper never printed,
   and the author would never learn. Detecting and flagging them is yours — you hold the parsed
   statistic and its context.

**What we DO fix is damage our own pipeline caused** — a glyph the text layer lost, a fused
exponent, a sign-flipped interval, a `<` extracted as `b`. That is the whole distinction: *did we
break this, or did the paper?*

Full statement, including the known limits: **[SCOPE.md](SCOPE.md)**.

---

## Install

```bash
# PDF only (pdfplumber)
pip install docpluck

# + DOCX support (adds mammoth)
pip install docpluck[docx]

# + HTML support (adds beautifulsoup4 + lxml)
pip install docpluck[html]

# Everything
pip install docpluck[all]
```

**System requirement for `extract_pdf()`:** [poppler-utils](https://poppler.freedesktop.org/) (provides the `pdftotext` binary). DOCX and HTML are pure Python — no system dependencies.

```bash
# Linux / WSL
apt-get install poppler-utils

# macOS
brew install poppler

# Windows
# Download from https://github.com/oschwartz10612/poppler-windows/releases
# Add bin/ to PATH
```

**Install from GitHub** (like R's `remotes::install_github()`):

```bash
pip install git+https://github.com/giladfeldman/docpluck.git

# Pinned version
pip install "docpluck>=1.3.0"
```

---

## Quick Start

```python
from docpluck import (
    extract_pdf, extract_docx, extract_html,
    normalize_text, NormalizationLevel, compute_quality_score,
)

# 1. Extract text from any supported format
with open("paper.pdf", "rb") as f:
    text, method = extract_pdf(f.read())

# Or from DOCX:
# with open("paper.docx", "rb") as f:
#     text, method = extract_docx(f.read())

# Or from HTML:
# with open("paper.html", "rb") as f:
#     text, method = extract_html(f.read())

print(f"Extracted {len(text):,} chars via {method}")

# 2. Normalize for statistical pattern matching
normalized, report = normalize_text(text, NormalizationLevel.academic)

print(f"Steps applied: {report.steps_applied}")
print(f"Changes made: {report.changes_made}")

# 3. Check quality
quality = compute_quality_score(normalized)
print(f"Quality: {quality['score']}/100 ({quality['confidence']})")
if quality["garbled"]:
    print("Warning: text may be corrupted (column merge or encoding failure)")
```

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

See `an internal design doc` for the full schema and design rationale.

---

## API Reference

### `extract_pdf(pdf_bytes: bytes) → tuple[str, str]`

Extract text from PDF bytes.

**Parameters:**
- `pdf_bytes` — Raw PDF file content as `bytes`

**Returns:** `(text, method)` tuple where:
- `text` — Extracted plain text. Check `text.startswith("ERROR:")` for failure.
- `method` — Engine used:
  - `"pdftotext_default"` — standard extraction (fast, ~400ms)
  - `"pdftotext_default+pdfplumber_recovery"` — SMP fallback triggered (~9s), used when pdftotext outputs `U+FFFD` replacement characters (common in Nature/Cell papers using Mathematical Italic fonts)

**Requires:** `pdftotext` binary on PATH.

```python
with open("paper.pdf", "rb") as f:
    text, method = extract_pdf(f.read())

if text.startswith("ERROR:"):
    raise RuntimeError(f"Extraction failed: {text}")
```

---

### `extract_docx(docx_bytes: bytes) → tuple[str, str]`

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

### `extract_html(html_bytes: bytes) → tuple[str, str]`

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

Count pages in a PDF using byte pattern matching. No external binary required. **PDF only** — returns `None` is not applicable for DOCX/HTML.

```python
with open("paper.pdf", "rb") as f:
    content = f.read()
    n = count_pages(content)
print(f"{n} pages")
```

---

### `normalize_text(text: str, level: NormalizationLevel) → tuple[str, NormalizationReport]`

Apply the normalization pipeline at the specified level.

**Parameters:**
- `text` — Raw extracted text
- `level` — `NormalizationLevel.none` | `NormalizationLevel.standard` | `NormalizationLevel.academic`

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
| `steps_applied` | `list[str]` | Step codes in order (e.g. `["S1_encoding_validation", "S3_ligature_expansion"]`) |
| `changes_made` | `dict[str, int]` | Character-level change counts per step |

---

### `compute_quality_score(text: str) → dict`

Compute extraction quality metrics.

**Returns:**

```python
{
    "score": 85,                    # 0–100 composite score
    "common_word_ratio": 0.142,     # fraction of first 2000 words that are common English words
    "garbled": False,               # True if common_word_ratio < 0.02 (column merge / encoding failure)
    "confidence": "high",           # "high" (≥80), "medium" (≥50), "low" (<50)
    "details": {
        "ligatures_remaining": 0,   # count of ff/fi/fl ligature chars not yet expanded
        "garbled_chars": 0,         # count of U+FFFD replacement characters
        "non_ascii_ratio": 0.031,   # fraction of non-ASCII characters
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

### `extract_sections(file_bytes, *, source_format=None, ...) → SectionedDocument`

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

Every character of the source belongs to exactly one section — the partition is total, so
nothing is silently dropped. Unrecognised spans carry `SectionLabel.UNKNOWN` rather than
being merged into a neighbour. Pipeline version: `SECTIONING_VERSION`.

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

---

## Integration Examples

### ESCIcheck / effectcheck

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

### Scimeto / MetaESCI (batch processing)

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
# {'version': '2.4.137',            # docpluck itself
#  'git_sha': '…',
#  'normalize_version': '1.9.58',   # in-repo pipeline versions, bumped
#  'sectioning_version': '1.2.5',   #   independently of the package version
#  'table_extraction_version': '2.4.12',
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

### MetaMisCitations (URL-based)

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
| Page numbers | Standalone `12` on its own line → stripped |

### Academic normalization adds (`NormalizationLevel.academic`)

| Artifact | Example (before → after) |
|----------|--------------------------|
| Stat line breaks | `"p =\n.001"` → `"p = .001"` |
| Dropped decimals | `"p = 484"` → `"p = .484"` |
| European decimals | `"p = 0,05"` → `"p = 0.05"` |
| CI delimiters | `"[0.81; 1.92]"` → `"[0.81, 1.92]"` |
| Greek letters | `"η² = 0.12"` → `"eta2 = 0.12"` |
| Superscripts | `"r² = 0.54"` → `"r2 = 0.54"` |
| Footnote markers | `"p < .001¹"` → `"p < .001"` |

---

## System Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | ≥ 3.10 | |
| pdfplumber | ≥ 0.11.0 | Core pip dependency — installed automatically |
| poppler-utils | any recent | System package — for `extract_pdf()` only |
| mammoth | ≥ 1.8.0 | Optional (`[docx]`) — pure Python, no system deps |
| beautifulsoup4 | ≥ 4.12.0 | Optional (`[html]`) — pure Python |
| lxml | ≥ 5.0.0 | Optional (`[html]`) — has prebuilt wheels |

The normalization and quality functions (`normalize_text`, `compute_quality_score`) have **no system requirements** — pure Python, no external binaries. DOCX and HTML extraction are pure Python too; only PDF needs a system binary.

---

## License

MIT. See [LICENSE](../LICENSE).

## Citation

If you use docpluck in research, please cite:

```
Feldman, G. (2026). docpluck: PDF text extraction and normalization for academic papers.
https://github.com/giladfeldman/docpluck
```
