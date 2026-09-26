"""Tier-D `table_parity` must match each table class to its own heading.

Since 2.4.145 a Camelot grid no caption claims is kept with
``caption_status="uncaptioned_candidate"`` and rendered under a
``### Uncaptioned candidate ...`` heading, never ``### Table N``. The check
used to compare ``### Table`` headings against ALL tables, so every paper with
a candidate failed it (208 cells in the 2.4.145 whole-corpus run, every one
explained exactly by the candidate count) and the one real defect in that run
- candidate ``<table>`` blocks deleted by the render chain - was buried among
them. These tests pin both directions: candidates are counted against their
own heading, and neither class can hide a problem in the other.
"""

from __future__ import annotations

import json

from scripts.harness.checks import check_table_parity


def _write(tmp_path, tables, rendered):
    (tmp_path / "tables.json").write_text(json.dumps({"tables": tables}), encoding="utf-8")
    (tmp_path / "rendered.md").write_text(rendered, encoding="utf-8")
    return tmp_path


CAPTIONED = {"label": "Table 1", "caption_status": "matched", "kind": "structured", "html": "<table></table>"}
CANDIDATE = {"label": None, "caption_status": "uncaptioned_candidate", "kind": "structured", "html": "<table></table>"}

GOOD_MD = (
    "### Table 1\n\n<table><tr><td>1</td></tr></table>\n\n"
    "## Uncaptioned table candidates (unverified)\n\n"
    "### Uncaptioned candidate u1 (page 3)\n\n<table><tr><td>2</td></tr></table>\n"
)


def test_a_rendered_candidate_passes(tmp_path):
    out = _write(tmp_path, [CAPTIONED, CANDIDATE], GOOD_MD)
    assert check_table_parity(out, "pdf")["verdict"] == "pass"


def test_a_missing_captioned_heading_is_not_hidden_by_a_candidate(tmp_path):
    md = GOOD_MD.replace("### Table 1\n\n", "")
    out = _write(tmp_path, [CAPTIONED, CANDIDATE], md)
    result = check_table_parity(out, "pdf")
    assert result["verdict"] == "fail"
    assert any("captioned" in p for p in result["problems"])


def test_a_missing_candidate_heading_fails(tmp_path):
    md = GOOD_MD.replace("### Uncaptioned candidate u1 (page 3)\n\n", "")
    out = _write(tmp_path, [CAPTIONED, CANDIDATE], md)
    result = check_table_parity(out, "pdf")
    assert result["verdict"] == "fail"
    assert any("candidate" in p for p in result["problems"])


def test_a_candidate_whose_table_was_deleted_fails(tmp_path):
    # The render chain once removed a candidate's <table> and kept its heading.
    md = GOOD_MD.replace("<table><tr><td>2</td></tr></table>\n", "")
    out = _write(tmp_path, [CAPTIONED, CANDIDATE], md)
    result = check_table_parity(out, "pdf")
    assert result["verdict"] == "fail"
    assert any("<table> count" in p for p in result["problems"])
