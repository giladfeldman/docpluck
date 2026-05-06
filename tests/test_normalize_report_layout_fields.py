"""NormalizationReport gains footnote_spans + page_offsets (default empty)."""

from docpluck import normalize_text, NormalizationLevel


def test_existing_unpacking_still_works():
    text = "Some plain text."
    out, report = normalize_text(text, NormalizationLevel.standard)
    assert isinstance(out, str)
    assert hasattr(report, "level")
    assert hasattr(report, "steps_applied")
    assert hasattr(report, "changes_made")


def test_new_fields_default_empty():
    out, report = normalize_text("anything", NormalizationLevel.standard)
    assert report.footnote_spans == ()
    assert report.page_offsets == ()


def test_to_dict_includes_new_fields():
    out, report = normalize_text("anything", NormalizationLevel.standard)
    d = report.to_dict()
    assert d["footnote_spans"] == []
    assert d["page_offsets"] == []
