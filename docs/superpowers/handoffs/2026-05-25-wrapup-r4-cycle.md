# Wrapup — R4 / v2.4.73-v2.4.76 session (2026-05-25) — ✅ RESOLVED in same-day combined v2.4.76 commit

> **Status (added at commit time):** All "What was NOT done" + "Known residuals" addressable items closed in the same-day combined v2.4.76 release. See CHANGELOG.md [2.4.76] for the merged Stream A + Stream B + extract_columns gate fix entry. R5 Path 1 (architectural multi-day) and R4 cosmetic follow-ups remain deferred to v2.4.77+ as planned. Article-finder skill issues (Tasks #8, #9) belong to a separate skill, untouched.
>
> Specifically closed during the wrapup:
> - Full pytest run: 1573 passed (incl. 19 EC-T1 + 8 EC-T3 + 3 R4 cases), corpus baseline clean.
> - `extract_columns.py::_detect_2col_midline`: real single-column false-detect bug (alternating-zeros histogram misread as gutter) — fixed with contiguous-run-≥2 gate + surrounding-density gate + neighbor-peak gate. Preserves R4 firing on jama_open_1 page 1 (3-bucket contiguous run). Resolves `test_amle_1_table_captions_not_cell_garbage` cascade.
> - `tests/test_extract_columns.py::FakePage` schema mismatch (missing `height`, `words` fields the v2.4.76 R4 rewrite now reads) — fixed.
> - `tmp_verify_corpus_worktree.py` stale diagnostic — removed; `tmp_*.py` and `verify_*.log` patterns added to `.gitignore`.
> - Combined v2.4.76 commit shape (handoff option **a**): single commit covering both work streams + the gate fix discovered during wrapup.

---

# Wrapup — R4 / v2.4.73-v2.4.76 session (2026-05-25)

**Session arc:** v2.4.73 ship → v2.4.74 ship → v2.4.76 work uncommitted (R4 + jama-open-1 D4 + external EC-T1/A4 streams merged in working tree). Two prod-verified deployments behind us; v2.4.76 mid-commit pending pytest confirmation.

**Repo state at handoff:** `main @ 380647a` (v2.4.74 tagged + prod-verified). Working tree dirty — see "v2.4.76 uncommitted" below.

---

## What shipped

### v2.4.73 (commit `3d30009`, tag pushed, prod-verified)
- **R1-repair**: woke up the dead `whitespace_cells` wiring. The v2.4.72 §A R1 fix was structurally dead — `_region_for_caption` returned None in 100% of B1 unmatched-caption cases because `_bbox_of_caption_line` matched first-20-char prefix against joined layout chars that drop inter-word whitespace and keep raw PDF ligatures. Fix: three-pass matcher in `docpluck/tables/detect.py` (exact prefix → normalized prefix with ligature-fold + whitespace-strip → label-only fallback). Region resolution went **0/22 → 22/22**; whitespace_cells now yields 72 cells on chan_feldman, 100 cells on maier.
- **New regression test:** `tests/test_r1_whitespace_cells_wiring_real_pdf.py` (3 cases — 2 real-PDF + 1 unit ligature/whitespace normalization).
- **Full pytest:** 1514 passed, 27 skipped, 1 xfailed.
- **Prod verified:** `curl https://extraction-service-production-d0e5.up.railway.app/_diag` → `docpluck_version: "2.4.73"`.

### v2.4.74 (commit `380647a`, tag pushed, prod-verified)
- **jama-open-1 defect cluster — 4 of 5 closed** (from `HANDOFF_2026-05-25_pretest-followups.md` Issue 1):
  - **D1 RUNNING_HEADER_LEAK** (`normalize.py`): JAMA-style `Downloaded from <bare-domain> … user on MM/DD/YYYY` watermark pattern + bare standalone `Month DD, YYYY` page-footer pattern. Cleared 13 download leaks + 15 date leaks.
  - **D2 HALLUC_HEAD** (`render.py _demote_isolated_table_cell_headings`): demote `### {label}` stranded inside table-cell clusters via bidirectional cell-fragment / column-header-stranded / data-shape signatures. Strict `_looks_like_real_sentence` gate prevents table-footer prose from blocking. Cleared all 4 surfaced cases.
  - **D3 ABSTRACT_LEVEL_MISMATCH** (`render.py _demote_abstract_zone_inline_labels`): zone-bounded demoter between `## Abstract` and next body-section h2 (80-line hard cap), using explicit `_STRUCTURED_ABSTRACT_INLINE_LABELS` allowlist. Two regressions surfaced + fixed during dev (over-demoted `## THEORETICAL DEVELOPMENT` then `## III. RESULTS`).
  - **D5 TABLE_STRUCTURE_CORRUPT** (`render.py _strip_phantom_camelot_tables`): strip Camelot `<table>` blocks with masthead-shaped `<th>` + ≤1 non-empty body cell OR section-name leak.
  - **D4 MISSING_SECTION** (Key Points sidebar) deferred — column-interleave problem, addressed by R4 in v2.4.76 below.
- **R1-perf threading**: `_layout_doc` kwarg on `extract_pdf_structured`; `render_pdf_to_markdown` pre-extracts once at step 0 and passes through. Eliminates 2x `extract_pdf_layout(pdf_bytes)` call flagged by v2.4.73 R1 AI-gold sweep.
- **R3b widening**: `_suppress_inline_duplicate_figure_captions` allows up to 250-char overhang when caption-continuation shape (lowercase start / `(A) (B)` panel labels), no stat shape, no body-prose starter (`We `/`In `/etc.), sentence-terminated.
- **R4 scaffold**: new `docpluck/extract_columns.py` (extract_page_text_columns / splice_column_corrected_pages / `_detect_2col_midline`). Wired into pipeline in v2.4.76.
- **NORMALIZATION_VERSION** 1.9.23 → 1.9.24.
- **New tests:** 5 jama-open-1 real-PDF cases + 5 extract_columns unit cases.
- **Full pytest:** 1527 passed, 27 skipped, 1 xfailed.
- **Prod verified:** `docpluck_version: "2.4.74"` live on Railway.

---

## v2.4.76 — UNCOMMITTED (two concurrent feature streams in working tree)

External tooling bumped `__init__.py` + `pyproject.toml` to **v2.4.76** mid-session. The working tree contains TWO parallel work streams:

### Stream A — my work (R4 column-aware re-extraction + jama-open-1 D4 closure)

- **Detector (`docpluck/normalize.py::_detect_column_interleave_pages`):** added Signature B (bimodal-line-length): substantial-content page (≥30 body lines) where ≥30% short (<40 chars) AND ≥30% long (>70 chars) is column-fragmented. Catches JAMA Open's abstract+sidebar interleave that escaped the original Signature A (period-terminated structured-abstract labels masked the flips).
- **Column extractor (`docpluck/extract_columns.py`):** `_crop_and_extract` runs pdftotext twice per flagged page with `-x -y -W -H` flags (one crop per column) — preserves pdftotext's gap-aware word-spacing that pdfplumber's `extract_text()` loses on tight-kerned PDFs. Fallback chain: pdftotext-crop → pdfplumber word-join → original text.
- **Wiring (`docpluck/extract.py::extract_pdf`):** R4 runs at the text-channel layer (after pdftotext, before return) so sections / normalize / render / structured ALL see the corrected text. Method tag gains `+column_corrected:N,M,...` suffix when R4 fires.
- **jama-open-1 D4 outcome:** Key Points sidebar (`Question / Findings / Meaning`) now appears as a coherent block. Abstract content flows in proper paragraph order. **All 5 of 5 jama-open-1 defects now closed.**
- **R4 firing observations:**
  - jama_open_1: pages 1, 3, 5, 6, 10, 11 ✓
  - chandrashekar_2023_mp: pages 1, 3, 5, 6, 7, 8, 9, 10, 14, 15, 16, 17, 19, 22, 26, 29, 31, 33, 39, 40, 41, 42, 44, 46 (aggressive — 24 pages)
  - ip_feldman_2025_pspb: 14 pages
  - plos_med_1: 8 pages
  - maier_2023_collabra: 10 pages
  - chan_feldman_2025_cogemo: not flagged
  - xiao_2021_crsp, efendic_2022_affect, jdm_.2023.16: not flagged
- **R4 regression test:** `tests/test_r4_column_correction_real_pdf.py` (3 cases — fires-on-jama / abstract-not-interleaved / key-points-present). **3/3 PASS standalone.**

### Stream B — external session work (EC-T1 + A4)

NOT my work, but in the working tree. Confirmed via CHANGELOG entries:

- **EC-T1**: new `docpluck/tables/flatten.py` — `flatten_table(table) → list[FlattenedRow]` for downstream stat-verification consumers (effectcheck, escimate, scimeto). 19 new tests in `tests/test_tables_flatten.py`. New top-level exports: `FlattenedRow`, `flatten_table`, `flatten_tables_for_paper`, `render_flattened_inline`. CLI gains `--tables-jsonl PATH` and `--flatten-tables-inline`. `TABLE_EXTRACTION_VERSION` 2.1.5 → 2.2.0. Sources: ESCIcheck handoffs 2026-05-24 and 2026-05-25.
- **A4 CI delimiter** (`tests/test_a4_ci_period_to_comma.py`): regression test for `[d.d.d.d]` → `[d.d, d.d]` rewrite. ESCIcheck handoff 2026-05-24 D2.

### Files modified / created (uncommitted)

```
 M CHANGELOG.md                              (combined v2.4.76 entries — both streams)
 M docpluck/__init__.py                      (version 2.4.74 → 2.4.76 + flatten exports)
 M docpluck/cli.py                           (--tables-jsonl + --flatten-tables-inline)
 M docpluck/extract.py                       (Stream A: R4 wiring)
 M docpluck/extract_columns.py               (Stream A: pdftotext-crop fallback)
 M docpluck/extract_structured.py            (Stream A: R1-perf carry-over)
 M docpluck/normalize.py                     (Stream A: bimodal Sig B / 1.9.24→1.9.25
                                              + Stream B: A4 CI delimiter)
 M docpluck/render.py                        (Stream A: D1/D2/D3/D5 demoters + R3b widen)
 M docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md
 M pyproject.toml                            (version 2.4.74 → 2.4.76)
?? docpluck/tables/flatten.py                (Stream B)
?? tests/test_a4_ci_period_to_comma.py       (Stream B)
?? tests/test_r4_column_correction_real_pdf.py (Stream A)
?? tests/test_tables_flatten.py              (Stream B)
?? tmp_verify_corpus_worktree.py             (stale diagnostic — gitignore candidate)
```

### Full pytest status (v2.4.76 working tree)

- **Started** ~17:20 with combined Stream A + Stream B changes.
- **Status at handoff**: hanging at 0 bytes output (same Windows `python -u | tail` buffering issue that delayed pytest output throughout this session — earlier runs eventually flushed and showed 1514 / 1527 passing).
- **Targeted-test signal**: 3/3 R4 tests pass. 5/5 jama-open-1 cluster tests pass. 5/5 extract_columns unit tests pass. EC-T1 author's CHANGELOG claims 19/19 flatten tests pass.

---

## Known residuals (for v2.4.77+ follow-up)

### R4 column-boundary cosmetic artifacts

The R4 column-crop is geometric — pdftotext runs on a fixed-x bounding box. This produces:
1. **Title truncation** on titles that span both columns (`Effect of Time-Restricted Eating on Weight Loss in Adu` cut at midline).
2. **Multi-word label splits**: `CONCLUSIONS AND RELEVANCE` at column boundary becomes `**CONCLUSIONS**` heading + `AND RELEVANCE` orphan line. (The D3 demoter only catches the first half — `CONCLUSIONS` is in its allowlist; `AND RELEVANCE` falls through as body prose.)
3. **Orphan fragments** from `(continued)` page markers split as `(contin` / `ued)`.

**Pragmatic interim**: structural defect (sidebar missing / abstract interleaved) is closed; cosmetic fragmentation remains. Full fix needs column-element detection (page-spanning banners get rendered FROM the original pdftotext output not the crops).

### R4 aggressive flagging on chandrashekar (24 pages) and ip_feldman (14 pages)

Both have substantial bimodal-line-length signatures. Per-page safe-fallback should prevent regression (column extractor returns empty for non-2-col pages → original text stays), but a corpus-wide check is needed before declaring R4 fully safe across the 50-PDF baseline.

### R5 — layout-channel per-char glyph identity recovery (bare table-cell betas)

Architectural multi-day work, not started this session. Existing `_recover_dropped_minus_in_record` (CI-paired form) shipped v2.4.72; bare-cell case (ar_apa_j_jesp_2009_12_011, 4 beta sign inversions in tables without adjacent CIs) needs per-char layout inspection infrastructure that doesn't exist yet. Per 2026-05-22 R5 decision table, this is Path 1 (recommended option). Multi-day work.

### Article-finder skill issues (not docpluck territory)

Both surfaced earlier this session:

- **Task #8** — `ai-gold.py resolve` should accept stem names + source-PDF paths (or docs should redirect to `check` directly). Per `HANDOFF_2026-05-25_pretest-followups.md` Issue 2.
- **Task #9** — `ai-gold.py onboard` needs `--skip-legacy` / `--ignore-unresolvable` flag. The `citationguard` onboard HALTED on 3,018 legacy bare-stem gold keys (`migrated=0 skipped=0 halted=3018`); the pipeline treats every unresolvable entry as a halt rather than auto-skipping pre-canonical-rollout legacy keys. Report at `ArticleRepository/onboarding_reports/2026-05-25_citationguard.md`.

---

## What was NOT done

1. **v2.4.76 not committed / tagged / pushed.** Working tree is dirty with both Stream A + Stream B. The next session owner should decide commit shape:
   - (a) Single combined v2.4.76 commit (CHANGELOG already merged — easiest).
   - (b) Stash R4, ship EC-T1 alone as v2.4.76, bump my work to v2.4.77 (cleaner history).
   - (c) Leave working tree dirty for the next session to decide.
2. **Full pytest verification** at v2.4.76 state — still hanging on Windows pipe buffer at handoff time. Will need to either wait for completion or kill and re-run synchronously.
3. **R5 Path 1** — multi-day architectural item, deferred to a dedicated session.
4. **R4 cosmetic follow-ups** (title-truncation, multi-word-label splits) — punch-list item for v2.4.77.
5. **Corpus baseline at v2.4.76** (`scripts/verify_corpus.py`) — not run with R4 active. Should run before v2.4.76 ships to confirm the aggressive R4 flagging on chandrashekar / ip_feldman / plos_med_1 / maier doesn't regress those papers.

---

## Suggested next-session workflow

1. **Decide v2.4.76 commit shape** (a / b / c above).
2. **Wait for pytest** OR kill + re-run synchronously.
3. **Run `scripts/verify_corpus.py`** to confirm R4 doesn't regress the 26-paper baseline.
4. **If clean**: stage + commit + tag v2.4.76 + push + verify Railway redeploy.
5. **Open tasks for next cycles** — R4 cosmetic residuals (v2.4.77), R5 architectural (dedicated session), article-finder skill fixes (separate skill).

---

## Tasks state at handoff

| ID | Status | Item |
|---|---|---|
| #1 | ✅ completed | R1 AI-gold sweep for 11 B1 papers |
| #2 | 🟡 in_progress | R4 column-aware re-extraction (Path 1) — Stream A above, ready to commit pending pytest |
| #3 | ⏸ pending | R5 layout-channel bare-cell minus recovery (Path 1) — architectural multi-day |
| #4 | ✅ completed | R3b block-caption-completion + widen suppressor (widening shipped v2.4.74; completion deferred) |
| #5 | ✅ completed | Ship v2.4.73 |
| #6 | ✅ completed | R1-repair |
| #7 | ✅ completed | jama-open-1 defect cluster (D1/D2/D3/D5 v2.4.74; D4 v2.4.76 once committed) |
| #8 | ⏸ pending | article-finder ai-gold.py resolve UX (article-finder skill territory) |
| #9 | ⏸ pending | article-finder citationguard onboard --skip-legacy flag (article-finder skill territory) |
| #10 | ✅ completed | R1 perf: thread layout_doc through extract_pdf_structured |

---

## Cross-references

- v2.4.72 bundled cycle CLOSED: [`2026-05-23-bundled-residual-cycle-CLOSED.md`](2026-05-23-bundled-residual-cycle-CLOSED.md)
- v2.4.73 commit `3d30009`: dead whitespace_cells wiring repair
- v2.4.74 commit `380647a`: jama-open-1 4/5 + R1-perf + R3b widen + R4 scaffold
- Pretest follow-ups handoff (source of jama-open-1 cluster): [`HANDOFF_2026-05-25_pretest-followups.md`](../HANDOFF_2026-05-25_pretest-followups.md)
- 2026-05-22 residual decision tables: [`2026-05-22-residual-after-locally-doable-pass.md`](2026-05-22-residual-after-locally-doable-pass.md)
- Memory: `feedback_fix_every_bug_found` — bound this session ("address all the issues that come up, leave nothing behind").
