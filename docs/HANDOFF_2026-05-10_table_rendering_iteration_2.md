# Handoff — Table Rendering Iteration 2 (continue the push)

**For:** A fresh Claude session to continue improving table rendering quality across the docpluck corpus, picking up from where iteration 1 of 2026-05-10 left off (commit `fb8a3b8`).

**The user's directive (still in force):** *"keep improving things until we see regressions or a block, for all types for all our corpus. I want us to push through and give it another major push to see how far we can go. As long as we can find ways to improve without regressions or blockers with reasonable investment, let's try and keep at it."*

**The user's hard rule (still in force):** *"disappearing text is unacceptable, that's the biggest nono."* If a fix removes content that was in the source PDF, revert. Char-count ratios (`output / pdftotext source`) should stay ≥ 0.97 across the corpus.

---

## What changed in the previous session (commits 6a0a8da → fb8a3b8)

Four bite-sized iterations were committed to `main`. Each is independently revertable. **38 unit tests pass at HEAD**; corpus char ratios held ≥ 0.97 on every paper that has ≥ 1 detected table; **zero word-level content loss** across the four iterations.

| SHA | Iteration | What landed |
|---|---|---|
| [`6a0a8da`](https://github.com/giladfeldman/docpluck/commit/6a0a8da) | 1 | Locator (non-blank-line search + redundant-edge trim + same-page overlap resolution), dedupe ranks by `<table>` / `<tr>` count instead of pipe-row count, continuation-merge **Case C** (parenthetical label-modifier rows like `(Extension)` merge into previous incomplete row), footnote-marker preservation (`*`, `†`, `‡`, `§`, `¶`, `Note.`) re-emitted after rendered HTML |
| [`bc9f39b`](https://github.com/giladfeldman/docpluck/commit/bc9f39b) | 2 | `_drop_caption_leading_rows` strips caption-tail / label-only / page-number-only leading rows from Camelot grids (3 conservative rules, never touches a row with ≥ 2 populated cells) |
| [`8cccbf2`](https://github.com/giladfeldman/docpluck/commit/8cccbf2) | 3 | `_split_mashed_cell` inserts `<br>` at column-undercount boundaries: camel-case (lowercase-only run ≥ 4) and letter→digit (any-letter word ≥ 4). Rules out `macOS`, `iPhone`, `WordPress`, `JavaScript`, `WiFi`. Catches `groupEasy`, `Year2011`, `size80`, `Gender35`, `studentsU.S.`. Mash counts: korbmacher 10→1, ip_feldman 6→1, chandrashekar 7→2. |
| [`fb8a3b8`](https://github.com/giladfeldman/docpluck/commit/fb8a3b8) | 4 | `_is_header_like_row` heuristic walks rows 1..3 promoting consecutive header-like rows into `<thead>`. Stops at group separators. Fixes ip_feldman Table 1 (Estimation / Average estimation row above metric row) and korbmacher Table 6. |

If you need to roll back any commit, the working tree is clean, `git reset --hard <sha>` is safe.

---

## Current state of corpus quality (2026-05-10, post-iteration-4)

Verified on the 7-paper corpus. Char ratios are computed from output (no warnings) / pdftotext source.

| Paper | src | output | ratio | tables in body | tables in unlocated appendix |
|---|---|---|---|---|---|
| `apa/korbmacher_2022_kruger` | 98311 | 109616 | **1.115** | 15 | 2 (Tables 5, 9 — Camelot extracted 0 cells; need investigation) |
| `apa/efendic_2022_affect`    | 52293 |  66148 | **1.265** | most  | a few |
| `apa/chandrashekar_2023_mp` | 112817 | 116384 | **1.031** | most | a few |
| `apa/ziano_2021_joep`        | 43478 |  56922 | **1.310** | 3 (all)| 0 |
| `apa/ip_feldman_2025_pspb`   | 88431 | 106694 | **1.206** | most  | a few |
| `nature/nat_comms_1`         | 76850 |  75353 | **0.981** | 0     | 0 (caption regex doesn't match `Table N \| ...` style) |
| `ieee/ieee_access_2`         | 71909 |  59397 | **0.826** ⚠️| 0 | 0 (caption regex doesn't match `TABLE N` Roman-numeral style) |

⚠️ The `0.826` on `ieee_access_2` looks scary but is **NOT a regression** from this session — it matches HEAD exactly (the file rewrites to the identical bytes). The low ratio is because pdftotext extracts a lot of headers/footers/affiliations on this paper that Camelot wouldn't have helped with anyway. Nothing in iterations 1–4 touched this paper.

**Mash-cell counts (cells with `[a-z][A-Z]` boundary that the splitter didn't catch):**

| Paper | mash cells remaining | total cells |
|---|---|---|
| korbmacher | 1 | 615 |
| efendic | 2 | 263 |
| chandrashekar | 2 | 354 |
| ziano | 0 | 483 |
| ip_feldman | 1 | 683 |

Most remaining mashes are non-letter-boundary cases like `(location)Paper-and-penComputer` where the camel-case adjacency rule can't fire because of the punctuation between words.

---

## Required reading before you touch code

1. [`LESSONS.md`](../LESSONS.md) — particularly L-001 (text-channel calibration, **don't swap pdftotext for downstream problems**), L-006 (Camelot decision + HTML addendum). **Don't relitigate decisions there.**
2. The user's auto-memory in your project memory folder, especially:
   - `project_camelot_for_tables.md` — Camelot is settled; pdfplumber stays for sections + F0 normalize + figure-bbox.
   - `feedback_dont_relitigate_table_lib.md` — don't propose pdfplumber tuning or new library swaps.
   - `feedback_dont_deviate_from_directives.md` — surface scope changes EXPLICITLY.
   - `project_html_tables_in_md.md` — HTML `<table>` is the rendering format inside the `.md` output.
3. The previous handoff: [`docs/HANDOFF_2026-05-10_table_rendering_iteration.md`](./HANDOFF_2026-05-10_table_rendering_iteration.md). Most of its "what's already settled" and "architecture" sections still apply.
4. The 7 current outputs in [`docs/superpowers/plans/spot-checks/splice-spike/outputs/`](./superpowers/plans/spot-checks/splice-spike/outputs/) — read at least 2 fully (e.g., `korbmacher_2022_kruger.md`, `ip_feldman_2025_pspb.md`) before proposing fixes. **The outputs no longer contain Camelot stderr warnings** — iteration 1's render command uses `2>/dev/null`. If you re-render, follow that pattern (the bash one-liners below already do).

---

## What's still settled (don't relitigate)

All the items from the previous handoff plus these new ones:

| Decision | Why | Where |
|---|---|---|
| **Output `.md` files do NOT contain Camelot stderr warnings.** Render with `2>/dev/null`. | Warnings clutter the file and inflate "size" without representing content. Iteration 1 onwards uses `2>/dev/null`. | bash one-liners below |
| **HTML rendering is the canonical path** in `_dedupe_table_blocks` (a code-block fragment fallback CANNOT outrank a real Camelot HTML table on the tiebreak). | Iteration 1, commit `6a0a8da`. | `_dedupe_table_blocks` ranks by `(has_html, n_tr, start)` |
| **Footnote markers preserve to a paragraph after the rendered HTML, not inside `<table>`.** | Iteration 1; user expectation is that explanatory `*M = …` etc. stay readable as prose. | `_extract_footnote_lines` |
| **Multi-row header detection caps at 3 rows AND respects group-separator rows.** | Iteration 4. Without the group-separator guard, a row like `["Easy", "", ""]` got promoted to `<th>` instead of rendering as `<td colspan>`. | `pdfplumber_table_to_markdown` |

---

## Remaining issues, prioritized for impact × risk

### Tier A — Worth attempting, content-preserving, ~1 iteration each

**A1. Camelot returns 0 cells for some specific tables (handoff item #2).** Examples: `korbmacher_2022_kruger` Tables 5 and 9. Camelot stream just couldn't find a table boundary. Likely Tables that span landscape pages or have unusual whitespace. Investigate one specific table — try `flavor="lattice"` as a backup before the raw_text fallback in `_format_table_md`. If lattice works, wire it as a per-page fallback. **Risk:** lattice often returns 0 too on whitespace-only tables; would only help cases with rule lines.

**A2. Adjacent-duplicate header cells should use `colspan` (handoff item #7).** Look at korbmacher Table 1's header: `Judgmental weight | Judgmental weight` — should be `<th colspan="2">`. Detect: when consecutive cells in a header row have identical content, merge with `colspan="N"`. Add to the `<thead>` rendering branch in `pdfplumber_table_to_markdown`. **Risk:** low. Don't apply to body rows (data cells with same numeric value are common and should NOT merge).

**A3. Aggressive mash split for non-adjacent letter-letter boundaries.** Cases like `(location)Paper-and-penComputer` slip through because the camel-case rule needs `[a-z][A-Z]` adjacency and these have punctuation between. New rule candidate: split at `[a-z\d][A-Z]` where the LEFT char is a word-ending character AND the LEFT word is ≥ 4 chars (allow a single non-letter punctuation in between, like `)` or `]`). **Risk:** higher false-positive rate. Test against `JavaScript`, `WordPress`, `macOS` (none have punctuation between, so still safe), but also check `O(n)Algorithm` (could false-split). Add a unit test corpus before shipping.

**A4. Camelot's `_trim_prose_tail` over-trimming.** Some tables drop legitimate "Note." footnote rows that DO carry table-relevant info. Iteration 1's footnote re-emit handles `*` / `†` markers but `_trim_prose_tail` may drop other prose-y rows that contain meaningful caveats. Audit: after re-render, grep each output for `Note. ` outside of `<table>` blocks and compare against pdftotext source. If the source has `Note. …` and the output doesn't, footnote-extract may be missing the row.

**A5. Caption-tail-as-header detection edge case.** Look at `chandrashekar_2023_mp` Table 7-10: they share `<th>Table 7</th>` as a (collapsed) header row. The current `_drop_caption_leading_rows` doesn't fire because the row HAS multi-column content (rule 1 only matches single-cell label rows). Add a rule 4: drop a row whose first cell is `Table N` AND all other cells are empty *as content but not as count*. Caveat: be careful — Camelot sometimes emits `["Table N", ""×N]` legitimately when row 0 was the caption.

### Tier B — Bigger lift but high-impact, suggest discussing with user before starting

**B1. Multi-page table assembly (handoff item #4).** `ip_feldman_2025_pspb` Table 2 spans 2 pages. Camelot extracted only the first page; hypotheses 5+, 6+, 7+ on page 2 ended up as plain prose after the table. Fix: detect "Table N (continued)" caption pattern AND/OR consecutive `Table N` captions in adjacent pages, run Camelot on each, concatenate cells (matching column structure). **Risk:** higher — multi-page tables can have different column layouts on different pages, and stitching is error-prone. Probably 1–2 day work.

**B2. Nature / IEEE caption format (handoff "What's NOT done yet").** `nature/nat_comms_1` and `ieee/ieee_access_2` currently detect 0 tables because `TABLE_CAPTION_RE` in `docpluck/tables/captions.py` only matches `^Table\s+\d+`. Nature uses `Table 1 |` (pipe separator instead of period/colon). IEEE uses `TABLE I` (Roman numerals + uppercase). **This is a docpluck library change, NOT a spike change.** The library is published to PyPI (per [`CLAUDE.md`](../CLAUDE.md) "Two-Repo Architecture"). Bumping the regex requires a version bump (`docpluck/__init__.py`, `pyproject.toml`, `docpluck/normalize.py::NORMALIZATION_VERSION`), CHANGELOG entry, tag, and updating `PDFextractor/service/requirements.txt` git pin. **Surface scope change to the user before doing this** — they may want to keep library work out of the spike for now.

**B3. Apply the spike's HTML-rendering improvements to `docpluck/tables/render.py:cells_to_html`** (handoff explicit follow-up). Same library-vs-spike concern as B2.

### Tier C — Lower priority / explicit follow-ups

**C1. Tabula as second extractor.** ChatGPT's research suggested it for cases Camelot fails. Adds a heavy Java dependency. Try only if A1 (lattice fallback) doesn't help for a specific paper.

**C2. Footnote rendering as a consolidated `## Footnotes` section.** Currently inline parenthetical refs (or, after iteration 1, paragraphs after the relevant table). Spec says consolidated section at end. Lowest priority — current handling is acceptable for review.

---

## The iterative model (unchanged from previous handoff)

```
LOOP:
  1. AI-VERIFY: read each of the 7 output .md files, looking for:
     - Cut/disappearing text vs the original PDF
     - Tables that look broken (wrong cells, missing data)
     - Captions that are truncated, malformed, or wrong
     - Sections that are missing or duplicated
     - Body prose that ended up inside a table (or vice versa)
     For each issue, note: file, line, what's wrong, hypothesis for cause.

  2. PICK HIGHEST-IMPACT ISSUE: the one that affects the most papers
     OR has the biggest visual/correctness impact OR is on the user's
     "disappearing text is unacceptable" list.

  3. FIX in splice_spike.py (or camelot_extract.py / extract_structured.py
     if the issue is upstream). Add a unit test for the fix to
     test_splice_spike.py if applicable.

  4. RUN TESTS: `cd docs/superpowers/plans/spot-checks/splice-spike &&
     python -m pytest test_splice_spike.py`. Must be 38+/38+ passing.

  5. RE-RENDER all 7 papers using the bash one-liner below.

  6. CHAR-RATIO + WORD-LOSS AUDIT: see "Audit one-liner" below. If
     ANY ratio drops below the previous iteration's value AND words
     are missing that aren't simply mash-split tokens (like the
     "DrivingDriving"→"Driving" case), INVESTIGATE before continuing.

  7. VISUAL VERIFY: open the 1-2 files most affected by the fix in
     your viewer. Confirm the fix worked AND no new regressions appeared.

  8. COMMIT with a clear message naming the fix + linking to the issue
     number from this handoff (A1 / A2 / etc.).

  9. REPORT to user with: what was fixed, what remains, the audit table.

GOTO LOOP

EXIT:
  - If a fix WOULD lose content (char ratio < 0.97 OR genuinely missing
    words), revert and document.
  - If two consecutive issues require multi-day work (e.g., tabular OCR,
    rewriting section detection), STOP and ask the user for direction.
  - If user says "we're done."
```

---

## Bash one-liners

### Re-render the corpus (use `2>/dev/null`, never `2>&1` — warnings clutter the .md files)

```bash
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck" && for f in korbmacher_2022_kruger efendic_2022_affect chandrashekar_2023_mp ziano_2021_joep ip_feldman_2025_pspb; do
  python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/apa/${f}.pdf" 2>/dev/null > "docs/superpowers/plans/spot-checks/splice-spike/outputs/${f}.md"
done && python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/nature/nat_comms_1.pdf" 2>/dev/null > "docs/superpowers/plans/spot-checks/splice-spike/outputs/nat_comms_1.md" && python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/ieee/ieee_access_2.pdf" 2>/dev/null > "docs/superpowers/plans/spot-checks/splice-spike/outputs/ieee_access_2.md" && echo RENDER_DONE
```

(~60–90 s; Camelot loads stream + lattice on every page.)

### Audit (char ratios + word loss vs git HEAD vs pdftotext source)

```bash
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck" && PYTHONIOENCODING=utf-8 python << 'EOF'
import sys, re, subprocess
sys.stdout.reconfigure(encoding='utf-8')
from docpluck import extract_pdf
papers = [
    ('apa/korbmacher_2022_kruger', 'korbmacher_2022_kruger'),
    ('apa/efendic_2022_affect', 'efendic_2022_affect'),
    ('apa/chandrashekar_2023_mp', 'chandrashekar_2023_mp'),
    ('apa/ziano_2021_joep', 'ziano_2021_joep'),
    ('apa/ip_feldman_2025_pspb', 'ip_feldman_2025_pspb'),
    ('nature/nat_comms_1', 'nat_comms_1'),
    ('ieee/ieee_access_2', 'ieee_access_2'),
]
def strip_warn(t):
    return '\n'.join(ln for ln in t.split('\n') if 'UserWarning' not in ln and 'site-packages' not in ln and 'cols, rows' not in ln)
print(f"{'Paper':30}  {'src':>6}  {'NEW':>6}  {'src_ratio':>9}  {'HEAD':>6}  {'Δ':>+5}  {'wlost':>5}")
for pdf, name in papers:
    with open(f'../PDFextractor/test-pdfs/{pdf}.pdf','rb') as f:
        t,_ = extract_pdf(f.read())
    new = open(f'docs/superpowers/plans/spot-checks/splice-spike/outputs/{name}.md', encoding='utf-8').read()
    head_r = subprocess.run(['git','show',f'HEAD:docs/superpowers/plans/spot-checks/splice-spike/outputs/{name}.md'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    head_clean = strip_warn(head_r.stdout)
    new_clean = strip_warn(new)
    new_w = set(re.findall(r'\b[A-Za-z][A-Za-z]{4,}\b', new_clean))
    head_w = set(re.findall(r'\b[A-Za-z][A-Za-z]{4,}\b', head_clean))
    lost = head_w - new_w
    ratio = len(new_clean) / len(t)
    delta = len(new_clean) - len(head_clean)
    print(f'{name:30}  {len(t):>6}  {len(new_clean):>6}  {ratio:>9.3f}  {len(head_clean):>6}  {delta:>+5}  {len(lost):>5}')
EOF
```

A "lost word" is a word ≥ 5 chars present in the HEAD output but not the NEW output. **CRITICAL:** if you see lost words like `DrivingDriving`, `groupEasy`, `studentsU`, those are MASH-SPLIT tokens that legitimately decomposed into separate words (e.g., `Driving` + `Driving`, `group` + `Easy`). They are NOT real losses. Real losses are content words that no longer appear anywhere in the output (verify with `grep -c "<word>"` against new output).

### Run unit tests (must stay green)

```bash
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck/docs/superpowers/plans/spot-checks/splice-spike" && python -m pytest test_splice_spike.py -v
```

Should report **38 passed** at HEAD (commit `fb8a3b8`). Each new fix should ideally add ≥ 1 unit test for the changed behavior.

---

## Key files (where work happens)

Same as previous handoff. Reproduced here for self-containedness:

| Path | Role |
|---|---|
| [`docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/splice_spike.py) | **The standalone the user reviews.** Most fixes go here. |
| [`docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/test_splice_spike.py) | 38 unit tests at HEAD. **Must stay green after every change.** |
| [`docs/superpowers/plans/spot-checks/splice-spike/outputs/`](./superpowers/plans/spot-checks/splice-spike/outputs/) | The 7 regenerated `.md` outputs. The user opens these in their viewer. |
| [`docpluck/tables/camelot_extract.py`](../docpluck/tables/camelot_extract.py) | Wraps Camelot. Library code. |
| [`docpluck/extract_structured.py`](../docpluck/extract_structured.py) | Orchestrator. Library code. |
| [`docpluck/tables/captions.py`](../docpluck/tables/captions.py) | Caption regex (Nature/IEEE broadening lives here — see B2). |
| [`docpluck/tables/render.py`](../docpluck/tables/render.py) | Library `cells_to_html`. Lacks the spike's smart features (continuation merge, multi-row header, mash split, caption-row drop). See B3. |

---

## Critical pitfalls (lessons accumulated across iterations 1–4)

- **Don't change the locator's max_window without considering blank-line-interleaved pdftotext rendering.** pdftotext on column-rendered tables emits each row as one non-blank line surrounded by blank-line gaps. Counting raw lines starves the window cap. Iteration 1 switched to non-blank-line space + redundant-edge trim; this works but if you bump the multiplier, the trim is what keeps the region tight.

- **Don't change the dedupe ranking back to `pipe_rows`.** It's always 0 since rendering switched to HTML on 2026-05-09. The current `(has_html, n_tr, start)` ordering is what guarantees a real Camelot table outranks a fragment-wrap code-block fallback.

- **Don't aggressively trim the located region without preserving footnote markers.** The redundant-edge trim from iteration 1 trims rows whose tokens are entirely covered elsewhere, but this can shed footnote lines whose tokens (asterisks, parentheticals) don't overlap with the table-token set. The footnote re-emit (`_extract_footnote_lines`) is a SECOND pass that catches these — keep both passes.

- **Multi-row header detection MUST guard against group-separator rows.** Without the `_is_group_separator` check at the top of the promotion loop, a row like `["Easy", "", ""]` gets pulled into `<thead>` and the colspan separator path never fires. The current code stops promotion at the first group-separator-shaped row.

- **Mash-split rules differ for camel-case vs letter→digit.** Camel-case uses lowercase-only run length to spare brand names (`macOS`, `JavaScript`). Letter→digit uses any-letter word length to catch capital-start short words (`Year2011`). Keep the dual-rule split — collapsing them either way regresses one set of cases.

- **`<th>` vs `<td>` is structural, not visual.** Iteration 4 changes only the tag, not the cell content. Char-ratio audits show `Δ = +0` because there's no content change — that's the expected and desired result.

- **`_camelot_cells_for_table` runs Camelot stream PER PAGE per table.** Cache by `(pdf_path, page)` is critical. If you add a lattice fallback (A1), cache by `(pdf_path, page, flavor)`. Cold-cache renders take 60–90 s on the corpus.

- **The standalone is throwaway-by-design.** The user reviews the standalone outputs. Don't worry about keeping it perfectly modular — it's a spike, not a final API. Library work (B2, B3) is a separate, larger lift that needs user buy-in due to the PyPI release flow per `CLAUDE.md`.

---

## Suggested first move for the new session

1. **Verify the working tree is clean** (`git status`) and you're at commit `fb8a3b8` or later on `main`.
2. **Re-render the corpus** with the bash one-liner above; confirm tests pass.
3. **Run the audit one-liner**; copy the table into your scratchpad.
4. **Read `korbmacher_2022_kruger.md` and `ip_feldman_2025_pspb.md` end-to-end**, looking for new issues. Compile a list of ≥ 5 specific issues with line references; map each to the A/B/C tier above.
5. **Pick the highest-impact issue from Tier A** (probably A2 — adjacent-duplicate header colspan — fastest path to visible improvement). Loop.
6. **If you hit a Tier B item**, surface it to the user before starting (per the `feedback_dont_deviate_from_directives.md` memory).

---

## Final note

The previous session committed 4 iterations content-preserving with full test coverage. The bar is high but reachable: each commit fixed something visible, added tests, and held the corpus's char-ratio floor. Surface scope changes explicitly. Don't add features the user didn't ask for. When in doubt about a fix, ASK before applying it.

Good luck. The next 3–5 fixes should be reachable with the same iterative loop. Tier A1, A2, A3 are the natural sequence.
