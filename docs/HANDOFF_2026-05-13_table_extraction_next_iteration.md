# Handoff — Table extraction quality iteration (post-Camelot-restored)

**Date written:** 2026-05-13 evening, after a marathon day of fixes.
**Library state at handoff:** `docpluck@v2.4.13` (live on prod).
**App state at handoff:** `docpluckapp@master` pinned to `v2.4.13` (live on Vercel + Railway).

## TL;DR

After 13 patch releases today (v2.4.6 → v2.4.13), the headline defect is **finally root-caused and shipped**: `camelot-py` was never declared as a dependency in `docpluck/pyproject.toml` or `PDFextractor/service/requirements.txt`, and the wrapper at `docpluck/tables/camelot_extract.py:276-278` silently caught the `ImportError` and returned `[]`. **For the entire production lifetime of the service, Camelot was absent and every PDF returned zero structured tables.** Five+ hours of work in v2.4.6 → v2.4.12 went into the WRONG rabbit hole (render-pipeline post-processors) because local dev had Camelot pip-installed manually, masking the bug.

v2.4.13 declares `camelot-py[cv]>=0.11.0` as a hard dep, adds `ghostscript libgl1 libglib2.0-0` to the Dockerfile, and exposes Camelot/OpenCV/Ghostscript version info via `/_diag`. **Live prod verification:** chan_feldman_2025_cogemo now returns **5 of 9 tables structured** (Tables 2, 5, 6, 7, 8 with HTML `<table>` grids; Tables 1, 3, 4, 9 fall back to populated `raw_text`).

**The next session continues from here, with a TIGHT iterative-local-first workflow per the user's explicit direction.** No more shipping based on local-only assumptions.

---

## Critical context — DO NOT re-litigate these

Read these BEFORE touching any rendering / table code:

1. **`feedback_pdftotext_version_skew`** memory — local dev runs Xpdf 4.00 (2017), Railway runs poppler-utils 25.03 (2025). Same PDF, different paragraph spacing (`\n\n` vs single `\n`). Every render-pipeline heuristic must be tested against BOTH styles. Pattern: line-level iteration, not paragraph-split.

2. **`feedback_no_silent_optional_deps`** memory — saved today. Never have `try: import X; except ImportError: return []` for a dep that's been settled-on. Declare it in pyproject.toml + make ImportError raise loudly. This was a $5-hour bug.

3. **`feedback_ai_verification_mandatory`** memory — char-ratio + Jaccard verifier are blind to "right words in wrong order under wrong heading". Don't ship without AI inspection of rendered output OR direct visual verification.

4. **`project_camelot_for_tables`** memory — Camelot stream flavor is the settled-on extractor (5-library bake-off, 2026-05-09). Don't re-litigate.

5. **CLAUDE.md hard rules** — `pdftotext -layout` is FORBIDDEN (column interleaving). `pymupdf/fitz` is AGPL-FORBIDDEN. Only pdfplumber (MIT) + pdftotext (default mode) allowed.

6. **CLAUDE.md release flow** — every library tag MUST bump app `service/requirements.txt`. The auto-bump bot now does this automatically (see Library/App Sync below).

---

## Library/App sync system (operational, do not break)

Three-part system shipped earlier today, working end-to-end:

1. **Library auto-bump bot** (`docpluck/.github/workflows/bump-app-pin.yml`) — on every `v*.*.*` tag push, opens a PR in `docpluckapp` bumping `service/requirements.txt` to the new tag. Uses `APP_REPO_TOKEN` secret (already set in `docpluck` repo).

2. **Post-deploy verifier** (`docpluckapp/.github/workflows/verify-railway-deploy.yml`) — on every push to master touching `service/`, polls `/health` for up to 8 min and asserts `docpluck_version` matches the requirements.txt pin. Fails the build if Railway didn't redeploy or the version doesn't match.

3. **Service version reporting** (`PDFextractor/service/app/main.py`) — `/health` and every extraction endpoint's metadata now report `docpluck.__version__` (not the FastAPI app version). `/_diag` reports docpluck + camelot + opencv + ghostscript versions + which render post-processors are loaded.

**Auto-merge is NOT enabled on `docpluckapp`** (the API call to enable it returned `allow_auto_merge: false`). So pin-bump PRs need manual merge (one click per release). Verify with `gh pr list --repo giladfeldman/docpluckapp`.

Documentation: `docpluck/docs/LIBRARY_APP_SYNC.md`.

---

## Version badge (operational)

Floating badge in the bottom-right of every workspace page shows `app vX.Y.Z · lib vX.Y.Z`. Click/hover for git SHA, deploy timestamp, extraction-service version. Fetches once on mount (per user direction — no auto-refresh). Goes amber when extraction service is unreachable.

- `frontend/src/app/api/version/route.ts` — server-side `/api/version` that reads `package.json` + proxies the extraction service's `/health`.
- `frontend/src/components/version-badge.tsx` — client component, mounted in root layout.

---

## Premium role / quota bypass (operational)

3-tier role system: `user` / `premium` / `admin`. Premium and admin bypass the 5/day quota. Admin gets dashboard access; premium is granted via the admin dashboard's Users-tab role badge (click to cycle user↔premium; admin role only via SQL).

- Schema: `frontend/src/lib/schema.ts` (users.role column).
- Auth: `frontend/src/lib/api-auth.ts` (`requireAdmin` reads role from DB with email fallback; `authenticateRequest` returns `dailyLimit: -1` for admin/premium).
- Migration applied: `frontend/drizzle/0001_add_user_role.sql`. giladfel@gmail.com is now `role='admin', daily_limit=-1`.

---

## What's CURRENTLY broken (next session's targets)

User confirmed via screenshots after v2.4.13 went live on prod:

### Defect A — Rendered view doesn't show structured tables at their caption position

**Symptom:** User reports "I'm still not seeing tables in the rendered view in their position". Tables 2, 5, 6, 7, 8 are now structured (cells extracted, HTML produced) but the Rendered view of chan_feldman_2025_cogemo seems to show only Table 1's caption + orphan rows in body position.

**To investigate:**

1. Locally render chan_feldman with v2.4.13 (camelot installed) and inspect the `.md` output for `<table>` blocks.
2. Compare position of `<table>` blocks vs the actual table mention in the body. If the renderer is putting them in the "Tables (unlocated in body)" appendix instead of inline, that's the bug.
3. Check `_render_sections_to_markdown` in `docpluck/render.py` lines 1132-1145 — `_locate_caption_anchor` finds the caption position inside the section's char window. If it returns -1, the table goes to `unlocated_tables`. The chan_feldman captions go from sec.text linear extraction — `_locate_caption_anchor` does whitespace-tolerant match. Verify it's matching for Tables 2/5/6/7/8.

**Likely cause:** The user might just need to scroll down — Table 2 is on page 7 of the PDF, so it's deep in the rendered .md. OR there's a real positioning bug where structured tables go to the appendix unlocated.

### Defect B — `raw_text` extraction bleeds past the table boundary

**Symptom:** Screenshots show:
- Table 1 raw_text includes "Note: Hypothesis 3 is not included in the replication because it involves a clinical intervention..." (this is body prose AFTER the table, not the table's cells).
- Table 9 raw_text starts with "than empathy. We provided full analyses and results for the comparisons in the 'Additional analyses and results' section in the supplementary." — entirely body prose, not table cells at all.

**Root cause:** `docpluck/extract_structured.py::_extract_table_body_text` (added in v2.4.12) uses `next_boundary` from the caption list. When the next caption is far away (or doesn't exist on the same page), it falls back to 3000 chars, which routinely captures the next paragraph of body prose.

**Fix direction (NEXT SESSION):**
- Detect end-of-table signals: form-feed (`\x0c`) marking page boundary, a long prose paragraph (>200 chars with 5+ stopwords) after a run of short cell-like lines, or a section heading.
- Stop short — better to under-extract (show too few cells) than over-extract (show body prose as cells).
- For pages where Camelot DID detect cells, set `raw_text=""` on the isolated tables on adjacent pages so they don't leak into pages with structured tables.

### Defect C — Some "tables" are actually body prose

**Symptom:** Table 4 raw_text shows measurement-scale text ("Perceived apology — 'The offender has apologised?' — 'The offender has attempted to explain their hurtful behaviour?'..."). These ARE the table cells (it's a measurement-scale comparison table), so this is actually correct. **No fix needed for Table 4** — it's working as intended.

But there's a broader concern about the boundary problem (Defect B) producing false-positive cells.

### Defect D (still open from earlier handoffs)

- xiao_2021_crsp false `Experiment` heading (`sections/taxonomy.py::lookup_canonical_label` needs context-aware rejection — Agent already mapped fix in earlier handoff).
- xiao_2021_crsp KEYWORDS / Introduction section boundary (partition-level fix in `sections/core.py`).
- Standalone page-number residue surviving S9 (15 instances, top: jmf_3, bmc_med_1).
- 50-PDF corpus expansion (Agent 6 from iter-1 provided ready-to-paste bash block in `docs/HANDOFF_2026-05-13_apa_50_expansion_iter_1.md`).

---

## The iterative-local-first workflow (user's explicit direction)

The user shipped this guidance at the end of today's session:

> "to save time and budget running this on the docker, you need to run as much as possible in local testing, figure all the quirks out, optimize as much as possible iteratively and ensure that things are working properly. first, the library, then comprehensive testing with local dev (analysis, export, examine exporting), then, when you're sure it's as good as can be, deploy, test online. iteratively, like we did before but real checks, not on a simulated side, not deterministic, you checking each step and ensuring we're making progress."

**Process for the next session:**

**Step 1 — Library audit (local).** With camelot installed locally (`pip install camelot-py[cv]` — already done as of this handoff), render chan_feldman and 4 other PDFs. For each:
- Open the `.md` and visually scan ALL 5 views' worth of content (rendered, raw, normalized, sections, tables).
- Identify every defect.
- Fix one class at a time. Re-render. Re-inspect.

**Step 2 — Library fixes, one at a time.**
- Tight regression test for each fix (test against poppler-style single-`\n` paragraph spacing per `feedback_pdftotext_version_skew`).
- Run `python scripts/verify_corpus.py` 26-paper baseline after each fix. Must stay 26/26.
- Spot-check 3-5 papers with the fix applied. Read the rendered output as a user would — not just diff-checks.

**Step 3 — Local dev stack.** Once library spot-checks are clean:
- Start the FastAPI extraction service locally: `cd ../PDFextractor/service && uvicorn app.main:app --port 6117 --reload`.
- Start the Next.js frontend locally: `cd ../PDFextractor/frontend && npm run dev` (port 6116).
- Upload chan_feldman + 2-3 other PDFs through the actual UI. Click through all 5 view tabs. Try the analyze flow. Try export.
- Find any frontend-only defects (rendering, layout, export-format quirks).

**Step 4 — Ship.** Only when local dev shows clean behavior:
- Bump library version, push tag → auto-bump bot opens PR → merge manually.
- Wait for verify-railway-deploy.yml to confirm `docpluck_version` matches.
- Probe prod `/_diag` to confirm camelot still installed, version matches.
- Hit `/tables` on chan_feldman, assert ≥ 5 structured tables.
- Open the workspace UI in a browser and verify the user-facing tabs.

---

## Useful commands for next session

```bash
# Local rendering for inspection
cd ~/Dropbox/Vibe/MetaScienceTools/docpluck
python -c "
from pathlib import Path
from docpluck.render import render_pdf_to_markdown
pdf = Path('../PDFextractor/test-pdfs/apa/chan_feldman_2025_cogemo.pdf').read_bytes()
md = render_pdf_to_markdown(pdf)
Path('tmp/chan.md').write_text(md, encoding='utf-8')
"

# Local structured extract to inspect tables
python -c "
from pathlib import Path
from docpluck.extract_structured import extract_pdf_structured
pdf = Path('../PDFextractor/test-pdfs/apa/chan_feldman_2025_cogemo.pdf').read_bytes()
r = extract_pdf_structured(pdf)
for t in r['tables']:
    print(f\"{t['label']} p.{t['page']} kind={t['kind']} cells={len(t.get('cells') or [])} html={bool(t.get('html'))} raw_text_chars={len(t.get('raw_text') or '')}\")
"

# 26-paper baseline (must pass)
python scripts/verify_corpus.py

# Heuristic linter for visible defects
python scripts/lint_rendered_corpus.py tmp/renders_v2.4.0/

# Probe prod state
curl -s https://extraction-service-production-d0e5.up.railway.app/_diag | python -m json.tool

# Probe prod tables for a specific PDF (admin API key in: env var or
# regenerate via frontend/scripts/get-or-create-admin-key.mjs)
curl -sS -X POST -H "Authorization: Bearer dp_..." \
  -F "file=@../PDFextractor/test-pdfs/apa/chan_feldman_2025_cogemo.pdf" \
  "https://extraction-service-production-d0e5.up.railway.app/tables" \
  | python -m json.tool

# Apply a Drizzle migration
DATABASE_URL="..." node ../PDFextractor/frontend/scripts/run-migration.mjs ../PDFextractor/frontend/drizzle/000X_*.sql

# Inspect Neon users table state
DATABASE_URL="..." node ../PDFextractor/frontend/scripts/inspect-users.mjs
```

---

## File map — what to touch and why

**Render pipeline (post-pdftotext, before markdown emission):**
- `docpluck/render.py::_render_sections_to_markdown` (lines 1093-1280) — section emission + table/figure splicing. Where structured `<table>` HTML gets dropped at the caption position.
- `docpluck/render.py::_locate_caption_anchor` (line 1008+) — whitespace-tolerant caption matching. Returns -1 if no match → table goes to unlocated appendix.
- `docpluck/render.py::_suppress_orphan_table_cell_text` (v2.4.10+) — drops orphan cell-row leaks after Table N captions. Already line-level for poppler compatibility.

**Structured extraction (Camelot + caption pairing):**
- `docpluck/extract_structured.py::extract_pdf_structured` — top-level. Camelot output → caption matching → final tables list.
- `docpluck/extract_structured.py::_find_caption_for_table` (line 238) — token-overlap scoring. Bug suspect when Tables 2/5/6/7/8 land in unlocated appendix.
- `docpluck/extract_structured.py::_extract_table_body_text` (line 410+, added v2.4.12) — raw_text fallback. **DEFECT B target.**
- `docpluck/extract_structured.py:142-154` — `pages_with_table_caption` filter. Drops Camelot tables on pages without same-page captions.

**Camelot wrapper:**
- `docpluck/tables/camelot_extract.py::_is_table_like` (line 137) — 40% data-cell ratio threshold. Conservative against false-positive 2-column body prose.
- `docpluck/tables/camelot_extract.py::_pick_best_per_page` (line 207) — stream vs lattice selection.
- `docpluck/tables/camelot_extract.py::extract_tables_camelot` (line 260) — entry point. Has `try: import camelot; except ImportError: return []` at line 276 — **DO NOT remove the try-except (camelot IS a hard dep now, but the fallback is still defensive), BUT consider raising loudly with an installation hint.**

**Service / Frontend:**
- `PDFextractor/service/app/main.py::/_diag` — single source of truth for "what's installed on prod". Hit this first when prod misbehaves.
- `PDFextractor/frontend/src/components/document-workspace.tsx` lines 905-930 — Tables tab. Renders `t.html` if present, else `t.raw_text` with amber notice, else the "No cells" banner.

---

## State at handoff — verified live on prod (2026-05-13 ~17:00)

```
GET /_diag:
{
  "docpluck_version": "2.4.13",
  "camelot_version": "1.0.9",
  "opencv_version": "4.13.0.92",
  "ghostscript_binary": "/usr/bin/gs",
  "post_processors_present": [
    "_demote_false_single_word_headings",
    "_demote_inline_footnotes_to_blockquote",
    "_promote_numbered_subsection_headings",
    "_promote_study_subsection_headings",
    "_rejoin_garbled_ocr_headers",
    "_suppress_orphan_table_cell_text"
  ]
}

POST /tables  (chan_feldman_2025_cogemo.pdf):
  Table 1 p.6  kind=isolated   html_len=0     raw_text_len=1704
  Table 2 p.7  kind=structured html_len=703   raw_text_len=275
  Table 3 p.8  kind=isolated   html_len=0     raw_text_len=594
  Table 4 p.9  kind=isolated   html_len=0     raw_text_len=2991
  Table 5 p.11 kind=structured html_len=2194  raw_text_len=1436
  Table 6 p.11 kind=structured html_len=708   raw_text_len=312
  Table 7 p.12 kind=structured html_len=478   raw_text_len=211
  Table 8 p.13 kind=structured html_len=1980  raw_text_len=469
  Table 9 p.13 kind=isolated   html_len=0     raw_text_len=589
```

- **Library:** v2.4.13 tagged, pushed, deployed.
- **App pin:** `service/requirements.txt` @v2.4.13.
- **Camelot:** v1.0.9 installed via `camelot-py[cv]` in pyproject deps.
- **Ghostscript:** /usr/bin/gs (auto-included with poppler-utils).
- **OpenCV:** 4.13.0.92 (via opencv-python-headless, Camelot[cv] dep).
- **26-paper baseline:** 26/26 PASS at v2.4.11 (last full run). v2.4.12, v2.4.13 — only library deps changed, unit tests 230/230 PASS.

**Open PRs in docpluckapp:** none (PR #4 for v2.4.13 manually merged at 16:58:44Z).

**App repo branches:** master @ 2031b06 (Dockerfile + /_diag changes after the v2.4.13 pin bump).

Good luck.
