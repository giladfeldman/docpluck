"""What does the 2026-10-30 W0p change do, site by site?

W0p (``normalize.recover_superscript_via_layout``) marks a layout-proven superscript
fused into a number (`2,5801` -> `2,580^1`). The change: (1) a marker may open with a
raised sign (`10` + raised `–3` -> `10^-3`); (2) a site must be a whole token on the
page the glyphs were seen on (it used to be the first bare-substring hit anywhere).

Per corpus paper: run ``normalize_text`` with the layout, capture W0p's INPUT text,
then apply both the shipped rule (arm A) and the pre-change rule (arm B, reconstructed
below: digit-only markers, first substring hit in the whole text) to that same input,
and print every line that differs. A SCREEN: each differing site still has to be read
against its page.

Usage:  python tools/diag/w0p_page_bound_diff.py [--limit N | --sample N] [--workers N]
"""

from __future__ import annotations

import argparse
import difflib
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.diag._corpus import baseline_corpus, coverage_line, sampled_corpus  # noqa: E402


def _arm_b(text: str, layout) -> str:
    """The rule as shipped before 2026-10-30."""
    from docpluck.normalize import _W0P_SIGNS, _layout_superscript_fusions

    for _page, fused, repaired in _layout_superscript_fusions(layout):
        if any(ch in fused for ch in _W0P_SIGNS):
            continue  # sign-opened markers did not exist
        if text.count(fused):
            text = text.replace(fused, repaired, 1)
    return text


def _run(item: tuple[str, str]) -> tuple[str, list[str]]:
    key, path = item
    import warnings
    warnings.filterwarnings("ignore")
    import docpluck.normalize as N
    from docpluck import extract_pdf
    from docpluck.extract_layout import extract_pdf_layout

    pdf = Path(path).read_bytes()
    try:
        text, _ = extract_pdf(pdf)
        layout = extract_pdf_layout(pdf)
    except Exception as exc:  # noqa: BLE001
        return key, [f"ERROR {type(exc).__name__}: {exc}"]
    seen: list[str] = []
    orig = N.recover_superscript_via_layout

    def hook(t, lay):
        seen.append(t)
        return orig(t, lay)

    N.recover_superscript_via_layout = hook
    try:
        N.normalize_text(text, N.NormalizationLevel.academic, dropped_minus_layout=layout)
    except Exception as exc:  # noqa: BLE001
        return key, [f"ERROR normalize {type(exc).__name__}: {exc}"]
    finally:
        N.recover_superscript_via_layout = orig
    if not seen:
        return key, ["W0p NOT REACHED"]
    inp = seen[0]
    a, b = orig(inp, layout), _arm_b(inp, layout)
    if a == b:
        return key, []
    out = []
    for ln in difflib.unified_diff(b.splitlines(), a.splitlines(), lineterm="", n=0):
        if ln.startswith(("---", "+++", "@@")):
            continue
        out.append("  " + ln[:200])
    return key, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sample", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    corpus = sampled_corpus(args.sample) if args.sample else baseline_corpus(args.limit)
    print(coverage_line())
    n = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for key, lines in ex.map(_run, [(k, str(p)) for k, p in corpus]):
            if lines:
                n += 1
                print(key)
                for ln in lines:
                    print(ln)
                sys.stdout.flush()
    print(f"papers={len(corpus)} differing={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
