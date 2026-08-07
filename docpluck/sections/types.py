"""Section and SectionedDocument — public data model."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from typing import Literal

from .taxonomy import SectionLabel, Confidence, DetectedVia


@dataclass(frozen=True)
class Section:
    label: str                          # "methods", "methods_2", "study_1_header"
    canonical_label: SectionLabel       # base label without numeric suffix
    text: str
    char_start: int                     # offset into normalized_text
    char_end: int
    # 1-indexed page numbers. **Currently ALWAYS `()` — for every format.**
    # Page mapping needs `NormalizationReport.page_offsets`, which only
    # `normalize_text(layout=...)` fills, and `extract_sections` deliberately
    # does not pass `layout=` (v1.6.1 took the layout channel out of the
    # sections path — LESSONS L-001). The DOCX/HTML branches never supply
    # offsets either. Verified 2026-08-07 on a 3-page PDF: every section came
    # back with `pages=()`.
    #
    # Stated here rather than left to be discovered because the field reads as
    # a working feature — the CLI and the service both emit `"pages": []` for
    # every section, which is indistinguishable from "this section spans no
    # pages". Wiring it up is a corpus-wide behaviour change (it would run F0),
    # so it is queued in todo.md rather than done here.
    pages: tuple[int, ...]
    confidence: Confidence
    detected_via: DetectedVia
    heading_text: str | None            # literal heading found, if any
    subheadings: tuple[str, ...] = ()   # in-section unrecognized headings (v1.6.1)

    def to_dict(self) -> dict:
        """JSON-ready view of the section — **every** field, no exceptions.

        Derived from ``fields()`` rather than a hand-written key list because
        the hand-written version is how ``subheadings`` went missing. v1.6.1
        added the field, the detector populated it, tests covered it — and
        both consumer surfaces (``docpluck sections --format json`` and the
        service's ``/sections`` endpoint) had independently enumerated the
        nine keys that existed before it, so the feature was invisible to
        every consumer while looking complete. Adding a field here now reaches
        callers automatically. (v2.4.126.)

        Enums are emitted as their ``.value`` and tuples as lists, matching
        what a JSON round-trip produces and what both surfaces already sent.
        """
        out = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, Enum):
                value = value.value
            elif isinstance(value, tuple):
                value = list(value)
            out[f.name] = value
        return out


@dataclass(frozen=True)
class SectionedDocument:
    sections: tuple[Section, ...]
    normalized_text: str
    sectioning_version: str
    source_format: Literal["pdf", "docx", "html"]

    #: The one field :meth:`to_dict` deliberately does not emit, and why.
    #: ``normalized_text`` is the whole document — megabytes on a long paper —
    #: and both existing consumer surfaces already chose to send a length
    #: instead. Naming the omission here makes it a decision rather than the
    #: kind of accident that lost ``Section.subheadings``; ``to_dict`` emits
    #: ``normalized_text_length`` in its place so nothing is silently absent.
    _TO_DICT_OMITS = ("normalized_text",)

    def to_dict(self) -> dict:
        """JSON-ready view of the document and its sections.

        Every field except :data:`_TO_DICT_OMITS`, derived from ``fields()``
        so a field added later cannot go missing. Sections are serialized by
        :meth:`Section.to_dict`.
        """
        out = {}
        for f in fields(self):
            if f.name in self._TO_DICT_OMITS:
                continue
            value = getattr(self, f.name)
            if f.name == "sections":
                value = [s.to_dict() for s in value]
            elif isinstance(value, tuple):
                value = list(value)
            out[f.name] = value
        out["normalized_text_length"] = len(self.normalized_text)
        return out

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
