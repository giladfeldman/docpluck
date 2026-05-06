# Handoff — App-Side Integration of v1.6.0 Section Identification

This is a handoff document for a fresh Claude Code session. Open the PDFextractor repo (NOT this docpluck library repo) in a worktree and paste the prompt at the bottom of this file.

---

## TL;DR

The docpluck library v1.6.0 ships a new section-identification feature (`extract_sections()` + `SectionedDocument`). The library work is **done and merged**. This handoff is for the **app-side** (Next.js + FastAPI) work to expose that capability to end users via:

1. A new FastAPI endpoint `POST /sections` in the extraction service
2. A new Next.js route `/api/sections` proxying it
3. A new upload UI page at `/sections` that lets users drop a PDF and see a labeled section breakdown
4. Updated `API.md` documenting the new endpoint
5. Tests for both the service endpoint and the proxy route

---

## Library context the app session needs to know

The library exposes (all importable from `docpluck`):

```python
from docpluck import (
    extract_sections,        # main entry: (file_bytes=, text=, source_format=) -> SectionedDocument
    SectionedDocument,       # frozen dataclass
    Section,                 # frozen dataclass
    SectionLabel,            # str enum: abstract, introduction, methods, results, ...
    Confidence,              # str enum: low / medium / high
    DetectedVia,             # str enum: markup, layout_signal, heading_match, ...
    SECTIONING_VERSION,      # str: "1.0.0"
)
```

`SectionedDocument` shape:
```python
SectionedDocument(
    sections: tuple[Section, ...],
    normalized_text: str,
    sectioning_version: str,         # "1.0.0"
    source_format: Literal["pdf", "docx", "html"],
)
```
Convenience: `.abstract`, `.introduction`, `.methods`, `.results`, `.discussion`, `.references` (each returns `Section | None`), plus `.get(label)`, `.all(label)`, `.text_for(*labels)`.

`Section` shape:
```python
Section(
    label: str,                       # "methods", "methods_2", "footnotes", "unknown"
    canonical_label: SectionLabel,    # base enum (without numeric suffix)
    text: str,
    char_start: int,
    char_end: int,
    pages: tuple[int, ...],           # 1-indexed; () if unavailable
    confidence: Confidence,
    detected_via: DetectedVia,
    heading_text: str | None,
)
```

The 18 canonical labels (see `docpluck/sections/taxonomy.py`):
`title_block, abstract, keywords, introduction, literature_review, theoretical_background, hypotheses, methods, results, discussion, conclusion, references, footnotes, acknowledgments, funding, disclosures, supplementary, unknown`.

Universal-coverage invariant: `sum(s.char_end - s.char_start for s in doc.sections) == len(doc.normalized_text)` (modulo a single-char tolerance for the F0 footnote sentinel).

Filter sugar already on existing extractors:
```python
from docpluck import extract_pdf, extract_docx, extract_html
text, method = extract_pdf(pdf_bytes, sections=["abstract", "references"])
```

CLI (already wired):
```bash
docpluck sections paper.pdf --format json
docpluck extract paper.pdf --sections abstract,references
```

---

## Pre-flight checks the app session must run first

Before writing any code:

1. Verify the library version is what the app's git pin needs to match:
   ```bash
   cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck
   git log -1 --format="%H %s"
   python -c "from docpluck import __version__; print(__version__)"
   ```
   Expect: `1.6.0`.

2. The library branch `feat/section-identification` must be merged to `main` and tagged `v1.6.0` BEFORE the app session starts (otherwise the git pin can't resolve). If not yet tagged, the app session should stop and ask the user to release the library first.

3. Verify the worktree is set up:
   ```bash
   cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor
   git status
   git checkout -b feat/sections-ui
   ```

---

## Required changes (in order)

### Step 1 — Bump the docpluck git pin

File: `service/requirements.txt`

Change:
```
docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git@v1.5.0
```

to:
```
docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git@v1.6.0
```

Rebuild the service venv:
```bash
cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor\service
pip install --upgrade --force-reinstall -r requirements.txt
python -c "from docpluck import extract_sections, SECTIONING_VERSION; print(SECTIONING_VERSION)"
# Expect: 1.0.0
```

### Step 2 — Add `POST /sections` FastAPI endpoint

File: `service/app/main.py` (or wherever `/extract` lives)

Add a route that mirrors `/extract` but returns sectioned JSON:

```python
from fastapi import FastAPI, UploadFile, File, HTTPException
from docpluck import extract_sections, SectionedDocument

@app.post("/sections")
async def sections_endpoint(file: UploadFile = File(...)) -> dict:
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file too large")
    blob = await file.read()
    try:
        doc = extract_sections(blob)
    except Exception as e:
        raise HTTPException(422, f"sectioning failed: {e}") from e
    return _serialize_sectioned_document(doc)


def _serialize_sectioned_document(doc: SectionedDocument) -> dict:
    return {
        "sectioning_version": doc.sectioning_version,
        "source_format": doc.source_format,
        "normalized_text_length": len(doc.normalized_text),
        "sections": [
            {
                "label": s.label,
                "canonical_label": s.canonical_label.value,
                "char_start": s.char_start,
                "char_end": s.char_end,
                "pages": list(s.pages),
                "confidence": s.confidence.value,
                "detected_via": s.detected_via.value,
                "heading_text": s.heading_text,
                "text": s.text,
            }
            for s in doc.sections
        ],
    }
```

Match the existing `/extract` endpoint's error-handling pattern, auth checks (if any apply at the service level — the frontend usually handles auth), and CORS headers.

### Step 3 — Service-side test

File: `service/tests/test_sections_endpoint.py`

```python
"""POST /sections endpoint integration test."""
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

pytest.importorskip("reportlab")

client = TestClient(app)


def _make_pdf() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 720, "Abstract")
    c.setFont("Helvetica", 11); c.drawString(72, 700, "Body of abstract.")
    c.setFont("Helvetica-Bold", 14); c.drawString(72, 660, "References")
    c.setFont("Helvetica", 11); c.drawString(72, 640, "[1] Doe.")
    c.showPage(); c.save()
    return buf.getvalue()


def test_sections_endpoint_returns_canonical_labels():
    files = {"file": ("x.pdf", _make_pdf(), "application/pdf")}
    r = client.post("/sections", files=files)
    assert r.status_code == 200
    payload = r.json()
    assert payload["sectioning_version"] == "1.0.0"
    assert payload["source_format"] == "pdf"
    labels = {s["canonical_label"] for s in payload["sections"]}
    assert "abstract" in labels
    assert "references" in labels


def test_sections_endpoint_rejects_oversize():
    big = b"%PDF-1.4\n" + b"x" * (50 * 1024 * 1024)  # 50MB
    files = {"file": ("big.pdf", big, "application/pdf")}
    r = client.post("/sections", files=files)
    # Either 413 (size guard) or 422 (sectioning failed) is acceptable
    assert r.status_code in (413, 422)
```

Run: `pytest tests/test_sections_endpoint.py -v` — must pass.

### Step 4 — Next.js API proxy route

File: `frontend/app/api/sections/route.ts`

Mirror the existing `frontend/app/api/extract/route.ts` pattern:

```ts
import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  // Apply the same usage-rate-limiting check that /api/extract uses
  // (read frontend/app/api/extract/route.ts and copy the daily-quota check)

  const formData = await req.formData();
  const file = formData.get("file") as File | null;
  if (!file) {
    return NextResponse.json({ error: "no file" }, { status: 400 });
  }

  const upstream = await fetch(`${process.env.EXTRACTION_SERVICE_URL}/sections`, {
    method: "POST",
    body: formData,
  });

  if (!upstream.ok) {
    return NextResponse.json(
      { error: `service returned ${upstream.status}` },
      { status: upstream.status }
    );
  }

  const data = await upstream.json();

  // Log the usage event (mirror /api/extract's usage-log insert)

  return NextResponse.json(data);
}
```

### Step 5 — Upload UI

File: `frontend/app/sections/page.tsx`

A simple drag-and-drop upload page that POSTs to `/api/sections` and renders the result as a labeled section list. Use the same component style as the existing extract page.

Minimum UX:
- File-drop zone (PDF only)
- Loading indicator while uploading
- Result view: each section shown as a card with `label`, `confidence` badge (color-coded: green=high, yellow=medium, gray=low), `pages` chip, `char_start–char_end` indicator, expandable text
- Top-of-page summary: total sections, sectioning_version, source_format
- Filter chips: click a canonical label to scroll to that section
- Error state for failed uploads

Add the page to the main nav (whichever component holds the existing /extract link).

### Step 6 — Update API.md

File: `API.md` (root of PDFextractor)

Add a new section documenting `POST /sections`:
- URL
- Auth requirements
- Request: multipart with `file` field
- Response shape (full JSON example)
- Error codes (413 for too large, 422 for sectioning failure, 401 for unauthorized)
- Example curl
- Note about `SECTIONING_VERSION` being stable per library version

Also update the service-level overview to mention the new endpoint alongside `/extract` and `/health`.

### Step 7 — Update CLAUDE.md (app-side)

The two-repo CLAUDE.md should mention the new `/sections` endpoint exists. One-line addition.

### Step 8 — Update README.md / ARCHITECTURE.md if needed

If the README has a "what we do" list, add section identification. If ARCHITECTURE has a service-endpoint diagram, add `/sections`.

### Step 9 — Run full QA

```bash
cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor
# Service tests
cd service && python -m pytest tests/ -q
# Frontend build
cd ../frontend && npm run build
# Local smoke: spin up service and frontend, manually upload a test PDF
```

The `/docpluck-qa` skill (in the docpluck repo) should also be re-run to verify the section-identification check (added in skill v1.1) passes against the deployed app.

### Step 10 — Deploy

Standard `/docpluck-deploy` flow. Pre-flight check 4 (git-pin verification) should now pass since the pin matches the released library version.

---

## Out of scope (do NOT do these)

- Don't add a per-section quality score to the API response — that's a v2.x feature (deferred in `TODO.md` of the library).
- Don't add hierarchical/tree section output — also deferred.
- Don't expose `extract_layout` directly — it's marked internal in the library.
- Don't wire the `--sections` filter sugar into the existing `/extract` endpoint as a query param — keep `/extract` and `/sections` as separate endpoints (cleaner for UI, easier to cache).

---

## Estimated complexity

- Steps 1-3 (service): ~1-2 hours including tests
- Step 4 (proxy): ~30 min
- Step 5 (UI): ~3-4 hours depending on polish
- Steps 6-8 (docs): ~30 min
- Step 9-10 (QA + deploy): ~30 min

Total: half-day to one full day.

---

## Prompt to paste into the fresh Claude session

> I'm continuing app-side work to expose docpluck v1.6.0's new section-identification feature in PDFextractor. The library work is complete and tagged. I need to add a new `POST /sections` endpoint, an `/api/sections` Next.js proxy, and a `/sections` upload UI page that displays labeled sections from an uploaded PDF.
>
> Read the full handoff at `C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck\HANDOFF_SECTIONS_APP_INTEGRATION.md` and follow it step by step. Use the superpowers:subagent-driven-development skill — one fresh subagent per logical step (service endpoint, service test, proxy route, UI page, docs) with combined spec-+-quality reviews after each.
>
> Work in a worktree on the PDFextractor repo: `git checkout -b feat/sections-ui` from `main`. Run pre-flight checks first (verify library tag exists and that the service rebuild succeeds with the new git pin). If the library tag `v1.6.0` doesn't exist yet, stop and ask the user to release the library first.
>
> After all steps land, run the full app QA suite (frontend build + service tests + manual smoke) and then `/docpluck-deploy`.
