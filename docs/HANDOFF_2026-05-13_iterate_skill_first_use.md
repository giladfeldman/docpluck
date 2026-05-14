# Handoff — first use of `/docpluck-iterate`, target front-matter leak class

**For:** a fresh session, no prior context loaded. Read this file end-to-end, then read [`.claude/skills/docpluck-iterate/SKILL.md`](../.claude/skills/docpluck-iterate/SKILL.md) and [`.claude/skills/docpluck-iterate/LEARNINGS.md`](../.claude/skills/docpluck-iterate/LEARNINGS.md), then start.

**Date authored:** 2026-05-13 evening.
**Library state:** `docpluck@v2.4.15` live on prod (Railway `/_diag` confirmed).
**App state:** `docpluckapp@master` pinned to `v2.4.15` (PR #6 merged, verify-railway-deploy.yml green).

---

## TL;DR

This is the **first real-world test** of the new `/docpluck-iterate` skill. The skill formalizes the library → local-app → production iterative loop with three uncategorical-blocker rules: zero text loss, zero hallucinations, tier 1 = tier 2 = tier 3 byte-match. See [`.claude/skills/docpluck-iterate/SKILL.md`](../.claude/skills/docpluck-iterate/SKILL.md).

**Your goal:** drive the **front-matter metadata-leak defect class** to ship across the corpus, then verify the entire library + local-app passes without issues. Stop when either (a) **one hour wall-clock** is reached, or (b) **all corpus papers** pass full AI verify (Phase 5d) and Tier 2 parity (Phase 6) for the targeted defect class with no TEXT-LOSS / HALLUCINATION findings.

Kickoff command:

```
/docpluck-iterate --goal until:"front-matter metadata leak resolved across full APA + AOM + IEEE + Nature + JAMA corpus, no TEXT-LOSS / HALLUCINATION findings in any Phase 5d AI verify"
```

If the user can't actively confirm the `until` is met at 60 minutes, fall back to the time budget:

```
/docpluck-iterate --goal time:60m
```

Either way, the skill will Phase 11 a handoff doc when it stops.

---

## The defect class to target

After v2.4.15 (which closed the xiao_2021_crsp KEYWORDS overshoot), a broad-read across 8 papers surfaced a **systematic, cross-publisher pattern**: front-matter metadata bleeding mid-Introduction. Confirmed instances:

| Paper | Style | Leak observed mid-Introduction |
|-------|-------|--------------------------------|
| `xiao_2021_crsp` | APA | `Supplemental data for this article can be accessed here.` + `Department of Psychology, University of` (truncated mid-line — the right-column affiliation block on page 1) |
| `amj_1` | AOM | `We wish to thank our editor Jill Perry-Smith and three anonymous reviewers for their insightful and constructive feedback. We also thank Angelo DeNisi, Matthew Feinberg...` (acknowledgments paragraph injected between intro paragraphs) |
| `amle_1` | AOM | `We thank Steven Charlier and three Academy of Management Learning and Education reviewers for offering highly constructive feedback...` + `A previous version of this article was presented at the Management Education and Development (MED) Plenary Session...` (similar acknowledgments + previous-version note) |
| `ieee_access_2` | IEEE | `RECKELL et al.` running header appears as its own paragraph between Abstract and `## INTRODUCTION`; also `I.` lonely Roman-numeral line before `## INTRODUCTION` |

All four are **systematically the same pattern**: pdftotext serializes the article's left column (Abstract, Introduction body) followed by the article's right-column / inter-column metadata (corresponding author, affiliations, acknowledgments, previous-version note, copyright, running headers, page numbers), and the linearized text-channel output inlines those metadata fragments as paragraphs inside what should be one continuous Introduction span.

The leak is INVISIBLE to:
- `scripts/verify_corpus.py` 26-paper baseline (passes 26/26 with this defect present)
- 951-test broad pytest (passes with this defect present)
- Char-ratio + Jaccard verifier metrics (the leak's tokens ARE present, just in the wrong section — Jaccard is blind to position)
- A 30-line eyeball check (the leak sits mid-document, often line 50–500)

The leak is VISIBLE to:
- A **full-document AI verify** subagent reading both pdftotext source + rendered .md (Phase 5d, ref [`references/ai-full-doc-verify.md`](../.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md)) — it surfaces as METADATA-LEAK findings.
- A human reading the rendered .md mid-document.

This is exactly the discovery → verification gap that the new skill is designed to close. Treat this iteration as the load-bearing first test of whether the protocol works in practice.

---

## Where to fix

**Layer-of-origin discipline (LESSONS L-001):** these are body-text artifacts, so the fix lives in the **text channel** (pdftotext output → `normalize.py` and/or `sections/annotators/text.py` and/or `sections/core.py`). Do NOT swap the text-extraction tool.

Two plausible fixes, both consistent with LESSONS L-001:

### Option A — Text-channel pre-filter (normalize.py)

Add a step that detects "orphan front-matter paragraph" between body paragraphs and either strips it or relocates it to a non-rendered span. Patterns to detect:

- `^We (wish to )?thank[ed]?\b` — acknowledgments leak
- `^Supplemental data for this article\b` — sidebar
- `^Department of [A-Z]` (with no period at end and < 80 chars) — truncated affiliation
- `^[A-Z]\. [A-Z]\. [A-Z][A-Z]+( ET AL\.?)?$` — Title-Case-initials running header (Q. XIAO ET AL., C. F. CHAN, etc.)
- `^[A-Z]+ et al\.?$` — lowercase running header
- `^A previous version of this article\b` — previous-version note
- `^© \d{4}\b` — copyright line
- `^CONTACT [A-Z]` — corresponding-author block
- `^Correspondence concerning this article` / `^Correspondence to[: ]` — corresponding-author block
- `^This work is licensed under\b` — IEEE / Creative Commons block

**Constraint:** the filter must be **context-aware** — these strings sometimes legitimately appear in the body (a paper discussing acknowledgments practice). Detect only when:
1. The paragraph is **short** (< 250 chars), AND
2. **Standalone** (preceded and followed by `\n\n`), AND
3. **Mid-body** (not within first 500 chars of the section), AND
4. **NOT inside an Abstract / Acknowledgments / Funding section** (where these are legitimate).

### Option B — Layout-aware F0 strip widening (`normalize.py::_f0_strip_running_and_footnotes`)

The existing `_f0_strip_running_and_footnotes` uses pdfplumber layout to detect running headers via vertical-position clustering. It may already be capable of identifying these inter-column metadata blocks via their distinct y-coordinates; the question is whether the render pipeline invokes F0 at the right point. Per the v2.4.5 close-out (`docs/HANDOFF_2026-05-13_iterative_1.md`, "Outstanding known issues"), F0 is NOT currently invoked from the render pipeline's normalize step. Wiring it in is the cleaner long-term fix but carries scope risk.

**Recommendation for this iteration:** start with Option A (text-channel pre-filter) — narrower scope, lower regression risk. If Option A misses paper-specific patterns, defer Option B to a subsequent iteration.

### Out of scope this iteration

- The `## Methods` section MISSING entirely in xiao (a different defect; xiao's source PDF doesn't have a Methods heading, just topic subheadings — needs section synthesis, not metadata-strip)
- IEEE Roman-numeral subsection promotion (`I.\n\n## INTRODUCTION` → `## I. INTRODUCTION`) — separate Defect D item
- xiao false `Experiment` heading — separate Defect D item

If the broad-read pass on cycle 1 surfaces those items higher than the metadata-leak class, follow the TRIAGE; otherwise stick to the metadata-leak class.

---

## The corpus to test against

The skill's Phase 5c uses the **26-paper spike baseline** (`scripts/verify_corpus.py`) as the regression gate. But the broad-read pass should sample beyond that, since the leak class shows up cross-publisher.

| Folder | Count | Representative | Use for |
|--------|-------|----------------|---------|
| `../PDFextractor/test-pdfs/apa/` | 18 | xiao, chan_feldman, chandrashekar, efendic, chen, ip_feldman, korbmacher, jamison, ziano, maier, jdm_*, ar_apa_j_jesp_* | APA pattern (right-column affiliations, supplemental-data sidebar) |
| `../PDFextractor/test-pdfs/aom/` | 14+ | amj_1, amle_1, amc_1, amd_1, amd_2, amp_1, annals_1..4, etc. | AOM pattern (we-thank acknowledgments, previous-version notes) |
| `../PDFextractor/test-pdfs/ieee/` | 10 | ieee_access_2..10 | IEEE pattern (Roman-numeral subsections, RECKELL-style running headers, IEEE license block) |
| `../PDFextractor/test-pdfs/nature/` | 5 | nat_comms_1..5 | Nature pattern (compact front-matter, no Introduction heading) |
| `../PDFextractor/test-pdfs/jama/` | unknown — list it | jama_open_1, jama_open_2, etc. | JAMA pattern (running headers per page, CONCLUSIONS AND RELEVANCE split) |
| `../PDFextractor/test-pdfs/chicago-ad/` | TBD | | Chicago pattern |
| `../PDFextractor/test-pdfs/asa/`, `vancouver/`, `harvard/` | TBD | | Other publisher patterns |

**Cycle 1 broad-read protocol:** sample 8–10 papers, one from each style folder where available. Render full, dispatch a full-doc AI verifier per `references/ai-full-doc-verify.md`. Surface findings into TRIAGE.

**Cycle 2+ targeted verify:** once the fix lands, render every paper in `apa/`, `aom/`, `ieee/`, `nature/` (the four styles confirmed-affected) and run full-doc AI verify on each. The skill's Phase 5d handles this — just give it the affected papers list.

**Stop condition for "corpus clean":** every paper in the four affected style folders renders with zero `METADATA-LEAK` findings (other than pre-existing leaks documented as known issues per the protocol). Pre-existing leaks are not blockers; new leaks introduced by the fix ARE.

---

## How to run the skill — practical kickoff

### Step 0 — Preflight read

In order (do not skip):

1. This handoff (this file).
2. [`.claude/skills/docpluck-iterate/SKILL.md`](../.claude/skills/docpluck-iterate/SKILL.md) — the orchestrator. Note especially Phase 5d (full-doc AI verify), Phase 6 (Tier 2 local-app parity), Phase 8 (Tier 3 prod parity), and the four uncategorical-blocker hard rules 0a-0d.
3. [`.claude/skills/docpluck-iterate/LEARNINGS.md`](../.claude/skills/docpluck-iterate/LEARNINGS.md) — seeded with the v2.4.14 + v2.4.15 lessons. Don't repeat the mistakes documented there.
4. [`tmp/iterate-todo.md`](../tmp/iterate-todo.md) — the seeded backlog. **Front-matter footnote / acknowledgment / sidebar metadata leak** is item #1 (S1×C1, single iter, high impact).
5. [`CLAUDE.md`](../CLAUDE.md) — project hard rules.
6. [`LESSONS.md`](../LESSONS.md) — durable incident log. L-001 is the relevant one ("never swap the text-extraction tool as a fix for downstream problems").
7. The most recent `docs/TRIAGE_*.md` — currently `docs/TRIAGE_2026-05-10_corpus_assessment.md`. It's stale (predates v2.4.x); cycle 1 broad-read will refresh it.

### Step 1 — Invoke the skill

```
/docpluck-iterate --goal time:60m
```

…OR if you're confident you'll converge within the hour:

```
/docpluck-iterate --goal until:"front-matter metadata-leak class resolved across apa+aom+ieee+nature with zero TEXT-LOSS/HALLUCINATION findings in Phase 5d AI verify"
```

The skill will:
- Ask you to confirm the goal at Phase 0.
- Print a cycle heartbeat at Phase 1.
- Run a broad-read on cycle 1 (Phase 2) because the active TRIAGE is stale (>7 days old, predates v2.4.x).
- Refresh TRIAGE in place, pick the metadata-leak class from the top-3.
- Implement the fix in `normalize.py` and/or `sections/`.
- Run Phase 5 Tier 1 verification (targeted tests + broad pytest + 26-paper baseline + **full-doc AI verify on every affected paper**, ref [`references/ai-full-doc-verify.md`](../.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md)).
- Run Phase 6 Tier 2 local-app parity (`diff` library output vs `/extract` endpoint output, both must match).
- Run `/docpluck-cleanup` then `/docpluck-review` then commit + tag + push (Phase 7).
- Wait for auto-bump bot PR, merge, verify Railway redeploy, run Phase 8 Tier 3 parity.
- Phase 9 self-improvement: append to LEARNINGS, update `_project/lessons.md`, refresh TODO.
- Phase 10 stop check: if goal met, exit; else loop.

### Step 2 — Watch the heartbeats

Each cycle prints:
- `🔁 docpluck-iterate · cycle N/expected · goal=... · target=...` — at Phase 1
- Cycle-end report per [`references/cycle-report-template.md`](../.claude/skills/docpluck-iterate/references/cycle-report-template.md) — at end of cycle
- `🔧 skill-optimize post-check ...` — at Phase 12

If you don't see those heartbeats in order, the skill drifted from spec — surface to the user.

### Step 3 — Final handoff

When the skill stops (goal met or must-stop), it writes `docs/HANDOFF_<YYYY-MM-DD>_iterate_<run-id>.md` with the cycle log, fixed bugs, open queue, proposed amendments. Read it; that's the next-session handoff.

---

## Stop conditions (in priority order)

The skill enforces these automatically; restating here so you (the fresh session) know what to expect:

1. **Goal-met stop (preferred):**
   - `time:60m` — Phase 10 detects budget exhausted; current cycle finishes, no new cycle starts. Phase 11 writes the handoff.
   - `until:"..."` — Phase 10 asks you to confirm completion against the description; if confirmed, Phase 11 writes the handoff.

2. **MUST-STOP (non-negotiable):**
   - `scripts/verify_corpus.py` 26-paper baseline regresses and the cycle's revert attempt also fails.
   - Three consecutive cycles produced PARTIAL / REVERT / FAIL.
   - `git push` rejected (branch protection / divergence).
   - Production `/_diag` doesn't reach the new version after 8 min.
   - Phase 5d AI verify returns TEXT-LOSS or HALLUCINATION findings AND the revert attempt also produces them (means the bug pre-exists in v2.4.15 and the fix made it worse, OR the fix introduced a new instance — either way, escalate).

3. **Soft-stop (surface to user, await direction):**
   - 3 consecutive cycles produced only metric shifts (no new structural improvements) → diminishing returns; switch focus?
   - TRIAGE empty after broad-read → corpus at quality floor for current detection ability; expand to 50-PDF / 101-PDF?

---

## Verification gates (the uncategorical-blockers — apply every cycle)

From the skill's rules 0a-0d (top of the hard-rules list):

- **0a** · Zero text loss — Phase 5d full-doc AI verify against pdftotext source-of-truth.
- **0b** · Zero hallucinations — same gate.
- **0c** · Tier 1 = Tier 2 = Tier 3 byte-match (or documented `tmp/known-tier-deltas.md`).
- **0d** · Every fix ships with a `*_real_pdf` regression test against an actual PDF fixture in `../PDFextractor/test-pdfs/`.

Tier 2 byte-diff is non-negotiable. Tier 3 byte-diff is non-negotiable. AI verify is non-negotiable.

**The single most important rule for this iteration:** **NO TEXT MAY DISAPPEAR.** A meta-science user pulling data from this library cannot be told "we silently dropped one paragraph but the rest is fine." A metadata-leak fix that ALSO drops a legitimate body paragraph is worse than the original leak. Revert in that case.

---

## File map — what to touch and why

**Most likely code change locations:**

- `docpluck/normalize.py` — text-channel normalization pipeline. The metadata-leak filter belongs here as a new step (S10 or similar — pick the next free letter / number; current is S9 = 4-digit page-number cluster strip). Increment `NORMALIZATION_VERSION` (currently `1.8.3`) to `1.8.4` if you add a new step.

- `docpluck/sections/annotators/text.py` — section-boundary hint annotator. If the fix is "treat orphan front-matter-shaped paragraphs as section boundaries" rather than "strip them," it lives here.

- `docpluck/sections/core.py` — partition logic. If the fix is "absorb orphan front-matter paragraphs into the nearest neighboring section's prefix unknown span" rather than strip-or-rebound, here.

**Tests:** add to `tests/test_normalization.py` (a contract test for the new step) AND a `tests/test_normalize_metadata_leak_real_pdf.py` (a real-PDF regression test per rule 0d — exercises the full library on xiao + amj_1 + amle_1 + ieee_access_2 fixtures and asserts the leak is gone from the rendered .md). Skip-if-fixture-missing pattern; do NOT commit PDFs.

**Docs:** `CHANGELOG.md` entry per the existing format. Bump `__version__` patch level (`v2.4.16`).

---

## Useful commands

```bash
# Sanity check the active version + prod state before starting:
python -c "import docpluck; print(docpluck.__version__)"
curl -s https://extraction-service-production-d0e5.up.railway.app/_diag | python -m json.tool | head -8

# Render the four leak-pattern papers as a quick before-snapshot:
for p in xiao_2021_crsp:apa amj_1:aom amle_1:aom ieee_access_2:ieee; do
  name="${p%:*}"; folder="${p#*:}"
  python -c "
from pathlib import Path
from docpluck.render import render_pdf_to_markdown
md = render_pdf_to_markdown(Path('../PDFextractor/test-pdfs/$folder/$name.pdf').read_bytes())
Path('tmp/${name}_v2.4.15.md').write_text(md, encoding='utf-8')
print('OK $name', len(md), 'chars')
" 2>&1 | grep -v -E "UserWarning|cols, rows"
done

# Look for the leak patterns in each:
grep -n "We wish to thank\|We thank\|Supplemental data\|^Department of\|^[A-Z]+ ET AL\|^© \\d{4}\|^CONTACT " tmp/xiao_2021_crsp_v2.4.15.md tmp/amj_1_v2.4.15.md tmp/amle_1_v2.4.15.md tmp/ieee_access_2_v2.4.15.md

# Once you've shipped the fix, re-render and verify:
# (the skill's Phase 5d does this automatically with a subagent, but you can spot-check first)
diff tmp/xiao_2021_crsp_v2.4.15.md tmp/xiao_2021_crsp_v2.4.16.md | head -30

# Background pytest pattern (post-fix):
DOCPLUCK_DISABLE_CAMELOT=1 python -u -m pytest tests/ -q --tb=line \
  --ignore=tests/test_extract_pdf_structured.py \
  --ignore=tests/test_cli_structured.py \
  --ignore=tests/test_corpus_smoke.py \
  --ignore=tests/test_benchmark_docx_html.py 2>&1 | awk '{print; fflush()}'
# (run via Bash with run_in_background: true; Monitor for "passed|failed|error")

# 26-paper baseline (the hard regression gate):
PYTHONUNBUFFERED=1 python -u scripts/verify_corpus.py 2>&1 | awk '{print; fflush()}'
# (must PASS 26/26; single WARN blocks)

# Tier 2 (local-app) parity — after restarting uvicorn:
ADMIN_KEY="<get from ../PDFextractor/frontend/scripts/get-or-create-admin-key.mjs>"
for p in xiao_2021_crsp:apa amj_1:aom amle_1:aom ieee_access_2:ieee; do
  name="${p%:*}"; folder="${p#*:}"
  curl -sS -X POST -H "Authorization: Bearer $ADMIN_KEY" \
    -F "file=@../PDFextractor/test-pdfs/$folder/$name.pdf" \
    http://localhost:6117/extract \
    | python -c "import sys, json; r = json.load(sys.stdin); print(r['text'])" \
    > tmp/${name}_v2.4.16_local-app.md
  diff tmp/${name}_v2.4.16.md tmp/${name}_v2.4.16_local-app.md
done
# (must produce no content diff per rule 0c)
```

---

## State at handoff — verified

```
# Library version (local + tagged + on PyPI ready):
docpluck.__version__ == "2.4.15"

# Prod /_diag (Railway):
{
  "docpluck_version": "2.4.15",
  "camelot_version": "1.0.9",
  "opencv_version": "4.13.0.92",
  "ghostscript_binary": "/usr/bin/gs",
  ...
}

# 26-paper baseline at v2.4.15: 26/26 PASS (verified by automated run)
# Broad pytest at v2.4.15: 953 passed, 17 skipped, 0 failed

# Open PRs in docpluckapp: none (PR #6 merged at 20:55:14Z)
# App master: docpluckapp@<latest>, requirements.txt pin = docpluck==2.4.15

# tmp/iterate-todo.md: pre-seeded with the post-v2.4.15 backlog
# .claude/skills/docpluck-iterate/LEARNINGS.md: pre-seeded with v2.4.14+v2.4.15 lessons
# active TRIAGE: docs/TRIAGE_2026-05-10_corpus_assessment.md (stale; cycle 1 broad-read refreshes)
```

Repo cleanliness: both repos clean. No uncommitted edits.

---

## Anticipated cycle count

Rough estimate for the metadata-leak class:

- **Cycle 1** (~30 min): broad-read refreshes TRIAGE; implement Option A (text-channel pre-filter for `We wish to thank` + `Supplemental data` + `^Department of` + running-header pattern). Phase 5a-d run. Phase 6 Tier 2 parity. Phase 7 release. Phase 8 Tier 3 prod verify. Phase 9 LEARNINGS + TODO. Ship `v2.4.16`.
- **Cycle 2** (~20 min): pick up additional patterns surfaced by cycle 1's AI verify (`A previous version of this article` / IEEE license block / `Correspondence concerning`). Ship `v2.4.17`.
- **Cycle 3 if budget remains** (~15 min): cross-corpus AI sweep — render every paper in apa+aom+ieee+nature, dispatch one subagent reading 5 random papers, surface any remaining METADATA-LEAK findings. If zero, declare the defect class resolved.

If the AI verify on cycle 1 already shows 0 METADATA-LEAK findings on all four pattern papers AND zero new findings cross-corpus, you're done early — write the final handoff and exit.

If cycle 2 still has METADATA-LEAK findings on papers NOT in the four-pattern set, the fix is incomplete — extend the patterns and ship cycle 3.

---

## Don't repeat these mistakes (from the v2.4.14 / v2.4.15 LEARNINGS)

1. **Don't write a regression test using `text = "Pre.\\n\\nABSTRACT\\n..."` synthesized strings.** Use a real PDF fixture. Rule 0d.

2. **Don't skip the full-document AI verify.** Char-ratio + Jaccard verifiers passed at v2.4.15 with this defect present — they're blind to "right words in wrong section." Rules 0a/0b are the gate.

3. **Don't ship the fix without Tier 2 byte-diff verification.** The v2.4.13 Camelot incident was exactly the "library works locally, prod silently breaks" class. Rule 0c.

4. **Don't try to fix more than one defect class per cycle.** Two fixes can't be reverted independently if one regresses.

5. **Don't skip the broad-read on cycle 1.** TRIAGE is stale (>7 days old). The metadata-leak class is the top hypothesized item but broad-read may surface something higher.

6. **Don't skip the `awk '{print; fflush()}'` after `python -u`.** Windows pipe buffering will silently hide pytest progress for minutes; you'll think it's hung.

7. **Don't paraphrase delegated skill output.** When you invoke `/docpluck-cleanup` or `/docpluck-review` (Phase 7), surface their status tables verbatim. The user sees what those skills said.

8. **Don't take 90 min on a 60-min budget.** Phase 10 stop check enforces this; current cycle finishes, no new cycle starts. Phase 11 handoff explains what's left.

---

## Hand-off chain

When you finish: the skill's Phase 11 writes `docs/HANDOFF_2026-05-13_iterate_<run-id>.md`. That becomes the input for the next session's `/docpluck-iterate` run.

The chain so far:
- `HANDOFF_2026-05-13_iterative_library_improvement.md` (workflow contract, narrative form)
- `HANDOFF_2026-05-13_iterative_1.md` (close-out of v2.4.2 through v2.4.5)
- `HANDOFF_2026-05-13_table_extraction_next_iteration.md` (v2.4.13 Camelot incident + Defect A/B targets)
- **(this file)** `HANDOFF_2026-05-13_iterate_skill_first_use.md` (first use of the formalized skill, metadata-leak target)
- → `HANDOFF_2026-05-13_iterate_<run-id>.md` (auto-written by skill on stop)
- → next session

Good luck. The whole point of the new skill is that "good luck" is no longer needed — the protocol enforces verification. Run it, watch it work, and document anything that breaks in LEARNINGS so the next run is smarter.
