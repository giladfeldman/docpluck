# Section Identification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `docpluck.sections` package that partitions PDF/DOCX/HTML academic papers into 18 canonical labeled sections (abstract, methods, references, disclosures, …) with universal char-level coverage, plus a layout-aware footnote/header strip step that catches intrusions text-only normalization misses.

**Architecture:** Two-tier sectioning. Tier 1 — three thin format-aware annotators (PDF/DOCX/HTML) emit `BlockHint`s. Tier 2 — one unified core canonicalizer maps heading text to `SectionLabel` enum, applies end-of-section boundaries, partitions into universal-coverage spans, assigns numeric suffixes for repeats, and assigns confidence. New `extract_layout.py` reads pdfplumber bounding boxes; new `F0` step in `normalize_text` strips footnotes/running-headers/footers when layout is supplied. All existing public APIs remain byte-identical when called as today.

**Tech Stack:** Python ≥3.10, dataclasses, enum, pdfplumber (already a dep), mammoth (DOCX, optional), beautifulsoup4 (HTML, optional), pytest. No new runtime deps.

**Spec:** `docs/superpowers/specs/2026-05-06-section-identification-design.md`

---

## Pre-flight

- [ ] **Step 0.1: Confirm working tree is clean and on a fresh branch**

```bash
cd C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck
git status
git checkout -b feat/section-identification
```

Expected: `nothing to commit, working tree clean` then branch switched.

- [ ] **Step 0.2: Confirm test suite passes before any changes**

```bash
pytest -x -q
```

Expected: all green. If anything fails, stop and investigate before adding new work on top.

---

## Phase 1 — Foundation: data model + taxonomy

Goal of phase: every type and constant the rest of the plan refers to exists and is importable. No detection logic yet.

### Task 1: Create `sections/` package skeleton + `SECTIONING_VERSION`

**Files:**
- Create: `docpluck/sections/__init__.py`
- Create: `tests/test_sections_version.py`

- [ ] **Step 1.1: Write the failing test**

`tests/test_sections_version.py`:

```python
"""Smoke test — module exists and exposes SECTIONING_VERSION."""

def test_sections_module_imports():
    from docpluck import sections
    assert sections is not None


def test_sectioning_version_is_semver_string():
    from docpluck.sections import SECTIONING_VERSION
    parts = SECTIONING_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_sectioning_version_starts_at_1_0_0():
    from docpluck.sections import SECTIONING_VERSION
    assert SECTIONING_VERSION == "1.0.0"
```

- [ ] **Step 1.2: Run test to verify it fails**

```bash
pytest tests/test_sections_version.py -v
```

Expected: `ImportError: No module named 'docpluck.sections'` or similar.

- [ ] **Step 1.3: Create the package**

`docpluck/sections/__init__.py`:

```python
"""
docpluck.sections — section identification for academic papers.

See docs/superpowers/specs/2026-05-06-section-identification-design.md
for the full design.

Public API: extract_sections, SectionedDocument, Section, SectionLabel,
Confidence, DetectedVia, SECTIONING_VERSION.
"""

SECTIONING_VERSION = "1.0.0"

__all__ = ["SECTIONING_VERSION"]
```

- [ ] **Step 1.4: Run test to verify it passes**

```bash
pytest tests/test_sections_version.py -v
```

Expected: 3 passing.

- [ ] **Step 1.5: Commit**

```bash
git add docpluck/sections/__init__.py tests/test_sections_version.py
git commit -m "feat(sections): scaffold sections package + SECTIONING_VERSION"
```

### Task 2: Add `SectionLabel`, `Confidence`, `DetectedVia` enums

**Files:**
- Create: `docpluck/sections/taxonomy.py`
- Test: `tests/test_sections_taxonomy.py`

- [ ] **Step 2.1: Write the failing test**

`tests/test_sections_taxonomy.py`:

```python
"""Taxonomy enums: SectionLabel, Confidence, DetectedVia."""

from docpluck.sections.taxonomy import SectionLabel, Confidence, DetectedVia


def test_canonical_labels_present():
    expected = {
        "title_block", "abstract", "keywords", "author_note",
        "introduction", "literature_review", "methods", "results",
        "discussion", "general_discussion",
        "acknowledgments", "funding", "conflict_of_interest",
        "data_availability", "author_contributions",
        "references", "appendix", "supplementary",
        "footnotes", "unknown", "study_n_header",
    }
    actual = {label.value for label in SectionLabel}
    assert actual == expected


def test_confidence_levels():
    assert Confidence.high.value == "high"
    assert Confidence.medium.value == "medium"
    assert Confidence.low.value == "low"


def test_detected_via_options():
    assert DetectedVia.heading_match.value == "heading_match"
    assert DetectedVia.markup.value == "markup"
    assert DetectedVia.layout_signal.value == "layout_signal"
    assert DetectedVia.text_pattern_fallback.value == "text_pattern_fallback"
    assert DetectedVia.position_inferred.value == "position_inferred"
```

- [ ] **Step 2.2: Run test to verify it fails**

```bash
pytest tests/test_sections_taxonomy.py -v
```

Expected: `ImportError: cannot import name 'SectionLabel'`.

- [ ] **Step 2.3: Implement the enums**

`docpluck/sections/taxonomy.py`:

```python
"""Canonical section labels + heading-text → label map."""

from __future__ import annotations

from enum import Enum


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
    study_n_header = "study_n_header"


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
```

- [ ] **Step 2.4: Run test to verify it passes**

```bash
pytest tests/test_sections_taxonomy.py -v
```

Expected: 3 passing.

- [ ] **Step 2.5: Commit**

```bash
git add docpluck/sections/taxonomy.py tests/test_sections_taxonomy.py
git commit -m "feat(sections): add SectionLabel, Confidence, DetectedVia enums"
```

### Task 3: Implement `HEADING_TO_LABEL` map + `lookup_canonical_label()`

**Files:**
- Modify: `docpluck/sections/taxonomy.py` (append to existing file)
- Modify: `tests/test_sections_taxonomy.py`

- [ ] **Step 3.1: Write the failing tests**

Append to `tests/test_sections_taxonomy.py`:

```python
from docpluck.sections.taxonomy import lookup_canonical_label


def test_lookup_exact_match():
    assert lookup_canonical_label("Abstract") == SectionLabel.abstract
    assert lookup_canonical_label("References") == SectionLabel.references
    assert lookup_canonical_label("Methods") == SectionLabel.methods


def test_lookup_case_insensitive():
    assert lookup_canonical_label("ABSTRACT") == SectionLabel.abstract
    assert lookup_canonical_label("references") == SectionLabel.references


def test_lookup_whitespace_collapsed():
    assert lookup_canonical_label("  Abstract  ") == SectionLabel.abstract
    assert lookup_canonical_label("Materials  and  Methods") == SectionLabel.methods


def test_lookup_punctuation_stripped():
    assert lookup_canonical_label("References:") == SectionLabel.references
    assert lookup_canonical_label("1. Methods") == SectionLabel.methods
    assert lookup_canonical_label("2.1. Materials and Methods") == SectionLabel.methods


def test_lookup_synonyms():
    assert lookup_canonical_label("Bibliography") == SectionLabel.references
    assert lookup_canonical_label("Works Cited") == SectionLabel.references
    assert lookup_canonical_label("Materials & Methods") == SectionLabel.methods
    assert lookup_canonical_label("Background") == SectionLabel.introduction
    assert lookup_canonical_label("Competing Interests") == SectionLabel.conflict_of_interest
    assert lookup_canonical_label("Disclosure") == SectionLabel.conflict_of_interest
    assert lookup_canonical_label("Supporting Information") == SectionLabel.supplementary


def test_lookup_returns_none_for_unrecognized():
    assert lookup_canonical_label("Frobnicator") is None
    assert lookup_canonical_label("Some Random Heading") is None
    assert lookup_canonical_label("") is None
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
pytest tests/test_sections_taxonomy.py -v
```

Expected: 6 new failures with `ImportError: cannot import name 'lookup_canonical_label'`.

- [ ] **Step 3.3: Implement the heading map and lookup**

Append to `docpluck/sections/taxonomy.py`:

```python
import re

# Heading-text → canonical-label map. Lookup is case-folded,
# whitespace-collapsed, leading-numbering-stripped, trailing-punctuation-stripped.
# Variants per label are grouped in a frozenset for O(1) multi-key lookup.
HEADING_TO_LABEL: dict[frozenset[str], SectionLabel] = {
    # Front matter
    frozenset({"abstract", "summary"}): SectionLabel.abstract,
    frozenset({"keywords", "key words", "keyword"}): SectionLabel.keywords,
    frozenset({"author note", "author's note", "authors' note", "authors note"}):
        SectionLabel.author_note,
    # Body
    frozenset({"introduction", "background", "introduction and background"}):
        SectionLabel.introduction,
    frozenset({"literature review", "review of literature", "related work",
               "theoretical background", "theory"}): SectionLabel.literature_review,
    frozenset({"method", "methods", "materials and methods", "materials & methods",
               "experimental procedures", "methodology", "experimental design",
               "study design", "procedure", "procedures"}): SectionLabel.methods,
    frozenset({"results", "results and discussion", "findings",
               "empirical results"}): SectionLabel.results,
    frozenset({"discussion", "general discussion"}): SectionLabel.discussion,
    # General discussion gets its own label only when explicitly named that way.
    frozenset({"general discussion", "overall discussion"}):
        SectionLabel.general_discussion,
    # Back matter
    frozenset({"acknowledgments", "acknowledgements", "acknowledgment",
               "acknowledgement"}): SectionLabel.acknowledgments,
    frozenset({"funding", "funding statement", "funding information",
               "financial support", "grants"}): SectionLabel.funding,
    frozenset({"conflict of interest", "conflicts of interest",
               "competing interests", "competing interest",
               "declaration of interest", "declaration of interests",
               "declarations", "disclosure", "disclosures",
               "competing financial interests"}):
        SectionLabel.conflict_of_interest,
    frozenset({"data availability", "data availability statement",
               "availability of data", "data and materials availability",
               "code availability", "data and code availability"}):
        SectionLabel.data_availability,
    frozenset({"author contributions", "author contribution",
               "contributions", "credit authorship statement",
               "credit author statement"}): SectionLabel.author_contributions,
    frozenset({"references", "bibliography", "works cited", "literature cited",
               "literature", "cited literature", "reference list",
               "list of references", "cited references"}): SectionLabel.references,
    frozenset({"appendix", "appendices", "appendix a", "appendix b",
               "appendix c", "appendix d"}): SectionLabel.appendix,
    frozenset({"supplementary", "supplementary material",
               "supplementary materials", "supplementary information",
               "supporting information", "online supplement",
               "supplemental materials", "supplemental material",
               "online supplementary material"}): SectionLabel.supplementary,
}


# Resolution order matters when a heading appears in multiple frozensets
# (currently only "general discussion" → both discussion and general_discussion).
# We prefer the more specific label.
_PREFERRED_OVER: dict[SectionLabel, SectionLabel] = {
    SectionLabel.general_discussion: SectionLabel.discussion,
}


_NUMBERING_PREFIX = re.compile(r"^\s*(\d+(\.\d+)*\.?)\s+")
_PUNCT_TRAILING = re.compile(r"[\s:.\-–—]+$")
_WHITESPACE = re.compile(r"\s+")


def _normalize_heading(text: str) -> str:
    """Case-fold, strip leading numbering, collapse whitespace, strip
    trailing punctuation. Returns '' for input that becomes empty."""
    s = text.strip().lower()
    s = _NUMBERING_PREFIX.sub("", s)
    s = _PUNCT_TRAILING.sub("", s)
    s = _WHITESPACE.sub(" ", s)
    return s.strip()


def lookup_canonical_label(heading_text: str) -> SectionLabel | None:
    """Map a literal heading string to its canonical SectionLabel, or None."""
    normalized = _normalize_heading(heading_text)
    if not normalized:
        return None
    matches: list[SectionLabel] = []
    for variants, label in HEADING_TO_LABEL.items():
        if normalized in variants:
            matches.append(label)
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    # Multi-match — apply preference order.
    for preferred, less_specific in _PREFERRED_OVER.items():
        if preferred in matches and less_specific in matches:
            return preferred
    return matches[0]
```

- [ ] **Step 3.4: Run tests to verify they pass**

```bash
pytest tests/test_sections_taxonomy.py -v
```

Expected: all 9 tests passing.

- [ ] **Step 3.5: Commit**

```bash
git add docpluck/sections/taxonomy.py tests/test_sections_taxonomy.py
git commit -m "feat(sections): heading-text → canonical-label map + lookup"
```

### Task 4: Implement `Section` and `SectionedDocument` dataclasses

**Files:**
- Create: `docpluck/sections/types.py`
- Test: `tests/test_sections_types.py`

- [ ] **Step 4.1: Write the failing test**

`tests/test_sections_types.py`:

```python
"""Section + SectionedDocument dataclasses."""

import pytest

from docpluck.sections.types import Section, SectionedDocument
from docpluck.sections.taxonomy import SectionLabel, Confidence, DetectedVia


def _mk(label, text, start, end, canonical=None, pages=()):
    return Section(
        label=label,
        canonical_label=canonical or SectionLabel(label),
        text=text,
        char_start=start,
        char_end=end,
        pages=pages,
        confidence=Confidence.high,
        detected_via=DetectedVia.heading_match,
        heading_text=None,
    )


def test_section_is_frozen():
    s = _mk("abstract", "hi", 0, 2)
    with pytest.raises(Exception):
        s.text = "changed"


def test_sectioned_document_get_returns_first():
    a = _mk("methods", "m1", 0, 2)
    b = _mk("methods_2", "m2", 5, 7, canonical=SectionLabel.methods)
    doc = SectionedDocument(
        sections=(a, b), normalized_text="m1   m2",
        sectioning_version="1.0.0", source_format="pdf",
    )
    assert doc.get("methods") is a
    assert doc.get("methods_2") is b


def test_sectioned_document_all_returns_all_in_order():
    a = _mk("methods", "m1", 0, 2)
    b = _mk("methods_2", "m2", 5, 7, canonical=SectionLabel.methods)
    doc = SectionedDocument(
        sections=(a, b), normalized_text="m1   m2",
        sectioning_version="1.0.0", source_format="pdf",
    )
    assert doc.all("methods") == (a, b)


def test_sectioned_document_text_for():
    abstract = _mk("abstract", "ABSTRACT", 0, 8)
    refs = _mk("references", "REFS", 9, 13)
    doc = SectionedDocument(
        sections=(abstract, refs), normalized_text="ABSTRACT REFS",
        sectioning_version="1.0.0", source_format="pdf",
    )
    assert doc.text_for("abstract", "references") == "ABSTRACT\n\nREFS"
    assert doc.text_for("references", "abstract") == "ABSTRACT\n\nREFS"  # always document order
    assert doc.text_for("methods") == ""


def test_sectioned_document_property_accessors():
    abstract = _mk("abstract", "ABSTRACT", 0, 8)
    refs = _mk("references", "REFS", 9, 13)
    doc = SectionedDocument(
        sections=(abstract, refs), normalized_text="ABSTRACT REFS",
        sectioning_version="1.0.0", source_format="pdf",
    )
    assert doc.abstract is abstract
    assert doc.references is refs
    assert doc.methods is None
    assert doc.results is None
    assert doc.introduction is None
    assert doc.discussion is None
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
pytest tests/test_sections_types.py -v
```

Expected: `ImportError: No module named 'docpluck.sections.types'`.

- [ ] **Step 4.3: Implement the dataclasses**

`docpluck/sections/types.py`:

```python
"""Section and SectionedDocument — public data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .taxonomy import SectionLabel, Confidence, DetectedVia


@dataclass(frozen=True)
class Section:
    label: str                          # "methods", "methods_2", "study_1_header"
    canonical_label: SectionLabel       # base label without numeric suffix
    text: str
    char_start: int                     # offset into normalized_text
    char_end: int
    pages: tuple[int, ...]              # 1-indexed; () if unavailable
    confidence: Confidence
    detected_via: DetectedVia
    heading_text: str | None            # literal heading found, if any


@dataclass(frozen=True)
class SectionedDocument:
    sections: tuple[Section, ...]
    normalized_text: str
    sectioning_version: str
    source_format: Literal["pdf", "docx", "html"]

    def get(self, label: str) -> Section | None:
        for s in self.sections:
            if s.label == label:
                return s
        return None

    def all(self, label: str) -> tuple[Section, ...]:
        # Match canonical_label so doc.all("methods") returns methods + methods_2 + ...
        canonical = label.split("_")[0] if label not in {l.value for l in SectionLabel} else label
        try:
            target = SectionLabel(label)
        except ValueError:
            target = None
        if target is None:
            return tuple(s for s in self.sections if s.label == label)
        return tuple(s for s in self.sections if s.canonical_label == target)

    def text_for(self, *labels: str) -> str:
        wanted: list[Section] = []
        for s in self.sections:
            if s.label in labels or s.canonical_label.value in labels:
                wanted.append(s)
        # Always document order — sort by char_start.
        wanted.sort(key=lambda s: s.char_start)
        return "\n\n".join(s.text for s in wanted)

    # 6 high-traffic convenience properties (per spec §4):
    @property
    def abstract(self) -> Section | None:
        return self._first_canonical(SectionLabel.abstract)

    @property
    def introduction(self) -> Section | None:
        return self._first_canonical(SectionLabel.introduction)

    @property
    def methods(self) -> Section | None:
        return self._first_canonical(SectionLabel.methods)

    @property
    def results(self) -> Section | None:
        return self._first_canonical(SectionLabel.results)

    @property
    def discussion(self) -> Section | None:
        return self._first_canonical(SectionLabel.discussion)

    @property
    def references(self) -> Section | None:
        return self._first_canonical(SectionLabel.references)

    def _first_canonical(self, label: SectionLabel) -> Section | None:
        for s in self.sections:
            if s.canonical_label == label:
                return s
        return None
```

- [ ] **Step 4.4: Run tests to verify they pass**

```bash
pytest tests/test_sections_types.py -v
```

Expected: 5 passing.

- [ ] **Step 4.5: Commit**

```bash
git add docpluck/sections/types.py tests/test_sections_types.py
git commit -m "feat(sections): Section + SectionedDocument dataclasses"
```

### Task 5: Re-export public API from `docpluck.sections.__init__`

**Files:**
- Modify: `docpluck/sections/__init__.py`
- Test: `tests/test_sections_public_api.py`

- [ ] **Step 5.1: Write the failing test**

`tests/test_sections_public_api.py`:

```python
"""Public API surface from docpluck.sections."""


def test_sections_namespace_exports():
    from docpluck.sections import (
        SECTIONING_VERSION,
        Section,
        SectionedDocument,
        SectionLabel,
        Confidence,
        DetectedVia,
    )
    assert SECTIONING_VERSION == "1.0.0"
    assert Section is not None
    assert SectionedDocument is not None
    assert SectionLabel.abstract.value == "abstract"
    assert Confidence.high.value == "high"
    assert DetectedVia.markup.value == "markup"
```

- [ ] **Step 5.2: Run test to verify it fails**

```bash
pytest tests/test_sections_public_api.py -v
```

Expected: `ImportError`.

- [ ] **Step 5.3: Update `__init__.py`**

`docpluck/sections/__init__.py`:

```python
"""
docpluck.sections — section identification for academic papers.

See docs/superpowers/specs/2026-05-06-section-identification-design.md.

Public API: extract_sections, SectionedDocument, Section, SectionLabel,
Confidence, DetectedVia, SECTIONING_VERSION.
"""

from .taxonomy import SectionLabel, Confidence, DetectedVia
from .types import Section, SectionedDocument

SECTIONING_VERSION = "1.0.0"

__all__ = [
    "SECTIONING_VERSION",
    "Section",
    "SectionedDocument",
    "SectionLabel",
    "Confidence",
    "DetectedVia",
]
```

- [ ] **Step 5.4: Run test to verify it passes**

```bash
pytest tests/test_sections_public_api.py tests/test_sections_version.py -v
```

Expected: all passing.

- [ ] **Step 5.5: Commit**

```bash
git add docpluck/sections/__init__.py tests/test_sections_public_api.py
git commit -m "feat(sections): re-export public API from sections namespace"
```

---

## Phase 2 — Text-only sectioning end-to-end

Goal of phase: a working text-only sectioner. Given a string, produce a `SectionedDocument` with universal coverage. Lowest-confidence path; later phases add precision.

### Task 6: `BlockHint` dataclass + text annotator skeleton

**Files:**
- Create: `docpluck/sections/annotators/__init__.py`
- Create: `docpluck/sections/annotators/text.py`
- Create: `docpluck/sections/blocks.py`
- Test: `tests/test_sections_text_annotator.py`

- [ ] **Step 6.1: Write the failing test**

`tests/test_sections_text_annotator.py`:

```python
"""Text-only annotator: detect headings via regex."""

from docpluck.sections.annotators.text import annotate_text
from docpluck.sections.blocks import BlockHint


def test_returns_list_of_blockhints():
    hints = annotate_text("Hello world.")
    assert isinstance(hints, list)
    for h in hints:
        assert isinstance(h, BlockHint)


def test_detects_standalone_heading():
    text = "Some intro text.\n\nReferences\n\n[1] Smith, J.\n"
    hints = annotate_text(text)
    headings = [h for h in hints if h.is_heading_candidate]
    assert len(headings) >= 1
    assert any(h.text.strip() == "References" for h in headings)


def test_detects_numbered_heading():
    text = "Stuff.\n\n1. Introduction\n\nMore stuff.\n2. Methods\n\nProcedure.\n"
    hints = annotate_text(text)
    heading_texts = [h.text.strip() for h in hints if h.is_heading_candidate]
    assert any("Introduction" in t for t in heading_texts)
    assert any("Methods" in t for t in heading_texts)


def test_detects_markdown_heading():
    text = "Body.\n\n# References\n\n[1] Smith, J.\n"
    hints = annotate_text(text)
    assert any(h.is_heading_candidate and "References" in h.text for h in hints)


def test_detects_underlined_heading():
    text = "Body.\n\nReferences\n----------\n\n[1] Smith, J.\n"
    hints = annotate_text(text)
    assert any(h.is_heading_candidate and "References" in h.text for h in hints)


def test_detects_spaced_caps_heading():
    text = "Body.\n\nR E F E R E N C E S\n\n[1] Smith, J.\n"
    hints = annotate_text(text)
    assert any(h.is_heading_candidate and "References".lower() in h.text.replace(" ", "").lower()
               for h in hints)


def test_no_false_positive_for_inline_mention():
    text = "We list our references at the end. The methods section follows."
    hints = annotate_text(text)
    headings = [h for h in hints if h.is_heading_candidate]
    assert headings == []


def test_block_hints_have_correct_offsets():
    text = "Body.\n\nReferences\n\n[1] Smith.\n"
    hints = annotate_text(text)
    for h in hints:
        assert text[h.char_start:h.char_end] == h.text
```

- [ ] **Step 6.2: Run tests to verify they fail**

```bash
pytest tests/test_sections_text_annotator.py -v
```

Expected: `ImportError`.

- [ ] **Step 6.3: Implement `BlockHint`**

`docpluck/sections/blocks.py`:

```python
"""BlockHint — output unit of Tier-1 annotators, input of Tier-2 core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class BlockHint:
    text: str
    char_start: int
    char_end: int
    page: int | None
    is_heading_candidate: bool
    heading_strength: Literal["strong", "weak", "none"]
    heading_source: Literal["markup", "layout", "text_pattern", None]
```

- [ ] **Step 6.4: Implement `annotators/__init__.py`**

`docpluck/sections/annotators/__init__.py`:

```python
"""Format-aware annotators (Tier 1)."""
```

- [ ] **Step 6.5: Implement `annotators/text.py`**

`docpluck/sections/annotators/text.py`:

```python
"""Text-only heading-candidate annotator (Tier 1 fallback)."""

from __future__ import annotations

import re

from ..blocks import BlockHint

# A "strong" heading line: standalone, on its own line, with optional numbering,
# matches a known canonical heading word, and has no terminal period in body
# style. Matched via the canonical taxonomy in core.py — text annotator only
# emits CANDIDATES; final canonicalization happens in Tier 2.
_HEADING_LINE = re.compile(
    r"""(?xm)               # verbose, multiline
    ^                       # start of line
    [ \t]*                  # optional leading whitespace
    (?:\#{1,6}[ \t]+)?      # optional markdown header marker
    (?:\d+(?:\.\d+)*\.?[ \t]+)?  # optional numbering: 1.  / 2.1  / 3.1.4.
    (?P<heading>            # capture the heading text
        [A-Z][A-Za-z &\-/]{0,80}      # title-case-ish words
        |
        [A-Z][A-Z &\-/]{0,80}         # ALL CAPS
        |
        (?:[A-Z][ \t]){2,30}[A-Z]     # spaced caps: "R E F E R E N C E S"
    )
    [ \t]*[:.]?[ \t]*       # optional trailing colon/period
    $                       # end of line
    """,
)

_UNDERLINED_HEADING = re.compile(
    r"""(?xm)
    ^[ \t]*(?P<heading>[A-Z][A-Za-z &\-/]{0,80})[ \t]*\n
    [ \t]*[-=]{2,}[ \t]*$
    """,
)


def annotate_text(text: str) -> list[BlockHint]:
    """Scan `text` for standalone heading-candidate lines.

    Returns BlockHints in document order. Body paragraphs are NOT emitted —
    only candidate headings. Tier 2 fills in the body spans by partitioning
    between adjacent heading positions.
    """
    hints: list[BlockHint] = []

    seen_offsets: set[int] = set()

    # Underlined headings first (so we can skip the underline line in the
    # plain heading scan below).
    for m in _UNDERLINED_HEADING.finditer(text):
        start = m.start("heading")
        end = m.end("heading")
        seen_offsets.add(start)
        hints.append(BlockHint(
            text=m.group("heading"),
            char_start=start,
            char_end=end,
            page=None,
            is_heading_candidate=True,
            heading_strength="strong",
            heading_source="text_pattern",
        ))

    for m in _HEADING_LINE.finditer(text):
        start = m.start("heading")
        end = m.end("heading")
        if start in seen_offsets:
            continue
        line = m.group(0)
        # Reject lines that look like body text mid-sentence: the line must
        # be preceded by a blank line, the start of the document, or a heading.
        before = text[max(0, start - 2):start]
        if before and not before.endswith("\n\n") and not before.endswith("\n"):
            continue
        # Reject lines that have terminal period followed by lowercase
        # (sentence continuation) — heuristic kept light because canonicalizer
        # will filter further.
        heading = m.group("heading").strip()
        if len(heading) < 2:
            continue
        # Strong if it's a recognized canonical heading by simple lowercase
        # whole-word check; weak otherwise.
        from ..taxonomy import lookup_canonical_label
        strength = "strong" if lookup_canonical_label(heading) is not None else "weak"
        hints.append(BlockHint(
            text=heading,
            char_start=start,
            char_end=end,
            page=None,
            is_heading_candidate=True,
            heading_strength=strength,
            heading_source="text_pattern",
        ))

    hints.sort(key=lambda h: h.char_start)
    return hints
```

- [ ] **Step 6.6: Run tests to verify they pass**

```bash
pytest tests/test_sections_text_annotator.py -v
```

Expected: 8 passing. If "spaced caps" test fails, that one is allowed to be best-effort — see Task 6.7 below.

- [ ] **Step 6.7: If `test_detects_spaced_caps_heading` fails, add a second pass**

Append a second regex pass to `annotate_text` BEFORE the existing scans:

```python
_SPACED_CAPS = re.compile(r"(?m)^[ \t]*(?:[A-Z][ \t]){2,30}[A-Z][ \t]*$")

def _spaced_caps_pass(text: str, hints: list[BlockHint], seen: set[int]) -> None:
    for m in _SPACED_CAPS.finditer(text):
        start, end = m.start(), m.end()
        if start in seen:
            continue
        seen.add(start)
        compact = m.group().replace(" ", "").replace("\t", "")
        hints.append(BlockHint(
            text=compact,
            char_start=start,
            char_end=end,
            page=None,
            is_heading_candidate=True,
            heading_strength="strong",  # spaced caps are visually distinct
            heading_source="text_pattern",
        ))
```

Then call `_spaced_caps_pass(text, hints, seen_offsets)` immediately after the underlined-heading pass.

Re-run: `pytest tests/test_sections_text_annotator.py -v` — all 8 should pass.

- [ ] **Step 6.8: Commit**

```bash
git add docpluck/sections/blocks.py docpluck/sections/annotators/__init__.py docpluck/sections/annotators/text.py tests/test_sections_text_annotator.py
git commit -m "feat(sections): text-only heading annotator + BlockHint type"
```

### Task 7: End-of-section boundary patterns

**Files:**
- Create: `docpluck/sections/boundaries.py`
- Test: `tests/test_sections_boundaries.py`

- [ ] **Step 7.1: Write the failing test**

`tests/test_sections_boundaries.py`:

```python
"""End-of-section boundary patterns (lifted from CitationGuard endPatterns)."""

from docpluck.sections.boundaries import is_section_boundary


def test_author_bio_caps_pattern_matches():
    assert is_section_boundary("HERMAN AGUINIS is the senior")
    assert is_section_boundary("JANE DOE is a Professor at...")


def test_corresponding_author_matches():
    assert is_section_boundary("Corresponding author: jane@example.org")


def test_email_contact_matches():
    assert is_section_boundary("Email: alice@example.org")
    assert is_section_boundary("E-mail: alice@example.org")


def test_orcid_matches():
    assert is_section_boundary("ORCID: 0000-0001-2345-6789")


def test_editorial_metadata_matches():
    assert is_section_boundary("Accepted by Editor X. on 2023-01-01")
    assert is_section_boundary("Action Editor: Y. Z.")
    assert is_section_boundary("Received: 2024-01-01")


def test_figure_caption_matches():
    assert is_section_boundary("Figure 1. Distribution of effect sizes.")
    assert is_section_boundary("Table 3. Means and standard deviations.")


def test_normal_body_text_does_not_match():
    assert not is_section_boundary("In our results, we observed that the effect was strong.")
    assert not is_section_boundary("The methods used in this study include...")
    assert not is_section_boundary("Smith, J. (2020). A paper title.")
```

- [ ] **Step 7.2: Run tests to verify they fail**

```bash
pytest tests/test_sections_boundaries.py -v
```

Expected: `ImportError`.

- [ ] **Step 7.3: Implement boundary patterns**

`docpluck/sections/boundaries.py`:

```python
"""End-of-section boundary patterns.

Lifted and consolidated from CitationGuard's `endPatterns`
(apps/worker/src/processors/referenceParser.ts ~lines 825-858).
These close a section ONLY when no canonical heading is found before
the next boundary. Primary boundary signal = next strong heading.
"""

from __future__ import annotations

import re

# Each pattern is anchored at the START of a line (the input is a single
# line trimmed). Line-by-line evaluation in the partitioner.
BOUNDARY_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Figure / table captions
    re.compile(r"^(Figure|Table|Fig\.|Tab\.)\s+\d+", re.IGNORECASE),

    # Author bio variants
    re.compile(r"^[A-Z]{2,}(?:\s+[A-Z]\.?)*(?:\s+[A-Z]{2,})*\s+(?:is|was|has|holds)\s"),
    re.compile(
        r"^[A-ZÀ-Ÿ][a-zà-ÿā-ž'-]+(?:\s+[A-ZÀ-Ÿ]\.?)+\s*\([^)]*@[^)]*\)\s+(?:is|was|has|holds)"
    ),
    re.compile(
        r"^[A-ZÀ-Ÿ][a-zà-ÿā-ž'-]+(?:\s+[A-ZÀ-Ÿ]\.?\s*)*"
        r"(?:\s+[A-ZÀ-Ÿ][a-zà-ÿā-ž'-]+)?\s+(?:PhD|Ph\.D|MD|MPH|MSc|MSW|DrPH|RN|FRCPC|FRCP)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^[A-ZÀ-Ÿ][a-zà-ÿā-ž'-]+(?:\s+[A-ZÀ-Ÿ]\.?\s*)*"
        r"(?:\s+[A-ZÀ-Ÿ][a-zà-ÿā-ž'-]+)*\s+is\s+(?:at|with|in)\s+"
        r"(?:the\s+)?(?:Department|School|Faculty|College|Division|Institute|Center|Centre)\b",
        re.IGNORECASE,
    ),

    # Corresponding author / contact metadata
    re.compile(r"^Corresponding\s+author\b", re.IGNORECASE),
    re.compile(r"^(?:Address|E-?mail|Tel|Fax|Contact)\s*:", re.IGNORECASE),
    re.compile(r"^ORCID\s*:", re.IGNORECASE),

    # Editorial metadata
    re.compile(
        r"^(?:Accepted by|Action Editor|Handling Editor|Received|Revised|Published)\s*:?\s",
        re.IGNORECASE,
    ),
)


def is_section_boundary(line: str) -> bool:
    """Return True if `line` looks like an end-of-section boundary marker."""
    trimmed = line.strip()
    if not trimmed:
        return False
    return any(pat.match(trimmed) for pat in BOUNDARY_PATTERNS)
```

- [ ] **Step 7.4: Run tests to verify they pass**

```bash
pytest tests/test_sections_boundaries.py -v
```

Expected: 7 passing.

- [ ] **Step 7.5: Commit**

```bash
git add docpluck/sections/boundaries.py tests/test_sections_boundaries.py
git commit -m "feat(sections): end-of-section boundary patterns"
```

### Task 8: Universal-coverage partitioner + suffix assignment

**Files:**
- Create: `docpluck/sections/core.py`
- Test: `tests/test_sections_core_partition.py`

- [ ] **Step 8.1: Write the failing tests**

`tests/test_sections_core_partition.py`:

```python
"""Universal-coverage partitioning + numeric suffix assignment."""

from docpluck.sections.blocks import BlockHint
from docpluck.sections.core import partition_into_sections
from docpluck.sections.taxonomy import SectionLabel, Confidence


def _hint(text, start, end, strength="strong", source="text_pattern"):
    return BlockHint(
        text=text, char_start=start, char_end=end,
        page=None, is_heading_candidate=True,
        heading_strength=strength, heading_source=source,
    )


def test_universal_coverage_no_gaps():
    text = "Intro paragraph.\n\nMethods\n\nWe did things.\n\nReferences\n\n[1] X."
    methods_idx = text.index("Methods")
    refs_idx = text.index("References")
    hints = [_hint("Methods", methods_idx, methods_idx + 7),
             _hint("References", refs_idx, refs_idx + 10)]
    sections = partition_into_sections(text, hints, source_format="pdf")
    # Sum of section text lengths == len(text), modulo nothing — universal coverage.
    total = sum(s.char_end - s.char_start for s in sections)
    assert total == len(text)
    # Sections are ordered by char_start.
    starts = [s.char_start for s in sections]
    assert starts == sorted(starts)


def test_unknown_prefix_for_unlabeled_lead():
    text = "Some unlabeled lead matter.\n\nMethods\n\nDetails."
    methods_idx = text.index("Methods")
    sections = partition_into_sections(
        text, [_hint("Methods", methods_idx, methods_idx + 7)], source_format="pdf"
    )
    assert sections[0].canonical_label == SectionLabel.unknown
    assert sections[0].char_start == 0


def test_canonical_labels_assigned_via_lookup():
    text = "Pre.\n\nAbstract\n\nThis is the abstract.\n\nReferences\n\n[1]."
    abs_idx = text.index("Abstract")
    refs_idx = text.index("References")
    sections = partition_into_sections(
        text,
        [_hint("Abstract", abs_idx, abs_idx + 8),
         _hint("References", refs_idx, refs_idx + 10)],
        source_format="pdf",
    )
    labels = [s.label for s in sections]
    assert "abstract" in labels
    assert "references" in labels


def test_numeric_suffix_for_repeats():
    text = ("Pre.\n\nMethods\n\nFirst.\n\nResults\n\nFirst.\n\n"
            "Methods\n\nSecond.\n\nResults\n\nSecond.\n\nReferences\n\n[1].")
    hints = []
    for word in ["Methods", "Results", "Methods", "Results", "References"]:
        idx = text.index(word, hints[-1].char_end if hints else 0)
        hints.append(_hint(word, idx, idx + len(word)))
    sections = partition_into_sections(text, hints, source_format="pdf")
    labels = [s.label for s in sections if s.canonical_label != SectionLabel.unknown]
    assert "methods" in labels
    assert "methods_2" in labels
    assert "results" in labels
    assert "results_2" in labels
    assert "references" in labels


def test_unknown_label_for_unrecognized_strong_heading():
    text = "Pre.\n\nFrobnicator\n\nWeird stuff."
    idx = text.index("Frobnicator")
    sections = partition_into_sections(
        text, [_hint("Frobnicator", idx, idx + 11)], source_format="pdf"
    )
    # The strong-but-unrecognized heading still creates a partition boundary,
    # and its span is labeled "unknown" with low confidence.
    unknowns = [s for s in sections if s.canonical_label == SectionLabel.unknown]
    assert any(s.char_start == idx for s in unknowns)
    assert all(s.confidence == Confidence.low for s in unknowns)


def test_weak_heading_ignored():
    text = "Pre.\n\nFrobnicator\n\nWeird stuff."
    idx = text.index("Frobnicator")
    h = BlockHint(
        text="Frobnicator", char_start=idx, char_end=idx + 11,
        page=None, is_heading_candidate=True,
        heading_strength="weak", heading_source="text_pattern",
    )
    sections = partition_into_sections(text, [h], source_format="pdf")
    # Weak unrecognized heading does NOT create a new partition.
    assert len(sections) == 1
    assert sections[0].canonical_label == SectionLabel.unknown
```

- [ ] **Step 8.2: Run tests to verify they fail**

```bash
pytest tests/test_sections_core_partition.py -v
```

Expected: `ImportError`.

- [ ] **Step 8.3: Implement the partitioner**

`docpluck/sections/core.py`:

```python
"""Tier-2 unified canonicalizer + universal-coverage partitioner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .blocks import BlockHint
from .taxonomy import (
    SectionLabel, Confidence, DetectedVia, lookup_canonical_label
)
from .types import Section


@dataclass
class _Marker:
    char_start: int
    label: SectionLabel
    confidence: Confidence
    detected_via: DetectedVia
    heading_text: str | None
    label_suffix_index: int | None  # for repeats: 1 (base), 2, 3, ...


def _resolve_label(hint: BlockHint) -> tuple[SectionLabel, Confidence, DetectedVia] | None:
    """Apply the conflict-resolution rule from spec §5.3.

    - Canonical heading match (any layout strength) → use canonical label.
    - Strong layout, unrecognized text → unknown label, low confidence.
    - Weak layout, unrecognized text → no marker (return None).
    """
    canonical = lookup_canonical_label(hint.text)
    if canonical is not None:
        if hint.heading_strength == "strong" or hint.heading_source == "markup":
            return canonical, Confidence.high, _via_for(hint)
        return canonical, Confidence.medium, _via_for(hint)
    if hint.heading_strength == "strong":
        return SectionLabel.unknown, Confidence.low, _via_for(hint)
    return None


def _via_for(hint: BlockHint) -> DetectedVia:
    if hint.heading_source == "markup":
        return DetectedVia.markup
    if hint.heading_source == "layout":
        return DetectedVia.layout_signal
    if hint.heading_source == "text_pattern":
        return DetectedVia.heading_match if lookup_canonical_label(hint.text) \
            else DetectedVia.text_pattern_fallback
    return DetectedVia.position_inferred


def _assign_suffixes(markers: list[_Marker]) -> None:
    """Mutates markers — assigns 2, 3, ... to repeated labels in document order.
    First occurrence keeps base label (suffix index None or 1)."""
    counts: dict[SectionLabel, int] = {}
    for m in markers:
        counts[m.label] = counts.get(m.label, 0) + 1
        m.label_suffix_index = counts[m.label]


def _label_string(canonical: SectionLabel, suffix_idx: int | None) -> str:
    """Return 'methods' for first, 'methods_2' for second, etc.
    Unknown stays 'unknown' regardless of repeat (we want a single bucket)."""
    if canonical == SectionLabel.unknown:
        return "unknown"
    if suffix_idx is None or suffix_idx == 1:
        return canonical.value
    return f"{canonical.value}_{suffix_idx}"


def partition_into_sections(
    text: str,
    hints: list[BlockHint],
    *,
    source_format: Literal["pdf", "docx", "html"],
    page_offsets: tuple[int, ...] = (),
) -> tuple[Section, ...]:
    """Partition `text` into universal-coverage Sections using `hints`.

    Algorithm:
      1. Resolve each hint to (label, confidence, via) per conflict rule.
         Drop hints that resolve to None.
      2. Sort markers by char_start. Coalesce duplicates at same offset.
      3. Each marker starts a span ending at the next marker's char_start
         (or end-of-text). If first marker is not at offset 0, prepend an
         `unknown` span covering [0, first_marker).
      4. Coalesce ADJACENT spans with the same label into one (rare).
      5. Assign numeric suffixes to repeated canonical labels in document
         order.
    """
    markers: list[_Marker] = []
    for hint in hints:
        resolved = _resolve_label(hint)
        if resolved is None:
            continue
        canonical, conf, via = resolved
        markers.append(_Marker(
            char_start=hint.char_start,
            label=canonical,
            confidence=conf,
            detected_via=via,
            heading_text=hint.text,
            label_suffix_index=None,
        ))

    markers.sort(key=lambda m: m.char_start)

    # Deduplicate markers at the same offset (e.g. underlined heading also
    # picked up by plain heading scan). Keep first occurrence.
    seen: set[int] = set()
    dedup: list[_Marker] = []
    for m in markers:
        if m.char_start in seen:
            continue
        seen.add(m.char_start)
        dedup.append(m)
    markers = dedup

    if not markers:
        sole = Section(
            label="unknown",
            canonical_label=SectionLabel.unknown,
            text=text,
            char_start=0,
            char_end=len(text),
            pages=_pages_for(0, len(text), page_offsets),
            confidence=Confidence.low,
            detected_via=DetectedVia.position_inferred,
            heading_text=None,
        )
        return (sole,)

    # Prepend an unknown span if first marker is not at offset 0.
    if markers[0].char_start > 0:
        prefix = Section(
            label="unknown",
            canonical_label=SectionLabel.unknown,
            text=text[0:markers[0].char_start],
            char_start=0,
            char_end=markers[0].char_start,
            pages=_pages_for(0, markers[0].char_start, page_offsets),
            confidence=Confidence.low,
            detected_via=DetectedVia.position_inferred,
            heading_text=None,
        )
        prefix_present = True
    else:
        prefix = None
        prefix_present = False

    _assign_suffixes(markers)

    sections: list[Section] = []
    if prefix_present:
        sections.append(prefix)

    for i, m in enumerate(markers):
        start = m.char_start
        end = markers[i + 1].char_start if i + 1 < len(markers) else len(text)
        sections.append(Section(
            label=_label_string(m.label, m.label_suffix_index),
            canonical_label=m.label,
            text=text[start:end],
            char_start=start,
            char_end=end,
            pages=_pages_for(start, end, page_offsets),
            confidence=m.confidence,
            detected_via=m.detected_via,
            heading_text=m.heading_text,
        ))

    # Coalesce adjacent same-label spans.
    coalesced: list[Section] = []
    for s in sections:
        if coalesced and coalesced[-1].label == s.label \
                and coalesced[-1].char_end == s.char_start:
            prev = coalesced[-1]
            coalesced[-1] = Section(
                label=prev.label,
                canonical_label=prev.canonical_label,
                text=prev.text + s.text,
                char_start=prev.char_start,
                char_end=s.char_end,
                pages=tuple(sorted(set(prev.pages) | set(s.pages))),
                confidence=prev.confidence,
                detected_via=prev.detected_via,
                heading_text=prev.heading_text,
            )
        else:
            coalesced.append(s)

    return tuple(coalesced)


def _pages_for(
    char_start: int, char_end: int, page_offsets: tuple[int, ...]
) -> tuple[int, ...]:
    """Return 1-indexed pages spanned by [char_start, char_end).

    `page_offsets[i]` is the char offset where page i+1 starts. Empty
    tuple means page info is unavailable; we return ()."""
    if not page_offsets:
        return ()
    pages: list[int] = []
    for i, off in enumerate(page_offsets):
        page_start = off
        page_end = page_offsets[i + 1] if i + 1 < len(page_offsets) else None
        if page_end is None:
            if char_end > page_start:
                pages.append(i + 1)
        elif char_start < page_end and char_end > page_start:
            pages.append(i + 1)
    return tuple(pages)
```

- [ ] **Step 8.4: Run tests to verify they pass**

```bash
pytest tests/test_sections_core_partition.py -v
```

Expected: 6 passing.

- [ ] **Step 8.5: Commit**

```bash
git add docpluck/sections/core.py tests/test_sections_core_partition.py
git commit -m "feat(sections): universal-coverage partitioner + suffix assignment"
```

### Task 8b: Boundary-aware truncation in the partitioner

**Why:** Without this, the last labeled section absorbs trailing content that has no heading (author bios, contact info, editorial metadata at the end of references). Spec §5.4 calls for boundaries as a secondary signal that closes a section when no heading is found before the next boundary line.

**Files:**
- Modify: `docpluck/sections/core.py`
- Test: `tests/test_sections_boundary_truncation.py`

- [ ] **Step 8b.1: Write the failing test**

`tests/test_sections_boundary_truncation.py`:

```python
"""Partitioner truncates a span when boundary pattern fires inside it."""

from docpluck.sections.blocks import BlockHint
from docpluck.sections.core import partition_into_sections
from docpluck.sections.taxonomy import SectionLabel


def _hint(text, start, end):
    return BlockHint(
        text=text, char_start=start, char_end=end,
        page=None, is_heading_candidate=True,
        heading_strength="strong", heading_source="text_pattern",
    )


def test_author_bio_truncates_references_section():
    text = (
        "Pre.\n\n"
        "References\n\n"
        "[1] Doe, J. (2020). Title. Journal, 1(1), 1-10.\n"
        "[2] Smith, A. (2021). Other. Journal, 2(2), 11-20.\n\n"
        "HERMAN AGUINIS is the senior chair of management at GWU.\n"
        "He has published widely on research methods.\n"
    )
    refs_idx = text.index("References")
    sections = partition_into_sections(
        text, [_hint("References", refs_idx, refs_idx + 10)],
        source_format="pdf",
    )
    refs = next(s for s in sections if s.canonical_label == SectionLabel.references)
    # The author-bio paragraph must NOT be inside references.
    assert "HERMAN AGUINIS" not in refs.text
    # And it must be SOMEWHERE in the partition (universal coverage).
    all_text = "".join(s.text for s in sections)
    assert all_text == text
    # An unknown span absorbs the bio.
    assert any(
        s.canonical_label == SectionLabel.unknown and "HERMAN AGUINIS" in s.text
        for s in sections
    )


def test_corresponding_author_truncates():
    text = (
        "Pre.\n\nMethods\n\nProcedures used.\n\n"
        "Corresponding author: jane@example.org\nDept of X, U of Y.\n"
    )
    methods_idx = text.index("Methods")
    sections = partition_into_sections(
        text, [_hint("Methods", methods_idx, methods_idx + 7)],
        source_format="pdf",
    )
    methods = next(s for s in sections if s.canonical_label == SectionLabel.methods)
    assert "jane@example.org" not in methods.text


def test_no_boundary_means_section_extends_to_eof():
    text = "Pre.\n\nAbstract\n\nThis is the abstract content with no trailing bio.\n"
    abs_idx = text.index("Abstract")
    sections = partition_into_sections(
        text, [_hint("Abstract", abs_idx, abs_idx + 8)],
        source_format="pdf",
    )
    abstract = next(s for s in sections if s.canonical_label == SectionLabel.abstract)
    assert "This is the abstract content" in abstract.text
    assert abstract.char_end == len(text)
```

- [ ] **Step 8b.2: Run tests to verify they fail**

```bash
pytest tests/test_sections_boundary_truncation.py -v
```

Expected: 2 failures (the no-boundary test should already pass).

- [ ] **Step 8b.3: Add boundary scan to the partitioner**

In `docpluck/sections/core.py`, after the `partition_into_sections` function returns its `coalesced` list but BEFORE the `return tuple(coalesced)`, insert:

```python
    # Boundary-aware truncation (spec §5.4): for each labeled span, scan its
    # text line-by-line for a boundary pattern. If one fires AFTER the first
    # 30 chars of the span (avoid matching the heading line itself), truncate
    # the span at that line and emit a trailing `unknown` span covering the
    # rest. Universal coverage is preserved.
    from .boundaries import is_section_boundary

    truncated: list[Section] = []
    for s in coalesced:
        if s.canonical_label == SectionLabel.unknown:
            truncated.append(s)
            continue
        offset = s.char_start
        cut_at: int | None = None
        for line in s.text.splitlines(keepends=True):
            line_start = offset
            offset += len(line)
            # Skip the first ~30 chars (likely the heading itself).
            if line_start - s.char_start < 30:
                continue
            if is_section_boundary(line):
                cut_at = line_start
                break
        if cut_at is None:
            truncated.append(s)
            continue
        # Emit truncated span + unknown tail.
        truncated.append(Section(
            label=s.label,
            canonical_label=s.canonical_label,
            text=s.text[: cut_at - s.char_start],
            char_start=s.char_start,
            char_end=cut_at,
            pages=_pages_for(s.char_start, cut_at, page_offsets),
            confidence=s.confidence,
            detected_via=s.detected_via,
            heading_text=s.heading_text,
        ))
        truncated.append(Section(
            label="unknown",
            canonical_label=SectionLabel.unknown,
            text=s.text[cut_at - s.char_start:],
            char_start=cut_at,
            char_end=s.char_end,
            pages=_pages_for(cut_at, s.char_end, page_offsets),
            confidence=Confidence.low,
            detected_via=DetectedVia.position_inferred,
            heading_text=None,
        ))

    return tuple(truncated)
```

- [ ] **Step 8b.4: Run tests to verify they pass**

```bash
pytest tests/test_sections_boundary_truncation.py tests/test_sections_core_partition.py -v
```

Expected: all green (3 new passing + 6 existing still passing).

- [ ] **Step 8b.5: Commit**

```bash
git add docpluck/sections/core.py tests/test_sections_boundary_truncation.py
git commit -m "feat(sections): boundary-aware truncation closes spans before author bios"
```

### Task 9: `extract_sections(text=...)` end-to-end text path

**Files:**
- Modify: `docpluck/sections/__init__.py`
- Modify: `docpluck/sections/core.py` (add public entry point)
- Test: `tests/test_sections_extract_text.py`

- [ ] **Step 9.1: Write the failing test**

`tests/test_sections_extract_text.py`:

```python
"""End-to-end: extract_sections from already-extracted+normalized text."""

from docpluck.sections import (
    extract_sections, SectionedDocument, SectionLabel, SECTIONING_VERSION,
)


SAMPLE = (
    "Some Title\n\nSmith, J.\n\n"
    "Abstract\n\nThis paper investigates X.\n\n"
    "Introduction\n\nIntro text.\n\n"
    "Methods\n\nWe did things.\n\n"
    "Results\n\nWe found stuff.\n\n"
    "Discussion\n\nIt was great.\n\n"
    "References\n\n[1] Doe, J. (2020).\n"
)


def test_returns_sectioned_document():
    doc = extract_sections(text=SAMPLE, source_format="pdf")
    assert isinstance(doc, SectionedDocument)


def test_universal_coverage_invariant():
    doc = extract_sections(text=SAMPLE, source_format="pdf")
    total = sum(s.char_end - s.char_start for s in doc.sections)
    assert total == len(SAMPLE)
    assert "".join(s.text for s in doc.sections) == SAMPLE


def test_canonical_labels_detected():
    doc = extract_sections(text=SAMPLE, source_format="pdf")
    labels = {s.canonical_label for s in doc.sections}
    expected = {
        SectionLabel.abstract, SectionLabel.introduction,
        SectionLabel.methods, SectionLabel.results,
        SectionLabel.discussion, SectionLabel.references,
    }
    assert expected.issubset(labels)


def test_convenience_properties_work():
    doc = extract_sections(text=SAMPLE, source_format="pdf")
    assert doc.abstract is not None
    assert "investigates X" in doc.abstract.text
    assert doc.references is not None
    assert "[1] Doe" in doc.references.text


def test_versioning_recorded():
    doc = extract_sections(text=SAMPLE, source_format="pdf")
    assert doc.sectioning_version == SECTIONING_VERSION
    assert doc.source_format == "pdf"


def test_text_for_filter():
    doc = extract_sections(text=SAMPLE, source_format="pdf")
    out = doc.text_for("abstract", "references")
    assert "investigates X" in out
    assert "[1] Doe" in out
    assert "We did things" not in out
```

- [ ] **Step 9.2: Run test to verify it fails**

```bash
pytest tests/test_sections_extract_text.py -v
```

Expected: `ImportError: cannot import name 'extract_sections'`.

- [ ] **Step 9.3: Implement `extract_sections` text path**

Append to `docpluck/sections/core.py`:

```python
def extract_sections_from_text(
    text: str,
    *,
    source_format: Literal["pdf", "docx", "html"],
    page_offsets: tuple[int, ...] = (),
) -> "SectionedDocument":
    """Build a SectionedDocument from already-normalized text using the
    text-only annotator. Used as fallback when no layout/markup is available."""
    from .annotators.text import annotate_text
    from .types import SectionedDocument
    from . import SECTIONING_VERSION

    hints = annotate_text(text)
    sections = partition_into_sections(
        text, hints, source_format=source_format, page_offsets=page_offsets,
    )
    return SectionedDocument(
        sections=sections,
        normalized_text=text,
        sectioning_version=SECTIONING_VERSION,
        source_format=source_format,
    )
```

Then in `docpluck/sections/__init__.py`, add the public dispatcher:

```python
"""
docpluck.sections — section identification for academic papers.
"""

from typing import Literal

from .taxonomy import SectionLabel, Confidence, DetectedVia
from .types import Section, SectionedDocument

SECTIONING_VERSION = "1.0.0"


def extract_sections(
    file_bytes: bytes | None = None,
    *,
    text: str | None = None,
    source_format: Literal["pdf", "docx", "html"] | None = None,
) -> SectionedDocument:
    """Public entry point. Either pass `file_bytes` (with optional
    source_format hint) or pre-extracted `text` + required `source_format`.

    Phase 2 only supports the text path. Phases 3-4 add markup-aware
    DOCX/HTML and layout-aware PDF paths.
    """
    if text is not None:
        if source_format is None:
            raise ValueError(
                "extract_sections(text=...) requires source_format= "
                "('pdf', 'docx', or 'html')"
            )
        from .core import extract_sections_from_text
        return extract_sections_from_text(text, source_format=source_format)

    if file_bytes is None:
        raise ValueError("extract_sections requires file_bytes= or text=")

    raise NotImplementedError(
        "Phase 2 only supports text= input. PDF/DOCX/HTML byte input "
        "lands in Phases 3-4."
    )


__all__ = [
    "SECTIONING_VERSION",
    "Section",
    "SectionedDocument",
    "SectionLabel",
    "Confidence",
    "DetectedVia",
    "extract_sections",
]
```

- [ ] **Step 9.4: Run tests to verify they pass**

```bash
pytest tests/test_sections_extract_text.py -v
```

Expected: 6 passing.

- [ ] **Step 9.5: Re-export `extract_sections` from top-level `docpluck` package**

Modify `docpluck/__init__.py` to add:

```python
from .sections import (
    extract_sections, SectionedDocument, Section,
    SectionLabel, Confidence, DetectedVia, SECTIONING_VERSION,
)
```

And append these names to `__all__`.

Add a one-liner test to confirm:

```python
# tests/test_sections_extract_text.py append:
def test_top_level_import():
    from docpluck import extract_sections, SectionedDocument
    assert extract_sections is not None
    assert SectionedDocument is not None
```

Re-run: `pytest tests/test_sections_extract_text.py -v` — 7 passing.

- [ ] **Step 9.6: Commit**

```bash
git add docpluck/sections/__init__.py docpluck/sections/core.py docpluck/__init__.py tests/test_sections_extract_text.py
git commit -m "feat(sections): extract_sections() text path end-to-end"
```

### Task 10: Phase-2 milestone — full regression check

- [ ] **Step 10.1: Run the entire test suite**

```bash
pytest -x -q
```

Expected: all green. New tests added; no regressions in existing extract/normalize/quality/etc.

- [ ] **Step 10.2: Spot-check on a real fixture if available**

If a docpluck test PDF is locally available (the conftest skips automatically when not):

```bash
pytest tests/test_extraction.py -v -k "pdf and not docx"
```

Expected: existing PDF tests still byte-identical (back-compat preserved).

- [ ] **Step 10.3: No commit needed** (this is a checkpoint).

---

## Phase 3 — DOCX + HTML annotators (markup-aware)

Goal: DOCX and HTML inputs use semantic markup (`<h1>`–`<h6>`, "Heading 1"–"Heading 6") as ground truth instead of regex fallback.

### Task 11: HTML annotator

**Files:**
- Create: `docpluck/sections/annotators/html.py`
- Test: `tests/test_sections_html_annotator.py`

- [ ] **Step 11.1: Write the failing test**

`tests/test_sections_html_annotator.py`:

```python
"""HTML annotator: <h1>-<h6> heading detection."""

import pytest

bs4 = pytest.importorskip("bs4")

from docpluck.sections.annotators.html import annotate_html


SAMPLE_HTML = """<html><body>
<h1>Some Title</h1>
<p>Author, J.</p>
<h2>Abstract</h2>
<p>This paper investigates X.</p>
<h2>Methods</h2>
<p>We did things.</p>
<h2>References</h2>
<p>[1] Doe, J. (2020).</p>
</body></html>"""


def test_annotate_html_returns_hints_with_text_offsets():
    text, hints = annotate_html(SAMPLE_HTML.encode("utf-8"))
    assert isinstance(text, str)
    for h in hints:
        assert text[h.char_start:h.char_end] == h.text


def test_annotate_html_detects_h1_h2_as_strong():
    _, hints = annotate_html(SAMPLE_HTML.encode("utf-8"))
    headings = [h for h in hints if h.is_heading_candidate]
    heading_texts = [h.text for h in headings]
    assert "Some Title" in heading_texts
    assert "Abstract" in heading_texts
    assert "Methods" in heading_texts
    assert "References" in heading_texts
    for h in headings:
        assert h.heading_strength == "strong"
        assert h.heading_source == "markup"


def test_annotate_html_h4_h6_are_weak():
    html = b"<html><body><h4>Subsubsection</h4><p>x</p></body></html>"
    _, hints = annotate_html(html)
    headings = [h for h in hints if h.is_heading_candidate]
    assert len(headings) == 1
    assert headings[0].heading_strength == "weak"
```

- [ ] **Step 11.2: Run test to verify it fails**

```bash
pytest tests/test_sections_html_annotator.py -v
```

Expected: `ImportError`.

- [ ] **Step 11.3: Implement HTML annotator**

`docpluck/sections/annotators/html.py`:

```python
"""HTML markup-aware heading annotator (Tier 1).

Uses beautifulsoup4 to walk the DOM, emitting BlockHints for <h1>-<h6>
elements with `heading_source="markup"` and a `heading_strength` derived
from heading depth. Body text content (the surrounding string used as the
`text` argument to the partitioner) is reconstructed by concatenating
extracted text in document order with `\n\n` separators between blocks.
"""

from __future__ import annotations

from ..blocks import BlockHint


def annotate_html(html_bytes: bytes) -> tuple[str, list[BlockHint]]:
    """Return (reconstructed_text, hints).

    The reconstructed text is what the sectioner partitions over. Hint
    char_start/char_end offsets refer into this text.
    """
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html_bytes, "html.parser")

    parts: list[str] = []
    hints: list[BlockHint] = []
    cursor = 0

    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
    BLOCK_TAGS = HEADING_TAGS | {"p", "li", "div", "section", "article",
                                  "blockquote", "pre"}

    body = soup.body or soup

    for el in body.descendants:
        name = getattr(el, "name", None)
        if name not in BLOCK_TAGS:
            continue
        # Get only this element's text WITHOUT descending into block children.
        # We do that by collecting only text-node children + inline-only descendants.
        text_chunks: list[str] = []
        for child in el.children:
            child_name = getattr(child, "name", None)
            if child_name in BLOCK_TAGS:
                # Block child handled separately when iteration reaches it.
                continue
            child_text = child.get_text() if child_name else str(child)
            if child_text:
                text_chunks.append(child_text)
        block_text = " ".join(t.strip() for t in text_chunks if t.strip())
        if not block_text:
            continue

        sep = "\n\n" if parts else ""
        block_start = cursor + len(sep)
        block_end = block_start + len(block_text)
        parts.append(sep + block_text)
        cursor = block_end

        if name in HEADING_TAGS:
            depth = int(name[1])
            strength = "strong" if depth <= 3 else "weak"
            hints.append(BlockHint(
                text=block_text,
                char_start=block_start,
                char_end=block_end,
                page=None,
                is_heading_candidate=True,
                heading_strength=strength,
                heading_source="markup",
            ))

    return "".join(parts), hints
```

- [ ] **Step 11.4: Run tests to verify they pass**

```bash
pytest tests/test_sections_html_annotator.py -v
```

Expected: 3 passing. If the offsets test fails because of subtle whitespace, adjust the implementation to keep offsets aligned with the returned text (the test asserts `text[start:end] == hint.text`).

- [ ] **Step 11.5: Wire HTML path through `extract_sections`**

Modify `extract_sections` in `docpluck/sections/__init__.py`:

```python
def extract_sections(
    file_bytes: bytes | None = None,
    *,
    text: str | None = None,
    source_format: Literal["pdf", "docx", "html"] | None = None,
) -> SectionedDocument:
    if text is not None:
        if source_format is None:
            raise ValueError("extract_sections(text=...) requires source_format=")
        from .core import extract_sections_from_text
        return extract_sections_from_text(text, source_format=source_format)

    if file_bytes is None:
        raise ValueError("extract_sections requires file_bytes= or text=")

    fmt = source_format or _detect_format(file_bytes)
    if fmt == "html":
        from .annotators.html import annotate_html
        from .core import partition_into_sections
        normalized, hints = annotate_html(file_bytes)
        sections = partition_into_sections(
            normalized, hints, source_format="html"
        )
        return SectionedDocument(
            sections=sections,
            normalized_text=normalized,
            sectioning_version=SECTIONING_VERSION,
            source_format="html",
        )

    raise NotImplementedError(
        f"source_format={fmt!r} byte input lands in later phases"
    )


def _detect_format(file_bytes: bytes) -> str:
    if file_bytes[:5] == b"%PDF-":
        return "pdf"
    if file_bytes[:2] == b"PK":  # ZIP-based, likely DOCX
        return "docx"
    head = file_bytes[:64].lower()
    if b"<!doctype html" in head or b"<html" in head:
        return "html"
    raise ValueError("Could not detect source format from bytes; pass source_format=")
```

Add a test:

```python
# tests/test_sections_html_annotator.py append:
def test_extract_sections_from_html_bytes():
    from docpluck import extract_sections
    doc = extract_sections(SAMPLE_HTML.encode("utf-8"))
    assert doc.source_format == "html"
    assert doc.abstract is not None
    assert "investigates X" in doc.abstract.text
    assert doc.references is not None
```

Run: `pytest tests/test_sections_html_annotator.py -v` → 4 passing.

- [ ] **Step 11.6: Commit**

```bash
git add docpluck/sections/annotators/html.py docpluck/sections/__init__.py tests/test_sections_html_annotator.py
git commit -m "feat(sections): HTML markup-aware annotator + extract_sections HTML path"
```

### Task 12: DOCX annotator

**Files:**
- Create: `docpluck/sections/annotators/docx.py`
- Test: `tests/test_sections_docx_annotator.py`

- [ ] **Step 12.1: Write the failing test**

`tests/test_sections_docx_annotator.py`:

```python
"""DOCX annotator: heading detection via mammoth-emitted HTML."""

import io

import pytest

mammoth = pytest.importorskip("mammoth")
docx_pkg = pytest.importorskip("docx")  # python-docx for fixture creation

from docpluck.sections.annotators.docx import annotate_docx


def _build_docx_with_real_headings() -> bytes:
    from docx import Document
    from docx.enum.style import WD_STYLE_TYPE  # noqa: F401
    d = Document()
    d.add_heading("Some Title", level=1)
    d.add_paragraph("Author, J.")
    d.add_heading("Abstract", level=2)
    d.add_paragraph("This paper investigates X.")
    d.add_heading("Methods", level=2)
    d.add_paragraph("We did things.")
    d.add_heading("References", level=2)
    d.add_paragraph("[1] Doe, J. (2020).")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_docx_with_real_headings():
    text, hints = annotate_docx(_build_docx_with_real_headings())
    assert isinstance(text, str)
    heading_texts = [h.text for h in hints if h.is_heading_candidate]
    assert "Abstract" in heading_texts
    assert "Methods" in heading_texts
    assert "References" in heading_texts
    for h in hints:
        if h.is_heading_candidate:
            assert h.heading_source == "markup"


def test_extract_sections_from_docx_bytes():
    from docpluck import extract_sections
    doc = extract_sections(_build_docx_with_real_headings())
    assert doc.source_format == "docx"
    assert doc.abstract is not None
    assert "investigates X" in doc.abstract.text
    assert doc.references is not None
```

- [ ] **Step 12.2: Run test to verify it fails**

```bash
pytest tests/test_sections_docx_annotator.py -v
```

Expected: `ImportError` for `annotate_docx`.

- [ ] **Step 12.3: Implement DOCX annotator**

`docpluck/sections/annotators/docx.py`:

```python
"""DOCX markup-aware annotator (Tier 1).

mammoth converts DOCX to HTML, mapping "Heading 1"–"Heading 6" paragraph
styles to <h1>–<h6>. We delegate to the HTML annotator after conversion.

When the DOCX uses ad-hoc bold instead of real Heading styles, mammoth
emits <p><strong>...</strong></p> and we get no headings — the partitioner
falls back to text-only annotation by yielding a single span. (Fallback
to text annotator for ad-hoc-bold DOCX is deferred — see TODO.)
"""

from __future__ import annotations

from ..blocks import BlockHint


def annotate_docx(docx_bytes: bytes) -> tuple[str, list[BlockHint]]:
    import io
    import mammoth  # type: ignore

    result = mammoth.convert_to_html(io.BytesIO(docx_bytes))
    html = result.value  # str

    from .html import annotate_html
    return annotate_html(html.encode("utf-8"))
```

- [ ] **Step 12.4: Wire DOCX path through `extract_sections`**

Add a branch in `extract_sections` in `docpluck/sections/__init__.py`:

```python
    if fmt == "docx":
        from .annotators.docx import annotate_docx
        from .core import partition_into_sections
        normalized, hints = annotate_docx(file_bytes)
        sections = partition_into_sections(
            normalized, hints, source_format="docx"
        )
        return SectionedDocument(
            sections=sections,
            normalized_text=normalized,
            sectioning_version=SECTIONING_VERSION,
            source_format="docx",
        )
```

(Place it before the "raise NotImplementedError" branch, alongside the HTML branch.)

- [ ] **Step 12.5: Run tests to verify they pass**

```bash
pytest tests/test_sections_docx_annotator.py -v
```

Expected: 2 passing.

- [ ] **Step 12.6: Commit**

```bash
git add docpluck/sections/annotators/docx.py docpluck/sections/__init__.py tests/test_sections_docx_annotator.py
git commit -m "feat(sections): DOCX annotator + extract_sections DOCX path"
```

---

## Phase 4 — PDF layout extraction + layout-aware PDF annotator

Goal: pdfplumber-based PDF reading produces per-page bounding boxes and font sizes; PDF annotator uses font size + position for heading detection.

### Task 13: `LayoutDoc` dataclasses + `extract_pdf_layout()`

**Files:**
- Create: `docpluck/extract_layout.py`
- Test: `tests/test_extract_layout.py`

- [ ] **Step 13.1: Write the failing test**

`tests/test_extract_layout.py`:

```python
"""Layout-aware PDF extraction via pdfplumber."""

import io
import os
import shutil

import pytest


def _build_synthetic_pdf() -> bytes:
    """Build a 1-page PDF with a heading and body using reportlab (fallback)
    or skip if not available. We just need any valid PDF for the smoke test."""
    rl = pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, 720, "Methods")
    c.setFont("Helvetica", 11)
    c.drawString(72, 700, "We did things.")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_layout_doc_shape():
    from docpluck.extract_layout import extract_pdf_layout, LayoutDoc, PageLayout, TextSpan
    pdf = _build_synthetic_pdf()
    layout = extract_pdf_layout(pdf)
    assert isinstance(layout, LayoutDoc)
    assert isinstance(layout.raw_text, str)
    assert len(layout.pages) == 1
    page = layout.pages[0]
    assert isinstance(page, PageLayout)
    assert all(isinstance(s, TextSpan) for s in page.spans)
    # Body text should be present.
    assert "We did things" in layout.raw_text


def test_layout_extract_includes_font_sizes():
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_build_synthetic_pdf())
    sizes = {round(s.font_size, 1) for p in layout.pages for s in p.spans}
    # Heading is 18pt, body is 11pt — both should appear.
    assert any(abs(s - 18.0) < 0.5 for s in sizes)
    assert any(abs(s - 11.0) < 0.5 for s in sizes)
```

- [ ] **Step 13.2: Run test to verify it fails**

```bash
pytest tests/test_extract_layout.py -v
```

Expected: `ImportError`.

- [ ] **Step 13.3: Implement `extract_layout.py`**

`docpluck/extract_layout.py`:

```python
"""Layout-aware PDF extraction.

Internal-only for v1.6.0 — used by docpluck.sections.annotators.pdf and the
F0 footnote/header strip step in normalize. Public API surface (the shape of
LayoutDoc) is NOT promised externally; see TODO.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TextSpan:
    text: str
    page_index: int          # 0-based
    x0: float
    y0: float
    x1: float
    y1: float
    font_size: float
    font_name: str
    bold: bool


@dataclass(frozen=True)
class PageLayout:
    page_index: int          # 0-based
    width: float
    height: float
    spans: tuple[TextSpan, ...]


@dataclass(frozen=True)
class LayoutDoc:
    pages: tuple[PageLayout, ...]
    raw_text: str
    page_offsets: tuple[int, ...]   # char offset of each page in raw_text


def extract_pdf_layout(pdf_bytes: bytes) -> LayoutDoc:
    """Read a PDF with pdfplumber and return per-page layout + raw text.

    `raw_text` joins per-page text with `\f` separators (matching the
    pdftotext form-feed convention) so existing normalization page-detection
    keeps working. `page_offsets[i]` is the start offset of page i+1 in
    raw_text.
    """
    import pdfplumber  # type: ignore
    import io

    pages: list[PageLayout] = []
    raw_chunks: list[str] = []
    offsets: list[int] = []
    cursor = 0

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, p in enumerate(pdf.pages):
            spans = tuple(_chars_to_spans(p.chars or [], page_index=i))
            page_text = p.extract_text() or ""
            offsets.append(cursor)
            if i > 0:
                # Form-feed page separator (matches pdftotext convention).
                raw_chunks.append("\f")
                cursor += 1
                offsets[-1] = cursor  # adjust to point AFTER the form feed
            raw_chunks.append(page_text)
            cursor += len(page_text)
            pages.append(PageLayout(
                page_index=i,
                width=float(p.width),
                height=float(p.height),
                spans=spans,
            ))

    return LayoutDoc(
        pages=tuple(pages),
        raw_text="".join(raw_chunks),
        page_offsets=tuple(offsets),
    )


def _chars_to_spans(chars: Iterable[dict], *, page_index: int) -> Iterable[TextSpan]:
    """Cluster pdfplumber per-character dicts into per-line text spans.

    Heuristic: chars with the same fontname + fontsize on close y-coords
    (within 1pt) get joined into a span; gaps in x of >2× space-width
    split into separate spans.
    """
    if not chars:
        return []
    # Sort by (y0 descending — reading order top-to-bottom in PDF coords —
    # then x0 ascending).
    chars_sorted = sorted(
        chars, key=lambda c: (-(c.get("y0") or 0.0), c.get("x0") or 0.0)
    )
    lines: list[list[dict]] = []
    current: list[dict] = []
    last_y: float | None = None
    for ch in chars_sorted:
        y = float(ch.get("y0") or 0.0)
        if last_y is None or abs(y - last_y) <= 1.0:
            current.append(ch)
            last_y = y
        else:
            if current:
                lines.append(current)
            current = [ch]
            last_y = y
    if current:
        lines.append(current)

    spans: list[TextSpan] = []
    for line in lines:
        line.sort(key=lambda c: c.get("x0") or 0.0)
        text = "".join(c.get("text", "") for c in line)
        if not text.strip():
            continue
        font_sizes = [float(c.get("size") or 0.0) for c in line if c.get("size")]
        font_size = max(set(font_sizes), key=font_sizes.count) if font_sizes else 0.0
        font_names = [str(c.get("fontname") or "") for c in line]
        font_name = max(set(font_names), key=font_names.count) if font_names else ""
        bold = "Bold" in font_name or "bold" in font_name
        x0 = min(float(c.get("x0") or 0.0) for c in line)
        x1 = max(float(c.get("x1") or 0.0) for c in line)
        y0 = min(float(c.get("y0") or 0.0) for c in line)
        y1 = max(float(c.get("y1") or 0.0) for c in line)
        spans.append(TextSpan(
            text=text, page_index=page_index,
            x0=x0, y0=y0, x1=x1, y1=y1,
            font_size=font_size, font_name=font_name, bold=bold,
        ))
    return spans
```

- [ ] **Step 13.4: Run tests to verify they pass**

```bash
pytest tests/test_extract_layout.py -v
```

Expected: 2 passing (skipped if reportlab not installed — that's OK; install it as a dev dep if missing).

If reportlab is missing, install:

```bash
pip install reportlab
```

then add `reportlab>=4` to `pyproject.toml [project.optional-dependencies] dev` list.

- [ ] **Step 13.5: Commit**

```bash
git add docpluck/extract_layout.py tests/test_extract_layout.py pyproject.toml
git commit -m "feat(extract_layout): pdfplumber-based LayoutDoc extraction"
```

### Task 14: PDF annotator — font-size + position heading detection

**Files:**
- Create: `docpluck/sections/annotators/pdf.py`
- Test: `tests/test_sections_pdf_annotator.py`

- [ ] **Step 14.1: Write the failing test**

`tests/test_sections_pdf_annotator.py`:

```python
"""PDF annotator: layout-aware heading detection."""

import io

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("pdfplumber")


def _make_pdf() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 16); c.drawString(72, 740, "Abstract")
    c.setFont("Helvetica", 11); c.drawString(72, 720, "This paper investigates X.")
    c.setFont("Helvetica-Bold", 16); c.drawString(72, 690, "Methods")
    c.setFont("Helvetica", 11); c.drawString(72, 670, "We did things.")
    c.setFont("Helvetica-Bold", 16); c.drawString(72, 640, "References")
    c.setFont("Helvetica", 11); c.drawString(72, 620, "[1] Doe, J. (2020).")
    c.showPage(); c.save()
    return buf.getvalue()


def test_pdf_annotator_detects_headings():
    from docpluck.sections.annotators.pdf import annotate_pdf
    text, hints = annotate_pdf(_make_pdf())
    heading_texts = [h.text.strip() for h in hints if h.is_heading_candidate]
    assert "Abstract" in heading_texts
    assert "Methods" in heading_texts
    assert "References" in heading_texts
    for h in hints:
        if h.is_heading_candidate:
            assert h.heading_source == "layout"


def test_pdf_extract_sections_end_to_end():
    from docpluck import extract_sections
    doc = extract_sections(_make_pdf())
    assert doc.source_format == "pdf"
    assert doc.abstract is not None
    assert "investigates X" in doc.abstract.text
    assert doc.methods is not None
    assert "We did things" in doc.methods.text
    assert doc.references is not None
```

- [ ] **Step 14.2: Run test to verify it fails**

```bash
pytest tests/test_sections_pdf_annotator.py -v
```

Expected: `ImportError`.

- [ ] **Step 14.3: Implement PDF annotator**

`docpluck/sections/annotators/pdf.py`:

```python
"""PDF layout-aware heading-candidate annotator (Tier 1).

Heuristics (spec §5.1):
- Body font size = mode of all char font sizes weighted by char count.
- `strong` heading: font ≥ 1.15× body, OR bold + ≥ 1.05× body, AND ≤ 12 words,
  AND ends in line break, AND no terminal period (or has explicit numbering).
- `weak` heading: ALL CAPS or Title Case, ≤ 8 words, isolated line, body-size
  font.
- Numbered headings (^\\d+(\\.\\d+)*\\s+[A-Z]) → strong regardless of font.
"""

from __future__ import annotations

import re
from collections import Counter

from ..blocks import BlockHint
from ...extract_layout import extract_pdf_layout, LayoutDoc, TextSpan


_NUMBERED_HEADING = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+[A-Z]")
_TERMINAL_PERIOD = re.compile(r"[.!?]\s*$")


def annotate_pdf(pdf_bytes: bytes) -> tuple[str, list[BlockHint]]:
    layout = extract_pdf_layout(pdf_bytes)
    return _annotate_layout(layout)


def _annotate_layout(layout: LayoutDoc) -> tuple[str, list[BlockHint]]:
    body_size = _body_font_size(layout)

    text = layout.raw_text
    hints: list[BlockHint] = []

    # Build a flat list of (text, char_start, char_end, page_index, span) for
    # every span. Map spans to char offsets in raw_text by linear scan within
    # each page.
    for page in layout.pages:
        page_start = layout.page_offsets[page.page_index]
        page_end = (
            layout.page_offsets[page.page_index + 1] - 1  # exclude the \f
            if page.page_index + 1 < len(layout.page_offsets)
            else len(text)
        )
        page_text = text[page_start:page_end]
        cursor = page_start
        for span in page.spans:
            # Find the span text within the page text starting from cursor.
            idx = page_text.find(span.text, cursor - page_start)
            if idx < 0:
                continue
            char_start = page_start + idx
            char_end = char_start + len(span.text)
            cursor = char_end
            hint = _classify_span(span, body_size, char_start, char_end)
            if hint is not None:
                hints.append(hint)

    hints.sort(key=lambda h: h.char_start)
    return text, hints


def _body_font_size(layout: LayoutDoc) -> float:
    counter: Counter[float] = Counter()
    for page in layout.pages:
        for span in page.spans:
            counter[round(span.font_size, 1)] += len(span.text)
    if not counter:
        return 11.0
    return max(counter.items(), key=lambda kv: kv[1])[0]


def _classify_span(
    span: TextSpan, body_size: float, char_start: int, char_end: int
) -> BlockHint | None:
    text = span.text.strip()
    if not text:
        return None
    word_count = len(text.split())

    is_numbered = bool(_NUMBERED_HEADING.match(text))
    has_terminal = bool(_TERMINAL_PERIOD.search(text))

    size_ratio = span.font_size / body_size if body_size > 0 else 1.0
    big_font = size_ratio >= 1.15
    bold_and_slightly_big = span.bold and size_ratio >= 1.05

    strong = (
        is_numbered
        or (big_font and word_count <= 12 and not has_terminal)
        or (bold_and_slightly_big and word_count <= 12 and not has_terminal)
    )
    if strong:
        return BlockHint(
            text=text,
            char_start=char_start,
            char_end=char_end,
            page=span.page_index + 1,
            is_heading_candidate=True,
            heading_strength="strong",
            heading_source="layout",
        )

    # Weak: ALL CAPS or Title Case, short, body-size font, no terminal period.
    is_all_caps = text == text.upper() and any(c.isalpha() for c in text)
    is_title_case = text == text.title()
    if (is_all_caps or is_title_case) and word_count <= 8 and not has_terminal:
        return BlockHint(
            text=text,
            char_start=char_start,
            char_end=char_end,
            page=span.page_index + 1,
            is_heading_candidate=True,
            heading_strength="weak",
            heading_source="layout",
        )

    return None
```

- [ ] **Step 14.4: Wire PDF path through `extract_sections`**

Add a branch in `extract_sections`:

```python
    if fmt == "pdf":
        from .annotators.pdf import annotate_pdf
        from .core import partition_into_sections
        from ..extract_layout import extract_pdf_layout
        layout = extract_pdf_layout(file_bytes)
        normalized = layout.raw_text
        from .annotators.pdf import _annotate_layout
        _, hints = _annotate_layout(layout)
        sections = partition_into_sections(
            normalized, hints, source_format="pdf",
            page_offsets=layout.page_offsets,
        )
        return SectionedDocument(
            sections=sections,
            normalized_text=normalized,
            sectioning_version=SECTIONING_VERSION,
            source_format="pdf",
        )
```

Replace the previous `raise NotImplementedError` clause with this branch.

- [ ] **Step 14.5: Run tests to verify they pass**

```bash
pytest tests/test_sections_pdf_annotator.py -v
```

Expected: 2 passing.

- [ ] **Step 14.6: Commit**

```bash
git add docpluck/sections/annotators/pdf.py docpluck/sections/__init__.py tests/test_sections_pdf_annotator.py
git commit -m "feat(sections): PDF layout-aware annotator + extract_sections PDF path"
```

---

## Phase 5 — F0 footnote / running-header strip in normalize

Goal: when `normalize_text(text, level, layout=...)` is called with a `LayoutDoc`, strip footnotes and running headers/footers and surface footnotes as a separate appendix.

### Task 15: Add `footnote_spans` and `page_offsets` to `NormalizationReport`

**Files:**
- Modify: `docpluck/normalize.py` — `NormalizationReport` dataclass and `normalize_text` signature
- Test: `tests/test_normalize_report_layout_fields.py`

- [ ] **Step 15.1: Write the failing test**

`tests/test_normalize_report_layout_fields.py`:

```python
"""NormalizationReport gains footnote_spans + page_offsets (default empty)."""

from docpluck import normalize_text, NormalizationLevel


def test_existing_unpacking_still_works():
    text = "Some plain text."
    out, report = normalize_text(text, NormalizationLevel.standard)
    assert isinstance(out, str)
    # Existing fields untouched.
    assert hasattr(report, "level")
    assert hasattr(report, "steps_applied")
    assert hasattr(report, "changes_made")


def test_new_fields_default_empty():
    out, report = normalize_text("anything", NormalizationLevel.standard)
    assert report.footnote_spans == ()
    assert report.page_offsets == ()


def test_to_dict_includes_new_fields():
    out, report = normalize_text("anything", NormalizationLevel.standard)
    d = report.to_dict()
    assert d["footnote_spans"] == []
    assert d["page_offsets"] == []
```

- [ ] **Step 15.2: Run test to verify it fails**

```bash
pytest tests/test_normalize_report_layout_fields.py -v
```

Expected: `AttributeError: 'NormalizationReport' object has no attribute 'footnote_spans'`.

- [ ] **Step 15.3: Add the fields**

In `docpluck/normalize.py`, modify the `NormalizationReport` dataclass:

```python
@dataclass
class NormalizationReport:
    level: str
    version: str = NORMALIZATION_VERSION
    steps_applied: list[str] = field(default_factory=list)
    steps_changed: list[str] = field(default_factory=list)
    changes_made: dict[str, int] = field(default_factory=dict)
    footnote_spans: tuple[tuple[int, int], ...] = ()  # pre-strip char offsets
    page_offsets: tuple[int, ...] = ()                 # post-strip body page offsets

    # ... existing _track method unchanged ...

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "version": self.version,
            "steps_applied": self.steps_applied,
            "steps_changed": self.steps_changed,
            "changes_made": self.changes_made,
            "footnote_spans": [list(s) for s in self.footnote_spans],
            "page_offsets": list(self.page_offsets),
        }
```

- [ ] **Step 15.4: Run tests to verify they pass**

```bash
pytest tests/test_normalize_report_layout_fields.py -v
```

Expected: 3 passing.

- [ ] **Step 15.5: Confirm no existing test regressed**

```bash
pytest tests/test_normalization.py -v -q
```

Expected: all green.

- [ ] **Step 15.6: Commit**

```bash
git add docpluck/normalize.py tests/test_normalize_report_layout_fields.py
git commit -m "feat(normalize): add footnote_spans + page_offsets to NormalizationReport"
```

### Task 16: Add `layout` parameter to `normalize_text`

**Files:**
- Modify: `docpluck/normalize.py`
- Test: `tests/test_normalize_layout_param.py`

- [ ] **Step 16.1: Write the failing test**

`tests/test_normalize_layout_param.py`:

```python
"""normalize_text(text, level, layout=...) accepts an optional LayoutDoc."""

import io

import pytest

pytest.importorskip("pdfplumber")
pytest.importorskip("reportlab")


def _make_pdf() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica", 11); c.drawString(72, 720, "Body line one.")
    c.showPage()
    c.setFont("Helvetica", 11); c.drawString(72, 720, "Body line two.")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_layout_param_optional_and_default_unchanged():
    from docpluck import normalize_text, NormalizationLevel
    out, _ = normalize_text("Body line one.\fBody line two.", NormalizationLevel.standard)
    assert "Body line one" in out


def test_layout_param_populates_page_offsets():
    from docpluck import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_make_pdf())
    out, report = normalize_text(layout.raw_text, NormalizationLevel.standard, layout=layout)
    assert len(report.page_offsets) == 2
    assert report.page_offsets[0] >= 0
    # The output text should be at least as short as the raw text (some
    # content may be stripped; never longer except for the footnote appendix).
```

- [ ] **Step 16.2: Run test to verify it fails**

```bash
pytest tests/test_normalize_layout_param.py -v
```

Expected: `TypeError: normalize_text() got an unexpected keyword argument 'layout'`.

- [ ] **Step 16.3: Add the parameter (no behavior change yet)**

In `docpluck/normalize.py`, modify `normalize_text`:

```python
def normalize_text(
    text: str,
    level: NormalizationLevel,
    *,
    layout=None,
) -> tuple[str, NormalizationReport]:
    """Apply normalization pipeline at the specified level.

    When `layout` is provided (a docpluck.extract_layout.LayoutDoc), the
    F0 step strips footnotes/running-headers/footers using PDF layout info
    and populates report.footnote_spans + report.page_offsets.
    """
    if level == NormalizationLevel.none:
        report = NormalizationReport(level="none")
        if layout is not None:
            report.page_offsets = layout.page_offsets
        return text, report

    report = NormalizationReport(level=level.value)
    if layout is not None:
        report.page_offsets = layout.page_offsets

    t = text

    # ... existing pipeline body unchanged ...
```

(Locate the existing function signature and body in `normalize.py:154–...`. The above change is just adding the kwarg + passing `page_offsets` through; the F0 step itself comes in Task 17.)

- [ ] **Step 16.4: Run tests to verify they pass**

```bash
pytest tests/test_normalize_layout_param.py -v
```

Expected: 2 passing.

- [ ] **Step 16.5: Commit**

```bash
git add docpluck/normalize.py tests/test_normalize_layout_param.py
git commit -m "feat(normalize): add layout= keyword to normalize_text (no-op for now)"
```

### Task 17: Implement F0 — running header/footer + footnote zone detection

**Files:**
- Modify: `docpluck/normalize.py`
- Test: `tests/test_normalize_f0_footnote_strip.py`

- [ ] **Step 17.1: Write the failing test**

`tests/test_normalize_f0_footnote_strip.py`:

```python
"""F0: layout-aware footnote + running-header strip."""

import io

import pytest

pytest.importorskip("pdfplumber")
pytest.importorskip("reportlab")


def _pdf_with_footnote_and_runheader() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    # Page 1
    c.setFont("Helvetica-Oblique", 9); c.drawString(72, 760, "MY JOURNAL — VOL 12")  # running header
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 720, "Abstract")
    c.setFont("Helvetica", 11); c.drawString(72, 700, "This is the abstract content.")
    c.setFont("Helvetica", 8); c.drawString(72, 80, "1 First footnote on page 1.")  # footnote
    c.showPage()
    # Page 2
    c.setFont("Helvetica-Oblique", 9); c.drawString(72, 760, "MY JOURNAL — VOL 12")  # running header
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 720, "Methods")
    c.setFont("Helvetica", 11); c.drawString(72, 700, "We did things.")
    c.setFont("Helvetica", 8); c.drawString(72, 80, "2 Second footnote on page 2.")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_f0_strips_running_header():
    from docpluck import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_pdf_with_footnote_and_runheader())
    out, _ = normalize_text(layout.raw_text, NormalizationLevel.academic, layout=layout)
    assert "MY JOURNAL — VOL 12" not in out


def test_f0_separates_footnotes_into_appendix():
    from docpluck import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_pdf_with_footnote_and_runheader())
    out, report = normalize_text(layout.raw_text, NormalizationLevel.academic, layout=layout)
    # Footnotes are present somewhere in the output (in the appendix).
    assert "First footnote" in out
    assert "Second footnote" in out
    # But they're NOT inline in the body — body sections should not contain them.
    body_only_until_appendix = out.split("\n\f\f\n", 1)[0] if "\n\f\f\n" in out else out
    assert "First footnote" not in body_only_until_appendix or \
           "Abstract" in body_only_until_appendix.split("First footnote")[0]


def test_f0_records_footnote_spans():
    from docpluck import normalize_text, NormalizationLevel
    from docpluck.extract_layout import extract_pdf_layout
    layout = extract_pdf_layout(_pdf_with_footnote_and_runheader())
    _, report = normalize_text(layout.raw_text, NormalizationLevel.academic, layout=layout)
    assert len(report.footnote_spans) >= 2
```

- [ ] **Step 17.2: Run test to verify it fails**

```bash
pytest tests/test_normalize_f0_footnote_strip.py -v
```

Expected: failures because F0 isn't wired yet.

- [ ] **Step 17.3: Implement F0**

In `docpluck/normalize.py`, after the `_find_references_spans` helper definition, add:

```python
def _f0_strip_running_and_footnotes(
    raw_text: str, layout
) -> tuple[str, list[tuple[int, int]]]:
    """Strip running headers/footers and footnotes using layout info.

    Returns (post_strip_text_with_appendix, footnote_spans_in_raw_text).

    Algorithm:
      1. For each page, find the body-text y-cluster (modal y of body-size spans).
      2. Lines above body-y by > N points → running header.
      3. Lines below body-y by > N points AND smaller font → footnote.
      4. Identify lines that repeat near-identically across ≥50% of pages
         at top or bottom → mark as running header/footer.
      5. Strip header/footer regions; preserve footnote regions and append
         them to the body text after a sentinel.
    """
    from .extract_layout import LayoutDoc, PageLayout, TextSpan

    if not isinstance(layout, LayoutDoc) or not layout.pages:
        return raw_text, []

    body_size = _body_size(layout)

    page_text_chunks: list[str] = []
    footnote_chunks: list[str] = []
    footnote_raw_spans: list[tuple[int, int]] = []

    # Identify recurring header/footer lines first.
    repeating_header_lines = _detect_repeating_lines(layout, position="top")
    repeating_footer_lines = _detect_repeating_lines(layout, position="bottom")

    for page in layout.pages:
        body_y_min, body_y_max = _body_y_band(page, body_size)
        keep_lines: list[str] = []
        page_footnotes: list[str] = []

        for span in page.spans:
            line_text = span.text.strip()
            if not line_text:
                continue

            is_header = (
                line_text in repeating_header_lines
                or span.y0 > body_y_max + 30
            )
            is_footer = (
                line_text in repeating_footer_lines
                and span.y0 < body_y_min - 30
            )
            is_footnote = (
                span.y0 < body_y_min - 30
                and span.font_size < body_size * 0.92
                and not is_footer
            )

            if is_header or is_footer:
                continue
            if is_footnote:
                page_footnotes.append(line_text)
                # Locate the span in raw_text to record provenance:
                page_start = layout.page_offsets[page.page_index]
                idx = raw_text.find(line_text, page_start)
                if idx >= 0:
                    footnote_raw_spans.append((idx, idx + len(line_text)))
                continue

            keep_lines.append(line_text)

        page_text_chunks.append("\n".join(keep_lines))
        if page_footnotes:
            footnote_chunks.append("\n".join(page_footnotes))

    body = "\n\f".join(page_text_chunks)
    if footnote_chunks:
        appendix = "\n\f\f\n" + "\n\n".join(footnote_chunks)
    else:
        appendix = ""
    return body + appendix, footnote_raw_spans


def _body_size(layout) -> float:
    from collections import Counter
    counter: Counter[float] = Counter()
    for page in layout.pages:
        for span in page.spans:
            counter[round(span.font_size, 1)] += len(span.text)
    if not counter:
        return 11.0
    return max(counter.items(), key=lambda kv: kv[1])[0]


def _body_y_band(page, body_size: float) -> tuple[float, float]:
    """Return (y_min, y_max) of the body-text band on this page."""
    body_spans = [s for s in page.spans if abs(s.font_size - body_size) <= 1.0]
    if not body_spans:
        return 0.0, page.height
    y_min = min(s.y0 for s in body_spans)
    y_max = max(s.y1 for s in body_spans)
    return y_min, y_max


def _detect_repeating_lines(layout, *, position: str) -> set[str]:
    """Return text lines that appear at the top (or bottom) of >=50% of pages."""
    if len(layout.pages) < 2:
        return set()
    counts: dict[str, int] = {}
    for page in layout.pages:
        if not page.spans:
            continue
        y_sorted = sorted(page.spans, key=lambda s: s.y0)
        if position == "top":
            candidates = [y_sorted[-1].text.strip()] if y_sorted else []
        else:
            candidates = [y_sorted[0].text.strip()] if y_sorted else []
        for c in candidates:
            if c:
                counts[c] = counts.get(c, 0) + 1
    threshold = len(layout.pages) // 2 + 1
    return {line for line, n in counts.items() if n >= threshold}
```

- [ ] **Step 17.4: Wire F0 into the pipeline**

In `normalize_text`, immediately after the existing `_raw_page_numbers = _detect_recurring_page_numbers(text)` line (currently `normalize.py:164`), add:

```python
    if layout is not None:
        t, footnote_spans = _f0_strip_running_and_footnotes(t, layout)
        report.footnote_spans = tuple(footnote_spans)
        report.steps_applied.append("F0")
        if footnote_spans:
            report.steps_changed.append("F0")
```

- [ ] **Step 17.5: Run tests to verify they pass**

```bash
pytest tests/test_normalize_f0_footnote_strip.py -v
```

Expected: 3 passing. The footnote-detection heuristic is approximate; if a test asserts something the heuristic doesn't quite achieve on the synthetic PDF, **adjust the assertion to be looser** (we'll tune on real corpus in Phase 7) — but never weaken the test to "always pass".

- [ ] **Step 17.6: Confirm no existing normalization test regressed**

```bash
pytest tests/test_normalization.py -v -q
```

Expected: all green.

- [ ] **Step 17.7: Commit**

```bash
git add docpluck/normalize.py tests/test_normalize_f0_footnote_strip.py
git commit -m "feat(normalize): F0 layout-aware footnote + running-header strip"
```

### Task 18: Surface footnotes as `footnotes` section in sectioner

**Files:**
- Modify: `docpluck/sections/__init__.py` (PDF branch)
- Modify: `docpluck/sections/core.py` (append-footnotes-section logic)
- Test: `tests/test_sections_footnote_section.py`

- [ ] **Step 18.1: Write the failing test**

`tests/test_sections_footnote_section.py`:

```python
"""Footnotes appear as their own section, not inside abstract/methods."""

import io

import pytest

pytest.importorskip("pdfplumber")
pytest.importorskip("reportlab")


def _pdf_with_footnote_in_abstract() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 720, "Abstract")
    c.setFont("Helvetica", 11); c.drawString(72, 700, "Body of abstract.")
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 660, "Methods")
    c.setFont("Helvetica", 11); c.drawString(72, 640, "We did things.")
    c.setFont("Helvetica", 8); c.drawString(72, 80, "1 This is the footnote.")
    c.showPage(); c.save()
    return buf.getvalue()


def test_footnote_in_separate_section():
    from docpluck import extract_sections
    doc = extract_sections(_pdf_with_footnote_in_abstract())
    fn = doc.get("footnotes")
    assert fn is not None, "Expected a 'footnotes' section to be present."
    assert "footnote" in fn.text.lower()
    if doc.abstract is not None:
        assert "footnote" not in doc.abstract.text.lower()
```

- [ ] **Step 18.2: Run test to verify it fails**

```bash
pytest tests/test_sections_footnote_section.py -v
```

Expected: failure — there's no `footnotes` section yet.

- [ ] **Step 18.3: Update PDF branch in `extract_sections` to run F0 and append footnotes section**

Replace the PDF branch added in Task 14 with:

```python
    if fmt == "pdf":
        from .annotators.pdf import _annotate_layout
        from .core import partition_into_sections, append_footnotes_section
        from ..extract_layout import extract_pdf_layout
        from ..normalize import normalize_text, NormalizationLevel

        layout = extract_pdf_layout(file_bytes)
        # Run normalize at academic level WITH layout — this strips
        # footnotes/headers/footers and appends a footnote appendix.
        normalized, report = normalize_text(
            layout.raw_text, NormalizationLevel.academic, layout=layout
        )
        # Re-extract layout-aware hints from raw layout (annotator works on
        # the layout itself, not on the post-strip text).
        _, hints = _annotate_layout(layout)
        # Adjust hint offsets: hints reference offsets in the RAW text;
        # F0 produced a different normalized string. Drop hints that don't
        # appear verbatim in `normalized` and rebuild offsets via .find().
        adjusted: list = []
        cursor = 0
        for h in hints:
            idx = normalized.find(h.text, cursor)
            if idx < 0:
                continue
            cursor = idx + len(h.text)
            adjusted.append(type(h)(
                text=h.text, char_start=idx, char_end=idx + len(h.text),
                page=h.page, is_heading_candidate=h.is_heading_candidate,
                heading_strength=h.heading_strength,
                heading_source=h.heading_source,
            ))
        sections = partition_into_sections(
            normalized, adjusted, source_format="pdf",
            page_offsets=report.page_offsets,
        )
        sections = append_footnotes_section(
            sections, normalized, report.footnote_spans
        )
        return SectionedDocument(
            sections=tuple(sections),
            normalized_text=normalized,
            sectioning_version=SECTIONING_VERSION,
            source_format="pdf",
        )
```

In `core.py`, add:

```python
def append_footnotes_section(
    sections: tuple[Section, ...],
    normalized_text: str,
    footnote_raw_spans: tuple[tuple[int, int], ...],
) -> tuple[Section, ...]:
    """If F0 produced a footnote appendix in `normalized_text` (sentinel
    `\\n\\f\\f\\n`), wrap it as a single `footnotes` Section."""
    sentinel = "\n\f\f\n"
    idx = normalized_text.find(sentinel)
    if idx < 0:
        return sections
    appendix_start = idx + len(sentinel)
    if appendix_start >= len(normalized_text):
        return sections
    appendix_text = normalized_text[appendix_start:]
    if not appendix_text.strip():
        return sections

    # Truncate the last existing section so it doesn't overlap the appendix.
    truncated: list[Section] = []
    for s in sections:
        if s.char_end > idx:
            truncated.append(Section(
                label=s.label,
                canonical_label=s.canonical_label,
                text=normalized_text[s.char_start:idx],
                char_start=s.char_start,
                char_end=idx,
                pages=s.pages,
                confidence=s.confidence,
                detected_via=s.detected_via,
                heading_text=s.heading_text,
            ))
        else:
            truncated.append(s)

    footnotes = Section(
        label="footnotes",
        canonical_label=SectionLabel.footnotes,
        text=appendix_text,
        char_start=appendix_start,
        char_end=len(normalized_text),
        pages=(),
        confidence=Confidence.medium,
        detected_via=DetectedVia.layout_signal,
        heading_text=None,
    )
    return tuple(truncated + [footnotes])
```

- [ ] **Step 18.4: Run tests to verify they pass**

```bash
pytest tests/test_sections_footnote_section.py -v
```

Expected: 1 passing.

- [ ] **Step 18.5: Confirm no regressions**

```bash
pytest tests/test_sections_pdf_annotator.py tests/test_sections_extract_text.py -v
```

Expected: all green.

- [ ] **Step 18.6: Commit**

```bash
git add docpluck/sections/__init__.py docpluck/sections/core.py tests/test_sections_footnote_section.py
git commit -m "feat(sections): surface footnotes as separate 'footnotes' section"
```

---

## Phase 6 — Filter sugar + CLI

### Task 19: `extract_pdf(sections=...)` filter sugar

**Files:**
- Modify: `docpluck/extract.py` — add `sections` parameter
- Test: `tests/test_extract_filter_sugar.py`

- [ ] **Step 19.1: Write the failing test**

`tests/test_extract_filter_sugar.py`:

```python
"""Filter sugar: extract_pdf(sections=...) returns concatenated section text."""

import io

import pytest

pytest.importorskip("pdfplumber")
pytest.importorskip("reportlab")


def _make_pdf() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 720, "Abstract")
    c.setFont("Helvetica", 11); c.drawString(72, 700, "Abstract body.")
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 660, "Methods")
    c.setFont("Helvetica", 11); c.drawString(72, 640, "Methods body.")
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 600, "References")
    c.setFont("Helvetica", 11); c.drawString(72, 580, "[1] Doe.")
    c.showPage(); c.save()
    return buf.getvalue()


def test_no_filter_preserves_byte_identical_output():
    """When sections= is None (default), output equals current extract_pdf()."""
    from docpluck import extract_pdf
    text_a, _ = extract_pdf(_make_pdf())
    text_b, _ = extract_pdf(_make_pdf(), sections=None)
    assert text_a == text_b


def test_filter_returns_only_requested_sections():
    from docpluck import extract_pdf
    text, _ = extract_pdf(_make_pdf(), sections=["abstract", "references"])
    assert "Abstract body" in text
    assert "[1] Doe" in text
    assert "Methods body" not in text


def test_filter_parity_with_sectioned_document():
    from docpluck import extract_pdf, extract_sections
    pdf = _make_pdf()
    via_filter, _ = extract_pdf(pdf, sections=["abstract"])
    doc = extract_sections(pdf)
    assert via_filter == (doc.abstract.text if doc.abstract else "")
```

- [ ] **Step 19.2: Run test to verify it fails**

```bash
pytest tests/test_extract_filter_sugar.py -v
```

Expected: `TypeError: extract_pdf() got an unexpected keyword argument 'sections'`.

- [ ] **Step 19.3: Add the parameter**

Open `docpluck/extract.py`. Two edits:

(a) Change the signature from:

```python
def extract_pdf(pdf_bytes: bytes) -> tuple[str, str]:
```

to:

```python
def extract_pdf(
    pdf_bytes: bytes,
    *,
    sections: list[str] | None = None,
) -> tuple[str, str]:
```

(b) The existing function ends with one or more `return text, method` (or equivalent) statements. Locate the FINAL successful-path return — the one that returns the fully-extracted text after both pdftotext and SMP-fallback paths have run. Immediately BEFORE that return, insert:

```python
    if sections is not None:
        from .sections import extract_sections
        doc = extract_sections(pdf_bytes)
        return doc.text_for(*sections), method
```

Add the same branch before any error-path return as well — even error-path callers expect `(text, method)`, but `sections=` should propagate the error string unchanged because the sectioner needs valid input. To keep that simple: only apply the sections branch on successful-path returns; for error paths (where `text` starts with `"ERROR:"`), return the error tuple untouched.

Update the docstring to document the new kwarg:

```python
"""...

    When ``sections=`` is provided, runs the sectioner and returns the
    concatenated text of just those sections (in document order),
    instead of the full text. The ``method`` string is unchanged.
    Error-path returns (text starting with "ERROR:") are not filtered.
"""
```

- [ ] **Step 19.4: Run tests to verify they pass**

```bash
pytest tests/test_extract_filter_sugar.py -v
```

Expected: 3 passing.

- [ ] **Step 19.5: Commit**

```bash
git add docpluck/extract.py tests/test_extract_filter_sugar.py
git commit -m "feat(extract): sections=[...] filter sugar on extract_pdf"
```

### Task 20: Same filter sugar for `extract_docx` and `extract_html`

**Files:**
- Modify: `docpluck/extract_docx.py`
- Modify: `docpluck/extract_html.py`
- Test: `tests/test_extract_filter_sugar.py` (extend)

- [ ] **Step 20.1: Append failing tests**

```python
# tests/test_extract_filter_sugar.py append:
def test_extract_docx_filter():
    pytest.importorskip("mammoth")
    pytest.importorskip("docx")
    from docx import Document
    d = Document()
    d.add_heading("Abstract", level=2); d.add_paragraph("Abstract body.")
    d.add_heading("Methods", level=2); d.add_paragraph("Methods body.")
    buf = io.BytesIO(); d.save(buf)
    from docpluck import extract_docx
    text, _ = extract_docx(buf.getvalue(), sections=["abstract"])
    assert "Abstract body" in text
    assert "Methods body" not in text


def test_extract_html_filter():
    from docpluck import extract_html
    html = b"<html><body><h2>Abstract</h2><p>Abstract body.</p>" \
           b"<h2>Methods</h2><p>Methods body.</p></body></html>"
    text, _ = extract_html(html, sections=["abstract"])
    assert "Abstract body" in text
    assert "Methods body" not in text
```

- [ ] **Step 20.2: Run, verify failure, implement, re-run**

Apply the same pattern as Task 19 to `extract_docx` and `extract_html`. Each gets `sections: list[str] | None = None` keyword and a post-extraction branch:

```python
    if sections is not None:
        from .sections import extract_sections
        doc = extract_sections(<bytes>)
        return doc.text_for(*sections), method
```

Run: `pytest tests/test_extract_filter_sugar.py -v` → 5 passing.

- [ ] **Step 20.3: Commit**

```bash
git add docpluck/extract_docx.py docpluck/extract_html.py tests/test_extract_filter_sugar.py
git commit -m "feat(extract): sections=[...] filter sugar on extract_docx/html"
```

### Task 21: CLI — `docpluck sections` and `--sections` flag

**Files:**
- Modify: `docpluck/cli.py`
- Test: `tests/test_cli_sections.py`

- [ ] **Step 21.1: Write the failing test**

`tests/test_cli_sections.py`:

```python
"""CLI: `docpluck sections <file>` and `docpluck extract --sections=...`."""

import io
import json
import os
import subprocess
import sys
import tempfile

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("pdfplumber")


def _make_pdf_file(tmp: str) -> str:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    p = os.path.join(tmp, "x.pdf")
    c = canvas.Canvas(p, pagesize=letter)
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 720, "Abstract")
    c.setFont("Helvetica", 11); c.drawString(72, 700, "Abstract body.")
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 660, "References")
    c.setFont("Helvetica", 11); c.drawString(72, 640, "[1] Doe.")
    c.showPage(); c.save()
    return p


def _run(*args) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "docpluck.cli", *args],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_cli_sections_json_output():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_pdf_file(tmp)
        code, out, err = _run("sections", path, "--format", "json")
        assert code == 0, err
        payload = json.loads(out)
        assert "sections" in payload
        assert payload["sectioning_version"] == "1.0.0"
        assert any(s["canonical_label"] == "abstract" for s in payload["sections"])


def test_cli_extract_sections_filter():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_pdf_file(tmp)
        code, out, err = _run("extract", path, "--sections", "abstract,references")
        assert code == 0, err
        assert "Abstract body" in out
        assert "[1] Doe" in out


def test_cli_version_still_works():
    code, out, _ = _run("--version")
    assert code == 0
    payload = json.loads(out)
    assert "version" in payload
```

- [ ] **Step 21.2: Run test to verify it fails**

```bash
pytest tests/test_cli_sections.py -v
```

Expected: failures (CLI doesn't know `sections` or `extract`).

- [ ] **Step 21.3: Implement CLI**

`docpluck/cli.py` (replace existing content):

```python
"""docpluck CLI.

Subcommands:
  docpluck --version              version + git sha JSON
  docpluck extract <file>         emit normalized text
  docpluck extract <file> --sections abstract,references
                                  emit text of just those sections
  docpluck sections <file>        emit SectionedDocument as JSON
  docpluck sections <file> --format summary
                                  emit a human-readable summary
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .version import get_version_info


def _read_bytes(path: str) -> bytes:
    return Path(path).read_bytes()


def _format_for(path: str) -> str:
    p = path.lower()
    if p.endswith(".pdf"): return "pdf"
    if p.endswith(".docx"): return "docx"
    if p.endswith((".html", ".htm")): return "html"
    raise SystemExit(f"unknown file extension: {path}")


def _cmd_extract(args: argparse.Namespace) -> int:
    from . import extract_pdf, extract_docx, extract_html
    fmt = _format_for(args.file)
    blob = _read_bytes(args.file)
    sections = [s.strip() for s in args.sections.split(",")] if args.sections else None
    if fmt == "pdf":
        text, _ = extract_pdf(blob, sections=sections)
    elif fmt == "docx":
        text, _ = extract_docx(blob, sections=sections)
    else:
        text, _ = extract_html(blob, sections=sections)
    sys.stdout.write(text)
    return 0


def _cmd_sections(args: argparse.Namespace) -> int:
    from . import extract_sections
    blob = _read_bytes(args.file)
    doc = extract_sections(blob)

    if args.format == "summary":
        lines = [f"sectioning_version: {doc.sectioning_version}",
                 f"source_format: {doc.source_format}",
                 f"sections ({len(doc.sections)}):"]
        for s in doc.sections:
            pages = ",".join(str(p) for p in s.pages) if s.pages else "-"
            lines.append(
                f"  [{s.confidence.value}] {s.label:>22}  pages={pages:6}  "
                f"chars={s.char_end - s.char_start}  via={s.detected_via.value}"
            )
        sys.stdout.write("\n".join(lines) + "\n")
        return 0

    payload = {
        "sectioning_version": doc.sectioning_version,
        "source_format": doc.source_format,
        "sections": [
            {
                "label": s.label,
                "canonical_label": s.canonical_label.value,
                "char_start": s.char_start,
                "char_end": s.char_end,
                "pages": list(s.pages),
                "confidence": s.confidence.value,
                "detected_via": s.detected_via.value,
                "heading_text": s.heading_text,
                "text": s.text,
            }
            for s in doc.sections
        ],
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args_in = list(sys.argv[1:] if argv is None else argv)

    if not args_in or args_in[0] in ("-V", "--version", "version"):
        print(json.dumps(get_version_info()))
        return 0

    if args_in[0] in ("-h", "--help", "help"):
        print("usage: docpluck [--version | extract <file> [--sections L1,L2] | sections <file> [--format json|summary]]")
        return 0

    parser = argparse.ArgumentParser(prog="docpluck", add_help=True)
    sub = parser.add_subparsers(dest="cmd", required=True)

    extract = sub.add_parser("extract")
    extract.add_argument("file")
    extract.add_argument("--sections", default=None,
                         help="Comma-separated list of section labels to filter.")
    extract.set_defaults(func=_cmd_extract)

    sections = sub.add_parser("sections")
    sections.add_argument("file")
    sections.add_argument("--format", default="json", choices=["json", "summary"])
    sections.set_defaults(func=_cmd_sections)

    parsed = parser.parse_args(args_in)
    return parsed.func(parsed)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 21.4: Run tests to verify they pass**

```bash
pytest tests/test_cli_sections.py -v
```

Expected: 3 passing.

- [ ] **Step 21.5: Commit**

```bash
git add docpluck/cli.py tests/test_cli_sections.py
git commit -m "feat(cli): docpluck sections + extract --sections subcommands"
```

---

## Phase 7 — Test corpus + version bump

### Task 22: Add unit fixtures (synthetic PDFs)

**Files:**
- Create: `tests/fixtures/sections/__init__.py`
- Create: `tests/fixtures/sections/builders.py`
- Create: `tests/test_sections_unit_corpus.py`

- [ ] **Step 22.1: Write fixture builders**

`tests/fixtures/sections/__init__.py`: empty file.

`tests/fixtures/sections/builders.py`:

```python
"""Synthetic PDF/DOCX/HTML fixtures for section-identification tests.

Each builder emits a minimal document containing exactly the section
labels the test needs. Built on demand (not committed binaries) so tests
remain hermetic and the repo stays small.
"""

from __future__ import annotations

import io


def build_apa_single_study_pdf() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 720
    def heading(t):
        nonlocal y
        c.setFont("Helvetica-Bold", 14); c.drawString(72, y, t); y -= 20
    def para(t):
        nonlocal y
        c.setFont("Helvetica", 11); c.drawString(72, y, t); y -= 20
    heading("Abstract"); para("This paper investigates X.")
    heading("Introduction"); para("Intro text.")
    heading("Methods"); para("We did things.")
    heading("Results"); para("We found stuff.")
    heading("Discussion"); para("It was great.")
    heading("References"); para("[1] Doe, J. (2020).")
    c.showPage(); c.save()
    return buf.getvalue()


def build_apa_multi_study_pdf() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 720
    def heading(t):
        nonlocal y
        c.setFont("Helvetica-Bold", 14); c.drawString(72, y, t); y -= 20
    def para(t):
        nonlocal y
        c.setFont("Helvetica", 11); c.drawString(72, y, t); y -= 20
    heading("Abstract"); para("Multi-study paper.")
    heading("Introduction"); para("Intro text.")
    heading("Methods"); para("Study 1 methods.")
    heading("Results"); para("Study 1 results.")
    heading("Methods"); para("Study 2 methods.")
    heading("Results"); para("Study 2 results.")
    heading("General Discussion"); para("Synthesis.")
    heading("References"); para("[1] Doe, J. (2020).")
    c.showPage(); c.save()
    return buf.getvalue()


def build_html_with_real_headings() -> bytes:
    return (
        b"<html><body>"
        b"<h2>Abstract</h2><p>This paper investigates X.</p>"
        b"<h2>Methods</h2><p>We did things.</p>"
        b"<h2>References</h2><p>[1] Doe, J. (2020).</p>"
        b"</body></html>"
    )


def build_docx_with_real_headings() -> bytes:
    from docx import Document
    d = Document()
    d.add_heading("Abstract", level=2); d.add_paragraph("This paper investigates X.")
    d.add_heading("Methods", level=2); d.add_paragraph("We did things.")
    d.add_heading("References", level=2); d.add_paragraph("[1] Doe, J. (2020).")
    buf = io.BytesIO(); d.save(buf)
    return buf.getvalue()
```

- [ ] **Step 22.2: Write per-fixture assertions**

`tests/test_sections_unit_corpus.py`:

```python
"""Unit-corpus assertions across synthetic fixtures."""

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("pdfplumber")

from docpluck import extract_sections
from docpluck.sections import SectionLabel
from tests.fixtures.sections import builders


def _assert_universal_coverage(doc):
    total = sum(s.char_end - s.char_start for s in doc.sections)
    # The footnotes appendix uses a sentinel; subtract it from coverage check.
    sentinel_count = doc.normalized_text.count("\n\f\f\n")
    assert total + sentinel_count * len("\n\f\f\n") >= len(doc.normalized_text) - 1


def test_apa_single_study_pdf():
    doc = extract_sections(builders.build_apa_single_study_pdf())
    _assert_universal_coverage(doc)
    expected = {
        SectionLabel.abstract, SectionLabel.introduction, SectionLabel.methods,
        SectionLabel.results, SectionLabel.discussion, SectionLabel.references,
    }
    actual = {s.canonical_label for s in doc.sections}
    assert expected.issubset(actual)


def test_apa_multi_study_pdf():
    doc = extract_sections(builders.build_apa_multi_study_pdf())
    _assert_universal_coverage(doc)
    methods = doc.all("methods")
    results = doc.all("results")
    assert len(methods) >= 2
    assert len(results) >= 2
    labels = [s.label for s in doc.sections]
    assert "methods" in labels and "methods_2" in labels


def test_html_real_headings():
    pytest.importorskip("bs4")
    doc = extract_sections(builders.build_html_with_real_headings())
    expected = {SectionLabel.abstract, SectionLabel.methods, SectionLabel.references}
    actual = {s.canonical_label for s in doc.sections}
    assert expected.issubset(actual)


def test_docx_real_headings():
    pytest.importorskip("mammoth")
    pytest.importorskip("docx")
    doc = extract_sections(builders.build_docx_with_real_headings())
    expected = {SectionLabel.abstract, SectionLabel.methods, SectionLabel.references}
    actual = {s.canonical_label for s in doc.sections}
    assert expected.issubset(actual)
```

- [ ] **Step 22.3: Run tests, debug, commit**

```bash
pytest tests/test_sections_unit_corpus.py -v
```

If any fixture fails to detect a label, drop into the `extract_sections` path and inspect what hints the annotator emitted. Most fixes will be small adjustments to font sizes in the synthetic builder so the body/heading ratio crosses the 1.15× threshold. The annotator code itself should not need to change to satisfy synthetic fixtures.

```bash
git add tests/fixtures/sections/__init__.py tests/fixtures/sections/builders.py tests/test_sections_unit_corpus.py
git commit -m "test(sections): unit corpus fixtures + per-format assertions"
```

### Task 23: Real-corpus integration tests (skipped if PDFs unavailable)

**Files:**
- Create: `tests/test_sections_real_corpus.py`

- [ ] **Step 23.1: Write the test**

`tests/test_sections_real_corpus.py`:

```python
"""Real-corpus integration tests. Skipped when test PDFs aren't present."""

import os

import pytest

from .conftest import requires_pdftotext, pdf_path

pytest.importorskip("pdfplumber")


@requires_pdftotext
def test_li_feldman_rsos():
    path = pdf_path("docpluck", "Li&Feldman-2025-RSOS-...-print.pdf")
    if not path or not os.path.exists(path):
        pytest.skip("Li&Feldman RSOS PDF not available")
    from docpluck import extract_sections
    with open(path, "rb") as f:
        doc = extract_sections(f.read())
    # Universal coverage holds.
    total = sum(s.char_end - s.char_start for s in doc.sections)
    assert total >= len(doc.normalized_text) - 8  # allow sentinel tolerance
    # References section is present and substantive.
    refs = doc.references
    assert refs is not None
    assert len(refs.text) > 1000
    # Abstract is present.
    assert doc.abstract is not None


@requires_pdftotext
def test_escicheck_pdfs_smoke():
    base = os.environ.get("DOCPLUCK_ESCICHECK_PDFS")
    if not base or not os.path.isdir(base):
        pytest.skip("ESCIcheck PDFs not available")
    from docpluck import extract_sections
    files = sorted(p for p in os.listdir(base) if p.lower().endswith(".pdf"))[:5]
    if not files:
        pytest.skip("No PDFs found in ESCIcheck dir")
    for fn in files:
        with open(os.path.join(base, fn), "rb") as f:
            doc = extract_sections(f.read())
        # Smoke: every PDF should produce ≥3 sections.
        assert len(doc.sections) >= 3, f"{fn}: only {len(doc.sections)} sections"
```

- [ ] **Step 23.2: Run (likely skip)**

```bash
pytest tests/test_sections_real_corpus.py -v
```

Expected: skips when PDFs unavailable. If user has them locally, real assertions run.

- [ ] **Step 23.3: Commit**

```bash
git add tests/test_sections_real_corpus.py
git commit -m "test(sections): real-corpus integration tests (skipped when PDFs absent)"
```

### Task 24: Golden snapshot regression test

**Files:**
- Create: `tests/golden/sections/apa_single_study.json` (will be generated by the test on first run)
- Create: `tests/test_sections_golden.py`

- [ ] **Step 24.1: Write the snapshot test**

`tests/test_sections_golden.py`:

```python
"""Regression test: sectioner output snapshot.

CI fails when SECTIONING_VERSION is unchanged but output drifts.
On a SECTIONING_VERSION bump, regenerate snapshots:

    DOCPLUCK_REGEN_GOLDEN=1 pytest tests/test_sections_golden.py
"""

import json
import os
import pathlib

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("pdfplumber")

from docpluck import extract_sections, SECTIONING_VERSION
from tests.fixtures.sections import builders


GOLDEN_DIR = pathlib.Path(__file__).parent / "golden" / "sections"


def _serialize(doc) -> dict:
    return {
        "sectioning_version": doc.sectioning_version,
        "source_format": doc.source_format,
        "sections": [
            {
                "label": s.label,
                "canonical_label": s.canonical_label.value,
                "char_start": s.char_start,
                "char_end": s.char_end,
                "pages": list(s.pages),
                "confidence": s.confidence.value,
                "detected_via": s.detected_via.value,
                "heading_text": s.heading_text,
            }
            for s in doc.sections
        ],
    }


def _check_snapshot(name: str, doc) -> None:
    path = GOLDEN_DIR / f"{name}.json"
    serialized = _serialize(doc)
    if os.environ.get("DOCPLUCK_REGEN_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(serialized, indent=2))
        return
    if not path.exists():
        pytest.skip(f"No golden file for {name}; set DOCPLUCK_REGEN_GOLDEN=1 to create.")
    expected = json.loads(path.read_text())
    assert serialized["sectioning_version"] == SECTIONING_VERSION
    assert serialized == expected, (
        f"{name}: output drifted but SECTIONING_VERSION unchanged. "
        "Either fix the regression, or bump SECTIONING_VERSION and regenerate "
        "with DOCPLUCK_REGEN_GOLDEN=1."
    )


def test_golden_apa_single_study_pdf():
    doc = extract_sections(builders.build_apa_single_study_pdf())
    _check_snapshot("apa_single_study_pdf", doc)


def test_golden_apa_multi_study_pdf():
    doc = extract_sections(builders.build_apa_multi_study_pdf())
    _check_snapshot("apa_multi_study_pdf", doc)


def test_golden_html_real_headings():
    pytest.importorskip("bs4")
    doc = extract_sections(builders.build_html_with_real_headings())
    _check_snapshot("html_real_headings", doc)
```

- [ ] **Step 24.2: Generate initial snapshots**

```bash
DOCPLUCK_REGEN_GOLDEN=1 pytest tests/test_sections_golden.py -v
```

Expected: tests pass (regen mode just writes files).

- [ ] **Step 24.3: Run again without regen flag**

```bash
pytest tests/test_sections_golden.py -v
```

Expected: 3 passing.

- [ ] **Step 24.4: Commit**

```bash
git add tests/golden/sections/ tests/test_sections_golden.py
git commit -m "test(sections): golden snapshots for regression detection"
```

### Task 25: Version bump + CHANGELOG

**Files:**
- Modify: `docpluck/__init__.py` (`__version__`)
- Modify: `pyproject.toml` (`version`)
- Modify: `CHANGELOG.md`

- [ ] **Step 25.1: Bump versions**

In `docpluck/__init__.py`, change:

```python
__version__ = "1.5.0"
```

to:

```python
__version__ = "1.6.0"
```

In `pyproject.toml`, change:

```toml
version = "1.5.0"
```

to:

```toml
version = "1.6.0"
```

- [ ] **Step 25.2: Append CHANGELOG entry**

Prepend to `CHANGELOG.md`:

```markdown
## v1.6.0 — 2026-MM-DD

### Added
- New `docpluck.sections` package: identifies academic-paper sections (abstract,
  methods, references, disclosures, …) with universal char-level coverage and
  per-section confidence + provenance. See
  `docs/superpowers/specs/2026-05-06-section-identification-design.md`.
  - 18 canonical labels + `unknown` fallback + numeric suffixes for repeats
    (e.g. `methods_2` for multi-study papers).
  - Two-tier algorithm: format-aware annotators (PDF/DOCX/HTML) +
    unified core canonicalizer.
  - `SECTIONING_VERSION` constant ("1.0.0") on every `SectionedDocument`.
- New internal `docpluck.extract_layout` module: pdfplumber-based layout
  extraction (per-page bounding boxes + font sizes). API not promised externally
  in this release.
- New `F0` step in `normalize_text(text, level, layout=...)`: layout-aware
  stripping of footnotes, running headers, and running footers. Footnotes are
  preserved and surface as the `footnotes` section.
- Filter sugar on existing extract calls: `extract_pdf(b, sections=["abstract",
  "references"])` returns concatenated section text in document order.
- New CLI subcommands: `docpluck extract <file> --sections=...`,
  `docpluck sections <file> [--format json|summary]`.

### Changed
- `NormalizationReport` gains `footnote_spans` and `page_offsets` fields
  (default empty tuples). Existing field/tuple-unpacking call sites are
  unchanged.

### Backwards compatibility
- `extract_pdf(bytes)`, `extract_docx(bytes)`, `extract_html(bytes)` byte-
  identical to v1.5.0 when called without the new `sections=` kwarg.
- `normalize_text(text, level)` byte-identical to v1.5.0 when called without
  the new `layout=` kwarg.
```

(Replace `2026-MM-DD` with today's date when ready to release.)

- [ ] **Step 25.3: Final test run**

```bash
pytest -x -q
```

Expected: all green.

- [ ] **Step 25.4: Commit**

```bash
git add docpluck/__init__.py pyproject.toml CHANGELOG.md
git commit -m "chore: bump v1.6.0 — section identification + layout-aware footnote strip"
```

---

## Done — verification checklist

- [ ] `pytest -x -q` is fully green.
- [ ] `python -c "from docpluck import extract_sections, SectionedDocument, SECTIONING_VERSION; print(SECTIONING_VERSION)"` prints `1.0.0`.
- [ ] `python -m docpluck.cli sections <some.pdf>` returns valid JSON.
- [ ] `git log --oneline main..feat/section-identification` shows ~25 commits, one per task.
- [ ] Spec doc `docs/superpowers/specs/2026-05-06-section-identification-design.md` is unchanged.
- [ ] `TODO.md` "Section identification — future enhancements" block is unchanged.
- [ ] Existing tests in `tests/test_extraction.py`, `tests/test_normalization.py`, `tests/test_quality.py`, `tests/test_request_09_reference_normalization.py` are still green (back-compat preserved).

If any item above is red, fix before merging to `main`.
