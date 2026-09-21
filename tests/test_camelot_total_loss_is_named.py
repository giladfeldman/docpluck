"""A total loss of the table channel must NAME itself in the artifact.

Why this file exists (2026-09-21). `extract_tables_camelot` catches its own
``ImportError`` and both per-flavor exceptions and then returns ``[]``
**normally**. Nothing propagates, so ``extract_structured``'s

    except Exception as exc:
        method_pieces.append(f"camelot_failed:{exc_name}")

never fired for either case, and no token was appended. A document that got
zero tables because Camelot could not run was byte-identical in ``method`` to a
document that genuinely has no tables.

MEASURED, so the scope of the claim is honest rather than rhetorical. Forcing
both Camelot flavors to raise DOES turn tests red -- 14 failed / 3 errors over
the 34 test files that reach the capability. But not one of those failures says
"Camelot did not run": they are cell-geometry and table-content tests failing
for downstream reasons, and a maintainer reading them debugs the wrong layer.
Meanwhile the two assertions that DO look at a camelot token cannot see it:

* ``tests/test_extract_pdf_structured.py`` asserts
  ``any(tok in method for tok in ("camelot_stream", "camelot_failed"))`` --
  which passes whether Camelot worked or blew up; and
* ``tests/test_smoke_fixtures.py`` has ``COUNT_TOLERANCE = 6``, and 8 of its 12
  fixtures expect <= 6 tables, so ZERO tables is inside tolerance for them.

And the suite is not the consumer. A corpus measurement reads the artifact, so a
box where Ghostscript or Camelot is mis-installed reports "these papers have no
tables" with a clean `method` string and nothing red anywhere near the numbers.
That is what this file closes: the artifact now names the loss, and this gate
fails if it ever stops doing so.

Same shape as ``tests/test_column_correction_actually_fires.py`` and
``tests/test_banded_crop_failure_is_not_silent.py``: an exception recorded only
where nothing asserts.
"""

import os
import sys

import pytest

from docpluck.extract_structured import extract_pdf_structured
from docpluck.tables.camelot_extract import CAMELOT_UNAVAILABLE_EVENTS
from docpluck.telemetry import fallback_scope
from docpluck.testing import require_corpus_pdf

pytest.importorskip("camelot", reason="camelot not installed (pip install docpluck[all])")

# Nine tables on the default path, `camelot_stream` in the method string.
_PAPER = "apa/chan_feldman_2025_cogemo.pdf"


@pytest.fixture(scope="module")
def paper_bytes() -> bytes:
    # require_, not corpus_pdf: a paper this gate claims to test and cannot read
    # is a FAILURE, never a skip.
    return require_corpus_pdf(_PAPER).read_bytes()


@pytest.fixture(autouse=True)
def _camelot_must_be_enabled(monkeypatch):
    """This whole file is meaningless under ``DOCPLUCK_DISABLE_CAMELOT``.

    36 test modules set that flag, and `conftest.py` restores it per module --
    but a leak would make every assertion below pass vacuously, which is the
    one outcome a capability gate must never have.
    """
    monkeypatch.delenv("DOCPLUCK_DISABLE_CAMELOT", raising=False)
    assert os.environ.get("DOCPLUCK_DISABLE_CAMELOT", "0") != "1"


def test_the_table_channel_fires_on_the_default_path(paper_bytes):
    """The capability runs, produces tables, and says it ran."""
    with fallback_scope() as fb:
        result = extract_pdf_structured(paper_bytes)
    method = result["method"]
    assert result["tables"], (
        "no tables extracted from a paper known to carry nine. Either the table "
        f"channel is broken or this paper stopped exercising it. method={method}"
    )
    assert "camelot_stream" in method, f"method does not report Camelot ran: {method}"
    leaked = CAMELOT_UNAVAILABLE_EVENTS & fb.counters.keys()
    assert not leaked, (
        f"Camelot reported itself unavailable on a working path: {sorted(leaked)}"
    )


def test_both_flavors_failing_is_named_in_the_method_string(paper_bytes, monkeypatch):
    """Two-sided control #1: the defect this file exists for.

    Both ``camelot.read_pdf`` calls raise, so ``extract_tables_camelot``
    returns ``[]`` the same way a table-less paper does -- and nothing
    propagates, so the caller's ``except`` cannot see it.
    """
    import camelot

    def _boom(*_a, **_kw):
        raise RuntimeError("injected: camelot backend unavailable")

    monkeypatch.setattr(camelot, "read_pdf", _boom)

    with fallback_scope() as fb:
        result = extract_pdf_structured(paper_bytes)
    method = result["method"]

    assert "camelot_all_flavors_failed" in fb.counters, (
        "both Camelot parsers raised and the library recorded nothing. "
        f"fallbacks={fb.counters}"
    )
    assert "camelot_failed:" in method, (
        "the table channel was entirely lost and the method string does not say "
        f"so -- zero tables is indistinguishable from a paper that has none. "
        f"method={method}"
    )
    assert "camelot_stream" not in method, (
        f"method claims Camelot ran while both parsers were raising: {method}"
    )


def test_camelot_not_installed_is_named_too(paper_bytes, monkeypatch):
    """Two-sided control #2: the branch with no telemetry AT ALL.

    ``except ImportError: return []`` recorded nothing whatsoever, so a machine
    without Camelot reported every paper as table-less in silence. Setting the
    module to ``None`` is what makes ``import camelot`` raise ImportError
    without patching ``builtins.__import__``, which perturbs unrelated imports.
    """
    monkeypatch.setitem(sys.modules, "camelot", None)

    with fallback_scope() as fb:
        result = extract_pdf_structured(paper_bytes)
    method = result["method"]

    assert "camelot_not_installed" in fb.counters, (
        f"Camelot was absent and nothing was recorded. fallbacks={fb.counters}"
    )
    assert "camelot_failed:" in method, (
        f"an absent Camelot left no trace in the method string. method={method}"
    )


def test_the_event_vocabulary_has_exactly_one_definition():
    """`CAMELOT_UNAVAILABLE_EVENTS` is the producer's own set.

    `extract_structured` turns these events into a method-string token. A
    second copy of the vocabulary would drift from the producer silently -- the
    failure mode this project is named for twice over (two Greek tables, two
    line-ending conventions). So assert the consumer imports the producer's
    set rather than restating it.
    """
    import docpluck.extract_structured as es
    from docpluck.tables import camelot_extract as ce

    assert es.CAMELOT_UNAVAILABLE_EVENTS is ce.CAMELOT_UNAVAILABLE_EVENTS, (
        "extract_structured is using its own copy of the unavailable-event "
        "vocabulary; the two will drift and the method string will go quiet again"
    )
    # And every member must actually be recorded somewhere in the producer --
    # an event name nobody emits makes the token unreachable.
    src = (ce.__file__ and open(ce.__file__, encoding="utf-8").read()) or ""
    for event in ce.CAMELOT_UNAVAILABLE_EVENTS:
        assert f'"{event}"' in src, (
            f"{event!r} is in CAMELOT_UNAVAILABLE_EVENTS but nothing in "
            f"camelot_extract.py records it, so the method token can never fire"
        )
