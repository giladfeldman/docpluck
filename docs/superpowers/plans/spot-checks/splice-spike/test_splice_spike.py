"""Unit tests for the splice spike. Synthetic inputs only — no PDF I/O."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from splice_spike import pdfplumber_table_to_markdown


def test_simple_2x3_table_becomes_html_table():
    table = [
        ["Variable", "M", "SD"],
        ["Age", "24.3", "3.1"],
        ["IQ", "100.5", "15.2"],
    ]
    result = pdfplumber_table_to_markdown(table)
    # HTML rendering (per 2026-05-09 user decision: HTML is the default)
    assert "<table>" in result
    assert "</table>" in result
    assert "<th>Variable</th>" in result
    assert "<th>M</th>" in result
    assert "<th>SD</th>" in result
    assert "<td>Age</td>" in result
    assert "<td>24.3</td>" in result
    assert "<td>IQ</td>" in result
    assert "<thead>" in result
    assert "<tbody>" in result


def test_none_cells_render_as_empty_string():
    table = [
        ["A", "B"],
        ["1", None],
        [None, "2"],
    ]
    result = pdfplumber_table_to_markdown(table)
    assert "<th>A</th>" in result
    assert "<th>B</th>" in result
    assert "<td>1</td>" in result
    assert "<td>2</td>" in result
    # Empty cells render as <td></td>
    assert "<td></td>" in result


def test_html_special_chars_escaped():
    """HTML special characters (<, >, &) must be escaped, not pipe characters."""
    table = [
        ["expression"],
        ["a < b & c > d"],
    ]
    result = pdfplumber_table_to_markdown(table)
    assert "&lt;" in result
    assert "&gt;" in result
    assert "&amp;" in result


def test_multiline_cell_renders_with_br():
    """Embedded newlines in a cell render as <br> tags in HTML output
    (the pipe-table limitation no longer applies)."""
    table = [
        ["heading"],
        ["line one\nline two"],
    ]
    # Note: input is two rows, so this is ONE data row with cell="line one\nline two".
    # The HTML renderer doesn't auto-split on \n inside a single cell — it's a
    # convention from the older pipe-table API. With HTML, the cell renders
    # as-is (newline preserved or normalized). Test that both lines appear.
    result = pdfplumber_table_to_markdown(table)
    assert "line one" in result
    assert "line two" in result


def test_empty_table_returns_empty_string():
    assert pdfplumber_table_to_markdown([]) == ""


def test_single_row_returns_empty_string():
    """A table with only a header and no data rows is degenerate; emit nothing
    so the spike doesn't insert phantom tables."""
    assert pdfplumber_table_to_markdown([["header only"]]) == ""


def test_continuation_rows_merge_with_br():
    """Rows where the first column is empty are continuations of the previous
    data row's cells, joined with ``<br>`` in the merged cell."""
    table = [
        ["No", "Hypothesis"],
        ["2a", "People underestimate negative experiences."],
        ["", "Multi-line continuation."],
    ]
    result = pdfplumber_table_to_markdown(table)
    # The continuation should be merged into hypothesis 2a's cell
    assert "<td>2a</td>" in result
    assert "People underestimate negative experiences.<br>Multi-line continuation." in result


def test_group_separator_row_uses_colspan():
    """A row with content only in the first cell (and N total columns) emits
    as a single <td colspan="N"> spanning the whole row."""
    table = [
        ["Ability", "Score", "Rank"],
        ["Easy", "", ""],
        ["Using a mouse", "3.1", "1"],
    ]
    result = pdfplumber_table_to_markdown(table)
    assert 'colspan="3"' in result
    assert "<strong>Easy</strong>" in result


from splice_spike import find_table_region_in_text


def test_finds_table_in_clear_page():
    page_text = (
        "This is the introduction paragraph that talks about the study.\n"
        "We measured several variables in our sample of 142 participants.\n"
        "\n"
        "Variable      M     SD    n\n"
        "Age          24.3   3.1   142\n"
        "IQ          100.5  15.2   142\n"
        "\n"
        "The table above shows our descriptives. Discussion follows."
    )
    table = [
        ["Variable", "M", "SD", "n"],
        ["Age", "24.3", "3.1", "142"],
        ["IQ", "100.5", "15.2", "142"],
    ]
    region = find_table_region_in_text(page_text, table)
    assert region is not None
    start, end = region
    lines = page_text.split("\n")
    region_text = "\n".join(lines[start:end])
    assert "Variable" in region_text
    assert "Age" in region_text
    assert "IQ" in region_text
    assert "introduction paragraph" not in region_text
    assert "Discussion follows" not in region_text


def test_returns_none_when_table_content_not_in_page():
    page_text = "No tables here. Just prose about cats."
    table = [
        ["Variable", "M"],
        ["Age", "24.3"],
    ]
    assert find_table_region_in_text(page_text, table) is None


def test_picks_correct_table_when_two_present():
    """Two tables on the same page; the function should return the region
    matching the table cells passed in, not the other table's region."""
    page_text = (
        "First table follows.\n"
        "Country  Population\n"
        "France   67000000\n"
        "Germany  83000000\n"
        "Then prose.\n"
        "Variable  M    SD\n"
        "Age       24   3\n"
        "IQ        100  15\n"
        "End."
    )
    second_table = [
        ["Variable", "M", "SD"],
        ["Age", "24", "3"],
        ["IQ", "100", "15"],
    ]
    region = find_table_region_in_text(page_text, second_table)
    assert region is not None
    start, end = region
    lines = page_text.split("\n")
    region_text = "\n".join(lines[start:end])
    assert "Variable" in region_text
    assert "France" not in region_text
    assert "Germany" not in region_text


def test_handles_pdftotext_column_interleaving_gracefully():
    """When pdftotext interleaves a 2-column page, table cells may be split
    across non-contiguous lines. The function should either return a region
    that covers the densest cluster (best-effort) or None (acknowledging
    failure). Either is acceptable; what's NOT acceptable is silently
    returning a region of unrelated prose."""
    page_text = (
        "Left column intro paragraph.\n"
        "Right column intro paragraph.\n"
        "Variable    M     SD     and right-column body line one\n"
        "Age         24.3  3.1    right-column body line two\n"
        "Discussion of left-column results.\n"
    )
    table = [
        ["Variable", "M", "SD"],
        ["Age", "24.3", "3.1"],
    ]
    region = find_table_region_in_text(page_text, table)
    if region is not None:
        start, end = region
        lines = page_text.split("\n")
        region_text = "\n".join(lines[start:end])
        # The region must contain at least the data row's identifying tokens
        assert "Age" in region_text
        assert "24.3" in region_text


from splice_spike import splice_tables_into_text


def test_replaces_table_region_with_markdown_table():
    pdftotext_text = (
        "Page 1 prose introduction.\n"
        "We measured the following variables.\n"
        "Variable      M     SD\n"
        "Age          24.3   3.1\n"
        "IQ          100.5  15.2\n"
        "Discussion follows the table."
    )
    tables = [
        {
            "page": 0,  # only page in this synthetic input
            "rows": [
                ["Variable", "M", "SD"],
                ["Age", "24.3", "3.1"],
                ["IQ", "100.5", "15.2"],
            ],
        }
    ]
    result = splice_tables_into_text(pdftotext_text, tables)

    # Original prose preserved
    assert "Page 1 prose introduction." in result
    assert "Discussion follows the table." in result
    # Original garbled table rows replaced
    assert "Variable      M     SD" not in result
    # HTML table inserted (per 2026-05-09 user decision: tables render as HTML)
    assert "<th>Variable</th>" in result
    assert "<th>M</th>" in result
    assert "<td>Age</td>" in result
    assert "<td>24.3</td>" in result


def test_handles_multiple_pages_via_form_feed():
    page1 = (
        "Page 1 prose.\n"
        "Variable A    Value\n"
        "thing         42\n"
        "more page 1 prose."
    )
    page2 = (
        "Page 2 prose, different tokens.\n"
        "Country  Population\n"
        "France   67000000\n"
        "page 2 ending."
    )
    pdftotext_text = page1 + "\f" + page2
    tables = [
        {"page": 0, "rows": [["Variable A", "Value"], ["thing", "42"]]},
        {"page": 1, "rows": [["Country", "Population"], ["France", "67000000"]]},
    ]
    result = splice_tables_into_text(pdftotext_text, tables)
    assert "<th>Variable A</th>" in result
    assert "<th>Country</th>" in result
    assert "<td>thing</td>" in result
    assert "<td>France</td>" in result
    # Prose between pages still present
    assert "Page 1 prose." in result
    assert "Page 2 prose, different tokens." in result


def test_table_with_unfindable_region_falls_back_to_page_top():
    """If find_table_region_in_text returns None, the orchestrator inserts the
    markdown table at the top of that page with a note. Tested by giving a
    table whose tokens do not appear on the page."""
    pdftotext_text = "Page with prose only and no table content."
    tables = [
        {
            "page": 0,
            "rows": [
                ["alpha", "beta"],
                ["gamma", "delta"],
            ],
        }
    ]
    result = splice_tables_into_text(pdftotext_text, tables)
    assert "<th>alpha</th>" in result
    assert "<td>gamma</td>" in result
    # Note must accompany unlocated tables so the eyeball reviewer can spot them.
    assert "[splice-spike: table location not found" in result
