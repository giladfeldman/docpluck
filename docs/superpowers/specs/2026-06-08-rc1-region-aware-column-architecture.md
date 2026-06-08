# RC-1 — Region-aware two-column reading-order architecture (design + start)

**Status:** Step 1 IMPLEMENTED 2026-06-08 (v2.4.82, default OFF). Step 2 (per-band region-aware crop) remains the multi-session work. This doc is the durable design + the precise gap analysis so the next session executes, not re-derives.

## Step 1 — IMPLEMENTED (v2.4.82, `DOCPLUCK_COLUMN_CORRECT_GENERAL`, default OFF)

The general-interleave flagged pages now join the O5 inversion pages under the gutter-strip detector + word-preservation guard when the flag is set. **AI-verified:** `j.jesp.2021.104154` numbered-section inversions 12+ → 4; `ip_feldman` B3 affiliation-leak + B4 mid-text-caption cleared. Ships dark (default off) because it is partial — table-bearing / no-clean-gutter pages stay untouched (that is Step 2). Flip the default after Step 2 lands.

**Reproducing the gap surfaced TWO pre-existing corruptions in `splice_column_corrected_pages` (fixed in v2.4.82, independent of the flag):**
- **Accept-any word splits:** pages outside the word-preserve set were accepted on any non-empty re-extraction; pdftotext column-crop split words straddling the crop-x (`jama_open_1` `adults`→`adu`, `ieee_access_3` `using`→`us`) — shipping in the DEFAULT on 5/26 baseline papers.
- **Cross-page boundary glue:** `extract_page_text_columns` returns page text without its trailing `\f`, so a corrected page's last word glued onto the next page's first word (`results`+`https`→`resultshttps`; running-header `J`→`fromj`).

**Fix:** word-preservation is now UNCONDITIONAL in the splice (every corrected page must be a pure reorder) + the page's trailing `\f` separator is re-attached. Param `word_preserve_pages` → `gutter_fallback_pages` (gutter detector opt-in only). **Validated: all 26 baseline papers preserve the raw pdftotext word-multiset under both flag settings** (`tmp/rc1_corpus_v2.py`). This means Step 2 can build on a splice that is now *guaranteed* word-faithful — any band-level crop it adds is gated by the same unconditional guard.

**Consequence for Step 2's scope:** the `jama_open_1` abstract (full-width title/byline band crossing the two abstract/sidebar columns) is exactly the case Step 1's whole-page crop CANNOT do without splitting words — so word-preservation now (correctly) rejects it and the page is word-correct-but-column-mixed. The per-band crop is the ONLY path to de-interleave it without corruption. Step 2 is therefore not optional polish; it is required to recover the reading order Step 1's safety guard had to give up.

**Evidence (2026-06-08 untested-corpus sweep):** column-interleave is the **dominant** defect on two-column APA papers — not just the ip_feldman/chandrashekar canaries. Confirmed on 4/4 two-column papers verified against article-finder golds:
- `j.jesp.2021.104154`: 12+ section-order inversions; Tables 3/7/9-10/12/14 broken (wrong-column data, merged, empty shells).
- `collabra.77859`: all 5 tables wrong-column data; paragraphs split at column breaks with continuations displaced 30-50 lines; possible stat corruption `M_age 59.3→39.3`.
- `collabra.37122`: `## Conclusion` after References+endmatter; headings lost mid-merge.
- (`s41467` Nature is NOT body-interleaved — single-column prose; its issue is figure-panel text injection, a separate finding.)

## What already exists (the foundation — do NOT rebuild)

`docpluck/extract_columns.py` (O5 / v2.4.75-80) is a working column re-extractor:
- `extract_page_text_columns(layout_doc, page_index, pdf_bytes, allow_gutter_fallback)` — re-extracts ONE page in left-then-right column order. Detects the midline two ways: `_detect_2col_midline` (word-center histogram) and `_detect_2col_midline_gutter` (full-height empty central gutter strip — the strong discriminator, center-constrained to [0.40W,0.60W]). Uses pdftotext column-crop (`-x -y -W -H`) per column for correct spacing.
- `splice_column_corrected_pages(raw_text, layout_doc, page_offsets, pages_to_fix, pdf_bytes, word_preserve_pages, changed_out)` — splices corrected pages back into raw_text. **Word-preservation guard**: a page in `word_preserve_pages` is accepted ONLY if the re-extraction preserves the substantial-word multiset (every alphabetic token len≥2) — a pure reorder that can't drop/fabricate text (rules 0a/0b).
- **Bilateral y-row gate** (in `extract_page_text_columns`): rejects pages where ≥30% of y-rows have words on BOTH sides of the midline — i.e. table pages (every table row spans both columns at the same y). This is what PROTECTS tables from being garbled by whole-page column correction. Bypassed only when `gutter_gated` (a clean full-height gutter proves no full-width row crosses center).

Detection already exists too:
- `normalize._detect_column_interleave_pages(text, page_offsets)` — flags general-interleave pages via Signature A (sentence-flip ≥6) + Signature B (bimodal short/long line density). Populates `report.column_interleave_pages`.
- `extract_columns._detect_reference_inversion_pages` — the narrow O5 case (reference entries before their own heading).

## The precise gap

1. **`_detect_column_interleave_pages` is SIGNAL-ONLY.** normalize.py:3813-3827 detects + records `report.column_interleave_pages` but **never calls `splice_column_corrected_pages` for those pages.** The comment says so explicitly ("no text rewrite this cycle — the column-aware re-extraction is the follow-up architectural work"). Only the O5 reference-inversion path (in `extract.py`) actually splices.
2. **Whole-page correction is too coarse for table-bearing pages.** `extract_page_text_columns` corrects a WHOLE page; the bilateral gate makes it SKIP (return "") any page with an embedded full-width table — leaving that page interleaved. Many failing pages are 2-col prose ABOVE/BELOW a full-width table on the same page → whole-page correction is rejected, so the prose stays interleaved.

## The plan

### Step 1 (SAFE incremental — feasible as a flag-gated cycle): wire general-interleave splice for gate-accepted pages
Wire `report.column_interleave_pages` → `splice_column_corrected_pages` in the extract path (where O5 already splices), with:
- `word_preserve_pages = ALL flagged pages` (every corrected page must preserve the word multiset — no text loss/fabrication, ever).
- `allow_gutter_fallback=True` (use the strong gutter discriminator).
- Behind a feature flag (e.g. `DOCPLUCK_COLUMN_CORRECT_GENERAL=1` or a `normalize_text` param) so the legacy path is **byte-identical when off** — ship dark, validate, then flip default.

Effect: pages with a clean full-height gutter and NO embedded full-width table (the common clean 2-col body page) get corrected (left-then-right); pages with an embedded table are still SKIPPED by the bilateral gate (no regression — they stay as today, deferred to Step 2). The word-preservation guard guarantees a corrected page never loses/fabricates a word — worst case is a no-op fallback.

This alone should fix the clean-body-page interleave on many Collabra/JESP pages (section-order + paragraph continuity), while leaving the table-bearing pages untouched (honest partial — log which pages were corrected vs skipped).

### Step 2 (the harder per-band architecture — multi-session): region-aware band segmentation
For a flagged page, segment into horizontal y-bands:
- A band with a clean full-height gutter across its y-range → 2-col prose → column-correct that band (left-then-right).
- A band with full-width content (table row, banner, full-width heading) → leave as-is.
- Reassemble bands in y-order.
This corrects the prose bands of a page that ALSO carries a table, without garbling the table — the case Step 1's whole-page bilateral gate skips. This is the "segregate full-width table band from 2-col prose band before column-correcting" from the 2026-06-07 ip_feldman B4/R4 diagnosis.

### Validation (every step)
- Word-preservation guard is the hard safety (rules 0a/0b).
- Re-render the 4 sweep papers (collabra.37122/.77859, j.jesp.2021) + AI-verify vs article-finder gold: section order restored, tables not garbled, 0 text-loss/hallucination.
- 26-paper baseline: 0 regressions. The char-ratio/Jaccard gate is BLIND to reordering (memory `feedback_ai_verification_mandatory`) — so a word-preservation guard + AI-verify are mandatory, not the baseline alone.
- Canary (ip_feldman B4/R4) is the ultimate target — Step 2 is what finally closes it.

## Risks
- Touches the core extraction reading-order path → flag-gate + word-preservation guard + ship-dark are mandatory.
- pdftotext column-crop spacing edge cases on tight-kerned PDFs (already handled by `_crop_and_extract`).
- Over-correction of a single-column page false-flagged by Signature A/B → the gutter detector + word-preservation guard reject it (no clean gutter → no midline → no-op).

## Next-session opener
1. Reproduce: run `_detect_column_interleave_pages` on collabra.77859 + j.jesp.2021 raw text; confirm the interleaved pages are flagged (signal present) and currently uncorrected.
2. Implement Step 1 behind the flag; re-render + AI-verify the 4 papers; 26-baseline.
3. If Step 1 clean, scope Step 2 (band segmentation) as its own cycle.
