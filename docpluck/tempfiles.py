"""One place that deletes a temp PDF, for every path that writes one.

## Why this module exists

Five call sites in ``docpluck/`` write the input PDF to a
``NamedTemporaryFile(suffix=".pdf", delete=False)`` and then have to delete it.
Until v2.4.135 they cleaned up three different ways:

    camelot_extract.py  ``_unlink_temp_pdf``  retry after gc, then RECORD
    extract.py          bare ``os.unlink``    RAISES out of ``extract_pdf``
    extract_columns.py  ``except: pass``      silent, twice

and the camelot version carried the comment *"BOTH call sites, because a fix
applied to one of two is not fixed, and this module has a documented history of
exactly that"*. It was a fix applied to **two of five** — the sentence was true
about the module it was written in and false about the library. That is the
project's "one concept, one table" rule: a behaviour with three implementations
has no contract, and the drift is silent because each implementation is locally
correct.

## The invariant

**A temp-PDF cleanup failure must never propagate out of an extraction entry
point, and must never be silent.**

Both halves have cost something already:

* *Propagating* — incident 2026-06-13: on Windows camelot still held the handle,
  ``unlink`` raised ``PermissionError [WinError 32]``, and
  ``extract_structured``'s broad ``except`` read that as "camelot failed" and
  dropped EVERY table on a document whose extraction had entirely succeeded.
  ``extract.py`` had no such net at all: it would simply raise, from the
  library's primary text entry point, after the text was already in hand.
* *Silent* — the previous cleanup swallowed ``PermissionError`` under a comment
  reasoning that "the OS temp dir reclaims the file later". It does not.
  Measured 2026-08-16: **1,535 leaked ``tmp*.pdf``**, one per call, each a full
  copy of the input document. Re-counted 2026-08-19: 1,469 still there. Nobody
  saw it because nothing said it.

Consequences of a leak, in ascending seriousness: disk; then the **"Camelot
cumulative-load flake"** (every leaked file also leaks its open handle, so a
long-lived process accumulates handles until camelot reports "No tables found in
table area" — nine real-PDF tests were failing in full runs and passing alone,
and that was recorded for months as an unexplained property of camelot); then
**the service retains user documents**, because the FastAPI path runs this per
request. That last is a data-retention property nobody chose.

## Why the retry works

The handle is held by the objects camelot returned. Dropping those references
and collecting releases it — verified directly, not reasoned about::

    unlink WITHOUT gc                      -> PermissionError [WinError 32]
    unlink AFTER del tables; gc.collect()  -> OK

The collection is paid ONLY when the first unlink fails, so POSIX — where
unlinking an open file is legal — never runs it.
"""

from __future__ import annotations

import gc
from pathlib import Path

from docpluck.telemetry import record_fallback

TEMP_PDF_NOT_DELETED = "temp_pdf_not_deleted"


def unlink_temp_pdf(tmp_path: str, *held) -> None:
    """Delete a temp PDF. Never raises; records when it genuinely cannot.

    Args:
        tmp_path: the file to remove. A falsy path is a no-op, so a caller whose
            ``NamedTemporaryFile`` never got as far as producing a name can call
            this from its ``finally`` unconditionally.
        held: whatever the call site still references that may hold the file
            handle open (the ``Table`` objects camelot returned). These are
            dropped before the collection.
    """
    if not tmp_path:
        return
    try:
        Path(tmp_path).unlink(missing_ok=True)
        return
    except OSError:
        pass
    # Drop OUR references to the objects holding the handle before collecting.
    # `del` rather than a rebind so the intent survives a linter that would
    # otherwise call the rebind dead.
    del held
    gc.collect()
    try:
        Path(tmp_path).unlink(missing_ok=True)
    except OSError as exc:
        # Genuinely still locked. RECORD it — a silent cleanup failure is what
        # let 1,535 files accumulate unnoticed, and a swallowed error reads
        # exactly like a successful delete.
        record_fallback(TEMP_PDF_NOT_DELETED,
                        detail=f"{Path(tmp_path).name}:{type(exc).__name__}")


__all__ = ["unlink_temp_pdf", "TEMP_PDF_NOT_DELETED"]
