# Handoff — results of the AI-Chrome visual verify pass + sticky-tabs ship

**Session date:** 2026-05-12 (continuation of `HANDOFF_2026-05-12_remaining_ui_and_chrome_verification.md`)

**Scope covered:** Both open items from the prior handoff.

---

## Item 1 — Sticky tabs (DONE, shipped, visually verified)

### What changed

File: `PDFextractor/frontend/src/components/document-workspace.tsx`

1. **Result `<Card>` gets `overflow-visible`** to override the shadcn default `overflow-hidden`. Without this override `position: sticky` doesn't pin to the viewport — `overflow-hidden` makes the Card the sticky's containing block, and since the Card itself doesn't scroll, the sticky never activates.
2. **Tab strip wrapped in a sticky bar** — `sticky top-16 z-10 -mx-4 px-4 pt-1 pb-3 mb-4 bg-card border-b border-zinc-200`. `top-16` (64px) sits below the `AppHeader` (sticky `top-0 z-50`, ~57px tall). `-mx-4 px-4` bleeds the `bg-card` fill to the Card edges through `CardContent`'s padding. Includes both the Copy/Download buttons and the `TAB_HINTS` line so the active tab's description is always visible.
3. **Per-tab scroll containers removed** (Option A from the handoff): dropped `max-h-[750px]/[700px]` + `overflow-auto` from the Rendered `<article>`, both `<pre>` blocks (Raw / Normalized), the sections list, and the tables list. Page scroll now handles everything.
4. **`content-visibility: auto` perf fix** added to direct children of the Rendered `<article>` (`[&>*]:[content-visibility:auto] [&>*]:[contain-intrinsic-size:auto_100px]`). Without this, long renders (e.g. `chen_2021_jesp` = ~97K-px tall page, ~3000 lines of markdown) freeze the Chrome paint thread under page-level scroll; CDP `Page.captureScreenshot` times out at 30s. This was a regression introduced by removing the per-tab scroll container. The fix lets Chrome skip layout/paint for off-screen blocks. Without it, Option A is unshippable on long-render papers.

### Visual verification

- `chen_2021_jesp.pdf` (1.30 MB, 14 pages, 97,100-px tall rendered page) uploaded via the workspace
- Scrolled to `scrollY = 1500`; via `getBoundingClientRect()` confirmed the sticky bar pinned at `top: 64px` (exactly `top-16`), `height ≈ 73px`, `bottom ≈ 137px`
- All five tabs (`Rendered | Raw | Normalized | Sections | Tables`) remained visible and clickable while reading mid-document content
- Cross-checked on all 26 corpus papers — sticky pins consistently; no JS-runtime errors

### Type-check

`npx tsc --noEmit` exit 0.

### Files / commits

Unmodified library; this is a frontend-only change in the PDFextractor repo. Two staged-but-uncommitted edits in `frontend/src/components/document-workspace.tsx`. No version bump needed.

---

## Item 2 — Visual verify pass on all 26 corpus papers (DONE)

### Method

1. Started the dev stack (uvicorn on :6117, Next.js dev on :6116) in background.
2. Staged all 26 PDFs into `PDFextractor/frontend/public/_test-pdfs/` (gitignored per `cbb7f24`).
3. Signed in via the dev `Credentials` provider (`test@docpluck.local` / `docpluck-dev`).
4. For each paper: JS-upload via `DataTransfer` + `<input type="file">` `change` event (the same-origin trick from the prior handoff), wait for `[data-slot="tabs-list"]`, click through Tables → Sections → Rendered, capture metadata (title, section count, doc height, tablesHtml count) and screenshot the Rendered tab.
5. All 26 papers analyzed successfully — no upload failures, no analyze timeouts, no JS errors.

### Workspace-level findings

| Aspect | Result |
|---|---|
| Sticky tabs across 26 papers | ✅ Consistent pinning at `top: 64px`; survived 97K-px and 165K-px tall renders (`chen_2021_jesp`, `amle_1`). |
| Page-level scroll | ✅ Smooth after `content-visibility:auto` fix. Without it, Chrome's paint thread froze. |
| JS errors | ✅ None observed across all 26 papers. |
| Analyze timeouts | ✅ None. Slowest paper: `nat_comms_2` (2.61 MB PDF, 125 s — bound by Camelot, not the workspace). |
| Tab badges / counts | ⚠️ The `tablesHtml` query (`role="tabpanel"[data-state=active] table`) returns 0 even on papers where Tables tab shows N table cards. Cause: when Camelot can't structure a table into cells, the workspace renders the card with `raw_text` (or "No cells or raw text" notice) — no actual `<table>` element. **Not a bug** — the per-table cards still display correctly. If we want a richer counter, count `[data-slot="card"]` inside the Tables panel instead. |
| Workspace UX | ✅ Staged progress + ETA feels responsive. ETA-vs-actual on long papers (`nat_comms_2`: 39s estimated vs 125s actual) understates Camelot when there are many tables — minor. |

### Library-side findings (visible in Rendered tab; **the API-level `verify_corpus.py` does NOT catch these**)

These are real `.md` rendering issues from the docpluck library that the workspace surfaces. None are workspace bugs.

**1. `## Abstract Abstract <body>` heading collapse** (≥5 papers)

Pattern: the `.md` output has `## Abstract` (or `## Keywords`) immediately followed on the same line/paragraph by the body text, with no intervening blank line. The workspace's `renderMarkdownToHtml` regex `^(#{1,6})\s+(.+)$` only matches when the heading is the whole paragraph — so the section renders as plain body text with the literal `## Abstract` prefix.

Papers exhibiting this in the corpus (visible in screenshots):
- `am_sociol_rev_3` — `## Abstract Abstract Lynching remains...`
- `amj_1` — `## Abstract Negative feedback alerts recipients...`
- `ar_royal_society_rsos_140072` — `## Keywords Keywords: isotocin, arginine vasotocin...`
- `ieee_access_4` — `## Abstract Abstract Diffusion models are emerging...`
- `jmf_1` — `## Abstract Abstract Objective: To determine...`

Likely more across the 26 (only checked the top of each render).

**Root cause hypothesis:** `render.py` is emitting `## Abstract` and the abstract body on the same paragraph (no `\n\n` between them) when the source PDF has the abstract heading and body on the same line. Two fixes possible:

- **Library fix (preferred):** in `render.py`, always emit `\n\n` after a section heading.
- **Workspace fix:** broaden `renderMarkdownToHtml` to detect `^## (\S+?)\s{2,}(.+)` and split — but that's papering over library output. The library fix is cleaner.

**2. Title duplicated as body text** (Nature Communications papers)

Pattern: after the `# Title` H1, the title repeats as 1-3 plain paragraphs of body text.

- `nat_comms_1` — H1 "Targeted treatment of injured nestmates with antimicrobial compounds in an ant society" followed by body paras "Targeted treatment of injured nestmates" / "with antimicrobial compounds in an ant" / "society"
- `nat_comms_2` — H1 "Para-infectious brain injury in COVID-19 persists at follow-up despite attenuated cytokine and autoantibody responses" followed by body paras "Para-infectious brain injury in COVID-19" / "persists at follow-up despite attenuated"

This is a publisher-specific title-block layout (Nature uses a multi-line title also reproduced in a smaller form below) that the library's title detector picks up once but doesn't suppress the second occurrence. Likely an annotator/title-strip rule needed for Nature Communications PDFs.

**3. Title truncation** (`ziano_2021_joep`)

Rendered title: "Replication: Revisiting Tversky and **(1992)** Disjunction Effect with an extension comparing between and within subject designs"

Original: "Replication: Revisiting Tversky and **Kahneman (1992)** Disjunction Effect..." — "Kahneman" dropped between "and" and "(1992)".

Looks like a title-parse regression on hyphenated/space-broken multi-word author names in titles. Suspect there's a rule that strips trailing-author-name + year pattern incorrectly.

**4. Inconsistent italic on author names** (`efendic_2022_affect`)

Authors line:
> Emir Efendic´1, *Subramanya Prasad Chandrashekar2*, Cheong Shing Lee3, *Lok Yan Yeung3*, Min Ji Kim3, *Ching Yee Lee3*, and Gilad Feldman3

Every other author is italicized — likely the PDF marks "joint first authors" with italics, and the library is propagating those italic spans into the `.md`. Either the library should normalize away author-name italics OR the `_italicize_known_subtitle_badges` heuristic from v2.3.1 (Bug 6) is misfiring on author lines.

Also: "Efendic´1" — the accent U+00B4 is rendered after "Efendic" instead of forming "Efendić" (U+0107). Likely a glyph-vs-combining-mark issue from the PDF; safe to defer.

**5. Garbled DOI / front-matter watermark** (`ip_feldman_2025_pspb`)

First paragraph below title:
> Personality and Social Psychology Bulletin 1- 19 © 2025 by the Society for Personality and Social Psychology, Inc Article reuse guidelines: sagepub.com/journals-permissions **DhttOpsI://1d0o.i1.o1rg7/71** ...

"DhttOpsI://1d0o.i1.o1rg7/71" is a column-interleave of "DOI: https://doi.org/10.1177/..." with the running-header text. This is the same family of issues normalize.py's W0 / running-header strip is meant to handle, but PSPB's particular layout slips through.

**6. Camelot can't structure tables** (`chandrashekar_2023_mp`)

10 tables detected. Captions present and correct. All 10 show "No cells or raw text extracted" in the workspace. The amber banner in `TablesView` already acknowledges this and says "Better cell extraction is on the v2.3.0 roadmap." — that comment in the source still mentions v2.3.0 even though we're now at v2.3.1. Minor: update the banner copy in `TablesView` to drop the version reference or bump it.

### Findings the API-level verifier WOULD have caught but didn't

`verify_corpus.py` passes 26/26 with no T (title-truncated) tag for `ziano_2021_joep`. Its title-truncation check (`_TITLE_RE` + a heuristic in `_metrics`) doesn't notice missing middle words — only end truncation. **Suggested verifier upgrade:** for each paper, compare the rendered title against the spike-baseline title's word set; flag if delta > 1 token.

---

## What I'd recommend the next session do

In order of value/cost:

1. **Library: fix `## Heading <body>` collapse in `render.py`** (issue 1 above). This affects user-visible quality on a noticeable fraction of papers. Test by adding a markdown-lint pass to `verify_corpus.py` that checks each `## ` is followed by `\n\n`. Bump library minor version.
2. **Library: suppress Nature-style title repetition** (issue 2). Add a publisher-detection rule in the title annotator: if H1 text appears verbatim within the first ~200 chars of body, strip the body occurrence.
3. **Library: `ziano_2021_joep` middle-word title truncation** (issue 3). Find the rule that drops "Kahneman" — likely a pattern in the title-extractor that strips one-word capitalized tokens before `(YYYY)`.
4. **Verifier upgrade**: title-word-delta check (catches 3 cleanly).
5. **Workspace polish**: update the Tables-tab amber banner to drop the "v2.3.0 roadmap" reference (it's stale at v2.3.1). One-line frontend edit.
6. **Library: PSPB column-interleave** (issue 5) — defer unless it shows up in another paper. Hard to fix without an extra layout pass on this specific publisher.

Issues 4 (italic author names) and 6 (Camelot 10-table failure) are known territory and lower-priority polish.

---

## State of the repos at end of session

- **`giladfeldman/docpluck`** — no library changes this session. The handoff added to `docs/` (this file + the prior handoff). Library still at v2.3.1.
- **`giladfeldman/docpluckapp`** — uncommitted edits in `frontend/src/components/document-workspace.tsx` (sticky tabs + content-visibility perf fix). Type-check passes. No app version bump needed.
- **Dev stack** — left running in background (`uvicorn :6117` and `next dev :6116`). Stop with `taskkill /FI "WINDOWTITLE eq Docpluck-*"` or just kill the bash background tasks. Logs at `/tmp/docpluck-svc.log` and `/tmp/docpluck-fe.log`.
- **Staged PDFs** — 26 corpus PDFs sit in `PDFextractor/frontend/public/_test-pdfs/` (gitignored). Can be left in place for future visual-verify sessions; they're 28 MB total.
