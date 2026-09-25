"""Every flattened row carries its table's `caption_status`.

Why this file exists (2026-09-24). Grids that no caption claims are kept as
`caption_status="uncaptioned_candidate"` tables (owner directive: retain and label,
never drop). They also flow into `flattened_rows` -- the channel consumers such as
Scimeto and ESCImate run statistical checks on -- and a `FlattenedRow` carried no
status, so ~369 grids across the 102-paper corpus, about half of them furniture,
reached those checks looking exactly like rows of captioned tables. Found by the
v2.4.145 release coordinator.

Owner decision, "option B": keep those rows (about half are real statistical
tables, which excluding them would drop again) and label every row with its
table's status so a consumer can filter.
"""

from pathlib import Path

import pytest

from docpluck.extract_structured import extract_pdf_structured
from docpluck.tables.flatten import flatten_table, flatten_tables_for_paper
from docpluck.testing import require_corpus_pdf

from .conftest import pdf_path

pytest.importorskip("camelot", reason="camelot not installed (pip install docpluck[all])")

_ALLOWED = {"matched", "none_found", "uncaptioned_candidate"}

# Kept candidate u1 on p29 is a regression table ("Coeff. (SE)") that no caption
# matched -- a real statistical table, exactly the case option B keeps.
_WITH_CANDIDATE = "chicago-ad/demography_3.pdf"


@pytest.fixture(scope="module")
def structured():
    return extract_pdf_structured(require_corpus_pdf(_WITH_CANDIDATE).read_bytes())


def test_every_row_states_a_valid_caption_status(structured):
    rows = flatten_tables_for_paper(structured["tables"])
    assert rows, "no flattened rows at all -- this test would pass vacuously"
    bad = [r for r in rows if r.get("caption_status") not in _ALLOWED]
    assert not bad, f"{len(bad)} rows lack a valid caption_status, e.g. {bad[0]}"


def test_candidate_rows_are_labelled_as_candidates(structured):
    rows = flatten_tables_for_paper(structured["tables"])
    by_status = {}
    for r in rows:
        by_status.setdefault(r["caption_status"], set()).add(r["table_id"])
    assert "uncaptioned_candidate" in by_status, (
        "no candidate rows on a paper known to carry a kept candidate table; "
        f"statuses seen: {sorted(by_status)}"
    )
    assert all(t.startswith("u") for t in by_status["uncaptioned_candidate"])
    assert "matched" in by_status, "captioned tables must flatten as 'matched'"


def test_the_early_return_path_is_labelled_too():
    """The packed-arms flattener returns early. A field stamped at one return and
    missed at the other is the failure this wrapper design exists to prevent."""
    p = Path(pdf_path("articlerepo", "10.1525__collabra.77859.pdf"))
    if not p.is_file():
        pytest.fail(f"packed-arms fixture not readable: {p} -- a gate that cannot "
                    "read its paper must fail, never skip")
    r = extract_pdf_structured(p.read_bytes())
    t2 = next(t for t in r["tables"] if t.get("label") == "Table 2")
    rows = flatten_table(t2)
    packed = [x for x in rows if x["row_label"].startswith("Attractive")]
    assert len(packed) == 2, "the packed-arms path did not run; this test proves nothing"
    assert all(x["caption_status"] == "matched" for x in rows), rows[:2]


def test_a_table_without_a_stated_status_is_never_called_certain():
    """A hand-built table dict (no caption_status) gets the conservative rule."""
    cells = [
        {"r": 0, "c": 0, "text": "Condition", "is_header": True},
        {"r": 0, "c": 1, "text": "M", "is_header": True},
        {"r": 1, "c": 0, "text": "Control", "is_header": False},
        {"r": 1, "c": 1, "text": "4.21", "is_header": False},
        {"r": 2, "c": 0, "text": "Treatment", "is_header": False},
        {"r": 2, "c": 1, "text": "5.10", "is_header": False},
    ]
    labelled = {"id": "t1", "label": "Table 1", "page": 1, "cells": cells}
    unlabelled = {"id": "x1", "label": None, "page": 1, "cells": cells}
    assert {r["caption_status"] for r in flatten_table(labelled)} == {"matched"}
    assert {r["caption_status"] for r in flatten_table(unlabelled)} == {"uncaptioned_candidate"}
