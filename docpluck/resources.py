"""Tell "the MACHINE ran out" apart from "the DOCUMENT failed".

## Why this module exists

Measured 2026-09-24/25. The release A/B ran the whole corpus through the service
three times (once per normalization level). Table output does not depend on the
level, yet 7-8 of 135 papers gave different ``tables.json`` in different runs of
the same PDF. It was not CPU load: 12 simultaneous processes on the same 55-page
paper (10.15626/mp.2022.3108) gave 12 byte-identical results. It was MEMORY. The
machine was out of commit ("the paging file is too small"), and:

* Camelot's lattice pass rasterises each page and runs OpenCV's adaptive
  threshold over it. Under memory pressure that raises
  ``cv2.error (-4: Insufficient memory)``. ``extract_tables_camelot`` caught it
  as ``camelot_lattice_exception`` and carried on with NO lattice tables, so every
  ruled table fell back to its stream reading. Reproduced with a 700 MB
  per-process cap (a Windows Job Object, so no other process is touched) on
  10.1038/s41598-023-50588-1: different tables, and the ``method`` string was
  byte-identical to the healthy run. A consumer could not tell.
* The region-driven pass does the same per page (``camelot_region_exception``
  -> ``continue``), which is the chandrashekar ``region_pick:1`` vs
  ``region_pick:4`` split.
* A full disk does the same one step earlier: the temp PDF cannot be written
  (``OSError [Errno 28]``), measured on this machine the same night.

Each of those handlers is CORRECT for a document-caused failure: a malformed
page should cost that page, not the paper. It is wrong for a machine-caused one,
because the same bytes then produce a different answer depending on what else is
running. So the two are told apart HERE, in one place, keyed on the error
CODES the libraries themselves define (never on message text, which a library
can reword in a patch release and silently turn this off):

* :func:`is_resource_exhaustion` -- the classifier.
* :func:`call_with_resource_retry` -- retry a call that failed for want of
  memory/disk, after releasing what we can. Transient pressure then yields the
  SAME output as a quiet machine.
* ``telemetry.record_fallback`` consults the classifier for the exception being
  handled, so EVERY degradation that happened because the machine ran out is
  also recorded as :data:`RESOURCE_EXHAUSTED`, whichever of the library's catch
  sites it went through; ``extract_pdf_structured`` then labels ``method`` with
  :data:`INCOMPLETE_METHOD_PIECE`. Pressure that outlasts the retries is
  therefore never silent.
"""

from __future__ import annotations

import errno
import gc
import sys
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

# The fallback event recorded when a degradation was caused by the machine, not
# the document. Its detail is the event of the step that degraded.
RESOURCE_EXHAUSTED = "resource_exhausted"
# One retry attempt of a call that failed for want of resources. Recorded even
# when the retry then succeeds, so a run that needed one says so.
RESOURCE_RETRY = "resource_retry"
# What ``extract_pdf_structured`` appends to ``method`` when RESOURCE_EXHAUSTED
# fired: the tables of this result are not the ones a quiet machine produces.
INCOMPLETE_METHOD_PIECE = "incomplete:resource_exhausted"

_ERRNOS = frozenset({errno.ENOSPC, errno.ENOMEM, errno.EMFILE, errno.ENFILE})
# Windows system error codes: ERROR_NOT_ENOUGH_MEMORY, ERROR_OUTOFMEMORY,
# ERROR_DISK_FULL, ERROR_NO_SYSTEM_RESOURCES, ERROR_COMMITMENT_LIMIT ("the paging
# file is too small for this operation to complete").
_WINERRORS = frozenset({8, 14, 112, 1450, 1455})

# Attempts in total (1 = no retry). Backoff doubles from the base: 1s, 2s, 4s.
# Sized for pressure from OTHER processes, which comes and goes over seconds; it
# costs nothing on a machine that never fails, and at most 7s on one that does.
RETRY_ATTEMPTS = 4
RETRY_BACKOFF_S = 1.0


def _is_cv2_out_of_memory(exc: BaseException) -> bool:
    # Only if OpenCV is already loaded: if it is not, this cannot be its error,
    # and importing it here would cost every caller an OpenCV import.
    cv2 = sys.modules.get("cv2")
    if cv2 is None:
        return False
    err_type = getattr(cv2, "error", None)
    no_mem = getattr(getattr(cv2, "Error", None), "StsNoMem", None)
    return (
        isinstance(err_type, type)
        and isinstance(exc, err_type)
        and no_mem is not None
        and getattr(exc, "code", None) == no_mem
    )


def is_resource_exhaustion(exc: BaseException | None) -> bool:
    """True if ``exc``, or any exception in its cause/context chain, means the
    machine ran out of memory, disk or handles -- not that the input is bad.

    The chain is walked because libraries wrap: a ``MemoryError`` raised inside
    a Camelot page parse can surface as some other exception type.
    """
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, MemoryError):
            return True
        if isinstance(exc, OSError) and (
            exc.errno in _ERRNOS or getattr(exc, "winerror", None) in _WINERRORS
        ):
            return True
        if _is_cv2_out_of_memory(exc):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def note_if_exhausted(exc: BaseException, *, where: str) -> None:
    """Record :data:`RESOURCE_EXHAUSTED` for a catch site that deliberately does
    NOT call ``record_fallback`` inside its handler (it returns a refusal reason,
    or substitutes a placeholder, and the caller records later -- outside the
    handler, where the in-flight exception is already gone).

    Found by a Sonnet review, 2026-09-25: ``cell_geometry`` swallowed a failure
    per table and per cell, so a MemoryError there changed ``cell_geometry`` and
    the bboxes with no label. An AST scan of the library the same day found 17
    broad handlers that neither record nor re-raise; these (and one in
    ``camelot_extract._camelot_flavor``) were the only ones on the table path.
    """
    if is_resource_exhaustion(exc):
        from docpluck.telemetry import record_fallback

        record_fallback(RESOURCE_EXHAUSTED, detail=where)


def call_with_resource_retry(fn: Callable[[], T], *, what: str) -> T:
    """Call ``fn()``; if it fails for want of resources, release what we hold,
    wait, and try again, up to :data:`RETRY_ATTEMPTS` in total.

    Any other exception propagates on the first attempt, untouched: retrying a
    document-caused failure costs time and cannot change its answer. The last
    resource failure propagates too, so the caller's own handler still runs --
    and ``record_fallback`` in that handler records :data:`RESOURCE_EXHAUSTED`.

    The wait can change latency, never output: every attempt runs the identical
    call on the identical input, and nothing is cut short when time runs out.
    """
    from docpluck.telemetry import record_fallback

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt >= RETRY_ATTEMPTS or not is_resource_exhaustion(exc):
                raise
            record_fallback(RESOURCE_RETRY, detail=f"{what}:{type(exc).__name__}")
        # Outside the handler, so the failed attempt's frames (which hold its
        # partial arrays and the traceback) are unreachable before collecting.
        gc.collect()
        time.sleep(RETRY_BACKOFF_S * (2 ** (attempt - 1)))
    raise AssertionError("unreachable")  # pragma: no cover
