"""A page NUMBER is furniture; a page BOUNDARY is structure. Do not delete the boundary.

## The defect (pre-existing, and it had been latent since the rule was written)

`_normalize_text` strips standalone page numbers with

    re.sub(r"^\\s*\\d{1,3}\\s*$", "", t, flags=re.MULTILINE)

Under `re.MULTILINE` the whitespace class matches newlines **and the form feed**,
so the match could extend past the page number and swallow the `\\f` next to it.

It stayed invisible for as long as a running footer stood between the page number
and the page break. The moment F0 stripped that footer, **all 15 form feeds
vanished** from `PMC13137057`'s output — and with them the `\\n\\f\\f\\n` marker
that separates the footnote appendix, folding a **6,055-character appendix back
into the body** where a consumer reads it as running text.

Measured on the 26-paper render baseline, against a `git worktree` of the tree
before the fix: **16 papers gain page breaks** (+1 to +17 each), **2 papers have
a destroyed footnote appendix restored** (0 → 1,288 and 0 → 2,165 bytes, with the
body shrinking by exactly the same amount — a move, not a rewrite), **0 papers
lose a line**, and every paper's total character count goes UP or stays equal.

## Why the form feed is CAPTURED rather than merely excluded

Narrowing the class to `[ \\t]` was the first fix, and it was wrong in the other
direction: a page number is frequently the FIRST thing on a new page, so the line
itself begins with the break (`"\\x0c496"`). With the form feed simply excluded
from the class, those lines stopped matching at all and the page numbers came
back — measured, `'496'`..`'502'` reappeared in the body of
`10.1016/j.jesp.2009.12.010`. Capturing the break and putting it back deletes the
number and keeps the boundary.

See LESSONS L-052.
"""

from __future__ import annotations

from docpluck.extract_layout import LayoutDoc, PageLayout, TextSpan
from docpluck.normalize import (
    PAGE_BREAK,
    _f0_strip_running_and_footnotes,
    _key,
    _strip_standalone_page_numbers as _strip_page_numbers,
)

# The SHIPPED function is imported, never a retyped copy of its regex. A pasted
# pattern is a second definition of one rule: it would keep passing while the
# rule it claims to pin drifted underneath it.


def test_a_page_number_alone_on_a_line_is_removed():
    assert _strip_page_numbers("body\n  42  \nmore") == "body\n\nmore"


def test_a_page_number_does_not_take_the_page_break_with_it():
    """The whole defect, in one assertion."""
    text = "body\n\n01\n\n\n" + PAGE_BREAK + "\n\nmore"
    out = _strip_page_numbers(text)
    assert PAGE_BREAK in out, repr(out)
    assert "01" not in out, repr(out)


def test_a_page_number_that_STARTS_a_page_is_still_removed():
    """`\\x0c496` — the break and the number share a line. Keep one, drop the other."""
    out = _strip_page_numbers("body\n" + PAGE_BREAK + "496\nmore")
    assert PAGE_BREAK in out, repr(out)
    assert "496" not in out, repr(out)


def test_an_inline_number_is_untouched():
    assert _strip_page_numbers("keep 12 inline") == "keep 12 inline"


def test_a_four_digit_number_is_not_this_rule_s_business():
    assert _strip_page_numbers("1174") == "1174"


# ── the same principle inside F0's strip loop ────────────────────────────────
#
# `re.split(r"([\n\f])", ...)` attaches the separator AFTER a line to that line,
# so deleting a stripped line consumed its page break too. A running footer is
# the LAST line on its page, which is exactly when it matters.


def _doc(n_pages: int) -> LayoutDoc:
    def page(i: int) -> PageLayout:
        mk = lambda t, y, sz: TextSpan(  # noqa: E731
            text=t, page_index=i, x0=49.6, y0=y, x1=545.0, y1=y + 9,
            font_size=sz, font_name="Times", bold=False)
        return PageLayout(i, 595.0, 842.0, spans=(
            mk("Journal of Constant Footers", 810.0, 7.0),
            mk(f"Body sentence {i} carrying the actual content of the page.", 400.0, 9.0),
        ))
    pages = tuple(page(i) for i in range(n_pages))
    return LayoutDoc(pages=pages, raw_text="", page_offsets=tuple(range(n_pages)))


def test_stripping_a_running_header_keeps_the_page_break():
    """The furniture must be the LAST line on its page, or this proves nothing.

    The segment split attaches the separator AFTER a line to that line, so
    `_drop()` only ever sees a page break when the line it deletes is the last
    one before it. The first version of this fixture put the furniture FIRST on
    each page, its separator was a newline, and the test passed even with
    `_drop()` neutered -- a guard that cannot fail is decoration.
    """
    doc = _doc(8)
    raw = PAGE_BREAK.join(
        f"Body sentence {i} carrying the actual content of the page."
        f"\nJournal of Constant Footers" for i in range(8)
    )
    before = raw.count(PAGE_BREAK)
    body, _spans, _texts = _f0_strip_running_and_footnotes(raw, doc)
    assert "Journal of Constant Footers" not in body, "the furniture should go"
    assert body.count(PAGE_BREAK) == before, (
        f"page breaks {before} -> {body.count(PAGE_BREAK)}; the boundary is structure")
    for i in range(8):
        assert f"Body sentence {i}" in body


def test_control_characters_do_not_defeat_the_key():
    """`_key` is hoisted and strips non-whitespace control characters.

    pdftotext emits a running header as a form feed + text + a BACKSPACE
    (measured on PMC13137057). A stray BACKSPACE is not whitespace, so
    `str.split()` leaves it and the line is unequal to its layout-channel twin.

    NOTE, so this is not read as more than it is: on the 26-paper baseline and
    the 30 held-out PMC papers this changes no output today, because those
    headers ALSO differ from their layout key by more than control characters
    (the channels disagree about where the line ends — see the handoff). It is
    kept as a correctness fix to a key used by both sides, not as a capability.
    """
    assert _key(PAGE_BREAK + "Frey et al." + chr(8)) == "Frey et al."
