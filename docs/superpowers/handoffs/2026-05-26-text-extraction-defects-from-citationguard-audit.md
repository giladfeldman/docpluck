# Handoff — PDF text-extraction defects surfaced by the CitationGuard canary audit

**Date:** 2026-05-26
**From:** citationguard-iterate (citelink 0.7.0 canary-audit cycle)
**To:** docpluck-iterate (and any PDF text-extraction consumer)
**Priority:** P1 — these defects cap citation-parsing accuracy on ~⅓ of canary papers, and the ceiling is in the extraction layer, not the parser.

---

## TL;DR

CitationGuard's citelink library was audited against AI ground truth across 3 canary
papers (Sonnet-watches-Opus). Three fix cycles eliminated every citelink-domain defect
that was safely fixable. The audit then bottomed out on a wall of defects that are
**not citelink's to fix** — they are PDF **text-extraction** defects in the text the
parser is handed. Per the CitationGuard CLAUDE.md domain boundary ("PDF text-extraction
defects belong to docpluck-iterate"), they are filed here.

Three defect classes, all reproduced with exact evidence below:

1. **Soft-hyphen (U+00AD) preservation at line breaks** — the big one. 151 occurrences
   in one canary; broke **50 of 90 references** in `chan_feldman_2025_cogemo` because the
   reference-line splitter cannot segment lines containing soft-hyphens.
2. **Glyph / ligature mis-extraction** — the *same author surname* extracted correctly
   in one place and mangled in another (`Västfjäll` → `Vastfall`), position-dependent on
   the PDF's font encoding.
3. **Dropped reference lines** — a whole reference (`Munafò et al., 2017`) absent from the
   extracted text entirely (0 occurrences), so no downstream tool can ever recover it.

The fixtures audited are pymupdf extractions (`*_pymupdf.txt`). The fix belongs in the
text-extraction layer — whether that is docpluck (if CitationGuard migrates its worker to
docpluck) or a post-processing normalizer CitationGuard adds in front of citelink. This
handoff gives docpluck-iterate the evidence to (a) verify docpluck does NOT have these
defects, and (b) if it does, fix them at the source.

---

## Why this matters to docpluck specifically

docpluck is the portfolio's canonical PDF→text/markdown extractor, and the CitationGuard
domain boundary routes text-extraction defects here. Whatever extractor CitationGuard's
worker ultimately uses, **these three classes are exactly the kind of fidelity defects
docpluck's own canary audit (`reading` view vs AI gold) is designed to catch.** If
docpluck already dehyphenates and normalizes glyphs, this handoff is a confirmation
request + two regression fixtures. If it doesn't, this is a prioritized bug list with
reproduction.

---

## Defect 1 — Soft-hyphen (U+00AD) preserved at line breaks  ⚠️ HIGHEST IMPACT

### What it is

When a word is hyphenated across a line break in the source PDF, the extractor emits the
Unicode **SOFT HYPHEN U+00AD** (`­`) followed by the line break, instead of dehyphenating
(joining the two fragments into the whole word).

### Evidence

```
File: CitationGuard/apps/worker/tests/extraction-results/chan_feldman_2025_cogemo.pdf_pymupdf.txt
Count of U+00AD in the extraction: 151
Sample:  ") relation­\r\nship betw"          →  should be ") relationship betw"
```

Reference-list titles are riddled with it:
`com­ mitment`, `pro­ motion`, `altru­ ism`, `hind­ sight`, `con­ vincing`,
`for­ giveness`, `sol­ ution`, `psycho­ logical`, `sat­ isfaction`,
and in author names: `Banerjee & Du­\r\nflo, 2011`.

### Downstream damage (measured)

- **chan_feldman_2025_cogemo: only 40 of 90 references parse.** The reference-line
  splitter keys on line boundaries + author-comma-year patterns; a soft-hyphen mid-token
  defeats both. 50 references are simply lost.
- Because the references are lost, **95 of 138 in-text citations cannot be matched** to a
  reference (matching accuracy 0.31) — the citations are detected fine, but there is no
  reference-list entry to resolve them to.
- Every soft-hyphenated **title** mismatches the AI gold title (12 CITATION-PARSING
  findings in cycle-1, all "title-drift" caused purely by `­`).

This single defect is the dominant accuracy ceiling on chan_feldman — bigger than every
genuine citelink bug combined.

### The fix (extraction layer)

Standard PDF dehyphenation. On extraction, when a U+00AD (or a regular hyphen at a line
end that splits a single word) is immediately followed by a newline:

- **Join** the two fragments and **drop** the soft-hyphen: `relation­\nship` → `relationship`.
- Be conservative about genuine hyphenated compounds that legitimately break across lines
  (`self-­\ncompassion` → `self-compassion`, keep the real hyphen). The reliable signal:
  U+00AD is *always* a discretionary/extraction hyphen and can always be removed; a real
  `-` (U+002D) at a line end is ambiguous and needs the "is the rejoined token a known
  word / does the next fragment start lowercase" heuristic.
- At minimum, **strip all U+00AD characters unconditionally** — they are never meaningful
  in extracted plain text. That alone recovers most of the damage.

### Interim defense already in place

- The **gold-generation protocol** (`article-finder/gold-generation.md`) already requires
  normalizing U+00AD out of the `title_start` field (so AI gold is clean).
- **citelink could** strip U+00AD defensively in its reference-section preprocessor as a
  belt-and-suspenders measure — but that does NOT fix the lost references (the line
  *splitting* already failed upstream of any per-entry cleanup). The real fix is in
  extraction, before the text reaches citelink.

---

## Defect 2 — Glyph / ligature mis-extraction (position-dependent)

### What it is

The same character sequence is extracted correctly in one location and mangled in another,
depending on the font / encoding of that specific run of glyphs in the PDF.

### Evidence

```
File: CitationGuard/apps/worker/tests/extraction-results/collabra_90203.pdf_pymupdf.txt
"Västfjäll"  FOUND @ offset 19633:  "Västfjäll (2021) and"      ← correct
"Vastfall"   FOUND @ offset 95163:  "Vastfall et \r\nal. (2"     ← MANGLED (same author)
```

`Västfjäll` → `Vastfall`: the `ä` (U+00E4) collapses to `a` and the `fj` + `ä` middle is
lost. The author is the same person (Daniel Västfjäll), extracted faithfully on page ~2
and mangled on a later page. A similar class produced `Sjöström` → `sjastram` (an ö→a
mojibake) in chan_feldman, and `Positive–negative` → `Positiveâ€"negative` (en-dash
mojibake) in title text.

### Downstream damage

- citelink detects `Vastfall et al. (2014)` as a citation that has no matching reference
  (the reference list has the correct `Västfjäll`), so it is reported as a HALLUCINATION
  even though citelink did exactly the right thing with the text it was given.
- The mangled author key (`vastfall` vs `vastfjall`) breaks citation→reference matching.

### The fix (extraction layer)

- Diagnose why pymupdf mis-maps the glyph run at that offset — usually a CID font with a
  non-standard `ToUnicode` CMap, or a ligature glyph (`fj`, `ﬂ`, `ﬁ`) with no Unicode
  mapping. docpluck's extraction should already handle ligature normalization; this is a
  good regression fixture to confirm it does.
- If docpluck uses a different backend (pdfminer, mupdf, an OCR consensus), compare its
  output at this offset against the AI gold (`Västfjäll`) — the AI gold is the answer key.

---

## Defect 3 — Whole reference line dropped from extraction

### What it is

A reference present in the PDF is entirely absent from the extracted text.

### Evidence

```
File: CitationGuard/apps/worker/tests/extraction-results/chen_2021_jesp.pdf_pymupdf.txt
grep "Munafò" → 0 matches
grep "Munafo" → 0 matches
```

The AI gold (`ai_gold/10.1016__j.jesp.2021.104154/citations.json`) has the
`Munafò et al. (2017)` reference (it is reference #of the printed list and is cited in
text). The pymupdf extraction dropped the line entirely — so citelink's reference count is
100 vs the gold's 101, and the Munafò in-text citation can never be matched.

### The fix (extraction layer)

- Likely the same glyph/font root cause as Defect 2 (the `ò` in Munafò, or a column-flow
  / two-column ordering issue that skipped the line). Diagnose with the AI gold reading
  view as the answer key: the reading gold shows where Munafò should appear.
- This is the hardest of the three to fix blindly — it needs the extractor's per-page
  text-run debugging. docpluck's `reading`-view canary audit against the AI gold is the
  right harness to localize it.

---

## How to reproduce / verify on the docpluck side

1. The two source PDFs are in the portfolio:
   - `CitationGuard/apps/worker/testpdfs/validation/apa/chen_2021_jesp.pdf`
     (DOI `10.1016/j.jesp.2021.104154`)
   - `ESCIcheckapp/testpdfs/Maier-etal-2023-Collabra-Small-etal-2007-replication-extension-print-nosupp.pdf`
     (DOI `10.1525/collabra.90203`)
   A third, `chan_feldman_2025_cogemo.pdf` (DOI `10.1080/02699931.2024.2434156`), is the
   151-soft-hyphen case — find it via `article-finder` cache or the CitationGuard
   `testpdfs/validation/apa/` tree.

2. Run docpluck's extractor on each, then diff against the AI gold reading view:
   ```bash
   python ~/.claude/skills/article-finder/ai-gold.py get 10.1080/02699931.2024.2434156 --view reading
   ```
   Grep the docpluck output for U+00AD (`­`), for `Vastfall`, and for `Munafò`. A clean
   extractor has zero soft-hyphens, the correct `Västfjäll`, and a present `Munafò`.

3. If docpluck reproduces any of the three, they become docpluck-iterate canary findings
   (the `reading` view defect taxonomy already covers TEXT-LOSS and glyph fidelity). If
   docpluck is clean, the action item flips to **CitationGuard: migrate the worker's text
   extraction from pymupdf to docpluck** — file that back to citationguard-iterate.

---

## Recommended split of ownership

| Fix | Owner | Rationale |
|---|---|---|
| Soft-hyphen dehyphenation in extraction | docpluck-iterate (source fix) | The 50-reference loss is unrecoverable downstream; must be fixed before the text reaches any parser. |
| Defensive U+00AD strip in citelink ref preprocessor | citationguard-iterate (belt-and-suspenders) | Cheap; protects citelink even if it is ever fed a dirty extraction. Does NOT replace the source fix. |
| Glyph/ligature normalization | docpluck-iterate | Extraction-backend concern; docpluck's ligature handling is the right layer. |
| Dropped-line diagnosis (Munafò) | docpluck-iterate | Needs per-page text-run debugging only the extractor has. |
| Migrate CitationGuard worker extraction → docpluck (if docpluck is clean) | citationguard-iterate | Removes the pymupdf defects from CitationGuard's production path. |

---

## What was already fixed on the citelink side (so you know the boundary)

citelink 0.7.0 fixed, in three audited cycles: sentence-adverb author hallucinations,
running-page-footer + download-watermark absorption, same-(author,year) matcher rejection,
and same-author multi-year parenthetical detection. Those were genuinely citelink's. The
defects in THIS handoff are the residue that no parser fix can touch — they are upstream of
the parser, in the bytes the parser is handed. See
`CitationGuard/docs/superpowers/handoffs/2026-05-26-canary-audit-steps-1-2-landed.md` for
the full citelink cycle log.

---

## Cross-references

- citelink audit log + ledger: `CitationGuard/docs/superpowers/handoffs/2026-05-26-canary-audit-steps-1-2-landed.md`
- Verdict ledger (per-paper, per-cycle): `CitationGuard/tmp/iterate/cycle-canary-smoke/`
- AI gold (answer keys): `ArticleRepository/ai_gold/{10.1016__j.jesp.2021.104154, 10.1080__02699931.2024.2434156, 10.1525__collabra.90203}/`
- Domain boundary rule: `CitationGuard/CLAUDE.md` → "Address-on-discovery" + the docpluck-vs-citationguard split.

---

## docpluck-iterate RESPONSE (2026-06-06) — verified against docpluck (NOT pymupdf)

All three defects were reproduced/verified against **docpluck's own extractor** (pdftotext + pdfplumber; docpluck never uses pymupdf — AGPL-forbidden, LESSONS L-003) by rendering the three papers via `tools/render_for_audit.py` (located through article-finder per the paper-locating rule).

| Defect | docpluck verdict | Action taken |
|---|---|---|
| 1. Soft-hyphen U+00AD | **PARTIALLY reproduced** — docpluck's S6 already stripped bare U+00AD (0 in output, references NOT lost, unlike pymupdf's 50/90 loss), but the bare strip left `relation\nship` which reflowed to the space-broken `relation ship` on ~6 words in chan_feldman. | **FIXED in v2.4.78** — `normalize.py` S6 now joins the fragments (drops U+00AD + newline, gated on a following letter) BEFORE the bare strip. chan_feldman: U+00AD=0, all 6 space-broken residuals recovered (`commitment`, `promotion`, `relationship`, …). Regression test `tests/test_normalize_soft_hyphen_dehyphenation.py`. |
| 2. Glyph mis-map (`Västfjäll`→`Vastfall`) | **REPRODUCED** — 9× correct `Västfjäll`, 1× `Vastfall` in collabra (raw pdftotext CID-font/ToUnicode mis-map at one offset, survives into .md). No `sjastram`/mojibake in docpluck (those were pymupdf-specific). | **DEFERRED — needs architecture decision.** No safe one-line fix (`Vastfall` is a plausible token; a `Vastfall`→`Västfjäll` string map would violate the no-PDF-specific-fix rule). Proper general fix = a same-document surname-consensus normalizer (majority spelling wins for near-miss rare-surname variants) — a new subsystem with regression risk. Surfaced for a product/scope decision. |
| 3. Dropped reference line (`Munafò`) | **CLEAN** — docpluck output contains both the in-text citation and the reference-list entry for `Munafò et al. (2017)`. pymupdf-only bug. | **No docpluck fix needed.** This is the strongest argument for CitationGuard migrating its worker's text extraction from pymupdf to docpluck — the dropped-line class disappears for free. |

**Net for CitationGuard:** migrating the worker to docpluck would (a) eliminate Defect 3 outright, and (b) neutralize the severe part of Defect 1 (docpluck never loses the references, and v2.4.78 also recovers the space-broken-word residual). Defect 2's glyph mis-map is a shared pdftotext-layer concern that docpluck owns but has deferred pending a consensus-normalizer decision. Recommend filing the migration as a citationguard-iterate item.
