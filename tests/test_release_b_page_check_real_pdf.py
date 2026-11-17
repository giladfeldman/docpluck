"""Real-paper regressions found by the Release B page check (2026-11-16): each
value below was read off the rendered page, not off any extractor.

* 10.1016/j.joep.2020.102349 Table 11 (p11): Original and Replication effect
  columns side by side. The record is the Replication block, whole (0.28
  [0.21, 0.36]); the Original cell is listed as `field_bound_by_later_column`.
* 10.1186/s12889-023-17078-5 Table 6 (p12): "2.50 [0.71–8.83]" was bound with
  CI_lower = 2.50 (the estimate). The page prints 0.71.
* 10.1017/jdm.2024.31 Table 5 (p11): each d sits one column left of its arm
  label; the Target d (-0.39) was bound as the Replication's d.
* 10.15626/mp.2022.3108 Table 10 (p10): its grid was Table 9's lower rows.
"""
from __future__ import annotations

import functools

from docpluck.extract_structured import extract_pdf_structured
from docpluck.tables.flatten import flatten_table
from docpluck.testing import require_corpus_pdf
from docpluck.testing.corpus import MANIFEST


@functools.lru_cache(maxsize=None)
def _records(doi: str, label: str, page: int):
    rel = next(k for k, v in MANIFEST.items() if v["doi"].lower() == doi.lower())
    r = extract_pdf_structured(require_corpus_pdf(rel).read_bytes())
    t = next(t for t in r["tables"] if t.get("label") == label and t.get("page") == page)
    return flatten_table(t)


def _row(recs, start, group=None):
    return [x for x in recs if x["raw_cells"] and x["raw_cells"][0].startswith(start)
            and x["fields"].get("group") == group]


def test_joep_table11_lists_the_original_effect():
    recs = _records("10.1016/j.joep.2020.102349", "Table 11", 11)
    (p1,) = _row(recs, "Problem 1")
    assert (p1["fields"]["est"], p1["fields"]["CI_lower"], p1["fields"]["CI_upper"]) == (
        0.28, 0.21, 0.36)
    assert any(u["reason"] == "field_bound_by_later_column" and "0.26" in u["cell"]
               for u in p1["unparsed"])


def test_s12889_table6_ci_lower_is_the_printed_bound():
    recs = _records("10.1186/s12889-023-17078-5", "Table 6", 12)
    (male_or,) = _row(recs, "Male", "OR")
    assert (male_or["fields"]["est"], male_or["fields"]["CI_lower"],
            male_or["fields"]["CI_upper"]) == (2.5, 0.71, 8.83)
    for x in recs:
        f = x["fields"]
        if "est" in f and "CI_lower" in f:
            assert f["CI_lower"] < f["est"] < f["CI_upper"], x["raw_cells"]


def test_jdm_table5_target_d_is_never_a_replication_value():
    recs = _records("10.1017/jdm.2024.31", "Table 5", 11)
    for x in recs:
        if x["fields"].get("group") == "Replication":
            assert x["fields"].get("d") != -0.39, x["raw_cells"]


def test_mp_table10_does_not_carry_table9_rows():
    rel = next(k for k, v in MANIFEST.items() if v["doi"].lower() == "10.15626/mp.2022.3108")
    r = extract_pdf_structured(require_corpus_pdf(rel).read_bytes())
    t10 = next(t for t in r["tables"] if t.get("label") == "Table 10")
    assert not any("8.45" in (c.get("text") or "") for c in t10["cells"])
    # The copied grid is removed; Table 10 keeps its own printed text.
    assert t10["content_status"] == "raw_text"
    assert "Inconsistent - Opposite direction" in t10["raw_text"]
    assert "8.45" not in t10["raw_text"]
    assert "Table 10<-Table 9" in r["fallback_details"]["table_grid_copies_a_neighbour"]
    t9 = next(t for t in r["tables"] if t.get("label") == "Table 9")
    assert any("8.45" in (c.get("text") or "") for c in t9["cells"])


def test_irsp946_side_by_side_tables_keep_their_own_values():
    """10.5334/irsp.946 p5 and p7 print each caption under its table; Table 3
    (p5) and Table 4 (p7) own their M/SD values and are never cleared as
    copies of the wider grid beside them."""
    rel = next(k for k, v in MANIFEST.items() if v["doi"].lower() == "10.5334/irsp.946")
    r = extract_pdf_structured(require_corpus_pdf(rel).read_bytes())
    for label, value in (("Table 3", "4.81"), ("Table 4", "3.78")):
        t = next(t for t in r["tables"] if t.get("label") == label)
        assert t["content_status"] != "not_captured:grid_copies_another_table", label
        assert any(value in (c.get("text") or "") for c in t["cells"]), label


def test_collabra77859_records_never_mix_two_studies():
    """10.1525/collabra.77859, values read off the page: Table 4 (p8) Joint
    prints the Replication's t 1.26 with p .210 (the Original's p .039 is in
    another block); Table 1 (p4) prints Separate and Joint results stacked in
    one cell, ".69 [.44, .94]" over ".39 [.21, .57]"."""
    (joint,) = _row(_records("10.1525/collabra.77859", "Table 4", 8), "Joint")
    assert (joint["fields"]["t"], joint["fields"]["p"]) == (1.26, 0.21)
    for x in _records("10.1525/collabra.77859", "Table 1", 4):
        f = x["fields"]
        if "d" in f and "CI_lower" in f:
            assert f["CI_lower"] < f["d"] < f["CI_upper"], x["raw_cells"]
