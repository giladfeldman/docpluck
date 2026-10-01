# docpluck

**Text, section, table and statistic extraction from academic papers (PDF, DOCX, HTML), built
for meta-science.**

docpluck turns a research article into text you can run statistical checks on. It extracts the
text layer, repairs the damage extraction itself causes (lost minus signs, split ligatures,
interleaved columns, Greek letters decoded as Latin), identifies the paper's sections, pulls
tables out as cell grids, flattens table rows into records a statistics checker can read, and
renders the whole paper as Markdown. Every output carries a record of what the library had to
guess or refused to guess, and a provenance block naming every engine version that shaped it.

It is a Python library and a command-line tool. A hosted web version runs at
[docpluck.app](https://docpluck.app).

- [Why this exists](#why-this-exists)
- [Scope: what docpluck will and will not change](#scope-what-docpluck-will-and-will-not-change)
- [Install](#install)
- [Quickstart](#quickstart)
- [Features](#features)
- [Command-line interface](#command-line-interface)
- [Configuration](#configuration)
- [Output formats](#output-formats)
- [Limitations and failure modes](#limitations-and-failure-modes)
- [Documentation](#documentation)
- [Citing, license, contributing](#citing-docpluck)

---

## Why this exists

Automated checks of the published record — recomputing *p*-values from reported test
statistics ([Nuijten et al., 2016](https://doi.org/10.3758/s13428-015-0664-2)), testing whether
reported means are possible given the sample size
([Brown & Heathers, 2017](https://doi.org/10.1177/1948550616673876)), collecting effect sizes
for meta-analysis — all start from the text of a paper. A PDF does not store that text
faithfully. Its text layer can drop the minus sign in `r = −.24`, decode `η²p` as `n2p`, emit
`<` as `b`, split `signiﬁcant` at the ligature, or read a two-column page across both columns
at once. Each of those silently changes or hides a statistic, and a checker built on top of it
cannot tell.

docpluck is the extraction layer for such checkers. It treats three things as its job:

1. **Deliver what is printed on the page**, in one canonical notation
   (`η²` → `eta2`, Unicode minus → `-`), so that one pattern matches every paper.
2. **Say when it could not.** A table it dropped, a glyph repair it declined, a font whose Greek
   letters are unreliable — each is recorded in a `fallbacks` field on the result, per document.
3. **Make the output reproducible.** `get_version_info()` names the docpluck version, each
   pipeline version, and the exact versions of poppler, pdfplumber, Camelot and the other
   engines, because any of them can change the output under a fixed docpluck release.

## Scope: what docpluck will and will not change

> docpluck extracts and normalizes **English-language** science articles written in **US numeric
> convention** (`.` decimal, `,` thousands). **It canonicalises notation. It does not fix the
> paper.**

- **The paper's own errors reach you untouched.** `p = 484`, `p < 05`, or a reversed interval
  `[5.37, 4.66]` are passed through exactly as printed. Detecting them is the job of the tool
  that holds the parsed statistic; a silent repair would validate a number the paper never
  printed.
- **European numbers pass through as printed.** `d = 0,45` stays `d = 0,45`; `N = 1,182` keeps
  its comma. Converting them destroys the only evidence of what the paper meant.
- **What docpluck does fix is damage its own pipeline caused** — a glyph the text layer lost, a
  fused exponent, a `<` extracted as `b`. The test is: *did extraction break this, or did the
  paper?*

The full consumer contract is [docs/SCOPE.md](https://github.com/giladfeldman/docpluck/blob/main/docs/SCOPE.md).

## Install

Requires Python 3.10 or newer.

```bash
pip install "docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git"
```

To pin a release, append its tag: `...docpluck.git@v2.4.148`. The package is also on PyPI
(`pip install docpluck`); the GitHub tags are the release of record and PyPI can trail them,
so check `pip index versions docpluck` if you need a specific version from PyPI.

| extra | adds | needed for |
|---|---|---|
| *(none)* | pdfplumber, Camelot (with OpenCV) | PDF text, layout, tables, figures, rendering |
| `[docx]` | mammoth | `extract_docx`, `extract_docx_structured`, DOCX sections |
| `[html]` | beautifulsoup4, lxml | `extract_html`, `html_to_text`, HTML sections |
| `[all]` | both of the above | everything |
| `[dev]` | pytest and test-only packages | running the test suite |

**System programs** (not installable with pip):

- **poppler** — provides the `pdftotext` binary every PDF path uses. Linux/WSL:
  `apt-get install poppler-utils`; macOS: `brew install poppler`; Windows: download a build
  from <https://github.com/oschwartz10612/poppler-windows/releases> and add its `bin` folder
  to `PATH`.

Ghostscript is **not** required: Camelot's ruled-table ("lattice") mode rasterizes pages through
pypdfium2, which pip installs.

DOCX and HTML extraction, normalization, and quality scoring are pure Python.

## Quickstart

Point these at any paper. (The repository's documentation gate runs this exact block against a
synthetic paper generated by `scripts/docs_sample_documents.py`.)

```python
from docpluck import (
    extract_pdf, normalize_text, NormalizationLevel, compute_quality_score,
    extract_sections, SectionLabel, extract_pdf_structured, render_pdf_to_markdown,
)

pdf = open("paper.pdf", "rb").read()

# 1. Raw text. `method` names the engine path that produced it.
text, method = extract_pdf(pdf)
assert not text.startswith("ERROR:"), text

# 2. Canonical notation for statistical pattern matching, and a report of what changed.
clean, report = normalize_text(text, NormalizationLevel.academic)
print(report.version, report.changes_made, report.fallbacks)

# 3. Is the extraction usable at all?
quality = compute_quality_score(clean)
print(quality["score"], quality["confidence"], quality["garbled"])

# 4. The paper's structure.
doc = extract_sections(pdf, source_format="pdf")
print([(s.label, s.confidence.value) for s in doc.sections])
results_text = doc.text_for("results")          # every Results section, in order
all_methods = doc.all(SectionLabel.methods)     # methods, methods_2, ...

# 5. Tables and figures as data.
structured = extract_pdf_structured(pdf)
print(len(structured["tables"]), "tables;", structured["fallbacks"])

# 6. The whole paper as Markdown.
markdown = render_pdf_to_markdown(pdf)
```

The same from the command line:

```bash
docpluck extract paper.pdf
docpluck sections paper.pdf --format summary
docpluck extract paper.pdf --structured
docpluck render paper.pdf
```

## Features

Every name below is importable from the package root (`from docpluck import ...`). The full
signatures, parameters and return fields are in the
[API reference](https://github.com/giladfeldman/docpluck/blob/main/docs/README.md).

### Text extraction

| function | input | returns |
|---|---|---|
| `extract_pdf(pdf_bytes, *, sections=None, max_input_bytes=None, pdftotext_timeout_seconds=120)` | PDF bytes | `(text, method)` |
| `extract_pdf_file(path)` | PDF path | `(text, method)` |
| `extract_docx(docx_bytes, *, sections=None, max_input_bytes=None)` | DOCX bytes | `(text, "mammoth")` |
| `extract_html(html_bytes, *, sections=None, max_input_bytes=None)` | HTML bytes | `(text, "beautifulsoup")` |
| `html_to_text(html)` | HTML string | text |
| `count_pages(pdf_bytes)` | PDF bytes | page count, no external program needed |

- PDF text comes from poppler's `pdftotext` in its default reading-order mode. Pages where it
  reads a two-column layout in the wrong order are detected and re-extracted column by column;
  `method` then reads `pdftotext_default+column_corrected:<pages>`.
- `sections=["abstract", "results"]` returns only those sections' text (labels as in
  `SectionLabel`).
- A PDF failure is returned as text beginning `ERROR:` rather than raised; `max_input_bytes`
  raises `ValueError` when the input is larger.

### Normalization

`normalize_text(text, level)` returns `(text, NormalizationReport)`. Levels
(`NormalizationLevel`):

| level | does |
|---|---|
| `none` | nothing |
| `standard` | encoding cleanup, ligatures, dashes and minus signs, invisible characters, hyphenation, running headers, page numbers, footnote furniture |
| `academic` | `standard` plus statistical notation: line breaks inside statistics, CI delimiters, Greek letters and super/subscripts to ASCII (`η²` → `eta2`), and glyph repairs proven from the PDF's own font evidence |

The report lists `steps_applied`, `steps_changed`, `changes_made` (counts per change type),
`changes_made_by_step`, and `fallbacks`. Every step is documented in
[docs/NORMALIZATION.md](https://github.com/giladfeldman/docpluck/blob/main/docs/NORMALIZATION.md).
`NORMALIZATION_VERSION` identifies the pipeline.

**Symbol contract.** `symbol_contract()` returns the machine-readable mapping of every Greek
letter and super/subscript docpluck emits; `explain_symbol("η")` explains one character;
`SYMBOL_CONTRACT_VERSION` versions it. Build downstream patterns from this rather than from
samples — see [docs/SYMBOL_CONTRACT.md](https://github.com/giladfeldman/docpluck/blob/main/docs/SYMBOL_CONTRACT.md).

### Quality score

`compute_quality_score(text)` returns `score` (0–100), `confidence` (`high` ≥ 80, `medium`
≥ 50, `low`), `common_word_ratio` (share of common English words), `garbled`, and `details`
(remaining ligatures, U+FFFD count, non-ASCII ratio, `has_corruption_signal`). `garbled` is
`True` only when the common-word ratio is below 0.02 **and** there is independent evidence —
a corruption signal (any U+FFFD, more than 20% non-ASCII, or 20+ unexpanded ligatures) or text
shorter than 500 characters — so a legitimate name index or reference list is not flagged. `count_replacement_chars` and `count_greek_chars`
expose two of those signals directly.

### Sections

`extract_sections(file_bytes, source_format="pdf" | "docx" | "html")` — or `text=...` for text
you already have — returns a `SectionedDocument` whose `sections` partition the whole document:
every character belongs to exactly one `Section`, and unrecognised spans are labelled
`unknown` rather than merged into a neighbour. `doc.abstract`, `doc.introduction`,
`doc.methods`, `doc.results`, `doc.discussion` and `doc.references` return the first such
section; `doc.all(label)` returns every one (a multi-study paper has `methods`, `methods_2`,
...); `doc.text_for(*labels)` joins their text in document order; `doc.get(label)` matches one
exact label; `doc.to_dict()` serialises it. Each section carries `label` (e.g. `methods_2`),
`canonical_label` (the `SectionLabel` without the study suffix), `text`,
`char_start`/`char_end`, `pages`, `confidence` (`Confidence`), `detected_via` (`DetectedVia`:
heading match, document markup, layout signal, text pattern, or position), `heading_text`
and `subheadings`.
Labels (`SectionLabel`) cover the title block, abstract, keywords, introduction, methods,
results, discussion, conclusion, the endmatter statements (acknowledgments, funding, conflict
of interest, data availability, author contributions), references, appendix, supplementary
material and footnotes. `SECTIONING_VERSION` versions the algorithm; `sectioning_text_id`
fingerprints the text buffer the offsets index into.

### Tables and figures

`extract_pdf_structured(pdf_bytes, *, thorough=False, table_text_mode="raw")` and
`extract_docx_structured(docx_bytes)` return the same `StructuredResult`: `text`, `method`,
`page_count`, `tables`, `figures`, `table_extraction_version`, `fallbacks`, `fallback_details`.

- PDF tables are found by Camelot (ruled "lattice" and whitespace "stream" modes) anchored on
  `Table N` captions; `thorough=True` also scans pages without a caption. DOCX tables are read
  directly from the document's own table markup (`rendering="markup"`).
- Each `Table` has its caption, footnote, `cells` (row, column, spans, text, header flag,
  box), an HTML rendering, and two fields that say how far to trust it:
  `caption_status` (`matched`, `none_found`, `uncaptioned_candidate`) and `cell_geometry`
  (whether each cell's `bbox` is verified geometry or zeros, and why).
- `table_text_mode="placeholder"` replaces table and figure regions in `text` with
  `[Table 1: caption]` markers, so body-text checks do not read table cells twice.
- PDF figures (`Figure`) carry label, page, box and caption. DOCX figure extraction is not
  implemented and returns an empty list.

### Table rows as records

`flatten_tables_for_paper(tables)` (or `flatten_table(table)` for one) turns each body row of
each table into a `FlattenedRow`: its table, page, row label, header, cells, an English sentence
(`"Importance: t(741) = 3.93, p < .001, d = 0.29"`) and parsed `fields`. This is the input
format for downstream statistics checkers; the CLI writes it as JSON Lines with
`render --tables-jsonl`. `render_flattened_inline(rows, table_id=...)` renders rows back as a
Markdown block.

### Markdown rendering

`render_pdf_to_markdown(pdf_bytes, *, normalization_level=NormalizationLevel.academic,
flatten_tables_inline=False, report=None)` produces a complete Markdown document: section
headings, body text, tables as HTML, figure captions. Pass a `RenderReport()` as `report` to
receive the post-processing steps that changed the output, lines removed, and `fallbacks`.

### Batch extraction and reproducibility receipts

`extract_to_dir(pdf_paths, out_dir, level=NormalizationLevel.academic)` writes
`<stem>.txt` plus a `<stem>.json` sidecar per PDF and returns an `ExtractionReport` holding
every version input (docpluck, pipelines, Python, Unicode database, poppler, pdfplumber,
pdfminer.six, Camelot, pypdfium2, OpenCV, mammoth, beautifulsoup4, lxml) and one
`ExtractionFileResult` per file. `report.write_receipt(path)` saves it as JSON.
`get_version_info()` returns the same version block on its own.

### Layout channel

`extract_pdf_layout(pdf_bytes, *, pages=None)` returns a `LayoutDoc` with pdfplumber's
per-character font, size and position for each page. The table, figure and glyph-repair code
reads this channel; it is exposed for consumers that need geometry.

### What the library did instead: `fallbacks`

Structured results, `NormalizationReport`, `RenderReport` and batch sidecars all carry
`fallbacks` (event name → count) and `fallback_details` (event → which font, token or
exception). `{}` means every detector ran and found nothing; a detector that could not run
says so with a `*_not_run` event. Keys worth acting on are listed in the
[API reference](https://github.com/giladfeldman/docpluck/blob/main/docs/README.md#fallbacks--what-the-library-silently-did-instead-read-this).

## Command-line interface

Installed as `docpluck` (also `python -m docpluck`). The file type is chosen by extension:
`.pdf`, `.docx`, `.html`/`.htm`. Output goes to standard output as UTF-8.

| command | output |
|---|---|
| `docpluck --version` | JSON version block (same as `get_version_info()`) |
| `docpluck extract FILE` | extracted text |
| `docpluck extract FILE --sections abstract,results` | only those sections' text |
| `docpluck extract FILE --structured` | `StructuredResult` as JSON (PDF and DOCX) |
| `docpluck sections FILE [--format json\|summary]` | the `SectionedDocument` as JSON, or a one-line-per-section summary |
| `docpluck render FILE` | Markdown (PDF) |

Options for `extract --structured`:

| option | effect |
|---|---|
| `--thorough` | also scan pages without a table caption (PDF) |
| `--text-mode raw\|placeholder` | how table and figure regions appear in `text` (PDF) |
| `--tables-only` / `--figures-only` | omit the other list |
| `--html-tables-to DIR` | also write each table's HTML to `DIR/<id>.html` |

Options for `render`:

| option | effect |
|---|---|
| `--level none\|standard\|academic` | normalization level (default `academic`) |
| `--flatten-tables-inline` | add a readable one-sentence-per-row block below each table |
| `--tables-jsonl PATH` | write every `FlattenedRow` to `PATH` as JSON Lines |

## Configuration

docpluck reads no configuration files. These environment variables change behaviour; all
default to off.

| variable | effect when set to `1` |
|---|---|
| `DOCPLUCK_FALLBACK_LOG` | print every fallback event to standard error as it happens |
| `DOCPLUCK_DISABLE_CAMELOT` | skip Camelot; tables then come only from the non-Camelot paths |
| `DOCPLUCK_COLUMN_CORRECT_GENERAL` | experimental: apply two-column re-ordering to more pages (still gated on a clean central gutter and on every word surviving) |
| `DOCPLUCK_COLUMN_CORRECT_BANDED` | experimental: per-band re-extraction for mixed-layout pages the whole-page corrector skips |
| `DOCPLUCK_RCT_L2_BYPASS` | diagnostic only: disables two table-region guards, for measuring their effect |

## Output formats

- **Text** (`extract_*`, `normalize_text`): plain UTF-8. After `academic` normalization Greek
  letters and super/subscripts are ASCII names per the symbol contract.
- **Structured JSON** (`extract_*_structured`, `extract --structured`): the `StructuredResult`
  described above; field-by-field tables in the
  [API reference](https://github.com/giladfeldman/docpluck/blob/main/docs/README.md#output-schemas).
- **Sections JSON** (`sections`): `sections[]` with `label`, `canonical_label`, `text`,
  `char_start`, `char_end`, `pages`, `confidence`, `detected_via`, `heading_text`,
  `subheadings`, plus `sectioning_version` and `source_format`.
- **Flattened rows** (`--tables-jsonl`): one `FlattenedRow` JSON object per line.
- **Markdown** (`render`): headings, paragraphs, HTML tables, and a separate
  "Uncaptioned table candidates (unverified)" section for grids no caption claimed.

## Limitations and failure modes

- **Scope**: English-language articles in US numeric convention. Other languages are not
  supported; non-English section headings and `Tabla`/`Abbildung` captions are not recognised.
- **Scanned PDFs** with no text layer return little or no text. docpluck does no OCR; a low
  `compute_quality_score` is the signal.
- **Undecodable glyphs** (fonts without a usable character map) come through as U+FFFD, and
  are counted. They are not guessed.
- **DOCX**: page numbers do not exist in the format (`page_count` is `0`); figures are not
  extracted; tracked-change handling is minimal.
- **Tables**: complex layouts (merged headers, tables spanning pages, rotated pages) can be
  captured partially or not at all; each such case is recorded in `fallbacks`. Grids without a
  caption are kept but marked `uncaptioned_candidate` — roughly half are real tables and half
  are page furniture, so decide explicitly how your checks treat them.
- **Reproducibility**: output depends on the installed poppler and Camelot versions, not only on
  docpluck's version. Record `get_version_info()` with any result you publish.

## Documentation

| page | contents |
|---|---|
| [docs/README.md](https://github.com/giladfeldman/docpluck/blob/main/docs/README.md) | API reference: every function, parameter and output field |
| [docs/SCOPE.md](https://github.com/giladfeldman/docpluck/blob/main/docs/SCOPE.md) | consumer contract: what is and is not changed |
| [docs/SYMBOL_CONTRACT.md](https://github.com/giladfeldman/docpluck/blob/main/docs/SYMBOL_CONTRACT.md) | how each Greek letter and super/subscript is emitted |
| [docs/NORMALIZATION.md](https://github.com/giladfeldman/docpluck/blob/main/docs/NORMALIZATION.md) | every normalization step |
| [docs/DESIGN.md](https://github.com/giladfeldman/docpluck/blob/main/docs/DESIGN.md) | architecture and engine choices |
| [docs/BENCHMARKS.md](https://github.com/giladfeldman/docpluck/blob/main/docs/BENCHMARKS.md) | extraction benchmarks |
| [CHANGELOG.md](https://github.com/giladfeldman/docpluck/blob/main/CHANGELOG.md) | what changed in each release, and what a consumer will see change |

## Citing docpluck

If you use docpluck in research, cite the version you used (from `get_version_info()`):

> Feldman, G. (2026). *docpluck: Text and statistic extraction from academic papers*
> (Version 2.4.148) [Computer software]. https://github.com/giladfeldman/docpluck

Machine-readable metadata is in [CITATION.cff](CITATION.cff); GitHub's "Cite this repository"
button reads it.

## License

MIT — see [LICENSE](LICENSE). docpluck deliberately uses only permissively licensed PDF
engines (poppler's `pdftotext` as an external program, pdfplumber and Camelot as libraries).

## Contributing

Bug reports are most useful with the DOI of the paper and the page where the output differs
from what is printed. See [CONTRIBUTING.md](CONTRIBUTING.md).
