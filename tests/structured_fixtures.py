"""One resolver for the structured-extraction fixtures, shared by every test.

It existed in TEN copies until 2026-09-17 -- ``_resolve_fixture`` was pasted,
byte for byte, into ``test_bbox_utils``, ``test_cli_structured``,
``test_extract_pdf_structured``, ``test_f0_table_region_aware``,
``test_figure_detect``, ``test_fixtures_manifest``, ``test_lattice_cluster``,
``test_smoke_fixtures``, ``test_table_detect`` and ``test_text_mode``. Ten copies
of one rule drift, and the drift is silent: this project has already shipped a
chi-square that came out ``chi2`` or ``ch2`` depending purely on which of two
Greek tables ran.

Each copy also skipped when its fixture did not resolve, which is how a suite
reports success having read nothing. Resolution now goes through the article
custodian and a miss is a FAILURE.
"""

from __future__ import annotations

import json
from pathlib import Path

from docpluck.testing import require_corpus_pdf

MANIFEST_PATH = Path(__file__).parent / "fixtures" / "structured" / "MANIFEST.json"


def load_manifest() -> dict:
    """The fixture manifest. Its absence is a FAILURE, not a skip.

    The file is committed beside this module; if it is gone, something deleted
    it, and reporting that as "nothing to test" would hide the deletion.
    """
    if not MANIFEST_PATH.is_file():
        raise AssertionError(
            f"the structured-fixture manifest is missing: {MANIFEST_PATH}. It is a "
            "committed file; skipping here would report a deleted manifest as an "
            "empty one."
        )
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def fixture_entries() -> list[dict]:
    return load_manifest()["fixtures"]


def fixture_ids() -> list[str]:
    return [e["id"] for e in fixture_entries()]


def resolve_fixture(fixture_id: str) -> Path:
    """The PDF for ``fixture_id``, from custody. Raises when it does not resolve."""
    for entry in fixture_entries():
        if entry["id"] == fixture_id:
            return require_corpus_pdf(entry["corpus_path"])
    raise AssertionError(
        f"fixture id {fixture_id!r} is not in {MANIFEST_PATH.name}. Known ids: "
        + ", ".join(sorted(fixture_ids()))
    )


__all__ = [
    "MANIFEST_PATH",
    "fixture_entries",
    "fixture_ids",
    "load_manifest",
    "resolve_fixture",
]
