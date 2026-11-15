"""Does every change in this release name the debt item it closes, and is that item closed?

Plan gap G1 (2026-11-13): of 435 debt items, 3 were ever named in a commit, so
"was this fixed, and where?" could only be answered by re-reading code. This
check reads the commits since the last release tag:

* every ``fix``/``feat``/``perf`` commit must cite a debt id (``d-xxxxxx``) or
  say ``no-debt`` in its message (a change no item asked for, said explicitly);
* every cited id must exist in ``TODO.md`` and, with ``--release``, be closed
  (``- [x]``) -- a release that cites an open item ships a claim nobody checked.

Exit 0 PASS, 1 FAIL (each problem listed), 2 COULD-NOT-VERIFY (no TODO.md or no
tag: never a silent pass).

    python scripts/check_debt_trace.py [--since v2.4.159] [--release]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r"\bd-[0-9a-f]{6}\b")
NEEDS_ID = re.compile(r"^(fix|feat|perf)(\(|:|!)")
# A release may cite an item it deliberately leaves open: the residual it logged
# ("logged as d-x"), an item it fixes only in part ("part of d-x"), or "open d-x".
# Those are listed, never failed; any other open citation still fails --release.
# A list counts whole: "logged as d-a d-b, d-c and d-d" leaves all four open
# (2.4.160: only the first id of such a list was read, so the rest failed).
OPEN_CITE = re.compile(
    r"(?:logged as|part of|open)\s+"
    r"(d-[0-9a-f]{6}(?:(?:\s*,\s*|\s+and\s+|\s+)d-[0-9a-f]{6})*)\b", re.I)


def open_citations(body: str) -> set[str]:
    """Every id a commit body cites as deliberately left open."""
    return {i for m in OPEN_CITE.findall(body) for i in ID.findall(m)}


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout


def _todo_states(todo: Path) -> dict[str, bool]:
    """d-id -> closed? from the TODO.md item lines (`- [x]` / `- [ ]`)."""
    states: dict[str, bool] = {}
    for line in todo.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*- \[( |x)\]", line)
        if not m:
            continue
        for anchor in re.findall(r"\^(d-[0-9a-f]{6})", line):
            states[anchor] = m.group(1) == "x"
    return states


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--since", help="tag to start from (default: latest v* tag)")
    ap.add_argument("--release", action="store_true",
                    help="also require every cited item to be closed")
    a = ap.parse_args(argv)
    since = a.since or _git("describe", "--tags", "--abbrev=0", "--match", "v*").strip()
    if not since:
        print("COULD-NOT-VERIFY: no release tag to start from")
        return 2
    todo = ROOT / "TODO.md"
    if not todo.is_file():
        print("COULD-NOT-VERIFY: TODO.md (the debt store) is not in this checkout")
        return 2
    states = _todo_states(todo)
    if len(states) < 50:   # a zero here means the parser broke, not that debt is empty
        print(f"COULD-NOT-VERIFY: only {len(states)} debt items parsed from TODO.md")
        return 2

    log = _git("log", "--format=%H%x1f%B%x1e", f"{since}..HEAD")
    problems: list[str] = []
    cited: set[str] = set()
    cited_open: set[str] = set()
    n = 0
    for entry in filter(str.strip, log.split("\x1e")):
        sha, _, body = entry.strip().partition("\x1f")
        subject = body.strip().splitlines()[0] if body.strip() else ""
        ids = set(ID.findall(body))
        cited |= ids
        cited_open |= open_citations(body)
        n += 1
        if NEEDS_ID.match(subject) and not ids and "no-debt" not in body:
            problems.append(f"{sha[:7]} cites no debt id (add d-xxxxxx or 'no-debt'): {subject[:80]}")
    for i in sorted(cited):
        if i not in states:
            problems.append(f"{i} is cited but is not a debt item in TODO.md")
        elif a.release and not states[i] and i not in cited_open:
            problems.append(f"{i} is cited by this release but still open in TODO.md")
    print(f"COVERAGE: {n} commits {since}..HEAD, {len(cited)} debt ids cited, "
          f"{len(states)} items in TODO.md")
    for i in sorted(cited_open):
        print(f"  cited as still open (by the commit's own words): {i}"
              + ("" if not states.get(i) else " -- now closed"))
    for p in problems:
        print("  " + p)
    print("DEBT TRACE: " + ("FAIL" if problems else "PASS"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
