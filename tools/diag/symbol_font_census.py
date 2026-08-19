"""What does each embedded font in this PDF actually DRAW?

The number this tool exists to make re-runnable
=============================================

Three documents asserted that on the minus-corruption paper "corrupt shapes came
from the symbol font **64/68** while real digits came from the body font
**135/135**", and nothing in this repo produced those figures. `OVERHAUL_REGISTER`
§G3 replaced them with "9 leading-`2`s differ in font from the digits glued to
them and 2 match, with no overlap" — and **that did not reproduce either**:
re-measured 2026-08-15 on the same paper it gives 10 differing, 6 matching, and
the two font sets DO overlap (`AdvTimes`, `AdvPS8E9A` appear on both sides).

Neither figure was wrong so much as UNSTATED: a per-token ratio depends entirely
on how you enumerate tokens, and no method was written down, so no method can be
re-run. That is the same defect twice — a measurement quoted forward without the
instrument that produced it.

So this tool reports the measurement that is method-independent and stark, and
it is the one the library's own detector actually keys on:

    AdvTimes    total=35682  distinct=86   <- a real text font
    AdvP586B    total=124    distinct=3    '2' x99, '3' x24, '.' x1

A font whose ENTIRE whole-document repertoire is `2`, `3` and `.` is not drawing
text. It is the symbol face drawing minus and multiply, decoded as digits — and
that is visible without any appeal to what the statistics ought to be, which is
the whole point of the typographic-evidence rule.

Re-run it before quoting any number from it:

    python tools/diag/symbol_font_census.py <path-to.pdf>
    python tools/diag/symbol_font_census.py <path.pdf> --top 12
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from docpluck.extract_layout import (  # noqa: E402
    detect_symbol_font_corruption,
    extract_pdf_layout,
    strip_font_subset_prefix,
)


def census(layout) -> dict[str, Counter]:
    """``{font: Counter(character -> count)}`` over the whole document."""
    per_font: dict[str, Counter] = {}
    for page in getattr(layout, "pages", ()) or ():
        for ch in getattr(page, "chars", ()) or ():
            name = strip_font_subset_prefix(str(ch.get("fontname") or ""))
            per_font.setdefault(name, Counter())[str(ch.get("text") or "")] += 1
    return per_font


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--top", type=int, default=10, help="fonts to list (by glyph count)")
    args = ap.parse_args()

    if not args.pdf.is_file():
        print(f"FATAL: no such file: {args.pdf}", file=sys.stderr)
        return 2

    layout = extract_pdf_layout(args.pdf.read_bytes())
    per_font = census(layout)
    if not per_font:
        print("NO CHARACTERS EXTRACTED — this is an instrument result, not a "
              "clean one. The PDF may be image-only.")
        return 2

    print(f"{args.pdf.name}: {len(per_font)} embedded font(s)\n")
    print(f"{'font':<28}{'glyphs':>8}{'distinct':>10}  repertoire")
    for font, counts in sorted(per_font.items(), key=lambda kv: -sum(kv[1].values()))[: args.top]:
        total = sum(counts.values())
        shown = "  ".join(f"{c!r}x{n}" for c, n in counts.most_common(6))
        print(f"{font:<28}{total:>8}{len(counts):>10}  {shown}")

    flagged = detect_symbol_font_corruption(layout)
    print("\nFLAGGED BY detect_symbol_font_corruption:",
          flagged if flagged else "(none)")
    print("\nA font drawing thousands of glyphs across 50-90 distinct characters "
          "is a text font.\nA font drawing a handful of characters, all of them "
          "Symbol-Greek preimages, is not.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
