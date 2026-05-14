---
name: docpluck-review
description: Code review specialist for Docpluck PDF extraction library + app. Reviews changes against CLAUDE.md hard rules (never use -layout flag, never use AGPL deps like pymupdf4llm, always normalize U+2212, no broad regex catch-alls in normalize.py per D5 lesson) plus section-identification rules (universal-coverage invariant in partition_into_sections, F0 footnote sentinel preservation, HTML CONTAINER_TAGS skip, PDF boundary-truncation skips heading line not flat char count). Checks normalization pipeline completeness, validates FastAPI endpoint security, reviews Auth.js middleware, checks for hardcoded secrets/URLs, verifies Dockerfile best practices. ALSO reviews frontend mobile/desktop UI parity (any nav/menu/CTA hidden behind `hidden sm:` / `hidden md:` etc. MUST have a mobile equivalent — hamburger, drawer, sheet) and marketing-page capability accuracy (homepage feature list, normalization step counts, supported formats must match current library reality). Use /docpluck-review after making code changes (especially in docpluck/sections/, docpluck/extract_layout.py, docpluck/normalize.py, frontend/src/app/page.tsx, frontend/src/components/app-header.tsx) or before merging.
tags: [python, fastapi, nextjs, pdf, authjs, drizzle, docpluck, review, mobile-parity, marketing-accuracy]
---

## [MANDATORY FIRST ACTION] preflight (do NOT skip, even if orchestrated by /ship)

**Your very first action in this skill, BEFORE reading anything else, is:**

1. Run: `bash ~/.claude/skills/_shared/bin/preflight-filter.sh <this-skill-name>` and print its `🔧 skill-optimize pre-check · ...` heartbeat as your first visible output line.
2. Initialize `~/.claude/skills/_shared/run-meta/<this-skill-name>.json` per `~/.claude/skills/_shared/preflight.md` step 6 (include `phase_start_sha` from `git rev-parse HEAD`).
3. Load `~/.claude/skills/_shared/quality-loop/core.md` into working memory (MUST-level rules gated by /ship).

If you skip these steps, /ship will detect the missing heartbeat and FAIL this phase. Do not proceed to the skill body until preflight has run.

# Docpluck Code Review

You are a code review specialist for Docpluck. Review all changed files against the project's hard rules and best practices.

## Project Location
`C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor`

## Hard Rules (from CLAUDE.md — violations are blockers)

### 1. NEVER use pdftotext with -layout flag
The default mode handles two-column academic papers correctly. The `-layout` flag causes column interleaving.
- **Check:** grep for `-layout` in all Python files
- **Severity:** BLOCKER

### 2. NEVER use AGPL dependencies
pymupdf4llm, PyMuPDF column_boxes(), pymupdf-layout are all AGPL. Incompatible with authenticated service.
- **Check:** grep for `pymupdf4llm`, `column_boxes`, `pymupdf-layout` in imports
- **Check:** Review requirements.txt and package.json for AGPL packages
- **Severity:** BLOCKER

### 3. ALWAYS normalize Unicode MINUS SIGN (U+2212)
PDFs use U+2212 for negative values. Must convert to ASCII hyphen.
- **Check:** If normalize.py is modified, verify U+2212 → `-` replacement exists
- **Severity:** BLOCKER

### 4. NEVER hardcode secrets, API keys, database URLs
- **Check:** grep for connection strings, API keys, tokens in source files
- **Check:** .env.local must be in .gitignore
- **Severity:** BLOCKER

### 5. NEVER strip HTML with greedy `<[^>]+>` regex
The `<` in `p < .001` gets interpreted as HTML tag start, eating content.
- **Check:** If any HTML stripping is added, verify it uses explicit tag names
- **Severity:** BLOCKER

### 6. NEVER use broad character classes in normalization re.sub patterns (D5 lesson, 2026-04-12)
`[^\n]`, `.`, `\S` as catch-all in `re.sub` replacements will match real statistical content and silently destroy data. The D5 bug (`[^\n]{1,20}` eating real p-values) affected ~1,590 PDFs and ~800-1,200 stat lines.
- **Check:** If `normalize.py` is modified, verify ALL `re.sub` patterns use narrow character classes (e.g., `[a-zA-Z]` not `[^\n]`)
- **Check:** Every regex that skips/removes content must have TWO independent safety guards (constrain both the skipped content AND the replacement target)
- **Check:** Every regex must be tested against `stat-value\nsection-number` patterns (the #1 false positive in academic PDFs)
- **Check:** Run `pytest tests/test_d5_normalization_audit.py -v` (153 tests) after any normalization change
- **Severity:** BLOCKER

### 7. NEVER use AGPL alternatives in extract_layout.py (v1.6.0)
pdfplumber (BSD-3) is the only allowed PDF layout extractor. pymupdf4llm, PyMuPDF column_boxes(), and pymupdf-layout are AGPL and incompatible with the authenticated SaaS service.
- **Check:** grep `docpluck/extract_layout.py` and `docpluck/sections/annotators/pdf.py` for `pymupdf4llm`, `column_boxes`, `pymupdf-layout`
- **Severity:** BLOCKER

### 8. Universal-coverage invariant in `partition_into_sections` (v1.6.0)
Sum of section spans MUST equal `len(text)` — every char accounted for.
- **Check:** If `docpluck/sections/core.py` is modified, run `pytest tests/test_sections_core_partition.py tests/test_sections_boundary_truncation.py tests/test_sections_unit_corpus.py -v`
- **Check:** Coalescing in `partition_into_sections` must SKIP `unknown` labels (otherwise heading-derived `unknown` spans merge with prefix unknown and lose the boundary marker — `test_unknown_label_for_unrecognized_strong_heading` will fail)
- **Severity:** BLOCKER

### 9. F0 footnote sentinel preservation (v1.6.0)
The literal sentinel `"\n\f\f\n"` separates body from footnote appendix in `normalize_text(layout=...)` output. `append_footnotes_section` finds this sentinel to extract the footnotes span.
- **Check:** Any normalization step that runs AFTER F0 in `docpluck/normalize.py` must NOT collapse `\f\f` whitespace runs
- **Check:** If you modify any step that touches form-feed or whitespace runs, re-run `pytest tests/test_normalize_f0_footnote_strip.py tests/test_sections_footnote_section.py -v`
- **Severity:** BLOCKER

### 10. HTML annotator must skip non-block containers (v1.6.0)
`docpluck/sections/annotators/html.py` defines `CONTAINER_TAGS = BLOCK_TAGS | {ul, ol, dl, dt, table, tbody, thead, tfoot, tr, th, td, caption}`. The child-skip loop in `annotate_html` MUST use `CONTAINER_TAGS`, NOT `BLOCK_TAGS` — otherwise `<section><ol><li>` reference lists produce duplicated text in `reconstructed_text`.
- **Check:** grep `annotate_html` for `child_name in CONTAINER_TAGS` (correct) vs `child_name in BLOCK_TAGS` (broken)
- **Check:** `pytest tests/test_sections_html_annotator.py::test_annotate_html_no_duplication_through_list_container` must pass
- **Severity:** BLOCKER

### 11. PDF section partitioner: boundary truncation skips first line, not flat char count (v1.6.0)
`partition_into_sections` boundary-aware truncation MUST skip the first line of each span (the heading line itself), NOT a flat character count. The original "skip first 30 chars" approach failed `test_corresponding_author_truncates` because the boundary line sat at offset 27 in the methods section.
- **Check:** in `core.py`, the truncation loop uses `if i == 0: continue` (line-index guard) not `if line_start - s.char_start < N` (char-offset guard)
- **Severity:** BLOCKER

### 12. Mobile / desktop nav parity (frontend, v2.4.18+)
Every navigation link, primary CTA, account control, and admin entry-point that is rendered on desktop MUST also be reachable on mobile. The most common failure: wrapping `<nav>` (or a menu container) in `className="hidden sm:flex"` / `hidden md:flex` / `hidden lg:flex` without a mobile counterpart (hamburger button + drawer / Sheet / collapsible menu). When this happens, mobile users land on the homepage with **no way to reach** `/extract`, `/api-docs`, `/benchmarks`, `/admin`, etc.
- **Check:** grep `frontend/src/components/` and `frontend/src/app/**/layout.tsx` for `hidden sm:`, `hidden md:`, `hidden lg:` on any element containing `<Link>` or `<a>` or `<button>`. For each match, verify there is a sibling block (typically gated by `sm:hidden` / `md:hidden`) that renders the same items as a hamburger / drawer / Sheet / Disclosure menu.
- **Check:** specifically inspect `frontend/src/components/app-header.tsx` — the primary `<nav>` MUST have a mobile-visible counterpart. Account email / Sign In / Sign Out controls also need mobile reachability (an avatar menu is fine; complete invisibility is not).
- **Check:** any item that appears conditionally on desktop (e.g., `{isAdmin && <Link href="/admin">…)`) MUST appear in the mobile menu under the same condition.
- **Check:** primary call-to-action buttons in hero / CTA sections must not rely on horizontal layout that overflows on 360px-wide viewports — verify with the responsive emulator OR by reading the CSS (no fixed widths > 320px on the CTA itself).
- **Severity:** BLOCKER for full nav being mobile-invisible (regression in feature reachability for ~50% of traffic). WARN for individual secondary links missing from a present mobile menu.

### 13. Marketing / landing-page accuracy must reflect current library capabilities (frontend, v2.4.18+)
The homepage (`frontend/src/app/page.tsx`) and any "About" / "Features" / "How it works" page is the public face of Docpluck. It MUST stay in lock-step with the library's actual public surface, not freeze at v1.x assumptions.
- **Check:** when this PR touches `docpluck/__init__.py:__all__`, `docpluck/normalize.py:NORMALIZATION_VERSION`, `pyproject.toml [project.optional-dependencies]`, or any new top-level module (`docpluck.sections`, `docpluck.tables`, `docpluck.figures`, `docpluck.extract_layout`, `docpluck.extract_docx`, `docpluck.extract_html`, `docpluck.render`), verify `frontend/src/app/page.tsx` still tells the truth. Specifically:
  - Hero copy / `<title>` / meta description: do they still describe the product as "PDF only" when DOCX + HTML are now supported? (Should mention all three.)
  - Hard-coded counts ("14 normalization steps", "16 normalization steps", "29/29 verified passages"): do they still match `NORMALIZATION_VERSION` and the current corpus size? Either update the number or replace with a code-derived count.
  - "Choose your level" / pipeline-step cards: list of steps must include everything currently in `normalize.py` (W0, R2, R3, A7, F0 in addition to S0–S9, A1–A6, A3a, A3b).
  - Major-feature absence: if a public capability shipped (section identification, table extraction via Camelot, figure extraction, layout-aware footnote stripping, render-to-markdown), the homepage Features grid should mention it OR a deliberate "marketing decision to hold back" note should exist in the PR description.
  - Hard-coded URLs in code samples (`https://docpluck.vercel.app/api/extract`, etc.) must match the actual production URL — prefer `process.env.NEXT_PUBLIC_API_BASE` or a constant in `frontend/src/lib/`.
- **Check:** the same audit applies to `frontend/src/app/about-normalization/page.tsx`, `frontend/src/app/api-docs/page.tsx`, `frontend/src/app/sections/page.tsx`, and `frontend/src/app/benchmarks/page.tsx` whenever the underlying library surface they describe changed.
- **Severity:** WARN (non-blocker) on isolated stale numbers; BLOCKER if the homepage actively contradicts shipped functionality (e.g., claims "PDF-only" while DOCX/HTML endpoints are live, or omits a feature gated behind a deploy that already happened).

### 14. Base-UI primitive component-hierarchy + polymorphism rules (frontend, v2.4.24+)
Base UI (`@base-ui-components/react`, used through `frontend/src/components/ui/*.tsx`) eager-renders portal children and asserts component-hierarchy invariants on mount. A violation produces a cryptic numeric production error (e.g. `Base UI error #31`) that crashes EVERY page rendering the offending tree, even before the user opens the menu. The dev build often masks this; only `next build` + a real browser hit surfaces it. Two recurring footguns from v2.4.24 incident:

**14a — Hierarchy violation (Base UI error #31).** A primitive whose name implies it labels / belongs to a parent group MUST be wrapped in that parent. Specifically for the `DropdownMenu` family in `frontend/src/components/ui/dropdown-menu.tsx`:
- `<DropdownMenuLabel>` (= `MenuPrimitive.GroupLabel`) MUST be inside `<DropdownMenuGroup>` (= `MenuPrimitive.Group`).
- `<DropdownMenuRadioItem>` MUST be inside `<DropdownMenuRadioGroup>`.
- `<DropdownMenuSubTrigger>` and `<DropdownMenuSubContent>` MUST be inside `<DropdownMenuSub>`.
- The same rule applies to `Combobox`, `Select`, `Tabs`, `Accordion`, and any other base-ui primitive with a `Group` / `Root` parent.
- **Check:** grep `frontend/src/` for `<DropdownMenuLabel`, `<DropdownMenuRadioItem`, `<DropdownMenuSubTrigger`, `<DropdownMenuSubContent`. For each match, walk OUT (not in) until you find a wrapping `<DropdownMenuGroup` / `<DropdownMenuRadioGroup` / `<DropdownMenuSub`. If absent within the same component, BLOCKER.
- **Severity:** BLOCKER (production-crashing).

**14b — Polymorphic `render={<Link>}` patterns on base-ui items.** Passing a Next.js `<Link>` (or any element form) to base-ui's `render` prop on `Menu.Item` / similar primitives crashed the page on click in production (the element-form clone path interacts badly with Next.js Link's ref forwarding). For navigation inside a base-ui menu / popover, use `onClick={() => router.push(href)}` with a `useRouter()` hook instead.
- **Check:** grep `frontend/src/` for `render={<Link` and `render={<a `. Each match is at minimum a WARN; on `MenuPrimitive.Item` / `DropdownMenuItem` / similar interactive primitives, BLOCKER.
- **Check:** when reviewing a new menu/dropdown component, prefer `onClick` + `router.push` over polymorphic `render` for navigation.
- **Severity:** BLOCKER on interactive menu items; WARN elsewhere.

**14c — Prefer vanilla disclosure for trivial mobile menus.** `MobileNav` and similar 3-to-6-item disclosures don't need base-ui's Portal / Positioner / Popup / Group machinery. A plain `useState` + outside-click + Escape pattern has zero hierarchy constraints, zero SSR Portal quirks, and zero base-ui dependency. Reach for base-ui only when the surface needs nested submenus, type-ahead selection, virtualization, or accessibility primitives that would be expensive to reproduce.
- **Check:** if a base-ui primitive is being used for a 3-to-6-item flat menu, ask the author why. WARN, not BLOCKER.

### 15a. Content-fidelity rules surfaced by Phase-5d AI verify (v2.4.29+, multi-paper)

The 2026-05-14 4-paper AI-verify run (xiao, amj_1, amle_1, ieee_access_2 against AI gold extractions of the source PDFs) surfaced content-fidelity defect classes the prior verifier suite is blind to. Each class maps to a specific code-review check. **Ground truth for any verification cited in this section is the AI multimodal read of the source PDF, NOT pdftotext / NOT Camelot** (per CLAUDE.md's ground-truth hard rule and memory `feedback_ground_truth_is_ai_not_pdftotext`).

**15a.1 — Unicode→ASCII normalization may touch ONLY U+2212.** Per CLAUDE.md L004, the only documented Unicode-to-ASCII conversion in `docpluck/normalize.py` is `U+2212 (MINUS) → "-"`. Any new substitution that touches Greek letters (β, δ, γ, σ, μ, τ, ε, ω, π and their uppercase forms), comparison operators (≥, ≤, ×, ÷, ±, ·), or thousands-separator commas in integers (`1,675 → 1675`) is content corruption. Real-world Phase-5d finding (ieee_access_2 v2.4.28): `β → "beta"`, `δ → "delta"`, `γ KEPT` (inconsistent), `× → "x"`, `≥/≤ → ">="/"<="`. Real-world Phase-5d finding (amle_1 v2.4.28): all comma-thousands stripped throughout body.
- **Check:** grep `docpluck/normalize.py` and `docpluck/render.py` for `.replace(` calls. Each replacement that takes a non-ASCII character on the left MUST be either:
  (a) The documented U+2212 → `-` (S5).
  (b) A soft-hyphen / line-wrap rejoin (S3, S4).
  (c) A smart-quote / fancy-quote / ligature normalization that preserves semantic content.
  (d) Explicitly documented and added to CLAUDE.md as a new normalization step.
- **Check:** grep `docpluck/normalize.py` for any regex of the form `r"(\d+),(\d{3})"` or `re.sub(r"(\d),(\d{3})", ...)`. Comma-thousands stripping is a content corruption (1,675 reads as 1675 = different number); BLOCKER.
- **Check:** grep `docpluck/` for `.replace("β"`, `.replace("δ"`, `.replace("γ"`, `.replace("σ"`, `.replace("μ"`, `.replace("≥"`, `.replace("≤"`, `.replace("×"`, `re.sub.*[α-ωΑ-Ω]`. Each is BLOCKER unless documented as a deliberate normalization with a published rationale.
- **Severity:** BLOCKER.

**15a.2 — Table cell emission must preserve cell boundaries (no concatenation, no phantom columns).** Real-world Phase-5d findings: ieee_access_2 Table 1 emits `<td>ParameterDescriptionReference Range/Value</td>` (three logical columns concatenated); amle_1 Table 13 emits `<td>Michigan State6Harvard University</td>` (3 logical cells fused); xiao Tables 1/2/6 emit phantom `<th></th>` empty cells between non-empty headers (Camelot stream-flavor whitespace-gap mis-segmentation); amj_1 Table 4 emits an essentially empty `<table>` while the actual matrix data is dumped to body stream.
- **Check:** when reviewing changes in `docpluck/tables/cell_cleaning.py`, `docpluck/tables/render_html.py`, `docpluck/tables/*.py`, or `docpluck/extract_structured.py`, run a real-PDF regression on the 4 canonical papers (xiao, amj_1, amle_1, ieee_access_2) and `grep -nE '<td>[A-Za-z]{6,}[A-Z][a-z]+' tmp/*_v<version>.md` to detect concatenation; `grep -cE '<th>[^<]+</th>\s*<th></th>\s*<th>[^<]+</th>' tmp/*_v<version>.md` to detect phantom columns.
- **Check:** if `docpluck/tables/extract.py` (Camelot wrapper) is touched, verify Camelot's `lattice` flavor is still preferred over `stream` for ruled tables (stream over-segments whitespace gaps) — and that the fallback chain doesn't silently drop to a flavor that produces phantom columns.
- **Check:** any new code that emits a `<table>` element MUST guarantee `<td>` boundaries between every pair of source cells; concatenation as a "cleanup" of empty cells is a BLOCKER.
- **Severity:** BLOCKER.

**15a.3 — Caption text must not be welded into thead.** Real-world Phase-5d finding (amle_1 Tables 3/4/5/7/8): `<th>TABLE 4<br>Most Cited Sources in General Management Textbooks<br>Source</th>` — the table caption + table number are jammed into the first thead cell instead of a separate `<caption>` element.
- **Check:** grep `docpluck/tables/render_html.py` and `docpluck/extract_structured.py` for the logic that places `### Table N` headings AND emits the `<table>`. The caption should be either above the `<table>` (as `*Table N. Caption*` italic line) OR inside `<caption>...</caption>` — never inside `<th>`.
- **Check:** `grep -nE '<th>(TABLE|Table)\s+\d+' tmp/*_v<version>.md` against the canonical-4 rendered output; any match is a BLOCKER.
- **Severity:** BLOCKER.

**15a.4 — Never fabricate a `## Introduction` heading if the source has none.** Real-world Phase-5d finding (xiao v2.4.28): `## Introduction` injected at .md line 19 even though the source PDF has no such heading (it goes directly from Keywords to body prose).
- **Check:** when reviewing changes in `docpluck/sections/annotators/text.py`, `docpluck/sections/taxonomy.py`, `docpluck/sections/core.py`, or `docpluck/render.py`, search for any unconditional `## Introduction` insertion. Heading must be detected from the source, not inserted as a fallback.
- **Check:** grep `docpluck/` for hard-coded strings like `"## Introduction"`, `"Introduction\n"`, `f"## {default_intro}"`. Each occurrence must be in a conditional path that detected the heading in the source.
- **Severity:** BLOCKER.

**15a.5 — ALL-CAPS section promotion must consume preceding Roman-numeral marker.** Real-world Phase-5d finding (ieee_access_2 v2.4.28): the cycle-11 ALL-CAPS promoter promoted `INTRODUCTION` → `## INTRODUCTION` but left orphan `I.` on the prior line. Same for `II.` / `III.` / `IV.`. The promoter must also handle the `V.: SUPPLEMENTARY INDEX` (colon-after-numeral) variant.
- **Check:** when reviewing changes in `docpluck/render.py::_promote_all_caps_section` (or equivalent), verify the regex consumes BOTH `^[IVX]{1,4}\.\s*\n` immediately above the promoted heading AND `^[IVX]{1,4}\.:?\s+[A-Z]` inline-prefix form.
- **Check:** run on the canonical-4 corpus, then `grep -nE '^[IVX]{1,4}\.\s*$' tmp/*_v<version>.md` — any match in the line immediately above a `## ` heading is a BLOCKER.
- **Severity:** BLOCKER.

**15a.6 — Endmatter (Appendix / Bios / Notes / ORCID) must not leak into References.** Real-world Phase-5d finding (amj_1 v2.4.28): Appendix A is fractured. Task Processes items 3-4 + Meta-Processes block + author bios all appear INSIDE `## REFERENCES` before the `## APPENDIX A` heading is emitted. Real-world Phase-5d finding (xiao v2.4.28): `Notes`, `ORCID`, `Authorship declaration`, `Disclosure statement`, `Additional information` appear as flat body text instead of `##` headings.
- **Check:** when reviewing changes in `docpluck/sections/`, verify the endmatter taxonomy detects `APPENDIX [A-Z]`, `Appendix [A-Z]`, `Author biographies`, `Notes`, `ORCID`, `Funding`, `Disclosure statement`, `Authorship declaration`, `Additional information`, and routes each to its own top-level section.
- **Check:** verify biographical-prose heuristic exists — patterns like `<Name> (<email>) is (assistant|associate|emeritus|full) (professor|student) of` should NOT appear inside a `## REFERENCES` block.
- **Severity:** BLOCKER for cross-section leak (content under wrong heading); WARN for flat-body when a `## ` heading was expected.

**15a.7 — Figure captions must not double-emit with mismatched normalization.** Real-world Phase-5d finding (ieee_access_2 v2.4.28): 37 figure captions emitted twice — once interleaved in body using ASCII normalization (`beta`, `>=`), once in dedicated `## Figures` section using Unicode (`β`, `≥`).
- **Check:** when reviewing changes in `docpluck/render.py` figure emission, verify each figure caption is emitted exactly once. If both inline + trailing-section are intentional, both must use the same normalization (and a comment in the source must justify the duplication).
- **Severity:** WARN if duplication is intentional and consistent; BLOCKER if normalization differs between the two emissions.

### 15. Corpus render verifier must pass on changes to render / extract / tables (v2.3.0+)
The 26-paper baseline in `docs/superpowers/plans/spot-checks/splice-spike/outputs[-new]/` is the regression line for `render_pdf_to_markdown`. Any change to `docpluck/render.py`, `docpluck/extract_structured.py`, `docpluck/extract.py`, `docpluck/tables/*.py`, or `docpluck/normalize.py` MUST be verified.
- **Check:** When any of those files are modified, run `python scripts/verify_corpus.py` (~8-12 min) before approving.
- **Expected:** `26 / 26 PASS`. Any FAIL is a regression and blocks the review.
- **Fast path** (for single-file changes touching only one rendering aspect): run `pytest tests/test_corpus_smoke.py -v` (~45s) — 3 representative papers (APA, AMA, JESP) covering Bug 3 figure positioning, lattice artifact filter, and appendix fallback.
- **Severity:** BLOCKER for `render.py` / `extract_structured.py` / `tables/`; WARN for other touches (where the smoke subset suffices).

## Review Checklist

### Python Service (`service/`)

- [ ] No `-layout` flag in pdftotext calls
- [ ] No AGPL imports
- [ ] normalize.py handles U+2212, U+2013, U+2014, U+2010, U+2011
- [ ] All 16 normalization steps present (S0-S9, A1-A6, A3a, A3b)
- [ ] D5 regression test suite passes (153 tests in `test_d5_normalization_audit.py`)
- [ ] Quality scoring uses common-word ratio threshold (0.02)
- [ ] SMP recovery maps Mathematical Italic chars to ASCII
- [ ] Dockerfile uses `python:3.12-slim` base with `poppler-utils`
- [ ] No hardcoded URLs or secrets
- [ ] FastAPI endpoints validate file type and size
- [ ] Temp files cleaned up in `finally` blocks

### Frontend (`frontend/`)

- [ ] Auth.js middleware protects all routes except /login and /api/auth
- [ ] Rate limiting checks daily usage before extraction
- [ ] API route validates session before forwarding to service
- [ ] No secrets in client-side code
- [ ] Environment variables used for all external URLs
- [ ] Drizzle schema matches ARCHITECTURE.md

### Frontend UI parity — mobile vs desktop (hard rule 12)

- [ ] `frontend/src/components/app-header.tsx` exposes the full nav on mobile (no `hidden sm:flex` / `hidden md:flex` on the only `<nav>`). If desktop has a horizontal bar, mobile MUST have a hamburger / Sheet / drawer rendering the SAME items in the SAME order.
- [ ] Every `<Link>` / `<a>` / `<button>` rendered conditionally on desktop (e.g., admin-only) is rendered under the same condition in the mobile menu.
- [ ] Account controls (email display, Sign In, Sign Out) are reachable on mobile — either inline in the header at xs viewports or inside the mobile menu / avatar dropdown.
- [ ] Footer links are not stranded inside `hidden sm:*` either.
- [ ] No element with a click handler / link is hidden on mobile without a documented replacement path. Document the replacement path in the PR description if non-obvious.
- [ ] Run a viewport-emulator pass at 360x800 (Pixel-class) and 390x844 (iPhone-class) AND read the JSX — both, because Tailwind classes can hide things the emulator misses if the emulator was opened before a code change.
- [ ] **Base-UI primitive hierarchy audit (rule 14a):** grep `frontend/src/` for `<DropdownMenuLabel`, `<DropdownMenuRadioItem`, `<DropdownMenuSubTrigger`, `<DropdownMenuSubContent`. Each match must have an enclosing `<DropdownMenuGroup` / `<DropdownMenuRadioGroup` / `<DropdownMenuSub` in the same JSX subtree. Missing wrapper = BLOCKER (production Base UI error #N crashes every page rendering this component).
- [ ] **Polymorphic-render audit (rule 14b):** grep `frontend/src/` for `render={<Link` and `render={<a `. Inside any base-ui interactive primitive (MenuPrimitive.Item / DropdownMenuItem / similar) = BLOCKER. Outside = WARN. Replace with `onClick={() => router.push(href)}`.
- [ ] **Trivial-menu vanilla-disclosure check (rule 14c):** if a new base-ui DropdownMenu / Popover is being added for a 3-to-6-item flat menu, surface as WARN — vanilla `useState` + outside-click is simpler and has zero base-ui hierarchy/Portal/SSR risk.
- [ ] **Production smoke required:** for any change touching `app-header.tsx`, `mobile-nav.tsx`, or any other component using base-ui primitives, the PR description MUST confirm a `next build` ran AND a real browser hit at mobile viewport (or the deployed preview URL) opened the menu without console errors. `next build` succeeding alone is NOT sufficient — base-ui hierarchy errors only fire at component-mount runtime.

### Marketing / landing-page accuracy (hard rule 13)

- [ ] If this PR touches `docpluck/__init__.py`, `docpluck/normalize.py`, `pyproject.toml`, OR any new `docpluck/*` module, the homepage (`frontend/src/app/page.tsx`) was re-read and still tells the truth.
- [ ] Homepage hero / meta description mentions every input format the library supports today (PDF + DOCX + HTML, not just PDF).
- [ ] Homepage Features grid mentions section identification, table extraction (Camelot), figure extraction, layout-aware footnote stripping, and render-to-markdown — OR the PR description explains why each absence is intentional.
- [ ] Hard-coded numbers ("14 normalization steps", verified-passage counts, average extraction time) match current reality. Either updated or derived from a constant (e.g., `NORMALIZATION_VERSION`).
- [ ] "Choose your level" / "Normalization" card list contains all currently-applied steps (S0–S9, A1–A6, A3a, A3b, W0, R2, R3, A7, F0 — confirm against `docpluck/normalize.py`).
- [ ] Code samples on the homepage and in `frontend/src/app/api-docs/` show URLs and parameter names that match what `service/app/main.py` actually accepts today.
- [ ] `frontend/src/app/about-normalization/`, `frontend/src/app/sections/`, `frontend/src/app/benchmarks/` re-checked if their underlying library surface shifted.

### Documentation

- [ ] Changes reflected in CLAUDE.md if architectural
- [ ] LESSONS.md updated if a new pitfall was discovered
- [ ] TODO.md updated if features were added/completed

## Output Format

```
## Docpluck Code Review

### Blockers
- [BLOCKER] description (file:line)

### Warnings
- [WARN] description (file:line)

### Suggestions
- [SUGGEST] description

### Summary
X blockers, Y warnings, Z suggestions
Verdict: APPROVE / REQUEST CHANGES
```

## Final step: read ~/.claude/skills/_shared/postflight.md and follow it.
