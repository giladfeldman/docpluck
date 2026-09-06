r"""Every corpus PDF a test names must RESOLVE, or be declared absent on purpose.

Written 2026-09-05 against the unfixed tree. RED as written: **seven** corpus references across
two test files resolve to nothing, and they are three different defects, not one.

    FOUR ARE FILENAME TYPOS -- the paper is on disk, hyphenated in the test, underscored on disk:
        chicago-ad/demography-5.pdf  -> chicago-ad/demography_5.pdf   (:479)
        asa/socius-4.pdf             -> asa/socius_4.pdf              (:494)
        ieee/ieee-access-7.pdf       -> ieee/ieee_access_7.pdf        (:512)
        nature/nat-comms-2.pdf       -> nature/nat_comms_2.pdf        (:528)

    TWO NAME A CORPUS SUBDIRECTORY THAT DOES NOT EXIST -- `test-pdfs/escicheck/`. Correcting a
        filename cannot fix these; see KNOWN_ABSENT.                  (:342, :363)

    ONE CAN NEVER RESOLVE BY CONSTRUCTION -- `Li&Feldman-2025-RSOS-...-print.pdf` in
        `test_sections_real_corpus.py:14` carries a literal `...` where the rest of the title
        was elided. No such file exists and none can.

`pytest.skip("... test PDF not available")` is TRUE in every case and reads as *the corpus is
incomplete*. For four of the seven it was not: the papers were on disk the whole time.

THE GENERAL RULE THIS ENCODES. **A name that does not resolve must fail LOUDLY.** An invented
filename matching nothing, a hyphenated filename matching nothing, an elided filename matching
nothing, and a strided sample that happens to contain no positives are one defect in four
costumes: an instrument reporting a clean result because it never looked.

KNOWN_ABSENT is a declaration, not a dumping ground -- a paper somebody decided not to hold, with
the decision recorded. Repointing a test at "the nearest similar file" is NOT a fix, and the two
entries there say why for each.

*(Written after the author's own first draft flagged synthetic fixture names and article-repository
DOIs as missing corpus papers. A gate noisy enough to be turned off is worth nothing, so the
scanner is scoped to corpus-helper calls only and asserts BOTH that it found enough and that it
found nothing synthetic.)*
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import PDF_PATHS

_TESTS = Path(__file__).resolve().parent
_CORPUS = Path(PDF_PATHS["docpluck"])

# Corpus references a test names that are NOT on this machine, each with the decision owed.
# Shrinks when a paper is re-acquired; never grows silently.
KNOWN_ABSENT: dict[str, str] = {
    # NOT typos. Both name a corpus subdirectory `escicheck/` that DOES NOT EXIST under
    # test-pdfs/ at all (which holds ama, aom, apa, asa, chicago-ad, docx, harvard, ieee,
    # nature, vancouver). A whole corpus slice is missing, so correcting a filename cannot
    # fix these.
    # An ELIDED literal: the filename itself contains `...` where the rest of the title was
    # cut. No such file exists and none can -- this can never resolve by construction.
    "Li&Feldman-2025-RSOS-...-print.pdf": (
        "DECISION OWED: recover the real filename and repoint `test_sections_real_corpus.py:14`, "
        "or retire that test. The three RSOS papers in harvard/ are NOT it (ar_royal_society_"
        "rsos_140066/140072/140081 -- different papers). Until then the test skips honestly."
    ),
    "escicheck/ip-feldman-2025-pspb-misestimation-of-emotional-experiences-print-nosupp.pdf": (
        "DECISION OWED. `apa/ip_feldman_2025_pspb.pdf` is on disk and is very likely the same "
        "paper -- it is the canary litmus paper, rendered on every commit -- but repointing a "
        "regression test at a differently-named file is a decision, not a typo fix, and would "
        "silently change what the test measures if the two differ. Confirm identity through "
        "article-finder, then repoint deliberately or retire."
    ),
    "escicheck/chandrashekar-et-al-2020-shafir-1993-replication-and-extensions-print-nosupp.pdf": (
        "DECISION OWED: re-acquire through article-finder, or retire the test that names it. "
        "`apa/chandrashekar_2023_mp.pdf` is NOT a substitute -- different year, journal and paper."
    ),
}

# A glob is not a name. `os.path.join(_TEST_PDFS, "*", "*.pdf")` is the corpus sweep in
# `test_normalize_idempotent_corpus`; asserting it "resolves" is meaningless.
_NOT_A_NAME = ("*",)

# SCOPE, and getting this wrong once is why it is spelled out. A bare `"*.pdf"` regex over
# tests/ also matches synthetic fixture names a test CREATES (`x.pdf`, `paper.pdf`, `nope.pdf`,
# `p.pdf`) and article-repository DOIs resolved through a different corpus key. Neither is a
# claim about the docpluck corpus, and asserting they resolve would make this gate noisy enough
# to be turned off -- which is how a gate dies. So only literals passed to the corpus HELPERS
# are scanned: `pdf_path("docpluck", ...)`, `pdf_available("docpluck", ...)` and
# `os.path.join(_TEST_PDFS, ...)`. Those are exactly the names that assert "this paper is in
# the corpus".
_CORPUS_CALL = re.compile(
    r'(?:pdf_path|pdf_available)\s*\(\s*"docpluck"\s*,(?P<args>[^)]*)\)'
    r'|os\.path\.join\(\s*_TEST_PDFS\s*,(?P<args2>[^)]*)\)',
    re.S,
)
_STR = re.compile(r'"([^"\n]+)"')


def _named_pdfs() -> dict[str, list[str]]:
    """{"<subdir>/<file>.pdf": ["test_file.py:line", ...]} for every corpus-helper call."""
    found: dict[str, list[str]] = {}
    for f in sorted(_TESTS.glob("test_*.py")):
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in _CORPUS_CALL.finditer(text):
            parts = _STR.findall(m.group("args") or m.group("args2") or "")
            if not parts or not parts[-1].endswith(".pdf"):
                continue
            lineno = text.count("\n", 0, m.start()) + 1
            found.setdefault("/".join(parts), []).append(f"{f.name}:{lineno}")
    return found


# The biggest version of "a path silently matched nothing" is the corpus ROOT moving. A scanner
# that only checks individual names would then report every path dead -- or, in a skip-based
# suite, produce 101 clean skips. Fail loudly on a missing root rather than reporting every
# name under it as dead.
_MIN_CORPUS_PDFS = 40  # the same floor `test_normalize_idempotent_corpus` uses


def test_the_corpus_root_resolves_and_is_not_empty():
    """Fail LOUDLY if the corpus moved -- never skip, and never report the names dead instead."""
    assert _CORPUS.is_dir(), (
        f"the docpluck corpus root does not resolve: {_CORPUS}. "
        "PDF_PATHS['docpluck'] in tests/conftest.py points somewhere that does not exist. Every "
        "per-paper test in this suite will SKIP, which reads as 'corpus incomplete' rather than "
        "'the corpus is gone'."
    )
    n = sum(1 for _ in _CORPUS.rglob("*.pdf"))
    assert n >= _MIN_CORPUS_PDFS, (
        f"the corpus root {_CORPUS} resolves but holds only {n} PDFs (floor {_MIN_CORPUS_PDFS}). "
        "A near-empty corpus makes every name-resolution result below meaningless."
    )


@pytest.fixture(scope="module")
def named() -> dict[str, list[str]]:
    if not _CORPUS.is_dir():
        pytest.skip(
            f"SKIPPED, NOT PASSED: the corpus at {_CORPUS} is absent, so no reference can be "
            "resolved. `test_the_corpus_root_resolves_and_is_not_empty` fails loudly for that "
            "case; this fixture's skip is the belt to its braces."
        )
    return _named_pdfs()


def test_the_scanner_actually_found_corpus_references(named):
    """CONTROL. A regex matching nothing would make every assertion below vacuous, and a regex
    matching too much would make this gate noisy enough to disable. Both sides are asserted."""
    assert len(named) >= 10, (
        f"only {len(named)} corpus-helper PDF references found across tests/ -- scanner broken"
    )
    assert any("demography" in n for n in named), (
        "the scanner did not see the demography reference it was written for"
    )
    assert not any(n.endswith(("/x.pdf", "/paper.pdf", "/nope.pdf", "/p.pdf")) for n in named), (
        "the scanner is picking up synthetic fixture names a test CREATES; those are not claims "
        "about the corpus and would make this gate noisy enough to be turned off"
    )


def test_every_corpus_pdf_a_test_names_resolves_on_disk(named):
    """RED FIRST 2026-09-05: six references resolved to nothing, five of them recoverable."""
    unresolved = {
        name: sites
        for name, sites in named.items()
        if name not in KNOWN_ABSENT
        and not any(t in name for t in _NOT_A_NAME)
        and not (_CORPUS / name).is_file()
    }
    assert not unresolved, (
        "tests name corpus PDFs that resolve to nothing -- each of these SKIPS silently and "
        "reads as 'corpus incomplete':\n"
        + "\n".join(f"  {n}  <- named at {', '.join(s)}" for n, s in sorted(unresolved.items()))
    )


def test_the_known_absent_list_has_not_rotted(named):
    """A paper since acquired must leave the list, or it hides a live gap behind a declaration."""
    stale = []
    for name in KNOWN_ABSENT:
        if (_CORPUS / name).is_file():
            stale.append(f"  {name}: now present on disk -- remove it from KNOWN_ABSENT")
        elif name not in named:
            stale.append(f"  {name}: no test names it any more -- remove it from KNOWN_ABSENT")
    assert not stale, "KNOWN_ABSENT is stale:\n" + "\n".join(stale)
