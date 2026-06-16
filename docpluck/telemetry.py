"""Lightweight in-process telemetry for fallback paths.

This is intentionally minimal and dependency-free:
- counters are process-local (no file I/O, no network)
- optional stderr logging is gated by DOCPLUCK_FALLBACK_LOG=1
"""

from __future__ import annotations

import os
import sys
from collections import Counter

_FALLBACK_COUNTERS: Counter[str] = Counter()


def record_fallback(event: str, *, detail: str | None = None) -> None:
    _FALLBACK_COUNTERS[event] += 1
    if os.environ.get("DOCPLUCK_FALLBACK_LOG", "0") == "1":
        suffix = f" ({detail})" if detail else ""
        print(f"[docpluck:fallback] {event}{suffix}", file=sys.stderr)


def get_fallback_counters() -> dict[str, int]:
    return dict(_FALLBACK_COUNTERS)


def reset_fallback_counters() -> None:
    _FALLBACK_COUNTERS.clear()

