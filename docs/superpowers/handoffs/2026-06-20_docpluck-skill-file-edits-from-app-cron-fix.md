# Handoff — commit 2 docpluck skill-file edits (from the app-repo daily-digest cron fix)

**Date:** 2026-06-20
**For:** the concurrent session working in the `docpluck` (library) repo
**Action needed:** commit two tracked-but-uncommitted skill files, by explicit path. ~2 minutes. No code logic involved.

## TL;DR

A sibling session fixed a production bug in the **app** repo (`PDFextractor` / `docpluckapp`), not the library. As part of that work it made two edits inside the **docpluck** repo's tooling tree:

| File | Change |
|------|--------|
| `.claude/skills/_project/lessons.md` | Appended one R1 lesson: *"2026-06-20 · docpluckapp (frontend) · daily-digest cron 'Daily dispatch failed' = transient Neon, not a logic bug → withDbRetry"* |
| `.claude/skills/docpluck-deploy/SKILL.md` | Fixed post-deploy check 5: the dry-run gate referenced a non-existent `wouldSend` field (the route returns a `DispatchResult`); also documented that `CRON_SECRET` is a Vercel-only var and must be pulled just-in-time. |

Both are pure docs/journal updates. They are **unrelated** to your REQUEST_10/11 table-flatten stream and must not be folded into it.

## Why they're uncommitted

The session that wrote them deploys from the **app** repo and chose not to push the **library** repo (pushing `docpluck` `main` triggers the ~5–10 min pre-push canary hook, and there was no library change to justify it). You're already active in this repo, so committing these alongside your next push is the lowest-friction path.

## How to commit (explicit paths — do NOT `git add -A`)

Staging only these two paths keeps your REQUEST_10/11 working-tree changes (`docpluck/tables/flatten.py`, `tests/conftest.py`, the REQUEST_*.md files, the new blank-header test) out of this commit:

```bash
cd C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck
git add .claude/skills/_project/lessons.md .claude/skills/docpluck-deploy/SKILL.md
git commit -m "docs(skills): record daily-digest cron lesson + fix deploy check-5 (from app-repo cron fix)" \
  -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

You can push them whenever you next push the library (the canary hook will run as usual — never `timeout`/kill it; verify with `git ls-remote`).

## Context — what the app-repo fix was (for reference only; already shipped)

The `docpluck.app` "Docpluck daily — 1 error" admin email was reporting `api/cron/daily-digest` → "Daily dispatch failed". Root cause (confirmed from prod `system_logs`): transient **Neon serverless** errors (connection recycled on scale-to-zero; control-plane 500 tagged `neon:retryable:true`) abort a single `neon-http` query and neither unattended cron retried. Fix added `withDbRetry` around every cron DB call + the in-band `sendEmail`.

Already committed **and deployed to production** in the app repo (`giladfeldman/docpluckapp`, branch `master`):

- `331b11a` — fix(notify): retry transient Neon errors in daily-digest + blob-cleanup crons (+ regression test)
- `ea86e85` — chore(lint): clear pre-existing eslint debt
- `0de4167` — chore(vercel): track frontend/.vercel/project.json to prevent duplicate projects

Post-deploy dry-run smoke = HTTP 200 + clean `DispatchResult`. **Nothing is pending in the app repo.** This handoff is only about the two docpluck-repo skill files above.
