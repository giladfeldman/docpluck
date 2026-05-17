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
import re
from pathlib import Path

# All corpora live under ~/Dropbox/Vibe. Manifest paths are stored relative to
# this root so the manifest is portable across machines.
VIBE = Path.home() / "Dropbox" / "Vibe"

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
        "vibe_root": "~/Dropbox/Vibe",
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
