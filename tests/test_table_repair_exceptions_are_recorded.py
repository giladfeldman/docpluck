"""Rule 40: a caught failure in the bottom-extend / dropped-sign repairs must be
ASSERTABLE (recorded through record_fallback), not swallowed. Forced-failure arm:
each handler records its named event; healthy arm: a clean call records none."""
from docpluck.telemetry import fallback_scope
from docpluck.tables import bottom_extend, dropped_glyphs


class _Boom:
    def get_text(self):
        raise ValueError("boom")

    @property
    def df(self):
        raise KeyError("boom")


def test_bottom_extend_text_exception_recorded():
    with fallback_scope() as fb:
        assert bottom_extend._text(_Boom()) == ""
    assert fb.counters.get("bottom_extend_text_exception") == 1


def test_bottom_extend_grid_unreadable_recorded():
    with fallback_scope() as fb:
        assert bottom_extend._grid_is_numeric(_Boom()) is False
    assert fb.counters.get("bottom_extend_grid_unreadable") == 1


def test_bottom_extend_outer_exception_recorded(monkeypatch):
    ct = object()

    def _raise(_ct):
        raise RuntimeError("boom")

    monkeypatch.setattr(bottom_extend, "continuation_bottom", _raise)
    with fallback_scope() as fb:
        assert bottom_extend.extend_to_table_bottom(object(), "x.pdf", ct) is ct
    assert fb.counters.get("bottom_extend_exception") == 1


def test_dropped_glyphs_text_exception_recorded():
    with fallback_scope() as fb:
        assert dropped_glyphs._text(_Boom()) == ""
    assert fb.counters.get("dropped_glyphs_text_exception") == 1


def test_dropped_glyphs_restore_exception_recorded(monkeypatch):
    def _raise(_ct, _layout):
        raise RuntimeError("boom")

    monkeypatch.setattr(dropped_glyphs, "_restore", _raise)
    with fallback_scope() as fb:
        assert dropped_glyphs.restore_dropped_signs(object(), object()) == 0
    assert fb.counters.get("dropped_glyphs_restore_exception") == 1


def test_healthy_text_records_nothing():
    class _Ok:
        def get_text(self):
            return " 1.5 "

    with fallback_scope() as fb:
        assert bottom_extend._text(_Ok()) == "1.5"
        assert dropped_glyphs._text(_Ok()) == "1.5"
    assert fb.counters == {}
