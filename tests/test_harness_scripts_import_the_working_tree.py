r"""Every script under ``tools/`` and ``scripts/`` must import the docpluck in
this repository -- never an installed copy from site-packages.

WHY THIS IS A TEST AND NOT A CONVENTION.  Python puts the SCRIPT'S OWN
DIRECTORY on ``sys.path[0]``, never the current working directory.  A script in
``tools/diag/`` therefore has no route to the repo root, and ``import docpluck``
silently resolves to whatever is installed.  Measured 2026-09-01 on this tree:

    python tools/<probe>.py        -> C:\Python314\Lib\site-packages\docpluck  2.4.137
    python -c "import docpluck"    -> <repo>\docpluck                             2.4.138
    python <probe-at-repo-root>.py -> <repo>\docpluck                             2.4.138

The third arm is the control: it isolates the cause to the script's DIRECTORY
rather than to "running a script".  16 of 34 importers resolved the installed
release, INCLUDING ``scripts/verify_corpus.py`` -- the 26-paper baseline that
gates every iterate cycle.  A fix could be verified all night against a library
it had not touched, with every log line naming the tree.

This is the shape of W-0011 (``tools/render_for_audit.py``, fixed in 52903fe),
generalised: that fix repaired ONE script, and the same defect sat in fifteen
others.  Per the project's "a check that CAN be a test MUST be a test" rule,
the census that found them is kept here as the gate.

The probe is written into each script's OWN directory on purpose.  A probe run
via ``python -c`` has no ``__file__``, so every correctly guarded script raises
``NameError`` and is scored "indeterminate" -- two earlier versions of this
census reported 0 tree / 23 indeterminate and 0 tree / 11 site-packages, and
BOTH were artifacts of the probe rather than facts about the scripts.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("tools", "scripts")
_IMPORTS_DOCPLUCK = re.compile(r"^\s*(?:import\s+docpluck|from\s+docpluck)")


def _importers() -> list[Path]:
    found: list[Path] = []
    for d in SCAN_DIRS:
        root = REPO_ROOT / d
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.py")):
            text = p.read_text(encoding="utf-8", errors="replace")
            if any(_IMPORTS_DOCPLUCK.match(line) for line in text.splitlines()):
                found.append(p)
    return found


_PROBE_HELPER = Path(__file__).with_name("_dp_import_probe.py")


def _resolve_docpluck_for(script: Path) -> str:
    """Run ``script`` for real and report which ``docpluck`` its import resolves.

    ``_dp_import_probe.py`` executes the script via ``runpy`` with
    ``sys.path[0]`` set to the script's own directory -- exactly what the
    interpreter does for ``python <script>`` -- and an import hook halts it the
    instant ``docpluck`` is requested.

    Earlier versions replayed only the script's PROLOGUE and were wrong three
    separate ways, each making a correctly-guarded script look defective: via
    ``python -c`` there is no ``__file__``, so every guard of the form
    ``Path(__file__).parents[N]`` raised ``NameError``; a multi-line
    ``from docpluck.x import (`` left an unclosed parenthesis; and a
    module-level ``parse_args()`` aborted the probe on missing CLI arguments.
    """
    proc = subprocess.run(
        [sys.executable, str(_PROBE_HELPER), str(script), str(script.parent)],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=180,
    )
    hits = [l for l in (proc.stdout or "").splitlines() if l.startswith("RESOLVED::")]
    if not hits:
        tail = (proc.stderr or "").strip().splitlines()[-1:] or ["<no output>"]
        pytest.fail(
            f"{script.relative_to(REPO_ROOT).as_posix()}: probe produced no "
            f"resolution -- the MEASUREMENT failed, which is NOT evidence the "
            f"script is clean. Last stderr line: {tail[0]}"
        )
    return hits[-1][len("RESOLVED::"):]


@pytest.mark.parametrize(
    "script", _importers(), ids=lambda p: p.relative_to(REPO_ROOT).as_posix()
)
def test_script_imports_docpluck_from_this_repo(script: Path) -> None:
    resolved = Path(_resolve_docpluck_for(script)).resolve()
    assert resolved.is_relative_to(REPO_ROOT), (
        f"{script.relative_to(REPO_ROOT).as_posix()} imports docpluck from\n"
        f"    {resolved}\n"
        f"instead of the working tree at\n"
        f"    {REPO_ROOT / 'docpluck'}\n"
        f"Any measurement this script produces describes the INSTALLED release, "
        f"not this repository. Add the repo-root guard (see "
        f"tools/render_for_audit.py) above the docpluck import."
    )


def test_the_census_actually_found_scripts_to_check() -> None:
    """A zero-length parametrisation would make the gate above vacuously green."""
    assert len(_importers()) >= 20, (
        f"only {len(_importers())} docpluck importers found under {SCAN_DIRS}; "
        f"the scan is broken, not the tree clean"
    )
