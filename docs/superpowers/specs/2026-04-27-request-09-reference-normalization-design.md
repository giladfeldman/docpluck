# Design — Request 9: Reference-list normalization

**Date:** 2026-04-27
**Source request:** [REQUEST_09_REFERENCE_LIST_NORMALIZATION.md](../../../REQUEST_09_REFERENCE_LIST_NORMALIZATION.md) (Scimeto / CitationGuard)
**Version:** Docpluck `1.4.5` → `1.5.0`

## Pretest finding (revises the request's diagnosis)

Scimeto's reproducer used `pdftotext -layout`. Docpluck explicitly avoids `-layout` (see `extract.py:13–16`). On actual Docpluck output of the same PDF (`Li&Feldman-2025-RSOS-...-print.pdf`):

- The full-URL watermark (`Downloaded from https://royalsocietypublishing.org/...`) is already stripped by S9. Raw=41 occurrences, normalized=0.
- All 45 references are present with correct numbers 1–45, splittable by `(?<=\s)(?=\d{1,3}\.\s+[A-Z])`.

The actual artifacts that survive normalization are smaller:
1. **Page-number digit residue** glued mid-line in references (e.g. `psychological 41 science.` in ref 17 — silently corrupts the title).
2. **Mid-ref single newlines** from in-PDF line wraps (e.g. `Adv. Methods\nPract. Psychol. Sci.` in ref 5).
3. **DOI cross-line breaks** (e.g. `(doi:10.\n1007/s10683-...)` in ref 38).

## Five components

| ID  | Step                          | Where                                   | Behavior                                                                                                                                                                                                                                                       |
| --- | ----------------------------- | --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| W1  | Watermark template library    | New step before S0 in `normalize_text`  | Strip 4 known overlay regexes anywhere in document: (a) `Downloaded from URL on DATE`, (b) RSOS running-footer (`\d+royalsocietypublishing.org/journal/\w+ R. Soc. Open Sci. \d+: \d+`), (c) `Provided by ... on YYYY-MM-DD`, (d) `This article is protected by copyright....`. |
| R1  | References-section detector   | Helper (no pipeline step)               | Find `^(References?\|Bibliography\|Works Cited\|Literature Cited)$` followed within 5k chars by ≥3 ref-like patterns. End on `Acknowledg/Funding/Supplementary/Appendix/Notes/Conflict`. Returns `(start, end)` or `None`.                                              |
| N1  | Inline orphan-digit scrub     | Academic-only step inside refs span     | Build set of standalone page numbers from raw text (lines matching `^\s*\d{1,3}\s*$` appearing ≥2 times). Inside refs span, delete ` <pg> ` matching `(?<=[a-z])\s+<pg>\s+(?=[a-z])`.                                                                                |
| N2  | Continuation-line join        | Academic-only step inside refs span     | Inside refs span, lines that don't start with a ref-start pattern (`^\d{1,3}\.\s+[A-Z]`, `^\[\d+\]\s+[A-Z]`, `^[A-Z][a-z]+,\s+[A-Z]\.`) are joined to the previous non-blank line with a single space.                                                              |
| N3  | DOI cross-line repair         | Academic-only, document-wide, after S7  | Replace `(doi:\S*\d)\.\s*\n\s*(\d)` with `\1.\2`.                                                                                                                                                                                                                |

W1 runs in **standard** + **academic** levels (publisher overlays are not academic-specific). N1, N2, N3 run **academic-only** because they require structure-aware rules.

## Pipeline insertion order

```
W0_watermark_strip       (NEW — before S0)
S0..S9                   (existing)
A1..A6                   (existing, academic)
R1_references_section    (NEW — academic, computed once, used by R2/R3)
R2_inline_pgnum_scrub    (NEW — N1)
R3_continuation_join     (NEW — N2)
S7-extension: DOI rejoin (NEW — N3, runs as A7 in academic level)
```

Total new steps: 4 tracked through `report._track()` (W0, R2, R3, A7). R1 is a helper, not a step.

## Regression safety

- **Bounded blast radius:** R2/R3 only fire if R1 finds a references span (≥3 ref-like patterns required).
- **Existing tests:** all 420 pass on baseline. New steps are additive within their level; synthetic-string tests in `test_normalization.py` test individual steps and are unaffected.
- **Corpus dry-run:** prototype tested against 51 PDFs in ESCIcheckapp/testpdfs — 0 regressions, 46 changed, max length delta ±66 chars on 100k+ char documents.
- **New regression file:** `tests/test_request_09_reference_normalization.py` asserts on Li&Feldman PDF (skipped if absent):
  - `Downloaded from https://royalsocietypublishing` not in normalized output
  - bibliography splits into 45 chunks numbered 1..45
  - ref 17 normalized text does not contain ` 41 science`
  - ref 38 normalized text contains `doi:10.1007/s10683`

## Versioning + reporting

- `NORMALIZATION_VERSION` 1.4.5 → **1.5.0**
- `__version__` 1.4.5 → **1.5.0**
- New report keys in `changes_made`: `watermarks_stripped`, `inline_pgnum_scrubbed`, `ref_continuations_joined`, `doi_rejoined`
- New step codes: `W0_watermark_strip`, `R2_inline_pgnum_scrub`, `R3_continuation_join`, `A7_doi_rejoin`

## What is intentionally not in scope

- Re-implementing reference parsing (authors/year/title split) — stays downstream.
- Layout-aware overlay detection via PDF coordinates — Docpluck doesn't retain coords; the W1 regex library covers the same cases the request demanded.
- Switching extraction to `-layout` mode — explicitly forbidden by CLAUDE.md per long-standing benchmarks.

## Reply to Scimeto

A separate `REPLY_FROM_DOCPLUCK_v1.5.0.md` will summarize:
- The pretest finding (their reproducer used `-layout` which Docpluck doesn't use; full-URL watermarks were already stripped).
- The three real artifacts that did survive and are now fixed.
- Confirmation that `splitIntoReferences` on Docpluck output of the test PDF should yield 45 numbered chunks.
- Recommendation: confirm Scimeto is consuming Docpluck output (not running its own pdftotext), since the `-layout` artifacts they described don't appear in Docpluck's pipeline.
