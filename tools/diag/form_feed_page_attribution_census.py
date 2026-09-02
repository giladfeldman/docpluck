"""Census: which form feeds actually corrupt the repeated-line gate's page map?

REGENERATES THE NUMBERS QUOTED IN `normalize.py`'s page-attribution comment.
A number quoted without the command that regenerates it is a claim, not a
finding -- this stream has already lost two figures that way (an unreproducible
font ratio, and its equally unreproducible correction).

The question is NOT "how many form feeds are glued to content". It is "how many
are glued to a line the gate actually RECORDS", because:

  - a form feed ALONE on its line is HARMLESS -- `strip()` empties the line, so
    nothing is recorded and the page increment lands cleanly either way;
  - a form feed glued to a line outside the 15-120 character candidate band is
    equally harmless -- that line is never recorded, so its page is never read.

Only a form feed glued to a RECORDED candidate misassigns a page. That is the
figure that bounds the fix, and it is smaller than "all glued" and larger than
any corner case -- which is exactly why it needed measuring rather than
rounding to either end.

ENGLISH-LANGUAGE SCOPE: this counts a typographic artifact of pdftotext's page
separator and is language-independent, so no language filter is applied. It
makes no claim about numeric locale or about any rule that reads content.

Usage
-----
    python tools/diag/form_feed_page_attribution_census.py <pdf-or-txt-dir> [--limit N]

Accepts a directory of PDFs (extracted through `extract_pdf`, the shipping
path) or a directory of pre-extracted `.txt`. Extracting once into a cache and
pointing this at the cache is the cheaper way to iterate.
"""

from __future__ import annotations

# --- repo-root import guard (do not remove) ---------------------------------
# Python puts THIS SCRIPT'S OWN DIRECTORY on sys.path[0] -- never the current
# working directory -- so a script under tools/ or scripts/ has no route to the
# repo root and a bare ``import docpluck`` silently resolves to whatever copy is
# INSTALLED.  Measured 2026-09-01: 16 of 34 importers here loaded site-packages
# 2.4.137 while this tree was 2.4.138, including the 26-paper baseline gate --
# so a fix could be verified all night against a library it had not touched.
# Keyed on the pyproject.toml marker rather than a parents[N] count, so it
# survives the file being moved.  Pinned by
# tests/test_harness_scripts_import_the_working_tree.py.
import sys as _sys
from pathlib import Path as _Path

for _root in _Path(__file__).resolve().parents:
    if (_root / "pyproject.toml").is_file():
        if str(_root) not in _sys.path:
            _sys.path.insert(0, str(_root))
        break
# --- end repo-root import guard ---------------------------------------------

import argparse
import os
import sys

PAGE_BREAK = chr(12)

# The gate's candidate band, mirrored from `normalize.py`'s repeated-line strip.
# ONE CONCEPT, ONE TABLE: if the band moves there, this census is measuring a
# different rule and its numbers stop describing the code.
CANDIDATE_MIN = 15
CANDIDATE_MAX = 120


class Census:
    def __init__(self) -> None:
        self.papers = 0
        self.total = 0
        self.alone = 0
        self.glued_candidate = 0
        self.glued_noncandidate = 0
        self.trailing = 0

    def add(self, raw: str) -> None:
        self.papers += 1
        for line in raw.split("\n"):
            n = line.count(PAGE_BREAK)
            if not n:
                continue
            self.total += n
            stripped = line.strip()
            content_at = len(line) - len(line.lstrip())
            leading = line.count(PAGE_BREAK, 0, content_at)
            self.trailing += n - leading
            if not stripped:
                self.alone += leading
            elif CANDIDATE_MIN <= len(stripped) <= CANDIDATE_MAX:
                self.glued_candidate += leading
            else:
                self.glued_noncandidate += leading

    def report(self) -> None:
        def pct(x: int) -> str:
            return f"{100.0 * x / self.total:5.1f}%" if self.total else "  n/a"

        print(f"papers                                    : {self.papers}")
        print(f"form feeds total                          : {self.total}")
        print(f"  alone on their line (HARMLESS)          : {self.alone:>6}  {pct(self.alone)}")
        print(
            f"  glued, line not a {CANDIDATE_MIN}-{CANDIDATE_MAX} candidate      : "
            f"{self.glued_noncandidate:>6}  {pct(self.glued_noncandidate)}"
        )
        print(
            f"  glued to a RECORDED candidate           : "
            f"{self.glued_candidate:>6}  {pct(self.glued_candidate)}   <- CORRUPTS THE MAP"
        )
        print(f"  after content on the line               : {self.trailing:>6}  {pct(self.trailing)}")
        print()
        print(
            "The bounding figure is the RECORDED-candidate row. "
            "'All glued' overstates it; 'alone on their line' is not a defect."
        )


def _iter_texts(path: str, limit: int | None):
    names = sorted(os.listdir(path))
    txts = [n for n in names if n.lower().endswith(".txt")]
    pdfs = [n for n in names if n.lower().endswith(".pdf")]

    if txts:
        for name in txts[:limit]:
            with open(os.path.join(path, name), encoding="utf-8") as fh:
                yield name, fh.read()
        return

    if not pdfs:
        print(f"no .txt or .pdf found under {path}", file=sys.stderr)
        return

    # Go through extract_pdf -- the SHIPPING path. A census that shells out to
    # pdftotext directly measures pdftotext, and cannot see the engine fallback.
    from docpluck.extract import extract_pdf

    for name in pdfs[:limit]:
        with open(os.path.join(path, name), "rb") as fh:
            data = fh.read()
        try:
            text, _engine = extract_pdf(data)  # TUPLE -- unpack, never measure whole
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        if not isinstance(text, str) or len(text) < 10_000:
            print(f"  SKIP {name}: extraction too small to trust", file=sys.stderr)
            continue
        yield name, text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("corpus", help="directory of .pdf or pre-extracted .txt")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)

    census = Census()
    for _name, text in _iter_texts(args.corpus, args.limit):
        census.add(text)

    if not census.papers:
        print("no papers read -- this is a broken instrument, not a clean result")
        return 2
    census.report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
