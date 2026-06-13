# docpluck vs liteparse — fair benchmark (2026-06-12)

## Why this exists

ScienceArena's public leaderboard showed **liteparse** (run-llama/liteparse) topping
`pdf-section-structure-v1` and `pdf-text-fidelity-v1` and beating docpluck, while
scoring ~0 on tables. This doc records a **version-current, task-symmetric** re-run of
the *same* ScienceArena deterministic scorers, plus two real-paper probes the arena
doesn't run. Conclusion up front:

> **Once docpluck is benchmarked at its current version on identical task sets,
> docpluck ≥ liteparse on every axis — sections, text fidelity, and tables.** The
> published "liteparse wins" was an artifact of (a) a stale docpluck pin (v2.4.79),
> (b) docpluck being scored on 30 extra hard real-paper tasks liteparse never ran,
> and (c) liteparse's section score actually being a ScienceArena-authored regex that
> overfits clean synthetic headings.

Companion: `ScienceArena/HANDOFF_2026-06-12_sciencearena_accuracy.md` (the arena-side
measurement fixes).

## What liteparse actually is (verified, not blog-derived)

- **v2.0.8**, **MIT license** (`License-Expression: MIT`); a Rust extension
  (`_liteparse.*.pyd`) over a bundled `pdfium.dll` (PDFium = permissive BSD/Apache).
  **Zero Python dependencies**; installs as a 7.7 MB prebuilt wheel; clean on Windows.
  Status: **Beta**.
- API: `LiteParse(...).parse(pdf_bytes) -> ParseResult` with `.text` (full doc) and
  `.pages[].text_items[]` (each a `TextItem(text, x, y, width, height, font_size,
  confidence)`). Optional Tesseract OCR (off for our runs — docpluck never OCRs, so
  `liteparse-no-ocr` is the apples-to-apples variant).
- **liteparse has no section or table extraction of its own.** It emits reading-order
  text + per-glyph geometry. ScienceArena's `liteparse-sections-heuristic` /
  `liteparse-tables-heuristic` are *arena-authored* bbox/regex heuristics layered on
  that output — not liteparse features.

License is therefore **not** a blocker (unlike PyMuPDF/AGPL). It bundles PDFium, which
docpluck already pulls transitively via `pypdfium2`.

## Method

ScienceArena lives locally; it already ships in-process adapters for both tools and
**deterministic** scorers (no LLM judge / Elo):
- text-fidelity `primary = 0.5·Levenshtein + 0.5·token_F1` vs gold (best of
  preserve-greek / ascii-greek profiles); plus footnote recall.
- sections `primary = 0.5·label_F1 + 0.5·heading_F1` (micro-F1 over canonical-label
  and normalized-heading multisets).
- tables `primary = 0.4·detection_F1 + 0.4·cell_F1 + 0.2·struct_agree`.

Re-run in the arena `.venv` with `docpluck` installed editable from this repo
(**v2.4.84**) and `liteparse` **2.0.8**. Two extra real-paper probes use the same
scorers against AI-multimodal-read gold (ground-truth-is-AI rule), scripts in
`ResearchPlatforms/_scratch/{apa_section_bench,pmc_text_bench}.py`.

## Results

### 1. Synthetic split (ScienceArena `revealed`) — current versions

| Arena | docpluck | liteparse | winner |
|---|---|---|---|
| **Sections** | **0.890** (label 0.881 / head 0.900) | 0.767 (label 0.767 / head 0.767) | **docpluck +0.123** |
| **Text fidelity** | **0.865** (std) / 0.856 (acad) — lev 0.841, tok 0.888 | 0.852 — lev 0.795, tok 0.909 | **docpluck +0.013** |
| **Tables** | **0.467** (detection 1.0, cell 0.0 on 2 synth) | 0.000 (misses both) | **docpluck** |

Text shape is informative: liteparse has higher token-F1 (PDFium keeps more whole
words) but **lower Levenshtein** (spatial spacing/order hurts character fidelity);
docpluck's pdftotext is cleaner per-character. Net `primary` favors docpluck.

### 2. Real APA / psychology sections (docpluck's design target, L-005)

6 real replication papers (PSPB, JESP×2, CRSP, JOEP, Collabra), AI-multimodal-read
gold, scored with the arena section scorer:

| Paper | docpluck | liteparse-heuristic |
|---|---|---|
| ip_feldman_2025_pspb | 0.668 | 0.200 |
| chen_2021_jesp | 0.702 | **0.000** |
| jamison_2020_jesp | 0.731 | **0.000** |
| xiao_2021_crsp | 0.668 | 0.667 |
| ziano_2021_joep | 0.646 | 0.600 |
| maier_2023_collabra | 0.604 | 0.364 |
| **mean** | **0.670** | **0.305** |

This is the decisive datapoint. liteparse's section heuristic only matches headings
that are *exactly* `Method`/`Results`/… on their own line, so it **collapses to 0.000**
on real APA papers whose headings are numbered ("6.2. Method") or renamed
("2. Experiment"). docpluck's layout-aware annotators handle them and **more than
double** liteparse. liteparse's synthetic section "win" does not generalize.

(Caveat: APA gold is major-section granularity from an AI read; absolute values are
indicative, but both tools are scored identically so the **relative** gap is sound.)

### 3. Real PMC text fidelity (gold-confounded — see handoff Finding 4)

The arena's 30 PMC "held-out" golds are **partial JATS excerpts** (e.g. 6,982 chars
of gold for a 10-page, 52k-char paper), so every full-text extractor scores low and
the metric mostly penalizes extracting the rest of the real paper:

| Paper | gold chars | docpluck primary | liteparse primary |
|---|---|---|---|
| PMC12081175 (10pp; degenerate gold) | 6,982 | 0.072 | 0.161 |
| PMC12648265 (17pp; fuller gold) | 27,046 | **0.634** | 0.565 |

On the less-degenerate paper docpluck wins (0.634 vs 0.565); on the degenerate one
both are floored by gold incompleteness. A full 30-paper aggregate was **not run to
completion**: liteparse's `parse()` **deadlocks when reused across many PDFs in one
long-lived process** (each call is ~0.1 s in isolation but the loop hangs after the
first paper — an independent liteparse robustness mark, and another reason not to host
it in the SaaS service process). The metric is gold-confounded regardless (handoff
Finding 4), so treat all PMC text numbers as unreliable until the arena gold scope is
fixed; they do not affect the conclusion, which rests on the synthetic, real-APA, and
table results above.

## Diagnosis — real win vs artifact

| Axis | liteparse "win" on leaderboard | reality |
|---|---|---|
| Sections | published 0.767 vs docpluck 0.559 | **artifact**: stale docpluck + arena regex overfit to synthetic; current docpluck wins 0.890 (synth) / 0.670 (real APA) vs 0.767 / 0.305 |
| Text fidelity | published 0.880 vs docpluck 0.691 | **artifact**: stale docpluck (v2.4.79) + docpluck scored on n=54 incl. 30 PMC vs liteparse n=24 synthetic; current/symmetric → docpluck 0.865 vs 0.852 |
| Tables | docpluck wins (liteparse 0) | **real & retained** — liteparse emits no tables by design |

There is **no axis on which liteparse genuinely beats current docpluck** on like-for-like
tasks.

## Is there anything to borrow? (prototype assessment)

No. The only place liteparse shows an edge is token-level word recall on clean
single-column text — but its overall text `primary` is *below* docpluck's pdftotext
(0.852 < 0.865), so adopting liteparse's reading-order would **regress** text fidelity,
violate L-001 (never swap the extraction tool for downstream gains), and add a native
wheel for no benefit. docpluck already ships `pypdfium2`, so even the "PDFium reading
order" idea is available in-tree if a future, signature-gated fallback ever proves
itself — but the current evidence does not motivate one.

→ **No docpluck code change is warranted by this investigation.** A forced borrow
would be a net regression. The actionable fixes are on ScienceArena's side (the
handoff) and were the real source of the misleading leaderboard.

## Integration ups / downs (summary)

**Ups:** MIT + PDFium (license-clean, unlike AGPL PyMuPDF); zero-dep self-contained
wheel; fast; deterministic; clean Windows install.
**Downs:** no sections/tables/footnotes of its own (docpluck's whole value-add); text
`primary` below docpluck; Beta maturity; adds a 7.7 MB native binary and a second
PDFium to the SaaS git-pin blast radius; nothing it does is both better-than-docpluck
and borrowable without regression.

**Recommendation: do not integrate or depend on liteparse; do not borrow from it.**
docpluck already meets or beats it on every measured axis. Fix the benchmark, not the
library.
