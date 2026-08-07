"""
Batch extraction helper for directory-level runs.

MetaESCI, Scimeto, and ESCImate all want the same "walk a list of PDFs,
normalize them, drop a sidecar, and give me a receipt" pattern. Instead of
each downstream re-implementing it, :func:`extract_to_dir` lives here and
returns an :class:`ExtractionReport` that doubles as a reproducibility
receipt: everything :func:`docpluck.get_version_info` reports — docpluck's own
version and SHA, the in-repo pipeline versions, **and the external engines
(pdftotext/poppler, pdfplumber, camelot) that a docpluck SHA does not pin** —
plus per-file status and quality signals.

Example::

    from docpluck import extract_to_dir, NormalizationLevel

    report = extract_to_dir(
        pdf_paths=list(Path("pdfs").glob("*.pdf")),
        out_dir="normalized_text",
        level=NormalizationLevel.academic,
    )
    print(f"{report.n_ok}/{report.n_total} ok, {report.elapsed_seconds:.1f}s")
    report.write_receipt("normalized_text/_docpluck_receipt.json")
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Optional, Union

from .extract import extract_pdf_file
from .normalize import NormalizationLevel, normalize_text
from .version import UNKNOWN, get_version_info

#: ``get_version_info()`` key -> :class:`ExtractionReport` field name.
#: Identity for every key except ``version``, which the report has always
#: spelled ``docpluck_version`` and which downstream receipts depend on.
_REPORT_FIELD_FOR_INFO_KEY = {"version": "docpluck_version"}


def _provenance_kwargs(info: dict) -> dict:
    """Translate ``get_version_info()`` into ``ExtractionReport`` kwargs.

    Splatted into the constructor rather than assigned field by field: a key
    added to ``get_version_info()`` without a matching field then raises
    ``TypeError`` on the first batch run, which is loud and immediate. The
    field-by-field alternative silently leaves the new field at its
    ``"unknown"`` default — a receipt that looks complete and is not, i.e.
    precisely the defect this surface exists to prevent.
    """
    return {_REPORT_FIELD_FOR_INFO_KEY.get(k, k): v for k, v in info.items()}


#: Unicode ranges counted as Greek by :func:`count_greek_chars`. Greek and
#: Coptic (U+0370–U+03FF) plus Greek Extended (U+1F00–U+1FFF, polytonic).
#: The first block carries a handful of Coptic-only letters (U+03E2–U+03EF);
#: they are counted, and they do not occur in the statistical notation this
#: signal exists to measure.
_GREEK_RANGES = ((0x0370, 0x03FF), (0x1F00, 0x1FFF))

#: Compiled FROM :data:`_GREEK_RANGES` rather than written out, so the two
#: cannot drift. A per-character Python loop over these ranges measured **60x
#: slower** than the regex (29 ms vs 0.5 ms on a 50k-char paper — 247 s vs 4 s
#: across MetaESCI's 8,431-document corpus), which is a real cost for a signal
#: computed on every file of every batch.
_GREEK_RE = re.compile(
    "[" + "".join(f"\\u{lo:04X}-\\u{hi:04X}" for lo, hi in _GREEK_RANGES) + "]"
)


def count_replacement_chars(text: str) -> int:
    """Count U+FFFD REPLACEMENT CHARACTER occurrences in ``text``.

    A non-zero count means some glyph was lost before docpluck saw it —
    typically a broken ``ToUnicode`` map, or Xpdf refusing an SMP codepoint.
    Downstreams gate acceptance on this (MetaESCI's G1), so it is recorded on
    the report rather than re-scanned from the written ``.txt``.
    """
    # Escape, not the literal glyph: a literal U+FFFD in source is exactly the
    # character most likely to be mangled by an encoding-unaware tool.
    return text.count("\ufffd")


def count_greek_chars(text: str) -> int:
    """Count Greek letters in ``text`` (see :data:`_GREEK_RANGES`).

    Paired with ``n_chars_normalized`` this gives Greek *density*, which
    downstreams use to detect a PDF whose Greek statistical symbols
    (η, β, χ, σ, α) were dropped or transliterated away.
    """
    return len(_GREEK_RE.findall(text))


@dataclass
class ExtractionFileResult:
    path: str
    ok: bool
    method: Optional[str] = None
    n_chars_raw: int = 0
    n_chars_normalized: int = 0
    #: Quality signals, both measured on the NORMALIZED text — i.e. on exactly
    #: the bytes written to ``<stem>.txt``, not on the raw extraction.
    n_replacement_chars: int = 0
    n_greek_chars: int = 0
    normalize_steps_changed: list[str] = field(default_factory=list)
    error: Optional[str] = None
    elapsed_seconds: float = 0.0


@dataclass
class ExtractionReport:
    """Machine-readable receipt for a batch extraction run.

    Contains the docpluck version metadata, per-file results, and aggregate
    counts. Serializable to JSON via :meth:`to_dict` / :meth:`write_receipt`
    so downstream pipelines can pin reproducibility against a fixed run.
    """

    docpluck_version: str
    normalize_version: str
    git_sha: str
    level: str
    out_dir: str
    # Provenance beyond docpluck's own SHA — one field per get_version_info()
    # key, same spelling (except `version`, which this class has always called
    # `docpluck_version`). See version.py for why an incomplete receipt is
    # worse than none. `extract_to_dir` fills these by **splatting**
    # get_version_info(), so a key added there without a field here raises
    # TypeError on the first batch run instead of silently defaulting.
    sectioning_version: str = UNKNOWN
    table_extraction_version: str = UNKNOWN
    python_version: str = UNKNOWN
    unicodedata_version: str = UNKNOWN
    pdftotext_path: str = UNKNOWN
    pdftotext_version: str = UNKNOWN
    pdftotext_engine: str = UNKNOWN
    poppler_version: Optional[str] = None
    pdfplumber_version: str = UNKNOWN
    pdfminer_six_version: str = UNKNOWN
    camelot_version: str = UNKNOWN
    pypdfium2_version: str = UNKNOWN
    opencv_version: str = UNKNOWN
    mammoth_version: str = UNKNOWN
    beautifulsoup4_version: str = UNKNOWN
    lxml_version: str = UNKNOWN
    n_total: int = 0
    n_ok: int = 0
    n_failed: int = 0
    elapsed_seconds: float = 0.0
    results: list[ExtractionFileResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize the whole report, field-for-field.

        Derived from ``asdict`` rather than a hand-written key list on
        purpose: the previous hand-enumerated version silently dropped any
        field added to the dataclass afterwards, which is the same
        incomplete-provenance failure this class exists to prevent.
        """
        d = asdict(self)
        d["elapsed_seconds"] = round(self.elapsed_seconds, 3)
        return d

    def write_receipt(self, path: Union[str, Path]) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return out


#: Keys of the per-file result that the sidecar deliberately omits.
#: ``path`` is already emitted as ``source``; ``elapsed_seconds`` is not final
#: when the sidecar is written, so emitting it would record a 0.0 that reads
#: as a real measurement; ``normalize_steps_changed`` is emitted under its
#: historic sidecar name ``steps_changed``, and carrying both spellings of one
#: value invites them to drift apart.
_SIDECAR_SKIP_RESULT_FIELDS = ("path", "elapsed_seconds", "normalize_steps_changed")


def _build_sidecar(
    *,
    source: Path,
    level: str,
    info: dict,
    result: ExtractionFileResult,
    changes_made,
) -> dict:
    """Assemble the per-file ``<stem>.json`` sidecar.

    Built from ``info`` and ``result`` wholesale rather than a hand-picked key
    list, so a provenance or quality field added to either cannot land on the
    report while silently missing from the sidecar — that divergence is the
    same incomplete-receipt defect this whole surface exists to prevent.

    ``info["version"]`` is re-keyed to ``docpluck_version`` and the bare
    ``version`` key is dropped: the sidecar's historic shape uses the explicit
    name, and a generic top-level ``version`` in a document that also carries
    four other ``*_version`` keys invites a downstream to read the wrong one.
    """
    provenance = {k: v for k, v in info.items() if k != "version"}
    provenance["docpluck_version"] = info["version"]

    per_file = {
        k: v
        for k, v in asdict(result).items()
        if k not in _SIDECAR_SKIP_RESULT_FIELDS
    }

    return {
        "source": str(source),
        "level": level,
        **provenance,
        **per_file,
        # Historic alias for `normalize_steps_changed`; downstreams read it.
        "steps_changed": result.normalize_steps_changed,
        "changes_made": dict(changes_made),
    }


def extract_to_dir(
    pdf_paths: Iterable[Union[str, Path]],
    out_dir: Union[str, Path],
    level: NormalizationLevel = NormalizationLevel.academic,
    write_sidecar: bool = True,
) -> ExtractionReport:
    """Extract and normalize a collection of PDFs into a directory.

    For each input PDF, writes ``<stem>.txt`` containing normalized text.
    When ``write_sidecar`` is true (default), also writes ``<stem>.json``
    with per-file metadata (method, normalize steps, timings, errors).

    Missing files are recorded as failures on the report — this function
    does not raise on individual file errors, only on argument errors.

    Args:
        pdf_paths: Iterable of PDF paths. Each path must point to a file.
        out_dir: Directory that will receive ``<stem>.txt`` (and sidecars).
            Created if it does not exist.
        level: Normalization level. Defaults to ``academic``.
        write_sidecar: Whether to emit the per-file ``.json`` sidecar.

    Returns:
        :class:`ExtractionReport` with aggregate counts and per-file results.
    """
    info = get_version_info()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    level_str = level.value if isinstance(level, NormalizationLevel) else str(level)

    report = ExtractionReport(
        level=level_str,
        out_dir=str(out),
        **_provenance_kwargs(info),
    )

    batch_start = time.monotonic()
    for p in pdf_paths:
        p = Path(p)
        report.n_total += 1
        file_start = time.monotonic()
        result = ExtractionFileResult(path=str(p), ok=False)

        try:
            raw_text, method = extract_pdf_file(p)
            result.method = method
            result.n_chars_raw = len(raw_text)

            if raw_text.startswith("ERROR:"):
                result.error = raw_text
            else:
                normalized, norm_report = normalize_text(raw_text, level)
                result.n_chars_normalized = len(normalized)
                result.n_replacement_chars = count_replacement_chars(normalized)
                result.n_greek_chars = count_greek_chars(normalized)
                result.normalize_steps_changed = list(
                    getattr(norm_report, "steps_changed", norm_report.steps_applied)
                )

                text_path = out / f"{p.stem}.txt"
                text_path.write_text(normalized, encoding="utf-8")

                # Set BEFORE the sidecar is built: the sidecar serializes
                # `result`, and a sidecar reporting ok=false beside a
                # successfully written .txt is a wrong value on disk.
                result.ok = True

                if write_sidecar:
                    sidecar_path = out / f"{p.stem}.json"
                    sidecar_path.write_text(
                        json.dumps(
                            _build_sidecar(
                                source=p,
                                level=level_str,
                                info=info,
                                result=result,
                                changes_made=norm_report.changes_made,
                            ),
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
        except FileNotFoundError as e:
            result.error = f"FileNotFoundError: {e}"
        except Exception as e:  # noqa: BLE001 — batch runner must never raise
            result.error = f"{type(e).__name__}: {e}"

        result.elapsed_seconds = round(time.monotonic() - file_start, 3)
        report.results.append(result)
        if result.ok:
            report.n_ok += 1
        else:
            report.n_failed += 1

    report.elapsed_seconds = time.monotonic() - batch_start
    return report
