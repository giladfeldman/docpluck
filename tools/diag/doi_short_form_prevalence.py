"""How often does a `doi:`-prefixed SHORT-form DOI actually occur in English papers?

WHY THIS EXISTS. On 2026-09-16 a review found that docpluck carried two
independent restatements of "this text is a DOI identifier" -- the H0
header-zone exemption `_DOI_IDENTIFIER_IN_LINE` and the P0r footer predicate
`_BARE_DOI_IDENTIFIER_LINE` -- and that they disagreed on `doi:10/gt3vmw`. The
divergence is real and the duplication is a genuine ONE-CONCEPT-ONE-TABLE
violation, so both now derive from shared fragments.

But the divergence was found by running a CONSTRUCTED string through the two
regexes, and a constructed string is evidence about the CODE, never about the
corpus (CLAUDE.md, "CASE STUDIES COME FROM REAL PAPERS"). Unifying the two
predicates WIDENS the H0 exemption: a header-zone line reading `doi: 10/gt3vmw`
is now protected from deletion where before it was not. That is a behaviour
change, and this project ships no rule without its corpus firing count. This
scan is that count.

TWO-SIDED BY CONSTRUCTION, because a zero is a claim about the INSTRUMENT until
proven otherwise (CLAUDE.md). The scan reports the target shape AND a control --
any bare short-form `10/xxxx` anywhere in the text. If the control is also zero
the measurement is unbounded and says nothing; only a firing control licenses
reading the target's zero as a property of the corpus.

ONE CONCEPT, ONE TABLE: the shapes are imported from `docpluck.normalize`, never
restated here. A scan carrying its own copy of the pattern it measures reports a
number about code that does not run.

ENGLISH ONLY, and the exclusions are printed. docpluck serves English-language
articles; evidence from bilingual SciELO or Turkish journals does not transfer.

Run:  python tools/diag/doi_short_form_prevalence.py [--sample N] [--seed S]
"""

from __future__ import annotations

# --- repo-root import guard (do not remove) ---------------------------------
# Python puts THIS SCRIPT'S OWN DIRECTORY on sys.path[0] -- never the current
# working directory -- so a bare ``import docpluck`` silently resolves to
# whatever copy is INSTALLED. Keyed on the pyproject.toml marker rather than a
# parents[N] count, so it survives the file being moved. Pinned by
# tests/test_harness_scripts_import_the_working_tree.py.
import sys as _sys
from pathlib import Path as _Path

for _root in _Path(__file__).resolve().parents:
    if (_root / "pyproject.toml").is_file():
        if str(_root) not in _sys.path:
            _sys.path.insert(0, str(_root))
        break
# --- end repo-root import guard ---------------------------------------------

import argparse
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _corpus import coverage_line, sampled_corpus  # noqa: E402
from _language import detect_language  # noqa: E402

from docpluck.extract import extract_pdf  # noqa: E402
from docpluck.normalize import _DOI_SHORT_FORM  # noqa: E402

# The shape the unification newly exempts: a `doi:` lead-in carrying the SHORT
# form, with no `doi.org` host (the host form was already matched before the
# change, so counting it would overstate what changed).
_TARGET = re.compile(rf"\bdoi\s*:\s*{_DOI_SHORT_FORM}", re.IGNORECASE)
_HOSTED = re.compile(r"doi\.org/10/", re.IGNORECASE)

# CONTROL. Any bare short-form DOI anywhere. If this is also zero, the target's
# zero is a statement about the instrument and must be reported as unbounded.
_CONTROL = re.compile(rf"(?<![./\w]){_DOI_SHORT_FORM}", re.IGNORECASE)

HEADER_ZONE_LINES = 30  # H0's flat cap; the zone where the exemption matters


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20260912)
    args = ap.parse_args()

    papers = sampled_corpus(args.sample, args.seed)
    print(coverage_line())

    langs: Counter[str] = Counter()
    n_text = 0
    target_lines = target_papers = target_in_header = 0
    control_lines = control_papers = 0

    for key, path in papers:
        try:
            with open(path, "rb") as fh:
                res = extract_pdf(fh.read())
            # extract_pdf returns (text, meta) on this path; a returned TUPLE is
            # not the value, and `.strip()` on it fails loudly rather than
            # silently measuring nothing.
            raw = res[0] if isinstance(res, tuple) else res
        except Exception as exc:  # a failed READ is not a clean zero
            print(f"  ! could not extract {key}: {type(exc).__name__}", file=sys.stderr)
            continue
        if not raw.strip():
            print(f"  ! empty text layer, excluded: {key}", file=sys.stderr)
            continue

        lang, _counts = detect_language(raw)
        langs[lang] += 1
        if lang != "english":
            continue
        n_text += 1

        lines = raw.splitlines()
        header = {id(l) for l in [l for l in lines if l.strip()][:HEADER_ZONE_LINES]}
        hits = [l for l in lines if _TARGET.search(l) and not _HOSTED.search(l)]
        if hits:
            target_papers += 1
            target_lines += len(hits)
            target_in_header += sum(1 for l in hits if id(l) in header)
            for l in hits[:3]:
                print(f"  TARGET {key} | {l.strip()[:100]}")

        ctl = [l for l in lines if _CONTROL.search(l)]
        if ctl:
            control_papers += 1
            control_lines += len(ctl)

    excluded = {k: v for k, v in langs.items() if k != "english"}
    print(f"\nEnglish papers measured: {n_text}")
    print(f"Excluded (non-English), reported not dropped silently: {excluded or 'none'}")
    print(
        f"TARGET  `doi: 10/xxxx`, no doi.org host : "
        f"{target_lines} lines in {target_papers} papers "
        f"({target_in_header} inside the first {HEADER_ZONE_LINES} non-blank lines)"
    )
    print(
        f"CONTROL any bare short-form `10/xxxx`   : "
        f"{control_lines} lines in {control_papers} papers"
    )
    if control_lines == 0:
        print(
            "\nUNBOUNDED: the control did not fire either, so the target's zero "
            "is a claim about this scan and not about the corpus. Do not quote it."
        )
        return 2
    print(
        "\nThe control fired, so the target count is a property of the corpus. "
        "A zero target means the unification is INERT on real documents -- kept "
        "because it removes a duplicated grammar, not because the shape occurs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
