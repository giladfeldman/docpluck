"""Corpus discovery for the docpluck verification harness.

NOT THE SAME SET AS ``docpluck/testing/corpus_manifest.py``, deliberately, and
the next reader will assume it is. This manifest is the HARNESS corpus: the 101
corpus PDFs plus 25 DOCX and 9 HTML documents from other sources, 135 in all.
``docpluck.testing``'s manifest is the PAPER corpus the test suite resolves BY
DOI -- the same 101 PDFs plus the render-baseline paper, 102 -- and the DOCX and
HTML are absent from it because they are not papers with DOIs and most are not in
custody at all.

Discovers every test document (PDF / DOCX / HTML) across the sibling repos and
emits a committed ``corpus_manifest.json``. The manifest stores Vibe-relative
paths only — no document bytes are committed (the repo is public; see
``feedback_no_pdfs_in_repo``). A document that has moved/disappeared is reported
by ``verify``, never silently dropped.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
from pathlib import Path

# All corpora live under the Vibe portfolio root. Resolved via VIBE_ROOT so the
# manifest stays portable across machines and future moves (the root moved off
# ~/Dropbox/Vibe on 2026-08-03); never hardcode an absolute user path here.
VIBE = Path(os.environ.get("VIBE_ROOT") or (Path.home() / "Vibe"))


def _out_root() -> Path:
    """Where the harness writes its rendered output — OUTSIDE this repo.

    **It used to be `<repo>/verify_out`, defined identically in three modules**
    (`extract.py`, `checks.py`, `inspect.py` — one concept, three tables), and
    it accumulated **347 MB of rendered publication text inside the working
    tree**: title, authors, full body, for 181 documents. Gitignored, but the
    custody rule is explicit that gitignoring is not containment —

        "NO PAPER, PUBLICATION TEXT, GOLD, OR BASELINE LIVES IN THIS REPO —
         article-finder is the sole custodian. Never commit or keep here ...
         the extracted/rendered text of a publication (in ANY format) ...
         **not even gitignored**."

    Found 2026-08-15; the directory on disk was last written 2026-05-22, i.e. it
    had been stale for three months and was regenerable from a newer library at
    any time. Removed, and the default moved out of the tree so it cannot
    silently rebuild there.

    Resolution order:
      1. ``DOCPLUCK_HARNESS_OUT``  — explicit override.
      2. ``$VIBE_ROOT/_artifacts/docpluck-harness`` — beside the portfolio, not
         inside a git repo.

    Output worth KEEPING is registered with article-finder under
    ``--artifact-class tool`` as ``<family>__<producer>@<version>``; an
    unversioned baseline is overwritten by the next release, which turns any
    gate comparing against it into a tautology. Everything here is scratch.
    """
    override = os.environ.get("DOCPLUCK_HARNESS_OUT")
    if override:
        return Path(override)
    return VIBE / "_artifacts" / "docpluck-harness"


OUT_ROOT = _out_root()


def require_corpus_root() -> None:
    """Fail loudly when the portfolio root is missing.

    A missing root must never be silent: discovering 0 documents makes a broken
    run look like a clean one, which is how the 2026-08-03 move went unnoticed
    for weeks.

    MOVED off module scope 2026-08-20. It used to raise on IMPORT, which meant
    `tests/test_harness_text_loss_reflow.py` — a pure-logic test of
    `_fingerprint` and `check_text_loss` that touches no corpus — could not even
    be COLLECTED on a machine without the corpus. pytest treats a collection
    error as an interrupted run, so CI was red on every push since at least
    2026-08-07 and nobody read it.

    The guarantee is unchanged: every function that actually reaches for a
    document calls this first, so a real run still fails loudly and
    immediately. Only the import is now free.
    """
    if not VIBE.is_dir():
        raise FileNotFoundError(
            f"Vibe root not found at {VIBE} — set VIBE_ROOT. A missing root must "
            "fail loudly: silently discovering 0 documents makes a broken run "
            "look like a clean one."
        )

# (source, root-relative-to-VIBE, glob, format). Order is stable — it fixes the
# manifest ordering so a regenerated manifest diffs cleanly.
# NOTE: the `corpus` source is NOT here. Its 101 papers come from the
# article custodian's committed manifest (`docpluck.testing.corpus_manifest`),
# injected by `discover()` below, because a glob computes its denominator from
# its own numerator -- it reports 40/40 on a corpus that has silently shrunk.
SOURCES: list[tuple[str, str, str, str]] = [
    ("escicheck", "MetaScienceTools/ESCIcheckapp/testpdfs", "*.pdf", "pdf"),
    ("docxtests", "MetaScienceTools/ESCIcheckapp/docxtests", "*.docx", "docx"),
    ("fulltext-html", "ArticleRepository/fulltext", "*.html", "html"),
]

# Files that match a glob but are not real test inputs.
_EXCLUDE_STEMS = {"oclc_page"}

_MANIFEST_PATH = Path(__file__).with_name("corpus_manifest.json")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _slug(text: str) -> str:
    """Filesystem- and URL-safe lowercase slug."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


def discover() -> list[dict]:
    """Walk every source and return the document records, deterministically ordered."""
    require_corpus_root()
    docs: list[dict] = []
    seen_ids: set[str] = set()
    # The docpluck corpus, from the custodian. Ordered by corpus name so the
    # manifest diffs cleanly, and keyed the same way the glob used to key it so
    # existing document ids are unchanged.
    from docpluck.testing.corpus import MANIFEST as _CORPUS

    for rel in sorted(_CORPUS):
        sub, _, stem = rel.rpartition("/")
        stem = stem[:-4] if stem.endswith(".pdf") else stem
        parts = ["corpus"] + ([sub] if sub else []) + [stem]
        doc_id = "__".join(_slug(x) for x in parts)
        seen_ids.add(doc_id)
        docs.append(
            {
                "id": doc_id,
                "source": "corpus",
                "format": "pdf",
                "corpus_path": rel,
                "doi": _CORPUS[rel]["doi"],
            }
        )
    for source, rel_root, pattern, fmt in SOURCES:
        root = VIBE / rel_root
        if not root.is_dir():
            continue
        for path in sorted(root.glob(pattern), key=lambda p: str(p).lower()):
            if not path.is_file() or path.stem in _EXCLUDE_STEMS:
                continue
            # NEITHER THE PATH NOR THE FILENAME MAY REACH THE COMMITTED MANIFEST.
            #
            # This repo is PUBLIC. Until 2026-09-17 this loop wrote a `rel_path`
            # (an internal portfolio path naming another project) and derived the
            # document `id` by slugifying the FILENAME. For the docx source those
            # filenames are in-progress replication manuscripts carrying co-author
            # names, so the committed manifest published the titles of unsubmitted
            # papers -- in the id as well as the path, which is why dropping only
            # the path would not have fixed it. Measured on origin/main the same
            # day: 76 occurrences of the internal project name, live and public.
            #
            # Both are replaced by the file's sha256, which identifies the document
            # and discloses nothing. `resolve()` rediscovers the local file by hash,
            # so the harness still works without the manifest carrying a path.
            #
            # The PDF source above is exempt because it does not go through here at
            # all: those 101 are named by DOI through the article custodian.
            sha = _sha256(path)
            doc_id = f"{_slug(source)}__{sha[:16]}"
            n = 2
            base = doc_id
            while doc_id in seen_ids:
                doc_id = f"{base}-{n}"
                n += 1
            seen_ids.add(doc_id)
            docs.append({"id": doc_id, "source": source, "format": fmt, "sha256": sha})
    return docs


def build_manifest() -> dict:
    require_corpus_root()
    docs = discover()
    by_fmt: dict[str, int] = {}
    for d in docs:
        by_fmt[d["format"]] = by_fmt.get(d["format"], 0) + 1
    return {
        "version": 1,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "counts": {"total": len(docs), "by_format": by_fmt},
        "documents": docs,
    }


def load_manifest() -> dict:
    if not _MANIFEST_PATH.is_file():
        raise FileNotFoundError(
            f"{_MANIFEST_PATH} missing — run `python -m scripts.harness.corpus --write`"
        )
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def resolve(doc: dict) -> Path:
    """Absolute path to a document record's source file.

    A record carrying ``corpus_path`` is one of docpluck's own papers and
    resolves through the article custodian by DOI; ``rel_path`` is the older
    portfolio-relative form, still used by the other sources.
    """
    require_corpus_root()
    if "corpus_path" in doc:
        from docpluck.testing.corpus import corpus_pdf

        return corpus_pdf(doc["corpus_path"])
    if "sha256" in doc:
        # Rediscover the local file by CONTENT. The manifest deliberately carries
        # no path for these (see discover()), so this walks the source roots and
        # matches the hash. Raises rather than returning a path that is not there.
        for source, rel_root, pattern, _fmt in SOURCES:
            if source != doc["source"]:
                continue
            root = VIBE / rel_root
            if not root.is_dir():
                continue
            for path in sorted(root.glob(pattern), key=lambda p: str(p).lower()):
                if path.is_file() and _sha256(path) == doc["sha256"]:
                    return path
        raise FileNotFoundError(
            f"{doc['id']}: no file under source {doc['source']!r} hashes to "
            f"{doc['sha256'][:16]}.... The document has been moved, renamed or "
            "changed; regenerate the manifest rather than guessing which file it was."
        )
    return VIBE / doc["rel_path"]


def main() -> None:
    ap = argparse.ArgumentParser(description="docpluck harness — corpus discovery")
    ap.add_argument("--write", action="store_true", help="write corpus_manifest.json")
    args = ap.parse_args()
    manifest = build_manifest()
    print(f"discovered {manifest['counts']['total']} documents: {manifest['counts']['by_format']}")
    missing = [d["id"] for d in manifest["documents"] if not resolve(d).is_file()]
    if missing:
        print(f"WARNING: {len(missing)} manifest paths do not resolve")
    if args.write:
        _MANIFEST_PATH.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"wrote {_MANIFEST_PATH}")
    else:
        print("(dry run — pass --write to persist)")


if __name__ == "__main__":
    main()
