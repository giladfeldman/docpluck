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
            # v1.6.1: only strong-layout or markup hints become subheadings.
            # Weak text_pattern hints (pass-3 line-isolated headings) are excluded:
            # they cannot be reliably distinguished from table-cell list items whose
            # normalized representation is also blank-line-separated single lines.
            # Smart list-vs-heading discrimination is deferred to v1.6.2+.
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

    # v1.6.1: fold adjacent markers with the same canonical_label when the
    # gap between them is small (< 100 chars). This handles the common
    # "Introduction\nBackground\n..." pattern where both map to introduction.
    # Keeps multi-study behavior intact: methods_2 of study 2 is far apart
    # from methods of study 1, so they remain separate.
    coalesced_markers: list[_Marker] = []
    for m in markers:
        if (
            coalesced_markers
            and coalesced_markers[-1].label == m.label
            and m.char_start - coalesced_markers[-1].char_start < 100
        ):
            # Drop this marker; the prior one already opens this section.
            continue
        coalesced_markers.append(m)
    markers = coalesced_markers

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
    #
    # v1.6.1: with strict canonical-only markers + clean normalized text, the
    # boundary-aware truncation pass is no longer needed and is destructive on
    # real APA papers (e.g., 'Corresponding Author:' inside Introduction would
    # truncate intro at that line). Disabled by listing all canonical labels.
    _NO_TRUNCATE = set(SectionLabel)
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

    # 2026-05-07 (Pattern E): two synthesis passes for papers with missing
    # canonical front-matter / body headings.  Many academic papers in real
    # corpora have implicit headings the regex detector cannot see:
    #   (1) Meta-Psychology / Collabra papers go straight from author block
    #       to abstract paragraph with NO "Abstract" heading at all — the
    #       leading `unknown` span absorbs the whole title block + abstract.
    #   (2) JESP / chen-style papers have an `Abstract` heading but no
    #       `Introduction` heading; sections 1–5 are intro-equivalent
    #       numbered chunks and the body starts at "6.2. Method".  The
    #       abstract section bloats to 20–30 % of doc.
    # We patch (1) first (synthesizes a missing `abstract`), then re-run (2)
    # so a freshly synthesized abstract can be split if it now bloats.
    final = _synthesize_abstract_from_leading_unknown(final, page_offsets)
    final = _synthesize_introduction_if_bloated_front_matter(final, page_offsets)
    return tuple(final)


def _synthesize_abstract_from_leading_unknown(
    sections: list[Section],
    page_offsets: tuple[int, ...],
) -> list[Section]:
    """Synthesize an `abstract` section out of the leading `unknown` span when
    no abstract heading was detected.

    Triggers when ALL of the following hold:
      - First section is `unknown` AND ≥1500 chars long.
      - There is NO existing `abstract` section anywhere.
      - There is at least one canonical body section (methods/results/
        discussion/literature_review/general_discussion) downstream — i.e.
        we're confident this is a paper, not just a fragment.
      - The leading `unknown` body contains a "long prose paragraph" — a
        ≥600-char chunk with no internal `\\n\\n` paragraph break.  That
        paragraph is the implicit abstract; everything before it is the
        title block / author affiliations.

    The split point is the start of the long prose paragraph.  No-op when
    any condition fails — the goal is to avoid synthesizing wrong abstracts
    on edge-case layouts (very short papers, commentaries, etc.).
    """
    if not sections:
        return sections
    if any(s.canonical_label == SectionLabel.abstract for s in sections):
        return sections
    body_labels = {
        SectionLabel.methods, SectionLabel.results, SectionLabel.discussion,
        SectionLabel.general_discussion, SectionLabel.literature_review,
        SectionLabel.conclusion,
    }
    if not any(s.canonical_label in body_labels for s in sections):
        return sections
    head = sections[0]
    if head.canonical_label != SectionLabel.unknown:
        return sections
    if len(head.text) < 1500:
        return sections
    # Find the first long prose paragraph (≥600 chars, no internal \n\n).
    paragraphs = []
    pos = 0
    body = head.text
    while pos < len(body):
        nxt = body.find("\n\n", pos)
        end = nxt if nxt >= 0 else len(body)
        paragraphs.append((pos, end))
        pos = end + 2 if nxt >= 0 else len(body)
    # The abstract is structurally one of the EARLY paragraphs in the
    # leading unknown — typically the first 1–2 paragraphs ≥ 600 chars.
    # Walk paragraphs in order; consider only those ≥ 600 chars; if the
    # first one contains citation-block tokens (DOI / @-email / explicit
    # "Department" affiliation), skip it and pick the next ≥ 600-char
    # paragraph as the abstract.  Limit consideration to the first 10
    # ≥600-char paragraphs to avoid picking body content in long
    # unknowns.
    #
    # Handles:
    #   - Aiyer/Collabra: para[citation, ~900, has doi.org/] → para[abstract, ~1700] → pick abstract
    #   - Nature/AOM/maier: first big paragraph IS the abstract → pick it
    #   - nat_comms (no abstract heading): first big para is authors+affiliations (1083 chars,
    #     has "Department"), next is abstract (957 chars) → skip first, pick second
    abstract_start_local = None
    cit_tokens = ("doi.org/", "@", "Department")
    sized = []
    for p_start, p_end in paragraphs:
        plen = p_end - p_start
        if plen >= 600:
            sized.append((p_start, plen))
            if len(sized) >= 10:
                break
    if sized:
        first_start, first_len = sized[0]
        first_text = body[first_start:first_start + first_len]
        first_is_citation = any(tok in first_text for tok in cit_tokens) and first_len < 1500
        if first_is_citation and len(sized) >= 2:
            abstract_start_local = sized[1][0]
        else:
            abstract_start_local = first_start
    if abstract_start_local is None:
        return sections
    if abstract_start_local == 0:
        # The whole leading unknown is one big paragraph (e.g. AOM Academy
        # of Management layout with title + authors + abstract glued without
        # blank lines, OR Social Forces with single-newline-only spacing).
        # Fall back to per-line scanning: walk the lines and find the FIRST
        # line ≥ 800 chars (a real prose abstract paragraph; affiliation
        # lines max out around 400-500 chars).  Title / author lines are
        # always < 200 chars.
        offset = 0
        line_split = None
        for line in body.splitlines(keepends=True):
            if len(line.strip()) >= 800:
                line_split = offset
                break
            offset += len(line)
        if line_split is None or line_split == 0:
            return sections
        abstract_start_local = line_split
    cut_global = head.char_start + abstract_start_local
    new_unknown = Section(
        label="unknown",
        canonical_label=SectionLabel.unknown,
        text=body[:abstract_start_local],
        char_start=head.char_start,
        char_end=cut_global,
        pages=_pages_for(head.char_start, cut_global, page_offsets),
        confidence=head.confidence,
        detected_via=head.detected_via,
        heading_text=head.heading_text,
    )
    new_abstract = Section(
        label="abstract",
        canonical_label=SectionLabel.abstract,
        text=body[abstract_start_local:],
        char_start=cut_global,
        char_end=head.char_end,
        pages=_pages_for(cut_global, head.char_end, page_offsets),
        confidence=Confidence.low,
        detected_via=DetectedVia.position_inferred,
        heading_text=None,
    )
    return [new_unknown, new_abstract] + sections[1:]


def _synthesize_introduction_if_bloated_front_matter(
    sections: list[Section],
    page_offsets: tuple[int, ...],
) -> list[Section]:
    """If the section immediately before the first canonical body section
    (methods/results/etc.) is bloated (>5000 chars AND >5% of doc) AND it
    is a front-matter section (abstract OR keywords) AND there is no
    `introduction` section anywhere, split that section at the first
    paragraph-break ≥800 chars past its start, and tag the trailing span
    as `introduction`.

    Handles two real layouts:
      - chen / jdm_m.2022.3: bloated `abstract` (no Introduction heading,
        body has numbered subsections 1./2./...).
      - chandrashekar / xiao: bloated `keywords` (Keywords appears before
        Introduction prose, no Introduction heading separates them).
    """
    if any(s.canonical_label == SectionLabel.introduction for s in sections):
        return sections
    body_labels = {
        SectionLabel.methods, SectionLabel.results, SectionLabel.discussion,
        SectionLabel.general_discussion, SectionLabel.literature_review,
        SectionLabel.conclusion,
    }
    first_body_idx = next(
        (i for i, s in enumerate(sections) if s.canonical_label in body_labels),
        None,
    )
    # Original case: bloat sits between front-matter and the first body section.
    # Extended case (bjps_1 / political science theory papers): keywords or
    # abstract absorbs the ENTIRE body of the paper and no canonical body
    # heading appears, only back-matter (references / acknowledgments / etc.).
    # Find the bloated front-matter candidate either way.
    if first_body_idx is None or first_body_idx == 0:
        # No body section detected — look for a bloated keywords/abstract
        # somewhere before any back-matter section (references / acks /
        # conflict_of_interest / data_availability / funding / supplementary).
        back_matter_labels = {
            SectionLabel.references, SectionLabel.acknowledgments,
            SectionLabel.funding, SectionLabel.conflict_of_interest,
            SectionLabel.data_availability, SectionLabel.author_contributions,
            SectionLabel.supplementary, SectionLabel.appendix,
        }
        # Find the first back-matter section (or end of doc).
        first_back_idx = next(
            (i for i, s in enumerate(sections)
             if s.canonical_label in back_matter_labels),
            len(sections),
        )
        if first_back_idx == 0:
            return sections
        # Cand is the bloated front-matter section in [0, first_back_idx).
        cand_idx = first_back_idx - 1
    else:
        cand_idx = first_body_idx - 1
    cand = sections[cand_idx]
    if cand.canonical_label not in (SectionLabel.abstract, SectionLabel.keywords):
        return sections
    cand_len = cand.char_end - cand.char_start
    # Lowered to 3000 (was 5000) on 2026-05-08 to catch Nature articles whose
    # synthesized abstract span absorbs ~3000-5000 chars of intro paragraphs
    # (no `Introduction` heading in Nature Comms / Sci Rep layouts).
    if cand_len < 3000:
        return sections
    total = sections[-1].char_end if sections else 0
    if total > 0 and cand_len / total < 0.05:
        return sections
    # Find the first paragraph break ≥800 chars in.  The first line is the
    # heading line and stays with the front-matter section.
    body = cand.text
    cut_local = body.find("\n\n", 800)
    if cut_local < 0:
        cut_local = body.find("\n", 1200)
        if cut_local < 0:
            return sections
        cut_local += 1
    else:
        cut_local += 2
    cut_global = cand.char_start + cut_local
    new_cand = Section(
        label=cand.label,
        canonical_label=cand.canonical_label,
        text=body[:cut_local],
        char_start=cand.char_start,
        char_end=cut_global,
        pages=_pages_for(cand.char_start, cut_global, page_offsets),
        confidence=cand.confidence,
        detected_via=cand.detected_via,
        heading_text=cand.heading_text,
        subheadings=cand.subheadings,
    )
    new_intro = Section(
        label="introduction",
        canonical_label=SectionLabel.introduction,
        text=body[cut_local:],
        char_start=cut_global,
        char_end=cand.char_end,
        pages=_pages_for(cut_global, cand.char_end, page_offsets),
        confidence=Confidence.low,
        detected_via=DetectedVia.position_inferred,
        heading_text=None,
    )
    return sections[:cand_idx] + [new_cand, new_intro] + sections[cand_idx + 1:]


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
