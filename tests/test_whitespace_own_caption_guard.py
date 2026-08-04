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


# --- inline cross-reference false positive (2026-08-04) -------------------------
# _CAPTION_LABEL_RE was UNANCHORED (`\b(?:Table|Figure)\s+\d+\s*[.:]`), so it fired on
# a mid-sentence cross-reference in a footnote/prose cell and condemned the grid.
# maier Table 5's region carries two such cells — "al. (2007) in Table 8." and
# "…in Figure 2. We summarized the in-" — so its 3x5 descriptives grid (whose data the
# raw_text channel HAD captured correctly: 2.84 [1.89] {1.36}* (170) …) was discarded
# and the table rendered as a caption-only stub. That is TEXT-LOSS from a false
# positive, verified against the AI gold.
#
# A real absorbed caption ANCHORS at the start of its cell; a cross-reference has text
# before it. camelot_extract._CAPTION_ROW_PATTERN already encodes exactly this
# discipline ("^\s*Table\s+\d+\s*[.:]", whose comment notes anchoring is why
# "see Table 2" mid-row does not match) — the whitespace copy had simply lost it.


def test_inline_cross_reference_does_not_condemn_grid():
    """A mid-sentence "in Table 8." / "in Figure 2." is a REFERENCE, not a caption."""
    # Standalone numeric cells so the grid clears the clean-data-row bar and this
    # test isolates the CAPTION rule (a mean-with-SD composite like "2.84 [1.89]"
    # is not a _CLEAN_DATA_CELL_RE match, which is a separate concern).
    cells = _grid(
        [
            ["Table 5. Hypothetical Donations: Descriptives", "", ""],
            ["Condition", "Identifiable", "Statistical"],
            ["Explicit learning", "2.84", "2.74"],
            ["No intervention", "2.58", "2.72"],
            ["Note. Based on Small et al. (2007) in Table 8.", "", ""],
        ]
    )
    assert _whitespace_grid_is_clean(cells, own_caption_number=5) is True


def test_absorbed_caption_at_cell_start_still_rejects():
    """The anchored form is unchanged: a real absorbed caption still condemns."""
    cells = _grid(
        [
            ["Table 5. Hypothetical Donations: Descriptives", "", ""],
            ["Condition", "Identifiable", "Statistical"],
            ["Explicit learning", "2.84", "2.74"],
            ["No intervention", "2.58", "2.72"],
            ["Table 8. Statistical tests for identifiability.", "", ""],
            ["Hypothesis", "p", "Effect size"],
        ]
    )
    assert _whitespace_grid_is_clean(cells, own_caption_number=5) is False
