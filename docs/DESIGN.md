# Design Decisions

This document explains the implementation choices behind docpluck — why things are the way they are. Each decision is backed by empirical testing on real academic PDFs.

---

## 1. Why pdftotext, not pymupdf / pymupdf4llm

We evaluated three extraction engines on 50 PDFs across 8 citation styles (APA, AMA/JAMA, Vancouver/BMC, Nature, IEEE, Harvard, Chicago, AOM):

| Engine | Speed | Column handling | False positives | License |
|--------|-------|-----------------|-----------------|---------|
| **pdftotext** | **0.4s** | Good | Low | MIT/GPL |
| pymupdf_raw | 0.9s | Poor | Low | AGPL v3 |
| pymupdf4llm | 9.4s | Best | **High** | **AGPL v3** |

### Why not pymupdf4llm

Despite best column handling, pymupdf4llm was rejected for two hard reasons:

**1. AGPL v3 license.** AGPL requires any software that *uses* an AGPL library to also be open-sourced under AGPL. This is incompatible with providing docpluck as a service (Docpluck App) or embedding it in commercial research software. No amount of quality improvement justifies an incompatible license.

**2. Markdown artifacts break downstream regex.** pymupdf4llm outputs Markdown, not plain text. This introduces two failure modes:
  - Bold markers wrap statistics: `**p** < .001` — regex patterns for `p < .001` fail
  - HTML `<` in statistics: `p < .001` gets rendered as an HTML tag start, eating 40,000+ characters of content

**3. False positives from figure axis labels.** In IEEE and figure-heavy papers, pymupdf4llm extracted `r>1` and `r>2` from figure axis labels as `<br>` HTML tags, reporting 168 "statistics" of which 167 were false positives.

### Why not pymupdf (raw)

PyMuPDF raw has better column handling than pdftotext but:
- Still AGPL v3 license
- Does not substantially outperform pdftotext on statistics extraction accuracy
- No benefit that justifies the license cost

### pdftotext final verdict

100% accuracy on 29 manually verified ground-truth passages. Fast (0.4s typical). MIT-compatible. The clear choice.

---

## 2. Why pdftotext default mode — NO `-layout` flag

This is the single most important implementation decision.

The `-layout` flag in pdftotext "preserves" physical column layout. In practice, for two-column academic papers, this means:

**With `-layout`:** Left column and right column are interleaved character by character on the same lines. A sentence split across two columns becomes jumbled.

**Default mode (no flag):** pdftotext reconstructs reading order, treating the document as flowing text. Columns are joined correctly.

**Empirical result:** On chan_feldman_2025_cogemo.pdf (APA 2-column psychology paper, page 12 with 8 correlation tests):

| Engine | p-values found | 95% CIs found | Total | Notes |
|--------|:--------------:|:-------------:|:-----:|-------|
| pdftotext `-layout` | 6/8 | 8/8 | 14 | Missed 2 p-values (column interleaving) |
| pdftotext default | 8/8 | 8/8 | 16 | **Perfect** |

The `-layout` flag is strictly worse for statistical pattern extraction. It is **never** used in docpluck.

---

## 3. Why pdfplumber for SMP recovery

Some journals (Nature, Cell, Physical Review) embed mathematics using SMP (Supplementary Multilingual Plane) Unicode fonts — specifically Mathematical Italic (U+1D434–U+1D467). Xpdf (which pdftotext uses internally) cannot decode characters above U+FFFF and replaces them with U+FFFD (replacement character `?`).

**Detection:** After pdftotext extraction, count `U+FFFD` characters. If any are present, trigger recovery.

**Recovery:** pdfplumber uses pdfminer under the hood, which correctly handles SMP Unicode. We extract with pdfplumber and then map the recovered SMP characters to ASCII equivalents (e.g. `𝑝` → `p`, `𝜂` → `eta`).

**Cost:** ~9s vs ~0.4s for normal extraction. Triggered automatically only when needed.

**Alternative considered:** Use pdfplumber always. Rejected because it's 23× slower and pdftotext produces better reading order for most PDFs.

---

## 4. Why normalization is in Python, not TypeScript

The Docpluck App frontend (Next.js/TypeScript) calls the Python extraction service via HTTP. We deliberately kept all normalization logic in Python for these reasons:

1. **Single source of truth.** Other Python projects (ESCIcheck, Scimeto, MetaESCI) can import `docpluck` directly without reimplementing normalization.

2. **Test coverage.** 151 Python tests cover every edge case. A TypeScript reimplementation would need its own test suite and would inevitably diverge.

3. **Service returns normalized text.** Downstream consumers receive already-normalized text — they don't need to know anything about the pipeline.

---

## 5. Why A1 runs before S9 (ordering matters)

S9 (header/footer removal) strips standalone numbers that appear alone on a line — these are typically page numbers. But A1 (statistical line break repair) joins patterns like:

```
p =
484
```
→ `p = .484`

If S9 runs first, it strips `484` as a page number before A1 can recognize it as a p-value split across a line break. In academic mode, A1 must run before S9.

This is why the pipeline order in `normalize.py` is:
```
S0-S8 → [A1 in academic mode] → S9 → [A2-A6 in academic mode]
```

---

## 6. Possessive quantifiers prevent regex catastrophe

Early versions of the normalization pipeline used `\s*` before lookaheads in line-break joining patterns. This caused catastrophic backtracking and text destruction.

**The bug:** Pattern `(p\s*[<=>]\s*)(?![.0]?\d)` intended to fix `p =\n0.001`. But when the lookahead failed:
1. `\s*` could backtrack past spaces
2. The engine consumed valid content while searching for a match
3. Input `p < 0.001, f = 0.16, 95% CI [0.10, 0.20]` became `p <95% CI [0.10, 0.20]` — the p-value, effect size, and separators were eaten

**The fix:** Use possessive quantifiers `[ \t]*+` (no backtracking) instead of `\s*`:
- `[ \t]*+` matches horizontal whitespace only, with no backtracking
- `\s` was wrong anyway — it matches `\n`, consuming newlines needed by the pattern
- Lookahead `(?!\d|[.]\d)` correctly catches all number formats: `0.001`, `.001`, `0.05`, `100`

**Rule:** Never use `\s*` before a lookahead in normalization regexes.

---

## 7. Unicode MINUS SIGN (U+2212) is not a hyphen

ASCII hyphen-minus `U+002D` and Unicode minus sign `U+2212` look identical but are different characters. Academic papers (especially from journal typesetting systems) frequently use the Unicode minus for negative values:

- `r = −0.73` uses `−` (U+2212)
- Pattern `r = -0.73` uses `-` (U+002D)

Any regex matching negative numbers with `-` will miss the Unicode version. S5 normalizes all Unicode minus, en-dash, em-dash, and hyphen variants to ASCII hyphen-minus before any pattern matching.

---

## 8. Soft hyphen (U+00AD) is invisible and dangerous

U+00AD (soft hyphen) is a formatting hint that tells renderers where a word *can* be broken if it doesn't fit on a line. It is invisible in most text displays. But it breaks string search:

- `"significant"` ≠ `"signifi\u00ADcant"` even though they look identical

Found in **14 out of 50 test PDFs**, with up to 151 instances in a single paper (chan_feldman_2025_cogemo.pdf). S6 strips them unconditionally.

---

## 9. Dropped decimal repair (A2) — 4.88% artifact rate

MetaESCI analysis of 121,000 results found that 4.88% of p-values had dropped leading decimal points:

- `p = 484` (should be `p = .484`)
- `p = 37` (should be `p = .37`)
- `p = 999` (should be `p = .999`)

This happens when PDF column layout splits the decimal point onto a different line or column than the digits.

**Detection heuristic:** A p-value > 1.0 and < 1000 with exactly 2-3 digits is almost certainly a dropped decimal. Insert a `.` before the digits.

**Limitation:** Cannot distinguish `p = 5` (too small to be a valid 2-digit dropped decimal) from a genuine value. Currently only repairs 2-3 digit values.

---

## 10. No AGPL dependencies — ever

pymupdf (PyMuPDF), pymupdf4llm, and PyMuPDF-story are all AGPL v3. Any code that imports them must also be AGPL v3 or obtain a commercial license.

docpluck's MIT license is incompatible with AGPL v3. No AGPL dependency will ever be added to docpluck. This is a hard constraint, not a preference.

All current and planned dependencies are MIT or BSD-compatible:

| Dep | License | Purpose |
|-----|---------|---------|
| pdfplumber | MIT | PDF SMP Unicode recovery |
| mammoth | BSD-2 | DOCX → HTML conversion |
| beautifulsoup4 | MIT | HTML parsing |
| lxml | BSD-3 | HTML parser backend |

---

## 11. Why mammoth for DOCX — not python-docx, docx2txt, or pandoc

Added in v1.3.0 when DOCX support was ported from Scimeto.

### Why mammoth.convert_to_html, not extract_raw_text

Mammoth provides two extraction modes:

- **`extract_raw_text()`**: Returns plain text with paragraph separation as `\n\n`, but **loses intra-paragraph line breaks** (Shift+Enter soft breaks become nothing).
- **`convert_to_html()`**: Returns structured HTML that preserves soft breaks as `<br>` tags, headings as `<h1>`–`<h6>`, and paragraph structure.

Academic documents use soft breaks in addresses, equations, poetry, and tables. Losing them breaks regex patterns that depend on line boundaries. We use `convert_to_html()` and then run the same `html_to_text()` tree-walk used for native HTML input — a single code path for both formats.

### Why not python-docx

`python-docx` is designed for document *creation* and *editing*, not extraction. It only exposes paragraph-level access, requires manual iteration for anything structural, and has no built-in handling for footnotes, soft breaks, or tracked changes. It's the wrong tool.

### Why not docx2txt

`docx2txt` is effectively unmaintained (last meaningful release 2019). It returns one big string with no structure preservation. Inferior to mammoth in every measurable way.

### Why not pypandoc

Pandoc produces excellent output — arguably the best DOCX fidelity of any tool — but it requires the `pandoc` binary installed on the host, adding a ~100MB system dependency that's painful to deploy. Mammoth is 100% pure Python.

### Why not docx2python

docx2python is a strong alternative with better footnote and header/footer support. We chose mammoth because it is already battle-tested in Scimeto production (since Dec 2025) with the exact block/inline-aware pipeline we're porting. If docx2python ever becomes necessary (e.g., for OMML equation support), we can swap it in — the `extract_docx()` function contract is minimal.

### OMML equation limitation

Mammoth silently drops Office Math (OMML) equation objects. This is a real limitation for STEM papers that embed statistical formulas as math objects. In practice:

- Social science papers (our primary use case) write inline stats as plain text — unaffected.
- STEM papers with equation-embedded results will lose those values.

Documented in README and BENCHMARKS. No workaround in v1.3.0.

---

## 12. Why BeautifulSoup + lxml with a custom tree-walk — not `get_text()`

Added in v1.3.0 when HTML support was ported from Scimeto.

### Why not BeautifulSoup.get_text(separator=...)

This seems like the obvious choice, but it does not work. `get_text()` applies a single separator uniformly to all element boundaries — block and inline alike. This means:

- `separator=' '` — `<p>Hello</p><p>World</p>` becomes `"Hello World"` (loses paragraph breaks)
- `separator='\n'` — `<a>Chan</a><a>ORCID</a>` becomes `"Chan\nORCID"` (unwanted line break inside a name)

The BeautifulSoup maintainer [has confirmed](https://bugs.launchpad.net/bugs/1768330) that block vs. inline awareness will not be added to BS4 because it would make BS4 "more like a web browser." The only correct approach is a custom tree-walk that knows about block vs. inline elements.

### The ChanORCID bug

Scimeto ran in production for weeks with a bug where adjacent `<a>` tags produced merged text: `<a>Chan</a><a>ORCID</a>` → `"ChanORCID"`. The fix: **always insert a space before and after every inline element**, not just between them. The docpluck port has a regression test named `test_chan_orcid_regression` specifically guarding this.

### Why lxml parser (not html.parser, not html5lib)

| Parser | Speed (100 iter) | Malformed HTML | Dependencies |
|--------|:----------------:|:--------------:|--------------|
| **lxml** | **7.55s** | Good recovery | C library (libxml2) |
| html.parser | 11.79s | Stricter | Built-in |
| html5lib | 22.35s | Best (full HTML5) | Pure Python |

Academic publisher HTML is machine-generated and well-formed, so html5lib's perfect HTML5 compliance is overkill. lxml is 1.5–3× faster than html.parser with good enough error recovery for the rare malformed case.

### Why not a content extractor (trafilatura, readability, jusText, newspaper4k)

These tools are designed for *news article extraction from web pages* — identifying the "main content" and stripping navigation/boilerplate. They solve a fundamentally different problem and would actively harm docpluck's use case:

- They would strip reference sections (considered "boilerplate")
- They would strip supplementary material links
- They would miss author affiliations and statistics in footers

docpluck receives **already-isolated article content** (not a web page). The correct strategy is "extract everything, let the tree-walk preserve structure." BeautifulSoup has the highest text recall (0.994) in published article-extraction benchmarks — which for our use case is a feature, not a bug.

### Why not inscriptis

inscriptis is the strongest alternative — it's an academic tool (JOSS paper) with built-in block/inline handling. We considered it seriously. We chose BS4 + custom walker because:

1. The Scimeto production walker is only ~60 lines and battle-tested
2. inscriptis focuses on *visual layout fidelity* (table alignment, indentation) that docpluck doesn't need
3. Porting Scimeto exactly gives us behavioral parity across the two codebases

---

## 13. Why a separate `extract_pdf_structured()` function (v2.0)

v2.0 added structured table and figure extraction. We considered three API approaches:

1. **Additive function** — keep `extract_pdf()` as is, add `extract_pdf_structured()` returning a richer dict.
2. **Opt-in flag on `extract_pdf()`** — `extract_pdf(pdf_bytes, structured=True)` returns a dict instead of a tuple.
3. **Breaking change** — `extract_pdf()` always returns a dict in v2.0.

We chose (1). The two-tuple `(text, method)` contract is pinned by the SaaS service via git-pin and consumed by 4+ downstream projects (ESCIcheck, MetaESCI, Scimeto, MetaMisCitations). A breaking change forces a coordinated bump everywhere; an opt-in flag changes the return type based on a parameter (awkward to type and document); an additive function lets new consumers opt in without disturbing old ones.

Internally the two functions share the PDF parse via the v1.6.0 `LayoutDoc` abstraction; structured extraction costs ~3-5× more than text-only because of the geometric clustering pass, not because of duplicated parsing.

Confidence is scored in two stages — `score_table()` returns the raw pre-clamp value (used for the isolation fall-back decision at threshold 0.4); `clamp_confidence()` applies per-rendering floor/ceiling to produce the user-visible `Table.confidence`. The separation matters: the whitespace floor is 0.4, equal to the threshold — clamping inside `score_table()` would silently absorb the fall-back signal.

See `docs/superpowers/specs/2026-05-06-table-extraction-design.md` for full data model and detection algorithm.

---

## Known Limitations

See the Docpluck App [UNADDRESSED_ISSUES.md](https://github.com/giladfeldman/docpluckapp) for the full list. Key ones:

| Issue | Rate | Notes |
|-------|------|-------|
| Column merge garbling | ~0.65% | Quality score detects it, but no repair attempted |
| Page footer contamination | ~0.25% | S9 helps but misses some cases |
| Merged F-statistics | Rare | `F(2,430) = 12.38 0.054` — two numbers space-separated |
| Line numbers adjacent to stats | Rare | `12F(2,430)` — line number prefix not stripped |
| Thousands separator ambiguity | Rare | A3 can't distinguish `N = 1,234` from European decimal |
