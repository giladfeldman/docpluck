r"""G5c2 must not glue a stray number onto a heading that already has one. RED as written.

`G5c2_split_numbered_heading_rejoin` (`_rejoin_split_numbered_headings`, B5, 2026-05-22)
rejoins a section heading whose leading number pdftotext linearised onto its own line::

    6.
                    ->   6. References
    References

Correct, and it fires on pass 1. **Its output is then eligible as its own input.** On pass 2
the rejoined `6. References` is no longer a BARE orphan number, so the "don't consume two
stacked orphans" guard does not see it -- and `lookup_canonical_label` strips a single leading
number, so `6. References` still resolves to `SectionLabel.references` and qualifies as a
target. A stray `3.` sitting above it is then glued on::

    3.
                    ->   3. 6. References
    6. References

A heading cannot have two numbers. This is the entire remaining content of the corpus
idempotency gate: measured 2026-09-08, ALL FOUR still-non-idempotent papers are this one shape
and nothing else, `steps_changed == ['G5c2_split_numbered_heading_rejoin']` in every case.

    efendic_2022_affect   3.  +  6. References          -> 3. 6. References
    am_sociol_rev_4       1.  +  2. Acknowledgments     -> 1. 2. Acknowledgments
                          3.  +  4. Funding             -> 3. 4. Funding
    nat_comms_3          16.  + 17. Code availability   -> 16. 17. Code availability
    bmc_med_4             8.  +  9. Funding             -> 8. 9. Funding
                         22.  + 23. References          -> 22. 23. References

## Not cosmetic: the heading stops resolving

    lookup_canonical_label("6. References")     -> SectionLabel.references
    lookup_canonical_label("3. 6. References")  -> None

So the second pass does not merely add a wrong number -- it destroys the heading's
resolvability, and the section partitioner loses the section. Digit COUNTS are identical
across all four papers, which is exactly why a digit-delta check could never have found this:
*look at WHAT moved, not how much.*

## The fix is idempotence by construction, not a special case

The guard refuses a target line that ALREADY CARRIES ITS OWN LEADING NUMBER. That is keyed on
a structural signature -- `N. <text>` -- never on a paper, a publisher or a heading word, and
it makes the rule's own output ineligible as its own input, which is what idempotency means
here. The pre-existing guard checked only for a BARE stacked orphan (`^N.$`) and so could
never see a line the rule had itself just produced.

## THE DOTLESS CASE: RAISED, MEASURED, AND DELIBERATELY NOT FIXED

Sol (openai seat, three-provider consult round 2026-09-09, which returned 0 findings from all
three) observed that the guard requires the dot, so a journal numbering headings WITHOUT one
(`6 References`) can still stack: `3.` + `6 References` -> `3. 6 References`. It reproduces --
on a CONSTRUCTED string.

Measured before acting on it, over the 101-paper corpus, pass 1:

    papers with a DOTLESS stacked heading (Sol's case)      0
    papers with a DOTTED  stacked heading (this guard)      0   <- the fix working
    papers with the raw PRECONDITION for the dotless case   3

**The zero is a real zero, not a broken search.** Both detectors were fired against known
positives first: the dotted pattern matches `3. 6. References` and `16. 17. Code availability`
(measured pre-fix outputs), the dotless pattern matches `3. 6 References` and
`3. 1 Introduction`, and neither matches the correct forms `6. References` or `2.1. Methods`.
The precondition arm finding 3 papers is the second control: the pipeline is not silent there,
those three simply never resolve to a canonical label, so G5c2 declines.

So the guard STAYS NARROW. A rule with no observed input in real English articles is pure
false-positive surface for no measured benefit, and widening `\.` to `\.?` would start
refusing rejoins whose heading text legitimately begins with a number and a space. This is
recorded rather than left implicit so the next reader does not re-derive it: the case is
KNOWN, the denominator is 101, and the answer was zero.

## ASSERTED THROUGH THE SHIPPED PATH

Everything goes through `normalize_text`. `_rejoin_split_numbered_headings` is still wired --
this rule is being GUARDED, not retired -- so a raw-function test would be legitimate here;
the shipped path is used anyway because it is the only thing that proves the guard survives
the full step ordering, and G5c2 runs LAST in `academic` precisely so it sees settled text.
"""

from __future__ import annotations

import functools
import re

import pytest

from docpluck.extract import extract_pdf
from docpluck.normalize import NormalizationLevel, normalize_text
from docpluck.sections.taxonomy import lookup_canonical_label
from tests.conftest import pdf_available, pdf_path

# `N. M. Heading` -- two numbers stacked on ONE line. No section heading in any numbering
# convention carries two independent numbers separated by a space.
#
# THE SEPARATOR IS `[ \t]`, NEVER `\s`. The first draft of this pattern used `\s+`, which
# matches a NEWLINE, so under `re.MULTILINE` it happily spanned the three separate lines
# `3.` / blank / `6. References` -- the very layout that is CORRECT here -- and reported a
# stacked heading on a paper the fix had already repaired. An over-broad instrument reads
# exactly like a failed fix. Caught only because the specific-form assertion beside it
# passed while this one failed, which is what a two-sided check is for.
_STACKED_HEADING_NUMBERS = re.compile(
    r"^[ \t]*\d{1,2}(?:\.\d{1,2}){0,3}\.[ \t]+\d{1,2}(?:\.\d{1,2}){0,3}\.[ \t]+[^\W\d_]",
    re.MULTILINE,
)

# (corpus, filename, the exact stacked forms measured on 2026-09-08)
_PAPERS = [
    ("apa", "efendic_2022_affect.pdf", ["3. 6. References"]),
    ("asa", "am_sociol_rev_4.pdf", ["1. 2. Acknowledgments", "3. 4. Funding"]),
    ("nature", "nat_comms_3.pdf", ["16. 17. Code availability"]),
    ("vancouver", "bmc_med_4.pdf", ["8. 9. Funding", "22. 23. References"]),
]


def test_the_detector_fires_on_the_measured_positives_and_not_on_the_correct_layout():
    """THE INSTRUMENT IS A SHIPPED COMPONENT OF THIS FILE, so it is tested too.

    A zero from `_STACKED_HEADING_NUMBERS` over a corpus is a claim about the regex until a
    known positive proves it fires. Every string below is a form MEASURED on a real paper on
    2026-09-08, not an invention -- the positives are what pass 2 produced before the fix, the
    negatives are the correct pass-1 layout the fix preserves.

    The first draft of this pattern used `\\s+` as the separator, which matches a newline, so
    under `re.MULTILINE` it spanned `3.` / blank / `6. References` -- three correct lines --
    and reported a defect on a repaired paper. It ran as an over-broad instrument for exactly
    one test run, and the negative cases below are what would have caught it immediately.
    """
    for positive in (
        "3. 6. References",
        "1. 2. Acknowledgments",
        "3. 4. Funding",
        "16. 17. Code availability",
        "8. 9. Funding",
        "22. 23. References",
    ):
        assert _STACKED_HEADING_NUMBERS.search(positive), (
            f"the detector no longer matches {positive!r} -- a measured pre-fix output. "
            "A regex that stopped firing would make every corpus assertion in this file "
            "pass vacuously."
        )
    for negative in (
        "3.\n\n6. References",       # the CORRECT layout: two separate lines, one blank between
        "6. References",             # G5c2's own correct pass-1 output
        "2.1. Methods",              # an ordinary sub-numbered heading
        "1. 2. 3.",                  # bare numbers -- a heading's text begins with a LETTER,
                                 # which is why the pattern ends `[^\W\d_]` and not `\S`.
                                 # With `\S` this case matched, and a run of stacked list
                                 # numbers would have been reported as a stacked heading.
        "In 2019, 15. 20. of cases",  # prose, not at a line start
    ):
        assert not _STACKED_HEADING_NUMBERS.search(negative), (
            f"the detector fires on {negative!r}, which is not a stacked heading"
        )


@functools.lru_cache(maxsize=None)
def _norm_twice(corpus: str, name: str) -> tuple[str, str]:
    # Cached: three tests x four papers is twelve extract-plus-two-normalize runs of the
    # same four PDFs, and each is seconds. The cache is keyed on the inputs and the
    # pipeline is pure, so this changes timing only.
    if not pdf_available("docpluck", corpus, name):
        pytest.skip(
            f"SKIPPED, NOT PASSED: {corpus}/{name} absent from the local corpus. "
            "Read a skip here as a check that did not run."
        )
    with open(pdf_path("docpluck", corpus, name), "rb") as fh:
        raw, _ = extract_pdf(fh.read())
    assert raw and len(raw) > 20000, f"{name}: extraction returned {len(raw or '')} chars -- vacuous"
    once, _ = normalize_text(raw, NormalizationLevel.academic)
    twice, _ = normalize_text(once, NormalizationLevel.academic)
    return once, twice


@pytest.mark.parametrize("corpus,name,stacked", _PAPERS)
def test_g5c2_does_not_stack_two_heading_numbers(corpus, name, stacked):
    """The measured shape, per paper, named. Real documents -- no constructed strings."""
    once, twice = _norm_twice(corpus, name)
    for form in stacked:
        assert form not in twice, (
            f"{name}: re-normalization produced {form!r} -- G5c2 glued a stray number onto a "
            f"heading that already had one. `lookup_canonical_label({form!r})` is "
            f"{lookup_canonical_label(form)!r}, so the section partitioner loses the heading."
        )
    found = _STACKED_HEADING_NUMBERS.findall(twice)
    assert not found, f"{name}: stacked heading numbers survive: {found[:4]}"


@pytest.mark.parametrize("corpus,name,stacked", _PAPERS)
def test_g5c2_leaves_these_papers_idempotent(corpus, name, stacked):
    """The corpus gate's own invariant, per paper. These four are the entire remaining
    content of `test_normalize_idempotent_corpus` at ratchet 0."""
    once, twice = _norm_twice(corpus, name)
    assert once == twice, (
        f"{name}: normalize_text is not idempotent. Every difference measured on this paper "
        f"came from G5c2 re-consuming its own output."
    )


@pytest.mark.parametrize("corpus,name,stacked", _PAPERS)
def test_the_headings_g5c2_correctly_rejoined_are_still_rejoined(corpus, name, stacked):
    """THE CONTROL. G5c2 is being GUARDED, not retired -- so its pass-1 work must survive.
    Each stacked form above is `<stray>. <real number>. <Heading>`; the real heading is the
    part after the first number, and it must still be present, numbered, and resolvable.

    Without this, "make `_rejoin_split_numbered_headings` a no-op" would turn the file green
    while deleting a repair the corpus needs -- the wrong-direction fixture this project has
    been bitten by before.
    """
    once, _twice = _norm_twice(corpus, name)
    for form in stacked:
        real = form.split(". ", 1)[1]  # "3. 6. References" -> "6. References"
        assert real in once, (
            f"{name}: {real!r} is not in the pass-1 output -- G5c2's correct rejoin was lost. "
            "The guard must refuse a SECOND number, not the first."
        )
        assert lookup_canonical_label(real) is not None, (
            f"{name}: {real!r} no longer resolves to a canonical section label"
        )
