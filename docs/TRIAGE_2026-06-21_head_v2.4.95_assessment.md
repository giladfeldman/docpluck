# TRIAGE 2026-06-21 — corpus assessment at HEAD v2.4.95 (supersedes 2026-06-15)

**Method:** Full-document AI-verify of the **7 onboarded canary papers** (fixed-3 + 4 of the
rotating pool) at HEAD **v2.4.95**, rendered via `tools/render_for_audit.py` (I9 cache-check,
`provenance_ok`), compared by 7 independent in-session **Sonnet** verifiers (Claude Max Agent
tool, never the API) against the article-finder `reading` golds. This **replaces the clobbered
`AUDIT_DEFERRED_TO_AGENT` "PASS" verdicts** the pre-commit canary-audit hook had written into
run-meta (memory `feedback_canary_audit_clobbers_phase5d` — the clobber nearly masked a fully
broken corpus again).

**Result: 7/7 FAIL.** Standing run verdict: **FAIL** (rule 0e-bis; iterate-gate `--cycle 3`
FAILs on I3 only — correct). Every defect clusters into **3 architectural root causes, all
flagged "needs user sign-off" for weeks.** No clean non-architectural win remains — the 3 most
promising leads (plos_med masthead-strip, ip_feldman Table-10 splice, abstract-date weld) each
bottom out in one of the three.

---

## The 3 root causes, ranked by blast radius

### RC-T — TABLE-bbox extraction · S0 × C3 (ARCHITECTURAL — bbox decision open since 2026-05-22) · **WIDEST: all 7 papers**

The single most pervasive defect. Camelot/extraction produces tables that are empty shells,
garbled, header-stripped, duplicated, or polluted with adjacent body text — on **two-column AND
single-column** papers alike. Confirmed instances at HEAD:

| Paper | RC-T damage |
|---|---|
| `ip_feldman` (single-col) | Table 10 cells jumble running-header `Ip and Feldman` + page `15` + section heading `Discussion` + Discussion body-prose + 1 real row `Loneliness.29***−.21***.07`, all bbox `(0,0,0,0)` → render correctly drops `<table>`, leaving an orphan `### Table 10` heading; T4/T5 truncated (missing Self/Others/Well-being sub-rows) |
| `maier` (single-col) | T5 unstructured fallback (all descriptives lost); T7 garbled with body text; T8/T9/T11 empty column headers + section labels merged into data cells; Contributor-Roles flat text |
| `xiao` (single-col) | T7 + T8 emitted **twice** (HTML `<table>` + duplicate flat columnar dump); T8 HTML collapses all rows into one cell; tables out of reading order |
| `plos_med` | T4 holds T3 content + journal running-header as column headers; T5 empty shell (13 SAE rows missing) |
| `chandrashekar` (2-col) | T7/T8 empty shells; T9 holds T10 structure; T10 fragment; T3+T4 merged into one corrupt 2-col table |
| `chan_feldman` (2-col) | T1/3/4 unstructured fallback; T2 `1232 C.F.CHAN AND G.FELDMAN` page-header as column header; T8/T9 swapped schemas |
| `ar_apa` | full table data duplicated as raw prose before the HTML `<table>` |

**Why it's architectural:** the fix is a bbox-computation strategy for region-bounding tables so
Camelot stops grabbing furniture/adjacent prose and stops emitting orphan headings / duplicate
dumps. The "modified-Approach-B `whitespace_cells`" wiring shipped v2.4.72, but the **bbox
strategy itself has been an open decision since 2026-05-22** (`docs/superpowers/handoffs/2026-05-22-residual-after-locally-doable-pass.md` R1). **Needs user go-ahead on the bbox path.**

**Root cause characterized (cycle 4, 2026-06-21) — the FULL-PAGE-BBOX signature.** ip_feldman
Table 10's computed bbox is `(x0=52.99, top=52.91, x1=576.53, bottom=799.69)` — top≈53 to
bottom≈800 spans **essentially the whole of page 15** (`render=whitespace`, confidence 0.99999),
vs. Tables 1–9 whose bboxes are tightly-bounded sub-regions (e.g. Table 9 = top 471→bottom 671).
That full-page region is why T10's cells are the running header `Ip and Feldman` + page `15` +
the `Discussion` heading + Discussion body-prose + a single real row `Loneliness.29***−.21***.07`,
all bbox `(0,0,0,0)`. **The structural signature:** a structured table whose region bbox spans
(near) the full page, whose cells carry furniture/prose signatures (running-header pattern, a
section-heading word, sentence-shaped cells). **Caveat for the fix:** bbox-size alone is NOT a
safe discriminator — legitimate landscape Tables 6/7/8 also have tall bboxes; the guard must key
on **cell content** (furniture/prose), routing a degenerate region to a clean unstructured
fallback (no orphan `### Table N`, no prose-as-cells) rather than emitting a bogus `<table>`.

### RC-1 — Two-column / sidebar reading-order INTERLEAVE · S0 × C4 (ARCHITECTURAL) · two-column + sidebar papers

| Paper | RC-1 damage |
|---|---|
| `chan_feldman` (2-col) | spurious `## Background` wrapper demotes real `##` subsections to `###`; Original-hypotheses / Extension headings lost to body; journal banner + `2025, VOL. 39…` + `Article views: 206` leak before Abstract |
| `chandrashekar` (2-col) | Method/Participants reading order scrambled; affiliation lines inside `## Abstract`; Fig 4/5 captions injected mid-Discussion |
| `plos_med` (1-col + **sidebar**) | the entire PLOS front-matter sidebar (OPEN ACCESS / Citation / authors / 18 affiliations / Received / Accepted / Copyright / Data-Availability / Funding / Competing-interests / Abbreviations) is **interleaved into the body before the Abstract**; `## Abstract Published: December 28, 2023` welded (Abstract heading + sidebar pub-date). The furniture-strip is **defeated by the interleave**, not missing a pattern. |

**Spec exists:** `docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md` (Step-2
per-band region-aware crop). The existing `DOCPLUCK_COLUMN_CORRECT_GENERAL=1` Step-1 flag does
**not** fix these (Step-1 whole-page gutter crop is skipped on table-bearing/no-clean-gutter
pages — exactly these). **Needs user go-ahead.**

### RC-B7 — Deleted-minus glyph (silent sign-flip) · **ALREADY DONE (W0h) — no further work** · `ar_apa`

**RESOLVED 2026-06-21 (cycle 4): RC-B7 is already implemented and working.** The layout-channel
per-char recovery the old TRIAGE proposed *exists*: `normalize.recover_dropped_minus_via_layout`
(**W0h, R5/B7**), wired `render.py:5079 → sections → normalize.py:3170`, regression-tested
(`tests/test_dropped_minus_layout_recovery_real_pdf.py`). At HEAD v2.4.95 ar_apa renders
`b = -.022 / b = -.88 / b = -.428` — **4 of 5 betas signed correctly** (the layout channel
preserves the dropped U+2212 as an unmapped `(cid:2)` glyph in font `AdvP4C4E74`; W0h reads it
back). The cycle-3 "GLYPH FAIL" was a **verifier over-flag** (it quoted the W0h-recovered
`-.022`/`-.428` yet called them defects — the ~26% FP rate).

**Two OCR-tier residuals remain — genuinely outside docpluck's MIT text+layout architecture
(documented won't-fix, NOT fixable):**
- `.245` minus: drawn as painted pixels — absent from pdftotext AND pdfplumber chars/lines/rects.
- β→b (all 5): both pdftotext AND pdfplumber extract Latin `b` (font `AdvPSMP10`); only visual OCR
  sees β. A blanket `b→β` remap is FP-unsafe (some papers genuinely report unstandardized `b`).

The only *other* ar_apa divergence is `### Supplemental analyses` not promoted (rendered as body
prose) — the **single-column sentence-case heading-promotion class** (the same string is body text
in the abstract, so no reliable text-only signal; the cycle-3 caption-follows revert proved this
class is FP-prone). Distinct from the table/interleave work; not pursued.

---

## Resolved this cycle (NOT docpluck defects — closed)

- **`collabra_77859` "Table 3" vs gold "Table 2"** → **docpluck CORRECT.** Source text-channel
  caption (line 866) reads verbatim `Table 3. Study 4: Dish sets` (tables run 1→5 sequentially);
  docpluck + the consumer both call it Table 3. **The AI gold mis-numbered it** → gold error,
  surface to article-finder for correction.
- **`collabra_90203` (maier) Table 10 r=.59 vs .63** → **not deterministically fixable.**
  pdftotext literally emits `.59` (text-line 1706); Camelot agrees; docpluck faithfully reports
  the text layer. `.63` exists only in the visual glyph → source text-layer/visual divergence,
  needs OCR. Documented limitation.

## Verification-infra issues to surface (not library code)

- **canary-audit clobber (task_c678d4e6).** The pre-commit `_shared/iterate-loop/canary-audit.sh`
  wrote `AUDIT_DEFERRED_TO_AGENT → union PASS` for all 5 canaries at HEAD, clobbering the real
  verdicts. Without this cycle's manual re-verify, the corpus would read green. Portfolio-wide
  substrate bug; re-confirmed live this cycle.
- **Suspected gold-paraphrase false-positives** on `ar_apa` (verifier flagged word-substitutions
  "increased"/"improved", "not yell"/"yet feel") — likely the AI gold paraphrasing vs verbatim;
  reproduce-at-HEAD before ever actioning (cross-project R-0006, ~26% FP rate). NOT counted as
  docpluck defects pending reproduction.

## Proposed cycle order (user authorized "do all three, 1-3" on 2026-06-21)
1. ~~**RC-B7 glyph**~~ — **DONE (W0h, cycle 4)**; residuals are OCR-tier won't-fix. No further work.
2. **RC-T table-bbox** — widest blast radius (all 7 papers). NEXT focused effort. Implement the
   degenerate-region guard keyed on **cell content** (full-page bbox + furniture/prose cells →
   clean unstructured fallback). Multi-session; full 26-paper baseline + AI-verify; must not
   suppress legitimate landscape Tables 6/7/8.
3. **RC-1 region-aware columns** — Step-2 per-band crop (spec ready); two-column + sidebar. Riskiest.
4. Surface the `collabra_77859` gold mis-numbering to article-finder.
