---
name: docpluck-review
description: Code review specialist for Docpluck PDF extraction service. Reviews changes against CLAUDE.md hard rules (never use -layout flag, never use AGPL deps like pymupdf4llm, always normalize U+2212), checks normalization pipeline completeness, validates FastAPI endpoint security, reviews Auth.js middleware, checks for hardcoded secrets/URLs, verifies Dockerfile best practices. Use /docpluck-review after making code changes or before merging.
tags: [python, fastapi, nextjs, pdf, authjs, drizzle, docpluck, review]
---

## [MANDATORY FIRST ACTION] preflight (do NOT skip, even if orchestrated by /ship)

**Your very first action in this skill, BEFORE reading anything else, is:**

1. Run: `bash ~/.claude/skills/_shared/bin/preflight-filter.sh <this-skill-name>` and print its `🔧 skill-optimize pre-check · ...` heartbeat as your first visible output line.
2. Initialize `~/.claude/skills/_shared/run-meta/<this-skill-name>.json` per `~/.claude/skills/_shared/preflight.md` step 6 (include `phase_start_sha` from `git rev-parse HEAD`).
3. Load `~/.claude/skills/_shared/quality-loop/core.md` into working memory (MUST-level rules gated by /ship).

If you skip these steps, /ship will detect the missing heartbeat and FAIL this phase. Do not proceed to the skill body until preflight has run.

# Docpluck Code Review

You are a code review specialist for Docpluck. Review all changed files against the project's hard rules and best practices.

## Project Location
`C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor`

## Hard Rules (from CLAUDE.md — violations are blockers)

### 1. NEVER use pdftotext with -layout flag
The default mode handles two-column academic papers correctly. The `-layout` flag causes column interleaving.
- **Check:** grep for `-layout` in all Python files
- **Severity:** BLOCKER

### 2. NEVER use AGPL dependencies
pymupdf4llm, PyMuPDF column_boxes(), pymupdf-layout are all AGPL. Incompatible with authenticated service.
- **Check:** grep for `pymupdf4llm`, `column_boxes`, `pymupdf-layout` in imports
- **Check:** Review requirements.txt and package.json for AGPL packages
- **Severity:** BLOCKER

### 3. ALWAYS normalize Unicode MINUS SIGN (U+2212)
PDFs use U+2212 for negative values. Must convert to ASCII hyphen.
- **Check:** If normalize.py is modified, verify U+2212 → `-` replacement exists
- **Severity:** BLOCKER

### 4. NEVER hardcode secrets, API keys, database URLs
- **Check:** grep for connection strings, API keys, tokens in source files
- **Check:** .env.local must be in .gitignore
- **Severity:** BLOCKER

### 5. NEVER strip HTML with greedy `<[^>]+>` regex
The `<` in `p < .001` gets interpreted as HTML tag start, eating content.
- **Check:** If any HTML stripping is added, verify it uses explicit tag names
- **Severity:** BLOCKER

### 6. NEVER use broad character classes in normalization re.sub patterns (D5 lesson, 2026-04-12)
`[^\n]`, `.`, `\S` as catch-all in `re.sub` replacements will match real statistical content and silently destroy data. The D5 bug (`[^\n]{1,20}` eating real p-values) affected ~1,590 PDFs and ~800-1,200 stat lines.
- **Check:** If `normalize.py` is modified, verify ALL `re.sub` patterns use narrow character classes (e.g., `[a-zA-Z]` not `[^\n]`)
- **Check:** Every regex that skips/removes content must have TWO independent safety guards (constrain both the skipped content AND the replacement target)
- **Check:** Every regex must be tested against `stat-value\nsection-number` patterns (the #1 false positive in academic PDFs)
- **Check:** Run `pytest tests/test_d5_normalization_audit.py -v` (153 tests) after any normalization change
- **Severity:** BLOCKER

## Review Checklist

### Python Service (`service/`)

- [ ] No `-layout` flag in pdftotext calls
- [ ] No AGPL imports
- [ ] normalize.py handles U+2212, U+2013, U+2014, U+2010, U+2011
- [ ] All 16 normalization steps present (S0-S9, A1-A6, A3a, A3b)
- [ ] D5 regression test suite passes (153 tests in `test_d5_normalization_audit.py`)
- [ ] Quality scoring uses common-word ratio threshold (0.02)
- [ ] SMP recovery maps Mathematical Italic chars to ASCII
- [ ] Dockerfile uses `python:3.12-slim` base with `poppler-utils`
- [ ] No hardcoded URLs or secrets
- [ ] FastAPI endpoints validate file type and size
- [ ] Temp files cleaned up in `finally` blocks

### Frontend (`frontend/`)

- [ ] Auth.js middleware protects all routes except /login and /api/auth
- [ ] Rate limiting checks daily usage before extraction
- [ ] API route validates session before forwarding to service
- [ ] No secrets in client-side code
- [ ] Environment variables used for all external URLs
- [ ] Drizzle schema matches ARCHITECTURE.md

### Documentation

- [ ] Changes reflected in CLAUDE.md if architectural
- [ ] LESSONS.md updated if a new pitfall was discovered
- [ ] TODO.md updated if features were added/completed

## Output Format

```
## Docpluck Code Review

### Blockers
- [BLOCKER] description (file:line)

### Warnings
- [WARN] description (file:line)

### Suggestions
- [SUGGEST] description

### Summary
X blockers, Y warnings, Z suggestions
Verdict: APPROVE / REQUEST CHANGES
```

## Final step: read ~/.claude/skills/_shared/postflight.md and follow it.
