"""Tier-2 unified canonicalizer + universal-coverage partitioner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .blocks import BlockHint
from .boundaries import is_section_boundary
from .taxonomy import (
    SectionLabel, Confidence, DetectedVia, lookup_canonical_label
)
from .types import Section, SectionedDocument


@dataclass
class _Marker:
    char_start: int
    label: SectionLabel
    confidence: Confidence
    detected_via: DetectedVia
    heading_text: str | None
    label_suffix_index: int | None  # for repeats: 1 (base), 2, 3, ...


def _resolve_label(hint: BlockHint) -> tuple[SectionLabel, Confidence, DetectedVia] | None:
    """v1.6.1: Only canonical-taxonomy heading matches create section markers.

    Strong-layout-but-unrecognized text is no longer promoted to an `unknown`
    span. Such hints are recorded by the caller for the post-partition
    `subheadings` collection pass.
    """
    canonical = lookup_canonical_label(hint.text)
    if canonical is None:
        return None
    if hint.heading_strength == "strong" or hint.heading_source == "markup":
        return canonical, Confidence.high, _via_for(hint)
    return canonical, Confidence.medium, _via_for(hint)


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
      2. Sort markers by char_start. Deduplicate markers at same offset.
      3. Assign numeric suffixes to repeated canonical labels in document
         order (so suffix is on the marker before sections are built).
      4. Build sections: each marker starts a span ending at the next
         marker's char_start (or end-of-text). If first marker is not at
         offset 0, prepend an `unknown` span covering [0, first_marker).
      5. Coalesce ADJACENT spans with the same canonical label (skipped for
         `unknown` to preserve heading-derived span boundaries).
      6. Boundary-aware truncation: scan each labeled span line-by-line
         (skipping the heading line) and split at the first boundary line.
    """
    markers: list[_Marker] = []
    unrecognized: list[BlockHint] = []
    for hint in hints:
        resolved = _resolve_label(hint)
        if resolved is None:
            # Only collect strong/markup hints as candidate subheadings —
            # weak hints are likely paragraph noise.
            if hint.heading_strength == "strong" or hint.heading_source == "markup":
                unrecognized.append(hint)
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

    # Coalesce adjacent same-label spans (rare; skip unknown to preserve boundaries).
    coalesced: list[Section] = []
    for s in sections:
        if coalesced and coalesced[-1].label == s.label \
                and coalesced[-1].label != "unknown" \
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

    # Boundary-aware truncation (spec §5.4): for each labeled span, scan its
    # text line-by-line for a boundary pattern. Skip the first line of the
    # span (the heading line) before scanning. If a boundary fires on any
    # subsequent line, truncate the span at that line and emit a trailing
    # `unknown` span covering the rest. Universal coverage is preserved.
    _NO_TRUNCATE = {
        SectionLabel.unknown,
        SectionLabel.references,
        SectionLabel.appendix,
        SectionLabel.supplementary,
    }
    truncated: list[Section] = []
    for s in coalesced:
        if s.canonical_label in _NO_TRUNCATE:
            truncated.append(s)
            continue
        offset = s.char_start
        cut_at: int | None = None
        for i, line in enumerate(s.text.splitlines(keepends=True)):
            line_start = offset
            offset += len(line)
            # Skip the first line (it contains the heading itself).
            if i == 0:
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

    # v1.6.1: attach unrecognized hints to the section that contains them.
    final: list[Section] = []
    for s in truncated:
        if not unrecognized:
            final.append(s)
            continue
        contained = tuple(
            h.text for h in unrecognized
            if s.char_start <= h.char_start < s.char_end
            and s.canonical_label != SectionLabel.unknown
        )
        if not contained:
            final.append(s)
            continue
        final.append(Section(
            label=s.label,
            canonical_label=s.canonical_label,
            text=s.text,
            char_start=s.char_start,
            char_end=s.char_end,
            pages=s.pages,
            confidence=s.confidence,
            detected_via=s.detected_via,
            heading_text=s.heading_text,
            subheadings=contained,
        ))
    return tuple(final)


def append_footnotes_section(
    sections: tuple[Section, ...],
    normalized_text: str,
    footnote_raw_spans: tuple[tuple[int, int], ...],
) -> tuple[Section, ...]:
    """If F0 produced a footnote appendix in `normalized_text` (sentinel
    ``\\n\\f\\f\\n``), wrap it as a single `footnotes` Section."""
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

    # Truncate any existing section that overlaps the appendix so it doesn't
    # include the sentinel or the footnote content.
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


def extract_sections_from_text(
    text: str,
    *,
    source_format: Literal["pdf", "docx", "html"],
    page_offsets: tuple[int, ...] = (),
) -> SectionedDocument:
    """Build a SectionedDocument from already-normalized text using the
    text-only annotator. Used as fallback when no layout/markup is available."""
    from .annotators.text import annotate_text
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
