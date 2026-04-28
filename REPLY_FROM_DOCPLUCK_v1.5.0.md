# Reply from Docpluck — Request 9 (Reference-list normalization)

**To:** Scimeto / CitationGuard team
**From:** Docpluck v1.5.0
**Date:** 2026-04-27
**Re:** [REQUEST_09_REFERENCE_LIST_NORMALIZATION.md](REQUEST_09_REFERENCE_LIST_NORMALIZATION.md)

## TL;DR

Shipped in v1.5.0. **Three** real artifacts fixed (page-number digit residue, mid-ref newline, DOI line break). The two artifacts you described as "Bug 1" and "Bug 2" don't reproduce on actual Docpluck output — your reproducer used `pdftotext -layout`, which Docpluck has explicitly avoided since v1.0 (see `extract.py:13–16`). Defense-in-depth watermark library added anyway; the four publisher templates from your request are now stripped before any other normalization runs.

## What you got

`v1.5.0` adds four new normalization steps:

| Step | Scope                                  | Effect                                                                                                                                                                          |
| ---- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| W0   | standard + academic, document-wide     | Strip 4 publisher overlay templates (Royal Society "Downloaded from...", RSOS running-footer artifact, Wiley/Elsevier "Provided by...", "This article is protected by copyright...") before any other normalization. |
| R2   | academic, inside references span only  | Scrub orphan page-number digits glued mid-reference (e.g. `psychological 41 science.` → `psychological science.`). Bounded by lowercase-surround guard. |
| R3   | academic, inside references span only  | Join continuation lines that don't start with a Vancouver / IEEE / APA reference marker, eliminating mid-ref `\n` artifacts. |
| A7   | academic, document-wide                | Rejoin DOIs broken across a line by pdftotext (`doi:10.\n1007/...`).                                                                                                            |

`NORMALIZATION_VERSION` is now `1.5.0`. Each step reports through `report.changes_made` so you can see which fired:

```python
report.changes_made = {
    "watermarks_stripped":      <int>,
    "inline_pgnum_scrubbed":    <int>,
    "ref_continuations_joined": <int>,
    "doi_rejoined":             <int>,
    ...
}
```

## What we found in pretesting

We ran your repro PDF (`Li&Feldman-2025-RSOS-PCIRR-Revisiting-mental-accounting-Thaler1999-RRR-print.pdf`) through actual Docpluck (not `pdftotext -layout`):

- **"Bug 1" full URL watermark:** raw text has the `Downloaded from https://royalsocietypublishing.org/...` banner 41 times. After Docpluck v1.4.5 normalization it appears **0 times** — S9's "≥5 repetition" header/footer scrub already nets it. v1.5.0's W0 step strips it explicitly so it never reaches body text in the first place (defense-in-depth, also catches lower-frequency variants).
- **"Bug 2" orphan-paragraph reflow:** does not happen in default `pdftotext` mode. The default reading-order reflow puts each reference on essentially one line. The orphan-paragraph artifact you described (`Pract. Psychol. Sci. 1, 389–402.` as its own block) is a `-layout` mode artifact specifically. Docpluck has avoided `-layout` since v1.0 — see [extract.py:13–16](docpluck/extract.py).
- **Three actual artifacts that did survive normalization on this PDF, now fixed by R2/R3/A7:**
  1. Ref 17 read `psychological 41 science.` — the journal page-number `41` got glued mid-title. **R2 fixed.**
  2. Refs 4, 5, 11, 27, 42 had stray `\n` mid-reference (e.g. `Adv. Methods\nPract. Psychol. Sci.`). **R3 fixed.**
  3. Ref 38 had `(doi:10.\n1007/s10683-...)`. **A7 fixed.**

After v1.5.0, splitting the bibliography on `(?<=\s)(?=\d{1,3}\.\s+[A-Z])` yields **45 chunks numbered 1..45**, no missing list numbers.

## Likely cause of your "29 of 45 refs got list_numbers" symptom

If your downstream `referenceParser` saw refs 17–45 instead of 1–45, you're probably running your own `pdftotext -layout` somewhere — not consuming Docpluck's output. With Docpluck's default-mode output, all 45 numbers are present and consecutive. Worth double-checking:

```python
# Confirm you're calling docpluck, not pdftotext directly:
from docpluck.extract import extract_pdf_file
from docpluck.normalize import normalize_text, NormalizationLevel
raw, _ = extract_pdf_file(pdf_path)
text, report = normalize_text(raw, NormalizationLevel.academic)
# `report.version` should be "1.5.0"
```

If you confirm Scimeto IS already on Docpluck, can you share a single-PDF case where v1.5.0 still drops list_numbers? We'll add it to the regression fixture and chase it down.

## Regression posture

- **51-PDF corpus dry-run:** 0 regressions, 46 PDFs changed (W0 fires on the 7 RSOS-family PDFs; R3 fires on most PDFs; A7 fires on 7 RSOS PDFs).
- **Test suite:** 425 passing / 9 skipped (was 420 / 9). Five new tests in `tests/test_request_09_reference_normalization.py` lock the four acceptance criteria from your request, gated on the Li&Feldman fixture (skipped if the corpus is not present).
- **CLAUDE.md hard rules respected:** still no `-layout`, still no AGPL deps, still normalizing U+2212.

## What's still out of scope

- Citation matching, DOI resolution, retraction checking — yours.
- Reference *parsing* (splitting clean strings into authors/year/title/journal) — yours.
- Coordinate-aware overlay detection (Docpluck doesn't retain PDF coordinates; the W0 regex library covers the same publishers your request listed).

## What we'd like back

If v1.5.0 still leaves a real artifact in your pipeline, send the PDF + the exact downstream parse output you'd expect. We'll add it to the regression suite and fix in v1.5.1.
