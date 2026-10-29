"""The repeated-line strip must not take the first line of a repeated caption.

## The defect, measured 2026-10-28 on `ieee_access_2.pdf`

Figures 6-29 of that paper share one caption, wrapped across lines. Its first
line, `RRMSE percentage across parameter ranges of [0, 1] for each respective
parameter with γ`, is printed once on each of 24 pages, which is the shape of a
running header. The once-per-page arm of the strip (rule 0g) took 23 of the 24
copies and left the continuation behind, so 23 captions began with
`the y-axis of each subfigure, β the x-axis of each subfigure`: the caption's
subject was deleted from every figure but the first, on pass 1.

The discriminator is guard (d) in `_normalize_text`: a repeated line whose next
line opens with the same words in at least 80% of its copies, where that next
line is not being stripped too, is one passage repeated, not furniture. It is
typographic: it reads which line the renderer placed next. The follower must
carry a word and not be a URL: over the 125-PDF corpus the only lines this
refusal spared before that check were content (this caption; row labels in
10.1177/23780231251314667) or furniture whose second line is a DOI URL,
`(2023) 13:23018 |` or a lone `|` (9 papers). After it, only the content.
That check was fitted to that corpus; it is an observation, not a law.
"""

from __future__ import annotations

from docpluck.extract import extract_pdf
from docpluck.normalize import PAGE_BREAK, NormalizationLevel, normalize_text
from docpluck.testing import require_corpus_pdf

_IEEE2 = "ieee/ieee_access_2.pdf"
_CAPTION_HEAD = "RRMSE percentage across parameter ranges"
_CAPTION_TAIL = "the y-axis of each subfigure"


def _norm(text: str):
    out, report = normalize_text(text, NormalizationLevel.academic)
    return out, report


def test_every_copy_of_a_repeated_caption_keeps_its_first_line():
    raw, _ = extract_pdf(require_corpus_pdf(_IEEE2).read_bytes())
    n_raw = raw.count(_CAPTION_HEAD)
    assert n_raw == 24, f"fixture changed: {n_raw} caption copies in the raw text"
    out, report = _norm(raw)
    assert out.count(_CAPTION_HEAD) == n_raw, (
        "the strip deleted the first line of a repeated figure caption"
    )
    assert out.count(_CAPTION_HEAD) == out.count(_CAPTION_TAIL)
    kept = report.fallback_details.get("repeated_line_kept_continued_block", {})
    assert any(k.startswith(_CAPTION_HEAD) for k in kept), (
        "the refusal must be named in the report, not silent"
    )


def test_the_watermark_on_the_same_paper_is_still_removed():
    """Two-sided: the veto must not switch the strip off on this paper."""
    raw, _ = extract_pdf(require_corpus_pdf(_IEEE2).read_bytes())
    out, _ = _norm(raw)
    assert raw.count("Author Manuscript") > 200
    assert out.count("Author Manuscript") == 1


_SOCIUS4 = "asa/socius_4.pdf"  # 10.1177/23780231251314667


def test_a_row_label_shared_by_five_tables_survives_in_each_table():
    """`Race (reference: White)` heads the race rows of five separate tables
    (Tables 4, 5A, 5B, 5C and one on page 28). Taking four copies leaves four
    tables listing `Black`, ... with no reference category, so their race
    coefficients cannot be read."""
    raw, _ = extract_pdf(require_corpus_pdf(_SOCIUS4).read_bytes())
    out, _ = _norm(raw)
    # The raw layer prints `25–34` with an en dash; normalization makes it ASCII.
    for label in ("Race (reference: White)", "Age (reference: 25"):
        assert raw.count(label) == 5, f"fixture changed: {label!r}"
        assert out.count(label) == 5, f"{label!r} deleted from some tables"


def _pages(block: list[str], n_pages: int, varying_body: bool = True) -> str:
    pages = []
    for i in range(n_pages):
        lines = [(PAGE_BREAK if i else "") + block[0], *block[1:]]
        lines += [
            f"Body sentence {i}-{j} carrying ordinary prose for page {i}."
            if varying_body else "Body sentence carrying ordinary prose."
            for j in range(4)
        ]
        pages.append("\n".join(lines))
    return "\n".join(pages)


def test_a_running_header_followed_by_varying_body_is_still_removed():
    header = "Journal of Measured Things Quarterly"
    out, _ = _norm(_pages([header], 6))
    assert out.count(header) == 1


def test_a_two_line_running_header_is_still_removed_as_a_pair():
    first, second = "Journal of Measured Things Quarterly", "Volume Twelve Issue Three"
    out, _ = _norm(_pages([first, second], 6))
    assert out.count(first) == 1
    assert out.count(second) == 1


def test_the_veto_cascades_through_a_three_line_block():
    """Pins the cascade AND its accepted cost (consult round 2026-10-28, Sonnet).

    Lines A and B qualify for the strip on every page; line C is spared by the
    year-in-parentheses guard and stays. Judged once, B is kept (C follows it)
    while A is stripped, because A's follower B was still in the strip set: an
    orphaned B in every copy. The cascade keeps A as well. For a running head
    like this one that means visible furniture in every copy, the reversible
    direction; a passage's first line deleted would not be reversible.
    """
    a = "Journal of Measured Things Quarterly"
    b = "Volume Twelve Issue Three"
    c = "Psychological Science (2021)"
    out, report = _norm(_pages([a, b, c], 6))
    assert out.count(c) == 6, "fixture: guard (a) should spare line C"
    assert out.count(b) == 6
    assert out.count(a) == 6, "B was kept but A, the line before it, was stripped"
    kept = report.fallback_details.get("repeated_line_kept_continued_block", {})
    assert a in kept and b in kept
