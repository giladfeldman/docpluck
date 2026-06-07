# Diagnosis — ip_feldman B4 (tables mid-body) + R4 (reading-order) are ONE root cause (2026-06-07)

**Bottom line (empirically verified, corrects the optimistic subagent estimates):**
The two "deferred canary tracks" on `ip_feldman_2025_pspb` — B4 (table content serialized
mid-body) and R4 (section-boundary reading-order displacement) — are **the same root cause**:
pdftotext column-interleaves **table-bearing two-column pages**, interleaving table
caption/headers/cells AND real body prose into one stream. **Neither is a safe single-cycle
fix.** Both need **region-aware column detection** — an architecture decision for the user.

This doc captures two diagnostic-subagent RCAs plus the orchestrator's empirical correction.

---

## What was confirmed

### Track A (B4 — tables serialized mid-body)
- Camelot DOES detect the tables (Table 2: 41 cells structured; Table 10: 12 cells but
  corrupt — absorbed adjacent-column prose into `<thead>`, so `_strip_phantom_camelot_tables`
  correctly drops the HTML, leaving a caption-only `### Table 10` block).
- The leak: the **linearized** table content stays in the section body text. The existing
  `render.py::_suppress_inline_duplicate_table_captions` only removes **italic** `*Table N.*`
  inline captions that **exactly** match the block caption. Two gaps surfaced:
  - Table 2's caption is emitted as **plain** text (not italic) and its content is
    **scattered** across the Introduction (rendered lines ~57, ~79, ~143), not a clean
    caption+trailing-cells block.
  - Table 10's inline caption is italic but **truncated** (`*Table 10. Intensity Estimates
    Regression Coefficients with*`) so it doesn't exact-match the block caption
    (`…with Outcomes (Extension).`).

### Track B (R4 — reading-order displacement)
- The column-correction infrastructure **already exists** (`docpluck/extract_columns.py`,
  wired in `extract.py` via `_detect_column_interleave_pages` → `splice_column_corrected_pages`).
- It does NOT fire on ip_feldman's problem pages because `_detect_2col_midline`'s
  word-center histogram (20 buckets × ~30pt) can't resolve the narrow ~17pt PSPB gutter
  (the gutter fits inside one bucket → no low-density valley → returns `None`).

---

## The orchestrator's empirical correction (why it is NOT single-cycle)

A line-start-x0 bimodal midline detector (the subagent's proposed minimal fix) was probed
against the real layout doc. **The bilateral gate blocks the target pages:**

| page (0-idx) | line-start right-cluster frac | proposed midline | **bilateral fraction** | gate verdict |
|---|---|---|---|---|
| 13 (Discussion) | 0.27 | 304 | **0.44** | REJECT (≥0.30) |
| 14 | 0.32 | 319 | **0.37** | REJECT (≥0.30) |
| 16 | 0.12 | 320 | 0.79 | REJECT (genuine table page) |

The bilateral gate (`extract_columns.py:140-151`) rejects any page where ≥30% of y-rows
have words on both sides of the midline — its PURPOSE is to protect genuine table pages
(amle_1 table pages run 38-66% bilateral) from being garbled by column-mode. ip_feldman's
problem pages have a **table coexisting with two-column prose**, so they read as 0.37-0.44
bilateral and are (correctly, by the gate's current logic) rejected. So:
- A line-start detector alone does NOT fix ip_feldman — the gate blocks it.
- **Lowering the bilateral threshold to admit these pages would risk garbling real
  table pages corpus-wide** (the gate was calibrated specifically against amle_1).

And the B4 leak can't be safely patched render-side either: the table content is
**interwoven with real prose** (e.g. rendered line 1349 `no support, we only summarized
interactions that were supported and documented below p < .05` sits between Table 10's
caption and its column headers/values). A "drop caption + trailing cell-shaped lines"
suppressor would risk **dropping that real prose — a TEXT-LOSS (rule 0a) violation**.

---

## The real fix (architecture decision for the user)

**Region-aware column detection.** Before deciding column-mode for a page, segregate the
page into vertical REGIONS: a full-width table region vs a two-column prose region. Apply
column-correction only to the prose region(s); leave the table region to Camelot. This:
- lets the prose region be column-corrected even when a table elsewhere on the page would
  otherwise trip the whole-page bilateral gate;
- keeps the table region out of the linear body stream so B4 stops leaking;
- fixes BOTH B4 and R4 on ip_feldman at the root (and any mixed table+column page).

Design sketch (respecting CLAUDE.md: pdfplumber MIT only, conditional fallback, no tool swap):
1. Detect horizontal band boundaries on the page (y-ranges) where the layout switches
   between full-width (table/figure) and two-column (prose) — e.g. via row-bilateral runs:
   contiguous y-bands that are bilateral = table band; unilateral-alternating = prose band.
2. Run the existing `_crop_and_extract` column logic per prose band (cropping x AND y),
   concatenate bands top-to-bottom, leaving table bands as-is (Camelot owns them, and the
   body text for those y-bands is suppressed).
3. Re-derive the column midline from the prose band's line-starts (not the whole page,
   which the table contaminates).

Effort: multi-session. Regression surface: every two-column paper (chandrashekar B6 canary,
amle_1, JAMA, all PSPB/JESP). Gate hard on the 26-corpus baseline every iteration.

---

## Status
- ip_feldman canary findings #3/#4 (Table 2/Table 10 B4) and #5 (Discussion R4) remain
  OPEN/deferred in the ledger. They are NOT regressions; they are this known root cause.
- Subagent raw RCAs (Camelot B4, R4) are in the session transcript (agentIds
  ab97a65fdc17ba56b, ab9470f2bbf13e4d3) — both correct on detection facts, both
  over-optimistic on the bilateral-gate interaction (corrected above).
- **Decision needed from user:** approve the region-aware column-detection architecture
  (multi-session) as the next track, or keep these deferred.
