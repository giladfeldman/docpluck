# docpluck scope

**Read this before building on docpluck's output.** It states what docpluck is for, and — more
usefully — what it is *not* for, so a consumer can tell a deliberate limit from a bug.

Introduced v2.4.128 (2026-08-13).

---

## THE SCOPE, IN ONE SENTENCE

> **docpluck extracts and normalizes ENGLISH-language science articles written in US numeric
> convention (`.` decimal, `,` thousands). We do not know how to handle European numbers, and we
> do not try: they are passed through EXACTLY AS PRINTED, unconverted.**

This is a **hard boundary set by the project owner (2026-08-14)**, not a tuning choice, not a
backlog item, and not a gap awaiting a fix. It is settled. If you are about to file "docpluck
doesn't convert `d = 0,45`" as a bug — that is this paragraph, working as intended.

**What we deleted to make that true** (v2.4.129): every EU→US conversion rule — `A3` (operator-gated
decimal comma), `A3c` (leading-zero decimal), `A3d` (leading comma) — and the whole document-level
numeric-locale inference (`infer_numeric_locale`, `NumericLocale`,
`NormalizationReport.numeric_locale`, `is_gating`).

**And what v2.4.130 (2026-08-14) deleted to finish the job** — three rules that repaired the
*paper* rather than canonicalising notation, plus the guard that existed only to serve them:

| rule | it did | why it is gone |
|---|---|---|
| `A2` | `p = 38.` → `p = .38.` | Repaired the AUTHOR's typo. Both firing sites in 297 English papers were the paper's own error, rasterized. No cited paper anywhere in its code. |
| `A3a` | `N = 1,182` → `1182` | Its only job was pre-empting `A3`, which is deleted. Produced 1000× errors on comma-decimal tables. Reported its metric as `thousands_separators_preserved` while stripping them. |
| `W0n` | `p < 05` → `p < .05` | Its premise — "a dotless threshold is provably corrupt" — is false. The same shape is the author's error in one real paper and our OCR loss in another; a layout gate to separate them was built and refuted. |

**Why, measured rather than assumed.** Over **297 English papers** from the custodian, the
conversion rules fired **10 times in 3 papers and not once correctly**: 8 corrupted mathematical
constraints, 1 laundered an author's copyediting error, 1 broke a URL. Meanwhile the locale
detector was **confidently wrong** on the one genuine European table ever found in an English paper
(`10.1177/0956797620935584` Table S2 — ~130 comma-decimal cells scored `european_markers=0`,
verdict `decisive_us`), because every marker it used required an operator and a table cell has
none.

**What this means if you consume docpluck:** a European decimal arrives verbatim. `d = 0,45` stays
`d = 0,45`. Deciding what it means is **yours**, and you are better placed to do it than we are —
you hold the parsed statistic and its context; we hold text. The source token is intact, so the
decision is still available to you. Once we had converted it, it was not.

### ✅ The 1000× error class is CLOSED (v2.4.130)

Earlier versions of this document warned that `A3a` stripped thousands separators and therefore
produced a **1000× error** wherever a paper used comma decimals — `10.1177/0956797620935584`
Table S2 prints a `df- satterthwaite` column of `185,178` (a Satterthwaite df is fractional; it
means 185.178) and we delivered `185178`.

**`A3a` is deleted.** A thousands separator now reaches you exactly as the paper printed it, and
the source token is intact, so you can still decide what it means. If you previously worked around
this by treating a suspiciously large integer in a statistic slot as a candidate 1000× error, that
workaround is no longer needed — but it is also harmless, because we no longer produce the input
it was written for.

**If you parse our output, you must now handle `1,182`.** `.replace(",", "")` in your layer is one
line and reversible; doing it in ours was irreversible and destroyed the only evidence that a table
was European. That asymmetry is the whole argument.

### ⚠ Where we ARE still lossy, and it is bigger than A3a ever was

**The render channel deletes content, and until v2.4.130 it did so with no telemetry whatsoever.**
`render_pdf_to_markdown()` chains 54 markdown post-processors — count it from the source with
`grep -c 'md = _step(' docpluck/render.py`, never from this sentence. **Twelve** of them can remove
lines rather than transform them (re-counted from source 2026-08-15; the figure previously written
here was "six", and an undercount in the inventory of deleting steps is exactly how a deleting step
goes unaudited). Measured on the baseline corpus at v2.4.129:

```
10.1017/s1930297500009189   an ENTIRE published-results sentence deleted
    "…(r(6) = 0.94, p < .001, 95% CI [0.71, .99]); and … (r(6) = 0.99, p < .001,
     95% CI [0.96, .99]). Hotelling's (1940) t indicated these correlations to be
     different from each other (t(5) = 4.66, p = .006)."
10.1001/jamanetworkopen.2023.48333   a hazard ratio and its CI deleted:  1.31 (1.20-1.44)
```

Two correlations, a Hotelling's *t*, three *p*-values and two confidence intervals — removed from a
meta-science pipeline with no count, no key in `changes_made`, and no log line. This ranked below
the numeric rules for three bad reasons, all recorded in `LESSONS.md` L-032: we audited where our
*vocabulary* was (notation-vs-repair is a framework about rewrites, and a deletion is not a
rewrite), we audited where the *instrumentation* was, and we ranked by the severity of the RULE
rather than of the OUTPUT.

**What v2.4.130 does about it:** the deleting steps now refuse to drop a line carrying statistical
content, and `render_pdf_to_markdown()` accepts an optional report so a deletion can be counted and
named. **What it does not do:** prove the class is closed. `tools/diag/render_deletion_scan.py` is
the gate; run it against your own corpus.

### ⚠ A CI whose upper-bound minus was fully dropped can be undetectable

**Declared here because nothing detects it and, until v2.4.134, no document said so** (register O6).

On some tight-kerned fonts pdftotext loses the leading U+2212 of a confidence interval's UPPER
bound while keeping the lower bound's, so a printed `[−0.78, −0.66]` arrives as `[-0.78, 0.67]`.
That result is **ascending, well-formed, and plausible**. Nothing about it is anomalous, so no
consumer validation can flag it — unlike a reversed interval, which announces itself.

docpluck recovers this class **only when it can prove the flip**, and there are two grades of
proof, which are now reported separately so you can tell them apart:

| `fallbacks` key | evidence | trust |
|---|---|---|
| `ci_upper_minus_reattached_from_detached_dash` | **typographic** — the renderer emitted a dash before the bound and the comma proves it is a sign, not a range separator | high |
| `ci_upper_minus_inferred_from_containment` | **inferential** — no glyph survived; only the estimate-containment arithmetic says the bound lost a minus | treat as a hypothesis |

**Neither key present does NOT mean the interval is sound.** When the estimate is absent, or when
containment cannot discriminate, docpluck leaves the interval exactly as extracted and says
nothing, because it has nothing to say. **A CI sign is not a verified quantity in docpluck's
output.** If your pipeline depends on interval direction, cross-check it against the estimate
yourself — you hold the parsed statistic and its context, and we hold text.

### ⚠ Known channel gaps, named rather than left silent

docpluck has three text channels (`normalize_text`, table-cell cleaning, the render post-process),
and a repair wired into two of them gives one input two answers. These are the gaps we know about as
of v2.4.134. They are pass-through or announced — none of them fabricates a value — but a consumer
should know where they are:

* **The detached CI-upper minus (W0q) is in 2 of 3 channels.** Body prose and table cells repair it;
  the render post-process does not, so a `raw_text` fallback block (a table Camelot could not
  capture, or a `DISABLE_CAMELOT` run) can still carry `[- 0.58, - 0.18]`.
* **The cross-cell variant repairs unevenly.** `_recover_ci_upper_in_grid_row` runs only inside
  `cells_grid_to_html`, so where the estimate and its CI live in SEPARATE cells the HTML and
  `flatten` are repaired while `cells[].text` / `raw_text` keep the dash.
* **`_drop_running_header_rows` protects tables with 3+ columns.** A two-column frequency grid can
  still lose a leading row, or have its counts blanked. Both now record
  (`cell_cleaning_running_header_row_dropped` / `_cell_blanked`), so the loss announces itself — but
  the step still does not consult a statistical-content guard.
* **A sign left at the end of a line with its digits wrapped to the next** is invisible to the
  already-signed guard, because these rules process one line at a time. No real paper exhibiting it
  has been found; pinned as a strict xfail so a future accidental fix is noticed.
* **A caption-anchored region can over-capture, horizontally AND vertically.** On a multi-column
  page a caption's bbox spans BOTH text columns (`_bbox_of_caption_line` groups chars by `round(top)`
  across the whole page), so the region absorbs the neighbour's body prose and the grid guards then
  reject the table. A fix was written and REVERTED in v2.4.134 because it cost a different paper a
  stat column (register §J14). Separately, a `caption_only`
  region (one where no table geometry was detected) still extends a fixed 250pt below the caption,
  so it can reach past the table's own note into the body text underneath. The prose guards catch
  the result and the grid is dropped rather than published as data, so this costs COVERAGE, never
  correctness: the table falls back to its `raw_text` block.
* **A wrapped table cell can land on its own row — in `cells`/HTML only.** Row clustering splits on
  the y-gap from the row's anchor, which keeps a continuation within one line pitch attached but
  separates one printed further down. A re-merge for that case was built and removed in v2.4.134
  because it chained (register §J4). **No value is lost, and the rendered table is correct.** The
  fragment survives the prose trim, and `cell_cleaning._merge_continuation_rows` rejoins it
  (`[0.12,` + `0.45]` -> `[0.12, 0.45]`).

  **Where it shows: `cells[]` only, and on EVERY capture path.** The merge runs inside
  `cells_grid_to_html`, i.e. at RENDER time, and inside `flatten` — so the `<table>` you read and
  the flattened records both carry `[0.12, 0.45]`, while the raw `cells[]` list still holds the
  unmerged `[0.12,` and a `0.45]` row. That is not specific to the whitespace path and is not new
  in v2.4.134; cells are built once and cleaned on the way out, so it has always been true of the
  Camelot path too. **If you consume `cells[]` directly rather than `html` or `flatten`, apply your
  own continuation merge or switch channel.** (An earlier draft of this bullet said the rendered
  `<table>` was affected as well. It is not — corrected 2026-08-19 by testing `cells_to_html`
  rather than reasoning about it.)
* **A table cell can be TWO PUBLISHED NUMBERS GLUED TOGETHER.** Camelot's column segmentation
  sometimes swallows a real inter-column gap, so `10.1177/01461672251327169` Table 3 ships `104594`
  — a sample size of 104 and one of 594 — and `10.1016/j.jesp.2009.12.010` Table 3 ships
  `4.603.804.80` for 4.60 / 3.80 / 4.80. Pre-existing Camelot behaviour, not introduced by any
  docpluck release, and **the worst class we ship by our own ranking**: the wrong value parses
  cleanly and nothing announces it. Where `cells[]` and `raw_text` disagree on a numeric value,
  **`raw_text` is the safer channel**. A detector needs the layout channel to prove the swallowed
  gap (register G6a/G6h). Measured today with `python tools/diag/fused_cell_census.py`: **34 cells,
  0.29% of 11,720, in 7 tables across 3 of 26 papers** — and that is a FLOOR, because two plain
  integers fused are indistinguishable from one six-digit number in text alone. The class is
  CONCENTRATED: one paper ships whole results tables of it.
* **`cells[].bbox` IS REAL NOW — but only where `Table["cell_geometry"]` says so** (new in
  v2.4.135). Every Camelot cell used to ship `(0.0, 0.0, 0.0, 0.0)`; they are now genuine
  pdfplumber-space rectangles `(x0, top, x1, bottom)`, the same convention the whitespace path
  already used. **Gate on the field**: trust the boxes when it starts with `verified` or equals
  `whitespace_native`; on `camelot_rotated_page:…`, `grid_shape_mismatch:…`,
  `roundtrip_failed:…` or `no_layout` the boxes are zeros because we refused rather than guess.
  We refuse because every way of getting this wrong yields coordinates that are *plausible and off
  by a page* — worse than none. Measured over 69 shipped tables: **81.2% verified, 5,206 of 5,686
  cells (91.6%) carrying a real box**; re-run with `python tools/diag/cell_geometry_census.py`.
  A verified bbox is the GRID RECTANGLE for that (row, column) — **not** a promise that
  `cells[i]["text"]` is exactly the text standing inside it, because Camelot assigns a whole text
  object to one grid cell even when its glyphs spill past that cell's column edges.
* **`table_prose_replacement_smaller_than_candidate`** — a NEW key. When a candidate was rejected as
  body prose and the replacement carries fewer populated cells, we record it rather than refuse the
  swap: smaller is usually correct (a grid half-composed of body prose loses those cells). Treat it
  as "look at this table" rather than as an error.

### The evidence axis, and what we will and will not decide for you

Every repair declares which kind of evidence it rests on:

* **TYPOGRAPHIC** — something the renderer actually put on the page: a surviving `(cid:N)` glyph,
  the font of *this* character, size and baseline, a backslash glued to a numeral. We act on these.
* **INFERENTIAL** — what a number *ought* to be given the others around it. This is your call, not
  ours: you hold the parsed statistic and a UI to flag it.

Two rule families sit on that line and the ruling is recorded here rather than left implicit
(register O8):

* **W0i / W0k / W0l** (`×` extracted as `3`) are **TYPOGRAPHIC**. The font genuinely mis-draws the
  multiplication glyph; the surrounding-token conditions only bound where we trust it.
* **W0j** (`_PROSE_MSTAT_CHANGE_RE`) is **INFERENTIAL** and is now labelled as such. It flips a
  sign keyed on a variable NAME (`Mchange`), and a name is not something the renderer emitted —
  `20.14` is not grammatically impossible in that slot, merely implausible. It is retained,
  narrowly scoped, and its firings are recorded; it is a candidate for retirement, and retiring it
  moves work onto you, so it is not being retired without notice.

Where we keep an inferential repair, it is **declared in `fallbacks`**, never silent. That is the
whole basis on which we keep any of them: the doctrine's reason for handing inferential judgement
to consumers was that docpluck had no channel to announce a guess, and that channel now exists.

---

## English-language science articles

docpluck extracts and normalizes **English-language academic articles**. That is the whole scope.

Consequences that are **deliberate, not defects**:

- Caption detection matches `Table N` / `Figure N` / `Fig. N`. It does **not** match `Tabela`,
  `Tabla`, `Tabelle`, `Tablo`, `Tableau` or `Tabel`. A non-English article will therefore yield no
  tables and no figures.
- Section detection keys on English headings (`Abstract`, `Method`, `Results`, `Discussion`,
  `References`).
- Running-header, footnote and furniture stripping is tuned to English-language publisher
  templates.

If you feed docpluck a non-English article it will still return text, and that text may look
reasonable. **Do not rely on it.** Nothing downstream of the raw text channel is validated for
non-English input.

### Why the boundary is drawn here, and why it matters more than it looks

The numeric-separator question — is `1,234` one thousand two hundred and thirty-four, or is it
1.234? — is genuinely hard *within English alone*, because English-language articles occasionally
carry a continental value (a table pasted from a comma-locale machine, a translated appendix, a
typo). docpluck resolves those on **structural** evidence: an operator in the value position, a
leading zero, bracket delimitation.

> **KNOWN LIMIT, measured 2026-08-14 — the structural evidence is operator-shaped, and a table
> cell has no operator.** `10.1177/0956797620935584` (Battal et al., *Psychological Science*)
> Table S2 is ~130 comma-decimal cells in an English-language paper, and every one of them is a
> bare cell. Two consequences:
>
> 1. `infer_numeric_locale()` reports `european_markers=0` on that document. The measurement
>    *"396 English articles → 0 European-locale"* below therefore describes the **reach of the
>    instrument**, not the absence of the convention.
> 2. `A3a` strips those cells' separators, turning a printed `df- satterthwaite` of `185,178`
>    (i.e. 185.178) into `185178` — a **1000× error on a published statistic**. Pinned in
>    `tests/test_a3a_known_wrong_european_decimal_table.py`; the remedy is a **local-window**
>    locale, not a document-level one.

What docpluck will **not** do is learn about that English problem from non-English articles. The
reason is concrete and was measured:

> Latin-American and Turkish journals publish **bilingual** articles — an English abstract over a
> native-language body. So a single SciELO paper contains `1,738 adult patients` (English
> abstract, a genuine thousands group) *and* `528,329` (Portuguese body, the decimal 528.329).
> A document-level locale verdict is therefore false for part of every such document.

Reasoning from those papers to English-article behaviour produces conclusions that are wrong in
both directions. So the corpus, the scans and the tests are all filtered to English, and any scan
that reasons about separators must report its language distribution and print what it excluded —
never drop it silently. The detector lives in `tools/diag/_language.py` and every scan that reads
text imports it (`non_statistic_corpus_scan.py`, `repair_site_scan.py`,
`render_deletion_scan.py`).

---

## What docpluck publishes about numeric convention: NOTHING, deliberately

**There is no `NormalizationReport.numeric_locale`.** Earlier versions of this document told
consumers to read that field instead of running their own inference. It was deleted in v2.4.129
along with `infer_numeric_locale`, `NumericLocale` and `is_gating`, and this section described a
field that no longer existed — a documentation defect of exactly the kind this project's first
rule forbids, since a consumer following it would get an `AttributeError`.

The field is gone because its verdict was **confidently wrong** on the only genuine European
table ever found in an English paper: `10.1177/0956797620935584` Table S2, ~130 comma-decimal
cells, scored `european_markers=0`, verdict `decisive_us`, confidence 1.0. Every marker it used
required an operator (`=`, `<`, `>`) immediately before the value, and a bare table cell has
none. So the measurement *"396 English articles → 0 European-locale documents"* described the
**reach of the instrument**, not the corpus.

**What replaces it: your own reading of an unmodified token.** Because nothing converts or strips
a numeric separator any more, the token you receive is the token the paper printed. That is
strictly more information than a verdict we computed for you — and unlike the verdict, it cannot
be wrong.

The marker vocabulary itself is **retained internally and unwired** (`tests/test_numeric_locale_markers.py`)
solely as the foundation for a future **LINE- or TABLE-scoped** guard. Never for another
document-level verdict: the bilingual problem above makes any whole-document answer false for
part of the document.

---

## Input formats

PDF, DOCX and HTML. See `docs/SYMBOL_CONTRACT.md` for the symbol conventions.

> ⚠ **The conventions apply identically across all three ONLY through `normalize_text()`.**
> This section previously said "which apply identically across all three", full stop. That was
> **false for the sections path** and had already been corrected in `SYMBOL_CONTRACT.md` on
> 2026-08-14 — the correction was made in the contract document and missed in the consumer-facing
> one, which is the document a consumer actually reads. Corrected here 2026-08-15.
>
> Concretely: `extract_sections()` on **DOCX and HTML** returns a field named `normalized_text`
> that holds the **raw reconstructed text** (`docpluck/sections/__init__.py:144` and `:159`) — the
> name is a promise the value does not keep. Only the PDF branch calls `normalize_text()`. If you
> consume `SectionedDocument.normalized_text` for DOCX or HTML, you are reading unnormalized text
> and must apply `normalize_text()` yourself. See `SYMBOL_CONTRACT.md` §KNOWN GAP.

---

## For consumer maintainers

If you are ESCImate/effectcheck, Scimeto/CitationGuard, citelink, MetaESCI, ScienceArena, or any
other consumer:

- **Assume English input.** If your corpus contains non-English articles, filter them before
  docpluck rather than after — the failure is silent, not loud.
- **Handle `1,182` and `0,45` yourself.** As of v2.4.130 we neither strip a thousands separator
  nor convert a decimal comma. `.replace(",", "")` in your layer is one line and reversible;
  doing it in ours was irreversible and destroyed the evidence that a table was European.
- **You may now run your own locale inference on our output, and you could not before.** The
  reason the old advice said not to was that `academic` had already turned every `d = 0,80` into
  `d = 0.80`, so a consumer inferring locale from our text was reading evidence we manufactured.
  That inversion is gone: separators reach you as printed.
- **`p = 38.`, `p < 05` and `p = 001` now reach you as printed.** These are the paper's own
  errors, not extraction damage — all verified by rasterizing the page. Detecting and flagging
  them is your job, and you are better placed to do it: you hold the parsed statistic and its
  context. Build the detector before you upgrade.
- **Do not hard-code a copy of our symbol tables.** Read `docpluck.symbol_contract()`.
- **If you render to markdown, pass `_report=RenderReport()`** and check
  `report.statistics_removed`. It should always be empty; if it is not, that is a docpluck bug
  and we want the DOI.

A limit you discover that is not written down here is a documentation bug — please report it.
