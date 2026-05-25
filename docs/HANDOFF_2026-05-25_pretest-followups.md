# Pretest follow-ups — handoff

**Created:** 2026-05-25
**Created from:** session that produced [`HANDOFF_2026-05-25_haiku-orchestration-pretest.md`](HANDOFF_2026-05-25_haiku-orchestration-pretest.md)
**Repo state at handoff:** `main` @ `9262e1e` ("docs: Haiku-orchestration pretest results + recommendations"), clean working tree, no open worktrees.
**Read first:** [`HANDOFF_2026-05-25_haiku-orchestration-pretest.md`](HANDOFF_2026-05-25_haiku-orchestration-pretest.md) — full pretest report. Specifically the "Issues found during the test" section, which is the source for both items below.

This handoff bundles two **independent** follow-ups deferred from the 2026-05-25 Haiku-orchestration pretest. They can be done in either order, in separate sessions, or in parallel worktrees. Do not bundle them into one commit — each gets its own.

---

## Issue 1 — jama-open-1 defect cluster (SERIOUS)

### Why this matters

JAMA Network Open's two-column-with-Key-Points-sidebar layout is a real publisher class docpluck currently can't render. Five distinct defects on one paper, all surfaced cleanly during the pretest's Test 1. None are paper-specific quirks — every fix must generalize to the JAMA Open structural signature per CLAUDE.md.

### Inputs

- **Test fixture:** `verify_out/pdfextractor__ama__jama-open-1/` (the rendered-output dir; `.gitignored` so will be regenerated on first run)
- **Gold reference:** `C:\Users\filin\Dropbox\Vibe\ArticleRepository\ai_gold\jama_open_1\reading.md`
- **Source PDF path:** look up via `python -c "import json; print(json.load(open(r'C:\Users\filin\Dropbox\Vibe\ArticleRepository\ai_gold\jama_open_1\reading.meta.json'))['source_pdf_path'])"`
- **Rendered output from the pretest (saved for diff convenience):** none preserved (worktrees deleted). Regenerate via the iterate skill.

### What's broken (five defect classes, with file pointers)

| # | Class | File / module | Symptom |
|---|---|---|---|
| 1 | **RUNNING_HEADER_LEAK** | `docpluck/normalize.py` (F0 layout-aware running-header strip) | `Downloaded from jamanetwork.com by Medizinisch-Biologische Fachbibliothek user on 03/18/2026` leaks into body ~11×; `October 27, 2023` page-marker date also leaks. Pattern is a per-page footer that F0 currently does not detect on JAMA Open's geometry. |
| 2 | **HALLUC_HEAD** | `docpluck/sections/annotators/text.py` (heading promotion) — verify exact module | Table 2 cell content promoted to h3: `### 1.0. Mean glucose level`, `### Control`, `### Body weight, kg`, `### Total cholesterol`. Likely cause: heading-promotion heuristic firing on short isolated lines inside table regions. |
| 3 | **ABSTRACT_LEVEL_MISMATCH** | `docpluck/sections/` (structured-abstract detection) | JAMA's structured abstract has 7 subsections (Importance / Objective / Design, Setting, and Participants / Interventions / Main Outcomes and Measures / Results / Conclusions and Relevance). Gold renders these as h3 under `## Abstract`. Docpluck renders some as h2 (`## Findings`, `## RESULTS`, `## CONCLUSIONS AND RELEVANCE`) — breaking hierarchy. |
| 4 | **MISSING_SECTION** | `docpluck/sections/` + extraction pipeline | JAMA Open's `## Key Points` (right-column sidebar above the abstract — a publisher-mandated structured summary with Question/Findings/Meaning) is entirely absent from rendered output. Likely cause: sidebar bbox not detected as a separate content region; gets dropped or interleaved with abstract. |
| 5 | **TABLE_STRUCTURE_CORRUPT** | `docpluck/tables/` | Table 3 ends up with `<th>JAMA Network Open \| Nutrition, Obesity, and Exercise</th>` (journal masthead leaking into table header) and `<td>Discussion</td>` (the next section's name leaking into a table cell). Likely cause: table-bbox boundary detection bleeds outside the table region. |

All five are documented in the pretest report's "Issues found during the test" section with the same evidence.

### Hard rules (from CLAUDE.md)

- **LEAVE NOTHING BEHIND.** Fix all 5 in this run. Pre-existing or not, fix them.
- **EVERY FIX MUST BE GENERAL.** Key each fix on the JAMA-Open structural signature (e.g. "two-column body + right-side sidebar + structured abstract with semantic subsection labels"), not on `jama-open-1` identity. The fix must not regress when a different JAMA Open paper hits.
- **Never use `-layout` flag; never use AGPL deps; always normalize U+2212.** Standard library invariants.
- **Ground truth = article-finder AI gold,** never pdftotext / Camelot / pdfplumber output.

### Procedure

1. **Pre-flight:** open a fresh Claude Code session in `C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck`. Confirm `git status` is clean and `git rev-parse HEAD` is `9262e1e` (or a descendant).
2. **Add `jama-open-1` to the canary set** before iterating. The canary set lives in `.claude/skills/_project/canary.json` (per iterate-loop spine docs). After this, every future iterate cycle will AI-verify this paper.
3. **Invoke the skill:**
   ```
   /docpluck-iterate --goal "PASS on jama-open-1" --no-broad-read
   ```
4. **Per-cycle fix order (suggested):** start with #1 (RUNNING_HEADER_LEAK) — F0 strip is upstream of section detection, fixing the header geometry first may reduce noise downstream. Then #2 (HALLUC_HEAD) and #3 (ABSTRACT_LEVEL_MISMATCH) which are both section-detection. Then #5 (TABLE_STRUCTURE_CORRUPT). #4 (MISSING_SECTION / Key Points sidebar) is the hardest — bbox detection — and can be last.
5. **Bump versions consistently** per CLAUDE.md "Release flow" section: `docpluck/__init__.py::__version__`, `pyproject.toml::version`, `docpluck/normalize.py::NORMALIZATION_VERSION` (only if normalize behavior changed), `CHANGELOG.md`.
6. **Regression baseline:** run the full 26-paper baseline after each cycle. Zero regressions allowed.
7. **Close the run** via `bash ~/.claude/skills/_shared/iterate-loop/iterate-gate.sh --close docpluck-iterate` only when:
   - All 5 defects PASS verdict on AI-verify for jama-open-1
   - Baseline 26-paper corpus is clean
   - Canary set updated and committed

### Done when

- `phase_5d_runs` in run-meta shows verdict PASS for `jama-open-1` with `findings_count == 0`
- `iterate-gate.sh --close` exits 0
- Canary set includes jama-open-1; CHANGELOG mentions the 5 fixes; a closeout handoff is written under `docs/HANDOFF_<date>_jama_open_1_cycle_close.md`

### Estimated scope

5 defect classes is roughly 2-4 cycles (some classes may share root cause, e.g., #2 + #3 could collapse into one section-detection fix). Plan for 60-120 min in a fresh session. Budget Opus tokens accordingly — this is exactly the kind of work that benefits from a clean context window.

---

## Issue 2 — `ai-gold.py resolve` stem behavior (MODERATE)

### Why this matters

During the pretest, the Arm A subagent hit a usability wall: it tried `ai-gold.py resolve jama_open_1` (and variants with the file path), all failed. But `ai-gold.py check jama_open_1 --view reading` worked directly. The `article-finder/SKILL.md` "RESOLVE the canonical key" step implies any natural identifier should resolve — so this asymmetry costs cycles for every new user / new subagent hitting the tool.

### Owner

The `article-finder` skill, not docpluck. Lives at `~/.claude/skills/article-finder/`. **Do not commit changes from inside the docpluck repo.** This issue needs its own session in whatever location owns the article-finder skill (likely under `~/.claude/skills/` directly).

### Inputs

- `~/.claude/skills/article-finder/SKILL.md`
- `~/.claude/skills/article-finder/gold-generation.md`
- The `ai-gold.py` script (locate via `find ~/.claude/skills/article-finder -name 'ai-gold.py' -o -name 'ai_gold.py'`)

### Two acceptable fixes

**Option A — Fix the resolver (cleaner):**
Make `ai-gold.py resolve` accept stem names (e.g. `jama_open_1`) as input. If a stem doesn't match any canonical key directly, look up `reading.meta.json` files under `ai_gold/<stem>/` and return the key. Should also accept source PDF file paths and resolve them via the `source_pdf_path` field stored in `reading.meta.json`.

**Option B — Document the asymmetry (faster, less ideal):**
If `resolve` is intentionally narrower than `check`, amend `article-finder/SKILL.md` and `gold-generation.md`:
- Add a clear note: "If you have a stem, skip `resolve` and call `check <stem> --view <name>` directly."
- Include a worked example using `jama_open_1` to show both paths.

Pick A if the resolver codebase makes it straightforward. Pick B otherwise.

### Test

```bash
# Should succeed (or, under Option B, the docs should redirect you to `check`):
python ~/.claude/skills/article-finder/ai-gold.py resolve jama_open_1

# Should also succeed (already works):
python ~/.claude/skills/article-finder/ai-gold.py check jama_open_1 --view reading
```

### Done when

- `resolve jama_open_1` either works (Option A) OR the docs unambiguously redirect to `check` with a worked example (Option B)
- A follow-up user / subagent hitting the same wall has a clear path forward
- Skill version bumped if applicable (article-finder is "self-improving via LEARNINGS.md" — append a lesson)

### Estimated scope

Option A: 1-2 hours. Option B: 20 minutes. Either is small; this is a sharp-edge polish, not a structural change.

---

## After both issues are done

Both follow-ups close the loop on the 2026-05-25 pretest's deferred findings. After both are merged:

- Update [`HANDOFF_2026-05-25_haiku-orchestration-pretest.md`](HANDOFF_2026-05-25_haiku-orchestration-pretest.md) "Approved follow-ups" section to mark items 1 and 2 as complete (with commit SHAs).
- The third approved follow-up — "Design and run the next pretest: Haiku-drafted code patches reviewed by Opus" — remains open. That's a separate brainstorm session; do not roll it into either of these.

## Files to clean up — DONE 2026-05-25

All pretest artifacts removed in the same session that produced this handoff:

- ✅ `C:\Users\filin\Dropbox\Vibe\ArticleRepository\_pretest_haiku_golds\` (whole dir) — removed
- ✅ `tmp/pretest_*.json`, `tmp/pretest_*.txt`, `tmp/run_meta_*.json` in docpluck — removed
- ✅ `tmp/test-2026-05-23-haiku-orchestration-findings.md` — removed (findings already merged into this handoff and the pretest report)
