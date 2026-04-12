---
name: docpluck-cleanup
description: Clean up Docpluck codebase. Sync CLAUDE.md/README.md/ARCHITECTURE.md against actual code, remove dead benchmark scripts, verify LESSONS.md is current, clean temp/ directory, check for stale environment variables, verify .gitignore covers sensitive files, update TODO.md progress. Use /docpluck-cleanup periodically or before releases.
tags: [python, pdf, docx, html, fastapi, nextjs, docs, cleanup]
---

## Before starting: read ~/.claude/skills/_shared/preflight.md and follow it for this skill.

# Docpluck Cleanup

You are a codebase janitor for Docpluck. Your job is to keep documentation accurate, remove dead code, and ensure the repo is in a clean state.

## Project Location
`C:\Users\filin\Dropbox\Vibe\PDFextractor`

## Cleanup Checklist

### 1. Documentation Sync
Read the actual code and verify each doc file is accurate:

- **CLAUDE.md** — Does the project structure match? Are the commands correct? Do the critical rules still apply?
- **README.md** — Does the architecture diagram match reality? Are the tech versions correct?
- **ARCHITECTURE.md** — Do the system diagrams match actual deployment? Are all tables listed?
- **API.md** — Do endpoint signatures match `service/app/main.py`? Are normalization steps current with `service/app/normalize.py`?
- **SETUP_GUIDE.md** — Are all URLs, project IDs, and domain names current?
- **TODO.md** — Mark completed items. Remove items that are no longer relevant.

### 2. Dead Code Removal
Check `scripts/` for benchmark scripts that were intermediate steps and no longer needed:
- `scripts/investigate_stat_loss.py` — diagnostic, can be removed
- `scripts/investigate_stat_loss2.py` — diagnostic, can be removed
- `scripts/trace_pipeline.py` — diagnostic, can be removed
- `scripts/trace_pipeline2.py` — diagnostic, can be removed
- `scripts/verify_ieee_fp.py` — diagnostic, can be removed
- `scripts/quick_apa_verify.py` — diagnostic, can be removed
- `scripts/diagnose_mismatches.py` — diagnostic, can be removed
- `scripts/benchmark_docling_optimized.py` — Docling was dropped

Keep: `benchmark.py`, `ground_truth_verify.py`, `optimized_extractors.py`, `pdftotext_enhanced.py`, `setup_test_pdfs.py`, `ai_verify.py`, `final_showdown.py`

### 3. Temp Directory
```bash
rm -rf temp/
```
Contains rendered PNG pages from verification — not needed in repo.

### 4. Environment Variable Audit
- Check `.env.local` has no real secrets committed
- Verify `.gitignore` includes: `.env`, `.env.local`, `.env.production`, `.vercel/`, `test-pdfs/`, `temp/`, `__pycache__/`, `node_modules/`, `.next/`

### 5. Stale Dependencies
- Check `frontend/package.json` for unused deps
- Check `service/requirements.txt` — should only have fastapi, uvicorn, pdfplumber, python-multipart
- Verify no pymupdf or pymupdf4llm in requirements (AGPL dropped)

### 6. Memory Files
Check `C:\Users\filin\.claude\projects\c--Users-filin-Dropbox-Vibe-PDFextractor\memory\` for stale memories that no longer reflect current state.

## Output Format
Report what was cleaned, what was updated, and what needs manual attention.

## Final step: read ~/.claude/skills/_shared/postflight.md and follow it.
