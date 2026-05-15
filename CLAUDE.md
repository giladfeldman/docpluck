# Docpluck — Library Repo (giladfeldman/docpluck, public)

## Two-Repo Architecture

Docpluck is split across **two repos** under `Vibe/MetaScienceTools/`:

| Path | Repo | Visibility | Contains |
|------|------|------------|----------|
| `docpluck/` (this repo) | `github.com/giladfeldman/docpluck` | **public** | The `docpluck` Python library only. Published to PyPI as `docpluck`. |
| `PDFextractor/` | `github.com/giladfeldman/docpluckapp` | **private** | The SaaS app (Next.js + FastAPI). **No library code lives here** — the service imports `docpluck` via a git pin in `service/requirements.txt`. |

### Why split

- Library can be open-sourced under MIT and consumed by anyone via PyPI without exposing app secrets/auth/billing logic.
- App can iterate freely without forcing library releases.
- No code duplication: there is exactly one copy of `extract.py` / `normalize.py` / `quality.py` etc., and it lives here.

### How the app consumes this library

`PDFextractor/service/requirements.txt` pins:
```
docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git@v<VERSION>
```

When this library releases a new version, the app's `requirements.txt` git pin must be bumped or production silently keeps running the old library. The `/docpluck-deploy` skill's pre-flight check 4 enforces this.

## Release flow (library → production)

1. Make + commit changes in this repo. Bump `__version__` (in `docpluck/__init__.py`), `version` (in `pyproject.toml`), and `NORMALIZATION_VERSION` (in `docpluck/normalize.py`) consistently.
2. Update `CHANGELOG.md`.
3. Push to `main`, then tag: `git tag v<VERSION> && git push --tags`.
4. (Optional) Publish to PyPI: `python -m build && twine upload dist/*`.
5. In `PDFextractor/service/requirements.txt`, bump the `@v<VERSION>` git pin and update any frozen version examples in `PDFextractor/API.md`.
6. Run `/docpluck-deploy` from the docpluck repo — pre-flight check 4 verifies the pin matches.

Skipping step 5 is the most common failure mode. The deploy skill catches it.

## Spike work queue (table-rendering iteration)

> **The canonical work queue for the splice-spike is the most recent `docs/TRIAGE_<date>_corpus_assessment.md`.** Always read it first and pick the next iteration from its top-3 candidates. The handoff doc (`docs/HANDOFF_<date>_table_rendering_iteration_<N>.md`) is one input but goes stale across sessions; the triage is the *living* priority list, recomputed each broad-read of the corpus.

**Iteration discipline (set 2026-05-10 after a long run of patches missed bigger structural issues):**

1. Start each session by reading the active `TRIAGE_*.md`'s top-3 candidates.
2. Every 3-5 iterations OR when a new pattern emerges, run a fresh broad-read across 8-10 random `.md` outputs *as a reader, not a diff* — sample the document START (first 30 lines) where most user-visible issues live. Update `TRIAGE.md` in place: strike resolved items, add new ones, re-rank by severity × cost.
3. Verification (post-fix) catches regressions; audit (periodic broad-read) catches new structural issues. **Char-ratio + word-delta metrics are blind to "right words in wrong order under wrong heading"** — they will pass a broken-section paper. The reader-pass is required.
4. If 3-4 iters in a row produce only small char-ratio shifts on isolated papers, surface "diminishing returns; should we shift focus?" to the user proactively.

## Critical hard rules (from project history)

> **READ [`LESSONS.md`](./LESSONS.md) BEFORE TOUCHING `extract*.py`, `normalize.py`, or `sections/`.**
> It is the durable incident log for the recurring mistakes below.  When in doubt about a change, the answer is almost always already there.

- **EVERY FIX MUST BE GENERAL — serve all future PDFs, never a one-PDF quick-hack.** docpluck is a meta-science tool that processes arbitrary academic PDFs across many publishers. Every change must be keyed on a STRUCTURAL SIGNATURE — a typographic pattern, layout invariant, glyph-corruption shape, section-structure rule — never on paper identity, filename, or a string hard-coded from one PDF. A change that resolves one paper's quirk but risks regressions on others is the WRONG fix; find the general root cause. Regression tests use specific PDF fixtures, but the fix *logic* must generalize to any PDF with the same structural signature. Always run the full 26-paper baseline to confirm no regression; widen verification (broad-read, more AI-golds) when a fix touches a shared code path. Established by user directive 2026-05-15. See memory `feedback_general_fixes_not_pdf_specific`.
- **NEVER swap the PDF text-extraction tool as a fix for downstream problems.** The TEXT channel is `extract_pdf` (pdftotext default mode); the LAYOUT channel is `extract_pdf_layout` (pdfplumber).  They are not interchangeable text sources.  Sections / normalize / batch consume the text channel; tables / figures / F0-layout-strip consume the layout channel.  Real-world-paper bugs (watermarks in body, abstract not detected, column interleaving) must be fixed in the layer that owns the artifact (`normalize.py` W0, `sections/annotators/text.py`, `sections/taxonomy.py`, `sections/core.py`) — not by switching extraction tools.  See [LESSONS.md L-001](./LESSONS.md#l-001--never-swap-the-pdf-text-extraction-tool-as-a-fix-for-downstream-problems) for the full incident record.
- **NEVER use pdftotext with `-layout` flag** — causes column interleaving. See `docpluck/extract.py:13–16` and [LESSONS.md L-002](./LESSONS.md#l-002--never-use-pdftotext--layout-flag).
- **NEVER use `pymupdf4llm`, PyMuPDF (`fitz`), or `column_boxes()`** — AGPL license, incompatible with the authenticated SaaS service.  pdfplumber (MIT) is the only allowed PDF library alongside pdftotext.  See [LESSONS.md L-003](./LESSONS.md#l-003--never-use-pymupdf4llm-pymupdf-fitz-column_boxes-or-other-agpl-licensed-pdf-tools).
- **ALWAYS normalize Unicode MINUS SIGN (U+2212) → ASCII hyphen** — breaks statistical pattern matching otherwise. (`normalize.py` step S5.)  See [LESSONS.md L-004](./LESSONS.md#l-004--always-normalize-unicode-minus-sign-u2212--ascii-hyphen).
- **Test on APA psychology / replication papers, not ML / engineering papers** — performance-metric tables look like statistical results and mask real failures.  See [LESSONS.md L-005](./LESSONS.md#l-005--test-on-apa--replication-report-papers-not-ml--engineering-papers).
- **FIX EVERY BUG FOUND IN THE SAME RUN — NEVER DEFER "PRE-EXISTING" DEFECTS.** When AI verify, /docpluck-qa, /docpluck-review, or any verification surface a defect during a cycle, fix it in the same run. "Pre-existing, not introduced this cycle" is NOT a license to ship around it — it's a signal that an earlier verification missed a real defect that has been silently corrupting outputs in the interim. Group defects by root cause (one cycle per root cause). Queue subsequent cycles immediately in the same run; don't terminate with the backlog non-empty. Established by user directive 2026-05-14 after the v2.4.16 cycle uncovered ~8 pre-existing defects via Phase 5d. See memory `feedback_fix_every_bug_found` and `.claude/skills/docpluck-iterate/SKILL.md` rule 0e.
  - **NEVER report a cycle or run as "clean", "shippable", "PASS", or done while known FAIL verdicts in the corpus remain unfixed.** A verification pass that surfaces N FAILs means there are N sets of defects to fix — full stop. The word "pre-existing" must never appear as a reassurance or as a reason to downgrade a verdict. Shipping an incremental per-cycle fix is correct and expected; *declaring victory while the corpus is broken is not*. If a verification sweep returns 13 FAILs, the run's standing verdict is FAIL and the run continues — fixing every one — until the corpus is clean, or the budget is exhausted and you report an honest PARTIAL with the exact remaining punch-list. There is no "issue we don't fix." If there are issues, you fix them. Always. Re-emphasized by user directive 2026-05-15 after a cycle-1 report framed "13 papers FAIL" as "cycle 1 is clean and shippable."
- **GROUND TRUTH FOR ALL VERIFICATION IS AN AI MULTIMODAL READ OF THE SOURCE PDF — NEVER pdftotext, Camelot, pdfplumber, or any deterministic extractor.** Every deterministic extractor we use has flaws we have already flagged (pdftotext drops Greek glyphs on tight-kerned PDFs and doesn't see tables/images; Camelot phantom-emits empty columns; pdfplumber `extract_words` is unreliable on tight-kerned PDFs). Comparing the library's rendered .md against pdftotext output can mask any bug that pdftotext itself produces — the very class of bugs the library exists to fix. The canonical Phase 5d / AI-verify / corpus-audit procedure: (1) an AI subagent reads the source PDF directly via the `Read` tool with `pages=N-M` (chunk into ≤20-page slices if needed), (2) the subagent produces a structured `tmp/<paper>_gold.md` capturing every section's body prose, every table cell-by-cell as visually rendered, every figure caption + description, every reference, every footnote, every appendix, (3) the gold extraction is saved and reused across cycles (PDFs are immutable), (4) a verification subagent compares the library's rendered .md against the AI gold (not against pdftotext). Pdftotext / Camelot output remain useful as DIAGNOSTIC artifacts to identify which layer of the library is at fault — but the verdict (PASS / FAIL) is judged against AI gold ONLY. Established by user directive 2026-05-14 after the cycle-15 audit run used pdftotext as truth and the user pointed out this had been clarified "many times" before. See memory `feedback_ground_truth_is_ai_not_pdftotext`, `.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md`, and `.claude/skills/docpluck-qa/SKILL.md` check 7g.

## Architecture: text channel vs layout channel

| Need | Channel | Module |
|------|---------|--------|
| Reading-order linear text | `extract_pdf` (pdftotext default) | `docpluck/extract.py` |
| Per-character font / position / page geometry | `extract_pdf_layout` (pdfplumber) | `docpluck/extract_layout.py` |
| Tables (cell bboxes, columns) | `extract_pdf_layout` only | `docpluck/tables/` |
| Figures (image bboxes) | `extract_pdf_layout` only | `docpluck/figures/` |
| Sections, normalize, batch | `extract_pdf` only | `docpluck/sections/`, `normalize.py`, `batch.py` |
| F0 layout-aware running-header / footnote strip | text from `extract_pdf` + layout from `extract_pdf_layout` | `normalize.py::_f0_strip_running_and_footnotes` |
| Combined output (text + tables + figures) | both, as separate channels | `docpluck/extract_structured.py` |

`extract_structured.py` is the canonical example of using both channels correctly without mixing them.

**On using pdfplumber as reference material:**  pdfplumber's source is open (MIT).  When docpluck needs better column / reading-order handling than pdftotext provides, the strategy is to **study pdfplumber's algorithm** (`pdfplumber/page.py`) and re-implement the relevant logic in docpluck — applied as a *conditional fallback* (e.g. when default pdftotext output looks broken on a paper) rather than as a default replacement.  Credit pdfplumber in code comments and `docs/DESIGN.md` when its algorithms are ported.

## Project skills (in `.claude/skills/docpluck-*`)

These four skills span BOTH repos via absolute paths. Keep paths in sync if either repo moves.

| Skill | Purpose | Targets |
|-------|---------|---------|
| `docpluck-qa` | Full QA suite | Library tests + service tests + ESCIcheck PDFs + production endpoints |
| `docpluck-review` | Code review against hard rules | Both repos' source files |
| `docpluck-cleanup` | Doc / dead-code / config sync | Both repos' docs |
| `docpluck-deploy` | Pre-flight + deploy + verify | Library tag → app requirements bump → Vercel/Railway |

## Key project docs (in `docs/`)

- `docs/README.md` — public-facing library README (renders on GitHub + PyPI).
- `docs/BENCHMARKS.md` — extraction-quality benchmarks across 50 PDFs.
- `docs/NORMALIZATION.md` — pipeline step-by-step reference.
- `docs/DESIGN.md` — architecture decisions.
- `docs/superpowers/specs/` — design docs for individual features (e.g. Request 9 reference normalization).
