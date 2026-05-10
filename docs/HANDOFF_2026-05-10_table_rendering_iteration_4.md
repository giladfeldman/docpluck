# Handoff — Table Rendering Iteration 4 (continue the push, expanded corpus)

**For:** A fresh Claude session to continue improving table rendering quality across the docpluck corpus, picking up from where iteration 3 of 2026-05-10 left off (commit `8aee794`).

**The user's directive (still in force):** *"keep improving things until we see regressions or a block, for all types for all our corpus. I want us to push through and give it another major push to see how far we can go. As long as we can find ways to improve without regressions or blockers with reasonable investment, let's try and keep at it."*

**The user's hard rule (still in force):** *"disappearing text is unacceptable, that's the biggest nono."* If a fix removes content that was in the source PDF, revert. Char-count ratios (`output / pdftotext source`) should stay ≥ 0.97 across the corpus when tables exist.

**New as of iteration 3:** corpus expanded from 7 papers to **27 papers** spanning AMA, AOM, APA, ASA, chicago-ad, harvard, IEEE, Nature. The new 20 are in `docs/superpowers/plans/spot-checks/splice-spike/outputs-new/`.

---

## What changed in the previous session (commits a22c3e3 → 8aee794)

Nine bite-sized iterations were committed to `main`. Each is independently revertable. **104 unit tests pass at HEAD** (was 38 two sessions ago); zero word-level content loss across all iterations on the 7-paper corpus.

| SHA | Iter | What landed |
|---|---|---|
| [`65aa320`](https://github.com/giladfeldman/docpluck/commit/65aa320) | 9 (Tier A1) | Super-header column-wise fold — when row 0 has empty cells AND every populated cell has populated below, fold into row 1 with `<br>` joins. Iterative for 3-row super-super-sub. Folded korbmacher T7's `["", "", "", "Mean", "", "Effect", ""]` over `["Condition", ..., "size r", "95% CI"]`. |
| [`2affe9b`](https://github.com/giladfeldman/docpluck/commit/2affe9b) | 10 (Tier A3 variant) | Relaxed mash split — 3-char lowercase run + whitespace anchor + capital-followed-by-lowercase. Catches `lowPositive` / `lowNegative` in efendic Table 1 without false-splitting brand names like `macOS` (no whitespace anchor) or `WordPress` (preceded by uppercase). |
| [`ca44aa0`](https://github.com/giladfeldman/docpluck/commit/ca44aa0) | 11 (new) | Strip orphan `Table N: ...` captions + leaked header fragments before `### Table N` heading, gated by 4-char prefix-stem subset check against rendered table caption + `<th>` cells. Catches korbmacher T2/3/6/7/8/11 caption echoes + ip_feldman `Study 1b` / `Study 3` leaked headers. |
| [`13fecec`](https://github.com/giladfeldman/docpluck/commit/13fecec) | 12 (Tier A5) | Per-column suffix-continuation fold — `Win-` / `Loss-` over `Uncertain` merges to `Win-Uncertain` / `Loss-Uncertain` (no separator — the dash IS the separator). Conservative — only on exactly 2-row headers. |
| [`e2746b5`](https://github.com/giladfeldman/docpluck/commit/e2746b5) | 13 (new) | Strip leaked fragment lines AFTER `</table>` close. Symmetric to iter 11; ≤80 chars, ≤12 words, no terminal `.`. Catches efendic Table 1's trailing `Negative affect Positive affect ...` leak. |
| [`3ee9ad4`](https://github.com/giladfeldman/docpluck/commit/3ee9ad4) | **14 (CRITICAL crash fix)** | `_format_figure_md` previously raised `ValueError: substring not found` when a figure caption had a `". "` only in chars 0-39, nuking the entire output to 0 bytes. Switch from `.index()` to `.find()` with explicit start/end. Discovered when 20 new PDFs were rendered and **2 of 5 in batch 1 were entirely zero-bytes** (`jama_open_1`, `jama_open_2`). |
| [`6a2bcb7`](https://github.com/giladfeldman/docpluck/commit/6a2bcb7) | 15 (new) | `_drop_running_header_rows` — remove top rows that look like leaked page running headers / page numbers. STRONG signals (pure number, "et al.", journal CAPS, "Vol.", DOI/URL) anchor; WEAK signals (single cap word, "X and Y") only count when paired with strong. Has a "real content below" guard so a numeric-only real table isn't killed. Catches chan_feldman `<th>COGNITION AND EMOTION 1231</th>`, am_sociol_rev_3 `<th>Nussio</th>` etc. |
| [`8aee794`](https://github.com/giladfeldman/docpluck/commit/8aee794) | 16 + 17 (new) | **iter 16:** `_is_spurious_body_prose_grid` — when ≥80% of populated cells are prose-like (≥30 chars, ≥4 words, ≥2 lowercase), <10% numeric, avg cell ≥35 chars, demote the "table" to fenced code block. Catches ar_apa_j_jesp Table 1 (was ratio 1.453, now 1.106 — biggest single win). **iter 17:** in-row strong-RH cell strip — when the new top header row mixes a strong-RH cell with non-RH content, blank just the strong cell. Catches chan_feldman T5 `["1236", "Target article", "Replication", ...]`. |

If you need to roll back any commit, the working tree is clean, `git reset --hard <sha>` is safe.

---

## Current state of corpus quality (2026-05-10, post-iteration-17)

Verified on the **27-paper corpus** (7 existing + 20 new). Char ratios are computed from output / pdftotext source.

### Existing 7 (in `outputs/`)

| Paper | src | output | ratio | from session start |
|---|---|---|---|---|
| `apa/korbmacher_2022_kruger` | 98311 | 106648 | **1.085** | -1098 (iter 9, 11) |
| `apa/efendic_2022_affect`    | 52293 |  60506 | **1.157** | -227 (iter 10, 11, 13, 15) |
| `apa/chandrashekar_2023_mp` | 112817 | 111634 | **0.990** | -2864 (iter 9, 11, 16, 17) |
| `apa/ziano_2021_joep`        | 43478 |  56666 | **1.303** ⚠ bloat | -163 (iter 12). Stitched 14-col Table 1 — Tier B. |
| `apa/ip_feldman_2025_pspb`   | 88431 | 103354 | **1.169** | -3340 (iter 9, 11, 13, 17) |
| `nature/nat_comms_1`         | 76850 |  75353 | **0.981** | unchanged (no detected tables — Tier B) |
| `ieee/ieee_access_2`         | 71909 |  59397 | **0.826** ⚠ low | unchanged (pre-existing extraction issue, Tier B) |

### New 20 (in `outputs-new/`)

| Paper | src | output | ratio | flag |
|---|---|---|---|---|
| `ama/jama_open_1` | 50456 | 58172 | **1.153** | (was 0-byte CRASH; now renders) |
| `ama/jama_open_2` | 48068 | 53032 | **1.103** | (was 0-byte CRASH; now renders) |
| `aom/amc_1` | 74623 | 73954 | 0.991 | tables flattened to prose |
| `aom/amj_1` | 126454 | 123219 | 0.974 | tables shredded; ≥3 figure captions truncated mid-word |
| `aom/amle_1` | 135600 | 111146 | **0.820** ⚠ low | 12 of 13 source tables not detected — Tier B |
| `apa/chan_feldman_2025_cogemo` | 81335 | 88063 | **1.083** | iter 16 demoted body-prose appendix table |
| `apa/chen_2021_jesp` | 136836 | 187008 | **1.367** ⚠ bloat | T9/T10 side-by-side merge fails; T2 caption issue |
| `apa/ar_apa_j_jesp_2009_12_010` | 79332 | 87707 | **1.106** | **iter 16 win**: was 1.453 (80+ rows of body prose as 2-col table demoted to code block) |
| `asa/am_sociol_rev_3` | 107541 | 111330 | 1.035 | T1 caption is mash-text |
| `asa/social_forces_1` | 92567 | 119773 | **1.294** ⚠ bloat | T1 page-header in thead (partial); T3 sig-stars split rows |
| `chicago-ad/demography_1` | 76008 | 76780 | 1.010 | `### Figureure 6` typo (cosmetic) |
| `chicago-ad/jmf_1` | 74796 | 64472 | **0.862** ⚠ low | No tables detected — Tier B |
| `harvard/bjps_1` | 92321 | 103256 | 1.118 | T1 caption mash; T4 in unlocated appendix |
| `harvard/ar_royal_society_rsos_140066` | 22913 | 22540 | 0.984 | no tables; abstract dup |
| `harvard/ar_royal_society_rsos_140072` | 60912 | 60458 | 0.993 | T1 cells full of leader-dots `. . . . . .` |
| `ieee/ieee_access_3` | 81412 | 79955 | 0.982 | All tables dropped by Camelot — Tier B |
| `ieee/ieee_access_4` | 59154 | 69759 | 1.179 | T1 has body prose in `<th>` cell (not 80% prose-like, so iter 16 didn't fire) |
| `nature/nat_comms_2` | 81475 | 76671 | **0.941** ⚠ low | Zero tables detected — Tier B |
| `nature/sci_rep_1` | 56139 | 66407 | 1.183 | T1 caption RESTATED after `</table>` (iter-13 strip is too aggressive a guard for caption-style lines with periods) |
| `nature/nathumbeh_2` | 116101 | 115127 | 0.992 | Zero tables detected — Tier B; ToC dot-leaders mistaken for headings |

**Cross-corpus zero word-level content loss confirmed across iterations 9-17.**

---

## Required reading before you touch code

1. [`LESSONS.md`](../LESSONS.md) — particularly L-001 (text-channel calibration), L-006 (Camelot decision + HTML addendum). **Don't relitigate decisions there.**
2. The user's auto-memory in your project memory folder.
3. The previous handoff: [`docs/HANDOFF_2026-05-10_table_rendering_iteration_3.md`](./HANDOFF_2026-05-10_table_rendering_iteration_3.md). Most of its "what's already settled" still applies.
4. **At least 3 outputs end-to-end**, ideally a mix of one ratio-stable APA (`korbmacher_2022_kruger.md`), one bloated paper (`chen_2021_jesp.md` or `social_forces_1.md`), and one new-style journal (`ieee_access_4.md`, `bjps_1.md`).

---

## What's still settled (don't relitigate)

All items from previous handoffs PLUS these new ones:

| Decision | Why | Where |
|---|---|---|
| **Super-header rows fold column-wise into next row.** | iter 9 / `65aa320`. | `_fold_super_header_rows` in `splice_spike.py` |
| **Mash split has a relaxed 3-char rule with whitespace anchor.** | iter 10 / `2affe9b`. | `_split_mashed_cell` |
| **Orphan `Table N:` captions + leaked header fragments are stripped before `### Table N` heading.** | iter 11 / `ca44aa0`. | `_strip_redundant_caption_echo_before_tables` |
| **Per-column suffix-continuation fold for 2-row headers.** | iter 12 / `13fecec`. | `_fold_suffix_continuation_columns` |
| **Leaked fragment lines after `</table>` are stripped (subset of table words).** | iter 13 / `e2746b5`. | `_strip_redundant_fragments_after_tables` |
| **`_format_figure_md` uses `.find()` not `.index()`.** | iter 14 / `3ee9ad4`. CRITICAL crash fix. | `_format_figure_md` |
| **Top rows of table grid that are pure running-header content (page numbers / "et al." / journal CAPS) are dropped.** | iter 15 / `6a2bcb7`. | `_drop_running_header_rows` |
| **2-col body-prose grids (≥80% prose cells) demote to code block.** | iter 16 / `8aee794`. | `_is_spurious_body_prose_grid` |
| **In-row strong-RH cell strip when row mixes strong-RH with real header content.** | iter 17 / `8aee794`. | `_drop_running_header_rows` (post-process step) |

---

## Remaining issues, prioritized for impact × risk

### Tier A — Worth attempting, content-preserving, ~1 iteration each

**A1. Caption duplicate AFTER `</table>`.** sci_rep_1 line 268 has the full caption restated as plain text `Table 1.  Baseline characteristics of participants. Notes: All values...`. Iter 13's strip uses `≤80 chars + no terminal period` to recognize fragments — caption restatements are longer and end in period, so they slip through. Idea: extend iter 13 to ALSO recognize a line that starts with `Table N.` / `Table N:` (regardless of length) as a strip candidate when ALL its words are subsets of the rendered caption.

**A2. ieee_access_4 Table 1 body prose in `<th>` cell.** A 14-line `<th>` cell containing `For comparison, we use FID and Recall data...` (full body prose absorbed into header). The iter 16 detector requires ≥80% of populated cells to be prose-like, but this table is mixed (one giant prose cell + many short header cells). Idea: independently detect a `<th>` (or `<td>`) cell that is itself ≥120 chars + multi-sentence + heading-like — split it out of the table and emit as a paragraph before/after the `<table>`.

**A3. demography_1 `### Figureure 6` typo** (cosmetic). The label normalization concatenates `Figure` + `ure` somewhere. Easy 1-liner fix in caption normalization. Low impact but very visible.

**A4. Caption truncated mid-word at line break.** amj_1 has captions ending in `…on Meta-`, `…on Task` (Processes is on next line). The caption-tail rescue logic exists but doesn't handle hyphenated word continuation across line breaks. Idea: when a caption ends in `-` and the next line starts with a lowercase letter, splice them together.

**A5. social_forces_1 T3 significance stars split into separate rows.** Rows like `<tr><td></td><td>∗∗∗</td><td>∗∗∗</td>...</tr>` immediately follow rows with the actual estimates. The stars belong WITH the estimates above (table cell continuation). Idea: detect a row whose only populated cells are statistical-significance markers (`*`, `∗`, `†`, `(<num>)`) and merge into the previous row's cells with `<sup>` or inline.

**A6. ASA / IEEE big-CAPS bibliography entries leak into thead.** ieee_access_4 T8 has thead polluted with `[63] A.` / `van Kavukcuoglu, "Pixel...`. Add a "looks-like-citation" pattern (`^\[\d+\]\s+[A-Z]\.\s+[A-Z]\w+`) to the strong-RH set.

### Tier B — Bigger lift, surface scope explicitly to the user before starting

**B1. Multi-page table assembly** (carried over).

**B2. Nature / IEEE caption format detection** (carried over). Affects nat_comms_1, nat_comms_2, ieee_access_3, jmf_1, amle_1, nathumbeh_2 — **the largest remaining quality gap**, since these papers have ZERO tables detected. Library-level fix needed in `docpluck/tables/captions.py`.

**B3. ziano T1 / chen T9-10: side-by-side merge without `Table N` signal** (carried over from handoff 3). Bigger lift but high impact for those papers.

**B4. Apply spike improvements to `docpluck/tables/render.py:cells_to_html`** (carried over). Library work.

### Tier C — Lower priority

**C1. PDF leader-dots** (`. . . . . .`) survive into HTML cells (rsos_140072 ethogram tables). Strip in `_split_mashed_cell` or upstream.

**C2. Tabula as second extractor** (carried over).

---

## The iterative model (unchanged)

```
LOOP:
  1. AI-VERIFY: read each .md for cut text, broken tables, malformed
     captions, missing/duplicated sections, body prose inside tables.

  2. PICK HIGHEST-IMPACT ISSUE: most papers affected OR biggest visual
     impact OR on the "disappearing text" list.

  3. FIX in splice_spike.py. Add a unit test for the changed behavior.

  4. RUN TESTS: cd docs/superpowers/plans/spot-checks/splice-spike &&
     python -m pytest test_splice_spike.py. Must be 104+/104+ passing.

  5. RE-RENDER all 7 (or all 27) papers using the bash one-liner below.

  6. CHAR-RATIO + WORD-LOSS AUDIT: see "Audit one-liner" below.

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

### Re-render the existing 7-paper corpus

```bash
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck" && for f in korbmacher_2022_kruger efendic_2022_affect chandrashekar_2023_mp ziano_2021_joep ip_feldman_2025_pspb; do
  python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/apa/${f}.pdf" 2>"docs/superpowers/plans/spot-checks/splice-spike/outputs/${f}.err" > "docs/superpowers/plans/spot-checks/splice-spike/outputs/${f}.md"
done && python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/nature/nat_comms_1.pdf" 2>docs/superpowers/plans/spot-checks/splice-spike/outputs/nat_comms_1.err > docs/superpowers/plans/spot-checks/splice-spike/outputs/nat_comms_1.md && python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/ieee/ieee_access_2.pdf" 2>docs/superpowers/plans/spot-checks/splice-spike/outputs/ieee_access_2.err > docs/superpowers/plans/spot-checks/splice-spike/outputs/ieee_access_2.md && echo OLD_DONE
```

### Re-render the new 20-paper corpus

```bash
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck" && for spec in "ama/jama_open_1" "ama/jama_open_2" "aom/amc_1" "aom/amj_1" "aom/amle_1" "apa/chan_feldman_2025_cogemo" "apa/chen_2021_jesp" "apa/ar_apa_j_jesp_2009_12_010" "asa/am_sociol_rev_3" "asa/social_forces_1" "chicago-ad/demography_1" "chicago-ad/jmf_1" "harvard/bjps_1" "harvard/ar_royal_society_rsos_140066" "harvard/ar_royal_society_rsos_140072" "ieee/ieee_access_3" "ieee/ieee_access_4" "nature/nat_comms_2" "nature/sci_rep_1" "nature/nathumbeh_2"; do
  name=$(basename "$spec")
  python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/${spec}.pdf" 2>"docs/superpowers/plans/spot-checks/splice-spike/outputs-new/${name}.err" > "docs/superpowers/plans/spot-checks/splice-spike/outputs-new/${name}.md"
done && echo NEW_DONE
```

(~25-30 min for the 20 new ones; can be parallelized by dispatching 4 subagents of 5 PDFs each — see this iteration's setup for the pattern.)

### Audit (char ratios across all 27 papers)

```bash
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck" && PYTHONIOENCODING=utf-8 python << 'EOF'
import sys, re
sys.stdout.reconfigure(encoding='utf-8')
from docpluck import extract_pdf
papers = [
    ('apa/korbmacher_2022_kruger', 'outputs/korbmacher_2022_kruger'),
    ('apa/efendic_2022_affect', 'outputs/efendic_2022_affect'),
    ('apa/chandrashekar_2023_mp', 'outputs/chandrashekar_2023_mp'),
    ('apa/ziano_2021_joep', 'outputs/ziano_2021_joep'),
    ('apa/ip_feldman_2025_pspb', 'outputs/ip_feldman_2025_pspb'),
    ('nature/nat_comms_1', 'outputs/nat_comms_1'),
    ('ieee/ieee_access_2', 'outputs/ieee_access_2'),
    ('ama/jama_open_1', 'outputs-new/jama_open_1'),
    ('ama/jama_open_2', 'outputs-new/jama_open_2'),
    ('aom/amc_1', 'outputs-new/amc_1'),
    ('aom/amj_1', 'outputs-new/amj_1'),
    ('aom/amle_1', 'outputs-new/amle_1'),
    ('apa/chan_feldman_2025_cogemo', 'outputs-new/chan_feldman_2025_cogemo'),
    ('apa/chen_2021_jesp', 'outputs-new/chen_2021_jesp'),
    ('apa/ar_apa_j_jesp_2009_12_010', 'outputs-new/ar_apa_j_jesp_2009_12_010'),
    ('asa/am_sociol_rev_3', 'outputs-new/am_sociol_rev_3'),
    ('asa/social_forces_1', 'outputs-new/social_forces_1'),
    ('chicago-ad/demography_1', 'outputs-new/demography_1'),
    ('chicago-ad/jmf_1', 'outputs-new/jmf_1'),
    ('harvard/bjps_1', 'outputs-new/bjps_1'),
    ('harvard/ar_royal_society_rsos_140066', 'outputs-new/ar_royal_society_rsos_140066'),
    ('harvard/ar_royal_society_rsos_140072', 'outputs-new/ar_royal_society_rsos_140072'),
    ('ieee/ieee_access_3', 'outputs-new/ieee_access_3'),
    ('ieee/ieee_access_4', 'outputs-new/ieee_access_4'),
    ('nature/nat_comms_2', 'outputs-new/nat_comms_2'),
    ('nature/sci_rep_1', 'outputs-new/sci_rep_1'),
    ('nature/nathumbeh_2', 'outputs-new/nathumbeh_2'),
]
print(f"{'Paper':40}  {'src':>6}  {'out':>6}  {'ratio':>6}  flag")
for pdf, name in papers:
    with open(f'../PDFextractor/test-pdfs/{pdf}.pdf','rb') as f:
        t,_ = extract_pdf(f.read())
    out = open(f'docs/superpowers/plans/spot-checks/splice-spike/{name}.md', encoding='utf-8').read()
    ratio = len(out) / len(t) if len(t) else 0
    flag = ''
    if ratio < 0.5: flag = '⚠ CRASH'
    elif ratio < 0.95: flag = '⚠ low'
    elif ratio > 1.20: flag = '⚠ bloat'
    short = pdf.split('/',1)[1]
    print(f'{short:40}  {len(t):>6}  {len(out):>6}  {ratio:>6.3f}  {flag}')
EOF
```

### Run unit tests (must stay green)

```bash
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck/docs/superpowers/plans/spot-checks/splice-spike" && python -m pytest test_splice_spike.py -v
```

Should report **104 passed** at HEAD (commit `8aee794`).

---

## Key files (where work happens)

Same as previous handoff. Reproduced here for self-containedness:

| Path | Role |
|---|---|
| [`docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/splice_spike.py) | **The standalone the user reviews.** Most fixes go here. |
| [`docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/test_splice_spike.py) | 104 unit tests at HEAD. **Must stay green after every change.** |
| [`docs/superpowers/plans/spot-checks/splice-spike/outputs/`](./superpowers/plans/spot-checks/splice-spike/outputs/) | The 7 existing-corpus regenerated `.md` outputs. |
| [`docs/superpowers/plans/spot-checks/splice-spike/outputs-new/`](./superpowers/plans/spot-checks/splice-spike/outputs-new/) | The 20 new-corpus regenerated `.md` outputs. |
| [`docpluck/tables/camelot_extract.py`](../docpluck/tables/camelot_extract.py) | Wraps Camelot. Library code. |
| [`docpluck/extract_structured.py`](../docpluck/extract_structured.py) | Orchestrator. Library code. |
| [`docpluck/tables/captions.py`](../docpluck/tables/captions.py) | Caption regex (Nature/IEEE broadening lives here — see B2). |
| [`docpluck/tables/render.py`](../docpluck/tables/render.py) | Library `cells_to_html`. Lacks the spike's smart features. See B4. |

---

## Critical pitfalls (lessons accumulated across iterations 1–17)

All previous-iteration pitfalls remain in force, plus:

- **The crash bug at iter 14 was a serious wake-up call.** A single `ValueError` in `_format_figure_md` nuked entire documents to 0 bytes — the worst possible content-loss scenario. Always use `.find()` (returns -1) instead of `.index()` (raises) when scanning strings, and put try/except around the rendering loop if a single figure failure shouldn't kill the whole document.

- **Weak-RH detection (single cap-cased word) is intrinsically ambiguous** — `Variable` looks identical to `Nussio`. The row-level rule that requires a STRONG anchor in the same row before counting weak signals as RH is the safety mechanism. Don't loosen it.

- **The body-prose detector (iter 16) requires ≥80% of cells to be prose-like.** A table with 1 giant prose cell + 5 short stat cells (ieee_access_4 T1) doesn't qualify and stays as a broken table. A separate "lift big prose cell out of table" approach (Tier A2) is needed.

- **The audit can catch in-flight files at 0 bytes** — a render that's mid-write looks identical to a crash. Always re-check the file size at the end and re-run audit if any `outputs/` file is 0 bytes during render.

- **Subagents are the right tool for parallel rendering.** Rendering 20 PDFs serially takes ~30 min. Dispatching 4 agents of 5 PDFs each cuts that to ~7-10 min. The pattern is in this iteration's setup — see `Agent` calls.

- **The standalone is throwaway-by-design.** Library work (B2, B4) is a separate larger lift requiring user buy-in due to the PyPI release flow per `CLAUDE.md`.

---

## Suggested first move for the new session

1. **Verify the working tree is clean** (`git status`) and you're at commit `8aee794` or later on `main`.
2. **Run the audit one-liner**; copy the table into your scratchpad.
3. **Read 2-3 outputs end-to-end**, looking for new issues. Compile a list of ≥ 3 specific issues with line references; map each to the A/B/C tier above.
4. **Pick the highest-impact issue from Tier A** (probably A1 — sci_rep_1 caption duplicate, easy and visible; or A6 — ieee_access_4 bibliography in thead, smaller fix). Loop.
5. **If you hit a Tier B item**, surface it to the user before starting.

---

## Final note

Iterations 9-17 added 9 commits, kept the unit test suite green at every step, never lost a single content word, and improved char ratios across the corpus while expanding the test corpus from 7 to 27 papers. The iter-14 crash discovery is a reminder that the corpus expansion is HOW you find these issues — every time you cast the net wider, you find new patterns.

The biggest remaining quality gaps are Tier B (library-level), so future sessions may need to grow into the docpluck library proper, or focus on the still-fixable Tier A items in the spike.

Surface scope changes explicitly. Don't add features the user didn't ask for. When in doubt, ASK before applying it.
