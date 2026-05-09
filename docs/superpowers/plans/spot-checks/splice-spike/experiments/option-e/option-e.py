"""
option-e.py  —  Real Poppler pdftotext -bbox-layout table extractor

INSTALL METHOD:
    Poppler 24.08.0 was ALREADY installed at:
        C:\\Users\\filin\\AppData\\Local\\poppler\\bin\\pdftotext.exe
    (Installed previously, likely as a dependency of the pdf2image package
     or as a standalone install.)
    No new install was needed. conda was not available on this system.

    Verification:
        /c/Users/filin/AppData/Local/poppler/bin/pdftotext -h
        → "pdftotext version 24.08.0"
        → Shows "-bbox-layout : like -bbox but with extra layout bounding box data."

POPPLER BINARY PATH:
    C:\\Users\\filin\\AppData\\Local\\poppler\\bin\\pdftotext.exe

APPROACH:
    1. Run:  pdftotext -bbox-layout <pdf> <output.html>
    2. Parse the HTML. The key structure is:
           <page width="..." height="...">
             <flow>
               <block xMin yMin xMax yMax>
                 <line xMin yMin xMax yMax>
                   <word xMin yMin xMax yMax>text</word>
                   ...
                 </line>
               </block>
             </flow>
           </page>
       Poppler groups words into blocks automatically — each <block> corresponds
       to a visually distinct text region. For tabular content, each column
       of a whitespace-ruled table appears as a SEPARATE block with a narrow
       x-range. This is the key structural advantage over pdfminer's LTTextBox.

    3. Table detection strategy:
       - HYBRID path: Use pdfplumber (via extract_pdf_structured) to get table bbox,
         then filter words inside that bbox.
       - PURE-BLOCK path (fallback): Find blocks that form a column grid (≥3 narrow
         blocks at different x-positions but similar y-ranges). This uses the block
         structure rather than raw word clustering.

    4. Cell rendering: within a block, sort words by (y, x) to reconstruct
       reading order within each cell. Cluster blocks into rows by y-overlap.

COORDINATE SYSTEM:
    Poppler -bbox-layout uses y-DOWN coordinates:
        yMin = top edge of element (smaller y = higher on page)
        yMax = bottom edge of element
    This is the SAME convention as pdfplumber's top/bottom.
    NO coordinate flipping is needed when using pdfplumber bboxes with Poppler words.

Run from project root:
    python docs/superpowers/plans/spot-checks/splice-spike/experiments/option-e/option-e.py
"""

from __future__ import annotations

import sys
import io
import re
import subprocess
from pathlib import Path
from html.parser import HTMLParser
from typing import NamedTuple

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[7]   # .../docpluck
sys.path.insert(0, str(REPO_ROOT))

APA_DIR = REPO_ROOT.parent / "PDFextractor" / "test-pdfs" / "apa"
OUT_DIR = Path(__file__).parent

POPPLER_PDFTOTEXT = Path(
    r"C:\Users\filin\AppData\Local\poppler\bin\pdftotext.exe"
)

# ── Import docpluck's structured extractor ─────────────────────────────────────
from docpluck.extract_structured import extract_pdf_structured

# ── Clustering thresholds ──────────────────────────────────────────────────────
Y_ROW_OVERLAP_PT = 2.0      # blocks overlap vertically if their y-ranges share ≥2pt
X_COL_SNAP_PT = 18.0        # word x-midpoints within 18pt → same column
BLOCK_WIDTH_MAX = 200.0     # blocks wider than this are "prose" blocks, not table columns
MIN_WORD_CHARS = 1


# ── Data types ─────────────────────────────────────────────────────────────────

class Word(NamedTuple):
    text: str
    xMin: float
    yMin: float
    xMax: float
    yMax: float

    @property
    def x_mid(self) -> float:
        return (self.xMin + self.xMax) / 2

    @property
    def y_mid(self) -> float:
        return (self.yMin + self.yMax) / 2


class Block(NamedTuple):
    xMin: float
    yMin: float
    xMax: float
    yMax: float
    words: list[Word]

    @property
    def x_mid(self) -> float:
        return (self.xMin + self.xMax) / 2

    @property
    def y_mid(self) -> float:
        return (self.yMin + self.yMax) / 2

    @property
    def width(self) -> float:
        return self.xMax - self.xMin

    @property
    def height(self) -> float:
        return self.yMax - self.yMin

    def text_by_reading_order(self) -> str:
        """Join words sorted by (yMin, xMin) — top-to-bottom, left-to-right."""
        return ' '.join(w.text for w in sorted(self.words, key=lambda w: (w.yMin, w.xMin)))


# ── HTML parser for pdftotext -bbox-layout output ─────────────────────────────

class BBoxHTMLParser(HTMLParser):
    """Parse pdftotext -bbox-layout HTML into per-page blocks + words."""

    def __init__(self) -> None:
        super().__init__()
        self.pages: list[dict] = []
        self._cur_page: dict | None = None
        self._cur_block: dict | None = None
        self._cur_word_attrs: dict | None = None
        self._collecting_text = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attr_dict = dict(attrs)
        if tag == "page":
            self._cur_page = {
                "width": float(attr_dict.get("width", 612)),
                "height": float(attr_dict.get("height", 792)),
                "blocks": [],
                "words": [],
            }
        elif tag == "block" and self._cur_page is not None:
            try:
                self._cur_block = {
                    "xMin": float(attr_dict.get("xmin", 0)),
                    "yMin": float(attr_dict.get("ymin", 0)),
                    "xMax": float(attr_dict.get("xmax", 0)),
                    "yMax": float(attr_dict.get("ymax", 0)),
                    "words": [],
                }
            except (ValueError, TypeError):
                self._cur_block = None
        elif tag == "word" and self._cur_page is not None:
            try:
                self._cur_word_attrs = {
                    "xMin": float(attr_dict.get("xmin", 0)),
                    "yMin": float(attr_dict.get("ymin", 0)),
                    "xMax": float(attr_dict.get("xmax", 0)),
                    "yMax": float(attr_dict.get("ymax", 0)),
                }
                self._collecting_text = True
            except (ValueError, TypeError):
                self._cur_word_attrs = None

    def handle_endtag(self, tag: str) -> None:
        if tag == "page":
            if self._cur_page is not None:
                self.pages.append(self._cur_page)
            self._cur_page = None
        elif tag == "block":
            if self._cur_block is not None and self._cur_page is not None:
                blk = Block(
                    xMin=self._cur_block["xMin"],
                    yMin=self._cur_block["yMin"],
                    xMax=self._cur_block["xMax"],
                    yMax=self._cur_block["yMax"],
                    words=self._cur_block["words"],
                )
                self._cur_page["blocks"].append(blk)
            self._cur_block = None
        elif tag == "word":
            self._collecting_text = False
            self._cur_word_attrs = None

    def handle_data(self, data: str) -> None:
        if self._collecting_text and self._cur_word_attrs and self._cur_page is not None:
            text = data.strip()
            if len(text) >= MIN_WORD_CHARS:
                w = Word(
                    text=text,
                    xMin=self._cur_word_attrs["xMin"],
                    yMin=self._cur_word_attrs["yMin"],
                    xMax=self._cur_word_attrs["xMax"],
                    yMax=self._cur_word_attrs["yMax"],
                )
                self._cur_page["words"].append(w)
                if self._cur_block is not None:
                    self._cur_block["words"].append(w)


def run_pdftotext_bbox(pdf_path: Path, out_html: Path) -> bool:
    """Run Poppler pdftotext -bbox-layout. Returns True on success."""
    result = subprocess.run(
        [str(POPPLER_PDFTOTEXT), "-bbox-layout", str(pdf_path), str(out_html)],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def parse_bbox_html(html_path: Path) -> list[dict]:
    """Parse the bbox HTML and return list of page dicts."""
    content = html_path.read_text(encoding="utf-8")
    parser = BBoxHTMLParser()
    parser.feed(content)
    return parser.pages


# ── Block-level table detection ────────────────────────────────────────────────

def blocks_overlap_vertically(b1: Block, b2: Block, tolerance: float = Y_ROW_OVERLAP_PT) -> bool:
    """True if two blocks share vertical extent (same table row)."""
    return not (b1.yMax + tolerance < b2.yMin or b2.yMax + tolerance < b1.yMin)


def is_table_block(blk: Block) -> bool:
    """True if this block looks like a table column block (not prose)."""
    if not blk.words:
        return False
    # Wide blocks spanning most of the page are likely prose
    if blk.width > BLOCK_WIDTH_MAX:
        return False
    # Blocks with only 1 word that's a single char (superscript, etc.) are footnotes
    if len(blk.words) == 1 and len(blk.words[0].text) <= 1:
        return False
    return True


def detect_table_blocks(
    blocks: list[Block],
    page_width: float = 612.0,
) -> list[Block] | None:
    """Find the set of blocks that form a table grid.

    Strategy:
    1. Filter to candidate table blocks (not wide prose blocks).
    2. Find the largest group of blocks that share y-overlap (same "row band").
       Blocks in the same row band at different x-positions = table columns.
    3. Extend to adjacent row bands that have ≥2 overlapping column positions.
    4. Return the complete set of table blocks.
    """
    candidates = [b for b in blocks if is_table_block(b)]
    if len(candidates) < 4:
        return None

    # Sort by yMin
    candidates.sort(key=lambda b: b.yMin)

    # Group blocks into "row bands" by y-overlap
    row_bands: list[list[Block]] = []
    for blk in candidates:
        placed = False
        for band in row_bands:
            # Check if this block overlaps with the band's y-range
            band_yMin = min(b.yMin for b in band)
            band_yMax = max(b.yMax for b in band)
            if blk.yMin <= band_yMax + Y_ROW_OVERLAP_PT and blk.yMax >= band_yMin - Y_ROW_OVERLAP_PT:
                band.append(blk)
                placed = True
                break
        if not placed:
            row_bands.append([blk])

    # Find the core: row bands with ≥3 blocks (multiple columns)
    multi_col_bands = [(i, band) for i, band in enumerate(row_bands) if len(band) >= 3]

    if len(multi_col_bands) < 2:
        # Try ≥2 columns
        multi_col_bands = [(i, band) for i, band in enumerate(row_bands) if len(band) >= 2]
        if len(multi_col_bands) < 3:
            return None

    # Find contiguous range of multi-column bands
    indices = [i for i, _ in multi_col_bands]
    best_start = best_end = indices[0]
    best_len = 1
    cur_start = indices[0]
    cur_len = 1

    for prev, curr in zip(indices[:-1], indices[1:]):
        if curr == prev + 1:
            cur_len += 1
            if cur_len > best_len:
                best_len = cur_len
                best_start = cur_start
                best_end = curr
        else:
            cur_start = curr
            cur_len = 1

    # Get column x_mid positions from the core multi-col bands
    core_bands = row_bands[best_start:best_end + 1]
    core_x_mids = sorted(set(
        round(b.x_mid / 10) * 10  # round to nearest 10 for dedup
        for band in core_bands
        for b in band
    ))

    # Extend upward to include caption/header rows (1-col or multi-col rows)
    ext_start = best_start
    while ext_start > 0:
        prev_band = row_bands[ext_start - 1]
        # Stop at clearly prose bands
        if any(b.width > BLOCK_WIDTH_MAX for b in prev_band):
            break
        # Caption-like single wide block
        if len(prev_band) == 1 and prev_band[0].width > 250:
            # Include caption (it's the table label) then stop
            ext_start -= 1
            break
        ext_start -= 1

    # Extend downward to include footnote rows (short 1-col rows below data)
    ext_end = best_end
    while ext_end < len(row_bands) - 1:
        next_band = row_bands[ext_end + 1]
        # Stop at prose paragraphs
        if any(b.width > BLOCK_WIDTH_MAX for b in next_band):
            break
        # Short footnote block: 1 block, not too wide
        if len(next_band) == 1 and next_band[0].width < 150:
            ext_end += 1
        else:
            break

    # Collect all table blocks
    table_bands = row_bands[ext_start:ext_end + 1]
    table_blocks = [b for band in table_bands for b in band]

    if len(table_blocks) < 4:
        return None

    return table_blocks


def filter_blocks_in_bbox(
    blocks: list[Block],
    bbox: tuple[float, float, float, float],  # (x0, y_top, x1, y_bottom) top-down
    tolerance: float = 5.0,
) -> list[Block]:
    """Keep blocks whose centre falls inside the bbox."""
    x0, y_top, x1, y_bottom = bbox
    result = []
    for b in blocks:
        if (x0 - tolerance <= b.x_mid <= x1 + tolerance and
                y_top - tolerance <= b.y_mid <= y_bottom + tolerance):
            result.append(b)
    return result


# ── Block → table grid conversion ────────────────────────────────────────────

def blocks_to_grid(table_blocks: list[Block]) -> list[list[str]]:
    """Convert a set of table blocks into a 2D grid.

    Algorithm:
    1. Cluster blocks into row bands by y-overlap.
    2. Detect column positions from block x_mids (global across all row bands).
    3. For each row band, assign blocks to columns and read their text.
    """
    if not table_blocks:
        return []

    # Sort blocks by yMin
    sorted_blocks = sorted(table_blocks, key=lambda b: (b.yMin, b.xMin))

    # Cluster into row bands
    row_bands: list[list[Block]] = []
    for blk in sorted_blocks:
        placed = False
        for band in row_bands:
            band_yMax = max(b.yMax for b in band)
            band_yMin = min(b.yMin for b in band)
            if blk.yMin <= band_yMax + Y_ROW_OVERLAP_PT and blk.yMax >= band_yMin - Y_ROW_OVERLAP_PT:
                band.append(blk)
                placed = True
                break
        if not placed:
            row_bands.append([blk])

    # Detect column positions from all block x_mids
    x_mids = sorted(b.x_mid for b in table_blocks)
    if not x_mids:
        return []

    col_centres_grouped: list[list[float]] = [[x_mids[0]]]
    for x in x_mids[1:]:
        if x - col_centres_grouped[-1][-1] <= X_COL_SNAP_PT:
            col_centres_grouped[-1].append(x)
        else:
            col_centres_grouped.append([x])

    col_centres = [sum(grp) / len(grp) for grp in col_centres_grouped]

    def assign_col(x_mid: float) -> int:
        return min(range(len(col_centres)), key=lambda i: abs(col_centres[i] - x_mid))

    # Build grid
    grid: list[list[str]] = []
    for band in row_bands:
        cells: list[str] = [''] * len(col_centres)
        for blk in band:
            col_i = assign_col(blk.x_mid)
            text = blk.text_by_reading_order()
            if cells[col_i]:
                cells[col_i] += ' ' + text
            else:
                cells[col_i] = text
        grid.append(cells)

    return grid


# ── Pipe-table renderer ───────────────────────────────────────────────────────

def render_pipe_table(grid: list[list[str]]) -> str:
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


# ── Per-PDF extraction ─────────────────────────────────────────────────────────

def extract_table_from_pdf(
    pdf_filename: str,
    target_page_1indexed: int | None = None,
    debug: bool = False,
) -> tuple[str, str]:
    """Extract first table from PDF using Poppler -bbox-layout blocks.

    Returns (markdown_table, detection_method).
    """
    pdf_path = APA_DIR / pdf_filename
    html_path = OUT_DIR / f"{pdf_path.stem}_bbox.html"

    # Run pdftotext -bbox-layout if not already done
    if not html_path.exists():
        if debug:
            print(f"  Running pdftotext -bbox-layout on {pdf_filename}...")
        ok = run_pdftotext_bbox(pdf_path, html_path)
        if not ok:
            return f"(ERROR: pdftotext -bbox-layout failed on {pdf_filename})\n", "error"
    else:
        if debug:
            print(f"  Using existing bbox HTML: {html_path.name}")

    pages = parse_bbox_html(html_path)
    if debug:
        print(f"  Parsed {len(pages)} pages from bbox HTML")

    # Try pdfplumber detection for table bbox
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()

    structured = extract_pdf_structured(pdf_bytes)
    pp_tables = structured.get('tables', [])

    if pp_tables:
        t = pp_tables[0]
        page_1indexed = t.get('page', 1)
        bbox_pp = t.get('bbox')

        if debug:
            print(f"  pdfplumber detected {len(pp_tables)} table(s). Using table[0]: page={page_1indexed}")
            print(f"  pdfplumber bbox: {bbox_pp}")

        if page_1indexed <= len(pages) and bbox_pp:
            page_data = pages[page_1indexed - 1]
            all_blocks = page_data['blocks']

            # pdfplumber bbox (x0, top, x1, bottom) is ALREADY top-down like Poppler
            if isinstance(bbox_pp, dict):
                x0, y_top, x1, y_bot = bbox_pp['x0'], bbox_pp['top'], bbox_pp['x1'], bbox_pp['bottom']
            else:
                x0, y_top, x1, y_bot = bbox_pp

            if debug:
                print(f"  Poppler top-down bbox: ({x0:.1f}, {y_top:.1f}, {x1:.1f}, {y_bot:.1f})")
                print(f"  Total blocks on page: {len(all_blocks)}")

            # Filter blocks to table bbox
            table_blocks = filter_blocks_in_bbox(all_blocks, (x0, y_top, x1, y_bot), tolerance=5.0)

            if debug:
                print(f"  Blocks in bbox: {len(table_blocks)}")
                for b in table_blocks[:20]:
                    preview = b.text_by_reading_order().encode('ascii', 'replace').decode()[:50]
                    print(f"    [{b.xMin:.0f},{b.yMin:.0f}→{b.xMax:.0f},{b.yMax:.0f}] w={b.width:.0f} '{preview}'")

            if len(table_blocks) >= 3:
                grid = blocks_to_grid(table_blocks)
                if debug:
                    print(f"  Grid: {len(grid)} rows × {len(grid[0]) if grid else 0} cols")
                if len(grid) >= 2:
                    return render_pipe_table(grid), f"hybrid (pdfplumber bbox, page={page_1indexed})"

    # Fall back to pure block detection
    if debug:
        print("  Falling back to pure block-geometry detection...")

    search_pages = ([target_page_1indexed - 1] if target_page_1indexed
                    else list(range(min(len(pages), 15))))

    for page_0 in search_pages:
        if page_0 >= len(pages):
            continue

        page_data = pages[page_0]
        all_blocks = page_data['blocks']
        page_w = page_data['width']

        if debug:
            print(f"  Scanning page {page_0+1}: {len(all_blocks)} blocks")

        table_blocks = detect_table_blocks(all_blocks, page_width=page_w)
        if table_blocks is None:
            if debug:
                print(f"    No table detected on page {page_0+1}")
            continue

        if debug:
            print(f"    Detected {len(table_blocks)} table blocks")
            for b in table_blocks[:15]:
                preview = b.text_by_reading_order().encode('ascii', 'replace').decode()[:50]
                print(f"      [{b.xMin:.0f},{b.yMin:.0f}→{b.xMax:.0f},{b.yMax:.0f}] w={b.width:.0f} '{preview}'")

        grid = blocks_to_grid(table_blocks)
        if debug:
            print(f"    Grid: {len(grid)} rows × {len(grid[0]) if grid else 0} cols")

        if len(grid) >= 2:
            return render_pipe_table(grid), f"pure-block-detection (page={page_0+1})"

    return "(no table detected — both hybrid and pure block detection failed)\n", "failed"


# ── Sample HTML generation ─────────────────────────────────────────────────────

def save_sample_bbox_html(pdf_filename: str, max_lines: int = 200) -> None:
    """Save truncated real pdftotext -bbox-layout HTML for page 7 of korbmacher.

    This shows what REAL Poppler word-level bbox HTML looks like, for comparison
    with Option C's pdfminer line-level fallback.
    """
    pdf_path = APA_DIR / pdf_filename
    html_path = OUT_DIR / f"{Path(pdf_filename).stem}_bbox.html"

    if not html_path.exists():
        run_pdftotext_bbox(pdf_path, html_path)

    content = html_path.read_text(encoding='utf-8')
    all_lines = content.splitlines()

    # Find page 7 start
    page_count = 0
    start_line = 0
    for i, line in enumerate(all_lines):
        if '<page ' in line:
            page_count += 1
            if page_count == 7:
                start_line = i
                break

    if start_line == 0:
        selected = all_lines[:max_lines]
    else:
        header_lines = all_lines[:4]
        page7_lines = all_lines[start_line:start_line + max_lines - 5]
        selected = header_lines + ['<!-- ... pages 1-6 omitted ... -->'] + page7_lines

    sample_text = '\n'.join(selected) + '\n'
    (OUT_DIR / "sample-bbox.html").write_text(sample_text, encoding='utf-8')
    print(f"  Wrote sample-bbox.html ({len(selected)} lines, page 7 of korbmacher)")


# ── Entry point ────────────────────────────────────────────────────────────────

def _pr(s: str) -> None:
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode('ascii', 'replace').decode('ascii'))


def main() -> None:
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    # Verify Poppler binary exists and supports -bbox-layout
    if not POPPLER_PDFTOTEXT.exists():
        _pr(f"ERROR: Poppler pdftotext not found at {POPPLER_PDFTOTEXT}")
        _pr("  Try: conda install -c conda-forge poppler")
        sys.exit(1)

    version_result = subprocess.run(
        [str(POPPLER_PDFTOTEXT), "-h"],
        capture_output=True, text=True
    )
    version_out = version_result.stdout + version_result.stderr
    if "-bbox-layout" not in version_out:
        _pr("ERROR: This pdftotext does not support -bbox-layout")
        _pr(version_out[:200])
        sys.exit(1)

    version_line = next((l for l in version_out.splitlines() if 'version' in l.lower()), "unknown")
    _pr(f"Poppler pdftotext: {version_line.strip()}")
    _pr(f"Binary: {POPPLER_PDFTOTEXT}")

    # Save sample bbox HTML (page 7 of korbmacher)
    _pr("\nSaving sample-bbox.html (page 7 of korbmacher)...")
    save_sample_bbox_html("korbmacher_2022_kruger.pdf", max_lines=200)

    # Extract korbmacher Table 1 (page 7)
    _pr("\nExtracting korbmacher_2022_kruger.pdf Table 1 (page 7)...")
    md_korb, method_korb = extract_table_from_pdf(
        "korbmacher_2022_kruger.pdf",
        target_page_1indexed=7,
        debug=True,
    )
    out_korb = (
        "### Table 1\n\n"
        "*Kruger's (1999) findings: Mean comparative ability estimates and "
        "judgmental weight of own and peers' abilities.*\n\n"
        f"{md_korb}\n"
        f"*Option E: real Poppler pdftotext -bbox-layout, {method_korb}*\n"
    )
    (OUT_DIR / "korbmacher_table1.md").write_text(out_korb, encoding='utf-8')
    _pr("  Wrote korbmacher_table1.md")
    _pr("  Preview:")
    for line in out_korb.splitlines()[:22]:
        _pr("    " + line)

    # Extract ziano Table 1 (page 2)
    _pr("\nExtracting ziano_2021_joep.pdf Table 1 (page 2)...")
    md_ziano, method_ziano = extract_table_from_pdf(
        "ziano_2021_joep.pdf",
        target_page_1indexed=2,
        debug=True,
    )
    out_ziano = (
        "### Table 1\n\n"
        "*Descriptive and omnibus inferential statistics, across original studies "
        "and replications.*\n\n"
        f"{md_ziano}\n"
        f"*Option E: real Poppler pdftotext -bbox-layout, {method_ziano}*\n"
    )
    (OUT_DIR / "ziano_table1.md").write_text(out_ziano, encoding='utf-8')
    _pr("  Wrote ziano_table1.md")
    _pr("  Preview:")
    for line in out_ziano.splitlines()[:22]:
        _pr("    " + line)

    _pr(f"\nDone. All files written to: {OUT_DIR}")


if __name__ == "__main__":
    main()
