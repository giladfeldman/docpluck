# Special Benchmark Mode: DOCX/PDF Parity + MetaESCI Regression

_Extracted from [../SKILL.md](../SKILL.md). Opt-in; 5-15 min runtime._


Opt-in cross-format benchmark suite (DOCX corpus, DOCX↔PDF parity via Word COM, PDF↔DOCX via pdf2docx, MetaESCI 200-DOI regression). Takes 5-15 minutes; only run when explicitly requested.

**Full procedure:** [references/benchmark-mode.md](references/benchmark-mode.md)

### Prerequisites

- Microsoft Word installed (for `docx2pdf`, accessed via COM)
- Python packages: `mammoth`, `beautifulsoup4`, `lxml`, `rapidfuzz`, `pdf2docx`, `docx2pdf`
- CitationGuard corpus present at `C:\Users\filin\Dropbox\Vibe\CitationGuard\apps\worker\testpdfs\validation\docx\`
- PDF test corpus at `C:\Users\filin\Dropbox\Vibe\PDFextractor\test-pdfs\`

### Running

Full benchmark (5–15 minutes, launches Word):
```bash
cd C:\Users\filin\Dropbox\Vibe\docpluck && python benchmarks/run_all.py
```

Quick mode (3 files per benchmark, 2–4 minutes):
```bash
cd C:\Users\filin\Dropbox\Vibe\docpluck && python benchmarks/run_all.py --quick
```

Skip Word-based conversion (if Word unavailable):
```bash
cd C:\Users\filin\Dropbox\Vibe\docpluck && python benchmarks/run_all.py --skip docx2pdf
```

Individual benchmarks:
```bash
# 1. DOCX corpus (24 files, ~45s)
python benchmarks/bench_docx_corpus.py --json benchmarks/results/docx_corpus.json

# 2. DOCX → PDF cross-format (20 files via Word COM, ~5-10 min)
python benchmarks/bench_docx_vs_pdf.py --json benchmarks/results/docx_vs_pdf.json

# 3. PDF → DOCX reverse cross-format (8 files via pdf2docx, ~2-4 min)
python benchmarks/bench_pdf_vs_docx.py --json benchmarks/results/pdf_vs_docx.json

# 4. MetaESCI regression baseline (200 frozen DOIs, ~70s)
python benchmarks/bench_metaesci_regression.py --json benchmarks/results/metaesci_regression.json
```

### What Each Benchmark Validates

**1. DOCX corpus benchmark** (`bench_docx_corpus.py`)
- Runs `extract_docx()` on all 24 CitationGuard DOCX files
- Validates: all 20 real papers extract successfully; all 4 corrupted files fail correctly
- Checks quality score ≥80 and "high" confidence for every real paper
- Detects garbled extractions (should be 0)
- Reports total chars, per-file times, aggregate stats

**2. DOCX → PDF cross-format benchmark** (`bench_docx_vs_pdf.py`)
- For each DOCX: extract text, convert DOCX→PDF via Word (`docx2pdf`), extract PDF text, compare
- Uses `rapidfuzz.token_set_ratio` to measure similarity (should be ≥ 80%)
- Uses char-count ratio to detect content loss (should be 0.7–1.3)
- Both extractors should produce "high" confidence quality scores
- This is the A/B gold-standard: same content, two extraction paths — asymmetry reveals bugs in either extractor

**3. PDF → DOCX reverse cross-format benchmark** (`bench_pdf_vs_docx.py`)
- For each PDF: extract text, convert PDF→DOCX via `pdf2docx` (pure Python), extract DOCX text, compare
- Default selection: 8 PDFs across APA, Vancouver, AMA, Harvard, IEEE, Nature styles
- Same pass criteria as #2

### Pass Criteria

Benchmark | Threshold
--- | ---
DOCX corpus extraction success | 20/20 real papers
DOCX corpus quality score | avg ≥ 80, all high confidence
DOCX corpus garbled count | 0
DOCX→PDF similarity (token_set_ratio) | avg ≥ 80%, min ≥ 80%
DOCX→PDF char ratio | 0.7–1.3
PDF→DOCX similarity | avg ≥ 80%, min ≥ 80%
PDF→DOCX char ratio | 0.7–1.3
MetaESCI extraction success | 200/200 (zero crashes, zero extraction errors)
MetaESCI high confidence | ≥ 99% (198/200+)
MetaESCI avg quality | ≥ 80 / 100
MetaESCI total U+FFFD | 0
MetaESCI stat linebreak survivors | 0
MetaESCI dropped decimal survivors | 0 (watch — current baseline has 21 in 3 files, real gaps pending A1/A2 enhancement)

### Interpreting Results

- **Similarity < 80%**: the two extractors are producing substantially different text for the same content. Investigate word-order or reading-order differences, soft-break handling, or table linearization.
- **Char ratio far from 1.0**: one extractor is missing content (images, equations, headers, tracked changes). Investigate which format is losing data.
- **DOCX quality score < PDF quality score**: something is wrong — DOCX should be cleaner than PDF (no column interleaving, no ligatures, no SMP Unicode). This is a red flag for mammoth configuration or the tree-walk.
- **OMML equations**: known limitation — mammoth drops Office Math objects. Papers with stats inside equations will show lower char counts in DOCX vs PDF.

### Output

Benchmark writes three files to `benchmarks/results/`:
- `docx_corpus.json` — per-file metrics
- `docx_vs_pdf.json` — cross-format comparison
- `pdf_vs_docx.json` — reverse comparison
- `REPORT.md` — consolidated markdown report

After running, read `benchmarks/results/REPORT.md` and report the summary to the user.

---

