# Option B: pdfplumber word-cluster from scratch — Notes

## Algorithm Details

### 1. Word extraction
- `pdfplumber.open(path)`, crop to bbox from `extract_pdf_structured(thorough=True)`.
- `extract_words(x_tolerance=2, y_tolerance=2)` → Word objects (text, x0, top, x1, bottom).
- x_tol=2 correctly splits multi-word phrases like "Using a mouse" into individual words.
  At x_tol=3+ they merge into "Usingamouse" (no spaces in PDF glyph stream).

### 2. Y-cluster threshold
- 3pt. Tested: asterisk superscripts appear 3-4pt above the data text baseline.
  Y-tol=3 correctly keeps them as separate y-clusters.
- Asterisk-only cluster detection: `re.fullmatch(r'[\*∗†‡§]+', text)`.
  These rows are folded into the adjacent logical row.

### 3. Column inference (bimodal gap method)
- **Key insight**: don't use header rows for column inference — multi-line
  headers have different word spacing than data rows.
- Infer columns from DATA rows only (after header_zone detection).
- Compute all sequential inter-word gaps per data row (x0[i+1] - x1[i]).
- Sort gaps → find the largest jump in the distribution ("bimodal split").
- Threshold = midpoint between the two gap populations.
- For korbmacher: within-word gaps are 2-3pt, inter-column gaps are 40-100pt.
  Bimodal split correctly fires at ~20pt → 5 correct columns: [97, 209, 276, 365, 460].
- Column start candidates: first word of each row + any word after a column-boundary gap.
- Cluster those candidates with the same threshold to get final column x0 positions.

### 4. Multi-line cell detection
- A y-cluster is a continuation of the pending row if:
  - Vertical gap < 7pt (close to previous row's bottom)
  - AND the new cluster has no word in column 0 (continuation of mid-table cells)
- This handles "exp. 1 (between-\nsubject)" style multi-line row labels.
- Limitation: fails when continuation rows DO have a col-0 word (gets treated as new row).

### 5. Side-by-side table detection
- For each y-cluster with >= 4 words: compute max-gap and median-gap.
- Trigger: max_gap > 60pt AND max_gap/median_gap > 4.0
- Valid x range: 20%-80% of bbox width (exclude edge artifacts).
- Score clusters by count × centrality (prefer x near center of valid range).
- Threshold: detected gap must appear in >= 20% of qualifying rows.
- Tuning log:
  - Initial threshold (50pt absolute, 5x ratio, 30% rows): korbmacher false-positive.
  - After adding 20%-80% bbox validity filter: korbmacher correctly no-split.
  - Ziano split detected at x=288 instead of correct x~354.
  - Root cause: continuation rows ("exp. N (between-subject) (%)") have a
    large gap at x~285 within the LEFT table itself, outvoting the real split at ~354.

### 6. Header zone detection
- Top 25% of bbox height = header zone.
- Count consecutive y-clusters fully within header zone.
- Minimum 1 cluster.

---

## Per-Table Assessment

### korbmacher_2022_kruger.pdf — Table 1 (page 7)

**Detected columns**: 5 — correct (ability domain, difficulty rating, % above average,
judgmental weight 1, judgmental weight 2).

**Row structure**: 10 data rows — correct (Easy×4 + Difficult×4 ability domains,
plus "Easy" and "Difficult" section headers).

**Data accuracy**: ✓ All numeric values in correct columns:
- "Using a mouse | 3.1 | 58.8 | 0.21 | 0.06" ✓
- "Driving | 3.6 | 65.4 | .89 | –.25" ✓
- etc.

**Issues**:
1. Header row merges multi-line column headers into one row — "Domain 1 difficulty"
   instead of separate "Comparative difficulty" column. The 3-line header (Ability | Domain,
   1/2/3, difficulty/ability) collapses to one noisy row.
2. Significance markers (∗∗, ∗∗∗∗) are folded into the data cells they annotate —
   e.g. "58.8 ∗∗∗∗" rather than clean "58.8". Makes cells messy but values are findable.
3. "Easy" and "Difficult" section headers appear as data rows with empty numeric cells —
   structurally correct, just aesthetically noisy.

**Verdict: USABLE** — the data values are correctly assigned to columns. A downstream
LLM or human reader can parse the values. The header is garbled but column ORDER is right.

---

### ziano_2021_joep.pdf — Table 1 (page 2, landscape, side-by-side)

**Split detection**: ✓ Split IS detected, but at x=288 instead of correct x≈354.

**Root cause of wrong split_x**: The PDF has many continuation rows like:
  `exp. 3 (within-   (%)   (80%)1  (37%)1  (43%)1`
These rows (left-table study names + their Accept/Reject % columns) have a large
gap at ~283pt — WITHIN the left table, between the study-name col and % cols.
This cluster (6 rows) outvotes the real split cluster at ~354pt (5 rows).

**Effect of wrong split**:
- Left table: 2 columns instead of ~7. All Win/Loss/Uncertain data and the first
  ES column get included in left. Renders as unstructured text blobs.
- Right table: 1 column. All right-table data collapses into single column.
- The structured content IS present but unreadable as a table.

**Additional challenges that make ziano hard regardless of split**:
1. The caption row ("Table 1 Descriptive and omnibus...") is inside the bbox and
   gets captured as table data.
2. The column header row (N/Choice/Win/Loss/Uncertain/Inferential) spans BOTH
   sub-tables without a visible gap — makes header detection ambiguous.
3. The running header "I. Ziano et al. / JournalofEconomicPsychology83(2021)102350"
   appears in the middle of the table bbox (landscape page, running header placed
   at the side).
4. Some data cells contain compound values like "22 (31%)1" (count + percentage +
   superscript note), making text-based column alignment unreliable.

**Verdict: NOT USABLE** for ziano in current form. The split is in the wrong place,
column structure collapses, and the running header/caption contaminate the output.

---

## Edge Cases Observed

1. **Superscript significance markers between rows**: Korbmacher places ∗∗, ∗∗∗∗ etc.
   in separate y-clusters between the data rows. These cluster at top~182, 200, 217, etc.
   Correctly identified as asterisk rows and folded. But they attach to the NEXT row
   (implemented) vs PREVIOUS row (more semantically correct — they annotate the row above).
   The test: "Using a mouse" at top=186.7 is followed by asterisks at top=200.3 which
   then precede "Driving" at top=204.0. The asterisks should annotate Driving's PRECEDING row.

2. **Multi-word ability names**: "Using a mouse", "Riding a bicycle", "Saving money",
   "Telling jokes", "Playing chess" — correctly captured as single col-0 values
   because multi-word continuations are merged.

3. **Landscape PDF (ziano)**: The page rotation doesn't affect pdfplumber coordinate
   extraction — coordinates are returned in the post-rotation space. No special handling needed.

4. **Running header in bbox (ziano)**: "I. Ziano et al." and journal name appear
   inside the cropped table region because the table bbox is very tall (encompasses
   the running header area in landscape). This is a bbox detection issue, not a
   word-clustering issue.

5. **Multi-word merged tokens (x_tol=3+)**: At x_tolerance=3, pdfplumber merges
   "Usingamouse" into one token, losing word boundaries. At x_tolerance=2, they
   stay separate. For column inference, separated words require the bimodal-gap approach;
   merged words would simplify column finding but lose readable text.

---

## Honest Verdict

**Option B (word-cluster from scratch) — overall assessment:**

**Viable for clean single tables (korbmacher-style)**: YES, with caveats.
- Column inference works when: data rows are consistent, column gaps >> within-word gaps.
- The bimodal gap method correctly handles the 5-column APA stats table.
- Asterisk row detection + folding preserves the data flow but embeds noise.
- Header is reconstructed but garbled (multi-line headers become one line of concatenated text).
- Time to tune: ~60% of budget spent on column inference alone.

**Viable for side-by-side tables (ziano-style)**: NO in current form.
- The side-by-side detection finds A split but at the wrong x position.
- The continuation-row gap artifact is a real problem: study name + data % rows
  create a false "large gap" inside the left table that outvotes the real inter-table gap.
- Even with correct split, both sub-tables have 7+ columns with complex multi-line headers
  that the current header-inference system can't reconstruct.
- Would need: explicit detection of "Paying to know" and "Choice under risk" label rows
  as table-group headers, then treat them as the true split anchors.

**Compared to lattice/whitespace approaches**:
- More robust to tables with NO visible grid lines.
- Much more fragile on complex side-by-side layouts.
- Algorithm complexity: HIGH. 4+ separate heuristics (y-cluster, asterisk, bimodal-gap,
  side-by-side) each requiring parameter tuning.
- The korbmacher result is arguably better than pdfplumber's lattice (which returns 0 cells)
  because the word-cluster approach doesn't require grid lines.

**Time spent**: ~75 minutes (exceeded 45-min target).
