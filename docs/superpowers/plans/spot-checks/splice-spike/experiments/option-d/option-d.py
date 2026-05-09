"""
option-d.py — Camelot table extraction experiment
Evaluates Camelot (camelot-py[base]) against two APA psychology PDFs.

Library: camelot-py 1.0.9, flavor=stream (whitespace-aligned tables)
Platform: Windows 11, Python 3.14
Note: Ghostscript is NOT required for stream flavor.
"""

import camelot
import unicodedata
import json


PDF_KORBMACHER = r"C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor\test-pdfs\apa\korbmacher_2022_kruger.pdf"
PDF_ZIANO = r"C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor\test-pdfs\apa\ziano_2021_joep.pdf"


def clean_cell(s: str) -> str:
    """Normalize Unicode in extracted cell text."""
    s = unicodedata.normalize("NFKD", str(s))
    s = s.replace("\n", " ").strip()
    return s


def df_to_markdown(df, caption: str = "", accuracy: float = 0.0, flavor: str = "stream") -> str:
    """Render a camelot DataFrame as a Markdown pipe-table."""
    # Find actual header rows and data rows
    lines = []

    # Convert to clean string matrix
    rows = []
    for ri in range(len(df)):
        row = [clean_cell(df.iloc[ri, ci]) for ci in range(len(df.columns))]
        rows.append(row)

    if not rows:
        return "_No data_"

    n_cols = len(rows[0])

    # Use first non-empty row as header
    header_idx = 0
    for i, row in enumerate(rows):
        if any(c.strip() for c in row):
            header_idx = i
            break

    header = rows[header_idx]
    data_rows = rows[header_idx + 1:]

    # Render table
    def fmt_row(cells):
        return "| " + " | ".join(cells) + " |"

    lines.append(fmt_row(header))
    lines.append("| " + " | ".join(["---"] * n_cols) + " |")
    for row in data_rows:
        lines.append(fmt_row(row))

    footer = f"\n*Camelot accuracy: {accuracy:.1f}, flavor: {flavor}*"
    if caption:
        return f"*{caption}*\n\n" + "\n".join(lines) + footer
    return "\n".join(lines) + footer


# ============================================================
# KORBMACHER 2022 — Table 1, page 7
# ============================================================
def extract_korbmacher():
    print("=== korbmacher_2022_kruger.pdf, page 7 ===")

    # Lattice: expected to fail on whitespace tables
    tables_lattice = camelot.read_pdf(PDF_KORBMACHER, pages="7", flavor="lattice")
    print(f"Lattice: {len(tables_lattice)} tables found")

    # Stream: default edge_tol
    for edge_tol in [50, 100, 200]:
        tables = camelot.read_pdf(PDF_KORBMACHER, pages="7", flavor="stream", edge_tol=edge_tol)
        print(f"Stream edge_tol={edge_tol}: {len(tables)} tables found")
        for i, t in enumerate(tables):
            print(f"  Table {i}: accuracy={t.accuracy:.1f}, whitespace={t.whitespace:.1f}, shape={t.df.shape}")

    # Best result: stream default
    tables = camelot.read_pdf(PDF_KORBMACHER, pages="7", flavor="stream")
    return tables[0]


# ============================================================
# ZIANO 2021 — Table 1, page 2 (landscape, two tables side-by-side)
# ============================================================
def extract_ziano():
    print("\n=== ziano_2021_joep.pdf, page 2 ===")

    # Lattice: expected to fail
    tables_lattice = camelot.read_pdf(PDF_ZIANO, pages="2", flavor="lattice")
    print(f"Lattice: {len(tables_lattice)} tables found")

    # Stream: various edge_tol
    for edge_tol in [50, 100, 200, 500]:
        tables = camelot.read_pdf(PDF_ZIANO, pages="2", flavor="stream", edge_tol=edge_tol)
        print(f"Stream edge_tol={edge_tol}: {len(tables)} tables found")
        for i, t in enumerate(tables):
            print(f"  Table {i}: accuracy={t.accuracy:.1f}, whitespace={t.whitespace:.1f}, shape={t.df.shape}")

    # Best result: stream default (all edge_tol produce same result)
    tables = camelot.read_pdf(PDF_ZIANO, pages="2", flavor="stream")
    return tables[0]


if __name__ == "__main__":
    korb_table = extract_korbmacher()
    ziano_table = extract_ziano()

    # Korbmacher: rows 2-3 are the real header (split across two rows)
    # rows 5-13 are data rows
    print("\n\nKorbmacher raw data:")
    df = korb_table.df
    for ri in range(len(df)):
        row = [clean_cell(df.iloc[ri, ci]) for ci in range(len(df.columns))]
        print(f"  row {ri}: {row}")

    print("\n\nZiano raw data (first 10 rows):")
    df2 = ziano_table.df
    for ri in range(min(10, len(df2))):
        row = [clean_cell(df2.iloc[ri, ci]) for ci in range(len(df2.columns))]
        print(f"  row {ri}: {row}")
