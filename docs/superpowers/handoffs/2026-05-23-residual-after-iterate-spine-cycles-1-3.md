# Handoff — Residual after iterate-loop spine cycles 1-3 (2026-05-23)

**Authored:** 2026-05-23, end of the iterate-loop spine end-to-end validation
session.
**Owner:** next docpluck session (defect-fix work only — substrate hardening
is owned separately, see `~/.claude/skills/_shared/iterate-loop/`).
**Prereq commits:** `chore/docs-domain-cutover` branch — see commits
`94b2745`, `2980264`, `a794a0a`, `8c71394`.

## TL;DR

The iterate-loop spine substrate was built, wired into docpluck-iterate, and
end-to-end validated across cycles 1-3. The substrate now hard-gates every
cycle and every run-close on rules I1-I9. Cycle 1 baselined 5 canary papers
via parallel verifier subagents. Cycle 2 cleared the F0 / P0r running-header
strip class. Cycle 3 cleared the G5d HALLUC-HEAD-2 (`## Supplemental
Materials` mid-Method on ip_feldman). All cycles 0-regression on non-target
papers.

The substrate is doing exactly what it was built to do: **the gate refuses to
let any cycle declare PASS while open canary findings remain**, exactly as
the user's directive demanded after run-9 shipped 15 cycles on
idempotency=0 while ip_feldman kept rendering with affiliation leaks,
hallucinated headings, and mid-text table captions.

This handoff lists the items that REMAIN open, organised by source:

- §A — R1-R5 streams carried over from
  [`2026-05-22-residual-after-locally-doable-pass.md`](2026-05-22-residual-after-locally-doable-pass.md)
  (4 streams still open).
- §B — new defect classes uncovered by the cycle-1-2-3 verifier subagents
  against AI golds (5 new structural defect classes; per-paper finding
  counts below).
- §C — the broad pytest red test that was already failing before this
  session (`test_p0r_recurring_running_header_strip.py::test_plos_med_1_no_banner_or_footer`).

The LEAVE-NOTHING-BEHIND directive is still active. The substrate-level
hardening work is owned by a separate workstream (see
`~/.claude/skills/_shared/iterate-loop/LESSONS.md`).

---

## §A. Carried-over streams from 2026-05-22-residual (R1-R5)

Implementation status as of 2026-05-23 (verified via grep):

| Stream | Status | Evidence |
|---|---|---|
| **R1** B1 modified-Approach-B (whitespace_cells hook) | **NOT IMPLEMENTED** | `grep "whitespace_cells" docpluck/extract_structured.py` → 0 hits. The `whitespace_cells` helper exists in `docpluck/tables/whitespace.py` but is still never called from the main pipeline. The marker harvest in `tmp/b1-marker-harvest.txt` is the input (uns=15, empty=0, solo=0). |
| **R2** B2b/B2c AI-gold verification | **PARTIALLY DONE** | Cycle-1 verifier subagents covered chan_feldman + ar_apa + chandrashekar + ip_feldman against AI golds. Cycle-3 verifiers re-verified each. Result: B2b orphan-demote is HOLDING (no false-positive demotions observed across 5 papers); B2c isolated-method-subsection-promote is UNDER-FIRING (~60 H3 subsection demotions remain across 4 of 5 canary papers — see §B). The heuristic's "fully paragraph-isolated + prose-line after" gate is too conservative; needs relaxation per the gold's H3 structure. |
| **R3a** B4 maier Table 3 citation-cell edge | **NOT IMPLEMENTED** | No `et al.` / `citation-cell signature` extension in `_is_table_header_like_short_line`. |
| **R3b** FIG-3c-2 figure-caption double-emission | **NOT IMPLEMENTED** | No FIG-3c-2 helper anywhere. |
| **R4** B6 column-interleave | **NOT IMPLEMENTED** | `test_request_09` is GREEN per the original handoff (verified), but the underlying defect is STILL present in the cycle-3 verifier reports on chan_feldman Measures + chandrashekar Method. Architectural decision still pending. |
| **R5** B7 deleted-minus glyph | **PARTIALLY IMPLEMENTED** | `_recover_minus_in_record` + `recover_minus_via_ci_pairing` exist in `normalize.py` but didn't fire on ar_apa_j_jesp_2009_12_011's 4 beta sign inversions (`b = .022`, `b = .88`, `b = .245`, `b = .428`) — the helpers fire on CI-paired contexts only, not bare table-cell betas without CI brackets. Architectural decision still pending. |

**Detailed status per stream is in the 2026-05-22 handoff §R1-R5; this
handoff only updates which lines moved.**

## §B. New defect classes uncovered by cycle-1-2-3 verifiers

Across 5 canary papers, 4 cycles, ~12 verifier subagents, the following
defect classes appeared in at least 2 papers each AND are NOT already
captured by R1-R5. They are ranked by impact × generality.

### B-new-1 · B2-inverse — H3 subsections still demoted to flat text

**Affects:** 4 of 5 canary papers (ar_apa: 7, chan_feldman: ~25, ip_feldman:
~20, chandrashekar: 10; plos_med_1: ~19). Total ~80 findings.

**Symptom:** lines that should be `### <Heading>` per the gold's section
structure render as flat body text. The existing
`_promote_isolated_method_subsection_headings` only promotes a narrow
fixed-set of labels (`Participants` / `Materials` / `Procedure` / …) AND
only when paragraph-isolated AND followed by prose. The H3-shape that
appears in the corpus is broader:

```
…body of preceding subsection.

Self-control assessment

We then asked participants to indicate…
```

Where "Self-control assessment" is a paragraph-isolated short Title-Case line
followed by prose. It's not in `_METHOD_SUBSECTION_LABELS`, so it's not
promoted.

**Fix candidates:**
- (i) widen `_METHOD_SUBSECTION_LABELS` from the gold-extracted subsection
  titles across the 5 canary papers (lowest risk; per-paper-shape work).
- (ii) add a generic isolated-Title-Case-line promoter with shape gate
  (≤6 words, paragraph-isolated, followed by prose, not preceded by a
  sibling label). Higher risk of false-positives on figure captions /
  raw_text fragments — needs the same prose-line guard as B2c.
- (iii) keep current narrow set but add a "build from gold" registration
  pass that learns the per-paper expected subsection labels from the
  reading.md gold (paper-specific lookup; doesn't generalise).

Recommend (ii) with a synthetic-shape contract test + 5-canary regression
test. The shape gate eliminates the figure-caption false-positive class.

### B-new-2 · HALLUC-HEAD-3 — all-caps front-matter labels promoted to `##`

**Affects:** chan_feldman_2025_cogemo (`## KEYWORDS` at L33). Likely affects
any Cognition-&-Emotion-style PDF where `KEYWORDS` appears as an all-caps
metadata label between abstract and body.

**Symptom:** the partitioner promotes a single all-caps token to `##` when
it should be inline metadata (`**Keywords:**`).

**Cycle-3 verifier confirmation:** "the most obvious target was missed. The
guard's continuation-word semantics + h2-only + label-style exclusion
design missed the textbook case."

**Fix shape:** extend `_demote_continuation_promoted_headings` OR add a
separate `_demote_metadata_label_headings` for all-caps single-token
`##`-headings that are followed (within 3 lines) by inline metadata content
(no sentence verb, contains `;` / `,` separators).

### B-new-3 · HALLUC-HEAD-1 extension — PLOS Author-Contributions packed-CRediT

**Affects:** plos_med_1 (`## Methodology` at L739, packed-CRediT
continuation pattern).

**Symptom:** the existing `_demote_credit_role_headings` (B2a Funding
split-role) handles `## Funding` + `acquisition:` but doesn't catch the
PLOS Author Contributions form where `## Methodology` follows
`**acquisition: …** Investigation: …` (line 731-738).

**Fix shape:** extend `_demote_credit_role_headings` to recognise the PLOS
Author Contributions packed-CRediT continuation — when the prior 3-5 lines
contain `**acquisition:**` / `**Investigation:**` / `**Conceptualization:**`
etc. with multiple CRediT roles concatenated, treat the next `##` as a
continuation, not a new section.

### B-new-4 · Table-region misplacement — `## Data Availability` BEFORE `## Method`

**Affects:** ip_feldman_2025_pspb (L378 `## Data Availability` appears
mid-Method, BEFORE `## Method` at L392; the legitimate section is at the
endmatter).

**Symptom:** an italic inline label `*Data Availability, Preregistration,
and Open-Science Disclosures.*` gets partitioned into:
- a `## Data Availability` heading at line 378
- a body sentence `Preregistration, and Open-Science Disclosures.` at line 380

Splitting an italic inline-label into a heading is the defect. The
partitioner saw the first two words "Data Availability" + period and
promoted them.

**Fix shape:** in `sections/core.py` (or wherever `*…*` italic-inline-label
heuristics live), refuse to promote when the italic content is broken by a
comma — italic labels with commas are metadata phrases, not section
titles.

### B-new-5 · Front-matter banner concatenation (welded headers)

**Affects:** ip_feldman_2025_pspb (line 5: `PSPXXX10.1177/01461672251327169Personality and Social Psychology BulletinIp and Feldman`).

**Symptom:** pdftotext serialises the journal banner, DOI, journal name,
and running header as a single concatenated line because they're on the
same y-position in the PDF.

**Fix shape:** in the front-matter pass (early in normalize.py), detect the
DOI-prefix concatenation pattern (`[A-Z]+\d{8,}10\.\d{4,}` shape — journal
SAGE-style ID + DOI), split into separate lines at DOI boundary, suppress
the journal-name + running-header pieces.

## §C. Broad-pytest red test (pre-existing)

`tests/test_p0r_recurring_running_header_strip.py::test_plos_med_1_no_banner_or_footer`
has been RED since commit `b3d572f` (cycle-2 P0r ship, 2026-05-23 03:05:34).

**Assertion failing:** `len(['PLOS Medicine | https://doi.org/10.1371/journal.pmed.1004323 December 28, 2023'])` is 1, expected 0. The PLOS long-prose-title page footer is still leaking on plos_med_1 — the P0r 5-shape detector handles short repeating headers but not long prose-title repeating footers.

**Fix shape:** extend P0r with a 6th shape signature: a long line (≥40
chars) that repeats ≥3 times across the document AND is prose-like (starts
Title-case + contains `the` / `of` / `and` / a URL marker). Tighten with a
y-position cluster guard to avoid stripping legitimate repeating body
text.

This is the "P0r-F long-prose-title" candidate flagged in the cycle-3
proposal. It's the cleanest entry point because there's already a defining
test in the repo.

---

## What is OUT of scope for this handoff

The following are owned by the **substrate hardening workstream**, NOT this
handoff (which is for docpluck library defect fixes only):

- iterate-loop spine substrate improvements (`~/.claude/skills/_shared/iterate-loop/`)
- gate rule additions (I10, I11, …) or test harness expansion
- cross-project rollout (citationguard, escicheck, scimeto, 2rmarkdown)
- verifier prompt template standardisation
- run-meta schema extensions

Those items are tracked in `~/.claude/skills/_shared/iterate-loop/LESSONS.md`
and the cross-project alert
(`docs/iterate-loop-cross-project-alert-2026-05-23.md` if it ships).

## How to use this handoff

1. Read this file end to end.
2. Read [`2026-05-22-residual-after-locally-doable-pass.md`](2026-05-22-residual-after-locally-doable-pass.md)
   for R1-R5 context (the §R1-R5 sections are still authoritative for the
   shape of each fix; this handoff only updates which lines moved).
3. Pick a single defect class from §A or §B per cycle (the cycle-3 work
   showed one-defect-per-cycle bundling is correct and traceable).
4. Run docpluck-iterate; the spine substrate gates each cycle. The canary
   set is in `.claude/skills/_project/canary.json`.
5. NEVER declare a cycle PASS while findings remain; the gate will refuse
   it via I3.

## Sequencing recommendation

Lowest-risk-first:
1. §C `test_plos_med_1_no_banner_or_footer` — already RED, defines success;
   P0r-F long-prose-title extension. ~1 cycle.
2. §B-new-2 HALLUC-HEAD-3 (all-caps `## KEYWORDS`) — narrow guard
   extension, ~1 cycle.
3. §B-new-3 HALLUC-HEAD-1 (PLOS Author-Contributions packed-CRediT) —
   ~1 cycle.
4. §B-new-4 italic-label-with-comma guard — ~1 cycle.
5. §B-new-5 front-matter banner concatenation — ~1 cycle.
6. §A R1 B1 modified-Approach-B — bigger scope, needs AI-gold verification
   for 11 papers; ~2-3 cycles.
7. §B-new-1 B2-inverse subsection promotion — high-leverage, MEDIUM risk;
   ~2 cycles + canary corpus sweep to validate generality.
8. §A R4 B6 column-interleave + §A R5 B7 deleted-minus — escalation-class,
   need user sign-off before implementation.

Open backlog total: **~80 findings across 5 canary papers**. The substrate
ensures none of them get silently dropped.

## Cross-references

- [`2026-05-22-residual-after-locally-doable-pass.md`](2026-05-22-residual-after-locally-doable-pass.md) — predecessor handoff with R1-R5 detail.
- `~/.claude/skills/_shared/iterate-loop/core.md` — iterate-loop spine rules I1-I9.
- `~/.claude/skills/_shared/iterate-loop/LESSONS.md` — substrate audit findings (L-1 to L-13).
- `.claude/skills/_project/canary.json` — docpluck canary set (5 papers, all DOI-keyed).
- `~/.claude/skills/_shared/run-meta/docpluck-iterate.json` — live run state.
- Memories: `feedback_paper_locating_via_article_finder`, `feedback_iterate_loop_spine`, `feedback_no_codex_in_gold_audit`, `feedback_fix_every_bug_found`, `feedback_ground_truth_is_ai_not_pdftotext`, `feedback_gold_canonical_key`.
