"""Each column belongs to the group header that spans it.

10.1177/01461672251327169 p11, Table 6, checked on the rasterized page 2026-10-14
(the page is printed sideways). "Participant-level analyses" spans Error mean |
Error SD | t-stat | p | Cohen's d and CI | Interpretation; "Item-level analysis" spans
t-stat | df | p | Cohen's d and CI. Both labels are CENTRED, so Camelot puts each in a
middle column of its span. The header also wraps ("Actual / prevalence / average",
"Error / mean"), and the wrap was folded with the same marker as a group header, so
flatten built six "groups" and bound the item-level t = -4.30, df = 5 to the
participant-level d = -1.44 [-1.55, -1.32] (ESCImate 0.7.17: two false WARNs, since
-4.30 / sqrt(6) = -1.76, the ITEM d). On the page: participant t = -35.02 (df = 593,
note), d = -1.44; item t = -4.30, df = 5, d = -1.76.
"""
from __future__ import annotations

import pytest

from docpluck.extract_structured import extract_pdf_structured
from docpluck.tables.flatten import _top_row_arm_cols, flatten_table
from docpluck.testing import require_corpus_pdf


@pytest.fixture(scope="module")
def rows():
    pdf = require_corpus_pdf("apa/ip_feldman_2025_pspb.pdf").read_bytes()
    t = [t for t in extract_pdf_structured(pdf)["tables"] if t.get("label") == "Table 6"][0]
    out = []
    for fr in flatten_table(t):
        d = fr if isinstance(fr, dict) else fr.__dict__
        out.append((d.get("row_label"), d.get("fields") or {}))
    return out


def _group(rows, label, group):
    return [f for lab, f in rows if lab == label and f.get("group") == group]


def test_participant_level_t_pairs_with_participant_d(rows):
    g = _group(rows, "Overall negative", "Participant-level analyses")
    assert len(g) == 1, rows
    f = g[0]
    assert f.get("t") == -35.02 and f.get("d") == -1.44, f
    assert "df" not in f, f


def test_item_level_t_df_pair_with_item_d(rows):
    g = _group(rows, "Overall negative", "Item-level analysis")
    assert len(g) == 1, rows
    f = g[0]
    assert (f.get("t"), f.get("df"), f.get("d")) == (-4.3, 5, -1.76), f


def test_wrapped_headers_are_not_groups(rows):
    groups = {f.get("group") for _, f in rows}
    assert groups <= {"Participant-level analyses", "Item-level analysis", None}, groups


def test_top_row_arm_cols_shape():
    grid = [["", "", "Original", "", "", "Replication", ""],
            ["", "Actual", "", "", "", "", ""],
            ["Item", "mean", "t", "p", "d", "t", "p"]]
    assert _top_row_arm_cols(grid) == {2, 5}
    # a label with a sub-header directly under it is the ordinary 2-row fold
    assert _top_row_arm_cols([["", "A", "B"], ["x", "M", "SD"]]) == set()
    # a top row that carries the row label is not a super-header row
    assert _top_row_arm_cols([["Item", "A", "B"], ["", "", ""]]) == set()


def test_restriction_never_removes_an_existing_grouping():
    """Top row with two standalone labels, but only ONE of them carries the fold marker
    (the other is folded into a different column): the old grouping is kept, never
    replaced by no grouping (tier-2 review, Sonnet, 2026-10-14)."""
    from docpluck.tables.cell_cleaning import _MERGE_SEPARATOR as S
    from docpluck.tables.flatten import _detect_column_groups
    header = ["Item", f"A{S}t", "p", f"B{S}t", "p"]
    old = _detect_column_groups(header)
    assert old is not None
    assert _detect_column_groups(header, None, {1, 2}) == old


def test_a_statistic_column_under_no_group_is_bound_to_neither(rows):
    """'Prevalence estimate mean' is printed under neither group header. It was
    shared into every arm, so each Item-level record carried M = the prevalence
    estimate (47.41 for "Had fight/argument") as if the item analysis reported it.
    It is now its own record with no group, like the printed-span path does."""
    item = _group(rows, "Had fight/argument", "Item-level analysis")
    assert all("M" not in f for f in item), item
    part = _group(rows, "Had fight/argument", "Participant-level analyses")
    assert len(part) == 1 and part[0].get("M") == -23.63 and part[0].get("SD") == 23.54, part
    own = [f for lab, f in rows if lab == "Had fight/argument" and "group" not in f]
    assert own and own[0].get("M") == 47.41, own


def test_role_repeat_grouping_keeps_unspanned_stats_apart():
    from docpluck.tables.cell_cleaning import _MERGE_SEPARATOR as S
    from docpluck.tables.flatten import _detect_column_groups
    # Shape of Table 6: a mean printed before the arms, then the first arm's own
    # mean / SD / t (its centred label lands on p), then the second arm.
    # The wrapped headers carry the fold marker too, as in the real grid.
    header = ["Item", f"Prev{S}mean", f"Error{S}mean", f"Error{S}SD", "t", f"A{S}p", "d",
              "t", f"B{S}p", "d"]
    label_cols, groups = _detect_column_groups(header, None, {5, 8})
    names = [g for g, _ in groups]
    assert names[:2] == ["A", "B"], groups
    assert ("", [1]) in groups and label_cols == [0], (label_cols, groups)
