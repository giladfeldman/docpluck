"""Subheadings attachment — v1.6.1.

Layout-strong heading hints with unrecognized text are attached to the
containing section's `subheadings` field rather than creating new spans.
"""

from docpluck.sections.blocks import BlockHint
from docpluck.sections.core import partition_into_sections


def _hint(text, start, end, *, strong=True, source="layout"):
    return BlockHint(
        text=text,
        char_start=start,
        char_end=end,
        page=1,
        is_heading_candidate=True,
        heading_strength="strong" if strong else "weak",
        heading_source=source,
    )


def test_unrecognized_strong_hint_inside_methods_attaches_as_subheading():
    text = (
        "Method\nbody of methods.\n"
        "Participants\nWe recruited 200 students.\n"
        "Results\nbody of results.\n"
    )
    methods_start = 0
    participants_start = text.find("Participants")
    results_start = text.find("Results")

    hints = [
        _hint("Method", methods_start, methods_start + len("Method")),
        _hint("Participants", participants_start, participants_start + len("Participants")),
        _hint("Results", results_start, results_start + len("Results")),
    ]
    sections = partition_into_sections(text, hints, source_format="pdf")
    methods = next(s for s in sections if s.label == "methods")
    assert "Participants" in methods.subheadings


def test_multiple_subheadings_in_document_order():
    # "Procedure" resolves to SectionLabel.methods in the taxonomy, so we use
    # "Materials" (confirmed unrecognized) to test three distinct subheadings.
    text = (
        "Method\nintro to methods.\n"
        "Participants\np\n"
        "Materials\nq\n"
        "Power Analysis\nr\n"
        "Results\nresults body.\n"
    )
    starts = {
        "Method": text.find("Method\n"),
        "Participants": text.find("Participants"),
        "Materials": text.find("Materials"),
        "Power Analysis": text.find("Power Analysis"),
        "Results": text.find("Results\n"),
    }
    hints = [
        _hint(name, s, s + len(name)) for name, s in starts.items()
    ]
    sections = partition_into_sections(text, hints, source_format="pdf")
    methods = next(s for s in sections if s.label == "methods")
    assert methods.subheadings == ("Participants", "Materials", "Power Analysis")


def test_unrecognized_hint_outside_any_section_is_dropped():
    """Hints in the title-block prefix are not promoted to subheadings of unknown."""
    text = (
        "Some title block content with a Foo line.\n"
        "Foo\n"
        "Method\nmethods body.\n"
    )
    foo_start = text.find("Foo\n")
    method_start = text.find("Method\n")
    hints = [
        _hint("Foo", foo_start, foo_start + 3),
        _hint("Method", method_start, method_start + 6),
    ]
    sections = partition_into_sections(text, hints, source_format="pdf")
    # Prefix unknown span exists, but its subheadings stays empty (we don't
    # promote orphan hints into the unknown prefix).
    prefix = sections[0]
    assert prefix.canonical_label.value == "unknown"
    assert prefix.subheadings == ()
