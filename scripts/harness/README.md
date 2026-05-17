# docpluck verification harness

A regression-safe, automated extraction-and-inspection harness. It drives the
**local app** (the FastAPI extraction service the deployed product uses),
saves every output view for every normalization level, and gates on
deterministic whole-corpus regression checks plus AI-gold deep inspection.

Built 2026-05-17 after a post-mortem (`docs/ITERATION_VERIFICATION_LESSONS.md`)
found the prior loop verified the library in isolation, per-cycle/per-target
only, against snapshot baselines that could themselves be broken.

## Why it exists

The old `scripts/verify_corpus.py` rendered the **library** directly and
compared against frozen `.md` snapshots with a char-ratio. That cannot see:
defects in the app↔library gap, a table missing from the rendered view,
text loss when the snapshot was already lossy, or a regression on any paper
that is not the current cycle's target. This harness fixes all four.

## Layout

| File | Role |
|------|------|
| `corpus.py` | Discover every test document (PDF/DOCX/HTML) → `corpus_manifest.json`. |
| `extract.py` | Drive the local app `/analyze` per document × level; save every view to `verify_out/`. |
| `checks.py` | **Tier-D** — deterministic checks → verdict matrix; diff vs committed `baseline_matrix.json`. |
| `inspect.py` | **Tier-A** — pair saved outputs with AI golds → `inspect_jobs.json`; collect agent verdicts. |
| `VERIFIER_PROMPT.md` | The prompt the orchestrator gives each Tier-A verifier agent. |
| `corpus_manifest.json` | Committed corpus (paths only — no document bytes). |
| `baseline_matrix.json` | Committed Tier-D verdict baseline (verdicts, not output snapshots). |
| `gold_keys.json` | Committed doc-id → ai-gold canonical key map. |

`verify_out/` (gitignored) holds the saved extraction outputs + matrices.

## Prerequisites

The local FastAPI service must be running with the current library:

```
cd PDFextractor/service
python -m uvicorn app.main:app --port 6117 --env-file .env --workers 4
```

The service uses whatever `docpluck` is importable — for local dev that is the
editable working-tree install, so it always reflects HEAD. (`requirements.txt`
pins a *released* version; that governs Railway prod, not local.)

## Usage

```bash
# 1. (re)discover the corpus
python -m scripts.harness.corpus --write

# 2. extract — drive the app, save every view × level
python -m scripts.harness.extract --workers 4              # whole corpus
python -m scripts.harness.extract --only <doc_id> --levels academic
python -m scripts.harness.extract --force                  # ignore the idempotency skip

# 3. Tier-D — deterministic regression gate
python -m scripts.harness.checks                           # build matrix, diff baseline
python -m scripts.harness.checks --update-baseline         # accept current as baseline

# 4. Tier-A — AI-gold deep inspection
python -m scripts.harness.inspect prepare --affected <doc_id> ...
#   -> orchestrator dispatches a verifier agent per job (see VERIFIER_PROMPT.md)
python -m scripts.harness.inspect collect
```

## The regression contract

`checks.py` writes a verdict **matrix** and diffs it against the committed
**baseline matrix**. A cell that was `pass` and is now `fail` is a
**REGRESSION** — the gate exits non-zero. A `fail` that was already `fail` is a
known issue (tracked, not a regression). A `pass` that becomes a new `fail`
(no baseline entry) also fails the gate — an uncovered defect.

This is the "a fix is never done forever" backcheck: every cycle re-extracts
and re-checks the **whole corpus**, so a fix to one paper that breaks another
is caught the same cycle.

## Tiers

- **Tier-D** (`checks.py`) — fast, AI-free, **whole corpus every cycle**. Catches
  text loss (paragraph-level), table-JSON↔rendered parity, glyph corruption.
- **Tier-A** (`inspect.py` + agents) — AI-gold semantic inspection on the
  tiered subset (cycle-affected docs + every open Tier-D fail + a rotating
  slice). Catches wrong-but-valid glyphs, misplaced sections, spliced tables.
