"""A CRediT contribution line is never a section heading.

PLOS-style Author Contributions print one CRediT role per line:

    Formal analysis: Julia F. van der Meulen, Ruben G. Duijnhoven.
    Funding acquisition: Julia F. van der Meulen, Marlies Y. Bongers, ...
    Methodology: Julia F. van der Meulen, ...

The canonical-heading passes matched the leading word of two of these lines --
``Funding`` (a canonical heading) and ``Methodology`` (an alias for Methods) --
and the render then cut the heading word out of the body: the line printed as
``acquisition: Julia F. ...`` and ``Methodology`` lost its colon and was split
from its names. Measured on 10.1371/journal.pmed.1004323 (plos_med_1).
"""

from __future__ import annotations

import pytest

from docpluck.sections.annotators.text import annotate_text

CREDIT_BLOCK = (
    "Author Contributions\n"
    "\n"
    "Conceptualization: Julia F. van der Meulen, Marlies Y. Bongers.\n"
    "Formal analysis: Julia F. van der Meulen, Ruben G. Duijnhoven.\n"
    "Funding acquisition: Julia F. van der Meulen, Marlies Y. Bongers, Lucilla E. Overdijk, Celine\n"
    "M. Radder, Sjors F. P. J. Coppus, Helen S. Kok.\n"
    "Investigation: Julia F. van der Meulen.\n"
    "Methodology: Julia F. van der Meulen, Marlies Y. Bongers, Jaklien C. Leemans, Ruben G.\n"
    "Duijnhoven, Sjors F. P. J. Coppus, Helen S. Kok.\n"
    "Software: Robert A. de Leeuw.\n"
    "\n"
    "References\n"
)


def test_credit_role_lines_emit_no_heading():
    texts = [h.text for h in annotate_text(CREDIT_BLOCK)]
    assert "Funding" not in texts, texts
    assert "Methodology" not in texts, texts
    # The real headings around the list still register.
    assert "Author Contributions" in texts, texts
    assert "References" in texts, texts


def test_real_funding_heading_still_detected():
    # Two-sided: the canonical Funding heading itself must keep working.
    text = (
        "We thank the participants.\n"
        "\n"
        "Funding\n"
        "The author(s) received no specific funding for this work.\n"
    )
    assert "Funding" in [h.text for h in annotate_text(text)]
    text2 = (
        "We thank the participants.\n"
        "Funding: This work was supported by grant 123 from the Foundation.\n"
    )
    assert "Funding" in [h.text for h in annotate_text(text2)]


def test_lone_methodology_heading_still_detected():
    # A Methodology heading that is not part of a contribution list survives.
    text = (
        "This concludes the introduction.\n"
        "\n"
        "Methodology\n"
        "\n"
        "We recruited 200 participants from an online panel for this study.\n"
    )
    assert "Methodology" in [h.text for h in annotate_text(text)]


def test_plos_med_author_contributions_keep_role_words():
    from docpluck.render import render_pdf_to_markdown
    from docpluck.testing import require_corpus_pdf

    pdf = require_corpus_pdf("vancouver/plos_med_1.pdf")
    md = render_pdf_to_markdown(pdf.read_bytes())
    assert "Funding acquisition: Julia F. van der Meulen" in md
    assert "Methodology: Julia F. van der Meulen" in md
    assert "\nacquisition: Julia" not in md
