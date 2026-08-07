"""
Version introspection helper.

Exposes :func:`get_version_info`, which returns a machine-readable dict of
everything that can change docpluck's output, for batch runners that record an
immutable "bundle receipt" alongside their outputs. See MetaESCI request D3.

Completeness is the whole point of this module: a receipt that omits an input
is worse than no receipt, because a downstream comparing two runs with
identical pins concludes the difference must be in its own code. The surface
therefore covers four classes of input, and every one of them must be here:

1. **docpluck's own version** — ``version``, ``git_sha``.
2. **In-repo pipeline versions** that are bumped independently of the package
   version — ``normalize_version``, ``sectioning_version``,
   ``table_extraction_version``. Any future ``*_VERSION`` constant added to the
   package belongs here on the same commit that introduces it.
3. **The interpreter** — ``python_version`` and ``unicodedata_version``.
   ``normalize.py`` calls ``unicodedata.normalize`` (NFC and NFKC), so the
   Unicode database shipped with CPython is a direct input to normalized text.
4. **External engines that docpluck does not vendor.** A docpluck SHA alone
   does *not* pin extraction — every engine below is replaceable underneath a
   fixed SHA:

   ===================== ====================================================
   ``pdftotext`` binary  the PDF text channel (``method=pdftotext_default``).
                         Resolved from ``PATH`` **once per process**, by
                         :func:`resolve_pdftotext_executable`, which the
                         extraction call sites use too — so ``pdftotext_path``
                         names the binary that actually produced the text
   pdfplumber            the PDF layout channel; pdfminer.six is the text
                         engine underneath it
   camelot               table extraction; its lattice flavor converts pages
                         to images through **pypdfium2** (camelot 2.x's
                         default backend) and finds rules with **OpenCV**
   mammoth               the DOCX channel
   beautifulsoup4/lxml   the HTML channel (``BeautifulSoup(html, "lxml")``)
   ===================== ====================================================

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

Every reported value is **stable within a process** — it must not depend on
whether an engine happens to have been imported yet, or a receipt written before
table extraction would disagree with one written after and manufacture a
phantom change. See :func:`_resolve_engine_version` for what that costs.

``tests/test_provenance_completeness.py`` asserts that every runtime dependency
declared in ``pyproject.toml`` reaches this surface, so adding a dependency
without adding its key fails the suite rather than silently shipping another
unpinnable input.
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
import sys
import unicodedata
from functools import lru_cache
import importlib.util
from importlib.metadata import (
    PackageNotFoundError,
    distribution as _distribution,
    version as _dist_version,
)
from pathlib import Path
from typing import Sequence

UNKNOWN = "unknown"
NOT_INSTALLED = "not installed"

#: External Python engines we report, keyed by receipt key. The value is
#: ``(import_name, candidate_distribution_names)``.
#:
#: Both halves are needed and neither is redundant:
#:
#: * the **import name** differs from the distribution name for four of these
#:   (``camelot``/``camelot-py``, ``cv2``/``opencv-python``, ``bs4``/
#:   ``beautifulsoup4``, ``pdfminer``/``pdfminer.six``);
#: * OpenCV ships under **three mutually exclusive distribution names** and
#:   camelot's ``[cv]`` extra names only one of them. This machine has
#:   ``opencv-python-headless`` installed, so asking metadata for
#:   ``opencv-python`` alone reports "not installed" while ``cv2`` imports
#:   fine — a wrong provenance value, which is the failure mode this whole
#:   module exists to prevent. Candidates are tried in order.
_ENGINE_MODULES: dict[str, tuple[str, tuple[str, ...]]] = {
    # PDF text/layout channel.
    "pdfplumber_version": ("pdfplumber", ("pdfplumber",)),
    "pdfminer_six_version": ("pdfminer", ("pdfminer.six",)),
    # Tables. pypdfium2 and OpenCV are not direct docpluck dependencies but
    # they decide what camelot's lattice flavor sees, so a change in either
    # changes captured tables under a fixed docpluck SHA.
    "camelot_version": ("camelot", ("camelot-py",)),
    "pypdfium2_version": ("pypdfium2", ("pypdfium2",)),
    "opencv_version": (
        "cv2",
        ("opencv-python", "opencv-python-headless", "opencv-contrib-python"),
    ),
    # DOCX channel.
    "mammoth_version": ("mammoth", ("mammoth",)),
    # HTML channel.
    "beautifulsoup4_version": ("bs4", ("beautifulsoup4",)),
    "lxml_version": ("lxml", ("lxml",)),
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
def resolve_pdftotext_executable() -> str:
    """The ``pdftotext`` binary this process will use, as an absolute path.

    **Both the version probe and every extraction call go through this**, so
    the receipt cannot name a different binary from the one that produced the
    text. Resolving ``"pdftotext"`` separately in each place is a real hazard,
    not a theoretical one: a process that changes ``PATH`` between the two —
    or that has more than one poppler/Xpdf build installed — would extract
    with binary B while the receipt swore it used A, which is exactly the
    confidently-wrong provenance value this module exists to prevent.

    Falls back to the bare name ``"pdftotext"`` when ``which`` finds nothing,
    so behaviour is unchanged on a machine where the binary is absent (the
    subprocess then raises ``FileNotFoundError`` as it always did).

    Cached: one process, one binary. A caller that genuinely swaps ``PATH``
    mid-run must call ``.cache_clear()`` on this *and* on
    :func:`_resolve_pdftotext`.
    """
    return shutil.which("pdftotext") or "pdftotext"


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

    Cached for the life of the process: one batch run is one set of engines,
    and re-probing per file would add a subprocess per PDF. A process that
    genuinely swaps its ``PATH`` mid-run can call ``.cache_clear()``.
    """
    try:
        result = subprocess.run(
            [resolve_pdftotext_executable(), "-v"],
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


def _distribution_owning_module(
    import_name: str, candidates: Sequence[str]
) -> str | None:
    """Which candidate distribution owns the module that would be imported.

    Uses ``find_spec`` — which resolves the module's file **without executing
    it** — and matches that path against each candidate's own recorded file
    list (its ``RECORD``), not against the shared ``site-packages`` root.
    Returns ``None`` when the question cannot be answered, so the caller falls
    back to declared order rather than guessing.

    Known limit: if two stale ``.dist-info`` directories both still record the
    same file, first-match wins and the answer may name the superseded wheel.
    That configuration is unresolvable from metadata alone; it is a narrower
    failure than the one this exists to prevent (reporting a distribution that
    is not installed at all).
    """
    try:
        spec = importlib.util.find_spec(import_name)
    except Exception:
        return None
    origin = getattr(spec, "origin", None) if spec is not None else None
    if not origin:
        return None
    try:
        origin_path = Path(origin).resolve()
    except Exception:
        return None

    for name in candidates:
        try:
            files = _distribution(name).files or ()
        except Exception:
            continue
        for f in files:
            try:
                if Path(f.locate()).resolve() == origin_path:
                    return name
            except Exception:
                continue
    return None


def _resolve_engine_version(
    import_name: str, dist_names: str | Sequence[str]
) -> str:
    """Version of an external Python engine, or ``"not installed"``.

    ``dist_names`` accepts a single name or a sequence of candidates. The
    single-string form is normalized rather than iterated: a bare ``str`` is
    itself a sequence, so iterating one would try ``"p"``, ``"d"``, ``"f"``…
    as distribution names and return ``"not installed"`` for a package that is
    plainly installed — a confidently wrong provenance value from a caller
    that did nothing unreasonable.

    Resolution, in order:

    1. **Installed distribution metadata**, which is authoritative here. When
       several candidates are installed (OpenCV ships under three mutually
       exclusive distribution names), the tie is broken by asking which one
       records the file ``find_spec`` would import — ``find_spec`` resolves
       the module without executing it.
    2. **The imported module's ``__version__``**, only when *no* candidate
       distribution is installed at all — a vendored copy or a source tree on
       ``sys.path``. The module is never imported just to read a version:
       importing camelot pulls in OpenCV and pandas, and ``get_version_info()``
       runs on every batch and on ``docpluck --version``.
    3. ``"not installed"``.

    **Why metadata wins, and what that costs.** The obvious alternative —
    prefer the imported module's self-report because "that is the code that
    runs" — makes the answer depend on *when* you ask. OpenCV shows it in one
    process: ``cv2`` self-reports ``"4.13.0"`` while its wheel is
    ``"4.13.0.92"``, so a worker writing a receipt before table extraction and
    another after would record two different values for one unchanged install,
    hiding a real wheel-patch bump (sonnet, 2026-08-07). A provenance value
    that changes with call order is worse than a slightly less precise one.

    The accepted cost, stated rather than hidden: a module that **shadows** an
    installed distribution (an earlier ``sys.path`` entry, an editable install
    pointing elsewhere) is not detected, and the receipt names the installed
    distribution. Detecting it needs a package-root comparison that
    ``importlib.metadata`` does not offer —
    ``distribution(name).locate_file("")`` is the whole ``site-packages``
    directory, so an "is the module inside this distribution" test built on it
    answers *true* for essentially everything and would itself return wrong
    versions (codex, 2026-08-07). A stable slightly-imprecise value beats an
    unstable sometimes-wrong one.
    """
    if isinstance(dist_names, str):
        dist_names = (dist_names,)

    installed: list[tuple[str, str]] = []
    for dist_name in dist_names:
        try:
            installed.append((dist_name, _dist_version(dist_name)))
        except PackageNotFoundError:
            continue
        except Exception:
            return UNKNOWN

    if len(installed) > 1:
        owner = _distribution_owning_module(
            import_name, [name for name, _ in installed]
        )
        if owner is not None:
            installed = [(n, v) for n, v in installed if n == owner] or installed

    if installed:
        return installed[0][1]

    # No metadata anywhere: a vendored copy or a source tree. The module's own
    # self-report is then the only answer there is.
    module = sys.modules.get(import_name)
    module_version = getattr(module, "__version__", None) if module else None
    if isinstance(module_version, str) and module_version:
        return module_version

    return NOT_INSTALLED


def get_version_info() -> dict:
    """Return a dict with every version input that can change docpluck's output.

    Keys:
        version:                  PEP 440 library version (matches ``pyproject.toml``).
        normalize_version:        ``NORMALIZATION_VERSION`` from ``normalize.py``.
        sectioning_version:       ``SECTIONING_VERSION`` from ``sections/``.
        table_extraction_version: ``TABLE_EXTRACTION_VERSION`` from ``extract_structured.py``.
        git_sha:                  Git SHA of the docpluck checkout, or ``"unknown"``.
        python_version:           Running interpreter, e.g. ``"3.14.5"``.
        unicodedata_version:      Unicode database backing ``unicodedata.normalize``,
                                  which ``normalize.py`` applies (NFC/NFKC).
        pdftotext_path:           Absolute path of the ``pdftotext`` binary this
                                  process uses — the same one extraction runs, so
                                  the receipt cannot name a different build.
        pdftotext_version:        Version reported by that binary, or ``"unknown"``.
        pdftotext_engine:         ``"poppler"``, ``"xpdf"``, or ``"unknown"``.
        poppler_version:          Same as ``pdftotext_version`` when the engine is
                                  poppler, else ``None``. Named for the common
                                  case; the pair above is authoritative. It is
                                  ``None`` rather than the version string under
                                  Xpdf because reporting an Xpdf version under a
                                  ``poppler_`` key would be a false provenance
                                  claim.

    Plus one key per external Python engine (see :data:`_ENGINE_MODULES`):
    ``pdfplumber_version``, ``pdfminer_six_version``, ``camelot_version``,
    ``pypdfium2_version``, ``opencv_version``, ``mammoth_version``,
    ``beautifulsoup4_version``, ``lxml_version``. Each reports the version of
    the module already imported when there is one, else the installed
    distribution, else ``"not installed"``.

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
        "python_version": platform.python_version(),
        "unicodedata_version": unicodedata.unidata_version,
        "pdftotext_path": resolve_pdftotext_executable(),
        "pdftotext_version": pdftotext_version,
        "pdftotext_engine": pdftotext_engine,
        "poppler_version": pdftotext_version if pdftotext_engine == "poppler" else None,
    }
    for key, (import_name, dist_names) in _ENGINE_MODULES.items():
        info[key] = _resolve_engine_version(import_name, dist_names)
    return info
