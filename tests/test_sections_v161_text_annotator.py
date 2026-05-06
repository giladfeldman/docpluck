"""v1.6.1 text annotator: canonical headings followed by body on same line."""

from docpluck.sections.annotators.text import annotate_text


def _texts_at(hints, label):
    return [h.text for h in hints if h.text == label]


def test_canonical_heading_followed_by_body_on_same_line():
    """The dominant publishing pattern: heading + first paragraph on one line."""
    text = (
        "Some title block.\n"
        "\n"
        "Abstract Jordan et al., 2011, demonstrated that people underestimated negative emotions.\n"
        "\n"
        "Keywords emotional pluralistic ignorance, positive emotions, well-being\n"
        "\n"
        "Introduction\n"
        "Background\n"
        "A growing body of literature has documented...\n"
    )
    hints = annotate_text(text)
    canonical_hits = [h.text for h in hints]
    assert "Abstract" in canonical_hits
    assert "Keywords" in canonical_hits
    assert "Introduction" in canonical_hits
    assert "Background" in canonical_hits


def test_canonical_word_inside_body_text_not_emitted():
    """Body usages like 'abstract concept' or mid-sentence 'methods' must not match."""
    text = (
        "Method\n"
        "We used the abstract method to investigate this.\n"
        "Methods are described in detail. Several methods were employed.\n"
    )
    hints = annotate_text(text)
    # Only the heading-position 'Method' should be picked up.
    method_hits = [h for h in hints if h.text == "Method"]
    assert len(method_hits) == 1, f"got {[h.text for h in hints]}"


def test_lowercase_canonical_word_at_paragraph_start_rejected():
    """Lowercase 'abstract' even at paragraph start is body text, not a heading."""
    text = (
        "Some intro line.\n"
        "\n"
        "abstract concept of fairness in psychology\n"
    )
    hints = annotate_text(text)
    assert not any(h.text.lower() == "abstract" for h in hints), \
        f"lowercase 'abstract' should not be emitted; got {[h.text for h in hints]}"


def test_references_at_paragraph_start_with_body_on_same_line():
    """The `References` headers in real PSPB papers often have first ref on same line."""
    text = (
        "Last line of discussion.\n"
        "\n"
        "References Smith, J. (2020). A paper on something. Journal, 10, 1-20.\n"
        "Jones, K. (2021). Another paper.\n"
    )
    hints = annotate_text(text)
    refs_hits = [h for h in hints if h.text == "References"]
    assert len(refs_hits) == 1


def test_acknowledgments_after_blank_line():
    text = (
        "Last line of discussion.\n"
        "\n"
        "Acknowledgments We thank Nikolay Petrov for assistance.\n"
        "\n"
        "Funding The author(s) disclosed receipt of the following financial support.\n"
    )
    hints = annotate_text(text)
    texts = [h.text for h in hints]
    assert "Acknowledgments" in texts
    assert "Funding" in texts


def test_canonical_heading_after_period_newline_no_blank_line():
    """Real PSPB pattern: paragraph ends with period, then heading on next line, no blank line between."""
    text = (
        "...estimations and well-being.\n"
        " Acknowledgments We thank Nikolay Petrov for assistance.\n"
        "...for final submission.\n"
        " Author Contributions Ho Ching Ip: Conceptualization.\n"
        "...this article.\n"
        " Funding The author(s) disclosed receipt of financial support.\n"
    )
    hints = annotate_text(text)
    texts = [h.text for h in hints]
    assert "Acknowledgments" in texts
    assert "Author Contributions" in texts
    assert "Funding" in texts


def test_canonical_word_inside_credit_taxonomy_list_not_emitted():
    """CRediT taxonomy role like 'Funding acquisition' appears mid-sentence in real
    APA papers (inside the Author Contributions body), never at line-start.  When
    it's in the middle of a line — i.e., not following any newline — it must not
    be detected as a heading."""
    text = (
        "Author Contributions Ho Ching Ip: Conceptualization, Data curation,"
        " Funding acquisition; Preregistration peer review;\n"
    )
    hints = annotate_text(text)
    # 'Funding' is mid-sentence — it follows no newline, so neither Pass 1a nor
    # Pass 1b should match it.  Only 'Author Contributions' (which has a Capital
    # body following it) should be detected.
    funding_hits = [h for h in hints if h.text == "Funding"]
    assert len(funding_hits) == 0, f"got {[h.text for h in hints]}"


def test_canonical_heading_with_lowercase_body_caught_by_blank_line_pred():
    """`Keywords emotional pluralistic ignorance...` — lowercase body, but
    blank line before. Should detect."""
    text = (
        "...data, and code: https://osf.io/bwmtr/\n"
        "\n"
        " Keywords emotional pluralistic ignorance, positive emotions, well-being\n"
        "\n"
        "Introduction\n"
        "Background\n"
    )
    hints = annotate_text(text)
    texts = [h.text for h in hints]
    assert "Keywords" in texts, f"got {texts}"


def test_credit_table_methodology_row_not_emitted():
    """CRediT author-contribution tables list 'Methodology' as a row label
    followed by a single-letter 'X' cell. That's a table cell, not a section heading."""
    text = (
        "Some discussion paragraph.\n"
        "\n"
        "Conceptualization\n"
        "\n"
        "X\n"
        "\n"
        "Pre-registrations\n"
        "\n"
        "X\n"
        "\n"
        "Methodology\n"
        "\n"
        "X\n"
        "\n"
        "Pre-registration peer review\n"
    )
    hints = annotate_text(text)
    # Methodology in this context should not be emitted as a canonical hint.
    assert not any(h.text == "Methodology" for h in hints), \
        f"Methodology should not be detected when followed by 1-char table cell; got {[h.text for h in hints]}"


def test_real_heading_followed_by_paragraph_still_emitted():
    """A canonical Methods heading followed by paragraph body text is still detected.

    Note: 'Methodology' was removed from the canonical taxonomy in v1.6.1 (it is
    a subsection label in APA papers, not a top-level section).  'Method' and
    'Methods' remain canonical and must still be emitted by the text annotator.
    """
    text = (
        "...end of intro.\n"
        "\n"
        "Method\n"
        "\n"
        "We describe our method in detail. The participants were recruited from a university subject pool. We used a 2x2 design.\n"
    )
    hints = annotate_text(text)
    assert any(h.text == "Method" for h in hints), \
        f"Canonical 'Method' heading should still be detected; got {[h.text for h in hints]}"
