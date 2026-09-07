# Docpluck — Library Repo (giladfeldman/docpluck, public)

## Working directive — LEAVE NOTHING BEHIND (read first; binds every task, skill, and run)

**Fix every issue you find, in the same run that finds it.** Any issue — small
or large, pre-existing or newly introduced, in code, docs, tests, or config,
"out of scope" or unrelated to the task at hand — is fixed now, not merely
reported and left behind. "Pre-existing", "known", "not introduced by this
change", and "out of scope" are NEVER grounds to leave a defect in place;
noticing a defect and walking past it is itself a defect.

Two — and only two — exceptions: **(a)** the fix needs a product or architecture
decision only the user can make → surface it immediately and explicitly, never
bury it; **(b)** the fix is genuinely too entangled to land in the current
change → queue it as an *immediate next step in the same run*, never as "later",
never as a handoff-doc footnote. Never end a task, cycle, or run with a known
issue unaddressed; never report work as "clean" / "done" / "shippable" / "PASS"
while a known issue is open.

**"Leave nothing behind" covers BUILT-BUT-NOT-WIRED, not just unfixed bugs.**
Work is not done when the code exists, the tests pass and the doc is written. It
is done when it **reaches the consumer through the path production actually
uses**. A capability that is implemented, validated, measured and then invoked by
nothing is indistinguishable from one that was never built — except that it
carries the *appearance* of being handled, which is worse, because every
subsequent reader believes the problem is solved. The same applies to a decision
that was taken and not implemented, a finding that was measured and not acted on,
and a report field that is populated but never serialized.

Before calling anything done, verify all four:

1. **A non-test call site exists** for every symbol added. `grep` for it. A module
   imported only by its own test is not shipped.
2. **Every production path is wired**, not just the one you were looking at. This
   project requires all three text channels (`normalize_text`, table-cell
   cleaning, the render post-process); a repair in two of three means a table
   cell and a body sentence give different answers for the same input.
3. **The caller passes what the capability needs.** A layout-gated repair reached
   through a call site that passes no layout is dead code with a passing test —
   measured 2026-08-13: `batch.py` called `normalize_text(raw_text, level)` with no
   layout, so the corpus pipeline received none of the layout-proven glyph repairs
   while the sections path received all of them. **FIXED in v2.4.128; re-verified
   2026-08-15 — both real call sites now pass `dropped_minus_layout=`, and the only
   remaining matches are a code comment and a docstring.** The example is kept
   because the SHAPE recurs, but note what happened to it: **this very sentence was
   read as current on 2026-08-15 and used to assert a "blocker" in a handoff that
   did not exist.** A stale claim in a rules file is exactly as dangerous as one in
   a handoff — when you cite a measurement, re-run it or date-stamp it as historical.
4. **Every value computed is read back** — serialized, returned, and consumed.

Evidence this needed saying (all 2026-08-13, all in one run): a validated
superscript-detection signal recorded as "signal validated, not yet wired"; a
`normalized_text` field on the DOCX/HTML section path that is not normalized; and
a `A6_footnote_removal` step whose own comment documents a worked example it
cannot perform, because an earlier step consumed its input. Each had a green test.
**A green test on an unreachable path is not evidence of anything.**

This is the project's first rule. It binds every `docpluck-*` skill
(`-iterate`, `-qa`, `-review`, `-cleanup`, `-deploy`) and overrides any skill
step that would permit a defect to be merely reported-and-left. It applies to
**every future run**, not just the run in which it was last stated. Established
by user directive 2026-05-14; re-affirmed 2026-05-15, 2026-05-17, and 2026-05-19
("address all the issues that come up, leave nothing behind, small/big,
doesn't matter pre-existing or not"). Full statement under "Critical hard
rules" below; durable cross-session record in memory `feedback_fix_every_bug_found`.

## Two-Repo Architecture

Docpluck is split across **two repos** under `Vibe/MetaScienceTools/`:

| Path | Repo | Visibility | Contains |
|------|------|------------|----------|
| `docpluck/` (this repo) | `github.com/giladfeldman/docpluck` | **public** | The `docpluck` Python library only. Published to PyPI as `docpluck`. |
| `PDFextractor/` | `github.com/giladfeldman/docpluckapp` | **private** | The SaaS app (Next.js + FastAPI). **No library code lives here** — the service imports `docpluck` via a git pin in `service/requirements.txt`. |

### Why split

- Library can be open-sourced under MIT and consumed by anyone via PyPI without exposing app secrets/auth/billing logic.
- App can iterate freely without forcing library releases.
- No code duplication: there is exactly one copy of `extract.py` / `normalize.py` / `quality.py` etc., and it lives here.

### How the app consumes this library

`PDFextractor/service/requirements.txt` pins:
```
docpluck[all] @ git+https://github.com/giladfeldman/docpluck.git@v<VERSION>
```

When this library releases a new version, the app's `requirements.txt` git pin must be bumped or production silently keeps running the old library. The `/docpluck-deploy` skill's pre-flight check 4 enforces this.

### Library ↔ app version sync (HARD RULE — when we bump the package, we bump the app; verify, don't assume)

**Invariant: the app's docpluck pin and the library version are ALWAYS in sync.** The `@v<VERSION>` pin in `PDFextractor/service/requirements.txt` on **docpluckapp `origin/master`** (what Railway deploys) MUST equal the library's latest released `v*` tag. A lagging pin = production silently runs the old library. Bumping the package therefore *is* bumping the app — the two are never released independently.

- **Mechanism (LOCAL, explicit, ordered):** `python scripts/check_app_pin_sync.py --fix --push` bumps the pin in `PDFextractor/service/requirements.txt`, commits it, and pushes to docpluckapp `master`, which triggers the Railway redeploy. It **refuses to move the pin backwards**.
  > **There is NO GitHub Actions workflow any more.** `bump-app-pin.yml` was DELETED on 2026-08-20 — this portfolio does not pay for GitHub Actions and never will, and the workflow had just proved why a race-y remote trigger is the wrong shape: a history purge force-pushed tags v2.4.134 and v2.4.135 together, both runs fired, the OLDER one finished ONE SECOND later (14:56:57 vs 14:56:56) and won, and production was silently downgraded. Nothing failed. A local script runs in a known order, on demand, with the result visible immediately.
- **Verification (mandatory, deterministic):** run `python scripts/check_app_pin_sync.py` — it reads the pin from docpluckapp `origin/master` (production-authoritative, NOT your local clone) and compares it to the latest library tag. Exit 0 = synced. This gate is wired into `/docpluck-qa`, `/docpluck-review`, and `/docpluck-deploy` (pre-flight check 4); every release MUST pass it.
- **A stale LOCAL clone lies.** A local `PDFextractor` checkout that hasn't fetched shows an *old* pin even when production is correctly synced — and almost causes a phantom "fix". ALWAYS verify against `origin/master` (the script does this for you); never judge sync from a local working-tree file.
- **Recovery when it drifted:** re-push the tag (`git push origin v<VERSION>` re-fires the workflow), or hand-bump `service/requirements.txt` to `@v<VERSION>` and push to docpluckapp `master` (triggers Railway redeploy). Then re-run the gate and confirm Railway `/health` reports `docpluck_version == <VERSION>`.

## Release flow (library → production)

1. Make + commit changes in this repo. Bump `__version__` (in `docpluck/__init__.py`), `version` (in `pyproject.toml`), and `NORMALIZATION_VERSION` (in `docpluck/normalize.py`) consistently.
2. Update `CHANGELOG.md`.
3. Push to `main`, then tag: `git tag v<VERSION> && git push --tags`.
4. (Optional) Publish to PyPI: `python -m build && twine upload dist/*`.
5. **Bump the app pin yourself** — nothing does it for you:
   ```bash
   python scripts/check_app_pin_sync.py --fix --push
   ```
   Then **verify**: `python scripts/check_app_pin_sync.py` (exit 0 = synced against `origin/master`). Also update any frozen version examples in `PDFextractor/API.md`.
6. Run `/docpluck-deploy` from the docpluck repo — pre-flight check 4 runs the same sync gate and the post-deploy step confirms Railway `/health` reports the new version.

The most common failure mode is assuming the auto-bump landed when it silently missed — step 5's `check_app_pin_sync.py` gate catches it. The deploy skill, qa, and review all run it.

## Spike work queue (table-rendering iteration)

> **The canonical work queue for the splice-spike is the most recent `docs/TRIAGE_<date>_corpus_assessment.md`.** Always read it first and pick the next iteration from its top-3 candidates. The handoff doc (`docs/HANDOFF_<date>_table_rendering_iteration_<N>.md`) is one input but goes stale across sessions; the triage is the *living* priority list, recomputed each broad-read of the corpus.

**Iteration discipline (set 2026-05-10 after a long run of patches missed bigger structural issues):**

1. Start each session by reading the active `TRIAGE_*.md`'s top-3 candidates.
2. Every 3-5 iterations OR when a new pattern emerges, run a fresh broad-read across 8-10 random `.md` outputs *as a reader, not a diff* — sample the document START (first 30 lines) where most user-visible issues live. Update `TRIAGE.md` in place: strike resolved items, add new ones, re-rank by severity × cost.
3. Verification (post-fix) catches regressions; audit (periodic broad-read) catches new structural issues. **Char-ratio + word-delta metrics are blind to "right words in wrong order under wrong heading"** — they will pass a broken-section paper. The reader-pass is required.
4. If 3-4 iters in a row produce only small char-ratio shifts on isolated papers, surface "diminishing returns; should we shift focus?" to the user proactively.

## Critical hard rules (from project history)

> **READ [`LESSONS.md`](./LESSONS.md) BEFORE TOUCHING `extract*.py`, `normalize.py`, or `sections/`.**
> It is the durable incident log for the recurring mistakes below.  When in doubt about a change, the answer is almost always already there.

- **NEVER call the Anthropic API. ALL Claude model calls go through Claude Max via Claude Code.** Allowed: `Agent` tool in-session (with `model="sonnet"` for the audit subagent); headless `claude -p --model sonnet` from `.git/hooks/*` and `tools/canary_audit.sh`; `mcp__scheduled-tasks__create_scheduled_task` invoking Claude Code. Forbidden: `import anthropic`, `ANTHROPIC_API_KEY` anywhere in this repo or any related repo (`docpluckapp`, `escicheck`, `2Rmarkdown`, `CitationGuard`). The canary-audit architecture (Sonnet-watches-Opus) is designed around this constraint: external enforcement is local git hooks + scheduled tasks invoking headless Claude Code. **GitHub Actions is not available to this portfolio at all** — see the NO GITHUB ACTIONS rule below. Source: user directive 2026-05-25 (memory `feedback_no_apis_only_claude_max`), re-affirming previous statements across multiple sessions. Failure to follow this rule is the same severity as failing "LEAVE NOTHING BEHIND."
- **LEAVE NOTHING BEHIND.** If you see an issue — any issue, however small, whether pre-existing, already-known, "out of scope", or unrelated to the task at hand — you fix it in the same run. "Pre-existing", "known", "not introduced by this change", and "out of scope" are NEVER grounds to leave a defect in place; noticing a defect and walking past it is itself a defect. Two — and only two — exceptions: **(a)** the fix needs a product or architecture decision only the user can make — surface it explicitly and immediately, never bury it; **(b)** the fix is genuinely too entangled to land in the current change — then it is queued as an *immediate next cycle in the same run*, never as "later", never as a handoff-doc footnote. Never end a task, cycle, or run with a known issue unaddressed. Established by user directive 2026-05-14, re-affirmed 2026-05-15, 2026-05-17, and **2026-05-19** ("doesn't matter pre-existing or not; this directive holds for all future runs, every skill"). This generalizes and strengthens the rule-0e family (memory `feedback_fix_every_bug_found`). See the prominent top-of-file statement under "Working directive — LEAVE NOTHING BEHIND".
- **NO GITHUB ACTIONS. EVER. Not a workflow, not a badge, not a reference.** (User directive 2026-08-20: *"remove any references to github actions or anything using it. I will never be paying to github to activate actions."*) All five workflows were deleted that day — the library's `bump-app-pin.yml`, `test.yml` and `publish.yml`, and the app's `verify-railway-deploy.yml` and `post-deploy-verify.yml` — along with both `.github/` directories. **Do not add one back, and do not write a doc, comment or skill step that assumes one exists.**

  **This is a cost decision AND a correctness one.** The app repo is private, so its Actions minutes are billable, and they were already blocked (*"recent account payments have failed or your spending limit needs to be increased"*) — meaning `verify-railway-deploy.yml`, the gate asserting production matched the pin, **had silently not run at all**, which is precisely the false-green this file exists to forbid. And on the same day `bump-app-pin.yml` demonstrated the structural flaw of a remote trigger you do not order: a history purge force-pushed v2.4.134 and v2.4.135 together, both runs fired, the **older** tag finished one second later and won, and production was silently downgraded.

  **What replaces each one — all local, all already wired:**

  | deleted workflow | replacement |
  |---|---|
  | `bump-app-pin.yml` | `python scripts/check_app_pin_sync.py --fix --push` (refuses to bump backwards); the plain form is still the gate in `/docpluck-qa`, `/docpluck-review`, `/docpluck-deploy` |
  | `test.yml` | `pytest` locally + the pre-push canary hook + `/docpluck-qa` |
  | `publish.yml` | `python -m build && twine upload dist/*`, run deliberately |
  | `verify-railway-deploy.yml` | `bash ~/.claude/skills/_shared/bin/deploy-drift-check.sh` — already `/ship` Phase 0.5, and it is what caught the 2026-08-20 downgrade |
  | `post-deploy-verify.yml` | the `/post-deploy-verify` skill |

  **A local script beats a remote workflow here for the reason the incident showed:** it runs in a known order, on demand, in front of someone, with the result visible immediately — rather than in a race between two runners whose finish order nobody controls, reporting to a tab nobody opens. This is the same principle as the portfolio's "external enforcement is local git hooks + scheduled tasks, NOT GitHub Actions" rule for Claude calls; it now covers CI entirely.

- **KEEP THE APP PIN IN SYNC WITH THE LIBRARY — when we bump the package, we bump the app.** The `@v<VERSION>` docpluck pin in `PDFextractor/service/requirements.txt` (on docpluckapp `origin/master`, the production-authoritative source) MUST always equal the library's latest released `v*` tag; a lagging pin silently runs the old library in production. **Nothing auto-bumps it** — you run `python scripts/check_app_pin_sync.py --fix --push` after tagging, then verify with `python scripts/check_app_pin_sync.py` (exit 0 = synced). The `--fix` path refuses to move the pin backwards. A stale LOCAL clone shows an old pin even when prod is synced, so the gate reads `origin/master`, never a local file. Wired into `/docpluck-qa`, `/docpluck-review`, `/docpluck-deploy`. Full mechanism + recovery under "Two-Repo Architecture → Library ↔ app version sync". Established by user directive 2026-06-20.
- **NO PAPER, PUBLICATION TEXT, GOLD, OR BASELINE LIVES IN THIS REPO — article-finder is the sole custodian.** Never commit or keep here: a PDF, the extracted/rendered text of a publication (in ANY format), a gold/ground-truth file, or a snapshot/golden/baseline directory holding article content — **not even gitignored**. Locate and register everything through `~/.claude/skills/article-finder/` (`find-pdf.py`, `ingest-local-pdf.py`, `ai-gold.py register-view`). Tool output (render/extract baselines) registers with `--artifact-class tool` under `<family>__<producer>@<version>`; an unversioned baseline is overwritten by the next release, which turns any gate comparing against it into a tautology. Consumers get their expected paper set from `ai-gold.py papers-with-view`, **never from a directory glob** — a gate that computes its denominator from its numerator prints `N / N` and passes on a corpus that has silently shrunk. Check with `python ~/.claude/skills/article-finder/publication-text-scan.py . --history` (exit 1 = release-stopper). Established by user directive 2026-08-07 after `tests/snapshots/*.txt` — 984 KB of published article body, one file carrying SAGE's own reuse notice — was found tracked on the PUBLIC remote for three months, past three cleanup passes and an allowlist-based exposure gate that listed `tests/**` as allowed. See [LESSONS.md L-013](./LESSONS.md) and memory `feedback_articlefinder_is_sole_custodian_of_papers`. **A force-push does not end a purge:** `refs/pull/*` still serves everything; verify with `git clone --mirror` and an unauthenticated `curl` at the PR SHA.
- **DOCPLUCK EXTRACTS AND NORMALIZES. IT DOES NOT FIX THE PAPER.** (User directive 2026-08-13.) docpluck's job is to be **the best text extractor for what is actually printed in science papers**. Normalization means *canonicalising notation* — a Greek letter to `chi`, a Unicode minus to ASCII, a superscript to caret. It does **not** mean correcting the authors' or the journal's mistakes. **Fixing is not normalizing.** Where a paper prints `t = 0,76` among period decimals, or `M = 26,21, SD = 28.88`, or `p < 05`, or a reversed CI `[5.37, 4.66]` — docpluck passes it through **verbatim**. It does not silently repair it, because *docpluck has no channel through which to relay that a repair happened*, and a silent repair **launders a real defect on its way into a meta-science pipeline**: the downstream tool then validates a number the paper never printed, and the author never learns their paper has an error. Flagging and alerting users is **ESCImate's and Scimeto's role** — they have the UI and the mandate for it. docpluck's obligation is to (a) pass the defect through untouched and (b) tell those consumers, in a handoff, which classes to expect. THE ONE EXCEPTION: a defect **docpluck's own pipeline introduced** (a fused exponent `×10⁹/L` -> `x109/L`, a dropped decimal the PDF text layer lost, a Greek table disagreeing with itself) is docpluck's to fix, because docpluck caused it and the source is intact underneath. The test is *"did we break this, or did the paper?"* — and where you cannot tell from the text, **rasterize the page and look**. Nobody recorded when "normalization" started meaning "repair"; realigning is now a standing obligation, and it applies to every consumer contract.
- **CASE STUDIES COME FROM REAL PAPERS, WITH THE DOI RECORDED. NEVER HYPOTHETICALS.** (User directive 2026-08-13.) Every rule, guard, decision and regression test must be justified by a shape **observed in a real document**, cited by DOI and page. A constructed string proves what the *code* does, never that the *shape occurs*. Hypotheticals are an endless, unmanageable slippery slope: you can invent a copyediting error forever and never finish. Evidence this needed saying: rule **A3d** was built on `p = ,025`, an example inherited from ESCImate's spec and "reproduced against unfixed code" — i.e. a constructed string run through the pipeline. A 600-paper corpus hunt then found **0 occurrences in 0 papers**. A rule with no observed input is pure false-positive surface for no benefit. Before adding or keeping any rule, ask: *which real paper, which page?* If the answer is "a reviewer's example", it is not evidence. **AND NEVER ACCEPT A HYPOTHETICAL CASE AS-IS FROM A HANDOFF.** (User directive 2026-08-13.) A handoff, a reply document, a consumer's spec, a prior findings doc — none of them confer evidence. An example arrives with a DOI and a page, or you go find one before you act on it; if you cannot find one, say so in writing and treat the rule as unjustified. A3d reached shipped code precisely by being copied forward: ESCImate's spec -> our reply doc -> our handoff -> our CHANGELOG -> `NORMALIZATION.md` -> a rule, acquiring the appearance of consensus at every hop while remaining one unchecked string. **Repetition is not verification.**
- **ENGLISH + US NUMERIC CONVENTION IS THE SCOPE. WE DO NOT CONVERT EUROPEAN NUMBERS — THEY PASS THROUGH AS PRINTED.** (User directive 2026-08-14. **Settled; never re-open as a new issue.**) docpluck serves **English-language science articles written in US numeric convention** (`.` decimal, `,` thousands). We **do not know how to handle EU numbers or conversions**, and we no longer pretend to: every EU→US conversion rule is DELETED (`A3` operator-gated decimal comma, `A3c` leading-zero decimal, `A3d` leading comma), as is the entire document-level numeric-locale inference (`infer_numeric_locale`, `NumericLocale`, `NormalizationReport.numeric_locale`, `is_gating`). Measured, not assumed: over **297 English papers** the conversion rules fired **10 times in 3 papers and NOT ONCE correctly** — 8 corrupted mathematical constraints (`10.1515/bpasts-2016-0057`), 1 laundered an author's error (`10.1371/journal.pone.0285114`), 1 broke a URL (`10.1177/0146167210380928` p13). The locale detector was **confidently wrong** on the only genuine European table ever found in an English paper (`10.1177/0956797620935584` Table S2: ~130 comma-decimal cells → `european_markers=0`, verdict `decisive_us`), because every marker was operator-gated and a table cell has no operator — so "396 English articles → 0 European" described the INSTRUMENT, not the corpus. **A European decimal now reaches the consumer verbatim, and that is correct**: the source token stays intact, so the consumer can still decide; once converted, it could not. The marker vocabulary is retained INTERNALLY and unwired (`tests/test_numeric_locale_markers.py`) solely as the foundation for a future LINE- or TABLE-scoped guard — **never for another document-level verdict**. This must be stated on the website, in every consumer report, and in `docs/SCOPE.md`. ~~**STILL LOSSY, and not hidden:** `A3a` strips thousands separators and therefore turns a printed `df- satterthwaite` of `185,178` into `185178` — pinned known-wrong, remedy is the local-window locale.~~ **CORRECTED 2026-08-15 — that sentence was STALE and is struck rather than deleted, because it is an instance of the failure this file warns about two rules below.** `A3a` was deleted in v2.4.130; re-measured 2026-08-15, no `.replace(",", "")` survives anywhere in `docpluck/` and the pin test's assertions inverted to pass-through, so `185,178` is now delivered verbatim and the 1000× class is CLOSED. The claim was written while it was true, outlived its subject by one release, and was then read as current by an independent review. **This is the second time in two days that a stale measurement in THIS file was cited as a live fact** (the first manufactured a non-existent `batch.py` plumbing blocker, see the four-checks rule at the top). Date-stamp or re-run every measurement you cite here.
- **A REWRITE MUST EARN ITS EVIDENTIARY COST — ask what NEED it serves before asking whether it works.** (User directive 2026-08-14.) `1,000` is not a problem; it is clearly one thousand. "Fixing" it to `1000` repairs nothing and **removes information** — including the very evidence a consumer would need to notice a European table. So NOTATION-vs-REPAIR is not enough; the second axis is **evidentiary loss**: *does this rewrite erase interpretation-relevant evidence?* `χ²`→`chi2` is non-invertible yet preserves the statistical referent; `1,000`→`1000` erases a locale-bearing mark. **The 30-second test every rewrite must pass: could a competent downstream consumer make a BETTER decision if it saw the original token? If yes, do not rewrite by default.** Convenience for a downstream parser is not a reason — `.replace(",", "")` is one line in the consumer and irreversible in us.
- **ENGLISH-LANGUAGE ARTICLES ONLY — and NEVER learn about an English-article problem from a non-English article.** docpluck's scope is **English-language science articles**. Non-English articles are out of scope: a caption label that only matches `Table`/`Figure` is correct-by-scope, not a defect. **The hard half of this rule is the second clause.** The EU-vs-US numeric-separator question is already hard enough within English; evidence gathered from Portuguese, Spanish, Turkish or German articles does not transfer and will actively mislead, because the failure modes differ in kind. Concretely, and this nearly shipped a wrong conclusion on 2026-08-13: a corpus-widening pass asked for "European-locale papers" found them where comma decimals actually live — SciELO and Turkish journals — and those articles are **bilingual**, carrying an English abstract over a native-language body. So `1,738 adult patients` (English abstract, a genuine thousands group) sits in the same document as `528,329` (Portuguese body, the decimal 528.329), and *any* document-level locale conclusion drawn from them describes a document shape docpluck does not serve. Corpus acquisition must state the language filter up front; any scan that reasons about separators must report the language distribution and print what it excluded, never drop it silently (the detector is `tools/diag/_language.py`; `non_statistic_corpus_scan.py`, `repair_site_scan.py` and `render_deletion_scan.py` are the pattern). This scope is part of the published contract and must be stated to consumers (ESCImate, Scimeto/CitationGuard, MetaESCI) — see `docs/SCOPE.md`. Established by user directive 2026-08-13.
- **A BEHAVIOUR CHANGE IS NOT FINISHED UNTIL THE CONSUMERS HAVE BEEN TOLD — the notification is the second half of the change, not documentation.** (User directive 2026-08-14, re-affirmed 2026-08-15.) docpluck feeds ESCImate/effectcheck, Scimeto/CitationGuard, citelink, MetaESCI, ScienceArena and the PDFextractor app. **Retiring a repair MOVES WORK ONTO THEM, and it can cost them coverage SILENTLY rather than loudly** — measured: ESCImate's `pat_CI3` does not match `[-0.60, -0,26]` at all, so the interval VANISHES from their record instead of misparsing, a loss their users cannot see. The standing order was *"consumers build the flag first, we retire second, never the reverse"* (the internal notation-vs-repair inventory §7). The owner OVERRODE it on 2026-08-14 — *"i run all costumers, and i approved this change. we're doing the right thing to do, we'll notify them and tell them to fix things after we're done"* — which converts the gate into a **DEBT**, not a dismissal. **Never treat a release as complete while that debt is unpaid, and never re-derive the override as a general licence: only the owner of the downstream systems may make that call, never a plan author.** The notification must state, per consumer: the exact before→after token table so they can grep their own output; what they must now detect THEMSELVES (flagging the paper's own errors is their role — they hold the parsed statistic and its context, we hold text); a **retrospective** action where a shipped defect already produced wrong published numbers (the `A3a` class produced a rank-biserial of 0.99938 where the truth was 0.38275); and any consumer running an EDITABLE INSTALL of this tree (MetaESCI) must be told to pin a version, because for them "uncommitted" was never containment. Template: an internal consumer notice. Standing final step in `/docpluck-deploy` and in every handoff.
- **WHAT KIND OF EVIDENCE DOES THE RULE USE? — TYPOGRAPHIC is allowed, INFERENTIAL is not.** (User directive 2026-08-15.) The 2026-08-14 inventory classified all 111 transformations as NOTATION vs REPAIR and **missed an entire axis**, which the user found by asking one question about one rule. Every rule must declare which kind of evidence it decides on: **TYPOGRAPHIC** — what the renderer actually put on the page (a surviving `(cid:N)` glyph, the font name of *this* character, font size + baseline, a codepoint table, a literal backslash glued to a numeral, a token in a slot where its class is grammatically impossible) — or **INFERENTIAL** — what the numbers *ought to be* (this value must be negative because otherwise it falls outside its confidence interval; this interval must be corrupted because it runs backwards). **Inferential evidence is the consumer's job**: ESCImate and Scimeto hold the parsed statistic and its context and have a UI to flag it; docpluck holds text and has no channel to announce that it guessed. Measured 2026-08-15: `W0b`/`W0d`/`W0g` decide inferentially and fire **0 times in 226 papers** ***(RE-MEASURED 2026-09-07 and the "0 times" does not hold as a general claim — `W0b` and `W0d` DO fire. Over the 101-paper local test corpus, pass 1, `NormalizationLevel.academic`, reading `NormalizationReport.steps_changed`: `W0g` 0 papers, **`W0b` 1 paper, `W0d` 1 paper** (`efendic_2022_affect`). AND WHERE THEY FIRE THEY ARE CORRECT — neutralising both and diffing recovers **62 minus signs**, turning `r = 2.74 [20.92, 20.30]` into `r = -.74 [-0.92, -0.30]`: an impossible correlation and a descending interval, repaired properly. The 226-paper figure carries no command, so it cannot be re-run and this is not a refutation of it — it is a different corpus measured a different way, which is exactly why this file elsewhere says to quote a number only with the command that regenerates it. **The operational point: do NOT retire `W0b`/`W0d` alongside `W0g` on the strength of the "0 times" line — doing so would lose real recoveries.** `W0g` remains condemned on its own evidence: it turns `p = .05` into `p = -.05`, an impossible value, and directive `0c90a18` names CI containment as forbidden.)***, while reproducibly inventing numbers — `score = 20.45` beside an unrelated interval becomes `score = -0.45`; `[2.92, 0.30]` becomes `[-.92, 0.30]`, manufacturing a minus that was never printed, on the exact reversed-CI shape this file elsewhere commits to passing through; and `recover_dropped_minus_ci_upper` re-centres an interval that **already validly contains** its estimate, resolving no contradiction at all. Same corruption class is handled correctly by `W0h`/`W0m`/`W0p`, which gate on the FONT of the specific character — on the same paper (`efendic_2022_affect`), the body font `AdvTimes` draws **35,682 glyphs across 86 distinct characters** while `AdvP586B` draws **124 glyphs across 3**: `'2'`×99, `'3'`×24, `'.'`×1. A "font" whose entire repertoire is `2`, `3` and `.` is the symbol face drawing minus and multiply, decoded as digits. **Re-run it: `python tools/diag/symbol_font_census.py <pdf>`.** *(This sentence previously asserted "corrupt shapes came from the symbol font 64/68 while real digits came from the body font 135/135" — not reproducible from this repo. the internal overhaul register §G3 replaced it with "9 differ, 2 match, no overlap", which **also** did not reproduce: re-measured 2026-08-15 it gives 10 differ, 6 match, and the font sets DO overlap. A per-token ratio depends entirely on how you enumerate tokens and no method was ever written down, so no method could be re-run. Twice is a pattern: **quote a number only with the command that regenerates it.**)* **The rule: if you cannot point at something the renderer emitted, pass through.** Standing `/docpluck-review` check.
- **MEASURE THE DENOMINATOR SEPARATELY FROM THE SHAPE — one real paper proves the shape EXISTS and says NOTHING about how often.** (User directive 2026-08-15.) The rule that a case must come from a real DOI (2026-08-13) is about EXISTENCE. It is not a prevalence claim, and both errors were made in one day. `W0o` was justified from ONE paper and shipped as a narrow fix; re-measured against 200 papers sampled from the 9,825-PDF repository it fires **181 times in 21 papers (10.5%)** — a systematic failure of one publisher's font pipeline, not a quirk. `W0b`/`W0d`/`W0g` were built for ONE paper and fire **0 times in 226**. ***(RE-MEASURED 2026-09-07 and the "0 times" does not hold as a general claim — `W0b` and `W0d` DO fire. Over the 101-paper local test corpus, pass 1, `NormalizationLevel.academic`, reading `NormalizationReport.steps_changed`: `W0g` 0 papers, **`W0b` 1 paper, `W0d` 1 paper** (`efendic_2022_affect`). AND WHERE THEY FIRE THEY ARE CORRECT — neutralising both and diffing recovers **62 minus signs**, turning `r = 2.74 [20.92, 20.30]` into `r = -.74 [-0.92, -0.30]`: an impossible correlation and a descending interval, repaired properly. The 226-paper figure carries no command, so it cannot be re-run and this is not a refutation of it — it is a different corpus measured a different way, which is exactly why this file elsewhere says to quote a number only with the command that regenerates it. **The operational point: do NOT retire `W0b`/`W0d` alongside `W0g` on the strength of the "0 times" line — doing so would lose real recoveries.** `W0g` remains condemned on its own evidence: it turns `p = .05` into `p = -.05`, an impossible value, and directive `0c90a18` names CI containment as forbidden.)*** Same evidence standard, opposite conclusions, and neither was knowable without counting. **Before keeping or killing a rule, sample a real denominator and report it.**
- **A ZERO IS A CLAIM ABOUT THE INSTRUMENT UNTIL YOU PROVE OTHERWISE.** (User directive 2026-08-15.) `tools/diag/repair_site_scan.py` reported **0 sites for every W0 glyph rule**, which reads as "these rules never fire" and means nothing of the sort: its corpus is the 26-paper render baseline, and that baseline contains **none of the papers those rules were built for**. A denominator that excludes every known positive cannot speak to prevalence. This is the same trap as the retired locale detector ("396 English papers -> 0 European" measured the INSTRUMENT) and as the `A6` superscript check, where 0 hits in 146 papers turned out to mean pdftotext flattens superscript codepoints before any rule sees them. **Before reporting a zero: run the detector against a KNOWN POSITIVE and show it fires.** If you cannot produce a known positive, say the measurement is unbounded rather than clean.
- **A DISCRIMINATOR DOES NOT TRANSFER BETWEEN CORRUPTION CLASSES — verify it per class, on the primary source.** (Measured 2026-08-15.) After the `<`-as-`b` fix, `pdffonts`' `uni` column looked like the general answer to glyph corruption. It is not. Traced to primary source on `10.1016/j.jesp.2013.08.005` p4: the corrupt `b` is drawn by `AdvTT454a7a89` and the surrounding digits by `AdvTT5235d5a9`, and **BOTH report `uni: no`**; no `/Differences` array remaps `0x3C` to `b`. The corruption is baked into the embedded glyph program, invisible to `/Encoding` and `/ToUnicode` alike. `uni: no` discriminates the `2`-for-minus class and **not** this one. **The signal that does fire is a FONT-BOUNDARY DISCONTINUITY** — a single-glyph mid-token switch to a font whose PostScript name does not share its neighbours' family root — which generalises to both. **Never inherit a discriminator by analogy; re-verify it against the specific class, and rasterize.** Related base-rate trap, same day: document-level `uni: no` fires on **84% of 200 papers** (plain Helvetica, Times) and discriminates nothing, while the same signal read PER CHARACTER is decisive.
- **AN UNMEASURED "IN PRACTICE THIS IS RARE" IN A DOCSTRING IS AS DANGEROUS AS AN UNMEASURED RULE — and it is how a defect survives for years.** (Measured 2026-08-15.) `extract_docx.py` documented its own silent OMML deletion and dismissed it: *"in practice this is rare in social science papers where stats are written as plain text."* Nobody measured it. Measured over 26 real papers: **4 (15%) contain OMML, ~45 non-empty spans, and EVERY ONE is `ηp2`, `χ2` or `ρ`** — precisely the effect sizes the library exists to deliver. The claim was not optimistic, it was **inverted**: the construct is uncommon per document and, where present, used almost exclusively for the statistics that matter most. Live consequence: `F(1,86) = 48.50, p < .001, ηp2 = .361.` was delivered as `= .361.` — a value no consumer can attribute to any statistic, which is **worse than a wrong number** because a wrong number can be challenged and an unlabelled one is structurally unidentifiable. **The rule: a KNOWN LIMITATION written down without a measurement is an unpaid debt, not a disclosure.** Grep the docstrings for "rare", "uncommon", "in practice", "edge case", "unlikely" and either measure each or mark it UNMEASURED. Fixed in v2.4.131; the false sentence is retained in the docstring because it is the reason nobody looked.
- **READ WHAT THE FILE ALREADY SAYS BEFORE INVENTING A HEURISTIC.** (User directive 2026-08-15.) A PDF and a DOCX carry a great deal of self-description we were not consulting, while building indirect and risky rules to guess the same facts. `pdffonts` exposes per-font `ToUnicode` presence; pdfplumber exposes the font, size and baseline of **every character**; a DOCX states superscript explicitly in `w:vertAlign` rather than leaving it to be inferred from Unicode codepoints. **Before writing a rule that guesses, ask what the file states.** And measure the signal's base rate before trusting it: document-level `uni: no` fires on **84% of 200 papers** including plain Helvetica and Times, so it discriminates nothing — the same signal read PER CHARACTER is decisive. A signal adopted without its base rate is just a new way to be confidently wrong.
- **AUDIT EVERY CHANNEL, NOT THE ONE YOU WERE LOOKING AT — the UNINSTRUMENTED channel is where the deletions are.** (User directive 2026-08-14, after the finding below.) An audit that names one channel has not measured its own coverage. docpluck has **three** text channels (`normalize_text`, `tables/cell_cleaning.py`, the `render.py` post-process); enumerate them first and state which channel every finding came from. **Evidence, and it indicts the framing of the very run that produced the rest of these rules:** the 2026-08-14 separation-of-duties audit classified all 111 `normalize.py` transformations NOTATION vs REPAIR and counted every numeric rule's firing sites across 297 English papers — and never asked the same question of `render.py`, the channel that actually reaches the user. Asked once, it answered immediately: `10.1017/s1930297500009189` lost an ENTIRE published-results sentence (two correlations, a Hotelling's *t*, three *p*-values, two confidence intervals) to `_suppress_inline_duplicate_table_captions`, and `10.1001/jamanetworkopen.2023.48333` lost a hazard ratio `1.31 (1.20-1.44)` to `_strip_phantom_camelot_tables` — with **no count, no key in `changes_made`, no log line**, because `render_pdf_to_markdown()` chained 54 `md = fn(md)` calls and returned a bare `str`. **Three sub-rules, each a standing `/docpluck-review` check (rule 0g) and `/docpluck-qa` check 3c:** **(1) Go to the uninstrumented channel FIRST** — instrumentation attracts audit, and its absence repels audit and therefore hides more; `A3a` got measured *because* it populated `changes_made`, which is exactly backwards. **(2) Rank by whether the wrong output ANNOUNCES ITSELF**, never by how dramatic the rule is — a stripped separator leaves a wrong-looking number someone can challenge, a deleted statistic leaves nothing at all. **(3) DELETE FURNITURE, NEVER DATA** — a step that removes content must consult `render._carries_statistical_content`, must refuse all-or-nothing per run (a half-suppressed table is a new defect whose gaps nobody can see), and must be recordable: deduplication is legitimate only when a copy demonstrably survives, otherwise it is a deletion wearing a dedup's name. **Corollary: count the steps from the SOURCE** — the handoff said 41, the source said 54. See `LESSONS.md` L-032.
- **ONE CONCEPT, ONE TABLE — two implementations of one rule WILL diverge.** If the same conversion, vocabulary, character class, threshold or pattern set exists in two places, they will drift apart, and the drift is silent. Measured 2026-08-13: `normalize.py`'s A5 step and `extract.py`'s SMP fallback each carried a Greek-to-ASCII table and disagreed on **9 of 9 shared letters**, so a chi-square left docpluck as `chi2` or `ch2` depending purely on which extraction path ran — and a consumer matching `chi2\(` therefore never checked that test, silently. Three of the disagreements collided with a *different statistic* (`eta2`→`n2` = sample size; `beta`→`b` = unstandardized coefficient, the exact corruption W0m exists to undo; `rho`→`r` = correlation). A real-PDF test exercised the offending path and passed before and after the fix because it never asserted the convention. **The rule:** one canonical definition (`docpluck/symbols.py` is the model), every other site derives from it, and a shared test asserts the sites *agree* rather than restating the constants twice. **A library that can convert one input two ways has no contract at all.** Established by user directive 2026-08-13; this is a standing `/docpluck-review` check.
- **EVERY FIX MUST BE GENERAL — serve all future PDFs, never a one-PDF quick-hack.** docpluck is a meta-science tool that processes arbitrary academic PDFs across many publishers. Every change must be keyed on a STRUCTURAL SIGNATURE — a typographic pattern, layout invariant, glyph-corruption shape, section-structure rule — never on paper identity, filename, or a string hard-coded from one PDF. A change that resolves one paper's quirk but risks regressions on others is the WRONG fix; find the general root cause. Regression tests use specific PDF fixtures, but the fix *logic* must generalize to any PDF with the same structural signature. Always run the full 26-paper baseline to confirm no regression; widen verification (broad-read, more AI-golds) when a fix touches a shared code path. Established by user directive 2026-05-15. See memory `feedback_general_fixes_not_pdf_specific`.
- **NEVER swap the PDF text-extraction tool as a fix for downstream problems.** The TEXT channel is `extract_pdf` (pdftotext default mode); the LAYOUT channel is `extract_pdf_layout` (pdfplumber).  They are not interchangeable text sources.  Sections / normalize / batch consume the text channel; tables / figures / F0-layout-strip consume the layout channel.  Real-world-paper bugs (watermarks in body, abstract not detected, column interleaving) must be fixed in the layer that owns the artifact (`normalize.py` W0, `sections/annotators/text.py`, `sections/taxonomy.py`, `sections/core.py`) — not by switching extraction tools.  See [LESSONS.md L-001](./LESSONS.md#l-001--never-swap-the-pdf-text-extraction-tool-as-a-fix-for-downstream-problems) for the full incident record.
- **NEVER use pdftotext with `-layout` flag** — causes column interleaving. See `docpluck/extract.py:13–16` and [LESSONS.md L-002](./LESSONS.md#l-002--never-use-pdftotext--layout-flag).
- **NEVER use `pymupdf4llm`, PyMuPDF (`fitz`), or `column_boxes()`** — AGPL license, incompatible with the authenticated SaaS service.  pdfplumber (MIT) is the only allowed PDF library alongside pdftotext.  See [LESSONS.md L-003](./LESSONS.md#l-003--never-use-pymupdf4llm-pymupdf-fitz-column_boxes-or-other-agpl-licensed-pdf-tools).
- **ALWAYS normalize Unicode MINUS SIGN (U+2212) → ASCII hyphen** — breaks statistical pattern matching otherwise. (`normalize.py` step S5.)  See [LESSONS.md L-004](./LESSONS.md#l-004--always-normalize-unicode-minus-sign-u2212--ascii-hyphen).
- **Test on APA psychology / replication papers, not ML / engineering papers** — performance-metric tables look like statistical results and mask real failures.  See [LESSONS.md L-005](./LESSONS.md#l-005--test-on-apa--replication-report-papers-not-ml--engineering-papers).
- **FIX EVERY BUG FOUND IN THE SAME RUN — NEVER DEFER "PRE-EXISTING" DEFECTS.** When AI verify, /docpluck-qa, /docpluck-review, or any verification surface a defect during a cycle, fix it in the same run. "Pre-existing, not introduced this cycle" is NOT a license to ship around it — it's a signal that an earlier verification missed a real defect that has been silently corrupting outputs in the interim. Group defects by root cause (one cycle per root cause). Queue subsequent cycles immediately in the same run; don't terminate with the backlog non-empty. Established by user directive 2026-05-14 after the v2.4.16 cycle uncovered ~8 pre-existing defects via Phase 5d. See memory `feedback_fix_every_bug_found` and `.claude/skills/docpluck-iterate/SKILL.md` rule 0e.
  - **NEVER report a cycle or run as "clean", "shippable", "PASS", or done while known FAIL verdicts in the corpus remain unfixed.** A verification pass that surfaces N FAILs means there are N sets of defects to fix — full stop. The word "pre-existing" must never appear as a reassurance or as a reason to downgrade a verdict. Shipping an incremental per-cycle fix is correct and expected; *declaring victory while the corpus is broken is not*. If a verification sweep returns 13 FAILs, the run's standing verdict is FAIL and the run continues — fixing every one — until the corpus is clean, or the budget is exhausted and you report an honest PARTIAL with the exact remaining punch-list. There is no "issue we don't fix." If there are issues, you fix them. Always. Re-emphasized by user directive 2026-05-15 after a cycle-1 report framed "13 papers FAIL" as "cycle 1 is clean and shippable."
- **TRIPLE AI VERIFICATION — MANDATORY BEFORE ACCEPTING *OR REJECTING* ANY FINDING.** (User directive 2026-08-05, portfolio-wide; see `~/Vibe/CLAUDE.md` and `_shared/lessons/triple-ai-verification-mandatory-for-science-claims.md`.) Three passes, all required, in order: **(1) you** — inspect the PRIMARY SOURCE directly, which for a PDF means **rasterize and READ the page** (`pdftoppm -png -r 300 -f N -l N doc.pdf out/p`; poppler is license-safe — NEVER PyMuPDF/`fitz`); **(2) codex** — `codex exec --sandbox read-only - < prompt.txt`; **(3) sonnet** — `Agent(model="sonnet")` via Claude Max, never the API. A REJECT is a claim too: this rule was created by a wrong *reject*. **NEVER adjudicate an extraction defect using the extractors under suspicion** — "pdftotext/pdfplumber cannot see it" is NOT "it is not there", and only the second licenses a won't-fix. Incident: the maier η²p finding was filed won't-fix ("never encoded, OCR-tier") on the strength of both extractors reporting 0 occurrences; rasterizing showed the page plainly prints `(η²ₚ = .000, 95% CI [.000, .003])`, and the text layer skips from `victim effect (` straight to `debiasing` — the lost span includes `.000`, `.003`, `.012` and `95% CI`, i.e. **published statistics missing from one channel while the rendered .md prints them from another**. When this rule is strengthened, **re-open every finding previously rejected under the weaker standard**; a wrong reject is invisible.
- **GROUND TRUTH FOR ALL VERIFICATION IS AN AI MULTIMODAL READ OF THE SOURCE PDF — NEVER pdftotext, Camelot, pdfplumber, or any deterministic extractor.** Every deterministic extractor we use has flaws we have already flagged (pdftotext drops Greek glyphs on tight-kerned PDFs and doesn't see tables/images; Camelot phantom-emits empty columns; pdfplumber `extract_words` is unreliable on tight-kerned PDFs). Comparing the library's rendered .md against pdftotext output can mask any bug that pdftotext itself produces — the very class of bugs the library exists to fix. The canonical Phase 5d / AI-verify / corpus-audit procedure: (1) **ground truth is generated by exactly ONE skill — `article-finder` — through ONE shared protocol, `~/.claude/skills/article-finder/gold-generation.md`.** docpluck's own skills (`docpluck-iterate`, `docpluck-qa`) NEVER generate ground truth themselves — no local extraction prompt, no hand-rolled gold-extraction subagent. On a cache miss they invoke `article-finder generate-gold <pdf>`, which extracts and registers the gold under the paper's canonical key. A consumer that carries a private extraction prompt forks the ground truth — the 2026-05-16 audit found docpluck-iterate and escicheck-iterate had each extracted the same paper with a divergent private prompt, producing two different golds. There is one producer, one protocol, one gold per paper. (2) The gold (the `reading` view) is cached in the shared `ai_gold/` repository and reused across cycles AND across projects (PDFs are immutable). (3) A verification subagent compares the library's rendered .md against the shared AI gold (not against pdftotext). Pdftotext / Camelot output remain useful as DIAGNOSTIC artifacts to identify which layer of the library is at fault — but the verdict (PASS / FAIL) is judged against the AI gold ONLY. Established by user directive 2026-05-14 (AI-not-pdftotext) and 2026-05-16 (generation owned by article-finder, never self-generated). See memory `feedback_ground_truth_is_ai_not_pdftotext`, `feedback_gold_generation_via_article_finder`, `.claude/skills/docpluck-iterate/references/ai-full-doc-verify.md`, and `.claude/skills/docpluck-qa/SKILL.md` check 7g.

## THE THREE TIERS — what a rewrite must EARN, and the test that decides

**User directive 2026-09-06**, after `W0k` was found destroying real published digits in
production, and after a cross-model review across three independent model providers. The
review round is retained privately. The user's words:

> *"we shouldn't just be fixing all 3s to \*, we should be checking if the paper uses bad fonts
> and the other signals, and when and only when all these signals converge, only then we make a
> correction. we should never ever discard meta data and important information like that and
> when we discover specific issues with specific fonts, then we should only suggest fixes for
> those specific cases, not for all cases in every situation."*

> *"a general fix for specific problems is a big nono, but I'm also worried about lots of small
> fixes for broken pdfs. what would you suggest as the best generalized strategy here?"*

This section is the answer. It does not replace **"DOCPLUCK EXTRACTS AND NORMALIZES. IT DOES NOT
FIX THE PAPER"** above — it makes that rule mechanically applicable instead of a judgement call.

### The gate test — apply this BEFORE writing any rule

> **If every surrounding word and number were replaced with random garbage, would the same
> evidence still justify the output?**

- **Yes** -> extraction/normalization. The evidence is local to the glyph, the byte, the font.
- **No** -> **repair, and repair is forbidden.** Capitalisation, neighbouring words, variable
  names, CI containment, "that number looks implausible" — all of these are the sentence
  reasoning about itself, and a rule that needs the sentence to make sense is fixing the paper.

`W0k` fails this instantly: its only inputs are the neighbouring words. So did every rule deleted
under the 2026-08-14 EU-numeric directive.

### The three tiers

| tier | what it is | permitted |
|---|---|---|
| **Notation** | a reversible rewrite of a **correctly encoded** character (U+2212 -> `-`, a superscript -> caret) | always |
| **Channel repair** | **our own pipeline** dropped something another channel still holds (a `(cid:N)` pdfplumber still has, a layout-visible superscript) | yes — fix it, COUNT it, and tell consumers |
| **File lie** | the text layer disagrees with the **printed page** | **NEVER silently corrected.** Emit what the file declares, plus a marker |

The tier decides what is allowed. Confidence does not.

### What "signal convergence" has to mean — and the trap

Gilad is right that a correction needs converging signals. **But signals only converge if they
have DIFFERENT PHYSICAL ORIGINS**, and all three consult seats independently made this point.

Subset-font name, tiny glyph repertoire, a font switch, a missing `/ToUnicode` — those are four
**consequences of one typesetting process**, not four votes. In the worked case they do not even
disagree with each other: `/Differences` names the slot `/three` and `/ToUnicode` maps it to
U+0033. **The file is internally consistent and consistently wrong.** The only contradiction is
between what the file DECLARES and what the page SHOWS.

So a sound convergence rule needs exactly two independent origins:

- **(A) the declared encoding** — `/Differences`, `/ToUnicode`, the glyph slot, the font program;
- **(B) the rendered evidence** — the glyph outline, a raster, or OCR of that region.

A linguistic third signal is **not** independence. It is `W0k` again with more steps.

**Corollary, and it is the one that kills a whole class of proposed fixes:** a rule that only
reads `text: str` can never satisfy (B), so it can never be licensed for a file lie. Check the
signature before you check the logic.

### Never a registry of fonts, publishers or papers

Key every rule on an **EVIDENCE CLASS**, never on a producer name, a font name, a journal or a
DOI. This is the existing **"EVERY FIX MUST BE GENERAL"** rule below, and it is also the answer to
Gilad's pile-of-patches worry — the two horns resolve because they are about different things:

- **general** in what the rule KEYS ON — a structural signature that will catch a publisher we
  have never seen;
- **specific** in what it FIRES ON — narrow enough that a correct paper is untouched.

Subset prefixes churn every issue; a publisher can ship a corrected font tomorrow (stale
positive) or a new hash (silent miss); nobody will re-census 8,000 articles. **A specific font is
a TEST FIXTURE, never a branch in the code.** If an evidence cache is ever wanted, key it on the
embedded font program's SHA-256 plus the character code — content, not name — and let an unknown
hash mean FLAG, never guess.

### The arithmetic every rule lives or dies by

**No rule ships, and no rule survives, without its corpus firing count AND how many of those
firings were CORRECT.** Not prevalence — accuracy.

That single number is the standing precedent: the EU-numeric rules were deleted for firing "ten
times in three papers and NOT ONCE correctly" over 297 papers. `W0k` fired on five papers in a
101-PDF corpus with **one correct and four destroying real published values**. Same arithmetic.

A rule with no correct/total number is unjustified, whatever its reasoning looks like.

### The output contract for a suspect value

Emit the declared text — a consumer that ignores the marker gets exactly today's behaviour, never
a silent substitution. The marker carries: page, character span or bbox, font PostScript name
(de-prefixed), glyph slot, declared codepoint, the `/Differences` glyph name, the evidence class
id, whether paint/OCR was consulted (`none|layout|ocr`), and the rule id + version.

**One deliberate exception, and it is the sharp edge of the design.** A parsed STATISTIC whose
span carries an unresolved conflict must NOT be available through the ordinary accessor — it
raises, or it comes back absent. Free text is fail-open; a number is fail-closed. The reason is
measured: this same font bug turns `-0.95` into `20.95`, a **sign error in a published
coefficient**, and a wrong number that looks plausible is the one failure nobody catches
downstream. Sol argued the strict form, Sonnet argued pure additivity, Grok the middle; the split
is recorded in that review. **The strict form was adopted for statistics only, as a maintainer
call rather than a user ruling — it is the one line in this section still open to revision.**

## Architecture: text channel vs layout channel

| Need | Channel | Module |
|------|---------|--------|
| Reading-order linear text | `extract_pdf` (pdftotext default) | `docpluck/extract.py` |
| Per-character font / position / page geometry | `extract_pdf_layout` (pdfplumber) | `docpluck/extract_layout.py` |
| Tables (cell bboxes, columns) | `extract_pdf_layout` only | `docpluck/tables/` |
| Figures (image bboxes) | `extract_pdf_layout` only | `docpluck/figures/` |
| Sections, normalize, batch | `extract_pdf` only | `docpluck/sections/`, `normalize.py`, `batch.py` |
| F0 layout-aware running-header / footnote strip | text from `extract_pdf` + layout from `extract_pdf_layout` | `normalize.py::_f0_strip_running_and_footnotes` |
| Combined output (text + tables + figures) | both, as separate channels | `docpluck/extract_structured.py` |

`extract_structured.py` is the canonical example of using both channels correctly without mixing them.

**On using pdfplumber as reference material:**  pdfplumber's source is open (MIT).  When docpluck needs better column / reading-order handling than pdftotext provides, the strategy is to **study pdfplumber's algorithm** (`pdfplumber/page.py`) and re-implement the relevant logic in docpluck — applied as a *conditional fallback* (e.g. when default pdftotext output looks broken on a paper) rather than as a default replacement.  Credit pdfplumber in code comments and `docs/DESIGN.md` when its algorithms are ported.

## Project skills (in `.claude/skills/docpluck-*`)

These four skills span BOTH repos via absolute paths. Keep paths in sync if either repo moves.

| Skill | Purpose | Targets |
|-------|---------|---------|
| `docpluck-qa` | Full QA suite | Library tests + service tests + ESCIcheck PDFs + production endpoints |
| `docpluck-review` | Code review against hard rules | Both repos' source files |
| `docpluck-cleanup` | Doc / dead-code / config sync | Both repos' docs |
| `docpluck-deploy` | Pre-flight + deploy + verify | Library tag → app requirements bump → Vercel/Railway |

## Key project docs (in `docs/`)

These are the ONLY files under `docs/` that are public — the list is the
allowlist in `/docpluck-cleanup` Section 0.1, and `tests/test_public_repo_hygiene.py`
enforces it. Everything else under `docs/` is internal by default and gitignored.

- `docs/README.md` — public-facing library README (renders on GitHub + PyPI).
- `docs/BENCHMARKS.md` — extraction-quality benchmarks across 50 PDFs.
- `docs/BENCHMARKS_liteparse_2026-06.md` — the liteparse comparison run (a dated RECORD, not a live claim).
- `docs/NORMALIZATION.md` — pipeline step-by-step reference.
- `docs/DESIGN.md` — architecture decisions.
- `docs/SCOPE.md` — **consumer contract.** English-language articles, US numeric convention; EU numbers pass through as printed. Required by the scope rule to be stated here, on the website, and in every consumer report.
- `docs/SYMBOL_CONTRACT.md` — **consumer contract.** "If you maintain a tool that parses docpluck's output, this page is your interface."

`docs/superpowers/specs/` holds design docs for individual features. It is
**internal and gitignored** — it was public until the 2026-08-06 purge, and this
entry used to list it as though it were part of the public doc set.
