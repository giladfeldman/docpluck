# HANDOFF 2026-06-08 — untested-manuscript sweep · v2.4.80 → v2.4.81 (RC-2 strip-fixes) + RC-1 started

## 1. State at handoff
- **Library version in working tree:** `2.4.81` (`__version__`, `pyproject.toml`, `NORMALIZATION_VERSION` 1.9.29). **UNCOMMITTED** — changes staged in the working tree, NOT committed/tagged/deployed (held for user go-ahead; run is PARTIAL while RC-1 open).
- **App pin / prod:** unchanged (still on 2.4.80). No deploy this run.
- **Run mode:** discovery sweep on previously-untested manuscripts (focus APA + other formats), article-finder for all article location + ground truth (I9/I18).

## 2. What shipped (working tree, uncommitted)
**v2.4.81 — RC-2 metadata/running-header leak strips** (one root cause: non-body furniture leaking into body). Files: `docpluck/normalize.py`, `docpluck/__init__.py`, `pyproject.toml`, `CHANGELOG.md`, `tests/test_p0r_recurring_running_header_strip.py`, `tests/test_normalize_metadata_leak_real_pdf.py`.
- **Running-header shapes** added to P0r `_looks_like_running_header_or_footer`: Elsevier `<Journal> <Vol> (<Year>) <ArtNo>` (`_ELSEVIER_JOURNAL_VOL_FOOTER`) + Nature `<Journal> | (<Year>)<Vol>:<ArtNo>` (`_JOURNAL_PIPE_ISSUE_FOOTER`). Leaked on 5/5 swept papers; ≥3×-repetition-guarded.
- **Corresponding-author footnote** (`_PAGE_FOOTER_LINE_PATTERNS`): lowercase `a Corresponding author:` + `Shared/Joint first author` openers (v2.4.6 pattern only matched capital-A).

**Verification:** 316 relevant tests pass, 0 fail — cycle1 P0r suite (45), cycle2 metadata-leak suite (36), focused normalize/footer blast-radius subset (235 incl. existing ar_apa/chen Elsevier-footer tests). Baseline: chen_2021_jesp (Elsevier family) + chandrashekar PASS. Real-PDF regressions on j.jesp.2021.104154, s41467, collabra.37122. **NOT verified:** full ~1900-test suite + 26-paper verify_corpus (both suspended ~14 min in by the machine bg-task limit) — but the change is normalize-text-only, so the unrun Camelot/table tests are outside its blast radius.

## 3. Discovery-sweep findings (full triage: `docs/TRIAGE_2026-06-08_untested_corpus_sweep.md`)
5 papers AI-verified (SHA-integrity-gated), all FAIL:
- collabra.37122, collabra.77859, j.jesp.2021.104154 (APA) · pci.rr.100726, s41467-023-42320-4 (other format).
- **RC-1 (dominant, ARCHITECTURAL):** two-column reading-order interleave — section-order scrambling, wrong-column tables, paragraph splits. Broad (every 2-col APA paper). User greenlit STARTING.
- **RC-2 (FIXED this run):** running-header + corresponding-author leaks.
- Other open: CC-BY license boilerplate (collabra.77859); `M_age 59.3→39.3` glyph/interleave (collabra.77859 — needs PDF diagnosis); `## Supplementary` hallucinated heading (s41467); Nature figure-panel text injection (s41467); Nature run-in `###` subheadings not promoted (s41467).
- Non-defects (gold-formatting philosophy, NOT actioned): markdown-italic stats, blockquotes, reply-headings, em-dash→`--`.

## 4. RC-1 — column architecture (STARTED; the next big work)
Design + precise gap analysis: `docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md`. Key insight: **the machinery already exists** — `_detect_column_interleave_pages` (detection) + `extract_columns.py::splice_column_corrected_pages` (correction, word-preservation-guarded) — but detection is **signal-only** (normalize.py:3813 records `column_interleave_pages`, never wires it to the splice; only the O5 inversion path splices).
- **Step 1 (safe, flag-gated, next session):** wire `column_interleave_pages` → `splice_column_corrected_pages` with `word_preserve_pages=ALL` + `allow_gutter_fallback`, behind a feature flag (default off = byte-identical). Corrects clean 2-col body pages; the bilateral gate still SKIPs table-bearing pages (no regression). Validate by re-render + AI-verify the 4 papers + 26-baseline.
- **Step 2 (harder):** per-y-band region-aware correction (segregate full-width table bands from 2-col prose bands) — closes the canary ip_feldman B4/R4.

## 5. Open queue (immediate next steps, same run / next session)
1. **RC-1 Step 1** (flag-gated general-interleave wiring) — highest impact.
2. **RC-2 residuals:** CC-BY license boilerplate strip; `## Supplementary Fig.` heading-promoter guard; Nature run-in subheading promotion.
3. **M_age 59.3→39.3 diagnosis** (potential silent stat corruption — confirm direction vs PDF).
4. **Re-verify the 7 SHA-mismatch APA papers** by regenerating golds from cached PDFs via `article-finder generate-gold` (collabra.23443/.32572/.57785, j.jesp.2020.104052, j.jesp.2022.104372, SPPS inaction-inertia 1948550619900570, rsos.250908).
5. **Article-finder provenance gap** (one DOI → two PDF copies) — raise with AF owner.
6. **Full pytest + 26-baseline / harness Tier-D** — run via a mechanism that survives the bg-task suspension (foreground chunks, or scheduled overnight).
7. **Commit/tag/deploy v2.4.81** once the user approves + the run reaches a clean-enough bar.

## 6. Stop reason
Session length + machine bg-task suspension (full-suite/baseline kept getting cut ~14 min in). Strip-fix cycles are complete + verified (blast-radius gate green); RC-1 is genuinely multi-session (designed + scoped, implementation queued). Run standing verdict: **PARTIAL** (RC-2 fixed; RC-1 + residuals open — per rule 0e-bis, not "clean").
