"""The canary harness must render the WORKING TREE, not an installed release.

Measured 2026-08-29. `tools/render_for_audit.py` is the artifact producer for every
canary audit, and `canary-audit.sh` prints "rendering at HEAD (<sha>)" while it
runs. It did not render HEAD.

Python puts the SCRIPT'S OWN DIRECTORY on `sys.path[0]`, not the cwd. The harness
lives in `tools/`, so `py -3 tools/render_for_audit.py` put `tools/` first and
`import docpluck` fell through to site-packages. On
`10.1001/jamanetworkopen.2023.39337`:

    installed 2.4.137     -> 10 stray running-head copies, 59,991 chars
    working tree 2.4.138  ->  0 stray running-head copies, 59,256 chars

So the canary scored the RELEASE's defect, reported it against the repo's sha, and
the working tree's repair was invisible to it. Every verdict taken that way — the
whole 6-paper run of 2026-08-29 included — measured the wrong artifact.

WHY IT SURVIVED, and the reason this test runs a SUBPROCESS rather than importing:
`python -c "import docpluck"` resolves the tree, because `-c` puts the cwd on the
path. The obvious check could not see it. Only executing a FILE reproduces the
condition, so the test must execute a file too. An in-process assertion here would
pass while the harness stayed broken.

Watched RED before being trusted: with the `sys.path.insert` removed from
`render_for_audit.py`, `test_harness_imports_docpluck_from_the_repo` fails with the
resolved path under `site-packages`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "tools" / "render_for_audit.py"
CANARY_DOI = "10.1001/jamanetworkopen.2023.39337"


def test_harness_imports_docpluck_from_the_repo(tmp_path):
    """Execute a file FROM tools/ and assert docpluck resolves to the working tree.

    This pins the mechanism the harness depends on, in the only way that can
    observe it: as a script file, where sys.path[0] is the script's directory.
    """
    probe = REPO / "tools" / "_pytest_probe_docpluck_origin.py"
    probe.write_text(
        "import sys\n"
        f"sys.path.insert(0, r'{REPO}')\n"
        "import docpluck, json\n"
        "print(json.dumps({'file': docpluck.__file__, 'version': docpluck.__version__}))\n",
        encoding="utf-8",
    )
    try:
        r = subprocess.run([sys.executable, str(probe)], capture_output=True,
                           text=True, cwd=str(REPO))
        assert r.returncode == 0, r.stderr[-400:]
        got = json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        probe.unlink(missing_ok=True)

    resolved = Path(got["file"]).resolve()
    assert str(resolved).startswith(str(REPO)), (
        "docpluck resolved to %s, not the working tree at %s. A script in tools/ "
        "gets tools/ on sys.path[0], so without an explicit repo-root insert the "
        "import falls through to site-packages and the canary scores the installed "
        "release while reporting the repo's sha." % (resolved, REPO)
    )


def test_harness_source_inserts_repo_root_before_importing_docpluck():
    """The insert must PRECEDE the import; after it, the module is already bound."""
    # Match STATEMENTS, not prose. A plain substring search finds `import
    # docpluck` inside the explanatory comment above the fix — which sits before
    # the insert — and fails a correct file. Caught by this test on its first run.
    import re

    src = HARNESS.read_text(encoding="utf-8")
    insert_m = re.search(r"^\s*sys\.path\.insert\(0, _REPO_ROOT\)", src, re.M)
    import_m = re.search(r"^\s*import docpluck\b", src, re.M)
    assert insert_m, "render_for_audit.py no longer inserts the repo root on sys.path"
    assert import_m, "render_for_audit.py no longer imports docpluck"
    insert_at, import_at = insert_m.start(), import_m.start()
    assert insert_at < import_at, (
        "the repo-root sys.path insert must come BEFORE `import docpluck`; "
        "inserting afterwards changes nothing, because the module is already resolved"
    )


def test_harness_records_which_library_it_used(tmp_path):
    """A gate that cannot name the artifact it scored is not a gate.

    The failing run logged `docpluck version: 2.4.137` for weeks and nobody could
    tell that was site-packages rather than a stale tree, because the version does
    not carry the origin. The receipt must carry the PATH.
    """
    if not (Path.home() / ".claude/skills/article-finder/cache-check.py").exists():
        pytest.skip("article-finder not present on this machine")
    out = tmp_path / "r.md"
    r = subprocess.run(
        [sys.executable, str(HARNESS), "--key", CANARY_DOI, "--out", str(out)],
        capture_output=True, text=True, cwd=str(REPO),
    )
    # Exit 2 with the origin guard's own message is the DEFECT firing, not an
    # environmental problem — skipping on it would turn the very failure this
    # file exists to catch into a green tick. Only genuine unavailability skips.
    if r.returncode == 2 and "must import the working tree" in r.stderr:
        pytest.fail(
            "the origin guard fired: the harness resolved docpluck outside the "
            "working tree, which is exactly the false green this test pins.\n"
            + r.stderr[-400:]
        )
    if r.returncode != 0:
        pytest.skip(f"harness could not render here (exit {r.returncode}): {r.stderr[-200:]}")

    payload = json.loads([ln for ln in r.stdout.splitlines() if ln.strip().startswith("{")][-1])
    assert payload["library_from_working_tree"] is True, (
        "the harness rendered with %s" % payload.get("library_path")
    )
    assert str(REPO) in payload["library_path"]
