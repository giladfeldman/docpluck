# Handoff — docpluck-iterate run 9 (continued) → fresh session

**Authored:** 2026-05-18, after shipping cycle 4 (v2.4.57). **For:** a fresh
`/docpluck-iterate` session that **continues run 9**.

This is a **mid-run handoff** (same as `HANDOFF_2026-05-17_iterate_run_9.md`):
the Tier-D backlog is **not** empty, the run should continue. Standing verdict
is **PARTIAL** until the Tier-D corpus is clean or the budget is spent.

**Goal:** `until:"Tier-D corpus clean"` (user-set this session).

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

## Open queue (the work — pick up here)

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

## Beyond Tier-D — backlog from Phase 5d (NOT Tier-D-visible; the scope question)

Cycle 4's mandatory Phase 5d AI-gold verify of `plos_med_1` confirmed the cmsy10 fix is clean but surfaced **severe pre-existing defects Tier-D's mechanical checks cannot see**:
- **TABLE-builder cluster** — `plos_med_1` Table 2 emits 1 of 11 rows (loses all 6 fibroid-size bins), Table 5 is an empty `<table>` shell (13 rows lost), Tables 3/4 have their bodies SWAPPED under each other's captions, Table 4 drops the `ephedrine` row, Table 3 has a broken cell `0/9 (0.0%`. This is the TRIAGE "TABLE cluster" — **C3 architectural, dedicated session**.
- **Section annotator** — promotes front-matter sidebar labels to `##` headings (`## Methodology` from a CRediT role, `## Funding`, `## Competing interests`, `## Data Availability Statement`); drops the real `## Conclusions` and `## Author summary`. (= TRIAGE HALLUC-HEAD-2.)
- **D4 metadata leak** — author affiliations, corresponding-author email, copyright/funding/competing-interests sidebars, `a1111111111` watermark, page furniture all dumped into the body; every table double-emitted (a garbled inline text dump in Results prose + the structured `### Table N` block).

**SCOPE DECISION FOR THE USER (an AskUserQuestion failed to deliver this session):** the user's stated goal is "Tier-D clean" (≈ cycles 5-6 + the timeouts). The above Tier-A defects are **beyond Tier-D's reach** — the harness `table_parity` check counts headings/`<table>` tags, not rows or cell correctness, so a catastrophically-wrong table still passes Tier-D. The TABLE cluster is C3 and the TRIAGE itself recommends a dedicated session. **Recommend:** finish Tier-D clean (cycles 5-6 + timeouts), then surface these to the user as a dedicated follow-up run. They are queued, documented, and not lost — but should not be crammed mid-run.

## Methodology / gotchas (carry forward)

- **Service restart orphans uvicorn workers.** `--workers 4` spawns a parent + 4 worker processes. Killing only the listening parent (`Get-NetTCPConnection -LocalPort 6117`) leaves the 4 workers ALIVE and still serving on the inherited socket (old library version). Kill ALL of them: find python processes with `spawn_main(parent_pid=<old>)` in their command line and `Stop-Process` each. Verify `/health` shows the NEW version after restart.
- **Never run the harness `extract` and the broad `pytest` concurrently** — CPU contention starves the service → false `extraction` timeouts (this session: `maier` false-timed-out under concurrent load, cleared on a clean re-extract; `xiao-poc-epley` did NOT clear → genuinely slow).
- **Harness `extract` skips on `source_sha1`, not docpluck version** — `--force` is mandatory after a code change.
- The harness Tier-D baseline is **academic-level only** (run-9 practice). `checks --levels academic` consistently.
- AI-gold generation via `article-finder generate-gold` works on a 16-page PDF when it reads in 2-3 page chunks (the first plos_med_1 attempt failed on a 2000px many-image limit; the retry succeeded).

## Run-meta / postflight

`~/.claude/skills/_shared/run-meta/docpluck-iterate.json` — this session populated `bugs_fixed` (cycle 4), `tests_added`, `lessons_appended` (4 total), `phase_failures`. The Phase 12 postflight ran at this session's end (heartbeat printed, signal cards written). Verdict for this session: **PARTIAL** — cycle 4 shipped clean, but the Tier-D corpus has 11 open fails; the run continues.

## Stop reason (this session)

Context budget — a full cycle (cycle 4) was completed end-to-end (DO-FIRST baseline refresh + code + AI-gold + 5 verification phases + cleanup/review sub-skills + release + prod verify + journal). Handed off at the clean post-cycle-4 boundary rather than starting the cycle-5 app fix half-way. The fresh session continues from **cycle 5 (app `preserve_math_glyphs` / DELTA-1)**.
