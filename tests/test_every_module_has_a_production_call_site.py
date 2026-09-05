"""No module under `docpluck/` may be imported ONLY by its own test.

Written 2026-09-05 against the unfixed tree and watched FAIL on five modules.

WHY. docpluck's CLAUDE.md opens with four checks a change must pass before it is "done",
and the first is: *"A non-test call site exists for every symbol added. `grep` for it. A
module imported only by its own test is not shipped."* That rule has existed since
2026-05-14 and nothing has ever checked it. The 2026-09-05 audit found five modules in
that state -- one of them, `docpluck/tables/confidence.py`, is a SECOND implementation of
a concept whose live implementation is inline in `camelot_extract.py` and uses a
completely different formula. Nine green tests cover the dead one. A reader who opens
`confidence.py` to learn how docpluck scores a table's confidence is reading code that
never runs, which is the "one concept, one table" hard rule failing in its worst form:
not drift, total divergence, with the tests pointing at the wrong copy.

THE SHAPE IS A RATCHET, NOT A CLEAN SWEEP. The five existing orphans are listed below
with the decision each is owed. Deleting or wiring them is an owner call and a separate
change; what this test buys today is that the sixth cannot appear unnoticed, and that
the five stop being invisible. `test_the_known_orphans_are_still_orphans` fails when one
is fixed, so the list cannot rot into a permanent excuse.

CONTROL. `test_the_importer_census_can_see_a_wired_module` asserts that modules known to
be wired are seen as wired. Without it, a census that resolved no imports at all would
report every module as an orphan -- or, with the allowlist, report exactly the five and
look correct while measuring nothing.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_PKG = _REPO / "docpluck"

# Modules with no production importer as of 2026-09-05, each with the decision owed.
# This is a RATCHET: it may shrink, never grow. Adding a name here is a decision to ship
# a module nothing calls, and needs the same justification as shipping dead code.
_KNOWN_ORPHANS: dict[str, str] = {
    "docpluck.tables.confidence": (
        "SUPERSEDED. The shipped confidence is computed inline at "
        "camelot_extract.py:809 as acc_frac * (1 - whitespace_pct/100); this module's "
        "base - 0.05*deviation_rows with floors/ceilings is a different formula "
        "entirely and reaches no consumer. DECISION OWED: delete it, or make it the "
        "single implementation and have camelot_extract call it."
    ),
    "docpluck.tables.cluster": "DECISION OWED: superseded by tables.whitespace's clustering, or unwired?",
    "docpluck.figures.detect": "DECISION OWED: figure detection is on no production path; wire or remove.",
    "docpluck.sections.annotators.pdf": "DECISION OWED: the PDF section annotator is not imported by sections.core.",
    "docpluck.sections.boundaries": "DECISION OWED: superseded by the boundary logic in normalize/sections.core?",
}

_CONTROL_WIRED = ("docpluck.normalize", "docpluck.tables.cell_cleaning", "docpluck.tables.flatten")


def _module_name(path: Path) -> str:
    return ".".join(path.relative_to(_REPO).with_suffix("").parts)


def _resolve(path: Path, node: ast.ImportFrom) -> str:
    """Absolute module name for a possibly-relative `from ... import ...`."""
    parent = list(path.relative_to(_REPO).parent.parts)
    if node.level:
        parent = parent[: len(parent) - (node.level - 1)] if node.level > 1 else parent
        return ".".join(parent + ([node.module] if node.module else []))
    return node.module or ""


def _production_importers() -> dict[str, set[str]]:
    """{module name: set of files under docpluck/ that import it}."""
    modules = {
        _module_name(f) for f in _PKG.rglob("*.py") if f.name != "__init__.py"
    }
    hits: dict[str, set[str]] = {m: set() for m in modules}
    for f in sorted(_PKG.rglob("*.py")):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        seen: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                seen.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = _resolve(f, node)
                seen.add(base)
                seen.update(f"{base}.{a.name}" for a in node.names)
            elif isinstance(node, ast.Call):
                # `__import__("docpluck.symbols", ...)` is a real wiring route in
                # normalize.py; a census blind to it would invent an orphan.
                fn = node.func
                name = getattr(fn, "id", None) or getattr(fn, "attr", None)
                if name in ("__import__", "import_module") and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        seen.add(arg.value)
        for m in modules:
            if f.name != Path(m.replace(".", "/") + ".py").name or _module_name(f) != m:
                if any(s == m or s.startswith(m + ".") for s in seen):
                    hits[m].add(f.as_posix())
    return hits


def test_the_importer_census_can_see_a_wired_module():
    """Two-sided control. A census resolving nothing calls every module an orphan."""
    hits = _production_importers()
    for m in _CONTROL_WIRED:
        assert m in hits, f"{m} vanished from the module list -- the census is broken"
        assert hits[m], (
            f"{m} is imported all over this package and the census sees zero importers. "
            "The instrument is broken; every other assertion here is vacuous."
        )


def test_no_new_module_is_imported_only_by_its_own_test():
    """RED FIRST 2026-09-05 with an empty allowlist: five modules failed."""
    hits = _production_importers()
    orphans = {
        m
        for m, importers in hits.items()
        if not importers and not m.endswith(".__main__")
    }
    new = sorted(orphans - set(_KNOWN_ORPHANS))
    assert not new, (
        "these modules under docpluck/ have NO production importer -- they are shipped in "
        "the package, covered by tests, and reached by nothing:\n"
        + "\n".join(f"  {m}" for m in new)
        + "\n\nCLAUDE.md check 1: a module imported only by its own test is not shipped. "
        "Wire it, delete it, or (deliberately) add it to _KNOWN_ORPHANS with the decision owed."
    )


def test_the_known_orphans_are_still_orphans():
    """The allowlist may shrink, never rot.

    A name here that has since been wired, renamed or deleted must leave the list --
    otherwise the list becomes a place where a fixed problem and a live one look the same.
    """
    hits = _production_importers()
    stale = []
    for m in sorted(_KNOWN_ORPHANS):
        if m not in hits:
            stale.append(f"  {m}: no longer exists under docpluck/ -- remove it from _KNOWN_ORPHANS")
        elif hits[m]:
            stale.append(f"  {m}: now imported by {sorted(hits[m])} -- remove it from _KNOWN_ORPHANS")
    assert not stale, "_KNOWN_ORPHANS is stale:\n" + "\n".join(stale)
