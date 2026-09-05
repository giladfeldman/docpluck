"""
docpluck.tables.docx_tables — table extraction from DOCX markup.

WHY THIS IS A DIFFERENT PROBLEM FROM PDF TABLES, AND AN EASIER ONE.
A PDF does not contain tables. It contains glyphs at coordinates, and
`tables/camelot_extract.py` *infers* a grid from them -- which is why that
module carries capture confidence, whitespace ratios, region-driven retries and
a whole family of glyph repairs for a text layer that lies. A DOCX **states**
its grid: `w:tbl` / `w:tr` / `w:tc`, with `w:gridSpan` and `w:vMerge` for spans.
There is nothing to infer and nothing to be confident about. Reading what the
file already says is both more accurate and the project's standing instruction
(CLAUDE.md: "READ WHAT THE FILE ALREADY SAYS BEFORE INVENTING A HEURISTIC").

ENGINE: mammoth, chosen on measurement rather than on the 2026-05 prose that
picked it for body text and was never re-asked about tables. Five candidates
over 16 English DOCX -- 5,091 truth cells, 3,908 statistic-bearing -- scored
two-sided against the OOXML itself:

    pandoc              cell 1.0000  stat 1.0000  fabricated 0   (+100 MB binary)
    mammoth             cell 0.9998  stat 1.0000  fabricated 0   (already shipped)
    docx2python         cell 0.9966  stat 0.9942  fabricated 1
    python-docx         cell 0.9917  stat 0.9893  fabricated 0   (0.0 on 3.6% of docs)
    Word -> PDF -> ours cell 0.0077  stat 0.0072  fabricated 1

Full method, the per-document minima the pooled column hides, and the three
instrument defects the two-sided design caught in its own ground-truth reader:
`docs/BENCHMARKS_docx_engines_2026-09.md`. The two results that decided it:
python-docx's `Document.tables` silently returns NOTHING for tables inside
`w:sdt` content controls (**2 of 55 real documents, 3.6%** -- and content
controls are what journal manuscript templates use), and the PDF-conversion
route re-infers from pixels a grid the DOCX had already stated exactly.

WHAT THIS MODULE DELIBERATELY DOES NOT DO: run the PDF glyph-repair chain.
`cell_cleaning.clean_cell_text` recovers `(cid:0)`-for-minus, `2`-for-minus,
`<`-as-backslash, `<`-as-`b` and `x`-as-`3` -- every one of them an artifact of a
PDF font whose ToUnicode map is broken. A DOCX carries real Unicode and has no
such layer. Measured over the corpus's 13 table-bearing DOCX: **0 occurrences of
`(cid:N)` or NUL, 0 math-alphanumeric styling, 0 Latin ligatures**, so those
repairs could only ever MISFIRE here -- rewriting `[20.45, 20.06]`, which a DOCX
author really typed, into a `[-0.45, -0.06]` the paper never printed. docpluck
extracts and normalizes; it does not fix the paper. What the same measurement
DID find is 78 occurrences of U+2212 in 2 documents, so the one mandatory repair
(hard rule 4 / LESSONS L-004, minus sign to ASCII) is applied and the rest are
not. See `clean_docx_cell_text`, which composes the SAME helpers the PDF chain
uses rather than restating them -- one concept, one table.
"""

from __future__ import annotations

import io
import re
from typing import Optional

from . import Cell, Table
from .captions import TABLE_CAPTION_RE
from .cell_cleaning import (
    decompose_ligatures,
    destyle_math_alphanumeric,
    normalize_cell_whitespace,
)
from .render import cells_to_html
from ..telemetry import record_fallback


# A `Note.` / `*p < .05` paragraph immediately after a table is its footnote.
# `flatten_table` reads caption AND footnote vocabulary to type an unlabelled
# estimate column, so dropping them silently loses effect-size typing rather
# than losing text.
_FOOTNOTE_RE = re.compile(r"^\s*(?:Note[.:]|\*+\s*p\s*[<=]|†|‡)", re.I)


def clean_cell_text(s: str | None) -> str:
    """The repairs a DOCX table cell needs, and no others.

    Composed from the same helpers as `cell_cleaning.clean_cell_text` -- never a
    second copy of them -- so a repair that changes there changes here too. The
    difference is the SELECTION, and the selection is measured:

    * `normalize_cell_whitespace` -- folds U+2212 to ASCII hyphen (hard rule 4;
      78 occurrences across 2 of 13 real DOCX), drops soft hyphens, collapses
      whitespace runs.
    * `destyle_math_alphanumeric` / `decompose_ligatures` -- notation
      canonicalisation that cannot invent a value. Measured 0 occurrences in
      DOCX cells; kept so a DOCX cell and a PDF cell holding the same character
      give the same answer, which `docs/SYMBOL_CONTRACT.md` promises.
    * every PDF glyph-corruption recovery -- EXCLUDED. See the module docstring.

    Idempotent, like its PDF sibling.
    """
    if s is None:
        return ""
    s = destyle_math_alphanumeric(s)
    s = decompose_ligatures(s)
    return normalize_cell_whitespace(s)


class _SpanGrid:
    """Place cells into a row-major grid honouring BOTH colspan and rowspan.

    A merged cell occupies every slot it spans, so the column index of the cells
    AFTER it is the one a consumer sees. Getting this wrong is not cosmetic:
    `tables/flatten.py` binds each value to its column header BY POSITION, so a
    header row that slid one column left publishes a t-statistic labelled `p`.

    Measured while building the benchmark: ignoring `rowspan` on
    10.1027/1618-3169/a000470 -- whose header carries `rowspan=2` on two columns
    -- slid the second header row two columns left, putting `Males`, `Females`,
    `Range` and `Mdn +/- MAD` under the wrong statistics. mammoth emits both
    attributes correctly; the bug was in the reader, and it would have looked
    exactly like an engine defect.
    """

    def __init__(self) -> None:
        self.rows: list[list[str]] = []
        self.header_flags: list[list[bool]] = []
        self._pending: dict[int, tuple[int, str, bool]] = {}

    def add_row(self, cells: list[tuple[str, int, int, bool]]) -> None:
        """`cells` are (text, colspan, rowspan, is_header) in document order."""
        row: list[str] = []
        flags: list[bool] = []
        col = 0

        def _widen(to: int) -> None:
            while len(row) <= to:
                row.append("")
                flags.append(False)

        def drain() -> None:
            nonlocal col
            while col in self._pending:
                left, text, hdr = self._pending[col]
                _widen(col)
                row[col], flags[col] = text, hdr
                if left <= 1:
                    del self._pending[col]
                else:
                    self._pending[col] = (left - 1, text, hdr)
                col += 1

        for text, cspan, rspan, hdr in cells:
            drain()
            for k in range(max(1, cspan)):
                _widen(col)
                # A merged cell contributes its text ONCE, in the slot it starts
                # in; every other slot it occupies is empty. That is exactly how
                # OOXML itself represents a vertical merge (`w:vMerge continue`
                # cells carry no text), so the grid docpluck emits and the grid
                # the file declares agree.
                #
                # Repeating the text instead is not a harmless duplicate: it made
                # a two-row header fold to `Group\x00BR\x00Group`, because
                # `_fold_super_header_rows` concatenates the header rows it is
                # given. A downstream verifier also cannot tell a propagated
                # repeat from a value the table really states twice.
                row[col] = text if k == 0 else ""
                flags[col] = hdr
                if rspan > 1:
                    self._pending[col] = (rspan - 1, "", hdr)
                col += 1
        drain()
        self.rows.append(row)
        self.header_flags.append(flags)


def _cell_text(cell) -> str:
    """Block children separated by a space, inline runs joined by nothing.

    Both halves are load-bearing, and each was got wrong once while measuring:

    * joining EVERYTHING with a space turns `R<sup>2</sup>` into `R 2`;
    * joining everything with nothing fuses a cell that stacks `.556` and `.390`
      as two paragraphs into `.556.390` -- a number the paper never printed,
      which is the class this project ranks worst because it does not announce
      itself.
    """
    blocks = cell.find_all(["p", "div"], recursive=False)
    if blocks:
        parts = [re.sub(r"\s+", " ", b.get_text("")).strip() for b in blocks]
        return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()
    return re.sub(r"\s+", " ", cell.get_text("")).strip()


def _span(cell, attr: str) -> int:
    try:
        return max(1, int(cell.get(attr, 1) or 1))
    except (TypeError, ValueError):
        return 1


# A whole paragraph that IS a table label. Three differences from the shared
# `TABLE_CAPTION_RE`, each because a DOCX states something a PDF does not:
#
#  * `$`-anchored. The PDF regex matches a caption at the START of a line in a
#    linear text dump and needs the trailing `(?:[.:]|\s+[A-Z])` guard so a body
#    sentence ("Table 13 below shows...") does not false-match. A DOCX states
#    its paragraph boundaries, so a paragraph whose ENTIRE content is
#    `Table S1` is unambiguously a label and needs no such guard. Different
#    evidence, not a second copy of the same rule.
#  * Accepts a SUPPLEMENTARY number (`Table S1`). Measured: supplementary
#    labels are why 73 of 87 real DOCX tables had no caption -- DOCX is the
#    format supplementary material is submitted in.
#  * Accepts the title on the SAME paragraph or the NEXT one. APA 7 prints the
#    label and the title as two separate paragraphs, which is what
#    10.5281/zenodo.21911212 does for all 11 of its tables.
_DOCX_TABLE_LABEL_RE = re.compile(
    r"^\s*(?:Table|TABLE)\s+(?P<num>S?\d+[A-Za-z]?)\s*(?:[.:—–-]\s*(?P<rest>\S.*))?$"
)
# A paragraph that merely REFERS to a table. Never a caption, whichever side of
# the table it sits on -- the negative control for the matcher above.
#
# WIDENED 2026-09-05 after the release consult round. The first version keyed on a
# short verb list plus a SINGULAR `\bTable\b`, and reproducibly promoted
# `cf. Table 2`, `See Tables 2 and 3` (the plural defeats `\bTable\b`) and a
# parenthetical `(Table 2)` to captions. Each then reached `flatten_table`'s
# effect-type vocabulary and typed a Cohen's d column as partial eta-squared --
# a real number published under the wrong statistic's name, which is worse than
# losing it, because a wrong number is quotable and a missing one is not.
_TABLE_REFERENCE_RE = re.compile(
    r"(?:\b(?:see|cf\.?|in|from|shown\s+in|presented\s+in|reported\s+in|"
    r"summari[sz]ed\s+in|listed\s+in|given\s+in|according\s+to)\s+Tables?\b"
    r"|\(\s*Tables?\s+S?\d)",
    re.I,
)

# A genuine APA table TITLE does not name a table number -- the label paragraph
# above it does that. So a paragraph sitting between the label and the table that
# names ANY table is prose, not this table's title.
_NAMES_A_TABLE_RE = re.compile(r"\bTables?\s+S?\d", re.I)


def _para_text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ")).strip()


def _scan_side(table_el, direction: str) -> tuple[Optional[str], Optional[str]]:
    """`(label, caption)` from up to two paragraphs on one side of the table.

    A paragraph that only REFERS to a table ("as shown in Table 3, ...") is
    refused, so proximity alone never promotes body prose to a caption. That
    matters more than the recall: a wrong caption is fed to
    `flatten_table`'s effect-type vocabulary, where a stray word can TYPE A
    STATISTIC the table does not report.
    """
    node = table_el
    passed: list[str] = []
    for _ in range(2):
        node = getattr(node, f"find_{direction}_sibling")(
            ["p", "h1", "h2", "h3", "h4", "h5", "h6", "table"]
        )
        if node is None or node.name == "table":
            return None, None
        text = _para_text(node)
        if not text:
            continue
        if _TABLE_REFERENCE_RE.search(text):
            return None, None
        m = _DOCX_TABLE_LABEL_RE.match(text)
        if m:
            label = f"Table {m.group('num')}"
            # The title sits on the label's own paragraph, or -- APA 7, which
            # prints label and title as two paragraphs -- on the one between the
            # label and the table, already collected in `passed`.
            title = m.group("rest")
            if title is None and passed:
                # APA 7 prints label and title as two paragraphs, so the
                # paragraph between the label and the table is usually the
                # title. Accept it ONLY if it does not itself name a table:
                # a `Table 4` label followed by "Table 3 reports the partial
                # eta-squared for each comparison" otherwise produces a caption
                # whose vocabulary types THIS table's Cohen's d column as
                # eta-squared. Reproduced by all three consult seats, 2026-09-05.
                if not _NAMES_A_TABLE_RE.search(passed[0]):
                    title = passed[0]
            return label, f"{label}. {title}" if title else label
        passed.append(text)
    return None, None


def _caption_side(table_els) -> str:
    """Which side of its table this DOCUMENT prints captions on.

    Decided once per document, by counting, rather than per table by trying both
    sides -- because trying both DOUBLE-ASSIGNS. Measured: a caption paragraph
    sitting between two tables was claimed by the table above it (as its "next")
    AND the table below it (as its "previous"), so 3 documents emitted the same
    label on two different tables. A consumer joining on `label` would then merge
    two unrelated grids.

    Journals are internally consistent about this, so the majority is the
    convention, and a tie resolves to "previous" (APA prints the caption above).
    """
    above = sum(1 for el in table_els if _scan_side(el, "previous")[0])
    below = sum(1 for el in table_els if _scan_side(el, "next")[0])
    return "next" if below > above else "previous"


def _footnote_for(table_el) -> Optional[str]:
    node = table_el.find_next_sibling(["p", "table"])
    if node is None or node.name == "table":
        return None
    text = re.sub(r"\s+", " ", node.get_text(" ")).strip()
    return text if text and _FOOTNOTE_RE.match(text) else None


def _header_row_count(grid: _SpanGrid) -> int:
    """How many leading rows mammoth marked as `<th>` (capped at 3, as the PDF path is)."""
    n = 0
    for flags in grid.header_flags:
        if flags and all(f or not t.strip()
                         for f, t in zip(flags, grid.rows[n], strict=False)) and any(flags):
            n += 1
        else:
            break
        if n >= 3:
            break
    return n


def extract_tables_docx(docx_bytes: bytes) -> tuple[list[Table], str]:
    """Every table the DOCX declares, as `Table` dicts, plus the method string.

    The returned `Table` is the SAME shape the PDF path returns, so
    `flatten_table`, `cells_to_html` and every consumer of `tables[]` work
    unchanged. Fields that have no DOCX meaning are `None` or zero **with the
    reason stated**, never a plausible-looking invention:

    * `page` is 0. OOXML has no page model at all -- pagination is decided by
      whichever renderer opens the file -- so any positive page number here
      would be fabricated. `flatten_table` already reads `int(page or 0)`.
    * `bbox` is all-zero and `cell_geometry` says why. A zero rectangle with no
      stated reason is indistinguishable from real geometry that happens to be
      zero.
    * `confidence` / `accuracy` / `whitespace` / `camelot_flavor` are `None`. A
      DOCX table is STATED, not captured, so there is no capture-quality signal;
      emitting a number would invent a confidence in a measurement nobody made.
    * `rendering` is `"markup"`. Reusing `"lattice"` would claim a Camelot
      capture path ran -- an unlabelled engine substitution.
    """
    import mammoth  # lazy: the core library works without the docx extra
    from bs4 import BeautifulSoup

    from ..extract_docx import _inline_omml_runs

    # The OMML fix has to run here too. `mammoth` has no model of `m:oMath` and
    # silently drops it, which deletes the NAME of a statistic; a table cell
    # holding `eta_p^2` is exactly where that matters. Same reason the sections
    # annotator calls it: every production path is wired, not just the one you
    # were looking at.
    result = mammoth.convert_to_html(io.BytesIO(_inline_omml_runs(docx_bytes)))
    for message in result.messages or ():
        record_fallback("docx_mammoth_conversion_message", detail=str(message)[:80])

    soup = BeautifulSoup(result.value, "html.parser")
    # EVERY table, nested ones included -- because a nested table is still a
    # table and its rows are now scoped to their own element (below).
    #
    # The first version took top-level tables only. Combined with a RECURSIVE row
    # scan that gave the worst of both: a nested table's rows were appended to its
    # parent, misattributed and folded under a fused header. Scoping the rows
    # fixed the fabrication and replaced it with a DELETION -- the nested table's
    # data vanished entirely, because `_cell_text` does not descend into a nested
    # table either. Trading a fabrication for a silent deletion is not a fix.
    #
    # So: scope the rows AND emit each table separately. Word's floating-table
    # wrapper (a 1x1 table around a real one) is removed by the `< 2 rows` guard
    # below rather than by a structural rule, which also covers wrappers this
    # code has not seen.
    table_els = list(soup.find_all("table"))
    caption_side = _caption_side(table_els)
    tables: list[Table] = []

    for idx, table_el in enumerate(table_els, start=1):
        grid = _SpanGrid()
        # ROWS OF THIS TABLE ONLY. `find_all("tr")` is recursive, so a nested
        # table's rows were being appended to its PARENT as if they were the
        # parent's own -- measured 2026-09-05: a 2-row outer table containing a
        # nested one reported `n_rows=4`, with the nested rows folded under a
        # fused header cell `Accuracy.04Speed.07`, a token no document printed.
        # The tables list is already filtered to top-level (above), so without
        # this the nested values are counted twice AND misattributed. Raised by
        # the Sol and Grok seats of the release consult round.
        for tr in table_el.find_all("tr"):
            if tr.find_parent("table") is not table_el:
                continue
            cells_in_row = tr.find_all(["td", "th"], recursive=False) or tr.find_all(["td", "th"])
            grid.add_row([
                (clean_cell_text(_cell_text(c)),
                 _span(c, "colspan"), _span(c, "rowspan"), c.name == "th")
                for c in cells_in_row
            ])

        if len(grid.rows) < 2:
            record_fallback("docx_table_below_two_rows", detail=f"{len(grid.rows)}rows")
            continue

        n_cols = max((len(r) for r in grid.rows), default=0)
        if not n_cols:
            record_fallback("docx_table_no_columns", detail=f"{len(grid.rows)}rows")
            continue

        n_header = _header_row_count(grid)
        cells: list[Cell] = []
        for r, row in enumerate(grid.rows):
            flags = grid.header_flags[r]
            for c in range(n_cols):
                text = row[c] if c < len(row) else ""
                is_header = bool(flags[c]) if c < len(flags) else False
                cells.append({
                    "r": r, "c": c, "rowspan": 1, "colspan": 1,
                    "text": text,
                    # Header-ness comes from the MARKUP (`<th>`, i.e. Word's own
                    # header-row flag), which is a fact the file states. The PDF
                    # path has to guess it from cell length and numeric ratio
                    # because a PDF states nothing.
                    "is_header": is_header or (n_header > 0 and r < n_header),
                    "bbox": (0.0, 0.0, 0.0, 0.0),
                })

        label, caption = _scan_side(table_el, caption_side)
        tables.append({
            "id": f"t{idx}",
            "label": label,
            "page": 0,
            "bbox": (0.0, 0.0, 0.0, 0.0),
            "caption": caption,
            "footnote": _footnote_for(table_el),
            "kind": "structured",
            "rendering": "markup",
            "confidence": None,
            "accuracy": None,
            "whitespace": None,
            "camelot_flavor": None,
            "n_rows": len(grid.rows),
            "n_cols": n_cols,
            "header_rows": n_header or 1,
            "cells": cells,
            # The SAME cleaning selection the cells were built with, and the
            # inferential CI repair off. Without both, `html` and
            # `cells[].text` disagree for one input -- measured, see
            # `cell_cleaning._html_escape`.
            # `declared_header_rows` is passed here for the same reason
            # `clean=` and `recover_ci_upper=` are: this channel must give the
            # SAME answer as `flatten_table` for one input. `n_header` is the
            # count mammoth read from `w:tblHeader`, so 0 means the author
            # declared nothing and the heuristic keeps the decision.
            "html": cells_to_html(
                cells, clean=clean_cell_text, recover_ci_upper=False,
                declared_header_rows=n_header or None,
            ),
            "raw_text": "\n".join("\t".join(r) for r in grid.rows),
            "cell_geometry": "no_layout:docx_states_no_page_geometry",
        })

    return tables, "mammoth"


__all__ = ["extract_tables_docx", "clean_docx_cell_text"]

# Exported under an unambiguous name too: `clean_cell_text` also exists in
# `cell_cleaning` with a DIFFERENT selection of repairs, and two functions with
# one name in one package is how the Greek-table divergence started.
clean_docx_cell_text = clean_cell_text
