# Handoff — autonomous `/docpluck-iterate` run (APA-first), session 3

**Authored:** 2026-05-16. Picks up from `docs/HANDOFF_2026-05-16_iterate_apa_run_2.md`.
**Stop reason:** wall-clock budget (5h autonomous run). 4 cycles shipped clean (v2.4.40–v2.4.43), each AI-gold-verified OVERALL PASS with zero regressions. Plus one mid-run process fix (gold-generation delegation). The APA corpus is **NOT clean — ~12 papers still FAIL** on pre-existing defects the cycles did not reach. Reported as an honest **PARTIAL** per rule 0e-bis. Full punch-list in §4.

---

## 1. State at handoff

| Item | Value |
|---|---|
| Library version | **v2.4.43** (tag pushed; `__init__.py` + `pyproject.toml` synced) |
| `NORMALIZATION_VERSION` | 1.9.7 (bumped at cycle 10) |
| 26-paper baseline | **26/26 PASS, 0 WARN** (re-confirmed every cycle) |
| Broad pytest | 1226 pass / **15 failed (all pre-existing snapshot drift — confirmed via git-stash round-trip every cycle)** / 0 new |
| Prod `/_diag` | v2.4.42 confirmed live during the run; v2.4.43 deploying at handoff |
| AI-gold cache | unchanged — this run REUSED cached `reading` golds; generated none |

## 2. Cycles shipped this session (4) + 1 process fix

| Cycle | Version | Defect | Layer |
|---|---|---|---|
| 8 | v2.4.40 | GLYPH S0 — standalone `2`-for-U+2212 minus recovery via point-estimate ∈ CI pairing (efendic 22 negative coefficient cells + `Mposterior`) | `normalize.py::recover_minus_via_ci_pairing` (W0d) + render post-process |
| 9 | v2.4.41 | G5 S1 — numbered subsection-heading regex too strict (no trailing dot, no internal colon); ~78 `###` headings recovered across 4 papers | `render.py::_NUMBERED_SUBSECTION_HEADING_RE` |
| 10 | v2.4.42 | D4 S2 — Elsevier page-1 footer (e-mail line + ISSN/copyright line) spliced into the Introduction body | `normalize.py` W0 watermark patterns (Issue K + L) |
| 11 | v2.4.43 | G5a S1 — single-level numbered section headings (`2. Omission neglect`) demoted to body text | `render.py::_promote_numbered_section_headings` |
| — | (ac34c7e, no version) | **PROCESS FIX** — gold generation delegated to article-finder; docpluck's private extraction prompt removed | skill docs (see §5) |

Every cycle: 26/26 baseline, 0 new pytest failures (15 pre-existing confirmed via stash round-trip), AI-gold verifier OVERALL PASS, ≥1 real-PDF regression test added, surgical verified diff.

## 3. APA corpus status

Cycles 8-11 each shipped a verified incremental fix, but none reached the dominant blockers (TABLE structure, named-heading demotion, figure-caption defects). The APA corpus is **not clean** — ~12 papers still FAIL Phase-5d. The standing run verdict is **PARTIAL** (rule 0e-bis): incremental fixes shipped, corpus still broken, run continues next session.

## 4. Open queue — punch-list for the next session

See `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md` "SESSION-3 STANDING VERDICT" for the full ranked table. Top items:

| Defect class | Sev | Cost | Notes |
|---|---|---|---|
| **TABLE structure destruction** | S0/S1 | C3 | ~11 papers — grid lost → caption-bleed, flat number-dump, empty `<table>` shells, two-tables-merged, rows dropped. The single largest blocker; needs a render/structured-extraction coordination design — a dedicated session. |
| **G5c split-line numbered headings** | S1 | C2 | `5.3.`\n\n`Results` — number alone on a line; renders orphan bare-number + a MISLABELED generic `## Results`. cycle-3 orphan-folder multi-level analogue. |
| **G5d named (unnumbered) heading demotion** | S1 | C2-C3 | ~7 papers — `Participants`, `Affect Heuristic`, `Background` as body text. Section-partitioner work; largest false-positive surface. |
| **G5b long-descriptive-title prose guard** | S1 | C1 | `≥5-lowercase-word` guard over-rejects legit long numbered headings. Cheap. |
| **FIG caption double-emission + truncation** | S2 | C2 | ~8 papers — caption inline + in `## Figures` block; truncated mid-word; figure data-labels as orphan body lines. |
| **GLYPH ligature `ﬁ`/`ﬂ`** | S2 | C1 | `conﬁdent`, `inﬂuence` not decomposed — NFKC fixes it; check why the current NFC pass misses U+FB01/FB02. Likely wide + cheap → good first pickup. |
| **COL column-interleave** | S0 | C3 | chan_feldman, chandrashekar — text-channel reading order. Escalate. |
| **GLYPH 011 `−`→deleted / efendic `Mchange` no-CI** | S0 | C3-C4 | unrecoverable from the text channel — needs layout-channel per-char glyph identity. Escalate. |

Plus: **15 pre-existing pytest failures** (12× `test_extract_pdf_byte_identical` snapshot drift + 2× `test_sections_golden` + 1× `test_request_09`) — a standalone `tests:` regen cycle. And the **3 gold-blocked APA papers** (010, 012, jamison — Anthropic content filter blocks the gold-extraction subagent).

**Recommended next pickup:** GLYPH ligature (S2×C1, likely wide, cheapest) → G5b prose-guard relax → G5c split-line folder → FIG caption dedup → G5d named-heading detection → TABLE cluster (C3, dedicated session).

## 5. Process improvement shipped this run — gold generation delegated to article-finder

Mid-run, ArticleFinder flagged (and the user confirmed as a directive) that `docpluck-iterate` carried its OWN gold-extraction prompt (`references/ai-full-doc-verify.md` Step 1b, ~115 lines) instead of going through the shared `~/.claude/skills/article-finder/gold-generation.md` protocol — and escicheck-iterate carried another private prompt. Two divergent prompts extracting the same paper produced two different `reading` golds (981 vs 617 lines). **Fixed (commit ac34c7e):** the private prompt was deleted; `ai-full-doc-verify.md` Step 1 now delegates generation to `article-finder generate-gold`; `SKILL.md`, `CLAUDE.md`, and `docpluck-qa/SKILL.md` updated; memory `feedback_gold_generation_via_article_finder` saved.

**Two coordination items for ArticleFinder (not actioned here — article-finder owns those files):**
1. The existing cached `reading` golds were produced by docpluck's old private prompt — they should be regenerated through the shared protocol.
2. The shared `gold-generation.md` `reading`-view prompt is simpler than docpluck's old one (no cell-by-cell tables / figure descriptions). docpluck's verifier does cell-by-cell TABLE checks — if the shared `reading` view stays simple, docpluck's TABLE verification degrades. The richness should be added to `gold-generation.md`, coordinated with the article-finder owner.

## 6. Pending SKILL.md amendment (awaiting user review)

The cycle-6 PROPOSED AMENDMENT (carried since session 1) still stands: SKILL.md Phase 4 should state that a glyph/encoding/character-level fix MUST be a shared helper applied at all three text chokepoints (`normalize_text` body / `tables/cell_cleaning` Camelot cells / `render_pdf_to_markdown` post-process) from the first edit. Cycles 7-8 applied this proactively and it worked cleanly — it should be promoted from "proposed" to skill text.

## 7. Stop reason

Wall-clock budget: the user instructed a 5-hour autonomous run. 4 cycles shipped clean and prod-bound (v2.4.40-43), plus the gold-generation process fix. The APA corpus improved but is **not clean — ~12 papers still FAIL** on the pre-existing TABLE / named-heading / figure-caption clusters (C2-C3, beyond per-cycle scope). Reported as an honest **PARTIAL** per rule 0e-bis. The next session resumes from §4.
