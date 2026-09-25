"""A machine that runs out of memory or disk must not change table output silently.

Measured 2026-09-24/25 (see ``docpluck/resources.py`` for the full record): in a
135-paper service run, 7-8 papers gave different ``tables.json`` in different
runs of the same PDF. Twelve simultaneous processes on one paper gave twelve
identical results, so it was not CPU load; a 700 MB per-process memory cap on
10.1038/s41598-023-50588-1 reproduced it (``camelot_lattice_exception`` -> the
stream reading of every ruled table, under a ``method`` byte-identical to the
healthy run's), and 1000 MB / 1500 MB caps did not.

These tests pin the three parts of the fix, each two-sided:

* the classifier separates machine-caused failures from document-caused ones;
* a transient machine failure is retried, so the output is the quiet-machine
  output; a document failure is not retried;
* a failure that outlasts the retries is recorded as ``resource_exhausted`` AND
  marks ``method``, through whichever catch site it passed.
"""
from __future__ import annotations

import errno

import pytest

from docpluck import resources
from docpluck.resources import (
    INCOMPLETE_METHOD_PIECE,
    RESOURCE_EXHAUSTED,
    RESOURCE_RETRY,
    call_with_resource_retry,
    is_resource_exhaustion,
)
from docpluck.telemetry import fallback_scope, record_fallback


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr(resources, "RETRY_BACKOFF_S", 0.0)


# ── the classifier ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("exc", [
    MemoryError(),
    OSError(errno.ENOSPC, "No space left on device"),
    OSError(errno.ENOMEM, "Cannot allocate memory"),
    OSError(errno.EMFILE, "Too many open files"),
])
def test_machine_failures_are_classified_as_exhaustion(exc):
    assert is_resource_exhaustion(exc)


@pytest.mark.parametrize("exc", [
    ValueError("malformed page"),
    KeyError("x"),
    OSError(errno.ENOENT, "No such file"),
    PermissionError(errno.EACCES, "denied"),
    None,
])
def test_document_failures_are_not(exc):
    assert not is_resource_exhaustion(exc)


def test_windows_commit_limit_is_exhaustion():
    # ERROR_COMMITMENT_LIMIT, "the paging file is too small" -- the exact state
    # the machine was in when the variance was measured.
    exc = OSError(errno.EINVAL, "paging file too small")
    exc.winerror = 1455
    assert is_resource_exhaustion(exc)


def test_a_wrapped_memory_error_is_still_found():
    try:
        try:
            raise MemoryError()
        except MemoryError as inner:
            raise RuntimeError("page parse failed") from inner
    except RuntimeError as outer:
        assert is_resource_exhaustion(outer)


def test_opencv_out_of_memory_is_keyed_on_its_code_not_its_text():
    cv2 = pytest.importorskip("cv2")
    oom = cv2.error("some future wording")
    oom.code = cv2.Error.StsNoMem
    other = cv2.error("Insufficient memory")  # the TEXT alone must not count
    other.code = cv2.Error.StsAssert
    assert is_resource_exhaustion(oom)
    assert not is_resource_exhaustion(other)


# ── retry ───────────────────────────────────────────────────────────────────


def test_transient_exhaustion_is_retried_to_the_same_answer():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise MemoryError()
        return "the quiet-machine answer"

    with fallback_scope() as fb:
        out = call_with_resource_retry(flaky, what="probe")
    assert out == "the quiet-machine answer"
    assert len(calls) == 2
    assert fb.counters.get(RESOURCE_RETRY) == 1
    # It WORKED, so the result is not incomplete and must not be marked so.
    assert RESOURCE_EXHAUSTED not in fb.counters


def test_persistent_exhaustion_propagates_after_the_attempts():
    calls = []

    def always():
        calls.append(1)
        raise MemoryError()

    with pytest.raises(MemoryError):
        call_with_resource_retry(always, what="probe")
    assert len(calls) == resources.RETRY_ATTEMPTS


def test_a_document_failure_is_not_retried():
    calls = []

    def bad_page():
        calls.append(1)
        raise ValueError("malformed")

    with pytest.raises(ValueError):
        call_with_resource_retry(bad_page, what="probe")
    assert calls == [1]


# ── the telemetry hook: every catch site, not one ───────────────────────────


def test_a_degradation_caused_by_exhaustion_is_recorded_as_such():
    with fallback_scope() as fb:
        try:
            raise MemoryError()
        except Exception:  # noqa: BLE001 - the shape of the library catch sites
            record_fallback("some_step_exception", detail="MemoryError")
    assert fb.counters.get(RESOURCE_EXHAUSTED) == 1
    assert fb.details[RESOURCE_EXHAUSTED] == {"some_step_exception": 1}


def test_a_degradation_caused_by_the_document_is_not():
    with fallback_scope() as fb:
        try:
            raise ValueError()
        except Exception:  # noqa: BLE001 - the shape of the library catch sites
            record_fallback("some_step_exception", detail="ValueError")
        record_fallback("camelot_table_too_small", detail="1x3")  # no exception at all
    assert RESOURCE_EXHAUSTED not in fb.counters


# ── end to end: the real extraction path ────────────────────────────────────


def _fake_camelot_that_runs_out(monkeypatch, *, failures: int):
    """Make the first ``failures`` Camelot calls fail the way the machine did,
    then behave normally. Returns the list of call flavors seen."""
    camelot = pytest.importorskip("camelot")
    real = camelot.read_pdf
    seen: list[str] = []

    def read_pdf(*args, **kwargs):
        seen.append(kwargs.get("flavor", "?"))
        if len(seen) <= failures:
            raise MemoryError("induced")
        return real(*args, **kwargs)

    monkeypatch.setattr(camelot, "read_pdf", read_pdf)
    return seen


def _real_pdf():
    from docpluck.testing import require_corpus_pdf

    # 10.1371/journal.pmed.1004323 -- one of the papers whose tables.json varied
    # between runs in the 2026-09-24 A/B.
    return require_corpus_pdf("vancouver/plos_med_1.pdf").read_bytes()


def _fingerprint(result):
    return [(t.get("id"), t.get("label"), t.get("page"), t.get("kind"),
             t.get("n_rows"), t.get("n_cols"), t.get("html")) for t in result["tables"]]


def test_transient_exhaustion_yields_the_quiet_machine_tables(monkeypatch):
    from docpluck.extract_structured import extract_pdf_structured

    data = _real_pdf()
    quiet = extract_pdf_structured(data)
    assert quiet["tables"], "control: this paper must have tables, or the test proves nothing"

    seen = _fake_camelot_that_runs_out(monkeypatch, failures=1)
    loaded = extract_pdf_structured(data)
    assert len(seen) > 1, "the fault was never injected"
    assert _fingerprint(loaded) == _fingerprint(quiet)
    assert loaded["method"] == quiet["method"]
    assert loaded["fallbacks"].get(RESOURCE_RETRY) == 1
    assert RESOURCE_EXHAUSTED not in loaded["fallbacks"]


def test_persistent_exhaustion_is_labelled_in_method(monkeypatch):
    from docpluck.extract_structured import extract_pdf_structured

    data = _real_pdf()
    # Enough failures to exhaust the retries of the first (stream) pass and no
    # more, so the rest of the pipeline runs and must still carry the label.
    _fake_camelot_that_runs_out(monkeypatch, failures=resources.RETRY_ATTEMPTS)
    loaded = extract_pdf_structured(data)
    assert loaded["fallbacks"].get(RESOURCE_EXHAUSTED), loaded["fallbacks"]
    assert loaded["method"].endswith("+" + INCOMPLETE_METHOD_PIECE), loaded["method"]
