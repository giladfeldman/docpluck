"""What a reference-list entry looks like, read from the text alone.

Two callers:

* ``core.partition_into_sections`` opens a ``references`` section at a numbered
  list of reference entries that has NO heading (some journals print the
  bibliography straight after the ``Keywords`` / ``Received:`` lines).
* ``docpluck.body_text`` stops the reference list where entry-shaped lines stop,
  so body paragraphs that the linearised text places after the bibliography
  heading are not cut away with it.

A line is entry-shaped when it carries an author-name pattern AND a year (or a
volume/page tail). Both are required: a numbered list of steps in a Methods
section has neither, and a sentence citing "Smith (2019)" has a year but is not
led by a reference number.
"""

from __future__ import annotations

import re

# "[3] ", "[3]. ", "3. ", "3) " at line start.
_NUMBERED_ENTRY = re.compile(r"(?m)^[ \t]*(?:\[(?P<b>\d{1,3})\]\.?|(?P<d>\d{1,3})[.)])[ \t]+(?=\S)")

_YEAR = re.compile(r"\b(?:1[89]|20)\d{2}[a-z]?\b")

# "A. B. Carter" | "Hartmann KL," | "Becker T," | "Smith, J." | "Smith J."
_AUTHOR = re.compile(
    r"\b[A-Z]\.[ \t]?(?:[A-Z]\.[ \t]?)*[A-Z][A-Za-z'’\-]+"
    r"|\b[A-Z][A-Za-z'’\-]+,?[ \t]+[A-Z]{1,3}\b[,.]"
    r"|\b[A-Z][A-Za-z'’\-]+,[ \t]+[A-Z]\."
)


def looks_like_reference_entry(entry: str) -> bool:
    """True when ``entry`` (one entry, possibly wrapped over lines) reads as a
    bibliography entry: an author-name pattern and a year."""
    head = entry[:400]
    return bool(_AUTHOR.search(head)) and bool(_YEAR.search(head))


def _numbered_entries(text: str, start: int, end: int):
    """Yield ``(number, entry_start, entry_end)`` for numbered lines in
    ``text[start:end]``; an entry runs to the next numbered line."""
    hits = []
    for m in _NUMBERED_ENTRY.finditer(text, start, end):
        num = int(m.group("b") or m.group("d"))
        hits.append((num, m.start()))
    for i, (num, s) in enumerate(hits):
        e = hits[i + 1][1] if i + 1 < len(hits) else end
        yield num, s, e


# Minimum entries that make a run a bibliography, and the share of the first
# ten that must be entry-shaped.
_MIN_RUN = 3
_MIN_SHAPED_SHARE = 0.8


def find_unheaded_reference_list(text: str, search_from: int) -> int | None:
    """Offset of a numbered reference list that starts at entry 1 at or after
    ``search_from``, or None.

    The run must count up from 1 without a gap for at least three entries, and
    at least 80 % of its first ten entries must be entry-shaped
    (:func:`looks_like_reference_entry`). The first such run wins.
    """
    entries = list(_numbered_entries(text, search_from, len(text)))
    for i, (num, s, _e) in enumerate(entries):
        if num != 1:
            continue
        run = [entries[i]]
        for nxt in entries[i + 1:]:
            if nxt[0] == run[-1][0] + 1:
                run.append(nxt)
            elif nxt[0] == 1:
                break
        if len(run) < _MIN_RUN:
            continue
        sample = run[:10]
        shaped = sum(looks_like_reference_entry(text[a:b]) for _n, a, b in sample)
        if shaped >= _MIN_SHAPED_SHARE * len(sample):
            return s
    return None
