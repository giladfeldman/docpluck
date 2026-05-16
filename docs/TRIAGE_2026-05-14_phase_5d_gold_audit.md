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
>
> **Update 2026-05-15 — ~~G4b SHIPPED v2.4.32~~ (cycle 15f-1).** New `_trim_table_caption_at_cell_region` in `extract_structured.py`: primary rule cuts after a sentence-terminated first caption line; fallback rule cuts at the first run of ≥3 header-like short lines. Verified against AI-gold `reading` view for amle_1/amj_1/xiao (26 tables) — all captions clean. 17 new tests. **G4a (body-stream dump) remains OPEN — queued as cycle 15f-2, C3.**

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

---

## APA BROAD-READ — autonomous run, 2026-05-15 (rendered v2.4.32, 18-paper APA corpus)

Reader-pass of the first ~32 lines of all 18 APA `.pdf` renders. 15/18 papers now have AI-gold `reading` views (010, 012, jamison content-filter-blocked at the subagent layer — render-verified only). Defect classes ranked by APA papers-affected:

| ID | Defect | APA papers affected | Sev | Cost | Status |
|---|---|---|---|---|---|
| **D1** | Letter-spaced lowercase Elsevier labels `a r t i c l e` / `i n f o` / `a b s t r a c t` leaked as body text; suppresses `## Abstract` | 010, 011, 012 (3) | S1 | C1 | **✓ SHIPPED v2.4.33 (cycle 1)** |
| **D4** | Journal/typesetting metadata leaked into front matter (volume/DOI banners, `Article views:`, `research-article2025`, `PSPXXX…`, open-science badge block, `Edited by:` lines, leading citation lines, copyright) | chan_feldman, chandrashekar, efendic, ip_feldman, maier, xiao, korbmacher, all jdm `Vol. 18:eN` headers (~12) | S2 | C2-C3 | OPEN — grab-bag; needs per-pattern triage, not one cycle |
| **D5** | Author/affiliation block fragmented; affiliation superscript markers (`a` `b` `c` `∗` `†` `‡` `⁎`) stranded on their own lines | 010, chen, jamison, ip_feldman, maier, korbmacher, jdm16, jdm_m2, jdm_m3 (~9) | S2 | C2 | OPEN |
| **D6** | Orphan section-number line (`1.` / `1`) stranded immediately before `## Introduction` (the `1.` of "1. Introduction" separated from its heading text) | jdm15, jdm16, jdm_m2, korbmacher, ziano, jamison (6) | S2 | C1 | OPEN — clean single root cause, cheap |
| **D2** | All-caps / concatenated front-matter labels leaked (`ABSTRACT`, `ARTICLE INFO`, `ARTICLEINFO`) — newer Elsevier + T&F layouts; abstract not promoted to a heading | chan_feldman, chen, jamison, ziano (4) | S1 | C2 | OPEN |
| **D3** | Abstract content mis-sectioned: chen places the abstract body under `## Introduction`; jamison/ziano/maier emit abstract prose with no heading | chen, jamison, ziano, maier (4) | S1 | C2 | OPEN — overlaps D2; abstract-detection on label-present layouts |
| **D7** | **G1 glyph collapse** — pdftotext maps efendic's U+2212 minus to digit `2`: `r = −.74 [−.92,−.30]` renders as `r = 2.74 [20.92, 20.30]`. 29 corrupted CIs. Confirmed in pdftotext raw output (upstream). | efendic (1, catastrophic) | **S0** | C2 | OPEN — **cycle 2 target** (published-stat corruption) |
| **D8** | Metadata mid-body: korbmacher acknowledgment + copyright block leaked into the Keywords section; xiao `CONTACT` line mid-Introduction | korbmacher, xiao (2) | S2 | C2 | OPEN |

**Cycle order for the APA fix loop (revised by this broad-read):** D1 ✓ → **D7/G1** (S0, efendic) → D6 (widest clean C1) → D2+D3 (abstract detection) → D5 (author block) → D4 (metadata grab-bag, split per pattern) → D8.

### Cycle-1 Phase-5d AI-gold verify — 011 findings (pre-existing, queued per rule 0e)

The 011 verifier (gold ↔ v2.4.33 render) returned FAIL — **all findings pre-existing** (the v2.4.32→v2.4.33 render diff is exactly the 3 collapsed D1 labels; cycle 1 introduced nothing). `## Abstract` recovery confirmed correct. Pre-existing defects queued:

- **D7b — minus-sign DROP (distinct from G1's `−`→`2`).** pdftotext raw output for 011 prints `b = .022`, `b = .245`, `b = .428` — the U+2212 minus is **deleted entirely** (gold: `−.022`, `−.245`, `−.428`). Confirmed upstream in `tmp/011_pdftotext.txt`. **Sign-inverts regression coefficients — S0.** Unlike G1 (`−`→`2`, a recoverable signal), a *deleted* minus leaves no text-channel signal — recovery needs the layout channel (pdfplumber per-char glyph). **C3-C4; likely escalate / layout-channel work.**
- **G2 reframed — `β`→`b` is pdftotext-upstream, not a docpluck transliteration rule.** pdftotext outputs `b` for efendic-family β glyphs; confirmed in `tmp/011_pdftotext.txt` line 333. The TRIAGE's original G2 hypothesis ("delete normalize.py Greek `.replace` rules") is wrong for 011 — there is no docpluck rule to delete; the corruption is in pdftotext's font handling. Layer = upstream; recovery needs layout-channel glyph identity.
- **G5 confirmed in APA — 7 subsection headings demoted to inline body text** in 011 (`Participants`, `Overview`, `Practice instructions`, `Self-control assessment`, `Perception of practice tasks`, `Stop signal`, `Supplemental analyses`). Also the "Supplemental analyses" section is shredded across the Table 1 region.
- **G3/G4 confirmed in APA — 011 Table 1 not reconstructed** ("Could not reconstruct a structured grid"); cell dump as orphan lines above the `### Table 1` marker; body-prose bleed into the `unstructured-table` fenced block.
- **G10/G11 in APA — 011 Figure 1** caption double-emitted (inline + `## Figures`); axis tick labels (`-10`, `-20`, `2.0 2.5 3.0…`, `Effort`) injected as orphan body lines.
- **D4 in APA — 011** Introduction contains leaked `E-mail address:`, `0022-1031/$ … Ó 2009 Elsevier` (note `Ó` = mangled `©`), `doi:10.1016/…` banner.

---

## APA Phase-5d FULL VERIFIER SWEEP — 14 papers in parallel (2026-05-15, renders v2.4.32 ≈ v2.4.33)

14 AI-gold verifier subagents run in parallel against the `reading` golds. Verdicts: **1 PASS (jdm_.2023.10), 13 FAIL.** (010/012/jamison gold-blocked — not in sweep.) This is the canonical cycles-2+ work queue. Root-cause groups ranked by APA papers-affected × severity:

| ID | Root cause | Papers affected | Sev | Cost | Notes |
|---|---|---|---|---|---|
| **GLYPH** | pdftotext mis-maps glyphs. Minus U+2212: `−`→`2` (efendic, 29 CIs), `−`→`(cid:0)` (ziano, chen), `−`→deleted (011). Greek: `β`→`b`, `η`→`n`, `α`→`a`. Superscript: `χ²`→`ch2`/`χ2`, `η²`→`n2`, `f²`→`f2`. Other: `<`→`\`, `≠`→`∕=`, `©`→`Ó`, `°`→`◦`, `△`→`(cid:4)`, `¬`/`\|` dropped. | efendic, 011, ziano, chen, korbmacher, jdm_m2, jdm_m3, jdm15, chandrashekar (~9) | **S0** | C2-C4 | Sign-inverts published stats. `(cid:0)`→`−` is the SAFEST recoverable slice (the marker is never legitimate); `2`→`−` recoverable via descending-CI discriminator; deleted-minus unrecoverable from text channel. Greek may be docpluck S0 math-italic transliteration OR pdftotext-upstream — diagnose per case. |
| **TABLE** | Caption welded into thead; rows dropped; body-prose bleed into table; empty `<table>` shells; two tables merged into one; mislabeled tables (Table 8 holds Table 9 grid); numeric cell SWAP (xiao Table 6 `4.91 (1.54)` vs gold `4.70 (1.64)`); G4a body-stream cell dumps (ziano ~1000 lines, chen, ip_feldman ~385 lines). | efendic, ziano, korbmacher, chan_feldman, chandrashekar, jdm15, jdm16, chen, maier, ip_feldman, xiao (~11) | **S0/S1** | C3 | Widest severe class. The G3/G4 cluster — needs design; handoff already flags as C3. |
| **G5** | Numbered subsections (`2.1`, `3.1.1`, …) emitted as plain body text, not `###` headings. | efendic, korbmacher, ziano, chan_feldman, chandrashekar, jdm15, jdm16, jdm_m2, chen, ip_feldman, maier, 011 (~12) | S1 | C2 | `sections/annotators/text.py` Pass 3. Widest structural class. |
| **HALLUC-HEAD** | Mid-sentence fragments / table-cell labels / TOC entries promoted to `##` headings: `## Methodology` (chan_feldman, chen — CRediT cell), `## Conclusion` (maier — none in gold), `## Supplementary Material`/`## Appendix` (jdm_m2 — mid-sentence), `## Data Availability Statement` (jdm15 — mid-Results), `## Supplemental Materials` (ip_feldman), `## Evaluation` (xiao), `## Introduction` mislabel of the Abstract (chen), `## Funding`/`## Methods` (chen). | chan_feldman, chen, maier, jdm_m2, jdm15, ip_feldman, xiao (~7) | S1 | C2 | Heading-promotion over-fires. Complement of G5 (under-fires). |
| **D6** | Orphan section-number line (`1.`/`2.`/`3.`/`4.`) stranded before `## Heading`. | ziano, korbmacher, jdm15, jdm16, jdm_m2, jdm_m3, jamison, chen (~8) | S2 | **C1** | Clean single root cause; cheapest wide win. |
| **D4** | Metadata leak: journal banner / DOI footer / copyright+CC-license banner / received-date / author-contact spliced into body — worst variant is the CC-license banner spliced MID-SENTENCE. | jdm15, jdm16, jdm_m2, jdm_m3, chan_feldman, chandrashekar, korbmacher, ip_feldman, efendic, 011, chen (~all) | S2 | C2 | |
| **FIG** | Figure caption double-emission; truncation mid-sentence; body-prose welded into caption (chan_feldman Figure 10, jdm16 Figure 1, jdm_m3). | chan_feldman, ziano, maier, jdm16, jdm15, jdm_m2, jdm_m3, chandrashekar (~8) | S2 | C2 | |
| **D2/D3** | Abstract not detected as its own section — placed under `## Introduction` (chen) or `## Keywords` (ziano), or unheaded. | chen, ziano, maier (~3) | S1 | C2 | |
| **COL** | Column-interleave / reading-order scramble — body sentences split across non-adjacent lines. | chan_feldman (Measures), chandrashekar (~2-3) | S0 | C3 | Text-channel reading order. |

**Cycle order for cycles 2+ (autonomous run):** 2 = GLYPH minus-recovery (`(cid:0)`→`−` + `2`→`−` descending-CI; S0, recoverable slice) → 3 = GLYPH Greek/superscript (diagnose layer first) → 4 = D6 orphan numbers (C1 wide win) → 5 = G5 subsection demotion → 6 = HALLUC-HEAD → 7 = D4 mid-sentence banner splice → 8 = FIG captions → TABLE cluster + COL escalated as C3 (dedicated session if budget remains). Every fix keyed on a structural signature, baseline-gated (user directive 2026-05-15).

---

## SESSION 3 — autonomous APA-first run, 2026-05-16

### Cycle 8 (v2.4.40) — standalone `2`-for-minus recovery via point-estimate ∈ CI pairing — SHIPPED

`normalize.py::recover_minus_via_ci_pairing` (W0d) recovers bracket-less corrupted point estimates by pairing each `2X.XX` token with the CI in the same `<tr>` row / text line: recover iff `−X.XX` ∈ CI and literal `2X.XX` ∉ CI (a point estimate always lies in its own CI — airtight invariant). efendic 22 negative B-coefficient cells + `Mposterior` recovered, verified cell-by-cell vs AI gold, 0 text-loss/hallucination.

**efendic GLYPH-cluster RESIDUALS (escalated — no text-channel signal):**
- 4× body-prose `Mchange = 2X.XX` (`20.14` ×2, `21.01`, `20.62`) — only an SE in parens, no CI to pair.
- 6× contrast-coding table-footnote `direction: 20.5 = low, + 0.5 = high` — **HAS a clean signature** (`2X.X = label, + X.X = label` symmetric `−X.X/+X.X` pair) — candidate for a small follow-up cycle.
- 1× `2100` for `−100` (affective-slider range) — no CI.
- → escalation bucket alongside 011 deleted-minus: needs layout-channel per-char glyph identity.

**efendic still FAILs** (verifier-confirmed pre-existing, NOT cycle-8 regressions): Table 2 grid lost (caption-bleed replaces 8 coefficient rows), Table 5 standalone grid lost (bare p-value list), Table 1 first data row dropped + column-fusion, section-boundary shuffle (empty headings, mislabeled `## 6. References`), D4 metadata leak (masthead + corresponding-author address into body), author-bios fragmented.

### G5 root-cause refinement (investigated cycle 8, queued cycle 9)

`render.py::_promote_numbered_subsection_headings` (regex `_NUMBERED_SUBSECTION_HEADING_RE`) has **two gaps** causing numbered headings to stay body text:
1. **Trailing dot after the number** — `_NUMBERED_SUBSECTION_HEADING_RE` is `^(\d+(\.\d+){1,3})\s+…` — requires whitespace immediately after the digits, so `5.3.3. Choice deferral` and `1.1. Hypotheses` (trailing `.` then space) never match. SAFE one-char fix: `…){1,3})\.?\s+`.
2. **Single-level top-level numbers** — the regex requires ≥1 `.\d` group, so `2. Omission neglect`, `3. Choice deferral`, `1. Hindsight bias` (single `N.`) are never promoted. Needs a new render-level promoter gated on: document already has ≥1 `## \d+\. ` numbered heading + line-isolated + short Title-Case + no terminal punctuation + small lowercase-run.

### Broad-read (v2.4.39, 12 FAIL APA papers) — defect-class ranking confirms queue
1. **D4 metadata leak into body** — 8 files (efendic, chandrashekar, maier, ip_feldman, xiao, chen, ar_apa_011, chan) — several mid-sentence.
2. **G5 heading demoted to body text** — 7 files (efendic, chandrashekar, jdm_m2, maier, ip_feldman, xiao, chen).
3. **D2/D3 abstract bleed / missing `## Abstract`** — 4 files (chan, maier, chen, chandrashekar).
4. **D5 author/title block fragmentation** — 4 files (chan, jdm16, ip_feldman, xiao).
5. **Glyph** (`Ó`→©, hyphenation word-splits, fused tokens, superscript digits) — 4 files.

**Revised cycle order session 3:** 9 = G5 numbered-heading promotion (2 gaps above) → 10 = D4 metadata leak → 11 = HALLUC-HEAD → 12 = FIG captions → TABLE cluster (C3) if budget.

### Cycle 9 (v2.4.41) — G5 numbered-subsection-heading regex loosening — SHIPPED

`_NUMBERED_SUBSECTION_HEADING_RE` gained an optional trailing dot in the number group + `:` in the title char class. ~78 multi-level subsection headings (`5.1.`, `5.3.3.`, `6.1.1. Replication: ...`) promoted to `###` across jdm_m.2022.2 / chen / jdm15 / jdm16, 0 false positives. AI-gold verifier (jdm_m.2022.2): OVERALL PASS, clean heading-markup-only change.

**G5 RESIDUALS (queued, distinct root causes):**
- **G5a — single-level top-level numbered headings** (`2. Omission neglect`, `3. Choice deferral`, `1. Hindsight bias`): `_NUMBERED_SUBSECTION_HEADING_RE` requires ≥1 `.\d` group, so single `N.` is never promoted. Needs a NEW render-level promoter gated on: document has ≥1 detected `#{2,4} \d` numbered heading + the candidate's number falls inside `[min,max]` of detected numbers (fills a gap) + line-isolated + short Title-Case + no terminal punct. The gate is what keeps it safe against enumerated lists (chandrashekar exclusion-criteria `1. Subjects... ; 2. ...`).
- **G5b — long-descriptive-title prose guard** (`2.4.2.2. Inference of planning strategies and strategy types` rejected by `max_lc_run >= 5`): the `≥5-lowercase-word` guard over-rejects legitimate long numbered headings. For a numbered+isolated line the number prefix is already strong evidence; the lc-run guard is near-redundant there.
- **G5c — split-line numbered headings** (`5.3.`\n\n`Results` — number alone on a line, title on the next; renders as orphan bare-number line, and the content gets a MISLABELED generic `## Results` instead of `### 5.3. Results`): the cycle-3 orphan-arabic-numeral folder's multi-level analogue.
- **G5d — NAMED (unnumbered) subsection headings demoted to inline body text** (`Participants`, `Overview`, `Self-control assessment` in ar_apa_011; `Affect Heuristic` efendic; `Default Effect` chandrashekar; `Background` ip_feldman): the widest G5 flavor and the riskiest — detecting a heading without a number prefix has a large false-positive surface; section-partitioner work (`sections/annotators/text.py`), C2-C3.

### Cycle 10 (v2.4.42) — D4 Elsevier page-footer strip — SHIPPED

Two `normalize.py` W0 patterns: Issue K strips the Elsevier ISSN/front-matter/copyright line (anchored on line-leading ISSN `\d{4}-\d{3}[\dX]/` + keyword guard), Issue L strips the singular `E-mail address:` corresponding-author line. ar_apa_011 + chen footer lines removed, 0 body-prose loss, AI-gold verifier OVERALL PASS.

**D4 RESIDUALS (queued):** bare lowercase `doi:10.…` footer line (not stripped — indistinguishable from a reference whose DOI wrapped to its own line; would need a front-matter-position gate); plural multi-line `E-mail addresses:` author list; `Received … Accepted …` history line; `article info` fragment; efendic journal-masthead block.

### Cycle 11 (v2.4.43) — G5a single-level numbered section-heading promotion — SHIPPED

New `render.py::_promote_numbered_section_headings` promotes `N. Title` → `## N. Title`, gated by 5 conjunctive safety checks (document-numbering-range, number-uniqueness, list-adjacency, terminal-punctuation, ≥5-lowercase-word prose guard). jdm_m.2022.2 6/7 sections promoted, chen 6/10, chandrashekar 0 false positives (enumerated lists correctly rejected). AI-gold verifier (jdm_m.2022.2): OVERALL PASS, 0 new defects.

**G5a RESIDUALS (queued):** the ≥5-lowercase-word prose guard rejects long descriptive headings (`4. Knowledge acquisition, decision delay, and choice outcomes`) — same G5b guard issue; list-number collision under-promotes a section heading whose number a body list reuses (chen 1/2/3/5 — conservative, not a false positive).

### Cycle 12 (v2.4.44) — GLYPH ligature decomposition — SHIPPED

`normalize.py::decompose_ligatures` is the single shared helper for the U+FB00-FB06 ligature block — an explicit ASCII table (`ﬁ→fi`, `ﬂ→fl`, …, `ﬅ/ﬆ→st`; NFKC is avoided because `ﬅ`→`ſt` carries a non-ASCII long s). **The body channel's S3 step already expanded ligatures** — the real gap was the table-cell, figure/table-caption, and `unstructured-table`-fence channels that bypass `normalize_text`. The helper is now called from all three channels (S3 body / `cell_cleaning._html_escape` / `render_pdf_to_markdown` post-process); the S3 step also gains `ﬅ/ﬆ` reach. Corpus scan found ligatures in 35 rendered papers (korbmacher 82×, jdm16 34×); jdm_m2/korbmacher/jdm16 verified → 0 residual. The `GLYPH ligature` row below is now RESOLVED.

> **Cycle-12 rework note (run 4, 2026-05-16):** the first cycle-12 attempt added a SECOND, parallel `decompose_ligatures` call *before* the pre-existing S3 step inside `normalize_text` — it consumed every ligature before S3 ran, so S3 tracked `ligatures_expanded = 0` and broke `test_normalization.py::test_report_tracks_changes`. The rework removed the duplicate call and unified S3 to use the shared helper. Lesson: before adding a glyph-normalization helper, grep the existing `normalize_text` S-steps for one already handling that glyph class — extend/unify it, do not add a parallel path.

### Cycle 13 (v2.4.45) — G5b long-descriptive-title prose guard — SHIPPED

`render.py`'s numbered-heading promoters carried a `max_lc_run >= 5` "long lowercase-word run" prose guard that mis-rejected legitimate descriptive headings. Reproduced at HEAD: jdm_.2023.16 alone had **19** multi-level numbered subsection headings demoted to body text, with `max_lc` up to **12** (`3.3.2.1. The quality of planning on the previous trial moderates the effect of reflection`) — far deeper than the TRIAGE's "raise 5→8" estimate. Re-scoped: the lc-run guard is **removed entirely from `_promote_numbered_subsection_headings`** (multi-level dotted numbering + capital-start + no-terminal-punctuation + single ≤80-char line is itself a sufficient heading signature; the lc-run guard cannot distinguish a descriptive heading from prose). For `_promote_numbered_section_headings` (single-level `N.`, real list-collision risk) the guard is kept but raised `5→8`, alongside its existing numbering-range/uniqueness/list-adjacency gates. jdm16: 19 headings recovered; v2.4.44→v2.4.45 diff is heading-promotion only (0 text loss/hallucination); 26/26 baseline.

### Cycle 14 (investigation, run 4) — G5c re-scoped C2 → C3 (no release)

Reproduced G5c at v2.4.45 on jdm_m.2022.2. The TRIAGE framed G5c as "the cycle-3 orphan-arabic-numeral folder's multi-level analogue" (C2, a render-layer fold). Reproduction shows it is **deeper** — section-partitioner work, C3:

- jdm_m.2022.2 has **6** orphan bare-number lines: `5.3.` (L114), `5.4.` (L185), `6.3.` (L260), `6.4.` (L285), `7.3.` (L329), `7.4.` (L403).
- Only **1** is the clean foldable case the TRIAGE described — `5.4.` immediately followed by a generic `## Discussion` (→ should be `### 5.4. Discussion`). A render-layer fold-into-next-heading handles this one.
- The other **5** are NOT foldable: pdftotext splits `6.3. Results` into `6.3.\n\nResults`; the section partitioner then consumes the bare word `Results` as a canonical section keyword (building/relocating a `## Results` block elsewhere) and strands `6.3.` with no title and the section body (`We performed one-way ANOVAs…`) starting directly after it. The title word is *gone from that position* — there is no following heading to fold into. `5.3.` (L114) is stranded above `### Figure 1` — same shape.
- Correct fix layer: `docpluck/sections/` — the partitioner must recognise `N.N.\n\n<CanonicalKeyword>` as ONE numbered heading `N.N. <Keyword>` and not detach the number. That is partitioner work with broad-corpus false-positive surface — a dedicated session, C3.

**Re-scoped:** G5c-1 (render-layer fold of orphan `N.N.` into an adjacent generic `##/###` heading — the `5.4.`/`## Discussion` case, C1-C2) can ship independently; G5c-2 (partitioner-level split-heading rejoin — the 5 title-loss cases, C3) needs the dedicated section-partitioner session alongside G5d and the TABLE cluster.

### Cycle G5c-1 (run 5, 2026-05-16) — orphan multi-level numeral render-fold — SHIPPED v2.4.46

New `render.py::_fold_orphan_multilevel_numerals_into_headings` — the multi-level
analogue of the arabic/roman orphan folders. Folds an orphan `N.N.` number into
the **immediately-adjacent** generic `##`/`###` heading at subsection level
(`5.4.`⏎`## Discussion` → `### 5.4. Discussion`). Keyed on the structural
signature (isolated multi-level dotted number) + blank-line-only adjacency;
`### Figure N`/`### Table N` and already-numbered headings excluded.

jdm_m.2022.2: the `5.4. Discussion` subsection recovered. **Phase-5d AI-gold
verdict (run 5):** jdm_m.2022.2 still **FAIL** — but the cycle's own diff is
heading-markup-only (verifier confirms `### 5.4. Discussion` correct vs gold §5.4,
0 sentence-level text loss, 0 hallucination, 0 regression). The FAIL is the
pre-existing punch-list: G5c-2 stranded orphans (`5.3.`/`6.3.`/`6.4.`/`7.3.`/`7.4.`),
HALLUC-HEAD (`## Supplementary Material`/`## Appendix` mid-sentence promotion),
FIG caption double-emission + truncation, D5 author-block fragmentation. 26/26
baseline; three-tier byte-identical. The 5 non-adjacent orphan numbers confirmed
NOT render-foldable (no heading to fold into) — they are G5c-2 partitioner work.

### SESSION-3 STANDING VERDICT (rule 0e-bis)

The APA corpus is **NOT clean**. Cycles 8-11 shipped 4 verified incremental fixes (v2.4.40-43), each AI-gold-verified OVERALL PASS with 0 regressions. But ~12 APA papers still FAIL Phase-5d on PRE-EXISTING defects the cycles did not reach. Verifier-confirmed open punch-list:

| Defect class | Sev | Papers | Notes |
|---|---|---|---|
| **TABLE structure destruction** | S0/S1 | efendic, ar_apa_011, xiao, jdm15/16, chen, maier, ip_feldman (~11) | grid lost → caption-bleed; flat number-dump; empty `<table>` shells; two tables merged; rows dropped. C3 — needs a render/structured coordination design. The single largest blocker. |
| ~~**G5c-1 split-line numbered headings — render fold**~~ ✓ SHIPPED v2.4.46 (run 5) | S1 | jdm_m.2022.2 (`5.4.`) | ~~render-layer fold of orphan `N.N.` into adjacent generic heading.~~ Done — `_fold_orphan_multilevel_numerals_into_headings`. |
| **G5c-2 partitioner split-heading rejoin** | S1 | jdm_m.2022.2 (`5.3.`/`6.3.`/`6.4.`/`7.3.`/`7.4.`) | the 5 non-adjacent cases — pdftotext splits `N.N. Title`, partitioner consumes the title word; needs partitioner-level rejoin. **C3** — dedicated session. |
| **G5d named (unnumbered) heading demotion** | S1 | ar_apa_011 (`Participants`, `Overview`), efendic, chandrashekar, ip_feldman (~7) | section-partitioner work; largest false-positive surface. |
| ~~**G5b long-descriptive-title prose guard**~~ ✓ FIXED v2.4.45 (cycle 13) | S1 | jdm16, jdm_m2, chen | ~~`≥5-lowercase-word` guard over-rejects legit long numbered headings.~~ Subsection promoter's lc-run guard removed; single-level raised 5→8. |
| **FIG caption double-emission + truncation** | S2 | jdm_m2, efendic, chan_feldman, ziano, jdm15/16 (~8) | caption inline + in `## Figures` block; truncated mid-word; figure data-labels as orphan body lines. |
| **GLYPH ligature** `ﬁ`/`ﬂ` not decomposed | S2 | jdm_m2 (and likely many) | `conﬁdent`, `inﬂuence` — NFKC would fix; check why current NFC pass misses U+FB01/FB02. |
| **D4 metadata residuals** | S2 | ar_apa_011 (`doi:` line), chen, efendic masthead | see D4 RESIDUALS above. |
| **COL column-interleave** | S0 | chan_feldman, chandrashekar | text-channel reading order. C3. |
| **GLYPH 011 `−`→deleted / efendic `Mchange` no-CI** | S0 | 011, efendic | unrecoverable from text channel — needs layout-channel glyph identity. Escalate. |

**Next session resumes here.** GLYPH ligature ✓ (v2.4.44), G5b prose-guard ✓ (v2.4.45),
G5c-1 render fold ✓ (v2.4.46). Recommended order: **FIG caption double-emission +
truncation** (S2×C2, ~8 papers — next cheapest wide win) → **G5c-2 partitioner
split-heading rejoin** (S1×C3, 5 jdm_m2 cases) → **G5d named/unnumbered heading
demotion** (S1×C2-C3, ~7 papers) → **HALLUC-HEAD** mid-sentence `##` promotion
(`## Supplementary Material`/`## Appendix` — S1×C2) → **TABLE cluster** (S0/S1×C3,
dedicated session, the single largest blocker) → **COL** + 011 deleted-minus
escalated (layout-channel, C3-C4).
