# Handoff — autonomous `/docpluck-iterate` run (APA-first), session 1

**Authored:** 2026-05-15, end of session. Picks up from `docs/HANDOFF_2026-05-15_autonomous_apa_first_10h.md`.
**Stop reason:** session budget / context length. The run is **PARTIAL — the APA corpus is NOT clean.** This handoff carries the full punch-list to the next session per rule 0e-bis (never report "clean" while FAILs remain).

---

## 1. State at handoff

| Item | Value |
|---|---|
| Library version | **v2.4.36** (tag pushed; `__init__.py` + `pyproject.toml` synced) |
| Prod `/_diag` | v2.4.33–v2.4.35 confirmed; v2.4.36 deploy in flight at handoff |
| `NORMALIZATION_VERSION` | 1.9.2 · `TABLE_EXTRACTION_VERSION` 2.1.1 |
| 26-paper baseline | **26/26 PASS, 0 WARN** at every cycle |
| Broad pytest | 1174 pass / **15 failed (all pre-existing snapshot drift — see §5)** / 0 new |
| AI-gold cache | All 28 generated golds registered in `ai_gold/`; 15/18 APA `reading` golds (3 content-filter-blocked) |

## 2. Cycles shipped this session

| Cycle | Version | Defect | Layer | Papers |
|---|---|---|---|---|
| 1 | v2.4.33 | D1 — letter-spaced Elsevier front-matter labels (`a r t i c l e`, `a b s t r a c t`) leaked as body text, suppressed `## Abstract` | `normalize.py` H0b | 3 (010/011/012) |
| 2 | v2.4.34 | GLYPH — math-italic Greek transliterated to ASCII Latin by S0 (`𝜂`→`n`, `𝛽`→`b`); corrupted effect-size symbols | `normalize.py` S0 + `cell_cleaning` + `render` (shared `destyle_math_alphanumeric`) | ~9 (korbmacher recovered FAIL→PASS) |
| 3 | v2.4.35 | D6 — orphan arabic section numbers stranded before `## ` headings | `render.py` `_fold_orphan_arabic_numerals_into_headings` | ~8 |
| 4 | v2.4.36 | GLYPH — `(cid:0)` corrupted minus signs in Camelot table cells | `tables/cell_cleaning.py` `_html_escape` | ziano, chen (+any pdfminer-unmapped-glyph paper) |

All four cycles: 26/26 baseline, 0 new pytest failures, surgical verified diffs, real-PDF regression tests added.

## 3. APA corpus status — 2 PASS / 13 FAIL / 3 gold-blocked

- **PASS (2):** `jdm_.2023.10`, `korbmacher_2022_kruger` (korbmacher recovered after cycle 2 — Greek was its only blocking-severity defect).
- **FAIL (13):** efendic, ziano, chan_feldman, chandrashekar, jdm_.2023.15, jdm_.2023.16, jdm_m.2022.2, jdm_m.2022.3, maier, ip_feldman, xiao, chen, ar_apa_j_jesp_2009_12_011. Cycles 1–4 reduced each paper's defect count but none of these is cleared — they retain table / section / metadata defects. **Re-verify them at v2.4.36 first thing next session** (cycles 3 & 4 fixes were not re-verified per-paper).
- **Gold-blocked (3):** `ar_apa_j_jesp_2009_12_010`, `..._012`, `jamison_2020_jesp` — the Anthropic API content filter blocks the gold-extraction subagent's output for these JESP social-psych papers (3 attempts each, varied prompts/chunking). No AI gold exists; render-pass verification only. This is a platform limitation, documented — not deferred work.

## 4. Open queue — punch-list for the next session

Canonical detail is in `docs/TRIAGE_2026-05-14_phase_5d_gold_audit.md` "APA Phase-5d FULL VERIFIER SWEEP". Root-cause groups still open, ranked:

| Group | Sev | Papers | Notes |
|---|---|---|---|
| **TABLE** destruction | S0/S1 | ~11 | caption→thead weld, dropped rows, body-prose bleed, empty shells, two-tables-merged, xiao Table 6 numeric SWAP, G4a body-stream dumps. C3 cluster — needs design. |
| **G5** subsection demotion | S1 | ~12 | numbered subsections (`2.1`, `5.3`) + non-canonical numbered top-level sections (`2. Omission neglect`) emitted as body text, not `###`/`##`. `sections/` + a render promoter. |
| **HALLUC-HEAD** | S1 | ~7 | mid-sentence fragments / table-cell labels / TOC entries promoted to `##` (`## Methodology`, `## Conclusion`, `## Appendix`, `## Data Availability Statement`). Tighten heading promotion. |
| **GLYPH minus `−`→`2`** | S0 | efendic (29 CIs) + standalone `r = 2.74`, `M = 20.54` | text-channel pdftotext corruption; recoverable via descending-CI-bracket discriminator + implausible-correlation rule. C2, risky — dedicated cycle. |
| **GLYPH minus `−`→deleted** | S0 | 011 | pdftotext drops U+2212 entirely; unrecoverable from text channel — needs layout-channel glyph identity. C3-C4, escalate. |
| **D4** metadata splice | S2 | ~all JDM | CC-license banner + `…Published online by Cambridge University Press` DOI footer spliced MID-SENTENCE into body prose. `normalize.py` page-footer strip — recognizable pattern, C1-C2. |
| **FIG** caption defects | S2 | ~8 | double-emission, truncation, body-prose welded into captions (chan_feldman Figure 10 hallucinated). |
| **COL** column-interleave | S0 | chan_feldman, chandrashekar | reading-order scramble. C3. |

Plus: **15 pre-existing pytest failures** (test-snapshot drift, see §5) — a `tests:` regen cycle. And the **3 gold-blocked APA papers**.

**Recommended next pickup:** (1) re-verify the 13 FAIL papers at v2.4.36 to get an accurate post-cycle-1–4 baseline; (2) D4 Cambridge-footer strip (clean, ~5 papers, C1-C2); (3) HALLUC-HEAD (tighten heading promotion); (4) G5; (5) efendic `−`→`2`; the TABLE cluster + COL are C3 — a dedicated session.

## 5. Pre-existing pytest failures (15 — carry-forward, queued)

Test-snapshot drift, NOT library bugs (the library output is verified correct vs AI-gold): 12× `test_v2_backwards_compat::test_extract_pdf_byte_identical` (raw-`extract_pdf` snapshots predate pdftotext version skew — untouched by any cycle this run), 2× `test_sections_golden` (regen with `DOCPLUCK_REGEN_GOLDEN=1`), 1× `test_request_09` bibliography regex. A standalone `tests:` regen cycle — verify new output against AI-gold before regenerating snapshots.

## 6. Process changes encoded this session (4 user directives)

- **Rule 0e-bis** (CLAUDE.md + SKILL.md): never report a cycle/run "clean"/"PASS"/done while known FAIL verdicts remain; "pre-existing" is not a defense; honest PARTIAL with punch-list at budget-stop.
- **Hard rule 16 / general fixes** (CLAUDE.md + SKILL.md): every fix keyed on a structural signature, never paper identity; 26-baseline-gated.
- **Hard rule 17 / subagent MANDATE** (SKILL.md): batch of 2+ independent units → parallel background subagents.
- **Hard rule 18 / gold persistence** (SKILL.md): every AI gold `register-view`'d to article-finder under the canonical DOI key the moment generated; Phase-12 end-of-run audit; `references/ai-full-doc-verify.md` "Choosing $KEY". 5 JDM golds re-keyed off stems onto canonical DOI keys this session.
- Memories: `feedback_use_subagents_aggressively`, `feedback_general_fixes_not_pdf_specific`, `feedback_gold_canonical_key`; `feedback_fix_every_bug_found` extended.

## 7. Stop reason

Session budget / conversation length. 4 cycles shipped, all clean; the APA corpus is improved but **not clean — 13 papers still FAIL**. Per rule 0e-bis this is reported as an honest **PARTIAL**, not "done". The next session resumes from §4.
