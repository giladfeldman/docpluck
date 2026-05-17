# Handoff — docpluck-iterate run 8 → run 9 (verification-harness foundation done; Phase C begins)

**Authored:** 2026-05-17, end of run 8. **For:** a fresh `/docpluck-iterate` session, **goal `time:5h`**.

Run 8 did **not** run normal fix cycles. The user halted the loop because severe
defects (missing text, misplaced tables, mojibake) were surviving "green"
cycles. Run 8 instead **rebuilt the verification methodology from the ground
up** — the prior loop verified the *library in isolation*, per-cycle/per-target,
against snapshot baselines that could themselves be broken. Run 9 resumes
normal iteration, but **every cycle is now gated by the new harness**.

**Read first:** [`docs/ITERATION_VERIFICATION_LESSONS.md`](ITERATION_VERIFICATION_LESSONS.md)
(why the old methodology failed) and [`scripts/harness/README.md`](../scripts/harness/README.md)
(how the harness works).

---

## State at handoff

- Library version: **v2.4.53** (unchanged this run — run 8 shipped no library code).
- Commits this run: `a513c1e` (docpluck — harness foundation), `32fc65d` (docpluckapp — pin self-doc).
  **Both committed locally, NOT pushed.** Run 9 (or the user) should push.
- Production: **v2.4.53**, current (the `requirements.txt` pin auto-bumps; prod is never stale — see `service/requirements.txt` comment).
- Local FastAPI service: run with `cd ../PDFextractor/service && python -m uvicorn app.main:app --port 6117 --env-file .env --workers 4`. It imports the editable working-tree `docpluck`, so it always reflects HEAD.
- Harness baseline: `scripts/harness/baseline_matrix.json` committed — 540 cells (180 docs × 3 levels), **84 known Tier-D fails** recorded. Regression gate verified live (`0 regressions` on re-run).

## What run 8 built (the foundation)

1. **`scripts/harness/`** — automated extraction-and-inspection harness:
   - `corpus.py` → `corpus_manifest.json` (180 docs: 152 PDF, 25 DOCX, 3 HTML).
   - `extract.py` — drives the **local app** `/analyze` per doc × normalization level, saves every view to `verify_out/` (gitignored).
   - `checks.py` — **Tier-D** deterministic checks (text-loss, table-parity, glyph) → verdict matrix, diffed vs the committed baseline.
   - `inspect.py` + `VERIFIER_PROMPT.md` — **Tier-A** AI-gold deep inspection driver.
2. **Skill integration** — `docpluck-iterate` **Phase 5H** + **rule 19**; `docpluck-qa` **check 7h**; `docpluck-review` **rule 16**. The harness is now the verification gate; `scripts/verify_corpus.py` is demoted to a fast supplementary smoke.
3. **`LEAVE NOTHING BEHIND` directive** — added to `CLAUDE.md` (both repos) + all 5 project skills + memory. *Any* issue seen — pre-existing, known, out-of-scope — is fixed in the same run; the only exits are an explicit user decision or an immediate-next-cycle queue.
4. **`docs/ITERATION_VERIFICATION_LESSONS.md`** — portable cross-project post-mortem (for scimeto / CitationGuard / ESCImate).

## How a cycle runs now (Phase 5H — the new gate)

Every cycle, after the library fix:

1. **Extract** — `python -m scripts.harness.extract --workers 4`. Re-extract the affected docs at all 3 levels AND, for the regression gate, the whole corpus at **`--levels academic`** (~180 extractions; full 3-level is slow — see Gotchas). Run a full 3-level sweep before a release / every ~3 cycles.
2. **Tier-D** — `python -m scripts.harness.checks`. **HARD GATE: 0 regressions (no `pass→fail` cell) and 0 new fails.** A regression on *any* corpus doc — not just the cycle's target — blocks the cycle.
3. **Tier-A** — `python -m scripts.harness.inspect prepare --affected <ids>`, dispatch one verifier agent per `ready` job (`VERIFIER_PROMPT.md`), then `inspect collect`. TEXT-LOSS = 0, HALLUCINATION = 0.
4. After the cycle ships clean: `python -m scripts.harness.checks --update-baseline` to record the new accepted state (the fixed cells flip `fail→pass`).

## Phase C work queue — the 84-fail backlog (run 9's job)

The baseline honestly records 84 Tier-D fails at v2.4.53. Recommended cycle order — highest data-corruption severity first:

| # | Class | Tier-D signal | Notes |
|---|---|---|---|
| 1 | **TABLE structure** | `table_parity` — 15 docs | Worst: corrupts published data. Adelina Tier-A confirmed body-sentence fragments welded into `<table>` header rows, concatenated cells (`444075438440878` = 6 values in one cell), **double-emission** (every table inline block + HTML). `extract_structured.py` / `tables/` / `render.py`. |
| 2 | **HALLUC-HEAD** | (Tier-A) | False headings: `## Funding` is the CRediT role **"Funding acquisition"** split into a heading + orphan `acquisition` — **a gap in the shipped HALLUC-HEAD-1 fix** (`_demote_credit_role_headings` misses *split* role labels). Also `## Evaluation`, `## Findings` (a line-wrapped sentence fragment promoted to a heading). |
| 3 | **text_loss** | `text_loss` — 9 docs | Run Tier-A to separate REAL body-text loss from table/list residue. Candidate real losses: xiao-status-quo `"…the effect was the"` (ends mid-sentence). Most of the 9 are linearized table/stimulus-list regions (Tier-D can't fully tell them apart — Tier-A confirms). |
| 4 | **glyph** | `glyph` — 4 docs | Mathematical-Alphanumeric / U+FFFD / private-use corruption. Note: pdftotext mis-decodes some symbols upstream — recovery may need the layout channel; some are escalation-class. |

These map to the older `TRIAGE_2026-05-14_phase_5d_gold_audit.md` families (TABLE cluster, HALLUC-HEAD-2, COL/GLYPH). **The harness `baseline_matrix.json` is now the authoritative defect inventory** — read it (or run `checks`) to see exact cells; the TRIAGE describes root causes.

Also still queued from run 7 (pre-harness): TBL-CAP (table-caption over-extension into column headers — maier/chen), FIG-3c-2, G5d, G5c-2. Re-confirm these against the harness before working them.

## Gotchas / notes for run 9

- **The local service must be running** (4-worker uvicorn, above) before any harness `extract`. `curl -s localhost:6117/health` must report `docpluck_version` = working-tree `__version__`.
- **Extraction is slow on this machine** — a full 180-doc × 3-level run took ~hours even at `--workers 4`. Per-cycle, gate on `--levels academic` whole-corpus (~25-40 min); do the full 3-level sweep before releases. `extract.py` is idempotent/resumable — unchanged docs are skipped.
- **Tier-D `text_loss` has known false-positive residue** (~9 docs) — mostly linearized table/stimulus-list regions and a few survey-item lists. The check exempts mastheads/PMC-banners/affiliations/running-elements; it cannot perfectly tell a linearized table from prose. **Treat a Tier-D `text_loss` fail as a candidate, not a verdict — Tier-A (AI gold) is authoritative.**
- **AI golds:** Adelina = `10.5334__irsp.571` (in the shared cache, mapped in `gold_keys.json`). **Aiyer is content-filter-blocked** — gold generation fails on it (a known issue with some social-psych PDFs); it is Tier-D-only. As run 9 works papers, generate their golds via `article-finder generate-gold` and add the doc-id→key mapping to `gold_keys.json` (run `inspect discover` / extend manually).
- **Gold-key mapping is sparse** — only Adelina is mapped. Tier-A coverage grows as run 9 generates golds for the papers it touches (the tiered policy: affected + open-fails + rotating slice).
- **Baseline maintenance:** after each clean cycle, `checks --update-baseline`. The 84 fails shrink as Phase C fixes land (`fail→pass`); the gate catches any new `pass→fail`.
- The `baseline_matrix.json` is large (~13k lines — a generated lockfile-style artifact). Diffs are proportional to changed cells. If diffs get noisy, consider slimming it to verdicts-only (the `diff_baseline` only needs verdicts).
- Run 8 did **not** run `/docpluck-qa` (no functional code changed). Run 9 changes library code → its first release MUST go through full `/ship` (qa + review + cleanup) per Phase 7.

## Stop reason (run 8)

Run 8's goal was to rebuild the verification foundation (user directive after halting the loop). Foundation complete: harness built + proven (caught real defects on the Adelina paper that 14 prior cycles missed), corpus extracted, baseline set, skills integrated, both user directives applied, foundation committed. Run 9 begins Phase C — harness-gated defect-fix cycles — at the TABLE structure class.
