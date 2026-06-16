# docpluck

PDF, DOCX, and HTML text extraction plus normalization for academic papers.

The full documentation lives in `docs/README.md`.

## Quick install

```bash
pip install docpluck
```

Optional extras:

```bash
pip install docpluck[docx]
pip install docpluck[html]
pip install docpluck[all]
```

## System requirement for PDF extraction

`extract_pdf()` requires the `pdftotext` binary from Poppler.

- Linux/WSL: `apt-get install poppler-utils`
- macOS: `brew install poppler`
- Windows: install Poppler and add its `bin` folder to `PATH`

## Links

- Full usage and API reference: `docs/README.md`
- Normalization pipeline details: `docs/NORMALIZATION.md`
- Benchmarks: `docs/BENCHMARKS.md`
- Design notes: `docs/DESIGN.md`

