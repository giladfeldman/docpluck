"""Cell-cleaning pipeline for academic-table cell grids.

Ported from the 2026-05 splice spike (docs/superpowers/plans/spot-checks/
splice-spike/splice_spike.py) into the library as part of v2.3.0
(TABLE_EXTRACTION_VERSION 2.1.0).

Input: 2-D list of cell strings as Camelot stream-flavor returns them.
Output: a clean <table>...</table> HTML string suitable for embedding in
Markdown.

The pipeline (orchestrated in :func:`cells_grid_to_html`):

1. ``_merge_continuation_rows`` — fold multi-line cell wraps into the
   parent row using a ``<br>`` placeholder.
2. ``_strip_leader_dots`` — strip ``. . . . . .`` alignment dots.
3. ``_split_mashed_cell`` — insert ``<br>`` at column-undercount boundaries
   inside a cell (e.g. ``groupEasy`` → ``group<br>Easy``).
4. ``_drop_running_header_rows`` — drop or blank running-header rows that
   Camelot pulled into the table.
5. Multi-row header detection via ``_is_header_like_row`` (capped at 3 rows).
6. ``_fold_super_header_rows`` — fold 2-row super-header into a single row.
7. ``_fold_suffix_continuation_columns`` — fold per-column suffix
   continuations (``Win-`` over ``Uncertain``).
8. ``_merge_significance_marker_rows`` — attach ``*``/``∗``/``†``/etc. rows
   as ``<sup>`` markers on the preceding (or following, for reference-
   category cases) numeric row.
9. ``_is_group_separator`` — render rows where only column 0 has content
   as ``<tr><td colspan="N"><strong>...</strong></td></tr>``.

Returns ``""`` for tables with fewer than 2 rows after cleaning, per the
v2.3.0 spec (`docs/HANDOFF_2026-05-11_visual_review_findings.md`).
"""

from __future__ import annotations

import re
from typing import Sequence


_MERGE_SEPARATOR = "\x00BR\x00"  # placeholder swapped to <br> after escaping
_SUP_OPEN = "\x00SUP\x00"  # placeholder swapped to <sup> after escaping
_SUP_CLOSE = "\x00/SUP\x00"  # placeholder swapped to </sup> after escaping


def _html_escape(s: str | None) -> str:
    """Escape HTML special characters for safe inclusion in cell content,
    then convert merge-separator placeholders to ``<br>`` and superscript
    placeholders to ``<sup>``/``</sup>``."""
    if s is None:
        return ""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace(_MERGE_SEPARATOR, "<br>")
        .replace(_SUP_OPEN, "<sup>")
        .replace(_SUP_CLOSE, "</sup>")
    )


# ---------------------------------------------------------------------------
# 1. _merge_continuation_rows
# ---------------------------------------------------------------------------


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
        for c in cells:
            s = (c or "").strip()
            if not s:
                continue
            if len(s.split()) >= 2 or len(s) >= 10:
                return True
        return False

    def _prev_col0_is_wrap(parent: list[str]) -> bool:
        if not parent or not parent[0]:
            return False
        s = parent[0].rstrip()
        if not s:
            return False
        return s.endswith(("/", "-", "—", "–"))

    def _is_label_modifier(s: str) -> bool:
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
        s = (s or "").strip()
        if not s:
            return False
        if _SENTENCE_END.search(s):
            return False
        if re.fullmatch(r"[\d.,%*∗+\-−–—]+", s):
            return False
        if _WRAP_PUNCT_END.search(s):
            return True
        if _CONJUNCTION_END.search(s):
            return True
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

        if (
            out
            and first
            and not rest_has_content
            and _prev_col0_is_wrap(out[-1])
        ):
            parent = out[-1]
            parent[0] = (
                parent[0].rstrip() + first
                if parent[0].rstrip().endswith(("/", "-"))
                else parent[0].rstrip() + " " + first
            )
            continue

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


# ---------------------------------------------------------------------------
# 2. _strip_leader_dots
# ---------------------------------------------------------------------------


_LEADER_DOTS = re.compile(r"(?:\.\s+){4,}\.?")


def _strip_leader_dots(s: str) -> str:
    """Strip long runs of leader-dots (``. . . . . . .``) from cell content."""
    if not s:
        return s
    out = _LEADER_DOTS.sub("", s)
    while _MERGE_SEPARATOR + _MERGE_SEPARATOR in out:
        out = out.replace(_MERGE_SEPARATOR + _MERGE_SEPARATOR, _MERGE_SEPARATOR)
    out = out.strip()
    if out.startswith(_MERGE_SEPARATOR):
        out = out[len(_MERGE_SEPARATOR):]
    if out.endswith(_MERGE_SEPARATOR):
        out = out[: -len(_MERGE_SEPARATOR)]
    return out.strip()


# ---------------------------------------------------------------------------
# 3. _split_mashed_cell
# ---------------------------------------------------------------------------


def _split_mashed_cell(s: str) -> str:
    """Insert ``<br>`` at apparent column-undercount boundaries inside a cell."""
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
                left = i
                while left > 0 and s[left - 1].islower():
                    left -= 1
                run_len = i - left + 1
                if run_len >= 4:
                    split_here = True
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


# ---------------------------------------------------------------------------
# 4. _is_header_like_row + _drop_running_header_rows + _is_group_separator
# ---------------------------------------------------------------------------


_NUMERIC_CELL_RE = re.compile(
    r"^[-−–]?\d+(?:[.,]\d+)*(?:[%∗*]+)?(?:\s*\([^)]*\))?$"
)


def _is_header_like_row(row: list[str]) -> bool:
    """Heuristic: a row that looks like part of a header rather than data."""
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
    (≥3 chars, contains a letter)."""
    if not row or n_cols < 3:
        return False
    first = row[0].strip() if row[0] else ""
    rest = [c for c in row[1:] if (c or "").strip()]
    if rest:
        return False
    if len(first) < 3:
        return False
    if not re.search(r"[A-Za-z]", first):
        return False
    return True


_STRONG_RH_PATTERNS = [
    re.compile(r"^\d{1,4}$"),
    re.compile(r"^\s*\|\s*\d{1,4}\b"),
    re.compile(r"^Vol\.?[\s:]", re.IGNORECASE),
    re.compile(r"^[A-Z][A-Z\s&]{6,}\s+\d{2,5}$"),
    re.compile(r".*\bet\s+al\.?\s*$"),
    re.compile(r"^(?:doi|https?)\b", re.IGNORECASE),
]

_WEAK_RH_PATTERNS = [
    re.compile(r"^[A-Z][A-Za-z'’]{1,15}$"),
    re.compile(r"^[A-Z][A-Za-z'’]{1,15}\s+and\s+[A-Z][A-Za-z'’]{1,15}$"),
    re.compile(r"^\d{1,4}$"),
]


def _is_strong_running_header(s: str) -> bool:
    s = (s or "").strip()
    if not s or len(s) > 40:
        return False
    return any(p.match(s) for p in _STRONG_RH_PATTERNS)


def _is_weak_running_header(s: str) -> bool:
    s = (s or "").strip()
    if not s or len(s) > 40:
        return False
    return any(p.match(s) for p in _WEAK_RH_PATTERNS)


def _is_running_header_cell(s: str) -> bool:
    """Backwards-compat alias used in tests — strong OR weak signal."""
    return _is_strong_running_header(s) or _is_weak_running_header(s)


def _drop_running_header_rows(rows: list[list[str]]) -> list[list[str]]:
    """Drop top rows of the grid that look like leaked running headers /
    page numbers rather than real column labels."""
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


# ---------------------------------------------------------------------------
# 5. _fold_super_header_rows
# ---------------------------------------------------------------------------


_SUFFIX_OPEN_PUNCT_RE = re.compile(r"[-—–:]\s*$")


def _fold_super_header_rows(header_rows: list[list[str]]) -> list[list[str]]:
    """Fold a super-header row into the row directly below it, column-wise."""
    if len(header_rows) < 2:
        return header_rows
    sup = list(header_rows[0])
    sub = list(header_rows[1])
    # v2.4.21 (cycle 6): body-prose leak rejection. Real super-headers
    # are typically short single-word or two-word labels. Body prose
    # that pdftotext-extracted-table-region-detection incorrectly
    # absorbed appears as a 60+-char run with sentence-y commas /
    # unmatched parens. Example caught in xiao_2021_crsp Table 5:
    #   sup row[0] = "the regret salience manipulation check item
    #     revealed a main effect of condition, FWelch(2,"
    # which got folded into the real Options header, producing
    # ``<th>the regret salience…, FWelch(2,<br>Options</th>``.
    # If ANY super-row cell exceeds 80 chars AND contains a comma-
    # then-lowercase or an unmatched open paren, DROP the super-row
    # rather than fold it. Real super-headers never look this way.
    if any(
        len((cell or "").strip()) > 80
        and (
            re.search(r",\s*[a-z]", cell or "")
            or ("(" in (cell or "") and (cell or "").count("(") > (cell or "").count(")"))
        )
        for cell in sup
    ):
        return [sub] + header_rows[2:]
    n = max(len(sup), len(sub))
    sup += [""] * (n - len(sup))
    sub += [""] * (n - len(sub))
    populated_sup_idx = [i for i, c in enumerate(sup) if (c or "").strip()]
    if not populated_sup_idx:
        return [sub] + header_rows[2:]
    if len(populated_sup_idx) == n:
        return header_rows
    for i in populated_sup_idx:
        if not (sub[i] or "").strip():
            return header_rows
    folded: list[str] = []
    for i in range(n):
        if (sup[i] or "").strip():
            folded.append(f"{sup[i]}{_MERGE_SEPARATOR}{sub[i]}")
        else:
            folded.append(sub[i])
    rest = header_rows[2:]
    return _fold_super_header_rows([folded] + rest)


# ---------------------------------------------------------------------------
# 6. _fold_suffix_continuation_columns
# ---------------------------------------------------------------------------


def _fold_suffix_continuation_columns(
    header_rows: list[list[str]],
) -> list[list[str]]:
    """Fold per-column suffix continuations in 2-row headers
    (``Win-`` over ``Uncertain`` → ``Win-Uncertain``)."""
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


# ---------------------------------------------------------------------------
# 7. _merge_significance_marker_rows
# ---------------------------------------------------------------------------


_SIG_MARKER_CHARS = re.compile(r"^[*∗†‡§+#]+$")


def _merge_significance_marker_rows(rows: list[list[str]]) -> list[list[str]]:
    """Merge rows whose only populated cells are significance markers
    (``*``, ``∗∗∗``, ``†``, etc.) into the nearest substantive estimate row
    as ``<sup>...</sup>``."""
    def _row_marker_only(row: list[str]) -> bool:
        populated = [(c or "").strip() for c in row]
        populated = [s for s in populated if s]
        if not populated:
            return False
        return all(_SIG_MARKER_CHARS.match(s) for s in populated)

    _NUMERIC_CELL = re.compile(r"^[+\-−–—]?\d+(?:\.\d+)?[%]?$")

    def _row_has_numeric_estimate(row: list[str]) -> bool:
        for c in row:
            s = (c or "").strip()
            if not s:
                continue
            if _NUMERIC_CELL.match(s):
                return True
        return False

    def _row_is_text_anchor(row: list[str]) -> bool:
        if _row_has_numeric_estimate(row):
            return False
        populated = [(c or "").strip() for c in row if (c or "").strip()]
        if not populated:
            return False
        for s in populated:
            if s.startswith(("(", "[")) and s.endswith((")", "]")):
                continue
            if _SIG_MARKER_CHARS.match(s):
                continue
            return True
        return False

    out: list[list[str]] = []
    input_rows = list(rows)
    i = 0
    while i < len(input_rows):
        row = input_rows[i]
        if _row_marker_only(row):
            target_idx: int | None = None
            target_direction = "back"
            blocked_by_anchor = False
            for k in range(len(out) - 1, -1, -1):
                if _row_has_numeric_estimate(out[k]):
                    target_idx = k
                    break
                if _row_is_text_anchor(out[k]):
                    blocked_by_anchor = True
                    break

            if (
                target_idx is None
                and blocked_by_anchor
                and i + 1 < len(input_rows)
                and _row_has_numeric_estimate(input_rows[i + 1])
            ):
                target_idx = i + 1
                target_direction = "forward"

            if target_idx is not None:
                source = (
                    out[target_idx] if target_direction == "back"
                    else input_rows[target_idx]
                )
                target = list(source)
                attached = False
                for col_i in range(min(len(row), len(target))):
                    marker = (row[col_i] or "").strip()
                    if not marker or not _SIG_MARKER_CHARS.match(marker):
                        continue
                    cur = (target[col_i] or "").rstrip()
                    if not cur:
                        continue
                    target[col_i] = f"{cur}{_SUP_OPEN}{marker}{_SUP_CLOSE}"
                    attached = True
                if attached:
                    if target_direction == "back":
                        out[target_idx] = target
                    else:
                        input_rows[target_idx] = target
                    i += 1
                    continue
        out.append(row)
        i += 1
    return out


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def cells_grid_to_html(rows: Sequence[Sequence[str | None]]) -> str:
    """Render a 2-D cell grid as an HTML ``<table>`` block.

    Applies the full cleaning pipeline (merge continuations, strip leader
    dots, split mashed cells, drop running headers, detect multi-row
    header, fold super-headers, fold suffix continuations, attach
    significance markers, render group separators). Returns ``""`` for
    tables with fewer than 2 rows after cleaning.
    """
    if len(rows) < 2:
        return ""

    norm: list[list[str]] = []
    for row in rows:
        norm.append([(c or "").strip() if c is not None else "" for c in row])

    norm = _drop_running_header_rows(norm)
    if len(norm) < 2:
        return ""

    merged = _merge_continuation_rows(norm)
    if len(merged) < 2:
        return ""

    n_cols = max(len(r) for r in merged) if merged else 0
    if n_cols == 0:
        return ""

    for r in merged:
        while len(r) < n_cols:
            r.append("")

    for row in merged:
        for ci in range(len(row)):
            row[ci] = _strip_leader_dots(row[ci])
            row[ci] = _split_mashed_cell(row[ci])

    merged = _merge_significance_marker_rows(merged)
    if len(merged) < 2:
        return ""

    n_header = 1
    for k in range(1, min(3, len(merged))):
        if _is_group_separator(merged[k], n_cols):
            break
        if _is_header_like_row(merged[k]):
            n_header = k + 1
        else:
            break
    if len(merged) - n_header < 1:
        n_header = 1

    header_rows = merged[:n_header]
    body = merged[n_header:]

    header_rows = _fold_super_header_rows(header_rows)
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
                f'    <tr><td colspan="{n_cols}"><strong>'
                f"{_html_escape(row[0])}</strong></td></tr>"
            )
            continue
        lines.append("    <tr>")
        for c in row:
            lines.append(f"      <td>{_html_escape(c)}</td>")
        lines.append("    </tr>")
    lines.append("  </tbody>")
    lines.append("</table>")

    return "\n".join(lines) + "\n"


__all__ = [
    "cells_grid_to_html",
    "_html_escape",
    "_merge_continuation_rows",
    "_strip_leader_dots",
    "_split_mashed_cell",
    "_is_header_like_row",
    "_is_group_separator",
    "_drop_running_header_rows",
    "_is_running_header_cell",
    "_is_strong_running_header",
    "_is_weak_running_header",
    "_fold_super_header_rows",
    "_fold_suffix_continuation_columns",
    "_merge_significance_marker_rows",
    "_MERGE_SEPARATOR",
    "_SUP_OPEN",
    "_SUP_CLOSE",
]
