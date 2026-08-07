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

## When to add a new lesson here

Add a lesson when:
- A Claude session (or you) tried to fix a problem and ended up reverting because the fix broke many other things.
- The same wrong reasoning has surfaced ≥2 times across sessions.
- A choice that looks "obviously wrong in retrospect" has historical context that explains why the alternative was tempting.

Format: short surface description, the failed attempt, the rule.  Cite specific files and dates so future readers can git-blame the actual change.
