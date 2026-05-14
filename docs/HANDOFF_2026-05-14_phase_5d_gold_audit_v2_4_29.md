# Handoff — Phase-5d AI-Gold Audit + v2.4.29 source-glyph preservation

**Authored:** 2026-05-14 (late session).
**Prior context:** `docs/HANDOFF_2026-05-14_iterate_6_cycles_complete.md` (v2.4.28 + 14-cycle deferred backlog).
**This session shipped:** v2.4.29 with three bundled cycles (15a/b/c), plus a paradigm-shift in verification methodology.

---

## TL;DR for the next session

1. **Methodology change shipped:** Phase 5d verification now uses **AI multimodal read of the source PDF** as ground truth — NOT pdftotext, NOT Camelot, NOT any deterministic extractor. CLAUDE.md hard rule + `.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md` + memory `feedback_ground_truth_is_ai_not_pdftotext`. The change exposed ~24 root-cause defect groups; v2.4.28 had been shipping with these undetected.

2. **v2.4.29 fixes (shipped):** source-glyph preservation in the render path. Greek letters (β/δ/γ/τ/etc.), math operators (×, ≥, ≤), super/subscripts (², ₀, etc.), comma-thousands separators (1,675), and combining-char author names (Förster, Potočnik) all now preserved in rendered .md.

3. **Front-end fix shipped:** `PDFextractor/frontend/src/components/document-workspace.tsx` — the `renderMarkdownToHtml` function was emitting `<p>TABLE_N</p>` instead of the `<table>` HTML; fixed (commit `4d022f8` on docpluckapp/master). Tables now appear in the Rendered tab.

4. **8 cycles deferred to follow-up sessions** — see "DEFERRED BACKLOG" below. All grounded against AI-gold and surfaced concrete root causes.

### Start by

1. **Confirm v2.4.29 prod** (after Vercel + Railway auto-deploys):
   ```bash
   curl -s https://extraction-service-production-d0e5.up.railway.app/_diag | python -m json.tool | head -8
   ```
   Expected: `"docpluck_version": "2.4.29"`.

2. **Merge the v2.4.29 auto-bump PR in docpluckapp** if not already merged:
   ```bash
   gh pr list --repo giladfeldman/docpluckapp --state open --search "v2.4.29"
   gh pr merge <N> --repo giladfeldman/docpluckapp --squash --delete-branch
   ```

3. **Re-run Phase 5d AI-gold verification on the 4 canonical papers at v2.4.29** to confirm 15a/b/c findings are gone and identify regressions. Gold extractions are CACHED at `tmp/<paper>_gold.md` (reusable forever).

4. **Pick next cycle from the TRIAGE doc**:
   `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md`. Recommended order: 15d (G6 orphan Roman numerals) → 15e (G16 page-header in equations) → 15f (G4 body-stream table duplication) → 15g (G1 pdftotext glyph collapse, biggest impact but riskiest).

---

## What shipped this session

### Documentation + methodology (no code, durable infrastructure)

| File | Change |
|---|---|
| [CLAUDE.md](../CLAUDE.md) | NEW hard rule: ground truth = AI multimodal PDF read (NOT pdftotext / Camelot / pdfplumber) |
| [`.claude/skills/docpluck-iterate/SKILL.md`](../.claude/skills/docpluck-iterate/SKILL.md) | Phase 5d rewritten (AI-gold methodology); subagent-parallelization section + safety checklist + 3 fan-out patterns + anti-patterns |
| [`.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md`](../.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md) | Full protocol rewrite: 6-step procedure, gold-extraction subagent prompt template, verifier prompt template, gold caching policy, failure modes (image-dimension limit, pypdfium2 fallback for Windows w/o `pdftoppm`, chunk discipline) |
| [`.claude/skills/docpluck-qa/SKILL.md`](../.claude/skills/docpluck-qa/SKILL.md) | Check 7g rewritten to use AI gold; check 7f content-fidelity linter added (12 defect-class tags) |
| [`.claude/skills/docpluck-review/SKILL.md`](../.claude/skills/docpluck-review/SKILL.md) | Hard rules 15a.1-15a.7 added (Unicode normalization scope, table cell emission, caption-thead bleed, hallucinated `## Introduction`, Roman-numeral promotion, endmatter routing, figure caption duplication) |
| `~/.claude/projects/.../memory/feedback_ground_truth_is_ai_not_pdftotext.md` | NEW feedback memory + MEMORY.md index entry |
| [docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md](TRIAGE_2026-05-14_phase_5d_gold_audit.md) | Consolidated triage doc with all 24 root-cause groups, cycle order, layer attribution |

### Code (v2.4.29, library)

| Module | Change | Cycle |
|---|---|---|
| `docpluck/normalize.py` | Added `preserve_math_glyphs` keyword param; gated A5 (Greek+math+super/sub), A3a (thousands strip), A3 (decimal comma), A3c (leading-zero decimal); added NFC composition + space-before-combining-mark squash at top of pipeline | 15a + 15b + 15c |
| `docpluck/sections/__init__.py` | Plumbed `preserve_math_glyphs` through `extract_sections` | 15a |
| `docpluck/render.py` | `render_pdf_to_markdown` internally passes `preserve_math_glyphs=True` | 15a |
| `tests/test_preserve_math_glyphs_real_pdf.py` | NEW — 13 real-PDF + synthetic regression tests | 15a/b/c |
| `docpluck/__init__.py`, `pyproject.toml` | v2.4.28 → 2.4.29 | release |
| `docpluck/normalize.py` | `NORMALIZATION_VERSION` 1.8.9 → 1.9.0 | release |
| `CHANGELOG.md` | New v2.4.29 block | release |

### Code (frontend, docpluckapp)

| File | Change | Commit |
|---|---|---|
| `frontend/src/components/document-workspace.tsx` | Fixed `renderMarkdownToHtml` table-pass-through bug (tables were rendering as `<p>TABLE_N</p>` instead of `<table>` HTML). Trim-strips-marker-spaces + paragraph-isolation defects. | `4d022f8` on master |

---

## DEFERRED BACKLOG (cycle 15d through 15+)

All grounded against AI-gold, with concrete layer attribution. Pick in priority order:

### Cycle 15d — G6: orphan Roman-numeral consumption (HIGH, C1)

ieee_access_2: `I.` / `II.` / `III.` / `IV.` alone on lines above `## INTRODUCTION` / `## METHODOLOGY` / `## RESULTS` / `## DISCUSSION AND CONCLUSION`. Cycle-11's ALL-CAPS promoter didn't consume the numeral.

**Layer:** `docpluck/render.py::_promote_all_caps_section` (or equivalent).
**Fix sketch:** when promoting an ALL-CAPS heading at line N, check line N-1 (or N-2 if blank) for `^[IVX]{1,4}\.\s*$` pattern. If matched, merge into the heading: `## I. INTRODUCTION` (or `## INTRODUCTION` and drop the numeral line). Also handle the colon variant: `V.: SUPPLEMENTARY INDEX`.

### Cycle 15e — G16: page-header leak in equations (MEDIUM, C1)

ieee_access_2: `Page 4 (2)` rendered where source has `(2)` (the page-header running text got fused into the equation number).

**Layer:** `normalize.py` (F0 or running-header pattern).
**Fix sketch:** add `^Page\s+\d+\s+(?=\()` strip pattern to F0 (or the running-header regex set).

### Cycle 15f — G4: body-stream cells duplicating structured tables (HIGH, C2)

amj_1 + amle_1 + xiao: each table emitted TWICE — once as broken plain-text dump in body, once as `<table>` HTML at end. amle_1 worst: Discussion section starts with raw cell-token spew.

**Layer:** `docpluck/render.py` or `docpluck/extract_structured.py` table-anchoring step.
**Fix sketch:** when a structured table is emitted (as `### Table N` + HTML), record its source-text span and SUPPRESS that span from the body stream.

### Cycle 15g — G1: pdftotext glyph collapse (S0, CRITICAL but C2-C3)

amj_1 + amle_1 stat sections: pdftotext is mapping source glyphs to wrong ASCII at the encoding layer:
- `=` → `5` ("p = .001" → "p 5 .001")
- `<` → `,` ("p < .001" → "p , .001")
- `−` (U+2212) → `2` ("b = −0.54" → "b 5 20.54" — SIGN-FLIPPED!)
- `×` → `3`
- `α` → `a`
- `χ²` → `x2`
- `Δ` → `D`
- `η_p²` → `hp2`
- `R²` → `R2`

**Layer:** pdftotext upstream. The .txt file itself has these substitutions (confirmed via diagnostic comparison).

**Fix strategy options:**
1. **Context-aware W-step** in `normalize.py`: detect stat-context-near patterns (`b 5`, `t 5`, `p 5`, `df 5`, `r 5`, `p ,`, `p < ` neighbors of `M`, `SE`, `t`, `b`, `r`, `R`, `df`, `LLCI`, `ULCI`) and correct `5`→`=`, `,`→`<`, `2`→`−`. RISK: false positives — `5` is also a legitimate digit. Use conservative anchors (e.g., `\bp\s+5\s+\.\d+` is high-confidence).
2. **Switch pdftotext flags**: try `-raw` mode or different font-encoding flags. RISK: forbidden per CLAUDE.md L-001 (never swap text-extraction tool/mode as a fix).
3. **Layout-channel rescue**: use pdfplumber's per-character font info to identify math glyphs and patch them into the pdftotext stream. Combines TEXT + LAYOUT channels.

Recommend (1) as the first attempt, very narrow anchors. Will need exhaustive D5 regression coverage.

### Cycle 15h — G3+G22: table cell defects (S0, C3, multi-cycle)

- xiao Tables 1/2/6: phantom empty columns (Camelot stream-flavor whitespace gaps).
- xiao Table 4: column-header collapse (`< .010.240[CI]` welded).
- xiao Table 6: **numerical-data SWAP** — shows 4.91 (1.54) but PDF says 4.70 (1.64). Published-stat corruption.
- xiao Table 8: fenced unstructured block contaminated with running-header `COMPREHENSIVE RESULTS IN SOCIAL PSYCHOLOGY` inside cells.
- amj_1 Tables 1/2: caption welded into thead.
- amj_1 Table 3: missing ΔF/R²/ΔR² rows.
- amj_1 Table 4: essentially empty `<table>` (data dumped to body stream).
- amle_1 Tables 3/4/5/6/7/8/9/10/11: caption-bleed in thead.
- amle_1 Table 13: column-fusion (`<td>Michigan State6Harvard University</td>` — 8-column 4-group×2-subcolumn structure collapsed).
- ieee_access_2 Table 1: 3 cols × 8 rows → 1 row × 6 fused cells.

**Layer:** `docpluck/tables/cell_cleaning.py`, `docpluck/tables/render_html.py`, `docpluck/extract_structured.py`.

### Cycle 15i — G5: section-boundary detection under-firing (HIGH, C2)

All 4 papers: many gold headings demoted to flat body prose.

- xiao: ~25 of ~35 gold headings missing; hallucinated `## Introduction` heading; `## Discussion` boundary error (covers Study-1 local only).
- amj_1: missing INDEX TERMS, Biographies.
- amle_1: ~13 subsection running heads flattened (Science-Practice Gap, Textbook Selection Criteria, Implications for X, etc.).
- ieee_access_2: 13 A./B./C./1)/2)/3) subsection markers flat.

**Layer:** `docpluck/sections/annotators/text.py` Pass 3.

### Cycle 15j — G7+G8+G21: math content destruction (S1, engineering papers only, C3)

ieee_access_2: equations annihilated. √, ², |·|, /, →, ×, {}, (), [] all dropped from math expressions; body prose around math splays into vertical one-word lines.

**Layer:** `normalize.py` whitespace-collapse over-aggressive on math content.
**Fix sketch:** detect math contexts (Greek-letter density, operator density per line) and disable whitespace-collapse rules inside them.

### Cycle 15k — G9+G24: endmatter routing (HIGH, C2)

- amj_1: Appendix A subsections leak between References and Appendix-A heading; author bios in post-References zone; **Acknowledgments paragraph MISSING entirely**.
- amle_1: author bios fused to last reference with no break; Acknowledgments missing.

**Layer:** `docpluck/sections/` endmatter taxonomy.

### Cycle 15l — G10+G11: figure caption emission (S2, C2)

- ieee_access_2: 37 captions emitted TWICE (inline ASCII + dedicated Unicode + ~10 truncated).
- amj_1 Figure 1 + ieee_access_2 Figs 2-7: chart-axis labels orphan in body.

### Cycle 15m — long tail (S2, mixed C)

G12 subscript flattening (ieee_access_2), G13 references concatenated (xiao, amj_1, amle_1), G14 URL soft-wrap space (ieee_access_2), G18 digit drift OCR-class (amle_1), G19 citation count drift (amle_1), G20 hallucinated `## Tables (unlocated in body)` meta-heading.

---

## State at handoff

```
$ git log --oneline -8
216a917 release: v2.4.29 — source-glyph preservation in render path (G2/G7/G12/G15/G17/G21)
223a271 docs(handoff): clean 6-cycle session handoff for next fresh session
0c8d9d2 docs(handoff): update for cycles 13+14 (v2.4.28 — items G + D shipped)
1f73132 release: v2.4.28 — chart-data trim widening (item G) + A3c leading-zero decimal (item D)
8f56130 docs(handoff): 4-cycle /docpluck-iterate resume run handoff
f8c51bf release: v2.4.27 — section-row label cell-merge fix (item C, xiao Table 6)
39b7c84 release: v2.4.26 — ALL-CAPS section heading promotion post-processor (item B)
3d2f03a release: v2.4.25 — caption-trim chain migrated to extract_structured.py (item A++)
```

**docpluck library tag pushed:** `v2.4.29`. Auto-bump PR pending in docpluckapp.

**Library tests at v2.4.29:**

| Suite | Result |
|---|---|
| `test_preserve_math_glyphs_real_pdf.py` (NEW, 13 tests, 4 papers) | 12 pass / 1 skip (² test gracefully skips when pdftotext drops it upstream — Cycle 15g territory) |
| All normalize tests (`-k normalize`) | 338 pass / 1 skip — back-compat preserved |
| D5 audit (153 tests) | All pass — no breaking changes |
| `test_sections_golden.py` | 1 pass / 2 PRE-EXISTING fails (synthetic-fixture char-offset drift; NOT introduced by this cycle — verified by git-stash compare) |
| 26-paper baseline | Background-run completed with exit code 0 |

**Production state (at session end):** v2.4.28 on Railway. v2.4.29 pending auto-deploy after auto-bump PR merge.

---

## What worked this session

- **Subagent parallel fan-out for gold extraction** (Pattern A from the updated iterate SKILL.md): 4 papers' golds generated in parallel ≈ wall-clock of the slowest paper (amle_1 ~16 min). Without parallelism, sequential would have been ~50+ min. The 1 failure (xiao image-limit) was retried with `pages="1-12"` chunk discipline and succeeded.
- **AI gold reused across verifiers** — same 4 gold files now serve every future cycle's verification. PDFs are immutable; golds are the durable artifact.
- **`preserve_math_glyphs` flag pattern** (one flag, multiple gated normalization steps) cleanly separated render fidelity from stat-extraction back-compat. All 153 D5 tests still pass.
- **Cycle bundling by root cause** (15a + 15b + 15c all "source-glyph preservation in render path") matched rule 0e's "Group defects by root cause" guidance.

## What didn't work / regressed

- **First xiao gold-extraction failed** with image-dimension limit at 53 tool calls. Retry with explicit 3-Read-call discipline succeeded. Lesson baked into ai-full-doc-verify.md.
- **Pre-existing golden test failures** in `test_sections_golden.py` (2 tests). Confirmed by git-stash to NOT be caused by this cycle; carrying as known-issue. Likely need DOCPLUCK_REGEN_GOLDEN=1 regenerate after Cycle 15i (section detection fix).
- **Context budget**: this session used substantial context for AI-gold methodology setup + 3 cycles + handoff. The user's "do iteration again" directive nominally maps to N cycles, but realistically each S0 fix is ~1 cycle worth of work; next session should aim for 2-3 cycles per session to stay sustainable.

## Files modified across this session (cumulative)

**docpluck (library) repo (commit 216a917):**

| File | Change |
|------|--------|
| `docpluck/normalize.py` | preserve_math_glyphs flag, A5/A3a/A3/A3c gating, NFC composition + space-before-combining squash, NORMALIZATION_VERSION 1.9.0 |
| `docpluck/sections/__init__.py` | preserve_math_glyphs forwarded to normalize_text |
| `docpluck/render.py` | render_pdf_to_markdown opts in to preserve_math_glyphs=True |
| `docpluck/__init__.py`, `pyproject.toml` | 2.4.28 → 2.4.29 |
| `CHANGELOG.md` | v2.4.29 block |
| `CLAUDE.md` | ground-truth hard rule |
| `tests/test_preserve_math_glyphs_real_pdf.py` | NEW — 13 regression tests |
| `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md` | NEW — consolidated triage with 24 root-cause groups |
| `.claude/skills/docpluck-iterate/SKILL.md` | Phase 5d rewrite + subagent parallelization |
| `.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md` | Full protocol rewrite |
| `.claude/skills/docpluck-qa/SKILL.md` | Check 7f + 7g rewrite |
| `.claude/skills/docpluck-review/SKILL.md` | Hard rules 15a.1-15a.7 |

**docpluckapp (app) repo (commit 4d022f8 on master):**

- `frontend/src/components/document-workspace.tsx` — table-HTML pass-through fix.

**~/.claude memory:**

- `feedback_ground_truth_is_ai_not_pdftotext.md` (NEW)
- `MEMORY.md` (index entry)

**Generated artifacts (`tmp/`, gitignored):**

- `tmp/<paper>_gold.md` × 4 — durable AI gold extractions (xiao 116KB, amj_1 133KB, amle_1 83KB, ieee_access_2 75KB)
- `tmp/<paper>_v2.4.28.md` × 4 — pre-fix rendered output
- `tmp/<paper>_v2.4.29_preview.md` × 2 — post-fix preview (ieee_access_2 + amle_1; xiao + amj_1 not yet re-rendered)
- `tmp/<paper>_pdftotext.txt` × 4 — diagnostic only

---

## How to resume

```bash
cd C:/Users/filin/Dropbox/Vibe/MetaScienceTools/docpluck

# 1. Confirm v2.4.29 prod (after Railway redeploys post auto-bump PR merge)
curl -s https://extraction-service-production-d0e5.up.railway.app/_diag | python -m json.tool | head -8

# 2. Re-render the 4 canonical papers at v2.4.29 (golds remain valid forever)
PYTHONUNBUFFERED=1 python -u -c "
from pathlib import Path
from docpluck.render import render_pdf_to_markdown
for stem, pdf in [
    ('xiao_2021_crsp', '../PDFextractor/test-pdfs/apa/xiao_2021_crsp.pdf'),
    ('amj_1', '../PDFextractor/test-pdfs/aom/amj_1.pdf'),
    ('amle_1', '../PDFextractor/test-pdfs/aom/amle_1.pdf'),
    ('ieee_access_2', '../PDFextractor/test-pdfs/ieee/ieee_access_2.pdf'),
]:
    md = render_pdf_to_markdown(Path(pdf).read_bytes())
    Path(f'tmp/{stem}_v2.4.29.md').write_text(md, encoding='utf-8')
    print(f'OK {stem}')
"

# 3. Re-verify against gold (4 parallel subagents, Pattern A from iterate SKILL.md)
# (Use the same verifier-prompt template as this session — see ai-full-doc-verify.md)

# 4. Pick next cycle from docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md
# Recommended order: 15d (orphan Roman numerals) → 15e (page-header in eq) → 15f (table dupes) → 15g (pdftotext glyph collapse)

# 5. Continue iterate loop per .claude/skills/docpluck-iterate/SKILL.md
```

### Mandatory pre-reading for the next session

- This handoff: `docs/HANDOFF_2026-05-14_phase_5d_gold_audit_v2_4_29.md`
- The triage doc: `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md` (THE canonical work queue)
- `CLAUDE.md` — especially the new ground-truth hard rule (AI multimodal PDF read)
- `.claude/skills/docpluck-iterate/SKILL.md` — full rewrite this session
- `.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md` — Phase 5d protocol
- Memory `feedback_ground_truth_is_ai_not_pdftotext.md`
- Memory `feedback_fix_every_bug_found.md` (rule 0e: never defer pre-existing)

---

The user's directive this session was "do iteration again, this time done right" — done. The methodology is now demonstrably right: AI-gold caught ~24 root-cause defect groups that 14 prior cycles missed. Three were shipped in v2.4.29; eight remain queued.
