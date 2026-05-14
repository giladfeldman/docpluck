# Cycle report template

> Loaded on demand at end of cycle. Print to user at end of every cycle so they can scan progress without scrolling logs.

```markdown
## Cycle <N> · v<X.Y.Z> · <target one-liner>

| Phase | Status | Notes |
|-------|--------|-------|
| 2 · Broad-read | DONE / SKIP | <e.g. "skipped — last broad-read was cycle N-2"> |
| 3 · Pick | <target> | from TRIAGE: <severity × cost> |
| 4 · Library fix | <files touched> | <what + why> |
| 5a · Targeted unit tests (contract + real-PDF) | PASS / FAIL | <N tests, M passed; both classes shown> |
| 5b · Broad pytest | PASS / FAIL | <N passed, M skipped> |
| 5c · 26-paper baseline | PASS 26/26 / FAIL | <regression details if any> |
| 5d · Full-doc AI verify (TIER 1) | PASS / FAIL · TEXT-LOSS=0 · HALLUC=0 | <papers verified, findings if any> |
| 5e · Camelot tests | PASS / FAIL / SKIP | <only if table-extraction touched> |
| 6a–c · Local-app parity (TIER 2) | PASS / FAIL | <diff result vs Tier 1 outputs> |
| 6d · UI smoke (every 3rd) | PASS / FAIL / SKIP | <5 tabs verified for one paper> |
| 7 · Cleanup + Review | PASS / FAIL | <delegated skill verdicts> |
| 7 · Release | vX.Y.Z tagged | <commit SHA> |
| 8a · Railway /_diag | DEPLOYED vX.Y.Z | <wall time> |
| 8b–c · Production parity (TIER 3) | PASS / FAIL | <diff result vs Tier 2 outputs, known-deltas applied> |
| 8d · Prod AI verify (every 3rd) | PASS / FAIL / SKIP | <one paper full AI-verify on prod output> |
| 9 · LEARNINGS appended | YES / NO | <theme if any> |
| 9 · TODO updated | YES | <pending count> |

### Issues surfaced this cycle
- ...

### AI-verify findings (Phase 5d / 8d — full-document structured read against pdftotext source)
- TEXT-LOSS findings: <count> — must be 0 to ship
- HALLUCINATION findings: <count> — must be 0 to ship
- SECTION-BOUNDARY findings: <count> — judged per finding
- METADATA-LEAK findings: <count> (new this cycle: <count>)

### Three-tier diff results
- Tier 1 (library) → Tier 2 (local-app): <bytes diff per paper; should be 0 for all>
- Tier 2 (local-app) → Tier 3 (production): <bytes diff per paper; should be 0 modulo known-deltas>
- New known-deltas added to `tmp/known-tier-deltas.md`: <list>

### Verdict: PASS / PARTIAL / FAIL / REVERT
```

## Notes on filling the template

- Every row is REQUIRED. If a phase was skipped, write `SKIP — <reason>`, not blank.
- AI-verify findings: count of each severity class. Zero is the goal; document each finding inline if nonzero.
- The three-tier diff section is what makes the report unambiguous about "this is shipped correctly across all environments." Don't summarize — list per-paper bytes diff.
- After printing this report, follow it with the current state of `tmp/iterate-todo.md` so the user sees the running backlog without scrolling.
