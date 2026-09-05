"""Every tool the project's gate skills NAME must exist and be loadable.

Written 2026-09-05 against the unfixed tree and watched FAIL (see the docstring of
`test_every_tool_a_gate_names_exists`).

WHY THIS FILE EXISTS. W-0023: `docpluck-qa` check 2 declared
`tools/diag/table_capture_guard_diff.py` MANDATORY for any change under `docpluck/tables/`,
and that tool raised `AttributeError` on all 26 corpus papers because one arm patched
`detect._column_runs`, a name that has never existed in any commit. The gate was mandatory
for months and had never once measured anything. `tests/test_table_capture_guard_diff_arms_resolve.py`
now pins that tool's ARMS. Nothing pinned the far cheaper precondition one level up:
**that the tool a gate names is even there.**

The two failure modes this file rules out:

  1. a gate step names a path that does not exist -- the operator either silently skips the
     step or "runs" a command that errors, and both look like a step that passed;
  2. a gate step names a path that exists but cannot be loaded -- a stale import, a moved
     dependency -- which fails at the moment of use, long after the review that mandated it.

CONTROL, because this test is itself an instrument and a broken parser would find zero
references and pass. `test_the_parser_actually_found_the_gate_commands` asserts a floor on
the number of references parsed AND that specific known-present tools are among them. A
zero here must read as a broken parser, never as a clean repo.

SCOPE. `.claude/` is gitignored and untracked (this is a PUBLIC repo; skill definitions must
not ship in it). So on any clone the skills are absent and these tests SKIP -- loudly, naming
the reason, because a skip is a coverage hole wearing a green tick. They are live on the
machine that runs the gates, which is the only machine where the gates exist.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SKILLS = _REPO / ".claude" / "skills"

_SKILL_FILES = (
    "docpluck-qa/SKILL.md",
    "docpluck-review/SKILL.md",
    "docpluck-cleanup/SKILL.md",
    "docpluck-deploy/SKILL.md",
)

# `docpluck-cleanup` carries a DELETION list -- scripts it instructs the operator to
# remove. Those names are supposed to be absent; asserting they exist would invert the
# skill's own instruction. The block is delimited by its own heading, so the exclusion
# tracks the document rather than a hand-maintained name list that would rot.
_DELETION_BLOCK_HEADING = re.compile(r"^#### .*known-deletable", re.IGNORECASE)
_ANY_HEADING = re.compile(r"^#{1,6} ")

_PATH_RE = re.compile(r"(?:tools|scripts)/[A-Za-z0-9_./-]+\.(?:py|sh)")


def _skills_present() -> bool:
    return all((_SKILLS / rel).is_file() for rel in _SKILL_FILES)


def _referenced_tools() -> dict[str, list[str]]:
    """{repo-relative path: [\"skill:line\", ...]} for every gate tool the skills name.

    References inside a `known-deletable` block are dropped -- see above.
    """
    found: dict[str, list[str]] = {}
    for rel in _SKILL_FILES:
        text = (_SKILLS / rel).read_text(encoding="utf-8", errors="replace")
        in_deletion_block = False
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _DELETION_BLOCK_HEADING.match(line):
                in_deletion_block = True
                continue
            if in_deletion_block and _ANY_HEADING.match(line):
                in_deletion_block = False
            if in_deletion_block:
                continue
            for m in _PATH_RE.finditer(line):
                found.setdefault(m.group(0), []).append(f"{rel}:{lineno}")
    return found


@pytest.fixture(scope="module")
def referenced() -> dict[str, list[str]]:
    if not _skills_present():
        pytest.skip(
            "SKIPPED, NOT PASSED: .claude/skills/ is gitignored and untracked in this "
            "PUBLIC repo, so the gate skills are absent from any clone. This check is "
            "live only where the gates themselves live."
        )
    return _referenced_tools()


def test_the_parser_actually_found_the_gate_commands(referenced):
    """Two-sided control on this file's own instrument.

    A regex that matches nothing yields an empty set, and every assertion below then
    passes over it. That is the exact shape of the defect this file was written for, so
    the floor and the named positives are asserted before anything else is trusted.
    """
    assert len(referenced) >= 12, (
        f"parsed only {len(referenced)} tool references from {len(_SKILL_FILES)} skills; "
        "the skills changed shape or the pattern is broken. A low number here is a claim "
        "about this parser, not about the repo."
    )
    for known in (
        "tools/diag/table_capture_guard_diff.py",
        "tools/diag/render_deletion_scan.py",
        "scripts/check_app_pin_sync.py",
    ):
        assert known in referenced, (
            f"{known} is named by a gate step and the parser did not see it -- the parser "
            "is broken, so every other assertion in this file is vacuous."
        )


def test_every_tool_a_gate_names_exists(referenced):
    """RED FIRST on 2026-09-05: `docpluck-review/SKILL.md:134` cited

        Pattern: `tools/diag/english_only_locale_scan.py`

    as the exemplar a language-reporting scan must copy, and no such file has ever
    existed. A reviewer following rule 0c is sent to nothing. The live exemplars are
    `tools/diag/_language.py` and the five scans that import it.
    """
    missing = {p: sites for p, sites in referenced.items() if not (_REPO / p).is_file()}
    assert not missing, "gate steps name tools that do not exist:\n" + "\n".join(
        f"  {p}  <- named at {', '.join(sites)}" for p, sites in sorted(missing.items())
    )


def test_every_tool_a_gate_names_can_be_loaded(referenced):
    """Existing is not running. A tool that cannot import fails at the moment of use.

    Each module is loaded in a SUBPROCESS, for two reasons. It is what an operator
    actually does (`python tools/diag/x.py ...`), and ten of these scans set
    `DOCPLUCK_DISABLE_CAMELOT=1` at module scope on purpose -- importing them into this
    process would reconfigure every test that ran after them. That module-scope env leak
    is a measured hazard in this repo's history (it was misfiled for weeks as a "Camelot
    cumulative-load flake"), so the isolation is deliberate, not incidental.

    `scripts/harness/extract.py` uses relative imports and is retried as a package
    module, which is how its gate step invokes it.
    """
    runner = (_REPO / "tests" / "_gate_tool_import_probe.py")
    failures: list[str] = []
    for rel in sorted(referenced):
        path = _REPO / rel
        if not path.is_file() or path.suffix != ".py":
            continue
        proc = subprocess.run(
            [sys.executable, "-W", "ignore", str(runner), rel],
            cwd=_REPO, capture_output=True, text=True, timeout=180,
        )
        if proc.returncode != 0:
            out = (proc.stderr or proc.stdout).strip().splitlines() or ["<no output>"]
            failures.append(f"  {rel}  ({', '.join(referenced[rel])}): {out[-1][:160]}")
    assert not failures, "gate steps name tools that cannot be loaded:" + "".join(
        chr(10) + f for f in failures
    )
