# Full-document AI verification (no-hallucination / no-text-loss gate)

> Loaded on demand from SKILL.md Phase 5d. Mandatory; never skipped.

This is the keystone meta-science gate. Char-ratio + Jaccard verifiers are blind to "right words in wrong order under wrong heading"; a 30-line eyeball is blind to mid-document drift; only a full-document structured read against the source PDF catches the two failure modes that make this library scientifically unusable:

- **Text disappearing.** A real paragraph from the PDF is missing from the rendered output. This is the biggest nono — it silently corrupts downstream meta-science.
- **Hallucinated text.** The rendered output contains a sentence, citation, or value that does not appear in the source PDF. Equally fatal.

Plus structural correctness: sections at the right boundaries, tables with the right cells, figure captions paired to the right figures, footnotes preserved, no front-matter / running-header / acknowledgment leaks mid-body.

## The protocol (every affected paper, every cycle, no exceptions)

For each paper the cycle's fix targets (typically 3–8 papers):

### Step 1 — Capture two artifacts

```bash
# 1a. Source-of-truth: pdftotext output (the library's text channel)
pdftotext -enc UTF-8 <pdf> /tmp/<paper>.txt

# 1b. Library output: the rendered .md (the cycle's product)
python -c "
from pathlib import Path
from docpluck.render import render_pdf_to_markdown
md = render_pdf_to_markdown(Path('<pdf>').read_bytes())
Path('tmp/<paper>_v<version>.md').write_text(md, encoding='utf-8')
"
```

(The reason we use `pdftotext` output as the source-of-truth, not the PDF itself, is that pdftotext is the library's text channel. If the PDF has content that pdftotext doesn't extract, that's not a library bug — it's an upstream PDF/pdftotext limitation. The verification is "did the library faithfully process what pdftotext gave it?")

### Step 2 — Dispatch the verifier subagent

Use the `Agent` tool with `general-purpose` subagent. Hand it BOTH artifacts and ask for a structured verdict. Prompt template:

```
You are auditing the docpluck library's PDF→Markdown rendering for a meta-science
project that demands zero text loss and zero hallucinations.

INPUTS:
  - /tmp/<paper>.txt — the pdftotext output (source of truth for what text exists)
  - tmp/<paper>_v<version>.md — docpluck's rendered output (what the library produced)

YOUR JOB: read BOTH files in full (not the first N lines — the entire documents).
Then produce a structured verdict. Be conservative — when in doubt, flag it.

CHECKS (in order; each must pass):

1. TEXT-LOSS check.
   For every substantive paragraph in the pdftotext output (>= 60 chars,
   sentence-shaped), verify the same paragraph appears in the rendered .md
   (allowing for normalization: U+2212→hyphen, soft-hyphen rejoin, line-wrap
   reflow, NFKC). Allowed omissions ONLY: running headers (e.g. "C. F. CHAN
   AND G. FELDMAN"), page numbers (standalone 1-4 digits), copyright lines
   ("© 2021 European Association of..."), Crossref boilerplate, watermark
   strips, ORCID lines, and explicit DOI banner lines. Anything else missing
   is a TEXT-LOSS finding.

2. HALLUCINATION check.
   For every substantive paragraph in the rendered .md (>= 60 chars,
   sentence-shaped), verify the same content appears in the pdftotext output.
   Anything in the .md that doesn't trace back to the source is a HALLUCINATION
   finding. Note: structured wrapping ("### Table 1", italic captions, fenced
   unstructured-table blocks) is renderer-added markup, NOT hallucination.

3. SECTION-BOUNDARY check.
   List every `## ` heading in the .md (these are top-level sections).
   For each: does the heading appear at a plausible boundary in the source
   (i.e. the content immediately following matches what a human reader would
   put under that heading in the source)? Specifically flag:
     - heading appears mid-paragraph (boundary too early/late by a paragraph)
     - section content belongs under a different canonical name
     - sections that should exist but don't (Methods missing despite "we
       recruited 200 participants..." prose)

4. TABLE check (if any `### Table N` headings exist).
   For each: (a) caption matches the source; (b) cell content is present
   either as <table> HTML or as fenced unstructured-table block; (c) no
   table absorbed adjacent body prose (boundary bleed); (d) no two tables
   merged into one.

5. FIGURE check (if any `### Figure N` headings exist).
   Each figure has a caption that matches the source. Captions are not
   truncated mid-sentence. Captions are not paired with the wrong figure.

6. METADATA-LEAK check.
   The body of any section should NOT contain orphan metadata: affiliations
   ("Department of Psychology, University of <truncated>"), corresponding
   author contact lines ("CONTACT: ..."), supplemental-data notices
   ("Supplemental data for this article can be accessed here."),
   acknowledgments ("We thank ...", "We wish to thank our editor ..."),
   funding statements that aren't in a Funding section, journal running
   headers ("RECKELL et al.", "Q. XIAO ET AL."). Each such occurrence is
   a METADATA-LEAK finding.

OUTPUT FORMAT (markdown):

## Verdict: PASS / FAIL

## Findings (severity-ordered)

### TEXT-LOSS (critical — blocks ship)
- <paragraph excerpt from source> · approx line N · NOT FOUND in rendered

### HALLUCINATION (critical — blocks ship)
- <sentence from rendered> · NOT TRACEABLE to source

### SECTION-BOUNDARY (high — usually blocks ship)
- "## Introduction" at .md line 22 should begin at .md line 18 (one paragraph
  earlier — currently begins on a metadata fragment)

### TABLE / FIGURE / METADATA-LEAK (medium — may ship with note)
- ...

## Confirmed matches (one line each — confirms you actually read the file)
- Abstract paragraph 1 (185 words) — present, matches source
- Section ## Methods — boundary correct, content matches source

Be specific. Quote excerpts. Cite line numbers in BOTH files. A vague
"section boundaries look OK" is not acceptable — list every ## heading
and rule on each. If the documents are too large to read fully in one
pass, read them in chunks and combine — do NOT skim.
```

Keep the subagent prompt self-contained (the subagent has no conversation context). For very large papers (>100 KB rendered), split into multiple subagent calls — one per major section.

### Step 3 — Adjudicate

- **All checks PASS** → record `5d: AI-verified <paper>` in cycle report. Proceed.
- **Any TEXT-LOSS or HALLUCINATION finding** → revert the cycle's library edit (if newly introduced) AND queue a new cycle to fix the root cause (if pre-existing). These are uncategorical-blockers. Append a LEARNINGS entry explaining what slipped through Phase 5a–c. Do NOT try to patch the renderer around the AI's complaint — root-cause it in the layer of origin.
- **SECTION-BOUNDARY or TABLE / FIGURE / METADATA-LEAK finding** → if newly introduced this cycle → revert. If pre-existing → DO NOT ship around it: **queue an immediate-subsequent cycle in the same run to fix it.** See memory `feedback_fix_every_bug_found` (v2.4.16 release).

**Pre-existing ≠ deferrable.** A finding that existed in the prior release and was missed by an earlier cycle's verification is even MORE reason to fix it now — that earlier verification missed a real defect, and the defect has been silently corrupting outputs for users in the interim. The phrase "pre-existing, not introduced this cycle" is NOT a license to ship around the bug. It IS a hint that the previous cycle's verification was incomplete. Group defects by root cause (one cycle per root cause, not one cycle per finding), but the run does not terminate until every finding is addressed or escalated to the user explicitly.

**Critical rule:** do not negotiate with TEXT-LOSS findings. There is no "minor text loss." A meta-science user pulling data from this library cannot be told "we silently dropped one paragraph but the rest is fine."

### Step 4 — Cross-paper sweep (every 3rd cycle)

The single-paper AI verify catches cycle-specific regressions. But systematic patterns (e.g. "metadata-leak mid-Intro now affects 15 papers, was 4") need a corpus-wide view.

Every 3rd cycle, dispatch ONE subagent to read 5 randomly-sampled rendered .md files at once and produce a corpus-level findings list:

```
You are auditing the docpluck library output across 5 papers for systematic
quality issues. <Same 6 checks as above.> Produce a corpus-level findings list:
which categories of finding appear in how many papers; rank by paper-count.
This drives TRIAGE update for the next cycle.
```

This is the "discovery beats verification" pass — `verify_corpus.py`'s metrics can pass while a systematic structural issue affects 15 papers.

## What NOT to do

| Anti-pattern | Why it's wrong |
|--------------|----------------|
| "Read first 30 lines" | Mid-document drift (footnote leaks, table boundary bleed) only shows mid-document. The 30-line skim is the BASELINE before AI verify, not a substitute. |
| "Trust char-ratio + Jaccard" | Both blind to "right words wrong order under wrong heading." Documented in memory `feedback_ai_verification_mandatory`. |
| "Eyeball is enough, skip the subagent" | Eyeball misses systematic issues across multiple papers. A subagent reading 5 papers at once catches patterns. |
| "Subagent costs tokens — skip on small fixes" | A "small fix" that silently drops one paragraph is a catastrophic meta-science failure. Token cost is irrelevant against scientific correctness. |
| "If it passes the 26-paper baseline metrics, it's fine" | The 26-paper baseline checks structure metrics, not content correctness. AI verify is the content gate. |
| "Render output looks OK to me, the AI is being paranoid" | The AI verifier is calibrated to be conservative. Side with the verifier; if it flags something the user accepts, document why in LEARNINGS for next time. |

## How this composes with other phases

- **Phase 5a–c (unit tests + baseline)** check that the LIBRARY CODE works as intended on its own terms.
- **Phase 5d (this protocol)** checks that the OUTPUT IS CORRECT against the source PDF.
- Both are required. Neither substitutes for the other.

## Suggested subagent cost-management

- A full AI-verify on one APA paper (~60-90 KB rendered .md, ~50 KB pdftotext.txt) takes one general-purpose subagent ~1-2 minutes wall time.
- Per cycle: 3-8 papers × ~2 min = 6-16 minutes. Acceptable.
- Per 3rd cycle: + one corpus-sweep subagent (~3-4 min for 5 papers in one call).
- Total cycle time impact: ~20 minutes added. Worth every minute against the alternative (shipping a regression).
