# Handoff — Table Rendering Iteration (continue the push)

**For:** A fresh Claude session to continue improving table rendering quality across the docpluck corpus. The previous session ran out of context after substantial work; this handoff captures everything you need.

**The user's directive:** *"keep improving things until we see regressions or a block, for all types for all our corpus. I want us to push through and give it another major push to see how far we can go."*

**The user's hard rule:** *"disappearing text is unacceptable, that's the biggest nono."* If a fix removes content that was in the source PDF, revert. Char-count ratios (output / pdftotext source) should stay ≥ 0.97 across the corpus.

---

## Required reading before you touch code

1. [`LESSONS.md`](../LESSONS.md) — particularly L-001 (text-channel calibration), L-006 (Camelot decision + HTML addendum). **Don't relitigate decisions there.**
2. Memory: `MEMORY.md` index in your project memory folder, especially:
   - `project_camelot_for_tables.md` — Camelot is settled.
   - `feedback_dont_relitigate_table_lib.md` — don't propose pdfplumber tuning or new library swaps.
   - `feedback_dont_deviate_from_directives.md` — surface scope changes EXPLICITLY before narrowing them.
   - `project_html_tables_in_md.md` — HTML `<table>` is the standard rendering inside `.md`, not pipe-tables.
3. The 7 current outputs in [`docs/superpowers/plans/spot-checks/splice-spike/outputs/`](./superpowers/plans/spot-checks/splice-spike/outputs/) — read at least 2 fully (e.g., `korbmacher_2022_kruger.md`, `ip_feldman_2025_pspb.md`) before proposing fixes.

---

## What's already settled (don't relitigate)

| Decision | Why | Where recorded |
|---|---|---|
| **Camelot stream** is the table cell extractor (replaces pdfplumber's `whitespace_cells` / `lattice_cells`) | 5-option bake-off A/B/C/D/E on 2026-05-09. Camelot won decisively. | LESSONS L-006 |
| **HTML `<table>`** is the table rendering format inside the `.md` output, not pipe-tables | Side-by-side demo on real complex tables; pipe-tables can't represent merged cells, multi-line cells, or group separators | LESSONS L-006 addendum, memory `project_html_tables_in_md.md` |
| **pdfplumber stays for sections + F0 normalize + figure-bbox** | The section detector (`docpluck/sections/`) has 250+ calibrated tests; ripping pdfplumber out there is a multi-day rework with regression risk per L-001 | Discussed in handoffs 2026-05-09; user explicitly accepted "3 combo: pdftotext + pdfplumber + Camelot" | 
| **PyMuPDF / fitz** is permanently excluded | AGPL license, incompatible with closed-source SaaS app | LESSONS L-003 |
| **`pdftotext -layout` flag** is permanently excluded | Causes column interleaving | LESSONS L-002 |
| **U+2212 → ASCII hyphen normalization** is required | Breaks statistical pattern matching otherwise | LESSONS L-004 |

---

## The architecture (current state)

```
PDF
 │
 ├─► pdftotext (text channel, no -layout flag)
 │     │
 │     └─► docpluck.extract_pdf() → linear text with \f page separators
 │
 ├─► pdfplumber (layout channel)
 │     │
 │     ├─► docpluck.extract_pdf_layout → LayoutDoc
 │     │     │
 │     │     ├─► docpluck/sections/ → section boundaries (## headings)
 │     │     ├─► docpluck/figures/detect.py → figure bboxes
 │     │     └─► docpluck/normalize.py F0 step → layout-aware running-header strip
 │     │
 │     └─► (NOT used for table cells anymore — Camelot replaces this)
 │
 └─► Camelot stream + lattice
       │
       └─► docpluck/tables/camelot_extract.py → cell-bearing Tables
             ├─► extract_tables_camelot(pdf_bytes) → list[Table]
             └─► merge_camelot_with_docpluck() (currently unused; see "what's not done")
```

Output pipeline:

```
docpluck.extract_pdf_structured(pdf_bytes)
  ├─ pdftotext text (with \f page seps)
  ├─ tables = Camelot output (filtered to caption-anchored + caption-matched)
  └─ figures = caption-regex matches on text (no bbox in v2)

splice_spike.render_pdf_to_markdown(pdf_path)  ← USER REVIEWS THIS
  ├─ runs extract_pdf_structured
  ├─ extract_sections on text (uses pdfplumber via section detector)
  ├─ for each table: locate region in text via token fingerprint, splice as
  │   ### Table N
  │   *caption*
  │
  │   <table>...</table>
  ├─ build appendix for unlocated tables + figures
  ├─ post-process: dedupe ### Table N blocks, dedupe ## H2 sections,
  │   strip standalone fragments, etc.
  └─ output .md file
```

---

## Key files (where work happens)

| Path | Role |
|---|---|
| [`docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/splice_spike.py) | **The standalone the user reviews.** Most fixes go here. Has `pdfplumber_table_to_markdown()` (HTML rendering — name kept for API stability), `_format_table_md()`, `render_pdf_to_markdown()`, post-processing helpers. |
| [`docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/test_splice_spike.py) | 15 unit tests for the standalone. Synthetic inputs only. **Must stay green after every change.** |
| [`docs/superpowers/plans/spot-checks/splice-spike/outputs/`](./superpowers/plans/spot-checks/splice-spike/outputs/) | The 7 regenerated `.md` outputs. The user opens these in their viewer to review. |
| [`docpluck/tables/camelot_extract.py`](../docpluck/tables/camelot_extract.py) | Wraps Camelot, applies `_strip_running_header_rows`, `_drop_caption_first_row`, `_trim_prose_tail`, `_is_table_like` filter. Returns Tables in docpluck schema. Called from `extract_pdf_structured`. |
| [`docpluck/extract_structured.py`](../docpluck/extract_structured.py) | Orchestrator. Runs pdftotext → captions regex → Camelot → caption-matching → returns Result with text, tables, figures. Has `_extract_caption_text`, `_join_split_captions`, `_apply_placeholder`. |
| [`docpluck/tables/captions.py`](../docpluck/tables/captions.py) | Pure-text caption regex (`^\s*Table\s+(\d+)(?:[.:]|\s+[A-Z])`). Pdfplumber-free. |
| [`docpluck/tables/render.py`](../docpluck/tables/render.py) | `cells_to_html()` — used by docpluck library. **Does NOT yet have the smart features the standalone has** (continuation merge, col-0 wrap detection, group separators). Needs porting from `splice_spike.pdfplumber_table_to_markdown`. |
| [`docs/superpowers/specs/2026-05-08-unified-extraction-design.md`](./superpowers/specs/2026-05-08-unified-extraction-design.md) | The original spec. Phase 0 (splice spike) is done; phase 1 (full library integration) is partly done (Stage 1 only). |
| [`docs/superpowers/plans/spot-checks/splice-spike/html-fallback-demo.md`](./superpowers/plans/spot-checks/splice-spike/html-fallback-demo.md) | The demo that convinced the user to switch to HTML. Useful reference. |

---

## Recent commit history (relevant ones, newest first)

```
a696e38  docs(lessons): L-006 addendum — HTML tables inside markdown
c576766  spike(splice): switch to HTML tables (replaces pipe-table rendering)
a028628  spike(splice): more table polish + revert risky orphan-strip
cf4cf23  spike(splice): fix two regressions found by AI verification
6f359e3  spike(splice): post-Camelot quality optimizations
6784377  feat(tables): replace pdfplumber with Camelot stream (LESSONS L-006)
d514502  spike(splice): 4-way table extraction experiment results (A/B/C/D)
72a1b7e  spike(splice): update phase-0 report with iteration findings
721db1d  spike(splice): real markdown rendering — sections + tables + caption absorption
08079df  spike(splice): phase-0 report and recommendation (AI verification draft)
```

If you need to roll something back, `git reset --hard <sha>` is safe — the working tree is clean.

---

## Test corpus

| File | What it stresses |
|---|---|
| `apa/korbmacher_2022_kruger.pdf` | Many tables (17), 2-row headers, Easy/Difficult group separators, calibration paper |
| `apa/efendic_2022_affect.pdf` | Camelot bundles a small real table with 50 rows of body prose — `_trim_prose_tail` test |
| `apa/chandrashekar_2023_mp.pdf` | Long replication report, multiple section-detection edge cases |
| `apa/ziano_2021_joep.pdf` | Landscape side-by-side tables, rotated margin text |
| `apa/ip_feldman_2025_pspb.pdf` | Multi-line hypothesis cells (Table 2), 2-row column header (Table 1) |
| `nature/nat_comms_1.pdf` | Nature format — captions don't match `Table N: ` regex; 0 tables detected currently |
| `ieee/ieee_access_2.pdf` | IEEE format — same caption format issue; 0 tables detected currently |

PDFs live at `../PDFextractor/test-pdfs/<style>/<name>.pdf` (relative to project root). Project root: `C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck`.

---

## What works well (current state, 2026-05-10)

- **All sections render** as `## Heading` with full body text. No missing sections detected on the audit. Section-edits-eating-table-headings bug fixed at `cf4cf23`.
- **Tables render as HTML `<table>`** with `<thead>`, `<tbody>`, escaped specials. `<br>` inside cells handled correctly.
- **Continuation rows merge** — multi-line cells like `Thought about distant friends/family` (split by pdftotext at `/`) re-join into one cell.
- **Group separators detected** — "Easy" / "Difficult" / "Negative experiences" emit as `<tr><td colspan="N"><strong>...</strong></td></tr>`.
- **Captions** — full sentence captions extracted (was truncating at first `\n\n` mid-sentence; now extends to next sentence terminator).
- **Caption regex dedup** — body-text references to "Table 1" no longer duplicate the real caption.
- **`_is_data_cell`** correctly rejects citations like "p. 3" or "et al. (2020)" so body prose is no longer mis-classified as table data.
- **Running headers stripped** from Camelot output (journal name in any column, "Personality and Social Psychology Bulletin 00(0)" patterns).
- **15/15 unit tests pass.** Char ratios 0.97–1.42 across corpus.

---

## What's broken or needs work (the user has flagged "cut text issues")

The user reviewed the outputs on 2026-05-10 and reports they see *"some disappearing/cut text issues."* You need to AI-verify each output and find them. Possible sources I (the previous session) didn't fully audit:

1. **Camelot's `_trim_prose_tail`** drops trailing prose rows. If a real table has prose-y final rows ("Note. ..." or footnotes that look prose-y), they may be silently lost. Verify each table's last rows.
2. **`_is_table_like` rejection** — when a Camelot table is rejected entirely, no pipe-table is emitted and no fallback is shown. The original pdftotext text is still in the body, but if it was supposed to be a table, the structure is gone. Verify on chandrashekar (had a 100-line "Table 1" rejected as body prose).
3. **The dedupe of `### Table N` blocks** — when two blocks share a number, the lower-pipe-row one is removed entirely. If the removed block had unique caption or notes, content is lost. Verify by counting unique tables before/after dedupe.
4. **Section heading shrink for table edits** — the table region is truncated to end before a section heading inside it. The truncated portion of the table is lost (we don't move it to the appendix in this case). Verify on ip_feldman where Results / Discussion were affected.
5. **Caption extraction** — `_extract_caption_text` walks past `\n\n` until it finds a sentence terminator. If the caption REALLY ends mid-sentence (rare), it now extends too far and pulls in body prose. Audit a few captions for over-extension.
6. **Multi-row header detection is missing** — first row alone is `<thead>`; second row of the header (e.g., "Estimation / errora / error (%) / t-statistics" in ip_feldman Table 1) ends up as the first body row. Look at the demo file for what merged 2-row headers should look like.
7. **Repeated content in adjacent header cells** — should emit as `<th colspan="2">` (e.g., "Judgmental weight" / "Judgmental weight" → one `<th colspan="2">`). Currently they're separate cells. Look at korbmacher Table 1 in the demo file for the difference.

---

## What's NOT done yet (lower-priority / explicit follow-ups)

- **Apply HTML rendering inside the integrated docpluck library**, not just the standalone. `docpluck/tables/render.py:cells_to_html` already exists but doesn't have `_merge_continuation_rows`, `_is_group_separator`, col-0 wrap detection. Port from `splice_spike.pdfplumber_table_to_markdown`.
- **Nature / IEEE caption format** — `^Table\s+\d+\s*\|` (Nature), `^TABLE\s+[IVX]+` (IEEE roman numerals). Currently 0 tables detected on those papers. Broaden `TABLE_CAPTION_RE` in `docpluck/tables/captions.py`.
- **Footnote rendering** — currently inline parenthetical `(1)`. Spec says consolidated `## Footnotes` section at end. Not implemented.
- **Figure rendering** — currently caption-only italic. No image extraction. Maybe acceptable; verify with user.
- **Phase 1 of unified-extraction-design spec** — full library integration. Stage 1 (tables) is done; figures + F0 still use pdfplumber. The user said "we'll keep this 3 combo" so this can wait.
- **Tabula as a second extractor** — ChatGPT's research suggested it for cases Camelot fails. Adds dependency. Try only if Camelot is failing on a specific paper after all other fixes.

---

## The iterative model (the user's instruction)

This is the loop the user wants you to run until you hit regressions or genuine blocks:

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

  4. RUN TESTS: `cd docs/superpowers/plans/spot-checks/splice-spike && python -m pytest test_splice_spike.py`. Must be 15+/15+ passing.

  5. RE-RENDER all 7 papers. Use the bash one-liner below.

  6. CHAR-RATIO AUDIT: compute output_chars / pdftotext_chars per paper.
     If any ratio drops below 0.97, you may have introduced a
     disappearing-text regression. INVESTIGATE before continuing.

  7. VISUAL VERIFY: open the 1-2 files most affected by the fix in your
     viewer (or grep / sed-n the relevant region). Confirm the fix worked
     AND no new regressions appeared.

  8. COMMIT with a clear message naming the fix + linking to the issue.

  9. REPORT to user with: what was fixed, what remains, char-ratio table.

GOTO LOOP

EXIT:
  - If a fix WOULD lose content (char ratio < 0.97), revert and document.
  - If two consecutive issues require multi-day work (e.g., tabular OCR,
    rewriting section detection), stop and ask user for direction.
  - If user says "we're done."
```

---

## The bash one-liner to re-render the corpus

```bash
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck" && for f in korbmacher_2022_kruger efendic_2022_affect chandrashekar_2023_mp ziano_2021_joep ip_feldman_2025_pspb; do
  python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/apa/${f}.pdf" > "docs/superpowers/plans/spot-checks/splice-spike/outputs/${f}.md" 2>&1
done && python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/nature/nat_comms_1.pdf" > "docs/superpowers/plans/spot-checks/splice-spike/outputs/nat_comms_1.md" 2>&1 && python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/ieee/ieee_access_2.pdf" > "docs/superpowers/plans/spot-checks/splice-spike/outputs/ieee_access_2.md" 2>&1
```

(~60-90s on first run because Camelot loads stream + lattice on every page.)

## The bash one-liner for the char-ratio audit

```bash
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck" && for pdf in apa/korbmacher_2022_kruger apa/efendic_2022_affect apa/chandrashekar_2023_mp apa/ziano_2021_joep apa/ip_feldman_2025_pspb nature/nat_comms_1 ieee/ieee_access_2; do
  src=$(python -c "from docpluck import extract_pdf
with open('../PDFextractor/test-pdfs/${pdf}.pdf','rb') as f:
    t,_=extract_pdf(f.read())
print(len(t))" 2>&1)
  bn=$(basename "$pdf")
  out=$(wc -c < "docs/superpowers/plans/spot-checks/splice-spike/outputs/${bn}.md")
  ratio=$(python -c "print(f'{$out/$src:.2f}')")
  printf "%-30s pdftotext %6s  output %6s  ratio %s\n" "$bn" "$src" "$out" "$ratio"
done
```

Healthy ratios: 0.97 – 1.45. Below 0.97 = potential content loss; investigate before committing.

---

## Critical pitfalls (lessons from this session)

- **Don't optimize aggressively without auditing for content loss.** I added a `_strip_orphan_caption_fragments_near_tables` function that removed up to 12 lines preceding every `### Table N` heading. The user pushed back: it might lose unique content. I reverted. Same caution applies to any function that REMOVES lines/paragraphs.
- **Section detection finds spurious sections** — e.g., chandrashekar has `## Results` × 4 because figure captions starting with "Results of direct replication..." get classified as sections. Currently handled by `_dedupe_h2_sections` (drop the heading, keep the body). Don't try to "fix" the section detector itself — that's L-001 territory.
- **Don't change the H2-boundary regex in `_dedupe_table_blocks`** without checking it doesn't false-match `### Table N+1` lines (the regex `^## ` matches a substring offset that turns `### ` into `## `). The current `^##(?!#)\s` is correct.
- **Camelot is slow.** Each page invokes both stream and lattice flavors. Set `DOCPLUCK_DISABLE_CAMELOT=1` env var to skip Camelot entirely — useful for fast tests. The library tests use this.
- **The standalone is throwaway-by-design.** The user reviews the standalone outputs. The integrated library work happens in parallel but lags. Don't worry about keeping standalone perfectly modular — it's a spike, not a final API.

---

## Suggested first move for the new session

1. Re-render the 7 outputs (one-liner above).
2. Run the char-ratio audit (one-liner above).
3. Read `korbmacher_2022_kruger.md` and `ip_feldman_2025_pspb.md` end-to-end, looking for the "cut/disappearing text" issues the user flagged.
4. Compile a list of ≥5 specific issues with line refs. Prioritize. Pick the highest-impact one and fix it first, in the iterative loop.

---

## Final note

The user is patient with the work but rightly frustrated when fixes cause regressions or when scope creeps quietly. Surface scope changes explicitly. Don't add features the user didn't ask for. When in doubt about a fix, ASK before applying it. The feedback memory `feedback_dont_deviate_from_directives.md` is the canonical guide.

Good luck. The spec, the bake-off evidence, and the iterative loop are all there. The hardest decisions (which tool, which format) are settled. The remaining work is local refinement of the renderer until quality is acceptable.
