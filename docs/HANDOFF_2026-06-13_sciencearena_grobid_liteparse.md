# docpluck ← ScienceArena: GROBID/liteparse re-audit + F0 layout body fix (2026-06-13)

**Trigger.** ScienceArena's public PDF leaderboard
(`sciencearena.vercel.app/arenas/pdf-{section-structure,table-extraction,text-fidelity}-v1`)
showed docpluck below GROBID (sections, tables) and below GROBID + liteparse
(text fidelity). The 2026-06-12 handoff had only covered docpluck-vs-liteparse, so
GROBID was a new, unexamined comparator. Question: artifact again, or real?

## Verdict: one artifact, one real bug

### Artifact — GROBID/liteparse beating docpluck on the leaderboard
The ScienceArena leaderboard aggregate (`framework/leaderboard.py::aggregate()`) takes
a flat mean over whatever task_ids each player ran, with **no task-id intersection**.
GROBID/claude/gemini ran only the small synthetic public split; docpluck additionally
ran 30+ hard held-out real papers, which drag its flat mean down. On the **common**
task set docpluck is at or above every competitor:

| Arena | Common tasks | docpluck | GROBID | liteparse |
|---|---|---|---|---|
| sections | 6 synthetic | **0.890** | 0.722 | 0.767 |
| tables | 2 synthetic | **0.467** | 0.412 | 0.000 |
| text fidelity | 24 synthetic | **0.898** | 0.897 | 0.880 |

This is an arena-side leaderboard-fairness bug (same class as the 2026-06-12
liteparse finding, only half-fixed). It is **not** a docpluck defect and requires no
docpluck change. The global fix is handed back to ScienceArena:
`ScienceArena/HANDOFF_2026-06-13_pdf_arena_global_fairness.md` (make the aggregate
intersection-aware at the framework layer; rank only players that ran the full split;
apply to all players + all arenas, not symptom-locally).

### Real — docpluck text fidelity collapsed on real biomedical PDFs (FIXED here)
On the held-out PMC set, docpluck's text fidelity was genuinely below liteparse and
raw pdftotext — but for a specific, fixable reason. ~16 of 30 papers scored token-F1
**≈ 0.00** against the JATS gold *with a normal character count*: the words were glued
(`CNSSpectrums`, `Thebehavioralhealthcarecontinuuminthe`).

**Root cause.** `normalize_text(..., layout=...)` (the recommended body-fidelity path
since v2.4.83) rebuilds the body from `TextSpan.text`, and `extract_layout._chars_to_spans`
built span text with a naive `"".join(chars)` — **no x-gap space reinsertion**.
pdfplumber's char stream omits the inter-word space glyph on tight-kerned PDFs
(Cambridge, two-column), so the layout body collapsed to space-ratio ~0.005 (vs ~0.13
via pdftotext). The function's docstring even *claimed* x-gap handling that was never
implemented. This is the `feedback_pdfplumber_extract_words_unreliable` failure
("always carry a char-level absolute-x-gap fallback") — never applied to span text.

**Fix (v2.4.86, `NORMALIZATION_VERSION` 1.9.33).** New
`extract_layout._join_chars_with_spaces` reinserts a space when the horizontal gap
between consecutive glyphs exceeds `0.20·font_size` — keyed on the structural signature
(x-gap), so it generalizes to every tight-kerned PDF, not one paper. Results:
- PMC13064744 token-F1 **0.00 → 0.86** (pdftotext baseline 0.93); space-ratio
  0.0053 → 0.1282.
- Full 30-paper PMC corpus token-F1 mean **~0.34 → 0.747** (0 catastrophic-zero
  papers, was 16/30; min 0.42, max 0.92) — on par with pdftotext (~0.77), above
  liteparse (~0.72).
- Full test baseline: **1584 passed, 0 failures** (no regression).
- New regression tests in `tests/test_extract_layout.py`.

**Known residual (not addressed here, tracked for follow-up).** `_chars_to_spans` still
does not split a line at a column gutter, so a line spanning two columns is merged
(minor reading-order interleaving in the layout body; the text channel handles column
order correctly). This caps the per-paper lift slightly below raw pdftotext on
two-column papers; it is a smaller, separate issue than the catastrophic gluing.

## What to learn from the open-source comparators
- **pdftotext**: its space-from-x-gap inference is precisely what docpluck's layout span
  reconstruction was missing. docpluck already had the correct spaced text via
  `extract_pdf`; the bug was that F0 discarded it and rebuilt from unspaced spans.
- **GROBID / liteparse**: nothing to port on extraction quality — on equal task sets
  docpluck matches or beats both. The lesson there is methodological (leaderboard
  fairness), owned by ScienceArena.

## Follow-ups
1. ✅ **DONE (v2.4.87, `NORMALIZATION_VERSION` 1.9.34).** Took the deeper option: F0
   (`_f0_strip_running_and_footnotes`) no longer rebuilds the body from spans — it now
   strips the identified header/footer/footnote *lines from the pdftotext body* and keeps
   the rest in pdftotext order/spacing (the documented text-channel/layout-channel split).
   This closed the residual two-column interleaving without needing column-gutter span
   splitting. Held-out PMC token-F1 mean **0.747 → 0.776** (above raw pdftotext 0.750),
   primary **0.559 → 0.666**. The span-text x-gap spacing fix (`_join_chars_with_spaces`)
   is retained — now load-bearing for span→pdftotext key matching and the sections/tables
   layout consumers. See CHANGELOG [2.4.87] and LESSONS L-007.
2. (release) Bump the `PDFextractor/service/requirements.txt` docpluck pin to v2.4.86
   and run `/docpluck-deploy` (this fix changes production body output on tight-kerned
   PDFs). Not done in this run.
3. (ScienceArena) Act on `HANDOFF_2026-06-13_pdf_arena_global_fairness.md`; re-run the
   three PDF arenas at docpluck >= 2.4.86 over the full symmetric split.
