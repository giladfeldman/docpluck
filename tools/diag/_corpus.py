"""Resolve the diagnostic corpus from ARTICLE-FINDER, never from a directory glob.

Every scan under ``tools/diag/`` used to compute its paper set with

    glob(os.path.join(VIBE_ROOT, "MetaScienceTools/PDFextractor/test-pdfs", "**/*.pdf"))

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


def coverage_line() -> str:
    """The line every scan must print. Names the corpus AND the shortfall."""
    exp, res = _expected[0], _resolved[0]
    if exp == 0:
        return "COVERAGE: unknown — no corpus resolved"
    state = "COMPLETE" if res == exp else "PARTIAL"
    return (
        f"COVERAGE: {state} — {res}/{exp} papers resolved from article-finder "
        f"(custodian, not a directory listing)"
    )
