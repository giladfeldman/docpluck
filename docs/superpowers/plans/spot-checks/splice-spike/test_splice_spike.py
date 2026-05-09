"""Unit tests for the splice spike. Synthetic inputs only — no PDF I/O."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from splice_spike import pdfplumber_table_to_markdown


def test_simple_2x3_table_becomes_pipe_table():
    table = [
        ["Variable", "M", "SD"],
        ["Age", "24.3", "3.1"],
        ["IQ", "100.5", "15.2"],
    ]
    result = pdfplumber_table_to_markdown(table)
    expected = (
        "| Variable | M | SD |\n"
        "| --- | --- | --- |\n"
        "| Age | 24.3 | 3.1 |\n"
        "| IQ | 100.5 | 15.2 |\n"
    )
    assert result == expected


def test_none_cells_render_as_empty_string():
    table = [
        ["A", "B"],
        ["1", None],
        [None, "2"],
    ]
    result = pdfplumber_table_to_markdown(table)
    expected = (
        "| A | B |\n"
        "| --- | --- |\n"
        "| 1 |  |\n"
        "|  | 2 |\n"
    )
    assert result == expected


def test_pipe_in_cell_is_escaped():
    table = [
        ["expression"],
        ["a | b"],
    ]
    result = pdfplumber_table_to_markdown(table)
    expected = (
        "| expression |\n"
        "| --- |\n"
        "| a \\| b |\n"
    )
    assert result == expected


def test_multiline_cell_collapses_to_single_line():
    """pdfplumber sometimes returns cells with embedded newlines.
    Pipe-table syntax cannot represent newlines inside a cell, so they
    must collapse to a space."""
    table = [
        ["heading"],
        ["line one\nline two"],
    ]
    result = pdfplumber_table_to_markdown(table)
    expected = (
        "| heading |\n"
        "| --- |\n"
        "| line one line two |\n"
    )
    assert result == expected


def test_empty_table_returns_empty_string():
    assert pdfplumber_table_to_markdown([]) == ""


def test_single_row_returns_empty_string():
    """A table with only a header and no data rows is degenerate; emit nothing
    so the spike doesn't insert phantom tables."""
    assert pdfplumber_table_to_markdown([["header only"]]) == ""
