"""Corpus discovery for the docpluck verification harness.

Discovers every test document (PDF / DOCX / HTML) across the sibling repos and
emits a committed ``corpus_manifest.json``. The manifest stores Vibe-relative
paths only — no document bytes are committed (the repo is public; see
``feedback_no_pdfs_in_repo``). A document that has moved/disappeared is reported
by ``verify``, never silently dropped.
"""

from __future__ import annotations

import argparse
import datetime as _dt
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
if not VIBE.is_dir():
    raise FileNotFoundError(
        f"Vibe root not found at {VIBE} — set VIBE_ROOT. A missing root must "
        "fail loudly: silently discovering 0 documents makes a broken run "
        "look like a clean one."
    )

# (source, root-relative-to-VIBE, glob, format). Order is stable — it fixes the
# manifest ordering so a regenerated manifest diffs cleanly.
SOURCES: list[tuple[str, str, str, str]] = [
    ("pdfextractor", "MetaScienceTools/PDFextractor/test-pdfs", "**/*.pdf", "pdf"),
    ("escicheck", "MetaScienceTools/ESCIcheckapp/testpdfs", "*.pdf", "pdf"),
    ("docxtests", "MetaScienceTools/ESCIcheckapp/docxtests", "*.docx", "docx"),
    ("fulltext-html", "ArticleRepository/fulltext", "*.html", "html"),
]

# Files that match a glob but are not real test inputs.
_EXCLUDE_STEMS = {"oclc_page"}

_MANIFEST_PATH = Path(__file__).with_name("corpus_manifest.json")


def _slug(text: str) -> str:
    """Filesystem- and URL-safe lowercase slug."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


def discover() -> list[dict]:
    """Walk every source and return the document records, deterministically ordered."""
    docs: list[dict] = []
    seen_ids: set[str] = set()
    for source, rel_root, pattern, fmt in SOURCES:
        root = VIBE / rel_root
        if not root.is_dir():
            continue
        for path in sorted(root.glob(pattern), key=lambda p: str(p).lower()):
            if not path.is_file() or path.stem in _EXCLUDE_STEMS:
                continue
            # doc id = source + publisher-subdir (if any) + filename stem.
            sub = path.parent.relative_to(root).as_posix()
            parts = [source] + ([sub] if sub != "." else []) + [path.stem]
            doc_id = "__".join(_slug(p) for p in parts)
            n = 2
            base = doc_id
            while doc_id in seen_ids:  # uniqueness guard
                doc_id = f"{base}-{n}"
                n += 1
            seen_ids.add(doc_id)
            docs.append(
                {
                    "id": doc_id,
                    "source": source,
                    "format": fmt,
                    "rel_path": path.relative_to(VIBE).as_posix(),
                }
            )
    return docs


def build_manifest() -> dict:
    docs = discover()
    by_fmt: dict[str, int] = {}
    for d in docs:
        by_fmt[d["format"]] = by_fmt.get(d["format"], 0) + 1
    return {
        "version": 1,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "vibe_root": "~/Vibe",
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
    """Absolute path to a document record's source file."""
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
