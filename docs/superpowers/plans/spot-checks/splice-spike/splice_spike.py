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


def _html_escape(s: str | None) -> str:
    """Escape HTML special characters for safe inclusion in cell content,
    then convert merge-separator placeholders to ``<br>``."""
    if s is None:
        return ""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace(_MERGE_SEPARATOR, "<br>")
    )


_MERGE_SEPARATOR = "\x00BR\x00"  # placeholder swapped to <br> after escaping


def _merge_continuation_rows(rows: list[list[str]]) -> list[list[str]]:
    """Merge rows where the first column is empty INTO the previous row.

    Camelot output for tables with multi-line cells often appears as:
        ['2a', 'People underestimate...']
        ['',   'continuation of the hypothesis']
        ['',   'still continuing']

    We merge those continuations back into the parent row's cell, joined
    with a placeholder that is later replaced by ``<br>`` AFTER HTML
    escaping (so the placeholder isn't escaped to ``&lt;br&gt;``).
    """
    def _looks_prose_like(cells: list[str]) -> bool:
        """A continuation row should have at least one cell with prose-like
        content (≥2 words OR ≥10 chars). Short single-token cells like "2" or
        "0.45" are likely separate data rows with an empty first column, not
        continuations."""
        for c in cells:
            s = (c or "").strip()
            if not s:
                continue
            if len(s.split()) >= 2 or len(s) >= 10:
                return True
        return False

    def _prev_col0_is_wrap(parent: list[str]) -> bool:
        """The previous row's col 0 ends with an EXPLICIT wrap mark (``/``,
        ``-``, ``—``, ``–``) — strong signal that the next col-0-only row
        is a continuation of this cell. Lowercase-letter endings are NOT
        used as a signal because group-separator labels (``Easy``,
        ``Difficult``, ``Ability``) usually end in lowercase too."""
        if not parent or not parent[0]:
            return False
        s = parent[0].rstrip()
        if not s:
            return False
        return s.endswith(("/", "-", "—", "–"))

    def _is_label_modifier(s: str) -> bool:
        """A col-0 value that's a parenthetical label modifier — i.e., a
        continuation marker like ``(Extension)``, ``(Original)``, ``(cont.)``,
        ``(continued)`` rather than a new row anchor.

        These appear in 2-row hypothesis tables where the first row's col 0
        is a hypothesis number (``H3``) and the second row's col 0 carries a
        condition label that visually belongs with the H-number above.
        """
        s = s.strip()
        if not s:
            return False
        if re.fullmatch(r"\([^)]+\)", s):
            return True
        if re.fullmatch(r"(?:cont\.?|continued|ctd\.?)", s, re.IGNORECASE):
            return True
        return False

    _SENTENCE_END = re.compile(r"[.!?]['\")\]]?\s*$")
    _WRAP_PUNCT_END = re.compile(r"[/,;:\-—–]\s*$")
    _CONJUNCTION_END = re.compile(
        r"\b(?:and|or|but|of|the|in|for|with|to|a|an|on|at|by|from|as|is|are"
        r"|was|were|be|been|than|that|which|who|when|where|while|during|after"
        r"|before|because|since|though|although|into|onto|upon)$",
        re.IGNORECASE,
    )

    def _cell_looks_incomplete(s: str) -> bool:
        """A cell whose content suggests it wraps to the next row.

        Signals: doesn't end with sentence terminator AND ends with wrap
        punctuation (/-,;:—–), a conjunction/preposition/article, or a
        lowercase letter on a multi-word string. Single-word labels (``M``,
        ``SD``, ``Variable``) are NOT flagged — they're complete labels.
        """
        s = (s or "").strip()
        if not s:
            return False
        if _SENTENCE_END.search(s):
            return False
        # Pure numeric data cells are complete.
        if re.fullmatch(r"[\d.,%*∗+\-−–—]+", s):
            return False
        if _WRAP_PUNCT_END.search(s):
            return True
        if _CONJUNCTION_END.search(s):
            return True
        # Multi-word string ending in lowercase = mid-sentence
        if len(s.split()) >= 2 and re.search(r"[a-z]\s*$", s):
            return True
        return False

    def _row_looks_incomplete(row: list[str]) -> bool:
        return sum(1 for c in row if _cell_looks_incomplete(c)) >= 2

    def _row_cells_are_short(row: list[str], threshold: int = 60) -> bool:
        return all(len((c or "").strip()) <= threshold for c in row)

    out: list[list[str]] = []
    for row in rows:
        first = row[0].strip() if row else ""
        rest_has_content = any((c or "").strip() for c in row[1:])

        # Case A: row has content only in non-first columns → continuation
        # of the parent row's data cells (multi-line cell wrapping in col 1+).
        if out and not first and rest_has_content and _looks_prose_like(row[1:]):
            parent = out[-1]
            for i in range(min(len(row), len(parent))):
                v = (row[i] or "").strip()
                if not v:
                    continue
                if parent[i].strip():
                    parent[i] = parent[i] + _MERGE_SEPARATOR + v
                else:
                    parent[i] = v
            continue

        # Case B: row has content only in col 0 (others empty) AND the
        # previous row's col 0 looks like it wraps → continuation of col 0.
        if (
            out
            and first
            and not rest_has_content
            and _prev_col0_is_wrap(out[-1])
        ):
            parent = out[-1]
            parent[0] = parent[0].rstrip() + first if parent[0].rstrip().endswith(("/", "-")) else parent[0].rstrip() + " " + first
            continue

        # Case C: row's col 0 is a "label modifier" (parenthetical like
        # ``(Extension)``) AND previous row's tail cells look incomplete
        # AND current row's cells are short. Treat the row as a
        # continuation of the previous logical row's hypothesis text.
        # This handles 2-row hypothesis layouts where pdftotext stream-
        # rendering breaks "H3 / Compared..." across two rows where col 0
        # carries the condition label.
        if (
            out
            and first
            and _is_label_modifier(first)
            and _row_looks_incomplete(out[-1])
            and _row_cells_are_short(row, threshold=60)
        ):
            parent = out[-1]
            for i in range(min(len(row), len(parent))):
                v = (row[i] or "").strip()
                if not v:
                    continue
                if parent[i].strip():
                    parent[i] = parent[i] + _MERGE_SEPARATOR + v
                else:
                    parent[i] = v
            continue

        out.append([(c or "").strip() for c in row])
    return out


def _split_mashed_cell(s: str) -> str:
    """Insert ``<br>`` at apparent column-undercount boundaries inside a cell.

    Camelot stream's whitespace-based column detection occasionally fails on
    tightly packed columns and concatenates two columns' content into one
    cell — e.g., ``Original domain groupEasy domain group``. This function
    detects the boundary with a conservative rule and inserts a visible line
    break so the cell is at least readable, even if the table's column count
    is still off.

    Two boundary types, each with its own length rule:

    - Camel-case (``[a-z][A-Z]``):
        - **Strict rule:** the LOWERCASE-only run preceding the boundary
          must be ≥ 4 chars. Walks back only while lowercase, so a
          preceding capital stops the count. Rules out ``macOS``,
          ``iPhone``, ``WiFi``, ``JavaScript``, ``WordPress``;
          ``groupEasy`` (``group`` = 5) splits.
        - **Relaxed rule (iteration 10):** the lowercase run is ≥ 3 chars
          AND is anchored on the LEFT by a whitespace character or the
          start of the cell, AND the camel-case Capital is followed by a
          lowercase letter (so it's a real word, not an all-caps token
          like ``OS`` or ``CI``). Catches ``lowPositive`` /
          ``lowNegative`` / ``highRisk`` inside multi-word cells (e.g.,
          ``Risk is lowPositive affect``) without false-splitting brand
          names like ``macOS`` (no whitespace anchor) or ``WordPress``
          (``ord`` is preceded by uppercase ``W``, not whitespace).

    - Letter→digit (``[a-zA-Z]\\d``): the any-letter WORD preceding the
      boundary must be ≥ 4 chars (counting both upper and lower). This
      catches column-mash like ``Year2011``, ``size80``, ``Gender35`` —
      where the LEFT word starts with a capital but is short enough that a
      lowercase-only rule would miss it. Additionally requires the digit
      to be followed by another digit, end-of-string, or punctuation
      (rules out ordinals like ``2a`` or labels like ``H1``).

    Uses the same merge-separator placeholder as the cell-continuation
    merger, so the placeholder survives HTML escaping and renders as
    ``<br>``.
    """
    if not s or len(s) < 6:
        return s
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        out.append(s[i])
        if i + 1 < n:
            cur, nxt = s[i], s[i + 1]
            split_here = False

            if cur.islower() and nxt.isupper():
                # Walk back collecting LOWERCASE only.
                left = i
                while left > 0 and s[left - 1].islower():
                    left -= 1
                run_len = i - left + 1
                # Strict rule: 4+ char lowercase run.
                if run_len >= 4:
                    split_here = True
                # Relaxed rule (iteration 10): 3-char run anchored by
                # whitespace/start AND right-side Capital followed by a
                # lowercase letter (not all-caps token like ``OS``).
                elif (
                    run_len >= 3
                    and (left == 0 or s[left - 1].isspace())
                    and i + 2 < n
                    and s[i + 2].islower()
                ):
                    split_here = True

            elif (
                cur.isalpha()
                and nxt.isdigit()
                and (
                    i + 2 >= n
                    or s[i + 2].isdigit()
                    or s[i + 2] in " .,"
                )
            ):
                # Walk back collecting ANY letter.
                left = i
                while left > 0 and s[left - 1].isalpha():
                    left -= 1
                word_len = i - left + 1
                if word_len >= 4:
                    split_here = True

            if split_here:
                out.append(_MERGE_SEPARATOR)
        i += 1
    return "".join(out)


_NUMERIC_CELL_RE = re.compile(
    r"^[-−–]?\d+(?:[.,]\d+)*(?:[%∗*]+)?(?:\s*\([^)]*\))?$"
)


def _is_header_like_row(row: list[str]) -> bool:
    """Heuristic: a row that looks like part of a header rather than data.

    Used to detect multi-row headers — common in academic tables where two
    or three rows of column labels stack above the data (e.g., a study-name
    row above a metric-name row above the data). Rules:

    - The row has at least one non-empty cell.
    - At most 30% of the non-empty cells look numeric (number + optional
      sign / decimals / asterisks / parenthetical CI). A genuine header row
      usually has zero numeric cells; the threshold tolerates one stray
      footnote ref or sample-size annotation.
    - The average length of non-empty cells is ≤ 30 chars. Header cells are
      short labels; data rows often carry long hypothesis statements.
    """
    nonempty = [c.strip() for c in row if (c or "").strip()]
    if not nonempty:
        return False
    numeric = sum(1 for c in nonempty if _NUMERIC_CELL_RE.match(c))
    if numeric / len(nonempty) > 0.3:
        return False
    avg_len = sum(len(c) for c in nonempty) / len(nonempty)
    if avg_len > 30:
        return False
    return True


def _is_group_separator(row: list[str], n_cols: int) -> bool:
    """A "group separator" row has content in only the first cell AND
    the table has ≥3 columns AND the label looks like a section header
    (≥3 chars, contains a letter — not a stat value or number).

    The 3-col threshold prevents tiny rows like ``[1, ""]`` in a 2-column
    table from being treated as group separators.
    """
    if not row or n_cols < 3:
        return False
    first = row[0].strip() if row[0] else ""
    rest = [c for c in row[1:] if (c or "").strip()]
    if rest:
        return False
    if len(first) < 3:
        return False
    # Must contain at least one letter (avoid pure numerics like "123")
    if not re.search(r"[A-Za-z]", first):
        return False
    return True


_SUFFIX_OPEN_PUNCT_RE = re.compile(r"[-—–:]\s*$")

_STRONG_RH_PATTERNS = [
    # Pure page number: "725", "1236"
    re.compile(r"^\d{1,4}$"),
    # Pipe-prefixed page header: "|232", "|232 Stacey et al."
    re.compile(r"^\s*\|\s*\d{1,4}\b"),
    # Page-number-with-vol: "Vol. 17", "Vol.:(0123456789)"
    re.compile(r"^Vol\.?[\s:]", re.IGNORECASE),
    # Journal-title-CAPS + page number: "COGNITION AND EMOTION 1231"
    re.compile(r"^[A-Z][A-Z\s&]{6,}\s+\d{2,5}$"),
    # Author "et al." cite: "Stacey et al.", "Smith et al"
    re.compile(r".*\bet\s+al\.?\s*$"),
    # DOI / URL header
    re.compile(r"^(?:doi|https?)\b", re.IGNORECASE),
]

_WEAK_RH_PATTERNS = [
    # Single short cap-cased word: "Nussio"
    re.compile(r"^[A-Z][A-Za-z'’]{1,15}$"),
    # "Smith and Jones"
    re.compile(r"^[A-Z][A-Za-z'’]{1,15}\s+and\s+[A-Z][A-Za-z'’]{1,15}$"),
    # Pure number repeated above
    re.compile(r"^\d{1,4}$"),
]


def _is_strong_running_header(s: str) -> bool:
    """Strong unambiguous running-header signal — a real column header
    almost never looks like this (pure page number, ``et al.``, journal
    CAPS line, ``Vol.``, DOI/URL)."""
    s = (s or "").strip()
    if not s or len(s) > 40:
        return False
    return any(p.match(s) for p in _STRONG_RH_PATTERNS)


def _is_weak_running_header(s: str) -> bool:
    """Weak signal — could plausibly be a real header word but matches
    common running-header layouts (single cap-cased word like ``Nussio``,
    or ``Smith and Jones``). Only counted as RH when it co-occurs with a
    STRONG signal in the same row."""
    s = (s or "").strip()
    if not s or len(s) > 40:
        return False
    return any(p.match(s) for p in _WEAK_RH_PATTERNS)


def _is_running_header_cell(s: str) -> bool:
    """Backwards-compat alias used in tests — strong OR weak signal."""
    return _is_strong_running_header(s) or _is_weak_running_header(s)


def _drop_running_header_rows(rows: list[list[str]]) -> list[list[str]]:
    """Drop top rows of the grid that look like leaked running headers /
    page numbers rather than real column labels.

    Iteration 15. Camelot occasionally captures the page running-header
    as the first row of an extracted table (e.g. social_forces_1 Table 1
    where row 0 is ``[ "|232Stacey et al." ]``, am_sociol_rev_3 Table 4
    where row 0 is ``[ "Nussio", "725" ]``). The real column headers are
    on row 1. Dropping the running-header row promotes the actual headers.

    A row qualifies for dropping when ALL of:
      - it has ≥1 populated cell;
      - at least one populated cell is a STRONG running-header signal
        (pure page number, ``et al.``, journal CAPS line, ``Vol.``,
        DOI/URL) — this anchor disambiguates from real header rows;
      - every populated cell is a strong-or-weak running-header signal.

    Iterates from the top until a non-qualifying row is reached. Stops if
    fewer than 2 rows would remain (preserve grid structure). An entirely
    blank top row is left alone (different artifact, not RH).
    """
    if not rows:
        return rows
    out = list(rows)
    while len(out) >= 2:
        top = out[0]
        populated = [c for c in top if (c or "").strip()]
        if not populated:
            break
        if not any(_is_strong_running_header(c) for c in populated):
            break
        if not all(
            _is_strong_running_header(c) or _is_weak_running_header(c)
            for c in populated
        ):
            break
        # Don't drop if every remaining row is also pure RH content —
        # that suggests we'd be killing a real (numeric-only) table
        # rather than stripping an RH artifact.
        has_real_below = any(
            (c or "").strip()
            and not _is_strong_running_header(c)
            and not _is_weak_running_header(c)
            for row in out[1:]
            for c in row
        )
        if not has_real_below:
            break
        out = out[1:]
    # Iteration 17 add-on: cell-level RH cleanup. After fully-RH row
    # removal, the (new) top row may STILL contain a strong-RH cell
    # mixed with real header content (e.g. chan_feldman T5:
    # ``["1236", "Target article", "Replication", "Reason for change"]``).
    # If at least one strong-RH cell coexists with a non-RH populated
    # cell in the same row, blank out the strong-RH cells. Conservative:
    # only blanks cells matching STRONG patterns (not weak), and only on
    # the very first row.
    if out:
        top = list(out[0])
        has_strong = any(_is_strong_running_header(c) for c in top)
        has_real = any(
            (c or "").strip()
            and not _is_strong_running_header(c)
            and not _is_weak_running_header(c)
            for c in top
        )
        if has_strong and has_real:
            for i, c in enumerate(top):
                if _is_strong_running_header(c):
                    top[i] = ""
            out = [top] + out[1:]
    return out





def _fold_suffix_continuation_columns(
    header_rows: list[list[str]],
) -> list[list[str]]:
    """Fold per-column suffix continuations in 2-row headers.

    Iteration 12 (handoff Tier A5). Camelot occasionally splits a single
    column label like ``Win-Uncertain`` across two header rows, with the
    suffix fragment in row 1 and the prefix (ending in ``-`` or ``:``)
    in row 0. Example from ziano Table 2:

        row 0: [..., "Win-:", "Loss-"]
        row 1: [...,  "Uncertain", "Uncertain"]

    Per-column rule: for each column where row1 is non-empty AND row0
    ends with ``-`` / ``—`` / ``–`` / ``:`` AND row1 starts with a
    letter, merge into row0 (no separator — the dash IS the separator)
    and clear row1's cell.

    If row1 is entirely empty after the per-column merges, drop it.

    Conservative: only fires on 2-row headers (so it doesn't interact
    weirdly with the iteration-9 super-header fold, which always runs
    first); preserves all other cells unchanged.
    """
    if len(header_rows) != 2:
        return header_rows
    sup = list(header_rows[0])
    sub = list(header_rows[1])
    n = max(len(sup), len(sub))
    sup += [""] * (n - len(sup))
    sub += [""] * (n - len(sub))
    new_sup = list(sup)
    new_sub = list(sub)
    merged_any = False
    for i in range(n):
        s = (sub[i] or "").strip()
        if not s or not s[0].isalpha():
            continue
        top = (sup[i] or "").rstrip()
        if not top or not _SUFFIX_OPEN_PUNCT_RE.search(top):
            continue
        new_sup[i] = top + s
        new_sub[i] = ""
        merged_any = True
    if not merged_any:
        return header_rows
    if all(not c.strip() for c in new_sub):
        return [new_sup]
    return [new_sup, new_sub]


def _fold_super_header_rows(header_rows: list[list[str]]) -> list[list[str]]:
    """Fold a super-header row into the row directly below it, column-wise.

    Camelot frequently splits a wrapped column header across two header
    rows, e.g. korbmacher Table 7:

        row 0: ["", "",          "",   "Mean",       "",        "Effect",  ""]
        row 1: ["Condition", "T-statistic", "df", "difference", "p-value", "size r", "95% CI"]

    The natural rendering is to fold ``Mean`` into ``Mean<br>difference`` (col 3)
    and ``Effect`` into ``Effect<br>size r`` (col 5), producing a single
    header row.

    Conservative rule (only fold when ALL of these hold):
      - There are ≥2 header rows.
      - The top row has at least one empty cell (genuine 2-row label
        headers usually have all-populated cells; super-headers have gaps).
      - Every populated cell in the top row has a populated cell directly
        below in the next row (no implicit colspan to merge across).

    When the rule passes, returns ``[folded] + header_rows[2:]`` where
    ``folded[i] = "super[i]<br>sub[i]"`` if super[i] is populated else
    ``sub[i]``. The fold is applied iteratively top-down — if 3 header
    rows fold pairwise they collapse to one row.

    The ``<br>`` between super and sub is inserted as the
    ``_MERGE_SEPARATOR`` placeholder so it survives ``_html_escape``.
    """
    if len(header_rows) < 2:
        return header_rows
    sup = list(header_rows[0])
    sub = list(header_rows[1])
    n = max(len(sup), len(sub))
    sup += [""] * (n - len(sup))
    sub += [""] * (n - len(sub))
    populated_sup_idx = [i for i, c in enumerate(sup) if (c or "").strip()]
    if not populated_sup_idx:
        # Empty super row — drop it.
        return [sub] + header_rows[2:]
    if len(populated_sup_idx) == n:
        # No empty cell in super row — likely a real 2-row header, don't fold.
        return header_rows
    # Every populated super cell must have a populated sub cell directly below.
    for i in populated_sup_idx:
        if not (sub[i] or "").strip():
            return header_rows
    # Safe to fold.
    folded: list[str] = []
    for i in range(n):
        if (sup[i] or "").strip():
            folded.append(f"{sup[i]}{_MERGE_SEPARATOR}{sub[i]}")
        else:
            folded.append(sub[i])
    rest = header_rows[2:]
    # Recurse: a 3-row super-super-sub may fold pairwise.
    return _fold_super_header_rows([folded] + rest)


def pdfplumber_table_to_markdown(rows: Sequence[Sequence[str | None]]) -> str:
    """Render a table (list of rows of cells) as an HTML ``<table>`` block
    suitable for embedding inside Markdown.

    Per the user's 2026-05-09 decision: HTML rendering is now the default
    for all tables (not just complex ones). The pipe-table syntax cannot
    represent merged cells, multi-line cells, group separators, or
    multi-row headers, all of which are common in academic tables.

    The function name is kept for API stability with the existing tests,
    but the output is now HTML.

    Smart features:
      - First row → ``<thead>`` with ``<th>`` cells.
      - Continuation rows (first cell empty, others have content) merge
        into the previous data row's cells with ``<br>`` separators.
      - Group separator rows (only first cell has content) emit as
        ``<tr><td colspan="N"><strong>group</strong></td></tr>``.
      - HTML special characters (``<``, ``>``, ``&``) are escaped.
      - Cells are stripped of surrounding whitespace.
      - Returns empty string for tables with fewer than 2 rows.
    """
    if len(rows) < 2:
        return ""

    # Normalize rows: convert None → "", strip cells, ensure list-of-lists.
    norm: list[list[str]] = []
    for row in rows:
        norm.append([(c or "").strip() if c is not None else "" for c in row])

    # Merge continuation rows.
    merged = _merge_continuation_rows(norm)
    if len(merged) < 2:
        return ""

    n_cols = max(len(r) for r in merged) if merged else 0
    if n_cols == 0:
        return ""

    # Pad short rows to n_cols.
    for r in merged:
        while len(r) < n_cols:
            r.append("")

    # Split apparent column-undercount mash inside individual cells. This
    # doesn't add columns to the row — it just inserts ``<br>`` between the
    # mashed parts so the cell is readable. The placeholder survives HTML
    # escaping and renders as ``<br>``.
    for row in merged:
        for ci in range(len(row)):
            row[ci] = _split_mashed_cell(row[ci])

    # Detect multi-row header: count consecutive header-like rows from the
    # top, capped at 3 (real-world tables don't stack more headers than
    # that without a structural marker). This rescues the second row of
    # tables like ip_feldman Table 1 where Camelot produces:
    #   row 0: ['', 'Estimation', 'Average estimation', '', ...]
    #   row 1: ['Experiences', 'errora', 'error (%)', 't-statistics', ...]
    # — both header rows. Without this, row 1 was rendering as `<td>` data.
    #
    # A group separator (only-col-0 row spanning the full width) must NOT
    # be promoted to header — it's an in-body section divider that gets
    # rendered as a single <td colspan="N"> below.
    n_header = 1
    for k in range(1, min(3, len(merged))):
        if _is_group_separator(merged[k], n_cols):
            break
        if _is_header_like_row(merged[k]):
            n_header = k + 1
        else:
            break
    # Sanity: don't promote multiple header rows if the body has fewer than 1
    # data row left (would leave the table with no <tbody> rows).
    if len(merged) - n_header < 1:
        n_header = 1

    header_rows = merged[:n_header]
    body = merged[n_header:]

    # Fold super-headers (e.g. korbmacher Table 7's ``["", "", "", "Mean",
    # "", "Effect", ""]`` row over ``["Condition", ..., "difference", ...,
    # "size r", "95% CI"]``) column-wise when the top row has empty cells
    # AND every populated top cell has a populated cell directly below.
    # See ``_fold_super_header_rows`` for the conservative rule.
    header_rows = _fold_super_header_rows(header_rows)
    # Per-column suffix-continuation fold for 2-row headers where individual
    # columns have ``Win-`` / ``Loss-`` over ``Uncertain`` / ``Uncertain``.
    header_rows = _fold_suffix_continuation_columns(header_rows)

    lines: list[str] = ["<table>"]
    lines.append("  <thead>")
    for hrow in header_rows:
        lines.append("    <tr>")
        for c in hrow:
            lines.append(f"      <th>{_html_escape(c)}</th>")
        lines.append("    </tr>")
    lines.append("  </thead>")
    lines.append("  <tbody>")
    for row in body:
        if _is_group_separator(row, n_cols):
            lines.append(
                f'    <tr><td colspan="{n_cols}"><strong>{_html_escape(row[0])}</strong></td></tr>'
            )
            continue
        lines.append("    <tr>")
        for c in row:
            lines.append(f"      <td>{_html_escape(c)}</td>")
        lines.append("    </tr>")
    lines.append("  </tbody>")
    lines.append("</table>")

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

    raw_lines = page_text.split("\n")
    if not raw_lines:
        return None

    # Search in NON-BLANK-line space. pdftotext often inserts a blank line
    # between every table row in column-rendered tables, doubling the line
    # count and starving the window cap. Counting only content lines lets the
    # algorithm operate on the table's actual row count without runaway.
    nb_lines: list[str] = []
    nb_to_raw: list[int] = []
    for i, ln in enumerate(raw_lines):
        if ln.strip():
            nb_lines.append(ln)
            nb_to_raw.append(i)
    if not nb_lines:
        return None

    per_line_hits = [len(_tokens(ln) & table_tokens) for ln in nb_lines]

    # Cap window length to ~2x the table's row count + slack. This prevents
    # runaway windows on real PDFs where the page also contains body prose
    # with overlapping tokens (e.g., "Table 3" referenced again later on the
    # page, or numeric tokens that happen to appear in surrounding text).
    max_window = max(8, len(table_rows) * 2 + 2)

    # Search every contiguous window. n is small (one page worth of lines).
    # Among windows meeting the coverage threshold, prefer maximum hit count
    # (tightly packed token matches), tiebreak on shorter length.
    best: Optional[tuple[int, int, int]] = None  # (-hits, length, start)
    for start in range(len(nb_lines)):
        running_token_set: set[str] = set()
        running_hits = 0
        for end in range(start, len(nb_lines)):
            length = end - start + 1
            if length > max_window:
                break
            running_hits += per_line_hits[end]
            running_token_set |= _tokens(nb_lines[end]) & table_tokens
            coverage = len(running_token_set) / len(table_tokens)
            if coverage < 0.6:
                continue
            candidate = (-running_hits, length, start)
            if best is None or candidate < best:
                best = candidate

    if best is None:
        return None
    _, length, nb_start = best
    nb_end = nb_start + length

    # Trim redundant edge lines: the picked window may extend past the actual
    # table into adjacent body prose whose tokens are *already* covered by
    # the table rows themselves (e.g., a paragraph that discusses
    # ``domains`` / ``ability`` after a table about domain difficulty).
    # Drop a trailing line ONLY if every table-token it carries is redundant
    # with the rest of the window. This preserves rows that hold unique
    # tokens (the actual table data) while shedding adjacent prose.
    line_token_sets: list[set[str]] = [
        _tokens(nb_lines[k]) & table_tokens for k in range(nb_start, nb_end)
    ]

    def _line_token_set(local_idx: int) -> set[str]:
        return line_token_sets[local_idx]

    core_start, core_end = nb_start, nb_end
    # Trim end while the trailing line's tokens are fully redundant.
    while core_end > core_start + 1:
        trailing = _line_token_set(core_end - 1 - nb_start)
        others: set[str] = set()
        for k in range(core_start - nb_start, core_end - 1 - nb_start):
            others |= line_token_sets[k]
        if trailing and not trailing.issubset(others):
            break
        if not trailing:
            # Empty token line at the edge — definitely safe to trim.
            core_end -= 1
            continue
        core_end -= 1
    # Trim start similarly.
    while core_start < core_end - 1:
        leading = _line_token_set(core_start - nb_start)
        others = set()
        for k in range(core_start + 1 - nb_start, core_end - nb_start):
            others |= line_token_sets[k]
        if leading and not leading.issubset(others):
            break
        if not leading:
            core_start += 1
            continue
        core_start += 1
    nb_start, nb_end = core_start, core_end

    raw_start = nb_to_raw[nb_start]
    raw_end = nb_to_raw[nb_end - 1] + 1  # exclusive
    return (raw_start, raw_end)


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
    """Pull a clean human-readable caption description from a Table.caption field.

    Strategy:
      - If the caption starts with the label, strip the label (and any
        trailing punctuation/whitespace).
      - Otherwise return the caption as-is.
      - Don't aggressively truncate at first "X." — that destroys legitimate
        captions like "Jordan et al. (2011) Studies 1b and 3: Summary" by
        cutting at "Jordan et al.".
      - Only truncate if the caption is very long (>300 chars), at the last
        sentence boundary before the cap.
    """
    if not caption:
        return ""
    # Collapse whitespace runs to single spaces; strip surrounding whitespace.
    text = re.sub(r"\s+", " ", caption).strip()
    if not text:
        return ""
    # Strip the label prefix if present (case-insensitive).
    if label:
        # Match optional label-with-period/colon at start.
        pattern = re.compile(
            r"^" + re.escape(label) + r"\s*[.:\-—–]?\s*",
            re.IGNORECASE,
        )
        m = pattern.match(text)
        if m:
            text = text[m.end():]
    # Strip any remaining leading orphan punctuation/whitespace.
    text = re.sub(r"^[\s.:\-—–]+", "", text)
    # Cap very long captions at the last sentence boundary before 300 chars.
    if len(text) > 300:
        snippet = text[:300]
        last_period = snippet.rfind(". ")
        if last_period > 100:
            text = snippet[: last_period + 1]
        else:
            text = snippet.rstrip() + "…"
    return text.strip()


_LABEL_ONLY_RE = re.compile(
    r"^(?:Table|Tab\.?|Figure|Fig\.?)\s+\d+(?:[.:]?)?\s*$",
    re.IGNORECASE,
)


def _drop_caption_leading_rows(
    grid: list[list[str]],
    label: str,
    caption: str,
) -> list[list[str]]:
    """Trim leading grid rows that are caption fragments rather than table data.

    Camelot's ``_drop_caption_first_row`` removes ONE row whose first cell
    matches the caption's first line, but real PDFs frequently render the
    caption across several lines (label + multi-line description) AND insert
    page-number rows above the table. The result is a Camelot grid whose
    first 1–4 rows are caption tail / label / page number — and rendering
    them as the table's header is visually broken.

    Drop rules (each conservative; only fires on near-certain caption noise):
      1. Row whose only-cell content is exactly ``Table N`` / ``Figure N``
         (the label by itself).
      2. Row with content ONLY in col 0, where col 0 is ≥ 5 chars and
         appears verbatim somewhere in the caption text (caption tail).
      3. Row with col 0 empty and col 1 = ``\\d{{1,3}}`` and all other cols
         empty (a page-number-only row Camelot picked up from the page).
      4. Row with EXACTLY ONE populated cell (in any column), where that
         cell is ≥ 5 chars and appears verbatim in the caption — covers the
         common Camelot quirk of placing the second line of a wrapped caption
         into a non-zero column when the first line was already absorbed.

    The function never deletes a row whose other columns hold real data
    (numerics, multi-cell content), so it cannot strip a legitimate header.
    """
    if not grid:
        return grid
    label_norm = label.strip().lower()
    cap_norm = re.sub(r"\s+", " ", caption or "").strip()

    while grid:
        first_row = grid[0]
        first_cell = (first_row[0] if first_row else "").strip()
        rest_nonempty = [c for c in first_row[1:] if (c or "").strip()]

        # Rule 1: row is just the label.
        if first_cell.lower() == label_norm and not rest_nonempty:
            grid = grid[1:]
            continue
        if _LABEL_ONLY_RE.match(first_cell) and not rest_nonempty:
            grid = grid[1:]
            continue

        # Rule 2: only col 0 has content AND col 0 looks like a caption-tail
        # line (≥5 chars, has a letter, appears in caption).
        if (
            first_cell
            and not rest_nonempty
            and len(first_cell) >= 5
            and re.search(r"[a-z]", first_cell, re.IGNORECASE)
            and cap_norm
            and first_cell in cap_norm
        ):
            grid = grid[1:]
            continue

        # Rule 3: col 0 empty, col 1 is a small page number, no other content.
        if not first_cell and len(first_row) >= 2:
            v1 = (first_row[1] or "").strip()
            other_after = [c for c in first_row[2:] if (c or "").strip()]
            if re.fullmatch(r"\d{1,3}", v1) and not other_after:
                grid = grid[1:]
                continue

        # Rule 4: caption-tail in any column. Exactly one populated cell that
        # appears verbatim in the caption text — Camelot sometimes drops the
        # second line of a wrapped caption into a middle column rather than
        # col 0 (e.g., korbmacher Table 7 puts "ratings between easy..." in
        # col 1 with all other cells empty).
        if cap_norm:
            populated = [
                (idx, (cell or "").strip())
                for idx, cell in enumerate(first_row)
                if (cell or "").strip()
            ]
            if (
                len(populated) == 1
                and len(populated[0][1]) >= 5
                and re.search(r"[a-z]", populated[0][1], re.IGNORECASE)
                and populated[0][1] in cap_norm
            ):
                grid = grid[1:]
                continue

        break

    return grid


_PROSE_CELL_NUMERIC_RE = re.compile(r"^[-−–]?\d+(?:[.,]\d+)*[%]?$")


def _is_spurious_body_prose_grid(grid: list[list[str]]) -> bool:
    """A grid that is ostensibly multi-column but whose cells are running
    body prose, not table data — Camelot misclassified a multi-column
    page layout (or interleaved body paragraphs) as a table.

    Iteration 16. Worst offender: ar_apa_j_jesp_2009_12_010 Table 1, an
    80+ row "table" where every cell is a slice of running text from the
    Methods section. Char ratio inflated to 1.453 by the duplication.

    A grid qualifies as "spurious body prose" when ALL of:
      - ≥ 4 populated rows;
      - ≥ 80% of populated cells are "prose-like" — ≥ 30 chars, ≥ 4
        words, contains ≥ 2 lowercase letters;
      - < 10% of populated cells are pure numeric (so we don't strip
        a real stat table whose cells happen to be slightly long);
      - average prose cell length ≥ 35 chars (real definition tables
        have shorter labels).

    Returns False for the iter-6 spurious-1col case (handled separately)
    and for any grid where row 0 looks like a real header (≥1 numeric or
    short-label cell pattern).
    """
    populated_rows = 0
    populated_cells = 0
    prose_cells = 0
    numeric_cells = 0
    prose_lengths: list[int] = []
    for row in grid:
        non_empty = [c.strip() for c in row if c and c.strip()]
        if not non_empty:
            continue
        populated_rows += 1
        for c in non_empty:
            populated_cells += 1
            if _PROSE_CELL_NUMERIC_RE.match(c):
                numeric_cells += 1
                continue
            n_lower = sum(1 for ch in c if ch.islower())
            n_words = len(c.split())
            if len(c) >= 30 and n_words >= 4 and n_lower >= 2:
                prose_cells += 1
                prose_lengths.append(len(c))
    if populated_rows < 4 or populated_cells == 0:
        return False
    if numeric_cells / populated_cells > 0.10:
        return False
    if prose_cells / populated_cells < 0.80:
        return False
    if not prose_lengths:
        return False
    if sum(prose_lengths) / len(prose_lengths) < 35:
        return False
    return True


def _is_spurious_single_column_grid(grid: list[list[str]]) -> bool:
    """A grid is "spurious 1-column" when every populated row has exactly one
    non-empty cell AND there are ≥ 4 such rows. Camelot/pdfplumber sometimes
    misclassify a stretch of body prose (page header + caption echo + body
    paragraphs) as a 1-column "table" — rendering them as ``<table>`` lies
    about the structure to the reader. Check the populated-cell count, not the
    grid width: a 5-column grid with all content stuffed into column 0 is
    just as spurious as a literal 1-column grid.
    """
    populated_rows = 0
    for row in grid:
        non_empty = sum(1 for cell in row if cell and cell.strip())
        if non_empty == 0:
            continue
        if non_empty >= 2:
            return False  # at least one row has multi-column content
        populated_rows += 1
    return populated_rows >= 4


def _render_grid_as_code_block(grid: list[list[str]]) -> str:
    """Emit a 1-column grid as a fenced code block, joining each row's
    non-empty cells with single spaces. Used as a fallback for grids whose
    "tabular" structure is spurious (see ``_is_spurious_single_column_grid``).
    """
    lines: list[str] = []
    for row in grid:
        text_cells = [cell.strip() for cell in row if cell and cell.strip()]
        if not text_cells:
            continue
        lines.append(" ".join(text_cells))
    if not lines:
        return ""
    return "```\n" + "\n".join(lines) + "\n```"


_SIDEBYSIDE_LABEL_RE = re.compile(r"^Table\s+\S+$", re.IGNORECASE)


def _detect_side_by_side_merge(
    grid: list[list[str]],
    label: str,
) -> int | None:
    """Detect when Camelot has stitched two adjacent independent tables into
    one grid — signaled by a header row whose cells are EACH a different
    ``Table N`` label (e.g., ``["Table 3", "Table 4"]``). When detected,
    return the column index of THIS table's label so the caller can extract
    just that column's content.

    Returns the column index, or None when the grid is a real merged-cell
    table (not a side-by-side stitch).

    Conservative: requires ALL non-empty cells in the first row to look like
    Table-N labels AND the labels to be DISTINCT. A real header that happens
    to contain "Table 1" / "Table 2" as repeated literal text won't fire
    because the labels would not all be distinct OR not all match the pattern.
    """
    if not grid or not grid[0]:
        return None
    first_row = [(c or "").strip() for c in grid[0]]
    nonempty = [c for c in first_row if c]
    if len(nonempty) < 2:
        return None
    if not all(_SIDEBYSIDE_LABEL_RE.match(c) for c in nonempty):
        return None
    if len(set(c.lower() for c in nonempty)) < 2:
        return None  # all labels identical — not a side-by-side stitch
    label_norm = (label or "").strip().lower()
    for col_idx, cell in enumerate(first_row):
        if cell.lower() == label_norm:
            return col_idx
    return None


def _extract_column_subgrid(
    grid: list[list[str]],
    col_idx: int,
) -> list[list[str]]:
    """Return a 1-column subgrid containing the cells of `col_idx` from the
    rows BELOW the header row at index 0. Used to extract a single sub-table
    from a side-by-side-merged grid (see ``_detect_side_by_side_merge``)."""
    sub: list[list[str]] = []
    for row in grid[1:]:
        if col_idx < len(row):
            cell = (row[col_idx] or "").strip()
        else:
            cell = ""
        sub.append([cell])
    return sub


def _format_table_md(table: dict, pdf_path: str | None = None) -> str:
    """Render a docpluck Table as a self-contained markdown block.

    Order of preference for cell content:
      1. ``cells`` populated by docpluck (lattice tables) → render directly.
      2. Camelot stream extraction (whitespace tables, the APA case) → render.
      3. Raw text in a fenced code block (last-resort fallback if Camelot fails).

    Before rendering, leading caption-fragment / label / page-number rows are
    stripped from the grid via ``_drop_caption_leading_rows``. If the resulting
    grid is a "spurious 1-column" run of prose (≥ 4 rows, no row has >1
    populated cell), render as a code block rather than ``<table>`` —
    pretending such content is tabular misleads the reader.
    """
    label = table.get("label") or "Table"
    caption = table.get("caption") or ""
    short_caption = _table_caption_short(caption, label)

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
        grid = _drop_caption_leading_rows(grid, label, caption)
        grid = _drop_running_header_rows(grid)
        if len(grid) >= 2:
            sbs_col = _detect_side_by_side_merge(grid, label)
            if sbs_col is not None:
                sub = _extract_column_subgrid(grid, sbs_col)
                code = _render_grid_as_code_block(sub)
                if code:
                    block_parts.append(code)
                return "\n".join(block_parts)
            if _is_spurious_single_column_grid(grid):
                code = _render_grid_as_code_block(grid)
                if code:
                    block_parts.append(code)
                return "\n".join(block_parts)
            if _is_spurious_body_prose_grid(grid):
                code = _render_grid_as_code_block(grid)
                if code:
                    block_parts.append(code)
                return "\n".join(block_parts)
            block_parts.append(pdfplumber_table_to_markdown(grid).rstrip("\n"))
            return "\n".join(block_parts)

    # 2. Camelot stream extraction
    if pdf_path:
        cam_rows = _camelot_cells_for_table(pdf_path, table)
        if cam_rows:
            cam_rows = _drop_caption_leading_rows(cam_rows, label, caption)
            cam_rows = _drop_running_header_rows(cam_rows)
            if len(cam_rows) >= 2:
                sbs_col = _detect_side_by_side_merge(cam_rows, label)
                if sbs_col is not None:
                    sub = _extract_column_subgrid(cam_rows, sbs_col)
                    code = _render_grid_as_code_block(sub)
                    if code:
                        block_parts.append(code)
                    return "\n".join(block_parts)
                if _is_spurious_single_column_grid(cam_rows):
                    code = _render_grid_as_code_block(cam_rows)
                    if code:
                        block_parts.append(code)
                    return "\n".join(block_parts)
                if _is_spurious_body_prose_grid(cam_rows):
                    code = _render_grid_as_code_block(cam_rows)
                    if code:
                        block_parts.append(code)
                    return "\n".join(block_parts)
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
    # Use find() (returns -1 on miss) rather than index() — the previous
    # `". " in caption[:300]` guard was wrong: it triggered for any "." in
    # 0-300 but the index() searched from 40, which raised ValueError when
    # the only "." sat in 0-39. Crash nuked the whole document for
    # jama_open_1 / jama_open_2.
    if len(caption) > 200:
        idx = caption.find(". ", 40, 300)
        if idx >= 0:
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


def _strip_orphan_caption_fragments_near_tables(text: str) -> str:
    """Strip ``Table N. caption ...`` fragments that appear immediately before
    a ``### Table N`` block.

    When the splice locator finds a tight region for a table inside a wider
    pdftotext-rendered table block, the parts of the original block OUTSIDE
    the located region remain as orphan paragraphs (caption line + a few
    fragmentary paragraphs). This pass removes any paragraph that contains a
    "Table N." caption line if the same N is the next ``### Table N`` heading.

    Only strips up to 8 lines preceding the heading and only if those lines
    look like fragments (≤80 chars each, not a section heading or pipe-row).
    """
    lines = text.split("\n")
    out_lines: list[str] = []
    i = 0
    n = len(lines)
    table_heading_re = re.compile(r"^### Table\s+(\d+)\s*$")
    caption_line_re = re.compile(r"^\s*Table\s+(\d+)\s*[.:]", re.IGNORECASE)

    while i < n:
        line = lines[i]
        m = table_heading_re.match(line)
        if not m:
            out_lines.append(line)
            i += 1
            continue
        # We are at a `### Table N` heading. Look back over the last ≤8 emitted
        # lines (skipping blank ones) for a caption-line that mentions the same N.
        target_num = int(m.group(1))
        # Walk back through out_lines collecting indices of fragmentary lines
        # until we find the caption line for the same number (or hit a non-fragment).
        lookback_indices: list[int] = []
        j = len(out_lines) - 1
        steps = 0
        found_caption_idx = -1
        while j >= 0 and steps < 12:
            cand = out_lines[j]
            steps += 1
            if cand.strip() == "":
                lookback_indices.append(j)
                j -= 1
                continue
            cm = caption_line_re.match(cand)
            if cm and int(cm.group(1)) == target_num:
                found_caption_idx = j
                lookback_indices.append(j)
                # Keep walking back for any short fragment lines also part of
                # this orphaned block (e.g., header tokens like "No\n\nHypothesis").
                j -= 1
                while j >= 0 and steps < 12:
                    cand2 = out_lines[j]
                    steps += 1
                    if cand2.strip() == "":
                        lookback_indices.append(j)
                        j -= 1
                        continue
                    if cand2.startswith(("#", "|", "```", "*")):
                        break
                    if len(cand2) > 80:
                        break
                    if re.search(r"[.!?]\)?\s*$", cand2) and len(cand2.split()) >= 6:
                        break
                    lookback_indices.append(j)
                    j -= 1
                break
            # Not a caption line — stop the lookback (don't strip arbitrary content).
            break
        if found_caption_idx >= 0:
            # Remove the orphan lines from out_lines.
            for idx in sorted(set(lookback_indices), reverse=True):
                out_lines.pop(idx)
        out_lines.append(line)
        i += 1
    return "\n".join(out_lines)


def _strip_redundant_caption_echo_before_tables(text: str) -> str:
    """Strip an orphan ``Table N: ...`` line that appears immediately before a
    ``### Table N`` block when its content is FULLY contained in the rendered
    table's caption + header cells directly below.

    Also strips short fragment lines (≤40 chars, ≤6 words, no terminal
    sentence punctuation) that lie BETWEEN the orphan caption and the
    heading IF every word in those fragments also appears in the rendered
    table. These fragments are header cells (``Study 1b``, ``Kruger
    (1999)``) that leaked out of the table region during splicing.

    Iteration 11 + extension. Replaces the older
    ``_strip_orphan_caption_fragments_near_tables`` (deliberately disabled
    because it risked content loss). This variant only strips when every
    word ≥3 chars is contained in the rendered table — so unique content
    is preserved. The user's hard rule (no disappearing text) is enforced
    by the strict subset check against the full rendered table text.
    """
    lines = text.split("\n")
    out_lines: list[str] = []
    n = len(lines)
    table_heading_re = re.compile(r"^### Table\s+(\d+)\s*$")
    caption_line_re = re.compile(r"^\s*Table\s+(\d+)\s*[.:]\s*(.+?)\s*$", re.IGNORECASE)
    italic_caption_re = re.compile(r"^\*(.+)\*\s*$")
    th_cell_re = re.compile(r"<th[^>]*>(.*?)</th>", re.DOTALL)
    sentence_end_re = re.compile(r"[.!?]\s*$")
    word_re = re.compile(r"[A-Za-z]{3,}")
    table_block_end_re = re.compile(r"^</table>\s*$")

    def _line_is_short_fragment(s: str) -> bool:
        s = s.strip()
        if not s or len(s) > 40:
            return False
        if len(s.split()) > 6:
            return False
        if sentence_end_re.search(s):
            return False
        return True

    def _stem(w: str) -> str:
        """4-char prefix stem so ``study`` matches ``studies``,
        ``error`` matches ``errors``, etc. Conservative — false-positive
        risk is acceptable because the strip is only triggered by an
        anchoring orphan caption that itself must already match."""
        return w[:4] if len(w) >= 4 else w

    def _stems(words: set[str]) -> set[str]:
        return {_stem(w) for w in words}

    i = 0
    while i < n:
        line = lines[i]
        m = table_heading_re.match(line)
        if not m:
            out_lines.append(line)
            i += 1
            continue
        target_num = int(m.group(1))

        # Collect the rendered table's word-set: italic caption + every
        # ``<th>`` cell text. Walk forward up to ~200 lines until ``</table>``.
        rendered_words: set[str] | None = None
        rendered_chunks: list[str] = []
        for k in range(i + 1, min(i + 200, n)):
            ln = lines[k]
            if rendered_words is None:
                stripped = ln.strip()
                if not stripped:
                    continue
                cap_m = italic_caption_re.match(stripped)
                if cap_m:
                    rendered_chunks.append(cap_m.group(1))
                    rendered_words = set()  # mark as found; will accumulate below
                else:
                    # No italic caption — bail.
                    break
            # After caption found, accumulate <th> cells.
            rendered_chunks.append(" ".join(th_cell_re.findall(ln)))
            if table_block_end_re.match(ln.strip()):
                break
        if rendered_words is None:
            out_lines.append(line)
            i += 1
            continue
        rendered_words = set(
            w.lower() for w in word_re.findall(" ".join(rendered_chunks))
        )
        rendered_stems = _stems(rendered_words)

        # Walk back through out_lines for an orphan ``Table N: ...`` plus
        # any short header-fragment lines between it and the heading. Only
        # strip when the entire collected block is a word-subset of the
        # rendered table.
        j = len(out_lines) - 1
        steps = 0
        candidate_indices: list[int] = []
        orphan_found = False
        while j >= 0 and steps < 12:
            cand = out_lines[j]
            steps += 1
            stripped = cand.strip()
            if stripped == "":
                candidate_indices.append(j)
                j -= 1
                continue
            cm = caption_line_re.match(cand)
            if cm and int(cm.group(1)) == target_num:
                orphan_words = set(
                    w.lower() for w in word_re.findall(cm.group(2))
                )
                if orphan_words and _stems(orphan_words).issubset(rendered_stems):
                    candidate_indices.append(j)
                    orphan_found = True
                # Stop walking back once the orphan caption is found
                # (or rejected — don't keep eating).
                break
            # Allow short header-fragment lines that are subsets of the
            # rendered table — they leaked out of the table region.
            # Match by 4-char prefix stem so ``Study 1b`` matches a
            # rendered ``Studies 1b and 3``.
            if _line_is_short_fragment(stripped):
                frag_words = set(w.lower() for w in word_re.findall(stripped))
                if frag_words and _stems(frag_words).issubset(rendered_stems):
                    candidate_indices.append(j)
                    j -= 1
                    continue
            # Anything else stops the walk-back (preserve content).
            break

        if orphan_found:
            for idx in sorted(set(candidate_indices), reverse=True):
                out_lines.pop(idx)

        out_lines.append(line)
        i += 1

    return "\n".join(out_lines)


def _strip_redundant_fragments_after_tables(text: str) -> str:
    """Strip leaked-cell fragment lines that appear immediately AFTER a
    ``</table>`` block when every word stem in those lines is already
    present in the table's caption + cells.

    Iteration 13. Symmetric to ``_strip_redundant_caption_echo_before_tables``
    but for the post-table side. Camelot occasionally drops row/column
    axis labels that pdftotext then renders as orphan paragraphs right
    after the rendered table block. Example from efendic Table 1:

        </table>

        Negative affect Positive affect Positive affect Negative affect

        Impact on non-manipulated attribute
        Benefit is low Benefit is high Risk is low Risk is high

    The first / fourth lines are subsets of the rendered table content
    (every word maps to a header/cell stem). The 3rd line ``Impact on
    non-manipulated attribute`` contains ``impact`` which is NOT in
    the rendered table and so is preserved (no content loss).

    Only fires when the line:
      - ≤80 chars
      - ≤12 words
      - has no terminal sentence punctuation (``.``/``!``/``?``)
      - every 4-char stem of every ≥3-char word is in the rendered table

    Walks forward up to ~6 non-blank lines after ``</table>`` and stops
    on the first non-subset content. Blank lines between candidate
    fragment lines are allowed and collapsed.

    Iteration 18 extension: also strips a full ``Table N. ...`` caption
    echo line that follows ``</table>`` (regardless of length / terminal
    period) when its table-number matches the preceding ``### Table N``
    heading AND every word stem after the ``Table N.`` prefix is already
    present in the rendered table's caption + cells. Catches sci_rep_1
    Table 1 where the full italic caption is restated as plain text after
    ``</table>``.
    """
    lines = text.split("\n")
    n = len(lines)
    table_end_re = re.compile(r"^</table>\s*$")
    table_start_re = re.compile(r"^\s*<table[^>]*>\s*$")
    italic_caption_re = re.compile(r"^\*(.+)\*\s*$")
    table_heading_re = re.compile(r"^###\s+Table\s+(\d+)\s*$", re.IGNORECASE)
    caption_echo_re = re.compile(
        r"^\s*Table\s+(\d+)\s*[.:]\s*(.+?)\s*$", re.IGNORECASE
    )
    th_cell_re = re.compile(r"<th[^>]*>(.*?)</th>", re.DOTALL)
    td_cell_re = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
    sentence_end_re = re.compile(r"[.!?]\s*$")
    word_re = re.compile(r"[A-Za-z]{3,}")

    def _stem(w: str) -> str:
        return w[:4] if len(w) >= 4 else w

    def _line_is_post_table_fragment(s: str) -> bool:
        s = s.strip()
        if not s or len(s) > 80:
            return False
        if len(s.split()) > 12:
            return False
        if sentence_end_re.search(s):
            return False
        return True

    drop_indices: set[int] = set()

    for i in range(n):
        if not table_end_re.match(lines[i].strip()):
            continue
        # Walk back to find the matching <table> opener and collect cells.
        cells_text: list[str] = []
        caption_text = ""
        table_num: int | None = None
        j = i - 1
        steps = 0
        while j >= 0 and steps < 400:
            steps += 1
            ln = lines[j]
            cells_text.append(" ".join(th_cell_re.findall(ln)))
            cells_text.append(" ".join(td_cell_re.findall(ln)))
            if table_start_re.match(ln.strip()):
                # Walk above the <table> opener through blank lines /
                # italic caption / ``### Table N`` heading to capture
                # both the caption text and the heading number.
                k = j - 1
                k_steps = 0
                while k >= 0 and k_steps < 8:
                    k_steps += 1
                    s = lines[k].strip()
                    if not s:
                        k -= 1
                        continue
                    cap_m = italic_caption_re.match(s)
                    if cap_m:
                        caption_text = cap_m.group(1)
                        k -= 1
                        continue
                    h_m = table_heading_re.match(s)
                    if h_m:
                        table_num = int(h_m.group(1))
                        break
                    break
                break
            j -= 1
        if not cells_text and not caption_text:
            continue
        rendered_words = set(
            w.lower() for w in word_re.findall(" ".join(cells_text) + " " + caption_text)
        )
        if not rendered_words:
            continue
        rendered_stems = {_stem(w) for w in rendered_words}

        # Walk forward from i+1 collecting leaked-fragment candidates.
        cand: list[int] = []
        forward_steps = 0
        nonblank_steps = 0
        k = i + 1
        while k < n and forward_steps < 12 and nonblank_steps < 6:
            forward_steps += 1
            stripped = lines[k].strip()
            if not stripped:
                cand.append(k)
                k += 1
                continue
            nonblank_steps += 1
            # Caption-echo branch: a line beginning ``Table N. ...`` /
            # ``Table N: ...`` that matches THIS table's heading number
            # AND whose payload words are a subset of the rendered
            # caption + cells. Allowed to be long / end in a period.
            ce_m = caption_echo_re.match(stripped)
            if (
                ce_m
                and table_num is not None
                and int(ce_m.group(1)) == table_num
            ):
                payload_words = set(
                    w.lower() for w in word_re.findall(ce_m.group(2))
                )
                if payload_words:
                    payload_stems = {_stem(w) for w in payload_words}
                    if payload_stems.issubset(rendered_stems):
                        cand.append(k)
                        k += 1
                        continue
            if not _line_is_post_table_fragment(stripped):
                break
            frag_words = set(w.lower() for w in word_re.findall(stripped))
            if not frag_words:
                break
            frag_stems = {_stem(w) for w in frag_words}
            if not frag_stems.issubset(rendered_stems):
                break
            cand.append(k)
            k += 1

        # Trim trailing blank-only candidates so we don't collapse a real
        # blank between tables.
        while cand and lines[cand[-1]].strip() == "":
            cand.pop()
        if cand:
            drop_indices.update(cand)

    if not drop_indices:
        return text
    out_lines = [ln for idx, ln in enumerate(lines) if idx not in drop_indices]
    return "\n".join(out_lines)


def _dedupe_h2_sections(text: str) -> str:
    """Demote duplicate H2 section headings to plain text.

    docpluck's section detector occasionally misclassifies a figure caption
    that starts with a section name ("Results of direct replication..."),
    creating multiple ``## Results`` headings. We keep the first occurrence
    of each heading text and demote the rest by stripping the ``## ``
    prefix. The body text under the demoted heading stays.

    The two structural appendix headings (``## Figures``, ``## Tables
    (unlocated in body)``) are exempt — they're intentional and emitted
    by the appendix builder.
    """
    EXEMPT = {"Figures", "Tables (unlocated in body)"}
    seen: set[str] = set()
    lines = text.split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^(##)(?!#)\s+(.+?)\s*$", line)
        if not m:
            continue
        heading_text = m.group(2).strip()
        if heading_text in EXEMPT:
            continue
        if heading_text in seen:
            # Demote: drop the heading line entirely so the body text below
            # flows into the previous section.
            lines[i] = ""
            continue
        seen.add(heading_text)
    return "\n".join(lines)


def _table_block_content_end(text: str, content_start: int, hard_end: int) -> int:
    """Find the end of a `### Table N` block's actual content within
    [content_start, hard_end].

    A table block's content consists of paragraphs that are one of:
      - blank
      - italic caption ``*…*``
      - code fence ``\\`\\`\\``` and the lines until the matching close
      - pipe-table rows ``| … |`` and ``| --- | --- |``
      - HTML ``<table>…</table>`` block (may span paragraphs because the
        renderer breaks the table across multiple ``\\n``-separated lines
        but typically with no blank-line gaps inside it; even so, defend
        against a stray ``\\n\\n`` inside the block).
    The block ends at the first paragraph that doesn't match any of these.
    """
    section = text[content_start:hard_end]
    paragraphs = re.split(r"(\n\s*\n)", section)
    # paragraphs alternates: [text, sep, text, sep, ..., text]
    in_html_table = False
    consumed = 0
    for chunk in paragraphs:
        if chunk == "" or re.fullmatch(r"\n\s*\n", chunk):
            consumed += len(chunk)
            continue
        if in_html_table:
            consumed += len(chunk)
            if "</table>" in chunk:
                in_html_table = False
            continue
        first_line = chunk.lstrip("\n").splitlines()[0] if chunk.strip() else ""
        is_caption = first_line.startswith("*") and first_line.endswith("*")
        is_fence_open = first_line.startswith("```")
        is_pipe_row = first_line.startswith("|")
        is_html_table_open = first_line.lstrip().startswith("<table")
        # Heuristic: pipe-table BLOCK if MOST lines start with `|`
        chunk_lines = chunk.strip().splitlines()
        pipe_lines = sum(1 for ln in chunk_lines if ln.lstrip().startswith("|"))
        fence_lines = sum(1 for ln in chunk_lines if ln.strip() == "```")
        is_pipe_block = chunk_lines and pipe_lines / max(len(chunk_lines), 1) >= 0.5
        is_fence_block = fence_lines >= 1
        if is_html_table_open:
            consumed += len(chunk)
            if "</table>" not in chunk:
                in_html_table = True
            continue
        if is_caption or is_pipe_row or is_pipe_block or is_fence_open or is_fence_block:
            consumed += len(chunk)
            continue
        # Not a table-content paragraph → stop here
        break
    return content_start + consumed


def _existing_table_numbers(text: str) -> set[int]:
    """Collect the set of table numbers already present as ``### Table N`` headings."""
    nums: set[int] = set()
    for m in re.finditer(r"^### Table\s+(\d+)", text, re.MULTILINE):
        nums.add(int(m.group(1)))
    return nums


def _dedupe_table_blocks(text: str) -> str:
    """Among multiple ``### Table N`` blocks with the same N, keep the
    highest-quality block. Quality ranking (best first):

      1. Block contains an HTML ``<table>`` element (Camelot-rendered cells).
      2. Block has more ``<tr>`` rows (more table content captured).
      3. Tiebreak: earliest position in the document (likely the body, not
         the appendix).

    A "block" runs from a ``### Table N`` heading to the next ``### `` /
    ``## `` heading or end of text. The previous metric (``pipe_rows`` from
    pipe-table lines) is now always 0 since rendering switched to HTML on
    2026-05-09 — a code-block fragment fallback would beat the real HTML
    table on the tiebreak. Ranking by ``<table>`` presence corrects this.
    """
    blocks: list[tuple[int, int, int, int, int]] = []  # (start, end, num, has_html, n_tr)
    matches = list(re.finditer(r"^### Table\s+(\d+)\s*$", text, re.MULTILINE))
    for i, m in enumerate(matches):
        start = m.start()
        # Default end = next ### heading or end-of-text.
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # Skip the current heading line so search ^ anchors don't false-match.
        heading_line_end = text.find("\n", m.start())
        if heading_line_end == -1:
            heading_line_end = m.end()
        else:
            heading_line_end += 1
        # Don't span across an H2 boundary (like "## Tables (unlocated in body)").
        # ^##(?!#)\s ensures we match a real H2, not the `### Table N+1` heading.
        h2 = re.search(r"^##(?!#)\s", text[heading_line_end:end], re.MULTILINE)
        if h2:
            end = heading_line_end + h2.start()
        # Trim block to only the table's own content (heading + caption + table).
        # Stop at the first paragraph that's NOT pipe-row, NOT code-fence, NOT
        # blank, NOT italic-caption — that's body text starting after the table.
        end = _table_block_content_end(text, heading_line_end, end)
        block_text = text[start:end]
        has_html = 1 if "<table>" in block_text else 0
        n_tr = len(re.findall(r"<tr\b", block_text))
        num = int(m.group(1))
        blocks.append((start, end, num, has_html, n_tr))

    # Group by number; pick the highest-quality block; mark others for removal.
    by_num: dict[int, list[tuple[int, int, int, int, int]]] = {}
    for b in blocks:
        by_num.setdefault(b[2], []).append(b)
    to_remove: list[tuple[int, int]] = []
    for num, group in by_num.items():
        if len(group) <= 1:
            continue
        # Sort: prefer has_html=1, then more <tr>, then earliest start.
        group.sort(key=lambda b: (-b[3], -b[4], b[0]))
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
            elif caption_label is None:
                # No caption matched, so the run is being dropped. But the
                # "Unlabeled fragment-wraps are noise" assumption fails when
                # the run contains footnote-marker paragraphs ("Note.", "*M=…",
                # "†p<.05") that won't be re-emitted by anything else — this
                # is real content loss against the source PDF. Rescue those
                # paragraphs and emit them as plain text. Numeric / single-word
                # noise still drops (preserves the dedup-vs-Camelot behavior).
                # Skip marker-only paragraphs (single ``†`` / ``*`` chars):
                # those carry no content and only add visual noise.
                fragment_blob = "\n\n".join(
                    paragraphs[j] for j in range(run_start, i)
                )
                for note in _extract_footnote_lines(fragment_blob):
                    if len(note.strip()) < 8:
                        continue
                    out_parts.append(note)
        else:
            for j in range(run_start, i):
                out_parts.append(paragraphs[j])
        if i < n:
            out_parts.append(paragraphs[i])
            i += 1

    return "\n\n".join(p for p in out_parts if p)


_FOOTNOTE_MARKER_RE = re.compile(
    r"^\s*(?:"
    r"[*†‡§¶]+"            # asterisk / dagger / section / pilcrow markers
    r"|Note[s]?\s*[.:]"    # "Note." or "Notes:"
    r"|\*[A-Za-z]"         # *M, *p, *N — common stat-table conventions
    r"|†[A-Za-z]"
    r")",
    re.IGNORECASE,
)
_FOOTNOTE_INLINE_NOTE_RE = re.compile(r"^\s*Note\s*[.:]\s", re.IGNORECASE)


def _extract_footnote_lines(region_text: str) -> list[str]:
    """Pick out paragraphs that look like table footnotes from the spliced
    region. Camelot's ``_trim_prose_tail`` and ``_drop_caption_first_row``
    deliberately remove prose-y rows from the structured cells, so explanation
    lines like ``*M = 1.13... attentiveness`` end up nowhere unless preserved
    here. We collect any paragraph in the region whose first non-blank line
    starts with a footnote marker (``*``, ``†``, ``‡``, ``§``, ``¶``,
    ``Note.``, etc.) and keep it for emission after the rendered table.

    Returns the collected paragraphs as plain text (whitespace collapsed).
    """
    out: list[str] = []
    seen: set[str] = set()
    for paragraph in re.split(r"\n\s*\n", region_text):
        first_line = paragraph.lstrip("\n").splitlines()[0] if paragraph.strip() else ""
        if not first_line:
            continue
        if not (
            _FOOTNOTE_MARKER_RE.match(first_line)
            or _FOOTNOTE_INLINE_NOTE_RE.match(first_line)
        ):
            continue
        # Collapse internal whitespace; strip surrounding ws.
        cleaned = re.sub(r"\s+", " ", paragraph).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


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
    # Pre-compute section start positions so we can shrink any table region
    # that bleeds across a section boundary — section headings must always win
    # over a table region that extended too far.
    section_starts = sorted(
        s.char_start for s in sections
        if not (s.canonical_label.name == "unknown" and s.char_start == 0)
    )

    def _shrink_to_avoid_section(start: int, end: int) -> tuple[int, int]:
        """If any section heading start lies strictly inside (start, end),
        truncate end to that section start (leave a small gap so the heading
        falls outside the table region)."""
        for sec_start in section_starts:
            if start < sec_start < end:
                return (start, sec_start)
        return (start, end)

    unlocated: list[dict] = []

    # First pass: locate each table (region or None).
    located: list[tuple[int, int, dict]] = []
    for t in tables:
        region = _locate_table_per_page(cleaned, page_starts, t)
        if region is None:
            unlocated.append(t)
            continue
        char_start, char_end = region
        char_start, char_end = _shrink_to_avoid_section(char_start, char_end)
        if char_start >= char_end:
            unlocated.append(t)
            continue
        located.append((char_start, char_end, t))

    # Resolve overlaps: when two tables on the same page both locate to
    # overlapping char regions, trim the earlier-starting one's end to begin
    # of the next. Without this, applying both edits in reverse char order
    # corrupts the spliced output. Defer collapsed regions to the appendix.
    located.sort(key=lambda x: (x[0], x[1]))
    for i in range(len(located) - 1):
        s, e, t = located[i]
        next_s = located[i + 1][0]
        if e > next_s:
            located[i] = (s, next_s, t)
    cleaned_located: list[tuple[int, int, dict]] = []
    for s, e, t in located:
        if s >= e - 10:  # too collapsed to be useful
            unlocated.append(t)
            continue
        cleaned_located.append((s, e, t))

    for char_start, char_end, t in cleaned_located:
        # Preserve footnote-like lines from the original spliced region. The
        # structured Camelot extraction often drops them via `_trim_prose_tail`,
        # leaving asterisk / dagger explanations like
        # ``*M = 1.13... attentiveness`` to be silently consumed when the
        # region is replaced by HTML. Re-emit them as a plain markdown
        # paragraph after the table.
        region_text = cleaned[char_start:char_end]
        footnote_lines = _extract_footnote_lines(region_text)
        table_md = _format_table_md(t, pdf_path=pdf_path)
        if footnote_lines:
            table_md = (
                table_md
                + "\n\n"
                + "\n\n".join(footnote_lines)
            )
        replacement = "\n\n" + table_md + "\n\n"
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
    # Iteration 11: strip ``Table N: ...`` orphan caption echoes when they
    # are word-set subsets of the rendered caption directly below. Narrower
    # than the older blanket strip — preserves any unique content.
    out = _strip_redundant_caption_echo_before_tables(out)
    # Iteration 13: strip leaked fragment lines that appear AFTER the
    # ``</table>`` close, when every word stem is already in the table's
    # caption + cells (symmetric to the iter-11 pre-table strip).
    out = _strip_redundant_fragments_after_tables(out)
    # Demote duplicate ## H2 section headings (figure captions starting with
    # "Results of..." that the section detector misclassified, etc.).
    out = _dedupe_h2_sections(out)
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
