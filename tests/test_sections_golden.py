"""Regression test: sectioner output snapshot.

CI fails when SECTIONING_VERSION is unchanged but output drifts.
On a SECTIONING_VERSION bump, regenerate snapshots:

    DOCPLUCK_REGEN_GOLDEN=1 pytest tests/test_sections_golden.py
"""

import json
import os
import pathlib

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("pdfplumber")

from docpluck import extract_sections, SECTIONING_VERSION
from tests.fixtures.sections import builders


GOLDEN_DIR = pathlib.Path(__file__).parent / "golden" / "sections"


def _serialize(doc) -> dict:
    return {
        "sectioning_version": doc.sectioning_version,
        "source_format": doc.source_format,
        "sections": [
            {
                "label": s.label,
                "canonical_label": s.canonical_label.value,
                "char_start": s.char_start,
                "char_end": s.char_end,
                "pages": list(s.pages),
                "confidence": s.confidence.value,
                "detected_via": s.detected_via.value,
                "heading_text": s.heading_text,
            }
            for s in doc.sections
        ],
    }


def assert_universal_coverage(doc) -> None:
    """Every character of ``normalized_text`` belongs to exactly one section.

    THIS RUNS EVEN UNDER ``DOCPLUCK_REGEN_GOLDEN=1``, on purpose. A snapshot
    can always be refreshed until it is green, which is the documented way to
    defeat a golden gate; a property cannot. So the snapshot pins WHAT the
    sectioner produced and this pins that it is still well-formed, and a
    regeneration that orphaned text would be refused at the moment of writing
    rather than recorded as the new truth.

    Added 2026-08-29, and it is a NEW GUARD rather than a regression pin —
    it passes against both the pre- and post-1.9.61 trees. It exists because
    of what the 1.9.61 golden drift turned out to be: normalization stopped
    eating the document's trailing page boundary, `normalized_text` grew by
    the two characters ``\\n\\f``, and the final section's ``char_end`` moved
    138->170 (single-study) and 190->222 (multi-study) to keep covering it.
    Had the sectioner NOT extended, the goldens would still have matched on
    every field while two characters belonged to no section at all — which is
    the failure this function can see and a snapshot comparison cannot.
    """
    text = doc.normalized_text
    sections = sorted(doc.sections, key=lambda s: s.char_start)
    if not sections:
        return
    assert sections[0].char_start == 0, (
        f"first section starts at {sections[0].char_start}, so "
        f"{sections[0].char_start} leading characters belong to no section"
    )
    cursor = 0
    for s in sections:
        assert s.char_start <= cursor, (
            f"gap before {s.canonical_label.value}: characters "
            f"[{cursor}:{s.char_start}] belong to no section — "
            f"{text[cursor:s.char_start]!r}"
        )
        cursor = max(cursor, s.char_end)
    assert cursor == len(text), (
        f"the last section ends at {cursor} but the text is {len(text)} "
        f"characters — {text[cursor:]!r} belongs to no section"
    )


def _check_snapshot(name: str, doc) -> None:
    path = GOLDEN_DIR / f"{name}.json"
    serialized = _serialize(doc)
    assert_universal_coverage(doc)
    if os.environ.get("DOCPLUCK_REGEN_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(serialized, indent=2))
        return
    if not path.exists():
        pytest.skip(f"No golden file for {name}; set DOCPLUCK_REGEN_GOLDEN=1 to create.")
    expected = json.loads(path.read_text())
    assert serialized["sectioning_version"] == SECTIONING_VERSION
    assert serialized == expected, (
        f"{name}: output drifted but SECTIONING_VERSION unchanged. "
        "Either fix the regression, or bump SECTIONING_VERSION and regenerate "
        "with DOCPLUCK_REGEN_GOLDEN=1."
    )


def test_golden_apa_single_study_pdf():
    doc = extract_sections(builders.build_apa_single_study_pdf())
    _check_snapshot("apa_single_study_pdf", doc)


def test_golden_apa_multi_study_pdf():
    doc = extract_sections(builders.build_apa_multi_study_pdf())
    _check_snapshot("apa_multi_study_pdf", doc)


def test_golden_html_real_headings():
    pytest.importorskip("bs4")
    doc = extract_sections(builders.build_html_with_real_headings())
    _check_snapshot("html_real_headings", doc)


def test_the_coverage_guard_rejects_an_orphaned_tail():
    """The guard above must actually fail when text is orphaned.

    A guard nobody has watched fail is a claim, not a check — and the exact
    shape it exists to catch (the last section stopping short of the text)
    is invisible to the snapshot comparison beside it, because every field
    still matches. This truncates the final section by the two characters the
    1.9.61 page-boundary repair restored and asserts the guard says so.
    """
    import dataclasses

    doc = extract_sections(builders.build_apa_single_study_pdf())
    assert_universal_coverage(doc)  # the real document is well-formed

    last = doc.sections[-1]
    truncated = dataclasses.replace(last, char_end=last.char_end - 2)
    maimed = dataclasses.replace(doc, sections=doc.sections[:-1] + (truncated,))

    with pytest.raises(AssertionError, match="belongs to no section"):
        assert_universal_coverage(maimed)
