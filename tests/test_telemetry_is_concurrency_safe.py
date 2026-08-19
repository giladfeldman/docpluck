"""Two documents extracted concurrently must not read each other's telemetry.

## The defect (R5), confirmed independently by both reviewers on 2026-08-15

v2.4.133 introduced ``StructuredResult["fallbacks"]`` so a consumer could finally
see what the library had silently done to their document. It computed that field
by diffing ONE process-global ``Counter``:

    before = fallback_snapshot()
    ...extract...
    return {"fallbacks": fallbacks_since(before)}

The FastAPI service runs sync extraction in a threadpool, so two documents
overlap routinely — and the diff then attributes every event recorded by the
OTHER document to this one. A user could be told a table had been dropped from
their paper when it was dropped from a stranger's. The field added to end
write-only telemetry was itself unreliable the moment it had two users.

A ``ContextVar``-scoped sink fixes it: a bare ``threading.Thread`` starts with an
empty context, and ``anyio``/Starlette's ``run_in_threadpool`` copies the
caller's, so sinks opened in one request are invisible to another.

Reproduced against the unfixed code before the fix was written:
``test_concurrent_scopes_do_not_bleed`` failed with each thread reporting the
other's events (observed counts of 200 where 100 were expected).
"""

from __future__ import annotations

import threading

from docpluck.telemetry import (
    fallback_scope,
    get_fallback_counters,
    get_fallback_details,
    record_fallback,
)


def test_concurrent_scopes_do_not_bleed():
    """Two threads, each recording only its own event, must each see only its own.

    The barrier is what makes this a real test rather than a lucky schedule: it
    guarantees both scopes are OPEN at the same time, which is precisely the
    window in which a shared global counter cross-contaminates.
    """
    n = 100
    results: dict[str, dict[str, int]] = {}
    start = threading.Barrier(2)

    def worker(name: str) -> None:
        with fallback_scope() as fb:
            start.wait(timeout=10)
            for _ in range(n):
                record_fallback(f"event_{name}")
        results[name] = dict(fb.counters)

    threads = [threading.Thread(target=worker, args=(nm,)) for nm in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert results["a"] == {"event_a": n}, (
        f"thread a saw thread b's events: {results['a']}"
    )
    assert results["b"] == {"event_b": n}, (
        f"thread b saw thread a's events: {results['b']}"
    )


def test_nested_scopes_report_independently_and_the_outer_sees_everything():
    """An inner scope reports only its own window; the outer still sees the lot.

    Both halves matter. If an inner scope swallowed its events, a caller wrapping
    the whole pipeline would silently lose whatever a scoped inner stage
    recorded — which is the same write-only failure in a new place.
    """
    with fallback_scope() as outer:
        record_fallback("outer_only")
        with fallback_scope() as inner:
            record_fallback("inner_only")
        assert inner.counters == {"inner_only": 1}
    assert outer.counters == {"outer_only": 1, "inner_only": 1}


def test_detail_survives_to_the_scope():
    """``detail`` is the whole point of the field: it names WHICH font/exception
    fired the event. It used to be accepted and discarded."""
    with fallback_scope() as fb:
        record_fallback("symbol_font_greek_corruption_detected", detail="AdvPS7DA6")
        record_fallback("symbol_font_greek_corruption_detected", detail="AdvPS7DA6")
        record_fallback("symbol_font_greek_corruption_detected", detail="AdvOT463cc31e")
    assert fb.counters == {"symbol_font_greek_corruption_detected": 3}
    assert fb.details == {
        "symbol_font_greek_corruption_detected": {
            "AdvPS7DA6": 2,
            "AdvOT463cc31e": 1,
        }
    }


def test_process_cumulative_counters_still_work():
    """The process-wide totals are what batch runs and diagnostics read, and are
    genuinely process-wide information. Scoping the per-document view must not
    have removed them."""
    before = get_fallback_counters().get("cumulative_probe", 0)
    with fallback_scope():
        record_fallback("cumulative_probe", detail="x")
    assert get_fallback_counters().get("cumulative_probe", 0) == before + 1
    assert "x" in get_fallback_details().get("cumulative_probe", {})


def test_a_scope_records_even_with_no_enclosing_scope():
    """Recording outside any scope must not raise — most of the library's 30-odd
    call sites run on paths a caller never scopes."""
    record_fallback("unscoped_probe")
