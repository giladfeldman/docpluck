# Self-improvement protocol (Phase 8 detail)

> Loaded on demand from SKILL.md Phase 8. Do not load up-front.

This is what makes the loop self-improving. Skip this and you've lost the cycle's signal.

## 8a · Append to LEARNINGS.md (per-cycle journal)

Open `.claude/skills/docpluck-iterate/LEARNINGS.md` (created on first run). Append one block:

```markdown
## Run: YYYY-MM-DD HH:MM · cycle <N> · v<X.Y.Z> · target=<one-line>

### Outcome
- <PASS / PARTIAL / REVERT / FAIL>
- <one-line summary of what shipped or didn't>

### Blind Spots (instructions / process gaps the run exposed)
- <e.g. "TRIAGE didn't list the running-header leak even though broad-read found it on 4 papers — TRIAGE update step needs explicit 'add new findings' instruction">

### Edge Cases (unexpected data / environment)
- <e.g. "pytest -q output buffered for 7 min on Windows — discovered awk fflush trick">

### Improvements (better approaches discovered this run)
- <e.g. "Splitting verify_corpus output filter from runtime via awk '{print; fflush()}' eliminated all polling">

### Verification Gaps (checks that should have caught issues earlier)
- <e.g. "26-paper baseline didn't exercise xiao_2021_crsp; that paper is the canonical Methods-missing case — should be in baseline">
```

A clean cycle with no surprises does NOT need a LEARNINGS entry. But "no surprises" is rare — be honest.

## 8b · Update _project/lessons.md (R1 spine rule)

If this cycle fixed any bug or had any user correction, append to `<project>/.claude/skills/_project/lessons.md` per the existing format (date, what happened, how to detect). One entry per finding. Keep entries short and actionable. The spine-gate (R1) checks that this file grew when `bugs_fixed` or `user_corrections` is non-empty in run-meta.

## 8c · Self-report into run-meta

Update `~/.claude/skills/_shared/run-meta/docpluck-iterate.json` per `_shared/preflight.md` step 6:
- `bugs_fixed` — one entry per defect class fixed this cycle.
- `tests_added` — paths to new/modified test files (the spine R2 will git-verify these).
- `lessons_appended` — titles of new entries in `_project/lessons.md`.
- `user_corrections` — any time the user corrected your approach.
- `phase_failures` — any check/test/build that failed and required a retry.
- `commands_run` / `files_touched` — append continuously, not at the end.
- `verdict` — `PASS` / `FAIL` / `PARTIAL` / `SKIPPED` for this cycle.

These power signal-detect.sh in postflight: if any are non-empty, `skill-optimize` writes a card to `_shared/lessons/` that future runs of you (and other docpluck skills with matching tags) will load via preflight.

## 8d · Update tmp/iterate-todo.md (always-visible TODO)

The always-visible TODO is markdown checkboxes the user can read between cycles:

```markdown
# Docpluck iterate · TODO

**Active goal:** <stop condition>
**Current cycle:** <N> of <expected>
**Last update:** <timestamp>

## Bugs fixed this run
- [x] vX.Y.Z · KEYWORDS overshoot — xiao_2021_crsp Methods now visible (cycle 2)

## Bugs in progress
- [ ] <current target>

## Backlog (top 5 from TRIAGE, severity × cost order)
- [ ] S1×C1 Front-matter footnote leak mid-Intro — 4 papers (xiao, amj_1, amle_1, ieee_access_2)
- [ ] S2×C2 IEEE Methodology subsection promotion — ieee_access_2/3
- [ ] ...

## Deferred (architectural / out-of-scope this run)
- [ ] S3×C4 50-PDF corpus expansion (separate skill / agent)
```

Print the TODO at the END of every cycle so the user can scan it without scrolling logs.

## 8e · SKILL.md amendment proposal (cross-cycle, after 2–3 LEARNINGS hits on the same theme)

If the same kind of finding shows up in 2+ LEARNINGS entries (e.g. "TRIAGE staleness keeps biting on cycle 1"), propose an amendment:

```
PROPOSED AMENDMENT to .claude/skills/docpluck-iterate/SKILL.md
- What: <change>
- Why: <repeated LEARNINGS finding, refs cycle dates>
- Risk: <low | medium — what could break>
```

**Wait for explicit user approval before editing the SKILL.** The amendment is the point — LEARNINGS.md is the journal, SKILL.md is where stable learnings live (per `_shared/learning-protocol.md`).

## How the wiring connects

```
   per-cycle (this skill)              cross-skill (skill-optimize)
   ──────────────────────              ────────────────────────────
   LEARNINGS.md (this skill only) ──┐
                                    │
   _project/lessons.md (this proj) ─┼─→ signal-detect.sh in postflight
                                    │       │
   run-meta/docpluck-iterate.json ──┘       │
                                            ▼
                                   _shared/lessons/<card>.md
                                            │
                                            ▼ (next preflight in any
                                               docpluck-tagged skill)
                                   loaded into context
```

Three cards into `_shared/lessons/` from this loop → `skill-optimize --consolidate` will propose a `_shared/domains/docpluck.md` brief that summarizes the domain across cards.
