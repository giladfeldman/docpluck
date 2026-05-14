# Normalization Pipeline Reference

The normalization pipeline transforms raw PDF-extracted text into clean text suitable for academic statistical pattern matching. It is applied after extraction via `normalize_text(text, level)`.

**Version:** 1.1.0  
**Three levels:** `none` | `standard` (F0 + H0 + T0 + P0 + P1 + W0 + S0-S9) | `academic` (everything in `standard` + A1-A6)

---

## Standard Steps (S0-S9)

Safe for any text processing task. Applied in both `standard` and `academic` modes.

---

### S0 — SMP Mathematical Italic → ASCII

**What:** Maps Unicode Supplementary Multilingual Plane (SMP) Mathematical Italic characters to their ASCII equivalents.

**Artifacts fixed:**
- Math italic capitals A-Z (U+1D434–U+1D44D)
- Math italic small a-z (U+1D44E–U+1D467)
- Math italic Greek (η, π, σ, etc.)

**Why:** Some PDFs (especially from physics and biology journals) embed math using SMP italic fonts. After pdfplumber recovery (see SMP recovery in `extract_pdf()`), these characters need mapping to ASCII so downstream regexes work.

**Example:**
```
Before: "𝑝 < 𝛼"
After:  "p < a"
```

**Source:** Nature/Cell papers with Mathematical Italic fonts.

---

### S1 — Encoding validation

**What:** Removes null bytes (`\x00`), normalizes line endings (`\r\n` → `\n`, `\r` → `\n`).

**Why:** PDF extraction occasionally produces null bytes that corrupt string operations. Mixed line endings from Windows-format PDFs cause inconsistent pattern matching.

**Example:**
```
Before: "Study\x00 results showed\r\neffects"
After:  "Study results showed\neffects"
```

**Source:** ESCIcheck Lesson 1 — null bytes in PDF text streams.

---

### S2 — Accent recombination

**What:** Combines decomposed accent characters with their base vowels into precomposed forms.

**Artifacts fixed:**
- `e + ´` → `é` (acute accent)
- `a + ˆ` → `â` (circumflex)
- `u + ¨` → `ü` (diaeresis)
- `o + \`` → `ò` (grave accent)

**Why:** Some PDF renderers extract diacritics as separate characters instead of precomposed Unicode. This breaks word matching for non-English text.

**Example:**
```
Before: "Me ́diane"  (separate accent)
After:  "Médiane"   (precomposed)
```

---

### S3 — Ligature expansion

**What:** Expands typographic ligatures to their constituent letters.

**Ligatures handled:**
- `ﬀ` (U+FB00) → `ff`
- `ﬁ` (U+FB01) → `fi`
- `ﬂ` (U+FB02) → `fl`
- `ﬃ` (U+FB03) → `ffi`
- `ﬄ` (U+FB04) → `ffl`

**Why:** Academic PDFs frequently use typographic ligatures. "signiﬁcant" does not match "significant". Average of 27.6 ligature characters per PDF found in our 50-PDF corpus.

**Example:**
```
Before: "The eﬀect was signiﬁcant (p < .001)"
After:  "The effect was significant (p < .001)"
```

**Source:** PDFextractor Lesson 3 — ligatures in psychological literature.

---

### S4 — Quote normalization

**What:** Converts typographic (curly) quotes to straight ASCII quotes.

**Characters handled:**
- `"` `"` `„` `‟` `″` `‶` → `"`
- `'` `'` `‚` `‛` `′` `‵` → `'`

**Why:** Curly quotes break exact-string matching and JSON parsing. Consistent straight quotes are expected by all downstream tools.

**Example:**
```
Before: "the "effect size" was d = 0.44"
After:  "the "effect size" was d = 0.44"
```

---

### S5 — Dash and minus normalization

**What:** Normalizes all Unicode dash variants to ASCII hyphen-minus (`-`).

**Characters handled:**
- `−` (U+2212 MINUS SIGN) → `-`
- `–` (U+2013 EN DASH) → `-`
- `—` (U+2014 EM DASH) → `--`
- `‐` (U+2010 HYPHEN) → `-`
- `‑` (U+2011 NON-BREAKING HYPHEN) → `-`

**Why:** U+2212 (MINUS SIGN) looks identical to a hyphen but is a different character. Any regex using `-` to match negative values (`r = -0.73`) will fail to match `r = −0.73`. This is one of the most impactful normalizations for statistical pattern matching.

**Example:**
```
Before: "r(261) = −0.73, 95% CI [−0.78, −0.67]"
After:  "r(261) = -0.73, 95% CI [-0.78, -0.67]"
```

**Source:** ESCIcheck Lesson 5 — Unicode minus in correlation coefficients.

---

### S6 — Whitespace and invisible character normalization

**What:** Normalizes all Unicode whitespace variants to regular space or removes invisible characters.

**Removed (invisible):**
- `\u00AD` (soft hyphen) → `""` — **critical**: invisible but breaks text search; found in 14/50 test PDFs
- `\u200B` (zero-width space) → `""`
- `\u200C` (zero-width non-joiner) → `""`
- `\u200D` (zero-width joiner) → `""`
- `\uFEFF` (BOM / zero-width no-break space) → `""`

**Converted to regular space:**
- `\u00A0` (non-breaking space)
- `\u2002`–`\u200A` (en space, em space, thin space, hair space, etc.)
- `\u202F` (narrow no-break space)
- `\u205F` (medium mathematical space)
- `\u3000` (ideographic space)

**Full-width ASCII → ASCII (U+FF01–U+FF5E):**
- `ｐ` → `p`, `＝` → `=`, `０` → `0`, etc.

**Why soft hyphen matters:** U+00AD is completely invisible in almost every text renderer. `"signifi\u00ADcant"` looks identical to `"significant"` but does not match it. Found in 14/50 test PDFs, up to 151 instances in a single paper.

**Example:**
```
Before: "p\u00A0<\u00A0.001 (N\u2009=\u200B1\u200924)"
After:  "p < .001 (N = 1 24)"   → then trailing spaces collapsed
```

**Source:** PDFextractor Lesson 6 (soft hyphen), ESCIcheck Lesson 9 (Unicode spaces).

---

### S7 — Hyphenation repair

**What:** Joins words split across lines by hyphens (end-of-line hyphenation).

**Pattern:** `([a-z])-\n([a-z])` → `\1\2`

**Why:** PDF renderers often preserve end-of-line hyphens that were only there for layout. "ob-\nserved" should be "observed".

**Example:**
```
Before: "The ef-\nfect was signi-\nficant"
After:  "The effect was significant"
```

**Note:** Only joins lowercase-to-lowercase to avoid merging hyphenated proper nouns or compound words at sentence boundaries.

---

### S8 — Mid-sentence line break joining

**What:** Joins lines that appear to be mid-sentence (lowercase letter or comma/semicolon followed by newline then lowercase letter).

**Pattern:** `([a-z,;])\n([a-z])` → `\1 \2`

**Why:** PDF extraction frequently breaks text at column widths, producing line breaks in the middle of sentences. These interfere with pattern matching across natural sentence spans.

**Example:**
```
Before: "The results showed\nthat participants in the treatment\ncondition performed better"
After:  "The results showed that participants in the treatment condition performed better"
```

---

### S9 — Header/footer removal

**What:** Removes repeated headers/footers and standalone page numbers.

**Two mechanisms:**
1. **Repeated lines:** Lines of 15-120 characters that appear ≥5 times across the document are stripped (journal name, running title, institution name).
2. **Standalone page numbers:** Lines matching `^\s*\d{1,3}\s*$` (1-3 digits alone on a line) are stripped.

**Why:** Academic journals print the journal name, volume, and page numbers on every page. These become noise in extracted text and produce false pattern matches.

**Ordering note:** In `academic` mode, A1 (statistical line break repair) runs **before** S9. This prevents `p =\n484` from having `484` stripped as a page number before A1 can join it.

**Example:**
```
Before (page 4 of journal article):
  "Journal of Experimental Psychology"  ← header on every page
  "..."
  "4"  ← page number
  "..."
After:  (headers and page numbers removed)
```

---

## Pre-S0 Document-shape Strips (v1.8.x)

Document-shape passes that run **before** the unicode/whitespace S0–S9
steps. They strip page-level junk that pdftotext serializes into the body
text stream (banners, dot-leader TOCs, page-footer lines, watermarks,
front-matter metadata leaks).

Implemented in `docpluck/normalize.py` (see code for full pattern lists);
documented here at summary level only.

| Step | Purpose | Notes |
|------|---------|-------|
| F0 | Layout-aware running-header / footer / footnote strip | Requires `LayoutDoc` from `extract_pdf_layout`; populates `report.footnote_spans`. Optional. |
| H0 | Document-header banner-line strip | Runs only in the first 30 lines; curated `_HEADER_BANNER_PATTERNS`. v1.8.0. |
| T0 | TOC dot-leader paragraph strip | Drops paragraphs containing `_{3,}` runs in the head zone (first ~100 lines). v1.8.0. |
| P0 | Page-footer / running-header LINE strip | Curated `_PAGE_FOOTER_LINE_PATTERNS` matching single complete lines. Includes `^Q. XIAO ET AL.$`, `^RECKELL et al.$`, `^CONTACT …$`, `^Department of …, University of <Place>, <Region>$`, `^Supplemental data for this article …$`, truncated `^Department of …, University of$`, JAMA/AOM/PMC footers, etc. v1.8.0 + v2.4.6 + v2.4.8 + v2.4.16. |
| P1 | Front-matter metadata-leak PARAGRAPH strip | **v2.4.16.** Drops orphan acknowledgments / license blocks / "previous version" notes / correspondence blocks that pdftotext inlines as standalone single-line paragraphs mid-Introduction. Position-gated to the first `max(8000, len(text)//6)` chars so the legitimate `## Acknowledgments` section at the end is preserved. |
| W0 | Publisher-overlay watermark strip | "Downloaded from …", "Provided by …", "This article is protected by copyright", Royal Society OA footer, Elsevier copyright stamp, two-column running-header, equal-contribution footnote. v1.7.0–v2.3.1. |

**Ordering:** F0 → H0 → T0 → P0 → P1 → W0 → S0 (unicode) → S1 …

P1 runs AFTER P0 because P0 already handles single-line variants of the
patterns P1 catches at paragraph level. The two are complementary:
P0 is globally safe (no position gate, matches full lines); P1 is
position-gated and matches paragraph openings to catch multi-sentence
acknowledgments / license blobs that pdftotext serialized on a single
long physical line.

---

## Academic Steps (A1-A6)

Statistics-aware repairs. Applied only in `academic` mode. **A1 runs before S9; A2-A6 run after S9.**

---

### A1 — Statistical line break repair

**What:** Joins statistical expressions split across line breaks.

**Patterns repaired:**
- `p\n<` → `p <`
- `p <\n.001` → `p < .001`
- `OR\n1.39` → `OR 1.39`
- `95%\nCI` → `95% CI`
- `F(1, 30) =\n4.425` → `F(1, 30) = 4.425`
- `=\n-0.73` → `= -0.73`

**Why:** PDF column layouts frequently break statistical expressions across lines. The value `0.001` appearing on its own line looks like a page number to S9. A1 must run before S9 to prevent this stripping.

**Regex safety:** All patterns use possessive quantifiers (`[ \t]*+`) to prevent catastrophic backtracking. See [DESIGN.md](DESIGN.md#6-possessive-quantifiers-prevent-regex-catastrophe).

**Rate:** ~0.77% of values in MetaESCI corpus were split across line breaks.

**Example:**
```
Before: "t(28.7) = 2.43, p\n= .021"
After:  "t(28.7) = 2.43, p = .021"
```

**Source:** MetaESCI extraction report, ESCIcheck Phase 2B.

---

### A2 — Dropped decimal repair

**What:** Restores the dropped leading `0.` from p-values and effect sizes.

**Detection:** A 2-3 digit integer value in a p-value context where the value > 1.0 and < 1000 (p-values must be 0–1, so any integer > 1 is a dropped decimal).

**Pattern:** `p = 484` → `p = .484`

**Also handles:**
- `d = 484` → `d = .484`
- `g = 37` → `g = .37`

**Why:** 4.88% rate in MetaESCI 121,000 results. Caused by PDF column layout splitting the decimal point from the digits (`.` on left column end, digits on right column).

**Limitations:**
- Does not fix single-digit values (`p = 5`) — ambiguous, could be valid
- Does not fix `N = 484` (not a p-value/effect size context)

**Example:**
```
Before: "F(2, 430) = 12.38, p = 484, eta2 = 54"
After:  "F(2, 430) = 12.38, p = .484, eta2 = .54"
```

**Source:** MetaESCI extraction report, ESCIcheck Lesson 14.

---

### A3 — Decimal comma normalization

**What:** Converts European-locale decimal commas to decimal points.

**Pattern:** `0,05` → `0.05`

**Detection:** Digit, comma, 1-3 digits, followed by whitespace or end of statistical expression (not followed by more digits, which would indicate a thousands separator like `1,234`).

**Why:** European journals (German, French, Dutch, Scandinavian) often use comma as decimal separator. `p = 0,05` is the same as `p = 0.05`.

**Limitation:** Cannot perfectly distinguish `d = 1,234` (European decimal: d = 1.234) from `N = 1,234` (thousands separator: N = 1234). Currently converts both. The ambiguity is rare in practice since very few effect sizes have 3 post-decimal digits.

**Example:**
```
Before: "p = 0,001, d = 0,44"
After:  "p = 0.001, d = 0.44"
```

**Source:** MetaESCI extraction report — European journal corpus.

---

### A4 — CI delimiter harmonization

**What:** Converts semicolon-delimited confidence intervals to comma-delimited.

**Pattern:** `[0.81; 1.92]` → `[0.81, 1.92]`

**Why:** Some journals/software output `[lower; upper]` with semicolon. APA 7th edition and most downstream tools expect `[lower, upper]` with comma. Harmonizing prevents duplicate patterns.

**Example:**
```
Before: "95% CI [-0.78; -0.67]"
After:  "95% CI [-0.78, -0.67]"
```

---

### A5 — Math symbol and Greek letter normalization

**What:** Converts Greek statistical letters and math symbols to ASCII equivalents.

**Greek letters (for downstream regex matching):**
- `η` → `eta`, `η²` → `eta2`, `ηG²` / `η²G` → `etaG2` (generalized)
- `χ` → `chi`, `χ²` → `chi2`
- `ω` → `omega`, `ω²` → `omega2`
- `α` → `alpha`
- `β` → `beta`
- `δ` → `delta`
- `σ` → `sigma`
- `φ` → `phi`
- `μ` → `mu`

**Math symbols:**
- `×` → `x`
- `≤` → `<=`
- `≥` → `>=`
- `≠` → `!=`

**Superscript digits (all):**
- `²³¹⁰⁴⁵⁶⁷⁸⁹` → `2 3 1 0 4 5 6 7 8 9`

**Subscript digits (all):**
- `₀₁₂₃₄₅₆₇₈₉` → `0 1 2 3 4 5 6 7 8 9`

**Why:** Greek letters and superscripts are common in effect size notation (`η²`, `ω²`, `χ²`) and cannot be matched by simple ASCII regex. Mapping to ASCII allows unified pattern matching.

**Example:**
```
Before: "η² = .054, χ²(2) = 8.36, ω² = .032"
After:  "eta2 = .054, chi2(2) = 8.36, omega2 = .032"
```

**Source:** ESCIcheck Lessons 12-13, MetaESCI Greek letter corpus.

**Note on Greek preservation (MetaESCI request D5).** A5 runs only at
`NormalizationLevel.academic`. The transliteration is intentional: downstream
effect-size parsers (`effectcheck`, ESCImate, MetaESCI) rely on ASCII
`eta2` / `chi2` / `omega2` tokens for their regex rulebook, so preserving the
original Greek characters would break the match rate that academic-level is
optimized for. If a consumer needs Greek preserved (publication-quality
rendering, Greek-language documents, non-effect-size downstream work), pass
`NormalizationLevel.standard` — the `standard` level skips A1–A6 entirely and
leaves every Greek glyph untouched. The extraction-time Greek count reported
by `extract_pdf` is independent of normalization level, so "how much Greek was
in the raw text" and "how the academic pipeline treated it" can be measured
separately.

---

### A6 — Footnote marker removal

**What:** Removes isolated superscript/subscript digit footnote markers that appear after statistical values.

**Pattern:** Digit/`]`/`)` followed by a Unicode superscript/subscript digit, followed by whitespace or end of expression.

**Example:**
```
Before: "p < .001¹, 95% CI [0.1, 0.5]²"
After:  "p < .001, 95% CI [0.1, 0.5]"
```

**Why:** Academic papers add footnote markers (¹²³) immediately after values to reference footnotes. These superscripts interfere with value extraction and should be stripped after statistical expressions.

**Note:** A5 converts most superscript digits to regular digits first. A6 catches any remaining Unicode superscripts that follow stat-adjacent characters.

**Source:** ESCIcheck Lesson 14 — footnote superscripts adjacent to p-values.

---

## Ordering Summary

```
extract_pdf()
    ↓
normalize_text(text, NormalizationLevel.academic)
    ↓
S0  SMP Mathematical Italic → ASCII
S1  Encoding validation
S2  Accent recombination
S3  Ligature expansion
S4  Quote normalization
S5  Dash and minus normalization
S6  Whitespace and invisible character normalization
S7  Hyphenation repair
S8  Mid-sentence line break joining
A1  Statistical line break repair  ← before S9 (prevents page number stripping)
S9  Header/footer removal
    (limit consecutive newlines to 2)
A2  Dropped decimal repair
A3  Decimal comma normalization
A4  CI delimiter harmonization
A5  Math symbol and Greek letter normalization
A6  Footnote marker removal
    ↓
    normalized text + NormalizationReport
```

**Critical ordering constraint:** A1 must run before S9. If S9 runs first, standalone digits like `484` (from `p =\n484`) are stripped as page numbers before A1 can rejoin them.
