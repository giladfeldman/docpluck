"""`include_uncaptioned=False` withholds uncaptioned candidates, and counts them.

Default stays True: Scimeto asked (2026-10-13) that candidates stay in default output.
"""
from __future__ import annotations

from docpluck import extract_structured as es


def _fake(*a, **k):
    return {
        "text": "x", "method": "pdftotext", "page_count": 1, "figures": [],
        "table_extraction_version": "t", "fallbacks": {}, "fallback_details": {},
        "tables": [
            {"id": "t1", "label": "Table 1", "caption_status": "matched", "cells": []},
            {"id": "u1", "label": None, "caption_status": "uncaptioned_candidate", "cells": []},
            {"id": "u2", "label": None, "caption_status": "uncaptioned_candidate", "cells": []},
        ],
    }


def test_default_keeps_candidates(monkeypatch):
    monkeypatch.setattr(es, "_extract_pdf_structured", _fake)
    r = es.extract_pdf_structured(b"%PDF")
    assert [t["id"] for t in r["tables"]] == ["t1", "u1", "u2"]
    assert "uncaptioned_candidates_withheld" not in r["fallbacks"]


def test_switch_off_withholds_and_counts(monkeypatch):
    monkeypatch.setattr(es, "_extract_pdf_structured", _fake)
    r = es.extract_pdf_structured(b"%PDF", include_uncaptioned=False)
    assert [t["id"] for t in r["tables"]] == ["t1"]
    assert r["fallbacks"]["uncaptioned_candidates_withheld"] == 2
