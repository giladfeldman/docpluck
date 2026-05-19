"""Regression tests for the cycle-6 harness text_loss reflow exemption.

scripts/harness/checks.py::check_text_loss flagged 7 papers whose table /
stimulus regions pdftotext linearized column-major and the renderer reflowed
(into <table>s or into prose). Every word survived — only word order changed —
so the MATCH_WINDOW (8-contiguous-word) proxy mismatched. The reflow exemption
(REFLOW_COVERAGE + REFLOW_MIN_RUN) recognises that case. The one genuine loss
in the same sweep (plos-med-1 SAE Table 5) must still fail.
"""
from scripts.harness.checks import _fingerprint, check_text_loss


def _write_cell(tmp_path, raw, rendered):
    (tmp_path / "raw.txt").write_text(raw, encoding="utf-8")
    (tmp_path / "rendered.md").write_text(rendered, encoding="utf-8")
    return tmp_path


def test_fingerprint_greek_glyph_and_ascii_name_agree():
    # A glyph/ASCII-name divergence (chi vs the Greek letter) must not read
    # as a fingerprint mismatch — cycle-6 _fingerprint defense-in-depth.
    assert _fingerprint("χ2 test = 14.3") == _fingerprint("chi2 test = 14.3")
    assert _fingerprint("β weight model") == _fingerprint("beta weight model")
    assert "chi" in _fingerprint("χ2")


def test_reflowed_table_region_is_not_text_loss(tmp_path):
    # Raw: a body-prose paragraph. Rendered: every word survives but the
    # renderer reflowed the order — longest contiguous run is 7, never 8.
    raw = (
        "Participants in the experimental condition were asked to "
        "estimate the probability that the target event would occur."
    )
    rendered = (
        "# Heading\n\n"
        "In this study participants the experimental condition mattered. "
        "Each were asked estimate beforehand. We found the probability "
        "that the target event would change. Whether it would occur "
        "depended entirely on the surrounding context of the trial."
    )
    res = check_text_loss(_write_cell(tmp_path, raw, rendered), "pdf")
    assert res["verdict"] == "pass", res
    assert res["reflowed_exempt"] >= 1


def test_genuine_paragraph_loss_still_fails(tmp_path):
    # Raw: a substantive body paragraph. Rendered: unrelated content — the
    # paragraph is genuinely gone (the plos-med-1 SAE Table 5 shape: a few
    # words recur, but coverage stays well below REFLOW_COVERAGE).
    raw = (
        "During the follow up period there was a new case in which a "
        "participant required myomectomy after the uterus was perforated "
        "and suffered from heavy bleeding overnight."
    )
    rendered = (
        "# Heading\n\n"
        "The introduction discusses procedural sedation and analgesia "
        "compared with general anesthesia for routine outpatient care."
    )
    res = check_text_loss(_write_cell(tmp_path, raw, rendered), "pdf")
    assert res["verdict"] == "fail", res
