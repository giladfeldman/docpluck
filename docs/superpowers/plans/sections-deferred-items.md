# Sections — deferred items

**Created:** 2026-05-08, end of strict-iteration campaign.
**Source iteration:** [HANDOFF_2026-05-07_sections_strict_iteration.md](../HANDOFF_2026-05-07_sections_strict_iteration.md).
**Final spot-check:** [spot-checks/2026-05-08_spot-final_all-styles.md](spot-checks/2026-05-08_spot-final_all-styles.md).
**Issues backlog:** [sections-issues-backlog.md](sections-issues-backlog.md).

---

## Why this document exists

The 2026-05-07 strict-iteration shipped 12 fixes and brought the cross-style corpus to 98/101 PASS or PASS_W (97 % acceptance, 9/9 styles converged with ≥3 consecutive first-try-clean). The remaining 3 hard fails could not be addressed without disproportionate effort or risk of regression. **Each is recorded here in full** so that:

1. Future sessions can pick up exactly where this iteration stopped.
2. Nothing is lost to "I'll remember to come back to that" optimism.
3. The cost / risk / generalization assessment that justified deferral is auditable.

If you're a future Claude session resuming sections work: read this doc *first*, then the spot-check, then the issues backlog.

---

## Convention

Each deferred item has a fixed schema:

- **Symptom** — what fails, on which paper(s).
- **Root cause** — what's actually wrong (often upstream of the sections module).
- **Why deferred** — the cost / risk / scope reason.
- **What would fix it** — a concrete plan a future session can execute.
- **Affected files / corpus paths** — where to look.
- **Risk of regression** — what could break if the fix is naïve.

---

## Deferred 1 — `jdm_.2023.10` is a 1-page archival correction notice (not a research paper)

- **Symptom:** Strict-bar grader reports `FAIL` with `missing hard ['abstract', 'references']`. Total normalized text is 1534 chars; only 2 sections detected (`unknown`, `keywords`).
- **Root cause:** Not a sectioner bug. The PDF is a published 1-page **archival correction notice / addendum** for Deppe et al. 2015 ("Reflective liberals and intuitive conservatives — ADDENDUM"). It contains: journal masthead, "ADDENDUM" tag, title repeat, author list, keyword line, two short paragraphs of correction text. **There IS no abstract, no references list, no methods.** The strict bar's "every canonical section the paper visually contains" is satisfied trivially because nothing canonical exists.
- **Why deferred:** The correct behavior is exactly what's happening — the sectioner extracts what's there and labels it accurately. The grader's `FAIL` is a grader-side categorization issue, not a sectioner-side bug. Adjusting the grader to recognize "this is a correction notice, not a paper" would require document-type classification, which is out of scope for the sectioner.
- **What would fix it:** Add a corpus-level filter that excludes documents where `total_chars < 3000` AND `n_sections < 3` from strict-bar grading (treating them as known-non-papers). The PDF itself stays in the corpus as a regression-test fixture for "we don't crash on tiny correction notices".
- **Affected files / corpus paths:**
  - `PDFextractor/test-pdfs/apa/jdm_.2023.10.pdf`
  - Any future grader that consumes `extract_sections` output.
- **Risk of regression:** Zero. The library handles this PDF correctly today.

---

## Deferred 2 — `nathumbeh_2` is a 59-page Nature Hum Behav supplementary materials document (column-bleed extraction)

- **Symptom:** Strict-bar grader reports `FAIL` with `missing hard ['abstract']`. Detected sections include `introduction`, `results` (×5), and **70 `supplementary` sections**. Title text is mangled (`'ASurtpicplleementary information https://doi.org/...'`).
- **Root cause:** Two-column layout where left column says `Article` / `Supplementary information` and right column has the title. pdftotext (and pdfplumber, verified) interleaves the columns producing nonsense like `ASurtpicplleementary` (= `A`/`Supplementary` interlocked). The sectioner faithfully partitions whatever it gets, but the input is corrupted at the extraction layer.
- **Why deferred:** This is a 59-page **supplementary materials** document, not a regular research paper. Out of scope for the sections module's strict-bar promise.
  Even if we did want to fix it, the only durable fix is extraction-layer column detection (`extract_pdf_layout` or `pdfplumber` with custom column-aware page chunking) — substantial work for a single edge case.
- **What would fix it:**
  1. Filter `nathumbeh_2.pdf` from the strict-bar grading corpus on the grounds that it's supplementary materials, not a paper.
  2. Long-term: explore using `extract_pdf_layout` (existing in the library) for two-column Nature publications. The layout-aware F0 step does strip running headers; it might also resolve column bleed if invoked on a `LayoutDoc` with column boundaries. Hasn't been wired into `extract_sections` (which uses plain `extract_pdf`).
- **Affected files / corpus paths:**
  - `PDFextractor/test-pdfs/nature/nathumbeh_2.pdf`
  - `docpluck/extract.py` (layout extraction is available but not used by sections)
- **Risk of regression:** None for option 1 (corpus-filter only). Option 2 is a larger change that should be its own work item.

---

## Deferred 3 — `plos_med_1` leading title block is 5.5 % of doc (just over the 5 % grader threshold)

- **Symptom:** Strict-bar grader reports `FAIL` with `unknown 5.5%`. The paper has all canonical sections detected (`abstract`, `introduction`, `methods`, `results`, `discussion`, `references`); the only fail is the leading-unknown title block being 2567 chars / 5.5 % of the 46,669-char paper.
- **Root cause:** PLOS Medicine layout has 13+ author affiliations on separate lines after the title. `'1Department of Sociology, Vanderbilt ... 2Department ... 3Department ...'` runs ~485 chars, plus title + DOI + journal masthead = 2567 chars before the first canonical heading. For a relatively short clinical-trial paper (46k chars), this works out to just over 5 %.
- **Why deferred:** The structural detection is correct — every canonical section IS detected. The fail is a grader threshold tuning issue, not a sectioner bug. Bumping the grader to 6 % or 7 % would let plos_med_1 pass but it's not really a quality issue to start with.
- **What would fix it:**
  - Quick fix: bump the grader's leading-unknown threshold from 5 % to 7 %. The strict bar (handoff §2) says "Title-block prefix unknown is fine if <2%"; the pragmatic grader's 5 % was already a relaxation. A 7 % cap still flags genuine catastrophic title-block bloat (33 % for `maier_2023_collabra` before fixes).
  - Alternative: differentiate "leading unknown" (acceptable up to ~7 %) from "mid-doc unknown" (acceptable up to ~1 % per the strict bar) and apply different thresholds. This is the more principled approach.
- **Affected files / corpus paths:**
  - `PDFextractor/test-pdfs/vancouver/plos_med_1.pdf`
  - Any consumer that re-implements the strict-bar scoring (currently only `_scratch_score.py`, which is deleted as part of this iteration cleanup).
- **Risk of regression:** Zero — grader-side change only.

---

## Other items observed during iteration but NOT pursued

These showed up in grading but aren't full failures (papers PASS with PASS_W warnings). Documented here so future hardening passes can pick them up.

### O.1 — JDM Cambridge 2023 papers have run-together word extraction

- **Affected:** `jdm_.2023.15.pdf`, `jdm_.2023.16.pdf`, `jdm_m.2022.2.pdf` (PASS or PASS_W today).
- **Symptom:** pdftotext (and pdfplumber, verified) extract text without interword spaces — `"Short-sighteddecisionscanhavedevastatingconsequences"`, `"Competinginterest. Theauthorsdeclarenone."`. The sections are detected correctly via canonical heading lookup (which works on numbering + heading word), but the section bodies have the run-together prose. End-of-paper labels like `Competing interest.` go undetected because the canonical regex requires `\b` word boundaries that don't exist in run-together text.
- **Root cause:** Cambridge JDM PDFs use a font that omits space characters in the Type-1 encoding. Both poppler (pdftotext) and pdfminer (pdfplumber) render literally what's in the stream.
- **Plan:** Out of scope for sectioner. A dictionary-based word-splitter pre-pass in `normalize.py` is theoretically possible but is a large undertaking. Defer indefinitely; track in the article-finder LESSONS.md as a known-bad-extraction class.

### O.2 — Some Elsevier papers have a borderline 2.0–2.3 % title-block unknown

- **Affected:** `ar_apa_j_jesp_2009_12_011.pdf` (2.1 %), `ar_apa_j_jesp_2009_12_012.pdf` (2.3 %) — currently PASS_or_PASS_W.
- **Symptom:** Strict bar says title-block <2 %. These two are 0.1–0.3 % over.
- **Plan:** Within rubber-band tolerance. Not a fix candidate. Mentioned for completeness.

### O.3 — Theory papers with NO body sections genuinely lack methods/results/discussion

- **Affected (lots):** AOM AMC editorials, BJPS political-philosophy papers, Royal Society papers. All currently PASS_W.
- **Symptom:** "no methods", "no results", "no discussion" warnings on theory papers.
- **Plan:** Genuinely correct behavior — these papers don't have those sections. The pragmatic grader counts substantial Introduction (>3000 chars) as body, which lets them pass. Don't try to synthesize methods/results/discussion sections that don't exist.

### O.4 — Combined "Results and discussion" heading satisfies one canonical, not both

- **Affected:** `nat_comms_1.pdf` (PASS_W with `no discussion`).
- **Symptom:** Heading text `Results and discussion` maps to canonical `results`, so the paper's discussion content is captured but not labeled separately.
- **Plan:** Conceptually a multi-label problem. The pragmatic grader marks this as PASS_W; for full strict-bar credit, a future enhancement could attach BOTH `results` and `discussion` markers when the heading is the combined form. Risk: low. Effort: small. Worth doing if a v2.2 round happens.

### O.5 — AOM "Academy of Management" front matter is one undivided line cluster

- **Affected:** `amd_2.pdf`, `amp_1.pdf`, `annals_1.pdf`, `annals_2.pdf` — all currently PASS or PASS_W after the line-fallback synthesis added 2026-05-08.
- **Status:** Now passing. Documented as a class so future regression-testing can spot it.

### O.6 — Royal Society Open Science papers use "1. Summary" instead of "Abstract"

- **Affected:** `ar_royal_society_rsos_140066/072/081.pdf` — all currently PASS_W after re-adding `summary` to canonical (2026-05-08).
- **Risk:** Re-adding `summary` to canonical could in theory re-introduce v1.6.1's regression on meta-analyses (per-study Summary subsections). The mitigation is the existing dedup/coalesce logic plus the fact that meta-analyses in our corpus haven't surfaced as regressions. Watch this on the next QA run. If meta-analysis regressions appear, switch to a position-aware safeguard (only treat Summary as abstract when it's the FIRST canonical section in the doc).

### O.7 — Webapp consolidation parallel track (handoff §8)

- **Status:** Not addressed in this iteration (explicitly out of scope per the handoff).
- **Plan:** When sections quality is locked in, brainstorm the unified `/document` UX with the user. Use `superpowers:brainstorming` per the handoff guidance.

---

## How to verify the deferred items haven't drifted

Run, from the docpluck repo root:

```bash
# 1. Sections + normalize regression suite
python -m pytest tests/test_sections_*.py tests/test_normalization.py -q
# Expected: 250 pass, 2 skipped (as of 2026-05-08).

# 2. Per-style strict-bar grading
# (Re-create _scratch_grade_batch.py / _scratch_score.py from spot-check report appendix.)
for sty in apa ieee nature vancouver aom ama asa harvard chicago-ad; do
    python _scratch_grade_batch.py $sty | python _scratch_score.py /dev/stdin
done
# Expected hard fails (3 total):
#   apa/jdm_.2023.10.pdf            (Deferred 1 — addendum)
#   nature/nathumbeh_2.pdf          (Deferred 2 — supplementary)
#   vancouver/plos_med_1.pdf        (Deferred 3 — borderline 5.5%)
# Any new hard fail = a regression. Investigate before shipping.

# 3. Full repo suite
python -m pytest tests/ -q
# Expected: 744 pass, 18 skipped.
```

---

## Last word

If a future session opens this file, the implicit question is "is this still the state?". Two checks:

1. Re-run the verification commands above. If anything has drifted, surface it before doing new work.
2. Skim [sections-issues-backlog.md](sections-issues-backlog.md) for any new entries — it's the live ledger; this file is a snapshot of the deferred subset at end of the 2026-05-07 / 08 iteration.

Decisions to defer were made carefully; decisions to revisit deferrals should also be made carefully.
