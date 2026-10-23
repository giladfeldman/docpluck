"""Alternating (recto/verso) running heads are furniture too.

10.1177/0956797610361706 (Psychological Science, 8 pages) prints
"Disease, Self-Perception, and Behavior <folio>" at the top of every even page
and "<folio>  Mortensen et al." at the top of every odd page after the first.
The layout-aware strip (`normalize._f0_strip_running_and_footnotes`) never took
either, for two independent reasons, both measured 2026-10-23:

1. It compared the topmost span's text EXACTLY across pages, and the folio is
   fused into that span ("... Behavior 441", "442  Mortensen et al."), so no two
   pages ever carried the same line.
2. It required a line on MORE THAN HALF the pages. Each alternating head sits on
   every page of ONE parity -- 4 of 8 here -- so even with the folio removed
   neither head qualified.

The text-only repeated-line strip needs >= 5 copies and these heads have 4, so
nothing removed them and the rendered markdown fused "Disease, Self-Perception,
and Behavior" into body prose four times.
"""

from pathlib import Path

import pytest

from conftest import pdf_path

pytest.importorskip("pdfplumber", reason="pdfplumber not installed (pip install docpluck[all])")

_DOI_FILE = "10.1177__0956797610361706.pdf"
_HEAD = "Disease, Self-Perception, and Behavior"


@pytest.fixture(scope="module")
def paper():
    p = Path(pdf_path("articlerepo", _DOI_FILE))
    if not p.is_file():
        pytest.fail(f"fixture not readable: {p} -- a gate that cannot read its paper must fail, never skip")
    from docpluck import extract_pdf
    from docpluck.extract_layout import extract_pdf_layout

    b = p.read_bytes()
    raw, _ = extract_pdf(b)
    return raw, extract_pdf_layout(b)


def _lines(text):
    return [ln.strip() for ln in text.splitlines()]


def test_both_alternating_heads_leave_the_layout_aware_body(paper):
    from docpluck import normalize_text
    from docpluck.normalize import NormalizationLevel

    raw, layout = paper
    assert raw.count(_HEAD) == 4, "positive control: the head is in the raw text 4 times"
    assert _lines(raw).count("Mortensen et al.") == 3, "positive control: the verso head, 3 times"
    for level in (NormalizationLevel.standard, NormalizationLevel.academic):
        out, _ = normalize_text(raw, level, layout=layout)
        assert out.count(_HEAD) == 0, f"{level.name}: recto running head survives"
        assert _lines(out).count("Mortensen et al.") == 0, f"{level.name}: verso running head survives"


def test_the_body_beside_the_heads_is_kept(paper):
    """Control: only the furniture goes -- the prose that follows each head stays."""
    from docpluck import normalize_text
    from docpluck.normalize import NormalizationLevel

    raw, layout = paper
    out, _ = normalize_text(raw, NormalizationLevel.academic, layout=layout)
    for words in ("beneficial for humans to have also", "chronically concerned with disease",
                  "response to disease salience"):
        assert words in " ".join(out.split()), words
    assert "Psychological Science" in out, "page 1's masthead line is not an alternating head"
