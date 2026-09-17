"""One extraction per document - the accept-precomputed parameters.

`/api/analyze` extracted the same upload more than once: its raw-text stage ran
`extract_pdf`, and `extract_pdf_structured` then ran it again, byte for byte,
on the same bytes; separately `render_pdf_to_markdown` and
`extract_pdf_structured` each opened the document with pdfplumber. Measured
2026-09-17 by COUNTING CALLS, not by reading the source - on
`10.1001/jamanetworkopen.2023.48333` through the /analyze call graph:

    pdftotext 6 -> 3    pdfplumber.open 6 -> 3    extract_pdf 2 -> 1

`_layout_doc` already existed on both `extract_pdf_structured` and
`render_pdf_to_markdown` and was simply never passed across the boundary -
docpluck-review rule 35, an accept-precomputed parameter that exists and is not
passed. `_raw_text` / `_page_count` are the pdftotext half of the same shape.

**Every count here is TWO-SIDED.** A counter that is not wired to the binding a
call actually uses reports zero and looks like a perfect saving, so each test
first shows the UNSHARED graph producing the higher number. A `from X import y`
binding is not updated by patching `X.y`, so the counter patches the definition
module *and* every module that imported the name.
"""

from __future__ import annotations

import io

import pytest

from docpluck.testing import require_corpus_pdf


# Camelot is not needed to count extractions, and skipping it keeps this module
# fast. Declarative - see conftest._camelot_disabled_per_module; a module-scope
# os.environ write leaks into every test collected afterwards.
DISABLE_CAMELOT = True


def _two_page_pdf() -> bytes:
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    for i in range(2):
        c.setFont("Helvetica-Bold", 14)
        c.drawString(72, 720, f"Section {i}")
        c.setFont("Helvetica", 11)
        c.drawString(72, 690, f"Body sentence unique to page {i}.")
        c.showPage()
    c.save()
    return buf.getvalue()


class _Counter:
    """Counts `extract_pdf` at EVERY live binding, and restores them all."""

    def __init__(self, monkeypatch):
        import docpluck
        import docpluck.extract as _ex
        import docpluck.extract_structured as _es
        import docpluck.render as _rd
        import docpluck.sections as _sec

        self.n = 0
        real = _ex.extract_pdf

        def counted(*a, **k):
            self.n += 1
            return real(*a, **k)

        # The definition module first, then every module that did
        # `from .extract import extract_pdf` at import time. Patching only the
        # first would leave those bindings pointing at the real function, and
        # this counter would read 0 on a graph that extracted twice.
        for mod in (_ex, _es, _rd, _sec, docpluck):
            if getattr(mod, "extract_pdf", None) is not None:
                monkeypatch.setattr(mod, "extract_pdf", counted, raising=False)


# -- extract_pdf_structured -------------------------------------------------

def test_structured_without_raw_text_extracts_once():
    """The control: no `_raw_text`, so the function extracts for itself."""
    from docpluck.extract_structured import extract_pdf_structured

    pdf = _two_page_pdf()
    with pytest.MonkeyPatch.context() as mp:
        c = _Counter(mp)
        extract_pdf_structured(pdf)
        assert c.n == 1


def test_structured_with_raw_text_does_not_extract_again():
    """Two-sided against the test above: 1 becomes 0, so the branch was reached."""
    from docpluck.extract import extract_pdf
    from docpluck.extract_structured import extract_pdf_structured

    pdf = _two_page_pdf()
    pair = extract_pdf(pdf)
    with pytest.MonkeyPatch.context() as mp:
        c = _Counter(mp)
        extract_pdf_structured(pdf, _raw_text=pair)
        assert c.n == 0


def test_structured_output_identical_with_and_without_raw_text():
    """The hard constraint: sharing must not change one byte of the output."""
    from docpluck.extract import extract_pdf, count_pages
    from docpluck.extract_structured import extract_pdf_structured

    pdf = require_corpus_pdf("apa/ziano_2021_joep.pdf").read_bytes()
    plain = extract_pdf_structured(pdf)
    shared = extract_pdf_structured(
        pdf, _raw_text=extract_pdf(pdf), _page_count=count_pages(pdf)
    )
    assert shared["text"] == plain["text"]
    assert shared["method"] == plain["method"]
    assert shared["page_count"] == plain["page_count"]
    assert [t.get("cells") for t in shared["tables"]] == [
        t.get("cells") for t in plain["tables"]
    ]
    assert [t.get("html") for t in shared["tables"]] == [
        t.get("html") for t in plain["tables"]
    ]
    assert [f.get("caption") for f in shared["figures"]] == [
        f.get("caption") for f in plain["figures"]
    ]


def test_page_count_is_taken_from_the_caller_when_given():
    from docpluck.extract_structured import extract_pdf_structured

    pdf = _two_page_pdf()
    assert extract_pdf_structured(pdf)["page_count"] == 2
    # A deliberately wrong value proves the argument is READ rather than
    # recomputed - a parameter accepted and then ignored is this repo's
    # longest-running defect shape.
    assert extract_pdf_structured(pdf, _page_count=99)["page_count"] == 99


def test_max_input_bytes_still_refuses_an_oversized_pdf_with_raw_text():
    """The cap lived inside the call `_raw_text` skips. It must not go with it."""
    from docpluck.extract import extract_pdf
    from docpluck.extract_structured import extract_pdf_structured

    pdf = _two_page_pdf()
    pair = extract_pdf(pdf)
    with pytest.raises(ValueError, match="max_input_bytes"):
        extract_pdf_structured(pdf, _raw_text=pair, max_input_bytes=10)


# -- extract_sections -------------------------------------------------------

def test_sections_with_raw_text_does_not_extract_again():
    from docpluck.extract import extract_pdf
    from docpluck.sections import extract_sections

    pdf = _two_page_pdf()
    pair = extract_pdf(pdf)
    with pytest.MonkeyPatch.context() as mp:
        c = _Counter(mp)
        extract_sections(pdf, source_format="pdf")
        assert c.n == 1, "control: the unshared call must extract once"
    with pytest.MonkeyPatch.context() as mp:
        c = _Counter(mp)
        extract_sections(pdf, source_format="pdf", _raw_text=pair)
        assert c.n == 0


def test_sections_output_identical_with_raw_text():
    from docpluck.extract import extract_pdf
    from docpluck.sections import extract_sections

    pdf = require_corpus_pdf("apa/ziano_2021_joep.pdf").read_bytes()
    plain = extract_sections(pdf, source_format="pdf")
    shared = extract_sections(pdf, source_format="pdf", _raw_text=extract_pdf(pdf))
    assert shared.normalized_text == plain.normalized_text
    assert [(s.label, s.char_start, s.char_end) for s in shared.sections] == [
        (s.label, s.char_start, s.char_end) for s in plain.sections
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(text="body text", source_format="pdf"),
        dict(file_bytes=b"<html><body><h1>H</h1><p>p</p></body></html>",
             source_format="html"),
    ],
)
def test_sections_refuses_raw_text_where_it_would_do_nothing(kwargs):
    """Refused, not ignored - an accepted no-op argument is the defect itself."""
    from docpluck.sections import extract_sections

    with pytest.raises(ValueError, match="_raw_text"):
        extract_sections(_raw_text=("t", "m"), **kwargs)


# -- render_pdf_to_markdown -------------------------------------------------

def _render_without_sharing(mp, pdf):
    """Reproduce the pre-2026-09-17 render: same code, sharing discarded."""
    import docpluck.render as rd

    real_struct, real_sections = rd.extract_pdf_structured, rd.extract_sections

    def drop_struct(b, **k):
        k.pop("_raw_text", None)
        k.pop("_page_count", None)
        return real_struct(b, **k)

    def drop_sections(b=None, **k):
        k.pop("_raw_text", None)
        return real_sections(b, **k)

    mp.setattr(rd, "extract_pdf_structured", drop_struct)
    mp.setattr(rd, "extract_sections", drop_sections)
    return rd.render_pdf_to_markdown(pdf)


def test_bare_render_runs_one_extraction_and_threads_it_to_both_callees():
    """`extract_pdf_structured` and `extract_sections` each ran pdftotext.

    Measured on a checkout of 29acfb9 without this change: a bare
    `render_pdf_to_markdown(pdf_bytes)` called `extract_pdf` **twice**; it now
    calls it once.

    THE OBVIOUS CONTROL IS NOT AVAILABLE HERE, and saying so is cheaper than a
    control that lies. Re-running this render with the sharing stripped out of
    the two callees does not reproduce the old behaviour: render still
    evaluates the shared pair to build the argument, the stripped callee then
    extracts anyway, and the count reads 3 - one MORE than the defect it is
    supposed to represent. So this pins the two halves that are directly
    observable instead: exactly one extraction happens, and both callees are
    handed it. Each callee's own "handed it -> does not extract" step is
    two-sided in its own test above.
    """
    import docpluck.render as rd
    from docpluck.render import render_pdf_to_markdown

    pdf = _two_page_pdf()
    seen: dict[str, object] = {}

    with pytest.MonkeyPatch.context() as mp:
        real_struct, real_sections = rd.extract_pdf_structured, rd.extract_sections

        def spy_struct(b, **k):
            seen["structured"] = k.get("_raw_text")
            return real_struct(b, **k)

        def spy_sections(b=None, **k):
            seen["sections"] = k.get("_raw_text")
            return real_sections(b, **k)

        mp.setattr(rd, "extract_pdf_structured", spy_struct)
        mp.setattr(rd, "extract_sections", spy_sections)
        c = _Counter(mp)
        render_pdf_to_markdown(pdf)

    assert c.n == 1
    assert seen["structured"] is not None, "structured was not handed the pair"
    assert seen["sections"] is not None, "sections was not handed the pair"
    # The same object, not two equal-looking ones: that is what makes it one
    # extraction rather than two that happen to agree.
    assert seen["structured"] is seen["sections"]


def test_render_output_unchanged_by_the_shared_extraction():
    """A real paper, both arms, byte-for-byte."""
    from docpluck.render import render_pdf_to_markdown

    pdf = require_corpus_pdf("apa/ziano_2021_joep.pdf").read_bytes()
    shared = render_pdf_to_markdown(pdf)
    with pytest.MonkeyPatch.context() as mp:
        unshared = _render_without_sharing(mp, pdf)
    assert shared == unshared


def test_render_given_both_precomputed_results_extracts_nothing():
    """The lazy pair: a render handed `_structured` AND `_sectioned` must not
    pay for an extraction neither of them will read."""
    from docpluck.extract_structured import extract_pdf_structured
    from docpluck.render import render_pdf_to_markdown
    from docpluck.sections import extract_sections

    pdf = _two_page_pdf()
    st = extract_pdf_structured(pdf)
    doc = extract_sections(pdf, source_format="pdf")
    with pytest.MonkeyPatch.context() as mp:
        c = _Counter(mp)
        render_pdf_to_markdown(pdf, _structured=st, _sectioned=doc)
        assert c.n == 0


# -- the three remaining call sites found in the same pass --------------------

def test_extract_pdf_with_sections_filter_extracts_once():
    """`extract_pdf(blob, sections=[...])` re-ran the extraction it just made.

    The `sections=` branch called `extract_sections(pdf_bytes)`, which calls
    `extract_pdf` with these same default arguments - so the filtered form cost
    two pdftotext runs where the unfiltered form costs one. Reachable from the
    CLI (`docpluck extract --sections abstract`) and from any library consumer
    using the filter.
    """
    # THROUGH THE MODULE, not through a name bound before the patch. A
    # `from docpluck.extract import extract_pdf` at the top of this function
    # captures the REAL function, so the outermost call would bypass the
    # counter and the control would read 0 while looking like a saving. That
    # is the same binding trap this module's docstring describes, and it
    # caught itself here.
    import docpluck.extract as _ex

    pdf = _two_page_pdf()
    with pytest.MonkeyPatch.context() as mp:
        c = _Counter(mp)
        _ex.extract_pdf(pdf)
        assert c.n == 1, "control: the unfiltered form extracts once"
    with pytest.MonkeyPatch.context() as mp:
        c = _Counter(mp)
        _ex.extract_pdf(pdf, sections=["abstract"])
        assert c.n == 1

    # The two-sided half, and it IS available here: dropping `_raw_text` on the
    # way into extract_sections restores exactly the old behaviour, because
    # extract_pdf's own call is unaffected by that wrapper.
    with pytest.MonkeyPatch.context() as mp:
        import docpluck.sections as _sec

        real = _sec.extract_sections

        def drop(b=None, **k):
            k.pop("_raw_text", None)
            return real(b, **k)

        mp.setattr(_sec, "extract_sections", drop)
        c = _Counter(mp)
        _ex.extract_pdf(pdf, sections=["abstract"])
        assert c.n == 2, "control: without sharing the filter costs two extractions"


def test_extract_pdf_sections_filter_output_unchanged():
    """The filtered text must be what the re-extracting version produced."""
    import docpluck.sections as sec
    from docpluck.extract import extract_pdf

    pdf = require_corpus_pdf("apa/ziano_2021_joep.pdf").read_bytes()
    shared, m1 = extract_pdf(pdf, sections=["abstract", "results"])

    with pytest.MonkeyPatch.context() as mp:
        real = sec.extract_sections

        def drop(b=None, **k):
            k.pop("_raw_text", None)
            return real(b, **k)

        mp.setattr(sec, "extract_sections", drop)
        unshared, m2 = extract_pdf(pdf, sections=["abstract", "results"])

    assert shared == unshared
    assert m1 == m2


def test_render_accepts_a_caller_supplied_pair():
    """`_raw_text` on the render seeds the one extraction it would make."""
    from docpluck.extract import extract_pdf
    from docpluck.render import render_pdf_to_markdown

    pdf = _two_page_pdf()
    pair = extract_pdf(pdf)
    with pytest.MonkeyPatch.context() as mp:
        c = _Counter(mp)
        render_pdf_to_markdown(pdf, _raw_text=pair)
        assert c.n == 0, "the render must not extract when handed the pair"


def test_render_output_identical_when_handed_the_pair():
    from docpluck.extract import extract_pdf
    from docpluck.render import render_pdf_to_markdown

    pdf = require_corpus_pdf("apa/ziano_2021_joep.pdf").read_bytes()
    assert render_pdf_to_markdown(pdf) == render_pdf_to_markdown(
        pdf, _raw_text=extract_pdf(pdf)
    )


def test_cli_render_with_tables_jsonl_extracts_and_parses_once(tmp_path):
    """The CLI's --tables-jsonl branch paid for two extractions and two parses.

    Two-sided on BOTH counters: the plain render branch is the control, and it
    is the SAME command with one flag removed.
    """
    import pdfplumber

    from docpluck import cli

    pdf = _two_page_pdf()
    src = tmp_path / "paper.pdf"
    src.write_bytes(pdf)

    def run(argv):
        opens = {"n": 0}
        with pytest.MonkeyPatch.context() as mp:
            real_open = pdfplumber.open

            def counted_open(*a, **k):
                opens["n"] += 1
                return real_open(*a, **k)

            mp.setattr(pdfplumber, "open", counted_open)
            c = _Counter(mp)
            cli.main(argv)
            return c.n, opens["n"]

    plain_extracts, plain_opens = run(["render", str(src)])
    jsonl_extracts, jsonl_opens = run(
        ["render", str(src), "--tables-jsonl", str(tmp_path / "t.jsonl")]
    )

    assert plain_extracts == 1
    assert jsonl_extracts == 1, "the sidecar flag must not buy a second pdftotext"
    assert jsonl_opens <= plain_opens, (
        f"the sidecar flag must not buy extra pdfplumber parses "
        f"({jsonl_opens} vs {plain_opens})"
    )
    assert (tmp_path / "t.jsonl").exists()
