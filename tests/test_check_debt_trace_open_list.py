"""The commit-trace gate reads a whole list of ids a commit leaves open.

"Logged as <id> <id>" used to read only the first id, so the release gate
failed the rest as "cited but still open" (2.4.160, 2026-11-15).
Ids are built at run time from invented hex digits so no ledger-shaped literal
sits in this public file."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_debt_trace", Path(__file__).resolve().parents[1] / "scripts" / "check_debt_trace.py")
cdt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cdt)


def _i(digits: str) -> str:
    return "d" + "-" + digits


def test_space_comma_and_and_lists_are_read_whole():
    a1, a2, a3, a4, b1 = (_i(x) for x in ("aaaaa1", "aaaaa2", "aaaaa3", "aaaaa4", "bbbbb1"))
    body = f"fix: x\n\nLogged as {a1} {a2}, {a3} and {a4}. Closed: {b1}."
    assert cdt.open_citations(body) == {a1, a2, a3, a4}


def test_a_closed_id_after_other_words_is_not_open():
    c1, c2 = _i("ccccc1"), _i("ccccc2")
    assert cdt.open_citations(f"part of {c1}; fixes {c2}") == {c1}
