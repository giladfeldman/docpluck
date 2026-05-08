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

## When to add a new lesson here

Add a lesson when:
- A Claude session (or you) tried to fix a problem and ended up reverting because the fix broke many other things.
- The same wrong reasoning has surfaced ≥2 times across sessions.
- A choice that looks "obviously wrong in retrospect" has historical context that explains why the alternative was tempting.

Format: short surface description, the failed attempt, the rule.  Cite specific files and dates so future readers can git-blame the actual change.
