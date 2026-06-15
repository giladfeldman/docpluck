# HANDOFF — docpluck-iterate resume (2026-06-15, updated post-B7)

> **Supersedes** the earlier citationguard-iterate-written stub of the same name (that one flagged
> B7 as "triage first" — now DONE). Its findings table is preserved below under "Open queue".

## TL;DR

- **B7 (dropped-minus sign-flip) FIXED and shipped as v2.4.89** (committed `44f4ccd`, tagged
  `v2.4.89` **locally — NOT pushed**). Full suite 1968 passed; AI-verify confirms all 5 ar_apa beta
  signs correct; canary pre-commit gate PASS (0 new findings).
- The run is **OPEN / PARTIAL** — standing verdict **FAIL** (rule 0e-bis). Two more architectural
  classes remain: **RC-1** (two-column interleave, user-approved) and **B1** (table-completeness,
  *beyond* the originally-approved B7+RC-1 scope — needs a scope nod). Plus a metadata-leak residual
  + heading-demotion.
- **User decisions 2026-06-15:** (1) "ship B7, then full handoff" → this doc. (2) "commit+tag now,
  batch prod deploy with RC-1" → **deploy is HELD** (see Deploy state).

## What shipped this session — cycle 1, B7 (v2.4.88 → v2.4.89)

`normalize.recover_dropped_minus_via_layout` (W0h). pdftotext drops the U+2212 glyph on tight-kerned
PDFs that draw the minus in a symbol font; W0g needs a CI to recover the sign, so a coefficient with
only a t/p value (`b = -.022, t(87)=.17`) was left sign-flipped. W0h reads the surviving `(cid:N)`
minus from the **layout channel** in the `<stat> = <minus><coef>` slot and re-inserts it. Threaded a
**dedicated `dropped_minus_layout` param** (`render → extract_sections → normalize_text`) so F0 stays
off in the text-channel-only section path. `NORMALIZATION_VERSION` 1.9.34 → 1.9.35.

- ar_apa: `-.022 / -.88 / -.428` recovered; `.48` stays positive. Surgical blast radius (only ar_apa
  flips of the 5 onboarded canary papers; other 4 byte-identical).
- **Documented OCR-only limitation:** ar_apa `-.245` is painted pixels (absent from pdftotext AND
  pdfplumber chars/lines/rects/curves AND pdfminer raw layer). User-approved to leave it. TODO.md R5.
- Files: `normalize.py`, `sections/__init__.py`, `render.py`, `__init__.py`, `pyproject.toml`,
  `tests/test_dropped_minus_layout_recovery_real_pdf.py`, `CHANGELOG.md`, `TODO.md`.

## Deploy state (HELD — batch with RC-1)

| Step | State |
|---|---|
| commit | ✅ `44f4ccd` (release) + `dca0e32` (docs) on `main` — **LOCAL, not pushed** |
| tag `v2.4.89` | ✅ created LOCAL, **NOT pushed** |
| push `main` | ⏸ HELD (deploy-safe — docpluck main push doesn't deploy — but held for the batch; user asked commit+tag only) |
| push tag → auto-bump PR | ⏸ HELD (pushing the tag opens the docpluckapp pin-bump PR) |
| PyPI publish | ⏸ HELD |
| `PDFextractor/service/requirements.txt` pin bump | ⏸ HELD (still `@v2.4.88`) |
| Railway/Vercel verify | ⏸ HELD |

**To deploy the batch (after RC-1 lands as v2.4.90):** push both tags, let the auto-bump PR open,
bump the requirements pin to the latest, merge, verify Railway `/_diag` + Vercel. Or `/docpluck-deploy`.

## Open queue (standing verdict FAIL — the run is not done)

### Cycle 2 — RC-1 two-column reading-order interleave (NEXT · user-approved · C4 multi-session)
The dominant defect — every two-column APA paper. **Spec:** `docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md`.
- **Step 1** (flag `DOCPLUCK_COLUMN_CORRECT_GENERAL`, default off) is implemented but proven a no-op
  on table-bearing pages (the failing ones) — flipping its default is ruled out.
- **Step 2 (the work):** per-band y-band segmentation. For a flagged page, segment into horizontal
  y-bands; a band with a clean full-height gutter → column-correct it (left-then-right); a full-width
  band (table row, banner) → leave as-is; reassemble in y-order. Corrects 2-col prose bands on pages
  that ALSO carry a table — the case the whole-page bilateral gate currently skips.
- **Foundation (do NOT rebuild):** `extract_columns.extract_page_text_columns` (midline detect:
  `_detect_2col_midline` histogram + `_detect_2col_midline_gutter` strip; bilateral y-row gate at
  L181-194 SKIPS table pages — Step 2 replaces whole-page with per-band) + `splice_column_corrected_pages`
  (UNCONDITIONAL word-preservation guard — every corrected page must be a pure reorder).
- **Targets / validation:** chan_feldman_2025_cogemo (heaviest), chandrashekar_2023_mp, collabra_37122,
  collabra_77859, jesp_2021_104154, + ar_apa Table 1 scramble. Word-preservation guard + AI-verify vs
  article-finder gold (char-ratio is BLIND to reordering) + full 1996-test suite, 0 regressions.

### B1 — table-completeness (BEYOND approved scope — needs user nod before starting)
plos_med_1 (fresh AI-verify v2.4.89): Table 2 loses 8/9 data rows; Table 3 loses Rel.risk+P-value
columns; **Table 4 body is garbled with Table 3 content**; Table 5 empty (all 10 SAE rows lost).
This is the outstanding **modified-Approach-B bbox-computation** architectural decision open since
2026-05-22 (run-9 close). High severity for a meta-science tool (silent whole-table loss).

### Separable / lower-tier
- **Metadata-leak residual** (plos): affiliations/abbreviations/running-headers leak into body. RC-2
  was declared closed (v2.4.81/83) but plos still leaks — investigate whether RC-2 missed PLOS layout.
- **Heading-demotion**: Method subheadings demoted to body (ar_apa: Overview/Practice instructions/
  Self-control assessment/Supplemental analyses; plos: Interventions/Randomization). Wide false-positive
  surface — full Phase-5H regression required before shipping a promotion rule.
- **ar_apa**: Fig 1 caption duplicated (body + Figures section); `article/info/Article history`
  front-matter leak; `awareness`→`efforts` word substitution (verify vs source PDF — possible gold or
  pdftotext artifact; ~26% verifier FP rate per cross-project R-0006).

### Prior citationguard-filed findings (8-paper punch-list — independent confirmation)
| Paper | Dominant defects |
|---|---|
| `ip_feldman_2025_pspb` | Table-cell numerics loose in Results body (L711+); Table-5 "Reasons for change" header→heading |
| `chandrashekar_2023_mp` | Tables 7/8 empty shells, Table 9 holds Table 10 data, Table 4 unstructured; B6 interleave |
| `chan_feldman_2025_cogemo` | **Heaviest** B6 interleave (Method/Results/PCIRR scramble); 5/9 tables unstructured; subheadings demoted |
| `ar_apa_j_jesp_2009_12_011` | ✅ **B7 FIXED v2.4.89** (3/4 betas; .245 OCR-only). Residual: Table 1 scramble (RC-1), headings |
| `jesp_2021_104154` | RC-1: 8+ section inversions; Table 1/2 merged, Table 3 split |
| `collabra_77859` | RC-1 pervasive interleave; all 5 tables missing/wrong-table data |
| `collabra_37122` | RC-1: `## Conclusion` after back-matter; Methods/Hypotheses heading split |

## Resume instructions

1. Re-invoke `/docpluck-iterate` (run-meta `~/.claude/skills/_shared/run-meta/docpluck-iterate.json`
   is OPEN at `current_cycle: 1`; read `open_findings[]` + `phase_5d_runs[]` for excerpts).
2. **Confirm scope with the user first:** RC-1 is approved; B1 + metadata are NOT (they surfaced
   during cycle-1 verification). Ask before starting B1.
3. Reproduce each finding at HEAD before trusting it (`reproduce-triage-defect-at-head`; ~26% verifier FP).
4. RC-1 Step 2 per the spec above. One root cause per cycle; real-PDF test + word-preservation + AI-verify + full suite.
5. Run `iterate-gate.sh --cycle N` every cycle; `--close` only when the corpus is clean (I6).

## Infra notes (cost time this session — fix next)
- `pytest -n auto` (xdist) output is buffered until the very end on Windows — mid-run it looks dead
  (0-byte output, no visible python proc). It is NOT dead. Use serial `pytest -q` + a `PYTEST_DONE_EXIT_$?`
  marker, or just wait for the completion notification. Full suite ~23 min.
- Camelot is non-deterministic on Windows (ar_apa rendered 27038B vs 27507B across identical runs — a
  table present/absent). Body-prose verification is stable; table verification needs a deterministic
  Camelot or retry before sha-pinning (affects I10 rendered_sha stability).
- plos_med_1 reading gold EXISTS (28d) — the TRIAGE "no gold/BLOCKED" was stale; I6 data-gap resolved.
  Gate flagged an I11 transition warning (gold may be under a non-canonical key dir) — rekey check.
- Canary rotating_pool size 2 == rotation_size 2 (no rotation); onboard efendic/maier/xiao.

## Why this matters downstream
escicheck reads docpluck's academic-level text for effect-size extraction — **B7's sign-flip directly
corrupted those statistics**, so v2.4.89 is a correctness fix for escicheck (deploy when batched).
citationguard's Harvard work (D1) similarly consumes docpluck text. RC-1 + B1 both affect what these
consumers see.
