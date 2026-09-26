"""Tables printed SIDEWAYS: read them in the frame they were typeset in.

Owner decision 2026-09-25 (option B of the rotated-table decision brief): turn a
rotated table's glyphs back upright using each character's text matrix, then grid
them with the whitespace path's own clustering and gates.

Why this is needed. A table typeset rotated by 90 degrees on a portrait page is
invisible to both of docpluck's usual captures when the page also carries
upright text. pdftotext's linear order scatters its cells (on
``10.1038/s41467-024-45528-0`` p6 Table 4's values come BEFORE its caption, one
token per line), and Camelot only rotates a page whose text is WHOLLY sideways
(cell_geometry trap T5), so a half-page rotated table beside upright prose is
never gridded. Over the 102-paper corpus manifest 31 of 435 table captions are
rotated; with Camelot on, 4 of them reach the caption-only path, and with Camelot
off (``DOCPLUCK_DISABLE_CAMELOT``, or Camelot failing under memory pressure) all
31 do.

THE EVIDENCE IS TYPOGRAPHIC, never words. Which glyphs belong to the table is
decided by what the renderer drew: a glyph's text matrix says whether it is
rotated and which way it reads (``detect.rotated_caption_direction``). Only the
glyphs that turn the SAME way as the table's caption are read.

That one fact is also what separates the two cases of sideways FURNITURE the
earlier content-status branch could not tell from a table by orientation alone.
Measured from the glyph matrices, both read the OPPOSITE way to their table on
every page checked:

* the repository watermark ``Author Manuscript`` on 10.1177/23780231251314667
  (12pt Helvetica, text matrix pointing down the page; the tables on p35/p37/p39
  read up it, and the watermark is drawn the same way on the upright p10);
* the journal header ``rsos.royalsocietypublishing.org R. Soc. open sci.`` on
  10.1098/rsos.140072 (down the page on p4 and p5; Table 1 on p5 reads up it).

A second, independent safeguard: content is read only from the caption onward
in the caption's own frame, so a line in the same direction drawn before the
caption is never read as the table (``lines_before_caption`` counts them).

Nothing is deleted from the document by either rule: those glyphs stay in the
text channel exactly as before. They are only not read AS THE TABLE.

Coordinates. A glyph read upward (matrix ``(0, s, -s, 0)``) has its ascenders
pointing to page-left, so in the table's own frame ``x`` runs up the page and
``top`` runs left to right: ``x = H - bottom``, ``top = x0``. A glyph read
downward (``(0, -s, s, 0)``) is the mirror: ``x = top``, ``top = W - x1``. Cell
bboxes are mapped back to pdfplumber page coordinates before they are returned.

``size`` must be recomputed. For a rotated glyph pdfplumber's ``size`` is the
extent along the PAGE's vertical, i.e. the glyph's advance width (2.0 for an
``i`` and 4.7 for an ``m`` in one 7pt run on nat_comms_4 p6), not its font size.
The font size is the glyph box's extent ACROSS the baseline: pdfminer builds
every glyph box one font size tall in text space, so turned upright it is the
box's height. It is NOT the text matrix's scale, which carries the size only
when the PDF sets it there: on rsos.140072 p5 ``hypot(a, b)`` is 9.96 for a
10pt glyph, on 10.1177/23780231251314667 p35 it is 1.0 for every glyph (7.5pt
body, 9pt caption label, 12pt watermark -- the size is in ``Tf`` there).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from itertools import pairwise

from . import Cell
from .captions import FIGURE_CAPTION_RE, TABLE_CAPTION_RE, CaptionMatch
from .detect import (
    _bbox_of_caption_line,
    line_is_rotated_furniture,
    rotated_caption_direction,
)
from .whitespace import WORD_GAP_RATIO

Bbox = tuple[float, float, float, float]

# Words are split at `whitespace.WORD_GAP_RATIO` of the font size: rotated glyphs
# carry no space glyph (0 blank chars among 2,598 rotated glyphs on
# nat_comms_4 p6), so words must be split from geometry (the L-007 rule).

# A table note is set smaller than the table body: the same ratio
# ``detect._detect_footnote_below`` uses for an upright table's note.
NOTE_SIZE_RATIO: float = 0.92


def glyph_direction(c: dict) -> int:
    """``0`` upright, ``1`` read up the page, ``-1`` read down it."""
    if c.get("upright", True) is not False:
        return 0
    m = c.get("matrix") or (0, 0, 0, 0, 0, 0)
    return 1 if m[1] > 0 else -1


def _to_frame(o: dict, *, direction: int, width: float, height: float) -> tuple[float, float, float, float]:
    if direction > 0:
        return height - o["bottom"], height - o["top"], o["x0"], o["x1"]
    return o["top"], o["bottom"], width - o["x1"], width - o["x0"]


def to_page_bbox(bbox: Bbox, *, direction: int, width: float, height: float) -> Bbox:
    """Map a bbox in the table's upright frame back to pdfplumber page space."""
    fx0, ftop, fx1, fbottom = bbox
    if direction > 0:
        return (ftop, height - fx1, fbottom, height - fx0)
    return (width - fbottom, fx0, width - ftop, fx1)


def upright_view(page_obj, direction: int):
    """A ``PageLayout`` holding only this page's glyphs that read in
    ``direction``, turned upright, plus the page's rules in the same frame.

    Upright glyphs (body prose beside a half-page table, running headers) and
    glyphs rotated the other way are not in it. ``words`` are split from the
    glyph gaps (``WORD_GAP_RATIO``) by pdfplumber's own word extractor.
    """
    from pdfplumber.utils.text import WordExtractor

    width = float(page_obj.width)
    height = float(page_obj.height)
    chars = []
    for c in getattr(page_obj, "chars", None) or ():
        if glyph_direction(c) != direction or not c.get("text"):
            continue
        x0, x1, top, bottom = _to_frame(c, direction=direction, width=width, height=height)
        n = dict(c)
        n.update(
            x0=x0, x1=x1, top=top, bottom=bottom, doctop=top,
            width=x1 - x0, height=bottom - top, size=bottom - top,
            upright=True,
        )
        chars.append(n)
    chars.sort(key=lambda c: (round(c["top"]), c["x0"]))
    # A SPACE GLYPH, where the PDF draws one, separates words and is kept for the
    # word extractor only. Glyph gaps alone cannot find that break when the face
    # is slanted by its text matrix: on 10.1177/23780231221103044 p37 the note's
    # oblique ``Note:`` (matrix ``(0, 1, -1, 0.32)``) has boxes wider than its
    # advances, the gap before ``Summary`` measures -0.03pt, and the note shipped
    # as ``Note:Summary`` -- though the PDF draws a space there.
    spaced = chars
    chars = [c for c in spaced if c["text"].strip()]

    def _frame_obj(o: dict) -> dict:
        x0, x1, top, bottom = _to_frame(o, direction=direction, width=width, height=height)
        n = dict(o)
        n.update(x0=x0, x1=x1, top=top, bottom=bottom, doctop=top,
                 width=x1 - x0, height=bottom - top)
        return n

    # Each word carries its glyphs' modal FONT size. The word's box height is not
    # one: it is the union of its glyph boxes, and on 10.1177/23780231251314667
    # p35 rows whose glyphs are all 7.5pt Times-Roman come out 10.0 tall where
    # they carry significance stars, so row sizes alternated 10.0 / 7.5.
    words = []
    for word, word_chars in WordExtractor(x_tolerance_ratio=WORD_GAP_RATIO).iter_extract_tuples(spaced):
        word["size"] = Counter(round(c["size"], 1) for c in word_chars).most_common(1)[0][0]
        words.append(word)
    return replace(
        page_obj,
        width=height,
        height=width,
        spans=(),
        chars=tuple(chars),
        words=tuple(words),
        lines=tuple(_frame_obj(o) for o in getattr(page_obj, "lines", ()) or ()),
        rects=tuple(_frame_obj(o) for o in getattr(page_obj, "rects", ()) or ()),
        curves=(),
    )


@dataclass(frozen=True)
class RotatedCapture:
    """What was read of one rotated table.

    ``caption`` is the caption as printed in the table's own frame: its first line
    plus the lines that continue it (see :func:`_caption_continues`). ``cells`` is
    empty when no grid passed the gates, and ``grid_rejected`` then says why.
    ``raw_text`` is the table's own lines in reading order, one cell-sized segment
    per line (a printed line split at column gaps) -- what the caption-only record
    carries when there is no grid. ``footnote`` is the table's note. The counts
    say what, of the glyphs turned the caption's way, was NOT read as this table,
    so a consumer can see it happened.
    """

    direction: int
    caption: str
    cells: list[Cell]
    grid_rejected: str | None
    raw_text: str
    footnote: str | None
    lines_before_caption: int
    lines_after_bound: int
    dotted_rules: int
    banner_lines: int = 0


def _line_text(line: list[dict]) -> str:
    return " ".join(w.get("text", "") for w in line)


def _segments(line: list[dict], gap: float) -> list[str]:
    """A printed line split where the gap between words is column-sized."""
    out: list[list[dict]] = []
    for w in line:
        if out and w["x0"] - out[-1][-1]["x1"] <= gap:
            out[-1].append(w)
        else:
            out.append([w])
    return [_line_text(seg) for seg in out]


def _modal_size(words: list[dict]) -> float:
    """Modal font size of ``words``, weighted by glyph count."""
    sizes: Counter[float] = Counter()
    for w in words:
        sizes[float(w.get("size") or 0.0)] += len(w.get("text", "")) or 1
    return sizes.most_common(1)[0][0] if sizes else 0.0


def _opens_other_caption(text: str, own: CaptionMatch) -> bool:
    for kind, regex in (("table", TABLE_CAPTION_RE), ("figure", FIGURE_CAPTION_RE)):
        m = regex.match(text)
        if m and not (kind == own.kind and int(m.group("num")) == own.number):
            return True
    return False


# A caption continues onto the next line only if that line follows it at no
# more than this many font sizes, carries no column gap, and is not set smaller
# than the caption's first line by more than NOTE_SIZE_RATIO allows.
_CAPTION_MAX_PITCH: float = 1.6


def _caption_continues(prev: list[dict], line: list[dict], caption_size: float, gap: float) -> bool:
    """TYPOGRAPHIC caption continuation, never the text channel's caption.

    The text channel cannot be used here: for a rotated caption it runs straight
    into whatever pdftotext emits next, which on 10.1177/23780231251314667 was
    the repository watermark (``Table 1. Author Manuscript``) and on the same
    paper's Table 2 a stray table value (``Table 2. .6***``).

    What ends a caption, measured on the four papers this was built for: the
    table's first row either has a column gap in it (the column heads of
    nat_comms_4 T4, jamison_2020 T4, rsos.140072 T1, socius_4 T1) or is set
    smaller than the caption (nat_comms_4 9.0 -> 7.0, jamison_2020 7.2 -> 6.4)
    or follows at a paragraph gap (socius_4 T3, a one-column list table: 25.6pt
    after a 10pt caption line). The caption's own second line has none of the
    three, and may be LARGER than its label (socius_4: ``Table 1.`` 9pt
    Helvetica-Bold, then the 10pt title), so size may only stop a caption by
    shrinking.
    """
    size = _modal_size(line)
    if caption_size and size < caption_size * NOTE_SIZE_RATIO:
        return False
    pitch = line[0]["top"] - prev[0]["top"]
    if pitch > _CAPTION_MAX_PITCH * max(size, _modal_size(prev)):
        return False
    return all(b["x0"] - a["x1"] <= gap for a, b in pairwise(line))


# A horizontal rule, in the table's frame: thinner than this and at least this
# long. A table's top rule separates its caption from its column heads.
_RULE_MAX_THICKNESS_PT: float = 2.0
_RULE_MIN_LENGTH_PT: float = 50.0


def _first_rule_below(view, y: float) -> float | None:
    """Top of the first horizontal rule drawn below ``y`` in the table's frame.

    The TYPOGRAPHIC end of a caption that its line spacing cannot give: on
    10.1177/23780231251327540 Table 3 and 10.1215/00703370-11057546 Table 3
    (both sideways) the title sits 17.4pt below its 9pt ``Table 3.`` label,
    wider than any line pitch inside a caption, and became the grid's first
    row; both tables' top rule is drawn at 96.0pt, between that title and the
    column heads.
    """
    tops = [
        o["top"]
        for o in (*view.lines, *view.rects)
        if o["bottom"] - o["top"] < _RULE_MAX_THICKNESS_PT
        and o["x1"] - o["x0"] >= _RULE_MIN_LENGTH_PT
        and o["top"] > y
    ]
    return min(tops) if tops else None


# A DOTTED RULE: a line drawn as a run of leader dots rather than as a vector
# line (10.1098/rsos.140072 Table 1 separates its rows this way: 70+ five-point
# periods per line). Every glyph a dot, at least this many, and no column gap
# between them -- so a row of per-column missing-value dots (". . . .", one per
# column, column gaps between) is NOT a rule and stays in the table.
_DOT_GLYPHS = frozenset(".·․…")
_DOTTED_RULE_MIN_DOTS: int = 10


def _is_dotted_rule(line: list[dict], gap: float) -> bool:
    glyphs = "".join(w.get("text", "") for w in line)
    if len(glyphs) < _DOTTED_RULE_MIN_DOTS or not set(glyphs) <= _DOT_GLYPHS:
        return False
    return all(b["x0"] - a["x1"] <= gap for a, b in pairwise(line))


# A short note line starts at the table's left edge (within this) -- a wrapped
# row label or value continues at its column's indent instead.
_NOTE_LEFT_TOL_PT: float = 2.0


def _max_gap(line: list[dict]) -> float:
    return max((b["x0"] - a["x1"] for a, b in pairwise(line)), default=0.0)


def _mostly_letters(line: list[dict]) -> bool:
    """More letters than digits: a note is words, a data row is numbers.

    ``detect._is_prose_row`` needs no such test, because it looks for prose
    BETWEEN tables; a note detector runs on table lines, and on
    10.1177/01461672251327169 Table 8 (p13, sideways) the last row's line of
    confidence intervals spans the table with no 12pt gap, and was read as the
    opening line of its note."""
    text = "".join(w.get("text", "") for w in line)
    return sum(ch.isalpha() for ch in text) > sum(ch.isdigit() for ch in text)


def _is_running_text(line: list[dict], left: float, width: float) -> bool:
    """``detect._is_prose_row``'s test, on words: at least ``_PROSE_MIN_GLYPHS``
    glyphs spanning ``_PROSE_MIN_SPAN_FRAC`` of the table's width with no gap of
    ``_PROSE_MAX_GAP_PT`` -- justified word spacing stretches well past a column
    gap's 5pt (10.1080/23743603.2021.1878340 Table 2's note) but never to 12."""
    from .detect import _PROSE_MAX_GAP_PT, _PROSE_MIN_GLYPHS, _PROSE_MIN_SPAN_FRAC

    glyphs = sum(len(w.get("text", "")) for w in line)
    if glyphs < _PROSE_MIN_GLYPHS or width <= 0 or not _mostly_letters(line):
        return False
    if line[-1]["x1"] - line[0]["x0"] < _PROSE_MIN_SPAN_FRAC * width:
        return False
    return _max_gap(line) < _PROSE_MAX_GAP_PT


def _note_start(body: list[list[dict]], gap: float) -> int:
    """Index of the first line of the table's trailing NOTE, or ``len(body)``.

    The note is the earliest trailing block that opens with a note-like line and
    continues with note-like or continuation lines to the end. A line OPENS a
    note when it is

    * set smaller than the table body (``NOTE_SIZE_RATIO``, the upright path's
      own test) -- 10.1038/s41467-024-45528-0 Table 4, 6pt under 7pt;
    * running text (:func:`_is_running_text`) -- the ``Abbreviations: ...``
      paragraph of 10.1001/jamanetworkopen.2023.39337 Table 2, 7pt like its
      cells, which was chopped into cells at the column boundaries; or
    * a short line starting at the table's left edge with no column gap in it
      (``c Indicates statistical significance using P < .05.``).

    A line CONTINUES a note when it opens one itself, or WRAPS the note text
    above it -- no gap of ``_PROSE_MAX_GAP_PT`` and directly under running text or
    smaller type: the hanging-indented, justified second and third lines of
    10.1080/23743603.2021.1878340 Table 2's ``(1) The F-statistics ...``.

    Guards: the block must hold a smaller-set or running-text line, so a
    trailing wrapped label (``mg/dL``) stays in the table; some line above it
    must have a column gap, so a single-column list table
    (10.1177/23780231251314667 Table 3, whose entries are running text) is not
    read as one long note; and ``WHITESPACE_MIN_ROWS`` lines must stay above it.
    """
    from .detect import _PROSE_MAX_GAP_PT
    from .whitespace import WHITESPACE_MIN_ROWS

    words = [w for ln in body for w in ln]
    if not words:
        return len(body)
    body_size = _modal_size(words)
    left = min(w["x0"] for w in words)
    width = max(w["x1"] for w in words) - left

    def strong(ln: list[dict]) -> bool:
        return _modal_size(ln) < body_size * NOTE_SIZE_RATIO or _is_running_text(ln, left, width)

    def opens(ln: list[dict]) -> bool:
        return strong(ln) or (
            ln[0]["x0"] - left <= _NOTE_LEFT_TOL_PT and _max_gap(ln) <= gap and _mostly_letters(ln)
        )

    def wraps(ln: list[dict]) -> bool:
        return _max_gap(ln) < _PROSE_MAX_GAP_PT and _mostly_letters(ln)

    def is_note_block(block: list[list[dict]]) -> bool:
        # A WRAPPED line (justified, hanging indent) may only follow a line that
        # is itself note text -- running text, smaller type, or another wrapped
        # line of it. Without that, a label-only row at the table's left edge
        # opened a "note" and the label-and-value rows after it came along as
        # continuation (second-model review, Sonnet, 2026-09-25).
        if not opens(block[0]):
            return False
        in_prose = strong(block[0])
        for ln in block[1:]:
            if strong(ln):
                in_prose = True
            elif opens(ln):
                in_prose = False
            elif not (in_prose and wraps(ln)):
                return False
        return True

    for i in range(WHITESPACE_MIN_ROWS, len(body)):
        block = body[i:]
        if not is_note_block(block):
            continue
        if not any(strong(ln) for ln in block):
            continue
        if not any(_max_gap(ln) > gap for ln in body[:i]):
            return len(body)
        return i
    return len(body)


def read_rotated_table(
    page_obj, cap: CaptionMatch, banners: frozenset[str] = frozenset()
) -> RotatedCapture | None:
    """Read the table under a rotated caption, or ``None`` when the caption is
    not rotated or cannot be found in its own frame.

    In the caption's frame: the caption is its first line plus the lines that
    continue it typographically (:func:`_caption_continues`). The table is every
    later line up to the next table or figure caption in that frame. Dotted rules
    (:func:`_is_dotted_rule`) are decoration, not rows. Trailing lines set smaller
    than the body are the table's note and go to ``footnote``, as an upright
    table's note does. The rest is gridded by ``whitespace.rotated_frame_cells``;
    if no grid passes its gates the same lines are still returned, in reading
    order, as ``raw_text``.
    """
    from .whitespace import (
        COLUMN_GAP_PT,
        _text_by_lines,
        _visual_lines,
        rotated_frame_cells,
    )

    direction = rotated_caption_direction(page_obj, cap)
    if direction is None:
        return None
    view = upright_view(page_obj, direction)
    cap_bbox = _bbox_of_caption_line(view, cap)
    if cap_bbox is None:
        return None
    lines = _visual_lines(list(view.words))
    before = [ln for ln in lines if ln[0]["top"] < cap_bbox[1] - 1.0]
    caption_lines = [ln for ln in lines if cap_bbox[1] - 1.0 <= ln[0]["top"] <= cap_bbox[3] - 1.0]
    after = [ln for ln in lines if ln[0]["top"] > cap_bbox[3] - 1.0]
    if not caption_lines:
        return None

    caption_size = _modal_size(caption_lines[0])
    i = 0
    rule_top = _first_rule_below(view, cap_bbox[3])
    while i < len(after) and (
        # Above the table's top rule, a line with no column gap is caption.
        (rule_top is not None and after[i][-1]["bottom"] <= rule_top
         and _max_gap(after[i]) <= COLUMN_GAP_PT)
        or _caption_continues(caption_lines[-1], after[i], caption_size, COLUMN_GAP_PT)
    ):
        caption_lines.append(after[i])
        i += 1
    caption = " ".join(_line_text(ln) for ln in caption_lines).strip()

    body: list[list[dict]] = []
    bounded_at: int | None = None
    dotted = 0
    banner_lines = 0
    for j in range(i, len(after)):
        ln = after[j]
        if _opens_other_caption(_line_text(ln), cap):
            bounded_at = j
            break
        # A banner recurring up the margin of most pages
        # (`detect.recurring_rotated_lines`) that turns the table's own way is
        # furniture too; the caller computes the set once per document.
        if banners and line_is_rotated_furniture(_line_text(ln), banners):
            banner_lines += 1
            continue
        if _is_dotted_rule(ln, COLUMN_GAP_PT):
            dotted += 1
            continue
        body.append(ln)
    lines_after_bound = 0 if bounded_at is None else len(after) - bounded_at

    footnote = None
    note_start = _note_start(body, COLUMN_GAP_PT)
    if note_start < len(body):
        footnote = " ".join(_text_by_lines(ln) for ln in body[note_start:]).strip() or None
        body = body[:note_start]

    grid_words = [w for ln in body for w in ln]
    cells, rejected = rotated_frame_cells(grid_words, own_caption_number=cap.number)
    width, height = float(page_obj.width), float(page_obj.height)
    for c in cells:
        c["bbox"] = to_page_bbox(tuple(c["bbox"]), direction=direction, width=width, height=height)
    raw_text = "\n".join(seg for ln in body for seg in _segments(ln, COLUMN_GAP_PT) if seg.strip())
    return RotatedCapture(
        direction=direction,
        caption=caption,
        cells=cells,
        grid_rejected=rejected,
        raw_text=raw_text,
        footnote=footnote,
        lines_before_caption=len(before),
        lines_after_bound=lines_after_bound,
        dotted_rules=dotted,
        banner_lines=banner_lines,
    )


__all__ = ["RotatedCapture", "glyph_direction", "read_rotated_table", "to_page_bbox", "upright_view"]
