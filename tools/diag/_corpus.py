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
    os.environ.get("ARTICLE_FINDER_HOME")
    or (Path.home() / ".claude" / "skills" / "article-finder")
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
    except Exception as exc:  # pragma: no cover - diagnostic output path
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
