# Library ↔ App version-sync process

**Problem:** Until v2.4.9, the `docpluck` library could ship a new tag (v2.4.6, v2.4.7, …) and the production extraction service on Railway kept running v2.4.5 silently — there was no automation linking the two repos and no observable signal that they were out of sync.

**Three-part fix shipped 2026-05-13:**

## 1. Real library-version reporting (`docpluckapp` service)

`PDFextractor/service/app/main.py`:

- Imports `docpluck` and exposes `docpluck.__version__` as the new module-level constant `DOCPLUCK_VERSION`.
- `/health` now returns `docpluck_version`, `service_version`, `sectioning_version`, and `table_extraction_version`.
- Every extraction endpoint's response metadata (`/extract`, `/render`, `/sections`, `/tables`) now reports the actual library version, not the FastAPI app version.
- Response header `x-docpluck-version` on `/render` mirrors the library version.

Verify live:
```bash
curl -s https://extraction-service-production-d0e5.up.railway.app/health \
  | python -c "import json,sys; print(json.load(sys.stdin)['docpluck_version'])"
```

## 2. Auto-bump workflow (`docpluck` library repo)

`.github/workflows/bump-app-pin.yml` triggers on any `v*.*.*` tag push:

1. Checks out `giladfeldman/docpluckapp` using the `APP_REPO_TOKEN` secret (a GitHub PAT with `repo` scope).
2. Rewrites `service/requirements.txt` to pin the new tag.
3. Opens a PR titled `pin: auto-bump docpluck library to vX.Y.Z`.
4. Enables auto-merge (squash). If repo auto-merge is disabled, the PR sits for manual review.

**Setup required once** (in this `docpluck` repo):

```bash
# Create a fine-scoped PAT with repo scope on giladfeldman/docpluckapp
gh secret set APP_REPO_TOKEN --repo giladfeldman/docpluck --body "$YOUR_PAT"
```

After setup, every `git tag vX.Y.Z && git push --tags` here triggers an
automatic PR in the app repo. No manual `service/requirements.txt` edit
needed.

## 3. Post-deploy verifier (`docpluckapp` repo)

`.github/workflows/verify-railway-deploy.yml` runs on every push to
`master` that touches `service/requirements.txt`, `service/**`, or the
workflow itself:

1. Parses the pinned library version from `service/requirements.txt`.
2. Polls `https://extraction-service-production-d0e5.up.railway.app/health`
   every 10s for up to ~8 min.
3. Asserts `health.docpluck_version` equals the pinned version.
4. Fails the build with a pointer to the Railway dashboard + manual
   redeploy command if the mismatch persists.

This catches:
- Build failures (Railway keeps serving the old container — verifier flags it).
- Watch-Paths misconfigurations (Railway didn't trigger a build at all).
- `pip` wheel caches that don't re-fetch the git URL despite tag bump.

## End-to-end flow

```
Release library:
   git tag v2.4.10 && git push --tags
       ↓
   Workflow #1 in `docpluck` repo:
       opens PR in `docpluckapp` bumping pin
       auto-merges if CI is green
       ↓
   Push to `docpluckapp@master` happens
       ↓
   Railway sees commit on `docpluckapp@master`
       → rebuilds extraction-service
       → pip pulls @v2.4.10 fresh
       ↓
   Workflow #3 in `docpluckapp` repo polls /health
       → asserts docpluck_version == "2.4.10"
       → green build = real verification, not just deploy-fired
```

If any link breaks (PAT expired, Railway watch-paths broken, build
failure, pip cache stale, library bug), the verifier in #3 turns the
build red — you find out within ~8 min instead of by user report.

## Manual fallback (when you can't wait for the bot)

If the bot fails or you need to ship a specific commit:

```bash
# 1. Bump pin manually
cd PDFextractor
sed -i 's|docpluck.git@v[0-9.]*|docpluck.git@v2.4.10|' service/requirements.txt
git add service/requirements.txt
git commit -m "pin: bump docpluck library to v2.4.10"
git push origin master

# 2. If Railway doesn't auto-build, force it:
railway link --project docpluck  # once
railway redeploy --from-source --service extraction-service --yes

# 3. Wait for verifier workflow run + check
gh run watch --repo giladfeldman/docpluckapp
```
