"""An unreadable page in the running-rule scan is recorded, not skipped silently (d-2ca28f).

`_furniture_rule_keys` counts how many pages repeat a rule; a page whose strokes
cannot be read drops out of that count. Before 2.4.159 it dropped out with no
trace, so a consumer could not tell the filter ran on fewer pages than it had.
"""
from __future__ import annotations

from types import SimpleNamespace

from docpluck import telemetry
from docpluck.tables import detect


def test_unreadable_page_records_a_fallback(monkeypatch):
    def boom(page):
        if page.page_number == 2:
            raise ValueError("bad page")
        return []

    monkeypatch.setattr(detect, "_joined_horizontal_strokes", boom)
    monkeypatch.setattr(detect, "_page_opens_a_caption", lambda p: False)
    layout = SimpleNamespace(pages=[SimpleNamespace(page_number=i) for i in range(1, 9)])
    telemetry.reset_fallback_counters()
    detect._FURNITURE_CACHE.clear()
    assert detect._furniture_rule_keys(layout) == frozenset()
    assert telemetry.get_fallback_counters().get("table_furniture_page_unreadable") == 1
    assert "p2:ValueError" in telemetry.get_fallback_details()["table_furniture_page_unreadable"]
