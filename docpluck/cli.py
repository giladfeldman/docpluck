"""docpluck CLI.

Subcommands:
  docpluck --version              version + git sha JSON
  docpluck extract <file>         emit normalized text
  docpluck extract <file> --sections abstract,references
                                  emit text of just those sections
  docpluck sections <file>        emit SectionedDocument as JSON
  docpluck sections <file> --format summary
                                  emit a human-readable summary
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .version import get_version_info


def _read_bytes(path: str) -> bytes:
    return Path(path).read_bytes()


def _format_for(path: str) -> str:
    p = path.lower()
    if p.endswith(".pdf"): return "pdf"
    if p.endswith(".docx"): return "docx"
    if p.endswith((".html", ".htm")): return "html"
    raise SystemExit(f"unknown file extension: {path}")


def _cmd_extract(args: argparse.Namespace) -> int:
    from . import extract_pdf, extract_docx, extract_html
    fmt = _format_for(args.file)
    blob = _read_bytes(args.file)
    sections = [s.strip() for s in args.sections.split(",")] if args.sections else None
    if fmt == "pdf":
        text, _ = extract_pdf(blob, sections=sections)
    elif fmt == "docx":
        text, _ = extract_docx(blob, sections=sections)
    else:
        text, _ = extract_html(blob, sections=sections)
    sys.stdout.write(text)
    return 0


def _cmd_sections(args: argparse.Namespace) -> int:
    from . import extract_sections
    blob = _read_bytes(args.file)
    doc = extract_sections(blob)

    if args.format == "summary":
        lines = [f"sectioning_version: {doc.sectioning_version}",
                 f"source_format: {doc.source_format}",
                 f"sections ({len(doc.sections)}):"]
        for s in doc.sections:
            pages = ",".join(str(p) for p in s.pages) if s.pages else "-"
            lines.append(
                f"  [{s.confidence.value}] {s.label:>22}  pages={pages:6}  "
                f"chars={s.char_end - s.char_start}  via={s.detected_via.value}"
            )
        sys.stdout.write("\n".join(lines) + "\n")
        return 0

    payload = {
        "sectioning_version": doc.sectioning_version,
        "source_format": doc.source_format,
        "sections": [
            {
                "label": s.label,
                "canonical_label": s.canonical_label.value,
                "char_start": s.char_start,
                "char_end": s.char_end,
                "pages": list(s.pages),
                "confidence": s.confidence.value,
                "detected_via": s.detected_via.value,
                "heading_text": s.heading_text,
                "text": s.text,
            }
            for s in doc.sections
        ],
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args_in = list(sys.argv[1:] if argv is None else argv)

    if not args_in or args_in[0] in ("-V", "--version", "version"):
        print(json.dumps(get_version_info()))
        return 0

    if args_in[0] in ("-h", "--help", "help"):
        print("usage: docpluck [--version | extract <file> [--sections L1,L2] | sections <file> [--format json|summary]]")
        return 0

    parser = argparse.ArgumentParser(prog="docpluck", add_help=True)
    sub = parser.add_subparsers(dest="cmd", required=True)

    extract = sub.add_parser("extract")
    extract.add_argument("file")
    extract.add_argument("--sections", default=None,
                         help="Comma-separated list of section labels to filter.")
    extract.set_defaults(func=_cmd_extract)

    sections = sub.add_parser("sections")
    sections.add_argument("file")
    sections.add_argument("--format", default="json", choices=["json", "summary"])
    sections.set_defaults(func=_cmd_sections)

    try:
        parsed = parser.parse_args(args_in)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2
    return parsed.func(parsed)


if __name__ == "__main__":
    raise SystemExit(main())
