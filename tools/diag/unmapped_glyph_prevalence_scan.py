"""How often does the table backend hand docpluck a glyph it could not decode?

Backlog row: todo.md W-0015.
Findings:    docs/FINDINGS_2026-09-02_table_channel_destroys_minus_signs.md

W0r (`cell_cleaning.recover_unmapped_glyph_minus`) was justified from ONE paper --
`10.1016/j.joep.2020.102350`, 22 destroyed minus signs, every one checked against the
rasterized page. That establishes the SHAPE IS REAL and says NOTHING about the rate,
and this project has been wrong in both directions on exactly that distinction: W0o was
built for one paper and turned out to fire in 10.5% of a 200-paper sample, while
W0b/W0d/W0g were built for one paper and fire 0 times in 226. So measure the
denominator separately.

WHAT IS MEASURED, AND WHY AT THIS LAYER. Camelot 2.0.0 reads text through
`playa.miner`, so this scan decodes each PDF with **playa itself** -- the same library,
the same decoder, the same failure. That is 1s per paper against ~60s for a full render,
which is what makes a real denominator affordable at all. It measures the SOURCE rate:
how often the backend emits an undecodable glyph anywhere in a document. The rate at
which the defect actually SHIPS is necessarily lower (only a glyph inside a captured
table cell reaches a `<td>`), and that half is measured by
`tools/diag/unmapped_minus_guard_diff.py` over the render corpus.

Three counts are kept DISTINCT, because they license different conclusions:

    before-a-digit    the repairable class. In these AdvTT-family stat tables the
                      code-0 slot draws U+2212, so `\x00 31` is -31. TYPOGRAPHIC
                      evidence -- what the renderer emitted for one character.
    not-before-a-digit  the RESIDUAL. Its glyph is unknown and W0r deliberately leaves
                      it alone. This number is the honest size of what is still
                      unrecovered, and it is the one to watch: if it is large, a
                      second rule may be warranted; if it is ~0, the repair covers the
                      class.
    U+FFFD            the other spelling of "undecodable". Reported so the open
                      question "does U+FFFD reach the same slot" has an answer with a
                      number attached instead of a presumption.

A ZERO IS A CLAIM ABOUT THE INSTRUMENT. The known positive is scanned FIRST and must
fire; if it does not, the decoder is not seeing what Camelot sees and every other zero
in the run is uninterpretable, so the scan says so and exits non-zero.

Usage:
    python tools/diag/unmapped_glyph_prevalence_scan.py                # 200-paper sample
    python tools/diag/unmapped_glyph_prevalence_scan.py --sample 400
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

# W-0011: without this insert, `import docpluck` in a tools/ script resolves to the
# INSTALLED release and every number printed would describe site-packages, not the tree.
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

import docpluck  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _corpus import coverage_line, sampled_corpus  # noqa: E402

# The known positive: 22 destroyed minus signs in the shipped markdown, every one
# verified against the page at 200dpi on 2026-09-02.
KNOWN_POSITIVE_DOI = "10.1016/j.joep.2020.102350"

NUL = "\x00"
_BEFORE_DIGIT_RE = re.compile(r"(?:\(cid:0\)|\x00)\s*(?=\d)")
_ANY_UNMAPPED_RE = re.compile(r"\(cid:\d+\)|\x00|�")


def _banner() -> None:
    print("docpluck module :", docpluck.__file__)
    if _REPO.lower() not in os.path.abspath(docpluck.__file__).lower():
        print("!! REFUSING: docpluck did not resolve to the working tree (W-0011).")
        raise SystemExit(2)
    print("docpluck version:", docpluck.__version__)
    try:
        import playa

        print("playa           :", getattr(playa, "__version__", "?"), "(Camelot 2.0's text backend)")
    except ImportError:
        print("!! REFUSING: playa is not importable, so this scan cannot see what Camelot sees.")
        raise SystemExit(2)
    print()


def _decode(path: str) -> str:
    import playa

    with playa.open(path) as doc:
        return "".join(
            (pg.extract_text() or "") if hasattr(pg, "extract_text") else ""
            for pg in doc.pages
        )


def _counts(text: str) -> tuple[int, int, int, int]:
    """(repairable, residual NUL/cid, U+FFFD, total unmapped markers)."""
    repairable = len(_BEFORE_DIGIT_RE.findall(text))
    nul_or_cid = text.count(NUL) + len(re.findall(r"\(cid:\d+\)", text))
    fffd = text.count("�")
    return repairable, nul_or_cid - repairable, fffd, len(_ANY_UNMAPPED_RE.findall(text))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20260813)
    args = ap.parse_args()

    _banner()

    # ── the known positive, FIRST ────────────────────────────────────────────
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _corpus import _find_pdf  # noqa: E402  (same custodian lookup, no glob)

    kp = _find_pdf(KNOWN_POSITIVE_DOI.replace("/", "__"))
    if kp is None:
        print(f"!! REFUSING: the known positive {KNOWN_POSITIVE_DOI} is not on this "
              "machine, so a zero anywhere below could not be distinguished from a "
              "broken decoder.")
        return 2
    kp_rep, kp_res, kp_fffd, _ = _counts(_decode(str(kp)))
    print(f"KNOWN POSITIVE {KNOWN_POSITIVE_DOI}: repairable={kp_rep} residual={kp_res} "
          f"U+FFFD={kp_fffd}")
    if kp_rep == 0:
        print("!! REFUSING: the known positive did not fire. The decoder is not seeing "
              "what Camelot sees; every zero below would be uninterpretable.")
        return 2
    print("   the instrument fires on a case verified against the rasterized page.\n")

    papers = sampled_corpus(args.sample, seed=args.seed)
    print(coverage_line())
    print()

    n_repairable = n_residual = n_fffd = 0
    papers_repairable: list[tuple[str, int]] = []
    papers_residual: list[tuple[str, int]] = []
    papers_fffd: list[tuple[str, int]] = []
    failed = 0
    t0 = time.time()

    for doi, path in papers:
        try:
            rep, res, fffd, _ = _counts(_decode(str(path)))
        except Exception as exc:  # a decode failure is NOT a zero
            failed += 1
            print(f"  DECODE FAILED {doi}: {type(exc).__name__}")
            continue
        n_repairable += rep
        n_residual += res
        n_fffd += fffd
        if rep:
            papers_repairable.append((doi, rep))
        if res:
            papers_residual.append((doi, res))
        if fffd:
            papers_fffd.append((doi, fffd))

    n = len(papers) - failed
    print(f"\npapers decoded                        : {n}  (decode failures: {failed})")
    print(f"elapsed                               : {time.time() - t0:.0f}s")
    print()
    print("REPAIRABLE — an unmapped glyph directly before a digit (what W0r recovers)")
    print(f"  papers affected : {len(papers_repairable)} / {n} "
          f"({100.0 * len(papers_repairable) / n:.1f}%)" if n else "")
    print(f"  sites total     : {n_repairable}")
    for doi, c in sorted(papers_repairable, key=lambda x: -x[1])[:25]:
        print(f"      {c:>5}  {doi}")
    if len(papers_repairable) > 25:
        print(f"      ... and {len(papers_repairable) - 25} more papers")
    print()
    print("RESIDUAL — an unmapped glyph NOT before a digit (W0r deliberately leaves it)")
    print(f"  papers affected : {len(papers_residual)} / {n}")
    print(f"  sites total     : {n_residual}")
    for doi, c in sorted(papers_residual, key=lambda x: -x[1])[:15]:
        print(f"      {c:>5}  {doi}")
    print()
    print("U+FFFD — the other spelling of 'undecodable'")
    print(f"  papers affected : {len(papers_fffd)} / {n}")
    print(f"  sites total     : {n_fffd}")
    for doi, c in sorted(papers_fffd, key=lambda x: -x[1])[:15]:
        print(f"      {c:>5}  {doi}")
    print()
    print("NOTE: this is the SOURCE rate — how often the backend emits an undecodable "
          "glyph anywhere in a document. The rate at which the defect SHIPS is lower "
          "(only a glyph inside a captured table cell reaches a <td>); that half is "
          "measured by tools/diag/unmapped_minus_guard_diff.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
