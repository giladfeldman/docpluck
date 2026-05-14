# Local verification (Phase 5 detail)

> Loaded on demand from SKILL.md Phase 5. Do not load up-front.

Per memory `feedback_ai_verification_mandatory`: AI-verification + visual inspection are **mandatory, not optional**. If budget is tight, scope the **code change** smaller — never scope the verification smaller.

Run these in order. Each must pass before moving to the next. Use `awk '{print; fflush()}'` after every `python -u` invocation — Windows pipe buffering hides progress otherwise (memory `feedback_pdftotext_version_skew` notes the same kind of skew applies to subprocess output).

## 5a · Targeted unit tests (≤30s)

```bash
DOCPLUCK_DISABLE_CAMELOT=1 python -u -m pytest \
  tests/test_<module-you-touched>.py \
  tests/test_normalization.py \
  tests/test_sections_core_partition.py \
  -q --tb=short
```

If FAIL → fix → retry. If after 3 retries still FAIL → revert the cycle's edits, append a LEARNINGS entry, ask the user.

## 5b · Broad pytest suite (~5 min, run in background)

```bash
DOCPLUCK_DISABLE_CAMELOT=1 python -u -m pytest tests/ -q --tb=line \
  --ignore=tests/test_extract_pdf_structured.py \
  --ignore=tests/test_cli_structured.py \
  --ignore=tests/test_corpus_smoke.py \
  --ignore=tests/test_benchmark_docx_html.py 2>&1 | awk '{print; fflush()}'
```

Run with `run_in_background: true` and arm a Monitor with the until-loop pattern from `~/.claude/skills/_shared/preflight.md`. Don't poll.

## 5c · 26-paper baseline (~10 min, run in background)

```bash
PYTHONUNBUFFERED=1 python -u scripts/verify_corpus.py 2>&1 | awk '{print; fflush()}'
```

**Hard gate: must PASS 26/26.** Anything less, even a single WARN, blocks the cycle. Per the iterative_library_improvement handoff: "If a paper now fails, your fix has overreach — narrow it and try again before continuing."

## 5d · Local re-render eyeball check (MANDATORY — never skip)

While the broad pytest + 26-paper baseline run, render 4–5 papers most likely to be affected by your fix (TRIAGE notes the affected papers). For each:
- Compare `tmp/<paper>_v<previous>.md` vs `tmp/<paper>_v<current>.md`
- Read the document START (first 30 lines) as a user
- Verify the targeted defect is gone AND no new defect appeared

If a new defect appeared, **revert and try again** — don't accumulate two fixes into one cycle.

**Why mandatory:** char-ratio + Jaccard verifiers are blind to "right words in wrong order under wrong heading." On 2026-05-13 the user spotted multiple visible defects (xiao keywords merging with intro, contact info infused mid-text, false `Experiment` heading) that the verifier passed. The user's words: *"these are examples that an AI verification of the output and visual inspect MUST identify without my going over it."*

## 5e · Camelot-bearing tests (only if you touched table extraction)

```bash
python -u -m pytest tests/test_extract_pdf_structured.py tests/test_cli_structured.py -q --tb=short
```

These are slow (~10 min). Skip if your change was section/normalize/render-only.

## Background pytest pattern (Monitor + run_in_background)

```python
# Bash with run_in_background: true
DOCPLUCK_DISABLE_CAMELOT=1 python -u -m pytest tests/ -q --tb=line ... 2>&1 | awk '{print; fflush()}'
# returns immediately with task-id <id> and output file path

# Then arm Monitor:
until grep -qE "passed|failed|error" "<output-file>" 2>/dev/null; do sleep 10; done
tail -10 "<output-file>"
```

The Monitor fires on the first match — no polling, no idle wakeups.

## Common verification failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| 0-byte output for 5+ min | Windows pipe buffering | Add `awk '{print; fflush()}'` |
| Targeted tests pass, baseline fails | Cross-module effect | Narrow the fix or revert |
| Baseline 25/26 with one WARN | Title-truncation edge case | Inspect the WARN paper, decide whether to revert |
| Eyeball finds new defect that wasn't there | Fix has overreach | Revert; try a narrower fix |
| `PermissionError: [WinError 32]` after Camelot | Cosmetic Windows shutil race | Ignore — known Camelot atexit issue |
