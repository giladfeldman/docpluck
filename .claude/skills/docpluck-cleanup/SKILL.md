---
name: docpluck-cleanup
description: Comprehensive doc-sync + dead-code cleanup across BOTH the docpluck library repo and the PDFextractor app repo. Reads actual code, then verifies CLAUDE.md / README.md / DESIGN.md / NORMALIZATION.md / BENCHMARKS.md / API.md / ARCHITECTURE.md / SETUP_GUIDE.md / TODO.md / CHANGELOG.md / LESSONS.md reflect it. ALSO syncs USER-FACING frontend pages (homepage, about-normalization, sections, api-docs, benchmarks) with current library capabilities — supported formats (PDF/DOCX/HTML), feature list, normalization step count, hard-coded URLs — and audits mobile/desktop content parity (no nav links, CTAs, or footer items hidden on mobile without a hamburger / Sheet equivalent). Removes dead benchmark scripts, cleans temp/, audits .gitignore + env vars, verifies cross-repo version pin consistency. Use /docpluck-cleanup periodically and after every release or major feature.
tags: [python, pdf, docx, html, fastapi, nextjs, docs, cleanup, marketing-sync, mobile-parity]
---

## [MANDATORY FIRST ACTION] preflight (do NOT skip, even if orchestrated by /ship)

**Your very first action in this skill, BEFORE reading anything else, is:**

1. Run: `bash ~/.claude/skills/_shared/bin/preflight-filter.sh <this-skill-name>` and print its `🔧 skill-optimize pre-check · ...` heartbeat as your first visible output line.
2. Initialize `~/.claude/skills/_shared/run-meta/<this-skill-name>.json` per `~/.claude/skills/_shared/preflight.md` step 6 (include `phase_start_sha` from `git rev-parse HEAD`).
3. Load `~/.claude/skills/_shared/quality-loop/core.md` into working memory (MUST-level rules gated by /ship).

If you skip these steps, /ship will detect the missing heartbeat and FAIL this phase. Do not proceed to the skill body until preflight has run.

# Docpluck Cleanup

You are a codebase janitor for Docpluck. Your job is to keep documentation accurate **across BOTH repos**, remove dead code, and ensure both repos are in a clean state. Run me periodically — at minimum **after every release** and **after every major feature**.

## Scope: TWO repos

| Repo | Path | Visibility |
|---|---|---|
| Library | `C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck` | public (PyPI: `docpluck`) |
| App | `C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor` | private (Vercel + Railway) |

**Doc-sync runs against BOTH.** Dead-code removal is per-repo. Always check both unless the user explicitly scopes (`/docpluck-cleanup --library` or `/docpluck-cleanup --app`).

---

## Section 1: Library repo doc sync

### 1.1 — Read the public API surface from code FIRST, then verify each doc reflects it

Before touching any doc, capture the current public surface so you can compare against it:

```bash
cd C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck
python -c "import docpluck; print('\n'.join(sorted(docpluck.__all__)))"
python -c "from docpluck import __version__, NORMALIZATION_VERSION; from docpluck.sections import SECTIONING_VERSION; print(f'lib={__version__} norm={NORMALIZATION_VERSION} sec={SECTIONING_VERSION}')"
python -c "from docpluck.sections import SectionLabel; print(','.join(l.value for l in SectionLabel))"
git log --oneline --since="30 days ago" | head -50
```

Then walk each doc:

#### `docs/README.md` (public-facing — renders on GitHub + PyPI)
- [ ] Quick-start example uses current public API names from `docpluck.__all__`
- [ ] Installation extras list matches `pyproject.toml [project.optional-dependencies]`
- [ ] Major features list mentions every name in `docpluck.__all__` at least once
- [ ] If a new module landed (e.g., `docpluck.sections`, `docpluck.extract_layout`), README has at least one example referencing it
- [ ] Section labels listed match `SectionLabel.__members__` if the README documents the taxonomy
- [ ] Version badge / install command shows current `__version__`

#### `docs/DESIGN.md`
- [ ] Architecture overview mentions every public module: `extract`, `extract_docx`, `extract_html`, `normalize`, `quality`, `batch`, `sections`, `extract_layout`
- [ ] Decision log entries exist for any major feature shipped since the last cleanup pass (cross-reference `git log --since="<last cleanup>" --oneline`)
- [ ] Spec doc references in `docs/superpowers/specs/` are linked correctly if the corresponding code shipped

#### `docs/NORMALIZATION.md`
- [ ] Lists every step actually applied in `docpluck/normalize.py`: S0–S9, A1–A6, A3a, A3b, W0, R2, R3, A7, F0
- [ ] Each step's behavior matches the implementation (read the code, don't trust the doc)
- [ ] `NORMALIZATION_VERSION` mentioned in the doc matches the constant in `normalize.py`
- [ ] If a new step was added (e.g., F0 layout-aware footnote strip in v1.6.0), it has its own subsection
- [ ] Sentinel conventions (e.g., `\f` page break, `\n\f\f\n` footnote appendix) are documented

#### `docs/BENCHMARKS.md`
- [ ] Numbers reflect the latest benchmark run (don't fabricate; if stale, mark stale rather than delete)
- [ ] Tested formats list matches what the library actually supports (PDF/DOCX/HTML)
- [ ] If section identification was added, mention coverage % on the test corpus or note "no formal benchmark yet — see TODO.md"

#### `docs/superpowers/specs/` and `docs/superpowers/plans/`
- [ ] Specs for features that already shipped: do NOT edit (historical record); only check for broken links / typos
- [ ] Plans for completed work: leave as-is (historical artifact)
- [ ] Specs for unshipped work: still describe what's planned cleanly

### 1.2 — Root-level docs

#### `CLAUDE.md` (library)
- [ ] Two-repo architecture table accurate
- [ ] Hard rules section lists every NEVER/ALWAYS rule from the codebase (cross-reference `.claude/skills/docpluck-review/SKILL.md` — every numbered hard rule there should be reflected here in summary form)
- [ ] Release flow steps still match what `/docpluck-deploy` does
- [ ] Project skills table accurate (counts + paths)
- [ ] "Key project docs" section lists every file in `docs/` (no orphans, no missing entries)

#### `CHANGELOG.md`
- [ ] Top entry matches `__version__` in `docpluck/__init__.py` and `version` in `pyproject.toml`
- [ ] All entries have a real date (not `2026-MM-DD` placeholder)
- [ ] Backwards-compat notes present for breaking-API changes
- [ ] No `[Unreleased]` section if there's nothing in it

#### `TODO.md`
- [ ] Items marked complete that ARE complete (cross-reference recent commits)
- [ ] New deferred items appended for any `TODO:` / `deferred to v...` comments found in the codebase since last pass (`git grep -n "TODO\|FIXME\|deferred to" docpluck/ tests/ | grep -v "test_"`)
- [ ] No items duplicated across milestones (e.g., same feature listed under both v2.0 and v2.1)

### 1.3 — Memory + auto-tracked files

- [ ] `C:\Users\filin\.claude\projects\C--Users-filin-Dropbox-Vibe-MetaScienceTools-docpluck\memory\MEMORY.md` — check for stale facts; cross-reference current state. The user's memory is the source of context for future Claude sessions; stale entries cause wrong assumptions.

### 1.4 — Library dead code / artifacts

- [ ] `tests/fixtures/` — confirm fixtures are still used (`grep -r fixture_name tests/test_*.py`)
- [ ] `tests/golden/` — confirm snapshot files still match a current test (no orphans)
- [ ] `pyproject.toml` extras — every extra has at least one user (no dead extras shipped)
- [ ] `docpluck/` — no `*.pyc`, no `__pycache__/` committed
- [ ] `.gitignore` includes `*.pdf` (per MEMORY.md rule: no PDFs in repo); golden snapshots are JSON, not PDF
- [ ] `.worktrees/` ignored (per existing `.gitignore`)
- [ ] No `REPLY_FROM_DOCPLUCK_v*.md` or `REQUEST_*.md` files older than 6 months that the user has explicitly archived (ASK before deleting these — they are intentional cross-project communication)

---

## Section 2: App repo doc sync

```bash
cd C:/Users/filin/Dropbox/Vibe/MetaScienceTools/PDFextractor
git log --oneline --since="30 days ago" | head -50
```

### 2.1 — Library pin verification (the #1 release-flow failure mode)

- [ ] `service/requirements.txt` git pin matches the latest released library version: `docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git@v<VERSION>` where `<VERSION>` matches the library's `__version__` in `docpluck/__init__.py`
- [ ] `service/Dockerfile` builds clean (don't run; verify no obvious staleness — base image, poppler-utils install, etc.)
- [ ] `API.md` example responses are byte-aligned with what the actual FastAPI route returns (especially after a library version bump)
- [ ] If the library shipped a new `extract_*` function or `extract_sections` capability, a corresponding endpoint exists in `service/app/main.py` (or is intentionally not yet exposed — flag for the user if unclear)

### 2.2 — Root docs

#### `CLAUDE.md` (app)
- [ ] Project structure matches actual directories (`frontend/`, `service/`, `scripts/`, etc.)
- [ ] Documented commands (`npm run dev`, `pytest`, etc.) work as written
- [ ] Critical rules apply
- [ ] Two-repo architecture table is consistent with the LIBRARY's `CLAUDE.md` (they should agree on which repo is which — flag any drift)

#### `README.md`
- [ ] Architecture diagram matches reality (Next.js + FastAPI + Neon)
- [ ] Tech versions correct (Next.js, Auth.js, Drizzle, Python, FastAPI)

#### `ARCHITECTURE.md`
- [ ] System diagrams match actual deployment (Vercel + Railway)
- [ ] All DB tables listed are present in `frontend/db/schema.ts` (or wherever the schema lives)
- [ ] No orphan tables (every schema table has at least one query in the codebase — `grep -r "table_name" frontend/`)

#### `API.md`
- [ ] Endpoint signatures match `service/app/main.py`
- [ ] If the library exposes new functions used by the app, API.md mentions any new endpoints surfacing them
- [ ] Response shapes match what the FastAPI routes actually return (read the code, don't trust the doc)
- [ ] Normalization step list current with library's `docpluck/normalize.py`
- [ ] Auth + rate-limit requirements documented per endpoint

#### `SETUP_GUIDE.md`
- [ ] All URLs / project IDs / domain names current
- [ ] Required env vars match what `frontend/.env.example` and `service/.env.example` reference
- [ ] Local-dev port numbers correct (frontend, service)

#### `TODO.md`
- [ ] Items marked complete that ARE complete

#### `LESSONS.md` / `UNADDRESSED_ISSUES.md` / `HANDOVER_SESSION_PROMPT.md`
- [ ] No stale lessons that contradict current code
- [ ] Unaddressed issues — flag any that look stale (committed code probably resolved them; ask user to confirm before removing)
- [ ] Handover prompt — if it's >30 days old and references a milestone that's already shipped, mark as outdated (don't auto-edit; this is communication artifact)

### 2.3 — App dead code / artifacts

#### `scripts/` — known-deletable diagnostic scripts (verify they exist before deleting):
- `scripts/investigate_stat_loss.py`, `investigate_stat_loss2.py` — diagnostic
- `scripts/trace_pipeline.py`, `trace_pipeline2.py` — diagnostic
- `scripts/verify_ieee_fp.py` — diagnostic
- `scripts/quick_apa_verify.py` — diagnostic
- `scripts/diagnose_mismatches.py` — diagnostic
- `scripts/benchmark_docling_optimized.py` — Docling was dropped

**Keep:** `benchmark.py`, `ground_truth_verify.py`, `optimized_extractors.py`, `pdftotext_enhanced.py`, `setup_test_pdfs.py`, `ai_verify.py`, `final_showdown.py`

Before deleting any script, grep the codebase to confirm nothing imports or invokes it: `grep -rn "<script_name>" .`

#### `temp/` — purge: `rm -rf temp/` (rendered PNG pages from verification, not needed in repo)

#### `.gitignore`:
- [ ] Includes `.env`, `.env.local`, `.env.production`, `.vercel/`, `test-pdfs/`, `temp/`, `__pycache__/`, `node_modules/`, `.next/`

#### Dependencies:
- [ ] `frontend/package.json` — no unused deps (compare to actual imports: `grep -r "from '<dep>'" frontend/app frontend/lib`)
- [ ] `service/requirements.txt` — only fastapi, uvicorn, pdfplumber, python-multipart, docpluck (+ optional extras)
- [ ] No `pymupdf`, `pymupdf4llm`, `column_boxes` anywhere in either repo (AGPL guard — BLOCKER if found)

### 2.4b — Frontend USER-FACING pages must reflect current library capabilities

The marketing surface (homepage, feature pages, docs pages) is the public face of Docpluck and goes stale faster than any other doc — every shipped library feature can silently un-document itself here. Audit on every cleanup run, not just on releases.

**Step 1 — capture ground truth from the LIBRARY repo:**

```bash
cd C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck
python -c "import docpluck; print(sorted(docpluck.__all__))"
python -c "from docpluck.normalize import NORMALIZATION_VERSION; print(NORMALIZATION_VERSION)"
python -c "
import re
src = open('docpluck/normalize.py').read()
steps = sorted(set(re.findall(r'^\s*#\s*(S\d|A\d[a-z]?|W\d|R\d|F\d)\b', src, re.M)))
print('Active normalization step labels:', steps, '→ count =', len(steps))
"
```

Note the supported formats (any `extract_pdf*`, `extract_docx*`, `extract_html*`, `extract_layout*`, `extract_structured*`, `render*`, `partition_into_sections`, `extract_tables*`, `extract_figures*` in `__all__`).

**Step 2 — audit each user-facing page against ground truth:**

#### `frontend/src/app/page.tsx` (homepage)
- [ ] Hero / `<h1>` / hero paragraph mentions every supported INPUT format (PDF + DOCX + HTML if all are exposed). NOT just "PDF" if the service accepts more.
- [ ] Stats row (e.g., `"14 normalization steps"`, `"100% ground truth"`, `"~400ms"`) matches current reality. If a hard-coded number drifted, either update it or replace with a constant import.
- [ ] Features grid mentions each MAJOR capability the library exposes today: column-aware reading order, ligature expansion, Unicode recovery, statistical line-break repair, minus-sign normalization, quality scoring, **section identification**, **table extraction**, **figure extraction**, **layout-aware footnote stripping**, **render-to-markdown**. Missing capability = stale homepage.
- [ ] "How it works" step list reflects the actual pipeline (e.g., "Extract → Normalize → Sections → Tables → Render", not just "Extract → Normalize → Score" if more is happening).
- [ ] "Choose your level" / normalization-tier cards list every step active in `normalize.py` for that tier.
- [ ] Code-sample URL (e.g., `https://docpluck.vercel.app/api/extract`) matches the actual production URL — flag if the frontend hard-codes an outdated host.
- [ ] CTA copy ("5 PDFs/day", "Free for researchers") matches the active rate-limit constants in `frontend/src/lib/`.

#### `frontend/src/app/about-normalization/page.tsx`
- [ ] Step list and per-step explanations match `docs/NORMALIZATION.md` AND `docpluck/normalize.py` (read all three; trust the code).
- [ ] `NORMALIZATION_VERSION` shown on the page matches the constant.

#### `frontend/src/app/api-docs/page.tsx`
- [ ] Endpoint list matches `service/app/main.py` routes — no missing endpoints, no removed-endpoint references.
- [ ] Request/response examples match the latest pydantic models / FastAPI signatures.
- [ ] Auth header / API-key format documented current.

#### `frontend/src/app/sections/page.tsx`
- [ ] If the page describes section-identification capability, it lists every `SectionLabel` member from `docpluck.sections.SectionLabel` (or a curated subset, with the curation criterion documented).
- [ ] Mentions current `SECTIONING_VERSION`.

#### `frontend/src/app/benchmarks/page.tsx`
- [ ] Numbers match `docs/BENCHMARKS.md` (which itself was synced in Section 1.1). If they drifted apart, fix benchmarks page to match the docs.

### 2.4c — Mobile vs desktop content parity (frontend)

A frequent regression: a `<nav>` or CTA gets `className="hidden sm:flex"` for desktop styling, but no mobile counterpart is added → mobile users land on a page with NO way to reach core features. The cleanup pass catches these because they accumulate silently across PRs that each "looked fine on the dev laptop."

- [ ] Grep `frontend/src/components/` and `frontend/src/app/**/*.tsx` for `hidden sm:`, `hidden md:`, `hidden lg:` and `sm:hidden`, `md:hidden`, `lg:hidden`. For every match on a container that holds `<Link>`, `<a>`, `<button>`, or `onClick` handlers, verify a sibling block renders the same items at the opposite breakpoint.
- [ ] `frontend/src/components/app-header.tsx` specifically: the primary `<nav>` MUST be reachable on mobile. If the nav is `hidden sm:flex`, there must be a mobile menu (hamburger button + Sheet/Drawer/Disclosure) in the same component rendering the SAME items, and conditional items (like admin) must appear under the same condition.
- [ ] Footer links not stranded inside `hidden sm:flex` either (mobile users still need to reach API docs, GitHub).
- [ ] `<table>` / wide layouts inside marketing pages: either responsive (`overflow-x-auto`) or restructured for mobile.
- [ ] No primary CTA button width is fixed > 320px on mobile.

If parity gaps are found, REPORT them in the cleanup output (do NOT silently rewrite the mobile UX — that's a design decision the user owns; flag it and let `/docpluck-review` enforce on the next PR).

### 2.4 — App memory

- [ ] `C:\Users\filin\.claude\projects\c--Users-filin-Dropbox-Vibe-MetaScienceTools-PDFextractor\memory\` — check for stale memories

---

## Section 3: Cross-repo consistency

- [ ] Library version (`docpluck/__init__.py:__version__`) == app's git pin (`service/requirements.txt`). MISMATCH = blocker for next deploy.
- [ ] Both `CLAUDE.md` files describe the same two-repo architecture (no contradictions on paths, repo names, visibility, or release flow)
- [ ] If a public library API changed, the app must use the new signature OR pin an older library version (don't silently break)
- [ ] If `SECTIONING_VERSION` bumped, `tests/golden/sections/*.json` files in the library were regenerated (verify with the test: `python -m pytest tests/test_sections_golden.py -q`)
- [ ] Library's current public surface (formats, modules, normalization step count) is REFLECTED on the homepage. Library says PDF + DOCX + HTML? Homepage must too. Library exposes `extract_tables`, `partition_into_sections`, `render_pdf_to_markdown`? Homepage Features grid mentions them, OR PR notes say marketing was deliberately deferred. (Audited in §2.4b above — surface drift here.)
- [ ] Mobile users can reach every desktop-only nav link / CTA. (Audited in §2.4c above — surface drift here.)

---

## Section 4: Output format

```
## Docpluck Cleanup Report — [date]

### Library repo
- Docs synced: [list of files updated, with one-line summary per change]
- Dead files removed: [list]
- TODO items marked complete: [list]
- Issues found requiring manual attention: [list]

### App repo
- Docs synced: [list]
- Dead files removed: [list]
- TODO items marked complete: [list]
- Issues found requiring manual attention: [list]

### Cross-repo
- Library version: X.Y.Z, App pin: X.Y.Z (matched / MISMATCH)
- Architecture consistency: OK / DRIFT FOUND ([details])

### Followup actions for the user
- [list anything cleanup couldn't auto-resolve — broken links, ambiguous deletions, semantic doc rewrites needed]
```

---

## Constraints

- **NEVER delete** `REPLY_FROM_DOCPLUCK_v*.md` or `REQUEST_*.md` files at the library root — these are intentional cross-project communication artifacts. Ask before archiving.
- **NEVER delete** spec/plan files in `docs/superpowers/` — these are historical record.
- **NEVER edit** a shipped spec to retroactively change requirements.
- **ALWAYS read code before editing a doc** that describes the code. Read first, then edit.
- **ALWAYS confirm** before deleting any script with `grep -rn "<script_name>" .` to verify nothing imports it.
- When in doubt, **REPORT for the user** instead of silently deleting/editing.
- Major doc rewrites (>50 lines) should be presented as a diff for user review BEFORE applying.

## Final step: read ~/.claude/skills/_shared/postflight.md and follow it.
