# Table Extraction Experiments — Side-by-Side Comparison

**Date:** 2026-05-09
**Goal:** Pick a viable approach for extracting cell-structured tables from APA PDFs.
**Test PDFs:** korbmacher_2022_kruger.pdf Table 1 (best case: clean 4×8 stats matrix), ziano_2021_joep.pdf Table 1 (worst case: landscape 2-tables-side-by-side).

## Summary table

| Option | Tool | korbmacher | ziano | New dep? | Single-extractor? | Notes |
|---|---|---|---|---|---|---|
| **A** | pdfplumber `extract_tables(text strategy)` | ❌ Bad — 3 cols, "Usingamouse" merged | ❌ Unusable | No | No | Subagent crashed twice with API overload but produced output; quality is the worst of the five. |
| **B** | pdfplumber `extract_words` + custom column-cluster | 🟡 OK — 5 cols, header garbled, asterisks misplaced | ❌ Side-by-side detection wrong | No | No | Most algorithmic effort, weakest result outside best case. |
| **C** | pdfminer.six word-bbox (replaces pdfplumber for cells) | ✅ Near-perfect | 🟡 Partial — data clean, rotated-margin "I. Ziano et al." creates spurious 15th column | No (pdfminer.six is already a transitive dep) | **Yes for cells**; pdfplumber still helps for detection on complex layouts | Closest to single-extractor preference. **Note:** spec called for `pdftotext -bbox-layout`, but installed `pdftotext` is xpdf v4.00 (no flag). pdfminer.six is a functional analog. |
| **D** | Camelot `flavor="stream"` | ✅ Near-perfect — accuracy 97.7 | ✅ Surprisingly clean — 52×14 single wide table, both sub-tables merged but values intact | **Yes** (`camelot-py[cv]`) | No — Camelot is another extractor | No Ghostscript needed (stream flavor only). Best raw quality. |
| **E** | **Real Poppler `pdftotext -bbox-layout`** + custom row/col clustering | ❌ Worst — entire row groups merged ("Easy Using a mouse Driving Riding a bicycle Saving money" all in one cell) | ❌ Multi-line study labels merged; row groups collapsed | Yes (Poppler binary) | Closest in spirit (single tool gives both text and word-bboxes) | Poppler installed cleanly, raw word-bbox data is the highest-quality input of any option, but the row-clustering algorithm is hard to get right. The subagent's implementation merged consecutive rows aggressively. **Theoretically best foundation, hardest to implement well.** Camelot has already solved this problem. |

## Headlines

- **A is dead.** Even when it ran, output was the worst.
- **B underperforms C and D** on both test cases. The custom word-cluster algorithm is sensitive to multi-line cells and side-by-side tables.
- **C and D both produce production-quality output on the simple case.** The difference between them is on the landscape side-by-side case AND on architecture.
- **D wins on raw quality**: cell content is cleaner on ziano (the wide-table merge is a known limitation Camelot acknowledges, but the data is recoverable). Camelot is meaningfully better than the other three for simple stats tables.
- **C wins on architecture**: closest to your "one extractor" preference. pdfminer.six can replace pdfplumber for cell extraction; pure-pdfminer detection works for simple whitespace tables but pdfplumber is still needed for landscape/complex layouts.

## What you should look at

Each option has 2–4 files. Recommended review order:

1. **C's korbmacher** ([`option-c/korbmacher_table1.md`](option-c/korbmacher_table1.md)) and **D's korbmacher** ([`option-d/korbmacher_table1.md`](option-d/korbmacher_table1.md)) — both are near-perfect. Compare them. Is there a meaningful quality difference?
2. **C's ziano** ([`option-c/ziano_table1.md`](option-c/ziano_table1.md)) and **D's ziano** ([`option-d/ziano_table1.md`](option-d/ziano_table1.md)) — both have structural problems, different ones. Which failure mode is easier to live with / post-process?
3. **C's notes** ([`option-c/notes.md`](option-c/notes.md)) — the architectural discussion is the most thorough. Particularly section "How viable is pure-pdftotext-only architecture?"
4. **D's notes** ([`option-d/notes.md`](option-d/notes.md)) — Ghostscript caveat (turns out not needed for stream), Camelot install footprint.

If you want to see the failure modes:
- **A's outputs** show what pdfplumber-text-strategy produces — instructive for "why this approach is rejected."
- **B's notes** ([`option-b/notes.md`](option-b/notes.md)) document why custom word-clustering breaks on side-by-side tables (the bimodal-gap algorithm is confounded by continuation rows).

## Recommendation (post-E)

**D wins.** Reasoning:

- Real Poppler `pdftotext -bbox-layout` (option E) provides the cleanest *raw input* of any option, but extracting cell structure from word bboxes requires nontrivial row/column clustering. The subagent's E implementation got it wrong — entire row groups collapsed into single cells. To beat D with E, we'd need to invest weeks porting algorithms that Camelot has already implemented. That's not a good trade.
- C is acceptable but its rotated-margin failure mode on landscape pages requires a custom post-processor we'd have to maintain.
- D works out-of-the-box with no per-paper tuning, no manual column-detection algorithm, no rotated-text post-processor. Accuracy 97.7 on korbmacher and 99.2 on ziano (Camelot's self-reported metric).

**Tradeoff accepted:** Camelot is a new dependency that doesn't satisfy the original "one extractor" goal. The user has explicitly accepted this: dropping pdfplumber (described as "horrible") and adding Camelot (described as "excellent"). Net dependency count stays the same, quality improves dramatically.

## What about pure pdftotext-bbox-layout in the long term?

Even after picking D for now, the E experiment confirmed:
- Real Poppler `pdftotext -bbox-layout` is installable on Windows.
- The HTML output format gives word-level bboxes as advertised.
- Building a robust cell extractor on top would take weeks of algorithm work.

A future direction (out of scope for this iteration): re-implement Camelot's stream-flavor algorithm against `pdftotext -bbox-layout` HTML output. That gives us the single-extractor architecture without depending on Camelot. But this is a multi-week effort and the value-add over Camelot is purely architectural (no quality gain). Not worth doing now.

## Critical reminder

The spec [`2026-05-08-unified-extraction-design.md`](../../../specs/2026-05-08-unified-extraction-design.md) constrains us to **pdftotext + pdfplumber, period** (license + lessons-learned constraints). Adopting either C (pdfminer.six) OR D (camelot-py) is a **spec amendment**. The spec needs updating before phase 1 starts. Both pdfminer.six and camelot-py are MIT-licensed and compatible with the SaaS use case, so the constraint is policy, not technical.

## Files

```
experiments/
├── COMPARISON.md         (this file)
├── option-a/
│   ├── option-a.py
│   ├── korbmacher_table1.md
│   └── ziano_table1.md
│   (no notes.md — subagent crashed)
├── option-b/
│   ├── option-b.py
│   ├── korbmacher_table1.md
│   ├── ziano_table1.md
│   └── notes.md
├── option-c/
│   ├── option-c.py
│   ├── korbmacher_table1.md
│   ├── ziano_table1.md
│   ├── sample-pdftotext-bbox.html
│   └── notes.md
└── option-d/
    ├── option-d.py
    ├── korbmacher_table1.md
    ├── ziano_table1.md
    └── notes.md
```
