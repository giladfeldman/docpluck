"""Heuristic linter for rendered docpluck markdown (Check 7c).

Greps rendered .md files for known visible-defect signatures that escaped
upstream filters in normalize.py + render.py. Each match is a FAIL — the
defect class should have been stripped before reaching .md.

Five signatures, from the 2026-05-13 xiao_2021_crsp + maier_2023_collabra
audit (see docs/HANDOFF_2026-05-13_apa_50_expansion.md):

  RH — running-header `Q. XIAO ET AL.` / `Q.M. SMITH ET AL`
  CT — `CONTACT <Name> <email>` Taylor & Francis footer
  CB — `[a-c] Contributed equally` / `[a-c] Corresponding Author:` footnote
  AF — standalone `Department of X, University of Y, Region` affiliation
  FN -- inline footnote leaked into prose (single-line digit + Though|Note|See|We)

Usage:
  python scripts/lint_rendered_corpus.py tmp/renders_v2.4.0/*.md
  python scripts/lint_rendered_corpus.py path/to/single.md

Exit code:
  0 — no defects found
  1 — at least one defect found (CI failure)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Each entry: (tag, pattern, description)
_LINT_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "RH",
        re.compile(r"^[A-Z]\.(?:\s*[A-Z]\.?)?\s+[A-Z]{2,}\s+ET\s+AL\.?\s*$"),
        "Running-header leak (initial + ALL-CAPS surname + ET AL.)",
    ),
    (
        "CT",
        re.compile(r"^CONTACT\s+[A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+)+\s+\S+@\S+"),
        "Contact-line footer (CONTACT <Name> <email>)",
    ),
    (
        "CB",
        re.compile(r"^[a-c]\s+(?:Contributed\s+equally|Corresponding\s+Author)\b"),
        "Prefixed contribution / corresponding-author footnote",
    ),
    (
        "AF",
        re.compile(
            r"^Department\s+of\s+[A-Z][A-Za-z]+(?:\s+and\s+[A-Z][A-Za-z]+)?,\s+"
            r"University\s+of\s+[A-Z][A-Za-z]+(?:\s+Kong)?,\s+.{2,80}$"
        ),
        "Standalone Dept/University affiliation line",
    ),
    (
        "FN",
        re.compile(
            r"^\d{1,2}\s+(?:Though|Note|See|We)\s+\w.{2,180}[\.\)]\s*$"
        ),
        "Inline footnote leaked as standalone paragraph",
    ),
]


def lint_file(path: Path) -> list[tuple[int, str, str, str]]:
    """Return defects as (line_no, tag, description, line_text) tuples."""
    if not path.exists() or path.suffix != ".md":
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    defects: list[tuple[int, str, str, str]] = []
    for i, line in enumerate(text.split("\n"), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        for tag, pat, desc in _LINT_PATTERNS:
            if pat.match(stripped):
                defects.append((i, tag, desc, stripped[:120]))
                break
    return defects


def main(argv: list[str]) -> int:
    paths: list[Path] = []
    for arg in argv:
        p = Path(arg)
        if p.is_dir():
            paths.extend(p.glob("**/*.md"))
        elif p.is_file():
            paths.append(p)
    if not paths:
        print("usage: lint_rendered_corpus.py <file.md | dir | glob>", file=sys.stderr)
        return 2
    total = 0
    files_with_defects = 0
    for path in sorted(paths):
        defects = lint_file(path)
        if not defects:
            continue
        files_with_defects += 1
        for ln, tag, desc, line_text in defects:
            print(f"{path}:{ln}: {tag} {desc} :: {line_text}")
            total += 1
    if total == 0:
        print(f"PASS: {len(paths)} files, 0 defects.")
        return 0
    print(
        f"\nFAIL: {total} defects across {files_with_defects} files "
        f"(of {len(paths)} checked)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
