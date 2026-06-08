# Diagnosis — ip_feldman B4 (tables mid-body) + R4 (reading-order) are ONE root cause (2026-06-07)

**Bottom line (empirically verified, corrects the optimistic subagent estimates):**
The two "deferred canary tracks" on `ip_feldman_2025_pspb` — B4 (table content serialized
mid-body) and R4 (section-boundary reading-order displacement) — are **the same root cause**:
pdftotext column-interleaves **table-bearing two-column pages**, interleaving table
caption/headers/cells AND real body prose into one stream. **Neither is a safe single-cycle
fix.** Both need **region-aware column detection** — an architecture decision for the user.

This doc captures two diagnostic-subagent RCAs plus the orchestrator's empirical correction.

---

## What was confirmed

### Track A (B4 — tables serialized mid-body)
- Camelot DOES detect the tables (Table 2: 41 cells structured; Table 10: 12 cells but
  corrupt — absorbed adjacent-column prose into `<thead>`, so `_strip_phantom_camelot_tables`
  correctly drops the HTML, leaving a caption-only `### Table 10` block).
- The leak: the **linearized** table content stays in the section body text. The existing
  `render.py::_suppress_inline_duplicate_table_captions` only removes **italic** `*Table N.*`
  inline captions that **exactly** match the block caption. Two gaps surfaced:
  - Table 2's caption is emitted as **plain** text (not italic) and its content is
    **scattered** across the Introduction (rendered lines ~57, ~79, ~143), not a clean
    caption+trailing-cells block.
  - Table 10's inline caption is italic but **truncated** (`*Table 10. Intensity Estimates
    Regression Coefficients with*`) so it doesn't exact-match the block caption
    (`…with Outcomes (Extension).`).

### Track B (R4 — reading-order displacement)
- The column-correction infrastructure **already exists** (`docpluck/extract_columns.py`,
  wired in `extract.py` via `_detect_column_interleave_pages` → `splice_column_corrected_pages`).
- It does NOT fire on ip_feldman's problem pages because `_detect_2col_midline`'s
  word-center histogram (20 buckets × ~30pt) can't resolve the narrow ~17pt PSPB gutter
  (the gutter fits inside one bucket → no low-density valley → returns `None`).

---

## The orchestrator's empirical correction (why it is NOT single-cycle)

A line-start-x0 bimodal midline detector (the subagent's proposed minimal fix) was probed
against the real layout doc. **The bilateral gate blocks the target pages:**

| page (0-idx) | line-start right-cluster frac | proposed midline | **bilateral fraction** | gate verdict |
|---|---|---|---|---|
| 13 (Discussion) | 0.27 | 304 | **0.44** | REJECT (≥0.30) |
| 14 | 0.32 | 319 | **0.37** | REJECT (≥0.30) |
| 16 | 0.12 | 320 | 0.79 | REJECT (genuine table page) |

The bilateral gate (`extract_columns.py:140-151`) rejects any page where ≥30% of y-rows
have words on both sides of the midline — its PURPOSE is to protect genuine table pages
(amle_1 table pages run 38-66% bilateral) from being garbled by column-mode. ip_feldman's
problem pages have a **table coexisting with two-column prose**, so they read as 0.37-0.44
bilateral and are (correctly, by the gate's current logic) rejected. So:
- A line-start detector alone does NOT fix ip_feldman — the gate blocks it.
- **Lowering the bilateral threshold to admit these pages would risk garbling real
  table pages corpus-wide** (the gate was calibrated specifically against amle_1).

And the B4 leak can't be safely patched render-side either: the table content is
**interwoven with real prose** (e.g. rendered line 1349 `no support, we only summarized
interactions that were supported and documented below p < .05` sits between Table 10's
caption and its column headers/values). A "drop caption + trailing cell-shaped lines"
suppressor would risk **dropping that real prose — a TEXT-LOSS (rule 0a) violation**.

---

## The real fix (architecture decision for the user)

**Region-aware column detection.** Before deciding column-mode for a page, segregate the
page into vertical REGIONS: a full-width table region vs a two-column prose region. Apply
column-correction only to the prose region(s); leave the table region to Camelot. This:
- lets the prose region be column-corrected even when a table elsewhere on the page would
  otherwise trip the whole-page bilateral gate;
- keeps the table region out of the linear body stream so B4 stops leaking;
- fixes BOTH B4 and R4 on ip_feldman at the root (and any mixed table+column page).

Design sketch (respecting CLAUDE.md: pdfplumber MIT only, conditional fallback, no tool swap):
1. Detect horizontal band boundaries on the page (y-ranges) where the layout switches
   between full-width (table/figure) and two-column (prose) — e.g. via row-bilateral runs:
   contiguous y-bands that are bilateral = table band; unilateral-alternating = prose band.
2. Run the existing `_crop_and_extract` column logic per prose band (cropping x AND y),
   concatenate bands top-to-bottom, leaving table bands as-is (Camelot owns them, and the
   body text for those y-bands is suppressed).
3. Re-derive the column midline from the prose band's line-starts (not the whole page,
   which the table contaminates).

Effort: multi-session. Regression surface: every two-column paper (chandrashekar B6 canary,
amle_1, JAMA, all PSPB/JESP). Gate hard on the 26-corpus baseline every iteration.

---

## Implementation started (2026-06-07, cycle 5) — validated band-detector prototype

User approved starting the region-aware architecture. Foundation built + **empirically
validated against ip_feldman's real layout**, but **deliberately NOT wired into the live
extraction pipeline** — a half-tuned reading-order change would risk silent corpus-wide
corruption that the char-ratio corpus gate cannot catch (per the skill: char-ratio/Jaccard
are blind to "right words, wrong order"). The live wiring + tuning + full corpus+AI gating
is the next focused session.

### Key insight discovered: a vertical empty-gutter strip beats the bilateral gate

The current whole-page **bilateral gate** (`extract_columns.py:140-151`, reject if ≥30% of
y-rows have words on both sides of the midline) **misclassifies genuine 2-column prose
pages with aligned baselines**. ip_feldman page 14 reads 0.37 bilateral (would be REJECTED)
yet has a clean full-height gutter at x=314 — it is real 2-col prose. A **gutter-strip
detector** (is there a central x-interval that NO word crosses across the band's height?)
gets page 14 right, and correctly finds NO full-page gutter on page 13 (Discussion) because
that page is banded (table band + prose bands). **The gutter-strip check should replace or
augment the bilateral gate.**

### Validated prototype (page map + band detector)

Page map (ip_feldman, 0-indexed) — current hist-path fires on only page 18; a line-start /
gutter detector would newly handle the pure-prose 2-col pages; the table-bearing pages need
banding:

```
pg words hist  ls_mid bilat  verdict
 0  540   -    319    0.27   prose (title/abstract page — handle with care)
 1  903   -    304    0.17   pure 2-col prose  ✅ single clean gutter band @299
 9  914   -    304    0.24   pure 2-col prose
11  314   -    248    0.26   pure 2-col prose
 5  742   -    304    0.39   MIXED (table+prose)  → needs banding
 8  482   -    244    0.33   MIXED → banding
10  472   -    290    0.42   MIXED → banding
12  321   -    244    0.35   MIXED → banding
13  595   -    304    0.44   MIXED (Discussion+Table 10) → banding
14  799   -    319    0.37   pure 2-col prose ✅ single clean gutter band @314 (bilateral-gate FALSE reject)
17  735   -    305    0.31   MIXED → banding
18  826  321    -     -      hist-path already fires
```

Band-detector prototype (validated: page 1 → one prose band mid=299; page 14 → one prose
band mid=314; page 13 → correctly splits into table/prose bands, though sparse-table bands
produce spurious gutter midlines (397, 278) that the refinement below must reject):

```python
TOL = 5.0
def _widest_empty_strip(words, lo, hi, min_w=8.0):
    """Widest x-interval in [lo,hi] crossed by no word [x0,x1]; (center,width) or None."""
    occ = sorted((max(w['x0'],lo), min(w['x1'],hi)) for w in words
                 if min(w['x1'],hi) > max(w['x0'],lo))
    best=None; cur=lo
    for a,b in occ:
        if a>cur and (a-cur) >= (best[1]-best[0] if best else 0): best=(cur,a)
        cur=max(cur,b)
    if cur<hi and (hi-cur) >= (best[1]-best[0] if best else 0): best=(cur,hi)
    return ((best[0]+best[1])/2, best[1]-best[0]) if best and (best[1]-best[0])>=min_w else None

def _column_bands(words, W, H):
    """Segment page rows into bands sharing a central gutter (prose) vs none (table).
    Greedy: extend a band while a central empty strip persists; close+reset when a row
    crosses the center."""
    from collections import defaultdict
    rows=defaultdict(list)
    for w in words: rows[int(round(w['top']/TOL)*TOL)].append(w)
    ykeys=sorted(rows); lo,hi=0.30*W,0.70*W; out=[]; cur=[]
    def flush():
        if not cur: return
        ws=[w for k in cur for w in rows[k]]; st=_widest_empty_strip(ws,lo,hi)
        out.append((cur[0],cur[-1],'prose' if st else 'table', st[0] if st else None,len(cur)))
    for k in ykeys:
        if _widest_empty_strip([w for kk in cur+[k] for w in rows[kk]],lo,hi): cur=cur+[k]
        else:
            if cur:
                flush(); cur=[k]
                if not _widest_empty_strip(rows[k],lo,hi): out.append((k,k,'table',None,1)); cur=[]
            else: out.append((k,k,'table',None,1)); cur=[]
    flush(); return out
```

### Refinements required before live wiring (next session)
1. **Center-constraint the gutter:** require the strip center within ~[0.42W, 0.58W]
   (257–355pt for W=612) so sparse-table bands don't yield bogus midlines (397, 278).
2. **Minimum band height:** a prose band must span ≥ N rows (e.g. ≥4) to be column-corrected;
   1-row "prose" bands are noise.
3. **Midline consistency:** within a page, real prose-band gutters cluster (~299–314);
   reject outlier midlines.
4. **Banded crop-extract:** extend `_crop_and_extract` to crop BOTH x (by band midline) and
   y (by band y-range), per prose band; concatenate bands top-to-bottom; leave table bands
   as original linear text (and suppress their body duplication once Camelot owns them — the
   B4 half).
5. **Replace/augment the whole-page bilateral gate** with the gutter-strip check (page 14
   false-reject above).

### Gating plan (mandatory, every iteration)
- 26-corpus baseline (`scripts/verify_corpus.py`) — catches gross regressions.
- **AI-audit of every 2-column paper** (ip_feldman, chandrashekar_2023_mp [B6 canary],
  chan_feldman, the JESP/PSPB family) — the ONLY check that catches reading-order scrambles
  (char-ratio is blind to word-order). Keep a change ONLY if all stay PASS.
- Add real-PDF tests asserting ip_feldman's Discussion opens with Discussion prose (not the
  Table-9 footnote) and Table 2/10 content no longer appears in body.

## CRITICAL design constraint proven empirically (2026-06-07): NO whole-page shortcut — banding is mandatory

A whole-page gutter-strip detector (`_detect_2col_midline_gutter`: widest empty x-interval in
[0.42W,0.58W] across ALL page words; bypass the bilateral gate when found) was implemented and
probed live, then **reverted** — it is UNSAFE. Result on ip_feldman (newly firing pages):

```
pg gutter newlen  note
 1   299   5860   genuine prose ✅
 4   314   5549   genuine prose ✅
 7   299   5375   genuine prose ✅
 9   299   5738   genuine prose ✅
10   306   3112   ⚠ TABLE page mis-fire (short output — table has a coincidental center gap;
                    whole-page column-crop splits the table wrongly)
14   314   5299   genuine prose ✅ (this is the one the bilateral gate falsely rejects)
15   299   5989   genuine prose ✅
16   314   5719   genuine prose ✅
17   299   5511   prose-ish
13    —      —    correctly NOT fired (no full-page gutter — needs banding)
```

**The killer: a table page can have a coincidental empty center band** (cells straddle the
centre with a gap), so a whole-page gutter fires and column-crops the table wrongly (page 10,
3112 chars). And it CANNOT be filtered by re-adding the bilateral gate: genuine prose (page 14,
0.37 bilateral) and the table page (page 10, 0.42 bilateral) are too close to separate with any
threshold. **There is no whole-page classifier that admits page 14 and rejects page 10.** The
discriminator must be applied PER Y-BAND (the prose bands have a gutter; the table band does
not), i.e. the **banded** approach in the refinements above is not optional — it is the only
safe design. The whole-page `_detect_2col_midline_gutter` shortcut is a dead end; do not
re-attempt it.

## Status
- ip_feldman canary findings #3/#4 (Table 2/Table 10 B4) and #5 (Discussion R4) remain
  OPEN/deferred in the ledger. They are NOT regressions; they are this known root cause.
- Subagent raw RCAs (Camelot B4, R4) are in the session transcript (agentIds
  ab97a65fdc17ba56b, ab9470f2bbf13e4d3) — both correct on detection facts, both
  over-optimistic on the bilateral-gate interaction (corrected above).
- **Decision needed from user:** approve the region-aware column-detection architecture
  (multi-session) as the next track, or keep these deferred.

## UPDATE 2026-06-07 (resume) — the SEPARABLE subcase shipped in v2.4.80 (O5), WITHOUT violating the "no whole-page shortcut" rule

The citationguard O5 case (`chen_2021_jesp` p19, `jamison_2020_jesp` p9 — reference entries
stranded above their own `References` heading) shipped a fix in v2.4.80. It **uses**
`_detect_2col_midline_gutter` — the function the section above calls "a dead end; do not
re-attempt." This is **not** a re-attempt of the unsafe design; read carefully:

**Why the "dead end" verdict stands and is not contradicted.** That verdict is about applying
the gutter shortcut **UNCONDITIONALLY to every page** — which mis-fires on table pages with a
coincidental center gap (ip_feldman p10 → garbled 3112-char crop) and cannot be rescued by the
bilateral gate (p10 0.42 vs p14 0.37 are inseparable whole-page). All true; still true.

**What v2.4.80 does differently — three independent confinements, none present in the reverted
probe:**
1. **Inversion-only entry.** The gutter detector runs ONLY on pages flagged by
   `_detect_reference_inversion_pages` (≥3 reference-entry lines above their own `References`
   heading). ip_feldman's table pages (10, 13, …) are NOT reference-inversion pages, so the
   gutter never runs on them. Empirically: the inversion detector fires on **exactly 2 of the
   101-paper corpus** (chen p19, jamison p9); ip_feldman gets `(no reorder)`.
2. **Center-constrained gutter** (spec refinement #1, now implemented): the strip center must
   lie in [0.40W, 0.60W], rejecting the off-center sparse-table "gutters" the probe hit.
3. **Word-preservation guard.** The re-extraction is accepted only if it preserves the page's
   substantial-word multiset (alphabetic tokens len ≥2). The p10-style garbling crop (3112
   chars, words lost) would be REJECTED and the page left untouched. A pure reorder can never
   drop or fabricate text (rules 0a/0b).

So the shortcut is safe **for the separable layout only** (table band above a 2-col reference
band whose gutter survives full-height), reached only through the inversion gate, and
backstopped by the word guard. The **interwoven** layout (ip_feldman B4/#3/#4, R4/#5) still has
NO surviving full-height gutter and still needs the per-y-band `_column_bands` architecture
prototyped above — that remains OPEN.

**Gating done:** 26-corpus baseline 26/26 PASS; 32 existing column tests + 5 new real-PDF tests
(`tests/test_o5_reference_inversion_real_pdf.py`); chen 0 stranded / 101 alphabetical-ordered
refs; jamison 0 / 37; ip_feldman + 98 others unchanged. Shipped in `extract_columns.py` +
`extract.py`. Version 2.4.79 → 2.4.80.
