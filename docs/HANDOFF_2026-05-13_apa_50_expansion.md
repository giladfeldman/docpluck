# Handoff — APA corpus expansion (+50 PDFs) + intense 1-hour parallel verification session

**For:** A fresh session that will (1) expand the test-PDF corpus by 50 new APA-style manuscripts via the `article-finder` skill, (2) run an **AI inspection of app-rendered output** to surface UI-level gaps invisible to the library verifier, (3) dispatch **parallel subagent investigation** across all five workspace views (Rendered, Raw, Normalized, Sections, **Tables**), (4) fix the highest-impact gap — **table rendering on APA papers is currently broken** — plus any other patterns surfaced, then (5) re-run AI inspection on the fixed output, and (6) close with **Chrome/Playwright automated visual verification** on the toughest articles through the `/docpluck-qa` skill.

**Predecessor:** `docs/HANDOFF_2026-05-13_iterative_1.md` — current corpus is 101 PDFs, all PASS at v2.4.5.

---

## Critical anchor issue: TABLE RENDERING IS BROKEN ON APA PAPERS

Visible on `chan_feldman_2025_cogemo.pdf` (already in corpus). The workspace `Tables` view shows:

- **Table 1** (`p.6`): caption present, yellow banner reads *"No cells or raw text extracted. The caption is above; the table's text content is available in the Raw tab."* — Camelot returned 0 cells.
- **Table 2** (`p.X`): no structured `<table>` HTML; cell content leaks into body markdown as a **vertical stack of single-value lines** (`M / SD / alpha` each on its own line; then `1. Degree of apology 2. Empathy ...` mashed on one line; then `5.63 13.22 16.82 6.74 10.11` on one line). The row × column grid is destroyed.

This is the single biggest visible quality gap in v2.4.5. The 101-PDF verifier doesn't catch it because the H-tag heuristic only flags missing `<table>` HTML when `### Table N` headings are present in body — v2.4.2's H-fix suppresses those headings when cells are empty, so the leak slips past.

### Likely root causes (Phase 1 investigates)

1. **Camelot stream-flavor failure on APA layouts** — `chan_feldman` Table 1 returns 0 cells. Compare bbox / dpi / line_scale / row_tol assumptions in `docpluck/tables/camelot_extract.py` against what the PDF actually has.
2. **Fallback when Camelot fails** — currently the raw text leaks as paragraph-broken lines (one cell per `\n\n`). Either reconstruct a minimal HTML grid from spatial layout (pdfplumber chars), OR clean up the vertical-stack appearance, OR explicitly mark the region as "table content unavailable, see raw view".
3. **Cross-view consistency** — Raw / Normalized / Sections views may show different things for the same table. Need a parallel audit.

---

## Workflow shape

```
Phase 0 (parallel)  : 4 read-only subagents investigate table-rendering
                       gap from different angles
Phase 1 (parallel)  : corpus expansion (50 new APA PDFs)
                       — runs while Phase 0 agents work
Phase 2 (background): 151-PDF verifier kicks off (will run for 45-60 min
                       through Phases 3-6)
Phase 3             : AI inspection of APP-RENDERED OUTPUT on chan_feldman
                       + 4 representative new APA papers (BEFORE any fix)
                       — establishes the baseline "what's actually broken
                       in the UI, not just in the library"
Phase 4 (parallel)  : 3 read-only subagents broad-audit all 5 views
                       across the new corpus
Phase 5             : fix the highest-impact pattern (Candidate A/B/C)
                       — full per-iteration loop with 26-paper gate
Phase 6             : AI inspection of APP-RENDERED OUTPUT again,
                       same 5 papers — confirm the fix is visible in
                       the live workspace, not just in unit-test output
Phase 7             : Chrome/Playwright automated visual verification
                       on the 5 toughest articles via /docpluck-qa skill
                       (or its sub-checks if /docpluck-qa is too heavy)
Phase 8             : Close-out handoff doc
```

Parallelism rules:
- Phase 0 dispatches 4 agents in ONE message with 4 `Agent` tool calls (`subagent_type: Explore`).
- Phase 4 dispatches 3 agents in ONE message.
- Phase 2 (151-paper verifier) runs in `run_in_background: true` from start; use `Monitor` with an `until grep -q "# Summary" ...; do sleep 30; done` loop to await without polling.
- Per-fix iteration loop (Phase 5: fix → tests → 26-paper gate → push) stays serial.

---

## Phase 0 — Parallel subagent investigation (FIRST, run all 4 in one message)

```
Agent 1 — Camelot path investigation:
  Read docpluck/tables/camelot_extract.py, docpluck/tables/cell_cleaning.py,
  and the Camelot call sites in extract_structured.py. Identify why
  chan_feldman_2025_cogemo Table 1 returns 0 cells. Report Camelot flavor +
  flags + table-area parameters used; suggest 2-3 specific tuning candidates
  (line_scale, edge_tol, row_tol). Read PDF metadata via pdfplumber if
  useful. Report < 300 words.

Agent 2 — Raw cell-text leak source:
  Read docpluck/render.py lines 1100-1250 + docpluck/extract_structured.py
  ::_extract_caption_text. The current path emits caption-only when html is
  empty (v2.4.2 fix). But the table's raw cell text still appears as
  free-floating one-cell-per-line paragraphs nearby. Trace where this text
  enters the rendered output — is it from the text-channel extraction
  (extract_pdf) reading the PDF in linear order, or from a separate table
  text-extraction path? Suggest a 2-step fix: (a) detect orphan
  single-cell-per-line blocks adjacent to a *Table N. ...* caption, (b)
  fold them into a <pre> raw block or hide them. Report < 300 words.

Agent 3 — All-views consistency check:
  Read tmp/renders_v2.4.0/chan_feldman_2025_cogemo.md (Rendered view).
  Then manually call render_pdf_to_markdown + extract_pdf + normalize_text
  + extract_sections + extract_pdf_structured on the PDF and compare what
  each view contains regarding Tables 1-9. Which views correctly show the
  data? Which lose it? Report a per-view × per-table matrix. < 400 words.

Agent 4 — Corpus-wide prevalence:
  Across all 18 existing apa/ PDFs, grep tmp/renders_v2.4.0/<paper>.md for:
    (a) "*Table" captions WITHOUT a following <table> in next 200 chars,
    (b) standalone single-value lines (^[A-Z]{1,3}$ or ^\d+\.\d+$) appearing
       within 50 lines after a *Table* caption.
  Report which papers exhibit each pattern, count of affected tables per
  paper, and whether the issue is APA-specific or also affects other styles
  (sample 5 papers from each non-APA style). < 300 words.
```

Wait for all 4 to return before deciding the Phase 5 fix direction.

---

## Phase 1 — Corpus expansion (15-20 min, parallel with Phase 0)

Add **50 new APA-style manuscripts** to `PDFextractor/test-pdfs/apa/`. Use `/article-finder` skill (DOI / journal+year queries).

### Existing APA PDFs (do NOT re-download)

```bash
ls ../PDFextractor/test-pdfs/apa/
```

At handoff write: 18 papers including `chan_feldman_2025_cogemo`, `chen_2021_jesp`, `efendic_2022_affect`, `ip_feldman_2025_pspb`, `korbmacher_2022_kruger`, `maier_2023_collabra`, `ziano_2021_joep`, JDM/JESP series, etc. Verify the current list before downloading.

### Stratify by table format (maximize coverage of the anchor issue)

| Cohort | Target | Why |
|---|---|---|
| **Multi-column stats tables** (Psych Science, JPSP, PSPB, JEP) | 15 | Means/SD/CI tables — chan_feldman Table 2 layout. |
| **Inline narrative tables** (hypothesis lists, intervention summaries) | 10 | chan_feldman Table 1 — Camelot 0 cells. |
| **Registered Reports / Stage 1 / Stage 2** | 10 | Subtitle badges + study-by-condition tables. |
| **Replication reports** (RRR, Many Labs) | 8 | Multi-study `Methods_2`/`Results_2` + forest tables. |
| **Open-access APA** (Collabra, Meta-Psychology, JESP) | 7 | Non-standard table numbering + running-header variants. |

For each PDF, stage: title, expected section structure, table count + format type.

### Adding to corpus

1. Save to `../PDFextractor/test-pdfs/apa/<surname>_<year>_<journal>.pdf`.
2. Update `../PDFextractor/test-pdfs/manifest.json` — append `{"id": "apa/<short_name>", "style": "apa"}`.
3. Optional: spike-baseline `.md` under `docs/superpowers/plans/spot-checks/splice-spike/outputs-new/<short_name>.md` with at least the `# Title` line.
4. Per memory `feedback_no_pdfs_in_repo`: PDFs are gitignored in library repo; the app repo keeps them locally.

After Phase 1: corpus is **151 PDFs** (101 + 50 new APA = 68 APA total).

---

## Phase 2 — 151-PDF verifier (background, throughout Phases 3-6)

```bash
cd ~/Dropbox/Vibe/MetaScienceTools/docpluck
python -u scripts/verify_corpus_full.py --save-renders > /tmp/v245_151.log 2>&1 &
```

Then `Monitor` with `until grep -q "# Summary" /tmp/v245_151.log 2>/dev/null; do sleep 30; done`.

Expected: existing 101 stay 101/101 PASS; new 50 add 5-15 new failures. Verifier **won't catch** the table-rendering issue — that's Phase 3 + 4's job.

---

## Phase 3 — AI inspection of APP-RENDERED OUTPUT (BEFORE any fix) (~10 min)

This is the gate that catches what unit tests + library verifier miss. Run the **app-level** extraction (uvicorn → frontend) on 5 hand-picked papers and inspect the actual rendered markdown via the workspace.

### Subjects (5 papers)

1. **`chan_feldman_2025_cogemo.pdf`** — the anchor case (Table 1 caption-only, Table 2 leaked cells).
2. **One new "multi-column stats table" APA paper** from Phase 1.
3. **One new "inline narrative table" APA paper** from Phase 1.
4. **One paper Camelot historically handles well** (e.g. `korbmacher_2022_kruger.pdf`) — regression sentinel.
5. **One paper with mixed table outcomes** (e.g. `ieee_access_4.pdf`, 10 tables in body) — cross-style sanity check.

### Method

For each paper, extract via the app (NOT directly via the library), then dispatch an AI inspection. Two approaches available:

**Option A — via service HTTP (preferred, faster):**
```bash
for p in chan_feldman_2025_cogemo new1 new2 korbmacher_2022_kruger ieee_access_4; do
  curl -X POST http://localhost:6117/extract \
    -F "file=@../PDFextractor/test-pdfs/<style>/<p>.pdf" \
    -F "normalization=academic" \
    > /tmp/app_render_<p>.json 2>&1
done
```

Then load each JSON's `rendered` / `raw` / `normalized` / `sections` / `tables` fields and inspect them.

**Option B — via the workspace UI (slower but exercises the full pipeline):** use the Chrome MCP `__autoCheck(name)` helper documented in `docs/HANDOFF_2026-05-13_iterative_library_improvement.md` (Chrome MCP helpers section). Upload each paper, wait for tabs to populate, capture all 5 view contents.

### AI inspection dispatch (parallel — 5 agents in ONE message)

```
Agent (per paper, ×5) — AI inspection of app-rendered output:
  You are a peer reviewer evaluating the workspace output of paper <name>.
  You have access to the rendered markdown, raw text, normalized text,
  detected sections, and Camelot tables (5 views total) from the live app.
  Compare against the actual PDF (read it via Read tool with pages=...).

  Score each view 0-10 on:
    - Fidelity to source (text accuracy, no missing/duplicated content)
    - Structure preservation (headings present + correct, tables ARE
      tables not flat text, figures captioned)
    - Visual cleanliness (no leaked page numbers, banners, footers)

  Specifically for the Tables view, count:
    - Tables with successful cells + <table> HTML
    - Tables with caption-only (Camelot 0 cells)
    - Tables with leaked cell-text-as-prose in nearby Rendered/Raw output

  Return a per-view scorecard + 3-5 highest-priority defects + 1
  recommended fix direction. < 500 words.
```

Aggregate the 5 reports. Identify the dominant defect class (likely table-rendering, confirming Phase 0 findings) and **the specific user-visible symptom** that will be the fix's success metric.

---

## Phase 4 — Parallel multi-view audit on new corpus (~10 min, dispatch 3 agents)

```
Agent 5 — Multi-column stats tables audit:
  From the 15 new "multi-column APA stats" papers, render each via
  render_pdf_to_markdown (or read tmp/renders_v2.4.0/<paper>.md once Phase
  2 verifier reaches them). Classify each table outcome as:
    (i)   cells extracted + <table> HTML emitted correctly
    (ii)  cells extracted but column/row order wrong
    (iii) Camelot 0 cells; only caption + leaked raw text
    (iv)  cells succeeded but contain garbage (FFFD, misalignment)
  Report counts per category + 2-3 example papers per category. < 400 words.

Agent 6 — Inline narrative tables audit:
  Same for the 10 "inline narrative" papers. Likely all category (iii).
  Confirm + flag any surprises. < 300 words.

Agent 7 — Non-table view audit on same 25 papers:
  Audit all 5 views for: missing/lowercase headings (v2.4.4 area), title
  issues, broken statistical expressions (η², p, F(df1, df2)), running-
  header leaks, leftover 4-digit page numbers (should be 0 after v2.4.5),
  FFFD residues. Report top 5 cross-cutting issues. < 400 words.
```

Combined: Phase 3 (app-level AI inspection) + Phase 4 (library-level multi-view) = full picture of what's broken and where the fix needs to land.

---

## Phase 5 — Fix the highest-impact pattern (~20-30 min)

Pick ONE fix direction based on Phase 0/3/4 outputs:

### Candidate A — Suppress orphan cell-text near captionless tables
Detect a sequence of short single-line paragraphs (1-3 words, no sentence structure) within ~10 lines after a `*Table N. ...*` italic caption when no `<table>` HTML follows. Fold into a `> NOTE: table content available in Raw view` blockquote, or hide entirely. Conservative — only fires when Camelot returned 0 cells. **Low risk, medium impact, ~20 min.**

### Candidate B — Camelot tuning for APA layouts
Agent 1's tuning candidates. Test sweeps on `chan_feldman` Tables 1+2 — if any setting recovers cells, validate against 26-paper baseline before lock-in. **Medium risk** (could regress other corpora), **high impact** if successful, **~30 min.**

### Candidate C — Spatial-layout reconstruction fallback (v2.5.0)
When Camelot 0 cells, walk pdfplumber `page.chars` in caption bbox, cluster by `top` (row) and `x0` (column), emit minimal raw HTML grid. **High effort + highest impact + minor version bump warranted.** Defer to a dedicated session.

**For this 1-hour session: start with A. If A lands fast and time remains, attempt B. Defer C.**

### The per-fix iteration loop

1. Code fix in `docpluck/render.py` (A) or `docpluck/tables/camelot_extract.py` (B).
2. Regression test in `tests/test_render.py` / `tests/test_table_detect.py`.
3. `python -m pytest tests/test_render.py tests/test_table_detect.py -x -q` (< 1 min).
4. `python scripts/verify_corpus.py` (26-paper baseline, ~10 min — **must pass 26/26**).
5. Bump `__version__`, `pyproject.toml`, `TABLE_EXTRACTION_VERSION` if `tables/` touched.
6. `CHANGELOG.md` block.
7. Commit + tag + push library. Bump app pin `service/requirements.txt`. Restart uvicorn (`Stop-Process` + restart on `:6117`).
8. Confirm 151-paper verifier still passes targeted papers.

---

## Phase 6 — Re-run AI inspection of APP-RENDERED OUTPUT (after fix) (~10 min)

**Same 5 papers from Phase 3, same parallel-5-agent dispatch.** This time the agents see the post-fix output. The comparison is the success metric:

- Defect count per view: should drop on the 3 targeted papers (chan_feldman + 2 new APA).
- Regression sentinel (paper 4): score should stay flat or improve.
- Cross-style sanity (paper 5): score should stay flat.

If defect count didn't drop or any view regressed, **revert the Phase 5 commit** (`git revert HEAD; git push`; bump app pin back; restart) and re-triage. Per the iteration handoff's discipline: "if the latest fix moved 0 papers, the targeted pattern was wrong — re-triage before continuing."

---

## Phase 7 — Chrome/Playwright automated visual verification via /docpluck-qa (~10 min)

Invoke the `/docpluck-qa` project skill on the **5 toughest articles** (the same Phase 3/6 set, biased toward the table-rendering anchor). The skill's existing infrastructure includes:

- **Check 5** (`ESCIcheck 10-PDF Verification — Library`) — runs the 10 APA test PDFs through the library extract+normalize pipeline and AI-verifies chars, quality score, p-values, method.
- **Check 6** (`ESCIcheck 10-PDF Verification — Local Webapp`) — same set through the local Next.js + FastAPI stack.
- **Check 13** (`ESCIcheck 10-PDF Verification — Production`) — against the production Vercel/Railway deployment.

For this session, the relevant subset is **Check 6** (local webapp) — exercises the same path as the workspace UI but in scripted form. The skill includes Chrome MCP / Playwright instrumentation for visual capture.

### Invocation

```
Run /docpluck-qa --check 6 --pdfs chan_feldman_2025_cogemo,<new-apa-1>,<new-apa-2>,korbmacher_2022_kruger,ieee_access_4 --capture-screenshots
```

If the skill doesn't support `--pdfs` filtering, run the full Check 6 and grep results for the 5 papers. If Check 6 doesn't include screenshots, manually run the Chrome MCP `__autoCheck` helper on the 5 papers and capture screenshots of all 5 tabs per paper (Rendered / Raw / Normalized / Sections / Tables = 25 screenshots).

### Success criteria

- **Tables view on chan_feldman**: caption-only-but-leaked-cells issue is GONE (or marked with the explanatory blockquote per Candidate A).
- **Rendered view on the 2 new APA papers**: no leaked single-cell-per-line orphan paragraphs near table captions.
- **All 5 views render without console errors** in the workspace.
- **Visual regressions on korbmacher + ieee_access_4 = none** (sentinel papers).

Document any new issues surfaced by the visual pass in the close-out handoff (Phase 8) as deferred items.

---

## Phase 8 — Close-out (5 min)

Write `docs/HANDOFF_2026-05-13_apa_50_<N>.md`:
- Final corpus size (151 PDFs).
- Versions shipped this session (v2.4.5 → v2.4.X / v2.5.0).
- Per-tag failure delta from the 151-paper verifier.
- **Specific table-rendering metric:** number of papers with cell-text leak before/after.
- Per-view scorecard delta from Phase 3 vs Phase 6 AI inspections.
- Screenshot inventory from Phase 7.
- Remaining failures + rough triage.
- Suggested next-session focus (likely Candidate B or C from Phase 5 if not done, or layout-aware running-header fix from the predecessor handoff).

---

## Hard rules (DO NOT VIOLATE)

1. **Never use `pdftotext` with `-layout`** — column interleaving.
2. **Never use `pymupdf4llm` / PyMuPDF / `fitz`** — AGPL incompatible.
3. **Text channel is `extract_pdf`, layout channel is `extract_pdf_layout` — never mix.**
4. **Always normalize `U+2212` → ASCII hyphen** in `normalize.py` S5.
5. **Add a regression test for every fix.**
6. **Bump library version every push.** Patch for fixes; minor for behavior changes affecting rendered bytes.
7. **`scripts/verify_corpus.py` must pass 26/26 before every push.**
8. **No PDFs committed to the library repo** (`feedback_no_pdfs_in_repo` memory).
9. **Camelot is the table library — don't re-litigate** (`feedback_dont_relitigate_table_lib` memory). Tune or fallback; don't propose a new extractor.
10. **HTML tables in `.md` output, not pipe-tables** (`project_html_tables_in_md` memory).
11. **Fix → AI inspect → visual verify, in that order.** If AI inspection of app-rendered output doesn't see the fix, the library push is incomplete.

---

## State at handoff

- **Library:** `giladfeldman/docpluck` v2.4.5 at HEAD `f94bcca`. `NORMALIZATION_VERSION` 1.8.3. `TABLE_EXTRACTION_VERSION` 2.1.0 (ripe for a bump if Phase 5 touches Camelot).
- **App:** `giladfeldman/docpluckapp` master `b9cee6f`, pinned to `docpluck v2.4.5`.
- **Dev service:** uvicorn `:6117` running v2.4.5 (restart needed after Phase 5 version bump).
- **Frontend:** Next.js on `:6116` — required for Chrome MCP / `/docpluck-qa` Check 6.
- **Corpus:** 101 PDFs all PASS at v2.4.5. APA = 18 papers (will be 68 after Phase 1).
- **Test suite:** 926+ tests pass.

## File map (table-rendering surface)

- `docpluck/tables/camelot_extract.py` — Camelot integration; the function that returns 0 cells on chan_feldman lives here.
- `docpluck/tables/cell_cleaning.py` — post-Camelot cell pipeline.
- `docpluck/tables/render.py` — `cells_to_html` + raw fallback.
- `docpluck/tables/captions.py` — caption regex + `_extract_caption_text`.
- `docpluck/extract_structured.py` — top-level structured-extract; builds Table dicts.
- `docpluck/render.py::_render_sections_to_markdown` lines 1180-1250 — body splicing (v2.4.2 H-tag fix lives here).
- `tests/test_table_detect.py`, `tests/test_tables_cell_cleaning.py` — table test harnesses.
- `.claude/skills/docpluck-qa/SKILL.md` — Check 5/6/13 ESCIcheck AI verification + Chrome MCP infrastructure.

## Target outcome

By session end: **151/151 PASS on corpus verifier** AND **table-rendering defect count on chan_feldman = 0** in the live workspace (Chrome screenshot evidence) AND **Phase 6 AI inspection score ≥ Phase 3 score** on all 5 papers. Document the before/after numbers in the close-out handoff.

Good luck.
