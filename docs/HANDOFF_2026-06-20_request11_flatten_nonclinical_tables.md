# Handoff — REQUEST_11 (flatten `fields` for non-clinical result tables) — v2.4.95 SHIPPED

**Date:** 2026-06-20
**Status:** COMPLETE. All 4 acceptance criteria met, both target papers AI-gold-verified, iterate-gate cycles 1 + 2 PASS (0 open, 0 blocked). Library bumped 2.4.94 → **2.4.95** (`TABLE_EXTRACTION_VERSION` 2.3.0 → **2.4.0**). **Not yet deployed** — see "Next step".

## What was asked

[REQUEST_11_FLATTEN_FIELDS_NONCLINICAL_TABLES.md](../REQUEST_11_FLATTEN_FIELDS_NONCLINICAL_TABLES.md): v2.4.94 populated `flattened_rows[].fields` for the clinical PROSECCO table (labelled headers); two of three target tables still returned `fields:{}` — header-stripped result tables and tables packing parallel arms into one cell.

## What shipped (all in `docpluck/tables/flatten.py`)

- **Cycle A — blank-header column-role recovery** (`_recover_blank_roles`): role from data-token SHAPE + caption/footnote/all-header-rows VOCAB, never bare position. New `BF01` role. Validity guards (`r∉[-1,1]`, non-monotone CI, non-int `n`, `p∉[0,1]`). Recovers 77859 T5, 90203 T8/T9/T10.
- **Cycle B — packed parallel-arm split** (`_detect_packed_arms` / `_flatten_packed_arms` / `_split_value_groups` / `_VALUE_GROUP_RE`): k≥2 arms packed per cell → one `group=<arm>` record per arm. 77859 T3 (Separate/Joint), xiao_2021 T7 (Regret/Justifiability, general dividend).
- **2 general L-004 fixes** (Cycle B): `_parse_number` + `_parse_ci_cell` fold U+2212 MINUS (negative t/d/CI were dropped/sign-flipped); `_VALUE_GROUP_RE` splits bracket-led CI groups.

Tests: `tests/test_tables_flatten_blank_header_recovery.py` (+16 cases incl. real-PDF Table 3, value-group splitter, single-arm non-firing guard). Reply: [REPLY_FROM_DOCPLUCK_v2.4.95.md](../REPLY_FROM_DOCPLUCK_v2.4.95.md).

## Verification (evidence, not assertion)

- **AI-gold (article-finder golds, `reading.md`):** 77859 Table 5 + Table 3 arms → PASS exact; 90203 Tables 8/9 (16 rows) → PASS exact; xiao T7 (12 rows) → PASS exact incl. U+2212 sign preservation + arm df-signature match. Recorded in `run-meta/docpluck-iterate.json` phase_5d_runs cycles 1+2.
- **Full before/after corpus diff (HEAD v2.4.94 vs working tree, 24 papers):** 10 changed = 2 targets + improvements (chan CIs, jamison M/SD, ziano est, korbmacher garbage-CI *removed*, xiao arm-split, ip_feldman real t-stats surfaced). Canary **structural** renders byte-identical (sha-matched); PROSECCO 6 stat rows untouched.
- **Tests:** 60 flatten tests green w/ Camelot; 160 logic/render/structured green w/ Camelot disabled.

## Two caveats surfaced (logged in run-meta open_findings; NOT flatten defects)

1. **90203 Table 10 "Joint/No-explicit" `r=.59`** — PDF **text layer** reads `.59` (pdftotext + Camelot agree); AI-visual gold reads `.63`. Text-layer corruption, undetectable without OCR. Pre-existing in the table HTML.
2. **77859 "Table 3" vs gold "Table 2"** — caption-number binding; docpluck + the consumer's request both say "Table 3"; AI gold says "Table 2". Values/arms all correct. Pre-existing caption-binding, not introduced by the arm-split. Needs PDF-page inspection to adjudicate (low priority).

## Deferred (deliberate, with reason)

- **`fields.effect_type`** (REQUEST §2.4): consumer marked it "not a blocker." Adding it changes PROSECCO's field-set → conflicts with acceptance #4 (PROSECCO byte-identical). Offered as an opt-in in the reply. If accepted: map `cohens_d`/`pearson_r`/`partial_eta_squared`/`mean_difference` from key-present + effect vocab.

## Next step (deploy — not done this run)

Library is tagged-ready but **not released**. To reach `https://docpluck.app`:
1. `git tag v2.4.95 && git push --tags` (pre-push canary hook runs ~5-10 min — never kill it).
2. Bump `PDFextractor/service/requirements.txt` git pin → `@v2.4.95`; update any frozen version examples in `PDFextractor/API.md`.
3. Run `/docpluck-deploy` from the docpluck repo (pre-flight check 4 enforces the pin match) → Vercel/Railway.
Until then the live service runs v2.4.94 and the two tables still return `{}` there.
