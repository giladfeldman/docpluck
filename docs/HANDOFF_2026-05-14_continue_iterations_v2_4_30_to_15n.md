# Handoff — Continue docpluck-iterate cycles via article-finder ground-truth cache

**Authored:** 2026-05-14 (end of cycle-15 session, post-v2.4.30 ship + post-article-finder-wiring).
**Audience:** New Claude session, fresh context, resuming docpluck-iterate.
**Hard rule for this session:** ALL ground truths created in this session MUST go through `article-finder` (`ai-gold.py store` after each new extraction). Never produce a local-only gold. Never re-extract a paper that's already cached.

---

## TL;DR

The prior session shipped **v2.4.29** + **v2.4.30** (5 fix cycles total across G2/G15/G17/G6 etc.) AND built the cross-project AI-gold storage infrastructure (`~/.claude/skills/article-finder/ai-gold.py` + `~/ArticleRepository/ai_gold/` with 16 papers cached, 1.2 MB). Your job is to **continue the fix cycles on docpluck's corpus**, using the cached golds (no re-extraction needed for the 16 already-stored papers).

### Start by

1. **Confirm prod is at v2.4.30** after Vercel + Railway auto-deploy + auto-bump PR merges:
   ```bash
   curl -s https://extraction-service-production-d0e5.up.railway.app/_diag | python -m json.tool | head -8
   ```
   Expected: `"docpluck_version": "2.4.30"`. If still on v2.4.28, check + merge open PRs:
   ```bash
   gh pr list --repo giladfeldman/docpluckapp --state open --search "v2.4.29 OR v2.4.30"
   ```

2. **Verify the AI-gold cache is reachable**:
   ```bash
   python ~/.claude/skills/article-finder/ai-gold.py stats
   ```
   Expected: 16 papers cached, ~1.2 MB total. If 0, something's broken — read the cross-project handoff at `~/ArticleRepository/docs/HANDOFF_2026-05-14_cross_project_ai_gold_unification.md` for context on the infrastructure.

3. **Run the Phase 0.8 mandatory smell-test** (skill SKILL.md, mandatory pre-cycle):
   - Ground-truth source: confirm `ai-gold.py` cache exists. Never use pdftotext as truth.
   - Cross-output coverage: enumerate which views the next cycle's fix affects.
   - Recurrence: search LEARNINGS for prior corrections; don't repeat.
   - Coverage matrix: `cat tmp/corpus-coverage.md` for state.
   - Defect-density: are 3+ recent cycles in the same root-cause class?
   - Postmortem-pending: any TRIAGE class missing a methodology postmortem?

4. **Pick the next cycle from TRIAGE** (`docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md`). Recommended order below.

---

## Where you are in the iteration

| Version | Cycles | Status |
|---|---|---|
| v2.4.28 (entry state) | 14 prior cycles | Shipped under pdftotext-baseline verification (catastrophic methodology failure — postmortem in `.claude/skills/docpluck-iterate/LEARNINGS.md`) |
| **v2.4.29** | 15a (Greek/math/super/sub preservation) + 15b (comma-thousands) + 15c (NFC composition) | Source-glyph preservation. New `preserve_math_glyphs` flag in `normalize_text`. 11 regression tests. 153 D5 tests still pass. |
| **v2.4.30** | 15d (orphan Roman-numeral consumption) | `_fold_orphan_roman_numerals_into_headings` post-processor. ieee_access_2 now has `## I. INTRODUCTION` / `## II. METHODOLOGY` / `## V.: SUPPLEMENTARY INDEX`. III./IV. are partial (queued for 15i). 5 new tests. |

**Next:** Cycles 15n → 15e → 15f → 15g → 15h → 15i → 15j → 15k → 15l → 15m (~10 cycles remaining in the TRIAGE).

---

## Recommended cycle order + brief notes

### Cycle 15n — Figure caption placeholder regression (FIRST priority)

**The defect:** v2.4.29's `## Figures` trailing-appendix block now shows `*Figure N. FIGURE N.*` placeholders for ieee_access_2's 37 captions instead of full-text captions. v2.4.28 had full captions. This is a NEW REGRESSION introduced by v2.4.29 — fix it before it propagates.

**Layer:** `docpluck/extract_structured.py::_extract_caption_text` chain. Specifically one of:
- `_strip_duplicate_uppercase_label`
- `_trim_caption_at_chart_data`
- `_trim_caption_at_running_header_tail`
- `_trim_caption_at_body_prose_boundary`

**Diagnostic strategy:** the INLINE figure captions (in body `### Figure N` blocks) ARE full-text and Unicode-correct. Only the trailing-section copies degraded. So `f["caption"]` is being stored as the trimmed-too-far form, and the inline emit must reconstruct from elsewhere. Trace:

```python
from docpluck.extract_structured import extract_pdf_structured
from pathlib import Path
r = extract_pdf_structured(Path('../PDFextractor/test-pdfs/ieee/ieee_access_2.pdf').read_bytes())
for f in r['figures'][:5]:
    print(f"label={f['label']!r}")
    print(f"caption={f['caption']!r}")
    print()
```

If `caption` is short (just `"FIGURE 6."`), that's the bug. Find which trim function is producing the over-strip; likely `_strip_duplicate_uppercase_label` interaction with NFC-composed input from v2.4.29's NFC step (Cycle 15c).

**Why this is the right next cycle:** small surface (one function chain), regression I introduced, ieee_access_2 has gold cached so verification is free.

### Cycle 15e — Page-header leak in equations

**The defect:** ieee_access_2 equation `(2)` renders as `Page 4 (2)` (the `Page 4` running-header line is fused to the equation number). Gold has just `(2)`.

**Layer:** F0 layout-aware strip OR normalize.py running-header pattern.

**Fix sketch:** Add a `^Page\s+\d+\s+(?=\()` strip pattern OR extend F0 layout strip to detect page-header lines that bleed into math.

### Cycle 15f — Body-stream table fragments duplicating structured tables

**The defect:** every table in xiao / amj_1 / amle_1 is emitted TWICE — once as broken plain-text dump in body, once as HTML at end. amle_1 has 13 tables × 2 = 26 emissions; pollutes Discussion section.

**Layer:** `docpluck/render.py` table-anchoring step. When a structured table is anchored inline, the body-stream cell content for that table region should be SUPPRESSED.

### Cycle 15g — pdftotext glyph collapse (HIGHEST IMPACT, RISKIEST)

**The defect:** pdftotext upstream is mapping `=` → `5`, `<` → `,`, `−` (U+2212) → `2`, `×` → `3`, `α` → `a`, `χ²` → `x2`, `Δ` → `D`, `η_p²` → `hp2`, `R²` → `R2`. So `b = −0.54` reads as `b 5 20.54` — sign-FLIPPED. **Every statistical paper is corrupt.**

**Layer:** pdftotext upstream. The .txt itself has these substitutions. Diagnostic-confirmed.

**Fix strategy options (evaluate before coding):**
- **A. Context-aware W-step in normalize.py** — detect stat-context patterns (`b 5`, `t 5`, `p 5`, `df 5`, `r 5`, `p ,`) and correct. Risk: false positives where `5` is a legitimate digit. Use narrow regex anchors with stat-keyword neighbors.
- **B. Layout-channel rescue** — use pdfplumber's per-character font info to identify math glyphs and patch them into pdftotext output. More accurate but heavier.

Recommend A with narrow anchors. Will need exhaustive D5-style regression coverage.

### Cycle 15h — Table cell defects (multi-paper, structural)

**The defects:**
- xiao Tables 1/2/6: phantom empty columns (Camelot stream-flavor whitespace gaps)
- xiao Table 6: **numerical-data SWAP** — shows `4.91 (1.54)` but gold/PDF say `4.70 (1.64)` (published-stat corruption!)
- xiao Table 8: fenced unstructured contaminated with running-header
- amj_1 Tables 1/2: caption-bleed into thead
- amj_1 Table 3: missing ΔF/R²/ΔR² rows
- amj_1 Table 4: essentially empty `<table>` (data dumped to body stream)
- amle_1 Tables 3-11: caption-bleed in thead
- amle_1 Table 13: column fusion `<td>Michigan State6Harvard University</td>`
- ieee_access_2 Table 1: 3×8 → 1×6 fused cells

**Layer:** `docpluck/tables/cell_cleaning.py`, `docpluck/tables/render_html.py`, `docpluck/extract_structured.py`. Multi-cycle work.

### Cycles 15i / 15j / 15k / 15l / 15m

See `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md` for full detail.

---

## How to run a cycle (the article-finder-wired protocol)

This is the canonical Phase 5d workflow. Memorize it.

### Step A — Check the shared gold cache FIRST

```bash
# All 16 papers from the prior session are already cached. For these,
# the check returns the path + exit 0 — skip the subagent dispatch.
python ~/.claude/skills/article-finder/ai-gold.py check <key>
```

Valid keys (all accepted by the script):
- `xiao_2021_crsp`, `amj_1`, `amle_1`, `ieee_access_2` (canonical 4)
- `jama_open_1`, `ip_feldman_2025_pspb`, `sci_rep_1`, `am_sociol_rev_3`, `bmc_med_1`, `bjps_1` (wave 1)
- `demography_1`, `chan_feldman_2025_cogemo`, `nat_comms_1`, `bmj_open_1`, `brjpsych_1`, `amd_1` (wave 2)

For papers NOT in this list, the check returns exit 1 (miss).

### Step B — On miss: dispatch a gold-extraction subagent

Use the prompt template at `.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md` Step 1b. Discipline:
- AT MOST 3 Read calls with `pages="1-N"` chunks (cycle-15 lesson: more = image-dimension limit).
- Subagent writes to `tmp/<paper>_gold.md`.
- If `Read` fails with image-dimension error, fall back to `pypdfium2` rendering PNGs visually (verified working in cycle-15 session).

### Step C — After miss-dispatch: STORE the new gold (MANDATORY)

```bash
python ~/.claude/skills/article-finder/ai-gold.py store <key> tmp/<paper>_gold.md \
    --source-pdf <abs path to PDF> \
    --version v1 \
    --by "docpluck-iterate@$(date +%Y-%m-%d)" \
    --note "Phase 5d gold extraction for cycle <N>"
```

**Skipping store = next cycle re-pays the 3-15min subagent cost.** Don't skip.

### Step D — Render at current HEAD

```bash
DOCPLUCK_DISABLE_CAMELOT=1 PYTHONUNBUFFERED=1 python -u -c "
from pathlib import Path
from docpluck.render import render_pdf_to_markdown
md = render_pdf_to_markdown(Path('<pdf>').read_bytes())
Path('tmp/<paper>_v<version>.md').write_text(md, encoding='utf-8')
"
```

(Camelot can be left enabled for cycles that touch table extraction; otherwise the env var speeds the render up substantially.)

### Step E — Dispatch verifier subagent

Use the prompt template at `.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md` Step 4. Inputs:
- GROUND TRUTH: path returned by `ai-gold.py check` or `ai-gold.py get <key>`
- RENDERED: `tmp/<paper>_v<version>.md`
- DIAGNOSTIC (optional): `tmp/<paper>_pdftotext.txt` (only for layer-attribution after a finding)

### Step F — Implement the fix

One root-cause class per cycle (per rule 0e). Write a regression test in the same edit (real-PDF preferred). Run `pytest` to confirm.

### Step G — Bump versions + commit + tag + push

```bash
# Bump __version__, pyproject.toml version, CHANGELOG.md, NORMALIZATION_VERSION (if normalize changed),
# SECTIONING_VERSION (if sections changed).
git add <changed files>
git commit -m "release: vX.Y.Z — <cycle summary>"
git tag vX.Y.Z
git push origin main && git push origin vX.Y.Z
```

Auto-bump bot opens a PR in `docpluckapp` ~30s after tag push; merge it.

### Step H — Phase 9 self-improvement (mandatory)

Per SKILL.md Phase 9, 9 steps:
1. Append cycle journal entry to `.claude/skills/docpluck-iterate/LEARNINGS.md`
2. Append project lesson if applicable
3. Update run-meta JSON
4. Refresh `tmp/iterate-todo.md`
5. Refresh `tmp/corpus-coverage.md`
6. Write a methodology postmortem if the cycle uncovered a defect class N prior cycles missed
7. User-correction ratchet if applicable
8. Skill-amendment proposal if same theme hit 2+ LEARNINGS
9. Verify Phase 0.8 smell-test invariants hold at cycle end

---

## State at handoff

```
$ git log --oneline -8
8e19e12 skills(iterate): wire Phase 5d to article-finder for long-term gold storage
7c7dd28 docs: handoff + TRIAGE updates (post v2.4.30)
5a2a648 release: v2.4.30 — Cycle 15d orphan Roman-numeral consumption (G6)
4a0152f skills(iterate): bake self-audit + methodology smell-test into the loop
aa62e3c docs(handoff): Phase-5d AI-gold audit + v2.4.29 source-glyph preservation
216a917 release: v2.4.29 — source-glyph preservation in render path (G2/G7/G12/G15/G17/G21)
```

**Library tags:** v2.4.29, v2.4.30 (both pushed). Auto-bump PRs may be pending in `docpluckapp`.

**Tests:** 366 pass / 1 skip / 1 warning (the III./IV. orphan-numeral limitation, intentionally documented). 153 D5 audit tests still pass.

**AI gold cache:** 16/101 papers (~16% corpus coverage). Cross-publisher: ≥1 paper per publisher.

**Pre-existing failures carrying forward:**
- 2× `test_sections_golden.py` failures (synthetic-fixture char-offset drift; pre-existed at HEAD before this session; queued for cycle 15i golden regeneration via `DOCPLUCK_REGEN_GOLDEN=1`).

---

## Files modified across the cycle-15 sessions (cumulative)

**docpluck library repo:**
- `docpluck/normalize.py` — preserve_math_glyphs flag, A5/A3a/A3/A3c gating, NFC composition. NORMALIZATION_VERSION 1.9.0.
- `docpluck/sections/__init__.py` — preserve_math_glyphs forwarded
- `docpluck/render.py` — preserve_math_glyphs opt-in; orphan Roman-numeral consumption (`_fold_orphan_roman_numerals_into_headings`); `_ROMAN_PREFIX_HEADING_RE` for inline form
- `docpluck/__init__.py`, `pyproject.toml` — 2.4.28 → 2.4.30
- `CHANGELOG.md` — v2.4.29 + v2.4.30 blocks
- `CLAUDE.md` — Ground-truth hard rule (AI multimodal PDF read)
- `tests/test_preserve_math_glyphs_real_pdf.py` — NEW 13 tests
- `tests/test_roman_numeral_section_promote_real_pdf.py` — NEW 5 tests
- `tests/test_all_caps_section_promote_real_pdf.py` — updated for cycle-15d-compatible expectation
- `tests/test_d5_normalization_audit.py` — version test relaxed to 1.9.x
- `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md` — NEW (24 root-cause groups)
- `docs/HANDOFF_2026-05-14_phase_5d_gold_audit_v2_4_29.md` — NEW
- `docs/HANDOFF_2026-05-14_full_corpus_iteration_v2_4_30.md` — NEW
- `docs/HANDOFF_2026-05-14_continue_iterations_v2_4_30_to_15n.md` — NEW (this file)
- `.claude/skills/docpluck-iterate/SKILL.md` — Phase 0.8/0.9/5g, Phase 9 expanded 5→9 steps, article-finder wiring
- `.claude/skills/docpluck-iterate/LEARNINGS.md` — session postmortem + per-cycle entries
- `.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md` — full protocol rewrite + Step 1a/1b/1c (CHECK / extract / STORE)
- `.claude/skills/docpluck-qa/SKILL.md` — 7f + 7g checks
- `.claude/skills/docpluck-review/SKILL.md` — Hard rules 15a.1-15a.7
- `tmp/corpus-coverage.md` — coverage matrix (gitignored; durable on disk)

**Article-finder skill (`~/.claude/skills/article-finder/`):**
- `ai-gold.py` — NEW CLI utility (check / get / store / list / stats)
- `SKILL.md` — documented `ai_gold/` directory + `ai-gold.py` + coexistence with deterministic `ground_truth/`

**docpluckapp (app) repo (commit `4d022f8` on master):**
- `frontend/src/components/document-workspace.tsx` — table-HTML pass-through fix

**Shared article repository (`~/ArticleRepository/`):**
- `ai_gold/` — NEW directory; 16 papers cached, ~1.2 MB
- `docs/HANDOFF_2026-05-14_cross_project_ai_gold_unification.md` — cross-project unification handoff (PARALLEL TRACK)

**Memory (`~/.claude/projects/.../memory/`):**
- `feedback_ground_truth_is_ai_not_pdftotext.md` — NEW
- `feedback_full_corpus_self_learning.md` — NEW

---

## Parallel track — cross-project AI gold unification

A separate handoff at `~/ArticleRepository/docs/HANDOFF_2026-05-14_cross_project_ai_gold_unification.md` describes a parallel work track: discover existing AI-extracted ground truths across all this user's MetaScience projects (ESCImate, metaESCI, Scimeto, ScienceArena, CitationGuard, etc.), migrate them into the shared `ai_gold/` repository, and wire each project's verification skill to use `ai-gold.py`. **That track is for a different session — don't conflate it with the docpluck-iterate continuation here.**

If you find that someone else has progressed the cross-project track, you may have a richer cache when you start. Run `ai-gold.py stats` to see current state.

---

## Mandatory pre-reading

Before any cycle:

1. This handoff: `docs/HANDOFF_2026-05-14_continue_iterations_v2_4_30_to_15n.md`
2. The TRIAGE doc (canonical work queue): `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md`
3. CLAUDE.md — especially the ground-truth + rule-0e hard rules
4. `.claude/skills/docpluck-iterate/SKILL.md` — Phase 0.8 smell-test, Phase 0.9 coverage matrix, Phase 5d (now article-finder-wired), Phase 9 9-step self-improvement
5. `.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md` — Phase 5d protocol with article-finder integration
6. `.claude/skills/docpluck-iterate/LEARNINGS.md` — session postmortem + per-cycle entries (rule 0e + glyph-preservation lessons + Roman-numeral lessons)
7. Memories: `feedback_ground_truth_is_ai_not_pdftotext`, `feedback_full_corpus_self_learning`, `feedback_fix_every_bug_found`, `feedback_ai_verification_mandatory`
8. `tmp/corpus-coverage.md` — current coverage state

---

## Hard rules for this session (DO NOT VIOLATE)

1. **Ground truth = AI multimodal PDF read.** Pdftotext / Camelot / pdfplumber are diagnostics only. CLAUDE.md hard rule.
2. **All new ground truths go through article-finder.** Never produce a local-only gold. `ai-gold.py check` first; `ai-gold.py store` after any new extraction.
3. **One root-cause class per cycle.** Don't bundle unrelated fixes. The shared "source-glyph preservation" was a legitimate bundle (one user-facing intent); arbitrary bundling is not.
4. **Add a regression test in the same commit.** Real-PDF test preferred; synthetic-only does not satisfy.
5. **Bump version on every release.** Patch for fixes; minor for behavior changes that alter rendered byte content.
6. **Phase 5d AI-gold verify before declaring a cycle done.** This is the keystone gate. Skipping it is what produced the 14-cycle methodology failure.
7. **Phase 0.8 smell-test BEFORE any code change.** All 6 checks must pass or the cycle stops.
8. **Phase 9 self-improvement after every cycle.** All 9 steps. Skipping = lost signal.
9. **Rule 0e: never defer pre-existing defects.** If Phase 5d surfaces N defects, fix all N in the same run (group by root cause).
10. **Methodology meta-audit every 3rd cycle.** Surface any drift; repair before continuing.

---

## Suggested session shape

**~3-4 cycles per session is sustainable** (cycle-15 session shipped 5 + infra; that was at the limit). Recommended:

- Cycle 1: Pick 15n (figure caption placeholder regression). Use cached ieee_access_2 gold. Investigate `_strip_duplicate_uppercase_label` chain. Ship as v2.4.31.
- Cycle 2: Pick 15e (page-header in equations). Use cached ieee_access_2 gold. Add F0 / running-header strip pattern. Ship as v2.4.32.
- Cycle 3: Pick 15f (body-stream table dupes). Multi-paper investigation across amj_1 + amle_1 + xiao. Use cached golds. Ship as v2.4.33.
- (Optional cycle 4 if budget allows): begin 15g (pdftotext glyph collapse) — biggest impact, plan + first iteration.

**Stop conditions** (per skill Phase 10):
- Time:60m default if no other goal.
- Must-stop: 26-paper baseline regresses; 3 consecutive PARTIAL/REVERT/FAIL; prod `/_diag` doesn't reach new version after 8 min.

**Soft-stop (surface and ask):** diminishing returns; TRIAGE empty.

End the session with:
- All shipped cycles released as tagged versions
- LEARNINGS.md updated per cycle
- A handoff doc (template: this file's structure) for the next session
- `corpus-coverage.md` refreshed

---

The cycle-15 session got us from "no methodology" to "methodology baked in + 16 papers cached + 2 shipped releases (5 cycles)." Your session should get us to "5+ more shipped releases + ~30 papers cached + the worst defect classes closed."

Continue iterating. All ground truths through article-finder. PDFs are immutable; cached golds are durable. Don't re-extract what's already cached. Don't ship a fix without AI-gold verification. Don't slide back to pdftotext-as-truth.

Good luck.
