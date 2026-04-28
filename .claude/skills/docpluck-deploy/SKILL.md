---
name: docpluck-deploy
description: Deploy Docpluck to production. Pre-flight checks (Next.js build, Python service health, git status), verify Vercel env vars (DATABASE_URL, AUTH_SECRET, AUTH_GITHUB_ID, AUTH_GOOGLE_ID, EXTRACTION_SERVICE_URL), push to GitHub for auto-deploy, verify Vercel deployment status, check Railway extraction service health, run post-deploy smoke test. Use /docpluck-deploy to deploy or verify deployment.
tags: [docpluck, nextjs, python, vercel, railway, neon, auth, deploy]
---

## [MANDATORY FIRST ACTION] preflight (do NOT skip, even if orchestrated by /ship)

**Your very first action in this skill, BEFORE reading anything else, is:**

1. Run: `bash ~/.claude/skills/_shared/bin/preflight-filter.sh <this-skill-name>` and print its `🔧 skill-optimize pre-check · ...` heartbeat as your first visible output line.
2. Initialize `~/.claude/skills/_shared/run-meta/<this-skill-name>.json` per `~/.claude/skills/_shared/preflight.md` step 6 (include `phase_start_sha` from `git rev-parse HEAD`).
3. Load `~/.claude/skills/_shared/quality-loop/core.md` into working memory (MUST-level rules gated by /ship).

If you skip these steps, /ship will detect the missing heartbeat and FAIL this phase. Do not proceed to the skill body until preflight has run.

# Docpluck Deploy

Deploy Docpluck to production on Vercel (frontend) and Railway (extraction service).

## Two-Repo Architecture (CRITICAL — read before deploying)

Docpluck is split across **two repos** under `C:\Users\filin\Dropbox\Vibe\MetaScienceTools\`:

| Path | Repo | Visibility | Contains |
|------|------|------------|----------|
| `docpluck/` | `giladfeldman/docpluck` | **public** | The `docpluck` Python library only (extraction + normalization + quality + DOCX/HTML). Published to PyPI. |
| `PDFextractor/` | `giladfeldman/docpluckapp` | **private** | The SaaS app only (Next.js frontend, FastAPI service `service/app/main.py`, Drizzle schema, Auth.js). **No library code duplication** — the service imports `docpluck` via a git pin in `service/requirements.txt`. |

Library changes therefore reach production via TWO steps:
1. Tag + push the library repo (this updates PyPI, but the app pins by git tag).
2. Bump the git pin in `PDFextractor/service/requirements.txt` (`docpluck @ git+https://...@v<NEW>`) and redeploy the app.

**Skipping step 2 silently keeps production on the old library.** Deploy pre-flight check 4 below catches this.

## Pre-Flight Checks

Run ALL checks before deploying. Any failure is a blocker.

### 1. Git Status (both repos)
```bash
cd C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck && git status --short && git log --oneline -3
echo "---"
cd C:/Users/filin/Dropbox/Vibe/MetaScienceTools/PDFextractor && git status --short && git log --oneline -3
```
Both working trees must be clean. Library tagged at `v<X.Y.Z>` matching `__version__`.

### 2. Frontend Build
```bash
cd C:/Users/filin/Dropbox/Vibe/MetaScienceTools/PDFextractor/frontend && npm run build
```
Must pass with 0 errors.

### 3. Python Service Module Check
```bash
cd C:/Users/filin/Dropbox/Vibe/MetaScienceTools/PDFextractor/service && python -c "
from app.main import app
# Library modules (NOT app.normalize / app.quality — those moved to the docpluck library)
from docpluck import normalize_text, NormalizationLevel, compute_quality_score, get_version_info
info = get_version_info()
print(f'All imports OK; docpluck=={info[\"version\"]} normalize={info[\"normalize_version\"]}')
"
```

### 4. Cross-Repo Library Version Sync (CRITICAL)

Verify the app's `service/requirements.txt` git pin matches the library's latest tag. Mismatches mean the deploy will silently ship the OLD library to prod.

```bash
LIB_VERSION=$(grep '^__version__' C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck/docpluck/__init__.py | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
APP_PIN=$(grep -oE 'docpluck.*@v[0-9]+\.[0-9]+\.[0-9]+' C:/Users/filin/Dropbox/Vibe/MetaScienceTools/PDFextractor/service/requirements.txt | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
echo "Library __version__: $LIB_VERSION"
echo "App requirements.txt pin: v$APP_PIN"
if [ "$LIB_VERSION" != "$APP_PIN" ]; then
  echo "❌ MISMATCH — bump PDFextractor/service/requirements.txt to docpluck @ git+https://github.com/giladfeldman/docpluck.git@v$LIB_VERSION before deploying"
  exit 1
fi

# Also verify the API.md examples are not stale beyond a major version
API_DOC_VERSION=$(grep -oE 'docpluck_version["\s:]+[0-9]+\.[0-9]+\.[0-9]+' C:/Users/filin/Dropbox/Vibe/MetaScienceTools/PDFextractor/API.md | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
LIB_MAJOR_MINOR=$(echo "$LIB_VERSION" | cut -d. -f1,2)
DOC_MAJOR_MINOR=$(echo "$API_DOC_VERSION" | cut -d. -f1,2)
if [ "$LIB_MAJOR_MINOR" != "$DOC_MAJOR_MINOR" ]; then
  echo "⚠️ API.md examples reference docpluck_version $API_DOC_VERSION; library is at $LIB_VERSION. Update PDFextractor/API.md."
fi
echo "✅ Library version sync OK"
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
