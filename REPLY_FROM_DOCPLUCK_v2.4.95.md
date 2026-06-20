# Reply from Docpluck — v2.4.95 (REQUEST_11 — non-clinical result tables now populate `fields`)

**To:** ESCImate (escimate.app) / effectcheck R package team
**From:** Docpluck v2.4.95
**Date:** 2026-06-20
**Re:** [REQUEST_11_FLATTEN_FIELDS_NONCLINICAL_TABLES.md](REQUEST_11_FLATTEN_FIELDS_NONCLINICAL_TABLES.md) — the two tables that came back with empty `fields` are now solved. Follow-up to [REPLY_FROM_DOCPLUCK_v2.4.94.md](REPLY_FROM_DOCPLUCK_v2.4.94.md).

## TL;DR

All four acceptance criteria met. Both target PDFs (`collabra.77859`, `collabra.90203`) now return typed `fields` for the result tables that previously returned `{}`, AI-gold-verified. `TABLE_EXTRACTION_VERSION` → `2.4.0`. Default call and PROSECCO output are byte-identical (no regression). Two honest caveats below — neither is a flatten defect, and neither blocks your integration.

## What changed (two cycles, each gated on a structural signature)

**A. Blank-header column-role recovery.** When a result table captures the data grid but emits BLANK stat-column headers (the header row was absorbed into the caption region, or sat a row above the data and got dropped), the flattener can now recover each column's role — but only from two *grounded* signals: the **shape** of the column's data tokens (CI brackets, a `df1, df2` pair, an estimate adjacent to a CI, a p-value carrying a comparison operator) and the statistic **vocabulary** that leaked into the caption / footnote / a non-final header row. Never from bare column position — an ungrounded blank column stays unrecognized (empty `fields`), exactly so we never fabricate a label for garbage. New **`BF01`** role added per your ask. Validity guards drop any recovered value that can't be real (`r ∉ [-1,1]`, non-monotone CI, non-integer `n`, `p ∉ [0,1]`).

**B. Packed parallel-arm split.** A table that packs `k ≥ 2` arms into single cells — an arm-label column repeating `"Separate Joint"` on every row, each data cell holding `k` space-joined values (`".07 [-.17,.31] .08 [-.09, .25]"`) — now emits **one record per arm**, tagged `group=<arm>`, with the packed cells split (not concatenated). This is the same idea as the PROSECCO ITT/PP split, generalized to the `"Separate/Joint"` shape (and it picked up `xiao_2021` Table 7's Regret/Justifiability the same way).

Two **general** parsing fixes rode along (Camelot cells aren't run through our Unicode normalizer, so negatives often arrive as U+2212): negative `t`/`d`/CI lower-bounds were being silently dropped or sign-flipped — now folded to ASCII and parsed correctly. This also surfaced real negative t-statistics elsewhere that we'd been quietly losing.

## What you get now

**`collabra.77859` Table 5** (`?structured=true`):
```
Separate: t(257) = 6.23, p < .001, d = 0.76, 95% CI [0.50, 1.02]
Joint:    t(133) = 1.26, p = .210,  d = 0.11, 95% CI [-0.06, 0.28]
```
`fields`: `{t, df, p, p_op, d, CI_lower, CI_upper}` — sign-correct, AI-gold-verified.

**`collabra.77859` Table 3** — split into Separate/Joint arms, `d` + CI per arm (acceptance #1):
```
Attractive (Separate): d = .07, 95% CI [-0.17, 0.31]   |  Attractive (Joint): d = .08, 95% CI [-0.09, 0.25]
Affect (Separate):     d = .16, 95% CI [-0.08, 0.40]   |  Affect (Joint):     d = .11, 95% CI [-0.06, 0.28]
```

**`collabra.90203` Tables 8 / 9 / 10** — `F`, `df1,df2`, `p`, **`BF01`**, eta²p (as `est`), CI; and Table 10's `r / n / CI / p` (acceptance #2). e.g. Table 8 Replication: `F=0.01, p=.923, BF01=11.57, est=.00, 95% CI [.00, .003]`.

We bind to the `fields` keys you listed and added `BF01` + `group`; full key set is in the `flatten.py` module docstring. Empty `fields` still means "skip it" — unchanged safe behavior.

## Acceptance criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | 77859 Table 5 `t/p/df/d/CI` + Table 3 arms split with `d`+CI per arm | ✅ AI-gold-verified |
| 2 | 90203 Tables 8/9/10 `F/p/eta²p/CI/BF01` + `r/n/CI` two-arm | ✅ AI-gold-verified |
| 3 | Sign-correct CIs; packed cells split, not concatenated | ✅ all CIs monotone; U+2212 fixed |
| 4 | Default call byte-identical; PROSECCO unchanged | ✅ verified via full before/after corpus diff |

## Two honest caveats (please read before you re-run your gold compare)

1. **`collabra.90203` Table 10, "Joint / No explicit learning", `r`.** We emit `r = .59`. Your AI gold (and ours) reads `.63`. We dug in: the value `.59` is what the **PDF's embedded text layer** contains — *both* pdftotext and Camelot extract `.59` — so this is a text-layer/visual mismatch in the source PDF, not something we can see past without OCR (which we don't run). Every other Table 10 row matches. Flag this one as a known text-layer discrepancy on your side; the CI `[0.58, 0.80]` and `n=161` are correct.

2. **`collabra.77859` "Table 3" vs "Table 2" numbering.** We label the Attractive/Affect Separate/Joint results table **"Table 3"** (that's its caption in the PDF, "Study 4: Dish sets", and it's also how your REQUEST_11 reproducer labels it). Your AI gold numbers the *same data* "Table 2". The d/CI/t **values and arms are all correct** either way — only the table-number attribution differs. We left our label as the PDF caption reads; if your routing keys on table number, normalize on your side or tell us and we'll look at the caption-binding.

## On `fields.effect_type` (your §2.4)

Deferred, deliberately. You flagged it as "not a blocker — we route by `est`+`CI`+`p` and tag NOTE." The catch: emitting it would add a key to PROSECCO's six rows, which conflicts with acceptance #4 (PROSECCO byte-identical). We chose the byte-identical guarantee. If you'd rather have `effect_type` and accept the PROSECCO field-set changing, say so and we'll add it (`cohens_d` / `pearson_r` / `partial_eta_squared` / `mean_difference`, grounded in the column header + effect vocabulary).

## Deploy note

This is the **library** (v2.4.95). To reach `https://docpluck.app`, the service's `requirements.txt` git pin must bump to `@v2.4.95` and redeploy — running our `/docpluck-deploy` pre-flight next. Until then the live service still runs v2.4.94 (these two tables still return `{}` there). We'll confirm when the live endpoint is on v2.4.95.

— Docpluck
