"""Does every repo path a docpluck project skill names still exist? (plan gap G9, 2026-11-13)

QA checks 4, 7 and 7e read a sibling checkout's `test-pdfs` folder, which was removed under
the custody rule; each printed SKIP on every run and nobody saw it. A check that cannot find its input must fail, and the
skill text that points at a vanished path is where that starts.

Scans `$DOCPLUCK_SKILLS_DIR/docpluck-*/**/*.md` (the maintainer's gate skills, never tracked here) for path tokens rooted in this repo
(`docpluck/`, `tests/`, `tools/`, `scripts/`, `docs/`) or in the retired corpus
folder (`test-pdfs`), and reports each that does not resolve. A line that says
the path is retired/removed/gone is history, not an instruction, and is skipped.

Exit 0 PASS, 1 FAIL (each missing path listed).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from docpluck.testing._root import ENV_SKILLS, project_skills_dir, tool_problem  # noqa: E402
TOKEN = re.compile(
    r"(?<![\w./-])((?:\.\./[\w-]+/)?test-pdfs[\w./-]*"
    r"|(?:docpluck|tests|tools|scripts|docs)/[\w./-]+\.(?:py|md|json|yaml|txt))"
)
# Lines that NAME a path without telling anyone to read it: the .gitignore
# entry list and the forbidden-folder lists of the cleanup / review gates.
ALLOW_LINE = ("`.env.local`", "`testpdfs/`")
HISTORY = re.compile(r"retired|removed|no longer exist|does not exist|was |used to|corrected|gone|RETIRED", re.I)


def main() -> int:
    # Dated lesson cards are history by construction: they record what a path
    # WAS on that day.
    SKILLS = project_skills_dir()
    if SKILLS is None:
        print("COULD-NOT-VERIFY: " + tool_problem(ENV_SKILLS))
        return 2
    md = sorted(f for f in SKILLS.glob("docpluck-*/**/*.md") if "lessons" not in f.parts)
    if not md:
        print("COULD-NOT-VERIFY: no docpluck skill files found")
        return 2
    missing: list[str] = []
    n = 0
    for f in md:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if HISTORY.search(line):
                continue
            for tok in TOKEN.findall(line):
                tok = tok.rstrip(".,)")
                if "<" in tok or "*" in tok or "{" in tok:
                    continue
                n += 1
                if any(a in line for a in ALLOW_LINE):
                    continue
                if not ((ROOT / tok).exists() or (ROOT.parent / tok).exists()
                        or (ROOT / "communications" / Path(tok).name).exists()):
                    missing.append(f"{f.relative_to(SKILLS).as_posix()}:{i}: {tok}")
    print(f"COVERAGE: {len(md)} skill files, {n} repo paths checked")
    for m in missing:
        print("  missing " + m)
    print("SKILL PATHS: " + ("FAIL" if missing else "PASS"))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
