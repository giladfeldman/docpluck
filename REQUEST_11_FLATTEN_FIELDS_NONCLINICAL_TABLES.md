> **STATUS — ADDRESSED in docpluck v2.4.95 (2026-06-20).** All 4 acceptance criteria met, both target PDFs AI-gold-verified. See [REPLY_FROM_DOCPLUCK_v2.4.95.md](REPLY_FROM_DOCPLUCK_v2.4.95.md) and [docs/HANDOFF_2026-06-20_request11_flatten_nonclinical_tables.md](docs/HANDOFF_2026-06-20_request11_flatten_nonclinical_tables.md). Two source-data caveats (Table 10 `r=.59` text-layer; Table 3/2 caption numbering) and the opt-in `effect_type` are documented in the reply. **Library not yet deployed** — live service runs v2.4.94 until the service pin bumps to `@v2.4.95`.

# Docpluck Request 11 — Populate `flattened_rows[].fields` (+ APA `sentence`) for non-clinical result tables

**Requested by:** ESCImate (escimate.app) / effectcheck R package team
**Date:** 2026-06-19
**Priority:** MEDIUM-HIGH — this is the remaining blocker on the table-row PARSE-MISS class. v2.4.94 solved it for the clinical-trial table; two of our three target tables still come back with empty `fields`.
**Related:**
- **Direct follow-up to `REQUEST_10_TABLE_FLATTEN_HTTP_EXPOSURE.md`** and its Tier-2 (`REQUEST_10_TIER2_ORPHANED_LABEL_ROW_RECOVERY.md`). Replies: `REPLY_FROM_DOCPLUCK_v2.4.93.md`, `REPLY_FROM_DOCPLUCK_v2.4.94.md`.
- ESCImate side: `ESCIcheckapp/tmp/iterate/docpluck_spike/EVIDENCE.md` (the spike that produced the data below), `ESCIcheckapp/docs/handoffs/2026-06-18-table-row-extraction.md`.

---

## 0. First — thank you. v2.4.94 works exactly as advertised on PROSECCO.

We ran the new flags against the **live** `https://docpluck.app/api/extract` on our three
target PDFs (baseline / `?flatten_tables_inline=true` / `?structured=true` /
`?sections=true`). Confirmed on our side:

- **Default call is byte-identical** (no flags → `{text, metadata, normalization, quality}`, text length unchanged).
- **PROSECCO `10.1371/journal.pmed.1004323` Table 2 is fully solved.** `?structured=true`
  returns **exactly 6 of 88 `flattened_rows` carrying stat fields — precisely the 6 gold
  rows R1–R6**, typed and sign-correct, including the dash-ambiguous R2 CI
  `(-11.2--7.5)` correctly resolved to `[-11.2, 7.5]` via your estimate-in-interval
  invariant (more reliable than our AI gold's raw verbatim, whose two passes disagreed on
  that sign). Zero false positives. We will consume `flattened_rows[].fields` directly.
- **Sections work** on all three (canonical labels, `confidence=high`, char offsets tile
  end-to-end with **0 boundary gaps**). `pages` comes back `[]` but offsets are what we need.

So Mode B (`structured`) is our chosen integration path. **This request is only about the
two tables where `fields` is not yet populated.**

---

## 1. The gap — non-clinical result tables capture the grid but emit empty `fields`

For our other two targets, `?structured=true` returns `flattened_rows` where **`fields` is
`{}`** and **`sentence` is the row label only** (not an APA sentence) — even though
`raw_cells` clearly contains the statistics and the table was captured. Two structural
problems are visible in the payload:

1. **Column headers are empty / misaligned**, so the flattener can't label which column is `t` / `F` / `r` / `p` / `df` / effect-size+CI.
2. **Multiple statistics are packed into a single cell** (a vertical-split artifact), so even with headers the value→column map is ambiguous.

Both are things docpluck can resolve with the cell **bbox geometry it already holds**;
a downstream text parser cannot (this is the whole reason REQUEST_10 existed). We are **not**
going to positionally bind these cells ourselves — empty headers + packed cells are exactly
the fabrication risk our design forbids ("never display garbage").

### Reproducer A — `10.1525/collabra.77859`, Table 5 (and Table 3)

Gold rows we need (independent-samples t with d + 95% CI; df in a header row):

| Row | t | p | df | d [95% CI] |
|---|---|---|---|---|
| Separate Evaluation | 6.23 | < .001 | 257 | 0.76 [.50, 1.02] |
| Joint Evaluation | 1.26 | .210 | 133 | 0.11 [-.06, .28] |

What `?structured=true` returned (verbatim from the live response):

```jsonc
// Table 5, row "Separate"
{ "label":"Table 5", "row_label":"Separate",
  "header":   ["", "Mean", "", "Mean", "", "", "", ""],          // stat columns unlabeled
  "raw_cells":["Separate", "$23.25 $32.69 3.91", "< .001", "$23.96 $33.70", "6.23", "< .001", "257", "0.76 [.50, 1.02]"],
  "sentence":"Separate",                                          // label only
  "fields":{} }                                                  // empty

// Table 3, row "Attractive" — note two arms packed per cell ("Separate Joint")
{ "label":"Table 3", "row_label":"Attractive",
  "header":   ["","","M (SD)","M (SD)","","","","d or dz [95%CI]"],
  "raw_cells":["Attractive","Separate Joint","4.76 (1.14) 4.50 (1.17)","4.84 (1.04) 4.61 (1.19)","0.60 0.95",".551 .344","260.54 131",".07 [-.17,.31] .08 [-.09, .25]"],
  "sentence":"Attractive", "fields":{} }
```

Note the packed cells: `"$23.25 $32.69 3.91"` is *Set-A mean + Set-B mean + t* in one cell;
in Table 3 every data cell holds the **Separate** and **Joint** sub-columns space-joined
(`".07 [-.17,.31] .08 [-.09, .25]"`), and `"260.54 131"` is two df values. This is the same
class as PROSECCO's ITT/PP parallel arms you already split — it just isn't firing here.

### Reproducer B — `10.1525/collabra.90203`, Tables 8, 9, 10

Three sub-shapes, all returning `fields:{}`:

- **Table 8** — columns `[stat, p, BF01, eta²p, 95% CI]`, header labels only `BF01`:
  ```jsonc
  { "label":"Table 8", "row_label":"Replication",
    "header":["","","","BF01","",""],
    "raw_cells":["Replication","0.01",".923","11.57",".00","[.00, .003]"], "fields":{} }
  ```
  Gold for that row: test stat 0.01, p .923, BF01 11.57, eta²p .00, 95% CI [.00, .003].
  (One row also leaked a heading into a data cell:
  `"3.91 H2: Interaction: Identifiability and Explicit Learning"` — a capture artifact.)
- **Table 9** — F-tests with BF, e.g. gold `F(1, 666) = 0.01, p = .940, BF01 = 11.56, eta²p = 0.00, 95% CI [0.00, 0.002]`.
- **Table 10** — correlations with parallel "Target article" vs "Replication" arms, e.g. gold
  `Identifiable/Explicit learning: Replication n 170, r .63, 95% CI [0.53, 0.72], p < .001`
  (same two-arm structure as ITT/PP).

---

## 2. What we need

Extend the v2.4.94 flattener so `flattened_rows[].fields` (and the APA `sentence`) are
populated for these non-clinical result-table shapes too, using the same stable
`FlattenedRow` contract. Concretely:

1. **Align stat columns when the header cell is blank** by reading the column's data tokens
   (and/or a `df`/`t`/`p`/`d or dz [95%CI]` label that sits in a *separate header row above*
   the data row). The PROSECCO path already proves you can emit typed `fields`; here the
   header just needs to be recovered from geometry rather than an adjacent text cell.
2. **Split packed cells** (`"$23.25 $32.69 3.91"`, `".07 [-.17,.31] .08 [-.09, .25]"`,
   `"260.54 131"`) into their constituent values — the same parallel-arm split you do for
   ITT/PP, generalized to the "Separate/Joint" and "Target article/Replication" arm pairs.
3. **Populate `fields`** with whatever is recognized, reusing your documented keys:
   `t, F, r, d, eta2, df, df1, df2, p, p_op, CI_lower, CI_upper, est, group`, plus please
   add **`BF01`** (Bayes factor) since these tables report it.
4. **Carry a semantic effect-type hint if you have one.** Minor but useful: in PROSECCO,
   rows R3/R6 are *mean differences* (remnant size, mm) but the `sentence` renders them as
   `"Risk diff = 7.7"` (the table's RD column label bled onto a t-test row). A
   `fields.effect_type` (e.g. `risk_difference_pct` vs `mean_difference` vs `cohens_d` vs
   `pearson_r`) would let us label/route correctly. If unavailable, we route by
   `est`+`CI`+`p` and tag NOTE — not a blocker.

We do **not** need you to compute or verify anything — just expose the parsed cells as typed
`fields` the way you already do for the clinical table.

---

## 3. Acceptance criteria

1. `?structured=true` on `10.1525/collabra.77859` returns `flattened_rows` for Table 5 with
   `fields` carrying `t=6.23, p=…, df=257, d=0.76, CI_lower=.50, CI_upper=1.02` (Separate) and
   the Joint row likewise; Table 3 rows split into Separate/Joint arms with `d` + CI per arm.
2. `?structured=true` on `10.1525/collabra.90203` returns `fields` for Tables 8/9/10 covering
   the `F/p/eta²p/CI/BF01` and `r/n/CI/p` (two-arm) shapes above.
3. Sign-correct CIs (same invariants as v2.4.94); packed cells split, not concatenated.
4. Default call (no flags) remains byte-identical; PROSECCO output unchanged (no regression).
5. (ours) We re-run the spike + AI-gold compare end-to-end and confirm zero new false
   positives, then ship the Mode B consumer integration.

---

## 4. How we'll consume it (so you know the shape we depend on)

`worker/docpluck_client.R` will call `/api/extract?structured=true&sections=true`, read
`flattened_rows[]` whose `fields` carry a recognized statistic, hand each to
`effectcheck::check_text()` as a table-derived row tagged via `check_scope`, and route
conservatively (NOTE unless independently verifiable). We bind to the **`fields` keys**, so
keep those names stable. Nothing breaks if a row has empty `fields` — we just skip it, which
is exactly today's safe behavior.

Questions or a shape you want a second sample of? The two DOIs above reproduce on the live
service today with `?structured=true`. Thanks again for the fast v2.4.93→v2.4.94 turnaround.

— The ESCImate / effectcheck team
