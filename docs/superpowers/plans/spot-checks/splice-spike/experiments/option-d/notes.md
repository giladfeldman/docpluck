# Option D: Camelot — Experiment Notes

## Installation

- **Library**: `camelot-py[base]` version 1.0.9
- **Status**: Already present in the environment (pre-installed). `pip install camelot-py[base]` showed "Requirement already satisfied."
- **Ghostscript**: NOT installed on this machine. No `gs` binary in PATH; no `C:\Program Files\gs\` directory.
- **Critical finding**: Ghostscript is only required for `flavor="lattice"` (it uses image-based line detection). `flavor="stream"` does NOT require Ghostscript — it uses PDF text coordinates directly. Stream extraction worked without any Ghostscript dependency.

## Per-table assessment

### korbmacher_2022_kruger.pdf — Table 1, page 7 (4×8 stats matrix, best case)

- **Lattice**: 0 tables found. Expected — whitespace table has no ruled lines.
- **Stream (default, edge_tol=50)**: **1 table found**. Shape: 14×5.
  - Accuracy: **97.7** / 100
  - Whitespace: 22.9 / 100
- **Stream (edge_tol=100)**: Same result (14×5, accuracy=97.7)
- **Stream (edge_tol=200)**: Returns 2 tables — second is a spurious 20×1 column fragment
- **Stream (edge_tol=500)**: Collapses everything into 1 table as 38×1 — too aggressive

**Best parameters**: `flavor="stream"`, default `edge_tol=50`

**Quality assessment**: The 14×5 DataFrame is structurally correct. It captures:
- Table title/caption in rows 0–1 (runs across merged columns — a real PDF artifact)
- Column header split across rows 2–3 (multi-row header — preserved correctly)
- Section break rows ("Easy", "Difficult") as partial rows
- All 8 data rows with correct numeric values
- Unicode: asterisk significance markers (∗ U+2217) preserved; minus signs (U+2212) preserved; "fi" ligature (U+FB01 → "fi" after NFKD normalization) handled

**Post-processing needed**: Minor. Rows 0–1 (caption/title) and multi-row header (rows 2–3) need manual merging logic. Data cells themselves are clean.

**Verdict**: **Usable with light post-processing.**

---

### ziano_2021_joep.pdf — Table 1, page 2 (landscape, two tables side-by-side, worst case)

- **Lattice**: 0 tables found. Expected.
- **Stream (all edge_tol values: 50, 100, 200, 500)**: **1 table found**. Shape: 52×14. Accuracy: **99.2**. Whitespace: 56.7.

**Quality assessment**: Camelot detected the entire landscape page as ONE wide table (14 columns = 7 columns per sub-table × 2 sub-tables). Structural issues:

1. **Two sub-tables not separated**: "Paying to know" (cols 1–6) and "Choice under risk" (cols 7–13) are concatenated into one 14-column extraction. No amount of parameter tuning changed this.

2. **Multi-line cells not merged**: Study names like "Tversky & Shafir, 1992, original (within-subject)" are split across 3 separate rows. Post-processing must detect and merge these hanging rows.

3. **"/" placeholders**: Most studies did not have "Paying to know" data in the original PDF. Camelot captured the empty left half correctly as "/" (these were truly empty cells in the PDF), but the "/" is ambiguous.

4. **"(cid:0)" artifact**: One cell contains `(cid:0)` — a malformed negative-sign encoding in the PDF font. Camelot faithfully reproduces the corrupt text; this is a PDF-level problem, not a Camelot problem.

5. **Unicode**: Greek chi (χ) and combining diaeresis for ü in "Kühberger" preserved correctly.

6. **High accuracy metric (99.2)** is misleading — it measures text-to-cell alignment, not semantic correctness. The structural problems are real.

**Verdict**: **Not directly usable without substantial post-processing.** The raw extraction is a faithful representation of the page geometry, but the two-tables-side-by-side layout requires a splitting step that Camelot does not provide.

---

## Accuracy / Whitespace Metrics Summary

| PDF | Flavor | edge_tol | Tables | Shape | Accuracy | Whitespace |
| --- | --- | --- | --- | --- | --- | --- |
| korbmacher | lattice | default | 0 | — | — | — |
| korbmacher | stream | 50 | 1 | 14×5 | 97.7 | 22.9 |
| korbmacher | stream | 100 | 1 | 14×5 | 97.7 | 22.9 |
| korbmacher | stream | 200 | 2 | 14×5 + 20×1 | 97.7 | 22.9 |
| ziano | lattice | default | 0 | — | — | — |
| ziano | stream | 50 | 1 | 52×14 | 99.2 | 56.7 |
| ziano | stream | 100 | 1 | 52×14 | 99.2 | 56.7 |
| ziano | stream | 200 | 1 | 52×14 | 99.2 | 56.7 |
| ziano | stream | 500 | 1 | 52×14 | 99.2 | 56.7 |

---

## Production Blockers

### Ghostscript (conditional blocker)

- **Stream flavor**: No Ghostscript required. Works out-of-the-box.
- **Lattice flavor**: Requires Ghostscript. Fails with `FileNotFoundError: Ghostscript is not installed` if `gs` is not in PATH.
- **Verdict**: For APA whitespace tables, stream-only mode avoids this dependency entirely. If lattice is ever needed (e.g., for bordered tables in supplementary materials), Ghostscript becomes a hard system dependency — which is a real production barrier on managed cloud environments (Railway, Render, etc.) unless a custom Dockerfile adds it.

### Install complexity

- `pip install camelot-py[base]` — clean install, no native build dependencies beyond what OpenCV provides.
- `pip install camelot-py[cv]` — includes the full OpenCV stack; slightly heavier but same result for stream flavor.
- No Ghostscript, no Poppler needed for stream-only usage.
- **Production verdict**: Install is straightforward for stream-only. Acceptable as a dependency.

### Python 3.14 compatibility

- Installed and ran without issues on Python 3.14.0. No compatibility warnings.

### Windows compatibility

- Camelot's path handling expects native OS paths. POSIX-style paths (`/c/Users/...`) fail with `FileNotFoundError`. Windows paths (`C:\Users\...`) work correctly.
- In production (Linux containers on Railway), this is a non-issue — paths will be POSIX natively.

---

## Honest Verdict

| Dimension | Assessment |
| --- | --- |
| **korbmacher (simple stats table)** | Y — works well. 97.7 accuracy, clean numeric cells, light post-processing only |
| **ziano (landscape, two-tables-side-by-side)** | Conditional — raw extraction is faithful but requires a split-and-merge post-processing step |
| **Install / runtime production-viable** | Y (stream-only, no Ghostscript) / Conditional (lattice needs Ghostscript) |

### Compared to alternatives

- **pdftotext default**: Linearizes columns into single-spaced prose — unrecoverable for multi-column tables.
- **pdfplumber lattice**: 0 cells on APA whitespace tables.
- **Camelot stream**: Actually detects and segments the tables. Data cells are clean. The main challenge is structural (multi-row headers, side-by-side tables) which requires post-processing regardless of which tool is used.

### Signal

For simple APA stats matrices (korbmacher-type), Camelot stream is a strong candidate — essentially no parameter tuning needed, high accuracy, clean cells. For complex landscape tables with side-by-side layouts (ziano-type), it still beats pdftotext and pdfplumber lattice but needs a post-processing layer to split and reconstruct the logical table structure. That post-processing is non-trivial but tractable.

**Bottom line**: Camelot stream is meaningfully better than the alternatives for the APA corpus. The Ghostscript dependency is a non-issue for stream-only mode. If the docpluck pipeline only needs stream flavor, this is a viable production dependency.
