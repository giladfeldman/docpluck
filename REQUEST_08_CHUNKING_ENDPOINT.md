# Docpluck Request 8 — Structural Chunking in the Extract Response

**Requested by:** ESCImate team
**Date:** 2026-04-11
**Priority:** HIGH (unblocks Phase C.3 remaining gap + prevents whole class of cross-project failures)
**Related:**
- `REQUESTS_FROM_ESCIMATE.md` (the parent doc — this is Request 8, a new addition)
- `HANDOVER_ESCIMATE_BASELINE_BLOCKERS.md` (the previous round of bugs, all now shipped in 1.4.0)
- `c:/Users/filin/Dropbox/Vibe/ESCIcheckapp/tests/outputs/docpluck_shootout/baseline/BASELINE_REPORT.md` (the baseline gap report that motivated this request)

---

## TL;DR

Docpluck should return **structural chunks** alongside flat text. A chunk is a stable, paragraph-or-section-level unit of text with byte offsets and a type tag (`paragraph`, `heading`, `table_row`, `metadata_header`, `caption`, `footnote`, etc). Downstream consumers (ESCImate, MetaESCI, Scimeto, future projects) iterate over chunks instead of re-chunking raw text themselves.

**Why now:** The baseline shootout found that ESCImate's stat-detection chunker is coupled to a specific upstream whitespace convention. When Docpluck preserves a Frontiers article-metadata header as three lines (`TYPE\nPUBLISHED\nDOI`) instead of one, ESCImate's chunk boundaries shift, one stat is missed, and another picks up a wrong df. Both extractions are faithful — it's just that chunking logic doesn't belong in the downstream consumer at all. It belongs in Docpluck where text structure is known.

**Scope:** Chunking ONLY. Not stat detection, not citation matching, not any domain-specific parsing. Docpluck's job stays "text extraction + normalization + structural segmentation." ESCImate's job stays "statistical interpretation, recomputation, and validation." The boundary moves up by exactly one layer.

---

## The concrete failure that motivated this

From the 2026-04-11 baseline shootout:

**File:** `frontiers_motivation_2024.pdf` (Frontiers in Psychology, APA-style stats)

**Current ESCImate pipeline** produced text with header collapsed onto one line (older pdftotext version on Windows):
```
TYPE Original Research PUBLISHED 02 May 2024 DOI 10.3389/fpsyg.2024.1388651
```

**Docpluck 1.4.0** (running on Railway with newer poppler) preserved line breaks as they appear in the PDF:
```
TYPE Original Research
PUBLISHED 02 May 2024
DOI 10.3389/fpsyg.2024.1388651
```

Both are faithful to their respective pdftotext outputs. Both are correct. But `effectcheck::check_text()` in ESCImate processes text in chunks of ~30 tokens and uses chunk boundaries to decide which `df` number to associate with a nearby statistic. When Docpluck preserves the extra line breaks, chunks shift by ~1 position, and:

- One statistic (`r(24) = 0.195, p = 0.240`) lands in a chunk that the detector skips entirely
- Another statistic (`r = 0.265, p = 0.108`) picks up the wrong surrounding `df` token (reads `df = 76` instead of `df = 28`)

This is not a Docpluck bug. It's ESCImate's chunker depending on upstream whitespace that it shouldn't care about. The proper fix is to move chunking out of ESCImate entirely.

**Generalizing the lesson:** any downstream consumer that has to re-segment Docpluck's flat text is duplicating work that Docpluck could do once, consistently, for every consumer. That duplication is the source of exactly the class of bug we just hit.

---

## Proposed API addition

### New response field: `chunks`

Every `/api/extract` response gains an optional `chunks` field:

```json
{
  "text": "...the existing flat text...",
  "chunks": [
    {
      "id": 0,
      "type": "metadata_header",
      "text": "TYPE Original Research\nPUBLISHED 02 May 2024\nDOI 10.3389/fpsyg.2024.1388651",
      "byte_start": 0,
      "byte_end": 89,
      "section": "header"
    },
    {
      "id": 1,
      "type": "heading",
      "text": "Promoting intrinsic motivation through teacher feedback",
      "byte_start": 91,
      "byte_end": 146,
      "section": "title",
      "heading_level": 1
    },
    {
      "id": 2,
      "type": "paragraph",
      "text": "Participants (N = 142) completed the Intrinsic Motivation Inventory...",
      "byte_start": 148,
      "byte_end": 427,
      "section": "body"
    },
    {
      "id": 3,
      "type": "paragraph",
      "text": "The omnibus ANOVA was significant, F(2, 37) = 6.801, p = .010, eta2 = .27.",
      "byte_start": 429,
      "byte_end": 503,
      "section": "results"
    },
    ...
  ],
  "metadata": { "engine": "pdftotext_default", "docpluck_version": "1.5.0", ... },
  "normalization": { ... },
  "quality": { ... }
}
```

**Opt-in:** the client requests chunks via `?chunks=true` (default `false` for backwards compatibility). Existing consumers see no change unless they ask.

### Chunk object schema

```typescript
type Chunk = {
  // Stable numeric identifier within this response. Consumers can reference
  // stats or citations by chunk_id + byte offset inside the chunk.
  id: number;

  // Coarse structural role. Consumers that only care about body paragraphs can
  // filter to `type: "paragraph"` and drop everything else.
  type:
    | "metadata_header"  // TYPE/PUBLISHED/DOI, journal running header, etc.
    | "heading"          // section titles ("Results", "Discussion", etc.)
    | "paragraph"        // regular body paragraph
    | "table_row"        // one row of a detected table, pipe-delimited
    | "table_caption"    // "Table 1: ..."
    | "figure_caption"   // "Figure 3: ..."
    | "list_item"        // numbered or bulleted list item
    | "footnote"         // detached footnote text
    | "reference"        // bibliography entry
    | "abstract"         // the abstract block
    | "author_block"     // author names + affiliations
    | "affiliation"      // standalone affiliation text
    | "unknown";         // everything else

  // The chunk's verbatim text. MUST match the corresponding byte range of the
  // flat `text` field exactly (so consumers can reconstruct the document
  // faithfully by concatenating chunks).
  text: string;

  // Byte offsets into the flat `text` field. Inclusive start, exclusive end.
  byte_start: number;
  byte_end: number;

  // Coarse logical section. Optional — empty string when unknown. Consumers
  // can use this to scope stat detection to `section: "results"` only.
  section?:
    | "header"
    | "title"
    | "abstract"
    | "introduction"
    | "methods"
    | "results"
    | "discussion"
    | "conclusion"
    | "references"
    | "supplement"
    | "body"  // generic body when section classifier is uncertain
    | "";

  // For headings only: level 1 = top, 2 = subsection, 3 = sub-subsection.
  heading_level?: number;

  // Optional pointer to the parent chunk (e.g., a figure caption pointing at
  // its containing section heading). Not required in v1.
  parent_id?: number;
};
```

### Stability guarantees (these are what make chunks useful)

1. **Byte offsets are exact.** `response.text.slice(chunk.byte_start, chunk.byte_end) === chunk.text` for every chunk. Consumers that already work with the flat text can use offsets to annotate or cross-reference without re-searching.
2. **Chunks partition the document or are explicit about gaps.** Either every byte of `text` belongs to exactly one chunk, or the response documents which gaps are intentional (e.g., inter-chunk whitespace).
3. **Stable ordering.** `chunks[0]` is always the first chunk, chunks are in reading order, `id` is monotonic.
4. **Stable boundaries across whitespace variation.** This is the load-bearing requirement: the same PDF run twice through Docpluck must produce the same chunks, and two PDFs with the same content but different whitespace formatting (e.g., one has `TYPE\nPUBLISHED\nDOI`, the other has `TYPE PUBLISHED DOI`) should produce **the same `metadata_header` chunk** with the same `text` content (modulo internal whitespace which is fine to differ).
5. **Type classification is best-effort, not authoritative.** A `paragraph` that could also be a `list_item` can ship as `paragraph`. Consumers should expect mild uncertainty. Unknown → `"unknown"`.
6. **Chunk `text` is normalized.** Same normalization level as the flat `text` field (respects `?normalize=standard|academic|none`).

### New request parameter

```
GET /api/extract?normalize=standard&chunks=true[&chunk_detail=basic|full]
```

- `chunks=true|false` (default `false`): include the `chunks` field in the response.
- `chunk_detail=basic|full` (default `basic`): `basic` returns the core fields above; `full` adds optional fields like `parent_id`, detected tables serialized as structured rows, and any extra metadata the type classifier produced.

---

## Why metadata_header specifically matters for the baseline failure

When ESCImate's `check_text()` iterates over `chunks.filter(c => c.section === "results" || c.section === "body")`, the Frontiers article header is excluded from stat detection entirely. No more chunk-boundary drift from metadata-header whitespace. The `r(24) = 0.195` stat gets found in its body chunk regardless of how many line breaks are between `TYPE` and `PUBLISHED` in the PDF.

This is a structural fix for a whole class of failure, not a workaround for one file.

---

## Implementation guidance (suggestions, not mandates)

The Docpluck team owns the implementation details. Some starting points:

### Detection strategy

**Heuristic chunker (v1, ship this):**
- Split on blank lines → candidate chunks
- Run type classifier on each candidate:
  - First 5 lines of document + runs of `TYPE/PUBLISHED/DOI/VOLUME/COPYRIGHT/LICENSE/RECEIVED/ACCEPTED/CITATION` → `metadata_header`
  - Short uppercase/title-case line at start of section boundary → `heading`
  - Line with ≥2 pipe characters `|` → `table_row`
  - Line starting with `Table N` or `Figure N` → caption
  - Line matching bibliography format → `reference`
  - Everything else → `paragraph`
- Merge consecutive `paragraph` chunks within a section
- Classify section by looking at last `heading` chunk above

**Advanced chunker (v2, follow-up):**
- Use font/layout information from pdfplumber (already in the dependency tree for SMP recovery)
- Train a simple classifier on heading/paragraph/caption distinctions

### Section classification

Start with a simple keyword lookup table:

```python
SECTION_KEYWORDS = {
    "introduction": ["introduction", "background"],
    "methods": ["method", "methods", "materials and methods", "participants", "procedure"],
    "results": ["result", "results", "findings"],
    "discussion": ["discussion", "general discussion"],
    "conclusion": ["conclusion", "conclusions"],
    "references": ["references", "bibliography", "works cited"],
}
```

When a `heading` chunk's lowercased text matches a keyword, subsequent chunks inherit that section until the next heading. Not perfect, but enough for ESCImate to filter to `section: "results"` for its stat detection.

### For DOCX and HTML

DOCX and HTML have richer structural information than PDF — don't throw it away:
- DOCX: mammoth already preserves heading levels, paragraph boundaries, and tables. Pass them through as chunk types directly.
- HTML: BeautifulSoup already tracks `<h1>`, `<p>`, `<table>`, `<section>`. Map those to chunk types directly.

This means chunking is *cheaper* on DOCX/HTML than on PDF — the structure is already there, just needs to be serialized into the `chunks` field.

### Testing

Request 6 (benchmark harness) already exists on the ESCImate side. After this request ships:

1. Docpluck exposes `chunks=true` on staging
2. ESCImate updates the harness to call with `chunks=true` and run a parallel check on the chunked output
3. ESCImate team prototypes a `check_text_from_chunks()` variant of `effectcheck` that iterates chunks directly (Path D territory — ESCImate-side refactor, not Docpluck's concern, but this is how the end-to-end test flow looks)

For the specific `frontiers_motivation_2024.pdf` failure, after this ships we expect:
- Docpluck returns ~12–15 chunks for the file
- `chunks[0]` is a `metadata_header` containing the `TYPE/PUBLISHED/DOI` lines
- ESCImate skips metadata_header chunks and starts stat detection from `section: "abstract"` or `section: "body"` onward
- All 9 stats are detected, all 9 have correct `df` values, C2 parity is 100%

---

## Backwards compatibility and deployment

- **No breaking changes.** `chunks=true` is opt-in. Existing consumers see identical responses to current Docpluck 1.4.0.
- **Cache key must include the chunks flag.** `extraction_cache.normalize_level` today encodes `standard:q=true:v=1.4.0`. Extend to `standard:q=true:c=true:v=1.5.0` when `chunks=true` is requested. Otherwise chunked-vs-unchunked responses collide in the cache.
- **Version bump.** Ship as Docpluck 1.5.0.
- **Documentation.** Update `docs/API.md` with the new parameter, response field, and chunk type vocabulary.
- **New lesson for LESSONS.md.** Record that ESCImate's chunker coupling was the motivation, so future consumers understand why this exists.

---

## Out of scope (explicit)

These are **not** Docpluck's job. They stay in ESCImate:

- **Stat detection** (regex patterns for `t(97) = 2.34, p < .001`). These encode statistical knowledge and belong in `effectcheck`.
- **Stat interpretation** (test type classification, one-tailed vs two-tailed, paired vs independent, design ambiguity).
- **Stat recomputation** (`pt()`, `pf()`, `pchisq()`, effect size formulas, CI construction).
- **Stat validation** (PASS / WARN / ERROR / NOTE / SKIP classification).

Docpluck's responsibility boundary is: `raw bytes → normalized flat text + structural chunks`. Stats are a downstream concern.

The ESCImate team is explicit that moves 2 and 3 from the architectural exploration (moving stat pattern detection or stat interpretation into Docpluck) are **NOT** wanted. Those stay in effectcheck. Request 8 is the only boundary move being requested. Everything else in `REQUESTS_FROM_ESCIMATE.md` remains as-is.

---

## Acceptance criteria

1. New `?chunks=true` parameter works on `/api/extract` for PDF, DOCX, and HTML
2. Response includes a `chunks` array matching the schema above
3. For every chunk, `response.text.slice(chunk.byte_start, chunk.byte_end) === chunk.text`
4. Running the same PDF twice produces identical chunks (determinism)
5. The `metadata_header` type correctly captures journal front-matter (TYPE/PUBLISHED/DOI, running headers, Frontiers-style metadata)
6. The `heading` type correctly identifies at least section-level headings (Introduction / Methods / Results / Discussion)
7. The `section` field correctly labels chunks under each of those standard headings
8. ESCImate's benchmark harness, re-run with `chunks=true` and a `check_text_from_chunks()` variant on the ESCImate side, produces 19/19 green on `escimate_validation`
9. `docs/API.md`, `CHANGELOG.md`, and `LESSONS.md` updated
10. Shipped as Docpluck 1.5.0 with a tagged GitHub release (Request 5.3 from the parent doc — release pinning discipline)

---

## Effort estimate

For the Docpluck team:
- **Core chunker (PDF heuristic)**: 2–3 days
- **DOCX / HTML pass-through chunking**: 0.5–1 day (structure is already there)
- **Section classifier**: 0.5 day (keyword table + heading walk)
- **API integration + tests**: 1 day
- **Cache key update + docs + release**: 0.5 day
- **Total**: ~1 week of Docpluck work

For the ESCImate team (parallel):
- **`check_text_from_chunks()` prototype**: 1 day
- **Harness update to exercise both paths**: 0.5 day
- **Regression test for frontiers_motivation**: 0.5 day
- **Total**: ~2 days of ESCImate work

---

## Open questions for the Docpluck team

1. **Chunk granularity knob** — do you want a `chunk_max_chars` parameter so consumers can request finer-grained chunks (e.g., sentence-level for translation use cases) vs coarser-grained (paragraph-level for stat detection)? Current proposal is fixed paragraph-level; ESCImate is fine with that but it might limit future flexibility.
2. **Caching policy** — should chunked responses invalidate the extraction cache if the chunker version bumps, or should they live under a compound key that includes chunker version? Probably the latter.
3. **Table rows** — for a multi-row table, do you emit one chunk per row (`type: "table_row"`) or one chunk per table with rows in the text (`type: "table"`)? ESCImate's use case wants per-row to avoid chunk-size blowup; Scimeto may want per-table for citation-in-caption matching. Suggest per-row as default with a future `chunk_tables=grouped|split` option.
4. **Do you want to own section classification at all?** If section classification feels too fragile or too domain-specific, ship chunks without `section` and let consumers do their own (simpler) section walk. Not a blocker either way.

Ping the ESCImate team on any of these. None are blocking for v1.

---

## Reference for the Docpluck team

When implementing, it may help to read ESCImate's current chunking logic to understand the downstream use case. See:

- `c:/Users/filin/Dropbox/Vibe/ESCIcheckapp/effectcheck/R/check.R` — the `check_text()` main function and its chunk iteration (very large file, ~4500 lines)
- `c:/Users/filin/Dropbox/Vibe/ESCIcheckapp/effectcheck/R/parse.R` — pattern detection within chunks
- `c:/Users/filin/Dropbox/Vibe/ESCIcheckapp/tests/outputs/docpluck_shootout/baseline/diag/` — diagnostic dumps of the two failing files with full text and stat tables

These are not prescriptive — the Docpluck chunker should be designed for general use, not to mirror ESCImate's internal chunking. But they show the downstream shape ESCImate wants to iterate over.

---

## Related requests

This is the 8th request in `REQUESTS_FROM_ESCIMATE.md`. Prior requests (1–7) are unchanged. Future requests beyond this one are deferred:

- **Request 1** (normalization ports) — still relevant, will be exercised by MetaESCI regression
- **Request 2** (DOCX engine verification) — still relevant
- **Request 3** (OCR research) — still relevant, still deferred
- **Request 4** (table extraction) — will interact with table_row chunking if you implement that
- **Request 5** (API contract) — docpluck_version is in place, Request 8 extends the API slightly
- **Request 6** (benchmark harness) — harness is built; will be re-run with chunks after 1.5.0
- **Request 7** (documentation) — 1.5.0 adds chunks docs

**No further architectural moves beyond Request 8 are planned.** The boundary between Docpluck (text + structure) and ESCImate (statistics) is where it stays. Request 8 closes the only place where the boundary was wrong.
