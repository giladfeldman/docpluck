"""
PDF Text Extraction
====================
Primary engine: pdftotext default mode (no -layout flag)
Column correction: pages read across both columns are re-extracted column by column.
(The pdfplumber U+FFFD / SMP recovery fallback was RETIRED 2026-09-24; an
undecodable glyph is now returned as U+FFFD.)

Requires poppler-utils installed on the system:
  - Linux/WSL: apt-get install poppler-utils
  - macOS: brew install poppler
  - Windows: https://github.com/oschwartz10612/poppler-windows/releases

Key design decision: pdftotext default mode (NO -layout flag).
The -layout flag preserves physical column layout, causing column interleaving
that breaks statistical pattern matching. Default mode correctly reconstructs
reading order. Verified on 50 PDFs across 8 citation styles — see BENCHMARKS.md.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union

from .telemetry import record_fallback
from .tempfiles import unlink_temp_pdf
from .version import resolve_pdftotext_executable

def extract_pdf(
    pdf_bytes: bytes,
    *,
    sections: list[str] | None = None,
    max_input_bytes: int | None = None,
    pdftotext_timeout_seconds: int = 120,
) -> tuple[str, str]:
    """Extract text from PDF bytes.

    Uses pdftotext (default reading-order mode). Pages where pdftotext reads
    a two-column layout across both columns are re-extracted column by
    column. An undecodable glyph is returned as U+FFFD, never guessed (the
    earlier pdfplumber recovery fallback was retired 2026-09-24).

    Args:
        pdf_bytes: Raw PDF file content as bytes.
        sections: Optional list of section labels (e.g. ``["abstract",
            "methods"]``) to filter the output. When provided, the full text
            is first extracted, then ``extract_sections`` is called and only
            the requested sections are returned concatenated in document order.
            Pass ``None`` (default) to return the full unfiltered text.

    Returns:
        A tuple of (text, method) where:
          - text: Extracted plain text. When ``sections`` is not None, only the
            text from the requested sections is included. May start with
            "ERROR: ..." if extraction failed — check with
            text.startswith("ERROR:").
          - method: Engine used: ``"pdftotext_default"``, optionally followed by
              ``+column_corrected:<pages>`` or ``+column_correction_failed:<exc>``,
              or ``"error"``. (``pdftotext_default+pdfplumber_recovery`` and
              ``…+pdfplumber_word_patch`` were retired in 2026-09 — see the
              U+FFFD note in the function body.)

    Guardrails:
        max_input_bytes: Optional hard cap for input size. When set and
            ``len(pdf_bytes)`` exceeds it, a ValueError is raised.
        pdftotext_timeout_seconds: Timeout for the pdftotext subprocess.
            Default 120 seconds preserves current behavior.

    Requires:
        pdftotext binary (from poppler-utils) on PATH.

    Example:
        with open("paper.pdf", "rb") as f:
            text, method = extract_pdf(f.read())
        print(f"Extracted {len(text)} chars via {method}")

        # Filter to only abstract + methods:
        with open("paper.pdf", "rb") as f:
            text, method = extract_pdf(f.read(), sections=["abstract", "methods"])
    """
    if max_input_bytes is not None and len(pdf_bytes) > max_input_bytes:
        raise ValueError(
            f"PDF input exceeds max_input_bytes: {len(pdf_bytes)} > {max_input_bytes}"
        )
    if pdftotext_timeout_seconds <= 0:
        raise ValueError("pdftotext_timeout_seconds must be > 0")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        # Primary: pdftotext default mode (no -layout flag — critical)
        result = subprocess.run(
            [resolve_pdftotext_executable(), "-enc", "UTF-8", tmp_path, "-"],
            capture_output=True,
            timeout=pdftotext_timeout_seconds,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0:
            return f"ERROR: pdftotext failed with code {result.returncode}", "error"

        text = result.stdout
        method = "pdftotext_default"

        # U+FFFD PASSES THROUGH AS PRINTED. A recovery used to live here: on >= 3
        # U+FFFD it ran pdfplumber over the whole document and either REPLACED the
        # entire text with pdfplumber's (Mode A) or substituted per word from a
        # global token set (Mode B). RETIRED 2026-09-24 by owner decision, on
        # evidence reproduced that week:
        #   * Mode A's guard `_reading_order_agrees` accepted a document's exact
        #     REVERSE, its blocks SHUFFLED, and completely UNRELATED text; and the
        #     swap joined pages with blank lines, so every page boundary vanished.
        #   * Mode B turned `partial <U+FFFD>2 = .35` into `partial R2 = .35` -- an
        #     effect size relabelled as a different statistic -- and it already
        #     EXECUTED on a real corpus paper (vancouver/plos_med_1.pdf), returning
        #     nothing only because no word happened to have a unique look-alike.
        #   * Across all 102 corpus papers NEITHER mode was ever accepted.
        # A visible U+FFFD is a flag a consumer can act on; a plausible wrong
        # token is not. (This is extract_pdf's contract. normalize_text's S5a and
        # S5b still rewrite U+FFFD in two narrow statistical contexts -- eta before
        # `2 =`, and >= / <= before a number -- and leave it everywhere else.) normalize.py still maps SMP math-italic characters that
        # pdftotext DOES decode (`_MATH_ALNUM_RE`), so nothing correctly encoded
        # is lost. Record: communications/DECISION_2026-09-22_fffd_recovery.md.

        # §A R4 / B6 column-aware re-extraction (v2.4.76, 2026-05-25).
        # Detector runs on form-feed-split pdftotext output (cheap, no
        # pdfplumber call). If any page is flagged for column-interleave,
        # extract the layout doc and rewrite those pages via pdftotext
        # crop-mode (per-column pdftotext gives correct word spacing where
        # pdfplumber `extract_text()` drops spaces on tight-kerned PDFs).
        # The corrected text then flows through ALL downstream channels —
        # sections, normalize, render, structured — because they all go
        # through extract_pdf. Per CLAUDE.md hard rule 3, this is
        # conditional fallback, NOT a default tool swap.
        try:
            from .normalize import _detect_column_interleave_pages
            from .extract_columns import (
                splice_column_corrected_pages,
                _detect_reference_inversion_pages,
                _detect_reference_rotation_pages,
            )
            ff_offsets: list[int] = [0]
            for idx, ch in enumerate(text):
                if ch == "\f":
                    ff_offsets.append(idx + 1)
            # Two cheap text-only detectors decide whether the (more expensive)
            # layout extraction + geometric re-order is worth running:
            #  - legacy column-INTERLEAVE (sentences woven between columns), and
            #  - O5 reading-order INVERSION (a page's reference entries serialized
            #    ABOVE their own References heading — chen page 19). The inversion
            #    pages are corrected under the word-preservation guard so the
            #    reorder can never lose or fabricate text (rule 0a / 0b).
            flagged_pages = _detect_column_interleave_pages(text, tuple(ff_offsets))
            inversion_pages = _detect_reference_inversion_pages(text, tuple(ff_offsets))
            # The same inversion on a CONTINUATION page of the reference list,
            # which carries no heading for the detector above to anchor on: the
            # alphabetical entries read as a rotated run ("N..Z" then "G..N").
            # chen p20 (10.1016/j.jesp.2021.104154) shipped 30 references out of
            # order this way. Same two safeties as the inversion pages, plus the
            # splice's requirement that the reorder leave the entries sorted.
            rotation_pages = _detect_reference_rotation_pages(text, tuple(ff_offsets))
            # RC-1 Step 1 (v2.4.82): GENERAL two-column interleave correction.
            # The O5 inversion path has always run the column-aware re-extraction
            # under TWO safeties: the full-height GUTTER-STRIP midline detector
            # (allow_gutter_fallback — strong 2-column evidence that bypasses the
            # bilateral table gate) AND the word-multiset preservation guard (a
            # reorder accepted only when it neither drops nor invents a word, rules
            # 0a/0b). The general-interleave flagged pages got NEITHER safety, so
            # they fell to the histogram detector + bilateral gate and stayed
            # interleaved on narrow-gutter (Elsevier / Collabra / JESP) and
            # table-bearing pages — the dominant defect on two-column APA papers
            # (TRIAGE 2026-06-08). When DOCPLUCK_COLUMN_CORRECT_GENERAL=1 the
            # flagged pages join the inversion pages under BOTH safeties: a flagged
            # page is corrected only when it has a clean full-height central gutter
            # (genuinely two-column, no full-width row crossing center) AND the
            # left-then-right re-extraction is a pure reorder of the same words.
            # Pages without a clean gutter (embedded full-width table, single
            # column) are left untouched — an honest partial; the per-band Step 2
            # closes those. Default OFF ⇒ byte-identical legacy path (ship dark,
            # validate against the AI golds, then flip the default).
            general_correct = (
                os.environ.get("DOCPLUCK_COLUMN_CORRECT_GENERAL", "0") == "1"
            )
            # RC-1 Step 2 (v2.4.90): per-band region-aware re-extraction for the
            # table-bearing / mixed-layout pages the whole-page corrector (Step 1)
            # cannot reach. Applied as a FALLBACK inside the splice only when the
            # whole-page path returns "" for a flagged page, and only under the
            # SAME unconditional word-preservation guard. Default OFF ⇒ the
            # legacy path is byte-identical (ship dark; validate vs AI golds, then
            # flip the default once Step 1 + Step 2 are jointly verified).
            banded_correct = (
                os.environ.get("DOCPLUCK_COLUMN_CORRECT_BANDED", "0") == "1"
            )
            # gutter_fallback_pages opt into the full-height gutter-strip detector
            # (bypasses the bilateral table gate). Word-preservation now gates
            # EVERY corrected page unconditionally inside the splice, so this set
            # only governs HOW aggressively the midline is detected, not whether
            # the result is trusted. Inversion pages always opt in; general
            # flagged pages opt in only under the flag.
            gutter_fallback_pages = set(inversion_pages) | set(rotation_pages)
            if general_correct or banded_correct:
                # Under BANDED too: a flagged page that IS a clean 2-column page
                # should be corrected by the proven whole-page gutter path; the
                # per-band fallback only fires when that path returns "" (the
                # table-bearing / mixed-layout pages it cannot reach).
                gutter_fallback_pages |= set(flagged_pages)
            all_pages = sorted(
                set(flagged_pages) | set(inversion_pages) | set(rotation_pages)
            )
            if all_pages:
                from .extract_layout import extract_pdf_layout
                # ONLY the flagged pages. The splice below rewrites pages in
                # `all_pages` and nothing else, so geometry for the other pages
                # was always discarded — but it was still parsed. Measured
                # 2026-09-17 on a 72-page RSOS paper with 23 flagged pages and
                # no inversion pages: the full-document parse cost 25.3 s and
                # changed nothing, against 1.0 s for the pdftotext call it was
                # correcting. `extract_pdf_layout` keeps one entry per PDF page
                # at its real index, so `page_idx` below still means page_idx.
                layout_doc = extract_pdf_layout(
                    pdf_bytes, pages=[p - 1 for p in all_pages]
                )
                changed: list[int] = []
                banded_pages = sorted(all_pages) if banded_correct else []
                corrected = splice_column_corrected_pages(
                    text, layout_doc, ff_offsets, all_pages,
                    pdf_bytes=pdf_bytes,
                    gutter_fallback_pages=sorted(gutter_fallback_pages),
                    banded_pages=banded_pages,
                    changed_out=changed,
                    rotation_pages=rotation_pages,
                    edge_trimmed_pages=sorted(
                        set(inversion_pages) | set(rotation_pages)
                    ),
                )
                if corrected and corrected != text and changed:
                    text = corrected
                    method = f"{method}+column_corrected:{','.join(map(str, changed))}"
        except Exception as exc:
            exc_name = type(exc).__name__
            record_fallback("column_correction_exception", detail=exc_name)
            method = f"{method}+column_correction_failed:{exc_name}"

        if sections is not None:
            from .sections import extract_sections
            # The pair THIS call just produced, rather than a second identical
            # run of it: `extract_sections(pdf_bytes)` calls `extract_pdf` with
            # these same default arguments, so `extract_pdf(blob, sections=[...])`
            # spawned pdftotext twice and — on a document whose column detectors
            # flag a page — ran the layout splice twice. `text`/`method` here are
            # exactly what this function returns when `sections` is None, i.e.
            # exactly what that second call would have computed. (2026-09-17)
            doc = extract_sections(pdf_bytes, _raw_text=(text, method))
            return doc.text_for(*sections), method

        return text, method

    finally:
        # CLEANUP IS BEST-EFFORT, AND IT IS RECORDED. A bare `os.unlink` here
        # raised `PermissionError [WinError 32]` straight out of the library's
        # PRIMARY TEXT ENTRY POINT whenever the temp file was momentarily locked
        # — after the text had already been extracted successfully. The sibling
        # camelot sites had been given exactly this guard in v2.4.134, under a
        # comment reading "BOTH call sites, because a fix applied to one of two
        # is not fixed"; there were five sites, and this was one of the three the
        # sweep never looked at. See `docpluck/tempfiles.py`.
        unlink_temp_pdf(tmp_path)


def extract_pdf_file(path: Union[str, Path]) -> tuple[str, str]:
    """Extract text from a PDF file on disk.

    Thin convenience wrapper around ``extract_pdf`` that reads ``path`` and
    raises a clean ``FileNotFoundError`` when the file does not exist, instead
    of the generic exception pdftotext emits on a missing input. Useful for
    batch runners that walk directories and want actionable errors.

    Args:
        path: Path to the PDF file on disk (str or pathlib.Path).

    Returns:
        Same tuple as ``extract_pdf``: ``(text, method)``.

    Raises:
        FileNotFoundError: If ``path`` does not exist or is not a regular file.

    Example:
        text, method = extract_pdf_file("paper.pdf")
    """
    p = Path(path)
    if not p.is_file():
        # is_file() returns False for both missing paths and non-file entries
        # (directories, broken symlinks). Distinguish for a clearer error.
        if p.exists():
            raise FileNotFoundError(f"Path is not a regular file: {p}")
        raise FileNotFoundError(f"PDF file not found: {p}")
    return extract_pdf(p.read_bytes())


def count_pages(pdf_bytes: bytes) -> int:
    """Count the number of pages in a PDF.

    Uses byte pattern matching first (fast, no external binary). For
    PDF 1.5+ documents that compress object streams (cross-reference
    streams + ``/ObjStm``), the literal ``/Type /Page`` markers are
    inside zlib-compressed blocks and the byte count returns 1 even
    for multi-page documents. v2.3.1 fix: when the byte-pattern result
    is 1, fall back to pdfplumber's accurate page count.

    Args:
        pdf_bytes: Raw PDF file content as bytes.

    Returns:
        Page count (integer, minimum 1).

    Example:
        with open("paper.pdf", "rb") as f:
            n = count_pages(f.read())
        print(f"{n} pages")
    """
    try:
        # Fast path: byte-pattern heuristic. Counts ``/Type /Page``
        # occurrences while subtracting the parent ``/Type /Pages``
        # entry. Works for uncompressed PDFs.
        count = pdf_bytes.count(b"/Type /Page") - pdf_bytes.count(b"/Type /Pages")
        if count >= 2:
            return count
        # The byte heuristic returned 0 or 1. For genuinely 1-page docs
        # this is correct; for compressed-stream PDFs it's a false low.
        # Use pdfplumber to disambiguate. pdfplumber is already a hard
        # dependency, so this never fails on import.
        try:
            import io
            import pdfplumber  # type: ignore[import-not-found]
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                return max(len(pdf.pages), 1)
        except Exception as exc:
            record_fallback("count_pages_pdfplumber_fallback_failed", detail=type(exc).__name__)
            # pdfplumber failed (corrupt PDF, password-protected, etc.) —
            # fall back to the heuristic's value.
            return max(count, 1)
    except Exception as exc:
        record_fallback("count_pages_exception", detail=type(exc).__name__)
        return 0
