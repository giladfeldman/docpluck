# Handoff — docpluck-iterate run 9 (continued, session 2) → fresh session

**Authored:** 2026-05-18, after shipping cycle 5 (app service_version 1.5.1).
**For:** a fresh `/docpluck-iterate` session that **continues run 9**.

This is a **mid-run handoff**. The Open queue is **not** empty — the run
continues. Standing verdict is **PARTIAL** until the whole queue is resolved
or each remaining item is explicitly escalated.

**Goal (unchanged, 2026-05-18 user directive):** address ALL issues — the
Group A Tier-D harness fails AND the full Group B / structural backlog. Leave
nothing behind. The run continues until every Open-queue item is resolved or
escalated to the user with analysis.

**Read first:** this doc, then `HANDOFF_2026-05-18_iterate_run_9_cont.md` (the
prior handoff — its **Group B punch-list B1–B7 is still the authoritative
detail** and is NOT reproduced here), `scripts/harness/README.md`,
`tmp/known-tier-deltas.md`, the `docpluck-iterate/LEARNINGS.md` run-9 cycle-5
journal (bottom).

---

## State at handoff

- **docpluck library: v2.4.57** — unchanged this session (cycle 5 was app-only).
- **docpluckapp: service_version 1.5.1** shipped — commits `c20fdcf` (fix) +
  `a4d3879` (test drift) on `master`, pushed. `verify-railway-deploy.yml` CI
  **success**. **Prod `/health` = service_version 1.5.1, docpluck_version
  2.4.57** (verified live, 49 s after push).
- **Harness Tier-D baseline refreshed** — committed `7bbf889` (docpluck `main`,
  pushed). **10 open fails** = 8 `text_loss` + 2 `extraction`. (Was 11; cycle 5
  fixed `xiao-status-quo` text_loss.)
- `verify_out/` holds the **post-cycle-5** whole-corpus extraction (180 docs,
  academic level, cycle-5 service code).
- Local FastAPI service: running at docpluck 2.4.57 / service_version 1.5.1.
  **Verify (`curl -s localhost:6117/health`) or restart** before harness work
  (see "Methodology / gotchas" — restart kills ALL uvicorn workers).
- The local `../PDFextractor` checkout is **current** (merged origin/master +
  cycle-5 commits, pushed). No git divergence to resolve.

## Cycle shipped this session

| Cycle | Ver | Defect (class) | Fix | Result |
|---|---|---|---|---|
| 5 | app svc-1.5.1 | DELTA-1: app `/analyze` + `/sections` views ASCII-transliterate math/Greek glyphs (`extract_sections` built with default `preserve_math_glyphs=False`, reused as `_sectioned=`) | both `extract_sections(file_bytes=content)` call sites (`main.py` 506 + 786) now pass `preserve_math_glyphs=True` | DELTA-1 resolved; app `/analyze` rendered byte-matches library render (plos_med_1 56678==56678, chan_feldman 87202==87202); Tier-D 0 regressions / 0 new fails / 1 fixed; 3 new tests; prod verified |

Phase 7 took the **lean path** (SPINE-SKIP recorded): cycle 5 touches no docpluck
library code, so the library hard rules have zero surface; inline 11-item
checklist done + passed.

## Bugs fixed this session

- **DELTA-1** — app `/analyze` + `/sections` glyph transliteration (the cycle).
- **5 docpluckapp service-test drift fixes** (commit `a4d3879`, test-only):
  stale `sectioning_version=="1.0.0"` (×2 sites → assert the live constant);
  two Xpdf-era SMP-recovery *mechanism* assertions → assert the clean-output
  *invariant* (poppler emits SMP codepoints, not U+FFFD, so the U+FFFD-keyed
  recovery legitimately stays dormant and normalize S0 destyles them);
  `test_math_italic_greek_eta` asserting the pre-v2.4.34 `eta→'n'` corruption →
  assert destyle to regular Greek eta; `test_all_styles_have_content` failing
  on the empty `test-pdfs/docx/` folder → skip folders with no synced fixtures.

## DO FIRST (fresh session)

1. **Methodology smell-test** (Phase 0.8) before any code.
2. Verify the local service (`curl -s localhost:6117/health` → docpluck 2.4.57,
   service_version 1.5.1) or restart it:
   `cd ../PDFextractor/service && python -m uvicorn app.main:app --port 6117 --env-file .env --workers 4`
3. Pick up at **cycle 6** below.

## Open queue — address ALL of it (run continues until empty or escalated)

### Cycle 6 — harness `_fingerprint` glyph-consistency + adjudicate 8 `text_loss` fails
- **KEY UPDATE from cycle 5:** the prior handoff predicted the glyph-transliteration
  `text_loss` false-positives would "mostly clear" after cycle 5. **They did
  NOT — only 1 of 9 cleared** (`xiao-status-quo`). So the **8 residual
  `text_loss` fails are candidate-GENUINE text loss, not check artifacts** —
  do NOT assume they are `_fingerprint` artifacts.
- The 8 residual `text_loss` docs: escicheck `ding-feldman`, `korbmacher-etal`,
  `li-feldman`, `mayiwar`, `wong-feldman`, `xiao-monin-miller`; pdfextractor
  apa `korbmacher-2022`, vancouver `plos-med-1`.
- **Adjudicate** each: obtain the AI gold via `article-finder generate-gold`
  (NEVER self-generate — rule 18), compare the harness `rendered.md` against the
  gold, classify REAL text loss vs check artifact. The prior handoff flagged
  `li-feldman` gambling problems / `mayiwar` `bbbggg` birth-sequences /
  `korbmacher` difficulty-rating note as linearized-table/stimulus regions —
  re-confirm against the gold.
- **`_fingerprint` defense-in-depth** (`scripts/harness/checks.py`): transliterate
  Greek→ASCII-name on BOTH raw and target before fingerprinting, so a future
  raw/rendered glyph divergence cannot create a false positive. Harness-only
  change — no library bump, no re-extract; just re-run `checks`.
- Real text loss found → that is a library defect → its own cycle.

### Cycle 7 — `normalize_text` single-pass word-rejoin incompleteness (DISCOVERED cycle 5)
- **Repro:** `extract_pdf(chan_feldman_2025_cogemo.pdf)` → `normalize_text(raw,
  academic)` = `norm1` (79436 chars) CONTAINS broken words `repli cations`,
  `differ ences`, `con ducted`. `normalize_text(norm1, academic)` = `norm2`
  (79385 chars) JOINS them. So the production single pass leaves broken words;
  a 2nd pass fixes them — the word-rejoin step is incomplete / mis-ordered on
  one pass.
- **Real production bug** — broken words ship in normalized / sections /
  rendered output, corpus-wide (intra-word spurious-space is a common
  tight-kerned-pdftotext artifact). Library cycle (`docpluck/normalize.py`);
  find the non-idempotent step (likely a word-rejoin that runs before a step
  it depends on, or a position-gated strip).
- **Regression witness:** `PDFextractor/service/tests/test_benchmark.py::
  test_normalization_idempotent` is left **intentionally RED** — it correctly
  caught this. It goes green when cycle 7 ships. Do NOT "fix the test."
- Needs a library version bump + tag + its own harness re-extract.

### Extraction timeouts — `nat_comms_3` + `xiao-poc-epley` (Group A, environmental)
- Both still time out (confirmed this session's full extract — genuine, not
  contention). Baselined `extraction=fail`. Fix path unchanged from the prior
  handoff: fresh service + clear Camelot `%TEMP%`, re-extract alone; if still
  timing out → profile Camelot → per-doc extraction cap or page-limit
  (**architecture decision — surface to the user**).
- NOTE: `maier` is NOT a genuine timeout — it false-fails under `--workers 4`
  CPU contention and clears on an un-contended re-extract (done this session).

### GROUP B — Tier-A / structural defects (B1–B7)
**Unchanged. See `HANDOFF_2026-05-18_iterate_run_9_cont.md` "GROUP B" for the
full B1–B7 punch-list** (TABLE-builder cluster, section-annotator
over-promotion, D4 metadata leak, caption residuals, G5c-2 partitioner rejoin,
COL column-interleave, GLYPH deleted-minus). Per the 2026-05-18 directive these
are firm queued cycles of this run, not a future-run deferral. Re-confirm each
at HEAD before coding.

## Process improvements proposed (awaiting user approval)

- **PROPOSED AMENDMENT — run the docpluckapp service test suite in the loop.**
  Cycle 5 was the first cycle to touch app code and run
  `PDFextractor/service/tests/`; it found 6 dormant issues (5 test drift + 1
  real library bug) invisible for many cycles because that suite is outside the
  iterate loop (the loop runs the docpluck library pytest + the harness only).
  Proposal: add a Phase 5/6 step — when a cycle touches `PDFextractor/service/`
  code, run the service suite and triage failures per the 3-bucket rule; also
  run it periodically (~every 5 cycles). Full rationale in the LEARNINGS run-9
  cycle-5 entry.

## Stop reason (this session)

Session context budget. Cycle 5 was completed end-to-end (app fix + 3 regression
tests + 5 pre-existing-drift fixes + full 180-doc corpus re-extract + Tier-D
gate + Phase 6c byte-parity + prod deploy + verify + baseline refresh + journal).
Handed off at the clean post-cycle-5 boundary rather than starting cycle 6
half-way. The run's standing verdict is **PARTIAL** — the Open queue (cycle 6,
cycle 7, extraction timeouts, Group B1–B7) is non-empty; the run continues.
