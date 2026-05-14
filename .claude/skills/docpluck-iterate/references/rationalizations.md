# Common rationalizations (red flags — STOP if you catch yourself thinking these)

> Loaded on demand when you catch yourself about to skip a verification step. Consult during Phase 5, 6, 8, 10 (any judgment call).

| Rationalization | Reality |
|-----------------|---------|
| "I'll skip the broad-read this cycle, the TRIAGE looks fresh" | TRIAGE staleness is the #1 source of wasted iterations. The schedule is "cycle 1 + every 3–5". |
| "I'll bundle two fixes in one cycle to save time" | Two fixes can't be reverted independently. One cycle = one defect class. |
| "Targeted tests pass, I can skip the 26-paper baseline" | The baseline is the regression gate. It exists because targeted tests miss cross-paper effects. |
| "30-line eyeball was clean, I can skip the full-doc AI verify" | The 30-line eyeball catches title-block issues; mid-document text loss / hallucinations only surface in the FULL read. Phase 5d is mandatory every cycle (rule 0a/0b). |
| "Char-ratio + Jaccard passed; the AI verify is paranoid" | Char-ratio and Jaccard are BOTH blind to "right words wrong order under wrong heading" AND to single-paragraph drops (a 1% char loss is invisible to char-ratio but is a paragraph of someone's results section). The AI verifier is the gate, not these. |
| "Synthetic text test is faster than fixing a PDF fixture path" | Synthetic-text tests are contract tests, not regression tests. They cover the helper's branching, not the bug surface. Rule 0d requires a `*_real_pdf` test for every cycle's fix. |
| "The library works standalone, the app will obviously work too" | v2.4.13 incident: Camelot installed locally but absent on prod. Library passed every test for months. Prod returned 0 structured tables on every PDF. Tier 2 parity is non-negotiable (rule 0c). |
| "Tier 2 diff has a trailing newline difference, ignore it" | If you don't document the delta in `tmp/known-tier-deltas.md`, the next cycle will chase it as a phantom regression. Document or fix — never silently ignore. |
| "Deploy is fine, /_diag check is slow" | /_diag is the cheap part. Tier 3 prod parity (Phase 8c) is the expensive but mandatory part. Skip only when the cycle's target class has no app-surface impact. |
| "I'll skip LEARNINGS this cycle, nothing novel happened" | Boring cycles are also signal. If nothing novel, write a one-line "no surprises" entry — don't skip. |
| "I'll let postflight run automatically, no need to print the heartbeat" | Postflight without the visible heartbeat = silent skip = no card written = no learning. ALWAYS print. |
| "User's not around, I'll make the architectural call myself" | Architectural changes are MUST-STOP. Wait or revert and surface. |
| "TEXT-LOSS finding is minor, just one paragraph dropped" | There is no "minor text loss" in a meta-science extraction library. A scientist downstream cannot be told "we silently dropped one paragraph but the rest is fine." Revert. |
| "Hallucination is just one weird sentence, the rest of the .md is fine" | A single hallucinated citation or value can become someone's published research artifact. Revert. |
| "AI verify is too slow on a big paper, I'll spot-check 30 lines instead" | Split the paper into multiple subagent calls — that's the supported pattern. Spot-checking is rule 0a/0b violation. |
| "The fix is small, no real-PDF test needed, the contract test covers it" | Small fixes break in big ways exactly because nobody added the real-PDF test. Rule 0d. |
| "I'll do Tier 2 and Tier 3 in parallel to save time" | Sequential, not parallel (rule 15). Tier 2 failure that's fixed before Tier 3 starts saves a deploy roll-back. |
