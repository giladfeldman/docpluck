"""Reproduce BOTH sign defects in the `<td>` table channel, in one run, no PDF needed.

Findings doc: docs/FINDINGS_2026-09-02_table_channel_sign_defects.md
Backlog row:  todo.md W-0016

The channel UNDER-SIGNS and OVER-SIGNS at once, by two independent mechanisms:

  FABRICATION  W0q `recover_dropped_minus_ci_upper` invents a minus that is not on the
               page. It decides on CENTRING ARITHMETIC alone -- no glyph evidence -- so
               it cannot distinguish "docpluck dropped a minus" from "the author typed
               the wrong sign". On 10.1080/02699931.2024.2434156 p13 Table 9 it silently
               corrects the AUTHORS' typo (Table 8 on the same page proves it is a typo).

  DESTRUCTION  the `(cid:0)` repair in cell_cleaning.py matches a literal 7-character
               string. Camelot now emits a raw NUL, so it never fires. docpluck DELETES
               NOTHING -- it ships the NUL verbatim into the <td>, and the loss happens
               in the consumer, whose `-?\\d*\\.?\\d+` reads "\\x0031" as "31".

They are NOT coupled: a NUL inside the bracket makes `_CI_BRACKET_CELL_RE` fail, so W0q
cannot fire on a NUL-corrupted CI. Section D tests that rather than asserting it.

Every section is TWO-SIDED -- a control that must fire sits beside the shape that must
not, so a silent "nothing happens" cannot be mistaken for a clean result.

Run:  py -3 tools/diag/table_channel_sign_census.py
"""

from __future__ import annotations

import os
import re
import sys

# W-0011: Python puts THIS FILE'S directory on sys.path[0], never the cwd. Without the
# insert below, `import docpluck` in a tools/ script resolves to the INSTALLED release
# and every number this script prints would describe site-packages, not the tree. That
# exact bug made 17 harness scripts audit the wrong library for weeks.
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

import docpluck  # noqa: E402
from docpluck.normalize import (  # noqa: E402
    NORMALIZATION_VERSION,
    recover_dropped_minus_ci_upper,
    recover_dropped_minus_ci_upper_in_text,
)
from docpluck.tables.cell_cleaning import (  # noqa: E402
    _MERGE_SEPARATOR,
    _recover_ci_upper_in_grid_row,
    cells_grid_to_html,
    clean_cell_text,
)

NUL = "\x00"


def _banner() -> None:
    print("docpluck module      :", docpluck.__file__)
    print("NORMALIZATION_VERSION:", NORMALIZATION_VERSION)
    if _REPO.lower() not in os.path.abspath(docpluck.__file__).lower():
        print("!! REFUSING: docpluck did not resolve to the working tree (W-0011).")
        raise SystemExit(2)
    print()


def section_a() -> None:
    print("=== A. FABRICATION - the arithmetic, and the controls that must NOT fire ===")
    print("    10.1080/02699931.2024.2434156 p13 Table 9 row 2bii prints")
    print("      r = -.43   [-0.52, 0.33]      <- the AUTHORS' typo; Table 8 has it right")
    est, lo, hi = -0.43, -0.52, 0.33
    got = recover_dropped_minus_ci_upper(est, lo, hi)
    print("    recover_dropped_minus_ci_upper(%.2f, %.2f, %.2f) -> %r  %s"
          % (est, lo, hi, got, "FIRES - fabricates" if got is not None else "silent"))
    pmid, phalf = (lo + hi) / 2.0, (hi - lo) / 2.0
    fhi = -hi
    fmid, fhalf = (lo + fhi) / 2.0, (fhi - lo) / 2.0
    print("      parsed  [%.2f, %.2f] mid %+.4f half %.4f  off-centre %.3f"
          % (lo, hi, pmid, phalf, abs(est - pmid) / phalf))
    print("      flipped [%.2f, %.2f] mid %+.4f half %.4f  off-centre %.3f"
          % (lo, fhi, fmid, fhalf, abs(est - fmid) / fhalf))
    print("      gate: parsed > 0.5 AND flipped < 0.5")
    print("      NOTE: %+.2f IS inside [%.2f, %.2f] - there is NO contradiction to resolve."
          % (est, lo, hi))
    print("    CONTROLS (each must return None):")
    for e2, l2, h2, why in [
        (-0.05, -0.52, 0.33, "estimate near the parsed centre"),
        (-0.43, -0.52, 0.50, "genuinely wide zero-straddling CI"),
        (0.43, -0.52, 0.33, "positive estimate"),
    ]:
        r = recover_dropped_minus_ci_upper(e2, l2, h2)
        print("      est %+.2f [%.2f, %.2f] -> %-6r %s  (%s)"
              % (e2, l2, h2, r, "ok" if r is None else "<-- UNEXPECTED FIRE", why))
    print()


def section_b() -> None:
    print("=== B. FABRICATION reaches BOTH shipped table surfaces ===")
    for s in ("r = -.43 [-0.52, 0.33]", "r = -.43, 95% CI [-0.52, 0.33]"):
        print("    text surface %-34r -> %r" % (s, recover_dropped_minus_ci_upper_in_text(s)))
    row = ["2bii", "r = -.43", "[-0.52, 0.33]"]
    print("    grid surface %-34r -> %r" % (row, _recover_ci_upper_in_grid_row(list(row))))
    print()


def section_c() -> None:
    print("=== C. DESTRUCTION - does the (cid:0) repair reach a raw NUL? ===")
    for raw, label in [
        ("(cid:0)0.33", "legacy form the repair WAS written for"),
        ("(cid:0) 31", "the docstring's own worked example"),
        (NUL + "0.33", "what Camelot emits NOW (raw NUL)"),
        (NUL + " 31", "raw NUL, spaced"),
        ("−0.33", "a real U+2212 minus (control)"),
        ("-0.33", "a plain ASCII minus (control)"),
    ]:
        print("    %-22r -> %-14r  %s" % (raw, clean_cell_text(raw), label))
    print()
    print("    d4's row: p4 Table 2 prints  199 -1 -31 -30 213 14 31 17")
    row = ["199", NUL + "1", NUL + "31", NUL + "30", "213", "14", "31", "17"]
    print("      in :", row)
    print("      out:", [clean_cell_text(c) for c in row])
    print()


def section_d() -> None:
    print("=== D. ARE THEY COUPLED? feed a DESTROYED bound to the inferential rule ===")
    print("    (if the NUL blocks the bracket regex, W0q cannot fire -> NOT coupled)")
    for label, row in [
        ("destroyed hi only  ", ["r = -.43", "[-0.52, " + NUL + "0.33]"]),
        ("destroyed lo and hi", ["r = -.43", "[" + NUL + "0.52, " + NUL + "0.33]"]),
        ("destroyed estimate ", ["r = " + NUL + ".43", "[-0.52, -0.33]"]),
    ]:
        cleaned = [clean_cell_text(c) for c in row]
        final = _recover_ci_upper_in_grid_row(list(cleaned))
        print("    %s -> %r  %s"
              % (label, final, "unchanged (W0q inert)" if final == cleaned else "<-- CHANGED"))
    print()


def section_e() -> None:
    print("=== E. END-TO-END through cells_grid_to_html ===")
    for title, grid in [
        ("FABRICATION", [["row", "r", "95% CI"], ["2bii", "r = -.43", "[-0.52, 0.33]"]]),
        ("DESTRUCTION", [["N", "d1", "d2", "u1"], ["199", NUL + "1", NUL + "31", "17"]]),
        ("CONTROL (cid:0)", [["N", "d1", "d2", "u1"], ["199", "(cid:0)1", "(cid:0)31", "17"]]),
    ]:
        html = cells_grid_to_html(grid)
        cells = [l.strip() for l in html.split("\n") if "<td>" in l]
        print("    %-16s %s" % (title, cells))
        print("    %-16s NUL present in output HTML: %s" % ("", NUL in html))
    print()


def section_f() -> None:
    print("=== F. WHY THE OBVIOUS FIX IS WORSE THAN THE DEFECT ===")
    print("    _MERGE_SEPARATOR =", repr(_MERGE_SEPARATOR))
    naive = lambda s: re.sub(NUL + r"\s*(?=\d)", "-", s)  # noqa: E731
    cell = "Age" + _MERGE_SEPARATOR + "31"
    after = naive(cell)
    print("    naive %r -> %r" % (cell, after))
    print("      fold sentinel intact: %s | minus injected into a header that printed none: %s"
          % (_MERGE_SEPARATOR in after, "-" in after and "-" not in cell))
    ok = [l.strip() for l in cells_grid_to_html([["Group", cell], ["A", "12"]]).split("\n")
          if "<th>" in l]
    bad = [l.strip() for l in cells_grid_to_html([["Group", after], ["A", "12"]]).split("\n")
           if "<th>" in l]
    print("      correct today  :", ok)
    print("      after naive fix:", bad)
    print("    => data LOSS converted into data FABRICATION. Any NUL handling must be")
    print("       sentinel-aware. See findings doc section 7.")
    print()


def section_g() -> None:
    print("=== G. THE PREVALENCE GAP - 4 call sites, 1 counter ===")
    sites = [
        ("docpluck/normalize.py", "recover_dropped_minus_ci_upper_in_text(t, _w0q_n)", "text", True),
        ("docpluck/tables/cell_cleaning.py", "recover_dropped_minus_ci_upper_in_text(s)", "table cell", False),
        ("docpluck/tables/cell_cleaning.py", "recover_dropped_minus_ci_upper(est, lo, hi)", "table grid", False),
        ("docpluck/tables/flatten.py", "recover_dropped_minus_ci_upper(", "flatten", False),
    ]
    for path, needle, chan, counted in sites:
        full = os.path.join(_REPO, path)
        hits = 0
        if os.path.exists(full):
            with open(full, encoding="utf-8") as fh:
                hits = sum(1 for line in fh if needle in line and "def " not in line)
        print("    %-36s %-12s counted=%-5s present=%s" % (path, chan, counted, hits > 0))
    print("    => any 'W0q fires N times' figure counted at most ONE of four call sites.")
    print("       Prevalence is UNKNOWN, not low. Instrument the three, then sample a corpus.")
    print()


if __name__ == "__main__":
    _banner()
    section_a()
    section_b()
    section_c()
    section_d()
    section_e()
    section_f()
    section_g()
