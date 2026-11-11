"""A grid holding only a small part of its printed table is set aside (d-095325).

10.15626/mp.2022.3108 p10 Table 10: once captions tie-break by position, a
lattice pass hands Table 10 a 2-row header-only grid while the page prints six
predictor rows under it; delivered as cells it displaced the full text. The
completeness test compares the grid's words with the text channel's body cut to
the table's own lines (note and two-line prose runs excluded, so a complete
grid on a two-column page -- 10.1177/19485506211056761 p2 Table 1 -- is not
judged against the prose beside it).
"""
from __future__ import annotations

from docpluck.extract_structured import (
    _grid_covers_little_of_printed_table,
    _printed_table_lines,
)


def _grid(*rows):
    return {"cells": [{"r": r, "c": c, "text": t} for r, row in enumerate(rows) for c, t in enumerate(row)]}


_BODY_T10 = "\n".join([
    "Predictor", "Default condition:", "No-Default- Opt-In", "Opt-Out - Opt-In",
    "Framing condition:", "Positive - Negative", "Original study's findings",
    "Signal", "Directionality", "Direct replication findings", "Signal", "Directionality",
    "Conceptual replication findings", "Signal", "Directionality",
    "Yes", "Yes", "Consistent", "Consistent", "No", "No", "Inconsistent - Opposite direction",
    "Consistent", "No", "Yes", "Consistent", "Consistent", "No", "Consistent", "Yes",
    "Consistent", "Yes", "Inconsistent - Opposite direction",
    "Note. Directionality dimension summarizes the directional consistency of results across",
])


def test_header_only_grid_is_partial():
    header = _grid(["Original study's findingsPredictorSignal", "Direct replication findings",
                    "Conceptual replication findings"], ["", "SignalDirectionality", "SignalDirectionality"])
    assert _grid_covers_little_of_printed_table(header, _BODY_T10)


def test_complete_grid_is_not_partial():
    rows = [ln.split() for ln in _BODY_T10.split("\n")[:-1]]
    assert not _grid_covers_little_of_printed_table(_grid(*rows), _BODY_T10)


def test_prose_after_the_table_is_not_counted():
    body = "\n".join([
        "Manipulated attribute", "Impact on affect", "Impact on non-manipulated attribute",
        "Risk is high", "Risk is low", "Benefit is high", "Benefit is low",
        "Negative affect", "Positive affect", "Positive affect", "Negative affect",
        "Benefit is low", "Benefit is high", "Risk is low", "Risk is high",
        "efficient than weighing the pros and cons or retrieving",
        "from memory many relevant examples, especially when the",
        "required judgment or decision is complex or mental",
        "resources are limited (Finucane et al., 2000, p. 3).",
    ] + ["and morality judgments are another case where the affect heuristic is used"] * 10)
    assert "efficient" not in _printed_table_lines(body)
    grid = _grid(["Manipulated attribute", "Impact on affect", "Impact on non-manipulated attribute"],
                 ["Risk is high", "Negative affect", "Benefit is low"],
                 ["Risk is low", "Positive affect", "Benefit is high"],
                 ["Benefit is high", "Positive affect", "Risk is low"],
                 ["Benefit is low", "Negative affect", "Risk is high"])
    assert not _grid_covers_little_of_printed_table(grid, body)


def test_small_tables_are_never_judged():
    assert not _grid_covers_little_of_printed_table(_grid(["A"]), "A\nB\nC 1.2 3.4")


def test_real_table_10_keeps_its_full_text():
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.15626__mp.2022.3108.pdf")
    t10 = next(t for t in extract_pdf_structured(p.read_bytes())["tables"] if t.get("label") == "Table 10")
    raw = t10.get("raw_text") or ""
    assert "Inconsistent - Opposite direction" in raw and "Framing condition:" in raw, t10.get("content_status")


def test_a_grid_carrying_more_numbers_than_the_text_is_kept():
    """10.1109/access.2024.3421281 p12 Table 4: cells fuse several values, so few
    tokens match one-for-one, but the grid holds every value and the text body
    (full-width table on a two-column page) only some columns."""
    body = "\n".join(["System", "A07", "A08", "A09", "A10", "A11", "A12", "Baseline", "RawNet2 w/ SimAM + CE",
                      "Replace CE w/ AAM", "Replace CE w/ WAAM", "+ MSE", "+ Adv.", "min t-DCF", "EER (%)",
                      "pooled", "attacks", "evaluation", "partition", "breakdown", "performance"] + ["1.79"] * 22)
    fused = " ".join(f"{a}.{b:02d}0.{b:02d}" for a in range(1, 4) for b in range(10, 40))
    grid = _grid(["System", fused])
    assert not _grid_covers_little_of_printed_table(grid, body)


def test_real_caption_below_table_keeps_its_grid():
    """10.5334/irsp.932 p5 prints Table 2's caption UNDER its grid; the text after
    that caption is Table 3. The complete 13x3 grid must stay Table 2's cells."""
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.5334__irsp.932.pdf")
    t2 = next(t for t in extract_pdf_structured(p.read_bytes())["tables"]
              if t.get("label") == "Table 2" and t.get("page") == 5)
    assert t2.get("cells") and "284 females" in " ".join(c["text"] for c in t2["cells"]), t2.get("content_status")


def test_real_grid_of_the_table_above_is_set_aside():
    """10.1016/j.jesp.2021.104154 p14: a grid spanning Table 12 was paired with the
    Table 13 caption under it; Table 13 must get its own 12x6 grid."""
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.1016__j.jesp.2021.104154.pdf")
    t13 = next(t for t in extract_pdf_structured(p.read_bytes())["tables"]
               if t.get("label") == "Table 13" and t.get("page") == 14)
    assert (t13.get("n_rows"), t13.get("n_cols")) == (12, 6)
