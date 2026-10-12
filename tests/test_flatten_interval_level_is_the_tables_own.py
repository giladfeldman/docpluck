"""The flattened sentence states the interval level the TABLE prints, never a
default "95%".

Reported by Scimeto (2026-08-21, §6): `_assemble_sentence` wrote "95% CI" for
every interval, so a 90% interval read as a 95% one -- and a CI-vs-p check that
judges a 90% interval at alpha = .05 reports an inconsistency the paper does not
have. The level now comes from the column header, a super-header, the caption
or the note; when the table states none, or states two different levels, the
sentence says a bare "CI" and `fields` carries no `CI_level`.
"""
from docpluck.tables.flatten import flatten_table


def _cell(r, c, text, header=False):
    return {"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": text,
            "is_header": header, "bbox": (0.0, 0.0, 0.0, 0.0)}


def _table(headers, values, caption=None, footnote=None):
    cells = [_cell(0, c, h, True) for c, h in enumerate(headers)]
    cells += [_cell(1, c, v) for c, v in enumerate(values)]
    return {"id": "T1", "label": "Table 1", "page": 1, "cells": cells,
            "bbox": (0.0, 0.0, 0.0, 0.0), "caption": caption, "footnote": footnote}


def _row(**kw):
    rows = flatten_table(_table(**kw))
    assert rows, "the table must flatten to at least one row"
    return rows[0]


def test_a_90_percent_level_is_carried():
    r = _row(headers=["Effect", "d", "LL", "UL"],
             values=["H1", "0.40", "0.10", "0.70"],
             caption="Table 1. Standardized effects with 90% CIs")
    assert "90% CI [0.1, 0.7]" in r["sentence"]
    assert "95%" not in r["sentence"]
    assert r["fields"]["CI_level"] == 90.0


def test_a_level_stated_only_in_the_caption_is_used():
    r = _row(headers=["Effect", "d", "lower", "upper"],
             values=["H1", "0.40", "0.10", "0.70"],
             caption="Table 1. Effect sizes with 95% confidence intervals")
    assert "95% CI [" in r["sentence"]
    assert r["fields"]["CI_level"] == 95.0


def test_two_different_levels_state_none():
    r = _row(headers=["Effect", "d", "lower", "upper"],
             values=["H1", "0.40", "0.10", "0.70"],
             caption="Table 1. 95% CI for d",
             footnote="Note. Intervals for the pooled estimate are 99% CIs.")
    assert "% CI" not in r["sentence"]
    assert "CI [" in r["sentence"]
    assert "CI_level" not in r["fields"]


def test_a_credible_interval_is_not_called_a_confidence_interval():
    r = _row(headers=["Effect", "d", "LL", "UL"],
             values=["H1", "0.40", "0.10", "0.70"],
             footnote="Note. LL and UL bound the 95% credible interval.")
    assert "95% CrI [" in r["sentence"]
    assert " CI [" not in r["sentence"]
