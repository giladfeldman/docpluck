"""A catch-all handler must leave a trace (plan W1 exit gate, 2026-11-13).

Swept 2026-11-13: 73 `except Exception` / bare handlers in the package; 18
recorded nothing. Each was read: they refuse a rewrite, return a visible
sentinel or `unknown`, or store the error on the result. This RATCHET pins
that list: a new silent catch-all fails here and must either record a
fallback (`record_fallback`), re-raise, or be added below WITH its reason.
Entries are (file, enclosing function); line numbers drift.
"""
from __future__ import annotations

import ast
from pathlib import Path

import docpluck

PKG = Path(docpluck.__file__).parent
_TRACE = ("record_fallback", "raise", "warnings.warn", "logger", "log.", "_record", "ERROR")

ALLOWED = {
    ("batch.py", "*"): "stores the error on the BatchResult (error / layout_error)",
    ("cli.py", "*"): "layout parse failure: callees re-parse and record their own failures",
    ("version.py", "*"): "identity lookups: the receipt shows `unknown`",
    ("tables/camelot_cell_join.py", "_line_text"): "an unreadable line rewrites nothing",
    ("tables/camelot_extract.py", "_camelot_flavor"): "flavor None = not recorded, never guessed",
    ("tables/cell_geometry.py", "*"): "returns a refusal reason string the caller records",
    ("tables/column_split.py", "_glyphs_of_row"): "an unreadable row is never 'equal' (no split)",
}


class _Scan(ast.NodeVisitor):
    """Each broad handler with its INNERMOST enclosing function."""

    def __init__(self):
        self.stack: list[str] = ["<module>"]
        self.found: list[tuple[str, int]] = []

    def _fn(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = _fn

    def visit_ExceptHandler(self, n):
        t = n.type
        names = (["<bare>"] if t is None else [t.id] if isinstance(t, ast.Name)
                 else [e.id for e in t.elts if isinstance(e, ast.Name)]
                 if isinstance(t, ast.Tuple) else [])
        if {"Exception", "BaseException", "<bare>"} & set(names):
            body = ast.unparse(ast.Module(body=n.body, type_ignores=[]))
            if not any(k in body for k in _TRACE):
                self.found.append((self.stack[-1], n.lineno))
        self.generic_visit(n)


def _silent_handlers():
    out = []
    for f in PKG.rglob("*.py"):
        scan = _Scan()
        scan.visit(ast.parse(f.read_text(encoding="utf-8")))
        rel = f.relative_to(PKG).as_posix()
        out += [(rel, fn, ln) for fn, ln in scan.found]
    return out


def test_every_silent_broad_except_is_allowed_with_a_reason():
    found = _silent_handlers()
    assert len(found) >= 5, "scan found almost nothing -- broken scan?"
    bad = sorted({(f, fn, ln) for f, fn, ln in found
                  if (f, fn) not in ALLOWED and (f, "*") not in ALLOWED})
    assert not bad, (
        "new catch-all handler(s) that record nothing; record_fallback, re-raise, "
        f"or allow with a reason: {bad}")
