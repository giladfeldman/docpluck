"""Cell-cleaning pipeline for academic-table cell grids.

Ported from the 2026-05 splice spike (an internal design doc
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
v2.3.0 spec (`an internal handoff doc (2026-05-11)`).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Sequence

from docpluck.telemetry import record_fallback

if TYPE_CHECKING:  # `Cell` is a TypedDict used only in annotations here
    from . import Cell

from docpluck.normalize import (
    decompose_ligatures,
    destyle_math_alphanumeric,
    recover_corrupted_lt_operator,
    recover_lt_as_b_operator,
    recover_corrupted_minus_signs,
    recover_dropped_minus_ci_upper,
    recover_dropped_minus_ci_upper_in_text,
    recover_pua_glyphs,
    recover_times_interaction_glyph,
)


_MERGE_SEPARATOR = "\x00BR\x00"  # placeholder swapped to <br> after escaping
_SUP_OPEN = "\x00SUP\x00"  # placeholder swapped to <sup> after escaping
_SUP_CLOSE = "\x00/SUP\x00"  # placeholder swapped to </sup> after escaping


# ── W0r: the UNMAPPED-GLYPH MINUS, in BOTH representations (v2.4.139) ────────
#
# RASTER-VERIFIED, and it is OURS: the page is correct and our extraction is not,
# so it falls under the ONE EXCEPTION to the separation-of-duties directive.
# `10.1016/j.joep.2020.102350` p2 Table 1 PRINTS `Cramer's V = 0.067
# [−0.108, 0.218]` — an interval that SPANS zero — and docpluck shipped
# `<td>[\x00 0.108, 0.218]</td>`, which every consumer reads as one that
# EXCLUDES zero. p4 Table 2 PRINTS the row `199  −1  −31  −30  213  14  31  17`
# and docpluck shipped the three SIGNED values unsigned while the three unsigned
# values in the same row survived — the row carries its own two-sided control.
# Both pages were rasterized at 200dpi and read (2026-09-02).
#
# WHY THE REPAIR THAT ALREADY EXISTED COULD NOT FIRE. Until now this was a bare
# `re.sub(r"\(cid:0\)\s*(?=\d)", "-", s)`, keyed on the seven-character literal
# pdfminer.six emits for a glyph it cannot map. **Camelot 2.0.0 does not use
# pdfminer.six.** It reads text through `playa.miner` (`camelot/utils.py`
# imports `LAParams`/`LTChar` from `playa.miner`), and playa's `Font.decode`
# falls back to an IDENTITY map — `((cid, chr(cid)) for cid in data)` — so the
# same unmappable character code 0 arrives as a raw U+0000 instead. Measured on
# the paper above, and the two readers disagree on the SAME file:
#
#     camelot.read_pdf(page 4, flavor="stream") : 21 cells carry \x00, 0 carry "(cid:0)"
#     pdfplumber (pdfminer.six) whole document  :  0 chars are \x00, 31 are "(cid:0)"
#
# So the literal-keyed repair became a green-shaped no-op the day the table
# backend changed, and nothing failed. Both spellings are recovered here for
# exactly that reason: a repair keyed on one library's spelling of "I could not
# decode this" is one dependency bump away from silently doing nothing.
#
# WHY BEFORE-A-DIGIT IS THE SIGNATURE. A NUL is never legitimate text, and the
# glyph the code-0 slot draws in these AdvTT-family stat tables is U+2212 — the
# same broken-ToUnicode font family behind W0b/W0h/W0m/W0o. `\x00 0.23` is the CI
# bound -0.23; `\x00 31` is -31. This is TYPOGRAPHIC evidence (what the renderer
# emitted for a specific character), never inferential: nothing here reasons
# about what the number OUGHT to be. A NUL that is NOT before a digit is left
# alone — its glyph is unknown, and inventing one is the hypothetical this
# project forbids.
#
# PREVALENCE, MEASURED SEPARATELY FROM THE SHAPE, because one paper proves a
# shape exists and says nothing about a rate (`tools/diag/unmapped_glyph_prevalence_scan.py`,
# 200 papers sampled from the article repository via the custodian, 2026-09-02):
#
#     3 / 200 papers (1.5%) carry the repairable shape, 86 sites
#     5 / 200 carry an unmapped glyph NOT before a digit (21 sites) — untouched here
#     1 / 200 carries U+FFFD (11 sites) — a different marker, not handled by this rule
#
# So this is a real but uncommon publisher-font failure, unlike W0o's 10.5%.
#
# ── AND THE FALSE-POSITIVE CLASS THAT SWEEP FOUND, WHICH ONE PAPER COULD NOT ──
#
# **The code-0 slot is not a minus everywhere. It is whatever THAT font left
# unmapped.** `10.1017/s1930297500007956` uses it for an EXTENSIBLE OPENING
# PARENTHESIS, with code 1 as its closing partner. RASTERIZED at 170dpi and read:
# p17 prints `y_i ~ Gaussian((μ1, μ2), [ … ]^-1)`, and playa yields
# `Gaussian \x00\n(μ1, μ2) , … \x01`. On that paper's DECODED TEXT the ungated
# rule fires 25 times and every one would MANUFACTURE a minus sign that is not on
# the page — data loss turned into data fabrication. Rendering it with the repair
# on and off gives byte-identical markdown, so on THAT paper none of the 25 reach
# a `<td>`; the gate closes a fabrication possible BY CONSTRUCTION rather than one
# observed shipping, and it is still required, because this is the single repair
# chain behind `flatten`, `cells[].text`, `raw_text` and the rendered `<table>`
# alike. Two independent discriminators separate the classes perfectly across
# every affected paper in the sample:
#
#     paper                        C0 codes present    NUL->digit same line / across a newline
#     10.1016/j.joep.2020.102350   {0x00: 31}                31 / 0     minus  (raster-verified)
#     10.1016/j.jesp.2025.104750   {0x00: 46}                44 / 0     minus
#     10.1016/j.jesp.2021.104226   {0x00: 17}                17 / 0     minus
#     10.1017/s1930297500007956    {0x00: 33, 0x01: 33, …}    0 / 25    DELIMITER (raster-verified)
#
# The delimiter paper's NUL count is matched EXACTLY by a code-1 count — an
# opening/closing pair — and not one of its sites sits on the same line as its
# digits, because an extensible delimiter is its own layout element while a minus
# is glued to its number. Both signals are typographic, and both are required:
#   * a partner code rules the class out inside a CELL, where whitespace has been
#     collapsed and the newline signal no longer exists;
#   * the same-line requirement rules it out in any raw text, where a partner may
#     have been split into a neighbouring cell.
# Where either says this font's unmapped slots are being used for something other
# than a minus, the text passes through untouched.
#
# THE TRAP, and why the repair is segment-scoped rather than one `re.sub`.
# `\x00` is ALSO docpluck's own placeholder character (`_MERGE_SEPARATOR`,
# `_SUP_OPEN`, `_SUP_CLOSE` above), and `clean_cell_text` runs a SECOND time
# from `_html_escape`, by which point those placeholders are present. A folded
# header puts a DIGIT immediately after a closing placeholder NUL —
# `"Replication\x00BR\x0095% CI"` — so a naive `\x00\s*(?=\d)` would destroy the
# fold AND inject a minus that was never printed, turning data loss into data
# FABRICATION. Nor is a generic `\x00[^\x00]*\x00` "placeholder span" safe: on a
# merged cell `"\x00 1" + _MERGE_SEPARATOR + "\x00 31"` it matches `"\x00 1\x00"`
# and protects a real minus from repair. The placeholders are therefore matched
# by their EXACT spellings, derived from the constants above so the two cannot
# drift, and the repair runs only on the text BETWEEN them.
_CELL_PLACEHOLDER_RE = re.compile(
    "|".join(re.escape(p) for p in (_MERGE_SEPARATOR, _SUP_OPEN, _SUP_CLOSE))
)
# The marker, then SPACES OR TABS ONLY, then a digit. Deliberately not `\s*`:
# `\s` matches a newline, and matching across one is exactly how the extensible
# -delimiter class above gets mistaken for a minus.
_UNMAPPED_MINUS_RE = re.compile(r"(?:\(cid:0\)|\x00)[ \t]*(?=\d)")
# Evidence that THIS font's unmapped slots are carrying something other than a
# minus: a second undecoded code point (the code-1 closing partner of an
# extensible parenthesis, and any other C0 control the backend passed through),
# or pdfminer's spelling of an unmapped code that is not 0. Tab, newline, form
# feed and carriage return are legitimate layout characters and are excluded.
_OTHER_UNMAPPED_SLOT_RE = re.compile(r"[\x01-\x08\x0b\x0e-\x1f]|\(cid:(?!0\))\d+\)")


def recover_unmapped_glyph_minus(s: str) -> str:
    """W0r: recover a minus sign the table backend could not map to Unicode.

    ``"(cid:0) 31"`` (pdfminer.six) and ``"\\x00 31"`` (playa, via Camelot 2.0)
    are the same defect wearing two spellings; both become ``-31``. Normalised
    to ASCII hyphen per CLAUDE.md hard rule 4.

    Passes the text through untouched when the marker is separated from its
    digit by a newline, or when the text carries a SECOND undecoded slot — both
    are the signature of a font using the code-0 slot for an extensible
    parenthesis rather than a minus, which is raster-verified on
    ``10.1017/s1930297500007956`` and would otherwise fabricate 25 minus signs
    that are not on the page.

    Never rewrites docpluck's own ``\\x00BR\\x00`` / ``\\x00SUP\\x00`` /
    ``\\x00/SUP\\x00`` placeholders, which is why this is not a single
    ``re.sub``: ``clean_cell_text`` runs again from :func:`_html_escape` after
    those exist. Idempotent, as :func:`clean_cell_text` requires.
    """
    if not s or ("\x00" not in s and "(cid:0)" not in s):
        return s
    out: list[str] = []
    pos = 0
    for m in _CELL_PLACEHOLDER_RE.finditer(s):
        out.append(s[pos:m.start()])
        out.append(m.group(0))
        pos = m.end()
    out.append(s[pos:])
    # The guard is evaluated on the text BETWEEN the placeholders, never on the
    # placeholders themselves — their own NULs are docpluck's, not the font's.
    body = "".join(out[::2])
    if _OTHER_UNMAPPED_SLOT_RE.search(body):
        return s
    return "".join(
        _UNMAPPED_MINUS_RE.sub("-", part) if i % 2 == 0 else part
        for i, part in enumerate(out)
    )


def clean_cell_text(s: str | None) -> str:
    """Every glyph repair a table cell needs — and NOTHING about HTML.

    **This is the canonical repair chain for the table-cell channel.** It was
    extracted from ``_html_escape`` on 2026-08-15 because fusing the repairs
    into the HTML escaper made them reachable *only* by the HTML path, so one
    input gave two answers depending on which consumer asked:

        cell text ``"[20.45, 20.06]"`` (a `2`-for-U+2212 corrupted CI)
          ``cells_to_html``            -> ``[-0.45, -0.06]``   repaired
          ``flatten._cells_to_grid``   -> ``[20.45, 20.06]``   RAW
          ``Table["cells"][i]["text"]``-> ``[20.45, 20.06]``   RAW
          ``Table["raw_text"]``        -> ``[20.45, 20.06]``   RAW

    ``flatten`` is production (``cli.py``, ``render.py``), and it feeds the
    JSONL sidecar — so a p-value that renders correctly in the HTML table was
    simultaneously being shipped corrupt to every structured consumer. That is
    the ONE CONCEPT, ONE TABLE rule's exact failure mode: a library that can
    convert one input two ways has no contract at all.

    Applied once per cell by :func:`repair_cells`, rather than at each consumer:
    the cleaning pipeline merges and splits cells, so cell↔position
    correspondence degrades as the pipeline runs, and a repair keyed on cell
    content must happen while the cell still is what the capture emitted.

    **v2.4.133 first placed that call at cell CONSTRUCTION, and that was wrong
    for a reason worth keeping written down**: the capture paths run their
    structural gates on the cells they have just built, so repairing at
    construction silently changed what those gates judge — and a correct
    `×`-as-`3` repair began deleting the rows below it. The call now sits after
    the gates. See :func:`repair_cells` and `whitespace._repaired_view`.

    MUST BE IDEMPOTENT — ``_html_escape`` still calls it, so a constructed cell
    is cleaned twice. Pinned by ``test_clean_cell_text_is_idempotent``.
    """
    if s is None:
        return ""
    # Strip math-alphanumeric styling (𝜂->η, 𝛽->β, 𝐴->A) — table cells come
    # from the Camelot layout channel and bypass normalize_text's S0 step, so
    # math-italic Greek would otherwise leak raw into rendered table HTML.
    s = destyle_math_alphanumeric(s)
    # Decompose Latin typographic ligatures (ﬁ->fi, ﬂ->fl, …) — table cells
    # bypass normalize_text, so a cell "conﬁdent" would otherwise leak the
    # raw presentation-form glyph into the rendered HTML (v2.4.44).
    s = decompose_ligatures(s)
    # Recover Adobe-Symbol-font glyphs surfaced as PUA codepoints (β->U+F062,
    # chi->U+F063, bullet->U+F0B7). Table cells come from the Camelot layout
    # channel and bypass normalize_text's W0e step, so a Symbol-PUA glyph
    # would otherwise leak raw into rendered table HTML (v2.4.54).
    s = recover_pua_glyphs(s)
    # W0r: recover a minus the table backend could not map to Unicode. Camelot's
    # text layer emits an unmappable glyph as "(cid:0)" (pdfminer.six) or as a
    # raw "\x00" (playa, Camelot 2.0) — the same defect, two spellings, and
    # keying on only the first made this a no-op for as long as Camelot 2.0 has
    # been installed. Placeholder-safe by construction; see the rule above.
    s = recover_unmapped_glyph_minus(s)
    # Recover '2'-for-U+2212 minus corruption in a CI cell — "[20.45, 20.06]"
    # is the descending (impossible) bracket for "[-0.45, -0.06]". Same
    # self-gating descending-bracket rule as normalize.py's W0b step; table
    # cells bypass W0b (Camelot layout channel).
    s = recover_corrupted_minus_signs(s)
    # Recover '<'-as-backslash corruption — pdftotext/pdfminer map the '<'
    # glyph to a literal backslash on some fonts, so a p-value cell "<.001"
    # arrives as "\.001". Must run BEFORE the "<"->"&lt;" escape below so the
    # recovered operator is HTML-escaped like any other "<". Same shared
    # helper as normalize.py's W0c step (table cells bypass W0c).
    s = recover_corrupted_lt_operator(s)
    # W0o: same class as W0c, different glyph ('<' extracted as 'b').
    s = recover_lt_as_b_operator(s)
    # Recover '×'-as-'3' corruption in an interaction-term predictor cell —
    # "Direction 3 manipulated attribute" is "Direction × manipulated attribute"
    # (same AdvPS… broken-ToUnicode font as the '2'-for-minus / '<'-as-backslash
    # corruptions above). TABLE-CELL ONLY (W0i): a bare '3' between words is
    # ambiguous in prose ("Table 3 summarizes", "osf.io/pg3ae"), so this never
    # runs in normalize_text or the whole-markdown post-process — only here,
    # where the cell is a Camelot predictor label. Self-guards a genuine ordinal
    # after a reference word (Model/Study/Wave/…). v2.4.103 / GLYPH.
    s = recover_times_interaction_glyph(s)
    # Recover a CI UPPER bound whose leading minus pdftotext/Camelot dropped or
    # detached into a stray en-dash — a same-cell "<estimate> ... [lo, hi]"
    # correlation cell ("−.73***\x00BR\x00[−0.78,  –  0.67] (−0.72)") where the
    # upper bound's minus is lost so a negative interval reads positive. Keyed on
    # the estimate-containment invariant; self-guards a legitimate zero-straddling
    # CI. W0g/W0h (normalize body) trust the bracket, so this minus dropped from
    # the bracket ITSELF is recovered here for the table channel (B7 / GLYPH,
    # v2.4.100). The merge-separator placeholders are still present, so the
    # decoration span matches across a "\x00BR\x00" wrap.
    s = recover_dropped_minus_ci_upper_in_text(s)
    return s


_CELL_WHITESPACE_RE = re.compile(r"\s+")


def normalize_cell_whitespace(text: str) -> str:
    """Canonicalise a freshly-clustered cell's whitespace — and NOTHING else.

    Soft hyphen dropped, U+2212 folded to ASCII hyphen (CLAUDE.md hard rule 4),
    whitespace runs collapsed. Deliberately NOT a glyph repair: the capture paths
    run their structural gates on the text this returns, and repairing before a
    gate is what deleted rows in v2.4.133. :func:`repair_cells` is the repair.

    One definition, three capture paths. This existed verbatim in
    `whitespace.py` AND `cluster.py`, which is the one-concept-one-table rule's
    failure mode sitting one wiring change away from mattering.
    """
    text = (text or "").replace("­", "")   # soft hyphen
    text = text.replace("−", "-")          # unicode minus -> ASCII hyphen
    return _CELL_WHITESPACE_RE.sub(" ", text).strip()


def repair_cells(cells: "list[Cell]") -> "list[Cell]":
    """Apply :func:`clean_cell_text` to every cell — the LAST step before emission.

    **Where a capture path calls this is load-bearing, not a detail.** It must run
    AFTER the structural gates and BEFORE the return:

      * after the gates, so a repair can never change which rows survive. When
        v2.4.133 repaired at cell CONSTRUCTION instead, the region-path gates
        began judging repaired text and a correct `×`-as-`3` repair started
        deleting the rows below it (register R4);
      * before the return, so `flatten`, `cells[].text`, `raw_text` and the
        rendered `<table>` all carry the same text (register F7a).

    Lives here rather than in either capture module so the two paths cannot
    diverge on what "repaired" means — the one-concept-one-table rule applied to
    the seam that broke it last time. Mutates in place and returns the same list.
    """
    for c in cells:
        c["text"] = clean_cell_text(c.get("text") or "")
    return cells


def _html_escape(s: str | None, clean=None) -> str:
    """Repair, then escape HTML special characters for safe inclusion in cell
    content, then convert merge-separator placeholders to ``<br>`` and
    superscript placeholders to ``<sup>``/``</sup>``.

    The repairs live in :func:`clean_cell_text`. This function is kept as the
    HTML-path entry point so grids that never went through cell construction
    (the whitespace fallback, the isolated path, tests) still get repaired —
    removing the repairs from here would silently strip them from those paths.
    ``clean_cell_text`` is idempotent, so the double application is a no-op.

    ``clean`` SELECTS the repair chain; it does not add a second one. Default is
    the PDF chain, so every existing caller is byte-identical. The DOCX table
    path passes its own, because **this function was silently applying the PDF
    glyph repairs to DOCX cells** (v2.4.140): `docx_tables` cleaned each cell
    with the DOCX chain at construction and then handed the grid to
    ``cells_to_html``, which re-cleaned it here with the PDF chain. Measured:
    a DOCX cell reading ``[20.45, 20.06]`` came back as ``cells[].text ==
    "[20.45, 20.06]"`` and ``html == "[-0.45, -0.06]"`` — **two minus signs the
    document does not contain, in one of the two fields, for one input.** That
    is both the fabrication class this project ranks worst and the "one concept,
    one table" failure: a library that answers one input two ways has no
    contract. `docx_tables`'s own docstring claimed the PDF chain was excluded;
    it was excluded from the cells and not from the HTML. Found 2026-09-05 by
    the Sol and Grok seats of the release consult round (Sonnet missed it and
    filed an explicit all-clear on the same question — a wrong reject).
    """
    s = (clean or clean_cell_text)(s)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace(_MERGE_SEPARATOR, "<br>")
        .replace(_SUP_OPEN, "<sup>")
        .replace(_SUP_CLOSE, "</sup>")
    )


# A cell holding ONLY a CI bracket: "[−0.78, −0.67]", "[−0.52,  0.33]",
# "[−0.78,  –  0.67]" (detached en-dash on the upper bound). Groups: (1) lo
# sign+magnitude, (2) detached dash run before hi, (3) hi attached sign, (4) hi
# magnitude. Sign chars accept ASCII hyphen AND U+2212; the detached separator
# also accepts en/em dash. Anchored end-to-end so a combined estimate+CI cell
# does not match (that path is handled by recover_dropped_minus_ci_upper_in_text).
_CI_BRACKET_CELL_RE = re.compile(
    r"^\s*\[\s*([-−]?\s*\d*\.\d+)\s*,"
    r"\s*([-−–—]\s+)?([-−]?)(\d*\.\d+)\s*\]\s*$"
)
# A cell stating a signed point estimate: "r = -.73", "−.32", "d = -0.43",
# "-.43". The leading label (r/d/β/…) is optional; what matters is a signed
# decimal that is the cell's principal value.
_EST_CELL_RE = re.compile(
    r"^\s*(?:[A-Za-zβΒ]+\s*=\s*)?([-−])\s*(\d*\.\d+)\s*$"
)


def _recover_ci_upper_in_grid_row(row: list[str]) -> list[str]:
    """Recover a dropped/detached minus on a CI UPPER bound when the estimate
    and the CI live in SEPARATE cells of the same row (the region-driven grid
    shape: ``… <td>r = -.73</td> <td>[−0.78,  –  0.67]</td> …``). For each
    CI-bracket cell, the nearest signed-estimate cell to its LEFT in the same
    row anchors the estimate-containment invariant
    (``recover_dropped_minus_ci_upper``); on a flip the bracket cell is
    rewritten with a single minus on the upper bound. The same-cell shape
    (estimate+CI mashed in one cell) is handled separately by
    ``recover_dropped_minus_ci_upper_in_text`` in ``_html_escape``. No-op when a
    row has no estimate-anchored bracket cell."""
    # Pre-scan the row for signed point estimates (cell index -> value).
    est_at: dict[int, float] = {}
    for i, cell in enumerate(row):
        m = _EST_CELL_RE.match(cell or "")
        if m:
            try:
                est_at[i] = float(("-" if m.group(1) in ("-", "−") else "") + m.group(2))
            except ValueError:
                pass
    if not est_at:
        return row
    out = list(row)
    for j, cell in enumerate(row):
        m = _CI_BRACKET_CELL_RE.match(cell or "")
        if not m:
            continue
        # Nearest estimate cell to the LEFT (correlation grids place the
        # estimate immediately before its CI within the same arm).
        left_est_idx = [k for k in est_at if k < j]
        if not left_est_idx:
            continue
        est = est_at[max(left_est_idx)]
        try:
            lo = float(m.group(1).replace("−", "-").replace(" ", ""))
            attached = m.group(3) or ""
            hi_signed = ("-" if attached in ("-", "−") else "") + m.group(4)
            hi = float(hi_signed)
        except ValueError:
            continue
        fixed_hi = recover_dropped_minus_ci_upper(est, lo, hi)
        if fixed_hi is None:
            continue
        lo_txt = re.sub(r"\s+", "", m.group(1))
        minus = "−" if lo_txt.startswith("−") else "-"
        out[j] = f"[{lo_txt}, {minus}{m.group(4)}]"
    return out


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

    # v2.4.27 (cycle 12): detect "section-row label" pattern — a row
    # with only ONE non-empty cell containing a noun-phrase + a
    # parenthesized descriptor (often n / M / SD breakdown). These are
    # spanning section labels within the table body (e.g. xiao Table 6's
    # ``Regret-Salient (n = 331, 5 selected the decoy, 1.5%)``) and
    # must NOT be merged into the prior data row. See HANDOFF
    # 2026-05-14 item C.
    _SECTION_ROW_LABEL_RE = re.compile(
        r"^[A-Z][\w\-]*(?:\s+[\w\-]+)*\s*\([^)]*\b(?:n|N|M|SD|p)\s*[=<>]"
    )

    def _is_section_row_label(row: list[str]) -> bool:
        non_empty = [(i, (c or "").strip()) for i, c in enumerate(row)]
        non_empty = [(i, s) for i, s in non_empty if s]
        if len(non_empty) != 1:
            return False
        _, content = non_empty[0]
        if len(content) > 200:
            return False
        return bool(_SECTION_ROW_LABEL_RE.match(content))

    # v2.4.94 (Tier-2): numeric / parenthetical continuation rows. Camelot
    # STREAM splits a stacked data cell across two physical rows — the value on
    # one row ("86", "-1.01% (-10.36-") and its parenthetical / CI-upper-bound
    # tail on the next ("(87.8%)", "8.34)", "(mean SD)†"). The prose-merge
    # branch above only fires for multi-WORD wraps, so these short numeric
    # fragments fell through as junk rows. Detect a row whose every non-empty
    # cell is a *fragment* (opens with "(" or is a bare close-paren tail) AND
    # whose every non-empty column is also populated in the parent row, then
    # fold each fragment back into the parent's same-column cell. Gated on the
    # column-alignment so an independent parenthetical row can't be absorbed
    # into an unrelated parent.
    def _is_fragment_cell(s: str) -> bool:
        s = (s or "").strip()
        if not s:
            return True  # empty cells don't disqualify the row
        if s.startswith("("):
            return True
        if ")" in s and "(" not in s:  # close-paren tail: "8.34)", "10.28)"
            return True
        # Close-bracket tail of a CI split across two rows: "[0.59," wraps and
        # its upper bound "0.73]" lands on the next row (cog_emo Table 8 — the
        # bracketed CI form, not the parenthetical one above). The parent cell
        # ends with "," so the fragment joins after a space → "[0.59, 0.73]".
        if "]" in s and "[" not in s:  # close-bracket tail: "0.73]", "−0.66]"
            return True
        return False

    def _is_fragment_continuation(row: list[str], parent: list[str]) -> bool:
        nz = [(i, (c or "").strip()) for i, c in enumerate(row)]
        nz = [(i, s) for i, s in nz if s]
        if not nz:
            return False
        if not all(_is_fragment_cell(s) for _, s in nz):
            return False
        # Every non-empty column must already be populated in the parent so we
        # only ever CONTINUE an existing cell, never invent a new column.
        for i, _ in nz:
            if i >= len(parent) or not (parent[i] or "").strip():
                return False
        return True

    out: list[list[str]] = []
    for row in rows:
        first = row[0].strip() if row else ""
        rest_has_content = any((c or "").strip() for c in row[1:])

        if _is_section_row_label(row):
            # Don't merge — emit as a separate row so the renderer can
            # surface the spanning section label as its own table row.
            out.append([(c or "").strip() for c in row])
            continue

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

        # v2.4.94 (Tier-2): numeric/parenthetical continuation — fold a
        # fragment row back into the parent's same-column cells. Unlike the
        # prose/label-modifier merges above, these fragments join INLINE (a
        # space, or nothing when the parent ends mid-token at a dash/open
        # paren) so "86" + "(87.8%)" → "86 (87.8%)" and
        # "-1.01% (-10.36-" + "8.34)" → "-1.01% (-10.36-8.34)".
        if out and _is_fragment_continuation(row, out[-1]):
            parent = out[-1]
            for i, cell in enumerate(row):
                v = (cell or "").strip()
                if not v or i >= len(parent):
                    continue
                base = parent[i].rstrip()
                if base.endswith(("-", "–", "—", "(", "−")):
                    parent[i] = base + v
                else:
                    parent[i] = base + " " + v
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

# A cell carrying a statistic VALUE (vs a header label). Broader than
# _NUMERIC_CELL_RE: also matches APA leading-dot decimals (".34"), operator-
# prefixed p-values ("< .001"), bracketed numeric intervals ("[0.53, 0.72]"),
# and the "N/A" filler — all DATA, not header text. The interval branch requires
# a digit and NO letters inside the brackets so a genuine header cell like
# "[95% CI]" (letters present) is NOT counted as data and stays a header. Used by
# `_is_header_like_row` so a real data row whose APA-formatted values the bare
# numeric pattern under-counted is not mistaken for an extra header row — the
# bug that silently dropped the FIRST data row of two-header-row correlation
# tables (collabra.90203 Table 10, DP-5).
_DATA_VALUE_CELL_RE = re.compile(
    r"^(?:"
    r"[<>=]?\s*[-−–]?\d*[.,]?\d+(?:[.,]\d+)*(?:[%∗*]+)?(?:\s*\([^)]*\))?"
    r"|\[[^\]A-Za-z]*\d[^\]A-Za-z]*\]"
    r"|n\s*/?\s*a"
    r")$",
    re.I,
)


def _is_header_like_row(row: list[str]) -> bool:
    """Heuristic: a row that looks like part of a header rather than data."""
    nonempty = [c.strip() for c in row if (c or "").strip()]
    if not nonempty:
        return False
    numeric = sum(1 for c in nonempty if _DATA_VALUE_CELL_RE.match(c))
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


# A running header is a NAME and a PAGE NUMBER — at most two populated cells.
# A row that fills the grid is a data row, whatever its cells look like.
#
# **This cap is the guard that was missing**, and its absence deleted published
# counts. `_WEAK_RH_PATTERNS` matches any single capitalised word (`Positive`,
# `Control`) and `_STRONG_RH_PATTERNS` matches any 1-4 digit integer — which is
# precisely what a frequency table is made of. So `["Positive", "245", "12"]`
# above `["Mean reaction time (ms)", "452.3", "18.7"]` was dropped whole, and in
# the blanking pass below a surviving `["Total sample size", "1240", "96"]` came
# back as `["Total sample size", "", ""]`. Bare integers in a counts table ARE
# the data and are often the only surviving copy of it — the case
# `render._carries_statistical_content` already documents.
#
# The value is not new: `camelot_extract._looks_like_running_header` has always
# rejected rows with more than two populated cells. This module held a second
# implementation of the same concept and never had the cap. One concept, two
# implementations, silently diverged.
_MAX_RUNNING_HEADER_CELLS = 2


def _row_can_be_a_running_header(row: list[str]) -> bool:
    """True when ``row`` is shaped like a leaked running header at all.

    Shape first, patterns second: a row wide enough to be data is not a header
    no matter how header-like its individual cells read.
    """
    populated = [c for c in row if (c or "").strip()]
    if not populated or len(populated) > _MAX_RUNNING_HEADER_CELLS:
        return False
    if not any(_is_strong_running_header(c) for c in populated):
        return False
    return all(
        _is_strong_running_header(c) or _is_weak_running_header(c)
        for c in populated
    )


def _drop_running_header_rows(rows: list[list[str]]) -> list[list[str]]:
    """Drop top rows of the grid that look like leaked running headers /
    page numbers rather than real column labels.

    Records every removal. Until v2.4.133 this module had ZERO telemetry — the
    register's "darkest channel" — so a deleted row left no count, no key and no
    log line anywhere, which is exactly the condition under which the data loss
    above went unnoticed.
    """
    if not rows:
        return rows
    out = list(rows)
    while len(out) >= 2:
        top = out[0]
        if not _row_can_be_a_running_header(top):
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
        record_fallback("cell_cleaning_running_header_row_dropped",
                        detail=" | ".join(c for c in top if (c or "").strip())[:60])
        out = out[1:]
    if out:
        top = list(out[0])
        strong = [c for c in top if _is_strong_running_header(c)]
        has_real = any(
            (c or "").strip()
            and not _is_strong_running_header(c)
            and not _is_weak_running_header(c)
            for c in top
        )
        # A LEAKED PAGE NUMBER IS ONE CELL; A COUNTS COLUMN IS SEVERAL.
        #
        # This pass blanks the "strong" cells of a row that also holds real
        # header text — correct for `["1236", "Target article", "Replication",
        # "Reason for change"]`, where a page number leaked into a genuine
        # header row. Applied to a DATA row it is worse than dropping the row:
        # `["Total sample size", "1240", "96"]` came back as
        # `["Total sample size", "", ""]`, so the table still looked complete
        # while its numbers were gone — a deletion that does not announce itself,
        # which this project ranks as the more dangerous kind.
        #
        # Requiring exactly one strong cell separates the two by their shape: a
        # running header contributes a single page number, while a frequency
        # table contributes a value per column. The row-width cap above cannot
        # do this job — the legitimate case is four cells wide.
        if len(strong) == 1 and has_real:
            for i, c in enumerate(top):
                if _is_strong_running_header(c):
                    record_fallback("cell_cleaning_running_header_cell_blanked",
                                    detail=(c or "").strip()[:40])
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


def cells_grid_to_html(
    rows: Sequence[Sequence[str | None]],
    *,
    clean=None,
    recover_ci_upper: bool = True,
) -> str:
    """Render a 2-D cell grid as an HTML ``<table>`` block.

    Applies the full cleaning pipeline (merge continuations, strip leader
    dots, split mashed cells, drop running headers, detect multi-row
    header, fold super-headers, fold suffix continuations, attach
    significance markers, render group separators). Returns ``""`` for
    tables with fewer than 2 rows after cleaning.

    **Every one of those ``""`` returns discards a whole table**, and until
    v2.4.133 all five did it silently — a caller receives an empty string that
    is indistinguishable from "this grid had no HTML worth rendering". Each now
    records which stage gave up and what the grid looked like when it did, so a
    vanished table is at least countable. (Register O11: this module had zero
    telemetry of any kind.)
    """
    if len(rows) < 2:
        record_fallback("cells_grid_to_html_too_few_rows", detail=f"{len(rows)}rows")
        return ""

    norm: list[list[str]] = []
    for row in rows:
        norm.append([(c or "").strip() if c is not None else "" for c in row])

    before_rh = len(norm)
    norm = _drop_running_header_rows(norm)
    if len(norm) < 2:
        record_fallback("cells_grid_to_html_empty_after_running_header_strip",
                        detail=f"{before_rh}->{len(norm)}")
        return ""

    merged = _merge_continuation_rows(norm)
    if len(merged) < 2:
        record_fallback("cells_grid_to_html_empty_after_continuation_merge",
                        detail=f"{len(norm)}->{len(merged)}")
        return ""

    n_cols = max(len(r) for r in merged) if merged else 0
    if n_cols == 0:
        record_fallback("cells_grid_to_html_no_columns", detail=f"{len(merged)}rows")
        return ""

    for r in merged:
        while len(r) < n_cols:
            r.append("")

    for row in merged:
        for ci in range(len(row)):
            row[ci] = _strip_leader_dots(row[ci])
            row[ci] = _split_mashed_cell(row[ci])

    before_sig = len(merged)
    merged = _merge_significance_marker_rows(merged)
    if len(merged) < 2:
        record_fallback("cells_grid_to_html_empty_after_significance_merge",
                        detail=f"{before_sig}->{len(merged)}")
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
            lines.append(f"      <th>{_html_escape(c, clean)}</th>")
        lines.append("    </tr>")
    lines.append("  </thead>")
    lines.append("  <tbody>")
    for row in body:
        if _is_group_separator(row, n_cols):
            lines.append(
                f'    <tr><td colspan="{n_cols}"><strong>'
                f"{_html_escape(row[0], clean)}</strong></td></tr>"
            )
            continue
        # Recover a dropped/detached minus on a CI upper bound when the row's
        # estimate and CI are in separate cells (region-driven grid). The
        # same-cell shape is handled inside _html_escape.
        #
        # OFF for markup formats. This repair decides INFERENTIALLY — it argues
        # the interval must be negative because otherwise it excludes the
        # estimate — and CLAUDE.md reserves inferential evidence for the
        # consumer, which holds the parsed statistic and has a UI to flag it.
        # It is justified on a PDF because a broken font really does drop the
        # glyph; a DOCX carries real Unicode, so the same rewrite would
        # manufacture a minus the author never typed. Measured 2026-09-05:
        # `-.73 [-0.78, 0.67]` became `[-0.78, -0.67]` in the DOCX html channel.
        if recover_ci_upper:
            row = _recover_ci_upper_in_grid_row(row)
        lines.append("    <tr>")
        for c in row:
            lines.append(f"      <td>{_html_escape(c, clean)}</td>")
        lines.append("    </tr>")
    lines.append("  </tbody>")
    lines.append("</table>")

    return "\n".join(lines) + "\n"


__all__ = [
    "cells_grid_to_html",
    "clean_cell_text",
    "recover_unmapped_glyph_minus",
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
