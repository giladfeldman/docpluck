# Handoff — Iteration 6 (start by reading TRIAGE.md, not this file)

**For:** A fresh Claude session continuing the docpluck splice-spike work. The previous session (this one) made a **structural change to how iterations are prioritized** — read the next section carefully before touching code.

**Branch:** `main` at `32cd761`. Working tree clean. **203 tests passing** in `docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`. Corpus is **26 papers** (`nathumbeh_2` was removed because it was supplementary materials, not an article).

---

## ⚠️ Read this section before doing ANYTHING else

The previous session ran 24+ iterations against a stale work queue (the previous handoff's "Tier A/B/C" list). Each iteration was technically clean — tests added, corpus re-rendered, char ratios stable, zero word loss. But the corpus stayed full of obvious problems the iteration loop never surfaced (page-footer interleave on 13 papers, banner junk, title-stuffed-into-Abstract on Nature) because **the loop was regression-focused, not discovery-focused**.

The user (Gilad) had to flag those problems manually. That was a process failure on my side. Don't repeat it.

### The iteration discipline now in force

**The canonical work queue is `docs/TRIAGE_2026-05-10_corpus_assessment.md`, NOT this handoff doc.**

Read [TRIAGE_2026-05-10_corpus_assessment.md](./TRIAGE_2026-05-10_corpus_assessment.md) FIRST. It maps:
- 8 dominant failure modes (F1 - F8) found across the corpus
- Severity (S0-S3) × scope (papers affected) × cost (C1-C4)
- Resolved markers (struck-through with commit SHAs)
- Top-3 priority-ordered candidates for the next iterations

The handoff lists what's happened; the triage lists what's *next*.

### Process rules

1. **Start each session by reading `TRIAGE_*.md`** (the most-recent-dated file). Pick the next iteration from its top-3 candidates.

2. **Every 3-5 iterations OR whenever a new pattern emerges, run a broad-read pass.** Sample 8-10 random `.md` outputs end-to-end *as a reader, not a diff*. Always check the document **START** (first 30 lines) — that's what the user sees first and where the worst issues hide. Update `TRIAGE.md` in place: strike resolved items, add new ones, re-rank by severity × cost.

3. **Verification ≠ audit.**
   - **Verification** (post-fix, every iter): "did I break things?" → char ratio + word delta + 1-2 visual reads.
   - **Audit** (periodic, broad): "what's still broken?" → 8-10 paper end-to-end reads.
   - **Both are required.** Char ratios + word-token deltas catch CONTENT LOSS. They are BLIND to structural problems where the right words are present but in the wrong order under the wrong heading. JAMA's `## CONCLUSIONS / AND RELEVANCE` split has a perfect char ratio and zero word delta — and is broken.

4. **If 3-4 iters in a row produce only small char-ratio shifts on isolated papers, surface "diminishing returns; should we shift focus?" to the user proactively.** Do not quietly continue patching the same area. The user wants outcome quality, not iteration count.

5. **The optimization criterion is "biggest visible-quality lift per hour of effort", not "next item in the queue".** That requires the triage to compare severity × cost — not just enumerate issues. If the priority-1 item in the triage is C3 (expensive) and a priority-3 item is C1 (~30 min), do the priority-3 first, then re-evaluate.

6. **Don't blindly trust the handoff's Tier list.** This handoff is a snapshot of one session's view. The triage is current.

---

## Session state at HEAD

### Commit history (this session, 7 commits)

| SHA | What |
|---|---|
| [`6e8d266`](https://github.com/giladfeldman/docpluck/commit/6e8d266) | iter-23 — fold FIGURE/TABLE captions split across consecutive lines (Tier A7) |
| [`768a942`](https://github.com/giladfeldman/docpluck/commit/768a942) | iter-24 — forward-attach for orphan marker rows after text-anchor (Tier A8); social_forces_1 stars |
| [`dcd2829`](https://github.com/giladfeldman/docpluck/commit/dcd2829) | docs — TRIAGE.md is canonical work queue + iteration discipline added to CLAUDE.md |
| [`fca6f61`](https://github.com/giladfeldman/docpluck/commit/fca6f61) | iter-25 — banner / running-header strip in document header zone (F6 RESOLVED) |
| [`fc7e129`](https://github.com/giladfeldman/docpluck/commit/fc7e129) | docs(triage) — F6 resolved, queue F5/F1 next |
| [`3b24041`](https://github.com/giladfeldman/docpluck/commit/3b24041) | iter-26 (F5 TOC dot-leader strip) + iter-27 (F1 cheap-variant page-footer strip) + drop nathumbeh_2 from corpus |
| [`32cd761`](https://github.com/giladfeldman/docpluck/commit/32cd761) | docs(triage) — F5 + F1 resolved, nathumbeh_2 dropped, iter-28/29/30 queued |

### Tests

```bash
cd docs/superpowers/plans/spot-checks/splice-spike && python -m pytest test_splice_spike.py -q
# Should show: 203 passed
```

The test file has explicit blocks per iteration: `Iter-23 / Tier A7`, `Iter-24 / Tier A8`, `Iter-25 / F6`, `Iter-26 / F5`, `Iter-27 / F1`. New iteration tests should be added in their own marked block at the end.

### Corpus

26 papers, split between two output directories per the historical session structure:

- `outputs/` — 7 papers (originally older corpus): korbmacher, efendic, chandrashekar, ziano, ip_feldman_2025_pspb, nat_comms_1, ieee_access_2.
- `outputs-new/` — 19 papers: jama_open_1/2, amc_1, amj_1, amle_1, chan_feldman_2025_cogemo, chen_2021_jesp, ar_apa_j_jesp_2009_12_010, am_sociol_rev_3, social_forces_1, demography_1, jmf_1, bjps_1, ar_royal_society_rsos_140066, ar_royal_society_rsos_140072, ieee_access_3, ieee_access_4, nat_comms_2, sci_rep_1.

`nathumbeh_2` was deleted at `3b24041` — it was supplementary materials, not an article.

### Resolved failure modes (don't relitigate)

- ✅ **F6 banner/running-header strip** at `fca6f61` — 16 papers had publisher banners (HHS, arXiv, AOM, Royal Society, Tandfonline, Elsevier, mangled-DOI, manuscript-ID gibberish) stripped from header zone.
- ✅ **F5 TOC dot-leader strip** at `3b24041` — TOC entries with `__________ 17` page-number trails dropped, plus false-promoted `## Heading` entries.
- ✅ **F1 cheap variant — page-footer line strip** at `3b24041` — 13+ papers had `Page N`, `October 27, 2023 X/13`, `(continued)`, `Corresponding Author:`, bare email lines, JAMA citation/category headers, `Open Access. ... (Reprinted)`, `© YYYY`, `aETH Zurich`, JAMA Visual Abstract sidebar all dropped.

The functions are in `splice_spike.py`:
- `_strip_document_header_banners` (header-zone-only, conservative — `_HEADER_BANNER_PATTERNS` curated regex list)
- `_strip_toc_dot_leader_block` (head-zone-only, drops paragraphs containing `_{3,}` + false `## Headings` immediately preceding TOC paragraphs)
- `_strip_page_footer_lines` (whole-document, line-level, `_PAGE_FOOTER_LINE_PATTERNS` curated regex list)

---

## What's next per the triage (top-3, priority-ordered)

These are pulled from `TRIAGE_2026-05-10_corpus_assessment.md`. Order is **biggest visible-quality lift per hour**, not "in handoff order".

### Iter-28 — F3 title rescue from Abstract section (C2, ~2 hr)

**Problem:** sci_rep_1, nat_comms_1, nat_comms_2, ar_royal_society_rsos_140066 — the article title and authors get dumped INSIDE the `## Abstract` section instead of being a `# Title` block at the top of the document. The section detector sees "Abstract" / "OPEN" / "ARTICLE" as the document's first heading and sweeps everything before it as preamble that gets bundled under that heading.

Example (sci_rep_1, current state):
```
## Abstract

OPEN The association between dietary
approaches to stop hypertension
diet and bone mineral density in US
adults: evidence from the National
Health and Nutrition Examination
Survey (2011–2018)
Xiang‑Long Zhai 1,3, ...
This study aimed to investigate the relationship between...
```

Title and authors are inside Abstract.

**Fix:** Layout-channel pre-pass that runs BEFORE section detection. Use `extract_pdf_layout` (pdfplumber) to find the LARGEST-font multi-line block in the upper third of page 1. That's the title. Find the next-largest line below it — that's the author byline. Emit the title as `# Title` at the top of the .md, then the authors line, then a blank, then continue with whatever section detection wanted to do.

Risk: false positives on papers where the title is small / where the journal banner is large. Mitigate by requiring the candidate title block to be in the top 30% of page 1 AND have no body-paragraph siblings on the same page.

### Iter-29 — F2 multi-word heading tokenization (C1, ~30 min)

**Problem:** JAMA structured-abstract headings like `CONCLUSIONS AND RELEVANCE` get split into `## CONCLUSIONS` (heading) + `AND RELEVANCE` (orphan body fragment). Affects jama_open_1, jama_open_2.

**Fix:** Recognize known multi-word section headings as a unit before fragmenting on whitespace. Curated list: `CONCLUSIONS AND RELEVANCE`, `DESIGN, SETTING, AND PARTICIPANTS`, `MAIN OUTCOMES AND MEASURES`, `INTERVENTIONS`. Easy to test, narrow blast radius.

### Iter-30 — F4 Key-Points sidebar detection (C2-C3)

**Problem:** JAMA-style "Key Points" sidebar boxes ("Question / Findings / Meaning") get inlined into the abstract as if they were body paragraphs. Affects jama_open_1, jama_open_2.

**Fix:** Layout-channel-aware. The Key Points box has its own bbox column at a different x-coordinate than the body. Detect text that wedges between body lines but lives in a different x-column → preserve as a separate `<aside>` block instead of inlining.

This one is closer to C3 because it needs page-bbox awareness similar to the deferred F1 structural fix. Consider doing iter-28 + iter-29 first, then re-evaluate whether iter-30 is the right next step.

---

## Required reading before touching code

1. **[`TRIAGE_2026-05-10_corpus_assessment.md`](./TRIAGE_2026-05-10_corpus_assessment.md)** — the work queue. Top-3 candidates section. Read this FIRST.
2. **[`LESSONS.md`](../LESSONS.md)** — durable incident log for the recurring mistakes (L-001 through L-005). Don't relitigate decisions there.
3. **[`CLAUDE.md`](../CLAUDE.md)** — particularly the new "Spike work queue" section at the top with the iteration discipline rules.
4. **Auto-memory at `~/.claude/projects/.../memory/`** — particularly `feedback_optimize_for_outcomes_not_iterations.md` and `project_triage_md_is_work_queue.md`.
5. **Three .md outputs end-to-end** — pick one stable APA, one with active issues (e.g. `outputs-new/sci_rep_1.md` for F3, `outputs-new/jama_open_1.md` for F2/F4), and one rendered cleanly (`outputs-new/am_sociol_rev_3.md` post iter-25/26/27 to see what success looks like).

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

# NEW batch 2 (9 papers — note nathumbeh_2 REMOVED)
cd "C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck" && for spec in "chicago-ad/demography_1" "chicago-ad/jmf_1" "harvard/bjps_1" "harvard/ar_royal_society_rsos_140066" "harvard/ar_royal_society_rsos_140072" "ieee/ieee_access_3" "ieee/ieee_access_4" "nature/nat_comms_2" "nature/sci_rep_1"; do
  name=$(basename "$spec")
  python docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py "../PDFextractor/test-pdfs/${spec}.pdf" 2>"docs/superpowers/plans/spot-checks/splice-spike/outputs-new/${name}.err" > "docs/superpowers/plans/spot-checks/splice-spike/outputs-new/${name}.md"
done && echo NEW_BATCH2_DONE
```

### Audit (char ratios + word counts across 26 papers)

```python
import re, subprocess, sys
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')
from docpluck import extract_pdf

PAPERS = [
    ('apa/korbmacher_2022_kruger', 'outputs/korbmacher_2022_kruger'),
    ('apa/efendic_2022_affect', 'outputs/efendic_2022_affect'),
    ('apa/chandrashekar_2023_mp', 'outputs/chandrashekar_2023_mp'),
    ('apa/ziano_2021_joep', 'outputs/ziano_2021_joep'),
    ('apa/ip_feldman_2025_pspb', 'outputs/ip_feldman_2025_pspb'),
    ('nature/nat_comms_1', 'outputs/nat_comms_1'),
    ('ieee/ieee_access_2', 'outputs/ieee_access_2'),
    ('ama/jama_open_1', 'outputs-new/jama_open_1'),
    ('ama/jama_open_2', 'outputs-new/jama_open_2'),
    ('aom/amc_1', 'outputs-new/amc_1'),
    ('aom/amj_1', 'outputs-new/amj_1'),
    ('aom/amle_1', 'outputs-new/amle_1'),
    ('apa/chan_feldman_2025_cogemo', 'outputs-new/chan_feldman_2025_cogemo'),
    ('apa/chen_2021_jesp', 'outputs-new/chen_2021_jesp'),
    ('apa/ar_apa_j_jesp_2009_12_010', 'outputs-new/ar_apa_j_jesp_2009_12_010'),
    ('asa/am_sociol_rev_3', 'outputs-new/am_sociol_rev_3'),
    ('asa/social_forces_1', 'outputs-new/social_forces_1'),
    ('chicago-ad/demography_1', 'outputs-new/demography_1'),
    ('chicago-ad/jmf_1', 'outputs-new/jmf_1'),
    ('harvard/bjps_1', 'outputs-new/bjps_1'),
    ('harvard/ar_royal_society_rsos_140066', 'outputs-new/ar_royal_society_rsos_140066'),
    ('harvard/ar_royal_society_rsos_140072', 'outputs-new/ar_royal_society_rsos_140072'),
    ('ieee/ieee_access_3', 'outputs-new/ieee_access_3'),
    ('ieee/ieee_access_4', 'outputs-new/ieee_access_4'),
    ('nature/nat_comms_2', 'outputs-new/nat_comms_2'),
    ('nature/sci_rep_1', 'outputs-new/sci_rep_1'),
]
def words(s): return re.findall(r'\b\w+\b', s)
print(f"{'Paper':40}  {'src':>6}  {'out':>6}  {'ratio':>6}  {'words':>6}")
for pdf, name in PAPERS:
    with open(f'../PDFextractor/test-pdfs/{pdf}.pdf','rb') as f:
        t,_ = extract_pdf(f.read())
    out = open(f'docs/superpowers/plans/spot-checks/splice-spike/{name}.md', encoding='utf-8').read()
    ratio = len(out) / len(t) if len(t) else 0
    flag = ''
    if ratio < 0.5: flag = 'CRASH'
    elif ratio < 0.95: flag = 'low'
    elif ratio > 1.20: flag = 'bloat'
    short = pdf.split('/',1)[1]
    print(f'{short:40}  {len(t):>6}  {len(out):>6}  {ratio:>6.3f}  {wc(out):>6}  {flag}')
```

### Word-level diff vs HEAD (use after every change)

```python
import re, subprocess
from collections import Counter
def words(s): return re.findall(r'\b\w+\b', s)
PAPER='outputs-new/sci_rep_1.md'  # change to suspect paper
text = open(f'docs/superpowers/plans/spot-checks/splice-spike/{PAPER}', encoding='utf-8').read()
res = subprocess.run(['git','show',f'HEAD:docs/superpowers/plans/spot-checks/splice-spike/{PAPER}'],capture_output=True,text=True,encoding='utf-8')
head = res.stdout
hw, cw = Counter(words(head)), Counter(words(text))
diffs = sorted([(cw[w]-hw[w], w) for w in set(hw)|set(cw) if cw[w]!=hw[w]])
for d, w in diffs[:20]: print(d, repr(w))
# Non-zero deltas should be ONLY tag tokens (td/tr/br/sup) or banner/footer
# tokens (Cite/Author/Page/etc.). Real-content body words = STOP and revert.
```

---

## Current corpus snapshot (audit at HEAD)

| Paper | src | output | ratio | flag | notes |
|---|---|---|---|---|---|
| korbmacher_2022_kruger | 98311 | 106647 | 1.085 | | stable |
| efendic_2022_affect | 52293 | 60131 | 1.150 | | stable |
| chandrashekar_2023_mp | 112817 | 111467 | 0.988 | | stable |
| ziano_2021_joep | 43478 | 56527 | 1.300 | bloat | T1 stitched 14-col — Tier B |
| ip_feldman_2025_pspb | 88431 | 103052 | 1.165 | | stable |
| nat_comms_1 | 76850 | 75289 | 0.980 | | F3 (title in Abstract) |
| ieee_access_2 | 71909 | 58802 | 0.818 | low | pre-existing extraction issue |
| jama_open_1 | 50456 | 57252 | 1.135 | | F2 (CONCLUSIONS/AND RELEVANCE), F4 (Key Points) |
| jama_open_2 | 48068 | 52347 | 1.089 | | F2, F4 |
| amc_1 | 74623 | 73852 | 0.990 | | tables flattened — partial |
| amj_1 | 126454 | 123111 | 0.974 | | iter-23 caption-fix |
| amle_1 | 135600 | 111027 | 0.819 | low | 12/13 source tables not detected — Tier B |
| chan_feldman_2025_cogemo | 81335 | 87245 | 1.073 | | stable |
| chen_2021_jesp | 136836 | 186852 | 1.366 | bloat | T9/T10 side-by-side — Tier B |
| ar_apa_j_jesp_2009_12_010 | 79332 | 87611 | 1.104 | | stable |
| am_sociol_rev_3 | 107541 | 110885 | 1.031 | | F2 (## Introduction misplaced) |
| social_forces_1 | 92567 | 116191 | 1.255 | bloat | iter-21+24 wins; some orphan stars remain |
| demography_1 | 76008 | 76401 | 1.005 | | stable |
| jmf_1 | 74796 | 64141 | 0.858 | low | No tables detected — Tier B |
| bjps_1 | 92321 | 103155 | 1.117 | | stable |
| ar_royal_society_rsos_140066 | 22913 | 21919 | 0.957 | | F3 (title in Abstract) |
| ar_royal_society_rsos_140072 | 60912 | 46681 | 0.766 | low | iter-22 leader-dot strip — NOT content loss |
| ieee_access_3 | 81412 | 79790 | 0.980 | | All tables dropped by Camelot — Tier B |
| ieee_access_4 | 59154 | 69483 | 1.175 | | T1 still has body-prose `<th>`; T8 still has bibliography in thead |
| nat_comms_2 | 81475 | 76637 | 0.941 | low | F3 (title in Abstract); zero tables detected — Tier B |
| sci_rep_1 | 56139 | 65918 | 1.174 | | F3 (worst — title fully in Abstract) |

---

## Key files

| Path | Role |
|---|---|
| [`docs/TRIAGE_2026-05-10_corpus_assessment.md`](./TRIAGE_2026-05-10_corpus_assessment.md) | **The canonical work queue. Read this first.** |
| [`docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/splice_spike.py) | The standalone the user reviews. Most fixes go here. ~3000 lines. |
| [`docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/test_splice_spike.py) | 203 unit tests at HEAD. Must stay green after every change. |
| [`docs/superpowers/plans/spot-checks/splice-spike/outputs/`](./superpowers/plans/spot-checks/splice-spike/outputs/) | 7 OLD-corpus regenerated `.md` outputs. |
| [`docs/superpowers/plans/spot-checks/splice-spike/outputs-new/`](./superpowers/plans/spot-checks/splice-spike/outputs-new/) | 19 new-corpus regenerated `.md` outputs. |
| [`docpluck/extract_layout.py`](../docpluck/extract_layout.py) | **For F3 title rescue (iter-28).** pdfplumber-based layout channel with per-character font/size/bbox. |
| [`docpluck/tables/captions.py`](../docpluck/tables/captions.py) | Library-level caption regex (Nature/IEEE broadening lives here — see B2 in triage). |

---

## Critical hard rules (still in force)

All previous-iteration rules from `LESSONS.md` PLUS:

- **Don't swap pdftotext for pymupdf etc.** L-001 / L-003. AGPL license issue. pdfplumber is the only allowed PDF library alongside pdftotext.
- **Don't use pdftotext `-layout`.** L-002. Causes column interleaving.
- **Always normalize U+2212 → ASCII hyphen.** L-004.
- **Test on APA / replication papers.** L-005. ML-engineering papers mask real failures.
- **Char ratio drop is not always content loss.** Iter-22 / iter-25 / iter-26 / iter-27 all dropped char counts on multiple papers; word-token diff confirmed they were tag/banner/footer tokens only. Always cross-check with `\b\w+\b` counter.
- **Conservative > canonical when uncertain.** Iter-20 first dropped hyphens; reverted because real compounds eroded.
- **Walk-back guards matter.** Iter-21 attached stars to `Ref.` text-anchor rows; iter-24 fixed with text-anchor block + forward-attach.
- **HTML placeholders survive escaping** (`_SUP_OPEN`, `_MERGE_SEPARATOR`).
- **Subagents that render PDFs sometimes fail silently** with 0-byte outputs — always verify file sizes after subagent batch rendering.
- **The corpus is large enough to find new patterns each iteration.** New issues that match no existing rule appear regularly. Surface them in the triage as you find them.

---

## What success looks like

A reader should be able to read a rendered .md file from top to bottom without bumping into:
- Banner junk (✅ resolved iter-25)
- TOC content (✅ resolved iter-26)
- Page-footer text mid-body (✅ resolved iter-27)
- Title nested under Abstract (⏳ iter-28)
- Multi-word headings split mid-phrase (⏳ iter-29)
- Sidebar Key-Points content inlined as body (⏳ iter-30)
- Body sentences split across page boundaries (⏳ future C3)

The user reads each .md file in a markdown viewer — what they see is what we're optimizing. Char ratios and word counts are necessary regression checks, not the end goal.

---

## One-line summary for the next session

> Read TRIAGE.md. Run pytest (203). Pick top-3. Iterate. Periodically broad-read 8-10 outputs. Update TRIAGE. Surface diminishing returns to the user. Optimize for outcome, not for iteration count.
