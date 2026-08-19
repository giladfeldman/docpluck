r"""Which glyphs are drawn by a font that is NOT the font of the text around them?

DIAGNOSTIC ONLY. This scan does not repair anything and is not imported by the
library. Its job is to establish whether a purely TYPOGRAPHIC signal can
identify the glyph-corruption classes that `W0b`/`W0d`/`W0g` currently decide
INFERENTIALLY — i.e. by reasoning about what the numbers ought to be, which is
the consumer's job, not ours.

## The corruption

Some publisher font pipelines emit a symbol as a digit. Rasterized from primary
source, `10.1177/19485506211056761` p5 prints

    interval (CI): [-0.96, -0.59], p = .003
    r(10) = -.84, 95% CI = [-0.95, -0.50], p < .001

while the extracted text layer says `[20.96, 20.59]` and `[20.95, 20.50]`. The
minus sign is drawn as a `2`. The same paper draws the multiplication sign as a
`3` and `<` as a backslash.

## The signal, and the two ways of getting it wrong

**Step 1 — the font's document-wide REPERTOIRE.** A text font in a 12-page
paper emits 50-90 distinct characters. Measured on the paper above:

    AdvTimes   total=35682  distinct=86    <- a real text font
    AdvP586B   total=124    distinct=3     '2'x99, '3'x24, '.'x1
    AdvPSMP4   total=24     distinct=1     '\\'x24

A font whose entire repertoire is three characters is not a text font.

**BUT THE REPERTOIRE ALONE DISCRIMINATES NOTHING.** Measured over the 152-paper
corpus: **109 papers (72%)** carry at least one font with <= 6 distinct
characters, and **13 (9%)** carry one that is >= 50% digits. Adopting it as a
gate would be the `uni: no` mistake again (that fires on 84% of 200 papers).

**Step 2 — the FALSE POSITIVES, and what actually separates them.** Of those 13,
the known-negative cases are legitimate typography:

    ieee-access-7          CMR5 / CMR6         LaTeX Computer Modern at 5pt/6pt
    chandrashekar-2021     ntxsups-Regular     a SUPERSCRIPT font ("sups")
    aom/amj-1              AdvOT463cc31e       footnote markers, n=568

Measured against their neighbouring characters:

    case                          d(size)   d(baseline)
    efendic AdvP586B  (POSITIVE)   +0.00    -0.24 / +0.09 / -0.02
    aom AdvOT463cc31e (negative)   +0.00    -2.49
    chandrashekar ntxsups (neg)    +0.00    -2.61 / -2.17
    ieee CMR5 (negative)           -4.98    --

A corrupt minus sign is drawn WHERE A MINUS SIGN GOES: inline, at the body
size, on the body baseline. Every false positive is displaced — smaller (a
LaTeX small-size face) or raised (a superscript face). So the discriminator is

    a single-glyph, mid-token switch to a font whose document-wide repertoire
    is tiny, AT THE SAME SIZE AND THE SAME BASELINE as its neighbours.

Three independent typographic conditions, none of which appeals to what the
number ought to be.

## Why "family root" was rejected

An earlier proposal compared PostScript family roots. Refuted: Elsevier's AdvTT
faces are opaque hashes, so root=`AdvTT` misses the known positive while
root=hash fires on every italic/roman pair in every paper.

## MEASURED LIMITATION — the "glued" condition is CLASS-SPECIFIC

Requiring the glyph to touch its neighbour is what suppresses italic statistical
symbols (`n = 42` has a real space), and it is correct for every corruption that
FUSES INTO A NUMBER — the `2`-for-minus in `[20.96`, the `\` in `\.001`.

**It also excludes a real corruption class, and this was measured, not assumed.**
`aom/amj-1` prints `(α = .93)` and delivers `a5(.93)`: the corrupt `α`->`a` and
`=`->`5` are STAND-ALONE tokens with ordinary word spaces around them, so they
fail the glue test. Tightening the gap from 0.4 to 0.15 x size took that paper
from 13 inline hits to 1 — it removed 58 italic-`n` false positives elsewhere
and **also removed a true positive here**.

So this scan currently answers *"which glyphs are fused into a token from a
foreign narrow font?"* and NOT the more general *"which glyphs came from a
mis-mapped symbol font?"* A separate detector is needed for the stand-alone
class, keyed on the font's repertoire alone plus the grammatical impossibility
of the decoded character in its slot (`5` in an operator position). Do not read
a zero from this scan as evidence that a paper is clean.

Corpus prevalence at these settings: **21 of 152 papers (14%)** show at least
one inline discontinuity; before the glue+family tightening it was 36 (24%), the
difference being mostly italic statistical symbols.

Usage:
    python -m tools.diag.glyph_font_discontinuity_scan            # corpus scan
    python -m tools.diag.glyph_font_discontinuity_scan --doc ID   # one paper
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from collections import Counter
from pathlib import Path

warnings.filterwarnings("ignore")

VIBE = Path(os.environ.get("VIBE_ROOT") or (Path.home() / "Vibe"))
_MANIFEST = Path(__file__).resolve().parents[2] / "scripts" / "harness" / "corpus_manifest.json"

# A font is "narrow" when its whole-document repertoire is at most this many
# distinct characters. Not a gate on its own — see the module docstring.
NARROW_REPERTOIRE = 6
# Below this many glyphs a font is too rare to say anything about.
MIN_GLYPHS = 8
# Same-size / same-baseline tolerances, in points. Derived from the measured
# separation above: true positives sit within ±0.5 of their neighbours on both
# axes; the nearest false positive is displaced 2.17pt vertically.
MAX_SIZE_DELTA = 0.5
MAX_BASELINE_DELTA = 0.6
# Two glyphs are GLUED when the gap between them is at most this fraction of
# the glyph size. Measured: the known-positive corrupt minus abuts its bracket
# at ratio -0.004; a word space at 10pt is ~0.25. Anything looser admits every
# space-separated pair and drowns the signal in italic statistical symbols.
MAX_GLUE_GAP = 0.15

# THE FONT-NAME DISCRIMINATORS LIVE IN THE LIBRARY, NOT HERE.
# `_same_family`, `strip_subset` and `_size_variant_base` were defined in this
# file and re-derived inside `extract_layout.detect_symbol_font_corruption` when
# that detector was hardened against the same false positives. Two definitions of
# one rule WILL diverge silently, so there is now exactly one, and this scan
# imports it. See `docpluck/extract_layout.py` for the measurements behind each.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from docpluck.extract_layout import (  # noqa: E402
    font_size_variant_base as _size_variant_base,
    fonts_are_same_family as _same_family,
    strip_font_subset_prefix as strip_subset,
)


def font_repertoires(pages) -> dict[str, Counter]:
    """Whole-document character census, per font."""
    per_font: dict[str, Counter] = {}
    for page in pages:
        for c in page.chars:
            per_font.setdefault(strip_subset(c["fontname"]), Counter())[c.get("text") or ""] += 1
    return per_font


def narrow_fonts(per_font: dict[str, Counter]) -> dict[str, dict]:
    """Fonts whose whole-document repertoire is implausibly small.

    NOT A GATE ON ITS OWN — 72% of the 152-paper corpus has one. Two exclusions
    are applied here because both are pure typography and both were measured
    against real false positives:

    * **TeX optical-size variants.** ``CMR5``/``CMR6`` are narrow only because
      the document sets few characters at 5pt; ``CMR10`` in the same document
      carries a full repertoire. `ieee-access-7` produced 86 inline hits this
      way, all legitimate LaTeX math.
    * **Repertoires that are already correct symbols.** ``NewTXMI`` emits
      ``𝛼``/``𝜒`` — real Unicode math italics, decoded correctly, legitimately
      inline in body text. The corruption classes emit plain ASCII standing in
      for a symbol (``AdvPS7DA6`` emits only ``D a b x`` — the Adobe-Symbol
      Greek mapping for Δ α β ξ), so a non-ASCII repertoire means the font is
      decoding fine and has nothing to report.
    """
    full_repertoire_bases = {
        _size_variant_base(f)
        for f, c in per_font.items()
        if len(c) > NARROW_REPERTOIRE and _size_variant_base(f)
    }
    out: dict[str, dict] = {}
    for font, cnt in per_font.items():
        total = sum(cnt.values())
        if total < MIN_GLYPHS or len(cnt) > NARROW_REPERTOIRE:
            continue
        base = _size_variant_base(font)
        if base and base in full_repertoire_bases:
            continue                        # a TeX optical-size cut
        chars = "".join(sorted(cnt))
        if any(ord(ch) > 127 for ch in chars if ch):
            continue                        # already-correct symbols
        out[font] = {
            "total": total,
            "distinct": len(cnt),
            "chars": chars,
            "digit_share": sum(v for k, v in cnt.items() if k.isdigit()) / total,
        }
    return out


def _line_chars(page):
    """Characters sorted into reading order, grouped by visual line."""
    chars = [c for c in page.chars if (c.get("text") or "").strip()]
    chars.sort(key=lambda c: (round(c["top"], 1), c["x0"]))
    return chars


def discontinuities(page, narrow: dict[str, dict]) -> list[dict]:
    """Glyphs from a narrow font that sit INLINE inside other-font text.

    Requires, for the immediate same-line neighbours drawn by a different font:
      * the same size   (|d| <= MAX_SIZE_DELTA)   — excludes LaTeX small faces
      * the same baseline (|d| <= MAX_BASELINE_DELTA) — excludes superscripts
    """
    hits: list[dict] = []
    chars = _line_chars(page)
    for i, c in enumerate(chars):
        font = strip_subset(c["fontname"])
        if font not in narrow:
            continue
        gap_limit = MAX_GLUE_GAP * max(c["size"], 1.0)

        def _is_glued_neighbour(x) -> bool:
            """Same line, TOUCHING this glyph, and from an unrelated family.

            Two conditions, both measured rather than guessed:

            * **Touching, not merely near.** The corrupt minus in the known
              positive abuts its bracket at a gap of **-0.04pt** (ratio -0.004
              of the glyph size). A word space at 10pt is ~2.5pt (ratio ~0.25),
              so a loose threshold admits every space-separated pair — which is
              how an earlier draft of this scan reported the italic ``n`` in
              ``n = 42`` across 58 sites of one BMC paper.
            * **An unrelated family.** ``MyriadPro-Regular`` beside
              ``MyriadPro-Italic`` is ordinary typography: journals set
              statistical symbols in italic, and that is a real mid-token font
              change carrying no defect. Used ONLY as a negative filter — the
              family root was refuted as a *positive* signal (opaque hash names
              defeat it), but "same stem, different style suffix" is sound
              evidence of ordinary styling.
            """
            if x is c or abs(x["top"] - c["top"]) >= 4.0:
                return False
            other = strip_subset(x["fontname"])
            if other == font or _same_family(other, font):
                return False
            return (
                abs(x["x0"] - c["x1"]) < gap_limit    # x follows c
                or abs(c["x0"] - x["x1"]) < gap_limit  # x precedes c
            )

        neighbours = [x for x in chars[max(0, i - 3): i + 4] if _is_glued_neighbour(x)]
        if not neighbours:
            continue
        ref = neighbours[0]
        d_size = c["size"] - ref["size"]
        d_base = c["top"] - ref["top"]
        inline = abs(d_size) <= MAX_SIZE_DELTA and abs(d_base) <= MAX_BASELINE_DELTA
        ctx = "".join(
            x["text"] for x in chars[max(0, i - 12): i + 12]
            if abs(x["top"] - c["top"]) < 4.0
        )
        hits.append({
            "char": c["text"], "font": font, "neighbour_font": strip_subset(ref["fontname"]),
            "size": round(c["size"], 2), "d_size": round(d_size, 2),
            "d_baseline": round(d_base, 2), "inline": inline, "context": ctx,
        })
    return hits


def scan_document(path: Path) -> dict:
    import pdfplumber
    with pdfplumber.open(str(path)) as pdf:
        per_font = font_repertoires(pdf.pages)
        narrow = narrow_fonts(per_font)
        hits: list[dict] = []
        if narrow:
            for pno, page in enumerate(pdf.pages, start=1):
                for h in discontinuities(page, narrow):
                    h["page"] = pno
                    hits.append(h)
    return {
        "n_fonts": len(per_font),
        "narrow_fonts": narrow,
        "hits": hits,
        "inline_hits": [h for h in hits if h["inline"]],
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--doc", help="a single corpus document id (substring match)")
    ap.add_argument("--limit", type=int, default=0, help="stop after N documents")
    ap.add_argument("--json", help="write full results here")
    args = ap.parse_args()

    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    docs = [d for d in manifest["documents"] if d["format"] == "pdf"]
    if args.doc:
        docs = [d for d in docs if args.doc in d["id"]]
        if not docs:
            raise SystemExit(f"no corpus document matches {args.doc!r}")
    if args.limit:
        docs = docs[: args.limit]

    results = {}
    n_narrow = n_inline = 0
    for i, d in enumerate(docs):
        path = VIBE / d["rel_path"]
        if not path.is_file():
            print(f"[{i}] {d['id']}: MISSING")
            continue
        try:
            res = scan_document(path)
        except Exception as exc:
            print(f"[{i}] {d['id']}: EXC {type(exc).__name__}: {exc}")
            continue
        results[d["id"]] = res
        if res["narrow_fonts"]:
            n_narrow += 1
        if res["inline_hits"]:
            n_inline += 1
            print(f"\n[{i}] {d['id']}")
            for font, meta in res["narrow_fonts"].items():
                print(f"      narrow font {font:<22} n={meta['total']:<5} "
                      f"distinct={meta['distinct']} chars={meta['chars']!r}")
            seen = Counter()
            for h in res["inline_hits"]:
                key = (h["font"], h["char"])
                seen[key] += 1
                if seen[key] <= 3:
                    print(f"      INLINE p{h['page']:<3} {h['char']!r} from {h['font']} "
                          f"in {h['neighbour_font']} dsize={h['d_size']:+.2f} "
                          f"dbase={h['d_baseline']:+.2f}")
                    print(f"             ctx: {h['context']!r}")
            print(f"      -> {len(res['inline_hits'])} inline hits, "
                  f"{len(res['hits']) - len(res['inline_hits'])} displaced (excluded)")

    n = len(results)
    print(f"\n{'=' * 68}")
    print(f"documents scanned                      : {n}")
    print(f"with a NARROW-repertoire font          : {n_narrow} "
          f"({100 * n_narrow / max(n, 1):.0f}%)   <- NOT a gate; see docstring")
    print(f"with an INLINE font discontinuity      : {n_inline} "
          f"({100 * n_inline / max(n, 1):.0f}%)   <- the discriminator")
    if n_inline == 0 and n:
        print("\nWARNING: zero inline hits. A ZERO IS A CLAIM ABOUT THE INSTRUMENT "
              "UNTIL PROVEN OTHERWISE.\nRun against the known positive before "
              "believing it:\n  --doc efendic")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
