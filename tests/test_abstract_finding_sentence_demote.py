"""Unit-contract test for the abstract-zone finding-sentence demote (v2.4.111).

jama_open_1 rendered "## TRE was more effective for weight loss" — a Key-Points
FINDING sentence column-interleaved into the abstract zone and over-promoted to
`## `. `_demote_abstract_zone_inline_labels` only demoted an explicit allowlist
of structured-abstract LABELS, so this sentence slipped through (the pre-existing
`test_d3_abstract_zone_no_intermediate_h2` failure).

Fix (v2.4.111): `_is_abstract_finding_sentence` demotes an abstract-zone `## `
whose text is a full CLAUSE with a finite VERB. The verb is the discriminator
that keeps a legitimate noun-phrase heading ("Effects of Diet on Body Weight" —
only lowercase prepositions) as a heading while demoting a finding sentence.
The `test_d3_abstract_zone_no_intermediate_h2` real-PDF assertion (in
test_jama_open_cluster_real_pdf.py) is the end-to-end regression guard.
"""

from __future__ import annotations

from docpluck.render import _is_abstract_finding_sentence


def test_finding_sentences_detected():
    for s in (
        "TRE was more effective for weight loss",
        "Time-restricted eating reduced body weight more than caloric restriction",
        "The intervention did not change HbA1c levels significantly",
        "Participants who exercised showed greater improvement in mood",
    ):
        assert _is_abstract_finding_sentence(s), f"should be a finding sentence: {s!r}"


def test_labels_and_noun_phrase_headings_not_demoted():
    for s in (
        # structured-abstract labels (all-caps or handled by allowlist)
        "IMPORTANCE",
        "MAIN OUTCOMES AND MEASURES",
        "CONCLUSIONS AND RELEVANCE",
        # short section headings
        "Introduction",
        "Methods",
        "Statistical Analysis",
        "Trial Registration",
        # NOUN-PHRASE headings with lowercase prepositions/articles but NO verb —
        # the exact FP class the finite-verb gate exists to exclude.
        "Effects of Diet on Body Weight",
        "Comparison of TRE and CR",
        "Association Between Sleep and Mood",
        "Baseline Characteristics of the Study Participants",
        "Study Design and Oversight",
    ):
        assert not _is_abstract_finding_sentence(s), f"should NOT demote: {s!r}"


def test_short_lines_never_demoted():
    # A <5-word line is never a finding sentence (too short to be a clause).
    assert not _is_abstract_finding_sentence("Weight was reduced")
    assert not _is_abstract_finding_sentence("HbA1c decreased")
