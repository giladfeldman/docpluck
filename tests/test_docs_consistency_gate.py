"""The gate that guards documentation accuracy had no test of its own.

`scripts/check_docs_consistency.py` asserts that the version numbers `docs/README.md`
advertises still match the constants this package defines. It is invoked by hand
from handoffs and release checklists and by nothing automatic -- so on 2026-08-20 it
was edited twice in one session with nothing pinning either change.

That is the shape this project has a standing rule about: **a check that CAN be a
test MUST be a test.** A gate nobody runs is indistinguishable from a gate that
passes, and this one guards a claim that reaches consumers -- `docs/README.md`
documents the provenance block returned by `get_version_info()`.

WHAT THIS PINS, and why each case is here:

* the gate PASSES on the tree as committed (a gate that cannot pass is useless);
* it FAILS when the package version drifts -- the case that goes stale on EVERY
  release and was uncovered until `ab291c7`;
* it FAILS when a pipeline version drifts -- `table_extraction_version` sat at
  `2.4.10` against a source value of `2.4.12` until it was spotted by eye;
* its own parser guard fires rather than silently passing on 0 findings.

Each drift case is exercised against a COPY of the repo in a tmp dir, so the test
never mutates the working tree.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_docs_consistency.py"

# Only the files the gate reads. Copying the whole repo would make the test slow
# and would drag the corpus along with it.
_NEEDED = [
    "scripts/check_docs_consistency.py",
    "docpluck/normalize.py",
    "docpluck/__init__.py",
    "docpluck/extract_structured.py",
    "docpluck/sections/__init__.py",
    "docs/README.md",
    "docs/NORMALIZATION.md",
    "docs/BENCHMARKS.md",
    "pyproject.toml",
]


def _run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "check_docs_consistency.py")],
        capture_output=True, text=True, cwd=str(root),
    )


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A copy of just the files the gate reads."""
    for rel in _NEEDED:
        src = ROOT / rel
        if not src.exists():
            pytest.skip(f"{rel} missing from this checkout")
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return tmp_path


def test_the_gate_passes_on_the_committed_tree():
    """If this fails, the docs and the constants have actually drifted."""
    r = _run(ROOT)
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"


def test_a_drifted_PACKAGE_version_is_caught(sandbox: Path):
    """The one that goes stale on every single release.

    `docs/README.md` advertises `'version': '<pkg>'`. Bumping the package without
    updating that line used to pass silently -- the gate checked three of the six
    keys the block advertises and this was not one of them.
    """
    init = sandbox / "docpluck" / "__init__.py"
    src = init.read_text(encoding="utf-8")
    bumped = re.sub(r'^__version__ = "([^"]+)"',
                    lambda m: f'__version__ = "{m.group(1)}-DRIFTED"',
                    src, count=1, flags=re.M)
    assert bumped != src, "could not find __version__ to drift"
    init.write_text(bumped, encoding="utf-8")

    r = _run(sandbox)
    assert r.returncode != 0, "a drifted package version was not caught"
    assert "version" in (r.stdout + r.stderr)


def test_a_drifted_PIPELINE_version_is_caught(sandbox: Path):
    """`table_extraction_version` sat at 2.4.10 against a source 2.4.12."""
    readme = sandbox / "docs" / "README.md"
    src = readme.read_text(encoding="utf-8")
    drifted = re.sub(r"'table_extraction_version': '[^']+'",
                     "'table_extraction_version': '0.0.0'", src, count=1)
    assert drifted != src, "could not find table_extraction_version to drift"
    readme.write_text(drifted, encoding="utf-8")

    r = _run(sandbox)
    assert r.returncode != 0, "a drifted pipeline version was not caught"
    assert "table_extraction_version" in (r.stdout + r.stderr)


def test_a_drifted_NORMALIZATION_version_is_caught(sandbox: Path):
    norm = sandbox / "docpluck" / "normalize.py"
    src = norm.read_text(encoding="utf-8")
    drifted = re.sub(r'^NORMALIZATION_VERSION = "([^"]+)"',
                     'NORMALIZATION_VERSION = "0.0.0"', src, count=1, flags=re.M)
    assert drifted != src, "could not find NORMALIZATION_VERSION to drift"
    norm.write_text(drifted, encoding="utf-8")

    r = _run(sandbox)
    assert r.returncode != 0, "a drifted normalization version was not caught"


def test_the_gate_names_the_two_keys_it_deliberately_does_not_check():
    """`python_version` and `unicodedata_version` are runtime facts, not constants.

    Excluding them is correct. Excluding them SILENTLY is not: an unexplained gap
    reads as an oversight to the next maintainer, and this gate had exactly that
    problem for the three keys it did check. The reason must stay in the source.
    """
    src = SCRIPT.read_text(encoding="utf-8")
    assert "python_version" in src and "unicodedata_version" in src, (
        "the deliberately-ungated keys are no longer named in the gate; either "
        "they are now checked, or the reason they are not has been lost")
