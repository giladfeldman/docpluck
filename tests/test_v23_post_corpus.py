"""Tests for v2.3.0 fixes discovered via scripts/verify_corpus.py.

Each test corresponds to a concrete regression or bug the corpus runner
caught on real PDFs. The tests are synthetic so they run fast and don't
touch the filesystem; they reproduce the minimal failure shape.
"""

from __future__ import annotations

from docpluck.extract_structured import _extract_caption_text
from docpluck.render import (
    _locate_caption_anchor,
    _pretty_label,
)
from docpluck.tables.camelot_extract import _pick_best_per_page


# ---------------------------------------------------------------------------
# 1. _pick_best_per_page lattice 1×1 / 1×col artifact filter
# ---------------------------------------------------------------------------


class _StubCamelotTable:
    """Just enough surface to look like a Camelot table to ``_pick_best_per_page``."""

    def __init__(self, page: int, n_rows: int, n_cols: int, accuracy: float):
        self.page = page
        self.accuracy = accuracy
        self.df = _StubDF(n_rows, n_cols)


class _StubDF:
    def __init__(self, n_rows: int, n_cols: int):
        self._rows = n_rows
        self.columns = list(range(n_cols))

    def __len__(self):
        return self._rows


def test_pick_best_skips_lattice_1x1_artifact():
    """jama_open_1 regression: lattice returns 1×1 artifacts on pages that
    have real stream tables. Without the 2×2 size filter the artifact
    "wins" the page and the real table is discarded."""
    stream = [_StubCamelotTable(page=6, n_rows=45, n_cols=7, accuracy=99.5)]
    lattice = [_StubCamelotTable(page=6, n_rows=1, n_cols=1, accuracy=100.0)]
    out = _pick_best_per_page(stream, lattice)
    # The 45×7 stream table must win — the 1×1 lattice artifact is filtered.
    assert len(out) == 1
    assert out[0] is stream[0]


def test_pick_best_skips_lattice_1xN_artifact():
    """A 1×N lattice 'table' is the same artifact shape (e.g. a header
    rule line). Must not displace a real stream table."""
    stream = [_StubCamelotTable(page=3, n_rows=20, n_cols=4, accuracy=95.0)]
    lattice = [_StubCamelotTable(page=3, n_rows=1, n_cols=5, accuracy=100.0)]
    out = _pick_best_per_page(stream, lattice)
    assert len(out) == 1
    assert out[0] is stream[0]


def test_pick_best_skips_lattice_Nx1_artifact():
    stream = [_StubCamelotTable(page=3, n_rows=20, n_cols=4, accuracy=95.0)]
    lattice = [_StubCamelotTable(page=3, n_rows=8, n_cols=1, accuracy=100.0)]
    out = _pick_best_per_page(stream, lattice)
    assert len(out) == 1
    assert out[0] is stream[0]


def test_pick_best_prefers_real_lattice_table():
    """A genuine ≥2×2 lattice table at high accuracy DOES win over stream
    (lattice means visible ruled lines — strong tabularity signal)."""
    stream = [_StubCamelotTable(page=3, n_rows=20, n_cols=4, accuracy=80.0)]
    lattice = [_StubCamelotTable(page=3, n_rows=15, n_cols=5, accuracy=98.0)]
    out = _pick_best_per_page(stream, lattice)
    assert len(out) == 1
    assert out[0] is lattice[0]


def test_pick_best_falls_back_to_stream_when_lattice_low_accuracy():
    """Lattice tables below 80% accuracy don't qualify (they may have
    spurious cell-merge issues)."""
    stream = [_StubCamelotTable(page=3, n_rows=20, n_cols=4, accuracy=80.0)]
    lattice = [_StubCamelotTable(page=3, n_rows=15, n_cols=5, accuracy=70.0)]
    out = _pick_best_per_page(stream, lattice)
    assert len(out) == 1
    assert out[0] is stream[0]


# ---------------------------------------------------------------------------
# 2. _locate_caption_anchor — Bug 3 (figure positioning)
# ---------------------------------------------------------------------------


def test_locate_caption_exact_match_returns_position():
    """Easy case: caption text appears verbatim in the normalized text."""
    text = "Some body prose.\n\nFigure 1. The actual caption sentence ends here.\n\nMore prose."
    cap = "Figure 1. The actual caption sentence ends here."
    idx = _locate_caption_anchor(text, "Figure 1", cap)
    assert idx == text.find(cap)
    assert idx > 0


def test_locate_caption_whitespace_tolerant():
    """efendic regression: caption has '. Note.' (space), normalized text
    has '.\\nNote.' (newline). Exact find() returns -1; the regex anchor
    succeeds."""
    text = (
        "Some body.\n\n"
        "Figure 1. t-Values for Manipulated Versus Non-Manipulated Attributes.\n"
        "Note. t-values for four-direction information manipulations.\n\n"
        "More prose."
    )
    cap = (
        "Figure 1. t-Values for Manipulated Versus Non-Manipulated Attributes. "
        "Note. t-values for four-direction information manipulations."
    )
    idx = _locate_caption_anchor(text, "Figure 1", cap)
    # Exact find returns -1 because newline≠space; anchor must still locate it.
    assert text.find(cap) == -1
    assert idx >= 0
    # The match should be at the start of the Figure caption line, not
    # somewhere in the body prose.
    assert text[idx:idx + 10] == "Figure 1. "


def test_locate_caption_returns_minus_one_when_no_plausible_match():
    """If the caption text doesn't appear in any form, return -1 so the
    caller can route the item to the appendix instead of inlining it
    at position 0 (which was the v2.2.0 Bug 3 behavior)."""
    text = "Some unrelated text without any figure captions."
    cap = "Figure 1. A caption that simply isn't in the text."
    idx = _locate_caption_anchor(text, "Figure 1", cap)
    assert idx == -1


def test_locate_caption_prefers_later_match_over_body_ref():
    """When the document has both a body reference ('see Figure 1') and
    the real caption, the anchor should prefer the LATER position
    (the real caption block is later in the document than abstract refs)."""
    text = (
        "Abstract: We test predictions using see Figure 1 results.\n\n"
        "## Results\n\nMain text describes findings shown in Figure 1.\n\n"
        "Figure 1. Detailed caption explaining the main result with numbers.\n\n"
        "Discussion follows."
    )
    cap = "Figure 1. Detailed caption explaining the main result with numbers."
    idx = _locate_caption_anchor(text, "Figure 1", cap)
    assert idx >= 0
    # Must be at the real caption position, not the body reference.
    assert text[idx:idx + 10] == "Figure 1. "
    # Must NOT be the body reference position (which is earlier).
    body_ref_pos = text.find("Figure 1 results")
    assert idx > body_ref_pos


def test_locate_caption_handles_empty_inputs():
    assert _locate_caption_anchor("", "Figure 1", "Figure 1. cap") == -1
    assert _locate_caption_anchor("some text", "Figure 1", "") == -1


# ---------------------------------------------------------------------------
# 3. Soft-hyphen rejoin in caption extraction
# ---------------------------------------------------------------------------


def _stub_caption_match(char_start: int, char_end: int):
    from docpluck.tables.captions import CaptionMatch
    return CaptionMatch(
        kind="figure",
        number=1,
        label="Figure 1",
        page=1,
        char_start=char_start,
        char_end=char_end,
        line_text="Figure 1",
    )


def test_caption_strips_soft_hyphen_before_whitespace():
    """chen_2021_jesp pattern: pdftotext renders soft hyphen + line wrap
    as ``­ `` (U+00AD + space). The caption extractor should fold the
    word back together: ``Sup­ plementary`` → ``Supplementary``."""
    raw = (
        "Figure 1. Plots are available in Sup­ plementary Materials only.\n\n"
        "Body follows."
    )
    fig_start = raw.index("Figure 1.")
    fig_end = fig_start + len("Figure 1.")
    cap = _stub_caption_match(fig_start, fig_end)
    snippet = _extract_caption_text(raw, cap)
    # Soft hyphen must be gone, word must be rejoined.
    assert "Sup­ plementary" not in snippet
    assert "Sup plementary" not in snippet
    assert "Supplementary" in snippet


def test_caption_strips_orphan_soft_hyphen():
    """An orphan U+00AD (no following whitespace) is also invisible by
    Unicode standard; drop it entirely."""
    raw = "Figure 1. Some­text without space after the soft hyphen.\n\nBody."
    fig_start = raw.index("Figure 1.")
    fig_end = fig_start + len("Figure 1.")
    cap = _stub_caption_match(fig_start, fig_end)
    snippet = _extract_caption_text(raw, cap)
    assert "Some­text" not in snippet
    assert "Sometext" in snippet


def test_caption_no_soft_hyphens_left_after_extraction():
    """No U+00AD should survive caption extraction under any condition."""
    raw = "Figure 1. A­B­ C­ D ­E.\n\n"
    fig_start = raw.index("Figure 1.")
    fig_end = fig_start + len("Figure 1.")
    cap = _stub_caption_match(fig_start, fig_end)
    snippet = _extract_caption_text(raw, cap)
    assert "­" not in snippet


# ---------------------------------------------------------------------------
# 4. _pretty_label for synthesized headings
# ---------------------------------------------------------------------------


def test_pretty_label_capitalizes_common_sections():
    assert _pretty_label("abstract") == "Abstract"
    assert _pretty_label("introduction") == "Introduction"
    assert _pretty_label("methods") == "Methods"
    assert _pretty_label("results") == "Results"
    assert _pretty_label("discussion") == "Discussion"
    assert _pretty_label("conclusion") == "Conclusion"


def test_pretty_label_handles_compound_canonical_labels():
    """Compound canonical labels with underscores get spaces + title-case."""
    assert _pretty_label("data_availability") == "Data Availability"
    assert _pretty_label("open_practices") == "Open Practices"


def test_pretty_label_returns_empty_for_empty_input():
    assert _pretty_label("") == ""
    assert _pretty_label(None) == ""


def test_pretty_label_passes_through_unknown_labels():
    """Unknown canonical → generic title-case fallback."""
    # The mapping table doesn't have 'sidebar'.
    assert _pretty_label("sidebar") == "Sidebar"
    assert _pretty_label("custom_section") == "Custom Section"
