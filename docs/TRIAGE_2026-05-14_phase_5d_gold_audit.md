# TRIAGE — Phase 5d AI-Gold Audit (2026-05-14)

**Methodology:** AI multimodal read of each source PDF (gold) ↔ rendered .md at v2.4.28. Pdftotext output used only as diagnostic for layer attribution. Per CLAUDE.md ground-truth hard rule and memory `feedback_ground_truth_is_ai_not_pdftotext`.

**Result:** 4 / 4 papers FAIL. Defect classes far broader than prior pdftotext-baseline audit suggested.

| Paper | Pages | Verdict | New findings vs prior audit |
|---|---|---|---|
| xiao_2021_crsp | 36 | FAIL | Table 6 numeric data SWAP (4.91 vs 4.70 — published-stat corruption); ~25 of ~35 gold headings demoted; references concatenated to mega-lines; notes run-on |
| amj_1 | 29 | FAIL | Catastrophic pdftotext glyph collapse (=→5, <→,, −→2, ×→3, α→a, χ²→x2); Acknowledgments paragraph MISSING; tables emitted twice; Förster→"Fö rster" combining-char split |
| amle_1 | 32 | FAIL | ~130 comma-thousands strips in body (1,675→1675); math-operator hallucinations (=→5, <→,); 9 of 13 tables caption-bleed; Table 13 column-fusion persists; digit drift (OCR-class) in 3 cells; Acknowledgments paragraph missing; author bios fused to last reference |
| ieee_access_2 | 22 | FAIL (worst) | β→"beta" 61×, δ→"delta" 32× (normalize.py transliteration); γ/τ preserved (inconsistent); equation destruction (√/²/|·|/→/×/{}/()/[] dropped); body prose splay into vertical one-word lines; Page 4 (2) header leak in equation; 37 figure captions emitted TWICE with mismatched normalization; URLs broken by soft-wrap spaces; subscripts/superscripts flattened |

## Root-cause groups, ranked by severity × papers-affected

### Tier S0 — Published-stat corruption (meta-science-fatal)

**G1. pdftotext glyph collapse** (amj_1, amle_1 confirmed; xiao stats also affected; likely every stats paper)
- `=` → `5`, `<` → `,`, `−` (U+2212) → `2`, `×` → `3`, `α` → `a`, `χ²` → `x2`, `Δ` → `D`, `η_p²` → `hp2`, `R²` → `R2`
- **Real-world impact:** "b = −0.54" reads as "b 5 20.54" — sign-flipped AND operator-corrupted. Every stat in every paper.
- **Layer:** pdftotext upstream (the .txt file itself has these substitutions). Diagnostic confirms.
- **Fix approach:** context-aware W-step in normalize.py — detect stat-near-keyword patterns and correct. Risk: false positives.

**G2. normalize.py Greek-letter transliteration** (ieee_access_2: β/δ→"beta"/"delta" 93 occurrences; γ/τ preserved)
- **Layer:** `docpluck/normalize.py` — code substitution rule
- **Fix:** delete the Greek-letter `.replace` rules (CLAUDE.md L004 allows ONLY U+2212→hyphen).

**G3. Table cell structural defects** (all 4 papers)
- Phantom empty columns (xiao Tables 1/2/6)
- Cell concatenation (ieee Table 1 fused 3×8 → 1×6; amle Table 13 fused HRM+SM groups: `<td>Michigan State6Harvard University</td>`)
- Caption-bleed into thead (amj_1 Tables 1/2; amle Tables 3-11)
- Empty `<table>` while cell data is dumped to body stream (amj_1 Table 4; xiao Table 4 column collapse)
- Missing trailing summary rows (xiao Table 3 missing ΔF/R²/ΔR²; amj_1 Table 3 same)
- Running-header leak inside thead (amj_1 Table 4: "Academy of Management Journal / April")
- **Layer:** `docpluck/tables/cell_cleaning.py`, `docpluck/tables/render_html.py`, `docpluck/extract_structured.py`

### Tier S1 — High (multi-paper structural)

**G4. Body-stream table fragments duplicating structured tables** (xiao, amj_1, amle_1)
- Each table emitted TWICE: once as broken plain-text dump in body, once as HTML at end
- amle_1 worst: Discussion section starts with raw token spew from Table 7 dump
- **Layer:** `docpluck/render.py` or `extract_structured.py` — body-stream cells should be SUPPRESSED after structured emission
- **Fix:** when a table is structured-extracted, suppress its cell content from body stream

> **Cycle 15f investigation (2026-05-15) — G4 is a multi-defect cluster, NOT a single body-strip fix. Re-scoped C2 → C3.**
>
> Investigated amle_1 at v2.4.31. Found TWO compounding defects, each substantial:
>
> **G4a — body-stream table-cell dump.** The RESULTS section's `sec.text` (from `extract_sections`) contains the raw pdftotext-linearized table region: caption line `TABLE 1`, the title, then ~140 lines of column-by-column linearized cells (`Rank / Academic / Source / Yes / Yes / No / 1,675 / 9.35% / 7.12 / ...`), then the `Note:` footnote, then body prose resumes. `render.py::_render_sections_to_markdown` emits `body_text = sec.text.strip()` verbatim, so this dump appears in the body. Separately the structured `<table>` HTML is emitted (correctly, 189 cells) in the `## Tables (unlocated in body)` appendix. Net: every table's data appears twice.
>   - Fix requires: detect the table-dump region inside each section's `sec.text` and strip it. The region runs caption-line → linearized-cells → `Note:` block → first body-prose line. `extract_structured._line_is_body_prose` + `_extract_table_body_text` already have the cell-vs-prose walk logic but produce cleaned text, not char offsets into the section. The two pipelines (`extract_sections` for body, `extract_pdf_structured` for tables) are **uncoordinated** — neither knows the other's regions. `normalize_text` has a `table_regions` param but render doesn't populate it. A correct fix needs the render layer to compute/pass table regions OR a section-text post-strip keyed on the structured tables' captions. **Risk:** false positives stripping legitimate short-line-dense body prose.
>
> **G4b — table caption field absorbs the entire linearized cell content.** `extract_pdf_structured` returns `Table 1` with `caption = "Table 1. Most Cited Sources in Organizational Behavior Textbooks Rank Academic Source Academic Rank 1 2 3 4 5 5 7 8 Yes Yes Yes Yes No Yes ..."` — the `_extract_caption_text` paragraph-walk, when the caption title has no sentence terminator (`Most Cited Sources in Organizational Behavior Textbooks` ends with no `.`), keeps walking through the linearized cells until the 400-char hard cap. Render emits this as `*Table 1. <400 chars of cell garbage>*` directly above the (correct) `<table>` HTML. Affects every table whose title lacks a trailing period — common in AOM/management journals.
>   - Fix layer: `extract_structured.py::_extract_caption_text` — for `cap.kind == "table"`, when the walk is about to consume a paragraph whose lines are predominantly cell-like (short, numeric, single-word), STOP at the title line. Lower-risk than G4a; could ship independently as its own cycle.
>
> **Recommendation:** split into two cycles. **15f-1 (G4b, C1-C2):** tighten the table-caption walk — isolated, testable, ships independently. **15f-2 (G4a, C3):** body-stream table-region strip — needs a render/section coordination design and broad-corpus false-positive testing; warrants a dedicated session. Do 15f-1 first; it's a clean win and de-risks 15f-2.

**G5. Section-boundary detection under-firing** (all 4 papers)
- xiao: ~25 of ~35 gold headings demoted to body prose
- amj_1: missing INDEX TERMS, Biographies, V.: SUPPLEMENTARY INDEX
- amle_1: ~13 subsections flat (Science-Practice Gap, Rewarding Scholarly Impact, Textbook Selection Criteria, Research Question N, Implications for X, etc.)
- ieee_access_2: 13 A./B./C./1)/2)/3) markers flat
- **Layer:** `docpluck/sections/annotators/text.py` (Pass 3)

**G6. Orphan Roman-numeral lines above ALL-CAPS headings** (ieee_access_2: I./II./III./IV.)
- **Layer:** `docpluck/render.py::_promote_all_caps_section`
- **Fix:** consume preceding `^[IVX]{1,4}\.\s*$` line

**G7. Equation destruction** (ieee_access_2)
- √, ², |·|, /, →, ×, {}, (), [] dropped from math expressions
- RRMSE formula and β₂ formula corrupted
- **Layer:** `docpluck/normalize.py` whitespace-collapse over-aggressive on math content
- **Fix:** detect math contexts and disable whitespace-collapse

**G8. Body prose splay around inline math glyphs** (ieee_access_2 catastrophic)
- Whole paragraphs around inline math explode into one-word-per-line vertical stacks
- **Layer:** unknown — extract.py reading-order or normalize.py paragraph-rejoin

**G9. Endmatter routing** (amj_1, amle_1)
- amj_1: Appendix A subsections leak between References and Appendix-A heading; bios mid post-References zone; **Acknowledgments paragraph MISSING entirely**
- amle_1: bios FUSED to last reference with no break; Acknowledgments missing
- **Layer:** `docpluck/sections/` endmatter taxonomy

### Tier S2 — Medium (single-paper or cosmetic)

**G10. Figure caption double-emission with mismatched normalization** (ieee_access_2 37×: inline ASCII + dedicated Unicode + ~10 truncated)
**G11. Figure body-labels orphaned** (amj_1 Figure 1; ieee Figures 2-7 chart-axis labels in body)
**G12. Subscript/superscript flattening** (ieee_access_2: S₀→S 0, M₀→M0, ℕⁿ→Nn)
**G13. References concatenated to mega-lines** (xiao, amj_1); references fused with author bios (amle_1)
**G14. URL soft-wrap space insertion** (ieee_access_2 refs [4]/[6]/[21])
**G15. Combining-character split / no NFKC** (amj_1: Förster→"Fö rster"; Potočnik→"Potocˇnik")
~~**G16. Page-header leak inside equations** (ieee_access_2: `Page 4 (2)`)~~ ✓ FIXED — verified at v2.4.31 (cycle 15e investigation, 2026-05-14): incidentally closed between v2.4.27 and v2.4.31 by some combination of preserve_math_glyphs / NFC / section-partitioning shifts. Confirmed across 6 IEEE papers (0 hits). Locked in by `tests/test_equation_page_header_strip_real_pdf.py` (6 tests).
**G17. Comma-thousands stripping** (amle_1 ~130 instances in body; structured tables PRESERVE commas — bug is body-text path only)
**G18. Digit drift / OCR misread** (amle_1: 14992 vs 14,002; 9913 vs 9,953; 48390 vs 48,396)
**G19. Citation count drift in body table dumps** (amle_1: 3986 vs 1,808; 1810 vs 1,318)
**G20. Hallucinated `## Tables (unlocated in body)` meta-heading** (amle_1, amj_1 — library marker leaking to user)
**G21. Bracket/paren stripping in math** (ieee_access_2: x(p₁)→x p1; [m₁,...]→m1,...; f(x, t)→f x, t)
**G22. xiao Table 6 numerical-data SWAP** (4.91 (1.54) vs gold 4.70 (1.64) — published-stat corruption)
**G23. xiao hallucinated `## Introduction` heading** (no such heading in PDF)
**G24. Acknowledgments paragraph dropped** (amj_1 entirely; amle_1 entirely)

## NEW DEFECTS DISCOVERED BY v2.4.29 RE-VERIFICATION (added 2026-05-14)

### ~~G_15n — Figure caption placeholder regression in ieee_access_2~~ ✓ FIXED v2.4.31 (2026-05-14)

**Status: SHIPPED v2.4.31.** Originally classified as a v2.4.29 regression; investigation found the placeholder behavior is long-standing (reproduces at v2.4.28 against current pdftotext output — the saved `tmp/ieee_access_2_v2.4.28.md` predates a pdftotext layout shift; PDFs are immutable but extracted text isn't).

**Root cause:** `_extract_caption_text` paragraph-walk bailed on `\n\n` after the ALL-CAPS label line because `FIGURE N.` ends with `.`. Plus the caption regex's MULTILINE `^` + `\s*` could land `m.start()` on a `\n`, giving `char_end == char_start` for PMC-style captions.

**Fix:** new helpers `_accumulated_is_label_only(text)` (keep walking past terminator when accumulated text is label-only) + `_strip_leading_pmc_running_header(snippet)` (strip `Author Manuscript` leakage between label and description, surfaced after the walk fix per rule 0e).

**Verification:** ieee_access_2 0/37 placeholders, 0/37 PMC leaks, Unicode preserved. 10 new tests in `tests/test_figure_caption_trim_real_pdf.py`. 26-paper baseline 26/26 PASS.

### G_partial_15d — III./IV. orphan numerals not adjacent (NEW limitation)

Cycle 15d (v2.4.30) successfully folds `I.` and `II.` (adjacent to their `##` headings) but not `III.` and `IV.` (placed far from their headings by the section partitioner, between `### Figure 9` / `### Table 1` blocks).

**Layer:** `docpluck/sections/core.py` (partition_into_sections) — places the orphan numeral in the wrong section.

**Severity:** S2. Half-fixed; documented as known limitation in the test (warning emitted).

**Cycle 15i+** (section-partitioner cycle).

## Recommended cycle order

| # | Cycle | Group | Severity | Cost | Why this order |
|---|---|---|---|---|---|
| 1 | 15a | G2 | S0 | C1 (delete code) | Highest-impact one-line fix; removes inconsistent Greek transliteration |
| 2 | 15b | G17 | S2 | C1 | Body-text comma-stripping is a single rule in normalize.py; structured tables already work |
| 3 | 15c | G15 | S2 | C1 | NFKC composition fixes combining-char splits |
| 4 | 15d | G6 | S1 | C1 | Consume Roman-numeral lines before promoted ALL-CAPS heads |
| 5 | 15e | G16 | S2 | C1 | Strip `Page N` from equation-number context |
| 6 | 15f | G4 | S1 | C2 | Suppress body-stream cells when structured table emitted |
| 7 | 15g | G1 | S0 | C2-C3 | pdftotext glyph collapse — needs careful context-aware W-step; biggest impact but riskiest |
| 8 | 15h | G3+G22 | S0 | C3 | Table cell defects + xiao Table 6 swap — multi-cycle work |
| 9 | 15i | G5 | S1 | C2 | Loosen section-detection thresholds |
| 10 | 15j | G7+G8+G21 | S1 | C3 | Math-content normalization gate — engineering papers |
| 11 | 15k | G9+G24 | S1 | C2 | Endmatter routing (Appendix, bios, Acknowledgments) |
| 12 | 15l | G10+G11 | S2 | C2 | Figure caption emission once + suppress body labels |
| 13 | 15m | G12+G13+G14+G18 | S2 | C2 | Long tail |

**Stop condition (per user directive):** continue until full corpus is AI-gold-verified clean. Rule 0e applies: every defect found must ship a fix in this run.

## Files (canonical 4 + reusable golds)

```
tmp/xiao_2021_crsp_gold.md          (116 KB) — AI gold, reusable forever
tmp/xiao_2021_crsp_v2.4.28.md       (118 KB) — rendered, audited
tmp/xiao_2021_crsp_pdftotext.txt    (114 KB) — diagnostic only

tmp/amj_1_gold.md                   (133 KB)
tmp/amj_1_v2.4.28.md                (143 KB)
tmp/amj_1_pdftotext.txt             (128 KB)

tmp/amle_1_gold.md                  ( 83 KB)
tmp/amle_1_v2.4.28.md               (204 KB)
tmp/amle_1_pdftotext.txt            (141 KB)

tmp/ieee_access_2_gold.md           ( 75 KB)
tmp/ieee_access_2_v2.4.28.md        ( 75 KB)
tmp/ieee_access_2_pdftotext.txt     ( 74 KB)
```
