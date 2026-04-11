"""
Batch extraction helper for directory-level runs.

MetaESCI, Scimeto, and ESCImate all want the same "walk a list of PDFs,
normalize them, drop a sidecar, and give me a receipt" pattern. Instead of
each downstream re-implementing it, :func:`extract_to_dir` lives here and
returns an :class:`ExtractionReport` that doubles as a reproducibility
receipt (``docpluck_version``, ``normalize_version``, ``git_sha``, per-file
status).

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
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Optional, Union

from .extract import extract_pdf_file
from .normalize import NormalizationLevel, normalize_text
from .version import get_version_info


@dataclass
class ExtractionFileResult:
    path: str
    ok: bool
    method: Optional[str] = None
    n_chars_raw: int = 0
    n_chars_normalized: int = 0
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
    n_total: int = 0
    n_ok: int = 0
    n_failed: int = 0
    elapsed_seconds: float = 0.0
    results: list[ExtractionFileResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "docpluck_version": self.docpluck_version,
            "normalize_version": self.normalize_version,
            "git_sha": self.git_sha,
            "level": self.level,
            "out_dir": self.out_dir,
            "n_total": self.n_total,
            "n_ok": self.n_ok,
            "n_failed": self.n_failed,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "results": [asdict(r) for r in self.results],
        }

    def write_receipt(self, path: Union[str, Path]) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return out


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

    report = ExtractionReport(
        docpluck_version=info["version"],
        normalize_version=info["normalize_version"],
        git_sha=info["git_sha"],
        level=level.value if isinstance(level, NormalizationLevel) else str(level),
        out_dir=str(out),
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
                result.normalize_steps_changed = list(
                    getattr(norm_report, "steps_changed", norm_report.steps_applied)
                )

                text_path = out / f"{p.stem}.txt"
                text_path.write_text(normalized, encoding="utf-8")

                if write_sidecar:
                    sidecar = {
                        "source": str(p),
                        "method": method,
                        "level": level.value if isinstance(level, NormalizationLevel) else str(level),
                        "normalize_version": info["normalize_version"],
                        "docpluck_version": info["version"],
                        "git_sha": info["git_sha"],
                        "n_chars_raw": result.n_chars_raw,
                        "n_chars_normalized": result.n_chars_normalized,
                        "steps_changed": result.normalize_steps_changed,
                        "changes_made": dict(norm_report.changes_made),
                    }
                    sidecar_path = out / f"{p.stem}.json"
                    sidecar_path.write_text(
                        json.dumps(sidecar, indent=2), encoding="utf-8"
                    )

                result.ok = True
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
