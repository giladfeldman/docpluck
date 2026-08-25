"""No markdown file may carry a raw C0 control character.

**A NUL in `CHANGELOG.md` made the PUBLIC repo's changelog a BINARY file.**
Found 2026-08-22. The v2.4.137 entry documented the corrupted-glyph class by
pasting the examples as raw bytes rather than escapes, so the prose *about*
control characters contained them:

    | `Schri<02>macher` |  | `No<04>allsanitat` |  | `A<03> -B<03> helices` |
    A blanket `[<00>-<08><0b><0e>-<1f>]` strip -- the obvious fix...

Two costs, and the second is the one nobody would have found by reading:

1. The sentence could not be read. That last span is the character CLASS the
   sentence is about, and it rendered as ``[ --]``.
2. The NUL sits at offset 3216 of the HEAD blob -- inside git's 8000-byte
   binary-detection window -- so `git diff` reported ``Bin 594328 -> 598973
   bytes`` and `--numstat` reported ``-  -``. **There has been no line-level
   diff, and no `git blame`, on any changelog change ever made**, and the whole
   594 KB was re-stored on every commit. Nothing failed; the symptom was the
   ABSENCE of a diff, which is why it survived every review.

The same shape reached six more files: four raw form feeds in `todo.md`'s
description of the form-feed defect (rendering ``"" * line.count("")``), and
two more in the phrase "the ``\\n\\f\\f\\n`` marker", which rendered as "the
`` marker" -- a sentence about the page-break marker that had lost its page-break
marker.

So this is a gate rather than a cleanup. A check that CAN be a test MUST be a
test: the next entry that quotes a corrupted glyph verbatim re-binaries the
public repo, and it would do it as silently as the first one did.

Escapes are the FAITHFUL form, not a lossy one -- ``\\x02`` names the byte, an
invisible 0x02 does not. Quoted U+FFFD is deliberately still allowed: the
changelog quotes a real defect where the library emitted raw U+FFFD, and that
character is printable, carries no binary risk, and is evidence.
"""

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# C0 minus the three whitespace characters a text file legitimately holds, plus
# DEL. U+000C (FORM FEED) is INCLUDED: it is legitimate in extracted PDF text,
# which is the whole point of the page-boundary work -- but a markdown file
# should write it as an escape, because it renders as nothing.
FORBIDDEN = {c for c in range(0x20) if c not in (0x09, 0x0A, 0x0D)} | {0x7F}

# Git decides "binary" by scanning this many bytes for a NUL.
GIT_BINARY_WINDOW = 8000


def _markdown_files() -> list[Path]:
    """Every tracked markdown file, from git rather than a directory glob.

    A glob would also sweep untracked scratch files and would silently shrink if
    the working tree were cleaned -- and a gate that computes its denominator
    from whatever happens to be on disk prints `N / N` and passes on nothing.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "*.md", "**/*.md"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [REPO / line for line in out.splitlines() if line.strip()]


def _control_chars(text: str) -> dict[int, int]:
    counts: dict[int, int] = {}
    for ch in text:
        o = ord(ch)
        if o in FORBIDDEN:
            counts[o] = counts.get(o, 0) + 1
    return counts


def test_the_detector_fires_on_a_planted_control_character():
    """A zero is a claim about the INSTRUMENT until the instrument is shown to fire.

    Without this, a scan that silently matched nothing -- a broken regex, an
    empty file list -- would report the same clean result as a genuinely clean
    repo. (Standing rule, CLAUDE.md.)
    """
    assert _control_chars("a\x02b\x00c") == {0x02: 1, 0x00: 1}
    assert _control_chars("plain text\n\twith\r\n whitespace") == {}


def test_the_file_list_holds_the_files_this_gate_exists_for():
    """The denominator must be real. An empty list passes every assertion below.

    Named files, not a count. A threshold ("more than N markdown files") is the
    same defect this repo already records elsewhere -- it derives its
    denominator from whatever happens to be on disk, so it passes on a corpus
    that has silently shrunk. It also nearly shipped here: the first draft
    asserted `> 50` on the assumption that the 243 markdown files in the working
    tree were tracked. Only **14** are; everything under `docs/` is internal and
    gitignored by the public-repo allowlist. The guard caught its own author.

    Scope is deliberately the TRACKED set. Those are the files that reach the
    public repo and PyPI, and the only ones where a NUL can cost a diff. The
    untracked internal docs were swept once by hand on 2026-08-22 (243 files,
    0 hits) but cannot be gated: they differ per machine, so a hard assertion on
    them would be flaky rather than protective.
    """
    tracked = {str(p.relative_to(REPO)).replace("\\", "/") for p in _markdown_files()}
    for required in ("CHANGELOG.md", "docs/README.md", "docs/NORMALIZATION.md"):
        assert required in tracked, (
            f"{required} is not in the tracked markdown set -- either it was "
            f"untracked, or this gate is reading the wrong file list. Got: "
            f"{sorted(tracked)}"
        )


@pytest.mark.parametrize("path", _markdown_files(), ids=lambda p: str(p.relative_to(REPO)))
def test_markdown_file_carries_no_raw_control_characters(path: Path):
    if not path.exists():  # tracked but deleted in the working tree
        pytest.skip("tracked file not present in the working tree")
    found = _control_chars(path.read_bytes().decode("utf-8"))
    assert not found, (
        f"{path.relative_to(REPO)} contains raw control characters "
        f"{ {f'U+{c:04X}': n for c, n in sorted(found.items())} }. "
        "Write them as escapes (\\x02, \\f) -- an invisible byte does not "
        "document itself, and a NUL makes the file BINARY to git."
    )


def test_no_markdown_file_has_a_nul_in_gits_binary_detection_window():
    """The specific failure that cost the public changelog its diffability.

    Narrower than the test above and kept separate on purpose: this one names
    the CONSEQUENCE, so a future reader who removes the general rule still has
    the reason it existed.
    """
    offenders = []
    for path in _markdown_files():
        if not path.exists():
            continue
        head = path.read_bytes()[:GIT_BINARY_WINDOW]
        if b"\x00" in head:
            offenders.append(f"{path.relative_to(REPO)} (NUL at byte {head.find(b'\x00')})")
    assert not offenders, (
        "git treats these as BINARY -- no diff, no blame, no line-level review, "
        f"and the whole file re-stored on every commit: {offenders}"
    )
