# Spot check 02 — Pattern A fix shipped

**Run:** 2026-05-07. **Trigger:** Pattern A (Elsevier "Keywords-first") fix complete; standing by for next priority.
**Test status:** 103 pass + 2 skipped (was 100 + 2; +3 new tests for the fix).

---

## TL;DR

- ✅ Pattern A is fixed in [docpluck/sections/annotators/text.py](../../../docpluck/sections/annotators/text.py). Spaced-letter typography (`a b s t r a c t` → flattened to lone lowercase `abstract` line) is now detected as a canonical heading when fully line-isolated and followed by a paragraph.
- ✅ All 3 affected APA papers (ar_apa_j_jesp_2009_12_010 / 011 / 012) now have `abstract` sections. Paper 010 cleanly clears the strict bar; 011 and 012 have residual ⚠️ from two **new** issues (H + I) that the Pattern A fix exposed.
- 🔍 Two new issues filed in the backlog: **Issue H** (©Elsevier copyright trailer leaks into abstract) and **Issue I** (running-header tail in middle sections).
- 🔍 New **Pattern E** filed: papers with NO `Abstract` heading at all (Meta-Psychology, Collabra). The chandrashekar_2023_mp paper that was in the v1.6.1 known-good baseline turns out to fail strict-bar recall (no Abstract, no Introduction detected) — pre-fix and post-fix outputs are identical, so this is a pre-existing limitation, not a regression.

---

## Pattern A — verified

**The actual root cause** turned out to be simpler than the original hypothesis: Elsevier two-column PDFs render the abstract heading as `a b s t r a c t` with spaced lowercase letters (gray typography). pdftotext flattens the letter spacing, leaving a lone lowercase `abstract` line in the normalized text. The detector's Title-Case post-filter rejected it as body text.

**The fix:** Added `_is_fully_isolated_heading()` in [annotators/text.py](../../../docpluck/sections/annotators/text.py:96). A lowercase canonical heading is accepted when ALL of the following hold:
1. The heading word is the entire line (no other words after — rejects `abstract concept of fairness`).
2. Preceded by a blank line (or start-of-doc).
3. The next non-blank line starts with an uppercase letter — i.e. a real paragraph start. Rejects `abstract\nis a word that means…` (lowercase continuation = body wrap).

**Tests added:** 3 new tests in [tests/test_sections_v161_text_annotator.py](../../../tests/test_sections_v161_text_annotator.py): one positive (Elsevier abstract detected), two negative (body uses still rejected). All existing tests continue to pass — 103 / 103 + 2 skipped.

---

## APA corpus status after Pattern A fix

| Paper | Status | Notes |
|---|---|---|
| ar_apa_j_jesp_2009_12_010 | **PASS strict bar** | 9 ✅ + 1 ⚠️ (abstract has ©Elsevier trailer — Issue H) |
| ar_apa_j_jesp_2009_12_011 | ⚠️ borderline FAIL | New abstract section detected ✅, but: ⚠️ ©Elsevier trailer (Issue H), ⚠️ running-header in results tail (Issue I), unknown 2.1% (within tolerance) |
| ar_apa_j_jesp_2009_12_012 | ⚠️ borderline FAIL | New abstract ✅; ⚠️ ©Elsevier trailer (Issue H); unknown 2.3% (just over 2% tolerance — Issue G) |
| chan_feldman_2025_cogemo | OK structurally | (v1.6.1 baseline) |
| chandrashekar_2023_mp | ❌ FAIL | NO abstract / NO intro detected. **Same output pre-fix and post-fix** → pre-existing issue, not regression. Paper has NO `Abstract` heading at all (Meta-Psychology layout) → Pattern E |
| chen_2021_jesp | ❌ FAIL | Abstract is bloated (22.9% of doc) → no Introduction detected. Pre-existing; **same output pre/post-fix** |
| efendic_2022_affect | OK structurally | (v1.6.1 baseline) |
| ip_feldman_2025_pspb | OK structurally | (v1.6.1 baseline) |
| jamison_2020_jesp | ❌ FAIL | NO methods detected (intro absorbs methods); spurious results section from a table |
| jdm_.2023.10 | ❌ FAIL | Catastrophic extraction (1537 chars total) — Pattern D, upstream pdftotext issue |
| jdm_.2023.15 | ⚠️ borderline | One ⚠️ from running-header in results tail (Issue I) |
| jdm_.2023.16 | ⚠️ borderline | ~80 char Funding+Competing-interest bleed in discussion tail (Pattern B) |
| jdm_m.2022.2 | ❌ FAIL | Spurious supplementary section starting mid-sentence; funding bleed |
| jdm_m.2022.3 | ❌ FAIL | Abstract bloated (no Introduction detected) |
| korbmacher_2022_kruger | ❌ FAIL | Abstract still has ~700 chars of post-abstract front matter (Acknowledgments + license) — Pattern B variant |
| maier_2023_collabra | ❌ FAIL | 33.9% leading unknown — Pattern E (no Abstract heading) + Collabra-specific "Downloaded from" preamble |
| xiao_2021_crsp | ❌ FAIL | T&F "ARTICLE HISTORY" layout — keywords absorbs Intro+Methods (Pattern C variant) |
| ziano_2021_joep | ⚠️ borderline | Funding bleed in general_discussion tail (Pattern B, ~80 chars) |

**Score:** 1 clean pass, 4 ⚠️-borderline, 9 ❌ fail. (Plus 3 v1.6.1 baselines marked "OK structurally" — not re-graded against strict bar yet; chandrashekar reveals one of those baselines was actually broken.)

**Distance from convergence (3 consecutive first-try-clean):** 1 paper, then everything that follows fails on something.

---

## Issues backlog snapshot

See [sections-issues-backlog.md](../sections-issues-backlog.md) for full details. Active issues:

| ID | Title | Affected | Leverage |
|---|---|---|---|
| ✅ A | Elsevier "Keywords-first" lowercase abstract | (fixed 2026-05-07) | high — verified |
| B | End-of-paper sections bleed into Discussion | jdm_.2023.16, jdm_m.2022.2/3, korbmacher, ziano | high — recurs across psych |
| C | Catastrophic intro/abstract failure (heterogeneous) | jdm_m.2022.3, maier, xiao | mixed — each variant separate |
| D | Catastrophic pdftotext extraction | jdm_.2023.10 | low — likely 1 file |
| E | Papers with NO Abstract heading | chandrashekar, maier (also) | high — open-access journals |
| F | Methods missing in jamison (intro absorbs) | jamison_2020_jesp | low so far |
| G | Title-block prefix borderline >2% | 011, 012 (~2.1–2.3%) | low — within rubber band |
| H | ©Elsevier copyright trailer in abstract | 010, 011, 012 | high — ALL Elsevier two-col |
| I | Running-header tail in middle sections | 011, jdm_.2023.15 | high — ALL two-col |

Issue E + Pattern C share the same surface symptom (long unknown / bloated abstract) but different causes; need to be diagnosed separately.

---

## Recommended next priority

The two highest-leverage open issues are:

1. **Issue H + Issue I together** (Elsevier two-column hygiene). Fixing both lets ar_apa_j_jesp_2009_12_011 and 012 pass cleanly, AND will likely improve other Elsevier papers that show up in IEEE/AMA/ASA. ~Medium effort. Single normalize.py-level pattern matcher for `© NNNN Publisher All rights reserved.` and `<Author> / <Journal> <Vol> (<Year>) <pages>`.
2. **Pattern B** (end-of-paper bleed). Recurs in 5+ papers; clean fix is to extend the inline-prefix detection in [annotators/text.py](../../../docpluck/sections/annotators/text.py) to recognize `Funding. <text>`, `Competing interest. <text>`, `Author contributions. <text>` even without canonical line-shape.

Pattern E is harder (synthesis of an abstract marker without a heading anchor); recommend deferring until A/B/H/I land.

**Tell me which to do next:**

- **(H+I)** — one combined commit, normalize.py change, expected impact: 010/011/012 all pass + likely fixes recurring issue across Elsevier.
- **(B)** — separate commit, annotators/text.py change, expected impact: jdm_.2023.16, ziano clean up; partial improvement on jdm_m.2022.2.
- **(both, in that order)** — H+I first, then B; ~1 hour each.
- **(E first)** — high leverage but harder; only choose if you want to bias toward open-access journals.

