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
    # v1.6.1: strong-but-unrecognized heading no longer creates a new partition
    # boundary. The whole document is a single unknown span.
    assert len(sections) == 1
    assert sections[0].canonical_label == SectionLabel.unknown
    assert sections[0].char_start == 0


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


def test_resolve_label_strong_layout_unrecognized_returns_none():
    """v1.6.1: strong-layout heading with unrecognized text no longer
    creates an unknown marker. It returns None and goes to subheadings."""
    from docpluck.sections.core import _resolve_label
    from docpluck.sections.blocks import BlockHint

    hint = BlockHint(
        text="Power Analysis and Sensitivity Test",
        char_start=100,
        char_end=135,
        page=1,
        is_heading_candidate=True,
        heading_strength="strong",
        heading_source="layout",
    )
    assert _resolve_label(hint) is None


def test_resolve_label_canonical_strong_layout_returns_high_marker():
    from docpluck.sections.core import _resolve_label
    from docpluck.sections.blocks import BlockHint
    from docpluck.sections.taxonomy import SectionLabel, Confidence

    hint = BlockHint(
        text="Methods",
        char_start=0,
        char_end=7,
        page=1,
        is_heading_candidate=True,
        heading_strength="strong",
        heading_source="layout",
    )
    label, conf, _via = _resolve_label(hint)
    assert label == SectionLabel.methods
    assert conf == Confidence.high


def test_resolve_label_canonical_weak_layout_returns_medium_marker():
    from docpluck.sections.core import _resolve_label
    from docpluck.sections.blocks import BlockHint
    from docpluck.sections.taxonomy import SectionLabel, Confidence

    hint = BlockHint(
        text="Methods",
        char_start=0,
        char_end=7,
        page=1,
        is_heading_candidate=True,
        heading_strength="weak",
        heading_source="text_pattern",
    )
    label, conf, _via = _resolve_label(hint)
    assert label == SectionLabel.methods
    assert conf == Confidence.medium
