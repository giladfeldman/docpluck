# Handoff — Table Rendering Iteration 3 (continue the push)

**For:** A fresh Claude session to continue improving table rendering quality across the docpluck corpus, picking up from where iteration 2 of 2026-05-10 left off (commit `a22c3e3`).

**The user's directive (still in force):** *"keep improving things until we see regressions or a block, for all types for all our corpus. I want us to push through and give it another major push to see how far we can go. As long as we can find ways to improve without regressions or blockers with reasonable investment, let's try and keep at it."*

**The user's hard rule (still in force):** *"disappearing text is unacceptable, that's the biggest nono."* If a fix removes content that was in the source PDF, revert. Char-count ratios (`output / pdftotext source`) should stay ≥ 0.97 across the corpus.

---

## What changed in the previous session (commits c493a3d → a22c3e3)

Four bite-sized iterations were committed to `main`. Each is independently revertable. **56 unit tests pass at HEAD** (was 38 before this session); corpus char ratios held ≥ 0.97 on every paper that has ≥ 1 detected table; **zero word-level content loss** across the four iterations (the only word-set differences are hyphenated fragments — e.g. `desirabil` from `desirabil-ity` — whose full forms now appear correctly because de-hyphenation happened naturally when fake tables were demoted).

| SHA | Iteration | What landed |
|---|---|---|
| [`c493a3d`](https://github.com/giladfeldman/docpluck/commit/c493a3d) | 5 (#A4) | When `_wrap_table_fragments` finds a 5+ paragraph run with NO matching caption (e.g. `Table S7` doesn't match `CAPTION_RE`'s digit-only regex), it used to silently drop the whole run. Now: extract footnote-marker paragraphs (`Note.`, `*M=…`, `†p<.05`) from the dropped run and re-emit them. Recovers chandrashekar's S7/S8 `Note. N =161;...` and `Note. N =235;...` lines that were a direct violation of "no disappearing text". 8-char minimum guards against stray marker-only paragraphs. |
| [`d1345ff`](https://github.com/giladfeldman/docpluck/commit/d1345ff) | 6 | Detect "spurious 1-column" grids (≥4 rows where no row has >1 populated cell) and emit as fenced code blocks instead of fake `<table>`. Removes 3 corpus regressions: korbmacher Tables 5 & 9, efendic Table 2 (50-row mess of caption-echo + page header + body prose). Side benefit: surrounding body prose flows correctly with proper de-hyphenation. |
| [`6fc7045`](https://github.com/giladfeldman/docpluck/commit/6fc7045) | 7 | Add Rule 4 to `_drop_caption_leading_rows`: drop a row with EXACTLY one populated cell (in any column, not just col 0) when that cell appears verbatim in the caption. Catches Camelot's habit of dropping the second line of a wrapped caption into a non-zero column. Fires on korbmacher Tables 7 & 12 (3 caption-tail rows total) and ziano Table 1 (1 prefix). |
| [`a22c3e3`](https://github.com/giladfeldman/docpluck/commit/a22c3e3) | 8 | Detect side-by-side-merged tables: when a header row's cells are all distinct `Table N` labels (e.g., `[Table 3, Table 4]`), Camelot stitched two adjacent independent tables into one grid. Extract just the matching column for the current label and demote to a code block. Fixes chandrashekar Tables 3 & 4 (each was rendering the same 50-row merged mess). |

If you need to roll back any commit, the working tree is clean, `git reset --hard <sha>` is safe.

---

## Current state of corpus quality (2026-05-10, post-iteration-8)

Verified on the 7-paper corpus. Char ratios are computed from output / pdftotext source.

| Paper | src | output | ratio | vs HEAD-of-iteration-2 |
|---|---|---|---|---|
| `apa/korbmacher_2022_kruger` | 98311 | 107746 | **1.096** | -1870 chars (cleaner: Tables 5/7/9/12) |
| `apa/efendic_2022_affect`    | 52293 |  60733 | **1.161** | -5415 chars (Table 2 demoted to code) |
| `apa/chandrashekar_2023_mp` | 112817 | 114498 | **1.015** | -1886 chars (Tables 3/4 split + Notes recovered + 1-col demote) |
| `apa/ziano_2021_joep`        | 43478 |  56829 | **1.307** | -93 chars (Table 1 caption-tail dropped) |
| `apa/ip_feldman_2025_pspb`   | 88431 | 106694 | **1.207** | unchanged (no fixes touched this paper) |
| `nature/nat_comms_1`         | 76850 |  75353 | **0.981** | unchanged |
| `ieee/ieee_access_2`         | 71909 |  59397 | **0.826** ⚠️| unchanged from HEAD; pre-existing upstream extraction issue, not something this session's fixes touch |

**Note coverage** (chandrashekar was the only paper with missing Notes; now full):

| Paper | src `Note.` | output `Note.` | missing |
|---|---|---|---|
| korbmacher | 5 | 5 | 0 |
| efendic | 7 | 7 | 0 |
| chandrashekar | 12 | 12 | **0** (was 2 missing) |
| ziano | 0 | 0 | 0 |
| ip_feldman | 6 | 6 | 0 |

**Spurious 1-column tables**: 0 across the corpus (was 3).
**Side-by-side merged tables**: 0 with `<th>Table N</th><th>Table M</th>` headers in the body (was 2 in chandrashekar).

---

## Required reading before you touch code

1. [`LESSONS.md`](../LESSONS.md) — particularly L-001 (text-channel calibration, **don't swap pdftotext for downstream problems**), L-006 (Camelot decision + HTML addendum). **Don't relitigate decisions there.**
2. The user's auto-memory in your project memory folder, especially:
   - `project_camelot_for_tables.md` — Camelot is settled.
   - `feedback_dont_relitigate_table_lib.md` — don't propose pdfplumber tuning or new library swaps.
   - `feedback_dont_deviate_from_directives.md` — surface scope changes EXPLICITLY.
   - `project_html_tables_in_md.md` — HTML `<table>` is the rendering format inside the `.md` output.
3. The previous handoff: [`docs/HANDOFF_2026-05-10_table_rendering_iteration_2.md`](./HANDOFF_2026-05-10_table_rendering_iteration_2.md). Most of its "what's already settled" still applies.
4. The 7 current outputs in [`docs/superpowers/plans/spot-checks/splice-spike/outputs/`](./superpowers/plans/spot-checks/splice-spike/outputs/) — read at least 2 fully (e.g., `korbmacher_2022_kruger.md`, `chandrashekar_2023_mp.md`) before proposing fixes. **Outputs no longer contain Camelot stderr warnings.**

---

## What's still settled (don't relitigate)

All items from the previous handoffs PLUS these new ones:

| Decision | Why | Where |
|---|---|---|
| **Spurious 1-column "tables" (≥4 rows, no row with >1 populated cell) render as fenced code blocks, not `<table>`.** | Iteration 6, commit `d1345ff`. Before: korbmacher Table 5 / 9 and efendic Table 2 each rendered 9-50 rows of body prose as fake tables. | `_is_spurious_single_column_grid` + `_render_grid_as_code_block` in `_format_table_md` |
| **Caption-tail rows are dropped when their single populated cell is in any column (col 0 OR higher) and matches caption text verbatim.** | Iteration 7, commit `6fc7045`. Camelot drops wrapped-caption second lines into non-zero columns; rule 2 only checked col 0. | `_drop_caption_leading_rows` Rule 4 |
| **Side-by-side merged tables (header row of distinct `Table N` labels) split per-column, demoted to code block per side.** | Iteration 8, commit `a22c3e3`. Camelot stitches adjacent PDF tables into one grid; rendering both sides as one table is misleading. | `_detect_side_by_side_merge` + `_extract_column_subgrid` in `_format_table_md` |
| **Footnote markers (`Note.`, `*`, `†`) are rescued from un-captioned 5+ fragment-runs even when the run as a whole is dropped as duplicate-of-Camelot noise.** | Iteration 5 (#A4), commit `c493a3d`. The "unlabeled fragment-wraps are noise" assumption fails when a run has `Note. N=161;...` content that doesn't appear elsewhere. | `_wrap_table_fragments` `elif caption_label is None` branch |

---

## Remaining issues, prioritized for impact × risk

### Tier A — Worth attempting, content-preserving, ~1 iteration each

**A1. Super-header / sub-header column-wise fold.** korbmacher Table 7's `<thead>` currently has two rows: `["", "", "", "Mean", "", "Eﬀect", ""]` over `["Condition", "T-statistic", "df", "diﬀerence", "p-value", "size r", "95% CI"]`. The natural rendering would fold "Mean" into "Mean<br>diﬀerence" (col 3) and "Eﬀect" into "Eﬀect<br>size r" (col 5) so the super-header columns merge with their sub-cells. **Risk**: a real 2-row header where row 1 has all-populated cells should NOT fold. Heuristic: fold only when row 1 has ≥1 empty cell AND every populated cell in row 1 has a populated cell directly below in row 2.

**A2. Side-by-side merge without `Table N / Table M` signal.** chandrashekar's Table 1 (`### Table 1` at L804 in the unlocated appendix) has the same 2-column-prose structure as Tables 3 & 4 had, but the header is `["", "Opt-Out conditions, the 'yes' response was pre-selected.<br>In positively framed Opt-In conditions, the 'No' response"]` (a caption-tail bleed) instead of `[Table 3, Table 4]`. Iteration 8's detector misses this. Idea: also detect when a 2-column grid has every row's content looking like prose (no numerics, no header-like row) — likely a side-by-side stitch with a different signature. **Risk**: hard to distinguish from a real 2-column prose-style table (e.g., a glossary). May want column 1's content to also overlap suspiciously with column 0's neighbor body prose.

**A3. Aggressive mash split for non-adjacent letter-letter boundaries** (carried over from iteration 2). Cases like `(location)Paper-and-penComputer` slip through because the camel-case rule needs `[a-z][A-Z]` adjacency and these have punctuation between. Test against `JavaScript`, `WordPress`, `macOS`, `O(n)Algorithm`. Add a unit test corpus before shipping.

**A4. Camelot's "0 cells but rendered as 1-col prose" upstream issue** (carried over). korbmacher Tables 5, 9 — these aren't really 0-cell extractions; docpluck/pdfplumber emits a 1-column "table" of prose (now demoted by iteration 6 to a code block). The CONTENT is preserved, but Tables 5 & 9 don't actually convey any tabular data. This is a docpluck library issue (table classifier accepts non-tabular regions); spike-side cleanup is already done by iteration 6.

**A5. ziano Table 1 fragmented sub-headers.** Rows like `<th>Win-:</th><th>Loss-</th>` followed by `<th>Uncertain</th><th>Uncertain</th>` are fragmented suffix-completions of `Win-Uncertain` / `Loss-Uncertain`. A simple "merge column-wise with no separator" rule would yield `Win-Uncertain` correctly. **Risk**: distinguishing fragmented suffix-cases from genuine 2-row headers is tricky; could test whether the cells in row 1 end with `-` or `:` (open punctuation) AND row 2's cell starts with a letter — strong fragment signal.

### Tier B — Bigger lift, surface scope explicitly to the user before starting

**B1. Multi-page table assembly** (carried over). `ip_feldman_2025_pspb` Table 2 spans 2 pages.

**B2. Nature / IEEE caption format** (carried over). Library-level change.

**B3. Apply spike improvements to `docpluck/tables/render.py:cells_to_html`** (carried over). Library work.

### Tier C — Lower priority

**C1. Tabula as second extractor.** Carried over.

**C2. Footnote rendering as a consolidated `## Footnotes` section.** Carried over.

---

## The iterative model (unchanged)

```
LOOP:
  1. AI-VERIFY: read each of the 7 output .md files for cut text, broken
     tables, malformed captions, missing/duplicated sections, body prose
     inside tables. For each issue, note: file, line, what's wrong, hypothesis.

  2. PICK HIGHEST-IMPACT ISSUE: most papers affected OR biggest visual impact
     OR on the "disappearing text" list.

  3. FIX in splice_spike.py (or upstream camelot_extract.py / extract_structured.py
     if needed). Add a unit test for the changed behavior.

  4. RUN TESTS: cd docs/superpowers/plans/spot-checks/splice-spike &&
     python -m pytest test_splice_spike.py. Must be 56+/56+ passing.

  5. RE-RENDER all 7 papers using the bash one-liner below.

  6. CHAR-RATIO + WORD-LOSS AUDIT: see "Audit one-liner" below. Real losses
     are content words missing from the new output (verify with grep). Hyphenated
     fragments that resolved into full words (e.g., "desirabil" → "desirability")
     are NOT losses — verify the full word exists.

  7. VISUAL VERIFY: open the 1-2 most-affected files in your viewer.

  8. COMMIT with a clear message naming the fix and audit numbers.

  9. REPORT to user.

GOTO LOOP

EXIT:
  - If a fix WOULD lose content (real ratio drop OR genuinely missing words), revert.
  - If two consecutive issues require multi-day work, STOP and ask user.
  - If user says "we're done."
```

---

## Bash one-liners

### Re-render the corpus (use `2>/dev/null`)

```bash
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck" && for f in korbmacher_2022_kruger efendic_2022_affect chandrashekar_2023_mp ziano_2021_joep ip_feldman_2025_pspb; do
  python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/apa/${f}.pdf" 2>/dev/null > "docs/superpowers/plans/spot-checks/splice-spike/outputs/${f}.md"
done && python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/nature/nat_comms_1.pdf" 2>/dev/null > "docs/superpowers/plans/spot-checks/splice-spike/outputs/nat_comms_1.md" && python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/ieee/ieee_access_2.pdf" 2>/dev/null > "docs/superpowers/plans/spot-checks/splice-spike/outputs/ieee_access_2.md" && echo RENDER_DONE
```

(~60–90 s; Camelot loads stream + lattice on every page.)

### Audit (char ratios + Note. preservation + word-loss vs HEAD vs pdftotext source)

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
print(f"{'Paper':30}  {'src':>6}  {'NEW':>6}  {'src_ratio':>9}  {'HEAD':>6}  {'delta':>6}  {'wlost':>5}")
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
    sign = '+' if delta >= 0 else ''
    print(f'{name:30}  {len(t):>6}  {len(new_clean):>6}  {ratio:>9.3f}  {len(head_clean):>6}  {sign}{delta:>5}  {len(lost):>5}')

note_re = re.compile(r'^Note\.\s+(.{5,200})', re.MULTILINE)
print('\n--- Note audit ---')
for pdf, name in papers[:5]:
    with open(f'../PDFextractor/test-pdfs/{pdf}.pdf','rb') as f:
        src,_ = extract_pdf(f.read())
    new = open(f'docs/superpowers/plans/spot-checks/splice-spike/outputs/{name}.md', encoding='utf-8').read()
    src_notes = note_re.findall(src)
    missing = [nt[:60] for nt in src_notes if nt[:25].strip() not in new]
    print(f'{name:30}  src_notes={len(src_notes):2}  missing={len(missing)}')
EOF
```

### Run unit tests (must stay green)

```bash
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck/docs/superpowers/plans/spot-checks/splice-spike" && python -m pytest test_splice_spike.py -v
```

Should report **56 passed** at HEAD (commit `a22c3e3`).

---

## Key files (where work happens)

Same as previous handoff. Reproduced here for self-containedness:

| Path | Role |
|---|---|
| [`docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/splice_spike.py) | **The standalone the user reviews.** Most fixes go here. |
| [`docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/test_splice_spike.py) | 56 unit tests at HEAD. **Must stay green after every change.** |
| [`docs/superpowers/plans/spot-checks/splice-spike/outputs/`](./superpowers/plans/spot-checks/splice-spike/outputs/) | The 7 regenerated `.md` outputs. |
| [`docpluck/tables/camelot_extract.py`](../docpluck/tables/camelot_extract.py) | Wraps Camelot. Library code. |
| [`docpluck/extract_structured.py`](../docpluck/extract_structured.py) | Orchestrator. Library code. |
| [`docpluck/tables/captions.py`](../docpluck/tables/captions.py) | Caption regex (Nature/IEEE broadening lives here — see B2). |
| [`docpluck/tables/render.py`](../docpluck/tables/render.py) | Library `cells_to_html`. Lacks the spike's smart features. See B3. |

---

## Critical pitfalls (lessons accumulated across iterations 1–8)

All previous-iteration pitfalls remain in force, plus:

- **Don't naively colspan-merge adjacent identical header cells.** Tested in iteration 5 prep: ziano Table 1's `<th>Uncertain</th><th>Uncertain</th>` are FRAGMENTED SUFFIXES of `Win-Uncertain` / `Loss-Uncertain` (the prefixes `Win-` and `Loss-` were on the previous header row). Merging would lose information. The handoff's old "A2. adjacent-duplicate header colspan" suggestion needs a more sophisticated check — see Tier A5 above.

- **A 5+ paragraph fragment-run with a non-matching caption silently drops the WHOLE run.** This is the "Note. N=161" / "Note. N=235" content-loss bug from iteration 5. The fix preserves footnote-marker paragraphs but still drops numeric noise (preserves the dedup-vs-Camelot intent). When auditing for lost content, run the Note. audit specifically — the word-set audit alone won't catch numeric-cell loss.

- **Hyphenated fragments resolving into full words look like "lost words" in the audit.** When iteration 6 demoted spurious 1-col tables, the surrounding body prose flowed correctly — and `desirabil-ity` (which the audit's `\b[A-Za-z]{5,}\b` regex saw as just `desirabil`) became `desirability`. The "lost word" `desirabil` is replaced by the FULL word `desirability` in the new output. Always verify with `grep "<full-word>" output.md` before declaring a fix lossy.

- **Side-by-side merge detection requires DISTINCT labels.** Two `Table 1` cells in a row are NOT a stitch — they're a legitimate (if unusual) repeat-header. The detector's `len(set(labels)) >= 2` guard catches this.

- **The standalone is throwaway-by-design.** Library work (B2, B3) is a separate larger lift requiring user buy-in due to the PyPI release flow per `CLAUDE.md`.

---

## Suggested first move for the new session

1. **Verify the working tree is clean** (`git status`) and you're at commit `a22c3e3` or later on `main`.
2. **Re-render the corpus** with the bash one-liner above; confirm tests pass.
3. **Run the audit one-liner**; copy the table into your scratchpad.
4. **Read 2 outputs end-to-end**, looking for new issues. Compile a list of ≥ 3 specific issues with line references; map each to the A/B/C tier above.
5. **Pick the highest-impact issue from Tier A** (probably A1 — super-header column fold — concrete and testable; A5 if you prefer a smaller fix). Loop.
6. **If you hit a Tier B item**, surface it to the user before starting (per the `feedback_dont_deviate_from_directives.md` memory).

---

## Final note

Iterations 5–8 were content-preserving with full test coverage. The bar is high but reachable: each commit fixed something visible, added tests, held the corpus's char-ratio floor, and recovered or cleaned content rather than removing it. The pattern is: detect a specific Camelot/pdfplumber misclassification → handle it explicitly with a conservative guard → never break a working case.

Surface scope changes explicitly. Don't add features the user didn't ask for. When in doubt, ASK before applying it.

The next 3–5 fixes should be reachable with the same iterative loop. Tier A1 (super-header fold) and A5 (suffix-fragment merge) are good next candidates if you want safe wins; Tier A2 (side-by-side without Table-N signal) is bigger but high-impact for chandrashekar.
