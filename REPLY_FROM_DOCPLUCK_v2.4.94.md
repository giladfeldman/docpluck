# Reply from Docpluck — v2.4.94 (REQUEST_10 Tier-2 gap CLOSED)

**To:** ESCImate (escimate.app) / effectcheck R package team
**From:** Docpluck v2.4.94
**Date:** 2026-06-19
**Re:** Follow-up to [REPLY_FROM_DOCPLUCK_v2.4.93.md](REPLY_FROM_DOCPLUCK_v2.4.93.md) — the PROSECCO R2/R3/R5/R6 gap is now fixed.

## TL;DR

In v2.4.93 I reported acceptance #1 as **PARTIAL**: PROSECCO Table 2 surfaced R1 + R4, but R2/R3/R5/R6 were blocked at the table-**capture** layer. **That gap is now closed in v2.4.94.** PROSECCO Table 2 flattens all six gold arm-records, sign-correct.

## Root cause (it was NOT what we first thought)

The first hypothesis — "Camelot drops the rows / orphaned labels need layout-channel synthesis" — was wrong. Grounding in the **raw per-flavor Camelot output** showed: Camelot **stream** captured every row (but lost the header text and vertically split each value from its `(percentage)`/CI-tail); Camelot **lattice** had clean headers but only the ruled-box rows; and docpluck's page-level flavor selection discarded the fuller stream table. So `flatten` never saw the rows.

## Fix (v2.4.94, `TABLE_EXTRACTION_VERSION` → 2.3.0)

1. **Cross-flavor row augmentation** — when lattice truncates a table stream captured in full (same column count, overlapping bbox, stream extends below), the missed lower rows are appended onto lattice's clean-header frame.
2. **Numeric/parenthetical continuation merge** — rejoins stream's split cells (`86`+`(87.8%)` → `86 (87.8%)`; `-1.01% (-10.36-`+`8.34)` → `-1.01% (-10.36-8.34)`).

Both gated hard on structural signatures; **full 2051-test suite green, zero regressions.**

## What you get now (PROSECCO Table 2, `?flatten_tables_inline=true` / `?structured=true`)

```
- Resection complete* (ITT): Risk diff = -1.01%, p = 0.09, 95% CI [-10.36, 8.34]   # R1
- Resection complete* (PP):  Risk diff =  0.06%, p = 0.06, 95% CI [-9.53, 9.65]    # R4
- adjusted for stratification factors (ITT): Risk diff = -1.83%, 95% CI [-11.2, 7.5]   # R2
- adjusted for stratification factors (PP):  Risk diff =  0.82%, 95% CI [-8.63, 10.28] # R5
- ... remnant (mean SD)† (ITT): Risk diff = 7.7, p = 0.15, 95% CI [-3.2, 18.5]      # R3
- ... remnant (mean SD)† (PP):  Risk diff = 8.4, p = 0.14, 95% CI [-3.1, 19.9]      # R6
```

All six with sign-correct `CI_lower < CI_upper`. The table's size-distribution sub-rows also surface as label-only `flattened_rows` (no stats; harmless to `check_text()`).

## Acceptance (updated)

- **#1 — now MET** (was PARTIAL): all five previously-missing rows R2/R3/R5/R6 surface, default call still byte-identical.
- **#2 — MET**: `flattened_rows` carry sign-correct CIs for every captured row.
- **#3 — MET**: docs updated (`PDFextractor/API.md`, `/api-docs`).
- **#4 — yours to run**: `docpluck_shootout.R` + gold compare; expect R2–R6 detected by `check_text()`, the only new rows being the intended table rows (plus the label-only size sub-rows, which you can drop by `check_scope`).

## Note

Minor residual: PROSECCO's size-bin labels carry a corrupted `≤` glyph (`�5–10 mm`) — a pre-existing pdftotext cell-glyph issue in those non-statistical count rows, unrelated to this fix and not blocking any stat row.

Production (`docpluck.app`) serves v2.4.94 once the tag is pushed (auto-bumps the Railway pin).

— Docpluck team
