> **STATUS 2026-06-18 — SHIPPED (PARTIAL) in docpluck v2.4.93.** Full surface
> (`?flatten_tables_inline` / `?structured` / `?sections`, all default-OFF) is live
> on `POST /api/extract`, plus the dash-sign CI fix. See
> [`REPLY_FROM_DOCPLUCK_v2.4.93.md`](REPLY_FROM_DOCPLUCK_v2.4.93.md). Acceptance #1
> is **PARTIAL**: R1 + R4 surface sign-correct; **R2/R3/R5/R6 are blocked at the
> Camelot capture layer** (orphaned row-labels), queued as a Tier-2 table-extraction
> fix (docpluck `LESSONS.md` L-009). #2/#3 met; #4 is ESCImate's to run.
>
> **UPDATE 2026-06-19 — v2.4.94 CLOSES acceptance #1.** ESCImate verified against the
> live service: PROSECCO Table 2 now returns all 6 gold rows (R1–R6) via `?structured=true`,
> sign-correct (R2's `(-11.2--7.5)` resolved to `[-11.2, 7.5]`), exactly 6/88 flattened_rows
> carry stat fields → zero false positives. ESCImate will consume `flattened_rows[].fields`.
> **Remaining table-row work moved to `REQUEST_11_FLATTEN_FIELDS_NONCLINICAL_TABLES.md`:**
> the flattener still emits empty `fields` for *non-clinical* result tables
> (`10.1525/collabra.77859`, `10.1525/collabra.90203`) — grid captured but headers blank
> and stats packed per cell. That is the only open table-flatten item.

# Docpluck Request 10 — Expose the EC-T1 table flattener / structured tables / sections over the hosted `/api/extract` HTTP API

**Requested by:** ESCImate (escimate.app) / effectcheck R package team
**Date:** 2026-06-18
**Priority:** MEDIUM-HIGH — unblocks a real, recurring PARSE-MISS class in ESCImate; the underlying feature was *already built in docpluck v2.2.0 explicitly for this consumer*, it just isn't reachable over HTTP.
**Related:**
- **Activates `REQUESTS_FROM_ESCIMATE.md` Request 4** ("Table extraction — LOW PRIORITY, defer to later … implement only if a specific use case emerges"). The specific use case has now emerged (see Reproducer).
- `REQUEST_08_CHUNKING_ENDPOINT.md` / `REQUEST_09_REFERENCE_LIST_NORMALIZATION.md` — architectural siblings: move a structural concern up into docpluck instead of re-deriving it in every downstream parser.
- ESCImate side: `ESCIcheckapp/LESSONS.md` (2026-06-18 entry "Flattened-table-row extraction is NOT tractable as a line parser"), `ESCIcheckapp/docs/handoffs/2026-06-18-table-row-extraction.md`, shared lesson card `verify-extractor-delivered-text-before-routing-parse-miss` (refinement "text present ≠ structure present").

---

## TL;DR

docpluck **v2.2.0** shipped the EC-T1 table flattener (`docpluck/tables/flatten.py`,
`flatten_tables_for_paper` → `FlattenedRow`) plus `extract_pdf_structured`
(`docpluck/tables/__init__.py`, structured `Table`/`Cell` with row/col coordinates) and
`extract_sections` (`docpluck/sections/`). The `flatten.py` module docstring **explicitly
names the intended consumers: "downstream stat-verification consumers
(effectcheck/escimate/scimeto)."** This is exactly what ESCImate needs.

**But none of it is reachable over the hosted HTTP API that ESCImate consumes.** ESCImate
calls `POST https://docpluck.app/api/extract` (see `ESCIcheckapp/worker/docpluck_client.R`)
and only ever receives `{metadata, normalization, quality, text}`. Verified empirically
against the **live** service on 2026-06-18 with `?tables=true`, `?sections=true`,
`?flatten_tables_inline=true`, `?structured=true` — every combination returns the same
text-only payload, and the `text` still contains the raw, column-shredded table cells
(no `<table>`, no flattened sentences). The published api-docs document only
`normalize` and `quality` params.

**The ask:** surface the already-built flattener / structured-tables / sections over
`/api/extract` behind an opt-in query parameter, default OFF (so ESCImate's current call is
byte-for-byte unchanged). Then ESCImate's existing inline-statistic parser consumes the
flattened APA sentences with near-zero new code.

---

## Why this matters (the consumer problem)

ESCImate's `effectcheck` parser is built around **inline APA statistics** —
`t(df)=…, p=…, d=… [CI]` written in a sentence. It deliberately does **not** try to
reconstruct table structure from flattened text, because the hosted `/api/extract` delivers
tables **column-shredded and reading-order-scrambled**: cells on separate lines, row labels
detached from their data, headers split across lines, and the cell-count / column-meaning
varying by row. A positional binder over that dump would mis-bind cells and emit a
**fabricated** statistic (e.g. read a risk-difference `-1.83%` as a "PSA percentage"),
which ESCImate's "never display garbage" design principle forbids.

So ESCImate scoped and then **deferred** building its own table parser (2026-06-18 decision):
the values are present in the delivered text, but their 2-D relational structure
(value → row-label → column) is destroyed by flattening. The only safe recovery path is for
**docpluck to deliver the structure** — which docpluck already computes internally (Camelot
cells with `bbox`, header detection, EC-T1 row flattening) but throws away before the HTTP
response.

---

## Reproducer (live, 2026-06-18)

**File:** `10.1371/journal.pmed.1004323` (PROSECCO trial, PLOS Medicine).
Resolve via `python ~/.claude/skills/article-finder/cache-check.py "10.1371/journal.pmed.1004323"`
→ `…/ArticleRepository/fulltext/10.1371__journal.pmed.1004323.pdf`.

**Current hosted `/api/extract?normalize=academic` `text` for Table 2** (verbatim, 2026-06-18):

```
isk diff. (95% P value
CI)

(87.8%)

(88.8%)

-1.01% (-10.36-
8.34)

0.09

(88.3%)

(88.2%)

0.06% (-9.53-
9.65)

0.06

-1.83% (-11.2-7.5)

-

0.82% (-8.63-
10.28)

-

7.7 (-3.2-18.5)

0.15

8.4 (-3.1-19.9)

0.14

adjusted for stratification factors
When incomplete; max. size of intracavitary remnant
```

The row labels ("Resection complete", "adjusted for stratification factors", "When
incomplete; max. size of intracavitary remnant") are emitted **before and after** their data
blocks; the data blocks have **different column semantics per row** (the "Resection complete"
block is `[PSA%, GA%, RD(CI), P]`; the "adjusted"/"remnant" blocks are
`[ITT-effect(CI), ITT-P, PP-effect(CI), PP-P]`). Unrecoverable by a line parser.

**ESCImate's AI ground truth** for this paper (`ai_gold/10.1371__journal.pmed.1004323/stats.json`)
has 5 table-only rows that effectcheck currently MISSES because they have no inline form:

| gold id | row | reported | 95% CI | p |
|---|---|---|---|---|
| R2 | ITT adjusted risk difference | −1.83% | (−11.2, 7.5) | — (cell `-`) |
| R3 | ITT remnant size, mean diff (t-test) | 7.7 mm | (−3.2, 18.5) | 0.15 |
| R4 | PP risk difference | 0.06% | (−9.53, 9.65) | 0.06 |
| R5 | PP adjusted risk difference | 0.82% | (−8.63, 10.28) | — |
| R6 | PP remnant size, mean diff (t-test) | 8.4 mm | (−3.1, 19.9) | 0.14 |

What docpluck's `flatten_tables_for_paper` would produce instead (per the library
contract) is one `FlattenedRow` per data row with a clean inline-APA `.sentence` and a parsed
`.fields` dict — e.g. for R3 something like
`{"row_label": "When incomplete; max. size of intracavitary remnant", "sentence": "…: 7.7 (95% CI -3.2 to 18.5), p = .15", "fields": {"M_diff": 7.7, "CI_lower": -3.2, "CI_upper": 18.5, "p": 0.15}}`.
That sentence is parseable by effectcheck's existing patterns; the `.fields` are a structured
fast-path.

---

## The request

Add an **opt-in** capability to `POST /api/extract`, **default OFF** (current behavior
unchanged — REQUEST 1.4's "no surprises for ESCImate" guardrail still holds). Two delivery
modes; **(A) is the minimum viable, (B) is the richer follow-on.** Implement (A) first if you
have to pick one.

### (A) `?flatten_tables_inline=true` — inline the rendered APA sentences into `text` (PREFERRED, smallest integration)

Wire the existing `render_pdf_to_markdown(..., flatten_tables_inline=True)` path (or call
`flatten_tables_for_paper` and splice) so that each table's flattened "rendered as text" rows
appear in the `text` field, fenced by the existing markers:

```
<!-- docpluck:flattened-table id="T2" start -->
### Table 2 — rendered as text
* When incomplete; max. size of intracavitary remnant: 7.7 (95% CI -3.2 to 18.5), p = .15
* …
<!-- docpluck:flattened-table id="T2" end -->
```

ESCImate then just adds `&flatten_tables_inline=true` to its existing call and its current
inline parser reads those sentences. **No new ESCImate parsing feature required.** The raw
scrambled cells can stay in `text` too (ESCImate dedups), or be replaced by the flattened
block — please document which.

### (B) `?structured=true` — add structured arrays to the JSON response (richer, enables a fields fast-path)

Add to the response (only when requested):

```jsonc
{
  "text": "...",
  "metadata": { ... },
  "normalization": { ... },
  "quality": { ... },
  "tables": [            // from extract_pdf_structured(): Table[]
    {
      "id": "t2", "label": "Table 2", "page": 9,
      "caption": "...", "footnote": "...",
      "kind": "structured", "rendering": "whitespace", "confidence": 0.9,
      "n_rows": 7, "n_cols": 8, "header_rows": 2,
      "cells": [ { "r": 0, "c": 0, "rowspan": 1, "colspan": 1, "text": "...", "is_header": true, "bbox": [..] }, ... ],
      "html": "<table>…</table>"
    }
  ],
  "flattened_rows": [    // from flatten_tables_for_paper(): FlattenedRow[]
    {
      "table_id": "t2", "page": 9, "label": "Table 2", "row_idx": 2,
      "row_label": "When incomplete; max. size of intracavitary remnant",
      "header": ["...","..."], "raw_cells": ["...","..."],
      "sentence": "…: 7.7 (95% CI -3.2 to 18.5), p = .15",
      "fields": { "M_diff": 7.7, "CI_lower": -3.2, "CI_upper": 18.5, "p": 0.15, "p_op": "=" }
    }
  ],
  "sections": [          // from extract_sections(): optional, behind ?sections=true
    { "label": "results", "canonical_label": "results", "text": "...",
      "char_start": 0, "char_end": 0, "pages": [9], "confidence": "high",
      "detected_via": "heading", "heading_text": "Results" }
  ]
}
```

Field names above are taken verbatim from the library types (`docpluck/tables/__init__.py`
`Cell`/`Table`, `docpluck/tables/flatten.py` `FlattenedRow`, `docpluck/sections/__init__.py`
`Section`/`SectionedDocument`). Keep them stable across releases — ESCImate will bind to them.

### One correctness note docpluck is uniquely positioned to get right: the dash-sign ambiguity

The flattened CIs use a dash as the lo–hi separator that collides with negative signs, e.g.
`(-11.2-7.5)` (= lower −11.2, upper +7.5) and `(-8.63-10.28)`. ESCImate's gold's two
extraction passes *disagreed* on the sign of one bound. Because docpluck has the **cell-level
structure and the bbox geometry**, it can disambiguate far more reliably than any text parser
(e.g. split on the separator x-gap, or enforce the estimate∈CI invariant: the point estimate
must lie inside its own interval). Please resolve sign in `FlattenedRow.fields.CI_lower/upper`
and document the rule.

---

## Acceptance

1. `POST /api/extract?flatten_tables_inline=true` on the PROSECCO PDF returns a `text` whose
   Table 2 region contains the 5 flattened rows above (R2–R6) with correctly bound
   effect / CI / p cells, and the default call (no param) is byte-identical to today.
2. (If (B) shipped) `?structured=true` returns `tables[]` + `flattened_rows[]` with the
   field names above; `flattened_rows` for PROSECCO Table 2 carries R2–R6 with
   `CI_lower < CI_upper` sign-correct.
3. api-docs (`/api-docs`) and `docs/API.md` document the new param(s), the response fields,
   and the default-OFF contract.
4. ESCImate verifies end-to-end via the existing benchmark harness
   (`ESCIcheckapp/tests/scripts/docpluck_shootout.R`) and an article-finder gold comparison:
   the 5 PROSECCO Table-2-only rows are detected by `effectcheck::check_text()`, with **zero
   new false positives** on the rest of the `escimate_validation` corpus (diff pre/post
   renders — the only new rows should be the intended table rows).

---

## Notes / boundaries

- **Default OFF** is non-negotiable (REQUEST 1.4 guardrail): ESCImate's production call must
  not change behavior until ESCImate opts in and re-verifies.
- This is **not** a normalization change and should not need a `NORMALIZATION_VERSION` bump;
  it's surfacing already-computed structure through the HTTP layer (the work is in the hosted
  Next.js service that owns `/api/extract`, plus a thin serializer over the library types).
- ESCImate owns the consumer side; once exposed, integration is `worker/docpluck_client.R`
  (add the query param + read the new fields) + feeding the flattened sentences into
  `check_text()`. ESCImate will mark table-derived rows with a `check_scope` tag and route
  them conservatively (NOTE when not independently verifiable).
- Contact / arbiter: ESCImate team (giladfel@gmail.com). Changes to this request can be made
  by either team with a note in the respective LESSONS.md.
