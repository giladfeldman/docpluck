# Handoff — docpluck-iterate run 9 (continued) → fresh session

**Authored:** 2026-05-18, after shipping cycle 4 (v2.4.57). **For:** a fresh
`/docpluck-iterate` session that **continues run 9**.

This is a **mid-run handoff** (same as `HANDOFF_2026-05-17_iterate_run_9.md`):
the backlog is **not** empty, the run should continue. Standing verdict is
**PARTIAL** until the WHOLE backlog is addressed or the budget is spent.

**Goal (updated 2026-05-18 by user directive):** originally `until:"Tier-D
corpus clean"`. After cycle 4's Phase 5d surfaced severe Tier-A defects beyond
Tier-D's mechanical reach, the user directed: **address ALL issues — the
Tier-D fails AND the full Tier-A / structural backlog — leave nothing behind.**
The run continues until every item in the "Open queue" below is resolved, or
each remaining item is explicitly escalated to the user with analysis. Group B
(Tier-A) is NOT deferred to a separate run. Every issue this run and the
prior run-8/run-9 handoffs have surfaced is enumerated below — nothing is
left as a "someday" footnote.

**Read first:** `HANDOFF_2026-05-17_iterate_run_9.md` (harness design, run-9
cycles 1-3), `scripts/harness/README.md`, `tmp/known-tier-deltas.md`,
`.claude/skills/docpluck-iterate/LEARNINGS.md` (the run-9 cycle-4 journal at
the bottom).

---

## State at handoff

- Library version **v2.4.57** — this session shipped **cycle 4** (commit `ad73397`, tag `v2.4.57`, pushed to `main`).
- **docpluckapp** auto-bump landed: commit `a523ee74 pin: auto-bump docpluck library to v2.4.57`; `verify-railway-deploy.yml` CI **success**. **Prod `/health` = docpluck 2.4.57** (verified).
- **Harness Tier-D baseline is now v2.4.57**, academic-level, committed in `ad73397`. **DO-FIRST #1 done** — the stale run-8 v2.4.53 3-level baseline was replaced by a clean full v2.4.56→v2.4.57 academic extract.
- Local FastAPI service: running at v2.4.57 (background task `bip0vu021`). **Verify (`curl -s localhost:6117/health` → 2.4.57) or restart** before harness work: `cd ../PDFextractor/service && python -m uvicorn app.main:app --port 6117 --env-file .env --workers 4`.
- **Harness Tier-D at v2.4.57: 11 open fails** = 9 `text_loss` + 2 `extraction` (`nat_comms_3`, `xiao-poc-epley`). plos_med_1 `glyph` is now PASS (cycle 4).

## Cycle shipped this session

| Cycle | Ver | Defect (class) | Fix | Result |
|---|---|---|---|---|
| 4 | v2.4.57 | cmsy10 `≥`/`≤` glyphs destroyed to U+FFFD by BOTH pdftotext and pdfplumber (glyph, S0) | new `normalize.py::recover_fffd_comparison_operators` (step S5b) — Rule 1 airtight complement-pairing, Rule 2 doc-consensus | `plos_med_1` glyph fail→pass; 0 regressions; 14 tests; AI-gold confirmed |

Phase 7 took the **FULL path** (`/docpluck-cleanup` PASS + `/docpluck-review` APPROVE) — breaks the 12-cycle lean-path streak: Phase 6c found a pre-existing Tier1≠Tier2 delta, so lean-path item 11 didn't hold.

## DO FIRST (fresh session)

1. **Methodology smell-test** (Phase 0.8) before any code.
2. Verify the local service is at v2.4.57 (or restart it). **`git pull` the local `../PDFextractor` checkout** — it is stale (HEAD pin v2.4.53; remote master is v2.4.57). Cycle 5 edits `PDFextractor/service/app/main.py`, so the local checkout must be current.
3. Pick up at **cycle 5** below.

## Open queue — address ALL of it (user directive 2026-05-18: leave nothing behind)

The run continues until every item in BOTH groups below is resolved, or an item
is explicitly escalated to the user with analysis. **Group A** = the Tier-D
harness fails (the `checks` gate). **Group B** = Tier-A / structural defects the
harness cannot see (it counts `### Table` headings + `<table>` tags, not row /
cell / section correctness). Per the user directive both groups are this run's
queue — Group B is not a future-run deferral. Suggested order: A first (smaller,
unblocks the gate), then B (B1 the table-builder is the largest).

---

### GROUP A — Tier-D harness fails

### Cycle 5 — app `preserve_math_glyphs` bug (DELTA-1) — DESIGNED, ready
- **Root cause:** `PDFextractor/service/app/main.py:786` computes `doc = extract_sections(file_bytes=content)` with the default `preserve_math_glyphs=False`, then reuses it as `_sectioned=doc` in the `render_pdf_to_markdown(...)` call (lines 843-848). `render_pdf_to_markdown` normally calls `extract_sections(..., preserve_math_glyphs=True)` itself; the `_sectioned=` arg makes it skip that and consume the caller's document verbatim. Result: the app's `/analyze` rendered view transliterates `≥`→`>=`, `χ`→`chi2`, `β`→`beta` — the library `render_pdf_to_markdown` itself is correct. Full writeup: `tmp/known-tier-deltas.md` Delta 3.
- **Fix:** `main.py:786` → `extract_sections(file_bytes=content, preserve_math_glyphs=True)`. The `sections` view is unaffected (section structure does not depend on glyph transliteration; preserving glyphs in section text is itself correct).
- **This is an APP change** (`docpluckapp` repo) — no docpluck library version bump. Restart the local service, re-extract via the harness, verify the rendered view now preserves `≥`/`χ`. Use `/docpluck-deploy` (app-code-touching) or the app's own flow.
- **Interaction:** DELTA-1 is also the root cause of several Tier-D `text_loss` false-positives — `checks.py::_fingerprint` tokenizes raw `χ2` (no token) and rendered `chi2` (`chi` token) inconsistently, breaking the 8-word window match. After cycle 5, **re-run `python -m scripts.harness.checks`** and see how many of the 9 `text_loss` fails resolve.

### Cycle 6 — harness `_fingerprint` glyph-consistency + adjudicate the residual `text_loss`
- After cycle 5, the glyph-transliteration `text_loss` false-positives should clear. The RESIDUAL fails are genuine linearized-table/stimulus regions — `li-feldman` gambling problems, `mayiwar` `bbbggg`/`gbbgbg` birth-sequences, `korbmacher` difficulty-rating note (see `HANDOFF_2026-05-17_iterate_run_9.md` cycle-5 section + the matrix `missing_samples`).
- **Defense-in-depth:** make `checks.py::_fingerprint` glyph-representation-consistent (transliterate Greek→ASCII-name on BOTH raw and target before fingerprinting) so the check is robust even if a future doc has raw/rendered glyph divergence. This is a **harness change** — no library version bump, no re-extract, just re-run `checks`.
- **CAUTION (carried from run-9 handoff):** do not just loosen the check. Generate AI golds for the residual `text_loss` docs (`article-finder generate-gold`) and adjudicate REAL loss vs check-artifact before/alongside the `_fingerprint` fix.

### Extraction timeouts — `nat_comms_3` + `xiao-poc-epley` (environmental)
- Both time out at >900s in the harness `extract` (academic level), even re-extracted ALONE with nothing else running — so NOT CPU contention; genuine. The slow layer is Camelot table extraction. The docpluck library is byte-identical to v2.4.53 here; provably not a code regression. Both are baselined as `extraction=fail` at v2.4.57.
- **Fix path:** restart the service fresh, clear Camelot temp artifacts (`%TEMP%`), re-extract each alone. If still timing out → profile Camelot → likely needs a per-doc extraction-time cap or a Camelot page-limit (an **architecture decision** — surface to the user).

---

### GROUP B — Tier-A / structural defects (firm cycles — user directive: do NOT defer)

Surfaced by cycle 4's Phase 5d AI-gold verify of `plos_med_1`, the run-8/run-9
handoff Tier-A backlog, and `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md`.
Tier-D's `table_parity` counts `### Table` headings + `<table>` tags only — a
catastrophically-wrong table still passes Tier-D — so these need AI-gold (Tier-A)
verification. Per the 2026-05-18 user directive each is a firm queued cycle of
THIS run; the run's standing verdict stays PARTIAL until all are resolved or
escalated. Verify every Group-B fix against the shared AI gold (article-finder).

**B1 — TABLE-builder cluster (S0/S1, C3 — the single largest blocker).**
- `plos_med_1`: Table 2 emits 1 of 11 rows (loses all 6 fibroid-size bins);
  Table 5 is an empty `<table>` shell (13 SAE rows lost); Tables 3/4 have their
  bodies SWAPPED under each other's captions; Table 4 drops the `ephedrine`
  row; Table 3 has a broken cell `0/9 (0.0%` (missing `)`).
- Corpus-wide (TRIAGE "TABLE structure destruction", ~11 papers — efendic,
  xiao, jdm15/16, chen, maier, ip_feldman, ar_apa_011): grid lost →
  caption-bleed, flat number-dump, empty `<table>` shells, two tables merged,
  rows dropped, numeric cell SWAP (xiao Table 6 `4.91` vs gold `4.70`).
- Layer: `docpluck/tables/`, `docpluck/extract_structured.py`, `render.py`
  table splice. Needs a render/structured coordination design — split into
  sub-cycles (TRIAGE G3/G4: G4b table-caption walk shipped v2.4.32; G4a
  body-stream cell-dump strip still open). This is the biggest item — budget
  several cycles.

**B2 — HALLUC-HEAD-2 / section-annotator over-promotion (S1, C2-C3).**
- `plos_med_1`: `## Methodology` (a CRediT role label), `## Funding`,
  `## Competing interests`, `## Data Availability Statement` promoted from
  front-matter sidebars; the real `## Conclusions` and `## Author summary`
  dropped. The run-9 HALLUC-HEAD-2: `## Funding` = CRediT role "Funding
  acquisition" split across heading + orphan word (gap in v2.4.53's
  `_demote_credit_role_headings`); plus open-ended `## Conclusion`/
  `## Evaluation`/`## Findings` mis-promotions.
- Includes **G5d** — named (unnumbered) subsection headings demoted to body
  text (~7 papers: ar_apa_011 Participants/Overview, efendic, chandrashekar,
  ip_feldman). Layer: `docpluck/sections/`. Dedicated partitioner session.

**B3 — D4 metadata leak (S2, C2).**
- `plos_med_1` + corpus: author affiliations, corresponding-author email,
  copyright / funding / competing-interests / abbreviations sidebars,
  `a1111111111`-style watermark strips, `N / M` page furniture and running
  headers leaked into the body. Plus TRIAGE D4 residuals (`doi:` footer line,
  plural `E-mail addresses:`, `Received…Accepted…` history line).
- Also: every table is DOUBLE-EMITTED — a garbled column-interleaved text dump
  inline in Results prose AND the structured `### Table N` block.
- Layer: `normalize.py` W0/P0/P1 strips + `render.py` body-stream suppression.

**B4 — caption residuals (S2, C2).**
- TBL-CAP: table-caption over-extension into column-header text (maier Tbl
  5/9/10/11, chen Tbl 3/5/6/7/9/13/15). Layer:
  `extract_structured.py::_trim_table_caption_at_cell_region`.
- FIG-3c-2: body-exceeds-block figure-caption double-emission (~7 figures) —
  needs the block caption completed before the de-dup is safe.

**B5 — G5c-2 partitioner split-heading rejoin (S1, C3).**
- pdftotext splits `N.N. Title` into `N.N.`⏎`Title`; the partitioner consumes
  the title word and strands the bare number (jdm_m.2022.2: 5 cases). Layer:
  `docpluck/sections/core.py` — recognise `N.N.\n\n<CanonicalKeyword>` as one
  numbered heading. Dedicated partitioner session (pairs with B2).

**B6 — COL column-interleave (S0, C3-C4 — escalation-class).**
- `test_request_09` is the one pre-existing broad-pytest fail (red since run 4).
  pdftotext reading-order scrambles body sentences across non-adjacent lines
  (chan_feldman Measures, chandrashekar). Layer: text-channel reading order.
  Per CLAUDE.md, study pdfplumber's column algorithm and re-implement it as a
  conditional fallback — do NOT swap the extraction tool. If it cannot land in
  a cycle, escalate explicitly to the user with the analysis; never silently
  leave `test_request_09` red.

**B7 — GLYPH deleted-minus residuals (S0, escalation-class).**
- A U+2212 minus DELETED entirely by pdftotext (ar_apa_011 `b = .022` for
  `−.022`, sign-inverting); efendic `Mchange = 2X.XX` with only an SE and no CI
  to pair. No text-channel signal survives — recovery needs the layout
  channel's per-char glyph identity. Escalation-class: attempt a
  layout-channel recovery; if unrecoverable, surface the analysis to the user.

**Carry-forward note:** the run-9 handoff also listed FIG residuals already
shipped (FIG-1..FIG-4, G5c-1, HALLUC-HEAD-1) — those are DONE, not re-queued.
Re-confirm each Group-B item at HEAD before coding (defects can be incidentally
fixed; cost estimates drift — see LEARNINGS).

## Methodology / gotchas (carry forward)

- **Service restart orphans uvicorn workers.** `--workers 4` spawns a parent + 4 worker processes. Killing only the listening parent (`Get-NetTCPConnection -LocalPort 6117`) leaves the 4 workers ALIVE and still serving on the inherited socket (old library version). Kill ALL of them: find python processes with `spawn_main(parent_pid=<old>)` in their command line and `Stop-Process` each. Verify `/health` shows the NEW version after restart.
- **Never run the harness `extract` and the broad `pytest` concurrently** — CPU contention starves the service → false `extraction` timeouts (this session: `maier` false-timed-out under concurrent load, cleared on a clean re-extract; `xiao-poc-epley` did NOT clear → genuinely slow).
- **Harness `extract` skips on `source_sha1`, not docpluck version** — `--force` is mandatory after a code change.
- The harness Tier-D baseline is **academic-level only** (run-9 practice). `checks --levels academic` consistently.
- AI-gold generation via `article-finder generate-gold` works on a 16-page PDF when it reads in 2-3 page chunks (the first plos_med_1 attempt failed on a 2000px many-image limit; the retry succeeded).

## Run-meta / postflight

`~/.claude/skills/_shared/run-meta/docpluck-iterate.json` — this session populated `bugs_fixed` (cycle 4), `tests_added`, `lessons_appended` (4 total), `phase_failures`. The Phase 12 postflight ran at this session's end (heartbeat printed, 2 signal cards written). Verdict for this session: **PARTIAL** — cycle 4 shipped clean, but the Open queue (Group A Tier-D fails + Group B Tier-A backlog) is non-empty; the run continues until the entire queue is resolved or each remaining item is explicitly escalated.

## Stop reason (this session)

Context budget — a full cycle (cycle 4) was completed end-to-end (DO-FIRST baseline refresh + code + AI-gold + 5 verification phases + cleanup/review sub-skills + release + prod verify + journal). Handed off at the clean post-cycle-4 boundary rather than starting the cycle-5 app fix half-way. The fresh session continues from **cycle 5 (app `preserve_math_glyphs` / DELTA-1)**.
