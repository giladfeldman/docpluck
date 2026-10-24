"""Public data model for reference entries and in-text citations."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Literal

#: How a bibliography identifies its entries. ``numbered`` lists print a number
#: ("[12]", "12.") that the text cites; ``author_year`` lists are cited by name
#: and year.
ReferenceStyle = Literal["numbered", "author_year"]

#: The printed form of one in-text citation.
CitationKind = Literal["numeric_bracket", "numeric_paren", "numeric_superscript", "author_year"]


def _to_json(value):
    if isinstance(value, tuple):
        return [_to_json(v) for v in value]
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


class _DictMixin:
    def to_dict(self) -> dict:
        """JSON-ready view: every field, tuples as lists."""
        return {f.name: _to_json(getattr(self, f.name)) for f in fields(self)}


@dataclass(frozen=True)
class ReferenceAuthor(_DictMixin):
    """One author as printed. ``family`` is the surname (particles kept:
    "van der Berg"); ``given`` is the given names or initials as printed, or
    ``None``. An organisation author has ``family`` set to its full name and
    ``given`` None."""

    family: str
    given: str | None = None


@dataclass(frozen=True)
class Reference(_DictMixin):
    """One parsed bibliography entry.

    ``raw_text`` is the entry as printed (line breaks joined, any list number
    removed). Every parsed field is ``None`` (or empty) when the entry does not
    print it or the parser could not place it; nothing is invented.
    """

    reference_id: str           # the printed number for a numbered list, else "r<n>"
    raw_text: str
    number: int | None          # printed list number, numbered lists only
    authors: tuple[ReferenceAuthor, ...]
    et_al: bool                 # the author list ends with "et al." / "..."
    year: str | None            # four digits ("2020"); None for "n.d." or none printed
    year_suffix: str | None     # same-author disambiguator: "a" in "2020a"
    title: str | None
    container: str | None       # journal, book (for a chapter), proceedings
    volume: str | None
    issue: str | None
    first_page: str | None      # or article number ("e0123", "100501")
    last_page: str | None       # as printed: "47" in "837-47"
    doi: str | None             # bare, lower-cased: "10.1234/abc"
    url: str | None
    pmid: str | None
    char_start: int             # offset of the entry in the text it was split from
    char_end: int


@dataclass(frozen=True)
class Citation(_DictMixin):
    """One in-text citation and the bibliography entries it cites.

    A grouped or ranged citation cites several entries: "[3-6]" has four
    ``reference_ids``, "(Smith, 2019; Lee, 2020)" has two. ``unresolved`` holds
    the parts that match no entry (a number past the end of the list, an
    author-year pair the bibliography does not contain); a citation whose
    ``reference_ids`` is empty is an orphan.
    """

    marker_text: str
    char_start: int             # offset into CitationAnalysis.text
    char_end: int
    kind: CitationKind
    reference_ids: tuple[str, ...]
    unresolved: tuple[str, ...] = ()


@dataclass(frozen=True)
class CitationAnalysis(_DictMixin):
    """Bibliography + in-text citation linkage for one document."""

    references: tuple[Reference, ...]
    citations: tuple[Citation, ...]
    style: ReferenceStyle | None            # None when no bibliography was found
    uncited_reference_ids: tuple[str, ...]  # entries no citation points at
    orphan_citations: tuple[str, ...]       # marker texts that resolve to nothing
    duplicate_reference_groups: tuple[tuple[str, ...], ...]  # one work listed twice
    text: str                               # the text citations were searched in
    references_version: str
