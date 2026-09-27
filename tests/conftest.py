"""
Test configuration for docpluck library tests.

PDF-dependent tests are skipped gracefully when pdftotext is not installed
or when test PDFs are not available (library tests should run anywhere).
"""

import os
import shutil
import sys

import pytest

# Ensure subprocess calls that invoke the docpluck CLI inherit UTF-8 stdio.
# This is needed on Windows where the default console encoding is cp1252 and
# U+2212 (MINUS SIGN) — which appears in normalized statistical text — is not
# representable.  Setting PYTHONUTF8 here propagates to any subprocess launched
# by subprocess.run() in tests without an explicit env= argument.
os.environ.setdefault("PYTHONUTF8", "1")


def pytest_addoption(parser):
    """Flags for the v2 backwards-compatibility checksum gate.

    The gate used to store the full ``extract_pdf()`` text of 12 published
    papers under ``tests/snapshots/`` — 984 KB of somebody else's article,
    tracked in a PUBLIC repo. A sha256 gives the identical byte-for-byte
    guarantee in ~1 KB, so the text is gone. What the text bought that a hash
    does not is *diff context on failure*; ``--snapshot-explain`` regenerates
    that locally, on demand, from the PDF that is already on the machine.
    """
    g = parser.getgroup("docpluck snapshots")
    g.addoption(
        "--snapshot-update", action="store_true", default=False,
        help="rewrite tests/snapshots/checksums.json from a live extract run",
    )
    g.addoption(
        "--snapshot-explain", action="store_true", default=False,
        help="on mismatch, dump the actual extract_pdf() text to tmp/snapshots/ "
             "so it can be diffed locally (never committed)",
    )


def pdftotext_available():
    """Check if pdftotext binary is on PATH."""
    return shutil.which("pdftotext") is not None


# Skip marker for tests that require pdftotext
requires_pdftotext = pytest.mark.skipif(
    not pdftotext_available(),
    reason="pdftotext not installed (apt-get install poppler-utils)"
)

# Test PDF directories — optional, tests skip if not present.
# No machine's directory layout is written in this public file: the article
# repository comes from $ARTICLE_REPOSITORY, private corpora from
# `tests/corpora.local.json` (see `_local_corpora.py`).
_HERE = os.path.dirname(__file__)

# NOTE: there is no "docpluck" key here any more. docpluck's own corpus resolves
# through the article custodian by DOI -- `docpluck.testing.corpus.corpus_pdf` --
# not through a directory, and a paper it cannot find FAILS rather than skipping.
# The one key below is the custodian's DOI-named fulltext folder, for tests that
# key on a paper outside the manifest.
# Machine-local corpora in PRIVATE sibling repos -- ONE definition, in
# `tests/_local_corpora.py`. Re-exported here so conftest users can reach it.
sys.path.insert(0, _HERE) if _HERE not in sys.path else None
from _local_corpora import local_corpus  # noqa: F401

from docpluck.testing import custody_path as _custody_path

PDF_PATHS = {
    # The shared article repository (article-finder cache). Closed-access PDFs
    # named by canonical DOI key (e.g. "10.1525__collabra.90203.pdf"). Tests
    # that key on a specific paper skip gracefully when the repo isn't present.
    # Resolved by the shared custodian resolver ($ARTICLE_REPOSITORY, no default).
    "articlerepo": str(_custody_path("fulltext")),
}


def pdf_path(corpus: str, *parts: str) -> str:
    """Return path to a test PDF under one of the ``PDF_PATHS`` roots.

    AN UNKNOWN CORPUS NAME RAISES. It used to return "", which made
    `pdf_available` return False and every caller skip -- so deleting a key from
    PDF_PATHS silently converted every call site into a permanent no-op with
    nothing to read. That is not hypothetical: removing the "docpluck" key on
    2026-09-17 left 8 files calling `pdf_available("docpluck", ...)`, and the W0k
    and W0g science guards -- the rules that were destroying real published
    digits and turning `p = .05` into `p = -.05` -- skipped with the message
    "absent from the local corpus" for papers that were in custody the whole time.

    A MISSING FILE still returns its path, so callers can skip on a corpus this
    machine genuinely does not have. A MISSING KEY is a programming error and
    says so.
    """
    if corpus not in PDF_PATHS:
        raise KeyError(
            f"unknown corpus {corpus!r}. Known: {sorted(PDF_PATHS)}. "
            "docpluck's OWN corpus is not here any more -- it resolves through "
            "the article custodian via `docpluck.testing.require_corpus_pdf"
            '("<subdir>/<file>.pdf")`, which fails loudly when a paper is not '
            "held. Returning an empty string here would make this call skip."
        )
    return os.path.join(PDF_PATHS[corpus], *parts)


def pdf_available(corpus: str, *parts: str) -> bool:
    """Check if a test PDF exists."""
    path = pdf_path(corpus, *parts)
    return bool(path) and os.path.isfile(path)


# ---------------------------------------------------------------------------
# A test may not leak a DOCPLUCK_* environment variable into the next test
# ---------------------------------------------------------------------------
#
# Several tests disable Camelot (or enable an experimental path) with
# `os.environ["DOCPLUCK_…"] = "1"` to keep themselves fast. If one forgets to
# restore it, every test that runs AFTERWARDS in the same process silently gets a
# different library.
#
# That is not hypothetical. `test_major_section_heading_promotion._render_cogemo`
# set `DOCPLUCK_DISABLE_CAMELOT=1` and never restored it, so every real-PDF table
# test collected after it found no tables and failed. The symptom — nine table
# tests failing in a full run and passing when run per-file — was recorded in
# CLAUDE.md, in a memory, and in three handoffs as "Camelot tests flake under
# cumulative load (even serial)", with the workaround "run each file separately".
# **It was never load, and the folklore is what stopped anyone looking**: a
# documented flake is a failure nobody re-investigates.
#
# So the class gets a guard rather than another one-line fix. This fails the
# offending test itself, naming the variable — instead of failing an innocent
# test several files later, which is what made it look like nondeterminism.
@pytest.fixture(autouse=True)
def _no_leaked_docpluck_env():
    before = {k: v for k, v in os.environ.items() if k.startswith("DOCPLUCK_")}
    yield
    after = {k: v for k, v in os.environ.items() if k.startswith("DOCPLUCK_")}
    if before != after:
        changed = sorted(set(before) | set(after))
        detail = ", ".join(
            f"{k}: {before.get(k)!r} -> {after.get(k)!r}"
            for k in changed
            if before.get(k) != after.get(k)
        )
        # Restore, so ONE offending test does not cascade into the rest of the run.
        for k in set(after) - set(before):
            os.environ.pop(k, None)
        for k, v in before.items():
            os.environ[k] = v
        raise AssertionError(
            f"this test leaked a DOCPLUCK_* environment variable into the rest of "
            f"the process: {detail}. Set it with `monkeypatch.setenv` or restore it "
            f"in a `finally` — an unrestored flag silently reconfigures every test "
            f"that runs after it (see the comment above this fixture)."
        )


# ---------------------------------------------------------------------------
# ...and a MODULE-level mutation happens before any test runs, so the per-test
# fixture above structurally cannot see it.
# ---------------------------------------------------------------------------
#
# `test_rc1_banded_column_real_pdf.py` had
# `os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")` at module scope. That
# executes during COLLECTION — before the first test's snapshot is taken — and was
# never undone, so merely COLLECTING that file disabled Camelot for the entire
# pytest process. Every real-PDF table test that ran afterwards found no tables.
#
# Together with the unrestored variable in `test_major_section_heading_promotion`,
# that is the whole of the "Camelot tests flake under cumulative load (even
# serial)" folklore, which was recorded in CLAUDE.md, in a memory, and in three
# handoffs with the workaround "run each file separately". It was never load, and
# the folklore is precisely what stopped anyone from looking: a documented flake
# is a failure nobody re-investigates.
#
# This check fails the RUN, loudly, naming the variable — because a module-scope
# environment mutation cannot be attributed to a single test, and there is no
# legitimate reason for one. Use a module-scoped autouse fixture instead.
_ENV_AT_CONFIGURE: dict = {}


def pytest_configure(config):
    _ENV_AT_CONFIGURE.clear()
    _ENV_AT_CONFIGURE.update(
        {k: v for k, v in os.environ.items() if k.startswith("DOCPLUCK_")}
    )


def pytest_collection_finish(session):
    after = {k: v for k, v in os.environ.items() if k.startswith("DOCPLUCK_")}
    if after != _ENV_AT_CONFIGURE:
        changed = sorted(set(_ENV_AT_CONFIGURE) | set(after))
        detail = ", ".join(
            f"{k}: {_ENV_AT_CONFIGURE.get(k)!r} -> {after.get(k)!r}"
            for k in changed
            if _ENV_AT_CONFIGURE.get(k) != after.get(k)
        )
        raise pytest.UsageError(
            f"a test MODULE mutated a DOCPLUCK_* environment variable at import "
            f"time: {detail}. That runs during collection and reconfigures the "
            f"library for every test in the process — it is the cause of the "
            f"historical 'Camelot flakes under cumulative load'. Move it into a "
            f"module-scoped autouse fixture that restores the prior value."
        )


@pytest.fixture(autouse=True, scope="module")
def _camelot_disabled_per_module(request):
    """Honour a module's `DISABLE_CAMELOT = True` flag — and undo it afterwards.

    36 test modules used to write `os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT",
    "1")` at module scope for speed. That executes during COLLECTION and was never
    undone, so importing ANY of them disabled Camelot for the entire process and
    every real-PDF table test collected afterwards found no tables.

    The intent was fine; the mechanism was a process-wide side effect at import
    time. The flag is now declarative and this fixture owns the lifetime, so the
    modules keep their speed and nothing leaks past them.
    """
    if not getattr(request.module, "DISABLE_CAMELOT", False):
        yield
        return
    prior = os.environ.get("DOCPLUCK_DISABLE_CAMELOT")
    os.environ["DOCPLUCK_DISABLE_CAMELOT"] = "1"
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop("DOCPLUCK_DISABLE_CAMELOT", None)
        else:
            os.environ["DOCPLUCK_DISABLE_CAMELOT"] = prior


# ---------------------------------------------------------------------------
# No article repository configured: ONE loud failure, every other paper test skips
# ---------------------------------------------------------------------------
#
# Owner decision 2026-09-27. With $ARTICLE_REPOSITORY unset (any public clone),
# `require_corpus_pdf` raises CorpusPaperMissing in ~100 tests. A hundred red
# lines bury the one fact that matters, so those tests are reported SKIPPED with
# the reason, while `test_corpus_manifest.py::test_the_custodian_is_reachable`
# still FAILS -- so the run never reads as green when nothing was read (the
# 2026-09-17 directive). The conversion happens ONLY when the repository itself
# is unreachable: with it configured, a missing paper still fails.

# What marks a failure as "caused by the unconfigured repository": the exception
# type, the unresolved-path sentinel that `docpluck.testing` builds on purpose
# (it names its own cause), or the resolver's own sentence.
_NO_REPO_SIGNS = ("no-article-repository", "ARTICLE_REPOSITORY is not set")
_SENTINEL_TEST = "test_the_custodian_is_reachable"


def _caused_by_unconfigured_repository(excinfo, text: str) -> bool:
    from docpluck.testing import CorpusPaperMissing, corpus_available

    if corpus_available():
        return False
    if excinfo is not None and excinfo.errisinstance(CorpusPaperMissing):
        return True
    return any(sign in text for sign in _NO_REPO_SIGNS)


def _skip_reason() -> str:
    from docpluck.testing import root_problem

    return f"Skipped: article repository not configured -- {root_problem()}"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if not rep.failed or item.name == _SENTINEL_TEST:
        return
    if _caused_by_unconfigured_repository(call.excinfo, rep.longreprtext):
        rep.outcome = "skipped"
        rep.longrepr = (str(item.path), item.location[1] or 0, _skip_reason())


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    """Same rule for a module that resolves its paper at import time."""
    outcome = yield
    rep = outcome.get_result()
    if rep.failed and _caused_by_unconfigured_repository(None, rep.longreprtext):
        rep.outcome = "skipped"
        rep.longrepr = (str(collector.path), 0, _skip_reason())
