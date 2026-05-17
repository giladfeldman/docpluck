# Tier-A verifier agent prompt template

The orchestrator (docpluck-iterate / docpluck-qa) dispatches **one verifier
agent per job** in `verify_out/inspect_jobs.json`. Each job is a
(document × normalization-level) cell with its AI gold and its saved harness
outputs. Fill the `{{...}}` placeholders from the job record and dispatch.

The agent compares **the files the harness downloaded from the app** against
the **AI-multimodal gold**. It does not re-render anything and does not look at
the source PDF except as noted. It writes one JSON verdict file.

---

## PROMPT

```
You are a verification agent for the docpluck academic-document extraction
system. Compare the app's saved extraction output against an AI-multimodal
ground-truth gold and produce a structured verdict.

GROUND TRUTH (the gold — an AI multimodal read of the source document):
  {{gold_reading}}

APP OUTPUT FILES (what the harness downloaded from the local app for this
document at normalization level "{{level}}"):
  rendered markdown : {{outputs.rendered}}
  raw text          : {{outputs.raw}}
  normalized text   : {{outputs.normalized}}
  tables JSON       : {{outputs.tables}}
  sections JSON     : {{outputs.sections}}

Read the gold IN FULL. Read the rendered markdown IN FULL. Open the other
files as needed. Then judge these checks. Quote specific evidence for every
finding (a sentence from the gold + the corresponding spot in the output).

1. TEXT-LOSS  (uncategorical blocker)
   Every substantive paragraph in the gold must appear in the rendered output.
   Allowed omissions: running headers, page numbers, copyright/watermark lines,
   the journal masthead. A dropped body/results/methods/discussion paragraph,
   a dropped sentence, a dropped table row, a dropped figure caption = FAIL.

2. HALLUCINATION  (uncategorical blocker)
   Every substantive paragraph in the rendered output must trace to the gold.
   Renderer markup (headings, italic captions) is not hallucination; invented
   prose is.

3. SECTION-BOUNDARY
   Every `##`/`###` heading in the rendered output exists at a plausible spot
   vs the gold's structure. Flag: a heading the gold does not have; a real
   section demoted to body text; body text promoted to a heading; a paragraph
   filed under the wrong heading.

4. TABLE  (cross-output — inspect tables JSON AND rendered markdown)
   For every table in tables.json: it must also appear in the rendered
   markdown as a `<table>` (a structured table) at the right place. Flag a
   table present in tables.json but absent/garbled in rendered markdown;
   a caption welded to a column-header row; a table or its caption spliced
   into a body sentence (mid-sentence/mid-word); concatenated or dropped
   cells; numeric cell values that differ from the gold.

5. FIGURE
   Figure captions match the gold. Flag truncation, off-by-one pairing,
   double-emission (the same caption inline AND as a block), body prose
   welded into a caption.

6. GLYPH-SEMANTIC
   Compare glyphs against the gold: a Greek letter / operator / statistic
   symbol that is a *valid codepoint but the wrong character* (e.g. rendered
   "ξ" where the gold has "ηp²"; "beta" where the gold has "β"; a digit where
   the gold has a minus sign). U+2212→hyphen and NFKC composition are allowed.

7. METADATA-LEAK
   Body sections must not contain orphan affiliations, contact lines,
   download watermarks, journal mastheads, received/accepted dates spliced
   into prose.

OUTPUT — write ONLY this JSON to {{verdict_path}} (overwrite):
{
  "doc_id": "{{doc_id}}",
  "level": "{{level}}",
  "verdict": "pass" | "fail",
  "checks": {
    "text_loss":        {"verdict": "pass|fail", "findings": ["..."]},
    "hallucination":    {"verdict": "pass|fail", "findings": ["..."]},
    "section_boundary": {"verdict": "pass|fail", "findings": ["..."]},
    "table":            {"verdict": "pass|fail", "findings": ["..."]},
    "figure":           {"verdict": "pass|fail", "findings": ["..."]},
    "glyph_semantic":   {"verdict": "pass|fail", "findings": ["..."]},
    "metadata_leak":    {"verdict": "pass|fail", "findings": ["..."]}
  },
  "summary": "one-paragraph plain-English assessment"
}

The overall "verdict" is "fail" if ANY check is "fail". TEXT-LOSS and
HALLUCINATION failures are uncategorical blockers — never soften them.
Each finding string must quote concrete evidence. Then reply with the JSON
verdict in your final message too.
```

---

## Notes for the orchestrator

- Dispatch jobs whose `status` is `ready`. Jobs with `status: gold_blocked`
  have no AI gold — record them as gold-blocked in the coverage matrix and do
  NOT treat them as passing (rule 18: a gold-blocked paper is verified by
  Tier-D only, never by a downgraded "looks fine").
- One agent per job, dispatched in parallel (independent inputs, distinct
  `verdict_path` outputs — the parallelization safety checklist passes).
- After all agents finish: `python -m scripts.harness.inspect collect`.
- TEXT-LOSS / HALLUCINATION fails are uncategorical blockers (CLAUDE.md 0a/0b).
