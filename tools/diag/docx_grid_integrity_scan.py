"""Two grid-placement defects in the DOCX table path, counted on real documents.

Both were reproduced synthetically by the 2026-09-05 release review round, and
neither is worth a fix unless real documents produce it -- a rule with no observed
input is false-positive surface for no benefit (CLAUDE.md: measure the denominator
separately from the shape).

    A. `_SpanGrid` never AGES a pending rowspan past a SHORT row.
       `drain()` only fires while `col` is in `_pending`, so a row that never
       reaches a pending column leaves that entry with its original count. The
       rowspan then extends by an extra row and shifts the NEXT row's cells right.
       Detected by object identity: `drain()` either deletes the entry or replaces
       it with a decremented tuple, and a new rowspan cell also replaces it, so an
       entry that survives a row AS THE SAME OBJECT was never aged.

    B. `w:gridBefore` is dropped by mammoth, so a row declared to start at grid
       column N is placed from column 0 and every value binds to the wrong header.
       Only a NON-UNIFORM `gridBefore` mis-binds: when every row of a table carries
       the same indent, header and data shift together and the binding survives.
       So the count that matters is per TABLE, not per row.

Both scans are two-sided. `--self-test` builds a known positive for each and shows
the detector firing, and a known negative and shows it silent; a zero from a run
that has not passed `--self-test` is a claim about the instrument, not the corpus.
`main()` therefore runs the self-test first and REFUSES to print counts if it fails.

    python tools/diag/docx_grid_integrity_scan.py --self-test
    python tools/diag/docx_grid_integrity_scan.py             # custody corpus
    python tools/diag/docx_grid_integrity_scan.py --wide      # every DOCX under VIBE_ROOT

Measured 2026-09-05 with `--wide` (619 readable documents, 3,019 tables):
`_SpanGrid` stale events **0** over 41,942 rows; tables with any `gridBefore`
**1**, and that one uniform; tables with NON-UNIFORM `gridBefore` **0**. Both
defects were therefore ACCEPTED rather than fixed -- see `todo.md`.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

# IMPORT THE WORKING TREE, NOT THE INSTALLED RELEASE -- the same guard every
# harness under tools/diag carries, and the reason
# tests/test_harness_scripts_import_the_working_tree.py exists.
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


# -- A. _SpanGrid pending-rowspan ageing -------------------------------------


def stale_pending_events(html: str) -> tuple[int, int, int, list[dict]]:
    """(tables, rows, stale_events, samples) for one mammoth HTML document."""
    from bs4 import BeautifulSoup

    from docpluck.tables.docx_tables import _SpanGrid, _cell_text, _span, clean_cell_text

    soup = BeautifulSoup(html, "html.parser")
    tables = rows = stale = 0
    samples: list[dict] = []
    for t_idx, table_el in enumerate(soup.find_all("table"), start=1):
        tables += 1
        grid = _SpanGrid()
        for r_idx, tr in enumerate(table_el.find_all("tr")):
            if tr.find_parent("table") is not table_el:
                continue
            cells_in_row = (
                tr.find_all(["td", "th"], recursive=False)
                or tr.find_all(["td", "th"])
            )
            before = dict(grid._pending)
            grid.add_row([
                (clean_cell_text(_cell_text(c)),
                 _span(c, "colspan"), _span(c, "rowspan"), c.name == "th")
                for c in cells_in_row
            ])
            for col, tup in before.items():
                if grid._pending.get(col) is tup:
                    stale += 1
                    if len(samples) < 20:
                        samples.append({"table": t_idx, "row": r_idx, "col": col,
                                        "pending": list(tup),
                                        "row_width": len(grid.rows[-1]),
                                        "cells_in_row": len(cells_in_row)})
            rows += 1
    return tables, rows, stale, samples


def mammoth_html(docx_bytes: bytes) -> str:
    """The same HTML the shipped path reads, OMML inlined the same way."""
    import mammoth

    from docpluck.extract_docx import _inline_omml_runs

    return mammoth.convert_to_html(io.BytesIO(_inline_omml_runs(docx_bytes))).value


# -- B. w:gridBefore uniformity ----------------------------------------------


def _grid_before_of(tr) -> int:
    pr = tr.find(f"{W}trPr")
    if pr is None:
        return 0
    e = pr.find(f"{W}gridBefore")
    if e is None:
        return 0
    try:
        return int(e.get(f"{W}val") or 0)
    except ValueError:
        return 0


def grid_before_tables(docx_bytes: bytes) -> tuple[int, int, int, int]:
    """(tables, rows, tables_with_any_gridBefore, tables_NONUNIFORM)."""
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        if "word/document.xml" not in z.namelist():
            return 0, 0, 0, 0
        root = ET.fromstring(z.read("word/document.xml"))
    tables = rows = any_gb = nonuniform = 0
    for tbl in root.iter(f"{W}tbl"):
        tables += 1
        vals: list[int] = []
        for tr in tbl.iter(f"{W}tr"):
            tcs = tr.findall(f"{W}tc")
            if not tcs:
                continue
            rows += 1
            # A trailing one-cell note row is not part of the data grid, and its
            # indent says nothing about how the data columns line up.
            if len(tcs) > 1:
                vals.append(_grid_before_of(tr))
        if any(vals):
            any_gb += 1
            if len(set(vals)) > 1:
                nonuniform += 1
    return tables, rows, any_gb, nonuniform


# -- corpus ------------------------------------------------------------------


def custody_docx() -> list[tuple[str, Path]]:
    """DOCX resolved through article-finder's index -- never a directory glob."""
    repo = Path(
        os.environ.get("ARTICLE_REPOSITORY")
        or (Path(os.environ.get("VIBE_ROOT") or (Path.home() / "Vibe")) / "ArticleRepository")
    )
    index = repo / "index.json"
    if not index.exists():
        raise SystemExit(
            f"FATAL: article-finder index not found at {index}. It is the sole "
            "custodian of papers, so there is no corpus to scan. Refusing to "
            "report a result computed from 0 documents."
        )
    data = json.loads(index.read_text(encoding="utf-8"))
    out: list[tuple[str, Path]] = []
    for key, entry in data.items():
        if not isinstance(entry, dict):
            continue
        fn = str(entry.get("filename") or "")
        if not fn.lower().endswith(".docx"):
            continue
        p = repo / "fulltext" / fn
        if p.exists():
            out.append((key, p))
    return sorted(out)


def wide_docx() -> list[tuple[str, Path]]:
    """Every DOCX under VIBE_ROOT -- a STRUCTURAL denominator, not a paper corpus.

    Grid placement is a property of OOXML, not of a document's language or
    discipline, so a wider denominator is strictly better evidence about how often
    the shape occurs. Nothing is read out of these files but their table structure,
    and nothing is written anywhere, so this does not move any article into or out
    of custody.
    """
    root = Path(os.environ.get("VIBE_ROOT") or (Path.home() / "Vibe"))
    skip = {".git", "node_modules", ".venv", "venv", "__pycache__", ".next"}
    out: list[tuple[str, Path]] = []
    for r, d, f in os.walk(root):
        d[:] = [x for x in d if x not in skip]
        for n in f:
            if n.lower().endswith(".docx") and not n.startswith("~$"):
                out.append((str(Path(r) / n), Path(r) / n))
    return sorted(out)


# -- self-test ---------------------------------------------------------------

_POS_SPAN = """<table>
  <tr><td>a1</td><td>b1</td><td rowspan="2">C</td></tr>
  <tr><td>a2</td></tr>
  <tr><td>a3</td><td>b3</td><td>c3</td></tr>
</table>"""
_DRAINED_SPAN = """<table>
  <tr><td rowspan="3">A</td><td>b1</td><td>c1</td></tr>
  <tr><td>b2</td></tr>
  <tr><td>b3</td><td>c3</td></tr>
</table>"""
_NEG_SPAN = """<table>
  <tr><th>Outcome</th><th>t</th><th>p</th></tr>
  <tr><td>Acc</td><td>2.1</td><td>.04</td></tr>
  <tr><td>Speed</td><td>1.3</td><td>.30</td></tr>
</table>"""


def _doc(rows_xml: str) -> bytes:
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body><w:tbl>'
        '<w:tblGrid><w:gridCol w:w="2000"/><w:gridCol w:w="2000"/>'
        '<w:gridCol w:w="2000"/><w:gridCol w:w="2000"/></w:tblGrid>'
        + rows_xml
        + "</w:tbl></w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


def _row(cells: Iterable[str], gb: int = 0) -> str:
    pr = f'<w:trPr><w:gridBefore w:val="{gb}"/></w:trPr>' if gb else ""
    tcs = "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in cells)
    return f"<w:tr>{pr}{tcs}</w:tr>"


def self_test() -> int:
    ok = True
    for name, html, expect in (
        ("POSITIVE  pending beyond a short row", _POS_SPAN, 1),
        ("NEGATIVE  rowspan drained normally", _DRAINED_SPAN, 0),
        ("NEGATIVE  plain 3x3 table", _NEG_SPAN, 0),
    ):
        _t, _r, stale, _s = stale_pending_events(html)
        good = stale == expect
        ok = ok and good
        print(f"  [{'OK ' if good else 'BAD'}] _SpanGrid  {name}: {stale} (expect {expect})")

    for name, b, expect in (
        ("POSITIVE  non-uniform gridBefore", _doc(_row("abcd") + _row([".04", ".30"], 2)), 1),
        ("NEGATIVE  uniform gridBefore", _doc(_row("abcd", 1) + _row("efgh", 1)), 0),
        ("NEGATIVE  no gridBefore", _doc(_row("abcd") + _row("efgh")), 0),
    ):
        _t, _r, any_gb, nonu = grid_before_tables(b)
        good = nonu == expect
        ok = ok and good
        print(f"  [{'OK ' if good else 'BAD'}] gridBefore {name}: nonuniform={nonu} "
              f"(expect {expect}), any={any_gb}")
    print("SELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--wide", action="store_true",
                    help="every DOCX under VIBE_ROOT, not only the custody corpus")
    ap.add_argument("--self-test", action="store_true",
                    help="show both detectors firing on a known positive and silent "
                         "on a known negative, then exit")
    ap.add_argument("--json", help="write the full result here")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    print("SELF-TEST (a zero below means nothing without it):")
    if self_test() != 0:
        print("FATAL: a detector failed its own control. Refusing to report counts.")
        return 3

    docs = wide_docx() if args.wide else custody_docx()
    if not docs:
        print("NO CORPUS -- 0 DOCX resolvable. This is a statement about the "
              "repository, not about the code.")
        return 2
    print(f"\nCORPUS: {len(docs)} DOCX "
          f"({'VIBE_ROOT walk' if args.wide else 'article-finder custody index'})")

    tot = {"docs_requested": len(docs), "unreadable": 0, "tables": 0, "rows": 0,
           "span_tables": 0, "span_rows": 0, "stale_events": 0,
           "tables_with_gridBefore": 0, "tables_nonuniform_gridBefore": 0}
    errors: list[list[str]] = []
    offenders: dict[str, dict] = {}
    for key, path in docs:
        try:
            b = path.read_bytes()
            t, r, any_gb, nonu = grid_before_tables(b)
            st, sr, stale, samples = stale_pending_events(mammoth_html(b))
        except Exception as exc:
            tot["unreadable"] += 1
            errors.append([str(path.name), f"{type(exc).__name__}: {exc}"[:100]])
            continue
        tot["tables"] += t
        tot["rows"] += r
        tot["span_tables"] += st
        tot["span_rows"] += sr
        tot["stale_events"] += stale
        tot["tables_with_gridBefore"] += any_gb
        tot["tables_nonuniform_gridBefore"] += nonu
        if stale or any_gb:
            offenders[key] = {"stale_events": stale, "gridBefore_tables": any_gb,
                              "nonuniform": nonu, "samples": samples[:5]}

    print(f"  unreadable (named, never dropped silently): {tot['unreadable']}")
    for name, why in errors[:10]:
        print(f"    SKIPPED {name}: {why}")
    print(f"  w:tbl elements: {tot['tables']}   w:tr rows: {tot['rows']}")
    print(f"  mammoth tables: {tot['span_tables']}   mammoth rows: {tot['span_rows']}")
    print(f"  A. _SpanGrid un-aged pending rowspans: {tot['stale_events']}")
    print(f"  B. tables with ANY w:gridBefore:        {tot['tables_with_gridBefore']}")
    print(f"     tables with NON-UNIFORM gridBefore:  "
          f"{tot['tables_nonuniform_gridBefore']}   <- the only shape that mis-binds")
    for key, d in list(offenders.items())[:10]:
        print(f"    {key}: {d['stale_events']} stale, {d['gridBefore_tables']} gb "
              f"({d['nonuniform']} non-uniform)")
    if args.json:
        Path(args.json).write_text(
            json.dumps({"totals": tot, "errors": errors, "offenders": offenders}, indent=2),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
