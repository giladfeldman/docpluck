# Docpluck Request 9 — Reference-List Normalization (Watermark Stripping + Continuation Reflow)

**Requested by:** Scimeto / CitationGuard team
**Date:** 2026-04-27
**Priority:** MEDIUM (silently corrupts numbered bibliographies; affects every consumer that parses references)
**Related:**
- `REQUEST_08_CHUNKING_ENDPOINT.md` (architectural sibling — both move structural concerns up into Docpluck instead of downstream parsers)
- Scimeto referenceParser: `apps/worker/src/processors/referenceParser.ts` (the downstream consumer that currently has to defend against these artifacts)

---

## TL;DR

When Docpluck normalizes a Vancouver/IEEE/Nature/AMA-style bibliography, two specific layout artifacts survive `normalize=academic` and corrupt the reference list seen by downstream parsers:

1. **Page-watermark text is glued mid-line into the reference list.** Royal Society Open Sci PDFs (and others) render `Downloaded from https://royalsocietypublishing.org/ on 18 September 2025` as an overlay that ends up concatenated *between* two numbered references — typically eating the leading `"N. "` of the next ref so its number is lost.
2. **Continuation lines from the same reference land in their own paragraph.** When a reference's tail (journal abbreviation + volume/issue/pages) wraps to a new line and the original PDF has extra vertical whitespace there, Docpluck emits a blank line, so the tail becomes its own paragraph block. Downstream parsers see it as an orphan reference with no list number.

Both are extraction/normalization concerns, not bibliography-parsing concerns. Every consumer (Scimeto, ESCImate, MetaESCI, future tools) re-implements defensive workarounds for the same artifacts — fixing once in Docpluck removes that duplication and produces better data for everyone.

---

## Reproducer (single PDF, two distinct bugs)

**File:** `c:/Users/filin/Dropbox/Vibe/MetaScienceTools/ESCIcheckapp/testpdfs/Li&Feldman-2025-RSOS-PCIRR-Revisiting-mental-accounting-Thaler1999-RRR-print.pdf`

**Source:** Royal Society Open Science, PCI-RR Stage 1 Registered Report, 45 numbered Vancouver-style references on pages 31–32, then a supplementary section.

**What Scimeto observed in production** (pre-Docpluck-fix): of 45 references in the bibliography, only 29 received a `list_number`, and the recovered numbers ranged 17–45 instead of 1–45. Refs 1–16 lost their number entirely. The user reported it as a "Vancouver parser misnumbering" bug; investigation traced it to extraction artifacts, not the parser.

**Reproduction with `pdftotext -layout`** (close enough to current Docpluck output to trigger both bugs deterministically):

```
                                                                          15. Leclerc F, Schmitt BH, Dube L. 1995 Waiting time and decision making: is time like money? J. Consum. Res. 22, 110–119. (doi:10.1086/209439)
                                                                          16. Samuelson P. 1963 Risk and uncertainty: a fallacy of large numbers. Scientia 57, 49–56.
Downloaded from https://royalsocietypublishing.org/ on 18 September 2025  17. Nosek BA, Hardwicke TE, Moshontz H, Allard A, Corker KS, Dreber A, Vazire S. 2022 Replicability, robustness, and reproducibility in psychological 41royalsocietypublishing.org/journal/rsos R. Soc. Open Sci. 12: 250979
                                                                               science. Annu. Rev. Psychol. 73, 719–748. (doi:10.1146/annurev-psych-020821-114157)

                                                                          18. Zwaan RA, Etz A, Lucas RE, Donnellan MB. 2018 Making replication mainstream. Behav. Brain Sci. 41, e120. (doi:10.1017/S0140525X17001972)
```

Two artifacts visible above:
1. The line beginning `Downloaded from https://royalsocietypublishing.org/ on 18 September 2025  17. Nosek BA…` — that's the page-watermark glued to ref 17. There is no newline between the watermark and `17.`, so any downstream splitter that splits on `\n` before a number cannot separate them.
2. The fragment `41royalsocietypublishing.org/journal/rsos R. Soc. Open Sci. 12: 250979` is *also* a watermark/header (the running footer of the article), inlined into ref 17.

In a different layout (refs 4 / 5 / 11 / 27 / 38 / 42 in the same PDF), Docpluck-equivalent normalization emits the journal-abbreviation tail of a ref as its own paragraph block — e.g. `Pract. Psychol. Sci. 1, 389–402. (doi:10.1177/2515245918787489)` is the tail of ref 5, not its own ref.

Full evidence is in the conversation that produced this request: a 54-block dump of what `splitIntoReferences()` saw after `pdftotext` extraction is reproducible in seconds via Scimeto's worker dist parser.

---

## Bug 1 — Page-watermark / running-header stripping

### What Docpluck currently does

`normalize=academic` already strips many running headers (page numbers, journal short titles repeated on every page). The Royal Society-style overlay slips through because:

- It contains a full URL (looks like reference content)
- It contains a date (looks like a citation year)
- It is rendered by the PDF viewer as an *overlay layer* sitting over the body text, not as a separate header in the layout, so layout-aware extractors merge it inline with whatever text is at the same y-coordinate.

### What Docpluck should do

**Detect and strip per-page overlay watermarks** before paragraph segmentation. Heuristics that should trigger removal:

1. The string **repeats verbatim on ≥3 pages** of the same document at the same approximate y-coordinate. (Royal Society overlays repeat on every page.)
2. The string matches a known overlay template (regex library), e.g.:
   - `Downloaded from https?://[^\s]+ on \d{1,2} \w+ \d{4}`
   - `\d+\s*royalsocietypublishing\.org/journal/\w+\s+R\.\s*Soc\.\s*Open\s*Sci\.\s*\d+:\s*\d+` (the running footer artifact)
   - `Provided by [\w\s]+ on \d{4}-\d{2}-\d{2}` (Wiley/Elsevier downloader watermarks)
   - `This article is protected by copyright\..*`
3. The string appears at a y-coordinate **outside the main text frame** as detected by the layout pass (most overlays are in margins).

Stripping should apply **before** text reflow so the watermark doesn't get glued to body text in the output.

### What "fixed" output looks like

```
15. Leclerc F, Schmitt BH, Dube L. 1995 Waiting time and decision making: is time like money? J. Consum. Res. 22, 110–119. (doi:10.1086/209439)
16. Samuelson P. 1963 Risk and uncertainty: a fallacy of large numbers. Scientia 57, 49–56.
17. Nosek BA, Hardwicke TE, Moshontz H, Allard A, Corker KS, Dreber A, Vazire S. 2022 Replicability, robustness, and reproducibility in psychological science. Annu. Rev. Psychol. 73, 719–748. (doi:10.1146/annurev-psych-020821-114157)
18. Zwaan RA, Etz A, Lucas RE, Donnellan MB. 2018 Making replication mainstream. Behav. Brain Sci. 41, e120. (doi:10.1017/S0140525X17001972)
```

Each reference begins with its number, on its own line, with no inlined watermark text.

### Why this belongs in Docpluck, not downstream

- Detection requires **multi-page evidence** (the "repeats on ≥3 pages" heuristic). Downstream parsers see a single normalized text blob and have no access to per-page layout, so they can only do single-string regex stripping that misses novel watermark templates.
- Layout-aware overlay detection requires the original PDF's coordinate system. Docpluck has it; downstream parsers don't.
- Every downstream consumer would otherwise re-implement the same regex library and watermark-detection heuristics, with the bug recurring whenever a new publisher's overlay appears.

---

## Bug 2 — Reference-paragraph reflow

### What Docpluck currently does

When the source PDF has a vertical-whitespace gap mid-reference (because the typesetter pushed the journal-info tail to the bottom of a column, or because a column break landed inside the ref), Docpluck currently emits the gap as a blank-line paragraph break. That turns the tail into its own block, e.g.:

```
5. LeBel EP, McCarthy RJ, Earp BD, Elson M, Vanpaemel W. 2018 A unified framework to quantify the credibility of scientific findings. Adv. Methods

Pract. Psychol. Sci. 1, 389–402. (doi:10.1177/2515245918787489)

6. Tversky A, Kahneman D. 1981 The framing of decisions and the psychology of choice. Science 211, 453–458. (doi:10.1126/science.7455683)
```

The middle paragraph is the tail of ref 5, but a downstream parser sees three paragraph blocks and treats the middle one as a separate, numberless reference.

### What Docpluck should do

Inside the **References / Bibliography section** (which Docpluck can detect via its existing section-segmentation logic), use a stricter paragraph-reflow rule:

- A new paragraph starts **only** if the line begins with a reference marker:
  - `^\d{1,3}\.\s` (Vancouver / AMA / Nature)
  - `^\[\d+\]\s` (IEEE)
  - `^[A-Z][a-z]+,\s+[A-Z]\.` (APA-style author start)
  - `^[A-Z][a-z]+\s+[A-Z]{1,3},` (Vancouver-style author start without comma)
- Any other line within the references section is a **continuation** and should be joined to the preceding reference with a single space, regardless of how much vertical whitespace preceded it.

This is fundamentally a section-aware reflow rule: outside the references section, blank lines are real paragraph boundaries; inside it, blank lines are visual artifacts of column/page layout.

### What "fixed" output looks like

```
5. LeBel EP, McCarthy RJ, Earp BD, Elson M, Vanpaemel W. 2018 A unified framework to quantify the credibility of scientific findings. Adv. Methods Pract. Psychol. Sci. 1, 389–402. (doi:10.1177/2515245918787489)
6. Tversky A, Kahneman D. 1981 The framing of decisions and the psychology of choice. Science 211, 453–458. (doi:10.1126/science.7455683)
```

Each reference is on a single logical line, regardless of how the source PDF wrapped it.

### Why this belongs in Docpluck, not downstream

- The "is this a continuation?" decision needs to know **which section we're in**. Docpluck's `normalize=academic` already does section detection (it knows where References starts). Downstream parsers re-derive section boundaries from text, which is fragile.
- The reflow rule is style-aware (Vancouver vs APA author-start patterns), but **Docpluck already has style metadata** if the chunking endpoint from Request 8 lands. Even without it, the union of "starts with `N.`, `[N]`, or `Lastname, X`" covers all major styles.
- Without this fix, every downstream parser invents its own continuation-merge heuristic, and they all get edge cases wrong differently. (Scimeto's current heuristic, for example, requires either `length < 60` or specific journal/location keywords — fragments like `Pract. Psychol. Sci. 1, 389–402.` slip through both because they're 63 chars and start with a publisher abbreviation not in the keyword list.)

---

## Test fixture suggestion

Add the li-feldman PDF to Docpluck's test corpus with two assertions:

1. After extraction, the string `Downloaded from https://royalsocietypublishing.org` does **not** appear in the output text (watermark stripped).
2. The string `41royalsocietypublishing.org/journal/rsos R. Soc. Open Sci. 12: 250979` does **not** appear in the output text (running-footer artifact stripped).
3. Splitting the references section on `^\d{1,3}\.\s` produces **45 chunks** (one per reference) with consecutive numbers 1 through 45.

These assertions will catch regressions in both watermark handling and reference reflow with one fixture.

---

## Why now (priority justification)

- **Silent data corruption.** Numbered references without `list_number` in Scimeto cannot be matched to in-text Vancouver citations (`[17]`, `(17)`) by position, which is the only matching signal Vancouver provides. Citations show as "unmatched" even when the reference is present in the bibliography.
- **Affects an entire publisher family.** Royal Society Open Science is just the most obvious case; any publisher that renders a "Downloaded from…" overlay (Wiley, Elsevier, ProQuest, JSTOR PDFs) hits the same bug class.
- **Rises with academic-PDF volume.** Both Scimeto and ESCImate are increasing throughput on real academic PDFs, so the rate of "looks correct but silently wrong" reference parsing is climbing.
- **Single PDF reproduces both bugs.** Cheap to add to the regression suite, broad coverage gain.

---

## Out of scope for this request

- Citation matching / DOI resolution / retraction checking — these stay in Scimeto.
- Reference *parsing* (splitting a clean reference string into authors/year/title/journal) — stays in Scimeto's referenceParser.
- Publisher-specific behavior beyond watermark stripping (e.g. canonicalizing journal abbreviations) — stays in downstream consumers.

This request is strictly about getting clean, structurally-faithful reference-section text out of Docpluck. The boundary moves up by one layer; Docpluck owns "extract + normalize + segment," consumers own "interpret."
