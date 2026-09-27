"""A table's printed note: located on the page, read from the text channel.

WHY TWO CHANNELS, AND WHICH ONE DECIDES WHAT
-------------------------------------------
The layout channel (pdfplumber) knows WHERE the note is -- the line that
begins with a ``Note.`` / ``Notes:`` / ``Source:`` label below this table's
caption, and the rows under it -- but on tight-kerned PDFs its characters
carry no spaces at all (`10.5465/amj.2016.1196` p20 reads
``Notes:n5356.NegativeFeedback(05neutralfeedback;...``), so its text is not
something a consumer can use. The text channel (pdftotext, the channel every
caption is already read from) carries the words with their spaces, but has no
geometry, so on its own it cannot say which table a ``Note.`` paragraph
belongs to or where the note stops and body prose begins.

So the layout channel DECIDES (which rows, how many) and the text channel
SUPPLIES (the characters). A note is delivered only where the two agree
character for character on every letter and digit of the rows delivered --
any disagreement is a refusal with a reason, never a guess. Punctuation and
symbols are not compared, because that is where the two channels are known to
decode differently; the delivered text is the text channel's, exactly as for
captions, so a consumer receives what pdftotext emitted and never a character
assembled from the other channel.

WHAT IS NOT CAPTURED, stated rather than implied: a note with no printed label
(a bare ``*p < .05`` legend, a superscript-letter footnote), a note printed on
a later page than its caption, and a note printed ABOVE its caption. All leave
``footnote`` None, exactly as before this module existed.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

from .bbox_utils import Bbox

# A note label BEGINS its line and is followed by `.` or `:` -- "Note that the
# results..." is prose and is excluded by the required punctuation.
_LABEL = r"(?:Notes?|NOTES?|Sources?|SOURCES?|Abbreviations?|ABBREVIATIONS?)\s*[.:]"
_NOTE_LABEL_RE = re.compile("^" + _LABEL)
_TEXT_NOTE_LABEL_RE = re.compile(r"(?m)^[ \t]*" + _LABEL)
_LEGEND_START_RE = re.compile(r"^[*†‡§#∗]")
_CAPTION_START_RE = re.compile(r"^(?:Table|TABLE|Figure|FIGURE|Fig\.)\s*[A-Z]?\d")

# Rows of one note sit a line pitch apart; the gap to whatever follows the
# note (body prose, a figure) is larger. See `_note_rows`.
_MAX_FIRST_GAP_PT: float = 25.0
_PITCH_FACTOR: float = 1.6
_PITCH_SLACK_PT: float = 4.0
# The note's FIRST gap (label row to the next row) may be at most this many
# times the label's type height. Leading runs to ~1.6x (`10.1186/s12889-023-`
# `17078-5` sets 7pt notes on 11.3pt lines); a page footer under a rule sits
# ~2.9x below (`10.1001/jamanetworkopen.2023.16111` p7).
_FIRST_GAP_FACTOR: float = 2.0
# A row whose type is larger than the label's by more than this is body text
# resuming, not the note continuing.
_SIZE_TOLERANCE_PT: float = 0.5
# Glyphs whose tops lie within this of the row's first glyph share its row.
_ROW_KEY_PT: float = 2.0
# A row whose type is below this fraction of an adjacent row's, and sits inside
# that row's vertical span, is a sub- or superscript of it.
_SCRIPT_SIZE_RATIO: float = 0.85
_SCRIPT_MAX_GLYPHS: int = 6
# A horizontal gap this wide inside one visual row separates two blocks (a
# column gutter, a table-cell gap); inter-word space stays far below it. The
# same bound `detect._is_prose_row` uses for a gutter.
_RUN_GAP_PT: float = 12.0


@dataclass(frozen=True)
class TableNote:
    text: str
    bbox: Bbox          # pdfplumber top-down, over the rows delivered
    rows: int           # rows delivered
    rows_located: int   # rows the layout channel attributed to the note


def _key(s: str) -> str:
    """Letters and digits only, compatibility-folded -- what both channels must
    agree on."""
    return "".join(ch for ch in unicodedata.normalize("NFKC", s).casefold() if ch.isalnum())


def _upright(c: dict) -> bool:
    return c.get("upright", True) is not False


def _group_rows(chars: list[dict]) -> list[list[dict]]:
    """Visual rows, with sub- and superscripts kept IN the row they belong to.

    Glyphs are grouped by `top`; then a SHORT row (at most `_SCRIPT_MAX_GLYPHS`
    glyphs) set in smaller type than an adjacent row (below `_SCRIPT_SIZE_RATIO`
    of it), whose vertical midpoint lies inside that row's span and whose glyphs
    lie within its horizontal extent, is a script and is merged into it. The
    shortness and containment matter: on `10.1080/02699931.2024.2434156` p8 a
    whole 8pt note line satisfies the size and span tests against the 9.5pt
    body line beside it in the other column. Grouping by
    `top` alone put `10.1001/jamanetworkopen.2023.39337`'s "HbA1c" subscript on
    a row of its own, so the layout read "HbA" where the text channel reads
    "HbA1c" and the rest of the note was refused."""
    rows: list[list[dict]] = []
    for c in sorted(chars, key=lambda c: (c.get("top", 0.0), c.get("x0", 0.0))):
        if rows and abs(c.get("top", 0.0) - rows[-1][0].get("top", 0.0)) <= _ROW_KEY_PT:
            rows[-1].append(c)
        else:
            rows.append([c])

    def span(r: list[dict]) -> tuple[float, float]:
        return min(c.get("top", 0.0) for c in r), max(c.get("bottom", 0.0) for c in r)

    i = 0
    while i < len(rows):
        r = rows[i]
        glyphs = [c for c in r if (c.get("text") or "").strip()]
        size = _modal_size(r)
        mid = sum(span(r)) / 2
        host = None
        for j in (i - 1, i + 1):
            if not (0 <= j < len(rows)) or len(glyphs) > _SCRIPT_MAX_GLYPHS or not glyphs:
                continue
            t, b = span(rows[j])
            hx0 = min(c.get("x0", 0.0) for c in rows[j])
            hx1 = max(c.get("x1", 0.0) for c in rows[j])
            if (size < _modal_size(rows[j]) * _SCRIPT_SIZE_RATIO and t <= mid <= b
                    and all(hx0 <= c.get("x0", 0.0) and c.get("x1", 0.0) <= hx1 for c in glyphs)):
                host = j
                break
        if host is None:
            i += 1
            continue
        rows[host].extend(r)
        del rows[i]
        i = max(0, min(i, host) - 1) if host < i else i
    for r in rows:
        r.sort(key=lambda c: c.get("x0", 0.0))
    return rows


def _runs(row: list[dict]) -> list[list[dict]]:
    """Split one visual row into horizontal runs at gaps >= `_RUN_GAP_PT`."""
    runs: list[list[dict]] = []
    for c in row:
        if runs and c.get("x0", 0.0) - max(g.get("x1", 0.0) for g in runs[-1]) < _RUN_GAP_PT:
            runs[-1].append(c)
        else:
            runs.append([c])
    return runs


def _span(run: list[dict]) -> tuple[float, float]:
    return min(c["x0"] for c in run), max(c["x1"] for c in run)


def _overlaps(a: tuple[float, float], b: tuple[float, float], slack: float = 5.0) -> bool:
    return a[0] < b[1] + slack and b[0] < a[1] + slack


def _row_text(run: list[dict]) -> str:
    return "".join(c.get("text", "") for c in run)


def _modal_size(chars: list[dict]) -> float:
    counts: dict[float, int] = defaultdict(int)
    for c in chars:
        if (c.get("text") or "").strip():
            counts[round(float(c.get("size") or 0.0), 1)] += 1
    return max(counts.items(), key=lambda kv: kv[1])[0] if counts else 0.0


def _note_rows(
    rows: list[list[dict]],
    x_range: tuple[float, float],
    rules: list[tuple[float, float, float]] = (),
) -> list[list[dict]] | None:
    """The note's label run plus the runs that continue it, top-down.

    The label run is the topmost run that begins with a note label and lies
    over the table (overlaps ``x_range``). A later row continues the note with
    the runs that overlap the label run horizontally, while it sits within one
    line pitch of the row above (the pitch is set by the note's own first
    gap, which may not exceed one line pitch of the label's own type), its type
    is not larger than the label's, no horizontal rule lies between it and the
    row above, and it does not begin a caption. A row carrying no letter or digit
    (a dagger set as its own superscript line) rides along without setting or
    breaking the pitch.

    Two measured cases fix the edges. The first-gap bound and the rule stop are
    `10.1001/jamanetworkopen.2023.16111` p7: the journal's page footer sits 23pt
    under the one-line note, below a rule, and was read as its second line. The
    one exception to the pitch is a row that OPENS A NEW PART of the note --
    within `_MAX_FIRST_GAP_PT`, a row that begins with `*`, `†`, `‡`, `§` or `#`
    (or with `p <` right after a row of only such marks), with a note label, or
    with a superscript marker. `10.1111/jomf.12989` p20 sets its `* p < .05`
    lines half a line lower than the note above them;
    `10.1001/jamanetworkopen.2023.39337` p7 does the same with its lettered
    footnotes, and `10.1177/23780231251321549` its second `Note:` after
    `Source:`.
    ``rules`` are horizontal rules as ``(x0, x1, y)``. Returns ``[]`` when there
    is no label, ``None`` when the note begins above its label
    (`_unlabelled_lead`)."""
    label_i = label_run = None
    for i, row in enumerate(rows):
        for run in _runs(row):
            if _NOTE_LABEL_RE.match(_row_text(run).lstrip()) and _overlaps(_span(run), x_range):
                label_i, label_run = i, run
                break
        if label_i is not None:
            break
    if label_i is None:
        return []
    band = _span(label_run)
    label_size = _modal_size(label_run)
    glyphs = [c for c in label_run if (c.get("text") or "").strip()]
    line_h = (max(c.get("bottom", 0.0) for c in glyphs) - min(c.get("top", 0.0) for c in glyphs)
              if glyphs else 0.0)
    first_gap_max = min(_MAX_FIRST_GAP_PT, max(line_h * _FIRST_GAP_FACTOR, line_h + _PITCH_SLACK_PT))
    if _unlabelled_lead(rows, label_i, label_run, first_gap_max, rules):
        return None
    out = _follow(rows, label_i, label_run, label_size, first_gap_max, rules)
    # A note set in TWO COLUMNS under a wide table: the second column starts
    # level with the label, to its right, in the note's type, within the
    # table's width. `10.1001/jamanetworkopen.2023.35237` p6 and
    # `10.1001/jamanetworkopen.2023.46085` p5 continue their notes there; read
    # from the label's column alone, both shipped cut short. The text channel
    # must still agree with the rows in order, or the note is refused.
    label_top = min(c.get("top", 0.0) for c in label_run)
    second = None
    for k in range(label_i, min(len(rows), label_i + 2)):
        for run in _runs(rows[k]):
            x0, _ = _span(run)
            top = min(c.get("top", 0.0) for c in run)
            if (x0 >= band[1] + _RUN_GAP_PT - 1.0 and _overlaps(_span(run), x_range)
                    and _key(_row_text(run))
                    and abs(_modal_size(run) - label_size) <= _SIZE_TOLERANCE_PT
                    and label_top - _ROW_KEY_PT <= top <= label_top + first_gap_max
                    and (second is None or x0 < _span(second[1])[0])):
                second = (k, run)
    if second is not None:
        out += _follow(rows, second[0], second[1], label_size, first_gap_max, rules)
    return out


def _follow(
    rows: list[list[dict]],
    start_i: int,
    first_run: list[dict],
    label_size: float,
    first_gap_max: float,
    rules: list[tuple[float, float, float]],
) -> list[list[dict]]:
    """``first_run`` plus the rows that continue it in its own column (see
    `_note_rows` for the rules)."""
    band = _span(first_run)
    out = [first_run]
    prev_top = min(c.get("top", 0.0) for c in first_run)
    pitch: float | None = None
    for row in rows[start_i + 1:]:
        picked = [c for run in _runs(row) if _overlaps(_span(run), band) for c in run]
        if not picked:
            continue
        text = _row_text(picked)
        if not _key(text):
            out.append(picked)
            continue
        top = min(c.get("top", 0.0) for c in picked)
        gap = top - prev_top
        prev_bottom = max(c.get("bottom", 0.0) for c in out[-1])
        if any(prev_bottom - 1.0 <= y <= top + 1.0 and _overlaps((x0, x1), band)
               for x0, x1, y in rules):
            break
        marks = "".join(_row_text(r) for r in _trailing_markless(out)) + text.lstrip()
        legend = gap <= _MAX_FIRST_GAP_PT and (
            bool(_LEGEND_START_RE.match(marks.lstrip()))
            or bool(_NOTE_LABEL_RE.match(text.lstrip()))
            or _starts_with_script(picked)
        )
        limit = first_gap_max if pitch is None else max(pitch * _PITCH_FACTOR, pitch + _PITCH_SLACK_PT)
        if gap > limit and not legend:
            break
        if _modal_size(picked) > label_size + _SIZE_TOLERANCE_PT:
            break
        if _CAPTION_START_RE.match(text.lstrip()):
            break
        if pitch is None and not legend:
            pitch = gap
        out.append(picked)
        prev_top = top
    return out


# A line of running text, not a table cell stub. `detect._is_prose_row` uses the
# same count.
_LEAD_MIN_GLYPHS: int = 25


def _unlabelled_lead(
    rows: list[list[dict]], label_i: int, label_run: list[dict], first_gap_max: float,
    rules: list[tuple[float, float, float]] = (),
) -> bool:
    """True when the note visibly BEGINS ABOVE its label: the line directly over
    the label is one unbroken run of text, starts where the label starts, is set
    in the label's type, and sits one line pitch above it. The note then has an
    unlabelled first line this module cannot attribute, and delivering it from
    the label down would silently drop that line -- `10.1186/s12889-023-17078-5`
    p10-13 print "Estimation of catastrophic costs using the output approach at
    a 20% threshold" above "Abbreviation: IQR ...". A table's last row fails the
    test: it has a column gutter, or starts elsewhere, or is a short stub, or
    the table's bottom rule separates it from the label (`10.5465/annals.2016.0011`
    p15, whose last row is one long left-column cell)."""
    if label_i == 0:
        return False
    band = _span(label_run)
    runs = [r for r in _runs(rows[label_i - 1]) if _overlaps(_span(r), band)]
    if len(runs) != 1:
        return False
    run = runs[0]
    glyphs = [c for c in run if (c.get("text") or "").strip()]
    if len(glyphs) < _LEAD_MIN_GLYPHS:
        return False
    label_top = min(c.get("top", 0.0) for c in label_run)
    gap = label_top - min(c.get("top", 0.0) for c in run)
    run_bottom = max(c.get("bottom", 0.0) for c in run)
    if any(run_bottom - 1.0 <= y <= label_top + 1.0 and _overlaps((x0, x1), band)
           for x0, x1, y in rules):
        return False
    return (
        abs(_span(run)[0] - band[0]) <= 3.0
        and abs(_modal_size(run) - _modal_size(label_run)) <= _SIZE_TOLERANCE_PT
        and 0 < gap <= first_gap_max
    )


def _starts_with_script(row: list[dict]) -> bool:
    """True when the row's first glyph is set smaller than the row's own type
    -- a superscript footnote marker (`a`, `b`, `1`) opening a footnote line."""
    glyphs = [c for c in row if (c.get("text") or "").strip()]
    if len(glyphs) < 2:
        return False
    return float(glyphs[0].get("size") or 0.0) < _modal_size(glyphs) * _SCRIPT_SIZE_RATIO


def _trailing_markless(out: list[list[dict]]) -> list[list[dict]]:
    """The rows at the end of ``out`` that carry no letter or digit."""
    tail: list[list[dict]] = []
    for r in reversed(out):
        if _key(_row_text(r)):
            break
        tail.insert(0, r)
    return tail


def starts_with_note_label(text: str) -> bool:
    """True when ``text`` begins with a printed note label (``Note.``,
    ``Notes:``, ``Source:``, ``Abbreviations:``) -- the same test the page
    search uses, so a grid row and a page line are judged alike."""
    return bool(_NOTE_LABEL_RE.match(text.lstrip()))


def caption_run_span(page_obj, caption_bbox: Bbox, label: str) -> tuple[float, float]:
    """The horizontal extent of the caption ITSELF on its line.

    ``detect._bbox_of_caption_line`` returns the whole visual row, and on a
    two-column page that row also carries the other column's text at the same
    height -- so its x-range would let a label in the other column pass as
    lying over this table. The run holding the caption's label is the caption.
    Falls back to the full row when no run carries the label."""
    x0, top, x1, bottom = caption_bbox
    # By vertical midpoint, not by `top`: the box's top is the row's highest
    # glyph, which may belong to the other column's line rather than the caption.
    row = [
        c for c in (page_obj.chars or ())
        if _upright(c) and top <= (c.get("top", 0.0) + c.get("bottom", 0.0)) / 2 <= bottom
    ]
    row.sort(key=lambda c: c.get("x0", 0.0))
    want = _key(label)
    for run in _runs(row):
        if want and want in _key(_row_text(run)):
            return _span(run)
    return x0, x1


def _match_rows_in_text(
    text: str, start: int, row_keys: list[str], hyphenated: list[bool] | None = None,
) -> tuple[int, int]:
    """Walk ``text`` from ``start`` matching the rows' letters and digits in
    order, skipping every other character of the text. A row counts only if
    its match ENDS AT A WORD BOUNDARY in the text: a row that stops mid-word
    means the layout row lost glyphs the text channel has, and delivering it
    would truncate the note -- unless the row ends in a hyphen
    (``hyphenated[i]``), where the word legitimately continues on the next
    line and the text channel may already have joined it (`10.1525/collabra.90203`
    p7: "origi-" / "nal" in the layout, "original" in the text).
    Returns (rows matched, end offset)."""
    pos = start
    ends: list[int] = []
    for n, key in enumerate(row_keys):
        i, p = 0, pos
        while i < len(key) and p < len(text):
            k = _key(text[p])
            if not k:
                p += 1
                continue
            # NFKC can expand one character (a ligature) into several.
            if key.startswith(k, i):
                i += len(k)
                p += 1
                continue
            break
        if i < len(key):
            break
        wraps = bool(hyphenated and hyphenated[n])
        if not wraps and p < len(text) and _key(text[p]) and _key(text[p - 1]):
            break
        ends.append(p)
        pos = p
    # A delivered note never ENDS on a hyphen-wrapped row: its word finishes on
    # the next row, which did not match, so the text would stop mid-word.
    while ends and hyphenated and hyphenated[len(ends) - 1] and len(ends) < len(row_keys):
        ends.pop()
    return len(ends), (ends[-1] if ends else start)


def locate_table_note(
    layout,
    text: str,
    *,
    page: int,
    page_text_span: tuple[int, int],
    below: float,
    above: float | None,
    x_range: tuple[float, float],
    after_offset: int | None = None,
) -> tuple[TableNote | None, str]:
    """Find the note printed below a table and read it from the text channel.

    ``below`` is the top-down y the note must start under (the caption line's
    top), ``above`` the y it must end before (the next caption on the page, if
    any), ``x_range`` the table's horizontal extent the label must overlap.
    ``page_text_span`` is the page's ``(start, end)`` in ``text``;
    ``after_offset`` prefers a label occurrence after the caption in text order.

    Returns ``(note, reason)``. ``reason`` is ``"ok"``, ``"partial"`` (only a
    leading subset of the located rows could be matched in the text channel;
    the note is those rows) or, with ``note`` None, why nothing was delivered.
    """
    if not (1 <= page <= len(layout.pages)):
        return None, "page_out_of_range"
    chars = [
        c for c in (layout.pages[page - 1].chars or ())
        if _upright(c)
        and c.get("top", 0.0) > below
        and (above is None or c.get("top", 0.0) < above)
    ]
    page_obj = layout.pages[page - 1]
    rules = [
        (float(o["x0"]), float(o["x1"]), (float(o["top"]) + float(o["bottom"])) / 2)
        for o in tuple(page_obj.lines or ()) + tuple(page_obj.rects or ())
        if float(o["x1"]) - float(o["x0"]) > 50.0 and float(o["bottom"]) - float(o["top"]) <= 2.0
        and float(o["top"]) > below
    ]
    note_rows = _note_rows(_group_rows(chars), x_range, rules) if chars else []
    if note_rows is None:
        return None, "unlabelled_lead"
    if not note_rows:
        return None, "no_label"
    note_rows = [r for r in note_rows if _key(_row_text(r))]
    row_keys = [_key(_row_text(r)) for r in note_rows]
    hyphenated = [_row_text(r).rstrip().endswith(("-", "­", "‐")) for r in note_rows]

    lo, hi = page_text_span
    page_text = text[:hi]
    best: tuple[int, int, int] | None = None   # (rows matched, preference, -start)
    best_end = 0
    for m in _TEXT_NOTE_LABEL_RE.finditer(text, lo, hi):
        s = m.start() + len(m.group(0)) - len(m.group(0).lstrip(" \t"))
        done, end = _match_rows_in_text(page_text, s, row_keys, hyphenated)
        if done == 0:
            continue
        pref = 1 if (after_offset is None or s >= after_offset) else 0
        cand = (done, pref, -s)
        if best is None or cand > best:
            best, best_end = cand, end
    if best is None:
        return None, "channels_disagree"
    done, _, neg_s = best
    s, end = -neg_s, best_end
    # Keep what closes the last line: its punctuation and any symbol-only
    # token after it, up to the line break -- `10.1017/jdm.2023.16` ends three
    # notes with "denoted by a cross (×).", whose "(×)." carries no letter or
    # digit and so is in no row key. Never past a letter or digit.
    while end < hi and text[end] != "\n" and not _key(text[end]):
        end += 1
    end = len(text[:end].rstrip())
    delivered = [c for r in note_rows[:done] for c in r]
    bbox = (
        min(c["x0"] for c in delivered), min(c["top"] for c in delivered),
        max(c["x1"] for c in delivered), max(c["bottom"] for c in delivered),
    )
    return (
        TableNote(text=text[s:end], bbox=bbox, rows=done, rows_located=len(row_keys)),
        "ok" if done == len(row_keys) else "partial",
    )


__all__ = ["TableNote", "caption_run_span", "locate_table_note", "starts_with_note_label"]
