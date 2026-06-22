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
    (`t`, `df`, `F`, `df1`, `df2`, `r`, `n`, `p_op`, `p`, `d`, `eta2`, `BF01`,
    `est`, `M`, `SD`, `CI_lower`, `CI_upper`, and `group` for a parallel-arm
    row's arm label). Empty dict when nothing is recognized.

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
    # BF01 (Bayes factor in favour of the null). Must precede bare patterns so
    # it isn't swallowed; accepts the subscript glyph, "BF01", "BF 01", "BF₀₁".
    ("BF01",  re.compile(r"^\s*BF\s*[._]?\s*(?:0?1|₀₁)\s*$", re.I)),
    ("df",    re.compile(r"^\s*df\s*$", re.I)),
    ("df1",   re.compile(r"^\s*df\s*1\s*$", re.I)),
    ("df2",   re.compile(r"^\s*df\s*2\s*$", re.I)),
    ("p",     re.compile(r"^\s*p(?:[\s\-]?value)?\s*$", re.I)),
    # "d", "Cohen's d", and "d or dz [95% CI]" combined effect+interval headers.
    # The combined bracket form is handled as est_ci below; the bare form here.
    ("d",     re.compile(r"^\s*(?:d|cohen[’']?s?\s*d)\s*$", re.I)),
    ("eta2",  re.compile(r"^\s*(?:η\s*²?|η2|eta[\s\-]?(?:square|sq|2)?(?:_?p)?)\s*$", re.I)),
    ("M",     re.compile(r"^\s*(?:M|mean)\s*$", re.I)),
    ("SD",    re.compile(r"^\s*(?:SD|std\.?\s*dev\.?|standard\s+deviation)\s*$", re.I)),
    ("n",     re.compile(r"^\s*n\s*$", re.I)),
    ("N",     re.compile(r"^\s*N\s*$")),
    # est_ci: a *combined* effect-and-interval column whose header carries an
    # effect word (or any leading text) followed by a CI marker — either
    # parenthesised "Risk diff. (95% CI)" / "OR (95% CI)" OR square-bracketed
    # "d or dz [95%CI]" / "d [95% CI]". The cell then holds an estimate AND its
    # interval (e.g. "-1.01% (-10.36-8.34)" or "0.76 [.50, 1.02]"). Must precede
    # the bare-"CI" pattern so a combined column is not mis-read as interval-only.
    ("est_ci", re.compile(r"[A-Za-z].*[\(\[]\s*95\s*%?\s*C\.?\s*I", re.I)),
    ("CI",    re.compile(r"^\s*(?:95\s*%?\s*)?CI(?:\s*\[?\s*lower\s*,?\s*upper\s*\]?)?\s*$", re.I)),
    ("CI_lo", re.compile(r"^\s*(?:lower|LL|lo|95\s*%?\s*lower)\s*$", re.I)),
    ("CI_hi", re.compile(r"^\s*(?:upper|UL|hi|95\s*%?\s*upper)\s*$", re.I)),
]

# Effect-type hint for an est_ci / est column, keyed on the effect word in the
# header (or the recovered vocab). Lets a downstream consumer route a parsed
# estimate semantically (Request 11 §2.4). Unmatched ⇒ no hint emitted.
_EFFECT_TYPE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("cohens_d",            re.compile(r"\b(?:d\s*z|d|cohen)\b", re.I)),
    ("hedges_g",            re.compile(r"\b(?:g|hedges)\b", re.I)),
    ("pearson_r",           re.compile(r"^\s*r\b", re.I)),
    ("eta_squared_partial", re.compile(r"η\s*²?\s*_?\s*p|η²p|eta.*p\b", re.I)),
    ("eta_squared",         re.compile(r"η\s*²?|η2|eta", re.I)),
    ("odds_ratio",          re.compile(r"\bOR\b|odds\s*ratio", re.I)),
    ("risk_difference",     re.compile(r"risk\s*diff", re.I)),
    ("mean_difference",     re.compile(r"mean\s*diff|\bMD\b|difference\s+in\s+means", re.I)),
]


def _effect_type_for(label: str) -> Optional[str]:
    """Best-effort semantic effect-type for an estimate column header/label."""
    s = (label or "").strip()
    if not s:
        return None
    for et, pat in _EFFECT_TYPE_PATTERNS:
        if pat.search(s):
            return et
    return None


# Effect-type → canonical field key. Only the unambiguous effect sizes are
# promoted to a typed key; everything else stays the generic `est` (paired with
# its CI), which the consumer routes by est+CI+p (Request 11 §2.4, §4).
_EFFECT_TYPE_KEY = {
    "cohens_d": "d",
    "eta_squared_partial": "eta2",
    "eta_squared": "eta2",
}


def _effect_key(header_cell: str, hint: Optional[str]) -> str:
    """Field key for an estimate column: a typed effect key (`d` / `eta2`) when
    the header or table vocabulary names the effect, else generic `est`."""
    et = _effect_type_for(header_cell) or hint
    return _EFFECT_TYPE_KEY.get(et or "", "est")


def _classify_column(header: str) -> Optional[str]:
    """Return the canonical role for a column header, or None if unrecognized.

    F-with-df (e.g. ``F(1, 998)``) returns ``"F_with_df"`` so the caller can
    later extract the df pair from the header itself.
    """
    h = (header or "").strip()
    if not h:
        return None
    # A folded super-header cell ("Replication\x00BR\x0095% CI") carries the GROUP
    # label in the super-part and the column's OWN role in the sub-part. Classify
    # on the sub-part first (then the super-part) so a folded CI / p / stat column
    # is still recognized — otherwise the whole "Replication…95% CI" string never
    # matches and the column's role is lost (collabra.90203 T10 CI, DP-5).
    if _MERGE_SEPARATOR in h:
        for part in reversed([p.strip() for p in h.split(_MERGE_SEPARATOR) if p.strip()]):
            role = _classify_column(part)
            if role:
                return role
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
# Comma-separated CI bounds. Allow a leading-dot decimal (APA omits the leading
# zero: ".50", ".003") as well as the full "0.50" form — `\d*\.\d+`.
_CI_INLINE_RE = re.compile(
    r"\[?\s*([-+]?\d*\.\d+)\s*,\s*([-+]?\d*\.\d+)\s*\]?"
)


def _parse_number(s: str) -> Optional[float]:
    # Fold U+2212 MINUS SIGN → ASCII hyphen first (Camelot cells are NOT run
    # through normalize.py, so a negative test statistic / mean often arrives as
    # U+2212 and would otherwise fail the ASCII-only number regex — dropping a
    # valid negative value). Same fold the CI / signed-float parsers already do.
    m = _NUM_RE.match((s or "").replace("−", "-"))
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
    # Fold U+2212 MINUS → ASCII hyphen up front so the comma-separated branch
    # (`_CI_INLINE_RE` + `float()`, ASCII-sign only) doesn't silently skip a
    # negative lower bound ("[−0.48, 0.15]" → must be (-0.48, 0.15), not
    # (0.48, 0.15)). The dash/hyphen branches already fold internally.
    s = s.replace("−", "-")
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


# ── Blank-header column-role recovery ───────────────────────────────────────
#
# Some result tables (Collabra t-/F-/Bayes tables) capture the data grid but
# emit BLANK stat-column headers: the header row was absorbed into the caption
# region, or the sub-header sits a row above the data and got dropped. A
# downstream text parser cannot bind the values; docpluck can, because the
# information survives in two recoverable places — (1) the *shape* of each
# column's data tokens, and (2) the statistic vocabulary that leaked into the
# table caption / footnote. We assign a role to a blank column ONLY when backed
# by a positive signal (unambiguous data shape OR a recovered caption token),
# never by bare column position — that would fabricate labels for garbage, the
# exact failure mode the consumer forbids (Request 11). Anything we cannot
# ground stays unrecognized, and its row keeps the safe today-behaviour of an
# empty `fields` dict.

# A cell holding ONLY a confidence interval: "[.50, 1.02]", "[0.53, 0.72]",
# "(-10.36–8.34)", "0.20, 0.38". Anchored end-to-end so a combined estimate
# cell ("0.76 [.50, 1.02]") does NOT match (the leading estimate breaks it).
# Requires either a bracket OR a decimal point so a bare integer pair ("1, 114")
# is left to the df-pair detector instead.
_CI_ONLY_RE = re.compile(
    r"^\s*[\[(]\s*[-+]?\d*\.?\d+\s*[,–—\-]\s*[-+]?\d*\.?\d+\s*[\])]\s*$"
    r"|^\s*[-+]?\d*\.\d+\s*[,–—]\s*[-+]?\d*\.?\d+\s*$"
)
# A bare integer df pair in ONE cell: "1, 114", "2, 998".
_DF_PAIR_RE = re.compile(r"^\s*(\d+)\s*,\s*(\d+)\s*$")
# A p-value-shaped cell: optional comparison op + a decimal in [0, 1] range
# (one leading digit at most), or an "N/A" filler.
_P_SHAPE_RE = re.compile(r"^\s*[<>=]?\s*[01]?\.\d+\s*$")
_NA_RE = re.compile(r"^\s*n\s*/?\s*a\s*$", re.I)
# A single bare number (a candidate test statistic / effect / BF cell).
_BARE_NUM_RE = re.compile(r"^\s*[-+]?\d*\.?\d+\s*$")
_BARE_INT_RE = re.compile(r"^\s*\d+\s*$")


def _looks_like_ci_only(v: str) -> bool:
    return bool(_CI_ONLY_RE.match(v or ""))


def _looks_like_df_pair(v: str) -> bool:
    return bool(_DF_PAIR_RE.match(v or ""))


def _looks_like_p(v: str) -> bool:
    return bool(_P_SHAPE_RE.match(v or "") or _NA_RE.match(v or ""))


# A sub-one decimal: a value in [0, 1) written APA-style (".551", "0.03") with an
# optional comparison op ("<.001"). Unlike `_P_SHAPE_RE` it rejects an integer
# part ≥ 1 (so a test statistic like "1.31" is NOT mistaken for a p-value). Used
# to separate a still-blank p column (sub-one) from a still-blank df / n column
# (values ≥ 1) when both are unlabeled and adjacent. (Pass 3.5, DP-2.)
_SUB_ONE_DEC_RE = re.compile(r"^\s*[<>=]?\s*0?\.\d+\s*$")


def _looks_like_sub_one(v: str) -> bool:
    return bool(_SUB_ONE_DEC_RE.match(v or ""))


def _has_comparison_op(v: str) -> bool:
    return "<" in (v or "") or ">" in (v or "")


def _is_num_or_na(v: str) -> bool:
    """A bare number or an N/A filler — the shape of a statistic-bearing cell
    once intervals/df-pairs are excluded."""
    return bool(_BARE_NUM_RE.match(v or "") or _NA_RE.match(v or ""))


# A combined estimate-and-interval cell: a leading number, then a bracketed or
# parenthesised interval — "0.76 [.50, 1.02]", "-1.01% (-10.36-8.34)". The
# leading number outside the bracket is what distinguishes it from a pure CI.
_EST_CI_CELL_RE = re.compile(
    r"^\s*[-+]?\d*\.?\d+\s*%?\s*[\[(].*[\])]\s*$"
)


def _looks_like_est_ci(v: str) -> bool:
    return bool(_EST_CI_CELL_RE.match(v or ""))


def _column_values(body: list[list[str]], ci: int) -> list[str]:
    """Non-empty data values of column `ci` across body rows."""
    out: list[str] = []
    for row in body:
        if ci < len(row):
            v = (row[ci] or "").strip()
            if v:
                out.append(v)
    return out


def _is_numeric_ish(v: str) -> bool:
    """A cell that carries a number, interval, p-value or N/A filler — i.e. a
    statistic value rather than a label or a leaked heading."""
    v = (v or "").strip()
    return bool(
        _BARE_NUM_RE.match(v)
        or _looks_like_ci_only(v)
        or _looks_like_df_pair(v)
        or _looks_like_p(v)
    )


def _is_data_row(row: list[str]) -> bool:
    """A body row carrying ≥2 statistic values — distinguishes real data rows
    from hypothesis sub-headers / section labels that leak into the body (e.g.
    ``['H1: Identifiability', '', ...]`` or a long ``H2a: ...`` label cell)."""
    return sum(1 for c in row if _is_numeric_ish(c)) >= 2


def _table_label_col(data_rows: list[list[str]], n_cols: int) -> int:
    """The row-identifier column: the one most consistently non-numeric across
    data rows (ties → left-most). Almost always column 0 in academic tables."""
    best_ci, best_score = 0, -1
    for ci in range(n_cols):
        score = sum(
            1
            for row in data_rows
            if ci < len(row) and (row[ci] or "").strip() and not _is_numeric_ish(row[ci])
        )
        if score > best_score:
            best_ci, best_score = ci, score
    return best_ci


def _frac_match(values: list[str], pred) -> bool:
    """True when ≥2 values and ≥60% of them satisfy `pred` — tolerant of the
    occasional capture artifact (a leaked heading glued onto one cell) without
    letting a single bad cell veto a whole column's recovered role."""
    if not values:
        return False
    if len(values) < 2:
        return all(pred(v) for v in values)
    hits = sum(1 for v in values if pred(v))
    return hits >= 2 and hits / len(values) >= 0.6


# Caption-leaked header tokens → canonical role. A table's header row sometimes
# lands in the caption text (e.g. "...Explicit Learning df F p BF01 95% CI ...").
# We recover the longest run of consecutive statistic tokens as an ordered role
# sequence, used to TYPE blank columns left-to-right where data shape alone is
# ambiguous (p vs BF01 vs effect when none carry an operator).
_CAPTION_TOKEN_ROLE: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^BF\s*[._]?\s*(?:0?1|₀₁)$", re.I), "BF01"),
    (re.compile(r"^(?:η\s*²?\s*_?p?|η2p?|etap?2?|eta)$", re.I), "eta2"),
    (re.compile(r"^df$", re.I), "df"),
    (re.compile(r"^(?:95\s*%?|95)$"), "CI"),
    (re.compile(r"^C\.?I\.?$", re.I), "CI"),
    (re.compile(r"^t$"), "t"),
    (re.compile(r"^F$"), "F"),
    (re.compile(r"^r$"), "r"),
    (re.compile(r"^p$"), "p"),
    (re.compile(r"^d(?:\s*z)?$", re.I), "d"),
    (re.compile(r"^M$"), "M"),
    (re.compile(r"^SD$"), "SD"),
    (re.compile(r"^n$"), "n"),
    (re.compile(r"^N$"), "N"),
    (re.compile(r"^BF$", re.I), "BF01"),
]


def _caption_token_role(tok: str) -> Optional[str]:
    t = (tok or "").strip().strip(",:;.")
    if not t:
        return None
    for pat, role in _CAPTION_TOKEN_ROLE:
        if pat.match(t):
            return role
    return None


def _recover_caption_header_run(text: str) -> list[str]:
    """The longest run of *consecutive* statistic tokens in `text`, as an
    ordered list of canonical roles. Empty when no run of ≥2 stat tokens exists.

    A "%" attached to "95% CI" collapses to a single CI role. Keyed on the
    structural signature "a header row leaked into the caption", general across
    publishers — never on caption wording for a specific paper."""
    if not text:
        return []
    toks = re.split(r"\s+", text.strip())
    best: list[str] = []
    cur: list[str] = []
    for tok in toks:
        role = _caption_token_role(tok)
        if role is None:
            if len(cur) > len(best):
                best = cur
            cur = []
            continue
        # Collapse a duplicate trailing CI ("95%" then "CI") into one role.
        if role == "CI" and cur and cur[-1] == "CI":
            continue
        cur.append(role)
    if len(cur) > len(best):
        best = cur
    return best if len(best) >= 2 else []


def _recover_blank_roles(
    header: list[str],
    body: list[list[str]],
    label_col: int,
    caption: Optional[str],
    footnote: Optional[str],
    extra_vocab: str = "",
) -> dict[int, str]:
    """Infer roles for columns whose grid header is blank/unrecognized.

    Returns ``{col_idx: role}`` for recovered columns only (recognized-header
    columns are left to the normal `_classify_column` path). Roles use the same
    canonical names plus ``df_pair`` (a "df1, df2" cell) and ``stat`` (a typed
    or generic test statistic). Every assignment is backed by a positive
    signal — unambiguous data shape or a recovered caption/header token."""
    n = len(header)
    cols = [ci for ci in range(n) if ci != label_col]
    grid_role = {ci: _classify_column(header[ci]) for ci in cols}

    # GATE — only recover on the "header-stripped result table" signature: the
    # stat-column header row was absorbed into the caption / dropped, so most
    # data columns are unlabeled. When the table already classifies most of its
    # columns (a normal labeled table with maybe one blank spacer column), we do
    # NOT second-guess it — recovering the stragglers there mis-binds values and
    # collides with recognized roles (the chen/korbmacher over-reach). Requires
    # ≥2 blank data columns AND blanks to outnumber recognized columns.
    data_cols = [ci for ci in cols if _column_values(body, ci)]
    recognized = [ci for ci in data_cols if grid_role[ci]]
    blank = [ci for ci in data_cols if not grid_role[ci]]
    if len(blank) < 2 or len(recognized) >= len(blank):
        return {}
    # If the grid already names a core test statistic (t / F / r / χ²), the
    # header row is intact enough — recovering blank stragglers there mis-binds
    # values. The header-stripped tables we target have NO recognized statistic.
    if {grid_role[ci] for ci in recognized} & {"t", "F", "F_with_df", "r", "chi2"}:
        return {}

    # Statistic vocabulary present anywhere we can read it: the grid headers
    # (all rows, via `extra_vocab`), the caption, the footnote. Used to TYPE the
    # leading statistic column and to confirm a token is plausible before
    # assigning it.
    vocab_text = " ".join(
        [header[ci] for ci in cols] + [caption or "", footnote or "", extra_vocab]
    )
    run = _recover_caption_header_run(caption or "") or _recover_caption_header_run(
        vocab_text
    )

    # GROUNDING GATE — fire ONLY on the Request-11 signature, so we never
    # second-guess an ordinary table that merely has a blank spacer column:
    #   (a) the stat header row leaked into the caption (a recovered run), OR
    #   (b) the table names a typed effect size (Cohen's d / η²p) AND carries a
    #       combined estimate+interval column (the t-/F-with-effect shape).
    # Tables that are neither (regression OR tables, bare correlation matrices)
    # are left exactly as the grid-header path produced them.
    has_typed_effect = bool(
        re.search(
            r"\bd\s*z?\b|\bd\s+or\s+d\b|cohen|η|\beta[\s_\-]?(?:squared|sq|p|2)\b",
            vocab_text,
            re.I,
        )
    )
    has_est_ci_col = any(
        _frac_match(_column_values(body, ci), _looks_like_est_ci)
        for ci in cols
        if not grid_role[ci]
    )
    if not run and not (has_typed_effect and has_est_ci_col):
        return {}

    override: dict[int, str] = {}

    # Pass 1 — unambiguous data-shape anchors on blank columns.
    for ci in cols:
        if grid_role[ci]:
            continue
        vals = _column_values(body, ci)
        if not vals:
            continue
        if _frac_match(vals, _looks_like_df_pair):
            override[ci] = "df_pair"
        elif _frac_match(vals, _looks_like_est_ci):
            # A leading number + its own bracketed interval, e.g.
            # "0.76 [.50, 1.02]" — a combined effect-and-CI column.
            override[ci] = "est_ci"
        elif _frac_match(vals, _looks_like_ci_only):
            override[ci] = "CI"
        elif _frac_match(vals, _looks_like_p) and any(
            _has_comparison_op(v) for v in vals
        ):
            # A p column is unambiguous only when it carries a comparison op
            # somewhere; an operator-less small-decimal column is deferred to
            # caption-token alignment below (it could be p, BF, or an effect).
            override[ci] = "p"

    # Test family — drives df-vs-n and the typing of the leading statistic
    # column. Determined from data shape + the recovered vocabulary, never from
    # bare position. df-pair ⇒ F; an effect "d/dz" column or a "t" token ⇒ t;
    # an "r" token ⇒ correlation.
    has_df_pair = "df_pair" in override.values()
    has_effect_ci = "est_ci" in override.values()
    has_d = bool(re.search(r"\bd\s*z?\b|\bd\s+or\s+d\b|cohen", vocab_text, re.I))
    has_F = bool(re.search(r"(?<![A-Za-z])F(?![A-Za-z])", vocab_text))
    has_t = bool(re.search(r"(?<![A-Za-z])t(?![A-Za-z])", vocab_text))
    has_r = bool(re.search(r"(?<![A-Za-z])r(?![A-Za-z])", vocab_text))
    if has_df_pair or (has_F and not has_t):
        family = "F"
    elif has_t or has_d or (has_effect_ci and not has_F):
        family = "t"
    elif has_r:
        family = "r"
    elif has_F:
        family = "F"
    else:
        family = None

    # Pass 2 — a lone all-integer column is df (t/F family) or n (r family).
    if family in ("t", "F", "r"):
        for ci in cols:
            if grid_role[ci] or ci in override:
                continue
            vals = _column_values(body, ci)
            if not _frac_match(vals, lambda v: bool(_BARE_INT_RE.match(v))):
                continue
            override[ci] = "n" if family == "r" else "df"

    # Pass 3 — the left-most still-blank bare-numeric column is the test
    # statistic, typed by family. Only fires when a family was established, so
    # an arbitrary number column is never labelled a statistic.
    if family in ("t", "F", "r"):
        for ci in cols:
            if grid_role[ci] or ci in override:
                continue
            vals = _column_values(body, ci)
            if _frac_match(vals, _is_num_or_na):
                override[ci] = family
                break

    # Set of column indices that carry (or will carry) a CI, for est-adjacency.
    ci_cols = {
        ci
        for ci in cols
        if grid_role[ci] in ("CI", "CI_lo", "CI_hi", "est_ci")
        or override.get(ci) in ("CI", "est_ci")
    }

    # Pass 4 — greedy left-to-right alignment of the recovered caption run to
    # the still-blank columns. Shape/family-anchored columns CONSUME their
    # matching token so the sequence stays aligned; a "CI"/"df" token is
    # consumed by the column that already owns that role rather than mis-assigned.
    if run:
        seq = list(run)

        def _consume(role_group: tuple[str, ...]) -> None:
            if seq and seq[0] in role_group:
                seq.pop(0)

        for ci in cols:
            assigned = grid_role[ci] or override.get(ci)
            if assigned:
                if assigned in ("CI", "est_ci", "CI_lo", "CI_hi"):
                    _consume(("CI",))
                elif assigned in ("df", "df1", "df2", "df_pair"):
                    _consume(("df",))
                elif assigned == "n":
                    _consume(("n",))
                elif seq and seq[0] == assigned:
                    seq.pop(0)
                continue
            # Blank, not yet anchored — take the next caption token if it names
            # a stat role we trust binding by position.
            if seq:
                tok = seq.pop(0)
                if tok in ("t", "F", "r", "p", "BF01", "eta2", "d", "M", "SD", "n", "N"):
                    override[ci] = tok
                    continue
            # No token left: a bare-number column immediately left of a CI
            # column is that interval's point estimate.
            vals = _column_values(body, ci)
            if _frac_match(vals, _is_num_or_na) and (ci + 1) in ci_cols:
                override[ci] = "est"

    # Pass 4.5 — p / df (or n) recovery for an established t/F/r results table.
    # Once the statistic column is typed (Pass 3 / grid) and the table carries a
    # recognized effect/CI column, the still-blank bare-numeric columns BETWEEN
    # the statistic and that interval are the p-value and the df/n: p is a sub-one
    # decimal (".551", "0.03", "<.001") with no integer part; df/n is a bare
    # number ≥ 1 (Welch "260.54", integer "131"). This types the operator-less p
    # that Pass 1 defers and the mixed-integer/decimal df that Pass 2 (all-integer
    # only) skips — both unambiguous HERE because position (after the statistic,
    # before the interval) pins them. Runs AFTER the caption-run pass so a leaked
    # header always wins, and BEFORE Pass 5 so a real df is not stolen as an
    # est-adjacent point estimate. Keyed on structure, never paper identity.
    # (DP-2: collabra.77859 Separate/Joint t-tests dropped p + Welch df.)
    if family in ("t", "F", "r"):
        stat_col = next(
            (ci for ci in cols if (override.get(ci) or grid_role[ci]) == family),
            None,
        )
        if stat_col is not None:
            right_bound = min(
                (
                    ci
                    for ci in cols
                    if ci > stat_col
                    and grid_role[ci] in ("est_ci", "CI", "CI_lo", "CI_hi", "est")
                ),
                default=n,
            )
            present_roles = {grid_role[ci] for ci in cols if grid_role[ci]} | set(
                override.values()
            )
            has_p = "p" in present_roles
            for ci in cols:
                if grid_role[ci] or ci in override:
                    continue
                if not (stat_col < ci < right_bound):
                    continue
                vals = _column_values(body, ci)
                if not _frac_match(vals, _is_num_or_na):
                    continue
                if not has_p and _frac_match(vals, _looks_like_sub_one):
                    override[ci] = "p"
                    has_p = True
                elif _frac_match(
                    vals,
                    lambda v: bool(_BARE_NUM_RE.match(v)) and (_parse_number(v) or 0) >= 1,
                ):
                    override[ci] = "n" if family == "r" else "df"

    # Pass 5 — final est-adjacency sweep for tables with no caption run: a
    # still-blank bare-number column immediately left of a CI column is the
    # interval's point estimate.
    for ci in cols:
        if grid_role[ci] or ci in override:
            continue
        vals = _column_values(body, ci)
        if _frac_match(vals, _is_num_or_na) and (ci + 1) in ci_cols:
            override[ci] = "est"

    # De-duplicate against the grid — a recovered role must never duplicate a
    # role the grid already recognized. A second "t"/"F"/"p"/… column collides
    # with the recognized one at value-extraction (last-write-wins) and silently
    # corrupts the real value (the chen Table 12 regression: a blank column got
    # typed "t" and overwrote the correctly-headed t). df1/df2/CI bounds legitly
    # come in pairs, so they are exempt.
    grid_roles_present = {r for r in grid_role.values() if r}
    single_roles = {
        "t", "F", "r", "chi2", "p", "df", "df_pair", "BF01", "M", "SD", "n", "N", "est",
    }
    override = {
        ci: role
        for ci, role in override.items()
        if not (role in single_roles and role in grid_roles_present)
    }

    return override


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
    roles_override: Optional[dict[int, str]] = None,
    effect_hint: Optional[str] = None,
) -> FlattenedRow:
    row_label, label_col = _pick_row_label(row)

    # Find the F-with-df regex by role name so the list-ordering can shift
    # without breaking the lookup.
    f_with_df_re = next(p for r, p in _ROLE_PATTERNS if r == "F_with_df")

    # Classify each non-label column. A `roles_override` entry (from blank-header
    # recovery) wins over the grid-header classification for that column.
    roles: dict[int, str] = {}
    df_from_header: dict[int, tuple[int, int]] = {}
    for ci, h in enumerate(header):
        if ci == label_col:
            continue
        if roles_override and ci in roles_override:
            roles[ci] = roles_override[ci]
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
        elif role == "df_pair":
            m = _DF_PAIR_RE.match(raw)
            if m:
                role_nums["df1"] = float(m.group(1))
                role_nums["df2"] = float(m.group(2))
        elif role == "CI":
            lo, hi = _parse_ci_cell(raw)
            if lo is not None and hi is not None:
                role_nums["CI_lower"] = lo
                role_nums["CI_upper"] = hi
        elif role == "est":
            # A recovered point-estimate column (its interval is a sibling CI
            # column). Bare value, no inline interval.
            est = _parse_number(raw)
            if est is None:
                est = _to_signed_float(raw)
            if est is not None:
                eff_key = _effect_key(header[ci], effect_hint)
                role_nums[eff_key] = est
                role_vals[eff_key] = raw
        elif role == "est_ci":
            # Combined estimate-and-interval cell, e.g. "-1.01% (-10.36-8.34)"
            # or "0.76 [.50, 1.02]".
            est = _parse_leading_number(raw)
            if est is not None:
                eff_key = _effect_key(header[ci], effect_hint)
                role_nums[eff_key] = est
                role_vals[eff_key] = (
                    re.split(r"[\[(]", raw, maxsplit=1)[0].strip() or _fmt_num(est)
                )
                if eff_key == "est":
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

    # Validity guards — a parsed value that violates a statistic's domain is
    # garbage, not data. Drop it (and its sentence part) rather than emit an
    # impossible field. Universal: an invalid statistic is wrong wherever it
    # comes from, recovered or grid-classified ("never display garbage").
    if "r" in role_nums and not (-1.0 <= role_nums["r"] <= 1.0):
        role_nums.pop("r")
        role_vals.pop("r", None)
    if "p" in role_nums and not (0.0 <= role_nums["p"] <= 1.0):
        role_nums.pop("p")
        role_vals.pop("p", None)
        role_vals.pop("p_op", None)
    for k in ("n", "N"):
        if k in role_nums and (role_nums[k] <= 0 or role_nums[k] != int(role_nums[k])):
            role_nums.pop(k)
            role_vals.pop(k, None)
    if (
        "CI_lower" in role_nums
        and "CI_upper" in role_nums
        and role_nums["CI_lower"] > role_nums["CI_upper"]
    ):
        role_nums.pop("CI_lower")
        role_nums.pop("CI_upper")
        role_vals.pop("CI", None)

    fields: dict[str, object] = {}
    if group:
        fields["group"] = group
    for k in ("t", "F", "chi2", "r", "d", "eta2", "M", "SD", "est", "BF01"):
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
        est_label = role_vals.get("est_label", "") or "estimate"
        est_txt = role_vals.get("est", _fmt_num(role_nums["est"]))
        parts.append(f"{est_label} = {est_txt}")

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
    if "BF01" in role_nums:
        parts.append(f"BF01 = {role_vals['BF01']}")

    if "CI_lower" in role_nums and "CI_upper" in role_nums:
        if "CI" in role_vals:
            # The raw CI cell may already carry its own brackets/parens —
            # strip them so the sentence renders one set, not "[[...]]".
            ci_txt = role_vals["CI"].strip().strip("[]()").strip()
            parts.append(f"95% CI [{ci_txt}]")
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
    n = len(header)

    # The sentinel marks where camelot PLACED each super-label — but a *centered*
    # spanning label (colspan is lost in stream extraction) lands mid-span, not at
    # its arm's first column, so trusting the sentinel as the arm boundary
    # mis-bins columns: collabra.90203 T10 puts the Target-article "r" into the
    # label region, and xiao_2021 T4 splits Original/Replication with the F values
    # swapped. Re-derive arm boundaries from EQUAL-WIDTH blocks of the data region
    # (the columns between the leading + trailing non-stat label columns), each of
    # which must contain exactly one super-label. Falls back to the literal
    # sentinel boundaries when the region does not divide evenly — so every
    # previously-grouped table stays byte-identical unless this strictly corrects
    # its alignment (a left-aligned super-header already at the block start yields
    # the identical grouping). General, keyed on structure, not paper id. (DP-5.)
    def _is_label_col(i: int) -> bool:
        return i not in starts and not _classify_column(header[i])

    lead = 0
    while lead < n and _is_label_col(lead):
        lead += 1
    trail = n - 1
    while trail >= 0 and _is_label_col(trail):
        trail -= 1
    width = trail - lead + 1
    k = len(starts)
    if (
        width >= k
        and width % k == 0
        and lead <= starts[0]
        and starts[-1] <= trail
    ):
        block = width // k
        blocks = [(lead + j * block, lead + (j + 1) * block - 1) for j in range(k)]
        if all(b_lo <= s <= b_hi for (b_lo, b_hi), s in zip(blocks, starts)):
            label_cols = [i for i in range(n) if i < blocks[0][0] or i > blocks[-1][1]]
            groups = [
                (
                    (header[s].split(_MERGE_SEPARATOR, 1)[0]).strip(),
                    list(range(b_lo, b_hi + 1)),
                )
                for (b_lo, b_hi), s in zip(blocks, starts)
            ]
            return label_cols, groups

    # Fallback: literal sentinel-boundary grouping (pre-existing behavior).
    label_cols = list(range(0, starts[0]))
    groups = []
    for gi, start in enumerate(starts):
        end = starts[gi + 1] if gi + 1 < len(starts) else n
        glabel = (header[start].split(_MERGE_SEPARATOR, 1)[0]).strip()
        groups.append((glabel, list(range(start, end))))
    return label_cols, groups


# A single statistic value-group: either a signed number with an optional
# ``(SD)`` and/or bracketed ``[CI]`` suffix, OR a standalone bracketed interval
# (a packed CI column whose cells are ``"[−0.48, 0.15] [−0.20, 0.34]"`` — no
# leading point estimate). Used to split a packed parallel-arm cell into one
# value per arm. The number branch is tried first so ``".07 [-.17,.31]"`` stays
# a single group rather than splitting the estimate from its interval.
_VALUE_GROUP_RE = re.compile(
    r"(?:"
    r"[+\-−]?(?:\d+\.?\d*|\.\d+)"  # signed number
    r"(?:\s*\([^)]*\))?"  # optional (SD)
    r"(?:\s*\[[^\]]*\])?"  # optional [CI]
    r"|"
    r"\[[^\]]*\]"  # OR a standalone bracketed interval
    r")"
)


def _split_value_groups(cell: str, k: int) -> Optional[list[str]]:
    """Split a packed multi-arm cell into EXACTLY ``k`` value-groups.

    A value-group is a number with an optional ``(SD)`` and/or ``[CI]`` suffix
    (``"4.76 (1.14)"``, ``".07 [-.17,.31]"``, ``"260.54"``). Returns the ``k``
    groups when the cell yields exactly ``k`` of them AND they cover the bulk of
    the cell's non-space characters; otherwise ``None`` so a cell that does not
    hold one value per arm is left intact rather than mis-split."""
    s = (cell or "").strip()
    if not s:
        return None
    groups = [
        m.group(0).strip() for m in _VALUE_GROUP_RE.finditer(s) if m.group(0).strip()
    ]
    if len(groups) != k:
        return None
    nospace = lambda x: re.sub(r"\s", "", x)  # noqa: E731
    if len("".join(nospace(g) for g in groups)) < 0.8 * len(nospace(s)):
        return None
    return groups


def _detect_packed_arms(
    header: list[str], body: list[list[str]]
) -> Optional[tuple[int, list[str]]]:
    """Detect a table whose parallel arms are packed into single cells.

    The Request-11 "Separate/Joint" shape: one arm-label column repeats the SAME
    ``k≥2`` arm names on every data row (``"Separate Joint"``) and the other data
    cells each pack ``k`` space-joined values, one per arm. This is distinct from
    `_detect_column_groups` (arms in *separate* columns via a folded super-header)
    — here every column holds all arms at once.

    Returns ``(arm_label_col, [arm_labels...])`` or ``None``. Keyed purely on the
    structural signature (a constant multi-token alpha label column + ≥2 cleanly
    ``k``-splittable data columns), so ordinary single-arm tables are untouched
    and stay byte-identical to the pre-existing path."""
    # Fold the super-header sentinel down to spaces first: a packed arm-label
    # column reads ``"Separate\x00BR\x00Joint"`` raw, and packed data cells are
    # likewise sentinel-joined. `_is_data_row` can't see numbers inside a packed
    # cell, so identify data rows by "≥2 cells containing a digit" instead.
    rows = [[_strip_fold_sentinels(c or "") for c in r] for r in body]
    data = [r for r in rows if sum(1 for c in r if re.search(r"\d", c)) >= 2]
    if len(data) < 2:
        return None
    n = max(len(r) for r in data)
    for a in range(n):
        vals = [(r[a].strip() if a < len(r) else "") for r in data]
        if any(not v for v in vals) or len(set(vals)) != 1:
            continue  # not a column that repeats one constant arm-label string
        toks = vals[0].split()
        k = len(toks)
        if not (2 <= k <= 4):
            continue
        if not all(re.fullmatch(r"[A-Za-z][A-Za-z.\-]*", t) for t in toks):
            continue  # arm labels are alphabetic words ("Separate", "Joint")
        splittable = sum(
            1
            for ci in range(n)
            if ci != a
            and (cv := _column_values(data, ci))
            and all(_split_value_groups(v, k) is not None for v in cv)
        )
        if splittable >= 2:
            return a, toks
    return None


def _flatten_packed_arms(
    table_id: str,
    page: int,
    label: Optional[str],
    header: list[str],
    body: list[list[str]],
    packed: tuple[int, list[str]],
    *,
    caption: Optional[str],
    footnote: Optional[str],
    vocab_all: str,
    effect_hint: Optional[str],
    n_cols: int,
) -> list[FlattenedRow]:
    """Emit one `FlattenedRow` per (body row × arm) for a packed-arm table.

    Each kept (non-arm-label) cell is split into its ``k`` per-arm values via
    `_split_value_groups`; cells that do not split (the DV label, blanks) are
    replicated across arms. Roles for blank stat columns are recovered on the
    SPLIT (single-value) shape, then the existing `_flatten_one_row` machinery
    types and assembles each arm exactly as for a normal row, tagging the arm
    via ``group=`` so Separate/Joint stay distinguishable."""
    arm_col, arm_labels = packed
    k = len(arm_labels)
    keep_cols = [ci for ci in range(n_cols) if ci != arm_col]
    sub_header = [
        _strip_fold_sentinels(header[ci]) if ci < len(header) else "" for ci in keep_cols
    ]

    emit: list[tuple[int, str, list[str]]] = []
    all_sub_rows: list[list[str]] = []
    for row_idx, row in enumerate(body):
        if _is_group_separator(row, n_cols):
            continue
        row = (list(row) + [""] * (n_cols - len(row)))[:n_cols]
        per_arm: list[list[str]] = [[] for _ in range(k)]
        for ci in keep_cols:
            cell = _strip_fold_sentinels(row[ci] or "").strip()
            groups = _split_value_groups(cell, k)
            for j in range(k):
                per_arm[j].append(groups[j] if groups is not None else cell)
        for j in range(k):
            all_sub_rows.append(per_arm[j])
            emit.append((row_idx, arm_labels[j], per_arm[j]))

    recovered: Optional[dict[int, str]] = None
    if all_sub_rows:
        lbl_col = _table_label_col(all_sub_rows, len(sub_header))
        recovered = (
            _recover_blank_roles(
                sub_header,
                all_sub_rows,
                lbl_col,
                caption,
                footnote,
                extra_vocab=vocab_all,
            )
            or None
        )

    out: list[FlattenedRow] = []
    for row_idx, glabel, sub_row in emit:
        out.append(
            _flatten_one_row(
                table_id,
                page,
                label,
                row_idx,
                sub_header,
                sub_row,
                group=glabel,
                roles_override=recovered,
                effect_hint=effect_hint,
            )
        )
    return out


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

    # Blank-header column-role recovery (non-grouped tables only — grouped
    # tables already resolve roles per arm). When the grid header leaves stat
    # columns unlabeled, recover their roles from data shape + caption/footnote
    # vocabulary so `fields` get populated instead of dropped.
    # Effect-type hint from the whole-table vocabulary (all header rows +
    # caption + footnote) — used to type a recovered estimate column (e.g.
    # a blank "d or dz [95% CI]" column ⇒ key `d`). Header text on the column
    # itself still wins; this only fills in when the column header is blank.
    vocab_all = " ".join(
        [" ".join(hr) for hr in header_rows]
        + [table.get("caption") or "", table.get("footnote") or ""]
    )
    effect_hint = _effect_type_for(vocab_all)

    # Packed parallel-arm table (Separate/Joint values space-joined inside each
    # cell). Detected only when there are no column-groups; handled by its own
    # split-then-flatten path so each arm becomes its own typed record.
    packed = _detect_packed_arms(header, body) if grouped is None else None
    if packed is not None:
        return _flatten_packed_arms(
            table_id,
            page,
            label,
            header,
            body,
            packed,
            caption=table.get("caption"),
            footnote=table.get("footnote"),
            vocab_all=vocab_all,
            effect_hint=effect_hint,
            n_cols=len(header),
        )

    roles_override: Optional[dict[int, str]] = None
    if grouped is None:
        n_cols0 = len(header)
        data_rows = [
            (list(r) + [""] * (n_cols0 - len(r)))[:n_cols0]
            for r in body
            if _is_data_row(r)
        ]
        if data_rows:
            lbl_col = _table_label_col(data_rows, n_cols0)
            recovered = _recover_blank_roles(
                header, data_rows, lbl_col,
                table.get("caption"), table.get("footnote"),
                extra_vocab=vocab_all,
            )
            roles_override = recovered or None

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
            out.append(
                _flatten_one_row(
                    table_id, page, label, row_idx, header, row,
                    roles_override=roles_override,
                    effect_hint=effect_hint,
                )
            )
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
                    table_id, page, label, row_idx, sub_header, sub_row,
                    group=glabel, effect_hint=effect_hint,
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
