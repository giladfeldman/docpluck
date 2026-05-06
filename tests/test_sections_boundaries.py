"""End-of-section boundary patterns (lifted from CitationGuard endPatterns)."""

from docpluck.sections.boundaries import is_section_boundary


def test_author_bio_caps_pattern_matches():
    assert is_section_boundary("HERMAN AGUINIS is the senior")
    assert is_section_boundary("JANE DOE is a Professor at...")


def test_corresponding_author_matches():
    assert is_section_boundary("Corresponding author: jane@example.org")


def test_email_contact_matches():
    assert is_section_boundary("Email: alice@example.org")
    assert is_section_boundary("E-mail: alice@example.org")


def test_orcid_matches():
    assert is_section_boundary("ORCID: 0000-0001-2345-6789")


def test_editorial_metadata_matches():
    assert is_section_boundary("Accepted by Editor X. on 2023-01-01")
    assert is_section_boundary("Action Editor: Y. Z.")
    assert is_section_boundary("Received: 2024-01-01")


def test_figure_caption_matches():
    assert is_section_boundary("Figure 1. Distribution of effect sizes.")
    assert is_section_boundary("Table 3. Means and standard deviations.")


def test_normal_body_text_does_not_match():
    assert not is_section_boundary("In our results, we observed that the effect was strong.")
    assert not is_section_boundary("The methods used in this study include...")
    assert not is_section_boundary("Smith, J. (2020). A paper title.")


def test_editorial_metadata_requires_colon_for_ambiguous_words():
    # "Published in Journal..." is body text, not a section boundary
    assert not is_section_boundary("Published in Journal of Personality 2020")
    assert not is_section_boundary("Revised and resubmitted in January")
    # but with a colon, it IS editorial metadata
    assert is_section_boundary("Published: 2024-06-15")
    assert is_section_boundary("Revised: 2024-03-01")
