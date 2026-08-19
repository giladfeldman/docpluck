"""TypedDict types — Cell, Table, Figure exposed from their packages."""

from typing import get_type_hints


def test_cell_typed_dict_fields():
    from docpluck.tables import Cell
    hints = get_type_hints(Cell)
    expected = {"r", "c", "rowspan", "colspan", "text", "is_header", "bbox"}
    assert set(hints.keys()) == expected


def test_table_typed_dict_fields():
    from docpluck.tables import Table
    hints = get_type_hints(Table)
    expected = {
        "id", "label", "page", "bbox", "caption", "footnote",
        "kind", "rendering", "confidence",
        # v2.4.133: the COMPONENTS of `confidence` plus the engine record.
        # `confidence` used to be `accuracy/100`, so an 80%-empty capture
        # scored 0.95; it is now Camelot's own `(accuracy/100)*(1-whitespace)`
        # applied to the grid docpluck ships. Shipping only the composite
        # would repeat the original mistake — one number, no way to tell
        # which half moved — so the parts travel with it.
        "accuracy", "whitespace", "camelot_flavor",
        "n_rows", "n_cols", "header_rows",
        "cells", "html", "raw_text",
        # v2.4.135: whether `cells[].bbox` carries REAL per-cell geometry, and
        # if not, why. Every table from every path declares a state — an earlier
        # draft set it only on the Camelot path and the census caught 11.6% of
        # tables reporting nothing at all, which both hid the state and
        # understated what we ship (the whitespace path's boxes are built from
        # pdfplumber words and are real by construction).
        "cell_geometry",
    }
    assert set(hints.keys()) == expected


def test_table_kind_literal_values():
    from docpluck.tables import TableKind
    import typing
    args = typing.get_args(TableKind)
    assert set(args) == {"structured", "isolated"}


def test_table_rendering_literal_values():
    from docpluck.tables import TableRendering
    import typing
    args = typing.get_args(TableRendering)
    assert set(args) == {"lattice", "whitespace", "isolated"}


def test_figure_typed_dict_fields():
    from docpluck.figures import Figure
    hints = get_type_hints(Figure)
    expected = {"id", "label", "page", "bbox", "caption"}
    assert set(hints.keys()) == expected


def test_cell_constructable_as_dict():
    from docpluck.tables import Cell
    c: Cell = {
        "r": 0, "c": 0, "rowspan": 1, "colspan": 1,
        "text": "Variable", "is_header": True,
        "bbox": (0.0, 0.0, 100.0, 20.0),
    }
    assert c["r"] == 0


def test_figure_constructable_as_dict():
    from docpluck.figures import Figure
    f: Figure = {
        "id": "f1", "label": "Figure 1", "page": 3,
        "bbox": (72.0, 100.0, 540.0, 320.0),
        "caption": "Mean reaction time across conditions.",
    }
    assert f["id"] == "f1"
