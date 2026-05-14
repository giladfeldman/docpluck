# Full-document AI verification (no-hallucination / no-text-loss gate)

> Loaded on demand from SKILL.md Phase 5d. Mandatory; never skipped.

This is the keystone meta-science gate. Char-ratio + Jaccard verifiers are blind to "right words in wrong order under wrong heading"; a 30-line eyeball is blind to mid-document drift; only a full-document structured comparison against the PDF itself catches the two failure modes that make this library scientifically unusable:

- **Text disappearing.** A real paragraph from the PDF is missing from the rendered output. This is the biggest nono — it silently corrupts downstream meta-science.
- **Hallucinated text.** The rendered output contains a sentence, citation, or value that does not appear in the source PDF. Equally fatal.

Plus structural correctness: sections at the right boundaries, tables with the right cells, figure captions paired to the right figures, footnotes preserved, no front-matter / running-header / acknowledgment leaks mid-body.

---

## Ground truth = AI multimodal read of the PDF, NOT pdftotext (CLAUDE.md hard rule)

The PDF is the only authoritative source. Every deterministic extractor we use (pdftotext, Camelot, pdfplumber) has flaws that we have already flagged — see memory `feedback_pdfplumber_extract_words_unreliable`, `feedback_pdftotext_version_skew`, and the recurring Camelot phantom-empty-column class of bugs. Comparing the library's rendered `.md` against pdftotext output can mask any bug pdftotext itself produces (e.g. Greek glyphs dropped on tight-kerned PDFs, columns interleaved, tables/images invisible). Those are exactly the bug class the library exists to fix.

**The verification procedure is therefore:**
1. AI subagent reads the source PDF directly (via `Read` with `pages=N-M`) and produces a structured "gold extraction" in `tmp/<paper>_gold.md`. The gold is what a careful human reader would write down given the PDF in front of them.
2. A second subagent compares the library's rendered `.md` against this AI gold across the 6 standard checks.
3. pdftotext / Camelot / pdfplumber output remain useful as **diagnostic** artifacts — when the gold says "β present in body" and the rendered .md says "beta" and pdftotext output also says "beta", that pinpoints pdftotext as the layer at fault (an upstream issue) vs the library's normalize layer. But the verdict (PASS/FAIL) is judged against AI gold ONLY.

Memory `feedback_ground_truth_is_ai_not_pdftotext` (2026-05-14, established after the user pointed out for the Nth time that we had been silently sliding back to pdftotext-as-truth).

---

## The protocol (every affected paper, every cycle, no exceptions)

For each paper the cycle's fix targets (typically 3–8 papers):

### Step 1 — Produce / refresh the AI gold extraction

The gold extraction is the source of truth for ALL future verification of this paper. It is generated once by an AI subagent reading the PDF and is reused across cycles (PDFs are immutable). **The gold is stored long-term in the shared article repository** (`~/ArticleRepository/ai_gold/<key>.md`) via the `article-finder` skill's `ai-gold.py` utility — every project that needs the gold for this paper can read it without re-running the AI extraction.

**Long-term gold caching (MANDATORY, added 2026-05-14):**

```bash
# 1. Check the shared repository FIRST. ~/.claude/skills/article-finder/ai-gold.py
#    handles DOI / .pdf-path / stem keys uniformly.
AI_GOLD_SCRIPT="~/.claude/skills/article-finder/ai-gold.py"

if cached=$(python "$AI_GOLD_SCRIPT" check "$KEY"); then
    # Cache HIT — copy to tmp/<paper>_gold.md and skip subagent dispatch.
    cp "$cached" "tmp/<paper>_gold.md"
    # (Or symlink, on platforms that support it.)
else
    # Cache MISS — dispatch the gold-extraction subagent (Step 1b below).
    # After the subagent writes tmp/<paper>_gold.md, STORE it back to the
    # shared repository so the next consumer (this or another project) reuses it.
    # See Step 1c below.
    :
fi
```

Where `$KEY` is one of:
- DOI in normalized form (e.g. `10.1080/23743603.2021.1878340`) — preferred when the paper has a DOI indexed in the article repository.
- Filename stem (e.g. `xiao_2021_crsp`) — for local fixture PDFs that don't have a DOI in the repo (the typical case for `PDFextractor/test-pdfs/<publisher>/<stem>.pdf`).
- Absolute path to the PDF (the script derives the stem from the filename).

The repository layout is described in `~/.claude/skills/article-finder/SKILL.md`. The new directory `ArticleRepository/ai_gold/` is dedicated to AI-multimodal ground truths (distinct from `ground_truth/` which holds deterministic-text ground truths from publisher HTML / PMC XML / OCR consensus).

### Step 1b — Dispatch gold-extraction subagent (only on cache miss)

**Gold-extraction subagent prompt template** (use `Agent` tool with `general-purpose`):

```
You are producing the canonical ground-truth extraction of a single academic PDF
for a meta-science library's verification pipeline. The PDF is the only
authoritative source. Read it as a careful human reader would.

INPUT:
  - <absolute path to PDF>

ACTION:
  Use the Read tool with pages=N-M to read the PDF directly. For papers longer
  than 20 pages, read in ≤20-page chunks and concatenate. Do NOT use pdftotext,
  Camelot, pdfplumber, or any deterministic extractor — they all have flaws
  this audit is meant to expose.

OUTPUT FORMAT (write to tmp/<paper>_gold.md, encoding='utf-8'):

# <Title exactly as printed>

**Authors:** <author 1> (<affiliation>), <author 2> (<affiliation>), ...
**Journal / venue / year:** <as printed>
**DOI:** <if printed>

## Abstract
<full abstract text, preserving Greek letters, math symbols, en-dashes,
 minus signs (U+2212), thousands separators in numbers, and superscripts>

## Keywords
<comma-separated list as printed>

## <Section 1 heading exactly as printed, preserving case>
<full body prose, paragraph by paragraph. Preserve everything: Greek letters
 (β, δ, γ, σ, μ, τ, ε, ω, π), comparison operators (≥, ≤, ×, ·, ±), thousands
 separators (1,675 not 1675), superscripts (²), em-dashes vs en-dashes vs
 hyphens vs minus signs. Footnote markers stay inline as superscripts.>

### <Subsection heading if present>
<...>

[continue for every section, subsection, sub-subsection in the order they
 appear in the PDF]

## Tables

### Table 1: <caption exactly as printed>
**Source page:** <page number>
**Structure:** <N columns × M rows; describe header hierarchy if multi-level>
**Cells (visual reading, row by row, comma-separated within row):**
- Header row: col1, col2, col3, ...
- Row 1: cell1, cell2, cell3, ...
- Row 2: cell1, cell2, cell3, ...
[...]
**Footnotes attached to table:** <if any>

### Table 2: ...
[...]

## Figures

### Figure 1: <caption exactly as printed>
**Source page:** <page number>
**Type:** <chart / diagram / photograph / flowchart / etc.>
**Content described:** <one paragraph describing what the figure shows — axes
 if a plot, nodes+edges if a diagram, etc. Do NOT transcribe legend/axis
 text as if it were caption prose — describe it instead.>

### Figure 2: ...
[...]

## Footnotes
1. <footnote 1 text as printed>
2. <footnote 2 text>
[...]

## Acknowledgments
<text as printed>

## Funding
<text as printed>

## References
1. <ref 1, formatted as printed>
2. <ref 2, formatted as printed>
[...]

## Appendices
### Appendix A: <title>
<full appendix content>

## Author biographies
<one paragraph per author, as printed>

---

DISCIPLINE:
- Preserve all Greek letters, math symbols, comparison operators, dashes,
  minus signs, and thousands separators exactly as they appear in the PDF.
- Do NOT transliterate (β stays β; do NOT write "beta").
- Do NOT strip commas from integers (1,675 stays 1,675).
- Do NOT collapse U+2212 to ASCII hyphen, do NOT collapse U+2013/2014 either.
  The gold preserves the source glyphs; downstream library normalization can
  legitimately ASCIIfy them (that is the library's job), but the gold has to
  hold the truth against which to judge.
- Read every page in full. Do not skim. If the PDF is too long for one Read
  call (>20 pages), make multiple Read calls with pages=1-20, pages=21-40, ...
  and concatenate.
- If a section, table, or figure is missing from the PDF (e.g., no Acknowledgments
  section exists), OMIT the heading from the gold rather than emit an empty one.

Return when tmp/<paper>_gold.md is written. The file is the contract — it must
be parseable as Markdown and faithful to the PDF.
```

Save the resulting gold as `tmp/<paper>_gold.md`.

### Step 1c — Store the new gold back to the shared repository (MANDATORY after a cache miss)

```bash
# Persist the freshly-generated gold to long-term storage so future
# consumers (this project's next cycle, OR ANY OTHER PROJECT) reuse it
# without re-running the AI extraction. PDFs are immutable; golds are
# durable artifacts that can be cached forever.
python ~/.claude/skills/article-finder/ai-gold.py store \
    "<KEY>" \
    "tmp/<paper>_gold.md" \
    --source-pdf "<absolute path to source PDF>" \
    --version v1 \
    --by "docpluck-iterate@<session-id-or-date>" \
    --note "Phase 5d gold extraction for cycle <N>"
```

This step is MANDATORY whenever Step 1b ran (i.e., whenever the cache missed and a new gold was generated). Skipping it means the next cycle re-pays the ~3-15min subagent cost for the same paper. The repository is the durable artifact; `tmp/<paper>_gold.md` is the working copy.

**Invalidation:** the meta JSON records the source PDF SHA256. If a future consumer detects the PDF on disk has a different hash than what's recorded, they can either accept the cache (if they trust the paper hasn't fundamentally changed) or re-extract. PDFs in our test corpus are immutable, so this is rare.

### Step 2 — Capture the library's rendered output

```bash
python -u -c "
from pathlib import Path
from docpluck.render import render_pdf_to_markdown
md = render_pdf_to_markdown(Path('<pdf>').read_bytes())
Path('tmp/<paper>_v<version>.md').write_text(md, encoding='utf-8')
" 2>&1 | awk '{print; fflush()}'
```

### Step 3 — Capture diagnostic artifacts (optional, used only when gold ↔ rendered.md disagree)

These are NOT ground truth. They are diagnostics — they help pinpoint which library layer caused a finding once the gold ↔ rendered.md comparison has already identified the finding.

```bash
# DIAGNOSTIC ONLY — not ground truth
pdftotext -enc UTF-8 <pdf> tmp/<paper>_pdftotext.txt
python -u -c "
import json
from pathlib import Path
from docpluck.extract_structured import extract_pdf_structured
r = extract_pdf_structured(Path('<pdf>').read_bytes())
Path('tmp/<paper>_structured.json').write_text(json.dumps(r, indent=2, default=str), encoding='utf-8')
"
```

### Step 4 — Dispatch the verifier subagent (compares rendered.md against AI gold)

Use the `Agent` tool with `general-purpose`. Prompt template:

```
You are auditing the docpluck library's PDF→Markdown rendering for a meta-science
project that demands zero text loss and zero hallucinations.

GROUND TRUTH: tmp/<paper>_gold.md — an AI multimodal extraction of the source
              PDF, produced by reading the PDF directly. This is what a careful
              human reader would write down. It preserves Greek letters,
              comparison operators, thousands separators, and dashes exactly
              as the PDF prints them.
RENDERED:    tmp/<paper>_v<version>.md — the library's output (what is being
              audited).
DIAGNOSTIC (optional, do NOT use as truth):
             tmp/<paper>_pdftotext.txt — pdftotext output (the library's
             TEXT-channel input).
             tmp/<paper>_structured.json — Camelot/pdfplumber LAYOUT-channel
             extraction (the library's table/figure input).
             Use these ONLY after you have already identified a finding via
             gold ↔ rendered comparison, to pinpoint which library layer is
             responsible (e.g. "rendered says 'beta', gold says 'β', pdftotext
             also says 'beta' → bug is in pdftotext upstream, not in
             normalize.py").

YOUR JOB: read BOTH gold and rendered.md IN FULL. Then produce a structured
verdict. Be conservative — when in doubt, flag it.

CHECKS (in order; each must pass):

1. TEXT-LOSS check.
   For every substantive paragraph in the gold (sentence-shaped, ≥60 chars),
   verify the same paragraph appears in the rendered .md. Allowed normalizations
   the library may apply: U+2212→hyphen, soft-hyphen rejoin, line-wrap reflow,
   NFKC composition, smart-quote→straight-quote. Allowed omissions ONLY:
   running headers (e.g. "Q. XIAO ET AL."), page numbers, copyright lines,
   Crossref boilerplate, watermark strips, ORCID lines, DOI banner lines.
   Anything else missing is a TEXT-LOSS finding.

2. HALLUCINATION check.
   For every substantive paragraph in the rendered .md (≥60 chars,
   sentence-shaped), verify the same content appears in the gold. Structured
   wrappers added by the renderer (`### Table N`, italic captions, fenced
   `unstructured-table` blocks, `## ` heading markers) are renderer markup,
   NOT hallucination. Sentences / numbers / claims not traceable to the gold
   are HALLUCINATIONs. Glyph hallucinations count: if the gold has β and the
   rendered .md has "beta", and the user did not authorize Greek→ASCII
   transliteration as a documented normalization (S5 covers only U+2212→hyphen
   per CLAUDE.md), then "beta" is hallucinated character content.

3. SECTION-BOUNDARY check.
   List every `## ` heading in the rendered .md. For each: does the heading
   appear at a plausible boundary as defined by the gold's section structure?
   Specifically flag:
     - heading appears mid-paragraph (boundary too early/late by ≥1 paragraph)
     - section content belongs under a different canonical name
     - sections that exist in the gold but don't appear in the rendered .md
       (e.g. gold has `## Study 1: Replication of …` but rendered has it as
       flat body text)
     - hallucinated headings that don't appear in the gold (e.g. rendered has
       `## Introduction` but the gold has no such heading and the section
       directly follows ## Keywords with body prose)
     - endmatter routing errors: gold says ## Appendix A contains items 1-4,
       rendered places items 3-4 inside ## References

4. TABLE check (for each `### Table N` heading in the rendered .md).
   Compare against the gold's `### Table N` block:
     - Caption matches the gold's caption text.
     - Cell content matches the gold's cell-by-cell reading. Specifically flag:
       * phantom empty columns (rendered has 7 columns where gold has 6,
         with an empty `<th></th>` inserted)
       * concatenated cells (rendered has `<td>Michigan State6Harvard
         University</td>` where gold has separate cells "Michigan State",
         "6", "Harvard University")
       * caption text welded into thead (rendered has `<th>TABLE N<br>Caption
         text</th>` instead of a `<caption>` element)
       * missing rows (gold has rows for DF / R² / ΔR² that rendered drops)
       * empty `<table>` (rendered has the `<table>` shell but cell content
         was dumped to body stream instead — gold has full structured table)
     - No body prose absorbed (boundary bleed).
     - No two tables merged into one.

5. FIGURE check (for each `### Figure N` heading).
   Compare against the gold's `### Figure N` block:
     - Caption matches the gold.
     - Caption not truncated mid-sentence (flag if rendered caption is
       suspiciously shorter than gold).
     - Caption paired to the right figure (no off-by-one).
     - Flag double-emission (same caption appearing twice in rendered .md
       with different normalization in each).

6. METADATA-LEAK check.
   The body of any section should NOT contain orphan metadata: affiliations
   ("Department of Psychology, University of <truncated>"), corresponding-
   author contact lines, supplemental-data notices, acknowledgments outside
   the Acknowledgments section, funding statements outside Funding section,
   journal running headers ("RECKELL et al.", "Q. XIAO ET AL."), running-
   header text wedged inside `<table>` or fenced unstructured blocks. Each
   such occurrence is a METADATA-LEAK finding.

OUTPUT FORMAT (markdown):

## Verdict: PASS / FAIL

## Findings (severity-ordered)

### TEXT-LOSS (critical — blocks ship)
- <gold paragraph excerpt> · gold §<section> · NOT FOUND in rendered

### HALLUCINATION (critical — blocks ship)
- <rendered sentence> · NOT TRACEABLE to gold

### SECTION-BOUNDARY (high)
- "## Introduction" at rendered .md line 22 — NOT IN GOLD (gold goes directly
  from `## Keywords` to body prose without an Introduction heading)

### TABLE / FIGURE / METADATA-LEAK (medium)
- ...

## Confirmed matches (one line each — proves you actually read both files)
- Abstract paragraph 1 (gold: 270 words; rendered: 270 words minus
  smart-quote→straight) — present, matches
- Section ## Methods — gold and rendered agree on boundary at paragraph N
- Table 1 — gold: 6 cols × 14 rows; rendered: 6 cols × 14 rows, all cells
  match
- ... etc

Be specific. Quote excerpts. Cite paragraph/line references in BOTH files.
A vague "section boundaries look OK" is NOT acceptable — list every ##
heading in BOTH files and rule on each.
```

### Step 5 — Adjudicate

- **All checks PASS** → record `5d: AI-verified <paper> against gold` in cycle report. Proceed.
- **Any TEXT-LOSS or HALLUCINATION finding** → revert the cycle's library edit (if newly introduced) AND queue a new cycle to fix the root cause (if pre-existing). These are uncategorical-blockers. Append a LEARNINGS entry explaining what slipped through Phase 5a–c. Do NOT try to patch the renderer around the AI's complaint — root-cause it in the layer of origin (use the diagnostic artifacts to pinpoint the layer).
- **SECTION-BOUNDARY or TABLE / FIGURE / METADATA-LEAK finding** → if newly introduced this cycle → revert. If pre-existing → DO NOT ship around it: **queue an immediate-subsequent cycle in the same run to fix it** (rule 0e in CLAUDE.md).

**Pre-existing ≠ deferrable.** A finding that existed in the prior release and was missed by an earlier cycle's verification is even MORE reason to fix it now — that earlier verification missed a real defect, and the defect has been silently corrupting outputs for users in the interim.

**Critical rule:** do not negotiate with TEXT-LOSS or HALLUCINATION findings. A meta-science user pulling data from this library cannot be told "we silently dropped one paragraph" or "we silently transliterated half the Greek letters but left the others."

### Step 6 — Cross-paper sweep (every 3rd cycle)

The single-paper AI verify catches cycle-specific regressions. But systematic patterns (e.g. "phantom-column emission now affects 15 papers, was 4") need a corpus-wide view.

Every 3rd cycle, dispatch ONE subagent given the rendered .md files + gold files for 5 randomly-sampled papers, asking for a corpus-level findings list: which categories of finding appear in how many papers; rank by paper-count. This drives TRIAGE update for the next cycle.

---

## What NOT to do

| Anti-pattern | Why it's wrong |
|--------------|----------------|
| "Use pdftotext output as source of truth" | Pdftotext has its own flaws (Greek glyphs dropped on tight-kerned PDFs, column interleave, tables invisible). Comparing rendered.md against pdftotext masks bugs pdftotext itself produces. Memory `feedback_ground_truth_is_ai_not_pdftotext`. |
| "Use Camelot's structured output as table truth" | Camelot phantom-emits empty columns and fuses adjacent cells — exactly the bug class we're trying to catch. Cell truth comes from the visual PDF via AI gold extraction. |
| "Read first 30 lines of rendered.md" | Mid-document drift only shows mid-document. 30-line skim is the BASELINE before AI verify, not a substitute. |
| "Trust char-ratio + Jaccard" | Both blind to "right words wrong order under wrong heading." |
| "Eyeball is enough, skip the subagent" | Eyeball misses systematic issues across multiple papers. |
| "Subagent costs tokens — skip on small fixes" | A "small fix" that silently drops one paragraph is a catastrophic meta-science failure. Token cost is irrelevant against scientific correctness. |
| "26-paper baseline passed, so it's fine" | Baseline checks structure metrics, not content correctness. AI verify against gold is the content gate. |
| "Render output looks OK to me, the AI is being paranoid" | The AI verifier is calibrated to be conservative. Side with the verifier. |

## How this composes with other phases

- **Phase 5a–c (unit tests + baseline)** check that the LIBRARY CODE works as intended on its own terms.
- **Phase 5d (this protocol)** checks that the OUTPUT IS CORRECT against the source PDF (via AI gold).
- Both are required. Neither substitutes for the other.

## Cost management

- Gold extraction: ~1 subagent call per paper, ~2-4 minutes for a 20-page paper. **Generated once, reused forever** (PDFs are immutable).
- Verification: ~1 subagent call per paper per cycle, ~1-2 minutes.
- Cycle-1 canonical corpus (xiao, amj_1, amle_1, ieee_access_2): generate the 4 gold files once, then per cycle pay only ~4-8 minutes of verification.
- Per 3rd-cycle corpus sweep: + ~3-4 min for one subagent given 5 paper gold+rendered pairs.

Total: ~10 minutes per cycle steady-state. Worth every minute against the alternative (shipping a regression).

## Gold-extraction failure modes + workarounds (lessons from 2026-05-14 cycle-15 run)

These are real failure modes observed when the canonical 4-paper corpus was gold-extracted for the first time. Bake them into the prompt template for future runs.

### Failure mode: "image dimension exceeds limit for many-image requests"

Symptom: a subagent reading a PDF via `Read(file_path=..., pages="1-20")` accumulates 20 page-images per call. If any page is high-DPI or large-format (tabloid, A3, landscape figure pages), the per-image dimension can exceed 2000px, OR the cumulative many-image budget gets hit. The subagent fails partway through with "An image in the conversation exceeds the dimension limit for many-image requests (2000px). Start a new session with fewer images."

Real incident: xiao_2021_crsp (36 pages, APA-format) failed after 53 tool calls on the first try.

**Workaround 1 (PREFERRED):** explicitly constrain the gold-extraction prompt to use a SMALL FIXED NUMBER of Read calls with bounded chunk size. For a 36-page paper: "Use EXACTLY THREE Read calls with `pages='1-12'`, `pages='13-24'`, `pages='25-36'`." For larger papers, 12-page chunks are a safe ceiling. After each chunk, write a partial gold to disk and DO NOT re-read pages.

**Workaround 2 (FALLBACK):** if the Read tool's PDF-rendering binary (`pdftoppm`) is unavailable on the host (as observed on this Windows machine for the amle_1 extraction), the subagent can render PDF pages to PNG via `pypdfium2` (a separate library — `pip install pypdfium2`) and then read the PNGs visually. This is **epistemically equivalent** to the Read tool's PDF path (both produce AI-multimodal reads of the visual rendering of the page), just using a different rendering binary. Note this in the gold's preamble: "Pages rendered via pypdfium2; read visually."

**Workaround 3 (LAST RESORT):** split the PDF into halves and dispatch two separate subagents, each producing a partial gold (`tmp/<paper>_gold_part1.md`, `tmp/<paper>_gold_part2.md`), then have the orchestrator concatenate. Use only when workarounds 1 and 2 fail.

### Failure mode: subagent burns tool-call budget on per-page Read calls

Symptom: subagent uses 50+ tool calls to read a 30-page paper. Indicates per-page Read loops. Even if it doesn't hit the image limit, it's slow and wasteful.

Fix: prompt MUST specify the exact number of chunks and their page ranges, AND say explicitly "do not re-read the same page twice." A correctly-chunked extraction takes 5-15 tool calls regardless of paper length.

### Failure mode: gold "cleans up" the source

Symptom: gold transliterates β→"beta", strips commas from 7,445→7445, or otherwise normalizes the source. This DEFEATS the purpose — the gold becomes useless for catching library normalization bugs because it has the same bug.

Fix: prompt MUST emphasize "preserve glyphs EXACTLY as printed; never transliterate; never strip commas; never collapse U+2212 to ASCII hyphen." The gold's job is fidelity to the PDF, not readability.

### Subagent dispatch cadence

- **Parallel by paper** (Pattern A from SKILL.md): dispatch one subagent per paper, all in background, all in the same message with multiple Agent tool calls. 4 papers in parallel ≈ wall-clock time of the slowest, not the sum.
- **Sequential by chunk within a paper**: within a single paper's gold extraction, chunks must be sequential (subagent reads chunk 1, writes partial gold, reads chunk 2, etc.). Do NOT dispatch 3 subagents to extract pages 1-12 / 13-24 / 25-36 in parallel — they'd each need to read the structure of the paper independently and produce inconsistent partial golds.

---

## Gold extraction lifetime + invalidation

- Gold extractions are cached at `tmp/<paper>_gold.md` and `tmp/<paper>_gold.json` (machine-readable companion).
- Invalidate ONLY when: (a) a new paper is added to the canonical corpus, (b) a prior gold extraction is found to be inaccurate (rare — note the inaccuracy and re-extract), (c) the gold-extraction prompt template materially changes.
- Library version bumps do NOT invalidate the gold (the gold is about the PDF, not the library).
- The gold is the durable artifact; the rendered .md changes every cycle.
