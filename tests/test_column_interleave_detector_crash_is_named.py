"""A crash in the column-interleave detector must be recorded, not read as "none found".

`normalize_text` runs `_detect_column_interleave_pages` as a signal-only step
and catches any exception so the pipeline never blocks on it. But an empty
`column_interleave_pages` is ALSO what a clean document produces, so until
dbe7611 a consumer could not tell "no interleaved pages" from "the detector
crashed". dbe7611 added `record_fallback("column_interleave_detector_exception")`
-- the one fix of that audit's five that had no gate asserting it. This is it.

The detector only runs when `report.page_offsets` is populated, and those come
from the LAYOUT channel -- a constructed string with form feeds leaves them empty
and the detector is never reached (the first draft of this file did exactly that,
and its control assertion caught it). So it runs on a real paper with its layout.
"""
import pytest

import docpluck.normalize as nz
from docpluck.extract import extract_pdf
from docpluck.extract_layout import extract_pdf_layout
from docpluck.normalize import NormalizationLevel, normalize_text
from docpluck.testing import require_corpus_pdf

_PAPER = "apa/chan_feldman_2025_cogemo.pdf"


@pytest.fixture(scope="module")
def inputs():
    # require_, not corpus_pdf: a paper this gate needs and cannot read is a FAILURE.
    pdf = require_corpus_pdf(_PAPER).read_bytes()
    text, _method = extract_pdf(pdf)
    return text, extract_pdf_layout(pdf)


def _run(inputs):
    text, layout = inputs
    out = normalize_text(text, NormalizationLevel.academic, layout=layout)
    return out[1] if isinstance(out, tuple) else out


def test_control_a_healthy_detector_records_nothing(inputs):
    report = _run(inputs)
    assert report.page_offsets, "no page offsets: the detector was never reached"
    assert "column_interleave_detector_exception" not in report.fallbacks


def test_a_crashing_detector_is_named_in_fallbacks(monkeypatch, inputs):
    def _boom(*a, **k):
        raise RuntimeError("injected detector crash")

    monkeypatch.setattr(nz, "_detect_column_interleave_pages", _boom)
    report = _run(inputs)
    assert report.page_offsets, "no page offsets: the detector was never reached"
    assert report.column_interleave_pages == ()
    assert "column_interleave_detector_exception" in report.fallbacks, (
        "the detector crashed and the report reads exactly like a clean document; "
        f"fallbacks={report.fallbacks}"
    )
