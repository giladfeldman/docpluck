"""Benchmark candidate DOCX engines on statistic-bearing tables and effect-size lines.

WHY THIS EXISTS. docpluck extracts DOCX as text+sections only: `extract_structured.py`
is PDF-only, so `tables` and `flattened_rows` are empty for every DOCX, and a consumer
that verifies effect sizes from table rows gets nothing for that whole input format.
Before wiring a DOCX table path we have to know WHICH engine to wire, with numbers
rather than with the 2026-05 `docs/DESIGN.md` §11 prose that chose mammoth for TEXT and
was never re-asked about TABLES.

GROUND TRUTH IS THE PRIMARY SOURCE, AND FOR A DOCX THAT IS THE OOXML.
A PDF has to be rasterized and read because its table structure is inferred. A DOCX
*states* its grid: `w:tbl` / `w:tr` / `w:tc`, with `w:gridSpan` for spans. So the truth
grid here is parsed straight from `word/document.xml` by `truth_tables()` -- an
independent minimal reader that shares no code with any candidate -- which is the
project's "READ WHAT THE FILE ALREADY SAYS BEFORE INVENTING A HEURISTIC" rule applied
to ground truth itself. It is NOT a second run of a candidate adjudicating its own
defect (CLAUDE.md: never adjudicate a tool's defect using that same tool).

THE MEASUREMENT IS TWO-SIDED, because a one-sided one cannot fail:

  POSITIVE  `cell_recall` / `stat_recall` -- the truth cells, and the statistic-bearing
            truth cells, a candidate reproduces at the right (row, column). A candidate
            that emits nothing scores 0; a candidate that emits the document twice
            still scores 1.0 here, which is why the negative side is required.

  NEGATIVE  `fabricated_numbers` -- numeric tokens the candidate puts in a table cell
            that occur in NO truth cell of that document. This side catches invention,
            deleted-revision text resurfacing as live data, and one document's values
            leaking into another's grid. A candidate is acceptable only when the
            positive side is high AND this is 0.

  CONTROL   `control_ok` -- the harness checks its own instrument before any engine.
            The truth reader must return non-empty cells for a document that has
            tables, and must NOT contain a planted value that is absent by
            construction. A zero from a broken reader looks exactly like a zero from a
            broken candidate (CLAUDE.md: a zero is a claim about the INSTRUMENT until
            you prove otherwise).

CORPUS. Every document comes from article-finder, the sole custodian, resolved through
its index by canonical key -- never from a directory glob and never from a sibling
project. No publication text is written anywhere by this script; it prints counts.

Usage:
    python tools/diag/docx_tool_benchmark.py --json out.json
    python tools/diag/docx_tool_benchmark.py --keys 10.5281/zenodo.21911212
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Callable, Optional

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# A cell is "statistic-bearing" when it carries a number inside a table whose
# vocabulary is statistical, or a number next to a statistical marker itself.
# Deliberately broad: a false positive only makes the benchmark harder, while a
# false negative silently removes the exact cells this exercise is about.
_STAT_MARKER = re.compile(
    r"(?:\bp\s*[<=>]|\bd\s*=|\bF\s*\(|\bt\s*\(|\br\s*=|\bM\s*=|\bSD\b|\bSE\b|\bOR\b|"
    r"\bCI\b|β|\bb\s*=|η|eta|χ|chi|\bz\s*=|\bBF|%)",
    re.I,
)
_NUMERIC = re.compile(r"[-−–+]?\d+(?:[.,]\d+)*%?")


# -- Ground truth: read the grid the DOCX itself declares --------------------


def _tc_text(tc) -> str:
    """Text of one `w:tc`: runs concatenated, PARAGRAPHS separated, deletions dropped.

    `w:delText` inside `w:del` is text the author REMOVED. A candidate that emits
    it is not recovering data, it is resurrecting a retraction -- so the truth
    grid must not contain it either, or the check would score that behaviour as
    correct. 5 of the 26 real manuscripts in the DOCX census carry `w:del`.

    THE PARAGRAPH BOUNDARY IS LOAD-BEARING AND THIS FUNCTION GOT IT WRONG FIRST.
    A stats cell routinely stacks several values as separate `w:p` paragraphs in
    one cell. The first version joined every `w:t` in the subtree with no
    separator, so a cell holding `.556` and `.390` came out as `.556.390` -- a
    number nobody printed, in the ground truth itself. It then scored mammoth,
    pandoc and docx2python as FABRICATING 12 numbers when all three were
    reporting the cell correctly (10.1080/00221309.2023.2275304, table 2). Same
    defect class the library's own `_linearize_omml` exists to prevent -- "never
    fuse two numerals whose relationship we cannot name" -- committed by the
    instrument that was there to detect it.
    """
    paras: list[str] = []

    def runs_of(node) -> str:
        buf: list[str] = []
        for n in node.iter():
            if n.tag == f"{W}delText":
                continue
            if n.tag == f"{W}t":
                buf.append(n.text or "")
            elif n.tag in (f"{W}tab", f"{W}br", f"{W}cr"):
                buf.append(" ")
        return "".join(buf)

    seen_para = False
    for child in tc.iter(f"{W}p"):
        seen_para = True
        txt = runs_of(child).strip()
        if txt:
            paras.append(txt)
    if not seen_para:
        paras.append(runs_of(tc))
    return re.sub(r"\s+", " ", " ".join(paras)).strip()


def truth_tables(docx_bytes: bytes) -> list[list[list[str]]]:
    """Every TOP-LEVEL table in the document, as a row-major grid of cell text.

    Top-level only, on purpose: Word wraps a floating table in an outer
    single-cell table, and counting both makes a candidate that reports one table
    look like it lost one. (Measured: the census reported `nested_tbl == tbl` on
    most real manuscripts -- every table there is inside a wrapper.) `w:gridSpan`
    is expanded so a merged header cell occupies the columns it actually spans and
    column indices line up with what a candidate reports.
    """
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        if "word/document.xml" not in z.namelist():
            return []
        root = ET.fromstring(z.read("word/document.xml"))

    body = root.find(f"{W}body")
    if body is None:
        return []

    # Containers that hold block content without being block content themselves.
    # `w:sdt` is a Word CONTENT CONTROL and it is not exotic: measured on the
    # corpus, both tables of 10.1080/00221309.2023.2275304 (a Taylor & Francis
    # manuscript template) sit in `w:sdt/w:sdtContent`, and the first version of
    # this reader -- which looked only at direct `w:tbl` children of `w:body` --
    # reported 0 tables there while three independent engines reported 2. That
    # is the failure this module warns about, committed by the module itself:
    # the zero described the INSTRUMENT, not the document.
    _TRANSPARENT = (f"{W}sdt", f"{W}sdtContent", f"{W}txbxContent")

    def grids_in(parent) -> list[list[list[str]]]:
        out: list[list[list[str]]] = []
        for child in parent:
            if child.tag in _TRANSPARENT:
                out.extend(grids_in(child))
                continue
            if child.tag != f"{W}tbl":
                continue
            tbl = child
            grid: list[list[str]] = []
            for tr in tbl.findall(f"{W}tr"):
                row: list[str] = []
                for tc in tr.findall(f"{W}tc"):
                    span = 1
                    pr = tc.find(f"{W}tcPr")
                    if pr is not None:
                        gs = pr.find(f"{W}gridSpan")
                        if gs is not None:
                            try:
                                span = max(1, int(gs.get(f"{W}val", "1") or 1))
                            except ValueError:
                                span = 1
                    row.append(_tc_text(tc))
                    row.extend([""] * (span - 1))
                grid.append(row)
            # A one-cell wrapper is Word's floating-table container, not a table:
            # descend into it and report what it holds.
            if len(grid) == 1 and len(grid[0]) == 1:
                first_tc = tbl.find(f"{W}tr/{W}tc")
                if first_tc is not None:
                    out.extend(grids_in(first_tc))
                continue
            out.append(grid)
        return out

    return grids_in(body)


def raw_table_count(docx_bytes: bytes) -> int:
    """Independent lower bound on real tables: every `w:tbl` with >1 row, anywhere.

    This is the control's second instrument. `truth_tables` walks a STRUCTURE and
    can therefore miss a container it does not know about -- it did, on
    `w:sdt`. `root.iter` walks every element regardless of nesting, so
    disagreement between the two is a statement about the structured walk. Using
    an engine's table count for this instead would let the thing under test
    adjudicate the instrument, which this project forbids.
    """
    import xml.etree.ElementTree as ET

    try:
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
            if "word/document.xml" not in z.namelist():
                return 0
            root = ET.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, ET.ParseError):
        return 0
    return sum(1 for t in root.iter(f"{W}tbl") if len(t.findall(f"{W}tr")) > 1)


def _cells_of(grids: list[list[list[str]]]) -> set[tuple[int, int, int, str]]:
    return {
        (ti, ri, ci, c)
        for ti, g in enumerate(grids)
        for ri, row in enumerate(g)
        for ci, c in enumerate(row)
        if c.strip()
    }


def _stat_cells(grids: list[list[list[str]]]) -> set[tuple[int, int, int, str]]:
    """Cells worth verifying: a number, inside a table whose vocabulary is statistical."""
    out: set[tuple[int, int, int, str]] = set()
    for ti, g in enumerate(grids):
        flat = " ".join(c for row in g for c in row)
        table_is_statistical = bool(_STAT_MARKER.search(flat))
        for ri, row in enumerate(g):
            for ci, c in enumerate(row):
                if not c.strip():
                    continue
                if _NUMERIC.search(c) and (table_is_statistical or _STAT_MARKER.search(c)):
                    out.add((ti, ri, ci, c))
    return out


def _numbers(s: str) -> set[str]:
    """Numeric tokens, sign-normalised so U+2212 vs '-' is not scored as invention."""
    return {
        m.group(0).replace("−", "-").replace("–", "-").rstrip("%")
        for m in _NUMERIC.finditer(s)
    }


# -- Candidate engines: each returns grids in the SAME shape as truth --------


class _SpanGrid:
    """Place cells into a row-major grid honouring BOTH colspan and rowspan.

    A merged cell occupies every slot it spans, so the column index of the cells
    AFTER it is the one the reader sees. Getting this wrong is not cosmetic: the
    first version of the mammoth adapter expanded colspan and ignored rowspan, so
    on 10.1027/1618-3169/a000470 -- whose header row carries `rowspan=2` on
    "Laboratory" and "Total" -- the second header row slid two columns left and
    `Males`/`Females`/`Range`/`Mdn +/- MAD` landed under the wrong statistics.
    That reads as an ENGINE defect and is an ADAPTER defect; mammoth emits both
    attributes correctly (verified against its raw HTML). A benchmark that got
    this wrong would have picked the wrong tool.

    It is also the exact failure the DOCX path must avoid in production:
    `tables/flatten.py` binds each value to its column header, so a header
    shifted by one labels a t-statistic as a p-value.
    """

    def __init__(self) -> None:
        self.rows: list[list[str]] = []
        self._pending: dict[int, tuple[int, str]] = {}  # col -> (rows_left, text)

    def add_row(self, cells: list[tuple[str, int, int]]) -> None:
        """`cells` are (text, colspan, rowspan) in document order."""
        row: list[str] = []
        col = 0

        def drain() -> None:
            nonlocal col
            while col in self._pending:
                left, text = self._pending[col]
                while len(row) <= col:
                    row.append("")
                row[col] = text
                if left <= 1:
                    del self._pending[col]
                else:
                    self._pending[col] = (left - 1, text)
                col += 1

        for text, cspan, rspan in cells:
            drain()
            for k in range(max(1, cspan)):
                while len(row) <= col:
                    row.append("")
                row[col] = text if k == 0 else ""
                if rspan > 1:
                    self._pending[col] = (rspan - 1, text if k == 0 else "")
                col += 1
        drain()
        self.rows.append(row)


def _html_cell_text(cell) -> str:
    """Block children separated, inline runs joined with nothing.

    `get_text(" ")` puts a space at EVERY string boundary, so `R<sup>2</sup>`
    came out as `R 2` and `SD` inside a styled run as ` SD `. Those were scored
    as mammoth losing cells when they were the adapter inserting spaces. Blocks
    still need a separator, or two stacked values in one cell fuse into a number
    nobody printed -- the same trap the truth reader fell into.
    """
    blocks = cell.find_all(["p", "div"], recursive=False)
    if blocks:
        parts = [re.sub(r"\s+", " ", blk.get_text("")).strip() for blk in blocks]
        return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()
    return re.sub(r"\s+", " ", cell.get_text("")).strip()


def cand_mammoth(b: bytes) -> list[list[list[str]]]:
    """The engine docpluck ships. Tables reach text only as mammoth's HTML."""
    import mammoth
    from bs4 import BeautifulSoup

    html = mammoth.convert_to_html(io.BytesIO(b)).value
    soup = BeautifulSoup(html, "html.parser")
    grids = []
    for t in soup.find_all("table"):
        if t.find_parent("table") is not None:
            continue
        g = _SpanGrid()
        for tr in t.find_all("tr"):
            cells = []
            for cell in tr.find_all(["td", "th"], recursive=False) or tr.find_all(["td", "th"]):
                def _span(attr: str) -> int:
                    try:
                        return max(1, int(cell.get(attr, 1) or 1))
                    except (TypeError, ValueError):
                        return 1
                cells.append((_html_cell_text(cell), _span("colspan"), _span("rowspan")))
            g.add_row(cells)
        grids.append(g.rows)
    return grids


def cand_python_docx(b: bytes) -> list[list[list[str]]]:
    import docx

    d = docx.Document(io.BytesIO(b))
    grids = []
    for t in d.tables:
        grid = [[re.sub(r"\s+", " ", c.text).strip() for c in r.cells] for r in t.rows]
        if len(grid) == 1 and len(grid[0]) == 1:
            continue
        grids.append(grid)
    return grids


def cand_docx2python(b: bytes, tmp: Path) -> list[list[list[str]]]:
    """docx2python has NO table accessor, and that is part of the measurement.

    `DocxContent` exposes `body` / `body_pars` / `body_runs` and nothing else
    (checked against the installed 3.7.1: no `tables` member). `body` is the
    whole document as a nested list, in which a real table and a run of ordinary
    paragraphs have the SAME shape, so the caller has to GUESS which is which.
    The honest minimum guess is "at least one row carries two or more cells";
    without it, the title block and a trailing note of
    10.1080/00221309.2023.2275304 were scored as tables and their prose numbers
    counted as 124 fabrications, which measured this adapter rather than
    docx2python. Having to guess is a genuine cost of this engine and is
    reported as such, not hidden by the guess.
    """
    from docx2python import docx2python

    p = tmp / "d2p.docx"
    p.write_bytes(b)
    with docx2python(str(p), html=False, duplicate_merged_cells=True) as d:
        grids = []
        for tbl in d.body:
            grid = [
                [re.sub(r"\s+", " ", " ".join(cell)).strip() for cell in row]
                for row in tbl
            ]
            if len(grid) < 2 or max((len(r) for r in grid), default=0) < 2:
                continue
            grids.append(grid)
        return grids


def cand_pandoc(b: bytes, tmp: Path) -> list[list[list[str]]]:
    p = tmp / "pd.docx"
    p.write_bytes(b)
    out = subprocess.run(
        ["pandoc", "-f", "docx", "-t", "json", "--track-changes=accept", str(p)],
        capture_output=True, timeout=300,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode("utf-8", "replace")[:120])
    ast = json.loads(out.stdout.decode("utf-8"))

    def inline_text(xs) -> str:
        buf: list[str] = []
        for x in xs if isinstance(xs, list) else []:
            t = x.get("t") if isinstance(x, dict) else None
            if t == "Str":
                buf.append(x["c"])
            elif t in ("Space", "SoftBreak", "LineBreak"):
                buf.append(" ")
            elif t in ("Emph", "Strong", "Strikeout", "Superscript", "Subscript",
                       "SmallCaps", "Underline"):
                buf.append(inline_text(x["c"]))
            elif t == "Quoted":
                buf.append(inline_text(x["c"][1]))
            elif t in ("Link", "Span"):
                buf.append(inline_text(x["c"][1]))
            elif t in ("Math", "Code"):
                buf.append(x["c"][1])
        return re.sub(r"\s+", " ", "".join(buf)).strip()

    def block_text(bs) -> str:
        buf: list[str] = []
        for blk in bs if isinstance(bs, list) else []:
            t = blk.get("t") if isinstance(blk, dict) else None
            if t in ("Plain", "Para"):
                buf.append(inline_text(blk["c"]))
            elif t == "LineBlock":
                buf.extend(inline_text(line) for line in blk["c"])
            elif t == "BlockQuote":
                buf.append(block_text(blk["c"]))
            elif t == "Div":
                buf.append(block_text(blk["c"][-1]))
        return re.sub(r"\s+", " ", " ".join(x for x in buf if x)).strip()

    def feed(g: _SpanGrid, body_rows) -> None:
        for row in body_rows or []:
            cells = row[1] if isinstance(row, list) and len(row) > 1 else []
            out_row: list[tuple[str, int, int]] = []
            for cell in cells:
                # Pandoc Cell = [attr, alignment, rowspan, colspan, blocks]
                rowspan = cell[2] if len(cell) > 2 and isinstance(cell[2], int) else 1
                colspan = cell[3] if len(cell) > 3 and isinstance(cell[3], int) else 1
                out_row.append((block_text(cell[4] if len(cell) > 4 else []),
                                max(1, colspan), max(1, rowspan)))
            g.add_row(out_row)

    grids = []
    for blk in ast.get("blocks", []):
        if blk.get("t") != "Table":
            continue
        c = blk["c"]  # [attr, caption, colspecs, thead, tbodies, tfoot]
        g = _SpanGrid()
        head = c[3] if len(c) > 3 else None
        if isinstance(head, list) and len(head) > 1:
            feed(g, head[1])
        for tb in (c[4] if len(c) > 4 else []) or []:
            if isinstance(tb, list) and len(tb) > 3:
                feed(g, tb[3])
        foot = c[5] if len(c) > 5 else None
        if isinstance(foot, list) and len(foot) > 1:
            feed(g, foot[1])
        grids.append(g.rows)
    return grids


def cand_pdf_via_word(tmp: Path, pdf_path: Optional[Path]) -> list[list[list[str]]]:
    """The "convert to PDF and feed the existing PDF path" option.

    The conversion itself is NOT done here: it needs Microsoft Word (Windows, COM)
    or LibreOffice, and neither exists in the Linux service image -- that
    unavailability is itself part of the finding. When a pre-converted PDF is
    supplied, this measures what docpluck's SHIPPED PDF table pipeline recovers
    from it, so the conversion route is scored on the same axes as the rest.
    """
    if pdf_path is None or not pdf_path.exists():
        raise RuntimeError("no converted pdf available")
    from docpluck import extract_pdf_structured

    res = extract_pdf_structured(pdf_path.read_bytes())
    grids = []
    for t in res["tables"]:
        cells = t.get("cells") or []
        if not cells:
            continue
        n_r = max(c["r"] for c in cells) + 1
        n_c = max(c["c"] for c in cells) + 1
        grid = [["" for _ in range(n_c)] for _ in range(n_r)]
        for c in cells:
            grid[c["r"]][c["c"]] = re.sub(r"\s+", " ", c["text"] or "").strip()
        grids.append(grid)
    return grids


# -- Scoring -----------------------------------------------------------------


def score(truth: list[list[list[str]]], got: list[list[list[str]]]) -> dict:
    """Positional cell recall plus the fabrication side, over ALL tables.

    Matching is by (row, column, text) within a table, but tables are matched by
    CONTENT rather than by index: a candidate that finds truth tables 1 and 3
    should not be punished for numbering them 0 and 1.
    """
    t_cells = _cells_of(truth)
    t_stats = _stat_cells(truth)
    truth_numbers = {n for (_, _, _, c) in t_cells for n in _numbers(c)}

    matched_cells: set[tuple[int, int, int, str]] = set()
    matched_stats: set[tuple[int, int, int, str]] = set()
    used: set[int] = set()

    for ti, tg in enumerate(truth):
        want = {(ri, ci, c) for ri, row in enumerate(tg)
                for ci, c in enumerate(row) if c.strip()}
        best_i: Optional[int] = None
        best_hit: set[tuple[int, int, str]] = set()
        for gi, gg in enumerate(got):
            if gi in used:
                continue
            have = {(ri, ci, c) for ri, row in enumerate(gg)
                    for ci, c in enumerate(row) if c.strip()}
            hit = want & have
            if len(hit) > len(best_hit):
                best_i, best_hit = gi, hit
        if best_i is not None:
            used.add(best_i)
        for (ri, ci, c) in best_hit:
            matched_cells.add((ti, ri, ci, c))
            if (ti, ri, ci, c) in t_stats:
                matched_stats.add((ti, ri, ci, c))

    got_numbers = {n for g in got for row in g for c in row for n in _numbers(c)}
    fabricated = sorted(got_numbers - truth_numbers)

    return {
        "truth_tables": len(truth),
        "got_tables": len(got),
        "truth_cells": len(t_cells),
        "cell_recall": round(len(matched_cells) / len(t_cells), 4) if t_cells else None,
        "truth_stat_cells": len(t_stats),
        "stat_recall": round(len(matched_stats) / len(t_stats), 4) if t_stats else None,
        "fabricated_numbers": len(fabricated),
        "fabricated_sample": fabricated[:6],
    }


# -- Corpus: article-finder is the only way in -------------------------------


def repo_root() -> Path:
    ar = os.environ.get("ARTICLE_REPOSITORY")
    if ar:
        return Path(ar)
    vibe = Path(os.environ.get("VIBE_ROOT") or (Path.home() / "Vibe"))
    return vibe / "ArticleRepository"


def _body_text(docx_bytes: bytes) -> str:
    """Flat `w:t` text of the main document part -- enough for language detection."""
    try:
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
            if "word/document.xml" not in z.namelist():
                return ""
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except zipfile.BadZipFile:
        return ""
    return " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))


def _language_of(docx_bytes: bytes) -> str:
    """Best-effort language, via the repo's own detector when importable."""
    text = _body_text(docx_bytes)[:20000]
    if not text.strip():
        return "unknown"
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from _language import detect_language  # type: ignore

        return detect_language(text)[0]
    except Exception:
        return "unknown"


def corpus(keys: Optional[list[str]] = None,
           english_only: bool = True) -> tuple[list[tuple[str, Path]], list[tuple[str, str]]]:
    """Resolve DOCX articles through the custodian's index, by canonical key.

    Never a directory glob: a gate whose denominator comes from whatever happens
    to be on disk prints `N / N` on a corpus that has silently shrunk.

    ENGLISH ONLY, AND THE EXCLUSIONS ARE PRINTED, NEVER DROPPED SILENTLY.
    docpluck's scope is English-language articles, and the hard rule is stronger
    than scope: never learn about an English-article problem from a non-English
    article. Three of the DOCX in custody are Turkish or German (acquired
    2026-08-13 for the retired numeric-locale work); scoring an engine's table
    recall on them would measure a document shape docpluck does not serve.
    """
    index_path = repo_root() / "index.json"
    if not index_path.exists():
        raise SystemExit(
            f"article repository not found at {repo_root()} -- set the "
            "ARTICLE_REPOSITORY environment variable. A missing root makes every "
            "lookup miss, which reads as an empty corpus rather than as a broken one."
        )
    index = json.loads(index_path.read_text(encoding="utf-8"))
    out: list[tuple[str, Path]] = []
    excluded: list[tuple[str, str]] = []
    for key, entry in index.items():
        if not isinstance(entry, dict):
            continue
        fn = str(entry.get("filename") or "")
        if (entry.get("format") or "").lower() != "docx" and not fn.lower().endswith(".docx"):
            continue
        if keys and key not in keys:
            continue
        p = repo_root() / "fulltext" / fn
        if not p.exists():
            excluded.append((key, "file missing from repository"))
            continue
        if english_only:
            lang = _language_of(p.read_bytes())
            if lang not in ("english", "unknown"):
                excluded.append((key, f"language={lang}"))
                continue
        out.append((key, p))
    return sorted(out), sorted(excluded)


def main() -> int:
    ap = argparse.ArgumentParser(description="DOCX engine benchmark (see module docstring)")
    ap.add_argument("--keys", nargs="*", help="canonical keys to restrict to")
    ap.add_argument("--json", help="write full results here")
    ap.add_argument("--pdf-dir", help="directory of <stem>.word.pdf conversions")
    ap.add_argument("--tmp", default=None)
    ap.add_argument("--all-languages", action="store_true",
                    help="disable the English-only filter (diagnostic use only)")
    args = ap.parse_args()

    tmp = Path(args.tmp or os.environ.get("TEMP", ".")) / "docx_bench"
    tmp.mkdir(parents=True, exist_ok=True)
    pdf_dir = Path(args.pdf_dir) if args.pdf_dir else None

    docs, excluded = corpus(args.keys, english_only=not args.all_languages)
    print(f"corpus: {len(docs)} DOCX in scope, {len(excluded)} excluded")
    for key, why in excluded:
        print(f"  EXCLUDED {key:34} {why}")
    if not docs:
        print("NO CORPUS -- 0 DOCX resolvable through article-finder. This is a "
              "statement about the repository, not about the engines.")
        return 2

    engines: dict[str, Callable[[bytes, str], list[list[list[str]]]]] = {
        "mammoth": lambda b, k: cand_mammoth(b),
        "python-docx": lambda b, k: cand_python_docx(b),
        "docx2python": lambda b, k: cand_docx2python(b, tmp),
        "pandoc": lambda b, k: cand_pandoc(b, tmp),
        "word-pdf+docpluck": lambda b, k: cand_pdf_via_word(
            tmp, (pdf_dir / f"{k.replace('/', '__')}.word.pdf") if pdf_dir else None
        ),
    }

    results: dict = {"documents": {}, "totals": {}}
    broken_controls: list[str] = []
    for key, path in docs:
        b = path.read_bytes()
        try:
            truth = truth_tables(b)
            truth_error = None
        except Exception as exc:
            truth, truth_error = [], f"{type(exc).__name__}: {exc}"[:160]
        t_cells, t_stats = _cells_of(truth), _stat_cells(truth)

        doc = {
            "truth_tables": len(truth),
            "truth_cells": len(t_cells),
            "truth_stat_cells": len(t_stats),
            "engines": {},
        }
        for name, fn in engines.items():
            t0 = time.time()
            try:
                s = score(truth, fn(b, key))
                s["seconds"] = round(time.time() - t0, 2)
            except Exception as exc:
                s = {"error": f"{type(exc).__name__}: {exc}"[:120],
                     "seconds": round(time.time() - t0, 2)}
            doc["engines"][name] = s

        # CONTROL, TWO-SIDED, AGAINST AN INDEPENDENT INSTRUMENT.
        #
        # The first version asked only "does the truth grid contain a value that
        # is absent by construction?" and short-circuited to OK whenever the
        # truth grid was EMPTY -- so a document whose tables the reader could not
        # see passed the control vacuously, and every engine that DID see them
        # was scored as fabricating their contents. That happened, on
        # 10.1080/00221309.2023.2275304: truth 0 tables, three engines 2 tables,
        # 37 "fabricated" numbers that were the paper's real descriptives.
        #
        # POSITIVE side: the structured walk must find as many tables as the flat
        # `w:tbl` scan does. NEGATIVE side: a value absent by construction must
        # not appear. Both instruments are ours and neither is an engine, so a
        # candidate never gets to adjudicate the ruler it is measured with.
        planted = "docpluck-absent-value-9182736450"
        raw_n = raw_table_count(b)
        control_reasons = []
        if truth_error:
            control_reasons.append(f"truth reader raised: {truth_error}")
        if truth and not t_cells:
            control_reasons.append("tables found but every cell empty")
        if any(planted in c for (_, _, _, c) in t_cells):
            control_reasons.append("planted absent value present in truth")
        if len(truth) < raw_n:
            control_reasons.append(
                f"the flat w:tbl scan sees {raw_n} multi-row tables, the "
                f"structured reader sees {len(truth)} -- the reader is missing a "
                "container, so every score on this document is unusable"
            )
        doc["raw_table_count"] = raw_n
        control_ok = not control_reasons
        doc["control_ok"] = control_ok
        doc["control_reasons"] = control_reasons
        if not control_ok:
            broken_controls.append(key)
        results["documents"][key] = doc

        print(f"\n{key}  tables={len(truth)} cells={len(t_cells)} "
              f"stat_cells={len(t_stats)} control={'OK' if control_ok else 'BROKEN'}")
        for r in control_reasons:
            print(f"   !! CONTROL: {r}")
        for name, s in doc["engines"].items():
            if "error" in s:
                print(f"   {name:20} ERROR {s['error']}")
            else:
                print(f"   {name:20} tbl {s['got_tables']:>3}/{s['truth_tables']:<3} "
                      f"cell {str(s['cell_recall']):>6}  stat {str(s['stat_recall']):>6}  "
                      f"fab {s['fabricated_numbers']:>4}  {s['seconds']:>6}s")

    # Totals pool over CELLS, not a mean of per-document ratios -- averaging
    # ratios lets a 4-cell table outvote a 200-cell one. Documents whose CONTROL
    # failed are excluded from the totals and counted separately: a score
    # computed against a truth grid we know is wrong is not a weaker measurement,
    # it is a different measurement, and averaging it in would launder it.
    scored = {k: d for k, d in results["documents"].items() if d["control_ok"]}
    for name in engines:
        num_c = den_c = num_s = den_s = fab = errs = 0
        for d in scored.values():
            s = d["engines"][name]
            if "error" in s:
                errs += 1
                den_c += d["truth_cells"]
                den_s += d["truth_stat_cells"]
                continue
            if s["cell_recall"] is not None:
                num_c += round(s["cell_recall"] * s["truth_cells"])
            den_c += s["truth_cells"]
            if s["stat_recall"] is not None:
                num_s += round(s["stat_recall"] * s["truth_stat_cells"])
            den_s += s["truth_stat_cells"]
            fab += s["fabricated_numbers"]
        results["totals"][name] = {
            "cell_recall": round(num_c / den_c, 4) if den_c else None,
            "stat_recall": round(num_s / den_s, 4) if den_s else None,
            "fabricated_numbers": fab,
            "errors": errs,
            "documents_scored": len(scored),
            "documents_excluded_broken_control": len(results["documents"]) - len(scored),
        }

    print(f"\n== POOLED OVER {len(scored)} DOCUMENTS WITH A SOUND CONTROL ==")
    if broken_controls:
        print(f"   {len(broken_controls)} EXCLUDED for a failed control: "
              f"{', '.join(broken_controls)}")
    print(f"{'engine':22} {'cell':>8} {'stat':>8} {'fabricated':>11} {'errors':>7}")
    for name, t in results["totals"].items():
        print(f"{name:22} {str(t['cell_recall']):>8} {str(t['stat_recall']):>8} "
              f"{t['fabricated_numbers']:>11} {t['errors']:>7}")

    results["broken_controls"] = broken_controls
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 1 if broken_controls else 0


if __name__ == "__main__":
    sys.exit(main())
