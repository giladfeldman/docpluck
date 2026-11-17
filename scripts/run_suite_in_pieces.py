"""Run the test suite as many small pytest runs, one log per piece, one summary.

Why: the full suite takes about two hours on a shared machine, and the machine-wide
job queue stops any single job at 60 minutes. One long run then dies with no
summary, which reads like "nothing failed" when most tests never ran.

Each piece is a few test files. When DOCPLUCK_JOB_QUEUE names a job-queue script
that takes `run --prio batch --group G -- <cmd>`, each piece runs through it;
otherwise pytest runs directly. A piece that is
stopped, crashes, or ends with no pytest summary line counts as NOT RUN, never as
passed. Exit 0 only when every piece reported a summary with no failures.

    python scripts/run_suite_in_pieces.py                 # whole suite, 4 files per piece
    python scripts/run_suite_in_pieces.py --files-per-piece 2 --only-pieces 5,9
    python scripts/run_suite_in_pieces.py tests/test_a.py tests/test_b.py
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# "6 passed in 3.62s" under -q; "==== 6 passed in 3.62s ====" otherwise.
_SUMMARY = re.compile(r"^=*\s*(\d+ (passed|failed|errors?|skipped|xfailed|xpassed|deselected)|no tests ran)\b.* in [\d.]+s")
_COUNT = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)")


def _test_files(paths: list[str]) -> list[str]:
    if paths:
        return paths
    return sorted(p.relative_to(REPO).as_posix() for p in (REPO / "tests").rglob("test_*.py"))


def _loadq() -> list[str]:
    q = Path(os.environ.get("DOCPLUCK_JOB_QUEUE", ""))
    if not os.environ.get("DOCPLUCK_JOB_QUEUE") or not q.is_file():
        return []
    return [sys.executable, str(q), "run", "--prio", "batch", "--group",
            os.environ.get("LOADQ_GROUP", "docpluck-suite"), "--"]


def _verdict(log: str, code: int) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    lines = [ln for ln in log.splitlines() if _SUMMARY.search(ln)]
    if not lines:
        return f"NOT RUN (no pytest summary, exit {code})", counts
    for n, kind in _COUNT.findall(lines[-1]):
        counts[kind.rstrip("s") if kind.startswith("error") else kind] = int(n)
    if counts.get("failed") or counts.get("error"):
        return "FAIL", counts
    return ("PASS" if code == 0 else f"NOT RUN (exit {code})"), counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="test files (default: every tests/test_*.py)")
    ap.add_argument("--files-per-piece", type=int, default=4)
    ap.add_argument("--only-pieces", default="", help="comma list of piece numbers to (re)run")
    ap.add_argument("--log-dir", default=str(REPO / "tmp" / "suite_pieces"))
    ap.add_argument("--no-queue", action="store_true", help="run pytest directly, not through DOCPLUCK_JOB_QUEUE")
    a = ap.parse_args()

    files = _test_files(a.paths)
    if not files:
        print("NOT RUN: no test files found", file=sys.stderr)
        return 2
    pieces = [files[i:i + a.files_per_piece] for i in range(0, len(files), a.files_per_piece)]
    wanted = {int(x) for x in a.only_pieces.split(",") if x.strip()}
    prefix = [] if a.no_queue else _loadq()
    log_dir = Path(a.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    totals: dict[str, int] = {}
    bad: list[str] = []
    for i, piece in enumerate(pieces):
        if wanted and i not in wanted:
            continue
        cmd = prefix + [sys.executable, "-m", "pytest", "-q", "-p", "no:randomly", "-rfE", *piece]
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = r.stdout + r.stderr
        (log_dir / f"piece_{i:03d}.log").write_text(out + f"\nEXIT {r.returncode}\n", encoding="utf-8")
        verdict, counts = _verdict(out, r.returncode)
        for k, v in counts.items():
            totals[k] = totals.get(k, 0) + v
        print(f"piece {i:03d}/{len(pieces) - 1:03d} {verdict:<40} {counts}  {' '.join(piece)}", flush=True)
        if verdict != "PASS":
            bad.append(f"{i:03d} {verdict}")
            for ln in out.splitlines():
                if ln.startswith(("FAILED", "ERROR")):
                    print("    " + ln, flush=True)

    print(f"TOTAL {totals}  pieces={len(wanted) or len(pieces)}  not-pass={len(bad)}")
    for b in bad:
        print(f"  not pass: piece {b}  (rerun: --only-pieces {int(b.split()[0])})")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
