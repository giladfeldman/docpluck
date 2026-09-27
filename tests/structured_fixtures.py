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


def caption_regions(fixture_id: str):
    """``caption_regions_for_pdf`` for a structured fixture."""
    return caption_regions_for_pdf(resolve_fixture(fixture_id).read_bytes())


def caption_regions_for_pdf(pdf: bytes):
    """``(layout, regions)``: one ``CandidateRegion`` per TABLE caption of the
    fixture, located the way production locates it -- the caption from the text
    channel (``extract_structured`` rejoins pdftotext's text and matches captions
    there), the region from ``detect._region_for_caption``.

    Replaces ``detect.find_table_regions`` (removed 2026-09-25), which matched
    captions in the LAYOUT channel's text instead: on tight-kerned PDFs that text
    has no spaces, and it found 0 of `10.5465/amj.2016.1196`'s five table
    captions while production found all five. Tests that borrowed regions from it
    were testing geometry on a path no document took.
    """
    from docpluck.extract import extract_pdf
    from docpluck.extract_layout import extract_pdf_layout
    from docpluck.extract_structured import _join_split_captions, _page_offsets
    from docpluck.tables.captions import (
        caption_anchor_is_in_text_reference,
        find_caption_matches,
    )
    from docpluck.tables.detect import _region_for_caption

    raw, _ = extract_pdf(pdf)
    rejoined = _join_split_captions(raw)
    by_key: dict = {}
    for c in find_caption_matches(rejoined, _page_offsets(rejoined)):
        if c.kind == "table":
            by_key.setdefault(c.number, []).append(c)
    captions = sorted(
        (
            next((c for c in group if not caption_anchor_is_in_text_reference(rejoined, c)), group[0])
            for group in by_key.values()
        ),
        key=lambda c: c.char_start,
    )
    layout = extract_pdf_layout(pdf)
    regions = [r for r in (_region_for_caption(layout, c) for c in captions) if r is not None]
    return layout, regions
