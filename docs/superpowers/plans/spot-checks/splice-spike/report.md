# Splice Spike — Phase 0 Report

**Date:** 2026-05-09
**Spec:** [`docs/superpowers/specs/2026-05-08-unified-extraction-design.md`](../../specs/2026-05-08-unified-extraction-design.md)
**Plan:** [`docs/superpowers/plans/2026-05-08-unified-extraction-phase-0-splice-spike.md`](../../2026-05-08-unified-extraction-phase-0-splice-spike.md)
**Author:** AI verification pass; awaiting user eyeball review.

## Summary

Phase 0 ran a 5-PDF prototype to test whether pdfplumber-derived tables can be spliced into pdftotext linear text at correct reading-order positions. **The splice locator algorithm works — but it's not the bottleneck.** The bottleneck sits one layer upstream: docpluck's `extract_pdf_structured` (which calls pdfplumber) returns empty cell structures for almost every table in the APA corpus. Where tables ARE detected, the splice algorithm places them correctly; but the "tables" being placed are not real pipe-tables — they are raw-text rows wrapped in pipe characters, no clearer than pdftotext's original output.

| Metric | Result |
|---|---|
| Tables detected by docpluck on 5 papers (combined) | 10 |
| Tables visually present in the 5 papers (estimate from `papers.md`) | ~16 |
| Detection rate | ~63%, with 3 of 5 papers returning **0 tables** |
| Splice locator: "location not found" diagnostics | 0 of 10 |
| Splice locator: tables placed correctly (where detection succeeded) | All 10 |
| Tables with usable cell structure (`cells` non-empty) | 0 of 10 |
| Tables rendered as proper pipe-tables (multi-column from cells) | 0 |
| Tables rendered as single-column pipe-wrapped raw text | 10 |

## Per-paper findings

### 1. korbmacher_2022_kruger.pdf — single-column JDM
- **Tables expected:** Table 1 on p. 7 (4×8 stats matrix).
- **Tables detected by docpluck:** **0**.
- **Splices in `outputs/korbmacher_2022_kruger.md`:** 0 pipe-table lines.
- **Outcome:** the table is silently absent from the spliced output; the .md is pure pdftotext prose. The token-fingerprinting locator never gets a chance to run because no tables are produced upstream.
- **Failure layer:** pdfplumber/docpluck table detection. pdfplumber's default lattice strategy needs ruled lines; this table is whitespace-aligned with no rules.

### 2. efendic_2022_affect.pdf — two-column SPPS
- **Tables expected:** Tables 1–5 across pp. 2–8 (mixed-effects regression tables).
- **Tables detected by docpluck:** **0**.
- **Splices in `outputs/efendic_2022_affect.md`:** 0 pipe-table lines.
- **Outcome:** same as korbmacher — pure pdftotext prose, no tables present in the markdown.
- **Failure layer:** pdfplumber/docpluck table detection. Two-column SPPS papers use whitespace-aligned tables, which pdfplumber's defaults don't pick up.

### 3. chandrashekar_2023_mp.pdf — multi-table page
- **Tables expected:** Tables 7, 8, 9, 10 consecutively on p. 10.
- **Tables detected by docpluck:** **0**.
- **Splices in `outputs/chandrashekar_2023_mp.md`:** 0 pipe-table lines.
- **Outcome:** all four tables silently missing from the markdown.
- **Failure layer:** same — whitespace tables not detected.

### 4. ziano_2021_joep.pdf — landscape multi-page table
- **Tables expected:** Table 1 spans landscape pp. 2–3 ("Table 1 (continued)"); plus likely Tables 2 and 3 elsewhere.
- **Tables detected by docpluck:** **3** (on pages 2, 4, 5).
- **Splices in `outputs/ziano_2021_joep.md`:** 149 pipe-table lines, 0 "location not found".
- **Outcome:** 3 of ~4 tables spliced into the markdown. The page-3 continuation of Table 1 was NOT detected (page-boundary failure in pdfplumber). All 3 detected tables landed at the correct reading-order position in the .md (verified by line-context spot-check).
- **Splice quality concern:** every spliced "table" has `cells: []` from pdfplumber, so the .md output renders each as a single-column pipe-table where each row is a full line of raw_text (e.g., `| Tversky & Shafir, 1992, / / / / / / / 98 Accept 68 58 35 (34%) |`). This is pipe-wrapped prose, not a structural improvement over pdftotext.

### 5. ip_feldman_2025_pspb.pdf — rotated correlation matrix
- **Tables expected:** ~8+ tables across pp. 4–13, including a rotated 90° correlation matrix on p. 13.
- **Tables detected by docpluck:** **7** (pp. 4–7, 9, 14, 15).
- **Splices in `outputs/ip_feldman_2025_pspb.md`:** 414 pipe-table lines, 0 "location not found".
- **Outcome:** the rotated table on p. 13 was NOT detected; pdftotext's reverse-rotated word output (`elbaT`, `serusaeM`) gives no anchor for table detection. ~3-4 of the body tables (Tables 6, 7, 8, etc. — visible by `^Table N\.` matches in the .md outside any spliced region) were also not detected. Where tables WERE detected (Tables 2, 4, 9, 10), splicing landed at correct positions, but again as pipe-wrapped raw_text, not real pipe-tables.
- **Splice quality concern:** same as ziano — single-column pipe-wrapped prose, not structural cell data.

## Failure modes observed

1. **Whitespace-aligned tables not detected** (3/5 papers — korbmacher, efendic, chandrashekar). pdfplumber's default lattice strategy requires ruled lines, which APA psychology papers do not draw. The output `.md` is pure pdftotext with no tables at all.

2. **Multi-page / continued tables partially detected** (ziano). The first page of a multi-page table is detected; continuation pages are not. Result: a partial table in the markdown.

3. **Rotated tables not detected** (ip_feldman p. 13). pdftotext emits rotated text in reverse character order, and pdfplumber doesn't reconstruct the rotation. This was an expected failure mode — included in the spike on purpose to confirm.

4. **Inconsistent detection on a single paper** (ip_feldman). 4–7 of ~10 tables detected. No clear pattern for which.

5. **Cells field always empty** (10/10 detected tables). Even when pdfplumber detects a table region, `cells` is empty for every APA paper in this corpus. The `raw_text` fallback (split by newlines into single-column pseudo-rows) means every spliced "pipe-table" is structurally pipe-wrapped prose, not multi-column data.

## What the spike PROVED works

- **The token-fingerprinting locator** (`find_table_region_in_text`) works as designed. 0 of 10 detected tables produced a "location not found" diagnostic. Spot-check of 3 splices (ziano page 2, ip_feldman pages 4 and 9) shows the spliced position matches the surrounding pdftotext context — the markdown table appears in the right place relative to the body prose.
- **The orchestrator** (`splice_tables_into_text`) handles per-page splicing, multi-table pages, and reverse-order index management correctly.
- **Form-feed page boundaries** (`\f`) align consistently between pdftotext and pdfplumber's page indices (after the 1-indexed → 0-indexed adjustment in `_load_tables_for_spike`).

## What the spike DISPROVED

- **The spec's implicit assumption** that pdfplumber's table channel produces usable cell structure. It does not, for the APA corpus. The spec's §3 "Tables → pipe table by default" cannot be delivered with the current upstream cell data.
- **The spec's phase-1 plan** as written would ship a feature that produces pipe-wrapped-prose for all detected tables on APA papers, plus silently-missing tables on the majority of papers. This is worse than today's behavior (where tables appear as garbled pdftotext rows but are at least visible).

## Recommendation

**(b) Modify the approach.** Specifically: phase 1 cannot rely on docpluck's existing `extract_pdf_structured.tables` channel. Two concrete adjustments are needed before phase 1:

1. **Improve table cell extraction at the docpluck layer.** Investigate calling `pdfplumber.Page.find_tables` directly with a combination of strategies:
   - **Lattice** (default) for journals that draw rules (Nature, JAMA).
   - **Stream-with-explicit-columns** for whitespace-aligned APA tables. This requires column-x-position detection (which pdfplumber supports via `text_x_tolerance` and `vertical_strategy="text"`). pdftotext's `-bbox-layout` mode can supply column boundaries as a hint.
   - **Detect "table caption + N lines below"** as a fallback region for tables pdfplumber misses entirely. This would at least mark the region for splicing even if cells aren't recovered.
2. **Add a "tables-as-prose-block" fallback to the spec.** When cells cannot be recovered, the markdown output should NOT pipe-wrap the raw text. Better: emit the table caption as a Markdown header (`### Table 1. <caption>`) followed by the raw text as a fenced code block. This preserves visual fidelity without false structure claims.

The splice algorithm itself (locator + orchestrator) is reusable for phase 1 as-is. The work is upstream.

**Spec amendment required before phase 1 plan:** §3 "Tables (default)" should be expanded with the prose-block fallback rule. §6 "Engineering risk" should be updated: the new top risk is *cell extraction from whitespace tables*, not splice positioning.

## What this report does NOT say

- **Performance numbers.** Phase 0 did not measure speed.
- **Behavior on non-APA layouts** (Nature, JAMA, AMA). Phase 0 corpus was APA only. Lattice-strategy detection may work much better on those journals; that is untested.
- **Whether pdftotext `-bbox-layout` mode would help.** Suggested in the recommendation but not prototyped.
- **Whether the markdown profile's other elements** (sections, footnotes, figures) are correct — phase 0 only addressed the splice algorithm.
- **Whether downstream consumers** (ESCIcheck, MetaESCI, Scimeto) would prefer the prose-block fallback or the silent-missing-tables status quo.

## Files referenced

- Outputs: [`outputs/`](outputs/) — 5 spliced `.md` files for eyeball comparison against the source PDFs in `../PDFextractor/test-pdfs/apa/`.
- Source PDFs: in the sibling repo `PDFextractor/test-pdfs/apa/`.
- Spike module: [`splice_spike.py`](splice_spike.py).
- Tests: [`test_splice_spike.py`](test_splice_spike.py) — 13/13 passing on synthetic input.
