"""
Regression tests for the MetaESCI D3/D5/D6/D7 follow-ups shipped in v1.4.2.

Groups covered:
- D7.1: extract_pdf_file raises FileNotFoundError on missing paths.
- D7.2: NormalizationReport.steps_changed only lists steps that actually
        modified the input.
- D6:   extract_to_dir writes normalized text + sidecar, populates an
        ExtractionReport, and records failures rather than raising.
- D3:   docpluck.get_version_info() + CLI print the version tuple as JSON.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import docpluck
from docpluck import (
    ExtractionReport,
    NormalizationLevel,
    extract_pdf_file,
    extract_to_dir,
    get_version_info,
    normalize_text,
)
from docpluck.cli import main as cli_main

import sys as _sys
_sys.path.insert(0, os.path.dirname(__file__))
from conftest import pdf_available, pdf_path, requires_pdftotext  # noqa: E402


# ─── D7.1: extract_pdf_file error handling ─────────────────────────────────

class TestExtractPdfFile:
    def test_missing_file_raises_clean_error(self, tmp_path: Path):
        missing = tmp_path / "does_not_exist.pdf"
        with pytest.raises(FileNotFoundError, match="does_not_exist.pdf"):
            extract_pdf_file(missing)

    def test_directory_instead_of_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="not a regular file"):
            extract_pdf_file(tmp_path)

    def test_accepts_str_and_path(self, tmp_path: Path):
        missing = tmp_path / "x.pdf"
        # Both string and Path inputs should produce the same error class.
        with pytest.raises(FileNotFoundError):
            extract_pdf_file(str(missing))
        with pytest.raises(FileNotFoundError):
            extract_pdf_file(missing)


# ─── D7.2: NormalizationReport.steps_changed ───────────────────────────────

class TestStepsChanged:
    def test_empty_string_yields_no_changed_steps(self):
        _, report = normalize_text("", NormalizationLevel.academic)
        assert report.steps_changed == []
        # steps_applied still records the pipeline order for diagnostics.
        assert len(report.steps_applied) > 0

    def test_pure_ascii_prose_has_empty_steps_changed(self):
        text = "The participants completed a questionnaire.\n"
        _, report = normalize_text(text, NormalizationLevel.academic)
        assert report.steps_changed == []

    def test_real_stats_record_relevant_changed_steps(self):
        text = "Results showed eta\u00b2 = .054, p = 03 and CI [0.1; 0.5]."
        _, report = normalize_text(text, NormalizationLevel.academic)
        # The input actually needs A2 (dropped decimal), A4 (CI delimiter),
        # A5 (Greek/superscript) — all three should appear.
        assert "A2_dropped_decimal_repair" in report.steps_changed
        assert "A4_ci_delimiter_harmonization" in report.steps_changed
        assert "A5_math_symbol_normalization" in report.steps_changed
        # steps_changed is a strict subset of steps_applied.
        assert set(report.steps_changed).issubset(set(report.steps_applied))

    def test_to_dict_exposes_both_lists(self):
        _, report = normalize_text("hello", NormalizationLevel.academic)
        d = report.to_dict()
        assert "steps_applied" in d
        assert "steps_changed" in d


# ─── D6: extract_to_dir + ExtractionReport ─────────────────────────────────

@requires_pdftotext
class TestExtractToDir:
    def test_missing_file_is_recorded_not_raised(self, tmp_path: Path):
        report = extract_to_dir(
            [tmp_path / "nope.pdf"],
            out_dir=tmp_path / "out",
            level=NormalizationLevel.academic,
        )
        assert isinstance(report, ExtractionReport)
        assert report.n_total == 1
        assert report.n_ok == 0
        assert report.n_failed == 1
        assert "FileNotFoundError" in (report.results[0].error or "")

    def test_receipt_round_trip(self, tmp_path: Path):
        report = extract_to_dir(
            [tmp_path / "nope.pdf"],
            out_dir=tmp_path / "out",
        )
        receipt_path = report.write_receipt(tmp_path / "out" / "_receipt.json")
        assert receipt_path.exists()
        loaded = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert loaded["docpluck_version"] == docpluck.__version__
        assert loaded["n_total"] == 1
        assert loaded["n_failed"] == 1

    def test_real_pdf_happy_path(self, tmp_path: Path):
        if not pdf_available("docpluck"):
            pytest.skip("docpluck test-pdfs not available")
        # Pick any single PDF from the local corpus.
        corpus_dir = Path(pdf_path("docpluck"))
        pdfs = list(corpus_dir.rglob("*.pdf"))
        if not pdfs:
            pytest.skip("no PDFs in docpluck corpus dir")
        report = extract_to_dir(
            [pdfs[0]],
            out_dir=tmp_path / "out",
            level=NormalizationLevel.academic,
        )
        assert report.n_total == 1
        assert report.n_ok == 1
        assert report.n_failed == 0
        # Sidecar + text file were written.
        assert (tmp_path / "out" / f"{pdfs[0].stem}.txt").exists()
        assert (tmp_path / "out" / f"{pdfs[0].stem}.json").exists()
        # Per-file result has the version metadata propagated.
        r0 = report.results[0]
        assert r0.ok is True
        assert r0.n_chars_normalized > 0


# ─── D3: version info + CLI ────────────────────────────────────────────────

class TestVersionInfo:
    def test_get_version_info_has_all_keys(self):
        info = get_version_info()
        assert set(info.keys()) >= {"version", "normalize_version", "git_sha"}
        assert info["version"] == docpluck.__version__

    def test_cli_version_prints_json(self, capsys):
        rc = cli_main(["--version"])
        assert rc == 0
        out = capsys.readouterr().out.strip()
        parsed = json.loads(out)
        assert parsed["version"] == docpluck.__version__
        assert "normalize_version" in parsed
        assert "git_sha" in parsed

    def test_cli_default_is_version(self, capsys):
        rc = cli_main([])
        assert rc == 0
        out = capsys.readouterr().out.strip()
        parsed = json.loads(out)
        assert parsed["version"] == docpluck.__version__

    def test_cli_unknown_arg_returns_nonzero(self, capsys):
        rc = cli_main(["--wat"])
        assert rc == 2
