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
from .normalize import (
    NormalizationLevel,
    _rejoin_garbled_ocr_headers,
    decompose_ligatures,
    destyle_math_alphanumeric,
    recover_corrupted_lt_operator,
    recover_corrupted_minus_signs,
    recover_minus_via_ci_pairing,
)
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


# v2.4.41 (cycle 9, G5): the number group tolerates an optional trailing
# dot — `5.1.`, `5.3.3.`, `1.1.` are the dominant subsection-numbering style
# in Cambridge/JDM and Elsevier papers (`5.1. Participants`), and the prior
# `\s+`-after-digits requirement rejected every one of them, demoting the
# heading to body text. The title may also carry an internal colon
# (`6.1.1. Replication: Retrospective hindsight bias`) — a colon mid-title
# is ordinary heading typography; a colon as the LAST char is still rejected
# downstream (`title.endswith(":")`).
_NUMBERED_SUBSECTION_HEADING_RE = re.compile(
    r"^(?P<num>\d+(?:\.\d+){1,3}\.?)\s+"
    r"(?P<title>[A-Z][A-Za-z0-9][\w\-\s,&\(\)/':]{1,78})\s*$"
)


def _promote_numbered_subsection_headings(text: str) -> str:
    """Promote ``1.2 Foo``-style lines to ``### 1.2 Foo`` h3 headings.

    Conservative: only multi-level numbering (``N.N`` or deeper), title must
    start with a capital letter and must not end in sentence-terminator
    punctuation. Multi-level dotted numbering at line-start is itself a strong
    section-heading signal — descriptive subsection titles legitimately run to
    many lowercase words ("3.3.2.1 The quality of planning on the previous
    trial moderates the effect of reflection"), so a lowercase-run prose guard
    mis-rejects real headings and is not applied here (cycle 13, G5b).
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


# ── Single-level numbered section-heading promotion (cycle 11, G5a) ─────────

_SINGLE_LEVEL_NUM_HEADING_RE = re.compile(
    r"^(?P<num>\d{1,2})\.\s+"
    r"(?P<title>[A-Z][A-Za-z0-9][\w\-\s,&\(\)/':]{1,78})\s*$"
)
# An already-emitted numbered heading at any depth (## / ### / ####). The
# captured group is the TOP-level number.
_EXISTING_NUMBERED_HEADING_RE = re.compile(r"^#{2,4}\s+(\d{1,2})(?:\.\d+)*\.?\s")


def _promote_numbered_section_headings(text: str) -> str:
    """Promote single-level ``N. Title`` lines (e.g. ``2. Omission neglect``)
    to ``## N. Title`` h2 headings.

    Single-level top-level numbered headings are demoted to body text when the
    title is not a canonical section word. Promoting them safely needs a
    document-internal-consistency gate: the document must already number its
    sections (≥1 existing ``#{2,4} N`` heading), and the candidate's number
    must fall in a contiguous integer run that connects to a proven number.
    That gate is what prevents an enumerated list (e.g. exclusion criteria
    ``1. … 2. … 3. …``) from being promoted — list numbers do not connect to
    the document's section-numbering range, and a number that repeats (a list
    restarting at 1) is excluded by the uniqueness test.

    Runs AFTER the orphan-numeral folders so ``## 1. Introduction`` exists as
    an anchor. Idempotent.
    """
    if not text:
        return text
    lines = text.split("\n")
    proven_any: set[int] = set()   # top-numbers of any existing #/##/### heading
    proven_h2: set[int] = set()    # top-numbers that already have a real `## N.`
    for line in lines:
        m = _EXISTING_NUMBERED_HEADING_RE.match(line)
        if not m:
            continue
        n = int(m.group(1))
        proven_any.add(n)
        if line.startswith("## ") and not line.startswith("### "):
            proven_h2.add(n)
    if not proven_any:
        return text

    def _adjacent_numbered(idx_iter) -> bool:
        # True if the nearest non-blank line in idx_iter is itself a
        # single-level `N. ` line — i.e. the candidate sits inside a numbered
        # LIST, not at a section boundary.
        for j in idx_iter:
            s = lines[j].strip()
            if not s:
                continue
            return bool(re.match(r"^\d{1,2}\.\s", s))
        return False

    # Clean single-level numbered candidates. A demoted section heading sits
    # on its own line BETWEEN body paragraphs (not blank-separated); a list
    # item sits adjacent to a sibling `N. ` line. We require the former.
    candidates: dict[int, list[tuple[int, str]]] = {}
    in_fence = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _SINGLE_LEVEL_NUM_HEADING_RE.match(line)
        if not m:
            continue
        if _adjacent_numbered(range(i - 1, -1, -1)) or _adjacent_numbered(
            range(i + 1, len(lines))
        ):
            continue  # inside a numbered list, not a section boundary
        title = m.group("title").rstrip()
        if title.endswith((".", "?", "!", ":", ",", ";")):
            continue
        lc_run = max_lc = 0
        for tok in title.split():
            if tok and tok[0].islower():
                lc_run += 1
                max_lc = max(max_lc, lc_run)
            else:
                lc_run = 0
        if max_lc >= 8:  # long prose-like run — not a heading (cycle 13, G5b)
            continue
        candidates.setdefault(int(m.group("num")), []).append((i, title))
    if not candidates:
        return text
    # Only numbers that appear exactly once are section-heading candidates;
    # a repeated number is a restarting list, not a section sequence.
    uniq = {n for n, occ in candidates.items() if len(occ) == 1}
    # Eligible = numbers in a contiguous integer run (over proven ∪ uniq)
    # that contains at least one proven number.
    universe = sorted(proven_any | uniq)
    eligible: set[int] = set()
    run: list[int] = []
    for n in universe:
        if run and n == run[-1] + 1:
            run.append(n)
        else:
            if any(x in proven_any for x in run):
                eligible |= set(run)
            run = [n]
    if any(x in proven_any for x in run):
        eligible |= set(run)
    for num in uniq & eligible:
        if num in proven_h2:
            continue  # section N already has its own `## N.` heading
        i, title = candidates[num][0]
        lines[i] = f"## {num}. {title}"
    return "\n".join(lines)


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


# ── Section C4: false single-word heading demotion ──────────────────────────


_FALSE_HEADING_RE = re.compile(r"^(#{2,3})\s+(?P<word>[A-Z][A-Za-z]{2,12})\s*$")

# Strong canonical section names — never demote even when followed by a
# lowercase or digit continuation. These are unambiguous section markers
# whose authoritative source is the document structure, not the surrounding
# prose. The RSOS-family regression (v2.4.9) showed that ``## Discussion``
# followed by body prose starting with ``of this study...`` got demoted —
# losing the section. Same for ``## References\n\n1. Öhman A...``.
_STRONG_SECTION_NAMES = frozenset({
    "abstract", "introduction", "background", "methods", "method",
    "materials", "results", "discussion", "discussions", "conclusion",
    "conclusions", "references", "bibliography", "acknowledgments",
    "acknowledgements", "funding", "limitations", "supplementary",
    "appendix", "keywords",
})


def _demote_false_single_word_headings(text: str) -> str:
    """Demote ``## Word`` / ``### Word`` lines that are mid-prose continuations.

    Audit of the v2.4.0 101-paper corpus found 197 false single-word section
    headings (24% of all such headings). Pattern: ``## Results`` (line N)
    followed by ``of Study 1`` (line N+1) — the heading text was originally
    one paragraph ("Results of Study 1") that pdftotext split across a column
    wrap; the section detector then promoted the first line to a heading and
    left the continuation behind.

    Rules to demote:
      1. Heading matches ``^(##|###)\\s+[A-Z][a-z]{2,12}\\s*$`` (single short
         capitalized word).
      2. Next non-blank, non-heading line starts with a lowercase letter, a
         digit, OR a continuation particle (``of``, ``from``, ``and``,
         ``for``, ``in``, ``shows``, etc.).
      3. The heading word itself is NOT a strong, unambiguous section
         marker (we keep ``## Abstract``, ``## Introduction``, ``## Methods``,
         ``## Discussion``, ``## References`` when they ARE followed by a
         capitalized sentence — those are not demoted).

    Demote = replace the heading line with the plain word (no leading
    ``##``), then re-join with the next paragraph if appropriate.
    """
    if not text:
        return text
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _FALSE_HEADING_RE.match(line)
        if not m:
            out.append(line)
            i += 1
            continue
        # v2.4.9: never demote strong canonical section names. The body
        # text following `## Discussion` or `## References` can start with
        # lowercase prose / numbered list ("of this study...", "1. Öhman A..."),
        # but the heading itself is authoritative.
        if m.group("word").lower() in _STRONG_SECTION_NAMES:
            out.append(line)
            i += 1
            continue
        # Find the next non-blank line.
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            out.append(line)
            i += 1
            continue
        next_line = lines[j].lstrip()
        # Heuristic: a single-word heading followed by a lowercase or digit
        # first-char paragraph is almost always a column-wrap split of one
        # original heading line (``Results of Study 1`` → ``## Results`` +
        # ``of Study 1``). Skip the lookahead for proper-sentence starts.
        first_char = next_line[:1]
        # v2.4.9: don't demote when the next line is a numbered subsection
        # (``3.1. Subjects``, ``3.1 Subjects``, ``4.1. Do seasonal``).
        # Royal Society RSOS papers use ``## Methods\n\n3.1. Subjects`` as
        # a legitimate section + numbered-subsection structure. The
        # `_promote_numbered_subsection_headings` post-processor will lift
        # those into ``### 3.1 Subjects`` headings.
        if re.match(r"^\d+(?:\.\d+){1,3}\.?\s+\w", next_line):
            out.append(line)
            i += 1
            continue
        is_continuation = bool(
            first_char and (first_char.islower() or first_char.isdigit())
        )
        if not is_continuation:
            out.append(line)
            i += 1
            continue
        # Demote: emit the bare word (no ##) and let it flow into the next
        # paragraph naturally. Preserve the same blank-line structure as a
        # normal paragraph would have.
        word = m.group("word")
        out.append(word + " " + next_line.rstrip())
        # Consume the next line we just merged.
        i = j + 1
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# ── HALLUC-HEAD-1 (v2.4.53): CRediT contributor-role heading demotion ─────
#
# The CRediT (Contributor Roles Taxonomy) block of a paper lists the 14
# standard contribution roles. One of them — "Methodology" — collides with
# the canonical Method/Methodology *section* keyword, so the section
# partitioner promotes that role token to a ``## Methodology`` heading even
# though it sits inside the contributor-roles table, not at a real section
# boundary (chan_feldman, chandrashekar, chen). A role token is only a
# false heading when it is surrounded by OTHER role tokens — a real
# Methodology section is followed by method prose, not a role list.

# Normalized CRediT role forms: lowercased, ``&``→``and``, dash/slash → space,
# whitespace-collapsed. See :func:`_normalize_credit_role`.
_CREDIT_ROLES = frozenset({
    "conceptualization",
    "data curation",
    "formal analysis",
    "funding acquisition",
    "investigation",
    "methodology",
    "project administration",
    "resources",
    "software",
    "supervision",
    "validation",
    "visualization",
    "visualisation",
    "writing",
    "writing original draft",
    "writing review and editing",
    "writing original draft preparation",
})


def _normalize_credit_role(line: str) -> str:
    """Normalize a line for CRediT-role matching."""
    s = line.strip().lstrip("#").strip()
    s = s.replace("&", " and ")
    s = re.sub(r"[-–—/]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def _demote_credit_role_headings(text: str) -> str:
    """Demote a ``## <CRediT-role>`` heading that sits inside the
    contributor-roles block.

    HALLUC-HEAD-1: the section partitioner promotes the CRediT role token
    ``Methodology`` to a ``## Methodology`` heading because it collides
    with the Method/Methodology section keyword. The heading is false
    only when it is embedded in the role list — so demote it ONLY when
    the surrounding ±10-line window holds at least 3 OTHER CRediT role
    tokens. A real Methodology section heading is followed by method
    prose (0 nearby role tokens) and is left untouched.
    """
    if not text:
        return text
    lines = text.split("\n")
    out: list[str] = []
    for i, line in enumerate(lines):
        m = re.match(r"^#{2,4}\s+(.+?)\s*$", line)
        if m and _normalize_credit_role(m.group(1)) in _CREDIT_ROLES:
            # Count OTHER CRediT role tokens in a ±10-line window.
            lo = max(0, i - 10)
            hi = min(len(lines), i + 11)
            nearby = 0
            for k in range(lo, hi):
                if k == i:
                    continue
                s = lines[k].strip()
                if s and _normalize_credit_role(s) in _CREDIT_ROLES:
                    nearby += 1
            if nearby >= 3:
                # Demote: drop the heading markup, keep the role word as
                # a plain line (it is real content of the role block).
                out.append(m.group(1).strip())
                continue
        out.append(line)
    return "\n".join(out)


# ── Section C3: inline-footnote demotion + study-subsection promotion ──────


_INLINE_FOOTNOTE_RE = re.compile(
    r"^(?P<num>\d{1,2})\s+"
    r"(?P<lead>Though|Note|See|We|This|The|These|Although|However|It\s|Although|For)\b"
    r".{2,210}[\.\)]\s*$"
)


def _demote_inline_footnotes_to_blockquote(text: str) -> str:
    """Demote leaked inline footnote paragraphs to ``> ¹ ...`` blockquotes.

    pdftotext renders footnotes at the bottom of each page in linear reading
    order, producing a standalone single-line paragraph like:

        1 Though we note a recent failed replication of the Kogut and Ritov
          (2005) by Majumder et al. (2023).

    These get spliced into body prose because they share a section's char
    window with surrounding paragraphs. This pass detects such lines and
    rewrites them as markdown blockquotes so the reader can still see the
    footnote content but it's visually demoted out of the prose flow.

    Conservative trigger requires ALL of:
      - The paragraph is exactly one line (no embedded ``\\n``).
      - Length 30-220 chars (real footnotes; longer is prose).
      - Starts with a 1-2 digit number followed by whitespace.
      - First word after the digit is from a small fixed set
        (``Though|Note|See|We|This|The|These|Although|However|It|For``) —
        these dominate academic footnote openings while rarely opening
        non-footnote numbered paragraphs.
      - Ends with a sentence-terminator (``.`` or ``)``).
    """
    if not text:
        return text
    paragraphs = re.split(r"(\n\n+)", text)
    for idx in range(0, len(paragraphs), 2):
        para = paragraphs[idx]
        stripped = para.strip()
        if not stripped or "\n" in stripped:
            continue
        if len(stripped) < 30 or len(stripped) > 220:
            continue
        if not _INLINE_FOOTNOTE_RE.match(stripped):
            continue
        paragraphs[idx] = f"> {stripped}"
    return "".join(paragraphs)


_STUDY_SUBSECTION_RE = re.compile(
    r"^Study\s+\d+\s+"
    r"(?:Design(?:\s+and\s+Findings)?|Results(?:\s+and\s+Findings)?|"
    r"Methods?|Procedure|Materials|Hypotheses|Predictions|Discussion)$"
)
_OVERVIEW_HEADING_RE = re.compile(
    r"^Overview\s+of\s+(?:the\s+)?[A-Z][A-Za-z\s]{2,60}$"
)

# v2.4.26 (cycle 11): post-processor regex for ALL-CAPS major section
# headings that pdftotext kept on their own line but the section
# detector rejected (blank_before / blank_after constraints failed
# because pdftotext flattened paragraph breaks around the heading).
#
# Captures AOM-style structure (amj_1):
#   * THEORETICAL DEVELOPMENT
#   * OVERVIEW OF THE STUDIES
#   * STUDY 1: QUASI-FIELD EXPERIMENT
#   * STUDY 2: LABORATORY EXPERIMENT
#   * MANIPULATION AND MEASURES
#   * GENERAL DISCUSSION  (also covered by the section detector — but
#     idempotent since this post-processor skips lines that already
#     have ``#`` prefix)
#
# Strict criteria to avoid false positives:
#   - Whole line is ALL-CAPS (letters + digits + ``:``/``-``/space/comma).
#   - ≥ 10 chars (excludes "USA", "EU").
#   - ≥ 2 whitespace-separated tokens.
#   - Doesn't end with a sentence terminator.
#   - At least one alphabetic character (excludes pure-digit lines).
_ALL_CAPS_SECTION_HEADING_RE = re.compile(
    r"^[A-Z][A-Z0-9:\-,/ ]{9,}[A-Z0-9]$"
)

# Cycle 15d (G6): Roman-numeral section markers in IEEE / engineering papers.
# IEEE style is `I. INTRODUCTION` / `II. METHODOLOGY` / ... / `V.: SUPPLEMENTARY INDEX`.
# Two layout variants observed in pdftotext output:
#   (A) Orphan numeral on its own line, blank, then ALL-CAPS heading on next line.
#       Detected via _ROMAN_NUMERAL_ORPHAN_RE; consumed by the post-processor
#       and folded into the following promoted heading: `## I. INTRODUCTION`.
#   (B) Roman numeral + (optional colon) + ALL-CAPS title on a single line.
#       The `.` and `:` after the numeral block the standard heading regex
#       above, so we add a dedicated _ROMAN_PREFIX_HEADING_RE for this form.
_ROMAN_NUMERAL_ORPHAN_RE = re.compile(r"^[IVX]{1,4}\.\s*$")
_ROMAN_PREFIX_HEADING_RE = re.compile(
    r"^([IVX]{1,4})\.:?\s+([A-Z][A-Z0-9:\-,/ ]{3,}[A-Z0-9])$"
)


def _fold_orphan_roman_numerals_into_headings(text: str) -> str:
    """Cycle 15d (G6): fold an orphan Roman-numeral line into the following
    `## ` heading.

    By the time `_promote_study_subsection_headings` runs, the section
    partitioner has often already promoted the ALL-CAPS heading to `## `
    on its own — but the preceding `I.` / `II.` / etc. numeral line is
    left as orphan body prose. This post-processor scans for the pattern
    and folds the numeral into the heading:

        I.\\n\\n## INTRODUCTION  →  ## I. INTRODUCTION

    Operates on text-level regex (multi-line) so it catches any blank-line
    separation between the numeral and the heading.
    """
    if not text:
        return text
    # Match: orphan Roman-numeral on its own line, any number of blank lines,
    # then a `## ` heading. Capture the numeral and the heading text.
    pattern = re.compile(
        r"(?m)^([IVX]{1,4}\.)\s*\n(?:\s*\n)+(?P<head>## (?!\s*[IVX]{1,4}\.\s)[^\n]+)"
    )

    def repl(m: re.Match) -> str:
        numeral = m.group(1)
        head_line = m.group("head")
        # head_line is "## SOMETHING" — splice the numeral after the `## `
        head_text = head_line[3:]
        return f"## {numeral} {head_text}"

    return pattern.sub(repl, text)


def _fold_orphan_arabic_numerals_into_headings(text: str) -> str:
    """Cycle 3 (D6): fold an orphan arabic section-number line into the
    following `## ` heading.

    JDM / Cambridge-style papers number their sections ``1. Introduction``,
    ``2. Method``, etc. pdftotext frequently emits the bare number on its
    own line, separated from the heading text the section partitioner
    promoted to `## `:

        1.\\n\\n## Introduction  →  ## 1. Introduction

    Arabic analogue of ``_fold_orphan_roman_numerals_into_headings``.
    Conservative: the number (1-2 digits, dot optional) must be IMMEDIATELY
    followed — blank lines only — by a `## ` heading that does not already
    begin with a number. A bare ``1.`` line that precedes ordinary body
    prose (page number, list item) is left untouched.
    """
    if not text:
        return text
    pattern = re.compile(
        r"(?m)^(\d{1,2})\.?[ \t]*\n(?:[ \t]*\n)+"
        r"(?P<head>## (?!\s*\d{1,2}[.\s])[^\n]+)"
    )

    def repl(m: re.Match) -> str:
        num = m.group(1)
        head_text = m.group("head")[3:]
        return f"## {num}. {head_text}"

    return pattern.sub(repl, text)


def _fold_orphan_multilevel_numerals_into_headings(text: str) -> str:
    """Cycle G5c-1: fold an orphan multi-level section-number line (``5.4.``,
    ``6.1.2.``) into the immediately following generic ``##``/``###`` heading.

    Multi-level analogue of :func:`_fold_orphan_arabic_numerals_into_headings`.
    pdftotext sometimes splits ``5.4. Discussion`` into a bare ``5.4.`` line
    and a separate ``Discussion`` line; the section partitioner then promotes
    the lone title word to a generic ``## Discussion`` and strands the number::

        5.4.\\n\\n## Discussion  →  ### 5.4. Discussion

    A multi-level dotted number alone on a line is itself a strong subsection
    signal — body prose and list items do not emit a bare ``5.4.`` line — so
    the fold is keyed purely on that structural signature plus blank-line-only
    adjacency to a heading. The result is always ``### ``: multi-level
    numbering denotes a subsection regardless of the level the partitioner
    happened to give the stranded title (cf. ``_NUMBERED_SUBSECTION_HEADING_RE``,
    which likewise emits ``### `` at any depth).

    The fold target must be a *generic* heading. ``### Figure N`` / ``### Table N``
    are library-emitted structural markers, and a heading already starting with
    a number is a real numbered section — both are excluded (the latter also
    keeps the pass idempotent). Only the immediately-adjacent case is folded;
    an orphan number separated from its heading by a figure block or by body
    prose (the title word consumed elsewhere) is partitioner-level work and is
    left untouched here.
    """
    if not text:
        return text
    pattern = re.compile(
        r"(?m)^(\d+(?:\.\d+){1,3})\.?[ \t]*\n(?:[ \t]*\n)+"
        r"(?P<head>#{2,3} (?!\s*\d)(?!Figure\b)(?!Table\b)[^\n]+)"
    )

    def repl(m: re.Match) -> str:
        num = m.group(1)
        head_text = m.group("head").split(" ", 1)[1]
        return f"### {num}. {head_text}"

    return pattern.sub(repl, text)


def _promote_study_subsection_headings(text: str) -> str:
    """Promote ``Study N Design and Findings`` etc. to ``### {title}``.

    Replication / multi-study papers (Collabra, Cogemo, JESP) use plain-text
    "Study 1 Design and Findings" lines as subsection headings — same font
    size as body in the PDF, so pdftotext linearizes them as bare lines and
    the section detector doesn't pick them up. This pass promotes them to
    `### Study N Foo` h3 headings.

    Conservative: only matches a closed set of subsection patterns
    (``Design (and Findings)``, ``Results (and Findings)``, ``Methods``,
    ``Procedure``, ``Materials``, ``Hypotheses``, ``Predictions``,
    ``Discussion``) and the related ``Overview of the …`` line.

    Operates at the line level (not paragraph level) because pdftotext often
    joins subsection-heading lines with surrounding body using single ``\\n``
    rather than ``\\n\\n``. When a matching line is found inside a multi-line
    paragraph, split the paragraph and promote the line to ``### {title}``
    surrounded by blank lines.
    """
    if not text:
        return text
    lines = text.split("\n")
    out: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out.append(line)
            continue
        promoted_h2 = False
        # Cycle 15d: inline Roman-numeral-prefixed ALL-CAPS heading
        # ("I. INTRODUCTION", "V.: SUPPLEMENTARY INDEX"). The `.`/`:` after
        # the numeral blocks the bare ALL-CAPS regex, so handle this form
        # explicitly before falling through to the bare ALL-CAPS branch.
        roman_inline = _ROMAN_PREFIX_HEADING_RE.match(stripped)
        if roman_inline and _is_safe_all_caps_promote(lines, i, stripped):
            if out and out[-1] != "":
                out.append("")
            out.append(f"## {stripped}")
            out.append("")
            promoted_h2 = True
        elif _ALL_CAPS_SECTION_HEADING_RE.match(stripped) and _is_safe_all_caps_promote(
            lines, i, stripped
        ):
            # v2.4.26 (cycle 11): an ALL-CAPS line sandwiched between a
            # sentence-terminator and a heading-like sub-section line
            # is almost certainly a major section heading that the
            # section detector missed because pdftotext flattened
            # paragraph breaks around it. Promote to ``## {heading}``.
            #
            # Cycle 15d (G6): when the heading is preceded by an orphan
            # Roman-numeral line ("I." on its own line above
            # "INTRODUCTION"), fold the numeral into the promoted heading
            # so the output reads "## I. INTRODUCTION" (matching the
            # source PDF) instead of leaving an orphan numeral above the
            # `##` line. Search the last ≤3 entries of out[] for the
            # orphan; remove it if found and prepend its content to the
            # heading text.
            roman_consumed = ""
            for back in range(1, min(4, len(out)) + 1):
                idx = len(out) - back
                if idx < 0:
                    break
                candidate = out[idx].strip()
                if candidate == "":
                    continue
                m = _ROMAN_NUMERAL_ORPHAN_RE.match(candidate)
                if m:
                    roman_consumed = candidate  # e.g. "I."
                    # Pop the orphan AND any subsequent blank lines so we
                    # don't end up with double blanks in front of `##`.
                    out = out[:idx]
                    # Trim any trailing blanks in out so the `##` lands
                    # cleanly after one blank line.
                    while out and out[-1] == "":
                        out.pop()
                break
            if out and out[-1] != "":
                out.append("")
            if roman_consumed:
                out.append(f"## {roman_consumed} {stripped}")
            else:
                out.append(f"## {stripped}")
            out.append("")
            promoted_h2 = True
        elif _STUDY_SUBSECTION_RE.match(stripped) or _OVERVIEW_HEADING_RE.match(stripped):
            # Promote with blank-line padding so downstream tools see it as
            # a standalone heading paragraph. Avoid double blank lines.
            if out and out[-1] != "":
                out.append("")
            out.append(f"### {stripped}")
            out.append("")
        else:
            out.append(line)
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _is_safe_all_caps_promote(lines: list[str], i: int, stripped: str) -> bool:
    """Guard for :func:`_promote_study_subsection_headings`'s ALL-CAPS
    branch to prevent false-positive promotion of body fragments.

    Requires both:
      * The previous non-blank line ends with a sentence-terminator
        (``.``, ``!``, ``?``) or is itself an empty/whitespace-only line
        from a paragraph break — i.e. the prior paragraph ended cleanly.
      * The next non-blank line starts with an uppercase letter (a real
        paragraph or sub-heading) AND doesn't itself look like part of
        the heading line's continuation (e.g. column-header siblings).

    Also requires the line to contain at least one alphabetic char so
    pure-digit lines (table-row leakage) don't fire.
    """
    if not any(c.isalpha() for c in stripped):
        return False
    # Previous non-blank line check.
    prev = None
    j = i - 1
    while j >= 0:
        ps = lines[j].strip()
        if ps:
            prev = ps
            break
        j -= 1
    if prev is None:
        return False
    if prev[-1:] not in {".", "!", "?", ":", '"', "'", ")", "]"}:
        return False
    # Next non-blank line check.
    nxt = None
    j = i + 1
    while j < len(lines):
        ns = lines[j].strip()
        if ns:
            nxt = ns
            break
        j += 1
    if nxt is None:
        return False
    if not nxt[:1].isupper():
        return False
    # Reject if the next line is itself ALL-CAPS — that would be a
    # continuation of a multi-line ALL-CAPS title (only the title
    # case at top-of-doc has this) rather than a sub-heading.
    if _ALL_CAPS_SECTION_HEADING_RE.match(nxt):
        return False
    return True


# ── Section C2: orphan table cell-text suppression ──────────────────────────


_ORPHAN_TABLE_CAPTION_RE = re.compile(
    r"^Table\s+(\d+)[.:]\s+(.{3,}?)$"
)
_ORPHAN_CELL_STOPWORDS = (
    " the ", " of ", " and ", " in ", " to ", " for ", " with ", " that ",
    " this ", " was ", " were ", " are ", " is ", " have ", " has ",
    " from ", " on ", " by ", " an ", " a ",
)


def _is_orphan_cell_paragraph(p: str) -> bool:
    """Return True iff ``p`` looks like a leaked table cell row, not prose.

    Conservative heuristic, used only inside the table-cell-text suppressor:
    - Total length ≤ 200 chars (cell content with quoted instruction text or
      concatenated column headers can run 100-200 chars on a single pdftotext
      line; longer than that is almost certainly prose).
    - Not a heading, caption, HTML block, or list marker.
    - Stopword-density and sentence-structure check rule out short prose.
    """
    if not p:
        return False
    if len(p) > 200:
        return False
    if p.startswith(("#", "*Table", "*Figure", "<table", "</table", "<thead", "<tbody", "<tr", "<td", "<th", ">")):
        return False
    if re.match(r"^(?:Table|Figure)\s+\d", p):
        return False
    if re.match(r"^[*+\-]\s", p) or re.match(r"^\d+\.\s+\w+", p):
        # Markdown list / numbered list — not a cell row.
        # (Numbered ranks like "1. Degree of apology" inside cells can match,
        # but those are typically inside <td> tags, not standalone paragraphs.)
        return False
    if p.startswith("Note") and (":" in p[:8] or "." in p[:8]):
        return False
    lower = " " + p.lower() + " "
    stopword_hits = sum(lower.count(sw) for sw in _ORPHAN_CELL_STOPWORDS)
    # Above 90 chars, prose density must be very low (cells with quoted
    # instruction text or column-header concatenations have ≤ 3 stopwords).
    if len(p) > 90 and stopword_hits >= 4:
        return False
    if len(p) <= 90 and stopword_hits >= 3:
        return False
    # Multi-sentence content is prose, not a cell row.
    if p.count(". ") >= 2:
        return False
    # Single long sentence ending in `.` (not `."` — cells often end in `"`)
    # is prose.
    if p.endswith(".") and not p.endswith(('."', '.")')) and len(p) > 70 and " " in p:
        return False
    return True


def _suppress_orphan_table_cell_text(text: str) -> str:
    """Suppress orphan cell-row text leaks after a plain-text Table caption.

    When Camelot does not register a table on a page but pdftotext linearized
    the cell content into the section body, the rendered markdown contains:

        Table 5. Comparison of target article versus replication.

        Target article

        Replication

        Study design

        Sample characteristics

    These short orphan paragraphs are leaked cell content with no structural
    value in the rendered view (the user is told to consult the Raw view).
    This pass:
      1. Detects single-line ``Table N. <caption>`` paragraphs (plain, not
         already italicized — the italic ``*Table N. ...*`` form is the
         v2.4.2 caption-only emission and never has orphan rows).
      2. Scans forward; if 3+ consecutive paragraphs match
         :func:`_is_orphan_cell_paragraph`, italicizes the caption and drops
         the orphan paragraphs.

    Conservative: only fires after a ``Table N.`` caption and only when the
    orphan run is at least 3 paragraphs long. Stops at the first non-orphan
    paragraph (normal prose, another caption, or a heading).
    """
    if not text or "Table" not in text:
        return text
    # Operate at LINE level. v2.4.10 rationale: pdftotext version skew
    # between local dev (Xpdf 4.00 -> `\n\n` paragraph breaks) and Railway
    # prod (poppler-utils 25.03 -> single `\n` between cell-content runs).
    # v2.4.11 enhancements:
    #   - Also fire after italic ``*Table N. ...*`` captions (v2.4.2
    #     emits those when Camelot returned 0 cells; orphan rows can
    #     follow the italic just as easily as a plain caption).
    #   - Accept digit-period prefix lines (``1. Degree of apology``)
    #     when seen inside a post-caption region. These look like
    #     numbered list items in isolation but are column-1 cell labels
    #     in academic stats tables.
    #   - Lower threshold from 3 to 2 orphans (covers two-column tables
    #     like chan_feldman Table 1 — Hypothesis + Description).
    italic_re = re.compile(r"^\*Table\s+(\d+)[.:]\s+.{3,}\*\s*$")
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        is_plain_caption = (
            stripped
            and not stripped.startswith("*")
            and not stripped.startswith("#")
            and _ORPHAN_TABLE_CAPTION_RE.match(stripped)
        )
        is_italic_caption = stripped and italic_re.match(stripped)
        if is_plain_caption or is_italic_caption:
            # Scan ahead for orphan-cell lines. Allow 0-1 blank lines
            # between orphans; stop on a second blank line or on the first
            # non-orphan (e.g. "Note: ..." caption tail, or the next prose
            # paragraph). No fixed line cap — academic stats tables can
            # have 30-100 orphan cell lines in a row (5x5 correlation
            # matrix + headers + group separators).
            j = i + 1
            blank_run = 0
            orphans: list[int] = []
            while j < len(lines):
                p = lines[j].strip()
                if not p:
                    blank_run += 1
                    j += 1
                    if blank_run > 1:
                        break
                    continue
                blank_run = 0
                # In post-caption cell context, also accept the
                # `^\d+\.\s+\w+` pattern (column-1 cell labels). Outside
                # this context it's still rejected as a numbered list.
                if _is_cell_like_in_post_caption_context(p):
                    orphans.append(j)
                    j += 1
                    continue
                break
            if len(orphans) >= 2:
                # Italicize plain captions; leave italic ones unchanged.
                # In both cases drop the orphan lines.
                if is_plain_caption:
                    out.append(f"*{stripped}*")
                else:
                    out.append(line)
                i = orphans[-1] + 1
                continue
        out.append(line)
        i += 1
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# FIG-3c (v2.4.51): a body line that begins a figure-caption run inline.
# pdftotext linearizes a figure's caption into the running text column, so
# the caption appears once inline in body prose and once as the spliced
# ``### Figure N`` block — a double-emission.
_INLINE_FIG_CAPTION_LABEL_RE = re.compile(r"^(?:Figure|FIGURE|Fig\.)\s+\d+\b")


def _suppress_inline_duplicate_figure_captions(text: str) -> str:
    """Drop a figure caption that pdftotext also left inline in the body
    text, when the figure already has a dedicated ``### Figure N`` block.

    pdftotext linearizes a figure caption into the running text column, so
    the caption is rendered twice: once inline in a section's body prose,
    once as the spliced ``### Figure N`` block. This removes the inline
    body copy.

    Safe-subset only (FIG-3c): the inline run is dropped ONLY when the
    ``### Figure N`` block's caption *fully covers* it — the block caption
    equals, or is a superset (prefix-wise) of, the normalized inline run.
    An inline run that EXCEEDS the block caption (the block caption was
    trimmed shorter, or the run accumulated trailing body prose) is left
    untouched so no caption text can be lost. Keyed purely on the
    structural signature (a ``Figure N``-led body run reproducing a known
    figure block's caption), not on paper identity.
    """
    lines = text.split("\n")
    # 1. Collect "### Figure N" block captions (label included).
    block_cap: dict[int, str] = {}
    for i, ln in enumerate(lines):
        m = re.match(r"^#{2,4} Figure (\d+)\s*$", ln)
        if not m:
            continue
        for j in range(i + 1, min(i + 5, len(lines))):
            cm = re.match(r"^\*(Figure\s+\d+.+?)\*\s*$", lines[j])
            if cm:
                block_cap[int(m.group(1))] = re.sub(
                    r"\s+", " ", cm.group(1)
                ).strip()
                break
    if not block_cap:
        return text
    # 2. Walk body lines; drop an inline run fully covered by a block caption.
    drop: set[int] = set()
    n = len(lines)
    i = 0
    while i < n:
        s = lines[i].strip()
        if (
            s
            and _INLINE_FIG_CAPTION_LABEL_RE.match(s)
            and not s.startswith(("#", "*", "<", "|", "`", ">"))
        ):
            num = int(re.match(r"^(?:Figure|FIGURE|Fig\.)\s+(\d+)\b", s).group(1))
            bc = block_cap.get(num)
            if bc:
                # Accumulate the inline run: consecutive non-blank body
                # lines until a blank line / structural element / new caption.
                run = [i]
                acc = s
                j = i + 1
                while j < n:
                    sj = lines[j].strip()
                    if (
                        not sj
                        or sj.startswith(("#", "*", "<", "|", "`", ">"))
                        or _INLINE_FIG_CAPTION_LABEL_RE.match(sj)
                        or re.match(r"^(?:Table|TABLE)\s+\d", sj)
                    ):
                        break
                    run.append(j)
                    acc = f"{acc} {sj}"
                    j += 1
                acc_norm = re.sub(r"\s+", " ", acc).strip()
                # Drop iff the block caption fully covers the inline run
                # (>=30 chars matched, so a coincidental short prefix can't
                # trigger removal).
                if len(acc_norm) >= 30 and bc.lower().startswith(acc_norm.lower()):
                    drop.update(run)
                    i = j
                    continue
        i += 1
    if not drop:
        return text
    kept = [ln for k, ln in enumerate(lines) if k not in drop]
    out = "\n".join(kept)
    # Collapse blank-line runs left by the removal.
    return re.sub(r"\n{3,}", "\n\n", out)


def _is_cell_like_in_post_caption_context(p: str) -> bool:
    """Like `_is_orphan_cell_paragraph` but accepts digit-period prefix
    lines (``1. Degree of apology``) which look like list items in
    isolation but are common column-1 cell labels in academic stats
    tables. Called only inside the post-caption scan window."""
    if _is_orphan_cell_paragraph(p):
        return True
    # Digit-period prefix: `^\d+\.\s+\w` — must be short (≤ 80 chars,
    # cell label), no multi-sentence prose.
    if re.match(r"^\d+\.\s+\w", p) and len(p) <= 80:
        # Reject if it has many stopwords (real list item with prose).
        lower = " " + p.lower() + " "
        if sum(lower.count(sw) for sw in _ORPHAN_CELL_STOPWORDS) >= 3:
            return False
        if p.count(". ") >= 2:
            return False
        return True
    return False


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
                raw_t = (item.get("raw_text") or "").strip()
                if html:
                    body_chunks.append(f"\n### {label}\n")
                    if cap:
                        body_chunks.append(f"*{cap}*\n")
                    body_chunks.append(html)
                elif raw_t:
                    # v2.4.14: Camelot returned no cells, but we extracted
                    # the linearized cell text following the caption
                    # (``raw_text``). Emit it as a fenced ``unstructured``
                    # block so the user sees the table's content inline at
                    # the caption position, with a clear note that the
                    # grid couldn't be reconstructed. Matches the Tables
                    # tab's behaviour in the SaaS UI (it shows raw_text
                    # under an amber notice when no html is present).
                    body_chunks.append(f"\n### {label}\n")
                    if cap:
                        body_chunks.append(f"*{cap}*\n")
                    body_chunks.append(
                        "\n> Could not reconstruct a structured grid for "
                        "this table. Showing the cell text as a flat list.\n\n"
                    )
                    body_chunks.append("```unstructured-table\n")
                    body_chunks.append(raw_t)
                    body_chunks.append("\n```\n")
                elif cap:
                    # v2.4.2: Camelot returned no cells AND we have no
                    # raw_text fallback for this caption. Skip the
                    # `### Table N` heading (which would falsely promise
                    # structured content) and emit the caption as a
                    # plain italicized paragraph so the table reference is
                    # preserved in body flow.
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
            or (t.get("raw_text") or "").strip()
        ]
        if renderable_tables:
            out_chunks.append("## Tables (unlocated in body)\n\n")
            for t in renderable_tables:
                label = t.get("label") or "Table"
                cap = t.get("caption") or ""
                cells = t.get("cells") or []
                html = t.get("html") or (cells_to_html(cells) if cells else "")
                raw_t = (t.get("raw_text") or "").strip()
                out_chunks.append(f"### {label}\n")
                if cap:
                    out_chunks.append(f"*{cap}*\n")
                if html:
                    out_chunks.append(html + "\n")
                elif raw_t:
                    # v2.4.14: surface raw_text fallback (same shape as
                    # the inline emission above).
                    out_chunks.append(
                        "\n> Could not reconstruct a structured grid for "
                        "this table. Showing the cell text as a flat list.\n\n"
                    )
                    out_chunks.append("```unstructured-table\n")
                    out_chunks.append(raw_t)
                    out_chunks.append("\n```\n")
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
        # preserve_math_glyphs=True so the rendered .md keeps β/δ/χ²/η²/²/₀
        # as the source PDF prints them. See CLAUDE.md ground-truth rule + memory
        # feedback_ground_truth_is_ai_not_pdftotext. The flag is plumbed through
        # extract_sections → normalize_text → A5 step.
        sectioned = extract_sections(
            pdf_bytes,
            source_format="pdf",
            preserve_math_glyphs=True,
        )

    # 3. Render sections + splice tables/figures.
    md = _render_sections_to_markdown(
        sectioned, structured["tables"], structured["figures"]
    )

    # 4. Post-process (spike pipeline order).
    md = _dedupe_h2_sections(md)
    md = _fix_hyphenated_line_breaks(md)
    md = _join_multiline_caption_paragraphs(md)
    md = _suppress_orphan_table_cell_text(md)
    md = _demote_inline_footnotes_to_blockquote(md)
    md = _promote_study_subsection_headings(md)
    md = _demote_false_single_word_headings(md)
    # HALLUC-HEAD-1: demote a `## <CRediT-role>` heading (e.g. `## Methodology`)
    # that the partitioner promoted from inside the contributor-roles block.
    md = _demote_credit_role_headings(md)
    md = _rejoin_garbled_ocr_headers(md)
    # v2.4.34: final guarantee — strip Mathematical-Alphanumeric styling from
    # the assembled markdown. S0 (body channel) and tables/cell_cleaning
    # (table HTML) already de-style their channels; this catches the
    # remaining surfaces — figure/table captions, unstructured-table fences,
    # raw_text fallbacks — so no math-italic glyph (𝜂, 𝛽, …) reaches the
    # rendered .md from ANY channel.
    md = destyle_math_alphanumeric(md)
    # v2.4.38: final guarantee — recover '2'-for-U+2212 minus corruption from
    # the assembled markdown. W0b (body channel) and cell_cleaning (Camelot
    # table cells) already cover their channels; this catches the remaining
    # surfaces — unstructured-table fenced blocks, raw_text table fallbacks
    # when Camelot is unavailable — so no sign-flipped CI reaches the .md.
    md = recover_corrupted_minus_signs(md)
    # v2.4.39: final guarantee — recover '<'-as-backslash glyph corruption from
    # the assembled markdown. W0c (body channel) and cell_cleaning (Camelot
    # table cells) already cover their channels; this catches the remaining
    # surfaces — unstructured-table fenced blocks and raw_text table fallbacks
    # when Camelot is unavailable — so no corrupted "p < .001" reaches the .md.
    md = recover_corrupted_lt_operator(md)
    # v2.4.40: recover standalone '2'-for-U+2212 minus corruption on
    # point-estimate cells/tokens by pairing each with the confidence
    # interval reported in the same table row or text line. The bracketed
    # CIs are already recovered above (recover_corrupted_minus_signs); this
    # pass reaches the bracket-less point estimates — every negative
    # B-coefficient table cell, the Mposterior mediation estimates — that
    # the descending-bracket rule structurally cannot see.
    md = recover_minus_via_ci_pairing(md)
    # v2.4.44: final guarantee — decompose Latin typographic ligatures
    # (ﬁ->fi, ﬂ->fl, …) from the assembled markdown. normalize (body) and
    # cell_cleaning (table cells) cover their channels; this catches the
    # remaining surfaces — figure/table captions, unstructured-table fences,
    # raw_text fallbacks — so no presentation-form ligature reaches the .md.
    md = decompose_ligatures(md)
    # FIG-3c: drop a figure caption pdftotext also left inline in the body
    # text, when a ``### Figure N`` block already carries it (double-emission).
    # Runs AFTER every glyph-normalization pass (destyle / minus-recovery /
    # ligature decomposition) so the inline body line and the figure block's
    # caption are compared in the SAME final glyph form — a stray ligature in
    # the block caption (``reﬂection`` vs body ``reflection``) would otherwise
    # defeat the equality check.
    md = _suppress_inline_duplicate_figure_captions(md)
    md = _merge_compound_heading_tails(md)
    md = _reformat_jama_key_points_box(md)
    md = _promote_numbered_subsection_headings(md)
    # Cycle 15d (G6): fold orphan Roman-numeral lines into the following
    # `## ` heading produced by the section partitioner. Runs LAST among
    # heading post-processors so it operates on the final heading shapes.
    md = _fold_orphan_roman_numerals_into_headings(md)
    md = _fold_orphan_arabic_numerals_into_headings(md)
    # Cycle G5c-1: multi-level analogue — fold an orphan `N.N.` number line
    # into the immediately following generic heading (`5.4.`\n\n`## Discussion`
    # -> `### 5.4. Discussion`). Runs alongside the single-level folders.
    md = _fold_orphan_multilevel_numerals_into_headings(md)
    # Cycle 11 (G5a): promote single-level `N. Title` lines to `## N. Title`,
    # gated on the document already numbering its sections. Runs AFTER the
    # orphan-numeral folders so `## 1. Introduction` exists as an anchor.
    md = _promote_numbered_section_headings(md)

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
