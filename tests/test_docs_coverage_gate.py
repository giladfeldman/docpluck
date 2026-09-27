"""Two-sided pin for `scripts/check_docs_coverage.py` (the documentation-drift gate).

A gate that passes on the real repo proves nothing unless it is also shown to FAIL when
the thing it guards is broken -- otherwise an empty derived surface or a regex that matches
everything would read as "fully documented". Each planted case below must be caught.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def gate():
    spec = importlib.util.spec_from_file_location(
        "check_docs_coverage", ROOT / "scripts" / "check_docs_coverage.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def surface(gate):
    return gate.collect_surface()


@pytest.fixture(scope="module")
def code(gate):
    return gate.documented_code_text()


def test_surface_is_derived_not_empty(surface):
    # The known-positive control: if derivation broke, every later "all documented"
    # would be vacuous.
    assert "extract_pdf" in surface["export"]
    assert "caption_status" in surface["field"]
    assert "uncaptioned_candidate" in surface["value"]
    assert "--tables-jsonl" in surface["cli flag"]
    assert "DOCPLUCK_FALLBACK_LOG" in surface["env var"]
    assert "[docx]" in surface["extra"]
    assert {"extract", "sections", "render"} <= surface["subcommand"]


def test_real_repo_is_fully_documented(gate, surface, code):
    assert gate.find_undocumented(surface, code) == []
    assert gate.check_changelog(surface, code) == []


@pytest.mark.parametrize("kind,token", [
    ("export", "planted_undocumented_export"),
    ("field", "planted_undocumented_field"),
    ("value", "planted_undocumented_value"),
    ("parameter", "planted_undocumented_param"),
    ("cli flag", "--planted-undocumented-flag"),
    ("env var", "DOCPLUCK_PLANTED_UNDOCUMENTED"),
    ("extra", "[planted]"),
    ("subcommand", "plantedsub"),
])
def test_planted_undocumented_token_fails(gate, surface, code, kind, token):
    planted = {k: set(v) for k, v in surface.items()}
    planted[kind].add(token)
    assert gate.find_undocumented(planted, code) == [f"{kind}: {token}"]


def test_prose_mention_is_not_documentation(gate, tmp_path):
    # `Table` in a sentence must not count; only code spans and fenced blocks do.
    doc = tmp_path / "doc.md"
    doc.write_text("A Widget in prose.\n\n`Gadget` inline.\n\n```python\nimport Gizmo\n```\n",
                   encoding="utf-8")
    code = gate.documented_code_text((str(doc),))
    assert not gate._is_documented("export", "Widget", code)
    assert gate._is_documented("export", "Gadget", code)
    assert gate._is_documented("export", "Gizmo", code)
    # A prefix must not satisfy a longer name, nor a longer name a prefix.
    assert not gate._is_documented("export", "extract_pdf", "extract_pdf_file")


def test_quickstart_without_python_block_is_refused(gate):
    with pytest.raises(SystemExit):
        gate.quickstart_blocks("# x\n\n## Quickstart\n\nno code here\n\n## Next\n")
