# TRIAGE 2026-06-15 — corpus assessment at HEAD v2.4.88 (supersedes 2026-06-08)

**Method:** Fresh broad-read + full-document AI-verify (Sonnet subagents vs article-finder `reading` golds) of the 5 canary papers + the 3 two-column papers that FAILed the 2026-06-08 sweep. Rendered at **v2.4.88** via `tools/render_for_audit.py` (I9, article-finder cache-check). **All findings re-verified at HEAD** before trusting the verifier (per `reproduce-triage-defect-at-head` + cross-project R-0006); confirmed-real and false-positive findings are separated below.

**Result: 7/7 FAIL, 1 BLOCKED (plos_med_1 — no gold).** Standing run verdict: **FAIL** (rule 0e-bis). The single dominant root cause is RC-1 two-column interleave; one separable catastrophic class (B7) is confirmed.

---

## What SHIPPED since the 2026-06-08 TRIAGE (was @ v2.4.80; now @ v2.4.88)

- **RC-2 metadata / running-header leaks — DONE.** v2.4.81 (Elsevier footer ×20, Nature footer ×15, lowercase corresponding-author) + v2.4.83 (bare `J. Chen et al.` ×20, footnote surface, label de-dup). The 2026-06-08 "fixable now" class is closed; canary front-matter is clean (ip_feldman first-page verified clean).
- **v2.4.84** R2 quantifier-head guard (stop deleting digits from ref titles). **v2.4.85** Harvard refs + page-break stitch. **v2.4.86/87** ScienceArena F0 body-from-text-channel + x-gap spaces. **v2.4.88** Camelot Windows temp-file cleanup (tables restored on Windows).

---

## RC-1 — Two-column reading-order INTERLEAVE · S0 × C4 (ARCHITECTURAL — needs user go-ahead) · **THE DOMINANT DEFECT**

Confirmed catastrophic on **4/4** two-column papers at HEAD:

| Paper | Confirmed RC-1 damage |
|---|---|
| `jesp_2021_104154` | 8+ numbered-section inversions (§3<§2, §5<§4, §5.3<§5.2, §7.2<§7.1, §7.4.2 after §7.4.6); Table 1/2 merged, Table 3 phantom dup, Table 8 body-embedded |
| `collabra_77859` | pervasive interleave (Intro/Participants, Study-1 Discussion); **all 5 tables** missing data or wrong-table content |
| `collabra_37122` | `## Conclusion` displaced after all back-matter; heading "Methods, Hypotheses… of the Target Article" split; Table 4 missing a column; Table 1/2 duplicated |
| `chandrashekar_2023_mp` (canary) | Tables 7/8 empty shells, Table 9 holds Table 10 data; Participants displaced; Fig 4/5 captions injected mid-Discussion |
| `chan_feldman_2025_cogemo` (canary) | heaviest — Method/Results/PCIRR scrambled; 5/9 tables unstructured fallback; Discussion subheadings demoted to body |

**KEY NEW FINDING (changes the plan): the existing RC-1 Step-1 flag is NOT a shortcut.** Re-rendering all 3 two-column papers with `DOCPLUCK_COLUMN_CORRECT_GENERAL=1` produced **byte-near-identical** output (collabra_37122 *identical*; jesp_2021 200712→200581 B). Step 1's whole-page gutter-gated crop is skipped on table-bearing / no-clean-gutter pages — i.e. exactly these papers. **Only Step 2 (per-band region-aware crop, `docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md`) can fix them.** Flipping the Step-1 default is ruled out as a win.

---

## B7 — Deleted-minus glyph (silent sign-flip) · S0 × C3 (ARCHITECTURAL — needs user go-ahead) · **SEPARABLE CATASTROPHE**

**CONFIRMED real against gold** on `ar_apa_j_jesp_2009_12_011` — body-prose betas (no CI to recover from):

| Gold | Rendered |
|---|---|
| `β = −.022, t(87)=.17` | `b = .022` |
| `β = −.88, t(87)=2.01` | `b = .88` |
| `β = −.245, t(43)=.30` | `b = .245` |
| `β = −.428, t(44)=3.14` | `b = .428` |

4 of 5 betas have the minus **silently dropped** (and Greek β→Latin b). pdftotext drops the U+2212 glyph on this tight-kerned 2009 Elsevier PDF, so it never reaches normalize → text-channel recovery is impossible; needs the **layout channel** (per-char glyph identity) or a co-located invariant. This is the deferred R5/B7 class (todo.md). It is paper/encoding-specific: ip_feldman betas render correctly signed (`β = -.23`). 3-path decision (layout per-char recovery / whitelist-warn / document-as-limitation) needs sign-off.

---

## Separable symptom defects (entangled with RC-1 on 2-col papers; low value to fix before RC-1)

- **Affiliation promoted to `### heading` inside Abstract** (chandrashekar: `### Department of Philosophy, Lake Forest College`). Demote-able via the `_FRONTMATTER_LEAK`/`_demote_metadata_label_headings` family — but placement is interleave-driven.
- **Table-cell numerics loose in body** (ip_feldman Table-6 region L711+: `46.08 / 69.64 / -23.56 …`). One `### Table N` heading without a matching `<table>`.
- **Method subsection headings demoted to body** (ar_apa: Overview / Practice instructions / Self-control assessment). Heading-promotion has a wide false-positive surface (lessons) → full Phase-5H regression required.

These are symptoms; fixing them while RC-1 is open is whack-a-mole and the papers stay FAIL. Defer until after the RC-1 decision.

---

## Verifier FALSE POSITIVES caught at HEAD (do NOT action — ~26% FP rate, cross-project R-0006)

- `jesp_2021` "**truncated — loses Study 3 + General Discussion + Conclusion**" → **FALSE.** All present (rendered L3397 `## 8. Study 3`, L4673 `## 9. General Discussion`, L4731 `## 10. Conclusion`; file is 5536 lines).
- `ip_feldman` "**missing `## Figures` section**" → gold-authoring artifact ("No figures present"), not a docpluck text-loss.
- `jesp_2021` / `collabra_77859` "**mojibake / curly-quote corruption**" → U+FFFD count = 0; verifier misread valid smart-quotes.

---

## Data gaps (not docpluck defects — surface to article-finder owner)

- **plos_med_1 canary has NO `reading` gold** (`ai-gold.py check` empty). The fixed-canary cannot be Phase-5d-verified until `article-finder generate-gold 10.1371/journal.pmed.1004323` runs. Blocks run-close (I6/I4).
- Canary `rotating_pool` size 2 == rotation_size 2 (no rotation). 3 papers (efendic, maier, xiao) still listed `still_to_onboard_before_use`.

---

## Proposed cycle order
1. **RC-1 Step 2** (per-band region-aware crop) — biggest blast radius (every two-column APA paper). Multi-session; behind the existing flag; word-preservation + AI-verify gated. **Needs user go-ahead.**
2. **B7 layout-channel sign recovery** — catastrophic silent stat corruption; narrower. **Needs user go-ahead on path.**
3. Generate plos_med_1 gold (article-finder) so the canary is honest again.
4. Symptom fixes (affiliation-heading demote, table-cell-in-body) — only after RC-1 lands.
