"""Resolve the diagnostic corpus from ARTICLE-FINDER, never from a directory glob.

Every scan under ``tools/diag/`` used to compute its paper set with

    glob(os.path.join(CORPUS_DIR, "**/*.pdf"))   # a sibling project directory

which violates the custody hard rule (article-finder is the sole custodian of
papers) and carries the coverage defect ``scripts/verify_corpus.py`` was rewired
to remove on 2026-08-07: **a denominator computed from the numerator can only
ever report 100%.** A glob that silently returns 40 files instead of 101 prints
"scanning 40 corpus PDFs" and every downstream count is quietly divided by the
wrong N — the scan looks like it ran and its blast-radius numbers are wrong by a
factor nobody can see.

So the set comes from the custodian, and three states are kept DISTINCT:

    nothing resolvable          -> SystemExit with a message naming the cause
    fewer papers than requested -> reported explicitly on the COVERAGE line
    all requested resolved      -> COVERAGE line says so

Every caller must print :func:`coverage_line` so a reader of the scan output can
see WHICH corpus produced the numbers. A blast-radius measurement whose corpus
is unstated is not re-runnable evidence.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# IMPORT docpluck FROM THIS TREE, not from site-packages.
#
# Measured 2026-09-17: without this, `import docpluck` here resolved to
# C:\...\site-packages\docpluck (the last RELEASED version), so every scan under
# tools/diag/ measured the installed release while reporting as though it had
# measured the working tree. That is the whole "a fix in the comparison key is not
# a fix in the shipped string" family, one layer down.
#
# It bit this module immediately: `docpluck_corpus()` below imports
# `docpluck.testing`, which exists only in the working tree until 2.4.144 ships.
# Against site-packages it raised ImportError, so the corpus repoint was dead in
# all nine scans that call it -- present in the source, unreachable in the run.
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

ARTICLE_FINDER = Path(
    os.environ.get("ARTICLE_FINDER_HOME") or "<ARTICLE_FINDER_HOME unset>"
)

# The render-baseline view whose registered papers are docpluck's OWN corpus —
# the same spec `scripts/verify_corpus.py` gates on, so the scans and the gate
# cannot silently disagree about what "the corpus" is.
DOCPLUCK_BASELINE_SPEC = "render-baseline__docpluck"


class CorpusUnavailable(SystemExit):
    """Raised (as SystemExit) when the custodian cannot supply a paper set.

    Deliberately fatal. A scan that continues on an empty corpus reports a
    false CLEAN, which is the failure mode this module exists to prevent.
    """


def _af(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ARTICLE_FINDER / script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,  # callers read the output; a failure surfaces as no data
    )


def _require_article_finder() -> None:
    if not (ARTICLE_FINDER / "ai-gold.py").is_file():
        raise CorpusUnavailable(
            f"FATAL: article-finder is not installed at {ARTICLE_FINDER}. It is the "
            "sole custodian of the corpus, so there is no paper set to scan. Set "
            "ARTICLE_FINDER_HOME if it lives elsewhere. Refusing to report a "
            "result computed from 0 papers."
        )


def baseline_corpus(limit: int | None = None) -> list[tuple[str, Path]]:
    """docpluck's own render-baseline corpus, as ``(canonical_key, pdf_path)``.

    Papers the custodian lists but whose PDF this machine does not hold are
    dropped HERE and counted, so :func:`coverage_line` can report the shortfall
    rather than hiding it in a smaller-looking N.
    """
    _require_article_finder()
    r = _af("ai-gold.py", "papers-with-view", DOCPLUCK_BASELINE_SPEC, "--latest", "--keys-only")
    # `_af` captures stderr, so a custodian warning reaches nobody unless it is
    # relayed. The one that matters says `--latest` resolved to a version
    # covering FEWER papers than an older one — the only signal that this
    # scan's denominator silently shrank.
    for line in r.stderr.splitlines():
        if line.startswith("WARNING:"):
            print(f"# custodian {line}", file=sys.stderr)
    keys = sorted(k for k in (ln.strip() for ln in r.stdout.splitlines()) if k)
    if not keys:
        raise CorpusUnavailable(
            f"FATAL: baseline view {DOCPLUCK_BASELINE_SPEC!r} has no registered "
            f"papers.\nstderr: {r.stderr.strip()}\n"
            "Refusing to report a result computed from 0 papers."
        )
    _expected[0] = len(keys)
    out: list[tuple[str, Path]] = []
    for key in keys[: limit or len(keys)]:
        p = _find_pdf(key)
        if p is not None:
            out.append((key, p))
    _resolved[0] = len(out)
    if not out:
        raise CorpusUnavailable(
            f"FATAL: the custodian lists {len(keys)} baseline papers but this "
            "machine holds none of their PDFs. Refusing to report a result "
            "computed from 0 papers."
        )
    return out


def sampled_corpus(n: int, seed: int = 20260813, **tags: str) -> list[tuple[str, Path]]:
    """A deterministic seeded sample of the shared repository, ``(doi, path)``.

    For measuring how OFTEN a shape occurs in the wild, where docpluck's own
    26-paper baseline corpus is too narrow to say anything. ``corpus-query.py``
    documents ``--sample N --seed S`` as deterministic for a given
    (query, seed, index_hash), so a re-run reproduces the same files unless the
    repository itself changed.
    """
    _require_article_finder()
    args = ["--format", "pdf", "--sample", str(n), "--seed", str(seed)]
    for k, v in tags.items():
        args += [f"--{k.replace('_', '-')}", v]
    r = _af("corpus-query.py", *args)
    try:
        d = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError):
        raise CorpusUnavailable(
            f"FATAL: corpus-query.py returned no parseable JSON.\n"
            f"stderr: {r.stderr.strip()[:500]}"
        ) from None
    files = [f for f in d.get("files", []) if f.get("exists")]
    _expected[0] = d.get("count", len(files))
    _resolved[0] = len(files)
    if not files:
        raise CorpusUnavailable(
            "FATAL: the custodian matched 0 existing PDFs for this query. "
            "Refusing to report a result computed from 0 papers."
        )
    return [(f.get("doi") or Path(f["path"]).stem, Path(f["path"])) for f in files]


def _find_pdf(key: str) -> Path | None:
    """Locate a paper's PDF by canonical key, from the repository cache only.

    ``--dry-run`` keeps this offline. A diagnostic scan must never reach the
    network mid-run, and a paper that is merely *downloadable* is not a paper
    this machine can measure.
    """
    doi = key.replace("__", "/") if key.startswith("10.") else key
    r = _af("find-pdf.py", doi, "--dry-run")
    try:
        d = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    if d.get("found") and d.get("source") == "repository_cache" and d.get("path"):
        p = Path(d["path"])
        return p if p.is_file() else None
    return None


# Module-level so `coverage_line()` reports the LAST resolution without every
# caller having to thread the counts through. Single-threaded scans only.
_expected = [0]
_resolved = [0]


def specimen_line() -> str:
    """Name the docpluck this scan actually imported, BY PATH.

    Added 2026-09-21 after a reconciliation that had to establish, by inference from
    commit dates and symbol presence, which copy of the library produced each
    historical figure -- and could not finish that inference for three of them.

    A scan's output said WHICH CORPUS it measured (``coverage_line``) but never
    WHICH LIBRARY, and until 2026-09-02 fourteen scans under this directory
    imported whatever was INSTALLED rather than this tree. The numbers were
    entirely plausible and described the wrong software.

    The identifier is the PATH, deliberately. ``__version__`` cannot serve: this
    tree has reported ``2.4.144`` while sitting in no tag and no commit, and the
    installed copy is routinely several releases stale, so two copies report
    plausibly and only the path distinguishes them.
    """
    try:
        import docpluck
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - any failure is reported, never raised
        return (
            f"SPECIMEN: UNKNOWN — `import docpluck` failed "
            f"({exc.__class__.__name__}: {exc}). No figure from this run describes "
            f"any library."
        )
    path = Path(docpluck.__file__).resolve()
    repo = Path(_REPO_ROOT).resolve()
    if repo in path.parents:
        where = "this working tree"
    else:
        where = (
            "an INSTALLED copy — figures from this run do NOT describe this checkout"
        )
    reported = getattr(docpluck, "__version__", "<none>")
    return f"SPECIMEN: {path} ({where}); reports __version__={reported}"


def coverage_line() -> str:
    """The two lines every scan must print: WHICH CORPUS, and WHICH LIBRARY.

    The specimen is appended here rather than added at ~40 call sites, so every
    scan that already prints coverage becomes self-identifying with no edit.
    """
    exp, res = _expected[0], _resolved[0]
    if exp == 0:
        corpus = "COVERAGE: unknown — no corpus resolved"
    else:
        state = "COMPLETE" if res == exp else "PARTIAL"
        corpus = (
            f"COVERAGE: {state} — {res}/{exp} papers resolved from article-finder "
            f"(custodian, not a directory listing)"
        )
    return f"{corpus}\n{specimen_line()}"


def docpluck_corpus() -> list[Path]:
    """docpluck's own 101-paper corpus, from the custodian's committed manifest.

    Added 2026-09-17 with the corpus repoint. Every scan under this directory
    used to build its paper set with

        glob(os.path.join(CORPUS_DIR, "**/*.pdf"))   # a sibling project directory

    which is the defect this module's own header describes: a denominator
    computed from the numerator. A glob that quietly returns 40 files instead of
    101 prints "scanning 40 corpus PDFs" and divides every blast-radius number
    below it by the wrong N, with nothing to read that says so.

    The manifest is committed, so it cannot shrink without a diff, and a paper it
    names that is not in custody raises rather than being dropped.
    """
    from docpluck.testing.corpus import CorpusPaperMissing, corpus_pdfs

    try:
        return corpus_pdfs()
    except CorpusPaperMissing as exc:
        raise CorpusUnavailable(
            f"FATAL: the docpluck corpus is not fully in custody -- {exc}. "
            "Refusing to report a result computed from a short corpus."
        ) from exc


# ===========================================================================
# SPECIMEN SELECTION — run a scan against a CHOSEN copy of the library.
#
# `specimen_line()` above is the DETECTION half of the 2026-09-21 fix: every
# scan says which docpluck produced its numbers. This is the SELECTION half.
# Until it existed, "what did release X actually do on the corpus?" meant
# copying a scan's loop into a throwaway harness by hand, and a scan cost
# ~17 min per arm because it ran one paper at a time.
#
# Contract, per ARM (one requested copy of the library):
#   * the request is a directory holding a `docpluck/` package, or a git ref
#     of THIS repository, which is checked out as a temporary worktree OUTSIDE
#     the repository and removed when the run ends;
#   * every process that measures inserts that root at `sys.path[0]` BEFORE
#     anything imports docpluck, then asserts `docpluck.__file__` lies inside
#     it — and REFUSES (SpecimenMismatch) otherwise. It never falls back to the
#     installed copy or to this tree;
#   * the parent re-checks the path every result reports, so an arm cannot
#     silently mix libraries;
#   * worker processes are SPAWNED, never forked: a forked child inherits
#     whatever docpluck the parent already imported (the parent imports this
#     tree to read the corpus manifest), which is the original defect again.
#
# The corpus manifest is always read from THIS tree, whatever the specimen: an
# old release has no `docpluck.testing`, and the paper set must not change
# between arms or the arms are not comparable.
#
# A scan that adopts this must import docpluck ONLY inside its per-paper
# function. A spawned worker re-executes the scan's module top level before the
# worker initializer runs, so a module-level `from docpluck... import` would
# bind this tree first — `bind_specimen` then refuses, loudly, rather than
# measuring the wrong library. Pinned by
# tests/test_harness_scripts_import_the_working_tree.py.
# ===========================================================================

import re as _re
import shutil as _shutil
import tempfile as _tempfile
from contextlib import ExitStack as _ExitStack
from contextlib import contextmanager as _contextmanager


class SpecimenMismatch(SystemExit):
    """The docpluck actually imported is not the one that was requested.

    Deliberately fatal, like :class:`CorpusUnavailable`: a scan that carries on
    measures some OTHER library while its output names the requested one.
    """


def _repo_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", _REPO_ROOT, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )


def _is_within(child: Path, parent: Path) -> bool:
    child, parent = Path(child).resolve(), Path(parent).resolve()
    return child == parent or parent in child.parents


def _specimen_parent_dir() -> Path:
    """Where a ref's temporary worktree goes: NEVER in or beside this repository.

    The project rule (CLAUDE.md, "ONE DIRECTORY"): a stale checkout beside the
    repo is indistinguishable from the real one at a glance. So the default is
    the system temp directory, overridable with ``DOCPLUCK_SPECIMEN_DIR`` — and
    an override that lands inside the repo or next to it is refused.
    """
    base = Path(os.environ.get("DOCPLUCK_SPECIMEN_DIR") or _tempfile.gettempdir()).resolve()
    repo = Path(_REPO_ROOT).resolve()
    if _is_within(base, repo) or base == repo.parent:
        raise SpecimenMismatch(
            f"FATAL: refusing to put a specimen worktree at {base} -- that is inside "
            f"or beside the repository {repo}. Point DOCPLUCK_SPECIMEN_DIR at a "
            "scratch/temp directory."
        )
    base.mkdir(parents=True, exist_ok=True)
    return base


def registered_worktrees() -> set[Path]:
    """Every checkout ``git worktree list`` knows for this repository."""
    r = _repo_git("worktree", "list", "--porcelain")
    return {
        Path(line[len("worktree "):]).resolve()
        for line in r.stdout.splitlines()
        if line.startswith("worktree ")
    }


@_contextmanager
def specimen_root(request: str):
    """Yield ``(root, commit)`` for one requested specimen; clean up afterwards.

    ``request`` is either an existing directory that contains
    ``docpluck/__init__.py`` (``commit`` is its HEAD, or ``None`` outside git)
    or a git ref of this repository (a tag such as ``v2.4.126``, a branch, a
    SHA), which is checked out detached into a fresh temporary worktree and
    removed on exit.

    Anything else raises :class:`SpecimenMismatch`. There is no fallback: a
    mistyped tag must not quietly measure the installed release.
    """
    as_path = Path(request).expanduser()
    if as_path.is_dir():
        root = as_path.resolve()
        if not (root / "docpluck" / "__init__.py").is_file():
            raise SpecimenMismatch(
                f"FATAL: specimen {request!r} is a directory but holds no "
                f"docpluck/__init__.py ({root}). It is not a docpluck checkout; "
                "refusing rather than falling back to another copy."
            )
        r = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False,
        )
        yield root, (r.stdout.strip() or None) if r.returncode == 0 else None
        return

    r = _repo_git("rev-parse", "--verify", "--quiet", f"{request}^{{commit}}")
    sha = r.stdout.strip()
    if r.returncode != 0 or not sha:
        raise SpecimenMismatch(
            f"FATAL: specimen {request!r} is neither a directory nor a git ref of "
            f"{_REPO_ROOT}. Refusing rather than falling back to another copy."
        )
    safe = _re.sub(r"[^A-Za-z0-9._-]+", "_", request)[:40]
    dest = Path(_tempfile.mkdtemp(prefix=f"docpluck-specimen-{safe}-", dir=_specimen_parent_dir()))
    add = _repo_git("worktree", "add", "--detach", str(dest), sha)
    if add.returncode != 0:
        _shutil.rmtree(dest, ignore_errors=True)
        raise SpecimenMismatch(
            f"FATAL: could not check out {request!r} ({sha[:12]}) at {dest}: "
            f"{add.stderr.strip()}"
        )
    try:
        yield dest.resolve(), sha
    finally:
        _repo_git("worktree", "remove", "--force", str(dest))
        _repo_git("worktree", "prune")
        _shutil.rmtree(dest, ignore_errors=True)
        if dest.resolve() in registered_worktrees() or dest.exists():
            print(
                f"# WARNING: specimen worktree {dest} was NOT removed -- remove it "
                f"with `git worktree remove --force {dest}`.",
                file=sys.stderr,
            )


def bind_specimen(root: str | os.PathLike) -> Path:
    """Make THIS process import docpluck from ``root``, and prove it did.

    Returns the resolved ``docpluck/__init__.py``. Raises
    :class:`SpecimenMismatch` when docpluck is already imported from elsewhere
    (it is never purged and re-imported: other modules may hold references to
    the old copy, and a purge yields one process running two libraries), or
    when the import lands outside ``root`` -- e.g. because an import hook such
    as an editable install's finder outranks ``sys.path``.
    """
    root = Path(root).resolve()
    loaded = sys.modules.get("docpluck")
    if loaded is not None:
        got = Path(getattr(loaded, "__file__", None) or "<no __file__>").resolve()
        if not _is_within(got, root):
            raise SpecimenMismatch(
                f"SPECIMEN MISMATCH: requested {root}, but this process had already "
                f"imported docpluck from {got}. Refusing to measure."
            )
        return got
    if str(root) in sys.path:
        sys.path.remove(str(root))
    sys.path.insert(0, str(root))
    import docpluck  # the import IS the operation being checked

    got = Path(getattr(docpluck, "__file__", None) or "<no __file__>").resolve()
    if not _is_within(got, root):
        raise SpecimenMismatch(
            f"SPECIMEN MISMATCH: requested {root}, but `import docpluck` resolved "
            f"{got}. Refusing to measure."
        )
    return got


_WORKER_BINDING: tuple[str, str] | BaseException | None = None


def _worker_init(root: str) -> None:
    # An initializer that RAISES only breaks the pool: the parent sees a bare
    # BrokenProcessPool and the reason is lost in a worker's stderr. So the
    # refusal is kept and re-raised from the first task, where it reaches the
    # parent verbatim.
    global _WORKER_BINDING
    try:
        got = bind_specimen(root)
        import docpluck

        _WORKER_BINDING = (str(got), str(getattr(docpluck, "__version__", "<none>")))
    except BaseException as exc:  # noqa: BLE001 - relayed to the parent, not swallowed
        _WORKER_BINDING = exc


def _worker_call(fn, item):
    if isinstance(_WORKER_BINDING, BaseException):
        raise _WORKER_BINDING
    return _WORKER_BINDING, fn(item)


class Arm:
    """One requested copy of the library, and everything measured with it.

    A plain class, not a dataclass, on purpose: ``@dataclass`` looks its module
    up in ``sys.modules``, and tests load this file with
    ``spec_from_file_location`` without registering it -- which made the
    decorator raise at import and took ``specimen_line()``'s tests down with it.
    """

    def __init__(self, request: str, root: Path, commit: str | None,
                 resolved: Path | None = None, version: str | None = None) -> None:
        self.request = request
        self.root = root
        self.commit = commit
        self.resolved = resolved
        self.version = version
        self.results: list = []

    @property
    def label(self) -> str:
        return "tree" if self.root == Path(_REPO_ROOT).resolve() else self.request

    def specimen_line(self) -> str:
        if self.resolved is None:
            return f"SPECIMEN[{self.label}]: UNKNOWN -- no item was measured"
        where = (
            "this working tree" if _is_within(self.resolved, Path(_REPO_ROOT))
            else "NOT this working tree"
        )
        commit = f"commit {self.commit[:12]}" if self.commit else "not a git checkout"
        return (
            f"SPECIMEN[{self.label}]: {self.resolved} ({where}; {commit}); "
            f"reports __version__={self.version}"
        )


def add_specimen_arguments(parser) -> None:
    """The shared CLI: ``--specimen`` (repeatable, one per arm), ``--workers``, ``--json``."""
    parser.add_argument(
        "--specimen", action="append", metavar="PATH_OR_REF",
        help="a directory holding a docpluck/ package, or a git ref of this repo "
             "(e.g. v2.4.126, checked out as a temporary worktree outside the repo "
             "and removed afterwards). Repeat for several arms, run concurrently. "
             "Default: this working tree.",
    )
    parser.add_argument(
        "--workers", type=int, default=1,
        help="worker processes in total, shared across arms. Default 1 = the "
             "original single-process run.",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="also write one JSON record per arm under "
             "$DOCPLUCK_DIAG_OUT/<scan>/, default <system temp>/docpluck-diag/<scan>/ "
             "(never inside the repo).",
    )


def run_arms(fn, items, requests: list[str] | None = None, workers: int = 1) -> list[Arm]:
    """Map ``fn`` over ``items`` once per requested specimen; results in ``items`` order.

    ``fn`` must be a picklable module-level function that imports docpluck
    INSIDE its body. With no ``requests`` the single arm is this working tree.

    The only in-process path is the original one -- one arm, this tree, one
    worker -- so a default run behaves as the scan always did, plus the
    assertion. Every other combination runs in spawned worker processes; arms
    run concurrently, each with its share of ``workers``.
    """
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor

    requests = list(requests or [_REPO_ROOT])
    items = list(items)
    with _ExitStack() as stack:
        arms = [Arm(req, *stack.enter_context(specimen_root(req))) for req in requests]

        if len(arms) == 1 and workers <= 1 and arms[0].root == Path(_REPO_ROOT).resolve():
            arm = arms[0]
            arm.resolved = bind_specimen(arm.root)
            import docpluck

            arm.version = str(getattr(docpluck, "__version__", "<none>"))
            arm.results = [fn(it) for it in items]
            return arms

        per_arm = max(1, workers // len(arms))
        ctx = multiprocessing.get_context("spawn")
        futures = []
        for arm in arms:
            pool = stack.enter_context(ProcessPoolExecutor(
                max_workers=per_arm, mp_context=ctx,
                initializer=_worker_init, initargs=(str(arm.root),),
            ))
            futures.append([pool.submit(_worker_call, fn, it) for it in items])

        for arm, futs in zip(arms, futures):
            for fut in futs:
                (got, version), result = fut.result()
                got = Path(got)
                if not _is_within(got, arm.root):
                    raise SpecimenMismatch(
                        f"SPECIMEN MISMATCH: arm {arm.label!r} requested {arm.root}, "
                        f"but a worker measured with {got}. Refusing to report."
                    )
                if arm.resolved is None:
                    arm.resolved, arm.version = got, version
                elif got != arm.resolved:
                    raise SpecimenMismatch(
                        f"SPECIMEN MISMATCH: arm {arm.label!r} mixed libraries: "
                        f"{arm.resolved} and {got}. Refusing to report."
                    )
                arm.results.append(result)
        return arms


def artifact_path(scan: str, arm: Arm) -> Path:
    """Where ``--json`` output goes: ``$DOCPLUCK_DIAG_OUT/<scan>/``, else
    ``<system temp>/docpluck-diag/<scan>/``.

    Never inside this repository -- the records carry article text (context
    snippets), which lives only with the custodian or in scratch output outside
    any repo. ``DOCPLUCK_DIAG_OUT`` overrides the directory; an override inside
    the repo is refused. The default is the system temp directory, like the
    harness scratch output -- there is no fixed machine-local root.
    """
    import datetime as _dt
    import tempfile

    override = os.environ.get("DOCPLUCK_DIAG_OUT")
    base = Path(override) if override else Path(tempfile.gettempdir()) / "docpluck-diag"
    base = base.resolve()
    if _is_within(base, Path(_REPO_ROOT)):
        raise CorpusUnavailable(
            f"FATAL: refusing to write diag output inside the repository ({base})."
        )
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = _re.sub(r"[^A-Za-z0-9._-]+", "_", arm.label)[-60:]
    out = base / scan / f"{stamp}__{safe}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    return out
