# Handoff — docpluck-iterate run 4: fix-and-continue (fresh session)

**Authored:** 2026-05-16, end of session 3. **For:** a fresh `/docpluck-iterate` session.
**Read this whole file before touching anything.** It is self-contained — it assumes no memory of session 3.

You have **three jobs, in this order**:

1. **JOB 1 — Resolve the in-flight cycle 12 (ligature fix).** It is committed-nowhere, sitting uncommitted in the working tree, and it is **broken** — it introduced a test regression and duplicates an existing normalize step. Decide: rework it, or revert it. **Do not commit it as-is.**
2. **JOB 2 — Finish the article-finder AI-gold integration.** ArticleFinder shipped its side and left docpluck a punch-list (`docs/handoffs/` — see §JOB 2). docpluck's session-3 fix (commit `ac34c7e`) did part of it; the rest is open.
3. **JOB 3 — Continue the APA iteration loop** from the TRIAGE punch-list.

Invoke the `docpluck-iterate` skill normally (it runs its own preflight). Then work these three jobs.

---

## 0. Immediate git / working-tree state

- Repo: `C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck`, branch `main`.
- Last commit: `5cc321a docs: add AI-gold instructions from article-finder coordination`.
- Recent history (all session 3, all clean, all prod-deployed): `bbad28f` v2.4.43 (cycle 11), `ac34c7e` skill-fix (gold delegation), `9b41e4d` v2.4.42 (cycle 10), `951b00a` v2.4.41-ish… — i.e. **v2.4.43 is the last shipped library version.**
- **Uncommitted working tree = the cycle-12 ligature attempt (v2.4.44).** Modified: `docpluck/normalize.py`, `docpluck/render.py`, `docpluck/tables/cell_cleaning.py`, `docpluck/__init__.py`, `pyproject.toml`, `CHANGELOG.md`, `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md`, `.claude/skills/docpluck-iterate/LEARNINGS.md`, `.claude/skills/_project/lessons.md`; untracked new file `tests/test_ligature_decomposition_real_pdf.py`.
- 26-paper baseline at the cycle-12 working tree: **26/26 PASS, 0 WARN** (re-confirmed).
- Broad pytest at the cycle-12 working tree: **16 failed / 1233 passed**. 15 of the 16 are the long-standing pre-existing set (12× `test_extract_pdf_byte_identical` snapshot drift + 2× `test_sections_golden` + 1× `test_request_09`). **The 16th is cycle-12-introduced** — see JOB 1.

---

## JOB 1 — Cycle 12 (ligature decomposition) is BROKEN. Rework or revert.

### What cycle 12 attempted

Goal: decompose Latin typographic ligatures (`ﬀ ﬁ ﬂ ﬃ ﬄ ﬅ ﬆ`, U+FB00-FB06) — a corpus scan found them in 35 rendered `.md` files (`korbmacher` 82×, `jdm_.2023.16` 34×). The attempt added a new `normalize.py::decompose_ligatures` helper (per-char NFKC scoped to `[ﬀ-ﬆ]`) and wired it into three channels: `normalize_text` body (right after the NFC step, ~line 1567), `tables/cell_cleaning._html_escape`, and `render_pdf_to_markdown` post-process. Bumped to v2.4.44, NORMALIZATION_VERSION 1.9.8.

### Why it is broken

**docpluck `normalize.py` ALREADY HAS a ligature-expansion step** — `S3_ligature_expansion` at **`normalize.py` ~line 1687**:

```python
t = t.replace("ﬀ", "ff")   # ﬀ
t = t.replace("ﬁ", "fi")   # ﬁ
t = t.replace("ﬂ", "fl")   # ﬂ
t = t.replace("ﬃ", "ffi")  # ﬃ
t = t.replace("ﬄ", "ffl")  # ﬄ
report._track("S3_ligature_expansion", before, t, "ligatures_expanded")
```

The cycle-12 `decompose_ligatures(t)` call was inserted EARLY in `normalize_text` (~line 1567, just after the NFC step) — it consumes every ligature **before** S3 runs. So S3 now finds nothing, tracks `ligatures_expanded = 0`, and `tests/test_normalization.py::TestFullPipeline::test_report_tracks_changes` fails:

```
raw = "signiﬁcant eﬀect −0.73"
assert report.changes_made.get("ligatures_expanded", 0) > 0   # -> 0, FAIL
```

That is the 16th pytest failure. **Cycle 12 starved a pre-existing step.**

### The real question to answer first

If `S3_ligature_expansion` already expands ligatures in the normalize body channel, **why did 35 rendered papers still show raw `ﬁ`/`ﬂ` glyphs?** Cycle 12 was triggered by that observation. Possible causes — INVESTIGATE before reworking:

- The rendered `.md` body may come from a path/level that does not run S3 (check what normalization level `render_pdf_to_markdown` applies to body text, and whether `preserve_math_glyphs` or a `NormalizationLevel` branch skips S3).
- S3 only covers FB00-FB04 — it does **not** handle `ﬅ` (FB05) / `ﬆ` (FB06). Those would survive S3.
- The ligatures in the render may come from channels that genuinely bypass `normalize_text` entirely: Camelot table cells (`cell_cleaning`), figure/table captions, `unstructured-table` fenced blocks, `raw_text` fallbacks.

### Correct rework (recommended)

1. **Remove** the early `decompose_ligatures(t)` call from `normalize_text` (~line 1567). The body channel already has S3 — do not starve it.
2. If S3's FB00-FB04-only coverage is the gap, **extend the existing S3 step** to also map `ﬅ`/`ﬆ`→`st` (and keep its `report._track` call intact).
3. The `cell_cleaning` + `render` post-process `decompose_ligatures` calls are probably the genuine fix (those channels bypass S3) — **verify** by rendering `korbmacher` / `jdm_.2023.16` with ONLY those two calls (no `normalize_text` call) and confirming 0 residual ligatures. Keep them if they close a real gap; the shared helper is fine to keep for those two channels.
4. Re-confirm `test_report_tracks_changes` passes, run the 26-paper baseline, AI-verify (see JOB 2 — golds now come from article-finder).
5. **Fix the stale narrative:** the uncommitted `CHANGELOG.md`, `LEARNINGS.md`, `_project/lessons.md`, and `TRIAGE` entries for cycle 12 currently claim a clean *new* fix. They are wrong — cycle 12 duplicated S3. Correct them to describe the actual rework before committing.

**Alternative — clean revert:** `git checkout -- docpluck/ pyproject.toml CHANGELOG.md docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md .claude/skills/docpluck-iterate/LEARNINGS.md .claude/skills/_project/lessons.md` and `rm tests/test_ligature_decomposition_real_pdf.py`, then redo ligature coverage as a fresh, correctly-scoped cycle once the S3-reach question above is answered. This is cleaner than fix-forward if the investigation shows the body path was fine all along.

**Do NOT** ship v2.4.44 until `test_report_tracks_changes` passes and the diff is a genuine, non-duplicate fix.

---

## JOB 2 — Finish the article-finder AI-gold integration

ArticleFinder's full instruction is at:
`C:\Users\filin\Dropbox\Vibe\ArticleRepository\docs\handoffs\2026-05-16_docpluck_ai-gold-instructions.md`
**Read it in full.** Summary of what docpluck still owes:

**Already done in session 3 (commit `ac34c7e`):** removed docpluck's private gold-extraction prompt from `references/ai-full-doc-verify.md` (Step 1b); rewrote Step 1 to delegate generation to `article-finder generate-gold`; updated `SKILL.md`, `CLAUDE.md`, `docpluck-qa/SKILL.md`; saved memory `feedback_gold_generation_via_article_finder`.

**Still open — audit `ac34c7e` against ArticleFinder's handoff and adjust:**

1. **Canonical DOI keys are now HARD-ENFORCED.** `ai-gold.py register-view` / `migrate` now *reject* a bare local stem (`chen_2021_jesp`) with an error. Confirm the docpluck-iterate skill (`ai-full-doc-verify.md` "Choosing $KEY" + Phase 5d) resolves the paper's DOI via `ai-gold.py resolve` and passes the DOI — not a stem. If the autonomous loop ever keys by a stem it will now fail loudly.
2. **`codex` CLI cross-model verification.** `gold-generation.md` now runs an independent Codex / GPT-5.5 model to audit every gold before storage; `generate-gold` blocks without it. `codex-cli 0.128.0` IS installed in this environment — **verify it is authenticated** (`codex --version` works; run `codex login` if calls fail). Note this dependency in the docpluck-iterate skill so a future run does not stall mystifyingly.
3. **Regenerate the stale `reading` golds.** docpluck's existing cached `reading` golds were produced by the old private prompt and diverge from `gold-generation.md`. Regenerate via `article-finder generate-gold <pdf>`. **Priority — the 3 fragmented papers first:**
   | Paper | old stem key | canonical DOI key |
   |---|---|---|
   | Chen 2021 JESP | `chen_2021_jesp` | `10.1016__j.jesp.2021.104154` |
   | Xiao 2021 CRSP | `xiao_2021_crsp` | `10.1080__23743603.2021.1878340` |
   | Efendic 2022 SPPS | `efendic_2022_affect` | `10.1177__19485506211056761` |
   Then regenerate the rest of docpluck's `reading` golds. After each, confirm with `ai-gold.py views <doi>`.
4. Run `python ~/.claude/skills/article-finder/ai-gold.py audit` — expect **0 issues**. Coordinate the removal of the old short-stem cache directories with article-finder (do not delete cache data unilaterally — article-finder owns the cache repo's commits).

**Important caveat for JOB 3:** cycles 8-12's Phase-5d verification consumed the *stale* `reading` golds (`tmp/*_gold.md`). The shipped fixes (v2.4.40-43) are still sound — they are keyed on structural signatures and gated by the 26-paper baseline — but once the golds are regenerated, **re-run the Phase-5d verifier for at least efendic / chen / xiao / jdm_m.2022.2 against the fresh golds** to confirm nothing was missed.

---

## JOB 3 — Continue the APA iteration loop

Work queue: `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md`, section **"SESSION-3 STANDING VERDICT"**. The APA corpus is **NOT clean — ~12 papers still FAIL** Phase-5d on pre-existing defects. Per rule 0e-bis the run continues. Ranked next pickups:

1. **G5b — long-descriptive-title prose guard** (S1, C1, cheap). `render.py::_promote_numbered_subsection_headings` and `_promote_numbered_section_headings` reject headings whose title has a run of ≥5 lowercase-initial words (`max_lc_run >= 5`). This over-rejects legitimate long numbered headings (`4. Knowledge acquisition, decision delay, and choice outcomes`; `2.4.2.2. Inference of planning strategies and strategy types`). For a *numbered* line that already passed the strict regex + (for section-level) the numbering-range/uniqueness/list-adjacency gates, the lc-run guard is near-redundant. Raise the threshold 5→8 in both promoters. ~25 headings, mostly `jdm_.2023.16`. This was the planned cycle 13.
2. **G5c — split-line numbered headings** (S1, C2). `5.3.`\n\n`Results` — the number alone on a line, the title on the next; renders as an orphan bare-number line, and the content gets a MISLABELED generic `## Results` instead of `### 5.3. Results`. The cycle-3 orphan-arabic-numeral folder's multi-level analogue.
3. **FIG caption double-emission + truncation** (S2, C2) — ~8 papers.
4. **G5d — named (unnumbered) heading demotion** (S1, C2-C3) — ~7 papers; section-partitioner work, largest false-positive surface.
5. **TABLE structure destruction** (S0/S1, C3) — ~11 papers, the single largest blocker; needs a render/structured-extraction coordination *design* — a dedicated session.
6. **COL column-interleave** (S0, C3) and **GLYPH 011 deleted-minus / efendic `Mchange` no-CI** (S0, C3-C4) — escalate; need the layout channel.

Also queued: a `tests:` regen cycle for the 15 pre-existing pytest failures (all snapshot drift — see `HANDOFF_2026-05-16_iterate_apa_run_3.md` §4). Triage each with a git-stash round-trip before regenerating.

**Iteration discipline (unchanged, non-negotiable):** one defect class per cycle; every fix keyed on a structural signature (never paper identity); 26/26 baseline is the no-regression gate; AI-gold Phase-5d verify every affected paper (gold OBTAINED from article-finder, never self-generated — JOB 2); add a real-PDF regression test in the same cycle; ship incrementally (tagged release per cycle); never report "clean" while corpus FAILs remain (rule 0e-bis).

---

## Run context — what session 3 shipped (cycles 8-11, all clean)

| Cycle | Version | Fix |
|---|---|---|
| 8 | v2.4.40 | standalone `2`-for-U+2212 minus recovery via point-estimate∈CI pairing (GLYPH, S0) |
| 9 | v2.4.41 | numbered subsection-heading regex loosened (trailing dot + internal colon); ~78 `###` headings recovered (G5, S1) |
| 10 | v2.4.42 | Elsevier page-1 footer (e-mail + ISSN lines) strip (D4, S2) |
| 11 | v2.4.43 | single-level numbered section-heading promotion (G5a, S1) |
| — | `ac34c7e` | process fix: gold generation delegated to article-finder (JOB 2 partial) |
| 12 | (v2.4.44 attempt) | ligature decomposition — **BROKEN, see JOB 1** |

Each of cycles 8-11: 26/26 baseline, 0 new pytest failures, AI-gold verifier OVERALL PASS, real-PDF test added, prod-deployed. Full detail: `docs/HANDOFF_2026-05-16_iterate_apa_run_3.md` and `.claude/skills/docpluck-iterate/LEARNINGS.md`.

`run-meta` (`~/.claude/skills/_shared/run-meta/docpluck-iterate.json`) was left mid-run (verdict blank, `postflight_heartbeat:false`). The fresh session's preflight will re-init it; the session-3 postflight was **not** run (this handoff replaces it). If you want the session-3 signal preserved, note that `bugs_fixed`/`tests_added`/`lessons_appended` arrays in that file already hold cycles 8-12's entries.

## Command cheat-sheet

```
# 26-paper baseline (the no-regression gate)
PYTHONUNBUFFERED=1 python -u scripts/verify_corpus.py 2>&1 | awk '{print; fflush()}'

# broad pytest (camelot off)
DOCPLUCK_DISABLE_CAMELOT=1 python -u -m pytest tests/ -q --tb=line

# render one paper
python -c "from docpluck.render import render_pdf_to_markdown; from pathlib import Path; print(render_pdf_to_markdown(Path('<pdf>').read_bytes()))"

# AI gold — OBTAIN from article-finder, never self-generate
python ~/.claude/skills/article-finder/ai-gold.py resolve "<doi>"
python ~/.claude/skills/article-finder/ai-gold.py check <doi-key> --view reading
python ~/.claude/skills/article-finder/ai-gold.py get   <doi-key> --view reading
#   on a miss: invoke the article-finder skill -> generate-gold <absolute-pdf-path>
python ~/.claude/skills/article-finder/ai-gold.py audit      # expect 0 issues

# prod health
curl -s https://extraction-service-production-d0e5.up.railway.app/_diag | python -m json.tool
```

APA test PDFs: `../PDFextractor/test-pdfs/apa/`. Library version files to bump together: `docpluck/__init__.py`, `pyproject.toml`, `docpluck/normalize.py::NORMALIZATION_VERSION` (only if normalize.py changed).
