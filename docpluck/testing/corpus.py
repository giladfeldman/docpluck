r"""Resolve the test corpus from the article custodian, by DOI -- never from a directory.

WHY THIS MODULE EXISTS
----------------------
Until 2026-09-17 the suite read its papers out of a sibling project directory of
101 PDFs. That directory was a custody violation: published article PDFs may
live in exactly one place, the shared article repository, and "it was
gitignored" is not containment. Every one of those 101 papers was already held
there by content hash, so the directory bought nothing and cost a rule.

It also hid a defect that no gate could see. When a paper was absent the tests
did not fail -- they SKIPPED. ``pdf.is_file()`` returned False, ``pytest.skip``
fired, and the run stayed green. Deleting the directory outright would therefore
have switched off the corpus-backed coverage of 73 test files without turning
anything red. An instrument that reports a clean result because it never looked
is the failure mode this project has written down more times than any other.

WHAT REPLACES IT
----------------
``MANIFEST`` (in ``corpus_manifest.py``, generated -- see ``regenerate.py``) maps
each corpus-relative name to the DOI that identifies the paper, the custodian's
path for it, and the sha256 of the bytes. Resolution is therefore by DOI, and
the paper set is a COMMITTED LIST rather than whatever a glob happens to return.

That distinction is the point. A glob computes its denominator from its own
numerator: it reports ``40/40`` on a corpus that has silently shrunk from 101,
and every blast-radius number downstream is quietly divided by the wrong N. A
committed manifest cannot shrink without a diff.

THE THREE OUTCOMES, KEPT APART ON PURPOSE
-----------------------------------------
1. **The repository is not on this machine at all.** The library is public and
   anyone may clone it; they will not have the custodian. Per-paper tests skip,
   and ``test_corpus_manifest.py`` says loudly, once, that the ROOT is gone --
   so the run never reads as "the corpus is merely incomplete".
2. **The repository is present but a named paper does not resolve.** This FAILS.
   It is the hole that was open before: a name matching nothing used to be
   indistinguishable from a paper deliberately not held.
3. **Everything resolves.** The integrity test additionally re-hashes all of it,
   because a DOI pointing at the WRONG paper is not hypothetical here -- the
   repository has held a wrong PDF under a correct DOI before, and existence
   checks are blind to it.

``corpus_pdf`` NEVER RAISES, AND THAT IS DELIBERATE
---------------------------------------------------
Most call sites bind their paper at module scope. Raising there would be a
pytest COLLECTION error, which pytest reports as an interrupted run -- this repo
lost a fortnight of red CI to exactly that in 2026-08 and nobody read it. So
``corpus_pdf`` always hands back a path, and the loudness lives in the one gate
that enumerates every name the suite asks for. Use ``require_corpus_pdf`` inside
a test body when you want the raise at the point of use.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from docpluck.testing.corpus_manifest import MANIFEST

__all__ = [
    "CorpusPaperMissing",
    "MANIFEST",
    "corpus_available",
    "corpus_names",
    "corpus_pdf",
    "corpus_pdfs",
    "repository_root",
    "require_corpus_pdf",
    "verify_manifest",
]


class CorpusPaperMissing(AssertionError):
    """A named paper did not resolve in custody.

    Deliberately an ``AssertionError``: pytest renders it as a FAILURE rather
    than an error, which is what a paper the suite claims to test and cannot
    read actually is.
    """


# The custodian's root. Resolved, never hardcoded -- the portfolio root has moved
# once already and a helper that silently returns nothing when it moves makes a
# broken run look like a clean one.
_ENV_REPO = "ARTICLE_REPOSITORY"
_ENV_VIBE = "VIBE_ROOT"


def repository_root() -> Path | None:
    """The article repository root, or None when it is not on this machine."""
    explicit = os.environ.get(_ENV_REPO)
    if explicit:
        p = Path(explicit)
        return p if p.is_dir() else None
    base = Path(os.environ.get(_ENV_VIBE) or (Path.home() / "Vibe"))
    p = base / "ArticleRepository"
    return p if p.is_dir() else None


def corpus_available() -> bool:
    """True when the custodian is present, so a miss below is a real miss."""
    return repository_root() is not None


def corpus_names(subdir: str | None = None) -> list[str]:
    """Corpus-relative names in the manifest, e.g. ``apa/efendic_2022_affect.pdf``.

    The denominator comes from the committed manifest, never from the filesystem.
    """
    names = sorted(MANIFEST)
    if subdir:
        prefix = subdir.rstrip("/") + "/"
        names = [n for n in names if n.startswith(prefix)]
    return names


def _unresolved_path(rel: str, why: str) -> Path:
    """A path that cannot exist, whose STRING names the cause.

    A skip reason reading ``<corpus>/apa/x.pdf not found`` teaches the reader
    nothing. This one says which of the three outcomes above they are in.
    """
    return Path(f"<docpluck-corpus-unresolved:{why}:{rel}>")


def corpus_pdf(rel: str) -> Path:
    """Resolve ``<subdir>/<file>`` to the custodian's copy. Never raises.

    Safe at module scope. When it cannot resolve, the returned path does not
    exist, so an existing ``if not p.is_file(): skip`` keeps working -- while
    ``test_corpus_manifest.py`` fails loudly for the same name.
    """
    rel = rel.replace("\\", "/").strip("/")
    entry = MANIFEST.get(rel)
    if entry is None:
        return _unresolved_path(rel, "not-in-manifest")
    root = repository_root()
    if root is None:
        return _unresolved_path(rel, "no-article-repository")
    return root / entry["held_at"]


def require_corpus_pdf(rel: str) -> Path:
    """Like :func:`corpus_pdf`, but raises :class:`CorpusPaperMissing` on a miss.

    Use inside a test body. Does not raise merely because the repository is
    absent -- that case is reported once, by the integrity test, rather than 73
    times.
    """
    key = rel.replace("\\", "/").strip("/")
    p = corpus_pdf(key)
    if p.is_file():
        return p
    if not corpus_available():
        raise CorpusPaperMissing(
            f"{key}: the article repository is not on this machine. Set "
            f"{_ENV_REPO} (or {_ENV_VIBE}) to point at it."
        )
    reason = (
        "no manifest entry -- the name matches no paper in custody"
        if key not in MANIFEST
        else f"manifest names {MANIFEST[key]['doi']} but {p} is not on disk"
    )
    raise CorpusPaperMissing(f"{key}: {reason}")


def corpus_pdfs(subdir: str | None = None) -> list[Path]:
    """Every manifest paper (optionally one subdirectory), all of which must resolve.

    Raises rather than returning a short list. A sweep silently running over 40
    papers instead of 101 still prints a percentage, and the percentage is wrong
    by a factor the reader cannot see.
    """
    names = corpus_names(subdir)
    if not names:
        # A subdirectory that matches nothing would otherwise return [], and a
        # caller sweeping it would report "0 failures out of 0" as a pass. That
        # is the same silent-empty defect this module exists to remove, so it
        # must not be reintroduced by a typo in a subdirectory name.
        raise CorpusPaperMissing(
            f"no manifest paper is under subdirectory {subdir!r}. Known "
            f"subdirectories: {', '.join(sorted({n.split('/')[0] for n in MANIFEST}))}"
        )
    if not corpus_available():
        raise CorpusPaperMissing(
            f"the article repository is not on this machine, so none of the "
            f"{len(names)} manifest papers can be read. Set {_ENV_REPO}."
        )
    out: list[Path] = []
    missing: list[str] = []
    for n in names:
        p = corpus_pdf(n)
        if p.is_file():
            out.append(p)
        else:
            missing.append(n)
    if missing:
        raise CorpusPaperMissing(
            f"{len(missing)} of {len(names)} manifest papers are not in custody: "
            + ", ".join(missing[:10])
            + ("..." if len(missing) > 10 else "")
        )
    return out


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest(check_bytes: bool = True) -> list[str]:
    """Return one problem string per manifest entry that does not check out.

    Empty list means every paper resolves AND its bytes hash to what the
    manifest recorded. The hash half is not ceremony: a DOI key pointing at the
    wrong paper reads as present to every existence check there is, and this
    repository has held a wrong PDF under a correct DOI before.
    """
    problems: list[str] = []
    for rel in corpus_names():
        entry = MANIFEST[rel]
        p = corpus_pdf(rel)
        if not p.is_file():
            problems.append(f"{rel}: {entry['doi']} not in custody (looked for {p})")
            continue
        if check_bytes:
            got = _sha256(p)
            if got != entry["sha256"]:
                problems.append(
                    f"{rel}: {entry['doi']} resolves but its BYTES differ -- "
                    f"manifest {entry['sha256'][:12]}..., on disk {got[:12]}.... "
                    "The custodian is holding different content under this DOI."
                )
    return problems
