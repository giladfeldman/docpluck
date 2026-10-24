"""Parse one bibliography entry string into fields.

Deterministic heuristics, no model. The order of operations:

1. identifiers (DOI, URL, PMID / PMCID, database tags) are cut out first, so
   their digits and dots cannot be mistaken for a volume or a title end;
2. the author block is consumed from the start of the entry by a small name
   grammar that tries each of the common name shapes (APA / Nature
   ``Surname, I. J.``, Vancouver ``Surname IJ``, IEEE ``I. J. Surname``,
   Chicago/ASA ``Surname, Given ... and Given Surname``, an organisation);
3. the year is read where the style puts it -- ``(2020a)`` straight after the
   authors (APA), a bare ``2020.`` after them (AOM, ASA, Harvard), or inside the
   source (Vancouver ``2020;12:45``, Nature ``(2020)`` at the end);
4. the title is the next sentence (or the quoted string, IEEE / ASA);
5. the source -- container, volume, issue, pages -- is read from what remains.

A field the parser cannot place is left ``None``.
"""

from __future__ import annotations

import re

from .types import Reference, ReferenceAuthor

_L = r"[^\W\d_]"  # any letter
_DASH = r"[\-‐‑‒–—]"

# --------------------------------------------------------------------------- identifiers
_DOI = re.compile(
    r"(?:\(?\s*(?:https?://)?(?:dx\.)?doi\.org/|\(?\s*\bdoi\s*:?\s*|\bDOI\s*:?\s*)?"
    r"(10\.\d{4,9}/[^\s\"“”<>]+)",
    re.IGNORECASE,
)
_URL = re.compile(r"(?:(?:Available|Retrieved|Retreived|Accessed)\s+(?:at|from|online)\s*:?\s*)?(?:<\s*)?((?:https?://|www\.)[^\s<>\"]+)", re.IGNORECASE)
_PMID = re.compile(r"\[?\s*(?:PMID|PubMed(?:\s+PMID)?)\s*:?\s*(\d{4,9})\s*\]?", re.IGNORECASE)
_PMCID = re.compile(r"\[?\s*PMC(?:ID)?\s*:?\s*PMC\d+\s*\]?", re.IGNORECASE)
_DB_TAGS = re.compile(
    r"\[\s*(?:PMC free article|Google Scholar|CrossRef|Crossref|PubMed|DOI|Web of Science|Scopus|"
    r"Ref list|Medline|CAS|ISI)\s*\]|\b(?:Google Scholar|CrossRef|Crossref)\b(?=\s*$)",
    re.IGNORECASE,
)
_ACCESSED = re.compile(r"[\[(]?\s*(?:accessed|cited|retrieved)\s*(?:on\s*)?:?\s*[\w ,]{3,30}\d{4}\s*[\])]?\.?", re.IGNORECASE)


def _clean_doi(doi: str) -> str:
    doi = doi.rstrip(".,;:")
    # drop an unbalanced closing bracket the citation wrapped round the DOI
    while doi and doi[-1] in ")]" and doi.count("(" if doi[-1] == ")" else "[") < doi.count(doi[-1]):
        doi = doi[:-1].rstrip(".,;:")
    return doi.lower()


def _cut_identifiers(text: str) -> tuple[str, str | None, str | None, str | None]:
    doi = url = pmid = None
    # extraction can put a space after the scheme or inside "doi. org"
    text = re.sub(r"\bhttp\s+s:", "https:", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(https?):\s+//", r"\1://", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(dx\.)?doi\.\s+org/", r"\1doi.org/", text, flags=re.IGNORECASE)
    text = re.sub(r"(doi\.org/|doi:\s?)1\s+0\.(\d{4,9}/)", r"\g<1>10.\2", text, flags=re.IGNORECASE)
    # A DOI broken by a space where the printed line wrapped ("10.1161/ CIRC...",
    # "10.1016/j. ijcard...") is rejoined when the break follows "/" or "." and
    # the rest of the entry is that one token -- a DOI is printed last.
    text = re.sub(r"(\b10\.\d{4,9}/(?:[^\s\"“”<>]*[./])?)\s+([^\s\"“”<>]+\.?)\s*$", r"\1\2", text)
    m = _DOI.search(text)
    if m:
        doi = _clean_doi(m.group(1))
        end = m.start(1) + len(m.group(1))
        text = text[: m.start()] + " " + text[end:]
        text = re.sub(r"\(\s*\)", " ", text)
        # the label of a DOI printed as a link: "DOI: https://doi.org/..."
        text = re.sub(r"\bDOI\s*:?\s*(?=$|\s*$)|\bDOI\s*:\s*", " ", text)
    m = _URL.search(text)
    if m:
        url = m.group(1).rstrip(".,;:>)")
        text = text[: m.start()] + " " + text[m.end():]
    m = _PMID.search(text)
    if m:
        pmid = m.group(1)
        text = text[: m.start()] + " " + text[m.end():]
    text = _PMCID.sub(" ", text)
    # a label whose value the text lost ("PMID:" with the number on a dropped line)
    text = re.sub(r"\b(?:PMID|PMCID)\s*:?(?=\s|$)", " ", text)
    text = _DB_TAGS.sub(" ", text)
    text = _ACCESSED.sub(" ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    text = re.sub(r"(?:[.,;:]\s*){2,}$", ".", text)
    return text.strip(" ,;"), doi, url, pmid


# --------------------------------------------------------------------------- authors
_PARTICLE = r"(?:van|von|der|den|de|del|della|degli|di|da|du|dos|das|le|la|st\.?|ter|ten|bin|ibn|al|el|y|zu|vom|op|'t)"
_FAM_WORD = rf"(?:{_L}[\w'’`]*(?:-{_L}[\w'’`]*)*)"
_FAMILY = rf"(?:(?:{_PARTICLE}[\s'’]+)*{_FAM_WORD}(?:\s+(?:{_PARTICLE}\s+)*{_FAM_WORD}){{0,2}}?)"
_INIT = r"(?:[A-ZÀ-ÞĀ-ſ][a-z]?\.)"
_INITIALS = rf"(?:{_INIT}(?:\s?{_DASH}?\s?{_INIT}){{0,3}})"
_VINITS = r"(?:[A-ZÀ-Þ]{1,4}(?:-[A-Z])?)"
_GIVEN_FULL = rf"(?:[A-ZÀ-Þ]{_L}+(?:{_DASH}{_L}+)?(?:\s+(?:{_INIT}|[A-ZÀ-Þ]{_L}+)){{0,2}})"

_ETAL = re.compile(r"^,?\s*(?:et\s*al\.?|and\s+others|et\s+alii)", re.IGNORECASE)
_ELLIPSIS = re.compile(r"^,?\s*(?:\.\s?\.\s?\.|…)\s*")
_SEP = re.compile(r"^(?:\s*,\s*(?:&|and)\s+|\s*,\s*|\s*;\s*|\s+&\s+|\s+and\s+)")

# One pattern per name shape; each matched at the current position.
_SHAPES = {
    # "Smith, J. A." / "van der Berg, C.-H."
    "inv_init": re.compile(rf"(?P<fam>{_FAMILY}),\s*(?P<giv>{_INITIALS})"),
    # "Smith JA" / "van der Berg C"
    "vanc": re.compile(rf"(?P<fam>{_FAMILY})\s+(?P<giv>{_VINITS})(?=[,.;:]|\s+(?:et\s+al|and|&)\b|\s*\(|\s*$)"),
    # "J. A. Smith"
    "init_first": re.compile(rf"(?P<giv>{_INITIALS})\s*(?P<fam>{_FAMILY})(?=\s*[,;:]|\s+(?:and|&)\s|\s*\(|\s*[.\"“]|\s*$)"),
    # "Smith, John" (first author, Chicago / ASA / MLA)
    "inv_full": re.compile(rf"(?P<fam>{_FAMILY}),\s+(?P<giv>{_GIVEN_FULL})(?=\s*[,.;(]|\s+(?:and|&)\s)"),
    # "John Smith" (later authors, Chicago / ASA)
    "full": re.compile(rf"(?P<giv>{_GIVEN_FULL})\s+(?P<fam>{_FAMILY})(?=\s*[,.;(]|\s+(?:and|&)\s|\s*$)"),
    # "Smith John" / "Smith John P." (ASA variant: surname first, no comma);
    # accepted only when the names are followed by a bare year (see _parse_authors)
    "sur_giv": re.compile(
        rf"(?P<fam>(?:{_PARTICLE}\s+)*{_FAM_WORD})\s+(?P<giv>{_GIVEN_FULL})(?=\s*[,.;]|\s+(?:and|&)\s|(?<=\.)\s)"
    ),
}
_FOLLOWERS = {
    "inv_init": ("inv_init",),
    "vanc": ("vanc",),
    "init_first": ("init_first",),
    "inv_full": ("full", "inv_full"),
}
_NOT_NAME = re.compile(
    r"^(?:the|a|an|in|on|of|and|for|from|with|to|journal|proceedings|vol|no|pp|eds?|editors?|press|university)$",
    re.IGNORECASE,
)


def _plausible_family(fam: str) -> bool:
    words = fam.split()
    if not words or len(words) > 4:
        return False
    head = words[-1]
    if _NOT_NAME.match(head) or _NOT_NAME.match(words[0]):
        return False
    return head[:1].isupper() or "-" in head


def _consume(text: str, first: str) -> tuple[list[ReferenceAuthor], bool, int]:
    """Consume names of shape `first` (then its followers) from text start."""
    authors: list[ReferenceAuthor] = []
    pos = 0
    et_al = False
    shapes = (first,)
    while True:
        rest = text[pos:]
        m = None
        for shape in shapes:
            cand = _SHAPES[shape].match(rest)
            if cand and _plausible_family(cand.group("fam")):
                m = cand
                break
        if m is None:
            break
        fam = re.sub(r"\s+", " ", m.group("fam")).strip()
        giv = re.sub(r"\s+", " ", m.group("giv")).strip()
        authors.append(ReferenceAuthor(fam, giv or None))
        pos += m.end()
        shapes = _FOLLOWERS.get(first, (first,))
        rest = text[pos:]
        e = _ETAL.match(rest)
        if e:
            et_al = True
            pos += e.end()
            break
        el = _ELLIPSIS.match(rest)
        if el:
            et_al = True
            pos += el.end()
            continue
        s = _SEP.match(rest)
        if not s:
            break
        # a separator must lead to another name; otherwise stop before it
        nxt = text[pos + s.end():]
        if not any(_SHAPES[sh].match(nxt) for sh in shapes) and not _ETAL.match(nxt):
            break
        pos += s.end()
    return authors, et_al, pos


_ORG = re.compile(
    r"(?P<org>[A-Z][\w&'’\-]*(?:[\s,]+(?:of|for|and|&|the|on|in|de|des|der|für|[A-Z][\w&'’\-.]*|\([A-Z]{2,}\))){0,12}?)"
    r"(?=\s*[.(]|\s*,\s*(?:\(?(?:1[6-9]|20)\d{2})|\s+(?:1[6-9]|20)\d{2}\b)"
)


_AFTER_SUR_GIV = re.compile(r"^\s*\.{0,2}\s*(?:1[6-9]|20)\d{2}[a-z]?\b")


def _parse_authors(text: str) -> tuple[list[ReferenceAuthor], bool, int, str]:
    best: tuple[list[ReferenceAuthor], bool, int, str] = ([], False, 0, "")
    for shape in ("inv_init", "vanc", "init_first", "inv_full"):
        authors, et_al, end = _consume(text, shape)
        if not authors:
            continue
        # prefer the reading that consumes more of the entry, then more names
        key = (end, len(authors))
        if key > (best[2], len(best[0])):
            best = (authors, et_al, end, shape)
    # surname-first names without a comma read like an organisation or a title,
    # so they win only when a bare year follows them directly
    authors, et_al, end = _consume(text, "sur_giv")
    if authors and end >= best[2] and _AFTER_SUR_GIV.match(text[end:]):
        return authors, et_al, end, "sur_giv"
    if best[0]:
        return best
    m = _ORG.match(text)
    if m and len(m.group("org")) >= 3:
        org = m.group("org").strip(" ,.")
        return [ReferenceAuthor(org, None)], False, m.end(), "org"
    return [], False, 0, ""


# --------------------------------------------------------------------------- year
_YEAR_RE = r"(?:1[6-9]\d{2}|20\d{2})"
_PAREN_YEAR = re.compile(
    rf"^\s*[.,]?\s*\(\s*(?P<y>{_YEAR_RE})(?P<s>[a-z])?(?:{_DASH}\d{{2,4}})?(?:,\s*[^)]{{1,30}})?\s*\)\s*[.,:]?|"
    rf"^\s*[.,]?\s*\(\s*(?P<nd>n\.\s?d\.|in press|forthcoming)(?:{_DASH}?(?P<nds>[a-z]))?\s*\)\s*[.,:]?",
    re.IGNORECASE,
)
_BARE_YEAR = re.compile(rf"^\s*[.,]?\s*(?P<y>{_YEAR_RE})(?P<s>[a-z])?(?:,\s*[A-Z][a-z]+(?:\s\d{{1,2}})?)?\s*[.,:]?(?=\s|$)")


# --------------------------------------------------------------------------- source
# a page, or an e-locator / article number ("e0238083", "zsab030", "S61")
_PAGES = rf"(?P<fp>[A-Za-z]{{0,5}}\d+[A-Za-z]{{0,2}})(?:\s*{_DASH}+\s*(?P<lp>[A-Za-z]{{0,5}}\d+[A-Za-z]{{0,2}}))?"
_SOURCE_PATTERNS = [
    # Vancouver / AMA: "Journal. 2020 Jan 5;12(3):45-67" (year may be absent here)
    re.compile(
        rf"^(?P<venue>.+?)[.,]?\s+(?P<y>{_YEAR_RE})(?P<s>[a-z])?(?:\s+[A-Z][a-z]{{2,8}}\.?(?:{_DASH}[A-Z][a-z]{{2,8}})?(?:\s+\d{{1,2}})?)?\s*"
        rf"(?:;\s*(?P<vol>[\w.]+)?\s*(?:\((?P<iss>[^)]{{1,20}})\))?\s*(?::\s*{_PAGES})?)?\s*[.;]?\s*$"
    ),
    # Nature: "Lancet 398, 223-237 (2021)" / "Nat. Med. 1-10 (2022)"
    re.compile(
        rf"^(?P<venue>.+?)\s+(?:(?P<vol>\d+[A-Za-z]?),\s*)?{_PAGES}\s*\((?P<y>{_YEAR_RE})(?P<s>[a-z])?\)\s*\.?\s*$"
    ),
    # APA / AOM / Harvard: "Journal, 12(3), 45-67" / "Journal, 6: 351-354" / "Journal 48, 11-22"
    re.compile(
        rf"^(?P<venue>.+?)(?:,|\s)\s*(?P<vol>\d+[A-Za-z]?)\s*(?:\((?P<iss>[^)]{{1,20}})\))?"
        rf"\s*(?:(?:[,:]|(?<=\))\.)\s*(?:pp?\.\s*)?{_PAGES})?\s*[.;]?\s*$"
    ),
    # ASA: "American Journal of Sociology 122(5):1448-84"
    re.compile(
        rf"^(?P<venue>.+?)\s+(?P<vol>\d+)\s*(?:\((?P<iss>[^)]{{1,20}})\))?\s*:\s*{_PAGES}\s*[.;]?\s*$"
    ),
]
_IN_BOOK = re.compile(r"^(?:In:?\s+)(?P<book>.+)$", re.IGNORECASE)
_PP = re.compile(rf"\(?\bpp?\.\s*{_PAGES}\)?")


def _strip_end(s: str | None) -> str | None:
    if s is None:
        return None
    s = s.strip(" ,;:")
    s = re.sub(r"\.$", "", s).strip()
    return s or None


_ABBREV = re.compile(
    r"(?:[A-Z]|vs|e\.g|i\.e|cf|al|St|Dr|Mr|Mrs|Ms|no|No|vol|Vol|ed|Ed|eds|Eds|pp|Inc|Ltd|Co|U\.S|U\.K|Jr|Sr)"
)


def _title_candidates(rest: str) -> list[tuple[str | None, str]]:
    """Every plausible (title, remainder) split of `rest`, earliest first.

    The quoted string when the entry quotes its title (IEEE, ASA); otherwise
    each sentence end (". " / "? " / "! ", not after an initial or a common
    abbreviation). The caller picks the split whose remainder reads best as a
    source, which is what lets a title keep a "?" or a subtitle sentence.
    """
    rest = rest.lstrip(" .,:;")
    q = re.match(r"^[\"“”‘'](?P<t>.+?)[,.]?[\"”’'](?:\s*[,.]?\s*)(?P<rest>.*)$", rest)
    if q and len(q.group("t")) > 3:
        return [(q.group("t").strip(" ,."), q.group("rest"))]
    out: list[tuple[str | None, str]] = []
    for m in re.finditer(r"([.?!])(?:\s+|$)", rest):
        before = rest[: m.start()]
        tail = re.search(r"(\S+)$", before)
        word = tail.group(1) if tail else ""
        if m.group(1) == "." and _ABBREV.fullmatch(word):
            continue
        title = before.strip()
        if m.group(1) in "?!":
            title = title + m.group(1)
        if len(title) < 3:
            continue
        out.append((title, rest[m.end():]))
    out.append((None, rest))
    return out


def _split_title(rest: str) -> tuple[str | None, str]:
    """Title = the quoted string, else the first sentence of `rest`."""
    return _title_candidates(rest)[0]


_BAD_VENUE = re.compile(r"\bvol\.|\bno\.\s*\d|\bpp\.|\d+\s*\(\s*\d|\d+\s*[:;]\s*\d|[a-z]{4,}[.?!]\s+[A-Z][a-z]")


def _source_quality(info: dict) -> int:
    q = 0
    v = info.get("venue")
    if v:
        q += 1
        if _BAD_VENUE.search(v):
            q -= 3
    if info.get("vol"):
        q += 2
    if info.get("fp"):
        q += 2
    if info.get("iss"):
        q += 1
    return q


_IEEE_HEAD = re.compile(r"^(?P<venue>.+?),\s*(?=(?:vol|no|pp|Art)\.)")


def _parse_ieee_tail(tail: str) -> dict:
    out: dict = {}
    m = re.search(r"\bvol\.\s*([\w.]+)", tail)
    if m:
        out["vol"] = m.group(1).rstrip(".")
    m = re.search(r"\bno\.\s*([\w/\-‐‑‒–—]+)", tail)
    if m and not re.search(r"Art\.\s*no\.\s*" + re.escape(m.group(1)), tail):
        out["iss"] = m.group(1)
    m = re.search(rf"(?:\bpp?\.|Art\.\s*no\.)\s*{_PAGES}", tail)
    if m:
        out["fp"], out["lp"] = m.group("fp"), m.group("lp")
    m = re.search(rf"(?<!\d)({_YEAR_RE})(?!\d)", tail)
    if m:
        out["y"] = m.group(1)
    return out


def _parse_source(src: str) -> dict:
    out: dict = {}
    src = src.strip(" .,;")
    if not src:
        return out
    m = _IN_BOOK.match(src)
    if m:
        book = m.group("book")
        pp = _PP.search(book)
        if pp:
            out["fp"], out["lp"] = pp.group("fp"), pp.group("lp")
            book = book[: pp.start()] + book[pp.end():]
        # drop the editor list: "P. Delacroix & V. Kowalczyk (Eds.), Title"
        book = re.sub(r"^.*?\((?:Eds?|Hrsg|eds?)\.?\)\s*,?\s*", "", book)
        venue, _ = _split_title(book)
        out["venue"] = _strip_end(venue or book.split(".")[0])
        return out
    m = _IEEE_HEAD.match(src)
    if m:
        out = _parse_ieee_tail(src[m.end():])
        out["venue"] = _strip_end(m.group("venue"))
        return out
    best: dict | None = None
    for pat in _SOURCE_PATTERNS:
        m = pat.match(src)
        if not m:
            continue
        gd = m.groupdict()
        venue = _strip_end(gd.get("venue"))
        if not venue or not re.search(_L, venue):
            continue
        cand = {"venue": venue}
        for k in ("vol", "iss", "fp", "lp", "y", "s"):
            if gd.get(k):
                cand[k] = gd[k]
        if best is None or _source_quality(cand) > _source_quality(best):
            best = cand
    if best is not None and _source_quality(best) > 0:
        return best
    pp = _PP.search(src)
    if pp:
        out["fp"], out["lp"] = pp.group("fp"), pp.group("lp")
        src = src[: pp.start()]
    # a trailing "(2020)" or ", 2020" year
    y = re.search(rf"[\s,(]({_YEAR_RE})([a-z])?\)?\.?\s*$", src)
    if y:
        out["y"], out["s"] = y.group(1), y.group(2)
        src = src[: y.start()]
    v = _strip_end(src.split(". ")[0]) if src else None
    if v and re.search(_L, v):
        out["venue"] = v
    return out


# --------------------------------------------------------------------------- entry
def parse_reference(raw: str, *, reference_id: str = "r1", number: int | None = None,
                    char_start: int = 0, char_end: int | None = None) -> Reference:
    """Parse one printed bibliography entry into a :class:`Reference`."""
    raw_text = re.sub(r"\s+", " ", raw).strip()
    text, doi, url, pmid = _cut_identifiers(raw_text)

    authors, et_al, a_end, _shape = _parse_authors(text)
    rest = text[a_end:]
    year = suffix = None
    # a group author after the personal names: "..., et al; SAVE Investigators."
    g = re.match(r"^\s*;\s*[^.;]{3,150}?(?:Group|Investigators|Consortium|Collaborat\w*|Committee|Team|Network|"
                 r"Study|Writing|Working|Coordinators|Society|Association)[^.;]{0,60}\.", rest)
    if authors and g:
        rest = rest[g.end():]

    m = _PAREN_YEAR.match(rest)
    if m:
        year, suffix = m.group("y"), m.group("s") or m.group("nds")
        rest = rest[m.end():]
    else:
        m = _BARE_YEAR.match(rest)
        if m and authors:
            year, suffix = m.group("y"), m.group("s")
            rest = rest[m.end():]

    # Pick the title/source split whose source reads best (earliest on a tie).
    title, src, info = None, rest, {}
    best_q = None
    for t, r in _title_candidates(rest):
        cand = _parse_source(r)
        q = _source_quality(cand)
        if t is not None and re.fullmatch(r"[\W\d]*", t):
            continue
        if best_q is None or q > best_q:
            title, src, info, best_q = t, r, cand, q
    # a "title" that is really the source ("Journal, 12, 45-67.") -- no title printed
    if title and not src.strip(" .") and re.search(r"\d", title):
        alt = _parse_source(title)
        if alt.get("vol") or alt.get("fp"):
            title, info = None, alt

    venue = info.get("venue")
    # one sentence with no volume, issue or page ("Smith (2012). A web page. <URL>")
    # is a title with no container, not a container with no title
    if title is None and venue and not (info.get("vol") or info.get("iss") or info.get("fp")) \
            and len([t for t, _r in _title_candidates(rest) if t]) <= 1:
        title, venue = venue, None
    if year is None and info.get("y"):
        year, suffix = info["y"], info.get("s") or suffix
    if year is None:
        y = re.search(rf"(?<!\d)({_YEAR_RE})([a-z])?(?!\d)", rest)
        if y:
            year, suffix = y.group(1), y.group(2)

    title = _strip_end(title)
    # Publisher-only remainder for a book: "Oxford University Press" is not a venue.
    if venue and re.search(r"\b(?:Press|Publishers?|Publishing|Verlag|Books|Wiley|Elsevier|Springer|Routledge|Sage|SAGE|Guilford)\b", venue) \
            and not info.get("vol") and not info.get("fp"):
        venue = None

    return Reference(
        reference_id=reference_id,
        raw_text=raw_text,
        number=number,
        authors=tuple(authors),
        et_al=et_al,
        year=year,
        year_suffix=suffix,
        title=title,
        container=venue,
        volume=info.get("vol"),
        issue=info.get("iss"),
        first_page=info.get("fp"),
        last_page=info.get("lp"),
        doi=doi,
        url=url,
        pmid=pmid,
        char_start=char_start,
        char_end=char_end if char_end is not None else char_start + len(raw),
    )
