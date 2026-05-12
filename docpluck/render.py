"""
docpluck.render — render a PDF as a complete markdown document.

Public API:
    render_pdf_to_markdown(pdf_bytes, *, normalization_level=...) -> str

The renderer is built on top of the existing library primitives:
    * extract_pdf_structured (text + Camelot tables + figures)
    * extract_sections (semantic section detection)
    * normalize_text (banner/footer/TOC strip already folded in at v1.8.0)
    * cells_to_html (table HTML emission)

After the markdown is assembled the file runs through a sequence of
*markdown-level* post-processors ported from the iter-23 → iter-34
splice-spike (docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py).
These passes fix concrete quality issues observed across a 26-paper corpus:
JAMA Key Points sidebars, multi-line FIGURE / TABLE captions, compound
section headings (``CONCLUSIONS AND RELEVANCE``), numbered subsection
promotion (``### 1.2 Foo``), title rescue when pdftotext linearizes the
abstract column before the title, etc.

The pdfplumber-internal table-cleaning helpers from the spike
(``pdfplumber_table_to_markdown`` and the 7 helpers it calls) are deferred
to v2.3.0 — v2.2.0 uses Camelot for table cells.
"""

from __future__ import annotations

import re
from typing import Optional

from .extract_layout import LayoutDoc
from .extract_structured import extract_pdf_structured
from .normalize import NormalizationLevel
from .sections import extract_sections
from .tables.render import cells_to_html


__all__ = ["render_pdf_to_markdown"]


# v2.3.0: prettier fallback heading text for synthesized sections (those
# where heading_text is empty because the section detector synthesized it
# via Pattern E rather than reading a real heading line from the PDF).
# Maps canonical labels to the conventional academic heading.
_PRETTY_LABELS: dict[str, str] = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "methods": "Methods",
    "results": "Results",
    "discussion": "Discussion",
    "conclusion": "Conclusion",
    "references": "References",
    "acknowledgments": "Acknowledgments",
    "funding": "Funding",
    "data_availability": "Data Availability",
    "open_practices": "Open Practices",
    "supplementary": "Supplementary Material",
    "author_contributions": "Author Contributions",
    "conflict_of_interest": "Conflict of Interest",
}


def _pretty_label(label: str) -> str:
    """Return a presentable heading for a canonical section label."""
    s = (label or "").strip()
    if not s:
        return s
    if s in _PRETTY_LABELS:
        return _PRETTY_LABELS[s]
    # Generic fallback: title-case, replace underscores with spaces.
    return s.replace("_", " ").title()


# v2.3.1 Bug 6 fix (`docs/HANDOFF_2026-05-11_visual_review_findings.md`):
# papers print short publication-format badge text immediately below the
# title (e.g. "Registered Report", "Pre-Registered", "Stage 1 Registered
# Report"). Without this pass they render as a stray plain-text line just
# below the `# Title` block, with no visual cue that they're a subtitle.
# We italicize them so the workspace UI styles them distinctly.
_SUBTITLE_BADGE_PATTERNS = [
    re.compile(r"^Registered\s+Report(?:\s+Stage\s+[12])?\b", re.IGNORECASE),
    re.compile(r"^Stage\s+[12]\s+Registered\s+Report\b", re.IGNORECASE),
    re.compile(r"^Pre-?Registered(?:\s+Replication)?\b", re.IGNORECASE),
    re.compile(r"^Pre-?Registered\s+Report\b", re.IGNORECASE),
    re.compile(r"^Replication\s+Report\b", re.IGNORECASE),
    re.compile(r"^Original\s+Investigation\b", re.IGNORECASE),
    re.compile(r"^Research\s+Article\b", re.IGNORECASE),
    re.compile(r"^Brief\s+Report\b", re.IGNORECASE),
    re.compile(r"^Short\s+Report\b", re.IGNORECASE),
    re.compile(r"^Letter\s+to\s+the\s+Editor\b", re.IGNORECASE),
]


def _italicize_known_subtitle_badges(text: str) -> str:
    """Italicize known publication-format badge lines immediately after
    the ``# Title`` block.

    Scope: only the first non-empty content line(s) within ~10 lines of
    the ``# Title``, AND the line must be short (≤ 50 chars) AND match
    a recognized badge pattern. This avoids touching body prose that
    happens to contain the phrase.

    Idempotent: already-italicized badges (``*Registered Report*``) are
    left alone.
    """
    if "# " not in text:
        return text
    lines = text.split("\n")
    # Find the # Title line.
    title_idx = -1
    for i, ln in enumerate(lines):
        if re.match(r"^#\s+\S", ln):
            title_idx = i
            break
    if title_idx < 0:
        return text

    # Look at the next ~10 lines for a badge candidate. Stop on the
    # first ## heading (we've left the title block).
    n_lines = len(lines)
    changed = False
    for j in range(title_idx + 1, min(title_idx + 11, n_lines)):
        ln = lines[j].strip()
        if not ln:
            continue
        if ln.startswith("##"):
            break  # entered the next section
        if len(ln) > 50:
            continue  # likely body prose, not a badge
        # Already italicized — leave alone.
        if ln.startswith("*") and ln.endswith("*") and not ln.startswith("**"):
            continue
        # Check against badge patterns.
        for pat in _SUBTITLE_BADGE_PATTERNS:
            if pat.match(ln):
                lines[j] = f"*{ln}*"
                changed = True
                break
    if changed:
        return "\n".join(lines)
    return text


# ── Section B markdown-level post-processors ───────────────────────────────


def _dedupe_h2_sections(text: str) -> str:
    """Demote duplicate ``##`` headings to plain text (first occurrence wins).

    Two structural appendix headings (``## Figures``, ``## Tables (unlocated
    in body)``) are exempt.
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
            lines[i] = ""
            continue
        seen.add(heading_text)
    return "\n".join(lines)


_COMPOUND_HEADING_TAILS: list[tuple[str, str]] = [
    ("CONCLUSIONS", "AND RELEVANCE"),
    # Additional JAMA structured-abstract heads — per
    # HANDOFF_2026-05-11_PROMOTE_SPIKE_TO_LIBRARY.md §B, the spike only saw
    # CONCLUSIONS-AND-RELEVANCE in the wild but the library should be
    # defensive against the rest of the JAMA set.
    ("OBJECTIVE", "IMPORTANCE"),
    ("DESIGN", "SETTING, AND PARTICIPANTS"),
    ("MAIN", "OUTCOMES AND MEASURES"),
    ("INTERVENTIONS", "MAIN OUTCOMES AND MEASURES"),
]


def _merge_compound_heading_tails(text: str) -> str:
    """Reattach an orphan heading tail to the heading line.

    Rewrites::

        ## CONCLUSIONS

        AND RELEVANCE {body...}

    as::

        ## CONCLUSIONS AND RELEVANCE

        {body...}
    """
    if not text:
        return text
    for prefix, tail in _COMPOUND_HEADING_TAILS:
        pattern = re.compile(
            rf"^## {re.escape(prefix)}[ \t]*\n\n{re.escape(tail)}[ \t]+",
            re.MULTILINE,
        )
        text = pattern.sub(f"## {prefix} {tail}\n\n", text)
    return text


_NUMBERED_SUBSECTION_HEADING_RE = re.compile(
    r"^(?P<num>\d+(?:\.\d+){1,3})\s+"
    r"(?P<title>[A-Z][A-Za-z0-9][\w\-\s,&\(\)/']{1,78})\s*$"
)


def _promote_numbered_subsection_headings(text: str) -> str:
    """Promote ``1.2 Foo``-style lines to ``### 1.2 Foo`` h3 headings.

    Conservative: only multi-level numbering (``N.N`` or deeper), title must
    start with a capital letter, must not end in sentence-terminator
    punctuation, and must not look like prose (no long lowercase-word runs).
    Idempotent: re-running the pass is a no-op.
    """
    if not text:
        return text
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        m = _NUMBERED_SUBSECTION_HEADING_RE.match(line)
        if not m:
            out.append(line)
            continue
        title = m.group("title").rstrip()
        if title.endswith((".", "?", "!", ":", ",", ";")):
            out.append(line)
            continue
        tokens = title.split()
        lc_run = max_lc_run = 0
        for tok in tokens:
            if tok and tok[0].islower():
                lc_run += 1
                max_lc_run = max(max_lc_run, lc_run)
            else:
                lc_run = 0
        if max_lc_run >= 5:
            out.append(line)
            continue
        if out and out[-1].startswith(f"### {m.group('num')} "):
            out.append(line)
            continue
        num = m.group("num")
        if out and out[-1].strip():
            out.append("")
        out.append(f"### {num} {title}")
        out.append("")
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# ── H1 hyphen-broken-word rejoin (post-render, on rendered markdown) ────────


def _fix_hyphenated_line_breaks(text: str) -> str:
    """Re-knit real compound words split across caption / body line wraps.

    Runs on rendered markdown AFTER normalize.S7 has already removed
    column-wrap hyphens — by this point the remaining hyphen-at-EOL cases
    are real hyphenated compounds (``Meta-Processes``) that pdftotext split
    across the wrap. Conservative: always keeps the hyphen, only removes
    the newline. Skips ``<table>`` blocks, fenced code, markdown headings.
    """
    lines = text.split("\n")
    in_table = False
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        ls = line.strip()
        if ls.startswith("```"):
            in_fence = not in_fence
            i += 1
            continue
        if not in_fence:
            if "<table" in ls:
                in_table = True
            if "</table>" in ls:
                in_table = False
                i += 1
                continue
        if in_fence or in_table:
            i += 1
            continue
        if ls.startswith("#"):
            i += 1
            continue
        if (
            i + 1 < len(lines)
            and len(line) >= 3
            and line.endswith("-")
            and line[-2].isalpha()
        ):
            next_line = lines[i + 1]
            ns = next_line.strip()
            if ns and ns[0].isalpha():
                lines[i] = line + ns
                del lines[i + 1]
                continue
        i += 1
    return "\n".join(lines)


# ── Multi-line caption paragraph fold ──────────────────────────────────────


_MULTILINE_CAPTION_START_RE = re.compile(r"^(?:FIGURE|TABLE)\s+\d+", re.IGNORECASE)
_MULTILINE_CAPTION_TERMINATOR_RE = re.compile(r"[.!?)]\s*$")
_MULTILINE_CAPTION_BLOCK_NEXT_RE = re.compile(
    r"^(?:"
    r"#{1,6}\s|"
    r"<|"
    r"```|"
    r"(?:FIGURE|TABLE|FIG\.?)\s+\d+\b|"
    r"Note\s*[.:]|"
    r"\[\d+\]|"
    r"\d+[.)]\s|"
    r"[*+\-]\s"
    r")",
    re.IGNORECASE,
)


def _join_multiline_caption_paragraphs(text: str) -> str:
    """Fold ``FIGURE N`` / ``TABLE N`` captions that pdftotext split across
    a column wrap inside a single paragraph.

    Conditions for folding ``lines[i] + lines[i+1]``:
      - ``lines[i]`` starts with ``FIGURE N`` / ``TABLE N``.
      - ``lines[i]`` is ≥ 60 chars and does NOT end with a sentence terminator.
      - ``lines[i+1]`` (stripped) is short (≤80 chars, ≤15 words) and does
        NOT itself look like a caption start / heading / HTML / list item.

    Line-local — never crosses a blank-line boundary, so table-header rows
    in the next paragraph are not absorbed.
    """
    if not text:
        return text
    paragraphs = re.split(r"(\n\n+)", text)
    for idx in range(0, len(paragraphs), 2):
        para = paragraphs[idx]
        if not para or "\n" not in para:
            continue
        lead_len = len(para) - len(para.lstrip("\n"))
        trail_len = len(para) - len(para.rstrip("\n"))
        lead = para[:lead_len]
        trail = para[len(para) - trail_len:] if trail_len else ""
        body = para[lead_len:len(para) - trail_len]
        lines = body.split("\n")
        i = 0
        while i + 1 < len(lines):
            line0 = lines[i]
            line1 = lines[i + 1]
            line1_s = line1.strip()
            if (
                len(line0) >= 60
                and _MULTILINE_CAPTION_START_RE.match(line0)
                and not _MULTILINE_CAPTION_TERMINATOR_RE.search(line0)
                and line1_s
                and len(line1_s) <= 80
                and len(line1_s.split()) <= 15
                and not _MULTILINE_CAPTION_BLOCK_NEXT_RE.match(line1_s)
            ):
                lines[i] = line0 + " " + line1_s
                del lines[i + 1]
                continue
            i += 1
        paragraphs[idx] = lead + "\n".join(lines) + trail

    return "".join(paragraphs)


# ── Section D: JAMA Key Points sidebar reformat ─────────────────────────────


_KEY_POINTS_BLOCK_RE = re.compile(
    r"^(?P<question>Key Points Question [^\n]+\?)\s*\n+"
    r"## Findings\s*\n+"
    r"(?P<findings>[^\n]+)\n"
    r"(?P<meaning>Meaning [^\n]+)\s*\n+",
    re.MULTILINE,
)


def _reformat_jama_key_points_box(text: str) -> str:
    """Extract the JAMA Key Points sidebar and emit a clean blockquote.

    The sidebar wedges into the body in pdftotext reading order, splitting
    the abstract's CONCLUSIONS sentence and falsely promoting ``Findings``
    to a ``## Findings`` heading. This pass:
      1. Matches the canonical ``Key Points Question … ## Findings … Meaning …`` block.
      2. Stitches the split sentence when applicable.
      3. Emits the content as a markdown blockquote after the stitched
         sentence.

    Idempotent: once reformatted the regex no longer matches.
    """
    if not text:
        return text
    m = _KEY_POINTS_BLOCK_RE.search(text)
    if not m:
        return text

    question_text = m.group("question")[len("Key Points Question "):].rstrip()
    findings_text = m.group("findings").strip()
    meaning_text = m.group("meaning")[len("Meaning "):].strip()

    block_start, block_end = m.span()
    before = text[:block_start]
    after = text[block_end:]

    before_rstripped = before.rstrip()
    after_lstripped = after.lstrip()
    stitched = False
    if (
        before_rstripped
        and not re.search(r"[.!?:]\s*$", before_rstripped)
        and after_lstripped
        and re.match(r"[a-z]", after_lstripped)
    ):
        first_line, sep, rest = after_lstripped.partition("\n")
        first_line = first_line.strip()
        if first_line:
            before = before_rstripped + " " + first_line + "\n"
            after = ("\n" + rest) if sep else "\n"
            stitched = True

    kp_block = (
        "> **Key Points**\n"
        ">\n"
        f"> **Question:** {question_text}\n"
        ">\n"
        f"> **Findings:** {findings_text}\n"
        ">\n"
        f"> **Meaning:** {meaning_text}\n"
    )

    if stitched:
        return before.rstrip("\n") + "\n\n" + kp_block + "\n" + after.lstrip("\n")
    else:
        return before.rstrip() + "\n\n" + kp_block + "\n" + after.lstrip("\n")


# ── Section C: layout-channel title rescue ──────────────────────────────────


_TITLE_REJECT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^HHS Public Access", re.IGNORECASE),
    re.compile(r"^arXiv:", re.IGNORECASE),
    re.compile(r"^www\.", re.IGNORECASE),
    re.compile(r"^https?://"),
    re.compile(r"^Article\s+https?://", re.IGNORECASE),
    re.compile(r"^Cite this article", re.IGNORECASE),
    re.compile(r"^Author manuscript", re.IGNORECASE),
]


_BANNER_SPAN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^HHS Public Access\s*$", re.IGNORECASE),
    re.compile(r"^Author manuscript\s*$", re.IGNORECASE),
    re.compile(r"^Published in final edited form as:?\s*$", re.IGNORECASE),
    re.compile(r"^arXiv:\d", re.IGNORECASE),
    re.compile(r"^https?://"),
    re.compile(r"^www\."),
    re.compile(r"^Cite this article", re.IGNORECASE),
    re.compile(r"^Original Investigation\b", re.IGNORECASE),
    re.compile(r"^Original Article\b", re.IGNORECASE),
    re.compile(r"^Original Research\b", re.IGNORECASE),
    re.compile(r"^ARTICLE\s*$"),
    re.compile(r"^Article\s*$"),
    re.compile(r"^Research\s*$"),
    re.compile(r"^OPEN\s*$"),
    re.compile(r"^[A-Z][A-Za-z\s\.&]{2,60}\.\s+Author manuscript", re.IGNORECASE),
    re.compile(r"^Journal of Economic Psychology\s*$"),
    re.compile(r"^Cognition and Emotion\s*$"),
    re.compile(
        r"^Journal\s*of\s*Experimental\s*Social\s*Psychology"
        r"(?:\s*\d+(?:\s*\(\d{4}\))?\s+\d+[‐-―\-]\d+)?\s*$"
    ),
    re.compile(r"^Contents lists available at\s+\S", re.IGNORECASE),
    re.compile(r"^journal homepage:", re.IGNORECASE),
]


def _is_banner_span_text(text: str) -> bool:
    if not text:
        return False
    for pat in _BANNER_SPAN_PATTERNS:
        if pat.match(text):
            return True
    return False


def _title_text_from_chars(page1, y_min: float, y_max: float, title_size: float) -> Optional[str]:
    """Reconstruct title text from per-character pdfplumber records using an
    absolute x-gap rule.

    Used as a fallback when ``extract_words`` returned concatenated tokens
    on tight-kerned PDFs (JAMA, AOM). pdfplumber's default ``x_tolerance=3``
    misses these — the difference between a real title and
    ``EffectofTime-RestrictedEatingonWeightLoss``.
    """
    chars = getattr(page1, "chars", ()) or ()
    height = float(getattr(page1, "height", 0) or 0.0)
    if not chars or height <= 0:
        return None
    rows: list[dict] = []
    for c in chars:
        try:
            sz = float(c.get("size") or 0.0)
        except (TypeError, ValueError):
            continue
        if abs(sz - title_size) > 1.2:
            continue
        ct = c.get("top")
        cb = c.get("bottom")
        if ct is None or cb is None:
            continue
        try:
            c_y0 = height - float(cb)
            c_y1 = height - float(ct)
            x0 = float(c.get("x0", 0) or 0)
            x1 = float(c.get("x1", 0) or 0)
        except (TypeError, ValueError):
            continue
        if c_y0 < y_min - 1.5 or c_y1 > y_max + 1.5:
            continue
        ctext = c.get("text") or ""
        if not ctext:
            continue
        rows.append({
            "top": float(ct), "x0": x0, "x1": x1, "text": ctext,
            "width": max(x1 - x0, 0.0),
        })
    if not rows:
        return None
    rows.sort(key=lambda r: (round(r["top"]), r["x0"]))
    lines: list[list[dict]] = []
    current: list[dict] = []
    current_top: Optional[float] = None
    for r in rows:
        if current_top is None or abs(r["top"] - current_top) > 2.0:
            if current:
                lines.append(current)
            current = [r]
            current_top = r["top"]
        else:
            current.append(r)
    if current:
        lines.append(current)
    line_texts: list[str] = []
    for line in lines:
        line.sort(key=lambda r: r["x0"])
        out_chars: list[str] = []
        prev_x1: Optional[float] = None
        for r in line:
            if prev_x1 is not None:
                gap = r["x0"] - prev_x1
                if gap > 1.5:
                    out_chars.append(" ")
            out_chars.append(r["text"])
            prev_x1 = r["x1"]
        line_texts.append("".join(out_chars).strip())
    line_texts = [lt for lt in line_texts if lt]
    if not line_texts:
        return None
    return " ".join(line_texts)


def _compute_layout_title(layout_doc: LayoutDoc) -> Optional[str]:
    """Identify the article title from page-1 layout spans.

    Returns the best-guess title text or ``None`` if no candidate was
    confidently identified. Conservative: returns ``None`` rather than risk
    emitting a banner / running-header line as the title.
    """
    if layout_doc is None or not getattr(layout_doc, "pages", ()):
        return None
    page1 = layout_doc.pages[0]
    spans = getattr(page1, "spans", ())
    if not spans:
        return None
    height = float(getattr(page1, "height", 0) or 0.0)
    if height <= 0:
        return None

    upper_threshold = height * 0.40
    upper_spans = [s for s in spans if s.y0 > upper_threshold]
    if not upper_spans:
        return None

    upper_spans = [
        s for s in upper_spans
        if not _is_banner_span_text(s.text.strip() if s.text else "")
    ]
    if not upper_spans:
        return None

    from collections import Counter
    size_counts: Counter[float] = Counter(
        round(float(s.font_size) * 2) / 2 for s in upper_spans
    )
    title_size: Optional[float] = None
    # Pass 1: largest font with count >= 2 (the title typically spans
    # 2-3 lines).
    for sz, count in sorted(size_counts.items(), reverse=True):
        if sz >= 12.0 and count >= 2:
            title_size = sz
            break
    if title_size is None:
        # Pass 2: fall back to the largest font in the TOP region with
        # count >= 1 AND >= 10 chars of combined span text. The top-
        # region filter (y0 >= 70% of page height) rejects mid-page
        # decorations like a "+" badge or section-heading numerals.
        # The text-length filter rejects short feature-labels (e.g. AOM
        # papers' "GUIDEPOST" header at font 30) in favor of the longer
        # title block immediately below.
        top_region_threshold = height * 0.70
        top_spans = [s for s in upper_spans if s.y0 >= top_region_threshold]
        candidate_sizes = sorted(
            {round(float(s.font_size) * 2) / 2 for s in top_spans},
            reverse=True,
        )
        for sz in candidate_sizes:
            if sz < 14.0:
                break
            matching = [s for s in top_spans if abs(float(s.font_size) - sz) < 0.3]
            combined_text_len = sum(len((s.text or "").strip()) for s in matching)
            if combined_text_len >= 10:
                title_size = sz
                break
    if title_size is None:
        return None

    title_spans = [
        s for s in upper_spans if abs(float(s.font_size) - title_size) < 0.3
    ]
    if not title_spans:
        return None

    # Restrict title_spans to the contiguous top cluster. The title sits
    # at the highest y0 (pdfplumber bottom-origin coords). A stray same-
    # font glyph elsewhere on the page (e.g. a "V." section heading at
    # y0=450 while the title sits at y0=672, with a >200-px gap between
    # them) would otherwise stretch the y-band and swallow the byline +
    # abstract. Cluster spans top-down, breaking on the first big gap.
    title_spans_sorted = sorted(title_spans, key=lambda s: -s.y0)
    cluster: list = [title_spans_sorted[0]]
    for s in title_spans_sorted[1:]:
        prev_y0 = min(c.y0 for c in cluster)
        # Gap between this span's top edge (y1) and the cluster's bottom
        # edge (prev_y0). A multi-line title has line-spacing ~30-40px;
        # 100-px gap is comfortably larger than any real line break.
        if prev_y0 - s.y1 > 100.0:
            break
        cluster.append(s)
    title_spans = cluster

    y_min = min(s.y0 for s in title_spans)
    y_max = max(s.y1 for s in title_spans)

    title_word_recs: list[tuple[float, float, str]] = []
    words = getattr(page1, "words", ()) or ()
    for w in words:
        wt = w.get("top")
        wb = w.get("bottom")
        if wt is None or wb is None:
            continue
        try:
            w_height = float(w.get("height") or 0.0)
            w_y0 = height - float(wb)
            w_y1 = height - float(wt)
        except (TypeError, ValueError):
            continue
        # Height filter — relaxed from 0.6 to 3.5: a single tall glyph
        # (U+FFFD replacement, an italic emphasis on a name, etc.) can
        # balloon a title word's metric height by ~2.5 px (e.g. ziano's
        # "Shafir�s" h=15.99 vs the title's 13.45). 3.5 px keeps that
        # word while still rejecting a running-header URL in a smaller
        # font that sits on the same y-band as a multi-line title
        # (ar_royal_society_rsos: running header h=13.45 vs title 28.89).
        if w_height > 0 and abs(w_height - title_size) > 3.5:
            continue
        # Y-bbox slop of 3.0 px (was 1.5) catches tall-glyph words like
        # "Shafir�s" whose bbox extends 2.6 px above the line's normal
        # top.
        if w_y0 >= y_min - 3.0 and w_y1 <= y_max + 3.0:
            text = (w.get("text") or "").strip()
            if not text:
                continue
            try:
                x0 = float(w.get("x0", 0) or 0)
            except (TypeError, ValueError):
                x0 = 0.0
            title_word_recs.append((float(wt), x0, text))

    if title_word_recs:
        # Group into lines by ``top`` proximity (4-px tolerance, to
        # match the y-bbox slop above), then x-sort within each line.
        # Sorting by ``(round(top), x0)`` directly mis-orders tall-glyph
        # words like ziano's "Shafir�s" (top=164.4) — they bin to a
        # different "round(top)" than their neighbours (top=167.0) and
        # sort to the front.
        title_word_recs.sort(key=lambda t: t[0])
        line_recs: list[list[tuple[float, float, str]]] = []
        current_line_recs: list[tuple[float, float, str]] = []
        current_top: Optional[float] = None
        for top, x0, text in title_word_recs:
            if current_top is None or abs(top - current_top) > 4.0:
                if current_line_recs:
                    line_recs.append(current_line_recs)
                current_line_recs = [(top, x0, text)]
                current_top = top
            else:
                current_line_recs.append((top, x0, text))
                current_top = (current_top + top) / 2.0
        if current_line_recs:
            line_recs.append(current_line_recs)
        lines: list[list[str]] = []
        for line_rec in line_recs:
            line_rec.sort(key=lambda r: r[1])
            lines.append([text for _, _, text in line_rec])
        title_text = " ".join(" ".join(line) for line in lines).strip()
    else:
        title_text = ""

    space_token_count = len(title_text.split())
    if space_token_count < 4 and len(title_text) >= 25:
        char_text = _title_text_from_chars(page1, y_min, y_max, title_size)
        if char_text and len(char_text.split()) >= 4:
            title_text = char_text

    if not title_text:
        title_spans_sorted = sorted(title_spans, key=lambda s: (-s.y0, s.x0))
        title_text = " ".join(s.text for s in title_spans_sorted).strip()

    title_text = re.sub(r"\s+", " ", title_text).strip()
    if len(title_text) < 10 or len(title_text) > 500:
        return None
    for pat in _TITLE_REJECT_PATTERNS:
        if pat.match(title_text):
            return None
    letters = sum(1 for c in title_text if c.isalpha())
    if letters < len(title_text) * 0.5:
        return None
    if len(re.findall(r"[A-Za-z]{2,}", title_text)) < 2:
        return None
    return title_text


def _strip_duplicate_title_occurrences(
    text: str,
    title_text: str,
    *,
    start_offset_lines: int = 1,
) -> str:
    """Remove paragraph-spans in ``text`` whose token content matches
    ``title_text``.

    Some publishers (Nature Communications, Sci Reports) repeat the title
    further down page 1 in a smaller font — once the layout-title rescue
    has placed ``# Title`` at the top, these duplicate body blocks remain
    and render as plain paragraphs like the title broken across 2-3 lines.
    This sweeps them out.

    ``start_offset_lines`` skips the first N lines (which contain the
    placed title itself and immediately-following blank/byline lines). The
    sweep is bounded to the first 80 lines of ``text`` to avoid touching
    real body content that may legitimately reuse title words.
    """
    if not text or not title_text:
        return text
    title_tokens = re.findall(r"\w+", title_text.lower())
    if len(title_tokens) < 4:
        return text
    title_token_set = set(title_tokens)
    lines = text.split("\n")
    horizon = min(80, len(lines))
    i = max(0, start_offset_lines)
    while i < horizon:
        line = lines[i].strip()
        if not line or line.startswith("#"):
            i += 1
            continue
        # Greedy-extend up to 12 lines or until a heading. Blank lines DO
        # NOT break the span — Nature-style titles split across columns
        # come out as 2-3 short paragraphs separated by blank lines, and
        # we need to span them to accumulate enough title tokens to match.
        accumulated: list[str] = []
        j = i
        deleted = False
        blank_run = 0
        while j < min(i + 12, horizon):
            line_j = lines[j].strip()
            if line_j.startswith("#"):
                break
            if not line_j:
                blank_run += 1
                # Two consecutive blank lines = real section break; stop.
                if blank_run >= 2:
                    break
                j += 1
                continue
            blank_run = 0
            accumulated.extend(re.findall(r"\w+", lines[j].lower()))
            if len(accumulated) > len(title_tokens) * 2.5:
                break
            covered = sum(1 for t in title_tokens if t in accumulated)
            recall = covered / len(title_tokens)
            in_title = sum(1 for t in accumulated if t in title_token_set)
            precision = (in_title / len(accumulated)) if accumulated else 0.0
            # High bar: dup blocks share ~all title words with little else.
            if recall >= 0.85 and precision >= 0.75:
                # Extend ``j`` forward to absorb short trailing-orphan
                # fragments — Nature-style multi-column layouts leave a
                # 1-2 word remainder ("society", "follow-up") after the
                # main title span that on its own won't hit the recall
                # threshold. Stop on the first line with any non-title
                # token.
                k = j + 1
                while k < min(j + 6, horizon):
                    nxt = lines[k].strip()
                    if not nxt:
                        k += 1
                        continue
                    if nxt.startswith("#"):
                        break
                    nxt_toks = re.findall(r"\w+", nxt.lower())
                    if (
                        nxt_toks
                        and len(nxt_toks) <= 4
                        and all(t in title_token_set for t in nxt_toks)
                    ):
                        j = k
                        k += 1
                    else:
                        break
                del lines[i:j + 1]
                horizon = min(80, len(lines))
                deleted = True
                break
            j += 1
        if not deleted:
            i += 1
        # If deleted: don't advance i — re-check in case a second duplicate
        # follows immediately.
    out = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", out)


def _apply_title_rescue(out: str, title_text: str) -> str:
    """Place ``# {title_text}`` correctly at the top of ``out``."""
    if not out or not title_text:
        return out

    out_lines = out.split("\n")
    head_30 = out_lines[:30]
    if any(re.match(r"^# [^#\s]", line) for line in head_30):
        return out

    title_block = f"# {title_text}\n"

    title_tokens = re.findall(r"\w+", title_text.lower())
    if len(title_tokens) < 3:
        return title_block + "\n" + out
    title_token_set = set(title_tokens)

    head_lines = out_lines[:50]
    first_h2_idx = next(
        (k for k, l in enumerate(head_lines) if l.lstrip().startswith("## ")),
        None,
    )

    best: Optional[tuple[int, int, float]] = None
    for i in range(len(head_lines)):
        line_i = head_lines[i].strip()
        if not line_i:
            continue
        if line_i.startswith("#"):
            continue
        accumulated: list[str] = []
        for j in range(i, min(i + 12, len(head_lines))):
            line_j = head_lines[j].strip()
            if not line_j:
                break
            if line_j.startswith("#"):
                break
            tokens = re.findall(r"\w+", head_lines[j].lower())
            accumulated.extend(tokens)
            if len(accumulated) > len(title_tokens) * 2.5:
                break
            covered = sum(1 for t in title_tokens if t in accumulated)
            recall = covered / len(title_tokens)
            if recall >= 0.85 and accumulated:
                in_title = sum(1 for t in accumulated if t in title_token_set)
                precision = in_title / len(accumulated)
                if precision >= 0.6:
                    score = recall + precision
                    if best is None or score > best[2]:
                        best = (i, j, score)

    if best is None:
        prefixed = title_block + "\n" + out
        return _strip_duplicate_title_occurrences(prefixed, title_text, start_offset_lines=2)

    s_idx, e_idx, _ = best
    if first_h2_idx is not None and s_idx > first_h2_idx:
        new_lines = out_lines[:s_idx] + out_lines[e_idx + 1:]
        new_text = "\n".join(new_lines)
        new_text = re.sub(r"\n{3,}", "\n\n", new_text)
        prefixed = title_block + "\n" + new_text
        return _strip_duplicate_title_occurrences(prefixed, title_text, start_offset_lines=2)

    # In-place upgrade: replace the matched title lines with `# Title`.
    # Pad the heading with blank lines on each side so downstream markdown
    # renderers treat it as a standalone block, not as text glued to the
    # adjacent paragraphs (which would produce "RESEARCH ARTICLE # Title"
    # all on one logical paragraph in HTML output).
    new_lines = (
        out_lines[:s_idx]
        + ["", title_block.rstrip("\n"), ""]
        + out_lines[e_idx + 1:]
    )
    new_text = "\n".join(new_lines)
    new_text = re.sub(r"\n{3,}", "\n\n", new_text)
    # Sweep any *additional* title duplicates remaining in the body
    # (Nature Communications-style repeat of the title in smaller font).
    # The placed title sits at s_idx; start the sweep just after it.
    return _strip_duplicate_title_occurrences(
        new_text, title_text, start_offset_lines=s_idx + 3
    )


# v2.3.0 Bug 5 — connector-word guard. A rescued title that ends in a
# connector (``of``, ``from``, ``for``, ``the``, ``and``, etc.) is almost
# certainly truncated mid-sentence by the layout-title font-boundary
# filter. Better to skip rescue than render a fragment as ``# Title``.
# Per `docs/HANDOFF_2026-05-11_visual_review_findings.md` Bug 5.
_TITLE_CONNECTOR_TAIL_WORDS = frozenset({
    "of", "from", "for", "the", "and", "or", "to", "with", "on", "at",
    "by", "in", "as", "is", "a", "an", "but", "into", "onto", "upon",
    "than", "that", "which", "who", "when", "where", "while", "during",
    "after", "before", "because", "since", "though", "although",
})


def _title_looks_truncated(title_text: str) -> bool:
    """True if ``title_text`` ends with a connector word.

    Used to gate ``_rescue_title_from_layout`` — a layout title ending in
    ``of``/``and``/``the``/etc. is almost certainly truncated mid-sentence
    by the dominant-font filter (e.g., a subtitle in a slightly smaller
    font on the second line gets excluded from the title span).
    """
    if not title_text:
        return False
    # Strip trailing punctuation / whitespace; lowercase for lookup.
    stripped = re.sub(r"[\s\.,;:!?\-—–]+$", "", title_text).lower()
    if not stripped:
        return False
    last_word = stripped.rsplit(None, 1)[-1] if " " in stripped else stripped
    return last_word in _TITLE_CONNECTOR_TAIL_WORDS


def _rescue_title_from_layout(out: str, layout_doc: Optional[LayoutDoc]) -> str:
    """Compute the layout title and place it at the top of ``out``.

    Failure-tolerant: returns ``out`` unchanged if ``layout_doc`` is missing
    or the title cannot be confidently identified.

    v2.3.0: skips rescue when the candidate title ends in a connector word
    (``of``/``from``/``the``/...). Such fragments indicate the layout
    title detector truncated mid-sentence; rendering them as ``# Title``
    yields nonsense like ``# Revisiting the effects of helper intentions
    on gratitude and indebtedness: Replication and extensions Registered
    Report of`` (real example from the 2026-05-11 visual review).
    """
    if not out or layout_doc is None:
        return out
    title_text = _compute_layout_title(layout_doc)
    if not title_text:
        return out
    if _title_looks_truncated(title_text):
        return out
    return _apply_title_rescue(out, title_text)


# ── Markdown emission ──────────────────────────────────────────────────────


# Caption-line shape: label + period + space + Capital letter — strong signal
# that we landed on the actual caption block rather than a body reference like
# "see Figure 1" or "Figure 1 shows ...". The Capital after the period is what
# distinguishes a caption (which always begins with a Capital noun) from a
# body sentence ("Figure 1 shows..." has lowercase after the number).
_CAPTION_LINE_LOOKAHEAD = re.compile(r"\s+[A-Z]")


def _locate_caption_anchor(text: str, label: str, caption: str) -> int:
    """Locate the char offset of a Table/Figure caption inside ``text``.

    Whitespace-tolerant: caption text comes from ``_extract_caption_text``
    with newlines flattened to spaces, but ``text`` (the SectionedDocument's
    normalized text) preserves paragraph breaks. A naive ``text.find(cap)``
    returns -1 because the embedded newline doesn't match.

    Strategy:
      1. Try the **full** caption (exact match — covers the case where
         normalize didn't reflow any whitespace).
      2. Try the **label prefix** ("Figure N.") followed by the first few
         caption tokens, allowing any whitespace run between tokens.
      3. Validate the match is a caption-line start (followed by a Capital
         letter, not a lowercase word like "shows").
      4. If multiple matches, prefer the one farther into the document
         (real captions appear later; "see Figure 1" body refs appear early).

    Returns -1 when no plausible anchor is found. The caller routes
    unlocated tables/figures to the appendix rather than placing them at
    position 0 (the v2.2.0 behavior that produced Bug 3 — every figure
    piled up before the abstract).
    """
    if not text or not caption:
        return -1

    # Try 1: exact match (fast, common case).
    idx = text.find(caption)
    if idx >= 0:
        return idx

    # Try 2: build a whitespace-tolerant regex from a short prefix of the
    # caption. Take label + first ~6 word-tokens.
    label_clean = (label or "").strip()
    # Split the caption into tokens, drop the label tokens if they prefix
    # the caption (we'll add them back as the anchor).
    cap_tokens = caption.split()
    if not cap_tokens:
        return -1
    # Drop label words from the front so the prefix focuses on the content
    # words that disambiguate from body references.
    label_words = label_clean.split() if label_clean else []
    content_tokens = cap_tokens
    if label_words and len(cap_tokens) >= len(label_words):
        if [t.rstrip(".:") for t in cap_tokens[:len(label_words)]] == [
            w.rstrip(".:") for w in label_words
        ]:
            content_tokens = cap_tokens[len(label_words):]

    # Use at most 8 tokens for the prefix; this is usually unique to the
    # caption in the whole document.
    prefix_tokens = content_tokens[:8]
    if len(prefix_tokens) < 2:
        # Too short to be a unique anchor — fall back to the longer
        # full-caption attempt to avoid false matches.
        return -1

    # Build a regex: label + ws + each prefix token separated by ws.
    pieces = []
    if label_clean:
        pieces.append(re.escape(label_clean))
        pieces.append(r"[\s.:]+")  # punctuation/whitespace after label
    pieces.extend(
        token if i == 0 else r"\s+" + token
        for i, token in enumerate(re.escape(t) for t in prefix_tokens)
    )
    pattern = re.compile("".join(pieces))

    # Find all candidate matches; prefer later positions (real captions
    # generally come later than body references in the prose).
    matches = list(pattern.finditer(text))
    if not matches:
        return -1
    # Filter by caption-line shape: the char right after the match should be
    # whitespace + a Capital letter (caption sentence) or end-of-paragraph.
    # If no candidate passes, fall back to the latest match.
    plausible = []
    for m in matches:
        tail = text[m.end():m.end() + 10]
        if _CAPTION_LINE_LOOKAHEAD.match(tail) or not tail.strip():
            plausible.append(m)
    chosen = plausible[-1] if plausible else matches[-1]
    return chosen.start()


def _render_sections_to_markdown(
    sectioned, tables: list[dict], figures: list[dict]
) -> str:
    """Render a SectionedDocument as markdown, splicing tables and figures.

    Each section becomes a ``## {heading}`` block. Tables whose caption maps
    to a section page are emitted as ``### {label}\\n*{caption}*\\n{html}``
    inside the section. Unmatched tables and all figures land in trailing
    ``## Tables (unlocated in body)`` / ``## Figures`` appendix sections.
    """
    if not sectioned.sections:
        return sectioned.normalized_text

    # Group tables/figures by the section they fall inside, using char_offsets.
    # Tables expose a caption + a "page" key but not a char offset; we splice
    # by walking each section's char_start..char_end window and dropping a
    # table reference at its caption-line position in the normalized text.
    text = sectioned.normalized_text

    # Build an index of (char_start, table_or_figure) by searching for the
    # table/figure caption text inside ``text``.
    #
    # v2.3.0 fix for Bug 3 (figures spliced before abstract; per
    # ``docs/HANDOFF_2026-05-11_visual_review_findings.md``): the previous
    # ``text.find(cap)`` was too fragile — caption text was extracted with
    # newlines flattened to spaces by ``_extract_caption_text``, but
    # ``sectioned.normalized_text`` preserves paragraph breaks. The exact-
    # match find() returned -1, and the fallback ``placements.append((0, …))``
    # piled every figure at the top of the document, ahead of the abstract.
    # ``_locate_caption_anchor`` below is whitespace-tolerant and verifies the
    # match is at a caption-line start, not a body reference ("see Figure 1").
    #
    # Tables/figures that can't be located inline land in
    # ``unlocated_tables`` / ``unlocated_figures`` and are emitted in the
    # appendix at the bottom of the rendered output. They are NOT spliced
    # at position 0 — that was the v2.2.0 behavior that produced Bug 3.
    placements: list[tuple[int, str, dict]] = []
    unlocated_tables: list[dict] = []
    unlocated_figures: list[dict] = []
    for t in tables:
        idx = _locate_caption_anchor(text, t.get("label") or "Table", t.get("caption") or "")
        if idx >= 0:
            placements.append((idx, "table", t))
        else:
            unlocated_tables.append(t)
    for f in figures:
        idx = _locate_caption_anchor(text, f.get("label") or "Figure", f.get("caption") or "")
        if idx >= 0:
            placements.append((idx, "figure", f))
        else:
            unlocated_figures.append(f)

    placements.sort(key=lambda p: p[0])
    consumed: set[int] = set()

    out_chunks: list[str] = []
    for sec in sectioned.sections:
        # Suppress headings for sections the detector couldn't label
        # confidently — they have no semantic heading text and the canonical
        # label is "unknown". Emit the body as bare paragraphs instead so
        # the rendered .md doesn't show a cosmetic "## unknown" wedge.
        canonical = (
            sec.canonical_label.value
            if hasattr(sec.canonical_label, "value")
            else str(sec.canonical_label)
        )
        skip_heading = (
            canonical == "unknown" and not sec.heading_text
        )
        if not skip_heading:
            heading = sec.heading_text or _pretty_label(sec.label)
            # v2.4.2: when the heading_text the section detector captured is
            # entirely lowercase (Elsevier "a b s t r a c t" letter-spaced
            # typography → pdftotext flattens to "abstract") AND the section
            # has a recognized canonical label, prefer the pretty Title-Case
            # form. Without this fix the rendered output reads ``## abstract``
            # alongside ``## Methods``/``## Results`` — a stylistic blemish
            # that surfaces on every Elsevier (JESP, Cognition, JEP) paper.
            if (
                heading
                and heading == heading.lower()
                and heading.isascii()
                and any(c.isalpha() for c in heading)
                and canonical != "unknown"
            ):
                pretty = _pretty_label(sec.label)
                if pretty and pretty != heading:
                    heading = pretty
            # \n\n (not \n) separates heading from body so downstream
            # markdown renderers treat them as a heading block + paragraph,
            # not as one mashed paragraph starting with "## Abstract ...".
            out_chunks.append(f"## {heading}\n\n")
        # Section body — splice in any tables/figures whose anchor falls
        # inside this section's char window.
        body_text = sec.text.strip()
        # Drop the leading heading word when the section detector kept it in
        # the body (common for Abstract/Keywords where the PDF puts the
        # heading and body on one line — without this we render
        # "## Abstract\n\nAbstract Lynching ..." with the word duplicated).
        if not skip_heading and sec.heading_text:
            heading_clean = sec.heading_text.strip()
            if heading_clean and body_text.lower().startswith(heading_clean.lower()):
                rest = body_text[len(heading_clean):]
                if not rest or rest[0] in " \t\n:.;,":
                    body_text = rest.lstrip(" \t:.;,\n")
        body_chunks: list[str] = [body_text]
        in_section = [
            (p_idx, kind, item)
            for p_idx, kind, item in placements
            if sec.char_start <= p_idx < sec.char_end and id(item) not in consumed
        ]
        for p_idx, kind, item in in_section:
            consumed.add(id(item))
            label = item.get("label") or ("Table" if kind == "table" else "Figure")
            cap = item.get("caption") or ""
            if kind == "table":
                cells = item.get("cells") or []
                html = item.get("html") or (cells_to_html(cells) if cells else "")
                if html:
                    body_chunks.append(f"\n### {label}\n")
                    if cap:
                        body_chunks.append(f"*{cap}*\n")
                    body_chunks.append(html)
                elif cap:
                    # v2.4.2: Camelot returned no cells for this caption.
                    # Skip the `### Table N` heading (which would falsely
                    # promise structured content) and emit the caption as a
                    # plain italicized paragraph so the table reference is
                    # preserved in body flow. Affected papers in the
                    # 101-PDF corpus: bjps_4, ar_apa_j_jesp_2009_12_011.
                    body_chunks.append(f"\n*{cap}*\n")
            else:
                body_chunks.append(f"\n### {label}\n")
                if cap:
                    body_chunks.append(f"*{cap}*\n")
        out_chunks.append("\n".join(body_chunks))
        out_chunks.append("\n\n")

    # Appendix: unconsumed tables/figures.
    # Two sources: (1) items in placements that no section claimed (idx fell
    # outside every section's char window), (2) items we could never anchor
    # (unlocated_*). Both still need to surface so the user doesn't lose them.
    leftover_tables = [t for _, k, t in placements if k == "table" and id(t) not in consumed]
    leftover_tables.extend(unlocated_tables)
    leftover_figures = [f for _, k, f in placements if k == "figure" and id(f) not in consumed]
    leftover_figures.extend(unlocated_figures)

    if leftover_tables:
        # v2.4.2: drop tables that have neither a caption nor structured
        # HTML — emitting a bare ``### Table N`` header in the appendix
        # adds no information and clutters the output.
        renderable_tables = [
            t for t in leftover_tables
            if (t.get("caption") or "").strip()
            or t.get("html")
            or t.get("cells")
        ]
        if renderable_tables:
            out_chunks.append("## Tables (unlocated in body)\n\n")
            for t in renderable_tables:
                label = t.get("label") or "Table"
                cap = t.get("caption") or ""
                cells = t.get("cells") or []
                html = t.get("html") or (cells_to_html(cells) if cells else "")
                out_chunks.append(f"### {label}\n")
                if cap:
                    out_chunks.append(f"*{cap}*\n")
                if html:
                    out_chunks.append(html + "\n")
                out_chunks.append("\n")

    if leftover_figures:
        out_chunks.append("## Figures\n\n")
        for f in leftover_figures:
            label = f.get("label") or "Figure"
            cap = f.get("caption") or ""
            out_chunks.append(f"### {label}\n")
            if cap:
                out_chunks.append(f"*{cap}*\n")
            out_chunks.append("\n")

    md = "".join(out_chunks)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


# ── Public entry point ─────────────────────────────────────────────────────


def render_pdf_to_markdown(
    pdf_bytes: bytes,
    *,
    normalization_level: NormalizationLevel = NormalizationLevel.standard,
    _structured: Optional[dict] = None,
    _sectioned=None,
    _layout_doc: Optional[LayoutDoc] = None,
) -> str:
    """Render a PDF as a complete markdown document.

    Pipeline:
      1. ``extract_pdf_structured`` — text + Camelot tables + figures.
      2. ``extract_sections`` (text=…, source_format='pdf') — section structure.
      3. Emit ``## {heading}`` sections, splicing tables / figures by caption
         position.
      4. Run markdown-level post-processors (in spike order):
            - ``_dedupe_h2_sections``
            - ``_fix_hyphenated_line_breaks``
            - ``_join_multiline_caption_paragraphs``
            - ``_merge_compound_heading_tails``
            - ``_reformat_jama_key_points_box``
            - ``_promote_numbered_subsection_headings``
            - ``_rescue_title_from_layout``  (needs pdfplumber layout)

    Args:
        pdf_bytes: Raw PDF bytes.
        normalization_level: Forwarded to ``extract_sections`` via the
            normalize step. Default is ``standard``; pass ``academic`` to
            also apply statistical-expression repairs.
        _structured: Optional pre-computed ``extract_pdf_structured`` result
            (StructuredResult dict). Pass this when the caller has already
            run structured extraction — skips a duplicate Camelot pass that
            costs 10–40s on real papers. Internal-use optimization;
            underscored to discourage casual library users from depending
            on a shape that may change.
        _sectioned: Optional pre-computed ``extract_sections`` result
            (SectionedDocument). Pass this when sections have already been
            computed — skips a duplicate pdftotext + normalize + annotate
            pass that costs 4–8s on real papers.
        _layout_doc: Optional pre-computed ``extract_pdf_layout`` result
            for the title-rescue annotator. Pass to skip a third pdfplumber
            pass.

    Returns:
        Markdown text suitable for direct ``.md`` output. Includes a ``# Title``
        line when the layout-channel title rescue succeeds.
    """
    # 1. Structured extraction (text + Camelot tables + figures).
    if _structured is not None:
        structured = _structured
    else:
        structured = extract_pdf_structured(pdf_bytes)
    if structured["text"].startswith("ERROR:"):
        return structured["text"]

    # 2. Section detection from the raw text. extract_sections internally
    #    re-runs extract_pdf + normalize_text on the bytes — we let it do
    #    that so the normalized_text it stores aligns with the section
    #    char_offsets it produces.
    if _sectioned is not None:
        sectioned = _sectioned
    else:
        sectioned = extract_sections(pdf_bytes, source_format="pdf")

    # 3. Render sections + splice tables/figures.
    md = _render_sections_to_markdown(
        sectioned, structured["tables"], structured["figures"]
    )

    # 4. Post-process (spike pipeline order).
    md = _dedupe_h2_sections(md)
    md = _fix_hyphenated_line_breaks(md)
    md = _join_multiline_caption_paragraphs(md)
    md = _merge_compound_heading_tails(md)
    md = _reformat_jama_key_points_box(md)
    md = _promote_numbered_subsection_headings(md)

    # 5. Title rescue — only available when pdfplumber layout extracts cleanly.
    if _layout_doc is not None:
        layout_doc = _layout_doc
    else:
        try:
            from .extract_layout import extract_pdf_layout
            layout_doc = extract_pdf_layout(pdf_bytes)
        except Exception:
            layout_doc = None
    md = _rescue_title_from_layout(md, layout_doc)
    md = _italicize_known_subtitle_badges(md)

    return md.rstrip() + "\n"
