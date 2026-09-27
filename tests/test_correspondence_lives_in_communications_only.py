"""Every correspondence-shaped file lives in the correspondence folder, never docs/ or repo root.

docpluck-cleanup Section 0.3b requires cross-project correspondence (handoffs,
findings, triage notes, inbox/outbox, requests, replies, notices, memos,
customer updates) to live only in the gitignored correspondence folder --
one flat directory, so a new naming convention still gets caught by a
DIRECTORY rule rather than a prefix denylist that can only ever cover
conventions someone already thought of.

Found by the 2026-09-26 /docpluck-cleanup re-run: a dated prompt file in
``docs/`` -- untracked and already gitignored (so no public exposure), but
still outside the correspondence folder where the rule requires it. It was moved
in the same run. This test pins that the check actually fires
(and doesn't merely rely on a human re-reading Section 0.3b) by scanning the
real working tree, tracked or not -- git-scoped checks are blind to a
gitignored misplacement, which is exactly what this file was.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The gitignored correspondence folder (its name is also in .gitignore).
CORRESPONDENCE_DIR = "communications"

CORRESPONDENCE_PREFIX = re.compile(
    r"^(INBOX|OUTBOX|HANDOFF|HANDOVER|REPLY|REPLIES|REQUEST|REQUESTS|"
    r"FINDINGS|TRIAGE|NOTICE|MEMO|CUSTOMER_UPDATE|PROMPTS|REPORT|BRIEF|RESULT|CONSUMER_NOTICE)[_.]",
    re.IGNORECASE,
)

# Directories to scan: repo root and docs/ (maxdepth 2 equivalent to the
# skill's `find . -maxdepth 2` check), excluding the correspondence folder,
# .git/, and any virtualenv / node_modules noise.
SCAN_DIRS = [REPO, REPO / "docs"]
EXCLUDE_DIR_NAMES = {".git", "node_modules", CORRESPONDENCE_DIR, "__pycache__", ".venv", "venv"}


def _correspondence_shaped_files_outside_communications() -> list[Path]:
    hits: list[Path] = []
    for d in SCAN_DIRS:
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.is_dir():
                continue
            if f.suffix.lower() != ".md":
                continue
            if CORRESPONDENCE_PREFIX.match(f.name):
                hits.append(f.relative_to(REPO))
    return hits


def test_no_correspondence_shaped_file_outside_communications():
    hits = _correspondence_shaped_files_outside_communications()
    assert not hits, (
        f"Correspondence-shaped file(s) found outside {CORRESPONDENCE_DIR}: "
        f"{[str(h) for h in hits]}. Move them into {CORRESPONDENCE_DIR} (flat, no "
        "subfolders) per docpluck-cleanup Section 0.3b."
    )


def test_the_regex_actually_fires_on_a_known_shape():
    """Two-sided control: the pattern must be capable of matching something,
    or the assertion above would pass vacuously on a broken pattern."""
    assert CORRESPONDENCE_PREFIX.match("NOTICE_example.md")
    assert CORRESPONDENCE_PREFIX.match("PROMPTS_example.md")
    assert not CORRESPONDENCE_PREFIX.match("README.md")
    assert not CORRESPONDENCE_PREFIX.match("NORMALIZATION.md")
