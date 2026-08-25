"""A PAGE NUMBER IS IN THE MARGIN; A BARE INTEGER IN THE BODY IS A VALUE.

`normalize.py::_strip_standalone_page_numbers` deleted EVERY line whose whole
content was a 1-3 digit integer, with no page context at all:

    _PAGE_NUMBER_LINE_RE = re.compile(r"^(\\f*)[ \\t]*\\d{1,3}[ \\t]*$", re.MULTILINE)

pdftotext emits a narrow numeric table column as one cell per line, so a printed
coefficient of `0` is that shape exactly. The rule was therefore silently
selective about which published values it destroyed -- `-4`, `0.5` and `1000`
survived, `0`, `4` and `999` did not -- and it destroyed them with no count, no
`changes_made` key and no log line.

REAL PAPER, NOT CONSTRUCTED. `10.1136/bmj-2024-080924` (BMJ), supplementary
appendix Table S1 p6, row "Number of Advancement Maneuvers (attempt #2)":

    Number of Advancement
    Maneuvers (attempt #2)      2 (0, 4)    2 (1, 4)    0   (-1.5 to 1.5)   0.999

The printed coefficient is `0`. docpluck delivered the interval and the p-value
with NO estimate -- a confidence interval attached to nothing, which is worse
than a wrong number because there is nothing for a reader to challenge. Filed by
ESCImate as `2026-08-09/DP-14`; the row-structure half of that report turned out
to be this deletion.

Found 2026-08-22 while auditing `ESCIcheckapp/REPLY_TO_DOCPLUCK_2026-08-09.md`.
Reproduce the class:
    python tools/diag/page_number_strip_blast_radius.py --baseline
"""

from __future__ import annotations

import pytest

from docpluck.normalize import (
    NormalizationLevel,
    _strip_standalone_page_numbers,
    normalize_text,
)


def _text(result):
    return result[0] if isinstance(result, tuple) else result


# ---------------------------------------------------------------- the defect

# The BMJ row, in the shape pdftotext actually emits it: one cell per line.
BMJ_ROW = (
    "Number of Advancement\n"
    "Maneuvers (attempt #2)\n"
    "\n"
    "2 (0, 4)\n"
    "\n"
    "2 (1, 4)\n"
    "\n"
    "0\n"
    "\n"
    "(-1.5 to 1.5)\n"
    "\n"
    "0.999\n"
)


def test_a_bare_coefficient_in_a_table_row_survives_normalization():
    """The published `0` must reach the consumer. 10.1136/bmj-2024-080924 Table S1."""
    out = _text(normalize_text(BMJ_ROW, level=NormalizationLevel.academic))
    assert "\n0\n" in out, (
        "the printed coefficient 0 was deleted; the consumer receives "
        "(-1.5 to 1.5) and p = 0.999 attached to no estimate"
    )


@pytest.mark.parametrize("value", ["0", "4", "12", "999", "100"])
def test_an_interior_bare_integer_is_never_deleted(value: str):
    """Any bare integer in the BODY of a page is a value, not furniture."""
    page = f"Some heading\n\nlabel cell\n\n{value}\n\n(-1.5 to 1.5)\n\nmore body text\n"
    assert f"\n{value}\n" in _strip_standalone_page_numbers(page)


# --------------------------------------------- still strips real page numbers


def _body(n_lines: int = 25) -> str:
    """A page's worth of text. The pagination gate requires consecutive page
    numbers to be at least `_PAGINATION_MIN_LINE_GAP` lines apart, which is what
    separates pages 1, 2, 3 from a table column reading `1 2 3` down adjacent
    cells -- so a fixture with five-line pages is not a document."""
    return "".join(f"Body sentence {i}." + chr(10) for i in range(n_lines))


def _paginated(numbers, where="foot"):
    """A document whose page numbers form a real run: one per page, ascending."""
    if where == "foot":
        return "".join(f"{chr(12)}{_body()}{n}" + chr(10) for n in numbers)
    return "".join(f"{chr(12)}{n}" + chr(10) + _body() for n in numbers)


def test_a_page_number_at_the_foot_of_a_page_is_still_stripped():
    out = _strip_standalone_page_numbers(_paginated((12, 13, 14), "foot"))
    for n in (12, 13, 14):
        assert f"\n{n}\n" not in out


def test_a_page_number_at_the_head_of_a_page_is_still_stripped():
    out = _strip_standalone_page_numbers(_paginated((12, 13, 14), "head"))
    for n in (12, 13, 14):
        assert f"\f{n}\n" not in out


def test_the_page_break_survives_the_strip():
    """v1.9.57's promise: delete the NUMBER, keep the BOUNDARY. See LESSONS L-052.

    True by construction now rather than by capture-group: the step splits on the
    form feed, edits within each page and rejoins, so the boundary cannot be
    consumed by the pattern that removes the number standing beside it.
    """
    out = _strip_standalone_page_numbers(_paginated((14, 15, 16), "head"))
    assert out.count("\f") == 3, "a form feed was consumed with a page number"


def test_a_page_number_above_a_leftover_footer_is_caught_by_the_run_gate():
    """Position identifies nothing; the RUN does.

    There is no margin gate at all -- it was built, measured at 9 strips in
    1,103 across the baseline, and removed because it is not idempotent inside a
    pipeline whose other steps delete lines. See the note above
    `_HEADER_ZONE_LINES`.
    """
    one_page = f"{chr(12)}{_body()}7\nJournal of Something, 2024\n"
    assert "\n7\n" in _strip_standalone_page_numbers(one_page)

    run = "".join(
        f"{chr(12)}{_body()}{n}\nJournal of Something, 2024\n" for n in (7, 8, 9)
    )
    out = _strip_standalone_page_numbers(run)
    for n in (7, 8, 9):
        assert f"\n{n}\n" not in out


def test_the_strip_is_idempotent_under_line_removal():
    """Running the rule twice, with lines removed in between, must not widen it.

    This is the shape that broke `test_normalize_idempotent_jama_open_1`: the
    step lives in a pipeline whose other steps delete lines, so its second-pass
    input has a different non-blank set from its first.
    """
    doc = "\fRunning header\n\nBody one.\n\n67\n\n67\n\nBody two.\n\n12\n"
    once = _strip_standalone_page_numbers(doc)
    # simulate an earlier step removing the header before the second pass
    thinned = once.replace("Running header\n\n", "")
    twice = _strip_standalone_page_numbers(thinned)
    assert twice == thinned, "the rule deleted more on a second pass"
    assert twice.count("67") == 2, "a table cell was swallowed by the sliding band"


# ------------------------------------------------------------- observability


def test_the_deletion_is_counted():
    """Rule 0g: a step that DELETES must record what it deleted."""
    body = "".join(f"{chr(12)}{_body()}{n}\n" for n in (12, 13, 14))
    report = normalize_text(body, level=NormalizationLevel.academic)
    report = report[1] if isinstance(report, tuple) else None
    if report is None:  # pragma: no cover - normalize_text always returns a report
        pytest.skip("normalize_text did not return a report")
    assert "page_numbers_stripped" in report.changes_made, (
        "the page-number strip removes content and must appear in changes_made"
    )


# ------------------------------------- pagination runs, wherever they sit

def test_a_mid_page_pagination_run_is_still_stripped():
    """A two-column PDF puts the page number in the MIDDLE of the reading order.

    Measured on 10.1016/j.jesp.2009.12.010: `495` lands between "non-agree-" and
    "ment and the status quo", nowhere near a page edge. The margin gate alone
    leaks it, so a run whose value increments once per page -- the exact
    pagination signature -- is stripped wherever it sits.
    """
    doc = "".join(
        f"{chr(12)}{_body(12)}{n}\n{_body(12)}"
        for n in (495, 496, 497, 498)
    )
    out = _strip_standalone_page_numbers(doc)
    for n in (495, 496, 497, 498):
        assert f"\n{n}\n" not in out, f"page number {n} survived in the body"


def test_a_table_column_of_small_integers_on_one_page_is_not_a_pagination_run():
    """Same shape, one page: values do not increment WITH the page."""
    page = "\fheading\n\n" + "\n\n".join(str(n) for n in (1, 2, 3, 4, 5)) + "\n\nfooter text\n"
    out = _strip_standalone_page_numbers(page)
    for n in (2, 3, 4):  # 1 and 5 sit in the margin band by construction
        assert f"\n{n}\n" in out, f"table cell {n} was deleted as a page number"


def test_two_pages_are_not_enough_for_a_pagination_run():
    """The threshold is >= 3 distinct pages, matching the 4-digit rule."""
    doc = (
        "\fbody a\n\nbody b\n\n7\n\nbody c\n\nbody d\n"
        "\fbody a\n\nbody b\n\n8\n\nbody c\n\nbody d\n"
    )
    out = _strip_standalone_page_numbers(doc)
    assert "\n7\n" in out and "\n8\n" in out
