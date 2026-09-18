"""Column correction must actually HAPPEN -- not merely fail quietly.

Why this file exists (2026-09-17, during the 2.4.144 release). A commit landed
`docpluck/extract.py` calling ``extract_pdf_layout(pdf_bytes, pages=[...])``
while the committed ``docpluck/extract_layout.py`` still had the one-argument
signature. Every paper needing column correction stopped getting it. Nothing
went red, because ``extract.py`` wraps the whole block in ``except Exception``
and folds the failure into the method string:

    method = f"{method}+column_correction_failed:{exc_name}"

So extraction still returned text, still looked successful, and the only
evidence of a lost capability was a substring nothing asserted on. The suite
had tests for how correction behaves and none for whether it runs at all --
the capability could be removed entirely and stay green.

The paper is chosen because it corrects with NO environment flags set:
``10.1016/j.jesp.2021.104154`` rewrites page 19 on the default path. A paper
that only corrects under ``DOCPLUCK_COLUMN_CORRECT_GENERAL`` would make this
gate depend on a flag production does not set.
"""

import pytest

from docpluck.extract import extract_pdf
from docpluck.testing import require_corpus_pdf

# Corrects page 19 on the default path, no env flags. If this paper ever stops
# needing correction the gate below fails LOUDLY rather than passing vacuously,
# which is the point -- see test_the_gate_detects_the_regression_it_exists_for.
_PAPER = "apa/chen_2021_jesp.pdf"


@pytest.fixture(scope="module")
def paper_bytes() -> bytes:
    # require_, not corpus_pdf: a paper this gate claims to test and cannot read
    # is a FAILURE, never a skip. A skipped capability gate is indistinguishable
    # from a passing one in a summary line.
    return require_corpus_pdf(_PAPER).read_bytes()


def test_column_correction_fires_on_the_default_path(paper_bytes):
    """The capability runs, and reports that it ran."""
    _text, method = extract_pdf(paper_bytes)
    assert "column_correction_failed" not in method, (
        "column correction raised and the exception was swallowed into the "
        "method string; extraction still 'succeeded'. method=" + method
    )
    assert "column_corrected:" in method, (
        "column correction did not fire on a paper that needs it. Either the "
        "capability is broken or this paper no longer exercises it -- both are "
        "release-stopping and neither may be silent. method=" + method
    )


def test_the_gate_detects_the_regression_it_exists_for(paper_bytes, monkeypatch):
    """Two-sided control: break it the way it broke, and prove the gate notices.

    Without this, a gate asserting only the happy path could itself be
    vacuous -- and a vacuous gate is worse than none, because it is counted.
    Here the exact 2026-09-17 defect is reproduced (a TypeError out of
    ``extract_pdf_layout``) and the assertion above is required to fail.
    """
    import docpluck.extract_layout as el

    def _boom(*_a, **_kw):
        raise TypeError("extract_pdf_layout() got an unexpected keyword argument 'pages'")

    monkeypatch.setattr(el, "extract_pdf_layout", _boom)
    _text, method = extract_pdf(paper_bytes)

    assert "column_correction_failed:TypeError" in method, (
        "the simulated break did not even reach the method string, so this "
        "control proves nothing about the gate. method=" + method
    )
    assert "column_corrected:" not in method, (
        "correction reported success while the layout call was raising. "
        "method=" + method
    )
