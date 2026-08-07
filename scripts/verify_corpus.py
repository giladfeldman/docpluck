"""Corpus verifier: render the corpus and compare against a pinned baseline.

Everything this needs comes from **article-finder**, the sole custodian of
papers and tool baselines. Nothing is located by globbing a directory and
nothing is read from a sibling repo:

  - the EXPECTED PAPER SET is `papers-with-view <baseline view>`
  - each PDF is located by canonical key via `find-pdf.py` (cache only)
  - each baseline is a versioned tool artifact, e.g.
    `render-baseline__docpluck-splice-spike@2026.05.10`

Why the paper set comes from the custodian (2026-08-07). This gate used to
derive its corpus from `glob("*.md")` over a local directory and then print
`N / N`, where N was *whatever it happened to find*. A half-present corpus
therefore reported a clean pass, and a corpus that vanished entirely reported
nothing at all. Coverage has to be asserted against an external, authoritative
denominator, or it is not being checked.

The three states are kept distinct, because conflating them is what let this
gate sit dead for a week while its output read as normal:

  no papers resolvable      -> SKIP,    exit 0  (this machine has no corpus)
  some but not all resolved -> PARTIAL, exit 1  (the silent-coverage-loss bug)
  all resolved              -> per-paper PASS/WARN/FAIL, exit 0/1

For each paper:
  - Locate the PDF through article-finder by canonical key
  - Verify it is the SAME BYTES the baseline was produced from
  - Run docpluck.render_pdf_to_markdown
  - Compute health metrics on the output
  - Compare against the pinned baseline
  - Print a per-paper PASS/WARN/FAIL line and a summary

Metrics computed per paper:
  - Title rescue: present? truncated (ends in connector)?
  - Section count
  - Table count (and how many have non-empty html)
  - Figure count (and longest caption length — detects Bug 4 leak)
  - Char-ratio vs spike baseline (out_len / spike_len)
  - Word-set Jaccard similarity to spike baseline (cheap content check)

Failure tags emitted (single-letter, easy to grep):
  T  = title truncated (ends in connector)
  D  = title has dropped/missing word(s) vs baseline (middle-of-title loss)
  S  = section count < expected
  H  = table missing html
  C  = caption > 800 chars (boundary leak)
  L  = output much shorter than baseline (<70%)
  J  = Jaccard < 0.6 (very different content)

Usage:
  python scripts/verify_corpus.py
  python scripts/verify_corpus.py --paper 10.1016/j.jesp.2021.104154
  python scripts/verify_corpus.py --diff                    # dump rendered to tmp/
  python scripts/verify_corpus.py --baseline-view render-baseline__docpluck@2.5.0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent.parent

# article-finder is the sole custodian of papers, ground truth and tool
# baselines. Overridable for a relocated install; never defaulted to a path
# inside this repo, which is the coupling this rewire exists to remove.
ARTICLE_FINDER = Path(
    os.environ.get("ARTICLE_FINDER_HOME")
    or Path(os.path.expanduser("~")) / ".claude" / "skills" / "article-finder"
)

# The baseline this corpus is measured against, as `<family>__<producer>`.
# Deliberately versionless HERE and resolved to the highest registered version
# at runtime: pinning a version in source would go stale silently, while a
# bare unversioned VIEW is refused by article-finder outright (a view a new
# release could overwrite in place turns this gate into a tautology).
#
# The prototype set that seeded this corpus is still registered as
# `render-baseline__docpluck-splice-spike@2026.05.10` and can be selected with
# `--baseline-view`. It is no longer the default because three of its 26
# artifacts were rendered from a different manifestation of the paper than the
# article repository holds (publisher PDF vs arXiv preprint vs PMC author
# manuscript share a DOI, not bytes), which is unverifiable by construction.
DEFAULT_BASELINE_SPEC = "render-baseline__docpluck"


# Set of connector words copy-pasted from docpluck.render._TITLE_CONNECTOR_TAIL_WORDS.
# Kept in sync via test; recomputing here keeps the verifier dependency-free.
_CONNECTOR_TAIL = {
    "of", "from", "for", "the", "and", "or", "to", "with", "on", "at",
    "by", "in", "as", "is", "a", "an", "but", "into", "onto", "upon",
    "than", "that", "which", "who", "when", "where", "while", "during",
    "after", "before", "because", "since", "though", "although",
}


def _af(script: str, *args: str) -> subprocess.CompletedProcess:
    """Run an article-finder command."""
    return subprocess.run(
        [sys.executable, str(ARTICLE_FINDER / script), *args],
        capture_output=True, text=True,
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_pinned(spec: str) -> bool:
    """True when `spec` already names an exact `family__producer@version`."""
    if str(ARTICLE_FINDER) not in sys.path:
        sys.path.insert(0, str(ARTICLE_FINDER))
    from _lib_artifacts import parse_tool_view
    return parse_tool_view(spec) is not None


def _resolve_baseline_view(spec: str) -> Optional[str]:
    """Resolve `<family>__<producer>` to its highest registered version."""
    if _is_pinned(spec):
        return spec
    r = _af("ai-gold.py", "papers-with-view", spec, "--latest", "--keys-only")
    for line in r.stderr.splitlines():
        if line.startswith("resolved --latest to view "):
            return line.split("resolved --latest to view ", 1)[1].strip()
    return None


def _expected_papers(view: str) -> list[str]:
    """The corpus this gate is REQUIRED to cover — the coverage denominator.

    Comes from the custodian, never from whatever happens to be on disk. This
    is the whole point of the rewire: a denominator you compute from the
    numerator can only ever report 100%.
    """
    r = _af("ai-gold.py", "papers-with-view", view, "--keys-only")
    return sorted(k for k in (ln.strip() for ln in r.stdout.splitlines()) if k)


def _key_to_doi(key: str) -> str:
    """Canonical key -> DOI. EVERY ``__`` is an encoded ``/``, not just the first.

    `10.1093/sf/soaf022` (Social Forces) keys as `10.1093__sf__soaf022`, and
    replacing only the first separator yields `10.1093/sf__soaf022` — a DOI that
    matches nothing, reported as "paper not in the repository". Fixture keys
    (`fixture__<producer>__<name>`) are not DOIs and pass through untouched.
    """
    return key.replace("__", "/") if key.startswith("10.") else key


def _find_pdf(key: str) -> Optional[Path]:
    """Locate a paper's PDF by canonical key, from the repository cache only.

    `--dry-run` keeps this offline: a verification gate must never reach out to
    the network mid-run, and a paper that is merely *downloadable* is not a
    paper this machine can verify.
    """
    r = _af("find-pdf.py", _key_to_doi(key), "--dry-run")
    try:
        d = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    if d.get("found") and d.get("source") == "repository_cache" and d.get("path"):
        p = Path(d["path"])
        return p if p.is_file() else None
    return None


def _baseline_for(key: str, view: str) -> tuple[Optional[Path], Optional[str]]:
    """Return (baseline path, source_pdf_sha256 it was produced from)."""
    if str(ARTICLE_FINDER) not in sys.path:
        sys.path.insert(0, str(ARTICLE_FINDER))
    from ai_gold_client import get_view
    path = get_view(key, view)
    if not path:
        return None, None
    meta_path = Path(path).with_name(f"{view}.meta.json")
    sha = None
    if meta_path.is_file():
        try:
            sha = json.loads(meta_path.read_text(encoding="utf-8")).get("source_pdf_sha256")
        except json.JSONDecodeError:
            pass
    return Path(path), sha


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


def _title_word_delta(rendered_title: Optional[str], spike_title: Optional[str]) -> int:
    """Count distinctive title words present in the spike but missing from
    the rendered title. Distinctive = 4+ letters (skips connectors/the/and).

    Catches middle-of-title truncations like
    ``Tversky and Kahneman (1992)`` → ``Tversky and (1992)`` (missing
    "Kahneman"), which the trailing-connector check (T) doesn't see.
    """
    if not rendered_title or not spike_title:
        return 0
    rendered_words = set(re.findall(r"[A-Za-z]{4,}", rendered_title.lower()))
    spike_words = set(re.findall(r"[A-Za-z]{4,}", spike_title.lower()))
    return len(spike_words - rendered_words)


def _classify(name: str, md: str, spike_md: Optional[str]) -> tuple[str, dict, list[str]]:
    """Return (status, metrics, tags). Status: PASS|WARN|FAIL."""
    m = _metrics(md)
    tags: list[str] = []

    if m["title_truncated"]:
        tags.append("T")
    if m["section_count"] < 4:
        tags.append("S")
    # Title-word delta vs spike baseline catches middle-of-title drops
    # that the T-tag (trailing-connector check) misses.
    spike_title: Optional[str] = None
    if spike_md:
        spike_m = _TITLE_RE.search(spike_md)
        spike_title = spike_m.group(1).strip() if spike_m else None
    missing_title_words = _title_word_delta(m["title"], spike_title)
    if missing_title_words > 0:
        tags.append("D")
    m["title_missing_words"] = missing_title_words
    m["spike_title"] = spike_title
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
    ap.add_argument("--paper", help="run only this paper (canonical key or DOI)")
    ap.add_argument("--diff", action="store_true",
                    help="dump rendered output to tmp/")
    ap.add_argument("--baseline-view", default=DEFAULT_BASELINE_SPEC,
                    help="'<family>__<producer>' (resolved to the newest "
                         "version) or a fully pinned '...@<version>'")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    if not (ARTICLE_FINDER / "ai-gold.py").is_file():
        print(
            f"SKIP: article-finder is not installed at {ARTICLE_FINDER}. It is "
            "the custodian of both the corpus and the render baselines, so "
            "there is nothing to verify against. Set ARTICLE_FINDER_HOME if it "
            "lives elsewhere. This is a clean skip, not a failure.",
            file=sys.stderr,
        )
        return 0

    view = _resolve_baseline_view(args.baseline_view)
    if view is None:
        print(
            f"ERROR: no registered baseline matches {args.baseline_view!r}.\n"
            f"Register one with:\n"
            f"  ai-gold.py register-view <doi> {args.baseline_view}@<version> "
            f"<rendered.md> --producer docpluck --artifact-class tool",
            file=sys.stderr,
        )
        return 1

    expected = _expected_papers(view)
    if not expected:
        print(
            f"SKIP: baseline view {view} has no registered papers — nothing to "
            "verify. This is a clean skip on a machine with no corpus, not a "
            "failure.",
            file=sys.stderr,
        )
        return 0

    papers = [args.paper.replace("/", "__")] if args.paper else expected
    print(f"# Corpus verification — baseline {view}")
    print(f"# expected corpus: {len(expected)} papers (from article-finder, "
          f"not from a directory listing)")
    print(f"# legend: T=title_truncated D=title_words_dropped S=few_sections H=missing_html C=caption_too_long L=much_shorter J=low_jaccard")
    print()
    print(f"{'STATUS':9} {'PAPER':40} {'TAGS':12} {'CHARS':>8} {'SECT':>5} {'TABS':>5} {'CAP':>6} {'RATIO':>6} {'JACC':>6}  TIME")
    print("-" * 113)

    summary = {"PASS": 0, "WARN": 0, "FAIL": 0, "NO_PDF": 0,
               "NO_BASE": 0, "PDF_DRIFT": 0, "ERROR": 0}
    failures_by_tag: dict[str, list[str]] = {}
    drifted: list[str] = []

    for key in papers:
        baseline_path, baseline_pdf_sha = _baseline_for(key, view)
        if baseline_path is None:
            print(f"{'NO_BASE':9} {key:40}  no {view} registered")
            summary["NO_BASE"] += 1
            continue
        pdf = _find_pdf(key)
        if pdf is None:
            print(f"{'NO_PDF':9} {key:40}  not in the article repository cache")
            summary["NO_PDF"] += 1
            continue

        # Comparing a render of file A against a baseline built from file B
        # measures nothing, and would report the difference as a docpluck
        # regression. Two manifestations of one paper (publisher PDF vs arXiv
        # preprint vs PMC author manuscript) share a DOI but not bytes.
        if baseline_pdf_sha and _sha256(pdf) != baseline_pdf_sha:
            print(f"{'PDF_DRIFT':9} {key:40}  repository PDF differs from the "
                  f"one this baseline was built from")
            summary["PDF_DRIFT"] += 1
            drifted.append(key)
            continue

        baseline_md = baseline_path.read_text(encoding="utf-8", errors="ignore")
        try:
            md, elapsed = _run_render(pdf)
        except Exception as e:
            print(f"{'ERROR':9} {key:40}  {type(e).__name__}: {e}")
            summary["ERROR"] += 1
            continue
        status, m, tags = _classify(key, md, baseline_md)
        summary[status] += 1
        for t in tags:
            failures_by_tag.setdefault(t, []).append(key)

        tag_str = ",".join(tags) or "—"
        ratio_str = f"{m['char_ratio_vs_spike']:.2f}" if m['char_ratio_vs_spike'] else "—"
        jacc_str = f"{m['jaccard_vs_spike']:.2f}" if m['jaccard_vs_spike'] is not None else "—"
        print(f"{status:9} {key:40} {tag_str:12} {m['total_chars']:>8} {m['section_count']:>5} {m['table_html_count']:>5} {m['longest_fig_caption_chars']:>6} {ratio_str:>6} {jacc_str:>6}  {elapsed:.1f}s")

        if args.diff:
            out_dir = REPO_ROOT / "tmp"
            out_dir.mkdir(exist_ok=True)
            (out_dir / f"{key}.rendered.md").write_text(md, encoding="utf-8")
            print(f"  → dumped to tmp/{key}.rendered.md")

    print()
    print("# Summary")
    verified = summary["PASS"] + summary["WARN"] + summary["FAIL"]
    attempted = len(papers)
    for k in ("PASS", "WARN", "FAIL", "NO_PDF", "NO_BASE", "PDF_DRIFT", "ERROR"):
        if summary[k]:
            print(f"  {k:10} {summary[k]:3} / {attempted}")
    print(f"  {'COVERAGE':10} {verified:3} / {len(expected)} papers in the "
          f"registered corpus were actually rendered and compared")

    if failures_by_tag:
        print()
        print("# Failures by tag")
        for tag, names in sorted(failures_by_tag.items()):
            print(f"  {tag}: {len(names):2}  {', '.join(names[:6])}{'...' if len(names) > 6 else ''}")

    if drifted:
        print()
        print("# Source-PDF drift (compared nothing — NOT a docpluck regression)")
        for k in drifted:
            print(f"  {k}")
        print("  The repository holds a different file for this DOI than the "
              "baseline was built from.\n  Re-register the baseline against the "
              "repository's copy, or reconcile the two manifestations.")

    # "Nothing was verified" is a clean skip ONLY when nothing was ever
    # attempted. If renders crashed or the source PDFs drifted, verified is
    # also 0 — and returning 0 there would be this gate reporting a green run
    # because every single paper failed, which is the exact defect class this
    # rewire exists to remove.
    nothing_attempted = (summary["ERROR"] == 0 and summary["PDF_DRIFT"] == 0)
    if not args.paper and verified == 0 and nothing_attempted:
        print()
        print("SKIP: nothing in the registered corpus is available on this "
              "machine — no PDF resolved. Clean skip, not a failure.",
              file=sys.stderr)
        return 0

    if not args.paper and verified < len(expected):
        print()
        print(
            f"PARTIAL COVERAGE: {verified} of {len(expected)} registered papers "
            f"were verified. A gate that silently shrinks its own corpus reports "
            f"a clean pass on a broken one — so this is a FAILURE, not a note.",
            file=sys.stderr,
        )
        return 1

    return 0 if summary["FAIL"] == 0 and summary["ERROR"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
