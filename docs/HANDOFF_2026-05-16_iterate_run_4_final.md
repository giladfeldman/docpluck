# Handoff — docpluck-iterate run 4 (fix-and-continue) — FINAL

**Authored:** 2026-05-16, end of run 4. **For:** a fresh `/docpluck-iterate` session.
This run executed `docs/HANDOFF_2026-05-16_iterate_run_4_fix_and_continue.md`'s three jobs.

## State at handoff

- Last shipped library version: **v2.4.45** (tag pushed, PyPI not published).
- docpluckapp `service/requirements.txt` pin: auto-bumped to **v2.4.45** (commit `26bf88f9`).
- Production `/_diag`: `docpluck_version = 2.4.45` — verified.
- 26-paper baseline: **26/26 PASS** at v2.4.45.
- Broad pytest: **0 failures** (the 15 pre-existing failures are resolved — see tests-regen).

## What run 4 shipped

| Item | Version | Outcome |
|---|---|---|
| JOB 1 — cycle 12 ligature rework | v2.4.44 | SHIPPED + prod-verified |
| JOB 3 — tests-regen | (no bump) | SHIPPED (`c831e28`) |
| JOB 3 — cycle 13 (G5b) | v2.4.45 | SHIPPED + prod-verified |
| JOB 2 — 3 fragmented golds | (cache) | REGISTERED under canonical DOI keys |
| skill — codex prerequisite note | (no bump) | committed `9aa4f5b` |

### JOB 1 — cycle 12 ligature rework (v2.4.44)
The session-3 cycle-12 attempt was broken (a duplicate `decompose_ligatures` call
before the pre-existing S3 step starved S3's tracking; `test_report_tracks_changes`
red). Reworked: removed the duplicate, unified S3 to call the single shared helper
(explicit U+FB00-FB06 ASCII table — NFKC of `ﬅ` yields a non-ASCII long-s), kept the
genuine `cell_cleaning` + render-post-process calls (table/caption/fence channels
bypass `normalize_text`). Stale narrative in CHANGELOG/LEARNINGS/lessons/TRIAGE
corrected. v2.4.44→ diff is ligature-only on korbmacher/jdm_m2/jdm16; 26/26.

### JOB 3 — tests-regen (`c831e28`, no version bump)
12 `test_extract_pdf_byte_identical` snapshots + 2 `test_sections_golden` goldens
regenerated (environmental pdftotext line-wrap drift; `extract_pdf` is a pure
pdftotext passthrough). The 15th failure, `test_request_09`, is **NOT** snapshot
drift — it is a real **COL-class** column-interleave defect (the numbered RSOS
bibliography renders as `References\n1. 2. 3. … 16.\n\nThaler RH…`, the number column
split from the entry text). Left red; tracked as the COL class.

### JOB 3 — cycle 13 (G5b, v2.4.45)
`render.py`'s numbered-heading promoters carried a `max_lc_run >= 5` prose guard
that demoted long descriptive headings. Reproduction showed real headings with
lowercase-runs up to 12 — the count cannot separate heading from prose, so "raise
5→8" would have been a partial fix. Removed the guard from
`_promote_numbered_subsection_headings` (multi-level dotted numbering is itself the
discriminator); kept it raised 5→8 in `_promote_numbered_section_headings`
(single-level numbers collide with enumerated lists). jdm_.2023.16: 19 headings
recovered; v2.4.44→v2.4.45 diff heading-promotion-only; 26/26.

### JOB 2 — 3 fragmented golds (Chen / Xiao / Efendic)
Regenerated all four views (`stats` / `reading` / `citations` / `intext_citations`)
for each of the 3 papers through `gold-generation.md` — dual stats extraction +
cross-check + reading/citations/intext carrier pass (12 subagents). Registered all
12 views under canonical DOI keys (`10.1016__j.jesp.2021.104154`,
`10.1080__23743603.2021.1878340`, `10.1177__19485506211056761`), producer
`article-finder`; `ai-gold.py audit` clean.

**Codex Step-4 cross-model verification was SKIPPED** (explicit user directive,
2026-05-16) because the `codex` CLI has a Windows UTF-8 file-read bug — it misreads
UTF-8 gold files as mojibake, flooding the verdict with false discrepancies. A full
report is at `~/ArticleRepository/docs/handoffs/2026-05-16_codex-cli-windows-encoding-issue.md`
(handed to the article-finder skill owner). The UTF-8-corrected Codex re-runs still
found **genuine** gold discrepancies (chen 28 / xiao 22 / efendic 19 — real citation
page-range swaps, missing title prefixes, a few wrong table cells) — the verdict
files are saved at `~/ArticleRepository/tmp/goldgen_run4/{chen,xiao,efendic}_verdict2.txt`
for article-finder's Step-4 fix-loop. The regenerated golds are dual-extracted +
cross-checked and supersede the old docpluck private-prompt golds, but they have NOT
passed Codex — a fix-loop is still owed (now article-finder's, per the directive).

## Open queue — JOB 3 remaining APA defect cycles (the run did NOT finish JOB 3)

**Standing verdict (rule 0e-bis): the APA corpus is NOT clean — ~11 papers still
FAIL Phase-5d.** This run shipped cycle 13 and re-scoped G5c; the cycles below remain.
Recommended order:

1. **G5c-1** — render-layer fold of an orphan multi-level `N.N.` line into an
   adjacent generic `##/###` heading (the `5.4.`/`## Discussion` case). C1-C2,
   ships independently. See TRIAGE "Cycle 14 (investigation)".
2. **FIG caption double-emission + truncation** — ~8 papers. S2, C2.
3. **G5c-2 + G5d + TABLE** — the section-partitioner cluster, C3, a dedicated
   session: G5c-2 (split-heading rejoin — pdftotext splits `N.N. Title` and the
   partitioner consumes the title word; 5 of 6 jdm_m2 cases), G5d (named/unnumbered
   heading demotion, ~7 papers), TABLE structure destruction (~11 papers, the single
   largest blocker).
4. **COL column-interleave** (incl. `test_request_09`'s numbered-bibliography split)
   and **GLYPH** deleted-minus — S0, C3-C4, layout-channel; escalate.

`test_request_09` will stay red until the COL class is fixed — it is a correct
regression test catching a real defect, not a stale fixture.

## Process notes / improvements

- The `codex` CLI Windows UTF-8 bug (above) is article-finder's `gold-generation.md`
  Step-4 to fix — report filed in the ArticleRepository handoffs dir.
- `ai-full-doc-verify.md` Step 1c now states the codex prerequisite (committed).
- Cross-skill lesson re-confirmed twice this run
  (`reproduce-triage-defect-at-head-before-trusting-cost-estimate`): both G5b and
  G5c were costed wrong in the TRIAGE — G5b deeper (guard removal, not 5→8), G5c
  deeper (partitioner, not a render fold). Always reproduce + measure at HEAD.

## Stop reason

Run 4 completed JOB 1, JOB 2, and 2 of JOB 3's items (tests-regen + cycle 13), and
re-scoped G5c. Stopped before the remaining JOB 3 cycles because they are a
fresh-session-sized block of C2-C3 section-partitioner work (G5c-2 / G5d / TABLE)
plus escalated C3-C4 layout-channel work (COL / GLYPH) — continuing to grind them in
an already-very-long session is the wrong call. The next `/docpluck-iterate` session
resumes at G5c-1 from the queue above.
