# TRIAGE 2026-06-08 — previously-untested manuscript sweep (APA-focus)

**Method:** 15 previously-untested papers located via article-finder; rendered at docpluck **v2.4.80**; AI-verified (sonnet subagents) against article-finder `reading` golds. **Integrity-gated** to papers whose cached PDF SHA == the gold's `source_pdf_sha256` (10/15 had a provenance mismatch — see bottom). Verified so far: **4 FAIL / 0 PASS** (collabra.37122, collabra.77859, j.jesp.2021.104154, pci.rr.100726; s41467 Nature pending).

This is the canonical work queue (per `project_triage_md_is_work_queue`). Two root-cause classes + a set of non-defects + an article-finder data-integrity gap.

---

## RC-1 — Two-column reading-order INTERLEAVE  ·  S0 × C4 (ARCHITECTURAL — needs user go-ahead)

**The dominant defect.** pdftotext serialises two-column pages by interleaving the columns; docpluck's column-correction (`extract_columns.py`, shipped in O5/v2.4.80) only triggers on the narrow *banded-reference* case, so general two-column **body** pages are still interleaved. Confirmed on **4/4** two-column papers:

- **Section-order scrambling** — j.jesp.2021.104154: **12+ section inversions** (§3 before §2, §5 before §4, §9.2/§9.4 before §9.1, Study-2 sub-results reordered); collabra.77859: Choice-of-Target / Overview / Study-intros displaced; collabra.37122: `## Conclusion` emitted *after* References + endmatter.
- **Paragraph continuity broken** — continuations displaced 30–50 lines, words split at the column break (`possi-`, `partici-`, `attrac-`, `in`+`tensity`).
- **Tables paired with wrong-column data** — collabra.77859: *all 5 tables* empty shells or wrong data (Table 2 block holds Table 3 content, etc.); j.jesp.2021: Tables 3/7/9-10/12/14 broken (unstructured fallbacks, empty shells, two tables merged into one 14-col HTML table).
- **Heading markers lost / spurious headings** — headings landing mid-column-merge render without `##`; row-labels promoted to spurious headings (`### Study`, `### Y-test experiment`).
- **⚠ Possible stat corruption** — collabra.77859 gold `M_age 59.3` → rendered `Mage 39.3` (digit 5→3). NEEDS diagnosis: pdftotext digit-glyph misread vs interleave displacement. If a real glyph misread this is a catastrophic meta-science class (silent stat corruption).

**This is the known deferred B4/R4/O5 class** (`docs/superpowers/specs/2026-06-07-ip_feldman-B4-R4-column-interleave-diagnosis.md`). The sweep's key strategic finding: **the impact is BROAD** — essentially every two-column APA paper, not just the ip_feldman/chandrashekar canaries. Real fix = region-aware column detection (segregate full-width bands from 2-col prose bands before column-correcting), extending the O5 `extract_columns.py` foundation. Multi-session; touches the core extraction reading-order path; **requires user go-ahead** (Phase 3: avoid C4 unless user-approved).

---

## RC-2 — Metadata / running-header leaks into body  ·  S1 × C1–C2 (SEPARABLE — fixable now)

Line-level metadata strips, **independent of column reading order** for the standalone-line subset. Confirmed across all 4 papers:

- **Running-header leak (standalone lines)** — j.jesp.2021: `J. Chen et al. / Journal of Experimental Social Psychology 96 (2021) 104154` ×10+ (Elsevier "Author et al. / Journal Vol (Year) ArticleNo" shape); collabra.37122: `Revisiting the Temporal Pattern of Regret…` ×3 (title-as-running-header). *(pci.rr `Reply to PCIRR S2…` ×2 is INLINE-merged with body → interleave-entangled subset, defer with RC-1.)*
- **Corresponding-author / affiliation footnote leak** — collabra.37122:37 (`a Corresponding author: …; gfeldman@hku.hk`); collabra.77859:40-41 (`a Shared first author b Corresponding author: …`); j.jesp.2021:46-53 (recommendation + email + dates block).
- **CC-BY license boilerplate in body** — collabra.77859:602-603.
- **Publication-history / "recommended for acceptance by…" lines** — j.jesp.2021.

These are general line-pattern strips keyed on metadata signatures (extends the v2.4.16 `_FRONTMATTER_LEAK` / P1 family + P0 running-header strip). Safe regardless of the RC-1 decision.

---

## Non-defects (gold-formatting-philosophy — NOT actioned)

docpluck is a faithful paper extractor; these are gold-authoring choices it doesn't (and shouldn't) reproduce:
- Markdown italic on statistics (`*t*`, `*p*`, `*if*`) stripped — docpluck does not convert font-italic → markdown italic.
- Blockquote (`>`) markers (pci.rr) — no reliable PDF signal for quote structure.
- `## Reply to Reviewer #N:` heading promotion (pci.rr) — non-canonical; promoting arbitrary `X:` lines is a wide false-positive surface.
- Em-dash `—` → `--` (pci.rr GL-1, confirmed lines 41/67) — LOW; verify pdftotext-layer vs a normalize step before deciding.

---

## Article-finder provenance gap (surface to AF owner — not a docpluck bug)

10/15 candidate papers: `cache-check` by DOI returns docpluck's **version-of-record** PDF, but the existing gold was produced by sibling skills (escicheck-iterate / citationguard) from a **different copy** (ESCIcheck `…print-nosupp.pdf` author/preprint). One DOI → two PDF copies; cache serves the VOR, gold linked to the preprint → verifying against the wrong copy yields false findings. Verification is gated on SHA match. The 7 genuinely-untested mismatches (collabra.23443/.32572/.57785, j.jesp.2020.104052, j.jesp.2022.104372, SPPS inaction-inertia 1948550619900570, rsos.250908) need **article-finder `generate-gold`** on the cached PDF to be tested with integrity. (efendic, ieee_access_2, maier are already-tested papers under alternate DOIs — excluded.)

---

## Proposed cycle order
1. **RC-2 cycle(s)** — separable metadata/running-header leak strips (safe, general, LEAVE-NOTHING-BEHIND). Real-PDF tests on collabra.37122 / collabra.77859 / j.jesp.2021.104154.
2. **M_age glyph diagnosis** — confirm 59.3→39.3 direction against PDF; fix if real glyph misread (could be its own cycle or RC-1-bound).
3. **RC-1** — pending user go-ahead (the decision below).
