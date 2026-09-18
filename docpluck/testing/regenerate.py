r"""Regenerate ``corpus_manifest.py`` from the article custodian.

Run this when a paper joins or leaves the test corpus::

    python -m docpluck.testing.regenerate <corpus-dir> --from-view render-baseline__docpluck

Either input may be used alone. ``<corpus-dir>`` takes the corpus from a
directory of files; ``--from-view`` takes it from a view the custodian has
registered, resolving each paper by DOI to the repository's own copy. The
second exists because the first cannot express a paper the custodian holds but
no local directory contains -- and because the directory this was first run
against is being deleted, at which point a directory-only generator could no
longer run at all.

The manifest is COMMITTED on purpose. It is the corpus's denominator, and a
denominator that is recomputed at read time from whatever happens to be on disk
cannot ever report that something went missing -- it just reports a smaller
number of successes out of a smaller total, at 100%.

Nothing published is written here: a DOI, a custodian-relative path and a
sha256 are identifiers, not article content. No PDF, and no extracted text, may
be committed to this repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HEADER = '''"""GENERATED -- do not edit by hand. See ``docpluck/testing/regenerate.py``.

Corpus-relative name -> the paper it names, as the article custodian holds it.

``held_at`` is relative to the article repository root; ``doi`` is the paper's
canonical identifier and the only thing here anybody should cite. ``sha256`` is
what the bytes must hash to, so a DOI key that has come to point at a DIFFERENT
paper fails loudly instead of reading as present.
"""

from __future__ import annotations

MANIFEST: dict[str, dict[str, str]] = {
'''

FOOTER = "}\n"


def _article_finder() -> Path:
    return Path(
        os.environ.get("ARTICLE_FINDER_HOME")
        or (Path.home() / ".claude" / "skills" / "article-finder")
    )


def _repository_root() -> Path:
    explicit = os.environ.get("ARTICLE_REPOSITORY")
    if explicit:
        return Path(explicit)
    return Path(os.environ.get("VIBE_ROOT") or (Path.home() / "Vibe")) / "ArticleRepository"


def _doi_from_held_at(held_at: str) -> str:
    """``fulltext/10.1001__jamanetworkopen.2023.39337.pdf`` -> the DOI it encodes.

    Some filenames carry a ``~<hex>`` disambiguator because the custodian holds
    more than one DISTINCT file under one DOI (a preprint and a version of
    record, say). It belongs to the filename, not to the paper, so it is
    stripped here -- the first draft of this function left it in and emitted
    three DOIs that resolve to nothing, e.g.
    ``10.1177/01461672251327169~8b62f2fb632bef4a``.

    ``held_at`` therefore stays the pointer to the exact bytes and ``doi`` stays
    the citable identifier; they are not interchangeable and the manifest keeps
    both.
    """
    stem = Path(held_at).stem
    return stem.split("~", 1)[0].replace("__", "/")


def _papers_from_view(spec: str) -> dict[str, dict[str, str]]:
    """Corpus entries for every paper in a REGISTERED VIEW, straight from custody.

    ``build()`` takes its paper set from a DIRECTORY, so the corpus is exactly
    whatever sits in that directory. That has two consequences this
    exists to remove:

    1. A paper the custodian holds but that directory does not cannot enter the
       manifest at all. ``10.1017/s1930297500009189`` is one -- it is in the
       render baseline, and it is the known positive for the
       ``_suppress_inline_duplicate_table_captions`` deletion class, so the
       corpus was missing the one paper that can prove that class is still
       caught.
    2. The directory is being deleted. A generator whose only input is a
       directory dies with it, and ``corpus_manifest.py`` -- a file whose header
       forbids editing it by hand -- would become impossible to regenerate and
       impossible to edit at the same moment.

    Nothing is downloaded and nothing is copied: the view gives canonical keys,
    ``find-pdf.py --dry-run`` resolves each to the custodian's own file, and the
    bytes are hashed where they already live. ``held_at`` therefore points at the
    repository exactly as ``build()``'s entries do, which is what lets
    ``docpluck.testing.corpus`` resolve both kinds identically.
    """
    af = _article_finder() / "ai-gold.py"
    if not af.is_file():
        raise SystemExit(
            f"FATAL: article-finder is not installed at {af.parent}. It is the sole "
            "custodian, so there is no view to read a paper set from."
        )
    r = subprocess.run(
        [sys.executable, str(af), "papers-with-view", spec, "--latest", "--keys-only"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    keys = sorted(k for k in (ln.strip() for ln in r.stdout.splitlines()) if k)
    if not keys:
        raise SystemExit(
            f"FATAL: view {spec!r} lists no papers.\nstderr: {r.stderr.strip()}\n"
            "Refusing to emit a manifest from an empty view -- a corpus that "
            "silently became empty must not read as a corpus that shrank."
        )
    finder = _article_finder() / "find-pdf.py"
    located: list[str] = []
    for key in keys:
        doi = key.replace("__", "/") if key.startswith("10.") else key
        fr = subprocess.run(
            [sys.executable, str(finder), doi, "--dry-run"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        try:
            d = json.loads(fr.stdout)
        except (json.JSONDecodeError, ValueError):
            d = {}
        if not (d.get("found") and d.get("source") == "repository_cache" and d.get("path")):
            raise SystemExit(
                f"FATAL: {doi} is in view {spec} but not in custody on this machine. "
                "Ingest it through article-finder before regenerating -- a manifest "
                "that quietly omits it would shrink the corpus with no diff to read."
            )
        located.append(d["path"])

    # ``held_at`` comes from the CUSTODIAN, never from arithmetic on the path we
    # were handed. Deriving it locally looked like one line and was wrong: the
    # repository presents itself at two paths on this machine (a Vibe-relative
    # one and the Dropbox directory it links to), so ``relative_to`` against the
    # configured root raised on files that were plainly in custody. ``build()``
    # already asks ``in-custody`` for exactly this field, and one concept gets
    # one implementation -- two would drift, and the drift would be silent.
    proc = subprocess.run(
        [sys.executable, str(af), "in-custody", "--json", *located],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if not proc.stdout.strip():
        raise SystemExit(f"FATAL: in-custody produced no output.\n{proc.stderr}")
    out: dict[str, dict[str, str]] = {}
    for f in json.loads(proc.stdout)["files"]:
        p = Path(f["path"])
        if not f.get("in_custody"):
            raise SystemExit(
                f"FATAL: {p} is in view {spec} but NOT in custody. Ingest it through "
                "article-finder before regenerating."
            )
        held = f["held_at"]
        out[f"baseline/{Path(held).name}"] = {
            "doi": _doi_from_held_at(held),
            "held_at": held,
            "sha256": f["sha256"],
        }
    return out


def build(paths: list[str]) -> dict[str, dict[str, str]]:
    """Ask the custodian which paper each file IS, by content hash."""
    af = _article_finder() / "ai-gold.py"
    if not af.is_file():
        raise SystemExit(
            f"FATAL: article-finder is not installed at {af.parent}. It is the sole "
            "custodian of the corpus, so there is nothing to build a manifest from. "
            "Refusing to emit a manifest assembled from a directory listing."
        )
    proc = subprocess.run(
        [sys.executable, str(af), "in-custody", "--json", *paths],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if not proc.stdout.strip():
        raise SystemExit(f"FATAL: in-custody produced no output.\n{proc.stderr}")
    data = json.loads(proc.stdout)
    out: dict[str, dict[str, str]] = {}
    roots = [Path(p).resolve() for p in paths]
    for f in data["files"]:
        p = Path(f["path"]).resolve()
        if p.suffix.lower() not in (".pdf", ".docx", ".html", ".htm"):
            continue
        if not f.get("in_custody"):
            raise SystemExit(
                f"FATAL: {p} is NOT in custody. Ingest it through article-finder "
                "before regenerating -- a manifest that quietly omits it would "
                "shrink the corpus with no diff to read."
            )
        held = f["held_at"]
        if not held.startswith("fulltext/"):
            continue
        rel = None
        for r in roots:
            if r in p.parents:
                rel = p.relative_to(r).as_posix()
                break
        if rel is None:
            continue
        out[rel] = {
            "doi": _doi_from_held_at(held),
            "held_at": held,
            "sha256": f["sha256"],
        }
    return out


def render(manifest: dict[str, dict[str, str]]) -> str:
    lines = [HEADER]
    for rel in sorted(manifest):
        e = manifest[rel]
        lines.append(f'    {rel!r}: {{\n')
        lines.append(f'        "doi": {e["doi"]!r},\n')
        lines.append(f'        "held_at": {e["held_at"]!r},\n')
        lines.append(f'        "sha256": {e["sha256"]!r},\n')
        lines.append("    },\n")
    lines.append(FOOTER)
    return "".join(lines)


def verify_against_custody(manifest: dict[str, dict[str, str]]) -> list[str]:
    root = _repository_root()
    bad = []
    for rel, e in sorted(manifest.items()):
        p = root / e["held_at"]
        if not p.is_file():
            bad.append(f"{rel}: {p} missing")
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        if h != e["sha256"]:
            bad.append(f"{rel}: sha mismatch")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "paths",
        nargs="*",
        help="directories or files to take the corpus FROM (each must already be in custody)",
    )
    ap.add_argument(
        "--from-view",
        metavar="SPEC",
        help="also take every paper in this registered view, resolved from custody "
             "by DOI rather than from a directory, e.g. render-baseline__docpluck",
    )
    ap.add_argument("--out", default=str(Path(__file__).with_name("corpus_manifest.py")))
    ap.add_argument("--check", action="store_true", help="verify only; write nothing")
    args = ap.parse_args()

    if not args.paths and not args.from_view:
        ap.error("give at least one path, or --from-view, or both")

    manifest = build(args.paths) if args.paths else {}
    from_dir = len(manifest)
    if args.from_view:
        # Directory entries WIN on a DOI collision: their corpus_path is the
        # name the suite already refers to (``apa/efendic_2022_affect.pdf``),
        # and re-keying it would break every test that names it. The view only
        # ever ADDS papers the directory does not hold.
        seen = {e["doi"] for e in manifest.values()}
        added = 0
        for rel, entry in sorted(_papers_from_view(args.from_view).items()):
            if entry["doi"] in seen:
                continue
            manifest[rel] = entry
            seen.add(entry["doi"])
            added += 1
        print(f"resolved {from_dir} documents from paths, "
              f"+{added} from view {args.from_view} not already present")
    print(f"resolved {len(manifest)} documents through article-finder")
    bad = verify_against_custody(manifest)
    if bad:
        print("FATAL: custody verification failed:", *bad, sep="\n  ")
        return 1
    if args.check:
        print("check only -- nothing written")
        return 0
    Path(args.out).write_text(render(manifest), encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
