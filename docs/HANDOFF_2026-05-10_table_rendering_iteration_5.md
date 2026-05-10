# Handoff — Table Rendering Iteration 5 (continue the push, 27-paper corpus, 132 tests)

**For:** A fresh Claude session to continue improving table rendering quality across the docpluck corpus, picking up from where iteration 4 of 2026-05-10 left off (commit `55fcfa4`).

**The user's directive (still in force):** *"keep improving things until we see regressions or a block, for all types for all our corpus. I want us to push through and give it another major push to see how far we can go. As long as we can find ways to improve without regressions or blockers with reasonable investment, let's try and keep at it."*

**The user's hard rule (still in force):** *"disappearing text is unacceptable, that's the biggest nono."* If a fix removes content that was in the source PDF, revert. Verify with **word-level** counts (`\b\w+\b`), not just char ratios — char ratios can drop legitimately when stripping HTML tag tokens or visual filler (see iter 22 below).

---

## What changed in the previous session (commits `fdf3022` → `55fcfa4`)

Five bite-sized iterations were committed to `main`. Each is independently revertable. **132 unit tests pass at HEAD** (was 104 two sessions ago); zero word-level content loss across all iterations on the 27-paper corpus.

| SHA | Iter | Tier | What landed |
|---|---|---|---|
| [`f7e1750`](https://github.com/giladfeldman/docpluck/commit/f7e1750) | 18 | A1 | **Strip `Table N.` caption echoes after `</table>`.** Extends iter-13's `_strip_redundant_fragments_after_tables` to recognize a full `Table N. ...` / `Table N: ...` caption echo (regardless of length / terminal period) when (a) the line's table number matches the preceding `### Table N` heading, and (b) every word stem in the payload is already in the rendered caption + cells. Caught 2 papers: `sci_rep_1` (1.183 → 1.175), `ieee_access_4` (1.179 → 1.176). |
| [`85fc37d`](https://github.com/giladfeldman/docpluck/commit/85fc37d) | 19 | A3 | **Fix `Figureure 6` typo in figure-label normalization.** `_wrap_table_fragments` had `re.sub(r"^Fig\.?", "Figure", ...)` with no negative lookahead — when caption_label was already `Figure 6`, the regex matched the `Fig` prefix and prepended a second `ure`. Added `(?!ure)` lookahead. Caught 4 occurrences across 3 papers: `demography_1` (1×), `jama_open_1` (1×), `jama_open_2` (2×). |
| [`bdf783f`](https://github.com/giladfeldman/docpluck/commit/bdf783f) | 20 | A4 | **Join hyphen-broken lines without dropping the hyphen.** New `_fix_hyphenated_line_breaks` pass joins lines ending in `[a-zA-Z]-` to the next line when the continuation starts with an alphabetic char. **Conservative rule: ALWAYS keep the hyphen** (real compounds like `self-control`, `meta-analysis`, `socio-economic` far outweigh genuine pdftotext word-internal soft-hyphen breaks). Skips HTML tables, fenced code blocks, headings, numeric ranges. Catches `Meta-\nProcesses` → `Meta-Processes` in amj_1 captions. **Initial impl drop-hyphen variant ate compound words; current variant zero-loss.** |
| [`47aabff`](https://github.com/giladfeldman/docpluck/commit/47aabff) | 21 | A5 | **Merge significance-marker rows as `<sup>` superscripts.** Camelot splits regression tables into 3 rows per variable (estimate / SE / stars). New `_merge_significance_marker_rows` detects rows whose only populated cells match `[*∗†‡§+#]+` and merges them as superscripts on the most recent NUMERIC estimate row above. Three guards: walk-back targets only PURELY-NUMERIC rows (skips `Ref.` text-anchors); skip empty target cells; preserve marker row if no attach possible. Uses `_SUP_OPEN/_CLOSE` placeholders that survive `_html_escape`. Affected social_forces_1 only (1.294 → 1.263); 62 estimate cells gained correct markers; 19 orphan marker rows preserved (couldn't safely attach). |
| [`55fcfa4`](https://github.com/giladfeldman/docpluck/commit/55fcfa4) | 22 | C1 | **Strip PDF leader-dots from cell content.** New `_strip_leader_dots` regex-strips runs of ≥4 dot-space pairs (`. . . . . .`) — these are visual alignment fillers from PDF table layouts, not data. Affected `ar_royal_society_rsos_140072` only (T2 ethogram). 60458 → 47206 chars (-22%, ~12KB of pure dot-noise removed). Word delta -62 = exclusively HTML tag tokens (`td`, `br`, `tr`); zero real-content word loss. **Note: this paper's char ratio is now 0.775, technically below the 0.95 alarm threshold, but the drop is purely from removing visual filler.** Future low-ratio audits should distinguish content loss from filler removal. |

If you need to roll back any commit, the working tree is clean, `git reset --hard <sha>` is safe.

---

## Current state of corpus quality (2026-05-10, post-iteration-22)

Verified on the **27-paper corpus**. Char ratios are computed from output / pdftotext source.

| Paper | src | output | ratio | flag | notes |
|---|---|---|---|---|---|
| `apa/korbmacher_2022_kruger` | 98311 | 106647 | 1.085 | | stable |
| `apa/efendic_2022_affect` | 52293 | 60505 | 1.157 | | stable |
| `apa/chandrashekar_2023_mp` | 112817 | 111633 | 0.990 | | stable |
| `apa/ziano_2021_joep` | 43478 | 56665 | **1.303** | bloat | T1 stitched 14-col — Tier B |
| `apa/ip_feldman_2025_pspb` | 88431 | 103353 | 1.169 | | stable |
| `nature/nat_comms_1` | 76850 | 75352 | 0.981 | | no detected tables — Tier B |
| `ieee/ieee_access_2` | 71909 | 59397 | **0.826** | low | pre-existing extraction issue — Tier B |
| `ama/jama_open_1` | 50456 | 58169 | 1.153 | | iter-19 cleanup |
| `ama/jama_open_2` | 48068 | 53026 | 1.103 | | iter-19 cleanup |
| `aom/amc_1` | 74623 | 73954 | 0.991 | | tables flattened to prose — partial |
| `aom/amj_1` | 126454 | 123217 | 0.974 | | iter-20 caption-fix; some figure captions still 2-line |
| `aom/amle_1` | 135600 | 111145 | **0.820** | low | 12 of 13 source tables not detected — Tier B |
| `apa/chan_feldman_2025_cogemo` | 81335 | 88063 | 1.083 | | iter-16 demoted body-prose |
| `apa/chen_2021_jesp` | 136836 | 187008 | **1.367** | bloat | T9/T10 side-by-side merge fails — Tier B |
| `apa/ar_apa_j_jesp_2009_12_010` | 79332 | 87703 | 1.106 | | iter-16 win |
| `asa/am_sociol_rev_3` | 107541 | 111330 | 1.035 | | T1 caption is mash-text |
| `asa/social_forces_1` | 92567 | 116925 | **1.263** | bloat | iter-21 win (was 1.294); some orphan stars remain |
| `chicago-ad/demography_1` | 76008 | 76777 | 1.010 | | iter-19 fix |
| `chicago-ad/jmf_1` | 74796 | 64472 | **0.862** | low | No tables detected — Tier B |
| `harvard/bjps_1` | 92321 | 103252 | 1.118 | | T1 caption mash; T4 in unlocated appendix |
| `harvard/ar_royal_society_rsos_140066` | 22913 | 22540 | 0.984 | | no tables |
| `harvard/ar_royal_society_rsos_140072` | 60912 | 47206 | **0.775** | low | iter-22 stripped 12kB leader-dots — **NOT content loss** |
| `ieee/ieee_access_3` | 81412 | 79955 | 0.982 | | All tables dropped by Camelot — Tier B |
| `ieee/ieee_access_4` | 59154 | 69567 | 1.176 | | iter-18 (small) win; T1 still has body-prose `<th>`; T8 still has bibliography in thead |
| `nature/nat_comms_2` | 81475 | 76669 | 0.941 | low | Zero tables detected — Tier B |
| `nature/sci_rep_1` | 56139 | 65953 | 1.175 | | iter-18 win |
| `nature/nathumbeh_2` | 116101 | 115110 | 0.991 | | ToC dot-leaders mistaken for headings |

**Cross-corpus zero word-level content loss confirmed across iterations 18–22.**

---

## Required reading before you touch code

1. [`LESSONS.md`](../LESSONS.md) — particularly L-001 (text-channel calibration), L-006 (Camelot decision + HTML addendum). **Don't relitigate decisions there.**
2. The user's auto-memory in your project memory folder.
3. The previous handoff: [`docs/HANDOFF_2026-05-10_table_rendering_iteration_4.md`](./HANDOFF_2026-05-10_table_rendering_iteration_4.md).
4. **At least 3 outputs end-to-end**, ideally a mix of one ratio-stable APA, one bloated paper, and `ar_royal_society_rsos_140072.md` to see the iter-22 leader-dot strip in action (table at line ~63).

---

## What's still settled (don't relitigate)

All items from previous handoffs PLUS these new ones:

| Decision | Why | Where |
|---|---|---|
| **`Table N.` caption echo after `</table>` is stripped (subset check).** | iter 18 / `f7e1750`. | `_strip_redundant_fragments_after_tables` |
| **`Fig\.?` → `Figure` rewrite has `(?!ure)` lookahead.** | iter 19 / `85fc37d`. | `_wrap_table_fragments` |
| **Hyphen-broken lines join with hyphen preserved (never drop).** | iter 20 / `bdf783f`. Conservative — content > canonical form. | `_fix_hyphenated_line_breaks` |
| **Significance-marker rows merge as `<sup>` on numeric estimate row above.** Empty-cell guard prevents orphan sups. Walk-back skips text-anchor (`Ref.`) rows. | iter 21 / `47aabff`. | `_merge_significance_marker_rows` |
| **Leader-dot runs (≥4 dot-space pairs) stripped from cell content.** | iter 22 / `55fcfa4`. | `_strip_leader_dots` |
| **`_SUP_OPEN/_CLOSE` placeholders survive HTML escaping** (mirrors `_MERGE_SEPARATOR` pattern). | iter 21 / `47aabff`. | `_html_escape` |

---

## Remaining issues, prioritized for impact × risk

### Tier A — Worth attempting, content-preserving, ~1 iteration each

**A2. ieee_access_4 Table 1 body prose in `<th>` cell** (carried over). 14-line `<th>` cell containing full body prose. Iter-16 detector requires ≥80% prose-like cells; this table has 1 giant prose cell + many short header cells (mixed). Idea: independently detect a `<th>`/`<td>` cell that is itself ≥120 chars + multi-sentence + heading-like — split it out of the table and emit as a paragraph before/after the `<table>`. Medium complexity; impacts 1-2 papers.

**A6. ASA / IEEE big-CAPS bibliography entries leak into thead** (deferred from iter-4 attempt). Tried adding `^\[\d+\]` as STRONG-RH pattern; the row in question is too tangled (8 cells of bibliography fragments + 4 cells of real headers, all in row 0 of Camelot output). A targeted "blank cells matching `^\[\d+\]`" approach would only clean 2 cells across the corpus. Recommend skipping until a structural fix becomes possible.

**A7 (new). amj_1 / amc_1 figure captions split across 2 lines without hyphen** (e.g., `FIGURE 3 ... on Task` + `Processes (Study 1)`). These render correctly in markdown (newline becomes space) but visually fragment the caption block in the .md file. Idea: when a paragraph starts with `^(?:FIGURE|TABLE)\s+\d+\b` and doesn't end in a sentence terminator AND the next paragraph is short (≤15 words, ≤80 chars) AND doesn't itself look like a caption / heading / HTML, join with a space. Affects amj_1 (5×), amc_1 (4×), ieee_access_3 (3×), some others. Risk: merging real next paragraphs into captions — needs a tight short-line guard.

**A8 (new). social_forces_1 orphan marker rows above estimate rows** — 19 marker rows currently preserved by iter-21's safety guard (no numeric row above). These belong to the NEXT estimate row (`0 ACEs Ref. / *** / 1 ACE 2.25...` — the `***` belongs to `1 ACE` not `0 ACEs`). A forward-walk variant: when a marker row's IMMEDIATE NEXT row has numeric cells, attach there instead. Risk: forward-attach is more aggressive; may misattribute in edge cases. Worth attempting carefully.

### Tier B — Bigger lift, surface scope explicitly to the user before starting

**B1. Multi-page table assembly** (carried over).

**B2. Nature / IEEE caption format detection** (carried over). Affects nat_comms_1, nat_comms_2, ieee_access_3, jmf_1, amle_1, nathumbeh_2 — **the largest remaining quality gap**, since these papers have ZERO tables detected. Library-level fix needed in `docpluck/tables/captions.py`.

**B3. ziano T1 / chen T9-10: side-by-side merge without `Table N` signal** (carried over).

**B4. Apply spike improvements to `docpluck/tables/render.py:cells_to_html`** (carried over). Library work.

### Tier C — Lower priority

**C2. Tabula as second extractor** (carried over).

**C3 (new). nathumbeh_2 ToC dot-leaders mistaken for headings.** Different from iter-22 — these are in body prose, not table cells. Probably a section-detector issue — out of scope for the spike.

---

## The iterative model (unchanged from iter 4)

```
LOOP:
  1. AI-VERIFY: read each .md for cut text, broken tables, malformed
     captions, missing/duplicated sections, body prose inside tables.

  2. PICK HIGHEST-IMPACT ISSUE: most papers affected OR biggest visual
     impact OR on the "disappearing text" list.

  3. FIX in splice_spike.py. Add a unit test for the changed behavior.

  4. RUN TESTS: cd docs/superpowers/plans/spot-checks/splice-spike &&
     python -m pytest test_splice_spike.py. Must be 132+/132+ passing.

  5. RE-RENDER all 27 papers using the bash one-liner below.

  6. CHAR-RATIO + WORD-LOSS AUDIT:
     - Char ratio drop is fine IF word delta is purely HTML tag tokens
       (`td`, `tr`, `br`). It is NOT fine if real content words are
       lost — verify with `\b\w+\b` counter (see iter-22 word-level
       diff for the technique).

  7. VISUAL VERIFY: open the 1-2 most-affected files in your viewer.

  8. COMMIT with a clear message naming the fix and audit numbers.

  9. REPORT to user.

GOTO LOOP

EXIT:
  - If a fix WOULD lose real-content words (not tag tokens), revert.
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

### Re-render the new 20-paper corpus (parallelize via 3-4 subagents of 5-7 PDFs each)

```bash
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck" && for spec in "ama/jama_open_1" "ama/jama_open_2" "aom/amc_1" "aom/amj_1" "aom/amle_1" "apa/chan_feldman_2025_cogemo" "apa/chen_2021_jesp" "apa/ar_apa_j_jesp_2009_12_010" "asa/am_sociol_rev_3" "asa/social_forces_1" "chicago-ad/demography_1" "chicago-ad/jmf_1" "harvard/bjps_1" "harvard/ar_royal_society_rsos_140066" "harvard/ar_royal_society_rsos_140072" "ieee/ieee_access_3" "ieee/ieee_access_4" "nature/nat_comms_2" "nature/sci_rep_1" "nature/nathumbeh_2"; do
  name=$(basename "$spec")
  python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/${spec}.pdf" 2>"docs/superpowers/plans/spot-checks/splice-spike/outputs-new/${name}.err" > "docs/superpowers/plans/spot-checks/splice-spike/outputs-new/${name}.md"
done && echo NEW_DONE
```

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
def wc(s): return len(re.findall(r'\b\w+\b', s))
print(f"{'Paper':40}  {'src':>6}  {'out':>6}  {'ratio':>6}  {'words':>6}")
for pdf, name in papers:
    with open(f'../PDFextractor/test-pdfs/{pdf}.pdf','rb') as f:
        t,_ = extract_pdf(f.read())
    out = open(f'docs/superpowers/plans/spot-checks/splice-spike/{name}.md', encoding='utf-8').read()
    ratio = len(out) / len(t) if len(t) else 0
    flag = ''
    if ratio < 0.5: flag = 'CRASH'
    elif ratio < 0.95: flag = 'low'
    elif ratio > 1.20: flag = 'bloat'
    short = pdf.split('/',1)[1]
    print(f'{short:40}  {len(t):>6}  {len(out):>6}  {ratio:>6.3f}  {wc(out):>6}')
EOF
```

### Word-level diff (use this when char ratio drops, to verify it's tag-only)

```bash
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck" && PYTHONIOENCODING=utf-8 python -c "
import re, subprocess
from collections import Counter
def words(s): return re.findall(r'\b\w+\b', s)
PAPER='outputs-new/social_forces_1.md'  # change to suspect paper
text = open(f'docs/superpowers/plans/spot-checks/splice-spike/{PAPER}', encoding='utf-8').read()
res = subprocess.run(['git','show',f'HEAD:docs/superpowers/plans/spot-checks/splice-spike/{PAPER}'],capture_output=True,text=True,encoding='utf-8')
head = res.stdout
hw, cw = Counter(words(head)), Counter(words(text))
diffs = sorted([(cw[w]-hw[w], w) for w in set(hw)|set(cw) if cw[w]!=hw[w]])
for d, w in diffs[:20]: print(d, repr(w))
# If non-zero deltas are ONLY for tokens like 'td', 'tr', 'br', 'sup' it's tag-only — safe.
"
```

### Run unit tests (must stay green)

```bash
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck/docs/superpowers/plans/spot-checks/splice-spike" && python -m pytest test_splice_spike.py -v
```

Should report **132 passed** at HEAD (commit `55fcfa4`).

---

## Key files (where work happens)

Same as previous handoff. Reproduced here for self-containedness:

| Path | Role |
|---|---|
| [`docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/splice_spike.py) | **The standalone the user reviews.** Most fixes go here. |
| [`docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/test_splice_spike.py) | 132 unit tests at HEAD. **Must stay green after every change.** |
| [`docs/superpowers/plans/spot-checks/splice-spike/outputs/`](./superpowers/plans/spot-checks/splice-spike/outputs/) | The 7 existing-corpus regenerated `.md` outputs. |
| [`docs/superpowers/plans/spot-checks/splice-spike/outputs-new/`](./superpowers/plans/spot-checks/splice-spike/outputs-new/) | The 20 new-corpus regenerated `.md` outputs. |
| [`docpluck/tables/camelot_extract.py`](../docpluck/tables/camelot_extract.py) | Wraps Camelot. Library code. |
| [`docpluck/extract_structured.py`](../docpluck/extract_structured.py) | Orchestrator. Library code. |
| [`docpluck/tables/captions.py`](../docpluck/tables/captions.py) | Caption regex (Nature/IEEE broadening lives here — see B2). |
| [`docpluck/tables/render.py`](../docpluck/tables/render.py) | Library `cells_to_html`. Lacks the spike's smart features. See B4. |

---

## Critical pitfalls (lessons accumulated across iterations 1–22)

All previous-iteration pitfalls remain in force, plus:

- **Char ratio drop is not always content loss.** Iter-22 dropped `ar_royal_society_rsos_140072` from 0.993 to 0.775 — but the missing 13kB was 100% leader-dot visual filler with zero word content. **Always cross-check with word-token delta** (`\b\w+\b` counter) and confirm any non-zero word deltas are exclusively HTML tag tokens (`td`/`tr`/`br`/`sup`).

- **Conservative > canonical when uncertain.** Iter-20's first impl dropped hyphens for lowercase line-wraps (`socio-\neconomic` → `socioeconomic`). That eroded real compounds (`self-control` → `selfcontrol`). The reverted version always keeps the hyphen. The user's hard rule prefers preserved-but-slightly-clunky to silent erosion.

- **Walk-back guards matter.** Iter-21's first impl attached stars to `Ref.` text-anchor rows (`Ref.<sup>***</sup>`) — wrong direction in regression tables where stars belong to the NEXT estimate row. The fix: walk-back targets ONLY rows with at least one purely-numeric cell. Text-anchor rows are skipped.

- **HTML placeholders need to survive escaping.** Inserting `<sup>...</sup>` directly into cell content gets HTML-escaped to `&lt;sup&gt;...`. Use `\x00`-bracketed placeholders (`_SUP_OPEN`, `_SUP_CLOSE`, `_MERGE_SEPARATOR`) that `_html_escape` swaps to real tags AFTER escaping the user content. The pattern is now well-established for any post-merge HTML insertion.

- **Subagents that render PDFs sometimes fail silently.** A general-purpose agent dispatched to render 19 PDFs returned 0-byte files (truncated by `>` redirect at start). Always verify file sizes after subagent batch rendering, and re-render any 0-byte files inline if needed. The pattern of "many 0-byte stdout files with empty stderr" is the classic signature of a failed subagent batch.

- **The corpus is large enough to find new patterns each iteration.** Iter-22's leader-dot finding came from the 27-paper corpus only (the 7-paper corpus didn't have it). Each iteration that lands a fix on a previously-stable paper is a "found a new pattern" event — don't be surprised by these.

---

## Suggested first move for the new session

1. **Verify the working tree is clean** (`git status`) and you're at commit `55fcfa4` or later on `main`.
2. **Run the audit one-liner**; copy the table into your scratchpad. **Run pytest**; should report 132 passed.
3. **Read 2-3 outputs end-to-end**, looking for new issues. Compile a list of ≥ 3 specific issues with line references; map each to the A/B/C tier above.
4. **Pick the highest-impact issue from Tier A** — A2 (ieee_access_4 body prose `<th>`), A7 (multi-line caption joining), or A8 (forward-attach for orphan marker rows). All are content-preserving but each has subtle edge cases worth thinking through.
5. **If you hit a Tier B item**, surface it to the user before starting.
6. **Don't forget**: word-token diff is the source of truth for content-preservation. Char ratio is just a hint.

---

## Final note

Iterations 18-22 added 5 commits, kept the unit test suite green at every step (104 → 132 tests), never lost a single content word across the corpus while improving char ratios on 4 papers, fixing visible bugs (Figureure typo, caption echoes), and removing 22% of one paper's noise. The session pattern is reliable: pick a Tier A item, scope tightly, write the fix + tests + audit + commit in one bite-sized pass, then loop.

The biggest remaining quality gaps are Tier B (library-level), so future sessions may need to grow into the docpluck library proper, or focus on the still-fixable Tier A items in the spike.

Surface scope changes explicitly. Don't add features the user didn't ask for. When in doubt, ASK before applying it.
