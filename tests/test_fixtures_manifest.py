"""The structured-fixture manifest is well-formed and every paper it names is in custody.

Rewritten 2026-09-17 with the corpus repoint. Two things changed, and the second
is the point of the exercise:

* ``source_path`` (a portfolio-relative directory path into a sibling project)
  became ``corpus_path``, a name resolved through the article custodian by DOI.
* ``test_fixture_source_path_resolves_to_real_pdf`` used to SKIP when a paper
  was not on disk. That is the defect, not a kindness: a manifest entry naming a
  paper nobody holds is exactly what this test exists to catch, and skipping made
  it report success for finding nothing. It now FAILS.
"""

import json
from pathlib import Path

import pytest

from tests.structured_fixtures import (
    MANIFEST_PATH,
    fixture_entries,
    load_manifest,
    resolve_fixture,
)

_FIXTURES_DIR = MANIFEST_PATH.parent


def test_fixtures_directory_exists():
    assert _FIXTURES_DIR.is_dir(), f"Missing: {_FIXTURES_DIR}"


def test_manifest_exists_and_is_json():
    assert MANIFEST_PATH.is_file(), f"Missing: {MANIFEST_PATH}"
    json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_top_level_schema():
    data = load_manifest()
    assert "version" in data
    assert "fixtures" in data
    assert isinstance(data["fixtures"], list)
    assert len(data["fixtures"]) >= 8, "expect >=8 fixtures collected"


def test_the_manifest_no_longer_carries_a_directory_path():
    """``source_path``/``vibe_relative`` are the retired, directory-based scheme.

    Asserted rather than assumed: a half-migrated manifest would resolve some
    fixtures through custody and leave others pointing at a directory that is
    about to be deleted, and only the deleted half would announce itself.
    """
    data = load_manifest()
    assert "vibe_relative" not in data, (
        "vibe_relative is the old directory-rooted resolution; fixtures resolve "
        "through article-finder now"
    )
    stale = [e["id"] for e in data["fixtures"] if "source_path" in e]
    assert not stale, f"fixtures still carrying the retired source_path: {stale}"


def test_each_fixture_entry_has_required_fields():
    valid_categories = {
        "lattice_table", "apa_lineless", "nature_minimal_rule",
        "figure_only", "negative_no_tables_no_figures",
        "table_of_contents_negative", "uncaptioned_table",
    }
    for entry in fixture_entries():
        assert "id" in entry
        assert "category" in entry
        assert entry["category"] in valid_categories, (
            f"Unknown category: {entry['category']} (entry: {entry['id']})"
        )
        assert "corpus_path" in entry
        assert "canonical_key" in entry, (
            f"{entry['id']}: no DOI recorded. The DOI is how the paper is named "
            "now; without it the entry cannot be re-resolved if the corpus name "
            "ever changes."
        )
        assert "expected_tables" in entry
        assert "expected_figures" in entry


def test_fixture_ids_are_unique():
    ids = [e["id"] for e in fixture_entries()]
    assert len(set(ids)) == len(ids), f"Duplicate fixture ids: {ids}"


@pytest.mark.parametrize(
    "entry",
    load_manifest()["fixtures"],
    ids=lambda e: e.get("id", "?"),
)
def test_every_fixture_resolves_in_custody_to_a_real_pdf(entry):
    """Per-fixture: the named paper is held, and the bytes are a PDF. No skip."""
    path: Path = resolve_fixture(entry["id"])
    head = path.read_bytes()[:5]
    assert head[:4] == b"%PDF", f"{entry['id']}: not a PDF at {path}"
