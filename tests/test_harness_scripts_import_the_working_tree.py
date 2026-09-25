r"""Every script under ``tools/`` and ``scripts/`` must import the docpluck in
this repository -- never an installed copy from site-packages.

WHY THIS IS A TEST AND NOT A CONVENTION.  Python puts the SCRIPT'S OWN
DIRECTORY on ``sys.path[0]``.  A script in
``tools/diag/`` therefore has no route to the repo root, and ``import docpluck``
silently resolves to whatever is installed.  Measured 2026-09-01 on this tree:

    python tools/<probe>.py        -> C:\Python314\Lib\site-packages\docpluck  2.4.137
    python -c "import docpluck"    -> <repo>\docpluck                             2.4.138
    python <probe-at-repo-root>.py -> <repo>\docpluck                             2.4.138

The third arm is the control: it isolates the cause to the script's DIRECTORY
rather than to "running a script".

NOTE THE SECOND ARM, because this docstring used to say "never the current
working directory" one paragraph above its own table showing the opposite.
``python -c`` and ``python -m`` BOTH put the CWD on ``sys.path[0]``; only a
SCRIPT FILE puts its own directory there.  Re-measured 2026-09-22 from the repo
root, four-sided::

    python -c "import docpluck"           sys.path[0] = ''            -> working tree
    python -m docpluck --version          (cwd)                       -> working tree
    python <script-outside-the-repo>.py   sys.path[0] = that dir      -> site-packages
    python tools/diag/<script>.py         sys.path[0] = tools/diag    -> site-packages

The load-bearing row is the last one, and it is the whole of the finding: a
scan under ``tools/diag/`` is not at the repo root, so it gets site-packages.
The over-reaching form matters because it mispredicts ``python -m pytest``
(which DOES get the tree) and any probe placed inside the repo.

16 of 34 importers resolved the installed
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

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.cpu_budget import run_with_cpu_budget

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
    # The custodian is pointed at a directory that does not exist. Two scripts
    # (`tools/diag/repair_gate_guard_diff.py`, `scripts/verify_corpus_full.py`)
    # resolve the corpus BEFORE importing docpluck -- one article-finder
    # subprocess per paper -- and on a loaded machine that alone outran the
    # 180 s timeout (measured 2026-09-25, CPU at 100%: both failed twice, as
    # TimeoutExpired, while every guarded script passed). The corpus is not
    # what this probe measures; `_corpus` now raises CorpusUnavailable at once
    # and the probe's fallback reads the sys.path the script left behind.
    env = {**os.environ, "ARTICLE_FINDER_HOME": str(REPO_ROOT / ".no-custodian-in-import-probe")}
    # A CPU budget, not a wall timeout: in a saturated full run on 2026-09-25
    # these probes timed out at 180s wall yet pass alone; measured at 100% load
    # the slowest took 54s wall on 0.5s CPU. See tests/cpu_budget.py.
    proc = run_with_cpu_budget(
        [sys.executable, str(_PROBE_HELPER), str(script), str(script.parent)],
        cpu_budget_s=180, fallback_wall_s=180, cwd=str(REPO_ROOT), encoding=None, env=env,
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


# --------------------------------------------------------------------------
# The gate above is only as good as its DENOMINATOR, and that denominator is
# computed by a line-anchored REGEX.  A regex cannot see an import it does not
# recognise, and a census that silently returns fewer scripts makes this whole
# file vacuously green -- the exact "a green gate can be blind BY CONSTRUCTION"
# shape the project's rules name.  So the census is cross-checked against an
# independent AST walk, and the two must agree exactly.
#
# Measured 2026-09-21 on bca86d3: AST 43, regex 43, symmetric difference empty,
# and no importlib/__import__ route to docpluck exists under tools/ or scripts/.
# --------------------------------------------------------------------------

import ast


def _importers_by_ast() -> set[str]:
    found: set[str] = set()
    for d in SCAN_DIRS:
        root = REPO_ROOT / d
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            try:
                tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for n in ast.walk(tree):
                if (
                    isinstance(n, ast.ImportFrom)
                    and (n.module or "").split(".")[0] == "docpluck"
                ) or (
                    isinstance(n, ast.Import)
                    and any(a.name.split(".")[0] == "docpluck" for a in n.names)
                ):
                    found.add(p.relative_to(REPO_ROOT).as_posix())
    return found


def test_regex_census_and_ast_census_agree() -> None:
    rx = {p.relative_to(REPO_ROOT).as_posix() for p in _importers()}
    by_ast = _importers_by_ast()
    assert rx == by_ast, (
        "the importer census disagrees with an independent AST walk, so the gate's "
        "denominator is wrong and every parametrised case above may be vacuous.\n"
        f"  seen only by AST  : {sorted(by_ast - rx)}\n"
        f"  seen only by regex: {sorted(rx - by_ast)}\n"
        "An `import docpluck` the regex cannot match (aliased, dynamic, or not "
        "line-anchored) silently shrinks what this file checks."
    )


def test_no_dynamic_import_route_to_docpluck() -> None:
    """`importlib.import_module("docpluck")` would evade BOTH censuses above."""
    offenders = []
    for d in SCAN_DIRS:
        root = REPO_ROOT / d
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            for kw in ("importlib.import_module", "__import__"):
                if kw in text and "docpluck" in text:
                    offenders.append(f"{p.relative_to(REPO_ROOT).as_posix()} ({kw})")
    assert not offenders, (
        "a dynamic import of docpluck evades both the regex and the AST census, so "
        f"the gate cannot see which copy it resolves: {offenders}"
    )


# --------------------------------------------------------------------------
# `_corpus.specimen_line()` is the durable half of the 2026-09-21 fix: it makes
# every scan's OUTPUT say which copy of the library produced its numbers.  A
# reporter that cannot tell the two apart is worse than none, so it is tested in
# BOTH directions -- it must name the tree when the tree is imported, and it
# must say INSTALLED when it is not.
# --------------------------------------------------------------------------


def _load_corpus_helper():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_diag_corpus_under_test", REPO_ROOT / "tools" / "diag" / "_corpus.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_specimen_line_names_the_working_tree() -> None:
    line = _load_corpus_helper().specimen_line()
    assert line.startswith("SPECIMEN: ")
    assert "this working tree" in line, line
    assert str(REPO_ROOT) in line, line


def test_specimen_line_flags_an_installed_copy(monkeypatch, tmp_path) -> None:
    """The NEGATIVE control.  Without it, a reporter hard-wired to say 'tree'
    would pass the test above and re-hide the defect it exists to surface."""
    mod = _load_corpus_helper()
    fake_pkg = tmp_path / "site-packages" / "docpluck"
    fake_pkg.mkdir(parents=True)
    (fake_pkg / "__init__.py").write_text("", encoding="utf-8")

    import types

    stub = types.ModuleType("docpluck")
    stub.__file__ = str(fake_pkg / "__init__.py")
    stub.__version__ = "0.0.0-not-this-tree"
    monkeypatch.setitem(sys.modules, "docpluck", stub)

    line = mod.specimen_line()
    assert "INSTALLED copy" in line, line
    assert "do NOT describe this checkout" in line, line
    assert "this working tree" not in line, line


# --------------------------------------------------------------------------
# SPECIMEN SELECTION (`_corpus.run_arms` / `bind_specimen` / `specimen_root`).
#
# The tests above prove a scan imports THIS tree by default. These prove the
# opposite direction is possible and honest: a scan can be pointed at a CHOSEN
# copy, lands in it, says so, and refuses -- never falls back -- when the import
# goes anywhere else. Every positive has a negative beside it, because a binder
# hard-wired to "succeed" would pass the positives alone.
#
# Specimens here are STUBS (a `docpluck/__init__.py` carrying only a version
# string) plus one real checkout of HEAD. The per-item function is
# `os.path.basename`: the property under test is WHICH library a worker bound,
# not what a scan measures with it.
# --------------------------------------------------------------------------

import textwrap

DIAG_DIR = REPO_ROOT / "tools" / "diag"


@pytest.fixture
def corpus_mod(monkeypatch):
    """`tools/diag/_corpus.py` under its REAL module name.

    Spawned workers unpickle `_corpus._worker_call` by name, so the module must
    be importable as `_corpus` in the child -- which inherits this sys.path.
    """
    monkeypatch.syspath_prepend(str(DIAG_DIR))
    import _corpus

    return _corpus


def _stub_specimen(root: Path, version: str) -> Path:
    pkg = root / "docpluck"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    return root


def _head_sha() -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def test_run_arms_binds_each_arm_to_its_own_specimen(corpus_mod, tmp_path) -> None:
    """Two arms in parallel: a stub and this tree. Each must land in its own.

    Two-sided within one run: the same machinery, the same worker count, and
    the two arms must DISAGREE about where docpluck lives -- a binder that
    ignored the request would put both in the same place.
    """
    stub = _stub_specimen(tmp_path / "stub", "0.0.0-stub-A")
    arms = corpus_mod.run_arms(
        os.path.basename, ["a.pdf", "b.pdf", "c.pdf"], [str(stub), str(REPO_ROOT)], workers=2,
    )
    by_label = {a.label: a for a in arms}
    stub_arm, tree_arm = by_label[str(stub)], by_label["tree"]

    assert stub_arm.resolved.is_relative_to(stub.resolve()), stub_arm.specimen_line()
    assert not stub_arm.resolved.is_relative_to(REPO_ROOT), stub_arm.specimen_line()
    assert stub_arm.version == "0.0.0-stub-A"
    assert "NOT this working tree" in stub_arm.specimen_line()

    assert tree_arm.resolved.is_relative_to(REPO_ROOT), tree_arm.specimen_line()
    assert "this working tree" in tree_arm.specimen_line()

    # Results come back in item order, whatever order the workers finished in.
    assert stub_arm.results == tree_arm.results == ["a.pdf", "b.pdf", "c.pdf"]


def test_bind_specimen_refuses_when_another_copy_is_already_loaded(corpus_mod, tmp_path) -> None:
    """A process that already imported docpluck cannot be re-pointed.

    This is exactly what a FORKED worker would be (it inherits the parent's
    import of this tree), which is why workers are spawned. Negative: a stub
    is refused. Positive: re-requesting the copy already loaded is accepted.
    """
    import docpluck  # this tree, per the census above

    assert Path(docpluck.__file__).resolve().is_relative_to(REPO_ROOT)
    stub = _stub_specimen(tmp_path / "stub", "0.0.0-stub")
    path_before = list(sys.path)
    with pytest.raises(corpus_mod.SpecimenMismatch, match="already imported"):
        corpus_mod.bind_specimen(stub)
    assert sys.path == path_before, "a refused bind must not edit sys.path"
    assert corpus_mod.bind_specimen(REPO_ROOT).is_relative_to(REPO_ROOT)


_HOOK_PROBE = textwrap.dedent(
    """
    import importlib.abc, importlib.util, sys
    diag, requested, decoy, hijack = sys.argv[1:5]
    sys.path.insert(0, diag)
    import _corpus

    class Hijack(importlib.abc.MetaPathFinder):
        # Stands in for an editable install's finder: it answers `docpluck`
        # before sys.path is ever consulted.
        def find_spec(self, name, path=None, target=None):
            if name != "docpluck":
                return None
            return importlib.util.spec_from_file_location(
                "docpluck", decoy + "/docpluck/__init__.py",
                submodule_search_locations=[decoy + "/docpluck"])

    if hijack == "1":
        sys.meta_path.insert(0, Hijack())
    print("BOUND::" + str(_corpus.bind_specimen(requested)))
    """
)


@pytest.mark.parametrize("hijack", [False, True], ids=["plain", "import-hook-outranks-path"])
def test_bind_specimen_refuses_an_import_that_lands_elsewhere(tmp_path, hijack) -> None:
    """The assertion after the import is what makes selection trustworthy.

    With an import hook that outranks ``sys.path`` (an editable install's
    finder is the real-world case), inserting the specimen at ``sys.path[0]``
    is not enough -- docpluck resolves to the decoy. The binder must notice and
    raise. Control arm: same process shape, no hook, binds the request.
    """
    requested = _stub_specimen(tmp_path / "requested", "0.0.0-requested")
    decoy = _stub_specimen(tmp_path / "decoy", "0.0.0-decoy")
    proc = subprocess.run(
        [sys.executable, "-c", _HOOK_PROBE, str(DIAG_DIR), str(requested), str(decoy),
         "1" if hijack else "0"],
        capture_output=True, text=True, cwd=str(tmp_path), timeout=120, check=False,
    )
    if hijack:
        assert proc.returncode != 0, proc.stdout
        assert "SPECIMEN MISMATCH" in proc.stderr, proc.stderr
        assert str(decoy.resolve()) in proc.stderr, proc.stderr
        assert "BOUND::" not in proc.stdout
    else:
        assert proc.returncode == 0, proc.stderr
        bound = Path(proc.stdout.strip().split("BOUND::")[-1])
        assert bound.is_relative_to(requested.resolve()), proc.stdout


def test_a_worker_refusal_reaches_the_parent_verbatim(corpus_mod, tmp_path) -> None:
    """A refused bind inside a WORKER must stop the run with its reason intact.

    A pool initializer that raises yields only a bare BrokenProcessPool, with
    the reason lost in a worker's stderr. Provoked for real: the requested
    package passes `specimen_root`'s check, but on import it replaces itself in
    `sys.modules` with a copy from elsewhere (a real pattern -- shim packages do
    it), so only the WORKER can see where docpluck actually came from.
    """
    decoy = _stub_specimen(tmp_path / "decoy", "0.0.0-decoy")
    requested = tmp_path / "requested"
    (requested / "docpluck").mkdir(parents=True)
    (requested / "docpluck" / "__init__.py").write_text(
        textwrap.dedent(
            f"""
            import importlib.util, sys
            _spec = importlib.util.spec_from_file_location(
                "docpluck", {str(decoy / "docpluck" / "__init__.py")!r})
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            sys.modules["docpluck"] = _mod
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(corpus_mod.SpecimenMismatch) as exc:
        corpus_mod.run_arms(os.path.basename, ["a.pdf", "b.pdf"], [str(requested)], workers=2)
    msg = str(exc.value)
    assert "SPECIMEN MISMATCH" in msg and str(decoy.resolve()) in msg, msg


def test_specimen_root_rejects_what_is_not_a_docpluck_checkout(corpus_mod, tmp_path) -> None:
    """No fallback: a wrong request is an error, never 'the installed copy'."""
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(corpus_mod.SpecimenMismatch, match="holds no docpluck"), corpus_mod.specimen_root(str(empty)):
        pass
    with pytest.raises(corpus_mod.SpecimenMismatch, match="neither a directory nor a git ref"), corpus_mod.specimen_root("v0.0.0-no-such-tag-anywhere"):
        pass
    # Positive control: a real checkout is accepted and reports its commit.
    with corpus_mod.specimen_root(str(REPO_ROOT)) as (root, sha):
        assert root == REPO_ROOT.resolve()
        assert sha == _head_sha()


def test_a_ref_is_checked_out_outside_the_repo_and_removed(corpus_mod, tmp_path, monkeypatch) -> None:
    """A tag becomes a temporary worktree -- never beside the repo, never left behind.

    The project's ONE DIRECTORY rule: stale checkouts beside the repository
    were indistinguishable from the real one. Negative: pointing the worktree
    parent at the repo's own parent directory is refused before git runs.
    """
    # Compared by LOCATION, never as a before/after set: other sessions on this
    # machine add and remove their own worktrees of this repo while the test
    # runs, and a whole-set comparison failed on exactly that.
    def near_repo() -> set[Path]:
        return {w for w in corpus_mod.registered_worktrees() if w.parent == REPO_ROOT.parent}

    before = near_repo()
    monkeypatch.setenv("DOCPLUCK_SPECIMEN_DIR", str(REPO_ROOT.parent))
    with pytest.raises(corpus_mod.SpecimenMismatch, match="inside or beside"), corpus_mod.specimen_root("HEAD"):
        pass
    assert near_repo() == before

    monkeypatch.setenv("DOCPLUCK_SPECIMEN_DIR", str(tmp_path))
    with corpus_mod.specimen_root("HEAD") as (root, sha):
        assert root.is_relative_to(tmp_path.resolve())
        assert not root.is_relative_to(REPO_ROOT)
        assert (root / "docpluck" / "__init__.py").is_file()
        assert sha == _head_sha()
        assert root in corpus_mod.registered_worktrees()
    assert root not in corpus_mod.registered_worktrees()
    assert not root.exists()


def test_run_arms_on_a_ref_measures_that_checkout(corpus_mod, tmp_path, monkeypatch) -> None:
    """End to end through a real git checkout: the worker imports the WORKTREE's
    docpluck -- same code as this tree, different path -- and the worktree is
    gone afterwards. A binder that quietly reused this tree would report a path
    inside REPO_ROOT here."""
    monkeypatch.setenv("DOCPLUCK_SPECIMEN_DIR", str(tmp_path))
    (arm,) = corpus_mod.run_arms(os.path.basename, ["x.pdf"], ["HEAD"], workers=1)
    assert arm.resolved.is_relative_to(tmp_path.resolve()), arm.specimen_line()
    assert not arm.resolved.is_relative_to(REPO_ROOT), arm.specimen_line()
    assert arm.commit == _head_sha()
    assert arm.results == ["x.pdf"]
    assert arm.root not in corpus_mod.registered_worktrees()
    assert not arm.root.exists()


def _module_level_docpluck_imports(path: Path) -> list[int]:
    """Line numbers of docpluck imports that execute at module import time."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    hits: list[int] = []

    def walk(stmts) -> None:
        for s in stmts:
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if (
                isinstance(s, ast.ImportFrom) and (s.module or "").split(".")[0] == "docpluck"
            ) or (
                isinstance(s, ast.Import) and any(a.name.split(".")[0] == "docpluck" for a in s.names)
            ):
                hits.append(s.lineno)
            for child in ("body", "orelse", "finalbody", "handlers"):
                walk(getattr(s, child, []) or [])

    walk(tree.body)
    return hits


def _specimen_selecting_scans() -> list[Path]:
    return sorted(
        p for p in DIAG_DIR.glob("*.py")
        if p.name != "_corpus.py" and "run_arms" in p.read_text(encoding="utf-8", errors="replace")
    )


def test_specimen_selecting_scans_import_docpluck_only_inside_functions() -> None:
    """A spawned worker re-runs the scan's top level BEFORE binding its specimen.

    So a module-level `from docpluck... import` binds this tree first, and the
    run is refused (see the test above) -- or, worse, a future refactor that
    purges modules would measure a mix. Caught here, statically, instead.
    """
    scans = _specimen_selecting_scans()
    assert scans, "no scan adopts run_arms -- this check would be vacuously green"
    offenders = {
        p.relative_to(REPO_ROOT).as_posix(): lines
        for p in scans if (lines := _module_level_docpluck_imports(p))
    }
    assert not offenders, (
        f"module-level docpluck imports in specimen-selecting scans: {offenders}. "
        "Move them inside the per-paper function."
    )


def test_the_module_level_import_detector_can_see_one(tmp_path) -> None:
    """Negative control for the detector above: it must flag a real offender."""
    bad = tmp_path / "bad.py"
    bad.write_text(
        "import os\ntry:\n    from docpluck.extract import extract_pdf\nexcept ImportError:\n"
        "    pass\ndef f():\n    import docpluck\n",
        encoding="utf-8",
    )
    assert _module_level_docpluck_imports(bad) == [3]


def test_artifact_path_never_writes_inside_the_repository(corpus_mod, tmp_path, monkeypatch) -> None:
    arm = corpus_mod.Arm("v2.4.126", tmp_path / "wt", "0" * 40, tmp_path / "wt" / "docpluck" / "__init__.py")
    monkeypatch.setenv("DOCPLUCK_DIAG_OUT", str(REPO_ROOT / "diag-out"))
    with pytest.raises(corpus_mod.CorpusUnavailable, match="inside the repository"):
        corpus_mod.artifact_path("some_scan", arm)
    assert not (REPO_ROOT / "diag-out").exists()

    monkeypatch.setenv("DOCPLUCK_DIAG_OUT", str(tmp_path / "out"))
    out = corpus_mod.artifact_path("some_scan", arm)
    assert out.parent == (tmp_path / "out" / "some_scan").resolve()
    assert out.name.endswith("__v2.4.126.json")
