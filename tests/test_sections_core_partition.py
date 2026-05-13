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


def test_synthesize_intro_keywords_cut_at_first_paragraph_break():
    """v2.4.15 regression target: when KEYWORDS is the bloated front-matter
    span (no `Introduction` heading detected), the synthesized split must
    land right after the keyword line — NOT 800 chars in. The 800-char
    rule (correct for ABSTRACT, which is typically a single 1500–3000-char
    paragraph) overshoots a short keyword line (~50–200 chars) and pulls
    intro paragraphs into the keywords span.

    Real-world regression: xiao_2021_crsp had the synthesized Introduction
    starting on next-column metadata (``Supplemental data...`` /
    ``Department of Psychology, University of``) because the cut absorbed
    two intro paragraphs into KEYWORDS.
    """
    # Layout: ABSTRACT + KEYWORDS (short keyword line) + 2 intro paragraphs +
    # Results heading. No `Introduction` heading anywhere.
    abstract_body = "X" * 1500  # one block, not crucial for the split
    keyword_line = "decoy effect; decision reversibility; regret"
    # Intro paragraphs sized so the KEYWORDS-to-next-marker span is large
    # enough to trigger the synthesis gate (cand_len ≥ 3000 AND ≥ 5% of doc).
    intro_p1 = (
        "Human choice behaviors are susceptible to manipulations of choice "
        "settings. " * 30
    )
    intro_p2 = (
        "The decoy effect emerges when two competing options are joined "
        "by a third option that is dominated by one. " * 30
    )
    text = (
        "Pre.\n\n"
        f"ABSTRACT\n{abstract_body}\n\n"
        f"KEYWORDS {keyword_line}\n\n"
        f"{intro_p1}\n\n"
        f"{intro_p2}\n\n"
        "Results\n\nresults body."
    )
    abs_idx = text.index("ABSTRACT")
    kw_idx = text.index("KEYWORDS")
    res_idx = text.index("Results")
    hints = [
        _hint("ABSTRACT", abs_idx, abs_idx + 8),
        _hint("KEYWORDS", kw_idx, kw_idx + 8),
        _hint("Results", res_idx, res_idx + 7),
    ]
    sections = partition_into_sections(text, hints, source_format="pdf")
    by_label = {s.canonical_label.value: s for s in sections
                if hasattr(s.canonical_label, "value")}
    assert "keywords" in by_label
    assert "introduction" in by_label, (
        "Synthesis should split the bloated KEYWORDS span into "
        "keywords + introduction when no Introduction heading exists."
    )
    kw = by_label["keywords"]
    intro = by_label["introduction"]
    # The keywords span should be SHORT (just the keyword line + heading),
    # not contain any intro-paragraph prose.
    assert len(kw.text) < 300, (
        f"keywords span should be tight, got {len(kw.text)} chars: "
        f"{kw.text[:200]!r}"
    )
    assert "Human choice behaviors" not in kw.text
    assert "decoy effect emerges" not in kw.text
    # The synthesized introduction should START with the first intro
    # paragraph — not mid-paragraph 800 chars deep.
    assert intro.text.lstrip().startswith("Human choice behaviors"), (
        f"introduction should begin at first intro paragraph, got: "
        f"{intro.text[:200]!r}"
    )


def test_synthesize_intro_abstract_still_uses_800_char_minimum():
    """The KEYWORDS-specific cut shortcut must NOT apply to abstract: a
    bloated ABSTRACT (no Introduction heading, no separate KEYWORDS) has
    a long single paragraph (the abstract proper) and the cut should
    still happen 800+ chars in, after that paragraph, so the abstract
    span stays intact.
    """
    # ABSTRACT body is a single ~1500-char paragraph; intro starts after a
    # paragraph break. No KEYWORDS section.
    abstract_para = (
        "The decoy effect refers to a robust violation of regularity in "
        "choice behavior. " * 30
    )
    intro_p1 = "We report two replication studies of the decoy effect. " * 8
    text = (
        "Pre.\n\n"
        f"Abstract\n{abstract_para}\n\n"
        f"{intro_p1}\n\n"
        "Results\n\nresults body."
    )
    abs_idx = text.index("Abstract")
    res_idx = text.index("Results")
    sections = partition_into_sections(
        text,
        [_hint("Abstract", abs_idx, abs_idx + 8),
         _hint("Results", res_idx, res_idx + 7)],
        source_format="pdf",
    )
    by_label = {s.canonical_label.value: s for s in sections
                if hasattr(s.canonical_label, "value")}
    assert "abstract" in by_label
    # The abstract should retain its long paragraph.
    abstract = by_label["abstract"]
    assert "decoy effect refers to" in abstract.text
    # If introduction got synthesized, it should NOT start mid-abstract-
    # paragraph.
    if "introduction" in by_label:
        intro = by_label["introduction"]
        assert not intro.text.lstrip().startswith("The decoy"), (
            "ABSTRACT cut should not overshoot into the abstract paragraph"
        )
