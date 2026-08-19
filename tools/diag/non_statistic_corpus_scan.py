"""Does any normalization rule rewrite a NON-STATISTIC?

docpluck's numeric rules key on shapes like `digit , digit` and `digit . digit`.
So does a URL path, a DOI, an ISBN, an IP address, a version string, a date, a
page range and a file path. A rule that cannot tell them apart corrupts the
paper's own references while looking like it is canonicalising a statistic.

This is not hypothetical and it is not old. Measured 2026-08-14, at HEAD:

    10.1177/0146167210380928 p13, reference list
        http://content.time.com/time/specials/article/0,9171,1848755,00.html
    A3c read `0,9171` as a leading-zero European decimal and emitted
        .../article/0.9171,1848755,00.html          a different URL. It 404s.

That defect survived QA and code review because **nothing ever asked the
question this scan asks.** (`HANDOFF_2026-08-13c` PHASE C: "The A3c URL
corruption should have been caught by QA or code-review, and was not.")

METHOD, and why it is shaped this way. Tokens are harvested FROM REAL PAPERS,
never invented: the second directive of 2026-08-13 is that a rule or a case must
be justified by a shape observed in a real document, and the same standard is
worth holding a guard battery to. A constructed battery tells you what the code
does to strings you imagined; a harvested one tells you what the code does to
the corpus. Each token is checked IN ITS OWN LINE — the rest of the line may
legitimately change (a real statistic on the same line should still normalize),
so the assertion is on the TOKEN's survival, not the line's.

ENGLISH ONLY, exclusions printed. See `docs/SCOPE.md`.

Run:  python tools/diag/non_statistic_corpus_scan.py [--sample N] [--seed S]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _corpus import baseline_corpus, coverage_line, sampled_corpus  # noqa: E402
from _language import detect_language  # noqa: E402

from docpluck.extract import extract_pdf  # noqa: E402
from docpluck.normalize import NormalizationLevel, normalize_text  # noqa: E402

# Each class names a thing that is NOT a statistic but carries digit/separator
# shapes. A rule that changes any of these has misidentified an identifier as a
# number, which is the defect class this scan exists to catch.
CLASSES: dict[str, re.Pattern[str]] = {
    "url": re.compile(r"https?://[^\s<>\"')]+|www\.[^\s<>\"')]+"),
    "doi": re.compile(r"\b10\.\d{4,9}/[^\s<>\"')]+"),
    "isbn": re.compile(r"\bISBN[:\s]*[\d,\-Xx]{10,20}"),
    "ip_address": re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),
    "version": re.compile(r"\bv?\d+\.\d+(?:\.\d+)+\b"),
    "iso_date": re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    "slash_date": re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    "page_range": re.compile(r"\bpp?\.\s?\d+[-–]\d+\b"),
    "file_path": re.compile(r"\b[\w./-]+\.(?:csv|xlsx?|sav|txt|zip|Rmd|py|R)\b"),
    "statute": re.compile(r"\b(?:Directive|Regulation|Act|Article)\s+\d+[\d,/]*\b"),
    # An OSF/registry handle: short alphanumerics that a glyph rule can eat.
    "registry_id": re.compile(r"\bosf\.io/\w+|\bNCT\d{8}\b|\bPROSPERO\s*CRD\d+"),
}


_ALNUM = re.compile(r"[^0-9A-Za-z]")

# Changes docpluck is ENTITLED to make to any text, identifier or not, and which
# must therefore not be reported here. Folding them out is what makes this gate
# worth running: its first version reported 127 "defects" of which nearly all were
# S5 dash canonicalisation and S6 invisible-character stripping doing their job —
# and a gate that cries wolf is a gate everyone learns to skip.
#
# Both are genuinely DESIRABLE on an identifier: a DOI carrying U+2010 HYPHEN or a
# URL carrying a U+200B ZERO WIDTH SPACE does not resolve, and folding them to
# ASCII is what makes the link work.
_DASHES = dict.fromkeys(
    [0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2212, 0x00AD, 0x2043], "-"
)
_INVISIBLE = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF], None
)
# Ligatures likewise: a PDF that encodes `/files/` with U+FB01 gives a URL that
# does not resolve, and expanding it is the fix, not the bug. Measured instance:
# `http://www.people-press.org/ﬁles/2015/` in 10.1016/j.jesp.2017.06.001.
_LIGATURES = {
    0xFB00: "ff", 0xFB01: "fi", 0xFB02: "fl",
    0xFB03: "ffi", 0xFB04: "ffl", 0xFB05: "st", 0xFB06: "st",
}
_NOTATION_FOLD = {**_DASHES, **_INVISIBLE, **_LIGATURES}


def notation_fold(s: str) -> str:
    """Collapse the differences a NOTATION step is allowed to introduce."""
    return re.sub(r"\s+", " ", s.translate(_NOTATION_FOLD)).strip()


def _classify_loss(token: str, out: str) -> str | None:
    """Why did ``token`` not survive? Returns None when that is CORRECT.

    Three outcomes, and conflating them was the first version's bug — it counted
    a furniture strip as a corruption and reported 862 "defects" that were the
    library working as designed:

      REWRITTEN  the token is still there with its separators changed. This is
                 the defect class: a rule read an identifier as a number.
                 `article/0,9171,…` -> `article/0.9171,…`
      REMOVED    the token is gone but its line survived — something deleted an
                 identifier out of live prose. Rarer, still a defect.
      None       the whole line went away. That is a running header, a masthead
                 or a "Downloaded from …" watermark, and removing it is the
                 FURNITURE class doing its job. Not reported.
    """
    if not out.strip():
        return None
    core = _ALNUM.sub("", token)
    if core and core in _ALNUM.sub("", out):
        return "REWRITTEN"
    # The token's alphanumeric core is gone too. If essentially nothing of the
    # line survived, it was furniture; if the line is still substantially there,
    # an identifier was deleted out of it.
    return "REMOVED" if len(out.strip()) >= 20 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--seed", type=int, default=20260814)
    ap.add_argument("--max-report", type=int, default=40)
    args = ap.parse_args()

    papers = (sampled_corpus(args.sample, args.seed) if args.sample
              else baseline_corpus())
    print(coverage_line())
    print(f"scanning {len(papers)} papers; ENGLISH-language articles only")
    print(f"classes: {', '.join(CLASSES)}\n")

    seen: Counter[str] = Counter()
    dropped: Counter[str] = Counter()
    broken: dict[str, list[tuple[str, str, str, list[str], str]]] = defaultdict(list)
    langs: Counter[str] = Counter()
    excluded = 0
    english = 0
    failures = 0

    for key, path in papers:
        try:
            with open(path, "rb") as fh:
                res = extract_pdf(fh.read())
            raw = res[0] if isinstance(res, tuple) else res
        except Exception as exc:  # pragma: no cover - diagnostic script
            failures += 1
            print(f"  SKIP {key}: {type(exc).__name__}: {exc}")
            continue

        lang, _ = detect_language(raw)
        langs[lang] += 1
        if lang != "english":
            excluded += 1
            continue
        english += 1

        for line in raw.splitlines():
            if not line.strip():
                continue
            hits = [(cls, m.group(0)) for cls, rx in CLASSES.items()
                    for m in rx.finditer(line)]
            if not hits:
                continue
            try:
                out, rep = normalize_text(line, NormalizationLevel.academic)
            except Exception:  # pragma: no cover - diagnostic script
                continue
            folded_out = notation_fold(out)
            for cls, token in hits:
                seen[cls] += 1
                if token in out or notation_fold(token) in folded_out:
                    continue
                verdict = _classify_loss(token, out)
                if verdict is None:
                    dropped[cls] += 1   # the whole line was furniture. Correct.
                    continue
                broken[cls].append((key, token, line.strip()[:160],
                                    list(rep.steps_changed), verdict))

    print("=== language distribution (ALL scanned) ===")
    for lang, n in langs.most_common():
        print(f"  {lang:18} {n}")
    print(f"  (excluded {excluded} non-English; {english} English scanned)")

    print("\n=== NON-STATISTIC TOKENS ===")
    print("  'furniture' = the whole line was a header/masthead/watermark and was")
    print("  correctly removed. Only 'defects' are rule failures.")
    print(f"\n  {'class':14} {'seen':>7} {'furniture':>10} {'defects':>9}")
    total_broken = 0
    for cls in CLASSES:
        n = len(broken[cls])
        total_broken += n
        flag = "   <== DEFECT" if n else ""
        print(f"  {cls:14} {seen[cls]:>7} {dropped[cls]:>10} {n:>9}{flag}")

    if total_broken:
        print(f"\n=== {total_broken} DEFECT(S) — a rule misidentified an "
              f"identifier as a number ===")
        shown = 0
        for cls in CLASSES:
            for key, token, line, steps, verdict in broken[cls]:
                if shown >= args.max_report:
                    break
                shown += 1
                print(f"\n  [{cls}] {verdict}  {key}")
                print(f"    token      : {token}")
                print(f"    rules fired: {', '.join(steps) or '(none tracked)'}")
                print(f"    line       : {line}")
        if total_broken > shown:
            print(f"\n  ... and {total_broken - shown} more")
    else:
        print("\n  CLEAN — no non-statistical token was rewritten or deleted "
              "out of live prose.")

    if failures:
        print(f"\nNOTE: {failures} paper(s) unreadable — counts are over "
              f"{len(papers) - failures} papers, not {len(papers)}.")
    print(f"\n{coverage_line()}")
    # Non-zero exit so this can gate a release rather than merely inform one.
    return 1 if total_broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
