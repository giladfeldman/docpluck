"""The render keeps every uncaptioned candidate that `tables` keeps.

Why this file exists (2026-09-25). `_strip_phantom_camelot_tables` deleted the
<table> of kept uncaptioned candidates in the render while `tables` and
`flattened_rows` still carried every cell -- three channels, two answers. Found by
the 2.4.145 release gate (tools/diag/render_deletion_scan.py, docpluck-qa check
3c) on 10.1017/s0007123424000024 p10: candidate u2 is a real 127-cell
literature-review table whose <th> absorbed one line of body prose, and the
render was left with an empty "### Uncaptioned candidate u2" heading.

Whether a candidate is kept is decided once, at the keep step in
extract_structured (recorded there). The render step no longer overrules it.
"""

import re

import pytest

from docpluck import render as R
from docpluck.render import render_pdf_to_markdown
from docpluck.testing import require_corpus_pdf

# A phantom-shaped block the stripper deletes (masthead <th>, section-name <td>) --
# the same block `test_render_never_deletes_published_statistics` pins as
# "still stripped", from 10.1001/jamanetworkopen.2023.48333.
_PHANTOM = (
    "<table><thead><tr><th>JAMA Network Open | Public Health</th></tr></thead>"
    "<tbody><tr><td>Discussion</td></tr></tbody></table>\n"
)


def _doc(*parts: str) -> str:
    return "\n".join(parts)


def test_a_phantom_shaped_candidate_is_left_to_the_keep_step():
    md = _doc("## Results", "", "Body.", "",
              R._UNCAPTIONED_CANDIDATES_HEADING, "",
              "### Uncaptioned candidate u1 (page 3)", _PHANTOM)
    assert "<table>" in R._strip_phantom_camelot_tables(md)


def test_the_same_block_outside_the_candidate_section_is_still_stripped():
    """Two-sided: the exemption must not neuter the stripper everywhere else."""
    before = _doc("## Tables (unlocated in body)", "", "### Table 2", _PHANTOM, "",
                  R._UNCAPTIONED_CANDIDATES_HEADING, "",
                  "### Uncaptioned candidate u1 (page 3)", "text only")
    out = R._strip_phantom_camelot_tables(before)
    assert "<table>" not in out
    # the section ends at the next `## ` heading: a block after it is stripped too
    after = _doc(R._UNCAPTIONED_CANDIDATES_HEADING, "",
                 "### Uncaptioned candidate u1 (page 3)", "text only", "",
                 "## Figures", "", _PHANTOM)
    assert "<table>" not in R._strip_phantom_camelot_tables(after)


def test_the_section_heading_has_one_definition():
    src = open(R.__file__, encoding="utf-8").read()
    assert src.count('"## Uncaptioned table candidates (unverified)"') == 1, (
        "the candidate-section heading is spelled in more than one place; the "
        "stripper's exemption would silently stop matching if one copy changed"
    )


pytest.importorskip("camelot", reason="camelot not installed (pip install docpluck[all])")


def test_no_candidate_heading_is_left_empty_on_the_paper_that_found_it():
    """10.1017/s0007123424000024: every kept candidate reaches the render with its grid."""
    md = render_pdf_to_markdown(require_corpus_pdf("harvard/bjps_1.pdf").read_bytes())
    i = md.find(R._UNCAPTIONED_CANDIDATES_HEADING)
    assert i >= 0, "this paper keeps uncaptioned candidates; the section is missing"
    sections = re.split(r"(?m)^### Uncaptioned candidate ", md[i:])[1:]
    assert sections, "no candidate headings in the candidate section"
    empty = [s.split("\n", 1)[0] for s in sections if "<table" not in s.split("\n## ", 1)[0]]
    assert not empty, f"candidate heading(s) with their grid deleted by the render: {empty}"
    assert "Doerr et al." in md[i:], "the p10 literature-review table is not in the render"
