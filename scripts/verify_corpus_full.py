"""Full-corpus verifier: run v2.4.0 render across all 101 PDFs in
PDFextractor/test-pdfs/ and flag papers with structural issues, even those
without a spike baseline.

For papers WITH a spike baseline, full metrics (char-ratio, Jaccard, D-tag)
apply just like in verify_corpus.py.

For papers WITHOUT a spike baseline (75 of the 101), we apply baseline-free
heuristics:
  - title present? non-trivial? not trailing-truncated?
  - section count >= 4 (most academic papers have at least Abstract +
    Introduction + Methods/Results + Discussion + References)
  - rendered length plausible (>5 KB)
  - title block not duplicated immediately in body (Nature-style)

Output: one line per paper with status + tags, then a triage section
listing the top issues for follow-up.

Usage:
  python scripts/verify_corpus_full.py
  python scripts/verify_corpus_full.py --only-fails
  python scripts/verify_corpus_full.py --paper jama_open_5
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
RENDERS_DIR = REPO_ROOT / "tmp" / "renders_v2.4.0"


_CONNECTOR_TAIL = {
    "of", "from", "for", "the", "and", "or", "to", "with", "on", "at",
    "by", "in", "as", "is", "a", "an", "but", "into", "onto", "upon",
    "than", "that", "which", "who", "when", "where", "while", "during",
    "after", "before", "because", "since", "though", "although",
}

_TITLE_RE = re.compile(r"^\s*#\s+([^\n]+)$", re.MULTILINE)
_H2_RE = re.compile(r"^\s*##\s+([^\n]+)$", re.MULTILINE)
_TABLE_HTML_RE = re.compile(r"<table>")
_FIG_CAPTION_RE = re.compile(r"^\*Figure\s+\d+\.?\s+[^\n]*?\*\s*$", re.MULTILINE)


def _all_pdfs() -> list[Path]:
    return sorted(APP_PDFS.rglob("*.pdf"))


def _find_spike_md(name: str) -> Optional[Path]:
    for d in SPIKE_OUT_DIRS:
        p = d / f"{name}.md"
        if p.exists():
            return p
    return None


def _word_set(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z]{4,}", text.lower()))


def _title_word_delta(rendered_title: Optional[str], spike_title: Optional[str]) -> int:
    if not rendered_title or not spike_title:
        return 0
    rw = set(re.findall(r"[A-Za-z]{4,}", rendered_title.lower()))
    sw = set(re.findall(r"[A-Za-z]{4,}", spike_title.lower()))
    return len(sw - rw)


def _has_immediate_title_repeat(md: str, title: str) -> bool:
    """True if the first few body paragraphs contain a span whose token
    content matches the title (the symptom my Nature-style sweep targets).
    Conservative — should never fire after v2.4.0 unless a regression."""
    if not title:
        return False
    title_tokens = re.findall(r"\w+", title.lower())
    if len(title_tokens) < 4:
        return False
    title_set = set(title_tokens)
    # Skip the title line itself; scan the next ~30 non-blank body lines.
    lines = md.split("\n")
    after_title = False
    accumulated: list[str] = []
    n_scanned = 0
    for ln in lines:
        line = ln.strip()
        if not after_title:
            if line.startswith("# "):
                after_title = True
            continue
        if not line or line.startswith("#"):
            if accumulated:
                # check whole accumulated span
                covered = sum(1 for t in title_tokens if t in accumulated)
                in_title = sum(1 for t in accumulated if t in title_set)
                if covered >= 0.8 * len(title_tokens) and in_title >= 0.7 * len(accumulated):
                    return True
            accumulated = []
            continue
        accumulated.extend(re.findall(r"\w+", line.lower()))
        n_scanned += 1
        if n_scanned > 30:
            break
    return False


def _metrics(md: str) -> dict:
    title_m = _TITLE_RE.search(md)
    title = title_m.group(1).strip() if title_m else None
    title_truncated = False
    if title:
        stripped = re.sub(r"[\s\.,;:!?\-—–]+$", "", title).lower()
        last = stripped.rsplit(None, 1)[-1] if " " in stripped else stripped
        title_truncated = last in _CONNECTOR_TAIL
    sections = _H2_RE.findall(md)
    return {
        "title": title,
        "title_truncated": title_truncated,
        "section_count": len(sections),
        "section_names": sections,
        "table_html_count": len(_TABLE_HTML_RE.findall(md)),
        "total_chars": len(md),
        "title_repeat_in_body": _has_immediate_title_repeat(md, title) if title else False,
        "longest_fig_caption_chars": max(
            (len(m.group(0)) for m in _FIG_CAPTION_RE.finditer(md)), default=0
        ),
    }


def _classify(name: str, md: str, spike_md: Optional[str]) -> tuple[str, dict, list[str]]:
    m = _metrics(md)
    tags: list[str] = []
    if m["title"] is None:
        tags.append("M")  # missing title
    if m["title_truncated"]:
        tags.append("T")
    if m["section_count"] < 4:
        tags.append("S")
    if m["title_repeat_in_body"]:
        tags.append("R")  # title repeats in body (Nature-style dup)
    appendix_idx = md.find("## Tables (unlocated in body)")
    body_section = md if appendix_idx < 0 else md[:appendix_idx]
    body_table_count = len(re.findall(r"^\s*###\s+Table\s+\d+", body_section, re.MULTILINE))
    if body_table_count > 0 and m["table_html_count"] == 0:
        tags.append("H")
    if m["longest_fig_caption_chars"] > 800:
        tags.append("C")
    if m["total_chars"] < 5000:
        tags.append("X")  # extremely short — likely failure

    spike_title = None
    if spike_md:
        spike_t = _TITLE_RE.search(spike_md)
        spike_title = spike_t.group(1).strip() if spike_t else None
    if spike_md:
        char_ratio = m["total_chars"] / max(1, len(spike_md))
        my_w = _word_set(md)
        sp_w = _word_set(spike_md)
        union = my_w | sp_w
        jaccard = len(my_w & sp_w) / len(union) if union else None
        m["char_ratio_vs_spike"] = char_ratio
        m["jaccard_vs_spike"] = jaccard
        if char_ratio < 0.7:
            tags.append("L")
        if jaccard is not None and jaccard < 0.6:
            tags.append("J")
    else:
        m["char_ratio_vs_spike"] = None
        m["jaccard_vs_spike"] = None
    if spike_title:
        miss = _title_word_delta(m["title"], spike_title)
        if miss > 0:
            tags.append("D")
        m["title_missing_words"] = miss
    else:
        m["title_missing_words"] = 0

    if not tags:
        status = "PASS"
    elif set(tags) <= {"L"}:
        status = "WARN"
    else:
        status = "FAIL"
    return status, m, tags


def _run_render(pdf_path: Path) -> tuple[str, float]:
    from docpluck import render_pdf_to_markdown
    t0 = time.time()
    data = pdf_path.read_bytes()
    md = render_pdf_to_markdown(data)
    return md, time.time() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper")
    ap.add_argument("--only-fails", action="store_true")
    ap.add_argument("--save-renders", action="store_true",
                    help="dump each rendered .md to tmp/renders_v2.4.0/")
    args = ap.parse_args()

    if args.paper:
        pdfs = [p for p in _all_pdfs() if p.stem == args.paper]
    else:
        pdfs = _all_pdfs()
    if not pdfs:
        print("ERROR: no PDFs found", file=sys.stderr)
        return 1
    if args.save_renders:
        RENDERS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"# Full-corpus verification — {len(pdfs)} PDFs (v2.4.0)")
    print(f"# legend: M=missing_title T=title_trunc D=title_words_dropped R=title_repeat_in_body S=few_sections H=missing_html C=cap_too_long X=output_too_short L=much_shorter J=low_jaccard")
    print()
    print(f"{'STATUS':6} {'PAPER':40} {'TAGS':15} {'CHARS':>8} {'SECT':>5} {'TABS':>5}  TIME")
    print("-" * 100)

    summary = {"PASS": 0, "WARN": 0, "FAIL": 0, "ERROR": 0}
    failures: list[tuple[str, str, dict, list[str]]] = []

    for pdf in pdfs:
        name = pdf.stem
        spike_path = _find_spike_md(name)
        spike_md = spike_path.read_text(encoding="utf-8", errors="ignore") if spike_path else None
        try:
            md, elapsed = _run_render(pdf)
        except Exception as e:
            print(f"{'ERROR':6} {name:40}  {type(e).__name__}: {e}")
            summary["ERROR"] += 1
            continue
        status, m, tags = _classify(name, md, spike_md)
        summary[status] += 1
        if status != "PASS":
            failures.append((name, status, m, tags))
        if args.only_fails and status == "PASS":
            continue
        if args.save_renders:
            (RENDERS_DIR / f"{name}.md").write_text(md, encoding="utf-8", errors="replace")
        tag_str = ",".join(tags) or "—"
        print(f"{status:6} {name:40} {tag_str:15} {m['total_chars']:>8} {m['section_count']:>5} {m['table_html_count']:>5}  {elapsed:.1f}s")

    print()
    print("# Summary")
    total = sum(summary.values())
    for k in ("PASS", "WARN", "FAIL", "ERROR"):
        if summary[k]:
            print(f"  {k:8} {summary[k]:3} / {total}")

    if failures:
        print()
        print("# Failure details")
        for name, status, m, tags in failures:
            tag_str = ",".join(tags)
            print(f"\n  {status} {name} [{tag_str}]")
            print(f"    title: {repr(m['title'])[:120]}")
            print(f"    sections={m['section_count']} tables={m['table_html_count']} chars={m['total_chars']}")
            if m.get("char_ratio_vs_spike") is not None:
                print(f"    vs_spike: char_ratio={m['char_ratio_vs_spike']:.2f} jaccard={m['jaccard_vs_spike']:.2f} title_missing_words={m.get('title_missing_words', 0)}")

    return 0 if summary["FAIL"] == 0 and summary["ERROR"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
