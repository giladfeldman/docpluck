# Corpus Assessment & Triage — 2026-05-10

**Last update:** 2026-05-10 after iter-31 (F6 residual + title-rescue tier-skip for PMC papers) landed in iteration-8 session. 231 tests passing. **All 26 papers now open with `# Title` as line 1.**

**Scope:** AI-verification read of 26 .md outputs in `docs/superpowers/plans/spot-checks/splice-spike/outputs{,-new}/`. Corpus reduced from 27 → 26 papers: nathumbeh_2 removed (was Nature Hum Behav supplementary materials, not an article — user decision 2026-05-10).

## Iteration log
- ✅ **iter-23** `6e8d266` — caption-fold across consecutive lines (FIGURE/TABLE N + tail).
- ✅ **iter-24** `768a942` — forward-attach for orphan marker rows (social_forces stars).
- ✅ **iter-25 / F6 RESOLVED** `fca6f61` — banner / running-header strip in header zone. 16 papers cleaned. Document START is now title or first author block instead of HHS / arXiv / Cite this article / mangled-DOI / manuscript-ID gibberish.
- ✅ **iter-26 / F5 RESOLVED** `3b24041` — TOC dot-leader strip in head zone (+ false-promoted-heading drop). General-purpose; main beneficiary (nathumbeh_2) was removed from corpus per user direction, but function stays in case other supplementary docs enter.
- ✅ **iter-27 / F1 RESOLVED (cheap variant)** `3b24041` — page-footer line strip across whole document. Page-N markers, JAMA `October 27, 2023 X/13` footers, `(continued)` page-break markers, `Corresponding Author:` lines, bare email lines, JAMA citation/category running headers, `Open Access. ... (Reprinted)` compound, `© YYYY` lines, `aETH Zurich` affiliation footnotes, JAMA Visual Abstract sidebar all dropped. 13+ papers visibly cleaner. Big visible-quality win: jama_open_1 abstract → trial registration → introduction now flows clean. The user's headline complaint about page-footer interleave is RESOLVED for the cheap-variant scope; the underlying sentence-stitching at page boundaries (C3 cost) is unfixed but the JUNK between halves is gone.
- ✅ **iter-28 / F3 RESOLVED** (this session) — layout-channel title rescue. `_compute_layout_title` reads pdfplumber per-character font sizes on page 1, identifies the dominant largest-font multi-line block in the upper 60%, and reconstructs its text via `extract_words` (or a char-level absolute-gap fallback for tight-kerned PDFs like JAMA / AOM). `_apply_title_rescue` then either UPGRADES an existing in-place plain-text title to `# Title` (korbmacher, chen, demography pattern) or PREPENDS `# Title` when the title was buried inside `## Abstract` (sci_rep_1, nat_comms_1/2, ar_royal_society_rsos_140066) or missing entirely. 17 of 26 papers now open with a proper `# Title` h1; the remaining 9 either have a banner above the title (separate F6 residual) or use a title font below the 12pt confidence threshold (demography_1, jmf_1 — title is at line 1 already, just not h1-marked).
- ✅ **iter-29 / F2 (compound-heading tail) RESOLVED** (iter-7) — `_merge_compound_heading_tails` reattaches orphaned multi-word JAMA structured-abstract heading tails. Currently curated to `CONCLUSIONS AND RELEVANCE` (the only real-world split observed). jama_open_1 / jama_open_2 fixed: `## CONCLUSIONS\n\nAND RELEVANCE This trial found...` → `## CONCLUSIONS AND RELEVANCE\n\nThis trial found...`.
- ✅ **iter-31 / F6 residual RESOLVED + title-rescue tier-skip** (iter-8) — two complementary fixes that together get all 26 papers to a `# Title` line-1. (a) Extended `_HEADER_BANNER_PATTERNS` with curated journal-name lines (Journal of Economic Psychology / Cognition and Emotion / Journal of Experimental Social Psychology / "Journal Name, Vol. N, No. M, Month YYYY, pp. PP-PP" Sage-style cite-line / "Journal Name, YYYY, V, PP-PP" Oxford-journals format / "https://doi.org/... Advance access publication date..."). (b) Added `_BANNER_SPAN_PATTERNS` + `_is_banner_span_text` to pre-filter banner spans BEFORE the dominant-font selector inside `_compute_layout_title`; relaxed the single-span title threshold to ≥14pt. PMC papers (ieee_access_2, demography_1, jmf_1) that previously had HHS Public Access at 22pt blocking title rescue now find the 14pt title below. Elsevier-template papers (ziano_2021_joep, chen_2021_jesp, ar_apa_j_jesp_2009_12_010) that had the bare journal name at 13.9pt above a 13.4pt title now skip the banner and pick the title. 7+ papers' document-start cleaned up cosmetically.

**Method:** three parallel agent reads of paper subsets (Nature+IEEE / APA+AOM / JAMA+ASA+Chicago+Harvard) plus my own targeted re-reads of `sci_rep_1`, `am_sociol_rev_3`, `chen_2021_jesp`, `jama_open_1`, `nathumbeh_2`. Categorical labels per issue (SECTION, TITLE, BODY, JUNK, etc.).

The user's headline complaint — *"the Nature .md is basically useless. There's an issue with the keywords appearing at page bottom one in between, and the parser picking the next page as being under the keywords"* — is **confirmed** and turns out to be the same root cause as several other large-impact bugs (running headers, copyright lines, affiliations, "(continued)" markers, sidebar text leaking into body). It's a structural issue with how page-bottom non-body content is interleaved into the body text stream.

Almost everything we've worked on for the past 24 iterations has been **table-rendering** improvements. The biggest remaining issues are at the **section / page-flow / non-body-junk** layer — a different layer of the pipeline.

---

## The 8 dominant failure modes

Ranked by how many papers they hit and how badly. Severity scale:

- **S0 — content disappears or becomes unreadable.** A reader cannot recover the paper.
- **S1 — major usability damage.** Section structure wrong, headings nested into wrong parents, body stitched onto Keywords or Abstract. Reader can read but cannot navigate.
- **S2 — visible but cosmetic.** Page numbers / copyright lines mid-text; reader's eye snags but content is intact.
- **S3 — minor.** Single-paper edge cases.

Cost scale:

- **C1 — 1 spike iteration** (~1 hour, isolated function in `splice_spike.py`)
- **C2 — 2-3 iterations** (touches multiple passes, needs design choice)
- **C3 — library-level structural** (changes to `docpluck/sections/` or `docpluck/normalize.py`, possible new abstraction)
- **C4 — needs an architectural change** (new pipeline pass / new data input)

| # | Failure mode | Severity | Papers affected (visible) | Cost | Notes |
|---|---|---|---|---|---|
| ~~F1~~ | ~~**Page-footer interleave** (cheap variant)~~ | ~~S1~~ | ~~13 papers~~ | ~~C3 / C2 cheap~~ | **RESOLVED iter-27** (`3b24041`). Curated `_PAGE_FOOTER_LINE_PATTERNS` line-level strip. JUNK between sentence halves removed. The structural fix to RE-STITCH the body sentence across page boundaries is unfixed (deferred to a future C3 iter that needs page-bbox awareness). |
| **F2** | **Section heading appears AFTER its content**: `## Introduction` printed at line N+5 while the introduction's first paragraph already started at line N. Caused partly by F1 (page footer pushed heading down past content — now fixed) and by section-detector misordering. The compound-heading split (`CONCLUSIONS / AND RELEVANCE`) is RESOLVED at iter-29. | **S1** | am_sociol_rev_3 (still — `## Introduction` between body sentence halves), sci_rep_1, amc_1 (1980s section), nat_comms_2 | **C2** | Compound-heading sub-bug RESOLVED iter-29 (`_merge_compound_heading_tails`). Remaining F2 cases are pure section-detector misorderings — library-level, deferred. |
| ~~F3~~ | ~~**Title + authors dumped into Abstract section**~~ | ~~S1~~ | ~~sci_rep_1, nat_comms_1, nat_comms_2, ar_royal_society_rsos_140066~~ | ~~C2~~ | **RESOLVED iter-28** (this session). Layout-channel pre-pass (`_compute_layout_title` + `_apply_title_rescue`) reads pdfplumber font sizes on page 1, finds dominant largest-font multi-line block in upper 60%, and emits `# Title` either by upgrading an existing in-place title block or prepending if the title was swept under `## Abstract`. Char-level fallback handles tight-kerned PDFs (JAMA, AOM). 17 papers now open with a proper `# Title` h1. |
| **F4** | **Sidebar / Key Points / Visual Abstract content interleaved into body**: JAMA-style "Key Points Question/Findings/Meaning" boxes get inlined into the abstract. "Visual Abstract" / "Supplemental content" labels appear as body. | **S1** | jama_open_1, jama_open_2 (sidebar labels now mostly stripped by iter-27; KEY POINTS box content still inlined) | **C2** | Layout-channel-aware: these boxes have their own bbox column. Could be detected by reading-order anomaly (text from a different x-column wedged between body lines) using the existing `extract_pdf_layout` channel. |
| ~~F5~~ | ~~**TOC dot-leader lines parsed as headings / body fragments**~~ | ~~S1~~ | ~~nathumbeh_2 (removed from corpus), nat_comms_1~~ | ~~**C1**~~ | **RESOLVED iter-26** (`3b24041`). Function strips TOC paragraphs containing `_{3,}` runs in head zone, also drops false `## Headings` immediately preceding TOC paragraphs. nathumbeh_2 main beneficiary was dropped from corpus. |
| ~~F6~~ | ~~**Running headers / journal banners at the start of the doc**~~ | ~~S2~~ | ~~16 papers~~ | ~~**C1**~~ | **RESOLVED iter-25** (`fca6f61`). |
| **F7** | **DOI / manuscript-ID character-mash**: `DhttOpsI::/1/d0o.i1.o1rg/710/.01107073/010202314222442142152353226688` — pdftotext reading-order corruption when DOI bbox is interleaved with another text run. | **S2** | am_sociol_rev_3 | **C2** | Specific to bicolumn-publisher-template overlap. Hard to fix in a generic way — narrowest fix is to recognize "looks like a corrupted DOI" by digit/letter density and strip the line entirely. Affects only 1-2 papers. |
| **F8** | **Numbered ToC headings printed without a preceding line**: `1. Hindsight bias`, `2. Reasons for hindsight bias` rendered as flat body text rather than `### 1. Hindsight bias`. | **S2** | chen_2021_jesp, korbmacher_2022_kruger (visibly), most replication papers | **C2** | Section detector doesn't recognize the journal's own numbered subsection style. Could be promoted to `###` headings with a pattern + paragraph-position guard. |

---

## Tier-A (do these next)

The quickest wins with the biggest visible impact, all C1/C2 and content-preserving:

### A. F6 — banner / running-header strip pass (C1, ~1 iter)

Curated regex strip pass running BEFORE section detection. Removes:
- `^www\.\S+$` lines
- `^HHS Public Access$` (already partly handled but inconsistent)
- `^[A-Z][A-Z\s]+\| .+$` (`Original Investigation | Public Health`)
- `^© 20\d\d` lines
- `^https?://doi\.org/\S+$` lines
- `^\d{6,}\s+ASRXXX\d+` (ASR manuscript ID)
- `^Vol\.\s*\d+` (Nature volume strings)

Affects 8+ papers. Cosmetic but huge perceived-quality win. Easy to test.

### B. F5 — ToC dot-leader strip (C1, ~1 iter)

Recognize `Background _________________ 17` style lines and either drop or fence as `<!-- toc -->`. Works regardless of whether the ToC is at the top of a supplementary appendix (nathumbeh_2) or inline.

Pattern: `^\s*[A-Z].{2,80}?\s*[_\.…]{3,}\s*\d{1,3}\s*$`

### C. F1 — page-footer interleave (C3, the user's headline)

This is the **biggest** quality lift but also the **most expensive**. Approach options:

1. **Cheap first-pass (C2):** strip a curated set of page-footer line patterns regardless of position:
   - `^Corresponding Author:` (and the email line that usually follows)
   - `^[a-z]+@\S+\.\w+$` (bare email line)
   - `^\d+\s*Vol\.:` / `^\d+/\d+$` (page-N-of-M)
   - `^.+ \| https://doi\.org/\S+`
   - `^\(continued\)$`
   - `^[A-Z][A-Z\s]{15,}\d{4}.*\d+/\d+$` (JAMA Network Open footer)
   
   This won't fix the *underlying* sentence-splitting (page break still cuts mid-sentence) but it removes the *junk* between halves so the two halves at least sit adjacent.

2. **Real fix (C3):** layout-channel pass that strips the bottom N% of every page (where bbox.y > 0.92 × page_height) before pdftotext linearizes. This is the principled fix but needs to thread page geometry through `extract_pdf` (currently text-only).

Recommend **C2 first** as iter-25, then evaluate.

### D. F3 — title block rescue (C2, ~2 iter)

Pre-section-detection pass that:
1. Reads the layout-channel font sizes for page 1.
2. Identifies the largest-font multi-line block in the upper third → that's the title.
3. Identifies the next-largest line below it → authors.
4. Emits a `# Title` line at the top of the .md, then the authors line, then a blank, then continues with whatever section detection wanted to do.

This single fix removes the title-stuffed-into-Abstract problem on sci_rep_1, nat_comms_2, ar_royal_society_rsos_140066, and likely several more.

---

## Tier-B (consider after Tier A)

### E. F4 — sidebar/Key-Points box detection (C2-C3)

Layout-aware: identify a text box that is geometrically isolated from the body column (different x-column, same y-range). Preserve as a separate block (`<aside>` or `> Key Points:`) rather than inlining it into the body. Affects JAMA-style papers strongly.

### F. F8 — numbered subsection promotion (C2)

`^(\d+\.)\s+[A-Z][a-z]` at start of paragraph → promote to `### N. Title`. Add a guard for "list item that just happens to start a paragraph" by checking the next paragraph also looks like body, not a sibling list item.

### G. F2 residual — `CONCLUSIONS AND RELEVANCE` split

Tokenize known multi-word section headings as a unit before fragmenting on whitespace. JAMA structured-abstract sections: `OBJECTIVE`, `DESIGN, SETTING, AND PARTICIPANTS`, `INTERVENTIONS`, `MAIN OUTCOMES AND MEASURES`, `CONCLUSIONS AND RELEVANCE`.

---

## Tier-C (low priority / paper-specific)

- F7 — DOI character-mash (am_sociol_rev_3 only)
- ar_royal_society_rsos_140072 (already known as iter-22 leader-dot win, low ratio is filler-removal, not content loss)
- amle_1's missing 12 of 13 source tables (Camelot extraction issue, pre-existing)
- Several Camelot-driven table issues already on the existing Tier-B list (B1 multi-page table assembly, B2 Nature/IEEE caption format, B3 side-by-side merge)

---

## What table-rendering work has already done (and the diminishing returns warning)

Iters 1-23 have all targeted **inside-the-table** quality (header detection, sup attachment, caption echoes, leader dots, hyphen joins, cell merging). The 27-paper corpus shows we've hit diminishing returns there: most remaining table issues are now **library-level** (Camelot misses tables, multi-page assembly, Nature/IEEE caption format). The next 5-10 iterations on the spike are unlikely to materially change perceived quality.

The **per-iteration ratio of effort-to-perceived-quality** would now be MUCH higher if we shifted to F1 (page-footer interleave), F6 (banner strip), F5 (ToC strip), and F3 (title rescue). These are the 4 fixes that would change the user's first impression of the .md output — *especially* for Nature papers which were called out specifically.

---

## Concrete recommendation (next 2-3 iterations)

Updated 2026-05-10 after iter-25/26/27 landed:

1. ~~**Iter-25 (F6)**~~ ✅ DONE at `fca6f61`.
2. ~~**Iter-26 (F5)**~~ ✅ DONE at `3b24041`.
3. ~~**Iter-27 (F1 cheap variant)**~~ ✅ DONE at `3b24041`.

**Next candidates (priority-ordered by impact × cost):**

4. ~~**Iter-28 (F3) — title rescue from Abstract.**~~ ✅ DONE iter-7.
5. ~~**Iter-29 (F2 residual) — multi-word heading tokenization.**~~ ✅ DONE iter-7.
6. ~~**Iter-31 (F6 residual) — banner-strip extension for journal-name-only banners.**~~ ✅ DONE iter-8. All 26 papers now have `# Title` line 1.
7. **Iter-32 (F4) — sidebar Key-Points box detection.** Layout-aware: identify text-block geometrically isolated from the body column (different x-column at same y-range). Preserve as a separate `<aside>` block rather than inlining into the abstract. Affects jama_open_1/2 (Key Points "Question / Findings / Meaning" wedged between the CONCLUSIONS-body sentence halves). C2-C3, may need page-bbox awareness similar to F1 structural fix. **NEXT.**
8. **Iter-33 (F2 structural) — section-detector misordering for am_sociol_rev_3, amc_1, sci_rep_1.** Library-level; deferred until layout-channel page-bbox awareness lands.
9. **Iter-34 (F8) — numbered subsection promotion.** `^(\d+\.)\s+[A-Z][a-z]` at start of paragraph → `### N. Title`. Affects chen_2021_jesp, korbmacher_2022_kruger, most replication papers. C2.
10. **Future (F1 structural)** — page-bbox-aware sentence stitching at page boundaries. Threads page geometry through `extract_pdf` to detect bottom-N% non-body bbox content and skip it BEFORE pdftotext linearizes. C3 / multi-iter. The cheap variant (iter-27) handled the JUNK; this would handle the SENTENCE-SPLIT itself.

With iter-31 landed, **all 26 papers now have a proper `# Title` as line 1.** The biggest remaining visible-quality issue on the corpus is the JAMA Key Points sidebar (iter-32). Beyond that, most remaining issues are library-level (Camelot table detection, multi-page table assembly, section-detector reordering).

---

## Open question for the user

Do you want:

- **(a)** I commit iter-24 (forward-attach for orphan markers, social_forces_1 stars) which is implemented and unit-tested but uncommitted, then start the assessment-driven iters?
- **(b)** Skip iter-24 (revert it) since it's table work and assessment says table work has diminishing returns — go straight to iter-25 (F6 banner strip)?
- **(c)** Pause iteration and have me do a full eyes-on read of any specific paper(s) you want me to investigate first?
