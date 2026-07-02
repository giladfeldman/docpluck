# FINDINGS 2026-07-01 — efendic Table 2 capture + collabra_77859 Tables 2↔3 pairing

Two independent table-extraction fixes, diagnosed and implemented this session.
Written as a handoff because the **shared main tree is being churned by concurrent
`docpluck-iterate` sessions + Dropbox working-file reverts** (memory
`feedback_concurrent_iterate_sessions_shared_tree`, `feedback_dropbox_reverts_working_files`),
so a clean single-session corpus gate + commit was not safe. Backups of the two
changed library files are in this session's scratchpad
(`detect_FINAL2.py`, `extract_structured_FINAL2.py`).

---

## FIX 1 — efendic Table 2 (page 6) recovered: 0×0 stub → 11×5, all 8 coefficients

**File:** `docpluck/tables/detect.py` (clean on top of committed HEAD 4cea4c6 — HEAD
has none of these functions; fully attributable to this work).

### The task's premise was WRONG
The handoff said efendic Table 2 is "Camelot-invisible / likely image or vector /
OCR-tier WON'T-FIX; both stream AND lattice return []." **False.** Evidence:
- pdfplumber page 6 carries **all 8 coefficient rows as clean text chars** with
  well-separated column x0s (`[46, 257/265, 338, 414, 532/540]`). Not image-only.
- Blind Camelot `stream pages="6"` returns **2 junk tables** `(30,2)` + `(56,1)`
  (the grid mis-merged with the 2-column body prose below it) — NOT `[]`. Only
  `lattice` returns `[]`.
- **Region-driven `stream` with a tight `table_areas` recovers the table perfectly**
  — `(9,5)`/`(10,5)`, accuracy 99–100 %, matching the article-finder `reading`
  gold's 8 rows (Intercept −0.09 … PMA×dir×MA 0.16, B/SE/95%CI/p). The residual
  cosmetic glyph substitutions (`2`→−, `3`→×, `\`→<) are the SEPARATE documented
  DP-3 font issue (NotoSerif `uni:no`), handled downstream by cell-cleaning.

### Root cause (why the v2.4.99 region path produced no candidate)
1. **Whitespace-column detection was diluted by trailing body prose.**
   `_whitespace_columns_stable` computed a GLOBAL column-stability fraction over the
   whole 250-pt search window. The 8 clean 4-col table rows + ~5 body-prose rows
   (widths 6/7/9/10) → modal-4 matched only 8/16 rows = 0.50 < the 0.6 threshold →
   detection returned None → region fell back to `caption_only` and ballooned the
   250-pt (and, via footnote-union, 440-pt) window into the prose → Camelot stream
   mis-segmented the dominant prose columns → 0×0 stub.
2. **`_detect_footnote_below` over-reached.** It vacuumed EVERY smaller-font char
   below the grid into one "footnote" — the table Note (y≈225) PLUS the Figure 2
   caption + figure-note far below (y≈448–501, after a 223-pt gap) — pushing the
   region bottom to 509.
3. **The region was clipped to the caption width.** The `p` column sits ~44 pt
   right of the caption's right edge, so a caption-width search box dropped it.

### The fix (3 changes, each keyed on a layout invariant — paper-agnostic)
- **`_aligned_row_run`** (replaces the boolean `_whitespace_columns_stable`): find
  the LARGEST CONTIGUOUS run of column-aligned rows and return its tight bbox.
  Contiguous-run instead of global-fraction ⇒ trailing prose no longer vetoes a
  clean grid. Column-START alignment within a 12-pt tolerance (absorbs a
  right-aligned/centered numeric column's left-edge jitter — e.g. `−0.09` starts
  ~7 pt left of `2.56` — while staying far below a real table's ≥40-pt gutter),
  compared against the run's RUNNING per-column mean so one jittered row can't sever
  it. Tries every column-count that occurs ≥3× (via `_longest_aligned_run`), so a
  table is found even when body prose outnumbers its rows.
- **`_contiguous_top_block`** in `_detect_footnote_below`: keep only the small-font
  block contiguous with the grid bottom; stop at the first inter-row gap > 25 pt.
  A table Note is contiguous with its table; distant small-font content is not.
- **`_widen_to_page_content`**: widen the geometry SEARCH box's right edge to the
  page content margin so a table wider than its caption isn't clipped. **Applied
  ONLY to the aligned-run path**; the `caption_only` FALLBACK keeps the caption
  width (a widened fallback reaches sideways into a stacked neighbour table and
  makes region-driven Camelot mis-segment it — verified on cog_emo p13's stacked
  Table 8/9).

### Verified
- efendic Table 2 → `11×5`, 47 cells, all 8 gold B-coefficients present, across
  repeated runs.
- `tests/test_table_detect.py` (7) + detect/caption/whitespace unit suite (30)
  all pass.

### ⚠️ KNOWN SIDE-EFFECT (must fix on the settled tree before shipping FIX 1)
An isolated DETECT-only subset diff (detect@HEAD vs detect@mine, everything else —
incl. the concurrent pairing refactor — held constant) over 9 high-table-count
papers found, alongside the efendic-T2 and cog_emo-T9 IMPROVEMENTS, one **regression
on efendic Table 3** (page 7, the sibling non-manipulated-attribute table):
- baseline: `12×9`, clean, loose 9-col grid, no running header.
- with my change: `13×5` (tighter 5-col grid — actually CLOSER to the gold's 5-col
  shape) BUT row 0 is the page **running header** `"Efendic et al. 1179"`.
All 9 coefficient data rows are correct in BOTH; the defect is only the prepended
header row. Mechanism: my `_widen_to_page_content` shifted which candidate
`_pick_better_table` selects — the winning table is now the auto-detect `camelot_t9`
(which, being `pages="all"` and region-unconstrained, swept in the running header),
not the clean region candidate `t3` (which the isolated region-driven Camelot call
produces WITHOUT the header — verified). The fix is either (a) a leading
running-header-row strip on captured tables (general, keyed on the repeated-header /
`Author et al. + page-number` signature — the same one `normalize.py::_f0_strip_
running_and_footnotes` already detects in the text channel), or (b) make the clean
region candidate win here. Both need the settled-tree 101-PDF gate to confirm no new
regression, so this is queued, not landed in the churning shared tree.

The other 5 subset papers' apparent "regressions" in the raw diff are a diff
artifact (the main-side fingerprint had not finished those papers when the diff ran
— they were absent, not removed).

### DETECT-only isolated subset result (9 high-table-count papers, complete)
detect@HEAD vs detect@mine, concurrent pairing refactor held constant on both sides:
- **Improvements:** efendic T2 (0-stub → 11×5, all 8 coeffs), cog_emo T9 (0-stub →
  12×4), chandrashekar T7 (2×4 → 12×9) + T8 (3×3 → 15×9) — substantial recovery,
  plos_med T5 (2×3 → 15×3), efendic T3 columns tightened 9→5 (gold-correct shape).
- **Regression (1):** efendic T3 prepends the running-header row (documented above).
- **Unchanged:** ip_feldman (all 10 tables), jama_open_1, xiao_2021 (all 8),
  bmc_med_3 (all 7); maier T11 differs by 1 cell (Camelot-flake noise).
Net: strongly positive; one minor, well-understood regression queued for the
settled-tree fix. (The full 101-PDF gate for the COMBINED detect+pairing deltas is
still required before ship.)

---

## FIX 2 — collabra_77859 Tables 2↔3 same-page caption→table swap (non-deterministic)

**File:** `docpluck/extract_structured.py`. **CAVEAT: this delta sits ON TOP of a
concurrent-session global-assignment refactor** (`_assign_tables_to_captions_global`
+ `_best_assignment_for_page`, which replaced HEAD's greedy `_find_caption_for_table`
+ `_rescue_duplicate_starved_captions`). My delta must be reconciled with / re-applied
on whichever pairing architecture lands. It is small and portable (see below).

### Symptom
Page 7 carries two captions — "Table 2. Study 2 results" (a t/df/d stat grid) and
"Table 3. Study 4: Dish sets" (a categorical grid). docpluck **swapped their cells
run-to-run**: sometimes Table 2 got the Dish grid and Table 3 the stat grid. The
physical PDF captions AND the article-finder `reading` gold both put Study-2-results
at Table 2 and Dish-sets at Table 3 (Tables 4 = Separate/Joint replication analyses,
5 = comparison — both already correct).

### Root cause
The stat grids share NO descriptive words with their captions, so every token-overlap
score is 0 — EXCEPT a spurious `+1` from the bare digit **"2"** ("Table 2"/"Study 2")
matching a stray "2" in the Dish grid's content. That single false point beat the
geometrically-correct pairing; and where scores genuinely tied at 0, the tie fell to
Camelot's NON-DETERMINISTIC emission order → the swap.

### The fix (2 changes, both general)
1. **Exclude bare integers from `_CAPTION_TOKEN_RE`** (`[a-z]{3,}|\d+\.\d+` — drop
   the old `\d+(?:\.\d+)?`). A standalone digit (a table number, page number, count)
   matches indiscriminately and manufactures false overlap; a DECIMAL (`4.76`) is a
   real statistic and is kept. Removes the spurious "2" match → all page-7 scores 0.
2. **Reading-order tie-break** in `_best_assignment_for_page`: when token totals tie,
   prefer the assignment with fewer reading-order INVERSIONS — captions arrive sorted
   top-to-bottom, so their tables should be in the same top-to-bottom order
   (`_reading_order_ranks` from each Camelot table's bbox top edge). This is the
   caption-above-table layout invariant; it makes the zero-overlap case deterministic
   and correct instead of Camelot-order-dependent. Ranked strictly BELOW token score,
   so it never overrides a real overlap signal.

### Stale tests corrected (same file family)
`tests/test_tables_flatten_blank_header_recovery.py` — two real-PDF tests asserted
collabra rows against the pre-refactor mislabels; retargeted to the gold-correct
labels:
- `test_collabra_77859_table5_real_pdf` → `test_collabra_77859_table4_separate_eval_real_pdf`
  (the Separate-Evaluation t=6.23/df=257/d=0.76 row is gold Table **4**).
- `test_collabra_77859_table3_packed_arms_real_pdf` → `..._table2_packed_arms_real_pdf`
  (the Attractive Separate/Joint d=0.07 rows are gold Table **2**).

### Verified
- collabra Tables 2/3/4/5 correctly labeled + deterministic across repeated runs.
- Both retargeted tests pass; flatten/cell synthetic suite (134) passes.

---

## Verification status (HONEST)

- **Unit + functional: PASS.** Both fixes verified end-to-end against the article-finder
  `reading` gold (NEVER pdftotext), plus all touched unit suites green.
- **Full 101-PDF corpus regression gate: NOT cleanly completed this session.** The
  shared tree was churned by concurrent sessions (global-assignment refactor + a
  dropped-minus-CI flatten change + a v2.4.100 dup-rescue ship) and Dropbox reverted
  working files across ≥3 session restarts, so a baseline-vs-main structured diff
  isolating ONLY these two changes could not be produced. A partial 44-paper diff was
  contaminated by the concurrent refactor (it captured the greedy→global pairing
  change corpus-wide, not my delta). **Next session must run the guarded 101-PDF diff
  for these two deltas on a settled tree before shipping**, per the project's
  zero-regression rule.

## Integration checklist for the next (settled-tree) session
1. Re-apply / confirm FIX 1 (`detect.py`) — it is clean on HEAD, drop-in.
2. Re-apply FIX 2's 2-line-idea delta on whatever pairing architecture is current
   (bare-digit exclusion in the token regex + a reading-order tie-break). If the tree
   still has greedy `_find_caption_for_table`, the tie-break goes in its
   `(-score, char_start)` key; if global, in `_best_assignment_for_page` as done here.
3. Keep the two retargeted collabra tests.
4. Run the full 101-PDF structured guard-diff (per-FILE Camelot gating for flake) +
   AI-gold canary on efendic + collabra_77859 + a multi-table-page sample. Zero-regression bar.
