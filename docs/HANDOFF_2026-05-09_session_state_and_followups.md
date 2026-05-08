# Handoff — session state at end of 2026-05-09

**For:** Future Claude session resuming docpluck library work after the post-v2.0.0 strict-iteration campaign.
**From:** Session that ran the strict-bar iteration (2026-05-07 → 09) and shipped 14+ targeted fixes for real-world section-detection failures.
**Sister handoff:** [HANDOFF_2026-05-09_unified_extraction_brainstorm.md](HANDOFF_2026-05-09_unified_extraction_brainstorm.md) — the open architectural question the user wants brainstormed in a fresh session. Read both.

> **Required reading before touching any extraction / sectioning code:** [LESSONS.md](../LESSONS.md), especially L-001 ("Never swap the PDF text-extraction tool as a fix for downstream problems"). Three sessions in a row have re-derived this lesson by trial and error; the fourth doesn't get to.

---

## 1. TL;DR

- **Library state:** v2.0.0 with 14 targeted fixes layered on top in the working tree (uncommitted). 255 sections + normalize tests pass + 2 skipped. 744 / 18 in the full repo suite.
- **Test corpus:** 101 fresh PDFs across 9 academic styles. **96–98 / 101 PASS or PASS_W** under the pragmatic strict-bar grader. All 9 styles meet the convergence criterion (≥3 consecutive first-try-clean papers). 3–5 hard fails are deferred with documented reasons in [`docs/superpowers/plans/sections-deferred-items.md`](superpowers/plans/sections-deferred-items.md).
- **Local app is live.** Python service on `:6117`, Next.js frontend on `:6116`. docpluck is installed in editable mode pointing at this working tree, so any further library change shows up live on next request.
- **Working tree is dirty.** Nothing pushed, nothing tagged. The user has been validating real-world papers in the local app and giving feedback that drove later fixes — see §3 for the recent ones that came from this loop.
- **The deeper question** the user posed at end of session is in the sister handoff. Pick that up in a fresh session because it requires architectural brainstorming, not more incremental fixes.

---

## 2. Quick-start for the next session

1. Open this file and the sister handoff in a fresh session.
2. Read `LESSONS.md` (5 short lessons; ~3 minutes).
3. Run baseline tests:
   ```bash
   cd C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck
   git status                                                 # working tree dirty — expected
   python -m pytest tests/test_sections_*.py tests/test_normalization.py -q
   # expected: 255 passed, 2 skipped
   ```
4. Confirm the local app responds:
   ```bash
   curl -s http://localhost:6117/health
   # expected: {"status":"ok",...}
   curl -sI http://localhost:6116/ | head -1
   # expected: HTTP/1.1 200 OK
   ```
   If the service is not up, restart with the dev token:
   ```bash
   DEV_TOKEN=$(cat /tmp/_dev_token.txt) INTERNAL_SERVICE_TOKEN="$DEV_TOKEN" \
     python -m uvicorn app.main:app --port 6117 --app-dir C:/Users/filin/Dropbox/Vibe/MetaScienceTools/PDFextractor/service
   ```
   The dev token (`local-dev-shared-token-…`) is in `/tmp/_dev_token.txt` AND in `PDFextractor/frontend/.env.local`.

---

## 3. What changed in this session (full ledger)

All changes are in the working tree, uncommitted. Test files are kept in sync.

### 3.1 Sectioner improvements (new heading patterns + synthesis)

| Date | Change | Files |
|---|---|---|
| 05-07 | Pattern A — lowercase line-isolated canonical headings (Elsevier `a b s t r a c t` → flattened by pdftotext to lowercase `abstract`). Added `_is_fully_isolated_heading` carve-out in [`docpluck/sections/annotators/text.py`](../docpluck/sections/annotators/text.py). | annotators/text.py + tests |
| 05-07 | Pattern E synthesis — when no Abstract heading is detected, synthesize one from the leading `unknown` span. Smart citation-block detection (skip the first ≥600-char paragraph if it has DOI/Department/email tokens). When the leading unknown is one big paragraph (single-newline-only), fall back to per-line scan looking for ≥800-char prose lines. | [`docpluck/sections/core.py`](../docpluck/sections/core.py) `_synthesize_abstract_from_leading_unknown` |
| 05-07 | Pattern E synthesis (part 2) — when the front-matter section before the first body section is bloated (>3000 chars + >5% of doc) and no Introduction was detected, split it into shrunken-front-matter + introduction. Handles bjps_1 (theory papers with body in keywords) and the Collabra/JDM bloated-abstract case. | core.py `_synthesize_introduction_if_bloated_front_matter` |
| 05-07 | Sentence-case heading acceptance — accept `Materials and methods` (lowercase function words) in addition to Title Case / ALL CAPS. | annotators/text.py |
| 05-07 | Roman-numeral + letter numbering prefix (`I. INTRODUCTION`, `II. METHODOLOGY`, `A. SUBSECTION`) | annotators/text.py `_NUM_PREFIX_FRAG`, taxonomy.py `_NUMBERING_PREFIX` |
| 05-07 | Taxonomy: added `experiment`/`experiments`, `methodology`, `experimental results`, `evaluation`, `performance evaluation`, `financial disclosure/funding` (and 2 more). | [`docpluck/sections/taxonomy.py`](../docpluck/sections/taxonomy.py) |
| 05-08 | `Conclusion` is its own canonical label (`SectionLabel.conclusion`), separate from `discussion`. `Discussion and Conclusion` combined stays as `discussion`. | taxonomy.py + tests |
| 05-09 | `summary` REMOVED from canonical abstract (per user feedback: "Summary" is more often a mid-paper subsection like "Summary of Original Studies"). RSOS papers now go through Pattern E synthesis instead. | taxonomy.py |
| 05-08 | Abstract synthesis: pick FIRST ≥600-char paragraph; if it looks like a citation block (has `doi.org/`, `@`, `Department` AND <1500 chars), skip to the NEXT ≥600-char paragraph. | core.py |

### 3.2 normalize.py W0 watermark patterns (the right layer for running-header / footnote leak)

| Date | Pattern | Targets |
|---|---|---|
| 05-07 | `© NNNN <Publisher> All rights reserved.` line-anchored | Elsevier, Springer, Wiley copyright stamps in abstracts |
| 05-07 | `<Author> / <Journal> <Vol> (<Year>) <pages>` line-anchored | Two-column running headers (Elsevier JESP, Cogn Psychol) |
| 05-07 | `Creative Commons … License` sentence | CC license footer in abstract paragraphs |
| 05-09 | `Downloaded from <url> [by guest] on <date>` (relaxed to allow optional intermediate phrase) | Collabra Psychology / UCPress watermark — was missing on every Collabra paper |
| 05-09 | `<a> <Surnames…> are equal-contribution / joint first authors <email>` | Author-equal-contribution footnote at bottom of page 1 (Brick et al 2021, Adelina-Feldman 2021 IRSP, etc.) |

All in [`docpluck/normalize.py`](../docpluck/normalize.py) `_WATERMARK_PATTERNS`. 14 unit tests in [`tests/test_normalization.py::TestW0_PublisherCopyrightAndRunningHeader`](../tests/test_normalization.py).

### 3.3 Documentation (the durable part)

| File | Status |
|---|---|
| [`LESSONS.md`](../LESSONS.md) | NEW — five lessons (L-001 to L-005), most critical is L-001 about NOT swapping PDF tools |
| [`CLAUDE.md`](../CLAUDE.md) | Updated — "Critical hard rules" section now leads with channel-separation rule and links to LESSONS.md; added explicit text-vs-layout architecture table |
| [`docs/DESIGN.md`](DESIGN.md) | Added §13 ("Two channels: text vs layout") |
| `docpluck/sections/__init__.py` | Inline guard comment at the PDF branch warning future sessions not to swap to pdfplumber + pointer to LESSONS.md L-001 |
| [`docs/superpowers/plans/sections-issues-backlog.md`](superpowers/plans/sections-issues-backlog.md) | Updated — full fix log + tests |
| [`docs/superpowers/plans/sections-deferred-items.md`](superpowers/plans/sections-deferred-items.md) | NEW — every deferred item explained with what would fix it |
| [`docs/superpowers/plans/spot-checks/`](superpowers/plans/spot-checks/) | 3 spot-check reports through the iteration |
| [`docs/superpowers/plans/2026-05-07-sections-strict-iteration-progress.md`](superpowers/plans/2026-05-07-sections-strict-iteration-progress.md) | Final tracking sheet |

### 3.4 Failed attempt that was REVERTED (don't redo it)

**2026-05-09 ~15:00:** wired `extract_pdf_layout` into `extract_sections` thinking F0 layout-aware running-header strip would fire on Brick et al's `"Downloaded from..."` watermark. **Broke 60+ corpus papers in one commit** — pdfplumber's text format diverges from pdftotext's enough that all heading regexes / taxonomy variants / synthesis heuristics fail. Reverted within 30 minutes. **The right fix was a normalize.py W0 regex** (now shipped). This is the third time a session has tried "swap pdfplumber for pdftotext as text source" and failed; LESSONS.md L-001 documents the full incident.

---

## 4. Test corpus + per-style status (final regrade)

Pragmatic strict-bar grader (see `_scratch_score.py` recipe in `docs/superpowers/plans/sections-deferred-items.md`):

| Style | PASS | PASS_W | FAIL | OK% |
|---|---|---|---|---|
| apa | 15 | 2 | 1 | 94% |
| ieee | 6 | 4 | 0 | 100% |
| nature | 8 | 1 | 1 | 90% |
| vancouver | 9 | 0 | 1 | 90% |
| aom | 2 | 8 | 0 | 100% |
| ama | 10 | 0 | 0 | 100% |
| asa | 3 | 7 | 0 | 100% |
| harvard | 3 | 8 | 2 | 85% |
| chicago-ad | 6 | 4 | 0 | 100% |
| **Total** | **62** | **34** | **5** | **95%** |

(Tally is post-summary-revert. Earlier in the day the corpus was at 98/101 because `summary` was in canonical; after reverting per user instruction, 1–2 RSOS papers regressed to FAIL because Pattern E synthesis doesn't recover them.)

**Hard fails as of last regrade:**
- `apa/jdm_.2023.10.pdf` — 1-page archival correction notice; not a research paper.
- `nature/nathumbeh_2.pdf` — 59-page Nature Hum Behav supplementary materials; column-bleed extraction.
- `vancouver/plos_med_1.pdf` — 5.5% leading title block, just over the 5% pragmatic threshold.
- `harvard/ar_royal_society_rsos_140072.pdf` — RSOS uses "1. Summary" instead of "Abstract"; Pattern E synthesis didn't catch this one.
- `harvard/bjpsych_open_1.pdf` — structured-abstract layout (Background/Method/Results/Conclusions as labeled subsections); harder pattern.

All 5 are documented in `sections-deferred-items.md` with the reason and what a future fix would have to do. None is a sectioner regression — they are layout edge cases.

---

## 5. Real-world papers the user uploaded that drove the late fixes

The user has been testing real-world papers from `~/Dropbox` (not in the test corpus). Three papers shaped the late fixes:

| Paper | Issue surfaced | Fix |
|---|---|---|
| `Adelina & Feldman 2021-Pronin & Ross 2006-replication and extension-print-nosupp.pdf` (IRSP) | 2-column extraction issue (pdftotext interleaves columns on this geometry); abstract not detected | Acknowledged as known pdftotext limitation. The interleaving is at extract level — sections module can't recover it. Documented as a class for future column-handling work (see sister handoff). |
| `Aiyer-etal-2024-Collabra-Gino-etal-2009-replication-extensions-print-nosupp.pdf` | Abstract section absorbed citation block; "Conclusion" became `discussion_2` | Smart citation-block detection in synthesis (skip the first ≥600 char paragraph if it has DOI tokens); `Conclusion` as separate canonical label. |
| `Brick et al-Miller & Ratner 1998 replications & extensions-print-nosupp.pdf` (Collabra) | "Downloaded from … by guest on 2021" in body sections; author-equal-contribution footnote leaked into abstract | Two new W0 watermark patterns. Verified: 16 raw watermarks → 0 in normalized text; 1 raw author footnote → 0 in normalized. |

**The Adelina paper still has unresolved 2-column interleaving.** This is the biggest remaining real-world quality gap and is the main motivation for the sister-handoff brainstorm.

---

## 6. What's still not done

### 6.1 Deferred (small)

The 5 hard fails in the test corpus (above). All have documented reasons. Don't chase these unless you're pursuing the architectural rework in the sister handoff.

### 6.2 Webapp consolidation (handoff §8 from earlier)

The original handoff (`HANDOFF_2026-05-07_sections_strict_iteration.md` §8) flagged that the user wants a single `/document` page that shows sections + tables + figures + normalized text together. **Not addressed** in this session beyond restarting the same separate `/extract` and `/sections` pages with the dev INTERNAL_SERVICE_TOKEN wiring.

The architectural question (sister handoff) needs to land first before this UX work, because the answer determines whether `/document` runs *one* unified extraction or stitches together two separate ones.

### 6.3 Commit + tag + deploy

Working tree is dirty. Suggested next-session sequence (after the sister-handoff brainstorm produces a direction):

1. Commit each logical change as its own commit (sectioner heuristics; W0 patterns; LESSONS.md docs; etc.).
2. Bump version: `__init__.py` `__version__`, `pyproject.toml`, `NORMALIZATION_VERSION`. The right number is `v2.1.0` (additive, no breaking).
3. Tag `v2.1.0`, push tag.
4. Bump `PDFextractor/service/requirements.txt` git pin from `@v2.0.0` to `@v2.1.0`.
5. Run `/docpluck-deploy` from this repo — pre-flight check 4 catches mismatched pins.

---

## 7. Architecture invariants that MUST be preserved

Anything that contradicts these is a regression. They are codified in `LESSONS.md` and `CLAUDE.md`:

1. **Text channel = `extract_pdf` (pdftotext default).** Sections, normalize, batch read this. Do not swap to pdfplumber's text — see L-001.
2. **Layout channel = `extract_pdf_layout` (pdfplumber).** Tables, figures, F0 layout-aware strip read this. Geometry-only.
3. **Never `pdftotext -layout`** (column interleaving on most papers).
4. **Never AGPL-licensed PDF tools** (pymupdf, pymupdf4llm, fitz). Only pdfplumber (MIT) + pdftotext.
5. **Always normalize U+2212 → ASCII hyphen** (S5 step in normalize.py).

---

## 8. Pointers

- Library code: `docpluck/`
- Tests: `tests/`
- Public-facing docs: `docs/README.md`, `docs/DESIGN.md`, `docs/NORMALIZATION.md`, `docs/BENCHMARKS.md`
- Internal lessons: `LESSONS.md`
- Plans / spot-checks / backlog: `docs/superpowers/plans/`
- Sister handoff (the brainstorm question): [HANDOFF_2026-05-09_unified_extraction_brainstorm.md](HANDOFF_2026-05-09_unified_extraction_brainstorm.md)
- Test corpus: `~/Dropbox/Vibe/MetaScienceTools/PDFextractor/test-pdfs/<style>/`

Good luck. Read LESSONS.md before doing anything.
