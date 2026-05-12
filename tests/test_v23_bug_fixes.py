"""Tests for v2.3.0 code-only Rendered-view bug fixes.

Per `docs/HANDOFF_2026-05-11_visual_review_findings.md`:
- Bug 4: caption text concatenates across figure boundaries.
- Bug 5: layout title rescue produces truncated title ending in
  a connector word like "of".
"""

from __future__ import annotations

from docpluck.extract_structured import _extract_caption_text
from docpluck.render import _title_looks_truncated


# ---------------------------------------------------------------------------
# Bug 5 — title-rescue connector guard
# ---------------------------------------------------------------------------


def test_title_truncated_when_ends_in_of():
    """The gratitude-paper example from the handoff:
    'Revisiting the effects of helper intentions on gratitude and
    indebtedness: Replication and extensions Registered Report of'
    ends in 'of' — almost certainly truncated."""
    title = (
        "Revisiting the effects of helper intentions on gratitude and "
        "indebtedness: Replication and extensions Registered Report of"
    )
    assert _title_looks_truncated(title)


def test_title_truncated_when_ends_in_connector_words():
    for connector in ("of", "from", "for", "the", "and", "or", "to",
                      "with", "on", "at", "by", "in", "as", "is",
                      "than", "that", "which", "when", "where",
                      "before", "after", "since", "because"):
        title = f"Some Plausible Title {connector}"
        assert _title_looks_truncated(title), f"missed connector: {connector!r}"


def test_title_truncated_ignores_trailing_punct_and_whitespace():
    """Trailing punctuation should not hide the connector tail."""
    assert _title_looks_truncated("Foo Bar of  ")
    assert _title_looks_truncated("Foo Bar of.")
    assert _title_looks_truncated("Foo Bar of -")


def test_title_not_truncated_when_full_sentence():
    """A real title doesn't end in a connector word."""
    assert not _title_looks_truncated(
        "Revisiting the effects of helper intentions on gratitude "
        "and indebtedness: A replication of Tsang (2006)"
    )
    assert not _title_looks_truncated("The Psychology of Decision Making")
    assert not _title_looks_truncated("A Pre-Registered Replication Study")


def test_title_not_truncated_when_single_word():
    """Edge case: a single-word title not in the connector list."""
    assert not _title_looks_truncated("Replication")
    assert not _title_looks_truncated("Methods")


def test_title_truncated_on_empty_input():
    assert not _title_looks_truncated("")
    assert not _title_looks_truncated(None)


def test_title_truncated_case_insensitive():
    """Connector check is case-insensitive (titles often Title Case
    each word including connectors)."""
    assert _title_looks_truncated("Some Title Of")
    assert _title_looks_truncated("Some Title OF")


# ---------------------------------------------------------------------------
# Bug 4 — caption boundary
# ---------------------------------------------------------------------------


def _make_caption(label: str, number: int, kind: str, char_start: int, char_end: int, page: int = 1):
    """Tiny CaptionMatch builder for tests."""
    from docpluck.tables.captions import CaptionMatch
    return CaptionMatch(
        kind=kind,
        number=number,
        label=label,
        page=page,
        char_start=char_start,
        char_end=char_end,
        line_text=label,
    )


def test_extract_caption_text_respects_next_boundary():
    """A caption that doesn't end with a sentence terminator must NOT
    extend past the next caption's char_start when next_boundary is
    provided. This is the gratitude-paper Figure 1 / Figure 2 bug."""
    raw = (
        "Figure 1. Study 2 selfish-ulterior condition results show association "
        "between gratitude and indebtedness\n\n"
        "Figure 2. Study 2 benevolent condition results\n\n"
    )
    fig1_start = raw.index("Figure 1.")
    fig1_end = fig1_start + len("Figure 1.")
    fig2_start = raw.index("Figure 2.")
    cap = _make_caption("Figure 1", 1, "figure", fig1_start, fig1_end)
    snippet = _extract_caption_text(raw, cap, next_boundary=fig2_start)
    # Must NOT contain Figure 2's caption text.
    assert "benevolent condition" not in snippet
    assert "Figure 2" not in snippet
    # But should contain Figure 1's text.
    assert "selfish-ulterior" in snippet


def test_extract_caption_text_without_boundary_uses_800char_cap():
    """When no next_boundary is provided, the 800-char hard cap still
    applies — runaway captions can't consume an entire paper."""
    raw = (
        "Figure 1. Short caption.\n\n"
        + "Body prose that just keeps going. " * 200
    )
    fig1_start = raw.index("Figure 1.")
    fig1_end = fig1_start + len("Figure 1.")
    cap = _make_caption("Figure 1", 1, "figure", fig1_start, fig1_end)
    snippet = _extract_caption_text(raw, cap)
    # Hard cap ≤ 400 chars after truncation ("…" suffix), so the
    # snippet must not contain anywhere near the full repeated body.
    assert len(snippet) <= 410


def test_extract_caption_text_stops_at_sentence_terminator():
    """Existing behavior preserved: a caption that ends with `.` is
    fully captured but doesn't bleed into following body prose."""
    raw = (
        "Figure 1. A clean caption that ends with a period.\n\n"
        "Unrelated body prose that should NOT be part of the caption.\n\n"
    )
    fig1_start = raw.index("Figure 1.")
    fig1_end = fig1_start + len("Figure 1.")
    cap = _make_caption("Figure 1", 1, "figure", fig1_start, fig1_end)
    snippet = _extract_caption_text(raw, cap)
    assert "clean caption that ends with a period" in snippet
    assert "Unrelated body prose" not in snippet
