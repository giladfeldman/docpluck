# Handoff — iterative library improvement loop

**For:** A fresh session continuing the v2.4.x → v2.5.x release chain. Goal is to drive as many of the 101 corpus PDFs to clean output as the weekly hour budget allows.

**Predecessor handoffs (read first if helpful):**
- `docs/HANDOFF_2026-05-12_visual_verify_results.md` — context for the v2.4.0 fixes
- `docs/HANDOFF_2026-05-12_phase2_101pdf_corpus.md` — context for v2.4.1 + the verifier upgrade

---

## State at handoff

**Library:** v2.4.1 tagged + pushed to `giladfeldman/docpluck`. Last commit `52b9042`.

**App:** `PDFextractor/service/requirements.txt` pins `docpluck v2.4.1` (commit `07dd742`). Vercel/Railway auto-deployed.

**Verification status:**
- 26-paper spike-baseline corpus (`scripts/verify_corpus.py`): **26/26 PASS** at v2.4.1.
- 101-paper wider corpus (`scripts/verify_corpus_full.py`): **never run end-to-end at v2.4.1.** A partial run at v2.4.0 surfaced 7 fails in the first 25 papers; v2.4.1 closed 5 of those 7 (the AMA/AOM `M` tags). The remaining ~75 papers' status is unknown. **Step 1 below is to run this verifier.**

**Repo cleanliness:** both repos clean. No uncommitted edits.

**Dev stack:** left running on `:6116` (Next.js) + `:6117` (uvicorn). The uvicorn process imported v2.4.1 via the editable local install, so it serves the current library. The Python service does NOT hot-reload on file change — restart it after every library edit (see "Workflow" below).

**Staged PDFs for workspace visual check:** all 101 are in `PDFextractor/frontend/public/_test-pdfs/` (gitignored). The `__autoCheck(name)` JS helper from the previous session is no longer in the browser; re-paste it from this doc's "Chrome MCP helpers" section if you want a visual loop.

---

## The iterative loop (one cycle = ~25-45 min)

1. **Re-run the full 101-PDF verifier** to enumerate current failures:
   ```
   cd ~/Dropbox/Vibe/MetaScienceTools/docpluck
   python -u scripts/verify_corpus_full.py --save-renders > /tmp/v24x.log 2>&1 &
   tail -f /tmp/v24x.log | grep -E "^(PASS|FAIL|WARN|ERROR)"
   ```
   Use `-u` for unbuffered output — without it Python buffers and you see nothing until exit. Wall time: 15-30 min depending on disk + Camelot.

2. **Triage failures by tag frequency.** Inside `/tmp/v24x.log` after the Summary, look at the "Failures by tag" lines. Pick the tag that appears most often — that's the highest-leverage fix.

   Tag legend (also at the top of every verifier run):
   ```
   M = missing # Title line                    [v2.4.0/2.4.1 fixed several]
   T = title ends in connector word            [pre-existing trim heuristic]
   D = title missing words vs spike baseline   [needs a spike .md to fire]
   R = title repeats in body                   [v2.4.0 fix targets this — Nature pattern]
   S = section count < 4                       [structural, sectioning bug]
   H = ### Table N heading w/ no <table> html  [Camelot couldn't extract cells]
   C = caption > 800 chars                     [caption boundary leak]
   X = output < 5 KB                           [almost certainly a PDF extract failure]
   L = much shorter than spike baseline        [requires baseline]
   J = Jaccard < 0.6 vs spike                  [requires baseline]
   ```

3. **Root-cause the top failure cluster.** Open `tmp/renders_v2.4.0/<paper>.md` (the saved render from step 1) and inspect the top of the file. Cross-reference against the actual PDF in `../PDFextractor/test-pdfs/<style>/<paper>.pdf`.

   A useful debugging one-liner — dump the layout title decision path for a specific paper:
   ```python
   PYTHONIOENCODING=utf-8 python -c "
   from docpluck.render import _compute_layout_title
   from docpluck.extract_layout import extract_pdf_layout
   import pathlib
   pdf = pathlib.Path('../PDFextractor/test-pdfs/<style>/<paper>.pdf').read_bytes()
   doc = extract_pdf_layout(pdf)
   print(repr(_compute_layout_title(doc)))
   "
   ```

4. **Fix in `docpluck/render.py`** (or wherever the root cause lives — `normalize.py` for body-text issues, `sections/` for missing-section issues, `tables/` for table-extraction issues).

5. **Add a unit test** to `tests/test_render.py` (or the matching test file) that locks in the fix. Tests use small synthetic fixtures, not full PDFs — keep them fast (<1s).

6. **Run targeted tests:**
   ```
   python -m pytest tests/test_render.py -x -q
   ```
   Should be <1s. Must pass before going further.

7. **Re-run the 26-paper spike-baseline corpus to guard against regression:**
   ```
   python -u scripts/verify_corpus.py > /tmp/v26.log 2>&1
   ```
   Wait for `PASS 26/26`. Wall time: ~8 min. **If a paper now fails, your fix has overreach — narrow it and try again before continuing.**

8. **Bump library version** (patch level — `2.4.1` → `2.4.2`, etc.):
   - `docpluck/__init__.py::__version__`
   - `pyproject.toml::version`
   - `CHANGELOG.md` — add a `## [2.4.x] — 2026-05-13` block with the fix description.

9. **Commit + tag + push** the library:
   ```
   cd ~/Dropbox/Vibe/MetaScienceTools/docpluck
   git add CHANGELOG.md docpluck/__init__.py docpluck/render.py pyproject.toml tests/test_render.py
   git commit -m "release: vX.Y.Z — <one-line summary>

   <body explaining the fix and which papers it affects>
   "
   git tag vX.Y.Z
   git push origin main
   git push origin vX.Y.Z
   ```

10. **Bump the app pin** in `PDFextractor/service/requirements.txt` to the new version, commit, push:
    ```
    cd ~/Dropbox/Vibe/MetaScienceTools/PDFextractor
    # edit service/requirements.txt
    git add service/requirements.txt
    git commit -m "bump: docpluck vA.B.C -> vX.Y.Z"
    git push origin master
    ```

11. **Restart the dev Python service** so the running uvicorn picks up the new library code:
    ```
    # find + kill the existing uvicorn:
    tasklist | grep python    # locate the larger-memory uvicorn process
    taskkill /PID <PID> /F
    cd ~/Dropbox/Vibe/MetaScienceTools/PDFextractor/service
    python -m uvicorn app.main:app --port 6117 --env-file .env > /tmp/docpluck-svc.log 2>&1 &
    ```
    Or use the bash background-task pattern from the previous session (start with `run_in_background`).

12. **Spot-check the fixed papers visually** via Chrome MCP — open `http://localhost:6116/extract`, sign in as `test@docpluck.local` / `docpluck-dev`, and upload 2-3 of the previously-failing PDFs to confirm the fix renders correctly in the actual workspace UI. Use the JS upload helper in the "Chrome MCP helpers" section below.

13. **Loop back to step 1** with the new version. Expect each iteration to PASS-flip 3-10 papers out of the 101 if the root cause is a publisher-format issue (e.g. all 10 IEEE papers share the same layout).

---

## Where to focus first

Best ROI ranking by expected paper-count impact (from the partial v2.4.0 run):

1. **Run-of-the-mill `S` tags** (section count < 4) — likely an `## Heading` detector blind spot for a particular publisher. If 5+ papers share this, fixing one detector rule unblocks all of them.
2. **`X` tags** (output < 5 KB) — extreme failures, usually a PDF extraction crash. Check `tmp/renders_v2.4.0/<paper>.md` to see how short the output is. May be the FFFD-recovery path mis-firing, or a scanned PDF that pdftotext can't extract from. The Adelina FFFD-recovery (v2.3.1) was the previous touch in this area.
3. **`H` tags** (table heading w/o HTML) — Camelot couldn't structure the table into cells. Real fix is hard (needs a smarter table-extraction strategy); cheap fix is to make the rendered output gracefully fall back to raw text under the heading rather than emit a bare `### Table N`. **`ar_apa_j_jesp_2009_12_011` is a known case** in the corpus.
4. **`R` tags** (title repeats in body) — v2.4.0 specifically targets this (Nature Communications). If new `R` tags appear in the 101 corpus, it's a different publisher's title-repeat pattern. Add their layout to the sweep heuristic.
5. **`T` tags** (trailing-connector truncation) — title detector dropped a tail word. Investigate per-paper; sometimes a layout-cluster widening is the fix.
6. **`D` tags** (title word-set delta) — middle-of-title word dropped. v2.4.0 fixed the ziano case; new D tags would point to different publisher-specific font-size quirks.

Avoid making sweeping changes for a single paper — wait until you have 2+ examples of the same pattern before generalizing the fix. Single-paper exceptions can go into the `## Known issues` section of the changelog instead of into the code.

---

## Hard rules (DO NOT VIOLATE)

These come from the project's `LESSONS.md` + the predecessor handoffs:

1. **Never use `pdftotext` with `-layout`** — column interleaving.
2. **Never use `pymupdf4llm` / PyMuPDF / `fitz` / `column_boxes()`** — AGPL license, incompatible with the SaaS service.
3. **Text channel is `extract_pdf`, layout channel is `extract_pdf_layout` — never mix them.** Fixes to body text go in `normalize.py` / `sections/`; fixes to title / tables / figures go in the layout-channel consumers.
4. **Always normalize `U+2212` (minus sign) → ASCII hyphen** in `normalize.py` step S5. If you touch S5, keep this.
5. **Add a regression test** to `tests/test_render.py` or the matching test file for every fix. Don't ship a fix that has only manual verification — the next session needs the test to catch a recurrence.
6. **Bump library version every time you push.** Patch-level for fixes; minor for behavior changes that alter rendered byte content.
7. **`scripts/verify_corpus.py` must pass 26/26 before every push.** It's the regression gate.

---

## Chrome MCP helpers (paste once per session)

After connecting to the browser and creating a tab, paste these into a JS exec to set up the upload helpers:

```js
window.__results = {};
window.__startUpload = async (name) => {
  const removeBtn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Remove');
  if (removeBtn) { removeBtn.click(); await new Promise(r => setTimeout(r, 200)); }
  const res = await fetch('/_test-pdfs/' + name);
  if (!res.ok) return 'fetch ' + res.status;
  const blob = await res.blob();
  const file = new File([blob], name, { type: 'application/pdf' });
  const input = document.querySelector('input[type="file"]');
  const dt = new DataTransfer();
  dt.items.add(file);
  input.files = dt.files;
  input.dispatchEvent(new Event('change', { bubbles: true }));
  window.__inflight = { name, t0: Date.now() };
  return 'started ' + name;
};
window.__autoCheck = (name) => {
  delete window.__results[name];
  window.__startUpload(name).then(() => {
    const id = setInterval(() => {
      if (document.querySelector('[data-slot="tabs-list"]')) {
        clearInterval(id);
        setTimeout(() => {
          const titleEl = document.querySelector('article h1');
          const firstParas = [...document.querySelectorAll('article p')]
            .slice(0, 5).map(p => p.textContent.trim().slice(0, 200));
          window.__results[name] = {
            title: titleEl?.textContent.trim().slice(0, 200),
            firstParas,
            docH: document.documentElement.scrollHeight,
          };
        }, 700);
      }
    }, 500);
  });
  return 'queued ' + name;
};
'helpers ready'
```

Then per paper:
```js
window.__autoCheck('jama_open_4.pdf')
// wait 20-60s
window.__results['jama_open_4.pdf']  // pull when ready
```

---

## When to stop the loop

- **Hard stop:** weekly hour budget exhausted (the user's directive).
- **Soft stop after each push:** if the latest fix moved 0 papers in the verifier, the targeted pattern was wrong — re-triage before continuing.
- **Soft stop on regression:** if `verify_corpus.py` drops below 26/26, REVERT and re-think. Never push a regression.

Write a short close-out handoff doc (`docs/HANDOFF_2026-05-13_iterative_<N>.md`) at the end of the session listing:
- Versions shipped (vA.B.C → vX.Y.Z)
- Failure count before + after
- One-paragraph description of the patterns fixed
- Remaining failures with rough triage

---

## File map

- `docpluck/render.py` — title detection, heading emission, title-rescue, duplicate sweep
- `docpluck/normalize.py` — text channel cleanup, watermark/header strips, U+FFFD recovery
- `docpluck/sections/` — section detection (annotators + core orchestrator)
- `docpluck/tables/` — Camelot integration + cell-to-HTML
- `scripts/verify_corpus.py` — 26-paper regression gate
- `scripts/verify_corpus_full.py` — 101-paper triage (created this session)
- `tests/test_render.py` — render unit tests (24 currently; add to this for every render fix)

Good luck. Make it count.
