"""
PDF Text Extraction
====================
Primary engine: pdftotext default mode (no -layout flag)
Fallback: pdfplumber for PDFs with SMP Unicode (Mathematical Italic fonts)

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


def extract_pdf(pdf_bytes: bytes, *, sections: list[str] | None = None) -> tuple[str, str]:
    """Extract text from PDF bytes.

    Uses pdftotext as the primary engine. Automatically falls back to
    pdfplumber if the PDF contains SMP Unicode characters (e.g. Mathematical
    Italic fonts used by Nature/Cell journals) that Xpdf cannot handle.

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
          - method: Engine used. One of:
              "pdftotext_default"                   — normal extraction
              "pdftotext_default+pdfplumber_recovery" — SMP fallback triggered

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
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        # Primary: pdftotext default mode (no -layout flag — critical)
        result = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", tmp_path, "-"],
            capture_output=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0:
            return f"ERROR: pdftotext failed with code {result.returncode}", "error"

        text = result.stdout
        method = "pdftotext_default"

        # SMP recovery: Xpdf replaces U+FFFF+ characters with U+FFFD (replacement char).
        # pdfplumber handles these correctly and remaps them to ASCII equivalents.
        #
        # 2026-05-11: only trigger recovery when FFFDs are meaningfully
        # present (\u2265 3) AND pdfplumber's reading order matches pdftotext's.
        # Previously a single stray FFFD would swap the entire pdftotext text
        # for pdfplumber's `extract_text()` \u2014 which on multi-column papers
        # like the Adelina/Pronin replication (IRSP) interleaves the two
        # columns word-by-word, producing unreadable body text with similar
        # overall length. The length-similarity check is insufficient; we
        # need a *reading-order* check.
        #
        # The check: take three 60-char snippets from non-FFFD-containing
        # regions of pdftotext's body. If pdfplumber's output contains all
        # three verbatim, both extractors agree on column ordering and the
        # recovery is safe. If even one snippet is reordered out, pdfplumber
        # collapsed the columns and we keep pdftotext's text (FFFDs and all).
        fffd_count = text.count("\ufffd")
        if fffd_count >= 3:
            recovered = _recover_with_pdfplumber(tmp_path)
            if (
                recovered
                and recovered.count("\ufffd") < fffd_count
                and _reading_order_agrees(text, recovered)
            ):
                text = recovered
                method = "pdftotext_default+pdfplumber_recovery"
            elif recovered:
                # v2.3.1: reading order disagreed (pdfplumber would
                # column-interleave a 2-column paper), but we can still
                # recover individual U+FFFD characters word-by-word
                # without disturbing pdftotext's reading order. For each
                # FFFD-containing word in pdftotext, find a same-shape
                # candidate in pdfplumber's output and substitute. This
                # is the 50-LOC fix from
                # ``docs/HANDOFF_2026-05-11_visual_review_findings.md``
                # \u2014 "18 residual FFFDs in Adelina body".
                patched, n_patched = _patch_fffds_word_by_word(text, recovered)
                if n_patched > 0:
                    text = patched
                    method = "pdftotext_default+pdfplumber_word_patch"

        if sections is not None:
            from .sections import extract_sections
            doc = extract_sections(pdf_bytes)
            return doc.text_for(*sections), method

        return text, method

    finally:
        os.unlink(tmp_path)


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
        except Exception:
            # pdfplumber failed (corrupt PDF, password-protected, etc.) —
            # fall back to the heuristic's value.
            return max(count, 1)
    except Exception:
        return 0


_FFFD_WORD_RE = re.compile(r"\S*�\S*")


def _patch_fffds_word_by_word(
    pdftotext_text: str, pdfplumber_text: str
) -> tuple[str, int]:
    """Per-word U+FFFD recovery using pdfplumber's text as the lookup source.

    Strategy: scan ``pdftotext_text`` for tokens containing U+FFFD, build a
    regex pattern with ``[A-Za-z]`` at each FFFD position (and the literal
    char elsewhere), and look for a UNIQUE matching token in
    ``pdfplumber_text``. When exactly one candidate matches, swap the
    pdftotext token for the candidate (recovers the lost letter).

    Conservative rules — only patch when:
    - The FFFD position resolves to an ASCII letter (no digits / punct, so we
      can't accidentally manufacture "1" into "I" or vice versa).
    - The candidate is unique within pdfplumber's token set (no ambiguity).
    - The non-FFFD characters in the pdftotext token match exactly.

    Returns ``(patched_text, n_chars_recovered)``.

    Caller invokes this when the full pdfplumber recovery was rejected
    by ``_reading_order_agrees`` (e.g. two-column papers where pdfplumber
    interleaves columns). Word-by-word patching doesn't move text around,
    so reading order is preserved.
    """
    if "�" not in pdftotext_text or not pdfplumber_text:
        return pdftotext_text, 0

    # Build pdfplumber's token set once. Use the same \S+ tokenization so
    # punctuation-attached words ("study)" / "(see") line up.
    pp_tokens = set(re.findall(r"\S+", pdfplumber_text))
    if not pp_tokens:
        return pdftotext_text, 0

    out_parts: list[str] = []
    pos = 0
    n_recovered = 0
    for m in _FFFD_WORD_RE.finditer(pdftotext_text):
        out_parts.append(pdftotext_text[pos:m.start()])
        token = m.group(0)
        # Build a per-char regex: literal escape except FFFD → [A-Za-z].
        pattern = re.compile(
            "^"
            + "".join(
                "[A-Za-z]" if ch == "�" else re.escape(ch)
                for ch in token
            )
            + "$"
        )
        candidates = [t for t in pp_tokens if pattern.match(t)]
        if len(candidates) == 1:
            out_parts.append(candidates[0])
            n_recovered += token.count("�")
        else:
            # Ambiguous (>1 candidate) or no match — keep the FFFD token
            # so the caller's quality scoring still flags the document.
            out_parts.append(token)
        pos = m.end()
    out_parts.append(pdftotext_text[pos:])
    return "".join(out_parts), n_recovered


def _reading_order_agrees(pdftotext_text: str, pdfplumber_text: str) -> bool:
    """Return True if pdfplumber's output preserves pdftotext's reading order.

    pdftotext (xpdf, no -layout flag) produces correctly-ordered column text.
    pdfplumber's ``page.extract_text()`` defaults sort characters by y-coord
    first, which interleaves the two columns of a two-column academic paper.
    On such papers the lengths come out very similar but the text is shuffled.

    Heuristic: extract three 60-char snippets from non-FFFD body regions of
    pdftotext (after the first 5%, at 30%, 50%, 70% of the document) and
    require that ALL THREE appear verbatim in pdfplumber's output. If even
    one is missing, columns were reordered.
    """
    n = len(pdftotext_text)
    if n < 2000:
        # Too short to safely sample; trust the length-similarity heuristic.
        ratio = len(pdfplumber_text) / max(n, 1)
        return 0.85 < ratio < 1.15

    # Build candidate windows at 30%, 50%, 70% of the doc; slide forward up
    # to 1000 chars looking for a 60-char run with no FFFDs / form feeds.
    for frac in (0.30, 0.50, 0.70):
        start = int(n * frac)
        snippet = None
        for offset in range(0, 1000, 30):
            window = pdftotext_text[start + offset : start + offset + 60]
            if (
                len(window) == 60
                and "�" not in window
                and "\f" not in window
                and not window.isspace()
            ):
                snippet = window
                break
        if snippet is None:
            # Couldn't find a clean snippet at this fraction; skip it.
            continue
        if snippet not in pdfplumber_text:
            return False
    return True


def _recover_with_pdfplumber(pdf_path: str) -> Optional[str]:
    """Recover text using pdfplumber when pdftotext produces garbled output.

    Triggered when U+FFFD (replacement character) appears in pdftotext output,
    which indicates SMP Mathematical Italic fonts (U+1D434-U+1D467) that
    Xpdf/poppler cannot decode. pdfplumber (using pdfminer) handles these
    correctly. Maps the recovered SMP characters to ASCII equivalents so
    downstream regex patterns work normally.

    Args:
        pdf_path: Path to the PDF file on disk.

    Returns:
        Recovered text string, or None if recovery failed.
    """
    try:
        import pdfplumber

        smp_to_ascii: dict[str, str] = {}
        # Math italic capitals A-Z: U+1D434–U+1D44D
        for i, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            smp_to_ascii[chr(0x1D434 + i)] = letter
        # Math italic small a-z: U+1D44E–U+1D467
        for i, letter in enumerate("abcdefghijklmnopqrstuvwxyz"):
            smp_to_ascii[chr(0x1D44E + i)] = letter
        # Math italic Greek (common in physics/biology papers)
        greek = {
            0x1D6E2: "A", 0x1D6E4: "G", 0x1D6E5: "D", 0x1D6F4: "S",
            0x1D6F7: "Ph", 0x1D6F8: "Ch", 0x1D6F9: "Ps", 0x1D6FA: "O",
            0x1D6FC: "a", 0x1D6FD: "b", 0x1D6FE: "g", 0x1D6FF: "d",
            0x1D700: "e", 0x1D701: "z", 0x1D702: "n", 0x1D703: "th",
            0x1D707: "m", 0x1D70B: "pi", 0x1D70C: "r", 0x1D70E: "s",
            0x1D711: "ph", 0x1D712: "ch", 0x1D713: "ps",
        }
        for cp, repl in greek.items():
            smp_to_ascii[chr(cp)] = repl

        pages_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)

        full_text = "\n\n".join(pages_text)

        for smp_char, ascii_equiv in smp_to_ascii.items():
            full_text = full_text.replace(smp_char, ascii_equiv)

        return full_text

    except Exception:
        return None
