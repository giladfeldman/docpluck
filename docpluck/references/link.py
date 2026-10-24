"""Find in-text citations and link each to the bibliography entries it cites.

Numeric citations -- "[1]", "[1-3]", "[1, 4]", "[1]-[3]", "(2-4)", and
superscripts that extracted text glues to the word ("stroke3-6", "care,5") --
resolve by list number. Author-year citations -- "(Smith, 2020)",
"(Smith & Lee, 2020; Park et al., 2019a, 2021)", "(Smith, 2020, p. 4)",
"Smith and Lee (2020)", "(Ford et al. 2018)" -- resolve by first-author
surname + year (+ the a/b suffix), using the second author or "et al." to
choose between same-surname, same-year entries.

Superscript and parenthesised numbers are ambiguous in plain text (an exponent,
an equation number, an enumeration), so they are searched only when the
bibliography is numbered, only where they resolve to list numbers, and only
when bracket citations are not the paper's own form.
"""

from __future__ import annotations

import bisect
import re
import unicodedata
from collections import defaultdict

from .types import Citation, Reference

_DASHES = r"\-‐‑‒–—"
_D = f"[{_DASHES}]"
_YEAR = r"(?:1[6-9]\d{2}|20\d{2})"


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower().translate(str.maketrans({"ß": "ss", "ø": "o", "æ": "ae", "ł": "l"})))


# --------------------------------------------------------------------------- numeric
def _expand_numbers(body: str, max_n: int) -> list[int] | None:
    """'1, 3-5' -> [1, 3, 4, 5]; None when any part is not a list number."""
    out: list[int] = []
    for part in re.split(r"\s*[,;]\s*", body.strip()):
        if not part:
            continue
        m = re.fullmatch(rf"(\d{{1,4}})(?:\s*{_D}+\s*(\d{{1,4}}))?", part)
        if not m:
            return None
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        if a < 1 or b < a or b > max_n or b - a > 60:
            return None
        out.extend(range(a, b + 1))
    return out or None


_BRACKET = re.compile(rf"\[\s*(\d{{1,4}}(?:\s*(?:[,;]|{_D}+)\s*\d{{1,4}})*)\s*\](?:\s*{_D}+\s*\[\s*(\d{{1,4}})\s*\])?")
_PAREN_NUM = re.compile(rf"(?<![\w(])\(\s*(\d{{1,3}}(?:\s*(?:[,;]|{_D}+)\s*\d{{1,3}})*)\s*\)")
# A superscript glued to the word or to the punctuation after it.
_SUPER = re.compile(
    rf"(?:(?<=[a-zß-ÿ)\]”’\"'%])|(?<=[a-z)\]][.,;:]))(\d{{1,3}}(?:(?:,|{_D})\d{{1,3}})*)(?=[\s.,;:)\]]|$)"
)
# words that are followed by a glued number for a reason other than a citation
_SUPER_STOP = re.compile(
    r"(?:^|[^a-z])(?:mg|kg|cm|mm|km|ml|mL|ng|nm|µm|um|g|m|s|ms|h|min|yr|wk|cd|ph|h|co|ch|sio|tio|ca|mg|na|fe|zn|iv|ii|vi|ix|xi|fig|figs|table|eq|eqs|step|phase|grade|type|stage|wave|study|exp|item|th|q|p|n|r|t|f|df|x|y|z|v|k|log|ln|exp|sin|cos|tan|e)$",
    re.IGNORECASE,
)


#: a number glued to a personal name ("Mara Ortiz2,", "Tom N. Ashby1 and"); the
#: group "n" is the number
_NAME_MARK = re.compile(
    r"(?:\b[A-ZÀ-Þ][a-zß-ÿ'’\-]+|\b[A-Z]\.)(?:\s+[A-Z]\.)*\s+[A-ZÀ-Þ][\w'’\-]*?[a-zß-ÿ]"
    r"(?P<n>\d{1,3}(?:,\d{1,3})*)(?=\s*(?:[,;.]|\band\b|$))",
    re.MULTILINE,
)


def _numeric_citations(text: str, skip: list[tuple[int, int]], by_number: dict[int, str],
                       allow_super: bool, allow_paren: bool) -> list[Citation]:
    max_n = max(by_number) if by_number else 0
    found: list[Citation] = []

    def inside_skip(a: int) -> bool:
        return any(s <= a < e for s, e in skip)

    def add(m, body: str, kind: str, extra_end: str | None = None):
        if inside_skip(m.start()):
            return
        nums = _expand_numbers(body, max_n)
        if nums is None:
            return
        if extra_end:
            b = int(extra_end)
            if b <= nums[-1] or b > max_n:
                return
            nums = nums + list(range(nums[-1] + 1, b + 1))
        ids = tuple(dict.fromkeys(by_number[n] for n in nums if n in by_number))
        missing = tuple(str(n) for n in nums if n not in by_number)
        found.append(Citation(m.group(0), m.start(), m.end(), kind, ids, missing))

    for m in _BRACKET.finditer(text):
        add(m, m.group(1), "numeric_bracket", m.group(2))
    taken = [(c.char_start, c.char_end) for c in found]

    def free(m) -> bool:
        return not any(s < m.end() and m.start() < e for s, e in taken)

    if allow_paren:
        for m in _PAREN_NUM.finditer(text):
            # "48 (18)": a value and its SD / count in a table row, not a citation
            if free(m) and not re.search(r"\d[\d.,%]*\s*$", text[max(0, m.start() - 12):m.start()]):
                add(m, m.group(1), "numeric_paren")
    if allow_super:
        # affiliation numbers in an author list ("Kai Lund1, Mara Ortiz2, ...") are
        # glued to names exactly like citations; skip a number glued to a personal
        # name when two more such names sit within 150 characters
        name_marks = [m.start("n") for m in _NAME_MARK.finditer(text)]

        def in_author_list(pos: int) -> bool:
            i = bisect.bisect_left(name_marks, pos - 150)
            j = bisect.bisect_right(name_marks, pos + 150)
            return pos in set(name_marks[i:j]) and j - i >= 3

        for m in _SUPER.finditer(text):
            if not free(m):
                continue
            if in_author_list(m.start()):
                continue
            pre = text[max(0, m.start() - 12): m.start()]
            word = re.search(r"([^\W\d_]+)[.,;:]?$", pre)
            if word and _SUPER_STOP.search(word.group(1)):
                continue
            # an identifier: "COVID19", "SARS-CoV-2", "H1N1" -- a word with a capital after
            # its first letter or a digit inside it
            tok = re.search(r"(\S+)$", pre)
            if tok and (re.search(r"\d", tok.group(1)) or re.search(r"[A-Z]{2,}[.,;:]?$", tok.group(1))):
                continue
            add(m, m.group(1), "numeric_superscript")
    found.sort(key=lambda c: c.char_start)
    return found


# --------------------------------------------------------------------------- author-year
_NAME = r"(?:(?:van|von|der|den|de|del|della|di|da|du|dos|le|la|ter|ten|al|el)\s+)*[A-ZÀ-ÞĀ-ſ][\w'’\-]*"
_NAMES = rf"{_NAME}(?:\s+{_NAME})?(?:(?:\s*,\s*{_NAME}(?:\s+{_NAME})?)*\s*,?\s*(?:&|and)\s+{_NAME}(?:\s+{_NAME})?|\s+et\s+al\.?)?"
_YEARS = rf"(?:{_YEAR}[a-z]?|n\.\s?d\.|in press)(?:\s*,\s*(?:{_YEAR}[a-z]?|[a-z](?![a-z])|in press))*"
_NARRATIVE = re.compile(
    rf"(?<![\w(])(?P<names>{_NAMES})(?:['’]s?)?\s*\(\s*(?P<years>{_YEARS})(?:\s*,\s*(?:pp?\.|chap\.|para\.)\s*[\w{_DASHES}]+)?\s*\)"
)
_PAREN = re.compile(r"\(([^()]{4,600}?)\)")
_PREFIX = re.compile(
    r"^(?:(?:e\.\s?g\.|i\.\s?e\.|cf\.|see(?:\s+also)?|for\s+(?:a\s+)?(?:review|reviews|example|discussion|meta-analysis|overview)s?(?:\s*,\s*see)?|also|reviewed\s+in|but\s+see|as\s+in|following|in)\s*,?\s*)+",
    re.IGNORECASE,
)
_BARE = re.compile(rf"(?<![\w(])(?P<names>{_NAMES})\s+(?P<years>{_YEAR}[a-z]?)(?![\w)])")
#: Words that open a parenthesis with a year and are not author names:
#: "(April 2019)", "(Study 2, 2020)", "(Wave 3 2018)".
_NOT_SURNAME = re.compile(
    r"^(?:January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|Spring|Summer|Fall|Autumn|Winter|"
    r"Study|Studies|Experiment|Experiments|Wave|Table|Tables|Figure|Figures|Fig|Appendix|Supplement|"
    r"Version|Since|Until|From|Before|After|Between|During|In|On|At|By|Year|Years|Published|Accessed|"
    r"Retrieved|Data|Census|Survey|Total|Mean|Median|Range|Age|Ages|Born|Circa|Ca|Early|Late|Mid|The|A|An|And|Or|"
    r"See|Cited|Edition|Vol|Volume|Issue|No|Phase|Round|Session|Cohort|Sample|Class|Grade)\b"
)
_PART = re.compile(rf"^(?P<names>{_NAMES})\s*,?\s+(?P<years>{_YEARS})(?:\s*,\s*(?:pp?\.|chap\.|para\.|Study|Experiment)\s*[\w{_DASHES}]+)?\s*$")


def _years(s: str) -> list[tuple[str | None, str | None]]:
    """'2020a, b, 2021' -> [('2020','a'), ('2020','b'), ('2021', None)]"""
    out: list[tuple[str | None, str | None]] = []
    last_year: str | None = None
    for part in re.split(r"\s*,\s*", s.strip()):
        m = re.fullmatch(rf"({_YEAR})([a-z])?", part)
        if m:
            last_year = m.group(1)
            out.append((m.group(1), m.group(2)))
        elif re.fullmatch(r"[a-z]", part) and last_year:
            out.append((last_year, part))
        elif re.fullmatch(r"n\.\s?d\.|in press", part):
            out.append((None, None))
    return out


def _cited_names(names: str) -> tuple[str, str | None, bool, int]:
    """-> (first surname, second surname or None, et_al, number of names)."""
    names = names.strip()
    et_al = bool(re.search(r"\bet\s+al\.?$", names))
    names = re.sub(r"\s+et\s+al\.?$", "", names)
    parts = [p.strip() for p in re.split(r"\s*,\s*(?:&|and)\s+|\s*,\s*|\s+&\s+|\s+and\s+", names) if p.strip()]
    first = parts[0] if parts else names
    second = parts[1] if len(parts) > 1 else None
    return first, second, et_al, len(parts)


class _AuthorYearIndex:
    def __init__(self, refs: list[Reference]):
        self.by_key: dict[tuple[str, str], list[Reference]] = defaultdict(list)
        for r in refs:
            if not r.authors or not r.year:
                continue
            fam = r.authors[0].family
            for key in {_fold(fam), _fold(fam.split()[-1])}:
                if key:
                    self.by_key[(key, r.year)].append(r)

    def resolve(self, first: str, second: str | None, et_al: bool, n_names: int,
                year: str | None, suffix: str | None) -> str | None:
        if year is None:
            return None
        cands: list[Reference] = []
        for key in dict.fromkeys((_fold(first), _fold(first.split()[-1]))):
            for r in self.by_key.get((key, year), []):
                if r not in cands:
                    cands.append(r)
        if not cands:
            return None
        if suffix:
            exact = [r for r in cands if (r.year_suffix or "") == suffix]
            if exact:
                cands = exact
        if len(cands) > 1 and second:
            sec = _fold(second)
            two = [r for r in cands if len(r.authors) > 1 and (_fold(r.authors[1].family) == sec
                                                               or _fold(r.authors[1].family.split()[-1]) == sec)]
            if two:
                cands = two
        if len(cands) > 1:
            if et_al:
                many = [r for r in cands if len(r.authors) >= 3 or r.et_al]
            elif second:
                many = [r for r in cands if len(r.authors) == n_names]
            else:
                many = [r for r in cands if len(r.authors) == 1]
            if many:
                cands = many
        if len(cands) > 1 and not suffix:
            plain = [r for r in cands if not r.year_suffix]
            if plain:
                cands = plain
        return cands[0].reference_id


def _author_year_citations(text: str, skip: list[tuple[int, int]], refs: list[Reference]) -> list[Citation]:
    index = _AuthorYearIndex(refs)
    found: list[Citation] = []

    def inside_skip(a: int) -> bool:
        return any(s <= a < e for s, e in skip)

    def resolve_part(names: str, years: str) -> tuple[list[str], list[str]]:
        first, second, et_al, n = _cited_names(names)
        ids: list[str] = []
        missing: list[str] = []
        for y, s in _years(years):
            rid = index.resolve(first, second, et_al, n, y, s)
            if rid:
                ids.append(rid)
            else:
                missing.append(f"{names.strip()} {y or 'n.d.'}{s or ''}")
        return ids, missing

    # Parenthetical groups first; their spans are then closed to the narrative pass.
    for m in _PAREN.finditer(text):
        if inside_skip(m.start()) or not re.search(_YEAR, m.group(1)):
            continue
        body = re.sub(r"\s+", " ", m.group(1))
        ids: list[str] = []
        missing: list[str] = []
        parsed_any = False
        for part in re.split(r"\s*;\s*", body):
            part = _PREFIX.sub("", part.strip()).strip()
            pm = _PART.match(part)
            if not pm or _NOT_SURNAME.match(pm.group("names")):
                continue
            parsed_any = True
            i, miss = resolve_part(pm.group("names"), pm.group("years"))
            ids += i
            missing += miss
        if parsed_any:
            found.append(Citation(m.group(0), m.start(), m.end(), "author_year",
                                  tuple(dict.fromkeys(ids)), tuple(missing)))
    taken = [(c.char_start, c.char_end) for c in found]
    for m in _NARRATIVE.finditer(text):
        if inside_skip(m.start()) or any(s < m.end() and m.start() < e for s, e in taken):
            continue
        names = re.sub(r"\s+", " ", m.group("names"))
        # a sentence-initial common word is not a name ("In (2020)" cannot occur, but
        # "Table (2020)" can): require the first name to be an author surname somewhere
        first = _cited_names(names)[0]
        if not any(k[0] in (_fold(first), _fold(first.split()[-1])) for k in index.by_key):
            continue
        ids, missing = resolve_part(names, m.group("years"))
        found.append(Citation(m.group(0), m.start(), m.end(), "author_year",
                              tuple(dict.fromkeys(ids)), tuple(missing)))
        taken.append((m.start(), m.end()))
    # Bare "Green and Stevens 1998" (no parentheses): taken only when every year
    # resolves to an entry, since nothing else marks it as a citation.
    for m in _BARE.finditer(text):
        if inside_skip(m.start()) or any(s < m.end() and m.start() < e for s, e in taken):
            continue
        names = re.sub(r"\s+", " ", m.group("names"))
        if _NOT_SURNAME.match(names):
            continue
        ids, missing = resolve_part(names, m.group("years"))
        if ids and not missing:
            found.append(Citation(m.group(0), m.start(), m.end(), "author_year", tuple(dict.fromkeys(ids)), ()))
    found.sort(key=lambda c: c.char_start)
    return found


# --------------------------------------------------------------------------- public
def link_citations(text: str, references, *, exclude_spans=()) -> tuple[Citation, ...]:
    """Find every in-text citation in ``text`` and link it to ``references``.

    ``exclude_spans`` are ``(start, end)`` ranges of ``text`` not to search --
    normally the bibliography itself. A numbered bibliography is cited by
    number; an author-year one by name and year.
    """
    refs = list(references)
    skip = [(int(a), int(b)) for a, b in exclude_spans]
    by_number = {r.number: r.reference_id for r in refs if r.number is not None}
    if by_number and len(by_number) >= len(refs) / 2:
        brackets = sum(1 for m in _BRACKET.finditer(text)
                       if not any(s <= m.start() < e for s, e in skip)
                       and _expand_numbers(m.group(1), max(by_number)))
        allow_alt = brackets < 3
        return tuple(_numeric_citations(text, skip, by_number, allow_super=allow_alt, allow_paren=allow_alt))
    return tuple(_author_year_citations(text, skip, refs))


def duplicate_groups(references) -> tuple[tuple[str, ...], ...]:
    """Groups of entries that list the same work twice (same DOI; else same
    title of 3+ words, year and first author)."""
    groups: dict[tuple, list[str]] = {}
    for r in references:
        if r.doi:
            key: tuple = ("doi", r.doi.lower())
        else:
            words = re.sub(r"\W+", " ", (r.title or "").lower()).split()
            if len(words) < 3:
                continue
            first = _fold(r.authors[0].family) if r.authors else ""
            key = ("t", " ".join(words), r.year or "", first)
        groups.setdefault(key, []).append(r.reference_id)
    return tuple(tuple(g) for g in groups.values() if len(g) > 1)
