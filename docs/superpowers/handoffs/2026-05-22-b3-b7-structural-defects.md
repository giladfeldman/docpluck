# Handoff — B3 through B7 (carry-forward structural defects)

**Authored:** 2026-05-22.
**Source of truth:** [`HANDOFF_2026-05-18_iterate_run_9_cont.md`](../../HANDOFF_2026-05-18_iterate_run_9_cont.md) §B3–B7.

This handoff is a CONTINUITY ANCHOR — it re-affirms that B3–B7 are still
open after the 2026-05-22 session and points back to the authoritative
detail in the run-9-cont handoff. Do NOT re-litigate the descriptions
here; read the cont handoff.

## Snapshot

| ID | Defect | Layer | Severity | Status @ 2026-05-22 |
|---|---|---|---|---|
| B3 | D4 metadata leak (author affiliations, copyright/funding sidebars, watermark strips, page furniture) + table double-emission | [`normalize.py`](../../../docpluck/normalize.py) W0/P0/P1 + [`render.py`](../../../docpluck/render.py) body suppression | S2 / C2 | open |
| B4 | Caption residuals — table-caption over-extension (TBL-CAP) + figure-caption double-emission (FIG-3c-2) | [`extract_structured.py::_trim_table_caption_at_cell_region`](../../../docpluck/extract_structured.py) | S2 / C2 | open |
| B5 | G5c-2 partitioner split-heading rejoin (`N.N.\n\n<CanonicalKeyword>`) | [`docpluck/sections/core.py`](../../../docpluck/sections/core.py) | S1 / C3 | open |
| B6 | COL column-interleave — `test_request_09` red since run 4 (chan_feldman Measures, chandrashekar) | text-channel reading order (study pdfplumber column algorithm, re-implement as conditional fallback per [`CLAUDE.md`](../../../CLAUDE.md)) | S0 / C3-C4 escalation-class | open |
| B7 | GLYPH deleted-minus residuals — U+2212 dropped entirely by pdftotext (ar_apa_011 `b = .022` for `−.022`, sign-inverting); efendic `Mchange = 2X.XX` | layout-channel per-char glyph identity | S0 escalation-class | open |

## Note on coupling with B3 from the 2026-05-22 session

The user deferred the B1-coupled question "when structured Table N is empty, keep the body table dump as fallback or strip it?" Per the B1 handoff, that decision rolls into the B1 next-iteration session. If A/B leaves a residual class of empty-shell tables, the answer may flip to "keep body dump." Otherwise the current strip is correct.

## Methodology / gotchas (carry forward)

These remain authoritative (from [`HANDOFF_2026-05-18_iterate_run_9_cont2.md`](../../HANDOFF_2026-05-18_iterate_run_9_cont2.md)):

- Service restart orphans uvicorn workers — kill ALL `spawn_main(parent_pid=<old>)` python processes
- Never run harness `extract` and broad `pytest` concurrently
- Harness `extract` skips on `source_sha1`, not docpluck version — `--force` mandatory after code change
- AI-gold via `article-finder generate-gold` (never self-generate; ground truth is AI multimodal read, never pdftotext)

## Sequencing recommendation

- **B6 first** (test_request_09 is RED in broad pytest; per verdict-gate that means the run carries a FAIL forever until resolved). This is the highest-priority item not blocked by an architecture decision.
- B3 second (high-volume, touches normalize which is well-understood).
- B4 + B5 paired (similar layer — extract_structured & sections).
- B7 last (escalation-class — surface analysis to user if layout-channel recovery is infeasible).

## Cross-references

- [`HANDOFF_2026-05-18_iterate_run_9_cont.md`](../../HANDOFF_2026-05-18_iterate_run_9_cont.md)
- [`HANDOFF_2026-05-18_iterate_run_9_cont2.md`](../../HANDOFF_2026-05-18_iterate_run_9_cont2.md)
- Memory `feedback_general_fixes_not_pdf_specific`
- [`LESSONS.md`](../../../LESSONS.md) — especially L-001 (never swap text-extraction as a fix for downstream)
