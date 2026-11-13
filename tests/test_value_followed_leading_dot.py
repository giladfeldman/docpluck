"""A row label followed by an APA leading-dot value is value-followed (d-8930b8).

`_value_followed_fraction` is the discriminator that keeps a repeated table row
label from being deleted as a watermark. Before 2026-11-13 `.35`, `-.35` and
`<.001` were not "values", and label / blank / blank / value was out of reach,
so such a label voted "overlay". Both failed on v2.4.159.
"""
from __future__ import annotations

import pytest

from docpluck.normalize import _VALUE_ONLY_LINE, _value_followed_fraction


@pytest.mark.parametrize("v", [".35", "-.35", "<.001", "(.12)", "−.08*"])
def test_leading_dot_values_are_values(v):
    assert _VALUE_ONLY_LINE.match(v)


@pytest.mark.parametrize("v", ["Author Manuscript", ".net framework", "p < .001 in"])
def test_text_is_not_a_value(v):
    assert not _VALUE_ONLY_LINE.match(v)


def test_two_blank_lines_between_label_and_value():
    lines = ["Self-esteem", "", "", ".35", "Self-esteem", "", "", "-.12"]
    assert _value_followed_fraction(lines, [0, 4]) == 1.0
