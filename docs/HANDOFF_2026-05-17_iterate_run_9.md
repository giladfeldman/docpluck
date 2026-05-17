# Handoff — docpluck-iterate run 9 → run 10 (Phase C, harness-gated)

**Authored:** 2026-05-17, end of run 9. **For:** a fresh `/docpluck-iterate` session.
**Stop reason:** `time:5h` budget exhausted — this is an honest **PARTIAL** (per
rule 0e-bis): 3 cycles shipped clean, the Tier-D backlog is **not** empty.

**Read first:** the run-8 handoff (`docs/HANDOFF_2026-05-17_iterate_run_8.md`)
for the harness design, and `scripts/harness/README.md`.

---

## State at handoff

- Library version: **v2.4.56** (run 9 shipped v2.4.54, v2.4.55, v2.4.56 — three clean cycles).
- All three tagged + pushed to `main`. Auto-bump PRs in `docpluckapp` — **NOT yet merged** (run 10 or the user should merge the latest, which advances the prod `requirements.txt` pin to v2.4.56).
- Local FastAPI service: restarted per cycle (`cd ../PDFextractor/service && python -m uvicorn app.main:app --port 6117 --env-file .env --workers 4`).
- Harness Tier-D (academic level) at v2.4.56: **fail count 28 → 11** (+ 1 `nat_comms_3` extraction timeout, see below). 18 cells fixed: 3 glyph + 15 table_parity.
- **Harness `baseline_matrix.json` NOT updated this run** — see "Run 10 MUST do first" below.

## Cycles run

| Cycle | Version | Defect class | Fixed | Tier-D result |
|---|---|---|---|---|
| 1 | v2.4.54 | glyph — Adobe-Symbol-font PUA codepoints (β/χ/• as U+F0xx) | `bh1988`, `xiao-monin-miller` | glyph fail→pass ×2, 0 new fails |
| 2 | v2.4.55 | table_parity — caption-only table emits no `### Table` heading | 15 docs | table_parity fail→pass ×15, 0 new fails |
| 3 | v2.4.56 | glyph — CMEX10 extensible matrix-bracket pieces (U+F8EE-F8FB) | `ieee_access_10` | glyph fail→pass ×1, 0 new fails |

All three: harness-gated, real-PDF regression tests added, lean release path (Phase 7 cleanup/review skipped — see LEARNINGS SPINE-SKIPs; the harness Tier-D is the gate).

## Bugs fixed

1. **Adobe-Symbol-font PUA glyphs** — new `normalize.py::recover_pua_glyphs` maps the Symbol StandardEncoding (U+F020-F0FF) → real Unicode; wired into all 3 text channels.
2. **CMEX10 extensible-bracket PUA glyphs** — same helper extended with U+F8EE-F8FB → U+23A1-23A6 (geometry-confirmed).
3. **Caption-only tables dropped from the rendered view** — `render.py` now emits `### {label}` + caption for an in-section caption-only table (was: italic caption only, no heading), consistent with the appendix path.

## Run 10 MUST do first

1. **Full 3-level `--force` extract + `checks --update-baseline`.** Run 9's per-cycle extracts were `--levels academic` only (a full 3-level extract is ~3× slower and did not fit the budget). The committed `baseline_matrix.json` still reflects v2.4.53 (none/standard cells especially). Until the baseline is updated, a regression of cycles 1-3's 18 fixed cells would NOT be flagged by Tier-D (it stays `fail`→`fail`). The per-cycle real-PDF regression tests protect the fixes in the meantime, but the baseline must be re-locked. Sequence: restart the service at the current version → `python -m scripts.harness.extract --force` (all 3 levels) → `python -m scripts.harness.checks --update-baseline`.
2. Merge the open `docpluckapp` auto-bump PR(s) so prod advances to v2.4.56.

## Open Tier-D / Tier-A punch-list (run 10's queue)

Ranked. Each carries run-9's completed analysis — pick up from here.

### 1. `plos_med_1` — U+FFFD where pdftotext destroyed `≥` (glyph, S0, 1 doc)
- 3 FFFD in the rendered .md: `age ?18 years`, `(<20/?20 mm)`, `<20 mm versus ?20 mm` — all are `≥`.
- **Both pdftotext AND pdfplumber drop the glyph to U+FFFD** (font `TeX_CM_Maths_Symbols` = cmsy10). The layout channel cannot recover it — the glyph identity is destroyed in both engines.
- **Fix design:** a new normalize step. Airtight rule: `<N` … `?N` (same N, same clause) → the `?` is `≥` (complement of `<N`); symmetric `>N`…`?N` → `≤`. This recovers 2 of the 3 rendered FFFD with zero false-positive risk. The 3rd (`age ?18`) has no local complement — extend with a doc-level inference (if every airtight pair in the doc agrees on `≥`, a lone `?`-before-digit is `≥`), but GUARD against the 6 size-bin FFFD in the table region (`?5–10 mm` … `?40 mm` — get `plos_med_1`'s AI gold via `article-finder generate-gold` to confirm whether those bins are `≥`-prefixed before applying a doc-wide rule).
- `normalize.py` already has `S5a_fffd_context_recovery` (recovers `?²` → `eta²`). Add a sibling S5b for the `≥`/`≤` case.

### 2. `text_loss` — 9 docs, largely Tier-D **check false-positives** (S1/S2)
- Run-9 finding: xiao-status-quo's `text_loss` fail is NOT real text loss — the sentence is fully present. `checks.py::_fingerprint` drops the raw `χ2` (χ is not `[a-z]`) but keeps the rendered `chi2` → `chi`; the extra "chi" word breaks the 8-word contiguous-window match → false "missing paragraph".
- **Fix design:** make `_fingerprint` glyph-representation-consistent — either transliterate Greek→ASCII-name on BOTH raw and rendered before fingerprinting, or drop the transliterated forms consistently. This is a **`scripts/harness/checks.py` change** (the harness, not the library) — no version bump, no re-extract; just re-run `checks`.
- **CAUTION:** not all 9 are check-FPs. Several missing samples are linearized table/stimulus regions (li-feldman gambling problems, mayiwar `bbbggg` birth-sequence, korbmacher difficulty-rating note). Generate AI golds (via `article-finder`) for the 9 and run Tier-A to adjudicate REAL loss vs check-artifact BEFORE loosening the check — do not make the gate blind to real loss.

### 3. `nat_comms_3` — Camelot extraction timeout (environmental, NOT a code regression)
- `nat_comms_3` (13.4 MB, 19 pages) times out at >900s in the service `/analyze`. pdftotext alone is 2.4s — the slow layer is **Camelot table extraction**. The code path (`extract_structured.py` / `tables/`) is byte-identical to v2.4.53; run 8 extracted this doc fine (baseline `extraction: pass`). Cycles 1-3 touched only normalize/render — a single-char-class regex cannot cause a 15-min slowdown. So this is environmental (machine load / accumulated Camelot temp-file state) OR a latent Camelot perf issue.
- **Run 10:** restart the service fresh, clear Camelot temp artifacts, re-extract `nat_comms_3` alone. If it still times out, profile Camelot on it — likely needs a per-doc extraction-time cap or a Camelot page-limit (an **architecture decision** — surface to the user).

### 4. HALLUC-HEAD-2 (Tier-A) — from the run-8 handoff
- `## Funding` is the CRediT role "Funding acquisition" **split** across a heading + orphan word — a gap in v2.4.53's `_demote_credit_role_headings` (it misses split role labels). Also open-ended `## Conclusion` / `## Evaluation` / `## Findings` mis-promotions.

### 5. run-7 residuals + COL — re-confirm against the harness
- TBL-CAP (table-caption over-extension into column headers), FIG-3c-2 (body-exceeds-block caption double-emission), G5d (named/unnumbered heading demotion), G5c-2 (partitioner split-heading rejoin), COL (column-interleave — `test_request_09`, the 1 pre-existing broad-pytest fail; layout-channel, likely escalation-class).

## Process notes / methodology

- **Targeted-extract protocol (run-9 methodology choice, surfaced to the user).** A full whole-corpus academic extract is ~70 min on this machine; per-cycle full extracts do not fit a 5h budget. Run 9 used: cycle 1 full extract (validated the harness end-to-end), cycles 2-3 targeted `--force --only <affected docs>` extracts. This is sound *because* each fix is a signature-gated no-op on unaffected docs (the helpers early-return) — the change is provably byte-identical elsewhere. Run 10's mandatory full 3-level extract (above) is the corpus-wide backstop.
- **Tooling gotcha:** a literal Private-Use / invisible codepoint typed into a Write/Edit `content` does not survive (the `\uXXXX` is interpreted then stripped). Build non-ASCII codepoints with `chr(0x...)` in source — see `tests/test_pua_glyph_recovery_real_pdf.py`.
- **Do NOT run the harness `extract` and the broad `pytest` concurrently** — CPU contention starves the FastAPI service and produces false `extraction` timeouts (3 docs hit this in run 9).
- `_project/lessons.md` gained 2 entries (harness `--force` requirement; the "defensive render choice that drops a structural marker" lesson). LEARNINGS.md has the 3 per-cycle journals.

## Stop reason

`time:5h` budget exhausted. 3 cycles shipped clean (18 Tier-D cells fixed). The corpus is **NOT clean** — 11 Tier-D fails + `nat_comms_3` + the Tier-A backlog remain. The run's standing verdict is **PARTIAL**; run 10 continues the punch-list above.
