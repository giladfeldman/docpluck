# Handoff — Canary-audit architecture + Cluster A/B/C landed (2026-05-25)

**Status: code uncommitted on `main`.** Audit infrastructure is built and working; the implementer-fix work is partial. v2.4.77 must NOT be tagged until the remaining 14 findings on `ip_feldman_2025_pspb` are cleared.

## What this session accomplished

The previous 4 attempts (2026-05-14 → 2026-05-23) to fix `ip_feldman_2025_pspb` defects all failed because the iterate-loop spine, while architecturally sound, depended on the implementing model invoking its own gate. The v2.4.72 bundled cycle bypassed the gate entirely by leaving skill-flow. This session built the structural answer: **Sonnet-via-Claude-Max independently audits Opus's work; the gate is enforced by an external model with no investment in the outcome.**

## Architecture delivered

| File | Purpose | Status |
|---|---|---|
| `~/.claude/projects/.../Vibe/memory/feedback_no_apis_only_claude_max.md` | Portfolio-wide hard rule | Written |
| `~/.claude/projects/.../docpluck/memory/feedback_no_apis_only_claude_max.md` | docpluck-local mirror | Written |
| `Vibe/CLAUDE.md` | Hard rule (Claude Max only) | Updated |
| `docpluck/CLAUDE.md` | Hard rule + Cluster A code references | Updated |
| `~/.claude/skills/_shared/iterate-loop/CROSS-PROJECT-ALERT-2026-05-23.md` | 2026-05-25 addendum: Claude Max only, no API | Updated |
| `~/.claude/skills/_shared/iterate-loop/audit-subagent-prompt.md` | Sonnet's audit-role prompt template | Created |
| `~/.claude/skills/_shared/iterate-loop/canary-audit.sh` | Orchestrator (intended for headless `claude -p`) | Created |
| `docpluck/.claude/skills/_project/canary.json::verification_protocol` | Per-project audit config (render command, defect taxonomy, gold view) | Extended |
| `docpluck/tools/render_for_audit.py` | Stable render-for-audit CLI (40s/paper) | Created |

## Hard rule established

**No Anthropic API. Ever.** All Claude calls (Opus + Sonnet, any purpose) go through Claude Max via:
1. `Agent` tool in-session with `model="sonnet"` (used this session for audits).
2. Headless `claude -p --model sonnet` from git hooks / scheduled tasks (blocked on `claude setup-token`, see below).
3. `mcp__scheduled-tasks__create_scheduled_task` invoking Claude Code.

The `canary-audit.sh` script is written for headless mode but blocked: `claude -p` returns 401 from bash subprocesses even though `claude auth status` shows `loggedIn:true, max`. **Required user action: run `claude setup-token` once in a regular terminal (creates a long-lived headless credential).** After that, the headless gate works.

## Validation: gate fires correctly on broken state

First audit at HEAD (v2.4.76, before any fixes) returned **FAIL with 10 findings on ip_feldman_2025_pspb**. The 4 user-named defects (Supplemental Materials hallucination, affiliation leak, mid-text Table 3 caption, Author Contributions split) all confirmed. **Sonnet additionally surfaced 6 defects no prior session had named** — most importantly that all 4 prior "we fixed it" handoffs had closed with these silently corrupting outputs.

## Code changes landed (uncommitted on main)

### Cluster A — terminator-aware promote/demote guards
- New `_prev_paragraph_is_sentence_terminated` helper in `docpluck/render.py` — prior paragraph must end with `.`/`!`/`?` (with optional close-quote) OR be a structural-boundary (heading/fence/italic-label). Otherwise candidate is a pdftotext column-wrap artifact.
- Wired into `_promote_isolated_titlecase_subsection_headings` (kills hallucinated `### Supplemental Materials` mid-Method).
- Mirror helper `_prior_paragraph_is_sentence_terminated` in `docpluck/sections/annotators/text.py` — used by Pass 1a AND Pass 1b canonical-heading detectors.
- `_demote_italic_label_with_comma_headings` updated to scan multi-line continuations for the first sentence terminator (fixes `## Data Availability` false section header).
- Net: **kills findings #2 (Supplemental Materials), #3 (Data Availability), #10 (Author Contributions split)**.

### Cluster B — inline duplicate Table caption suppressor
- New `_suppress_inline_duplicate_table_captions` in `docpluck/render.py`, modeled on the existing figure version. Wired into the render pipeline next to the figure call.
- Plus a "next paragraph is single-line short label" guard in `_promote_isolated_titlecase_subsection_headings` to reject cell-region promotions.
- Net: **kills finding #5 (mid-text Table 3 caption) and finding #4 (`### Exploratory open-ended` hallucinated heading)**.

### Cluster C — P0 affiliation patterns (partial)
- Added 2 new patterns to `docpluck/normalize.py::_PAGE_FOOTER_LINE_PATTERNS` for bare-university + name-led-affiliation shapes.
- Added 1 new pattern to `_FRONTMATTER_LEAK_PARA_PATTERNS` for multi-line corresponding-author paragraphs.
- Net: **most of finding #1 cleared; "Fu Lam, Hong Kong SAR." fragment line 37 still remains** (paragraph-level matcher doesn't reach this orphaned wrap-tail).

### Cluster D-partial — phantom-guard prose-in-`<th>` detection (didn't fire)
- Extended `_strip_phantom_camelot_tables` with a `th_section_leak` detector: when a `<th>` cell contains ≥8 words including ≥3 function words AND ≥2 verb-shape words, treat as Discussion-body bleed.
- Logic landed but **didn't fire on Table 10** (need to debug — possibly the verbosity heuristics need tuning).

### PSPB-style subsection heading promotion
- Relaxed `blank_after` requirement in `_promote_isolated_titlecase_subsection_headings` when next line is body prose with no blank between (Sage/APA layout style).
- Carved out `## heading` prefix from the "prev structural markup" reject — `## Introduction` IS valid prior context for `### Background` promotion.
- Net: **all of `### Background`, `### The Misestimation of Others' Emotions`, `### Original Hypotheses…`, `### Extensions`, `### Participants`, `### Prevalence Estimate Errors`, `### Intensity Estimate Errors`, `### Replication: Prevalence`, `### Limitations and Future Directions`, etc. now promoted correctly**.

## Final audit verdict (v9)

`tmp/audit-smoke/ip_feldman_v9.md` audited via Sonnet — **FAIL, 14 findings remaining**:

### Of the original 10 findings:
- ✅ **5 CLEARED**: #2 Supplemental Materials, #3 Data Availability, #4 Exploratory open-ended, #5 mid-text Table 3 caption, #10 Author Contributions split.
- ❌ **5 PERSISTENT**: #1 affiliation leak (mostly cleared, 1 fragment), #6 Table 3 malformed, #7 Table 4 truncated, #8 Table 5 (status: partially fixed by sectioning, structural defects remain), #9 Table 10 (defect shape changed — now has NO body, was previously polluted).

### Plus deeper audit surfaced 9 new pre-existing defects:
- METADATA-LEAK lines 0-16 (front-matter at very top of doc — article-type code, journal banner, DOI line).
- SECTION-BOUNDARY: `Design and Procedure`, `Power Analysis and Sensitivity Test`, `Measures`, `Data Analysis Strategy` still plain text (not `###`).
- SECTION-BOUNDARY: `Challenging and Reframing Misestimation` (Discussion subsection) plain text.
- TABLE: Table 6 multi-word rows split across two `<tr>` elements.
- TABLE: Table 6 "Overall negative/positive" rows merged.
- TABLE: Table 8 variable-name rows split.
- TABLE: Table 9 caption truncated mid-word.
- TABLE: Table 9 Interpretation column split.
- TEXT-LOSS: `## Data Availability` section absent from end-matter.

## What remains — next session's cycle plan

### Phase 1: ship the architecture safely (no v2.4.77 yet)
1. **User runs `claude setup-token`** (one-time, ~30 sec, interactive in browser). Enables headless `claude -p --model sonnet` from git hooks / scheduled tasks.
2. **Smoke-test headless gate**: `bash ~/.claude/skills/_shared/iterate-loop/canary-audit.sh --quick docpluck-iterate` should fire RED, then a second run after fixes should fire GREEN.
3. **Wire git hooks**: pre-commit / pre-push / pre-tag (task #4 in this session's todo).
4. **Wire scheduled-tasks watchdog** (task #5).

### Phase 2: clear remaining 14 findings
1. **Table 10 phantom-guard tuning** — the th_section_leak heuristic landed but didn't fire. Debug why: probably the cell content has hyphens splitting words ("cau-tion") that break the word-shape detection. ~30 min.
2. **Affiliation fragment "Fu Lam, Hong Kong SAR."** — paragraph-level matcher needs a pre-join step OR the line-level matcher needs an orphan-wrap-tail pattern. ~20 min.
3. **Missing Method subsections** (Design and Procedure, Power Analysis, Measures, Data Analysis Strategy) — investigate why these don't promote despite the new logic. ~30 min.
4. **Missing Discussion subsection** (Challenging and Reframing Misestimation) — same investigation. ~10 min.
5. **Cluster D-full Camelot tuning** — Tables 3, 4, 6, 8, 9 all have structural defects from Camelot's column-tolerance + cell-wrap handling. RCA explicitly called this "cross-channel refactor, multi-cycle work." Realistic estimate: **separate session, 4-8 hours, full corpus regression-testing required**. Findings #6, #7 + most of the new table defects (#6 split rows, #8 split rows, #9 Interpretation column).
6. **Front-matter at top of doc (lines 0-16)** — pre-existing defect across many PSPB papers, never surfaced because no audit was looking. Needs P0 pre-pass for journal masthead block detection. ~1-2 hours.
7. **Data Availability section absent from end-matter** — the Cluster A demote-fix turned `## Data Availability` into italic body text, but the gold has it as a separate `##` section at the END (after Author Contributions). My fix may have stripped the legitimate end-matter section too. Investigate. ~30 min.

### Phase 3: validation + ship
1. Re-audit (single Sonnet pass, ideally twice with finding-union per the determinism directive).
2. If clean on all canary papers → bump `__version__` and `NORMALIZATION_VERSION` to v2.4.77 / 1.9.24.
3. Tag, push, bump app pin per docpluck/CLAUDE.md release flow.

### Phase 4: replicate to other iterate projects
Once docpluck audit + git hooks + scheduled watchdog are proven end-to-end clean, replicate the pattern to:
- escicheck-iterate (easiest — has 46 successful phase_5d_runs already, well-defined defect taxonomy)
- 2rmarkdown-iterate (needs 3-tier verdict-vocabulary integration)
- citationguard-iterate (needs corpus onboarding first; 2-view-per-paper case)

## Critical lessons learned this session

1. **Self-enforcement is structurally impossible.** No amount of prose ("LEAVE NOTHING BEHIND", "FIX EVERY BUG") changes the fact that the implementing model is also the model deciding whether to verify. External enforcement (different model + git hooks + scheduled tasks) is the only path that works.
2. **The audit's non-determinism is real.** Sonnet's first audit returned 10 findings; second returned 18; third returned 14. Same model, same prompt, same files. Mitigation: run audit twice + union findings (next session task). Until then, treat the gate's verdicts as a moving floor — any finding once seen stays open until cleared on a later run.
3. **"Fix all N findings" can balloon when the audit goes deeper.** Original ask was 4 defects; first audit found 10; deeper audit found 18. The bulk of the deeper findings are pre-existing structural defects (Camelot table issues, missing subsection headings, front-matter at top of doc) that the four prior "we fixed it" cycles never surfaced because their verification was unit-test green, not AI-gold diff.
4. **Camelot table-rendering is its own multi-session project.** Don't bundle Camelot tuning with quick-win fixes. The `render_for_audit.py` CLI + `canary-audit.sh` orchestrator make a proper iterate cycle now possible; use it.

## Files modified (uncommitted)

```
docpluck/render.py                                   (Cluster A helpers + Cluster B suppressor + PSPB carve-out)
docpluck/normalize.py                                (Cluster C affiliation patterns)
docpluck/sections/annotators/text.py                 (Cluster A prior-paragraph-terminator guard)
docpluck/.claude/skills/_project/canary.json         (verification_protocol extension)
docpluck/CLAUDE.md                                   (no-API hard rule)
docpluck/tools/render_for_audit.py                   (NEW)
~/.claude/skills/_shared/iterate-loop/audit-subagent-prompt.md   (NEW)
~/.claude/skills/_shared/iterate-loop/canary-audit.sh            (NEW)
~/.claude/skills/_shared/iterate-loop/CROSS-PROJECT-ALERT-2026-05-23.md  (2026-05-25 addendum)
Vibe/CLAUDE.md                                       (no-API hard rule)
~/.claude/projects/.../Vibe/memory/MEMORY.md         (no-API index entry)
~/.claude/projects/.../Vibe/memory/feedback_no_apis_only_claude_max.md  (NEW)
~/.claude/projects/.../docpluck/memory/MEMORY.md     (no-API index entry)
~/.claude/projects/.../docpluck/memory/feedback_no_apis_only_claude_max.md  (NEW)
```

## Audit artifacts left on disk

- `tmp/audit-smoke/ip_feldman_*.md` — multiple renders showing progression v1 → v9.
- `tmp/iterate/canary-380647a7cb2a/ip_feldman_2025_pspb.verdict.json` — first audit verdict (10 findings).
- `tmp/audit-smoke/ip_feldman_v9.md` — current state (14 findings remaining, mostly Camelot).

## Recommended next-session opener

Read this handoff. Then read `tmp/audit-smoke/ip_feldman_v9.md`. Then run `claude setup-token` (interactive). Then `bash ~/.claude/skills/_shared/iterate-loop/canary-audit.sh --quick docpluck-iterate` should fire RED with the 14 remaining findings. Phase 2.1 (Table 10 phantom-guard tuning) is the highest-leverage next 30 min.
