#!/usr/bin/env python3
"""The authoritative instrument for TEXT LOSS between two renders of the same input.

WHY THIS EXISTS, and why the obvious instruments do not work
------------------------------------------------------------
On 2026-08-28 a normalization change deleted an article's title on
`10.1001/jamanetworkopen.2023.39337` -- the title line vanished in all ELEVEN of
its occurrences -- and three separate gates reported green, each blind for a
DIFFERENT reason:

  * the idempotency test is structurally blind: ``normalize(normalize(x)) ==
    normalize(x)`` holds PERFECTLY when pass 1 deletes something and pass 2 finds
    nothing left to delete. It passes BECAUSE of the deletion, so re-running it
    can never help;
  * the canary audited papers none of which carried the signature;
  * and every COUNT-BASED comparison is blind by construction -- a character
    delta scores page-furniture removal and real data loss IDENTICALLY.

Three weaker instruments were built and rejected first (docpluck-77, measured):

  1. a line-multiset diff reports a RE-WRAP as a deletion. It false-flagged two
     intact reference lines whose wrap point moved;
  2. a whole-line substring test fails the same way once the wrap moves past the
     compared prefix;
  3. a character-count delta cannot distinguish loss from furniture removal.

WHAT ACTUALLY WORKS -- and it is TWO arms, because they catch different failures
--------------------------------------------------------------------------------
ARM A -- a WORD-LEVEL diff of the whitespace-collapsed full text.
    Collapsing every run of whitespace (newlines included) to a single space
    BEFORE tokenising is the entire trick: a re-wrap changes line boundaries and
    not the word sequence, so it produces a zero diff. That is precisely the
    false positive that killed instruments 1 and 2.

ARM B -- a line going from >= MIN_COPIES occurrences to ZERO.
    Needed IN ADDITION, because a deleted title is not "statistical content": the
    span audit files it under non-statistical, and only this arm names it. The
    threshold keys on the OCCURRENCE COUNT (11 -> 0 on the JAMA paper), which is
    why it is a count of copies and not a length.

Both arms must report zero. Either firing is a loss.

USAGE
-----
    python tools/diag/text_loss_differential.py --before <file|dir> --after <file|dir>
    python tools/diag/text_loss_differential.py --before a.md --after b.md --json

Exit 0 = no loss. Exit 1 = loss detected. Exit 2 = usage/setup error, INCLUDING an
empty or unreadable input -- a green computed from nothing is the false green this
whole tool exists to prevent.

NOTE ON SCOPE. This compares two RENDERS. It does not know which is correct; it
reports what the second lost relative to the first. Run it with the reference
render as ``--before``.
"""

from __future__ import annotations

import argparse
import collections
import difflib
import json
import os
import re
import sys

# Reuse docpluck's own predicate rather than restating it. ONE CONCEPT, ONE TABLE:
# a second copy of "what counts as a published quantity" would drift from the one
# every content-removing post-processor already consults.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)) if os.path.basename(
    os.path.dirname(_HERE)) == "tools" else os.path.dirname(os.path.dirname(_HERE)))
try:
    from docpluck.render import _carries_statistical_content  # type: ignore
except Exception:  # pragma: no cover - exercised only when run outside the repo
    _carries_statistical_content = None  # type: ignore

# A line must appear at least this many times before ARM B will treat its total
# disappearance as a loss. Below it, a line vanishing is ordinary editing rather
# than the all-copies-gone signature. 5 is docpluck-77's measured value.
MIN_COPIES = 5

# ARM A ignores deleted spans shorter than this many words. A one- or two-word
# deletion is usually furniture (a page number, a folio) and reporting it drowns
# the signal. The sabotage control below is caught at 12 words.
MIN_SPAN_WORDS = 3

_WS = re.compile(r"\s+")


def collapse(text: str) -> list[str]:
    """Whitespace-collapsed word sequence. This is what makes a re-wrap invisible."""
    return _WS.sub(" ", text).strip().split(" ") if text.strip() else []


def line_counts(text: str) -> collections.Counter:
    return collections.Counter(
        ln.strip() for ln in text.splitlines() if ln.strip()
    )


def arm_a_deleted_spans(before: str, after: str) -> list[dict]:
    """Word-level diff -> the spans present in `before` and absent from `after`."""
    wb, wa = collapse(before), collapse(after)
    sm = difflib.SequenceMatcher(a=wb, b=wa, autojunk=False)
    out = []
    for tag, i1, i2, _j1, _j2 in sm.get_opcodes():
        if tag not in ("delete", "replace"):
            continue
        span = wb[i1:i2]
        if len(span) < MIN_SPAN_WORDS:
            continue
        joined = " ".join(span)
        carries = bool(_carries_statistical_content(joined)) if _carries_statistical_content else None
        out.append({
            "words": len(span),
            "carries_statistical_content": carries,
            "excerpt": joined[:300],
        })
    return out


def arm_b_all_copies_gone(before: str, after: str) -> list[dict]:
    """Lines that went from >= MIN_COPIES occurrences to ZERO *and are truly absent*.

    THE SECOND CLAUSE IS LOAD-BEARING, and my own controls are what found it. A
    naive "no longer present as a line" test re-creates instrument 1's defect
    exactly: re-wrapping the document at a different width merges a standalone
    line into a paragraph, so its LINE count drops to zero while every word of it
    is still there. Measured 2026-08-28 on the JAMA render: an unguarded arm B
    reported 8 false losses on a pure re-wrap, including `<tr>` (70x) and the
    running head (10x), with nothing deleted at all.

    So a candidate is only a loss when its CONTENT has left the whitespace-
    collapsed text entirely -- which is arm A's insight applied to arm B.
    """
    cb, ca = line_counts(before), line_counts(after)
    after_collapsed = " " + _WS.sub(" ", after).strip() + " "
    out = []
    for line, n in cb.items():
        if n < MIN_COPIES or ca.get(line, 0) != 0:
            continue
        needle = _WS.sub(" ", line).strip()
        if needle and needle in after_collapsed:
            continue  # re-wrapped, not removed
        out.append({"occurrences_before": n, "excerpt": line[:300]})
    return sorted(out, key=lambda r: -r["occurrences_before"])


def _read(path: str) -> dict[str, str]:
    if os.path.isfile(path):
        return {os.path.basename(path): open(path, encoding="utf-8", errors="replace").read()}
    out = {}
    for name in sorted(os.listdir(path)):
        if name.lower().endswith((".md", ".txt")):
            full = os.path.join(path, name)
            if os.path.isfile(full):
                out[name] = open(full, encoding="utf-8", errors="replace").read()
    return out


def compare(before: str, after: str) -> dict:
    spans = arm_a_deleted_spans(before, after)
    gone = arm_b_all_copies_gone(before, after)
    return {
        "arm_a_deleted_spans": spans,
        "arm_a_spans_carrying_statistics": [s for s in spans if s["carries_statistical_content"]],
        "arm_b_all_copies_gone": gone,
        "loss": bool(spans or gone),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--before", required=True, help="reference render (file or dir)")
    ap.add_argument("--after", required=True, help="render under test (file or dir)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    for p in (a.before, a.after):
        if not os.path.exists(p):
            print(f"text_loss_differential: no such path: {p}", file=sys.stderr)
            return 2

    # Two single FILES are compared directly, whatever they are called. Matching
    # them by basename made the tool report "nothing was compared" for the most
    # common invocation of all -- caught by its own controls, 2026-08-28.
    if os.path.isfile(a.before) and os.path.isfile(a.after):
        key = f"{os.path.basename(a.before)} -> {os.path.basename(a.after)}"
        b_texts = {key: open(a.before, encoding="utf-8", errors="replace").read()}
        a_texts = {key: open(a.after, encoding="utf-8", errors="replace").read()}
    else:
        b_texts, a_texts = _read(a.before), _read(a.after)
    if not b_texts:
        print("text_loss_differential: BEFORE side is empty - refusing to report a "
              "clean run computed from nothing.", file=sys.stderr)
        return 2

    shared = sorted(set(b_texts) & set(a_texts))
    if not shared:
        print("text_loss_differential: the two sides share no filenames - nothing was "
              "compared. This is a setup error, not a pass.", file=sys.stderr)
        return 2

    results, any_loss = {}, False
    for name in shared:
        if not b_texts[name].strip():
            print(f"text_loss_differential: {name}: BEFORE is blank - refusing.", file=sys.stderr)
            return 2
        r = compare(b_texts[name], a_texts[name])
        results[name] = r
        any_loss = any_loss or r["loss"]

    missing = sorted(set(b_texts) - set(a_texts))
    if missing:
        any_loss = True

    if a.json:
        print(json.dumps({"compared": shared, "missing_after": missing,
                          "results": results, "loss": any_loss}, indent=2))
        return 1 if any_loss else 0

    print(f"text_loss_differential · compared {len(shared)} document(s)")
    if missing:
        print(f"  MISSING ENTIRELY from the AFTER side: {', '.join(missing)}")
    for name in shared:
        r = results[name]
        spans, gone = r["arm_a_deleted_spans"], r["arm_b_all_copies_gone"]
        stat = r["arm_a_spans_carrying_statistics"]
        flag = "LOSS" if r["loss"] else "ok"
        print(f"  [{flag}] {name}: arm A {len(spans)} deleted span(s) "
              f"({len(stat)} carrying statistics) · arm B {len(gone)} all-copies-gone")
        for s in spans[:5]:
            mark = " <-- STATISTICAL" if s["carries_statistical_content"] else ""
            print(f"      A: -{s['words']}w{mark}: {s['excerpt'][:110]}")
        for g in gone[:5]:
            print(f"      B: {g['occurrences_before']}x -> 0: {g['excerpt'][:110]}")
    print()
    if any_loss:
        print("VERDICT: TEXT LOSS. Both arms must be zero before this is a pass.")
        return 1
    print("VERDICT: no loss detected (arm A 0, arm B 0).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
