"""
Test configuration for docpluck library tests.

PDF-dependent tests are skipped gracefully when pdftotext is not installed
or when test PDFs are not available (library tests should run anywhere).
"""

import os
import shutil
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

# Test PDF directories — optional, tests skip if not present
_HERE = os.path.dirname(__file__)
# docpluck's sibling repos under the same parent (e.g. MetaScienceTools/).
# Derived from this file so paths are robust to where the tree is checked out.
_SIBLINGS = os.path.dirname(os.path.dirname(_HERE))  # parent of the docpluck repo
# Portfolio root: env override first, then the canonical ~/Vibe location
# (moved out of ~/Dropbox/Vibe on 2026-08-03 — a hardcoded old root makes
# every articlerepo/sibling-corpus test SKIP silently, which reads as green).
_VIBE = os.environ.get("VIBE_ROOT") or os.path.join(os.path.expanduser("~"), "Vibe")


def _sibling_repo(name: str, *parts: str) -> str:
    """Locate a sibling project's corpus, wherever the portfolio keeps it.

    THE SAME DEFECT AS THE DROPBOX MOVE, ONE DIRECTORY DEEPER. The comment above
    warns that a hardcoded root makes sibling-corpus tests skip silently and "reads
    as green" — and then this file hardcoded ``$VIBE/<name>``, while the portfolio
    had since grouped its projects into ``MetaScienceProjects/`` and
    ``MetaScienceTools/``. Measured 2026-08-27: ``$VIBE/MetaESCI`` and
    ``$VIBE/MetaMisCitations`` do not exist; both live under
    ``$VIBE/MetaScienceProjects/``.

    **AND IT COSTS NOTHING TODAY — say so rather than imply otherwise.** Measured the
    same day by counting `pdf_available(...)` / `pdf_path(...)` call sites per corpus
    across `tests/*.py`: ``escicheck`` **0 files**, ``metaesci`` **0**,
    ``metamiscitations`` **0**. All three are dead configuration, so these stale paths
    were costing zero skips, and repairing them buys zero coverage back. A first draft
    of this docstring claimed a corpus of "198 PDFs" had been invisible to the suite —
    that number came from a RECURSIVE find (they are nested under `jdm/` and
    `pci_rr/`), the non-recursive listing this file actually uses returns 0, and no
    test wanted them either way. It is fixed because a latent wrong path becomes a
    silent skip the moment someone writes the first test against it, not because
    anything is being recovered.

    **The live hole is a different corpus.** ``docpluck`` — used by **6 test files** —
    points at the sibling ``PDFextractor/test-pdfs/``, which exists and holds **0
    PDFs**, almost certainly because article custody moved to article-finder. That is
    a policy question, not a path bug, and it is not silently patched here.

    So the location is SEARCHED rather than asserted. A name genuinely not on this
    machine (ESCIcheck, 2026-08-27) still returns a non-existent path and its tests
    still skip — correct, and now the only reason they would.
    """
    for group in ("", "MetaScienceProjects", "MetaScienceTools"):
        base = os.path.join(_VIBE, group, name) if group else os.path.join(_VIBE, name)
        if os.path.isdir(base):
            return os.path.join(base, *parts)
    # Not found anywhere — return the canonical spelling so the skip reason still
    # names a path a human can go and check.
    return os.path.join(_VIBE, name, *parts)

PDF_PATHS = {
    # docpluck's test corpus = sibling PDFextractor repo's test-pdfs/.
    "docpluck": os.path.join(_SIBLINGS, "PDFextractor", "test-pdfs"),
    # The shared article repository (article-finder cache). Closed-access PDFs
    # named by canonical DOI key (e.g. "10.1525__collabra.90203.pdf"). Tests
    # that key on a specific paper skip gracefully when the repo isn't present.
    "articlerepo": os.path.join(_VIBE, "ArticleRepository", "fulltext"),
    # Other-project corpora — if not under `_SIBLINGS`, dependent tests skip
    # gracefully (pdf_available returns False). Update to repo-relative once
    # the locations of these sibling repos are confirmed.
    "escicheck": _sibling_repo("ESCIcheck", "testpdfs", "Coded already"),
    "metaesci": _sibling_repo("MetaESCI", "data", "pdfs"),
    "metamiscitations": _sibling_repo("MetaMisCitations", "data", "pretest_a", "pdfs"),
}


def pdf_path(corpus: str, *parts: str) -> str:
    """Return path to a test PDF, or empty string if not available."""
    base = PDF_PATHS.get(corpus, "")
    if not base:
        return ""
    return os.path.join(base, *parts)


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
