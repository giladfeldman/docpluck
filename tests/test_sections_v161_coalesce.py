"""v1.6.1: adjacent same-canonical-label markers coalesce when gap is small."""

from docpluck.sections.blocks import BlockHint
from docpluck.sections.core import partition_into_sections


def test_adjacent_same_canonical_markers_coalesce():
    """`Introduction\\nBackground\\n...` should produce ONE introduction
    section, not 'introduction' + 'introduction_2'."""
    text = (
        "Some title block.\n\n"
        "Introduction\n"
        "Background\n"
        "A growing body of literature has documented...\n"
        "More body text here.\n"
        "\nMethod\nbody of methods.\n"
    )
    intro_pos = text.find("Introduction")
    bg_pos = text.find("Background")
    method_pos = text.find("Method\n")
    hints = [
        BlockHint(text="Introduction", char_start=intro_pos, char_end=intro_pos + 12,
                  page=None, is_heading_candidate=True,
                  heading_strength="strong", heading_source="text_pattern"),
        BlockHint(text="Background", char_start=bg_pos, char_end=bg_pos + 10,
                  page=None, is_heading_candidate=True,
                  heading_strength="strong", heading_source="text_pattern"),
        BlockHint(text="Method", char_start=method_pos, char_end=method_pos + 6,
                  page=None, is_heading_candidate=True,
                  heading_strength="strong", heading_source="text_pattern"),
    ]
    sections = partition_into_sections(text, hints, source_format="pdf")
    intro_sections = [s for s in sections if s.canonical_label.value == "introduction"]
    assert len(intro_sections) == 1, f"got {[s.label for s in sections]}"
    # The single intro span should cover from Introduction to start of Method.
    assert intro_sections[0].char_start == intro_pos
    assert intro_sections[0].char_end == method_pos


def test_distant_same_canonical_markers_remain_separate():
    """Multi-study paper: methods + methods_2 stay separate when far apart."""
    body_padding = "x" * 5000
    text = f"Method\n{body_padding}\nResults\n{body_padding}\nMethod\nstudy 2 methods.\n"
    methods_1 = 0
    results_pos = text.find("Results")
    methods_2_pos = text.rfind("Method\n")
    hints = [
        BlockHint(text="Method", char_start=methods_1, char_end=6,
                  page=None, is_heading_candidate=True,
                  heading_strength="strong", heading_source="text_pattern"),
        BlockHint(text="Results", char_start=results_pos, char_end=results_pos + 7,
                  page=None, is_heading_candidate=True,
                  heading_strength="strong", heading_source="text_pattern"),
        BlockHint(text="Method", char_start=methods_2_pos, char_end=methods_2_pos + 6,
                  page=None, is_heading_candidate=True,
                  heading_strength="strong", heading_source="text_pattern"),
    ]
    sections = partition_into_sections(text, hints, source_format="pdf")
    methods_sections = [s for s in sections if s.canonical_label.value == "methods"]
    assert len(methods_sections) == 2, f"got {[s.label for s in sections]}"
