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
    _looks_like_running_header_or_footer,
    _rejoin_garbled_ocr_headers,
    decompose_ligatures,
    destyle_math_alphanumeric,
    recover_corrupted_lt_operator,
    recover_corrupted_minus_signs,
    recover_dropped_minus_via_ci_pairing,
    recover_minus_via_ci_pairing,
    recover_pua_glyphs,
)
from .sections import extract_sections
from .tables.flatten import (
    FlattenedRow,
    flatten_table,
    render_flattened_inline,
)
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


def _table_completeness_marker(cells, raw_text: str) -> str:
    # Approach-C instrumentation (B1, 2026-05-22): emit a machine-greppable
    # HTML comment when the structured table is degenerate, so the harness +
    # broad-pytest can count silent-failure shapes corpus-wide before any
    # repair pass lands. STRUCTURAL signals only (cell counts) — no per-PDF
    # heuristics, no caption text mining (caption "N=K" is sample size, not
    # row count). The three diagnostic shapes:
    #   - empty-shell:      cells=0 AND no raw_text fallback (B1 canonical:
    #                       plos-med-1 Table 5)
    #   - unstructured:     cells=0 but raw_text fallback present (Camelot
    #                       returned nothing; linearized fenced block used)
    #   - single-row:       cells=1 (almost always headers-only, body lost)
    if cells:
        try:
            n_rows = max(c["r"] for c in cells) + 1
        except (KeyError, TypeError, ValueError):
            n_rows = 0
    else:
        n_rows = 0
    if n_rows == 0 and not (raw_text or "").strip():
        return "<!-- table-empty-shell: 0 rows recovered, no raw_text fallback -->\n"
    if n_rows == 0:
        return "<!-- table-unstructured: 0 structured rows, raw_text fallback only -->\n"
    if n_rows == 1:
        return "<!-- table-single-row: 1 row recovered (likely headers-only, body lost) -->\n"
    return ""


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


# Word-boundary regex per role, allowing the inner spaces in multi-word roles
# (e.g. "data curation") to match across hyphens / slashes too. Built once
# at module load so the demote function stays cheap on every render.
_ROLE_TOKEN_PATTERNS: list[tuple[str, "re.Pattern[str]"]] = [
    (
        role,
        re.compile(
            r"\b" + re.escape(role).replace(r"\ ", r"[\s\-/]+") + r"\b",
            re.IGNORECASE,
        ),
    )
    for role in _CREDIT_ROLES
]


_WORD_RE = re.compile(r"[A-Za-z]+")


def _max_distinct_roles_in_any_line(window_lines: list[str], exclude: str) -> int:
    """Largest count of distinct CRediT roles on a 'packed' line.

    A packed CRediT-roles table line ("Project administration Resources
    Software Supervision Validation Visualisation Writing-original draft …")
    is the highest-signal indicator we are inside the contributor-roles
    block. To avoid demoting a real Methodology section whose prose happens
    to mention 3 role-like words ('our investigation used the software in
    our resources'), the line is only counted when its words are MOSTLY
    inside role tokens — ≥70 % of the line's alphabetic words must belong
    to one of the matched role spans. Prose mixes role words with verbs,
    prepositions, and connectives and falls well under that threshold."""
    best = 0
    for line in window_lines:
        if not line.strip():
            continue
        words = _WORD_RE.findall(line)
        if len(words) < 3:
            continue
        # Find role matches and the words they cover.
        hits: set[str] = set()
        covered_chars: list[tuple[int, int]] = []
        for role, pat in _ROLE_TOKEN_PATTERNS:
            if role == exclude:
                continue
            for m in pat.finditer(line):
                hits.add(role)
                covered_chars.append(m.span())
        if len(hits) < 3:
            continue
        # Count words whose span overlaps any role-covered span.
        words_in_roles = 0
        for wm in _WORD_RE.finditer(line):
            ws, we = wm.span()
            for cs, ce in covered_chars:
                if ws < ce and we > cs:
                    words_in_roles += 1
                    break
        coverage = words_in_roles / max(1, len(words))
        if coverage >= 0.70 and len(hits) > best:
            best = len(hits)
    return best


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

    B2a (2026-05-22): also recognises SPLIT-FORM roles where the heading
    text is a single-word prefix of a multi-word CRediT role and the
    next non-blank line completes it — e.g. ``## Funding`` + blank +
    ``acquisition`` is the role "Funding acquisition" with the second
    word orphaned onto its own line by the partitioner. ``## Writing``
    + ``original draft`` (and variants) are handled the same way.
    """
    if not text:
        return text
    lines = text.split("\n")
    out: list[str] = []
    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]
        m = re.match(r"^#{2,4}\s+(.+?)\s*$", line)
        demoted = False
        if m:
            heading_text = m.group(1).strip()
            heading_role = _normalize_credit_role(heading_text)
            full_role: Optional[str] = None
            orphan_idx: Optional[int] = None
            # B2a: split-form completion is tried FIRST — single role-word
            # PREFIX of a multi-word _CREDIT_ROLES entry, completed by the
            # next non-blank line. Preferred over the standalone match
            # because the longer form is the more accurate role attribution
            # when both shapes are present (e.g. ``## Writing`` is itself
            # the bare role ``writing`` AND a prefix of ``writing original
            # draft``; the orphan line on the next non-blank decides).
            if heading_role and " " not in heading_role:
                prefix_with_space = heading_role + " "
                candidates = {
                    r for r in _CREDIT_ROLES if r.startswith(prefix_with_space)
                }
                if candidates:
                    for j in range(i + 1, min(n, i + 4)):
                        s = lines[j].strip()
                        if not s:
                            continue
                        combined = _normalize_credit_role(heading_role + " " + s)
                        if combined in candidates:
                            full_role = combined
                            orphan_idx = j
                        # First non-blank line decides; whether or not it
                        # matched, stop the lookahead.
                        break
            # Fall back to the standalone match if no split-form was found.
            if full_role is None and heading_role in _CREDIT_ROLES:
                full_role = heading_role
            if full_role is not None:
                lo = max(0, i - 10)
                hi = min(n, i + 11)
                # Signal A — whole-line role neighbours.
                nearby = 0
                for k in range(lo, hi):
                    if k == i or k == orphan_idx:
                        continue
                    s = lines[k].strip()
                    if s and _normalize_credit_role(s) in _CREDIT_ROLES:
                        nearby += 1
                # Signal B — packed CRediT-line in window.
                window_lines = [
                    lines[k]
                    for k in range(lo, hi)
                    if k != i and k != orphan_idx
                ]
                packed_max = _max_distinct_roles_in_any_line(
                    window_lines, full_role
                )
                # §B-new-3 (2026-05-23): Signal C — PLOS Author-Contributions
                # packed-CRediT continuation. PLOS-style contributor blocks
                # use `**Role:** Names. **Role:** Names.` form (each role
                # followed by colon + name list). The coverage gate in
                # `_max_distinct_roles_in_any_line` undercounts these because
                # name-tokens dilute role-token coverage below 70%. Count
                # distinct CRediT roles that appear with a trailing `:` in
                # the window (across all lines).
                packed_colon_roles: set[str] = set()
                window_text = "\n".join(window_lines)
                for role, pat in _ROLE_TOKEN_PATTERNS:
                    if role == full_role:
                        continue
                    for rm in pat.finditer(window_text):
                        # Check: role match is immediately followed (within
                        # 3 chars, optionally through `**` markdown markers)
                        # by `:`. This catches `Methodology:` and
                        # `**Methodology:**` alike.
                        tail = window_text[rm.end(): rm.end() + 5]
                        if re.match(r"\*{0,2}\s*:", tail):
                            packed_colon_roles.add(role)
                            break
                if nearby >= 3 or packed_max >= 3 or len(packed_colon_roles) >= 3:
                    if orphan_idx is not None:
                        # Split-form: emit the combined role as plain text,
                        # preserve any blank lines that sat between heading
                        # and orphan, drop the orphan line itself.
                        out.append(
                            (heading_text + " " + lines[orphan_idx].strip()).strip()
                        )
                        for k in range(i + 1, orphan_idx):
                            out.append(lines[k])
                        i = orphan_idx + 1
                    else:
                        out.append(heading_text)
                        i += 1
                    demoted = True
        if not demoted:
            out.append(line)
            i += 1
    return "\n".join(out)


# ── B2b (2026-05-22): orphan generic-label heading demote ─────────────────
#
# The section partitioner promotes single-word canonical labels
# (``Conclusion``, ``Evaluation``, ``Findings``, ``Implications``,
# ``Limitations``) to ``##`` headings whenever they appear on a line by
# themselves. In front-matter sidebars and appendix labels these words
# stand alone with NO body prose after them — the next paragraph is
# another heading or another short label. A real Conclusion / Evaluation
# / Findings section is always followed by ≥3 prose lines.

_GENERIC_DEMOTE_LABELS = frozenset({
    "Conclusion",
    "Conclusions",
    "Evaluation",
    "Evaluations",
    "Findings",
    "Implications",
    "Limitations",
})

_PROSE_LINE_RE = re.compile(r"\b[a-z]{2,}\b")


def _is_prose_line(line: str) -> bool:
    """A line counts as PROSE for the B2b orphan test when it has both
    real word content AND at least one lowercase-letter word (so a
    string of column-header tokens like ``CI BF01`` doesn't satisfy)."""
    s = line.strip()
    if len(s) < 20:
        return False
    if s.startswith("#"):
        return False
    if not _PROSE_LINE_RE.search(s):
        return False
    return True


def _demote_orphan_generic_headings(text: str) -> str:
    """B2b: demote ``## <generic-label>`` headings that have no body
    prose after them (front-matter sidebar / appendix-marker shape).

    A real Conclusion / Evaluation / Findings section is followed by ≥3
    lowercase prose lines within a small window. When the window after
    the heading contains 0 prose lines (only blank lines and further
    headings), the heading is the orphan label — demote to body text.
    """
    if not text:
        return text
    lines = text.split("\n")
    n = len(lines)
    out: list[str] = []
    i = 0
    while i < n:
        line = lines[i]
        m = re.match(r"^#{2,4}\s+(.+?)\s*$", line)
        demoted = False
        if m and m.group(1).strip() in _GENERIC_DEMOTE_LABELS:
            # Look forward up to 15 lines for prose evidence; stop early
            # at the next heading line (which definitively ends the
            # current section's "body").
            window_end = min(n, i + 16)
            prose_lines = 0
            for j in range(i + 1, window_end):
                if lines[j].lstrip().startswith("#"):
                    break
                if _is_prose_line(lines[j]):
                    prose_lines += 1
                    if prose_lines >= 1:
                        # Even ONE prose line within the window is
                        # enough to treat the heading as legitimate —
                        # this is a conservative gate (we only demote
                        # the obvious orphan case, never tighten a real
                        # section).
                        break
            if prose_lines == 0:
                out.append(m.group(1).strip())
                i += 1
                demoted = True
        if not demoted:
            out.append(line)
            i += 1
    return "\n".join(out)


# ── HALLUC-HEAD-2 / G5d-2 (2026-05-23 cycle 3): continuation-promoted heading demote ─

# Words that, when appearing as the last token of a line with no sentence
# terminator, signal the line continues onto the next (soft-wrap split).
# Articles + the most common prepositions + coordinating conjunctions.
# Conservative set — we only demote when the prior line ENDS in one of these
# AND has no terminating punctuation. Excludes adverbs / pronouns / verbs
# (false-positive risk too high) and conjunctions like "but" / "or" / "yet"
# (legitimately ending a sentence as a stylistic device).
_CONTINUATION_TAIL_WORDS = frozenset({
    # Articles
    "a", "an", "the",
    # Prepositions (top 20 by academic-prose frequency)
    "of", "in", "to", "for", "with", "on", "at", "by", "from",
    "about", "into", "through", "during", "before", "after",
    "against", "between", "among", "via", "across", "within",
    # Coordinating "and" only (NOT "but" / "or" / "yet" / "nor")
    "and",
    # Subordinating that clearly continues
    "as", "than",
})


# Labels that, when starting a heading, indicate the heading is a structural
# label (Table 1, Figure 3, Appendix A, etc.) and should NEVER be demoted by
# the continuation-word guard. Established 2026-05-23 cycle 3 after the
# initial guard demoted `### Table 1` in chandrashekar_2023_mp because the
# prior body line ended in "of" (legitimate soft-wrap continuation context
# but legitimate heading too).
_LABEL_STYLE_HEADING_PREFIXES = (
    "Table ", "Tab. ", "Tab ",
    "Figure ", "Fig. ", "Fig ",
    "Appendix ", "App. ",
    "Box ",
    "Scheme ",
    "Equation ", "Eq. ", "Eq ",
    "Algorithm ", "Alg. ",
    "Listing ",
    "Section ", "Sec. ",
    "Chapter ", "Ch. ",
    "Note ",
    "Example ",
    "Supplementary ",
)


def _demote_continuation_promoted_headings(text: str) -> str:
    """HALLUC-HEAD-2 / G5d-2: demote ``## <Title>`` when the immediately-prior
    non-empty line ends in a continuation word (``the``, ``in``, ``of``, …)
    AND has no sentence terminator.

    The partitioner sees the second half of a soft-wrap-split sentence as
    a candidate heading and promotes it. This guard fires when that
    promotion is unsafe — when the prior text grammatically continues into
    what was promoted.

    Specific cycle-3 case (2026-05-23): on ``ip_feldman_2025_pspb``,
    "The calculated effect sizes are summarized in the\\n\\n## Supplemental
    Materials\\n" — the partitioner promoted ``## Supplemental Materials``
    because pdftotext column-broke "in the / Supplemental Materials".

    SCOPE LIMITS (to avoid false-positive demotions):

    * **h2 only.** Only ``## <Title>`` is at risk of over-promotion via this
      mechanism. ``### `` and ``#### `` headings have additional context
      (parent ``##`` already established) and over-promotions are rare. The
      cycle-3 chandrashekar render had ``### Table 1`` after "experimental
      design of" — legitimate h3 label, must not be demoted.
    * **Skip label-style headings.** "Table 1", "Figure 3", "Appendix A",
      "Box 2", etc. are structural labels — always legitimate even when the
      surrounding prose is technically continuation-shaped.

    Returns the demoted text. As of v2.4.79 the demoted continuation is
    rejoined to the prior line it grammatically continues (with the trailing
    sentence terminator restored when the phrase completes the sentence),
    rather than left as an orphan bare line — an orphaned fragment like
    "Supplemental Materials" reads as a hallucination to the AI verifier
    (ip_feldman canary finding #2).
    """
    if not text:
        return text
    lines = text.split("\n")
    n = len(lines)
    out: list[str] = []
    i = 0
    while i < n:
        line = lines[i]
        # Only h2 headings — h3+ have lower over-promotion risk and h3 labels
        # like `### Table 1` would false-positive on legitimate cases.
        m = re.match(r"^(##)\s+(.+?)\s*$", line)
        demoted = False
        if m and not line.startswith("###"):
            heading_text = m.group(2).strip()
            # Skip label-style headings (Table N, Figure N, Appendix, …).
            is_label = any(heading_text.startswith(p) for p in _LABEL_STYLE_HEADING_PREFIXES)
            if not is_label:
                # Find the immediately-prior non-empty line.
                j = i - 1
                while j >= 0 and not lines[j].strip():
                    j -= 1
                if j >= 0:
                    prev = lines[j].rstrip()
                    # Don't fire if prev is itself a heading, list-item, table
                    # row, blockquote, or any markdown-structural line.
                    is_structural_prev = bool(re.match(
                        r"^\s*(?:#|[*+\-]\s|\d+\.\s|>|<|\||```|\*Table\b|\*Figure\b)",
                        prev,
                    ))
                    if not is_structural_prev:
                        # Sentence terminator check — prev must NOT end in
                        # one of these.
                        last_char_terminates = prev.endswith(
                            (".", "?", "!", ":", ";", ")", "]", "}", "\"", "'", "*", "—", "–")
                        )
                        if not last_char_terminates:
                            last_word_match = re.search(r"(\b[A-Za-z]+)\s*$", prev)
                            if last_word_match:
                                last_word = last_word_match.group(1).lower()
                                if last_word in _CONTINUATION_TAIL_WORDS:
                                    # v2.4.79: rejoin the demoted continuation to
                                    # the prior line instead of leaving it as an
                                    # orphan bare line. The promoted heading lost
                                    # its trailing period and gained blank-line
                                    # padding; an orphaned "Supplemental Materials"
                                    # fragment reads as a hallucination to the AI
                                    # verifier (ip_feldman canary finding #2). The
                                    # prior line grammatically continues into this
                                    # phrase, so join them and restore a sentence
                                    # terminator when the phrase completes the
                                    # sentence (next non-blank line starts a new
                                    # sentence or markdown block).
                                    k = len(out) - 1
                                    while k >= 0 and not out[k].strip():
                                        k -= 1
                                    if k >= 0:
                                        nxt = i + 1
                                        while nxt < n and not lines[nxt].strip():
                                            nxt += 1
                                        starts_new = (
                                            nxt >= n
                                            or lines[nxt].lstrip()[:1].isupper()
                                            or bool(re.match(
                                                r"^\s*(?:#|[*+\-]\s|\d+\.\s|>|<|\||```)",
                                                lines[nxt],
                                            ))
                                        )
                                        joined = out[k].rstrip() + " " + heading_text
                                        if starts_new and not joined.rstrip().endswith(
                                            (".", "?", "!", ":", ";", ")", "]", "\"", "'")
                                        ):
                                            joined = joined.rstrip() + "."
                                        # Drop the blank padding lines between the
                                        # prior line and the demoted heading.
                                        del out[k + 1:]
                                        out[k] = joined
                                    else:
                                        out.append(heading_text)
                                    i += 1
                                    demoted = True
        if not demoted:
            out.append(line)
            i += 1
    return "\n".join(out)


# ── §B-new-2 HALLUC-HEAD-3 (2026-05-23): metadata-label heading demote ────
#
# Affects Cognition-&-Emotion-style PDFs where ``KEYWORDS`` appears as an
# all-caps metadata label between abstract and body. The partitioner promotes
# the single token to ``## KEYWORDS``. The fix: when the next non-blank lines
# (within 3) look like inline metadata content (semicolon-separated word
# list, comma-separated keyword phrases, no sentence verb), demote.
#
# Distinct from the continuation-word guard (HALLUC-HEAD-2): that fires on
# soft-wrap split; this fires on a structural label that has NO body section
# beneath it — just metadata.

# All-caps metadata labels that, when they appear as a single-token ``##``
# heading followed by inline metadata content, are NOT real section
# headings. Conservative set: only labels that frequently appear as front-
# matter metadata in academic PDFs.
_METADATA_LABEL_TOKENS = frozenset({
    "KEYWORDS",
    "Keywords",
    "KEY WORDS",
    "Key Words",
    "ABBREVIATIONS",
    "Abbreviations",
    "JEL",
    "MSC",
    "PACS",
})

# A line counts as METADATA SHAPE for the demote test when it:
#  - Contains a separator: `;` or 3+ commas.
#  - Has NO sentence verb pattern (no `is`/`are`/`was`/`were`/`have`/`has` in
#    common subject-verb position).
#  - Is reasonably short (≤300 chars — keyword lists rarely exceed this).
_METADATA_SHAPE_SEP_RE = re.compile(r";|,.*,.*,")
_METADATA_SENTENCE_VERB_RE = re.compile(
    r"\b(?:is|are|was|were|have|has|had|will|would|can|could|may|might|"
    r"should|must|do|does|did|been|being)\b",
    re.IGNORECASE,
)


def _looks_like_metadata_content(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 300:
        return False
    if not _METADATA_SHAPE_SEP_RE.search(s):
        return False
    if _METADATA_SENTENCE_VERB_RE.search(s):
        return False
    return True


def _demote_metadata_label_headings(text: str) -> str:
    """§B-new-2 HALLUC-HEAD-3: demote a ``## KEYWORDS`` (or similar metadata-
    label) heading when the next non-blank lines (within 3) match a metadata
    shape (separator-bearing list with no sentence verb).

    Fires only on h2/h3 headings whose entire text is one of
    ``_METADATA_LABEL_TOKENS``. Conservative: never fires on multi-word
    headings, never on headings whose follow-on is prose.
    """
    if not text:
        return text
    lines = text.split("\n")
    n = len(lines)
    out: list[str] = []
    i = 0
    while i < n:
        line = lines[i]
        m = re.match(r"^(#{2,4})\s+(.+?)\s*$", line)
        demoted = False
        if m:
            label = m.group(2).strip()
            if label in _METADATA_LABEL_TOKENS:
                # Find first metadata-shape line within ~15 non-heading
                # lines. Skip intervening headings (some papers — e.g.
                # xiao_2021_crsp — render with KEYWORDS / Introduction /
                # metadata-list, where the keywords list lands BELOW
                # `## Introduction` because R4 column-aware extraction
                # reorders the front-matter). Without the heading-skip,
                # the bare `## KEYWORDS` survived as an h2 even though
                # its metadata payload was clearly present, just offset
                # by one heading.
                next_line = ""
                j = i + 1
                scanned = 0
                while j < n and scanned < 15:
                    s = lines[j].strip()
                    if not s:
                        j += 1
                        continue
                    if re.match(r"^#{1,6}\s", s):
                        # Intervening heading — keep scanning past it,
                        # but cap the scan so we don't reach body prose.
                        j += 1
                        scanned += 1
                        continue
                    next_line = lines[j]
                    break
                if next_line and _looks_like_metadata_content(next_line):
                    # Emit as bold inline metadata label, not a heading. The
                    # metadata content line below stays as-is. We use bold
                    # rather than plain text so the label remains visually
                    # distinct in the rendered .md.
                    out.append(f"**{label}:**")
                    i += 1
                    demoted = True
        if not demoted:
            out.append(line)
            i += 1
    return "\n".join(out)


# ── §B-new-4 (2026-05-23): italic-label-with-comma heading demote ─────────
#
# Affects ip_feldman_2025_pspb and similar: an italic inline metadata phrase
# like ``*Data Availability, Preregistration, and Open-Science Disclosures.*``
# gets partitioned into ``## Data Availability`` heading + body sentence
# ``Preregistration, and Open-Science Disclosures.`` because the comma broke
# the label phrase across the heading and body.
#
# Fix shape: when a ``## <Heading>`` is followed by a body line that starts
# with a Title-Case continuation list pattern (``Word,`` or ``and Word``),
# the heading was wrongly split off a comma-broken metadata phrase. Demote
# the heading and rejoin into a single italic inline label.

_LIST_CONTINUATION_LEAD_RE = re.compile(
    r"^\s*(?:[A-Z][A-Za-z\-]+(?:\s+[A-Za-z\-]+){0,4}\s*,|"
    r"and\s+[A-Z][A-Za-z\-]+(?:\s+[A-Za-z\-]+){0,4}[.,])",
)


_METADATA_LABEL_HEADING_PREFIXES = frozenset({
    # Real metadata-label phrases that get comma-split across heading + body
    # by pdftotext column-wraps. Restricted to the open-science / data-
    # availability family — these are the only headings observed in the wild
    # (2026-05-23 ip_feldman finding #3) where the body continuation is a
    # genuine list-continuation of a metadata phrase, not a real subsection.
    "Data Availability",
    "Open Science Disclosures",
    "Preregistration",
    "Code Availability",
    "Open Practices",
    "Materials Availability",
    "Open Materials",
    "Open Data",
    "Author Contributions",
    "CRediT",
    "Funding",
    "Conflict of Interest",
    "Competing Interests",
})


def _demote_italic_label_with_comma_headings(text: str) -> str:
    """§B-new-4: demote ``## <Heading>`` when the immediately following non-
    blank paragraph begins with a list-continuation phrase that completes
    a metadata-label sentence (e.g. ``## Data Availability`` followed by
    ``Preregistration, and Open-Science Disclosures. We provided...``).

    Conservative gates:
      * Heading must be in ``_METADATA_LABEL_HEADING_PREFIXES`` — restricted
        to the open-science / data-availability metadata family. Without
        this allowlist, the heuristic fired on generic subsection words like
        ``## Discussion`` whose body legitimately starts with capital +
        comma'd subject phrase (``In this study, participants...``) and
        wrecked the rendered output.
      * Continuation paragraph must start with ``Word,`` or ``and Word`` shape.
      * Continuation paragraph must contain a sentence terminator (``.``)
        within its first sentence — a real metadata-label phrase ends with
        period, a body sentence opening with a comma'd word list rarely
        does in academic prose.

    2026-05-25 fix (Cluster A, finding #3 on ip_feldman_2025_pspb): scans
    up to the next ``\\n\\n`` paragraph break for the first sentence
    terminator, not just the single immediate next line — pdftotext
    column-wraps may push the terminator several lines down.  Original
    behaviour (`next_line.rstrip().endswith(".")`) silently failed on
    multi-line continuations.

    2026-05-25 wrapup: added ``_METADATA_LABEL_HEADING_PREFIXES`` allowlist
    after this demoter wrecked ``## Discussion`` on jdm_m.2022.2.pdf —
    flattening it to italic body that prevented the orphan-multilevel-
    number fold from producing ``### 5.4. Discussion``. The 2026-05-23
    pre-allowlist behaviour was too aggressive for the real corpus.
    """
    if not text:
        return text
    lines = text.split("\n")
    n = len(lines)
    out: list[str] = []
    i = 0
    while i < n:
        line = lines[i]
        m = re.match(r"^(#{2,4})\s+(.+?)\s*$", line)
        demoted = False
        if m:
            heading_text = m.group(2).strip()
            words = heading_text.split()
            if heading_text not in _METADATA_LABEL_HEADING_PREFIXES:
                # Not a known metadata-label prefix — never demote, even when
                # the body continuation looks list-shaped.
                pass
            elif 1 <= len(words) <= 3:
                # Find start of next non-blank paragraph (within 3 lines).
                j = i + 1
                while j < n and j - i <= 3 and not lines[j].strip():
                    j += 1
                if (
                    j < n
                    and j - i <= 3
                    and _LIST_CONTINUATION_LEAD_RE.match(lines[j].rstrip())
                ):
                    # Collect the full continuation paragraph (until next blank).
                    para_lines: list[str] = []
                    k = j
                    while k < n and lines[k].strip():
                        para_lines.append(lines[k].rstrip())
                        k += 1
                    para_text = " ".join(para_lines).strip()
                    # Find the first sentence (ending with `.` `!` or `?`,
                    # optionally close-quote/paren, followed by space+Capital
                    # or end-of-paragraph).  Without a terminator within the
                    # paragraph, we cannot safely demote.
                    sentence_match = re.match(
                        r"^(.+?[.!?][\"”’\)\]]*)(?:\s+[A-Z]|\s*$)",
                        para_text,
                    )
                    if sentence_match:
                        first_sentence = sentence_match.group(1).strip()
                        rest_offset = len(sentence_match.group(1))
                        rest = para_text[rest_offset:].lstrip()
                        # Emit demoted italic label + remaining paragraph as
                        # a separate body paragraph.  Preserves all body
                        # content; only the false heading is gone.
                        out.append(f"*{heading_text}, {first_sentence}*")
                        if rest:
                            out.append("")
                            out.append(rest)
                        i = k  # consumed [i..k-1]
                        demoted = True
        if not demoted:
            out.append(line)
            i += 1
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# ── B2c (2026-05-22): isolated method-subsection promotion ────────────────
#
# G5d: real subsection headings (``Participants``, ``Materials``,
# ``Procedure``, ``Measures``, ``Stimuli``, ``Design``, ``Apparatus``,
# ``Analysis``) appear alone on a line as titles for a method
# subsection. The general partitioner Pass 3 requires ≥5 chars AND
# ≥2 words for weak headings, so these single-word labels never get
# promoted. Render layer rescues them when they sit fully paragraph-
# isolated AND are immediately followed by prose.

_METHOD_SUBSECTION_LABELS = frozenset({
    "Participants",
    "Materials",
    "Procedure",
    "Procedures",
    "Measures",
    "Stimuli",
    "Design",
    "Apparatus",
    "Analysis",
    "Analyses",
    "Sample",
    "Subjects",
})


def _promote_isolated_method_subsection_headings(text: str) -> str:
    """B2c: promote a bare single-word method-subsection label to a
    ``### {label}`` heading when it is paragraph-isolated and the
    immediately following non-blank line is prose.

    Conservative gates that prevent false positives on table cells:
      * Line must be FULLY isolated (blank line before AND after).
      * Line content must be exactly one of ``_METHOD_SUBSECTION_LABELS``.
      * Next non-blank line must be PROSE (lowercase word, ≥20 chars)
        — table cells fail this gate because they are short tokens.
      * Previous non-blank line must NOT itself be a single token
        from ``_METHOD_SUBSECTION_LABELS`` (back-to-back labels are
        almost certainly a glossary or sidebar, not real subsections).
    """
    if not text:
        return text
    lines = text.split("\n")
    n = len(lines)
    out: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in _METHOD_SUBSECTION_LABELS and stripped:
            blank_before = i == 0 or not lines[i - 1].strip()
            blank_after = i == n - 1 or not lines[i + 1].strip()
            if blank_before and blank_after:
                # Find next non-blank line.
                j = i + 1
                while j < n and not lines[j].strip():
                    j += 1
                if j < n and _is_prose_line(lines[j]):
                    # Find previous non-blank line and reject if it is
                    # itself a labels-only sibling (sidebar / glossary).
                    k = i - 1
                    while k >= 0 and not lines[k].strip():
                        k -= 1
                    prev_is_sibling_label = (
                        k >= 0 and lines[k].strip() in _METHOD_SUBSECTION_LABELS
                    )
                    if not prev_is_sibling_label:
                        # Pad with a blank line above and below the
                        # promoted heading, matching the convention used
                        # by ``_promote_study_subsection_headings``.
                        if out and out[-1] != "":
                            out.append("")
                        out.append(f"### {stripped}")
                        out.append("")
                        continue
        out.append(line)
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# ── §B-new-1 (2026-05-23): generic Title-Case subsection promoter ─────────
#
# Wider analogue of B2c. The narrow ``_METHOD_SUBSECTION_LABELS`` set misses
# the long tail of paper-specific H3 subsection titles ("Self-control
# assessment", "Outcome variables", "Manipulation check") that appear as
# paragraph-isolated short Title-Case lines followed by prose. Per the
# cycle-1-2-3 verifier sweep across 5 canary papers, this is the largest
# single defect class (~80 findings).
#
# Shape gate (deliberately stricter than B2c to compensate for the open-set
# label vocabulary):
#   * Line is fully paragraph-isolated (blank before AND after).
#   * Line has ≤6 words AND ≤60 chars (real subsection titles are short).
#   * Every alphabetic word starts with an uppercase letter OR is one of
#     {of, the, and, a, an, in, for, to, on, with} (Title Case with
#     standard small-word exceptions).
#   * No sentence terminator (`.`, `?`, `!`) inside the line — real titles
#     don't have mid-sentence punctuation.
#   * No trailing colon (those are inline labels, handled elsewhere).
#   * Next non-blank line is PROSE (≥20 chars, contains a lowercase word).
#   * Previous non-blank line is PROSE or a heading — NOT another isolated
#     short line (which would indicate a glossary/sidebar/figure-caption
#     fragment, not a subsection break).
#   * Line does NOT match a known figure/table/equation label prefix.

_TITLE_CASE_SMALL_WORDS = frozenset({
    "of", "the", "and", "a", "an", "in", "for", "to", "on", "with",
    "or", "vs", "vs.", "by", "at", "as", "but", "nor", "&", "from",
    "into", "via", "per",
})

# Labels that should NEVER be promoted as a subsection heading (already
# handled by other passes, or structurally a different kind of element).
_NEVER_PROMOTE_PREFIXES = (
    "Table ", "Figure ", "Fig.", "Fig ", "Appendix ", "Box ",
    "Eq. ", "Equation ", "Note ", "Chapter ", "Section ", "Step ",
    "Algorithm ", "Listing ", "Scheme ",
)


def _looks_like_titlecase_subsection_label(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 60:
        return False
    if s.endswith((":", ".", "?", "!", ";", "—", "–")):
        return False
    if any(s.startswith(p) for p in _NEVER_PROMOTE_PREFIXES):
        return False
    # No sentence terminator inside the line (excluding the trailing-char check
    # above which catches end-of-line).
    if re.search(r"[.?!]\s", s):
        return False
    words = s.split()
    if not (1 <= len(words) <= 6):
        return False
    # The first word MUST start with an uppercase letter (a paragraph-
    # isolated short line beginning lowercase is almost certainly a
    # grammatical continuation / wrap, not a subsection title).
    first_bare = re.sub(r"^[\(\[\{]+|[\)\]\},]+$", "", words[0])
    if not first_bare or not first_bare[0].isalpha() or not first_bare[0].isupper():
        return False
    # Subsequent words: accept Sentence-case (first-word-capitalized, others
    # lowercase) AND Title-Case (every content word capitalized). Either is
    # the academic-subsection convention. Reject only if a word starts with
    # a NON-letter that isn't part of a hyphenated compound — e.g. a numeric
    # token that suggests a stat-row fragment.
    for w in words[1:]:
        bare = re.sub(r"^[\(\[\{]+|[\)\]\},]+$", "", w)
        if not bare:
            continue
        if not bare[0].isalpha():
            # Pure-numeric tokens reject (table cells "0.92"); compound
            # alpha-numeric ("5-HT", "2nd") with any alpha letter pass.
            if not any(c.isalpha() for c in bare):
                return False
            continue
        # Any alphabetic case accepted here (Sentence- or Title-Case both OK).
    # Must contain at least one ≥3-char alphabetic word (excludes "M = 5.4").
    if not any(len(re.sub(r"[^A-Za-z]", "", w)) >= 3 for w in words):
        return False
    return True


# Sentence-terminator detection — used by promote/demote helpers to reject
# candidates whose prior paragraph ended mid-sentence (a pdftotext column-wrap
# artifact).  Terminators: `.` `!` `?` optionally followed by close-quote
# (straight/curly) or close-paren/bracket.  Semicolons and colons do NOT
# count: a line ending with ";" or ":" is mid-list / lead-in to a display,
# not a sentence boundary.
#
# 2026-05-25 fix — Cluster A root cause: pdftotext routinely splits a body
# sentence at a column boundary, putting a short label-shaped line from the
# next column on a paragraph-isolated next line.  Every promotion helper
# until now checked only `blank_before` / `blank_after`; with this guard
# they also require the prior paragraph to be sentence-terminated.  Kills
# `### Supplemental Materials` mid-Method on ip_feldman + parallel false
# positives across the corpus.  Audit: tmp/iterate/canary-380647a7cb2a/.
_SENTENCE_TERMINATOR_RE = re.compile(
    r"[.!?][\"”’\)\]]*\s*$"
)


def _prev_paragraph_is_sentence_terminated(lines: list[str], i: int) -> bool:
    """Return True if the paragraph immediately preceding ``lines[i]`` ends
    with a sentence terminator (``.`` / ``!`` / ``?``, possibly followed by
    a close-quote or close-paren).  Returns True at start-of-document (no
    prior paragraph to corrupt).

    Also returns True when the prior non-blank line is a STRUCTURAL boundary
    (markdown heading ``#…``, italic-label ``*…*``, table fence ``<table>``,
    blockquote ``>``, list marker, or `---`-divider) — these are equivalents
    of "paragraph ended" for the purpose of admitting a subsequent heading
    candidate.  Without this, `### Background` after `## Introduction`
    gets rejected because `## Introduction` doesn't end with `.` `!` `?`.

    Used by promotion guards to reject candidates whose paragraph-isolation
    is a pdftotext column-wrap artifact rather than a real paragraph break.
    """
    k = i - 1
    while k >= 0 and not lines[k].strip():
        k -= 1
    if k < 0:
        return True  # start-of-document; nothing to mis-attribute to
    prev = lines[k].rstrip()
    if not prev:
        return True  # defensive
    # Structural-boundary equivalents — these are always "paragraph end"
    # regardless of whether they end with `.` `!` `?`.
    if prev.startswith(("#", "*", "<", ">", "|", "`", "---", "===")):
        return True
    if re.match(r"^\s*[\-+*]\s", prev) or re.match(r"^\s*\d+\.\s", prev):
        return True  # list item
    return bool(_SENTENCE_TERMINATOR_RE.search(prev))


# 2026-05-26 (Cluster A-ter): parent ``## `` section labels where stacked
# titlecase candidates are NOT subsection headings but list items:
#   - CRediT roles ("Methodology", "Data curation", "Writing - original
#     draft") under Author Contributions / CRediT.
#   - Declaration items under Declaration of Conflicting Interests.
#   - Funding agency names under Funding.
#   - Disclosure items under Disclosure / Open-Science.
# When the chain detection walks back to one of these parents, REJECT
# the chain — the candidates are content of the section, not subsections
# of it.
_CHAIN_REJECT_PARENTS = frozenset({
    "Author Contributions",
    "Authorship Declaration",
    "Authorship Statement",
    "Author Information",
    "Author Roles",
    "Author Statement",
    "Contributions",
    "CRediT",
    "CRediT Authorship Statement",
    "Declaration of Conflicting Interests",
    "Declaration of Interests",
    "Declarations",
    "Disclosure",
    "Disclosures",
    "Funding",
    "Funding Statement",
    "Conflict of Interest",
    "Conflicts of Interest",
    "Acknowledgments",
    "Acknowledgements",
    "ORCID iDs",
    "ORCID",
    "Notes",
    "References",
    "Bibliography",
    "Data Availability",
    "Data and Code Availability",
    "Supplemental Material",
    "Supplementary Materials",
    "Supplementary Information",
})


def _is_subsection_chain_member(lines: list[str], i: int) -> bool:
    """Return True when ``lines[i]`` is a paragraph-isolated short Title-
    Case line that participates in a CHAIN of consecutive blank-separated
    subsection-candidate lines, where the chain:

    1. Opens after a parent ``## `` heading (walking backward through the
       chain, the first non-candidate non-blank line MUST be a ``## `` —
       not a deeper heading, not body prose, not structural markup).
    2. Terminates in body prose (walking forward through the chain, the
       first non-candidate non-blank paragraph MUST be a multi-line
       paragraph OR a sentence-terminated long single-line ≥60 chars).

    Designed to recognise the PSPB / Sage / APA layout where pdftotext
    serialises a parent section with stacked subsection headings:

        ## Method

        Design and Procedure

        Power Analysis and Sensitivity Test

        We summarized the experimental design ... [multi-line body]

    The intermediate ``Design and Procedure`` and ``Power Analysis ...``
    labels should each promote to ``### {label}`` even though the
    cell-region (next-para single-line short non-terminated) and
    sibling-label (prev non-blank is a titlecase label) rejects in
    ``_promote_isolated_titlecase_subsection_headings`` individually
    block them.

    The chain check is STRUCTURAL — no paper identity, no fixed label
    vocabulary; position-agnostic (works in Methods, Results, Discussion,
    anywhere with a ``## `` parent). Accepts both
    ``_METHOD_SUBSECTION_LABELS`` members and general titlecase candidates
    as chain members.

    2026-05-26 (Cluster A-ter, ip_feldman finding cluster): closes the
    Method-subsection promotion gap that survived Cluster A's PSPB-style
    relaxation. Targets the 4-5 Method subsection findings on
    ip_feldman_2025_pspb plus analogous findings on chan_feldman and
    ar_apa where stacked subsections are demoted to plain text.
    """
    n = len(lines)
    s = lines[i].strip()
    if not s:
        return False
    if not (
        _looks_like_titlecase_subsection_label(s)
        or s in _METHOD_SUBSECTION_LABELS
    ):
        return False

    # Walk BACKWARD through STRICTLY ADJACENT (blank, titlecase-candidate)
    # pairs counting candidates until reaching the ``## `` parent.  Any
    # body line, heading other than ``## ``, structural markup, or non-
    # candidate content BETWEEN the candidate and its parent rejects the
    # chain — the chain bypass is reserved for STACKED-adjacent
    # subsection sets (where the only thing between candidate and ``## ``
    # parent is other candidates + blank lines).  This conservatism keeps
    # the bypass from over-promoting table-cell labels that happen to
    # appear deeper in a ``## `` section (e.g. Table 4 row labels on
    # ip_feldman, which look like a chain but aren't real subsections).
    backward_count = 0
    parent_found = False
    parent_label = ""
    k = i - 1
    while k >= 0:
        while k >= 0 and not lines[k].strip():
            k -= 1
        if k < 0:
            return False  # walked off top without ## parent
        prev = lines[k].strip()
        if prev.startswith("## ") and not prev.startswith("### "):
            parent_found = True
            parent_label = prev[3:].strip()
            break
        # Any other heading (# / ### / #### / etc.) breaks adjacency
        if prev.startswith("#"):
            return False
        if (
            _looks_like_titlecase_subsection_label(prev)
            or prev in _METHOD_SUBSECTION_LABELS
        ):
            backward_count += 1
            k -= 1
            continue
        # Body / structural markup / non-candidate — chain broken
        return False
    if not parent_found:
        return False

    # 2026-05-26 (Cluster A-ter): reject when parent section is a known
    # non-subsection-bearing section (Author Contributions, CRediT,
    # Acknowledgments, Funding, etc.).  Candidates underneath those
    # parents are list items (CRediT roles, ORCID names, funding agencies),
    # not subsection headings.  Even when the stacked-adjacent shape
    # matches, the parent identity tells us "this stack is content, not
    # subsections."
    if parent_label in _CHAIN_REJECT_PARENTS:
        return False

    # Walk FORWARD through ADJACENT (blank, titlecase-candidate) pairs
    # counting candidates until reaching body prose or end-of-doc.
    # ``### `` sibling subsections (already-promoted candidates from the
    # SAME or a PRIOR iteration of this promoter) are transparent — they
    # don't count toward the chain but don't break it either.
    forward_count = 0
    body_found = False
    j = i + 1
    while j < n:
        while j < n and not lines[j].strip():
            j += 1
        if j >= n:
            return False  # walked off bottom with no body
        para_first = lines[j].strip()
        para_count = 0
        m = j
        while m < n and lines[m].strip():
            para_count += 1
            m += 1
        # ``### `` sibling subsection — transparent (advance j past it,
        # don't count toward chain, don't break).
        if para_first.startswith("### "):
            j = m
            continue
        # Other heading depth (# / ## / #### / etc.) — chain broken
        if para_first.startswith("#"):
            return False
        # Multi-line paragraph = body
        if para_count >= 2:
            body_found = True
            break
        # Single-line: body if long (≥60 chars) or sentence-terminated
        if len(para_first) >= 60 or para_first[-1:] in ".!?":
            body_found = True
            break
        if (
            _looks_like_titlecase_subsection_label(para_first)
            or para_first in _METHOD_SUBSECTION_LABELS
        ):
            forward_count += 1
            j = m
            continue
        return False  # non-candidate non-body — chain broken
    if not body_found:
        return False

    # Adjacent chain SIZE = 1 (current) + adjacent_backward + adjacent_forward.
    # Require ≥ 2 — solo candidates (size 1) are handled by the standard
    # gates with PSPB-style relaxation; the chain bypass exists only for
    # the stacked-candidates case the standard gates can't see across.
    adjacent_chain_size = 1 + backward_count + forward_count
    return adjacent_chain_size >= 2


# ── Wrapped-title-duplicate demoter (2026-06-06, Cycle 4 redux) ────────────
#
# Pdftotext routinely emits the document title TWICE on PSPB / Sage / APA
# two-column layouts: once as the main full-width title (becomes `# H1`),
# and a second time as a running-header copy at the top of column 1
# broken across column-wrapped lines. Until cycle 4, the publisher
# metadata block (article ID, article-type code) absorbed/separated the
# duplicate so it never became a `### ` promotion candidate.
#
# Cluster E re-land (2026-06-06) strips the metadata absorber, which
# exposes the duplicate as a candidate. The candidate then passes
# `_promote_isolated_titlecase_subsection_headings`'s gate set (the
# prev-paragraph-terminator guard treats the `# H1` as a structural
# boundary; no other reject catches it because the chain detector
# correctly returns False for an H1 parent, and the immediate prev-non-
# blank H1 reject doesn't see across multi-line continuation forms),
# producing `### The Complex Misestimation of Others'` immediately under
# the H1 with continuation lines as orphan body.
#
# This demoter runs AFTER all promotion passes and looks for the
# STRUCTURAL signature — a `### ` heading immediately after `# H1`,
# whose token concatenation (with subsequent continuation lines) is an
# ordered prefix of the H1's tokens. When detected with ≥75% coverage
# of the H1 tokens, strip the `### ` line + continuation lines.
_TITLE_DUPLICATE_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


# ── Cohesive front-matter masthead-block strip (2026-06-06, Cycle 4 redux) ─
#
# pdftotext serialises the title-page publisher masthead (journal name,
# volume/page range, society copyright, DOI, article-reuse URLs) inline
# with the title + author block on column-heavy layouts (Sage / PSPB /
# APA). Existing P0 / P0r / P1 strippers (normalize.py) catch the lines
# that carry a recognisable publisher signature (©-copyright, sagepub
# URLs, "Article reuse guidelines:", JAMA-style footers). What survives
# to the rendered body on ip_feldman_2025_pspb (canary finding #1,
# METADATA-LEAK @ lines 1-17) is the residue: author-name+superscript
# lines, journal-name wrap fragments, a bare page-range, a copyright
# tail, the "DOI:" label, and the bare DOI — all sitting between the H1
# title and the `## Abstract` heading.
#
# This pass runs at render level (AFTER title rescue inserts the `# H1`)
# and strips that residual masthead block with a cohesive-block gate:
# the H1→first-`##` zone must contain >= 2 HARD masthead markers (bare
# DOI / DOI: label / page-range / author-name+superscript / ©-copyright)
# before any line is removed. The gate makes the pass self-limiting:
# on a paper whose H1→`##` zone is real content (no masthead residue),
# fewer than 2 hard markers are present and the pass is a no-op.
#
# General by construction — keyed on structural shapes (DOI grammar,
# page-range grammar, name+trailing-affiliation-digit, ©), never on
# paper identity or a hard-coded journal string. See Run-11 handoff
# (2026-05-26-run-11-...) cycle-4-redux step 2.

# Hard masthead markers (presence of >=2 in the zone confirms a masthead
# block and licenses stripping the softer journal-name / society wraps).
_MASTHEAD_BARE_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
_MASTHEAD_DOI_LABEL_RE = re.compile(
    r"^(?:DOI:?|https?://(?:dx\.)?doi\.org/\S+)\s*$", re.IGNORECASE
)
# Page / volume range: optional leading BOM/soft-hyphen junk, NN-NN.
_MASTHEAD_PAGE_RANGE_RE = re.compile(
    r"^[﻿­\s]*\d{1,4}\s*[­\-‐-―]\s*\d{1,4}\s*$"
)
# Author name with a trailing affiliation superscript digit (1-2 digits),
# optionally led by "and " (pdftotext splits multi-author lists).
_MASTHEAD_AUTHOR_SUPERSCRIPT_RE = re.compile(
    r"^(?:and\s+)?[A-Z][a-zA-Z.’']+(?:\s+[A-Z][a-zA-Z.’']+){1,3}\d{1,2}$"
)
# Copyright line / tail (© ... OR a "..., Inc"/"Society for ..." fragment).
_MASTHEAD_COPYRIGHT_RE = re.compile(
    r"(?:^\s*(?:©|\(c\)|copyright\b)"
    r"|\bSociety\s+for\b"
    r"|,\s*Inc\.?\s*$)",
    re.IGNORECASE,
)


def _looks_like_masthead_hard_marker(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    return bool(
        _MASTHEAD_BARE_DOI_RE.match(s)
        or _MASTHEAD_DOI_LABEL_RE.match(s)
        or _MASTHEAD_PAGE_RANGE_RE.match(s)
        or _MASTHEAD_AUTHOR_SUPERSCRIPT_RE.match(s)
        or _MASTHEAD_COPYRIGHT_RE.search(s)
    )


def _is_frontmatter_prose_line(line: str) -> bool:
    """A line that is clearly running prose (not masthead) — used to
    terminate the masthead zone so an undetected abstract or any real
    body text before the first `## ` heading is never stripped.

    Conservative: only a long (>=80 char) line ending in a sentence
    terminator counts as prose. Short masthead lines (author names,
    journal wraps, DOI) never reach 80 chars + terminator.
    """
    s = line.strip()
    if len(s) < 80:
        return False
    return bool(_SENTENCE_TERMINATOR_RE.search(s))


def _strip_frontmatter_masthead_block(text: str) -> str:
    """Strip the residual publisher masthead block between the document
    H1 and the first `## ` body-section heading.

    Fires only when the zone holds >= 2 hard masthead markers. Walks the
    zone from H1+1, stopping at the first `## ` heading OR the first prose
    line OR 30 lines (whichever comes first); every non-blank line in the
    confirmed zone is masthead and is removed. Blank-line structure is
    re-collapsed afterward.

    No-op when: no H1 present; zone has < 2 hard markers; the very first
    post-H1 content is prose (real body — nothing to strip).
    """
    if not text:
        return text
    lines = text.split("\n")
    n = len(lines)

    h1_idx = -1
    for idx, line in enumerate(lines):
        s = line.lstrip()
        if s.startswith("# ") and not s.startswith("## "):
            h1_idx = idx
            break
    if h1_idx < 0:
        return text

    zone_indices: list[int] = []
    hard_markers = 0
    j = h1_idx + 1
    walked = 0
    while j < n and walked <= 30:
        raw = lines[j]
        s = raw.strip()
        if s.startswith("## "):
            break  # body-section boundary — zone ends
        if _is_frontmatter_prose_line(raw):
            break  # real content — stop, preserve everything from here
        if s:
            zone_indices.append(j)
            if _looks_like_masthead_hard_marker(raw):
                hard_markers += 1
        j += 1
        walked += 1

    if hard_markers < 2 or not zone_indices:
        return text

    strip = set(zone_indices)
    out = [line for i, line in enumerate(lines) if i not in strip]
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# ── Column-wrapped subsection-heading repair (2026-06-06, Cycle 4 redux) ───
#
# Dense two-column Sage / PSPB / APA layouts column-wrap a subsection
# heading whose title carries a citation. pdftotext serialises the wrap
# as two physical lines, producing two distinct defect shapes that the
# section partitioner + the render-level promoters cannot catch (the
# title trips the `et al.` sentence-internal-period gate, the 6-word cap,
# and the trailing-colon gate in `_looks_like_titlecase_subsection_label`
# — gates that exist to reject prose corpus-wide and must NOT be relaxed
# globally; see LESSONS + RCA 2026-06-06).
#
# Two tightly-gated structural signatures (no paper identity, no hard-
# coded strings — keyed purely on citation/wrap typography):
#
#   Rule A — citation-wrap promote (canary finding #3):
#       Choice of Study for Replication: Jordan et al.   <- L0 (blank-before, Title-Case, ends "et al.")
#       (2011)                                            <- L1 (bare year, alone on its line)
#                                                         <- blank
#       We aimed to revisit ...                           <- body prose
#     -> ### Choice of Study for Replication: Jordan et al. (2011)
#     A bare "(YYYY)" alone on its own line only happens when a citation
#     in a SHORT heading overflows the wrap; in body the year stays glued
#     to the following text. That is the disambiguating signal.
#
#   Rule B — orphan tail reattach (canary finding #4):
#       ### Original Hypotheses and Findings in Target    <- H (h2/h3, no terminal .!?:)
#                                                         <- blank
#       Article: Jordan et al. (2011)                     <- T (short, colon-led completion)
#       Jordan et al. (2011) empirical work ...           <- body prose
#     -> ### Original Hypotheses and Findings in Target Article: Jordan et al. (2011)
#     Generalises the proven `_merge_compound_heading_tails` off its
#     hard-coded JAMA tail list to any short colon-led / paren-led tail.
_CITATION_WRAP_L0_RE = re.compile(
    r"^[A-Z][A-Za-z].{0,58}\bet al\.$"      # Title-Case start, <=60 chars, ends "et al."
)
_BARE_YEAR_LINE_RE = re.compile(
    r"^\(\d{4}[a-z]?\)[.,;]?$"               # (2011) / (2011a) / (2011). alone
)
_ORPHAN_TAIL_RE = re.compile(
    r"^(?:[A-Z][a-z]+:|\()"                  # colon-led word ("Article:") or paren-led
)


def _repair_column_wrapped_headings(text: str) -> str:
    """Repair column-wrapped subsection-heading titles (Rules A + B above).

    Conservative — both rules require the wrap-continuation to be followed
    by body prose (never another heading), so two real sibling headings
    are never merged, and a real heading is never extended with a real
    body sentence (the tail is short + has a heading-completion shape).
    """
    if not text:
        return text
    lines = text.split("\n")
    n = len(lines)
    out: list[str] = []
    i = 0
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # ── Rule B: orphan tail reattach to an existing heading ──────────
        m_h = re.match(r"^(#{2,3})\s+(.*)$", stripped)
        if m_h:
            htext = m_h.group(2).rstrip()
            if htext and htext[-1] not in ".!?:":
                # next non-blank line
                j = i + 1
                while j < n and not lines[j].strip():
                    j += 1
                if j < n:
                    tail = lines[j].strip()
                    tail_words = tail.split()
                    # line after the tail must be body prose (not heading/markup)
                    k = j + 1
                    while k < n and not lines[k].strip():
                        k += 1
                    after_is_prose = (
                        k < n
                        and not lines[k].lstrip().startswith(
                            ("#", "*", "<", ">", "|", "`", "-", "+")
                        )
                        and len(lines[k].strip()) >= 40
                    )
                    if (
                        len(tail) <= 55
                        and 1 <= len(tail_words) <= 7
                        and _ORPHAN_TAIL_RE.match(tail)
                        and tail[-1] not in ".!?"  # tail isn't a full sentence
                        and after_is_prose
                    ):
                        out.append(f"{m_h.group(1)} {htext} {tail}")
                        # skip blanks + the tail line; continue from k
                        out.append("")
                        i = k
                        continue

        # ── Rule A: citation-wrap promote (body L0 + bare-year L1) ───────
        blank_before = (not out) or out[-1].strip() == ""
        if (
            blank_before
            and stripped
            and _CITATION_WRAP_L0_RE.match(stripped)
            and i + 1 < n
            and _BARE_YEAR_LINE_RE.match(lines[i + 1].strip())
        ):
            # line after the bare-year must be body prose
            k = i + 2
            while k < n and not lines[k].strip():
                k += 1
            after_is_prose = (
                k < n
                and not lines[k].lstrip().startswith(
                    ("#", "*", "<", ">", "|", "`", "-", "+")
                )
                and len(lines[k].strip()) >= 40
            )
            if after_is_prose:
                joined = f"{stripped} {lines[i + 1].strip()}"
                if out and out[-1] != "":
                    out.append("")
                out.append(f"### {joined}")
                out.append("")
                i += 2
                # swallow the blank(s) between L1 and prose
                while i < n and not lines[i].strip():
                    i += 1
                continue

        out.append(line)
        i += 1

    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _demote_wrapped_title_duplicate(text: str) -> str:
    """Strip a `### {prefix-of-H1}` + continuation block immediately
    following the document H1, where the block's token sequence is an
    ordered prefix of the H1's tokens (≥75% coverage).

    Pattern (after the standard promote/demote passes):

        # The Complex Misestimation of Others' Emotions: Underestimation
        of Emotional Prevalence Versus Overestimation of Emotional
        Intensity and Their Associations with Well-Being

        ### The Complex Misestimation of Others'

        Emotions: Underestimation of Emotional
        Prevalence Versus Overestimation of Emotional Intensity and
        Their Associations with Well-Being

    The `### ` line + 3 continuation lines together reconstruct the H1's
    token sequence as an ordered prefix. Strip them.

    Conservative gates (no false-positive paths):
    - Only fires when an H1 (`# `) is present in the doc.
    - Only considers a `### ` candidate within 2 blank lines after the H1
      (so a legitimate `### Background` after `## Introduction` body is
      safe — it's not immediately after the H1).
    - Requires the candidate + accumulated continuation tokens to form
      an EXACT ordered prefix of the H1 tokens (modulo punctuation).
    - Requires ≥75% H1-token coverage to fire (a short coincidental
      prefix like `### The Complex` alone with 3 tokens against a 20-
      token H1 has 15% coverage and is preserved).
    - H1 must have ≥4 tokens (skip short titles where false-positive
      risk is higher).

    See Run-11 handoff line 93-100 + cycle 4 lesson for the structural
    background.
    """
    if not text:
        return text
    lines = text.split("\n")
    n = len(lines)

    # Find the first H1 (`# ` not `## `).
    h1_idx = -1
    for idx, line in enumerate(lines):
        s = line.lstrip()
        if s.startswith("# ") and not s.startswith("## "):
            h1_idx = idx
            break
    if h1_idx < 0:
        return text

    h1_text = lines[h1_idx].lstrip()[2:]  # strip `# `
    h1_tokens = [
        t.lower() for t in _TITLE_DUPLICATE_TOKEN_RE.findall(h1_text)
    ]
    if len(h1_tokens) < 4:
        return text  # too-short title; false-positive risk too high

    # Scan forward for the `### ` candidate within ≤2 blank lines.
    j = h1_idx + 1
    blanks_skipped = 0
    while j < n and not lines[j].strip():
        blanks_skipped += 1
        if blanks_skipped > 2:
            return text
        j += 1
    if j >= n:
        return text

    cand = lines[j].lstrip()
    if not cand.startswith("### ") or cand.startswith("#### "):
        return text

    # Build accumulated tokens from `### ` candidate + continuation lines.
    accum_tokens: list[str] = [
        t.lower() for t in _TITLE_DUPLICATE_TOKEN_RE.findall(cand[4:])
    ]
    if not accum_tokens:
        return text
    # Must already be a prefix of H1 tokens.
    if accum_tokens != h1_tokens[:len(accum_tokens)]:
        return text

    # Walk forward absorbing continuation lines as long as they extend
    # the prefix match.  block_end is the FIRST line we keep
    # (i.e. lines[j..block_end-1] are candidates for strip).
    block_end = j + 1
    k = j + 1
    while k < n and len(accum_tokens) < len(h1_tokens):
        s = lines[k].strip()
        if not s:
            k += 1
            continue
        if s.startswith(("#", "*", "<", ">", "|", "`")):
            break  # structural marker terminates the duplicate block
        new_tokens = [
            t.lower() for t in _TITLE_DUPLICATE_TOKEN_RE.findall(s)
        ]
        trial = accum_tokens + new_tokens
        if len(trial) > len(h1_tokens):
            break  # would exceed H1 length — not a prefix
        if trial != h1_tokens[:len(trial)]:
            break  # divergence from H1 token sequence
        accum_tokens = trial
        block_end = k + 1
        k += 1

    # Require ≥75% H1-token coverage to be confident.
    coverage = len(accum_tokens) / len(h1_tokens)
    if coverage < 0.75:
        return text

    # Strip lines[j..block_end-1] (the `### ` line + continuation lines).
    out = lines[:j] + lines[block_end:]
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _strip_pre_title_heading_noise(text: str) -> str:
    """Strip heading markup that appears ABOVE the document H1 title.

    A real section/subsection heading never precedes the title. A ``#``-
    prefixed line in the pre-title masthead zone is a promoted journal-
    section label (e.g. ``### FlashReport`` / ``### RESEARCH ARTICLE`` on
    Elsevier front matter) — masthead noise the gold omits. Drop those
    lines entirely.

    Must run AFTER title rescue (the H1 is the anchor). No-op when there is
    no H1 or no heading precedes it. General — keyed on "a heading line sits
    above the document title", never on the label text.

    2026-06-06 (run-11, ar_apa `### FlashReport`).
    """
    if not text:
        return text
    lines = text.split("\n")
    h1_idx = -1
    for ix, ln in enumerate(lines):
        s = ln.lstrip()
        if s.startswith("# ") and not s.startswith("## "):
            h1_idx = ix
            break
    if h1_idx <= 0:
        return text
    out: list[str] = []
    for ix, ln in enumerate(lines):
        if ix < h1_idx and ln.lstrip().startswith("#"):
            continue  # drop pre-title heading-noise line
        out.append(ln)
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _nearest_h2_parent_label(lines: list[str], i: int) -> Optional[str]:
    """Walk backward from ``lines[i]`` to the nearest ``## `` heading and
    return its label, tolerating interleaved running-header / short non-
    heading lines. Returns None if the document H1 (``# ``) is reached
    first (no enclosing ``## `` section) or no parent is found within a
    bounded scan.

    2026-06-06 (run-11): used by the regular promotion path to consult
    ``_CHAIN_REJECT_PARENTS`` the same way the chain path does, so a CRediT
    role label (e.g. ``Methodology``) stranded under ``## Author
    Contributions`` by an interleaved running-header line is not promoted.
    """
    k = i - 1
    seen = 0
    while k >= 0 and seen < 80:
        s = lines[k].strip()
        if s.startswith("## ") and not s.startswith("### "):
            return s[3:].strip()
        if s.startswith("# ") and not s.startswith("## "):
            return None  # hit the H1 title; no enclosing ## section
        k -= 1
        seen += 1
    return None


def _promote_isolated_titlecase_subsection_headings(text: str) -> str:
    """§B-new-1: promote paragraph-isolated Title-Case short lines (≤6 words,
    ≤60 chars) followed by prose to ``### {label}`` headings.

    Strict gates to prevent figure-caption / table-cell / sidebar false
    positives — see ``_looks_like_titlecase_subsection_label`` and the prev-
    line non-sibling guard below. Conservative: skips lines already wrapped
    in any markdown structural marker.

    2026-05-25 guard added: prior paragraph MUST be sentence-terminated.
    Pdftotext column-wraps that orphan a short title-case line in the
    middle of a sentence are NOT real subsection labels and must not be
    promoted (e.g. ``### Supplemental Materials`` mid-Method on
    ip_feldman_2025_pspb).  See ``_prev_paragraph_is_sentence_terminated``.

    2026-05-26 (Cluster A-ter): chain detection — when the candidate is
    part of a verified ``## ``-rooted chain of consecutive titlecase
    labels terminating in body prose, bypass the cell-region /
    sibling-label / prev-paragraph-terminator rejects (they correctly
    reject individual candidates that look like cell labels, but they
    can't see across the chain to confirm the candidates are real
    stacked subsections). See ``_is_subsection_chain_member``.
    """
    if not text:
        return text
    lines = text.split("\n")
    n = len(lines)
    out: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip lines that already carry structural markup.
        if not stripped or stripped.startswith(("#", "*", "_", "<", ">", "|", "`", "-", "+")):
            out.append(line)
            continue
        # 2026-05-26 (Cluster A-ter): chain promotion BEFORE the standard
        # gate set.  When chain detection confirms ``## `` parent + body
        # terminus, all the individual-candidate rejects are bypassed.
        # Also covers _METHOD_SUBSECTION_LABELS members that B2c rejected
        # (e.g. "Measures" with blank_after=False).
        if _is_subsection_chain_member(lines, i):
            if out and out[-1] != "":
                out.append("")
            out.append(f"### {stripped}")
            out.append("")
            continue
        # B2c (``_promote_isolated_method_subsection_headings``) handles
        # ``_METHOD_SUBSECTION_LABELS`` members when they are FULLY blank-
        # isolated (blank_before AND blank_after).  When they aren't
        # — PSPB / Sage layouts that place the label directly above body
        # prose with no blank between — B2c rejects them.  Let the
        # general promoter step in via its PSPB-style relaxation
        # (handles blank_after=False when next line is prose).
        # 2026-05-26 (Cluster A-ter): previously this skipped unconditionally,
        # which left ip_feldman_2025_pspb's solo ``Measures`` /
        # ``Data Analysis Strategy`` etc. permanently as plain body text.
        if stripped in _METHOD_SUBSECTION_LABELS:
            _b2c_blank_before = i == 0 or not lines[i - 1].strip()
            _b2c_blank_after = i == n - 1 or not lines[i + 1].strip()
            if _b2c_blank_before and _b2c_blank_after:
                # B2c's eligibility conditions met — it handled (or
                # rejected) this line under its own gate set; don't
                # double-process.
                out.append(line)
                continue
            # else: B2c rejected because of blank_after=False — fall
            # through so general PSPB-style relaxation can handle.
        if not _looks_like_titlecase_subsection_label(stripped):
            out.append(line)
            continue
        blank_before = i == 0 or not lines[i - 1].strip()
        blank_after = i == n - 1 or not lines[i + 1].strip()
        # 2026-05-25 (PSPB-style heading: blank-before + immediate body):
        # Sage / APA two-column layouts often place a subsection heading
        # (single Title-Case line) immediately followed by the body text
        # on the next line WITHOUT a blank line between them.  The original
        # helper required blank_after, which rejected legitimate PSPB
        # subsection headings ("Background", "Choice of Study", "The
        # Misestimation of Others' Emotions" on ip_feldman_2025_pspb).
        # New logic: blank_before required; blank_after is sufficient
        # alone, but when missing, we also admit when the line passes
        # the stricter title-case-label check AND the immediate next line
        # is body prose (lowercase or sentence-starter Capital).  All the
        # downstream gates (prior-paragraph-terminator, sibling-label,
        # structural-markup-prev) still apply.
        if not blank_before:
            out.append(line)
            continue
        if not blank_after:
            # Allow only when next line is immediate body prose AND the
            # candidate line passes the strict title-case-label shape.
            next_line_raw = lines[i + 1] if i + 1 < n else ""
            next_line_stripped = next_line_raw.strip()
            if not next_line_stripped:
                out.append(line)
                continue
            # Next must be prose (a body sentence, not another label).
            # _is_prose_line is the standard prose check.
            if not _is_prose_line(next_line_raw):
                out.append(line)
                continue
            # Don't admit if current line ends with a terminator (then it's
            # a sentence, not a heading).
            if stripped[-1] in ".!?":
                out.append(line)
                continue
        # Next non-blank line must be PROSE (validated above for the
        # no-blank-after path; here for the blank-after path).
        j = i + 1
        while j < n and not lines[j].strip():
            j += 1
        if j >= n or not _is_prose_line(lines[j]):
            out.append(line)
            continue
        # 2026-05-25 guard (Cluster B residue, ip_feldman finding #4):
        # Look at the NEXT paragraph after current.  A real subsection
        # heading is followed by a multi-line body paragraph (≥3 wrapped
        # lines forming a sentence-terminated body).  A cell-region label
        # is followed by a SINGLE-LINE short paragraph (the next cell
        # label).  Count consecutive non-blank lines starting at j —
        # if it's just 1 line AND that line is short + non-terminated,
        # we're in cell-region (reject).  This preserves PSPB-style
        # subsection headings (whose body paragraphs wrap across 3-8 lines
        # with no internal blanks) while rejecting cell labels (each on
        # its own single-line paragraph).
        next_para_line_count = 0
        k = j
        while k < n and lines[k].strip():
            next_para_line_count += 1
            k += 1
        next_para_first = lines[j].strip()
        if (
            next_para_line_count == 1
            and len(next_para_first) < 60
            and next_para_first[-1:] not in ".!?"
        ):
            out.append(line)
            continue
        # 2026-05-25 guard (Cluster A): prior paragraph MUST be sentence-
        # terminated.  Pdftotext column-wraps that orphan a short title-case
        # line in the middle of a wrapped sentence are NOT real subsection
        # labels.  Without this guard, "Supplemental Materials" appearing
        # mid-paragraph (because pdftotext split "...summarized in the\n\n
        # Supplemental Materials\n\nThere were...") gets falsely promoted.
        if not _prev_paragraph_is_sentence_terminated(lines, i):
            out.append(line)
            continue
        # Previous non-blank line must NOT itself be a short isolated
        # title-case line (sibling-label / glossary-sidebar / figure-
        # caption fragment shape).
        k = i - 1
        while k >= 0 and not lines[k].strip():
            k -= 1
        if k >= 0:
            prev = lines[k].strip()
            if (
                _looks_like_titlecase_subsection_label(prev)
                or prev in _METHOD_SUBSECTION_LABELS
            ):
                out.append(line)
                continue
            # Also skip when prev is structural markup (figure / table /
            # blockquote / fence / italic-label / list / divider) — those
            # contexts are not real "end of prior subsection" boundaries.
            # 2026-05-25 carve-out: a parent HEADING ("## Introduction") IS
            # a valid prior context for a subsection-heading promotion —
            # we want "Background" promoted to "### Background" right
            # after "## Introduction".  Without this carve-out, PSPB-style
            # subsection headings remain plain text body across the whole
            # Introduction / Method / Results / Discussion.
            if prev.startswith(("*", "<", ">", "|", "`", "-", "+", "_")):
                out.append(line)
                continue
            # Heading-prefix: only skip if the candidate would create a
            # nonsensical level relationship (e.g. promoting a label right
            # after another `###` heading — implies the prior section had
            # zero body).  Allow promotion when prev is ## or higher.
            if prev.startswith("###"):
                out.append(line)
                continue
            # 2026-05-26 (Cluster E side-effect fix): also reject when prev
            # is a top-level ``# `` H1 title.  pdftotext routinely emits
            # the title twice — once as the H1 + a running-header copy
            # broken across wrap lines at the top of column 1.  The
            # running-header first wrap line is a title-case candidate;
            # without this reject it would promote to ``### `` and
            # duplicate the title (e.g. ip_feldman_2025_pspb after
            # Cluster E stripped the metadata block that previously
            # separated them).
            if prev.startswith("# ") and not prev.startswith("## "):
                out.append(line)
                continue
        # 2026-06-06 (run-11 finding cluster): the following body must read
        # as a real subsection body. A candidate whose body's FIRST
        # alphabetic character is lowercase is a fragment torn from a running
        # sentence — the candidate line was a table-cell value / mid-sentence
        # wrap, not a title. E.g. `### Close replication` then "testing the
        # proposed causal chain..." (chan_feldman); `### Proced` then
        # "age >=18 years..." (plos_med, a truncation fragment). A genuine
        # subsection body opens with a capital. (Chain-validated stacked
        # subsections bypass this — they took the early chain path above.)
        _body_first = lines[j].strip()
        _body_first_alpha = next((c for c in _body_first if c.isalpha()), "")
        if _body_first_alpha and _body_first_alpha.islower():
            out.append(line)
            continue
        # 2026-06-06 (run-11, plos_med `### Methodology`): reject promotion
        # when the nearest enclosing `## ` parent is a known non-subsection-
        # bearing section (Author Contributions / CRediT / Funding / ...).
        # Generalizes the chain-path `_CHAIN_REJECT_PARENTS` protection to the
        # regular promotion path — a CRediT role label gets here when an
        # interleaved running-header line breaks chain adjacency.
        _parent_label = _nearest_h2_parent_label(lines, i)
        if _parent_label is not None and _parent_label in _CHAIN_REJECT_PARENTS:
            out.append(line)
            continue
        # Promote.
        if out and out[-1] != "":
            out.append("")
        out.append(f"### {stripped}")
        out.append("")
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


_CELL_FRAGMENT_NO_TERMINATOR_RE = re.compile(
    r"^[^.!?]{0,60}$"  # no sentence terminator anywhere in the line
)
# Data-cell signature patterns (any-match → cell fragment).
_DATA_UNIT_SUFFIX_RE = re.compile(
    r",\s*(?:%|kg|cm|mm|mg/dL|mL|g/L|g/dL|U/L|nmol/L|mmol/L|pg/mL|ng/mL|"
    r"min|h|d|y|years|wk|weeks|months|mo|s)\b\s*$"
)
_STATS_LABEL_SUFFIX_RE = re.compile(
    r"\b(?:Mean|Median|SD|IQR|SE|CI|No\.|%)\b\s*=?\s*$"
)
_SINGLE_TITLECASE_TOKEN_RE = re.compile(r"^[A-Z][a-z]*$")
_SINGLE_ACRONYM_TOKEN_RE = re.compile(r"^[A-Z]{1,6}$")
_NUMERIC_PREFIX_RE = re.compile(r"^\d+(?:\.\d+)*\.?\s+\S")


def _is_table_cell_fragment(line: str) -> bool:
    """Stricter than ``not _is_prose_line``: a line counts as a TABLE-CELL
    FRAGMENT when it is short AND lacks a sentence terminator anywhere
    (`.` / `!` / `?`) OR carries an unambiguous data-label suffix
    (`, %` / `, mg/dL` / `, kg`) / numeric prefix / single-word column-
    label shape.
    """
    s = line.strip()
    if not s or len(s) > 60 or len(s.split()) > 8:
        return False
    if s.startswith(("#", ">", "|", "`", "<", "*", "_")):
        return False
    if (_DATA_UNIT_SUFFIX_RE.search(s)
        or _STATS_LABEL_SUFFIX_RE.search(s)
        or _SINGLE_TITLECASE_TOKEN_RE.match(s)
        or _SINGLE_ACRONYM_TOKEN_RE.match(s)
        or _NUMERIC_PREFIX_RE.match(s)):
        return True
    if _CELL_FRAGMENT_NO_TERMINATOR_RE.match(s):
        return True
    return False


_PHANTOM_TABLE_HEADER_PATTERNS = [
    # JAMA Open journal masthead leak.
    re.compile(r"JAMA\s+Network\s+Open\s*[|]", re.IGNORECASE),
    re.compile(r"JAMA\s+Network\s+Open\s+\|\s+\S", re.IGNORECASE),
    # NEJM masthead.
    re.compile(r"The\s+NEW\s+ENGLAND\s+JOURNAL", re.IGNORECASE),
    # Generic "Journal of X | Subsection" running header.
    re.compile(r"^[A-Z][\w\s]+\s+\|\s+[A-Z]\w+", re.MULTILINE),
]

_PHANTOM_TABLE_BODY_LEAK_TOKENS = frozenset({
    "Discussion", "Conclusion", "Conclusions", "Introduction", "Methods",
    "Method", "Results", "Limitations", "References", "Background",
    "Materials", "Procedure", "Participants",
})


def _strip_phantom_camelot_tables(text: str) -> str:
    """jama-open-1 TABLE_STRUCTURE_CORRUPT fix (v2.4.74, 2026-05-25):
    drop Camelot-emitted ``<table>`` blocks whose content is structurally
    page-content (journal masthead, paper title, next-section name), not
    real tabular data.

    Structural signature for a PHANTOM table — ALL must hold:
      1. ``<thead>`` exists AND ≥1 ``<th>`` cell matches a running-header /
         masthead pattern (JAMA Network Open, NEJM masthead, generic
         `<Journal> | <Section>` form).
      2. ``<tbody>`` has ≤1 row total, OR the only non-empty body cell is
         a single section-name token (Discussion / Conclusion / Methods).

    When both hold, the "table" is Camelot picking up a page-spanning row
    above or below the real table caption — false positive that bleeds the
    journal masthead into a `<th>` and the next section name into a `<td>`.
    Removed in place; the caption line (``*Table N. …*``) and the
    ``### Table N`` heading remain so the reader sees the caption and
    knows the table itself wasn't recoverable. This is intentionally
    LOSSY (we drop garbage HTML) — preferred to emitting structurally
    wrong table content per CLAUDE.md hard rule 0b (no hallucinated text).
    """
    if not text or "<table" not in text:
        return text
    # Process each <table>...</table> block independently.
    pattern = re.compile(r"<table\b[^>]*>.*?</table>\s*", re.DOTALL | re.IGNORECASE)

    def is_phantom(block: str) -> bool:
        # Extract <th> contents.
        th_cells = re.findall(r"<th[^>]*>(.*?)</th>", block, re.DOTALL | re.IGNORECASE)
        if not th_cells:
            return False
        th_text = " | ".join(c.strip() for c in th_cells)
        masthead_match = any(
            p.search(th_text) for p in _PHANTOM_TABLE_HEADER_PATTERNS
        )
        # 2026-05-25 (Cluster D-partial, ip_feldman finding #9):
        # ALSO treat tables whose <th> content is long-form body prose
        # (not a column-header noun phrase) as phantom.  Sage two-column
        # layouts where a body paragraph shares y-coordinates with the
        # actual table header line cause Camelot to absorb body words
        # into the <thead>.  Distinguishing signature: a <th> cell with
        # MANY words (≥8), containing function words ("and", "we",
        # "below", "those", "with", "against") AND verb-shape words
        # (ending in -ed / -ing / -ly).  Legitimate column headers are
        # short noun phrases ("β for negative", "Outcomes (Extension)")
        # without function-word + verb co-occurrence.  Three-channel
        # corroboration prevents legitimate-but-long headers from
        # tripping (e.g. multi-clause caption-like headers).
        _FUNCTION_WORDS_IN_PROSE = frozenset({
            "and", "or", "but", "we", "us", "our", "you", "they", "them",
            "their", "those", "these", "this", "that", "with", "without",
            "for", "from", "to", "in", "on", "at", "by", "as", "of",
            "below", "above", "before", "after", "against", "between",
            "yet", "however", "although", "though", "while", "because",
            "since", "if", "when", "where", "which", "who", "whom",
            "what", "have", "has", "had", "should", "would", "could",
            "may", "might", "must", "can", "will", "shall", "do", "does",
            "did", "is", "are", "was", "were", "be", "been", "being",
        })
        th_section_leak = False
        if not masthead_match:
            for th_cell in th_cells:
                cleaned_th = re.sub(r"<[^>]+>", "", th_cell)
                # Strip <br>-implied whitespace runs too.
                cleaned_th = re.sub(r"\s+", " ", cleaned_th).strip()
                # Drop trailing-hyphen artifacts from PDF line-wrap ("cau-tion")
                cleaned_th = cleaned_th.replace("- ", "")
                words = re.findall(r"\b[\w']+\b", cleaned_th.lower())
                if len(words) < 8:
                    continue
                fn_count = sum(1 for w in words if w in _FUNCTION_WORDS_IN_PROSE)
                verb_count = sum(
                    1 for w in words
                    if len(w) >= 4 and w[0].islower()
                    and (w.endswith("ed") or w.endswith("ing") or w.endswith("ly"))
                )
                # Body-prose signature: ≥3 function words AND ≥2 verb-shape words.
                # Backstop: the OLD heuristic (named section-token + verb-shape)
                # still works for cases where the section name is present.
                if fn_count >= 3 and verb_count >= 2:
                    th_section_leak = True
                    break
                word_set = set(words)
                if any(t.lower() in word_set for t in _PHANTOM_TABLE_BODY_LEAK_TOKENS):
                    if verb_count >= 1:
                        th_section_leak = True
                        break
        if not (masthead_match or th_section_leak):
            return False
        # Inspect tbody: count non-empty body cells, look for section-name leak.
        body_cells = re.findall(r"<td[^>]*>(.*?)</td>", block, re.DOTALL | re.IGNORECASE)
        non_empty = [c.strip() for c in body_cells if c.strip()]
        # 2026-05-25 (Cluster D-partial): when the <th> already shows
        # body-prose leak (th_section_leak=True), we have strong evidence
        # the entire table region is corrupted by Camelot absorbing
        # adjacent-column body text.  In that case, the `>3 body cells`
        # early-return below would still keep the table even though its
        # data is unreadable — drop unconditionally on th_section_leak.
        if th_section_leak:
            return True
        if len(non_empty) > 3:
            # Not a phantom — real table with content despite masthead-shaped header.
            return False
        # Either ≤1 body cell OR an obvious section-name leak.
        if not non_empty:
            return True
        for cell_text in non_empty:
            cleaned = re.sub(r"<[^>]+>", "", cell_text).strip()
            if cleaned in _PHANTOM_TABLE_BODY_LEAK_TOKENS:
                return True
        if len(non_empty) <= 1:
            return True
        return False

    def replacement(m):
        return "" if is_phantom(m.group(0)) else m.group(0)

    return pattern.sub(replacement, text)


_ABSTRACT_ZONE_END_HEADINGS = frozenset({
    "Introduction", "Background", "Methods", "Method", "Materials",
    "Materials and Methods", "Patients and Methods", "Subjects and Methods",
    "Participants and Procedure", "Participants", "Procedure",
    "Theoretical Development", "Theory", "Literature Review",
})

# Structured-abstract / Key Points inline labels that get wrongly promoted
# to ## headings when column-interleave drops them on their own lines.
# Title-cased + uppercase variants both included since promoters can produce
# either depending on the source casing. CONSERVATIVE allowlist — never
# demote a heading not in this exact set (avoids over-demoting legitimate
# body-section h2s like `## THEORETICAL DEVELOPMENT` per the 2026-05-25
# amj_1 regression).
_STRUCTURED_ABSTRACT_INLINE_LABELS = frozenset({
    # JAMA structured-abstract labels (uppercase per JAMA house style).
    "IMPORTANCE", "Importance",
    "OBJECTIVE", "Objective",
    "OBJECTIVES", "Objectives",
    "DESIGN, SETTING, AND PARTICIPANTS", "Design, Setting, and Participants",
    "INTERVENTIONS", "Interventions",
    "MAIN OUTCOMES AND MEASURES", "Main Outcomes and Measures",
    "RESULTS", "CONCLUSIONS", "CONCLUSIONS AND RELEVANCE",
    "Conclusions and Relevance",
    # Other structured-abstract conventions.
    "PURPOSE", "Purpose",
    "DESIGN", "Design",
    "FINDINGS",
    # JAMA Key Points sidebar trio.
    "Question", "Findings", "Meaning",
})


def _demote_abstract_zone_inline_labels(text: str) -> str:
    """jama-open-1 ABSTRACT_LEVEL_MISMATCH fix (v2.4.74, 2026-05-25):
    between ``## Abstract`` and the next genuine body-section h2 (e.g.
    ``## Introduction`` / ``## Methods``), demote ``## X`` headings whose
    text is in ``_STRUCTURED_ABSTRACT_INLINE_LABELS`` to inline bold
    ``**X**``. JAMA structured-abstract inline labels (`IMPORTANCE`,
    `RESULTS`, `CONCLUSIONS AND RELEVANCE`, `MAIN OUTCOMES AND MEASURES`)
    and Key Points sidebar labels (`Question`, `Findings`, `Meaning`) get
    promoted to h2 by upstream rules when column-interleave drops them on
    their own lines — this demoter undoes the misplaced promotions.

    Conservative: only demotes headings in the explicit allowlist, never
    a heading whose text is "any all-caps phrase". A real body-section h2
    like ``## THEORETICAL DEVELOPMENT`` (amj_1 fixture) is preserved.
    Belt-and-braces against R4 column-interleave's structural cause being
    unfixed yet.
    """
    if not text:
        return text
    lines = text.split("\n")
    n = len(lines)
    out: list[str] = []
    i = 0
    in_zone = False
    abstract_line_idx = -1
    # Hard cap: structured-abstract labels appear within ~80 lines of
    # `## Abstract` in every JAMA Open paper observed. Beyond that, ANY
    # `## RESULTS` is a body-section heading (e.g. `## III. RESULTS` in
    # ieee_access_2, where `## I. INTRODUCTION` doesn't match the
    # _ABSTRACT_ZONE_END_HEADINGS set because of the roman-numeral prefix
    # and so `in_zone` would otherwise stay True for the whole paper).
    ZONE_LINE_CAP = 80
    while i < n:
        line = lines[i]
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            heading = m.group(1).strip()
            if heading == "Abstract":
                in_zone = True
                abstract_line_idx = i
                out.append(line)
                i += 1
                continue
            if in_zone:
                if (i - abstract_line_idx) > ZONE_LINE_CAP:
                    in_zone = False
                elif heading in _ABSTRACT_ZONE_END_HEADINGS:
                    in_zone = False
                    out.append(line)
                    i += 1
                    continue
                if in_zone and heading in _STRUCTURED_ABSTRACT_INLINE_LABELS:
                    # Inside zone AND known inline label — demote to bold.
                    out.append(f"**{heading}**")
                    i += 1
                    continue
        out.append(line)
        i += 1
    return "\n".join(out)


def _looks_like_real_sentence(line: str) -> bool:
    """A line counts as a REAL SENTENCE for the demote-blocking test when
    it ends with `.`, `?`, or `!` AND has ≥4 words AND contains at least
    one lowercase token. Strict — table footnotes ("This table summarises
    the key findings.") are sentences; column labels like "Change from
    baseline, %" are not.
    """
    s = line.strip()
    if len(s) < 25:
        return False
    if not s.endswith((".", "?", "!")):
        return False
    if len(s.split()) < 4:
        return False
    if not re.search(r"\b[a-z]{3,}\b", s):
        return False
    return True


def _demote_isolated_table_cell_headings(text: str) -> str:
    """jama-open-1 HALLUC_HEAD fix (v2.4.74, 2026-05-25): demote a
    ``### {label}`` heading that was wrongly promoted from a table cell.

    Structural signature: the heading line is short (≤6 words, ≤60 chars,
    no sentence terminator) AND BOTH of its surrounding non-blank windows
    (3 lines each side, stopping at fences / blockquotes / other headings)
    contain ≥1 ``_is_table_cell_fragment``-shape line and ZERO
    ``_looks_like_real_sentence``-shape lines. That's the canonical
    table-cell-region signature — column-label fragments, single letters,
    short value labels, none of which are real sentences.

    Conservative — gated by the strict ``_looks_like_real_sentence`` test
    (must end with terminator + ≥4 words + lowercase token) rather than
    the loose ``_is_prose_line`` (which catches non-sentence labels like
    "Change from baseline, %" as "prose" because they contain a lowercase
    word). A real ``### Subsection`` heading is always immediately followed
    by real-sentence prose, so the bidirectional cluster gate makes
    false-positive demotion extremely unlikely. Skips ``### Table N`` /
    ``### Figure N`` (legitimate caption headings).

    Surfaced by the 2026-05-25 jama-open-1 cluster: `### 1.0. Mean glucose
    level`, `### Control`, `### Body weight, kg`, `### Total cholesterol`
    — all stranded inside Table 2 / Table 4 cell regions.
    """
    if not text:
        return text
    lines = text.split("\n")
    n = len(lines)
    out: list[str] = []
    i = 0
    while i < n:
        line = lines[i]
        m = re.match(r"^###\s+(.+?)\s*$", line)
        demoted = False
        if m:
            heading = m.group(1).strip()
            # Skip legitimate splice-anchor headings.
            if not (heading.startswith("Table ") or heading.startswith("Figure ")):
                # Heading itself must look like a table-cell fragment OR have
                # the data-shape signature (numeric prefix etc.).
                if _is_table_cell_fragment(heading):
                    # Walk backward up to 3 non-blank lines, stopping at fences.
                    prev_cell = 0
                    prev_sent = 0
                    prev_single_token_cells = 0  # column-header-row signal
                    k = i - 1
                    walked_back = 0
                    while k >= 0 and walked_back < 3:
                        s = lines[k].strip()
                        if not s:
                            k -= 1
                            continue
                        if s.startswith(("#", ">", "|", "`", "<")):
                            break
                        if _looks_like_real_sentence(s):
                            prev_sent += 1
                        elif _is_table_cell_fragment(s):
                            prev_cell += 1
                            # Single Title-Case word or single short acronym = column header.
                            if (_SINGLE_TITLECASE_TOKEN_RE.match(s)
                                or _SINGLE_ACRONYM_TOKEN_RE.match(s)):
                                prev_single_token_cells += 1
                        walked_back += 1
                        k -= 1
                    # Walk forward symmetrically.
                    next_cell = 0
                    next_sent = 0
                    next_single_token_cells = 0
                    k = i + 1
                    walked_fwd = 0
                    while k < n and walked_fwd < 3:
                        s = lines[k].strip()
                        if not s:
                            k += 1
                            continue
                        if s.startswith(("#", ">", "|", "`", "<")):
                            break
                        if _looks_like_real_sentence(s):
                            next_sent += 1
                        elif _is_table_cell_fragment(s):
                            next_cell += 1
                            if (_SINGLE_TITLECASE_TOKEN_RE.match(s)
                                or _SINGLE_ACRONYM_TOKEN_RE.match(s)):
                                next_single_token_cells += 1
                        walked_fwd += 1
                        k += 1
                    # Demotion rules — any of these is enough:
                    #   (a) bidirectional cell cluster with no real sentences anywhere.
                    #   (b) prev side has ≥2 single-token-cell signals (column-header
                    #       row signature) — unambiguous table-region stranding even
                    #       when the forward side has the table footer note prose.
                    #   (c) heading text itself carries an unambiguous data-cell
                    #       signature: data-unit comma-suffix (`, %` / `, kg` /
                    #       `, mg/dL`) or numeric-prefix-shape (`1.0. X`). These
                    #       shapes are STRUCTURALLY table-cell content (no real
                    #       section heading ends in `, kg`) — demote regardless
                    #       of surrounding context, as long as ≥1 cell-fragment
                    #       neighbour exists on either side (anchors it in a
                    #       table region rather than free body text).
                    #   (d) next non-blank line is a data-unit suffix cell label
                    #       (e.g. `Plasma lipid levels, mg/dL`). Heading is then
                    #       a row label whose value column follows.
                    bidirectional = (
                        prev_cell >= 1 and next_cell >= 1
                        and prev_sent == 0 and next_sent == 0
                    )
                    column_header_stranded = prev_single_token_cells >= 2
                    heading_is_data_shape = bool(
                        _DATA_UNIT_SUFFIX_RE.search(heading)
                        or _NUMERIC_PREFIX_RE.match(heading)
                    )
                    next_is_data_unit_label = False
                    k_nb = i + 1
                    while k_nb < n and not lines[k_nb].strip():
                        k_nb += 1
                    if k_nb < n:
                        next_is_data_unit_label = bool(
                            _DATA_UNIT_SUFFIX_RE.search(lines[k_nb].strip())
                        )
                    data_shape_with_anchor = heading_is_data_shape and (
                        prev_cell >= 1 or next_cell >= 1
                    )
                    next_label_with_anchor = next_is_data_unit_label and (
                        prev_cell >= 1 or prev_single_token_cells >= 1
                    )
                    if (bidirectional or column_header_stranded
                        or data_shape_with_anchor or next_label_with_anchor):
                        out.append(heading)
                        i += 1
                        demoted = True
        if not demoted:
            out.append(line)
            i += 1
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


# §C P0r-F (NORMALIZATION_VERSION 1.9.23 / v2.4.71, 2026-05-23): strip P0r-
# shape running-header / page-footer lines that survive INSIDE an
# ``unstructured-table`` fenced block. The body normalize-stage P0r runs
# before the table-fence assembly, so when Camelot is disabled (or returns
# no cells) and the table region falls back to raw_text, a footer line that
# pdftotext serialised inside the table region remains welded into that
# raw_text dump. Same 3-channel discipline as the glyph-recovery passes:
# body channel (normalize), table-cell channel (cell_cleaning), assembled
# fences (this pass). Shape-only — no repetition gate needed because the
# 5 P0r shape signatures are very specific to running headers/footers and
# ``unstructured-table`` block contents are cell tokens, never real prose.
_UNSTRUCTURED_TABLE_FENCE_OPEN = "```unstructured-table"
_FENCE_CLOSE = "```"


def _strip_running_header_lines_in_unstructured_table_fences(text: str) -> str:
    """Drop P0r-shape running-header / page-footer lines that survived inside
    ``unstructured-table`` fenced blocks (Camelot-disabled / cells-not-recovered
    fallback path). Shape-gated only — the 5 P0r signatures are specific
    enough that any line matching one inside such a fence is a footer."""
    if _UNSTRUCTURED_TABLE_FENCE_OPEN not in text:
        return text
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    for line in lines:
        if not in_fence:
            out.append(line)
            if line.startswith(_UNSTRUCTURED_TABLE_FENCE_OPEN):
                in_fence = True
            continue
        # Inside fence:
        if line.startswith(_FENCE_CLOSE):
            in_fence = False
            out.append(line)
            continue
        if _looks_like_running_header_or_footer(line.strip()):
            continue  # drop the footer line
        out.append(line)
    cleaned = "\n".join(out)
    # Collapse double-blank runs left by the removal.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# FIG-3c (v2.4.51): a body line that begins a figure-caption run inline.
# pdftotext linearizes a figure's caption into the running text column, so
# the caption appears once inline in body prose and once as the spliced
# ``### Figure N`` block — a double-emission.
_INLINE_FIG_CAPTION_LABEL_RE = re.compile(r"^(?:Figure|FIGURE|Fig\.)\s+\d+\b")

# 2026-05-25 (Cluster B, ip_feldman findings #4 + #5): parallel of the
# figure caption-suppressor.  Pdftotext linearises a table caption into
# the body text column the same way it linearises a figure caption; the
# figure helper has existed since 2026-05-12, but the table form was
# never written.  Result: italic `*Table N. <caption>.*` lines appear
# duplicated in body prose AND as the in-block caption above the rendered
# `<table>`.  This pass keeps the in-block caption and drops the
# orphaned body-text duplicates.  Also suppresses body-text duplicates
# of TABLE-CELL content that surfaces as paragraph-isolated short labels
# in between the inline caption and the next prose paragraph (e.g.
# "Exploratory open-ended" — finding #4 — which is a cell of Table 4
# that pdftotext serialised in body order).
_INLINE_TABLE_CAPTION_LABEL_RE = re.compile(r"^(?:Table|TABLE|Tab\.)\s+\d+\b")
_ITALIC_TABLE_CAPTION_RE = re.compile(r"^\*(Table\s+(\d+)[\.\:].+?)\*\s*$")


def _suppress_inline_duplicate_table_captions(text: str) -> str:
    """Drop italic `*Table N. <caption>.*` lines that pdftotext also left
    inline in body prose, when the table already has a dedicated
    ``### Table N`` block with the same caption.

    Parallel of ``_suppress_inline_duplicate_figure_captions``.  Same root
    cause (pdftotext linearises captions into running text), same safe-
    subset semantics (drop only when the inline duplicate is OUTSIDE the
    `### Table N` block zone and its caption exactly matches the in-block
    caption — case-insensitive, whitespace-normalised).

    Also drops the trailing body-text block (up to next blank+structural
    boundary) that pdftotext linearises after the inline caption — those
    are duplicate table-cell content that no longer belong in body once
    the HTML block is rendered (covers finding #4 "Exploratory open-ended"
    which is a Table 4 cell label, not a real subsection).
    """
    if not text or "Table " not in text:
        return text
    lines = text.split("\n")
    n = len(lines)
    # 1. Collect "### Table N" block headings + their accompanying italic
    # captions.  Heading-line index → (block caption text, heading line index).
    block_info: dict[int, tuple[str, int]] = {}
    for i, ln in enumerate(lines):
        m = re.match(r"^#{2,4}\s+Table\s+(\d+)\s*$", ln)
        if not m:
            continue
        num = int(m.group(1))
        # Italic caption within next 5 lines.
        for j in range(i + 1, min(i + 5, n)):
            cm = _ITALIC_TABLE_CAPTION_RE.match(lines[j].strip())
            if cm:
                cap_norm = re.sub(r"\s+", " ", cm.group(1)).strip()
                block_info[num] = (cap_norm, i)
                break
    if not block_info:
        return text
    # 2. Walk body lines; drop inline matches that aren't the in-block caption.
    drop: set[int] = set()
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        cm = _ITALIC_TABLE_CAPTION_RE.match(s)
        if not cm:
            continue
        num = int(cm.group(2))
        info = block_info.get(num)
        if not info:
            continue
        block_caption, heading_idx = info
        # Skip if this IS the in-block caption (within 5 lines of the heading).
        if abs(i - heading_idx) <= 5:
            continue
        candidate = re.sub(r"\s+", " ", cm.group(1)).strip()
        if candidate.lower() != block_caption.lower():
            continue
        # Drop this inline caption + tighten surrounding blank lines.
        drop.add(i)
        if i > 0 and not lines[i - 1].strip():
            drop.add(i - 1)
        # Walk forward through any body-text run that is short, cell-shaped
        # content (Table N body data that pdftotext linearised after the
        # caption).  Stop at the first long prose sentence, structural
        # marker, or second blank line.  This is what kills finding #4
        # ("Exploratory open-ended") which sits as one of these cell
        # fragments between the inline caption and the next real
        # paragraph.  Conservative: cap at 12 lines, stop on `.`-terminated
        # multi-word prose.
        j = i + 1
        blank_run = 0
        cell_lines_consumed: list[int] = []
        while j < n and j - i < 12:
            sj = lines[j].strip()
            if not sj:
                blank_run += 1
                if blank_run > 1:
                    break
                j += 1
                continue
            blank_run = 0
            if sj.startswith(("#", "*", "<", "|", "`", ">")):
                break
            # Real prose: ≥ 80 chars and ends with sentence terminator → stop.
            if len(sj) >= 80 and sj[-1] in ".!?":
                break
            # Otherwise treat as cell-shaped continuation.
            cell_lines_consumed.append(j)
            j += 1
        # Only drop the cell run if it's clearly cell content (each line short
        # AND none ends in a body-prose-sentence terminator with > 80 chars).
        if cell_lines_consumed:
            drop.update(cell_lines_consumed)
        # Drop trailing blank line.
        if j < n and not lines[j].strip():
            drop.add(j)
    if not drop:
        return text
    return "\n".join(ln for i, ln in enumerate(lines) if i not in drop)


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
                # FIG-3c-2 (§A R3b, 2026-05-23): inverse safe-superset.
                # When the inline run STARTS with the block caption's full
                # text (block_cap is a prefix of inline acc_norm, ≥30 chars
                # matched), AND the overhang is clearly caption-continuation
                # (NOT body content), drop the inline. Critical text-loss
                # guard (CLAUDE.md hard rule 0a): if the overhang carries
                # ANY statistic shape (F(.), t(.), χ², p = , p <, B = , d =,
                # OR =, β =, R² =), it's body content (an F-statistic
                # sentence following the caption period), not extra caption
                # text — must KEEP. Conservative thresholds: overhang ≤120
                # chars + sentence-terminated + no stat shape.
                if (
                    len(bc) >= 30
                    and acc_norm.lower().startswith(bc.lower())
                ):
                    overhang = acc_norm[len(bc):].strip()
                    has_stat_shape = bool(re.search(
                        r"\b(?:F|t|d|B|β|χ²|χ2|η²|η2|R²|R2|OR|RR|HR|Z|Q)\s*[=(]"
                        r"|\bp\s*[=<>]"
                        r"|\b\d+\s*,\s*\d+\)\s*=\s*\d",
                        overhang,
                    ))
                    # Body-prose signature: first-person / sentence-starter
                    # words at the START of the overhang. If the overhang
                    # starts with "We ", "In ", "Although ", "However ", etc.,
                    # it's body text after the caption sentence ended.
                    body_prose_start = bool(re.match(
                        r"^(?:We\s|Our\s|This\s+study|In\s+(?:this|the|sum|summary|particular|addition|contrast)|"
                        r"Although\s|However\s|Therefore\s|Thus\s|Importantly\s|Notably\s|"
                        r"Specifically\s|First\s*,|Second\s*,|Third\s*,|Furthermore\s|"
                        r"Moreover\s|Additionally\s|Finally\s|Consequently\s|"
                        r"As\s+(?:we|expected|predicted|shown|noted)\s)",
                        overhang,
                    ))
                    if (
                        not has_stat_shape
                        and not body_prose_start
                        and 0 < len(overhang) <= 120
                        and overhang[-1] in ".?!"
                    ):
                        drop.update(run)
                        i = j
                        continue
                    # R3b wider form (v2.4.74, 2026-05-25): allow up to 250
                    # chars overhang when the overhang is clearly caption-
                    # continuation shape. Stricter than the ≤120 path —
                    # the overhang must additionally start with a lowercase
                    # word (caption continuation typical: "showing the …")
                    # OR a parenthesis-bracketed phrase ("(A) … (B) …" —
                    # multi-panel figure caption pattern). And must end
                    # with a sentence terminator. No stat shape, no body-
                    # prose starter.
                    overhang_extension_shape = bool(
                        re.match(r"^[a-z]", overhang)
                        or re.match(r"^\(\w\)", overhang)
                        or re.match(r"^[A-Z]\.\s+[A-Z]", overhang)  # panel labels
                    )
                    if (
                        not has_stat_shape
                        and not body_prose_start
                        and overhang_extension_shape
                        and 120 < len(overhang) <= 250
                        and overhang[-1] in ".?!"
                    ):
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
    sectioned,
    tables: list[dict],
    figures: list[dict],
    *,
    flatten_tables_inline: bool = False,
    docpluck_version: Optional[str] = None,
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
                completeness_marker = _table_completeness_marker(cells, raw_t)
                if html:
                    body_chunks.append(f"\n### {label}\n")
                    if completeness_marker:
                        body_chunks.append(completeness_marker)
                    if cap:
                        body_chunks.append(f"*{cap}*\n")
                    body_chunks.append(html)
                    # EC-T1: optional human-readable flattened block below the
                    # <table>. Same records that go into the .tables.jsonl
                    # sidecar — single source of truth, no drift risk.
                    if flatten_tables_inline:
                        records = flatten_table(item)
                        if records:
                            body_chunks.append(
                                "\n"
                                + render_flattened_inline(
                                    records,
                                    table_id=str(item.get("id") or label),
                                    label=label,
                                    version=docpluck_version,
                                )
                            )
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
                    if completeness_marker:
                        body_chunks.append(completeness_marker)
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
                    # v2.4.55: Camelot returned no cells AND there is no
                    # raw_text fallback — an isolated table detected only by
                    # its caption. v2.4.2 emitted just the italic caption with
                    # NO `### Table N` heading, reasoning a bare heading
                    # "falsely promises structured content". But that drops
                    # the table from every structural view: a reader scanning
                    # `### Table` headings and the harness Tier-D
                    # `table_parity` check (### Table heading count must match
                    # tables.json count) both lose it. Emit the heading +
                    # caption so the table is visible AS a table — consistent
                    # with the appendix leftover-table path below, which
                    # already emits `### {label}` for a caption-only table.
                    # The `*{cap}*` italic line is kept immediately after the
                    # heading so `_suppress_orphan_table_cell_text` still
                    # recognizes it and drops any linearized orphan cell-rows.
                    body_chunks.append(f"\n### {label}\n")
                    if completeness_marker:
                        body_chunks.append(completeness_marker)
                    body_chunks.append(f"*{cap}*\n")
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
                completeness_marker = _table_completeness_marker(cells, raw_t)
                out_chunks.append(f"### {label}\n")
                if completeness_marker:
                    out_chunks.append(completeness_marker)
                if cap:
                    out_chunks.append(f"*{cap}*\n")
                if html:
                    out_chunks.append(html + "\n")
                    if flatten_tables_inline:
                        records = flatten_table(t)
                        if records:
                            out_chunks.append(
                                render_flattened_inline(
                                    records,
                                    table_id=str(t.get("id") or label),
                                    label=label,
                                    version=docpluck_version,
                                )
                                + "\n"
                            )
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


# ── v2.4.83: de-dup the table/figure label between heading and caption ──────
#
# Every table/figure block is emitted as ``### Table N`` immediately followed
# by an italic ``*Table N. <desc>*`` caption (see _render_sections_to_markdown
# body + appendix paths). The label number is therefore printed twice — once
# as the heading, once at the head of the caption ("### Table 1" then
# "*Table 1. …*"). Strip the redundant ``Table N.`` / ``Figure N.`` prefix from
# the caption line when an immediately-preceding ``### Table N`` / ``### Figure
# N`` heading already carries the same number.
#
# Runs LAST in the pipeline, AFTER the caption-detecting passes that key on the
# ``Table N.`` prefix (``_suppress_inline_duplicate_table_captions``,
# ``_suppress_orphan_table_cell_text``) — so it never disturbs their matching.
# The structured ``caption`` field from extract_pdf_structured is unchanged
# (verbatim printed caption); only the rendered markdown is de-duplicated.
_DEDUPE_HEADING_LABEL_RE = re.compile(r"^#{2,4}\s+(Table|Figure)\s+(\d+(?:\.\d+)?)\s*$")
_DEDUPE_ITALIC_CAPTION_RE = re.compile(
    r"^(?P<indent>\s*)\*(?P<kind>Table|Figure)\s+(?P<num>\d+(?:\.\d+)?)\.\s+(?P<desc>.+?)\*\s*$"
)


def _dedupe_label_in_table_figure_caption(text: str) -> str:
    """Strip a redundant ``Table N.`` / ``Figure N.`` prefix from an italic
    caption that immediately follows a matching ``### Table N`` / ``### Figure
    N`` heading (the heading already shows the number).

    Conservative: fires only when the heading and the caption carry the SAME
    kind+number, the caption has a non-empty description after the label, and
    the caption is the first non-blank, non-comment line under the heading.
    Idempotent — a caption already stripped of its label no longer matches.
    """
    if not text or ("Table " not in text and "Figure " not in text):
        return text
    lines = text.split("\n")
    n = len(lines)
    for i, ln in enumerate(lines):
        hm = _DEDUPE_HEADING_LABEL_RE.match(ln)
        if not hm:
            continue
        kind, num = hm.group(1), hm.group(2)
        # Inspect the first non-blank, non-comment line after the heading.
        for j in range(i + 1, min(i + 5, n)):
            s = lines[j].strip()
            if not s or s.startswith("<!--"):
                continue
            cm = _DEDUPE_ITALIC_CAPTION_RE.match(lines[j])
            if cm and cm.group("kind") == kind and cm.group("num") == num:
                desc = cm.group("desc").strip()
                if desc:
                    lines[j] = f"{cm.group('indent')}*{desc}*"
            break  # only the first content line under the heading is the caption
    return "\n".join(lines)


# ── Public entry point ─────────────────────────────────────────────────────


def render_pdf_to_markdown(
    pdf_bytes: bytes,
    *,
    normalization_level: NormalizationLevel = NormalizationLevel.standard,
    flatten_tables_inline: bool = False,
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
        flatten_tables_inline: When True, emit a human-readable
            ``### {label} — rendered as text`` block immediately after each
            ``<table>``, with one bullet per body row carrying the labelled
            sentence (e.g. ``Importance: t(741) = 3.93, p < .001, d = 0.29``).
            Bounded by HTML-comment sentinels
            ``<!-- docpluck:flattened-table id="…" start --> … end -->``.
            Default False keeps the .md output unchanged from prior versions.
            Callers who want the structured records as a JSONL sidecar should
            instead call :func:`docpluck.flatten_tables_for_paper` on
            ``structured["tables"]`` from ``extract_pdf_structured`` — that
            function is the canonical source, and the inline block here is
            *derived from* the same records (so the two outputs cannot drift).
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
    # 0. Pre-extract layout doc once (v2.4.74 R1-perf). Used downstream by
    #    BOTH extract_pdf_structured (§A R1 whitespace_cells fallback) AND
    #    the title-rescue step at line ~3335. Sharing eliminates the duplicate
    #    pdfplumber pass that the R1 AI-gold sweep flagged as 2x cost on
    #    every render path with unmatched captions. extract_pdf_structured's
    #    `_layout_doc` parameter is None-tolerant — falls back to its own
    #    extraction if the shared doc isn't available, preserving the existing
    #    caller contract.
    if _layout_doc is not None:
        layout_doc = _layout_doc
    else:
        try:
            from .extract_layout import extract_pdf_layout
            layout_doc = extract_pdf_layout(pdf_bytes)
        except Exception:
            layout_doc = None

    # 1. Structured extraction (text + Camelot tables + figures).
    if _structured is not None:
        structured = _structured
    else:
        structured = extract_pdf_structured(pdf_bytes, _layout_doc=layout_doc)
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
    from . import __version__ as _dp_ver
    md = _render_sections_to_markdown(
        sectioned,
        structured["tables"],
        structured["figures"],
        flatten_tables_inline=flatten_tables_inline,
        docpluck_version=_dp_ver,
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
    # B2b (2026-05-22): demote orphan generic-label `##` headings that the
    # partitioner promoted from a front-matter sidebar or appendix marker
    # (``## Conclusion`` / ``## Evaluation`` / ``## Findings`` /
    # ``## Implications`` / ``## Limitations`` with no body prose after).
    md = _demote_orphan_generic_headings(md)
    # HALLUC-HEAD-2 / G5d-2 (2026-05-23 cycle 3): demote ``## <Title>`` that
    # the partitioner over-promoted from the second half of a soft-wrap-split
    # sentence. Fires when the IMMEDIATELY-PRIOR non-empty line ends in a
    # continuation word (the, in, of, and, …) AND has no sentence terminator.
    # Specific defect: ip_feldman_2025_pspb cycle-2 line 409
    # ``## Supplemental Materials`` promoted from "summarized in the\n
    # Supplemental Materials".
    md = _demote_continuation_promoted_headings(md)
    # §B-new-2 (2026-05-23) HALLUC-HEAD-3: demote ``## KEYWORDS`` and other
    # all-caps single-token metadata labels when followed by metadata-shape
    # content (separator-bearing list with no sentence verb).
    md = _demote_metadata_label_headings(md)
    # §B-new-4 (2026-05-23): demote ``## <Heading>`` that was wrongly split
    # off a comma-broken italic metadata label (``*Data Availability,
    # Preregistration, and Open-Science Disclosures.*``).
    md = _demote_italic_label_with_comma_headings(md)
    # B2c (2026-05-22): promote isolated bare method-subsection labels
    # (``Participants`` / ``Materials`` / ``Procedure`` / ``Measures`` /
    # ``Stimuli`` / ``Design`` / ``Apparatus`` / ``Analysis``) sitting on
    # their own line with paragraph isolation, after the demote passes
    # have settled the major heading layout.
    md = _promote_isolated_method_subsection_headings(md)
    # §B-new-1 (2026-05-23): wider analogue — promote any paragraph-isolated
    # Title-Case short line (≤6 words, ≤60 chars) followed by prose, gated
    # by strict shape checks. Runs AFTER B2c so the narrow set still wins.
    md = _promote_isolated_titlecase_subsection_headings(md)
    # 2026-06-06 (Cycle 4 redux): repair column-wrapped subsection-heading
    # titles carrying a citation — Rule A promotes a body `{Title} et al.`
    # + bare `(YYYY)` wrap to `### {Title} et al. (YYYY)` (finding #3);
    # Rule B reattaches a short colon-/paren-led orphan tail onto an
    # existing heading that was split mid-title (finding #4). Runs AFTER
    # the titlecase promoter so Rule B sees the partially-promoted `###`.
    md = _repair_column_wrapped_headings(md)
    # v2.4.74 (jama-open-1 HALLUC_HEAD fix): demote ### headings that the
    # promoters just stranded inside table-cell-region clusters. Runs AFTER
    # all promoters so it sees the final ### state and can target promotions
    # that landed in cell-cluster contexts.
    md = _demote_isolated_table_cell_headings(md)
    # v2.4.74 (jama-open-1 ABSTRACT_LEVEL_MISMATCH fix): demote misplaced
    # ## headings between ## Abstract and the next body-section h2. JAMA-
    # style structured-abstract inline labels (IMPORTANCE / OBJECTIVE /
    # RESULTS / CONCLUSIONS AND RELEVANCE) and Key Points sidebar labels
    # (Question / Findings / Meaning) get wrongly promoted by upstream
    # promoters when column-interleave drops them onto their own lines.
    # Belt-and-braces until R4 column-aware re-extraction lands.
    md = _demote_abstract_zone_inline_labels(md)
    # v2.4.74 (jama-open-1 TABLE_STRUCTURE_CORRUPT fix): strip Camelot
    # phantom tables whose <th> cells carry running-header/masthead text
    # and whose body is essentially empty or a single section-name leak
    # (Discussion / Conclusion / Methods).
    md = _strip_phantom_camelot_tables(md)
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
    # §A R5 / B7 (2026-05-23): recover DROPPED minus glyphs (pdftotext emits
    # no glyph for U+2212 on certain fonts). Same 3-channel discipline as
    # W0d above — body normalize covers body text; this final pass catches
    # the table-cell / unstructured-table / raw_text fallback surfaces.
    md = recover_dropped_minus_via_ci_pairing(md)
    # v2.4.44: final guarantee — decompose Latin typographic ligatures
    # (ﬁ->fi, ﬂ->fl, …) from the assembled markdown. normalize (body) and
    # cell_cleaning (table cells) cover their channels; this catches the
    # remaining surfaces — figure/table captions, unstructured-table fences,
    # raw_text fallbacks — so no presentation-form ligature reaches the .md.
    md = decompose_ligatures(md)
    # v2.4.54: final guarantee — recover Adobe-Symbol-font glyphs surfaced as
    # U+F0xx PUA codepoints (β→U+F062, χ→U+F063, •→U+F0B7). W0e (body channel)
    # and cell_cleaning (Camelot table cells) cover their channels; this
    # catches the remaining surfaces — figure/table captions, unstructured-
    # table fences, raw_text fallbacks — so no Symbol-PUA glyph reaches the .md
    # from ANY channel. Runs with the other glyph passes, before the caption
    # de-dup that compares spans for equality (FIG-3c lesson).
    md = recover_pua_glyphs(md)
    # FIG-3c: drop a figure caption pdftotext also left inline in the body
    # text, when a ``### Figure N`` block already carries it (double-emission).
    # Runs AFTER every glyph-normalization pass (destyle / minus-recovery /
    # ligature decomposition) so the inline body line and the figure block's
    # caption are compared in the SAME final glyph form — a stray ligature in
    # the block caption (``reﬂection`` vs body ``reflection``) would otherwise
    # defeat the equality check.
    md = _suppress_inline_duplicate_figure_captions(md)
    # 2026-05-25 (Cluster B): parallel for tables — drop body-text duplicate
    # of `*Table N. <caption>.*` when the `### Table N` block already carries
    # it.  Same root cause as figure variant (pdftotext linearises captions
    # into body text); without this pass, ip_feldman shows the Table 3
    # caption twice in body prose plus a third time inside its real block.
    md = _suppress_inline_duplicate_table_captions(md)
    # §C P0r-F (2026-05-23): strip P0r-shape running-header / page-footer
    # lines that survived inside ``unstructured-table`` fenced blocks
    # (third-channel completion of the body normalize-stage P0r).
    md = _strip_running_header_lines_in_unstructured_table_fences(md)
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

    # 5. Title rescue — uses the layout_doc computed once at step 0 (v2.4.74).
    md = _rescue_title_from_layout(md, layout_doc)
    # 2026-06-06 (Cycle 4 redux, Cluster E side-effect protection): strip
    # the `### {prefix-of-H1}` + continuation block that pdftotext column-
    # wraps emit on PSPB/Sage layouts. MUST run AFTER `_rescue_title_from_
    # layout` because the H1 it inserts is the anchor for the token-prefix
    # match. Requires ≥75% H1-token-coverage to fire — false-positives
    # architecturally impossible because legitimate subsection headings
    # under a `## ` parent (e.g. `### Background`) are not located ≤2 blank
    # lines below the H1 and don't reproduce the H1's token sequence as an
    # ordered prefix.
    md = _demote_wrapped_title_duplicate(md)
    # 2026-06-06 (Cycle 4 redux step 2): strip the residual publisher
    # masthead block (author+superscript, journal-name wraps, page range,
    # copyright tail, DOI: label, bare DOI) between the H1 and the first
    # `## ` body-section heading. Runs AFTER the wrapped-title demoter so
    # the zone no longer contains a `### `-duplicate that would otherwise
    # terminate the zone early. Self-limiting >=2-hard-marker gate.
    md = _strip_frontmatter_masthead_block(md)
    # 2026-06-06 (run-11, ar_apa `### FlashReport`): strip heading markup
    # that sits ABOVE the document H1 — a journal-section label promoted to
    # a heading in the pre-title masthead zone. Runs after title rescue (H1
    # is the anchor).
    md = _strip_pre_title_heading_noise(md)
    md = _italicize_known_subtitle_badges(md)
    # v2.4.83: runs LAST — strip the redundant ``Table N.`` / ``Figure N.``
    # label from a caption that sits directly under its ``### Table N`` heading.
    # Must follow the caption-detecting passes above that key on the prefix.
    md = _dedupe_label_in_table_figure_caption(md)

    return md.rstrip() + "\n"
