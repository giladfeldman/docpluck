"""RC-T cycle 4 (2026-08-04): the grid guard must not reject a region for its OWN caption.

Root cause (reproduced 2026-08-04, chan_feldman + maier — 19/19 regions):
``_region_for_caption`` builds ``full_bbox = _union(caption_bbox, geom_bbox)``, so a
caption-anchored region ALWAYS contains its own caption line by construction (Camelot
needs it for pairing). ``_whitespace_grid_is_clean``'s caption-absorption guard rejected
on ANY ``Table N.`` cell anywhere in the grid, so it condemned every region grid —
``whitespace_cells`` returned 0 cells universally and the raw_text fallback truncated
rows (chan T3 dropped its first four rows; maier T5 mispaired).

The guard's real target is a FOREIGN caption absorbed mid-grid: cog_emo Table 8's region
reaches down into Table 9's caption at grid row 4 (top=273, vs Table 8's own caption at
top=53). That case must STILL be rejected.

Structural signature separating the two: a table's own caption sits in the grid's
LEADING rows AND names the anchoring caption's own number. The exemption is
IDENTITY-based, not position-based — a first draft keyed on position alone and codex
review (2026-08-04) found three ways it would admit a WRONG table; all three reproduced
locally and are pinned below. So a caption cell is exempt only when the caller supplies
``own_caption_number``, the cell names that exact number, it sits within
``_OWN_CAPTION_MAX_ROW``, and it is the first such match.

Tests are written against the structural signature (synthetic cells), not paper identity,
so they pin the general rule (rule 16 / "fixes must be general").
"""

from __future__ import annotations

from docpluck.tables.whitespace import _whitespace_grid_is_clean


def _grid(rows: list[list[str]]) -> list[dict]:
    """Build a minimal cell grid from row-major text."""
    cells: list[dict] = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            cells.append(
                {
                    "r": r,
                    "c": c,
                    "rowspan": 1,
                    "colspan": 1,
                    "text": text,
                    "is_header": r == 0,
                    "bbox": (0.0, float(r), 1.0, float(r) + 1.0),
                }
            )
    return cells


def test_own_caption_in_leading_row_does_not_reject_grid():
    """A ``Table N.`` in row 0 is the region's OWN caption — expected, not corruption.

    Regression for RC-T cycle 4: this returned False for every caption-anchored
    region, zeroing the whitespace fallback corpus-wide.
    """
    cells = _grid(
        [
            ["Table 9. Summary of statistical tests.", "", ""],
            ["Hypothesis", "p", "Effect size"],
            ["1a", "<.001", "0.67"],
            ["1b", "<.001", "0.36"],
            ["2a", "<.001", "0.73"],
        ]
    )
    assert _whitespace_grid_is_clean(cells, own_caption_number=9) is True


def test_own_caption_exemption_requires_the_caller_to_name_the_number():
    """Without ``own_caption_number`` the strict any-caption reject is unchanged.

    Callers whose cells are not caption-anchored (the legacy auto-detect path) must
    keep the original behaviour, so the exemption is opt-in.
    """
    cells = _grid(
        [
            ["Table 9. Summary of statistical tests.", "", ""],
            ["Hypothesis", "p", "Effect size"],
            ["1a", "<.001", "0.67"],
            ["1b", "<.001", "0.36"],
            ["2a", "<.001", "0.73"],
        ]
    )
    assert _whitespace_grid_is_clean(cells) is False


# --- codex review, 2026-08-04 -------------------------------------------------
# A first draft of this fix exempted the topmost caption by POSITION alone. Codex
# flagged three ways that admits a WRONG table; all three reproduced locally before
# the fix was reworked to be identity-based. These pin them.


def test_neighbour_caption_in_leading_row_still_rejects_grid():
    """codex 2026-08-04 #1: a leading caption whose number is NOT the anchor's.

    The position-only draft blessed this as "own", converting an honest "no table"
    into a silently WRONG table. The number must match the anchoring caption.
    """
    cells = _grid(
        [
            ["Table 9. Neighbour summary.", "", ""],
            ["Variable", "M", "SD"],
            ["Empathy", "2.44", "0.62"],
            ["Regret", "4.90", "0.35"],
        ]
    )
    assert _whitespace_grid_is_clean(cells, own_caption_number=4) is False


def test_neighbour_caption_left_of_own_caption_still_rejects_grid():
    """codex 2026-08-04 #2: ``(r, c)`` order picks the LEFTMOST caption.

    On a side-by-side page that is the neighbour's, not the anchor's. Identity
    matching makes sort order irrelevant.
    """
    cells = _grid(
        [
            ["Table 9. Neighbour summary.", "Table 4. Descriptives.", ""],
            ["Variable", "M", "SD"],
            ["Empathy", "2.44", "0.62"],
            ["Regret", "4.90", "0.35"],
        ]
    )
    assert _whitespace_grid_is_clean(cells, own_caption_number=4) is False


def test_second_caption_sharing_the_own_caption_row_still_rejects_grid():
    """codex 2026-08-04 #3: the draft exempted the whole ROW, not the cell.

    A neighbouring ``Table N.`` / ``Figure N.`` sharing the own-caption row rode
    along free. The exemption is per-CELL and fires at most once.
    """
    with_table = _grid(
        [
            ["Table 4. Descriptives.", "Table 5. Regression results.", ""],
            ["Variable", "M", "SD"],
            ["Empathy", "2.44", "0.62"],
            ["Regret", "4.90", "0.35"],
        ]
    )
    assert _whitespace_grid_is_clean(with_table, own_caption_number=4) is False

    with_figure = _grid(
        [
            ["Table 4. Descriptives.", "Figure 2. Empathy by condition.", ""],
            ["Variable", "M", "SD"],
            ["Empathy", "2.44", "0.62"],
            ["Regret", "4.90", "0.35"],
        ]
    )
    assert _whitespace_grid_is_clean(with_figure, own_caption_number=4) is False


def test_repeated_own_caption_still_rejects_grid():
    """Two copies of the SAME caption ⇒ the region spans two renderings of it.

    A genuine caption line appears once, so only the first match is exempt.
    """
    cells = _grid(
        [
            ["Table 4. Descriptives.", "", ""],
            ["Table 4. Descriptives.", "", ""],
            ["Variable", "M", "SD"],
            ["Empathy", "2.44", "0.62"],
            ["Regret", "4.90", "0.35"],
        ]
    )
    assert _whitespace_grid_is_clean(cells, own_caption_number=4) is False


def test_foreign_caption_below_data_still_rejects_grid():
    """A ``Table N.`` appearing BELOW the data rows is a genuine absorption — reject.

    This is the cog_emo Table 8 case the guard was written for: Table 8's region
    reaches down and pulls in Table 9's caption line partway through the grid.
    """
    cells = _grid(
        [
            ["Table 8. Control condition: Intercorrelations.", "", ""],
            ["Variable", "M", "SD"],
            ["Empathy", "2.44", "0.62"],
            ["Regret", "4.90", "0.35"],
            ["Table 9. Summary of statistical tests.", "", ""],
            ["Hypothesis", "p", "Effect size"],
        ]
    )
    assert _whitespace_grid_is_clean(cells, own_caption_number=8) is False


def test_second_caption_inside_leading_block_still_rejects_grid():
    """Two DIFFERENT captions in the leading rows ⇒ the region straddles two tables.

    Only the grid's FIRST caption occurrence is exempt; a second one — even inside
    the leading-row window — proves the region is mis-bounded.
    """
    cells = _grid(
        [
            ["Table 4. Descriptive statistics.", "", ""],
            ["Table 5. Regression results.", "", ""],
            ["Predictor", "b", "SE"],
            ["Intercept", "0.42", "0.11"],
            ["Empathy", "0.31", "0.08"],
        ]
    )
    assert _whitespace_grid_is_clean(cells, own_caption_number=4) is False


def test_figure_caption_in_leading_row_still_rejects_grid():
    """The own-caption exemption covers TABLE captions only.

    A region anchored on a table caption that leads with a ``Figure N.`` label has
    absorbed a neighbouring figure — still mis-bounded.
    """
    cells = _grid(
        [
            ["Figure 2. Mean empathy by condition.", "", ""],
            ["Variable", "M", "SD"],
            ["Empathy", "2.44", "0.62"],
            ["Regret", "4.90", "0.35"],
        ]
    )
    assert _whitespace_grid_is_clean(cells) is False
