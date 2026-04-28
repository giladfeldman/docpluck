# Docpluck — Library Repo (giladfeldman/docpluck, public)

## Two-Repo Architecture

Docpluck is split across **two repos** under `Vibe/MetaScienceTools/`:

| Path | Repo | Visibility | Contains |
|------|------|------------|----------|
| `docpluck/` (this repo) | `github.com/giladfeldman/docpluck` | **public** | The `docpluck` Python library only. Published to PyPI as `docpluck`. |
| `PDFextractor/` | `github.com/giladfeldman/docpluckapp` | **private** | The SaaS app (Next.js + FastAPI). **No library code lives here** — the service imports `docpluck` via a git pin in `service/requirements.txt`. |

### Why split

- Library can be open-sourced under MIT and consumed by anyone via PyPI without exposing app secrets/auth/billing logic.
- App can iterate freely without forcing library releases.
- No code duplication: there is exactly one copy of `extract.py` / `normalize.py` / `quality.py` etc., and it lives here.

### How the app consumes this library

`PDFextractor/service/requirements.txt` pins:
```
docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git@v<VERSION>
```

When this library releases a new version, the app's `requirements.txt` git pin must be bumped or production silently keeps running the old library. The `/docpluck-deploy` skill's pre-flight check 4 enforces this.

## Release flow (library → production)

1. Make + commit changes in this repo. Bump `__version__` (in `docpluck/__init__.py`), `version` (in `pyproject.toml`), and `NORMALIZATION_VERSION` (in `docpluck/normalize.py`) consistently.
2. Update `CHANGELOG.md`.
3. Push to `main`, then tag: `git tag v<VERSION> && git push --tags`.
4. (Optional) Publish to PyPI: `python -m build && twine upload dist/*`.
5. In `PDFextractor/service/requirements.txt`, bump the `@v<VERSION>` git pin and update any frozen version examples in `PDFextractor/API.md`.
6. Run `/docpluck-deploy` from the docpluck repo — pre-flight check 4 verifies the pin matches.

Skipping step 5 is the most common failure mode. The deploy skill catches it.

## Critical hard rules (from project history)

- **NEVER use pdftotext with `-layout` flag** — causes column interleaving on two-column papers. See `docpluck/extract.py:13–16`.
- **NEVER use `pymupdf4llm` or `column_boxes()`** — AGPL license, incompatible with the authenticated SaaS service.
- **ALWAYS normalize Unicode MINUS SIGN (U+2212) → ASCII hyphen** — breaks statistical pattern matching otherwise. (`normalize.py` step S5.)
- **Test on APA psychology / RR papers** — not ML / engineering papers (false-positive stats from performance-metric tables).

## Project skills (in `.claude/skills/docpluck-*`)

These four skills span BOTH repos via absolute paths. Keep paths in sync if either repo moves.

| Skill | Purpose | Targets |
|-------|---------|---------|
| `docpluck-qa` | Full QA suite | Library tests + service tests + ESCIcheck PDFs + production endpoints |
| `docpluck-review` | Code review against hard rules | Both repos' source files |
| `docpluck-cleanup` | Doc / dead-code / config sync | Both repos' docs |
| `docpluck-deploy` | Pre-flight + deploy + verify | Library tag → app requirements bump → Vercel/Railway |

## Key project docs (in `docs/`)

- `docs/README.md` — public-facing library README (renders on GitHub + PyPI).
- `docs/BENCHMARKS.md` — extraction-quality benchmarks across 50 PDFs.
- `docs/NORMALIZATION.md` — pipeline step-by-step reference.
- `docs/DESIGN.md` — architecture decisions.
- `docs/superpowers/specs/` — design docs for individual features (e.g. Request 9 reference normalization).
