# Handoff — autonomous `/docpluck-iterate` run (APA-first), session 2

**Authored:** 2026-05-16. Picks up from `docs/HANDOFF_2026-05-15_iterate_apa_run_1.md`.
**Stop reason:** context budget — the user set "run autonomously until 60% context." 1 cycle shipped clean (v2.4.39); the APA corpus is **NOT clean — ~12 papers still FAIL.** Reported as an honest **PARTIAL** per rule 0e-bis. Full punch-list in §4.

---

## 1. State at handoff

| Item | Value |
|---|---|
| Library version | **v2.4.39** (tag pushed; `__init__.py` + `pyproject.toml` synced) |
| Prod `/_diag` | **v2.4.39 confirmed live** on Railway (library installed from the pin) |
| App pin | `docpluckapp` master `80cb49c pin: auto-bump docpluck library to v2.4.39` (auto-bump bot commits direct to master — no PR) |
| `NORMALIZATION_VERSION` | 1.9.5 · `TABLE_EXTRACTION_VERSION` 2.1.3 |
| 26-paper baseline | **26/26 PASS, 0 WARN** |
| Broad pytest | 1196 pass / **15 failed (all pre-existing snapshot drift — confirmed via git-stash round-trip, see §5)** / 0 new |
| AI-gold cache | unchanged from session 1 (15/18 APA `reading` golds registered; 3 content-filter-blocked) |

## 2. Cycle shipped this session (1)

| Cycle | Version | Defect | Layer |
|---|---|---|---|
| 7 | v2.4.39 | GLYPH — `<`-as-backslash corruption (efendic: 24 occurrences — `p < .001` read `p \ .001`, table p-cells `<.001` read `\.001`, Wiley DOI `13:1<1::` read `13:1\1::`) | shared `recover_corrupted_lt_operator` (W0c + cell_cleaning + render post-process) |

Cycle 7: 26/26 baseline, 0 new pytest failures, surgical verified diff (54 lines, all `\`→`<`), real-PDF regression test added (8 new tests), AI-gold verifier confirmed corruption gone with zero hallucination.

## 3. APA corpus status — 3 PASS / ~12 FAIL / 3 gold-blocked

- **PASS (3):** `jdm_.2023.10`, `korbmacher_2022_kruger`, `ziano_2021_joep` (unchanged from session 1).
- **FAIL (~12):** efendic, chan_feldman, chandrashekar, jdm_.2023.15, jdm_.2023.16, jdm_m.2022.2, jdm_m.2022.3, maier, ip_feldman, xiao, chen, ar_apa_j_jesp_2009_12_011. **efendic itself still FAILs** — cycle 7 cleared its `<`-corruption but the AI-gold verifier confirmed it still FAILs on the pre-existing defects in §4.
- **Gold-blocked (3):** `ar_apa_j_jesp_2009_12_010`, `..._012`, `jamison_2020_jesp` — Anthropic content filter blocks the gold-extraction subagent. Platform limitation.

## 4. Open queue — punch-list for the next session

The efendic v2.4.39 AI-gold verifier identified the residual defects precisely. Ranked:

| Group | Sev | Notes |
|---|---|---|
| **efendic standalone-minus residuals** | S0 | Standalone `2X.XX` minus-corrupted cells — `Mchange = 20.14` should be `−0.14`, `21.01`→`−1.01`, `20.62`→`−0.62`. The verifier found these in **body prose AND every negative table B-coefficient/CI**. `recover_corrupted_minus_signs` only handles bracketed pairs (descending-CI rule) and `r = 2.X` — standalone `= 2X.XX` cells are genuinely ambiguous (a literal mean could be `20.14`) and need column/context-aware logic (e.g. recover only when the same paper already has confirmed `2`→`−` corruption nearby). **C2 — next cycle target.** |
| **SECTION-ASSEMBLY** (G5 + HALLUC-HEAD) | S1 | `##` headings attach to the wrong paragraph; `## Results` over Method prose; numbered subsections demoted to body text; mid-sentence fragments promoted to false `##` headings. Hits 6 of 7 swept papers. C2-C3. |
| **TABLE** flattening/destruction | S0/S1 | Flat `unstructured-table` blocks, dropped header rows, two-tables-merged (efendic Table 4 absorbs Table 5), column-fusion (`0.15[-0.88, -0.29]<.001` — CI/SE/p welded). Blocks jdm15/16/m3 (closest-to-PASS). C3, needs design. |
| **FIG** caption defects | S2 | Double-emission, truncation, body-prose welded into captions (efendic Figures 1/4/5). |
| **COL** column-interleave | S0 | chan_feldman, chandrashekar — reading-order scramble. C3. |
| **GLYPH 011** `−`→deleted | S0 | pdftotext drops U+2212 entirely; unrecoverable from text channel — needs layout-channel glyph identity. Escalate. |

Plus: **15 pre-existing pytest failures** (§5) — a `tests:` regen cycle. And the **3 gold-blocked APA papers**.

**Recommended next pickup:** (1) efendic standalone-minus residuals (S0, finishes efendic's GLYPH cluster); (2) SECTION-ASSEMBLY (widest blocker); (3) TABLE flattening (clears the closest-to-PASS jdm papers). COL + 011-minus are C3/escalate.

## 5. Pre-existing pytest failures (15 — carry-forward, confirmed)

Confirmed pre-existing this session via a **git-stash round-trip**: stashing the cycle-7 changes and re-running the same 15 node-ids at v2.4.38 produced the identical 15 failures with identical names. Cycle 7 introduced zero. All Bucket-2 test-fixture drift (not library bugs): 12× `test_v2_backwards_compat::test_extract_pdf_byte_identical` (raw-`extract_pdf` snapshots predate pdftotext version skew — `extract_pdf` does not run `normalize_text`, so the W0c step provably cannot affect them), 2× `test_sections_golden`, 1× `test_request_09`. A standalone `tests:` regen cycle — verify new output vs AI-gold before regenerating with `DOCPLUCK_REGEN_GOLDEN=1`.

## 6. Process notes

- **Glyph-fix 3-channel pattern applied proactively.** Cycles 2/4/6 each rediscovered that a glyph corruption reaches the rendered .md through three channels (normalize body / Camelot cells / render post-process). Cycle 7 applied the shared-helper-at-all-three-channels pattern from the first edit — the cycle-6 PROPOSED AMENDMENT working as intended. It remains a pending SKILL.md Phase 4 amendment awaiting user review.
- **Tier 2 / Tier 3 verification constraint.** The local FastAPI service ran v2.4.19 and restarting it during an unattended run is intrusive; the prod `/extract` endpoint is authenticated (401 without an API key). Tier 3 was verified via prod `/_diag` (v2.4.39 confirmed, library installed from the pin) — the same constraint session 1 documented. Tier 1 == Tier 3 for library output is structural (prod imports the identical tagged release).

## 7. Stop reason

Context budget — the user instructed "run iterations autonomously until 60% context." 1 cycle shipped clean (v2.4.39, prod-verified). The APA corpus improved (efendic's `<`-corruption cleared) but is **not clean — ~12 papers still FAIL**, blocked by the efendic standalone-minus residual (S0), the section-assembly cluster (S1, C2-C3), and table-structure flattening (C3). Reported as an honest **PARTIAL** per rule 0e-bis. The next session resumes from §4.
