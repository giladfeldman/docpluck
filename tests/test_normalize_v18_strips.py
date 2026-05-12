"""Tests for the v1.8.0 document-shape strip passes: H0, T0, P0.

Ported from docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py
(iter-25 / iter-26 / iter-27 / iter-33 / iter-31 blocks).
"""

from docpluck.normalize import (
    NormalizationLevel,
    NORMALIZATION_VERSION,
    _strip_document_header_banners,
    _strip_toc_dot_leader_block,
    _strip_page_footer_lines,
    normalize_text,
)


def test_version_bumped():
    assert NORMALIZATION_VERSION == "1.8.0"


# ── H0: header banner strip ────────────────────────────────────────────────


def test_h0_strips_hhs_public_access_block():
    text = "HHS Public Access\nAuthor manuscript\nPublished in final edited form as: Demography. 2023 ...\n\nReal Title Goes Here\nAbstract\n\nbody"
    out = _strip_document_header_banners(text)
    assert "HHS Public Access" not in out
    assert "Author manuscript" not in out
    assert "Published in final edited form as" not in out
    assert "Real Title Goes Here" in out
    assert "Abstract" in out


def test_h0_strips_arxiv_banner():
    text = "arXiv:2401.12345v2 [cs.CL] 19 Feb 2024\n\nTitle of Paper\nAbstract"
    out = _strip_document_header_banners(text)
    assert "arXiv:" not in out
    assert "Title of Paper" in out


def test_h0_strips_aom_masthead():
    text = "r Academy of Management Journal 2020, Vol. 63, No. 2, 351–381.\nhttps://doi.org/10.5465/amj.2018.0023\nTitle of Paper\nAbstract"
    out = _strip_document_header_banners(text)
    assert "Academy of Management" not in out
    assert "Title of Paper" in out


def test_h0_preserves_title_when_unknown():
    # Title-like lines that don't match any explicit pattern must stay.
    text = "Some Unknown Multi-Word Title\nAuthor One Author Two\nAffiliation Line\n\nAbstract"
    out = _strip_document_header_banners(text)
    assert "Some Unknown Multi-Word Title" in out
    assert "Author One Author Two" in out


def test_h0_only_acts_in_header_zone():
    # Banner-pattern-like text appearing AFTER the 30-line cap is preserved.
    pre_lines = ["Body line %d" % i for i in range(35)]
    text = "\n".join(pre_lines) + "\nHHS Public Access"
    out = _strip_document_header_banners(text)
    # The HHS line is outside the header zone — stays.
    assert "HHS Public Access" in out


def test_h0_idempotent():
    text = "HHS Public Access\nAuthor manuscript\nTitle Line\nAbstract\nbody"
    once = _strip_document_header_banners(text)
    twice = _strip_document_header_banners(once)
    assert once == twice


# ── T0: TOC dot-leader strip ───────────────────────────────────────────────


def test_t0_strips_toc_with_dot_leaders():
    text = (
        "Table of Contents\n\n"
        "Background ____________ 17\n\n"
        "Methods ____________ 19\n\n"
        "Results ____________ 24\n\n"
        "Real Body Heading\n\n"
        "body text that is real and should stay verbatim no underscores here"
    )
    out = _strip_toc_dot_leader_block(text)
    assert "____" not in out
    assert "Table of Contents" not in out
    assert "Real Body Heading" in out
    assert "body text" in out


def test_t0_skips_body_paragraphs_far_from_top():
    # Underscores after line 100 must not be touched.
    pre = "\n\n".join(["paragraph %d" % i for i in range(110)])
    text = pre + "\n\nA paragraph ____ with underscores deep in the body"
    out = _strip_toc_dot_leader_block(text)
    assert "with underscores deep in the body" in out


def test_t0_no_op_when_no_dot_leader():
    text = "Regular paragraph one\n\nRegular paragraph two"
    out = _strip_toc_dot_leader_block(text)
    assert out == text


# ── P0: page-footer line strip ─────────────────────────────────────────────


def test_p0_strips_corresponding_author_email_block():
    text = (
        "body sentence one and it goes\n"
        "aETH Zurich\n"
        "Corresponding Author: Enzo Nussio, Center for Security Studies, ETH Zurich\n"
        "Email: enzo.nussio@sipo.gess.ethz.ch\n"
        "body sentence two continues here"
    )
    out = _strip_page_footer_lines(text)
    assert "aETH Zurich" not in out
    assert "Corresponding Author:" not in out
    assert "Email:" not in out
    assert "body sentence one" in out
    assert "body sentence two" in out


def test_p0_strips_jama_running_header():
    text = (
        "real body line\n"
        "JAMA Network Open. 2023;6(10):e2339337. doi:10.1001/jamanetworkopen.2023.39337\n"
        "another real body line"
    )
    out = _strip_page_footer_lines(text)
    assert "JAMA Network Open. 2023" not in out
    assert "real body line" in out
    assert "another real body line" in out


def test_p0_strips_page_n_lines():
    text = "real line\nPage 27\nanother line"
    out = _strip_page_footer_lines(text)
    assert "Page 27" not in out
    assert "real line" in out
    assert "another line" in out


def test_p0_strips_pmc_supplementary_footer():
    text = (
        "body\n"
        "ELECTRONIC SUPPLEMENTARY MATERIAL The online version of this article (https://doi.org/10.x/y) contains supplementary material.\n"
        "body continues"
    )
    out = _strip_page_footer_lines(text)
    assert "ELECTRONIC SUPPLEMENTARY MATERIAL" not in out
    assert "body continues" in out


def test_p0_idempotent():
    text = "real\nPage 27\n© 2024 Some Publisher\nreal"
    once = _strip_page_footer_lines(text)
    twice = _strip_page_footer_lines(once)
    assert once == twice


# ── Integration: end-to-end through normalize_text at standard ─────────────


def test_normalize_at_standard_runs_h0_t0_p0():
    text = "HHS Public Access\nAuthor manuscript\nReal Title\n\nbody body body body"
    out, report = normalize_text(text, NormalizationLevel.standard)
    assert "HHS Public Access" not in out
    assert "Real Title" in out
    assert "H0_header_banner_strip" in report.steps_applied
    assert "T0_toc_dot_leader_strip" in report.steps_applied
    assert "P0_page_footer_strip" in report.steps_applied
    # H0 actually fired, so it should be in steps_changed too.
    assert "H0_header_banner_strip" in report.steps_changed


def test_normalize_at_none_skips_h0_t0_p0():
    text = "HHS Public Access\nAuthor manuscript\nReal Title\nbody"
    out, report = normalize_text(text, NormalizationLevel.none)
    # At level=none nothing is applied, including the new strips.
    assert out == text
    assert "H0_header_banner_strip" not in report.steps_applied
