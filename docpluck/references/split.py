"""Split a references section into one string per bibliography entry.

The input is a references section's text as docpluck emits it (academic
normalization has usually re-joined each entry onto one line, but not always:
some layouts keep the printed line breaks, a numbered list can print the number
on its own line, and a page or column break can split an entry). Two modes:

* **numbered** -- most lines open with a list number ("[12]", "12.", "12)").
  An entry starts at a line whose number continues the sequence; every other
  line is a continuation. Sequence-checking is what keeps a continuation line
  that happens to open with a number ("2020;12:45-67.") from starting an entry.
* **author_year** -- an entry starts at a line that opens with an author name
  (or an organisation) and states a year near its start, after a line that
  ended an entry. Everything else is a continuation.

Hanging indentation is not visible in extracted text, so it is never relied on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING = re.compile(
    r"^\s*(?:\d{1,2}\.?\s+)?(?:references?(?:\s+cited)?|bibliography|literature\s+cited|works\s+cited|"
    r"reference\s+list|literatur(?:verzeichnis)?|sources|notes\s+and\s+references)\s*:?\s*$",
    re.IGNORECASE,
)

# "[12]", "[12].", "12.", "12)" at line start. A bare "12 " only before a
# Vancouver author name: too many continuation lines open with a volume or a year.
_NUM_START = re.compile(
    r"^\s*(?:\[(\d{1,4})\]\.?(?=\s|$)|(\d{1,4})[.)](?=\s|$)|(\d{1,4})\s*$"
    # BMJ: "12 Smith AB, Jones C." -- a bare number, accepted only before a Vancouver name
    r"|(\d{1,3})\s+(?=[A-ZÀ-Þ][\w'’\-]+(?:\s[A-ZÀ-Þ]?[\w'’\-]+)?\s[A-Z]{1,3}[,.]))"
)

# PMC author-manuscript running footer, glued into entries on PMC reprints.
_PMC_FOOTER = re.compile(
    r"\s*(?:[A-Z][\w.&:,' -]{0,80}?\.\s+)?Author manuscript;\s+available in PMC\s+\d{4}(?:\s+[A-Z][a-z]+)?(?:\s+\d{1,2})?\.?"
)
_YEAR = re.compile(r"(?<!\d)(?:1[6-9]\d{2}|20\d{2})(?!\d)|\bn\.\s?d\.|\bin press\b", re.IGNORECASE)

# A line that opens like an author list: "Surname, I.", "Surname, Given",
# "Surname IJ,", "I. J. Surname", "van der Berg, J.", or an organisation name.
_LETTER = r"[^\W\d_]"
_SURNAME = rf"(?:(?:[a-z]{{1,4}}|[dD]e|[vV]an|[vV]on|[dD]er|[dD]i|[dD]a|[lL]e|[lL]a|[dD]u|[dD]el|[dD]ella|[tT]er|[tT]en|[dD]os|[dD]as|[aA]l|[eE]l)[\s'’]+)*{_LETTER}[\w'’\-]*"
_ENTRY_START = re.compile(
    rf"^(?:"
    rf"{_SURNAME}(?:\s{_SURNAME})?,\s+(?:[A-Z]|{_LETTER})"     # Surname, I. / Surname, Given
    rf"|{_SURNAME}(?:\s{_SURNAME})?\s+[A-Z]{{1,4}}[,.](?:\s|$)"  # Surname IJ,
    rf"|{_SURNAME}(?:\s{_SURNAME})?\s+[A-Z]{{1,4}}(?:-[A-Z])?(?:\s+(?:and|&)\s|\s*\()"  # Surname IJ and / Surname J-P (2020)
    rf"|(?:[A-Z]\.\s?-?){{1,3}}\s?{_SURNAME}"                  # I. J. Surname
    rf"|[A-Z][\w&'’\-]*(?:\s+(?:of|for|and|&|the|on|de|des|der|für|[A-Z][\w&'’\-]*)){{0,8}}[.,(]"  # organisation
    rf")"
)


@dataclass(frozen=True)
class _Line:
    text: str
    start: int
    end: int
    blank_before: bool


@dataclass(frozen=True)
class RawEntry:
    """One bibliography entry as printed, before field parsing."""

    text: str
    number: int | None
    char_start: int
    char_end: int


def _lines(text: str) -> list[_Line]:
    out: list[_Line] = []
    pos = 0
    blank = False
    for raw in text.split("\n"):
        start, end = pos, pos + len(raw)
        pos = end + 1
        stripped = raw.replace("\f", " ").strip()
        if not stripped:
            blank = True
            continue
        lead = len(raw) - len(raw.lstrip())
        out.append(_Line(stripped, start + lead, start + lead + len(stripped), blank))
        blank = False
    return out


#: A list number that extraction ran into the previous entry's line: "... 457-485. [16] Young G"
#: or "... 2014;129:837-47. 12. Smith". Cut there; the numbered splitter's
#: sequence check decides whether the cut starts an entry, and a cut that does
#: not is joined back with the same single space.
_INLINE_NUM = re.compile(
    r"(?<=[.)\]\d])\s+(?=\[\d{1,4}\](?:\s|$)|\d{1,3}\.\s+[A-ZÀ-ſ])"
    # BMJ: "... 1834-40. 4 Smith AB, Jones C." -- a bare number before a Vancouver name
    r"|(?<=[.)\]\d])\s+(?=\d{1,3}\s+[A-ZÀ-Þ][\w'’\-]+(?:\s[A-ZÀ-Þ]?[\w'’\-]+)?\s[A-Z]{1,3}[,.])"
)
#: the NEXT entry's number printed at the end of this entry's last line
#: ("... PMID: 28140125 2."). A volume ends lines the same way ("J Pers. 12."),
#: so these are cut only when the line-end numbers count up 2, 3, 4, ...
_TRAIL_NUM = re.compile(r"(?<=[.)\]\d])\s+(?=(\d{1,3})\.$)")


def _trailing_sequence(lines: list[_Line]) -> bool:
    nums = [int(m.group(1)) for ln in lines if (m := _TRAIL_NUM.search(ln.text))]
    run = best = 0
    for k, n in enumerate(nums):
        run = run + 1 if k and n == nums[k - 1] + 1 else 1
        best = max(best, run)
    return best >= 3


def _explode(lines: list[_Line]) -> list[_Line]:
    out: list[_Line] = []
    trailing = _trailing_sequence(lines)
    for ln in lines:
        if _NUMBERS_ONLY.match(ln.text):
            # "1. 2." -- one line per list number
            for m in re.finditer(r"\[?\d{1,4}[\].)]?", ln.text):
                out.append(_Line(m.group(), ln.start + m.start(), ln.start + m.end(), ln.blank_before))
            continue
        cuts = [m.end() for m in _INLINE_NUM.finditer(ln.text)]
        if trailing:
            cuts += [m.end() for m in _TRAIL_NUM.finditer(ln.text)]
            cuts.sort()
        if not cuts:
            out.append(ln)
            continue
        bounds = [0] + cuts + [len(ln.text)]
        for k in range(len(bounds) - 1):
            piece = ln.text[bounds[k]:bounds[k + 1]].strip()
            if piece:
                s = ln.start + bounds[k]
                out.append(_Line(piece, s, s + len(piece), ln.blank_before if k == 0 else False))
    return out


def _number(line: str) -> int | None:
    m = _NUM_START.match(line)
    if not m:
        return None
    return int(m.group(1) or m.group(2) or m.group(3) or m.group(4))


def _strip_number(line: str) -> str:
    return _NUM_START.sub("", line, count=1).strip()


def _join(parts: list[str]) -> str:
    out = ""
    for p in parts:
        if not out:
            out = p
        elif out.endswith("-") and not out.endswith(" -") and p[:1].islower():
            out += p  # word broken at a line end: keep the hyphen, no space
        elif re.search(r"(?:doi\.org/|doi:\s?|https?://|\b10\.\d{4,9}/)\S*[./_:\-]$", out, re.IGNORECASE):
            out += p  # a DOI / URL broken at a line end (after a "." / "/" / "-")
        else:
            out += " " + p
    out = _PMC_FOOTER.sub("", out)
    return re.sub(r"\s{2,}", " ", out).strip()


def _numbered_score(lines: list[_Line]) -> int:
    """Length of the longest run of list numbers that increase by 1-3."""
    best = run = 0
    last = None
    for ln in lines:
        n = _number(ln.text)
        if n is None:
            continue
        if last is not None and 0 < n - last <= 3:
            run += 1
        else:
            run = 1
        last = n
        best = max(best, run)
    return best


def detect_style(text: str) -> str | None:
    """``"numbered"``, ``"author_year"`` or None (no entry-shaped lines)."""
    lines = _explode([ln for ln in _lines(text) if not _HEADING.match(ln.text)])
    if not lines:
        return None
    score = _numbered_score(lines)
    starts = sum(1 for ln in lines if _ENTRY_START.match(ln.text) and _YEAR.search(ln.text[:160]))
    if score >= 3 or (score >= 2 and score >= starts):
        return "numbered"
    return "author_year" if starts >= 1 else None


_ENTRYISH = re.compile(r"\bdoi\b|10\.\d{4,9}/|(?<!\d)(?:1[6-9]|20)\d{2}[a-z]?(?!\d)|\d+\s*\(\d+\)|\d+[:;,]\s*\d+", re.IGNORECASE)


def entry_density(text: str) -> float:
    """Share of the non-blank lines that look like bibliography lines: a list
    number, an author-list opening, a year, a DOI or a volume/page group."""
    lines = [ln for ln in _lines(text) if not _HEADING.match(ln.text)]
    if not lines:
        return 0.0
    hits = sum(1 for ln in lines if _number(ln.text) is not None or _ENTRY_START.match(ln.text)
               or _ENTRYISH.search(ln.text))
    return hits / len(lines)


def _split_numbered(lines: list[_Line]) -> list[RawEntry]:
    entries: list[tuple[int | None, list[_Line]]] = []
    last: int | None = None
    used: set[int] = set()
    n_bracketed = sum(1 for ln in lines if ln.text.startswith("["))
    for ln in lines:
        n = _number(ln.text)
        starts = False
        if n is not None and n not in used:
            bare = re.fullmatch(r"\d{1,4}", ln.text.strip()) is not None
            # the first number of the section opens the list wherever it starts
            follows_last = last is None or 0 < n - last <= 3
            if ln.text.startswith("["):
                # "[n]" at a line start is an entry label whatever the order the
                # columns were read in (one paper's text runs 1-10, 16-27, 11, 28, ...)
                starts = follows_last or (n - 1) in used or n <= max(2 * n_bracketed, 10)
            elif bare and last is not None:
                # a number alone on its line must follow the last entry exactly:
                # it could be a page number
                starts = n == last + 1
            else:
                # Two columns read across interleave the sequence ("11.", "28.",
                # "12.", "29."): a number whose predecessor is already an entry
                # continues a chain. One missing link is allowed: an entry whose
                # number was not read (an organisation author after a bare BMJ
                # number) must not end the chain.
                starts = follows_last or (n - 1) in used or (n - 2) in used
        if starts:
            entries.append((n, [ln]))
            used.add(n)
            last = n
        elif entries:
            entries[-1][1].append(ln)
        # lines before the first numbered entry are dropped (heading furniture)
    out = []
    for n, lns in entries:
        parts = [_strip_number(lns[0].text)] + [x.text for x in lns[1:]]
        parts = [p for p in parts if p]
        text = _join(parts)
        if text:
            out.append(RawEntry(text, n, lns[0].start, lns[-1].end))
    return out


_ENDS_ENTRY = re.compile(r"(?:[.)\]]|\d|[a-z0-9]/\S*|\.\s*\[[^\]]*\])\s*$")

#: a line holding only list numbers: "1. 2.", "3.", "[4]"
_NUMBERS_ONLY = re.compile(r"^(?:\[?\d{1,4}[\].)]?\s*)+$")


def _detached_numbers(lines: list[_Line]) -> bool:
    """Numbers printed apart from their entries: some layouts come out of
    extraction as a block of list numbers ("1. 2.", "3.", "4.") followed by the
    entries they label, with no number on the entry lines themselves."""
    only = [ln for ln in lines if _NUMBERS_ONLY.match(ln.text)]
    with_text = [ln for ln in lines if _number(ln.text) is not None and not _NUMBERS_ONLY.match(ln.text)]
    return len(only) >= 3 and len(only) > len(with_text)


def _split_detached(lines: list[_Line]) -> list[RawEntry]:
    numbers: list[int] = []
    groups: list[list[_Line]] = []
    prev_number_line = True
    for ln in lines:
        if _NUMBERS_ONLY.match(ln.text):
            numbers += [int(x) for x in re.findall(r"\d{1,4}", ln.text)]
            prev_number_line = True
            continue
        opens = bool(_ENTRY_START.match(ln.text))
        if not groups or (opens and (prev_number_line or _ENDS_ENTRY.search(groups[-1][-1].text))):
            groups.append([ln])
        else:
            groups[-1].append(ln)
        prev_number_line = False
    texts = [(_join([x.text for x in lns]), lns) for lns in groups]
    texts = [(t, lns) for t, lns in texts if t]
    # The number blocks do not come out next to the entries they label (a block
    # "19. 20. 21. 22." can precede entry 6), so a number is never taken from a
    # block. An entry is numbered by its position, and only when the list is
    # complete: as many entries as list numbers, and the numbers are exactly 1..N.
    complete = sorted(numbers) == list(range(1, len(texts) + 1))
    return [RawEntry(t, k if complete else None, lns[0].start, lns[-1].end)
            for k, (t, lns) in enumerate(texts, start=1)]


def _split_author_year(lines: list[_Line]) -> list[RawEntry]:
    groups: list[list[_Line]] = []
    for ln in lines:
        opens = bool(_ENTRY_START.match(ln.text)) and bool(_YEAR.search(ln.text[:200]))
        if not groups:
            if opens or _ENTRY_START.match(ln.text):
                groups.append([ln])
            continue
        prev = groups[-1][-1].text
        prev_closed = bool(_ENDS_ENTRY.search(prev))
        cur = " ".join(x.text for x in groups[-1])
        cur_has_year = bool(_YEAR.search(cur))
        if opens and (prev_closed or ln.blank_before) and cur_has_year and len(cur) >= 25:
            groups.append([ln])
        elif opens and prev_closed and not cur_has_year and len(groups) == 1:
            groups = [[ln]]  # furniture before the first entry ("Funding", a name, a country)
        else:
            groups[-1].append(ln)
    out = []
    for lns in groups:
        text = _join([x.text for x in lns])
        if not text:
            continue
        pieces = _split_inline(text)
        if len(pieces) == 1:
            out.append(RawEntry(text, None, lns[0].start, lns[-1].end))
            continue
        # offsets of the pieces: proportional inside the group's span (the joined
        # text differs from the source only by whitespace)
        span = lns[-1].end - lns[0].start
        for a, b in pieces:
            s = lns[0].start + round(a * span / max(len(text), 1))
            e = lns[0].start + round(b * span / max(len(text), 1))
            out.append(RawEntry(text[a:b].strip(), None, s, e))
    return out


_INLINE_GAP = re.compile(r"(?<=\S)\s+(?=[^\W\d_])")
_GAP_BEFORE = re.compile(r"(?:[.)\]\d]|(?:doi\.org/|doi:\s?|https?://|\b10\.\d{4,9}/)\S*)$", re.IGNORECASE)


def _split_inline(text: str) -> list[tuple[int, int]]:
    """Entries that extraction ran together on one line.

    A boundary is a sentence end followed by a complete author list and then a
    year -- "(2020)." straight after the names (APA) or a bare "2020." -- which
    is the shape of an entry opening, not of a title or a journal name.
    """
    from .parse import _BARE_YEAR, _PAREN_YEAR, _parse_authors

    cuts = [0]
    for m in _INLINE_GAP.finditer(text):
        pos = m.end()
        before = text[cuts[-1]:m.start()]
        # a gap after a sentence end, or after a DOI / URL (which can end in a letter)
        if len(before) < 25 or not _YEAR.search(before) or not _GAP_BEFORE.search(before):
            continue
        authors, _et_al, end, _shape = _parse_authors(text[pos:pos + 400])
        if not authors:
            continue
        after = text[pos + end:pos + end + 40]
        if _PAREN_YEAR.match(after) or (_BARE_YEAR.match(after) and len(authors) >= 1 and end >= 4):
            cuts.append(pos)
    cuts.append(len(text))
    return [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)]


def _opens_entry(line: str) -> bool:
    """A line that opens like a bibliography entry: a list label, or an author
    list followed straight away by a year."""
    from .parse import _BARE_YEAR, _PAREN_YEAR, _parse_authors

    if _NUM_START.match(line) and not re.fullmatch(r"\s*\d{1,4}\s*", line):
        return True
    if not _ENTRY_START.match(line):
        return False
    authors, _et_al, end, _shape = _parse_authors(line[:400])
    if not authors:
        return False
    after = line[end:end + 40]
    return bool(_PAREN_YEAR.match(after) or _BARE_YEAR.match(after))


def entry_runs(text: str, *, min_entries: int = 5, split_kinds: bool = False) -> list[tuple[int, int]]:
    """Every stretch of ``text`` made of entry-opening lines (gaps of at most
    three other lines between them) holding at least ``min_entries`` openers,
    as ``(start, end)``. With ``split_kinds`` a run also ends where the openers
    change kind (list numbers vs author names), so numbered notes next to an
    author-year list are two runs; without it a numbered list whose wrapped
    lines open like author names stays one run."""
    lines = _lines(text)
    runs: list[tuple[int, int, int]] = []  # (count, first index, last index)
    run_first = None
    kind = None
    count = gap = 0
    last_i = -1
    for i, ln in enumerate(lines):
        if _opens_entry(ln.text):
            k = "num" if _NUM_START.match(ln.text) else "name"
            if run_first is None or gap > 3 or (split_kinds and k != kind):
                if run_first is not None:
                    runs.append((count, run_first, last_i))
                run_first, count, kind = i, 0, k
            count += 1
            gap = 0
            last_i = i
        else:
            gap += 1
    if run_first is not None:
        runs.append((count, run_first, last_i))
    out = []
    for count, a, b in runs:
        if count < min_entries:
            continue
        # carry the last entry's continuation lines (up to three)
        end_idx = b
        while (end_idx + 1 < len(lines) and end_idx + 1 <= b + 3
               and not _HEADING.match(lines[end_idx + 1].text)
               and not _ENDS_ENTRY.search(lines[end_idx].text)):
            end_idx += 1
        out.append((count, lines[a].start, lines[end_idx].end))
    return [(a, b) for _c, a, b in out]


#: A place the last entry could end: after ".", ")", "]" or a digit, before a capital.
_TAIL_CUT = re.compile(r"(?<=[.)\]\d])\s+(?=[A-ZÀ-Þ•])")


_VOLUME_PAGES = re.compile(r"\d+\s*\(\d+\)|\d+\s*[:;,]\s*\d+")


def _trim_last(entries: list[RawEntry], text: str) -> list[RawEntry]:
    """Cut back matter (publisher notes, author biographies) off the last entry.

    Nothing marks where a bibliography ends, so whatever follows it -- when the
    section runs to the end of the document -- is glued to the last entry. The
    entry is cut at the first sentence boundary where the text before it already
    reads as a complete reference (authors or a year, plus a container with a
    volume, page or DOI) and the text after it is longer than any entry should be.
    """
    if len(entries) < 2:
        return entries
    from .parse import parse_reference

    last = entries[-1]
    lengths = sorted(len(e.text) for e in entries[:-1])
    median = lengths[len(lengths) // 2]
    limit = max(1.5 * median, 150)
    if len(last.text) <= 2 * median or len(last.text) <= limit:
        return entries
    for m in _TAIL_CUT.finditer(last.text):
        head, rest = last.text[:m.start()], last.text[m.end():]
        if len(rest) <= limit:
            break
        # what follows reads like more entries (years plus volume / page
        # numbers), not like back matter: the entries ran together, keep them
        if len(_YEAR.findall(rest)) >= 3 and len(_VOLUME_PAGES.findall(rest)) >= 3:
            break
        if not _YEAR.search(head):
            continue
        r = parse_reference(head)
        if not (r.container and (r.volume or r.first_page or r.doi)):
            continue
        # the joined text lost line breaks (and a list number), so find where
        # the head ends in the section text ignoring whitespace
        tail = re.sub(r"\s+", "", head)[-25:]
        found = re.compile(r"\s*".join(map(re.escape, tail))).search(text, last.char_start, last.char_end)
        end = found.end() if found else last.char_start + len(head)
        return entries[:-1] + [RawEntry(head, last.number, last.char_start, end)]
    return entries


def split_entries(text: str) -> list[RawEntry]:
    """Split one references section into entries (offsets index ``text``)."""
    lines = _explode([ln for ln in _lines(text) if not _HEADING.match(ln.text)])
    if not lines:
        return []
    style = detect_style(text)
    if style == "numbered":
        numbered = _split_numbered(lines)
        if _detached_numbers(lines):
            # numbers alone on their lines either sit next to their entries (the
            # sequence splitter reads that) or come in blocks apart from them; the
            # detached reading splits at every entry-like line, so it wins only when
            # the sequence reading collapsed (a block of numbers yields one entry)
            detached = _split_detached(lines)
            if 2 * len(numbered) < len(detached):
                # the numbers may also be note numbers above an author-year list
                author_year = _split_author_year(lines)
                return _trim_last(author_year if len(author_year) >= len(detached) else detached, text)
        return _trim_last(numbered, text)
    if style == "author_year":
        return _trim_last(_split_author_year(lines), text)
    return []
