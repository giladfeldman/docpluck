# Normalization Pipeline Reference

The normalization pipeline transforms raw PDF-extracted text into clean text suitable for academic statistical pattern matching. It is applied after extraction via `normalize_text(text, level)`.

**Version:** see `docpluck.normalize.NORMALIZATION_VERSION` (current code is the source of truth).  
**Three levels:** `none` | `standard` (document-shape cleanup + core cleanup + ref/reflow repair) | `academic` (everything in `standard` + statistical repairs).

> This document explains the core step families. The live pipeline has grown beyond the original v1.1 shape (for example `W0*`, `R2`, `R3`, `A7`, and additional recovery stages). For the exact execution order and current step list, inspect `docpluck/normalize.py`.

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
| C0 | Line-final BACKSPACE strip (furniture debris) | **v1.9.58.** Removes U+0008 where it stands at the END of a line — running-header debris pdftotext glues onto a real line (`10.3389/fvets.2025.1645266` p2 emits its header as form feed + `Abuna et al.` + BS). Runs **before F0** so the F0 comparison key (`_key`, which has discarded this character since v1.9.57) and the emitted text are ONE rule rather than two. **Deliberately one character wide:** over the 30-paper held-out PMC corpus all 33 U+0008 occurrences carry the identical context `'.'` + BS + newline and none carry the overstrike signature, while U+0002/03/04/07 in the same corpus are corrupted CONTENT glyphs (`Schri\x02macher` = "Schrittmacher") that deleting would destroy. Those are **counted**, not stripped — see `residual_control_chars` below. |
| F0 | Layout-aware running-header / footer / footnote strip | Requires `LayoutDoc` from `extract_pdf_layout`; populates `report.footnote_spans` (raw char offsets) and `report.footnote_texts` (the captured footnote strings, parallel — v2.4.83). Stripped footnotes move to an appendix after a `\n\f\f\n` marker. Optional. |
| H0 | Document-header banner-line strip | Runs only in the first 30 lines; curated `_HEADER_BANNER_PATTERNS`. v1.8.0. |
| T0 | TOC dot-leader paragraph strip | Drops paragraphs containing `_{3,}` runs in the head zone (first ~100 lines). v1.8.0. |
| P0 | Page-footer / running-header LINE strip | Curated `_PAGE_FOOTER_LINE_PATTERNS` matching single complete lines. Includes `^Q. XIAO ET AL.$`, `^RECKELL et al.$`, `^CONTACT …$`, `^Department of …, University of <Place>, <Region>$`, `^Supplemental data for this article …$`, truncated `^Department of …, University of$`, JAMA/AOM/PMC footers, etc. v1.8.0 + v2.4.6 + v2.4.8 + v2.4.16. |
| P1 | Front-matter metadata-leak PARAGRAPH strip | **v2.4.16.** Drops orphan acknowledgments / license blocks / "previous version" notes / correspondence blocks that pdftotext inlines as standalone single-line paragraphs mid-Introduction. Position-gated to the first `max(8000, len(text)//6)` chars so the legitimate `## Acknowledgments` section at the end is preserved. |
| W0 | Publisher-overlay watermark strip | "Downloaded from …", "Provided by …", "This article is protected by copyright", Royal Society OA footer, Elsevier copyright stamp, two-column running-header, equal-contribution footnote. v1.7.0–v2.3.1. |

**Ordering:** C0 → F0 → H0 → T0 → P0 → P1 → W0 → S0 (unicode) → S1 …

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

### A2, A3, A3a, A3c, A3d, W0n — ALL RETIRED (v2.4.129 / v2.4.130, 2026-08-14)

**These sections used to document six live rules. Every one is deleted.** They are recorded here
rather than removed because a consumer upgrading from an older version needs to know exactly what
stopped happening, and because the reasoning is the contract.

| rule | it used to do | why it is gone |
|---|---|---|
| `A2` | `p = 484` → `p = .484` | Repaired the **paper's** error. No cited paper in its code; both firing sites across 297 English papers were the author's, confirmed by rasterizing. |
| `A3` | `d = 0,45` → `d = 0.45` | EU→US conversion, out of scope. Fired 9 times in 2 papers and **not once correctly**. |
| `A3a` | `N = 1,182` → `1182` | Existed only to pre-empt `A3`, which is gone. Produced 1000× errors on comma-decimal tables. |
| `A3c` | `(0,003)` → `(0.003)` | EU→US conversion. Its one firing in 297 papers broke a reference-list URL. |
| `A3d` | `p = ,025` → `p = .025` | **0 sites in 897 papers.** Built on a constructed string copied forward through four documents. |
| `W0n` | `p < 05` → `p < .05` | Premise false — the same shape has **opposite owners** in two real papers. |

#### The two rules that decide all six

**1. docpluck canonicalises NOTATION; it does not repair the PAPER.** A Greek letter becomes
`chi`, a Unicode minus becomes ASCII, a superscript becomes a caret — those preserve the
statistical referent. Correcting an author's or a journal's mistake is different in kind, because
**docpluck has no channel through which to announce a repair**, so a silent one launders a real
defect into a meta-science pipeline: the consumer validates a number the paper never printed and
the author never learns. Flagging is ESCImate's and Scimeto's role — they have the UI and the
mandate. **The one exception:** a defect docpluck's own pipeline introduced (a fused exponent, a
glyph our text layer lost) is ours, because we caused it and the source is intact underneath.

**2. A rewrite must earn its evidentiary cost.** `1,000` is not a problem; it is clearly one
thousand. Rewriting it to `1000` repairs nothing and **removes information** — including the only
evidence a consumer would have that a table is European. The test: *could a competent downstream
consumer make a better decision if it saw the original token?* If yes, do not rewrite by default.

#### The evidence that settled it, in one line

**The same text shape has OPPOSITE OWNERS in two real English papers.**
`10.1016/j.jesp.2009.12.011` p3 **prints** `p < 05` — the author dropped the period.
`10.1177/0956797613482946` p6 **prints** `p < .05` — our OCR text layer lost it. A layout gate
calibrated to separate them (advance ratio 0.51 vs 0.99) was built and **refuted**: the second
paper is a scan whose char boxes come from an OCR engine, so the gate manufactures its own
evidence for exactly the case it exists to catch. Under irreducible ambiguity the default is
**pass-through**, because pass-through is reversible for the consumer and a repair is not.

#### What a consumer must now do

- Handle `1,182` and `0,45` yourself. `.replace(",", "")` is one line in your layer and reversible;
  it was irreversible in ours.
- Detect `p = 38.`, `p < 05`, `p = 001` yourself — and you are better placed to, because you hold
  the parsed statistic and its context.
- You may now run your own locale inference on our output, and you could not before: `academic`
  used to convert `d = 0,80` to `d = 0.80`, so a consumer inferring locale from our text was
  reading evidence we had manufactured.

**See `docs/SCOPE.md`, the internal notation-vs-repair inventory, and `LESSONS.md`
L-026/L-029/L-031/L-032.**

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

## Glyph-recovery steps (W0…) — and the EVIDENCE each one decides on

These undo corruption **docpluck's own input channel introduced**: a PDF whose embedded font has a
broken character map makes pdftotext deliver a glyph that is not what the page prints. That is
docpluck's to fix, unlike an error the authors made, which passes through untouched.

Every rule declares which kind of evidence it rests on. The distinction is a contract with
consumers, not bookkeeping:

* **TYPOGRAPHIC** — something the renderer actually put on the page: a surviving `(cid:N)` glyph,
  the font of *this* character, its size and baseline, a backslash glued to a numeral, a dash in a
  slot where its class is grammatically impossible. docpluck acts on these.
* **INFERENTIAL** — what a value *ought* to be given the values around it. This is properly the
  consumer's call: they hold the parsed statistic and a UI to flag it. Where docpluck keeps such a
  rule, it is **declared in `fallbacks`**, never silent.

| step | corruption | evidence | notes |
|---|---|---|---|
| W0b | `2` for U+2212 in a CI (`[20.45, 20.06]`) | INFERENTIAL | self-gated on a DESCENDING bracket, which is impossible for a real interval |
| W0c / W0o | `<` as `\` or as `b` (`\.001`) | **TYPOGRAPHIC** | a literal backslash glued to a numeral is not text |
| W0d | `2`-for-minus proven by point-estimate ∈ CI | INFERENTIAL | |
| W0e | Adobe-Symbol PUA codepoints | **TYPOGRAPHIC** | codepoint table |
| W0g | dropped minus proven by a CI bracket | INFERENTIAL | |
| W0h | dropped minus, proven by the layout's surviving `(cid:N)` | **TYPOGRAPHIC** | identity-based pairing since v2.4.133; REFUSES when context cannot separate candidates |
| W0i / W0k / W0l | `×` extracted as `3` | **TYPOGRAPHIC** | the font mis-draws the multiply glyph; the token conditions only bound where it is trusted |
| W0j sig. A | `2`-for-minus in a contrast-coding note | INFERENTIAL, self-corroborating | the `+ X.X = <word>` twin on the same line is a second emitted token |
| **W0j sig. B** | `Mchange = 20.14` | **INFERENTIAL** | keys on the variable NAME. `20.14` is not impossible in that slot, only implausible. Records `w0j_mstat_sign_inferred_from_variable_name` on every firing |
| W0m | `β` extracted as `b`, proven by the layout font | **TYPOGRAPHIC** | the coefficient value is part of the identity |
| W0p | a superscript footnote marker fused into a number (`2,5801`) | **TYPOGRAPHIC** | font size + baseline. Emits caret notation (`2,580^1`) — lossless, never deletion |
| **W0q** | a CI upper bound whose minus is DETACHED (`[-0.58,  -  0.18]`) | **TYPOGRAPHIC** | new in v2.4.134 |

### W0q — detached CI-upper minus (new in v2.4.134)

pdftotext separates a U+2212 from its digits on some fonts, so a printed `[−0.58, −0.18]` arrives
as `[- 0.58,\n- 0.18]`. A consumer whose CI pattern requires the sign adjacent to the digit reads
the upper bound as POSITIVE — a silently inverted interval.

The dash is a glyph the renderer emitted, and **the comma is what makes its reading unambiguous**:
in `[lo, – hi]` the comma already occupies the separator role, so the dash cannot be a range
separator (`0.19–0.45`) and can only be a sign that lost its kerning. The rule refuses to emit a
bracket that would run backwards.

This repair previously existed **only in the table-cell channel**, so a CI in a results sentence
never met it — the three-channel rule, violated. Confirmed against the rasterized page of
`10.1016/j.jesp.2021.104154` p13.

Recovery is reported per evidence class, and consumers should treat the two differently:

| `fallbacks` key | meaning |
|---|---|
| `ci_upper_minus_reattached_from_detached_dash` | typographic — the dash was on the page |
| `ci_upper_minus_inferred_from_containment` | inferential — no glyph survived; treat as a hypothesis |

**Neither key present does not mean the interval is sound.** See `docs/SCOPE.md`.

## Ordering Summary

```
extract_pdf()
    ↓
normalize_text(text, NormalizationLevel.academic)
    ↓
C0  Line-final BACKSPACE strip   ← pre-S0, before F0 (see the pre-S0 table)
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
    [A2 / A3 / A3a / A3c / A3d and infer_numeric_locale() WERE HERE — all
     deleted v2.4.129-130; numbers pass through exactly as printed]
A3b Statistical df-bracket harmonization
W0  glyph-recovery family (see the section above for each step's EVIDENCE class)
    W0_watermark, W0b, W0c, W0o, W0d, W0j, W0k, W0l, W0g,
    W0q  ← new v2.4.134: detached CI-upper minus, body-prose channel
    W0h, W0m, W0p  (layout-gated — only when `layout=` is supplied)
    W0e
A4  CI delimiter harmonization
A5  Math symbol and Greek letter normalization
A6  Footnote marker removal
    ↓
    normalized text + NormalizationReport
```

**Ordering constraint (v2.4.134):** W0q runs immediately after W0g. It must run **after** the
CI-pairing rules, because it rewrites the very bracket they read — repairing the bracket first
would change what W0g adjudicates. It exposed a latent defect in exactly that seam: with the CI
made parseable, W0g read the detached-minus ESTIMATE beside it as bare-positive and emitted
`d = - -0.38`. `_already_carries_a_sign` closes that, and the idempotency corpus gate is what
caught it.

**Critical ordering constraint:** A1 must run before S9. If S9 runs first, standalone digits like `484` (from `p =\n484`) are stripped as page numbers before A1 can rejoin them.

**Ordering constraint REMOVED (v2.4.130):** this document used to specify that the numeric-locale
inference had to run after header/footer removal and before A2/A3, "later and A3 has already
resolved the very commas it needs to read". That sentence is the clearest statement of the problem
that eventually deleted the whole feature: **docpluck's own normalization INVERTED the evidence the
inference depended on.** A consumer running locale inference on our output was reading commas we
had already converted. The inference, A2, A3, A3a, A3c, A3d and W0n are all gone, so the
constraint no longer exists — and a consumer's own inference is now valid, because the separators
it reads are the ones the paper printed.

## Report field: `residual_control_chars` (new in v1.9.58)

The count of C0 control characters **still present in the returned text** —
i.e. the ones `C0` deliberately did NOT remove because they are corrupted
*content* glyphs rather than furniture. Over the 30-paper held-out PMC corpus
there are 49 such characters in 16 papers (`Schri\x02macher` = "Schrittmacher",
`No\x04allsanitat` = "Notfall…", `A\x03 -B\x03 helices`).

They are counted rather than deleted because docpluck **extracts and
normalizes; it does not repair the paper** — and counted rather than left
silent because a known limitation written down without a measurement is an
unpaid debt, not a disclosure. A non-zero value is your signal that the text
holds characters no downstream regex will match; recovering the underlying
glyph is W0-family work that has not been done.

The count describes the string it is returned **alongside**, on every code
path including `NormalizationLevel.none`.

---

## Report field: `numeric_locale` — DELETED (v2.4.129)

**There is no `NormalizationReport.numeric_locale`.** This section used to document a
`NumericLocale` with a `verdict`, `confidence`, per-marker `evidence` counts and `computed_at`,
and told consumers to read it. The field, `infer_numeric_locale()`, `NumericLocale`,
`is_gating` and `LOCALE_MIN_GATING_CONFIDENCE` are all gone. A consumer following the old advice
would get an `AttributeError`.

**Why it was deleted, measured rather than argued.** Its verdict was **confidently wrong** on the
only genuine European table ever found in an English-language paper: `10.1177/0956797620935584`
Table S2, roughly 130 comma-decimal cells, scored `european_markers=0`, verdict `decisive_us`,
confidence 1.0. Every marker it used required an operator (`=`, `<`, `>`) immediately before the
value, and a bare table cell has none. So the reassuring measurement *"396 English articles → 0
European-locale documents"* described the **reach of the instrument**, not the corpus.

**Its stated purpose no longer exists either.** The field was justified by the fact that
"normalization inverts the evidence it is derived from" — `academic` turned every `d = 0,80` into
`d = 0.80`, so a consumer inferring locale from our output was reading evidence we had
manufactured, and this field was "the only channel through which the true verdict survives".
**That inversion is gone.** No rule converts or strips a numeric separator any more, so the text
you receive carries the paper's own separators and **your own inference on our output is now
valid**. An unmodified token beats a verdict we computed for you, and unlike the verdict it cannot
be wrong.

**The marker vocabulary is retained internally and unwired** (`tests/test_numeric_locale_markers.py`)
solely as the foundation for a future **LINE- or TABLE-scoped** guard — never for another
document-level verdict. The bilingual problem makes any whole-document answer false for part of the
document: a single SciELO paper carries `1,738 adult patients` (English abstract, a genuine
thousands group) and `528,329` (native-language body, the decimal 528.329).

See `docs/SCOPE.md`.