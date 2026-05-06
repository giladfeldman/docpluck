"""BlockHint — output unit of Tier-1 annotators, input of Tier-2 core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class BlockHint:
    text: str
    char_start: int
    char_end: int
    page: int | None
    is_heading_candidate: bool
    heading_strength: Literal["strong", "weak", "none"]
    heading_source: Literal["markup", "layout", "text_pattern", None]
