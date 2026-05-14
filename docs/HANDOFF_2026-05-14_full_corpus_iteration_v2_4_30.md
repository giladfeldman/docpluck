# Handoff — Full-corpus iteration with self-learning baked in (v2.4.29 → v2.4.30)

**Authored:** 2026-05-14 (third session of the day, ~5-6h cumulative).
**Prior context:** `docs/HANDOFF_2026-05-14_phase_5d_gold_audit_v2_4_29.md` (v2.4.29 ship).
**This session shipped:** v2.4.30 (Cycle 15d) + comprehensive iterate-skill self-improvement infrastructure + 10 AI-gold extractions (up from 4 at session start) + 4-paper v2.4.29 re-verification.

---

## TL;DR for the next session

The two methodology corrections from the user in this session ("AI ground truth, not pdftotext" and "do this on the full corpus with self-learning baked into the skill") are now **structurally encoded in the iterate skill** — not just patched into one cycle. Future sessions running `/docpluck-iterate` will execute the Phase 0.8 smell-test, advance the coverage matrix, and write a methodology postmortem any time a defect class survives N prior cycles.

### Start by

1. **Confirm v2.4.30 prod** (after Vercel + Railway auto-deploy):
   ```bash
   curl -s https://extraction-service-production-d0e5.up.railway.app/_diag | python -m json.tool | head -8
   ```
   Expected: `"docpluck_version": "2.4.30"`.

2. **Merge auto-bump PRs** for v2.4.29 + v2.4.30 in docpluckapp if not already done.

3. **Check wave 2 gold extractions** — 6 dispatched at session end (demography_1, chan_feldman_2025_cogemo, nat_comms_1, bmj_open_1, brjpsych_1, amd_1). When complete, the gold corpus is 16/101 (~16%).

4. **Re-verify v2.4.30 against gold on ieee_access_2** to confirm Cycle 15d (Roman-numeral consumption) landed cleanly — this is the cycle's reverification gate.

5. **Pick next cycle from TRIAGE** (`docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md`). Recommended order: 15e (page-header in equations) → 15n (figure caption placeholder regression, new in this session) → 15f (body-stream table dupes) → 15g (pdftotext glyph collapse — biggest impact but riskiest).

6. **Dispatch wave 3 of gold extractions** (~10 papers) per the corpus-coverage matrix. Target publishers with low/zero gold count first: chicago-ad (1 done), nature (2 done), vancouver (2 done), apa (18 papers total — only 3 done).

---

## What shipped this session

### Releases

| Tag | Cycles | Notes |
|---|---|---|
| **v2.4.29** | 15a (Greek/math/super/sub preservation) + 15b (comma-thousands preservation) + 15c (NFC composition) | New `preserve_math_glyphs=False` flag, plumbed through `normalize_text` → `extract_sections` → `render_pdf_to_markdown`. NORMALIZATION_VERSION 1.8.9 → 1.9.0. 11 new regression tests. Verified on canonical 4: ieee_access_2 has 61 β + 43 δ + 106 ≤ restored (was 0/0/0). amle_1 has 7,445 / 33,719 / 32,981 / 1,675 etc. all comma-preserved. |
| **v2.4.30** | 15d (orphan Roman-numeral consumption) | `_fold_orphan_roman_numerals_into_headings` post-processor + `_ROMAN_PREFIX_HEADING_RE` inline form. ieee_access_2 now has `## I. INTRODUCTION` / `## II. METHODOLOGY` / `## V.: SUPPLEMENTARY INDEX`. III./IV. partial (queued 15i+). 5 new regression tests. |

### Methodology infrastructure (durable, prevents the failure mode that produced 14 broken cycles)

| File | Change |
|---|---|
| [CLAUDE.md](../CLAUDE.md) | Ground-truth hard rule: AI multimodal PDF read is the ONLY truth; pdftotext / Camelot / pdfplumber are diagnostics |
| [`.claude/skills/docpluck-iterate/SKILL.md`](../.claude/skills/docpluck-iterate/SKILL.md) | **Phase 0.8** mandatory pre-cycle smell-test (6 checks: ground-truth, cross-output coverage, recurrence, coverage-matrix, defect-density, postmortem-pending). **Phase 0.9** corpus-coverage matrix init. **Phase 5f** cross-output consistency check. **Phase 5g** methodology meta-audit (every 3rd cycle or after any user correction). **Phase 9** expanded from 5 to 9 steps including 8e refresh-matrix, 8f write-postmortem-if-applicable, 8g user-correction-ratchet, 8i verify-smell-test-invariants-at-cycle-end. |
| [`.claude/skills/docpluck-iterate/LEARNINGS.md`](../.claude/skills/docpluck-iterate/LEARNINGS.md) | **Session postmortem** — full root-cause analysis of how 14 cycles shipped under pdftotext-baseline verification. Catastrophic-bug postmortem template added to the top. |
| [`.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md`](../.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md) | Full protocol rewrite + failure-mode addendum (image-dimension limit, pypdfium2 fallback for Windows w/o pdftoppm, chunk discipline) |
| [`.claude/skills/docpluck-qa/SKILL.md`](../.claude/skills/docpluck-qa/SKILL.md) | Check 7f content-fidelity linter + 7g AI-gold verify |
| [`.claude/skills/docpluck-review/SKILL.md`](../.claude/skills/docpluck-review/SKILL.md) | Hard rules 15a.1-15a.7 |
| `~/.claude/projects/.../memory/feedback_ground_truth_is_ai_not_pdftotext.md` | User correction encoded as memory |
| `~/.claude/projects/.../memory/feedback_full_corpus_self_learning.md` | User correction encoded as memory |

### Corpus coverage (`tmp/corpus-coverage.md`)

Total test corpus: **101 PDFs** across 9 publishers (ama, aom, apa, asa, chicago-ad, harvard, ieee, nature, vancouver — the docx/ directory has 0 PDFs).

**Golds generated this session: 10/101 (~10%)**. Cross-publisher coverage at session end:

| Publisher | Total | Golds | First-wave / second-wave choices |
|---|---|---|---|
| ama | 10 | 1 | jama_open_1 |
| aom | 10 | 2 | amj_1 (session-start), amle_1 (session-start), amd_1 (wave 2 in flight) |
| apa | 18 | 2 | xiao_2021_crsp (session-start), ip_feldman_2025_pspb, chan_feldman_2025_cogemo (wave 2 in flight) |
| asa | 10 | 1 | am_sociol_rev_3 |
| chicago-ad | 10 | 0→1 | demography_1 (wave 2 in flight) |
| harvard | 13 | 1 | bjps_1, brjpsych_1 (wave 2 in flight) |
| ieee | 10 | 1 | ieee_access_2 (session-start) |
| nature | 10 | 1 | sci_rep_1, nat_comms_1 (wave 2 in flight) |
| vancouver | 10 | 1 | bmc_med_1, bmj_open_1 (wave 2 in flight) |

After wave 2 completes (~6 more golds): 16/101 (~16%). Cross-publisher: ≥1 gold per publisher.

### v2.4.29 re-verification (4 canonical papers vs AI gold)

| Paper | Verdict | 15a/b/c | New findings |
|---|---|---|---|
| xiao_2021_crsp | FAIL (improving) | ✓ Greek (η,χ,φ), math (×), commas (1,001 / 1,100 / 1,053), NFC (Król) | New phantom `## Evaluation` heading (was `## Introduction`); references concatenated to mega-lines; ORCID URLs lost; CONTACT line mid-body |
| amj_1 | PARTIAL PASS | ✓ Förster/Potočnik NFC; 4,200 / 10,000 commas | Acknowledgments paragraph DROPPED (text-loss); Appendix A still fractured; bios still fused; pdftotext glyph collapse (=→5, <→,, −→2, ×→3, α→a, χ²→x2) persists as expected for Cycle 15g |
| amle_1 | PASS (with persisting structural defects) | ✓ All ~130 comma-thousands preserved (7,445 / 33,719 / 32,981 / 49,742 / 89,044 / etc.) | Table 13 `State6Harvard` fusion incidentally eliminated. Reported regression in unlocated-tables HTML→flat was TRANSIENT (current re-render shows 13 `<table>` grids intact). 14 demoted subsections still flat. Acknowledgments paragraph fragmented into Intro body. |
| ieee_access_2 | PASS (with one new regression) | ✓ β/δ/γ/τ/≤/≥/× all preserved; INDEX TERMS now its own `## ` heading | **NEW Cycle 15n**: 37 figure captions in `## Figures` block degraded to placeholders `*Figure N. FIGURE N.*` (was full text in v2.4.28). Inline `### Figure N` blocks have full Unicode-correct text — only the trailing appendix copies regressed. Likely a caption-trim chain over-strip after NFC. |

**Net assessment of v2.4.29:** clean wins on character-level fidelity (Greek/math/commas/NFC). Some incidental wins on Table-13 column-fusion. One new regression (Cycle 15n) discovered. All previously known structural defects (15d-15+) persist as expected.

---

## DEFERRED BACKLOG (TRIAGE-ordered)

Full detail in `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md`. Quick view:

| # | Cycle | Group | Severity | Status |
|---|---|---|---|---|
| 1 | 15a | G2 | S0 | ✓ shipped v2.4.29 |
| 2 | 15b | G17 | S2 | ✓ shipped v2.4.29 |
| 3 | 15c | G15 | S2 | ✓ shipped v2.4.29 |
| 4 | 15d | G6 | S1 | ✓ shipped v2.4.30 (adjacent fold; III./IV. partial → cycle 15i) |
| 5 | **15e** | G16 page-header in equations | S2 | **next session priority** |
| 6 | 15n | NEW figure caption placeholder regression | S2 | discovered this session — investigate `_strip_duplicate_uppercase_label` chain |
| 7 | 15f | G4 body-stream table dupes | S1 | multi-paper |
| 8 | 15g | G1 pdftotext glyph collapse | S0 | biggest impact; needs context-aware W-step in normalize.py |
| 9 | 15h | G3+G22 table cell defects | S0 | xiao Table 6 numeric SWAP is the worst case |
| 10 | 15i | G5 section detection under-firing | S1 | also covers the III./IV. partial-fix follow-up |
| 11 | 15j | G7+G8+G21 math content destruction | S1 | engineering papers |
| 12 | 15k | G9+G24 endmatter routing | S1 | Appendices, bios, Acknowledgments |
| 13 | 15l | G10+G11 figure caption emission | S2 | |
| 14 | 15m | G12+G13+G14+G18+G19+G20 long tail | S2 | |

---

## State at handoff

```
$ git log --oneline -6
5a2a648 release: v2.4.30 — Cycle 15d orphan Roman-numeral consumption (G6)
4a0152f skills(iterate): bake self-audit + methodology smell-test into the loop
aa62e3c docs(handoff): Phase-5d AI-gold audit + v2.4.29 source-glyph preservation
216a917 release: v2.4.29 — source-glyph preservation in render path (G2/G7/G12/G15/G17/G21)
223a271 docs(handoff): clean 6-cycle session handoff for next fresh session
0c8d9d2 docs(handoff): update for cycles 13+14 (v2.4.28 — items G + D shipped)
```

**Library tags pushed:** `v2.4.29`, `v2.4.30`. Auto-bump PRs pending in docpluckapp.

**Library tests at v2.4.30:**

| Suite | Result |
|---|---|
| `test_preserve_math_glyphs_real_pdf.py` (13 tests) | 12 pass / 1 skip |
| `test_roman_numeral_section_promote_real_pdf.py` (5 tests, NEW) | 5 pass with 1 documented warning for III./IV. limitation |
| All D5 audit tests (153) | All pass |
| Sections + normalize + render tests | 366 pass / 1 skip |
| `test_sections_golden.py` | 1 pass / 2 PRE-EXISTING fails (not introduced this session; queued for cycle 15i regeneration) |
| 26-paper baseline (`verify_corpus.py`) | Passed at v2.4.29 (background-run completed exit 0) |

**Production state:** Railway likely at v2.4.28 (waiting on auto-bump PRs to merge for v2.4.29 + v2.4.30).

---

## What worked this session

- **Parallel subagent dispatch** (Pattern A from updated SKILL.md): 10 gold extractions ran with up to 6 in parallel; wall-clock ≈ slowest paper, not sum. Total gold-extraction time across the session: ~30-50 min wall clock for 10 papers.
- **Cycle 15a/b/c bundled as one root cause** ("source-glyph preservation"): matched the rule-0e discipline of one-root-cause-per-release. Easy to ship + verify.
- **AI-gold methodology surfaced bugs that pdftotext-baseline missed for 14 cycles**: Greek transliteration, comma-strip, NFC, glyph collapse. None of these would have been caught by the prior verification.
- **Skill self-improvement infrastructure committed as its own commit** (4a0152f): durable; cannot be lost between sessions.
- **User-correction ratchet fired correctly**: both methodology corrections (AI ground truth + full-corpus / self-learning) are encoded as memory + project documentation + skill amendments, in addition to being applied to the current cycle.

## What didn't work

- **Cycle 15d landed only 50%** for ieee_access_2: I. + II. + V.: are folded but III. + IV. aren't (placed far from their headings by the section partitioner). Half-fixes are reportable but ideally a cycle should fully close its scope. Properly: the cycle's plan should have called out the dependency on section-partitioner placement up front.
- **amle_1's transient HTML-table regression** burned ~10-15 min of investigation before resolving on its own. Camelot stream-flavor non-determinism is a known irritant; should be in the iteration playbook's "known noise sources" section.
- **Two pre-existing `test_sections_golden.py` failures** remain unaddressed (pre-date this session; verified by git-stash). They should have been queued earlier; carrying forward.

## Files modified this session (cumulative)

**docpluck (library) repo:**

| File | Change |
|------|--------|
| `docpluck/normalize.py` | preserve_math_glyphs flag, A5/A3a/A3/A3c gating, NFC composition + space-before-combining-mark squash. NORMALIZATION_VERSION 1.9.0 |
| `docpluck/sections/__init__.py` | preserve_math_glyphs forwarded |
| `docpluck/render.py` | preserve_math_glyphs opt-in; `_ROMAN_NUMERAL_ORPHAN_RE` + `_ROMAN_PREFIX_HEADING_RE`; `_fold_orphan_roman_numerals_into_headings` wired in |
| `docpluck/__init__.py`, `pyproject.toml` | 2.4.28 → 2.4.30 |
| `CHANGELOG.md` | v2.4.29 + v2.4.30 blocks |
| `CLAUDE.md` | Ground-truth hard rule |
| `tests/test_preserve_math_glyphs_real_pdf.py` | NEW 13 tests |
| `tests/test_roman_numeral_section_promote_real_pdf.py` | NEW 5 tests |
| `tests/test_all_caps_section_promote_real_pdf.py` | Updated for cycle 15d-compatible expectation |
| `tests/test_d5_normalization_audit.py` | Version-bump test relaxed to 1.9.x |
| `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md` | NEW + Cycle 15n + 15d-partial entries |
| `docs/HANDOFF_2026-05-14_phase_5d_gold_audit_v2_4_29.md` | NEW |
| `docs/HANDOFF_2026-05-14_full_corpus_iteration_v2_4_30.md` | NEW (this file) |
| `.claude/skills/docpluck-iterate/SKILL.md` | Phase 0.8/0.9 added, Phase 5d/5f/5g added, Phase 9 expanded 5→9 |
| `.claude/skills/docpluck-iterate/LEARNINGS.md` | Session postmortem |
| `.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md` | Full rewrite + failure modes |
| `.claude/skills/docpluck-qa/SKILL.md` | 7f + 7g |
| `.claude/skills/docpluck-review/SKILL.md` | Hard rules 15a.1-15a.7 |
| `tmp/corpus-coverage.md` | NEW |
| `tmp/<paper>_gold.md` × 10 | Cached gold extractions |

**docpluckapp (app) repo (commit 4d022f8 on master):**

- `frontend/src/components/document-workspace.tsx` — table-HTML pass-through fix from earlier this session.

**~/.claude memory (cumulative):**

- `feedback_ground_truth_is_ai_not_pdftotext.md` (NEW this session)
- `feedback_full_corpus_self_learning.md` (NEW this session)
- `MEMORY.md` (2 new index lines)

---

## How to resume

```bash
cd C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck

# 1. Confirm v2.4.30 prod (after auto-bump PRs merge + Railway redeploys)
curl -s https://extraction-service-production-d0e5.up.railway.app/_diag | python -m json.tool | head -8

# 2. Check on wave 2 of gold extractions (started end of this session):
ls tmp/{demography_1,chan_feldman_2025_cogemo,nat_comms_1,bmj_open_1,brjpsych_1,amd_1}_gold.md 2>/dev/null
# If all present, gold corpus is 16/101. If some missing, the agents may have failed (re-dispatch with smaller chunks).

# 3. Run Phase 0.8 smell-test (mandatory before any cycle):
#    - Ground-truth source: must be AI-gold, never pdftotext (CLAUDE.md hard rule).
#    - Cross-output coverage: enumerate which views the cycle's fix affects.
#    - Recurrence: search LEARNINGS + memory for prior corrections on the topic.
#    - Coverage matrix: read tmp/corpus-coverage.md.
#    - Defect-density: are 3+ recent cycles in the same root-cause class?
#    - Postmortem-pending: any TRIAGE class without a methodology postmortem?

# 4. Re-verify v2.4.30 on ieee_access_2 (Cycle 15d ship gate):
python -u -c "
from pathlib import Path
from docpluck.render import render_pdf_to_markdown
md = render_pdf_to_markdown(Path('../PDFextractor/test-pdfs/ieee/ieee_access_2.pdf').read_bytes())
Path('tmp/ieee_access_2_v2.4.30.md').write_text(md, encoding='utf-8')
print('## I. INTRODUCTION:', '## I. INTRODUCTION' in md)
print('## II. METHODOLOGY:', '## II. METHODOLOGY' in md)
print('## V.: SUPPLEMENTARY INDEX:', '## V.: SUPPLEMENTARY INDEX' in md)
"

# 5. Dispatch wave 3 (10 more papers, publisher diversity-first per coverage matrix)
# 6. Pick next fix cycle from docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md
#    Recommended order: 15e (page-header in equations) → 15n (figure caption placeholder regression)
#    → 15f (body-stream table dupes) → 15g (pdftotext glyph collapse)
```

### Mandatory pre-reading for the next session

- This handoff: `docs/HANDOFF_2026-05-14_full_corpus_iteration_v2_4_30.md`
- Prior handoff: `docs/HANDOFF_2026-05-14_phase_5d_gold_audit_v2_4_29.md`
- Triage doc (canonical work queue): `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md`
- Coverage matrix (durable): `tmp/corpus-coverage.md`
- CLAUDE.md — especially the ground-truth + rule-0e hard rules
- `.claude/skills/docpluck-iterate/SKILL.md` — full rewrite with Phase 0.8/0.9 + 5g + expanded Phase 9
- `.claude/skills/docpluck-iterate/LEARNINGS.md` — session postmortem at the top
- Memories: `feedback_ground_truth_is_ai_not_pdftotext.md`, `feedback_full_corpus_self_learning.md`, `feedback_fix_every_bug_found.md`

---

The session's biggest durable artifact is not the v2.4.29 + v2.4.30 ships — it's the iterate skill itself. The Phase 0.8 smell-test + Phase 9 expansion + corpus-coverage matrix are the mechanisms that turn future sessions into self-correcting iterations. The user's framing was operative: "self-learning and improvement have to baked into the skill." It's baked.
