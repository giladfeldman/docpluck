# Changelog

## [2.1.0] — 2026-05-09

Strict-bar iteration on a 101-PDF corpus across 9 academic styles (apa, ieee, nature, vancouver, aom, ama, asa, harvard, chicago-ad). 96–98 of 101 papers PASS or PASS_W under the pragmatic grader; all 9 styles converge (≥3 consecutive first-try-clean papers). 14 targeted fixes across the section identification + normalization layers; no API surface changes. See [`docs/superpowers/plans/sections-issues-backlog.md`](docs/superpowers/plans/sections-issues-backlog.md) for the full per-issue ledger and [`LESSONS.md`](LESSONS.md) for the durable architectural rules this iteration codified.

### Added — section identification

- New canonical label `SectionLabel.conclusion` (separate from `discussion`). Many empirical papers — especially IEEE technical, Collabra Psychology, JESP / Cogn Psych replication reports — have BOTH a Discussion section AND a brief Conclusion wrap-up. Mapping `Conclusion` to its own label preserves the distinction in the output rather than producing `discussion_2`. Combined `Discussion and Conclusion(s)` headings stay as `discussion`.
- Pattern A: lowercase line-isolated canonical headings now detected (Elsevier renders `Abstract` as `a b s t r a c t`, which pdftotext flattens to lowercase `abstract`).
- Sentence-case heading acceptance: `Materials and methods` (lowercase function words) alongside Title Case / ALL CAPS.
- Roman-numeral and letter numbering prefixes: `I. INTRODUCTION`, `II. METHODOLOGY`, `A. SUBSECTION` (IEEE / ACM technical papers).
- Pattern E synthesis (`core.py::_synthesize_abstract_from_leading_unknown`): when no Abstract heading is detected and the first section is a long unknown span, synthesize an `abstract` from the first ≥600-char prose paragraph. Smart citation-block detection skips the leading paragraph if it has DOI/`Department`/email tokens and is <1500 chars. Falls back to a per-line scan when the leading unknown is one big paragraph.
- Pattern E synthesis part 2 (`core.py::_synthesize_introduction_if_bloated_front_matter`): when no Introduction heading is detected and the front-matter section is >3000 chars and >5% of doc, split into shrunken-front-matter + introduction. Recovers bjps_1 (theory papers with body in keywords) and bloated-abstract Collabra/JDM cases.
- Taxonomy variants added — methods: `experiment`, `experiments`, `methodology`. results: `experimental results`, `evaluation`, `experimental evaluation`, `performance evaluation`. funding: `financial disclosure`, `financial disclosure/funding`, `funding/financial disclosure`. Conclusion variants: `conclusions`, `conclusion and future work`, `conclusions and future work`, `concluding remarks`.

### Removed — section taxonomy

- `summary` removed from canonical `abstract` set. In real-world psychology papers it is more often a mid-paper subsection (`Summary of Original Studies`, per-study summary in meta-analyses) than an abstract heading. The Royal Society Open Science layout that uses `1. Summary` as its abstract is recovered by Pattern E synthesis instead.

### Added — normalization (W0 publisher / running-header / footnote watermarks)

- Elsevier-style copyright stamp on its own line (`© 2009 Elsevier Inc. All rights reserved.`), including pdftotext's `Ó` flattening of `©`.
- Two-column running headers like `M. Muraven / Journal of Experimental Social Psychology 46 (2010) 465-468`.
- Creative Commons license footer sentences in abstract paragraphs.
- Collabra/UCPress watermark `Downloaded from <url> by guest on <date>` — relaxed the existing `Downloaded from` pattern to allow the optional intermediate `by guest` phrase. Was missing on every Collabra paper before.
- Author-equal-contribution footnote line (`a Surname, Surname, … are equal-contribution first authors b email`) — open-access journals print this at bottom of page 1; pdftotext interleaves it into the abstract.

### Documentation

- `LESSONS.md` (NEW) — durable incident log with five lessons (L-001 to L-005). Most critical: L-001, "never swap the PDF text-extraction tool as a fix for downstream problems." Three sessions in a row had re-derived this lesson by trial and error; this iteration codifies it permanently.
- `docs/DESIGN.md` §13 — explicit `text channel (pdftotext)` vs `layout channel (pdfplumber)` architecture rule, with the right layer to fix each class of real-world-paper artifact.
- `CLAUDE.md` Critical hard rules section now leads with the channel-separation rule and points future sessions at LESSONS.md before they touch `extract*.py` / `normalize.py` / `sections/`.
- Inline guard comment at the PDF branch of `extract_sections()` warning future sessions not to swap `extract_pdf` for `extract_pdf_layout`.

### Compatibility

- All public APIs unchanged. Library is drop-in compatible with v2.0.0 callers.
- `SECTIONING_VERSION`: `1.1.0` → `1.2.0` (additive: new `conclusion` label).
- `NORMALIZATION_VERSION`: `1.6.0` → `1.7.0` (additive: new W0 watermark patterns).
- Section partitioning output may differ on Collabra Psychology, RSOS, IEEE, and Elsevier two-column papers — these previously emitted bloated front-matter / missing abstract / `discussion_2` instead of `conclusion`. Behavior on the 250+ unit-test corpus is unchanged.

### Tests

- 749 passed, 18 skipped (full repo suite). 255 passed + 2 skipped on `tests/test_sections_*.py` + `tests/test_normalization.py`.
- 14 new W0 unit tests in `TestW0_PublisherCopyrightAndRunningHeader`.
- New sectioning tests for `conclusion` canonicalization, lowercase-isolated heading acceptance, Roman-numeral prefix parsing, sentence-case heading acceptance, and Pattern E synthesis.

## [2.0.0] — 2026-05-07

A combined release: structured-extraction (tables + figures) and a section-identification surgical fix that makes sectioning actually usable on real APA papers. Both work streams landed concurrently on `feat/table-extraction` and ship together.

### Added — structured extraction

- `extract_pdf_structured()` — structured PDF extraction returning tables, figures, page count, method, and text in a single call. Opt-in companion to `extract_pdf()`; the existing function is unchanged.
- `docpluck.tables` package — table region detection, lattice + whitespace cell clustering, HTML rendering, confidence scoring with isolation fallback (`ISOLATION_THRESHOLD = 0.4`).
- `docpluck.figures` package — caption-anchored figure detection (label, page, bbox, caption metadata only; no image extraction in v2.0).
- `Cell`, `Table`, `Figure`, `StructuredResult` TypedDicts and `TABLE_EXTRACTION_VERSION` re-exported from top-level `docpluck`.
- New CLI flags on `docpluck extract`: `--structured`, `--thorough`, `--text-mode {raw,placeholder}`, `--tables-only`, `--figures-only`, `--html-tables-to DIR`.
- F0 footnote-strip in `normalize_text()` accepts a new `table_regions=` kwarg; lines whose y-range falls inside any provided table region are preserved (so table footnotes like `Note. *p < .05.` are not misclassified as page footnotes).
- New geometric primitives on `LayoutDoc.PageLayout`: `lines`, `rects`, `curves`, `chars`, `words` — all additive.
- 12-fixture smoke corpus driven by `tests/fixtures/structured/MANIFEST.json` (manifest-only — PDFs not committed; tests skip cleanly when source PDFs are not on the local Dropbox tree).
- Backwards-compat snapshot tests for `extract_pdf()` across all 12 fixtures (output is byte-identical to v1.6.x).

### Changed — section identification (surgical fix)

- **Architectural pivot.** The PDF section path now consumes `extract_pdf` (pdftotext) + `normalize_text(academic)` instead of `extract_pdf_layout` (pdfplumber). Sectioning runs after the library's canonical 22-step normalization pipeline (hyphenation repair, line-break joining, header/footer removal, footnote stripping, page-number scrub, watermark strip, statistical pattern repair, etc.) and so inherits all of it for free. The pdfplumber-based path was producing column-merged text (e.g. `References` jammed mid-line into body text) and font-size heuristics that failed on body-font-bold headings (`Abstract`). Result on a 5-paper APA corpus: every canonical section is detected, no garbage `unknown` spans, no running-header contamination.
- **Section partitioner: only canonical-taxonomy heading matches create section markers.** v1.6.0 promoted any layout-strong heading (including page running headers, citation residue, methods/results subsections) to an `unknown` section, which on real APA papers shredded ~90% of the document into incoherent fragments. Layout-strong headings whose text isn't in the canonical taxonomy are no longer separate sections.
- **`SECTIONING_VERSION` 1.0.0 → 1.1.0** (additive `subheadings` field; output shape change).
- **Boundary-aware truncation disabled** for all canonical labels. With strict canonical-only markers + clean normalized text, truncation patterns (Email/ORCID/author-bio caps) were destructive — cutting References to a few characters or chopping Introduction at a `Corresponding Author:` line.

### Added — section identification

- `Section.subheadings: tuple[str, ...]` (default `()`) — placeholder for in-section structure surfaced by future smart subheading detection. Empty in v2.0.0; populated in a later release.
- Text annotator detects canonical headings whether line-isolated, followed by Capital-body word, or preceded by blank line — so `Abstract Jordan et al., 2011...` style (heading + first paragraph on one line) is caught.
- CRediT author-contribution table cells are filtered out of heading candidates (e.g. `Methodology\n\nX\n\nPre-registration peer review`).

### Fixed — section identification

- Adjacent same-canonical-label markers with a small gap coalesce into one span (handles `Introduction\nBackground\n...` producing one `introduction` instead of `introduction` + `introduction_2`).
- `Acknowledgments`, `Author Contributions`, `Funding`, `Keywords` are now detected when preceded by single-newline paragraph break (not just blank-line).
- `References`, `Appendix`, `Supplementary` no longer truncate at `Email:` / `ORCID:` / author-bio boundary patterns.
- `Declaration of Competing Interest` (Elsevier-style) added to `conflict_of_interest` taxonomy variants.

### Removed — section taxonomy tightening

- `procedure`, `procedures` removed from canonical `methods` set — APA subsection labels, not top-level sections.
- `study design`, `experimental design`, `methodology` removed from canonical `methods` set — same reason.
- `summary` removed from canonical `abstract` set — too ambiguous (meta-analyses use it as per-study subheading).

### Compatibility

- `extract_pdf()` output is byte-identical to v1.6.x — verified by snapshot tests on 12 PDFs.
- All existing public APIs unchanged.
- New surface (structured extraction) is purely additive; opt-in via `extract_pdf_structured()` or `--structured` CLI flag.
- `Section.subheadings` is an additive dataclass field with default `()`; existing constructors keep working unchanged.

### Known limitations (sections)

- Papers with no `Introduction` heading (some JESP papers jump from Abstract directly to `6.2. Method`) produce a large `abstract` span covering both abstract and intro. Structural — without an explicit marker, the partitioner can't break the section.
- Meta-analyses with embedded per-study summaries may produce unusual section ordering. v2.0.0's section target is well-formatted single-study APA papers.
- `subheadings` field is empty by design in v2.0.0 (smart list-vs-heading discrimination deferred).

### Internal

- Sections package: `extract_pdf_layout` and `_annotate_layout` (pdfplumber PDF annotator) are no longer used by the sections path. They remain in the library for use by the structured (tables/figures) module. F0 step in normalize remains for callers who explicitly pass `layout=...`.
- Coordination: structured extraction builds on top of `extract_pdf_layout()` / `LayoutDoc`; resolves the latent F0 / table-footnote conflict noted in v1.6.0's spec.

## [1.6.0] — 2026-05-06

### Added

- New `docpluck.sections` package: identifies academic-paper sections (abstract,
  methods, references, disclosures, …) with universal char-level coverage and
  per-section confidence + provenance. See
  `docs/superpowers/specs/2026-05-06-section-identification-design.md`.
  - 18 canonical labels + `unknown` fallback + numeric suffixes for repeats
    (e.g. `methods_2` for multi-study papers).
  - Two-tier algorithm: format-aware annotators (PDF/DOCX/HTML) +
    unified core canonicalizer.
  - `SECTIONING_VERSION` constant ("1.0.0") on every `SectionedDocument`.
- New internal `docpluck.extract_layout` module: pdfplumber-based layout
  extraction (per-page bounding boxes + font sizes). API not promised externally
  in this release.
- New `F0` step in `normalize_text(text, level, layout=...)`: layout-aware
  stripping of footnotes, running headers, and running footers. Footnotes are
  preserved and surface as the `footnotes` section.
- Filter sugar on existing extract calls: `extract_pdf(b, sections=["abstract",
  "references"])` returns concatenated section text in document order. Same
  kwarg added to `extract_docx` and `extract_html`.
- New CLI subcommands: `docpluck extract <file> --sections=...`,
  `docpluck sections <file> [--format json|summary]`.

### Changed

- `NormalizationReport` gains `footnote_spans` and `page_offsets` fields
  (default empty tuples). Existing field/tuple-unpacking call sites are
  unchanged.

### Backwards compatibility

- `extract_pdf(bytes)`, `extract_docx(bytes)`, `extract_html(bytes)` byte-
  identical to v1.5.0 when called without the new `sections=` kwarg.
- `normalize_text(text, level)` byte-identical to v1.5.0 when called without
  the new `layout=` kwarg.

## [1.5.0] — 2026-04-27

### Added (Scimeto Request 9 — reference-list normalization)

- **W0 — Watermark template library** (runs in standard + academic, before S0).
  Strips four publisher-overlay templates that previously bled into the body
  text: `Downloaded from URL on DATE`, the RSOS running-footer artifact
  (`\d+royalsocietypublishing.org/journal/\w+ R. Soc. Open Sci. \d+: \d+`),
  Wiley/Elsevier-style `Provided by ... on YYYY-MM-DD`, and
  `This article is protected by copyright....`. Defense-in-depth alongside
  S9's repetition-based scrub; bounds blast radius before any reflow.
- **R2 — Inline orphan page-number scrub** (academic, inside references span).
  Repairs the silent corruption case where pdftotext glued a page-header digit
  between two body words inside a reference (e.g. ref 17 of the Li&Feldman
  PDF read `psychological 41 science.` because `41` is the journal page).
  Uses lowercase-surround guard to avoid touching volume numbers, page
  ranges, or year boundaries.
- **R3 — Continuation-line join** (academic, inside references span).
  Joins lines inside the bibliography that don't start with a Vancouver,
  IEEE, or APA reference marker onto the preceding reference. Eliminates
  orphan-paragraph artifacts that mid-ref column wraps used to produce.
- **A7 — DOI cross-line repair** (academic, document-wide).
  Rejoins DOIs broken across a line by pdftotext (`(doi:10.\n1007/...)`).
  The `doi:` prefix in the lookbehind chain is load-bearing — without it
  the rule would damage decimals at line ends in normal prose.

### Helper

- New `_find_references_spans` returns ALL qualifying bibliography spans
  (a header followed within 5k chars by ≥3 ref-like patterns) in document
  order, so PDFs with both a main and a supplementary bibliography get
  R2/R3 applied to each.

### Tests

- Added `tests/test_request_09_reference_normalization.py` (5 cases) gated on
  the Li&Feldman 2025 RSOS fixture PDF (skipped if absent). Asserts the four
  acceptance criteria from the request: watermark URL absent, RSOS footer
  absent, bibliography splits cleanly into 45 numbered chunks 1..45, ref 17
  free of `41 science`, ref 38 DOI rejoined.
- Existing `TestVersionBumps` updated to expect `1.5.0`.
- Full suite: **425 passing, 9 skipped** (+5 new cases).

### Pretest finding (revises the original request's diagnosis)

Scimeto's reproducer used `pdftotext -layout`. Docpluck explicitly avoids
`-layout` (see `extract.py:13–16`). On actual Docpluck output of the same
PDF, the full-URL watermark and orphan-paragraph reflow described in the
request are **already** absent — S9's repetition-based scrub kills the URL
banner, and default pdftotext reading-order reflow eliminates the
orphan-paragraph artifact. The three artifacts that did survive
(page-number digit residue, mid-ref `\n`, DOI line break) are now fixed.
Corpus dry-run: 51 PDFs, 0 regressions, 46 changed.

### Versioning

- `__version__`: 1.4.5 → **1.5.0**
- `NORMALIZATION_VERSION`: 1.4.5 → **1.5.0**
- New `changes_made` keys: `watermarks_stripped`, `inline_pgnum_scrubbed`,
  `ref_continuations_joined`, `doi_rejoined`.
- New step codes: `W0_watermark_strip`, `R2_inline_pgnum_scrub`,
  `R3_continuation_join`, `A7_doi_rejoin`.

## [1.4.4] — 2026-04-11

### Fixed (code-review follow-up to v1.4.3)

- **A3b was too permissive** — the initial v1.4.3 pattern
  `(\b[A-Za-z]{1,4})\[(\d+,\d+)\]` matched any 1-4 letter word before a
  bracketed numeric pair, which falsely converted citation/figure/
  equation references like `ref[1,2]`, `fig[1,2]`, `eq[1,2]` into
  `ref(1, 2)`, `fig(1, 2)`, `eq(1, 2)`. Tightened the pattern to require
  `=` immediately after the closing `]` — the assignment marker is the
  real signal that the bracketed pair is a df expression being assigned
  to a test statistic (as in `F[2,42]= 13.689`), not a reference list.
  Caught in the docpluck-review skill pass immediately after v1.4.3 tag.

### Tests

- Added `test_a3b_does_not_fire_on_short_word_citations` with 4 probes.
- Added `test_a3b_still_fires_on_real_stat_with_equals` as a positive-
  path regression guard.
- Full suite: **267 passing, 9 skipped** (+2 new cases vs v1.4.3).

## [1.4.3] — 2026-04-11

### Fixed (MetaESCI D1/D2 lost-source repro)

- **A3 lookbehind regression (D2 root cause).** The Braunstein lookbehind
  `(?<![a-zA-Z,0-9])` added in v1.4.1 did not exclude `[` or `(`, so
  pdftotext output like `F[2,42]=13.689` or `F(2,42)=13.689` (tight-
  spaced df forms with no space after the comma) was corrupted to
  `F[2.42]` / `F(2.42)` — converting the df separator into a decimal
  point. Downstream effectcheck regex then failed to parse the stat and
  silently dropped the row. Fix: lookbehind now excludes
  `[a-zA-Z,0-9\[\(]`. Discovered via MetaESCI D2 repro on
  `10.15626/mp.2019.1723` where docpluck produced 0 rows vs checkpdfdir's
  3 rows.
- **A3b statistical df-bracket harmonization (new step).** Some PDFs
  encode F/t/chi2 degrees of freedom with square brackets, e.g.
  `F[2,42]=13.689`. effectcheck's `parse.R` only matches parenthesized
  df, so bracketed forms are silently dropped. A3b converts the bracket
  form to canonical parens when the bracket immediately follows a short
  stat identifier. Runs in academic level only, after A3 and before A4.
  Tracked in `NormalizationReport.steps_applied` as
  `A3b_stat_bracket_to_paren`.

### Changed

- `NORMALIZATION_VERSION` bumped `"1.4.1"` → `"1.4.2"` to reflect the A3b
  addition and the A3 lookbehind semantic change. Downstream consumers
  should invalidate their extraction cache on this bump.

### Tests

- New `TestA3_StatBracketLookbehind` class in `tests/test_normalization.py`
  with 5 regression cases covering square-bracket and tight-paren df
  forms, thousands-separator tight-paren form (`t(1,197)`), and a
  citation-list negative case (`[1,2]` must not become `(1,2)`).
- Full suite: **265 passed, 9 skipped** (+5 new cases vs v1.4.2).

### Notes for MetaESCI downstream gaps

- **D1** (row-count drops across 6 sources): 3 of 30 lost rows are
  directly fixed by the A3/A3b changes above (all from
  `10.15626/mp.2019.1723`). The remaining ~27 rows contain cleanly
  normalized text in the docpluck output and appear to be effectcheck
  `parse.R` edge cases (uppercase `P`, table rows with pipe separators,
  and clean `F(df1, df2) = xx.xxx` forms that should match but don't).
  Report these to the effectcheck team with the PDFs:
  `10.1525/collabra.150`, `10.1177/0146167210376761`,
  `10.1177/0146167220977709`, `10.15626/mp.2021.2803`,
  `10.1098/rsos.211412`.
- **D4** (CI width-ratio divergences): the `raw_text` columns are
  byte-identical between Run A and Run B; only the computed CI bounds
  differ. That places the divergence in effectcheck's CI compute logic
  (`compute_ci` / `compute.R`), not in docpluck normalization. Not
  actionable on the docpluck side.

## [1.4.2] — 2026-04-11

### Added (MetaESCI D3/D5/D6/D7 follow-ups)

Addresses the non-blocking items MetaESCI filed in
`REQUESTS_FROM_METAESCI.md` ahead of the full 8,455-PDF batch. No
normalization semantics changed — `NORMALIZATION_VERSION` is still
`"1.4.1"`, so outputs byte-identical against v1.4.1 except for the
diagnostics changes below.

- **`docpluck.extract_pdf_file(path)`** — path-based wrapper around
  `extract_pdf(bytes)` that raises a clean `FileNotFoundError` with the
  offending path when the file is missing or is not a regular file (D7.1).
  Keeps the bytes API untouched.
- **`docpluck.extract_to_dir(paths, out_dir, level)`** + new
  **`ExtractionReport`** dataclass in `docpluck/batch.py` (D6). Batch
  runner that writes `<stem>.txt` (+ optional `<stem>.json` sidecar) for
  each input PDF and returns a serializable receipt with the library
  version, normalize version, git SHA, per-file method, timings, and
  failure reasons. `report.write_receipt(path)` persists it for
  downstream reproducibility pinning. Exceptions inside the loop are
  recorded, not raised — batch runs never abort on a single bad file.
- **`docpluck.get_version_info()`** + `docpluck/cli.py` (D3). New console
  entry point `docpluck --version` (also `python -m docpluck --version`)
  prints a single JSON line
  `{"version": ..., "normalize_version": ..., "git_sha": ...}`. Batch
  runners can call this once per run and stash the output next to
  results as a "bundle receipt".
- **`NormalizationReport.steps_changed`** (D7.2). New list alongside the
  existing `steps_applied`, containing only pipeline steps that actually
  modified the text. `steps_applied` is unchanged for backward compat;
  `to_dict()` now exposes both. Use `steps_changed` when you want to
  know what the pipeline *did* on a given input vs. what it *ran*.

### Fixed

- `docpluck/__init__.py` `__version__` was stale at `"1.3.1"` despite
  `pyproject.toml` and `NORMALIZATION_VERSION` both advancing to
  `"1.4.1"`. Now synced to `"1.4.2"`.

### Docs

- `docs/NORMALIZATION.md` — A5 section clarifies that
  `NormalizationLevel.academic` intentionally transliterates Greek
  statistical letters (η²→eta2, χ²→chi2, etc.) and points callers who
  need Greek preserved at `NormalizationLevel.standard` (D5).

### Unchanged

- `NORMALIZATION_VERSION` stays at `"1.4.1"`. No regex, no A-rule
  thresholds, no tokenization changed. Fresh batch runs against v1.4.2
  produce identical `data/results` to v1.4.1 given the same corpus —
  only diagnostic fields differ.
- All 227 pre-existing tests continue to pass. New tests added for
  `extract_pdf_file`, `extract_to_dir`, `steps_changed`, and the CLI.

### Deferred (requires MetaESCI repro data)

- **D1** (classify 4 + 54 dropped rows vs checkPDFdir) — needs the two
  A/B CSVs per subset that MetaESCI references but that currently only
  exist as a single merged CSV in their `data/results/subset/` tree.
- **D2** (one lost source per subset) — same.
- **D4** (A4 CI harmonization regex audit) — read-only audit done; see
  `REPLY_FROM_DOCPLUCK.md` for the preliminary hypothesis. No regex
  change until a real repro lands.

## [1.4.1] — 2026-04-11

### Fixed

- **A3 lookbehind to block author affiliation false-positives** (ESCImate
  report via `effectcheck/R/parse.R:189`). The v1.4.0 A3 decimal-comma rule
  was corrupting multi-affiliation citation markers like `Braunstein1,3`
  into `Braunstein1.3`. Added a `(?<![a-zA-Z,0-9])` lookbehind that blocks
  three classes of false positive:

  1. Author affiliations like `Braunstein1,3` — the letter before `1`
     blocks the match.
  2. Multi-affiliation sequences like `Wagner1,3,4` — both the letter
     before `1` and the comma before `3` block.
  3. Bracket-internal multi-value content like `[0.45,0.89]` — the digit
     before the comma blocks (A4 handles the bracket normalization).

  Six new regression tests under `TestA3_BraunsteinLookbehind`. Full suite:
  247 passed, 8 skipped.

### Compatibility

- No public API changes. `NORMALIZATION_VERSION` bumped `1.4.0 -> 1.4.1`.

## [1.4.0] — 2026-04-11

### Added

- **A3a thousands-separator protection** (ESCImate Request 1.1). The A3
  decimal-comma rule was corrupting `N = 1,182` to `N = 1.182`, which
  downstream parsers read as a sample size of 1.182 people. New step A3a
  runs before A3 and strips commas from only the integer token in known
  sample-size contexts (`N` / `n` / `df` / `"sample size of"` /
  `"total of ... participants"`), so A3 sees an already-clean integer and
  leaves it alone.
- **S5a FFFD eta context recovery** (ESCImate Request 1.2). pdftotext
  occasionally drops Greek eta (U+03B7) as U+FFFD even after the
  pdfplumber SMP fallback. Added a context-aware second line of defense
  that rewrites `U+FFFD` to `"eta"` **only** when followed by a statistical
  eta-squared pattern (`² = .NNN` / `2 = .NNN`, including the `_p²` partial
  variant). Generic FFFDs in prose are left alone for the quality scorer
  to flag.

### Verified (no code change)

- A5 Greek transliteration runs inside the academic block. Consumers that
  need Greek preserved should pass `NormalizationLevel.standard`; the
  effectcheck parser handles both forms. Documented in v1.4.2 after the
  MetaESCI D5 follow-up.

### Compatibility

- No public API changes. `NORMALIZATION_VERSION` bumped `1.3.1 -> 1.4.0`.

## [1.3.1] — 2026-04-11

### Fixed (normalization + quality scoring)

Three gaps identified by the v1.3.0 MetaESCI 200-DOI regression baseline, all
closed in this release. After the fixes, the same benchmark passes 9/9 criteria
(200/200 files, 100% high confidence, avg quality 99.95/100, zero residual
artifacts). No regressions in the 27 pre-existing tests or in the DOCX/PDF
cross-format benchmarks.

1. **A1 column-bleed extension.** PSPB multi-column layouts produce patterns
   like `p\n\n01\n\n01\n\n= .28` where `01` lines are column-bleed fragments.
   Two new A1 rules tolerate up to 4 short digit-only fragment lines — one for
   `p\n...\n=`, one for `p =\n...\n value`. They run *before* the simple
   `p =\n digit` rule so the first fragment isn't mis-joined. Regression tests
   in `tests/test_normalization.py::TestA1_ColumnBleed`.

2. **A2 widening.** A2's `val > 1.0` threshold rejected `p = 01` (float value
   1.0). Changed to `val >= 1.0`; the `\d{2,3}` prefix still prevents touching
   `p = 1`. The lookahead was extended to accept a sentence-ending period via
   `\.(?!\d)` but still rejects real decimals like `p = 15.8`. Regression tests
   in `tests/test_normalization.py::TestA2_DroppedDecimalV2`.

3. **Quality scorer — corruption signal required for garbled flag.** The
   v1.3.0 scorer flagged non-prose documents (reviewer acknowledgment lists,
   reference dumps) as garbled because it only looked at common-word ratio.
   v1.3.1 requires at least one independent corruption signal (U+FFFD / non-ASCII
   ratio > 20% / ≥20 ligatures / text < 500 chars) before flagging. Real
   column-merge garbage still trips the signal (always retains ligatures);
   valid non-prose content does not. Regression tests in `test_quality.py`.

### Changed

- `NORMALIZATION_VERSION` bumped from `"1.2.0"` to `"1.3.1"` so downstream
  consumers can detect the new pipeline. `NormalizationReport.version` reflects
  the change.
- `compute_quality_score()` result dict gains a new field
  `details.has_corruption_signal` (bool).
- Internal dropped-decimal benchmark detection regex tightened to match A2's
  own lookahead so diagnostic candidates align with what A2 actually fixes
  (prevents false positives like `p = 15.8` from column-merged table cells).

### Compatibility

- No public API changes. `extract_pdf`, `extract_docx`, `extract_html`,
  `normalize_text`, and `compute_quality_score` signatures are unchanged.
- All 211 pre-existing tests continue to pass. 16 new regression tests added
  (total 227).
- Verified no regressions on Scimeto/CitationGuard DOCX corpus (20/20 real
  papers extract at 100/100 quality) or cross-format parity (99.0% similarity
  on the DOCX→PDF spot check, identical to v1.3.0).

## [1.3.0] — 2026-04-10

### Added
- **Private benchmark suite** stress-testing extraction on a 24-file real-world DOCX corpus and bidirectional cross-format comparisons (DOCX↔PDF via Word, PDF→DOCX via `pdf2docx`). Results: 20/20 DOCX real files extracted at 100/100 quality, 98.8% avg DOCX→PDF similarity, format parity between `extract_docx` and `extract_pdf` confirmed. Scripts and per-file results live in a private research repo.
- **Phase 2 benchmark section** in `docs/BENCHMARKS.md` documenting the aggregate results.
- **Benchmark mode** in the `docpluck-qa` skill: triggered by "DOCX benchmark", "--benchmark-docx", "format parity", etc. Does NOT run during normal QA (5–15 min; launches Word).
- **DOCX extraction** via `extract_docx()` — uses `mammoth` to convert DOCX to HTML
  (preserving Shift+Enter soft breaks as `<br>` tags) then runs the same tree-walk
  used for native HTML. Ported from Scimeto's production code (running since Dec 2025).
- **HTML extraction** via `extract_html()` and `html_to_text()` — uses `beautifulsoup4`
  + `lxml` with a custom block/inline-aware tree-walk. Specifically regression-tested
  against the "ChanORCID" bug (adjacent inline elements merging text).
- **Optional dependency groups** in `pyproject.toml`:
  - `docpluck[docx]` adds mammoth
  - `docpluck[html]` adds beautifulsoup4 + lxml
  - `docpluck[all]` adds everything
  Core `pip install docpluck` still installs only pdfplumber for PDF support.
- **60 new tests** (46 HTML + 18 DOCX + 12 benchmark + corrections), bringing total to 211:
  - `tests/test_extract_html.py` — block/inline handling, ChanORCID regression,
    whitespace normalization, HTML entities, academic patterns
  - `tests/test_extract_docx.py` — mammoth integration, soft breaks, smart quotes,
    statistical values, ligature normalization integration, error handling
  - `tests/test_benchmark_docx_html.py` — 15 ground-truth statistical passages survive
    extraction and normalization for both formats with rapidfuzz ≥ 90% matching.
    Idempotency, quality scoring, and performance verified.
- **FastAPI service updates** (`PDFextractor/service/app/main.py`):
  - File type detection (PDF, DOCX, HTML, HTM) with per-type magic-byte validation
  - Extraction routing to the correct engine
  - Response format adds `file_type` field; `pdf_hash` kept for backward compat
  - Health endpoint reports all engines and supported types
- **Documentation** updates to README, BENCHMARKS, and DESIGN covering the new formats,
  library choices, rejected alternatives, and known limitations (OMML equations,
  tracked changes, memory usage).

### Changed
- `extract_html` and `extract_docx` use lazy imports so the core library still works
  without the optional dependencies installed.
- Version bumped to 1.3.0.

### Known limitations (documented, not bugs)
- **OMML equations** in DOCX are silently dropped (mammoth limitation). Rare in social
  science where stats are written as plain text; affects STEM papers.
- **Tracked changes** in DOCX are only partially handled by mammoth.
- **No page counting** for DOCX/HTML — `pages` is `None` for non-PDF formats.

## [1.1.0] — 2026-04-06

### Added
- S6: Soft hyphen (U+00AD) removal — was silently breaking text search across 14/50 test PDFs
- S6: Full-width ASCII→ASCII (U+FF01-FF5E) — handles full-width digit/letter patterns
- S6: All Unicode space variants (U+2002-U+205F, U+3000, ZWJ/ZWNJ)
- A5: Greek statistical letters (η→eta, χ→chi, ω→omega, α→alpha, β→beta, δ→delta, σ→sigma, φ→phi, μ→mu)
- A5: Combined forms (η²→eta2, χ²→chi2, ω²→omega2) and all superscript/subscript digits
- A6 (new step): Footnote marker removal after statistical values ("p < .001¹" → "p < .001")
- 151 tests across 6 test files

### Fixed
- A1 now runs before S9 to prevent page-number stripping of statistical values split across lines
- Possessive quantifiers in all line-break joining regexes to prevent catastrophic backtracking

## [1.0.0] — 2026-03-15

Initial release. Extracted from the Docpluck academic PDF extraction service.

### Features
- `extract_pdf()` — pdftotext primary + pdfplumber SMP fallback
- `normalize_text()` — 14-step pipeline (S0-S9, A1-A5) at three levels: none/standard/academic
- `compute_quality_score()` — composite quality metric with garbled detection
- 122 tests across 6 test files
