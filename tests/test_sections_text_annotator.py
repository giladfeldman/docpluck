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
