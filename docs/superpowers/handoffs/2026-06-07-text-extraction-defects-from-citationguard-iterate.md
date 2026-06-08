# Text-extraction defects for docpluck — from citationguard-iterate (2026-06-07)

**Reporter:** citationguard-iterate (citelink accuracy loop).
**Verified against:** docpluck **v2.4.79**, `docpluck render <pdf> --level academic`
(this is the production path — the CitationGuard worker calls the hosted API
`/extract?normalize=academic&quality=true`). Every item below was confirmed to
**persist in `--level academic` output**, not just raw pymupdf — so each is a
current docpluck defect, not a stale-fixture artifact.

> Note: soft-hyphen (U+00AD) issues from the prior 2026-05-26 report are NOT
> repeated here — `--level academic` now strips U+00AD and rejoins correctly
> (verified: "Pos­avac"→"Posavac", "Bene­dict"→"Benedict", chen titles clean,
> 0 U+00AD in academic output). Thank you — that class is resolved.

Repro for any item:
```
docpluck render <pdf> --level academic | grep -n "<marker text>"
```
PDFs: nat_comms_2 = `CitationGuard/apps/worker/testpdfs/validation/nature/nat_comms_2.pdf`
(DOI 10.1038/s41467-023-42320-4); chen_2021 =
`ArticleRepository/fulltext/10.1016__j.jesp.2021.104154.pdf`.

---

## Class A — superscript reference markers DROPPED (nat_comms_2, Nature)

The trailing superscript citation numeral on a word is lost during extraction —
the word survives, the number vanishes. Confirmed against the AI gold + the
visible PDF (the numbers are real superscripts on those words).

| Marker | docpluck academic shows | Should be |
|---|---|---|
| 28 | `…JAK-STAT signalling being a significant…` | `…being a significant…²⁸` |
| 30 | `…immunosuppressants, such as dexamethasone, although…` | `…dexamethasone³⁰, although…` |
| 46 | `…proliferation and increased apoptosis…` | `…apoptosis⁴⁶` |
| 41 (×2, body) | `…respiratory disease severity.` | `…severity⁴¹.` |

**Impact:** citelink (citation detector) cannot detect a marker that is not in
its input → false "missed citation" + lower citation-recall on Nature papers.
**Likely cause:** superscript-glyph / small-font handling drops the run when it
ends a word at certain positions (NB: most superscripts DO survive — e.g.
"COVID-1914,27" below — so this is a subset, not a blanket loss).

## Class B — superscript GLUED to a preceding number-bearing token (nat_comms_2)

A superscript citation list is concatenated onto a compound that ends in digits,
with no separator: `COVID-19` + superscript `14,27` → **`COVID-1914,27`**.

| docpluck academic | Should be (so the citation is separable) |
|---|---|
| `…following COVID-1914,27 and…` | `…following COVID-19¹⁴,²⁷ and…` (or at least a separator before the citation digits) |
| `…persists months after COVID-1940,41.` | `…after COVID-19⁴⁰,⁴¹.` |
| `…in COVID-1928 …` | `…in COVID-19²⁸ …` |

**Impact:** the citation digits fuse with the term's own number ("1914,27"), so a
naive parser reads a single number. citelink now special-cases this, but the
clean fix is in extraction: emit a separator (or superscript markup) between a
`WORD-NN` token and a trailing superscript citation list.

## Class C — line-break dehyphenation removes a SEMANTIC hyphen (nat_comms_2 + chen)

A genuinely-hyphenated compound that wraps a line is joined WITHOUT the hyphen,
fusing two words. The same documents wrap true word-splits correctly
("inde-"+"pendent"→"independent"), so this needs dictionary/frequency awareness.

| docpluck academic | Should be |
|---|---|
| `cardiorespiratory` (nat_comms) | `cardio-respiratory` |
| `neutrophilassociated` (nat_comms) | `neutrophil-associated` |
| `SelfCompassion` (chen, "Self-Compassion and forgiveness…") | `Self-Compassion` |

**Impact:** corrupts reference titles and breaks title matching.

## Class D — reference-text losses / mangling (chen_2021, APA)

In each case the citing tool (citelink) parsed faithfully what it received; the
defect is in the extracted text.

| Reference | docpluck academic shows | Should be |
|---|---|---|
| Nosek & Lakens, 2014 | `Nosek, B. A., & Lakens, D. (2014). A method to increase the credibility of…` | title is `Registered reports: A method to increase the credibility of…` — the **"Registered reports: " prefix is dropped** |
| Open Science Collaboration, 2015 | `Open, S. C. (2015). Psychology…` | author is **"Open Science Collaboration"** (mangled into a fake initials author "Open, S. C."); title is `Estimating the reproducibility of psychological science.` |
| Litman et al., 2017 | `…TurkPrime. Com: A versatile…` | `…TurkPrime.com: A versatile…` — a **space is inserted inside the "domain.com" token** |

**Impact:** dropped title prefix, mangled organisation author, and split domain
token all corrupt reference parsing/matching.

---

## How these were found / how to re-verify after a fix

citationguard-iterate compares citelink output against AI gold (article-finder
`citations`/`intext_citations` views). After a docpluck fix, re-run
`docpluck render --level academic` on the two PDFs and confirm the "Should be"
column. The CitationGuard side will then regenerate its extraction fixtures from
docpluck academic (they are currently stale raw-pymupdf) and re-score.

**Cross-note to CitationGuard:** the iterate fixtures
(`apps/worker/tests/extraction-results/*.pdf_pymupdf.txt`) are raw pymupdf, but
production feeds citelink docpluck `--level academic`. They should be regenerated
from docpluck academic so the loop tests the real production input (this is why
the soft-hyphen class above was a false positive in the prior fixture-based pass).

---

## Maintainer analysis — layer-of-origin (added 2026-06-07 by docpluck-iterate)

All four classes reproduce at HEAD (v2.4.79). Each was traced to its origin
layer by comparing three artifacts on the two PDFs: raw pdftotext
(`docpluck.extract.extract_pdf`, the TEXT channel), the pdfplumber char stream
(`extract_pdf_layout`, the LAYOUT channel), and the `--level academic` render.

**Key finding: none of these is created by docpluck's normalize/render
transforms.** Every defect is already present, identically, in the *raw
pdftotext output* — i.e. it is a pdftotext-extraction-layer (or source-PDF)
artifact, not a docpluck bug introduced downstream. Per CLAUDE.md L-001 the
artifact-owning layer must own the fix; here that layer is pdftotext, which we
cannot change. The only docpluck-side remedy is a **layout-informed correction
pass** that uses the pdfplumber geometry docpluck already extracts to repair the
text channel (the same cross-channel pattern as the existing F0 running-header /
footnote strip). That is an architecture + product decision — see the open
decision at the bottom.

| Class | Reproduces | Origin layer | In raw pdftotext? | Recoverable via LAYOUT channel? | Notes |
|---|---|---|---|---|---|
| **A** superscript "dropped" | yes | pdftotext superscript-flattening | yes | **yes** | Not actually dropped — the numeral is flattened to baseline and *glued* to whichever token precedes it in reading order, so a word can appear bare (the numeral landed on a neighbour). Same root cause as B. |
| **B** superscript glued to number token | yes (`COVID-1928`, `COVID-1914,27`, `COVID-1921,22`, `COVID-1940,41`, `IL-646`, `severity21-25`) | pdftotext superscript-flattening | yes | **yes** | Layout proof: after `COVID-19` (sz=8.22, top=327.5) the citation digits `28` are sz=4.93 + raised (top=326.6) — unambiguous superscripts. NOT recoverable in text channel alone: `COVID-1928` is ambiguous vs the year 1928. |
| **C** semantic hyphen removed | yes (`cardiorespiratory`, `neutrophilassociated`) | pdftotext default-mode **dehyphenation** | yes | **yes** | Layout proof: source has `cardio-` (top=563.1) + line break + `respiratory` (top=573.8) with the hyphen glyph intact. pdftotext removes line-break hyphens (incl. semantic ones) when it joins; the hyphen is *gone* from the text channel, so this is unrecoverable there. |
| **D** reference mangling | partial | source PDF / pdftotext | yes | **no (mostly)** | `Registered reports:` title prefix is absent from **both** pdftotext *and* pdfplumber (genuine source-PDF loss — unrecoverable without an external citation DB, which would be a forbidden paper-specific hack). `Open, S. C.` and `TurkPrime. Com` are faithful-but-ugly source extractions; only "fixable" via risky, non-general text micro-rewrites. |

**Bottom line:** A, B, C are recoverable but ONLY via a layout-informed pass
(new capability, corpus-wide regression risk, plus a product decision on how to
emit citation markers). D is largely a source-PDF loss docpluck cannot fix
generally; citelink already special-cases it and that remains the right home.

### Is there a pdftotext flag for this? (checked — no)

Asked + tested against poppler 24.08:

- **No `pdftotext` flag** emits superscripts-as-markup or keeps semantic hyphens
  in the text output. `--help` has no `-superscript`/`-hyphen` option; all text
  modes (default, `-raw`, `-layout`) run the same lossy serialization (`-layout`
  is banned here regardless — L-002 column interleaving).
- The structured modes (`-tsv`/`-bbox`) expose per-word boxes. Empirically on
  these PDFs: `-tsv` **does** keep the line-break hyphen (`cardio-` is its own
  word) — so the hyphen is dropped by the *plain-text de-hyphenation join*, not by
  the tool. BUT `-tsv` shows a typesetting hyphen and a semantic hyphen
  identically (both are a line-end hyphen glyph), so keep-vs-drop still needs a
  dictionary. And for superscripts, pdftotext's word assembler merges the
  citation digits into the neighbouring word even in `-tsv` (no clean small-height
  token), so reliable superscript detection still needs char-level geometry
  (pdfplumber: digits are sz≈4.9 vs 8.2 body + raised).
- Net: no free flag. Every recovery is a *build* (geometry-aware correction pass,
  plus a dictionary for hyphens), which is the decision below.

### DISPOSITION — WON'T FIX in docpluck (user decision, 2026-06-07)

The maintainer chose **"keep the text channel pure pdftotext; do not build the
correction pass."** Rationale: it would add a geometry-aware correction layer to
the most regression-sensitive code path, for defects that originate upstream of
docpluck and that the consumer (citelink/scimeto) already compensates for — with
no cheap flag available. Per-class disposition: **A/B** won't fix (ambiguous in
text channel — `COVID-1928` vs the year 1928 — and citelink already special-cases
the glue); **C** won't fix for now (cleanest candidate if ever revisited);
**D** can't fix generally (`Registered reports:` is absent from *both* extractor
channels — a source-PDF loss; `Open, S. C.` / `TurkPrime. Com` are faithful
source extractions).

**Routing correction for CitationGuard/scimeto:** the prior triage boundary
("text-extraction defects are FILED in CitationGuard but FIXED in docpluck") does
**not** hold for these items — they are won't-fix in docpluck. Compensation stays
on the consumer side (citelink reference/citation parsing), where Class B is
already handled. The one substrate action that remains is CitationGuard's own:
regenerate the iterate fixtures from docpluck `--level academic` (not raw
pymupdf). **No docpluck release is required for anything in this report.**

> ⚠️ **SUPERSEDED 2026-06-07 (resume):** the user reversed the blanket won't-fix
> and directed "review, verify, and fix it all to the best you can" + "build O5
> now." The authoritative disposition is now the **"RESOLUTION (2026-06-07
> resume)"** section appended at the very bottom of this file. The won't-fix text
> above is retained only as the record of the earlier decision.

---

## RESOLUTION (2026-06-07 resume) — full review of EVERY scimeto item

Per the user's "review, verify, and fix it all to the best you can," I went
through every docpluck-routed item across **all** of scimeto's communications for
this run — this handoff (A–D), `CitationGuard/docs/DOCPLUCK_HANDOFF_2026-06-07.md`,
and `CitationGuard/docs/TRIAGE_iterate_2026-06-07.md` (O1–O5 + the 06-07b
dispositions) — and verified each at HEAD (v2.4.79) against the **raw pdftotext**
and **pdfplumber layout** channels (not pymupdf, not the rendered .md alone).

> **STRONGER A/B finding (2026-06-07d, tested):** a deep re-investigation + direct
> testing of citelink **reversed** the original ask. citelink ALREADY detects the
> glued form (`apoptosis46`→[46], `severity43`→[43], `COVID-1914,27`→[14,27]); its
> detector regex `([a-z.)"])(\d{1,3}…)` is *built* for letter-adjacent digits, so a
> docpluck split (`apoptosis 46`) or Unicode superscript (`⁴⁶`, not ASCII `\d`)
> would **REGRESS** citelink detection (verified: both split forms return n=0). Plus
> a split corrupts math exponents (`g/cm²`→`g/cm 2`, 29 in sci_rep_1, in body prose).
> So A/B are won't-fix in docpluck for a stronger reason than "ambiguous": fixing
> them breaks the consumer. The only real residual — `COVID-1928` (single citation,
> digit-ending host) — is a citelink special-case extension (it already handles the
> comma-list shape). Full evidence + the citelink test table:
> `CitationGuard/docs/DOCPLUCK_HANDOFF_2026-06-07.md` → "🛑 UPDATE 2026-06-07d".

| Item (scimeto) | Verified layer-of-origin | Verdict |
|---|---|---|
| **A** superscript "dropped" (nat_comms) | text channel — numeral is **flattened to baseline + glued to a neighbour token** (`apoptosis46`), *not* dropped | **WON'T-FIX docpluck — citelink already detects the glued form; a docpluck split would REGRESS it** (tested, see note above). No docpluck action. |
| **B** superscript glued to number token (`COVID-1928`) | text channel | **WON'T-FIX docpluck.** Splitting breaks citelink + is exponent-ambiguous (`g/cm²`). The single-`COVID-1928` miss is a citelink special-case gap (it already catches `COVID-1914,27`). |
| **C** semantic hyphen removed (`cardiorespiratory`) | text channel — pdftotext's **dehyphenation join** drops line-break hyphens incl. semantic ones | **won't-fix for now.** Real on nat_comms; needs a layout+dictionary build (declined). NB chen `SelfCompassion` from the handoff **does not occur** in chen's text at all (misattributed). |
| **D** reference mangling (chen) | source-PDF / text channel — **confirmed absent from raw pdftotext too**: `Registered reports:` prefix is gone; `Open, S. C.` and `TurkPrime. Com` are the *literal* pdftotext extraction | **can't-fix generally.** Source loss / faithful-but-ugly extraction; stays in citelink. |
| **Strömwall → "Str¨omwall"** glyph-mangle (TRIAGE 06-07b item 4) | — | **already resolved.** At HEAD academic it renders correctly as `Strömwall`; the detached-diaeresis form was a **pymupdf-fixture artifact**, not present in the production pdftotext/academic path. No action. |
| **O5** chen references "36 stranded before the References header" | **docpluck reading-order** (real; NOT the A–D class) | **real docpluck bug** — see below. |

**So: of everything scimeto routed to docpluck, O5 is the only genuine
docpluck-side defect. A/B/C/D and Strömwall are correctly consumer-side or
already resolved** (each verified at the raw-channel level, not assumed).

### O5 — root cause + why it is the in-progress region-aware architecture

On chen's **physical page 19** the reference list is two-column, and pdftotext
**inverts the columns**: it emits the right column (C–E…Fritz…Gelman) *before* the
left column (the `References` heading + Aarts…Benjamini). The page is **banded** —
a CRediT contributor *table* occupies the top, the two-column references the
bottom — so a naïve whole-page column-correction would crop the table into halves
and garble it, and the corrector's whole-page bilateral-table gate (correctly)
rejects the page.

This is the **same root cause** as the `ip_feldman` B4/R4 tracks already
diagnosed in the committed spec
`docs/superpowers/specs/2026-06-07-ip_feldman-B4-R4-column-interleave-diagnosis.md`:
*pdftotext column-interleaves table-bearing two-column pages.* The spec's fix is
**region-aware column detection** (segment the page into full-width table bands vs
two-column prose bands; column-correct only the prose bands). That work was
**user-approved and a validated prototype built, but deliberately NOT wired live**
because a half-tuned reading-order change silently corrupts the corpus (the
char-ratio/Jaccard corpus gate is blind to "right words, wrong order"); the spec
records that live wiring + tuning + full corpus+AI gating is "the next focused
session."

**Working-tree cleanup (LEAVE NOTHING BEHIND):** I found `extract_columns.py` in
the working tree carrying a **broken, abandoned half-wire** of that architecture —
an `IndentationError` plus a call to an **undefined** `_detect_2col_midline_gutter`
— which made the module un-importable. Because the column-corrector is imported
lazily and its failure is swallowed by an `except Exception` in `normalize.py`,
this had **silently disabled column-correction for every flagged paper** (e.g.
plos). I restored the file to clean committed HEAD; the module imports and
column-correction works again. (No diagnosis was lost — it lives in the committed
spec; the working-tree prototype was never committed and was non-functional.)

### O5 disposition — FIXED in v2.4.80 (user-greenlit gated build, 2026-06-07 resume)

O5 is **fixed**. The user approved the gated build; it landed as the
reading-order half of the region-aware column track, scoped tightly enough to be
corpus-safe (no full band-segmentation was needed — chen/jamison's reference
band sits cleanly below the contributor table, so left-then-right column
re-extraction suffices).

**What shipped (`extract.py` + `extract_columns.py`, no `NORMALIZATION_VERSION`
change — text channel only):**

1. **`_detect_reference_inversion_pages`** — cheap text-only trigger: a page with
   ≥3 reference-entry lines (`Surname, F. M.`, anchored at line start) appearing
   ABOVE its own `References` heading. Unambiguous inversion signature; fires on
   exactly **2 of 101** corpus papers (chen p19, jamison p9) — both genuine.
2. **`_detect_2col_midline_gutter`** — full-height empty central gutter-strip
   midline detector; resolves the narrow (~4pt) reference-column gutter the
   histogram can't, and bypasses the bilateral-table gate (a clean full-height
   strip can't coexist with a full-width table row). Confined to the inversion
   path (`allow_gutter_fallback`) so the legacy column path stays byte-identical.
3. **Word-preservation guard** (`word_preserve_pages`) — the re-extraction is
   accepted only if it preserves the page's substantial-word multiset (every
   alphabetic token len ≥2): a pure reorder that can never drop or fabricate
   reference text (rules 0a/0b).

**Verification:** chen now has **0** reference entries stranded before the
heading (was 36+) and **101 entries in alphabetical order** after it; jamison
likewise (0 stranded, 37 entries); all key surnames present per the AI gold. The
other **99 corpus papers are unchanged** (detector doesn't fire; legacy path
byte-identical). 32 existing column tests pass + 5 new real-PDF tests
(`tests/test_o5_reference_inversion_real_pdf.py`) + the 26-paper corpus baseline
gate. Version 2.4.79 → **2.4.80**.

**A–D and Strömwall remain as in the RESOLUTION table above** — text-channel /
source-PDF / already-resolved, no docpluck change. Only O5 shipped.
