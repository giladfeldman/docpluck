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

import importlib
import json
import platform
import re
import sys
import tomllib
import unicodedata
from dataclasses import fields
from pathlib import Path

import pytest

import docpluck
from docpluck import get_version_info
from docpluck.batch import (
    _GREEK_RANGES,
    _GREEK_RE,
    ExtractionFileResult,
    ExtractionReport,
    _provenance_kwargs,
    count_greek_chars,
    count_replacement_chars,
    extract_to_dir,
)
from docpluck.version import (
    _ENGINE_MODULES,
    _PDFTOTEXT_VERSION_RE,
    _distribution_owning_module,
    _resolve_engine_version,
    _resolve_pdftotext,
    resolve_pdftotext_executable,
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
    INTERPRETER_KEYS = {
        "python_version",
        # normalize.py calls unicodedata.normalize (NFC/NFKC), so the Unicode
        # database CPython ships with is a direct input to normalized text.
        "unicodedata_version",
    }
    EXTERNAL_ENGINE_KEYS = {
        "pdftotext_version",
        "pdftotext_engine",
        "poppler_version",
        "pdfplumber_version",
        "pdfminer_six_version",
        "camelot_version",
        "pypdfium2_version",
        "opencv_version",
        "mammoth_version",
        "beautifulsoup4_version",
        "lxml_version",
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

    def test_reports_the_interpreter_and_its_unicode_database(self):
        info = get_version_info()
        assert self.INTERPRETER_KEYS <= set(info)
        assert info["python_version"] == platform.python_version()
        assert info["unicodedata_version"] == unicodedata.unidata_version

    def test_every_declared_runtime_dependency_reaches_the_receipt(self):
        """Structural guard against the ORIGINAL defect recurring by a new route.

        The incident was an output-determining input nobody had listed. Listing
        engines by hand reproduces that risk one dependency later, so this
        derives the expectation from ``pyproject.toml``: every distribution
        docpluck declares as a runtime dependency (core, plus the non-dev
        extras that back the DOCX and HTML channels) must have a key on the
        receipt. Adding a dependency without adding its key fails here.

        Dev/test-only extras are excluded — pytest's version cannot change a
        user's extraction output.
        """
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        if not pyproject.exists():  # installed-wheel test run
            pytest.skip("pyproject.toml not available (not a source checkout)")
        cfg = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        project = cfg["project"]

        declared = list(project.get("dependencies", []))
        for extra, deps in project.get("optional-dependencies", {}).items():
            if extra == "dev":
                continue
            declared += deps

        # "camelot-py[cv]>=0.11.0,<3.0" -> "camelot-py"
        dist_names = {
            re.split(r"[\[><=!;~ ]", spec, maxsplit=1)[0].strip()
            for spec in declared
        }
        assert dist_names, "sanity: pyproject must declare dependencies"

        reported = {
            dist
            for _key, (_imp, dists) in _ENGINE_MODULES.items()
            for dist in dists
        }
        missing = dist_names - reported
        assert not missing, (
            f"runtime dependencies absent from get_version_info(): {sorted(missing)} "
            "— add them to version._ENGINE_MODULES"
        )

        # And every engine key actually lands in the returned dict.
        info = get_version_info()
        assert set(_ENGINE_MODULES) <= set(info)

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

    def test_installed_metadata_wins_over_the_modules_self_report(
        self, monkeypatch, tmp_path
    ):
        """Metadata is authoritative when the distribution is installed.

        This is the property that makes the value order-stable, and it is a
        deliberate trade: a module that *shadows* an installed distribution is
        not detected, and the receipt names the installed one. Detecting it
        needs a package-root comparison ``importlib.metadata`` does not offer
        (``locate_file("")`` is the whole ``site-packages``), and an attempt
        built on that returned wrong versions and reintroduced order
        dependence (codex, 2026-08-07). Documented in
        ``_resolve_engine_version``; asserted here so it stays a decision.
        """
        import types
        from importlib.metadata import version as dist_version

        shadow_file = tmp_path / "shadow" / "pdfplumber" / "__init__.py"
        shadow_file.parent.mkdir(parents=True)
        shadow_file.write_text("", encoding="utf-8")

        fake = types.ModuleType("pdfplumber")
        fake.__version__ = "9.9.9-shadowed"
        fake.__file__ = str(shadow_file)
        monkeypatch.setitem(sys.modules, "pdfplumber", fake)

        assert _resolve_engine_version("pdfplumber", "pdfplumber") == dist_version(
            "pdfplumber"
        )

    def test_a_module_without_any_distribution_reports_its_own_version(
        self, monkeypatch
    ):
        """Vendored copy / source tree on ``sys.path``: the self-report is all there is."""
        import types

        fake = types.ModuleType("vendored_engine")
        fake.__version__ = "3.2.1-vendored"
        monkeypatch.setitem(sys.modules, "vendored_engine", fake)
        assert (
            _resolve_engine_version("vendored_engine", ("no-such-distribution",))
            == "3.2.1-vendored"
        )

    def test_engine_version_falls_back_to_metadata_without_importing(
        self, monkeypatch
    ):
        monkeypatch.delitem(sys.modules, "pdfplumber", raising=False)
        resolved = _resolve_engine_version("pdfplumber", ("pdfplumber",))
        assert re.match(r"^\d+\.", resolved), resolved
        assert "pdfplumber" not in sys.modules, "must not import to read a version"

    def test_engine_version_does_not_depend_on_import_order(self):
        """A provenance value must not change with WHEN you ask for it.

        Regression (sonnet, 2026-08-07): preferring the imported module's
        ``__version__`` made ``opencv_version`` read ``"4.13.0.92"`` before
        ``cv2`` was imported and ``"4.13.0"`` after — same install, one
        process, two answers. A worker writing a receipt before table
        extraction and another after would have recorded a phantom change and
        hidden a real wheel-patch bump.
        """
        candidates = _ENGINE_MODULES["opencv_version"]
        before = _resolve_engine_version(*candidates)
        try:
            importlib.import_module(candidates[0])
        except ImportError:
            pytest.skip(f"{candidates[0]} not importable")
        after = _resolve_engine_version(*candidates)
        assert before == after, (
            f"reported {before!r} before import and {after!r} after"
        )

    def test_the_expensive_ownership_scan_stays_off_the_normal_path(
        self, monkeypatch
    ):
        """Walking a distribution's file list must not happen per engine.

        An earlier form called ``packages_distributions()`` (6-11 s per call,
        uncached by the stdlib) once per engine, turning ``get_version_info()``
        from milliseconds into ~24 s. Ownership resolution must be reached only
        when several candidate distributions are actually INSTALLED — so making
        it explode must not break the ordinary single-candidate lookups.
        """
        def _explode(*_a, **_k):
            raise AssertionError("ownership scan reached on the normal path")

        monkeypatch.setattr(
            "docpluck.version._distribution_owning_module", _explode
        )
        for key, (import_name, dists) in _ENGINE_MODULES.items():
            installed = sum(
                1 for d in dists
                if _resolve_engine_version(import_name, (d,)) != "not installed"
            )
            if installed > 1:
                continue  # genuinely ambiguous; the scan is warranted there
            assert _resolve_engine_version(import_name, dists)

    def test_absent_engine_is_reported_as_not_installed(self, monkeypatch):
        monkeypatch.delitem(sys.modules, "definitely_not_a_real_pkg", raising=False)
        assert (
            _resolve_engine_version(
                "definitely_not_a_real_pkg", ("definitely-not-a-real-pkg",)
            )
            == "not installed"
        )

    def test_a_bare_string_distribution_name_is_not_iterated_per_character(
        self, monkeypatch
    ):
        """A ``str`` is a sequence, so iterating one tries "p", "d", "f"…

        That returns "not installed" for a plainly-installed package — a
        confidently wrong provenance value from a caller that did nothing
        unreasonable. Both call shapes must agree.
        """
        monkeypatch.delitem(sys.modules, "pdfplumber", raising=False)
        assert _resolve_engine_version(
            "pdfplumber", "pdfplumber"
        ) == _resolve_engine_version("pdfplumber", ("pdfplumber",))
        assert _resolve_engine_version("pdfplumber", "pdfplumber") != "not installed"

    def test_opencv_resolves_under_any_of_its_distribution_names(self, monkeypatch):
        """OpenCV ships as opencv-python / -headless / -contrib, one at a time.

        camelot's ``[cv]`` extra names only ``opencv-python``. A single-name
        lookup reports "not installed" on a headless install while ``cv2``
        imports fine — again a wrong value, not a missing one.
        """
        monkeypatch.delitem(sys.modules, "cv2", raising=False)
        _import_name, candidates = _ENGINE_MODULES["opencv_version"]
        assert len(candidates) >= 3, candidates
        resolved = _resolve_engine_version("cv2", candidates)
        installed_under_any = any(
            _resolve_engine_version("cv2", (c,)) != "not installed"
            for c in candidates
        )
        if installed_under_any:
            assert resolved != "not installed"
            assert re.match(r"^\d+\.", resolved), resolved

    def test_receipt_names_the_binary_extraction_actually_runs(self):
        """The receipt and the extraction must not resolve `pdftotext` separately.

        They used to: `get_version_info()` cached its probe while
        `extract_pdf` re-resolved the bare name from `PATH` on every call, so a
        `PATH` change (or a second poppler/Xpdf build) between the two meant the
        receipt could name binary A while binary B produced the text — a
        confidently wrong provenance value (codex, 2026-08-07). Both now go
        through `resolve_pdftotext_executable()`.
        """
        import docpluck.extract as extract_mod
        import docpluck.extract_columns as columns_mod

        resolved = resolve_pdftotext_executable()
        assert get_version_info()["pdftotext_path"] == resolved
        # Every module that shells out to pdftotext must use the same resolver.
        for mod in (extract_mod, columns_mod):
            src = Path(mod.__file__).read_text(encoding="utf-8")
            assert '"pdftotext"' not in src, (
                f"{mod.__name__} hard-codes the bare binary name; it must call "
                "resolve_pdftotext_executable() so the receipt cannot diverge"
            )
            assert "resolve_pdftotext_executable" in src

    def test_missing_binary_still_falls_back_to_the_bare_name(self, monkeypatch):
        """A machine without pdftotext must behave exactly as it always did."""
        monkeypatch.setattr("docpluck.version.shutil.which", lambda _n: None)
        resolve_pdftotext_executable.cache_clear()
        try:
            assert resolve_pdftotext_executable() == "pdftotext"
        finally:
            resolve_pdftotext_executable.cache_clear()

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

    def test_report_carries_the_actual_version_values_not_defaults(self):
        """A field can exist and still never be filled.

        ``extract_to_dir`` splats ``get_version_info()`` into the constructor,
        so this asserts the value round-trips rather than sitting at its
        ``"unknown"`` default — the write-only-field failure mode.
        """
        info = get_version_info()
        report = ExtractionReport(
            level="academic", out_dir="/tmp/out", **_provenance_kwargs(info)
        )
        d = report.to_dict()
        for key, value in info.items():
            field_name = "docpluck_version" if key == "version" else key
            assert d[field_name] == value, f"{field_name} did not round-trip"

    def test_an_unmapped_version_info_key_fails_loudly(self):
        """A new receipt key with no report field must raise, not default.

        Silently defaulting is what makes an incomplete receipt look complete.
        """
        info = get_version_info()
        info["some_future_engine_version"] = "1.0"
        with pytest.raises(TypeError):
            ExtractionReport(
                level="academic", out_dir="/tmp/out", **_provenance_kwargs(info)
            )

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

    def test_section_to_dict_emits_every_field_including_subheadings(self):
        """Regression: ``subheadings`` reached NO consumer surface.

        v1.6.1 added the field, ``sections/core.py`` populates it, tests cover
        it — but ``docpluck sections --format json`` and the service's
        ``/sections`` endpoint had each independently enumerated the nine keys
        that existed beforehand. The feature worked and was invisible.
        """
        from docpluck.sections.types import Section
        from docpluck.sections.taxonomy import Confidence, DetectedVia, SectionLabel

        section = Section(
            label="methods",
            canonical_label=SectionLabel.methods,
            text="body",
            char_start=0,
            char_end=4,
            pages=(1, 2),
            confidence=Confidence.high,
            detected_via=DetectedVia.heading_match,
            heading_text="Method",
            subheadings=("Participants", "Materials"),
        )
        d = section.to_dict()
        assert {f.name for f in fields(Section)} == set(d)
        assert d["subheadings"] == ["Participants", "Materials"]
        # Enums flattened, tuples listed — matches what both surfaces sent.
        assert d["canonical_label"] == SectionLabel.methods.value
        assert d["confidence"] == Confidence.high.value
        assert d["pages"] == [1, 2]
        assert d == json.loads(json.dumps(d))

    def test_cli_sections_json_carries_subheadings(
        self, tmp_path, capsys, monkeypatch
    ):
        """Drives the REAL CLI command, not just the serializer.

        An earlier version of this test built a ``SectionedDocument`` and
        called ``to_dict()`` on it directly — which would have stayed green if
        ``cli.py`` regressed to a hand-enumerated payload, i.e. it would not
        have caught the very defect it exists for (codex, 2026-08-07). It now
        goes through ``_cmd_sections``; only the PDF-bytes-to-document step is
        stubbed, because a synthetic PDF cannot reliably produce a subheading.
        """
        from docpluck import cli as cli_mod
        from docpluck.sections.blocks import BlockHint
        from docpluck.sections.core import partition_into_sections
        from docpluck.sections.types import SectionedDocument

        text = (
            "Method\nbody of methods.\n"
            "Participants\nWe recruited 200 students.\n"
            "Results\nbody of results.\n"
        )

        def hint(t):
            start = text.find(t)
            return BlockHint(
                text=t, char_start=start, char_end=start + len(t), page=1,
                is_heading_candidate=True, heading_strength="strong",
                heading_source="layout",
            )

        # Real detector: the subheading must be produced, not hand-written.
        sections = partition_into_sections(
            text, [hint("Method"), hint("Participants"), hint("Results")],
            source_format="pdf",
        )
        doc = SectionedDocument(
            sections=tuple(sections), normalized_text=text,
            sectioning_version="test", source_format="pdf",
        )
        assert doc.get("methods").subheadings == ("Participants",), (
            "fixture precondition: the detector must attach the subheading"
        )
        # `_cmd_sections` does a function-local `from . import extract_sections`,
        # so the seam is the PACKAGE attribute, not an attribute of `cli`.
        # Patching `cli.extract_sections` would have silently missed
        # (codex, 2026-08-07). `raising=True` is deliberate: if the name ever
        # moves, this fails loudly instead of stubbing nothing.
        monkeypatch.setattr(docpluck, "extract_sections", lambda _blob: doc)

        src = tmp_path / "paper.pdf"
        src.write_bytes(b"%PDF-1.4\n% stub, extract_sections is patched\n")
        rc = cli_mod.main(["sections", str(src), "--format", "json"])
        assert rc == 0

        payload = json.loads(capsys.readouterr().out.strip())
        methods = next(s for s in payload["sections"] if s["label"] == "methods")
        assert methods["subheadings"] == ["Participants"], payload

    def test_sectioned_document_omits_only_the_documented_field(self):
        """The one omission must be a named decision, not an accident."""
        from docpluck.sections.types import SectionedDocument

        doc = SectionedDocument(
            sections=(), normalized_text="abcdef",
            sectioning_version="test", source_format="pdf",
        )
        d = doc.to_dict()
        declared = {f.name for f in fields(SectionedDocument)}
        omitted = declared - set(d)
        assert omitted == set(SectionedDocument._TO_DICT_OMITS)
        # …and the omitted field is still represented, not simply dropped.
        assert d["normalized_text_length"] == 6

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

    def test_greek_regex_matches_the_declared_ranges_exactly(self):
        """The regex is compiled FROM ``_GREEK_RANGES``; prove they agree.

        Exhaustive over every codepoint from just below the first range to
        just above the last, so an off-by-one at any boundary fails. The
        per-character reference loop is the readable definition; the regex is
        the shipped implementation because the loop measured 60x slower.
        """
        def in_ranges(cp: int) -> bool:
            return any(lo <= cp <= hi for lo, hi in _GREEK_RANGES)

        lo_bound = min(lo for lo, _ in _GREEK_RANGES) - 2
        hi_bound = max(hi for _, hi in _GREEK_RANGES) + 2
        mismatches = [
            cp
            for cp in range(lo_bound, hi_bound + 1)
            if bool(_GREEK_RE.fullmatch(chr(cp))) != in_ranges(cp)
        ]
        assert not mismatches, [hex(c) for c in mismatches[:10]]

        # Boundaries, spelled out so a failure names the edge.
        assert count_greek_chars("ͯ") == 0  # just below Greek and Coptic
        assert count_greek_chars("Ͱ") == 1  # first
        assert count_greek_chars("Ͽ") == 1  # last
        assert count_greek_chars("Ѐ") == 0  # Cyrillic starts here
        assert count_greek_chars("ỿ") == 0  # just below Greek Extended
        assert count_greek_chars("ἀ") == 1
        assert count_greek_chars("῿") == 1
        assert count_greek_chars(" ") == 0

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
