# Design — Section Identification + Layout-Aware Footnote Detection

**Date:** 2026-05-06
**Source request:** User brainstorm — "level above normalization" that identifies academic-paper sections (abstract, introduction, methods, results, references, disclosures, etc.) and lets callers request only certain sections. Sister problem: footnotes/running-headers intruding into body text after PDF extraction.
**Version:** Docpluck `1.5.x` → `1.6.0`
**Status:** Design approved by user 2026-05-06 (this conversation). Implementation plan to follow.

---

## 1. Problem & motivation

Docpluck today exposes three layers — `extract` (PDF/DOCX/HTML → text), `normalize` (S0–S5 standard, A0–A7 academic cleanup), `quality` (scoring). All operate on the document as a single undifferentiated string. Consumers who want only the abstract, only the references, or only the methods must do their own ad-hoc string slicing.

CitationGuard solved this *just for the references section* in `apps/worker/src/processors/referenceParser.ts` (~2,250 lines), with `findReferenceSectionStart` (17 header regexes) + `extractReferenceSection` (~25 end-of-section patterns). That logic is duplicated, fragile, and locked inside the SaaS app rather than the OSS library.

Two further pain points:

1. **Footnote intrusion.** When a section spans pages and the page break sits between body text and footnotes, `pdftotext` collapses the footnote into the body. The abstract on page 1 ends up with footnote 1 appended; methods on pages 5–6 contains a stray "23 corresponding author email…" line. Page-number stripping (R2 in `normalize.py`) catches a subset, but most footnote intrusions survive.
2. **Running headers/footers** that don't match the page-number pattern (e.g. journal name + DOI on every odd page) likewise survive.

Both are consequences of doing structure-aware work on text that has lost its layout.

**Goal of this design:** add a fourth layer (`sections`) above `normalize`, and give `normalize` the optional layout context it needs to strip footnotes and running headers cleanly.

## 2. Scope

### In scope (v1.6.0)

- New `docpluck.sections` package producing `SectionedDocument` from PDF/DOCX/HTML.
- Universal-coverage partitioning into 18 canonical labels + `unknown` fallback + `study_n_header` structural markers.
- Two-tier algorithm: format-aware annotators (PDF / DOCX / HTML) + unified canonicalizer.
- Layout-aware PDF extraction via pdfplumber (already a dep) → new internal `extract_pdf_layout()` returning a `LayoutDoc`.
- New `F0` step in `normalize` that strips footnotes + running headers + running footers when a `LayoutDoc` is supplied. Footnote text is preserved, surfaced as the `footnotes` section.
- Per-section confidence (`high`/`medium`/`low`), per-section `detected_via` provenance, per-section page tuples.
- `extract_sections(file_or_text)` top-level helper.
- Filter sugar on existing `extract_pdf` / `extract_docx` / `extract_html` (`sections=["abstract","references"]`).
- CLI: `docpluck extract --sections abstract,references paper.pdf`, `docpluck sections paper.pdf [--format json|summary]`.
- `SECTIONING_VERSION` constant, recorded on every `SectionedDocument`.

### Explicitly out of scope (deferred — see §10 and `TODO.md`)

1. Hierarchical / tree output (Q2 option C from brainstorm).
2. Splitting `title_block` into `title` / `authors` / `affiliations`.
3. Custom heading-map / user-supplied taxonomy extension API.
4. Re-validation of the conflict-resolution rule (text wins for canonical, layout wins for unknown — Q4.vi).
5. Public `extract_pdf_layout()` API. It exists internally for v1; we don't promise its shape externally.
6. PyMuPDF-based extraction. Off the table — AGPL incompatible with docpluck's MIT license.

## 3. Architecture

### 3.1 Module layout

```
docpluck/
  extract.py              ← unchanged public API
  extract_layout.py       ← NEW: pdfplumber → LayoutDoc
  normalize.py            ← gains 1 new step: F0 footnote/header strip;
                            NormalizationReport gains footnote_spans, page_offsets fields
  sections/               ← NEW package
    __init__.py           ← public API: extract_sections(), SectionedDocument, etc.
    core.py               ← unified canonicalizer + universal-coverage partitioner
    annotators/
      __init__.py
      pdf.py              ← font-size + position-based heading detection
      docx.py             ← <h1>-<h6> from mammoth HTML output
      html.py             ← <h1>-<h6> + <section>/<article>
      text.py             ← regex-based fallback (used by all three)
    taxonomy.py           ← canonical labels enum + heading-text → label map
    boundaries.py         ← end-of-section patterns (lifted from CitationGuard)
```

`sections/` is a package because the v1 LOC estimate (~1,500–2,000) puts it above the comfortable single-file ceiling. `normalize.py` is currently 637 lines — the F0 step plus the new fields can live there without splitting. `extract_layout.py` is its own file because pdfplumber is heavier than the existing `extract.py` dependencies and isolating it makes the `extract_pdf()` fast-path obviously unaffected.

### 3.2 Pipeline composition

```
file bytes
  │
  ▼  extract_pdf_layout()                  (PDF only; DOCX/HTML have markup)
LayoutDoc { pages: list[PageLayout], raw_text: str }
  │  raw_text is byte-identical to current extract_pdf() output
  ▼  normalize_text(raw_text, level, layout=LayoutDoc | None)
NormalizedText { text, steps_applied, footnote_spans, page_offsets }
  │
  ▼  extract_sections(normalized + layout hints)
SectionedDocument
```

### 3.3 Two-tier sectioning algorithm

```
                       TIER 1 — format-aware annotators
   ┌────────────────────────────────────────────────────────┐
   │  PDFLayoutAnnotator   → list[BlockHint]                │
   │  DOCXMarkupAnnotator  → list[BlockHint]                │
   │  HTMLMarkupAnnotator  → list[BlockHint]                │
   └────────────────────────────────────────────────────────┘
                              │
                              ▼  list[BlockHint]
   ┌────────────────────────────────────────────────────────┐
   │  TIER 2 — unified core (sections/core.py)              │
   │   1. Map heading_text → canonical SectionLabel         │
   │   2. Resolve text-vs-layout conflicts (Q4.vi rule)     │
   │   3. Apply end-of-section boundary patterns            │
   │   4. Assign numeric suffixes for repeats               │
   │   5. Partition into universal-coverage spans           │
   │   6. Assign confidence + detected_via                  │
   └────────────────────────────────────────────────────────┘
                              │
                              ▼
                      SectionedDocument
```

Tier 2 is format-agnostic. All canonicalization logic lives there exactly once. Each Tier 1 annotator is a thin module that knows how to read its format and emit `BlockHint`s.

## 4. Data model

```python
class SectionLabel(str, Enum):
    # Front matter
    title_block = "title_block"
    abstract = "abstract"
    keywords = "keywords"
    author_note = "author_note"
    # Body
    introduction = "introduction"
    literature_review = "literature_review"
    methods = "methods"
    results = "results"
    discussion = "discussion"
    general_discussion = "general_discussion"
    # Back matter
    acknowledgments = "acknowledgments"
    funding = "funding"
    conflict_of_interest = "conflict_of_interest"
    data_availability = "data_availability"
    author_contributions = "author_contributions"
    references = "references"
    appendix = "appendix"
    supplementary = "supplementary"
    # Special
    footnotes = "footnotes"
    unknown = "unknown"
    study_n_header = "study_n_header"   # actual labels: study_1_header, study_2_header...

class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"

class DetectedVia(str, Enum):
    heading_match = "heading_match"
    markup = "markup"
    layout_signal = "layout_signal"
    text_pattern_fallback = "text_pattern_fallback"
    position_inferred = "position_inferred"

@dataclass(frozen=True)
class Section:
    label: str                       # e.g. "methods", "methods_2", "study_1_header"
    canonical_label: SectionLabel    # base without numeric suffix
    text: str
    char_start: int                  # offset into normalized text
    char_end: int
    pages: tuple[int, ...]           # 1-indexed; () if unavailable
    confidence: Confidence
    detected_via: DetectedVia
    heading_text: str | None         # literal heading found, if any

@dataclass(frozen=True)
class SectionedDocument:
    sections: tuple[Section, ...]    # ordered, contiguous, universal-coverage
    normalized_text: str
    sectioning_version: str
    source_format: Literal["pdf", "docx", "html"]

    def get(self, label: str) -> Section | None: ...      # first match
    def all(self, label: str) -> tuple[Section, ...]: ... # all matches
    def text_for(self, *labels: str) -> str: ...          # concat in document order

    # Convenience properties — only the 6 high-traffic ones:
    @property
    def abstract(self) -> Section | None: ...
    @property
    def introduction(self) -> Section | None: ...
    @property
    def methods(self) -> Section | None: ...
    @property
    def results(self) -> Section | None: ...
    @property
    def discussion(self) -> Section | None: ...
    @property
    def references(self) -> Section | None: ...
```

### Design decisions captured (per user's 2026-05-06 request to document carefully)

- **Universal coverage with `unknown` fallback** rather than `None`-returning fields. Reason: cleaner partition (every char accounted for); `unknown` surfaces unrecognized content rather than silently dropping it; downstream concatenation is deterministic; matches GROBID's "every block has a label" model.
- **Numeric suffixes for repeats** (`methods_2`) rather than merging or hierarchical grouping. Reason: preserves multi-study structure with minimal data-model complexity; tree mode (Q2.C) was deferred. `doc.methods` returns the first match (covers the simple case), `doc.all("methods")` returns all (covers the multi-study case).
- **6 convenience properties, not 18.** Reason: 18 properties pollutes autocomplete and creates cargo-cult equality; the long tail (e.g. `data_availability`) is fine via `doc.get("data_availability")`. Mirrors `dict.get()`.
- **`NormalizationReport` field-additions, not a new function.** Adding `footnote_spans=()`, `page_offsets=()` with defaults is non-breaking. A new `normalize_text_full()` would create two near-identical functions that drift apart.
- **Title block stays merged in v1.** Splitting into title/authors/affiliations is a separate hard problem (affiliation parsing). Consumers who need structured authors should use CrossRef/DOI lookup, not docpluck. (TODO.)
- **Hardcoded taxonomy in v1.** Custom heading maps are deferred — we want to see real-world misses on Hebrew / non-English / domain-specific journals before designing an extension API. (TODO.)

## 5. Detection algorithm

### 5.1 Heading detection (Tier 1)

Each annotator emits:

```python
@dataclass
class BlockHint:
    text: str
    char_start: int
    char_end: int
    page: int | None
    is_heading_candidate: bool
    heading_strength: Literal["strong", "weak", "none"]
    heading_source: Literal["markup", "layout", "text_pattern", None]
```

**PDF annotator (`annotators/pdf.py`)** — uses `LayoutDoc`:

- Body-text font size = mode of all char font sizes weighted by char count.
- `strong` heading candidate when **all** of:
  - font size ≥ 1.15× body, OR bold + ≥ 1.05× body
  - ≤ 12 words
  - line ends in `\n` (not mid-sentence)
  - no terminal period, OR explicit numbering (`^\d+(\.\d+)*\s+[A-Z]`)
- `weak` heading candidate when:
  - ALL CAPS or Title Case
  - ≤ 8 words
  - preceded and followed by blank line
  - layout signal ambiguous (font same as body but isolated)
- Numbered headings always `strong` regardless of font.

**DOCX annotator (`annotators/docx.py`)** — mammoth's HTML output already includes `<h1>`–`<h6>` for "Heading 1"–"Heading 6" paragraph styles. Direct mapping: `<h1>`–`<h3>` → `strong`, `<h4>`–`<h6>` → `weak`. Falls back to text annotator when DOCX uses ad-hoc bold instead of real Heading styles (~15% of academic DOCX submissions in author-draft experience).

**HTML annotator (`annotators/html.py`)** — `<h1>`–`<h3>` → `strong`, `<h4>`–`<h6>` → `weak`. `<section>`/`<article>` boundaries are reinforcing signals but not standalone.

**Text annotator (`annotators/text.py`)** — fallback used by all three when stronger signals are absent. Patterns lifted from CitationGuard's `headerPatterns` plus extensions:

- `^\s*(?:\d+\.?\s*)?(References|Methods|Abstract|...)\s*$`
- `^#+\s+\w+` (Markdown-ish)
- `^\w+\s*\n[-=]{2,}` (underlined)
- `^R\s*E\s*F\s*E\s*R\s*E\s*N\s*C\s*E\s*S$` (spaced-out caps)

### 5.2 Canonical label mapping (Tier 2)

A single hardcoded `taxonomy.HEADING_TO_LABEL` table:

```python
HEADING_TO_LABEL: dict[frozenset[str], SectionLabel] = {
    frozenset({"abstract", "summary"}): SectionLabel.abstract,
    frozenset({"keywords", "key words", "keyword"}): SectionLabel.keywords,
    frozenset({"introduction", "background"}): SectionLabel.introduction,
    frozenset({"method", "methods", "materials and methods", "materials & methods",
               "experimental procedures", "methodology", "experimental design"}):
        SectionLabel.methods,
    frozenset({"results", "results and discussion", "findings"}): SectionLabel.results,
    frozenset({"discussion", "general discussion"}): SectionLabel.discussion,
    frozenset({"references", "bibliography", "works cited", "literature cited",
               "literature", "cited literature", "reference list",
               "list of references"}): SectionLabel.references,
    frozenset({"conflict of interest", "conflicts of interest", "competing interests",
               "declaration of interest", "disclosure", "disclosures", "declarations",
               "competing financial interests"}): SectionLabel.conflict_of_interest,
    # ... ~80–100 entries total
}
```

Lookup is case-folded, whitespace-collapsed, punctuation-stripped before matching. `frozenset` allows one-pass O(1) lookup against multiple variants per canonical label.

### 5.3 Conflict resolution (Q4.vi rule)

| Heading text | Layout strength | Result |
|---|---|---|
| canonical match | any | use canonical label, `confidence=high` if layout `strong` else `medium` |
| unrecognized | `strong` | new partition span, label `unknown`, `confidence=low` |
| unrecognized | `weak` / `none` | no new span; treated as body text |

**TODO (per user):** revisit this rule after MVP testing on the test corpus. May need refinement once we see real failures.

### 5.4 End-of-section boundary detection

Lifted and consolidated from CitationGuard `endPatterns` (~25 patterns) into `sections/boundaries.py`. These close a section *only when no heading is found before the next boundary* — primary signal is the next strong heading; boundaries are secondary.

Boundary patterns include:
- Author bio blocks (`^[A-Z]{2,}(?:\s+[A-Z]\.?)*\s+(?:is|was|has|holds)\s`)
- Figure/table captions (`^(Figure|Table)\s+\d+`)
- ORCID / corresponding-author lines (`^Corresponding author\b`, `^ORCID\b`)
- Email/affiliation contact (`^(?:Address|E-?mail|Tel|Fax)\s*:`)
- Editorial metadata (`^(?:Accepted by|Action Editor|Received|Revised|Published)\s*:?\s`)

### 5.5 Universal-coverage partitioning

After Tier 2 has a list of `(char_start, label, confidence)` markers in document order:

1. Sort markers by `char_start`.
2. Each marker starts a span; the span ends at the next marker's `char_start` (or end-of-text).
3. If no marker exists at offset 0, prepend an `unknown` span covering `[0, first_marker)`.
4. Coalesce adjacent spans with the same label into one (rare but possible after footnote stripping).
5. Assign numeric suffixes for repeated canonical labels in document order: first occurrence keeps the base label; subsequent occurrences get `_2`, `_3`, …
6. Compute `pages` per span by intersecting `char_start`/`char_end` against `NormalizedText.page_offsets`.

**Key simplification:** we identify *boundaries*, not *extents*. There's no "where does Methods end?" question — Methods ends where the next labeled span begins. This eliminates a class of false-positive bugs that CitationGuard's `extractReferenceSection` end-pattern logic suffers from.

### 5.6 Confidence assignment

| Confidence | When |
|---|---|
| `high` | Heading text matched canonical taxonomy AND (layout is `strong` OR markup is structural) |
| `medium` | Heading text matched canonical taxonomy with `weak` layout, OR markup-only without text confirmation |
| `low` | Position-inferred, OR layout-strong but text-unknown (`unknown` span case) |

`unknown` spans always get `low`.

## 6. Footnote & header strip — `F0` step

Runs **after** S0–S5 standard steps and **before** A0–A7 academic steps. Only fires when `layout` is provided to `normalize_text`.

### 6.1 Algorithm

1. **Identify footnote zones per page** using `LayoutDoc`:
   - Find the lowest body-text y-coordinate cluster on each page (the line where main text ends).
   - Lines below that cluster matching any of: (a) font size < body × 0.92, (b) preceded by a horizontal rule, (c) starting with a digit/symbol marker matching a known body superscript, (d) starting with `^\d+\s+[A-Z]` and located in the bottom 25% of the page → mark as footnote.
   - Compute char-offset spans in the raw text.
2. **Identify running header/footer zones**:
   - Lines appearing at the *top* or *bottom* of ≥ 50% of pages with near-identical text → mark as running header/footer.
   - Standalone page numbers continue to be handled by the existing R2 step (this is the layout-aware complement, catching page-headers that R2 misses).
3. **Strip in order** (so removed offsets don't invalidate later spans):
   - Running headers → running footers → footnotes (preserving content for `footnotes` section) → standalone page-number residue.
4. **Store footnote spans** in `NormalizationReport.footnote_spans` (pre-strip char offsets, for provenance/debugging) and **append a footnotes appendix** to the returned normalized text.

### 6.2 Output composition

After F0, `normalize_text(text, layout=...)` returns text structured as:

```
<post-strip body text>
<single sentinel newline>
<footnotes appendix: per-page footnote zones in page order, joined by "\n\n">
```

The sectioner then partitions:
- The body region into the 18 canonical labels + `unknown`.
- The appendix region into a single `footnotes` Section whose `pages` tuple is the union of source pages.

This keeps the universal-coverage invariant `sum(len(s.text) for s in doc.sections) == len(doc.normalized_text)` (modulo the sentinel) true, and means the `footnotes` Section has well-defined `char_start`/`char_end` like every other section. `page_offsets` covers only the body region; the appendix has no page mapping beyond the section-level `pages` tuple.

When `layout` is not provided, F0 is a no-op, no appendix is added, and the `footnotes` section is absent (not present in `doc.sections`).

### 6.3 What this fixes

- Abstract on page 1 followed by footnote 1: footnote text was previously appended to `abstract`. Now it goes to `footnotes`.
- Methods on pages 5–6 with running header "FELDMAN ET AL." on page 6: previously stuck in the middle of methods text. Now stripped before sectioning sees it.
- Journal name + DOI footer on every page: previously polluted multiple section bodies. Now stripped once.

## 7. Public API

### 7.1 Python

```python
from docpluck import (
    extract_sections,
    SectionedDocument, Section, SectionLabel,
    Confidence, DetectedVia,
    SECTIONING_VERSION,
)

# Auto-detect format from bytes magic
doc: SectionedDocument = extract_sections(file_bytes)

# Or explicit format
doc = extract_sections(file_bytes, source_format="pdf")

# Or pre-extracted text (no layout context — sectioning still runs at lower confidence)
doc = extract_sections(text="...", source_format="pdf")

# Convenience accessors
doc.abstract.text                     # first abstract, or None
doc.references.pages                  # tuple of 1-indexed page numbers
doc.get("methods_2")                  # second methods (multi-study)
doc.all("methods")                    # all methods sections in document order
doc.text_for("abstract", "references")  # concatenated, document order
[s for s in doc.sections if s.confidence == Confidence.high]

# Versioning + provenance
doc.sectioning_version
doc.source_format
```

### 7.2 Filter sugar on existing extract calls

```python
text, method = extract_pdf(pdf_bytes, sections=["abstract", "references"])
text, method = extract_docx(docx_bytes, sections=["methods"])
text, method = extract_html(html_bytes, sections=["abstract"])
```

When `sections=None` (default), behavior is **byte-identical to today.** Layout extraction is opt-in.

### 7.3 CLI

```bash
docpluck extract paper.pdf --sections abstract,references
docpluck sections paper.pdf
docpluck sections paper.pdf --format json     # default
docpluck sections paper.pdf --format summary  # human-readable
docpluck sections paper.pdf --confidence-min high
```

JSON schema is stable and versioned by `SECTIONING_VERSION`.

## 8. Backwards compatibility commitments

1. `extract_pdf(pdf_bytes) -> tuple[str, str]` — output byte-identical to today.
2. `extract_docx(...)` and `extract_html(...)` — same.
3. `normalize_text(text)` and `normalize_text(text, level)` — output byte-identical to today.
4. `NormalizationReport` — gains `footnote_spans=()` and `page_offsets=()` fields with defaults; existing fields and tuple unpacking unchanged.

Anything that breaks these commitments is a bug, not a v2 migration.

## 9. Versioning

```python
# docpluck/sections/__init__.py
SECTIONING_VERSION = "1.0.0"
```

Bump policy:
- **Major** — change that produces different sections for the same input on a non-trivial set of papers.
- **Minor** — new canonical labels added, new heading variants matched.
- **Patch** — bug fixes that don't shift the dominant case.

Recorded on every `SectionedDocument`, mirroring `NORMALIZATION_VERSION` in `normalize.py:25`.

## 10. Testing

### 10.1 Test corpus (committed under `tests/fixtures/sections/`)

**Unit fixtures** — synthetic minimal PDFs/DOCX/HTML with controlled sections (one per canonical label). ~25 fixtures.

**Real-world corpus**:
- APA single-study (psych)
- APA multi-study (Study 1 / Study 2 / General Discussion)
- Vancouver / numbered-reference (medical, PMC manuscripts)
- IEEE / `[N]` references (engineering — kept for breadth)
- Nature / Science (front-matter heavy, end-matter heavy)
- Royal Society Open Science (RSOS — already addressed by W0 watermark step)
- Hebrew academic (one fixture, to surface non-English heading misses early)
- DOCX with real Heading styles
- DOCX with ad-hoc bold-as-heading
- HTML from a publisher landing page with `<section>` semantics
- HTML scraped from preprint server (poorer markup)
- ≥2 papers from the existing ESCIcheck 10-PDF set

Target: ~30 PDF + 6 DOCX + 4 HTML.

### 10.2 Test types

1. **Boundary coverage tests** — `sum(len(s.text) for s in doc.sections) == len(doc.normalized_text)` (modulo line-join whitespace); `s[i].char_start < s[i+1].char_start`.
2. **Label tests** — expected canonical labels present with confidence ≥ minimum.
3. **Page-range tests** — for known multi-page sections, assert page tuples.
4. **Regression tests** — golden JSON snapshots; CI fails if `SECTIONING_VERSION` is unchanged but output drifts.
5. **Footnote-strip tests** — fixtures with known footnote intrusions; assert footnotes are in the `footnotes` section and absent from body sections.
6. **Filter-sugar parity tests** — `extract_pdf(b, sections=["abstract"])` returns same text as `extract_sections(b).abstract.text`.
7. **Back-compat tests** — `extract_pdf(b)` is byte-identical to current output across the existing test corpus.

## 11. Performance budget

| Operation | Median target (20-page paper) |
|---|---|
| `extract_pdf()` (text-only, unchanged) | ≤ 0.3 s |
| `extract_pdf_layout()` (pdfplumber, internal) | ≤ 1.5 s |
| `normalize_text(layout=...)` | ≤ 0.5 s |
| `extract_sections()` end-to-end | ≤ 2.5 s |

Slower than current text-only path (layout extraction is ~5× slower than `pdftotext`), but acceptable: sectioning is opt-in, the SaaS pipeline already runs at multi-second per-paper budgets, and existing call sites get exactly today's performance.

If pdfplumber proves too slow on >50pp papers, fall back to text-only sectioning (skip layout-aware branch) — confidence degrades to `low`/`medium` but functionality remains.

## 12. Error handling

- **Garbled-text PDF** (existing detection in CitationGuard's `_check_text_quality`) → sectioning short-circuits, returns `SectionedDocument` with single `unknown` span and confidence `low`.
- **Empty document** → `SectionedDocument` with empty `sections` tuple.
- **pdfplumber import failure / unavailable** → falls back to text-only extraction; sectioning still runs without layout signals.
- **DOCX without mammoth installed** → existing `ImportError` propagates (no change).

No new exception classes. Failures degrade gracefully to lower-confidence output rather than raising.

## 13. Deferred items (TODO.md additions)

To be added to `TODO.md` when the design is committed:

1. Hierarchical / tree section output (Q2 option C from brainstorm).
2. Splitting `title_block` into `title` / `authors` / `affiliations` (affiliation parsing).
3. Custom heading-map / user-supplied taxonomy extension API (after we see real-world non-English/domain misses).
4. Validation of the conflict-resolution rule (text-pattern wins for canonical, layout wins for unknown — Q4.vi); requires MVP first.
5. Public `extract_pdf_layout()` API (once shape stabilizes through internal use).
6. Section-aware quality scoring in `quality.py` (e.g., flag low-confidence references that may need re-extraction).
7. Confidence calibration — current `high`/`medium`/`low` is heuristic; a real numeric calibration would need the test corpus + manual gold labels.

## 14. Implementation phases (rough estimate; full plan via writing-plans skill)

1. **Phase 1 — Data model + taxonomy.** `SectionLabel`, `Section`, `SectionedDocument`, taxonomy table, `SECTIONING_VERSION`. No detection yet. ~300 LOC.
2. **Phase 2 — Text annotator + core canonicalizer.** Pure text-based sectioning end-to-end. Works on any input string. Lowest-confidence path. ~400 LOC.
3. **Phase 3 — DOCX + HTML annotators.** Markup-aware paths. Both formats now ship at higher confidence. ~250 LOC.
4. **Phase 4 — `extract_pdf_layout()` + PDF annotator.** pdfplumber integration; layout-aware heading detection. ~400 LOC.
5. **Phase 5 — `F0` footnote/header strip.** Layout-aware normalize step. ~250 LOC.
6. **Phase 6 — Filter sugar + CLI.** `extract_pdf(sections=...)` + `docpluck sections` command. ~150 LOC.
7. **Phase 7 — Test corpus + regression snapshots.** Build fixtures, golden snapshots, CI integration. Ongoing.

Each phase is independently committable and testable. Phases 1–2 alone deliver a functional (low-confidence) sectioner; later phases are additive precision improvements.
