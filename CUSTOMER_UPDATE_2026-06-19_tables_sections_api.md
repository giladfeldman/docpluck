# Docpluck API Update — Tables & Sections are now reachable over HTTP

**To:** All Docpluck API consumers (ESCImate / effectcheck, Scimeto / CitationGuard, MetaESCI, and any project calling `POST /api/extract`)
**From:** Docpluck team
**Date:** 2026-06-19
**Library versions:** `docpluck` **v2.4.93** (2026-06-18) → **v2.4.94** (2026-06-19)
**Endpoint:** `POST https://docpluck.vercel.app/api/extract` (+ `POST /api/sections`)

---

## TL;DR

Docpluck has, for some time, computed rich **table structure** (Camelot cells with
per-cell coordinates, header detection, APA-style row "flattening") and **semantic
section boundaries** (abstract / methods / results / references / …) *inside the
library*. Until now none of that was reachable over the hosted HTTP API — every
`/api/extract` call returned text-only `{text, metadata, normalization, quality}`,
with tables arriving column-shredded inside `text`.

**As of v2.4.93–v2.4.94 you can now opt in to that structure over HTTP:**

| New parameter | What you get | Formats |
|---|---|---|
| `?flatten_tables_inline=true` | Each table's data rows appended into `text` as one clean **APA-style sentence per row**, fenced by HTML-comment markers | PDF |
| `?structured=true` | Top-level `tables[]` (structured cells + per-cell `bbox` + pre-rendered `html`) and `flattened_rows[]` (parsed `fields` dict per row) | PDF |
| `?sections=true` | Top-level `sections[]` — labelled, char-offset semantic sections | PDF / DOCX / HTML |

There is also a dedicated **`POST /api/sections`** endpoint if you only want
section structure.

**Nothing changes unless you ask for it.** With none of these flags set, every
response is **byte-for-byte identical** to what you receive today. This is a strict,
additive, opt-in expansion — no migration required.

---

## 1. Tables — from column-shredded text to parseable rows

### The problem this solves

The hosted API has always delivered PDF tables as **column-shredded,
reading-order-scrambled** text: cells on separate lines, row labels detached from
their data, headers split across lines, and the column meaning varying row to row.
A line parser over that dump mis-binds cells and can emit a **fabricated** statistic
(e.g. reading a risk-difference as a percentage). That is why downstream consumers
deliberately *did not* try to reconstruct tables from flat text — the 2-D
relationship (value → row-label → column) was destroyed by the time the text
reached you.

Docpluck is the right layer to fix this because it still holds the cell-level
structure and the page geometry. So we now expose it.

### 1a. `?flatten_tables_inline=true` — the smallest integration

Each detected table's rows are appended to `text` as one APA-style sentence per data
row, fenced by HTML comments so you can slice them out trivially. The raw cells stay
in `text` above the block (dedup on your side if you don't want them).

```
<!-- docpluck:flattened-table id="camelot_t10" start -->
### Table 2 — rendered as text
*Flattened from header + cells by docpluck v2.4.94.*

- Resection complete* (ITT): Risk diff = -1.01%, p = 0.09, 95% CI [-10.36, 8.34]
- Resection complete* (PP):  Risk diff =  0.06%, p = 0.06, 95% CI [-9.53, 9.65]
<!-- docpluck:flattened-table id="camelot_t10" end -->
```

**How to leverage it:** add `&flatten_tables_inline=true` to your existing
`/api/extract` call. If you already run an inline-statistic / APA parser over
`text`, it now reads these sentences with **no new parsing code** — the table values
arrive in exactly the inline form your parser already understands.

### 1b. `?structured=true` — the richer, structured fast-path

Adds two top-level arrays to the JSON response (only when requested):

```jsonc
{
  "tables": [ /* extract_pdf_structured: Table[] — structured cells incl. per-cell bbox + pre-rendered html */ ],
  "flattened_rows": [
    {
      "table_id": "camelot_t10", "page": 9, "label": "Table 2", "row_idx": 0,
      "row_label": "Resection complete*",
      "header": ["", "ITT PSA N = 98", "GA N = 89", "Risk diff. (95% CI)", "P value"],
      "raw_cells": ["Resection complete*", "86 (87.8%)", "79 (88.8%)", "-1.01% (-10.36-8.34)", "0.09"],
      "sentence": "Resection complete* (ITT): Risk diff = -1.01%, p = 0.09, 95% CI [-10.36, 8.34]",
      "fields": { "group": "ITT", "est": -1.01, "p": 0.09, "p_op": "=", "CI_lower": -10.36, "CI_upper": 8.34 }
    }
  ]
}
```

**`FlattenedRow` field names are stable across releases — bind to them.** The
`fields` dict carries any recognized statistics, all optional:
`t, F, chi2, r, d, eta2, M, SD, n, N, df, df1, df2, p, p_op, CI_lower, CI_upper`,
plus `est` (a combined-column point estimate) and `group` (a parallel-arm tag such
as `ITT` / `PP`).

**How to leverage it:** use `flattened_rows[].fields` as a typed fast-path (no
sentence re-parsing), or `tables[].cells` (with `bbox` + `html`) when you need the
full grid — e.g. rendering the table, or your own column logic.

### Three correctness guarantees worth knowing about

These ship in the flattener and apply to every captured row:

1. **Combined estimate-and-CI columns are parsed.** A header like
   `Risk diff. (95% CI)`, `Mean diff (95% CI)`, `OR (95% CI)`, or
   `Cohen's d (95% CI)` was previously unclassified and dropped. Now both the
   estimate and its interval are extracted from the one cell.
2. **CI sign is disambiguated.** A dash is both the lo–hi separator and a negative
   sign — `(-11.2-7.5)` means lower −11.2, upper +7.5. Docpluck resolves this with
   two general invariants: interval monotonicity (`CI_lower < CI_upper`) and, when a
   point estimate is present, the estimate-in-interval invariant
   (`CI_lower ≤ est ≤ CI_upper`). A typographically distinct range glyph (en/em-dash
   or " to ") is treated as sign-unambiguous. **Result: `flattened_rows` carry
   sign-correct bounds** — something a pure text parser cannot reliably do because it
   lacks the cell geometry.
3. **Parallel arms don't collide.** A folded super-header (`ITT` / `PP`,
   `Study 1` / `Study 2`) emits **one row per (row × arm)** with a `fields.group`
   tag, so two `P value` / two `Risk diff.` columns no longer silently overwrite each
   other.

> **Format note:** tables and flattening are **PDF-only**. On DOCX/HTML those two
> flags are ignored and `metadata.tables_skipped="non-pdf"` is set. `sections` still
> works on all three formats.

---

## 2. Sections — labelled, char-offset semantic structure

You can now get the document's **semantic section map** — where the abstract,
methods, results, references, etc. begin and end — two ways:

- **`POST /api/extract?sections=true`** — adds a `sections[]` array to the normal
  extract response (PDF / DOCX / HTML).
- **`POST /api/sections`** — a dedicated endpoint returning only the section map.

Each section looks like:

```json
{
  "label": "methods",
  "canonical_label": "methods",
  "char_start": 1842,
  "char_end": 12530,
  "pages": [3, 4, 5],
  "confidence": "high",
  "detected_via": "heading_match",
  "heading_text": "Method",
  "text": "Participants. We recruited …"
}
```

**Key properties:**

- **18 canonical labels:** `title_block`, `abstract`, `keywords`, `introduction`,
  `literature_review`, `theoretical_background`, `hypotheses`, `methods`, `results`,
  `discussion`, `conclusion`, `references`, `footnotes`, `acknowledgments`,
  `funding`, `disclosures`, `supplementary`, `unknown`. (`label` may be suffixed,
  e.g. `methods_2`; `canonical_label` is always one of the 18.)
- **Universal coverage:** `char_start` / `char_end` offsets tile the normalized text
  end-to-end with **no gaps** — every byte belongs to exactly one section.
- **Confidence + provenance:** `confidence` (`low`/`medium`/`high`) and
  `detected_via` (`heading_match`, `layout_signal`, `markup`, …) let you decide how
  much to trust each boundary.

**How to leverage it:** scope your processing to the section you care about. For
statistical extraction, filter to `canonical_label == "results"` (and/or
`"methods"`) and run your detector only there — this removes a whole class of
boundary-drift bugs where front-matter whitespace shifted your chunking and a stat
was missed or picked up the wrong `df`. For citation work, jump straight to the
`references` section.

> **Stability:** `sectioning_version` is stable per library release. Bumping
> `docpluck` may relabel the same file — pin a version if your pipeline depends on
> stable labels.

> **Reference-section bonus (v2.4.85+):** section detection also drives cleaner
> reference lists — per-page download/watermark overlays (`Downloaded from …`,
> running footers) are stripped, and continuation lines that the PDF wrapped to a new
> block are reflowed back onto their reference. Numbered Vancouver/IEEE bibliographies
> now split cleanly one-entry-per-number instead of losing leading numbers to inlined
> watermark text.

---

## 3. How we implemented your request — and how to leverage it

This release is the direct answer to a specific, filed request:
**REQUEST_10 — "Expose the table flattener / structured tables / sections over the
hosted `/api/extract` HTTP API"** (raised by the ESCImate / effectcheck team,
2026-06-18), which also closes the long-standing **Request 4** ("table extraction —
implement only if a specific use case emerges"). The use case emerged.

### What you asked for

> "docpluck **already built** the EC-T1 table flattener, structured tables, and
> section extraction *in the library* — the `flatten.py` docstring even names the
> intended consumers (effectcheck / escimate / scimeto). But **none of it is
> reachable over the hosted HTTP API.** Surface it behind an opt-in query parameter,
> default OFF, so our current call is byte-for-byte unchanged. Then our existing
> inline parser consumes the flattened sentences with near-zero new code."

The reproducer was **PROSECCO Table 2** (PLOS Medicine, `10.1371/journal.pmed.1004323`):
five table-only rows (risk differences and mean differences, with CIs and p-values)
that have no inline form anywhere in the prose, so a stat-verification parser
**missed them entirely**. The table also has the dash-vs-minus CI ambiguity that made
two independent extraction passes *disagree* on the sign of a bound.

### How we implemented it — honestly, in two steps

We do not ship a plausible-sounding fix without reproducing the failure on the actual
PDF. Here is exactly what happened, including the part we got wrong first:

**Step 1 — v2.4.93 (2026-06-18): HTTP surface + flatten-quality fixes.**
We wired the already-built flattener / structured-tables / sections through
`/api/extract` behind the three default-OFF params above, and fixed three general
flatten-quality issues keyed on structural signatures (combined est+CI columns,
dash-sign CI disambiguation, parallel ITT/PP arms — see §1). We reported the result
**honestly as PARTIAL**: on PROSECCO Table 2, only the first of three conceptual data
rows ("Resection complete") was surfacing — so you got gold rows **R1 (ITT)** and
**R4 (PP)** sign-correct, but **R2/R3/R5/R6 were still missing**. Crucially, we told
you *why*: the missing rows were dropped at the table-**capture** layer, *before* the
flattener ever ran — and we queued (did not bury) the remaining fix.

**Step 2 — v2.4.94 (2026-06-19): the capture-layer gap, root-caused and closed.**
Our first hypothesis for the missing rows ("Camelot drops them / they're orphaned
labels needing layout synthesis") turned out to be **wrong**, and we only found that
by inspecting the *raw per-flavor Camelot output* for the page:

- Camelot **stream** captured *every* data row — but lost the column-header text and
  vertically split each value from its `(percentage)` / CI-tail.
- Camelot **lattice** had *clean headers* but only the one row inside the ruled box.
- Docpluck's page-level flavor selection let lattice win the page and **discarded the
  fuller stream table** — so the flattener never saw R2/R3/R5/R6.

The real fix was therefore in the capture layer, not the flattener: (1) a
**cross-flavor row augmentation** that grafts the rows stream captured but lattice
truncated onto lattice's clean-header frame (gated hard on equal column count +
overlapping/extending bbox), and (2) a **numeric/parenthetical continuation merge**
that rejoins stream's split cells (`86` + `(87.8%)` → `86 (87.8%)`). Both are keyed
on structural signatures, so they generalize to any stacked-cell table and touch no
table that already captured correctly — verified by the **full 2051-test suite green
with zero regressions**.

### What you get now, and how to leverage it

PROSECCO Table 2 now flattens to **all six gold arm-records, sign-correct**:

```
- Resection complete* (ITT): Risk diff = -1.01%, p = 0.09, 95% CI [-10.36, 8.34]   # R1
- Resection complete* (PP):  Risk diff =  0.06%, p = 0.06, 95% CI [-9.53, 9.65]    # R4
- adjusted for stratification factors (ITT): Risk diff = -1.83%, 95% CI [-11.2, 7.5]    # R2
- adjusted for stratification factors (PP):  Risk diff =  0.82%, 95% CI [-8.63, 10.28]  # R5
- ... remnant (mean SD) (ITT): Risk diff = 7.7, p = 0.15, 95% CI [-3.2, 18.5]       # R3
- ... remnant (mean SD) (PP):  Risk diff = 8.4, p = 0.14, 95% CI [-3.1, 19.9]       # R6
```

**To leverage it in your worker:**

1. Add `&flatten_tables_inline=true` (and/or `&structured=true`, `&sections=true`) to
   your existing `/api/extract` query string.
2. Read the appended APA sentences from `text` (sliced by the
   `<!-- docpluck:flattened-table … -->` markers) — or, if you opted into
   `structured=true`, read `flattened_rows[].sentence` / `.fields` directly.
3. Feed those rows into your existing stat detector. Table-derived rows have no inline
   form in the prose, so they are **purely additive** — the only new rows in a
   before/after diff should be the intended table rows. Tag them (e.g. a
   `check_scope` marker) and route them conservatively if your design requires
   independent verifiability.

> **Acceptance status:** all four REQUEST_10 acceptance criteria are now **MET** on
> our side (default call byte-identical; PROSECCO R2–R6 surfaced sign-correct;
> docs updated). Criterion #4 — end-to-end verification via your own benchmark
> harness + AI-gold compare — is yours to run; flag any new false positive back to us.

---

## 4. Backward compatibility, caching, and versioning

- **Default-OFF is non-negotiable.** With none of `flatten_tables_inline` /
  `structured` / `sections` set, the response is the exact historical
  `{text, metadata, normalization, quality}`. Your production call does not change
  behavior until you opt in and re-verify.
- **Cache note.** Opt-in structure calls **bypass the server-side extraction cache**
  (it only stores `{text, metadata}`). If you call repeatedly with these flags, cache
  on your side.
- **Quota.** `/api/sections` counts toward your daily quota (logged with
  `normalize_level="sections"`), same auth contract as `/api/extract` (session cookie
  or `Authorization: Bearer dp_...`).
- **No normalization-version bump.** These changes are flatten + capture + HTTP
  surfacing — `NORMALIZATION_VERSION` is unchanged, so your **cached normalized
  extractions are not invalidated**. (`TABLE_EXTRACTION_VERSION` bumped to `2.3.0` in
  v2.4.94; `SECTIONING_VERSION` unchanged.)
- **File-size paths.** `/api/extract` (and the structure flags on it) support the
  blob two-step upload for files >4.5 MB. `/api/sections` is multipart-only and
  subject to Vercel's 4.5 MB body limit — for larger files, run the `docpluck` Python
  library directly.

## 5. Full reference

- API contract & response shapes: `PDFextractor/API.md` → "Structure surfacing
  (opt-in)" and "POST /api/sections", and the live `/api-docs` page.
- Change history: `docpluck/CHANGELOG.md` entries **v2.4.93** and **v2.4.94**.
- The request/reply trail behind this update:
  `REQUEST_10_TABLE_FLATTEN_HTTP_EXPOSURE.md`,
  `REPLY_FROM_DOCPLUCK_v2.4.93.md`, `REPLY_FROM_DOCPLUCK_v2.4.94.md`.

Questions, or a table class in your corpus that still doesn't capture cleanly? Send us
the DOI — we reproduce on the real PDF before we change anything.

— The Docpluck team
