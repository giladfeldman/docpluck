# Docpluck — Roadmap / Deferred Work

This file tracks future-aim items that are scoped out of the current milestone but should not be lost. See `docs/superpowers/specs/` for active specs.

## Tables — formal evaluation corpus (deferred to v2.1)

v2.0 ships with smoke tests only (`tests/fixtures/tables/`, ~10-15 hand-picked PDFs with per-PDF assertions on table count, row/col counts, specific cell values). No formal accuracy numbers.

v2.1 (or a dedicated eval milestone) should add:

- **30-40 hand-labeled APA-psych PDFs** with HTML ground truth for every table (and figure caption + bbox where checkable).
- Scoring with **TEDS** (Tree-Edit-Distance Similarity, ICDAR 2021) + **cell-exact-match rate** + **table-detection precision/recall**.
- Numbers added to `BENCHMARKS.md` alongside existing engine-comparison results.
- A separate Elsevier/Springer/Nature/IEEE slice (~10 PDFs) so we can also report on lattice (full-grid) tables, not just APA lineless.

This is the foundation for the level-C work below — without numbers we can't tell if a "best-in-class" claim is true. Best done after v2.0 ships, because real edge cases will surface in production use and inform what's worth labeling carefully.

## Tables — future "level C" aims (deferred from v2.0)

The current table-extraction milestone (see `docs/superpowers/specs/2026-05-06-table-extraction-design.md`) targets level **B**: detect every table, emit structured cells when there are ruling lines or clean column-gap whitespace, isolate (raw text + bbox) otherwise.

Deferred to a later release ("level C — best-in-class APA-psych structured extraction"):

- **Multi-row header recovery** with colspan/rowspan inference (e.g., "Pretest" / "Posttest" headers spanning 2-3 columns each, with "M (SD)" sub-headers below).
- **Correlation-matrix awareness** — recognize lower-triangular layout, handle diagonal blanks / "—" / "1.00", emit a `matrix: true` flag with row/col labels.
- **Footnote-marker linking** — attach `*`, `**`, `***`, `†`, `‡`, superscript-letter markers as cell metadata linked to a parsed footnote dictionary (`*p < .05` etc.), instead of dropping or concatenating into the number.
- **Multi-page table stitching** — detect "Table N (continued)" / repeated header rows on the next page, stitch into a single logical table.
- **Two-column-span table detection** in two-column papers — detect tables that span the full printable width before column-aware reading-order is applied.
- **Landscape (rotated 90°) table support** — read PDF page rotation + `LTChar` matrix orientation, rotate coordinates before clustering.
- **Build a 50-PDF APA-psych eval set** with hand-labeled HTML ground truth, scored with TEDS (Tree-Edit-Distance Similarity, ICDAR 2021) + cell-exact-match. Target: TEDS > 0.80 on the APA-psych slice.

These are real engineering items, not nice-to-haves — they're what would let docpluck claim best-in-class status against GROBID/Camelot/Docling on the APA-psych corpus specifically. Out of scope for v2.0 to keep the first release shippable.

## Figures — future "level C" aims (deferred from v2.0)

The current milestone targets figure level **A**: detect figure regions, emit `figures: [{page, bbox, label, caption}]`, strip/placeholder the figure region from the linear `text` output. No image extraction, no figure-content understanding.

Deferred to a later release if it proves valuable and doable:

- **Figure image extraction** — pull the actual figure rendering (vector graphics or rasterized image) and emit it as a separate asset (PNG/SVG path) alongside the metadata.
- **Axis-label / legend OCR** — for raster figures, OCR the in-figure text so downstream tools can search for variable names appearing only in figures.
- **In-text figure reference resolution** — link "(see Figure 3)" mentions in the prose back to the corresponding figure object.
- **Figure-type classification** — distinguish bar plot / scatter plot / forest plot / flowchart / schematic / photograph (useful for meta-analysis tooling that wants forest plots).
- **Subfigure detection** — handle "Figure 2a / 2b / 2c" panel layouts as a parent figure with child panels.

Worth revisiting once the table track is shipped and we know which figure-side capabilities downstream tools (ESCIcheck, MetaESCI, Scimeto) actually need.

## Section identification — future enhancements (deferred from v1.6.0)

The v1.6.0 milestone (`docs/superpowers/specs/2026-05-06-section-identification-design.md`) ships a flat sectioner with 18 canonical labels + `unknown` fallback, hardcoded taxonomy, and merged `title_block`. Deferred:

- **Hierarchical / tree section output.** Currently flat with numeric suffixes (`methods_2`). Add a tree mode (`Body → Study 1 → Methods/Results`, `Body → Study 2 → Methods/Results`) when a real consumer needs it. (Q2 option C from the brainstorm.)
- **Split `title_block` into `title` / `authors` / `affiliations`.** Currently merged because affiliation parsing is its own hard problem; consumers needing structured author metadata should use CrossRef/DOI lookup. Worth doing once we have a use case that can't be served by external APIs.
- **Custom heading-map / user-supplied taxonomy extension API.** Hardcoded taxonomy in v1; revisit after we collect real-world misses on Hebrew / non-English / domain-specific journals.
- **Validate the conflict-resolution rule** (text-pattern wins for canonical headings, layout wins for unknown headings — Q4.vi from the brainstorm). Test against the v1 corpus once MVP ships and adjust if there's a class of papers the rule fails on.
- **Public `extract_pdf_layout()` API.** Internal-only in v1.6.0. Promote to public API once the `LayoutDoc` shape stabilizes and an external consumer asks for it.
- **Section-aware quality scoring** in `quality.py` (e.g., flag a low-confidence `references` section that may need re-extraction).
- **Confidence calibration.** Current `high`/`medium`/`low` is heuristic. Real numeric calibration needs the v1 test corpus + manual gold labels.

## Table/figure text-mode — future configuration enhancements (deferred from v2.0)

The current milestone ships with two `text` modes for `extract_pdf_structured()`:
- `"raw"` (default) — flowing text including table contents, identical to `extract_pdf()` behavior. Backwards-compatible.
- `"placeholder"` — table/figure regions replaced with `[Table N: caption]` / `[Figure N: caption]` markers.

Deferred richer modes to consider once the two-mode default is in production and we have feedback:

- **`"strip"`** — remove the region entirely with no marker (cleanest for some consumers, but loses positional cue).
- **`"inline_markdown"`** — render structured tables as markdown pipe-tables inline in `text` (LLM-friendly; lossy on multi-row headers; reintroduces stat-regex false positives — careful).
- **`"inline_html"`** — same idea but HTML tables inline (preserves more structure than markdown).
- **Per-table-type override** — different mode for tables vs. figures, e.g. raw for tables, strip for figures.
- **Confidence-gated mode** — placeholder only when structured extraction confidence is high; raw fallback otherwise.
- **Custom placeholder template** — caller supplies `f"[{label}: {caption}]"` or similar.

Add only when a real downstream consumer asks for one. YAGNI until then.

---

## 2026-05-25 wrapup punch-list — canary-audit + Cluster A/B/C + leftover v2.4.76

> **Source:** Two-session wrapup combining R4 cycle work (uncommitted v2.4.76 from earlier today) and the canary-audit architecture session. See `docs/superpowers/handoffs/2026-05-25-canary-audit-architecture-and-cluster-A-B-C-landed.md` and `docs/superpowers/handoffs/2026-05-25-wrapup-r4-cycle.md` for full details. The 11th defect (`test_plos_med_1_no_fence_footer`) was fixed in the wrapup itself before commits.

### Must do before v2.4.77 tag

- [ ] **Run full pytest** to confirm combined v2.4.76 (R4 + EC-T1 + A4) + canary-audit (Cluster A/B/C/D-partial + PSPB-style heading + plos_med_1 P0r fix) state is clean. Estimated 24 min.
- [ ] **Run `scripts/verify_corpus.py`** — R4 fires aggressively on chandrashekar_2023 (24 pages) and ip_feldman (14 pages). Confirm no regression vs the 26-paper baseline before tagging.
- [ ] **Commit shape** (per 2026-05-25 wrapup decision): single combined v2.4.76 commit for R4 + EC-T1 + A4 + jama-open-1 D4 + plos_med_1 P0r fix, then separate `feat(canary-audit)` commit on top for Cluster A/B/C + audit infrastructure.

### Canary-audit infrastructure — operational

- [ ] **`claude setup-token`** — user runs this once in a regular terminal (interactive browser auth) so headless `claude -p --model sonnet` works from git hooks / scheduled tasks. Required before Phase 1 of canary-audit deploy.
- [ ] **Wire git hooks** in `.git/hooks/`: pre-commit (quick canary on `docpluck/*.py` changes), pre-push (full canary on push to main), pre-tag (full canary, no exceptions). Each shells out to `~/.claude/skills/_shared/iterate-loop/canary-audit.sh`.
- [ ] **Wire scheduled-tasks watchdog** via `mcp__scheduled-tasks__create_scheduled_task` — daily audit of HEAD against canary, PushNotification on FAIL.
- [ ] **Double-audit + finding-union** mode in `canary-audit.sh` — runs Sonnet twice and unions findings (per `feedback_audit_nondeterminism_mitigation.md`). Currently the script runs Sonnet once.
- [ ] **Persistent open-finding ledger** at `.claude/skills/_project/canary-findings-ledger.json` — once a defect is reported at HEAD SHA X, stays open until a later audit confirms clear.

### Remaining ip_feldman_2025_pspb defects (14 in final audit)

- [ ] **Front-matter leak lines 0-16** — article ID, journal banner, society copyright, DOI fragment emitted as body before Abstract. Needs P0 pre-pass for journal masthead block detection.
- [ ] **Affiliation fragment "Fu Lam, Hong Kong SAR." (line 37)** — corresponding-author paragraph wrap-tail. Either pre-join wrapped affiliation paragraphs at P0 level OR add an orphan-wrap-tail pattern.
- [ ] **Missing Method subsections** — `Design and Procedure`, `Power Analysis and Sensitivity Test`, `Measures`, `Data Analysis Strategy` still plain text. Investigate why these specific ones don't promote (others on same paper do).
- [ ] **Missing Discussion subsection** `Challenging and Reframing Misestimation`.
- [ ] **Table 10 phantom-guard** — th_section_leak heuristic didn't fire (cell content has hyphens splitting words like "cau-tion"). Debug + retune word-shape detection.
- [ ] **Data Availability section absent from end-matter** — Cluster A demote-fix may have over-stripped the legitimate `## Data Availability` section that should remain after Author Contributions.
- [ ] **False positive `### Reasons for change` (line 554)** — over-promotion in some context post-Cluster-B; investigate scope.
- [ ] **Table 3 malformed** (cluster D-full Camelot — multi-session)
- [ ] **Table 4 truncated** (Cluster D-full Camelot)
- [ ] **Table 6 split rows** for multi-word items
- [ ] **Table 8 split rows** for variable names
- [ ] **Table 9 caption truncated mid-word** ("Versus" cut off, missing "Replication.")
- [ ] **Table 9 Interpretation column** split across two `<tr>` rows.
- [ ] **Table 10 no body** (caption only).

### Cluster D-full Camelot tuning (deferred to its own session)

- [ ] Stream-flavor column-tolerance tuning (`column_tol`, `row_tol`, `edge_tol` per-page or per-paper).
- [ ] Post-Camelot header-cell splitter for concatenated columns (e.g. "Study 3Replication").
- [ ] Multi-line cell wrap detection for body rows that span two PDF lines.
- [ ] Multi-row header collapse (Table 5 fragmented headers).
- [ ] Full 26-paper corpus regression-test infrastructure (table-specific AI gold view, not just `reading.md`).

### R4 cycle residuals (from `2026-05-25-wrapup-r4-cycle.md`)

- [ ] **R4 title truncation** — `Effect of Time-Restricted Eating on Weight Loss in Adu` cut at column midline.
- [ ] **R4 multi-word-label splits** — `CONCLUSIONS AND RELEVANCE` becomes `**CONCLUSIONS**` heading + `AND RELEVANCE` orphan.
- [ ] **R4 (continued) fragment** — `(continued)` page marker splits as `(contin` / `ued)`.
- [ ] **R5 Path 1** — layout-channel per-char glyph identity recovery (bare table-cell betas, ar_apa_j_jesp_2009_12_011). Architectural multi-day work.

### Article-finder skill issues (separate skill, separate session)

- [ ] **Task #8**: `ai-gold.py resolve` should accept stem names + source-PDF paths (or docs redirect to `check`).
- [ ] **Task #9**: `ai-gold.py onboard` needs `--skip-legacy` / `--ignore-unresolvable` flag (citationguard onboard halted on 3,018 legacy bare-stem keys).

## 2026-06-07 — v2.4.78 landed (committed 73462e3, unpushed→pushed, NOT tagged)

> **Source:** Cycle-4-redux session. See `docs/superpowers/handoffs/2026-06-07-v2.4.78-landed-canary-iterate.md` for the full state + next-session opener. v2.4.78 cleared canary findings #1/#3/#4 + 4 run-11 hallucinated-heading findings + citationguard soft-hyphen Defect 1. Corpus 26/26, full pytest 1861 passed, canary re-audit 8→5.

### Remaining canary findings on ip_feldman_2025_pspb (from 2026-06-07 re-audit @ 73462e3)

- [x] **METADATA-LEAK** — ✅ CLEARED in **v2.4.79** (cycle 5). New `_PAGE_FOOTER_LINE_PATTERNS` entry strips US-format `Received Month DD, YYYY; revision accepted Month DD, YYYY` (date sub-pattern accepts either order; gated on `revision accepted` + trailing year). The handoff-suggested `^Received .*; revision accepted .*$` was tightened to avoid matching body prose. Real-PDF + contract tests added.
- [x] **HALLUCINATION** — ✅ CLEARED in **v2.4.79** (cycle 5). Confirmed **audit false-positive** (the sentence is real — gold line 86); the actual defect was a spurious mid-sentence split + dropped period left by `_demote_continuation_promoted_headings`. The demoter now rejoins the demoted continuation to the prior line it continues + restores the terminal period. Verifier allowed-omissions doc updated so publication-history dates can't churn METADATA-LEAK→TEXT-LOSS.
- [ ] **TABLE #3 + #4 (B4) AND SECTION-BOUNDARY #5 (R4) share ONE root cause** — DIAGNOSED 2026-06-07 (cycle 5), see [`docs/superpowers/specs/2026-06-07-ip_feldman-B4-R4-column-interleave-diagnosis.md`](docs/superpowers/specs/2026-06-07-ip_feldman-B4-R4-column-interleave-diagnosis.md). pdftotext column-interleaves table-bearing two-column pages, interleaving table caption/headers/cells AND real body prose into one stream. **Empirically NOT single-cycle** (corrects optimistic subagent estimates): the existing R4 infra's bilateral gate (protects table pages corpus-wide) rejects the target pages (measured bilateral 0.37–0.44 > 0.30), and the B4 leak can't be stripped render-side because real prose is interwoven with table content (would risk TEXT-LOSS, rule 0a). **Real fix = region-aware column detection** (segregate full-width table band from 2-col prose band before column-correcting) — multi-session architecture, **needs user go-ahead**.

### Deferred from this session (surfaced, not hacked)

- [ ] **`### Reasons for change`** (ip_feldman) — Table 5 column header promoted to heading; needs table-region awareness (the body-coherence guard doesn't catch it because its body starts capitalized). RCA: rank-3 in the 2026-06-06 run-11 RCA.
- [ ] **`## Data Availability` end-matter absent** — RCA CORRECTED the run-11 "demoter over-strip" premise: the section never enters the text channel (pdftotext drops the title-page box). Needs cross-channel (pdfplumber) recovery, same architecture class as B7. NOT a demoter exception.
- [ ] **Glyph `Västfjäll`→`Vastfall`** (ar_apa/collabra, citationguard Defect 2) — baked pdftotext CID-font mis-map; needs a same-document surname-consensus normalizer (new subsystem). **Product/architecture decision on scope.**
- [ ] **org-author `Open Science Collaboration`→`Open, S. C.`** — baked into the PDF's embedded text by the publisher (identical in pdftotext AND pdfplumber); no safe general docpluck fix. **Routed to CitationGuard** (DOI/CrossRef author reconciliation).
- [ ] **Tag v2.4.78** once the full canary set clears (currently 5 open). Then bump `PDFextractor/service/requirements.txt` pin + run `/docpluck-deploy`.

### Substrate / infra follow-ups (2026-06-07)

- [x] **Tune the canary git-hooks to be ledger-aware (regression-only gate).** ✅ DONE (2026-06-07 cycle 5). `canary-audit.sh --gate-new-only` mode had landed but the hooks weren't passing it. Now wired: `.git/hooks/pre-commit` runs `--quick … --gate-new-only` (routine commits block only on NEW/regressed findings, not the deferred baseline); `.git/hooks/pre-push` uses `--gate-new-only` for **main** pushes but keeps the **strict** no-exceptions gate for **tag** pushes (a release tag must ship a fully-clean canary). Substrate self-tests 16/16 pass.
- [ ] **Modern Standby permanent disable** (optional, user/admin): `reg add HKLM\SYSTEM\CurrentControlSet\Control\Power /v PlatformAoAcOverride /t REG_DWORD /d 0 /f` + reboot. Current `powercfg /change standby-timeout-ac 0` works but can revert on power-plan change. See memory `feedback_long_runs_die_on_this_machine`.

### Replicate canary-audit pattern to other iterate skills (after docpluck proven)

- [ ] **escicheck-iterate** — easiest pilot (46 successful phase_5d_runs already, well-defined stats-family defect taxonomy). Update `verification_protocol` in its `canary.json`.
- [ ] **2rmarkdown-iterate** — needs 3-tier verdict-vocabulary (GREEN/YELLOW/RED → PASS/FAIL/FAIL) integration in the orchestrator. Fixture-keyed corpus.
- [ ] **citationguard-iterate** — needs corpus onboarding into article-finder FIRST (`corpus-query --source citationguard` returns 0 currently). Two-view-per-paper (`citations.v2` + `intext_citations.v1`).
