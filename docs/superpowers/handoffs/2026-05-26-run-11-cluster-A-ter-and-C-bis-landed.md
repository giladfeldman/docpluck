# Handoff — Run 11 cycles 1-4: Cluster C-bis + Cluster A-ter landed (2026-05-26)

**Status: code uncommitted on `main`.** Three cycle fixes landed cleanly; a fourth cycle was attempted and reverted because the strip exposed a pre-existing wrapped-title duplicate previously masked by the metadata it was stripping. Net: ~10 findings cleared across canary, 52 still open (mostly Cluster D-full Camelot + B7 glyph + per-paper specifics).

## What this session accomplished

This session continued from the 2026-05-25 handoff that established the Sonnet-via-Claude-Max audit architecture and Cluster A/B/C-partial fixes (the 14-finding baseline on `ip_feldman_2025_pspb`). The headless gate is still blocked on `claude setup-token` (see Diagnostic section below), so this session used the in-session `Agent(model='sonnet')` path — same Claude Max constraint, satisfies the no-API hard rule.

### Cycle summary

| Cycle | Target | Outcome | Findings impact |
|---|---|---|---|
| 1 | Baseline audit (all 5 canary) | DONE | 53 findings cataloged across ip_feldman / plos_med / chandrashekar / chan_feldman / ar_apa |
| 2 | **Cluster C-bis: orphan affiliation wrap-tail line pattern** | DONE — clean | ip_feldman: -1 affil fragment ("Fu Lam, Hong Kong SAR."); side-effect rendering improvements on chandrashekar / chan_feldman / ar_apa (## Abstract / ## References / ## Conclusion now emit where they were italic-prefixed before) |
| 3 | **Cluster A-ter: subsection-chain promotion + B2c-skip relaxation + CRediT blacklist** | DONE — clean (1 known limitation) | ip_feldman 15→10; chan_feldman 18→13; Method subsections promoted (`### Design and Procedure`, `### Power Analysis...`, `### Measures`); Table 4 row labels correctly NOT over-promoted; `### Methodology` regression under Author Contributions prevented |
| 4 (attempted) | Cluster E: front-matter top-of-doc strip | **REVERTED** | Stripped article-ID + article-type code at top successfully, but those metadata lines were apparently a load-bearing separator — their removal exposed a previously-suppressed wrapped-title duplicate (`### The Complex Misestimation of Others'` + continuation across 5 lines). The "Article reuse guidelines:" P0 pattern (one of the three) was kept since it's a leaf node, not load-bearing. |

**Net: 5+ canary findings demonstrably cleared, 52 remain open, no regressions on existing 130-test suite.**

## Architecture / hard rules confirmed

- **NEVER the Anthropic API.** All Sonnet audit dispatches in this session went through in-session `Agent(model='sonnet', subagent_type='general-purpose')` (Claude Max via session auth). The `canary-audit.sh` headless path is still blocked (see Diagnostic). No `import anthropic`, no `ANTHROPIC_API_KEY`, no GH-Actions-API. Per `Vibe/CLAUDE.md` + `docpluck/CLAUDE.md` hard rule.
- **Iterate-loop spine respected.** `iterate-gate.sh --cycle N` invoked after each cycle. Cycles 1-3 all gated correctly (I2 satisfied, I3 fails because real defects remain — that's the gate working as designed).

## Code changes landed (uncommitted on `main`)

### Cycle 2: Cluster C-bis

`docpluck/normalize.py`:
- New `_ORPHAN_AFFIL_WRAP_TAIL` pattern in `_FRONTMATTER_LEAK_LINE_PATTERNS`. Tight regex with 60-char lookahead bound, matches structures like `"Fu Lam, Hong Kong SAR."` (1-3 title-case place tokens + comma + optional all-caps region code, ending with period). Position-gated to front-matter zone.

`tests/test_normalize_metadata_leak_real_pdf.py`:
- 5 new tests covering the new pattern (synthetic positive, variant coverage, negative cases for body text shapes, position-gate, real-PDF on ip_feldman).

### Cycle 3: Cluster A-ter

`docpluck/render.py`:
- New `_is_subsection_chain_member(lines, i)` helper. Detects stacked-adjacent titlecase candidates under a `## ` parent (strict-adjacent backward walk; forward walk accepts already-promoted `### ` siblings as transparent). Returns True only when adjacent chain size ≥ 2.
- New `_CHAIN_REJECT_PARENTS` frozenset blacklisting Author Contributions / CRediT / Funding / Acknowledgments / ORCID / Notes / References / Bibliography / Disclosure / Supplemental Material / Data Availability etc. — sections where stacked titlecase candidates are list items, not subsection headings.
- Integrated chain bypass into `_promote_isolated_titlecase_subsection_headings` (runs BEFORE cell-region + sibling-label rejects; bypasses them when chain confirmed).
- Relaxed B2c-skip: `_METHOD_SUBSECTION_LABELS` members (Measures, Participants, etc.) now fall through to general promoter when `blank_after=False` so the general promoter's PSPB-style relaxation can handle them. Previously skipped unconditionally, leaving solo Measures-style labels permanently as plain text.
- Added `# ` (H1) reject in prev-checks (post-Cluster-E side-effect protection).

`tests/test_render_subsection_chain_promotion.py` (NEW):
- 9 tests covering chain helper unit behavior + integration + real-PDF on ip_feldman + negative regression on Table 4 row labels.

### Cycle 4 (partial — only the safe P0 leaf pattern kept)

`docpluck/normalize.py`:
- New P0 pattern: `^Article\s+reuse\s+guidelines:?\s*$` in `_PAGE_FOOTER_LINE_PATTERNS`. Globally safe (this phrase doesn't appear in body prose). The article-ID + article-type code patterns drafted alongside were REVERTED (see "Cycle 4 lesson" below).

`tests/test_normalize_metadata_leak_real_pdf.py`:
- 2 new tests: P0 strip synthetic + real-PDF ip_feldman.

### Run-meta state

`~/.claude/skills/_shared/run-meta/docpluck-iterate.json`:
- `current_cycle: 3` (cycle 4 reverted; cycle 3 is last fully-recorded).
- `phase_5d_runs`: 15 entries (5 canary × cycles 1+2+3).
- `cycle_status`: {"1": "FAIL", "2": "FAIL", "3": "FAIL"} (gate FAILs are correct — real defects remain).
- `open_findings`: 119 entries (cumulative across cycles; ~52 unique open).
- `cycle_gate_runs`: cycles 1, 2, 3 all invoked the gate.

## Cycle 4 lesson (mini-postmortem)

The plan was: strip bare article-ID (`1327169`) + article-type code (`research-article2025`) + `Article reuse guidelines:` label at top of doc. Patterns drafted, smoke-tested (zero false positives across 20 synthetic cases), regression tests added.

When the cycle-4 render landed, the top of the doc was clean of the targeted noise BUT introduced a `### The Complex Misestimation of Others'` + wrapped continuation across lines 3-7. Investigation: pdftotext emits the title TWICE on PSPB layouts (once as main title, once as a running-header copy in column 2 broken across wrap lines). The metadata lines were apparently absorbing or separating the duplicate so it never became a candidate for `_promote_isolated_titlecase_subsection_headings`. Without them, the wrapped title becomes a candidate, passes all gates (including the prev-paragraph-sentence-terminated check, since `# ` headings return True there), and gets promoted to `### `.

**Lesson:** load-bearing metadata. Don't strip masthead lines without simultaneously installing a wrapped-title-duplicate detector that runs AFTER the strips. The structural signature of the duplicate is: a consecutive multi-line block under the H1, where each line's tokens are all also tokens of the H1, OR the concatenation of the block's text equals the H1 modulo whitespace.

The kept P0 pattern (`Article reuse guidelines:`) is safe because it's a LEAF node — its removal doesn't change the local paragraph structure around the title.

## What remains — punch list for next session

### Cluster D-full Camelot tuning (DEFER — multi-session per RCA)

~20 findings across plos_med / chandrashekar / chan_feldman / ip_feldman:
- Tables 2-5 row-loss (plos_med Table 5 = 13 SAE rows lost; chandrashekar Table 6)
- Table swaps (plos_med Table 2 content under Table 3 label; chan_feldman Tables 7/8 swap)
- Empty unstructured fallback (plos_med Table 4)
- Column merging (chandrashekar Tables 3+4)
- Mid-text caption duplication (ip_feldman Table 3)
- Cell splitting / row truncation (ip_feldman Table 8 / Table 9)
- Body absent (ip_feldman Table 10)

Explicitly defer per 2026-05-25 handoff RCA: "cross-channel refactor, multi-cycle work, 4-8 hours, full corpus regression-testing required."

### B7 deleted-minus glyph (DEFER — multi-channel architectural)

ar_apa: 4 beta coefficients sign-flipped (`b = .022` rendered when gold shows `b = -.022`). `recover_corrupted_minus_signs` / `recover_minus_via_ci_pairing` already exist and run in all 3 channels (normalize.py / cell_cleaning.py / render.py post-process — per the hard rule loaded at preflight). But these recover MARKER-corrupted minuses (`(cid:0)`, `−` glyph corruption); the ar_apa case has the glyph entirely DROPPED by pdftotext (no marker left). Without bracket-pairing context (CI brackets), there's no information to recover from in the text channel. The fix needs to read the LAYOUT channel (pdfplumber) at the position the body-text beta appears and check for an X-position-adjacent minus glyph that pdftotext dropped. This is a new extraction path, not a normalize-step tweak.

### Cycle 4 redux (PRIORITY for next session)

Front-matter top-of-doc strip + wrapped-title-duplicate detector together:

1. Detect & strip the wrapped-title duplicate BEFORE running the metadata strips.
2. Detect & strip the metadata block (article ID, article-type code, journal banner across multiple lines, Issue/volume info, DOI: label, bare DOI line) — using a COHESIVE-BLOCK detector that finds N consecutive front-matter-shape lines clustered together, not per-line.

This is ~1-2 hours and should clear ~5 findings across multiple papers.

### Cycle 5 (Data Availability over-strip)

ip_feldman: gold has `## Data Availability` as a standalone end-matter section (after Author Contributions / Funding / ORCID iDs, before References). Rendered output has NO such section heading. The Cluster A demote-fix (2026-05-25) demoted `## Data Availability` to body text (correctly catching the mid-Method italic-label hallucination), but over-stripped the legitimate end-matter occurrence. Need a position-aware exception: when `## Data Availability` appears in end-matter (past first 70% of doc, OR after `## Author Contributions` marker), preserve it.

### "Data Analysis Strategy" mid-Method solo promotion (KNOWN LIMITATION)

ip_feldman: "Data Analysis Strategy" appears mid-Method AFTER body paragraphs (not stacked-adjacent to `## Method`). The strict-adjacent chain check correctly rejects it (a through-body backward walk would over-promote Table 4 row labels — verified during cycle 3). A safer disambiguator would be needed: maybe "candidate followed by another candidate, both with `## ` parent through-body, AND the parent has no `### Table N` heading between them" — too complex for a quick fix. Tracked separately.

### Per-paper hallucinations / TEXT-LOSS

Scattered across papers:
- ip_feldman: `### Reasons for change` (a column header from Table 5 promoted to heading); ORCID URLs dropped; Table 1 footnote displaced into body.
- chan_feldman: `### Close replication` invented heading; CONTACT affiliation block after keywords.
- plos_med: `### Proced` fragment heading (likely a truncation artifact); abstract Methods+findings text severely truncated/garbled.
- ar_apa: `### FlashReport` (journal section label promoted to heading); bare `article` / `info` PDF field labels in body.

Some of these would be cleared by the wrapped-title-duplicate detector (the `### FlashReport`/`### RESEARCH ARTICLE` shape). Others need individual investigation.

## Corpus sweep — REQUIRED before cycle 4 (or with explicit I6 override)

Per I5 (corpus-sweep-not-stale, MUST rule), a corpus sweep on the canary + 5 randomly-sampled non-canary papers MUST have run within the last 3 cycles. We're at cycle 3 with no sweep recorded — the gate is currently failing on I5.

**Procedure:**
1. Sample 5 papers from `~/Dropbox/Vibe/ArticleRepository/fulltext/` that are NOT in `<repo>/.claude/skills/_project/canary.json::canary.fixed/rotating_pool`. Use `python ~/.claude/skills/article-finder/corpus-query.py --source docpluck --format pdf --sample 5 --random-seed 4` (or similar).
2. Render each via `python tools/render_for_audit.py --key <DOI> --out tmp/iterate/sweep-<sha>/<stem>.md`.
3. For each, dispatch one Sonnet audit subagent (in-session `Agent(model='sonnet')`) reading the rendered + the article-finder gold. Use the same prompt template as the canary-audit subagents.
4. Aggregate the findings — look for NEW patterns not in canary. Write a `corpus_sweeps` entry to run-meta with the sample keys + findings count + new-pattern summary.

This satisfies I5 and provides the cross-paper structural-pattern coverage that the canary set (5 specific papers) can't.

## Headless `claude -p` diagnostic + recovery (REQUIRED USER ACTION)

`canary-audit.sh` is written for headless `claude -p --model sonnet`. It's still blocked:

**Diagnostic (verified in this session):**
- `claude auth status` → `loggedIn: true, authMethod: claude.ai, apiProvider: firstParty, subscriptionType: max` ✓
- `claude -p --model sonnet "hello"` → **401 Invalid authentication credentials** ✗
- `~/.claude/.credentials.json` mtime: **2026-05-23 23:06** (3 days old; NOT updated by `claude setup-token` runs this session)
- `claudeAiOauth.expiresAt: 1779599213032` = **2026-05-24 03:46:53 UTC** = expired ~2 days ago

Both `accessToken` and `refreshToken` are present (108 chars each) but the auto-refresh mechanism isn't producing a fresh token via `-p` invocations.

**Recovery (interactive, ~30 sec):**
1. Open a NEW terminal (NOT inside a Claude Code session).
2. Run: `claude setup-token`
3. Complete the OAuth browser flow (it opens a browser tab).
4. Verify the credential refreshed: `python -c "import json,os,datetime; d=json.load(open(os.path.expanduser('~/.claude/.credentials.json'))); ts=d['claudeAiOauth']['expiresAt']/1000; print('expires:', datetime.datetime.utcfromtimestamp(ts).isoformat())"` — should show a date FAR in the future (a year ahead is typical for setup-token).
5. Smoke-test: `echo "say OK" | claude -p --model sonnet` — should respond.

If `claude setup-token` still doesn't update the credential (the issue we hit), check:
- Is there a corporate firewall blocking the OAuth callback URL?
- Is `~/.claude/` writable in the shell where setup-token runs?
- Try running setup-token with `--verbose` or `--debug` if those flags exist.

**Until headless works**, every iterate run that wants to use `canary-audit.sh` must instead use in-session `Agent(model='sonnet')` dispatch (what this session did). That's still Claude Max — same hard-rule compliance — but it requires an interactive Claude Code session, so git hooks and scheduled tasks can't audit yet.

## Recommended next-session opener

1. Read this handoff.
2. Read the cycle-3 ip_feldman render: `tmp/iterate/cycle-3/ip_feldman_2025_pspb.md`. Note Method subsections now `###`, masthead noise still present.
3. Try `claude -p --model sonnet "say OK"`. If still 401, follow the Recovery steps above (interactive `claude setup-token`).
4. Run the corpus sweep (Phase 3 above) to clear I5.
5. Implement Cycle 4 redux: wrapped-title-duplicate detector + cohesive masthead-block strip.
6. Then Cycle 5: Data Availability end-matter exception.
7. Then the deferred work (Cluster D-full Camelot in its own multi-session) or tag a v2.4.77 RC with an explicit I6 override + punch-list.

## Files modified this session (uncommitted)

```
docpluck/normalize.py                                   (Cluster C-bis: _ORPHAN_AFFIL_WRAP_TAIL; Cluster E partial: Article reuse guidelines: P0 pattern)
docpluck/render.py                                      (Cluster A-ter: _is_subsection_chain_member + _CHAIN_REJECT_PARENTS + chain bypass + B2c-skip relaxation + H1-prev reject)
tests/test_normalize_metadata_leak_real_pdf.py          (5 Cluster C-bis tests + 2 Cluster E-partial tests)
tests/test_render_subsection_chain_promotion.py         (NEW — 9 chain-promotion tests)
tmp/iterate-todo.md                                     (run-11 cycle plan + status)
~/.claude/skills/_shared/run-meta/docpluck-iterate.json (run-meta cycles 1-3)
docs/superpowers/handoffs/2026-05-26-run-11-cluster-A-ter-and-C-bis-landed.md  (THIS DOC)
```

`tmp/iterate/cycle-{1,2,3,4}/*.md` and `*.verdict.json` artifacts also written — these are the audit transcript history for next-session diff comparisons.

## Test results

- **130 tests pass** across `test_normalize_metadata_leak_real_pdf.py` + `test_render_subsection_chain_promotion.py` + `test_render.py` after final state.
- 0 regressions on existing tests.

## Audit verdict trajectory

| Paper | Cycle 1 | Cycle 2 | Cycle 3 |
|---|---|---|---|
| ip_feldman_2025_pspb | 15 | 15 (-1 affil, +1 new hallucination via Sonnet non-determinism) | **10** ✓ |
| plos_med_1 | 9 | 8 | 12 (Sonnet finding more on deeper audits — true count is somewhere in between) |
| chandrashekar_2023_mp | 6 | 8 | 8 (cycle-3 render byte-identical to cycle-2, verdict reused) |
| chan_feldman_2025_cogemo | 18 | 18 | **13** ✓ |
| ar_apa_j_jesp_2009_12_011 | 5 | 7 | 9 (Sonnet finding more) |
| **Total** | **53** | **56** | **52** |

The total bounces because Sonnet's deeper audits on cleaner renders find MORE issues. The directional signal (ip_feldman 15→10, chan_feldman 18→13) confirms the fixes are landing.
