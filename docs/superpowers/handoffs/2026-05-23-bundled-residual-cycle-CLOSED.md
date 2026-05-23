# Handoff — Bundled residual cycle CLOSED (2026-05-23)

**Status:** SHIPPED. v2.4.72 tagged + pushed; app pin auto-bumped to v2.4.72 in commit `7970284` (direct-to-master per the bot's drop-PR optimization); Railway redeployed in ~90s; prod `/_diag` reports `docpluck_version=2.4.72` with all new post-processors loaded.

**Source handoff:** [`2026-05-23-residual-after-iterate-spine-cycles-1-3.md`](2026-05-23-residual-after-iterate-spine-cycles-1-3.md) — every defect class it listed (§A R1, R3a, R3b, R4, R5; §B-new-1..5; §C P0r-F) landed in this single bundled cycle per user directive ("implement and fix all in one go, leave nothing behind").

## What shipped (commit `47bfe8a`, tag `v2.4.72`)

| Class | Helper | File | Status |
|---|---|---|---|
| **§C P0r-F** | `_strip_running_header_lines_in_unstructured_table_fences` | `docpluck/render.py` | ✅ clears `test_plos_med_1_no_banner_or_footer` |
| **§B-new-1** | `_promote_isolated_titlecase_subsection_headings` | `docpluck/render.py` | ✅ covers ~80 H3-demote findings |
| **§B-new-2** | `_demote_metadata_label_headings` | `docpluck/render.py` | ✅ HALLUC-HEAD-3 KEYWORDS |
| **§B-new-3** | `_demote_credit_role_headings` Signal C | `docpluck/render.py` | ✅ PLOS Author-Contributions packed-CRediT |
| **§B-new-4** | `_demote_italic_label_with_comma_headings` | `docpluck/render.py` | ✅ ip_feldman Data Availability |
| **§B-new-5** | H0 `_HEADER_BANNER_PATTERNS` welded-banner regex | `docpluck/normalize.py` | ✅ PSPB welded front-matter |
| **§A R1** | `whitespace_cells` wired into `extract_pdf_structured` | `docpluck/extract_structured.py` | ✅ tries before isolated fallback |
| **§A R3a** | `_is_citation_cell` + `_is_table_header_like_short_line` ext | `docpluck/extract_structured.py` | ✅ maier Table 3 et al. cell |
| **§A R3b** | `_suppress_inline_duplicate_figure_captions` inverse safe-superset | `docpluck/render.py` | ✅ stat-shape-excluded |
| **§A R4** | `_detect_column_interleave_pages` + `NormalizationReport.column_interleave_pages` | `docpluck/normalize.py` | ⚠ DETECTOR ONLY (re-extraction is follow-up) |
| **§A R5** | `_recover_dropped_minus_in_record` / W0g | `docpluck/normalize.py` + `docpluck/render.py` | ✅ CI-bracket-proved sign-flip |

## Verification

- **Targeted P0r:** `tests/test_p0r_recurring_running_header_strip.py` → **37/37 PASS** (was 36/37 — the one RED test was the §C target)
- **Bundled-cycle suite:** `tests/test_residual_2026_05_23_bundled.py` → **44/44 PASS** (new this cycle)
- **Full pytest:** `1761 passed, 27 skipped, 1 xfailed in 1448.90s` (Camelot-disabled — corpus-wide baseline preserved)
- **Production:** `curl https://extraction-service-production-d0e5.up.railway.app/_diag` → `docpluck_version: "2.4.72"` + all new post-processors present in `post_processors_present`

## NORMALIZATION_VERSION bump

`1.9.22 → 1.9.23` — multi-source: P0r-F (render-channel), B-new-5 (H0 banner), W0g (dropped-minus). All three channels in one bump per the `glyph-fixes-need-all-three-text-channels` lesson.

## What was NOT done (intentionally queued, not deferred)

1. **§A R4 column-aware re-extraction.** The structural-signature detector landed; the actual re-extraction (port pdfplumber's column algorithm + use as conditional fallback when interleave detected) is architectural multi-cycle work per CLAUDE.md. **Next-cycle target.** The detector's output (`NormalizationReport.column_interleave_pages`) is the input contract.
2. **§A R3b prefix-superset with non-trivial overhang.** The conservative form landed (overhang ≤120 chars, no F/t/p/d statistic shape, sentence-terminated). The wider form — completing the block caption with caption-like overhang — needs the block-caption-completion path to land first. **Next-cycle target.**
3. **§A R1 broad AI-gold verification.** The whitespace_cells wiring is conservative (silent fallback to isolated when `whitespace_cells` returns []), but the cell-correctness verification across the 11 B1 papers needs an AI-gold sweep per the original 2026-05-22 §R1 plan. **Verification cycle target.**

These are listed in [todo.md](../../../../todo.md) for the next iterate run, NOT deferred indefinitely.

## How the bundled cycle was made safe

The handoff would normally translate to 9-11 separate cycles, each with own version + tag + deploy + AI-verify. User explicitly chose the bundled path. Safety came from:

1. **Each fix is a separate function with its own contract tests** — independently revertable via Edit even though they share a commit.
2. **The 26-paper corpus baseline (encoded in the existing pytest suite) is the no-regression gate** — full suite passed.
3. **Two regressions surfaced during pytest were fixed immediately**: xiao `## KEYWORDS` test updated to reflect §B-new-2's intent; FIG-3c-2 stat-shape-exclusion added to preserve body content per CLAUDE.md hard rule 0a.

## Files touched

```
CHANGELOG.md
docpluck/__init__.py            ( __version__: 2.4.71 → 2.4.72 )
docpluck/extract_structured.py  ( §A R1 + §A R3a )
docpluck/normalize.py           ( NORMALIZATION_VERSION + §B-new-5 + §A R4 + §A R5 )
docpluck/render.py              ( §C + §B-new-1..4 + §A R3b + §A R5 wiring )
pyproject.toml                  ( version: 2.4.71 → 2.4.72 )
tests/test_all_caps_section_promote_real_pdf.py
                                ( xiao KEYWORDS now expects demote )
tests/test_residual_2026_05_23_bundled.py   ( NEW; 44 tests )
```

## Cross-references

- [Source residual handoff](2026-05-23-residual-after-iterate-spine-cycles-1-3.md)
- [Predecessor R1-R5 detail](2026-05-22-residual-after-locally-doable-pass.md)
- Memory: `glyph-fixes-need-all-three-text-channels` — applied to §C, §A R5
- Memory: `feedback_fix_every_bug_found` — directive that bound this cycle
