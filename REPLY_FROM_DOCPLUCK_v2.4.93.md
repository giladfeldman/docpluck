# Reply from Docpluck — REQUEST_10 (Table-flatten / structured-tables / sections over HTTP)

**To:** ESCImate (escimate.app) / effectcheck R package team
**From:** Docpluck v2.4.93
**Date:** 2026-06-18
**Re:** [REQUEST_10_TABLE_FLATTEN_HTTP_EXPOSURE.md](REQUEST_10_TABLE_FLATTEN_HTTP_EXPOSURE.md) — also closes [REQUESTS_FROM_ESCIMATE.md](REQUESTS_FROM_ESCIMATE.md) Request 4.

## TL;DR

**Shipped the full surface (modes A + B + sections) behind opt-in, default-OFF params on `POST /api/extract`.** Your current call is byte-identical until you opt in. Add `&flatten_tables_inline=true` and your existing inline-APA parser reads the flattened rows with no new parsing code.

**One honest caveat, grounded in a real run of the PROSECCO PDF (not a guess):** for PROSECCO Table 2, **Camelot captures only the first of the table's three conceptual data rows** ("Resection complete"). The "adjusted for stratification factors" and "remnant size (mean diff)" rows have row-labels rendered as orphaned text blocks *below* the numeric grid, so they're dropped at the table-**extraction** layer before flatten ever runs (`thorough=True` doesn't recover them). So acceptance criterion #1 is **PARTIAL**: you get sign-correct **R1 (ITT) + R4 (PP)** today; **R2/R3/R5/R6 are blocked on a separate Tier-2 fix** (orphaned-label row recovery), which is queued, not silently dropped — details below.

## What you got (v2.4.93)

### New `/api/extract` params — all default OFF

| Param | Scope | Effect |
|-------|-------|--------|
| `flatten_tables_inline=true` | PDF | Appends each table's flattened rows (one APA sentence per data row) into `text`, fenced by `<!-- docpluck:flattened-table id="…" start/end -->`. **Raw cells are retained** above the block — dedup on your side if needed. |
| `structured=true` | PDF | Adds top-level `tables[]` (structured `Cell[]` incl. per-cell `bbox` + pre-rendered `html`) and `flattened_rows[]` (`FlattenedRow[]`). |
| `sections=true` | PDF/DOCX/HTML | Adds top-level `sections[]` (same shape as `/api/sections`). |

With none set, the response is the exact historical `{text, metadata, normalization, quality}` (REQUEST 1.4 "no surprises" guardrail holds). Opt-in calls **bypass the server-side extraction cache** (it only stores `{text, metadata}`); cache on your side if you call repeatedly. Full docs: [`PDFextractor/API.md` → Structure surfacing](../PDFextractor/API.md).

### `flattened_rows` field names (stable — bind to these)

`table_id, page, label, row_idx, row_label, header, raw_cells, sentence, fields`. The `fields` dict carries any recognized statistics: `t, F, chi2, r, d, eta2, M, SD, n, N, df, df1, df2, p, p_op, CI_lower, CI_upper`, plus two new keys this release:
- **`est`** — a combined-column point estimate (from a `Risk diff. (95% CI)` / `Mean diff (95% CI)` / `OR (95% CI)` style column).
- **`group`** — a parallel-arm tag (e.g. `ITT` / `PP`) when the table has a folded super-header.

### Three general flatten-quality fixes (library v2.4.93, keyed on structural signatures)

1. **Combined `est_ci` columns** — `Risk diff. (95% CI)` etc. were previously unclassified and dropped; now both the estimate and its interval are parsed from the one cell.
2. **Dash-sign CI disambiguation** — you flagged that your two gold passes *disagreed* on a bound's sign for `(-11.2-7.5)`. Resolved with two general invariants: interval monotonicity (`lo < hi`) and, when a point estimate is present, the **estimate-in-interval** invariant (`lo ≤ est ≤ hi`). A typographically distinct range glyph (en/em-dash or " to ") is treated as sign-unambiguous and used directly. So `flattened_rows` carry **sign-correct** `CI_lower < CI_upper`.
3. **Parallel arms** — one `FlattenedRow` per (row × arm), so the two `P value` / two `Risk diff.` columns in ITT/PP tables no longer collide (previously the second silently overwrote the first).

### PROSECCO Table 2 — what you actually get now

The captured "Resection complete" row flattens into two sign-correct records:

```
- Resection complete* (ITT): Risk diff = -1.01%, p = 0.09, 95% CI [-10.36, 8.34]
- Resection complete* (PP): Risk diff = 0.06%, p = 0.06, 95% CI [-9.53, 9.65]
```

That is your gold **R1** (ITT risk diff) and **R4** (PP risk diff −, the one of your 5 "missing" rows that Camelot does capture), with correct effect / CI / p binding.

## Acceptance criteria mapping

| # | Criterion | Status |
|---|-----------|--------|
| 1 | PROSECCO Table 2 region contains R2–R6; default call byte-identical | **PARTIAL.** Default call byte-identical ✅. R4 surfaced sign-correct ✅. **R2/R3/R5/R6 NOT surfaced** — dropped at Camelot capture, not flatten (Tier-2, queued). |
| 2 | `?structured=true` returns `tables[]` + `flattened_rows[]`; PROSECCO CIs sign-correct (`CI_lower < CI_upper`) | **MET** for every row Camelot captures. |
| 3 | api-docs + `API.md` document params, fields, default-OFF | **MET** (`PDFextractor/API.md`, `/api-docs`). |
| 4 | ESCImate end-to-end via `docpluck_shootout.R` + gold compare, zero new false positives | **Yours to run** — see below. |

## What you should do

1. In `worker/docpluck_client.R`, add `flatten_tables_inline=true` (and/or `structured=true`, `sections=true`) to the query string. Read the appended sentences (or `flattened_rows`) and feed them into `check_text()`. Tag table-derived rows with your `check_scope` marker and route conservatively, as planned.
2. Run `tests/scripts/docpluck_shootout.R` + a gold compare on `escimate_validation`. The only **new** rows in the diff should be intended table rows; flag any new false positive back to us.
3. Expect PROSECCO to gain R1 + R4, not the full 5, until Tier-2 lands.

## Tier-2 (queued, not done here): orphaned-label row recovery

Recovering R2/R3/R5/R6 needs a **table-extraction** change — rebinding row-labels that Camelot renders as separate blocks below the grid and recovering multi-value rows. That's a broad, regression-risky change to the capture layer requiring full-baseline + AI-gold verification across publishers, so it is scoped as its own effort (tracked in docpluck `LESSONS.md` L-009 and the iterate queue). If PROSECCO-class multi-block tables are high-value for your corpus, say so and we'll prioritize it.

## Versions

- docpluck `__version__` → **2.4.93**. **No `NORMALIZATION_VERSION` / `SECTIONING_VERSION` / `TABLE_EXTRACTION_VERSION` change** — this is flatten + HTTP surfacing, so your cached normalized extractions are NOT invalidated.
- Production (`docpluck.app`) picks up v2.4.93 when the library tag is pushed (the `bump-app-pin.yml` workflow bumps `service/requirements.txt` on tag → Railway redeploy). Until then the params are live in the app layer but the flatten-quality fixes ride the library pin.

Tests: 35 flatten unit tests (16 new) + 6 new service integration tests (incl. the default-OFF byte-identical assertion) green.

— Docpluck team
