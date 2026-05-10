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


from splice_spike import _is_header_like_row


def test_header_like_row_label_only():
    """A row of short text labels with zero numeric cells is header-like."""
    assert _is_header_like_row(["Variable", "Mean", "SD"]) is True
    assert _is_header_like_row(["", "Estimation", "Average estimation", ""]) is True


def test_header_like_row_data_with_numbers_is_not_header_like():
    """A data row with numeric cells fails the ≤30% numeric threshold."""
    assert _is_header_like_row(["Age", "24.3", "3.1"]) is False
    assert _is_header_like_row(["IQ", "100.5", "15.2"]) is False


def test_header_like_row_with_long_prose_is_not_header_like():
    """A hypothesis-statement row with one long cell exceeds the avg-length
    threshold and is recognized as data."""
    long = "Compared to judgments of others' abilities, participants' judgments of their own abilities better predict their comparative ability judgments."
    assert _is_header_like_row(["H1", long, "Replication"]) is False


def test_two_row_header_renders_both_in_thead():
    """When the first two rows of a grid are both header-like and the third
    row has numeric data, both rows must end up inside `<thead>` (with
    `<th>` cells), not `<tbody>`."""
    grid = [
        ["", "Estimation", "Average estimation", ""],
        ["Experiences", "errora", "error (%)", "t-statistics"],
        ["Negative experiences", "−17.2", "5.47**", ""],
    ]
    result = pdfplumber_table_to_markdown(grid)
    # Both header rows must be inside <thead>...</thead>, with <th> cells.
    head_block = result.split("<tbody>")[0]
    assert "<thead>" in head_block
    assert head_block.count("<tr>") == 2  # two header rows
    assert "<th>Experiences</th>" in head_block
    assert "<th>errora</th>" in head_block
    # Body must NOT contain those header cells as <td>.
    body_block = result.split("<tbody>")[1]
    assert "<td>Negative experiences</td>" in body_block
    assert "<th>Experiences</th>" not in body_block


def test_single_row_header_still_renders_one_thead_row():
    """When only the first row is header-like (rest is data), thead has
    exactly one <tr> — backward-compat with the simpler tables."""
    grid = [
        ["Variable", "Mean", "SD"],
        ["Age", "24.3", "3.1"],
        ["IQ", "100.5", "15.2"],
    ]
    result = pdfplumber_table_to_markdown(grid)
    head_block = result.split("<tbody>")[0]
    assert head_block.count("<tr>") == 1


from splice_spike import _split_mashed_cell


def test_mash_split_camel_case_with_long_left_word():
    """`groupEasy` splits into `group<br>Easy` because LEFT word ``group``
    is ≥ 4 chars."""
    out = _split_mashed_cell("Original domain groupEasy domain group")
    # The MERGE_SEPARATOR placeholder is what survives to <br> in HTML render.
    # Convert to readable form for assertion.
    rendered = out.replace("\x00BR\x00", "<br>")
    assert rendered == "Original domain group<br>Easy domain group"


def test_mash_split_letter_digit_with_long_left_word():
    """`size80` splits because ``size`` is a 4-letter word."""
    out = _split_mashed_cell("Sample size80")
    rendered = out.replace("\x00BR\x00", "<br>")
    assert rendered == "Sample size<br>80"


def test_mash_split_does_not_split_short_left_word():
    """`macOS` must NOT split — LEFT word ``mac`` is only 3 chars."""
    out = _split_mashed_cell("macOS Big Sur")
    assert "\x00BR\x00" not in out
    assert out == "macOS Big Sur"


def test_mash_split_does_not_split_iphone_or_ordinal():
    """`iPhone`, `WiFi`, and ordinals like `2a`/`H1` must NOT split."""
    assert "\x00BR\x00" not in _split_mashed_cell("iPhone")
    assert "\x00BR\x00" not in _split_mashed_cell("WiFi")
    assert "\x00BR\x00" not in _split_mashed_cell("Hypothesis 2a")
    assert "\x00BR\x00" not in _split_mashed_cell("H1")


def test_mash_split_does_not_split_camel_case_brand_names():
    """Camel-case boundaries use lowercase-only run length, so brand names
    like ``JavaScript`` (run ``ava`` = 3) and ``WordPress`` (run ``ord`` =
    3) don't false-split."""
    assert "\x00BR\x00" not in _split_mashed_cell("JavaScript")
    assert "\x00BR\x00" not in _split_mashed_cell("WordPress")


def test_mash_split_letter_digit_with_capital_start_word():
    """`Year2011` splits — letter→digit boundaries use any-letter word
    length, so a capital-start short word like ``Year`` (4 chars) catches
    column-mash that lowercase-only would miss."""
    out = _split_mashed_cell("Year2011 or earlier")
    rendered = out.replace("\x00BR\x00", "<br>")
    assert rendered == "Year<br>2011 or earlier"


def test_mash_split_handles_us_initials_after_long_word():
    """The pattern from ip_feldman Table 3:
    ``students`` → 8 chars, then ``U`` → split. Boundary is between
    ``s`` and ``U``."""
    out = _split_mashed_cell("U.S. American studentsU.S. American students")
    rendered = out.replace("\x00BR\x00", "<br>")
    assert rendered == "U.S. American students<br>U.S. American students"


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


from splice_spike import (
    _wrap_table_fragments,
    _is_spurious_single_column_grid,
    _render_grid_as_code_block,
    _format_table_md,
)


def test_spurious_1col_detector_flags_long_prose_run():
    """A grid with 5+ rows where each row has only one populated cell is
    almost certainly prose misclassified as a table."""
    grid = [
        ["Page header line"],
        ["Table caption echo"],
        ["Body paragraph A"],
        ["Body paragraph B"],
        ["Body paragraph C"],
    ]
    assert _is_spurious_single_column_grid(grid) is True


def test_spurious_1col_detector_passes_real_2col_table():
    """A real 2-column table must NOT be flagged."""
    grid = [
        ["Header 1", "Header 2"],
        ["A", "B"],
        ["C", "D"],
        ["E", "F"],
        ["G", "H"],
    ]
    assert _is_spurious_single_column_grid(grid) is False


def test_spurious_1col_detector_passes_short_1col_grid():
    """A short 1-column grid (e.g., 3 rows) might be a legitimate small list,
    so don't downgrade it."""
    grid = [["Item A"], ["Item B"], ["Item C"]]
    assert _is_spurious_single_column_grid(grid) is False


def test_spurious_1col_detector_passes_grid_with_some_multicol_rows():
    """A grid where AT LEAST one row has 2+ populated cells is a real table
    — the 1-col rows are likely just sparse cells."""
    grid = [
        ["Header 1", "Header 2"],
        ["Sparse row"],
        ["Sparse row 2"],
        ["Sparse row 3"],
        ["Sparse row 4"],
    ]
    assert _is_spurious_single_column_grid(grid) is False


def test_render_grid_as_code_block_joins_cells_per_row():
    grid = [
        ["First line of prose"],
        ["Second line of prose"],
        ["", "Third line", ""],  # multi-cell row joined with spaces
    ]
    out = _render_grid_as_code_block(grid)
    assert out.startswith("```\n")
    assert out.endswith("\n```")
    assert "First line of prose" in out
    assert "Second line of prose" in out
    assert "Third line" in out


def test_format_table_md_demotes_spurious_1col_to_code_block():
    """End-to-end: a fake 1-column "table" of prose renders as a code block,
    not as ``<table>``."""
    fake_table = {
        "label": "Table 5",
        "caption": "Classification of the replication.",
        "cells": [
            {"r": 0, "c": 0, "text": "Page header"},
            {"r": 1, "c": 0, "text": "Table 5: Classification of the replication."},
            {"r": 2, "c": 0, "text": "Design facet Replication"},
            {"r": 3, "c": 0, "text": "IV operationalization Same"},
            {"r": 4, "c": 0, "text": "DV operationalization Same"},
        ],
    }
    out = _format_table_md(fake_table)
    assert "<table>" not in out
    assert "```" in out
    assert "### Table 5" in out
    assert "IV operationalization Same" in out


def test_wrap_fragments_rescues_note_lines_from_uncaptioned_run():
    """A fragment-run of 5+ short paragraphs whose preceding caption does NOT
    match ``CAPTION_RE`` (e.g. ``Table S7. ...`` — supplement label with
    non-digit prefix) is otherwise silently dropped. Any ``Note.``, ``*M=…``,
    ``†p<.05`` lines inside that run must still be re-emitted as paragraphs —
    they're real source content, not duplicate-of-Camelot noise."""
    text = (
        "Table S7. The results of Binomial Logistic Regression\n\n"
        "Predictor\n\n"
        "Estimate SE\n\n"
        "Z\n\n"
        "p Odds ratio Lower\n\n"
        "Upper\n\n"
        "Intercept Conditions\n\n"
        "-0.298 0.275\n\n"
        "1.638 1.780\n\n"
        "Note. N =161; Estimates represent the log odds of \"DV = 1\" vs. \"DV = 0\";\n\n"
        "Some non-fragment body paragraph that has more than one hundred characters in it so it is not a fragment."
    )
    out = _wrap_table_fragments(text, existing_table_nums=set())
    # The ``Note.`` line must survive even though the surrounding numeric rows
    # are dropped (caption_label is None, so no ``### Table S7`` block emitted).
    assert "Note. N =161" in out
    assert 'log odds of "DV = 1"' in out
    # The non-fragment body paragraph still emits.
    assert "Some non-fragment body paragraph" in out


def test_wrap_fragments_skips_marker_only_paragraphs():
    """A stray ``†`` / ``*`` paragraph (just the marker, no content) is noise
    — its real footnote text lives elsewhere as prose. Don't re-emit it."""
    text = (
        "Some long preceding paragraph that is not classified as a fragment because it is too long over hundred chars.\n\n"
        "X1\n\n"
        "X2\n\n"
        "X3\n\n"
        "X4\n\n"
        "†\n\n"
        "X5\n\n"
        "Some other paragraph long enough to break out of being considered a fragment by the heuristic.\n\n"
        "Note. The actual footnote prose is preserved as it is substantive content here.\n\n"
        "X6\n\n"
        "X7\n\n"
        "X8\n\n"
        "X9\n\n"
        "X10\n\n"
        "Final non-fragment paragraph that is long enough to break the run, otherwise the run would never end."
    )
    out = _wrap_table_fragments(text, existing_table_nums=set())
    # The marker-only "†" paragraph drops (under 8 chars after strip).
    assert "\n†\n" not in out
    assert "\n\n†\n\n" not in out
    # The substantive Note. line in the next dropped run is rescued.
    assert "Note. The actual footnote prose" in out


def test_wrap_fragments_uncaptioned_run_drops_pure_noise():
    """An un-captioned fragment-run with NO footnote markers stays dropped —
    that's the existing dedup-vs-Camelot behavior we're preserving. Only
    footnote-bearing paragraphs are rescued, not numeric noise."""
    text = (
        "Some prefix paragraph that is long enough to be classified as real prose by the fragment heuristic.\n\n"
        "X1\n\n"
        "X2\n\n"
        "X3\n\n"
        "X4\n\n"
        "X5\n\n"
        "X6\n\n"
        "Some non-fragment body paragraph that has more than one hundred characters in it so it is not a fragment."
    )
    out = _wrap_table_fragments(text, existing_table_nums=set())
    # The pure-noise fragments still drop (no footnote markers to rescue).
    assert "X1" not in out
    assert "X6" not in out
    # The flanking paragraphs survive.
    assert "Some prefix paragraph" in out
    assert "Some non-fragment body paragraph" in out


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
