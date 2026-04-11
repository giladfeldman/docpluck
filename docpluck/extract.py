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
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union


def extract_pdf(pdf_bytes: bytes) -> tuple[str, str]:
    """Extract text from PDF bytes.

    Uses pdftotext as the primary engine. Automatically falls back to
    pdfplumber if the PDF contains SMP Unicode characters (e.g. Mathematical
    Italic fonts used by Nature/Cell journals) that Xpdf cannot handle.

    Args:
        pdf_bytes: Raw PDF file content as bytes.

    Returns:
        A tuple of (text, method) where:
          - text: Extracted plain text. May start with "ERROR: ..." if extraction
            failed — check with text.startswith("ERROR:").
          - method: Engine used. One of:
              "pdftotext_default"                   — normal extraction
              "pdftotext_default+pdfplumber_recovery" — SMP fallback triggered

    Requires:
        pdftotext binary (from poppler-utils) on PATH.

    Example:
        with open("paper.pdf", "rb") as f:
            text, method = extract_pdf(f.read())
        print(f"Extracted {len(text)} chars via {method}")
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
        if text.count("\ufffd") > 0:
            recovered = _recover_with_pdfplumber(tmp_path)
            if recovered:
                text = recovered
                method = "pdftotext_default+pdfplumber_recovery"

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
    if not p.exists():
        raise FileNotFoundError(f"PDF file not found: {p}")
    if not p.is_file():
        raise FileNotFoundError(f"Path is not a regular file: {p}")
    return extract_pdf(p.read_bytes())


def count_pages(pdf_bytes: bytes) -> int:
    """Count the number of pages in a PDF.

    Uses byte pattern matching (no external binary required). Fast and
    reliable for well-formed PDFs. Returns 1 as a minimum.

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
        count = pdf_bytes.count(b"/Type /Page") - pdf_bytes.count(b"/Type /Pages")
        return max(count, 1)
    except Exception:
        return 0


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
