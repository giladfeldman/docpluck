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

## When to add a new lesson here

Add a lesson when:
- A Claude session (or you) tried to fix a problem and ended up reverting because the fix broke many other things.
- The same wrong reasoning has surfaced ≥2 times across sessions.
- A choice that looks "obviously wrong in retrospect" has historical context that explains why the alternative was tempting.

Format: short surface description, the failed attempt, the rule.  Cite specific files and dates so future readers can git-blame the actual change.
