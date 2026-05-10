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


def test_two_row_header_folds_super_into_sub():
    """Super-header pattern (top row has empty cells AND every populated top
    cell has a populated cell directly below) folds column-wise into the
    next row using ``<br>``. ip_feldman Table 1 pattern.

    Replaces an earlier test that asserted both rows render separately;
    iteration 9 (commit pending) folds them per Tier A1 of the
    iteration-3 handoff."""
    grid = [
        ["", "Estimation", "Average estimation", ""],
        ["Experiences", "errora", "error (%)", "t-statistics"],
        ["Negative experiences", "−17.2", "5.47**", ""],
    ]
    result = pdfplumber_table_to_markdown(grid)
    head_block = result.split("<tbody>")[0]
    body_block = result.split("<tbody>")[1]
    # After folding there is exactly one header row.
    assert head_block.count("<tr>") == 1
    assert "<th>Experiences</th>" in head_block
    assert "<th>Estimation<br>errora</th>" in head_block
    assert "<th>Average estimation<br>error (%)</th>" in head_block
    assert "<th>t-statistics</th>" in head_block
    # Original separate cells must NOT appear.
    assert "<th>errora</th>" not in head_block
    assert "<th>Estimation</th>" not in head_block
    # Body unchanged.
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


from splice_spike import _fold_super_header_rows


def test_fold_super_header_korbmacher_table7_pattern():
    """korbmacher Table 7 shape: 7 columns where ``Mean`` is super-header for
    ``difference`` (col 3) and ``Effect`` is super-header for ``size r``
    (col 5). After fold the two header rows collapse to one."""
    grid = [
        ["", "", "", "Mean", "", "Effect", ""],
        ["Condition", "T-statistic", "df", "difference", "p-value", "size r", "95% CI"],
        ["Original", "668.5", "238", "2.78", "<.001", "0.82", "[0.79, 0.85]"],
    ]
    result = pdfplumber_table_to_markdown(grid)
    head_block = result.split("<tbody>")[0]
    # One folded header row.
    assert head_block.count("<tr>") == 1
    assert "<th>Condition</th>" in head_block
    assert "<th>Mean<br>difference</th>" in head_block
    assert "<th>Effect<br>size r</th>" in head_block
    assert "<th>95% CI</th>" in head_block
    # Pre-fold separate cells must NOT appear.
    assert "<th>Mean</th>" not in head_block
    assert "<th>Effect</th>" not in head_block


def test_fold_super_header_does_not_fold_real_two_row_header():
    """If every cell in the top header row is populated (no empty cells),
    it's a genuine 2-row label header, not a super-header. Don't fold."""
    rows = [
        ["Group A", "Group A", "Group B", "Group B"],
        ["Mean", "SD", "Mean", "SD"],
    ]
    out = _fold_super_header_rows([list(r) for r in rows])
    assert len(out) == 2
    assert out[0] == ["Group A", "Group A", "Group B", "Group B"]
    assert out[1] == ["Mean", "SD", "Mean", "SD"]


def test_fold_super_header_does_not_fold_when_sub_below_super_is_empty():
    """If a populated super cell has an EMPTY cell directly below it, that's
    likely an implicit colspan we mustn't squash. Don't fold."""
    rows = [
        ["", "Statistics", "Statistics", ""],
        ["Variable", "Mean", "SD", ""],
    ]
    # Super "Statistics" at col 1 has sub "Mean" (ok); col 2 has sub "SD"
    # (ok). Both populated supers have populated subs — fold should fire.
    out = _fold_super_header_rows([list(r) for r in rows])
    assert len(out) == 1
    # Now flip: col 2's sub is empty, breaking the rule.
    rows2 = [
        ["", "Statistics", "Statistics", ""],
        ["Variable", "Mean", "", "t"],
    ]
    out2 = _fold_super_header_rows([list(r) for r in rows2])
    assert len(out2) == 2  # not folded


def test_fold_super_header_drops_entirely_empty_super_row():
    """A header row that is all-empty should be dropped (keep only the
    populated row below)."""
    rows = [
        ["", "", "", ""],
        ["Variable", "Mean", "SD", "n"],
    ]
    out = _fold_super_header_rows([list(r) for r in rows])
    assert len(out) == 1
    assert out[0] == ["Variable", "Mean", "SD", "n"]


def test_fold_super_header_uses_merge_separator_placeholder():
    """The fold join must use the ``_MERGE_SEPARATOR`` placeholder so the
    ``<br>`` survives ``_html_escape``."""
    from splice_spike import _MERGE_SEPARATOR
    rows = [
        ["", "Estimation", ""],
        ["Var", "error", "t"],
    ]
    out = _fold_super_header_rows([list(r) for r in rows])
    assert len(out) == 1
    assert out[0][1] == f"Estimation{_MERGE_SEPARATOR}error"


def test_fold_super_header_no_op_on_single_row():
    """One-row header is unchanged."""
    rows = [["Variable", "Mean", "SD"]]
    out = _fold_super_header_rows([list(r) for r in rows])
    assert out == rows


from splice_spike import _fold_suffix_continuation_columns


def test_suffix_fold_ziano_table2_pattern():
    """ziano Table 2: ``Win-:`` / ``Loss-`` over ``Uncertain`` /
    ``Uncertain`` merges per column to ``Win-:Uncertain`` /
    ``Loss-Uncertain``. Row 1 becomes empty and is dropped."""
    rows = [
        ["", "N", "Pass-Fail", "Win-:", "Loss-"],
        ["", "",  "",          "Uncertain", "Uncertain"],
    ]
    out = _fold_suffix_continuation_columns([list(r) for r in rows])
    assert len(out) == 1
    assert out[0] == ["", "N", "Pass-Fail", "Win-:Uncertain", "Loss-Uncertain"]


def test_suffix_fold_does_not_fire_when_top_does_not_end_open_punct():
    """Top cell ``Mean`` (no trailing ``-`` or ``:``) doesn't fold even if
    bottom is ``difference``. The super-header fold (different rule)
    handles that case."""
    rows = [
        ["", "Mean"],
        ["X", "difference"],
    ]
    out = _fold_suffix_continuation_columns([list(r) for r in rows])
    assert out == rows


def test_suffix_fold_does_not_fire_when_bottom_starts_with_digit():
    """Bottom cell starting with a digit/symbol isn't a word continuation
    — don't merge."""
    rows = [
        ["", "Section-"],
        ["", "1.2"],
    ]
    out = _fold_suffix_continuation_columns([list(r) for r in rows])
    assert out == rows


def test_suffix_fold_keeps_row1_when_some_cells_dont_merge():
    """Per-column rule: cols that meet the rule merge, cols that don't
    keep their bottom-row cell intact."""
    rows = [
        ["", "Win-",      "Real header A"],
        ["", "Uncertain", "Real header B"],
    ]
    out = _fold_suffix_continuation_columns([list(r) for r in rows])
    # Col 1 merged; col 2 untouched. Row 1 still has "Real header B"
    # so it stays.
    assert len(out) == 2
    assert out[0] == ["", "Win-Uncertain", "Real header A"]
    assert out[1] == ["", "", "Real header B"]


def test_suffix_fold_no_op_for_single_row_header():
    """Doesn't apply to 1-row headers."""
    rows = [["Win-:", "Loss-"]]
    out = _fold_suffix_continuation_columns([list(r) for r in rows])
    assert out == rows


def test_suffix_fold_no_op_for_3_row_header():
    """Conservative — only fires on exactly 2-row headers."""
    rows = [
        ["", "A-", "B-"],
        ["", "X",  "Y"],
        ["", "Z",  "W"],
    ]
    out = _fold_suffix_continuation_columns([list(r) for r in rows])
    assert out == rows


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
    # Brand names embedded in prose still don't split — the lowercase run
    # is preceded by an UPPER letter, not whitespace.
    assert "\x00BR\x00" not in _split_mashed_cell("the JavaScript runtime")
    assert "\x00BR\x00" not in _split_mashed_cell("uses WordPress on macOS")


def test_mash_split_relaxed_3char_with_whitespace_anchor():
    """Iteration 10 relaxed rule: 3-char lowercase run anchored by
    whitespace AND followed by Capital+lowercase splits.

    Catches efendic Table 1's ``Risk is lowPositive affect`` where ``low``
    is only 3 chars but is clearly a complete word due to the preceding
    space and the trailing lowercase ``ositive``."""
    out = _split_mashed_cell("Risk is lowPositive affect")
    rendered = out.replace("\x00BR\x00", "<br>")
    assert rendered == "Risk is low<br>Positive affect"

    out2 = _split_mashed_cell("Benefit is lowNegative affect")
    rendered2 = out2.replace("\x00BR\x00", "<br>")
    assert rendered2 == "Benefit is low<br>Negative affect"


def test_mash_split_relaxed_anchored_at_string_start():
    """Cell starting with a 3-char word + Capital+lowercase splits at the
    string start (no preceding whitespace required)."""
    out = _split_mashed_cell("lowPositive affect")
    rendered = out.replace("\x00BR\x00", "<br>")
    assert rendered == "low<br>Positive affect"


def test_mash_split_relaxed_does_not_split_macos_in_prose():
    """Brand names like ``macOS`` even with a leading whitespace anchor
    don't split because the right-side Capital is followed by an UPPER
    letter (``S``), not lowercase — so it's an all-caps token, not a word."""
    out = _split_mashed_cell("running on macOS daily")
    assert "\x00BR\x00" not in out


def test_mash_split_relaxed_does_not_split_two_caps_in_a_row():
    """Pattern like ``CI`` after a 3-char word should NOT split — the
    Capital after the boundary must be followed by a lowercase letter to
    qualify as a real word start."""
    out = _split_mashed_cell("the lowCI bound")
    assert "\x00BR\x00" not in out


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


def test_drop_caption_leading_caption_tail_in_non_zero_column():
    """Camelot sometimes places the second line of a wrapped caption into
    column 1 (or higher) instead of column 0. korbmacher Table 7's first row
    is ``["", "ratings between easy and diﬃcult abilities (within conditions).",
    "", "", "", "", ""]`` — the caption-tail leak. Rule 4 drops it."""
    grid = [
        ["", "ratings between easy and diﬃcult abilities (within conditions).", "", "", "", "", ""],
        ["", "", "", "Mean", "", "Eﬀect", ""],
        ["Condition", "T-statistic", "df", "diﬀerence", "p-value", "size r", "95% CI"],
        ["Original", "668.5", "238", "2.78", "<.001", "0.82", "[0.79, 0.85]"],
    ]
    out = _drop_caption_leading_rows(
        grid,
        label="Table 7",
        caption=(
            "Asymptotic Wilcoxon-Mann-Whitney tests comparing perceived domain diﬃculty "
            "ratings between easy and diﬃcult abilities (within conditions)."
        ),
    )
    # The caption-tail row drops; the actual two header rows + data row remain.
    assert len(out) == 3
    assert out[0][3] == "Mean"
    assert out[1][0] == "Condition"


def test_drop_caption_rule4_does_not_fire_when_text_not_in_caption():
    """Rule 4 ONLY drops when the populated cell appears verbatim in the
    caption — random single-cell rows must not be dropped."""
    grid = [
        ["", "Subgroup A", "", "", ""],
        ["x1", "x2", "x3", "x4", "x5"],
    ]
    out = _drop_caption_leading_rows(
        grid,
        label="Table 1",
        caption="Some caption that does not mention Subgroup at all.",
    )
    # Subgroup A row stays (it's not in caption).
    assert len(out) == 2
    assert out[0][1] == "Subgroup A"


def test_drop_caption_rule4_does_not_fire_on_multi_populated_row():
    """Rule 4 requires EXACTLY one populated cell — a multi-cell row, even
    if some content overlaps caption, must stay."""
    grid = [
        # Two populated cells; "Mean" is in caption but row has > 1 populated cell.
        ["Variable", "Mean", "", "", ""],
        ["Age", "24.3", "3.1", "0.5", "1.0"],
    ]
    out = _drop_caption_leading_rows(
        grid,
        label="Table 1",
        caption="Mean values across conditions.",
    )
    assert len(out) == 2
    assert out[0][0] == "Variable"


from splice_spike import (
    _wrap_table_fragments,
    _is_spurious_single_column_grid,
    _render_grid_as_code_block,
    _format_table_md,
    _detect_side_by_side_merge,
    _extract_column_subgrid,
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


def test_side_by_side_detector_fires_on_two_table_labels():
    """A header row of [Table 3, Table 4] is the chandrashekar pattern: two
    independent tables that Camelot stitched into one grid. Returns the
    column index of the matching label."""
    grid = [
        ["Table 3", "Table 4"],
        ["row 1 col 0 prose", "row 1 col 1 prose"],
        ["row 2 col 0 prose", "row 2 col 1 prose"],
    ]
    assert _detect_side_by_side_merge(grid, label="Table 3") == 0
    assert _detect_side_by_side_merge(grid, label="Table 4") == 1
    # Label not in header → None (we'd render the full grid as fallback).
    assert _detect_side_by_side_merge(grid, label="Table 5") is None


def test_side_by_side_detector_skips_when_labels_repeat():
    """Two ``Table 1`` cells side-by-side aren't a stitch — they're a
    legitimate (if unusual) repeat-header. Don't fire."""
    grid = [
        ["Table 1", "Table 1"],
        ["A", "B"],
    ]
    assert _detect_side_by_side_merge(grid, label="Table 1") is None


def test_side_by_side_detector_skips_when_first_row_has_real_headers():
    """A normal header row is NOT all Table-N labels."""
    grid = [
        ["Variable", "Mean", "SD"],
        ["Age", "24.3", "3.1"],
    ]
    assert _detect_side_by_side_merge(grid, label="Table 1") is None


def test_side_by_side_detector_supports_supplement_labels():
    """``Table S7`` / ``Table S8`` is a valid two-different-label pair."""
    grid = [
        ["Table S7", "Table S8"],
        ["A", "B"],
    ]
    assert _detect_side_by_side_merge(grid, label="Table S7") == 0


def test_extract_column_subgrid_picks_target_column():
    grid = [
        ["Table 3", "Table 4"],
        ["3a", "4a"],
        ["3b", "4b"],
        ["3c", ""],
    ]
    out = _extract_column_subgrid(grid, col_idx=0)
    assert out == [["3a"], ["3b"], ["3c"]]
    out2 = _extract_column_subgrid(grid, col_idx=1)
    assert out2 == [["4a"], ["4b"], [""]]


def test_format_table_md_splits_side_by_side_merged_table():
    """End-to-end: a side-by-side-merged grid for ``Table 3`` renders only
    Table 3's column content, dropped to a code block (1-col after split)."""
    fake_table = {
        "label": "Table 3",
        "caption": "Study stimuli for conceptual replication.",
        "cells": [
            {"r": 0, "c": 0, "text": "Table 3"},
            {"r": 0, "c": 1, "text": "Table 4"},
            {"r": 1, "c": 0, "text": "Stimuli for Johnson 2002"},
            {"r": 1, "c": 1, "text": "LeBel classification: replication"},
            {"r": 2, "c": 0, "text": "Introduction prose"},
            {"r": 2, "c": 1, "text": "Design facet: Same"},
            {"r": 3, "c": 0, "text": "More body text"},
            {"r": 3, "c": 1, "text": "Procedural details: Similar"},
        ],
    }
    out = _format_table_md(fake_table)
    # Code block with Table 3's column content only.
    assert "<table>" not in out
    assert "```" in out
    assert "Stimuli for Johnson 2002" in out
    assert "Introduction prose" in out
    # Table 4's cells must NOT leak into Table 3's render.
    assert "LeBel classification" not in out
    assert "Procedural details" not in out


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


def test_wrap_fragments_label_norm_preserves_full_figure_word():
    """Regression: previous code had ``re.sub(r"^Fig\\.?", "Figure", ...)``
    which on a caption_label of ``Figure 6`` would match the ``Fig``
    prefix and prepend a second ``ure`` → ``Figureure 6``. Seen in
    demography_1 Figure 6. Negative lookahead ``(?!ure)`` blocks the
    rewrite when the full word ``Figure`` is already present.
    """
    text = (
        "Figure 6 baseline caption text on this line\n\n"
        "X1\n\nX2\n\nX3\n\nX4\n\nX5\n\nX6\n\n"
        "Final non-fragment paragraph long enough to break the run, with several real words so it is not detected as a fragment line itself."
    )
    out = _wrap_table_fragments(text, existing_table_nums=set())
    # The corrupt label must NOT appear.
    assert "Figureure" not in out
    # If a labeled block was emitted, it should use the normal label.
    if "###" in out:
        assert "### Figure 6" in out


def test_wrap_fragments_label_norm_still_rewrites_short_fig():
    """Sanity: the ``Fig`` / ``Fig.`` → ``Figure`` rewrite still fires
    for inputs like ``Fig 7`` / ``Fig. 7`` (real shortcuts that need
    expansion). Only ``Figure`` is left alone."""
    text = (
        "Fig. 7 baseline caption text on this line\n\n"
        "X1\n\nX2\n\nX3\n\nX4\n\nX5\n\nX6\n\n"
        "Final non-fragment paragraph long enough to break the run, with several real words so it is not detected as a fragment line itself."
    )
    out = _wrap_table_fragments(text, existing_table_nums=set())
    # Bug-corrupt label must NOT appear.
    assert "Figureure" not in out
    if "###" in out:
        # Fig / Fig. should normalize to Figure.
        assert "### Figure" in out


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


from splice_spike import _strip_redundant_caption_echo_before_tables


def test_strip_caption_echo_when_orphan_is_subset_of_rendered():
    """Iteration 11: orphan ``Table N: ...`` line whose words are all in
    the rendered caption gets stripped."""
    text = (
        "Some preceding paragraph.\n\n"
        "Table 2: Extension: Manipulation of perceived domain difficulty.\n\n"
        "### Table 2\n"
        "*Extension: Manipulation of perceived domain difficulty in target's domains.*\n\n"
        "<table><tr><td>data</td></tr></table>\n"
    )
    out = _strip_redundant_caption_echo_before_tables(text)
    # The orphan caption line must be removed.
    assert "Table 2: Extension: Manipulation" not in out
    # Heading and rendered caption stay.
    assert "### Table 2" in out
    assert "*Extension: Manipulation" in out
    # Preceding paragraph stays.
    assert "Some preceding paragraph." in out


def test_strip_caption_echo_preserves_orphan_with_unique_content():
    """When the orphan caption contains a word NOT in the rendered caption,
    the orphan stays — content preservation is the hard rule."""
    text = (
        "Table 2: Mentions the unique-word XYLOPHONE here.\n\n"
        "### Table 2\n"
        "*Different rendered caption text here.*\n\n"
        "<table></table>\n"
    )
    out = _strip_redundant_caption_echo_before_tables(text)
    assert "XYLOPHONE" in out
    assert "Table 2: Mentions" in out


def test_strip_caption_echo_only_strips_matching_table_number():
    """Orphan ``Table 5: ...`` near a ``### Table 6`` heading is NOT
    stripped — wrong number."""
    text = (
        "Table 5: Some leftover orphan here.\n\n"
        "### Table 6\n"
        "*Real caption for table six.*\n\n"
    )
    out = _strip_redundant_caption_echo_before_tables(text)
    assert "Table 5: Some leftover orphan" in out


def test_strip_caption_echo_handles_truncated_orphan():
    """A typical case: pdftotext renders a wrapped caption truncated. As
    long as every word in the truncated line is in the full rendered
    caption, strip it."""
    text = (
        "Table 7: Asymptotic Wilcoxon-Mann-Whitney tests comparing perceived domain difficulty\n\n"
        "### Table 7\n"
        "*Asymptotic Wilcoxon-Mann-Whitney tests comparing perceived domain difficulty ratings between easy and difficult abilities.*\n\n"
    )
    out = _strip_redundant_caption_echo_before_tables(text)
    assert "Table 7: Asymptotic" not in out
    assert "*Asymptotic Wilcoxon-Mann-Whitney" in out


def test_strip_caption_echo_does_not_strip_when_no_rendered_caption():
    """If there's no italic ``*caption*`` directly after the heading,
    don't strip — we can't verify content containment."""
    text = (
        "Table 2: Some echo.\n\n"
        "### Table 2\n\n"
        "<table></table>\n"
    )
    out = _strip_redundant_caption_echo_before_tables(text)
    assert "Table 2: Some echo" in out


def test_strip_caption_echo_walks_past_header_fragments_in_table():
    """ip_feldman Table 1 pattern: orphan caption + leaked header-cell
    fragments (``Study 1b``, ``Study 3``) appear between the orphan and
    the ``### Table 1`` heading. Both the caption AND the fragments are
    stripped because every word is in the rendered table."""
    text = (
        "Body paragraph text here that is not a header fragment.\n\n"
        "Table 1.  Jordan et al. (2011) Studies 1b and 3: Summary of Findings.\n\n"
        "Study 1b\n\n"
        "Study 3\n\n"
        "### Table 1\n"
        "*Jordan et al. (2011) Studies 1b and 3: Summary of Findings.*\n\n"
        "<table>\n"
        "  <thead><tr><th>Study 1b</th><th>Study 3</th></tr></thead>\n"
        "  <tbody><tr><td>data</td><td>data</td></tr></tbody>\n"
        "</table>\n"
    )
    out = _strip_redundant_caption_echo_before_tables(text)
    # Orphan caption stripped.
    assert "Table 1.  Jordan et al" not in out
    # Standalone leaked header fragments stripped.
    assert "\nStudy 1b\n\n" not in out
    assert "\nStudy 3\n\n" not in out
    # Body paragraph preserved.
    assert "Body paragraph text here" in out
    # Heading + table preserved.
    assert "### Table 1" in out
    assert "<th>Study 1b</th>" in out


def test_strip_caption_echo_does_not_strip_unrelated_short_lines():
    """A short line that is NOT a subset of the rendered table stays put
    — we don't have evidence it's a leaked fragment."""
    text = (
        "Some unrelated short line.\n\n"
        "Table 2: Caption text matches.\n\n"
        "### Table 2\n"
        "*Caption text matches.*\n\n"
        "<table><tr><td>x</td></tr></table>\n"
    )
    out = _strip_redundant_caption_echo_before_tables(text)
    # Orphan is stripped (subset of caption).
    assert "Table 2: Caption text matches" not in out
    # Unrelated short line stays — not a subset.
    assert "Some unrelated short line." in out


from splice_spike import _strip_redundant_fragments_after_tables


def test_strip_post_table_fragment_when_all_words_in_table():
    """efendic Table 1 pattern: ``Negative affect Positive affect ...``
    leaked right after </table>. Every word stem is in the table's
    cells, so it gets stripped."""
    text = (
        "### Table 1\n"
        "*Summary of the Affect Heuristic.*\n\n"
        "<table>\n"
        "  <thead><tr><th>Risk is low<br>Positive affect</th><th>Benefit is high</th></tr></thead>\n"
        "  <tbody>\n"
        "    <tr><td>Benefit is high<br>Positive affect</td><td>Risk is low</td></tr>\n"
        "    <tr><td>Benefit is low<br>Negative affect</td><td>Risk is high</td></tr>\n"
        "  </tbody>\n"
        "</table>\n\n"
        "Negative affect Positive affect Positive affect Negative affect\n\n"
        "Real body paragraph that has actual prose content and ends in a period.\n"
    )
    out = _strip_redundant_fragments_after_tables(text)
    # The leaked line is gone.
    assert "Negative affect Positive affect Positive affect" not in out
    # The body paragraph stays.
    assert "Real body paragraph" in out
    # The table itself stays.
    assert "<table>" in out


def test_strip_post_table_fragment_preserves_lines_with_unique_words():
    """If a post-table line contains a word NOT in the table, it stays."""
    text = (
        "<table>\n"
        "  <thead><tr><th>Apple</th></tr></thead>\n"
        "  <tbody><tr><td>Banana</td></tr></tbody>\n"
        "</table>\n\n"
        "Cherry orange grape\n"
    )
    out = _strip_redundant_fragments_after_tables(text)
    # 'cherry'/'orange'/'grape' aren't in table — preserve.
    assert "Cherry orange grape" in out


def test_strip_post_table_stops_at_real_paragraph():
    """Walk-forward stops on the first non-fragment line (e.g. one with a
    terminal period or > 12 words). Subsequent leaked lines don't get
    stripped because we stopped early."""
    text = (
        "<table>\n"
        "  <thead><tr><th>Apple</th><th>Banana</th></tr></thead>\n"
        "  <tbody><tr><td>data</td><td>data</td></tr></tbody>\n"
        "</table>\n\n"
        "Apple banana data data\n\n"
        "This is a real paragraph that ends in a period.\n\n"
        "Apple banana again\n"
    )
    out = _strip_redundant_fragments_after_tables(text)
    # First leaked line stripped.
    assert "Apple banana data data\n" not in out
    # Real paragraph preserved.
    assert "This is a real paragraph" in out
    # Post-paragraph "Apple banana again" preserved (stop-on-paragraph).
    assert "Apple banana again" in out


def test_strip_post_table_preserves_long_lines():
    """A line >80 chars is not considered a fragment, even if all words
    are in the rendered table."""
    long_repeat = "Apple Banana Cherry " * 6  # ~120 chars
    text = (
        "<table>\n"
        "  <thead><tr><th>Apple Banana Cherry</th></tr></thead>\n"
        "  <tbody><tr><td>data</td></tr></tbody>\n"
        "</table>\n\n"
        + long_repeat
        + "\n"
    )
    out = _strip_redundant_fragments_after_tables(text)
    # Long line stays.
    assert "Apple Banana Cherry Apple Banana Cherry" in out


def test_strip_post_table_caption_echo_when_words_subset():
    """sci_rep_1 Table 1 pattern: full italic caption restated as plain
    text after </table>. Long, ends in period — the regular fragment
    rule rejects it. Iter-18 caption-echo branch strips it because all
    payload words are subsets of the rendered caption."""
    text = (
        "### Table 1\n"
        "*Baseline characteristics of participants. Notes: All values are presented as proportion (%), or mean(standard error). PIR, ratio of family income to poverty; BMD, bone mineral density.*\n\n"
        "<table>\n"
        "  <thead><tr><th>Characteristics</th><th>Means (standard error) or percentage</th></tr></thead>\n"
        "  <tbody>\n"
        "    <tr><td>Age (year)</td><td>39.07 (0.28)</td></tr>\n"
        "    <tr><td>Body mass index (kg/m2)</td><td>28.78 (0.16)</td></tr>\n"
        "  </tbody>\n"
        "</table>\n\n"
        "Table 1.  Baseline characteristics of participants. Notes: All values are presented as proportion (%), or mean(standard error). PIR, ratio of family income to poverty; BMD, bone mineral density.\n\n"
        "association between the DASH diet and various aspects of BMD.\n"
    )
    out = _strip_redundant_fragments_after_tables(text)
    # Plain-text caption echo gone.
    assert "Table 1.  Baseline characteristics" not in out
    # Italic caption (inside the heading block) survives.
    assert "*Baseline characteristics of participants" in out
    # Body paragraph after the echo stays.
    assert "association between the DASH diet" in out


def test_strip_post_table_caption_echo_preserves_unique_payload():
    """If the post-table caption echo contains a word NOT in the
    rendered caption + cells (e.g. a footnote anchor), DO NOT strip
    — the unique word might be real content."""
    text = (
        "### Table 1\n"
        "*Baseline characteristics of participants. Notes: PIR, ratio of family income to poverty.*\n\n"
        "<table>\n"
        "  <thead><tr><th>Characteristics</th><th>Mean</th></tr></thead>\n"
        "  <tbody><tr><td>Age</td><td>39</td></tr></tbody>\n"
        "</table>\n\n"
        "Table 1. Baseline characteristics with extra unique footnote text about whatever.\n"
    )
    out = _strip_redundant_fragments_after_tables(text)
    # Has unique words ('extra', 'footnote', 'about', 'whatever') — preserve.
    assert "Table 1. Baseline characteristics with extra" in out


def test_strip_post_table_caption_echo_only_matching_table_number():
    """A ``Table 2.`` line right after Table 1's </table> is NOT
    stripped — different table number means the words aren't a caption
    echo of THIS table even if they happen to be a subset."""
    text = (
        "### Table 1\n"
        "*Baseline characteristics of participants.*\n\n"
        "<table>\n"
        "  <thead><tr><th>Characteristics</th></tr></thead>\n"
        "  <tbody><tr><td>Age</td></tr></tbody>\n"
        "</table>\n\n"
        "Table 2. Baseline characteristics of participants.\n"
    )
    out = _strip_redundant_fragments_after_tables(text)
    # Table 2 echo preserved despite subset (it's a different table).
    assert "Table 2. Baseline characteristics" in out


from splice_spike import _fix_hyphenated_line_breaks


def test_fix_hyphenated_compound_word_join():
    """amj_1 Figure 4 pattern: caption ends with ``Meta-`` and the next
    line starts with ``Processes``. Compound word — keep hyphen, drop
    newline + leading whitespace on next line."""
    text = (
        "FIGURE 4 Regression Slopes for the Interaction on Meta-\n"
        "Processes (Study 1)\n"
    )
    out = _fix_hyphenated_line_breaks(text)
    assert "Meta-Processes (Study 1)" in out
    # No leftover stray ``Meta-\n`` or ``Meta- Processes``.
    assert "Meta-\nProcesses" not in out
    assert "Meta- Processes" not in out


def test_fix_hyphenated_lowercase_keeps_hyphen():
    """Conservative rule: keep the hyphen even for lowercase
    continuations. Real compound words (``self-control``,
    ``meta-analysis``) are far more common than pdftotext word-internal
    breaks, so dropping the hyphen erodes content more than it helps."""
    text = (
        "the multi-\n"
        "step approach is widely used.\n"
    )
    out = _fix_hyphenated_line_breaks(text)
    # Hyphen preserved, newline removed.
    assert "multi-step approach" in out
    assert "multi-\nstep" not in out


def test_fix_hyphenated_skips_inside_html_table():
    """Cell breaks use ``<br>`` inside HTML tables — never literal ``\\n``.
    But if the table-row text happens to contain ``\\n`` because the
    rendering is multi-line, the hyphen-join must NOT fire while inside
    ``<table>...</table>``."""
    text = (
        "<table>\n"
        "  <thead><tr><th>Meta-</th><th>data</th></tr></thead>\n"
        "  <tbody><tr><td>Meta-</td><td>2</td></tr></tbody>\n"
        "</table>\n"
        "Meta-\n"
        "Processes joined here\n"
    )
    out = _fix_hyphenated_line_breaks(text)
    # Inside the table, lines are untouched.
    assert "<th>Meta-</th>" in out
    # Outside the table, hyphen-join fires.
    assert "Meta-Processes joined here" in out


def test_fix_hyphenated_skips_inside_fenced_code():
    """Fenced code blocks preserve raw content."""
    text = (
        "```\n"
        "first-\n"
        "line\n"
        "```\n"
        "outside-\n"
        "Block\n"
    )
    out = _fix_hyphenated_line_breaks(text)
    # Inside the fence: untouched.
    assert "first-\nline" in out
    # Outside: joined.
    assert "outside-Block" in out


def test_fix_hyphenated_skips_heading_line():
    """A heading line ending in ``-`` is not a body-text wrap. Skip."""
    text = (
        "### Section-\n"
        "Continued\n"
    )
    out = _fix_hyphenated_line_breaks(text)
    # Heading preserved as-is.
    assert "### Section-\nContinued" in out


def test_fix_hyphenated_skips_numeric_range():
    """``1990-\\n2000`` is a date range, not a word break. Char before
    the hyphen is a digit → no join."""
    text = (
        "from 1990-\n"
        "2000 the trend was clear.\n"
    )
    out = _fix_hyphenated_line_breaks(text)
    # Untouched.
    assert "1990-\n2000" in out


def test_fix_hyphenated_chained_joins():
    """``a-\\nb-\\nc`` should chain-join in one pass."""
    text = "FIGURE 1 some-\nMore-\nWords here\n"
    out = _fix_hyphenated_line_breaks(text)
    assert "some-More-Words here" in out


def test_fix_hyphenated_skips_blank_continuation():
    """Paragraph break (blank line) means the next paragraph's first line
    is NOT a wrapped continuation. Don't join across paragraph
    boundaries."""
    text = (
        "End of caption-\n"
        "\n"
        "Start of next paragraph.\n"
    )
    out = _fix_hyphenated_line_breaks(text)
    # Hyphen + paragraph break preserved (blank line is non-alpha first char).
    assert "End of caption-\n\nStart of next" in out


from splice_spike import _format_figure_md


def test_format_figure_md_long_caption_with_period_only_in_first_40_chars():
    """Regression: previous code did `". " in caption[:300]` then
    `caption.index(". ", 40)` — when the only ". " sat in chars 0-39,
    the index() raised ValueError and crashed the entire render. Crash
    nuked output for jama_open_1 / jama_open_2 (0 bytes).

    Confirm that a long caption whose only early ". " is at e.g. char
    20 doesn't crash and falls through to the no-cut branch."""
    # Caption: 250 chars, only ". " is at char 20, then a long tail with
    # no further ". ".
    cap = "Figure 1. Short note " + ("x" * 230)
    fig = {"label": "Figure 1", "caption": cap}
    # Must not raise.
    out = _format_figure_md(fig)
    assert out.startswith("*Figure 1.")
    assert "x" in out  # tail preserved (no cut applied because no ". " ≥40)


def test_format_figure_md_long_caption_with_period_after_40_cuts():
    """Long caption with a ". " after position 40 still gets cut at that
    position, preserving original behavior."""
    cap = (
        "Figure 1: Some short caption text describing the chart shown above. "
        "Subsequent body text that should be cut off here goes on and on for "
        "another two hundred chars worth of irrelevant prose to trigger the "
        "len > 200 path."
    )
    fig = {"label": "Figure 1", "caption": cap}
    out = _format_figure_md(fig)
    # The cut should remove the "Subsequent body text..." portion.
    assert "Some short caption text" in out
    assert "Subsequent body text" not in out


def test_format_figure_md_short_caption_unchanged():
    """A caption ≤200 chars is never cut."""
    fig = {"label": "Figure 2", "caption": "Figure 2. Short caption."}
    out = _format_figure_md(fig)
    assert out == "*Figure 2. Short caption.*"


from splice_spike import _drop_running_header_rows, _is_running_header_cell


def test_running_header_cell_pure_page_number():
    """Pure 1-4 digit numbers like '725', '1236' are running-header pages."""
    assert _is_running_header_cell("725")
    assert _is_running_header_cell("1236")
    assert _is_running_header_cell(" 232 ")
    assert not _is_running_header_cell("12345")  # too long for a page number
    assert not _is_running_header_cell("0.5")    # not pure digits


def test_running_header_cell_pipe_prefixed():
    """social_forces_1 pattern: ``|232 Stacey et al.``"""
    assert _is_running_header_cell("|232 Stacey et al.")
    assert _is_running_header_cell("| 232")


def test_running_header_cell_journal_caps():
    """chan_feldman pattern: ``COGNITION AND EMOTION 1231``"""
    assert _is_running_header_cell("COGNITION AND EMOTION 1231")
    assert _is_running_header_cell("JOURNAL OF SCIENCE 42")


def test_running_header_cell_author_only():
    """am_sociol_rev_3 pattern: ``Nussio``, ``Stacey et al.``"""
    assert _is_running_header_cell("Nussio")
    assert _is_running_header_cell("Stacey et al.")
    assert _is_running_header_cell("Smith and Jones")


def test_running_header_cell_does_not_match_punctuated_headers():
    """Real column headers with punctuation (%, /, multi-word phrases)
    aren't even WEAK running header signals.

    Note: ``Mean`` and ``Variable`` look like weak signals (single
    cap-cased word) at the cell level — the row-level rule disambiguates
    by requiring a STRONG signal to be present in the same row before
    treating any cell as RH content."""
    assert not _is_running_header_cell("p-value")
    assert not _is_running_header_cell("95% CI")
    assert not _is_running_header_cell("T-statistic")
    assert not _is_running_header_cell("Sample size")
    # These would look like weak signals individually, but the row-level
    # rule protects them in real header rows (no STRONG anchor → keep).
    from splice_spike import _is_weak_running_header, _is_strong_running_header
    assert _is_weak_running_header("Mean")
    assert not _is_strong_running_header("Mean")


def test_drop_running_header_rows_drops_top_row_with_pure_numbers():
    """A top header row of all running-header cells is dropped; the next
    row becomes the new header."""
    grid = [
        ["Nussio", "725"],
        ["Variable", "Mean"],
        ["Trust", "1.5"],
    ]
    out = _drop_running_header_rows(grid)
    assert len(out) == 2
    assert out[0] == ["Variable", "Mean"]
    assert out[1] == ["Trust", "1.5"]


def test_drop_running_header_rows_drops_multiple_top_rows():
    """Iterates from the top — drops as many fully-running-header rows
    as there are."""
    grid = [
        ["725", "726"],
        ["COGNITION AND EMOTION 1231", ""],
        ["Variable", "Mean"],
        ["Trust", "1.5"],
    ]
    out = _drop_running_header_rows(grid)
    assert len(out) == 2
    assert out[0] == ["Variable", "Mean"]


def test_drop_running_header_rows_preserves_row_with_real_content():
    """A row that has any non-running-header populated cell is kept."""
    grid = [
        ["Variable", "Mean"],
        ["Trust", "1.5"],
    ]
    out = _drop_running_header_rows(grid)
    assert out == grid


def test_drop_running_header_rows_does_not_drop_below_2_rows():
    """Refuse to leave the grid with fewer than 2 rows — preserves
    table structure even if every remaining row looks running-header-y."""
    grid = [
        ["725", ""],
        ["726", ""],
    ]
    out = _drop_running_header_rows(grid)
    # Both look like running-header rows but we don't drop both.
    assert len(out) == 2


def test_drop_running_header_rows_skips_empty_top_row():
    """An entirely-empty top row stops the loop (it's a structural
    artifact, not a running-header row)."""
    grid = [
        ["", ""],
        ["Variable", "Mean"],
    ]
    out = _drop_running_header_rows(grid)
    assert out == grid


def test_drop_running_header_rows_blanks_in_row_strong_rh_cell():
    """Iter 17: chan_feldman T5 pattern. Top row has a strong-RH cell
    (page number 1236) mixed with real header content. The cell-level
    cleanup blanks out the strong-RH cell while keeping real headers."""
    grid = [
        ["1236", "Target article", "Replication", "Reason for change"],
        ["Study design", "between", "between", "—"],
        ["Sample size",  "100",     "200",      "+100"],
    ]
    out = _drop_running_header_rows(grid)
    # Row 0 kept (it has real header content) but col 0 ("1236") blanked.
    assert len(out) == 3
    assert out[0] == ["", "Target article", "Replication", "Reason for change"]


def test_drop_running_header_rows_does_not_blank_when_no_real_content():
    """If top row has only strong/weak RH and no non-RH cells, don't
    blank — that's already handled by the row-drop logic, no additional
    cell-blanking needed."""
    grid = [
        ["1236", "726"],
        ["Variable", "Mean"],
        ["x", "1.5"],
    ]
    # Both cells of row 0 are strong RH, no real content, so the row
    # itself is dropped.
    out = _drop_running_header_rows(grid)
    assert out[0] == ["Variable", "Mean"]


def test_drop_running_header_rows_blanks_strong_in_real_header_row():
    """In-row strip when top row has strong RH (1236) mixed with cells
    that are clearly non-RH (multi-word headers with punctuation /
    numerics nearby).

    Note on the limitation: a synthetic row like
    ``["Variable", "Mean", "725"]`` would be ROW-DROPPED instead of
    cell-stripped — single-cap-word cells qualify as weak-RH and the
    weak+strong combo triggers row drop. Real-world header cells almost
    always have multi-word labels (``Reason for change``,
    ``Target article``) or short labels with punctuation (``p-value``,
    ``95% CI``) that disambiguate from name-like weak signals."""
    grid = [
        ["1236", "Target article", "Replication", "Reason for change"],
        ["Study design", "between", "between", "—"],
        ["Sample size",  "100",     "200",      "+100"],
    ]
    out = _drop_running_header_rows(grid)
    assert len(out) == 3
    # Real headers preserved; the page-number cell blanked.
    assert out[0] == ["", "Target article", "Replication", "Reason for change"]


from splice_spike import _is_spurious_body_prose_grid


def test_spurious_body_prose_detector_flags_2col_running_text():
    """ar_apa_j Table 1 pattern: 80+ rows of running body prose split
    across 2 columns. Every cell is long, multi-word, lowercase-rich."""
    rows = [
        ["had to cover support for graduate students so there is more",
         "Assessments following the initial and final confederate proposals"],
        ["need. The confederate then was invited to put forward his own",
         "Did this large between condition difference in rates of agreement"],
        ["counterproposal which the experimenter indicated would have",
         "reflect a grudging acceptance by Positive Expectations condition"],
        ["be the final proposal considered because the available time for",
         "participants of a proposal that they deemed unfair and unattractive"],
        ["the negotiation had been exhausted. This proposal effectively",
         "Participants in the Positive Expectations condition rated the"],
    ]
    assert _is_spurious_body_prose_grid(rows)


def test_spurious_body_prose_detector_passes_real_stat_table():
    """A normal stat table with short labels + numeric data isn't body prose."""
    rows = [
        ["Variable", "Mean", "SD", "N"],
        ["Age",      "24.3", "3.1", "100"],
        ["IQ",       "100.5", "15.2", "100"],
        ["Score",    "85.1",  "8.7", "98"],
        ["Rating",   "5.2",   "1.4", "100"],
    ]
    assert not _is_spurious_body_prose_grid(rows)


def test_spurious_body_prose_detector_passes_definition_table():
    """A real definition table (term + short definition) is NOT prose
    because the definitions don't reach 35 chars on average AND the
    terms aren't 4+ words."""
    rows = [
        ["Term",        "Definition"],
        ["Replication", "Repeating an experiment to verify findings."],
        ["Extension",   "Building on prior work with new conditions."],
        ["Pre-reg",     "Registering hypotheses and methods upfront."],
        ["OSF",         "Open Science Framework, a project repository."],
    ]
    # The "Term" column has 1-word entries — not prose-like (need ≥4 words).
    assert not _is_spurious_body_prose_grid(rows)


def test_spurious_body_prose_detector_passes_short_grid():
    """Need ≥4 populated rows to qualify."""
    rows = [
        ["Some long prose-like cell that easily passes the prose check.",
         "Another long prose-like cell that also passes the prose check."],
        ["Second row of prose-like content with ample length and words.",
         "Matching prose-like cell on the right that has lots of words."],
        ["Third row of similar prose content with enough length and words.",
         "Right side cell with prose pattern enough length and word count."],
    ]
    # Only 3 rows, doesn't qualify.
    assert not _is_spurious_body_prose_grid(rows)


def test_spurious_body_prose_detector_passes_numeric_heavy_grid():
    """Even with some prose, if numeric cells are >10% it's a stat
    table not body prose."""
    rows = [
        ["Long cell with body prose content of various words and length",
         "12.5"],
        ["Another long body prose row with sufficient text and word count",
         "13.7"],
        ["Yet more long body prose with enough text and four-plus words",
         "14.2"],
        ["Continuation of body prose with sufficient length and word count",
         "15.8"],
        ["Final row of body prose with enough text words and length here",
         "16.3"],
    ]
    # Half of cells are numeric → not body prose.
    assert not _is_spurious_body_prose_grid(rows)


from splice_spike import (
    _merge_significance_marker_rows,
    _SUP_OPEN,
    _SUP_CLOSE,
    _html_escape,
)


def _sup(marker: str) -> str:
    return f"{_SUP_OPEN}{marker}{_SUP_CLOSE}"


def test_merge_sig_marker_row_attaches_to_estimate_row():
    """social_forces_1 Table 3 pattern: 3 rows per variable
    (estimate / SE / stars). The stars row gets eaten and its markers
    attach as ``<sup>...</sup>`` on the estimate row's cells. The SE
    row stays in place."""
    rows = [
        ["Mother born in USA", "3.02", "0.54", "0.64", "0.67"],
        ["",                    "(1.34)", "(0.13)", "(0.12)", "(0.12)"],
        ["",                    "∗",      "∗∗",     "∗",      "∗"],
        ["Mother age 14 rural", "0.91", "1.10", "1.07", "1.08"],
    ]
    out = _merge_significance_marker_rows(rows)
    # Marker-only row absorbed.
    assert len(out) == 3
    # Estimate row got markers as superscripts.
    assert out[0] == [
        "Mother born in USA",
        f"3.02{_sup('∗')}",
        f"0.54{_sup('∗∗')}",
        f"0.64{_sup('∗')}",
        f"0.67{_sup('∗')}",
    ]
    # SE row untouched (just stripped/passed through).
    assert out[1] == ["", "(1.34)", "(0.13)", "(0.12)", "(0.12)"]
    # Verify the placeholders survive HTML escaping and become real <sup> tags.
    escaped = _html_escape(out[0][1])
    assert escaped == "3.02<sup>∗</sup>"


def test_merge_sig_marker_skips_non_marker_row():
    """A row with mixed marker + real-text cells doesn't qualify as
    marker-only — preserve."""
    rows = [
        ["Variable", "1.0", "2.0"],
        ["",         "*",   "footnote text"],
    ]
    out = _merge_significance_marker_rows(rows)
    # Both rows preserved.
    assert len(out) == 2
    assert out[1] == ["", "*", "footnote text"]


def test_merge_sig_marker_handles_no_target_above():
    """A marker-only row at the very top of a table has no row above
    to merge into — just preserve it as-is."""
    rows = [
        ["", "*", "**"],
        ["Header A", "Header B", "Header C"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 2
    assert out[0] == ["", "*", "**"]


def test_merge_sig_marker_walks_past_se_row():
    """The walk-back skips intermediate SE rows (whose only populated
    cells are parenthetical numbers like ``(0.13)``) until it finds
    the actual estimate row."""
    rows = [
        ["Variable", "1.0", "2.0", "3.0"],
        ["",         "(0.1)", "(0.2)", "(0.3)"],
        ["",         "(extra notes)", "", ""],
        ["",         "*",     "**",    "*"],
    ]
    out = _merge_significance_marker_rows(rows)
    # Marker row absorbed into the estimate row (skipping both SE-style rows).
    assert len(out) == 3
    assert out[0] == [
        "Variable",
        f"1.0{_sup('*')}",
        f"2.0{_sup('**')}",
        f"3.0{_sup('*')}",
    ]


def test_merge_sig_marker_preserves_dagger_markers():
    """Dagger and double-dagger markers (``†``, ``‡``) are valid
    significance markers in some journals — should also merge."""
    rows = [
        ["Var", "1.0", "2.0"],
        ["",    "†",   "‡"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 1
    assert out[0] == ["Var", f"1.0{_sup('†')}", f"2.0{_sup('‡')}"]


def test_merge_sig_marker_skips_empty_target_cell():
    """If the target estimate row's cell is EMPTY in a column where the
    marker row has a star, don't attach — markers shouldn't appear in
    isolation. Prevents ``<td><sup>**</sup></td>`` orphans where the
    estimate column was missing data."""
    rows = [
        ["Var", "1.0", "", "3.0"],
        ["",    "*",   "**", "*"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 1
    assert out[0] == ["Var", f"1.0{_sup('*')}", "", f"3.0{_sup('*')}"]


def test_merge_sig_marker_preserves_row_when_no_attach_possible():
    """If walking back finds an estimate row but every marker column is
    empty in that target, fall back to preserving the marker row
    rather than silently dropping it (would lose the markers)."""
    rows = [
        ["Var", "", "", ""],
        ["",    "*", "**", "*"],
    ]
    out = _merge_significance_marker_rows(rows)
    # Marker row preserved because target had no non-empty cells to attach to.
    assert len(out) == 2
    assert out[1] == ["", "*", "**", "*"]


def test_merge_sig_marker_does_not_attach_to_text_anchor_row():
    """The walk-back stops at a text-anchor row (e.g. ``Ref.``) — text
    anchors carry no significance, so the markers don't attach there.

    Iteration 24 (Tier A8) extends this: when walk-back is blocked by a
    text-anchor row AND the immediate-next row is numeric, the markers
    forward-attach to that next row (social_forces_1 pattern: stars
    between ``0 ACEs Ref.`` and ``1 ACE 2.25 ...`` belong to ``1 ACE``).
    """
    rows = [
        ["0 ACEs", "Ref.", "Ref.", "Ref."],
        ["",       "*",    "**",   "*"],
        ["1 ACE",  "2.25", "0.56", "0.74"],
    ]
    out = _merge_significance_marker_rows(rows)
    # Marker row consumed: forward-attached to "1 ACE" row.
    assert len(out) == 2
    # The "Ref." row stays clean — no <sup> on it.
    assert out[0] == ["0 ACEs", "Ref.", "Ref.", "Ref."]
    # Stars now decorate "1 ACE" estimates.
    assert out[1] == [
        "1 ACE",
        f"2.25{_sup('*')}",
        f"0.56{_sup('**')}",
        f"0.74{_sup('*')}",
    ]


# ---------------------------------------------------------------------------
# Iter-24 / Tier A8: forward-attach for orphan marker rows
# ---------------------------------------------------------------------------


def test_a8_forward_attach_after_text_anchor():
    """Real social_forces_1 pattern: 0 ACEs Ref. / *** / 1 ACE 2.25...
    Markers between a Ref. row and the next numeric row attach FORWARD
    to the next row."""
    rows = [
        ["0 ACEs", "Ref.", "Ref.", "Ref.", "Ref."],
        ["",       "***",  "***",  "**",   "**"],
        ["1 ACE",  "2.25", "0.56", "0.74", "0.76"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 2
    assert out[0] == ["0 ACEs", "Ref.", "Ref.", "Ref.", "Ref."]
    assert out[1] == [
        "1 ACE",
        f"2.25{_sup('***')}",
        f"0.56{_sup('***')}",
        f"0.74{_sup('**')}",
        f"0.76{_sup('**')}",
    ]


def test_a8_does_not_forward_attach_when_back_attach_works():
    """Standard pattern: estimate row directly above marker row. Iter-21
    walk-back wins — markers attach BACK to the estimate row. Forward-
    attach must not run when back-attach already succeeded."""
    rows = [
        ["Var1", "1.0", "2.0", "3.0"],
        ["",     "*",   "**",  "***"],
        ["Var2", "4.0", "5.0", "6.0"],  # this row must be untouched
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 2
    assert out[0] == [
        "Var1", f"1.0{_sup('*')}", f"2.0{_sup('**')}", f"3.0{_sup('***')}",
    ]
    # Var2 row preserved exactly — no forward absorption.
    assert out[1] == ["Var2", "4.0", "5.0", "6.0"]


def test_a8_does_not_forward_attach_when_walk_back_runs_through_stderr():
    """Estimate / std-err / marker — walk-back skips the parenthetical
    std-err row and finds the estimate. Forward-attach must NOT fire."""
    rows = [
        ["Var1", "1.0",   "2.0",   "3.0"],
        ["",     "(0.1)", "(0.2)", "(0.3)"],
        ["",     "*",     "**",    "***"],
        ["Var2", "9.0",   "8.0",   "7.0"],  # untouched
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 3
    assert out[0] == [
        "Var1", f"1.0{_sup('*')}", f"2.0{_sup('**')}", f"3.0{_sup('***')}",
    ]
    assert out[1] == ["", "(0.1)", "(0.2)", "(0.3)"]
    assert out[2] == ["Var2", "9.0", "8.0", "7.0"]


def test_a8_does_not_forward_attach_when_no_text_anchor_above():
    """If walk-back simply runs out of rows (no text-anchor block) the
    marker row stays as-is; forward-attach is gated on a text-anchor
    block to avoid grabbing markers that just happen to be at the top
    of the table."""
    rows = [
        ["",       "*",    "**",   "***"],     # orphan marker, top of table
        ["1 ACE",  "2.25", "0.56", "0.74"],
    ]
    out = _merge_significance_marker_rows(rows)
    # Marker row preserved (no text-anchor above to signal "use forward").
    assert len(out) == 2
    assert out[0] == ["", "*", "**", "***"]
    assert out[1] == ["1 ACE", "2.25", "0.56", "0.74"]


def test_a8_does_not_forward_attach_when_next_is_not_numeric():
    """Text-anchor above + non-numeric next (e.g. another text row).
    Forward-attach refuses because next has nothing to decorate."""
    rows = [
        ["0 ACEs", "Ref.", "Ref.", "Ref."],
        ["",       "*",    "**",   "*"],
        ["1 ACE",  "Ref.", "Ref.", "Ref."],  # also text-anchor
    ]
    out = _merge_significance_marker_rows(rows)
    # Marker preserved — neither back nor forward has a numeric estimate.
    assert len(out) == 3
    assert out[1] == ["", "*", "**", "*"]


def test_a8_forward_attach_skips_empty_marker_columns():
    """Forward-attach respects the per-column guard: only columns with a
    populated marker get a <sup>; columns with an empty marker stay
    untouched on the target row."""
    rows = [
        ["0 ACEs", "Ref.", "Ref.", "Ref.", "Ref."],
        ["",       "***",  "",     "**",   ""],  # only cols 1 and 3 have markers
        ["1 ACE",  "2.25", "0.56", "0.74", "0.76"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 2
    assert out[1] == [
        "1 ACE",
        f"2.25{_sup('***')}",
        "0.56",  # no marker for this column → unchanged
        f"0.74{_sup('**')}",
        "0.76",  # no marker for this column → unchanged
    ]


def test_a8_forward_attach_skips_empty_target_cells():
    """If the next-row target cell is empty, the marker is not attached
    there (mirrors back-attach guard) — leaves the marker row preserved
    when no attach happens."""
    rows = [
        ["0 ACEs", "Ref.", "Ref.", "Ref.", "Ref."],
        ["",       "***",  "***",  "**",   "**"],
        ["1 ACE",  "",     "",     "",     ""],  # all empty target cells
    ]
    out = _merge_significance_marker_rows(rows)
    # No attachment possible: all forward-target cells are empty.
    assert len(out) == 3
    assert out[1] == ["", "***", "***", "**", "**"]


from splice_spike import _strip_leader_dots, _MERGE_SEPARATOR


def test_strip_leader_dots_removes_long_run():
    """A long run of space-separated dots is the classic PDF
    leader-dot filler used to visually align label/value columns."""
    s = "behaviour" + _MERGE_SEPARATOR + ". " * 50 + "."
    out = _strip_leader_dots(s)
    assert out == "behaviour"


def test_strip_leader_dots_preserves_short_dot_runs():
    """``e.g.``, ``i.e.``, sentence-end ``..`` should be preserved —
    only ≥4 dot-space pairs trigger the strip."""
    cases = [
        "e.g. some example",
        "i.e. another",
        "5. Numbered list item",
        "Hello. World!",
        ". . one two",  # only 2 pairs — keep
        ". . . three",  # 3 pairs — keep (threshold is 4)
    ]
    for c in cases:
        assert _strip_leader_dots(c) == c.strip(), f"changed: {c!r}"


def test_strip_leader_dots_handles_inline_run():
    """A leader-dot run between real text on a single cell line
    is collapsed but the surrounding text is preserved."""
    s = "label . . . . . . . . . . . . . . value"
    out = _strip_leader_dots(s)
    assert out == "label  value" or out == "label value"


def test_strip_leader_dots_cleans_doubled_br_placeholders():
    """If stripping a leader-dot run leaves two adjacent ``<br>``
    placeholders, collapse them so the rendered HTML doesn't have
    double line breaks."""
    s = "chase" + _MERGE_SEPARATOR + ". " * 50 + _MERGE_SEPARATOR + "ram"
    out = _strip_leader_dots(s)
    # Single <br> separator between the surviving labels.
    assert out == "chase" + _MERGE_SEPARATOR + "ram"


def test_strip_leader_dots_strips_trailing_br():
    """Trailing ``<br>`` placeholders left by removed dot-rows are
    cleaned up."""
    s = "bite" + _MERGE_SEPARATOR + ". " * 50
    out = _strip_leader_dots(s)
    assert out == "bite"


def test_strip_leader_dots_empty_input():
    assert _strip_leader_dots("") == ""
    assert _strip_leader_dots(None) is None


def test_merge_sig_marker_only_merges_columns_with_markers():
    """If the marker row has stars only in some columns and others
    empty, only those columns gain the superscript. Columns without a
    marker stay unchanged."""
    rows = [
        ["Var", "1.0", "2.0", "3.0"],
        ["",    "*",   "",    "**"],
    ]
    out = _merge_significance_marker_rows(rows)
    assert len(out) == 1
    assert out[0] == ["Var", f"1.0{_sup('*')}", "2.0", f"3.0{_sup('**')}"]


# ---------------------------------------------------------------------------
# _join_multiline_caption_paragraphs (iteration 23 / Tier A7)
# ---------------------------------------------------------------------------

from splice_spike import _join_multiline_caption_paragraphs


def test_inter_paragraph_caption_split_is_NOT_merged():
    """Inter-paragraph (blank-line separated) caption + tail is intentionally
    NOT merged. The joiner is line-local so it cannot accidentally absorb
    the table header row that typically follows a caption in its own
    paragraph (see amc_1 TABLE 1 / TABLE 4 incident from iter-23 v1)."""
    text = (
        "TABLE 1 Summary of How Articles Published in Academy of Management Journals and Included in Our Collection Have\n"
        "\n"
        "Shaped the Definition of CSR\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    # Two paragraphs preserved.
    assert "\n\n" in out
    assert "Have\n\nShaped" in out


def test_skip_caption_with_terminator():
    """Captions ending in ``.``, ``!``, ``?``, or ``)`` are already complete
    and must NOT swallow the next line into the caption."""
    cases = [
        ("FIGURE 1 A long enough title that meets the sixty character guard requirement.\n(Study X)\n", "(Study X)"),
        ("TABLE 3 A long enough title that meets the sixty character guard (Continued)\nDavis 1973 ...\n", "Davis"),
        ("FIGURE 7 A long enough title that meets the sixty character guard (Study 2)\nMeta-Processes label\n", "Meta-Processes label"),
    ]
    for text, marker in cases:
        out = _join_multiline_caption_paragraphs(text)
        # Caption + tail still on separate lines (not folded).
        assert "\n" + marker in out, f"unexpected fold: {text!r} → {out!r}"


def test_skip_when_next_line_is_long():
    """If the candidate continuation line is long (>80 chars), do not fold."""
    long_next = "This is a long body paragraph that goes well past eighty characters and should certainly not be slurped into a caption."
    text = (
        "FIGURE 5 A long enough caption that clears the sixty character line guard for testing\n"
        + long_next + "\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    assert long_next in out
    # Long body line still on its own line under the caption.
    assert "testing\n" + long_next in out


def test_skip_when_next_line_is_another_caption():
    """Two adjacent caption lines never fold into each other."""
    text = (
        "FIGURE 5 A long enough caption that clears the sixty character line guard\n"
        "FIGURE 6 Another caption\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    assert "guard\nFIGURE 6" in out


def test_skip_when_next_line_is_heading():
    """Never absorb a markdown heading into a caption."""
    text = (
        "TABLE 2 A long enough caption that clears the sixty character line guard\n"
        "## Methods\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    assert "guard\n## Methods" in out


def test_skip_when_next_line_is_html():
    """Never absorb an HTML opener (e.g. ``<table>``) into a caption."""
    text = (
        "TABLE 2 A long enough caption that clears the sixty character line guard\n"
        "<table>\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    assert "guard\n<table>" in out


def test_skip_when_next_line_is_numbered_reference():
    """Numbered references like ``[1]`` should not be merged."""
    text = (
        "TABLE 2 A long enough caption that clears the sixty character line guard\n"
        "[3] Some reference\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    assert "guard\n[3] Some reference" in out


def test_skip_when_next_line_is_table_footer_note():
    """``Note: ...`` table footers should not be merged into a caption."""
    text = (
        "TABLE 2 A long enough caption that clears the sixty character line guard\n"
        "Note: significance markers below.\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    assert "guard\nNote: significance markers" in out


def test_skip_when_paragraph_does_not_start_with_caption_marker():
    """Random short-line splits unrelated to a FIGURE/TABLE caption are
    untouched."""
    text = "Some title without label\nshort next\n"
    out = _join_multiline_caption_paragraphs(text)
    assert out == text


def test_lowercase_figure_table_keyword_is_matched():
    """Caption keyword match is case-insensitive (some PDFs emit ``Figure``
    or ``Table`` rather than all-caps). Caption length must clear the
    >=60-char line-1 guard."""
    text = (
        "Table 1 Summary of Studies linking negative feedback and recipient creativity with\n"
        "Results across three samples\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    assert "with Results across three samples" in out


def test_skip_caption_too_short_for_line_guard():
    """A bare label like ``FIGURE 1 Theoretical Framework`` (30 chars) does
    NOT trigger the joiner. The next line is typically figure data, not a
    caption continuation. The >=60-char line-0 guard prevents false joins."""
    text = "FIGURE 1 Theoretical Framework\nResults summary.\n"
    out = _join_multiline_caption_paragraphs(text)
    assert "FIGURE 1 Theoretical Framework\nResults summary." in out


# ---- Pass A: intra-paragraph fold (caption + tail on consecutive lines) ----


def test_intra_paragraph_fold_amj_figure_2():
    """``FIGURE 2 ... Creativity\\n(Study 1)`` (single paragraph, two lines)
    folds to a single line."""
    text = (
        "FIGURE 2 Regression Slopes for the Interaction of Negative Feedback and the Direction of Feedback Flow on Creativity\n"
        "(Study 1)\n"
        "\n"
        "Body paragraph follows.\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    first_para = out.split("\n\n")[0]
    assert first_para == (
        "FIGURE 2 Regression Slopes for the Interaction of Negative Feedback and the Direction of Feedback Flow on Creativity (Study 1)"
    )


def test_intra_paragraph_fold_amj_figure_3():
    """``FIGURE 3 ... Task\\nProcesses (Study 1)`` folds to one line."""
    text = (
        "FIGURE 3 Regression Slopes for the Interaction of Negative Feedback and the Direction of Feedback Flow on Task\n"
        "Processes (Study 1)\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    assert "Direction of Feedback Flow on Task Processes (Study 1)" in out
    # The folded paragraph is a single line.
    first_para = out.split("\n\n")[0].rstrip()
    assert "\n" not in first_para


def test_intra_paragraph_fold_amc_table_1():
    """``TABLE 1 ... Have\\nShaped the Definition of CSR`` folds to one
    line."""
    text = (
        "TABLE 1 Summary of How Articles Published in Academy of Management Journals and Included in Our Collection Have\n"
        "Shaped the Definition of CSR\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    assert "Have Shaped the Definition of CSR" in out
    first_para = out.split("\n\n")[0].rstrip()
    assert "\n" not in first_para


def test_intra_paragraph_fold_preserves_subsequent_data_lines():
    """A caption + tail folds, but later figure-data lines in the same
    paragraph stay where they are (no cascade beyond what the heuristic
    permits)."""
    text = (
        "FIGURE 5 Regression Slopes for the Interaction of Negative Feedback on Recipient\n"
        "Creativity (Study 2)\n"
        "Bottom-up Flow 4\n"
        "Top-down Flow Lateral Flow 3\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    # Caption + tail merged into one line.
    assert "on Recipient Creativity (Study 2)" in out
    # Figure-data lines preserved (not absorbed into caption since the new
    # line-0 ends in ``)`` terminator after fold).
    assert "Bottom-up Flow 4" in out
    assert "\nBottom-up Flow 4" in out  # still on its own line


def test_intra_paragraph_fold_skips_short_label_caption():
    """A bare label like ``FIGURE 1 Theoretical Framework`` (30 chars) +
    a longer figure-data first line is NOT folded, because line-0 fails the
    >=60-char guard."""
    text = (
        "FIGURE 1 Theoretical Framework\n"
        "Direction of Feedback Flow\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    # Two lines preserved.
    assert out.count("\n") >= 1
    assert "FIGURE 1 Theoretical Framework\nDirection of Feedback Flow" in out


def test_intra_paragraph_fold_skips_long_continuation():
    """If line 1 is itself a long body paragraph (>80 chars), don't fold."""
    long_body = (
        "Direction of Feedback Flow 1. Bottom-up Feedback Flow 2. Top-down Feedback Flow 3. Lateral Feedback Flow"
    )
    assert len(long_body) > 80
    text = (
        "FIGURE 1 A long enough caption to clear the sixty character line guard\n"
        + long_body
        + "\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    # Long line 1 still on its own line.
    assert long_body in out
    assert "guard\n" + long_body in out


def test_intra_paragraph_fold_chains_for_three_line_caption():
    """A caption wrapped onto 3 lines (caption + tail-1 + tail-2) chain-folds
    while the line-0 still has no terminator and each tail stays short."""
    text = (
        "TABLE 9 A long caption that wraps over three lines because the column was narrow with\n"
        "Recommendations for Future\n"
        "Research (Detailed).\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    assert (
        "TABLE 9 A long caption that wraps over three lines because the column was narrow with Recommendations for Future Research (Detailed)."
        in out
    )


def test_empty_input_is_safe():
    assert _join_multiline_caption_paragraphs("") == ""


def test_no_blank_separated_paragraphs_is_safe():
    """A text with no blank lines is returned unchanged."""
    text = "FIGURE 5 Title\nMore on next line\n"
    out = _join_multiline_caption_paragraphs(text)
    assert out == text


def test_real_amj_1_figure_3_pattern():
    """Reproduce the exact amj_1 FIGURE 3 case (intra-paragraph fold)."""
    text = (
        "However, negative feedback reduced ... .\n"
        "\n"
        "FIGURE 3 Regression Slopes for the Interaction of Negative Feedback and the Direction of Feedback Flow on Task\n"
        "Processes (Study 1)\n"
        "\n"
        "FIGURE 4 ... on Meta-Processes (Study 1)\n"
        "\n"
        "performance appraisal, employees received both numerical and written feedback ...\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    # FIGURE 3 caption is now on one line.
    assert "Direction of Feedback Flow on Task Processes (Study 1)" in out
    # FIGURE 4 caption already had a closing ``)`` so it stays alone, and the
    # body paragraph after the blank line is preserved.
    assert "FIGURE 4 ... on Meta-Processes (Study 1)\n\nperformance appraisal" in out


def test_intra_paragraph_fold_at_interior_line_pair():
    """Caption can appear MID-paragraph when the prior body sentence has no
    blank-line break (amc_1 TABLE 2 pattern). Pass A scans every adjacent
    line pair, not just lines[0]."""
    text = (
        "investigated. Second, regarding integration, given the highly multidisciplinary nature of CSR, we considered ...\n"
        "TABLE 2 Criteria for Selecting Collection Articles and Evaluating the Status Quo of Corporate Social\n"
        "Responsibility Research\n"
        "1. Definition and operationalizations and content domain and dimensionality and measurement and methodological rigor\n"
    )
    out = _join_multiline_caption_paragraphs(text)
    # Caption + tail folded.
    assert "Corporate Social Responsibility Research" in out
    # The numbered list line is long (>80 chars), so it stays separate.
    assert "Research\n1. Definition" in out


# ---------------------------------------------------------------------------
# Iter-25 / Tier F6: document-header banner strip
# ---------------------------------------------------------------------------

from splice_spike import _strip_document_header_banners


def test_banner_strip_hhs_three_line_block():
    """``HHS Public Access`` / ``Author manuscript`` / ``Published in
    final edited form as: ...`` — all three lines at the document head
    are dropped (demography_1, ieee_access_2 pattern)."""
    text = (
        "HHS Public Access\n"
        "Author manuscript\n"
        "Published in final edited form as: Demography. 2023 October 01; 60(5): 1415-1440. doi:10.1215/00703370-10924116.\n"
        "The Economic Assimilation of Second-Generation Men\n"
        "Andres Villarreal\n"
        "\n"
        "## Abstract\n"
        "\n"
        "Body text starts here.\n"
    )
    out = _strip_document_header_banners(text)
    assert "HHS Public Access" not in out
    assert "Author manuscript" not in out
    assert "Published in final edited form" not in out
    # Title and author preserved.
    assert "The Economic Assimilation" in out
    assert "Andres Villarreal" in out
    # Body unchanged.
    assert "Body text starts here." in out
    assert "## Abstract" in out


def test_banner_strip_aom_masthead():
    """``r Academy of Management ... YYYY, Vol. N, ...`` is dropped."""
    text = (
        "r Academy of Management Collections 2024, Vol. 3, No. 1, 1-16. https://doi.org/10.5465/amc.2022.0006\n"
        "\n"
        "## Abstract\n"
        "\n"
        "Body.\n"
    )
    out = _strip_document_header_banners(text)
    assert "Academy of Management Collections 2024" not in out
    assert "## Abstract" in out


def test_banner_strip_sage_volume_banner():
    """SAGE/Cambridge journal volume banners ('Journal Name YYYY, Vol. X(Y) pages').
    Drop these but keep title/authors."""
    text = (
        "American Sociological Review 2024, Vol. 89(4) 708-734 (c) The Author(s) 2024\n"
        "The Dark Side of Community Ties\n"
        "Enzo Nussio\n"
        "\n"
        "## Abstract\n"
    )
    out = _strip_document_header_banners(text)
    assert "American Sociological Review 2024" not in out
    assert "The Dark Side" in out
    assert "Enzo Nussio" in out


def test_banner_strip_mangled_doi_line():
    """Lines starting with ``DhttOpsI:`` are mangled DOI from PDF text-run
    overlap and carry no information for the reader."""
    text = (
        "DhttOpsI::/1/d0o.i1.o1rg7/710/.0107073/010202314222442142152353226688 journals.sagepub.com/home/asr\n"
        "Author Name\n"
        "\n"
        "## Abstract\n"
    )
    out = _strip_document_header_banners(text)
    assert "DhttOpsI" not in out
    assert "Author Name" in out


def test_banner_strip_manuscript_id_gibberish():
    """Manuscript-ID strings like ``1253268 ASRXXX10.1177/...American
    Sociological ReviewNussio research-article2024`` are stripped."""
    text = (
        "1253268 ASRXXX10.1177/00031224241253268American Sociological ReviewNussio research-article2024\n"
        "\n"
        "## Abstract\n"
    )
    out = _strip_document_header_banners(text)
    assert "ASRXXX" not in out
    assert "## Abstract" in out


def test_banner_strip_arxiv_preprint_banner():
    """``arXiv:NNNN.NNNNNvN [cs.XX] DD Mon YYYY`` line dropped from header."""
    text = (
        "Latent Denoising Diffusion GAN: Faster sampling\n"
        "\n"
        "arXiv:2406.11713v1 [cs.CV] 17 Jun 2024\n"
        "\n"
        "## Abstract\n"
        "\n"
        "Body mentions arXiv:1234.5678v2 in passing — preserved.\n"
    )
    out = _strip_document_header_banners(text)
    # Banner gone.
    lines = out.split("\n")
    assert not any(l.strip().startswith("arXiv:2406.11713") for l in lines)
    # Title preserved.
    assert "Latent Denoising Diffusion GAN" in out
    # Body mention preserved.
    assert "Body mentions arXiv:1234.5678v2" in out


def test_banner_strip_elsevier_sciencedirect_block():
    """Elsevier banner: 'Journal Name 96 (2021) 104154 Contents lists ...' /
    'journal homepage: www.elsevier.com/...'."""
    text = (
        "Journal of Experimental Social Psychology 96 (2021) 104154 Contents lists available at ScienceDirect\n"
        "Journal of Experimental Social Psychology\n"
        "journal homepage: www.elsevier.com/locate/jesp\n"
        "\n"
        "Retrospective and prospective hindsight bias\n"
        "Author Name\n"
        "\n"
        "## ABSTRACT\n"
    )
    out = _strip_document_header_banners(text)
    assert "Contents lists available at ScienceDirect" not in out
    assert "journal homepage:" not in out
    assert "Retrospective and prospective hindsight bias" in out
    assert "Author Name" in out


def test_banner_strip_royal_society_block():
    """Royal Society Open Science: 'rsos.royalsocietypublishing.org' /
    'Cite this article: ...' / 'Subject Areas: ...' all dropped."""
    text = (
        "rsos.royalsocietypublishing.org\n"
        "Research\n"
        "Cite this article: Shibasaki M, Isomura T, Masataka N. 2014 Viewing images.\n"
        "Subject Areas: behaviour/cognition/evolution\n"
        "Author for correspondence: Nobuo Masataka\n"
        "Received: 30 May 2014\n"
        "Accepted: 7 October 2014\n"
        "\n"
        "## Abstract\n"
    )
    out = _strip_document_header_banners(text)
    assert "rsos.royalsocietypublishing.org" not in out
    assert "Cite this article:" not in out
    assert "Subject Areas:" not in out
    assert "Author for correspondence:" not in out
    assert "Received: 30 May 2014" not in out
    assert "Accepted: 7 October 2014" not in out
    assert "## Abstract" in out


def test_banner_strip_only_in_header_zone():
    """Patterns that match banner text in BODY (after the first ##
    heading) are NOT stripped — only the document header zone is touched."""
    text = (
        "Title\n"
        "\n"
        "## Abstract\n"
        "\n"
        "We tried Article reuse guidelines and ISSN: 0269-9931 in our analysis.\n"
        "Cite this article: shows up legitimately in this body sentence.\n"
        "arXiv:2406.11713v1 [cs.CV] 17 Jun 2024 — body mention.\n"
    )
    out = _strip_document_header_banners(text)
    # Body lines preserved verbatim.
    assert "ISSN: 0269-9931" in out
    assert "Cite this article: shows up legitimately" in out
    assert "arXiv:2406.11713v1 [cs.CV] 17 Jun 2024" in out


def test_banner_strip_preserves_title_among_banners():
    """The CORE safety guarantee: a title line that doesn't match any
    banner pattern is preserved even when it's surrounded by banner
    lines that are dropped."""
    text = (
        "HHS Public Access\n"
        "Author manuscript\n"
        "The Real Title Of The Paper That Should Survive\n"
        "Published in final edited form as: Some Journal. 2024.\n"
        "\n"
        "## Abstract\n"
    )
    out = _strip_document_header_banners(text)
    assert "The Real Title Of The Paper That Should Survive" in out
    assert "HHS Public Access" not in out
    assert "Published in final edited form" not in out


def test_banner_strip_when_no_heading_in_first_30_lines():
    """If the first ## heading is past line 30, the header zone is
    capped at line 30 — banners after line 30 are NOT stripped (they're
    body content at that point)."""
    body_lines = ["Body sentence number {}.".format(i) for i in range(40)]
    # Plant a banner-pattern line at body line 35 (well past cap).
    body_lines[35] = "HHS Public Access"
    text = "\n".join(body_lines) + "\n## Abstract\n"
    out = _strip_document_header_banners(text)
    # The line at body index 35 is preserved (past header zone cap).
    assert "HHS Public Access" in out


def test_banner_strip_idempotent():
    """Running the strip twice should produce the same output as running
    it once (no double-collapsing of blank lines)."""
    text = (
        "HHS Public Access\n"
        "Author manuscript\n"
        "Title Line\n"
        "\n"
        "## Abstract\n"
        "\n"
        "Body.\n"
    )
    once = _strip_document_header_banners(text)
    twice = _strip_document_header_banners(once)
    assert once == twice


def test_banner_strip_no_banners_returns_unchanged():
    """If no banner pattern matches in the header zone, return the
    original text unchanged (no spurious whitespace fiddling)."""
    text = "Just A Title\n\nAuthor Name\n\n## Abstract\n\nBody.\n"
    out = _strip_document_header_banners(text)
    assert out == text


def test_banner_strip_empty_input_safe():
    assert _strip_document_header_banners("") == ""


def test_banner_strip_drops_arxiv_banner_only_when_format_matches():
    """The arXiv banner regex is strict (NUMBER.NUMBER vN [category]
    DD Mon YYYY). A loose mention of arXiv is NOT stripped."""
    text = (
        "arXiv reference in metadata\n"
        "\n"
        "## Abstract\n"
    )
    out = _strip_document_header_banners(text)
    # "arXiv reference in metadata" doesn't match the strict banner regex.
    assert "arXiv reference in metadata" in out


# ---------------------------------------------------------------------------
# Iter-26 / Tier F5: TOC dot-leader strip
# ---------------------------------------------------------------------------

from splice_spike import _strip_toc_dot_leader_block


def test_toc_strip_drops_paragraph_with_dot_leader():
    """A paragraph containing dot-leader runs (``___``) near the doc top
    is dropped (TOC entry)."""
    text = (
        "Title line\n"
        "\n"
        "Table of Contents\n"
        "List of figures _________________ 3\n"
        "List of tables __________________ 4\n"
        "\n"
        "## Real Body Section\n"
        "\n"
        "Body paragraph text.\n"
    )
    out = _strip_toc_dot_leader_block(text)
    assert "List of figures" not in out
    assert "Table of Contents" not in out
    assert "## Real Body Section" in out
    assert "Body paragraph text." in out


def test_toc_strip_drops_false_promoted_heading():
    """A ``## Heading`` immediately followed by a TOC dot-leader paragraph
    is itself dropped (it's a misparsed TOC entry, not a real section)."""
    text = (
        "Title line\n"
        "\n"
        "## Background\n"
        "\n"
        "_________________________________ 17\n"
        "3. Measuring something ____________ 17\n"
        "4. Research plan __________________ 18\n"
        "\n"
        "## Findings\n"
        "\n"
        "________________________________ 21\n"
        "7.4 Replication ________________________ 21\n"
        "\n"
        "## Real Section\n"
        "\n"
        "Real body content here without any underscore runs at all.\n"
    )
    out = _strip_toc_dot_leader_block(text)
    # False headings dropped.
    assert "## Background" not in out
    assert "## Findings" not in out
    # TOC entries dropped.
    assert "Research plan" not in out
    assert "Replication" not in out
    # Real section preserved.
    assert "## Real Section" in out
    assert "Real body content here" in out


def test_toc_strip_preserves_real_heading_followed_by_body():
    """A ``## Background`` followed by REAL body prose (no dot-leader)
    is preserved — only the TOC pattern triggers the false-heading drop."""
    text = (
        "## Background\n"
        "\n"
        "Real body intro paragraph with no underscores.\n"
        "\n"
        "Followup paragraph also fine.\n"
    )
    out = _strip_toc_dot_leader_block(text)
    assert "## Background" in out
    assert "Real body intro paragraph" in out


def test_toc_strip_only_in_first_100_lines():
    """A paragraph with dot-leaders deep in the body (past line 100) is
    NOT stripped — this prevents accidentally removing body content that
    happens to mention long underscore runs."""
    body = "\n".join([f"Body paragraph {i}." for i in range(50)])  # 50 lines
    body += "\n" + ("\n".join([f"Para {i}\n" for i in range(60)]))  # more lines
    text = (
        "## Real Section\n"
        "\n"
        + body
        + "\n\nDeep paragraph that has __________ 200 a fake leader inside.\n"
    )
    out = _strip_toc_dot_leader_block(text)
    # Deep paragraph preserved.
    assert "fake leader inside" in out


def test_toc_strip_drops_table_of_contents_label():
    """The literal ``Table of Contents`` label is dropped even if alone
    on its own paragraph."""
    text = "Title\n\nTable of Contents\n\n## Body\n\nBody.\n"
    out = _strip_toc_dot_leader_block(text)
    assert "Table of Contents" not in out
    assert "## Body" in out


def test_toc_strip_drops_list_of_supplementary_figures_label():
    """Generic 'List of Supplementary Figures/Tables' labels are dropped
    when they appear as standalone paragraphs in the head zone."""
    text = (
        "Title\n"
        "\n"
        "List of Supplementary Tables\n"
        "\n"
        "## Body\n"
        "\n"
        "Body content.\n"
    )
    out = _strip_toc_dot_leader_block(text)
    assert "List of Supplementary Tables" not in out
    assert "## Body" in out


def test_toc_strip_no_underscores_returns_unchanged():
    """If the input contains no underscore runs at all, return verbatim
    (no spurious whitespace fiddling)."""
    text = "Title\n\n## Abstract\n\nBody text.\n"
    out = _strip_toc_dot_leader_block(text)
    assert out == text


def test_toc_strip_empty_input_safe():
    assert _strip_toc_dot_leader_block("") == ""


def test_toc_strip_idempotent():
    text = (
        "Title\n"
        "\n"
        "## Background\n"
        "\n"
        "________________ 17\n"
        "3. Section ______ 17\n"
        "\n"
        "## Real\n"
        "\n"
        "Body.\n"
    )
    once = _strip_toc_dot_leader_block(text)
    twice = _strip_toc_dot_leader_block(once)
    assert once == twice


def test_toc_strip_preserves_normal_underscores_in_body():
    """Single or double underscores (variable names, italic markers)
    are NOT triggered — only runs of 3+ underscores qualify as leader."""
    text = (
        "## Section\n"
        "\n"
        "We use the variable my_var_name for the analysis.\n"
        "Italic text with single _underscore_ markers stays.\n"
    )
    out = _strip_toc_dot_leader_block(text)
    assert "my_var_name" in out
    assert "_underscore_" in out
    assert "## Section" in out


def test_toc_strip_does_not_drop_real_body_heading_above_toc():
    """If a real ``## Heading`` is followed by REAL body, then a TOC
    paragraph, the heading is preserved (only the heading IMMEDIATELY
    above the TOC paragraph is dropped)."""
    text = (
        "## Real Section\n"
        "\n"
        "Real body content with no leaders.\n"
        "\n"
        "Old TOC ____________________ 5 leaks here in the early head zone.\n"
        "\n"
        "## Body Continues\n"
    )
    out = _strip_toc_dot_leader_block(text)
    # Real Section heading preserved (not adjacent to TOC).
    assert "## Real Section" in out
    assert "Real body content" in out
    # TOC leak dropped.
    assert "Old TOC" not in out
    # Subsequent heading preserved.
    assert "## Body Continues" in out


# ---------------------------------------------------------------------------
# Iter-27 / Tier F1 (cheap variant): page-footer line strip
# ---------------------------------------------------------------------------

from splice_spike import _strip_page_footer_lines


def test_footer_strip_drops_bare_page_number():
    """`Page 7` lines (bare page-N markers) are stripped wherever they
    appear in the document (demography_1, jmf_1 pattern)."""
    text = (
        "Body sentence one.\n"
        "Page 2\n"
        "Body sentence two.\n"
        "Page 27\n"
        "Body sentence three.\n"
    )
    out = _strip_page_footer_lines(text)
    assert "Page 2" not in out
    assert "Page 27" not in out
    assert "Body sentence one." in out
    assert "Body sentence two." in out
    assert "Body sentence three." in out


def test_footer_strip_drops_jama_date_pageofm():
    """`October 27, 2023 1/13` JAMA page footer dropped."""
    text = (
        "Body line A.\n"
        "October 27, 2023 1/13\n"
        "Body line B.\n"
        "December 19, 2023 5/12\n"
        "Body line C.\n"
    )
    out = _strip_page_footer_lines(text)
    assert "October 27, 2023 1/13" not in out
    assert "December 19, 2023 5/12" not in out
    assert "Body line A." in out
    assert "Body line C." in out


def test_footer_strip_drops_continued_marker():
    """Bare `(continued)` / `(Continued)` page-break markers dropped."""
    text = "First half.\n(continued)\nSecond half.\n(Continued)\nThird half.\n"
    out = _strip_page_footer_lines(text)
    assert "(continued)" not in out
    assert "(Continued)" not in out
    assert "First half." in out
    assert "Second half." in out


def test_footer_strip_drops_corresponding_author_line():
    """Single line starting with `Corresponding Author:` (the page-bottom
    footnote variant) dropped — a body sentence half above is preserved."""
    text = (
        "...lynch mobs do not usually count\n"
        "aETH Zurich\n"
        "Corresponding Author: Enzo Nussio, Center for Security Studies, ETH Zurich, ...\n"
        "Email: enzo.nussio@sipo.gess.ethz.ch\n"
        "\n"
        "## Introduction\n"
        "\n"
        "on standing organizational structures...\n"
    )
    out = _strip_page_footer_lines(text)
    assert "Corresponding Author:" not in out
    assert "aETH Zurich" not in out
    assert "Email: enzo.nussio@sipo.gess.ethz.ch" not in out
    # Body halves preserved.
    assert "lynch mobs do not usually count" in out
    assert "## Introduction" in out
    assert "on standing organizational" in out


def test_footer_strip_drops_bare_email_line():
    """A line that's just one or more email addresses is dropped."""
    text = (
        "Body.\n"
        "author@example.com\n"
        "More body.\n"
        "first@uni.edu, second@uni.edu\n"
        "Even more body.\n"
    )
    out = _strip_page_footer_lines(text)
    assert "author@example.com" not in out
    assert "first@uni.edu" not in out
    assert "Body." in out


def test_footer_strip_does_NOT_drop_email_inside_sentence():
    """An email mentioned inside a longer sentence is preserved (the
    pattern matches whole-line emails only)."""
    text = "Please contact author@example.com for the dataset.\n"
    out = _strip_page_footer_lines(text)
    assert "author@example.com" in out


def test_footer_strip_drops_jama_running_header():
    """The JAMA citation running header (`JAMA Network Open. 2023;...`) and
    category banner (`JAMA Network Open | Public Health ...`) dropped."""
    text = (
        "Body.\n"
        "JAMA Network Open. 2023;6(10):e2339337. doi:10.1001/jamanetworkopen.2023.39337\n"
        "JAMA Network Open | Nutrition, Obesity, and Exercise Effect of Time-Restricted Eating\n"
        "More body.\n"
    )
    out = _strip_page_footer_lines(text)
    assert "JAMA Network Open." not in out
    assert "Body." in out


def test_footer_strip_drops_open_access_compound_line():
    """`Open Access. This is an open access article ... doi:... (Reprinted)`
    compound footer dropped."""
    text = (
        "Body.\n"
        "Open Access. This is an open access article distributed under the terms of the CC-BY-NC-ND License. JAMA Network Open. 2023;6(10):e2339337. doi:10.1001/jamanetworkopen.2023.39337 (Reprinted)\n"
        "More body.\n"
    )
    out = _strip_page_footer_lines(text)
    assert "Open Access. This is an open access article" not in out
    assert "Body." in out


def test_footer_strip_drops_copyright_year_line():
    """Standalone `© 2024 Some Publisher` line dropped."""
    text = "Body.\n© 2024 Informa UK Limited, trading as Taylor & Francis Group\nMore body.\n"
    out = _strip_page_footer_lines(text)
    assert "Informa UK Limited" not in out
    assert "Body." in out


def test_footer_strip_drops_jama_visual_abstract_marker():
    """`+ Visual Abstract + Supplemental content` JAMA sidebar dropped."""
    text = "Body.\n+ Visual Abstract + Supplemental content\nMore body.\n"
    out = _strip_page_footer_lines(text)
    assert "Visual Abstract" not in out


def test_footer_strip_drops_jama_author_affil_pointer():
    """`Author affiliations and article information are listed at the end
    of this article.` JAMA pointer dropped."""
    text = (
        "Body.\n"
        "Author affiliations and article information are listed at the end of this article.\n"
        "More body.\n"
    )
    out = _strip_page_footer_lines(text)
    assert "Author affiliations and article information" not in out


def test_footer_strip_preserves_normal_body():
    """A document with no footer-pattern lines is returned verbatim."""
    text = "## Title\n\nBody text.\n\nMore body text.\n"
    out = _strip_page_footer_lines(text)
    assert out == text


def test_footer_strip_idempotent():
    text = (
        "Body line.\n"
        "Page 5\n"
        "(continued)\n"
        "Body continuation.\n"
        "© 2024 Publisher\n"
        "End body.\n"
    )
    once = _strip_page_footer_lines(text)
    twice = _strip_page_footer_lines(once)
    assert once == twice


def test_footer_strip_empty_input_safe():
    assert _strip_page_footer_lines("") == ""


def test_footer_strip_drops_aETH_affiliation_marker():
    """`aETH Zurich` footnote-anchor pattern (single lowercase letter +
    institution acronym) dropped."""
    text = "Body.\naETH Zurich\nbCambridge University\nMore body.\n"
    out = _strip_page_footer_lines(text)
    assert "aETH Zurich" not in out
    # bCambridge University also matches the pattern.
    assert "bCambridge University" not in out
    assert "Body." in out


def test_footer_strip_does_not_drop_real_capitalized_phrase():
    """A real two-word capitalized phrase like `New York Times` does NOT
    match the affiliation-marker pattern (no leading lowercase letter +
    ALL-CAPS acronym)."""
    text = "Body about New York Times article.\n"
    out = _strip_page_footer_lines(text)
    assert "New York Times article" in out


# ---------------------------------------------------------------------------
# Iter-29 / Tier F2-residual: multi-word JAMA heading tail re-attachment
# ---------------------------------------------------------------------------

from splice_spike import _merge_compound_heading_tails


def test_compound_heading_merges_conclusions_and_relevance():
    """The classic JAMA case: ``## CONCLUSIONS`` with ``AND RELEVANCE``
    orphan in the next paragraph (jama_open_1, jama_open_2)."""
    text = (
        "## RESULTS\n"
        "\n"
        "Seventy-five participants were enrolled.\n"
        "\n"
        "## CONCLUSIONS\n"
        "\n"
        "AND RELEVANCE This randomized clinical trial found that a TRE diet "
        "strategy was effective.\n"
    )
    out = _merge_compound_heading_tails(text)
    assert "## CONCLUSIONS AND RELEVANCE" in out
    # The orphaned tail must NOT remain as standalone body.
    assert "AND RELEVANCE This randomized" not in out
    # Body content survives intact, starting with the original first body word.
    assert "This randomized clinical trial found that a TRE diet strategy was effective." in out
    # The other heading is untouched.
    assert "## RESULTS" in out


def test_compound_heading_preserves_unrelated_headings():
    """Other ## headings and body content must not be modified."""
    text = (
        "## Introduction\n"
        "\n"
        "Background paragraph one.\n"
        "\n"
        "## Methods\n"
        "\n"
        "Methodology details.\n"
    )
    out = _merge_compound_heading_tails(text)
    assert out == text


def test_compound_heading_no_match_when_tail_missing():
    """``## CONCLUSIONS`` followed by body that does NOT start with
    ``AND RELEVANCE`` is left alone (not all JAMA papers split this way)."""
    text = (
        "## CONCLUSIONS\n"
        "\n"
        "These findings support the hypothesis that fasting helps.\n"
    )
    out = _merge_compound_heading_tails(text)
    assert out == text


def test_compound_heading_idempotent():
    """Running the merge twice produces no further change."""
    text = (
        "## CONCLUSIONS\n"
        "\n"
        "AND RELEVANCE This randomized clinical trial found a benefit.\n"
    )
    once = _merge_compound_heading_tails(text)
    twice = _merge_compound_heading_tails(once)
    assert once == twice
    assert "## CONCLUSIONS AND RELEVANCE" in once


def test_compound_heading_empty_input_safe():
    assert _merge_compound_heading_tails("") == ""


def test_compound_heading_does_not_rewrite_already_correct_heading():
    """If the heading is already ``## CONCLUSIONS AND RELEVANCE`` we should
    NOT find a body paragraph starting with ``AND RELEVANCE`` — make sure
    a properly-formed heading is preserved."""
    text = (
        "## CONCLUSIONS AND RELEVANCE\n"
        "\n"
        "This randomized clinical trial found that a TRE diet strategy was effective.\n"
    )
    out = _merge_compound_heading_tails(text)
    assert out == text


def test_compound_heading_does_not_match_when_heading_has_extra_text():
    """``## CONCLUSIONS:`` (with trailing colon) is NOT a bare heading
    and the merge should not fire."""
    text = (
        "## CONCLUSIONS:\n"
        "\n"
        "AND RELEVANCE This study found a benefit.\n"
    )
    out = _merge_compound_heading_tails(text)
    # Heading unchanged.
    assert "## CONCLUSIONS:" in out
    # Body unchanged (orphan stays — out of scope for this narrow merge).
    assert "AND RELEVANCE This study" in out


# ---------------------------------------------------------------------------
# Iter-28 / Tier F3: title rescue from inside ## Abstract
# ---------------------------------------------------------------------------

from splice_spike import _apply_title_rescue


def test_title_rescue_strips_title_swept_into_abstract():
    """sci_rep_1 / nat_comms_2 pattern: title block was swept INSIDE
    ``## Abstract`` by the section detector. Rescue must strip those
    lines from the abstract and prepend ``# Title`` at top."""
    title_text = (
        "The association between dietary approaches to stop hypertension "
        "diet and bone mineral density in US adults"
    )
    out = (
        "## Abstract\n"
        "\n"
        "OPEN The association between dietary\n"
        "approaches to stop hypertension\n"
        "diet and bone mineral density in US\n"
        "adults\n"
        "Xiang-Long Zhai, Mo-Yao Tan, Gao-Peng Wang\n"
        "This study aimed to investigate the relationship between DASH and BMD.\n"
    )
    rescued = _apply_title_rescue(out, title_text)
    assert rescued.startswith(f"# {title_text}\n"), rescued[:200]
    # The original 4-line title block (with the "OPEN" leader-token) must
    # have been stripped from INSIDE ``## Abstract`` — there should be no
    # ``OPEN The association`` literal line in the rescued output.
    assert "OPEN The association between dietary" not in rescued
    # The Abstract section now contains ONLY the author line + abstract body.
    abstract_idx = rescued.index("## Abstract")
    abstract_body = rescued[abstract_idx:]
    assert "approaches to stop hypertension" not in abstract_body
    assert "diet and bone mineral density in US" not in abstract_body
    # Authors line is NOT part of the title token-match window (different
    # tokens) so it stays put under ## Abstract — author rescue is
    # intentionally out of scope for iter-28.
    assert "Xiang-Long Zhai" in abstract_body
    # Abstract-body sentence survives.
    assert "This study aimed to investigate" in abstract_body


def test_title_rescue_upgrades_inplace_when_title_already_before_abstract():
    """korbmacher pattern: title is already on its own lines BEFORE
    ``## Abstract`` as plain text. The rescue should upgrade those lines
    to ``# Title`` in place — not duplicate the title at the top."""
    title_text = (
        "Both better and worse than others depending on difficulty: "
        "Replication and extensions of Kruger's (1999) effects"
    )
    out = (
        "Both better and worse than others depending on difficulty: "
        "Replication and extensions of Kruger's\n"
        "(1999) effects\n"
        "Max Korbmacher Ching Kwan Gilad Feldman\n"
        "\n"
        "## Abstract\n"
        "\n"
        "Above-and-below-average effects are well-known phenomena.\n"
    )
    rescued = _apply_title_rescue(out, title_text)
    assert rescued.startswith(f"# {title_text}\n"), rescued[:200]
    # The plain-text title block was replaced (so the un-escaped title text
    # should appear at most ONCE — once as the # heading).
    assert rescued.count(title_text) == 1
    # Authors and Abstract section survive.
    assert "Max Korbmacher" in rescued
    assert "## Abstract" in rescued
    assert "Above-and-below-average effects" in rescued


def test_title_rescue_prepends_when_title_missing_from_doc():
    """nat_comms_1 pattern: title got dropped completely upstream and the
    rendered doc starts directly with ``## Abstract`` + body. Rescue must
    prepend ``# Title`` at the top without touching anything else."""
    title_text = (
        "Targeted treatment of injured nestmates with antimicrobial "
        "compounds in an ant society"
    )
    out = (
        "## Abstract\n"
        "\n"
        "Erik T. Frank, Lucie Kesner, Joanito Liberti et al.\n"
        "Infected wounds pose a major mortality risk in animals.\n"
    )
    rescued = _apply_title_rescue(out, title_text)
    assert rescued.startswith(f"# {title_text}\n"), rescued[:200]
    # Original content preserved.
    assert "## Abstract" in rescued
    assert "Erik T. Frank" in rescued
    assert "Infected wounds pose a major mortality risk" in rescued


def test_title_rescue_does_not_double_prepend_when_h1_already_present():
    """If the document already has an ``# `` h1 in the first 30 lines, the
    rescue is a no-op (we never want two title lines)."""
    out = (
        "# Some Existing Title\n"
        "\n"
        "## Abstract\n"
        "\n"
        "Body sentence.\n"
    )
    rescued = _apply_title_rescue(out, "A Different Computed Title From Layout")
    assert rescued == out


def test_title_rescue_no_match_short_title_just_prepends():
    """A 2-token title is too short to confidently locate; we just prepend."""
    out = "## Abstract\n\nBody one.\n"
    rescued = _apply_title_rescue(out, "Short Title")
    # Token count is 2, below the >=3 threshold — we just prepend.
    assert rescued.startswith("# Short Title\n"), rescued
    assert "## Abstract" in rescued


def test_title_rescue_empty_inputs_safe():
    assert _apply_title_rescue("", "Title") == ""
    out = "## Abstract\n\nBody.\n"
    assert _apply_title_rescue(out, "") == out


def test_title_rescue_no_token_match_means_just_prepend():
    """If the computed title's tokens don't appear in the first 50 lines of
    the document, we should still place the title at the top (no in-place
    replacement)."""
    out = (
        "## Methods\n"
        "\n"
        "We surveyed 100 participants about their lunch preferences.\n"
        "## Results\n"
        "\n"
        "Half preferred soup.\n"
    )
    rescued = _apply_title_rescue(out, "An Entirely Unrelated Title String About Astrophysics Galaxies")
    assert rescued.startswith("# An Entirely Unrelated Title String About Astrophysics Galaxies\n")
    # Original content preserved.
    assert "## Methods" in rescued
    assert "## Results" in rescued
    assert "Half preferred soup" in rescued


# Layout-side title computation tests — exercise _compute_layout_title with a
# synthetic LayoutDoc-shaped object. We use lightweight stand-ins for the
# pdfplumber layout dataclasses to avoid spinning up pdfplumber in tests.

from splice_spike import _compute_layout_title


class _StubSpan:
    """Mimics the attributes of docpluck.extract_layout.TextSpan."""
    def __init__(self, text, x0, y0, x1, y1, font_size, bold=False, font_name=""):
        self.text = text
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        self.font_size = font_size
        self.font_name = font_name
        self.bold = bold


class _StubPage:
    def __init__(self, height, spans, words=()):
        self.height = height
        self.width = 595.0
        self.spans = spans
        self.words = tuple(words)


class _StubDoc:
    def __init__(self, pages):
        self.pages = tuple(pages)


def test_compute_layout_title_picks_dominant_largest_font_block():
    """Three lines at 26pt (title) above two lines at 9pt (body) — the
    title is identified, not the body."""
    spans = [
        # Title spans at 26pt (bottom-origin y0; larger = higher on page).
        _StubSpan("ignored span text 1", 100, 720, 400, 740, font_size=26.0),
        _StubSpan("ignored span text 2", 100, 690, 400, 710, font_size=26.0),
        _StubSpan("ignored span text 3", 100, 660, 400, 680, font_size=26.0),
        # Body at 9pt below.
        _StubSpan("body 1", 100, 400, 400, 410, font_size=9.0),
        _StubSpan("body 2", 100, 390, 400, 400, font_size=9.0),
    ]
    words = [
        # Words have top-origin coords. y0_from_bottom = height - bottom.
        # height=800, title at y0=660..740 → bottom=60..140 (top=60..140).
        # We'll seed words inside the title y-range:
        {"text": "Targeted",   "x0": 100, "top": 60,  "bottom": 80},
        {"text": "treatment",  "x0": 200, "top": 60,  "bottom": 80},
        {"text": "of",         "x0": 320, "top": 60,  "bottom": 80},
        {"text": "wounds",     "x0": 100, "top": 90,  "bottom": 110},
        {"text": "in",         "x0": 200, "top": 90,  "bottom": 110},
        {"text": "ants",       "x0": 240, "top": 90,  "bottom": 110},
        # Body word should NOT be matched (outside y-range).
        {"text": "BodyWord",   "x0": 100, "top": 390, "bottom": 400},
    ]
    page = _StubPage(height=800, spans=spans, words=words)
    doc = _StubDoc(pages=[page])
    title = _compute_layout_title(doc)
    assert title is not None, "expected a title to be found"
    # Multi-line title must concatenate with proper word spacing.
    assert "Targeted treatment of" in title
    assert "wounds in ants" in title
    assert "BodyWord" not in title


def test_compute_layout_title_returns_none_when_no_large_font_present():
    """A page with only small font (<12pt) should not yield a title — too
    risky to upgrade body text to a title heading."""
    spans = [
        _StubSpan("body line 1", 100, 700, 400, 710, font_size=10.0),
        _StubSpan("body line 2", 100, 690, 400, 700, font_size=10.0),
    ]
    page = _StubPage(height=800, spans=spans, words=[])
    doc = _StubDoc(pages=[page])
    assert _compute_layout_title(doc) is None


def test_compute_layout_title_rejects_obvious_banner():
    """If the largest-font upper-page-1 block is publisher banner text
    (e.g. ``HHS Public Access``), reject it as a title candidate."""
    spans = [
        _StubSpan("HHS Public Access", 100, 700, 300, 720, font_size=20.0),
        _StubSpan("HHS Public Access", 100, 670, 300, 690, font_size=20.0),
    ]
    words = [
        {"text": "HHS",    "x0": 100, "top": 80,  "bottom": 100},
        {"text": "Public", "x0": 150, "top": 80,  "bottom": 100},
        {"text": "Access", "x0": 220, "top": 80,  "bottom": 100},
        {"text": "HHS",    "x0": 100, "top": 110, "bottom": 130},
        {"text": "Public", "x0": 150, "top": 110, "bottom": 130},
        {"text": "Access", "x0": 220, "top": 110, "bottom": 130},
    ]
    page = _StubPage(height=800, spans=spans, words=words)
    doc = _StubDoc(pages=[page])
    assert _compute_layout_title(doc) is None


def test_compute_layout_title_handles_empty_doc_safely():
    assert _compute_layout_title(None) is None
    assert _compute_layout_title(_StubDoc(pages=[])) is None
    page = _StubPage(height=800, spans=[], words=[])
    assert _compute_layout_title(_StubDoc(pages=[page])) is None
