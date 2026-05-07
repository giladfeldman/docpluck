# Handoff — Sections strict-iteration validation

**For:** Future Claude session picking up sections-quality work after v2.0.0 release.
**From:** Session that shipped v2.0.0 (combined structured-extraction + section-id surgical fix).
**Date created:** 2026-05-07.
**Branch:** `main` (post-release; fresh branch off main is recommended for any code changes).

---

## 1. Context — what shipped, what's still wrong

**v2.0.0 already on production.** Library tagged + pushed; PDFextractor app pinned at `@v2.0.0` and redeployed (Vercel + Railway). Sections work end-to-end on the 5-paper APA corpus that was used during the surgical-fix iteration:

- `ip_feldman_2025_pspb.pdf`, `chen_2021_jesp.pdf`, `efendic_2022_affect.pdf`, `chan_feldman_2025_cogemo.pdf`, `chandrashekar_2023_mp.pdf` — all return canonical sections without garbage `unknown` spans.

**The problem the user surfaced after release:** sections still has too many mistakes when run on a wider PDF corpus. The "ok" bar used during the v1.6.1 surgical-fix iteration was too loose ("meh, ok"), letting through papers where label/boundary/contamination errors are still common enough that real users would ditch the feature.

**The user's call:** raise the bar, run iterative testing across more styles, stop only when **2 papers from each style** clear the strict bar. Last time we stopped after one paper grade clean on first try; that's not enough.

The user also flagged a parallel UX concern: the webapp has separate `/extract` and `/sections` pages. They want a **single interface** that exposes sections + normalization together — a request I made notes about during the v1.6.1 brainstorm but never addressed. **Parallel track, not part of this iteration.** Flag it back to the user when this iteration finishes.

---

## 2. The strict bar — proposal

Last time's bar (too loose):
- No `unknown` span > 10% of doc
- All canonical sections "present"
- "Section bodies don't contain page running headers"
- "Subheadings field surfaces obvious in-section structure"
- "No section truncated to <50 chars unless that's actually all there is"

That's a **suite-level** bar; it accepted papers where individual sections had the right label but wrong boundary, or partial contamination, or missing subsections, etc.

**Proposed strict bar — per-section grading rubric.** For each section in the output, the AI grader (you, reading the PDF + the section JSON) assigns one of four marks:

| Mark | Meaning |
|---|---|
| ✅ **correct** | Label right; boundary within ±1 paragraph of ground truth; body free of headers/footers/footnotes/cross-section contamination; subheadings populate iff source has them |
| ⚠️ **minor issue** | Label right and boundary roughly right, but ONE of: <±2-paragraph boundary slip, missing 1 subheading, 1 stray header line in body, <100 chars of cross-section bleed |
| ❌ **major issue** | Label right but boundary very wrong (>3 paragraphs), OR multiple minor issues combined, OR subheadings field has table-cell garbage instead of real subsections, OR body contains a clearly-different-section's content |
| 🚫 **wrong** | Label wrong, OR section duplicates content from another section, OR section is empty/single-line when source has substance |

**Pass criterion (per paper):**

- **All sections must be ✅ or ⚠️.** ZERO ❌ or 🚫.
- **At least 80% of sections must be ✅** (no more than 20% ⚠️).
- **No mid-doc unknown span >1% of doc length.** (Title-block prefix unknown is fine if <2%.)
- **Canonical-section recall = 100%.** Every canonical section the paper visually contains MUST be detected. No "structural" excuses for missed Abstract / Introduction / References — if a human reader can spot it, the system has to.

**Convergence criterion (across corpus):**

Stop iteration when **2 papers from each style** pass on **first try** without code changes. That's the signal the heuristics generalize. Approximately 8 styles × 2 = **16 first-try-clean papers minimum** before declaring done.

> **If a style only has 5 PDFs total and 3 of them keep failing,** that's the signal that style is genuinely hard for the current heuristics — STOP and report back rather than keep iterating. The user prefers "ditch this style for v2.1" over "keep iterating on diminishing returns."

---

## 3. The corpus — `PDFextractor/test-pdfs/`

Style breakdown:

| Style | PDFs | Path |
|---|---|---|
| `apa` | 5 | `C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor\test-pdfs\apa\` |
| `ama` | 5 | same parent, `ama/` |
| `aom` | 10 | `aom/` |
| `asa` | 5 | `asa/` |
| `harvard` | 5 | `harvard/` |
| `ieee` | 5 | `ieee/` |
| `nature` | 10 | `nature/` |
| `vancouver` | 5 | `vancouver/` |

**8 styles, ~50 PDFs total.** Plus the 5 APA papers from the v1.6.1 iteration are already known-good; they don't count toward the new "2 first-try-clean per style" budget but are useful as regression baselines.

---

## 4. Process — per-paper iteration

For each style, in this order: `apa` → `ieee` → `nature` → `vancouver` → `aom` → `ama` → `asa` → `harvard` (psych first, hardest layouts last).

### Per-paper procedure

1. **Run the sectioner** on the PDF. Dump JSON.

   ```python
   from pathlib import Path
   from docpluck.sections import extract_sections
   pdf = Path("<absolute_path>").read_bytes()
   doc = extract_sections(pdf)
   for s in doc.sections:
       print(f"{s.label!r:30s} chars=[{s.char_start:6d}..{s.char_end:6d}] len={len(s.text):6d} subhead={list(s.subheadings)[:3]}")
   ```

2. **Read the PDF** (`Read` tool with `pages` parameter, page-ranged for long papers — typically pages 1-3 cover title/abstract/intro start, then a chunk for body, then last 2 pages for references/back matter).

3. **Grade per section** against the rubric in §2. Write the grading explicitly:

   ```
   [00] unknown (title block, 622 chars)        ✅ correct
   [01] abstract  (1075 chars, "Abstract")       ✅ correct
   [02] keywords (236 chars)                     ✅ correct
   [03] introduction (18058 chars, "Introduction") ⚠️ minor: missed "Background" subheading
   [04] methods (20101 chars, "Method")          ✅ correct
   ...
   ```

4. **If all ✅ or ⚠️ AND ≥80% ✅ AND no >1% mid-doc unknowns AND 100% recall** → paper PASSES. Increment that style's pass-counter. If pass-counter for that style reaches 2 → mark style "converged" and skip remaining papers in that style.

5. **If ANY section is ❌ or 🚫** → paper FAILS. Diagnose, fix the heuristic in `docpluck/sections/`, run regression suite (`pytest tests/test_sections_*.py -q`), re-run on this paper. Repeat until paper passes. Then move to the next paper in the same style.

6. **Stop the entire iteration** when every style has 2 first-try-clean passes, OR a style has used up its PDFs without converging (escalate to user).

### Tracking sheet

Maintain a markdown table during iteration:

```
| Style | PDFs tried | First-try clean | Notes |
|---|---|---|---|
| apa | 1/5 (ip_feldman) | 1/2 | ⚠️ Background subheading missed |
| apa | 2/5 (chen) | 1/2 | ❌ huge abstract (no Introduction heading); needs intro-implicit handling |
| ... |
```

Commit this sheet as a working doc in `docs/superpowers/plans/2026-05-07-sections-strict-iteration-progress.md` so progress is durable across sub-sessions.

---

## 5. Likely issues to expect (from prior diagnosis)

**Already-known limitations from v2.0.0:**

- **Papers with no `Introduction` heading** (some JESP papers go from Abstract directly to `6.2. Method`) → abstract span is huge, swallowing intro.
- **Meta-analyses with embedded per-study summaries** → unusual section ordering.
- **`subheadings` field is empty by design.** Smart list-vs-heading discrimination was deferred to v2.1.

**Style-specific patterns to watch for:**

- **IEEE / Vancouver** — numbered headings (`1. Introduction`, `2. Methods`, `2.1 Participants`). Current text annotator strips leading numbers via `\d+(\.\d+)*\.?[ \t]+` prefix in regex — should still match, but verify.
- **Nature** — heavy use of front-matter (`Editorial summary`, `Subjects` list, ORCID iDs, supplementary references). Front-matter heuristics may misfire.
- **AOM / ASA / Harvard / AMA** — varied heading styles; some use `BACKGROUND` / `METHODS` ALL-CAPS, some use `Method` Title Case. Taxonomy already covers both via `_normalize_heading` lowercase fold.
- **Some Nature/Science papers** — section names in side margins or header bars that pdfplumber may treat as body. Less applicable now that we're on `extract_pdf` (pdftotext), but watch for column-extraction artifacts.

**Heuristic levers in `docpluck/sections/`:**

- `taxonomy.py` — add/remove canonical heading variants. v1.6.1 already removed `procedure/procedures`, `study design`, `experimental design`, `methodology`, `summary`. Be careful not to over-trim.
- `annotators/text.py` — three passes (canonical-line-isolated-or-Capital-body, canonical-after-blank-line, line-isolated heading-shape). Knobs: blank-line predicate strictness, Title-Case post-filter, table-cell-detection threshold (currently 5 chars).
- `core.py` — `_resolve_label` (canonical-only rule), adjacency-coalesce (gap < 100 chars), `_NO_TRUNCATE` (currently all canonical labels).

---

## 6. Tools / no API calls

User constraint from v1.6.1: **no Anthropic API calls; everything runs through Claude Code Max subscription.** The AI grader IS the session running, reading the PDF with the `Read` tool. Same as last time.

Before starting, run:

```bash
cd C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck
git log --oneline v2.0.0..HEAD       # any post-release commits to be aware of
git status                            # working tree state
python -m pytest tests/test_sections_*.py -q  # baseline green
```

If the regression suite isn't green at the start, fix that BEFORE starting iteration — you can't tell whether iteration changes pass or fail without a clean baseline.

---

## 7. Bar tuning — escape valves

The strict bar in §2 is a **starting point**. If after running 5+ papers it turns out the bar is unrealistic (e.g., no paper passes because section boundaries are inherently fuzzy), tune carefully:

1. **Don't lower the recall floor.** 100% canonical-section recall is non-negotiable — if Methods is in the paper, the system MUST find it.
2. **Boundary slip tolerance can flex.** ±1 paragraph might be unrealistic for two-column papers where pdftotext reading-order has natural fuzz. ±3 paragraphs is OK if the section content is predominantly correct.
3. **Subheadings field can be ignored entirely** for v2.1 acceptance. The v2.0.0 release shipped with subheadings empty by design.

What CANNOT be lowered:
- All canonical sections detected (recall = 100%).
- No `wrong` (🚫) sections.
- No mid-doc unknown >5% of doc.

If the bar becomes "all ✅ or ⚠️ with ≤2 ⚠️ per paper", that's still meaningful — better than v1.6.1's "meh, ok."

---

## 8. Webapp consolidation — parallel track

Separate from sections quality: the user wants a **single interface** at `/extract` (or new `/document`) that shows sections AND normalization together, instead of separate `/extract` and `/sections` pages.

Don't pursue in this iteration — flag back to user when sections iteration converges. Ideas to brainstorm with the user when that comes up:

- One landing page: upload PDF → see normalized text WITH section gutter showing detected boundaries.
- Toggleable section view: click a section's heading in the gutter to scroll/highlight.
- Export buttons: "copy abstract", "download references as BibTeX", etc.
- Future: subheadings as nested foldable list (once v2.1 populates them).

Don't implement until user confirms the design direction. Brainstorm first (use `superpowers:brainstorming`).

---

## 9. Hand-off mechanics — how to start

1. **New session begins.** First action: read this file (`docs/HANDOFF_2026-05-07_sections_strict_iteration.md`).
2. **Confirm baseline.** Run the three sanity commands in §6.
3. **Confirm the strict bar with the user** before iteration starts. The proposal in §2 is a starting point; the user may refine.
4. **Create the progress sheet** at `docs/superpowers/plans/2026-05-07-sections-strict-iteration-progress.md` (gitignored if user doesn't want it tracked, but committed is recommended for durability across sub-sessions).
5. **Start with `apa/` directory.** First paper: pick one NOT in the v1.6.1 corpus (the 5 from v1.6.1 are known-good; they don't count toward fresh first-try-clean budget). The APA dir has 5 PDFs; the v1.6.1 corpus used `chan_feldman_2025_cogemo.pdf`, `chandrashekar_2023_mp.pdf`, `chen_2021_jesp.pdf`, `efendic_2022_affect.pdf`, `ip_feldman_2025_pspb.pdf` — so APA might already be exhausted and the new session should pick a different style first or check if there are other APA PDFs added since.
6. **Iterate per §4.** Track in the progress sheet. Commit fixes with descriptive messages.
7. **When converged or escalation needed, report to user** with the progress sheet and a summary of what changed.

---

## 10. Known files / commits to be aware of

**Library v2.0.0 release commits (post v1.6.0 baseline):**

- Tag: `v2.0.0` at `6adf13f` (`chore: gitignore v1.6.1 surgical-fix brainstorm artifacts`)
- `ec53afe` — regression test for top-level v2.0 exports + lessons.md
- `95ca48c` — Cell top-level export fix (caught by /ship Phase 3)
- `cc54844` — merge of `feat/table-extraction` (containing both the structured-extraction work and the section-id surgical fix)
- `593663f` — version bump to 2.0.0 + CHANGELOG reconciliation

**Section-relevant code (v2.0.0):**

- `docpluck/sections/__init__.py` — public API; PDF path uses `extract_pdf` + `normalize_text(academic)` (NOT `extract_pdf_layout`)
- `docpluck/sections/core.py` — `partition_into_sections` with adjacency-coalesce and disabled boundary truncation
- `docpluck/sections/taxonomy.py` — current canonical map; `procedure`/`study design`/`experimental design`/`methodology`/`summary` already removed
- `docpluck/sections/annotators/text.py` — three-pass detector; canonical at line-isolated, canonical-after-blank-line, table-cell filter
- `docpluck/sections/types.py` — `Section.subheadings: tuple[str, ...] = ()`

**Regression test files (must stay green):**

- `tests/test_sections_*.py` (~25 files)
- `tests/test_v2_top_level_exports.py` — Cell export guard
- `tests/test_d5_normalization_audit.py` — 153 normalize tests

---

## 11. Project memory

Already in `~/.claude/projects/.../memory/MEMORY.md`:
- `*.pdf` gitignore rule (manifest-with-skip pattern).

Consider adding when this iteration converges:
- Strict-bar definition that stuck (so future iterations don't re-litigate it).
- Any style that proved structurally hard (e.g., "Nature papers without canonical Introduction heading require the implicit-Introduction heuristic, deferred to v2.1").

That's it. Read this, confirm bar with user, iterate, report back. Good luck.
