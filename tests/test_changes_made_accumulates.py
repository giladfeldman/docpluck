"""`changes_made[metric]` must ACCUMULATE — three rules share one key.

Filed by ESCImate/effectcheck in `INBOX_FROM_ESCIMATE_2026-08-21.md` §4, verified
by reading docpluck's source rather than inferred from behaviour:

    if diff != 0:
        self.changes_made[metric_name] = abs(diff)     # <- assignment, not +=

Three rules write `dropped_minus_signs_recovered` over one document (W0g, W0q,
W0h) and three write `minus_signs_recovered`; they cover distinct channels, so
two firing on one paper is ordinary. When they do, only the LAST one's delta
survives. effectcheck publishes this to users as a per-document column
`upstream_sign_rewrites`, and has had to document it as a *lower bound* rather
than a count.

Two further holes in the same line, both named in the filing:

- a step whose net length delta is ZERO is not recorded at all, although
  `steps_changed` gets it — and a glyph substitution (`2` -> `-`) is exactly
  length-neutral, so the rules this metric exists for are the ones most likely
  to vanish from it;
- the value is a character-length delta, not an event count, and nothing said so.

`changes_made_by_step` answers the per-rule question the filing asked for second.
"""

from __future__ import annotations

from docpluck.normalize import NormalizationReport


def _report() -> NormalizationReport:
    return NormalizationReport(level="academic")


def test_two_steps_sharing_a_metric_accumulate():
    r = _report()
    r._track("W0g", "aa", "a", "dropped_minus_signs_recovered")     # delta 1
    r._track("W0q", "bbb", "b", "dropped_minus_signs_recovered")    # delta 2
    assert r.changes_made["dropped_minus_signs_recovered"] == 3, (
        "the second rule overwrote the first; the consumer's "
        "upstream_sign_rewrites column is an undercount"
    )


def test_three_steps_sharing_a_metric_accumulate():
    r = _report()
    for step, before, after in (
        ("W0g", "aa", "a"),
        ("W0q", "bbb", "b"),
        ("W0h", "cccc", "c"),
    ):
        r._track(step, before, after, "minus_signs_recovered")
    assert r.changes_made["minus_signs_recovered"] == 1 + 2 + 3


def test_a_length_neutral_change_is_still_recorded():
    """A glyph substitution (`2` -> `-`) has zero length delta and must not vanish."""
    r = _report()
    r._track("W0h", "d = 2.38", "d = -.38", "dropped_minus_signs_recovered")
    assert "W0h" in r.steps_changed
    assert r.changes_made_by_step.get("W0h") is not None, (
        "a rule that changed the text left no trace in the per-step breakdown"
    )


def test_per_step_breakdown_separates_rules_sharing_one_metric():
    r = _report()
    r._track("W0g", "aa", "a", "dropped_minus_signs_recovered")
    r._track("W0q", "bbb", "b", "dropped_minus_signs_recovered")
    assert r.changes_made_by_step["W0g"] == 1
    assert r.changes_made_by_step["W0q"] == 2


def test_an_unchanged_step_records_nothing():
    r = _report()
    r._track("S9", "same", "same", "whatever")
    assert "whatever" not in r.changes_made
    assert "S9" not in r.changes_made_by_step
    assert "S9" not in r.steps_changed


def test_the_breakdown_is_serialized():
    """A value computed and never read back is not shipped."""
    r = _report()
    r._track("W0g", "aa", "a", "dropped_minus_signs_recovered")
    assert "changes_made_by_step" in r.to_dict()
