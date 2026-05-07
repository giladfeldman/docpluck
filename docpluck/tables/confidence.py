"""
Confidence scoring for structured tables.

Two-stage design:
  - score_table() returns the *pre-clamp* raw score (or None for isolated).
    The orchestrator uses this raw value to decide whether to fall back to
    kind="isolated" (when raw < ISOLATION_THRESHOLD = 0.4).
  - clamp_confidence() applies per-rendering floors/ceilings to produce
    the user-facing Table.confidence value.

This separation matters: if we clamped inside score_table, the floor would
silently absorb the fall-back signal (e.g. whitespace floor 0.4 == threshold
0.4 means clamped scores never trigger fall-back).

See spec §5.6.
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from . import Cell, TableRendering


ISOLATION_THRESHOLD: float = 0.4


def score_table(cells: list[Cell], *, rendering: TableRendering) -> Optional[float]:
    """Pre-clamp raw confidence. None for isolated."""
    if rendering == "isolated":
        return None

    if not cells:
        return 0.0

    if rendering == "lattice":
        base = 0.85
    else:  # whitespace
        base = 0.65

    cells_per_row: dict[int, int] = Counter(c["r"] for c in cells)
    counts = list(cells_per_row.values())
    modal = Counter(counts).most_common(1)[0][0]

    deviation_rows = sum(1 for n in counts if n != modal)
    score = base - 0.05 * deviation_rows

    if any(n == 0 for n in counts):
        score -= 0.10

    return score


def clamp_confidence(score: Optional[float], *, rendering: TableRendering) -> Optional[float]:
    """Apply per-rendering floor/ceiling to produce the user-facing confidence."""
    if rendering == "isolated" or score is None:
        return None
    if rendering == "lattice":
        floor, ceiling = 0.5, 0.95
    else:  # whitespace
        floor, ceiling = 0.4, 0.85
    return max(floor, min(ceiling, score))


def should_fall_back_to_isolated(score: Optional[float]) -> bool:
    """Whether a pre-clamp score is too low to ship as structured."""
    if score is None:
        return False
    return score < ISOLATION_THRESHOLD


__all__ = ["score_table", "clamp_confidence", "should_fall_back_to_isolated", "ISOLATION_THRESHOLD"]
