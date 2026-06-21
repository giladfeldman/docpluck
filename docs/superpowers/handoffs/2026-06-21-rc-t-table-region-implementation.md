# RC-T table-region implementation (then RC-1) — handoff (2026-06-21)

## 1. Goal
Implement the **RC-T table-region prose-contamination** fix per
[`docs/superpowers/specs/2026-06-21-rc-t-table-region-prose-contamination.md`](../specs/2026-06-21-rc-t-table-region-prose-contamination.md)
— a region prose-trim + degenerate-region guard keyed on **cell content** — so the 7
v2.4.95 canary papers stop emitting garbage table cells, orphan `### Table N` headings,
empty shells, and duplicate dumps; ship it gated on the full 26-paper baseline + 7-canary
AI-verify with **zero regressions**; THEN pick up RC-1 (region-aware columns).

## 2. Why it matters
RC-T is the single most pervasive defect in the v2.4.95 corpus — broken tables on **all 7**
verified canaries (single- AND two-column). docpluck is a meta-science tool where a fabricated
table (e.g. a running header surfacing as a column header, or Discussion prose as table cells)
is worse than a missing one — it silently corrupts the science. The bbox-computation decision
this resolves has been open since 2026-05-22; the root cause is now confirmed (not guessed), so
the work is bounded.

## 3. State at handoff
- Branch: `feat/rc-t-table-region-guard` (LOCAL only — not pushed; push only when the user asks).
- HEAD commit: `927d869` ("docs(spec): RC-T table-region prose-contamination — confirmed 2-layer root cause + fix plan")
- Committed this session (2 docs-only commits, NO library code changed):
  - `db7192b` — `docs/TRIAGE_2026-06-21_head_v2.4.95_assessment.md` (canonical work queue) + `.claude/skills/docpluck-iterate/LEARNINGS.md` (cycle 3-4 entry)
  - `927d869` — the RC-T spec
- Uncommitted at handoff: `todo.md` (RC-T deferral logged + collabra.77859 closed as adjudicated). **Commit this with your first RC-T commit, or separately — it's pure logging.**
- Library code (`docpluck/`): clean, unchanged. Working tree otherwise clean.
- `tmp/iterate/cycle-3/*.md` are this session's canary renders (gitignored working artifacts; safe to ignore/delete).

## 4. What's done (confirmed)
- **Full real AI-verify of all 7 onboarded canaries @ v2.4.95 = 7/7 FAIL** (7 in-session Sonnet verifiers vs article-finder golds), replacing the clobbered `AUDIT_DEFERRED→PASS` placeholders. Verdicts + findings are in run-meta `phase_5d_runs` (cycle 3).
- **RC-B7 (deleted-minus glyph) confirmed ALREADY DONE** — `normalize.recover_dropped_minus_via_layout` (W0h), wired render.py:5079→normalize.py:3170, tested `tests/test_dropped_minus_layout_recovery_real_pdf.py`. HEAD recovers 4/5 ar_apa betas. **Do not re-implement it.** Residuals (`.245` pixel-minus, β→b) are OCR-tier won't-fix (verified: pdfplumber also extracts `b`/no-minus).
- **RC-T root cause confirmed by instrumentation** (the spec's "2 layers"): (1) Camelot runs free-form (`camelot.read_pdf(..., flavor="stream")`, no `table_areas`) → whole-page bbox; (2) the whitespace fallback region = `caption + SEARCH_BELOW_PT(250)` (detect.py:45,86,99) with no table-END detection → reaches into prose; the clusterer turns prose into rows. Proof: ip_feldman T10 region `(63,71,564,331)` includes Discussion prose at top≈322; structured cells contain `'Ip and Feldman'`/`'15'`/`'Discussion'`/sentence-prose + 1 real row.
- **2 carried-over open_findings adjudicated NOT docpluck defects** (collabra_77859 gold mis-numbering; collabra_90203 text-layer/visual divergence) — closed in todo.md.

## 5. What's next (concrete, ordered)
1. **Reproduce at HEAD first** (mandatory — ~26% verifier FP rate). Render ip_feldman + plos_med + maier + chan_feldman via `python tools/render_for_audit.py --key <doi> --out tmp/x.md` and confirm the table defects are present before coding. Keys: ip_feldman `10.1177/01461672251327169`, plos_med `10.1371/journal.pmed.1004323`, maier `10.1525/collabra.90203`, chan_feldman `10.1080/02699931.2024.2434156`.
2. **Implement the region prose-trim** in `docpluck/tables/whitespace.py` (`whitespace_cells` / `_cluster_into_rows`): compute stable column boundaries from the header + first data rows, then walk rows down and STOP at the first run of prose-shaped rows (full-region-width single text run, no interior column gap aligned to boundaries, sentence-shaped). Trim that row + everything below. The region comes from `docpluck/tables/detect.py::_region_for_caption`.
3. **Add the degenerate-region guard** (belt-and-suspenders): if after trimming the cells are still dominated by furniture/prose (a running-header-pattern cell, a section-heading word like `Discussion`/`Method`, >X% sentence-shaped cells), do NOT emit a `<table>` AND **suppress the orphan `### Table N` heading** — route to the existing `<!-- table-unstructured -->` fallback. The orphan-heading emission is in `docpluck/render.py` (grep `### Table` / the structured-table splice).
4. **Add real-PDF regression tests** (`tests/test_*_real_pdf.py`): ip_feldman T10 (orphan gone OR table recovered), plos_med T5, maier T7, chan_feldman T2 — each FAILS at HEAD, PASSES after. Follow the `PYTEST_XDIST_WORKER`-skip convention for value-exact Camelot tests (see `tests/test_tables_flatten_blank_header_recovery.py`).
5. **Bump versions** consistently: `docpluck/__init__.py::__version__`, `pyproject.toml::version`, `TABLE_EXTRACTION_VERSION` in `extract_structured.py` (table-extraction change), `NORMALIZATION_VERSION` iff normalize.py changes. Update `CHANGELOG.md`.
6. **Verify (HARD GATE):** full 26-paper baseline `PYTHONUNBUFFERED=1 python -u scripts/verify_corpus.py` = 26/26; an ALL-~48-paper guard-live-vs-bypassed render diff (bounded samples give false confidence — see Watchouts); broad `pytest` green; 7-canary AI-verify (render → `ai-gold.py get <key> --view reading` → Sonnet verifier per `~/.claude/skills/_shared/iterate-loop/audit-subagent-prompt.md`) showing no NEW TEXT-LOSS/HALLUCINATION and the touched tables improved or fail-clean.
7. **Then RC-1** (after RC-T ships): region-aware columns for two-column + PLOS-sidebar interleave (chan_feldman, chandrashekar, plos_med front-matter-before-Abstract). Step-2 band path exists ship-dark behind `DOCPLUCK_COLUMN_CORRECT_BANDED`; spec `docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md`, diagnosis `docs/superpowers/specs/2026-06-07-ip_feldman-B4-R4-column-interleave-diagnosis.md`.

## 6. Open decisions
- **RC-T fix depth — guard-only vs guard+recover.** The spec's Layer-1 (pass detect.py regions to Camelot as `table_areas` to actually RECOVER lost tables) is larger and listed out-of-scope for the first cut.
  - (A) **First cut = prose-trim + degenerate-guard only** (clean-fail: no garbage, no orphan; tables still missing). Recommended — lands a safe, general improvement and de-risks the corpus; recovery is a follow-on.
  - (B) Also do Layer-1 `table_areas` recovery in the same cycle (higher value, much higher regression surface).
  - Recommendation: **A first**, then B as a separate cycle once A's baseline is green.
- **Whether to push the branch.** It's local. Push only when the user asks (you're off `main` already, so a docs PR is fine when they want it).

## 7. Watchouts
- **The canary-audit hook clobbers run-meta `phase_5d_runs` with `AUDIT_DEFERRED_TO_AGENT → union PASS`** (memory `feedback_canary_audit_clobbers_phase5d`). It masked this exact 7/7-FAIL corpus as green. **Never trust a canary "PASS" whose `raw_verdicts` are `AUDIT_DEFERRED`** — re-verify manually with in-session Sonnet subagents after every commit before trusting iterate-gate I3.
- **bbox-size is NOT a safe discriminator.** Legitimate landscape Tables 6/7/8 (ip_feldman) have tall bboxes too. Key the guard on CELL CONTENT (furniture/prose), never on "bbox spans most of the page."
- **A bounded sample gives FALSE confidence — run the guard-live-vs-bypassed diff over the FULL ~48-paper corpus.** The cycle-3 caption-follows attempt looked clean on 11 papers and broke 4 real headings on the full set; it was reverted. Same trap waits here (a real sparse/wide-note table row mistaken for prose). This is rule 19 (regression-backcheck) — non-negotiable.
- **Don't truncate legitimate tables.** A genuine wide note/footnote row or merged spanning cell must survive the prose-trim. The trim fires only on prose-shaped rows.
- **Verifiers over-flag (~26% FP).** Reproduce every claimed table defect at HEAD before fixing (cross-project R-0006).
- **`python` (bare) on this machine may hit the Windows Store stub → blank renders.** Use `py -3` for renders (canary.json's `render_command` already does). The global site-packages is fixed (todo.md 2026-06-13 note) but verify `python -s -c "import docpluck"` works.

## 8. Context pointers
- **RC-T spec (read first):** `docs/superpowers/specs/2026-06-21-rc-t-table-region-prose-contamination.md`
- **Canonical work queue:** `docs/TRIAGE_2026-06-21_head_v2.4.95_assessment.md`
- **This session's learnings:** `.claude/skills/docpluck-iterate/LEARNINGS.md` (2026-06-21 entry)
- **Run TODO + run-meta:** `tmp/iterate-todo.md`; `~/.claude/skills/_shared/run-meta/docpluck-iterate.json` (cycle-3 `phase_5d_runs` = the 7 real verdicts)
- **Table pipeline:** `docpluck/tables/{detect.py,whitespace.py,camelot_extract.py,render.py}`, `docpluck/extract_structured.py`
- **RC-1 specs (for step 7):** `docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md`, `docs/superpowers/specs/2026-06-07-ip_feldman-B4-R4-column-interleave-diagnosis.md`
- **Iterate discipline:** `~/.claude/skills/_shared/iterate-loop/core.md` (I1-I12 gate); run `/docpluck-iterate` to resume the loop properly
- **Memories:** `project_docpluck_rc_b7_done_w0h` (don't re-do B7), `feedback_canary_audit_clobbers_phase5d`, `feedback_general_fixes_not_pdf_specific`, `feedback_ground_truth_is_ai_not_pdftotext`
