"""What does the 2026-10-30 W0p change do, site by site?

W0p (``normalize.recover_superscript_via_layout``) marks a layout-proven superscript
fused into a number (`2,5801` -> `2,580^1`). The change: (1) a marker may open with a
raised sign (`10` + raised `–3` -> `10^-3`); (2) a site must be a whole token on the
page the glyphs were seen on (it used to be the first bare-substring hit anywhere).

Per corpus paper: run ``normalize_text`` with the layout, capture W0p's INPUT text,
then apply both the shipped rule (arm A) and the pre-change rule (arm B, the function
as committed at ``_ARM_B_COMMIT``, loaded from git) to that same input, and print every
line that differs (each line cut to 200 characters; a long line can hide a second site,
so read the page, not only the printed excerpt). A SCREEN: each differing site still has to be read
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


# The last commit before the 2026-10-30 change. Arm B is that commit's own
# ``recover_superscript_via_layout`` loaded from git, not a reconstruction: a
# reconstruction built on today's detector inherits today's new branches (word
# markers, consult 2026-10-31) and reports them as "no change".
_ARM_B_COMMIT = "11da59a"
_ARM_B_FN = None


def _arm_b(text: str, layout) -> str:
    """The rule as shipped at ``_ARM_B_COMMIT``."""
    global _ARM_B_FN
    if _ARM_B_FN is None:
        import subprocess
        import types
        root = Path(__file__).resolve().parents[2]
        src = subprocess.run(["git", "show", f"{_ARM_B_COMMIT}:docpluck/normalize.py"],
                             cwd=root, capture_output=True, text=True, encoding="utf-8",
                             check=True).stdout
        mod = types.ModuleType("docpluck._normalize_arm_b")
        mod.__package__ = "docpluck"
        sys.modules[mod.__name__] = mod  # dataclasses look their module up here
        exec(compile(src, f"normalize@{_ARM_B_COMMIT}", "exec"), mod.__dict__)
        _ARM_B_FN = mod.recover_superscript_via_layout
    return _ARM_B_FN(text, layout)


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
    sys.stdout.reconfigure(encoding="utf-8")  # page text holds ligatures (U+FB03)
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
