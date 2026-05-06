"""Confidence scoring for structured tables."""

from docpluck.tables import Cell
from docpluck.tables.confidence import (
    score_table,
    should_fall_back_to_isolated,
    ISOLATION_THRESHOLD,
)


def _row(r, n_cols, is_header=False) -> list[Cell]:
    return [
        {
            "r": r, "c": c, "rowspan": 1, "colspan": 1,
            "text": "x", "is_header": is_header,
            "bbox": (0.0, 0.0, 0.0, 0.0),
        }
        for c in range(n_cols)
    ]


def test_isolated_returns_none():
    assert score_table([], rendering="isolated") is None


def test_clean_lattice_high_score_unclamped():
    # 4 rows × 3 cols, all rows full → no deviation → base 0.85
    cells = []
    for r in range(4):
        cells.extend(_row(r, 3, is_header=(r == 0)))
    raw = score_table(cells, rendering="lattice")
    assert raw is not None
    assert raw == 0.85   # base, no penalties


def test_lattice_can_go_below_threshold_when_degraded():
    # 12 rows each with a unique cell count (1..12) → all counts distinct.
    # Counter.most_common(1)[0][0] picks the first key inserted (Python 3.7+
    # dict ordering), which is count=1 (row 0). The other 11 rows all deviate.
    # score = 0.85 - 0.05*11 = 0.30 < 0.4 → should_fall_back returns True.
    cells = []
    for r in range(12):
        cells.extend(_row(r, r + 1))  # row r has r+1 cells (all distinct)
    raw = score_table(cells, rendering="lattice")
    assert raw is not None
    assert raw < 0.4
    assert should_fall_back_to_isolated(raw) is True


def test_clean_whitespace_lower_than_lattice():
    cells = []
    for r in range(4):
        cells.extend(_row(r, 3, is_header=(r == 0)))
    lattice = score_table(cells, rendering="lattice")
    whitespace = score_table(cells, rendering="whitespace")
    assert whitespace is not None and lattice is not None
    assert whitespace < lattice
    assert whitespace == 0.65   # base, no penalties


def test_should_fall_back_when_below_threshold():
    # Pre-clamp score below ISOLATION_THRESHOLD → fall back to isolated
    assert should_fall_back_to_isolated(score=0.3) is True
    assert should_fall_back_to_isolated(score=0.39) is True
    assert should_fall_back_to_isolated(score=0.4) is False
    assert should_fall_back_to_isolated(score=None) is False


def test_clamp_confidence_lattice_bounds():
    # Clamp applied separately by callers; raw scores beyond bounds get clamped.
    from docpluck.tables.confidence import clamp_confidence
    assert clamp_confidence(0.99, rendering="lattice") == 0.95
    assert clamp_confidence(0.10, rendering="lattice") == 0.5
    assert clamp_confidence(0.85, rendering="lattice") == 0.85


def test_clamp_confidence_whitespace_bounds():
    from docpluck.tables.confidence import clamp_confidence
    assert clamp_confidence(0.99, rendering="whitespace") == 0.85
    assert clamp_confidence(0.10, rendering="whitespace") == 0.4
    assert clamp_confidence(0.65, rendering="whitespace") == 0.65


def test_clamp_confidence_isolated_returns_none():
    from docpluck.tables.confidence import clamp_confidence
    assert clamp_confidence(0.99, rendering="isolated") is None
    assert clamp_confidence(None, rendering="isolated") is None
