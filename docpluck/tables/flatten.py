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
    _MERGE_SEPARATOR,
    _SUP_OPEN,
    _SUP_CLOSE,
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


def _strip_fold_sentinels(s: str) -> str:
    """Remove the internal fold/super-script sentinels (`\\x00BR\\x00`,
    `\\x00SUP\\x00`, `\\x00/SUP\\x00`) the HTML emitter uses, so the plain
    `header`/`raw_cells` strings we emit in a `FlattenedRow` are clean."""
    if not s:
        return s
    return (
        s.replace(_MERGE_SEPARATOR, " ")
        .replace(_SUP_OPEN, "")
        .replace(_SUP_CLOSE, "")
        .strip()
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
    # est_ci: a *combined* effect-and-interval column whose header carries an
    # effect word (or any leading text) followed by a parenthesised CI marker,
    # e.g. "Risk diff. (95% CI)", "Mean diff (95%CI)", "OR (95% CI)",
    # "Cohen's d (95% CI)". The cell then holds an estimate AND its interval
    # (e.g. "-1.01% (-10.36-8.34)"). Must precede the bare-"CI" pattern so a
    # combined column is not mis-read as an interval-only column.
    ("est_ci", re.compile(r"[A-Za-z].*\(\s*95\s*%?\s*C\.?\s*I", re.I)),
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


# Range separators that are typographically DISTINCT from a minus sign, so a
# split on them is sign-unambiguous: en-dash, em-dash, horizontal bar, or the
# spelled-out " to ". (Camelot cells are NOT run through normalize.py, so the
# source glyphs survive — a minus is usually U+2212/U+002D while the range
# separator is U+2013, and they disambiguate themselves.)
_RANGE_SEP_RE = re.compile(r"\s*(?:–|—|―|\bto\b)\s*")
_PAREN_RE = re.compile(r"\(([^()]*)\)")
# Two signed decimals joined by a single ASCII hyphen — the AMBIGUOUS case the
# distinct-glyph split above could not resolve (e.g. "-11.2-7.5").
_HYPHEN_CI_RE = re.compile(r"^\s*(-?)\s*(\d*\.?\d+)\s*-\s*(-?)\s*(\d*\.?\d+)\s*$")


def _to_signed_float(s: str) -> Optional[float]:
    """First signed decimal in `s`, with U+2212 minus folded to ASCII."""
    if not s:
        return None
    m = re.search(r"[-+]?\d*\.?\d+", s.replace("−", "-").replace("%", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _parse_leading_number(s: str) -> Optional[float]:
    """Leading numeric token of a combined estimate cell, e.g.
    ``-1.01% (-10.36-8.34)`` → ``-1.01``. Stops at the first ``(``."""
    head = (s or "").split("(", 1)[0]
    return _to_signed_float(head)


def _resolve_hyphen_ci(
    body: str, estimate: Optional[float]
) -> tuple[Optional[float], Optional[float]]:
    """Resolve a hyphen-joined CI like ``-11.2-7.5`` where the separator dash
    collides with a negative sign. docpluck enforces two general invariants —
    interval monotonicity (``lo < hi``) and, when the row's point estimate is
    known, the estimate-in-interval invariant (``lo <= estimate <= hi``) — to
    pick the one sign assignment that can be correct. Keyed purely on the
    structural shape, never on paper identity."""
    t = body.replace("−", "-").replace("%", "").strip().strip("[]()")
    m = _HYPHEN_CI_RE.match(t)
    if not m:
        return None, None
    mag1, mag2 = float(m.group(2)), float(m.group(4))
    sign1 = -1.0 if m.group(1) == "-" else 1.0
    sign2 = -1.0 if m.group(3) == "-" else 1.0
    primary = (sign1 * mag1, sign2 * mag2)

    # Candidate sign assignments, primary interpretation first.
    seen: set[tuple[float, float]] = set()
    valid: list[tuple[float, float]] = []
    for a in (sign1, 1.0, -1.0):
        for c in (sign2, 1.0, -1.0):
            cand = (a * mag1, c * mag2)
            if cand in seen:
                continue
            seen.add(cand)
            lo, hi = cand
            if lo < hi and (estimate is None or lo <= estimate <= hi):
                valid.append(cand)
    if primary in valid:
        return primary
    if valid:
        return valid[0]
    # No assignment satisfies the invariants — fall back to the literal parse
    # only if it is at least monotonic, else give up (don't emit a bad CI).
    if primary[0] < primary[1]:
        return primary
    return None, None


def _parse_ci_cell(
    s: str, estimate: Optional[float] = None
) -> tuple[Optional[float], Optional[float]]:
    """Parse a confidence-interval cell into ``(lo, hi)``.

    Handles, in order of decreasing certainty:
      1. comma-separated ``[0.20, 0.38]`` / ``0.20, 0.38`` (unambiguous);
      2. a distinct range glyph (en/em-dash or " to "), e.g. ``-10.36–8.34``
         (sign-unambiguous because the separator is not a minus);
      3. a hyphen-collision ``-11.2-7.5`` resolved via the monotonicity and
         estimate-in-interval invariants (see ``_resolve_hyphen_ci``).

    When the cell wraps the interval in parentheses (a combined
    ``-1.01% (-10.36-8.34)`` estimate cell), the parenthesised content is tried
    first. `estimate` (the row's point estimate) disambiguates case 3."""
    if not s:
        return None, None
    parens = _PAREN_RE.findall(s)
    for body in ([parens[-1]] if parens else []) + [s]:
        b = (body or "").strip().strip("[]")
        # 1. comma-separated
        m = _CI_INLINE_RE.search(b)
        if m:
            try:
                return float(m.group(1)), float(m.group(2))
            except ValueError:
                pass
        # 2. distinct range glyph (en/em-dash, " to ")
        parts = _RANGE_SEP_RE.split(b, maxsplit=1)
        if len(parts) == 2:
            lo, hi = _to_signed_float(parts[0]), _to_signed_float(parts[1])
            if lo is not None and hi is not None:
                return lo, hi
        # 3. hyphen collision — resolve by invariant
        lo, hi = _resolve_hyphen_ci(b, estimate)
        if lo is not None and hi is not None:
            return lo, hi
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


def _est_label_from_header(h: str) -> str:
    """Effect label of a combined ``est_ci`` column — the header with its
    parenthesised CI marker stripped, e.g. ``Risk diff. (95% CI)`` →
    ``Risk diff.``."""
    cleaned = _strip_fold_sentinels(h or "")
    cleaned = re.sub(r"\(?\s*95\s*%?\s*C\.?\s*I[^)]*\)?", "", cleaned, flags=re.I)
    return cleaned.strip(" .,:") or ""


def _flatten_one_row(
    table_id: str,
    page: int,
    label: Optional[str],
    row_idx: int,
    header: list[str],
    row: list[str],
    group: Optional[str] = None,
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
        elif role == "est_ci":
            # Combined estimate-and-interval cell, e.g. "-1.01% (-10.36-8.34)".
            est = _parse_leading_number(raw)
            if est is not None:
                role_nums["est"] = est
                role_vals["est"] = raw.split("(", 1)[0].strip() or _fmt_num(est)
                role_vals["est_label"] = _est_label_from_header(header[ci])
            # The estimate anchors the CI sign when the bounds are hyphen-glued.
            lo, hi = _parse_ci_cell(raw, estimate=est)
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
    if group:
        fields["group"] = group
    for k in ("t", "F", "chi2", "r", "d", "eta2", "M", "SD", "est"):
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

    sentence = _assemble_sentence(
        row_label, role_vals, role_nums, df_val, df1_val, df2_val, group
    )

    return FlattenedRow(
        table_id=table_id,
        page=page,
        label=label,
        row_idx=row_idx,
        row_label=_strip_fold_sentinels(row_label),
        header=[_strip_fold_sentinels(h) for h in header],
        raw_cells=[_strip_fold_sentinels(c) for c in row],
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
    group: Optional[str] = None,
) -> str:
    """Produce a flattened APA-style sentence from the parsed cells.

    Consolidations applied:
      * ``est`` (+ ``CI``)        → ``{effect} = {value}`` (combined column)
      * ``t`` + ``df``           → ``t(df) = value``
      * ``F`` + ``df1, df2``     → ``F(df1, df2) = value``
      * ``r`` + ``n``            → ``r(n - 2) = value``
      * ``chi2`` + ``df`` + ``n`` → ``χ²(df, N = n) = value``
      * ``M`` + ``SD``            → ``M = m, SD = sd`` (joint)
      * ``p_op`` + ``p``          → ``p {op} {value}``
      * ``CI_lower`` + ``CI_upper`` → ``95% CI [lo, hi]``

    `group` (a super-header arm such as ``ITT`` / ``PP``) is appended to the
    row label so parallel-group rows stay distinguishable.

    Unmatched columns fall through to ``header: value`` form, dropped from
    the sentence to keep it readable.
    """
    parts: list[str] = []

    if "est" in role_nums:
        est_label = role_vals.get("est_label", "")
        est_txt = role_vals.get("est", _fmt_num(role_nums["est"]))
        parts.append(f"{est_label} = {est_txt}" if est_label else est_txt)

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

    eff_label = _strip_fold_sentinels(row_label)
    if group:
        eff_label = f"{eff_label} ({group})" if eff_label else f"({group})"

    if not parts:
        # No stat shapes recognized — fall back to a labelled cell dump so the
        # row is still visible. Skip empty/label cells.
        return eff_label

    body = ", ".join(parts)
    if eff_label:
        return f"{eff_label}: {body}"
    return body


# ── Public entry points ─────────────────────────────────────────────────────


def _detect_column_groups(
    header: list[str],
) -> Optional[tuple[list[int], list[tuple[str, list[int]]]]]:
    """Detect parallel column groups from a folded super-header.

    `_fold_super_header_rows` joins a super-header label into the first column
    of each span it covers using the `_MERGE_SEPARATOR` sentinel (e.g.
    ``ITT\\x00BR\\x00PSA N = 98``). Two or more such sentinel columns therefore
    mark the start of two or more parallel arms (ITT / PP, Study 1 / Study 2).

    Returns ``(label_cols, [(group_label, col_indices), ...])`` when ≥2 groups
    are found, else ``None`` (so non-grouped tables are byte-identical to the
    pre-existing single-row path). Keyed on the structural fold signature, not
    on any column text — general across publishers."""
    starts = [i for i, h in enumerate(header) if _MERGE_SEPARATOR in (h or "")]
    if len(starts) < 2:
        return None
    label_cols = list(range(0, starts[0]))
    groups: list[tuple[str, list[int]]] = []
    for gi, start in enumerate(starts):
        end = starts[gi + 1] if gi + 1 < len(starts) else len(header)
        glabel = (header[start].split(_MERGE_SEPARATOR, 1)[0]).strip()
        groups.append((glabel, list(range(start, end))))
    return label_cols, groups


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

    grouped = _detect_column_groups(header)

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

        if grouped is None:
            out.append(_flatten_one_row(table_id, page, label, row_idx, header, row))
            continue

        # Parallel-group table: emit one record per (row × arm). Shared label
        # columns are prepended to each arm's own columns so role lookup and
        # the row label both work on the sliced sub-row.
        label_cols, groups = grouped
        for glabel, gcols in groups:
            if not any((row[i] or "").strip() for i in gcols):
                continue  # this arm is empty on this row — don't emit a stub
            sub_header = [header[i] for i in label_cols] + [header[i] for i in gcols]
            sub_row = [row[i] for i in label_cols] + [row[i] for i in gcols]
            out.append(
                _flatten_one_row(
                    table_id, page, label, row_idx, sub_header, sub_row, group=glabel
                )
            )

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
