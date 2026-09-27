"""Write three tiny SYNTHETIC documents (PDF, DOCX, HTML) for executing the README.

The README quickstart must be run, not eyeballed (`scripts/check_docs_coverage.py`
executes it). Running it needs a document, and this repository must never hold a
real article -- so these are generated from made-up sentences, with no external
dependency: the PDF is written byte by byte, the DOCX is a hand-built zip.

    python scripts/docs_sample_documents.py OUT_DIR

writes OUT_DIR/paper.pdf, OUT_DIR/paper.docx and OUT_DIR/paper.html.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

LINES = [
    "Abstract",
    "We tested whether a synthetic manipulation changes a synthetic outcome.",
    "Results",
    "The effect was significant, t(28) = 2.10, p = .045, d = 0.77.",
    "A second test gave F(1, 58) = 4.12, p = .047.",
    "References",
    "Author, A. (2020). A made-up reference. Journal of Examples, 1, 1-2.",
]


def _pdf_bytes(lines: list[str]) -> bytes:
    stream_lines = ["BT", "/F1 11 Tf", "72 720 Td", "14 TL"]
    for ln in lines:
        esc = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_lines.append(f"({esc}) Tj T*")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def _docx_bytes(lines: list[str], path: Path) -> None:
    paras = "".join(
        f"<w:p><w:r><w:t xml:space=\"preserve\">{ln}</w:t></w:r></w:p>" for ln in lines
    )
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        ),
        "word/document.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:document xmlns:w="{W}"><w:body>{paras}</w:body></w:document>'
        ),
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, xml in parts.items():
            z.writestr(name, xml)


def write_samples(out_dir: str | Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pdf, docx, html = out / "paper.pdf", out / "paper.docx", out / "paper.html"
    pdf.write_bytes(_pdf_bytes(LINES))
    _docx_bytes(LINES, docx)
    html.write_text(
        "<html><body>" + "".join(
            f"<h2>{ln}</h2>" if ln in ("Abstract", "Results", "References") else f"<p>{ln}</p>"
            for ln in LINES
        ) + "</body></html>",
        encoding="utf-8",
    )
    return {"pdf": pdf, "docx": docx, "html": html}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/docs_sample_documents.py OUT_DIR")
    for kind, p in write_samples(sys.argv[1]).items():
        print(kind, p)
