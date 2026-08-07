"""Provenance-completeness guards (MetaESCI INBOX 2026-08-07, asks A-1 / A-2).

Incident that produced these tests: MetaESCI ran the *same* docpluck SHA
(``a5c02ef``) against the *same* PDF (``10.1098/rsos.202336``) in April and in
August and got 49,091 vs 50,101 normalized characters, because the system
poppler binary was replaced on 2026-05-14. ``get_version_info()`` reported
``{version, normalize_version, git_sha}`` — all three identical across both
runs — so nothing in docpluck's recorded provenance made the change
detectable, and the downstream spent real time attributing it to its own code.

The class of defect is *incomplete provenance*, not "poppler specifically", so
these tests pin the whole surface:

* every in-repo ``*_VERSION`` constant the package exports is on the receipt;
* every external engine that can change output is on the receipt;
* the receipt serializer cannot drift from the dataclass it serializes;
* the per-file sidecar cannot drift from the report.

A test that only asserted ``"poppler_version" in info`` would have let the next
unreported input through, which is exactly how this one got here.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import fields

import pytest

import docpluck
from docpluck import get_version_info
from docpluck.batch import (
    ExtractionFileResult,
    ExtractionReport,
    count_greek_chars,
    count_replacement_chars,
    extract_to_dir,
)
from docpluck.version import (
    _PDFTOTEXT_VERSION_RE,
    _resolve_engine_version,
    _resolve_pdftotext,
)


# ─── A-1: the version surface is complete ──────────────────────────────────

class TestVersionInfoCompleteness:
    #: Every key a consumer is entitled to pin on. Grouped by why it is here.
    IN_REPO_KEYS = {
        "version",
        "git_sha",
        "normalize_version",
        "sectioning_version",
        "table_extraction_version",
    }
    EXTERNAL_ENGINE_KEYS = {
        "pdftotext_version",
        "pdftotext_engine",
        "poppler_version",
        "pdfplumber_version",
        "camelot_version",
    }

    def test_reports_every_in_repo_pipeline_version(self):
        info = get_version_info()
        assert self.IN_REPO_KEYS <= set(info)
        assert info["version"] == docpluck.__version__
        assert info["normalize_version"] == docpluck.NORMALIZATION_VERSION
        assert info["sectioning_version"] == docpluck.SECTIONING_VERSION
        assert info["table_extraction_version"] == docpluck.TABLE_EXTRACTION_VERSION

    def test_reports_every_external_engine(self):
        """The 2026-08-07 incident: a SHA does not pin the pdftotext binary."""
        info = get_version_info()
        assert self.EXTERNAL_ENGINE_KEYS <= set(info)

    def test_no_exported_version_constant_is_missing_from_the_receipt(self):
        """Structural guard: adding a ``*_VERSION`` export must extend the receipt.

        This is the test that generalises the incident. Any future pipeline
        version constant exported from ``docpluck`` (the next ``FIGURES_VERSION``,
        say) fails here until it is added to ``get_version_info()``, instead of
        silently shipping another unpinnable input.
        """
        # Constant name -> receipt key. Matching by KEY, not by value: a
        # value-match would pass if a new constant merely happened to hold the
        # same string as an existing one, which is exactly the silent gap.
        # Adding a constant without a mapping here fails the test by design.
        constant_to_key = {
            "NORMALIZATION_VERSION": "normalize_version",
            "SECTIONING_VERSION": "sectioning_version",
            "TABLE_EXTRACTION_VERSION": "table_extraction_version",
        }
        exported = {n for n in docpluck.__all__ if n.endswith("_VERSION")}
        assert exported, "sanity: the package should export version constants"

        unmapped = exported - set(constant_to_key)
        assert not unmapped, (
            f"new exported version constant(s) {unmapped} must be added to "
            "get_version_info() and to this test's mapping"
        )

        info = get_version_info()
        for name, key in constant_to_key.items():
            assert key in info, f"{name} is not on the receipt (expected key {key!r})"
            assert info[key] == getattr(docpluck, name)

    def test_pdftotext_version_is_resolved_not_a_placeholder(self):
        """On a machine with poppler installed (CI + dev), this must be real."""
        version, engine = _resolve_pdftotext()
        if engine == "unknown":
            pytest.skip("no pdftotext binary on PATH")
        assert engine in ("poppler", "xpdf")
        assert re.match(r"^\d+\.", version), f"unparsed pdftotext version: {version!r}"

    def test_poppler_key_is_none_under_a_non_poppler_engine(self, monkeypatch):
        """``poppler_version`` must never carry an Xpdf version.

        Reporting one would be a false provenance claim: the two engines differ
        behaviourally (Xpdf 4.x emits ``\\n\\n`` paragraph breaks where poppler
        emits ``\\n``), so a downstream pinning ``poppler_version`` would record
        a value that means something else entirely.
        """
        monkeypatch.setattr(
            "docpluck.version._resolve_pdftotext", lambda: ("4.00", "xpdf")
        )
        info = get_version_info()
        assert info["pdftotext_version"] == "4.00"
        assert info["pdftotext_engine"] == "xpdf"
        assert info["poppler_version"] is None

    @pytest.mark.parametrize(
        "stdout, stderr, returncode, expected",
        [
            # Real poppler 24.08.0 banner: on stderr, and it carries Xpdf's
            # inherited "Glyph & Cog" line, so testing for Xpdf first would
            # misclassify every poppler install.
            (
                "",
                "pdftotext version 24.08.0\n"
                "Copyright 2005-2024 The Poppler Developers - http://poppler.freedesktop.org\n"
                "Copyright 1996-2011, 2022 Glyph & Cog, LLC\n",
                0,
                ("24.08.0", "poppler"),
            ),
            # Xpdf 4.00: no poppler line, and it exits NON-ZERO. Gating on the
            # return code would report "unknown" for exactly the engine whose
            # identity matters most (it emits \n\n paragraph breaks).
            (
                "",
                "pdftotext version 4.00\nCopyright 1996-2022 Glyph & Cog, LLC\n",
                99,
                ("4.00", "xpdf"),
            ),
            # A build that banners on stdout must still be recognised.
            ("pdftotext version 22.02.0 (poppler)\n", "", 0, ("22.02.0", "poppler")),
            # Unparseable output degrades to unknown rather than guessing.
            ("", "some other tool\n", 0, ("unknown", "unknown")),
        ],
    )
    def test_engine_detection(self, monkeypatch, stdout, stderr, returncode, expected):
        class _Completed:
            pass

        proc = _Completed()
        proc.stdout, proc.stderr, proc.returncode = stdout, stderr, returncode
        monkeypatch.setattr(
            "docpluck.version.subprocess.run", lambda *a, **k: proc
        )
        _resolve_pdftotext.cache_clear()
        try:
            assert _resolve_pdftotext() == expected
        finally:
            _resolve_pdftotext.cache_clear()

    def test_missing_binary_degrades_to_unknown(self, monkeypatch):
        def _boom(*a, **k):
            raise FileNotFoundError("pdftotext")

        monkeypatch.setattr("docpluck.version.subprocess.run", _boom)
        _resolve_pdftotext.cache_clear()
        try:
            assert _resolve_pdftotext() == ("unknown", "unknown")
        finally:
            _resolve_pdftotext.cache_clear()

    def test_version_regex_matches_both_engine_banners(self):
        assert _PDFTOTEXT_VERSION_RE.search("pdftotext version 24.08.0").group(1) == "24.08.0"
        assert _PDFTOTEXT_VERSION_RE.search("pdftotext version 4.00").group(1) == "4.00"

    def test_engine_version_prefers_the_imported_module_over_metadata(
        self, monkeypatch
    ):
        """Report the code that will actually run, not what is merely installed.

        A shadowing module, an editable install pointing elsewhere, or a
        vendored copy makes distribution metadata disagree with the imported
        module. Metadata would then be a confidently wrong provenance value.
        """
        import types

        fake = types.ModuleType("pdfplumber")
        fake.__version__ = "9.9.9-shadowed"
        monkeypatch.setitem(sys.modules, "pdfplumber", fake)
        assert _resolve_engine_version("pdfplumber", "pdfplumber") == "9.9.9-shadowed"

    def test_engine_version_falls_back_to_metadata_without_importing(
        self, monkeypatch
    ):
        monkeypatch.delitem(sys.modules, "pdfplumber", raising=False)
        resolved = _resolve_engine_version("pdfplumber", "pdfplumber")
        assert re.match(r"^\d+\.", resolved), resolved
        assert "pdfplumber" not in sys.modules, "must not import to read a version"

    def test_absent_engine_is_reported_as_not_installed(self, monkeypatch):
        monkeypatch.delitem(sys.modules, "definitely-not-a-real-pkg", raising=False)
        assert (
            _resolve_engine_version("definitely_not_a_real_pkg", "definitely-not-a-real-pkg")
            == "not installed"
        )

    def test_version_info_is_json_serializable(self):
        """Receipts get written to disk; a non-serializable value breaks them."""
        json.dumps(get_version_info())

    def test_returns_a_fresh_dict_each_call(self):
        a = get_version_info()
        a["version"] = "mutated"
        assert get_version_info()["version"] == docpluck.__version__


# ─── A-1: the report carries the same provenance ───────────────────────────

class TestReportProvenance:
    def test_report_has_a_field_for_every_version_info_key(self):
        """The receipt must not be a lossy projection of the version surface."""
        info = get_version_info()
        field_names = {f.name for f in fields(ExtractionReport)}
        # `version` is spelled `docpluck_version` on the report (historic, and
        # part of its public JSON shape); everything else matches by name.
        expected = (set(info) - {"version"}) | {"docpluck_version"}
        assert expected <= field_names, f"missing: {expected - field_names}"

    def test_to_dict_cannot_drift_from_the_dataclass(self):
        """The serializer used to hand-enumerate keys and silently drop new ones."""
        report = ExtractionReport(
            docpluck_version="x", normalize_version="y", git_sha="z",
            level="academic", out_dir="/tmp/out",
        )
        assert {f.name for f in fields(ExtractionReport)} == set(report.to_dict())

    def test_to_dict_still_rounds_elapsed_seconds(self):
        report = ExtractionReport(
            docpluck_version="x", normalize_version="y", git_sha="z",
            level="academic", out_dir="/tmp/out",
        )
        report.elapsed_seconds = 1.23456789
        assert report.to_dict()["elapsed_seconds"] == 1.235


# ─── The serializer-drift class, package-wide ──────────────────────────────

class TestNoSerializerDropsAField:
    """Generalises the ``to_dict()`` drift beyond the class that surfaced it.

    A hand-enumerated key list is individually correct on the day it is
    written and silently wrong the moment a field is added beside it. Every
    unit passes; the value just never reaches disk.
    """

    def test_normalization_report_serializes_column_interleave_pages(self):
        """Regression: the field was populated, documented, and never serialized.

        ``_detect_column_interleave_pages`` fills it, and
        ``extract_columns`` documents ``NormalizationReport.column_interleave_pages``
        as the canonical source of the signal — but ``to_dict()`` omitted it,
        so any consumer reading the serialized report saw a complete-looking
        object with the signal missing.
        """
        from docpluck.normalize import NormalizationReport

        report = NormalizationReport(level="academic")
        report.column_interleave_pages = (3, 7)
        assert report.to_dict()["column_interleave_pages"] == [3, 7]

    @pytest.mark.parametrize(
        "factory",
        [
            pytest.param(
                lambda: __import__(
                    "docpluck.normalize", fromlist=["NormalizationReport"]
                ).NormalizationReport(level="academic"),
                id="NormalizationReport",
            ),
            pytest.param(
                lambda: ExtractionReport(
                    docpluck_version="x", normalize_version="y", git_sha="z",
                    level="academic", out_dir="/tmp/out",
                ),
                id="ExtractionReport",
            ),
        ],
    )
    def test_to_dict_covers_every_declared_field(self, factory):
        instance = factory()
        declared = {f.name for f in fields(instance)}
        serialized = set(instance.to_dict())
        assert not declared - serialized, (
            f"{type(instance).__name__}.to_dict() drops "
            f"{sorted(declared - serialized)}"
        )

    def test_serialized_reports_are_json_round_trippable(self):
        from docpluck.normalize import NormalizationReport

        report = NormalizationReport(level="academic")
        report.footnote_spans = ((1, 2), (3, 4))
        report.column_interleave_pages = (3,)
        # Tuples must already be lists, so a Python-side read and a
        # post-JSON read agree.
        d = report.to_dict()
        assert d == json.loads(json.dumps(d))


# ─── A-2: per-file quality signals ─────────────────────────────────────────

class TestQualitySignals:
    def test_counts_replacement_characters(self):
        assert count_replacement_chars("clean text") == 0
        assert count_replacement_chars("a�b�c") == 2

    def test_counts_greek_across_both_blocks(self):
        # Greek and Coptic (U+0370-03FF): eta, beta, chi, sigma, alpha.
        assert count_greek_chars("η β χ σ α") == 5
        # Greek Extended (U+1F00-1FFF), polytonic.
        assert count_greek_chars("ἀἁ") == 2
        # Latin look-alikes and subscript/superscript digits are not Greek.
        assert count_greek_chars("p = .05, n2 = .12, abc") == 0
        # The realistic case this exists for.
        assert count_greek_chars("η²ₚ = .000, 95% CI [.000, .003]") == 1

    def test_file_result_exposes_both_signals(self):
        field_names = {f.name for f in fields(ExtractionFileResult)}
        assert {"n_replacement_chars", "n_greek_chars"} <= field_names


# ─── End-to-end: the written artefacts actually carry all of it ────────────

def _tiny_pdf_bytes() -> bytes:
    """A minimal one-page PDF with extractable Greek + ASCII text."""
    import io
    pdfplumber = pytest.importorskip("pdfplumber")  # noqa: F841
    reportlab = pytest.importorskip("reportlab")  # noqa: F841
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "Results: F(1, 98) = 4.21, p = .043.")
    c.showPage()
    c.save()
    return buf.getvalue()


class TestWrittenReceiptAndSidecar:
    """A field that exists on the dataclass but never reaches disk is not shipped."""

    @pytest.fixture()
    def run(self, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(_tiny_pdf_bytes())
        out = tmp_path / "out"
        report = extract_to_dir([pdf], out)
        assert report.n_ok == 1, report.results[0].error
        return report, out

    def test_receipt_on_disk_carries_the_external_engine_versions(self, run):
        report, out = run
        receipt_path = report.write_receipt(out / "_receipt.json")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        for key in TestVersionInfoCompleteness.EXTERNAL_ENGINE_KEYS:
            assert key in receipt, f"receipt is missing {key}"
        assert receipt["pdftotext_version"] == get_version_info()["pdftotext_version"]

    def test_sidecar_carries_provenance_and_quality_signals(self, run):
        _report, out = run
        sidecar = json.loads((out / "paper.json").read_text(encoding="utf-8"))
        required = (
            TestVersionInfoCompleteness.IN_REPO_KEYS
            | TestVersionInfoCompleteness.EXTERNAL_ENGINE_KEYS
        ) - {"version"}  # spelled `docpluck_version` here
        required |= {"docpluck_version", "n_replacement_chars", "n_greek_chars"}
        missing = required - set(sidecar)
        assert not missing, f"sidecar is missing {sorted(missing)}"
        # Backwards compatibility: the pre-2026-08-07 sidecar keys survive.
        for key in (
            "source", "method", "level", "normalize_version", "docpluck_version",
            "git_sha", "n_chars_raw", "n_chars_normalized", "steps_changed",
            "changes_made",
        ):
            assert key in sidecar, f"sidecar dropped legacy key {key}"

    def test_sidecar_reports_the_true_success_status(self, run):
        """Regression (codex, 2026-08-07): the sidecar recorded ``ok: false``.

        It serialized the result before ``ok`` was set, so every successful
        extraction shipped a sidecar contradicting both the written ``.txt``
        and the report — a wrong value on disk, not a missing one.
        """
        _report, out = run
        sidecar = json.loads((out / "paper.json").read_text(encoding="utf-8"))
        assert sidecar["ok"] is True
        assert sidecar["error"] is None

    def test_sidecar_has_no_bare_version_key(self, run):
        """A generic ``version`` beside five ``*_version`` keys invites misreads."""
        _report, out = run
        sidecar = json.loads((out / "paper.json").read_text(encoding="utf-8"))
        assert "version" not in sidecar
        assert sidecar["docpluck_version"] == docpluck.__version__

    def test_sidecar_does_not_report_a_zero_elapsed_time(self, run):
        """`elapsed_seconds` is not final when the sidecar is written.

        Emitting it there would record a 0.0 that reads as a measurement.
        """
        _report, out = run
        sidecar = json.loads((out / "paper.json").read_text(encoding="utf-8"))
        assert "elapsed_seconds" not in sidecar
