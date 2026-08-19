"""How many papers carry UNDECODABLE fonts, and how often do the INFERENCE rules fire?

Two questions, one sample, because they have to be compared against the same
denominator.

## Why this scan exists

`tools/diag/repair_site_scan.py` reports **0 sites for every W0 glyph rule**,
which reads as "these rules never fire" and is not what it means. Its corpus is
the 26-paper render baseline, and that baseline contains **none of the papers
these rules were built for** — not `efendic_2022` (the `2`-for-minus and
`<`-as-backslash source), not `10.1016/j.jesp.2016.11.001` (the `<`-as-`b`
source). A denominator that excludes every known positive cannot speak to
prevalence. Same trap as the retired locale detector, which measured the
INSTRUMENT and was read as measuring the corpus.

## The distinction being measured

The 2026-08-14 audit classified rules as NOTATION vs REPAIR. It never asked a
second question, and the project owner did:

    **What KIND of evidence does the rule use to decide?**

    TYPOGRAPHIC — reads what the renderer actually put on the page:
        W0h  a surviving `(cid:N)` glyph where the minus was
        W0m  the layout channel proves a math-symbol-font beta
        W0p  font size + baseline prove a superscript
        W0e  a PUA codepoint maps to a known glyph

    INFERENTIAL — reasons about what the NUMBERS ought to be:
        W0b  a bracketed interval is DESCENDING, so assume a corrupted minus
        W0d  the de-corrupted value falls INSIDE the reported CI, the literal
             does not, so assume a corrupted minus
        W0g  the CI "proves" a dropped sign

The inferential three apply a statistical model to decide whether to rewrite a
published number. That is the inference the downstream verification tools exist
to perform, and docpluck has no channel to announce having performed it.

## The alternative this scan tests

A PDF states, in its own metadata, whether each embedded font carries a usable
character map (`pdffonts`, the `uni` column). Measured on the two source papers:

    10.1016/j.jesp.2016.11.001   BFDKFC+AdvTT94c8263f.I   uni: no   <- the `<`-as-`b` font
    efendic_2022_affect          LGBAGA+AdvPS8E91 ...     uni: no   <- the AdvPS family

and at FONT level, via pdfplumber's per-character `fontname`, the two are not
close: in efendic the body font `AdvTimes` draws 35,682 glyphs across 86 distinct
characters, while `AdvP586B` draws 124 across 3 — `'2'` x99, `'3'` x24, `'.'` x1.
A font whose entire repertoire is `2`, `3` and `.` is the symbol face drawing
minus and multiply. **The font discriminates without any appeal to what the
statistics ought to be.**

Reproduce with `python tools/diag/symbol_font_census.py <pdf>`. This docstring
previously claimed "(64 of 68)" and "(135)", a per-TOKEN ratio nothing in this
repo produced; its replacement in `OVERHAUL_REGISTER` §G3 ("9 differ, 2 match,
no overlap") did not reproduce either — re-measured 2026-08-15 it gives 10/6 and
the font sets DO overlap. A per-token ratio depends on how tokens are enumerated
and no method was ever written down. The font census does not have that problem.

So the question this scan answers is: how big is each population?

    A. papers with at least one embedded font reporting no character map
    B. papers where an INFERENCE rule actually changes a number

If A is common and B is rare, the inference rules are carrying very little
weight and a font gate can replace them. If B is common and lands outside A,
the font signal is not sufficient and the trade-off is real.

Run:  python tools/diag/font_risk_and_inference_scan.py [--sample N]
"""

from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from docpluck.extract import extract_pdf  # noqa: E402
from docpluck.normalize import NormalizationLevel, normalize_text  # noqa: E402

_VIBE = os.environ.get("VIBE_ROOT") or str(Path.home() / "Vibe")
_REPO = Path(_VIBE) / "ArticleRepository" / "fulltext"

# The three rules that decide by statistical inference, plus the typographic
# ones for contrast. Tracked-step names, so attribution comes from the library
# rather than from a copy of each regex (one concept, one table).
_INFERENCE = ["W0b_minus_sign_recovery", "W0d_minus_ci_pairing", "W0g_dropped_minus_ci_pairing"]
_CONTEXTUAL = ["W0j_prose_minus_recovery", "W0k_prose_times_recovery", "W0l_prose_times_residuals"]
_TYPOGRAPHIC = ["W0c_lt_operator_recovery", "W0o_lt_as_b_recovery", "W0e_pua_glyph_recovery"]
_ALL = _INFERENCE + _CONTEXTUAL + _TYPOGRAPHIC


def _fonts_without_unicode(pdf: Path) -> list[str]:
    """Fonts the PDF itself declares it cannot map to Unicode (`uni` == no)."""
    try:
        out = subprocess.run(
            ["pdffonts", str(pdf)], capture_output=True, text=True, timeout=60
        ).stdout
    except Exception:  # noqa: BLE001
        return []
    bad = []
    for line in out.splitlines()[2:]:
        parts = line.split()
        # name type encoding emb sub uni objectID gen  -> `uni` is 3rd from the
        # right of the flag block; parse from the end to survive spaces in names.
        if len(parts) >= 6 and parts[-3] == "no":
            bad.append(parts[0])
    return bad


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=150)
    ap.add_argument("--seed", type=int, default=20260814)
    args = ap.parse_args()

    if not _REPO.is_dir():
        raise SystemExit(f"FATAL: article repository not found at {_REPO}")
    pdfs = sorted(_REPO.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"FATAL: no PDFs under {_REPO}")
    total_available = len(pdfs)
    rng = random.Random(args.seed)
    sample = rng.sample(pdfs, min(args.sample, len(pdfs)))

    print(f"ARTICLE REPOSITORY: {total_available} PDFs available")
    print(f"SAMPLED:            {len(sample)} (seed {args.seed})\n")

    papers_with_bad_font = 0
    bad_font_names: Counter[str] = Counter()
    rule_papers: Counter[str] = Counter()
    rule_sites: Counter[str] = Counter()
    inference_in_bad_font_paper = 0
    inference_papers: set[str] = set()
    errors = 0
    scanned = 0

    for pdf in sample:
        bad = _fonts_without_unicode(pdf)
        try:
            text, _engine = extract_pdf(pdf.read_bytes())
        except Exception:  # noqa: BLE001
            errors += 1
            continue
        if not text or text.startswith("ERROR:"):
            errors += 1
            continue
        scanned += 1
        if bad:
            papers_with_bad_font += 1
            for f in bad:
                bad_font_names[f.split("+")[-1]] += 1

        _out, report = normalize_text(text, NormalizationLevel.academic)
        fired_inference = False
        for step in _ALL:
            n = report.changes_made.get(_METRIC.get(step, ""), 0)
            if step in report.steps_changed:
                rule_papers[step] += 1
                rule_sites[step] += max(n, 1)
                if step in _INFERENCE:
                    fired_inference = True
        if fired_inference:
            inference_papers.add(pdf.stem)
            if bad:
                inference_in_bad_font_paper += 1

    print("=" * 72)
    print("A. THE RISK POPULATION — fonts the PDF itself says it cannot decode")
    print(f"   papers scanned                       {scanned}")
    print(f"   papers with >=1 undecodable font     {papers_with_bad_font}"
          f"  ({100.0 * papers_with_bad_font / max(scanned, 1):.0f}%)")
    if bad_font_names:
        print("   most common such fonts:")
        for name, n in bad_font_names.most_common(8):
            print(f"       {n:5d}  {name}")
    print()
    print("B. HOW OFTEN EACH RULE ACTUALLY CHANGES A NUMBER")
    print(f"   {'rule':34} {'papers':>7} {'sites':>7}   evidence type")
    for step in _ALL:
        kind = ("INFERENCE (statistical)" if step in _INFERENCE
                else "contextual (linguistic)" if step in _CONTEXTUAL
                else "typographic")
        print(f"   {step:34} {rule_papers[step]:7d} {rule_sites[step]:7d}   {kind}")
    print()
    print(f"   papers where an INFERENCE rule fired  {len(inference_papers)}")
    print(f"     ...of those, also had a bad font    {inference_in_bad_font_paper}")
    print()
    print("READ THIS BEFORE QUOTING THE NUMBERS:")
    print("  * A rule firing is not a rule being RIGHT. Every site needs the page")
    print("    rasterized before anyone calls it a correct repair.")
    print("  * `uni: no` means the font declares no character map. It is a RISK")
    print("    marker, not proof any particular token is corrupt.")
    if errors:
        print(f"  * {errors} paper(s) failed to extract and are excluded.")
    return 0


# Tracked-step -> the metric key it increments, so site counts come from the
# library's own report rather than from a re-implemented pattern.
_METRIC = {
    "W0b_minus_sign_recovery": "minus_signs_recovered",
    "W0d_minus_ci_pairing": "minus_signs_recovered",
    "W0g_dropped_minus_ci_pairing": "dropped_minus_recovered",
    "W0j_prose_minus_recovery": "minus_signs_recovered",
    "W0k_prose_times_recovery": "times_glyphs_recovered",
    "W0l_prose_times_residuals": "times_glyphs_recovered",
    "W0c_lt_operator_recovery": "lt_operators_recovered",
    "W0o_lt_as_b_recovery": "lt_operators_recovered",
    "W0e_pua_glyph_recovery": "pua_glyphs_recovered",
}


if __name__ == "__main__":
    raise SystemExit(main())
