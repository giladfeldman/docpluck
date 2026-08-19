"""Wide-corpus BASELINE-FREE render verifier: structural heuristics, no comparison.

Sibling of ``verify_corpus.py``, and the division of labour is now explicit:

    verify_corpus.py        compares each render against a PINNED baseline
                            registered with article-finder. That is the gate.
    verify_corpus_full.py   applies baseline-FREE structural heuristics to a WIDER
                            corpus, so a paper with no registered baseline is still
                            looked at. It is a smoke, never a gate.

Heuristics applied per paper:
  - title present? non-trivial? not trailing-truncated?
  - section count >= 4 (most academic papers have at least Abstract +
    Introduction + Methods/Results + Discussion + References)
  - rendered length plausible (>5 KB)
  - title block not duplicated immediately in body (Nature-style)

TWO DEFECTS FIXED 2026-08-19, both of the same "silently measures nothing" family
this repo has met repeatedly:

1. **The spike-baseline arm compared against nothing.** ``SPIKE_OUT_DIRS`` held two
   filesystem paths that the 2026-08-06 public-repo redaction rewrote into the PROSE
   placeholder ``"an internal design doc"`` — twice, identically. ``_find_spike_md``
   therefore returned ``None`` for every paper, so the char-ratio / Jaccard / D-tag
   comparison never ran, and the script printed PASS lines the whole time. A redaction
   pass that rewrites a path CONSTANT as if it were a docstring leaves working-looking
   code that does nothing. The arm is REMOVED rather than repaired: baseline
   comparison belongs to ``verify_corpus.py``, which does it against the custodian.

2. **The corpus came from ``rglob`` over a sibling repo.** That violates the custody
   hard rule (article-finder is the sole custodian) and carries the coverage defect
   ``verify_corpus.py`` was rewired to remove on 2026-08-07: a denominator computed by
   globbing reports whatever it happens to find, so a corpus that has silently shrunk
   still prints a clean run. The paper set now comes from the custodian via
   ``tools/diag/_corpus.py`` and every run prints its COVERAGE line.

Usage:
  python scripts/verify_corpus_full.py
  python scripts/verify_corpus_full.py --only-fails
  python scripts/verify_corpus_full.py --sample 60      # wider than the baseline set
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
sys.path.insert(0, str(REPO_ROOT))
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


def _corpus(sample: Optional[int]) -> list[tuple[str, Path]]:
    """The paper set, from the CUSTODIAN — never a directory glob.

    See the module docstring: a denominator computed by globbing reports whatever it
    happens to find, so a corpus that has silently shrunk still prints a clean run.
    """
    from tools.diag._corpus import baseline_corpus, sampled_corpus

    return sampled_corpus(sample) if sample else baseline_corpus()


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


_CORRECTION_TITLE_RE = re.compile(
    r"\b(?:addendum|corrigendum|correction|erratum|retraction)\b",
    re.IGNORECASE,
)


def _classify(name: str, md: str, spike_md: Optional[str]) -> tuple[str, dict, list[str]]:
    m = _metrics(md)
    tags: list[str] = []
    title_text = m["title"] or ""
    is_correction_paper = bool(_CORRECTION_TITLE_RE.search(title_text))

    if m["title"] is None:
        tags.append("M")  # missing title
    if m["title_truncated"]:
        tags.append("T")
    if m["section_count"] < 4 and not is_correction_paper:
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
    # X (short output) is suppressed when the title indicates an ADDENDUM /
    # CORRIGENDUM / CORRECTION / ERRATUM — these are genuinely 1-page
    # correction notices and a short render is correct (the
    # jdm_.2023.10 paper is the canonical case in the 101-PDF corpus).
    if m["total_chars"] < 5000 and not is_correction_paper:
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
    ap.add_argument("--sample", type=int, default=None,
                    help="sample N papers from the shared repository instead of the baseline set")
    ap.add_argument("--only-fails", action="store_true")
    ap.add_argument("--save-renders", action="store_true",
                    help="dump each rendered .md to tmp/renders_v2.4.0/")
    args = ap.parse_args()

    from tools.diag._corpus import coverage_line

    corpus = _corpus(args.sample)
    resolved = len(corpus)
    if args.paper:
        corpus = [(k, p) for k, p in corpus if p.stem == args.paper or k == args.paper]
    if not corpus:
        print("ERROR: the custodian resolved no PDFs for this selection", file=sys.stderr)
        return 1
    pdfs = [p for _, p in corpus]
    if args.save_renders:
        RENDERS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"# Wide-corpus BASELINE-FREE verification — {len(pdfs)} PDFs")
    print(f"# {coverage_line()}")
    if len(corpus) != resolved:
        # Never let a --paper filter hide behind the corpus-wide COVERAGE line: the
        # two numbers mean different things and printing only the larger one is the
        # denominator defect this script was just repaired for.
        print(f"# FILTERED: --paper selected {len(corpus)} of the {resolved} resolved papers.")
    print("# HEURISTIC SMOKE, NOT A GATE: no render is compared against a baseline here.")
    print("#   The baseline comparison is scripts/verify_corpus.py, which does it against")
    print("#   the custodian's pinned view. A clean run here is not evidence of no regression.")
    print("# legend: M=missing_title T=title_trunc R=title_repeat_in_body S=few_sections H=missing_html C=cap_too_long X=output_too_short")
    print()
    print(f"{'STATUS':6} {'PAPER':40} {'TAGS':15} {'CHARS':>8} {'SECT':>5} {'TABS':>5}  TIME")
    print("-" * 100)

    summary = {"PASS": 0, "WARN": 0, "FAIL": 0, "ERROR": 0}
    failures: list[tuple[str, str, dict, list[str]]] = []

    for pdf in pdfs:
        name = pdf.stem
        # No baseline arm here by design — see the module docstring. Passing None is
        # the honest statement that nothing is being compared, rather than a lookup
        # that silently finds nothing and reports PASS.
        spike_md = None
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
