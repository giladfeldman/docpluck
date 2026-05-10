# Handoff — Iteration 7 (start by reading TRIAGE.md, not this file)

**For:** A fresh Claude session continuing the docpluck splice-spike work. The previous (iter-7) session landed two structural fixes — F3 (title rescue) and the compound-heading sub-bug of F2 — and surfaced new high-value targets in the triage. Read the next section before touching code.

**Branch:** `main` at `58c5228`. Working tree clean. **221 tests passing** in `docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`. Corpus is **26 papers** (unchanged from iter-6).

---

## Read this section before doing ANYTHING else

The same iteration discipline as iter-6 still applies:

> **The canonical work queue is `docs/TRIAGE_2026-05-10_corpus_assessment.md`, NOT this handoff doc.**

Read [TRIAGE_2026-05-10_corpus_assessment.md](./TRIAGE_2026-05-10_corpus_assessment.md) FIRST. It maps:
- 8 dominant failure modes (F1-F8). Six are now ~~struck-through~~ as resolved (F1 cheap, F3, F5, F6, plus F2 compound-heading sub-bug).
- Remaining: F2 (section-detector misordering), F4 (Key-Points sidebar), F7 (DOI character-mash), F8 (numbered ToC headings).
- Top-3 priority-ordered candidates for the next iterations (iter-30, iter-31, iter-32).

The handoff lists what's happened; the triage lists what's *next*.

### Process rules (unchanged from iter-6)

1. **Start each session by reading `TRIAGE_*.md`** (the most-recent-dated file). Pick the next iteration from its top-3 candidates.

2. **Every 3-5 iterations OR whenever a new pattern emerges, run a broad-read pass.** Sample 8-10 random `.md` outputs end-to-end *as a reader, not a diff*. Always check the document **START** (first 30 lines). Update `TRIAGE.md` in place.

3. **Verification ≠ audit.** Char-ratio + word-delta is BLIND to "right words in wrong order under wrong heading". Periodic broad-reads are required.

4. **If 3-4 iters in a row produce only small char-ratio shifts on isolated papers, surface "diminishing returns; should we shift focus?" to the user proactively.**

5. **The optimization criterion is "biggest visible-quality lift per hour of effort", not "next item in the queue".**

6. **Don't blindly trust this handoff's Tier list.** The triage is current.

---

## Session state at HEAD

### Commit history (iter-7 session, 1 commit)

| SHA | What |
|---|---|
| [`58c5228`](https://github.com/giladfeldman/docpluck/commit/58c5228) | iter-28 layout-channel title rescue + iter-29 compound-heading merge (combined commit; both iters small and orthogonal) |

### Tests

```bash
cd docs/superpowers/plans/spot-checks/splice-spike && python -m pytest test_splice_spike.py -q
# Should show: 221 passed
```

The test file has explicit blocks per iteration. Iter-28 / Iter-29 tests live at the end of the file:
- `Iter-28 / Tier F3: title rescue from inside ## Abstract` (10 tests across `_apply_title_rescue` and `_compute_layout_title` with stub LayoutDoc)
- `Iter-29 / Tier F2-residual: multi-word JAMA heading tail re-attachment` (7 tests)

### Functions added

In `splice_spike.py` (~600 new lines, all conservative + heavily commented):

- `_compute_layout_title(layout_doc) -> str | None` — given an `extract_pdf_layout` output, identify the article title from page-1 spans + words. Conservative thresholds (>=12pt + 2 spans, OR >=18pt single span). Char-level fallback `_title_text_from_chars` for tight-kerned PDFs.
- `_title_text_from_chars(page1, y_min, y_max, title_size) -> str | None` — absolute-gap (>1.5pt) word reconstruction from per-character pdfplumber records. Used when `extract_words` returns concatenated tokens.
- `_apply_title_rescue(out, title_text) -> str` — three-case placement: existing h1 → no-op; in-place upgrade when title found before first `## ` heading; strip+prepend when title found inside the first `## ` section.
- `_rescue_title_from_layout(out, pdf_path) -> str` — top-level orchestrator with full failure-tolerance (any IO / import / parse error returns `out` unchanged).
- `_merge_compound_heading_tails(text) -> str` — narrow regex pass merging `## CONCLUSIONS\n\nAND RELEVANCE...` → `## CONCLUSIONS AND RELEVANCE\n\n...`. Curated list `_COMPOUND_HEADING_TAILS` is a single entry today; extend if other publishers split their multi-word headings the same way.

Both passes run at the END of `render_pdf_to_markdown`, after `_strip_page_footer_lines`. Order: footer-strip → compound-heading-merge → title-rescue.

### Resolved failure modes (don't relitigate)

- ✅ **F1 cheap variant** at `3b24041` (iter-6).
- ✅ **F3 title rescue** at `58c5228` (this session). 17 of 26 papers now open with `# Title`.
- ✅ **F5 TOC dot-leader strip** at `3b24041` (iter-6).
- ✅ **F6 banner-strip (curated patterns)** at `fca6f61` (iter-6).
- ✅ **F2 compound-heading-tail (`CONCLUSIONS AND RELEVANCE`)** at `58c5228` (this session).

---

## What's next per the triage (top-3, priority-ordered)

These are pulled from `TRIAGE_2026-05-10_corpus_assessment.md`. Order is **biggest visible-quality lift per hour**, not "in handoff order".

### Iter-30 — F4 Key Points sidebar detection (C2-C3, ~3 hr)

**Problem:** JAMA papers have a "Key Points" sidebar box (Question / Findings / Meaning) that lives in a separate x-column from the body. pdftotext linearizes it INTO the abstract. Currently jama_open_1 / jama_open_2 have:

```
## CONCLUSIONS AND RELEVANCE

This randomized clinical trial found that a TRE diet strategy without calorie counting was effective for weight loss and lowering of HbA1c levels compared with

Key Points Question Is time-restricted eating (TRE) without calorie counting more effective for weight loss...

## Findings

In a 6-month randomized clinical trial involving 75 adults with T2D, TRE was more effective for weight loss...
Meaning These findings suggest that time-restricted eating may be an effective alternative strategy...

daily calorie counting in a sample of adults with T2D. These findings will need to be confirmed by larger RCTs with longer follow-up.
```

The `Key Points Question ... Findings ... Meaning ...` block is wedged between the two halves of the CONCLUSIONS body sentence. Plus it false-promotes "Findings" to a `##` heading.

**Fix:** Layout-channel-aware. The sidebar has its own bbox column at a different x-coordinate than the body. Detect text whose x-column is >50pt offset from the dominant body column on the same page, in the same y-range as body text → preserve as a separate `<aside>` block (or `> Key Points:` blockquote) instead of inlining.

Implementation sketch:
1. From `extract_pdf_layout`, group page-1 spans by x-column (cluster on x0 with 30pt tolerance).
2. Identify the dominant body column (most spans at body-text font size).
3. Tag spans NOT in body column at body font size as "sidebar".
4. In the rendered .md, find the substring corresponding to those sidebar spans and rewrap as `> Key Points: ...`.
5. Also drop the false-promoted `## Findings` heading.

This is C3 because it needs page-bbox awareness threaded through the spike. Consider iter-31 first if iter-30 stalls.

### Iter-31 — F6 residual: extra banner patterns for plain-text journal-name lines (C1, ~30 min)

**Problem:** 7 papers have a journal-name banner at line 1 ABOVE the rescued `# Title`:

| Paper | Banner line still at top |
|---|---|
| korbmacher_2022_kruger | `Judgment and Decision Making, Vol. 17, No. 1, January 2022, pp. 449–486` |
| ziano_2021_joep | `Journal of Economic Psychology` |
| chan_feldman_2025_cogemo | `Cognition and Emotion` |
| chen_2021_jesp | `Journal of Experimental Social Psychology` |
| ar_apa_j_jesp_2009_12_010 | `Journal of Experimental Social Psychology 46 (2010) 494–504` |
| social_forces_1 | `Social Forces, 2025, 104, 224–249` |
| (+ ieee_access_2 — line 1 IS the title, low char ratio) |

These bare journal-name lines aren't in the curated `_HEADER_BANNER_PATTERNS` list yet. Add patterns for:
- `^Journal of [A-Z][\w ]+(?:\s+\d+\s+\(\d{4}\)\s+[\d–-]+)?$`
- `^Cognition and Emotion$`
- `^Social Forces,\s*\d{4},\s*\d+,\s*[\d–-]+$`
- `^Judgment and Decision Making,\s*Vol\.\s*\d+`
- (similar pattern for any bare `^<Title-Cased Journal Name>(\s+\d.*)?$` that appears before the `# Title`)

C1, narrow regex extension, low risk. Cleans the document START on 7+ papers. Easy reader-quality win.

### Iter-32 — F2 structural section-detector misordering (C2-C3)

**Problem:** Even with iter-27 + iter-29 fixes, am_sociol_rev_3 still shows `## Introduction` printed BETWEEN halves of a body sentence (not inside, but the heading is in the wrong reading-order position). amc_1 has `## 1980s` mid-paragraph. nat_comms_2 has F3-residual where the `## Abstract` heading still appears at line N+1 with author-block as line N text.

This is library-level (`docpluck/sections/`). Defer until F4 sidebar detection lands and we have a clear threading-of-page-bbox-info pattern to reuse.

---

## Required reading before touching code

1. **[`TRIAGE_2026-05-10_corpus_assessment.md`](./TRIAGE_2026-05-10_corpus_assessment.md)** — the work queue. Top-3 candidates section. Read this FIRST.
2. **[`LESSONS.md`](../LESSONS.md)** — durable incident log for L-001 through L-005.
3. **[`CLAUDE.md`](../CLAUDE.md)** — particularly the "Spike work queue" section with iteration discipline rules.
4. **Auto-memory at `~/.claude/projects/.../memory/`** — particularly `feedback_optimize_for_outcomes_not_iterations.md` and `project_triage_md_is_work_queue.md`.
5. **Three .md outputs end-to-end** — pick one rescued-title APA (`outputs/korbmacher_2022_kruger.md`, see line 2 has `# Title`), one with active F4 issue (`outputs-new/jama_open_1.md` — Key Points sidebar wedged between CONCLUSIONS halves at line 18-26), and one rendered cleanly (`outputs-new/sci_rep_1.md` — `# Title`, then `## Abstract` with author byline + abstract body, then `## Introduction`).

---

## Operational details

### Render commands (3 batches, parallelize)

```bash
# OLD batch (7 papers in outputs/)
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck" && for f in korbmacher_2022_kruger efendic_2022_affect chandrashekar_2023_mp ziano_2021_joep ip_feldman_2025_pspb; do
  python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/apa/${f}.pdf" 2>"docs/superpowers/plans/spot-checks/splice-spike/outputs/${f}.err" > "docs/superpowers/plans/spot-checks/splice-spike/outputs/${f}.md"
done && python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/nature/nat_comms_1.pdf" 2>docs/superpowers/plans/spot-checks/splice-spike/outputs/nat_comms_1.err > docs/superpowers/plans/spot-checks/splice-spike/outputs/nat_comms_1.md && python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/ieee/ieee_access_2.pdf" 2>docs/superpowers/plans/spot-checks/splice-spike/outputs/ieee_access_2.err > docs/superpowers/plans/spot-checks/splice-spike/outputs/ieee_access_2.md && echo OLD_DONE

# NEW batch 1 (10 papers)
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck" && for spec in "ama/jama_open_1" "ama/jama_open_2" "aom/amc_1" "aom/amj_1" "aom/amle_1" "apa/chan_feldman_2025_cogemo" "apa/chen_2021_jesp" "apa/ar_apa_j_jesp_2009_12_010" "asa/am_sociol_rev_3" "asa/social_forces_1"; do
  name=$(basename "$spec")
  python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/${spec}.pdf" 2>"docs/superpowers/plans/spot-checks/splice-spike/outputs-new/${name}.err" > "docs/superpowers/plans/spot-checks/splice-spike/outputs-new/${name}.md"
done && echo NEW_BATCH1_DONE

# NEW batch 2 (9 papers)
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck" && for spec in "chicago-ad/demography_1" "chicago-ad/jmf_1" "harvard/bjps_1" "harvard/ar_royal_society_rsos_140066" "harvard/ar_royal_society_rsos_140072" "ieee/ieee_access_3" "ieee/ieee_access_4" "nature/nat_comms_2" "nature/sci_rep_1"; do
  name=$(basename "$spec")
  python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/${spec}.pdf" 2>"docs/superpowers/plans/spot-checks/splice-spike/outputs-new/${name}.err" > "docs/superpowers/plans/spot-checks/splice-spike/outputs-new/${name}.md"
done && echo NEW_BATCH2_DONE
```

### Audit (char ratios + word counts across 26 papers)

Same Python audit script as the iter-6 handoff §`Audit`. The list of 26 papers is unchanged.

### Word-level diff vs HEAD (use after every change)

Same script as iter-6 handoff. Non-zero deltas should be ONLY tag tokens (td/tr/br/sup), banner/footer tokens (Page/Cite/etc.), or expected title-prepend tokens.

---

## Current corpus snapshot (audit at HEAD `58c5228`)

| Paper | src | output | ratio | flag | notes |
|---|---|---|---|---|---|
| korbmacher_2022_kruger | 98311 | 106651 | 1.085 | | iter-28 in-place title upgrade (line 2) |
| efendic_2022_affect | 52293 | 60133 | 1.150 | | iter-28 title upgrade |
| chandrashekar_2023_mp | 112817 | 111470 | 0.988 | | iter-28 title upgrade |
| ziano_2021_joep | 43478 | 56520 | 1.300 | bloat | T1 stitched 14-col — Tier B; banner above title |
| ip_feldman_2025_pspb | 88431 | 103054 | 1.165 | | iter-28 title upgrade |
| nat_comms_1 | 76850 | 75379 | 0.981 | | iter-28 title PREPEND (was missing) |
| ieee_access_2 | 71909 | 58802 | 0.818 | low | pre-existing extraction issue; line 1 IS title (no #) |
| jama_open_1 | 50456 | 57254 | 1.135 | | iter-28 char-fallback + iter-29 CONCLUSIONS merge |
| jama_open_2 | 48068 | 52349 | 1.089 | | iter-28 char-fallback + iter-29 |
| amc_1 | 74623 | 73855 | 0.990 | | iter-28 title upgrade; tables flattened — partial |
| amj_1 | 126454 | 123114 | 0.974 | | iter-28 char-fallback title upgrade |
| amle_1 | 135600 | 111029 | 0.819 | low | iter-28 char-fallback title upgrade; 12/13 tables undetected — Tier B |
| chan_feldman_2025_cogemo | 81335 | 87247 | 1.073 | | banner above title |
| chen_2021_jesp | 136836 | 186853 | 1.366 | bloat | iter-28 in-place title upgrade; banner above title |
| ar_apa_j_jesp_2009_12_010 | 79332 | 87612 | 1.104 | | banner above title |
| am_sociol_rev_3 | 107541 | 110887 | 1.031 | | iter-28 title prepend; F2 misordering remains |
| social_forces_1 | 92567 | 116193 | 1.255 | bloat | iter-21+24 wins; banner above title |
| demography_1 | 76008 | 76401 | 1.005 | | title font <12pt — no rescue, but title at line 1 already |
| jmf_1 | 74796 | 64141 | 0.858 | low | title font <12pt — no rescue; no tables — Tier B |
| bjps_1 | 92321 | 103157 | 1.117 | | iter-28 title upgrade |
| ar_royal_society_rsos_140066 | 22913 | 21922 | 0.957 | | iter-28 title PREPEND |
| ar_royal_society_rsos_140072 | 60912 | 46684 | 0.766 | low | iter-28 title upgrade; iter-22 leader-dot strip — NOT content loss |
| ieee_access_3 | 81412 | 79792 | 0.980 | | iter-28 title upgrade; All tables dropped — Tier B |
| ieee_access_4 | 59154 | 69485 | 1.175 | | iter-28 title upgrade; T1 body-prose `<th>` |
| nat_comms_2 | 81475 | 76758 | 0.942 | low | iter-28 title PREPEND; zero tables — Tier B |
| sci_rep_1 | 56139 | 65916 | 1.174 | | iter-28 title PREPEND from inside Abstract — flagship F3 fix |

---

## Key files

| Path | Role |
|---|---|
| [`docs/TRIAGE_2026-05-10_corpus_assessment.md`](./TRIAGE_2026-05-10_corpus_assessment.md) | **The canonical work queue. Read this first.** |
| [`docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/splice_spike.py) | The standalone the user reviews. Most fixes go here. ~3800 lines. |
| [`docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/test_splice_spike.py) | 221 unit tests at HEAD. Must stay green after every change. |
| [`docs/superpowers/plans/spot-checks/splice-spike/outputs/`](./superpowers/plans/spot-checks/splice-spike/outputs/) | 7 OLD-corpus regenerated `.md` outputs. |
| [`docs/superpowers/plans/spot-checks/splice-spike/outputs-new/`](./superpowers/plans/spot-checks/splice-spike/outputs-new/) | 19 new-corpus regenerated `.md` outputs. |
| [`docpluck/extract_layout.py`](../docpluck/extract_layout.py) | pdfplumber-based layout channel. iter-28 calls `extract_pdf_layout` from here. |
| [`docpluck/tables/captions.py`](../docpluck/tables/captions.py) | Library-level caption regex. |

---

## Critical hard rules (still in force)

All previous-iteration rules from `LESSONS.md` PLUS:

- **Don't swap pdftotext for pymupdf.** L-001 / L-003. AGPL license.
- **Don't use pdftotext `-layout`.** L-002.
- **Always normalize U+2212 → ASCII hyphen.** L-004.
- **Test on APA / replication papers.** L-005.
- **Char ratio drop is not always content loss.** Iter-22 / iter-25–27 / iter-28 all dropped char counts on multiple papers; word-token diff confirmed they were tag/banner/footer/marker tokens only.
- **Conservative > canonical when uncertain.**
- **Walk-back guards matter.**
- **HTML placeholders survive escaping** (`_SUP_OPEN`, `_MERGE_SEPARATOR`).
- **Subagents that render PDFs sometimes fail silently** with 0-byte outputs — always verify file sizes after subagent batch rendering.
- **The corpus is large enough to find new patterns each iteration.** Surface them in the triage.
- **(NEW iter-7) Layout-channel font sizes from `extract_pdf_layout` are reliable for title detection but `extract_words` text spacing is NOT — it depends on a 3pt default `x_tolerance` that fails on tight-kerned PDFs (JAMA, AOM). Always carry a char-level fallback that uses absolute x-gap (>1.5pt) for word reconstruction.**

---

## What success looks like

A reader should be able to read a rendered .md file from top to bottom without bumping into:
- Banner junk (✅ resolved iter-25, with 7-paper residual planned for iter-31)
- TOC content (✅ resolved iter-26)
- Page-footer text mid-body (✅ resolved iter-27)
- Title nested under Abstract (✅ resolved iter-28)
- Multi-word headings split mid-phrase (✅ resolved iter-29 for `CONCLUSIONS AND RELEVANCE`)
- Sidebar Key-Points content inlined as body (⏳ iter-30)
- Plain-text journal-name banner above title (⏳ iter-31)
- Body sentences split across page boundaries (⏳ future C3)

The user reads each .md file in a markdown viewer — what they see is what we're optimizing.

---

## One-line summary for the next session

> Read TRIAGE.md. Run pytest (221). Top-3 = iter-30 (F4 Key Points), iter-31 (F6 residual), iter-32 (F2 structural). Iter-31 is the cheap C1 win (~30 min) cleaning the doc-start of 7 more papers; consider doing it FIRST if iter-30 stalls. Periodically broad-read 8-10 outputs. Update TRIAGE. Surface diminishing returns to the user. Optimize for outcome, not iteration count.
