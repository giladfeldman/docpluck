"""A glyph repair may never turn a KEPT row into a DELETED one.

## The defect (R4), found by two independent reviewers on 2026-08-15

v2.4.133 moved ``cell_cleaning.clean_cell_text`` from the HTML escaper to cell
CONSTRUCTION so every table-text channel would finally agree. That fix is right.
It also, unannounced, changed what the STRUCTURAL GATES are handed: on the region
path ``camelot_extract._camelot_table_to_dict`` feeds its freshly-built cells to
``whitespace._trim_trailing_prose_rows`` / ``_whitespace_grid_is_clean``, and
``whitespace._normalize_cell_text`` began repairing at build in the same release,
so all three call sites of those two gates flipped from raw text to repaired text
at once.

One of the three affected predicates changes in the DELETING direction:

``whitespace._row_is_prose`` returns False as soon as ``_STAT_TOKEN_RE`` matches,
and that pattern matches a digit. The W0i corruption class prints ``×`` as ``3``,
so an interaction-term row label

    raw       "Direction 3 manipulated attribute"   digit present -> NOT prose
    repaired  "Direction × manipulated attribute"   no digit, 3 word tokens -> PROSE

Three such rows in a row satisfy ``_PROSE_RUN_MIN`` and
``_trim_trailing_prose_rows`` cuts from the FIRST one to the END of the grid —
so a correct repair deletes every row below it, published data included, and
both region-path ``return None`` sites were silent.

Reviewers split on shipping it; both reproduced the mechanism. Reproduced here
against the unfixed code before the fix was written: this file's
``test_prose_run_of_repaired_interaction_rows_survives`` failed with the grid cut
to zero rows, and ``test_row_is_prose_is_not_flipped_by_a_repair`` failed on all
three rows.

## The rule this pins

A repair may not flip a CONTENT-DELETING predicate into deleting. It may still
decide a VALIDITY predicate — those judge the text we actually ship, and there
the repaired form is the honest input. That split is deliberate and is the
reviewers' converged position; a blanket "gates always see raw" would throw away
the two directions where the repair legitimately rescues a grid.
"""

from __future__ import annotations

from docpluck.tables.cell_cleaning import clean_cell_text
from docpluck.tables.whitespace import (
    _cell_is_clean_data,
    _cell_is_garbled,
    _row_is_prose,
    _trim_trailing_prose_rows,
    _whitespace_grid_is_clean,
)


def _grid(rows: list[list[str]]) -> list[dict]:
    """Build a cell list the way the capture paths do — RAW text, no repair."""
    cells: list[dict] = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if not text:
                continue
            cells.append(
                {
                    "r": r,
                    "c": c,
                    "rowspan": 1,
                    "colspan": 1,
                    "text": text,
                    "is_header": r == 0,
                    "bbox": (0.0, 0.0, 0.0, 0.0),
                }
            )
    return cells


# The W0i shape: an interaction term whose `×` pdftotext delivered as `3`. Three
# consecutive rows is the minimum that forms a `_PROSE_RUN_MIN` run.
#
# Shaped so the deletion is DATA loss, not merely row loss: the cut runs from the
# first prose row to the END of the grid, so `Gender`'s published coefficients
# below the run go with them.
#
# The labels are tuned to sit between two neighbouring guards, so the test
# reaches the predicate it exists to pin: each is >40 chars (so the grid is not
# waved through by `_is_categorical_grid`) but carries <6 alphabetic words (so it
# is not a `_cell_is_prose` sentence fragment, which would reject the grid for a
# different and legitimate reason).
# RE-BASED 2026-09-07 ON A REPAIR THAT STILL SHIPS. This fixture used to carry
# `Direction 3 manipulated ...`, repaired to `Direction x ...` by W0i. W0i was
# removed from every default path under the THREE TIERS directive (CLAUDE.md,
# user directive 2026-09-06), so that repair no longer fires and the fixture
# would have made every assertion below VACUOUS -- the file's own
# `test_repair_actually_fires_on_this_fixture` exists to catch exactly that, and
# it did.
#
# The INVARIANT this file pins is unchanged and still worth pinning: a repair
# must never turn a data row into prose, because the prose trim then DELETES it.
# It is now carried by the unmapped-glyph minus recovery -- a CLASS A repair of a
# marker that cannot legitimately occur, which the directive keeps.
_INTERACTION_ROWS = [
    ["Predictor", "b", "SE"],
    ["Age", "0.12", "0.05"],
    ["Direction and manipulated attributional outcome", "(cid:0)0.42", "0.05"],
    ["Valence and counterfactual framing manipulation", "(cid:0)0.31", "0.07"],
    ["Salience and presentation ordering counterbalance", "(cid:0)0.18", "0.06"],
    ["Gender", "0.31", "0.09"],
]


def test_repair_actually_fires_on_this_fixture():
    """Known positive. Without this the rest of the file could pass on a fixture
    the repair never touches, which would make every assertion below vacuous."""
    repaired = clean_cell_text("(cid:0)0.42")
    assert repaired == "-0.42", (
        f"the known-positive repair no longer fires (got {repaired!r}); every "
        "assertion in this file would be vacuous"
    )


def test_row_is_prose_is_not_flipped_by_a_repair():
    """The predicate at its ROOT: a row that carries data raw still carries data
    once its glyphs are repaired.

    Fixed by teaching `_STAT_TOKEN_RE` the notation the repair chain emits, not
    only by the both-forms rule at the call site. Both, deliberately: the token
    vocabulary is the real defect (the operator class did not cover `×`), and
    the structural rule is what protects the next repair nobody has written yet.
    """
    for row in _INTERACTION_ROWS[2:5]:
        assert not _row_is_prose(row), f"raw row read as prose: {row!r}"
        repaired = [clean_cell_text(cell) for cell in row]
        assert not _row_is_prose(repaired), (
            f"a REPAIR turned a data row into prose: {row!r} -> {repaired!r}. "
            "That is the deletion vector this file exists to close."
        )


def test_prose_run_of_repaired_interaction_rows_survives():
    """The gate in isolation: the grid keeps all five rows."""
    cells = _grid(_INTERACTION_ROWS)
    kept = _trim_trailing_prose_rows(cells)
    assert {c["r"] for c in kept} == set(range(len(_INTERACTION_ROWS))), (
        f"rows deleted: kept {sorted({c['r'] for c in kept})} of "
        f"{list(range(len(_INTERACTION_ROWS)))}"
    )


def test_region_path_keeps_every_row_and_still_ships_repaired_text():
    """END TO END through the REAL region capture path — the one that deletes.

    Deliberately NOT a hand-built cell list handed straight to the gate: a test
    that constructs its own cells pins the helper, not the pipeline, and would
    stay green if construction changed again (the lesson `_FakeCamelotTable`
    already encodes in ``test_table_cell_channels_agree``). ``id_prefix`` must
    start with ``region`` — that is the branch that runs the two gates.

    Both halves are asserted together, because either alone can be satisfied by
    the defect: keeping the rows while shipping raw text loses the v2.4.133 fix,
    and shipping repaired text while dropping the rows is the R4 defect.
    """
    from docpluck.tables.camelot_extract import _camelot_table_to_dict
    from tests.test_table_cell_channels_agree import _FakeCamelotTable

    td = _camelot_table_to_dict(
        _FakeCamelotTable(tuple(_INTERACTION_ROWS)), 0, id_prefix="region_t"
    )
    assert td is not None, (
        "the whole table was discarded — the prose run cut every row and the "
        "region path returned None"
    )
    rows_kept = {c["r"] for c in td["cells"]}
    assert len(rows_kept) == len(_INTERACTION_ROWS), (
        f"rows deleted: kept {sorted(rows_kept)} of "
        f"{list(range(len(_INTERACTION_ROWS)))}"
    )
    texts = [c["text"] for c in td["cells"]]
    assert "-0.42" in texts, (
        "cells shipped RAW — the v2.4.133 channel-agreement fix was lost"
    )
    assert "(cid:0)0.42" not in texts
    # raw_text is derived from the repaired cells, so the sidecar and the HTML
    # cannot disagree about the same table.
    assert "-0.42" in td["raw_text"] and "(cid:0)" not in td["raw_text"]
    assert "0.31" in td["raw_text"], "the row below the prose run was deleted"


def test_genuine_absorbed_prose_is_still_trimmed():
    """The guard must not be disarmed. Real absorbed body prose carries no digit
    in EITHER form, so it is still prose under the both-forms rule and is still
    cut. Paired with the test above so an absence assertion cannot be satisfied
    by data loss (LESSONS L-041)."""
    cells = _grid(
        [
            ["Predictor", "b"],
            ["Age", "0.12"],
            ["participants were asked to recall a hurting", ""],
            ["experience that had happened to them in the", ""],
            ["past and to describe it in as much detail as", ""],
        ]
    )
    kept = _trim_trailing_prose_rows(cells)
    assert {c["r"] for c in kept} == {0, 1}, (
        "absorbed body prose was NOT trimmed — the guard is disarmed"
    )


def test_validity_predicates_still_judge_the_repaired_form():
    """The other half of the rule. A repair MAY decide a validity predicate,
    because those judge the text docpluck actually ships.

    `\\.001` is the `<`-as-backslash class: raw it is not a data cell, repaired it
    plainly is. `(cid:0)` before a digit is a recoverable minus: raw it is a
    garble marker that condemns the grid, repaired it is an ordinary bound.
    """
    assert not _cell_is_clean_data("\\.001")
    assert _cell_is_clean_data(clean_cell_text("\\.001"))

    assert _cell_is_garbled("(cid:0)0.23")
    assert not _cell_is_garbled(clean_cell_text("(cid:0)0.23"))


def test_grid_condemned_raw_by_a_recoverable_marker_is_accepted():
    """A grid whose only garble is a recoverable `(cid:0)` minus is a real data
    table and must survive the clean-grid gate, since every channel ships the
    repaired text. This is the ACCEPTANCE direction the both-forms rule keeps."""
    cells = _grid(
        [
            ["Predictor", "b", "95% CI"],
            ["Age", "(cid:0)0.23", "[(cid:0)0.45, (cid:0)0.06]"],
            ["Gender", "0.11", "[0.02, 0.20]"],
        ]
    )
    assert _whitespace_grid_is_clean(cells), (
        "a table whose only defect is a repairable minus was condemned"
    )


def test_mid_token_glyph_fusion_still_condemns_the_grid():
    """The converse, so the test above cannot pass by disabling the guard. A
    `(cid:N)` NOT before a digit is unrecoverable — its presence really is proof
    the char extraction for the region is corrupt, and the grid must still be
    rejected."""
    cells = _grid(
        [
            ["Predictor", "b"],
            ["[(cid:0)ra00m..er's,V", "0.23"],
            ["Gender", "0.11"],
        ]
    )
    assert not _whitespace_grid_is_clean(cells), (
        "an unrecoverable mid-token glyph fusion was accepted"
    )
