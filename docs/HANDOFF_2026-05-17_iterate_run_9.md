# Handoff — docpluck-iterate run 9 (mid-run) → fresh session

**Authored:** 2026-05-17, ~143 min into a `time:5h` run. **For:** a fresh
`/docpluck-iterate` session that **continues run 9** (~2h35m of budget remained
when this session handed off — context ran low, not the clock).

This is a **mid-run handoff**, not an end-of-run one: 3 cycles shipped clean,
the Tier-D backlog is **not** empty, and the run should continue. The standing
verdict is **PARTIAL** until the corpus is clean or the budget is spent.

**Read first:** `docs/HANDOFF_2026-05-17_iterate_run_8.md` (harness design),
`scripts/harness/README.md`, and `.claude/skills/docpluck-iterate/LEARNINGS.md`
(the 3 run-9 cycle journals at the bottom).

---

## State at handoff

- Library version: **v2.4.56** — run 9 shipped **v2.4.54, v2.4.55, v2.4.56**, three clean harness-gated cycles. All three committed + tagged + pushed to `main` (commits `ef63ba2`, `5938b78`, `bddbd04`; run-9 handoff `5c3ad3c`).
- **Auto-bump PRs in `docpluckapp` are NOT merged** — merge the latest so prod's `service/requirements.txt` pin advances to v2.4.56.
- Local FastAPI service: last restarted at v2.4.56 (background task `bz1lp6pyd`). **Verify it (`curl -s localhost:6117/health` → `docpluck_version` 2.4.56) or restart it** before any harness work: `cd ../PDFextractor/service && python -m uvicorn app.main:app --port 6117 --env-file .env --workers 4`. Restart is required after every library code change (the service caches the imported modules).
- Harness Tier-D (academic level) at v2.4.56: **fail count 28 → 11** (+ `nat_comms_3` extraction timeout). 18 cells fixed (3 glyph + 15 table_parity), 0 new fails across all 3 cycles.
- `verify_out/` is a **mix of versions** (cycle-1 full extract was v2.4.54; cycles 2-3 re-extracted only their targeted docs). `baseline_matrix.json` is **still run-8's (v2.4.53)** — not updated this run.

## Cycles shipped this run

| Cycle | Ver | Defect (class) | Fix | Result |
|---|---|---|---|---|
| 1 | v2.4.54 | Adobe-Symbol-font PUA glyphs β/χ/• as U+F0xx (glyph) | new `normalize.py::recover_pua_glyphs` — Symbol StandardEncoding U+F020-F0FF → Unicode, 3 channels | bh1988 + xiao-monin-miller glyph fail→pass |
| 2 | v2.4.55 | caption-only/isolated table emits no `### Table` heading (table_parity) | `render.py` in-section `elif cap:` branch emits `### {label}` + caption | 15 docs table_parity fail→pass |
| 3 | v2.4.56 | CMEX10 extensible matrix-bracket pieces U+F8EE-F8FB (glyph) | `recover_pua_glyphs` extended → U+23A1-23A6 | ieee_access_10 glyph fail→pass |

All lean release path (Phase 7 cleanup/review skipped — harness Tier-D is the gate; see LEARNINGS SPINE-SKIPs).

## DO FIRST (fresh session, before new cycles)

1. **Full 3-level `--force` extract + `checks --update-baseline`.** Run 9's per-cycle extracts were `--levels academic` only. The committed `baseline_matrix.json` still reflects v2.4.53, so a regression of cycles 1-3's 18 fixed cells would NOT be flagged (it stays `fail`→`fail`). Until then the per-cycle real-PDF regression tests are the only guard. Sequence: confirm service at current version → `python -m scripts.harness.extract --force` (all 3 levels — slow, ~hours; or `--levels academic` + accept academic-only) → `python -m scripts.harness.checks` (expect `nat_comms_3` extraction as the only diff vs a clean run) → `checks --update-baseline`.
2. Merge the open `docpluckapp` auto-bump PR(s) → prod to v2.4.56.
3. **Methodology smell-test** (Phase 0.8) before any code.

## Open backlog (the queue — pick up here)

Each item carries run-9's completed analysis.

### Cycle 4 — `plos_med_1` U+FFFD where pdftotext destroyed `≥` (glyph, S0, 1 doc) — IN PROGRESS, designed
- **rendered.md has 3 FFFD**, all `≥`: `age �18 years`, `(<20/�20 mm)`, `<20 mm versus �20 mm`. raw.txt has 9 total (6 more are table-region size bins `�5-10 mm` … `�40 mm`, which do NOT reach rendered.md — the Tier-D `glyph` check only flags rendered.md, so cycle 4 must clear the 3 prose ones).
- **Both pdftotext AND pdfplumber drop the glyph to U+FFFD** (font `TeX_CM_Maths_Symbols` = cmsy10). The layout channel cannot recover it — glyph identity is destroyed in both engines. Recovery must be context-based.
- `normalize.py` already has `S5a_fffd_context_recovery` (~line 1798) — recovers `�` followed by `²`/`2 = .NN` → `eta`. Add a sibling **S5b** for the `≥`/`≤` case.
- **Fix design (airtight + scoped):**
  - Rule 1 (airtight, zero false-positive): within one line/clause, `<\s*(\d+)` … `�\s*\1` (same N) → that `�` is `≥` (the complement of `<N`). Symmetric `>N`…`� N` → `≤`. This recovers `(<20/?20)` and `<20 versus ?20` — 2 of the 3.
  - Rule 2 (for the lone `age ?18` — no local complement): a doc-level inference — if every Rule-1 firing in the doc agrees on `≥` (and there is ≥1), a lone `�` directly before a digit → `≥`. **GUARD against the 6 table-region size bins** — get `plos_med_1`'s AI gold (`article-finder generate-gold`) to confirm whether those bins are `≥`-prefixed before applying any doc-wide rule; if uncertain, scope Rule 2 to prose lines only (Rule 1 alone still gets 2/3, and the 3rd can be escalated).
- Real-PDF regression test required (rule 0d). Targeted extract `--force --only pdfextractor__vancouver__plos-med-1`.

### Cycle 5 — `text_loss` — 9 docs, largely Tier-D **check false-positives** (S1/S2)
- **Run-9 finding (verified on xiao-status-quo):** the `text_loss` fail is NOT real loss — the sentence is fully present in rendered.md. `scripts/harness/checks.py::_fingerprint` drops the raw `χ2` (χ ∉ `[a-z]`) but keeps the rendered `chi2` → `chi`; the extra "chi" token breaks the 8-word contiguous-window match → false "missing paragraph".
- **Fix:** make `_fingerprint` glyph-representation-consistent — e.g. transliterate Greek→ASCII-name on BOTH the raw and the target before fingerprinting, or strip transliterated forms consistently. This is a **`scripts/harness/checks.py`** change (the harness, not the library) → **no version bump, no re-extract** — just re-run `checks`.
- **CAUTION — do not just loosen the check.** Several of the 9 missing-samples are genuine linearized table/stimulus regions (li-feldman gambling problems, mayiwar `bbbggg`/`gbbgbg` birth-sequences, korbmacher difficulty-rating note). Generate AI golds for the 9 (`article-finder`) and run **Tier-A to adjudicate REAL loss vs check-artifact** before/alongside the `_fingerprint` fix — never make the gate blind to real text loss.
- The 9 text_loss docs: `escicheck__ding-feldman-2025-rsos-pcirr-fox-rottenstreich-2003`, `escicheck__korbmacher-etal-2022-kruger-1999`, `escicheck__li-feldman-2025-rsos-pcirr-revisiting-mental-accounting-thaler1999`, `escicheck__mayiwar-etal-2024-qjep-kahneman-tversky-1972`, `escicheck__wong-feldman-2025-rsos-read-etal-1999`, `escicheck__xiao-et-al-status-quo-bias-samuelson-zeckhauser-1988`, `escicheck__xiao-etal-2024-irsp-monin-miller2001`, `pdfextractor__apa__korbmacher-2022-kruger`, `pdfextractor__vancouver__plos-med-1`.

### `nat_comms_3` — Camelot extraction timeout (environmental, NOT a code regression)
- `nat_comms_3` (13.4 MB, 19 pages) times out at >900s in the service `/analyze`. pdftotext alone is 2.4s — the slow layer is **Camelot table extraction**. `extract_structured.py`/`tables/` is byte-identical to v2.4.53; run 8 extracted this doc fine (baseline `extraction: pass`). Cycles 1-3 touched only normalize/render (a single-char-class regex cannot cause a 15-min slowdown) — provably not a code regression. Environmental (machine load / accumulated Camelot temp state) or a latent Camelot perf issue.
- **Fix path:** restart the service fresh, clear Camelot temp artifacts (`%TEMP%`), re-extract `nat_comms_3` alone. If it still times out, profile Camelot on it — likely needs a per-doc extraction-time cap or a Camelot page-limit (an **architecture decision** — surface to the user).

### Tier-A backlog (from run-8 handoff, re-confirm against the harness)
- **HALLUC-HEAD-2:** `## Funding` is the CRediT role "Funding acquisition" **split** across a heading + orphan word — a gap in v2.4.53's `_demote_credit_role_headings` (misses split role labels). Plus open-ended `## Conclusion`/`## Evaluation`/`## Findings` mis-promotions.
- **run-7 residuals:** TBL-CAP (table-caption over-extension into column headers), FIG-3c-2 (body-exceeds-block caption double-emission), G5d (named/unnumbered heading demotion), G5c-2 (partitioner split-heading rejoin).
- **COL:** column-interleave — `test_request_09` is the one pre-existing broad-pytest fail (red since run 4); layout-channel reading order, likely escalation-class.

## Methodology / gotchas (carry forward)

- **Targeted-extract protocol.** A full whole-corpus academic extract is slow (~tens of min). Each run-9 cycle's fix was a signature-gated no-op on unaffected docs (the helpers early-return), so cycles 2-3 used `extract --force --only <affected docs>` + a whole-corpus `checks`. Sound *because* the change is provably byte-identical elsewhere — but the fresh session must still do the **full 3-level extract + `--update-baseline`** (DO FIRST #1) as the corpus-wide backstop.
- **Harness `extract.py` skips on `source_sha1`, not docpluck version** — a plain `extract` after a code change skips every doc. `--force` is mandatory. (See `_project/lessons.md`.)
- **Never run the harness `extract` and the broad `pytest` concurrently** — CPU contention starves the service → false `extraction` timeouts (3 docs hit this in run 9).
- **Tooling:** a literal Private-Use / invisible codepoint typed into a Write/Edit `content` does not survive (the `\uXXXX` is interpreted then stripped). Build non-ASCII codepoints with `chr(0x...)` in source — see `tests/test_pua_glyph_recovery_real_pdf.py`. The `normalize.py` `_SYMBOL_PUA_RE`/`_SYMBOL_PUA_MAP` region holds literal PUA chars (functionally correct, verified) — edit it via a `chr()`-construction Python rewrite, not a string-match Edit.
- LEARNINGS.md has the 3 run-9 cycle journals; `_project/lessons.md` gained 2 entries (harness `--force`; "a defensive render choice that drops a structural marker is usually wrong").

## Run-meta / postflight

`~/.claude/skills/_shared/run-meta/docpluck-iterate.json` is **un-finalized** (the run continues): `bugs_fixed` (3), `tests_added` (3), `lessons_appended` (2), `phase_failures` (2) are populated; `verdict`/`completed_at`/`postflight_heartbeat` are cleared. The fresh session's preflight extends this file; finalize it + run the Phase 12 postflight at the true end of the run.

## Stop reason (this session)

Context budget ran low — handed off mid-run. The clock budget (`time:5h`) had ~2h35m remaining. The fresh session continues from **cycle 4 (plos_med_1 FFFD)**.
