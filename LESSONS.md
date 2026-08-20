# Docpluck — Lessons (incident log of recurring mistakes)

**Purpose.** When a Claude session (or human contributor) keeps re-discovering the same painful conclusion, write it here so the next session reads it FIRST and skips the wasted iteration.  Each lesson must be: (1) the surface problem, (2) the failed-fix attempt that taught us, (3) the correct rule.

**Read this file before touching `docpluck/extract*.py`, `docpluck/normalize.py`, or `docpluck/sections/`.**

---

## L-001 — Never swap the PDF text-extraction tool as a fix for downstream problems

### The recurring mistake

A real-world paper looks bad in `extract_sections()` output (column interleaving, running headers in body, abstract not detected, etc.).  The seemingly natural fix: "pdftotext is producing messy text; pdfplumber's text looks cleaner; let me swap the source."  That's wrong, and we have learned it the hard way at least three times:

- **v1.6.0 era:** PDF section path used `extract_pdf_layout` (pdfplumber).  Some heuristics shipped that depended on that text format.
- **v1.6.1:** Simplified to plain pdftotext.  60+ heuristic patterns and ~250 unit tests got tuned to pdftotext's output: word boundaries, line wrapping, page breaks, paragraph spacing, "Methods\n" vs "Methods " behavior.
- **2026-05-09:** While fixing a real-world Brick et al 2021 Collabra paper that had `"Downloaded from http://online.ucpress.edu/... by guest on 03 June 2021"` watermarks leaking into body sections, a Claude session reasoned: "the layout-aware F0 step in `normalize.py` would strip these — let me wire `extract_pdf_layout` into `extract_sections` so F0 fires."  In a single change:
  - Sections detection failed on every Nature paper (10/10 hard fail).
  - Sections detection failed on every AMA / JAMA paper (10/10 hard fail).
  - APA went from 17/18 PASS to 7/18 PASS.
  - Total: **60+ corpus papers regressed in one commit**, all because pdfplumber's text formatting (word spacing, line breaks, multi-column reading order) does not match the format the heading regexes were tuned for.

The session reverted within 30 minutes.  This is the third time.

### The rule

**The TEXT channel is `extract_pdf` (pdftotext, default mode).  Do NOT replace it.**  Every downstream consumer that reads text content (sections, normalize, batch, statistics extraction) is calibrated against pdftotext's output.  The taxonomy variants, heading regexes, paragraph-detection heuristics, watermark patterns, and section-synthesis logic are all empirically tuned to that format.

If a real-world paper has bad output:

1. **Identify which layer owns the issue.**
   - Watermarks / running headers in body → `normalize.py` `_WATERMARK_PATTERNS` (W0 step).
   - Heading not detected → `docpluck/sections/annotators/text.py` (regex tweak) OR `docpluck/sections/taxonomy.py` (canonical variant).
   - Abstract bloat / synthesis → `docpluck/sections/core.py` (Pattern E synthesis).
   - Numbering prefix not stripped → `docpluck/sections/taxonomy.py` (`_NUMBERING_PREFIX`) and `annotators/text.py` (`_NUM_PREFIX_FRAG`).
   - Page-boundary artifacts → `normalize.py` W0 patterns or S9 repeat-line strip.
2. **Fix in that layer with a precise pattern that targets the artifact.**
3. **Test against the existing corpus** (tests/test_sections_*.py + the per-style PDF corpus regrade) before declaring the fix done.

The LAYOUT channel (`extract_pdf_layout`, pdfplumber) is for geometric / positional information consumed by tables, figures, and the F0 layout-aware strip when called explicitly.  It is NOT a substitute text source.

### Architecture rule of thumb

| Need | Channel | Module |
|---|---|---|
| Reading-order linear text | `extract_pdf` (pdftotext default) | `docpluck/extract.py` |
| Per-character font / position / page geometry | `extract_pdf_layout` (pdfplumber) | `docpluck/extract_layout.py` |
| Tables (cell bboxes, column geometry) | `extract_pdf_layout` only | `docpluck/tables/` |
| Figures (image bboxes) | `extract_pdf_layout` only | `docpluck/figures/` |
| Sections, normalize, batch | `extract_pdf` only | `docpluck/sections/`, `normalize.py`, `batch.py` |
| `extract_structured` (combined) | both, as separate channels | `docpluck/extract_structured.py` |
| Layout-aware running-header strip (F0) | both: text in, layout for span lookup | `normalize.py::_f0_strip_running_and_footnotes` |

`extract_structured` is the canonical example of how to use both channels correctly: text from pdftotext drives the `text` field; layout from pdfplumber drives the `tables` / `figures` fields; the channels do not mix.

### Open-source pdfplumber as reference material (NOT runtime swap)

pdfplumber (MIT-licensed) has good algorithms for column detection, reading-order clustering, and word grouping.  When docpluck needs to handle a layout pdftotext mishandles (e.g. tightly packed two-column papers where pdftotext interleaves), the strategy is:

- **Study pdfplumber's algorithm** (`pdfplumber/page.py`, `extract_text` / `chars_to_textmap`).
- **Re-implement the relevant column-detection / clustering logic** in docpluck (we already pull pdfplumber as a transitive dep via the layout module, so we can call it directly when we want).
- **Apply it as a per-paper fallback** when default pdftotext output looks broken (e.g. dense column interleaving detected via heuristic).
- **Credit pdfplumber** in code comments and `docs/DESIGN.md` whenever its algorithms are ported.

What we do NOT do: swap the default text source.  The fallback is conditional and the calibrated pdftotext path remains the default.

### Verification when adding a real-world-paper fix

After any normalize.py / sections/ change that targets a real-world paper artifact:

1. Run `python -m pytest tests/test_sections_*.py tests/test_normalization.py -q` — must stay green.
2. Run the full per-style corpus regrade (see `docs/superpowers/plans/sections-issues-backlog.md` "How to verify" section).  PASS + PASS_W count must not drop materially.
3. If a regression appears, **do not chase it across layers** — revert and diagnose the root cause first.

---

## L-002 — Never use `pdftotext -layout` flag

**Surface:** "Default pdftotext is interleaving columns; let me try `-layout` mode."

**Failure mode:** The `-layout` flag preserves physical column geometry by inserting whitespace, which makes statistical pattern matching break across the corpus.  Two-column papers come out as side-by-side text that's even harder to parse.

**Rule:** `extract_pdf` runs pdftotext WITHOUT `-layout`.  This is enforced in `docpluck/extract.py:13–16`.  Do not regress this.

---

## L-003 — Never use `pymupdf4llm`, PyMuPDF (`fitz`) `column_boxes()`, or other AGPL-licensed PDF tools

**Surface:** "`pymupdf4llm` has nice column handling out of the box; let me add it as a dep."

**Failure mode:** The licensing on pymupdf / pymupdf4llm is AGPL.  Including it in docpluck pollutes the SaaS service (PDFextractor app) which is a closed-source authenticated product.  The docpluck library is MIT and must stay AGPL-free.

**Rule:** Only MIT / BSD / Apache-2 / similar permissive PDF libraries.  pdfplumber (MIT) is the only PDF library currently allowed alongside pdftotext.

---

## L-004 — Always normalize Unicode MINUS SIGN (U+2212) → ASCII hyphen

**Surface:** Statistical patterns like `f = -0.35` fail to match in the regex tier even though the text "looks right."

**Failure mode:** Many academic PDFs render minus signs as U+2212 MINUS SIGN, not U+002D HYPHEN-MINUS.  Regex `[-]` matches only the ASCII hyphen.

**Rule:** `normalize.py` step S5 maps U+2212 → `-`.  Do not regress.  If you add new statistical regex patterns, test on a paper that contains U+2212 minuses (most APA replication papers do).

---

## L-005 — Test on APA / replication-report papers, not ML / engineering papers

**Surface:** "Let me check this normalize change on the IEEE Access PDF I have lying around."

**Failure mode:** ML / engineering papers have tables full of performance metrics (`F1 = 0.85`, `loss = 0.123`) that look like statistical results to the academic-norm pipeline, generating false positives that mask real failures.

**Rule:** Use the APA / Cambridge JDM / Collabra Psychology / IRSP replication-report corpus when validating normalization changes.  IEEE / engineering / Nature CS papers can come later as a stress test, after the psychology baseline is solid.

---

## L-006 — Use Camelot (`flavor="stream"`) for table cell extraction; pdfplumber is unsuitable

**Surface:** "Tables in our markdown output look unreadable. pdfplumber's `extract_tables()` returns `cells: []` for whitespace-aligned tables (the entire APA corpus). What library should we use?"

**Failure mode (the temptation):** Try harder with pdfplumber. Tune `text_x_tolerance`, switch `vertical_strategy` to `text`, write a custom word-cluster algorithm on top of `extract_words()`. After a 2026-05-09 5-way bake-off — pdfplumber `extract_tables(text)` (Option A), pdfplumber `extract_words` + custom column-cluster (Option B), pdfminer.six word-bbox (C), Camelot stream (D), real Poppler `pdftotext -bbox-layout` + custom clustering (E) — every pdfplumber-based approach failed on either the simple case (column merging, words concatenated like "Usingamouse") or the side-by-side landscape case. **pdfplumber's table extraction is fundamentally bad for APA whitespace tables and tuning won't fix it.**

**The rule:**

- Use **Camelot `read_pdf(..., flavor="stream")`** for table cell extraction. Stream flavor needs no Ghostscript (lattice flavor does). Camelot accuracy: ~97–99% on APA stats matrices, no per-paper tuning.
- pdfplumber is dropped from docpluck's table pipeline. It remains a transitive dependency only as long as it's pulled in elsewhere; the goal is to remove it entirely.
- This **supersedes the "pdfplumber-only" constraint in L-003**. Permissive license rule still holds: Camelot is MIT.
- License check: Camelot is MIT-licensed (atlanhq/camelot). Confirmed compatible with the closed-source SaaS PDFextractor app.
- If Camelot returns one wide table for a side-by-side landscape layout (it merges them — e.g., ziano Table 1), that's a known limitation. Post-process to split if needed; do NOT abandon Camelot for this.
- Don't try Option E (real Poppler `pdftotext -bbox-layout` + custom clustering) thinking you'll do better than Camelot. The 2026-05-09 spike confirmed the input data is excellent but rebuilding what Camelot already does is multi-week algorithm work for zero quality gain.

**Evidence trail:**
- Experiments at [`docs/superpowers/plans/spot-checks/splice-spike/experiments/`](./docs/superpowers/plans/spot-checks/splice-spike/experiments/) (commit `a3cc72a`).
- 8 sample `.md` outputs across 5 options × 2 papers (korbmacher 4×8 stats matrix, ziano landscape side-by-side).
- [`COMPARISON.md`](./docs/superpowers/plans/spot-checks/splice-spike/experiments/COMPARISON.md) summarizes the bake-off and recommendation.

**The "PyMuPDF would also be nice" question:** PyMuPDF / `fitz` is AGPL — see L-003. It is permanently excluded.

**Date:** 2026-05-09.

### Addendum (same date): HTML tables inside Markdown, not pipe-tables

After seeing pipe-table vs HTML rendering side-by-side on real complex tables (korbmacher Table 1 with Easy/Difficult group separators + multi-row headers; ip_feldman Table 2 with multi-line hypothesis cells), the user decided that **all tables in the .md output are rendered as HTML `<table>` blocks**, not Markdown pipe-tables. CommonMark allows raw HTML inline, so all renderers handle this correctly.

Reasoning: pipe-tables cannot represent merged cells, multi-line cells, group-separator rows, or multi-row headers, and most academic tables have at least one of these features.

The renderer (`pdfplumber_table_to_markdown` — keeping name for API stability) emits HTML with these features:
- Continuation rows (col 0 empty + prose elsewhere) merge into the previous row's cell with `<br>`.
- Col-0 wrap detection (prev row's col 0 ends with `/`, `-`, `—`, `–`) merges col-0-only continuation rows into that cell.
- Group separator rows (only first cell, ≥3-col table, ≥3-char label with letters) emit as `<tr><td colspan="N"><strong>label</strong></td></tr>`.
- HTML special chars escaped; `<br>` placeholder is escape-safe.

Section headings (`## Heading`, `### Table N`) and italic captions (`*caption*`) remain Markdown.

Demo showing the difference: `docs/superpowers/plans/spot-checks/splice-spike/html-fallback-demo.md`.

---

## L-007 — Layout span text MUST reinsert inter-word spaces from the x-gap (never `"".join(chars)`)

### The recurring mistake
When a downstream step rebuilds text from the **layout channel** (`extract_pdf_layout`
→ `TextSpan.text`), it is tempting to construct a line's text by concatenating
pdfplumber's per-character `chars`: `"".join(c["text"] for c in line)`. This is wrong.
pdfplumber's char stream **does not carry the inter-word space glyph** on tight-kerned
PDFs (Cambridge journals, many two-column layouts) — pdftotext *infers* those spaces
from the horizontal gap, but the raw chars do not. So the naive join glues whole lines
into one token (`CNSSpectrums`, `Thebehavioralhealthcarecontinuuminthe`).

### What it broke (2026-06-13, v2.4.86)
`extract_layout._chars_to_spans` built span text with the naive join. Since v2.4.83 the
F0 step (`normalize_text(..., layout=...)`) rebuilds the **body** from spans, so on
~16 of 30 real biomedical PDFs the body collapsed to space-ratio ~0.005 (vs ~0.13 via
pdftotext) — token-F1 ≈ 0.00 against the JATS gold *with a normal character count*.
The defect was invisible to char-ratio/word-delta metrics (the chars are all there;
only the spaces are gone) and was surfaced by ScienceArena's `pdf-text-fidelity-v1`
held-out PMC set, where raw pdftotext beat docpluck. The function's own docstring even
*claimed* x-gap handling that had never been implemented.

### The rule
- Any reconstruction of text from layout chars MUST reinsert a space when the
  horizontal gap between consecutive glyphs exceeds a **font-relative** threshold
  (`gap > 0.20·font_size` reproduces pdftotext/JATS spacing to ~0.2% space-density).
  Use `extract_layout._join_chars_with_spaces`; never `"".join(chars)`.
- This is the in-repo instance of memory `feedback_pdfplumber_extract_words_unreliable`
  ("always carry a char-level absolute-x-gap fallback"). It applies to span text, and
  to any future layout-channel text reconstruction (sections annotators, tables).
- **A space-density collapse is the canary.** When a layout-derived body has space-ratio
  far below the pdftotext text for the same PDF (e.g. < 0.05 vs ~0.13), suspect glued
  word boundaries before anything else — it is not "dropped text."
- Architecturally, the body is sourced from `extract_pdf` (pdftotext, which already has
  correct spaces AND correct column reading-order) and the layout channel is used only
  to *identify* lines to strip (running headers / footnotes), per L-001's
  text-channel/layout-channel split. **Done in v2.4.87** (`NORMALIZATION_VERSION`
  1.9.34): `_f0_strip_running_and_footnotes` no longer rebuilds the body from spans — it
  builds strip-key sets from the span classification and deletes the matching lines from
  the pdftotext `raw_text`, keeping the rest in pdftotext order/spacing. This closed the
  residual two-column interleaving (`how www.cambridge.org/cns we can pay for it`) that
  the v2.4.86 spacing patch left behind, and lifted the held-out PMC token-F1 mean
  0.745 → 0.776 (primary 0.559 → 0.666). The F0 body is now provably a line-subsequence
  of the text channel (guarded by
  `tests/test_normalize_f0_footnote_strip.py::test_f0_body_is_a_line_subsequence_of_the_text_channel`).
  Rebuilding the whole body from spans is the smell that made the gluing bug possible; do
  not reintroduce it.

Cite: `docpluck/normalize.py` (`_f0_strip_running_and_footnotes`),
`docpluck/extract_layout.py` (`_join_chars_with_spaces`),
`tests/test_normalize_f0_footnote_strip.py`, `tests/test_extract_layout.py`,
CHANGELOG 2026-06-13 (v2.4.86 spacing, v2.4.87 body-source).

---

## L-008 — Temp-file cleanup must be best-effort; a broad `except` around extraction will swallow a cleanup error into total silent failure

### The recurring mistake
A function writes input to a `NamedTemporaryFile(delete=False)`, runs an external
library, and unlinks the temp file in a `finally` block. The caller wraps the whole
call in `except Exception: return []`. If the unlink raises, the exception escapes the
`finally`, the caller's broad `except` swallows it, and the **successful** extraction
result is discarded — a total, silent, output-zeroing failure that looks like "the
tool found nothing."

### What it broke (2026-06-13, v2.4.88)
`tables/camelot_extract.py::extract_tables_camelot` unlinked its temp PDF in a
`finally`. Under **camelot-py 2.0.0 on Windows**, Camelot still held the file handle
open, so `Path(tmp_path).unlink()` raised `PermissionError [WinError 32]`. The
exception propagated into `extract_structured`'s `except Exception` →
`camelot_failed`, `tables=[]` — so **every** paper lost **all** tables on Windows even
though Camelot had extracted them fine. POSIX allows unlinking an open file, so
prod/Linux/Railway never saw it; it was invisible outside Windows dev and only caught
by the corpus render verifier (tag H, 4 tables → 0).

### The rules
1. **Temp-file cleanup is always best-effort.** Wrap `unlink`/`rmtree` of a temp path
   in `try/except OSError: pass` (or use a tempdir context that tolerates it). A
   failure to delete scratch is never worth failing — or silently zeroing — the real
   result. The OS temp dir reclaims it.
2. **A platform-specific cleanup failure is invisible on the platform you test prod on.**
   POSIX `unlink`-while-open succeeds; Windows refuses. If extraction works in CI/Linux
   but returns empty locally on Windows (or vice-versa), suspect a `finally`-block
   cleanup raising under a held file handle before suspecting the extractor.
3. **A broad `except Exception` around a subprocess/library call hides this class.**
   When such a wrapper exists, the inner function must not raise on cleanup — otherwise
   "tool failed, 0 results" silently conflates real failure with a cosmetic cleanup error.
4. **Pin breaking-major dependencies.** The drift to camelot-py 2.0.0 came through the
   unbounded `camelot-py[cv]>=0.11.0` pin. Settled-on deps should carry a tested upper
   bound (see memory `feedback_no_silent_optional_deps`); a major bump is opt-in + re-verified.

Cite: `docpluck/tables/camelot_extract.py` (`extract_tables_camelot` `finally`),
`docpluck/extract_structured.py` (the broad `except`), `tests/test_camelot_temp_cleanup.py`,
CHANGELOG 2026-06-13 (v2.4.88).

---

## L-009 — A library feature is not "delivered" to a consumer until it is reachable over the surface they actually call; and table-FLATTEN quality is bounded by table-CAPTURE

### The recurring mistake

Two mistakes, both surfaced 2026-06-18 by ESCImate `REQUEST_10`:

1. **"Built ≠ reachable."** docpluck shipped `flatten_tables_for_paper` / `extract_pdf_structured` / `extract_sections` in v2.2.0 *for* the stat-verification consumers (the `flatten.py` docstring names effectcheck/escimate/scimeto) — but the hosted `/api/extract` endpoint those consumers call only ever returned `{text, metadata, normalization, quality}`. The capability sat unreachable for months. A feature added for a consumer must be exposed over the consumer's actual call surface (and documented in `API.md`) in the same effort, or it is invisible.

2. **Flatten quality is downstream of capture.** When asked to "make PROSECCO Table 2's 5 missing rows appear," the tempting read is "fix the flattener." Grounding first (dumping `extract_pdf_structured(pdf)["tables"]`) showed only **1 of 3** data rows reached `flatten` — so the fix belonged in the capture layer, not flatten. No amount of flatten work can surface a row Camelot never emitted.

3. **Re-ground even WITHIN the layer you've localized to — the first capture-layer hypothesis was also wrong.** The Tier-2 spec (written from the captured docpluck `Table`) asserted "Camelot's stream parser drops the rows / they're orphaned labels needing layout-channel synthesis." Dumping the **raw per-flavor Camelot output** (`camelot.read_pdf(pages="9", flavor=...)`) disproved it: **stream captured every row** (but lost the header text and vertically split each value from its parenthetical), **lattice had clean headers but only the ruled-box rows**, and `_pick_best_per_page` discarded the fuller stream table. The real fix (v2.4.94) was a cross-flavor merge + numeric-continuation merge — NOT orphaned-label synthesis. Lesson: localizing to "the capture layer" is not the root cause; inspect the *rawest* artifact (each flavor's df + bbox + row y-bands) before designing the fix.

### The rules

1. **Expose-where-called.** Surfacing an already-built library capability is HTTP-layer + serializer work in the app repo; do it behind an opt-in, default-OFF param so existing callers are byte-identical, and document the param + response fields + default in `API.md`. (REQUEST_10 modes A/B; `REPLY_FROM_DOCPLUCK_v2.4.93.md`.)
2. **Ground table fixes in the rawest artifact.** Dump `extract_pdf_structured(pdf)["tables"]` first; if the target rows are absent, drop one level further and dump each Camelot flavor's raw `df` / `_bbox` / `rows`. The fix locus (flatten vs. flavor-selection vs. continuation-merge vs. region detection) is only knowable from that rawest view — a plausible mid-layer hypothesis (here, "orphaned labels") can be flatly wrong.
3. **v2.4.93 flatten fixes** (combined `est_ci` columns, dash-sign CI, parallel ITT/PP groups) flatten every row Camelot captures. **v2.4.94 Tier-2** (cross-flavor lattice-augmentation + numeric-continuation merge) makes capture deliver the rows: PROSECCO R1–R6 now flatten sign-correct. Gated hard (equal-col-count + bbox overlap + extends-below; fragment-cell + column-aligned) so the 100-PDF / 2000-test corpus is regression-free.

Cite: `docpluck/tables/camelot_extract.py::_augment_lattice_with_stream_rows` + `docpluck/tables/cell_cleaning.py::_merge_continuation_rows` (v2.4.94), `docpluck/tables/flatten.py` (v2.4.93), `tests/test_camelot_lattice_augment.py`, `tests/test_tables_cell_cleaning.py`, `tests/test_tables_flatten.py`, `REQUEST_10_TIER2_ORPHANED_LABEL_ROW_RECOVERY.md` (root cause corrected), CHANGELOG v2.4.93–v2.4.94.

---

## L-010 — A caption that starts a page is mis-paged by the `^\s*` form-feed; and a font with no ToUnicode makes its glyph unrecoverable (recover the column ROLE, not the glyph)

### Two findings, both surfaced 2026-06-25 by the ESCIcheck handoff

1. **The `^\s*` caption regex eats the `\f` and mis-pages a page-starting table.**
   `TABLE_CAPTION_RE` / `FIGURE_CAPTION_RE` begin `^\s*`. When a table starts a new
   page, pdftotext emits `…results\n\fTable 4. …`, and `\s*` consumes the `\f`, so
   `m.start()` lands *before* the form-feed. `_page_for_offset` then counts the
   caption on the page BEFORE the break (off-by-one), and `_line_at` returns the
   empty pre-`\f` segment (so `line_text == ''`). With the wrong page,
   `_bbox_of_caption_line` can't find the caption in the layout channel → the whole
   layout-region lookup returns None → the whitespace/char fallback never fires and
   the table degrades to a caption-only stub. On `collabra.77859` this hit **all 5
   tables**. The seemingly-obvious fix — advance `char_start` past the leading `\f`
   to the actual "Table"/"Figure" token (`captions.find_caption_matches`) — DOES
   correct the page AND unblock `collabra.77859` Table 4's replication stats (DP-1) in
   isolation. **It was tried 2026-06-25 and REVERTED.** Populating the
   previously-empty `line_text` re-scores `_find_caption_for_table`'s same-page
   token-overlap and surfaces low-quality whitespace tables, so the mandatory AI-gold
   canary verify caught it mis-pairing tables whose captions share a page (efendic
   T4/T5, cog_emo T8/T9 swapped) and only half-fixing plos_med. **The lesson is the
   process, not the patch:** a capture-path change that helps one paper in isolation
   can silently mis-pair others — only a corpus-wide AI-gold verify (NOT the unit
   suite, which stayed green) reveals it. The real fix needs same-page-caption
   disambiguation in `_find_caption_for_table` + whitespace-region quality gating
   FIRST; queued as its own gated cycle. Symptom to watch: `line_text == ''` on a
   caption, or a caption whose `page` is one less than where the table visibly is.

2. **A glyph with no ToUnicode mapping is gone from BOTH channels — recover its
   ROLE, not the glyph.** `collabra.90203` reports `η²p`, but `pdffonts` shows the
   symbol font as `uni: no` (no ToUnicode CMap), so pdftotext AND pdfplumber both
   decode the glyph as U+0020 — the text reads `( = .000, …)` and the table's
   effect-column header is blank. This is the same class as the residual deleted-minus
   (memory `project_docpluck_rc_b7_done_w0h`): the *character identity* is absent from
   the PDF, so text-channel recovery is **OCR-tier won't-fix**. But in a TABLE the
   column's *role* is recoverable from structure — an F-test/ANOVA results table that
   reports a Bayes factor + CI and names no competing effect reports η²p by APA
   convention — so type the value `eta2` from the structural signature (range-guarded
   to η²'s `[0,1]` domain) even though the glyph is unrecoverable
   (`flatten._infer_anova_eta2_hint`). Don't chase the glyph; recover the meaning.

### The rules

1. **A caption-page / capture-path change MUST be AI-gold-verified across the corpus
   before shipping — the unit suite will not catch a mis-pairing.** The page-fix kept
   all 1852 unit tests green yet swapped table↔caption pairings on 3 papers. Per the
   project ground-truth rule, render the canary set and compare TABLES against the AI
   `reading` golds; revert if any paper regresses. (`^\s*`-anchored scans that skip
   `\f` ARE the right idea for page attribution, but the downstream `line_text` /
   same-page-caption scoring must be made robust in the same change, not after.)
2. **Before "the symbol got stripped", run `pdffonts`.** If the glyph's font is
   `uni:no`, nothing in the byte stream carries its identity — stop trying to recover
   the glyph; recover the column's role/meaning from structure, or mark it OCR-tier.
   (Shipped: `flatten._infer_anova_eta2_hint` types the value `eta2` from the F-test
   table structure even though the η²p glyph is gone.)
3. **A self-labeled cell beats its column header.** `r = .67` / `d = 0.32` states its
   own type; type by the cell token even under a generic "Effect size" header
   (`flatten._inline_stat_field`, shipped) — store only the numeric part so the
   sentence assembler doesn't double the prefix (`r = r = .67`).

Cite (SHIPPED v2.4.4): `docpluck/tables/flatten.py::_infer_anova_eta2_hint` +
`_inline_stat_field`, `docpluck/tables/cell_cleaning.py::_is_fragment_cell` (bracket-CI
tail). REVERTED (queued): the `captions.find_caption_matches` char_start advance +
`whitespace._whitespace_grid_is_clean` / `_trim_trailing_prose_rows` gates.
See CHANGELOG v2.4.98. (The originating triage doc is internal — see L-011.)

---

## L-011 — This repo is PUBLIC; internal working material must never be tracked here

**Surface:** On 2026-08-06 the user noticed `github.com/giladfeldman/docpluck`
was serving a large volume of internal `.md` files to the world. A scan found
**259 tracked internal files**: cross-project correspondence with downstream
consumers (`REPLY_FROM_*`, `REQUEST_*`, `CUSTOMER_UPDATE_*`), 98 session
handoff / findings / triage logs, 123 `docs/superpowers/` plans, specs and
spike outputs, 23 `.claude/` agent-skill definitions, and the backlog. They
leaked absolute local filesystem paths, the **private** app repo's internals,
unreleased plans, and other projects' architecture. No credentials leaked.

All 259 were purged from the full history (478 commits, 126 tags) with
`git-filter-repo` and force-pushed; commit *messages* were redacted in the
same rewrite.

**Why it happened — the part worth remembering.** The cleanup skill had a
`.gitignore` audit and had passed over these files repeatedly without flagging
them, because:

1. **It scanned for known-bad filenames.** A denylist cannot catch a category
   that should not exist — the next `HANDOFF_2026-09-01_*.md` is a new name the
   old rule never matched. The fix is an **allowlist**: assert every tracked
   path is on the list of what may be public, and treat anything else as a
   failure. Denylist thinking is why three cleanups reported "clean".
2. **It named these files as things to PRESERVE** — the checklist literally
   said "ASK before deleting these — they are intentional cross-project
   communication" and "NEVER delete spec/plan files … historical record". Both
   are true and both are irrelevant: **preserve ≠ publish.** Keep the content
   somewhere private; keep it out of the public repo. A rule written to prevent
   data loss silently authorized data exposure.
3. **`.gitignore` had per-file entries**, added reactively one at a time
   (`REQUESTS_FROM_ESCIMATE.md`, two specific spec paths). Each was correct and
   none generalized. Ignore rules must be **categorical**.

**Rules:**
- Only the library, its tests/tooling, CI, and the public doc set
  (`README`, `docs/README`, `docs/DESIGN`, `docs/NORMALIZATION`,
  `docs/BENCHMARKS*`, `CHANGELOG`, `LICENSE`) may be tracked here. Everything
  else under `docs/` is internal by default. `CLAUDE.md` and `LESSONS.md` are
  public by explicit user decision (2026-08-06).
- **`git rm --cached` is only half a fix.** It cleans the tip; the file stays
  readable at every prior commit and tag on GitHub. Never report an exposure as
  "removed" when only the tip changed — say plainly that a history rewrite is
  required, and that clones/forks will break.
- **Commit messages leak too** — they cite purged filenames, other projects,
  and local paths. Redact them in the *same* rewrite (`--replace-message`); a
  second pass means a second force-push.
- **A secret found in a public repo must be ROTATED, not just purged.** A
  history rewrite does not un-leak a key that was already public.
- Before any rewrite: `git bundle create ../backup.bundle --all`. After: verify
  zero internal paths in `git log --all --name-only`, all tags resolve, every
  kept file's blob SHA is unchanged, and the test suite passes.
- **Verify against a fresh `--mirror` clone of the REMOTE, not the local repo.**
  The local repo is what you just rewrote; it cannot testify about what GitHub
  still serves. This is how the survivors below were caught.
- **A force-push does not clean everything.** Three server-side survivors:
  **(1) stale remote branches** — 4 existed here, all fully merged into main, all
  still serving every purged file until deleted; **(2) `refs/pull/N/head`** —
  GitHub PR refs that **git cannot delete and force-push does not touch**. A
  merged PR pins its original commits forever and their blobs stay readable at
  `/blob/<sha>/<path>` and via the API. A *mirror* clone reveals them; a normal
  clone does not, so a normal clone falsely reports CLEAN. **Only GitHub Support
  can purge them.** **(3) forks** — separate repos a rewrite never reaches.
  On 2026-08-06 `main` + all 126 tags came back clean while `refs/pull/1/head`
  still served 126 internal files, `TODO.md` among them — verified readable.
  Cleaning main and the tags but leaving a PR ref is **PARTIAL**, not done.

**Known accepted residue** (deliberate, re-stated every run so it stays conscious):
`.github/workflows/bump-app-pin.yml` names the private app repo because it must
push a pin bump there; `tests/test_metaesci_followups.py` and
`tests/test_request_09_reference_normalization.py` embed a downstream
consumer's name in public test filenames.

Cite: `.gitignore` (categorical block + rationale header), `/docpluck-cleanup`
**Section 0 — PUBLIC-REPO EXPOSURE GATE** (blocking, allowlist-based),
`tests/test_canary_provenance.py` (must SKIP when the untracked `canary.json`
is absent, not error at collection).

---

## L-012 — Four ways this repo told the truth in a docstring and a lie in the call graph

**Origin (2026-08-07, MetaESCI `INBOX_FROM_METAESCI_2026-08-07.md`).** MetaESCI ran
the **same** docpluck SHA (`a5c02ef`) against the **same** PDF
(`10.1098/rsos.202336`) in April and in August: 49,091 vs 50,101 normalized
characters, 9 vs 10 downstream effect rows. The system poppler binary had been
replaced on 2026-05-14. `get_version_info()` reported three keys, **all identical
across both runs**. Nothing docpluck recorded made the change detectable, so the
downstream hunted the difference in its own code.

They filed one ask. Sweeping for the *class* found three more defects of the same
shape, two of them user-facing and one of them older than the ask.

### 1. An incomplete provenance receipt is worse than none

A complete-*looking* receipt is read as a complete pin. A library SHA cannot pin
an external binary: `pdftotext_default` shells out to whatever is on `PATH`.

**Enumerate four classes, not one:** the library itself; **every in-repo
`*_VERSION` constant** (`SECTIONING_VERSION` / `TABLE_EXTRACTION_VERSION` were
exported and independently bumped, just never on the receipt); **the interpreter**
(`normalize.py` calls `unicodedata.normalize`, so CPython's Unicode database is a
direct input); and **every external engine** — including the ones for the formats
you were not thinking about. Two of docpluck's three input formats (DOCX via
mammoth, HTML via bs4/lxml) were unpinned entirely, and camelot's lattice flavor
rasterizes through pypdfium2 and OpenCV.

**Guard it structurally, not by name.** A test asserting `"poppler_version" in
info` passes forever while the next input goes unreported. Two guards now derive
their expectations from the repo itself:
`test_every_declared_runtime_dependency_reaches_the_receipt` reads
`pyproject.toml`; `test_no_exported_version_constant_is_missing_from_the_receipt`
reads `docpluck.__all__`.

**Record the ENGINE when two engines share a name.** poppler and Xpdf both banner
as `pdftotext version N` and differ *behaviourally* (Xpdf 4.x emits `\n\n`
paragraph breaks — memory `feedback_pdftotext_version_skew`). Hence
`pdftotext_engine`; hence `poppler_version` is `None` under Xpdf. And **do not
gate the probe on its exit code** — Xpdf prints the banner and exits non-zero, so
`returncode == 0` would report `unknown` for the very engine whose identity
matters most. Read both stdout and stderr.

**Prefer the module in `sys.modules` over `importlib.metadata`, and allow several
distribution names.** Metadata can name code that never runs (this checkout's own
`importlib.metadata.version("docpluck")` lags `docpluck.__version__`). OpenCV
ships as `opencv-python` / `-headless` / `-contrib`; camelot's extra names only
the first, so a single-name lookup reports "not installed" on a machine where
`cv2` imports fine. **Wrong is worse than missing.**

### 2. A declared option the code never branches on

`render_pdf_to_markdown(normalization_level=…)` was accepted, documented as
"forwarded to `extract_sections`", and **discarded** — `extract_sections` took no
level and hard-coded `academic`. `none`, `standard` and `academic` produced
byte-identical markdown. The CLI's `--level` and the service's `/render?level=`
both rode on it: a documented user-facing option that had never done anything.

**When you make such an option real, the default must preserve today's
behaviour.** The declared default was `standard` while the code did `academic`;
plumbing it through as-declared would have silently downgraded every render in the
corpus. Move the default to what the code actually did, so only callers who
explicitly asked for something else see a change. **Check the other repo too** —
the service's `/render` defaulted to `standard`, so the library fix alone would
have changed production output the moment the pin bumped.

And where a branch genuinely cannot honour the option (DOCX/HTML never call
`normalize_text`), **raise** rather than accept-and-ignore. Accepting an argument
that changes nothing is the defect, not the fix.

### 3. A hand-enumerated serializer drops the next field added

Four of them here. Every unit was individually correct; the value just never
reached the consumer.

- **`Section.subheadings` reached NO consumer.** v1.6.1 added the field,
  `sections/core.py` populates it, tests cover it — and both surfaces
  (`docpluck sections --format json` and the service's `/sections`) had
  *independently* enumerated the nine keys that existed beforehand. The feature
  worked and was invisible. Two consumers writing the same key list is a
  duplicated hazard, not a redundancy.
- **`NormalizationReport.to_dict()` dropped `column_interleave_pages`**, a
  populated field `extract_columns.py` documents as the canonical source of that
  signal. Live, and older than the ask.
- **`ExtractionReport.to_dict()`** would have dropped every field added by this
  very change.
- The per-file `<stem>.json` sidecar, built from a picked key list.

Derive from `fields()` / `asdict()`, and pin it with a guard asserting `to_dict()`
covers every declared field. Where an omission is genuinely wanted (a
megabyte-sized `normalized_text`), **name it** in a constant and emit something in
its place, so it reads as a decision. Also **splat** rather than assign
field-by-field when copying one structure into another: a new key then raises
`TypeError` immediately instead of silently sitting at its default.

### 4. Dead code that documentation described as live

`append_footnotes_section` had **zero call sites** anywhere *and* an unreachable
precondition (it looked for the F0 sentinel that only `normalize_text(layout=…)`
produces; `extract_sections` never passes `layout=`). It was orphaned by the
v1.6.1 change that took F0 out of the sections path — and `/docpluck-review`
SKILL.md check 9 still described it as the thing that finds the sentinel. **A
comment or doc that names a function is a claim about the call graph; verify the
function is invoked.**

### How these were found, and how they were nearly mis-found

An AST sweep, not grep: dict literals mirroring a dataclass, dataclass fields
never assigned, function parameters never referenced. Grep cannot see any of them.

But the sweep's *first* answers were mostly wrong. It flagged eleven `Section(…)`
rebuilds as dropping `subheadings`; reproduction showed subheadings are attached
at `core.py:299`, **after** the coalesce and truncation rebuilds, and are never
attached to `unknown` spans at all (`core.py:283`) — so all but the dead one were
false. It flagged `_detect_2col_midline_gutter(page_height)` as a dead parameter;
the docstring already explains why it is deliberately unused. **Every finding is a
hypothesis until a reproduction confirms it — including your own tool's.**

Two more, both found by cross-model review rather than by re-reading the code, and
both *wrong values on disk* rather than missing ones: a sidecar recording
`ok: false` on every **successful** extraction, and an `elapsed_seconds: 0.0`
written before the timer stopped. Neither crashed, neither failed a test.

### What the SECOND review pass taught (the fix needed four more rounds)

The work above was reviewed once, declared clean, and then re-reviewed at higher
rigor. The second pass found **more defects in the fix than the fix had found in
the code** — every one of them a value that was wrong or unstable rather than
missing:

- **A crash I shipped between two reviews.** Adding `pdftotext_path` to the
  receipt without adding the matching `ExtractionReport` field made
  `extract_to_dir` — the public batch API — raise `TypeError` 100% of the time.
  The *splat* construction is what made it loud instead of silent, which is why
  it is built that way; but it still reached a review, not a test run.
- **A provenance value that changed with call order.** Preferring the imported
  module's `__version__` made `opencv_version` read `4.13.0.92` before `cv2` was
  imported and `4.13.0` after — one process, one install, two answers. **Ask of
  any recorded value: does it depend on *when* I ask?**
- **A "fix" for that whose premise was false.** Detecting a shadowing module by
  comparing its path against `distribution(name).locate_file("")` fails because
  that root is the whole `site-packages` — the test answers *true* for
  essentially everything. It would have returned wrong versions. Dropped in
  favour of a stated limitation: **a stable slightly-imprecise value beats an
  unstable sometimes-wrong one, and an honest documented gap beats an
  unreliable detector.**
- **A 60x-and-then-3000x performance regression, in the correctness fix.**
  `packages_distributions()` costs 6–11 s per call and the stdlib does not cache
  it; calling it once per engine took `get_version_info()` from milliseconds to
  ~24 s. **Measure the helper you just added to a per-file path.**
- **A cosmetic cleanup that broke seven tests.** Removing an unused parameter
  from a private helper — genuinely unused *in the body* — broke every test that
  passed it positionally. **A parameter's contract includes its call sites.**
  Reverted and documented instead, matching what this codebase already does for
  `_detect_2col_midline_gutter(page_height)`.

Two of those (the crash, the order-instability) were found by a model, not by
re-reading; two more (the false `locate_file` premise, the dead
`_cached_packages_distributions` left behind by my own refactor) were found by
asking a model to falsify the *fix* rather than review the code. **Route the
remedy past a second model, not just the defect** — and re-run the full suite
after every "obviously safe" cleanup.

### A declared field with no way to populate it

`Section.pages` is documented as 1-indexed page numbers and is **always `()`**,
for every format: page mapping needs `NormalizationReport.page_offsets`, which
only `normalize_text(layout=...)` fills, and `extract_sections` deliberately
omits `layout=` (v1.6.1 — see L-001). The CLI and the service both emit
`"pages": []`, which reads as "spans no pages" rather than "not computed".

Not fixed here, and that is the point of recording it: wiring it up runs F0 and
is exactly the corpus-wide change L-001 records being reverted. **When the fix
is a behaviour change you cannot verify in the current run, say so at the field,
queue it, and tell the user — do not leave the field looking functional.**

### And one performance defect in the fix itself

The first `count_greek_chars` was a per-character Python loop — **60x slower**
than the equivalent regex (29 ms vs 0.5 ms per paper; 247 s vs 4 s across the
requester's 8,431-document corpus). Measure a helper that runs on every file of
every batch. The regex is compiled *from* the range table so the readable
definition and the fast implementation cannot drift, with an exhaustive
boundary test proving they agree.

Cite: `docpluck/version.py`, `docpluck/batch.py`, `docpluck/normalize.py`
(`NormalizationReport.to_dict`), `docpluck/sections/types.py`,
`docpluck/sections/__init__.py`, `docpluck/sections/core.py`, `docpluck/cli.py`,
`docpluck/render.py`, `tests/test_provenance_completeness.py`, CHANGELOG
`[2.4.126]`, `REPLY_FROM_DOCPLUCK_v2.4.126.md`.

---

## L-013 — An allowlist of allowed PATHS cannot see disallowed CONTENT; and a force-push does not end a purge

**Surface.** `tests/snapshots/*.txt` — 12 files, 984 KB — were the byte-identical
`extract_pdf()` output of real published papers: title, all authors,
affiliations, full body. `apa_efendic_affect.txt` carried SAGE's own
`Ó The Author(s) 2021 / Article reuse guidelines: sagepub.com/journals-permissions`
verbatim. They were git-tracked and served from a **public** remote from
2026-05-07 to 2026-08-07. Plaintext is *more* scrapable and indexable than the
PDFs this repo already refuses to commit (`.gitignore` `*.pdf`).

**Why three cleanup passes missed them.** All three scanned for known-bad
*filenames*, and these are named exactly like ordinary fixtures. The 2026-08-06
pass fixed that by **inverting** to an allowlist of paths that may be public
(L-011) — and `tests/**` is on it, so the allowlist passed them too. An allowlist
answers *"is this path allowed to be public?"*. It cannot answer *"should this
content exist at all?"*. **Both checks are required**, and the content one has to
be content-based:

```bash
python ~/.claude/skills/article-finder/publication-text-scan.py . --history
```

**The obvious content rule is the wrong one — measured, not assumed.** "Flag a
DOI plus >2 KB of prose, or publisher boilerplate" flagged **24 files to catch
12**: `normalize.py`, `render.py` and `CHANGELOG.md` all carry
`Article reuse guidelines` and `journals.sagepub.com` *as the patterns this
library strips*. Boilerplate proves a file MENTIONS a publisher, never that it IS
one. A **bibliography** discriminates — over these 12 leaks versus this repo's
own source and docs, (APA entries + numbered entries + in-text citations) scored
**28–130 against 0–1**. Two false-negative traps found during calibration: the
five APA papers had zero numbered references while the seven
Nature/IEEE/JAMA/BMC papers had zero APA ones (an APA-only detector clears seven
leaks), and 43 KB of column-wrapped BMC measured 1,509 B of prose until lines
were de-wrapped, falling under the floor entirely.

**The fixtures were exposed AND unused.** The test they served had resolved
under the abandoned `~/Dropbox/Vibe` root since 2026-08-03, so all 12 SKIPPED
while the suite reported green — all of the exposure, none of the protection.

**A sha256 gives the identical guarantee in ~80 bytes per fixture.**
`tests/snapshots/checksums.json` pins digest + byte count + `method`; the pins
were generated from the old `.txt` files and then re-derived from a live
extraction run, matching digest-for-digest before anything was deleted. The one
thing a hash cannot do — print a diff — is restored by `--snapshot-explain`,
which fetches the expected text from **article-finder**, where the 12 texts now
live as versioned tool artifacts (`extract-text__docpluck@2.4.126`) keyed by DOI.

**A force-push does not end a purge.** After rewriting the history (283 commits,
127 tags; 21,597 retained file entries verified byte-identical against a
pre-purge bundle) and force-pushing `main` and every tag — all verified clean by
mirror clone — **`refs/pull/1/head` still serves 312 pre-purge commits and 37
article-text paths, HTTP 200 UNAUTHENTICATED.** That includes 24 splice-spike
render baselines everyone believed were safely gitignored. Git cannot delete a
merged PR's ref and a force-push does not touch it; only GitHub Support can.
**Verify a purge with `git clone --mirror` plus an unauthenticated `curl` at the
PR SHA — a normal clone shows clean.** Gitignoring is not protection: those
baselines reached the public remote through exactly this ref.

**Rule.** Papers, publication text, ground truth, test corpora and tool
baselines belong to **article-finder**, not to this repo and not to a gitignored
corner of it. Never commit the extracted text of a paper — "it's just text, no
copyright issue" was the written rationale for these fixtures, and it was wrong.

Cite: `tests/snapshots/checksums.json`, `tests/test_v2_backwards_compat.py`,
`tests/conftest.py`, `scripts/verify_corpus.py`,
`~/.claude/skills/article-finder/{publication-text-scan.py,_lib_textleak.py,_lib_artifacts.py,ingest-local-pdf.py}`,
memory `feedback_articlefinder_is_sole_custodian_of_papers`, 2026-08-07.

---

## L-014 — An exclusion list is not a discriminator; and the corpus you measure on decides which way a shared rule is wrong

### The surface problem

ESCImate filed one divergence against `normalize.py`'s A3 (European decimal comma):
`t(28) = 2,21, d = 0,45` left `2,21` unconverted because A3's trailing lookahead omits
`,`, so a downstream parser read **2** — a 10× error. Their proposed fix was to admit `,`
into the lookahead. Reasonable, reproduced, real.

Measuring it produced the opposite finding, an order of magnitude larger.

### What measurement showed

Their remedy, run over the 101-PDF corpus: **52 sites in 16 of 101 papers, 0 true
positives.** Every one was a citation or affiliation superscript run
(`Yuan-Ai Tseng 1,12, Yu-Lun Ou 2,3,12`), a figure list, or a chemical name. An
adversarial pass then refuted **our own** narrower "comma + space" variant with a sentence
neither corpus contained: `Studies 1,2, and 3 replicated` → `Studies 1.2, and 3`. An
English list comma *is* followed by whitespace.

Then the same scan, pointed at the **shipped** rule rather than the proposal: A3 fired 29
times across 13 papers and **~27 were not decimals** — `controls.7,8` → `controls.7.8`
(Vancouver superscripts after a sentence period), `Frank 1,2` → `Frank 1.2` (affiliation
markers), `Experiments 1,2` (enumeration), `9,57` (a flattened ANOVA df pair). The
divergence they filed was real and it was the *smaller* half of the problem.

### Root cause

A3 discriminated with a **negative enumeration** — a lookbehind listing five characters
that may not precede the number. An enumeration is never complete: the sentence period
and the `%` were simply not on the list, and the first element of an affiliation run is
space-preceded, so the comma exclusion that protects the run's interior protects nothing
at its head. A3a had the same shape one level up: its bracket guard recognised exactly one
label form (`[A-Z]` + bracket), so `chi2(2,420)` lost its df pair and
`Median (Q1,Q3) … 148 (52,272)` published `(52272)` — a destroyed interquartile range,
in a table whose adjacent row `8 (4,14)` came out correctly.

### The rules

1. **Prefer a positive structural signature to a growing denylist.** A3 now converts only
   in the **value position** — an operator immediately before the number. Count the
   exclusions: a lookbehind with five of them was already the signal to invert the rule.
2. **Two corpora, opposite risk profiles, one regex.** Their papers are continental, ours
   English; the same rule is too conservative on theirs and too aggressive on ours. A
   shared conformance corpus containing only one side's papers will keep prescribing the
   other side's regressions. Contribute negative cases, not just failing ones.
3. **Verify the fix's premise, not only the defect.** Their remedy and our counter-remedy
   were both refuted by measurement *before* either shipped. Reproduce the proposal on
   your own corpus and count.
4. **Verify the praise too.** Their reply stated that A3a "handles every one of those
   cases correctly." It half-handled `1,234/5,678` → `1,234/5678`, because `/` was missing
   from the boundary class. A compliment is a claim.
5. **Preserving an ambiguous token is not the same as getting it wrong.** Where evidence
   is absent (a prose decimal with no operator, a lone bracketed count), leave the source
   form: both readings stay recoverable. Fusing a pair is irreversible.
6. **A guard's comment is a claim about the guard.** Ours named `t(1,197)` and
   `chi2(2,42)` as blocked cases; neither was.

Cite: `docpluck/normalize.py` (A3a bracket guard, A3 value position, A3d),
`tests/test_numeric_separator_value_position.py`,
`tools/diag/a3_comma_lookahead_scan.py`, `tools/diag/a3a_df_bracket_guard_scan.py`,
`CHANGELOG.md [2.4.127]`, ESCImate spec 1.4.0 conformance corpus (38 → 47 passing),
2026-08-12.

---

## L-015 — Test the composition that ships, not the one that is easy to run

### The mistake

docpluck feeds effectcheck: `PDF → docpluck.normalize_text → effectcheck::check_text`. When
ESCImate filed a separator divergence, both implementations were compared **on raw PDF text** —
`effectcheck(raw)` beside `docpluck(raw)`. That composition does not exist in production.
effectcheck never sees raw text. It sees whatever docpluck leaves behind.

Two conclusions were therefore unsafe, in opposite directions:

- a defect measured in the downstream may be **unreachable** in production, because the upstream
  already repaired its trigger — effort spent on it is wasted;
- a distinction the upstream **destroys** is unrecoverable downstream no matter how good the
  downstream is. `148 (52,272)` fused to `(52272)` cannot be un-fused by any consumer.

### The rules

1. **When two tools compose, the harness is the composition.** Run A, feed A's output to B,
   diff at both boundaries. Anything B changes in A's output is the real contract surface: either
   A left something B had to repair, or B damaged something A had already made correct.
2. **Ownership follows the evidence, not the symptom.** The layer that can still see what
   disambiguates a token owns the repair. Asking the downstream to fix something whose evidence
   the upstream deleted is asking it to guess.
3. **Pin the versions that actually run.** The effectcheck installed in the consumer's library was
   **0.6.19**, three releases behind the separator rewrite it was being credited with. Measuring
   the version in the sibling repo's source tree would have told a flattering, false story.

Cite: `docs/FINDINGS_2026-08-13_separator_ambiguity_matrix.md`, 2026-08-13.

---

## L-016 — docpluck can SEE what the consumer can only guess; spend the evidence here

### The measurement

`jama_open_1.pdf` page 2 renders as `controls.7,8However` in the pdftotext channel. In the
**layout** channel:

```
 '.'   size 8.48   top 373.06     body text
 '7'   size 5.49   top 371.98     65% of body size, baseline raised 1.08pt
 ','   size 5.49   top 371.98     same run
 '8'   size 5.49   top 371.98
 'H'   size 8.48   top 373.06     body resumes
```

`7,8` is a Vancouver citation superscript, **provably**, from font size and baseline. (A first
write-up of this measurement also claimed pdftotext had dropped the space before "However". It
had not — that was an artifact of the probe, which joined LAYOUT glyphs, and a glyph stream
contains no space characters at all. Corrected on re-measurement: the text channel reads
`controls.7,8 However`. The superscript evidence itself reproduced exactly.) docpluck had
been inferring it from text shape ("is there a period before the digits?") — a heuristic standing
in for a fact it already had. effectcheck receives `controls.7,8However` and has nothing but the
shape, forever.

### The rules

1. **Prefer a fact to a heuristic when the channel carries the fact.** Font size + baseline settles
   super/subscripts; x-gaps settle dropped spaces; bounding boxes settle table-cell membership;
   the whole document settles the decimal convention (mutually exclusive within one article) and
   the citation style (a numbered bibliography plus superscript runs).
2. **Never insert markers inline.** Anything docpluck writes into the text becomes text the
   consumer must parse; an annotation is a new contract and a new parsing hazard. Resolve, or
   abstain and record the abstention in the report — not in the text. (codex, 2026-08-13.)
3. **The two channels come from different engines and do not align 1:1.** pdftotext and pdfplumber
   disagree on ligatures, dropped spaces, hyphen repair and column order, so a layout fact applied
   to the wrong span is the failure mode to design against. Correlate conservatively — the W0h/W0m
   pattern (rewrite at most as many slots as the layout counted, left to right) exists for exactly
   this reason. See L-001 for why the channels must not simply be swapped.
4. **Measure precision, recall AND abstention per signal before adopting it.** A signal that fires
   rarely but wrongly is worse than one that abstains often.

Cite: `docpluck/extract_layout.py`, `docs/FINDINGS_2026-08-13_separator_ambiguity_matrix.md`,
2026-08-13. Status: the superscript measurement above is verified; the corpus-wide precision and
recall of each signal were still being measured when this was written — **treat the wider claims
as UNVERIFIED until that report lands.**

---

## L-017 — One text defect has one injury PER CONSUMER, and almost nothing downstream is gated

### The measurement

One docpluck defect — emitting `controls.7.8` where the paper prints `controls.7,8` — was traced
into three different consumers, each damaged a different way:

| consumer | injury | why it cannot defend itself |
|---|---|---|
| effectcheck (statistics) | reads a fabricated decimal in prose | it sees text only |
| **citelink** (citation checking) | **a citation marker is silently deleted** | its detector matches digit runs with separators `[,–-]`; the `8` is then dropped by its own *"skip if preceded by a digit"* filter — a filter that is CORRECT, and exists so `0.91` is not read as a citation |
| CitationGuard | number parsed under hardcoded US-locale assumptions | it consumes no locale information at all |

Each consumer's own handling was individually reasonable. The damage came from upstream, and only
upstream can fix it.

### The second half: the blast radius is immediate

Surveying how each consumer actually obtains docpluck:

| consumer | mechanism | gate |
|---|---|---|
| MetaESCI | **editable install of the working tree** | **none** — uncommitted work runs against real corpus batches |
| ESCIcheckapp worker | HTTP to live `docpluck.app` | **none** |
| CitationGuard | HTTP to the deployed service | **none** |
| PDFextractor | git tag pin, verified against `origin/master` | yes |
| ScienceArena | package metadata + a build gate that fails on drift | yes |

Plus: `/render` returns a `PlainTextResponse` with **no version in the body**, so an external
caller cannot tell that the text changed; and `/sections` hand-rolls its serializer instead of
calling `Section.to_dict()`, so a NEW report field silently fails to reach it — the exact bug that
hid `subheadings` until 2026-08-07.

### The rules

1. **Estimate a text change's blast radius per CONSUMER, not per repo.** Ask what each one's own
   heuristics will do with the changed bytes. The answers differ and some are invisible.
2. **A defect the downstream cannot see is upstream's to own** — see L-016.
3. **Before changing text, check who is gated.** In this portfolio most consumers are not, so
   "it's only in the working tree" is not containment: MetaESCI's editable install means anything
   merely *written* is already live for its next batch.
4. **A new report field is not delivered until every serializer emits it.** Grep for hand-rolled
   serializers in the same change.

Cite: `docs/FINDINGS_2026-08-13_decisions_and_implications.md` Part 1.7 and 3.4,
`citelink/src/numericCitationDetector.ts:207`, 2026-08-13.

---

## L-018 — A partial transliteration is worse than none: one unmapped character silently downgrades a verified result

### The measurement

`academic` normalization transliterates Greek and superscripts into the flat ASCII that consumers
parse. It does it **incompletely**:

```
chi-squared(2)  ->  chi2(2)     correct
R-squared adj   ->  R2adj       correct
BF subscript01  ->  BF01        correct   (subscript DIGITS U+2080-2089 are mapped)
eta-squared-p   ->  eta2<U+209A>  WRONG   (the subscript LETTER is not)
```

The whole subscript-letter block **U+2090–U+209C** and the phonetic subscripts U+1D62–U+1D6A pass
through untouched. So partial eta squared — one of the most common effect sizes in psychology —
leaves docpluck as a mixed ASCII/Unicode token.

Run end to end through the real consumer, whose normalizer explicitly handles the intended form
(`effectcheck/R/parse.R:576` maps `eta2p|eta_p2|etap2|...` to "partial eta-squared"):

```
'F(1, 98) = 4.20, p = .043, eta2p = .04'          ->  effect_reported 0.04   status PASS
'F(1, 98) = 4.20, p = .043, eta2<U+209A> = .04'   ->  effect_reported NA     status OK
```

**The row still appears. Nothing errors. The status silently degrades from PASS (checked and
correct) to OK (nothing was checked).** An effect size stops being verified because of one
unmapped character.

### Measured frequency — small, and format-dependent, which is the second lesson

| input channel | documents with a surviving subscript letter |
|---|---|
| PDF (pdftotext) | **0 of 26** sampled — publishers position subscripts *typographically*, so the codepoint never reaches the text |
| DOCX (mammoth) | **1 of 25** — 2 occurrences of `H` + U+2090 (`Hₐ`, the alternative hypothesis), both surviving normalization |

So this is a **latent** defect on the PDF corpus and an **active but rare** one on DOCX. The
harmful token (`eta2` + U+209A) was constructed to demonstrate the mechanism; it has not been
observed in real input yet. Fix it because the failure is silent and the fix is a table
completion with a blast radius of exactly the documents containing those codepoints — but do not
report it as a widespread active defect.

**The second lesson is the format blindness itself:** the 101-PDF corpus that every measurement
in this project runs against **cannot see this class at all**, because the codepoints never
survive pdftotext. A library with three input formats needs its corpus to cover three input
formats, or a whole defect class is structurally invisible.

### The rules

1. **A transliteration table is a contract; enumerate the whole Unicode block, not the members you
   happened to meet.** Mapping the digits of a block and not its letters is the same defect shape
   as an exclusion list that is missing a character (L-014).
2. **Test a mapping through the CONSUMER, not against itself.** `eta2<U+209A>` looks fine on
   screen and is a perfectly valid string; only running the consumer shows the verification
   silently disappearing.
3. **A downgrade from "checked" to "not checked" is a silent failure, not a degraded one.** Any
   status that can mean either "verified" or "there was nothing to verify" needs the two states
   distinguished, or a defect upstream will present as a clean result.
4. Corollary for reviewers: when a consumer hand-enumerates spellings of a symbol, that list is a
   map of what the producer is expected to emit. Diff your output against it.

Cite: `docpluck/normalize.py` (Greek/superscript transliteration tables),
`effectcheck/R/parse.R:576`, `docs/FINDINGS_2026-08-13_decisions_and_implications.md` D6a,
2026-08-13.

---

## L-019 — Normalization can INVERT the evidence a downstream rule depends on

### The measurement

ESCImate's spec 1.4.0 added rules L1/L2/L3: infer the article's numeric locale from
operator-guarded markers, and gate every separator rule on it. The two conventions are mutually
exclusive within one article, so one unambiguous token settles every ambiguous one. Good design.

Run that same inference before and after docpluck's `academic` normalization, on one document:

```
RAW text       ->  decisive_eu   (6 European markers, 0 US)
DELIVERED text ->  decisive_us   (0 European markers, 6 US)    the verdict INVERTS
N = 1,234      ->  N = 1234                                    already resolved, wrongly
```

Normalization converts every `d = 0,80` to `d = 0.80`, so the delivered text *looks* decisively
US **by construction**. The downstream's locale inference cannot fire correctly in production: it
works in their tests, which feed it raw text, and is defeated in the pipeline, which feeds it
ours.

### The rules

1. **Ask what evidence your transformation consumes, not just what text it changes.** A rule that
   rewrites the very tokens a downstream rule votes on does not merely change output — it
   *inverts the input to their decision procedure*, silently and in a direction that looks
   healthy.
2. **A document-level fact must be computed where the evidence still exists, and then PUBLISHED.**
   Anything else asks the consumer to re-derive a fact from text you already resolved. Publish the
   fact with its confidence and evidence counts, not a bare label.
3. **When a sibling project ships a rule that depends on your output, run their rule on your
   output.** Reading their design is not enough; theirs was sound and still cannot work.
4. Corollary to L-015: "test the composition" includes testing the *consumer's internal
   inferences* against your output, not only the final numbers.

Cite: `docs/FINDINGS_2026-08-13_decisions_and_implications.md` D5,
`ESCIcheckapp/effectcheck/R/parse.R::infer_numeric_locale`, spec 1.4.0 rules L1-L3, 2026-08-13.

---

## L-020 — Corpus coverage decides which defects are knowable; ours covers one format and one locale

### The measurements that exposed it

Three defect classes found on 2026-08-13 are **structurally invisible** to the 101-PDF corpus that
every gate in this project runs against:

| defect class | why the corpus cannot see it |
|---|---|
| unmapped subscript letters (`eta2ₚ`) | 0 of 26 PDFs contain the codepoints — publishers position subscripts *typographically*. Found only by testing the **DOCX** channel: 1 of 25 files (`Hₐ`). |
| numeric-locale canonicalisation | 101 papers: 80 decisive-US, 20 no-evidence, 1 false-conflict, **0 European**. The entire feature is unmeasurable here. |
| continental tables / bare-cell decimals | the corpus has none, so the accepted cost of the value-position gate is untested rather than tested-and-cheap |

The corpus is also in the wrong place: it lives at `PDFextractor/test-pdfs`, which violates the
custody rule that **article-finder is the sole custodian of papers**, and it is far smaller than
what article-finder can supply.

### The rules

1. **A green corpus diff is only as good as the corpus's coverage.** Before trusting one, ask what
   the corpus does *not* contain. Ours contains one input format (PDF), one locale (US-English),
   and no continental tables.
2. **A library with N input formats needs a corpus covering N input formats.** The DOCX defect was
   found by deliberately leaving the corpus, not by any gate.
3. **Get the corpus from the custodian, not from a directory.** `ai-gold.py papers-with-view`
   supplies the expected paper set; a glob computes its denominator from its numerator and prints
   `N / N` on a corpus that has silently shrunk.
4. **State the coverage gap in the finding.** "0 European papers" turns "we measured no impact"
   from a reassurance into a known blind spot.

Cite: `HANDOFF_2026-08-13_locale_layout_and_downstream.md` §2,
`docs/FINDINGS_2026-08-13_decisions_and_implications.md`, 2026-08-13.

---

## L-021 — Reproduce every claim: your own, the reviewer's, and the compliment

### What went wrong in one session

| claim | who made it | what reproduction showed |
|---|---|---|
| "pdftotext dropped the space before *However*" | **me** | probe artifact — I joined LAYOUT glyphs, which contain no space characters at all, so *every* space was missing |
| "citelink drops citation marker 8" | a reviewer | my first reproduction ran the regex **without the loop's filters** and concluded both markers survived — the faithful replay confirmed the reviewer |
| "`Mdn 12,34` converts today, so the fix loses it" | a reviewer | false — the shipped rule never converted it |
| "docpluck's A3a handles every one of those cases correctly" | **a compliment from the consumer** | it half-handled `1,234/5,678` → `1,234/5678` |
| "admit a bare comma into the lookahead" | the consumer's proposed **fix** | 52 sites / 16 papers / 0 true positives |
| "admit a comma followed by whitespace" | **my** counter-proposal | refuted by `Studies 1,2, and 3` → `Studies 1.2, and 3` |

Six claims, six wrong in some direction, all caught by running code — including two of mine and
one *praise* that was hiding a defect.

### The rules

1. **Reproduce before repeating, and reproduce FAITHFULLY.** A partial reproduction (the regex
   without its filters) is worse than none: it produces a confident wrong answer.
2. **Verify the fix's premise, not only the defect.** Two candidate fixes died to measurement
   *before* shipping; a third defect was found by an adversarial pass *after* implementation.
3. **Verify praise too.** "You handle this correctly" is a claim about your code, and it can be
   wrong in the direction that hides a defect.
4. **Say which of your own claims were wrong, in the artifact.** A corrected record is worth more
   than a clean-looking one; the next session inherits whichever you leave.

Cite: `docs/FINDINGS_2026-08-13_decisions_and_implications.md` Part 4, 2026-08-13.

---

## L-022 — Ship the contract, not just the code: normalization levels are a promise

### The finding

docpluck was **already** converting European decimals to US form at `academic` — partially,
accidentally, and undocumented. Nobody downstream knew whether to expect source form or canonical
form, so:

- Scimeto's parser strips every comma and calls `parseFloat` — safe only by accident of our
  behaviour (`0,80` would become **80** on raw input);
- effectcheck built a locale inference that our behaviour makes inoperable;
- and a continental paper could reach a consumer with **mixed conventions inside one document**.

The escape hatch already existed and was already correct — `standard` and `none` are
character-faithful for numerics, and `preserve_math_glyphs=True` skips the decimal rules — but it
was never stated as a contract, so no consumer chose a level deliberately.

### The rules

1. **A normalization level is an API promise. Write it down.** `academic` = value-normalized text
   for machine consumption (it already transliterates Greek, U+2212, ligatures, quotes and
   superscript digits). `standard`/`none` = character-faithful. A consumer that wants fidelity
   must be told which door to use.
2. **Partial canonicalisation is the worst state.** Converting some tokens and not others yields
   documents that are internally inconsistent — `[1,12, 2.78]` — which no consumer can detect.
   Either canonicalise completely under an explicit gate, or not at all.
3. **When you resolve an ambiguity, publish that you did.** The value alone is not enough: emit
   the inferred fact, its confidence, its evidence count, and how many tokens you converted.
4. **Check what the consumers assume before changing the promise.** Two of them had already built
   on the undocumented behaviour in opposite directions.

Cite: `HANDOFF_2026-08-13_locale_layout_and_downstream.md` §4,
`Scimeto/apps/worker/src/utils/statisticalExtractor.ts:55`, 2026-08-13.

---

## When to add a new lesson here

Add a lesson when:
- A Claude session (or you) tried to fix a problem and ended up reverting because the fix broke many other things.
- The same wrong reasoning has surfaced ≥2 times across sessions.
- A choice that looks "obviously wrong in retrospect" has historical context that explains why the alternative was tempting.

Format: short surface description, the failed attempt, the rule.  Cite specific files and dates so future readers can git-blame the actual change.

## L-023 — Never learn about an English-article problem from a non-English article

**Established by user directive 2026-08-13, after it nearly shipped a wrong conclusion.**

docpluck's scope is **English-language science articles**. The rule that matters is not the scope
statement itself but its second half: **evidence gathered from non-English articles must never be
used to reason about an English-article problem.**

**What happened.** The EU-vs-US numeric-separator question needed European-locale papers to be
measurable, and the 101-paper corpus had zero. A corpus-widening pass was asked for them. It found
them the only place they exist in quantity — SciELO (Brazilian, Chilean, Colombian) and Turkish
journals — and returned 21 papers all measuring `decisive_eu`. Those 21 were then used to evaluate
a document-level locale gate.

**Why that was wrong twice over.**

1. *The papers are bilingual.* A SciELO article carries an English abstract over a
   native-language body. Verified by marker position within the document:

   ```
   Rev Med Chile:  '1,738 adult patients'  at  2% of the document   (English abstract)
                   13 European markers     at  19,37,40,46,49%      (Spanish body)
   ```

   So one document genuinely contains both conventions, each correct in its own span. Every
   document-level conclusion drawn from it describes a shape docpluck does not serve.

2. *The failure modes differ in kind.* Within English, a continental value is an anomaly — a
   pasted table, a translated appendix, a typo — and the right response is a structural rule. In a
   continental article it is the norm. A rule tuned on the second is wrong for the first, and the
   corpus that produced it looks like evidence.

**The trap is that the measurement was competent.** The scan was correct, the 21 papers really are
`decisive_eu`, the bilingual finding really is true. Nothing failed. The error was upstream of all
of it: the corpus was selected by the property under study rather than by the scope being served,
so it could only ever confirm something about a population docpluck does not process.

**The rule.**

- Corpus acquisition **states its language filter up front**, in the request, not afterwards.
- Any scan reasoning about separators, locale, or number formatting **reports its language
  distribution and prints what it excluded**. A silent exclusion is how this happened.
- A paper that is *mixed* (English abstract, other-language body) is excluded too, not counted as
  English — its halves disagree. `tools/diag/english_only_locale_scan.py` implements the
  conservative test: English function words must be the plurality AND beat the runner-up 3x.
- **Language is not locale.** Measured the same day: 15 of 18 Turkish papers are `decisive_us`,
  because they follow APA. Selecting by language to get a locale is unsound in both directions.

**The generalisation, which is the part worth carrying to other projects:** when you widen a
corpus to make a feature measurable, you are choosing the population your conclusions will
describe. If you select on the property under study, you get a corpus that can only confirm.
Select on the *scope being served*, then measure whether the property is even present — and if it
is not, that absence is the finding.

See `docs/SCOPE.md` (the consumer-facing statement), the CLAUDE.md hard rule, and memory
`feedback_english_only_never_learn_from_non_english`.

## L-024 — One concept, one table: the same input must never convert two ways

**User directive 2026-08-13** — *"different paths resulting in different conversions is a big nono...
that chi square can result in both 'chi' and 'ch' by docpluck is inexcusable."* Now a standing
`/docpluck-review` check (0b).

`normalize.py`'s A5 step and `extract.py`'s SMP math-italic fallback each carried a Greek-to-ASCII
table. They disagreed on **9 of 9 shared letters**, so a chi-square left docpluck as `chi2` or
`ch2` depending purely on which extraction path handled the PDF. Three disagreements collided with
a *different statistic*:

```
chi2(2) -> ch2(2)   a consumer matching `chi2\(` never checked that test, and nothing reported it
eta2    -> n2       collides with n, the SAMPLE SIZE
beta    -> b        collides with b, the UNSTANDARDIZED COEFFICIENT — the exact corruption W0m
                    exists to detect and undo from layout evidence. One path manufactured what
                    another repairs.
rho     -> r        collides with r, the CORRELATION
```

**Why it survived:** `test_mathitalic_greek_real_pdf.py` exercised the offending path and passed
both before and after the fix, because it never asserted the *convention*. A test that runs a path
without asserting the thing that matters is not coverage.

**The remedy shape:** one canonical definition (`docpluck/symbols.py`); every other site DERIVES
from it — `extract.py` now computes its SMP table by walking each math-italic codepoint back to the
plain letter and asking the one table — and a shared test asserts the sites **agree** rather than
restating the constants twice. Consumers read `symbol_contract()`, not a copy.

**A library that can convert one input two ways has no contract at all.**

The same audit found the class is wide: caption vocabularies that disagree with each other, three
sibling regexes with three different "already-signed" exclusion lists (the drift produced `--0.09`),
and repairs present in two of the three required text channels.

## L-025 — "Leave nothing behind" covers BUILT-BUT-NOT-WIRED, not just unfixed bugs

**User directive 2026-08-13** — *"about 'done' but 'not/never wired', inexcusable, we work on
things, we fix them, and then it's not wired?"*

Work is not done when the code exists, the tests pass and the doc is written. It is done when it
**reaches the consumer through the path production actually uses**. A capability that is
implemented, validated, measured and then invoked by nothing is indistinguishable from one never
built — except that it carries the *appearance* of being handled, which is worse, because every
later reader believes the problem is solved.

Found in one session, each with a green test:

- a superscript-detection signal **validated and documented** in a findings doc, recorded as
  "signal validated, not yet wired", and called by nothing. Wiring it (W0p) recovered **three wrong
  sample sizes in one paper** and eliminated one of only two false locale `conflict` verdicts
  across 396 English papers;
- `batch.py` calling `normalize_text(raw_text, level)` with no `layout=`, so an 8,431-article
  corpus pipeline received **none** of the layout-gated glyph repairs while the sections path
  received all of them;
- `A6_footnote_removal`, whose own comment documents a worked example it **cannot perform**,
  because an earlier step consumed its input — it reports no work rather than failing;
- `extract_sections(html).normalized_text` returning text that never went through
  `normalize_text` — the field name is a false claim;
- `find_figures(layout)` called only by tests while production hardcodes
  `"bbox": (0.0, 0.0, 0.0, 0.0)` — a field that looks computed and is zeros;
- `partition_into_sections(source_format=...)` accepted and never branched on.

**The four checks, before calling anything done:**

1. **A non-test call site exists** for every symbol added — `grep` for it.
2. **Every production path is wired**, not just the one you were looking at.
3. **The caller passes what the capability needs** — a layout-gated repair reached through a call
   site that passes no layout is dead code with a passing test.
4. **Every value computed is read back** — serialized, returned, consumed.

**A green test on an unreachable path is not evidence of anything.**

## L-026 — Normalization canonicalises NOTATION; it does not repair the paper

**User directive 2026-08-13.** *"fixing it isn't normalizing, it's fixing, and that's not what
docpluck does."*

docpluck's job is to be the best text extractor for **what is actually printed** in science papers.
Where a paper prints an error, docpluck passes it through **verbatim**:

```
t = 0,76               among period decimals   PSPB 10.1177/0146167212446164 p9
-0.43 [-0.60, -0,26]   table AND prose         Collabra 10.1525/collabra.32572 p5
M = 26,21, SD = 28.88                          10.1371/journal.pone.0285114
5.75 [5.37, 4.66]      reversed CI             10.1177/0146167219867963 Table 3
```

**Why silent repair is worse than none.** docpluck has no channel to say a repair happened, so it
**launders a real defect** into a meta-science pipeline: the consumer validates a number the paper
never printed, and the author never learns their paper has an error. The Collabra case above is the
project owner's own paper — docpluck was hiding a genuine copyediting defect from the one pipeline
built to catch exactly that.

Flagging and alerting users is **ESCImate's and Scimeto's** role; they have the UI and the mandate.
docpluck's obligation is to pass the defect through and tell those consumers which classes to expect.

**THE ONE EXCEPTION:** a defect docpluck's own pipeline introduced (a fused exponent, a decimal the
PDF text layer dropped, two internal tables disagreeing) is docpluck's to fix — we caused it and the
source is intact underneath. Test: *"did we break this, or did the paper?"* Where the text cannot
tell you, **rasterize the page and look**; never adjudicate with the extractors under suspicion.

**How the drift happened, because this is the transferable part:** nobody decided that
"normalization" would mean "repair". It arrived one defensible rule at a time, each justified by a
real-looking example, and the sum became a policy no one chose. Two cheap checks stop it: *is this
canonicalising notation, or correcting substance?* and *which real paper?*

**Measured caution on sequencing:** effectcheck's real CI regex does not match `[-0.60, -0,26]` —
the whole CI silently vanishes rather than misparsing. So retiring a repair is a *coverage loss*
for consumers until they handle the raw form. **Tell consumers first, then retire.** Never reverse.

## L-027 — Case studies come from real papers, with the DOI. Never hypotheticals.

**User directive 2026-08-13.** *"never hypotheticals because they might never happen and if we do
hypothetical it's an endless slippery slope that we can't manage."*

A constructed string proves what the **code** does. It never proves the **shape occurs**.

Rule `A3d` was built on `p = ,025` — an example inherited from ESCImate's spec and "reproduced
against unfixed code", i.e. a constructed string run through the pipeline. A 600-paper corpus hunt
then found **0 occurrences in 0 papers**. A rule with no observed input is pure false-positive
surface for no benefit, and it had already propagated into the CHANGELOG, `NORMALIZATION.md` and
three consumer-facing reply documents as though it were an observed case.

Before adding or keeping any rule: **which real paper, which page?** If the answer is "a reviewer's
example", it is not evidence. And a rule built this way is a *method* failure, not a one-off — audit
its siblings the same way.

**NEVER ACCEPT A HYPOTHETICAL AS-IS FROM A HANDOFF.** A3d reached shipped code by being copied
forward — ESCImate's spec -> our reply doc -> our handoff -> our CHANGELOG -> `NORMALIZATION.md` ->
a rule — acquiring the appearance of consensus at every hop while remaining one unchecked string.
**Repetition is not verification.** An example arrives with a DOI and a page, or you go find one
before acting; if you cannot, say so in writing and treat the rule as unjustified.

## L-028 — A change that moves work onto a consumer ships with a comprehensive report

**User directive 2026-08-13.** Retiring a repair does not delete the work — it *moves* it to the
consumer. We do not get to make that change and leave them to discover it.

Every such change ships with a report that transfers the whole experience: what changed (with
before/after literals), the **principle** so they can apply it to future cases themselves rather
than memorise a list, the observed defect-class catalogue **with DOIs and frequencies** so they
build detectors against real shapes, the **measured** impact on their code, what we will NOT do, and
a migration order.

Their job is to **FLAG, never to correct** — the same separation that produced the change.

**Migration order is always: they build the flag, THEN we retire the repair.** Measured reason:
effectcheck's real CI regex does not match `[-0.60, -0,26]` — the CI silently *vanishes* rather than
misparsing, so retiring first is a coverage loss their users cannot see. Reversing the order turns a
correctness improvement into a silent regression.

**And report the negative results too.** Classes hunted and NOT found (`p > 1`, negative SD) bound
the surface, and rows that look like errors but are not (semicolon CI delimiters = house style;
4-digit p-values = raw SPSS precision) stop a consumer building a detector that cries wolf. Two
independent reviews disagreed on the precision row; inspection settled it.

---

## L-029 — Audit the rules you intend to KEEP, not only the ones you intend to remove

**2026-08-14.** A full inventory classified all 111 transformations and measured firing rates for
the numeric family over 297 English papers. `A3`, `A3c` and `A3d` were measured in detail and
retired or deleted. `A3a` was marked **KEEP / NOTATION** and its error rate was **never measured at
all** — the audit only interrogated its removal candidates.

An independent third-model review, asked to hunt in good faith for a case where the comma rules are
*right*, found one — and in the same table found this:

```
10.1177/0956797620935584  Battal et al., Psychological Science, Table S2 p24
  printed    df- satterthwaite   185,178   31,836   188,193      t-ratios  -1,966  -7,799
  delivered                      185178    31836    188193                 -1966   -7799
```

Rasterized and confirmed. A Satterthwaite df is **fractional by construction**, so `185,178` is
185.178. **A 1000× error on published inferential statistics, in the rule the audit had cleared.**

Three transferable points:

1. **An audit that only scrutinises the candidates for removal is not an audit.** The rules you are
   not suspicious of are exactly where an unmeasured error rate survives, because nothing prompts
   anyone to look.
2. **Silent-but-plausible is a worse failure mode than silent-but-visibly-broken.** A
   half-converted interval (`0,85-0.99`) carries two conventions in one token and might prompt
   scrutiny. `31836` looks like an ordinary number and never will. Rank defects by whether the
   wrong output *announces itself*, not only by frequency.
3. **A measurement can describe your instrument rather than your corpus.** "396 English articles →
   0 European-locale documents" was true and misleading: every European marker
   `infer_numeric_locale` recognises is **operator-gated**, and a flattened table cell has no
   operator, so a 130-cell comma-decimal table contributes zero evidence. Before quoting a null
   result, ask *what would this instrument be unable to see?* — and say so alongside the number.

## L-030 — Do not edit the code while an "independent" verification of it is running

**2026-08-14, and this one was mine.** A Sonnet review was dispatched to independently verify the
A3-family findings. While it ran, I landed the numeric-tuple guard in `normalize.py`. The reviewer
measured `A3c — 1 site`, re-ran the identical command minutes later, measured `A3c — 0 sites`, and
had to re-measure twice to work out **which state of the library it was reviewing** — noting,
correctly, that it could no longer separate "what the plan proposes" from "what someone already
started implementing."

A verification pass is only worth its tokens if the artifact holds still. The whole point of the
triple-verification rule is three *independent* looks at **one** object; a moving target gives you
three looks at three different objects and the appearance of agreement.

**The rule:** freeze the file, or hand the reviewer an immutable reference — a commit SHA, a copy,
or a worktree — and state it in the prompt. If you must keep working, work somewhere else. And when
a review returns against a version you have since changed, **say so in writing** rather than
quietly folding its findings into the new state, because the reader cannot otherwise tell which
claims were checked against what.

Corollary, same session: my consult document hand-transcribed three regexes from `normalize.py` and
got all three wrong (`[≤≥]` became `[<=>=]`, the sign class `[-–−+]` became `[-.-+]`,
`_VALUE_END_MARKERS` `*†‡§¶#` became `*+-#`). The reviewer caught it by opening the file. **Paste
from the source; never retype it** — L-021 and L-023 are the same lesson and it keeps costing.

---

## L-031 — Six method traps from the 2026-08-14 separation-of-duties run

Each cost real time or nearly shipped a wrong decision. None is specific to the rule that exposed
it.

### 1. The same input shape can have OPPOSITE owners in different documents

`p < 05` is the paper's copyediting error in `10.1016/j.jesp.2009.12.011` p3 (the page prints no
dot) and docpluck's OCR loss in `10.1177/0956797613482946` p6 (the page prints it). One text shape,
two owners, and **the text channel cannot tell them apart**. Do not assume a shape has a single
cause because the first instance you rasterized had one. **Under irreducible ambiguity the default
is pass-through** — pass-through is reversible for the consumer, repair is not.

### 2. A gate built on the channel under suspicion is circular

A layout gate was built to separate those two cases and measured beautifully (0.51 vs 0.99). It is
worthless: Dong's page is a **scan**, so its char boxes were produced by an **OCR engine**, not the
typesetter — the gate's evidence is manufactured by the very process whose reliability is in
question, in exactly the case it exists to catch. This is the *"never adjudicate with the extractors
under suspicion"* rule wearing a disguise; it slipped past because the evidence was *geometric*
rather than *textual* and so felt independent. **Ask what PRODUCED your evidence, not what form it
takes.**

### 3. A guard that lives in the CALLER is lost when the caller changes

Deleting `infer_numeric_locale` silently took the ML-tensor-shape exclusion with it, because that
guard lived in the function body while the pattern it protected lived in a module-level table. The
raw marker immediately started voting European on `(70,64472)` again — caught only because a test
had just been written to pin the vocabulary. **Put the guard in the pattern, the constant, the
table — in the thing it protects, never in one of its callers.**

### 4. Removing a rule can EXPOSE a sibling it was masking

With `A3c` deleted, `(0,003)` reached `A4`'s spacing arm intact for the first time and it emitted
`(0, 003)` — a European p-value rendered as a two-element pair. `A3c` had been inventing the
*decimal* reading; `A4` invented the *separator* reading. Same defect, other hat. **After deleting a
rule, re-run the inputs it used to consume** — they now reach code that never saw them.

### 5. A gate that cries wolf is a gate everyone learns to skip

The identifier scan's first run reported **127 defects**; nearly all were dash canonicalisation and
invisible-character stripping doing their job. Folding out the changes docpluck is *entitled* to
make reduced it to **1 real defect** — which was a genuine, previously-unknown bug. A gate's
precision is not cosmetic: it decides whether the gate gets read. **Budget as much care for the
false-positive folding as for the detection.**

### 6. `(cid:N)` desyncs string offsets from pdfplumber char indices — silently

A pdfplumber char whose glyph has no ToUnicode entry has `text == "(cid:2)"` — **seven string
characters from one char object**. Indexing `page.chars[]` with an offset into
`"".join(c["text"] …)` drifts by +6 per such glyph and lands on a different token several words
away. It reported "not found" on the very site under study, i.e. it looked like *absence of
evidence*. Build an explicit index map (`tools/diag/raster_site.py::_char_text_and_index_map`).

---

## L-032 — Audit every CHANNEL, not the one you were looking at. The uninstrumented channel is where the deletions are.

**2026-08-14, and it indicts the framing of the whole run that found it.** The separation-of-duties
audit was exhaustive *about `normalize.py`*: all 111 transformations classified NOTATION vs REPAIR,
every firing site of every numeric rule counted across 297 English papers, four rules queued to
retire, each verdict decided by rasterizing the page. **The same question was never asked of
`render.py`** — and `render.py` is the channel that reaches the user.

Asked for the first time, it answered immediately. Measured on the baseline corpus, at HEAD:

```
10.1017/s1930297500009189   an ENTIRE published-results sentence deleted
    "…(240 participants * 8 items), we found a strong relationship … (r(6) = 0.94,
     p < .001, 95% CI [0.71, .99]); and … (r(6) = 0.99, p < .001, 95% CI [0.96, .99]).
     Hotelling's (1940) t indicated these correlations to be different from each other
     (t(5) = 4.66, p = .006)."
    present before the post-process chain, ABSENT after.   _suppress_inline_duplicate_table_captions

10.1001/jamanetworkopen.2023.48333   a hazard ratio and its CI deleted
    "<td>1.31 (1.20-1.44)<br>…</td>"                       _strip_phantom_camelot_tables
```

Two correlations, a Hotelling's *t*, three *p*-values and two confidence intervals — **the exact
quantities docpluck exists to deliver** — removed from a meta-science pipeline with **no count, no
key in `changes_made`, no log line, nothing.** `render_pdf_to_markdown()` chains 54 `md = fn(md)`
calls and returns a bare `str`; there is no report object, so no consumer can even ask.

### Why this ranked below the numeric rules, wrongly

Three biases, all worth naming because each will recur:

1. **We audited where the vocabulary was.** "Notation vs repair" is a framework about *rewrites*.
   A deletion is not a rewrite, so the structure channel fell outside the framework entirely and
   nobody noticed the framework had a hole rather than the code having none.
2. **We audited where the instrumentation was.** `A3a` was auditable because it populates
   `report.changes_made`; that is precisely why it got measured, and it is precisely backwards.
   **An uninstrumented channel is where you should look FIRST, because nothing in it can ever have
   been noticed.** Instrumentation attracts audit; the absence of it repels audit and hides more.
3. **We ranked by the severity of the RULE, not of the OUTPUT.** `A3a`'s 1000× error is dramatic
   and it fires 984 times; a deleted sentence is undramatic and rare. But a stripped separator
   leaves a wrong-looking number a consumer can still challenge, while a deleted statistic leaves
   **nothing at all** — no artefact, no anomaly, no trace. Rank by *whether the wrong output
   announces itself*, then by *whether anyone is positioned to see it*. Silence scores worst on
   both.

### The rules

- **Enumerate the channels before auditing any of them**, and state which channel each finding
  came from. docpluck has three (`normalize_text`, table-cell cleaning, the render post-process);
  an audit that names only one has not measured its own coverage.
- **Count the steps from the SOURCE.** The handoff said 41 post-process calls; the source says 54.
  A number copied from a document is a claim (L-027, and the standing ALWAYS-CHECK rule).
- **A channel that cannot report what it did cannot be audited, only spot-checked.** Give it a
  report object before arguing about its individual steps.
- **Deletion needs a positive licence.** A step that *removes* content must state what it removed
  and why, in a form the consumer receives — the same standard a rewrite is now held to.

### Corollary — the measurement instrument is a hypothesis too

The first version of `tools/diag/render_deletion_scan.py` diffed pre-chain against final markdown
and reported a deleted sentence in `10.1017/s0007123424000024`. **It was an artefact of the
instrument**: later steps had reflowed the line, so difflib saw a `delete` plus an unrelated
`insert`, and the digit-signature guard failed because the digits were no longer contiguous. A
second false positive followed — a *legitimate* caption dedup, where the surviving copy differed
from the deleted one by a trailing footnote marker.

Both were caught only by trying to attribute the finding to a specific step and discovering no step
had done it. **Per-step attribution is not a nicety; it is what makes the measurement falsifiable.**
And a scan that re-implements the chain measures its own copy — so the scan derives the step list
from `render_pdf_to_markdown`'s own source and wraps the real module attributes (L-024, one concept
one table).


---

## L-033 — A test that asserts an ABSENCE can be satisfied by DATA LOSS

**2026-08-14, found while fixing L-032, and it is the sharper half of that lesson.**

`tests/test_minus_sign_recovery_real_pdf.py::test_efendic_table_point_estimates_recovered_via_ci`
asserted:

```python
md = render_pdf_to_markdown(pdf.read_bytes())
assert "21.34" not in md   # Table 3, Direction x Attribute -> -1.34
assert "21.05" not in md   # Table 4, PMA -> -1.05
```

and its docstring drew the obvious conclusion — *"Mode-agnostic: … the CI-pairing recovery reaches
the point estimate in either mode."* It was green for months.

**The recovery never reached them.** `_suppress_orphan_table_cell_text` was deleting the entire
linearized table — corrupt estimates, correct CIs and all. The token was absent because the DATA
was absent. Measured by disabling the v2.4.130 guard and re-rendering the same paper: the guard
restores **2,544 characters**, and `21.34` / `21.05` come back with them.

So a test written to prove *"we fixed this corruption"* was actually proving *"this content is
gone"*, and the two are indistinguishable from the assertion alone.

### Why this class is so hard to see

- **It is green.** Nothing crashes, no count drops, no warning fires. It is the "a green result
  from an empty input is a false green" rule (CLAUDE.md), but arriving through a *test* rather
  than through a check.
- **The docstring makes the wrong claim confidently**, because whoever wrote it reasoned from the
  passing assertion rather than from the output. The claim then travels (L-027).
- **The fix that exposes it looks like a regression.** When the guard landed, this test went red,
  and the obvious reading was "my change broke the minus recovery". The correct reading was "my
  change restored the data this test was silently missing". Only rendering both ways and diffing
  told them apart.

### The rules

- **An assertion of the form `X not in output` is only meaningful alongside an assertion that the
  surrounding content IS present.** Pair every absence with a presence: `assert "21.34" not in md`
  needs `assert "[-1.58, -1.10]" in md` beside it, or it cannot distinguish *fixed* from *deleted*.
- **When a test goes red after a fix, render both ways and diff before concluding it is a
  regression.** `len(after) - len(before)` answered this one in a single line.
- **Prefer asserting the CORRECT value over the absence of the wrong one.** `assert "-1.34" in md`
  cannot be satisfied by deletion; `assert "21.34" not in md` can.
- Same family: a suite that fails to *load* reports as a smaller green run, and a module imported
  only by its own test is not shipped. **All three are "the check passed because it never ran on
  anything."**


---

## L-034 — A stale claim in a RULES file is as dangerous as one in a handoff, and I proved it on myself

**2026-08-15, in the session whose entire subject was unverified claims travelling between
documents.** L-027 says a case must come from a real paper. The standing ALWAYS-CHECK rule says a
description is not the thing it describes. I wrote both into `CLAUDE.md` this week — and then did
this:

`CLAUDE.md`'s "leave nothing behind" section carried a worked example:

> *"measured 2026-08-13: `batch.py` calls `normalize_text(raw_text, level)` with no `layout=`, so
> the 8,431-article corpus pipeline receives none of the layout-proven glyph repairs"*

I read it as current, and wrote a **BLOCKER** into the session handoff on the strength of it: *"the
plumbing must be fixed before the CI-pairing rules can be font-gated."* Codex's review of that
handoff flagged the line. I checked every call site:

```
LAYOUT  docpluck/batch.py:310              normalize_text(raw_text, level, dropped_minus_layout=layout)
LAYOUT  docpluck/sections/__init__.py:116  normalize_text(..., dropped_minus_layout=...)
```

**It was fixed in v2.4.128.** `batch.py`'s own comment says so. The only remaining textual matches
are a code comment and a docstring example. The blocker did not exist, and a fresh session acting
on my handoff would have gone off to repair plumbing that was already sound — or, worse, concluded
the real work was too expensive and skipped it.

### Why a rules file is the WORST place for a stale example

- It is written to be trusted. That is the point of it.
- Nobody re-derives an example inside a hard rule; the rule is the authority.
- The example is usually the most concrete, quotable, confidence-inspiring sentence in the entry —
  so it travels further and faster than the rule it illustrates.
- And the fix that retires it lands in a DIFFERENT file, so nothing forces the rule to be updated.
  The example rots silently while the rule stays true.

### The rules

- **When you cite a measurement in a rules file, date-stamp it AND state whether it is live or
  historical.** "Measured 2026-08-13" is not enough — 2026-08-13 was two releases ago.
- **When you fix a defect, grep the rules files for its description.** The fix is not complete
  while a hard rule still describes the broken state as current. This is "leave nothing behind"
  applied to prose.
- **Before promoting an inherited example into a BLOCKER, re-run it.** A blocker is the single
  highest-leverage sentence in a handoff — it decides what the next session does first.
- Keep the example if the SHAPE recurs, but mark it: *fixed in vX, re-verified on DATE, kept
  because the shape recurs.* Both `CLAUDE.md` and `/docpluck-review` rule 0b now carry that form,
  including a note that they were themselves misread.

**The uncomfortable part:** this was caught by an outside reviewer, on a document I had written to
warn a future session about exactly this failure mode. Self-review does not catch it, because the
same reading that trusted the claim writes the summary of it.


---

## L-035 — The INSTRUMENT is a shipped component, and nothing tested it

**2026-08-15 · release-stopper · found by an independent Fable 5 review**

`tools/diag/render_deletion_scan.py` — the gate that certifies "no published statistic was
deleted" — derived its step list by scraping production's source with `^\s*md = (\w+)\(`. Correct
when written. Then v2.4.130 rewrote the chain as `md = _step(_report, "name", fn, md)`, so the
pattern returned exactly `['_render_sections_to_markdown', '_step', '_rescue_title_from_layout']`,
and the instrumenting wrapper bailed on `_step` because its first positional argument is the report
and the wrapper tested `isinstance(md, str)`.

**Zero of 53 deleting steps were instrumented. It reported "26/26 papers, 0 deletions."**

That is this project's own rule — *a zero is a claim about the INSTRUMENT until you prove
otherwise* — broken by the gate written to enforce it, in the same release. The function's docstring
boasted that deriving names from source prevents a drifted copy; **the drift happened inside the
deriving.**

Repaired (0 → 54 steps), its first genuine run found a real defect immediately: a numbered
bibliography stripped as an author-affiliation block on `10.48550/arxiv.2406.11713`. The guard
against that class already existed — its own comment says it was written after a corpus scan caught
it on 5 papers — but **both its arms were APA-shaped**, so an IEEE entry
(`[21] P. Dhariwal…, arXiv:2105.05233, 2021.`) matched neither. The class walked back in while the
instrument said zero.

**The rule.** A rule that breaks turns a test red. **An instrument that breaks turns nothing red —
it emits the same word it emits when everything is fine.** Every gate needs a known-positive test
that drives a real defect through the real production path and asserts the gate goes red; assert
its COVERAGE COUNT, not just its verdict; and make it **raise** rather than report clean when it
can see nothing. Prefer intercepting the single wrapper every step flows through over scraping
source or wrapping N module attributes.

**When you repair a blind gate, treat every "0" it ever reported as UNMEASURED** — and triage its
first real run carefully: 84 of the 93 lines this one then reported were *further* defects in the
instrument, not the corpus.

Pinned by `test_the_gate_sees_the_whole_chain_not_three_names`,
`test_the_gate_actually_records_a_deletion_driven_through_the_real_step`.

---

## L-036 — A fix can be worse than the defect it replaces

**2026-08-15 · release-stopper · reproduced against shipped v2.4.131**

v2.4.131 fixed a real, serious defect: mammoth silently deleted OMML equations, so `ηp2 = .361`
shipped as `= .361`. The fix recovered the text by concatenating every `m:t` run in document order.
Correct for a run of characters. **Catastrophic for a structured object:**

```
source: 'ratio = 1/2 of sample.'    v2.4.131 delivered: 'ratio = 12 of sample.'
```

Before the fix the fraction was deleted; after it, the library **manufactured the number 12**. By
this project's own ranking — rank defects by whether the wrong output ANNOUNCES ITSELF — the fix
made that case *strictly worse*: a deletion leaves nothing to trust, a plausible number gets parsed
and published. The same release still deleted display math (`m:oMathPara`), so **1 of the 4 OMML
papers in the fix's own measurement was still broken after the fix.**

**The rule.** When a fix converts a **deletion into a value**, the review question is not "does it
recover the case?" but **"can the value it now emits be WRONG?"** Test the fix on inputs it was not
built for; measure it against **its own stated positives** (nobody re-ran all four); and **never
fuse two numerals whose relationship you cannot name** — structures we can name emit their real
operator, structures we cannot space-join, which is lossy, visibly so, and incapable of
manufacturing a number.

---

## L-037 — Read the DIAGNOSTIC channel your libraries already emit

**2026-08-15 · critical · found by Fable 5 asking "what do our libraries tell us that we discard?"**

After two releases, a raster investigation and a 26-paper corpus measurement to discover mammoth's
OMML deletion:

```python
mammoth.convert_to_html(raw).messages
  -> Message(type='warning', message='An unrecognised element was ignored: {…/2006/math}oMath')
```

**mammoth had been naming the defect, on every affected file, for years.** The code read only
`.value`. Same shape throughout: `extract.py` runs pdftotext with `capture_output=True` and never
reads `result.stderr`; `camelot_extract.py` catches exceptions but not the `warnings.warn` signals
Camelot uses for *"No tables found in table area"*. **docpluck built three telemetry systems of its
own while discarding the telemetry its dependencies already emitted.**

**The generalisation, same day:** before designing any new lookup, ask what the library that
produced this data structure already computes and hands you for free. Camelot builds a full
per-cell coordinate grid (`Table.cells`) as a side effect of table detection; docpluck hardcoded
every cell box to `(0,0,0,0)` (`camelot_extract.py:562`) and three reviewers then independently
designed ways to *reconstruct* it. Camelot also exposes a purpose-built
`Table.confidence = (accuracy/100)×(1−whitespace/100)`; docpluck recomputes a worse one from
accuracy alone, so a 95%-accurate but 80%-empty capture reports **0.95** where Camelot says
**0.19** — shipping today, in a field consumers read.

**Detection:** for every third-party call, if the code binds `result` and reads one field, open the
library's source and list what else is on that object. Four places to look — a messages/warnings
object; `stderr`; Python `warnings` (catching exceptions does NOT catch warnings); and quality/score
fields the library already computes.

Full inventory and status: `docs/OVERHAUL_REGISTER.md`.

---

## L-038 — Reconcile against the FINDINGS list, never the STEP list

**2026-08-15.** The prior handoff carried both a **§3 "CONFIRMED OPEN — verified, not yet fixed"**
table (O1–O12) and a **§5 "What's next — ordered, concrete"** step list. The execution run followed
§5 faithfully and **§5 never referenced §3**. Six confirmed, reproduced, written-down defects were
left untouched while the run reported itself complete against its own plan.

Two independent audits, asked *"which of these are STILL PRESENT?"* and explicitly told not to
trust any document's status claim, found those six plus **eight more nobody had listed**.

**Why it survives:** the plan is the artifact you check completeness against. When the plan is also
what dropped the item, the check is circular — the same shape as "never adjudicate a tool's defect
using that same tool", applied to plans rather than extractors. Nothing fails; the verdict is green.

**The rule.** Before declaring any run complete, walk **every prior open-item table** and mark each
FIXED / OPEN / PARTIAL with `file:line`. A handoff's step list must be a **superset** of its open
findings, or must state which findings it defers and why. An unmentioned finding is a dropped one.

**And when a user asks "are you sure?", treat it as a live hypothesis that you are not.** That
question is what found this.

---

## L-039 — A rule whose premise is another step's behaviour breaks on the path where that step is skipped

**2026-08-15.** `normalize_text("the value 10⁹", academic, preserve_math_glyphs=True)` returned
`"the value 10"` — **a billion-fold error in a published number, booked as `footnotes_removed: 1`.**

Neither step was wrong alone. **A5** rewrites superscripts to caret form and is **skipped** when
`preserve_math_glyphs=True` (the trace literally says `A5_skipped_preserve_math_glyphs`). **A6**
deleted a superscript after `[\d\]\)]`, justified by its own comment — *"Note: A5 already converted
² -> 2"*. That comment is **a claim about A5's behaviour, and it was false on one of two paths.**

**The inversion is how to spot the class:** a genuine footnote marker after a word
(`Smith et al.¹`) never matched the pattern at all. The rule **spared the case it was written for
and destroyed the case another rule in the same file warns about** — `W0p`'s docstring says
"deleting the wrong one loses nine orders of magnitude", three thousand lines away.

**The rule.** A comment asserting what an earlier step did is a claim about the call graph **under
every flag combination**; grep the flag and check the skipped path. Prefer rules whose correctness
is *local*: A6 now keys on `[\]\)]` alone, because nothing exponentiates a closing bracket, so it
no longer depends on what ran before it. Test every rule under each flag that can skip a neighbour.
And cross-check the telemetry NAME against the effect — "footnotes_removed" while deleting an
exponent is a false all-clear, which is worse than silence because silence invites a check.

Known and written down on 2026-08-13; unfixed until an audit reproduced it. See L-038.

---

## L-040 — Write-only telemetry is not telemetry

**2026-08-15.** The library had **31 `record_fallback(...)` call sites**; `get_fallback_counters()`
was called by **one test and nothing else**. Every silent substitution, dropped table and refused
repair went into a process-global Counter no consumer read.

**The sting:** that included the `w0h_ambiguous_pairing_refused` signals added *hours earlier in the
same session*, whose whole justification was *"refusing is safe because we record it."* The refusal
was safe; the recording went nowhere. A safety property had been built on a channel that did not
exist, and then cited in a CHANGELOG.

This is the fourth of the four checks — *every value computed is read back* — failed across a whole
subsystem, and the sibling of L-037: there we discarded a **library's** diagnostics, here our own.

**The rule.** When you add a `record_*` / `log_*` / `_track` call, **grep for a NON-TEST reader of
that channel in the same change**. No reader means you added a comment, not telemetry. Never
justify a behaviour on a channel you have not confirmed reaches someone. Process-global cumulative
counters need a snapshot/delta helper or every consumer reinvents it wrongly
(`telemetry.fallback_snapshot` / `fallbacks_since` / `fallback_scope`).

Wiring it was immediately informative: **8–26 tables per paper** are dropped by the table-likeness
gate, previously invisible.

---

## L-041 — A fix moves what a gate SEES, not just what a consumer gets

**2026-08-15, v2.4.133 → v2.4.134.** Moving `clean_cell_text` to cell CONSTRUCTION fixed a real
divergence: `flatten`, `cells[].text` and `raw_text` had shipped corrupt values while the rendered
`<table>` showed repaired ones. The fix was right and the placement was not, because the capture
paths run their **structural gates on the cells they have just built**. Repairing before the gates
changed what the gates judge, and one predicate moved in the deleting direction: the W0i class
prints `×` as `3`, so the raw label `Direction 3 manipulated attribute` carries a digit and reads as
DATA while the repaired `Direction × manipulated attribute` reads as PROSE. Three consecutive such
rows form a prose run and the trim cuts **from the first of them to the end of the grid**.

Two independent reviewers both found the mechanism; one called it "unmeasured, ship", the other
"content vanishes, do not ship". The execution run before them tried three times to reproduce it and
failed — the missing condition was simply that the rows be CONSECUTIVE.

**The rule.** When you move a transformation earlier in a pipeline, list every predicate downstream
of the new position and ask which of them changes verdict. "It only changes what consumers receive"
is a claim about the data flow that is false whenever a gate reads the same structure.

**And split gates by what a rejection COSTS**, rather than applying one policy:

* a predicate that DELETES content (prose trim) must not be flippable INTO deleting by a repair —
  require both the raw and repaired forms to agree;
* a predicate that decides VALIDITY (is this grid publishable at all?) should judge the repaired
  form, because that is the text you actually ship, and rejecting there costs a table you could
  have published rather than rows you silently drop.

**Corollary — fix the vocabulary, not only the seam.** The root cause was that `_STAT_TOKEN_RE`, the
evidence that a row carries data, did not include `×` — the notation the repair chain *itself
emits*. A repair chain and the predicates that read its output share a vocabulary; when one grows a
token, the other must learn it.

---

## L-042 — Quote a number only with the command that regenerates it

**2026-08-15.** Three documents asserted that corrupt shapes "came from the symbol font **64/68**
while real digits came from the body font **135/135**". Nothing in the repo produced those figures.
The register replaced them with "**9** differ, **2** match, no overlap" — and **that did not
reproduce either**: re-measured on the same paper it gives **10 differ, 6 match, and the font sets
DO overlap**.

Neither figure was fabricated. Both were **per-token ratios whose enumeration method was never
written down**, so neither could be re-run — and the correction reproduced the exact defect it was
written to fix, in the same file, within one day.

**The rule.** A measurement in a document is a claim until a command regenerates it. Either commit
the probe and name it at the point of quotation, or date-stamp the number as historical. The
replacement here is method-independent and stark — `AdvTimes` 35,682 glyphs / 86 distinct
characters vs `AdvP586B` 124 / 3 (`'2'`×99, `'3'`×24, `'.'`×1) — and ships as
`tools/diag/symbol_font_census.py`.

**Related:** a *zero* is a claim about the instrument (L-033). This is its sibling: a *ratio* is a
claim about the enumeration.

---

## L-043 — The idempotency gate catches what reading the rule cannot

**2026-08-15.** `_ALREADY_SIGNED` is a one-character negative lookbehind, so it refuses `-0.38` and
**accepts** `- 0.38`. On a detached sign W0g read the estimate as bare-positive, proved it negative
from its CI, and emitted `d = - -0.38` — a double-signed effect size no paper printed.

The comment directly above that constant records that `-2.68 -> --.68` had **already happened** in
v2.4.62, and states that *"the fix then covered the one dash form in front of us"*. It covered the
ATTACHED form. Nobody asked what the DETACHED one would do, on fonts whose defining behaviour is
detaching glyphs from their digits.

It surfaced only because an unrelated repair made one paper's CI parseable, which let W0g reach an
estimate it had never been able to see, and `test_normalize_idempotent_corpus` went red. No unit
test, no hand battery and no reading of the regex would have found it.

**The rule.** Run the idempotency corpus gate after ANY change to a text-rewriting rule, including
changes that only make *more input reachable*. A rule that fabricates a value usually reveals itself
as non-idempotence long before it reveals itself as a wrong number, because pass 2 feeds the rule
its own output — which is the one input nobody writes a fixture for.

**Corollary:** widening what a rule can see is a change to every rule downstream of it.

---

## L-044 — A documented flake is a failure nobody re-investigates

**2026-08-16.** Nine real-PDF table tests failed in every full-suite run and passed when run
per-file. This was written up in `CLAUDE.md`, in a memory, and in three handoffs as *"Camelot tests
flake under cumulative load (even serial)"*, with the standing workaround **"run each file
separately"**.

It was **36 test modules calling `os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")` at module
scope**. That runs during COLLECTION, before any test executes, and was never undone — so importing
any one of them disabled Camelot for the whole process and every table test collected afterwards
found no tables. Reproducible in 48 seconds with two files.

**The write-up was load-bearing in the wrong direction.** It attributed an ordinary state leak to a
third-party library, gave it a plausible mechanism ("cumulative load"), and supplied a workaround
good enough that nobody paid the cost again. Every subsequent session — including the one that
finally found it, for most of its length — repeated the explanation instead of testing it.

**The rule.** A "known flake" is an UNDIAGNOSED BUG with a story attached. Before repeating one:

1. **Bisect it.** Order-dependence and load-dependence are distinguishable in minutes — run the
   failing file after progressively smaller prefixes. If a two-file combination reproduces it, it
   was never load.
2. **Ask what the workaround implies.** "Run each file separately" is a statement that state crosses
   files. That is a bug description, not a property of the test subject.
3. **Never let a flake justify a green.** A suite with a documented flake cannot certify anything,
   because the next real regression arrives wearing the same clothes.

**Corollary — a per-test guard cannot catch a module-scope mutation**, because the mutation happens
before the first test's snapshot. Guard collection separately (`pytest_configure` /
`pytest_collection_finish`); see `tests/conftest.py`.

---

## L-045 — A skipped test is a coverage hole wearing a green tick

**2026-08-16.** 21 test modules resolved their fixtures under `~/Dropbox/Vibe`, the portfolio root
abandoned on 2026-08-03. `conftest.py` had the correct `VIBE_ROOT`-aware resolver all along; these
files bypassed it with their own hardcoded path. Their fixtures therefore "were not present" and the
tests **skipped silently** — on a machine where those exact PDFs sit at the current root and were
being read successfully by other code in the same session.

The count was reported for months as "147 skipped", alongside "2,582 passed", as though the two were
comparable facts. They are not: a skip is a test that did not run.

This is the failure mode `CLAUDE.md`'s own never-hardcode-the-root rule warns about in as many
words — *"a discovery helper that returns empty when the root is wrong makes a broken run look like
a clean one"* — and an earlier commit had fixed exactly this class in the snapshot suite and stopped
there.

**The rule.** Treat the skip COUNT as a metric with a budget, not as background noise. Any skip
whose reason is "fixture not available" is a claim about the machine that must be checked against
the machine — `ls` the path. And when a root moves, `grep` for the OLD root across the whole tree,
not just the file that reported the symptom.

**Detection:** a suite summary line quoting skips next to passes without a reason breakdown. Run
`pytest -rs` and group the reasons; a dozen tests skipping for one stale path is one bug, not
twelve.

## L-046 — A revert is a CLAIM, and its example is the first thing to re-measure

**2026-08-19.** Three gold-verified text-loss defects sat behind `xfail(strict)` markers because a
fix for each had been attempted and reverted as net-harmful. The revert of the row-clustering fix
was justified in `docs/FINDINGS_2026-08-04_row_cluster_chain_merge.md` by one sentence:

> a real row can legitimately be TALL: xiao Table 4's row 2 spans **94.4pt** as a multi-line
> stacked data block

Re-measured with `python tools/diag/row_cluster_census.py`: that "row" is the **entire table body** —
the stacked header, all five product rows and all five CI continuation lines, 75 words — and the
grid was rejected on its own merits, so `xiao_2021_crsp` Table 4 emitted **`cells=0`**. The example
held up as the *legitimate* case that made the fix unsafe was itself the defect. With the fix it is
7 rows / 35 cells, matching the printed page.

The prohibition then propagated: into the findings doc, into the test's `xfail` reason, into the
handoff's "why it is hard" column, and into four geometric discriminators designed and rejected
*around* a constraint that did not exist. Nobody re-opened the PDF.

**The rule.** Same standard as [[feedback-inherited-bans-are-claims-recheck-by-counting]], stated
for reverts specifically: **a revert names a counter-example, and the counter-example is a
measurement that can be wrong.** Before designing around it, re-run it. One command here; four
abandoned discriminators and two sessions otherwise.

**Detection:** any "we tried X and it broke N tests" carried across sessions without the numbers
re-derived. If the doc names a specific paper and table, open that table.

## L-047 — A repair can re-create, through its own remedy, the defect it repairs

**2026-08-19.** The chain-merge fix above needed a second half: the anchor rule can split a wrapped
cell away from its own row, so an indented, single-baseline, vertically-contiguous line was folded
back into the row above it. Every condition was individually defensible and it passed the unit
tests, the 9 previously-broken real-PDF tests, and all three defect tests.

The corpus guard-diff said **21 tables lost cells (−867) and 12 lost raw_text**.

Cause: each fold EXTENDED the row, so the contiguity test compared the next line against an
ever-lower bottom edge and could never fail. On `10.1111/jomf.13036` Table 6 the data rows are
labelled `1`, `2`, `3`, `4+` in a column indented past `Overall childhood disadvantage`, so all five
read as continuations and folded into a single 75pt row — **an unbounded chain merge, produced by
the fix for unbounded chain merges.** Re-anchoring the test on the preceding LINE did not save it
either: inter-line leading is only ~3pt, so the bound never bit. It was deleted, not tuned; over the
whole corpus it bought one correct fold.

Two further defects surfaced in the same guard-diff, both in remedies rather than in the original
code: the prose-plausibility guard condemned a real 33×4 qualitative review table
(`10.5465/amc.2022.0006` Table 4, 70 cells and 2,008 characters), and — worse — when it rejected, the
fallback produced **nothing**, so the "guard" was a deletion. Fixed with a header-row veto and by
making the rejection provisional: the candidate is stashed and restored unless a replacement
actually materialises.

**The rule.** A remedy is new code and gets the same adversarial reading as the code it replaces.
Ask specifically: *can this remedy exhibit the defect class it targets?* And **never let a guard
trade content for emptiness** — a rejection is only a rejection when something takes the rejected
thing's place; otherwise it is a deletion wearing a guard's name (the `render.py` finding of
[[L-032]], one layer up).

**Detection:** a fix that accumulates state while deciding (`prev.extend(...)` then testing against
`prev`). A monotone accumulator inside a stopping condition is a stopping condition that does not
stop. And: unit tests plus targeted real-PDF tests are not a gate for a capture-path change — only a
corpus before/after is. All three defects here were invisible to 31 green tests.

## L-048 — A gate's VERDICT RULE is a claim like any other, and it can be wrong benignly

**2026-08-19.** `tools/diag/table_capture_guard_diff.py` was built to answer "did this capture-path
change make table content DISAPPEAR". Its verdict rule was `cells_lost > 0 -> FAIL`. It flagged 5
tables and printed `VERDICT: FAIL - content regressed`. **All five were improvements.**

* `10.1016/j.joep.2020.102350` T1 lost the running header `I. Ziano et al.` and the journal footer —
  **furniture leaving a table is the correct direction**;
* `10.1016/j.jesp.2009.12.010` T3 went 4 cells to 0 while its text went 148 to **345** characters,
  because the 4 cells were fused (`4.603.804.80`) and missing a whole condition row;
* `10.1177/01461672251327169` T3/T4 the same, one of them publishing `104594` — a sample size of 104
  and one of 594 glued into a number the paper never printed;
* `10.48550/arxiv.2406.11713` T5 went 18 cells to 14 because the 18 were half body prose.

Cell count answers *"did the grid shrink"*, which is a different question, and it falls legitimately
in at least three ways one 26-paper corpus exhibits. **No counter separates those from a real loss.**

The danger is not the wasted time. It is that a gate crying wolf five times produces a five-item
punch-list of imaginary defects, and the only thing that stopped it here was opening every table.
The next reader would have "fixed" five non-problems.

**The rule.** A gate that cannot be wrong in the BENIGN direction is a gate nobody will keep running.
State what a flag MEANS, not what it proves: this one now reports **FLAGGED FOR INSPECTION** with a
`content chars` column beside the cell count, exits non-zero so flags cannot be skipped, and carries
the four measured benign examples in its own docstring so the next reader need not re-derive them.
And **correcting a mis-specified metric is not the same as tuning a gate until it passes** — the
test is whether you can state the metric's question independently of this run's result.

**Detection:** a gate whose verdict is a bare inequality on a proxy. Ask what else moves that proxy.

## L-049 — Re-run the gate on the tree you intend to SHIP, not the tree that was reviewed

**2026-08-19.** Three defects were found in one release's own remedies, one at each verification
stage, and each was invisible to the stage before it:

| stage | what it caught | invisible to |
|---|---|---|
| corpus guard-diff | the continuation re-merge CHAINED, re-creating the chain merge it repaired (−867 cells) | 31 green targeted tests |
| two independent reviewers | pass 3 returned a label-only bbox (35pt for a 247.6pt caption); the header veto was buyable with one short cell | the guard-diff, which measures content and not bbox geometry |
| corpus guard-diff **again** | the guard destroyed `10.48550/arxiv.2406.11713` Table 1's published FID values (27 cells → 0, 511 chars → 61) | both reviewers, because it did not exist when they read the tree |

The reviewers read tree *N*. Their fixes made tree *N+1*. The gate had only ever run on *N*. A
reviewer's finding is a change like any other, and **a fix made in response to review is the least
tested code in the release** — it is written last, under time pressure, with the reviewer's framing
rather than the corpus's.

**The rule.** Freezing the tree for review is right; treating the review's OWN fixes as pre-verified
is not. Run the full gate again after the last edit, however small, and budget for it.

**Detection:** any release where the final gate run predates the final commit. Compare timestamps.

## L-050 — A fix that names its own blast radius is still claiming, and the claim is checkable

**2026-08-19.** v2.4.134 fixed a temp-PDF leak in `camelot_extract.py` and wrote, in the source,
next to the fix:

> `BOTH call sites, because a fix applied to one of two is not fixed, and this module has a
> documented history of exactly that.`

The sentence is a claim about scope, it was made by the author of the fix, and nobody ran the grep
that decides it. `NamedTemporaryFile(suffix=".pdf", delete=False)` returns **five** sites in
`docpluck/`. The fix covered two. The remaining three were `extract.py` — the library's primary text
entry point, unlinking with **no exception handling at all** — and two silent `except: pass` blocks
in `extract_columns.py`.

What makes this worth a lesson is not the miss; it is that the miss came wearing the exact language
of thoroughness. "BOTH call sites" scopes the claim to the module without saying so, and a reader —
including the author, a week later — reads it as the library. The comment's own reference to a
"documented history of exactly that" is what makes it persuasive, and the history repeated inside the
sentence claiming to have learned from it.

**Two of the project's standing rules already covered this and neither fired**, because both were
read as being about the code rather than about the comment:

* *AUDIT EVERY CHANNEL, not the one you were looking at* — the audit named `camelot_extract.py`, so
  its coverage was never measured. The uninstrumented channel is where the defects are.
* *A description is not the thing it describes* — a source comment is a claim with a citation. The
  citation here is a grep. It takes four seconds.

**The rule.** When a fix states its own scope — "both", "all", "every call site", "the only place
this happens" — that sentence is the first thing to verify, and it is verifiable mechanically. Run
the enumeration the claim implies and paste the count. If the count and the claim disagree, the
claim is the defect.

**Detection:** grep the diff for `both`, `all `, `every`, `the only`. Each occurrence is an
enumeration somebody asserted without running.

## L-051 — A release gate that only runs the library's own suite is blind to its consumers

**2026-08-20.** `/ship` ran the docpluck library suite: **2840 passed, 0 failed**. It then ran the
**docpluckapp service suite**, which imports the library through an editable install:
**13 failed, 154 passed.**

Every one of the 13 asserted a rule docpluck had deliberately retired — A2 (dropped-decimal repair,
deleted v2.4.130), A3 (EU→US decimal comma, retired with the locale feature), and A5's v1.0 symbol
conventions (`x` for `×`, `F1` for `F₁`). The library repo carries the same normalization suite and
**its copy was updated as each rule retired**. The second copy was not, and nothing compares them.

It had been red against a healthy library for three releases, and the app pin had just been bumped
to `v2.4.135`, so the app's tests encoded a contract production no longer honoured.

**Two failure modes, and the second is the expensive one:**

1. The obvious one — the app's CI is broken.
2. The one that costs months — **a suite that reports FAIL on a healthy tree trains everyone to
   skim past failures.** That is precisely the mechanism behind L-044: the "Camelot cumulative-load
   flake" survived as folklore because failures on a healthy tree had become normal.

**The rule.** "One concept, one table" applies to TESTS. When a release retires a behaviour, grep
for its assertions across **every repo that imports the library**, and run the CONSUMER's suite as
part of the release gate. The library's own green suite is structurally blind to this class: each
repo's tests are internally consistent, and the drift lives at the seam.

**And when you fix them, do not weaken a test to match a bug.** Each inverted expectation here was
checked against `docs/SYMBOL_CONTRACT.md` and `docs/SCOPE.md` first — `×`→`*` and `F₁`→`F_1` turned
out to be deliberate v2.0 decisions with recorded reasons, not drift.

**Detection:** `grep -rl "<retired-token>" <consumer-repo>` at retirement time; and a release gate
step that runs each consumer's suite against the tag being shipped.
