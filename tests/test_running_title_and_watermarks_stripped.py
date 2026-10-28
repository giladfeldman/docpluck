"""Running titles and publisher watermarks do not stay in body text.

Rasterised 2026-10-27:

* 10.1525/collabra.77608 prints its title, cut short ("... Peters et al. (2006)
  With an..."), at the top of its recto pages. It stayed in the text on most
  pages, between and inside sentences and glued onto reference entries, and a
  consumer read its "Peters et al. (2006)" as a citation.
* 10.1037/a0012616 and 10.1037/0278-6133.15.3.167 carry the APA PsycNET
  watermark sideways in the margin of every page.
* 10.1177/0956797615601103 carries Sage's old "Downloaded from pss.sagepub.com at
  ... on October 30, 2015" stamp.
"""
from __future__ import annotations

import pytest

from docpluck.normalize import (
    NormalizationLevel,
    _strip_page_top_running_title,
    normalize_text,
)

TITLE = "Revisiting the Links Between Numeracy and Decision Making: Replication Report of Peters et al. (2006) With an Extension"
RUN = "Revisiting the Links Between Numeracy and Decision Making: Replication Report of Peters et al. (2006) With an..."


def _doc(n_pages=12, run=RUN, first_page_title=TITLE):
    pages = [f"Collabra: Psychology\n{first_page_title}\nAuthor One\nAbstract text here."]
    for i in range(1, n_pages):
        head = run if i % 2 == 0 else "Author One"
        pages.append(f"{head}\nBody sentence {i} about numeracy continues on this page.\nMore body {i}.")
    return "\f".join(pages)


def test_running_title_is_removed_from_later_pages_only():
    text = _doc()
    out, removed = _strip_page_top_running_title(text)
    assert removed == {RUN: 5}                                 # pages 2, 4, 6, 8, 10
    assert RUN not in out.split("\f", 1)[1]
    assert out.split("\f")[0] == text.split("\f")[0]          # page 1 untouched
    assert "Body sentence 2 about numeracy" in out


def test_needs_the_title_echo_and_the_page_position():
    # A repeated page-top line that is not the title (a table header) stays.
    hdr = "Variable Study one sample Study two sample Total sample size"
    out, removed = _strip_page_top_running_title(_doc(run=hdr))
    assert removed == {} and hdr in out
    # Under the furniture floor P0q uses (5 pages): stays. 10 pages carry the
    # title on pages 2, 4, 6, 8 -- four, so nothing is taken.
    out, removed = _strip_page_top_running_title(_doc(n_pages=10))
    assert removed == {} and out.count(RUN) == 4


def test_a_title_printed_twice_on_a_page_is_left_alone():
    # The header-above-title contract P0q pins (2026-09-01): a line printed
    # twice on one page -- page 1 included -- is not a running head, and P0t
    # takes nothing either.
    text = _doc(first_page_title=RUN + "\n" + RUN)
    out, removed = _strip_page_top_running_title(text)
    assert removed == {} and out == text


def test_the_strip_is_reported_by_line_through_normalize_text():
    out, report = normalize_text(_doc(), NormalizationLevel.academic)
    assert RUN not in out.split("\f", 1)[1]
    assert report.changes_made.get("running_titles_stripped") == 5
    assert report.fallbacks.get("running_title_stripped") == 5, report.fallbacks
    assert report.fallbacks.get("running_title_kept_on_page_1") == 1, report.fallbacks
    assert RUN[:120] in report.fallback_details["running_title_stripped"]


def test_apa_watermark_and_sage_stamp_are_removed():
    body = ("The participants were randomly assigned. This document is copyrighted by the "
            "American Psychological Association or one of its allied publishers.\n"
            "This article is intended solely for the personal use of the individual user and "
            "is not to be disseminated broadly.\nResults followed.\n"
            "Downloaded from pss.sagepub.com at UNIV OF LETHBRIDGE on October 30, 2015\n")
    out, _ = normalize_text(body, NormalizationLevel.academic)
    assert "copyrighted by the American Psychological" not in out
    assert "intended solely for the personal use" not in out
    assert "Downloaded from pss.sagepub.com" not in out
    assert "The participants were randomly assigned." in out and "Results followed." in out


def _render(key):
    from docpluck.testing.corpus import custody_path
    from docpluck.render import render_pdf_to_markdown
    p = custody_path("fulltext", key + ".pdf")
    if not p.is_file():
        pytest.skip(f"{key} not held")
    md = render_pdf_to_markdown(p.read_bytes())
    return md[0] if isinstance(md, tuple) else md


def test_real_collabra_running_title_gone():
    md = _render("10.1525__collabra.77608")
    body = md.split("\n", 6)[-1]   # past the rendered title
    assert "Replication Registered Report of Peters et al. (2006) With an..." not in body
    assert body.count("Peters et al. (2006)") >= 3   # the real citations stay


def test_real_apa_watermark_gone():
    md = _render("10.1037__a0012616")
    assert "This document is copyrighted by the American Psychological Association" not in md


def test_real_abstract_still_found_once_the_watermark_is_gone():
    # The page prints no "Abstract" heading; the abstract is inferred from the
    # first long prose paragraph. Removing the ~220-char watermark must not
    # shrink the leading span below the inference floor and lose the abstract.
    from docpluck.testing.corpus import custody_path
    from docpluck.sections import extract_sections
    p = custody_path("fulltext", "10.1037__a0012616.pdf")
    if not p.is_file():
        pytest.skip("10.1037/a0012616 not held")
    secs = extract_sections(p.read_bytes()).sections
    ab = next((s for s in secs if s.label == "abstract"), None)
    assert ab is not None, [s.label for s in secs[:4]]
    assert "Previous studies have reported" in ab.text
    md = _render("10.1037__a0012616")
    assert "## Abstract" in md


def test_heading_below_a_dropped_title_keeps_its_blank_line():
    # 10.1525/collabra.77608 p11 opens "RUN" / "" / "Replication: Dichotomized
    # numeracy". The heading must still sit after a blank line once the title
    # is gone, or the section detector no longer sees a heading there.
    pages = [f"Collabra: Psychology\n{TITLE}\nAuthor One\nAbstract text here."]
    for i in range(1, 12):
        pages.append(f"{RUN}\n\nHeading {i}\n\nBody sentence {i}." if i % 2 == 0
                     else f"Author One\nBody sentence {i}.")
    out, removed = _strip_page_top_running_title("\f".join(pages))
    assert removed == {RUN: 5}
    assert "\f\n\nHeading 2\n\nBody sentence 2." in out, repr(out)


def test_real_collabra_headings_survive_the_title_strip():
    from docpluck.testing.corpus import custody_path
    from docpluck.sections import extract_sections
    p = custody_path("fulltext", "10.1525__collabra.77608.pdf")
    if not p.is_file():
        pytest.skip("10.1525/collabra.77608 not held")
    labels = [s.label for s in extract_sections(p.read_bytes()).sections]
    assert "discussion" in labels and "references" in labels, labels
    md = _render("10.1525__collabra.77608")
    assert "### Replication: Dichotomized numeracy" in md
