# Release flow (Phase 6 + Phase 7 detail)

> Loaded on demand from SKILL.md Phase 6 / 7. Do not load up-front.

Once **all** Phase 5 gates pass, ship the cycle.

## Phase 6 · Release

### 6.1 · Bump versions consistently
- `docpluck/__init__.py::__version__` (patch for fixes; minor for behavior changes; major for API breaks)
- `pyproject.toml::version`
- `docpluck/normalize.py::NORMALIZATION_VERSION` — **only if normalize.py changed**
- `docpluck/sections/__init__.py::SECTIONING_VERSION` — only if sections code changed
- `CHANGELOG.md` — add a `## [vX.Y.Z] — YYYY-MM-DD` block per the existing format (Defect / Fix / Verification / Bumps / Tests / Out of scope)

### 6.2 · Invoke `/docpluck-cleanup`
Doc + version pin sync across both repos. Wait for its postflight heartbeat. If it FAILs, fix what it surfaces before continuing.

### 6.3 · Invoke `/docpluck-review`
Hard-rule check on staged changes. Blockers must be fixed before tag push. Especially: never `-layout` flag, never AGPL deps, U+2212 normalize, F0 sentinel preservation.

### 6.4 · Commit + tag + push the library
```bash
git add CHANGELOG.md docpluck/__init__.py docpluck/<changed>.py pyproject.toml tests/test_<module>.py
git commit -m "$(cat <<'EOF'
release: vX.Y.Z — <one-line summary>

<body explaining what + why + which papers / which test files added>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git tag vX.Y.Z
git push origin main
git push origin vX.Y.Z
```

Per CLAUDE.md `git` rules: NEVER `--amend`, NEVER `--no-verify`, NEVER `--force` to main, NEVER `git add -A`/`.`.

### 6.5 · Auto-bump bot opens app PR (~30s after tag push)
```bash
gh pr list --repo giladfeldman/docpluckapp --state open --search "vX.Y.Z" --json number,title
```

When the PR appears, merge it:
```bash
gh pr merge <N> --repo giladfeldman/docpluckapp --squash --delete-branch
```

## Phase 7 · Deploy verification

Two paths — pick by complexity of the change:

### 7a · Simple path (most cycles)

Wait for Railway to redeploy with the new pin (~2–4 min) and verify `/_diag` shows the new version. Use a Monitor with bounded poll:

```bash
while true; do
  v=$(curl -s --max-time 10 https://extraction-service-production-d0e5.up.railway.app/_diag 2>/dev/null \
      | python -c "import sys, json; print(json.load(sys.stdin).get('docpluck_version','?'))" 2>/dev/null)
  if [ "$v" = "X.Y.Z" ]; then echo "DEPLOYED vX.Y.Z"; break; fi
  sleep 20
done
```

Then probe one extraction endpoint with the affected paper to confirm the fix is live (e.g. `/tables` on chan_feldman_2025_cogemo).

### 7b · Full deploy path (Defect classes that touch the app)

Invoke `/docpluck-deploy`. It runs the canonical pre-flight + post-deploy checks. Wait for its postflight heartbeat. Treat any FAIL as a phase failure for this cycle.

## Common release failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| Auto-bump PR doesn't open within 60s | `bump-app-pin.yml` workflow failed or `APP_REPO_TOKEN` expired | Check workflow run in `docpluck/.github/`; rotate token if needed |
| `/_diag` stuck at old version after 8 min | Railway deploy failed OR `verify-railway-deploy.yml` PR check is failing | Check Railway logs; manually trigger redeploy via dashboard |
| `gh pr merge` returns "not mergeable" | PR has merge conflicts (rare for auto-bump) | Manual rebase on master |
| App requirements.txt pin doesn't match library version | Pre-existing app drift | `/docpluck-cleanup` enforces this; should have been caught Phase 6 |
| `git push` rejected | Branch protection or divergence | MUST-STOP — surface to user |
