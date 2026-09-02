"""`sectioning_text_id` — the offsets must name the buffer they index.

Asked for independently by Scimeto/CitationGuard and ESCImate on 2026-08-21,
after Scimeto measured that **27 of 27** of their stored documents held
`char_start`/`char_end` indexing a string they did not have
(`INBOX_FROM_SCIMETO_2026-08-21c_offsets_are_not_one_flag.md` §1). Nothing threw;
a drifted slice still returns text, just starting a few words off.

The field's whole value is that it cannot be right by accident, so these tests
assert the properties a consumer will actually rely on:

  - it is DERIVED from the returned text, not passed in (so it cannot disagree
    with the buffer standing next to it);
  - a one-character change to the buffer changes it;
  - a change to `SECTIONING_VERSION` changes it (same text, different cuts);
  - it reaches `to_dict()`, which is the only surface the CLI and the service
    serialize through;
  - the documented recipe reproduces it, so a JS consumer can verify rather
    than trust.
"""

import hashlib

import pytest

from docpluck.sections import (
    SECTIONING_VERSION,
    SectionedDocument,
    sectioning_text_id,
)


def _doc(text: str, version: str = SECTIONING_VERSION) -> SectionedDocument:
    return SectionedDocument(
        sections=(),
        normalized_text=text,
        sectioning_version=version,
        source_format="pdf",
    )


class TestDerivedNotPassed:
    def test_it_is_computed_from_the_text_it_ships_with(self):
        doc = _doc("Introduction\n\nWe tested whether ...")
        assert doc.sectioning_text_id == sectioning_text_id(
            doc.normalized_text, doc.sectioning_version
        )

    def test_it_cannot_be_supplied_by_a_caller(self):
        # `init=False`: a caller-supplied id could disagree with the text beside
        # it, which is the exact failure the field exists to detect.
        with pytest.raises(TypeError):
            SectionedDocument(
                sections=(),
                normalized_text="x",
                sectioning_version=SECTIONING_VERSION,
                source_format="pdf",
                sectioning_text_id="dp1/whatever/deadbeef",
            )


class TestItActuallyDiscriminates:
    def test_one_character_of_drift_changes_it(self):
        # The measured defect was a LENGTH change from Greek transliteration
        # (`pi` for U+03C0), which shifts every offset after it.
        a = _doc("mean age 30 years, pi = 3.14")
        b = _doc("mean age 30 years, π = 3.14")
        assert a.sectioning_text_id != b.sectioning_text_id

    def test_a_sectioning_version_bump_changes_it_on_identical_text(self):
        # Same buffer, different cuts. A hash of the text alone would call this
        # a match and hand the consumer stale spans.
        text = "Abstract\n\nWe report ...\n\nMethods\n\nParticipants ..."
        assert _doc(text, "1.2.5").sectioning_text_id != _doc(text, "1.2.6").sectioning_text_id

    def test_identical_input_gives_an_identical_id(self):
        assert _doc("same").sectioning_text_id == _doc("same").sectioning_text_id


class TestItReachesConsumers:
    def test_to_dict_carries_it(self):
        # `to_dict` is derived from `fields()`, so this passes for free — the
        # test is here because `Section.subheadings` went missing for a whole
        # release through a hand-written key list, and both consumer surfaces
        # serialize through this method.
        d = _doc("body").to_dict()
        assert d["sectioning_text_id"] == _doc("body").sectioning_text_id

    def test_it_is_exported_from_the_package_root(self):
        import docpluck

        assert docpluck.sectioning_text_id is sectioning_text_id


class TestTheDocumentedRecipeReproducesIt:
    def test_python_recipe(self):
        text = "Results\n\nt(48) = 2.11, p = .040, d = 0.30"
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
        assert sectioning_text_id(text, "1.2.5") == f"dp1/1.2.5/{digest}"

    def test_the_shape_is_the_documented_three_part_form(self):
        parts = sectioning_text_id("x", "1.2.5").split("/")
        assert parts[0] == "dp1"
        assert parts[1] == "1.2.5"
        assert len(parts) == 3 and len(parts[2]) == 32

    def test_astral_and_control_characters_hash_by_utf8_bytes(self):
        # A JS consumer slices with UTF-16 units but `TextEncoder`/`update(s,
        # "utf8")` agrees with Python here. Verified against node on
        # 2026-08-22: both give 06a25f342d2929c263966c9100ac5844 for this
        # string. Pinned so a future change to the recipe cannot silently
        # desync the two languages.
        text = "hello world — π ≥ β \x08 astral: \U0001f600"
        assert (
            sectioning_text_id(text, "1.0.0")
            == "dp1/1.0.0/06a25f342d2929c263966c9100ac5844"
        )
