"""Placeholder markers land on their own caption line, not shifted.

CaptionMatch offsets index the REJOINED shadow string (`_join_split_captions`
turns ``T\\n\\n1:`` into ``Table 1:``), while placeholder mode splices into the
caller's raw text. Before 2026-10-08 the offsets were used on raw text directly,
so every marker after the first rejoin was spliced at the wrong position: the
two strings differ in length in 29 of 102 corpus papers (measured 2026-09-26).
"""
from __future__ import annotations

import docpluck.extract_structured as ES


def _captions(raw: str):
    rejoined = ES._join_split_captions(raw)
    return ES.find_caption_matches(rejoined, ES._page_offsets(rejoined))


def test_offset_map_points_each_rejoined_char_at_its_source():
    raw = "Intro text.\n\nT\n\n1: Means by group.\n\nFig. 2. A plot.\n\nTable 3. Last.\n"
    rejoined, to_raw = ES._join_split_captions_mapped(raw)
    assert rejoined == ES._join_split_captions(raw)
    assert rejoined != raw
    assert len(to_raw) == len(rejoined) + 1
    assert to_raw[-1] == len(raw)
    assert to_raw == sorted(to_raw)  # monotone: a rejoin never reorders text
    # Text after the rewrites maps onto identical characters.
    i = rejoined.index("Table 3. Last.")
    assert raw[to_raw[i]:to_raw[i] + len("Table 3. Last.")] == "Table 3. Last."


def test_markers_replace_their_own_caption_after_a_rejoin():
    raw = (
        "Body paragraph before.\n\n"
        "T\n\n1: Means by group.\n\n"
        "Body paragraph between the two tables.\n\n"
        "Table 2. Correlations among measures.\n\n"
        "Closing body paragraph.\n"
    )
    assert len(ES._join_split_captions(raw)) != len(raw)  # the case under test
    out = ES._apply_placeholder(raw, _captions(raw))
    assert out == (
        "Body paragraph before.\n\n"
        "[Table 1: Means by group.]\n\n"
        "Body paragraph between the two tables.\n\n"
        "[Table 2: Correlations among measures.]\n\n"
        "Closing body paragraph.\n"
    ), out


def test_no_rejoin_leaves_offsets_unchanged():
    raw = "Para.\n\nTable 1. Alpha.\n\nPara two.\n"
    assert ES._join_split_captions_mapped(raw)[1] == list(range(len(raw) + 1))
    out = ES._apply_placeholder(raw, _captions(raw))
    assert out == "Para.\n\n[Table 1: Alpha.]\n\nPara two.\n", out
