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
