# Corpus Assessment & Triage — 2026-05-10

**Last update:** 2026-05-10 after iter-26+27 landed at `3b24041` (TOC strip + page-footer strip).

**Scope:** AI-verification read of 26 .md outputs in `docs/superpowers/plans/spot-checks/splice-spike/outputs{,-new}/`. Corpus reduced from 27 → 26 papers: nathumbeh_2 removed (was Nature Hum Behav supplementary materials, not an article — user decision 2026-05-10).

## Iteration log
- ✅ **iter-23** `6e8d266` — caption-fold across consecutive lines (FIGURE/TABLE N + tail).
- ✅ **iter-24** `768a942` — forward-attach for orphan marker rows (social_forces stars).
- ✅ **iter-25 / F6 RESOLVED** `fca6f61` — banner / running-header strip in header zone. 16 papers cleaned. Document START is now title or first author block instead of HHS / arXiv / Cite this article / mangled-DOI / manuscript-ID gibberish.
- ✅ **iter-26 / F5 RESOLVED** `3b24041` — TOC dot-leader strip in head zone (+ false-promoted-heading drop). General-purpose; main beneficiary (nathumbeh_2) was removed from corpus per user direction, but function stays in case other supplementary docs enter.
- ✅ **iter-27 / F1 RESOLVED (cheap variant)** `3b24041` — page-footer line strip across whole document. Page-N markers, JAMA `October 27, 2023 X/13` footers, `(continued)` page-break markers, `Corresponding Author:` lines, bare email lines, JAMA citation/category running headers, `Open Access. ... (Reprinted)` compound, `© YYYY` lines, `aETH Zurich` affiliation footnotes, JAMA Visual Abstract sidebar all dropped. 13+ papers visibly cleaner. Big visible-quality win: jama_open_1 abstract → trial registration → introduction now flows clean. The user's headline complaint about page-footer interleave is RESOLVED for the cheap-variant scope; the underlying sentence-stitching at page boundaries (C3 cost) is unfixed but the JUNK between halves is gone.

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
| **F2** | **Section heading appears AFTER its content**: `## Introduction` printed at line N+5 while the introduction's first paragraph already started at line N. Caused partly by F1 (page footer pushed heading down past content — now fixed) and by section-detector misordering. | **S1** | am_sociol_rev_3 (still — `## Introduction` between body sentence halves), sci_rep_1, jama_open_1 (`AND RELEVANCE` orphan), amc_1 (1980s section), nat_comms_2 | **C2** | Iter-27 removed the F1 component; remaining cases are pure section-detector misorderings. jama_open_1's `## CONCLUSIONS / AND RELEVANCE` split is a heading-tokenization bug — multi-word headings (`CONCLUSIONS AND RELEVANCE`, `DESIGN, SETTING, AND PARTICIPANTS`) should be tokenized as a unit. |
| **F3** | **Title + authors dumped into Abstract section**: the title block ends up nested under `## Abstract` instead of being the document's `# Title` block. Affiliations sometimes follow. | **S1** | sci_rep_1 (worst), nat_comms_2, ar_royal_society_rsos_140066 | **C2** | Section-detector treats the first heading-like word ("Abstract", "OPEN", "ARTICLE") as the document opener. Needs an explicit pre-pass that finds the article title (large-font line, multi-line wrap) and sets it as the doc title before any `##` is emitted. |
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

4. **Iter-28 (F3) — title rescue from Abstract.** Layout-channel pre-pass that finds the large-font multi-line block at the top of page 1 and emits it as `# Title` before any `##` heading. Then the section detector won't sweep title + authors into the first `## Abstract`. Affects sci_rep_1, nat_comms_1/2, ar_royal_society_rsos_140066. C2, ~2 hr.
5. **Iter-29 (F2 residual) — multi-word heading tokenization.** Recognize known compound section headings as units: `CONCLUSIONS AND RELEVANCE`, `DESIGN, SETTING, AND PARTICIPANTS`, `MAIN OUTCOMES AND MEASURES`. Affects jama_open_1/2 abstract structure. C1, ~30 min.
6. **Iter-30 (F4) — sidebar Key-Points box detection.** Layout-aware: identify text-block geometrically isolated from the body column (different x-column at same y-range). Preserve as a separate `<aside>` block rather than inlining into the abstract. Affects jama_open_1/2. C2-C3, may need page-bbox awareness similar to F1 structural fix.
7. **Future (F1 structural)** — page-bbox-aware sentence stitching at page boundaries. Threads page geometry through `extract_pdf` to detect bottom-N% non-body bbox content and skip it BEFORE pdftotext linearizes. C3 / multi-iter. The cheap variant (iter-27) handled the JUNK; this would handle the SENTENCE-SPLIT itself.

After iter-28/29 the user-visible quality should be meaningfully cleaner across most of the 26-paper corpus. Remaining work after that is largely library-level (Camelot table detection, multi-page table assembly).

---

## Open question for the user

Do you want:

- **(a)** I commit iter-24 (forward-attach for orphan markers, social_forces_1 stars) which is implemented and unit-tested but uncommitted, then start the assessment-driven iters?
- **(b)** Skip iter-24 (revert it) since it's table work and assessment says table work has diminishing returns — go straight to iter-25 (F6 banner strip)?
- **(c)** Pause iteration and have me do a full eyes-on read of any specific paper(s) you want me to investigate first?
