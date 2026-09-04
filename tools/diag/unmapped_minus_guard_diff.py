"""What does the W0r unmapped-glyph-minus repair actually change, corpus-wide?

Backlog row: todo.md W-0015.
Findings:    docs/FINDINGS_2026-09-02_table_channel_destroys_minus_signs.md

W0r (`cell_cleaning.recover_unmapped_glyph_minus`) recovers a minus the table backend
could not map to Unicode, in BOTH of the spellings the two readers produce -- the
literal ``(cid:0)`` (pdfminer.six) and the raw NUL (playa, via Camelot 2.0). It changes
SIGNS in the table channel, and this project's history says a sign-changing edit does
not ship on one paper's evidence. So: render every corpus paper TWICE in one process --

    arm A   the shipped code
    arm B   `recover_unmapped_glyph_minus` neutralised to the identity function

-- and diff the two markdown outputs line by line, so every difference in the corpus is
attributable to this one repair and nothing else.

WHAT COUNTS AS EXPECTED. The repair rewrites a NUL (or ``(cid:0)``) that sits directly
before a digit into an ASCII hyphen, and touches nothing else. So an EXPECTED difference
is one where arm-B's line becomes arm-A's line under exactly that substitution. Anything
else -- a line that appears, a line that vanishes, a line whose text changed some other
way -- is FLAGGED and printed in full, because the one way this repair could do harm is
by changing what a capture GATE judges: the validity predicates in `whitespace.py` score
the REPAIRED view of a cell, and a cell that was unreadable garbage (``\x00 31``) becomes
clean data (``-31``), which can flip a grid from rejected to accepted. That is probably
an improvement, but it is a table appearing or disappearing and it must be looked at, not
assumed.

A ZERO IS A CLAIM ABOUT THE INSTRUMENT. If no paper differs between the arms, the two
arms are the same code and the scan measured nothing -- so it says so and exits non-zero
rather than printing a clean-looking PASS.

Usage:
    python tools/diag/unmapped_minus_guard_diff.py                 # baseline corpus
    python tools/diag/unmapped_minus_guard_diff.py --limit 5       # a quick pass
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
import time

# W-0011: Python puts THIS FILE'S directory on sys.path[0], never the cwd. Without the
# insert below, `import docpluck` in a tools/ script resolves to the INSTALLED release
# and every number this script prints would describe site-packages, not the tree.
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

import docpluck  # noqa: E402
from docpluck.tables import cell_cleaning  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _corpus import baseline_corpus, coverage_line  # noqa: E402

NUL = "\x00"
# The substitution the repair performs, applied to arm B so an EXPECTED difference can
# be recognised without re-implementing the rule's placeholder protection: arm B's
# markdown is past the HTML emitter, so docpluck's own `\x00BR\x00` placeholders have
# already become `<br>` and every NUL still present is an unmapped glyph.
_EXPECTED_SUB_RE = re.compile(r"(?:\(cid:0\)|\x00)\s*(?=\d)")


def _banner() -> None:
    print("docpluck module:", docpluck.__file__)
    if _REPO.lower() not in os.path.abspath(docpluck.__file__).lower():
        print("!! REFUSING: docpluck did not resolve to the working tree (W-0011).")
        raise SystemExit(2)
    print("docpluck version:", docpluck.__version__)
    print()


def _render(pdf_bytes: bytes) -> str:
    from docpluck.render import render_pdf_to_markdown

    md = render_pdf_to_markdown(pdf_bytes)
    return md[0] if isinstance(md, tuple) else md


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    _banner()
    papers = baseline_corpus(limit=args.limit)
    print(coverage_line())
    print()

    shipped = cell_cleaning.recover_unmapped_glyph_minus
    arms_differ = 0
    total_nul_b = 0
    total_expected = 0
    flagged: list[tuple[str, str, str]] = []
    affected: list[tuple[str, int]] = []

    for key, path in papers:
        data = open(path, "rb").read()
        t0 = time.time()
        md_a = _render(data)
        cell_cleaning.recover_unmapped_glyph_minus = lambda s: s
        try:
            md_b = _render(data)
        finally:
            cell_cleaning.recover_unmapped_glyph_minus = shipped

        nul_b = md_b.count(NUL) + md_b.count("(cid:0)")
        nul_a = md_a.count(NUL) + md_a.count("(cid:0)")
        total_nul_b += nul_b
        same = md_a == md_b
        if not same:
            arms_differ += 1
        if nul_b:
            affected.append((key, nul_b))

        a_lines = md_a.splitlines()
        b_lines = md_b.splitlines()
        paper_flags = 0
        paper_expected = 0
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(
            a=b_lines, b=a_lines, autojunk=False
        ).get_opcodes():
            if op == "equal":
                continue
            if op == "replace" and (i2 - i1) == (j2 - j1):
                for bl, al in zip(b_lines[i1:i2], a_lines[j1:j2]):
                    if _EXPECTED_SUB_RE.sub("-", bl) == al:
                        paper_expected += 1
                    else:
                        paper_flags += 1
                        flagged.append((key, bl, al))
                continue
            for bl in b_lines[i1:i2]:
                paper_flags += 1
                flagged.append((key, bl, "<<line only in arm B (repair OFF)>>"))
            for al in a_lines[j1:j2]:
                paper_flags += 1
                flagged.append((key, "<<line only in arm A (repair ON)>>", al))

        total_expected += paper_expected
        print(
            f"  {key:<44} NUL off={nul_b:<4} on={nul_a:<4} "
            f"lines: expected={paper_expected:<4} FLAGGED={paper_flags:<4} "
            f"{'same' if same else 'differ'}  {time.time() - t0:5.1f}s"
        )

    print()
    print(f"papers                       : {len(papers)}")
    print(f"papers whose arms differ     : {arms_differ}")
    print(f"papers carrying an unmapped glyph in the SHIPPED markdown with the repair OFF:")
    for key, n in affected:
        print(f"    {key}  {n}")
    print(f"unmapped-glyph sites, repair OFF, total : {total_nul_b}")
    print(f"lines changed EXACTLY as the rule predicts: {total_expected}")
    print(f"lines FLAGGED for a human to look at      : {len(flagged)}")
    for key, bl, al in flagged[:60]:
        print(f"  [{key}]")
        print(f"    OFF: {bl[:160]!r}")
        print(f"    ON : {al[:160]!r}")
    if len(flagged) > 60:
        print(f"  ... and {len(flagged) - 60} more")

    print()
    if arms_differ == 0:
        print(
            "VERDICT: INSTRUMENT FAILURE - no paper differed between the arms, so the "
            "two arms ran the same code and this scan measured nothing. A corpus with "
            "no known positive cannot speak to a repair's blast radius."
        )
        return 2
    if flagged:
        print(f"VERDICT: FLAGGED - {len(flagged)} line(s) changed in a way the rule does "
              "not predict. Go and look; do not read this as a regression on its own.")
        return 1
    print("VERDICT: CLEAN - every corpus difference is exactly the substitution the "
          "rule describes, and nothing else moved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
