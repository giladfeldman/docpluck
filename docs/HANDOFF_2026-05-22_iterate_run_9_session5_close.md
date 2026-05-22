# Handoff — docpluck-iterate run 9 (session 5, close) → run 9 CLOSED

**Authored:** 2026-05-22, end of session 5.
**For:** archival. Run 9 is now CLOSED — the corpus is fully idempotent.

This session executed the punch-list from
`HANDOFF_2026-05-22_iterate_run_9_session4_final.md` — the 4 long-tail
individual non-idempotent papers (socius-4, demography-5, ieee-access-7,
nat-comms-2). All 4 cleared in **one bundled cycle** (cycle 15) since
each had a distinct mechanism and the structural fixes were independent.
A 5th pre-existing regression (`test_bibliography_splits_into_45_consecutive`
on Li&Feldman RSOS) was found while running broad pytest and fixed in
the same commit per the **LEAVE NOTHING BEHIND** directive.

---

## State at handoff (run 9 closed)

- **docpluck library: v2.4.68 SHIPPED + LIVE.** Tag pushed; auto-bump
  bot fired (workflow run `26287763515`, 11s success); Railway prod
  confirmed at `docpluck_version=2.4.68`.
- **NORMALIZATION_VERSION 1.9.20 → 1.9.21.**
- **Idempotency: 0/180 (was 4/180) non-idempotent corpus-wide.**
  Strided ratchet test moved from `1/21` → `0/21` (ratchet constant
  lowered from `2` → `0`).
- **Broad pytest: 1363 passed, 27 skipped, 1 xfailed.** No regressions.
- **Run 9 arc: 85 → 0 non-idempotent across 9 shipped cycles** (cycle 7
  baselined; cycles 8-15 each cleared a class).

## Cycle 15 — five structural fixes in one commit

| # | Defect class | Fix | Papers cleared |
|---|---|---|---|
| 1 | JOIN — cross-paragraph CI/OR/RR/HR → digit, A1 fires only on pass 2 after S9 strips intervening header noise | Cross-paragraph A1r variant in LateJoin block with STAT-VALUE lookahead (excludes bibliography `\d+\.\s+[A-Z]` form) | demography-5 (Mortality HR + OR tables) |
| 2 | STRIP — S9 stripping figure-axis tick label `1000` because labeled neighbor `S<= 10000` not seen as numeric | New `_LABELED_NUMERIC_LINE_RE` helper; `_is_in_numeric_block` accepts labeled-numeric neighbors | nat-comms-2 |
| 3 | STRIP — S9 false-stripping table source-attribution caption `(2003-2023)` × 13 as running-header | S9 repeated-line caption guard: skip lines with parenthesized year/year-range OR ≥6 spaces ending in `.` | socius-4 (real silent caption loss in production) |
| 4 | CHARSUB — A5 transliteration `σ → sigma` orphans U+0302 onto trailing `a`; pass-2 NFC composes to `â` | Final `unicodedata.normalize("NFC", t)` pass at end of `normalize_text` | ieee-access-7 |
| 5 | (pre-existing) R3 continuation-join smashed 2-column bibliography numbers (`1.\n2.\n...\n16.`) into one header line | `_pair_two_column_bibliography` R3 pre-pass | Li&Feldman 2025 RSOS (Royal Society Open Science 2-column form) |

Bugs 3 + 5 were latent production text-loss / structure-loss bugs that
the cycle-14-and-earlier verification missed. Bug 5's regression test
was skipped by `requires_fixture` in CI without the Dropbox PDF; the
session-5 broad-pytest sweep with the fixture present surfaced it.

## Tests added (8 new, 1 ratchet)

- `test_late_join_crosses_paragraph_for_ci_or_rr_hr` (cycle 15, synthetic)
- `test_labeled_numeric_line_protects_figure_axis_value` (cycle 15, synthetic)
- `test_s9_preserves_caption_with_year_range` (cycle 15, synthetic)
- `test_final_nfc_pass_composes_orphan_combining_after_a5` (cycle 15, synthetic)
- `test_normalize_idempotent_demography_5_real_pdf` (cycle 15, real PDF)
- `test_normalize_idempotent_socius_4_real_pdf` (cycle 15, real PDF)
- `test_normalize_idempotent_ieee_access_7_real_pdf` (cycle 15, real PDF)
- `test_normalize_idempotent_nat_comms_2_real_pdf` (cycle 15, real PDF)
- `_IDEMPOTENCY_RATCHET: 2 → 0` (the strided-sample ratchet is now zero)

## Open queue at run-9 close

**Run 9 idempotency front: EMPTY.** All 85 → 0.

**Group B — Tier-A / structural defects (carried forward, unchanged):**

- **B1 plos-med-1 / text_loss** — Tables 2-5; Table 5 has 13 SAE rows
  lost. The 1 still-failing Tier-D cell. ARCHITECTURAL — needs design
  decision before coding. Carried forward to a future run.
- **B2-B7** — unchanged from `HANDOFF_2026-05-18_iterate_run_9_cont2.md`.

**Cross-cutting backlog (per the project todo.md):**

- Phase C / Phase D portfolio-review recs (Vibe top-level).
- 3 advisory recs explicitly held back.
- Postflight-watchdog cleanup items.

These are NOT idempotency items; they belong to other workstreams.

## Process improvements applied this run

1. **Bisect-by-`_track` was the workhorse** — used 4 times this session
   (one per paper), cost ~2 min each, identified the responsible
   normalize step every time. The handoff's "How to investigate" snippet
   was perfect. The pattern is well-documented in cycle-12 LESSONS;
   already a project lesson — no further action.

2. **One bundled cycle for N distinct mechanisms** — when each defect's
   fix touches a different code path in the same file (no shared state,
   no overlapping diff), bundling is correct and FASTER than N separate
   cycles. The discipline rule "one class of defect per cycle" exists to
   prevent un-revertible co-fixes; here each fix CAN be reverted
   independently (each is its own contiguous block). The test additions
   give us per-fix regression protection. Applied directly per cycle-14
   precedent (which packaged 3 fixes).

3. **Broad pytest as a regression detector for skipped-in-CI tests** —
   `requires_fixture`-gated tests get skipped in CI without the
   fixture PDF, masking regressions for cycles. When the fixture IS
   present locally, the broad pytest run catches them. Run broad pytest
   at the end of each cycle (not just unit subsets) to surface these.
   The Phase 5b broad pytest step in the iterate skill already calls
   for this; the discipline here is to actually GATE on its result, not
   declare the cycle clean before it returns.

## Stop reason

User directive at session start: *"implement all in handoff ..."* — the
handoff was `HANDOFF_2026-05-22_iterate_run_9_session4_final.md`, which
listed the 4 long-tail papers + the standing "LEAVE NOTHING BEHIND"
binding. All 4 cleared + 1 pre-existing regression also fixed. Corpus
is fully idempotent. Run 9 closes.

## Quick reference

| What | Command |
|------|---------|
| Verify Railway prod at v2.4.68 | `curl -s https://extraction-service-production-d0e5.up.railway.app/health` |
| Re-extract academic with cycle-15 normalize | `python -u -m scripts.harness.extract --levels academic --workers 2 --force` |
| Run Tier-D gate | `python -u -m scripts.harness.checks --levels academic` |
| Strided ratchet idempotency test (now 0/21) | `pytest tests/test_normalize_idempotent_real_pdf.py::test_normalize_idempotent_corpus -q` |
| Corpus-wide non-idempotent scan (180 PDFs) | see HANDOFF session-4 "How to investigate" Python snippet |
