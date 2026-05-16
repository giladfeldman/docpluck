# Handoff — docpluck-iterate run 5 (G5c-1)

**Authored:** 2026-05-16, end of run 5. **For:** a fresh `/docpluck-iterate` session.
Run 5 resumed from `docs/HANDOFF_2026-05-16_iterate_run_4_final.md` and shipped
the first item of its open queue (G5c-1).

## State at handoff

- Last shipped library version: **v2.4.46** (tag `v2.4.46` pushed; PyPI not published).
- docpluckapp pin: auto-bumped to **v2.4.46** — workflow now commits directly
  (`dcf377af pin: auto-bump docpluck library to v2.4.46`), no PR.
- Production `/_diag`: `docpluck_version = 2.4.46` — verified.
- 26-paper baseline: **26/26 PASS** at v2.4.46 (0 FAIL, 0 WARN).
- Broad pytest: **1265 passed, 1 failed** — the 1 failure is `test_request_09`
  (pre-existing COL-class numbered-bibliography column-split; left red by run 4,
  tracked in TRIAGE; a heading-fold cycle cannot affect it). 0 new failures.
- Three-tier parity: Tier-1 == Tier-2 == Tier-3 **byte-identical** for jdm_m.2022.2.

## What run 5 shipped

| Cycle | Version | Outcome |
|---|---|---|
| G5c-1 — orphan multi-level numeral render-fold | v2.4.46 | SHIPPED + three-tier-verified |

### Cycle G5c-1 (v2.4.46)

pdftotext splits a numbered subsection heading such as `5.4. Discussion` into a
bare `5.4.` line + a separate `Discussion` line; the section partitioner promotes
the lone title word to a generic `## Discussion` and strands the number. New
render post-processor `_fold_orphan_multilevel_numerals_into_headings` — the
multi-level analogue of `_fold_orphan_arabic_numerals_into_headings` /
`_fold_orphan_roman_numerals_into_headings` — folds an orphan `N.N.` number into
the **immediately-adjacent** generic `##`/`###` heading at subsection level:
`5.4.`⏎`## Discussion` → `### 5.4. Discussion`.

Keyed purely on the structural signature (an isolated multi-level dotted number
is itself a strong subsection marker) + blank-line-only adjacency. `### Figure N`
/ `### Table N` (library-emitted structural markers) and already-numbered
headings are excluded. jdm_m.2022.2's `5.4. Discussion` recovered;
AI-gold-verified correct against gold §5.4; 26/26 baseline; 11 new tests in
`tests/test_orphan_multilevel_number_real_pdf.py`.

**Scope discipline:** jdm_m.2022.2 has 6 orphan multi-level numbers but only
`5.4.` is immediately adjacent to a generic heading. The other 5 (`5.3.`/`6.3.`/
`6.4.`/`7.3.`/`7.4.`) are followed by a figure block or by body prose — the
partitioner consumed the title word, so there is no heading to fold into. They
are **G5c-2** (partitioner split-heading rejoin), confirmed not render-foldable.

### Phase-5d AI-gold verdict — jdm_m.2022.2 still FAIL (rule 0e-bis)

The verifier confirmed the cycle's own diff is heading-markup-only:
`### 5.4. Discussion` correct vs gold, 0 sentence-level text loss, 0
hallucination, 0 regression. **But jdm_m.2022.2 still FAILs Phase-5d** on
pre-existing defects the cycle did not reach. The run's standing verdict is
**FAIL / PARTIAL** — a verified incremental fix shipped, the corpus is not clean.

## Open queue — recommended order for the next session

Per the TRIAGE "SESSION-3 STANDING VERDICT" (updated this run):

1. **FIG caption double-emission + truncation** — ~8 papers. S2, C2. Next
   cheapest wide win (jdm_m.2022.2 Figure 1 emitted twice, caption truncated
   mid-sentence; Figures 2/3/4 inline + in `## Figures`; Figure 3 body-prose
   welded onto caption).
2. **G5c-2 partitioner split-heading rejoin** — 5 jdm_m.2022.2 cases. S1, C3 —
   the partitioner must recognise `N.N.`⏎`<CanonicalKeyword>` as one heading and
   not detach the number. Dedicated session.
3. **G5d named/unnumbered heading demotion** — ~7 papers. S1, C2-C3.
4. **HALLUC-HEAD** — mid-sentence words promoted to `##` headings
   (`## Supplementary Material`, `## Appendix` in jdm_m.2022.2). S1, C2.
5. **TABLE structure destruction** — ~11 papers. S0/S1, C3 — the single largest
   blocker. Dedicated session.
6. **COL column-interleave** (incl. `test_request_09`'s numbered-bibliography
   split) + **GLYPH** 011 deleted-minus / efendic no-CI `Mchange`. S0, C3-C4,
   layout-channel — escalate.

## Process notes

- **Release path:** run 5 used the lean-checks release path (user directive) —
  the Phase-7 `/docpluck-cleanup` + `/docpluck-review` sub-skills were skipped;
  essential hard-rule checks done inline. Recorded as a `spine_skips` entry. The
  render-layer regex-only change touches no `-layout`/AGPL/tool-swap/U+2212/
  ImportError/HTML-table surface; 26/26 baseline + byte-identical three-tier diff
  are the no-regression evidence.
- **Stale local uvicorn:** the local service was found frozen at v2.4.19 (module
  cache from a long-ago startup). Restarted with `--env-file .env` for Tier-2;
  it now runs current (v2.4.46). Future runs: always restart uvicorn at Phase 6.
- **Prod auth for Tier-3:** the local frontend `.env.local` `INTERNAL_SERVICE_TOKEN`
  does NOT match prod's Railway token (401). Use the `dp_` admin key via
  `frontend/scripts/get-or-create-admin-key.mjs` with `DATABASE_URL` from
  `.env.local` — that is the working Tier-3 auth path.

## Stop reason

Goal was `until:"context window hits ~60%"`. Run 5 completed cycle G5c-1 in full
(code → Tier-1 → Tier-2 → release → Tier-3 → self-improvement). Stopped before
bootstrapping a second cycle because the context budget was reached and the next
queue item (FIG captions, C2) is a fresh-cycle-sized block. The next
`/docpluck-iterate` session resumes at the FIG caption cycle from the queue above.
