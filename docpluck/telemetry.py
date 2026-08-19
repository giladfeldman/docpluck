"""Lightweight in-process telemetry for fallback paths.

This is intentionally minimal and dependency-free:
- counters are process-local (no file I/O, no network)
- optional stderr logging is gated by DOCPLUCK_FALLBACK_LOG=1

## Why the sinks are context-scoped rather than a bare module global

Until v2.4.133 this module held one process-global ``Counter`` and every reader
diffed it. The FastAPI service runs sync extraction in a threadpool, so two
documents extracted concurrently incremented the SAME counter and each one's
``fallbacks`` reported the other's events — a document could be told a table had
been dropped that was dropped from a different paper. Reproduced with a
two-thread probe (Sonnet, 2026-08-15); pinned by
``tests/test_telemetry_is_concurrency_safe.py``.

A :class:`ContextVar` fixes it because every concurrency primitive that matters
here starts with its own context: a bare ``threading.Thread`` begins with an
empty one, and ``anyio``/Starlette's ``run_in_threadpool`` copies the caller's.
So sinks opened inside one request are invisible to another.

The cumulative process-global counter is KEPT, because it is what a batch run
and the diagnostics read, and it is genuinely process-wide information. It is
simply no longer the thing a per-document result is computed from.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from contextvars import ContextVar

# Process-lifetime cumulative totals. Diagnostics and batch summaries read this;
# per-document results never do (see the module docstring).
_FALLBACK_COUNTERS: Counter[str] = Counter()
_FALLBACK_DETAILS: dict[str, Counter[str]] = {}

# The stack of open :class:`fallback_scope` sinks for THIS context. A tuple so
# that setting it is an atomic rebind rather than a mutation another context
# could observe half-done.
_SINKS: ContextVar[tuple["fallback_scope", ...]] = ContextVar("_SINKS", default=())


def record_fallback(event: str, *, detail: str | None = None) -> None:
    """Record that a fallback path fired.

    ``event`` is a stable machine-readable name and is what consumers key on.
    ``detail`` is the specific instance — the font that looked corrupt, the
    exception type, the shape that was too small.

    **``detail`` used to go nowhere.** The Counter was keyed on ``event`` alone,
    so ``record_fallback("symbol_font_greek_corruption_detected", detail=font)``
    discarded the font name and the doc comment promising a consumer "can see
    which document to distrust" was false of the artifact — a false positive and
    a real corruption arrived indistinguishable. Details are now counted per
    event and travel with it.
    """
    _FALLBACK_COUNTERS[event] += 1
    if detail:
        _FALLBACK_DETAILS.setdefault(event, Counter())[detail] += 1
    for sink in _SINKS.get():
        sink._record(event, detail)
    if os.environ.get("DOCPLUCK_FALLBACK_LOG", "0") == "1":
        suffix = f" ({detail})" if detail else ""
        print(f"[docpluck:fallback] {event}{suffix}", file=sys.stderr)


def get_fallback_counters() -> dict[str, int]:
    """Process-lifetime cumulative totals. NOT per-document — use
    :class:`fallback_scope` for that."""
    return dict(_FALLBACK_COUNTERS)


def get_fallback_details() -> dict[str, dict[str, int]]:
    """Process-lifetime ``{event: {detail: count}}``."""
    return {event: dict(counts) for event, counts in _FALLBACK_DETAILS.items()}


def reset_fallback_counters() -> None:
    _FALLBACK_COUNTERS.clear()
    _FALLBACK_DETAILS.clear()


class fallback_scope:
    """Capture the fallbacks recorded inside a ``with`` block.

    **Why this exists.** Until v2.4.133 there were 31 ``record_fallback(...)``
    call sites in the library and **the only reader of ``get_fallback_counters()``
    anywhere was a test.** Every silent substitution, every dropped table, every
    refused repair was write-only in production: the library recorded that it had
    done something unusual and then told nobody. That is the fourth of the
    project's four checks — *every value computed is read back* — failed across
    an entire telemetry subsystem, including the ambiguous-pairing refusals added
    in that same release.

    **And then the fix re-created the defect one layer up**: the first version of
    this class had ZERO call sites of its own, so it was itself write-only. It is
    now the mechanism behind both ``StructuredResult["fallbacks"]`` and
    ``NormalizationReport.fallbacks`` — grep for `fallback_scope(` before
    believing this sentence.

        with fallback_scope() as fb:
            result = extract_pdf_structured(data)
        fb.counters   # -> {"camelot_table_below_accuracy_threshold": 2, ...}
        fb.details    # -> {"symbol_font_greek_corruption_detected": {"AdvPS7DA6": 13}}

    Scopes are per-CONTEXT, so two documents extracted concurrently in a
    threadpool cannot see each other's events. Nested scopes each see only what
    happened inside them, and an inner scope's events also reach every enclosing
    one — a caller wrapping the whole pipeline must not lose an event just
    because an inner stage happened to be scoped too.
    """

    __slots__ = ("counters", "details", "_token")

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.details: dict[str, dict[str, int]] = {}
        self._token = None

    def _record(self, event: str, detail: str | None) -> None:
        self.counters[event] = self.counters.get(event, 0) + 1
        if detail:
            per_event = self.details.setdefault(event, {})
            per_event[detail] = per_event.get(detail, 0) + 1

    def __enter__(self) -> "fallback_scope":
        self.counters = {}
        self.details = {}
        self._token = _SINKS.set(_SINKS.get() + (self,))
        return self

    def __exit__(self, *_exc) -> None:
        if self._token is not None:
            _SINKS.reset(self._token)
            self._token = None
        return None
