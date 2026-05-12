"""Corpus verifier: run v2.3.0 render against the spike's 26-paper corpus.

For each paper:
  - Locate the PDF in PDFextractor/test-pdfs/
  - Run docpluck.render_pdf_to_markdown
  - Compute health metrics on the output
  - Compare against the spike's known-good baseline in
    docs/superpowers/plans/spot-checks/splice-spike/outputs[-new]/
  - Print a per-paper PASS/WARN/FAIL line and a summary

Metrics computed per paper:
  - Title rescue: present? truncated (ends in connector)?
  - Section count
  - Table count (and how many have non-empty html)
  - Figure count (and longest caption length — detects Bug 4 leak)
  - Char-ratio vs spike baseline (out_len / spike_len)
  - Word-set Jaccard similarity to spike baseline (cheap content check)

Failure tags emitted (single-letter, easy to grep):
  T  = title truncated
  S  = section count < expected
  H  = table missing html
  C  = caption > 800 chars (boundary leak)
  L  = output much shorter than baseline (<70%)
  J  = Jaccard < 0.6 (very different content)

Usage:
  python scripts/verify_corpus.py
  python scripts/verify_corpus.py --paper chen_2021_jesp
  python scripts/verify_corpus.py --diff chen_2021_jesp   # dump rendered to /tmp
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
APP_PDFS = REPO_ROOT.parent / "PDFextractor" / "test-pdfs"
SPIKE_OUT_DIRS = [
    REPO_ROOT / "docs/superpowers/plans/spot-checks/splice-spike/outputs",
    REPO_ROOT / "docs/superpowers/plans/spot-checks/splice-spike/outputs-new",
]


# Set of connector words copy-pasted from docpluck.render._TITLE_CONNECTOR_TAIL_WORDS.
# Kept in sync via test; recomputing here keeps the verifier dependency-free.
_CONNECTOR_TAIL = {
    "of", "from", "for", "the", "and", "or", "to", "with", "on", "at",
    "by", "in", "as", "is", "a", "an", "but", "into", "onto", "upon",
    "than", "that", "which", "who", "when", "where", "while", "during",
    "after", "before", "because", "since", "though", "although",
}


def _find_pdf(name: str) -> Optional[Path]:
    """Locate <name>.pdf under APP_PDFS (any subdir)."""
    for p in APP_PDFS.rglob(f"{name}.pdf"):
        return p
    return None


def _find_spike_md(name: str) -> Optional[Path]:
    for d in SPIKE_OUT_DIRS:
        p = d / f"{name}.md"
        if p.exists():
            return p
    return None


def _list_spike_papers() -> list[str]:
    names: set[str] = set()
    for d in SPIKE_OUT_DIRS:
        if not d.exists():
            continue
        for p in d.glob("*.md"):
            names.add(p.stem)
    return sorted(names)


def _word_set(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z]{4,}", text.lower()))


_TITLE_RE = re.compile(r"^\s*#\s+([^\n]+)$", re.MULTILINE)
_H2_RE = re.compile(r"^\s*##\s+([^\n]+)$", re.MULTILINE)
_H3_RE = re.compile(r"^\s*###\s+([^\n]+)$", re.MULTILINE)
_TABLE_HTML_RE = re.compile(r"<table>")
_FIG_CAPTION_RE = re.compile(
    # Real caption lines rendered by render.py look like:
    #     *Figure N. Some sentence ending with .*
    # Italic markers wrap the whole line. Body references like "Figure 2b
    # shows ..." don't have the leading *, so they don't match.
    r"^\*Figure\s+\d+\.?\s+[^\n]*?\*\s*$",
    re.MULTILINE,
)


def _metrics(md: str) -> dict:
    """Compute health metrics on a rendered .md string."""
    title_m = _TITLE_RE.search(md)
    title = title_m.group(1).strip() if title_m else None
    title_truncated = False
    if title:
        stripped = re.sub(r"[\s\.,;:!?\-—–]+$", "", title).lower()
        last = stripped.rsplit(None, 1)[-1] if " " in stripped else stripped
        title_truncated = last in _CONNECTOR_TAIL

    sections = _H2_RE.findall(md)
    subsections = _H3_RE.findall(md)
    table_html_blocks = _TABLE_HTML_RE.findall(md)
    # Caption length: longest "Figure N." caption stretch on a single line
    longest_fig_caption = 0
    for m in _FIG_CAPTION_RE.finditer(md):
        caption_text = m.group(0)
        if len(caption_text) > longest_fig_caption:
            longest_fig_caption = len(caption_text)

    return {
        "title": title,
        "title_truncated": title_truncated,
        "section_count": len(sections),
        "section_names": sections,
        "subsection_count": len(subsections),
        "table_html_count": len(table_html_blocks),
        "longest_fig_caption_chars": longest_fig_caption,
        "total_chars": len(md),
        "total_words": len(re.findall(r"\b[A-Za-z]+\b", md)),
    }


def _classify(name: str, md: str, spike_md: Optional[str]) -> tuple[str, dict, list[str]]:
    """Return (status, metrics, tags). Status: PASS|WARN|FAIL."""
    m = _metrics(md)
    tags: list[str] = []

    if m["title_truncated"]:
        tags.append("T")
    if m["section_count"] < 4:
        tags.append("S")
    # Tables: ``### Table N`` headings that appear BEFORE the "Tables
    # (unlocated in body)" appendix should have HTML. Headings inside the
    # appendix are explicitly known-isolated (Camelot couldn't extract
    # cells); those aren't render bugs, just inherent extraction limits.
    appendix_idx = md.find("## Tables (unlocated in body)")
    body_section = md if appendix_idx < 0 else md[:appendix_idx]
    body_table_heading_count = len(re.findall(r"^\s*###\s+Table\s+\d+", body_section, re.MULTILINE | re.IGNORECASE))
    table_heading_count = len(re.findall(r"^\s*###\s+Table\s+\d+", md, re.MULTILINE | re.IGNORECASE))
    if body_table_heading_count > 0 and m["table_html_count"] == 0:
        tags.append("H")
    if m["longest_fig_caption_chars"] > 800:
        tags.append("C")

    char_ratio = None
    jaccard = None
    if spike_md:
        char_ratio = m["total_chars"] / max(1, len(spike_md))
        my_words = _word_set(md)
        spike_words = _word_set(spike_md)
        union = my_words | spike_words
        if union:
            jaccard = len(my_words & spike_words) / len(union)
        if char_ratio < 0.7:
            tags.append("L")
        if jaccard is not None and jaccard < 0.6:
            tags.append("J")

    m["char_ratio_vs_spike"] = char_ratio
    m["jaccard_vs_spike"] = jaccard
    m["table_heading_count"] = table_heading_count

    if not tags:
        status = "PASS"
    elif set(tags) <= {"L"}:
        status = "WARN"
    else:
        status = "FAIL"
    return status, m, tags


def _run_render(pdf_path: Path) -> tuple[str, float]:
    """Run docpluck.render_pdf_to_markdown on a PDF path. Returns (md, seconds)."""
    from docpluck import render_pdf_to_markdown
    t0 = time.time()
    data = pdf_path.read_bytes()
    md = render_pdf_to_markdown(data)
    return md, time.time() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", help="run only this paper (basename without .pdf)")
    ap.add_argument("--diff", action="store_true",
                    help="dump rendered output for the named paper to tmp/")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    papers = [args.paper] if args.paper else _list_spike_papers()
    if not papers:
        print("ERROR: no spike baselines found", file=sys.stderr)
        return 1

    print(f"# Corpus verification — {len(papers)} papers")
    print(f"# legend: T=title_truncated S=few_sections H=missing_html C=caption_too_long L=much_shorter J=low_jaccard")
    print()
    print(f"{'STATUS':6} {'PAPER':40} {'TAGS':12} {'CHARS':>8} {'SECT':>5} {'TABS':>5} {'CAP':>6} {'RATIO':>6} {'JACC':>6}  TIME")
    print("-" * 110)

    summary = {"PASS": 0, "WARN": 0, "FAIL": 0, "NO_PDF": 0, "ERROR": 0}
    failures_by_tag: dict[str, list[str]] = {}

    for name in papers:
        pdf = _find_pdf(name)
        if pdf is None:
            print(f"{'NO_PDF':6} {name:40}")
            summary["NO_PDF"] += 1
            continue
        spike_md_path = _find_spike_md(name)
        spike_md = spike_md_path.read_text(encoding="utf-8", errors="ignore") if spike_md_path else None
        try:
            md, elapsed = _run_render(pdf)
        except Exception as e:
            print(f"{'ERROR':6} {name:40}  {type(e).__name__}: {e}")
            summary["ERROR"] += 1
            continue
        status, m, tags = _classify(name, md, spike_md)
        summary[status] += 1
        for t in tags:
            failures_by_tag.setdefault(t, []).append(name)

        tag_str = ",".join(tags) or "—"
        ratio_str = f"{m['char_ratio_vs_spike']:.2f}" if m['char_ratio_vs_spike'] else "—"
        jacc_str = f"{m['jaccard_vs_spike']:.2f}" if m['jaccard_vs_spike'] is not None else "—"
        print(f"{status:6} {name:40} {tag_str:12} {m['total_chars']:>8} {m['section_count']:>5} {m['table_html_count']:>5} {m['longest_fig_caption_chars']:>6} {ratio_str:>6} {jacc_str:>6}  {elapsed:.1f}s")

        if args.diff:
            out_dir = REPO_ROOT / "tmp"
            out_dir.mkdir(exist_ok=True)
            (out_dir / f"{name}.rendered.md").write_text(md, encoding="utf-8")
            print(f"  → dumped to tmp/{name}.rendered.md")

    print()
    print("# Summary")
    total = sum(summary.values())
    for k in ("PASS", "WARN", "FAIL", "NO_PDF", "ERROR"):
        if summary[k]:
            print(f"  {k:8} {summary[k]:3} / {total}")
    if failures_by_tag:
        print()
        print("# Failures by tag")
        for tag, names in sorted(failures_by_tag.items()):
            print(f"  {tag}: {len(names):2}  {', '.join(names[:6])}{'...' if len(names) > 6 else ''}")

    return 0 if summary["FAIL"] == 0 and summary["ERROR"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
