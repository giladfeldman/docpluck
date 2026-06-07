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
