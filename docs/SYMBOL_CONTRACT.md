# docpluck symbol contract

**Contract version 2.0** · introduced in docpluck v2.4.128 · machine-readable via
`docpluck.symbol_contract()`

This is the authoritative statement of what docpluck emits for every Greek letter and every
sub/superscript form it transliterates, at `normalize_level="academic"` — the level every
statistics consumer uses.

**If you maintain a tool that parses docpluck's output, this page is your interface.** Build your
patterns from `symbol_contract()` rather than from samples or from a copy of our tables.

---

## Why this exists

Until v2.4.128 docpluck could spell the same Greek letter two different ways depending on which
extraction path handled the document. Two tables lived in one library — one in `normalize.py`'s A5
step, one in `extract.py`'s SMP math-italic fallback — and they had diverged on **9 of 9 shared
letters**:

| codepoint | SMP fallback path | A5 path |
|---|---|---|
| MATHEMATICAL ITALIC CHI | `ch` | `chi` |
| MATHEMATICAL ITALIC ETA | `n` | `eta` |
| MATHEMATICAL ITALIC BETA | `b` | `beta` |
| MATHEMATICAL ITALIC RHO | `r` | *(unmapped)* |

The consequences were silent, and three were **collisions with a different statistic**:

- `chi2(2) = 5.10` on one path became `ch2(2) = 5.10` on the other. A consumer matching `chi2\(`
  therefore **never checked that chi-square test, and nothing reported it.**
- `eta2` became `n2`, colliding with **n**, the sample size.
- `beta` became `b`, colliding with **b**, the unstandardized coefficient — which is precisely the
  corruption another docpluck module (`W0m`) exists to detect and undo from layout font evidence.
  One path manufactured what another repairs.
- `rho` became `r`, colliding with **r**, the correlation.

A library that can convert one input two ways has no contract at all. Both paths now read one
table, and a shared test asserts they **agree** rather than restating the constants twice.

---

## Greek

Every letter is spelled out in full. **`chi`, never `ch`. `rho`, never `r`. `beta`, never `b`.**
Short forms are ambiguous against Latin statistical symbols that mean something else entirely —
`b`, `n`, `r`, `s` and `d` are all real statistics — and an ambiguity here is indistinguishable
downstream from a real value.

### Lowercase — always transliterated

| | | | | |
|---|---|---|---|---|
| α → `alpha` | β → `beta` | γ → `gamma` | δ → `delta` | ε → `epsilon` |
| ζ → `zeta` | η → `eta` | θ → `theta` | ι → `iota` | κ → `kappa` |
| λ → `lambda` | μ → `mu` | ν → `nu` | ξ → `xi` | ο → `omicron` |
| π → `pi` | ρ → `rho` | σ → `sigma` | ς → `sigma` | τ → `tau` |
| υ → `upsilon` | φ → `phi` | χ → `chi` | ψ → `psi` | ω → `omega` |

### Variant codepoints — same letter, different codepoint, same output

A publisher's font decides which codepoint lands in the text, and the **same statistic must not
flatten or survive depending on that choice**. U+03D5 GREEK PHI SYMBOL is the phi *coefficient*,
and it was unmapped while U+03C6 GREEK SMALL LETTER PHI was mapped — 39 occurrences across 3 of
250 corpus papers, including a `95% CI for ϕ` table header.

ϕ → `phi` · ϑ → `theta` · ϵ → `epsilon` · ϰ → `kappa` · ϖ → `pi` · ϱ → `rho` · ϐ → `beta`

### Uppercase with no Latin lookalike — always transliterated

Γ → `Gamma` · Δ → `Delta` · Θ → `Theta` · Λ → `Lambda` · Ξ → `Xi` · Π → `Pi` · Σ → `Sigma` ·
Φ → `Phi` · Ψ → `Psi` · Ω → `Omega`

### Uppercase that looks identical to a Latin capital — standalone tokens only

Α Β Ε Ζ Η Ι Κ Μ Ν Ο Ρ Τ Υ Χ are transliterated **only when the character stands alone as a
token**:

```
'Β = .31'           ->  'Beta = .31'        standalone: transliterated
'ANOVA'             ->  'ANOVA'             inside a word: left alone
'a within-Ν design' ->  'a within-Ν design' hyphen is word-joining: left alone
```

A broken font encoding that emits Greek Alpha for a Latin A inside a word would otherwise turn
`ANOVA` into `AlphaNOVA` — corrupting prose to fix a symbol. Standalone, the codepoint is the only
evidence available and it says Greek: an author who meant the letter A would have typed the
Latin A.

---

## Superscripts and subscripts

### Subscripts — always transliterated

**A subscript RUN joins the token before it with a single underscore** — `eta2_p`, `M_p`, `H_a`, `M_beta`, `BF_01`. One underscore per run, not per character. Contract v1.0 *fused* them (`eta2p`, `Mp`, `Mbeta`), which produced tokens that read as something else: the `p` of partial eta-squared collides with a p-value, and `Mp` is indistinguishable from a variable of that name.

Digits ₀–₉ → `0`–`9`. Latin subscript letters (U+2090–U+209C, the complete block) → their letter:
ₐ `a` · ₑ `e` · ₒ `o` · ₓ `x` · ₔ `e` · ₕ `h` · ₖ `k` · ₗ `l` · ₘ `m` · ₙ `n` · ₚ `p` · ₛ `s` ·
ₜ `t`. Phonetic subscripts ᵢ `i` · ᵣ `r` · ᵤ `u` · ᵥ `v`. **Greek subscripts take the Greek
spelling**: ᵦ `beta` · ᵧ `gamma` · ᵨ `rho` · ᵩ `phi` · ᵪ `chi` — a subscript beta is not the
letter `b`.

So `η²ₚ` → `eta2_p`. Before v2.4.128 it left as `eta2` plus a live U+209A, and measured end to end
that degraded effectcheck from `effect_reported = 0.04`, status **PASS**, to `NA`, status **OK** —
a verified effect size silently downgraded to unverified by one character.

### Superscripts — position decides

**This is the one rule a lookup table cannot express.**

| context | behaviour | example |
|---|---|---|
| after a **letter** | flattens to a bare digit — it is a symbol suffix | `η²` → `eta2`, `R²adj` → `R2adj` |
| after a **digit** | becomes **caret notation** — it is an exponent | `10⁹` → `10^9`, `2×10⁻⁶` → `2*10^-6` |

Flattening an exponent would **fuse it into the mantissa**: `×10⁹/L` became `x109/L` (v1.0), a clinical
lab value nine orders of magnitude wrong and unrecoverable. Caret is used rather than leaving the
glyph because it is flat ASCII, unambiguous, and already the form effectcheck's own normalizer
produces internally when it folds Unicode superscripts before its extraction regexes run.

**Stated residual ambiguity:** `N = 42³` may be a footnote marker rather than 42-cubed, and the
text channel cannot decide. `42^3` keeps both readings recoverable where `423` destroys them.

---

## Stated ambiguities we do NOT resolve

Honesty about what we cannot disambiguate is part of the contract.

| construct | output | why |
|---|---|---|
| `×` (U+00D7) | `*` | `2 × 3 design` → `2 * 3 design`; `×10⁹/L` → `*10^9/L`. v1.0 used the letter `x`, indistinguishable from a variable named x. A significance star is positionally distinct — it *trails* a value, never sits between two operands. |
| a superscript digit after a digit | `^N` | may be an exponent or a footnote marker; geometry does not separate them |
| dashes | all folded to ASCII `-` | codepoint does not predict role: one corpus paper uses U+2013 EN DASH as its house minus sign, while others use it for ranges |
| Greek capitals inside words | left alone | see above |

---

## Scope

- Applies to **`normalize_level="academic"`**, the level statistics consumers use.
- **Not** applied when `preserve_math_glyphs=True` — the `/render` path is deliberately
  source-faithful and keeps the original glyphs.
- Applies to PDF, DOCX and HTML input **through `normalize_text()`**.

> ### ⚠ KNOWN GAP — `extract_sections()` on DOCX and HTML does NOT apply this contract
>
> **Corrected 2026-08-14.** This section previously read *"Applies identically across PDF, DOCX
> and HTML input"*, and that was **false for the sections path**. Measured:
>
> ```
> input                                    We found χ²(2) = 5.10; β = −0.20; η²ₚ = .04; the ﬁrst effect.
> normalize_text(academic)                 We found chi2(2) = 5.10; beta = -0.20; eta2_p = .04; the first effect.
> extract_sections(html).normalized_text   We found χ²(2) = 5.10; β = −0.20; η²ₚ = .04; the ﬁrst effect.
> ```
>
> The PDF branch of `extract_sections` calls `normalize_text`; the DOCX and HTML branches
> annotate the raw extractor output and never normalize it. **The field name
> `normalized_text` is therefore a false claim on those two branches**, and every statistic a
> DOCX/HTML section consumer reads arrives unnormalized.
>
> **If you consume `extract_sections()` on DOCX or HTML, run `normalize_text()` on the text
> yourself until this is fixed.** (`extract_sections(normalization_level=…)` already *refuses*
> a non-default level on those branches rather than ignoring it, so nothing silently pretends
> to have applied one.)
>
> The fix is a factoring job, not a patch: the contract's steps (W0e, S0, S2–S6, A5) live
> inline inside `normalize_text` alongside furniture-stripping and line-joining steps that are
> calibrated to pdftotext's line structure and are **not** safe to run on an HTML block. They
> need extracting into one shared entry point that all three formats call — the same
> *one concept, one table* remedy used for `docpluck/symbols.py`. Tracked; not attempted as a
> late edit to the hottest file in the library, because a silent regression in the PDF path
> would cost more than this gap does.

---

## Using the contract

```python
from docpluck import symbol_contract, explain_symbol

c = symbol_contract()
c["version"]              # '2.0' — bumped only when the contract CHANGES
c["greek"]["χ"]           # 'chi'
c["greek_ambiguous_upper"]  # the standalone-only capitals
c["subscript"]["ₚ"]       # 'p'  (emitted as '_p' — see the underscore rule)
c["positional_rules"]     # the rules a table cannot express, as prose

explain_symbol("χ")
# "U+03C7 GREEK SMALL LETTER CHI -> 'chi' (always)"
```

`explain_symbol` is for debugging a pattern that did not match: paste in the character you saw in
the source and it tells you what docpluck did with it.

**Do not hard-code a copy of these tables.** A hand-maintained copy in a consumer is the same drift
this contract exists to end — citelink already keeps its own copy of docpluck's ligature map, and
effectcheck its own locale inference. Read `symbol_contract()` at runtime, or generate your
patterns from it at build time and assert on `version`.

---

## For consumer maintainers

If your tool matches any of these tokens, please check it against this table:

- **effectcheck / ESCImate** — `parse.R` folds a fixed alternation
  `(?:eta2p|η2p|etap2|ηp2|eta_p2|…)`. `eta2p` is what we emit; confirm the rest of your
  alternation matches this contract, and that your chi-square pattern expects `chi2` (we never
  emit `ch2`).
- **Scimeto / CitationGuard** — `statisticalExtractor.ts`.
- **citelink** — hand-maintains a copy of docpluck's ligature map; consider reading
  `symbol_contract()` instead.

If a symbol you rely on is missing here, that is a docpluck bug — please report it rather than
working around it locally, because a local workaround is invisible to us and diverges silently.
