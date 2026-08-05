"""Real-PDF regression tests for the KEYWORDS label/value split (run 6, cycle 2).

Defect (reproduced at HEAD on ``xiao_2021_crsp``, 2026-08-05): the synthesized
Introduction began on the **keyword list**, and the keywords section retained
only its own label::

    keywords section  = 'KEYWORDS\\n\\n'                      (10 chars)
    introduction[:70] = 'Decoy effect; decision reversibility; regret; attraction …'

so the rendered document reads as though "Decoy effect; decision reversibility;
…" were the Introduction's opening sentence, and the keywords are lost as
keywords.

Root cause: the keywords branch of
``_synthesize_introduction_if_bloated_front_matter`` cuts at the FIRST ``\\n\\n``
inside the candidate span. Taylor & Francis (and other sidebar-metadata
layouts) serialise the block as ``KEYWORDS`` / blank / values, so the first
paragraph break sits between the LABEL and its own VALUES — not after them.
The branch's comment anticipated a "short keyword line" but never guarded
against the label-then-blank-then-values shape.

Note the heading itself is *synthesized*: the string "Introduction" does not
appear anywhere in this paper's source text. So this is a heading-PLACEMENT
defect, not the front-matter reordering that ``render.py``'s
``_demote_metadata_label_headings`` comment attributes it to.

The fix skips any candidate cut that would leave no keyword CONTENT behind —
keyed on the structural signature, never on the label text or the paper.

Per /docpluck-iterate rule 0d: ships with a ``*_real_pdf`` test exercising the
public library entry point on an actual PDF fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docpluck.sections import extract_sections
from docpluck.sections.core import _is_metadata_label_line
from docpluck.sections.taxonomy import SectionLabel


_PDF_ROOT = Path(__file__).resolve().parents[1] / ".." / "PDFextractor" / "test-pdfs"


def _sections(rel: str):
    pdf = (_PDF_ROOT / rel).resolve()
    if not pdf.is_file():
        pytest.skip(f"fixture not available locally: {rel}")
    res = extract_sections(pdf.read_bytes())
    if isinstance(res, tuple):
        res = res[0]
    return list(getattr(res, "sections", res))


def _one(sections, label: SectionLabel):
    hits = [s for s in sections if getattr(s, "canonical_label", None) is label]
    return hits[0] if hits else None


# ── Contract tests (synthetic, fast) ───────────────────────────────────────


@pytest.mark.parametrize(
    "line", ["KEYWORDS", "Keywords", "Key words", "KEYWORDS:", "keyword"]
)
def test_bare_metadata_labels_detected(line):
    assert _is_metadata_label_line(line)


@pytest.mark.parametrize(
    "line",
    [
        "Decoy effect; decision reversibility; regret",
        # a label that CARRIES its value is not a bare label
        "Keywords: decoy effect; regret",
        "ABSTRACT",
        "Human choice behaviors are susceptible to manipulations",
        "",
        # long line that merely starts with the word
        "Keywords were coded by two independent raters across all conditions",
    ],
)
def test_non_label_lines_rejected(line):
    assert not _is_metadata_label_line(line)


def _first_content_cut(body: str) -> int:
    """Mirror of the cut loop in the keywords branch, so the boundary
    behaviour is pinned independently of the surrounding Section plumbing."""
    search_from = 0
    while True:
        nxt = body.find("\n\n", search_from)
        if nxt < 0:
            return -1
        kept = body[:nxt]
        if [
            ln.strip()
            for ln in kept.split("\n")
            if ln.strip() and not _is_metadata_label_line(ln)
        ]:
            return nxt
        search_from = nxt + 2


@pytest.mark.parametrize(
    "body,expected_kept",
    [
        # the defect shape: label / blank / values
        ("KEYWORDS\n\nDecoy effect; regret\n\nHuman choice...\n\n",
         "KEYWORDS\n\nDecoy effect; regret"),
        # pre-existing shape (value on the label line) must be UNCHANGED
        ("KEYWORDS: decoy; regret\n\nHuman choice...\n\n",
         "KEYWORDS: decoy; regret"),
        # values immediately after the label, no blank between
        ("KEYWORDS\nDecoy effect; regret\n\nHuman choice...\n\n",
         "KEYWORDS\nDecoy effect; regret"),
        # several blanks before the values
        ("KEYWORDS\n\n\n\nDecoy effect; regret\n\nHuman choice...\n\n",
         "KEYWORDS\n\n\n\nDecoy effect; regret"),
    ],
)
def test_cut_lands_after_the_keyword_values(body, expected_kept):
    cut = _first_content_cut(body)
    assert cut >= 0
    assert body[:cut] == expected_kept


@pytest.mark.parametrize(
    "body",
    [
        "KEYWORDS\n\n\n\n",        # label only, no content anywhere
        "KEYWORDS\nDecoy effect",  # no paragraph break at all
    ],
)
def test_degenerate_spans_bail_out_instead_of_cutting(body):
    """No content / no break must leave the sections untouched rather than
    manufacture an empty keywords span."""
    assert _first_content_cut(body) == -1


# ── Real-PDF tests (the rule-0d gate) ──────────────────────────────────────


def test_xiao_keywords_span_carries_its_values_real_pdf():
    """The keywords section must contain the keywords, not just the label."""
    secs = _sections("apa/xiao_2021_crsp.pdf")
    kw = _one(secs, SectionLabel.keywords)
    assert kw is not None, "keywords section not detected"
    text = kw.text or ""
    # the defect left exactly 'KEYWORDS\n\n' (10 chars)
    assert len(text) > 20, f"keywords span collapsed to the label alone: {text!r}"
    assert "Decoy effect" in text
    assert "replication" in text


def test_xiao_introduction_does_not_start_on_the_keyword_list_real_pdf():
    """The synthesized Introduction must begin at the real first sentence."""
    secs = _sections("apa/xiao_2021_crsp.pdf")
    intro = _one(secs, SectionLabel.introduction)
    assert intro is not None, "introduction section not synthesized"
    head = (intro.text or "").lstrip()
    assert not head.startswith("Decoy effect; decision reversibility")
    assert head.startswith("Human choice behaviors are susceptible")


def test_xiao_keyword_values_are_not_duplicated_into_intro_real_pdf():
    """The values belong to keywords only — they must not also open the intro."""
    secs = _sections("apa/xiao_2021_crsp.pdf")
    intro = _one(secs, SectionLabel.introduction)
    assert "attraction effect; replication" not in (intro.text or "")[:200]
