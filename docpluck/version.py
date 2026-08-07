"""
Version introspection helper.

Exposes :func:`get_version_info`, which returns a machine-readable dict of
everything that can change docpluck's output, for batch runners that record an
immutable "bundle receipt" alongside their outputs. See MetaESCI request D3.

Completeness is the whole point of this module: a receipt that omits an input
is worse than no receipt, because a downstream comparing two runs with
identical pins concludes the difference must be in its own code. The surface
therefore covers three classes of input, and every one of them must be here:

1. **docpluck's own version** — ``version``, ``git_sha``.
2. **In-repo pipeline versions** that are bumped independently of the package
   version — ``normalize_version``, ``sectioning_version``,
   ``table_extraction_version``. Any future ``*_VERSION`` constant added to the
   package belongs here on the same commit that introduces it.
3. **External engines that docpluck does not vendor** — the poppler/Xpdf
   ``pdftotext`` binary, pdfplumber, camelot. A docpluck SHA alone does *not*
   pin extraction: ``method=pdftotext_default`` shells out to whatever
   ``pdftotext`` is on PATH.

The external-engine keys exist because of a real, measured incident (MetaESCI,
2026-08-07): the same docpluck SHA (``a5c02ef``) run against the same PDF
(``10.1098/rsos.202336``) produced 49,091 normalized chars in April and 50,101
in August, because the system poppler binary was replaced on 2026-05-14.
Nothing in docpluck's recorded provenance made that detectable.

``pdftotext_engine`` is reported separately from ``pdftotext_version`` because
poppler and Xpdf are *behaviourally* different, not merely differently
versioned: Xpdf 4.x emits ``\\n\\n`` paragraph breaks where poppler emits a
single ``\\n``, which every line-level post-processor in ``render.py`` has to
cope with. A bare version number cannot distinguish them (both call themselves
"pdftotext version <N>").
"""

from __future__ import annotations

import re
import subprocess
import sys
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version as _dist_version
from pathlib import Path

UNKNOWN = "unknown"

#: External Python engines we report, keyed by receipt key. The value is
#: ``(import_name, distribution_name)`` — they differ for camelot, which
#: imports as ``camelot`` from the ``camelot-py`` distribution.
_ENGINE_MODULES = {
    "pdfplumber_version": ("pdfplumber", "pdfplumber"),
    "camelot_version": ("camelot", "camelot-py"),
}

# "pdftotext version 24.08.0" / "pdftotext version 4.00" — both engines use
# this exact prefix, which is why the version alone cannot identify the engine.
_PDFTOTEXT_VERSION_RE = re.compile(r"pdftotext\s+version\s+(\S+)", re.IGNORECASE)


@lru_cache(maxsize=1)
def _resolve_git_sha() -> str:
    """Best-effort resolution of the docpluck git SHA.

    Returns ``"unknown"`` if docpluck was installed from a wheel, from PyPI,
    or from a directory that is not a git checkout. Never raises.
    """
    pkg_dir = Path(__file__).resolve().parent
    repo_root = pkg_dir.parent
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip() or UNKNOWN
    except Exception:
        pass
    return UNKNOWN


@lru_cache(maxsize=1)
def _resolve_pdftotext() -> tuple[str, str]:
    """Best-effort resolution of the ``pdftotext`` binary's version and engine.

    Returns ``(version, engine)`` where ``engine`` is one of ``"poppler"``,
    ``"xpdf"``, or ``"unknown"``. Both are ``"unknown"`` when the binary is
    absent or unparseable. Never raises.

    Implementation notes, each of which is load-bearing:

    * ``pdftotext -v`` writes its banner to **stderr**, not stdout (verified on
      poppler 24.08.0). We read *both* streams and concatenate, so a build that
      chooses stdout is still recognised.
    * The **return code is deliberately ignored**. Xpdf's ``pdftotext -v``
      prints the banner and then exits non-zero (it treats the invocation as a
      usage error). Gating on ``returncode == 0`` would report ``"unknown"``
      for exactly the engine whose identity matters most.
    * Poppler's banner also carries the ``Glyph & Cog, LLC`` copyright line
      inherited from Xpdf, so poppler must be tested for **first**; a
      ``Glyph & Cog`` match alone does not mean Xpdf.
    """
    try:
        result = subprocess.run(
            ["pdftotext", "-v"],
            capture_output=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        return UNKNOWN, UNKNOWN

    banner = f"{result.stderr or ''}\n{result.stdout or ''}"

    match = _PDFTOTEXT_VERSION_RE.search(banner)
    resolved = match.group(1) if match else UNKNOWN

    lowered = banner.lower()
    if "poppler" in lowered:
        engine = "poppler"
    elif "xpdf" in lowered or "glyph & cog" in lowered:
        engine = "xpdf"
    else:
        engine = UNKNOWN

    return resolved, engine


def _resolve_engine_version(import_name: str, dist_name: str) -> str:
    """Version of an external Python engine, or ``"not installed"``.

    Prefers the ``__version__`` of the module **already imported into this
    process**, because that is the code docpluck will actually run. Installed
    distribution metadata can disagree with it — a shadowing module earlier on
    ``sys.path``, an editable install pointing elsewhere, or a module imported
    from a vendored copy all produce a metadata version that never executes.
    Reporting that would be a confidently wrong provenance value, which is
    worse than none.

    Falls back to ``importlib.metadata`` when the module is not yet imported,
    rather than importing it: importing camelot pulls in OpenCV and is
    expensive, and ``get_version_info()`` runs on every batch and on
    ``docpluck --version``.
    """
    module = sys.modules.get(import_name)
    if module is not None:
        reported = getattr(module, "__version__", None)
        if isinstance(reported, str) and reported:
            return reported

    try:
        return _dist_version(dist_name)
    except PackageNotFoundError:
        return "not installed"
    except Exception:
        return UNKNOWN


def get_version_info() -> dict:
    """Return a dict with every version input that can change docpluck's output.

    Keys:
        version:                 PEP 440 library version (matches ``pyproject.toml``).
        normalize_version:       ``NORMALIZATION_VERSION`` from ``normalize.py``.
        sectioning_version:      ``SECTIONING_VERSION`` from ``sections/``.
        table_extraction_version: ``TABLE_EXTRACTION_VERSION`` from ``extract_structured.py``.
        git_sha:                 Git SHA of the docpluck checkout, or ``"unknown"``.
        pdftotext_version:       Version reported by the ``pdftotext`` binary on
                                 PATH, or ``"unknown"``.
        pdftotext_engine:        ``"poppler"``, ``"xpdf"``, or ``"unknown"``.
        poppler_version:         Same as ``pdftotext_version`` when the engine is
                                 poppler, else ``None``. Named for the common
                                 case; the pair above is authoritative. It is
                                 ``None`` rather than the version string under
                                 Xpdf because reporting an Xpdf version under a
                                 ``poppler_`` key would be a false provenance
                                 claim.
        pdfplumber_version:      Installed pdfplumber distribution version.
        camelot_version:         Installed ``camelot-py`` distribution version.

    Subprocess-backed values (``git_sha``, the ``pdftotext`` pair) are resolved
    at most once per process and cached. A fresh dict is returned on every
    call, so callers may mutate the result without corrupting the cache.
    """
    from . import __version__
    from .normalize import NORMALIZATION_VERSION
    from .sections import SECTIONING_VERSION
    from .extract_structured import TABLE_EXTRACTION_VERSION

    pdftotext_version, pdftotext_engine = _resolve_pdftotext()

    info = {
        "version": __version__,
        "normalize_version": NORMALIZATION_VERSION,
        "sectioning_version": SECTIONING_VERSION,
        "table_extraction_version": TABLE_EXTRACTION_VERSION,
        "git_sha": _resolve_git_sha(),
        "pdftotext_version": pdftotext_version,
        "pdftotext_engine": pdftotext_engine,
        "poppler_version": pdftotext_version if pdftotext_engine == "poppler" else None,
    }
    for key, (import_name, dist_name) in _ENGINE_MODULES.items():
        info[key] = _resolve_engine_version(import_name, dist_name)
    return info
