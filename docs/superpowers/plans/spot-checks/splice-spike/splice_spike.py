"""Splice spike (phase 0+).

Throwaway prototype that produces a single .md per input PDF combining:
- pdftotext text (cleaned of running headers)
- docpluck section boundaries (## headings)
- Camelot stream-flavor tables (### Table N + pipe-table)
- fragment-wrapping for tables Camelot misses

Per the 2026-05-09 5-option bake-off (LESSONS L-006), Camelot stream is the
chosen library for table cell extraction. pdfplumber returns 0 cells for
APA whitespace tables; Camelot returns clean cell grids without per-paper tuning.

This module is NOT production code. It will be deleted (or its surviving
helpers moved into proper modules) once phase 1 ships.
"""
from __future__ import annotations

import re
from typing import Optional, Sequence


# ---------------------------------------------------------------------------
# Camelot cell extraction with per-page caching
# ---------------------------------------------------------------------------

# Cache keyed by (pdf_path, page) → list of camelot.core.Table objects.
# Populated lazily on first request; one Camelot call per page across the run.
_CAMELOT_CACHE: dict[tuple[str, int], list] = {}


def _camelot_tables_for_page(pdf_path: str, page_1indexed: int) -> list:
    """Run Camelot stream on a single page, cached. Returns list of Camelot Tables."""
    key = (pdf_path, page_1indexed)
    if key in _CAMELOT_CACHE:
        return _CAMELOT_CACHE[key]
    try:
        import camelot
    except ImportError:
        _CAMELOT_CACHE[key] = []
        return []
    try:
        tables = list(camelot.read_pdf(pdf_path, pages=str(page_1indexed), flavor="stream"))
    except Exception:
        tables = []
    _CAMELOT_CACHE[key] = tables
    return tables


def _bbox_overlap_score(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    """Intersection-over-union for two (x0, y0, x1, y1) bboxes."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    if ix0 >= ix1 or iy0 >= iy1:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    a_area = max(0.0, (ax1 - ax0)) * max(0.0, (ay1 - ay0))
    b_area = max(0.0, (bx1 - bx0)) * max(0.0, (by1 - by0))
    union = a_area + b_area - inter
    if union <= 0:
        return 0.0
    return inter / union


def _camelot_cells_for_table(pdf_path: str, table: dict) -> list[list[str]] | None:
    """For a docpluck Table dict, return Camelot-extracted cell grid or None.

    Strategy: run Camelot stream on the table's page; pick the Camelot Table
    whose bbox overlaps best with docpluck's bbox; convert its DataFrame into
    a list of rows. Returns None if Camelot found nothing or has no overlap.
    """
    page = table.get("page", 0) or 0
    if page < 1:
        return None
    cam_tables = _camelot_tables_for_page(pdf_path, page)
    if not cam_tables:
        return None

    # Camelot bbox is (x0, y0_top, x1, y1_bottom) in PDF points (y from bottom).
    # docpluck bbox is (x0, top, x1, bottom) where top/bottom are from page top.
    # For overlap purposes, both spaces are consistent within themselves;
    # for landscape pages or single-table pages the best Camelot table is
    # usually the one with the largest area / most rows.
    target_bbox = tuple(table.get("bbox") or (0.0, 0.0, 0.0, 0.0))

    best = None  # (-score, -rows, idx)
    for i, ct in enumerate(cam_tables):
        try:
            cb = ct._bbox  # (x1, y1, x2, y2) in PDF points; y from bottom
        except AttributeError:
            cb = None
        score = 0.0
        if cb and target_bbox != (0.0, 0.0, 0.0, 0.0):
            # Convert candidate to (x0, y0, x1, y1) in any consistent space.
            # We only care about ranking; use raw IoU with whatever frames we have.
            score = _bbox_overlap_score(target_bbox, (cb[0], cb[1], cb[2], cb[3]))
        rows = len(ct.df)
        candidate = (-score, -rows, i)
        if best is None or candidate < best:
            best = candidate

    if best is None:
        return None
    _, _, idx = best
    chosen = cam_tables[idx]
    df = chosen.df

    # Convert DataFrame to list of rows. Strip cells; collapse internal whitespace.
    rows: list[list[str]] = []
    for ri in range(len(df)):
        row = [str(df.iloc[ri, ci]).replace("\n", " ").strip() for ci in range(len(df.columns))]
        rows.append(row)
    # Drop fully-empty leading/trailing rows
    while rows and not any(c for c in rows[0]):
        rows.pop(0)
    while rows and not any(c for c in rows[-1]):
        rows.pop()
    if len(rows) < 2:
        return None
    return rows


def pdfplumber_table_to_markdown(rows: Sequence[Sequence[str | None]]) -> str:
    """Render a pdfplumber-style table (list of rows of cells) as a GFM pipe table.

    - Cells that are None render as empty strings.
    - Embedded newlines in a cell collapse to a single space (pipe-table syntax
      cannot represent in-cell newlines).
    - Pipe characters in cells are escaped as ``\\|``.
    - Returns the empty string for tables with fewer than 2 rows (no data).
    """
    if len(rows) < 2:
        return ""

    def _cell(value: str | None) -> str:
        if value is None:
            return ""
        return value.replace("\n", " ").replace("|", "\\|").strip()

    header = [_cell(c) for c in rows[0]]
    body = [[_cell(c) for c in row] for row in rows[1:]]

    n_cols = len(header)
    lines: list[str] = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * n_cols) + " |")
    for row in body:
        # pad / truncate to header width so pipe-table is rectangular
        normalized = list(row) + [""] * max(0, n_cols - len(row))
        normalized = normalized[:n_cols]
        lines.append("| " + " | ".join(normalized) + " |")

    return "\n".join(lines) + "\n"


_TOKEN_RE = re.compile(r"[A-Za-z]{3,}|\d+(?:\.\d+)?")


def _tokens(s: str) -> set[str]:
    """Identifying tokens of a string: words ≥3 chars and numeric literals."""
    return set(_TOKEN_RE.findall(s))


def find_table_region_in_text(
    page_text: str,
    table_rows: Sequence[Sequence[Optional[str]]],
) -> Optional[tuple[int, int]]:
    """Locate the contiguous line range in ``page_text`` that the given table occupies.

    Algorithm: build the union of "identifying tokens" across all cells of the
    table. For each line, compute hit count = number of identifying tokens
    present. Scan all contiguous windows whose summed hit count is the highest;
    take the smallest such window with at least 60% of the table's tokens
    represented. Return ``(start_line, end_line_exclusive)`` or ``None`` if no
    window meets the threshold.

    This is a coarse, approximate algorithm by design — phase 0's whole point
    is to learn how often it actually works on real PDFs.
    """
    table_tokens: set[str] = set()
    for row in table_rows:
        for cell in row:
            if cell is None:
                continue
            table_tokens |= _tokens(cell)
    if not table_tokens:
        return None

    lines = page_text.split("\n")
    if not lines:
        return None

    per_line_hits = [len(_tokens(line) & table_tokens) for line in lines]

    # Cap window length to ~2x the table's row count + slack. This prevents
    # runaway windows on real PDFs where the page also contains body prose
    # with overlapping tokens (e.g., "Table 3" referenced again later on the
    # page, or numeric tokens that happen to appear in surrounding text).
    max_window = max(8, len(table_rows) * 2 + 2)

    # Search every contiguous window. n is small (one page worth of lines).
    # Among windows meeting the coverage threshold, prefer maximum hit count
    # (tightly packed token matches), tiebreak on shorter length.
    best: Optional[tuple[int, int, int]] = None  # (-hits, length, start)
    for start in range(len(lines)):
        running_token_set: set[str] = set()
        running_hits = 0
        for end in range(start, len(lines)):
            length = end - start + 1
            if length > max_window:
                break
            running_hits += per_line_hits[end]
            running_token_set |= _tokens(lines[end]) & table_tokens
            coverage = len(running_token_set) / len(table_tokens)
            if coverage < 0.6:
                continue
            candidate = (-running_hits, length, start)
            if best is None or candidate < best:
                best = candidate

    if best is None:
        return None
    _, length, start = best
    return (start, start + length)


def splice_tables_into_text(
    pdftotext_text: str,
    tables: list[dict],
) -> str:
    """Splice each table's markdown rendering into the page it belongs to.

    ``pdftotext_text`` uses ``\\f`` (form feed, ASCII 12) as the page
    separator — this is pdftotext's default behavior.

    Each entry in ``tables`` is a dict with at least:
      - ``page``: 0-based index of the page (matches ``pdftotext_text.split('\\f')``)
      - ``rows``: pdfplumber-style list-of-lists of cells

    For each table, we find its line range on its page using
    ``find_table_region_in_text``. If found, we replace those lines with the
    markdown-rendered table. If not, we prepend the markdown table at the top
    of the page with a visible diagnostic note so reviewers can spot the
    failure mode.
    """
    pages = pdftotext_text.split("\f")

    # Group tables by page so we can splice all of a page's tables before
    # moving on (table region indices shift as we splice; per-page reverse
    # ordering keeps indices stable).
    by_page: dict[int, list[dict]] = {}
    for t in tables:
        by_page.setdefault(t["page"], []).append(t)

    new_pages: list[str] = []
    for page_idx, page_text in enumerate(pages):
        page_tables = by_page.get(page_idx, [])
        if not page_tables:
            new_pages.append(page_text)
            continue

        # Locate each table's region first, then splice in reverse line order
        # so earlier indices stay valid.
        located: list[tuple[Optional[tuple[int, int]], dict]] = []
        for t in page_tables:
            region = find_table_region_in_text(page_text, t["rows"])
            located.append((region, t))

        lines = page_text.split("\n")

        # Splice located tables in reverse-start order.
        located_with_region = [
            (region, t) for (region, t) in located if region is not None
        ]
        located_with_region.sort(key=lambda x: x[0][0], reverse=True)
        for region, t in located_with_region:
            start, end = region
            md = pdfplumber_table_to_markdown(t["rows"]).rstrip("\n")
            lines[start:end] = [md]

        # Prepend unlocated tables (with diagnostic note) at the top of page.
        unlocated = [t for (region, t) in located if region is None]
        if unlocated:
            preface: list[str] = []
            for t in unlocated:
                md = pdfplumber_table_to_markdown(t["rows"]).rstrip("\n")
                note = (
                    "[splice-spike: table location not found on this page; "
                    "inserted at top]"
                )
                preface.append(note)
                preface.append(md)
                preface.append("")
            lines = preface + lines

        new_pages.append("\n".join(lines))

    return "\n".join(new_pages)


def _load_tables_for_spike(pdf_path: str) -> tuple[str, list[dict]]:
    """Load text and tables (lattice→rows conversion) from a PDF.

    Used by the older `splice_tables_into_text` path. The newer
    `render_pdf_to_markdown` uses `_load_full_for_render` instead, which
    returns the richer Table/Figure/Section objects directly.
    """
    from docpluck.extract_structured import extract_pdf_structured

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    result = extract_pdf_structured(pdf_bytes)
    text: str = result["text"]

    out: list[dict] = []
    for t in result.get("tables", []):
        page_1indexed: int = t["page"]
        page_0indexed = page_1indexed - 1

        cells = t.get("cells") or []
        if cells:
            n_rows = max(c["r"] for c in cells) + 1
            n_cols = max(c["c"] for c in cells) + 1
            grid: list[list[str]] = [[""] * n_cols for _ in range(n_rows)]
            for c in cells:
                grid[c["r"]][c["c"]] = c["text"]
            rows = grid
        else:
            raw = t.get("raw_text") or ""
            rows = [[line] for line in raw.splitlines() if line.strip()]

        out.append({"page": page_0indexed, "rows": rows})

    return text, out


# ---------------------------------------------------------------------------
# Iteration 2: full markdown rendering with sections + figures + clean tables
# ---------------------------------------------------------------------------


def _table_caption_short(caption: str | None, label: str | None) -> str:
    """Pull a short human caption from the docpluck Table.caption field.

    docpluck's `caption` for an isolated table includes the label, the short
    caption sentence, AND the entire flattened cell content (because pdfplumber
    didn't structure it). We want just the LABEL line + the description sentence.
    """
    if not caption:
        return label or ""
    lines = [ln.strip() for ln in caption.splitlines() if ln.strip()]
    if not lines:
        return label or ""
    # First line is usually the label. If the label is on its own line, the
    # second line is the description. If label and description are joined,
    # split at the first ". " in the first line.
    first = lines[0]
    if label and first.startswith(label) and len(first) > len(label) + 2:
        # Label and description on same line, e.g. "Table 1. Descriptive ..."
        rest = first[len(label):].lstrip(" .")
        # Cut at first period+space (end of caption sentence)
        if ". " in rest:
            rest = rest.split(". ", 1)[0] + "."
        return rest
    if len(lines) >= 2:
        desc = lines[1]
        if ". " in desc:
            desc = desc.split(". ", 1)[0] + "."
        return desc
    return ""


def _format_table_md(table: dict, pdf_path: str | None = None) -> str:
    """Render a docpluck Table as a self-contained markdown block.

    Order of preference for cell content:
      1. ``cells`` populated by docpluck (lattice tables) → render directly.
      2. Camelot stream extraction (whitespace tables, the APA case) → render.
      3. Raw text in a fenced code block (last-resort fallback if Camelot fails).
    """
    label = table.get("label") or "Table"
    short_caption = _table_caption_short(table.get("caption"), label)

    block_parts = [f"### {label}"]
    if short_caption and short_caption != label:
        block_parts.append(f"*{short_caption}*")
        block_parts.append("")

    # 1. Lattice table from docpluck
    cells = table.get("cells") or []
    if cells:
        n_rows = max(c["r"] for c in cells) + 1
        n_cols = max(c["c"] for c in cells) + 1
        grid: list[list[str]] = [[""] * n_cols for _ in range(n_rows)]
        for c in cells:
            grid[c["r"]][c["c"]] = c["text"]
        if n_rows >= 2:
            block_parts.append(pdfplumber_table_to_markdown(grid).rstrip("\n"))
            return "\n".join(block_parts)

    # 2. Camelot stream extraction
    if pdf_path:
        cam_rows = _camelot_cells_for_table(pdf_path, table)
        if cam_rows:
            block_parts.append(pdfplumber_table_to_markdown(cam_rows).rstrip("\n"))
            return "\n".join(block_parts)

    # 3. Last-resort fallback: raw_text in a code block
    raw = (table.get("raw_text") or "").rstrip()
    raw_lines = raw.splitlines()
    drop_count = 0
    for ln in raw_lines[:3]:
        stripped = ln.strip()
        if not stripped:
            drop_count += 1
            continue
        if stripped == label:
            drop_count += 1
            continue
        if short_caption and stripped.startswith(short_caption[:30]):
            drop_count += 1
            continue
        break
    body = "\n".join(raw_lines[drop_count:]).rstrip()
    if body:
        block_parts.append("```")
        block_parts.append(body)
        block_parts.append("```")

    return "\n".join(block_parts)


def _format_figure_md(fig: dict) -> str:
    """Render a docpluck Figure as an italicized caption line."""
    label = fig.get("label") or "Figure"
    caption = (fig.get("caption") or "").strip()
    # Caption sometimes contains the entire surrounding page text after the figure;
    # cut at the first newline + double-space or at first ".\f" / page break artifact.
    caption = caption.split("\f")[0].strip()
    # Cut at first ". " after >40 chars to keep just the figure description.
    if len(caption) > 200 and ". " in caption[:300]:
        idx = caption.index(". ", 40)
        caption = caption[: idx + 1]
    if caption.startswith(label):
        caption = caption[len(label):].lstrip(" .")
    return f"*{label}. {caption}*" if caption else f"*{label}.*"


def _page_char_starts(text: str) -> list[int]:
    """Return the char-offset where each page starts in `text` (\\f-separated)."""
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\f":
            starts.append(i + 1)
    return starts


def _locate_table_per_page(
    text: str,
    page_starts: list[int],
    table: dict,
) -> tuple[int, int] | None:
    """Find the (char_start, char_end) of a table's region in `text`.

    Constrains search to the table's declared page (1-indexed `page` field).
    Returns None if the table cannot be located.
    """
    page_1 = table.get("page", 1)
    page_idx = page_1 - 1
    if page_idx < 0 or page_idx >= len(page_starts):
        return None
    page_start = page_starts[page_idx]
    page_end = (
        page_starts[page_idx + 1] - 1
        if page_idx + 1 < len(page_starts)
        else len(text)
    )
    page_text = text[page_start:page_end]
    raw = table.get("raw_text") or ""
    rows = [[ln] for ln in raw.splitlines() if ln.strip()]
    if not rows:
        return None
    region = find_table_region_in_text(page_text, rows)
    if region is None:
        return None
    line_start, line_end = region
    lines = page_text.split("\n")
    char_in_page_start = sum(len(ln) + 1 for ln in lines[:line_start])
    char_in_page_end = sum(len(ln) + 1 for ln in lines[:line_end])
    return (page_start + char_in_page_start, page_start + char_in_page_end)


def _join_split_captions(text: str) -> str:
    """Join captions that pdftotext split across paragraphs.

    Common patterns where a caption like "Table 1: Kruger's findings..." gets
    split across paragraph boundaries by pdftotext's column rendering:

    - "T\\n\\n1: Kruger's findings..." → "Table 1: Kruger's findings..."
    - "Fig.\\n\\n2.1: ...\\n\\n... continuation" → "Figure 2.1: ... continuation"

    The function rejoins these into a single line so caption-absorption works.
    """
    # Pattern: "T" or "Fig"/"Figure" alone on a line, followed by blank line,
    # followed by "<number>: <description>"
    text = re.sub(
        r"^(T|Table|Fig\.?|Figure)\s*\n\s*\n\s*(\d+(?:\.\d+)?)([\s.:\-—–]+)",
        r"\1 \2\3",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    # Normalize "T 1:" → "Table 1:", "Fig 2." → "Figure 2."
    text = re.sub(
        r"^T\s+(\d+(?:\.\d+)?)([\s.:\-—–])",
        r"Table \1\2",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"^Fig\.?\s+(\d+(?:\.\d+)?)([\s.:\-—–])",
        r"Figure \1\2",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    return text


def _existing_table_numbers(text: str) -> set[int]:
    """Collect the set of table numbers already present as ``### Table N`` headings."""
    nums: set[int] = set()
    for m in re.finditer(r"^### Table\s+(\d+)", text, re.MULTILINE):
        nums.add(int(m.group(1)))
    return nums


def _dedupe_table_blocks(text: str) -> str:
    """Among multiple ``### Table N`` blocks with the same N, keep the one with
    the most pipe-table rows (``| ... |`` lines). Drop the others.

    A "block" runs from a ``### Table N`` heading to the next ``### `` /
    ``## `` heading or end of text.
    """
    blocks: list[tuple[int, int, int, int]] = []  # (start, end, num, pipe_rows)
    matches = list(re.finditer(r"^### Table\s+(\d+)\s*$", text, re.MULTILINE))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # Don't span across an H2 boundary (like "## Tables (unlocated in body)")
        h2 = re.search(r"^## ", text[start + 1:end], re.MULTILINE)
        if h2:
            end = start + 1 + h2.start()
        block_text = text[start:end]
        pipe_rows = len(re.findall(r"^\| ", block_text, re.MULTILINE))
        num = int(m.group(1))
        blocks.append((start, end, num, pipe_rows))

    # Group by number; pick the block with most pipe_rows; mark others for removal.
    by_num: dict[int, list[tuple[int, int, int, int]]] = {}
    for b in blocks:
        by_num.setdefault(b[2], []).append(b)
    to_remove: list[tuple[int, int]] = []
    for num, group in by_num.items():
        if len(group) <= 1:
            continue
        group.sort(key=lambda b: (-b[3], b[0]))  # max pipe_rows, then earliest
        for b in group[1:]:
            to_remove.append((b[0], b[1]))

    if not to_remove:
        return text
    to_remove.sort(reverse=True)
    out = text
    for s, e in to_remove:
        out = out[:s] + out[e:]
    return out


def _wrap_table_fragments(
    text: str,
    *,
    existing_table_nums: set[int] | None = None,
) -> str:
    """Wrap runs of consecutive "fragmented" short paragraphs in fenced code
    blocks.

    Tables missed by pdfplumber show up in pdftotext as a sequence of short
    paragraphs (often one token per paragraph) separated by blank lines.

    A "fragment paragraph" is: a non-empty single-line paragraph of ≤80
    characters that doesn't look like a complete prose sentence, doesn't start
    with markdown markers, and isn't a heading.

    A "fragment run" is 5+ consecutive fragment paragraphs.

    If the paragraph immediately preceding the run looks like a table caption
    (matches ``^(?:Table|T|Fig\\.?|Figure)\\s*\\d+`` with a description), the run is
    prefixed with ``### Table N`` / ``### Figure N`` and emitted as a labeled
    block.
    """
    paragraphs = re.split(r"\n\s*\n", text)
    n = len(paragraphs)

    SENTENCE_TAIL = re.compile(r"[.!?]\)?\s*$")
    NUMERIC_TAIL = re.compile(r"\d+\.\d*\s*$")
    ABBREV_TAIL = re.compile(r"\b(?:e\.g|i\.e|cf|et al|Mr|Dr|Fig|Tab|vs|St)\.?\s*$", re.IGNORECASE)
    CAPTION_RE = re.compile(
        r"^\s*(?P<label>(?:Table|T|Fig\.?|Figure)\s*\d+(?:\.\d+)?)"
        r"[\s.:\-—–]*"
        r"(?P<desc>.*\S)?\s*$",
        re.IGNORECASE,
    )

    def is_fragment(p: str) -> bool:
        s = p.strip()
        if not s:
            return False
        if len(s) > 100:
            return False
        if s.startswith(("#", "|", "```", "*", ">")):
            return False
        # Allow 2- or 3-line paragraphs that are still short overall (table cells
        # that pdftotext kept on adjacent lines without blank line between).
        line_count = s.count("\n") + 1
        if line_count > 3:
            return False
        # Reject "real prose" sentences: end with .!?, ≥6 words, no numeric/abbrev tail.
        if SENTENCE_TAIL.search(s) and len(s.split()) >= 6:
            if not (NUMERIC_TAIL.search(s) or ABBREV_TAIL.search(s)):
                return False
        return True

    out_parts: list[str] = []
    i = 0
    while i < n:
        run_start = i
        while i < n and is_fragment(paragraphs[i]):
            i += 1
        run_len = i - run_start
        if run_len >= 5:
            # Optionally absorb a preceding caption-style paragraph (look back
            # up to 2 paragraphs because the caption description sometimes
            # continues across one paragraph break).
            caption_label: str | None = None
            caption_desc: str | None = None
            caption_label_num: int | None = None
            for lookback in (1, 2):
                if len(out_parts) < lookback:
                    break
                idx = -lookback
                target = out_parts[idx].strip()
                if target.startswith(("#", "```", "*")):
                    break
                m = CAPTION_RE.match(target)
                if m and len(target) <= 250:
                    caption_label = m.group("label")
                    desc_parts = [(m.group("desc") or "").strip()]
                    # If lookback==2, the paragraph at -1 is a continuation of
                    # the description (short, no caption prefix).
                    if lookback == 2:
                        cont = out_parts[-1].strip()
                        if cont and not CAPTION_RE.match(cont) and len(cont) <= 200:
                            desc_parts.append(cont)
                    caption_desc = " ".join(p for p in desc_parts if p).strip()
                    # Pop the absorbed paragraphs.
                    for _ in range(lookback):
                        out_parts.pop()
                    break

            fragment_lines = [paragraphs[j].strip() for j in range(run_start, i)]
            block_parts: list[str] = []
            suppressed = False
            if caption_label:
                # Normalize the label: "T 1" → "Table 1", "Fig 2" → "Figure 2"
                norm_label = re.sub(r"^T\b", "Table", caption_label, flags=re.IGNORECASE)
                norm_label = re.sub(r"^Fig\.?", "Figure", norm_label, flags=re.IGNORECASE)
                # If a real ``### Table N`` already exists for this number from
                # a Camelot splice, drop this fragment-wrap synthesis to avoid
                # a duplicate `### Table N` block.
                num_match = re.search(r"\d+", norm_label)
                if (
                    existing_table_nums
                    and num_match
                    and norm_label.lower().startswith("table")
                    and int(num_match.group(0)) in existing_table_nums
                ):
                    suppressed = True
                else:
                    block_parts.append(f"### {norm_label}")
                    if caption_desc:
                        block_parts.append(f"*{caption_desc}*")
                        block_parts.append("")
            if not suppressed and caption_label:
                # Only emit fragment-wrap blocks that have an absorbed caption.
                # Unlabeled fragment-wraps (no caption found) are typically
                # leftover noise from fragmented tables Camelot already
                # rendered as a labeled pipe-table elsewhere — emitting them
                # produces duplicate content as a code block.
                block_parts.append("```")
                block_parts.append("\n".join(fragment_lines))
                block_parts.append("```")
                out_parts.append("\n".join(block_parts))
        else:
            for j in range(run_start, i):
                out_parts.append(paragraphs[j])
        if i < n:
            out_parts.append(paragraphs[i])
            i += 1

    return "\n\n".join(p for p in out_parts if p)


def _strip_running_headers(text: str) -> str:
    """Strip lines that appear at the same form-feed-bounded position across
    multiple pages, plus standalone short numeric "page number" lines.

    Form-feeds are preserved.
    """
    pages = text.split("\f")
    if len(pages) < 3:
        return text  # not enough pages to detect repetition

    # Tally line frequency across pages (only look at first 3 + last 3 lines of
    # each page — running headers/footers live there).
    line_freq: dict[str, int] = {}
    for page in pages:
        plines = [ln.strip() for ln in page.split("\n") if ln.strip()]
        edge_lines = set(plines[:3]) | set(plines[-3:])
        for ln in edge_lines:
            line_freq[ln] = line_freq.get(ln, 0) + 1

    # A line that appears at the edge of ≥40% of pages is a running header.
    threshold = max(3, len(pages) * 4 // 10)

    out_pages: list[str] = []
    for page in pages:
        kept: list[str] = []
        for ln in page.split("\n"):
            stripped = ln.strip()
            if stripped and line_freq.get(stripped, 0) >= threshold:
                continue  # running header
            # Standalone page numbers (≤4 digits, possibly with surrounding ws)
            if re.fullmatch(r"\s*\d{1,4}\s*", ln):
                continue
            kept.append(ln)
        out_pages.append("\n".join(kept))
    return "\f".join(out_pages)


def _strip_leading_heading(body: str, heading: str) -> str:
    """Strip the heading text (and optional numbering prefix like ``1.``) from
    the start of a section body so the rendered output doesn't show
    ``## Introduction\\n\\nIntroduction\\n``.

    Handles: bare heading on its own line, ``N.`` / ``N.M.`` numbering, and the
    heading appearing as the first line of a paragraph.
    """
    if not body or not heading:
        return body
    # Skip leading whitespace
    stripped = body.lstrip()
    leading_ws = body[: len(body) - len(stripped)]
    # Match optional "N." or "N.M." numbering, then the heading text, then optional newline
    pattern = re.compile(
        r"^(?:\d+(?:\.\d+)*\.?\s*)?" + re.escape(heading) + r"\s*\n?",
        re.IGNORECASE,
    )
    m = pattern.match(stripped)
    if m:
        return leading_ws + stripped[m.end():]
    return body


def render_pdf_to_markdown(pdf_path: str) -> str:
    """Render a PDF as a single Markdown document.

    Pipeline:
      1. ``extract_pdf_structured`` → raw text (with form-feeds) + tables + figures.
      2. ``_strip_running_headers`` → drop repeating page edges + page-number lines,
         keeping form-feeds intact.
      3. Locate each table on its declared page using the per-page locator.
      4. Locate each section using ``extract_sections(text=cleaned)``.
      5. Splice in reverse char-offset order:
           - tables: replace located region with formatted table block
           - sections: insert ``## <heading>`` and strip duplicated heading from body
      6. Replace remaining form-feeds with blank lines, collapse runs of newlines.
      7. Append a "Figures" appendix with italicized captions.
      8. Append a "Tables (unlocated)" appendix for tables that couldn't be placed.
    """
    from docpluck import extract_pdf_structured, extract_sections

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    structured = extract_pdf_structured(pdf_bytes)
    raw_text: str = structured["text"]
    tables = structured.get("tables", [])
    figures = structured.get("figures", [])

    cleaned = _strip_running_headers(raw_text)
    page_starts = _page_char_starts(cleaned)

    # Re-extract sections from the cleaned text so char offsets line up.
    sd = extract_sections(text=cleaned, source_format="pdf")
    sections = list(sd.sections)

    # Each edit is (char_start, char_end, replacement). Applied to `cleaned`
    # in reverse char-start order.
    edits: list[tuple[int, int, str]] = []

    # Tables first (so we can detect overlap with section ranges later).
    unlocated: list[dict] = []
    for t in tables:
        region = _locate_table_per_page(cleaned, page_starts, t)
        if region is None:
            unlocated.append(t)
            continue
        char_start, char_end = region
        replacement = "\n\n" + _format_table_md(t, pdf_path=pdf_path) + "\n\n"
        edits.append((char_start, char_end, replacement))

    # Section heading insertions: replace [char_start, char_end] with
    # `## heading\n\n{body-without-heading}`. If a table edit lies fully within
    # this section, leave the section body alone for the table edit to handle —
    # the section replacement will preserve text up-to and after the table region
    # is invalid. Solve this by ONLY replacing the leading heading-text, not the
    # entire section body.
    for sec in sections:
        if sec.canonical_label.name == "unknown" and sec.char_start == 0:
            continue
        heading = sec.heading_text or sec.label.replace("_", " ").title()
        # Find length of the heading-prefix in the body (numbering + heading + delim + newline).
        section_body = cleaned[sec.char_start:sec.char_end]
        leading = section_body.lstrip()
        leading_ws_len = len(section_body) - len(leading)
        # Match: optional "N." or "N.M." numbering, the heading, optional trailing
        # delimiters (":", ".", "—", " - ", ","), optional whitespace+newline.
        pattern = re.compile(
            r"^(?:\d+(?:\.\d+)*\.?\s*)?"
            + re.escape(heading)
            + r"\s*[:.\-—–,]*\s*\n?",
            re.IGNORECASE,
        )
        m = pattern.match(leading)
        prefix_len = leading_ws_len + (m.end() if m else 0)
        # Also try to absorb any orphan trailing-numbering on the line BEFORE this
        # section start, e.g. "...references.\n\n1. \n\nIntroduction" — the "1. "
        # is left behind by extract_sections splitting at the heading boundary.
        # Look back ≤20 chars for a pattern like "\n\n<digits>.\s*\n" and absorb it.
        lookback_start = max(0, sec.char_start - 20)
        lookback_text = cleaned[lookback_start:sec.char_start]
        orphan_match = re.search(
            r"\n\s*\d+(?:\.\d+)*\.?\s*\n?\s*$",
            lookback_text,
        )
        adjusted_start = sec.char_start
        if orphan_match:
            adjusted_start = lookback_start + orphan_match.start()
        edits.append((
            adjusted_start,
            sec.char_start + prefix_len,
            f"\n\n## {heading}\n\n",
        ))

    # Apply edits in reverse char-start order. Sort key: (start, end) descending.
    edits.sort(key=lambda e: (e[0], e[1]), reverse=True)
    out = cleaned
    for char_start, char_end, replacement in edits:
        out = out[:char_start] + replacement + out[char_end:]

    # ---- Post-processing ----
    out = out.replace("\f", "\n\n")
    # Strip standalone "..." or "…" runs left behind by half-detected tables.
    out = re.sub(r"^[\s.…]+$", "", out, flags=re.MULTILINE)
    # Strip lines that are only stray punctuation / single chars.
    out = re.sub(r"^\s*[.,;:\-—–]\s*$", "", out, flags=re.MULTILINE)
    # Strip orphan numbering lines like "1." or "2.1." on their own.
    out = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s*$", "", out, flags=re.MULTILINE)
    # Collapse 3+ blank lines.
    out = re.sub(r"\n{3,}", "\n\n", out)
    # Join split table/figure captions before wrapping.
    out = _join_split_captions(out)
    # Wrap runs of fragmented "table-like" short lines in code blocks. Tables
    # missed by pdfplumber show up in pdftotext as one-word-per-line fragments.
    # Pass the set of table numbers already present as ``### Table N`` headings
    # (from the splice step) so fragment-wrap doesn't duplicate them.
    existing_table_nums = _existing_table_numbers(out)
    out = _wrap_table_fragments(out, existing_table_nums=existing_table_nums)
    # Final dedupe pass: among multiple ``### Table N`` blocks for the same N,
    # keep the one with the most pipe-table rows.
    out = _dedupe_table_blocks(out)
    out = out.strip() + "\n"

    # ---- Appendices ----
    appendix_parts: list[str] = []
    if figures:
        appendix_parts.append("\n## Figures\n")
        for fig in figures:
            appendix_parts.append(_format_figure_md(fig))
            appendix_parts.append("")
    if unlocated:
        appendix_parts.append("\n## Tables (unlocated in body)\n")
        for t in unlocated:
            appendix_parts.append(_format_table_md(t, pdf_path=pdf_path))
            appendix_parts.append("")

    if appendix_parts:
        out = out.rstrip() + "\n\n" + "\n".join(appendix_parts).rstrip() + "\n"

    # Final dedupe pass — also covers ``### Table N`` blocks that ended up in
    # the appendix vs. inline.
    out = _dedupe_table_blocks(out)
    return out


def _run_cli(pdf_path: str) -> str:
    return render_pdf_to_markdown(pdf_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("usage: python splice_spike.py <pdf-path>", file=sys.stderr)
        sys.exit(2)
    output = _run_cli(sys.argv[1])
    # Re-open stdout in UTF-8 mode for Windows compatibility (Windows default
    # is often cp1252 which cannot encode many Unicode chars in PDF text).
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
    sys.stdout.write(output)
