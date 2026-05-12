# Handoff — Phase 2 (101-PDF corpus expansion)

**Session date:** 2026-05-12 (continuation of the v2.3.1 → v2.4.0 → v2.4.1 release chain)

## State at handoff

- **Library:** v2.4.1 tagged + pushed. PyPI not published.
- **App pin:** `docpluck v2.4.0` in `PDFextractor/service/requirements.txt`. Needs bump to v2.4.1 next session.
- **26-paper corpus verifier (`scripts/verify_corpus.py`):** 26/26 PASS at v2.4.1.
- **101-paper corpus verifier (`scripts/verify_corpus_full.py`, new this session):** partial-run result before v2.4.1 was applied — 7 failures observed in 25 papers processed (run cancelled to ship v2.4.1). Of those, 5 were the M-tag (missing title) on AMA/AOM single-span-title layouts that v2.4.1 specifically targets. **Next session must re-run with `python scripts/verify_corpus_full.py` to enumerate the actual v2.4.1 failure set.**

## What's in v2.4.1

A single fix to `_compute_layout_title` in `docpluck/render.py`:

- Pass 2 of the title-size selector (single-span fallback) now requires the span to be in the TOP region of the page (y0 ≥ 70% of page height) AND have ≥ 10 chars of combined text.
- Catches AMA/AOM cases where a mid-page big-font decoration (a "+" glyph at font 16.0, an "GUIDEPOST" feature-label at font 30.0) was outranking the actual title at a smaller font (e.g. font 15.0 on the JAMA Open layout).

Affects: `jama_open_3/4/6/10`, `amd_1`, `annals_4`, and likely several more AMA-format papers in the wider 101-PDF corpus.

## Known issues remaining (from partial 101-run)

| Paper | Tag | Cause |
|---|---|---|
| `ar_apa_j_jesp_2009_12_011` | H | Camelot couldn't extract any tables despite body referencing them (`### Table N` headings present but no `<table>` HTML). Known Camelot limitation; banner already warns user. |

Other papers' status under v2.4.1 is **unknown** — the partial run was on the v2.4.0 code path and is now stale.

## Recommended next-session workflow

1. **Bump app pin** in `PDFextractor/service/requirements.txt`: `v2.4.0` → `v2.4.1`. Commit + push.
2. **Run full 101-PDF verifier:** `python scripts/verify_corpus_full.py --save-renders` (15-30 min).
3. **Triage failures** by tag frequency: M / D / R / S / H / C / X / L / J. Probably 2-5 distinct root-cause patterns.
4. **Pick top 1-2 patterns** with highest paper-count, root-cause, fix in `render.py` (or wherever it lives), add unit tests.
5. **Re-run 26-paper verifier** to guard against regressions.
6. **Tag + push** as v2.4.2.
7. **Visual spot-check** of representative fixed papers through the workspace via Chrome MCP.
8. Repeat from step 2 until weekly quota exhausted or all 101 papers pass.

## Renders directory

`tmp/renders_v2.4.0/` contains rendered `.md` files for the ~25 papers processed in the partial run. Useful for grepping for "## Heading word" patterns and other regressions before re-running. **Stale at v2.4.1** — re-render is needed to update them.

## Tagging legend (for the new verifier)

| Tag | Meaning |
|---|---|
| M | missing `# Title` line |
| T | title ends in connector word ("of", "the", "and", ...) — almost certainly truncated |
| D | title is missing distinct words ≥ 4 letters that the spike baseline has (middle truncation; needs spike baseline to fire) |
| R | title text appears as body prose immediately after `# Title` (Nature-style duplication) |
| S | section count < 4 |
| H | `### Table N` headings present in body but no `<table>` HTML element |
| C | longest `*Figure N. ...*` caption > 800 chars (boundary leak) |
| X | output < 5 KB (extremely short — likely PDF extract failure) |
| L | output much shorter than spike baseline (requires baseline) |
| J | Jaccard vs spike < 0.6 (requires baseline) |
