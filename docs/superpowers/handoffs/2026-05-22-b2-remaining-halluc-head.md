# Handoff — B2 HALLUC-HEAD remaining subcases

**Authored:** 2026-05-22, end of post-run-9-close session.
**Prereq commit:** `aaf38d0` (B2 packed-CRediT-line demote signal for chan_feldman).

## TL;DR

The chan_feldman `## Methodology` case from B2 is fixed (packed-CRediT-line
heuristic with ≥70 % coverage gate). Three other B2 mechanisms remain,
each its own demote heuristic.

## State at handoff

`aaf38d0` added Signal B to [`_demote_credit_role_headings`](../../../docpluck/render.py): either ≥3 whole-line role neighbours (original v2.4.53 logic) OR at least one packed-CRediT line in the ±10 window (≥3 distinct role substrings AND ≥70 % alphabetic-word coverage).

Tests passing: `test_demote_credit_methodology_packed_roles_line`, `test_demote_credit_methodology_keeps_real_methods_heading`, `test_max_distinct_roles_in_any_line_helper`.

## Open subcases

### B2a — `## Funding` from CRediT role `Funding acquisition`

Per [`HANDOFF_2026-05-18_iterate_run_9_cont.md`](../../HANDOFF_2026-05-18_iterate_run_9_cont.md) §B2:
> `## Funding` = CRediT role "Funding acquisition" split across heading + orphan word (gap in v2.4.53's `_demote_credit_role_headings`)

`_normalize_credit_role("Funding")` returns `"funding"`, which is NOT in `_CREDIT_ROLES` (the set contains `"funding acquisition"`). The packed-line Signal B may or may not fire depending on what's next to the `## Funding` heading.

**Approach:** when the heading text is a single role-word PREFIX of a multi-word `_CREDIT_ROLES` entry (`funding` is prefix of `funding acquisition`; `writing` is prefix of multiple), and the next non-blank line completes the role (`acquisition`, `original draft`, …), recognise the split form. Then run the existing Signal A + B test. Verify on chan_feldman (look for `## Funding` near `acquisition`).

### B2b — open-ended `## Conclusion` / `## Evaluation` / `## Findings` mis-promotions

Per the same handoff:
> plus open-ended `## Conclusion`/`## Evaluation`/`## Findings` mis-promotions.

These are NOT CRediT-role collisions. The partitioner promotes generic words that appear standalone in front-matter sidebars or appendix labels. The fix layer is the section partitioner / annotator, not the demote pass.

**Approach:** in [`docpluck/sections/`](../../../docpluck/sections/), require these specific labels to have ≥N lines of body prose AFTER them before promotion. Single-line headings followed by another heading or end-of-document are demotion candidates.

### B2c — G5d named (unnumbered) subsection headings demoted to body text

> Includes G5d — named (unnumbered) subsection headings demoted to body text (~7 papers: ar_apa_011 Participants/Overview, efendic, chandrashekar, ip_feldman).

OPPOSITE problem: real subsection headings (`Participants`, `Overview`, `Materials`) that look like ordinary capitalised words and get LEFT as body text instead of being promoted to `### Participants`. Layer: section partitioner. Tied to B2b (same code path).

## Step-by-step

1. Get AI golds for chan_feldman (existing), ar_apa_011, efendic, chandrashekar, ip_feldman via `article-finder generate-gold` (never self-generate).
2. Implement B2a (Funding split-role) first — narrow scope, single function edit.
3. Implement B2b + B2c together — they touch the same partitioner code.
4. Per-paper regression test using `requires_fixture` gate (PDF in `PDFextractor/test-pdfs/`).
5. Broad pytest + 26-paper baseline.

## Cross-references

- [`HANDOFF_2026-05-18_iterate_run_9_cont.md`](../../HANDOFF_2026-05-18_iterate_run_9_cont.md) §B2 (canonical detail)
- Memory `feedback_general_fixes_not_pdf_specific`
- [`LESSONS.md`](../../../LESSONS.md) §L-006-ish (section detector rules)
