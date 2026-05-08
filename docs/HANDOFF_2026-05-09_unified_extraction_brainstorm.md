# Handoff — Brainstorm: can we produce ONE optimal extraction (text + sections + tables + figures)?

**For:** A fresh Claude session to brainstorm the architectural question with the user. **Do not start coding.** This is a design conversation that has implications across `docpluck/extract*.py`, `docpluck/sections/`, `docpluck/tables/`, `docpluck/normalize.py` and the SaaS app's UI. The user explicitly wants a brainstorm, not implementation.

**Sister handoff (state of the codebase):** [HANDOFF_2026-05-09_session_state_and_followups.md](HANDOFF_2026-05-09_session_state_and_followups.md). Read it first so you know where the codebase is.

**Required reading before responding:**
1. [LESSONS.md](../LESSONS.md), particularly L-001.
2. [docs/DESIGN.md](DESIGN.md) §13 ("Two channels: text vs layout").

---

## The user's question, in their words

> "I don't care much for speed, I do however really care about accuracy. Some academic sessions need both. They need the best text, but they want the sections/tables/figures using *that* text. Isn't there a way to do both optimally? … Telling academics, here are two different outputs for the same document — figure it out, doesn't seem acceptable. I feel like we can do better."

The user is asking: **for a single PDF, can docpluck return ONE accurate, unified result containing the cleanest possible text *and* the sections / tables / figures derived from that same text — instead of forcing the consumer to reconcile two separate extractions?**

They're explicitly OK with paying the speed cost. Accuracy + unification is what they care about.

---

## Why this is a hard question (the constraint that makes it interesting)

Today's docpluck has two extractors that answer different questions:

| Channel | Source | Strength | Weakness |
|---|---|---|---|
| Text | `extract_pdf` (pdftotext default mode) | Reading-order linear text; clean word boundaries; ~250 tests + a corpus of empirical heading patterns are calibrated to this | No char positions, no fonts, no per-page layout |
| Layout | `extract_pdf_layout` (pdfplumber) | Per-char fonts / positions / page geometry; powers tables + figures | Linear text via `extract_text()` mishandles column reading-order on many real-world papers; word-spacing differs from pdftotext |

[`extract_pdf_structured()`](../docpluck/extract_structured.py) already calls both and returns a combined dict — but its `text` field is pdftotext's text and its `tables` field is pdfplumber-derived. They are produced by separate parses and **never reconciled**. The consumer gets two views of the same document.

**The temptation everyone has tried (and reverted):** unify by switching the text source to pdfplumber's `extract_text()`, so the layout-derived structures (tables, F0 footnote strip, etc.) operate on the same string the consumer sees. Three sessions in a row have done this and reverted within an hour because pdfplumber's text format breaks ~250 calibrated heuristics. See [LESSONS.md L-001](../LESSONS.md#l-001--never-swap-the-pdf-text-extraction-tool-as-a-fix-for-downstream-problems).

So the question is **not** "should we use one tool instead of two." It's "**given that pdftotext's text is best for sections and pdfplumber's layout is best for tables/figures, how do we produce one consistent output where every offset / heading / table is a faithful reference to the same underlying paper?**"

---

## What "one optimal output" might mean concretely

Pick one of these (or invent a better one) and discuss tradeoffs:

### Definition A — single string, every offset valid

ONE canonical text string. Every section / table / figure / footnote / running-header reference points to char offsets *in that string*.
- Easiest for consumers; "source of truth" is unambiguous.
- Hardest to produce because tables are 2D structures (rows / cells) that need to be rendered into the linear string somehow (e.g. as TSV, or with `[Table 1: see structured.tables[0]]` placeholders).

### Definition B — multiple views, all aligned

Multiple representations (linear text, table grid, figure list) but with a **mapping** between them. Section X spans char offsets [a, b] in the linear text AND covers pages 3–5 of the layout. Table 2 has cell text "0.45" at row 3 col 2 AND those exact characters appear at char offset c in the linear text.
- More flexible: each consumer picks the view they want.
- Requires a synchronization invariant: the linear text and the layout text must be derivable from the same source so offsets line up.

### Definition C — text-first with layout annotations

The "primary product" is the linear text (cleaner = better). Layout-derived metadata (table regions, figure regions, font sizes per char span) is attached as a side-channel keyed by char offset. Tables are extracted by mapping pdfplumber's table region to the same char offset range in the primary text.
- Closest to what consumers in `extract_structured` already have today, but with the synchronization actually enforced.
- Hard part: pdfplumber's chars and pdftotext's chars don't necessarily occupy the same offsets in the same string.

---

## Candidate technical approaches (not exhaustive — the user wants you to think more broadly too)

### Approach 1 — Stay with two extractors, add a reconciliation layer

Run both extractors as today; produce a **mapping** between pdftotext char offsets and pdfplumber char positions. With the mapping, table regions (pdfplumber bbox) can be expressed as ranges of pdftotext char offsets. F0 running-header strip operates on pdftotext text but uses pdfplumber-derived "lines that repeat at top of page" via the mapping.

- **Strength:** preserves the calibrated text channel intact. No regression risk to the 250+ test corpus.
- **Hard part:** building the offset mapping. Needs character-by-character alignment between two text streams that differ on word-spacing / line-breaks. Probably approached via dynamic-programming alignment (Needleman-Wunsch on chars) constrained by page boundaries (form-feed `\f` is a known-shared boundary).
- **Open question:** how often do the two streams disagree by more than a few chars per page? If the mapping is mostly identity with occasional skips, this is tractable. If the streams diverge dramatically on dense column papers, the mapping is brittle.

### Approach 2 — Use pdftotext `-bbox-layout` mode (single tool, both channels)

pdftotext has an undocumented-ish `-bbox-layout` mode that emits HTML where each `<word>` element has `xMin`/`yMin`/`xMax`/`yMax` attributes. This gives **one parse that produces both reading-order text AND character bounding boxes** from the same engine. Tables / figures / F0 strip would all operate on positions tied to pdftotext's text.

- **Strength:** one parse, one source of truth, and the text format is exactly what the existing pipeline expects (pdftotext default).
- **Hard part:** pdftotext's bbox mode is less feature-rich than pdfplumber for table/figure extraction (no line / rectangle detection — those are vector-graphics features pdfplumber gets from pdfminer).
- **Worth investigating:** can we use `-bbox-layout` for the chars + positions, and pdfplumber ONLY for line / rect / curve geometry? Then both views live in the same coordinate space.

### Approach 3 — Treat pdfplumber as the single canonical source and migrate everything

Long-term clean: standardize on pdfplumber for both text and layout, retune all 250+ tests + heuristics to its format. Done once, the architecture is simple.

- **Strength:** unified, principled, every offset is canonical.
- **Hard part:** requires re-running the entire strict-iteration corpus campaign on pdfplumber output, re-tuning every regex, accepting that some current behaviors will silently shift. Probably 2–4 weeks of focused work + extensive QA.
- **Risk:** if pdfplumber's text proves worse than pdftotext on some layouts (it does on certain two-column papers), you've burned the boats.

### Approach 4 — Build a "best-of-both" extraction by porting pdfplumber's algorithms onto pdftotext-derived char positions

pdfplumber's column-detection / repeating-line-detection / word-clustering algorithms are open-source (MIT). Re-implement them in docpluck operating on pdftotext's `-bbox-layout` HTML output. You get pdfplumber-quality structure with pdftotext's text fidelity. Credit pdfplumber in code comments.

- **Strength:** combines the strengths of both tools without runtime dependency mixing.
- **Hard part:** pdfplumber's algorithms assume access to the full pdfminer character stream; pdftotext gives a more constrained view. Some algorithms may not port cleanly.

### Approach 5 — Two extractors, one *post-processed* output

Each extractor runs; the outputs are reconciled by a layer that knows about both formats. Produces ONE final output (e.g. a JSON document with `text`, `sections`, `tables`, `figures`, `pages`) where every cross-reference has been validated.

- This is essentially "Approach 1, but the consumer never sees the two streams." Internally we have two; externally one.
- **Open question:** is the reconciliation worth doing inside docpluck, or is the consumer best served by us being explicit about the dual-stream nature?

---

## Specific things to investigate during the brainstorm

- **What does `pdftotext -bbox-layout` actually look like for a typical academic paper?** Run it on a paper from `~/Dropbox/Vibe/MetaScienceTools/PDFextractor/test-pdfs/apa/` and inspect the HTML. Does it have what tables/figures need (line drawings, rectangles)? Or only chars + positions?
- **How divergent are pdftotext's text and pdfplumber's `extract_text()` on the same paper?** Run a char-level diff on `efendic_2022_affect.pdf` (clean APA), `nat_comms_1.pdf` (Nature 2-col), `chen_2021_jesp.pdf` (JESP 2-col). If they diverge by <5% per page, Approach 1's offset mapping is feasible. If they diverge by >20%, it's not.
- **What does pdfplumber actually do that pdftotext doesn't?** Specifically: line / rect / curve detection (used by `tables/cluster.py` for "lattice" table detection); character positions (used by F0 layout-aware running-header strip). Are there alternative ways to get those without pdfplumber's text stream?
- **What do downstream consumers actually want?** ESCIcheck, MetaESCI, Scimeto. They each call docpluck's library API. Read their consumer code (paths in PDFextractor/CLAUDE.md and in the docpluck repo's CHANGELOG). Do they want one unified output or are they happy with two streams?

---

## What is OUT of scope for the brainstorm

- **Adding a new PDF library.** Only pdftotext + pdfplumber are allowed (license constraint, see L-003).
- **Switching to a different default text source.** L-001 has been re-derived three times; the brainstorm should treat that as a settled constraint, not relitigate it.
- **A full rewrite of docpluck.** Whatever is proposed has to be additive or migratory in a way that keeps the existing 250+ test corpus green.
- **Coding.** This is design / discussion. Implementation comes after the user agrees on a direction.

---

## Concrete deliverable from the brainstorm session

A short design document — say 1–2 pages — that:

1. States the user's problem in one paragraph.
2. Picks ONE of the approaches above (or invents a better one) as the recommendation.
3. Lists the open questions that need empirical investigation before committing to that approach (e.g. "diff pdftotext and pdfplumber output on N papers").
4. Sketches a migration path from today's two-stream world to whatever's recommended, with named milestones.
5. Calls out what could break if the recommendation goes wrong (so the user can weigh tradeoffs).

Save it as `docs/superpowers/specs/2026-05-XX-unified-extraction-design.md` once the user has signed off.

---

## How to start the conversation with the user

The user has already framed it: they want one extraction that's both accurate AND structurally complete (sections + tables + figures). They want the text to be the same text the structures reference.

A good opening:

> I read both handoffs and LESSONS.md. The constraint is clear: pdftotext for text, pdfplumber for layout, no swapping. Within that constraint there are at least 5 ways to give you a unified output. Before I pick one, I want to understand which of these matters more to your consumers: (a) one canonical text string with everything pointing at offsets in it, or (b) multiple views with a guaranteed alignment between them. The first is simpler for consumers but forces tables to render into the text somehow; the second is more flexible but requires we publish the alignment as part of the API. Which feels right?

Then explore the approaches with concrete tradeoffs. **Don't immediately propose code.**

Good luck. The user has been thoughtful and consistent in feedback through this iteration; this is a real architectural question worth thinking carefully about.
