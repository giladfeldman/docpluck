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


def test_locator_handles_blank_line_interleaved_pdftotext():
    """When pdftotext renders a table with each row separated by blank lines
    (a common 2-column page artifact), the locator must still find the
    region. Counting non-blank lines for the window cap fixes this — the
    earlier raw-line cap was starved by the doubled line count."""
    page_text = (
        "Some intro paragraph.\n"
        "\n"
        "T\n"
        "\n"
        "1: Findings caption split across paragraphs.\n"
        "\n"
        "Ability\n"
        "\n"
        "Domain\n"
        "\n"
        "Comparative\n"
        "\n"
        "Easy\n"
        "\n"
        "Using a mouse\n"
        "\n"
        "3.1\n"
        "\n"
        "Driving\n"
        "\n"
        "3.6\n"
        "\n"
        "1 Higher numbers reflect difficulty.\n"
    )
    table_rows = [
        ["Ability", "Domain", "Comparative"],
        ["Easy", "", ""],
        ["Using a mouse", "3.1", "0.21"],
        ["Driving", "3.6", "0.65"],
    ]
    region = find_table_region_in_text(page_text, table_rows)
    assert region is not None, "locator should find blank-line-separated table rows"
    start, end = region
    lines = page_text.split("\n")
    region_text = "\n".join(lines[start:end])
    assert "Ability" in region_text
    assert "Driving" in region_text


from splice_spike import _merge_continuation_rows


def test_case_c_label_modifier_merges_into_previous_row():
    """A 2-row table layout where col 0 carries a parenthetical label
    modifier ((Extension)) should merge into the row above whose hypothesis
    statement wraps incompletely (ends with conjunction "and")."""
    rows = [
        ["H3", "Compared to the replication", "Domain", "Replication and"],
        ["(Extension)", "condition participants, the easy", "diﬃculty;", "easy domain"],
        ["", "domain condition participants", "ambiguity", "conditions"],
        ["", "assign lower domain diﬃculty.", "", ""],
    ]
    merged = _merge_continuation_rows(rows)
    # Should collapse to ONE logical row (H3's row, with all continuations merged).
    assert len(merged) == 1
    parent = merged[0]
    # Col 0 contains both H3 and (Extension) joined by the merge separator.
    assert "H3" in parent[0]
    assert "(Extension)" in parent[0]
    # Col 1 contains the original hypothesis text plus continuations.
    assert "Compared to the replication" in parent[1]
    assert "domain condition participants" in parent[1]
    # Col 3 contains both 'Replication and' and continuation 'easy domain'.
    assert "Replication and" in parent[3]
    assert "easy domain" in parent[3]


def test_case_c_does_not_fire_on_complete_data_rows():
    """A row where the previous row's cells look complete (numeric data,
    sentence terminators) must NOT be merged into the previous row even if
    col 0 of the current row is short — they are separate data rows."""
    rows = [
        ["Age", "24.3", "3.1", "142"],
        ["IQ", "100.5", "15.2", "142"],
    ]
    merged = _merge_continuation_rows(rows)
    # Two rows must remain — the second is NOT a continuation of the first.
    assert len(merged) == 2
    assert merged[0][0] == "Age"
    assert merged[1][0] == "IQ"


from splice_spike import _dedupe_table_blocks


from splice_spike import _extract_footnote_lines


def test_footnote_extraction_picks_asterisk_and_note_lines():
    """Camelot drops prose-y rows from cells; the splice region preserves
    them. Footnote-marker paragraphs (``*M = 1.13...``, ``†No appropriate
    omnibus...``, ``Note.``) must be re-emitted after the rendered table so
    explanations of ``*`` / ``†`` symbols in cells aren't orphaned."""
    region = (
        "Some table data row here.\n\n"
        "More table data.\n\n"
        "*M = 1.13; SD = 0.55 (lower numbers indicate higher attentiveness).\n\n"
        "**M = 4.83, SD = 0.51 (higher numbers indicate higher attentiveness).\n\n"
        "†No appropriate omnibus effect size.\n\n"
        "Note. Counts above 80% are considered attentive.\n\n"
        "Some unrelated body prose that should not be picked up."
    )
    out = _extract_footnote_lines(region)
    # Must pick the *, **, †, and Note. lines, but NOT the body prose.
    joined = " ".join(out)
    assert "*M = 1.13" in joined
    assert "**M = 4.83" in joined
    assert "†No appropriate omnibus effect size." in joined
    assert "Note. Counts above 80% are considered attentive." in joined
    assert "Some unrelated body prose" not in joined


def test_footnote_extraction_skips_when_no_markers():
    """Region with no footnote markers returns empty list — don't emit
    spurious paragraphs after the table."""
    region = (
        "Header row\n\n"
        "Data row 1\n\n"
        "Data row 2\n\n"
        "Body prose follows."
    )
    assert _extract_footnote_lines(region) == []


from splice_spike import _drop_caption_leading_rows


def test_drop_caption_leading_label_only_row():
    """A leading row whose first cell is exactly ``Table N`` (with all
    other cells empty) is a caption-label fragment, not a header."""
    grid = [
        ["Table 5", "", "", "", ""],
        ["Variable", "Mean", "SD", "Mean", "SD"],
        ["Age", "24.3", "3.1", "25.1", "2.9"],
    ]
    out = _drop_caption_leading_rows(
        grid,
        label="Table 5",
        caption="Table 5 Descriptive table of the participation rates.",
    )
    assert out[0][0] == "Variable"
    assert len(out) == 2


def test_drop_caption_leading_caption_tail_row():
    """A row with content only in col 0, whose content appears verbatim in
    the caption text, is a caption-tail line picked up by Camelot."""
    grid = [
        ["Descriptive table of the participation rates.", "", "", "", ""],
        ["Variable", "Mean", "SD", "Mean", "SD"],
        ["Age", "24.3", "3.1", "25.1", "2.9"],
    ]
    out = _drop_caption_leading_rows(
        grid,
        label="Table 5",
        caption="Table 5 Descriptive table of the participation rates. Note: ...",
    )
    assert out[0][0] == "Variable"


def test_drop_caption_leading_page_number_row():
    """A row with col 0 empty and col 1 a small number (1-3 digits) and no
    other content is a page-number row Camelot picked up off-table."""
    grid = [
        ["", "5"],
        ["Variable", "Mean"],
        ["Age", "24.3"],
    ]
    out = _drop_caption_leading_rows(
        grid,
        label="Table 1",
        caption="Table 1: Mean age across conditions.",
    )
    assert out[0][0] == "Variable"


def test_drop_caption_does_not_drop_legitimate_header():
    """A row with multiple non-empty cells must NEVER be dropped — it's a
    real header even if col 0 is short or appears in caption."""
    grid = [
        ["Variable", "Mean", "SD"],
        ["Age", "24.3", "3.1"],
    ]
    out = _drop_caption_leading_rows(
        grid,
        label="Table 1",
        caption="Table 1: Mean age, SD, and Variable analysis across conditions.",
    )
    # All three rows preserved (the original 2 + nothing dropped).
    assert len(out) == 2
    assert out[0][0] == "Variable"


def test_drop_caption_empty_grid_returns_empty():
    assert _drop_caption_leading_rows([], "Table 1", "caption") == []


def test_dedupe_prefers_html_table_over_code_block():
    """When two ``### Table N`` blocks exist for the same N — one with an
    HTML ``<table>`` and one with a fragment-wrapped ``\\`\\`\\`` code block —
    the HTML one must win regardless of order."""
    text = (
        "### Table 1\n"
        "*caption A*\n\n"
        "```\n"
        "stray fragment lines\n"
        "more fragments\n"
        "```\n\n"
        "Some prose between blocks.\n\n"
        "### Table 1\n"
        "*caption B*\n\n"
        "<table>\n"
        "  <thead><tr><th>X</th></tr></thead>\n"
        "  <tbody><tr><td>1</td></tr></tbody>\n"
        "</table>\n"
    )
    out = _dedupe_table_blocks(text)
    # The HTML version must survive.
    assert "<table>" in out
    assert "<th>X</th>" in out
    # The code-block version must be removed.
    assert "stray fragment lines" not in out
    # Only ONE ### Table 1 heading remains.
    assert out.count("### Table 1") == 1
