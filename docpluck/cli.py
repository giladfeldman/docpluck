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
    fmt = _format_for(args.file)
    blob = _read_bytes(args.file)

    if getattr(args, "structured", False):
        return _cmd_extract_structured(args, blob, fmt)

    from . import extract_pdf, extract_docx, extract_html
    sections = [s.strip() for s in args.sections.split(",")] if args.sections else None
    if fmt == "pdf":
        text, _ = extract_pdf(blob, sections=sections)
    elif fmt == "docx":
        text, _ = extract_docx(blob, sections=sections)
    else:
        text, _ = extract_html(blob, sections=sections)
    sys.stdout.write(text)
    return 0


def _cmd_extract_structured(args: argparse.Namespace, blob: bytes, fmt: str) -> int:
    if fmt != "pdf":
        sys.stderr.write("--structured is only supported for PDF inputs.\n")
        return 2
    from . import extract_pdf_structured

    result = extract_pdf_structured(
        blob,
        thorough=bool(getattr(args, "thorough", False)),
        table_text_mode=getattr(args, "text_mode", "raw"),
    )

    if getattr(args, "tables_only", False):
        result["figures"] = []
    if getattr(args, "figures_only", False):
        result["tables"] = []

    if getattr(args, "html_tables_to", None):
        out_dir = Path(args.html_tables_to)
        out_dir.mkdir(parents=True, exist_ok=True)
        for t in result["tables"]:
            html = t.get("html")
            if html:
                (out_dir / f"{t['id']}.html").write_text(html, encoding="utf-8")

    sys.stdout.write(json.dumps(result, ensure_ascii=False, default=list) + "\n")
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


def _cmd_render(args: argparse.Namespace) -> int:
    from . import render_pdf_to_markdown, NormalizationLevel
    blob = _read_bytes(args.file)
    level = NormalizationLevel(args.level)
    md = render_pdf_to_markdown(blob, normalization_level=level)
    sys.stdout.write(md)
    return 0


def main(argv: list[str] | None = None) -> int:
    # Ensure stdout is always UTF-8 (matters on Windows where the default is cp1252).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args_in = list(sys.argv[1:] if argv is None else argv)

    if not args_in or args_in[0] in ("-V", "--version", "version"):
        print(json.dumps(get_version_info()))
        return 0

    if args_in[0] in ("-h", "--help", "help"):
        print("usage: docpluck [--version | extract <file> [--sections L1,L2] [--structured [--thorough] [--text-mode raw|placeholder] [--tables-only|--figures-only] [--html-tables-to DIR]] | sections <file> [--format json|summary] | render <file> [--level none|standard|academic]]")
        return 0

    parser = argparse.ArgumentParser(prog="docpluck", add_help=True)
    sub = parser.add_subparsers(dest="cmd", required=True)

    extract = sub.add_parser("extract")
    extract.add_argument("file")
    extract.add_argument("--sections", default=None,
                         help="Comma-separated list of section labels to filter.")
    extract.add_argument("--structured", action="store_true",
                         help="Emit JSON with tables and figures (PDF only).")
    extract.add_argument("--thorough", action="store_true",
                         help="With --structured: scan every page for uncaptioned tables.")
    extract.add_argument("--text-mode", default="raw", choices=("raw", "placeholder"),
                         dest="text_mode",
                         help="With --structured: how to render table/figure regions in 'text'.")
    extract.add_argument("--tables-only", action="store_true",
                         dest="tables_only",
                         help="With --structured: omit figures from output.")
    extract.add_argument("--figures-only", action="store_true",
                         dest="figures_only",
                         help="With --structured: omit tables from output.")
    extract.add_argument("--html-tables-to", metavar="DIR", default=None,
                         dest="html_tables_to",
                         help="With --structured: write each structured table's HTML to DIR/<id>.html.")
    extract.set_defaults(func=_cmd_extract)

    sections = sub.add_parser("sections")
    sections.add_argument("file")
    sections.add_argument("--format", default="json", choices=["json", "summary"])
    sections.set_defaults(func=_cmd_sections)

    render = sub.add_parser("render")
    render.add_argument("file")
    render.add_argument(
        "--level",
        default="standard",
        choices=["none", "standard", "academic"],
        help="Normalization level applied during section detection. Default: standard.",
    )
    render.set_defaults(func=_cmd_render)

    try:
        parsed = parser.parse_args(args_in)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2
    return parsed.func(parsed)


if __name__ == "__main__":
    raise SystemExit(main())
