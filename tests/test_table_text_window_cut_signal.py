"""A table text cut by the 1500-char window must say so.

Before: the walk stopped silently at the window's far end while non-prose
table lines were still waiting, so a truncated table text was
indistinguishable from a complete one. Synthetic grid (numbers only, no
article text): the gate is structural -- a non-prose line beyond the window.
"""
from __future__ import annotations

from docpluck.extract_structured import _extract_table_body_text_and_reason
from docpluck.tables.captions import CaptionMatch
from docpluck.telemetry import fallback_scope

_CAPTION = "Table 2 Descriptive statistics by item"


def _cap(text: str) -> CaptionMatch:
    return CaptionMatch(kind="table", number=2, label="Table 2", page=5,
                        char_start=0, char_end=len(_CAPTION), line_text=_CAPTION)


def _rows(n: int) -> str:
    return "".join(f"{i:02d} item   {i}.{i % 10}0   ({i % 7}.{i % 9}1)   .{i:02d}\n"
                   for i in range(1, n + 1))


def _walk(text: str) -> tuple[str, dict]:
    with fallback_scope() as fb:
        body, _ = _extract_table_body_text_and_reason(text, _cap(text))
    return body, dict(fb.counters), {k: dict(v) for k, v in fb.details.items()}


def test_long_table_cut_by_window_records_the_cut():
    text = _CAPTION + "\n" + _rows(80)          # ~3000 chars of grid rows
    body, counters, details = _walk(text)
    assert "01 item" in body
    assert "80 item" not in body                  # the window really cut it
    assert counters.get("table_text_cut_at_window") == 1
    assert details["table_text_cut_at_window"] == {"Table 2 p5": 1}


def test_short_table_inside_window_records_nothing():
    text = _CAPTION + "\n" + _rows(10)
    body, counters, _ = _walk(text)
    assert "10 item" in body
    assert "table_text_cut_at_window" not in counters


def test_table_ended_by_prose_records_nothing():
    prose = ("The results of the second study were broadly consistent with the "
             "first, and we therefore pooled the samples for the main analysis.\n")
    text = _CAPTION + "\n" + _rows(10) + prose + _rows(60)
    body, counters, _ = _walk(text)
    assert "table_text_cut_at_window" not in counters


def test_capitalised_data_rows_are_not_trimmed_as_headings():
    """The trailing-heading trim popped every `Item NN  x.xx (y.yy) .zz` row."""
    rows = "".join(f"Item {i:02d}   {i}.{i % 10}0   ({i % 7}.{i % 9}1)   .{i:02d}\n"
                   for i in range(1, 11))
    text = _CAPTION + "\n" + rows
    body, _ = _extract_table_body_text_and_reason(text, _cap(text))
    assert "Item 01" in body and "Item 10" in body


def test_a_real_trailing_heading_is_still_trimmed():
    text = _CAPTION + "\n" + _rows(5) + "General Discussion\n"
    body, _ = _extract_table_body_text_and_reason(text, _cap(text))
    assert "05 item" in body
    assert "General Discussion" not in body
