"""
option-c.py  —  pdfminer.six word-bbox single-extractor cell extraction

APPROACH: HYBRID (pdfplumber for bbox detection, pdfminer for cell text)

Context
-------
The experiment spec asked for pdftotext -bbox-layout mode, which outputs per-word
HTML with xMin/yMin/xMax/yMax attributes.  CRITICAL FINDING: the installed
pdftotext is xpdf/Glyph&Cog v4.00, which does NOT have -bbox-layout.  That flag
belongs to the Poppler fork.  There is no Poppler pdftotext on this system.

Closest viable analog: pdfminer.six (already installed, MIT-licensed, not pdfplumber).
pdfminer provides per-character and per-line bounding boxes via its layout analysis
engine.  At the LTTextLine level, each line has (x0, y0, x1, y1) in PDF-native
points with bottom-left origin (y increases upward), which is exactly the per-line
positional data that -bbox-layout would have delivered.

Hybrid vs pure-single-extractor
---------------------------------
This implementation is HYBRID:
- Table bounding boxes: detected by pdfplumber via extract_pdf_structured()
  (still needs pdfplumber for detection — this is the limitation documented in notes.md)
- Cell content: extracted from pdfminer.six LTTextLine objects inside the bbox
  (zero pdfplumber usage for cell content)

Architecture overview
---------------------
1. extract_pdf_structured(pdf_bytes) → get table bbox + page for each detected table
2. Open PDF with pdfminer, iterate LTTextLine elements on the table's page
3. Filter lines inside the table bbox (with small tolerance)
4. Filter out decorative lines (short single-char lines like "/" that are border rules)
5. Cluster lines by y-midpoint → identify rows (tolerance: 4pt)
6. Detect multi-line cells: merge y-clusters sharing same column x within 20pt
7. Cluster by x-midpoint within rows → identify columns
8. Build grid, render as pipe-table

Coordinate system note
----------------------
pdfminer uses PDF native coordinates: (0,0) at BOTTOM-LEFT, y increases upward.
So y0 < y1 and higher y = higher on page.
pdfplumber uses the same convention for bbox: (x0, top, x1, bottom) where
"top" and "bottom" are measured from the TOP of the page (y increases downward).
pdfplumber bbox format: {'x0': ..., 'top': ..., 'x1': ..., 'bottom': ...}
Translation: pdfminer_y = page_height - pdfplumber_top (for top edge)
             pdfminer_y = page_height - pdfplumber_bottom (for bottom edge)
So pdfplumber bbox (x0, top, x1, bottom) → pdfminer (x0, h-bottom, x1, h-top)

Run from project root:
    python docs/superpowers/plans/spot-checks/splice-spike/experiments/option-c/option-c.py
"""

from __future__ import annotations

import sys
import io
from pathlib import Path
from typing import NamedTuple

# ── Ensure project root is on sys.path ────────────────────────────────────────
# This file lives at: docpluck/docs/superpowers/plans/spot-checks/splice-spike/experiments/option-c/
REPO_ROOT = Path(__file__).resolve().parents[7]  # .../docpluck
sys.path.insert(0, str(REPO_ROOT))

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBox, LTTextLine
from docpluck.extract_structured import extract_pdf_structured

# ── Paths ──────────────────────────────────────────────────────────────────────
APA_DIR = REPO_ROOT.parent / "PDFextractor" / "test-pdfs" / "apa"
OUT_DIR = Path(__file__).parent

# ── Clustering thresholds ──────────────────────────────────────────────────────
Y_CLUSTER_PT = 5.0          # lines within 5pt vertically → same row
X_COL_SNAP_PT = 20.0        # x-midpoint within 20pt of column centre → same column
MIN_LINE_LENGTH = 2          # filter out decorative lines shorter than 2 chars
MIN_WORD_CHARS = 1           # minimum non-whitespace chars to keep a line
SLASH_FILTER = True          # filter lines that are purely "/" or "|" (PDF table rules)


# ── Data types ─────────────────────────────────────────────────────────────────

class TextLine(NamedTuple):
    text: str
    x0: float
    y0: float   # bottom of line (pdfminer coords: higher = higher on page)
    x1: float
    y1: float   # top of line

    @property
    def x_mid(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def y_mid(self) -> float:
        return (self.y0 + self.y1) / 2


# ── pdfminer line extraction ───────────────────────────────────────────────────

def extract_lines_on_page(pdf_path: str, page_num_0indexed: int) -> list[TextLine]:
    """Extract all LTTextLine objects from a specific page (0-indexed)."""
    lines: list[TextLine] = []
    for i, page_layout in enumerate(extract_pages(pdf_path)):
        if i != page_num_0indexed:
            continue
        for elem in page_layout:
            if isinstance(elem, LTTextBox):
                for line in elem:
                    if isinstance(line, LTTextLine):
                        txt = line.get_text().strip()
                        if len(txt) >= MIN_WORD_CHARS:
                            lines.append(TextLine(
                                text=txt,
                                x0=line.x0,
                                y0=line.y0,
                                x1=line.x1,
                                y1=line.y1,
                            ))
        break
    return lines


def filter_lines_in_bbox(
    lines: list[TextLine],
    bbox_pm: tuple[float, float, float, float],  # (x0, y_bottom, x1, y_top) in pdfminer coords
    tolerance: float = 2.0,
) -> list[TextLine]:
    """Keep only lines whose midpoint falls inside the bbox."""
    x0, y_bot, x1, y_top = bbox_pm
    result = []
    for ln in lines:
        if (x0 - tolerance <= ln.x_mid <= x1 + tolerance and
                y_bot - tolerance <= ln.y_mid <= y_top + tolerance):
            result.append(ln)
    return result


def is_decorative(ln: TextLine) -> bool:
    """Return True if this line is a decorative rule (slash, pipe, single char)."""
    t = ln.text.strip()
    if not t:
        return True
    if SLASH_FILTER and all(c in '/|\\-_' for c in t):
        return True
    # Very short single character that is not alphanumeric/digit
    if len(t) == 1 and not t.isalnum():
        return True
    return False


# ── Row/column clustering ──────────────────────────────────────────────────────

def cluster_by_y(lines: list[TextLine], tolerance: float = Y_CLUSTER_PT) -> list[list[TextLine]]:
    """Group lines into rows by y-midpoint proximity.

    Lines are sorted by y_mid descending (top-to-bottom on page).
    Lines within `tolerance` points of the current cluster's y-centroid are merged in.
    """
    if not lines:
        return []
    sorted_lines = sorted(lines, key=lambda l: -l.y_mid)  # top first
    clusters: list[list[TextLine]] = []
    current: list[TextLine] = [sorted_lines[0]]
    current_y = sorted_lines[0].y_mid

    for ln in sorted_lines[1:]:
        if abs(ln.y_mid - current_y) <= tolerance:
            current.append(ln)
            # Update running centroid
            current_y = sum(l.y_mid for l in current) / len(current)
        else:
            clusters.append(current)
            current = [ln]
            current_y = ln.y_mid
    clusters.append(current)
    return clusters


def detect_columns(rows: list[list[TextLine]]) -> list[float]:
    """Detect column x-midpoint positions from all words across all rows.

    Algorithm:
    1. Collect all x_mid values.
    2. Sort and greedily cluster within X_COL_SNAP_PT.
    3. Return cluster centres, sorted left-to-right.
    """
    x_mids: list[float] = []
    for row in rows:
        for ln in row:
            x_mids.append(ln.x_mid)

    if not x_mids:
        return []

    x_mids.sort()
    col_centres: list[list[float]] = [[x_mids[0]]]
    for x in x_mids[1:]:
        if x - col_centres[-1][-1] <= X_COL_SNAP_PT:
            col_centres[-1].append(x)
        else:
            col_centres.append([x])

    return [sum(grp) / len(grp) for grp in col_centres]


def assign_to_column(x_mid: float, col_centres: list[float], tolerance: float = X_COL_SNAP_PT) -> int:
    """Return the index of the nearest column centre within tolerance, else -1."""
    best_i = -1
    best_dist = float('inf')
    for i, cx in enumerate(col_centres):
        dist = abs(x_mid - cx)
        if dist < best_dist:
            best_dist = dist
            best_i = i
    if best_dist <= tolerance:
        return best_i
    # If outside tolerance, still assign to nearest (for wide tables)
    return best_i


def build_grid(
    rows: list[list[TextLine]],
    col_centres: list[float],
) -> list[list[str]]:
    """Assign each line to its column and build a 2D grid.

    Multi-line cells: lines in the same row that share a column get their
    text joined with a space.
    """
    grid: list[list[str]] = []
    for row in rows:
        cells: list[list[str]] = [[] for _ in col_centres]
        for ln in row:
            col_i = assign_to_column(ln.x_mid, col_centres)
            if col_i >= 0:
                cells[col_i].append(ln.text)
        # Join multi-word cells; sort by x_mid for consistent ordering
        row_data: list[str] = []
        for col_texts in cells:
            row_data.append(' '.join(col_texts))
        grid.append(row_data)
    return grid


# ── Pipe-table renderer ────────────────────────────────────────────────────────

def render_pipe_table(grid: list[list[str]]) -> str:
    """Render a 2D grid as a GFM pipe-table."""
    if len(grid) < 2:
        return "(table has fewer than 2 rows — cannot render as pipe-table)\n"

    def _cell(v: str) -> str:
        return v.replace('\n', ' ').replace('|', '\\|').strip()

    n_cols = max(len(row) for row in grid)
    header = [_cell(c) for c in grid[0]] + [''] * (n_cols - len(grid[0]))
    sep = ['---'] * n_cols

    lines = []
    lines.append('| ' + ' | '.join(header) + ' |')
    lines.append('| ' + ' | '.join(sep) + ' |')
    for row in grid[1:]:
        cells = [_cell(c) for c in row] + [''] * (n_cols - len(row))
        lines.append('| ' + ' | '.join(cells) + ' |')

    return '\n'.join(lines) + '\n'


# ── pdfplumber bbox → pdfminer coords ─────────────────────────────────────────

def pdfplumber_bbox_to_pdfminer(
    bbox,
    page_height: float,
) -> tuple[float, float, float, float]:
    """Convert pdfplumber bbox to pdfminer (x0, y_bottom, x1, y_top).

    pdfplumber bbox is a tuple (x0, top, x1, bottom) where top/bottom are
    measured from the TOP of the page (y-down convention).
    pdfminer uses y-up from bottom of page.
    """
    if isinstance(bbox, dict):
        x0, top, x1, bottom = bbox['x0'], bbox['top'], bbox['x1'], bbox['bottom']
    else:
        # tuple format: (x0, top, x1, bottom)
        x0, top, x1, bottom = bbox
    y_top_pm = page_height - top    # pdfminer y of top edge
    y_bot_pm = page_height - bottom # pdfminer y of bottom edge
    return (x0, y_bot_pm, x1, y_top_pm)


def get_page_height(pdf_path: str, page_num_0indexed: int) -> float:
    """Get the height of a specific page from pdfminer."""
    for i, page_layout in enumerate(extract_pages(pdf_path)):
        if i == page_num_0indexed:
            return page_layout.height
    return 792.0  # fallback US letter


# ── Main extraction logic ──────────────────────────────────────────────────────

def extract_table_cells(
    pdf_path: str,
    pdf_bytes: bytes,
    table_meta: dict,
    debug: bool = False,
) -> list[list[str]]:
    """Extract table cells using pdfminer line bboxes inside pdfplumber-detected bbox.

    Returns a 2D grid (list of rows, each row is list of cell strings).
    """
    page_1indexed = table_meta.get('page', 1)
    page_0indexed = page_1indexed - 1
    bbox = table_meta.get('bbox')

    if not bbox:
        return []

    pdf_path_str = str(pdf_path)

    # Get page height for coordinate conversion
    page_h = get_page_height(pdf_path_str, page_0indexed)

    # Convert pdfplumber bbox to pdfminer coordinates
    bbox_pm = pdfplumber_bbox_to_pdfminer(bbox, page_h)

    if debug:
        print(f"  Table page={page_1indexed}, pdfplumber bbox={bbox}")
        print(f"  Page height={page_h:.1f}, pdfminer bbox (x0,y_bot,x1,y_top)={[round(v,1) for v in bbox_pm]}")

    # Extract all lines from the page
    all_lines = extract_lines_on_page(pdf_path_str, page_0indexed)

    if debug:
        print(f"  Total lines on page: {len(all_lines)}")

    # Filter to table bbox
    table_lines = filter_lines_in_bbox(all_lines, bbox_pm, tolerance=4.0)

    if debug:
        print(f"  Lines in bbox: {len(table_lines)}")
        for ln in table_lines[:20]:
            print(f"    [{ln.x0:.0f},{ln.y0:.0f},{ln.x1:.0f},{ln.y1:.0f}] '{ln.text[:50]}'")

    # Remove decorative lines
    table_lines = [ln for ln in table_lines if not is_decorative(ln)]

    if debug:
        print(f"  Lines after decorative filter: {len(table_lines)}")

    if not table_lines:
        return []

    # Cluster by y to get rows
    rows = cluster_by_y(table_lines, tolerance=Y_CLUSTER_PT)

    if debug:
        print(f"  Row clusters: {len(rows)}")
        for i, row in enumerate(rows):
            texts = [ln.text[:20] for ln in row]
            y_avg = sum(ln.y_mid for ln in row) / len(row)
            print(f"    Row {i} (y_avg={y_avg:.1f}): {texts}")

    # Detect column positions
    col_centres = detect_columns(rows)

    if debug:
        print(f"  Column centres: {[round(c,1) for c in col_centres]}")

    # Build grid
    grid = build_grid(rows, col_centres)

    return grid


# ── Pure pdfminer table detection (fallback when pdfplumber finds nothing) ─────

def detect_table_bbox_from_lines(
    lines: list[TextLine],
    page_height: float,
) -> tuple[float, float, float, float] | None:
    """Detect table region purely from pdfminer line geometry.

    Strategy:
    1. Cluster lines into rows by y.
    2. Find the largest contiguous run of rows with ≥2 columns (data core).
    3. Extend upward to include header rows (rows with ≥2 cols just above, OR
       rows that look like column headers based on short text count).
    4. Extend upward further to include 1-col category-label rows (like "Easy",
       "Difficult") that appear immediately above multi-col data rows.
    5. Extend downward similarly.
    6. Stop when hitting long-prose rows (footnotes / body text).

    Returns pdfminer bbox (x0, y_bot, x1, y_top) or None.
    """
    if len(lines) < 4:
        return None

    # Cluster all lines by y to identify rows
    rows = cluster_by_y(lines, tolerance=Y_CLUSTER_PT)

    # Score each row by its number of distinct x-column clusters
    def count_cols(row: list[TextLine]) -> int:
        if not row:
            return 0
        x_mids = sorted(ln.x_mid for ln in row)
        if len(x_mids) == 1:
            return 1
        cols = 1
        for i in range(1, len(x_mids)):
            if x_mids[i] - x_mids[i-1] > X_COL_SNAP_PT:
                cols += 1
        return cols

    def is_long_prose(row: list[TextLine]) -> bool:
        """True if row looks like body text (one wide line of >60 chars)."""
        if len(row) != 1:
            return False
        txt = row[0].text
        return len(txt) > 60 and (row[0].x1 - row[0].x0) > 200

    col_counts = [count_cols(row) for row in rows]

    # Find the largest contiguous range of rows with ≥2 columns (data core)
    best_start = 0
    best_end = 0
    best_score = 0
    cur_start = 0
    cur_score = 0

    for i, cnt in enumerate(col_counts):
        if cnt >= 2:
            cur_score += cnt
            if cur_score > best_score:
                best_score = cur_score
                best_start = cur_start
                best_end = i
        else:
            cur_start = i + 1
            cur_score = 0

    if best_score < 4:  # need at least 4 column-points of evidence
        return None

    # Extend the range: include adjacent rows that are either:
    # - multi-column (≥2 cols) — additional header/data rows
    # - single-column with short text (≤4 words) — category label rows
    # Stop at long prose rows (footnotes)

    def is_table_adjacent(row: list[TextLine]) -> bool:
        if count_cols(row) >= 2:
            return True
        if is_long_prose(row):
            return False
        # Short 1-col row — likely a category label ("Easy", "Difficult")
        txt = ' '.join(ln.text for ln in row)
        return len(txt.split()) <= 4 and len(txt) <= 30

    # Extend upward (rows are sorted top-to-bottom, so lower index = higher y)
    ext_start = best_start
    while ext_start > 0:
        prev_i = ext_start - 1
        row = rows[prev_i]
        if is_long_prose(row):
            break
        # Stop at caption lines ("Table 1: ...")
        txt = ' '.join(ln.text for ln in row)
        if txt.lower().startswith('table ') or txt.lower().startswith('fig'):
            break
        if is_table_adjacent(row):
            ext_start = prev_i
        else:
            break

    # Extend downward
    ext_end = best_end
    while ext_end < len(rows) - 1:
        next_i = ext_end + 1
        row = rows[next_i]
        if is_long_prose(row):
            break
        if is_table_adjacent(row):
            ext_end = next_i
        else:
            break

    table_rows = rows[ext_start:ext_end + 1]
    if not table_rows:
        return None

    all_table_lines = [ln for row in table_rows for ln in row]
    x0 = min(ln.x0 for ln in all_table_lines) - 2
    x1 = max(ln.x1 for ln in all_table_lines) + 2
    y_bot = min(ln.y0 for ln in all_table_lines) - 2
    y_top = max(ln.y1 for ln in all_table_lines) + 2

    return (x0, y_bot, x1, y_top)


# ── Per-PDF extraction ─────────────────────────────────────────────────────────

def extract_first_table(
    pdf_filename: str,
    debug: bool = False,
    target_page_1indexed: int | None = None,
) -> tuple[str, list[dict]]:
    """Extract the first detected table from a PDF. Return (markdown, diagnostics).

    Falls back to pure pdfminer detection if pdfplumber finds no tables.
    """
    pdf_path = APA_DIR / pdf_filename
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()

    structured = extract_pdf_structured(pdf_bytes)
    tables = structured.get('tables', [])

    pdf_path_str = str(pdf_path)

    if tables:
        # Hybrid path: use pdfplumber bbox for detection
        t = tables[0]
        if debug:
            print(f"\n=== {pdf_filename} (HYBRID) ===")
            print(f"Detected {len(tables)} table(s). Using table[0]: page={t.get('page')}, label={t.get('label')}")
            if t.get('bbox'):
                print(f"  pdfplumber bbox: {t['bbox']}")
        grid = extract_table_cells(pdf_path_str, pdf_bytes, t, debug=debug)
        if not grid:
            return "(grid is empty — no lines extracted in bbox)\n", [t]
        return render_pipe_table(grid), [t]

    # Pure pdfminer detection path
    if debug:
        print(f"\n=== {pdf_filename} (PURE pdfminer detection) ===")
        print("  No tables detected by extract_pdf_structured. Using pure pdfminer detection.")

    # Determine which page to search
    search_pages = ([target_page_1indexed - 1] if target_page_1indexed
                    else list(range(min(10, 20))))  # search first 10 pages

    for page_0 in search_pages:
        if debug:
            print(f"  Scanning page {page_0 + 1}...")
        all_lines = extract_lines_on_page(pdf_path_str, page_0)
        # Remove obvious decorative lines
        clean_lines = [ln for ln in all_lines if not is_decorative(ln)]

        page_h = get_page_height(pdf_path_str, page_0)
        bbox_pm = detect_table_bbox_from_lines(clean_lines, page_h)

        if bbox_pm is None:
            if debug:
                print(f"    No table region detected on page {page_0 + 1}.")
            continue

        if debug:
            print(f"    Detected table bbox (pdfminer): {[round(v,1) for v in bbox_pm]}")

        # Filter lines to table bbox
        table_lines = filter_lines_in_bbox(clean_lines, bbox_pm, tolerance=4.0)
        table_lines = [ln for ln in table_lines if not is_decorative(ln)]

        if debug:
            print(f"    Lines in detected bbox: {len(table_lines)}")

        if len(table_lines) < 4:
            continue

        rows = cluster_by_y(table_lines, tolerance=Y_CLUSTER_PT)
        col_centres = detect_columns(rows)
        grid = build_grid(rows, col_centres)

        if len(grid) < 2:
            continue

        # Fake table meta for reporting
        fake_meta = {
            'page': page_0 + 1,
            'label': f'(pure-detected, page {page_0+1})',
            'bbox': bbox_pm,
            'detection': 'pure-pdfminer',
        }

        if debug:
            print(f"    Grid: {len(grid)} rows × {len(grid[0]) if grid else 0} cols")

        return render_pipe_table(grid), [fake_meta]

    return "(no table detected on any page — pure pdfminer detection failed)\n", []


# ── Sample HTML generation (analog to pdftotext -bbox-layout output) ───────────

def generate_sample_bbox_html(pdf_filename: str, max_lines: int = 200) -> str:
    """Generate a sample XML/HTML showing per-line bboxes, analogous to pdftotext -bbox-layout.

    This is the pdfminer equivalent of what -bbox-layout would produce.
    We output page 7 of korbmacher (the table page) to show the format.
    """
    pdf_path = APA_DIR / pdf_filename
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!-- pdfminer.six LTTextLine bbox output — analog to pdftotext -bbox-layout -->',
        '<!-- Coordinate system: x increases right, y increases UP from bottom-left -->',
        '<!-- Each <line> element: xMin=x0, yMin=y0 (bottom), xMax=x1, yMax=y1 (top) -->',
        '<document>',
    ]

    line_count = 0
    for page_num, page_layout in enumerate(extract_pages(str(pdf_path))):
        if page_num > 8:  # only show first 9 pages for korbmacher
            break
        lines.append(f'  <page number="{page_num+1}" width="{page_layout.width:.1f}" height="{page_layout.height:.1f}">')
        for elem in page_layout:
            if isinstance(elem, LTTextBox):
                for line in elem:
                    if isinstance(line, LTTextLine):
                        txt = line.get_text().strip()
                        if txt and line_count < max_lines:
                            txt_safe = txt.encode('ascii', 'xmlcharrefreplace').decode()
                            lines.append(
                                f'    <line xMin="{line.x0:.2f}" yMin="{line.y0:.2f}" '
                                f'xMax="{line.x1:.2f}" yMax="{line.y1:.2f}">'
                                f'{txt_safe}</line>'
                            )
                            line_count += 1
        lines.append('  </page>')
        if line_count >= max_lines:
            lines.append('  <!-- output truncated at 200 lines -->')
            break

    lines.append('</document>')
    return '\n'.join(lines) + '\n'


# ── Entry point ────────────────────────────────────────────────────────────────

def _pr(s: str) -> None:
    """Print safely on Windows console (encode non-ASCII as '?')."""
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode('ascii', 'replace').decode('ascii'))


def main() -> None:
    # Wrap stdout for UTF-8 where possible
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    # Write sample bbox HTML (using korbmacher, page 7 is the table page)
    _pr("Generating sample bbox HTML...")
    sample_html = generate_sample_bbox_html("korbmacher_2022_kruger.pdf", max_lines=200)
    (OUT_DIR / "sample-pdftotext-bbox.html").write_text(sample_html, encoding='utf-8')
    _pr(f"  Wrote sample-pdftotext-bbox.html ({len(sample_html.splitlines())} lines)")

    # Extract korbmacher Table 1 (page 7, pure pdfminer detection since pdfplumber misses it)
    _pr("\nExtracting korbmacher_2022_kruger.pdf Table 1 (page 7)...")
    md_korb, korb_meta = extract_first_table(
        "korbmacher_2022_kruger.pdf", debug=True, target_page_1indexed=7
    )
    (OUT_DIR / "korbmacher_table1.md").write_text(md_korb, encoding='utf-8')
    _pr("  Wrote korbmacher_table1.md")
    _pr("  Preview:")
    for line in md_korb.splitlines()[:18]:
        _pr("    " + line)

    # Extract ziano Table 1 (page 2, hybrid: pdfplumber bbox detection)
    _pr("\nExtracting ziano_2021_joep.pdf Table 1 (page 2)...")
    md_ziano, ziano_meta = extract_first_table("ziano_2021_joep.pdf", debug=True)
    (OUT_DIR / "ziano_table1.md").write_text(md_ziano, encoding='utf-8')
    _pr("  Wrote ziano_table1.md")
    _pr("  Preview:")
    for line in md_ziano.splitlines()[:25]:
        _pr("    " + line)

    _pr("\nDone. All files written to: " + str(OUT_DIR))


if __name__ == "__main__":
    main()
