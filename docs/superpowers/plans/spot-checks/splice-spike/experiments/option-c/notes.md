# Option C: pdfminer.six word-bbox single-extractor — Notes

## Critical Finding: pdftotext -bbox-layout NOT AVAILABLE on this system

The experiment spec assumed `pdftotext -bbox-layout` would be available. It is not.
The installed `pdftotext` is **xpdf/Glyph&Cog v4.00** (`/mingw64/bin/pdftotext`).
`-bbox-layout` is a **Poppler-fork** flag that does not exist in xpdf.

**Closest viable analog used instead:** `pdfminer.six` (already installed, MIT-licensed,
not pdfplumber). `pdfminer.six` provides per-line bounding boxes via its layout analysis
engine at the `LTTextLine` level: each line has `(x0, y0, x1, y1)` in PDF-native points
with bottom-left origin. This is functionally equivalent to what `-bbox-layout` would
have delivered — per-element geometry that is entirely independent of pdfplumber.

The sample-pdftotext-bbox.html file shows what the pdfminer output looks like,
formatted in the same `xMin/yMin/xMax/yMax` style that `-bbox-layout` would use.

---

## Approach

**HYBRID** for ziano (pdfplumber detects table bbox, pdfminer extracts cell content).
**PURE pdfminer detection** for korbmacher (pdfplumber detects 0 tables — whitespace
tables without ruled lines are invisible to pdfplumber's lattice detector).

### Pipeline
1. Try `extract_pdf_structured()` → get pdfplumber table bboxes
2. If no tables detected, fall back to pure pdfminer detection:
   - Cluster all page lines by y-position into rows
   - Score each row by number of distinct x-column clusters
   - Find largest contiguous run of multi-column rows (data core)
   - Extend upward/downward to absorb header rows and single-col category labels
3. Filter `LTTextLine` objects to the table bbox
4. Remove decorative lines (pure "/" or "|" or single non-alphanumeric chars)
5. Cluster by y → rows; cluster by x within rows → columns
6. Build grid; render as pipe-table

---

## Coordinate-translation gotchas

1. **pdfminer vs pdfplumber y-convention**: pdfminer y=0 is bottom of page, y
   increases upward. pdfplumber `top`/`bottom` are distances from the TOP of
   the page (y-down). Translation: `pdfminer_y = page_height - pdfplumber_top`.

2. **Ligature characters in pdfminer output**: pdfminer renders PDF ligatures
   correctly as Unicode (ﬃ U+FB03 "ﬃ", ﬁ U+FB01, etc.). These are not ASCII
   and cause Windows cp1252 console errors but write fine to UTF-8 files.
   The actual cell content is accurate.

3. **pdfplumber bbox tuple format**: `extract_pdf_structured()` returns bbox as
   `(x0, top, x1, bottom)` tuple (not a dict). Initial implementation assumed
   a dict — fixed.

4. **Rotated margin text (ziano)**: The watermark/citation "I. Ziano et al."
   in the right margin is printed vertically — pdfminer gives one character per
   line at extreme x positions (~701pt). These persist even after decorative
   filtering because individual letters like "I", "Z", "i" pass the
   `len >= 1` filter. They appear as a spurious 15th column in ziano's output.

5. **Slash "/" lines as table rules**: ziano uses "/" characters at column
   positions to indicate missing data (printed as vertical column separators
   in the PDF). These were filtered by the decorative filter, but some remain
   in ambiguous positions.

---

## Per-table assessment

### korbmacher_2022_kruger.pdf — Table 1 (page 7)  
**VERDICT: NEAR-PERFECT**

Detection: pure pdfminer (pdfplumber found 0 tables for this paper — it's a
whitespace-ruled table, not a line-ruled table).

Result (12 rows × 5 columns):
- Header row: "Ability | Domain | Comparative | Judgmental weight | Judgmental weight" ✓
- Sub-header: blank | "difficulty1" | "ability2" | "of Own ability3" | "of Others' ability3" ✓
- Category label rows: "Easy" (blank data cells) ✓; "Difficult" (blank data cells) ✓
- All 8 data rows correct with statistical annotations (∗∗, ∗∗∗∗, –.25∗, etc.) ✓
- Significance stars (∗) correctly extracted ✓
- Minus signs (–) correctly extracted as Unicode minus ✓ (these would need
  normalization per LESSONS.md L-004 before downstream processing)

**Minor issues:**
- "Judgmental weight" appears twice in header (correct — two separate columns share
  that label in the original, disambiguated by sub-headers)
- The "Ability" column sub-header cell is blank (correct — no sub-label in original)

**Usable for production? YES**, with the following caveats:
- Requires pure pdfminer detection (pdfplumber misses this table entirely)
- Category label rows ("Easy", "Difficult") appear as data rows with blank cells
  rather than being merged into a rowspan — acceptable for most downstream uses

---

### ziano_2021_joep.pdf — Table 1 (page 2, landscape)  
**VERDICT: PARTIALLY USABLE, structural noise**

Detection: hybrid (pdfplumber bbox covers almost entire page: x 56–707, y 41–507).

**What worked:**
- All study row labels (Tversky & Shafir 1992, Kühberger et al. 2001, etc.) extracted ✓
- Numeric cell values (36, 38, 21 (32%), etc.) extracted ✓
- Statistical results (χ² values, p values, Cramér's V) extracted ✓
- "Paying to know" / "Choice under risk" two-table structure detected ✓
- Multi-line cells preserved (row author labels span 3 lines, correctly kept together)
- "(continued on next page)" note captured

**What failed:**
1. **Rotated margin text**: "I. Ziano et al." printed vertically in the right margin
   is extracted as individual characters per pdfminer line → creates a spurious
   15th column (should be 14: 7 per table × 2 tables) containing "I Z", "i a n",
   "o", "e t a", "l"
2. **Column count inflated**: 15 columns detected instead of 14 (2 × 7), because
   the margin text's x-position (~701pt) is treated as a real column
3. **"Paying to know" left-side data missing**: The "Paying to know" half's N/Win/Loss
   columns appear largely empty for Kühberger et al. rows (rows 26–45). This is
   because the original PDF has missing data indicated differently in those rows,
   and pdfminer doesn't see the "N" values that pdfplumber might infer from line rules
4. **"Choice Win" merged in col 3**: The header "Choice" and "Win" appear merged
   in the "Paying to know" sub-table because they are positioned very close in x
   (~169pt and ~205pt, within the 20pt X_COL_SNAP_PT threshold)
5. **`(cid:0)` character**: One minus sign in the Cramér's V CI appears as the
   unmapped glyph `(cid:0)` — this is a pdfminer limitation for custom glyph IDs,
   not a bug in the algorithm

**Usable for production? PARTIALLY** — data values are largely correct but structural
issues (extra column, merged header cells, sparse left-side data) would require
post-processing to produce a clean output.

---

## Critical: How viable is pure-pdftotext-only architecture?

### Summary verdict: **MAYBE — conditional YES for body tables, NO for complex landscape**

**Strengths of pdfminer as single-extractor:**

1. **Clean line bboxes**: At `LTTextLine` level, pdfminer gives precise per-line
   (x0, y0, x1, y1) that cleanly separate table rows. For korbmacher (a typical
   clean APA table), the y-separation between rows is ~17pt — trivially clusterable.

2. **No pdfplumber needed for cell text**: All cell content for korbmacher was
   extracted purely from pdfminer without any pdfplumber call.

3. **Pure detection works for whitespace tables**: pdfminer's column-count heuristic
   correctly identified korbmacher's table even though pdfplumber finds nothing there.
   This is a genuine advantage: pdfminer sees structure where pdfplumber sees nothing.

4. **One library, two jobs**: pdfminer gives both reading-order text AND geometry from
   a single extraction pass. The current architecture requires pdftotext (text) +
   pdfplumber (geometry). pdfminer could collapse both.

**Weaknesses / remaining problems:**

1. **Table detection still hard**: Pure pdfminer detection requires a heuristic
   (multi-column clustering). It will miss tables that span adjacent regions of
   a page (like ziano's two side-by-side tables that pdfplumber's bbox lumps together).

2. **Landscape + rotated elements**: pdfminer extracts rotated margin text faithfully,
   which creates spurious columns. A post-filter is needed.

3. **pdfplumber for table detection is still useful**: For ziano-style tables with
   explicit ruled lines, pdfplumber's bbox is precise. Pure pdfminer detection would
   struggle with two side-by-side tables (it sees them as one wide region).

4. **`-bbox-layout` is still unavailable**: The actual Poppler pdftotext with
   `-bbox-layout` flag is not installed. If the user wants this specific tool, they
   need `poppler-utils` installed (e.g., via conda or a different package manager).

5. **pdfminer's `LTTextBox` grouping is aggressive**: pdfminer groups lines into
   text boxes before presenting them. In column-interleaved layouts, boxes may span
   across columns. Going to `LTChar` level (individual characters) would give finer
   control but is significantly more complex.

### Recommendation to user

The **single-extractor dream is achievable** using pdfminer.six with this approach:

- **Drop pdfplumber for cell content**: pdfminer gives cleaner line-level geometry
  for typical APA tables, with correct Unicode (ligatures, special chars).
- **Keep pdfplumber ONLY for bbox detection** (as a detection signal, not for cell
  text extraction). This is a much smaller dependency surface.
- **OR** invest in pure pdfminer detection (more heuristics) to eliminate pdfplumber
  entirely — viable for most APA-style tables but will need special handling for
  landscape/rotated elements.

**If Poppler's pdftotext were installed**: `-bbox-layout` would give word-level bboxes
directly from the shell with no Python library overhead. The same algorithm implemented
here would work with that input. Consider `conda install -c conda-forge poppler` or
equivalent to test the true `-bbox-layout` option.

---

## Honest verdict

| Metric | Assessment |
|--------|-----------|
| korbmacher extraction quality | Excellent (near-perfect) |
| ziano extraction quality | Partial (data values OK, structure noisy) |
| Usable on korbmacher? | **YES** |
| Usable on ziano? | **NO** (without post-processing for rotated margin text) |
| Pure single-extractor viable? | **MAYBE** — needs pdfplumber for detection on complex layouts |
| pdfminer replaces pdfplumber for CELL CONTENT | **YES**, clearly |
| pdfminer replaces pdfplumber for TABLE DETECTION | **Partially** — works for whitespace tables, not for complex layouts |
| pdftotext -bbox-layout truly available? | **NO** on this system (xpdf v4.00 installed, not Poppler) |
