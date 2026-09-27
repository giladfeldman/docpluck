# Contributing to docpluck

Thank you for helping. docpluck feeds automated checks of published statistics, so the bar is
that every change is justified by a real paper and leaves the output no less faithful to what
is printed on the page.

## Reporting a problem

The most useful report names:

1. the paper's **DOI** and the **page** where the output differs from the printed page;
2. what the page prints and what docpluck returned (a short excerpt is enough);
3. the output of `docpluck --version`, which records every engine version involved.

Please do **not** attach or paste the article itself. Refer to it by DOI; we obtain papers
through our own channels, and this repository never stores article files or their text.

## Development setup

```bash
git clone https://github.com/giladfeldman/docpluck.git
cd docpluck
pip install -e ".[dev]"
pytest
```

PDF tests need poppler's `pdftotext` on `PATH`. Some tests read a corpus of real test papers
that is not distributed with this repository (papers are never stored here).

## Before opening a pull request

- `pytest` passes.
- `python scripts/check_docs_coverage.py` passes: every public function, parameter, output
  field, CLI option, environment variable and extra is documented in `README.md` or
  `docs/README.md`, and the README quickstart runs. If you add a public name, document it.
- `python scripts/check_docs_consistency.py` passes (documented version numbers match the code).
- `CHANGELOG.md` has an entry saying what a consumer will see change.

## Rules a change must respect

- **Notation, not repair.** docpluck canonicalises how things are written; it does not correct
  the paper's own errors. See [docs/SCOPE.md](docs/SCOPE.md).
- **General fixes only.** Key a rule on a structural signature (a layout pattern, a font or
  encoding signal), never on one paper, publisher or file name. Cite the real papers (by DOI)
  that show the shape.
- **Say what you did.** A new fallback or refused repair is recorded with
  `docpluck.telemetry.record_fallback`, so it reaches the `fallbacks` field consumers read.
- **Permissive licenses only.** PDF handling uses poppler (`pdftotext`, as an external
  program), pdfplumber and Camelot. AGPL libraries such as PyMuPDF cannot be used.
- **Never `pdftotext -layout`**: it interleaves columns.

## License

By contributing you agree that your contribution is licensed under the MIT License.
