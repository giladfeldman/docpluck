"""
docpluck.tables.flatten — turn structured table cells into parseable per-row
records (sentence + structured fields) for downstream stat-verification tools
(effectcheck, escimate, scimeto).

Why: docpluck emits academic results tables as `<table>` HTML. Each `<td>`
carries just the cell value (`3.93`) while the column header (`t-value`) and
the row label (`Importance`) live in separate cells. A sentence-oriented
parser scanning the markdown text sees a bare `3.93` and can't bind it to a
test. ESCIcheck filed this in `DOCPLUCK_HANDOFF_2026-05-24.md` (D1 cluster) —
~78 effectcheck rows blocked across 6 canary papers (collabra_90203,
collabra_57785, lee_feldman_rsos_250908, imada_collabra_32572,
brick_collabra_23443, majumder_jdm_2024_31).

What we emit: per body row, a `FlattenedRow` dict with
  * `raw_cells` — uninterpreted cell strings (downstream consumer can roll
    its own parser without trusting ours)
  * `header`   — column-header strings (same length as raw_cells)
  * `row_label` — the body row's left-most non-numeric cell (or first cell)
  * `sentence` — best-effort English flattening, e.g.
      "Importance: t(741) = 3.93, p < .001, d = 0.29"
    Built by `_assemble_sentence` from the parsed `fields`. Three nested
    fidelity levels so consumers pick what they trust.
  * `fields`   — structured dict of recognized statistical quantities
    (`t`, `df`, `F`, `df1`, `df2`, `r`, `n`, `p_op`, `p`, `d`, `eta2`, `M`,
    `SD`, `CI_lower`, `CI_upper`). Empty dict when nothing is recognized.

Canonical contract: docpluck always emits these records as a sidecar
`<paper>.tables.jsonl` next to the rendered `.md`. The `render_pdf_to_markdown`
flag `flatten_tables_inline=True` additionally emits a human-readable block
*derived from* the same records below each `<table>`, bounded by HTML-comment
sentinels (`<!-- docpluck:flattened-table id="T8" start -->` … ` end -->`).
The two outputs share a single code path — the inline block is *generated
from* the JSONL records, so they cannot drift relative to each other.

ESCIcheck handoff source: `ESCIcheckapp/docs/DOCPLUCK_HANDOFF_2026-05-25.md`.
Triage cluster: `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md` → EC-T1.
"""

from __future__ import annotations

import re
from typing import Optional, TypedDict

from . import Cell, Table
from .cell_cleaning import (
    _drop_running_header_rows,
    _is_group_separator,
    _is_header_like_row,
    _merge_continuation_rows,
    _merge_significance_marker_rows,
    _fold_super_header_rows,
    _fold_suffix_continuation_columns,
    _strip_leader_dots,
    _split_mashed_cell,
)


# ── Public types ─────────────────────────────────────────────────────────────


class FlattenedRow(TypedDict):
    """One row of a structured table, rendered as a parseable record."""

    table_id: str
    page: int
    label: Optional[str]            # Table label, e.g. "Table 8"
    row_idx: int                    # 0-based body-row index
    row_label: str                  # Left-most non-numeric cell, or first cell
    header: list[str]               # Column-header strings
    raw_cells: list[str]            # Body-row cells (same len as header)
    sentence: str                   # Best-effort flattened English
    fields: dict[str, object]       # Structured parsed values (may be empty)


# ── Grid construction (mirrors cells_grid_to_html cleaning steps) ───────────


def _cells_to_grid(cells: list[Cell]) -> list[list[str]]:
    """Reconstruct a row-major 2-D grid from a flat Cell list.

    Same logic the HTML emitter uses (`cells_grid_to_html` in
    cell_cleaning.py:650-660). Defensive against missing rows/cols.
    """
    if not cells:
        return []
    n_r = max(c["r"] for c in cells) + 1
    n_c = max(c["c"] for c in cells) + 1
    grid: list[list[str]] = [["" for _ in range(n_c)] for _ in range(n_r)]
    for c in cells:
        # Take the first text written into each (r, c) — duplicates are rare
        # but if they appear we trust the earlier one. (Mirrors HTML emitter.)
        if grid[c["r"]][c["c"]] == "":
            grid[c["r"]][c["c"]] = (c.get("text") or "").strip()
    return grid


def _clean_grid(grid: list[list[str]]) -> tuple[list[list[str]], list[list[str]]]:
    """Run the same cleaning pipeline as `cells_grid_to_html` and split into
    (header_rows, body_rows). Returns ([], []) when the table is too small."""
    if len(grid) < 2:
        return [], []

    norm: list[list[str]] = []
    for row in grid:
        norm.append([(c or "").strip() if c is not None else "" for c in row])

    norm = _drop_running_header_rows(norm)
    if len(norm) < 2:
        return [], []

    merged = _merge_continuation_rows(norm)
    if len(merged) < 2:
        return [], []

    n_cols = max(len(r) for r in merged) if merged else 0
    if n_cols == 0:
        return [], []

    for r in merged:
        while len(r) < n_cols:
            r.append("")

    for row in merged:
        for ci in range(len(row)):
            row[ci] = _strip_leader_dots(row[ci])
            row[ci] = _split_mashed_cell(row[ci])

    merged = _merge_significance_marker_rows(merged)
    if len(merged) < 2:
        return [], []

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
    return header_rows, body


# ── Column-role classification ──────────────────────────────────────────────


# A column-role is the canonical statistic kind we believe a column carries.
# We match on the (case-folded, punctuation-stripped) column-header text.
# Order matters — earlier entries win. The patterns target the academic-paper
# vocabulary, not exhaustive coverage; unmatched columns fall through to a
# generic "header: value" rendering.
_ROLE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("t",     re.compile(r"^\s*t(?:[\s\-]?value|[\s\-]?stat(?:istic)?)?\s*$")),
    # F_with_df must precede the bare-F pattern; ordering is load-bearing.
    ("F_with_df", re.compile(r"^\s*F\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*$")),
    ("F",     re.compile(r"^\s*F(?:[\s\-]?value|[\s\-]?stat(?:istic)?)?\s*$")),
    ("chi2",  re.compile(r"^\s*(?:χ\s*²?|χ2|chi[\s\-]?(?:square|sq|2))\s*$", re.I)),
    ("r",     re.compile(r"^\s*r\s*$")),
    ("df",    re.compile(r"^\s*df\s*$", re.I)),
    ("df1",   re.compile(r"^\s*df\s*1\s*$", re.I)),
    ("df2",   re.compile(r"^\s*df\s*2\s*$", re.I)),
    ("p",     re.compile(r"^\s*p(?:[\s\-]?value)?\s*$", re.I)),
    ("d",     re.compile(r"^\s*(?:d|cohen[’']?s?\s*d)\s*$", re.I)),
    ("eta2",  re.compile(r"^\s*(?:η\s*²?|η2|eta[\s\-]?(?:square|sq|2)?(?:_?p)?)\s*$", re.I)),
    ("M",     re.compile(r"^\s*(?:M|mean)\s*$", re.I)),
    ("SD",    re.compile(r"^\s*(?:SD|std\.?\s*dev\.?|standard\s+deviation)\s*$", re.I)),
    ("n",     re.compile(r"^\s*n\s*$", re.I)),
    ("N",     re.compile(r"^\s*N\s*$")),
    ("CI",    re.compile(r"^\s*(?:95\s*%?\s*)?CI(?:\s*\[?\s*lower\s*,?\s*upper\s*\]?)?\s*$", re.I)),
    ("CI_lo", re.compile(r"^\s*(?:lower|LL|lo|95\s*%?\s*lower)\s*$", re.I)),
    ("CI_hi", re.compile(r"^\s*(?:upper|UL|hi|95\s*%?\s*upper)\s*$", re.I)),
]


def _classify_column(header: str) -> Optional[str]:
    """Return the canonical role for a column header, or None if unrecognized.

    F-with-df (e.g. ``F(1, 998)``) returns ``"F_with_df"`` so the caller can
    later extract the df pair from the header itself.
    """
    h = (header or "").strip()
    if not h:
        return None
    # Strip a single trailing punct (`,`, `:`, `.`) that some PDFs include.
    h = h.rstrip(",:.")
    for role, pat in _ROLE_PATTERNS:
        if pat.match(h):
            return role
    return None


# ── Cell-value parsing ──────────────────────────────────────────────────────


_NUM_RE = re.compile(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*$")
_P_OP_RE = re.compile(r"^\s*([<>=]+)?\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*$")
_CI_INLINE_RE = re.compile(
    r"\[?\s*([-+]?\d+\.\d+)\s*,\s*([-+]?\d+\.\d+)\s*\]?"
)


def _parse_number(s: str) -> Optional[float]:
    m = _NUM_RE.match(s or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _parse_p_cell(s: str) -> tuple[Optional[str], Optional[float]]:
    """Parse a p-value cell that may carry a comparison op: ``<.001`` → ('<', 0.001)."""
    if not s:
        return None, None
    txt = s.strip().lstrip("p").strip()
    txt = txt.lstrip(":=").strip()
    m = _P_OP_RE.match(txt)
    if not m:
        return None, None
    op, val = m.group(1), m.group(2)
    try:
        f = float(val)
    except ValueError:
        return op, None
    return (op or "="), f


def _parse_ci_cell(s: str) -> tuple[Optional[float], Optional[float]]:
    """Parse a ``[0.20, 0.38]`` or ``0.20, 0.38`` CI cell into (lo, hi)."""
    m = _CI_INLINE_RE.search(s or "")
    if not m:
        return None, None
    try:
        return float(m.group(1)), float(m.group(2))
    except ValueError:
        return None, None


# ── Row flattening ──────────────────────────────────────────────────────────


def _pick_row_label(row: list[str]) -> tuple[str, int]:
    """Return (label, label_col_idx). Picks the left-most cell that is not
    a pure number — that's almost always the row identifier in academic tables."""
    for i, cell in enumerate(row):
        if cell.strip() == "":
            continue
        if _parse_number(cell) is None:
            return cell.strip(), i
    # All-numeric row: fall back to first cell, even if empty.
    return (row[0].strip() if row else ""), 0


def _flatten_one_row(
    table_id: str,
    page: int,
    label: Optional[str],
    row_idx: int,
    header: list[str],
    row: list[str],
) -> FlattenedRow:
    row_label, label_col = _pick_row_label(row)

    # Find the F-with-df regex by role name so the list-ordering can shift
    # without breaking the lookup.
    f_with_df_re = next(p for r, p in _ROLE_PATTERNS if r == "F_with_df")

    # Classify each non-label column.
    roles: dict[int, str] = {}
    df_from_header: dict[int, tuple[int, int]] = {}
    for ci, h in enumerate(header):
        if ci == label_col:
            continue
        role = _classify_column(h)
        if role == "F_with_df":
            m = f_with_df_re.match((h or "").strip().rstrip(",:."))
            if m:
                df_from_header[ci] = (int(m.group(1)), int(m.group(2)))
            roles[ci] = "F"
        elif role is not None:
            roles[ci] = role

    # Pull per-role values out of the body row.
    role_vals: dict[str, str] = {}
    role_nums: dict[str, float] = {}
    for ci, role in roles.items():
        if ci >= len(row):
            continue
        raw = (row[ci] or "").strip()
        if not raw:
            continue
        role_vals[role] = raw
        if role == "p":
            op, p = _parse_p_cell(raw)
            if p is not None:
                role_nums["p"] = p
                if op:
                    role_vals["p_op"] = op
        elif role == "CI":
            lo, hi = _parse_ci_cell(raw)
            if lo is not None and hi is not None:
                role_nums["CI_lower"] = lo
                role_nums["CI_upper"] = hi
        else:
            n = _parse_number(raw)
            if n is not None:
                role_nums[role] = n

    # Consolidate separate CI_lo / CI_hi columns into CI_lower / CI_upper so
    # the assembler sees a single CI primitive.
    if "CI_lo" in role_nums and "CI_hi" in role_nums:
        role_nums["CI_lower"] = role_nums.pop("CI_lo")
        role_nums["CI_upper"] = role_nums.pop("CI_hi")

    # Resolve df: prefer explicit "df" cell; else F-with-df header.
    df_val = role_nums.get("df")
    df1_val = role_nums.get("df1")
    df2_val = role_nums.get("df2")
    for ci, (a, b) in df_from_header.items():
        if df1_val is None and df2_val is None:
            df1_val, df2_val = float(a), float(b)

    fields: dict[str, object] = {}
    for k in ("t", "F", "chi2", "r", "d", "eta2", "M", "SD"):
        if k in role_nums:
            fields[k] = role_nums[k]
    for k in ("n", "N"):
        if k in role_nums:
            v = role_nums[k]
            fields[k] = int(v) if v == int(v) else v
    for k_label, k_val in (("df", df_val), ("df1", df1_val), ("df2", df2_val)):
        if k_val is not None:
            fields[k_label] = int(k_val) if k_val == int(k_val) else k_val
    if "p" in role_nums:
        fields["p"] = role_nums["p"]
        if "p_op" in role_vals:
            fields["p_op"] = role_vals["p_op"]
    if "CI_lower" in role_nums:
        fields["CI_lower"] = role_nums["CI_lower"]
        fields["CI_upper"] = role_nums["CI_upper"]

    sentence = _assemble_sentence(row_label, role_vals, role_nums, df_val, df1_val, df2_val)

    return FlattenedRow(
        table_id=table_id,
        page=page,
        label=label,
        row_idx=row_idx,
        row_label=row_label,
        header=list(header),
        raw_cells=list(row),
        sentence=sentence,
        fields=fields,
    )


def _fmt_num(x: float) -> str:
    """Format a parsed numeric value preserving common APA conventions."""
    if x == int(x):
        return str(int(x))
    # Strip trailing zeros without losing leading-zero precision.
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return s or "0"


def _assemble_sentence(
    row_label: str,
    role_vals: dict[str, str],
    role_nums: dict[str, float],
    df: Optional[float],
    df1: Optional[float],
    df2: Optional[float],
) -> str:
    """Produce a flattened APA-style sentence from the parsed cells.

    Consolidations applied:
      * ``t`` + ``df``           → ``t(df) = value``
      * ``F`` + ``df1, df2``     → ``F(df1, df2) = value``
      * ``r`` + ``n``            → ``r(n - 2) = value``
      * ``chi2`` + ``df`` + ``n`` → ``χ²(df, N = n) = value``
      * ``M`` + ``SD``            → ``M = m, SD = sd`` (joint)
      * ``p_op`` + ``p``          → ``p {op} {value}``
      * ``CI_lower`` + ``CI_upper`` → ``95% CI [lo, hi]``

    Unmatched columns fall through to ``header: value`` form, dropped from
    the sentence to keep it readable.
    """
    parts: list[str] = []

    if "t" in role_nums:
        if df is not None:
            parts.append(f"t({_fmt_num(df)}) = {role_vals['t']}")
        else:
            parts.append(f"t = {role_vals['t']}")

    if "F" in role_nums:
        if df1 is not None and df2 is not None:
            parts.append(f"F({_fmt_num(df1)}, {_fmt_num(df2)}) = {role_vals['F']}")
        else:
            parts.append(f"F = {role_vals['F']}")

    if "chi2" in role_nums:
        chi_val = role_vals["chi2"]
        if df is not None and "n" in role_nums:
            parts.append(f"χ²({_fmt_num(df)}, N = {role_vals['n']}) = {chi_val}")
        elif df is not None:
            parts.append(f"χ²({_fmt_num(df)}) = {chi_val}")
        else:
            parts.append(f"χ² = {chi_val}")

    if "r" in role_nums:
        if "n" in role_nums:
            try:
                df_r = int(role_nums["n"]) - 2
                parts.append(f"r({df_r}) = {role_vals['r']}")
            except (TypeError, ValueError):
                parts.append(f"r = {role_vals['r']}")
        else:
            parts.append(f"r = {role_vals['r']}")

    if "M" in role_nums and "SD" in role_nums:
        parts.append(f"M = {role_vals['M']}, SD = {role_vals['SD']}")
    elif "M" in role_nums:
        parts.append(f"M = {role_vals['M']}")
    elif "SD" in role_nums:
        parts.append(f"SD = {role_vals['SD']}")

    if "p" in role_nums:
        op = role_vals.get("p_op", "=")
        # `role_vals['p']` may carry the comparison operator inline (`<.001`).
        # Strip leading ops so the sentence renders `p < .001` not `p < <.001`.
        p_txt = role_vals["p"].lstrip("p").lstrip(":=").strip().lstrip("<>=").strip()
        parts.append(f"p {op} {p_txt}")

    if "d" in role_nums:
        parts.append(f"d = {role_vals['d']}")
    if "eta2" in role_nums:
        parts.append(f"η² = {role_vals['eta2']}")

    if "CI_lower" in role_nums and "CI_upper" in role_nums:
        if "CI" in role_vals:
            parts.append(f"95% CI [{role_vals['CI']}]")
        else:
            lo = _fmt_num(role_nums["CI_lower"])
            hi = _fmt_num(role_nums["CI_upper"])
            parts.append(f"95% CI [{lo}, {hi}]")

    if not parts:
        # No stat shapes recognized — fall back to a labelled cell dump so the
        # row is still visible. Skip empty/label cells.
        return row_label

    body = ", ".join(parts)
    if row_label:
        return f"{row_label}: {body}"
    return body


# ── Public entry points ─────────────────────────────────────────────────────


def flatten_table(table: Table) -> list[FlattenedRow]:
    """Flatten a structured `Table` into per-row `FlattenedRow` records.

    Returns ``[]`` for tables with no usable cells or fewer than 2 rows
    after cleaning. Safe to call on every emitted table — empty results
    are silently skipped by the JSONL sidecar writer.
    """
    cells = table.get("cells") or []
    if not cells:
        return []
    grid = _cells_to_grid(cells)
    header_rows, body = _clean_grid(grid)
    if not header_rows or not body:
        return []

    # Use the FINAL header row as the canonical column-header line. (When the
    # table has a super-header + sub-header, _fold_super_header_rows already
    # concatenated them so the last header row carries the full label.)
    header = header_rows[-1]

    table_id = table.get("id") or table.get("label") or "table"
    page = int(table.get("page") or 0)
    label = table.get("label")

    out: list[FlattenedRow] = []
    n_cols = len(header)
    for row_idx, row in enumerate(body):
        if _is_group_separator(row, n_cols):
            continue
        # Pad/trim the body row to the header length so role lookup is safe.
        if len(row) < n_cols:
            row = list(row) + [""] * (n_cols - len(row))
        elif len(row) > n_cols:
            row = list(row[:n_cols])
        rec = _flatten_one_row(table_id, page, label, row_idx, header, row)
        out.append(rec)

    return out


def render_flattened_inline(
    records: list[FlattenedRow],
    *,
    table_id: str,
    label: Optional[str] = None,
    version: Optional[str] = None,
) -> str:
    """Render flattened rows as a markdown block bounded by HTML-comment
    sentinels, for inline emission below a `<table>`.

    Returns ``""`` when records is empty (no inline block produced).
    """
    if not records:
        return ""
    title = label or f"Table {table_id}"
    ver_suffix = f" v{version}" if version else ""
    lines: list[str] = []
    lines.append(f'<!-- docpluck:flattened-table id="{table_id}" start -->')
    lines.append(f"### {title} — rendered as text")
    lines.append(
        f"*Flattened from header + cells by docpluck{ver_suffix}. "
        f"See the `.tables.jsonl` sidecar for structured form.*"
    )
    lines.append("")
    for r in records:
        lines.append(f"- {r['sentence']}")
    lines.append(f'<!-- docpluck:flattened-table id="{table_id}" end -->')
    return "\n".join(lines) + "\n"


def flatten_tables_for_paper(tables: list[Table]) -> list[FlattenedRow]:
    """Flatten every structured table for a paper, in document order.

    Returned records are suitable for direct JSONL emission (one record per
    line via ``json.dumps``).
    """
    out: list[FlattenedRow] = []
    for tbl in tables:
        out.extend(flatten_table(tbl))
    return out


__all__ = [
    "FlattenedRow",
    "flatten_table",
    "flatten_tables_for_paper",
    "render_flattened_inline",
]
