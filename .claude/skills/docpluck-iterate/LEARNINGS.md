# docpluck-iterate · per-skill learnings journal

This file is the per-skill learning journal for `/docpluck-iterate`. Append one block at the bottom of this file for every cycle that surfaced a blind spot, edge case, improvement, or verification gap. After 2–3 entries with the same theme, propose a SKILL.md amendment and wait for user approval.

**Companion files:**
- Per-cycle TODO: `tmp/iterate-todo.md`
- Cross-skill lessons: `<project>/.claude/skills/_project/lessons.md`
- Cross-project shared cards: `~/.claude/skills/_shared/lessons/` (auto-managed by skill-optimize)

A clean cycle with no surprises does NOT need a LEARNINGS entry. But "no surprises" is rare — be honest.

---

## Run: 2026-05-13 22:00 · cycle 0 (skill-bootstrap, not an iteration) · v2.4.15

### Outcome
- SEED — this entry pre-loads the journal with three sessions' worth of process learnings (v2.4.14, v2.4.15, the broad-read + handoff workflow). Future cycles append to this same file.

### Blind Spots
- **TRIAGE drift across releases.** The active `docs/TRIAGE_2026-05-10_corpus_assessment.md` was written for the splice-spike (table-internals) and is structurally misaligned with the post-v2.4.14 work (KEYWORDS/Introduction, F0 leaks). A fresh broad-read on cycle 1 of any new run is mandatory; do NOT just pop the next item off the splice-spike triage.
- **`_synthesize_introduction_if_bloated_front_matter` had two regimes (ABSTRACT vs KEYWORDS) collapsed into one heuristic** — the 800-char rule was correct for ABSTRACT but overshot for short keyword lines. Future similar functions should be label-aware from the start; if a function takes a candidate of mixed types, branch by type before applying the heuristic.

### Edge Cases
- **Windows pytest output buffering.** `python -u` alone is insufficient; subprocess output through `Bash` redirection buffers fully until process exit (observed: 7+ minutes 0-byte output, then full dump). Workaround: pipe through `awk '{print; fflush()}'` after `python -u`. Verified for both `pytest -q` and `verify_corpus.py`.
- **Camelot atexit shutil.rmtree races on Windows** — produces a final `PermissionError: [WinError 32]` traceback after every successful Camelot run because the temp file is still open in another process during cleanup. Cosmetic; ignore. Do not chase.
- **Smart apostrophe `'` doubles as quote-delimiter in academic text.** A naive regex `[""\"\'](.{4,}?)[""\"\']` for "is this a quoted instrument item?" matches across hundreds of chars when an apostrophe appears mid-paragraph. Fix: restrict to double-quote characters only, AND cap the inner-content length (`{4,160}`).

### Improvements
- **Background pytest + Monitor pattern** beats foreground polling. Launch `pytest` with `run_in_background: true`, arm a Monitor with `until grep -qE "passed|failed|error" <output>; do sleep 10; done`, work on docs/CHANGELOG while waiting. Saves ~5 min per cycle.
- **Targeted unit tests with `DOCPLUCK_DISABLE_CAMELOT=1`** finish in 0.3–3s and catch most regressions; the broad pytest (without camelot fixture files) finishes in ~5 min and catches cross-module effects; the 26-paper baseline (~10 min) is the regression gate. Run them sequentially, NOT in parallel — they compete for CPU + camelot temp dir.
- **`_diag` polling cycle for Railway deploy:** `until v=$(curl -s /_diag | jq -r .docpluck_version); [ "$v" = "X.Y.Z" ] && break; sleep 20` — bounded, predictable, ~2-4 min wall time post-PR-merge.
- **Auto-bump PR open delay is ~15-30s** after `git push --tags`. A 25-30s sleep before checking is wasted; use Monitor with poll-and-break instead.

### Verification Gaps
- **The 26-paper baseline doesn't include xiao_2021_crsp** even though it's the canonical "missing Methods section" case. Several deferred Defect D items only show up in the 101-paper full corpus. Adding xiao + 4-5 publisher-diverse cases to the 26-paper baseline would make the regression gate catch more before-and-after differences.
- **Eyeball check (Phase 5d) is the only thing that catches "right words in wrong order under wrong heading"** — the verifier's char-ratio + Jaccard tags pass even when the user-visible output is broken. Memory `feedback_ai_verification_mandatory` documents this. Never skip Phase 5d.
- **No automated check for "front-matter footnote / acknowledgment leak mid-Introduction"** — the v2.4.15 broad-read found this on 4 papers (xiao, amj_1, amle_1, ieee_access_2) but no test catches it. Adding a heuristic check (e.g. "Introduction body should not contain `Department of`, `We thank`, `We wish to thank`, etc. as standalone short paragraphs") would be a useful post-v2.4.15 follow-up.

### Process notes (one-time, for the bootstrap)
- This skill was created post-hoc from v2.4.14 + v2.4.15 sessions. The handoff `docs/HANDOFF_2026-05-13_table_extraction_next_iteration.md` and predecessor `docs/HANDOFF_2026-05-13_iterative_library_improvement.md` together describe the same loop in narrative form. The skill formalizes the discipline.
- The skill is namespaced `docpluck-iterate` (not `*-qa`/`*-review`/`*-cleanup`/`*-deploy`) so the quality-loop spine R1–R5 doesn't auto-gate it. But every cycle DELEGATES to those skills, so the spine still runs transitively. Cycles where delegated skills FAIL count as cycle failures.

---

## Run: 2026-05-13 22:30 · cycle 0.1 (skill-amend, post-user-feedback) · meta-science correctness

### Outcome
- SEED — user reviewed the v0.1 skill draft and identified three critical missing rules. The skill now encodes them as rules 0a/0b/0c/0d (uncategorical blockers, top of the hard-rules list) plus expanded Phase 5d + new Phase 5.5 + Phase 7c.

### Blind Spots (gaps the v0.1 draft had — now closed)
- **The original "Phase 5d eyeball" was a 30-line read.** This is inadequate for meta-science. A 30-line read catches title-block issues but is structurally blind to mid-document text loss / hallucinations / boundary errors. **Replaced with a full-document AI-verify subagent protocol** (see `references/ai-full-doc-verify.md`) that reads BOTH the rendered .md and the pdftotext source-of-truth in full and produces structured findings: TEXT-LOSS, HALLUCINATION, SECTION-BOUNDARY, TABLE, FIGURE, METADATA-LEAK.
- **No "tests use real library + real PDFs" rule.** The v0.1 draft inherited the v2.4.15 pattern where a unit test used synthesized `text = "ABSTRACT\nblah\n\nKEYWORDS foo\n\n..."` strings. That covers the helper's contract but not the bug surface (two-column layout, pdftotext reading-order quirks, full-pipeline interaction). **Added rule 0d** and `references/real-library-real-pdf.md` mandating that every cycle's regression test exercises the public library on an actual PDF fixture.
- **No "Tier 1 → Tier 2 → Tier 3 parity chain" rule.** The v0.1 draft had a Phase 7 deploy check but no requirement that the LIBRARY output, LOCAL-APP output, and PROD output match byte-for-byte. The v2.4.13 Camelot-not-installed incident was exactly this class of bug — library worked locally, prod silently produced wrong output for months. **Added rule 0c** and `references/three-tier-parity.md` mandating sequential Tier 1 → Tier 2 → Tier 3 verification with byte-diff gates at each boundary.

### Edge Cases (operational realities of the three-tier chain)
- **Tier 2 requires uvicorn restart after every library version bump.** Python module cache holds the OLD library code otherwise. Skipping the restart silently produces stale-library output that the Tier 2 diff will catch — but only if you remember to restart.
- **Tier 3 has pdftotext version skew** (Xpdf 4.00 local vs poppler 25.03 prod, memory `feedback_pdftotext_version_skew`). Some deltas are intentional. Document them in `tmp/known-tier-deltas.md` so future cycles don't chase phantoms. Never silently ignore an unexpected delta.
- **AI verify on prod (Tier 3) is mandatory every 3rd cycle.** The Tier 2 = Tier 3 byte-diff catches gross divergence; AI verify catches subtle content drift that a byte-diff can't (e.g. encoding differences that round-trip but produce different rendered text).

### Improvements (better approaches surfaced by user feedback)
- **Rule 0a/0b are uncategorical-blockers** — there is no negotiating with TEXT-LOSS or HALLUCINATION findings. The rationalizations table explicitly forbids "I'll skip the AI verify, char-ratio passed" and "this TEXT-LOSS finding is minor, just one paragraph." A single paragraph is someone's results section.
- **Real-PDF regression tests have `_real_pdf` suffix in the function name** (per `references/real-library-real-pdf.md`). Grep-discoverable: `pytest -k "real_pdf"` runs the gate; `pytest -k "not real_pdf"` runs fast contract tests. This naming is the lightest-weight enforcement of rule 0d.
- **The three tiers are SEQUENTIAL, not parallel** (rule 15). Tier 1 must pass before Tier 2 starts; Tier 2 before Tier 3. This prevents the "Tier 3 is fine, ship anyway" failure mode where a Tier 2 divergence is rationalized away.

### Verification Gaps (still open, deferred for future skill cycles)
- **No automated check that a cycle added a `_real_pdf` test.** Currently it's documented as required but enforced by self-discipline + the spine R2 check (which only verifies tests/ paths changed, not that a real-PDF test specifically was added). Future improvement: a pytest collection hook that warns when `tests_added` in run-meta has no `*_real_pdf` entry. Token-budget-low priority.
- **No machine-readable diff format for Tier 1/Tier 2/Tier 3 outputs.** Currently uses `diff` and visual inspection. A `compare-tiers.sh` script that emits a structured JSON of paragraph-level matches/diffs would be more reliable than `diff`. Deferred.
- **AI-verify subagent prompt is in a reference file but not in code.** A future improvement is `scripts/ai_verify.py` that takes a paper, dispatches the subagent, and emits a JSON verdict. Currently the protocol is documented and the orchestrator dispatches manually. Deferred.
