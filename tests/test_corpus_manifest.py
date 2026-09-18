r"""Every corpus paper a test names must RESOLVE IN CUSTODY -- and it must be the right paper.

This replaces ``test_every_named_test_pdf_resolves.py``, which asked the same
question of a sibling DIRECTORY that no longer exists. What it was written to
catch is unchanged and is restated here because it is the whole point:

    A NAME THAT DOES NOT RESOLVE MUST FAIL LOUDLY. An invented filename matching
    nothing, a hyphenated filename matching nothing, an elided filename matching
    nothing, and a strided sample that happens to contain no positives are one
    defect in four costumes: an instrument reporting a clean result because it
    never looked.

THREE THINGS CHANGED ON 2026-09-17, AND THE THIRD IS NEW COVERAGE
-----------------------------------------------------------------
1. Resolution is by DOI through the article custodian, so the scanner looks for
   ``corpus_pdf("...")`` / ``require_corpus_pdf("...")`` literals rather than
   three different directory-rooted spellings. The old scanner covered two of
   the six shapes then in the tree; the other four were invisible to it.

2. ``KNOWN_ABSENT`` is gone, and its three entries are resolved rather than
   declared. Two named an ``escicheck/`` subdirectory that never existed under
   the corpus at all; the third,
   ``Li&Feldman-2025-RSOS-...-print.pdf``, carried a literal ``...`` where the
   rest of the title had been elided, so it could never resolve by construction.
   None of the three is named by any test after the repoint, so a list declaring
   them absent would now be a list about nothing.

3. **The bytes are checked, not just the existence.** A DOI key pointing at the
   WRONG paper reads as present to every existence check there is, and this
   repository has held a wrong PDF under a correct DOI before. Three of the 101
   papers are SECONDARY manifestations -- the custodian holds two distinct files
   under one DOI, and the tests were calibrated against the second. Resolving
   those by DOI alone would silently hand the suite different bytes and shift
   layout assertions for a reason nobody could trace.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from docpluck.testing.corpus import (
    MANIFEST,
    corpus_available,
    corpus_names,
    repository_root,
    verify_manifest,
)

_TESTS = Path(__file__).resolve().parent

# Only literals handed to the corpus resolvers are scanned. Getting this wrong
# once is why it is spelled out: a bare `"*.pdf"` regex over tests/ also matches
# synthetic fixture names a test CREATES (`x.pdf`, `paper.pdf`, `nope.pdf`) and
# article-repository DOIs resolved through a different helper. Neither is a claim
# about this corpus, and asserting they resolve would make this gate noisy enough
# to be turned off -- which is how a gate dies.
_CORPUS_CALL = re.compile(r'\b(?:require_)?corpus_pdf\(\s*"([^"\n]+)"\s*\)')

# Floors below which "every name resolved" stops meaning anything. MEASURED
# 2026-09-17 immediately after the repoint, not guessed: 111 resolver call sites
# naming 22 distinct papers. A first draft put the name floor at 40 and this gate
# failed against a correct tree -- the same corpus is named by many files, so the
# count that moves when coverage is lost is the CALL SITES, not the distinct names.
_MIN_CALL_SITES = 90
_MIN_NAMES = 18
_MIN_MANIFEST = 90


def _call_site_count() -> int:
    """Every resolver call, literal-named or not -- the number that drops when
    a file stops using the corpus."""
    pat = re.compile(r"\b(?:require_)?corpus_pdf(?:s)?\(")
    return sum(
        len(pat.findall(f.read_text(encoding="utf-8", errors="replace")))
        for f in sorted(_TESTS.glob("test_*.py"))
        if f.name != Path(__file__).name
    )


def _named() -> dict[str, list[str]]:
    """{corpus-relative name: ["test_file.py:line", ...]} for every resolver call."""
    found: dict[str, list[str]] = {}
    for f in sorted(_TESTS.glob("test_*.py")):
        if f.name == Path(__file__).name:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for m in _CORPUS_CALL.finditer(text):
            lineno = text.count("\n", 0, m.start()) + 1
            # A COMMENT IS NOT A CALL. A retirement note showing the correct form
            # made this gate demand that the placeholder in the example be a real
            # paper -- the kind of false positive that gets a gate switched off,
            # which the gate this replaced warned about in as many words. Only
            # executable lines assert that a paper is in the corpus.
            if lines[lineno - 1].lstrip().startswith("#"):
                continue
            found.setdefault(m.group(1), []).append(f"{f.name}:{lineno}")
    return found


@pytest.fixture(scope="module")
def named() -> dict[str, list[str]]:
    return _named()


# ---------------------------------------------------------------------------
# Controls first. A gate whose instrument is broken reports a clean corpus.
# ---------------------------------------------------------------------------

def test_the_scanner_actually_found_corpus_references(named):
    """Two-sided. A regex matching nothing makes every assertion below vacuous;
    a regex matching too much makes this gate noisy enough to disable."""
    sites = _call_site_count()
    assert sites >= _MIN_CALL_SITES, (
        f"only {sites} corpus resolver call sites across tests/ (floor "
        f"{_MIN_CALL_SITES}) -- the suite has stopped reading the corpus, or the "
        "scanner is broken. Either way every assertion below is vacuous."
    )
    assert len(named) >= _MIN_NAMES, (
        f"only {len(named)} distinct papers named across tests/ (floor {_MIN_NAMES})"
    )
    assert any("efendic_2022_affect" in n for n in named), (
        "the scanner did not see the efendic reference, which is named by more test "
        "files than any other paper in the corpus"
    )
    synthetic = [n for n in named if n in {"x.pdf", "paper.pdf", "nope.pdf", "p.pdf"}]
    assert not synthetic, (
        f"the scanner is picking up synthetic fixture names a test CREATES: {synthetic}. "
        "Those are not claims about the corpus."
    )


def test_the_manifest_is_not_a_stub():
    """The denominator is committed; assert it is the size it should be.

    Without this, a manifest emptied by a bad regeneration would make
    'every name resolves' true and meaningless.
    """
    assert len(MANIFEST) >= _MIN_MANIFEST, (
        f"the corpus manifest holds only {len(MANIFEST)} papers (floor {_MIN_MANIFEST}). "
        "Regenerate it with `python -m docpluck.testing.regenerate <paths>` and read "
        "the diff -- a corpus does not shrink by accident."
    )
    for rel, entry in MANIFEST.items():
        assert entry.get("doi", "").startswith("10."), f"{rel}: no DOI recorded"
        assert entry.get("held_at", "").startswith("fulltext/"), f"{rel}: no custody path"
        assert len(entry.get("sha256", "")) == 64, f"{rel}: no sha256"


def test_the_custodian_is_reachable():
    """Fail LOUDLY when the article repository is absent -- never skip.

    User directive 2026-09-17: "tests should fail when the folder's missing, so
    that test should be corrected." Before the repoint an absent corpus produced
    101 clean skips and a green run, which reads as 'the corpus is incomplete'
    rather than 'nothing was tested'.
    """
    assert corpus_available(), (
        "the article repository is not on this machine, so NOTHING in the "
        "corpus-backed suite actually ran against a paper. Set ARTICLE_REPOSITORY "
        "to its location (or VIBE_ROOT to the portfolio root). This is a failure "
        "rather than a skip on purpose: a skip here reported success for a suite "
        f"that read nothing. Looked for: {repository_root()}"
    )


# ---------------------------------------------------------------------------
# The gate itself.
# ---------------------------------------------------------------------------

def test_every_corpus_paper_a_test_names_is_in_the_manifest(named):
    """A name the suite asks for that the custodian does not hold is a FAILURE."""
    unknown = {n: s for n, s in named.items() if n not in MANIFEST}
    assert not unknown, (
        "tests name papers that are in no manifest entry -- each one used to SKIP "
        "silently and read as 'corpus incomplete':\n"
        + "\n".join(f"  {n}  <- named at {', '.join(s)}" for n, s in sorted(unknown.items()))
        + "\n\nEither the name is wrong, or the paper must be ingested through "
        "article-finder and the manifest regenerated."
    )


def test_every_manifest_paper_resolves_and_its_bytes_are_right():
    """Existence AND content. The second half is the one that catches a wrong paper."""
    problems = verify_manifest(check_bytes=True)
    assert not problems, (
        f"{len(problems)} of {len(MANIFEST)} corpus papers did not check out:\n"
        + "\n".join("  " + p for p in problems)
    )


def test_the_manifest_has_no_paper_no_test_and_no_sweep_uses():
    """Report, do not fail, on manifest entries nothing names individually.

    Most of the 101 are read only by corpus-wide sweeps (``corpus_pdfs()``), which
    is legitimate -- so this cannot be an assertion without deleting the sweeps'
    denominator. It prints instead, so a reader can see how much of the corpus is
    exercised by name.
    """
    named = set(_named())
    unnamed = [n for n in corpus_names() if n not in named]
    print(
        f"\ncorpus: {len(MANIFEST)} papers; {len(named)} named by a test directly; "
        f"{len(unnamed)} reached only through corpus-wide sweeps."
    )


def test_the_manifest_carries_identifiers_only_and_no_publication_text():
    """The manifest is COMMITTED to a PUBLIC repo. Identifiers only.

    A DOI, a custodian-relative path and a sha256 name a paper; they are not the
    paper. Prose, titles, abstracts or excerpts would be publication text in a
    project repository, which the custody rule forbids outright -- and a
    generated file is exactly where it would go unnoticed, because everyone
    reads it as metadata. This project has already had 984 KB of article body
    sit on the public remote for three months inside files that looked like
    ordinary fixtures.

    Written as a shape check rather than a word denylist, for the same reason:
    the leaked files were named like fixtures, so three filename-based cleanups
    walked past them.
    """
    doi_re = re.compile(r"10\.[0-9]{4,9}/\S+")
    held_re = re.compile(r"fulltext/[^/]+\.pdf")
    sha_re = re.compile(r"[0-9a-f]{64}")
    name_re = re.compile(r"[a-z0-9\-]+/[A-Za-z0-9_.\-]+\.pdf")

    offenders = []
    for rel, entry in MANIFEST.items():
        extra = set(entry) - {"doi", "held_at", "sha256"}
        if extra:
            offenders.append(f"{rel}: unexpected field(s) {sorted(extra)}")
        if not name_re.fullmatch(rel):
            offenders.append(f"{rel}: not a plain corpus filename")
        if not doi_re.fullmatch(entry.get("doi", "")):
            offenders.append(f"{rel}: doi is not a bare DOI")
        if not held_re.fullmatch(entry.get("held_at", "")):
            offenders.append(f"{rel}: held_at is not a bare custody path")
        if not sha_re.fullmatch(entry.get("sha256", "")):
            offenders.append(f"{rel}: sha256 is not 64 hex characters")
    assert not offenders, (
        "the corpus manifest carries something that is not an identifier -- this "
        "file is committed to a PUBLIC repository:\n" + "\n".join("  " + o for o in offenders)
    )


def test_a_sweep_over_an_unknown_subdirectory_raises_rather_than_returning_empty():
    """CONTROL on the resolver itself, not on the corpus.

    `corpus_pdfs("apa")` is how the corpus-wide sweeps get their denominator. A
    typo in that string used to return `[]`, and a sweep over nothing reports
    "0 failures out of 0" as a pass -- the same silent-empty defect the whole
    repoint exists to remove, reintroduced one layer up.
    """
    from docpluck.testing.corpus import CorpusPaperMissing, corpus_pdfs

    with pytest.raises(CorpusPaperMissing):
        corpus_pdfs("apa-typo-that-matches-nothing")

    # ... and the positive half, so this is not just asserting that some string
    # fails: a real subdirectory still returns papers.
    assert len(corpus_pdfs("apa")) > 10


def test_no_test_skips_on_whether_a_corpus_paper_EXISTS():
    """A corpus paper that does not resolve must FAIL. Asserted, not trusted.

    Four sites in `test_single_column_subsection_promote_real_pdf.py` survived
    the 2026-09-17 repoint still carrying
    `@pytest.mark.skipif(not <corpus_pdf(...)>.exists(), ...)`. They called the
    new resolver, so they did not look stale -- and then re-imposed exactly the
    semantics the repoint removed: with the custodian PRESENT and the paper
    unresolvable, the test skipped and the run stayed green. One of the two
    papers is `ip_feldman_2025_pspb.pdf`, a byte-variant, which is where a silent
    skip would be hardest to notice.

    They were found by a reviewer's grep. A check that can be a test must be a
    test, or the next one is found the same way or not at all.
    """
    # A BALANCED-PAREN SCAN, not one regex. The first draft of this gate was
    # `skipif\([^)]*?corpus_pdf\(...` and reported CLEAN against the four sites it
    # was written for: `[^)]*` cannot cross the `)` that closes `corpus_pdf(...)`,
    # so it matched the single-line spelling and missed the multi-line one -- and
    # multi-line is the spelling that was actually in the tree. Caught by running
    # the pattern against both forms before trusting it, which is the only reason
    # this gate is not another instrument reporting a clean result for a corpus it
    # never looked at.
    offenders = []
    for f in sorted(_TESTS.glob("test_*.py")):
        if f.name == Path(__file__).name:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"skipif\(", text):
            depth, i, n = 1, m.end(), len(text)
            while i < n and depth:
                if text[i] == "(":
                    depth += 1
                elif text[i] == ")":
                    depth -= 1
                i += 1
            call = text[m.end():i]
            if re.search(r"\b(?:require_)?corpus_pdf\(", call) and re.search(
                r"\.(?:exists|is_file)\(\)", call
            ):
                offenders.append(f"  {f.name}:{text.count(chr(10), 0, m.start()) + 1}")
    assert not offenders, (
        "these tests skip on whether a corpus paper exists, which is the silent "
        "green the repoint removed -- call `require_corpus_pdf(...)` in the test "
        "body instead:\n" + "\n".join(offenders)
    )
