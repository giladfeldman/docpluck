# DP-2 + DP-5 flatten fixes — commit/coordination handoff (2026-06-22)

## 1. Goal
Commit the **DP-2 + DP-5 table-flatten fixes** (already complete + verified, working tree, v2.4.97) as a clean commit on top of the concurrent session's RC-T render-guard commit `84a4d42` (v2.4.96) — staging **only the 8 listed files** — without colliding with the parallel session that shares this working tree.

## 2. Why it matters
docpluck is a meta-science tool; a dropped or mis-bound table row silently corrupts downstream stat verification (effectcheck/ESCImate). DP-2 and DP-5 came from a real consumer handoff (`ESCIcheckapp/docs/DOCPLUCK_HANDOFF_2026-06-21.md`). **Two Claude sessions are editing this one working tree concurrently** (the other committed `84a4d42` mid-work), so the commit must stage explicit paths — a `git add -A`/`git add .` from either session would sweep the other's unfinished work into the wrong commit (memory `release-version-collision-with-parallel-uncommitted-stream`).

## 3. State at handoff
- Branch: `feat/rc-t-table-region-guard`
- HEAD commit: `84a4d42` (`fix(render): RC-T — strip Camelot tables that are absorbed body prose (v2.4.96)`) — committed by the **concurrent session** (Gilad Feldman, 2026-06-22 07:56), not this one.
- Committed in this session: **none** (this session did not commit, per the "commit only when asked" rule).
- Uncommitted (this session's DP-2/DP-5 work, all on top of `84a4d42`):
  - `docpluck/tables/flatten.py` — DP-2 Pass 4.5 (type blank `p`/`df`); DP-5 `_classify_column` sentinel-aware + `_detect_column_groups` equal-width-block arm alignment
  - `docpluck/tables/cell_cleaning.py` — DP-5 `_DATA_VALUE_CELL_RE` + `_is_header_like_row` data-value recognition
  - `docpluck/extract_structured.py` — `TABLE_EXTRACTION_VERSION` `2.4.0` → `2.4.1` (DP-2/DP-5 note)
  - `docpluck/__init__.py` — `__version__` `2.4.96` → `2.4.97`
  - `pyproject.toml` — `version` `2.4.96` → `2.4.97`
  - `CHANGELOG.md` — new `[2.4.97]` entry
  - `tests/test_tables_flatten_blank_header_recovery.py` — DP-2 tests added (`test_separate_arm_p_and_df`, `test_joint_arm_p_and_integer_df`, packed-arms p/df assertions)
  - `tests/test_tables_superheader_alignment_real_pdf.py` — **new** (DP-5 real-PDF + contract tests)
- Working artifacts (gitignored, safe to ignore/delete): `tmp/repro_dp.py`, `tmp/dbg_dp2.py`, `tmp/cache_and_flatten.py`, `tmp/flat_mine.json`, `tmp/flat_head.json`, `tmp/tblcache/*.json`.

## 4. What's done (verified)
- **DP-2 — 77859 Table 3 `fields` now include `p` + `df`.** `_recover_blank_roles` Pass 4.5 types the operator-less `.XXX` p column and the integer/Welch-decimal df column it previously skipped. Verified: the DP-2 tests **fail at HEAD** (`KeyError: 'p'`) and **pass** after; `flatten_table` on the live PDF yields `p=.551, df=260.54` for the Separate arm.
- **DP-5 — 90203 Table 10 emits all 6 conditions, correctly arm-split.** Handoff blamed Camelot, but Camelot extracted all 6 rows — `flatten` dropped the first data row (mistook it for a 3rd header row) then mis-bound the centered super-header. Three coupled fixes (header-detection, block-alignment, folded-header classify). Verified: Table 10 → 12 rows (6 conditions × Target/Replication) with the **exact** handoff values (`r=.63, n=170, CI [0.53,0.72]` for Identifiable/Explicit); rendered `.md` `<table>` shows all 6 rows; real-PDF tests fail-at-HEAD/pass-after.
- **Incidental correct improvements** (same root cause): `xiao_2021` T4 Original/Replication F **un-swapped** (was wrong at HEAD — a canary), `chan_feldman` T8 arm labels recovered (canary), `jama_open_2` T3 HR estimates+CIs recovered.
- **No clean-table regression**: full-corpus (101-PDF) **deterministic cached-table flatten diff** (mine vs HEAD) — every change is a recovered row, a correct arm split, a recovered field, or a removed stat-less spurious row; already-garbage tables (chen T9, aom amd_2, ieee T10) shuffle but no clean table regressed. 285 contract tests pass; both touched test files pass per-file (superheader 7/7, flatten_blank_header 27/27).

## 5. What's next (numbered, concrete)
1. **Coordinate with the concurrent session first.** Confirm the other session has finished writing to the working tree (or have it commit/stash its own files) so the two change-sets don't interleave. Both sets are on `84a4d42`; they touch disjoint files (theirs: `render.py`; mine: `flatten.py`/`cell_cleaning.py`), so they compose cleanly.
2. **Commit DP-2 + DP-5 as v2.4.97, staging only these 8 files** (never `git add -A`):
   ```bash
   git add docpluck/__init__.py pyproject.toml docpluck/extract_structured.py \
           docpluck/tables/cell_cleaning.py docpluck/tables/flatten.py \
           tests/test_tables_flatten_blank_header_recovery.py \
           tests/test_tables_superheader_alignment_real_pdf.py CHANGELOG.md
   git commit -m "fix(tables): DP-2 type blank p/df + DP-5 two-header-row recovery & super-header alignment (v2.4.97)"
   ```
   (Optional: split into two commits — DP-2 = `flatten.py` Pass 4.5 + the `test_tables_flatten_blank_header_recovery.py` additions; DP-5 = `cell_cleaning.py` + the rest of `flatten.py` + the new test file — if independent revertability is wanted. The version-bump files go with whichever commit ships last.)
3. **Before any `git tag v2.4.97` / release**: run the formal Sonnet canary AI-verify (the project's keystone gate — `references/ai-full-doc-verify.md`) on the touched canaries (`90203` maier, `xiao`, `chan_feldman`) against the article-finder golds, and the 26-paper baseline. Tagging fires `bump-app-pin.yml`, so do not tag until that gate is green (run `python scripts/check_app_pin_sync.py` after).
4. **Architectural backlog — leave as documented backlog** (user decision 2026-06-22). Do NOT start RC-T Layer-1 recovery or RC-1 default-flip this stream. The four remaining handoff defects map to existing tracked work (see §6 / §8).

## 6. Open decisions
- **Tag/release v2.4.97 now, or batch with later table work?** Options: (A) tag now — ships the fixes to the app via the pin bump, but each tag is a Railway redeploy; (B) leave committed-but-untagged and batch with the next table cycle. **Recommendation: (B)** — the concurrent session's v2.4.96 is also untagged on this branch; tag once when the branch's table work is consolidated, after the formal canary AI-verify. Confirm with the user.
- **Commit granularity (1 vs 2 commits).** Recommendation: **1 commit** — DP-2 and DP-5 are both from the same handoff, ship together as v2.4.97, and were verified together; the CHANGELOG documents both. Split only if you specifically want per-defect revertability.

## 7. Watchouts
- **Shared working tree (live collision risk).** The other session committed `84a4d42` while this session worked. NEVER `git add -A`/`git add .` — stage the 8 explicit paths only. Verify `git status` shows nothing unexpected staged before committing.
- **Real-PDF Camelot tests flake under *cumulative* load — even serially.** Running 13 Camelot-heavy test files in one `pytest` process flaked 9 ("no tables extracted"); each passes per-file. So the canonical `pytest tests/ -q` whole-suite run is unreliable for the table real-PDF tests — run them **per file** (or in small batches) to gate. This is a pre-existing infra issue (`test_rc_t_degenerate_table_real_pdf.py` docstring notes the xdist variant; this extends it to serial cumulative load). Not fixed here.
- **DP-5 was misdiagnosed in the source handoff** ("Camelot drops a row" → actually a `flatten` header-miscount). Reproducing at HEAD before coding is what caught it (memory `reproduce-triage-defect-at-head-before-trusting-cost-estimate`). Apply the same to DP-1/DP-6 before assuming they're Layer-1.
- **Version already bumped in the working tree** (`__version__`/`pyproject` → 2.4.97, `TABLE_EXTRACTION_VERSION` → 2.4.1). Don't double-bump.
- **No formal Sonnet AI-gold verify run yet** (only deterministic + the consumer-handoff's AI-derived expected values, which my output matches exactly). The project rule is AI-gold is the verdict — run it before tagging (§5 step 3).
- **`NORMALIZATION_VERSION` / `SECTIONING_VERSION` intentionally NOT bumped** — this change is table-flatten only.

## 8. Context pointers
- Source defect list (the 6 DP defects): `../../../../ESCIcheckapp/docs/DOCPLUCK_HANDOFF_2026-06-21.md`
- Living work queue (RC-T / RC-1 architectural backlog = DP-1/3/4/6): `docs/TRIAGE_2026-06-21_head_v2.4.95_assessment.md`
- RC-T spec (DP-1/DP-6 Layer-1 recovery is the out-of-scope follow-on): `docs/superpowers/specs/2026-06-21-rc-t-table-region-prose-contamination.md`
- RC-1 spec (DP-3/DP-4 interleave; banded flag exists, default-OFF pending Step-2 polish): `docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md`
- This session's tests: `tests/test_tables_superheader_alignment_real_pdf.py`, `tests/test_tables_flatten_blank_header_recovery.py`
- Release/AI-verify gate: `.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md`; app-pin gate `scripts/check_app_pin_sync.py`
- Memories: `feedback_docpluck_app_pin_sync` (verify origin/master before/after tag), `feedback_canary_audit_clobbers_phase5d` (don't trust AUDIT_DEFERRED PASS), `feedback_general_fixes_not_pdf_specific`, `release-version-collision-with-parallel-uncommitted-stream`

### Architectural backlog (DP-1/3/4/6 — left as documented backlog per user decision 2026-06-22)
| Defect | Paper | Maps to | Status |
|---|---|---|---|
| DP-1 | 77859 Table 1/2 not extracted (Camelot 0 cells) | RC-T **Layer-1** recovery (`table_areas`) | deferred — out-of-scope in RC-T spec |
| DP-3 | 37122 figure-caption interleaved between stat & CI | RC-1 column interleave | deferred — banded flag exists, default-OFF |
| DP-4 | cog_emo under-extraction (22 vs 47) | RC-T + RC-1 | partial (T6 prose-strip in `84a4d42`; T8 arm labels in v2.4.97); rest deferred |
| DP-6 | 37122 results-summary table mashed into prose | RC-T Layer-1 / RC-1 | deferred |
