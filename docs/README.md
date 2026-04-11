# docpluck

**PDF, DOCX, and HTML text extraction and normalization for academic papers.**

Built from cross-project experience across 8,000+ PDFs spanning psychology, medicine, economics, physics, and biology. Achieves 100% accuracy on 29 manually verified ground-truth passages (see [BENCHMARKS.md](BENCHMARKS.md)).

Supports three input formats:
- **PDF** via `pdftotext` default mode (with `pdfplumber` SMP recovery)
- **DOCX** via `mammoth` (DOCX → HTML → text, preserving Shift+Enter soft breaks)
- **HTML** via `beautifulsoup4` + `lxml` (block/inline-aware tree-walk)

All three formats feed into the same 15-step normalization pipeline and quality scoring.

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
| `standard` | S0-S9 | General text processing (NLP, search indexing) |
| `academic` | S0-S9 + A1-A6 | Statistical pattern matching, meta-analysis |

```python
from docpluck import normalize_text, NormalizationLevel

# Raw text
text, _ = normalize_text(raw, NormalizationLevel.none)

# General cleanup
text, report = normalize_text(raw, NormalizationLevel.standard)

# Full statistical repair (recommended for academic PDFs)
text, report = normalize_text(raw, NormalizationLevel.academic)

print(report.version)          # "1.1.0"
print(report.steps_applied)    # ["S0_smp_to_ascii", "S1_encoding_validation", ...]
print(report.changes_made)     # {"ligatures_expanded": 27, "dashes_normalized": 3, ...}
```

**`NormalizationReport` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `level` | `str` | Level used: `"none"`, `"standard"`, or `"academic"` |
| `version` | `str` | Pipeline version (e.g. `"1.1.0"`) |
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
