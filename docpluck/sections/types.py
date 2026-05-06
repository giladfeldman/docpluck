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
    subheadings: tuple[str, ...] = ()   # in-section unrecognized headings (v1.6.1)


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
