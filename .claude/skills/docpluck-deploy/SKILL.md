---
name: docpluck-deploy
description: Deploy Docpluck to production. Pre-flight checks (Next.js build, Python service health, git status), verify Vercel env vars (DATABASE_URL, AUTH_SECRET, AUTH_GITHUB_ID, AUTH_GOOGLE_ID, EXTRACTION_SERVICE_URL), push to GitHub for auto-deploy, verify Vercel deployment status, check Railway extraction service health, run post-deploy smoke test. Use /docpluck-deploy to deploy or verify deployment.
tags: [docpluck, nextjs, python, vercel, railway, neon, auth, deploy]
---

## Before starting: read ~/.claude/skills/_shared/preflight.md and follow it for this skill.

# Docpluck Deploy

Deploy Docpluck to production on Vercel (frontend) and Railway (extraction service).

## Project Location
`C:\Users\filin\Dropbox\Vibe\PDFextractor`

## Pre-Flight Checks

Run ALL checks before deploying. Any failure is a blocker.

### 1. Git Status
```bash
cd C:/Users/filin/Dropbox/Vibe/PDFextractor
git status
git log --oneline -3
```
Working tree must be clean. All changes committed.

### 2. Frontend Build
```bash
cd frontend && npm run build
```
Must pass with 0 errors.

### 3. Python Service Module Check
```bash
cd service && python -c "
from app.main import app
from app.normalize import normalize_text, NormalizationLevel
from app.quality import compute_quality_score
print('All imports OK')
"
```

### 4. Verify Vercel Environment Variables
```bash
cd frontend && vercel env ls
```

Required variables (all must show as "Encrypted"):
- `DATABASE_URL` — Neon connection string
- `AUTH_SECRET` — Auth.js session key
- `AUTH_TRUST_HOST` — must be `true`
- `AUTH_GITHUB_ID` — GitHub OAuth client ID
- `AUTH_GITHUB_SECRET` — GitHub OAuth client secret
- `AUTH_GOOGLE_ID` — Google OAuth client ID
- `AUTH_GOOGLE_SECRET` — Google OAuth client secret
- `EXTRACTION_SERVICE_URL` — Railway service URL

If any are missing, refer to SETUP_GUIDE.md.

## Deploy

### Frontend (Vercel)
Push to GitHub triggers auto-deploy:
```bash
git push origin master
```

Or manual deploy:
```bash
cd frontend && vercel --prod
```

### Extraction Service (Railway)
If connected to GitHub, push triggers auto-deploy.

If not connected, deploy via CLI:
```bash
cd service && railway up --detach
```

Note: Railway CLI upload may timeout. If so, connect GitHub repo in Railway dashboard (root dir `/service`).

## Post-Deploy Verification

### 1. Vercel Deployment Status
```bash
cd frontend && vercel ls | head -5
```
Latest deployment must show `Ready`.

### 2. Frontend Health
```bash
curl -s -o /dev/null -w "%{http_code}" https://docpluck.vercel.app/login
```
Must return 200.

### 3. Railway Service Health
```bash
curl -s https://extraction-service-production-d0e5.up.railway.app/health
```
Must return `{"status":"ok",...}`.

### 4. Smoke Test (if service is live)
```bash
# Test extraction endpoint directly
curl -s -X POST https://extraction-service-production-d0e5.up.railway.app/extract \
  -F "file=@test-pdfs/apa/chan_feldman_2025_cogemo.pdf" | python -c "
import sys, json
data = json.load(sys.stdin)
print(f'Engine: {data[\"metadata\"][\"engine\"]}')
print(f'Chars: {data[\"metadata\"][\"chars\"]}')
print(f'Quality: {data[\"quality\"][\"score\"]}')
assert data['metadata']['chars'] > 10000, 'Too few chars'
assert data['quality']['score'] >= 80, 'Quality too low'
print('Smoke test: PASS')
"
```

## Rollback

If deployment fails:
```bash
# Vercel: rollback to previous deployment
cd frontend && vercel rollback

# Railway: redeploy from last working commit
railway service extraction-service
railway redeploy
```

## Report Format

```
## Docpluck Deploy Report

### Pre-Flight
| Check | Status |
|-------|--------|
| Git clean | PASS/FAIL |
| Frontend build | PASS/FAIL |
| Service modules | PASS/FAIL |
| Env vars | X/Y present |

### Deployment
| Target | Status | URL |
|--------|--------|-----|
| Vercel | DEPLOYED/FAILED | https://docpluck.vercel.app |
| Railway | DEPLOYED/FAILED | https://extraction-service-production-d0e5.up.railway.app |

### Post-Deploy
| Check | Status |
|-------|--------|
| Frontend 200 | PASS/FAIL |
| Service health | PASS/FAIL |
| Smoke test | PASS/FAIL/SKIP |
```

## Final step: read ~/.claude/skills/_shared/postflight.md and follow it.
