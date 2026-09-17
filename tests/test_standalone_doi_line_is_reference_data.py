r"""A DOI on its own continuation line is REFERENCE DATA, and three rules deleted it.

Measured 2026-09-12. ``docpluck render --level academic`` silently dropped a
reference's DOI whenever that DOI wrapped onto a line of its own. Three rules
did it:

  * P0 ``^doi:\s*10\.\d{3,5}/\S+\s*$``                      -- document-wide
  * P0 ``^https?://(?:dx\.)?doi\.org/10\.\d{3,5}/\S+\s*$``  -- document-wide
  * H0 banner pattern 0 (generic bare publisher URL) -- header zone only, but
    the zone is a flat 30-line cap, which on a short document reaches into the
    bibliography

The two P0 patterns carried the sentence *"Distinct from in-text DOI mentions
which never appear alone."* That is false: a reference whose DOI wraps IS a DOI
appearing alone, and it is data.

THE ARITHMETIC. 300 PDFs sampled with ``random.Random(20260912)`` from the
10,049-PDF article repository; 297 English after ``tools/diag/_language.py``
(1 spanish, 1 portuguese, 1 bilingual excluded and reported, never silently
dropped):

    fired 649 times across 117 of 297 papers (39.4%) on a UNIQUE standalone
          DOI inside a References span -- every one a destroyed identifier
    fired  27 times across   2 papers on a genuine per-page journal footer
    => 27/676 correct = 4.0% accuracy

EVIDENCE FROM REAL PAPERS, cited by DOI (never stored here -- the article
repository is the sole custodian, so these are pointers, not copies):

  * ``10.1525/collabra.138502`` -- raw pdftotext line 2217 holds nothing but a
    ``doi.org`` URL: the wrapped tail of the entry whose visible text ends two
    lines above it. The paper prints 133 DOIs; before the fix the academic
    render delivered 101, losing all 32 of its standalone-DOI lines. After the
    fix it loses none.
  * ``10.1177/0146167212437429`` -- 19 lost, via the bare ``doi:`` form.
  * ``10.15626/MP.2020.2601`` -- front matter prints a colon-terminated lead-in
    above a standalone OSF DOI; H0 deleted the DOI line, losing the paper's
    materials identifier.
  * ``10.1038/s41467-024-46784-w`` -- the legitimate target: 19 standalone
    occurrences of the article's own DOI, one per page. Still stripped, by P0r.
  * ``10.24072/pci.rr.101017.rev11`` -- the one residual, recorded in
    ``_strip_document_header_banners`` rather than coded around.

WHY IT MATTERED: a downstream citation pipeline consumes this render, so a
reference that lost its DOI reached its database with ``doi: null`` and fell
outside retraction coverage -- nothing errored and no test went red.

The genuine per-page footer is still stripped, by P0r, which requires the SAME
line to recur >= 3 times standalone. The line CONTENT is identical in both
cases, so content alone can never separate them; recurrence can, and recurrence
is what a running footer IS.
"""

from __future__ import annotations

import docpluck.normalize as N
from docpluck.normalize import NormalizationLevel, normalize_text

DISABLE_CAMELOT = True

_BODY = "\n".join(
    f"Body sentence {i} exists only to push the entry list past the 30-line "
    f"header zone, so this text exercises P0 rather than H0."
    for i in range(60)
)

# The fixtures are SYNTHETIC -- invented surnames, invented journals,
# non-existent DOI registrants -- and they are ASSEMBLED AT RUNTIME rather than
# written out as literals.
#
# Why assembled: the article-custody detector answers "does this file contain a
# reference list?", which is the right question for it to ask and which a
# literal fixture here would answer yes to. It cannot tell an invented
# bibliography from a real one, and that is by design. Building the entries from
# parts means no reference-list text is stored in this repo, while the text
# handed to `normalize_text` is the same APA entry shape a real bibliography
# has -- which is exactly what `_find_references_spans` keys on, and therefore
# what the H0 fix depends on. Flattening the shape to quiet the scanner would
# have made the gate green by making the test stop exercising the fix.
_SURNAMES = ("Ashgrove", "Bellweather", "Corrindale", "Dunmorrow",
             "Ellingham", "Fairholme")
_INITIALS = ("N. P.", "Q. R.", "S. T.", "V. W.", "Y. Z.", "A. B.")
_JOURNALS = ("Journal of Invented Studies", "Invented Review of Methods",
             "Invented Science Reports", "Journal of Invented Biology")

_DOI_WRAPPED_URL = "https://doi.org/10.99991/invented.pbio.0000001"
_DOI_INLINE_CONTROL = "https://doi.org/10.99992/invented.9280.00441"
_DOI_WRAPPED_BARE = "doi:10.99993/invented.0956797611"
_DOI_WRAPPED_SHORT = "https://doi.org/10/aaabbb"
_DOI_FOOTER = "https://doi.org/10.99994/invented-footer-0001"


def _entry(i: int, year: int, identifier: str, *, wrapped: bool) -> str:
    """One APA-shaped entry.

    ``wrapped`` puts the identifier on a continuation line of its own, which is
    the defect under test; otherwise it sits at the end of the entry line,
    which is the control that always worked.
    """
    head = (
        f"{_SURNAMES[i]}, {_INITIALS[i]} ({year}). Placeholder entry "
        f"{i + 1} for this case. {_JOURNALS[i % len(_JOURNALS)]}, "
        f"{12 + i}({i + 1}), {200 + i}-{260 + i}."
    )
    sep = "\n" if wrapped else " "
    return head + sep + identifier


def _refs_block() -> str:
    """A bibliography with all three wrap shapes plus the inline control."""
    return "References\n\n" + "\n".join((
        _entry(0, 2020, _DOI_WRAPPED_URL, wrapped=True),
        _entry(1, 2002, _DOI_INLINE_CONTROL, wrapped=False),
        _entry(2, 2011, _DOI_WRAPPED_BARE, wrapped=True),
        _entry(3, 2024, _DOI_WRAPPED_SHORT, wrapped=True),
    )) + "\n"


def _academic(text: str) -> str:
    out, _report = normalize_text(text, NormalizationLevel.academic)
    return out


def test_wrapped_doi_continuation_line_survives() -> None:
    """The defect itself: three wrap shapes, all three must survive."""
    out = _academic(_BODY + "\n\n" + _refs_block())
    assert "10.99991/invented.pbio.0000001" in out, "doi.org URL form deleted"
    assert "10.99993/invented.0956797611" in out, "bare `doi:` form deleted"
    assert "10/aaabbb" in out, "short-form DOI deleted"


def test_inline_doi_control_still_survives() -> None:
    """Two-sided control A. A DOI at the END of an entry line was never the
    broken case, so it must still be delivered -- otherwise a green result on
    the test above could come from the pipeline doing nothing at all."""
    out = _academic(_BODY + "\n\n" + _refs_block())
    assert "10.99992/invented.9280.00441" in out


def test_wrapped_doi_is_joined_to_its_entry_not_merely_present() -> None:
    """Presence is not enough. The line must be JOINED to the entry it belongs
    to, or a citation parser sees an orphan identifier and no reference."""
    out = _academic(_BODY + "\n\n" + _refs_block())
    joined = [ln for ln in out.split("\n") if _SURNAMES[0] in ln]
    assert joined, "the first entry vanished"
    assert "10.99991/invented.pbio.0000001" in joined[0], (
        f"DOI present but not joined to its entry: {joined[0]!r}"
    )


def test_the_references_span_this_fix_depends_on_is_actually_detected() -> None:
    """Non-vacuity guard. The H0 end-condition is "inside a References span",
    so if the synthetic entries ever stopped qualifying as entries, the span
    would vanish, the exemption would never fire, and the tests above could
    still pass for an unrelated reason. Assert the span exists."""
    block = _refs_block()
    assert N._find_references_spans(block), (
        "no References span detected in the fixture -- the entry shape no "
        "longer qualifies, so the H0 tests below are not measuring the fix"
    )


def test_recurring_doi_page_footer_is_still_stripped() -> None:
    """Two-sided control B. The rules' LEGITIMATE target must still go.

    A journal stamps its own DOI on every page, so the identical line recurs and
    P0r strips it. Without this assertion the fix could be "keep every short
    line", which is not what was asked for. Real shape behind it:
    ``10.1038/s41467-024-46784-w`` carries 19 such lines, all still removed.
    """
    pages = "\n\n".join(
        f"Page {i} body text about the procedure and its outcome measures.\n"
        f"{_DOI_FOOTER}"
        for i in range(1, 7)
    )
    out = _academic(pages)
    survivors = [ln for ln in out.split("\n") if ln.strip() == _DOI_FOOTER]
    assert not survivors, f"recurring DOI footer survived: {survivors}"


def test_p0r_doi_shape_is_reachable_from_the_shipped_predicate() -> None:
    """The new shape must be wired into the predicate P0r actually calls -- a
    pattern matched only by its own test is not shipped."""
    assert N._looks_like_running_header_or_footer(_DOI_FOOTER)
    assert N._looks_like_running_header_or_footer("DOI: 10.99995/invented.2021.137706")
    assert not N._looks_like_running_header_or_footer(
        "Invented Review of Methods, 62(7-8), 520-531."
    )


def test_deleted_p0_patterns_stay_deleted() -> None:
    """Pins the removal itself: no P0 pattern may match a standalone DOI line
    again. Re-adding one would silently restore the 4%-accuracy behaviour."""
    for line in (
        _DOI_WRAPPED_URL,
        _DOI_WRAPPED_BARE,
        "doi: 10.99996/invented.2017.09.007",
    ):
        matching = [p.pattern for p in N._PAGE_FOOTER_LINE_PATTERNS if p.match(line)]
        assert not matching, f"P0 matches {line!r} again via {matching}"


def test_header_zone_does_not_reach_into_an_entry_list() -> None:
    """H0's 30-line cap is position-only. On a SHORT document the zone reaches
    the bibliography, and no line inside a References span is header furniture.

    This is the shape that exposed the defect: the References heading AND a
    wrapped short-form DOI both sit inside the 30-line zone.
    """
    short = (
        "Short-Form DOIs in Entry Lists: A QA Fixture\n\n"
        "Abstract. A short document whose entry list starts inside the "
        "header zone.\n\n"
        "References\n\n"
        + "\n".join((
            _entry(0, 2024, "https://doi.org/10/aaabbb", wrapped=False),
            _entry(1, 1935, "https://doi.org/10/cccddd", wrapped=False),
            _entry(2, 2016, "https://doi.org/10/eeefff", wrapped=False),
            _entry(3, 2020, "https://doi.org/10/zzzzzz", wrapped=True),
            _entry(4, 2002, _DOI_INLINE_CONTROL, wrapped=False),
        ))
        + "\n"
    )
    # The wrapped DOI must be inside the 30-line zone, or this test silently
    # becomes a P0 test rather than the H0 test it claims to be.
    wrapped_at = next(
        i for i, ln in enumerate(short.split("\n")) if "10/zzzzzz" in ln
    )
    assert wrapped_at < N._HEADER_ZONE_LINES, (
        f"fixture grew: the wrapped DOI is at line {wrapped_at}, outside the "
        f"{N._HEADER_ZONE_LINES}-line header zone, so H0 is not being tested"
    )

    out = _academic(short)
    assert "10/zzzzzz" in out, "short-form DOI deleted inside the header zone"
    for control in ("10/aaabbb", "10/cccddd", "10/eeefff",
                    "10.99992/invented.9280.00441"):
        assert control in out, f"control DOI {control} lost"


def test_colon_led_identifier_line_in_the_header_zone_survives() -> None:
    """A materials DOI introduced by a colon-terminated lead-in is the object of
    a sentence, so it is data rather than a banner. Real shape behind it:
    ``10.15626/MP.2020.2601`` front matter."""
    front_matter = """Journal of Invented Studies, 2022, vol 6, IS.2020.0001
https://doi.org/10.99997/IS.2020.0001
Article type: Original Article

All supplementary files can be accessed at OSF:
https://doi.org/10.99998/OSF.IO/AAAAAA

A Placeholder Title For The Document Under Test

Abstract
Placeholder abstract prose describing the procedure that was carried out.
"""
    out = _academic(front_matter)
    assert "10.99998/osf.io/aaaaaa" in out.lower()


def test_genuine_publisher_landing_page_banner_is_still_stripped() -> None:
    """Two-sided control C. The fix must NOT become "keep every short line". A
    bare publisher landing-page URL carries no DOI grammar and is still
    furniture -- this is what banner pattern 0 exists for."""
    doc = """www.invented-publisher.com/inventedjournal
Article

A Placeholder Title For The Document Under Test

Abstract
Placeholder abstract prose describing the procedure that was carried out.
"""
    out = _academic(doc)
    assert "www.invented-publisher.com/inventedjournal" not in out


def test_doi_identifier_definition_excludes_landing_pages() -> None:
    """The shared identifier definition is what the colon exemption keys on, so
    both of its sides are pinned here rather than left to inference."""
    assert N._DOI_IDENTIFIER_IN_LINE.search("https://doi.org/10.99998/OSF.IO/AAAAAA")
    assert N._DOI_IDENTIFIER_IN_LINE.search("https://doi.org/10/aaabbb")
    assert not N._DOI_IDENTIFIER_IN_LINE.search(
        "http://journal.invented-publisher.com/content/36/10/1318"
    )
    assert not N._DOI_IDENTIFIER_IN_LINE.search(
        "www.invented-publisher.com/inventedjournal"
    )


def test_the_two_doi_regexes_agree_on_a_colon_prefixed_short_form() -> None:
    """L-057 (2026-09-16, docpluck-review). ``_DOI_IDENTIFIER_IN_LINE`` and
    ``_BARE_DOI_IDENTIFIER_LINE`` each carried their own DOI grammar and
    disagreed on ``doi:10/gt3vmw`` -- a ``doi:``-prefixed shortDOI -- matched by
    one and missed by the other, the exact class rule 0b (ONE CONCEPT, ONE
    TABLE) exists to catch. Both now derive from the shared `_DOI_FULL_FORM` /
    `_DOI_SHORT_FORM` pair; pin that they stay in agreement rather than trust
    the comment that says they should."""
    line = "doi:10/gt3vmw"
    assert N._DOI_IDENTIFIER_IN_LINE.search(line), (
        "regression: _DOI_IDENTIFIER_IN_LINE stopped recognising a "
        "doi:-prefixed short-form DOI"
    )
    assert N._BARE_DOI_IDENTIFIER_LINE.match(line), (
        "regression: _BARE_DOI_IDENTIFIER_LINE stopped recognising a "
        "doi:-prefixed short-form DOI"
    )
