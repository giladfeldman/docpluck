"""Regression test for D4 — Cambridge / JDM publisher boilerplate splice (cycle 5, v2.4.37).

The APA Phase-5d sweep found the Cambridge University Press per-page footer
("https://doi.org/10.1017/jdm.<id> Published online by Cambridge University
Press") and the open-access licence sentence ("This is an Open Access
article, distributed under the terms of the Creative Commons Attribution
licence ... properly cited.") spliced MID-SENTENCE into the body prose of
every Cambridge JDM paper.

Fix (v2.4.37): two patterns added to `normalize.py` W0 watermark-strip —
non-anchored so they catch the boilerplate whether it stands on its own line
or is glued inline. Removing it rejoins the split body sentence.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.normalize import NormalizationLevel, normalize_text

TEST_PDFS = Path(__file__).resolve().parents[1].parent / "PDFextractor" / "test-pdfs"


def _norm(text: str) -> str:
    out, _ = normalize_text(text, NormalizationLevel.academic)
    return out


# ── Unit tests on the W0 strip ──────────────────────────────────────────

def test_strips_cambridge_running_footer_inline():
    src = (
        "In these contexts, individuals usually fail to "
        "https://doi.org/10.1017/jdm.2022.2 Published online by Cambridge "
        "University Press notice the absence of relevant information."
    )
    out = _norm(src)
    assert "Cambridge University Press" not in out
    assert "doi.org/10.1017" not in out
    # The split sentence must rejoin.
    assert "fail to notice the absence" in " ".join(out.split())


def test_strips_open_access_licence_sentence():
    src = (
        "consumers commonly find themselves Association for Decision Making. "
        "This is an Open Access article, distributed under the terms of the "
        "Creative Commons Attribution licence "
        "(https://creativecommons.org/licenses/by/4.0), which permits "
        "unrestricted re-use, distribution and reproduction, provided the "
        "original article is properly cited. having to make decisions."
    )
    out = " ".join(_norm(src).split())
    assert "Open Access article" not in out
    assert "Creative Commons" not in out
    assert "Association for Decision Making" not in out
    assert "consumers commonly find themselves" in out
    assert "having to make decisions" in out


def test_plain_prose_untouched():
    src = "Participants read a vignette and rated their confidence on a 7-point scale."
    assert _norm(src).strip() == src


# ── Real-PDF regression test ────────────────────────────────────────────

@pytest.mark.parametrize("stem", ["jdm_m.2022.2", "jdm_.2023.15"])
def test_no_cambridge_boilerplate_in_render(stem):
    from docpluck.render import render_pdf_to_markdown

    pdf = TEST_PDFS / "apa" / f"{stem}.pdf"
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    md = render_pdf_to_markdown(pdf.read_bytes())
    assert "Published online by Cambridge University Press" not in md, (
        f"{stem}: Cambridge running footer leaked into render"
    )
    assert "This is an Open Access article" not in md, (
        f"{stem}: open-access licence boilerplate leaked into render"
    )
