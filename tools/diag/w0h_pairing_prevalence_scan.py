"""How often do W0h/W0m's two UNDER-repair modes actually occur?

A post-fix review of v2.4.133 named two ways the new identity-based pairing
declines to repair a coefficient it could have repaired. Both are pass-through,
so neither publishes a wrong number — but both leave a corrupt one, and the
review asked for them to be closed. This project's rules say a rule must be
justified by a shape observed in a REAL document, and that one paper proves
existence while saying nothing about prevalence. So: count first.

    R1a  EXHAUSTIVE MATCH. When the layout proves k>1 sites all reading the same
         `num`, and the text holds exactly k candidate tokens, every candidate is
         provably corrupt — the counts force a bijection and there is nothing to
         disambiguate. The v2.4.133 rule still ran the per-site context match and
         refused all k on a tie.

    R1b  THE `cid` TOKEN. `_context_tokens` tokenises the layout line, which
         contains `(cid:N)` markers — artefacts of the very corruption being
         repaired, and impossible in the pdftotext window because pdftotext drops
         the glyph. `cid` therefore entered the wanted set as a token no
         candidate could ever match, deflating every score by the same fraction
         and, on a sparse line, pushing the best candidate under the 0.12
         corroboration floor into a REFUSAL.

Both are measured against the real pairing code, not a description of it: the
scan calls `_layout_negative_coefficient_sites` / `_layout_beta_coefficient_sites`
and `_best_context_match` directly, and for R1b re-runs the same decision with
the `cid` filter disabled so the two verdicts can be compared per site.

A ZERO HERE IS A CLAIM ABOUT THE INSTRUMENT unless the detector is shown to fire,
so the summary reports how many SITES were found at all. If that is 0 the counts
below mean nothing and the scan says so.

Usage:
    python tools/diag/w0h_pairing_prevalence_scan.py              # 26-paper baseline
    python tools/diag/w0h_pairing_prevalence_scan.py --sample 80  # wider denominator
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _corpus import baseline_corpus, coverage_line, sampled_corpus  # noqa: E402
from _language import detect_language  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from docpluck import normalize as N  # noqa: E402
from docpluck.extract import extract_pdf  # noqa: E402
from docpluck.extract_layout import extract_pdf_layout  # noqa: E402


def _w0h_candidates(text: str, num: str) -> list:
    pat = re.compile(r"(?<=[\w\s])(=\s{0,3})(" + re.escape(num) + r")(?![\d.])")
    return list(pat.finditer(text))


def _decide(candidates: list, text: str, line: str, num: str, *, strip_cid: bool):
    """Re-run the real pairing decision with the `cid` filter on or off."""
    saved = N._CID_MARKER_RE
    if not strip_cid:
        # A pattern that matches nothing, so `_context_tokens` leaves `cid` in.
        N._CID_MARKER_RE = re.compile(r"(?!x)x")
    try:
        return N._best_context_match(candidates, text, line, num)
    finally:
        N._CID_MARKER_RE = saved


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument(
        "--extra", action="append", default=[],
        help="path to an additional PDF to scan. Use this to include a KNOWN "
             "POSITIVE: the 26-paper render baseline contains none for W0h, so "
             "a run without one can only report an unbounded zero.",
    )
    args = ap.parse_args()

    corpus = sampled_corpus(args.sample) if args.sample else baseline_corpus()
    if args.limit:
        corpus = corpus[: args.limit]
    for extra in args.extra:
        p = Path(extra)
        if not p.is_file():
            print(f"FATAL: --extra {extra} does not exist", file=sys.stderr)
            return 2
        corpus = list(corpus) + [(p.stem, p)]

    print(coverage_line())
    print(f"scanning {len(corpus)} paper(s) for W0h/W0m pairing under-repair\n")

    scanned = 0
    total_sites = 0
    ambiguous_sites = 0          # >1 candidate, i.e. a pairing decision was needed
    r1a_papers: list[str] = []
    r1a_groups = 0               # num-groups where k>1 sites and k candidates
    r1b_papers: list[str] = []
    r1b_sites = 0                # decisions the `cid` filter CHANGED
    skipped: list[str] = []
    errors: list[tuple[str, str]] = []

    for key, path in corpus:
        try:
            data = path.read_bytes()
            text, _engine = extract_pdf(data)
            lang, _c = detect_language(text)
            if lang != "english":
                skipped.append(f"{key} [{lang}]")
                continue
            layout = extract_pdf_layout(data)
            sites = list(N._layout_negative_coefficient_sites(layout))
        except Exception as exc:  # noqa: BLE001
            errors.append((key, f"{type(exc).__name__}: {exc}"[:120]))
            continue
        scanned += 1
        total_sites += len(sites)
        if not sites:
            continue

        per_num = Counter(s["num"] for s in sites)
        hit_a = hit_b = 0
        for num, k in per_num.items():
            cands = _w0h_candidates(text, num)
            if k > 1 and len(cands) == k:
                hit_a += 1
        for site in sites:
            cands = _w0h_candidates(text, site["num"])
            if len(cands) <= 1:
                continue          # no pairing decision to make
            ambiguous_sites += 1
            with_cid = _decide(cands, text, site["line"], site["num"], strip_cid=False)
            without = _decide(cands, text, site["line"], site["num"], strip_cid=True)
            if (with_cid is None) != (without is None) or with_cid is not without:
                hit_b += 1

        if hit_a:
            r1a_papers.append(key)
            r1a_groups += hit_a
        if hit_b:
            r1b_papers.append(key)
            r1b_sites += hit_b
        if hit_a or hit_b:
            print(f"-- {key}: R1a groups={hit_a}  R1b changed decisions={hit_b}")

    print("\n" + "=" * 72)
    print(f"PAPERS SCANNED             {scanned}")
    print(f"W0h SITES FOUND            {total_sites}   <- the instrument's known positive")
    print(f"SITES NEEDING A PAIRING    {ambiguous_sites}  (>1 textual candidate)")
    print(f"R1a exhaustive-match groups {r1a_groups} in {len(r1a_papers)} paper(s)"
          f"{': ' + ', '.join(r1a_papers) if r1a_papers else ''}")
    print(f"R1b decisions the cid filter changed {r1b_sites} in {len(r1b_papers)} paper(s)"
          f"{': ' + ', '.join(r1b_papers) if r1b_papers else ''}")
    if skipped:
        print(f"SKIPPED non-English        {len(skipped)}")
    if errors:
        print(f"ERRORS                     {len(errors)}")
        for key, msg in errors[:6]:
            print(f"     {key}: {msg}")
    if total_sites == 0:
        print("\nTHE DETECTOR FOUND NO SITES AT ALL on this corpus, so the counts "
              "above are UNBOUNDED, not clean. This corpus contains no known "
              "positive for W0h — re-run including "
              "`ar_apa_j_jesp_2009_12_011` before reading any zero as evidence.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
