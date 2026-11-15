"""The debt-trace gate reads a whole list of ids a commit leaves open.

"Logged as d-aaaaaa d-bbbbbb" used to read only the first id, so the release
gate failed the rest as "cited but still open" (2.4.160, 2026-11-15).
Ids here are invented."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_debt_trace", Path(__file__).resolve().parents[1] / "scripts" / "check_debt_trace.py")
cdt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cdt)


def test_space_comma_and_and_lists_are_read_whole():
    body = "fix: x\n\nLogged as d-aaaaa1 d-aaaaa2, d-aaaaa3 and d-aaaaa4. Closed: d-bbbbb1."
    assert cdt.open_citations(body) == {"d-aaaaa1", "d-aaaaa2", "d-aaaaa3", "d-aaaaa4"}


def test_a_closed_id_after_other_words_is_not_open():
    assert cdt.open_citations("part of d-ccccc1; fixes d-ccccc2") == {"d-ccccc1"}
