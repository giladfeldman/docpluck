# Cross-project lessons: why an iteration loop ships defects it "verified"

**Audience:** any project running an autonomous fix→verify→release loop with
`*-iterate` / `*-qa` / `*-review` project skills — e.g. scimeto, CitationGuard,
ESCImate. (Written from the docpluck post-mortem, 2026-05-17, but the failure
modes are not docpluck-specific.)

**Purpose:** a portable checklist of *why* a self-improving loop can run dozens
of green cycles while the product the user actually touches stays broken — and
what to change in your iteration/QA/review skills so it can't happen to you.

---

## TL;DR

docpluck's iteration loop ran ~14+ cycles, each reporting PASS, each adding
tests, each "AI-verified". Then the user opened the **app** and immediately saw
severe defects: **missing body text** (the project's #1 rule — never lose
text), tables present in one tab but missing/garbled in another, table content
spliced into a sentence mid-word, and mojibake glyphs. None were caught.

The bugs were not exotic. The **verification was structurally incapable of
seeing them**. Six root causes, each one a thing your loop probably also does.

---

## What happened (concretely)

1. The loop verified `render_pdf_to_markdown()` — a **library function** — by
   calling it directly in Python. The user uses the **app**: a frontend → API →
   service → library stack, with a result cache, a pinned library version, and
   normalization-level defaults. Rendering the two flagged PDFs through the
   library at HEAD did **not** reproduce the user's defects. The defects live in
   the **app↔library gap** — a gap the verification never looked at.
2. The regression gate (`verify_corpus.py`) compared each new render against
   **frozen `.md` snapshots** from an earlier cycle, using a character-count
   ratio and Jaccard word-overlap. If a snapshot already contained a defect, the
   new (identically-defective) output scored ~1.0 similarity → **PASS**.
3. Deep ("AI") verification ran **only on the cycle's target paper**. Papers not
   touched this cycle were never re-checked. A regression introduced into paper
   M by cycle N surfaced only if M happened to be a later cycle's target.
4. Verification compared **one output view** (`rendered.md`) against ground
   truth. A table correct in the structured-JSON view but missing from the
   rendered view was invisible — nothing compared the views to each other.
5. The "AI verify" and "broad-read" steps were effectively **manual visual
   reads** ("read the first 30 lines", "eyeball the tab"). Slow, non-reproducible,
   first thing dropped under time pressure.
6. The loop never **re-examined its own gates**. Every cycle a defect "passed",
   that was taken as evidence the cycle was clean — never as evidence the gate
   was blind.

---

## The six root causes (the lessons)

### 1. Verify the artifact the user consumes — not an intermediate

A loop that tests an internal function tests a thing **no user ever runs**. The
user runs the deployed product: a UI, an API, a CLI, with caching, version
pins, config defaults, and serialization in between. Every one of those is a
place for a defect the library-level test cannot see.

**Do:** point your verification harness at the *same entry point and the same
output* the user gets — the API response, the downloaded file, the rendered
page. If the user can "download a .md", verify *that .md*.

### 2. A frozen output snapshot is not ground truth — it rots

Comparing "new output" against "old output" only answers *did it change*, never
*is it correct*. The first time a defect enters a snapshot it becomes the
expected value, and the gate defends the bug forever after.

**Do:** gate against (a) **intrinsic invariants** that are true regardless of
version (every source paragraph must survive; every detected table must render;
no replacement chars) and/or (b) **independent ground truth** (an AI multimodal
read of the source, regenerated, not a cached past output). Store *verdicts*
(pass/fail), not output blobs, as your baseline.

### 3. Re-verify the whole corpus every cycle — "fixed" is not "fixed forever"

Per-cycle/per-target verification is how regressions hide. A fix keyed on one
document's quirk routinely breaks three others; if those others aren't
re-checked, the breakage ships.

**Do:** every cycle, run at least a **cheap deterministic gate over the entire
corpus**. Diff the verdict matrix against the committed baseline. **Any
PASS→FAIL is a regression and blocks the cycle** — even if "this cycle's diff
didn't cause it" (it did, or an earlier cycle did and you're only now seeing
it). Reserve expensive AI inspection for a tiered subset (changed papers + every
open failure + a rotating slice).

### 4. Cheap similarity metrics are blind to structural corruption

Character-count ratio and word-set overlap pass a document whose words are all
present but **in the wrong order, under the wrong heading, or with a table
spliced into a sentence**. They cannot detect one missing paragraph when total
length barely moves. They were the metrics that missed every defect here.

**Do:** check the *invariant that matters directly*. "No text loss" =
**paragraph-level presence** check (each source paragraph ≥ N chars appears in
the output), not a length ratio. Structure = explicit assertions (heading order,
table placement, caption boundaries).

### 5. Check cross-output consistency, not just one view

If your product exposes multiple views of the same document (rendered, tables,
sections, raw, normalized), a fact can be right in one and wrong in another.
Verifying one view in isolation guarantees nothing about the others.

**Do:** assert **parity across every view**: table count in the rendered view ==
table count in the structured view; headings in rendered ⊆ sections data; the
same sentence text reconciles across raw → normalized → rendered.

### 6. Automate the inspection — a manual eyeball silently degrades

A verification step that depends on a human (or an agent) "reading it" is slow,
non-reproducible, and the first casualty of a time budget. "Visual review" that
gets rushed is worse than no review — it produces false confidence.

**Do:** make the harness **save every output to disk** (every document × every
option × every view) and run the checks — deterministic and AI — **on the saved
files, programmatically**. The same inputs must produce the same verdict every
run. A manual read can be a *supplement*, never the *gate*.

### Bonus: stale installs and caches make "local testing" lie

The local app may run a **stale pinned library**; a result **cache** may serve
old output and skip processing entirely (symptom: you extract a file and see no
processing activity in the local logs — that's a cache hit). Either way "I
tested locally" tested the wrong code.

**Do:** the harness must **assert the version under test** at the endpoint
(`/health`/`/_diag` reports the build) and **bypass or version-key every
cache**. Treat an unverified version as a hard stop.

---

## Drop-in checklist for your `*-iterate` / `*-qa` / `*-review` skills

Audit your skills against these. Each "no" is a defect-escape route.

- [ ] Does verification run against the **user-facing artifact** (deployed/local
      app output, downloaded file), not just an internal function?
- [ ] Does the harness **assert the exact code version** it's exercising, and
      **bypass caches**?
- [ ] Is the regression gate based on **intrinsic invariants / fresh ground
      truth** — never a frozen past-output snapshot?
- [ ] Does **every cycle re-verify the whole corpus** (cheap deterministic tier)
      and **block on any PASS→FAIL**?
- [ ] Is the #1 content rule (no text loss / no hallucination) checked at
      **paragraph granularity**, not via a length/similarity ratio?
- [ ] Are **all output views cross-checked** against each other, not one view in
      isolation?
- [ ] Is inspection **automated on saved output files** — reproducible — rather
      than a manual/visual read that can be skipped?
- [ ] After any defect the user reports, do you **fix the gate first** (so that
      class can never escape again), then the code?
- [ ] Does the loop run a **periodic methodology audit** — "for each escaped
      defect, which gate should have caught it, and why didn't it?"
- [ ] Is "pre-existing, not introduced this cycle" treated as a **blind-spot
      signal**, never as a reason to ship around the defect?

## A self-audit you can run today (≈30 min, no code changes)

1. Take 3 documents your loop reported "clean". Open them **in the actual
   product** (not the library). List every defect you see by eye.
2. For each defect: which gate *should* have caught it? Open that gate's code.
   Confirm whether it is even *capable* of catching that defect class. (It very
   likely is not — that's the point.)
3. Check your regression gate: does it compare against a **frozen snapshot**? If
   yes, it is defending whatever bugs were in that snapshot.
4. Check coverage: does each cycle deep-verify only the **target** document? If
   yes, every other document is unprotected against that cycle's regressions.
5. Write the gaps into your skill's LEARNINGS, and amend the skill so each gap
   becomes an enforced gate.

---

**The one-sentence version:** *verify the thing the user actually receives,
against ground truth, across every output view, over the whole corpus, every
cycle, automatically — and when something still escapes, fix the verifier
before you fix the bug.*
