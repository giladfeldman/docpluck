# Handoff — docpluck-iterate run 9 (continued, session 3) → fresh session

**Authored:** 2026-05-20, mid-run after cycle 6/7 shipped + cycle 8 staged but
not yet tagged/pushed (re-extract in progress).
**For:** a fresh `/docpluck-iterate` session that **continues run 9**.

This is a **mid-run handoff**. Cycle 8's library code is in the working tree
(uncommitted), all tests pass, broad pytest is clean, the harness re-extract
is running in the background but not yet finished. Standing verdict is
**PARTIAL** until cycles 8 (finish), 9, 10 + extraction timeouts + Group B
are resolved or each remaining item is explicitly escalated.

**Goal (unchanged):** address ALL issues — small/big, pre-existing or not —
in this run. Standing directive re-affirmed 2026-05-19 (top-of-file "Working
directive" in both CLAUDE.mds; binds all future runs; memory
`feedback_fix_every_bug_found`).

**Read first:** this doc, then `HANDOFF_2026-05-18_iterate_run_9_cont2.md`
(prior handoff), `scripts/harness/README.md`, `tmp/iterate-todo.md`,
`tmp/known-tier-deltas.md`, the LEARNINGS.md cycle-6/7/8 journals.

---

## State at handoff

- **docpluck library: v2.4.59 PREPARED but NOT YET TAGGED/PUSHED.** Code +
  tests + version bumps (`__init__.py`, `pyproject.toml::version`,
  `NORMALIZATION_VERSION` 1.9.12 → 1.9.13) + CHANGELOG + LEARNINGS +
  `_project/lessons.md` + `tmp/iterate-todo.md` + run-meta — ALL written and
  unstaged on `main`. `git status` shows the modified set (see "Pending
  commit" below).
- **docpluck library v2.4.58 IS SHIPPED.** Cycle 7 fully rolled out — main
  pushed (`0e6b849`), tagged `v2.4.58`, auto-bump bot landed on docpluckapp
  master as `fa35008`, Railway prod confirmed `docpluck_version=2.4.58`.
- **docpluckapp service_version 1.5.1** — current prod (cycle 5 + auto-bump
  to docpluck 2.4.58). Will auto-bump to 2.4.59 once cycle 8 is tagged.
- **Harness re-extract IN PROGRESS** (background task `byhol9iqq`, started
  ~13:00 local). At handoff time it was at 312/540 cells (≈58%). Expected to
  complete in ~30-40 more min. Workers=2 (low-contention; the cycle-7 first
  attempt with `--workers 4` after a long pytest run hit 6 environmental
  Camelot timeouts that all cleared on a fresh-service `--workers 2` re-run).
- **Local FastAPI service:** running at docpluck **2.4.59** (post-cycle-8
  restart) / service_version 1.5.1. Verify
  (`curl -s localhost:6117/health`) — `docpluck_version` must say `2.4.59`.

## Cycles shipped this session

| Cycle | Ver | Defect | Fix | Result |
|---|---|---|---|---|
| 6 | harness-only (commit `72d34e5`) | text_loss false-positives on reflowed table/stimulus regions (7 papers) + `_fingerprint` Greek/ASCII-name divergence | `scripts/harness/checks.py` reflow exemption (coverage ≥0.90 + run≥3) + Greek translit in `_fingerprint` | 7 false-positives cleared, plos-med-1 real loss retained; 0 regressions; 3 harness tests |
| 7 | v2.4.58 (commit `0e6b849`, tag pushed; docpluckapp `fa35008` auto-bumped; **prod LIVE**) | normalize_text non-idempotence (S7a whitespace strip; H0 banner position-gate) | S7a → strip all whitespace in match (handles newline-broken compounds); H0r late re-strip on stabilized line positions | chan_feldman idempotent in 1 pass; Tier-D 0 regressions; 4 new tests; corpus scan **85/180 → 36/180 after cycle 8** (49 cleared total); strided ratchet 10 → 6 |

## Cycle 8 — PENDING COMMIT (everything ready except Tier-D gate + tag)

**Pending commit** (8 files modified, 0 untracked from this cycle — the
`NEON_HANDOFF_2026-05-20.md` untracked file is the user's, unrelated):

```
 M .claude/skills/_project/lessons.md
 M .claude/skills/docpluck-iterate/LEARNINGS.md
 M CHANGELOG.md                       (v2.4.59 entry written)
 M docpluck/__init__.py               (__version__ = "2.4.59")
 M docpluck/normalize.py              (S7+S8 lookahead form, S8 Greek, LateJoin block)
 M pyproject.toml                     (version = "2.4.59")
 M tests/test_normalize_idempotent_real_pdf.py  (_IDEMPOTENCY_RATCHET = 6)
```

`scripts/harness/baseline_matrix.json` is **NOT yet updated** — wait for the
re-extract + Tier-D to confirm 0 regressions, then `checks --update-baseline`.

### Cycle 8's code changes (`docpluck/normalize.py`)
1. **S7 → lookahead form.** `re.sub(r"([a-z])-\n([a-z])", r"\1\2", t)` →
   `re.sub(r"([a-z])-\n(?=[a-z])", r"\1", t)`. Chained hyphenated breaks
   converge in one pass.
2. **S8 → lookahead form + Greek-aware.**
   `re.sub(r"([a-z,;])\n([a-z])", r"\1 \2", t)` →
   `re.sub(r"([a-z,;])\n(?=[a-zα-ω])", r"\1 ", t)`. Lookahead so chained
   single-line breaks all join in one pass; Greek class so `,\nσ²(ξ)` joins
   on pass 1 (fixes the S8-runs-before-A5 ordering gap — see LEARNINGS).
3. **NEW `LateJoin_line_break_rejoin` block** at end of pipeline (right
   before H0r). Re-applies S7, S8, and (academic) A1 stat-line-repair
   patterns on stabilized line positions — catches boundaries that S9 /
   R3 exposed by removing or rearranging lines after the original S7/S8/A1
   ran. A1r uses `[ \t]*\n[ \t]*` (horizontal whitespace only) so it never
   joins across a `\n\n` paragraph break — that's what
   `test_column_bleed_too_many_fragments_ignored` requires.

### Cycle 8 verification status
- Targeted unit tests (`tests/test_normalize_idempotent_real_pdf.py`):
  **4/4 pass**.
- Broad pytest (`pytest tests/`): **1345 pass + 1 known pre-existing B6
  fail (`test_request_09_reference_normalization`) + 21 skipped + 1
  xfailed**. (Cycle 8 fixed the `test_column_bleed_too_many_fragments_ignored`
  failure that the loose `\s*` would have introduced.)
- Idempotency scan corpus-wide (`verify_out/*/academic/raw.txt`):
  **85 → 36 non-idempotent (49 papers cleared, 58% reduction).**
- Strided-sample ratchet: 10 → 6.
- Tier-D: **PENDING** (re-extract in progress).

### Cycle 8 — DO FIRST (fresh session)
1. **Methodology smell-test** (Phase 0.8) before any code.
2. Verify the local service is at v2.4.59
   (`curl -s localhost:6117/health` → `docpluck_version=2.4.59`).
3. Check the re-extract status:
   `cat C:\Users\filin\AppData\Local\Temp\claude\C--Users-filin-Dropbox-Vibe-MetaScienceTools-docpluck\8cc90de7-ed27-48c9-8ed2-fd27a8a823f7\tasks\byhol9iqq.output`
   - If finished: proceed.
   - If still running: wait (no concurrent harness extract + pytest).
4. **Run Tier-D:** `python -m scripts.harness.checks --levels academic`.
   - Expected: 0 regressions (Tier-D ignores `normalized.txt` content; the
     cycle-8 changes affect the `normalized` view but the verdicts —
     text_loss, table_parity, glyph — should hold).
   - If 6 environmental timeouts re-appear (LEARNINGS card on contention):
     restart service + clear Camelot `%TEMP%` + re-extract those alone with
     `--workers 2`. They cleared cleanly in cycle 7's verification.
5. **If Tier-D clean:**
   - `python -m scripts.harness.checks --levels academic --update-baseline`.
   - `git add docpluck/__init__.py docpluck/normalize.py pyproject.toml CHANGELOG.md tests/test_normalize_idempotent_real_pdf.py scripts/harness/baseline_matrix.json .claude/skills/docpluck-iterate/LEARNINGS.md .claude/skills/_project/lessons.md`.
   - Commit with the prepared message (see "Cycle-8 commit message" below).
   - `git tag v2.4.59 && git push origin main && git push origin v2.4.59`.
   - Wait for docpluckapp auto-bump direct push (per LEARNINGS card
     `drop-ci-pr-step-whose-check-does-not-gate-the-change`, the workflow
     now commits directly to master, no PR; `gh run list --repo
     giladfeldman/docpluckapp --workflow bump-app-pin.yml --limit 1`
     and `gh api repos/giladfeldman/docpluckapp/commits` to confirm).
   - Poll Railway prod for docpluck_version=2.4.59 (≤8 min).
6. **Continue to cycle 9** (STRIP bucket — see "Open queue" below).

### Cycle-8 commit message (prepared)

```
normalize: cycle 8 — JOIN bucket idempotence (S7+S8 lookahead, Greek, LateJoin) [v2.4.59]

A 180-doc scan post-cycle-7 found 85 papers non-idempotent. Root causes in
the JOIN bucket (54 papers):

- S7 + S8 line-join re.subs consume BOTH boundary chars per match — a
  chained run of N joinable adjacencies (`a\nb\nc\nd`) halved per pass and
  needed log2(N)+1 passes to fully converge. Production single-pass output
  shipped paragraphs with half their pdftotext line-wraps still mid-sentence.

- S8 trailing class `[a-z]` did not match Greek-initial lines, so
  `,\nσ²(ξ)` escaped S8 on pass 1; A5 then transliterated `σ`→`sigma` and
  only pass 2's S8 caught it (S8-runs-before-A5 ordering gap).

- S9 strips repeated header/footer + page-number lines via `"\n".join` of
  a filtered list — when an intermediate line is dropped, the two
  surrounding lines become adjacent with a single `\n` between them,
  re-exposing line-break boundaries S7/S8/A1 already ran past
  (chen_2021_jesp `...predictions on the\nprobability of...`).

Three fixes:

- S7 + S8 → non-consuming lookahead form: `([a-z,;])\n(?=[a-zα-ω])` →
  `\1 ` for S8 (analogous for S7's hyphen-rejoin). Chained adjacencies
  fully converge in one pass.

- S8 Greek-aware: trailing class extended to lowercase Greek (U+03B1–
  U+03C9) so `,\nσ²(ξ)` joins on pass 1.

- LateJoin block before H0r: re-applies S7/S8 + academic A1 stat-line
  patterns on stabilized end-of-pipeline line positions. A1r uses
  `[ \t]*\n[ \t]*` (horizontal whitespace ONLY) so it never joins across
  a `\n\n` paragraph break — preserves the
  test_column_bleed_too_many_fragments_ignored contract (5+ column-bleed
  fragments stripped by S9 must NOT silently auto-join into a stat).

Idempotency scan: 85/180 → 36/180 non-idempotent (49 cleared, 58%
reduction). Strided-sample ratchet test 10 → 6. Broad pytest 1345 pass
(only known pre-existing B6 fail). NORMALIZATION_VERSION 1.9.13.

Remaining residuals: STRIP bucket — S9 4-digit page-num cluster detection
fires only on pass 2 (cycle 9; same H0r-pattern fix needed) — and CHARSUB
bucket — destructive `recover_minus_via_ci_pairing` (cycle 10).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## Open queue — address ALL of it (run continues until empty or escalated)

### Cycle 9 — STRIP bucket (~28 of the 36 residuals)
Position/cluster-gated strips fire only on pass 2. Apply the H0r pattern
(re-strip on stabilized line positions / fixed-point) to:
- **P0 "Author affiliations and article information are listed at the end of this article"** (12 JAMA papers — `jama_open_1`/`_2`/...`_12`). Pattern is in `normalize.py:~726`.
- **S9 4-digit page-number cluster** (chandrashekar `7182`, aiyer `1118`/`1265`, etc.). Pass-1 doesn't detect the cluster (insufficient signal); pass-2 cleaner input lets it fire. Same H0r-pattern fix needed.
- Other residuals — diagnose via `python -u -c "...normalize×2 diff per doc..."` (template in `tmp/iterate-todo.md`).
- **Defense:** the LateJoin block I added uses `[ \t]*\n[ \t]*` not `\s*\n\s*` — DO NOT loosen it; that would re-break `test_column_bleed_too_many_fragments_ignored`.
- Library cycle, version bump + tag + harness re-extract.

### Cycle 10 — CHARSUB bucket (5-7 residuals)
Destructive char-substitution on re-application.
- **ip_feldman** (`-2.68` → `--.68`): `recover_minus_via_ci_pairing`'s
  `_CORRUPT_NEG_TOKEN_RE = re.compile(r"(?<![\d.])2(\d?\.\d+)\b")` lookbehind
  allows `-` before the `2`. Fix: tighten to `(?<![\d.\-])`. ONE-CHAR fix.
  Sites: `normalize.py:~1436`.
- 4-6 other CHARSUB residuals (ieee-access-7, ziano, van-boven, chan-feldman-rsos, chandrashekar-pronin-kugler) — diagnose each destructive step + guard.
- Library cycle.

### Cycle 11+ — corpus ratchet → 0 final pass
After cycles 9/10, run the idempotency scan corpus-wide. If any residuals,
diagnose + fix. Ratchet `_IDEMPOTENCY_RATCHET` in `tests/test_normalize_idempotent_real_pdf.py` → 0.

### Extraction timeouts (task #3)
- **Persistent:** `nat_comms_3` + `xiao-poc-epley` — Camelot table extraction >900s. Cycle-7 re-extract surfaced 6 transient timeouts (yeung-feldman, nat-comms-5, nathumbeh-2, sci-rep-1/2/4) that ALL cleared on a fresh-service `--workers 2` re-extract w/ cleared `%TEMP%` (33438 stale files removed).
- **Fix path:** restart service fresh, clear Camelot `%TEMP%`, re-extract each alone. If still timing out → profile Camelot → per-doc time-cap or page-limit (**architecture decision — surface to the user**).

### GROUP B — Tier-A / structural defects (firm cycles — user directive: do NOT defer)
Unchanged from prior handoff. See `HANDOFF_2026-05-18_iterate_run_9_cont2.md`
"GROUP B" for B1–B7. Re-confirm each at HEAD before coding.
- **B1** TABLE-builder cluster (plos_med_1 Tables 2/3/4/5 + ~13-paper corpus; Table 5 = 13 SAE rows lost — confirmed cycle 6).
- **B2** HALLUC-HEAD-2 / section-annotator over-promotion + G5d.
- **B3** D4 metadata leak + table double-emission.
- **B4** caption residuals (TBL-CAP + FIG-3c-2).
- **B5** G5c-2 partitioner split-heading rejoin.
- **B6** COL column-interleave (escalation-class; `test_request_09` still RED).
- **B7** GLYPH deleted-minus residuals (escalation-class).

## Methodology / gotchas (carry forward)

- **`re.sub` boundary-consume.** This handoff's biggest lesson: a `re.sub(r"X\nY",r"\1 \2",t)` pattern consumes both X and Y per match, so a chained run of adjacent matches half-converges per pass — needs lookahead form `r"X\n(?=Y)"` `r"\1 "`. Encoded in cycle-8 LEARNINGS and `_project/lessons.md`.
- **S9 line-removal re-exposes line-break boundaries.** Any step that does `"\n".join(filtered_lines)` can put two previously-non-adjacent lines next to each other with a single `\n`. If neighbours are joinable prose, that's a new boundary the earlier S7/S8/A1 ran past. Pattern: late-pipeline re-application on stabilized positions (H0r generalized to LateJoin).
- **NEVER run harness extract + broad pytest concurrently.** CPU contention causes false `pdftotext` timeouts. Cycle 7 hit this; cycle 8 sequenced them and was clean.
- **Service restart kills 1 parent + 4 worker python processes.** `Get-NetTCPConnection -LocalPort 6117 -State Listen → OwningProcess → ParentProcessId + 4 kids → Stop-Process -Force -ErrorAction SilentlyContinue`.
- **Camelot `%TEMP%` accumulates.** 33438 stale `tmp*` items after one long run. Clear before re-extract on persistent-timeout investigation:
  `Get-ChildItem $env:TEMP -Filter 'tmp*' | Where-Object {$_.LastWriteTime -lt (Get-Date).AddMinutes(-30)} | Remove-Item -Recurse -Force`.
- **Harness `extract` skips on `source_sha1`, not docpluck version** — `--force` is mandatory after any code change.
- **`shutil.which("pdftotext")` returns `C:\Users\filin\bin\pdftotext.EXE`** — pdftotext is on PATH. The conftest skip pattern works; an inner `pytest.skip("PDF not available")` is the more common skip cause.

## Process improvements proposed (awaiting user approval)

- **Carry-forward from cycle 5 (still open):** run the docpluckapp service test suite (`cd PDFextractor/service && python -m pytest tests/`) whenever a cycle touches app/service code, and periodically regardless. Cycle 5 was the first to surface 6 dormant issues (5 drift + 1 real bug) in that suite. **Cycle 7's idempotency test `test_normalization_idempotent` in `PDFextractor/service/tests/test_benchmark.py` is now GREEN** (chan_feldman is idempotent post-cycle-7 fix). Cycle 8 didn't re-run the service suite — the next time something touches app code or every ~5 cycles, do it.

## Stop reason (this session)

Context budget. Cycles 6 + 7 fully shipped end-to-end this session; cycle 8
prepared end-to-end except for the Tier-D regression gate (harness re-extract
running in background at 58% when this handoff was written) and the final
commit + tag + push + Railway deploy. The Open queue (cycle 9 STRIP, cycle 10
CHARSUB, extraction timeouts, Group B B1–B7) is large but well-mapped. Per
the user directive ("leave nothing behind"), this run's standing verdict is
**PARTIAL** — the run continues until every queue item is resolved or
explicitly escalated.
