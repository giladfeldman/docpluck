# Three-tier parity chain (library → local-app → production)

> Loaded on demand from SKILL.md Phase 5e / Phase 6 / Phase 7. Mandatory; the chain is a hard sequence.

The library is consumed by an authenticated SaaS service. Bug surface is multiplicative across tiers:

- A library that renders correctly **standalone** can render differently under the **service** (different Python version, different shell encoding, different pdftotext version, different package cache, layout extraction process boundaries).
- A service that renders correctly **locally** can render differently in **production** (different OS, different pdftotext version — Xpdf 4.00 locally vs poppler 25.03 on Railway, memory `feedback_pdftotext_version_skew`; different file-system permissions for Camelot temp dirs; different env vars).

The three tiers MUST match. If they don't, the bug isn't "shipped" — it's just located somewhere new.

```
   TIER 1 (library)         TIER 2 (local app)         TIER 3 (production)
   ─────────────────        ─────────────────          ─────────────────
   render_pdf_to_markdown()  POST /extract via         POST /extract via
   called directly from      uvicorn :6117 + Next      Railway prod URL
   Python                    :6116 in this dev shell

   Output A                  Output B                   Output C

       MUST EQUAL                MUST EQUAL
       (A == B)                  (B == C)
```

Equality is exact-byte-match for the rendered `text` field. Allowed deltas: timestamp / request-id metadata, `extracted_via` provenance string, version numbers in metadata. All MD content (sections, tables, normalization) must be identical.

---

## Tier 1 — Library (standalone)

This is what Phase 5a–d already covers. The library is exercised directly:

```python
from docpluck.render import render_pdf_to_markdown
from docpluck.extract_structured import extract_pdf_structured

md = render_pdf_to_markdown(<pdf-bytes>)         # Tier 1 rendered output
s = extract_pdf_structured(<pdf-bytes>)          # Tier 1 structured output
```

Outputs go to `tmp/<paper>_v<version>.md` and `tmp/<paper>_v<version>_structured.json`. Phase 5d AI-verifies these.

**Hard rule:** Tier 1 tests run against ACTUAL PDFs in `../PDFextractor/test-pdfs/`, not synthesized text. A unit test that uses `text = "ABSTRACT\nblah blah\n\nKEYWORDS foo\n\nBody..."` is NOT a Tier 1 test — it's a contract test for one helper function, useful but insufficient. Every cycle adds at least ONE real-PDF regression test alongside any contract test.

---

## Tier 2 — Local app parity

This is the new phase. Most cycles, library output → local-app output is identical; but the cycles where they differ are exactly the ones that ship subtle prod bugs. Skipping this tier is how production silently diverges from local-dev expectations.

### 2.1 — Start the dev stack (one-shot per session, not per cycle)

```bash
# Library is installed editable into the service's venv — service picks up
# the current working tree's library code at process start. Restart needed
# whenever library code changes between cycles.

cd ../PDFextractor/service
python -m uvicorn app.main:app --port 6117 --env-file .env > /tmp/docpluck-svc.log 2>&1 &
# Use run_in_background: true; Monitor for "Application startup complete"

cd ../frontend
npm run dev > /tmp/docpluck-fe.log 2>&1 &
# Use run_in_background: true; Monitor for "Ready in"
```

After each library version bump in Phase 6, RESTART uvicorn before Tier 2 verify — Python module cache holds the OLD library code otherwise.

### 2.2 — Probe each affected paper through the service

```bash
# Get an admin API key (one-shot per session — keep the value in env var)
ADMIN_KEY=$(DATABASE_URL="$(grep ^DATABASE_URL ../PDFextractor/frontend/.env.local | cut -d= -f2-)" \
            node ../PDFextractor/frontend/scripts/get-or-create-admin-key.mjs 2>&1 | tail -1)

# For each affected paper, POST to /extract and save the response
for paper in <affected-papers>; do
  curl -sS -X POST \
    -H "Authorization: Bearer $ADMIN_KEY" \
    -F "file=@../PDFextractor/test-pdfs/<style>/$paper.pdf" \
    http://localhost:6117/extract \
    | python -c "import sys, json; r = json.load(sys.stdin); print(r['text'])" \
    > tmp/${paper}_v<version>_local-app.md
done
```

For structured extraction (tables):

```bash
curl -sS -X POST -H "Authorization: Bearer $ADMIN_KEY" \
  -F "file=@../PDFextractor/test-pdfs/<style>/$paper.pdf" \
  http://localhost:6117/extract-structured \
  > tmp/${paper}_v<version>_local-app_structured.json
```

### 2.3 — Diff Tier 1 vs Tier 2

```bash
diff tmp/<paper>_v<version>.md tmp/<paper>_v<version>_local-app.md
```

**Expected:** no diff (except trailing newline maybe). Any content diff is a Tier 1 ≠ Tier 2 finding and blocks the cycle.

Common Tier 2 divergences and their causes:

| Diff symptom | Cause | Fix |
|--------------|-------|-----|
| Service version != library version in metadata | uvicorn picked up cached library | Restart uvicorn |
| Unicode normalization diff (NFC vs NFD) | Service request-body decoding differs | Check `app/main.py::extract_endpoint` — must use `file.read()`-then-pass-bytes pattern, not `file.read().decode()` |
| Trailing whitespace differs | One side strips, other doesn't | Standardize in renderer |
| Whole sections present in one, absent in other | DIFFERENT LIBRARY VERSION RUNNING | Verify `docpluck.__version__` returned by /health matches working-tree |

If Tier 2 fails: do NOT proceed to Phase 6 release. Revert to a known-good state or fix the divergence. Tier 2 is a hard gate.

### 2.4 — UI smoke check (every 3rd cycle, NOT every cycle)

Upload one paper through the actual Next.js frontend (Chrome MCP), open all five view tabs (Rendered / Raw / Normalized / Sections / Tables), and visually compare each tab against the Tier 1 outputs:

- Rendered tab content = Tier 1 `render_pdf_to_markdown` output
- Raw tab = Tier 1 pdftotext output
- Normalized tab = Tier 1 `normalize_text(...)` step output
- Sections tab = Tier 1 `extract_sections(...)` JSON
- Tables tab = Tier 1 `extract_pdf_structured(...)['tables']`

This catches frontend-side rendering bugs (CSS / HTML escape / serialization) that the curl smoke does not.

---

## Tier 3 — Production parity

After Phase 6 release lands and Railway redeploys (Phase 7), production must match Tier 2 (and therefore Tier 1).

### 3.1 — Probe each affected paper against prod

```bash
PROD_URL=https://extraction-service-production-d0e5.up.railway.app

for paper in <affected-papers>; do
  curl -sS -X POST \
    -H "Authorization: Bearer $ADMIN_KEY" \
    -F "file=@../PDFextractor/test-pdfs/<style>/$paper.pdf" \
    "$PROD_URL/extract" \
    | python -c "import sys, json; r = json.load(sys.stdin); print(r['text'])" \
    > tmp/${paper}_v<version>_prod.md
done
```

### 3.2 — Diff Tier 2 vs Tier 3

```bash
diff tmp/<paper>_v<version>_local-app.md tmp/<paper>_v<version>_prod.md
```

**Expected:** no content diff. Allowed: pdftotext-version-skew differences (Xpdf 4.00 local vs poppler 25.03 prod) — paragraph spacing (`\n\n` vs `\n`) may differ in raw outputs, but rendered .md should normalize this away. If the difference is in NORMALIZED text or RENDERED markdown beyond expected encoding, that's a Tier 2 ≠ Tier 3 finding.

Common Tier 3 divergences:

| Diff symptom | Cause | Fix |
|--------------|-------|-----|
| Whole paragraphs in different order | poppler vs Xpdf reading-order difference | Library has a known-paper-class workaround (per `_synthesize_introduction_if_bloated_front_matter`) — verify those firing both sides |
| Extra `\n\n` paragraph breaks on one side | Xpdf inserts `\n\n` for paragraphs; poppler often uses `\n` | Renderer must operate at line level, not split on `\n\n` (memory `feedback_pdftotext_version_skew`) |
| Tables present locally, absent on prod | Camelot install drift on Railway | Check `/_diag` for `camelot_version`; check Dockerfile for `ghostscript libgl1 libglib2.0-0` |
| Library version mismatch | Auto-bump PR didn't land or didn't redeploy | Check `/_diag::docpluck_version` against the cycle's tag |

### 3.3 — Tier 3 AI verify (every 3rd cycle, OR every cycle if Tier 2 had unusual deltas)

For one randomly-chosen affected paper, run the full AI-verify (per `references/ai-full-doc-verify.md`) against the PROD `text` output. Compare verdict to Tier 1 AI-verify for the same paper. The verdicts should match.

If Tier 3 AI verify finds NEW issues that Tier 1 didn't, the bug is in the prod environment, not the library — escalate as a deploy issue, not a library issue.

---

## Allowed deltas across tiers (document and exempt)

Some deltas are pdftotext-version-induced and intentional. Document them in `tmp/known-tier-deltas.md` so future cycles don't chase phantoms:

```markdown
## Known Tier 2 ≠ Tier 3 deltas (pdftotext version skew)

| Paper | Field | Local (Xpdf 4.00) | Prod (poppler 25.03) | Reason |
|-------|-------|-------------------|----------------------|--------|
| chan_feldman | Table 1 raw_text trailing newlines | 3 `\n` | 1 `\n` | poppler doesn't insert `\n\n` between page-boundary lines |
| efendic | NFC vs NFKC | NFC | NFC | both produce NFC, no delta — listed for completeness |
```

Updating this file is part of Phase 5e / Phase 7 — never ignore an unexpected delta without documenting it.

---

## Failure modes the three-tier chain catches

This is why it exists, in order of how badly each one would have failed if shipped without the parity check:

1. **v2.4.13 incident** — Camelot was installed locally (dev convenience) but not declared in `pyproject.toml`. Library Tier 1 worked perfectly for months. Prod Tier 3 returned 0 structured tables on every PDF because Camelot was absent. Memory: `feedback_no_silent_optional_deps`. Three-tier would have caught this at first Tier 3 probe.
2. **pdftotext version skew** — local Xpdf 4.00 emits `\n\n` for paragraph breaks; prod poppler 25.03 emits `\n`. Heuristics tuned only against `\n\n` silently produced different output on prod. Three-tier would have caught this immediately.
3. **Frontend table-tab regression** — library + service correct, but frontend's `<pre>` rendering of `raw_text` stripped leading whitespace and the user saw broken cell alignment. UI smoke (Tier 2.4) catches this; curl smoke doesn't.
4. **Service request-body encoding bug** — if `app/main.py` ever switches from passing raw bytes to passing decoded strings, all non-ASCII content corrupts. Tier 1 ≠ Tier 2 byte-diff catches this on the first paper with non-ASCII characters.

Each of these is a real incident class. The three-tier chain is the gate.
