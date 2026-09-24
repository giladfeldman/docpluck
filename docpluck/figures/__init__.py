"""
docpluck.figures — figure metadata extraction for academic PDFs.

See an internal design doc for the design.

Public types: Figure.
"""

from __future__ import annotations

from typing import Optional, TypedDict


class Figure(TypedDict):
    """One figure, located by its caption in the text channel.

    ``bbox`` is NOT COMPUTED: it is always ``(0.0, 0.0, 0.0, 0.0)``, meaning
    "unknown", never a region at the page origin. Figures are found from their
    caption text (``extract_structured._figure_from_caption``); nothing measures
    where the graphic sits on the page. A layout-channel detector that guessed a
    bbox from nearby drawing primitives existed in ``figures/detect.py`` but was
    never on the production path and was deleted on 2026-09-25 (it found 0 of 5
    figures on a Nature figure-only paper). ``page``, ``label`` and ``caption`` are
    real; ``bbox`` is a placeholder until a measured implementation exists.
    """

    id: str
    label: Optional[str]
    page: int
    bbox: tuple[float, float, float, float]
    caption: Optional[str]


__all__ = ["Figure"]
