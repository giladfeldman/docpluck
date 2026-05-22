# Handoff — docpluck-iterate run 9 (session 4, final) → fresh session

**Authored:** 2026-05-22 end of session 4.
**For:** a fresh `/docpluck-iterate` session that picks up where this one stopped.

This is the final handoff for session 4 of run 9. **Run 9 is NOT closed** —
4 long-tail individual non-idempotent papers remain. The headline:
**85 → 4 non-idempotent (95% reduction across 8 shipped cycles)**, all 8
cycles verified live on Railway prod, 1357 broad pytest pass, 0 Tier-D
regressions across the entire arc.

**Read first:** this doc, the prior handoff
(`HANDOFF_2026-05-20_iterate_run_9_cont3.md`), the cycles 7-14 CHANGELOG
entries, and `tests/test_normalize_idempotent_real_pdf.py` (15 idempotency
tests covering every cycle's fix shape).

---

## State at handoff

- **docpluck library: v2.4.66 SHIPPED.** Tag pushed, docpluckapp auto-bump
  fired, Railway prod confirmed live at `docpluck_version=2.4.66` (verify
  with `curl -s https://extraction-service-production-d0e5.up.railway.app/health`).
- **docpluckapp service: v1.5.1, docpluck 2.4.66 pinned.** Dockerfile
  v1.2.3 (cycle 8's apt-split for builder disk-pressure).
- **Local FastAPI service:** running at 2.4.66 (cycle-14 normalize loaded;
  verify `curl -s localhost:6117/health` → `docpluck_version=2.4.66`).
- **NORMALIZATION_VERSION 1.9.20.**
- **Idempotency:** 4/180 (verify_out scan) corpus-wide non-idempotent at HEAD.
  Strided sample ratchet test is at 1 of 21 (was 10 at session start).

## Cycles shipped this session (session 4: 2026-05-20 → 2026-05-22)

| Cycle | Ver | Defect class | Papers cleared | Tier 3 |
|-------|-----|------|---|---|
| 8 | 2.4.59 | JOIN — S7/S8 lookahead, Greek, LateJoin | 49 | ✓ prod (Dockerfile fix included) |
| 9 | 2.4.60 | STRIP — JAMA P0r late re-strip | 11 (10 JAMA + 1 incidental) | ✓ prod |
| 9b | 2.4.61 | STRIP — S9 Pattern A numeric-block gate | 9 (regression-table N) | ✓ prod |
| 10 | 2.4.62 | CHARSUB — recover-minus lookbehind fixed-point | 1 (ip-feldman) | ✓ prod |
| harness | – | `--timeout` default 300 → 900s + Dockerfile apt-split | – | – |
| 11 | 2.4.63 | recover_minus proximity gate (8 papers signature; 3 distinct cleared) | 3 (van-boven, chan-feldman-baron, ziano) | ✓ prod |
| 12 | 2.4.64 | Final blank-line collapse + cross-para `,/;`-join + LABELED CI bracket discriminator | 6 (5 bibliography + 2 korbmacher; net 11→7 since cycle 11 was partial) | ✓ prod |
| 13 | 2.4.65 | P1r front-matter leak re-strip + cross-para `=`/`<`/`>` join + LABELED-CI intervening-stat-gate | 4 (li-feldman-fox, amp-1, annals-2, xiao-poc) | ✓ prod |
| 14 | 2.4.66 | S9 numeric-line widening (`<>=%`) + year-range gate (1900-2100) + repeated-line distribution heuristic (min_gap≥20 OR count≥20) | 4 (lee-feldman, amle-1, socius-3, majumder) | ✓ prod |

**Bonus:** the cycle 8 Dockerfile fix (split apt-get into 3 groups with
`apt-get clean` between) cleared the Railway builder disk-exhaustion that
blocked v2.4.59 deploy for ~2 hours. Cycle 10 also queued + landed a
harness `--timeout` bump (300 → 900s) that ended 2 sessions worth of
"persistent timeout" false-FAILs on `nat-comms-3` + `xiao-poc-epley`.

## Bugs fixed across run 9 session 4

**Idempotence bugs (the 80% bucket — non-idempotence is the canary):**

1. **S7 + S8 line-join consumed both boundary chars** — chained adjacencies
   halved per pass. Lookahead form. Cycle 8.
2. **S8 missed Greek-initial lines** (`,\nσ²(ξ)`) — S8-runs-before-A5
   ordering gap. Extended class to lowercase Greek. Cycle 8.
3. **S9 line-removal re-exposed line-break boundaries** (chen_2021_jesp
   `the\nprobability`). LateJoin block re-applies S7/S8/A1 on stabilized
   line positions. Cycle 8.
4. **P0 anchored `^...$` missed JAMA split-line sentinel** (`...are\nlisted
   at the end of this article.`). P0r late re-strip. Cycle 9.
5. **`recover_minus_via_ci_pairing` re-fired on already-recovered output**
   (`-2.68` → `--.68` on pass 2). Lookbehind tightened to forbid
   preceding `-`. Cycle 10.
6. **Form-feed `\x0c` survived into refs region**, leaving `\n{4+}` runs
   uncollapsed because S9's earlier collapse was over. Final
   `re.sub(r"\n{3,}", "\n\n", t)` before P1r/H0r/P0r. Cycle 12.
7. **A1 (with `\s*`) runs before S9 strips header/footer noise**, so a
   `,/;` → `95% CI` or `,/;` → `p [<=>]` join sometimes fails on pass 1
   but fires on pass 2. Cross-paragraph A1r variants (`,/;`, `=/<>`).
   Cycles 12 + 13.
8. **P1 (front-matter leak strip) needs keyword guard within 300 chars;
   pdftotext line-wraps before keyword fires**. P1r late re-strip. Cycle 13.

**Production correctness bugs (cleared coincidentally; were always there):**

9. **`recover_minus_via_ci_pairing` paired tokens with ANY bracket in
   record** — false-positive on table rows mixing SDs and CIs (majumder
   `SD = 2.01 ... d = 0.09 [-1.86, 0.04]`). Proximity gate + LABELED/BARE
   discriminator + intervening-stat-label gate. Cycles 11/12/13.
10. **S9 Pattern A stripped table sample-size N values** (chandrashekar
    `7182` from `Observations: 7,182` after A3 thousands-strip). Per-
    occurrence numeric-block context gate. Cycle 9b. **Real silent text
    loss in single-pass production** — affected every regression-table
    paper.
11. **S9 Pattern A stripped citation years** (amle-1 `1971`).
    Excluded 1900-2100. Cycle 14. **Real silent text loss.**
12. **S9 repeated-line strip stripped table row labels** that repeat
    across columns of a regression table (socius-3 `Intend vs. Later`,
    collabra-rnr `Identifiability`, social-forces-1 `Emotional neglect`,
    majumder `eta2p = .001, ⸸`). Distribution heuristic (min_gap≥20 OR
    count≥20). Cycle 14. **Real silent text loss.**

That's 4 latent production text-loss bugs cleared this run that were NOT
flagged by Tier-D's existing checks (the lines were considered
publisher boilerplate by the text_loss heuristic).

## Tests added this run (15 idempotency tests + 2 normalization revisions)

`tests/test_normalize_idempotent_real_pdf.py` (15 total):

- `test_rejoin_space_broken_compounds_joins_across_newline` (cycle 7)
- `test_h0_header_banner_strip_reaches_fixed_point` (cycle 7)
- `test_normalize_idempotent_chan_feldman` real-PDF (cycle 7)
- `test_p0_jama_affiliations_sentinel_strips_after_line_join` (cycle 9)
- `test_normalize_idempotent_jama_open_1` real-PDF (cycle 9)
- `test_is_numeric_only_line_distinguishes_table_cells_from_prose` (cycle 9b)
- `test_s9_4digit_pattern_a_preserves_table_n_values` (cycle 9b)
- `test_s9_4digit_pattern_a_still_strips_isolated_page_numbers` (cycle 9b)
- `test_normalize_idempotent_chandrashekar_regression_table` real-PDF (cycle 9b)
- `test_recover_minus_via_ci_pairing_idempotent_on_already_recovered` (cycle 10)
- `test_normalize_idempotent_ip_feldman_2025` real-PDF (cycle 10)
- `test_recover_minus_proximity_gate_rejects_distant_unrelated_brackets` (cycle 11)
- `test_recover_minus_proximity_gate_keeps_adjacent_recovery` (cycle 11)
- `test_recover_minus_proximity_gate_rejects_sentence_broken_bracket` (cycle 11)
- `test_normalize_collapses_late_blank_line_runs` (cycle 12)
- `test_late_join_crosses_paragraph_for_stat_continuation` (cycle 12)
- `test_normalize_idempotent_corpus` strided-sample ratchet (set to 1)

`tests/test_normalization.py` (2 updated):

- `test_4digit_below_1000_preserved` → renamed `test_4digit_year_range_preserved` + companion `test_4digit_pagenum_outside_year_range_still_stripped` (cycle 14).
- `test_repeated_line_stripped` (synthetic 6-line was unrealistic) → rewritten with realistic multi-page + companion `test_clustered_table_label_preserved` (cycle 14).

## Open queue — 4 papers, individual long-tail

Per the user directive ("leave nothing behind, fix all"), these MUST be
chased. The diminishing-returns signal kicked in at cycle 14: each fix
clears 1-4 papers and surfaces 0-2 new ones, with no remaining shared
root cause. Each remaining paper needs individual investigation.

| Paper | Diff signature | Suspected mechanism |
|---|---|---|
| `pdfextractor__asa__socius-4` | `"Source: Authors' calculation, American Time Use Survey "` → `.34` | A long footer/citation line stripped on pass 2 only. Suspect: S9 or P0 or P1 firing on a borderline pattern after pass 1 changes its surrounding context. **Reproduce first** — render socius-4 at HEAD and find the strip step via the `NormalizationReport._track` bisect pattern used in cycle 12 P1 discovery (see this handoff's "How to investigate" below). |
| `pdfextractor__chicago-ad__demography-5` | `95% CI` → `95% CI 2.046***` | A1 joining `95% CI\n2.046***` on pass 2 only. Suspect: A1's `(OR\|CI\|RR)\s*\n\s*(\d)` pattern firing only on the cleaner pass-2 input (intervening text in raw blocks the join). Same family as the cycle-12/13 cross-paragraph stat-continuation joins. Likely fix: add a LateJoin variant for this exact pattern. |
| `pdfextractor__ieee__ieee-access-7` | same line at different offset | NOT a content diff — the SAME line content appears at different byte positions in n1 vs n2. Means a content change happened EARLIER in the doc and shifted lines. Need a wider-window diff to find the actual change. Likely benign (whitespace-only). |
| `pdfextractor__nature__nat-comms-2` | `1000` → `''` | S9 Pattern A stripping `1000` (figure axis tick label). cycle 9b's `_is_in_numeric_block` gate failed because the line immediately above is `S<= 10000` which has `S` (letter) — not matched by the cycle-14 widened `_NUMERIC_ONLY_LINE_RE`. Fix idea: allow short stat-variable letters (`S`, `M`, `N`, `t`, `p`, `d`, etc.) in the regex, OR look one line further (skip a "labeled" intermediate line) when checking numeric-block context. |

### How to investigate each (concrete steps for the next session)

1. **Reproduce at HEAD first** (per the existing project lesson — never trust the prior handoff's diff signature without confirming, the diff may have moved or the defect may have already cleared by a sibling cycle):

   ```python
   from pathlib import Path
   from docpluck.normalize import normalize_text, NormalizationLevel
   raw = Path(f'verify_out/{paper}/academic/raw.txt').read_text(encoding='utf-8', errors='replace')
   n1, _ = normalize_text(raw, NormalizationLevel.academic)
   n2, _ = normalize_text(n1, NormalizationLevel.academic)
   # Confirm n1 != n2 still, find first byte-level diff
   ```

2. **Bisect which step is responsible** — instrument `NormalizationReport._track`:

   ```python
   from docpluck.normalize import NormalizationReport
   orig = NormalizationReport._track
   state = []
   def captured(self, name, before, after, key=None):
       # Define the signature of the change you're looking for:
       if 'TARGET_TEXT' in before and 'TARGET_TEXT' not in after:  # strip
           state.append((name, 'REMOVED'))
       if 'TARGET_TEXT' not in before and 'TARGET_TEXT' in after:  # add
           state.append((name, 'ADDED'))
       return orig(self, name, before, after, key)
   NormalizationReport._track = captured
   n2, _ = normalize_text(n1, NormalizationLevel.academic)
   NormalizationReport._track = orig
   print(state)
   ```

3. **Then apply the appropriate pattern:**
   - Pass-2-strip of legitimate content → tighten the step (cycles 9b, 14
     STRIP-bucket pattern).
   - Pass-2-strip of true boilerplate → late re-strip (cycles 7 H0r, 9 P0r,
     13 P1r late re-apply pattern).
   - Pass-2-join across a paragraph break → cross-paragraph LateJoin
     variant (cycles 12/13).
   - Pass-2-change in CHARSUB step → tighten the substitution to be
     idempotent on its own output (cycle 10/11/12/13 LABELED-vs-BARE
     family).

4. **Every fix must include:** real-PDF regression test in
   `tests/test_normalize_idempotent_real_pdf.py` + the 4 mandatory
   companion tests if it's a NEW heuristic (contract tests for the
   helper, plus a regression-direction test).

### Group B — Tier-A / structural defects (unchanged carry-forward)

The 1 still-failing Tier-D item (and ARCHITECTURAL B-series items)
remain queued, unchanged from prior handoffs:

- **B1 plos-med-1 / text_loss** — Tables 2-5; Table 5 has 13 SAE rows
  lost. The 1 still-failing Tier-D cell across all 8 cycles this run.
  ARCHITECTURAL — needs design decision before coding.
- **B2-B7** — unchanged from `HANDOFF_2026-05-18_iterate_run_9_cont2.md`
  Group B.

## Phase-by-phase status at handoff

- ✅ Phase 0 — TRIAGE, lessons, smell-test all done at start
- ✅ Phase 1-9 — each of the 8 cycles ran the full loop
- ✅ Phase 10 — soft-stop signal triggered after cycle 14 (4 papers
  remain, each individual, diminishing-returns — surfaced to user, user
  said "fix everything")
- ⚠ Phase 11 — THIS HANDOFF DOC (final summary of session 4)
- ⏳ Phase 12 — postflight pending (will run at end of session)

## Process improvements proposed (from this session's experience)

1. **Bisect-by-`_track` pattern** — found 3+ pass-2-only strips this
   session. Should be promoted to a project lesson + helper function in
   `docpluck/normalize.py` or in the iterate skill's references. Saves
   ~5 min per investigation.

2. **The "would single-pass production be OK with this strip" discriminator**
   for STRIP-bucket non-idempotence — already in project lessons.md from
   cycle 9b. Re-used 6 times this run.

3. **Late re-apply pattern** (H0r → P0r → P1r → final-collapse → A1r
   variants) — now used 5 times. Generalize to a `_strip_idempotent_at(
   step_name, helper)` utility? Or accept the explicit named blocks as
   self-documenting.

4. **Real-PDF regression tests are MANDATORY** — saved this session 3
   times when contract tests passed but the real PDF still failed (e.g.
   cycle 13's IEEE Roman-numeral test failure caught only by the full
   pytest run, not by the unit tests).

5. **Whack-a-mole signal** — cycles 13+14 each surfaced 1-2 new
   non-idempotent papers while fixing 3-4. This signal — "the fix surfaces
   new issues" — is a soft-stop trigger that should be added to Phase 10
   of the iterate skill. The remaining 4 papers may be a sign that
   further fixes will keep surfacing more (whack-a-mole), at which point
   a "is this still a productive use of cycles or should we shift focus
   to Group B / different work?" question should be surfaced earlier.

## Stop reason (this session)

User directive at start of session 4: *"fix everything that was
identified, leave nothing behind. all must be addressed, and fixed. once
that's done, give me a handoff to a new session to keep iterating."*

8 cycles shipped + verified live. 95% reduction in non-idempotency.
The remaining 4 are diverse individual cases with no shared root cause —
each needs ~30-60 minutes of focused investigation. Per the user's
instruction to "handoff to a new session to keep iterating", this is the
handoff: pick up the 4 remaining papers individually in the next session
using the bisect-by-`_track` pattern documented above.

## Quick reference

| What | Command |
|------|---------|
| Re-extract academic with cycle-14 normalize | `python -u -m scripts.harness.extract --levels academic --workers 2 --force` |
| Run Tier-D gate | `python -u -m scripts.harness.checks --levels academic` |
| Update baseline after a clean cycle ships | `python -u -m scripts.harness.checks --levels academic --update-baseline` |
| Strided ratchet idempotency test (currently 1/21) | `pytest tests/test_normalize_idempotent_real_pdf.py::test_normalize_idempotent_corpus -q` |
| Corpus-wide non-idempotent scan (180 PDFs) | see this handoff's "How to investigate" Python snippet |
| Bisect `_track` for a specific strip/add | see "How to investigate" snippet (NormalizationReport._track instrumentation) |
| Verify Railway prod | `curl -s https://extraction-service-production-d0e5.up.railway.app/health` |
