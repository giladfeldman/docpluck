# Table Extraction Experiments — Side-by-Side Comparison

**Date:** 2026-05-09
**Goal:** Pick a viable approach for extracting cell-structured tables from APA PDFs.
**Test PDFs:** korbmacher_2022_kruger.pdf Table 1 (best case: clean 4×8 stats matrix), ziano_2021_joep.pdf Table 1 (worst case: landscape 2-tables-side-by-side).

## Summary table

| Option | Tool | korbmacher | ziano | New dep? | Single-extractor? | Notes |
|---|---|---|---|---|---|---|
| **A** | pdfplumber `extract_tables(text strategy)` | ❌ Bad — 3 cols, "Usingamouse" merged | ❌ Unusable | No | No | Subagent crashed twice with API overload but produced output; quality is the worst of the four. |
| **B** | pdfplumber `extract_words` + custom column-cluster | 🟡 OK — 5 cols, header garbled, asterisks misplaced | ❌ Side-by-side detection wrong | No | No | Most algorithmic effort, weakest result outside best case. |
| **C** | pdfminer.six word-bbox (replaces pdfplumber for cells) | ✅ Near-perfect | 🟡 Partial — data clean, rotated-margin "I. Ziano et al." creates spurious 15th column | No (pdfminer.six is already a transitive dep) | **Yes for cells**; pdfplumber still helps for detection on complex layouts | Closest to your "one extractor" preference. **Note:** the spec called for `pdftotext -bbox-layout`, but the installed `pdftotext` is xpdf v4.00 (no `-bbox-layout` flag). pdfminer.six is a functional analog. |
| **D** | Camelot `flavor="stream"` | ✅ Near-perfect — accuracy 97.7 | ✅ Surprisingly clean — 52×14 single wide table, both sub-tables merged but values intact | **Yes** (`camelot-py[cv]`) | No — Camelot is yet another extractor on top of pdftotext + pdfplumber | No Ghostscript needed (stream flavor only). Best raw quality but adds a third extractor dependency, contradicting your stated preference. |

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

## Recommendation

If you weigh **architecture (single extractor)** more, **C is the answer**. We accept the "rotated margin text creates spurious column" failure mode on landscape pages, which is fixable with a narrow-column-filter post-processor.

If you weigh **raw output quality** more, **D is the answer**. Camelot stream flavor is best-in-class for stats tables and works out-of-the-box without per-paper tuning, at the cost of a new dependency.

A hybrid is also possible: use **C for the common case (whitespace tables, like the entire APA corpus)** and **fall back to D only when we detect the failure mode**. That defers the new-dependency cost to the rare case. But hybrids are hard to justify and add complexity.

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
