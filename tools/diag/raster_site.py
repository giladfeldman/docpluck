"""Rasterize the page a token is printed on, and crop to it, so a human can LOOK.

This is the ONLY test that decides who owns a defect.

    "did we break this, or did the paper?"

Where the extracted text cannot answer that, **rasterize the page and look** —
never adjudicate an extraction defect with the extractors under suspicion.
"pdftotext cannot see it" is not "it is not there"; only the second licenses a
won't-fix, and only the rendered page establishes it. (CLAUDE.md hard rule;
created by a wrong REJECT — a dropped eta-squared filed "never encoded,
OCR-tier" on the strength of both extractors reporting zero occurrences, while
the page plainly printed it.)

poppler's ``pdftoppm`` only. **Never PyMuPDF / fitz** — AGPL, incompatible with
the authenticated service (LESSONS L-003).

Usage:
    python tools/diag/raster_site.py <DOI-or-path> "<needle>" [--out NAME]
                                     [--dpi 600] [--pad 8] [--zoom 5]

``<needle>`` is matched against the page's pdfplumber character stream with
whitespace removed, because that stream has no spaces: search for
``p<05(see`` rather than ``p < 05 (see``. The script reports which page matched
and writes a PNG cropped to the token's own bounding box.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ARTICLE_FINDER = Path(
    os.environ.get("ARTICLE_FINDER_HOME")
    or (Path.home() / ".claude" / "skills" / "article-finder")
)


def resolve_pdf(ref: str) -> Path:
    """A DOI resolves through the CUSTODIAN; a path is used as given.

    Papers live in article-finder's repository, never in this repo
    (CLAUDE.md: article-finder is the sole custodian of publications).
    """
    p = Path(ref)
    if p.is_file():
        return p
    r = subprocess.run(
        [sys.executable, str(ARTICLE_FINDER / "find-pdf.py"), ref, "--dry-run"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    try:
        d = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError):
        raise SystemExit(f"FATAL: could not resolve {ref!r}: {r.stderr.strip()[:300]}")
    if not (d.get("found") and d.get("path")):
        raise SystemExit(f"FATAL: {ref!r} is not in the local repository cache.")
    return Path(d["path"])


def _char_text_and_index_map(chars) -> tuple[str, list[int]]:
    """Concatenated char text, plus a string-offset -> char-index map.

    A char whose glyph has no ToUnicode entry carries ``text == "(cid:2)"`` —
    SEVEN string characters from ONE char object. Indexing ``chars[]`` with a
    raw string offset therefore desyncs by +6 per such glyph, silently, and
    lands several words away. Hit 2026-08-14 on the very site under study, where
    it reported a clean "not found" — i.e. it looked like absence of evidence.
    """
    parts: list[str] = []
    idx: list[int] = []
    for ci, c in enumerate(chars):
        t = c["text"]
        parts.append(t)
        idx.extend([ci] * len(t))
    return "".join(parts), idx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ref", help="DOI (resolved via article-finder) or a PDF path")
    ap.add_argument("needle", help="token to find, whitespace-free (e.g. 'p<05(see')")
    ap.add_argument("--out", default="site")
    ap.add_argument("--dpi", type=int, default=600)
    ap.add_argument("--pad", type=float, default=8.0, help="padding in PDF points")
    ap.add_argument("--zoom", type=int, default=5)
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    import pdfplumber
    from PIL import Image

    pdf_path = resolve_pdf(args.ref)
    outdir = Path(args.outdir or Path(tempfile.gettempdir()) / "docpluck_raster")
    outdir.mkdir(parents=True, exist_ok=True)

    with pdfplumber.open(pdf_path) as pdf:
        hit = None
        for pageno, page in enumerate(pdf.pages, start=1):
            chars = page.chars
            s, imap = _char_text_and_index_map(chars)
            i = s.find(args.needle)
            if i < 0:
                continue
            hit = (pageno, page, chars, imap[i],
                   imap[i + len(args.needle) - 1] + 1)
            break
        if hit is None:
            raise SystemExit(
                f"NOT FOUND: {args.needle!r} in any page's char stream of "
                f"{pdf_path.name}.\nThe char stream has NO SPACES — try the "
                "whitespace-free form of the token."
            )
        pageno, page, chars, lo, hi = hit
        cs = chars[lo:hi]
        x0 = min(c["x0"] for c in cs) - args.pad
        x1 = max(c["x1"] for c in cs) + args.pad
        top = min(c["top"] for c in cs) - args.pad
        bot = max(c["bottom"] for c in cs) + args.pad
        pw = page.width
        fonts = sorted({c["fontname"] for c in cs})

    subprocess.run(
        ["pdftoppm", "-png", "-r", str(args.dpi), "-f", str(pageno), "-l",
         str(pageno), str(pdf_path), str(outdir / f"{args.out}_page")],
        check=True,
    )
    # `--out` may be an ABSOLUTE path (it is the natural thing to pass when the
    # crop should land in a scratch directory), and `Path.glob` rejects a
    # non-relative pattern with NotImplementedError. Glob on the stem only.
    rendered = sorted(outdir.glob(f"{Path(args.out).name}_page-*.png"))
    if not rendered:
        raise SystemExit("FATAL: pdftoppm produced no image.")
    img = Image.open(rendered[-1])
    sc = img.size[0] / pw
    box = (max(0, int(x0 * sc)), max(0, int(top * sc)),
           min(img.size[0], int(x1 * sc)), min(img.size[1], int(bot * sc)))
    crop = img.crop(box)
    crop = crop.resize((crop.width * args.zoom, crop.height * args.zoom),
                       Image.LANCZOS)
    out_png = outdir / f"{args.out}.png"
    crop.save(out_png)

    print(f"pdf       : {pdf_path}")
    print(f"page      : {pageno}  (1-indexed)")
    print(f"token     : {args.needle!r}")
    print(f"fonts     : {', '.join(fonts)}")
    print(f"bbox(pts) : x {x0:.1f}..{x1:.1f}  y {top:.1f}..{bot:.1f}")
    print(f"crop      : {out_png}")
    print(f"full page : {rendered[-1]}")
    print("\nNow LOOK at the crop. What the PAGE prints is the answer;")
    print("what the text layer says is the question.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
