"""A band whose pdftotext crop DID NOT RUN must abandon the page, loudly.

Why this file exists (2026-09-17, re-gated 2026-09-21).
``extract_page_text_banded`` re-extracts a page band by band, shelling out to
``pdftotext`` once per band with ``timeout=30``. The crop helper swallowed every
failure into ``return ""``:

    except Exception:
        return ""

so a timeout, a non-zero exit and a genuinely blank region were the same value.
The caller joined the parts, so an expired band simply VANISHED and the page came
back short -- with every surviving word still in the right order, which is
exactly what a real word loss looks like. Observed:
``test_banded_reextraction_is_word_preserving_real_pdf`` failed with
``{'and': 17} != {'and': 19}`` during a run that took 1:00:06 for work that takes
46 s on a quiet machine, and passed on both trees afterwards. Machine load became
a correctness-shaped failure, which is the most expensive kind of flake because
it accuses the code under test.

In production the splice's word-multiset guard refused the short page, so no
wrong text ever shipped. That is the trap: the capability was dropped for that
page with **no record of any kind**, so a machine under load quietly stopped
correcting columns and every artifact still looked complete. Same shape as the
2026-09-17 ``column_correction_failed:TypeError`` defect
(``tests/test_column_correction_actually_fires.py``) -- a swallowed exception
recorded nowhere anything asserts on.

The general shape, which is worth more than this one fix: a swallowed
subprocess timeout turns machine load into a correctness failure. The slow
machine does not report being slow -- it reports wrong output.
"""

import re
import subprocess
from collections import Counter

import pytest

from docpluck.extract_columns import extract_page_text_banded
from docpluck.extract_layout import extract_pdf_layout
from docpluck.telemetry import fallback_scope
from docpluck.testing import require_corpus_pdf

# Page 7 (index 6) is a full-width Table 2 above a two-column body, so the band
# segmenter produces MORE THAN ONE band -- the precondition for this whole
# failure mode, asserted below rather than assumed.
_PAPER = "apa/chan_feldman_2025_cogemo.pdf"
_PAGE_IDX = 6


@pytest.fixture(scope="module")
def layout_and_bytes():
    # require_, not corpus_pdf: a paper this gate claims to test and cannot read
    # is a FAILURE, never a skip. A skipped capability gate is indistinguishable
    # from a passing one in a summary line.
    data = require_corpus_pdf(_PAPER).read_bytes()
    return extract_pdf_layout(data), data


def _subst_words(text: str) -> Counter:
    return Counter(re.findall(r"[^\W\d_]{2,}", text.casefold(), flags=re.UNICODE))


def test_banded_reextraction_fires_with_no_env_flags(layout_and_bytes):
    """The capability runs on a real paper on the default path."""
    layout, data = layout_and_bytes
    out = extract_page_text_banded(layout, _PAGE_IDX, data)
    assert out.strip(), (
        "banded re-extraction returned nothing on a page it is known to rebuild; "
        "the capability is not running and nothing else in the suite would say so"
    )
    # Multi-band is the precondition for a per-band failure to be possible at
    # all. If this page ever became single-band, the control below would pass
    # vacuously -- so it fails here instead, loudly.
    assert len(out.splitlines()) > 1, "expected a multi-line band reassembly"


def test_a_failed_crop_abandons_the_page_instead_of_shortening_it(
    layout_and_bytes, monkeypatch
):
    """Two-sided control: make the crop time out, prove the loss is not silent.

    Without this arm the test above could pass while every failure mode stayed
    invisible -- and a vacuous gate is worse than none, because it is counted.
    """
    layout, data = layout_and_bytes
    real_run = subprocess.run
    calls = {"n": 0}

    def _timeout_on_the_second_crop(cmd, *a, **kw):
        # Fail ONE band, not all of them. Failing every band would produce an
        # empty page for the uninteresting reason; the defect was a page
        # assembled from SOME of its bands.
        if isinstance(cmd, list) and "-x" in cmd:
            calls["n"] += 1
            if calls["n"] == 2:
                raise subprocess.TimeoutExpired(cmd, 30)
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(subprocess, "run", _timeout_on_the_second_crop)

    with fallback_scope() as fb:
        out = extract_page_text_banded(layout, _PAGE_IDX, data)

    assert calls["n"] >= 2, (
        "the injected timeout never reached a second crop, so this control "
        f"proves nothing about the gate (crops attempted: {calls['n']})"
    )
    assert "banded_crop_timeout" in fb.counters, (
        "a pdftotext crop timed out and the library recorded nothing; the "
        f"capability can now fail invisibly. fallbacks={fb.counters}"
    )
    assert out == "", (
        "a timed-out band produced a PARTIAL page rather than abandoning it. "
        "That page is a word loss wearing a reorder's clothes -- exactly the "
        f"{{'and': 17}} != {{'and': 19}} failure this gate exists for. "
        f"got {len(_subst_words(out))} distinct words"
    )


def test_a_nonzero_exit_is_recorded_too(layout_and_bytes, monkeypatch):
    """The other silent branch: `pdftotext` ran and failed.

    ``returncode != 0`` had its own bare ``return ""``, which no amount of
    exception handling would have covered.
    """
    layout, data = layout_and_bytes
    real_run = subprocess.run
    calls = {"n": 0}

    class _Failed:
        returncode = 1
        stdout = ""
        stderr = "injected"

    def _fail_second_crop(cmd, *a, **kw):
        if isinstance(cmd, list) and "-x" in cmd:
            calls["n"] += 1
            if calls["n"] == 2:
                return _Failed()
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(subprocess, "run", _fail_second_crop)

    with fallback_scope() as fb:
        out = extract_page_text_banded(layout, _PAGE_IDX, data)

    assert calls["n"] >= 2, f"injection never reached a second crop ({calls['n']})"
    assert "banded_crop_nonzero_exit" in fb.counters, (
        f"pdftotext exited non-zero and nothing was recorded. fallbacks={fb.counters}"
    )
    assert out == "", "a failed crop produced a partial page"
