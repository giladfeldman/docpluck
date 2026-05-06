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
    assert SECTIONING_VERSION == "1.6.1"
    assert Section is not None
    assert SectionedDocument is not None
    assert SectionLabel.abstract.value == "abstract"
    assert Confidence.high.value == "high"
    assert DetectedVia.markup.value == "markup"
