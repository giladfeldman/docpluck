# Handoff — Iteration 8 (start by reading TRIAGE.md, not this file)

**For:** A fresh Claude session continuing the docpluck splice-spike work. The iter-8 session was the longest and most productive yet: **6 iterations landed in one session (iter-28, iter-29, iter-31, iter-32, iter-33, iter-34)**, all under the TRIAGE-first iteration discipline established in iter-6.

**Branch:** `main` at `24f530f`. Working tree clean. **253 tests passing** in `docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`. Corpus is **26 papers** (unchanged from iter-6).

---

## Read this section before doing ANYTHING else

The iteration discipline established in iter-6 still applies, and it WORKED in iter-8 — 6 iterations landed with zero content loss, all 26 papers visibly cleaner, and the durable lessons captured below.

> **The canonical work queue is `docs/TRIAGE_2026-05-10_corpus_assessment.md`, NOT this handoff doc.**

Read [TRIAGE_2026-05-10_corpus_assessment.md](./TRIAGE_2026-05-10_corpus_assessment.md) FIRST. It maps:
- 8 dominant failure modes (F1-F8). **Seven are now ~~struck-through~~ as resolved** — F1 (cheap variant), F1 extended, F2 compound-heading sub-bug, F3, F4, F5, F6, F8 (multi-level scope).
- Remaining: F2 structural (section-detector misordering), F7 (DOI character-mash — 1 paper), F8 single-level scope, F1 structural (page-bbox-aware sentence stitching).
- A NEW "Promotion to library" section at the bottom documenting that **NO library code has been touched yet** — see Cross-Repo State below.

### Process rules (unchanged from iter-6)

1. **Start each session by reading `TRIAGE_*.md`** (the most-recent-dated file). Pick the next iteration from its top-3 candidates.
2. **Every 3-5 iterations OR whenever a new pattern emerges, run a broad-read pass.** Sample 8-10 random `.md` outputs end-to-end *as a reader, not a diff*. Always check the document **START** (first 30 lines). Update `TRIAGE.md` in place.
3. **Verification ≠ audit.** Char-ratio + word-delta is BLIND to "right words in wrong order under wrong heading". Periodic broad-reads are required.
4. **If 3-4 iters in a row produce only small char-ratio shifts on isolated papers, surface "diminishing returns; should we shift focus?" to the user proactively.**
5. **The optimization criterion is "biggest visible-quality lift per hour of effort", not "next item in the queue".**

These rules worked in iter-8 — I did a broad-read between iter-31 and iter-32 that surfaced both F4 (Key Points) AND F1-extended footer patterns AND F8 numbered subsections as a coherent priority cluster, and all three landed in the same session.

---

## Session state at HEAD

### Commit history (iter-8 session, 4 spike commits + 1 handoff)

| SHA | What |
|---|---|
| [`5174f24`](https://github.com/giladfeldman/docpluck/commit/5174f24) | iter-7 handoff doc (start of session — context for iter-8) |
| [`58c5228`](https://github.com/giladfeldman/docpluck/commit/58c5228) | iter-28 layout-channel title rescue + iter-29 compound-heading merge (jama_open_1/2 `## CONCLUSIONS AND RELEVANCE` merged; 17 of 26 papers got `# Title`) |
| [`c413a16`](https://github.com/giladfeldman/docpluck/commit/c413a16) | iter-31 F6 residual + title-rescue tier-skip; **all 26 papers now have `# Title` line 1** |
| [`527ed53`](https://github.com/giladfeldman/docpluck/commit/527ed53) | iter-32 JAMA Key Points reformat + iter-33 extra footer-strip patterns |
| [`24f530f`](https://github.com/giladfeldman/docpluck/commit/24f530f) | iter-34 multi-level numbered subsection promotion (`### 1.1 Background`) |
| this commit | iter-8 handoff doc (this file) |

### Tests

```bash
cd docs/superpowers/plans/spot-checks/splice-spike && python -m pytest test_splice_spike.py -q
# Should show: 253 passed
```

Test blocks per iteration (all under the same single file):
- Iter-23 / Tier A7 — caption-fold
- Iter-24 / Tier A8 — orphan markers
- Iter-25 / Tier F6 — banner strip
- Iter-26 / Tier F5 — TOC dot-leader strip
- Iter-27 / Tier F1 (cheap) — page-footer line strip
- Iter-29 / Tier F2-residual — compound-heading tail merge
- Iter-28 / Tier F3 — title rescue from inside `## Abstract`
- Iter-31 / Tier F6-residual — extra journal-name banner patterns + title-rescue tier-skip + banner-span pre-filter
- Iter-32 / Tier F4 — JAMA Key Points sidebar reformat
- Iter-33 / Tier F1-extension — extra footer/running-header patterns
- Iter-34 / Tier F8 — multi-level numbered subsection promotion

### Functions added this session (all in `splice_spike.py`)

- `_compute_layout_title(layout_doc)` — page-1 font-size analysis; identifies dominant largest-font multi-line block in upper 60%; returns title text (with `_title_text_from_chars` char-level fallback for tight-kerned PDFs like JAMA / AOM).
- `_title_text_from_chars(page1, y_min, y_max, title_size)` — absolute-gap (>1.5pt) word reconstruction from per-character pdfplumber records.
- `_apply_title_rescue(out, title_text)` — three-case placement: existing h1 no-op / in-place upgrade / strip+prepend.
- `_rescue_title_from_layout(out, pdf_path)` — failure-tolerant orchestrator.
- `_is_banner_span_text(text)` — span-level banner check (`_BANNER_SPAN_PATTERNS`) used to PRE-FILTER spans before dominant-font selector runs. Catches HHS Public Access, Author manuscript, bare journal names, etc.
- `_merge_compound_heading_tails(text)` — re-attach orphan `AND RELEVANCE` to `## CONCLUSIONS`. Curated `_COMPOUND_HEADING_TAILS`.
- `_reformat_jama_key_points_box(text)` — detect canonical Key Points sidebar, emit clean blockquote, stitch split CONCLUSIONS sentence.
- `_promote_numbered_subsection_headings(text)` — promote `\d+\.\d+...` headings to `### N.N Title`.

Two new pattern lists were added: `_BANNER_SPAN_PATTERNS` (span-level pre-filter) and updates to `_HEADER_BANNER_PATTERNS` (line-level header-zone strip) + `_PAGE_FOOTER_LINE_PATTERNS` (whole-document line-level strip).

### Resolved failure modes (don't relitigate)

- ✅ **F1 cheap variant** at `3b24041` (iter-6).
- ✅ **F1 extended** at `527ed53` (this session) — extra footer/header patterns.
- ✅ **F3 title rescue** at `58c5228` + `c413a16` (this session). 26/26 papers now have `# Title`.
- ✅ **F5 TOC dot-leader strip** at `3b24041` (iter-6).
- ✅ **F6 banner-strip (curated patterns)** at `fca6f61` (iter-6) + `c413a16` (this session, residual).
- ✅ **F2 compound-heading-tail (`CONCLUSIONS AND RELEVANCE`)** at `58c5228` (this session).
- ✅ **F4 JAMA Key Points sidebar** at `527ed53` (this session). Stitches split CONCLUSIONS sentence + emits blockquote.
- ✅ **F8 multi-level numbered subsection** at `24f530f` (this session). `### 1.1`, `### 1.2.1`, etc.

---

## Cross-Repo State — IMPORTANT

**No library code has been touched in iter-23 through iter-34.** All spike fixes live in `docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py` — a STANDALONE renderer that imports from `docpluck` library functions but doesn't modify them.

| Layer | This Session | State |
|---|---|---|
| **Spike** (`splice_spike.py`) | All fixes | ~3900 lines; 253 tests passing |
| **Library** (`docpluck/`) | UNTOUCHED | No changes — `__version__` unchanged |
| **App** (`PDFextractor/` separate repo) | UNTOUCHED | `service/requirements.txt` git pin unchanged |
| **PyPI** | UNTOUCHED | No new release needed |

This is **intentional spike-vs-library separation** per CLAUDE.md and the project's two-repo architecture. The spike is a sandbox for iterating on heuristics; when they stabilize, they need to be ported into the library proper.

**No action is required on the app side at this time.** The user's question about "making the app support the new updates" applies once we promote the spike fixes to the library — which is a separate iteration (iter-37+) tracked in TRIAGE's new "Promotion to library" section.

When that day comes, the porting plan is:
1. **`docpluck/normalize.py`** ← absorb `_strip_document_header_banners`, `_strip_toc_dot_leader_block`, `_strip_page_footer_lines` (with `_PAGE_FOOTER_LINE_PATTERNS`, `_HEADER_BANNER_PATTERNS`).
2. **`docpluck/sections/`** ← absorb `_compute_layout_title`, `_apply_title_rescue`, `_merge_compound_heading_tails`, `_promote_numbered_subsection_headings`. Wire title-rescue into the section detector so `## Abstract` doesn't sweep the title in the first place (eliminating the post-process patch).
3. **New `docpluck/sidebar.py` (or similar)** ← absorb `_reformat_jama_key_points_box` for JAMA-style sidebar detection.
4. Bump `docpluck/__init__.py::__version__` (e.g. 1.6.0 → 1.7.0).
5. Bump `pyproject.toml::version` and `docpluck/normalize.py::NORMALIZATION_VERSION` consistently.
6. Update `docs/CHANGELOG.md`.
7. Tag + push: `git tag v1.7.0 && git push --tags`.
8. (Optional) Publish to PyPI: `python -m build && twine upload dist/*`.
9. In `PDFextractor/service/requirements.txt`, bump the `@vX.Y.Z` git pin.
10. Run `/docpluck-deploy` from the docpluck repo — pre-flight check 4 verifies the pin.

---

## What's next per the triage (top-3, priority-ordered)

These are pulled from `TRIAGE_2026-05-10_corpus_assessment.md`. Order is **biggest visible-quality lift per hour**, not "in handoff order".

### Iter-35 — F8 single-level numbered headings (C2, ~1 hr)

**Problem:** `1. Hindsight bias`, `2. Reasons for hindsight bias` (chen_2021_jesp pattern) — single-level numbered subsection headings that pdftotext renders as plain text glued into a paragraph. Iter-34 explicitly deferred this because the same pattern matches list items and citation entries in body prose.

**Fix:** Promote `^\d+\.\s+[A-Z]...$` only when:
- Previous output line is blank (paragraph break above), AND
- Next output line is non-blank body text (not a heading), AND
- Title is 2-60 chars, ends without terminal punctuation, no `et al.`, no long lowercase runs.

Risk papers to inspect after the fix: any paper with numbered reference lists in body (chen_2021_jesp, korbmacher_2022_kruger references, etc.).

### Iter-36 — F2 structural section-detector misordering (C3, library-level)

**Problem:** `## Introduction` in sci_rep_1 has author affiliations + publisher banner LINES UNDER IT instead of body content. amc_1 has `## 1980s` mid-paragraph (a year decade misclassified as a section). am_sociol_rev_3 has `## Introduction` between two halves of a body sentence.

**Fix:** Library-level. Section detector needs page-bbox awareness — read the layout channel to identify which spans are body vs. preamble vs. footnotes, then reorder. C3 / multi-iter. Deferred until layout-channel page-bbox awareness pattern is established (which iter-32 partly proved out via the JAMA Key Points fix).

### Iter-37 — promote spike fixes into library

See "Cross-Repo State" above. After iter-35 / iter-36, when the spike is stable, port the 8 helper functions + 3 pattern lists into `docpluck/normalize.py` and `docpluck/sections/`. Bump the library version. Bump the PDFextractor git pin. Run `/docpluck-deploy`.

---

## Required reading before touching code

1. **[`TRIAGE_2026-05-10_corpus_assessment.md`](./TRIAGE_2026-05-10_corpus_assessment.md)** — the work queue + new Promotion-to-library section. Read this FIRST.
2. **[`LESSONS.md`](../LESSONS.md)** — durable incident log for L-001 through L-006.
3. **[`CLAUDE.md`](../CLAUDE.md)** — particularly the two-repo architecture section + iteration discipline + L-001 to L-005.
4. **Auto-memory at `~/.claude/projects/.../memory/`** — particularly `feedback_optimize_for_outcomes_not_iterations.md`, `project_triage_md_is_work_queue.md`, and the new iter-8 entries.
5. **Three .md outputs end-to-end** — pick one rescued-title APA with subsection headings (`outputs/korbmacher_2022_kruger.md` — `# Title`, `### 1.1 Background`, `### 1.2.1 Underlying mechanisms`, body), one JAMA paper with the rescued Key Points box (`outputs-new/jama_open_1.md` line 1-30 — title, abstract, RESULTS, CONCLUSIONS, blockquote), and one cleanly-rendered Nature paper (`outputs-new/sci_rep_1.md` — `# Title`, `## Abstract`, `## Introduction`).

---

## Operational details

### Render commands (3 batches, parallelize)

Same commands as iter-7 handoff §"Operational details". The 26-paper corpus is unchanged.

### Audit (char ratios + word counts across 26 papers)

Same Python audit script as iter-6 and iter-7 handoffs. The list of 26 papers is unchanged.

### Word-level diff vs HEAD (use after every change)

Same Python diff script. Non-zero deltas should be ONLY tag tokens (td/tr/br/sup), banner/footer/marker tokens, or expected title/heading-prepend tokens.

---

## Current corpus snapshot (audit at HEAD `24f530f`)

| Paper | src | output | ratio | flag | notes |
|---|---|---|---|---|---|
| korbmacher_2022_kruger | 98311 | 110752 | 1.126 | | iter-28 title + iter-34 subsection headings (4 `### N.N` promoted) |
| efendic_2022_affect | 52293 | 61140 | 1.169 | | iter-28 title + iter-34 subsections |
| chandrashekar_2023_mp | 112817 | 113865 | 1.009 | | iter-28 title + iter-34 subsections |
| ziano_2021_joep | 43478 | 58241 | 1.339 | bloat | T1 stitched 14-col — Tier B; iter-31 banner stripped |
| ip_feldman_2025_pspb | 88431 | 106000 | 1.199 | | iter-28 title + iter-34 subsections |
| nat_comms_1 | 76850 | 76456 | 0.995 | | iter-28 title PREPEND |
| ieee_access_2 | 71909 | 59749 | 0.831 | low | iter-31 tier-skip title rescue; pre-existing extraction issue |
| jama_open_1 | 50456 | 58716 | 1.164 | | iter-28 + iter-29 + iter-32 (Key Points box, stitched sentence) |
| jama_open_2 | 48068 | 52999 | 1.103 | | iter-28 + iter-29 + iter-32 + iter-33 (`+ Supplemental content` stripped) |
| amc_1 | 74623 | 74646 | 1.000 | | iter-28 title upgrade |
| amj_1 | 126454 | 124303 | 0.983 | | iter-28 char-fallback title upgrade |
| amle_1 | 135600 | 112327 | 0.828 | low | iter-28 char-fallback title; 12/13 tables undetected — Tier B |
| chan_feldman_2025_cogemo | 81335 | 89048 | 1.095 | | iter-31 banner stripped |
| chen_2021_jesp | 136836 | 191105 | 1.397 | bloat | iter-28 title; iter-31 banner stripped; iter-34 deferred (single-level) |
| ar_apa_j_jesp_2009_12_010 | 79332 | 89352 | 1.126 | | iter-31 banner stripped |
| am_sociol_rev_3 | 107541 | 112843 | 1.049 | | iter-28 title prepend; F2 misordering remains |
| social_forces_1 | 92567 | 117585 | 1.270 | bloat | iter-21+24 wins; iter-31 banner stripped; iter-33 12 running-headers stripped |
| demography_1 | 76008 | 77025 | 1.013 | | iter-31 tier-skip title rescue; iter-33 CC license stripped |
| jmf_1 | 74796 | 64916 | 0.868 | low | iter-31 tier-skip title rescue; no tables — Tier B |
| bjps_1 | 92321 | 104264 | 1.129 | | iter-28 title; iter-33 9 running-headers stripped + `(Received...)` cite-line stripped |
| ar_royal_society_rsos_140066 | 22913 | 22230 | 0.970 | | iter-28 title PREPEND |
| ar_royal_society_rsos_140072 | 60912 | 47583 | 0.781 | low | iter-28 title; iter-22 leader-dot strip — NOT content loss |
| ieee_access_3 | 81412 | 80462 | 0.988 | | iter-28 title; All tables dropped — Tier B |
| ieee_access_4 | 59154 | 71106 | 1.202 | bloat | iter-28 title; T1 body-prose `<th>` |
| nat_comms_2 | 81475 | 77681 | 0.953 | | iter-28 title PREPEND; zero tables — Tier B |
| sci_rep_1 | 56139 | 68828 | 1.226 | bloat | iter-28 title PREPEND from inside Abstract — flagship F3 fix |

---

## Key files

| Path | Role |
|---|---|
| [`docs/TRIAGE_2026-05-10_corpus_assessment.md`](./TRIAGE_2026-05-10_corpus_assessment.md) | **The canonical work queue + new Promotion-to-library section. Read this first.** |
| [`docs/superpowers/plans/spot-checks/splice-spike/splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/splice_spike.py) | The standalone renderer. ~3900 lines. |
| [`docs/superpowers/plans/spot-checks/splice-spike/test_splice_spike.py`](./superpowers/plans/spot-checks/splice-spike/test_splice_spike.py) | 253 unit tests at HEAD. Must stay green. |
| [`docs/superpowers/plans/spot-checks/splice-spike/outputs/`](./superpowers/plans/spot-checks/splice-spike/outputs/) | 7 OLD-corpus regenerated `.md` outputs. |
| [`docs/superpowers/plans/spot-checks/splice-spike/outputs-new/`](./superpowers/plans/spot-checks/splice-spike/outputs-new/) | 19 new-corpus regenerated `.md` outputs. |
| [`docpluck/extract_layout.py`](../docpluck/extract_layout.py) | pdfplumber-based layout channel. Used by `_compute_layout_title`. |

---

## Critical hard rules (still in force)

All previous-iteration rules from `LESSONS.md` PLUS these durable lessons that emerged in iter-8:

- **Layout-channel font sizes are reliable; `extract_words` text spacing is NOT.** pdfplumber's default 3pt `x_tolerance` collapses tight-kerned PDFs (JAMA, AOM, some Sage) into concatenated tokens. Always carry a char-level absolute-x-gap fallback (>1.5pt) for any layout-channel text reconstruction. See `_title_text_from_chars`.
- **PMC papers have HHS Public Access at the LARGEST font on page 1.** Before running any "dominant largest font" selector, PRE-FILTER spans through a banner-recognition pattern (`_BANNER_SPAN_PATTERNS`) so the selector skips banner spans and finds the real content underneath.
- **Elsevier-template PDFs put the bare journal name at a slightly LARGER font than the title.** Same defensive pattern as above — pre-filter the journal-name spans.
- **Char-ratio drop is not content loss.** Word-delta vs HEAD with `\b\w+\b` counter is the definitive check. All iter-25 through iter-34 dropped char counts on multiple papers; zero ever lost real body content — losses are exclusively banner/footer/marker tokens.
- **Conservative > canonical when uncertain.** Single-level numbered headings (`1. X`) deferred to iter-35 because the same pattern matches list items and citation entries; multi-level (`1.1 X`, `1.2.1 X`) is safe because the format is too distinctive for body prose.
- **Subagents that render PDFs sometimes fail silently** with 0-byte outputs — always verify file sizes after subagent batch rendering. (This applies to any parallel rendering script.)
- **All spike work is sandboxed.** No library code (`docpluck/`) or app code (PDFextractor) has been modified in iter-23 through iter-34. Promotion to library is a SEPARATE, future iteration with its own release-flow checklist (see TRIAGE's Promotion-to-library section).

---

## What success looks like

A reader should be able to read a rendered .md file from top to bottom without bumping into:
- Banner junk (✅ resolved iter-25 + iter-31 residual)
- TOC content (✅ resolved iter-26)
- Page-footer text mid-body (✅ resolved iter-27 cheap + iter-33 extended)
- Title nested under Abstract (✅ resolved iter-28)
- Title font below 12pt blocking rescue (✅ resolved iter-31 tier-skip)
- Multi-word headings split mid-phrase (✅ resolved iter-29 for `CONCLUSIONS AND RELEVANCE`)
- Plain-text journal-name banner above title (✅ resolved iter-31)
- Sidebar Key-Points content inlined as body (✅ resolved iter-32)
- Multi-level numbered subsections glued into prose (✅ resolved iter-34)
- Single-level numbered subsections glued into prose (⏳ iter-35)
- Section detector misordering (⏳ iter-36 — library-level)
- Body sentences split across page boundaries (⏳ future C3)

The user reads each .md file in a markdown viewer — what they see is what we're optimizing.

---

## One-line summary for the next session

> Read TRIAGE.md (top-3 = iter-35 single-level numbered headings, iter-36 F2 structural section-detector, iter-37 promote-to-library). Run pytest (253). Periodically broad-read 8-10 outputs. Update TRIAGE. **All iter-23–34 work lives in the spike; library is untouched — porting is a deliberate future step.** Surface diminishing returns to the user. Optimize for outcome, not iteration count.
