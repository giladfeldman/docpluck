"""verify_corpus tag C fires on a concatenated caption, not on a long one.

WHY. Tag C was "longest figure caption > 800 chars", a proxy for the v2.3.0
Bug 4 leak (one figure's caption running into the next). It false-FAILed every
release since 2.4.145 on 10.1038/s41467-023-43885-w Fig. 5, an 864-char legend
that is correct against printed p7, and it could only see captions whose line
starts with "*Figure": on 2026-10-02 it read 14 of 116 figures in the 28-paper
corpus, because most renders put the label in a ``### Figure N`` heading.

MEASURED 2026-10-02 on the 28 corpus renders: 116 of 116 captions read; the new
rule fires on 0 real captions and on 0 of 27 body sentences that open with a
figure/table reference; splicing each paper's real adjacent captions (92 pairs)
is caught 92 times. Strings below are neutral: no paper text lives in this repo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import verify_corpus as vc  # noqa: E402


# Four H2 sections, so the unrelated "few sections" tag S stays quiet and the
# status asserted below is tag C's (or c's) alone.
_PAPER = "## Introduction\n\n## Method\n\n## Results\n\n## Discussion\n\n"


@pytest.mark.parametrize("md", [
    "### Figure 2\n*Alpha by condition. Error bars are 95% CIs. Figure 3. Beta by age.*",
    "### Figure 1\n*Figure 1 | Alpha by condition. Figure 2 | Beta by age.*",
    "### Figure 4\n*Alpha by condition. Figure 5 Beta of the second study.*",
    "### Figure 1\n*Figure 1. Figure 2.*",
    "*Figure 2. Alpha by condition. Table 3. Beta by age.*",
])
def test_a_second_caption_start_fails(md):
    status, m, tags = vc._classify("x", _PAPER + md, None)
    assert m["concatenated_captions"] == 1
    assert tags == ["C"] and status == "FAIL"


@pytest.mark.parametrize("md", [
    "### Figure 5\n*Alpha as shown in Figure 3. The bars (see Fig. 2). Gamma.*",
    "### Figure 1\n*Figure 1 | Alpha. See Table 2 for details.*",
    "Body text. Figure 2 illustrates the effect. Table 4 presents the means.",
])
def test_an_in_sentence_reference_passes(md):
    status, m, tags = vc._classify("x", _PAPER + md, None)
    assert m["concatenated_captions"] == 0
    assert tags == [] and status == "PASS"


def test_a_long_single_caption_is_a_warning_not_a_failure():
    md = _PAPER + "### Figure 5\n*Figure 5 | " + "Alpha beta gamma delta. " * 40 + "*"
    status, m, tags = vc._classify("x", md, None)
    assert m["longest_fig_caption_chars"] > 800
    assert tags == ["c"] and status == "WARN"


def test_a_caption_under_a_figure_heading_is_measured():
    md = "### Figure 1\n*Alpha by condition.*\n\n### Figure 2\n*Beta.*"
    assert vc._metrics(md)["longest_fig_caption_chars"] == len("*Alpha by condition.*")
