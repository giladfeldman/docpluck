# Handoff — B1 next iteration (after Approach C instrumentation)

**Authored:** 2026-05-22, end of post-run-9-close session.
**Owner:** next docpluck session.
**Prereq commit:** `2583011` (B1 Approach C: `_table_completeness_marker`).

## TL;DR

Approach C instrumentation now emits HTML-comment markers for three
structurally-degenerate table shapes. Before choosing between **Approach A**
(Camelot fallback chain — lattice + char-reconstruction) and **Approach B**
(per-table flavor selector with confidence scoring), harvest the C-marker
distribution across the corpus to learn WHICH failure mode dominates per
paper. Then code the targeted fix.

## State at handoff

- `_table_completeness_marker` in [`docpluck/render.py`](../../../docpluck/render.py) emits one of:
  - `<!-- table-empty-shell: 0 rows recovered, no raw_text fallback -->`
  - `<!-- table-unstructured: 0 structured rows, raw_text fallback only -->`
  - `<!-- table-single-row: 1 row recovered (likely headers-only, body lost) -->`
- Emitted from all 4 table-emission sites (3 inline + appendix).
- 8 unit tests in [`tests/test_render.py`](../../../tests/test_render.py) (search `table_completeness` / `empty_shell` / `unstructured_emits` / `healthy_table_no_marker` / `appendix_empty_shell`).
- B1 cluster: ~11 papers (efendic, xiao, jdm15/16, chen, maier, ip_feldman, ar_apa_011, plus plos-med-1 Tables 2/3/4/5) — see [`HANDOFF_2026-05-18_iterate_run_9_cont.md`](../../HANDOFF_2026-05-18_iterate_run_9_cont.md) §B1 for the exact symptoms per paper.

## Step 1 — Harvest the markers from a fresh corpus render

```powershell
python -u -m scripts.harness.extract --levels academic --workers 2 --force
```

Then grep the rendered .md outputs:

```powershell
Get-ChildItem scripts/harness/runs/*/rendered.md -Recurse |
  ForEach-Object {
    $pdf = $_.Directory.Name
    $shell = (Select-String "table-empty-shell" $_.FullName -SimpleMatch).Count
    $uns   = (Select-String "table-unstructured" $_.FullName -SimpleMatch).Count
    $solo  = (Select-String "table-single-row"  $_.FullName -SimpleMatch).Count
    "$pdf empty=$shell uns=$uns solo=$solo"
  } | Sort-Object | Out-File tmp/b1-marker-harvest.txt
```

Group by paper. Identify the dominant failure mode for the 11 B1 papers.

## Step 2 — Decide A vs B

| Dominant mode | Recommended approach |
|---|---|
| `empty-shell` dominates (Camelot returns nothing) | **Approach A** — add lattice flavor fallback + pdfplumber char-reconstruction. Lattice needs Ghostscript; check if Railway prod image has it (memory `project_camelot_for_tables` originally chose stream-only specifically to avoid Ghostscript) |
| `single-row` dominates (Camelot returns headers only, body lost) | **Approach A** — same fallback chain. Lattice often handles bordered tables; char-reconstruction handles whitespace tables |
| `unstructured` dominates (raw_text used as flat list) | The library already shows raw_text; the issue is *visibility*. Tune `tables/whitespace.py` / `tables/cluster.py` so cells get reconstructed from the existing raw_text. **Modified Approach B**, narrow scope |
| Mix of all 3 + numeric-cell SWAP (xiao Table 6 `4.91` vs gold `4.70`) | **Approach B** — confidence-scored per-table flavor selector. Numeric SWAP is a Camelot-stream pathology no fallback chain catches. Several cycles |

## Step 3 — Implement, gated by AI-gold

Every fix must be verified against the article-finder–generated AI gold for the affected papers — never against pdftotext/Camelot themselves. See memory `feedback_ground_truth_is_ai_not_pdftotext` and `.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md`.

Baseline-gate: run the full 26-paper baseline before merging. The C-marker harvest itself is a new baseline metric — track marker counts so future regressions surface.

## Step 4 — Coupled decision (B3 double-emission)

Deferred from the 2026-05-22 session: when structured Table N is empty, should `render.py` keep the body table-dump as fallback, or strip it (current behavior, exposes the empty shell loudly)? The B1 fix may resolve this naturally — if A/B recovers cells, the body strip is correct. Re-ask the user only if A/B leaves a residual class of empty-shell tables.

## Cross-references

- [`LESSONS.md`](../../../LESSONS.md) — never swap extraction tools; never use `pdftotext -layout`; never use AGPL pdf libs
- Memory `feedback_general_fixes_not_pdf_specific` — key fixes on structural signatures, not paper identity
- Memory `feedback_dont_relitigate_table_lib` — don't re-propose a Camelot replacement
