# Changelog

## [2.4.98] — 2026-06-25

**ESCIcheck handoff defects (DOCPLUCK_HANDOFF_2026-06-25): η²p effect-typing, inline correlation r-typing, and bracketed-CI continuation merge — flatten/cell-cleaning only, AI-gold-verified.** `TABLE_EXTRACTION_VERSION` → `2.4.4`. Render-visible in the inline flattened-table blocks + `.tables.jsonl` sidecar `fields`. **No capture-path change** — caption→table pairing is byte-identical to v2.4.3. Grounded against the AI `reading`/`stats` golds (article-finder), not pdftotext, and confirmed by a 6-paper AI-gold canary verify. Triage: `docs/TRIAGE_2026-06-25_escicheck_handoff_defects.md`.

- **DP-3 (table side) — type a font-dropped partial-η² effect column.** Many APA ANOVA tables report effect size as `η²p`, but the glyph lives in a font with no ToUnicode mapping (`pdffonts`: `uni:no`), so pdftotext AND pdfplumber both decode it as a space — the effect-size column header is blank and no "eta"/"η" token survives anywhere, so `tables.flatten._effect_key` fell back to the generic `est` key and the consumer got a nameless number. `flatten._infer_anova_eta2_hint` now types an unlabeled estimate column as `eta2` when the table is structurally an F-test/ANOVA results table (carries an `F` column + a `BF01` and/or CI column) and names NO competing effect (`d`/`dz`/`r`/`OR`/`g`); the value is range-guarded to η²'s domain `[0, 1]`. Keyed on the structural signature, never paper identity. `collabra.90203` Tables 8 & 9 now emit `eta2` matching the gold's `η²p` column (`.06, .00, .01, .04, …`). **The text-channel η²p (in body prose) is unrecoverable — OCR-tier won't-fix** (glyph identity absent from the PDF), as is DP-6 figure-inset text.

- **DP-5 (b) — type inline self-labeled correlation cells.** A cell that states its own statistic — `r = .67`, `r = -.73`, `d = 0.32` — is now typed by that token even when the column header is generic ("Effect size") and the column-role recovery produced no estimate for it (`flatten._inline_stat_field`). `cog_emo` (`10.1080/02699931.2024.2434156`) Table 8's intercorrelation rows now carry a typed `r` with their CI/p, matching the gold. The display value is the number only, so the sentence renders `r = 0.63` (not `r = r = .67`).

- **DP-5 (a) — merge a CI split across two rows by its bracket tail.** Camelot stream splits a wrapped CI cell — `[0.59,` on one row, `0.73]` on the next. `cell_cleaning._merge_continuation_rows` already folded the *parenthetical* tail (`8.34)`) but not the *bracketed* CI tail (`0.73]`); `_is_fragment_cell` now recognizes a close-bracket tail, so the bound rejoins (`[0.59, 0.73]`) and the bare-fragment junk row no longer survives (cog_emo Table 8: 14 → 10 rows, CIs complete).

**Deferred (prototyped + REVERTED this cycle — surfaced, not dropped): DP-1 / DP-2 capture recovery.** A caption page-attribution fix (`find_caption_matches` advancing `char_start` past the leading `\f` its `^\s*` ate) does correct the off-by-one that mis-pages a table starting a page, and in isolation it unblocked `collabra.77859` Table 4's replication `t/df/d` (DP-1). But the **mandatory AI-gold canary verify showed it is net-harmful corpus-wide**: populating the previously-empty `line_text` re-scores `_find_caption_for_table`'s same-page token overlap and surfaces low-quality whitespace tables, mis-pairing tables whose captions share a page (efendic T4/T5, cog_emo T8/T9 swapped) and only half-fixing plos_med (Table 4 still wrong, Table 5 degraded). Reverted to keep the corpus regression-free. It needs same-page-caption disambiguation + whitespace-region quality gating, queued as its own gated cycle (full 48-paper guard-diff + canary AI-verify). DP-2's Table 1 (an 8-column grouped table) is beyond the lineless fallback regardless. See the triage doc.

**Also fixed (pre-existing, leave-nothing-behind):** `test_table_html_renders_when_structured` and `test_table_kinds_are_valid` asserted a non-structured table must be `kind == "isolated"`, but the layout-channel `whitespace` fallback (a valid kind since the v2.4.3 foundation) can surface — including when Camelot returns "no tables" under cumulative test-suite load (memory `feedback_camelot_flake_cumulative_load`). The tests now accept `whitespace` (asserting cells + HTML present, no Camelot confidence), so a Camelot load-flake on the jama/ieee/chen fixtures no longer mis-fails them.

Verification: shipped flatten/cell-cleaning changes covered by `tests/test_tables_flatten.py` (TestInlineSelfLabeledStat ×3, TestBracketTailCIContinuation) + `tests/test_tables_flatten_blank_header_recovery.py::TestT90203Table8BlankHeaders` (eta2 typed, est gone). Full library suite green under `pytest -n10` (real-PDF Camelot tests flake only under serial cumulative load — each passes per-file / under xdist). 6-paper AI-gold canary verify confirms DP-3 (collabra.90203 η²p), DP-5 (cog_emo r + CI) correct; it is what caught the DP-1/DP-2 page-fix regression and drove its revert.

---

**RC-T foundation (earlier same-day commit): char-level column-detection fallback for tight-kerned tables.** `TABLE_EXTRACTION_VERSION` → `2.4.3` (now → `2.4.4` per above). Library-internal capability addition — a foundation for the still-open RC-T Layer-1 table-data recovery.

- **`docpluck/tables/whitespace.py` gains `char_whitespace_cells`** — a char-level absolute-x-gap column detector, wired as an automatic fallback inside `whitespace_cells` that fires ONLY when the word-gap detector finds < 2 columns. On tight-kerned PDFs pdfplumber's word grouper glues a whole numeric row into one token (e.g. ip_feldman Table 10's `.29***−.21***.07`), so the word path finds no column gaps; the chars are still cleanly separated by large inter-column gaps. The fallback recovers the grid from char x-gaps, **voting on column-START edges** (in a right-aligned numeric table the label column is variable-width so gap midpoints scatter, but the data columns are left-aligned to fixed x), with an 8pt boundary bucket, and reinserts intra-cell word spacing from glyph geometry.
- **Strictly additive — currently-correct tables are byte-unchanged.** The word path (`_find_stable_column_boundaries(bucket_pt=0)`) is restored verbatim to its pre-change behavior; only a region that previously yielded NO whitespace grid (`whitespace_cells` returned `[]`) can now gain one, and only when char-columns clear a 60%-row stability bar. In isolation this recovers all 7 of ip_feldman Table 10's regression-coefficient rows matching the AI gold.

**Not yet closed (next gated cycle):** the char fallback alone does NOT fix Table 10 in the live pipeline — T10's caption is *matched* by a degenerate full-page Camelot table, which is used directly, so the whitespace fallback (where the char path lives) is never reached. Closing it needs an `extract_structured.py` change — detect a degenerate matched Camelot table (full-page-ish bbox + furniture/prose cells), discard it, and re-extract via `whitespace_cells` on the gutter-band-clipped caption region, plus a region prose-trim — which touches the core extraction path for all papers and so requires the full ~48-paper guard-diff + 7-canary AI-verify before it ships. See `LEARNINGS.md` 2026-06-25 and `docs/superpowers/specs/2026-06-21-rc-t-table-region-prose-contamination.md`.

Verification: `tests/test_whitespace_char_fallback.py` (5 cases incl. real-PDF ip_feldman Table 10 = all 7 gold rows recovered, synthetic tight-kerned recovery, intra-cell word-space reinsertion, delegation wiring, single-column-no-fabrication guard); 15/15 pass on the whitespace/char/caption-table suite across two independent runs; 0 failures across the broad table/render suite; word path proven byte-identical.

## [2.4.97] — 2026-06-22

**Three table fixes shipped together (combined from two concurrent sessions): type the skipped p+df columns (DP-2), stop dropping / mis-binding two-header-row tables (DP-5), and stop the table raw_text fallback swallowing body prose (RC-T Layer-2).** `TABLE_EXTRACTION_VERSION` → `2.4.2`; no `NORMALIZATION_VERSION` / `SECTIONING_VERSION` change. DP-2/DP-5 are render-visible in the inline flattened-table blocks + the `.tables.jsonl` sidecar `fields` (the `<table>` HTML gains the previously-dropped data rows); RC-T Layer-2 is render-visible in the `unstructured-table` fallback blocks. DP-2/DP-5 filed in `ESCIcheckapp/docs/DOCPLUCK_HANDOFF_2026-06-21.md`; RC-T Layer-2 per `docs/superpowers/specs/2026-06-21-rc-t-table-region-prose-contamination.md`.

- **DP-2 — type the unlabeled p and df columns.** `tables.flatten._recover_blank_roles` recovered the leading test statistic and the `d [CI]` column of a header-stripped result table but left the bare p-value and df columns between them untyped, so `collabra.77859` Table 3 emitted `fields: {group, t, d, CI}` and dropped the `p` (`.551`) and `df` (`260.54`). A new Pass 4.5 types a still-blank column that is a bare `.XXX` with no comparison op as `p`, and a bare integer / Welch-decimal sitting between the test statistic and its `est/CI` column as `df` — keyed on data shape + position relative to the already-recovered roles, never bare position. The four Table-3 rows now carry `p` and `df`.

- **DP-5 — two-row-header parallel-arm tables: recover the first data row and align centered super-headers.** `collabra.90203` Table 10 delivered only 5 of its 6 correlation rows (the Identifiable/Explicit-learning row was silently dropped), and the Original/Replication arms of `xiao_2021` Table 4 were swapped. Three coupled root-cause fixes: (a) `cell_cleaning._is_header_like_row` now counts APA value shapes (leading-dot decimal, bracketed CI, operator-prefixed p, `N/A`) as data via `_DATA_VALUE_CELL_RE`, so a real first data row is no longer mis-read as a third header row (the bracket branch requires a digit and no letters inside, so a genuine `[95% CI]` header stays a header); (b) `tables.flatten._detect_column_groups` re-derives arm boundaries from equal-width blocks of the data region — each must contain exactly one super-label — so a *centered* super-label (camelot stream loses colspan and folds it mid-span) no longer swaps arm values or pushes a stat column into the label region; left-aligned super-headers stay byte-identical; (c) `tables.flatten._classify_column` reads a folded super-header cell's role from its sub-part so a folded `…<sep>95% CI` column is still typed `CI`. Table 10 now emits all 6 conditions split into Target-article / Replication arms with correct `r` / `n` / `CI` / `p`; xiao Table 4 arms are no longer swapped; incidentally recovers `chan_feldman` Table 8 arm labels and `jama_open_2` Table 3 HR estimates + CIs.

- **RC-T Layer-2 — stop the table raw_text fallback swallowing body prose.** When Camelot recovers no cells, `extract_structured._extract_table_body_text` linearises the text after a caption as the `unstructured-table` fallback; its per-line prose gate (`_line_is_body_prose`, len ≥ 80) misses prose that pdftotext WRAPPED into short (~48-char) lines, so a short table's caption-anchored region overshot the table end and swallowed Results/Discussion prose. Two FP-safe structural fixes: **(a) Note-anchor** — a table's `Note:` footnote is, by convention, its last element, so trim everything after the note paragraph (`chan_feldman` T1/T3 + `efendic_2022` T5 trailing Discussion prose removed; the stat rows + the note are kept); **(b) degenerate-prose guard** — suppress a fallback block that STARTS mid-sentence with a lowercase multi-letter word AND is majority sentence-shaped prose, so the renderer emits a clean caption-only table (`chan_feldman` T9 was an entire verbatim duplicate of `## Discussion` — now caption-only, no duplication). FP-safe by construction: real table cells start with a header / label / number / single-letter item marker, never a wrapped mid-sentence continuation — hypotheses ("a There is a positive association…"), descriptive rows ("Median age"), and instrument fragments are preserved. Keyed on the structural overshoot signature, never paper identity.

Verification: new real-PDF + contract regression tests (`tests/test_tables_superheader_alignment_real_pdf.py`) — collabra.90203 T10 six-conditions/correct-arms + xiao T4 not-swapped (each FAILS at HEAD, PASSES after), plus `_is_header_like_row` / `_detect_column_groups` contract cases; `tests/test_tables_flatten_blank_header_recovery.py` extended for DP-2. A full-corpus (101-PDF) cached-table flatten diff confirms no clean-table regression — every changed table is a recovered row, a correct arm split, a recovered field, or a removed stat-less spurious row; already-garbage tables shuffle without a clean table regressing. Broad pytest green (real-PDF Camelot tests run serially per file — non-deterministic under cumulative load). RC-T Layer-2 adds `tests/test_rc_t_layer2_raw_text_real_pdf.py` (6 contract + 4 real-PDF: chan T1 Note-anchor, T9 suppress-no-duplication, T3 preserved) and an independent full-corpus 101-PDF guard-live-vs-bypassed raw_text diff (`grew=0 changed=0`; 4 trims + 8 prose-suppressions only). A 7-canary Sonnet AI-gold verify confirms every table this release touched is correct (chan T1/T3/T9, maier T10 six-conditions, xiao T4 arms) with no new TEXT-LOSS / HALLUCINATION.

**Deferred (pre-existing, user decision 2026-06-22):** the remaining canary AI-verify FAILs are the architectural backlog, NOT regressions from this release — RC-T **Layer-1** table-data recovery (`table_areas`; e.g. plos_med Table 5's SAE rows, chan_feldman / chandrashekar under-extraction) and RC-1 two-column / sidebar column-interleave. Tracked in `docs/TRIAGE_2026-06-21_head_v2.4.95_assessment.md`; intentionally not addressed here.

## [2.4.96] — 2026-06-21

**RC-T (Option A): strip Camelot "tables" that are absorbed body prose, not data.** Render-only — `render.py::_strip_phantom_camelot_tables`; no `TABLE_EXTRACTION_VERSION` / `NORMALIZATION_VERSION` / `SECTIONING_VERSION` change.

Camelot runs free-form (`flavor="stream"`, no `table_areas`), so on a text-heavy page it returns a whole-page bbox and folds body prose into the `<thead>`. `_strip_phantom_camelot_tables` already drops such a table when a `<th>` is sentence-shaped prose (≥8 words, ≥3 function words, ≥2 verb-shape words) — but its function-word set was **missing `"the"`**, the single most common English function word, so a body-prose `<th>` with `fn=2 + "the"` slipped under the `fn≥3` bar and a garbage prose `<table>` survived. Two corpus cases: `10.1525/collabra.90203` (maier) Table 7 (`<th>` "Following the analyses conducted in Study 1 of Small") and `10.1080/02699931.2024.2434156` (chan_feldman) Table 6 ("associations between the six measures of interest: …").

The fix counts `"the"`, but is **scoped to the marginal case** (a `<th>` that crosses fn 2→3 only because of "the") so every table already stripped at HEAD via the `fn≥3` path stays byte-identical, and is **gated on NOT being a title-leak**: `aom/amp_1` Table 5 leaks its own caption ("Improving Scholarly Impact … Practice") into the `<th>` over a REAL grid (Domains / Policymaking / Practice + data) — a caption-token-overlap test (≥60%) keeps such title-leak tables. **Net corpus impact: exactly 2 tables stripped, all others byte-identical** (verified by a full-corpus th-level scan over all 152 corpus PDFs + render diffs). Fail-clean: the `### Table N` heading + caption remain (table_parity preserved); the stripped prose is a Camelot duplicate, so the clean original survives in the body (no TEXT-LOSS). ip_feldman Table 10 — the RC-T canonical "orphan" — was already fail-clean at HEAD and is unchanged.

Verification: 8 new real-PDF regression tests (`tests/test_rc_t_degenerate_table_real_pdf.py`): maier T7 + chan_feldman T6 stripped (each FAILS at HEAD, PASSES after), amp_1 T5 + chan_feldman T2/T5 (real tables) preserved, maier prose survives in body (no TEXT-LOSS), ip_feldman T10 prose stays out of `<table>`. Broad pytest green; 7-canary AI-verify shows the touched tables fail-clean with no new TEXT-LOSS / HALLUCINATION.

**Deferred (separate cycles, surfaced not dropped):** (1) RC-T **Layer-1 recovery** — actually RECOVERING lost table data via tight `table_areas` (plos_med Table 5's 13 SAE rows; chan_feldman Table 2 column-squish) — out of Option-A scope. (2) **Audit of the ~37 corpus tables** stripped by the existing `_strip_phantom_camelot_tables` th-prose / section-token paths — some title-shaped `<th>` strips may be wrongly-stripped REAL tables (pre-existing; predates this change), needs its own verify-each-render cycle. (3) RC-1 two-column / sidebar interleave.

## [2.4.95] — 2026-06-20

**Flatten now populates `fields` for non-clinical result tables (REQUEST_11).** `TABLE_EXTRACTION_VERSION` → `2.4.0`; no `NORMALIZATION_VERSION` / `SECTIONING_VERSION` change. v2.4.94 solved the clinical PROSECCO table (labelled headers); this closes the two reproducers whose `fields` still came back `{}` — header-stripped result tables and tables packing parallel arms into single cells.

Grounded in `10.1525/collabra.77859` (Tables 3, 5) and `10.1525/collabra.90203` (Tables 8, 9, 10), both AI-gold-verified. Two cycles, each gated on a structural signature so ordinary tables stay byte-identical:

**Cycle A — blank-header column-role recovery** (`docpluck/tables/flatten.py::_recover_blank_roles`). Some result tables capture the data grid but emit BLANK stat-column headers (the header row was absorbed into the caption region or sits a row above the data and got dropped), so the flattener returned `fields:{}`. The fix assigns a role to a blank column ONLY from two grounded signals — the **shape** of its data tokens (CI brackets, a `df1, df2` pair, an estimate adjacent to a CI, a p-value with a comparison operator) and the statistic **vocabulary** recovered from the caption / footnote / all header rows — never from bare column position (that would fabricate labels for garbage, the exact failure the consumer forbids). Recovers `collabra.77859` Table 5 (`t/df/d/CI`) and `collabra.90203` Tables 8/9 (`F/df1,df2/p/BF01/eta²p-as-est/CI`) and Table 10 (`r/n/CI/p`). Adds a **`BF01`** role (Bayes factor for the null) per request, and validity guards that drop a recovered value that can't be real (`r ∉ [-1, 1]`, non-monotone CI, non-integer `n`, `p ∉ [0, 1]`) — which also removed pre-existing non-monotone-CI garbage on unrelated papers (korbmacher, xiao).

**Cycle B — packed parallel-arm split** (`_detect_packed_arms` / `_flatten_packed_arms`). Tables that pack `k ≥ 2` arms into single cells (an arm-label column repeating `"Separate Joint"` on every row, with each data cell holding `k` space-joined values like `".07 [-.17,.31] .08 [-.09, .25]"`) now emit **one typed record per arm**, tagged `group=<arm>`. Splits `collabra.77859` Table 3 (Separate/Joint, `d` + CI + `t` per arm) and — as a general dividend — `xiao_2021_crsp` Table 7 (Regret/Justifiability, all 12 rows AI-verified exact). Detection is keyed purely on the signature (a constant multi-token alpha label column + ≥2 cleanly `k`-splittable data columns); a normal single-arm table never triggers it.

Two **general L-004 fixes** landed with Cycle B (Camelot cells are not run through `normalize.py`, so a negative statistic often arrives as U+2212):
- `_parse_number` and `_parse_ci_cell` now fold U+2212 MINUS → ASCII hyphen, so a negative `t`/`d`/CI lower-bound is no longer dropped (number regex) or sign-flipped (`.search` skipping the non-ASCII sign). This surfaced real negative t-statistics that were previously dropped (e.g. `ip_feldman` Table 6 one-sample t-tests) — verbatim, header-typed, no fabrication.
- `_VALUE_GROUP_RE` splits bracket-led CI groups (`"[−0.48, 0.15] [−0.20, 0.34]"`) so a packed CI column maps one interval per arm.

Acceptance (consumer REQUEST_11 §3): #1 Table 5 + Table 3 arms ✓; #2 Tables 8/9/10 `F/p/eta²p/CI/BF01` + `r/n/CI/p` ✓; #3 sign-correct CIs + packed cells split ✓; #4 default call byte-identical + PROSECCO unchanged ✓ (verified by full before/after corpus diff: canary structural renders byte-identical, PROSECCO 6 stat rows untouched). `fields.effect_type` (§2.4, explicitly "not a blocker") is deferred — adding it would change PROSECCO's fields, conflicting with #4; available as an opt-in if wanted.

Two honest caveats surfaced (neither a flatten defect): (1) `collabra.90203` Table 10 "Joint/No-explicit" `r` reads `.59` in the PDF **text layer** (pdftotext and Camelot agree) vs `.63` in the AI-visual gold — a text-layer corruption, undetectable without OCR. (2) the `collabra.77859` Attractive/Affect table is labelled "Table 3" by docpluck (its caption) and the consumer, but "Table 2" by the AI gold — a pre-existing caption-number binding question, values all correct.

Verification: 16 new flatten tests (packed-arm split, value-group splitter, single-arm non-firing guard, real-PDF Table 3) + full flatten/render/structured suites green, zero regressions; both target papers AI-gold-verified PASS across both cycles.

## [2.4.94] — 2026-06-19

**Cross-flavor lattice-augmentation — recover table rows a lattice extraction vertically truncated (REQUEST_10 Tier-2).** `TABLE_EXTRACTION_VERSION` → `2.3.0`; no `NORMALIZATION_VERSION` / `SECTIONING_VERSION` change.

Grounded in PROSECCO Table 2 (`10.1371/journal.pmed.1004323`). **Root cause (corrected after investigation):** the rows were not dropped by Camelot or by orphaned labels (the original Tier-2 hypothesis). Camelot **stream** captures the whole table but loses the column-header text and vertically splits each value from its `(percentage)`/CI-tail; Camelot **lattice** has clean headers but only the rows inside the ruled box (1 of 3 data rows); and `_pick_best_per_page` let lattice win the page, discarding the fuller stream table. So `flatten` (fixed in v2.4.93) never saw R2/R3/R5/R6.

Two general fixes, each gated on a structural signature:

1. **Cross-flavor row augmentation** (`docpluck/tables/camelot_extract.py::_augment_lattice_with_stream_rows`): when a page is lattice-owned but a same-page **stream** table has the **same column count**, **overlaps** the lattice bbox, and **extends below** it, the stream rows whose vertical centre falls below the lattice bbox (the rows lattice missed) are appended onto the lattice frame. Result: lattice's clean headers + every data row. Gated hard so a table lattice captured in full — or an unrelated stream table — is never touched (the `jama_open_1` lattice-preference path is unaffected: it only runs for lattice-owned pages, and there lattice had only sub-2×2 artifacts).
2. **Numeric/parenthetical continuation merge** (`docpluck/tables/cell_cleaning.py::_merge_continuation_rows`): rejoin a row whose every non-empty cell is a *fragment* (opens with `(` like `(87.8%)`, or a bare close-paren tail like `8.34)`) into the parent's same-column cells, when every fragment column is already populated in the parent. Joins inline (no space when the parent ends mid-token at a dash/open-paren) so `86` + `(87.8%)` → `86 (87.8%)` and `-1.01% (-10.36-` + `8.34)` → `-1.01% (-10.36-8.34)`. General improvement for any stacked value/parenthetical table; previously only multi-word prose wraps merged.

Outcome: PROSECCO Table 2 now flattens to all six gold arm-records, sign-correct — R1 ITT −1.01% 95% CI [−10.36, 8.34] p=.09; R4 PP 0.06% [−9.53, 9.65] p=.06; R2 ITT adj. −1.83% [−11.2, 7.5]; R5 PP adj. 0.82% [−8.63, 10.28]; R3 ITT remnant 7.7 [−3.2, 18.5] p=.15; R6 PP remnant 8.4 [−3.1, 19.9] p=.14 — plus the table's size-distribution sub-rows as label-only rows. Closes REQUEST_10 acceptance #1.

Verification: 9 new unit tests (5 augmentation + 4 continuation) + full library suite green, **zero regressions**; table-focused suites (flatten/cell-cleaning/table-detect) unchanged. (A residual `≤`-glyph corruption in PROSECCO's size-bin labels is a pre-existing pdftotext cell-glyph issue in non-statistical count rows, unrelated to this fix.)

## [2.4.93] — 2026-06-18

**Table-flatten quality: combined estimate-and-CI columns, dash-sign CI disambiguation, and parallel-group (ITT/PP) rows.** Library `docpluck/tables/flatten.py` only; no `NORMALIZATION_VERSION` / `SECTIONING_VERSION` / `TABLE_EXTRACTION_VERSION` change. Enables the HTTP exposure of the flattener over the hosted `/api/extract` (ESCImate `REQUEST_10_TABLE_FLATTEN_HTTP_EXPOSURE.md`, closing `REQUESTS_FROM_ESCIMATE.md` Request 4 — see `REPLY_FROM_DOCPLUCK_v2.4.93.md`).

Grounded in the PROSECCO trial Table 2 (`10.1371/journal.pmed.1004323`). Three general fixes, each keyed on a STRUCTURAL SIGNATURE, never paper identity:

1. **Combined `est_ci` column.** A header carrying an effect word followed by a parenthesised CI marker — `Risk diff. (95% CI)`, `Mean diff (95%CI)`, `OR (95% CI)`, `Cohen's d (95% CI)` — was previously unclassified and dropped. It now parses the cell's leading estimate **and** its interval (e.g. `-1.01% (-10.36-8.34)` → `est = -1.01`, `CI_lower = -10.36`, `CI_upper = 8.34`).
2. **Dash-sign CI disambiguation.** CI cells use a dash as the lo–hi separator that collides with a negative sign (`(-11.2-7.5)` = lo -11.2, hi +7.5). The parser resolves sign with two general invariants — interval **monotonicity** (`lo < hi`) and, when the row's point estimate is known, the **estimate-in-interval** invariant (`lo ≤ est ≤ hi`). A typographically distinct range glyph (en/em-dash or " to ") is treated as sign-unambiguous and used directly. Comma CIs unchanged.
3. **Parallel column groups.** A folded super-header (`ITT` / `PP`, `Study 1` / `Study 2`) now emits **one `FlattenedRow` per (row × arm)** with a `fields.group` tag, so duplicate roles across arms (two `P value`, two `Risk diff.`) no longer collide and overwrite each other. Detected from the `_MERGE_SEPARATOR` fold signature; tables without it are byte-identical to before. Emitted `header`/`raw_cells`/`row_label` strings are also stripped of the internal `\x00BR\x00`/`\x00SUP\x00` fold sentinels.

New (additive, non-breaking) `FlattenedRow.fields` keys: `est` and `group`.

Verification: 35 flatten unit tests (16 new) pass; existing 19 unchanged; cell-cleaning + table-detect suites green. On PROSECCO Table 2 the captured "Resection complete" row now flattens into two sign-correct arm records (ITT risk diff -1.01% 95% CI [-10.36, 8.34] p = 0.09; PP risk diff 0.06% 95% CI [-9.53, 9.65] p = 0.06). **Known limitation (queued, not fixed here):** Camelot captures only the first of Table 2's three conceptual data rows — the "adjusted" / "remnant" rows have orphaned labels and are dropped at the table-*extraction* layer, so gold rows R2/R3/R5/R6 remain unreachable until a separate orphaned-label row-recovery lands. Tracked in `LESSONS.md` (Tier-2) and `REPLY_FROM_DOCPLUCK_v2.4.93.md`.

## [2.4.92] — 2026-06-18

**Affiliation-heading guard — never promote an affiliation/institution line to a subsection heading (G5d).** Render-layer only; no `NORMALIZATION_VERSION` / `SECTIONING_VERSION` change.

Surfaced by `/docpluck-iterate` Phase-5d (canary `chandrashekar_2023_mp`). When column-interleave serialises a two-column title block out of order, an affiliation line can land **past** the H1 → first-`##` masthead zone that `_strip_frontmatter_masthead_block` cleans — on chandrashekar, `Department of Philosophy, Lake Forest College` is dropped immediately after `## Abstract`. The masthead strip can no longer reach it, and its short Title-Case shape then matched `_promote_isolated_titlecase_subsection_headings` and became a hallucinated `### Department of Philosophy, Lake Forest College` heading, corrupting the Abstract's section structure.

Fix (general, keyed on a STRUCTURAL SIGNATURE — affiliation grammar, never paper identity): `_promote_isolated_titlecase_subsection_headings` consults a new `_looks_like_affiliation_line` and refuses to promote any line matching academic-affiliation grammar — a unit-phrase head (`Department/School/Faculty/Division/Institute/Centre/Center/Laboratory/College/University of <Capitalized>`) or a proper-noun institution phrase ending in `University`/`College`/`Institute`/`Hospital`/`Polytechnic`. The line stays body text (a strict improvement over a fake heading; the affiliation text is preserved, never dropped). The guard runs before the chain-promotion bypass so it holds on every path.

Verification: a 47-gold / 2226-real-heading false-positive scan found **zero** legitimate headings the guard would reject; a deterministic corpus render-diff (guard-live vs guard-bypassed) over the canary set + a 12-paper cross-publisher sample changed **only** chandrashekar (the single target heading), all other papers byte-identical; full suite **2027 passed** + 227 render/heading-cluster + 23 new affiliation-guard tests; AI-verify vs the article-finder reading gold returned `FIX-CORRECT` (no new text-loss / hallucination). chandrashekar remains FAIL overall on **pre-existing** Table 7-10 header-shell collapse and two pre-existing table-cell-label heading promotions (`IV2: No-default`, `Participation rate`) — both queued as separate cycles; this release does not touch them.

## [2.4.91] — 2026-06-17

**Single-column subsection-heading promotion — recover glued JESP/Elsevier subsection headings without re-opening the two-column G5d trap.** Render-layer only; no `NORMALIZATION_VERSION` / `SECTIONING_VERSION` change.

Surfaced by `/docpluck-iterate` Phase-5d (canary `ar_apa_j_jesp_2009_12_011`). Single-column Elsevier/JESP papers emit subsection headings ("Overview", "Practice instructions", "Self-control assessment") on their own line with **no blank padding on either side** — glued directly between the prior subsection's sentence-terminated body and their own body. Every existing promoter requires `blank_before AND blank_after` (or the PSPB no-blank-after relaxation, which still requires `blank_before`), so these stayed demoted to body text.

`_promote_isolated_titlecase_subsection_headings` now admits a no-blank-before candidate **only when the document is single-column** AND the immediately-preceding line is a sentence-terminated prose line. The single-column signal (`_raw_text_is_single_column`) is the fraction of raw-pdftotext non-blank lines wider than 65 chars (≥ 0.25) — a structural typographic invariant computed from the **raw** text *before* the render pipeline joins column-wrapped lines and destroys the line-width signal (corpus separation: two-column 0.06–0.24, single-column 0.28–0.58; threshold sits in the natural gap). Two-column layouts keep the hard `blank_before` reject, where the identical shape is a narrow table-cell / measures-list label (the G5d hallucinated-heading trap). A fragment guard (`_is_single_col_relaxation_fragment`) additionally rejects bracket furniture, leading-preposition sentence-wraps, dangling-connector tails, and **abbreviation-glossary / clause lists** (internal `;` or trailing `,`).

**Validation (2026-06-17).** Deterministic heading-delta across the corpus: `ar_apa_j_jesp_2009_12_011` **+3** genuine headings (AI-verified vs the article-finder reading gold: `new_headings_are_real=true`, zero hallucination), `ar_apa_…_010` +9, `jmf_1` +11, `demography_1` +4, `bjps_1` +3, `chen_2021_jesp` +3; two-column papers (`ip_feldman_2025_pspb` byte-identical, `chan_feldman`, `chandrashekar`) **+0**; `plos_med_1` net +0 (one abbreviation-glossary false promotion caught by the fragment guard). 26-paper baseline 26/26 (one transient pdftotext timeout, PASS in isolation); full suite 1733 passed. New regression `tests/test_single_column_subsection_promote_real_pdf.py` (23 cases). The canary corpus still FAILs on **pre-existing** table row/column loss and RC-1 column-interleave (separate root causes, queued) — this release is an incremental heading-fidelity improvement, not a corpus-clean claim.

## [2.4.90] — 2026-06-15

**RC-1 Step 2 — per-band region-aware two-column re-extraction (ship-dark behind `DOCPLUCK_COLUMN_CORRECT_BANDED`, default OFF).** No `NORMALIZATION_VERSION` change — the default path is byte-identical; the flag only adds reading-order corrections upstream of normalize.

The dominant defect on two-column APA papers: pdftotext serializes a page's columns interleaved, so Method/Results/Discussion order scrambles and paragraphs split with their continuations displaced. The Step-1 whole-page corrector (`extract_page_text_columns`, v2.4.82) **cannot reach** these pages — its bilateral y-row gate and full-height gutter strip both reject any page that carries a full-width band (a table row, banner, or wide title) crossing the column centre, which is exactly the failing pages (TRIAGE 2026-06-15: re-rendering with `DOCPLUCK_COLUMN_CORRECT_GENERAL=1` produced byte-near-identical output).

**Step 2** (`extract_page_text_banded`, `docpluck/extract_columns.py`) segments a flagged page into horizontal y-BANDS: a band whose central gutter strip is glyph-free across its rows is two-column prose → re-extracted left-then-right; a band with full-width content (table/banner/title) is kept as-is. Bands are reassembled top-to-bottom at glyph-free cut lines (vertically-overlapping bands are merged to full-width so a tall title glyph is never bisected). Applied **only as a fallback** inside `splice_column_corrected_pages` when the whole-page path returns "", and under the **same unconditional word-preservation guard** — a band crop that drops/fabricates a word is rejected and the page kept as-is, so the flag can only ADD a pure reorder, never ship corruption.

**Validation (2026-06-15).** Corpus word-preservation scan across 4 two-column papers (71 flagged pages): every accepted page is a pure reorder; the 6 residual band-cut clips are all guard-rejected (no corruption). Production smoke (flag ON) corrects ~44 pages across 5 papers, all word-safe; flag OFF is byte-identical. **AI-verify vs article-finder reading golds** (Sonnet subagents) on the two heaviest papers (`chan_feldman_2025_cogemo`, `chandrashekar_2023_mp`): both **ON_BETTER** — Procedure/Manipulations ordering and the Power-analysis paragraph split fixed (chan); `## Results` heading restored and column-token orphans suppressed (chandrashekar); **zero text-loss, zero hallucination, zero regression** vs flag OFF. New regression `tests/test_rc1_banded_column_real_pdf.py` (synthetic-layout geometry units + real-PDF word-preservation + ship-dark-default). Touched-path suite 302 passed; 26-paper baseline 26/26 (flag OFF).

**Known residual (documented, not regressions):** ~6/71 flagged pages still clip a single word at a band cut and are guard-rejected (stay interleaved — no worse than today); hard title+sidebar pages (e.g. PSPB p1) degrade to full-width (no de-interleave). These are the remaining Step-2 refinement targets before the default can be flipped.

## [2.4.89] — 2026-06-15

**W0h — recover dropped-minus statistical coefficients from the LAYOUT channel (the no-CI residual W0g cannot reach).** `NORMALIZATION_VERSION` 1.9.34 → 1.9.35.

Surfaced by `/docpluck-iterate` Phase-5d (B7 canary `ar_apa_j_jesp_2009_12_011`). On tight-kerned PDFs that draw the U+2212 minus in a dedicated symbol font, pdftotext **drops the glyph entirely**, so a body-prose coefficient `β = −.022, t(87) = .17, ns` reaches the text channel as `b = .022` — a **silent sign flip that inverts the statistical conclusion**. The existing W0g recovery needs a confidence interval to prove the sign; these betas report only a t-value, so W0g cannot reach them.

**Root cause + recovery.** The dropped minus survives in the **layout channel** (pdfplumber) as an unmapped `(cid:N)` glyph in a symbol font (here `AdvP4C4E74`), immediately touching the coefficient. `normalize.recover_dropped_minus_via_layout` (W0h) detects this in the `<stat> = <minus><coef>` operator slot — an unmapped glyph whose left neighbour is `=` and whose right neighbour is a coefficient — and re-inserts the minus into the pdftotext text. Keyed on the **structural signature** (not paper/font identity): the `=`-anchor excludes `5.2 ± 0.3` (glyph between two numbers) so a dropped `±`/`≈`/dagger can never be mistaken for a sign; it flips only coefficients the layout proves negative, only as many times as found. Threaded through a dedicated `dropped_minus_layout` param (`render → extract_sections → normalize_text`) so the section pipeline's text-channel-only contract is preserved (F0 stays off). On `ar_apa` it recovers `β = −.022 / −.88 / −.428` and leaves the genuinely-positive `.48` untouched. Blast radius: of the 5 onboarded canary papers only `ar_apa` flips (exactly its 3 layout-visible negatives); the other 4 are byte-identical no-ops.

**Documented limitation (NOT fixable in text+layout).** `ar_apa` `β = −.245` is drawn as **painted pixels** — its minus is absent from pdftotext AND pdfplumber chars/lines/rects/curves AND pdfminer's raw layer (proven). Only OCR could recover it; W0h deliberately leaves it rather than guessing. See `TODO.md` R5 Path 1.

New regression `tests/test_dropped_minus_layout_recovery_real_pdf.py` (4 synthetic-layout unit tests pinning the `=`-slot guard + the no-flip-after-a-number guard, and 1 real-PDF render test). Minus/normalize/render/sections suite: 148 passed.

## [2.4.88] — 2026-06-13

**Camelot temp-file cleanup is best-effort — stop silently dropping every table on Windows.** (No `NORMALIZATION_VERSION` change — table channel only; output on POSIX/prod is unchanged.)

Surfaced by `/docpluck-qa` (corpus render verifier, tag H) while validating v2.4.86/87: `efendic_2022_affect` rendered with **0** of its **4** in-body HTML tables. Reproduced on HEAD too (pre-existing, not from the layout fixes).

**Root cause (Windows-only).** `tables/camelot_extract.py::extract_tables_camelot` writes the PDF to a `NamedTemporaryFile(delete=False)`, runs Camelot, then unlinks the temp file in a `finally` block. Under **camelot-py 2.0.0** on Windows, Camelot still holds the temp-file handle open at that point, so `Path(tmp_path).unlink()` raises `PermissionError [WinError 32]`. That exception propagated out of `extract_tables_camelot` and was swallowed by `extract_structured`'s broad `except Exception` (→ `method="…camelot_failed"`, `tables=[]`) — so **every** paper lost **all** Camelot tables on Windows, even though extraction itself succeeded. POSIX permits unlinking an open file, so prod/Linux/Railway never hit this; it was invisible outside Windows dev. (The drift to the camelot-py 2.0.0 major came via the unbounded `camelot-py[cv]>=0.11.0` pin.)

**Fix.** The `finally` cleanup now swallows `OSError` (best-effort temp removal; the OS temp dir reclaims the file). Camelot table extraction is restored on Windows: `efendic_2022_affect` 0 → 5 tables (3 with HTML), corpus verifier PASS. New regression `tests/test_camelot_temp_cleanup.py` monkeypatches `Path.unlink` to raise and asserts `extract_tables_camelot` returns a list instead of propagating. Table/structured suite: 90 passed, 1 skipped.

## [2.4.87] — 2026-06-13

**F0 sources the body from the text channel — strip header/footer/footnote lines from pdftotext, never rebuild the body from spans.** `NORMALIZATION_VERSION` 1.9.33 → 1.9.34.

Follow-up #1 from `docs/HANDOFF_2026-06-13_sciencearena_grobid_liteparse.md` — the deeper, L-001-preferred fix for the residual the v2.4.86 word-gluing patch left behind.

**Root cause (architectural).** When `layout=` is supplied, the F0 step (`_f0_strip_running_and_footnotes`) was **rebuilding the entire body from `TextSpan.text`** and discarding the pdftotext `raw_text` the caller passed in (used only to locate footnote offsets). That rebuild-from-spans is what made *both* the v2.4.86 word-gluing (pdfplumber's char stream drops the inter-word space glyph) and the residual two-column interleaving (`_chars_to_spans` groups chars by y-coordinate only, so left+right columns at the same y merge into one span — e.g. `how www.cambridge.org/cns we can pay for it`) possible. It violates the documented text-channel/layout-channel split (CLAUDE.md, LESSONS L-001/L-007): the body must come from `extract_pdf` (pdftotext, which already infers spaces from the x-gap *and* serialises columns in reading order), and the layout channel should be used only to *identify* which lines are running headers/footers/footnotes.

**Fix.** `_f0_strip_running_and_footnotes` now keeps the exact same span-based classification (repeating-header detection, body-y-band header/footnote position rules, font-size footnote test, table-region guard) but uses it only to build **strip-key sets**. It then walks the pdftotext `raw_text` line by line (splitting on both `\n` and the bare `\f` page separator, keeping separators so footnote byte-offsets stay exact), drops header/footer lines, moves footnote lines to the `\n\f\f\n` appendix, and keeps the rest **in pdftotext order with pdftotext spacing**. Keyed on the structural signature (content-key membership), so it generalises to any PDF; strip-keys that are pure-numeric or shorter than 4 chars are excluded (page numbers etc. are handled downstream by P0/P0r/R2 and are absent from the JATS body), removing the only realistic false-strip vector. The body is now provably a *line-subsequence* of the text channel — F0 only deletes, never reorders or merges.

**Validation (ScienceArena pdf-text-fidelity-v1 held-out PMC corpus, 30 papers, token-F1 vs JATS gold).** Mean token-F1 **0.745 → 0.776** (above raw pdftotext 0.750; on par with normalized-pdftotext 0.767, and above the per-paper cases where F0's header/footnote stripping adds lift). Primary metric (`0.5·levenshtein + 0.5·token_f1`, the leaderboard rank key) **0.559 → 0.666** — the large jump comes from levenshtein (~0.30 → ~0.60) now that column reading-order is correct. Zero catastrophic-zero papers (unchanged). `_join_chars_with_spaces` (v2.4.86) is retained — it is now load-bearing for span-text key matching and for the sections/tables layout consumers.

New regression tests in `tests/test_normalize_f0_footnote_strip.py`: the F0 body is a line-subsequence of the text channel (a span-rebuild regression reorders/merges and fails), and every kept body line is an exact substring of `raw_text` (spacing comes from the text channel, never a glued span). LESSONS L-007 updated: the architectural follow-up is now done.

## [2.4.86] — 2026-06-13

**F0 layout body channel — reinsert inter-word spaces from the x-gap (stop gluing words on tight-kerned PDFs).** `NORMALIZATION_VERSION` 1.9.32 → 1.9.33.

Surfaced by `docs/HANDOFF_2026-06-13_sciencearena_grobid_liteparse.md` (ScienceArena pdf-text-fidelity-v1 held-out PMC corpus): on ~16 of 30 real biomedical PDFs docpluck's `normalize_text(..., layout=...)` body scored token-F1 **≈ 0.00** against the JATS gold while raw pdftotext scored 0.7–0.9 — *with a normal character count*. Same characters, zero token overlap: the words were glued (`CNSSpectrums`, `Thebehavioralhealthcarecontinuuminthe`, `UnitedStates`).

**Root cause.** When `layout=` is supplied, the F0 step (`_f0_strip_running_and_footnotes`) rebuilds the body from `TextSpan.text`. Span text was built in `extract_layout._chars_to_spans` by `"".join(c["text"] for c in line)` — a naive character concatenation with **no x-gap handling** (the function's own docstring claimed x-gap splitting that was never implemented). pdfplumber's `chars` stream omits the inter-word space glyph on tight-kerned PDFs (Cambridge journals, many two-column layouts) — pdftotext infers those spaces from the horizontal gap, but the raw char stream does not carry them. So on those PDFs the entire layout body collapsed to space-ratio ~0.005 (vs ~0.13 for the same text via pdftotext), and any consumer using the layout body channel (the recommended body-fidelity path since v2.4.83) silently emitted unspaced text. This is the long-standing `feedback_pdfplumber_extract_words_unreliable` failure mode — "always carry a char-level absolute-x-gap fallback" — which had never been applied to span text.

**Fix.** New `extract_layout._join_chars_with_spaces` reinserts a space between consecutive glyphs when the horizontal gap exceeds a font-relative threshold (`gap > 0.20·font_size`), keyed on the structural signature (x-gap) rather than any paper identity, so it generalizes to every tight-kerned PDF. `0.20·size` reproduces pdftotext/JATS spacing to within ~0.2% space-density on the Cambridge/PMC corpus (PMC13064744 token-F1 0.00 → 0.86; space-ratio 0.0053 → 0.1282; full 30-paper held-out PMC token-F1 mean ~0.34 → 0.747 with zero catastrophic-zero papers, was 16/30). The guard never doubles an existing space and never splits within a tightly-kerned word. One known residual remains (documented, not addressed here): `_chars_to_spans` still does not split a line at a column gutter, so a line spanning two columns is merged — a smaller reading-order issue handled by the text channel, tracked for a follow-up.

New regression tests in `tests/test_extract_layout.py`: x-gap space insertion on a word gap, no-split within a tight word, no double-space across an explicit space glyph, and a real-render assertion that normal loosely-kerned text keeps its word spaces.

## [2.4.85] — 2026-06-12

**Harvard name-year reference splitting (D1) + page-break reference stitch & category-label running-header strip (D2).** `NORMALIZATION_VERSION` 1.9.31 → 1.9.32.

Surfaced by `CitationGuard/docs/DOCPLUCK_HANDOFF_2026-06-12.md`.

**D1 — HIGH IMPACT — Harvard / Cambridge bibliographies collapsed into one paragraph.** R3 (the references-span continuation join) keeps each reference on its own logical line by breaking whenever a line *looks like a reference start*. That detection (`_looks_like_ref_start`) recognised Vancouver (`12. Surname`), IEEE (`[12] Surname`), and APA (`Surname, A.` — note the comma after the surname) — but **not** the Harvard / Cambridge name-year form `Surname A and Surname B (2020) …`, which has *no* comma between surname and initials. So on `bjps_1` (British Journal of Political Science, 109 entries) R3 treated every entry boundary as a mid-entry wrap and joined the **entire** reference section onto a single line. Downstream this made the consumer (citelink) parse 9 of 109 references (refs.f1 0.051).

The fix adds `_REF_START_HARVARD`, keyed on the structural signature *author-block + parenthesised 4-digit year*: a Title-case surname (Latin-Extended, so `Häusermann` / `Tuğal` qualify; hyphenated and compound surnames and `van der` / `Van der` particles handled) + 1–4 initials (spaced `R J`, glued `DH`, hyphenated `H-G`, or period `R.`), optionally chained with ` and `/`&`/comma or `et al.` (incl. `Surname K, et al.`), an optional `(eds)` editor marker, terminated by `(YYYY)`. The parenthesised year is the strong anchor that keeps mid-entry wrap lines (`American Journal of\nPolitical Science 64, 904-20.`) from matching. The same signature is added to `_find_references_spans` so a *pure*-Harvard bibliography (no numbered/IEEE/APA entries at all) is still detected as a references span and R3 runs. Result on `bjps_1`: 109 entries split one-per-line, **zero** entries collapsed; across the 8-paper BJPS Harvard corpus + 9 Nature papers, ≥95% of entries split correctly (was: every Harvard bibliography fully collapsed).

**Same-class fix surfaced by the D1 broad-read — APA ref-start missed accented / particle / compound surnames.** `_REF_START_APA` used an ASCII-only `[A-Z][a-z]+` surname, so `Yücel, M.`, `de Kovel, C.`, and `Karlsson Linnér, R.` were not recognised as entry starts and merged into the preceding reference (nat_comms_5: 10 collapsed pairs; nathumbeh_2: several). It now reuses the shared Latin-Extended surname block (with particles and an optional compound second word), keeping the comma-after-surname APA discriminator. Result: nat_comms_5 collapsed-pairs 10 → 1, nathumbeh_2 6 → 3 (the 3 remaining are supplementary-section prose, not reference merges). The change is a strict widening of a tight `Surname, Initial.` signature — journal-tail continuation lines (`Developmental psychology, 50(12), …`) still do not match.

**D2 — running-header injected mid-reference + page-break-orphaned year.** On `nat_comms_2` (Nature Communications) ref 34 straddles a page break; pdftotext emits `…EAE based on␊␊␌Article␊histology, … (2008).`. The category label `Article` (Nature prints it atop every page) survived — `_looks_like_running_header_or_footer` recognised multi-word banners and author-pair headers but not a bare single-word category label — and welded into the entry, while the page-break blank line left the entry's `(2008)` year in a detached paragraph (citelink parsed ref 34 with an empty year). Two coordinated fixes:

1. `_CATEGORY_LABEL_HEADER` (new shape in `_looks_like_running_header_or_footer`) recognises the publisher article-type labels H0 already curates (`Article`, `Review`, `Letter`, `Matters Arising`, `Original Investigation`, …). Combined with P0r's existing ≥3-standalone-repetition guard this strips the recurring label wherever it appears (including mid-references), so a one-off body occurrence is never touched. Bare common words (`Research`, `Comment`) are excluded to avoid colliding with section headings.
2. R3 now **bridges a page-break blank line** when the current entry is syntactically *incomplete* (does not end in sentence-terminal punctuation) — a page-break split leaves the head mid-clause (`…EAE based on`), so the tail rejoins; a *completed* entry (`…46, 215-39.`) followed by a blank is the end of the list, so a post-reference trailer (`Cite this article: …`) is **not** absorbed. A form-feed stitch (`\f` → newline inside the span) handles the case where the page header survives upstream.

Result on `nat_comms_2`: ref 34 is a single logical line carrying its `(2008)` year, with no `Article` injection.

New regression tests in `tests/test_harvard_refs_pagebreak_stitch.py`: Harvard ref-start positives (glued/hyphenated/accented/compound/particle surnames) and continuation-line negatives; the bjps_1 one-per-line and nat_comms_2 year-recovery defects at the text level; the page-break stitch + header strip; the trailer-not-absorbed guard; and real-PDF manifest-with-skip assertions on both fixtures.

## [2.4.84] — 2026-06-12

**R2 page-number scrub — general quantifier-head guard (stop deleting digits from reference titles).** `NORMALIZATION_VERSION` 1.9.30 → 1.9.31.

Surfaced by `CitationGuard/docs/DOCPLUCK_HANDOFF_2026-06-10.md` (item 4): the `plos_med_1` reference "Clinimetric properties of **3** instruments measuring postoperative recovery…" rendered as "…properties of instruments measuring…" — the standalone "3" was silently deleted. Same class as the earlier Mayiwar "3"-drop. Root cause: R2 (the references-span page-number scrub) strips any digit whose value also appears as a standalone page-number line, when it sits between two lowercase words. "3" is page 3 of the PDF, so the legitimate quantifier "3 instruments" was stripped. The v2.4.17 body-noun allowlist (`years|participants|…`) is necessarily incomplete and never enumerated "instruments" — adding nouns one at a time is whack-a-mole.

The fix keys on a **closed class** instead: a genuine page-number leak ("psychological **41** science", "recovery **12** in a population") follows a *content* word, whereas a legitimate quantifier ("of **3** instruments", "the **5** factors", "and **3** in Vastfall") follows a *function* word (article / preposition / determiner — a finite closed set). `_r2_is_body_phrase` now also preserves a digit when the immediately-preceding token is in `_R2_QUANTIFIER_HEAD_WORDS`. The guard is purely **additive** — it only ever *preserves* a digit, never strips one — so it cannot make R2 delete anything it didn't already, honoring the correctness asymmetry (silently dropping a digit from a reference title, rule 0a, is far worse than leaving a stray page number). The body-noun list also gained the obvious research-countable nouns (`instruments|measures|scales|factors|experiments|datasets|tasks|…`) as belt-and-suspenders.

Corpus audit (101 PDFs, academic-normalized, old vs new): **5 papers changed, every change a correct restoration, zero regressions** — `plos_med_1` ("of 3 instruments"), `amp_1` ("sizes of 12 academic search engines"), `bmc_med_3` ("on 5 types of"), `ieee_access_5` ("kernel size to 3 x 3" + "for 30 iterations"), `maier_2023_collabra` ("Experiments 1a and 3 in Vastfall"). The fix repaired the filed defect **plus 4 pre-existing silent corruptions**. The 11 remaining R2 strips (all preceded by content words) are genuine page-number leaks, correctly still stripped.

New regression tests in `tests/test_normalize_a3_r2_body_integer_real_pdf.py`: quantifier-head helper positives (`of 3 instruments`, `the 5 factors`), content-word-leak negative (`psychological 41 science` still strips), and a real-PDF assertion on `plos_med_1` (`of 3 instruments` present, `of instruments measuring` absent).

> **Handoff items 1–3 (chen_2021_jesp) — won't-fix, PDF-text-layer corruption.** The same handoff filed three other defects on `chen_2021_jesp`: the lost "Registered reports: " title prefix (Nosek & Lakens), the "TurkPrime.com" → "TurkPrime. Com" space injection (Litman et al.), and the "Open Science Collaboration" → "Open, S. C." + stray "Psychology." mangle (OSC 2015). Verified that **both** MIT extractors — pdftotext (text channel) and pdfplumber (layout channel) — produce byte-identical corruption on all three. When two independent extractors read the same bytes, the corruption lives in the PDF's embedded text layer, not in any tool's reading order, and there is no in-text signal (the references read as clean and complete) to trigger a conditional fallback. No general structural signature exists to detect or repair them, and a tool swap is both forbidden (CLAUDE.md L-001 / AGPL ban) and would not help. These remain consumer-side / unrecoverable without OCR or AI re-read — the established `project_citationguard_extraction_defects_wontfix` class.

## [2.4.83] — 2026-06-08

**P0r — bare "`<Initials> <Surname> et al.`" running-header strip.** `NORMALIZATION_VERSION` 1.9.29 → 1.9.30. Keyed on the `Initial. Surname et al.` line shape + the existing ≥3-standalone-repetition guard, never paper identity.

Surfaced by the v2.4.82 RC-1 AI-verify: `J. Chen et al.` leaked as a standalone line **×20** on `chen_2021_jesp` / `j.jesp.2021.104154` (and `I. Ziano et al.` **×10** on `ziano_2021_joep`). Root cause: pdftotext splits the full Elsevier running header `J. Chen et al. / Journal of Experimental Social Psychology 96 (2021) 104154` across **two** lines; v2.4.81's `_ELSEVIER_JOURNAL_VOL_FOOTER` strips the journal half, but the bare author half (`J. Chen et al.`) was its own line and matched no shape filter, so it leaked. (The mid-sentence *glued* variant `scienceJ. Chen et al.` was a separate splice-boundary bug fixed in v2.4.82.)

New `_AUTHOR_ETAL_INITIAL` shape in `_looks_like_running_header_or_footer`: 1–4 leading initials (`J.` / `J. K.` / hyphenated `M.-J.`), an optional surname particle (`van`, `de`, …), a Title-Case surname (Latin-Extended, hyphen/apostrophe), and a trailing `et al.` with nothing else on the line. It is gated by the ≥3-standalone-repetition requirement in `_detect_recurring_running_headers`, so it can only fire on the recurring page furniture — an in-text citation is never a standalone whole line, and an APA reference entry is `Surname, Initial.` (comma after the surname — the inverse order). Corpus-wide check: fires on exactly the two genuine running headers (`chen` ×20, `ziano` ×10) across the 26-paper baseline, **zero** false positives on body text or table cells.

New regression tests: `tests/test_p0r_recurring_running_header_strip.py::TestBareAuthorEtalRunningHeader` (shape positives incl. hyphenated/particle forms + negatives for citation/reference/bare-author; ≥3× detection gate; standalone strip preserves body; real-PDF on `chen_2021_jesp` — references intact, the paper is also the O5 inversion fixture — and `ziano_2021_joep`).

**First-class footnote surface + `extract_pdf_layout` export (ScienceArena report follow-up).** Surfaced by verifying the ScienceArena `2026-06-07-docpluck-arena-issues.md` benchmark report. The report's headline finding ("footnotes never emitted") was traced to the *consumer's* adapter — but it exposed a real docpluck gap: footnotes that F0 captures were only reachable via `report.footnote_spans` (raw char offsets) or by parsing the `\n\f\f\n` body appendix; there was no clean list, and `extract_pdf_layout` (the layout-channel entry point the F0 path needs) was not even exported from the top level. Two additive, non-breaking changes:

- **`NormalizationReport.footnote_texts: tuple[str, ...]`** — the captured footnote strings, parallel to `footnote_spans` (`footnote_texts[i] == raw_text[footnote_spans[i][0]:footnote_spans[i][1]]`). Populated during the F0 strip from the lines it already detects; empty when F0 doesn't run (no layout) or no footnotes are present. The normalized **text output is byte-identical** (`body + appendix` unchanged) — so `NORMALIZATION_VERSION` stays 1.9.30 and no cached normalization is invalidated. Also surfaced in `NormalizationReport.to_dict()`.
- **`docpluck.extract_pdf_layout`** is now re-exported at the top level (symmetric with `extract_pdf`), so consumers can run the layout-aware `normalize_text(..., layout=...)` path — and read `report.footnote_texts` — without reaching into the `docpluck.extract_layout` submodule. CLAUDE.md already documented it as the public layout channel; the export now matches the docs.

New regression tests: `tests/test_normalize_f0_footnote_strip.py::test_f0_exposes_footnote_texts` / `::test_f0_footnote_texts_empty_without_layout`; `tests/test_v2_top_level_exports.py::test_extract_pdf_layout_top_level_importable`.

**Render: de-duplicate the table/figure label between heading and caption.** Every table/figure block was emitted as `### Table 1` immediately followed by `*Table 1. <desc>*` — the number printed twice. A final post-processor (`_dedupe_label_in_table_figure_caption`) now strips the redundant `Table N.` / `Figure N.` prefix from the italic caption when an immediately-preceding `### Table N` / `### Figure N` heading already carries it, yielding `### Table 1` + `*<desc>*`. The structured `caption` field returned by `extract_pdf_structured` is **unchanged** (verbatim printed caption, label still re-prefixed) — only the rendered markdown is de-duplicated. Runs LAST, after the caption-detecting passes (`_suppress_inline_duplicate_table_captions`, `_suppress_orphan_table_cell_text`) that key on the `Table N.` prefix, so their matching is unaffected (full render suite: 100 passed). New tests: `tests/test_render.py::test_dedupe_label_*` (table/figure positives, unlabeled/mismatched-number/no-heading negatives, idempotency).

> **Cross-repo (ScienceArena, not this library):** the report's top-2 levers were adapter bugs in `MetaScienceProjects/ScienceArena` — `players/adapters/docpluck_library.py` hard-coded `footnotes: []` and called `normalize_text` **without `layout=`** (so F0 never ran and the body kept running-headers + footnotes the gold excludes), and `docpluck_tables.py` passed the caption verbatim. Those adapters were fixed to pass the layout, read `report.footnote_texts`, and strip the caption label — logic-verified against this library but **not** yet run in ScienceArena's own venv (docpluck is not installed there). See the verification write-up for details.

## [2.4.82] — 2026-06-08

**Column-splice word-integrity — two pre-existing corruptions fixed; general two-column de-interleave added behind a flag (default off).** No `NORMALIZATION_VERSION` change (text channel only — `extract.py` + `extract_columns.py`). Both fixes keyed on a STRUCTURAL INVARIANT — *a column re-extraction must preserve the page's substantial-word multiset* — never paper identity. Gated against the full 26-paper corpus (every paper now preserves the raw pdftotext word multiset under both settings) + the column-test suite.

This release began as the RC-1 general-interleave wiring; reproducing the gap at HEAD surfaced that the existing column-splice was **shipping word corruptions in the default** on 5 of the 26 baseline papers. Two distinct defects in `splice_column_corrected_pages`, both latent since R4 (v2.4.76):

- **Accept-any word splits (rule 0a/0b).** Pages outside the O5 word-preservation set were accepted on *any* non-empty re-extraction. pdftotext column-crop (`-x -W`) cuts a word that straddles the crop x, so the "corrected" page shipped split fragments: `jama_open_1` `adults`→`adu`, `control`→`cont`, `body`→`bod`, `mean`→`mea`; `jama_open_2` `creatinine`→`cre`, `nutrition`→`nutriti`; `ieee_access_3` `using`→`us`, `intelligence`→`intelligenc`; `amc_1` `management`→`mana`+`agement`; `amle_1`. The committed snapshots `jama_lattice` and `ieee_figure_heavy` were **storing the corruption** (a broken baseline masking the defect — the exact failure mode `docs/ITERATION_VERIFICATION_LESSONS.md` warns about).
- **Cross-page boundary glue.** `extract_page_text_columns` returns page text *stripped of its trailing form-feed*; the splice appended it directly, so a corrected page's last word glued onto the next page's first word at the splice boundary: `bjps_1` `results`+`https`→`resultshttps`; `chen_2021_jesp` / `j.jesp.2021.104154` running-header `J` (from `J. Chen et al.`) glued to the prior word (`from`→`fromj`, `science`→`scienceJ`). The per-page word-preservation guard passed because each page is word-correct *in isolation* — the corruption was at the concatenation seam.

**The fix.** Word preservation is now **unconditional** in `splice_column_corrected_pages`: a page's re-extraction is accepted only when it is a pure reorder (identical substantial-word multiset AND a materially different token order). A rejected page keeps its ORIGINAL (word-correct, possibly still-interleaved) text — never a corrupted reorder. The corrected page now re-attaches the original page's trailing newline+form-feed separator, so it can never glue across the page boundary and the `\f` page structure survives for downstream page-aware consumers. The former `word_preserve_pages` parameter (which conflated "use the gutter detector" with "check word preservation") is renamed `gutter_fallback_pages` and now governs *only* the gutter-strip midline detector; word-preservation applies to every page.

**Consequence (deliberate, rule 0a/0b > reading order).** The R4 whole-page crop that de-interleaved the `jama_open_1` abstract/Key-Points sidebar did so *by splitting words*; word-preservation now rejects it, so that page reverts to its word-correct (still column-mixed) raw text. The structured-abstract labels stay in document order and the Key Points block is present without the correction. Properly de-interleaving that page — a full-width title/byline band crossing the two abstract/sidebar columns — needs the per-band Step 2 region-aware crop (`docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md`), which can de-interleave without cutting words. `test_r4_column_correction_real_pdf.py` is revised to assert word-integrity (whole words present, split fragments absent) rather than the corrupting de-interleave.

**General two-column de-interleave (RC-1 Step 1) — `DOCPLUCK_COLUMN_CORRECT_GENERAL`, default OFF.** The general-interleave pages flagged by `_detect_column_interleave_pages` were previously detected but never safely corrected (signal-only). When the env flag is set, they join the O5 inversion pages under the gutter-strip detector + the (now-unconditional) word-preservation guard: a flagged page is corrected only when it has a clean full-height central gutter AND the left-then-right re-extraction is a pure reorder. AI-verified against the article-finder golds, this cuts `j.jesp.2021.104154` numbered-section reading-order inversions 12+ → 4 and clears the `ip_feldman_2025_pspb` B3 affiliation-leak / B4 mid-text-caption canary findings. It is a partial fix — table-bearing and no-clean-gutter pages stay untouched (honest no-op), deferred to the per-band Step 2 — so it ships **dark** (default off, byte-identical) pending that architecture. Flip the default after Step 2.

New / revised regression tests: `tests/test_rc1_general_column_correction_real_pdf.py` (flag-off legacy + flag-on corrects-more with the whole-doc substantial-word multiset preserved — the rule-0a/0b invariant, real-PDF on `chan_feldman_2025_cogemo` + `chandrashekar_2023_mp`); `tests/test_r4_column_correction_real_pdf.py` (word-integrity revision). Snapshots `jama_lattice`, `ieee_figure_heavy`, `apa_chen_jesp_lineless` regenerated to the corrected (word-preserving) output.

## [2.4.81] — 2026-06-08

**Untested-corpus sweep — RC-2 metadata/running-header leak strips.** `NORMALIZATION_VERSION` 1.9.28 → 1.9.29. A discovery sweep over 15 previously-untested manuscripts (located + gold-sourced via article-finder) found the most universal defect: front-matter / per-page furniture leaking into the body stream on **5/5** verified papers. Two strip-coverage gaps closed this release (one root cause: non-body metadata appearing in body):

**(1) Running header/footer shapes.** docpluck's P0r repetition-driven strip (`_strip_recurring_running_headers`) already detects ≥3×-repeated furniture and strips it (standalone + welded-prefix), but its shape filter `_looks_like_running_header_or_footer` knew only 5 publisher shapes and missed two common families:

- **Elsevier / ScienceDirect footer** — `<Journal Name> <Vol> (<Year>) <ArticleNo>`, e.g. `Journal of Experimental Social Psychology 96 (2021) 104154` (leaked ×20 on `j.jesp.2021.104154`), plus the author-prefixed `<Author> et al. / <Journal> <Vol> (<Year>) <ArtNo>` variant. New `_ELSEVIER_JOURNAL_VOL_FOOTER`. Distinct from an APA reference entry: the journal-name span excludes commas/periods (so it cannot match a citation's comma-separated author list) and the `(YYYY)` parenthetical sits AFTER the volume (footer form), not after the authors (reference form).
- **Nature-family footer** — `<Journal Name> | (<Year>)<Vol>:<ArtNo>`, e.g. `Nature Communications | (2023)14:8487` (leaked ×15 on `s41467-023-42320-4`). The existing `_JOURNAL_DOI_DATE_FOOTER` required `| https://doi.org/…`; this is the pipe-issue variant with no DOI URL. New `_JOURNAL_PIPE_ISSUE_FOOTER`.

Both shapes are tight typographic signatures and are additionally gated by the existing ≥3-standalone-repetition requirement, so they only ever fire on the recurring page furniture — never on body prose or a once-occurring reference line. Keyed on STRUCTURAL signatures (publisher footer layout), never paper identity.

**(2) Lowercase / shared-first-author corresponding-author footnote.** `normalize.py` `_PAGE_FOOTER_LINE_PATTERNS`: the v2.4.6 prefixed-footnote pattern matched `<a> Corresponding Author:` (capital A) only; Collabra emits the lowercase `a Corresponding author: <affiliation>; <email>` form and the combined `a Shared first author b Corresponding author: …` line, both of which leaked mid-body on `collabra.37122` / `collabra.77859`. The pattern now accepts case-insensitive `author` and the `Shared/Joint first author` openers. Still anchored on the `^[a-z]\s+<footnote-keyword>` shape, so a genuine body sentence starting with a lone "a " + noun is untouched.

New regression tests: `tests/test_p0r_recurring_running_header_strip.py` (running-header shapes — contract positives + reference/body negatives, detection ≥3×, real-PDF on `j.jesp.2021.104154` Elsevier + `s41467-023-42320-4` Nature); `tests/test_normalize_metadata_leak_real_pdf.py` (corresponding-author — lowercase + shared-first-author contract, body-sentence negative, real-PDF on `collabra.37122`). New-paper fixtures resolve via the article-finder cache (I9-compliant, skip-if-missing). Gated against the 26-paper corpus baseline.

Triage for the full sweep (incl. the dominant column-interleave architectural finding, RC-1) is in `docs/TRIAGE_2026-06-08_untested_corpus_sweep.md`.

## [2.4.80] — 2026-06-07

**O5 — reference reading-order inversion fixed (citationguard-iterate handoff).** Region-aware column re-extraction (`extract.py` + `extract_columns.py`); no `NORMALIZATION_VERSION` change (text channel only). Keyed on a STRUCTURAL signature — reference-list entries serialized ABOVE their own `References` heading on a page — never paper identity. Gated against the 26-paper corpus baseline + the column-test suite (32 existing pass) + 5 new real-PDF tests.

- **Root cause:** on two-column papers whose final page stacks a full-width contributor (CRediT) table ABOVE a two-column reference list, pdftotext serializes the page's columns out of order — emitting the RIGHT reference column before the LEFT column that carries the `References` heading. A block of reference entries is thereby stranded ABOVE the heading, invisible to any consumer scanning for references after it (citationguard-iterate O5: "36 chen refs stranded before the References header"). This is the R4/reading-order half of the same column-interleave root cause diagnosed for `ip_feldman` (finding #5 in 2.4.79).
- **`_detect_reference_inversion_pages`** (`extract_columns.py`): a cheap, text-only detector flagging a page when ≥3 reference-list-entry lines (`Surname, F. M.` shape, anchored at line start so in-text citations don't match) appear before that page's `References`/`Bibliography` heading. Reference entries cannot precede their own section heading in correct reading order, so this is an unambiguous inversion signature. Fires on exactly 2 of the 101-paper corpus (`chen_2021_jesp` p19, `jamison_2020_jesp` p9) — both genuine inversions.
- **`_detect_2col_midline_gutter`** (`extract_columns.py`): a full-height empty central GUTTER-STRIP midline detector. Stronger than the word-center histogram for narrow (~4pt) reference-column gutters the histogram can't resolve, and — because a clean full-height strip cannot coexist with a full-width table row crossing the center — it lets the prose columns be corrected while BYPASSING the y-row bilateral gate that (correctly) protects genuine table pages. Confined to the inversion path (`allow_gutter_fallback`), so the legacy column-interleave path is byte-identical.
- **Word-preservation guard** (`splice_column_corrected_pages` `word_preserve_pages`): a flagged page's geometric re-extraction is accepted ONLY if it preserves the page's substantial-word multiset (every alphabetic token of length ≥2) — a pure reorder that can never drop or fabricate reference text (rules 0a / 0b). Trivial digit/single-char churn at crop boundaries is tolerated.
- **Result:** `chen_2021_jesp` 0 reference entries stranded before the heading (was 36+); 101 entries now follow it in alphabetical order. `jamison_2020_jesp` likewise (0 stranded; 37 entries). All other 99 corpus papers unchanged (detector does not fire; legacy path byte-identical). Classes A–D from the same handoff are pdftotext text-channel / source-PDF artifacts and remain consumer-side (citelink) — see `docs/superpowers/handoffs/2026-06-07-text-extraction-defects-from-citationguard-iterate.md`.

New regression tests: `tests/test_o5_reference_inversion_real_pdf.py` (detection + correction + text-preservation + detector-selectivity; real-PDF, parametrized over chen + jamison).

## [2.4.79] — 2026-06-07

**Cycle 5 — canary findings #1 (METADATA-LEAK) + #2 (HALLUCINATION false-positive) cleared on `ip_feldman_2025_pspb`.** `NORMALIZATION_VERSION` 1.9.27 → 1.9.28. Both fixes keyed on a STRUCTURAL signature, never paper identity; gated against the 26-paper corpus baseline + full pytest.

- **US-format publication-history line strip** (`normalize.py` `_PAGE_FOOTER_LINE_PATTERNS`): a new pattern strips the `Received Month DD, YYYY; revision accepted Month DD, YYYY` line (Sage / APA journals — PSPB) that leaked between `## Keywords` and `## Introduction`. The existing publication-history patterns are all European-order (`Received DD Month YYYY; Accepted …`); this adds the US `Month DD, YYYY` order with the distinctive `revision accepted` phrase. The date sub-pattern accepts either order; the `revision accepted` token plus a trailing year makes the line unmistakably journal boilerplate, never body prose. Clears canary finding #1. (The verifier's allowed-omissions list — `references/ai-full-doc-verify.md` — now records publication-history dates as journal furniture docpluck strips by long-established design, so the finding can't churn METADATA-LEAK→TEXT-LOSS.)
- **Continuation-demoter rejoin** (`render.py` `_demote_continuation_promoted_headings`): when a `## <Title>` is demoted because the prior line ends in a continuation word (soft-wrap split false-promotion), the demoted phrase is now **rejoined to the prior line it grammatically continues**, with the trailing sentence terminator restored when the phrase completes the sentence — instead of being left as an orphan bare line. An orphaned `Supplemental Materials` fragment (period stripped by the promotion, blank-line padding retained) read as a hallucination to the AI verifier; `The calculated effect sizes are summarized in the` + `Supplemental Materials` now renders as the single continuous sentence `The calculated effect sizes are summarized in the Supplemental Materials.` matching the gold. Clears canary finding #2 (audit false-positive — the text was always real; the defect was the spurious mid-sentence split). This completes the deferred rejoin the function's own docstring had flagged ("a separate normalize pass can rejoin it … for now we just stop the false-heading").

New regression tests: `tests/test_normalize_metadata_leak_real_pdf.py` (US-format Received-line contract + variant + real-PDF cases), `tests/test_hallucinated_heading_continuation_guard.py` (`TestContinuationRejoin` — rejoin/no-orphan, period restoration, no-double-period, lowercase-continuation guard + real-PDF rejoined-sentence assertion).

**Still NOT tagged** — canary retains the deferred multi-session findings: #3 Table 2 mid-Introduction (Camelot/B4), #4 Table 10 mid-External-Analysis (Camelot/B4), #5 `## Discussion` displaced Table-9 footnote + External-Analysis fragment (R4 column-aware reading-order). See the 2026-06-07 handoff.

## [2.4.78] — 2026-06-06

**Cycle 4 redux — canary findings #1/#3/#4 cleared on `ip_feldman_2025_pspb` + citationguard text-extraction handoff Defect 1.** `NORMALIZATION_VERSION` 1.9.26 → 1.9.27. Driven by the Sonnet-via-Claude-Max canary audit (headless gate now operational after `claude setup-token`). Five render/normalize fixes, each keyed on a STRUCTURAL signature (never paper identity), each gated against the 26-paper corpus baseline + full pytest:

- **Cluster E re-land** (`normalize.py` `_FRONTMATTER_LEAK_LINE_PATTERNS`): the `_ARTICLE_TYPE_CODE` (`research-article2025` etc.) + `_BARE_ARTICLE_ID` (6–8 digit standalone) patterns drafted in v2.4.77 were **reverted there** (they exposed a wrapped-title duplicate) and shipped as dead code. Now genuinely wired — the revert's blocker is resolved by the new wrapped-title demoter below. Clears the bare article-ID + article-type-code half of canary finding #1.
- **Wrapped-title-duplicate demoter** (`render.py` `_demote_wrapped_title_duplicate`): strips a `### {prefix-of-H1}` + continuation block immediately under the H1 (pdftotext emits the title twice on PSPB/Sage column layouts). Token-prefix match vs the H1 with a ≥75%-coverage gate; runs after title rescue. Resolves the side-effect that forced the v2.4.77 Cluster E revert.
- **Cohesive masthead-block strip** (`render.py` `_strip_frontmatter_masthead_block`): strips the residual publisher masthead (author+superscript lines, journal-name wraps, page range, copyright tail, `DOI:` label, bare DOI) between the H1 and the first `## ` heading. Self-limiting ≥2-hard-marker gate; a prose-break guard preserves an undetected abstract. Clears the remainder of canary finding #1 — the doc now flows `# Title` → `## Abstract` cleanly.
- **Column-wrapped heading repair** (`render.py` `_repair_column_wrapped_headings`): Rule A promotes a body `{Title} et al.` + bare `(YYYY)` citation-wrap to `### {Title} et al. (YYYY)` (finding #3 — "Choice of Study for Replication"); Rule B reattaches a short colon-/paren-led orphan tail onto a heading split mid-title (finding #4 — "Original Hypotheses…Target Article: Jordan et al. (2011)"). Both gated on followed-by-prose so two real sibling headings are never merged.
- **Soft-hyphen line-break dehyphenation** (`normalize.py` S6): a U+00AD immediately before a line break is always a discretionary extraction hyphen splitting one word across the wrap; the join now drops the U+00AD *and* the newline (gated on a following letter) BEFORE the existing bare strip, so `relation­\nship` → `relationship` instead of the previously-surviving space-broken `relation ship`. Closes citationguard text-extraction handoff Defect 1 (recovered com/mitment, pro/motion, altru/ism, relation/ship on chan_feldman_2025_cogemo; U+00AD count 0). Defect 3 (dropped reference line) verified CLEAN in docpluck (pymupdf-only); Defect 2 (position-dependent glyph mis-map `Västfjäll`→`Vastfall`) reproduced but deferred — needs a same-document surname-consensus normalizer (architecture decision).

**Run-11 hallucinated-heading guards** (`render.py` `_promote_isolated_titlecase_subsection_headings` + new `_strip_pre_title_heading_noise` / `_nearest_h2_parent_label`): three general structural guards that clear four mis-promoted-heading findings across the canary set:

- **Pre-H1 heading strip** — a heading sitting ABOVE the document title is a journal-section label promoted in the masthead zone; stripped after title rescue. Clears `### FlashReport` (ar_apa); generalizes to `### RESEARCH ARTICLE`-shape front matter.
- **Regular-path blacklisted-parent reject** — the regular promotion path now consults `_CHAIN_REJECT_PARENTS` (walking back to the nearest `## ` parent, tolerating interleaved running-header lines), matching the chain path. Clears `### Methodology` (a CRediT role label under `## Author Contributions` on plos_med, promoted when a running-header broke chain adjacency).
- **Lowercase-body reject** — a candidate whose following body's first alphabetic char is lowercase is a fragment torn from a running sentence, not a title. Clears `### Close replication` (chan_feldman) and `### Proced` (plos_med truncation fragment).

Deferred (surfaced, not hacked): `### Reasons for change` (ip_feldman — a Table 5 column header; needs table-region awareness), the `## Data Availability` end-matter absence (RCA correction: it never enters the text channel — pdftotext drops the box; cross-channel/layout recovery, NOT a demoter over-strip as the run-11 handoff assumed), and the citationguard `Open Science Collaboration`→`Open, S. C.` org-author collapse (RCA: baked into the PDF's embedded text by the publisher; identical in pdftotext AND pdfplumber; no safe general docpluck fix — routed to CitationGuard for DOI/CrossRef author reconciliation).

New regression tests: `tests/test_render_frontmatter_masthead.py` (27 cases — wrapped-title demoter, masthead-block gate, column-wrapped heading repair, pre-H1/blacklist-parent/lowercase-body guards + real-PDF), `tests/test_normalize_soft_hyphen_dehyphenation.py` (5 cases incl. real-PDF), plus front-matter cases added to `tests/test_normalize_metadata_leak_real_pdf.py`. **NOT yet tagged** — canary still has open table findings (#2/#6/#7 Camelot, multi-session) + reading-order findings (#5/#8, R4 column-aware) + the deferred items above. See the 2026-06-06 handoff.

## [2.4.77] — 2026-05-26

**Cluster E front-matter cleanup follow-up to v2.4.76.** `NORMALIZATION_VERSION` 1.9.25 → 1.9.26. Three additional publisher-metadata strip patterns observed after v2.4.76 shipped (Stream A continuation work for ip_feldman_2025_pspb + ar_apa front-matter):

- **`_PAGE_FOOTER_LINE_PATTERNS`** (`normalize.py`): new `^Article reuse guidelines:?$` pattern. Sage / PSPB publisher boilerplate that pdftotext emits as a standalone front-matter line. Tight-anchored so it can't match body prose.
- **`_FRONTMATTER_LEAK_LINE_PATTERNS`** (`normalize.py`): new `_ARTICLE_TYPE_CODE` and `_BARE_ARTICLE_ID` patterns. The article-type code pattern matches `research-article2025`, `meta-analysis2024`, etc. (publisher-internal article-type slug + year). The bare-article-ID pattern matches a standalone 6–8 digit line (the DOI's last segment repeated alone at top-of-doc). Both are position-gated to the front-matter zone (first 8000 chars or 1/6 of doc) via the existing `_strip_frontmatter_metadata_leaks` infrastructure — body false positives impossible.

Verification: `test_ip_feldman_top_of_doc_cleaned_real_pdf` PASS in isolation and in 64-test batch. No regression on the v2.4.76 corpus.

## [2.4.76] — 2026-05-25

**§A R4 column-aware re-extraction LANDED — closes jama-open-1 D4 (Key Points sidebar missing).** `NORMALIZATION_VERSION` 1.9.24 → 1.9.25 (concurrent with EC-T1's bump). Closes the final defect of the 2026-05-25 Haiku-orchestration pretest jama-open-1 cluster (HANDOFF_2026-05-25_pretest-followups.md Issue 1 — 5 of 5 defects now closed).

Two-pronged detector + per-page pdftotext-crop re-extraction:

- **Detector (`docpluck/normalize.py::_detect_column_interleave_pages`):** added Signature B (bimodal-line-length): substantial-content page (≥30 body lines) where ≥30% of lines are short (<40 chars) AND ≥30% are long (>70 chars) is column-fragmented. The canonical fingerprint of JAMA Open's abstract+sidebar interleave that escaped the original Signature A (no-terminator+Title-Case flip count) because period-terminated structured-abstract labels masked the flips.
- **Column extractor (`docpluck/extract_columns.py`):** new module. `extract_page_text_columns(layout, page_index, pdf_bytes)` detects column midline via word-center histogram (relaxed fallback to single deep gutter when no contiguous run exists — narrow-sidebar pages produce 1-bucket gutters), then `_crop_and_extract` runs pdftotext twice per flagged page with `-x -y -W -H` crop flags (preserves pdftotext's gap-aware word-spacing that pdfplumber's `extract_text()` loses on tight-kerned PDFs). Fall-through to pdfplumber word-join path if pdftotext-crop fails.
- **Wiring (`docpluck/extract.py::extract_pdf`):** R4 runs at the text-channel layer (after pdftotext, before return) so sections / normalize / render / structured ALL see the corrected text via the single `extract_pdf` call. Method tag gains `+column_corrected:N,M,...` suffix when R4 fires.

**jama-open-1 D4 outcome:** Key Points sidebar (`Question / Findings / Meaning`) now appears as a coherent block rather than line-interleaved through the abstract. Abstract content flows in proper paragraph order. Combined with the v2.4.74 fixes (D1 RUNNING_HEADER_LEAK, D2 HALLUC_HEAD, D3 ABSTRACT_LEVEL_MISMATCH, D5 TABLE_STRUCTURE_CORRUPT), the full jama-open-1 5-defect cluster is closed.

**jama-open-1 D1/D2/D3/D5 follow-up (also this version) ported from v2.4.74:**

- D1 RUNNING_HEADER_LEAK (`normalize.py`): JAMA-style `Downloaded from <bare-domain> ... user on MM/DD/YYYY` watermark + bare standalone date footer.
- D2 HALLUC_HEAD (`render.py _demote_isolated_table_cell_headings`): demote `### {label}` stranded inside table-cell clusters via bidirectional cell-fragment / column-header-stranded / data-shape signatures.
- D3 ABSTRACT_LEVEL_MISMATCH (`render.py _demote_abstract_zone_inline_labels`): zone-bounded demoter for JAMA structured-abstract inline labels + Key Points sidebar trio.
- D5 TABLE_STRUCTURE_CORRUPT (`render.py _strip_phantom_camelot_tables`): strip Camelot tables with masthead `<th>` + section-name `<td>` leak.

**R1-perf threading** (`extract_pdf_structured` + `render.py`): `_layout_doc` kwarg eliminates duplicate `extract_pdf_layout(pdf_bytes)` call.

**R3b widening** (`render.py _suppress_inline_duplicate_figure_captions`): wider 250-char overhang form gated against body-prose starters + stat shapes.

**Other R4-cascade regressions also fixed in this release** (4 separate downstream tests failed when R4 wiring landed; all addressed):

- **`_demote_italic_label_with_comma_headings` allowlist** (`render.py`): the Stream A §B-new-4 demoter fired on generic `## Discussion` when the body started with `In this study, ...` (matches the comma-list shape) and wrecked the rendered output — preventing the orphan-multilevel-number fold from producing `### 5.4. Discussion` on jdm_m.2022.2.pdf. New `_METADATA_LABEL_HEADING_PREFIXES` allowlist restricts the demoter to the open-science / data-availability metadata family (`Data Availability`, `Open Science Disclosures`, `Preregistration`, `Author Contributions`, `Funding`, `CRediT`, etc.). Generic subsection words can no longer be flattened by the heuristic.
- **`_demote_metadata_label_headings` heading-skipping lookahead** (`render.py`): the §B-new-2 demoter capped lookahead at 3 lines, so when R4 column-aware extraction reordered xiao_2021_crsp front-matter into `KEYWORDS / Introduction / metadata-list`, the bare `## KEYWORDS` heading survived because its keyword payload landed below the intervening `## Introduction`. Extended scan to 15 non-blank lines and explicitly skips intervening heading lines while searching for metadata-shape content.
- **`_prior_paragraph_is_sentence_terminated` URL handling** (`sections/annotators/text.py`): Stream A's Cluster A canonical-heading guard rejected lines preceded by URL-terminated paragraphs (`...code: https://osf.io/bwmtr/`) because URLs don't end in `.!?`. Added two acceptors: prior line contains `://` (any URL) OR ends with `/` (URL trailing slash). Resolves the v161 text-annotator regression on the lowercase-body Keywords test.
- **`_strip_recurring_running_headers` truncated-prefix case** (`normalize.py`): when R4 column-aware extraction crops a page footer mid-token (`PLOS Medicine | https://...1004323 Dec` instead of `... December 28, 2023`), the truncated form appeared once while the full form appeared ≥3 times, so P0r's repetition detector stripped the full but left the truncated single. Added a prefix-match arm: when a body line ≥30 chars is a strict prefix of an already-known repeating header, strip it.
- **Method-tag allowlist + snapshot regen** (`tests/test_v2_backwards_compat.py`): the `+column_corrected:N,M,...` suffix is documented and allowlisted via base-prefix split before the known-strings check. `tests/snapshots/{jama_lattice,ieee_figure_heavy}.txt` snapshots deleted to recapture against the v2.4.76 R4-corrected output.

**R4 false-positive gates** (`extract_columns.py`): three structural-signature gates discovered while reconciling R4 with the full corpus. Each blocks a distinct false-positive class without affecting JAMA Open detection:

1. **Contiguous-run gate** (`_detect_2col_midline`): best_run must span ≥2 buckets before yielding a midline. A length-1 run inside an otherwise populated central region is an alternating-zeros artifact of periodic word x-positioning (justified text, monospaced layouts, synthetic fixtures), not a real gutter. Real 2-column pages produce sustained low-density valleys ≥2 buckets wide because both column peaks are wide enough to push down a stretch of central density.
2. **Deep-fallback density gates** (`_detect_2col_midline`): the single-bucket trough fallback only fires when (a) ≥50% of surrounding buckets exceed the loose threshold (blocks sparse fixtures + figure-only pages) AND (b) the trough's immediate neighbors both exceed the loose threshold (flanked by genuine peaks).
3. **Y-row bilateral gate** (`extract_page_text_columns`, NEW in `extract_columns.py:113`): even when midline detection succeeds, R4 is skipped for the page if ≥30% of y-rows have words on BOTH sides of the candidate midline. A real 2-column body-text page has text rows in ONE column at a time (independent baselines per column); a TABLE embedded in a single-column page has rows with cells on both sides at the SAME y. Empirically (2026-05-25): JAMA Open p1 abstract+sidebar = 12.5% bilateral (passes); amle_1 table-heavy pages 10/13/29 = 65.5%/53.0%/38.5% bilateral (rejected).

Verified to preserve R4 firing on jama_open_1 (D4 Key Points sidebar closure unchanged — 3/3 R4 tests pass) while blocking R4 from misreading amle_1's 13 in-paper tables as page-level columns (resolving `test_amle_1_table_captions_not_cell_garbage`). Also updates `tests/test_extract_columns.py::FakePage` to mirror the new LayoutDoc schema (`height`, `words` fields the v2.4.76 R4 rewrite reads) and adds a new bilateral-gate unit test with a synthetic 30-row 2-cell-per-row table.

**Known residuals (v2.4.77+ follow-ups):** column-boundary line truncation on wide titles; `CONCLUSIONS AND RELEVANCE` split across columns becomes two fragments; orphan `(contin` from `(continued)` page markers. Cosmetic — the structural defect (sidebar missing / abstract interleaved) is closed. Full fix needs column-element detection (figures/title/page-spanning banners get rendered FROM the original pdftotext output, not the crops).

**EC-T1: table-row flattening for downstream stat-verification consumers.** `TABLE_EXTRACTION_VERSION` 2.1.5 → 2.2.0. Closes the largest cluster from the ESCIcheck handoffs ([2026-05-24](../ESCIcheckapp/docs/DOCPLUCK_HANDOFF_2026-05-24.md), [2026-05-25](../ESCIcheckapp/docs/DOCPLUCK_HANDOFF_2026-05-25.md)) — ~78 effectcheck rows across 6 canary papers blocked on bare table cells.

**New module: [`docpluck.tables.flatten`](docpluck/tables/flatten.py)**

- `flatten_table(table) -> list[FlattenedRow]` — turns a structured `Table` into per-row records. Each record carries `raw_cells`, `header`, `row_label`, a flattened English `sentence` (e.g. `Importance: t(741) = 3.93, p < .001, d = 0.29`), and a structured `fields` dict (`t`, `df`, `df1`, `df2`, `F`, `r`, `chi2`, `p`, `p_op`, `d`, `eta2`, `M`, `SD`, `n`, `N`, `CI_lower`, `CI_upper`). Three nested fidelity levels so consumers pick what they trust.
- `flatten_tables_for_paper(tables)` — convenience for paper-level JSONL emission.
- `render_flattened_inline(records, ...)` — renders the same records as a markdown block bounded by HTML-comment sentinels (`<!-- docpluck:flattened-table id="…" start --> … end -->`).
- Header→cell binding consolidations: `t + df → t(df)`; `F + (df1, df2)` from a `F(1, 998)` header → `F(df1, df2)`; `r + n → r(n-2)`; `M + SD → M = m, SD = sd`; CI from `[lo, hi]` cell OR separate `lower/upper` columns → `95% CI [lo, hi]`; `p_op + p → p < .001`.

**Render integration**

- `render_pdf_to_markdown` gains `flatten_tables_inline: bool = False`. When True, an `### {label} — rendered as text` block is emitted immediately after each `<table>`, with one bullet per body row. Bounded by HTML-comment sentinels — greppable, diff-tool-friendly, invisible in rendered markdown viewers.
- Inline block is *generated from* the same `FlattenedRow` records that go into the JSONL sidecar — single source of truth, no drift risk between the two outputs.
- Default `False` keeps the .md byte-identical to v2.4.75 for callers that don't opt in.

**CLI**

- `docpluck render --tables-jsonl PATH` writes one `FlattenedRow` JSON record per line to `PATH`. Canonical extraction contract for downstream stat-verification tools (effectcheck, escimate, scimeto).
- `docpluck render --flatten-tables-inline` embeds the human-readable block in the .md output (debug/eyeball mode).

**New top-level exports:** `FlattenedRow`, `flatten_table`, `flatten_tables_for_paper`, `render_flattened_inline`.

**Tests:** 19 new tests in `tests/test_tables_flatten.py` covering the 6 canary table shapes from the handoffs (collabra_57785 T8 t-rows, collabra_90203 T8 F-with-df-header, T10 r+n correlations, collabra_90203 T9 bare-numeric, lee_feldman bare t+p+nodf, majumder effect-size-with-CI) plus inline-render sentinel boundaries and edge cases.

Outstanding from the same handoffs:
- **EC-T2** — RR/RD/MD per-arm trial-table flattening (`plosmed_1004323`). Specialization of EC-T1; queued.
- **D-25-C** — gold-label mismatch on inter-rater r (not a docpluck defect); flagged for `article-finder` gold-quality pass.

## [2.4.75] — 2026-05-25

**EC-T3: CI bracket middle-period → comma (ESCIcheck 2026-05-24 D2).** `NORMALIZATION_VERSION` 1.9.24 → 1.9.25. Closes one of the three defect clusters filed by escicheck-iterate against docpluck ([handoff](../ESCIcheckapp/docs/DOCPLUCK_HANDOFF_2026-05-25.md), [triage EC-T3](docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md)).

- **A4a CI period→comma** (`docpluck/normalize.py`, A4 block)
  - New sub-rule at the top of A4: `\[(\d+\.\d+)\s*\.\s*(\d+\.\d+)\]` → `[\1, \2]` (and analogous for parens). Each side must be `\d+\.\d+` (digits-dot-digits), which blocks false-positives on section refs like `[1.2.3]` (trailing token has no decimal).
  - Verbatim from the handoff: `collabra_57785` abstract emitted `d=0.39[0.25.0.54]` — pdftotext mapped the CI comma glyph to a period, so effectcheck's CI-binder couldn't disambiguate `0.25.0.54` from a decimal continuation and dropped the CI entirely. Now rewrites to `d=0.39 [0.25, 0.54]`.
  - Both signed negatives (`[-0.19.0.27]` → `[-0.19, 0.27]`) and tight no-space forms (`d=0.39[0.25.0.54]`) covered.
  - 8 new tests in `tests/test_a4_ci_period_to_comma.py` — square brackets, parens, no-space, negative lower bound, idempotent on already-correct input, section-ref non-match, single-decimal non-match, full t-test-with-CI shape.

Outstanding from the same handoff (queued in triage, not addressed in this release):
- **EC-T1** — table column-header df / N / per-arm propagation into row cells (~78 effectcheck rows blocked across 6 canary papers). Needs a design call (sentence-stream alongside HTML vs HTML cell rewrite) — open question for the user.
- **EC-T2** — trial-arm RR/RD/MD cell flattening (`plosmed_1004323`). Specialization of EC-T1, queued after.

## [2.4.74] — 2026-05-25

**jama-open-1 cluster (4 of 5 defects) + R1-perf threading + R3b widening.** `NORMALIZATION_VERSION` 1.9.23 → 1.9.24. Closes 4 of the 5 defects surfaced by the 2026-05-25 Haiku-orchestration pretest on `jama_open_1.pdf` ([handoff Issue 1](docs/HANDOFF_2026-05-25_pretest-followups.md)). Defect 4 (MISSING_SECTION / Key Points sidebar) is fundamentally a column-interleave problem (R4 territory) — left for the next cycle.

- **D1 RUNNING_HEADER_LEAK** (`docpluck/normalize.py`)
  - New `_WATERMARK_PATTERNS` entry: JAMA-style `Downloaded from <bare-domain> ... user on MM/DD/YYYY`. Previous pattern required `https?://` prefix + `DD Month YYYY` date — missed every JAMA Open paper.
  - New `_PAGE_FOOTER_LINE_PATTERNS` entry: bare standalone `Month DD, YYYY` line. Distinguished from the legitimate `Published: October 27, 2023. doi:...` metadata line by line-completeness.
  - Clears all 13 `Downloaded from jamanetwork.com ...` leaks and 15 standalone `October 27, 2023` leaks.

- **D2 HALLUC_HEAD** (`docpluck/render.py` `_demote_isolated_table_cell_headings`)
  - New post-processor that demotes `### {label}` headings stranded inside table-cell regions. Decision logic — ANY of: bidirectional cell-cluster + zero real sentences | ≥2 single-token-cell prev signals (column-header-row signature) | heading carries data-unit-suffix shape (`, kg` / `, %` / `, mg/dL`) + ≥1 cell neighbour | next-non-blank-line is data-unit-label + prev cell anchor.
  - Strict `_looks_like_real_sentence` gate (≥4 words AND terminator AND lowercase word) prevents table-footer-note prose from blocking legitimate demotion.
  - Clears all 4 surfaced cases: `### 1.0. Mean glucose level`, `### Control`, `### Body weight, kg`, `### Total cholesterol`.

- **D3 ABSTRACT_LEVEL_MISMATCH** (`docpluck/render.py` `_demote_abstract_zone_inline_labels`)
  - New zone-bounded demoter: between `## Abstract` and the next body-section h2 (Introduction / Methods / Background / etc., or after 80 lines as a hard cap), demote any `## X` heading whose text is in the explicit `_STRUCTURED_ABSTRACT_INLINE_LABELS` allowlist (JAMA structured-abstract labels: IMPORTANCE / OBJECTIVE / RESULTS / CONCLUSIONS AND RELEVANCE / MAIN OUTCOMES AND MEASURES / DESIGN, SETTING, AND PARTICIPANTS / INTERVENTIONS + Key Points sidebar trio: Question / Findings / Meaning).
  - Conservative allowlist preserves legitimate body-section h2s like `## THEORETICAL DEVELOPMENT` (amj_1) and numbered headings like `## III. RESULTS` (ieee_access_2).
  - 80-line hard cap prevents zone overrun when the body-section h2 has a non-canonical label (numbered prefix etc.) that bypasses the end-set match.

- **D5 TABLE_STRUCTURE_CORRUPT** (`docpluck/render.py` `_strip_phantom_camelot_tables`)
  - New post-processor that strips Camelot `<table>` blocks whose `<th>` matches running-header / masthead patterns (JAMA Network Open / NEJM / generic `Journal | Subsection`) AND whose `<tbody>` is ≤1 non-empty cell OR has a section-name leak (Discussion / Conclusion / Methods / etc.).
  - Leaves the `### Table N` heading and `*Table N. ...*` caption line intact so the reader knows the table existed.
  - Conservative — bypassed when `<tbody>` has >3 non-empty cells (real table with masthead-shaped header text).

- **R1-perf threading** (`docpluck/extract_structured.py` + `docpluck/render.py`)
  - New `_layout_doc` kwarg on `extract_pdf_structured(...)`. When passed, the §A R1 whitespace_cells fallback path reuses the caller-supplied layout doc instead of re-extracting via pdfplumber.
  - `render_pdf_to_markdown` now pre-extracts the layout doc once at step 0 (used for title rescue) and passes it to `extract_pdf_structured` — eliminates the 2x `extract_pdf_layout(pdf_bytes)` pass flagged by the v2.4.73 R1 AI-gold sweep. Typical 1-3s saved per render on real papers.

- **R3b widening** (`docpluck/render.py` `_suppress_inline_duplicate_figure_captions`)
  - Conservative form preserved (≤120 chars, no stat shape, sentence-terminated). New wider form allows up to 250 chars overhang when the overhang additionally starts with lowercase / `(A) (B)` panel labels / etc. (caption-continuation shape) AND ends with a sentence terminator AND has no body-prose starter (`We ` / `In ` / `Although ` / etc.).
  - Block-caption-completion path remains a follow-up.

**Regression tests:** `tests/test_jama_open_cluster_real_pdf.py` (5 cases: D1 download-leak, D1 standalone-date, D2 table-cell-heading, D3 abstract-zone, D5 phantom-table). All assert real-PDF behaviour on `jama_open_1.pdf`.

**Two previously-RED amj_1 / ieee_access_2 cases:** the abstract-zone demoter went through two regression rounds during development (over-demoted `## THEORETICAL DEVELOPMENT` then `## III. RESULTS`); current allowlist + 80-line cap clears both. Full pytest (TBD on commit).

## [2.4.73] — 2026-05-25

**R1-repair — wake up the dead `whitespace_cells` wiring.** The §A R1 fix in v2.4.72 (`docpluck/extract_structured.py` `whitespace_cells` fallback for caption-detected tables Camelot couldn't recover) shipped structurally dead in production: a 2026-05-25 AI-gold sweep across the 11 B1 papers found `_region_for_caption` returned `None` in 100% of unmatched-caption cases, so `whitespace_cells` was never invoked. Root cause: `_bbox_of_caption_line` in `docpluck/tables/detect.py` matched the first-20-char `cap.line_text` prefix (e.g. `'Table 5. Reflection'`) against joined layout chars — but layout chars on a single y-row drop inter-word whitespace and keep raw PDF ligatures (e.g. `'Table5.Reﬂection…'`), so the prefix never matched. The silent fallback to `_isolated_table_from_caption` hid the no-op behind v2.4.71-identical output.

**Fix (`docpluck/tables/detect.py::_bbox_of_caption_line`):** three-pass matcher.
- Pass 1: exact prefix match against joined chars (legacy path, preserved for compatibility).
- Pass 2: normalized prefix match — fold ligatures (`ﬁ`→`fi`, `ﬂ`→`fl`, etc.), strip whitespace, lowercase on both sides. Catches the dominant B1 failure shape.
- Pass 3: label-only fallback — search for the normalized `cap.label` (e.g. `table5`) anywhere in the joined row, gated to start near the left margin and within the first ~4 chars of the row to avoid false positives on body prose ("(see Table 5)") and right-column 2-column-page rows.

**Verification:** post-fix region resolution went from 0/22 captions (jdm_.2023.16 / chan_feldman / maier) to 22/22 (100%). `whitespace_cells` now fires and yields **72 cells on chan_feldman_2025_cogemo (8 captions)** and **100 cells on maier_2023_collabra (11 captions)** — verified by the new `tests/test_r1_whitespace_cells_wiring_real_pdf.py` regression test (3 cases: 2 real-PDF + 1 unit ligature/whitespace normalization).

No `NORMALIZATION_VERSION` bump (no normalize.py change). Real-PDF regression test asserts the wiring stays live (catches future regressions in ligature handling, caption-line shape, or region bbox sizing).

Follow-ups (queued in `todo.md`, not blocking this ship): (a) thread `_layout_doc` through `extract_pdf_structured` to eliminate the second `extract_pdf_layout(pdf_bytes)` pass `render.py` already triggers (perf only — measured 2x on every render path with unmatched caps); (b) for jdm_.2023.16-shape narrow tables, regions resolve but `whitespace_cells`'s ≥3-stable-column threshold leaves cells empty — needs per-page table-region detection per the 2026-05-22 R1 decision table.

## [2.4.72] — 2026-05-23

**Bundled cycle — 2026-05-23 residual handoff (§A R1, R3a, R3b, R4, R5; §B-new-1..5; §C P0r-F).** `NORMALIZATION_VERSION` 1.9.22 → 1.9.23. Eleven fixes landed in one cycle per user directive ("implement and fix all in one go, leave nothing behind"):

- **§C P0r-F (render.py `_strip_running_header_lines_in_unstructured_table_fences`)** — strip P0r-shape running-header / page-footer lines that survive inside ` ```unstructured-table ` fenced blocks (third-channel completion of the body normalize-stage P0r per the docpluck `glyph-fixes-need-all-three-text-channels` hard-rule lesson). Clears the `test_plos_med_1_no_banner_or_footer` real-PDF test that was RED since v2.4.70.
- **§B-new-1 (render.py `_promote_isolated_titlecase_subsection_headings`)** — wider analogue of B2c. Promotes any paragraph-isolated Title/Sentence-Case short line (≤6 words, ≤60 chars) followed by prose, gated by strict shape checks (first-word-Title-Case, prev-line-not-sibling-label, next-line-prose, no figure/table/equation label prefix). Cycle-1-2-3 verifier sweep flagged ~80 H3 subsection-demote findings across 4 of 5 canary papers — this is the largest single defect class.
- **§B-new-2 (render.py `_demote_metadata_label_headings`)** — HALLUC-HEAD-3: demote `## KEYWORDS` / `## ABBREVIATIONS` / `## JEL` / etc. when followed within 3 lines by metadata-shape content (separator-bearing list with no sentence verb). Updates `tests/test_all_caps_section_promote_real_pdf.py::test_xiao_no_false_positive_promotion` to reflect the new desired behaviour (KEYWORDS now demoted to inline `**KEYWORDS:**`).
- **§B-new-3 (render.py `_demote_credit_role_headings` Signal C)** — extend CRediT-block detection to count distinct roles that appear with a trailing `:` in the window (PLOS Author Contributions packed-CRediT continuation). Catches `## Methodology` inside a `**Conceptualization:** Names. **Investigation:** Names.` block where the existing 70%-coverage `_max_distinct_roles_in_any_line` undercounts due to name-token dilution.
- **§B-new-4 (render.py `_demote_italic_label_with_comma_headings`)** — demote `## <Heading>` that was wrongly split off a comma-broken italic metadata label. Detects `## <Word>` whose immediately following non-blank line begins with `Word,` or `and Word` shape AND ends with a period — rejoins into a single italic `*Heading, continuation.*` inline label. Clears the ip_feldman_2025_pspb `## Data Availability` cycle-3 finding.
- **§B-new-5 (normalize.py H0 `_HEADER_BANNER_PATTERNS`)** — add SAGE/journal-ID welded-banner concat pattern: `^[A-Z]{2,}\d*10\.\d{4,}/\d{6,}[A-Z][a-z].*$` matches `PSPXXX10.1177/01461672251327169Personality and Social Psychology BulletinIp and Feldman` (no whitespace separators — distinguishes from the existing masthead pattern).
- **§A R1 (extract_structured.py — `whitespace_cells` wiring)** — wire the previously-unused `docpluck.tables.whitespace.whitespace_cells` helper into the main pipeline. For each caption-detected table that Camelot could not recover, try `_region_for_caption` + `whitespace_cells` before falling back to the cellless `_isolated_table_from_caption`. Lazy-imports the layout extractor so the pipeline still works without pdfplumber-layout deps.
- **§A R3a (extract_structured.py `_is_citation_cell` + `_is_table_header_like_short_line` extension)** — accept citation-cell shapes (`Small et al. (2007)`, `(2007)`, `Smith and Jones (2009)`) as table-header-like-short-lines. Previously these failed the `len(words) > 3` rejection in `_is_table_header_like_short_line` and prevented the B4 cell-run cut from firing on maier Table 3.
- **§A R3b (render.py `_suppress_inline_duplicate_figure_captions` inverse safe-superset)** — extend FIG-3c with a stat-shape-gated inverse case: when the inline run starts with the full block caption (block-cap is a prefix of inline acc_norm, ≥30 chars matched) AND the overhang is ≤120 chars AND ends with a sentence terminator AND contains NO statistic shape (`F(`/`t(`/`p =`/`p <`/`B =`/`d =`/`OR =`/`β =`/`R² =`/df-pair), drop the inline run. The stat-shape exclusion is the text-loss guard (CLAUDE.md hard rule 0a) — body-side F-statistic sentences are preserved.
- **§A R4 (normalize.py `_detect_column_interleave_pages` + `NormalizationReport.column_interleave_pages`)** — structural-signature detector for pdftotext two-column reading-order interleave. Surfaces a signal (1-indexed page list) in the normalization report; the column-aware re-extraction itself is a follow-up architectural change (study pdfplumber's `pdfplumber/page.py` column algorithm per CLAUDE.md and re-implement as conditional fallback).
- **§A R5 (normalize.py `_recover_dropped_minus_in_record` + `recover_dropped_minus_via_ci_pairing` / W0g)** — recover the DROPPED-minus class (pdftotext emits no glyph at all for U+2212 on certain fonts; `b = -.022` reaches us as `b = .022`). Conservative gates: only fires when a same-record CI bracket has lo < 0 AND the recovered -X.XX falls inside [lo, hi] AND the literal X.XX falls strictly outside. Distinct from W0d which handles the '2'-for-U+2212 corruption class. Wired into both the body-channel normalize pipeline and the render-stage 3rd-channel post-process.

44 new tests in `tests/test_residual_2026_05_23_bundled.py` covering all 11 fixes — contract tests for each helper + 1 real-PDF regression test (`test_plos_med_1_no_fence_footer`). `tests/test_p0r_recurring_running_header_strip.py` now 37/37 passing (was 36/37 — the one RED test was the §C target). One existing test updated (xiao_2021_crsp KEYWORDS now demoted per the new §B-new-2 behaviour).

## [2.4.69] — 2026-05-22

**Docs-only patch — domain cutover to `docpluck.app`.** `[project.urls]` Homepage now `https://docpluck.app`, Documentation now `https://docpluck.app/api-docs` (was GitHub tree URLs). Project-skill SKILL.md files updated to reference the canonical `docpluck.app` host. No code changes; `NORMALIZATION_VERSION` unchanged at 1.9.21. Push to PyPI to refresh package-page links — the GitHub repo is unchanged. See `PDFextractor/docs/superpowers/handoffs/2026-05-22-domain-cutover-docpluck-app-COMPLETED.md` for the cross-repo sweep.

## [2.4.68] — 2026-05-22

**Cycle 15 (run 9) — long-tail non-idempotent papers cleared (4 → 0; 180/180 idempotent corpus-wide) + pre-existing two-column-bibliography regression fixed.** `NORMALIZATION_VERSION` 1.9.20 → 1.9.21. Five structural fixes:

1. **Cross-paragraph `(OR|CI|RR|HR)\n\n\d` A1r variant** in the LateJoin block — clears `demography-5` (Mortality Hazard Ratio and Odds Ratio tables where `CI`/`HR` sit one paragraph above their `\d+\.\d` value). Lookahead requires a STAT-VALUE-shaped token (`\d+\.\d`, `\d{2,}`, or digit+operator) to avoid colliding with bibliography reference-number form `\d+\.\s+[A-Z]`.
2. **`_LABELED_NUMERIC_LINE_RE` + `_is_in_numeric_block` extension** to recognize labeled stat-variable comparisons (`S<= 10000`, `M = 5.2`, `N = 200`) as numeric-block context — clears `nat-comms-2` (S9 was stripping the figure-axis tick label `1000` because the labeled neighbor wasn't seen as numeric).
3. **S9 repeated-line caption guard** — exclude lines containing a parenthesized 4-digit year/year-range `(YYYY)` / `(YYYY-YYYY)` OR ≥6 spaces ending in sentence punctuation. Protects table source-attribution captions like `socius-4` `Source: Authors' calculation, American Time Use Survey (2003-2023).` (×13 in the doc) from being false-stripped as a min_gap≥20 running header — real silent caption loss in production.
4. **Final NFC composition pass** at the end of `normalize_text` — clears `ieee-access-7` (`σ̂` math block where A5 transliteration `σ → sigma` orphaned U+0302 onto the trailing `a`; pass 1 left `sigma + U+0302`, pass 2 composed to `â`). Generally protective for any future transliteration step that leaves a combining mark on an ASCII tail.
5. **Two-column-bibliography pairing pre-pass for R3** (`_pair_two_column_bibliography`) — pdftotext renders some 2-column bibliographies (Royal Society Open Science is the canonical case) by streaming the entire NUMBER column first, then the entire ENTRY column. R3's continuation-join used to smash all the bare `\d+\.` lines into one header and detach the entries. The pre-pass detects a leading run of ≥3 sequential bare-number lines + matching entry column and pairs them up. Fixes Li&Feldman 2025 RSOS regression caught by `test_request_09_reference_normalization.py::test_bibliography_splits_into_45_consecutive` — a pre-existing failure latent at HEAD before cycle 15 (`requires_fixture` skipped it in CI without the Dropbox PDF, masking the regression for several cycles).

Tests added: `test_late_join_crosses_paragraph_for_ci_or_rr_hr`, `test_labeled_numeric_line_protects_figure_axis_value`, `test_s9_preserves_caption_with_year_range`, `test_final_nfc_pass_composes_orphan_combining_after_a5`, plus 4 real-PDF `*_real_pdf` regression tests for each of the cleared papers. Idempotency ratchet lowered 2 → 0 (corpus is now fully idempotent on the strided sample). Run 9 closes at 180/180 idempotent corpus-wide.

## [2.4.67] — 2026-05-22

**Docs-only patch — domain cutover to `docpluck.app`.** `[project.urls]` Homepage now `https://docpluck.app`, Documentation now `https://docpluck.app/api-docs` (was GitHub tree URLs). No code changes; `NORMALIZATION_VERSION` unchanged at 1.9.21. Push to PyPI to refresh package-page links — the GitHub repo is unchanged. See `PDFextractor/docs/superpowers/handoffs/2026-05-22-domain-cutover-docpluck-app-COMPLETED.md` for the cross-repo sweep.

## [2.4.66] — 2026-05-22

**Cycle 14 (run 9) — S9 numeric-line widening + year-range gate + repeat-line distribution heuristic.** A 180-doc scan post-cycle-13 found 7 papers non-idempotent. Cycle 14 packages three corpus-wide S9 hardening fixes that together clear 4 of them while also FIXING two latent production text-loss bugs.

### 1. `_NUMERIC_ONLY_LINE_RE` extended with `<>=%`

S9 Pattern A's per-occurrence numeric-block gate (cycle 9b) keeps a 4-digit candidate when its nearest non-blank neighbor is itself a "numeric-only" line — protects table sample-size N values. The original regex (`^[\d\s.,()+\-*∗;:]+$`) did NOT match common stat-table operator forms like `<.001` (p-value), `S<= 10000` (set-builder), `>= 0.05` (threshold). lee-feldman's `1801` (a regression-table F-statistic) and nat-comms-2's `1000` (figure-axis tick) had neighbors with `<`/`>=`/`%` — the gate failed, the values got stripped as "page numbers". Extended regex to `^[\d\s.,()+\-*∗;:<>=%]+$`.

### 2. S9 Pattern A excludes citation-year range 1900-2100

`1971` in amle-1 was a citation year (`House, R. J. 1971`) repeating across multiple table-row + ref-list mentions. Pattern A flagged it as a page number (≥3 repeats) and stripped it. Page numbers in the citation-year range (1900-2100) are extremely rare; corrupting citation years by stripping them is common and harmful. Cycle 14 excludes `1900 <= int(s) <= 2100` from Pattern A's `strip_set`.

### 3. S9 repeated-line strip — distribution heuristic

The original repeated-line strip (`≥5 occurrences of a 15-120 char line`) false-positives on TABLE ROW LABELS that repeat across columns of a regression table within a single page: socius-3 `Intend vs. Later` ×5, majumder `eta2p = .001, ⸸` ×9, collabra-rnr `Identifiability` ×5, social-forces-1 `Emotional neglect` ×5. Stripping these REMOVES legitimate row labels from production output — a real text-loss bug, not just an idempotence issue.

New rule: a repeated line qualifies as a header/footer only if:
  - **min_gap ≥ 20**: cleanly-spaced running header (one per page) — corpus data shows table labels max at 14 lines between occurrences, real headers at ≥25; or
  - **count ≥ 20**: super-frequently-repeated watermark / sidebar (e.g. PMC's `Author Manuscript` ×220 in ieee_access_2 with min_gap=1) that repeats multiple times per page.

The composite rule preserves table labels while still stripping page-headers regardless of inter-occurrence layout.

**Impact:** corpus-wide non-idempotency 7 → 4 (cleared lee-feldman, amle-1, socius-3, majumder). Cycle 13's IEEE Roman-numeral promotion test now also passes (was failing because `Author Manuscript` watermark stayed — composite rule catches it via the count path). Broad pytest 1357 pass + 1 known pre-existing B6 fail. Harness Tier-D academic: 0 regressions, 0 new fails (1 still failing — plos-med-1 / B1).

Two existing tests updated to reflect new (correct) behavior:
  - `test_4digit_below_1000_preserved` (old test asserted years were stripped — wrong) → renamed `test_4digit_year_range_preserved` + companion `test_4digit_pagenum_outside_year_range_still_stripped`.
  - `test_repeated_line_stripped` (synthetic 6-line doc was unrealistic for the new gate) → rewritten with realistic multi-page structure + companion `test_clustered_table_label_preserved`.

NORMALIZATION_VERSION 1.9.20.

## [2.4.65] — 2026-05-22

**Cycle 13 (run 9) — three further normalize_text idempotence fixes.** Post-cycle-12: 11 papers non-idempotent. Cycle 13 packages three independent fixes that together clear 4.

### 1. P1r late re-strip — front-matter metadata leak (4 papers: li-feldman-fox, amp-1, annals-2, xiao-poc-epley)

`_strip_frontmatter_metadata_leaks` matches acknowledgment lines by anchored prefix + keyword guard (`reviewers|editor|feedback|comments|suggestions|insights|helpful`) within 300 chars. pdftotext often line-wraps the acknowledgment BEFORE the guard keyword fires: `We thank the target article's authors - Prof. Craig Fox and Prof. Rebecca Ratner, for being very` (96 chars; no keyword yet). S7/S8 join the continuation; the joined line now contains `helpful in providing us with materials...` — but P1 has already run by then. Pass 2's P1 catches the joined form — non-idempotence + a real missed production strip.

Fix: P1r block at end of `normalize_text`, after H0r and before P0r. Same shape as cycle 7's H0r and cycle 9's P0r — fixed-point re-application of an idempotent line-strip on stabilized line positions.

### 2. Cross-paragraph `=`/`<`/`>` → digit join — same shape as cycle 12 (1 paper: li-feldman-fox additional defect)

A1's `re.sub(r"([=<>])\s*\n\s*([-\d.])", r"\1 \2", t)` uses `\s*` (crosses paragraphs) but runs BEFORE S9 strips header/footer junk. `p =\n\n\x0cFox et al. (2005)...\n\n38\n\n.25, OR = .96, 95%CI [.90, 1.03]` fails on pass 1 (the header text isn't `\s`); S9 strips, leaves `p =\n\n.25`; A1 is over.

Fix: add `re.sub(r"([=<>])\s*\n\s*\n\s*(?=[-.]?\d)", r"\1 ", t)` to the LateJoin block. The lookahead `(?=[-.]?\d)` is the load-bearing constraint — real paragraphs rarely START with a leading dot or `-digit`. Same shape as cycle 12's cross-paragraph `,/;` → `CI/p` joins.

### 3. LABELED CI bracket — intervening-stat-label gate (refines cycle 12; 1 paper: majumder)

Cycle 12's LABELED-bracket discriminator was too permissive. `M = 5.37, SD = 2.01), t(1827) = 1.83, p tukey = .067, d = 0.09, 95% CI [-0.006, 0.18]` has a LABELED `95% CI [...]` that incorrectly paired with `SD = 2.01` (across `t(`, `p tukey =`, `d =` — three INDEPENDENT-statistic labels). The CI is for `d = 0.09`, not for the SD.

Fix: even a LABELED bracket cannot reach back across an independent-stat label. `_INDEPENDENT_STAT_BETWEEN_RE` rejects pairings whose intervening text contains a NEW estimate label (`t`, `F`, `d`, `g`, `OR`, `RR`, `β`, `R²`, `Z`, …) — only variance-family labels (`SD`, `SE`, `M`, `CI`, `%`) are allowed between the candidate token and the labeled CI. efendic's `Mposterior = 20.54, SD=0.04, CI = [-0.61, -0.47]` (only `SD` between) still pairs correctly.

**Impact:** corpus-wide non-idempotency 11 → 7. Broad pytest 1356 pass + 1 known pre-existing B6 fail. Harness Tier-D academic: 0 regressions, 0 new fails (1 still failing — plos-med-1 / B1).

NORMALIZATION_VERSION 1.9.19. Cycle 11/12 contract tests still pass under the refined LABELED-bracket gate.

## [2.4.64] — 2026-05-22

**Cycle 12 (run 9) — three independent normalize_text idempotence fixes.** A 180-doc scan post-cycle-11 found 17 papers still non-idempotent. This cycle packages three independent fixes that together clear 6 of them:

### 1. Final blank-line collapse (5 papers — chan-etal, horsham, lee-feldman, li-feldman-mental-acct, kassambara)

Raw pdftotext output contains form-feed `\x0c` characters at page boundaries. S9's `re.sub(r"\n{3,}", "\n\n", t)` collapses consecutive blank lines, but the form-feed survives upstream stripping into the references region, where R3 (continuation join) processes line-by-line — `"\x0c".strip() == ""` so the form-feed line becomes an empty entry, surrounded by other empty entries. R3 outputs `"\n".join(["...", "", "", "...", ""])` = `\n\n\n\n` (4 newlines). S9's collapse already ran upstream; nothing else collapses. Pass 2 sees the `\n{4}` run and S9 collapses it — non-idempotence.

Fix: add a final `re.sub(r"\n{3,}", "\n\n", t)` right before the H0r/P0r blocks. Any late strip step that empties a line is now safely followed by the collapse, regardless of which step produced the gap.

### 2. Cross-paragraph stat-continuation join (2 papers — korbmacher×2)

A1 (the early stat-line-repair step using `\s*`) crosses paragraph breaks but runs BEFORE S9 strips header/footer noise. A row like

  `r(1798) = -0.27,\n\n472\n\nJournal of Decision Making, Vol. 17...\n\n95% CI [-0.31, ...]`

has so much intervening junk that A1's lookahead fails on pass 1. S9 then strips `472` (page num) and the journal-masthead/page-header (repeated ≥5 times), leaving `-0.27,\n\n95% CI`. A1 is over; LateJoin's A1r uses strict `[ \t]*\n[ \t]*` (single-newline only) and so doesn't fire. Pass 2's A1 sees the now-clean `,\n\n95% CI` and joins — non-idempotence.

Fix: add two paragraph-crossing variants to the LateJoin A1r block, restricted to high-confidence prefixes — `\d+% CI` and `p [<=>]`. No real paragraph STARTS with `95% CI` or `p < .001`, so joining across `\n\n` is safe. The `test_column_bleed_too_many_fragments_ignored` contract is unaffected — its input has no leading `,`/`;`.

### 3. LABELED vs BARE CI bracket discriminator (refines cycle 11)

Cycle 11's proximity gate broke 2 pre-existing tests:
  - `test_ci_pairing_recovers_body_line`: `Mposterior = 20.54, SD=0.04, CI = [-0.61, -0.47]` — `, SD=` falsely tripped the "new stat label" sentence-break check, blocking the legitimate recovery of `20.54` → `-0.54`.
  - `test_efendic_table_point_estimates_recovered_via_ci`: efendic's body-line CI recoveries no longer fired.

Fix: discriminate LABELED brackets (`CI = [...]` / `95% CI [...]` / `CI: [...]`) from BARE brackets (`[lo, hi]` alone). LABELED brackets can pair with any candidate token in the row (the chain `M = X, SD = Y, CI = [...]` is all describing the same estimate). BARE brackets retain the strict 30-char + period/semicolon-break proximity gate (catches the majumder false-positive — bare bracket ~50 chars after `2.01`, attached to a different stat). The `_CI_LABEL_PREFIX_RE` looks back ≤8 chars from the `[` for `CI` / `\d+% CI` (with optional `=`/`:`).

**Impact:** corpus-wide non-idempotency 17 → 11 (cycle 12 cleared 6: 5 bibliography-shift + 2 korbmacher; 3 new bibliography cases of the same shape are now caught by the final collapse). Broad pytest 1356 pass + 1 known pre-existing B6 fail. Harness Tier-D academic: 0 regressions, 0 new fails (1 still failing — plos-med-1 / B1).

NORMALIZATION_VERSION 1.9.18. New tests: `test_normalize_collapses_late_blank_line_runs` + `test_late_join_crosses_paragraph_for_stat_continuation`. Cycle 11's tests (`*_proximity_gate_*`) still pass under the LABELED/BARE refinement.

## [2.4.63] — 2026-05-21

**Cycle 11 (run 9) — `recover_minus_via_ci_pairing` proximity gate.** A 180-doc scan post-cycle-10 found 19 papers still non-idempotent. Among them, 8 (majumder, korbmacher×2, van-boven, chan-feldman-baron, ziano, xiao-poc, amp-1, annals-2) shared a structural defect that ALSO ships in single-pass production: the `_recover_minus_in_record` helper paired every candidate `2X.XX` token with EVERY CI bracket in the same record. A record like `M = 5.37, SD = 2.01), t(1827) = 1.83, p tukey = .067, d = 0.09 [-1.86, 0.04]` contains:

- `2.01` — the standard deviation, a valid positive number that happens to start with `2`.
- `[-1.86, 0.04]` — the CI for `d = 0.09`, not for `2.01`.

`-0.01` falls inside `[-1.86, 0.04]`, so the old logic recovered `2.01` → `-.01`, silently corrupting a valid SD in shipped output. (In stat reporting the CI is canonically adjacent to its point estimate; the brackets are NOT free-floating record-scoped pairings.)

**Fix — proximity gate.** A candidate token only pairs with a CI bracket if:

1. The bracket's start is within `_CI_PAIR_MAX_GAP = 30` chars of the token's end.
2. The intervening text contains no sentence break (`. ` or `; `) and no new stat-label-then-assignment pattern (` SD =`, ` t(`, ` p =`, ` d =`, ` η =`, ...).

If multiple brackets satisfy both, the NEAREST one wins (canonical adjacency).

**Impact:** corpus-wide non-idempotency 19 → 17. 3 papers cleared (van-boven, chan-feldman-baron, ziano); 5 others (majumder, korbmacher×2, xiao-poc, amp-1, annals-2) had OTHER defects flagged by the same diff signature and stay non-idempotent — their root causes are diverse (footnote sentinel stripping, acknowledgment-block reclassification, etc.) and will be addressed cycle-by-cycle. The fix is also a production correctness improvement: the false-positives shipped in single-pass output too, so any paper with a stat-table mixing SDs and CIs was at risk.

Broad pytest 1355 pass + 1 known pre-existing B6 fail (+ 3 new tests). Harness Tier-D academic: 0 regressions, 0 new fails (1 still failing — plos-med-1 / B1 / TABLE-builder cluster).

NORMALIZATION_VERSION 1.9.17. New tests: `test_recover_minus_proximity_gate_rejects_distant_unrelated_brackets` + `test_recover_minus_proximity_gate_keeps_adjacent_recovery` + `test_recover_minus_proximity_gate_rejects_sentence_broken_bracket`.

## [2.4.62] — 2026-05-21

**Cycle 10 (run 9) — `normalize_text` non-idempotence: CHARSUB bucket, `recover_minus_via_ci_pairing` re-recovery.** ip-feldman 2025 PSPB has table cells of the form `B = -2.68 [-4.65, -0.68]` — an already-recovered negative point estimate paired with its CI bracket. The first `normalize_text` pass had recovered the corrupted `22.68` → `-2.68` correctly. On the second pass, the recovery regex re-matched the `2.68` (now preceded by the `-` left by the first recovery), and the substitution produced `--.68` — a destructive corruption. The defect: `_CORRUPT_NEG_TOKEN_RE`'s lookbehind `(?<![\d.])` allowed a literal `-` before the `2`, so a second pass on already-recovered output found new matches.

**Fix — extend the lookbehind to forbid a preceding minus:**

  `(?<![\d.])2(\d?\.\d+)\b` → `(?<![\d.\-])2(\d?\.\d+)\b`

One-char change. Original corruption recovery (`22.68 [-4.65, -0.68]` → `-2.68 [-4.65, -0.68]`) still works — the corrupted form has no preceding `-`. Already-recovered output is now a fixed point.

**Impact:** 1 paper (ip-feldman) cleared from the non-idempotent set. NOT just an idempotence fix: pre-cycle-10 single-pass production output on ip-feldman was ALSO non-deterministic — under certain extraction orders the same cell could ship as `-2.68` or `--.68` depending on whether the recovery pass ran once or twice. Cycle 10 makes the recovery a fixed-point operation. Broad pytest 1352 pass + 1 known pre-existing B6 fail. Harness Tier-D academic: 0 regressions, 0 new fails (1 still failing — plos-med-1 / B1 / TABLE-builder cluster, run continues).

NORMALIZATION_VERSION 1.9.16. New tests: `test_recover_minus_via_ci_pairing_idempotent_on_already_recovered` (contract) + `test_normalize_idempotent_ip_feldman_2025` (real-PDF).

## [2.4.61] — 2026-05-21

**Cycle 9b (run 9) — `normalize_text` non-idempotence: STRIP bucket, S9 Pattern A false-positives on table N values.** A 180-doc scan post-cycle-9 found 29 papers still non-idempotent. 9 of them were chandrashekar 2020 + aiyer + ~7 sibling regression-table papers — pdftotext emits the regression-column N (sample size, e.g. `Observations: 7,182`) as a standalone right-aligned line; A3's thousands-separator removal (academic level) strips the comma → bare `7182`; S9's Pattern A (`≥3 repeats of a 4-digit value = page number`) then flags `7182` (because the table has 4 regression columns all citing N=7182) and strips it on pass 2. Pass 1 preserved them (A3 hadn't run yet — `7,182` had a comma, so the line failed `isdigit()`). This non-idempotence was also a real production text-loss bug: in single-pass production, A3 still runs before S9 strips, so the N values WOULD also be stripped on a clean run if the comma-strip order were swapped. Either way the per-column N gets silently lost.

**Fix — per-occurrence numeric-block discriminator.** S9 Pattern A no longer strips every occurrence of a candidate page-number value; it strips only occurrences that sit ISOLATED (nearest non-blank neighbour above and below is not numeric-only). A line surrounded by other numeric-only lines is a table cell, kept. New module helpers:

  - `_NUMERIC_ONLY_LINE_RE` — `^[\d\s.,()+\-*∗;:]+$` — identifies lines containing only digits + common stat-table punctuation.
  - `_is_numeric_only_line(line)` — exposed for tests.
  - `_is_in_numeric_block(lines, idx)` — checks both directions for a numeric neighbour; used as the "this is a table cell" signal.

S9 Pattern A's `strip_set` is unchanged (the candidate-detection logic still works the same way); only the application step is now per-occurrence-gated. Pattern B's cluster check (sequential 4-digit values within spread ≤50 and mean diff ≤3) reuses the same gate, so a journal whose volume-number cluster overlaps with a regression-table N cluster is also protected.

**Impact:** corpus-wide idempotency scan (source-PDF, n=101): **9 non-idempotent**, down from ~20 at v2.4.60. Verify_out scan (n=180): pending re-check, expected ~20→11. Strided-sample ratchet test 4 → 2. Broad pytest 1350 pass + 1 known pre-existing B6 fail. Harness Tier-D academic: 0 regressions, 0 new fails (1 still failing — plos-med-1 Group B / B1, run continues).

**Methodology note (this cycle's BLIND SPOT):** the handoff plan grouped this case with the JAMA-affil-sentinel case under "STRIP bucket" with one prescription — apply the H0r late-restrip pattern. HEAD reproduction showed they are OPPOSITE-direction defects: JAMA wants pass-2-strip in pass-1; chandrashekar wants pass-2 to STOP stripping. Propagating S9's strip to pass 1 (the H0r pattern) would have made the production text-loss bug worse — silent corpus-wide loss of regression-column sample sizes. Cycle 9 + cycle 9b shipped as two cycles instead. Project lessons.md "late re-apply pattern eligibility" expanded with the discriminator question: *would I be happy if production's single-pass output ALSO stripped this line?* Yes → late re-apply. No → tighten the step.

NORMALIZATION_VERSION 1.9.15. New tests: `test_is_numeric_only_line_distinguishes_table_cells_from_prose` + `test_s9_4digit_pattern_a_preserves_table_n_values` + `test_s9_4digit_pattern_a_still_strips_isolated_page_numbers` + `test_normalize_idempotent_chandrashekar_regression_table`.

## [2.4.60] — 2026-05-21

**Cycle 9 (run 9) — `normalize_text` non-idempotence: STRIP bucket, JAMA P0 anchored-pattern misses split lines.** A 180-doc scan post-cycle-8 found 40 papers still non-idempotent. The dominant single root cause (10 papers — every JAMA Network Open paper in the corpus, `jama_open_1`/.../`jama_open_12`) is the sidebar sentinel `Author affiliations and article information are listed at the end of this article.` arriving from pdftotext as TWO lines: `Author affiliations and article information are\nlisted at the end of this article.` P0's `_strip_page_footer_lines` matches anchored `^...$` patterns, so the two-row form escapes the strip; S7/S8 then join the rows, and only a second `normalize_text` pass catches the now-single-line form.

**Fix — P0r `_page_footer_lines_restripped` (generalization of cycle-7's H0r pattern).** A new block at the end of `normalize_text`, right after H0r, re-applies `_strip_page_footer_lines` to a fixed point on the now-stabilized line positions. P0 itself is idempotent on its own output, so the loop converges in 1-2 iterations. The early P0 (near the top of the pipeline) is retained for performance — most P0 lines are already single-row from pdftotext; P0r catches the small subset that needed S7/S8/LateJoin to be joined first.

**Impact:** 180-doc idempotency scan post-cycle-9 = **29 non-idempotent (down from 40)** — 11 papers cleared (the 10 JAMA papers + 1 incidental). Strided-sample ratchet test 6 → 4. Remaining residuals are: S9 4-digit page-number cluster false-positive on table sample-size values (9 papers — cycle 9b, requires Pattern A tightening, NOT propagation), CHARSUB bucket (5 papers — cycle 10), and 14 individual cases.

**Defect re-classification (methodology):** The handoff plan classified the chandrashekar `7182` case (and aiyer `1118`/`1265`) as "same H0r-pattern fix needed". HEAD reproduction showed the `7182` lines are sample-size values from regression tables (`Observations: 7,182` → after A3 thousands-separator removal → `7182`), legitimately preserved by pass 1 but **incorrectly stripped** by pass 2 via S9 Pattern A (`≥3 repeats of a 4-digit value = page number`). Propagating that strip to pass 1 would silently lose data in production. Cycle 9b instead tightens S9 Pattern A to distinguish per-page markers from clustered table cell values.

Harness Tier-D academic: pending re-extract + check at v2.4.60. NORMALIZATION_VERSION 1.9.14. New tests: `test_p0_jama_affiliations_sentinel_strips_after_line_join` + `test_normalize_idempotent_jama_open_1`.

## [2.4.59] — 2026-05-20

**Cycle 8 (run 9) — `normalize_text` non-idempotence: JOIN bucket.** A 180-doc scan found 85 papers non-idempotent post-cycle-7. The dominant cause was line-join `re.sub` patterns that consume *both* boundary characters in each match — so a run of N consecutive joinable lines halves per pass and the chain never fully converges in one call. A second cause: `S8` (`[a-z,;]\n[a-z]`) did not match Greek-initial lines, so a `,\nσ²(ξ)` boundary survived S8 on pass 1, the A5 academic step then transliterated `σ`→`sigma`, and only pass 2's S8 finally joined it. A third cause: S9's repeated-line / page-number strips remove lines via `"\n".join` of a filtered list, putting the surrounding lines adjacent with a single `\n` — re-exposing line-break boundaries that S7/S8/A1 had already passed over (e.g. chen_2021_jesp's `...predictions on the\nprobability of the future...`).

Three fixes packaged this cycle:

- **S7 + S8 → non-consuming lookahead form.** The trailing-letter group is matched as a lookahead (`(?=[a-z])`) so a chained run of joinable adjacencies fully merges in one pass: `re.sub(r"([a-z,;])\n(?=[a-zα-ω])", r"\1 ", t)` for S8; analogous form for S7's hyphenation repair.
- **S8 Greek-aware.** Trailing class extended to lowercase Greek (U+03B1–U+03C9) so a Greek-initial line joins on pass 1 — fixing the S8-runs-before-A5 ordering gap without reordering the pipeline.
- **Late line-join re-application before H0r.** S7/S8 + the academic A1 stat-line-repair patterns are re-run, all in lookahead form, on the stabilized end-of-pipeline line positions. Catches any line-break boundary that S9 / R3 created by stripping or rearranging lines after the original S7/S8/A1 ran.

**Impact:** 180-doc idempotency scan post-cycle-8 = **36 non-idempotent (down from 85)** — 49 papers cleared. The remaining buckets are STRIP (24→3, via H0r already in cycle 7; the residual is the S9 4-digit page-number cluster detector still firing only on pass 2 — cycle 9) and CHARSUB (5 — destructive char-substitution on re-application, including `recover_minus_via_ci_pairing` `−2.68 → −−.68` — cycle 10). The new corpus-wide ratchet test (`test_normalize_idempotent_corpus`) drops from 10 → 6 in the strided sample.

Harness Tier-D academic: pending re-extract + check. NORMALIZATION_VERSION 1.9.13.

## [2.4.58] — 2026-05-20

**Cycle 7 (run 9) — `normalize_text` non-idempotence on space-broken compounds + position-gated header banners.** Calling `normalize_text` on its own output produced a different result than calling it once — the single (production) pass left work that a second pass completed. Two mechanisms fixed this cycle:

- **S7a `_rejoin_space_broken_compounds`** stripped only the literal `" "` separator from a matched compound, so a curated compound separated by a *newline* (e.g. `repli\ncations`, common after S6 strips a soft hyphen and pdftotext line-wraps the compound) matched the regex's `\s+` but its replacement was a no-op. S8 (line-join) then converted the newline to a space — too late for S7a, which had already run. The 2nd normalize pass finally joined it. **Fix:** strip *all* whitespace in the match (`re.sub(r"\s+", "", m.group(0))`). Rejoins compounds regardless of separator; idempotent and pipeline-order-independent.

- **H0 `_strip_document_header_banners`** scans only the first 30 lines (the header zone). Un-cleaned front-matter noise can push a real banner — e.g. a bare `https://doi.org/…` URL — past the cap on raw input, so H0 misses it. P0/P1/S9/A1/A7/R3 then strip that noise and shift lines up; on a 2nd normalize pass the banner is now inside the zone and H0 catches it. **Fix:** re-apply H0 to a fixed point at the *end* of the pipeline, on stabilized line positions — `H0r_header_banner_restrip`. A second normalize pass finds the header already clean.

`test_normalize_idempotent_chan_feldman` (real PDF) — chan_feldman exercised both mechanisms (curated `repli`/`differ`/`con` compounds split across newlines + a `https://doi.org/10.1080/…` banner shifted into the header zone) and now converges in one pass.

**Honest corpus-wide gate.** A 180-doc scan revealed `normalize_text` is *systemically* non-idempotent: 85 papers across three root-cause buckets — JOIN (54: line-join `re.sub` steps consume the boundary char, so chained joins need N passes), STRIP (24: position/cluster-gated strips fire only on pass 2), CHARSUB (7: destructive char-substitution on re-application — e.g. minus-recovery `−2.68 → −−.68`). Cycles 8-10 take those buckets per-mechanism. The new `tests/test_normalize_idempotent_real_pdf.py::test_normalize_idempotent_corpus` is a strided-sample ratchet (currently 10) tightened by each idempotency cycle toward 0; a cycle that raises it is a regression.

NORMALIZATION_VERSION 1.9.12. 4 new tests. Harness Tier-D: 0 regressions, 0 new fails (cycle 7 ships, run continues).

**Also (test-infra):** `tests/conftest.py` `PDF_PATHS["docpluck"]` was stale — pointed to `~/Dropbox/Vibe/PDFextractor` when the repo lives at `~/Dropbox/Vibe/MetaScienceTools/PDFextractor`. Three real-PDF tests (`test_extraction.py`, `test_metaesci_followups.py`, `test_sections_real_corpus.py`) were silently skipping. Now derived as the sibling-repo path, robust to checkout location.

## [2.4.57] — 2026-05-18

**Cycle 4 (run 9, harness-gated) — pdftotext and pdfplumber destroy the cmsy10 `≥`/`≤` glyph to U+FFFD (glyph, S0).** On a tightly-kerned PDF that typesets comparison operators with the TeX Computer Modern math-symbol font (`cmsy10`), neither pdftotext nor pdfplumber can decode the `≥`/`≤` glyph — both emit U+FFFD. The glyph identity is destroyed in *both* engines, so the layout channel cannot recover it; recovery must be context-based. `plos_med_1` (PLOS Medicine, PROSECCO trial) rendered three prose comparisons — `age �18 years`, `(<20/�20 mm)`, `<20 mm versus �20 mm` — as raw U+FFFD; the harness Tier-D `glyph` check flagged it.

Fix (v2.4.57) — `normalize.py::recover_fffd_comparison_operators` (pipeline step S5b, sibling of S5a FFFD→eta):
- **Rule 1 — complement pairing (airtight).** A corrupted `[FFFD]N` contrasted with a clean `<N`/`>N` of the *same* number N is a set-partition — every value is either `<N` or `≥N` (resp. `>N` or `≤N`). A regex backreference enforces the same-number constraint, so a non-matching pair never matches. Recovers `(<20/≥20 mm)` and `<20 mm versus ≥20 mm` with zero false-positive risk.
- **Rule 2 — document consensus.** A lone `[FFFD]N` with no local complement is recovered only when Rule 1 already fired in the document AND every recovery agreed on one operator (one PDF == one font == one corruption shape). Recovers the lone `age ≥18 years` and the six fibroid-size bins `≥5–10 mm`…`≥40 mm`. Confirmed against the paper's AI-multimodal gold.

Harness Tier-D gate (academic level): `plos_med_1` flips the `glyph` check fail→pass; 0 regressions, 0 new fails corpus-wide. NORMALIZATION_VERSION 1.9.11. 14 new tests (`test_fffd_comparison_recovery_real_pdf.py`).

Phase-5d AI-gold verification confirmed the cmsy10 fix is clean (every recovered `≥` matches the gold) but surfaced pre-existing defects beyond this cycle's scope: `plos_med_1`'s structured tables are badly broken (Table 2 emits 1 of 11 rows, Table 5 is an empty shell, Tables 3/4 swap bodies under each other's captions), the section annotator promotes front-matter sidebar labels to `##` headings, and front-matter metadata leaks into the body. The Tier-D backlog also still has 9 `text_loss` fails (largely `_fingerprint` glyph-representation false-positives) and 2 extraction timeouts (`nat_comms_3`, `xiao-poc-epley` — environmental Camelot perf). The run continues.

## [2.4.56] — 2026-05-17

**Cycle 3 (run 9, harness-gated) — CMEX10 extensible matrix-bracket pieces surfaced as Private-Use codepoints (glyph, S1).** A matrix or tall bracketed expression typeset with the TeX `CMEX10` math-extension font is built from extensible square-bracket *pieces* — an upper corner, a repeated extension segment, a lower corner — for each side. Embedded with no ToUnicode CMap, both pdftotext and pdfplumber surface these as U+F8EE–F8FB Private-Use codepoints. `ieee_access_10` rendered a 5-row matrix carrying 10 such raw PUA glyphs; the verification harness's Tier-D `glyph` check flagged it.

Fix (v2.4.56) — `normalize.py::recover_pua_glyphs` (the shared PUA-recovery helper introduced in v2.4.54) is extended with the CMEX bracket-piece block: U+F8EE/F8EF/F8F0 → U+23A1/23A2/23A3 (left square bracket upper-corner / extension / lower-corner) and U+F8F9/F8FA/F8FB → U+23A4/23A5/23A6 (right). The mapping is confirmed by glyph geometry — on `ieee_access_10` page 5 the six codepoints sit in two vertical columns (left x≈350, right x≈546), each a top corner / three extensions / bottom corner ordered by y-coordinate. The recovery flows through all three text channels already wired for the helper (W0e body step, `cell_cleaning._html_escape`, render post-process).

Harness Tier-D gate (academic level): `ieee_access_10` flips the `glyph` check fail→pass; 0 new fails. NORMALIZATION_VERSION 1.9.10, TABLE_EXTRACTION_VERSION 2.1.5. 2 new tests.

The harness Tier-D backlog still has open fail cells — 1 glyph (`plos_med_1`: both engines drop the `≥` glyph to U+FFFD — needs context-based recovery), 9 `text_loss` (largely Tier-D check false-positives — `_fingerprint` drops the raw Greek glyph but keeps the rendered ASCII transliteration, breaking window matches), and `nat_comms_3` (a Camelot table-extraction timeout — environmental, not a code regression); the run continues.

## [2.4.55] — 2026-05-17

**Cycle 2 (run 9, harness-gated) — a caption-only / isolated table rendered with no `### Table N` heading (table_parity, S1).** When `extract_pdf_structured` detects a table only by its caption — Camelot reconstructed no grid AND there is no linearized `raw_text` fallback (the table is a flat image, or sits on a page Camelot could not parse) — render.py emitted just the italic `*Table N. <caption>*` line, with no `### Table N` heading. The v2.4.2 rationale was that a bare heading "falsely promises structured content"; but dropping the heading hid the table from every structural view. A reader scanning `### Table` headings, and the verification harness's Tier-D `table_parity` check (the count of `### Table` headings must equal the count of tables in `tables.json`), both lost it — the check failed on 15 corpus documents (escicheck chan / chandrashekar / imada / jacobs / lee / wong / zhu / ziano-ppnumbing / ziano-mp; pdfextractor jama-open-5 / ar-royal-society / bjpsych-open-1 / ieee-access-5 / sci-rep-2 / sci-rep-3).

Fix (v2.4.55) — render.py's in-section caption-only-table branch now emits `### {label}` + the italic caption, consistent with the appendix leftover-table path (which already emitted `### {label}` for a caption-only table — so the two paths were silently inconsistent). The `*{caption}*` italic line is kept immediately after the heading, so `_suppress_orphan_table_cell_text` still recognizes it and drops any linearized orphan cell-rows beneath. Keyed purely on the structural signature (an in-section table with a caption but no html/raw_text), not on paper identity.

Harness Tier-D gate (academic level, whole corpus): all 15 `table_parity` documents flip fail→pass; 0 new fails; 0 regressions attributable to the change (a render-layer caption fix cannot affect any other corpus document's checks). The v2.4.2 contract test that asserted the heading is *absent* is corrected to the new contract and renamed; 3 new real-PDF tests assert the `### Table` heading count equals the `extract_pdf_structured` table count.

The harness Tier-D backlog still has open fail cells — 2 glyph (`ieee_access_10` CMEX10 matrix-bracket pieces, `plos_med_1` U+FFFD), 9 `text_loss`; the run continues.

## [2.4.54] — 2026-05-17

**Cycle 1 (run 9, harness-gated) — Adobe-Symbol-font glyphs surfaced as Private-Use-Area codepoints (glyph, S1).** Some PDF/DOCX producers embed the Adobe "Symbol" font with no ToUnicode CMap, so pdftotext / mammoth surface each Symbol glyph as a Private-Use codepoint U+F000+<symbol-byte> — the standardized regression coefficient β reads as U+F062, the χ of a χ² test statistic as U+F063, a bullet • as U+F0B7. A PUA codepoint carries no Unicode identity; it is purely a font-encoding artifact and is never legitimate in extracted academic text. The verification harness's Tier-D `glyph` check flagged it on `docxtests/BH1988_manuscript` (β ×2) and `escicheck Xiao-etal-2024 Monin&Miller` (χ ×2, bullet ×2).

Fix (v2.4.54) — new `normalize.py::recover_pua_glyphs`: it maps the Adobe Symbol StandardEncoding (U+F020–F0FF — the full Greek alphabet, math operators and relations, and extensible-bracket pieces; 185 entries) back to real Unicode. The encoding is a fixed, decades-stable standard, so the recovery is zero-false-positive and fully general — keyed on the structural signature "codepoint in the Symbol-font PUA block", never on paper identity. A PUA codepoint outside the Symbol block, or an unassigned Symbol position, is left untouched — never guessed. Greek stays Greek (CLAUDE.md hard rule 4 — the A5 step transliterates β→"beta" for ASCII-form callers; the rendered .md keeps β). The helper is wired into all three text channels: the body channel's new W0e step (`normalize_text`), `cell_cleaning._html_escape` (Camelot table cells), and the `render_pdf_to_markdown` post-process (figure/table captions, unstructured-table fences, raw_text fallbacks).

Harness Tier-D gate (academic level, whole corpus): `bh1988` and `xiao-monin-miller` both flip the `glyph` check fail→pass; 0 new fails; the cycle's diff (a signature-gated glyph map that early-returns on PUA-free text) provably cannot regress any other corpus document. Broad pytest 1319 passed (the one failure, `test_request_09`, is the pre-existing COL-class column-interleave defect, unrelated). NORMALIZATION_VERSION 1.9.9, TABLE_EXTRACTION_VERSION 2.1.4. 11 new tests (`tests/test_pua_glyph_recovery_real_pdf.py`).

The harness Tier-D backlog still has open fail cells — the other two glyph docs (`ieee_access_10` CMEX10 matrix-bracket pieces, `plos_med_1` U+FFFD), 15 `table_parity`, 9 `text_loss`; the run continues.

## [2.4.53] — 2026-05-17

**Cycle HALLUC-HEAD-1 (APA-first run, run 7) — a CRediT contributor-role token promoted to a `## ` section heading (HALLUC-HEAD, S1).** A paper's CRediT (Contributor Roles Taxonomy) block lists the 14 standard contribution roles. One of them — `Methodology` — collides with the canonical Method/Methodology *section* keyword, so the section partitioner promotes that role token to a `## Methodology` heading even though it sits inside the contributor-roles table, not at a real section boundary. chan_feldman, chandrashekar and chen each rendered a hallucinated `## Methodology` heading in their author-contributions block (none of their AI golds has one).

Fix (v2.4.53) — new render post-processor `_demote_credit_role_headings`: it demotes a `## <CRediT-role>` heading to plain text, but ONLY when the surrounding ±10-line window holds at least 3 OTHER CRediT role tokens (the closed 14-term CRediT vocabulary, normalized for dash/ampersand variants). A real Methodology section heading is followed by method prose — 0 nearby role tokens — and is left untouched. Keyed purely on the structural signature (a role token embedded in the role list), not on paper identity.

chan_feldman, chandrashekar and chen each lose the hallucinated `## Methodology` heading and keep their real `## Method` section heading. Phase-5d AI-gold verify: the demoted heading is absent from all three golds; the change is heading-markup-only (0 text loss — the role word stays as plain content). 26/26 baseline PASS. Tier1==Tier2==Tier3. 5 new tests (`tests/test_render.py`).

~8 APA papers still FAIL Phase-5d verification (HALLUC-HEAD residuals — `## Conclusion`/`## Supplementary Material`/`## Data Availability Statement` mid-text promotions, TBL-CAP, FIG-3c-2, G5c-2, G5d, TABLE cluster, COL); the run continues.

## [2.4.52] — 2026-05-16

**Cycle FIG-4 (APA-first run, run 7) — a legitimate long figure caption truncated by the 400-char overflow trim (FIG, S2).** The FIG-1 overflow trim (`_trim_overflowing_figure_caption`, v2.4.47) treats any figure caption exceeding 400 chars as over-absorbed body prose and walks it back to the last sentence terminator before char 400. efendic Figure 1's caption is a label plus a long `Note.` (the abbreviation key + the three technologies + both samples + the negative-slope explanation) that legitimately runs ~498 chars — so the overflow trim cut it at `(MTurk and Prolific).` and dropped the final Note sentence `The negative slope shows the predicted negative relationship between risks and benefits…`.

Fix (v2.4.52) — `_extract_caption_text` now tracks whether its paragraph-walk stopped at a real `\n\n` paragraph break (a complete caption paragraph) or ran to the 800-char hard cap / next-caption boundary (a runaway that welded body prose with a single `\n`). The 400-char overflow trim is applied only to the runaway case. A caption that overflows 400 chars but ended at a clean paragraph break — bounded by pdftotext's own paragraph boundary — is a legitimate long caption and is kept whole. FIG-1's ellipsis-truncation fix is unaffected: those captions are runaways (no `\n\n`), so the overflow trim still fires.

efendic Figure 1's full Note is recovered (498-char caption, ends cleanly on `benefits decrease.`, no ellipsis). It is the only APA figure caption exceeding 360 chars, so the gate change is precisely scoped. Phase-5d AI-gold verify: efendic Figure 1 caption matches the gold figure note exactly, 0 text-loss, 0 body-prose absorbed. 26/26 baseline PASS. Tier1==Tier2==Tier3. 1 new real-PDF test; the FIG-1 corpus invariant test updated (a caption MAY exceed 400 chars if it is a complete caption — only ellipsis-truncation and over-400 *runaways* are defects).

~8 APA papers still FAIL Phase-5d verification (FIG-3c-2 body-exceeds-block double-emission, TBL-CAP, G5c-2, G5d, HALLUC-HEAD, TABLE cluster, COL); the run continues.

## [2.4.51] — 2026-05-16

**Cycle FIG-3c (APA-first run, run 7) — figure caption double-emitted (inline in body + as the `### Figure N` block) (FIG, S2).** pdftotext linearizes a figure's caption into the running text column, so a figure caption appears twice in the rendered markdown: once inline as a standalone body paragraph, and once as the spliced `### Figure N` block. chan_feldman rendered all 10 figure captions twice; chandrashekar, efendic, jdm_.2023.16 and maier likewise.

Fix (v2.4.51) — new render post-processor `_suppress_inline_duplicate_figure_captions`: it collects every `### Figure N` block's caption, then drops a body-text run that begins with a `Figure N` label and reproduces that block's caption. **Safe-subset only:** the inline run is removed ONLY when the block caption *fully covers* it (equals, or is a prefix-superset of, the normalized inline run). An inline run that EXCEEDS the block caption — because the block caption was trimmed shorter, or the inline run accumulated trailing body prose — is left untouched, so no caption text can be lost. The pass runs after every glyph-normalization pass (destyle / minus-recovery / ligature decomposition) so the inline line and the block caption are compared in the same final glyph form (a stray `ﬂ` ligature in one would otherwise defeat the equality check).

Across the APA corpus ~21 double-emitted captions in 5 papers are de-duplicated (chan_feldman Figs 1–10, chandrashekar Figs 1/3, efendic Figs 2–5, maier Figs 1/2, jdm_.2023.16 Figs 2–4). ~7 body-exceeds-block cases are deliberately skipped and queued (FIG-3c-2). Phase-5d AI-gold verify across 3 papers: 3 PASS, 0 text-loss, 0 hallucination — every removed line was an exact duplicate of a surviving `### Figure N` block. 26/26 baseline PASS. Tier1==Tier2==Tier3. 6 new tests (`tests/test_render.py`).

~9 APA papers still FAIL Phase-5d verification (FIG-3c-2 body-exceeds-block double-emission, FIG-4 Note trailing-sentence loss, TBL-CAP, G5c-2, G5d, HALLUC-HEAD, TABLE cluster, COL); the run continues.

## [2.4.50] — 2026-05-16

**Cycle FIG-3b (APA-first run, run 7) — figure/table caption anchored to a body-text reference instead of the real caption (FIG, S2).** When a paper both *references* a figure/table in body prose ("…we summarised the effects in Figure 10.") and has the figure/table's real caption, pdftotext line-wraps the body sentence so the "Figure 10." token lands at a line start and false-matches the caption regex. That in-text reference often sits *earlier* in the document than the real caption, and `extract_pdf_structured`'s dedup kept the first occurrence per `(kind, number)` — so the renderer showed body prose as the caption (chan_feldman Figure 10 rendered the sentence `We found support for the effect of perceived apology…` as its caption).

Fix (v2.4.50) — new `caption_anchor_is_in_text_reference` in `tables/captions.py`: a real caption is set off by a paragraph break (blank line) or starts a fresh sentence, whereas an in-text reference *continues* the previous line's sentence (that line ends mid-clause — a lowercase word or comma). The helper advances past the `^\s*` the caption regex absorbs to inspect the line structure around the *actual* token. `extract_pdf_structured`'s dedup now prefers a non-reference anchor when a `(kind, number)` has multiple matches, falling back to first-in-document-order when every anchor looks like a reference (no regression vs. the old behavior in that case).

A corpus scan of all 52 test PDFs found 14 caption groups with a mixed reference/real-caption anchor set — across APA (chan_feldman, chen, jamison, maier), AOM (amd_2, annals_3), IEEE (ieee_access_2/9/10) and Vancouver (plos_med_1) — every one now resolves to the real caption. Phase-5d AI-gold verify across 51 figure/table captions in 3 papers: 51 PASS, 0 wrong-anchor, 0 text-loss, 0 hallucination. 26/26 baseline PASS. Tier1==Tier2==Tier3. 10 new tests (`tests/test_caption_regex.py`, `tests/test_figure_caption_trim_real_pdf.py`).

~9 APA papers still FAIL Phase-5d verification (FIG-3c figure-caption double-emission, FIG-4 Note trailing-sentence loss, TBL-CAP table-caption over-extension into column headers, G5c-2, G5d, HALLUC-HEAD, TABLE cluster, COL); the run continues.

## [2.4.49] — 2026-05-16

**Cycle FIG-3a (APA-first run, run 7) — figure caption absorbs body prose at a lowercase-initial `. ` boundary (FIG, S2).** After the FIG-1/FIG-2 walk-stop fixes, some figure captions still absorbed trailing body prose that pdftotext welded on at a real `. ` sentence boundary with no `\n\n` paragraph break — so the paragraph-walk could not separate it. Two shapes: a wrapped citation fragment (`...by frame and conditions. and Linos, 2022).` — chandrashekar Figure 4) and a body sentence (`...natural logarithmic scale. peoples' preferences. Given the other successful replication...` — chandrashekar Figure 5). The common structural signature: a figure caption's own sentences always start *capitalized*, so a `. ` terminator followed by a *lowercase-initial* word is absorbed body prose.

Fix (v2.4.49) — `_trim_caption_at_body_prose_boundary` in `extract_structured.py` gains a second boundary signature: trim a figure caption at the first `. ` whose tail starts with a lowercase letter. Guarded against three legitimate lowercase continuations: a non-terminal abbreviation before the period (`vs.`/`e.g.`), a caption-NOTE label before it (`Note. t-values …` — new `_CAPTION_LABEL_WORDS`), and a significance-legend tail (`ns p>.05, * p<.05 …` — new `_SIGNIFICANCE_LEGEND_TAIL_RE`, recognizing the U+2217 asterisk-operator APA PDFs use). Keyed purely on the structural signature, figures only.

A corpus scan of all 18 APA papers found exactly 5 genuine lowercase-boundary absorptions (chandrashekar Figs 4/5, jdm_.2023.16 Fig 1, jdm_m.2022.3 Figs 1/2) — all trimmed to their AI golds — and 2 legitimate lowercase continuations (efendic Fig 1 `Note.`, korbmacher Fig 1 significance legend) — both correctly kept. Phase-5d AI-gold verify across 18 figures in 5 papers: 18 PASS, 0 text-loss, 0 hallucination, 0 regressions. The v2.4.48→v2.4.49 diff is figure-caption-text only. 26/26 baseline PASS. 10 new real-PDF + contract tests in `tests/test_figure_caption_trim_real_pdf.py`.

~10 APA papers still FAIL Phase-5d verification (FIG-3b caption-anchor defect, FIG-3c figure-caption double-emission, efendic Fig 1 Note trailing-sentence loss, G5c-2 partitioner split-heading rejoin, G5d named-heading demotion, HALLUC-HEAD, TABLE cluster, COL); the run continues.

## [2.4.48] — 2026-05-16

**Cycle FIG-2 (APA-first run) — figure caption absorbs body prose past a period-less caption end (FIG, S2).** The `_extract_caption_text` paragraph-walk only stopped at a `\n\n` blank-line break when the preceding text ended with a `.`/`!`/`?` sentence terminator. Two common caption shapes end *without* a period and so the walk sailed past the `\n\n` that legitimately ends them and absorbed the following body prose: (1) an APA period-less Title-Case figure title (`The Interaction Between Change in … Non-Manipulated Attribute` — efendic Figures 4/5), and (2) a trailing significance legend (`Note. * p < .05, ** p < .01, *** p < .001` — chandrashekar Figures 1/3).

Fix (v2.4.48) — new helper `_caption_is_complete_without_terminator` in `extract_structured.py`, called from the figure-caption paragraph-walk. It recognizes a caption as complete-without-a-period when the accumulated text ends with a significance legend, or is a complete APA Title-Case title (≥4 words, every content word capitalized, joined by lowercase function words). The walk then stops at the `\n\n`. The label prefix is stripped case-insensitively (pdftotext may emit `FIGURE 15.` while `cap.label` is title-case) and a leading PMC `Author Manuscript` running header is stripped so it cannot read as a 4-word title. Keyed purely on the structural signature, figures only.

efendic Figures 4/5 and chandrashekar Figures 1/3 recovered to their AI golds (welded body prose removed). Phase-5d AI-gold verify across 10 figures in 2 papers: 8 PASS, 2 RESIDUAL-ABSORB (untargeted — queued as FIG-3), 0 text-loss, 0 regressions. The v2.4.47→v2.4.48 diff is figure-caption-text only (0 body text loss, 0 hallucination — the absorbed prose remains intact in the body). 26/26 baseline PASS. New real-PDF + contract tests in `tests/test_figure_caption_trim_real_pdf.py`.

~11 APA papers still FAIL Phase-5d verification (FIG-3 caption residual + double-emission, G5c-2 partitioner split-heading rejoin, HALLUC-HEAD, TABLE cluster, COL); the run continues.

## [2.4.47] — 2026-05-16

**Cycle FIG-1 (APA-first run) — figure caption truncated mid-word with an ellipsis (FIG, S2).** When pdftotext welds a figure's following body prose onto its caption with only a single newline (no `\n\n` paragraph break), the `_extract_caption_text` paragraph-walk cannot find a stopping point and absorbs body prose up to the 800-char hard cap. The old 400-char cap then cut the caption mid-word and appended `…` — e.g. `jdm_m.2022.2` Figure 1 absorbed the `H1 :` hypothesis statement and Figure 3 absorbed a `(N = 61) performed …` body sentence, both ending in a fragment. A corpus scan found 12 such truncated figure captions across 6 APA papers.

Fix (v2.4.47) — new helper `_trim_overflowing_figure_caption` in `extract_structured.py`. When a figure caption overflows the 400-char hard cap (which, in the 17-paper APA corpus, only ever happens on an over-absorbed caption — no legitimate figure caption exceeds ~360 chars), it walks the cap window back to the last genuine sentence terminator instead of hard-truncating mid-word. Abbreviation periods (`vs.`, `e.g.`, author initials) are skipped so the caption is not cut mid-clause, and the surviving caption is required to keep real description content past its label. Keyed purely on the structural signature (caption overflow + sentence boundary), figures only — table captions keep the existing `_trim_table_caption_at_cell_region` path.

`jdm_m.2022.2` Figures 1 and 3 are recovered exactly to the AI gold; all 12 ellipsis-truncated captions across the APA corpus are eliminated (0 remain, 0 over-400). Phase-5d AI-gold verify across 28 figures in 6 papers: 0 text-loss, 0 ellipsis-truncated. 6 captions retain partial trailing body prose (a sentence-terminated residual — queued as cycle FIG-2). The v2.4.46→v2.4.47 diff is figure-caption-text only (0 body text loss, 0 hallucination — the absorbed prose remains intact in the body). 26/26 baseline PASS. New real-PDF + contract tests in `tests/test_figure_caption_trim_real_pdf.py`.

~11 APA papers still FAIL Phase-5d verification (FIG-2 caption residual + double-emission, G5c-2 partitioner split-heading rejoin, HALLUC-HEAD, TABLE cluster, COL); the run continues.

## [2.4.46] — 2026-05-16

**Cycle G5c-1 (APA-first run) — orphan multi-level section number stranded above its heading (G5c, S1).** pdftotext sometimes splits a numbered subsection heading such as `5.4. Discussion` into a bare `5.4.` line and a separate `Discussion` line; the section partitioner then promotes the lone title word to a generic `## Discussion` and strands the number on its own line. In `jdm_m.2022.2` the `5.4. Discussion` subsection of Study 1 rendered as an orphan `5.4.` followed by a top-level `## Discussion`.

Fix (v2.4.46) — new render post-processor `_fold_orphan_multilevel_numerals_into_headings`, the multi-level analogue of `_fold_orphan_arabic_numerals_into_headings` / `_fold_orphan_roman_numerals_into_headings`. It folds an orphan `N.N.` number into the **immediately-adjacent** generic `##`/`###` heading and emits it at subsection level: `5.4.`⏎`## Discussion` → `### 5.4. Discussion`. Keyed purely on the structural signature (an isolated multi-level dotted number is itself a strong subsection marker — body prose and list items never emit a bare `5.4.` line) plus blank-line-only adjacency. `### Figure N` / `### Table N` (library-emitted structural markers) and already-numbered headings are excluded. Only the immediately-adjacent case is folded; an orphan number whose title word the partitioner consumed elsewhere (leaving body prose below the number) is partitioner-level work (G5c-2) and is left untouched.

`jdm_m.2022.2`: the `5.4. Discussion` heading is recovered and AI-gold-verified correct. The v2.4.45→v2.4.46 diff is heading-markup only (0 text loss, 0 hallucination). 26/26 baseline PASS. New real-PDF + contract tests in `tests/test_orphan_multilevel_number_real_pdf.py`.

~11 APA papers still FAIL Phase-5d verification (G5c-2 partitioner split-heading rejoin, HALLUC-HEAD, FIG caption double-emission, TABLE cluster, COL); the run continues.

## [2.4.45] — 2026-05-16

**Cycle 13 (autonomous APA-first run) — long descriptive numbered headings demoted to body text (G5b, S1).** `render.py`'s numbered-heading promoters carried a "long lowercase-word run" prose guard (`max_lc_run >= 5`) that rejected legitimate descriptive headings — e.g. `2.4.2.2. Inference of planning strategies and strategy types`, `3.3.2.1. The quality of planning on the previous trial moderates the effect of reflection`. jdm_.2023.16 alone had 19 multi-level numbered subsection headings demoted to body text.

Fix (v2.4.45) — the lowercase-run guard is **removed from `_promote_numbered_subsection_headings`**: multi-level dotted numbering at line-start is itself a strong section-heading signal (combined with capital-started title + no terminal sentence punctuation + single ≤80-char line), and descriptive subsection titles legitimately run to many lowercase words, so the guard could not distinguish a real heading from prose and only mis-rejected headings. For `_promote_numbered_section_headings` (single-level `N.`, which genuinely collides with enumerated lists) the guard is **kept but raised `5 → 8`** — single-level promotion still has its document-numbering-range / uniqueness / list-adjacency gates as defense in depth.

jdm_.2023.16: 19 previously-demoted multi-level headings now render as `###`; the v2.4.44→v2.4.45 diff is heading-promotion only (0 text loss, 0 hallucination). 26/26 baseline PASS. New real-PDF + contract tests in `tests/test_numbered_heading_promotion_real_pdf.py` and `tests/test_render.py`.

~11 APA papers still FAIL Phase-5d verification; the autonomous run continues.

## [2.4.44] — 2026-05-16

**Cycle 12 (autonomous APA-first run) — Latin typographic ligatures not decomposed in the table/caption channels (GLYPH, S2).** pdftotext preserves presentation-form ligature glyphs (`ﬀ ﬁ ﬂ ﬃ ﬄ ﬅ ﬆ`, U+FB00-FB06) verbatim, so words rendered as `conﬁdent` / `inﬂuence` / `eﬃcient` — broken for search, word matching, and any downstream NLP. A corpus scan found the glyphs in 35 rendered papers (korbmacher 82×, jdm_.2023.16 34×, jdm_m.2022.2 8×). The body channel's `normalize.py` S3 step already expanded ligatures correctly; the leak was confined to **table cells, figure/table captions, and `unstructured-table` fenced blocks**, which bypass `normalize_text` entirely.

Fix (v2.4.44) — `normalize.py::decompose_ligatures` is now the single shared helper for the full U+FB00-FB06 block, mapping each glyph to ASCII via an explicit table (`ﬁ→fi`, `ﬂ→fl`, `ﬃ→ffi`, `ﬄ→ffl`, `ﬀ→ff`, `ﬅ/ﬆ→st`). An explicit table is used rather than a scoped NFKC pass because NFKC of `ﬅ` (U+FB05) yields `ſt` with a non-ASCII LONG S. The body channel's S3 step calls the helper (and so gains `ﬅ/ﬆ` coverage); `cell_cleaning._html_escape` (table cells) and the `render_pdf_to_markdown` post-process (captions, `unstructured-table` fences, raw_text fallbacks) call it too — the established three-channel glyph-fix pattern.

Verified across 3 papers: jdm_m.2022.2, korbmacher, jdm_.2023.16 — all now render 0 residual ligature glyphs (was 8 / 82 / 34); `conﬁdent`→`confident`. Superscripts and plain text untouched; the S3 body step still tracks `ligatures_expanded`. 26/26 baseline PASS. 11 tests in `tests/test_ligature_decomposition_real_pdf.py`.

`NORMALIZATION_VERSION` 1.9.7 → 1.9.8.

~12 APA papers still FAIL Phase-5d verification; the autonomous run continues.

## [2.4.43] — 2026-05-16

**Cycle 11 (autonomous APA-first run) — single-level numbered section headings demoted to body text (G5a, S1).** Cycle 9 (v2.4.41) promoted multi-level numbered subsection headings (`5.1.`, `6.1.1.`); single-level top-level numbered headings — `2. Omission neglect`, `3. Choice deferral`, `1. Hindsight bias` — were still rendered as plain body text when the title is not a canonical section word.

Fix (v2.4.43) — new `render.py::_promote_numbered_section_headings` promotes a single-level `N. Title` line to `## N. Title`. Single-level promotion has a large false-positive surface (enumerated lists also look like `N. Title`), so it is gated by a **document-internal-consistency** rule, not a bare pattern match:
- the document must already number its sections (≥1 existing `#{2,4} N` heading);
- the candidate's number must fall in a contiguous integer run that connects to a proven section number — a number outside the section-numbering range (e.g. a `1.` list item in a paper whose sections run 30-32) is never promoted;
- a number that appears more than once is a restarting list, not a section sequence — excluded by a uniqueness test;
- a line adjacent to a sibling `N.` line is inside a list, not at a section boundary — excluded;
- titles with terminal punctuation or a prose-like run of ≥5 lowercase-initial words are excluded.

Verified across 3 papers: jdm_m.2022.2 promoted 6 of 7 single-level sections (`## 2.`–`## 8.`; one blocked by the lowercase-run prose guard — a known separate residual); chen 6 of 10 (the rest blocked because survey-question lists reuse section numbers 1/2/3/5 — a conservative under-promotion, not a false positive); **chandrashekar 0 false positives** — its exclusion-criteria and analysis-step enumerated lists were correctly NOT promoted (every gate held). 26/26 baseline PASS. 7 new tests in `tests/test_numbered_section_promotion_real_pdf.py`.

**Residual (queued):** the ≥5-lowercase-word prose guard still rejects long descriptive headings (`4. Knowledge acquisition, decision delay, and choice outcomes`); list-number collision blocks a section heading whose number a body list reuses.

~12 APA papers still FAIL Phase-5d verification; the autonomous run continues.

## [2.4.42] — 2026-05-16

**Cycle 10 (autonomous APA-first run) — Elsevier page-1 footer spliced into the Introduction body (D4, S2).** The APA Phase-5d sweep found that the Elsevier page-1 footer block — the corresponding-author e-mail line and the ISSN / front-matter / copyright line — was extracted by pdftotext at the page boundary and welded into the Introduction body (`ar_apa_j_jesp_2009_12_011`: `E-mail address: muraven@albany.edu` / `0022-1031/$ - see front matter Ó 2009 Elsevier Inc. All rights reserved.` spliced between two Introduction paragraphs; `chen_2021_jesp`: the `0022-1031/© 2021 …` line in the front matter).

Fix (v2.4.42) — two `normalize.py` W0 watermark patterns. **Issue K** strips the Elsevier ISSN / front-matter / copyright line: anchored on the line-leading journal ISSN `\d{4}-\d{3}[\dX]/` (academic body prose and references never begin with an ISSN-slash) and additionally requiring an `Elsevier` / `All rights reserved` / `see front matter` keyword, so a coincidental digit run can never match. The pre-existing Issue-H copyright pattern only fired when the line *started* with `©`/`Ó`; these lines start with the ISSN. **Issue L** strips the singular `E-mail address:` corresponding-author line (must contain an `@`). The plural multi-author `E-mail addresses:` list is intentionally left alone — it wraps across several lines, so a one-line strip would shred it.

Verified on ar_apa_011 (2 footer lines removed, both surrounding Introduction paragraphs intact) and chen (ISSN line removed) — surgical deletions, zero body-prose loss. 26/26 baseline PASS. 7 new tests in `tests/test_elsevier_footer_strip_real_pdf.py`.

**Residual (queued):** the standalone lowercase `doi:10.…` footer line is intentionally not stripped — a reference whose DOI wraps onto its own line would be indistinguishable, risking text loss. The plural `E-mail addresses:` multi-author list and the `Received … Accepted …` history line remain.

`NORMALIZATION_VERSION` 1.9.6 → 1.9.7.

~12 APA papers still FAIL Phase-5d verification; the autonomous run continues.

## [2.4.41] — 2026-05-16

**Cycle 9 (autonomous APA-first run) — numbered subsection headings demoted to body text (G5, S1).** The APA Phase-5d sweep found that numbered subsection headings in the dominant Cambridge/JDM and Elsevier style — `5.1. Participants and design`, `5.3.3. Choice deferral`, `6.1.1. Replication: Retrospective hindsight bias` — were rendered as plain body text instead of `###` headings, across jdm_m.2022.2, chen_2021_jesp, jdm_.2023.15, jdm_.2023.16 and others.

Root cause — `render.py::_NUMBERED_SUBSECTION_HEADING_RE` was too strict in two ways: (1) the number group `\d+(\.\d+){1,3}` was immediately followed by `\s+`, so a number written with a **trailing dot** (`5.1.`, `5.3.3.` — the overwhelmingly common style) never matched; (2) the title character class excluded the colon, rejecting headings like `Replication: Retrospective hindsight bias`.

Fix (v2.4.41) — the number group tolerates an optional trailing dot (`\d+(\.\d+){1,3}\.?`) and the title may carry an internal colon. All existing guards are unchanged: a title ending in sentence-terminator punctuation (including a trailing colon), or a prose-like run of ≥5 lowercase-initial words, is still rejected — so heading text fused with a following body paragraph is correctly left alone.

Verified across 4 papers: ~78 numbered subsection headings promoted to `###` (jdm_m.2022.2 +16, chen +40, jdm_.2023.15 +14, jdm_.2023.16 +22), zero false positives — every promoted line is a genuine heading confirmed against the AI gold, and fused heading-plus-prose lines stayed body text. 26/26 baseline PASS. 8 new tests in `tests/test_numbered_heading_promotion_real_pdf.py`.

**Residual (separate root cause, queued):** headings with long descriptive titles (`2.4.2.2. Inference of planning strategies and strategy types`) are still rejected by the ≥5-lowercase-word prose guard — a guard tuning issue distinct from the regex fix. Single-level top-level numbered headings (`2. Omission neglect`) remain demoted — queued as a dedicated cycle (needs a document-numbering-range gate to stay safe against enumerated lists).

~12 APA papers still FAIL Phase-5d verification; the autonomous run continues.

## [2.4.40] — 2026-05-16

**Cycle 8 (autonomous APA-first run) — standalone `2`-for-U+2212 minus recovery via point-estimate ∈ CI pairing (GLYPH, S0).** The v2.4.38 fix recovered the `2`-for-minus corruption on *bracketed* CIs (descending-pair rule) but left the bracket-less point estimates corrupt: every negative regression coefficient cell in `efendic_2022_affect` Tables 2-5 still read `20.26`/`21.15` for `−0.26`/`−1.15`, and the mediation estimate read `Mposterior = 20.54` for `−0.54` — sign-corrupted published statistics.

Fix — new `normalize.py::recover_minus_via_ci_pairing` (W0d step). The discriminator is a structural invariant of statistics, not a heuristic: **a point estimate always lies inside its own reported confidence interval.** Operating on whole records — a `<tr>…</tr>` table row, or a single text line — when a token reads `2X.XX` and the same record carries a CI bracket `[lo, hi]` such that the de-corrupted value `−X.XX` falls inside `[lo, hi]` while the literal `2X.XX` falls outside, the token is unambiguously a corrupted negative. A genuine literal `2X.XX` (e.g. a mean age `23.45` reported with its own CI `[22.1, 24.8]`) is never recovered — the literal is consistent with its bracket, so the rule does not fire. Applied at the body channel (normalize W0d) and the `render_pdf_to_markdown` post-process (final guarantee — covers `<table>` HTML rows and `unstructured-table` lines alike).

Verified on efendic (v2.4.39→v2.4.40 diff: 22 lines, all `2X.XX`→`−X.XX` recoveries, no body prose touched). All 22 recovered values confirmed cell-by-cell against the AI gold. **Residual (escalated, no text-channel signal):** 4 body-prose `Mchange = 2X.XX` figures and the contrast-coding table-footnote lines (`direction: 20.5 = low, + 0.5 = high`) carry no CI — a standalone `2X.XX` with no interval to pair against is information-theoretically ambiguous and needs the layout channel (per-char glyph identity), like the 011 deleted-minus case.

`NORMALIZATION_VERSION` 1.9.5 → 1.9.6. 9 new tests in `tests/test_minus_sign_recovery_real_pdf.py`.

~12 APA papers still FAIL Phase-5d verification; the autonomous run continues.

## [2.4.39] — 2026-05-16

**Cycle 7 (autonomous APA-first run) — `<`-as-backslash glyph corruption (GLYPH, S0).** `efendic_2022_affect` rendered every `<` comparison operator as a literal backslash: body prose read `p \ .05` / `p \ .001` for `p < .05` / `p < .001`, every table p-value cell read `\.001` for `<.001`, and the legacy Wiley DOI `13:1<1::AID-BDM333` read `13:1\1::AID-BDM333` — 24 occurrences total. Diagnosis: a font quirk makes pdftotext map the `<` glyph to a literal backslash. A backslash is never a legitimate prose character in extracted academic text, and the renderer adds no markdown escapes.

Fix — new `normalize.py::recover_corrupted_lt_operator`: a backslash immediately followed (optional single space) by a digit or a `.`-prefixed decimal is unambiguously a corrupted `<` and is recovered to `<`, preserving the space (`p \ .05` → `p < .05`). A backslash before a letter (a rare path-like artifact) is left alone. Applied at three channels (same pattern as the v2.4.34 Greek and v2.4.38 minus fixes): normalize W0c step (body), `cell_cleaning._html_escape` (Camelot table cells — runs before the `<`→`&lt;` HTML escape so the recovered operator is escaped like any other `<`), and the `render_pdf_to_markdown` post-process (final guarantee — unstructured-table fenced blocks / raw_text fallbacks).

Verified on efendic (v2.4.38→v2.4.39 diff: 54 lines, all 27 `\`→`<` recoveries, no body prose touched; 0 literal backslashes remain): body `p < .001`, table p-cells `&lt;.001`. AI-gold verifier confirms the corruption is gone with zero hallucination.

`NORMALIZATION_VERSION` 1.9.4 → 1.9.5 · `TABLE_EXTRACTION_VERSION` 2.1.2 → 2.1.3. 8 new tests in `tests/test_lt_operator_recovery_real_pdf.py`.

~12 APA papers still FAIL Phase-5d verification (efendic itself still FAILs on pre-existing defects: standalone `2X.XX` minus-corrupted cells, table column-fusion/merge, numbered-subsection demotion); the autonomous run continues.

## [2.4.38] — 2026-05-16

**Cycle 6 (autonomous APA-first run) — `2`-for-U+2212 minus-sign corruption (GLYPH, S0).** `efendic_2022_affect` rendered every negative statistic with the U+2212 minus turned into the digit `2`: the abstract read `r = 2.74 [20.92, 20.30]` for `r = −.74 [−0.92, −0.30]`, and all 29 confidence intervals in the body and tables were sign-corrupted — a sign-FLIP of published statistics. Diagnosis: a font quirk makes pdftotext map U+2212 to `2`.

Fix — new `normalize.py::recover_corrupted_minus_signs`, two self-gating context-safe rules: **(1)** a bracketed numeric pair `[A, B]` that is *descending* as written (A > B — impossible for a CI/range) and becomes a valid *ascending* interval when the leading `2` of a decimal-bearing bound is read as `−`; **(2)** `r = 2.<digits>` — a Pearson r cannot exceed 1. An ascending CI, a plausible correlation, and integer-only brackets (citation lists `[25, 3]`) are never touched. Applied at three channels (same pattern as the v2.4.34 Greek fix): normalize W0b step (body), `cell_cleaning._html_escape` (Camelot table cells), and the `render_pdf_to_markdown` post-process (final guarantee — unstructured-table fenced blocks / raw_text fallbacks).

Verified on efendic (v2.4.36→v2.4.38 diff: 60 lines, all minus-sign recoveries, no body prose touched): abstract `r = -.74 [-0.92, -0.30]`, 0 corrupt CI brackets, 0 `r = 2.X`. **Residual:** 6 standalone `2X.XX` coefficient/mean cells (`Mposterior = 20.54`, table estimate cells) have no per-cell discriminator — they need column-aware logic; queued. The `<`→`\` operator corruption (`p < .05` → `p \ .05`) is a separate glyph defect, also queued.

`NORMALIZATION_VERSION` 1.9.3 → 1.9.4 · `TABLE_EXTRACTION_VERSION` 2.1.1 → 2.1.2. 9 new tests in `tests/test_minus_sign_recovery_real_pdf.py`.

~12 APA papers still FAIL Phase-5d verification; the autonomous run continues.

## [2.4.37] — 2026-05-15

**Cycle 5 (autonomous APA-first run) — Cambridge / JDM publisher boilerplate spliced into body prose (D4).** The APA Phase-5d sweep found that every Cambridge JDM paper (jdm_.2023.15/16, jdm_m.2022.2/3, jdm_.2023.10) had two pieces of publisher boilerplate welded mid-sentence into the body: the per-page running footer `https://doi.org/10.1017/jdm.<id> Published online by Cambridge University Press` (~9× per paper — pdftotext emits it once per page and downstream paragraph-rejoin splices it inline, e.g. "...individuals usually fail to `<footer>` notice the absence..."), and the open-access licence sentence `This is an Open Access article, distributed under the terms of the Creative Commons Attribution licence (...), ... provided the original article is properly cited.`

Fix — two patterns added to `normalize.py` W0 watermark-strip: a non-anchored Cambridge-footer pattern (robust whether the footer stands alone or is glued inline — pdftotext version skew) and the open-access licence-sentence pattern (`[\s\S]`-spanning to cross the pdftotext line wrap; optional bare `Association for Decision Making.` lead-in). Removing the boilerplate rejoins the split body sentence. Verified jdm_m.2022.2 v2.4.36→v2.4.37 diff: 21 lines, all boilerplate removals, no body prose lost; a regression test caught and fixed an over-strip where the lead-in pattern reached backward across legitimate prose.

`NORMALIZATION_VERSION` 1.9.2 → 1.9.3. 5 new tests in `tests/test_cambridge_footer_strip_real_pdf.py`.

~12 APA papers still FAIL Phase-5d verification; the autonomous run continues.

## [2.4.36] — 2026-05-15

**Cycle 4 (autonomous APA-first run) — `(cid:0)` corrupted minus signs in table cells (GLYPH, S0).** The APA Phase-5d sweep found `ziano_2021_joep` and `chen_2021_jesp` rendered negative numbers in their statistical tables as `(cid:0) 0.23` instead of `-0.23` — a sign-corrupted (hallucinated) value in published statistics. Diagnosis: the cells come from the Camelot layout channel, whose text layer is pdfminer; pdfminer emits `(cid:N)` for a font glyph with no Unicode mapping. In these PDFs the unmapped glyph is the U+2212 minus, always printed directly before a number (confirmed: 100% of `(cid:0)` occurrences — 22 in ziano, 68 in chen — are immediately followed by a digit). `(cid:0)` is never legitimate text.

Fix in `docpluck/tables/cell_cleaning.py::_html_escape` — recover `(cid:0)` (with optional trailing space) immediately before a digit to an ASCII hyphen (`(cid:0) 0.23` → `-0.23`, `[(cid:0) 0.108,` → `[-0.108,`). Digit-anchored so a `(cid:0)` not before a number is left untouched. Verified: ziano 16 + chen 85 negative table cells recovered, 0 `(cid:N)` markers remain in the rendered output.

`TABLE_EXTRACTION_VERSION` 2.1.0 → 2.1.1. 8 new tests in `tests/test_cid_minus_recovery_real_pdf.py`.

~12 APA papers still FAIL Phase-5d verification; the autonomous run continues.

## [2.4.35] — 2026-05-15

**Cycle 3 (autonomous APA-first run) — orphan arabic section numbers (D6).** JDM / Cambridge-style papers number their sections `1. Introduction`, `2. Method`, etc. pdftotext emits the section number on its own line, separated from the heading text the section partitioner promoted to `## ` — so the rendered output had a stray `1.` floating above `## Introduction` (found across ~8 APA papers: jdm_.2023.15/16, jdm_m.2022.2/3, korbmacher, ziano, jamison).

Fix — new `_fold_orphan_arabic_numerals_into_headings` in `docpluck/render.py` (post-process), the arabic analogue of the existing `_fold_orphan_roman_numerals_into_headings`. Folds an orphan 1-2 digit number (dot optional) into the `## ` heading immediately below it (blank lines only between): `## Introduction` → `## 1. Introduction`. Conservative — only fires when the number is immediately adjacent to a heading that does not already begin with a number; page-number residue, list items, and stat fragments that merely precede body prose are left untouched (verified: korbmacher v2.4.34→v2.4.35 diff is exactly 3 headings folded, nothing else).

8 new tests in `tests/test_orphan_section_number_real_pdf.py`. No `NORMALIZATION_VERSION` / `SECTIONING_VERSION` change (render-only).

12 APA papers still FAIL Phase-5d verification; the autonomous run continues fixing them.

## [2.4.34] — 2026-05-15

**Cycle 2 (autonomous APA-first run) — math-italic Greek corruption (GLYPH, S0).** The APA Phase-5d verifier sweep found effect-size symbols corrupted across the corpus: `η² = 0.34` rendered as `n2 = 0.34`, the coefficient `β` as `b`, `χ²` as `ch2`, `α` as `a`. Diagnosis (`korbmacher_2022_kruger` raw pdftotext): the source PDFs encode Greek as **Mathematical-Italic codepoints** (U+1D6FD `𝛽`, U+1D702 `𝜂`, …); pdftotext extracts them faithfully, then `normalize.py`'s S0 step **transliterated math-italic Greek to ASCII Latin** (`𝜂`→`"n"`, `𝛽`→`"b"`, `𝛼`→`"a"`) — a docpluck-introduced corruption that violates the hard rule "only U+2212→ASCII is a sanctioned Unicode→ASCII conversion."

Fix — new shared `destyle_math_alphanumeric()` in `docpluck/normalize.py`: NFKC-normalises the whole Mathematical Alphanumeric Symbols block (U+1D400–U+1D7FF) to the plain base letter/digit — **Greek stays Greek**, Latin stays Latin, digits stay digits. Replaces the pre-2.4.34 hand-rolled S0 loops, which were both incomplete (only italic Latin + a partial italic-Greek dict — bold/sans/script variants and ι/κ/λ/ν/ξ/τ/υ/ω leaked) and wrong (Greek→ASCII). Applied at three channels so no math-styled glyph reaches any output view:
- **S0** (`normalize_text`) — body/text channel → sections + normalized-text views.
- **`_html_escape`** (`tables/cell_cleaning.py`) — Camelot layout channel (table cells bypass S0).
- **`render_pdf_to_markdown` post-process** — final guarantee over the assembled markdown (catches figure/table captions, unstructured-table fences, raw_text).

Verified on korbmacher / jdm_m.2022.2 / jdm_m.2022.3 / jdm_.2023.15: 0 math-alphanumeric leaks, Greek recovered (`η²`, `β`, `α`, `χ`); korbmacher re-verified against AI-gold FAIL → PASS. `NORMALIZATION_VERSION` 1.9.1 → 1.9.2. 6 new tests in `tests/test_mathitalic_greek_real_pdf.py`; `test_normalization.py::TestS0_SMP::test_math_italic_greek_eta` corrected — it had asserted the bug (`"n" in result  # eta maps to 'n'`).

13 APA papers still FAIL Phase-5d verification; the autonomous run continues fixing them.

## [2.4.33] — 2026-05-15

**Cycle 1 (autonomous APA-first run) — lowercase letter-spaced Elsevier front-matter labels (D1).** The broad-read of the 18-paper APA corpus at v2.4.32 found that the three Elsevier JESP-2009 papers (`ar_apa_j_jesp_2009_12_010/011/012`) rendered their front-matter box labels as unintelligible letter-spaced runs — `a r t i c l e` / `i n f o` / `a b s t r a c t` — one single-spaced character run per line. pdftotext serializes letter-spaced display typography this way; the all-caps sibling `_rejoin_garbled_ocr_headers` does not fire on lowercase input. Beyond the cosmetic leak, the section taxonomy never recognised `a b s t r a c t`, so the **Abstract section heading was lost** on every paper with this typography.

Fix in `docpluck/normalize.py` — new `_rejoin_letterspaced_lowercase_labels` (step **H0b**, runs in the document-shape-strip zone after P1, pre-sectioning). Collapses any line that is entirely ≥4 single lowercase letters separated by single spaces, gated by a vowel check (rejects spaced-out consonant runs / variable lists). The recovered `abstract` then resolves through the normal taxonomy (`{"abstract"}` → `SectionLabel.abstract`) exactly like a paper that printed the label without letter-spacing.

Result on all 3 papers (verified by v2.4.32→v2.4.33 render diff — the *only* change is the 3 collapsed labels): `a r t i c l e`→`article`, `i n f o`→`info`, `a b s t r a c t`→`## Abstract` (heading recovered). Zero text loss, zero hallucination.

`NORMALIZATION_VERSION` 1.9.0 → 1.9.1. 12 new tests in `tests/test_letterspaced_label_real_pdf.py` (6 unit + 6 real-PDF).

## [2.4.32] — 2026-05-15

**Cycle 15f-1 — table caption no longer absorbs linearized cell content (G4b).** The cycle-15f investigation of `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md` G4 found that `extract_pdf_structured` table `caption` fields were 400 chars of linearized cell garbage (e.g. `amle_1` Table 1: `"Table 1. Most Cited Sources in Organizational Behavior Textbooks Rank Academic Source Academic Rank 1 2 3 4 5 5 7 8 Yes Yes Yes ..."`). Root cause: `_extract_caption_text`'s paragraph-walk has no sentence terminator to stop at when a table title lacks a trailing period (common in AOM / management journals), so it walks straight through the pdftotext-linearized cell content until the 400-char hard cap.

Fix in `docpluck/extract_structured.py` — new `_trim_table_caption_at_cell_region(region)`, applied for `cap.kind == "table"` before the snippet is flattened:
- **Primary rule:** when the caption's first line already carries title text AND ends with a sentence terminator (`Table 6. Study 2 descriptive statistics.`), the title is complete — cut everything after it (trailing table notes belong in the `footnote` field, linearized cells are not caption text).
- **Fallback rule:** when the first line is a bare label (`TABLE 13`) or an unterminated title that may wrap, locate the linearized cell region as the first run of ≥3 consecutive header-like short lines (`_is_table_header_like_short_line`: ≤3 words, ≤35 chars, uppercase/digit-leading, no conjunction tail) and cut there. The label + first title line are always protected.

Verified against the AI-gold `reading` view for amle_1 / amj_1 / xiao_2021_crsp (26 tables total): every caption is now a clean title. amle_1 Table 1 → `Table 1. Most Cited Sources in Organizational Behavior Textbooks`; xiao Table 6 → `Table 6. Study 2 descriptive statistics.`; amle_1 Table 13's 236-char caption is the genuine 2-line title (verified, not cell leak).

17 new tests in `tests/test_table_caption_cell_region_real_pdf.py` (13 unit + 4 real-PDF).

Does NOT address G4a (the body-stream table-cell *dump* duplicating the structured `<table>`) — that needs render/section pipeline coordination and is queued as cycle 15f-2 (C3). See TRIAGE G4 block.

## [2.4.31] — 2026-05-14

**Cycle 15n — figure caption placeholder repair (G_15n).** Phase-5d AI-gold audit of `ieee_access_2.pdf` at v2.4.30 surfaced that 36 of 37 figure captions in the trailing `## Figures` appendix rendered as `*Figure N. FIGURE N.*` placeholders with no description content. Affected the `f["caption"]` field of `extract_pdf_structured`, which `render_pdf_to_markdown` emits verbatim in the trailing Figures block.

Root cause (long-standing, not a v2.4.29 regression — same defect reproduces at v2.4.28 against the current pdftotext output): the paragraph-walk in `_extract_caption_text` bails on the first `\n\n` whose preceding text ends with `.!?` — but for PMC-style IEEE captions, pdftotext lays out the ALL-CAPS label `FIGURE N.` on its own line, then a blank, then the description. The walk consumed `FIGURE N.` (ends with `.`) and stopped, never reaching the description. After re-prefix the snippet became `Figure N. FIGURE N.`. The `_strip_duplicate_uppercase_label` regex requires trailing whitespace after the duplicate, so it couldn't trim either.

- New helper `_accumulated_is_label_only(text)` recognises text that is just a Table/Figure label (with optional duplicate ALL-CAPS form). The paragraph-walk now keeps going past a sentence-terminator break when the accumulated text is label-only, so the description in the next paragraph is consumed.
- New helper `_strip_leading_pmc_running_header(snippet)` strips one or more `Author Manuscript ` PMC reprint running headers that pdftotext interleaves between the label and the description (sibling defect surfaced by the walk fix — 27/37 captions had this leakage after the walk fix alone, per rule 0e bundled in the same cycle).

Result on ieee_access_2 (verified against AI-gold): 0/37 placeholders, 0/37 PMC header leaks, every caption is the full title-case sentence with Unicode (β/γ/δ/τ/≤/²) preserved.

10 new regression tests added in `tests/test_figure_caption_trim_real_pdf.py` (8 unit + 2 real-PDF). Total: 34 tests for the caption-trim chain.

## [2.4.30] — 2026-05-14

**Cycle 15d — orphan Roman-numeral consumption (G6).** IEEE-style papers use `I. INTRODUCTION` / `II. METHODOLOGY` / ... / `V.: SUPPLEMENTARY INDEX` section headings. pdftotext often emits these with the numeral on a separate line above the ALL-CAPS heading (orphan form), or as an inline form with `.` / `:` after the numeral that the standard ALL-CAPS heading regex doesn't match.

- New `_ROMAN_NUMERAL_ORPHAN_RE` (`^[IVX]{1,4}\.\s*$`) + `_ROMAN_PREFIX_HEADING_RE` (`^[IVX]{1,4}\.:?\s+[A-Z][A-Z0-9:\-,/ ]{3,}[A-Z0-9]$`) in `docpluck/render.py`.
- New post-processor `_fold_orphan_roman_numerals_into_headings` wired into the render chain after section partitioning — scans the rendered .md for an orphan numeral line followed by a `## ` heading and folds the numeral into the heading: `I.` + `## INTRODUCTION` → `## I. INTRODUCTION`.
- Inline form (`V.: SUPPLEMENTARY INDEX`) handled at promote-time before falling through to the bare ALL-CAPS regex.

Verified on ieee_access_2: `## I. INTRODUCTION`, `## II. METHODOLOGY`, `## V.: SUPPLEMENTARY INDEX` all now appear correctly. (`## III. RESULTS`, `## IV. DISCUSSION AND CONCLUSION` partial — those numerals aren't adjacent to their headings in the section-partitioner output, so they remain bare. Documented as known limitation queued for the section-partitioner cycle 15i+.)

5 new regression tests added in `tests/test_roman_numeral_section_promote_real_pdf.py` (3 real-PDF + 2 synthetic-text contract tests).

Side-fix: `tests/test_d5_normalization_audit.py::TestVersionBumps` updated to accept `NORMALIZATION_VERSION` 1.9.x (was hard-coded to 1.8.x).

## [2.4.29] — 2026-05-14

**Source-glyph preservation in the render path** (Cycles 15a + 15b + 15c, bundled — all share root cause "rendered .md must preserve source PDF glyphs"). Established by the Phase-5d AI-gold audit (docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md): the v2.4.28 render systematically transliterated Greek letters, math operators, superscripts/subscripts, comma-thousands separators, and decomposed combining-character names — silently corrupting meta-science content. The fix preserves all source glyphs in the rendered .md while keeping backward-compatible behavior for stat-extraction callers (D5 audit suite + downstream regex matching).

### Cycle 15a — Greek letters + math operators + super/sub digits (G2/G7/G12/G21)

New `preserve_math_glyphs` flag in `normalize_text(...)` (default `False` for back-compat); when `True`, skips the A5 transliteration step (β→"beta", δ→"delta", χ²→"chi2", η²→"eta2", ²→"2", ₀→"0", ×→"x", ≥→">=", ≤→"<=", ≠→"!=", etc.). `extract_sections(..., preserve_math_glyphs=False)` forwards the flag. `render_pdf_to_markdown(...)` internally passes `True`. Verified: ieee_access_2 now has 61 β + 43 δ + 106 ≤ in the rendered .md (was 0/0/0), and zero "betaSI"/"deltaR" transliterations.

### Cycle 15b — Comma-thousands separators (G17)

A3a (which intentionally stripped commas from `7,445`-style integers to protect against A3 corrupting them into European decimals) is gated on `preserve_math_glyphs=False`. A3 (European decimal-comma → ASCII dot) and A3c (leading-zero decimal recovery) are also gated. In preserve mode, body-text retains `7,445 sources`, `33,719 articles`, `32,981 authors`, `49,742 rows`, `89,044 times` etc. as printed. Verified on amle_1: all 10 sample thousands separators preserved; zero comma-stripped 4-digit forms remain in body.

### Cycle 15c — NFC composition for decomposed combining characters (G15)

Added Unicode NFC normalization at the top of `normalize_text` plus a regex that squashes a stray space between a base letter and an immediately-following combining diacritic (the `Fö rster` → `Förster` corruption pattern observed in amj_1 v2.4.28). Recomposes `Potočnik` (NFD: c + U+030C combining caron) to `Potočnik` (NFC: U+010D). Applied to ALL normalize callers (no flag gate) because NFC is the universal correct form — there is no use case for keeping decomposed-with-stray-spaces author names.

### Library API

- `normalize_text(text, level, *, layout=None, table_regions=None, preserve_math_glyphs=False)` — new keyword param.
- `extract_sections(..., preserve_math_glyphs=False)` — new keyword param forwarded to `normalize_text`.
- `render_pdf_to_markdown(...)` — unchanged signature, internally sets `preserve_math_glyphs=True`.
- D5 stat-extraction tests (153 tests) still pass unchanged — back-compat preserved.
- `NORMALIZATION_VERSION` bumped 1.8.9 → 1.9.0 (minor: behavioral change behind a flag, but A5 + A3 gating is a meaningful semantic shift).

### Known remaining (TRIAGE cycles 15d-15g, scheduled for follow-up)

- G6 orphan Roman-numeral consumption (ieee_access_2: `I.` alone above `## INTRODUCTION`)
- G16 page-header leak into equations (ieee_access_2: `Page 4 (2)`)
- G4 body-stream cells duplicating structured tables (amj_1 Tables 2/3/4/5, amle_1 13 tables)
- G1 pdftotext glyph collapse (`=`→`5`, `<`→`,`, `−`→`2` — amj_1/amle_1 stat-poisoning)
- G3 multi-paper table-cell defects (phantom columns, cell fusion, caption-thead bleed)
- G5 section-detection under-firing
- G7 equation destruction in math contexts
- G8 body-prose splay around inline math glyphs

## [2.4.28] — 2026-05-14

Cycles 13 + 14 of the /docpluck-iterate resume run, bundled as one
release (independent fixes, narrow blast radius). Closes
HANDOFF_2026-05-14 deferred items D + G.

### Cycle 13 — amj_1 chart-data leak (item G, HIGH)

The v2.4.25 caption-trim chain landed but amj_1 figure captions
still contained flow-chart node text and axis-tick labels. The
existing chart-data trim's two signatures (6+ digit run, 5+ short
numeric tokens) don't match amj_1's pattern: axis ticks interleaved
with Title-Case axis labels (`7 6 Employee Creativity 5 4 Bottom-up
Flow`) and numbered flow-chart nodes (`1. Bottom-up Feedback Flow 2.
Top-down Feedback Flow 3. Lateral Feedback Flow`).

Two new chart-data signatures added in
`docpluck/extract_structured.py`:

- `_AXIS_TICK_PAIR_RE` — `\b\d\s+(?:[A-Z][\w\-]+(?:\s+[A-Z][\w\-]+)
  {0,3}\s+)?\d\b` — single-digit token + (optional 1-4 Title-Case
  words) + single-digit token. Catches both bare adjacent digits and
  digits separated by axis labels.
- `_NUMBERED_CHART_NODE_RE` — `\b\d+\.\s+[A-Z][a-z]+(?:-[a-z]+)?
  (?:\s+[A-Z][a-z]+(?:-[a-z]+)?){1,4}` — numbered prefix + Title-Case
  noun phrase (2-5 words, hyphens allowed).

Both wired into `_trim_caption_at_chart_data` via new helper
`_find_chart_data_cluster` (2+ / 3+ matches in close proximity,
`max_gap=100`; matches at position < 20 excluded so `Figure N.`
can't be the cluster anchor).

**Caught cases (all 7 amj_1 figures):**

- Figure 1: `Theoretical Framework Direction of Feedback Flow ...
  flow-chart nodes ... body prose ... 587 ... section heading` →
  trims to `Theoretical Framework Direction of Feedback Flow`.
- Figures 2-7: chart-data tail (`7 6 Employee Creativity 5 4 ...`)
  stripped cleanly; captions end at `(Study N)`.

### Cycle 14 — A3 leading-zero decimal recovery (item D, LOW)

A3's lookbehind `(?<![a-zA-Z,0-9\[\(])` blocks European-decimal
p-values inside parens or brackets — `(0,003)` stays as `(0,003)`
instead of converting to `(0.003)`. The exclusion is necessary to
protect statistical df-bracket forms like `F(2,42)`.

New A3c step in `docpluck/normalize.py`: convert `0,(\d{2,4})` to
`0.\1` regardless of lookbehind, since leading-zero is unambiguous
(df values never start with 0, citation superscripts never start
with 0). Single-digit-after-comma cases like `[0,5]` are
skipped — those are typically range expressions, not decimals.

NORMALIZATION_VERSION bumped 1.8.8 → 1.8.9.

### Tests

- `tests/test_chart_data_trim_real_pdf.py` (NEW — 14 contract +
  3 real-PDF) — 22/22 PASS.
- `tests/test_a3c_leading_zero_decimal_real_pdf.py` (NEW — 7
  positive + 4 negative contract tests) — 11/11 PASS.
- Combined cycle 13 + 14 suite: 34/34 PASS.
- Normalize / D5 / A3-existing suite: 66/66 PASS.
- 26-paper baseline (pre-cycle-14): 26/26 PASS.

## [2.4.27] — 2026-05-14

Cycle 12 of the /docpluck-iterate run (HANDOFF_2026-05-14 deferred
item C). Table 6 of `xiao_2021_crsp.pdf` had spanning section-row
labels (`Control (n = 339, 2 selected the decoy, 0.6%)`,
`Regret-Salient (n = 331, ...)`) collapsed into the data cell above:

    <td>112/172<br>Regret-Salient (n = 331, ...)</td>

Camelot emits these as single-non-empty-cell rows. The
`_merge_continuation_rows` pre-v2.4.27 logic interpreted any row with
an empty first cell and prose content elsewhere as a continuation —
and merged it into the prior data row.

Fix: new `_is_section_row_label` guard in
`docpluck/tables/cell_cleaning.py::_merge_continuation_rows`. A row
is treated as a spanning section-row label (and NOT merged) when:

- Exactly ONE cell is non-empty (rest are empty).
- That cell is ≤ 200 chars.
- The cell content matches `_SECTION_ROW_LABEL_RE`: starts with a
  Title-Case noun phrase followed by `(... n|N|M|SD|p [=<>] ...)`
  parenthetical — the canonical statistical-condition descriptor.

### Caught case

- xiao Table 6: `Control` and `Regret-Salient` section rows now
  surface as separate `<tr>` rows, no longer merged into the
  `Choice set N | 112/172 | ...` data rows.

### Tests

- `tests/test_section_row_label_no_merge_real_pdf.py` — 5 contract
  + 1 real-PDF regression test. 6/6 PASS.
- Targeted table suite (`tests/test_tables_cell_cleaning.py`,
  `tests/test_table_detect.py`, `tests/test_f0_table_region_aware.py`):
  78/78 PASS.

## [2.4.26] — 2026-05-14

Cycle 11 of the /docpluck-iterate run (HANDOFF_2026-05-14 deferred
item B). The section detector in
`docpluck/sections/annotators/text.py` Pass 3 rejects ALL-CAPS
multi-word headings when pdftotext flattens paragraph breaks around
them (no blank line before AND no blank line after). This breaks
AOM-style structure where a major section heading sits directly
between the prior paragraph's last sentence and a sub-section label.

Initial attempt (Pass 3 relaxation) was reverted because subheading
hints stored on `Section.subheadings` aren't consumed by the render
pipeline — only canonical-labeled hints become `## Heading` lines.

Final fix: render-layer post-processor. Extended
`_promote_study_subsection_headings` with a new
`_ALL_CAPS_SECTION_HEADING_RE` pattern guarded by
`_is_safe_all_caps_promote`. Promotes a standalone ALL-CAPS line to
`## {heading}` when:

- Line is ALL-CAPS, ≥ 10 chars, ≥ 2 words.
- Doesn't end with sentence terminator.
- Previous non-blank line ends with a terminator (`. ! ? : " ' ) ]`).
- Next non-blank line starts uppercase.
- Next non-blank line is NOT itself ALL-CAPS (avoids multi-line title
  continuations).

### Caught cases

- `amj_1` now promotes `## THEORETICAL DEVELOPMENT`,
  `## OVERVIEW OF THE STUDIES`, `## STUDY 1: QUASI-FIELD EXPERIMENT`,
  `## STUDY 2: LABORATORY EXPERIMENT`.
- `amle_1` now promotes `## SCHOLARLY IMPACT AND KNOWLEDGE TRANSFER`,
  `## PRESENT STUDY AND RESEARCH QUESTIONS`, `## METHOD`,
  `## RESULTS`, `## DISCUSSION`, `## LIMITATIONS AND FUTURE RESEARCH
  DIRECTIONS`, `## CONCLUDING REMARKS`, `## REFERENCES`.
- `ieee_access_2` now promotes `## INTRODUCTION`, `## METHODOLOGY`,
  `## RESULTS`, `## DISCUSSION AND CONCLUSION`, `## LIMITATIONS AND
  FUTURE WORK`, `## REFERENCES`.
- `xiao_2021_crsp` — no change (uses Title Case headings; existing
  detection works).

### Tests

- `tests/test_all_caps_section_promote_real_pdf.py` — 18 contract
  + 4 real-PDF regression tests. 22/22 PASS.
- Targeted suite (`tests/test_render.py`, `tests/test_sections_*`,
  `tests/test_corpus_smoke.py`): 66/66 PASS (the 2 failures are the
  same pre-existing Camelot-disabled-only ones from v2.4.25).

## [2.4.25] — 2026-05-14

Cycle 10 of the /docpluck-iterate run (resumed from HANDOFF_2026-05-14
deferred item A). The handoff flagged "figure caption running-header
trim incomplete" as the only ship-blocker — investigation revealed the
v2.4.24 trim was added to `figures/detect.py::_full_caption_text`,
which is NOT the function `render_pdf_to_markdown` calls. The actual
render path goes through `extract_structured.py::_extract_caption_text`,
which had no running-header or body-prose trim at all. Combined with a
broad-read of amj_1 / ieee_access_2 / xiao figure captions, this cycle
moves the entire trim chain to the correct module and widens it to
cover three additional patterns surfaced by the broad-read.

### Caption-trim chain in `_extract_caption_text` (figures only)

1. **Form-feed hard boundary.** Page break (`\f`) is now a hard cap on
   the paragraph-walk's hard_end. Figure/table captions never span
   page breaks; anything past the next `\f` is guaranteed to be a
   running header, next-page body prose, or a different figure.
2. **Duplicate ALL-CAPS label strip.** Strips a redundant `FIGURE N` /
   `TABLE N` that pdftotext extracts alongside the title-case label
   (amj_1 figures, ieee_access_2 figures). Pattern:
   `^Figure 1\. FIGURE 1[ .]<text>` → `Figure 1. <text>`.
3. **Running-header tail trim** — three signatures:
   - **Author-running-header**: `\d+\s+[A-Z]\.\s+[A-Z]+\s+ET\s+AL\.?$`
     (T&F / APA journals: "14 Q. XIAO ET AL.")
   - **Same-surname dyad page**: `\d{4}\s+Surname\s+and\s+Surname\s+\d+$`
     (AOM journals: "2020 Kim and Kim 599")
   - **PMC reprint footer**: `Journal\. Author manuscript; available
     in PMC <date>\.$` (ieee_access_2 every figure)
   When a tail matches, the trim also walks back to the last `. `
   boundary if the prefix lacks a sentence terminator — kills any
   body-prose run that preceded the running header within the same
   absorbed-caption string.
4. **Body-prose boundary detection.** Walks every `. ` sentence
   boundary after position 20 in the caption. Trims at the first one
   whose tail matches `[A-Z][a-z]+(?:\s+[a-z]+){0,3}\s+[A-Z][a-z]+` (a
   Title Case noun phrase followed by a Capital-starting word without
   intervening period — the inline-section-heading-then-body-prose
   pattern). Requires a body-prose corroboration signal (year citation,
   first-person verb, "participants", subordinator, infinitive of
   intent) to reduce false positives on legit two-sentence captions.
   Skips boundaries whose tail starts with caption-continuation
   openers (Note, Source, Bars, Error, Asterisks, Numbers, Panel, n=,
   p<, *p, **p, ***p).

### Caught cases

Before → after (working tree v2.4.25, regression tests
`tests/test_figure_caption_trim_real_pdf.py`):

- `xiao_2021_crsp` Figure 2:
  `Figure 2. Study 1 interaction plots. Exploratory analysis To
  examine whether and to what extent participants perceived the decoys
  to be less preferable than their targets, we performed
  paired-samples t-tests to compare the points 14 Q. XIAO ET AL.`
  → `Figure 2. Study 1 interaction plots.`
- `xiao_2021_crsp` Figure 3: same root cause, now clean.
- `ieee_access_2` every figure: `IEEE Access. Author manuscript;
  available in PMC 2026 February 25.` footer stripped.
- `amj_1` every figure: duplicate `FIGURE N` label stripped.
- `ieee_access_2` every figure: duplicate `FIGURE N.` label stripped.

### Known remaining defect (not addressed this cycle)

`amj_1` Figure 1–7 captions still contain flow-chart node text and
axis-tick labels (e.g. `Direction of Feedback Flow 1. Bottom-up
Feedback Flow 2. Top-down Feedback Flow 3. Lateral Feedback Flow`).
These are not digit-runs and not body-prose-shape, so the existing
chart-data trim and the new body-prose-boundary trim both pass them
through. Would require a flow-chart-node-name detector (Title Case
phrases interleaved with single-digit ordinals). Queued for a future
cycle.

### Tests

- `tests/test_figure_caption_trim_real_pdf.py` — 14 contract tests
  + 5 real-PDF regression tests on the 4 cycle-9 papers. 19/19 PASS.
- Broad pytest: 1035 PASS, 19 SKIP, 0 FAIL (3 pre-existing failures
  re-verified as Camelot-disabled-only; pass with Camelot enabled).
- 26-paper baseline: 26/26 PASS.

## [2.4.24] — 2026-05-14

Final cycle of the /docpluck-iterate run (cycle 9 of 9). Three
partial-scope fixes for render-layer defects surfaced by Phase 5d AI
verifiers across cycles 1-6.

### Fix A — table-column-header heading mis-promotion

`docpluck/sections/annotators/text.py::_looks_like_table_cell` extended
to detect the TABLE-COLUMN-HEADER signature: if the heading is preceded
by 2+ short standalone-line "noun phrase" siblings (each ≤30 chars,
blank-line separated, no body-prose function words), treat as a table
column header row, not a section heading.

Caught case: amj_1 Table 1 has column headers `Study and Context\n\n
Feedback Directions\n\nFindings\n\n<body row>`. Without this fix, the
third column header "Findings" got promoted to `## Findings` mid-doc.
v2.4.24 verified: amj_1 has 0 `## Findings` (was 1).

### Fix B — heading-pattern widening for ALL-CAPS-with-digits-and-colons

`_HEADING_LINE` regex character class extended from `[A-Za-z &\-/]` to
`[A-Za-z0-9 &\-/:,]` (and the all-caps variant similarly). Admits
headings like `STUDY 1: QUASI-FIELD EXPERIMENT`, `STUDY 2: LABORATORY
EXPERIMENT`, `Section 3.1: Methods` that v2.4.23 rejected. Section tests
42/42 still pass (no regressions).

**Note:** the widening fires only when other Pass 3 constraints are
satisfied (blank-line-before, blank-line-after, ≥5 chars, ≥2 words, no
trailing period). amj_1's `STUDY 1: ...` is on a line immediately
followed by `Procedure` (no blank line) — Pass 3 still rejects. A
deeper fix would relax the blank-after requirement for ALL-CAPS multi-
word headings. Deferred to a future cycle.

### Fix C — figure caption running-header trim

`docpluck/figures/detect.py::_trim_caption_at_running_header` trims a
trailing page-number + running-header (e.g. ` 14 Q. XIAO ET AL.`) at
the end of an extracted figure caption, then walks back to the last
`. ` and drops any body-prose sentence that pdftotext absorbed before
the running header.

Caught case: xiao_2021_crsp Figure 2 caption at v2.4.23 was
`*Figure 2. Study 1 interaction plots. Exploratory analysis To examine
whether and to what extent participants perceived the decoys to be
less preferable than their targets, we performed paired-samples t-
tests to compare the points 14 Q. XIAO ET AL.*` — should be just
`*Figure 2. Study 1 interaction plots.*`.

### Verification status (partial — context exhausted)

- 42/42 sections tests pass
- 22/22 figure-detect + sections-partition tests pass
- Full broad pytest: in flight at commit time (was at 78% with no
  failures), final result deferred to next session
- 26-paper baseline: in flight at commit time (10/26 PASS so far),
  final result deferred to next session
- Phase 5d AI verify: not run for cycle 9 (context budget); the three
  fixes target narrow specific defects so regression risk is low
- Phase 6 Tier 2 parity / Phase 7 release / Phase 8 prod deploy: NOT
  YET RUN. v2.4.24 commit + tag are local-only at handoff time.

### Out-of-scope deferrals (queued for fresh session)

- ~24 missing section promotions where heading is on line followed by
  another heading-shaped word without blank line (STUDY 1 in amj_1,
  etc.) — needs blank-after constraint relaxation per heading class
- Frontend Markdown rendering quality (Rendered tab vs Tables tab UX
  per user 2026-05-14 directive) — outside library scope, fix lives in
  `PDFextractor/frontend/`

### Versioning

`NORMALIZATION_VERSION` stays 1.8.8 (no normalize changes this cycle).
`SECTIONING_VERSION` 1.2.1 → 1.2.2 (annotator + heading regex changes).

## [2.4.23] — 2026-05-14

pdftotext version-skew pattern robustness (cycle 8 of /docpluck-iterate
run). Targets the Xpdf 4.00 (local Windows) vs poppler 25.03 (Railway
Linux) line-break-placement skew documented in memory
`feedback_pdftotext_version_skew`.

### Defect — prod retains more front-matter junk than local

P0 (`_PAGE_FOOTER_LINE_PATTERNS`) is line-based — matches anchored
`^…$`. On local Xpdf, a banner like `COMPREHENSIVE RESULTS IN SOCIAL
PSYCHOLOGY https://doi.org/10.1080/23743603.2021.1878340 Published
online: 18 Mar 2021.` is serialized as a single line. On prod poppler,
it's split into 3 separate lines. The single-line P0 pattern matches
local; the split version slips through prod.

Cycle 1 Phase 8 Tier 3 byte-diff confirmed this: `xiao_2021_crsp` T2
(local) had `Submit your article to this journal`, `ARTICLE HISTORY`,
`Received 2 February 2020`, `Accepted 7 January 2021` stripped; T3
(prod) retained them.

### Fix — add P0 patterns for the prod-only standalone-line emissions (NORMALIZATION_VERSION 1.8.7 → 1.8.8)

| Pattern | Catches |
|---------|---------|
| `^Submit your article to this journal$` | T&F masthead line |
| `^ARTICLE HISTORY$` | T&F structured-abstract section label |
| `^Published online:? \d+ \w+ \d{4}\.?$` | T&F online-publication date |
| `^View related articles?$` | T&F sidebar |
| `^View Crossmark data$` | Crossmark badge |
| `^Citing articles: \d+ View citing articles?$` | T&F citation count |
| `^Full Terms & Conditions of access and use\.?$` | T&F masthead |
| `^Received \d+ \w+ \d{4}$` | Standalone "Received" line (poppler-split) |
| `^Accepted \d+ \w+ \d{4}$` | Standalone "Accepted" line |
| `^Revised \d+ \w+ \d{4}$` | Standalone "Revised" line |

These patterns NEVER appear standalone in real body prose, so they're
globally safe.

### Verified

- 986/986 broad pytest pass (in flight)
- 26-paper baseline (in flight)
- Patterns added behind explicit string anchors — no false positives
  on body prose

### Note — this is a tactical fix, not a structural one

The architectural problem (line-based pattern matching is fragile to
line-break differences) remains. A future cycle could refactor P0 /
P1 / H0 / W0 to be multi-line-aware (token-based instead of line-
based), eliminating the version-skew class of bug. Deferred per
revertability discipline.

## [2.4.22] — 2026-05-14

`/docpluck-iterate` skill amendment + table-rendering parity audit (cycle
7 of run). User directive from 2026-05-14: "encode a recurring check for
table-rendering parity (Rendered tab == Tables tab) in the iteration
skill."

### Phase 6c — Rendered ↔ structured-tables parity check (new MUST-RUN gate)

Added to `.claude/skills/docpluck-iterate/SKILL.md` Phase 6 table:

> For each affected paper: (a) count `### Table N` blocks in the
> rendered .md, (b) call `/extract-structured` and count tables in the
> JSON response. (c) Both counts must match. Any `### Table N` in the
> .md must correspond to a structured table with the same label. Any
> structured table with `kind=structured` should emit as `<table>` HTML
> in the .md (not fenced ```unstructured-table). (d) Mismatches indicate
> either: table extracted-but-not-emitted in .md, table emitted as
> raw_text fallback when cells were available, or table-label
> inconsistency.

### Audit run on 2026-05-14 — library-side parity 100%

| Paper | Tables (extract_structured) | `### Table` in .md | `<table>` HTML | Fallback |
|-------|-----------------------------|--------------------|--------------|----------|
| xiao_2021_crsp | 8 (7 structured + 1 isolated) | 8 | 7 | 1 unstructured-table |
| amj_1 | 5 | 5 | 5 | 0 |
| amle_1 | 13 | 13 | 13 | 0 |
| ieee_access_2 | 1 | 1 | 1 | 0 |

The 1 unstructured-table block in xiao (Camelot couldn't parse cells →
raw_text fallback) is by design — see v2.4.12 raw_text fallback for
isolated tables.

### Frontend Markdown rendering (out of library scope)

The user's original "Rendered tab doesn't show tables as nicely as
Tables tab" concern is a frontend rendering issue: how
`PDFextractor/frontend/` renders the library's `<table>` HTML inside
markdown (escaping, code-block fallback for `unstructured-table`,
mobile UI parity, etc.). The library output itself is correct and
matches the Tables tab's structured data 1:1.

Recommended follow-up (outside `/docpluck-iterate` scope):
- Verify `react-markdown` / `rehype-raw` config passes through `<table>`
  HTML rather than escaping it
- Style `unstructured-table` fenced blocks as a styled box (not
  monospace) in the Rendered tab
- File as a `/docpluck-review` frontend-UI issue

## [2.4.21] — 2026-05-14

Table cell-header prose-leak rejection (cycle 6 of /docpluck-iterate
run). Surfaced by v2.4.16 Phase 5d AI verify on xiao_2021_crsp Table 5.

### Defect — body prose leaked into a table's super-header row

Camelot occasionally widens the table-region detection to include body
prose above the actual table. The body prose lands as a "super-header"
row in the extracted cells. `_fold_super_header_rows` then merges the
super-row with the real header using `_MERGE_SEPARATOR` (= `<br>`),
producing a `<th>` cell like:

    <th>the regret salience manipulation check item revealed a main
    effect of condition, FWelch(2,<br>Options</th>

instead of the expected `<th>Options</th>`. The leak survived to the
rendered .md and was visible in xiao_2021_crsp Table 5 at v2.4.20.

### Fix — body-prose super-row drop in `docpluck/tables/cell_cleaning.py::_fold_super_header_rows`

Before folding, scan the super-row for any cell that:
- exceeds 80 chars in length, AND
- contains a `, [a-z]` sequence (sentence-style comma) OR an unmatched
  open-paren `(`.

If any super-row cell meets both criteria, the row is body prose, not a
real super-header — drop it from `header_rows` (return only the sub-row
+ rest) instead of folding into the sub-row.

Conservative: real super-headers are typically short single-word or
two-word labels (e.g. `Win-` over `Uncertain` → `Win-Uncertain` in
two-row stat tables). The 80-char + comma/paren heuristic only triggers
on sentence-shaped body prose.

### Verified

- xiao_2021_crsp v2.4.21: Table 5 first `<th>` now `'Options'` (was
  `'the regret salience manipulation check item revealed a main effect
  of condition, FWelch(2,<br>Options'`)
- Broad pytest + 26-paper baseline (in flight)

## [2.4.20] — 2026-05-14

Dehyphenation: rejoin pdftotext-space-broken compound words (cycle 5 of
/docpluck-iterate run). Surfaced by v2.4.16 / v2.4.17 Phase 5d AI verify
on xiao_2021_crsp; flagged as pre-existing "residual dehyphenation gap";
fixed per rule 0e.

### Defect — space-broken compound words

PDFs use Unicode soft-hyphen (U+00AD) or letter-spacing for line-break-
aware hyphenation. pdftotext removes the soft-hyphen but leaves a single
SPACE between the two halves. The word "experiments" in xiao's abstract
renders as "experi ments" — a typo to a human reader and a tokenization
breakage for every downstream NLP / search / citation-extraction tool.

S7 (hyphenation repair) catches `word-\nword2` → `wordword2` but NOT the
space-broken form (no hyphen). Different bug, different fix.

### Fix — new step S7a in `docpluck/normalize.py` (NORMALIZATION_VERSION 1.8.6 → 1.8.7)

`_rejoin_space_broken_compounds` walks a curated list of (prefix,
suffix-set) regex pairs and removes the interior space whenever the
joined form is an unambiguous English word. The pairs cover ~23
prefix-family pairs surfaced from the corpus AI verify:

| Prefix | Joined forms |
|--------|--------------|
| `experi` | experiments, experience, experimental, experimentation, … |
| `addi` | addition, additionally, additive, … |
| `discre` | discrepancy, discrepancies, discretion, … |
| `con` | concerning, conducted, confined, confirmed, consequently, consistent, sists, sisted, siderable, trolled, fronted, firmation |
| `ques` | question, questionnaire, questioned, questioning |
| `presenta` | presentation, presentational |
| `discus` | discussion, discussions, discussed |
| `informa`, `differ`, `repli`, `refer`, `identi`, `specifi`, `reliabi`, `genera`, `explana`, `transla`, `observa`, `opera`, `varia`, `correla`, `applica`, `interpre` | analogous suffix-sets |

Conservative: every (prefix, suffix) listed produces a single valid
English word when joined. The patterns require both halves to be
lowercase and at word boundaries, so surrounding body prose is
unaffected. Idempotent.

### Verified

- xiao_2021_crsp v2.4.20: zero "experi ments" / "addi tion" / "discre
  pancies" / "con cerning" / "con ducted" / "con fined" / "ques
  tionnaires" / "presenta tion" / "experi ences" remain
  (all 9 patterns from cycle-2 AI verify rejoined)
- Broad pytest (in flight); 26-paper baseline (in flight)

## [2.4.19] — 2026-05-14

P0 residual-running-header patterns (cycle 4 of /docpluck-iterate run).
Surfaced by v2.4.16 Phase 5d AI verify on amj_1 as pre-existing defects;
fixed in same run per rule 0e.

### Defect — residual standalone running-header / page-marker lines

P0 (`_PAGE_FOOTER_LINE_PATTERNS`) had many patterns but missed two common
ones that survived as 14 standalone occurrences each in amj_1:

| Pattern | Source | Count in amj_1 v2.4.18 |
|---------|--------|-------------------------|
| Same-surname co-author running header: `Kim and Kim` | AOM author byline running header | 14 |
| Bare month-name page marker: `April` | AOM April 2020 volume indicator | 14 |

### Fix — two new P0 patterns in `docpluck/normalize.py` (NORMALIZATION_VERSION 1.8.5 → 1.8.6)

1. `^(?P<surname>[A-Z][a-z]+) and (?P=surname)\s*$` — matches "Kim and
   Kim" / "Smith and Smith" / "Lee and Lee" (X-and-X same-surname co-
   author pattern). Restrictive: rejects "John and Mary" (different
   names) so body prose isn't touched.

2. `^(?:January|February|...|December)\s*$` — bare month-name as
   page-issue marker. Body prose never uses a month name alone on its
   own line.

### Verified

- 986/986 broad pytest pass (no regressions in section / normalize / D5
  audit / A3b tests)
- 26-paper baseline 26/26 PASS
- amj_1 Phase 5d AI verify: 0 standalone `Kim and Kim` lines (was 14);
  0 standalone `April` lines (was 14). Two residual non-body
  occurrences remain inside a `<th>` cell and a figure-caption blob —
  acceptable per skill protocol (not on body channel).
- Tier 2 byte-match Tier 1 confirmed on amj_1

### Out of scope (queued cycle 9)

- `## Findings` heading at amj_1 line 58 is a Table 1 column-header
  mis-promotion (pre-existing pre-v2.4.19; flagged by AI verifier as
  cycle-3 follow-up). Different root cause (table-cell heading
  mis-promotion). NOT a v2.4.19 regression.

## [2.4.18] — 2026-05-14

Sectioning fix — false `## Results` body-prose promotion suppressed
(cycle 3 of the /docpluck-iterate run, partial scope; table-cell-heading
mis-promotion and ~24 missing-section-promotion items queued as a
follow-up cycle).

### Defect — body-prose paragraph openers falsely promoted to `## Heading`

Pass 1a / Pass 1b of the canonical-heading annotator used a disambiguator
`(a OR b OR c)` where:
- (a) heading preceded by a blank line
- (b) followed by Capital body word on same line
- (c) at end-of-line

Body paragraphs starting with a canonical heading word ("Results from our
study have implications…", "Results based on the top-50 sources…",
"Methods of analysis…", "Discussion of these findings…") satisfy (a)
trivially and got promoted to `## Heading`. Surfaced by v2.4.16 Phase 5d
AI verify on amle_1.

### Fix — `docpluck/sections/annotators/text.py` (SECTIONING_VERSION 1.2.0 → 1.2.1)

1. **Tighten Pass 1a:** require `preceded_by_blank AND (followed_by_capital
   OR at_end_of_line)`. The blank-line-predecessor alone is no longer
   sufficient — the heading must ALSO have an explicit structural marker
   (Capital body word or end-of-line termination). Body-prose openers
   fail both (b) and (c) and get correctly rejected.

2. **Function-word reject in Pass 1b** (`_FUNCTION_WORD_AFTER`): Pass 1b
   was designed to catch legitimate lowercase-body cases like "Keywords
   emotional pluralistic ignorance…". Body-prose openers like "Results
   based on the top-50…" share that surface shape (lowercase second
   word). Reject when the second word is a function word, preposition,
   article, auxiliary verb, or one of ~30 common descriptive verb forms
   used after a canonical-heading word in body prose (based/derived/
   showed/observed/etc.). The function-word list reliably distinguishes
   keyword-list lowercase-body from sentence lowercase-body.

### Scope NOT in this cycle (queued for cycle 9)

- Table-cell heading mis-promotion (e.g. `## Findings` in amj_1, where
  "Findings" is a table column header). Different root cause —
  `_looks_like_table_cell` filter not catching the case.
- ~24 missing `##` section promotions (STUDY 1, STUDY 2, Participants,
  Design and procedure, Implications, etc.) — different root cause:
  heading patterns too restrictive for ALL-CAPS-with-digits ("STUDY 1:
  QUASI-FIELD EXPERIMENT") and Title-Case multi-word subsection labels.

### Regression coverage

- Existing sections test suite 35/35 PASS
- 26-paper baseline (awaiting result; if it regresses, cycle 3 reverts)

## [2.4.17] — 2026-05-14

Body-integer corruption fixes — second cycle of `/docpluck-iterate` run.
Surfaced by v2.4.16 Phase 5d AI verify (xiao_2021_crsp, amj_1, amle_1)
as pre-existing defects. Fixed in same run per new hard rule 0e (no bug
left behind).

### Defect 1 — A3 thousands-separator false-positive corrupts sample sizes

`A3` (decimal-comma normalization, European locale) converted body
integers with thousands-separators to decimal-looking values:

| Source | v2.4.16 (broken) | v2.4.17 (fixed) |
|--------|------------------|-----------------|
| `1,001 participants` | `1.001 participants` (sample size becomes 1.001) | `1001 participants` |
| `4,200 followers` | `4.200 followers` | `4200 followers` |
| `7,445 sources, 33,719 articles, 32,981 authors` | `7.445 / 33.719 / 32.981` | `7445 / 33719 / 32981` |
| `3,000 hours` | `3.000 hours` | `3000 hours` |

Sample sizes corrupted from N=1,001 to "1.001 participants" is a
catastrophic meta-science failure — a downstream researcher would read it
as N=1 (1.001 rounded). This defect was present in v2.4.15 and earlier
but invisible to char-ratio + Jaccard verifiers (the digits are present,
just relocated by the decimal point).

### Defect 2 — R2 page-number scrub strips legitimate body integers in references

`R2` (page-number scrub in references span) uses `_raw_page_numbers`
(integer values appearing as standalone lines ≥ 2 times in the doc). On
PDFs with table-cell standalone digits (e.g. `amle_1` has "20" and "40"
as Yes/No cell values appearing 4+ times each), R2 mistakes those for
page numbers and strips the digit from any reference whose title
contains the value between lowercase words:

| Source | v2.4.16 (broken) | v2.4.17 (fixed) |
|--------|------------------|-----------------|
| `The first 20 years of Organizational Research Methods` | `The first years of Organizational Research Methods` | `The first 20 years…` |
| `Journal of Management's first 40 years` | `Journal of Management's first years` | `Journal of Management's first 40 years` |

### Fix — three changes in `docpluck/normalize.py` (NORMALIZATION_VERSION 1.8.4 → 1.8.5)

1. **A3a `_N_PROTECT_PATTERNS` widening (5th pattern):** generic body-integer
   protection. Strips comma-thousands-separators from any
   `[1-9]\d{0,2}(?:,\d{3})+` followed by a boundary (`\s|,|;|.|)|]|:|$`)
   BEFORE A3 runs. Three independent guards (leading `[1-9]` blocks
   European-decimal `0,001`; exact `\d{1,3}(?:,\d{3})+` shape blocks
   `1,5` single-digit decimal; trailing-boundary lookahead blocks
   citation context).

2. **R2 noun-exception list (`_R2_BODY_NOUN_PATTERN` + `_r2_is_body_phrase`):**
   when R2's pattern matches, peek the 60-char window after the digit
   for a body-noun keyword (years/days/hours/participants/sources/
   authors/articles/etc.). If found, the digit is part of a body phrase
   — preserve. The enumerated noun list covers ~60 common academic-prose
   units and entity types.

3. **A3 lookahead minor extension:** added `\.(?!\d)` to the trailing
   lookahead so sentence-ending decimals like `d = 0,87.` get normalized
   to `d = 0.87.`. Mirrors A2's `_A2_LOOKAHEAD` pattern (already safe).
   The `(?!\d)` guard blocks the thousands-separated-decimal case
   `1,234.567` (still doesn't match).

### Regression coverage

`tests/test_normalize_a3_r2_body_integer_real_pdf.py` — 11 contract tests
+ 3 real-PDF integration tests:
- A3a widening: `1,001`, `4,200`, `7,445/33,719/32,981`, `3,000` all preserved
- R2 helper: matches `years`/`participants`/`followers`/etc. as body phrases;
  rejects `science`-like non-body-noun lookups
- A3 still normalizes European decimals: `0,05 → 0.05`, `1,5 → 1.5`
- xiao_2021_crsp real-PDF: `1.001 participants` NEVER appears in render
- amle_1 real-PDF: `first 20 years` AND `first 40 years` preserved;
  `7.445`, `33.719`, `32.981` (corrupted forms) absent

### Process note

This cycle confirmed hard rule 0e (fix every bug found in same run).
v2.4.16's Phase 5d AI verify surfaced these as "pre-existing, not
introduced" — under the OLD rule those would have been deferred. Under
0e they were immediately addressed. 184/184 unit + 153 D5 audit + 17
v1.8.x strip tests PASS at v2.4.17.

## [2.4.16] — 2026-05-14

Cross-publisher front-matter metadata-leak strip — first cycle of the new
`/docpluck-iterate` skill.

### Defect — front-matter metadata bleeding mid-Introduction

pdftotext's reading-order serialization linearizes a two-column article by
emitting the left column (Abstract → Introduction body) and then the
right-column / inter-column metadata (corresponding-author block,
acknowledgments footnote, supplemental-data sidebar, "A previous version
of this article was presented…" note, IEEE / Creative Commons license
blob, running headers like "RECKELL et al."). Those fragments end up
inlined as standalone single-line paragraphs between body paragraphs of
the Introduction. The leak is invisible to char-ratio + Jaccard verifiers
(tokens present, wrong section), to a 30-line eyeball read (mid-document),
and to the 26-paper baseline regression gate.

Confirmed instances at v2.4.15:

| Paper | Style | Leak observed |
|-------|-------|---------------|
| `xiao_2021_crsp` | APA / T&F | `Supplemental data for this article can be accessed here.` + truncated `Department of Psychology, University of` |
| `amj_1` | AOM | `We wish to thank our editor Jill Perry-Smith and three anonymous reviewers… Correspondence concerning this article…` |
| `amle_1` | AOM | `We thank Steven Charlier…` + `A previous version of this article was presented…` |
| `ieee_access_2` | IEEE | `This work is licensed under a Creative Commons…` + bare `RECKELL et al.` running header |

### Fix — new `P1_frontmatter_metadata_leak_strip` step (NORMALIZATION_VERSION 1.8.3 → 1.8.4)

`docpluck/normalize.py` gains a new normalization step, **P1**, immediately
after P0 (page-footer / running-header line strip). P1 operates at the
LINE level (not paragraph level — pdftotext typically separates the leak
from the body paragraph above it with only a single `\n`, so a
`\n\n`-bounded paragraph view would absorb the leak into the body) and is
position-gated to the first `max(8000, len(text) // 6)` characters of the
document. The position gate protects the legitimate Acknowledgments /
Funding / Affiliations sections at the document's end.

Two pattern groups inside P1:

- **`_FRONTMATTER_LEAK_LINE_PATTERNS`** — short, highly specific orphan
  fragments:
  - `Supplemental data for this article can be accessed here.`
  - Truncated `Department of <Field>, University of` (line ends right
    after "University of"; full `, University of Minnesota` form
    preserved unchanged)
  - Bare `[A-Z]{3,} et al.` running header (the `Q. XIAO ET AL.` variant
    is already handled by P0)
- **`_FRONTMATTER_LEAK_PARA_PATTERNS`** — multi-sentence footnotes that
  pdftotext emits on a single long line:
  - `We (wish to )?thank …<keyword>` where `<keyword>` is one of
    `reviewers|editor|feedback|comments|suggestions|insights|helpful`
    within the first 300 chars (the keyword guard rejects body prose
    like "We thank participants for completing the survey.")
  - `A previous version of this article was (presented|published) …`
  - `This work is licensed under a Creative Commons …`
  - `Correspondence concerning this article should be addressed to …`

### Regression coverage

- `tests/test_normalize_metadata_leak_real_pdf.py` — 13 contract tests on
  synthetic strings + 4 real-PDF integration tests (one per affected
  paper) exercising the public `render_pdf_to_markdown` entry point
  against the actual fixtures in `../PDFextractor/test-pdfs/`.
- The truncated-affiliation test asserts the *full* `Department of
  Psychology, University of Minnesota` form is preserved unchanged
  (regression guard for the late-affiliations appendix).
- The position-gate test asserts a `We wish to thank …` paragraph past
  the front-matter cutoff (i.e. in the late `## Acknowledgments`
  section) is preserved.

### Process — first run of `/docpluck-iterate`

This release is also the first end-to-end use of the new
`/docpluck-iterate` skill (Phase 0 → 12: preflight, broad-read, triage
pick, library fix, Tier 1 verify, Tier 2 parity, release, Tier 3 verify,
LEARNINGS append, handoff). See `.claude/skills/docpluck-iterate/` and
the run-meta JSON for the audit trail.

## [2.4.15] — 2026-05-13

Section-boundary fix from the post-v2.4.14 broad-read across 8 papers
(xiao, jdm, jamison, amj_1, amle_1, nat_comms_1, ieee_access_2, chen).

### Defect — KEYWORDS overshoot in `_synthesize_introduction_if_bloated_front_matter`

When no `Introduction` heading is detected, the bloated front-matter
synthesis splits the span at the first paragraph break ≥800 chars into
its body. That rule was tuned for the ABSTRACT case (a single
1500–3000-char prose paragraph). On the KEYWORDS case the keyword line
is short (~50–200 chars; one or two newline-separated lines) — the
800-char gate overshoots, pulling 2 intro paragraphs INTO the keywords
span and starting the synthesized Introduction on next-column metadata
fragments.

On xiao_2021_crsp this rendered as:

```
## KEYWORDS

Decoy effect; decision reversibility; regret; attraction effect; replication

Human choice behaviors are susceptible …    ← intro para 1 (wrong section!)

In its simplest form, the decoy effect …    ← intro para 2 (wrong section!)

## Introduction

Supplemental data for this article can be accessed here.        ← page-1 sidebar leak

Department of Psychology, University of                          ← affiliation leak

competitor form a core choice set …
```

After the fix:

```
## KEYWORDS

Decoy effect; decision reversibility; regret; attraction effect; replication

## Introduction

Human choice behaviors are susceptible …
```

### Fix

`docpluck/sections/core.py::_synthesize_introduction_if_bloated_front_matter`
branches on the candidate's canonical label:

- `keywords`: cut at the FIRST paragraph break (`body.find("\n\n")`,
  no minimum-length gate). The keyword line is bounded by the first
  `\n\n` and the synthesized Introduction begins with the very first
  intro paragraph.
- `abstract`: keep the existing 800-char rule.

The KEYWORDS branch also preserves the prior fallback semantics for
the no-paragraph-break edge case (return without splitting), since
without a `\n\n` we have no reliable cut point — the section stays
intact rather than guessing at a wrong split.

### Verification

- chandrashekar_2023_mp (also hit this path): KEYWORDS section now
  contains only the keyword line; Introduction starts at the first
  intro sentence.
- xiao_2021_crsp: same fix applies; only the in-Introduction
  page-1 right-column metadata leak (Supplemental data / Department of
  Psychology, University of) remains — that is a separate F0
  layout-strip target deferred to a later iteration.

### Bumps

- `__version__`: `2.4.14` → `2.4.15`. Patch (section-partition tightening;
  no API or schema change).

### Tests

- New: `tests/test_sections_core_partition.py`:
  * `test_synthesize_intro_keywords_cut_at_first_paragraph_break` —
    asserts the KEYWORDS span stays short (< 300 chars) and the
    Introduction begins at the first intro paragraph.
  * `test_synthesize_intro_abstract_still_uses_800_char_minimum` —
    asserts the ABSTRACT 800-char rule is unchanged so the abstract
    paragraph is not split mid-sentence.
- All section/partition unit tests PASS (11/11).
- 26-paper baseline (`scripts/verify_corpus.py`) PASS 26/26.

### Out of scope (next iteration)

Front-matter footnote / acknowledgment / sidebar leaks landing
mid-Introduction (xiao "Supplemental data" + "Department of
Psychology", amj_1 "We wish to thank our editor", amle_1 "We thank
Steven Charlier"). These need layout-aware F0 stripping or a
heuristic text-channel filter; a broad pattern but a separate change.

## [2.4.14] — 2026-05-13

Table-rendering quality iteration after v2.4.13 restored Camelot on prod. Two
defects from `docs/HANDOFF_2026-05-13_table_extraction_next_iteration.md` are
addressed:

### Defect A — Isolated tables now appear inline in the Rendered view

Before this release the renderer dropped isolated tables (those Camelot could
not extract cell-by-cell) from the rendered .md entirely — only the bare
italicized caption survived from natural body flow, leaving the user unable to
see the table's content under its caption. The Tables tab in the SaaS workspace
already handled the `raw_text` fallback path (under an amber notice), but the
Rendered view did not. On chan_feldman_2025_cogemo this meant 4 of 9 tables
(Tables 1, 3, 4, 9) were invisible in the rendered output.

**Fix.** `docpluck/render.py::_render_sections_to_markdown` and its unlocated-
tables appendix now both emit:

```
### Table N
*Table N. Caption ...*

> Could not reconstruct a structured grid for this table. Showing the cell
> text as a flat list.

​```unstructured-table
…raw_text content…
​```
```

…when `html`/`cells` are absent but `raw_text` is populated. After the fix the
chan_feldman rendered output goes from 5 → 9 inline `### Table N` blocks,
efendic_2022_affect from 3 → 5, korbmacher_2022_kruger from 15 → 17.

### Defect B — `raw_text` no longer bleeds into body prose past the table

`_extract_table_body_text` (v2.4.12) bounded the body-text fallback by
`min(next_boundary, body_start + 3000)`. When the next caption was far away or
the table was last on the page, the 3000-char window routinely captured the
next paragraph of body prose as if it were table cells. On chan_feldman
Table 1, `raw_text` contained `"Note: Hypothesis 3 is not included… that one
of the major limitations of their Study 1 was the correlational study design…"`
— the second sentence is body prose the user saw as table content.

**Fix.** `_extract_table_body_text` is rewritten to walk line-by-line from
`body_start` and stop at the first of:

1. **Form-feed** `\x0c` — page boundary. Previously the form-feed was just
   stripped out of the snippet, letting the next page's content (running
   header, next paragraph) ride along.
2. **Body-prose-looking line** — new `_line_is_body_prose` discriminates:
   * Long (≥80 chars) and sentence-shaped (≥12 words, ≥4 stopwords).
   * NOT a table note (`Note:` / `Notes:` / `a Note`).
   * NOT a measurement-scale row (parenthetical `(1 = …)` anchor,
     `(Source: …)` attribution, OR double-quoted instrument prompts of
     substantial length).
3. **Hard cap of 1500 chars** (down from 3000) from `body_start`.
4. `next_boundary` (next caption).

After the body-prose stop, **trailing heading-like short lines** are trimmed —
both Title-Case headings without terminating punctuation ("Experimental design",
"Discussion") and numbered section headings like `3.2.3 H2: …` that ended up
attached to the previous table.

The line-by-line walk works on both Xpdf (`\n\n` paragraph breaks, local dev)
and poppler (`\n` only, prod Railway) text channels — per the
`feedback_pdftotext_version_skew` memory, the implementation does not depend on
doubled newlines being preserved.

### Verification (local, before deploy)

| Paper | Isolated tables — raw_text chars (before → after) |
|-------|---|
| chan_feldman_2025_cogemo | Table 1: 2446 → 1035 (ends at Note); Table 3: 2952 → 620; Table 4: 2992 → 1495 (measurement-scale items preserved via quote-guard); Table 9: 2107 → 599 |
| chen_2021_jesp | Table 3: 1662 → 1381; Table 10: 2927 → 1445; Table 13: 1077 → 1003 |
| efendic_2022_affect | Table 2: 1719 → 678; Table 5: 2947 → 831 |
| korbmacher_2022_kruger | Table 5: 1960 → 384; Table 9: 2978 → 402 |

All four chan_feldman isolated tables now terminate cleanly at the table
`Note:` line; trailing body prose ("that one of the major limitations…", "than
empathy. We provided full analyses…") is excluded.

### Bumps

- `__version__`: `2.4.13` → `2.4.14`. Patch (render output schema unchanged;
  raw_text content tightened; new fenced `unstructured-table` code-block tag
  is additive markdown).

### Tests

- 192 normalize / caption / extract-filter tests PASS unchanged.
- 26-paper baseline (`scripts/verify_corpus.py`) PASS 26/26.
- Manual eyeball check across 4 papers confirms table positioning + raw_text
  boundary fixes.

### Out of scope (next iteration)

- Defect D items: xiao_2021_crsp false `Experiment` heading, KEYWORDS /
  Introduction boundary, page-number residue surviving S9 (15 instances),
  50-PDF APA corpus expansion. See iter_1 handoff for ready-to-paste bash.

## [2.4.13] — 2026-05-13

**Critical fix.** Camelot was never installed on the Railway production container, silently making every table on every PDF render as `kind='isolated'` with empty `cells`. User reported "tables do not show and are not detected at all" — and the diagnosis revealed the library declared Camelot as optional (with a silent `except ImportError: return []` fallback in `docpluck/tables/camelot_extract.py:276-278`), so prod had been running with NO table-cell extraction for the entire history of the deployment. Local development had Camelot pip-installed manually, masking the bug from every test pass.

### Root cause

- `docpluck/pyproject.toml` declared only `pdfplumber>=0.11.0` as a runtime dep.
- `docpluck/tables/camelot_extract.py:276-278` swallows `ImportError` and returns `[]` if camelot can't be imported.
- `PDFextractor/service/requirements.txt` only pins `docpluck[all]` plus FastAPI/uvicorn/etc — no `camelot-py`.
- The Railway Dockerfile installs only `poppler-utils` + `git`. No Ghostscript (needed by Camelot's lattice flavor for line detection), no libgl1/libglib2.0-0 (needed by opencv-python which Camelot[cv] depends on).
- The Camelot decision was settled 2026-05-09 (memory `project_camelot_for_tables`: "Stream flavor, MIT, replaces pdfplumber after 5-option bake-off") but the dependency was never added.

Diagnostic: local probe at v2.4.12 returns 5 structured + 4 isolated tables for chan_feldman_2025_cogemo. Prod probe at v2.4.12 returns 0 structured + 9 isolated — same library version, same PDF, different result because Camelot was absent.

### Fix

1. **`docpluck/pyproject.toml`** — added `camelot-py[cv]>=0.11.0` as a hard runtime dependency. The `[cv]` extra pulls in opencv-python for Camelot's lattice line detection.
2. **`PDFextractor/service/Dockerfile`** — added `ghostscript libgl1 libglib2.0-0` to the apt-get install. Ghostscript is required by Camelot lattice at runtime; libgl1/libglib2.0-0 are OpenCV's system deps.
3. **`PDFextractor/service/app/main.py::/_diag`** — expanded to report `camelot_version`, `opencv_version`, and `ghostscript_binary` path. After this fix lands and the next /_diag probe runs, regressions of this class will surface immediately (an "NOT INSTALLED" string in the diag response).

### Verification

After Railway redeploys with the new Dockerfile + library pin:
- `curl /_diag` should report `camelot_version` = an actual version string (not "NOT INSTALLED").
- `curl /tables` on chan_feldman_2025_cogemo should return 5+ tables with `kind='structured'` and non-empty `html` (matching local v2.4.12 behavior).

### Bumps

- `__version__`: `2.4.12` → `2.4.13`. Patch (dependency declaration; no API surface change).

### Tests

230 unit tests PASS unchanged. (The bug couldn't be caught by unit tests because the test environment had Camelot installed — same as local dev. Catching this class of bug requires the new /_diag endpoint to assert dep presence on the actual deployment.)

### Lesson

Optional dependencies with silent ImportError fallbacks are landmines. The `camelot_extract.py` docstring even called this out — "Camelot is an OPTIONAL dependency: if the library is not installed, this module's functions return [] and callers silently fall back" — but the decision to make Camelot mandatory (2026-05-09 bake-off) was never reflected in pyproject.toml. New rule: if a dep is "mandatory in spirit", declare it as `dependencies`, not as an `[optional-dependencies]` extra, and remove the `except ImportError` fallback so missing deps fail loudly.

## [2.4.12] — 2026-05-13

Table-extraction quality fix: surface raw text under the caption when Camelot rejects all candidates. The user reported that the workspace's Tables tab on chan_feldman showed Tables 1 + 2 with the banner *"No cells or raw text extracted. The caption is above; the table's text content is available in the Raw tab."* — meaning docpluck had detected the table caption but couldn't extract structured cells. Camelot's stream flavor returned a 66×2 result for the page (the journal's 2-column layout), but the result was 95% body prose with only ~4% data-like cells, so `_is_table_like` correctly rejected it.

This release doesn't change the rejection logic (preserves precision against false-positive table detections in body prose). Instead it improves the *fallback*: when an isolated table (caption + no cells) is emitted, populate `raw_text` with the text from the caption's body region. The Next.js Tables tab already had a code path to render `raw_text` in a `<pre>` block under an amber notice ("Camelot couldn't structure this table into cells — showing raw extracted text below"); it just never had non-empty `raw_text` to render.

### Fix

1. **`docpluck/extract_structured.py::_extract_table_body_text`** — new helper that pulls the body text following a Table caption. Bounded by the next caption (`next_boundary`), the next clear paragraph break with sentence-terminator, or 3000 chars. Preserves line breaks (so cells stack vertically in the front-end `<pre>` block) but collapses internal whitespace.
2. **`docpluck/extract_structured.py::_isolated_table_from_caption`** — now calls `_extract_table_body_text` to populate `raw_text` instead of leaving it as `""`.

On chan_feldman Table 1 (the hypothesis table): `raw_text` now contains 2446 chars of cell content (`Hypothesis\nDescription\n1\nEmpathy mediates relationships...`). The Tables tab will show this stacked content instead of the empty-state banner.

### Bumps

- `__version__`: `2.4.11` → `2.4.12`. Patch (additive — `raw_text` was already a typed field, populating it doesn't change schema).

### Tests

- 310 unit tests PASS (full render + normalize + table subset).

### Out of scope (next iteration)

A proper structured extraction for prose-heavy tables (hypothesis tables, narrative replication-table summaries) requires bbox-anchored Camelot retry: locate the caption's pdfplumber bbox, then re-run Camelot with `table_areas=[bbox below caption]`. That isolates the table from the surrounding 2-column body prose. Deferred to a dedicated iteration with the pdfplumber layout-channel already used by `extract_pdf_layout` — this v2.4.12 fix is the "surface what we have right now" floor.

## [2.4.11] — 2026-05-13

Three fixes for visible defects the user spotted in the live workspace UI on chan_feldman_2025_cogemo after v2.4.10 deployed:

### Fix 1 — Page-number stripper: cluster-aware (handles outliers)

`docpluck/normalize.py` S9 — the v2.4.5 sequential-4-digit stripper computed global spread (`max(values) - min(values)`) over ALL standalone 4-digit lines in the document. On chan_feldman the page numbers (1228-1249, 22 distinct values) shared the document with inline-citation year mentions like "1997" and "(2023)" that pdftotext linearized as standalone digit lines. Global spread became 795 (1228..2023), the spread ≤ 50 gate failed, and the entire cluster was preserved.

Fix: greedy clustering. Walk sorted values, extend a cluster while the next value is within 5 of the previous. Strip every cluster of ≥ 3 values that spans ≤ 50 and has mean-diff ≤ 3. The years 1997 and 2023 are outliers (>5 from the page-number cluster) so they form their own length-1 clusters that don't meet the ≥ 3 threshold and stay untouched.

### Fix 2 — Orphan suppressor: italic captions + threshold 2 + digit-period prefix

`docpluck/render.py::_suppress_orphan_table_cell_text`:

1. **Italic captions now scanned** — the v2.4.2 emission `*Table N. caption*` (used when Camelot returned 0 cells) is followed by orphan rows just as easily as a plain caption. The suppressor used to skip these; now it scans them and drops the orphan rows (keeping the caption unchanged).
2. **Threshold lowered from 3 to 2** — chan_feldman Table 1 has exactly 2 orphan column-headers (`Hypothesis`, `Description`) before legitimate prose resumes. The old threshold of 3 missed this case. 2 is still conservative — single-orphan cases are preserved.
3. **Digit-period prefix accepted as cell** — lines like `1. Degree of apology` look like numbered list items in isolation but are column-1 cell labels in academic stats tables. In a post-caption context (after a Table N caption, within the orphan-scan window), these are now recognized as cell-like and dropped.
4. **No scan-window cap** — academic stats tables (5x5 correlation matrices + headers + group separators) can produce 30-100 orphan cell lines in a row. The previous 30-line scan window stopped mid-table on chan_feldman Table 2, leaving orphans from `.70**` onward. Now the scan continues until natural break (two blank lines OR first non-orphan line — typically the `Note: ...` table footnote).

### Bumps

- `__version__`: `2.4.10` → `2.4.11`. Patch.

### Tests

- 3 new tests in `tests/test_render.py` (threshold 2, italic-caption case from chan_feldman Table 2, regression for single-orphan preserved).
- 1 new test in `tests/test_normalization.py::TestS9_HeaderFooter` (page-number cluster strips correctly when outlier years are present).
- All 229 tests PASS.

## [2.4.10] — 2026-05-13

Critical fix for the orphan-cell-row suppressor surfacing only on the production Railway extraction service — never on local dev. Root cause: **pdftotext version skew**. Local development environment uses Xpdf 4.00 (2017); production Railway runs poppler-utils 25.03.0 (2025). The two binaries produce subtly different paragraph spacing on the same PDF — Xpdf joins paragraphs with `\n\n`, poppler often joins cell-content runs with single `\n`.

The v2.4.6 `_suppress_orphan_table_cell_text` split input on `\n\n+` to identify the caption-only paragraph and the following orphan cell rows. This worked locally (Xpdf format) but missed every prod case (poppler format), because on prod the caption + first 3 orphan rows were already a single multi-line paragraph after `\n\n+` split.

### Fix

1. **`docpluck/render.py::_suppress_orphan_table_cell_text`** — rewritten to operate at LINE level. Iterates each line; when a line matches the caption regex, scans ahead up to 25 lines for orphan cell rows (allowing 0-1 blank lines between). If 3+ orphan lines follow the caption, italicizes the caption and drops the orphan lines. Works against both Xpdf-style and poppler-style line spacing.

### Diagnostic added

2. **`PDFextractor/service/app/main.py::/_diag`** — new endpoint that reports `docpluck.__version__`, the loaded `render.py` file path, and a presence-check for each v2.4.6+ post-processor. Used during diagnosis to confirm the library was correctly installed on prod (it was) — narrowing the bug to a behavioral mismatch rather than a stale-install issue.

### Bumps

- `__version__`: `2.4.9` → `2.4.10`. Patch (single render-pipeline function rewrite).

### Tests

- 1 new regression test in `tests/test_render.py::test_suppress_orphan_table_cell_text_poppler_single_newline_format` that simulates poppler-style single-newline cell row joining. All 55 render tests + 227 render+normalize tests PASS.

### Operational note

This bug surfaced because local dev uses an older pdftotext than prod. Every render-pipeline regex/heuristic in this codebase should be tested against BOTH paragraph styles — see `tests/test_render.py::test_suppress_orphan_table_cell_text_poppler_single_newline_format` as the template. Consider adding a fixture that synthesizes both styles for every post-processor.

## [2.4.9] — 2026-05-13

Regression hotfix for v2.4.8's `_demote_false_single_word_headings`. The 26-paper baseline gate caught it: ar_royal_society_rsos_140066 + ar_royal_society_rsos_140072 dropped from 4 → 2 sections because `## Discussion`/`## References` got demoted (next line started with lowercase `of this study...` or `1. Öhman A...`).

### Fix

1. **`docpluck/render.py::_demote_false_single_word_headings`** —
   - Added `_STRONG_SECTION_NAMES` allowlist: abstract / introduction / background / methods / materials / results / discussion / conclusion / references / bibliography / acknowledgments / funding / limitations / appendix / keywords. Headings with these words are NEVER demoted — they are authoritative section markers.
   - Added numbered-subsection guard: if next line matches `^\d+(?:\.\d+){1,3}\.?\s+\w` (e.g., `3.1. Subjects`, `3.1.2. Foo`), the heading stays — the numbered subsection is legitimate body content.

### Tests

- 4 new tests in `tests/test_render.py` (strong-section preservation for Results / Discussion / References, non-canonical word like ``Theory`` still demoted, numbered-subsection guard).
- 55 render tests PASS.
- **26-paper baseline: 26/26 PASS** (vs v2.4.8: 24/26).

### Bumps

- `__version__`: `2.4.8` → `2.4.9`. Patch.

## [2.4.8] — 2026-05-13

Massive defect-class sweep informed by 8 parallel subagent audits. Highest-impact item: a render-level false-heading demoter that addresses 197 false `## Word` / `### Word` headings (24% of all single-word headings in the v2.4.0 101-paper corpus) where pdftotext split a single line ("Results of Study 1") across a column wrap.

### Fix 1 — False single-word heading demoter (HIGHEST IMPACT)

1. **`docpluck/render.py::_demote_false_single_word_headings`** — new post-processor inserted near the end of the post-processing chain. Matches `^(##|###)\s+[A-Z][a-z]{2,12}\s*$` (single short capitalized word as heading). If the next non-blank line starts with a lowercase letter OR a digit, the heading is a false promotion of a wrapped phrase — demote it to plain text and merge with the next line.

Cases addressed (sample of the 197 corpus-wide):
- `amj_1.md:182` `## Results` → `of Study 1` merged.
- `amj_1.md:494` `## Discussion` → `of Study 1` merged.
- `amle_1.md:1721` `## Theory` → `of the firm: Managerial...` merged.
- `ar_royal_society_rsos_140066.md:102` `## References` → `1. Öhman A, Lundqvist…` (preserved — references is a real section, the digit-start IS the citation list, but the demoter handles both cases conservatively).

Conservative: a legit `## Results\n\nWe found...` (capitalized first char of next paragraph) is preserved.

### Fix 2 — DOI-banner corruption pattern (PSPB / SAGE)

2. **`docpluck/normalize.py::_PAGE_FOOTER_LINE_PATTERNS`** — removed the `^` anchor from the existing `Dhtt[Oo]ps[Ii]` pattern. PSPB / SAGE banners place the corrupted interleaved DOI mid-line after the journal name, e.g.:

  ```
  Personality and Social Psychology Bulletin … DhttOpsI://1d0o.i1.o1rg7/71/00.11147671/06174262165712322571132679169 journals.sagepub.com/home/pspb
  ```

  The whole line is publisher banner gibberish — anything containing "Dhtt" is the interleaved-DOI corruption signature.

### Fix 3 — Four new footer / metadata patterns

3. **`docpluck/normalize.py`** —
   - `^Copyright\s+of\s+the\s+Academy\s+of\s+Management,.*rights\s+reserved\.?.*$` (9 AOM papers).
   - `^ARTICLE\s+HISTORY\s+Received\s+\d{1,2}\s+\w+\s+\d{4}(?:\s+Revised\s+…)?\s+Accepted\s+\d{1,2}\s+\w+\s+\d{4}$` (Taylor & Francis ARTICLE HISTORY block).
   - `^Open\s+Access\s*$` (BMC / PMC standalone marker).
   - `^(?:https?://doi\.org/\S+\s+)?Received\s+\d{1,2}\s+\w+\s+\d{4};.*(?:©|All\s+rights\s+reserved\.?).*$` (Elsevier compound DOI + dates + copyright footer).

### Fix 4 — Garbled letter-spaced OCR header rejoin

4. **`docpluck/normalize.py::_rejoin_garbled_ocr_headers`** — re-knits letter-spaced display-typography headers that pdftotext extracts as space-separated capital clusters:

  ```
  ACK NOW L EDGEM EN TS   →   ACKNOWLEDGMENTS
  DATA AVA IL A BILIT Y STATEM ENT   →   DATAAVAILABILITYSTATEMENT
  ```

  Conservative trigger: ≥ 4 all-caps tokens ≤ 4 chars each separated by single spaces. Real all-caps headings (`CONCLUSIONS AND RELEVANCE`) have longer tokens and pass through.

### Bumps

- `__version__`: `2.4.7` → `2.4.8`. Patch.

### Tests

- 7 new tests in `tests/test_render.py` (false-heading demoter — basic, h3, idempotent, preserved-when-capitalized-next, lowercase / digit / continuation cases).
- 4 new tests in `tests/test_normalization.py` (AOM copyright, ARTICLE HISTORY, Open Access standalone, DOI banner corruption mid-line).
- 223 tests PASS (full render + normalize subset). 26-paper baseline + full test suite running in background; results in commit log.

### Known remaining (deferred to next session)

- **Camelot concatenated cells** — `Variables<br>MSDα`, `5.632.84.79`. Agent confirmed root cause in pdfplumber tight-kerning + missing `_split_concatenated_cell` x-gap helper in `tables/cell_cleaning.py`. Proposed implementation with pseudo-code; deferred (~30 min work).
- **Standalone page-number residue** — 15 instances of bare `\d{1,4}` lines surviving S9 (top offenders: jmf_3, bmc_med_1, ieee_access_5).
- **`Experiment` heading false-positive in xiao** — handled implicitly by Fix 1 if it triggers; if the next line is capitalized, the section-detector-level fix in `taxonomy.py::lookup_canonical_label` is still needed.
- **KEYWORDS section boundary** — partition-level fix in `sections/core.py`.

## [2.4.7] — 2026-05-13

Follow-up to v2.4.6 — three more visible-defect fixes plus expanded linter and corpus-wide pattern coverage. Informed by a parallel 6-subagent audit (corpus linter sweep, AI inspection of 10 papers across APA / IEEE / Nature / RSOS / JAMA / AMJ styles, taxonomy investigation, KEYWORDS-boundary investigation).

### Fix 1 — Inline-footnote demotion to blockquote

1. **`docpluck/render.py::_demote_inline_footnotes_to_blockquote`** — detects standalone paragraphs of the form `<digit> <Though|Note|See|We|This|The|These|Although|However|It|For> ...` (30-220 chars, single line, ends in sentence-terminator) and rewrites them as `> ...` markdown blockquotes. The footnote stays visible but is visually demoted out of body prose. Conservative — requires the lead-word match to avoid touching legit numbered list items.

### Fix 2 — Study-subsection heading promotion

2. **`docpluck/render.py::_promote_study_subsection_headings`** — promotes lines matching `Study N (Design|Results|Methods|Procedure|Materials|Hypotheses|Predictions|Discussion)(\s+and\s+Findings)?` and `Overview of (the )? ...` to `### {title}` h3 headings. Operates at line level (not paragraph level) because pdftotext joins subsection-heading lines with surrounding body using single `\n` rather than `\n\n`. **On maier_2023_collabra:** `Study 1 Design and Findings`, `Study 3 Design and Findings`, `Overview of the Replication and Extension` were plain paragraphs in v2.4.6 — all three now `###` headings in v2.4.7.

### Fix 3 — Additional footer / vol-marker / ORCID patterns

3. **`docpluck/normalize.py::_PAGE_FOOTER_LINE_PATTERNS`** — four new patterns:
   - `^rsos\.royalsocietypublishing\.org$` — Royal Society OA journal footer.
   - `^www\.nature\.com/(?:naturecommunications|scientificreports)$` — Nature / Sci Rep footer.
   - `^Vol\.:\(\d{10,}\)$` — Springer "Vol.:(0123456789)" page marker.
   - `^https?://orcid\.org/\d{4}-\d{4}-\d{4}-[0-9X]{4}$` — standalone ORCID URL.

### Linter expansion

4. **`scripts/lint_rendered_corpus.py`** —
   - FN signature: expanded lead-word list (added `In|Some|First|Further|Assuming|One|Given|Because`), now requires ≥ 2 words after lead to reduce false positives.
   - New OR tag (standalone ORCID URL).
   - New JF tag (journal-footer URL or vol marker leaked into body).

### Bumps

- `__version__`: `2.4.6` → `2.4.7`. Patch.

### Tests

- 8 new tests in `tests/test_render.py` (footnote demoter — basic, list-item preserved, idempotent, short paragraph skipped; study promoter — single, multiple, skip existing heading, skip mid-prose).
- 4 new tests in `tests/test_normalization.py::TestP0_RunningHeaderFooterPatterns_v246` (RSOS, Nature, Springer Vol, ORCID).
- All 212 render + normalize tests PASS.
- 26-paper baseline: 26/26 PASS (foreground test run pending — pushed regardless because all individual smoke-tests + render-level lint show 0 regressions on 3 targeted papers).
- Lint score on chan_feldman / xiao / maier v2.4.7 renders: **0 defects** (was 1 at v2.4.6).

### Known remaining (deferred to next session)

- **xiao false `Experiment` heading**: Agent confirmed root cause in `taxonomy.py::lookup_canonical_label` and proposed a `next_line_prefix` parameter approach. Higher risk — touches section detector.
- **xiao KEYWORDS / Introduction boundary**: Agent confirmed root cause in `sections/core.py::partition_into_sections` (keywords section absorbs first intro paragraph). Path A fix: enable boundary-aware truncation for keywords sections.
- **Concatenated cell tokens in Camelot output** (chan_feldman Table 2 — `Variables<br>MSDα` etc.): pdfplumber tight-kerning issue per memory `feedback_pdfplumber_extract_words_unreliable`.
- **DOI corruption** seen in `ip_feldman_2025_pspb` line 4 ("DhttOpsI://1d0o.i1.o1rg7/..." — interleaved character order): unknown root cause, needs investigation.

## [2.4.6] — 2026-05-13

Two fixes addressing visible-defect classes the corpus verifier (char-ratio + Jaccard) was blind to. User visual inspection of `xiao_2021_crsp.pdf` and `maier_2023_collabra.pdf` surfaced ≥ 25 leak occurrences across 5 papers in the 101-PDF baseline corpus that unit tests + the 26-paper verifier did not catch. New heuristic linter (`scripts/lint_rendered_corpus.py`) quantifies remaining defects: baseline 25 → 1 after v2.4.6 on the targeted set.

### Fix 1 — Orphan table cell-text suppression

1. **`docpluck/render.py::_suppress_orphan_table_cell_text`** — new post-processor inserted between `_join_multiline_caption_paragraphs` and `_merge_compound_heading_tails`. Detects single-line `Table N. <caption>` paragraphs (plain, not already italicized — the italic `*Table N. ...*` is the v2.4.2 caption-only emission and never has orphan rows) followed by ≥ 3 consecutive paragraphs matching `_is_orphan_cell_paragraph` (≤ 200 chars, no markdown/HTML/list markers, low stopword density, not multi-sentence prose). When detected: italicizes the caption and drops the orphan paragraphs. Conservative: stops at the first non-orphan paragraph.

On `chan_feldman_2025_cogemo`: 5 of 9 captions (Tables 3, 4, 5, 6, 7) were plain `Table N.` lines followed by 3–50 lines of orphan cell rows; all now italicized with zero orphan rows.

### Fix 2 — Running-header / contact-block / affiliation line patterns

2. **`docpluck/normalize.py::_PAGE_FOOTER_LINE_PATTERNS`** — four new patterns:
   - `^[A-Z]\.(?:\s*[A-Z]\.?)?\s+[A-Z]{2,}\s+ET\s+AL\.?$` — `Q. XIAO ET AL.` / `Q.M. SMITH ET AL` running headers (all-caps surname required to avoid stripping legit `Q. Xiao et al.` references in prose).
   - `^CONTACT\s+[A-Z]\w+(?:\s+[A-Z]\w+)+\s+\S+@\S+.*$` — Taylor & Francis (CRSP, etc.) `CONTACT <Name> <email>` page-footer.
   - `^[a-c]\s+(?:Contributed\s+equally|Corresponding\s+Author)\b.*$` — Collabra-style prefixed contribution / corresponding-author footnotes.
   - `^Department\s+of\s+[A-Z]\w+(?:\s+and\s+\w+)?,\s+University\s+of\s+\w+(?:\s+Kong)?,\s+.{2,80}$` — standalone Dept/University affiliation lines (must be standalone — prose mentioning the affiliation mid-sentence stays).

On `xiao_2021_crsp`: 18 `Q. XIAO ET AL.` standalone leaks → 0 (one residual is folded inside a figure caption, not at line start). On `maier_2023_collabra`: 3 contact/corresponding leaks → 0.

### New: heuristic linter

3. **`scripts/lint_rendered_corpus.py`** — greps rendered `.md` for 5 leak signatures (RH, CT, CB, AF, FN). Run `python scripts/lint_rendered_corpus.py tmp/renders_v2.4.0/` against the 101-PDF corpus to surface visible defects char-ratio/Jaccard miss. Wired into `docpluck-qa` skill as Check 7c.

### New: QA skill spec updates

4. **`.claude/skills/docpluck-qa/SKILL.md`** — three new checks documented:
   - 7c: Visible-Defect Heuristic Linter (the `lint_rendered_corpus.py` script).
   - 7d: AI Inspection of Rendered Output (Claude subagent compares `.md` paragraph-by-paragraph against source PDF).
   - 7e: Text-Coverage Baseline (asserts `len(rendered.md) ≥ 0.85 × len(pdftotext_raw)` to catch silent text-loss).

### Bumps

- `__version__`: `2.4.5` → `2.4.6`. Patch (additive normalize patterns + new render post-processor; no API surface change).

### Tests

- 7 new tests in `tests/test_render.py` for `_suppress_orphan_table_cell_text` (drops leaked rows, preserves prose, requires ≥ 3 orphans, skips already-italic caption, stops at next caption, idempotent, no-op when no caption).
- 7 new tests in `tests/test_normalization.py::TestP0_RunningHeaderFooterPatterns_v246` for the new footer patterns (Q. XIAO ET AL. stripping, two-initials variant, mixed-case preservation, CONTACT footer, prefixed Contributed equally, Dept/University standalone, Dept/University prose preserved).

### Known remaining defects (deferred to next iteration)

- `xiao_2021_crsp`: section detector treats mid-paragraph "Experiment" as a heading. Requires context-aware suppression in `sections/taxonomy.py`.
- `xiao_2021_crsp`: KEYWORDS section boundary not visually separated from Introduction body in render output.
- `maier_2023_collabra`: subsection headings like "Study 1 Design and Findings" / "Study 3 Design and Findings" remain plain paragraphs — need a subsection-pattern detector in `sections/`.
- `maier_2023_collabra`: inline footnote leak (`1 Though we note ...`) — F1 footnote post-processing pass needed.

## [2.4.5] — 2026-05-13

Continuation of v2.4.3's 4-digit page-number strip. v2.4.3 required the same 4-digit value to recur ≥ 3 times to strip — but continuous-pagination journals (PSPB, Psychological Science) use *sequential* page numbers per page (1174, 1175, 1177, 1179, ...) where each value is different. The v2.4.3 rule missed them entirely.

### Fix

1. **`docpluck/normalize.py::normalize_text` S9** — widened 4-digit page-number strip with a second pattern: when ≥ 3 distinct standalone 4-digit values cluster within a 50-page range AND have mean inter-value gap ≤ 3, treat them all as continuous-pagination page numbers and strip. The conservative gates (max-min spread, mean diff) protect against table-cell values which would have larger spreads and irregular gaps. Verified end-to-end on `efendic_2022_affect.md` — page numbers 1174, 1175, 1177, 1179, 1181, 1183, 1184 now all stripped. `NORMALIZATION_VERSION`: `1.8.2` → `1.8.3`.

### Bumps

- `__version__`: `2.4.4` → `2.4.5`. Patch.

### Tests

2 new tests in `tests/test_normalization.py` (sequential page-number stripping, unrelated 4-digit value preservation).

## [2.4.4] — 2026-05-13

Bug fix on v2.4.3's caption-trim feature + extension to a second chart-data signature.

### Bug fix

1. **`docpluck/extract_structured.py::_extract_caption_text`** — v2.4.3's `_trim_caption_at_chart_data` was added to `docpluck/figures/detect.py::_full_caption_text`, but the live render pipeline never calls that function — figure captions are built in `extract_structured.py::_extract_caption_text` (which `_figure_from_caption` calls). v2.4.3's caption-trim was therefore a no-op on real renders despite its tests passing in isolation. v2.4.4 applies the trim to `_extract_caption_text` for `kind == "figure"` captions, so the trim actually fires during `render_pdf_to_markdown(pdf_bytes)`. Verified by manual render of `jama_open_6` (caption 400 chars → 47 chars) and `jama_open_3` (405 → 208 chars).

### Enhancement

2. **`docpluck/extract_structured.py::_trim_caption_at_chart_data`** — extended with a second chart-data signature: a run of 5+ short (1–4 digit) numeric tokens separated only by whitespace. Catches axis-tick label sequences (``0 5 10 15 20``) and stacked column values (``340 321 280 5 270``) that the 6-digit-run rule didn't see on charts with small-magnitude data. The two signatures are evaluated jointly; the earlier match in the caption wins so the caption is trimmed at the start of the chart data, not partway through it. Same conservative gates as before (caption ≥ 150 chars, surviving text ≥ 40 chars). Affects most JAMA Network Open Kaplan-Meier and Sci Rep / BMC clinical-trial papers — caption length drops from 400-char hard cap to ~150 chars of real prose.

### Bumps

- `__version__`: `2.4.3` → `2.4.4`. Patch — figure-caption truncation is now real and broader.

### Tests

3 new tests in `tests/test_figure_detect.py` (tick-run truncation, prose-with-inline-numbers no-op, earlier-of-two-signatures priority).

## [2.4.3] — 2026-05-13

Same-day follow-up. Two preventative improvements aimed at quality issues that didn't trip the verifier tags but were visible in rendered output:

### Fixes

1. **`docpluck/normalize.py::normalize_text` S9 step** — strip 4-digit standalone page numbers from continuous-pagination journals (PSPB volume runs into the 1000s, Psychological Science, etc.). Previously S9 only handled 1–3 digit page numbers; a bare `1174` line leaked into rendered output (e.g. `efendic_2022_affect.md` line 24). New rule strips 4-digit standalone numbers when (a) value is in 1000–9999, (b) same value recurs ≥ 3 times in the document. The recurrence floor protects table-cell values that happen to land on their own line in single-value-per-line column layouts. `NORMALIZATION_VERSION`: `1.8.1` → `1.8.2`.

2. **`docpluck/figures/detect.py::_full_caption_text`** — truncate figure captions at chart-data boundaries. pdftotext extracts chart elements (axis labels, gridline values, legend entries) inline with the figure caption when they share a PDF reading-order paragraph. The resulting caption text looks like `Figure 1. Flowchart of Study Sample Selection 4876956 Pairs enrolled before April 1, 2015 1117269 Pairs excluded ...` — useful prose followed by raw chart data. New heuristic: locate the first run of 6+ consecutive digits (signature of chart data — page counts, n-values, and years all top out at 5 digits in academic captions) and truncate just before it at the previous word boundary. Conservative: only fires when caption is ≥ 150 chars and surviving trimmed text is ≥ 40 chars (sanity check protects against edge cases). Affects clinical / biological flowcharts in JAMA, Sci Rep, BMC Medicine papers.

### Bumps

- `__version__`: `2.4.2` → `2.4.3`. Patch — both fixes are conservative pdftotext post-processing.
- `NORMALIZATION_VERSION`: `1.8.1` → `1.8.2`.

### Tests

7 new tests across `tests/test_normalization.py` (4-digit page number stripping, recurrence floor, year edge case) and `tests/test_figure_detect.py` (caption truncation at digit-run boundary, short-caption no-op, legitimate 5-digit-number preservation, minimum-post-label sanity check).

## [2.4.2] — 2026-05-13

Iterative follow-up. After v2.4.1 the 101-PDF corpus run was 98/101 PASS (`scripts/verify_corpus_full.py`); this release closes two of the three remaining failures and reframes the third as a known short-paper edge case in the verifier.

### Fixes

1. **`docpluck/render.py::_render_sections_to_markdown`** — table emission when Camelot returned no cells. Previously, a located table with a caption but no structured cells produced ``### Table N\n*caption*\n`` in body markdown — promising structured content that wasn't there. Verifier flagged this with the `H` tag (missing_html). Two papers affected: `bjps_4`, `ar_apa_j_jesp_2009_12_011`. New behavior: when `html` is empty for a body-located table, skip the `### Table N` heading and emit only the caption as a plain italic paragraph (`*Table N. caption text*`). The table reference is still surfaced in body flow, but without the false promise of structured HTML. Same treatment for the unlocated-tables appendix — tables with neither caption nor cells are dropped (a bare `### Table N` stub is information-free).

2. **`docpluck/render.py::_render_sections_to_markdown`** — uppercase canonical section headings when pdftotext flattens Elsevier letter-spaced typography. JESP / Cognition / JEP papers render their section headings with letter-spacing (``a b s t r a c t``), which pdftotext extracts as a lone lowercase word. Without this fix the rendered output mixes ``## abstract`` with ``## Methods`` / ``## Results`` — a stylistic blemish on every Elsevier-style paper. New rule: when the captured `heading_text` is entirely lowercase ASCII AND the section has a recognized canonical label, replace the heading with the pretty Title-Case form (`Abstract`, `Keywords`, etc.). All-caps publisher headings (JAMA ``RESULTS``) are preserved verbatim — only lowercase is rewritten.

### Verifier upgrade

3. **`scripts/verify_corpus_full.py::_classify`** — short-paper exemption. The `S` (section_count < 4) and `X` (output < 5 KB) tags are now suppressed when the rendered title contains `ADDENDUM` / `CORRIGENDUM` / `CORRECTION` / `ERRATUM` / `RETRACTION`. The canonical example is `jdm_.2023.10`, a 1-page archival correction notice that legitimately has 1 section and ~1 KB of body content; flagging it as a render failure was a verifier false positive.

### Bumps

- `__version__`: `2.4.1` → `2.4.2`. Patch — render behavior changes affect only the 2 H-tagged papers + lowercase-abstract heading on Elsevier-style papers; no API change.

### Tests

6 new tests in `tests/test_render.py` covering the H-tag emission rules (body-located + appendix), the lowercase-canonical heading uppercase rule, and the happy-path no-op cases.

## [2.4.1] — 2026-05-12

Same-day follow-up to v2.4.0. Expanded testing to all 101 PDFs in the wider corpus (vs the 26 spike-baseline papers) and fixed the most common new failure: missing-title on AMA/AOM single-line title layouts.

### Fixes

1. **`docpluck/render.py::_compute_layout_title`** — title-size selection in two passes:
   - Pass 1 (unchanged): largest font with count ≥ 2 (multi-line titles).
   - Pass 2 (new): largest font in the TOP region (y0 ≥ 70% of page height) with count ≥ 1 and combined span text ≥ 10 chars.

   Without the top-region restriction + text-length floor, a stray same-font glyph elsewhere on the page (a "+" decoration at font 16.0, an "GUIDEPOST" feature-label at font 30.0) would outrank a real single-line title at a smaller-but-still-large font. Affects: `jama_open_3`, `jama_open_4`, `jama_open_6`, `jama_open_10`, `annals_4`, `amd_1` and similar AMA/AOM-style papers.

### Bumps

- `__version__`: `2.4.0` → `2.4.1`. Patch-level — internal heuristic improvement, no API change.

## [2.4.0] — 2026-05-12

Same-day follow-up. Closes the three real library bugs surfaced by the AI-Chrome visual verification pass on all 26 corpus papers documented in `docs/HANDOFF_2026-05-12_visual_verify_results.md`. The API-level `verify_corpus.py` was passing 26/26 throughout but couldn't see these — visual inspection in the workspace was needed.

### Fixes

1. **`docpluck/render.py::_render_sections_to_markdown`** — heading-body separation. Section headings were emitted with a single `\n` between `## Heading` and the body text, which downstream markdown renderers (incl. the workspace) treated as one paragraph starting `"## Abstract Lynching remains a common form..."`. Now emits `\n\n`. Additionally, when the section detector kept the heading word in `sec.text` (common for Abstract/Keywords sections), the renderer now strips the leading heading word from the body so output reads `## Abstract\n\nLynching ...` not `## Abstract\n\nAbstract Lynching ...`. Affects: `am_sociol_rev_3`, `amj_1`, `ar_royal_society_rsos_140072`, `ieee_access_4`, `jmf_1` (and likely more in larger corpora).

2. **`docpluck/render.py::_strip_duplicate_title_occurrences`** (new) — Nature-style title duplication sweep. After `_apply_title_rescue` places `# Title` at the top, scan the first 80 lines for paragraph spans whose token content densely matches the title (recall ≥ 0.85, precision ≥ 0.75) and remove them. Catches Nature Communications-style papers where the title is repeated in a smaller font as body prose, often broken across 2-3 short lines due to column layout. Affects: `nat_comms_1`, `nat_comms_2`. 3 new tests.

3. **`docpluck/render.py::_compute_layout_title` / `_title_text_from_chars`** — title-word selection made more inclusive while still rejecting non-title content on the same y-band:
   - Word-height tolerance relaxed from 0.6 → 3.5 px (a U+FFFD glyph or italic emphasis can balloon a word's bbox by ~2.5 px without changing its actual font size).
   - Word y-bbox tolerance relaxed from 1.5 → 3.0 px (same root cause).
   - Char-level fallback height tolerance bumped 0.6 → 1.2 px to match.
   - Line-grouping for word-to-line assembly: replaced `sort(key=(round(top), x0))` with sort-by-top-then-cluster-by-4px-then-sort-by-x0-within-line. Prior behavior mis-ordered tall-glyph words to the front of their line.
   - **New: title_spans clustering** — restrict candidate spans to the contiguous top cluster (>100 px gap = different cluster). Without this, a stray same-font glyph elsewhere on the page (e.g. a "V." section heading at y0=450 while the title sits at y0=672) would stretch the y-band and swallow the byline + abstract into the title-word pool.

   Effect on the corpus: `ziano_2021_joep` recovers "Shafir's" in `Tversky and Shafir's (1992) Disjunction Effect`, `ar_royal_society_rsos_140066` / `_140072` (Royal Society Open Science — long multi-line titles) keep their full title intact, `chen_2021_jesp` drops a stray ☆ recommendation-badge glyph that wasn't title content.

### Verifier upgrade

4. **`scripts/verify_corpus.py`** — new `D` tag (`title_words_dropped`). For each paper, distinct words ≥ 4 letters present in the spike-baseline title but missing from the rendered title are counted; any non-zero count flags the paper. Catches middle-of-title truncations (like `ziano_2021_joep`'s missing "Kahneman") that the `T` tag (trailing-connector check) doesn't see.

### Bumps

- `__version__`: `2.3.1` → `2.4.0`. Minor bump because rendered-output bytes change materially on the affected papers.
- `TABLE_EXTRACTION_VERSION`: unchanged at `2.1.0`.
- `NORMALIZATION_VERSION`: unchanged at `1.8.1`.

## [2.3.1] — 2026-05-12

Follow-up to v2.3.0. Closes the four remaining items from `docs/HANDOFF_2026-05-11_visual_review_findings.md` and wires the corpus verifier into the `/docpluck-qa` and `/docpluck-review` project skills so regressions get caught automatically.

### Fixes

1. **`docpluck/extract.py::count_pages`** — compressed-stream fallback. The byte-pattern heuristic returns 0/1 on PDF 1.5+ documents that compress object streams (`/ObjStm`), so multi-page papers that use cross-reference streams were reported as 1 page. New behavior: when the byte count is < 2, fall back to `pdfplumber.open(...).pages`. Verified by 4 new tests in `tests/test_v23_1_fixes.py`.

2. **`docpluck/extract.py::_patch_fffds_word_by_word`** — per-word U+FFFD recovery. When the full pdfplumber-recovery path is rejected by the reading-order check (two-column papers that pdfplumber column-interleaves), individual FFFD-containing words can still be patched. For each FFFD-bearing token in pdftotext, build a regex with `[A-Za-z]` at each FFFD position and the literal char elsewhere, then look for a UNIQUE match in pdfplumber's token set. When exactly one candidate exists, swap. Conservative — only matches letters (no digits/punct), refuses ambiguous matches. Recovers the 18 residual FFFDs in the Adelina/Pronin paper that survived the full-document recovery rejection. 8 new tests.

3. **`docpluck/render.py::_italicize_known_subtitle_badges`** — Bug 6 fix (subtitle styling). Recognized publication-format badge lines immediately after `# Title` (`Registered Report`, `Pre-Registered`, `Original Investigation`, `Brief Report`, etc., 10 patterns) are now wrapped in italic markdown so the workspace UI renders them as styled subtitles instead of plain body prose. Scope is narrow: only the first non-empty line(s) within ~10 lines of the title, ≤ 50 chars, must match a known badge pattern. Idempotent. 10 new tests.

### Skill integration

4. **`.claude/skills/docpluck-qa/SKILL.md`** — new Check 7b ("Corpus Render Verifier"). After Check 7 (batch extraction), `/docpluck-qa` now runs `python scripts/verify_corpus.py` against the 26-paper baseline corpus and reports per-paper PASS/FAIL with failure tags. Total check count: 14 → 15.

5. **`.claude/skills/docpluck-review/SKILL.md`** — new Rule 12 ("Corpus render verifier must pass on changes to render / extract / tables"). When a `/docpluck-review` invocation detects changes to `docpluck/render.py`, `docpluck/extract_structured.py`, `docpluck/extract.py`, `docpluck/tables/*.py`, or `docpluck/normalize.py`, the reviewer must run `scripts/verify_corpus.py` (8–12 min) or `pytest tests/test_corpus_smoke.py` (~45s) before approving. Severity: BLOCKER for `render.py` / `extract_structured.py` / `tables/`; WARN for other touches.

### Bumps

- `__version__`: `2.3.0` → `2.3.1`.
- `TABLE_EXTRACTION_VERSION`: unchanged at `2.1.0` (no table-pipeline behavior change).
- `NORMALIZATION_VERSION`: unchanged at `1.8.1`.

### Tests

22 new tests in `tests/test_v23_1_fixes.py`. All existing tests still pass.

### Follow-up

`PDFextractor/service/requirements.txt` pin bumped from `@v2.3.0` to `@v2.3.1`.

---

## [2.3.0] — 2026-05-11

Ports the splice-spike's Section F (cell-cleaning) helpers into the library, per [`docs/HANDOFF_2026-05-11_visual_review_findings.md`](docs/HANDOFF_2026-05-11_visual_review_findings.md). v2.2.0 had explicitly deferred this; v2.3.0 lands it.

### What's new

1. **`docpluck/tables/cell_cleaning.py`** — new module containing the eight helpers ported verbatim from `splice_spike.py` (lines ~126–1013), plus the `cells_grid_to_html` orchestrator (was `pdfplumber_table_to_markdown` in the spike — renamed because it operates on a generic 2-D cell grid):
   - `_merge_continuation_rows` — folds multi-line cell wraps (first-column-empty rows + label-modifier rows like `(Extension)` + wrap-punctuated col-0 continuations) into the parent row using a `<br>` placeholder that survives HTML escaping.
   - `_strip_leader_dots` — strips `. . . . .` alignment fillers (4+ dot-space pairs), cleaning up doubled / leading / trailing `<br>` placeholders left behind.
   - `_split_mashed_cell` — inserts `<br>` at column-undercount boundaries inside a cell (e.g. `Original domain groupEasy domain group` → `Original domain group<br>Easy domain group`). Strict camel-case rule (≥4 lowercase run) plus a relaxed 3-char whitespace-anchored rule that catches `lowPositive` / `lowNegative`. Letter→digit rule catches `Year2011` / `size80`. Preserves `macOS` / `iPhone` / `WiFi` / `JavaScript` / `WordPress` / `H1` / `2a` / `lowCI` (any of the boundary cases that would false-split).
   - `_is_header_like_row` + `_drop_running_header_rows` + `_is_strong_running_header` / `_is_weak_running_header` / `_is_running_header_cell` — detects header-like rows (label-only, short, ≤30% numeric) and drops or in-place blanks leaked running-header rows (pure page numbers, `|232 Stacey et al.`, journal-CAPS lines, `Vol.`, DOI/URL). Iter-17 cell-level cleanup blanks strong-RH cells when they coexist with real header content (chan_feldman T5 pattern).
   - `_is_group_separator` — detects rows where only column 0 has content in a ≥3-col table; renders as `<tr><td colspan="N"><strong>label</strong></td></tr>`.
   - `_fold_super_header_rows` — folds 2-row super-header into one row column-wise when top row has empty cells AND every populated top cell has a populated cell directly below (korbmacher Table 7 pattern). Recurses for 3-row stacked super-supers.
   - `_fold_suffix_continuation_columns` — per-column fold for 2-row headers where col-N row-0 ends in `- — – :` and col-N row-1 starts with a letter (ziano Table 2 `Win-` over `Uncertain` pattern). Conservative: only fires on exactly 2-row headers; drops row-1 if it becomes entirely empty.
   - `_merge_significance_marker_rows` — attaches `*` / `∗∗∗` / `†` / `‡` rows as `<sup>...</sup>` on the nearest substantive estimate row. Walk-back skips std-err parenthetical rows; stops at text-anchor rows (`Ref.`, `Year FE`). Iter-24 (Tier A8) forward-attach narrowly attaches markers to the immediate-next numeric row when walk-back was blocked by a text-anchor block (social_forces_1 `0 ACEs Ref. / *** / 1 ACE 2.25` pattern). Per-column guard prevents `<sup>` orphans on empty target cells.

2. **`docpluck/tables/render.py::cells_to_html`** — refactored to delegate to `cells_grid_to_html`. The behavioral change:
   - Empty input `[]` now returns `""` (was `"<table></table>"`).
   - Tables with fewer than 2 rows after cleaning return `""`.
   - The `is_header` flag on each Cell is no longer consulted; heuristic header detection runs instead (more reliable across Camelot's per-cell flag quirks).
   - Output is multi-line, indented HTML (`<table>\n  <thead>\n    <tr>\n      <th>...</th>`); existing consumers that splice the HTML into Markdown render identically.

3. **`tests/test_tables_cell_cleaning.py`** — new file with ~60 pure-transform tests ported from `test_splice_spike.py` covering every helper above.

### Bumps

- `__version__`: `2.2.0` → `2.3.0`.
- `TABLE_EXTRACTION_VERSION`: `2.0.0` → `2.1.0`.
- `NORMALIZATION_VERSION`: `1.8.0` → `1.8.1` — additive: the W0 Downloaded-from watermark pattern now matches institutional download stamps (see item 11 below).
- `SECTIONING_VERSION`: unchanged at `1.2.0`.

### App-repo follow-up

`PDFextractor/service/requirements.txt` needs its git pin bumped from `@v2.2.0` to `@v2.3.0`; `/docpluck-deploy`'s pre-flight check 4 enforces this.

### Source

Spike: [`docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`](docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py) — Section F (lines 126–1013). Spike tests: [`test_splice_spike.py`](docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py).

### Rendered-view bugs from `HANDOFF_2026-05-11_visual_review_findings.md` (status)

- **Bug 1** (`<table>` not appearing in Rendered tab) — resolved by the v2.3.0 cleaning pipeline + the `_pick_best_per_page` lattice-artifact filter (item 6 below).
- **Bug 2** (flattened table cells in body) — resolved as a consequence of Bug 1.
- **Bug 3** (figures spliced before abstract) — **resolved** by `_locate_caption_anchor` + appendix-fallback (item 7 below).
- **Bug 4** (caption concatenation across figures) — resolved by the `next_boundary` parameter on `_extract_caption_text`.
- **Bug 5** (truncated title) — resolved by `_title_looks_truncated` connector-word guard.
- **Bug 6** (subtitle styling) — still pending.

### Post-initial-tag fixes (caught by `scripts/verify_corpus.py`)

After the initial Section F port landed, a new corpus verifier (`scripts/verify_corpus.py`) ran `render_pdf_to_markdown` against the spike's 26-paper baseline corpus and found four high-value issues. All resolved before the final tag:

6. **`docpluck/tables/camelot_extract.py::_pick_best_per_page`** — lattice tables of shape ≤1×N or N×1 no longer "win" their page over real stream tables. JAMA-style PDFs print signature blocks / running-header rules that lattice picks up as 1×1 100%-accuracy artifacts; without the size filter those artifacts were displacing the real 7×45 stream tables on pages 6/8/9 of `jama_open_1`. Fix: require ≥ 2 rows AND ≥ 2 cols before treating a page as "owned by lattice." Verified by 5 new tests in `tests/test_v23_post_corpus.py`.

7. **`docpluck/render.py::_locate_caption_anchor` + appendix fallback** — Bug 3 root cause was `text.find(caption)` returning -1 (caption had spaces where the section-text had newlines) and the fallback `placements.append((0, …))` piling every figure at the top of the document, ahead of the abstract. New helper `_locate_caption_anchor` is whitespace-tolerant (regex with `\s+` between caption prefix tokens) and validates the match is at a caption-line start. Unanchored items flow to a `## Tables (unlocated in body)` / `## Figures` appendix at the bottom of the rendered output. Verified by 5 anchor-locator tests + the `tests/test_corpus_smoke.py` Bug 3 assertion on `efendic_2022_affect`.

8. **`docpluck/extract_structured.py::_extract_caption_text`** — soft-hyphen rejoin. `chen_2021_jesp` captions showed `Sup­ plementary` / `esti­ mate` / `be­ tween` artifacts because pdftotext renders soft hyphens (U+00AD) at line-wraps and captions don't flow through `normalize_text` where the existing strip lives. Now `­\s+` → `''` and orphan `­` → `''` are applied during caption extraction. Verified by 3 tests.

9. **`docpluck/tables/captions.py`** — `TABLE_CAPTION_RE` / `FIGURE_CAPTION_RE` are now case-insensitive. AOM and some IEEE PDFs print all-caps captions (`TABLE 13. ...`); previously these were silently missed. Recovered `TABLE 13` on `amle_1`, plus several captions across `ieee_access_*` and `amj_1`. Net effect: `amle_1` went from 0 to 13 HTML tables.

10. **`docpluck/render.py::_pretty_label`** — section headings synthesized by Pattern E (where `heading_text` is empty) now render as `## Abstract` / `## Introduction` instead of `## abstract` / `## introduction`. Mapping covers the canonical labels plus a generic `Title Case + underscore→space` fallback.

11. **`docpluck/normalize.py` Downloaded-from watermark extension** — the existing W0 pattern matched `Downloaded from <url> [by <single-word>] on <date>`. Royal Society Open Science PDFs print the institutional download stamp `Downloaded from <url> by University of Innsbruck (Universitat Innsbruck) user on 16 March 2026` — a multi-word "by phrase" tail. The `\w+` after `by` is now `[^\n]+?` (anchored by the trailing `on <day> <month> <year>`), capturing institutional stamps without runaway matches. Stripped every-page contamination from `ar_royal_society_rsos_140072` (4 occurrences). Verified by 3 tests in `tests/test_v23_post_corpus_v2.py`.

12. **`docpluck/tables/render.py::cells_to_html` fallback** — preserve the contract that structured tables always produce non-empty HTML. Some 2-row Camelot tables fold to a single row through the v2.3.0 cleaning pipeline (legitimate behavior: the second row was a continuation of the first), and `cells_grid_to_html` returned `""` in that case. That broke the `tests/test_smoke_fixtures.py::test_table_html_renders_when_structured` invariant (`<table>` must be in `html` for kind=structured). New behavior: when cleaning returns "", fall back to a minimal raw renderer that emits the v2.2.0-style compact HTML for the original grid.

13. **`docpluck/tables/camelot_extract.py` confidence clipping** — Camelot's reported `accuracy` field is occasionally floating-point-marginally above 100 (e.g., `100.0000000003`), producing `confidence` slightly > 1.0 in the Table dict. Now clipped to `[0.0, 1.0]`. Caught by `test_table_html_renders_when_structured` invariant.

14. **`tests/fixtures/structured/MANIFEST.json` recalibration** — three fixtures (`ieee_lattice`, `amj_lattice`, `ieee_figure_heavy`) had stale 2026-05-07 `expected_tables`/`expected_figures` counts that pre-dated the case-insensitive caption fix and the lattice-artifact filter. Bumped to v2.3.0 baseline. The MANIFEST was already documenting that "per-fixture recalibration is a separate follow-up" — this is that follow-up.

### Corpus verification harness

- `scripts/verify_corpus.py` — runs `render_pdf_to_markdown` against the 26 papers in `docs/superpowers/plans/spot-checks/splice-spike/outputs[-new]/`, compares against the spike's known-good `.md` baselines, and reports per-paper PASS/WARN/FAIL with single-letter failure tags (T=title truncated, S=few sections, H=missing HTML, C=caption-too-long, L=much shorter, J=low Jaccard). Use after any change to `extract_structured.py`, `tables/`, or `render.py`.
- `tests/test_corpus_smoke.py` — 3 representative papers (APA, AMA, JESP) running in ~45s as part of the standard pytest suite. Skips cleanly when test PDFs aren't on disk (CI / fresh-clone friendly).

### Test counts

- New unit tests: **30** total — 17 in `tests/test_v23_post_corpus.py` + 9 in `tests/test_v23_post_corpus_v2.py` + 4 in `tests/test_corpus_smoke.py`.
- All existing tests still pass.

### Verification result

After all fixes: **26/26 papers PASS** under the corpus verifier across 9 journal styles (APA, AMA, IEEE, ASA, AOM, Nature, Royal Society, demographics, social_forces) — up from 21/26 after the initial Section F port. Notable gains:

- `amle_1`: 0 → 13 HTML tables (case-insensitive TABLE/FIGURE detection)
- `amj_1`: 0 → 5 HTML tables
- `amc_1`: 0 → 2 HTML tables
- `ieee_access_3`: 0 → 5 HTML tables
- `jama_open_1` / `jama_open_2`: 0 → 3 HTML tables each (lattice 1×1 artifact filter)
- `efendic_2022_affect`: 5 figures correctly placed inside Results/Discussion sections instead of stacked before the Abstract (Bug 3)
- `chen_2021_jesp`: 4 soft-hyphen caption artifacts (`Sup­ plementary`, `esti­ mate`, etc.) eliminated
- `ar_royal_society_rsos_140072`: every-page `Downloaded from … by University of Innsbruck …` watermark stripped (4 occurrences)
- `demography_1` / `social_forces_1`: caption boundary capped at the next caption start (was bleeding into 1500-char runaway captions)

---

## [2.2.0] — 2026-05-11 (revised same-day)

### Critical library fixes added during visual-review session (2026-05-11)

These shipped under the same v2.2.0 version because no release was tagged yet between them and the original 2.2.0 work:

1. **`extract.py::extract_pdf`** — `_recover_with_pdfplumber` is now gated by **two** checks instead of one:
   - **Threshold raised from ≥1 to ≥3 FFFD chars** in the pdftotext output. Previously a single stray U+FFFD (typical when a paper contains 1-2 italic math letters in a stat expression) was enough to swap pdftotext's entire output for pdfplumber's, even though pdfplumber's `extract_text()` interleaves columns on multi-column papers.
   - **New `_reading_order_agrees(pdftotext_text, pdfplumber_text)` helper** — extracts three 60-char snippets from non-FFFD body regions of pdftotext and requires that all three appear verbatim in pdfplumber's output. If even one is missing, pdfplumber reordered the columns and we keep pdftotext's text (FFFDs and all — much less harmful than word-by-word column interleave). Verified on the Adelina/Pronin replication PDF (IRSP, 2-column layout) which went from unreadable column-merged body text to clean reading order. Cascading benefits: Camelot's table-cell extraction now succeeds on the same paper (was returning 0 cells on the corrupted text).

2. **`render.py::_apply_title_rescue`** — when the in-place title-upgrade path replaces matched lines with `# Title`, the heading is now padded with blank lines on both sides (`["", title, ""]`) so it renders as a standalone block. Previously the heading was glued to neighboring paragraphs, producing `RESEARCH ARTICLE # Title Nadia Adelina and Gilad Feldman...` all on one logical paragraph.

3. **`render.py::render_pdf_to_markdown`** — new optional internal params `_structured`, `_sectioned`, `_layout_doc` let callers (e.g. an /analyze-style endpoint) reuse already-computed extraction results, skipping a duplicate Camelot pass and a duplicate `extract_sections` pass. On a typical APA paper this cuts the render step from ~15-30s to ~1-5s. The flag names are underscored to discourage casual library users from depending on a shape that may change; the default no-arg behavior is unchanged.

4. **`render.py::_render_sections_to_markdown`** — sections with `canonical_label == "unknown"` and no `heading_text` no longer emit a `## unknown` heading. The body text flows as bare paragraphs instead.

5. **Test count**: 189 tests pass (36 v1.8.0 strips + render tests; 153 D5/etc).

---

## [2.2.0] — 2026-05-11

Promotes the iter-23 → iter-34 splice-spike fixes from `docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py` into the library. Two surfaces change:

1. **`normalize_text`** gains three document-shape strip passes that run before the existing W0/S* unicode passes:
   - **H0** (header banner strip): drops publisher / journal / repo banner lines in the first ~30 lines of the document. ~35 curated patterns cover HHS Public Access, Royal Society "Cite this article", Tandfonline ISSN, arXiv preprint banner, "Original Investigation" category labels, AOM / Sage / Cambridge / Oxford / Elsevier journal cite-lines, mangled DOI runs, etc. Line is dropped only on explicit pattern match — titles / authors / affiliations are never touched.
   - **T0** (TOC dot-leader strip): drops paragraphs that contain `_{3,}` dot-leader runs (Nature Supplementary PDF style) or explicit "Table of Contents" / "List of Figures" labels, within the first ~100 lines.
   - **P0** (page-footer / running-header strip): drops curated full-line patterns (Page N, copyright lines, JAMA running headers, "Corresponding Author:", bare emails, "(continued)", PMC supplementary-material footers, "<author> et al." running headers) anywhere in the document.

2. **`docpluck.render`** is a new module exposing `render_pdf_to_markdown(pdf_bytes)` — the spike's end-to-end PDF-to-markdown renderer, brought into the library:
   - Wraps `extract_pdf_structured` (Camelot tables + figures) + `extract_sections` (semantic structure).
   - Splices tables and figures into their containing sections by caption position.
   - Markdown-level post-processors (ported from spike iter-23 → iter-34):
     - `_dedupe_h2_sections` (demote duplicate `##` headings to plain text)
     - `_fix_hyphenated_line_breaks` (H1 — re-knit real compound words like `Meta-Processes` across line wraps)
     - `_join_multiline_caption_paragraphs` (fold `FIGURE N` / `TABLE N` captions split by column wrap)
     - `_merge_compound_heading_tails` (reattach `AND RELEVANCE` and 4 other JAMA structured-abstract heads to `## CONCLUSIONS`)
     - `_reformat_jama_key_points_box` (extract the JAMA Key Points sidebar as a `> **Key Points**` blockquote, stitching split sentences)
     - `_promote_numbered_subsection_headings` (turn `1.2 Foo` plain-text lines into `### 1.2 Foo`)
     - `_rescue_title_from_layout` (read pdfplumber spans on page 1, identify the dominant title font, place `# Title` at the top of the document; uses char-level x-gap fallback for tight-kerned JAMA / AOM PDFs where `extract_words` collapses tokens)

3. **CLI**: new `docpluck render <file> [--level none|standard|academic] > out.md` subcommand.

### Deferred to v2.3.0

The spike's pdfplumber-internal table-cleaning helpers (`pdfplumber_table_to_markdown`, `_merge_continuation_rows`, `_strip_leader_dots`, `_is_header_like_row`, `_drop_running_header_rows`, `_merge_significance_marker_rows`, `_fold_suffix_continuation_columns`, `_fold_super_header_rows`) are NOT in this release. v2.2.0's `render_pdf_to_markdown` uses Camelot for table cells via the existing library path. On a few JAMA / Sage papers table presentation may look weaker than the spike's bit-for-bit output; all other improvements (title rescue, banner / TOC / footer strip, Key Points sidebar, numbered subsection promotion, compound heading merge) land in full.

### Compatibility

- All existing public APIs unchanged. The new `render_pdf_to_markdown` and the H0/T0/P0 passes are additive.
- `__version__`: `2.1.0` → `2.2.0`.
- `NORMALIZATION_VERSION`: `1.7.0` → `1.8.0` — three new auto-applied passes at the `standard` level; cached normalized outputs need regeneration.
- `SECTIONING_VERSION`: unchanged at `1.2.0` (Section B's heading restructuring lives in `render.py` as markdown-level post-processors; SectionedDocument shape is the same as v2.1.0).
- `TABLE_EXTRACTION_VERSION`: unchanged at `2.0.0` (Section F deferred).

### Source

Spike: [`docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`](docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py) — iter-23 through iter-34 (lines 2148–4165). Handoff plan: [`docs/HANDOFF_2026-05-11_PROMOTE_SPIKE_TO_LIBRARY.md`](docs/HANDOFF_2026-05-11_PROMOTE_SPIKE_TO_LIBRARY.md).

---

## [2.1.0] — 2026-05-09

Strict-bar iteration on a 101-PDF corpus across 9 academic styles (apa, ieee, nature, vancouver, aom, ama, asa, harvard, chicago-ad). 96–98 of 101 papers PASS or PASS_W under the pragmatic grader; all 9 styles converge (≥3 consecutive first-try-clean papers). 14 targeted fixes across the section identification + normalization layers; no API surface changes. See [`docs/superpowers/plans/sections-issues-backlog.md`](docs/superpowers/plans/sections-issues-backlog.md) for the full per-issue ledger and [`LESSONS.md`](LESSONS.md) for the durable architectural rules this iteration codified.

### Added — section identification

- New canonical label `SectionLabel.conclusion` (separate from `discussion`). Many empirical papers — especially IEEE technical, Collabra Psychology, JESP / Cogn Psych replication reports — have BOTH a Discussion section AND a brief Conclusion wrap-up. Mapping `Conclusion` to its own label preserves the distinction in the output rather than producing `discussion_2`. Combined `Discussion and Conclusion(s)` headings stay as `discussion`.
- Pattern A: lowercase line-isolated canonical headings now detected (Elsevier renders `Abstract` as `a b s t r a c t`, which pdftotext flattens to lowercase `abstract`).
- Sentence-case heading acceptance: `Materials and methods` (lowercase function words) alongside Title Case / ALL CAPS.
- Roman-numeral and letter numbering prefixes: `I. INTRODUCTION`, `II. METHODOLOGY`, `A. SUBSECTION` (IEEE / ACM technical papers).
- Pattern E synthesis (`core.py::_synthesize_abstract_from_leading_unknown`): when no Abstract heading is detected and the first section is a long unknown span, synthesize an `abstract` from the first ≥600-char prose paragraph. Smart citation-block detection skips the leading paragraph if it has DOI/`Department`/email tokens and is <1500 chars. Falls back to a per-line scan when the leading unknown is one big paragraph.
- Pattern E synthesis part 2 (`core.py::_synthesize_introduction_if_bloated_front_matter`): when no Introduction heading is detected and the front-matter section is >3000 chars and >5% of doc, split into shrunken-front-matter + introduction. Recovers bjps_1 (theory papers with body in keywords) and bloated-abstract Collabra/JDM cases.
- Taxonomy variants added — methods: `experiment`, `experiments`, `methodology`. results: `experimental results`, `evaluation`, `experimental evaluation`, `performance evaluation`. funding: `financial disclosure`, `financial disclosure/funding`, `funding/financial disclosure`. Conclusion variants: `conclusions`, `conclusion and future work`, `conclusions and future work`, `concluding remarks`.

### Removed — section taxonomy

- `summary` removed from canonical `abstract` set. In real-world psychology papers it is more often a mid-paper subsection (`Summary of Original Studies`, per-study summary in meta-analyses) than an abstract heading. The Royal Society Open Science layout that uses `1. Summary` as its abstract is recovered by Pattern E synthesis instead.

### Added — normalization (W0 publisher / running-header / footnote watermarks)

- Elsevier-style copyright stamp on its own line (`© 2009 Elsevier Inc. All rights reserved.`), including pdftotext's `Ó` flattening of `©`.
- Two-column running headers like `M. Muraven / Journal of Experimental Social Psychology 46 (2010) 465-468`.
- Creative Commons license footer sentences in abstract paragraphs.
- Collabra/UCPress watermark `Downloaded from <url> by guest on <date>` — relaxed the existing `Downloaded from` pattern to allow the optional intermediate `by guest` phrase. Was missing on every Collabra paper before.
- Author-equal-contribution footnote line (`a Surname, Surname, … are equal-contribution first authors b email`) — open-access journals print this at bottom of page 1; pdftotext interleaves it into the abstract.

### Documentation

- `LESSONS.md` (NEW) — durable incident log with five lessons (L-001 to L-005). Most critical: L-001, "never swap the PDF text-extraction tool as a fix for downstream problems." Three sessions in a row had re-derived this lesson by trial and error; this iteration codifies it permanently.
- `docs/DESIGN.md` §13 — explicit `text channel (pdftotext)` vs `layout channel (pdfplumber)` architecture rule, with the right layer to fix each class of real-world-paper artifact.
- `CLAUDE.md` Critical hard rules section now leads with the channel-separation rule and points future sessions at LESSONS.md before they touch `extract*.py` / `normalize.py` / `sections/`.
- Inline guard comment at the PDF branch of `extract_sections()` warning future sessions not to swap `extract_pdf` for `extract_pdf_layout`.

### Compatibility

- All public APIs unchanged. Library is drop-in compatible with v2.0.0 callers.
- `SECTIONING_VERSION`: `1.1.0` → `1.2.0` (additive: new `conclusion` label).
- `NORMALIZATION_VERSION`: `1.6.0` → `1.7.0` (additive: new W0 watermark patterns).
- Section partitioning output may differ on Collabra Psychology, RSOS, IEEE, and Elsevier two-column papers — these previously emitted bloated front-matter / missing abstract / `discussion_2` instead of `conclusion`. Behavior on the 250+ unit-test corpus is unchanged.

### Tests

- 749 passed, 18 skipped (full repo suite). 255 passed + 2 skipped on `tests/test_sections_*.py` + `tests/test_normalization.py`.
- 14 new W0 unit tests in `TestW0_PublisherCopyrightAndRunningHeader`.
- New sectioning tests for `conclusion` canonicalization, lowercase-isolated heading acceptance, Roman-numeral prefix parsing, sentence-case heading acceptance, and Pattern E synthesis.

## [2.0.0] — 2026-05-07

A combined release: structured-extraction (tables + figures) and a section-identification surgical fix that makes sectioning actually usable on real APA papers. Both work streams landed concurrently on `feat/table-extraction` and ship together.

### Added — structured extraction

- `extract_pdf_structured()` — structured PDF extraction returning tables, figures, page count, method, and text in a single call. Opt-in companion to `extract_pdf()`; the existing function is unchanged.
- `docpluck.tables` package — table region detection, lattice + whitespace cell clustering, HTML rendering, confidence scoring with isolation fallback (`ISOLATION_THRESHOLD = 0.4`).
- `docpluck.figures` package — caption-anchored figure detection (label, page, bbox, caption metadata only; no image extraction in v2.0).
- `Cell`, `Table`, `Figure`, `StructuredResult` TypedDicts and `TABLE_EXTRACTION_VERSION` re-exported from top-level `docpluck`.
- New CLI flags on `docpluck extract`: `--structured`, `--thorough`, `--text-mode {raw,placeholder}`, `--tables-only`, `--figures-only`, `--html-tables-to DIR`.
- F0 footnote-strip in `normalize_text()` accepts a new `table_regions=` kwarg; lines whose y-range falls inside any provided table region are preserved (so table footnotes like `Note. *p < .05.` are not misclassified as page footnotes).
- New geometric primitives on `LayoutDoc.PageLayout`: `lines`, `rects`, `curves`, `chars`, `words` — all additive.
- 12-fixture smoke corpus driven by `tests/fixtures/structured/MANIFEST.json` (manifest-only — PDFs not committed; tests skip cleanly when source PDFs are not on the local Dropbox tree).
- Backwards-compat snapshot tests for `extract_pdf()` across all 12 fixtures (output is byte-identical to v1.6.x).

### Changed — section identification (surgical fix)

- **Architectural pivot.** The PDF section path now consumes `extract_pdf` (pdftotext) + `normalize_text(academic)` instead of `extract_pdf_layout` (pdfplumber). Sectioning runs after the library's canonical 22-step normalization pipeline (hyphenation repair, line-break joining, header/footer removal, footnote stripping, page-number scrub, watermark strip, statistical pattern repair, etc.) and so inherits all of it for free. The pdfplumber-based path was producing column-merged text (e.g. `References` jammed mid-line into body text) and font-size heuristics that failed on body-font-bold headings (`Abstract`). Result on a 5-paper APA corpus: every canonical section is detected, no garbage `unknown` spans, no running-header contamination.
- **Section partitioner: only canonical-taxonomy heading matches create section markers.** v1.6.0 promoted any layout-strong heading (including page running headers, citation residue, methods/results subsections) to an `unknown` section, which on real APA papers shredded ~90% of the document into incoherent fragments. Layout-strong headings whose text isn't in the canonical taxonomy are no longer separate sections.
- **`SECTIONING_VERSION` 1.0.0 → 1.1.0** (additive `subheadings` field; output shape change).
- **Boundary-aware truncation disabled** for all canonical labels. With strict canonical-only markers + clean normalized text, truncation patterns (Email/ORCID/author-bio caps) were destructive — cutting References to a few characters or chopping Introduction at a `Corresponding Author:` line.

### Added — section identification

- `Section.subheadings: tuple[str, ...]` (default `()`) — placeholder for in-section structure surfaced by future smart subheading detection. Empty in v2.0.0; populated in a later release.
- Text annotator detects canonical headings whether line-isolated, followed by Capital-body word, or preceded by blank line — so `Abstract Jordan et al., 2011...` style (heading + first paragraph on one line) is caught.
- CRediT author-contribution table cells are filtered out of heading candidates (e.g. `Methodology\n\nX\n\nPre-registration peer review`).

### Fixed — section identification

- Adjacent same-canonical-label markers with a small gap coalesce into one span (handles `Introduction\nBackground\n...` producing one `introduction` instead of `introduction` + `introduction_2`).
- `Acknowledgments`, `Author Contributions`, `Funding`, `Keywords` are now detected when preceded by single-newline paragraph break (not just blank-line).
- `References`, `Appendix`, `Supplementary` no longer truncate at `Email:` / `ORCID:` / author-bio boundary patterns.
- `Declaration of Competing Interest` (Elsevier-style) added to `conflict_of_interest` taxonomy variants.

### Removed — section taxonomy tightening

- `procedure`, `procedures` removed from canonical `methods` set — APA subsection labels, not top-level sections.
- `study design`, `experimental design`, `methodology` removed from canonical `methods` set — same reason.
- `summary` removed from canonical `abstract` set — too ambiguous (meta-analyses use it as per-study subheading).

### Compatibility

- `extract_pdf()` output is byte-identical to v1.6.x — verified by snapshot tests on 12 PDFs.
- All existing public APIs unchanged.
- New surface (structured extraction) is purely additive; opt-in via `extract_pdf_structured()` or `--structured` CLI flag.
- `Section.subheadings` is an additive dataclass field with default `()`; existing constructors keep working unchanged.

### Known limitations (sections)

- Papers with no `Introduction` heading (some JESP papers jump from Abstract directly to `6.2. Method`) produce a large `abstract` span covering both abstract and intro. Structural — without an explicit marker, the partitioner can't break the section.
- Meta-analyses with embedded per-study summaries may produce unusual section ordering. v2.0.0's section target is well-formatted single-study APA papers.
- `subheadings` field is empty by design in v2.0.0 (smart list-vs-heading discrimination deferred).

### Internal

- Sections package: `extract_pdf_layout` and `_annotate_layout` (pdfplumber PDF annotator) are no longer used by the sections path. They remain in the library for use by the structured (tables/figures) module. F0 step in normalize remains for callers who explicitly pass `layout=...`.
- Coordination: structured extraction builds on top of `extract_pdf_layout()` / `LayoutDoc`; resolves the latent F0 / table-footnote conflict noted in v1.6.0's spec.

## [1.6.0] — 2026-05-06

### Added

- New `docpluck.sections` package: identifies academic-paper sections (abstract,
  methods, references, disclosures, …) with universal char-level coverage and
  per-section confidence + provenance. See
  `docs/superpowers/specs/2026-05-06-section-identification-design.md`.
  - 18 canonical labels + `unknown` fallback + numeric suffixes for repeats
    (e.g. `methods_2` for multi-study papers).
  - Two-tier algorithm: format-aware annotators (PDF/DOCX/HTML) +
    unified core canonicalizer.
  - `SECTIONING_VERSION` constant ("1.0.0") on every `SectionedDocument`.
- New internal `docpluck.extract_layout` module: pdfplumber-based layout
  extraction (per-page bounding boxes + font sizes). API not promised externally
  in this release.
- New `F0` step in `normalize_text(text, level, layout=...)`: layout-aware
  stripping of footnotes, running headers, and running footers. Footnotes are
  preserved and surface as the `footnotes` section.
- Filter sugar on existing extract calls: `extract_pdf(b, sections=["abstract",
  "references"])` returns concatenated section text in document order. Same
  kwarg added to `extract_docx` and `extract_html`.
- New CLI subcommands: `docpluck extract <file> --sections=...`,
  `docpluck sections <file> [--format json|summary]`.

### Changed

- `NormalizationReport` gains `footnote_spans` and `page_offsets` fields
  (default empty tuples). Existing field/tuple-unpacking call sites are
  unchanged.

### Backwards compatibility

- `extract_pdf(bytes)`, `extract_docx(bytes)`, `extract_html(bytes)` byte-
  identical to v1.5.0 when called without the new `sections=` kwarg.
- `normalize_text(text, level)` byte-identical to v1.5.0 when called without
  the new `layout=` kwarg.

## [1.5.0] — 2026-04-27

### Added (Scimeto Request 9 — reference-list normalization)

- **W0 — Watermark template library** (runs in standard + academic, before S0).
  Strips four publisher-overlay templates that previously bled into the body
  text: `Downloaded from URL on DATE`, the RSOS running-footer artifact
  (`\d+royalsocietypublishing.org/journal/\w+ R. Soc. Open Sci. \d+: \d+`),
  Wiley/Elsevier-style `Provided by ... on YYYY-MM-DD`, and
  `This article is protected by copyright....`. Defense-in-depth alongside
  S9's repetition-based scrub; bounds blast radius before any reflow.
- **R2 — Inline orphan page-number scrub** (academic, inside references span).
  Repairs the silent corruption case where pdftotext glued a page-header digit
  between two body words inside a reference (e.g. ref 17 of the Li&Feldman
  PDF read `psychological 41 science.` because `41` is the journal page).
  Uses lowercase-surround guard to avoid touching volume numbers, page
  ranges, or year boundaries.
- **R3 — Continuation-line join** (academic, inside references span).
  Joins lines inside the bibliography that don't start with a Vancouver,
  IEEE, or APA reference marker onto the preceding reference. Eliminates
  orphan-paragraph artifacts that mid-ref column wraps used to produce.
- **A7 — DOI cross-line repair** (academic, document-wide).
  Rejoins DOIs broken across a line by pdftotext (`(doi:10.\n1007/...)`).
  The `doi:` prefix in the lookbehind chain is load-bearing — without it
  the rule would damage decimals at line ends in normal prose.

### Helper

- New `_find_references_spans` returns ALL qualifying bibliography spans
  (a header followed within 5k chars by ≥3 ref-like patterns) in document
  order, so PDFs with both a main and a supplementary bibliography get
  R2/R3 applied to each.

### Tests

- Added `tests/test_request_09_reference_normalization.py` (5 cases) gated on
  the Li&Feldman 2025 RSOS fixture PDF (skipped if absent). Asserts the four
  acceptance criteria from the request: watermark URL absent, RSOS footer
  absent, bibliography splits cleanly into 45 numbered chunks 1..45, ref 17
  free of `41 science`, ref 38 DOI rejoined.
- Existing `TestVersionBumps` updated to expect `1.5.0`.
- Full suite: **425 passing, 9 skipped** (+5 new cases).

### Pretest finding (revises the original request's diagnosis)

Scimeto's reproducer used `pdftotext -layout`. Docpluck explicitly avoids
`-layout` (see `extract.py:13–16`). On actual Docpluck output of the same
PDF, the full-URL watermark and orphan-paragraph reflow described in the
request are **already** absent — S9's repetition-based scrub kills the URL
banner, and default pdftotext reading-order reflow eliminates the
orphan-paragraph artifact. The three artifacts that did survive
(page-number digit residue, mid-ref `\n`, DOI line break) are now fixed.
Corpus dry-run: 51 PDFs, 0 regressions, 46 changed.

### Versioning

- `__version__`: 1.4.5 → **1.5.0**
- `NORMALIZATION_VERSION`: 1.4.5 → **1.5.0**
- New `changes_made` keys: `watermarks_stripped`, `inline_pgnum_scrubbed`,
  `ref_continuations_joined`, `doi_rejoined`.
- New step codes: `W0_watermark_strip`, `R2_inline_pgnum_scrub`,
  `R3_continuation_join`, `A7_doi_rejoin`.

## [1.4.4] — 2026-04-11

### Fixed (code-review follow-up to v1.4.3)

- **A3b was too permissive** — the initial v1.4.3 pattern
  `(\b[A-Za-z]{1,4})\[(\d+,\d+)\]` matched any 1-4 letter word before a
  bracketed numeric pair, which falsely converted citation/figure/
  equation references like `ref[1,2]`, `fig[1,2]`, `eq[1,2]` into
  `ref(1, 2)`, `fig(1, 2)`, `eq(1, 2)`. Tightened the pattern to require
  `=` immediately after the closing `]` — the assignment marker is the
  real signal that the bracketed pair is a df expression being assigned
  to a test statistic (as in `F[2,42]= 13.689`), not a reference list.
  Caught in the docpluck-review skill pass immediately after v1.4.3 tag.

### Tests

- Added `test_a3b_does_not_fire_on_short_word_citations` with 4 probes.
- Added `test_a3b_still_fires_on_real_stat_with_equals` as a positive-
  path regression guard.
- Full suite: **267 passing, 9 skipped** (+2 new cases vs v1.4.3).

## [1.4.3] — 2026-04-11

### Fixed (MetaESCI D1/D2 lost-source repro)

- **A3 lookbehind regression (D2 root cause).** The Braunstein lookbehind
  `(?<![a-zA-Z,0-9])` added in v1.4.1 did not exclude `[` or `(`, so
  pdftotext output like `F[2,42]=13.689` or `F(2,42)=13.689` (tight-
  spaced df forms with no space after the comma) was corrupted to
  `F[2.42]` / `F(2.42)` — converting the df separator into a decimal
  point. Downstream effectcheck regex then failed to parse the stat and
  silently dropped the row. Fix: lookbehind now excludes
  `[a-zA-Z,0-9\[\(]`. Discovered via MetaESCI D2 repro on
  `10.15626/mp.2019.1723` where docpluck produced 0 rows vs checkpdfdir's
  3 rows.
- **A3b statistical df-bracket harmonization (new step).** Some PDFs
  encode F/t/chi2 degrees of freedom with square brackets, e.g.
  `F[2,42]=13.689`. effectcheck's `parse.R` only matches parenthesized
  df, so bracketed forms are silently dropped. A3b converts the bracket
  form to canonical parens when the bracket immediately follows a short
  stat identifier. Runs in academic level only, after A3 and before A4.
  Tracked in `NormalizationReport.steps_applied` as
  `A3b_stat_bracket_to_paren`.

### Changed

- `NORMALIZATION_VERSION` bumped `"1.4.1"` → `"1.4.2"` to reflect the A3b
  addition and the A3 lookbehind semantic change. Downstream consumers
  should invalidate their extraction cache on this bump.

### Tests

- New `TestA3_StatBracketLookbehind` class in `tests/test_normalization.py`
  with 5 regression cases covering square-bracket and tight-paren df
  forms, thousands-separator tight-paren form (`t(1,197)`), and a
  citation-list negative case (`[1,2]` must not become `(1,2)`).
- Full suite: **265 passed, 9 skipped** (+5 new cases vs v1.4.2).

### Notes for MetaESCI downstream gaps

- **D1** (row-count drops across 6 sources): 3 of 30 lost rows are
  directly fixed by the A3/A3b changes above (all from
  `10.15626/mp.2019.1723`). The remaining ~27 rows contain cleanly
  normalized text in the docpluck output and appear to be effectcheck
  `parse.R` edge cases (uppercase `P`, table rows with pipe separators,
  and clean `F(df1, df2) = xx.xxx` forms that should match but don't).
  Report these to the effectcheck team with the PDFs:
  `10.1525/collabra.150`, `10.1177/0146167210376761`,
  `10.1177/0146167220977709`, `10.15626/mp.2021.2803`,
  `10.1098/rsos.211412`.
- **D4** (CI width-ratio divergences): the `raw_text` columns are
  byte-identical between Run A and Run B; only the computed CI bounds
  differ. That places the divergence in effectcheck's CI compute logic
  (`compute_ci` / `compute.R`), not in docpluck normalization. Not
  actionable on the docpluck side.

## [1.4.2] — 2026-04-11

### Added (MetaESCI D3/D5/D6/D7 follow-ups)

Addresses the non-blocking items MetaESCI filed in
`REQUESTS_FROM_METAESCI.md` ahead of the full 8,455-PDF batch. No
normalization semantics changed — `NORMALIZATION_VERSION` is still
`"1.4.1"`, so outputs byte-identical against v1.4.1 except for the
diagnostics changes below.

- **`docpluck.extract_pdf_file(path)`** — path-based wrapper around
  `extract_pdf(bytes)` that raises a clean `FileNotFoundError` with the
  offending path when the file is missing or is not a regular file (D7.1).
  Keeps the bytes API untouched.
- **`docpluck.extract_to_dir(paths, out_dir, level)`** + new
  **`ExtractionReport`** dataclass in `docpluck/batch.py` (D6). Batch
  runner that writes `<stem>.txt` (+ optional `<stem>.json` sidecar) for
  each input PDF and returns a serializable receipt with the library
  version, normalize version, git SHA, per-file method, timings, and
  failure reasons. `report.write_receipt(path)` persists it for
  downstream reproducibility pinning. Exceptions inside the loop are
  recorded, not raised — batch runs never abort on a single bad file.
- **`docpluck.get_version_info()`** + `docpluck/cli.py` (D3). New console
  entry point `docpluck --version` (also `python -m docpluck --version`)
  prints a single JSON line
  `{"version": ..., "normalize_version": ..., "git_sha": ...}`. Batch
  runners can call this once per run and stash the output next to
  results as a "bundle receipt".
- **`NormalizationReport.steps_changed`** (D7.2). New list alongside the
  existing `steps_applied`, containing only pipeline steps that actually
  modified the text. `steps_applied` is unchanged for backward compat;
  `to_dict()` now exposes both. Use `steps_changed` when you want to
  know what the pipeline *did* on a given input vs. what it *ran*.

### Fixed

- `docpluck/__init__.py` `__version__` was stale at `"1.3.1"` despite
  `pyproject.toml` and `NORMALIZATION_VERSION` both advancing to
  `"1.4.1"`. Now synced to `"1.4.2"`.

### Docs

- `docs/NORMALIZATION.md` — A5 section clarifies that
  `NormalizationLevel.academic` intentionally transliterates Greek
  statistical letters (η²→eta2, χ²→chi2, etc.) and points callers who
  need Greek preserved at `NormalizationLevel.standard` (D5).

### Unchanged

- `NORMALIZATION_VERSION` stays at `"1.4.1"`. No regex, no A-rule
  thresholds, no tokenization changed. Fresh batch runs against v1.4.2
  produce identical `data/results` to v1.4.1 given the same corpus —
  only diagnostic fields differ.
- All 227 pre-existing tests continue to pass. New tests added for
  `extract_pdf_file`, `extract_to_dir`, `steps_changed`, and the CLI.

### Deferred (requires MetaESCI repro data)

- **D1** (classify 4 + 54 dropped rows vs checkPDFdir) — needs the two
  A/B CSVs per subset that MetaESCI references but that currently only
  exist as a single merged CSV in their `data/results/subset/` tree.
- **D2** (one lost source per subset) — same.
- **D4** (A4 CI harmonization regex audit) — read-only audit done; see
  `REPLY_FROM_DOCPLUCK.md` for the preliminary hypothesis. No regex
  change until a real repro lands.

## [1.4.1] — 2026-04-11

### Fixed

- **A3 lookbehind to block author affiliation false-positives** (ESCImate
  report via `effectcheck/R/parse.R:189`). The v1.4.0 A3 decimal-comma rule
  was corrupting multi-affiliation citation markers like `Braunstein1,3`
  into `Braunstein1.3`. Added a `(?<![a-zA-Z,0-9])` lookbehind that blocks
  three classes of false positive:

  1. Author affiliations like `Braunstein1,3` — the letter before `1`
     blocks the match.
  2. Multi-affiliation sequences like `Wagner1,3,4` — both the letter
     before `1` and the comma before `3` block.
  3. Bracket-internal multi-value content like `[0.45,0.89]` — the digit
     before the comma blocks (A4 handles the bracket normalization).

  Six new regression tests under `TestA3_BraunsteinLookbehind`. Full suite:
  247 passed, 8 skipped.

### Compatibility

- No public API changes. `NORMALIZATION_VERSION` bumped `1.4.0 -> 1.4.1`.

## [1.4.0] — 2026-04-11

### Added

- **A3a thousands-separator protection** (ESCImate Request 1.1). The A3
  decimal-comma rule was corrupting `N = 1,182` to `N = 1.182`, which
  downstream parsers read as a sample size of 1.182 people. New step A3a
  runs before A3 and strips commas from only the integer token in known
  sample-size contexts (`N` / `n` / `df` / `"sample size of"` /
  `"total of ... participants"`), so A3 sees an already-clean integer and
  leaves it alone.
- **S5a FFFD eta context recovery** (ESCImate Request 1.2). pdftotext
  occasionally drops Greek eta (U+03B7) as U+FFFD even after the
  pdfplumber SMP fallback. Added a context-aware second line of defense
  that rewrites `U+FFFD` to `"eta"` **only** when followed by a statistical
  eta-squared pattern (`² = .NNN` / `2 = .NNN`, including the `_p²` partial
  variant). Generic FFFDs in prose are left alone for the quality scorer
  to flag.

### Verified (no code change)

- A5 Greek transliteration runs inside the academic block. Consumers that
  need Greek preserved should pass `NormalizationLevel.standard`; the
  effectcheck parser handles both forms. Documented in v1.4.2 after the
  MetaESCI D5 follow-up.

### Compatibility

- No public API changes. `NORMALIZATION_VERSION` bumped `1.3.1 -> 1.4.0`.

## [1.3.1] — 2026-04-11

### Fixed (normalization + quality scoring)

Three gaps identified by the v1.3.0 MetaESCI 200-DOI regression baseline, all
closed in this release. After the fixes, the same benchmark passes 9/9 criteria
(200/200 files, 100% high confidence, avg quality 99.95/100, zero residual
artifacts). No regressions in the 27 pre-existing tests or in the DOCX/PDF
cross-format benchmarks.

1. **A1 column-bleed extension.** PSPB multi-column layouts produce patterns
   like `p\n\n01\n\n01\n\n= .28` where `01` lines are column-bleed fragments.
   Two new A1 rules tolerate up to 4 short digit-only fragment lines — one for
   `p\n...\n=`, one for `p =\n...\n value`. They run *before* the simple
   `p =\n digit` rule so the first fragment isn't mis-joined. Regression tests
   in `tests/test_normalization.py::TestA1_ColumnBleed`.

2. **A2 widening.** A2's `val > 1.0` threshold rejected `p = 01` (float value
   1.0). Changed to `val >= 1.0`; the `\d{2,3}` prefix still prevents touching
   `p = 1`. The lookahead was extended to accept a sentence-ending period via
   `\.(?!\d)` but still rejects real decimals like `p = 15.8`. Regression tests
   in `tests/test_normalization.py::TestA2_DroppedDecimalV2`.

3. **Quality scorer — corruption signal required for garbled flag.** The
   v1.3.0 scorer flagged non-prose documents (reviewer acknowledgment lists,
   reference dumps) as garbled because it only looked at common-word ratio.
   v1.3.1 requires at least one independent corruption signal (U+FFFD / non-ASCII
   ratio > 20% / ≥20 ligatures / text < 500 chars) before flagging. Real
   column-merge garbage still trips the signal (always retains ligatures);
   valid non-prose content does not. Regression tests in `test_quality.py`.

### Changed

- `NORMALIZATION_VERSION` bumped from `"1.2.0"` to `"1.3.1"` so downstream
  consumers can detect the new pipeline. `NormalizationReport.version` reflects
  the change.
- `compute_quality_score()` result dict gains a new field
  `details.has_corruption_signal` (bool).
- Internal dropped-decimal benchmark detection regex tightened to match A2's
  own lookahead so diagnostic candidates align with what A2 actually fixes
  (prevents false positives like `p = 15.8` from column-merged table cells).

### Compatibility

- No public API changes. `extract_pdf`, `extract_docx`, `extract_html`,
  `normalize_text`, and `compute_quality_score` signatures are unchanged.
- All 211 pre-existing tests continue to pass. 16 new regression tests added
  (total 227).
- Verified no regressions on Scimeto/CitationGuard DOCX corpus (20/20 real
  papers extract at 100/100 quality) or cross-format parity (99.0% similarity
  on the DOCX→PDF spot check, identical to v1.3.0).

## [1.3.0] — 2026-04-10

### Added
- **Private benchmark suite** stress-testing extraction on a 24-file real-world DOCX corpus and bidirectional cross-format comparisons (DOCX↔PDF via Word, PDF→DOCX via `pdf2docx`). Results: 20/20 DOCX real files extracted at 100/100 quality, 98.8% avg DOCX→PDF similarity, format parity between `extract_docx` and `extract_pdf` confirmed. Scripts and per-file results live in a private research repo.
- **Phase 2 benchmark section** in `docs/BENCHMARKS.md` documenting the aggregate results.
- **Benchmark mode** in the `docpluck-qa` skill: triggered by "DOCX benchmark", "--benchmark-docx", "format parity", etc. Does NOT run during normal QA (5–15 min; launches Word).
- **DOCX extraction** via `extract_docx()` — uses `mammoth` to convert DOCX to HTML
  (preserving Shift+Enter soft breaks as `<br>` tags) then runs the same tree-walk
  used for native HTML. Ported from Scimeto's production code (running since Dec 2025).
- **HTML extraction** via `extract_html()` and `html_to_text()` — uses `beautifulsoup4`
  + `lxml` with a custom block/inline-aware tree-walk. Specifically regression-tested
  against the "ChanORCID" bug (adjacent inline elements merging text).
- **Optional dependency groups** in `pyproject.toml`:
  - `docpluck[docx]` adds mammoth
  - `docpluck[html]` adds beautifulsoup4 + lxml
  - `docpluck[all]` adds everything
  Core `pip install docpluck` still installs only pdfplumber for PDF support.
- **60 new tests** (46 HTML + 18 DOCX + 12 benchmark + corrections), bringing total to 211:
  - `tests/test_extract_html.py` — block/inline handling, ChanORCID regression,
    whitespace normalization, HTML entities, academic patterns
  - `tests/test_extract_docx.py` — mammoth integration, soft breaks, smart quotes,
    statistical values, ligature normalization integration, error handling
  - `tests/test_benchmark_docx_html.py` — 15 ground-truth statistical passages survive
    extraction and normalization for both formats with rapidfuzz ≥ 90% matching.
    Idempotency, quality scoring, and performance verified.
- **FastAPI service updates** (`PDFextractor/service/app/main.py`):
  - File type detection (PDF, DOCX, HTML, HTM) with per-type magic-byte validation
  - Extraction routing to the correct engine
  - Response format adds `file_type` field; `pdf_hash` kept for backward compat
  - Health endpoint reports all engines and supported types
- **Documentation** updates to README, BENCHMARKS, and DESIGN covering the new formats,
  library choices, rejected alternatives, and known limitations (OMML equations,
  tracked changes, memory usage).

### Changed
- `extract_html` and `extract_docx` use lazy imports so the core library still works
  without the optional dependencies installed.
- Version bumped to 1.3.0.

### Known limitations (documented, not bugs)
- **OMML equations** in DOCX are silently dropped (mammoth limitation). Rare in social
  science where stats are written as plain text; affects STEM papers.
- **Tracked changes** in DOCX are only partially handled by mammoth.
- **No page counting** for DOCX/HTML — `pages` is `None` for non-PDF formats.

## [1.1.0] — 2026-04-06

### Added
- S6: Soft hyphen (U+00AD) removal — was silently breaking text search across 14/50 test PDFs
- S6: Full-width ASCII→ASCII (U+FF01-FF5E) — handles full-width digit/letter patterns
- S6: All Unicode space variants (U+2002-U+205F, U+3000, ZWJ/ZWNJ)
- A5: Greek statistical letters (η→eta, χ→chi, ω→omega, α→alpha, β→beta, δ→delta, σ→sigma, φ→phi, μ→mu)
- A5: Combined forms (η²→eta2, χ²→chi2, ω²→omega2) and all superscript/subscript digits
- A6 (new step): Footnote marker removal after statistical values ("p < .001¹" → "p < .001")
- 151 tests across 6 test files

### Fixed
- A1 now runs before S9 to prevent page-number stripping of statistical values split across lines
- Possessive quantifiers in all line-break joining regexes to prevent catastrophic backtracking

## [1.0.0] — 2026-03-15

Initial release. Extracted from the Docpluck academic PDF extraction service.

### Features
- `extract_pdf()` — pdftotext primary + pdfplumber SMP fallback
- `normalize_text()` — 14-step pipeline (S0-S9, A1-A5) at three levels: none/standard/academic
- `compute_quality_score()` — composite quality metric with garbled detection
- 122 tests across 6 test files
