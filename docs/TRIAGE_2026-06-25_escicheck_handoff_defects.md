# Triage — ESCIcheck handoff defects (2026-06-25)

Source: `ESCIcheckapp/docs/DOCPLUCK_HANDOFF_2026-06-25.md` (6 defects, DP-1…DP-6).
Grounded against: **AI multimodal `reading` + `stats` golds** (article-finder, the
authoritative ground truth per project rule) AND the rawest docpluck artifacts
(`extract_pdf_structured(pdf)["tables"]` grids + `extract_pdf_layout` chars +
`pdffonts`). Harness: `tmp/handoff_2026_06_25/ground.py`.

Tested at working-tree **v2.4.98** (foundation: RC-T char-level whitespace fallback
landed in 521089a but NOT yet wired for these cases). `flatten.py` and the table
capture path are byte-identical to released **v2.4.97** (what production runs / what
the handoff was filed against) — confirmed by `git diff v2.4.97 HEAD --stat`.

---

## Root-cause grouping (the 6 defects collapse to 4 causes)

| # | Defect | Root cause | Owning layer | Recoverable? |
|---|--------|-----------|--------------|--------------|
| **DP-3** | η²p symbol stripped on F-rows (text `( = .000…`) | **pdftotext AND pdfplumber both decode the η²p glyph as U+0020.** The glyph lives in font `PXAAAA+NotoSerif-Regular`, which `pdffonts` reports as **`uni: no`** (no ToUnicode CMap) + MacRoman encoding → the glyph's Unicode identity is absent from the PDF. NOT a docpluck strip. | Font / both extraction channels | **Text channel: NO** (OCR-tier; glyph identity genuinely absent). **Table channel: YES (structurally)** — the column *position* is recoverable; infer `effect_type=eta2`. |
| **DP-1** | Table 4 (Study 4) "original" t-values bare (`3.91`, `2.15` alone on lines) | **Side-by-side 2-panel table → Camelot captures 0 cells** (docpluck `t2` is a `shape=0x0` caption-only stub). The values exist ONLY in the column-flattened pdftotext stream. | Capture (L-006 side-by-side limit + L-009 "flatten ⊆ capture") | **Partial** — needs degenerate-stub→whitespace re-extract (the work the v2.4.98 commit explicitly deferred). |
| **DP-2** | Study 1 Table 1 extension rows absent | **Table 1 (`t1`) captured 0 cells** (same `shape=0x0` stub class as DP-1). | Capture | Same as DP-1. |
| **DP-5** | cog_emo correlation r-cells not typed | **(a) Table 2: cells glued by tight kerning** (`1. Degree of apology 5.632.84.79` — M/SD/α + r all in one cell), so no per-cell values exist to type. **(b) Table 8: rows DO flatten with p/CI/group but the r value isn't keyed `r`.** | (a) Capture (RC-T gluing) + (b) flatten typing | **Partial** — (a) needs RC-T whitespace fallback to un-glue; (b) is a flatten r-typing gap. |
| **DP-4** | Table 8/9/10 replication rows "not surfaced" | **Inaccurate as filed.** Table 8 & 9 rows ARE flattened with `F`, `est`, `p`, `BF01`, `CI_lower/upper` (verified at v2.4.97 path). Table 10 rows ARE typed `r`. The ONLY gap is the `est` column being keyed generic `est` instead of `eta2` — i.e. DP-3 (table side). Handoff itself rated this "lower priority — body-text versions cover the stat." | — | **Already working** except the DP-3 eta2-typing. |
| **DP-6** | cog_emo figure-inset stats | Text embedded in figure raster/vector annotations. | Out of scope for text extraction | **Won't-fix** (handoff agrees: "Likely out of scope… noted for completeness."). |

### The deep structural commonality
DP-1, DP-2, DP-5(a), and DP-3 are all **the same family**: PDFs where the deterministic
extractors lose information the human eye sees — tight-kerned glyph-gluing, side-by-side
two-panel tables, and broken-ToUnicode symbol fonts. This is precisely the territory the
v2.4.98 **RC-T** foundation was built for. DP-3's *text* instance and DP-6 are the
genuinely-unrecoverable tail (OCR-tier / figure-raster).

---

## Per-defect verdict & proposed fix

### DP-3 — η²p (HIGHEST VALUE, split verdict)
- **Text channel: WON'T-FIX (honest).** Glyph Unicode identity absent from PDF
  (NotoSerif-Regular `uni:no`). Recovering it = OCR or font-glyph-shape classification,
  which we have ruled OCR-tier won't-fix for the residual-minus class (memory
  `project_docpluck_rc_b7_done_w0h`). Same class.
- **Table channel: FIX (general, structural).** When a flattened table row's estimate
  column has NO effect-type signal from header text OR table vocab (because the η²p glyph
  was dropped everywhere), but the table is structurally an **F-test / ANOVA results
  table** (carries F columns + a `BF01` and/or a `95% CI` column, and carries NO competing
  typed-effect column — no `d`/`dz`/`r`/`OR`), infer `effect_type = eta2` for that
  estimate column. Keyed on the structural signature, not on paper identity → generalizes
  to any APA ANOVA table whose η² header glyph is font-broken. Unblocks the consumer
  binding the value to an effect-size name.

### DP-1 / DP-2 — degenerate Camelot stub → whitespace re-extract
- **FIX, but it is the heaviest item and the one the v2.4.98 commit deferred.** The plan
  (from the foundation commit message + RC-T spec): detect a degenerate matched Camelot
  table (`shape=0x0` / caption-only / full-page-absorb) → discard → re-extract the
  caption-anchored region via `whitespace_cells` (now char-fallback-capable) on the
  gutter-band-clipped region + region prose-trim. **Touches the core `extract_structured`
  path for ALL papers** → requires the full ~48-paper guard-diff + 7-canary AI-verify
  before shipping. Side-by-side 2-panel split (L-006) is an added wrinkle for DP-1's table.

### DP-5 — correlation-matrix r-typing
- **(b) FIX (flatten):** type a correlation-matrix data cell as `r` (with its N + CI) when
  the table is a correlation matrix (extends REQUEST_11 / already done for 90203 T10).
- **(a) gated on capture:** cog_emo Table 2's glued cells need the RC-T whitespace fallback
  first; no r exists to type until the cell is un-glued. Shares the DP-1/DP-2 capture work.

### DP-4 — already working
- No code change for the rows themselves. The `eta2` typing is folded into DP-3.

### DP-6 — won't-fix
- Document as out-of-scope (figure-inset text). No code change.

---

## RESOLUTION (v2.4.98, this run)

| Defect | Status | What landed |
|--------|--------|-------------|
| **DP-3** (η²p) | **FIXED (table) / WON'T-FIX (text)** | Table: `flatten._infer_anova_eta2_hint` types the `est` column as `eta2` on the F-test/ANOVA structural signature, range-guarded to [0,1]; collabra.90203 T8/T9 now match the gold's `η²p`. Text: glyph has no ToUnicode (`pdffonts` uni:no) → OCR-tier won't-fix (documented). |
| **DP-5 (b)** (r-cells) | **FIXED** | `flatten._inline_stat_field` types a self-labeled `r = .67` cell under a generic "Effect size" header; cog_emo T8 rows carry typed `r` + CI matching the gold. |
| **DP-5 (a)** (CI split) | **FIXED** | `cell_cleaning._is_fragment_cell` recognizes a bracketed-CI close tail (`0.73]`) → CI rejoins `[0.59, 0.73]`, junk fragment rows gone (cog_emo T8 14→10 rows). |
| **DP-1** (Table 4 bare t) | **DEFERRED (page-fix prototyped + REVERTED)** | A caption page-attribution fix unblocked Camelot capture of Table 4's replication `t/df/d` in isolation — but the AI-gold canary verify showed it net-harmful corpus-wide (see below). Reverted; DP-1 remains unaddressed pending the gated capture cycle. |
| **DP-2** (Study 1 Table 1) | **DEFERRED** | Same page-fix; reverted. Table 1 is an 8-column grouped table beyond the lineless fallback regardless. |
| **DP-4** (Table 8/9/10 rows) | **WAS ALREADY WORKING** | Rows were present at v2.4.97; only the η²p typing was missing (= DP-3, now fixed). |
| **DP-6** (figure-inset) | **WON'T-FIX** | Figure-raster text, out of scope for text extraction (handoff agrees). |

**Why DP-1/DP-2 were reverted (the AI-verify caught what the unit suite did not).**
The caption page-fix (`find_caption_matches` advancing `char_start` past the leading
`\f`) is correct for the off-by-one page attribution and fixes `collabra.77859` in
isolation. But it also *populates the previously-empty `line_text`*, which re-scores
`_find_caption_for_table`'s same-page token-overlap and surfaces low-quality
whitespace tables. The mandatory 6-paper AI-gold canary verify found it **mis-pairs
tables whose captions share a page** — efendic T4↔T5 and cog_emo T8↔T9 swapped, and
plos_med only half-fixed (Table 4 still wrong, Table 5 degraded). All 1852 unit tests
stayed green; only the corpus AI-verify revealed it. Reverted to keep the corpus
regression-free (LESSONS L-010). The real fix needs same-page-caption disambiguation
in `_find_caption_for_table` + whitespace-region quality gating, as its own gated
cycle (full 48-paper guard-diff + canary AI-verify).

**Queued (immediate next, surfaced not dropped):** the DP-1/DP-2 capture cycle —
(1) make `_find_caption_for_table` robust when ≥2 table captions sit on one page
(bbox-proximity, not just token overlap), (2) the whitespace/char region prose-trim +
clean-data quality gate (already prototyped in this run's reverted whitespace.py —
salvageable), (3) THEN re-apply the page-fix and re-verify the full canary. Plus the
side-by-side 2-panel column split for DP-1's Original-study t (3.91/2.15).

## Recommended sequencing (severity × cost, leave-nothing-behind compliant)

1. **DP-3 table-side eta2 inference** + **DP-5(b) r-typing** — both pure-`flatten.py`
   changes, no core-path risk, gated by structural signatures, baseline-safe. Highest
   value / lowest risk. **Do first.**
2. **DP-1/DP-2/DP-5(a) capture** — the deferred degenerate-stub→whitespace re-extract.
   Core-path; full 48-paper guard-diff + 7-canary AI-verify. Larger, riskier cycle.
3. **DP-3 text-channel** + **DP-6** — WON'T-FIX, documented here + in the reply. (Surfaced,
   not silently dropped — the two CLAUDE.md exceptions: these need OCR, an architecture
   change only the user can sanction.)

Verification bar for every code change: full 26-paper baseline (no regression) + the
relevant AI-gold canary rows re-verified against the `reading`/`stats` golds (NEVER
pdftotext), per the project's ground-truth rule.
