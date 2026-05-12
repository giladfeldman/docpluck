# Handoff — UI polish + Chrome-MCP visual verification (post-v2.3.1)

**For:** A fresh session picking up after **library v2.3.1** and **PDFextractor master @ 5f457ae** ship.

**Status at handoff:** Everything in [`HANDOFF_2026-05-11_visual_review_findings.md`](./HANDOFF_2026-05-11_visual_review_findings.md) is closed except the two items below, both of which need infrastructure (a running dev stack and Chrome MCP) that wasn't available during the v2.3.x sessions.

```
docpluck library  → tagged v2.3.1, pushed to giladfeldman/docpluck
PDFextractor app  → master @ 5f457ae, pin @v2.3.1, pushed
Corpus verifier   → 26/26 PASS across 9 journal styles
Test suites       → 323 unit + 22 v2.3.1 + 48 smoke fixtures all green
                    (verified 917 passed / 18 skipped at 2026-05-12 close-out)
```

## Close-out audit (2026-05-12)

A close-out audit of this thread verified:

  - ✅ **Library v2.3.1** is shipped, tagged, and tested (`pytest tests/` → 917 passed / 18 skipped / 0 failures, 24 min run).
  - ✅ **App pin** is bumped to v2.3.1 in `PDFextractor/service/requirements.txt`.
  - ✅ **Open Item 2** (Chrome-MCP visual review) is fully documented below — no work attempted.
  - ⚠️ **Open Item 1** (sticky tabs) — implementation IS in `PDFextractor/frontend/src/components/document-workspace.tsx` working tree but NOT committed. Awaiting browser verification + commit. See item 1 below for the specific verification steps and the proposed commit message.

The two open items can be tackled in either order. They're independent. Both are explicitly low-priority polish — the library is production-ready as-is.

---

## Open item 1 — Sticky tabs while scrolling the Rendered view  ⚠️ IMPLEMENTED-BUT-UNCOMMITTED

**Status (updated 2026-05-12 close-out):** The fix is **already written in the PDFextractor working tree** and matches Option A below — Card gets `overflow-visible`, `TabsList` wrapped in a `sticky top-16 z-10` container, per-tab `max-h-[700-750px] overflow-auto` removed from rendered/raw/normalized/sections/tables panes so the whole page scrolls naturally. Run `cd PDFextractor && git diff frontend/src/components/document-workspace.tsx` to see it. Outstanding:

  1. **Manual browser verification not yet performed** — the change has not been opened in a browser. Run `start_app.bat`, upload a long paper (`chen_2021_jesp.pdf`), scroll the Rendered tab, and confirm tab strip stays pinned + clickable. Test in Chrome AND Firefox (Safari has known quirks with sticky inside `overflow-y: auto` ancestors).
  2. **Commit + push not done.** Once verified, commit message proposal: `fix(workspace): pin tab strip on scroll for long Rendered views (closes handoff item 1)`. No app-version bump needed (pure UX tweak).
  3. **No library change involved.**

If verification reveals a problem (e.g. the sticky pin overlaps the page header or breaks Safari), revert the working-tree change with `git restore frontend/src/components/document-workspace.tsx` and pick Option B from the original direction below.

---

**Original direction** (kept for reference / Option B if Option A fails verification):

**Symptom:** On long-render papers (e.g. `chen_2021_jesp` rendered = 180 KB of markdown, ~3000 lines), the user scrolls down the Rendered tab to read a Discussion section near the bottom. The five tab buttons (`Rendered | Raw | Normalized | Sections | Tables`) scroll out of view with the rest of the page header, so switching tabs requires scrolling all the way back to the top.

**Affected file:** `PDFextractor/frontend/src/components/document-workspace.tsx`

**Fix direction:**

1. Wrap the `<TabsList>` (the row of five tab buttons) in a `position: sticky` container. The component uses `shadcn/ui`'s `<Tabs>` primitive — it's `<TabsList>` inside `<Tabs>` directly.

2. The tricky part: `position: sticky` only works when **every ancestor in the scroll chain has `overflow: visible`**. The current workspace has the tab content in its own scroll container, which defeats sticky positioning. Options:

   - **Option A (preferred — already implemented in working tree):** lift the scroll out of the tab content. Let the whole page scroll naturally, and make the `<TabsList>` `sticky top-16 z-10 bg-card border-b`. (top-16 pins below the 56-px AppHeader; matches GitHub's file viewer pattern.)
   - **Option B (fallback if A breaks Safari):** keep per-tab scrolling but add a fixed-position floating tab strip that mirrors the active tab's state. More code, but preserves the current "tab content scrolls inside a fixed-height viewport" pattern.

3. **Don't forget the upload form / status banner.** The current top of the workspace shows an upload-status banner during the long Camelot pass. When the user scrolls, that banner should either also stay visible (sticky) OR fold away cleanly. Pick one — current behavior is ambiguous.

4. The `app-header.tsx` Workspace nav link uses standard Next.js navigation. It's already sticky-friendly. No change needed there.

**Estimated effort to close:** 15–30 minutes (browser verify + commit).

---

## Open item 2 — AI-Chrome-verified iterative review on the 26-paper corpus

**Context:** The original visual-review handoff (2026-05-11) described an "AI-Chrome-verified iterative model" — upload each PDF through the workspace, screenshot the Rendered/Raw/Normalized/Sections/Tables tabs, and feed the screenshots back into a vision model to spot regressions. During v2.3.x, that was approximated by `scripts/verify_corpus.py` running `render_pdf_to_markdown` directly (API-level, no browser). The verifier catches:

  - Title presence / truncation
  - Section count
  - Table HTML count
  - Caption boundary leaks
  - Char-ratio + Jaccard vs spike baseline

What the verifier **doesn't** catch:

  - **Visual layout issues** (e.g. an HTML `<table>` that renders OK as markdown source but breaks the workspace's table styling).
  - **Sticky tab regressions** from open item 1.
  - **JS-runtime errors** in `DocumentWorkspace` rendering specific shapes (e.g. a paper with 30+ figures might overflow a flex container).
  - **Workspace UX** — does the staged progress + ETA feel responsive? Does the Tab badge count match the actual table count?

These need browser-level verification.

### Prerequisites

1. **Local dev stack running.** From `PDFextractor/`:
   ```
   start_app.bat
   ```
   This launches Next.js on `:3000` and uvicorn on `:6117`. The Python service auto-loads `service/.env` for `INTERNAL_SERVICE_TOKEN` (template at `service/.env.example`).

2. **Chrome MCP available** in the Claude Code session (`mcp__Claude_in_Chrome__*` tools). Check with `mcp__Claude_in_Chrome__list_connected_browsers`.

3. **Dev sign-in.** The dev-only Credentials provider (`frontend/src/lib/auth.ts`, registered when `NODE_ENV !== "production"`) lets the agent sign in without OAuth. Default creds: `test@docpluck.local` / `docpluck-dev`. Auto-creates the user with `dailyLimit=-1` so quota doesn't bite during agent loops.

4. **Same-origin test PDFs staged.** Drop the 26-paper corpus into `frontend/public/_test-pdfs/<name>.pdf` (gitignored — see `PDFextractor/.gitignore` and the commit `cbb7f24`). The PDFs are available locally at:

   ```
   ~/Dropbox/Vibe/MetaScienceTools/PDFextractor/test-pdfs/{ama,aom,apa,asa,...}/<name>.pdf
   ```

   Copy or symlink the 26 papers from there. The corpus is enumerated in `docpluck/docs/superpowers/plans/spot-checks/splice-spike/outputs[-new]/` (one `.md` per paper).

### The iteration loop

For each of the 26 papers (recommended order — APA first as it's the primary use case, then per-style spot-checks):

1. **JS-upload pattern** (bypasses the file picker, which is non-automatable):
   ```js
   const res = await fetch("/_test-pdfs/efendic_2022_affect.pdf");
   const blob = await res.blob();
   const file = new File([blob], "efendic_2022_affect.pdf", { type: "application/pdf" });
   const input = document.querySelector('input[type="file"]');
   const dt = new DataTransfer();
   dt.items.add(file);
   input.files = dt.files;
   input.dispatchEvent(new Event('change', { bubbles: true }));
   ```
   Use `mcp__Claude_in_Chrome__javascript_tool` to run it. The `file_upload` MCP tool's "Not allowed" restriction does not apply because the file source is same-origin.

2. **Wait for analyze completion.** The workspace shows `[data-slot="tabs-list"]` once `/api/analyze` returns. Poll for it via `mcp__Claude_in_Chrome__find` or a JS `MutationObserver`.

3. **Screenshot each tab.** `mcp__Claude_in_Chrome__preview_screenshot` (or equivalent) on each of `Rendered`, `Raw`, `Normalized`, `Sections`, `Tables`. For the Rendered tab specifically, scroll-screenshot in 750-px increments to cover the whole document.

4. **Vision-model review.** Feed each screenshot batch back to the model with the prompt template:
   > Does this render look right? Flag: (a) figures that appear before the abstract, (b) captions that bleed across boundaries, (c) tables that render as raw text instead of HTML, (d) headings that look stuck to body prose, (e) sidebar / running-header / footer content leaking into body.

5. **Compare against the spike baseline.** The spike's known-good outputs live in `docpluck/docs/superpowers/plans/spot-checks/splice-spike/outputs[-new]/<name>.md`. Diff the workspace's Rendered tab content against the corresponding `.md` for unexpected divergences.

6. **Triage findings.** Classify each finding as:
   - **Library bug** → file a new GitHub issue in `giladfeldman/docpluck` and add a corpus test.
   - **Workspace bug** → file in `giladfeldman/docpluckapp` and add a Playwright test.
   - **Cosmetic** → add to a TODO punch-list for a future polish pass.

### Expected outcomes

  - The library is already at corpus-PASS 26/26 on the API-level verifier. Visual review should mostly confirm.
  - Likely findings:
    - Workspace cosmetic issues (sticky tabs — see item 1, scroll position resets on tab switch, etc.).
    - Long-paper performance (renders > 200 KB might lag in the workspace's markdown renderer).
    - Edge-case styling on tables with many merged cells (`amle_1` has a 13-table cluster).

  - Unlikely (but possible) library findings:
    - Bug 6 subtitle italicization on a paper not yet seen.
    - A specific publisher's running-header / footer pattern that v2.3.x normalize doesn't catch.

### Automation-ready: optional `scripts/visual_verify_corpus.py`

If the manual loop is fruitful, consider promoting it to a script. The shape:

```python
# scripts/visual_verify_corpus.py
#
# Usage:
#   start_app.bat   # launch dev stack first
#   python scripts/visual_verify_corpus.py
#
# Walks the 26-paper corpus, drives the workspace via Chrome DevTools
# Protocol (chromedp or playwright-python), saves screenshots, emits a
# Markdown report with per-paper PASS/WARN/FAIL.
```

This would close the loop and make `/docpluck-qa` Check 7b (currently API-only) able to optionally include visual verification. The handoff author considered writing it during v2.3.x but Chrome MCP wasn't available so the user-facing verifier stayed API-only.

**Estimated effort:** 4–8 hours for a single full pass. The script (if you write one) is another ~3 hours.

---

## What's already done (context for the next session)

### Library — `giladfeldman/docpluck`

| Tag | What landed | When |
|-----|-------------|------|
| v2.3.0 | Spike Section F port (8 cell-cleaning helpers + orchestrator), Bugs 1-5 fixed, lattice 1×1 artifact filter, case-insensitive captions, pretty section labels, extended Downloaded-from watermark, corpus verifier + 115 new unit tests | 2026-05-11 |
| v2.3.1 | `count_pages` compressed-stream fallback, `_patch_fffds_word_by_word` (Adelina FFFDs), `_italicize_known_subtitle_badges` (Bug 6), `/docpluck-qa` Check 7b + `/docpluck-review` Rule 12 (corpus verifier as regression gate), 22 new tests | 2026-05-12 |

### PDFextractor app — `giladfeldman/docpluckapp`

| Commit | What landed |
|-------|-------------|
| `e0fec07` | service v1.4.2 → v1.5.0: `/analyze`, `/render`, `/tables` endpoints + `service/.env` scaffold |
| `b535659` | Dev-only NextAuth Credentials provider for local/Playwright sign-in |
| `58c153d` | Unified `/extract` workspace with 5 tabs (`Rendered`/`Raw`/`Normalized`/`Sections`/`Tables`) replacing the legacy extract-form + sections-form |
| `39d6132` | `/api/analyze`, `/api/render`, `/api/tables` Next.js proxy routes |
| `cbb7f24` | gitignore `frontend/public/_test-pdfs/` |
| `e525b83` → `5f457ae` | docpluck pin v2.1.0 → v2.3.0 → v2.3.1 |

### Infrastructure for the next session

- **`scripts/verify_corpus.py`** in the docpluck repo — 26-paper API-level verifier. Run it before/after any change to render/extract/tables to catch regressions cheaply (8–12 min).
- **`tests/test_corpus_smoke.py`** — 3 representative papers run in the standard pytest suite (~45s). Skips cleanly when PDFs aren't on disk.
- **`/docpluck-qa` Check 7b + `/docpluck-review` Rule 12** — corpus verifier integrated into the skill workflows. Any change to `render.py` / `extract_structured.py` / `tables/*.py` / `normalize.py` triggers a corpus run.

---

## One-paragraph TL;DR for the next session

Two items remain from the original 2026-05-11 visual-review handoff: (1) make the workspace's tab strip sticky so long Rendered views don't lose their tab buttons on scroll — pure frontend tweak in `document-workspace.tsx`; (2) run the AI-Chrome-verified iterative review on the same 26-paper corpus the API-level verifier already passes, to catch workspace-only / visual-only issues that `verify_corpus.py` can't see. Library and app are otherwise at v2.3.1 / pin-bumped and production-clean.
