
## Stripping load-bearing front-matter metadata exposes pre-existing wrapped-title duplicates (2026-05-26 Cluster E revert)

**What:** Cycle 4 of run 11 added line patterns to strip bare article ID (`1327169`) + article-type code (`research-article2025`) at top of PSPB-layout docs. Patterns smoke-tested clean (zero false positives across 20 cases). Render showed top-of-doc metadata correctly gone — but introduced `### Title duplicate` as wrapped multi-line text immediately under the H1. Root cause: pdftotext emits the title TWICE on PSPB layouts (main + running-header copy in column 2). The metadata lines were absorbing/separating the duplicate so it never reached `_promote_isolated_titlecase_subsection_headings`. Without them, the wrap candidate is now isolated and gets promoted.

**How to detect:** any metadata-strip cycle where the BEFORE render had multi-line text just under the H1 (before the author byline) needs a wrapped-title-duplicate check AFTER the strips. Compare H1 token set vs the next 5-10 non-blank lines' token sets — if there's high overlap, the lines under the H1 are likely a duplicate that the metadata block was hiding.

**Fix:** strip metadata + install a wrapped-title-duplicate detector in the same change. Don't ship the strip alone. The duplicate detector should match a paragraph-block under the H1 whose concatenated text equals the H1 modulo whitespace (or whose tokens are a high-overlap subset). Run AFTER the strips, BEFORE `_promote_isolated_titlecase_subsection_headings` so the wrap doesn't get promoted to `### `.

**File:** `docpluck/normalize.py::_FRONTMATTER_LEAK_LINE_PATTERNS` had the `_ARTICLE_TYPE_CODE` + `_BARE_ARTICLE_ID` additions reverted; the safer `Article reuse guidelines:` leaf-node P0 pattern was kept (it's not load-bearing).

## Subsection-chain promotion needs (a) parent-section blacklist AND (b) strict-adjacent backward walk (2026-05-26 Cluster A-ter)

**What:** Stacked Method subsections (e.g., `## Method` immediately followed by `Design and Procedure` + blank + `Power Analysis and Sensitivity Test` + blank + body) were not being promoted to `### ` headings because the existing `_promote_isolated_titlecase_subsection_headings` cell-region reject + sibling-label reject correctly reject each candidate individually but can't see across the chain to confirm "this is a real stacked subsection set." The chain detection helper (`_is_subsection_chain_member`) closes that gap.

**Two safety guards are mandatory:**
1. **`_CHAIN_REJECT_PARENTS` blacklist** — when the chain's parent is `## Author Contributions` / `## CRediT` / `## Funding` / `## Acknowledgments` / etc., the candidates underneath are list items (CRediT roles, ORCID names, funding agencies), NOT subsection headings. Walking back to find the parent label and rejecting these is essential — otherwise chan_feldman's "Methodology" CRediT role gets promoted to `### Methodology` (the existing `test_chan_feldman_no_credit_role_methodology_heading` test catches this regression).
2. **Strict-adjacent backward walk** (don't traverse through body) — a through-body backward walk over-promotes Table 4 row labels on ip_feldman ("Exploratory open-ended" / "Well-being measures and traits" / "IV1: estimation of negative emotional events" — these look like chain members under `## Method` if you walk through body). Strict-adjacent (only blank-separated candidates count) avoids this trap.

**How to detect:** after any chain-promotion change, render and grep both: (a) `^### Methodology` on chan_feldman (must be 0) and (b) `^### Exploratory open-ended` / `^### IV1:` on ip_feldman (must be 0).

**File:** `docpluck/render.py::_is_subsection_chain_member` (helper) + `_CHAIN_REJECT_PARENTS` frozenset (blacklist) + integration in `_promote_isolated_titlecase_subsection_headings` (bypass cell-region + sibling-label rejects when chain confirmed).

## Orphan affiliation wrap-tail needs a tight line-level pattern with 60-char length lookahead (2026-05-26 Cluster C-bis)

**What:** Cluster C's name-led-affiliation pattern in `_FRONTMATTER_LEAK_PARA_PATTERNS` matches the first line of a 2-line wrapped corresponding-author paragraph (`"Gilad Feldman, Department of Psychology, University of Hong Kong, Pok"`), but the wrap-tail (`"Fu Lam, Hong Kong SAR."`) survives because line-by-line iteration in `_strip_frontmatter_metadata_leaks` can't see across the boundary. The 2026-05-25 Cluster C run cleared finding #1 mostly but left this orphan.

**Fix shape:** `^(?=.{1,60}$) <1-3 title-case place tokens>, <region: title-case+all-caps OR all-caps+optional-zip OR title-case>\.\s*$`. The 60-char lookahead bounds the line length so legitimate body sentences ending with a "Place, Region" phrase (typically much longer) aren't absorbed. Position-gated to front-matter zone via the outer strip's 8000-char cutoff.

**File:** `docpluck/normalize.py::_ORPHAN_AFFIL_WRAP_TAIL`. Regression tests in `tests/test_normalize_metadata_leak_real_pdf.py` covering positive variants ("Berkeley, CA.", "Cambridge, MA 02138.", etc.) and negative shapes ("(Miller & Prentice, 1994).", citations, body sentences containing place names).

## CHANGELOG-documented public-API names must be in `__all__` (caught 2026-05-07, v2.0.0 release)

**What:** v2.0.0 CHANGELOG line "`Cell, Table, Figure, StructuredResult` TypedDicts and `TABLE_EXTRACTION_VERSION` re-exported from top-level `docpluck`" was inaccurate — `Cell` was importable via `docpluck.tables.Cell` but not from top-level `docpluck`. Caught by /ship Phase 3 cleanup against `docpluck.__all__`.

**Why:** When implementing a new public-surface CHANGELOG entry, it's easy to write the docs from intent ("we expose Cell, Table, Figure...") then only re-export the ones actually used by the orchestrator (extract_pdf_structured uses Table + Figure but doesn't return Cell directly — so Cell got missed in the import line).

**Fix:** Added `Cell` to `from .tables import` and to `__all__`. Added regression test `tests/test_v2_top_level_exports.py` asserting every CHANGELOG-documented v2.0 name is both importable AND in `__all__`.

**How to detect:**
1. After writing a CHANGELOG entry that mentions "re-exported from top-level <pkg>", run:
   `python -c "import <pkg>; print(set(<pkg>.__all__) ^ {<documented names>})"`
2. The symmetric difference should be empty (or only contain the legitimate non-public names).
3. The `tests/test_v2_top_level_exports.py` regression test is the durable version of this check.

## Hardcoded version-string assertions break every release-bump (caught 2026-05-09, v2.1.0 release)

**What:** v2.1.0 release bumped `SECTIONING_VERSION` 1.1.0 → 1.2.0 and `NORMALIZATION_VERSION` 1.6.0 → 1.7.0. Four tests had the OLD version strings hardcoded as bare equality assertions:
- `tests/test_sections_version.py::test_sectioning_version_is_v110` — `assert SECTIONING_VERSION == "1.1.0"`
- `tests/test_sections_public_api.py::test_sections_namespace_exports` — `assert SECTIONING_VERSION == "1.1.0"`
- `tests/test_cli_sections.py::test_cli_sections_json_output` — `assert payload["sectioning_version"] == "1.1.0"`
- `tests/test_d5_normalization_audit.py::TestVersionBumps` — `assert NORMALIZATION_VERSION == "1.6.0"` AND `assert report.version == "1.6.0"`

Plus three golden snapshot files (`tests/golden/sections/*.json`) had the version baked in as a JSON field, requiring `DOCPLUCK_REGEN_GOLDEN=1` to refresh.

**Why:** Each version-pin test was deliberately written to verify the constant is at the version the contributor expected — defensible as a tripwire. But that means EVERY release bump fails the full test suite until the pins are updated. The current pattern is a tax on every release rather than a meaningful invariant.

**Fix:** Updated all six call sites + 3 golden files to the new version. Renamed `test_sectioning_version_is_v110` → `test_sectioning_version_is_v120` so the function name doesn't lie about the assertion.

**How to detect (pre-tag):**
1. Before running the full suite post version-bump, grep the test tree:
   `grep -rn 'SECTIONING_VERSION\|NORMALIZATION_VERSION\|sectioning_version\|normalization_version' tests/ | grep -E '"[0-9]+\.[0-9]+\.[0-9]+"'`
2. Every match is a candidate for update. Update them in the same commit as the version bump so the release commit stays atomic.

**How to detect (durable):** Add a test in v2.2.0+ that asserts `SECTIONING_VERSION == docpluck.sections.SECTIONING_VERSION` (self-referential, never breaks) and replaces the hardcoded-version pin tests entirely. Deferred for now — the cost of updating 6 sites once per minor release is low enough that this isn't worth the complexity yet.

## Pdftotext serializes right-column metadata as orphan single-line paragraphs mid-Introduction (caught 2026-05-14, v2.4.16 release)

**What:** Four papers across four publishers (xiao APA/T&F, amj_1 + amle_1 AOM, ieee_access_2 IEEE) showed front-matter metadata (acknowledgments, license blocks, "previous version" notes, supplemental-data sidebars, truncated affiliations, running headers) bleeding mid-body in the rendered .md. The leak is invisible to char-ratio + Jaccard verifiers, to the 26-paper baseline regression gate, and to a 30-line eyeball check.

**Why:** pdftotext's reading-order serialization linearizes a two-column article by emitting the left-column (Abstract → Introduction body) first, then the right-column / inter-column metadata. The metadata fragments end up inlined as standalone single-line paragraphs between body paragraphs of the Introduction. pdftotext typically separates them from the body paragraph above with only a single `\n` (no blank line), so a `\n\n`-bounded paragraph-level view of the text absorbs the leak into the body paragraph and never sees it as a separate unit.

**Fix:** New `P1_frontmatter_metadata_leak_strip` step in `normalize.py` (NORMALIZATION_VERSION 1.8.4) operating at the **LINE level** (not paragraph level — that was a draft mistake) and position-gated to `max(8000, len(text) // 6)` chars. Plus three globally-safe additions to P0 (`_PAGE_FOOTER_LINE_PATTERNS`): bare uppercase running header (`^[A-Z]{2,}(?:\s+[A-Z]{2,}){0,3}\s+et\s+al\.?$`), T&F supplemental-data sidebar boilerplate, and truncated `Department of <X>, University of$` affiliation. Multi-sentence acknowledgments / license / correspondence / previous-version blocks stay in P1 with the position gate because they CAN legitimately appear in the late `## Acknowledgments` section.

**How to detect (next time):**
1. The leak shape: a single physical line (often very long — 200–700 chars), bounded by `\n` from a body paragraph above and `\n\n` from the next body paragraph below, that starts with a metadata-y opener.
2. Grep the rendered .md mid-body for: `^We (?:wish to )?thank `, `^Supplemental data for this article`, `^Department of [A-Z].*, University of\s*$`, `^[A-Z]{3,} et al\.?$`, `^This work is licensed under (a |the )?Creative Commons`, `^A previous version of this article was (?:presented|published)`, `^Correspondence concerning this article`.
3. **Never apply position-gated strips to the bare running-header class** — it recurs at every page break (`RECKELL et al.` shows up at 3% AND 18% of `ieee_access_2`'s rendered .md). Globally-safe patterns go in P0; only patterns with false-positive risk in the late Acknowledgments / Affiliations go in P1.

## Real-PDF regression tests must drive through the public library entrypoint, not the helper (caught 2026-05-14, v2.4.16 release)

**What:** A natural first instinct when writing the regression test for the P1 strip was to call `_strip_frontmatter_metadata_leaks(text)` directly with synthesized strings like `"Body.\n\nWe wish to thank X for feedback.\n\nBody 2."`. The handoff's rule 0d says every fix ships with a `*_real_pdf` test that exercises the **public** library entry point on an **actual** PDF fixture.

**Why:** The contract test against the helper passed in isolation, but a real pdftotext rendering of the same PDF revealed the leak appears separated by only a single `\n` (not `\n\n`), so the helper's paragraph-level view didn't isolate the leak. The contract test was a false-positive PASS: helper-correct, library-broken. The discovery only came from re-rendering an actual PDF and grepping the .md.

**Fix:** Per skill rule 0d, the regression test file is named `test_*_real_pdf.py` and uses `render_pdf_to_markdown(Path('../PDFextractor/test-pdfs/<style>/<paper>.pdf').read_bytes())` to drive the full pipeline. Contract tests with synthetic strings are useful as helpers but never substitute for a real-PDF regression test. Use `pytest.skip` when the fixture is unavailable locally (PDFs are gitignored per memory `feedback_no_pdfs_in_repo`).

**How to detect (next time):** If `bugs_fixed` in run-meta references a normalization-pipeline defect, grep the new tests for `render_pdf_to_markdown\|extract_pdf\b` AND `test-pdfs/` — a fix without that combination is a synthetic-only test and won't catch real pdftotext output quirks.

## Caption trim chain belongs in extract_structured, not figures/detect (caught 2026-05-14, v2.4.25 release)

**What:** v2.4.24 added a figure-caption running-header trim to `docpluck/figures/detect.py::_full_caption_text`. The trim was correctly implemented and passed unit tests calling `find_figures()` directly. But `render_pdf_to_markdown()` doesn't call `find_figures()` — its render path goes through `docpluck/extract_structured.py::_extract_caption_text`. Result: the v2.4.24 fix was completely invisible in rendered output. The cycle-9 ship-blocker (xiao Figure 2 caption with body prose absorbed) was still present in production for 24 hours after v2.4.24 was tagged.

**Why:** Two `_full_caption_text` / `_extract_caption_text` functions exist for similar purposes but feed different consumers. The naming similarity (`_full_caption_text` vs `_extract_caption_text`) hides the divergence.

**Fix:** v2.4.25 migrated the running-header trim plus three new trim functions (duplicate-label strip, body-prose boundary, PMC reprint footer) to `extract_structured.py::_extract_caption_text`. Now both render paths consume the trim chain.

**How to detect (next time):**
1. When adding a fix to any `docpluck/<module>/detect.py` or any helper named `_*caption*` / `_*table*` / `_*figure*`, grep for callers: `grep -rn "function_name" docpluck/ tests/`.
2. If `render_pdf_to_markdown` isn't in the call chain (transitively), the fix won't surface in rendered output. Add the fix to the consumer that IS in the chain (`extract_structured.py::_extract_caption_text` for caption text, `tables/cell_cleaning.py` for table rows, `render.py::_promote_*` post-processors for heading promotion).
3. **The regression test must drive `render_pdf_to_markdown(pdf_bytes)`** and assert on the rendered `.md` output, not on the helper's return value. Rule 0d strengthened: real-PDF tests go through the render entry point.

## Section.subheadings tuple is stored but not rendered (caught 2026-05-14, v2.4.26 release)

**What:** Initial Pass 3 relaxation for cycle 11 (admitting ALL-CAPS multi-word headings with no blank-before/after) correctly emitted heading hints from `annotate_text`. The hints reached `Section.subheadings` via `core.py:281`. But the rendered .md output had no `## METHOD` / `## RESULTS` lines — the `subheadings` tuple is **stored but never consumed** by `render.py`. Only canonical-labeled hints (resolving to `SectionLabel.methods` etc.) become `## ` rendered lines.

**Why:** Section.subheadings was added in v1.6.1 as a "in-section unrecognized headings" field for downstream consumers, but `render.py` was not updated to surface them. Smart list-vs-heading discrimination for weak text_pattern hints is deferred to v1.6.2+ per a comment in `core.py:99-103`.

**Fix:** v2.4.26 reverted the Pass 3 relaxation and added a render-layer post-processor (`_promote_study_subsection_headings` extended with `_ALL_CAPS_SECTION_HEADING_RE`). The post-processor operates on the FINAL rendered text, scanning every line and promoting matching ones to `## ` — no involvement of the section detector at all.

**How to detect (next time):**
1. When adding heading detection: write the regression test FIRST against `render_pdf_to_markdown(pdf_bytes)` and assert on rendered `## ` / `### ` lines. If the assertion fails after a fix that touched only the section detector, the fix is in the wrong layer.
2. Render-layer post-processors (`_promote_*` functions in `render.py`) are the right tool when the section detector's strict isolation constraints reject real headings that pdftotext flattened. They have access to the final rendered text and can be more permissive about context.
3. **Never modify `Section.subheadings` and expect it to render.** That tuple is metadata only. To surface a heading in rendered output, either (a) add a canonical label so it becomes a `Section`, or (b) add a render-layer post-processor.

## Camelot section-row labels (single-cell with parenthetical) are NOT continuation rows (caught 2026-05-14, v2.4.27 release)

**What:** Table 6 in `xiao_2021_crsp.pdf` has condition-group section-row labels like `Control (n = 339, 2 selected the decoy, 0.6%)` and `Regret-Salient (n = 331, ...)`. Camelot emits these as rows with one non-empty cell (the label) and all other columns empty. `_merge_continuation_rows`'s first-cell-empty + rest-has-prose path then merged them into the data row above, producing `<td>112/172<br>Regret-Salient (n = 331, ...)</td>`.

**Why:** The continuation-row signature (empty first cell + prose elsewhere) overlaps with the section-row signature (empty first cell + one prose cell elsewhere). The merge rule treated them identically.

**Fix:** v2.4.27 added `_is_section_row_label` guard early in the merge loop. A row is treated as a spanning section-row label (not merged) when exactly ONE cell is non-empty AND that cell is ≤ 200 chars AND matches `[A-Z][\w\-]*(?:\s+[\w\-]+)*\s*\([^)]*\b(?:n|N|M|SD|p)\s*[=<>]`.

**How to detect (next time):** When `_merge_continuation_rows` misfires, look for rows with EXACTLY one non-empty cell and a parenthetical statistical descriptor. The "exactly one cell" is the discriminator from a true continuation row (which has content in multiple cells matching the parent row's column structure).

## Cluster-detection prevents false-positives in chart-data trim (caught 2026-05-14, v2.4.28 release)

**What:** amj_1 figure captions contained flow-chart node text (`1. Bottom-up Feedback Flow 2. Top-down Feedback Flow 3. Lateral Feedback Flow`) and axis-tick labels (`7 6 Employee Creativity 5 4 Bottom-up Flow`) interleaved with the legit caption. A single occurrence of either pattern could be legitimate (`Study 1 in Figure 2`), so single-match regexes either over-trim legit captions or miss the real chart-data leak.

**Why:** The discriminator between "legit number in caption" and "chart-data leak" is *repetition*. Real captions reference one or two numbers in prose; chart-data appendages have 2+ axis-tick pairs or 3+ numbered-list items in close succession (typically within 100 chars of each other).

**Fix:** New `_find_chart_data_cluster(caption, pattern, min_matches, max_gap)` helper in `docpluck/extract_structured.py`. Slides a window through `pattern.finditer(caption)` results and returns the start of the FIRST cluster of `min_matches` consecutive matches where each adjacent pair is within `max_gap` chars. Matches at position < 20 are filtered to prevent `Figure N.` from self-anchoring.

**How to detect (next time):** When designing a chart-data / metadata trim, ask: "what's the false-positive case where one match is legit?" If you can construct one, switch to cluster detection. A single match should NEVER trigger a destructive trim.

## A3 lookbehind override: narrower follow-up rule, not relaxed original (caught 2026-05-14, v2.4.28 release)

**What:** A3's lookbehind `(?<![a-zA-Z,0-9\[\(])` blocks European-decimal conversion of `(0,003)` and `[0,05]` inside parens/brackets. This exclusion is necessary to protect statistical df forms like `F(2,42)` (must NOT convert to `F(2.42)`) and citation superscripts like `Smith1,3`. But it leaves legitimate parenthetical p-values uncorrected.

**Why:** Relaxing A3's lookbehind would break df-form protection. The right structure is a narrower follow-up rule with stronger guards.

**Fix:** New A3c step in `docpluck/normalize.py` runs AFTER A3. Pattern `0,(\d{2,4})` regardless of lookbehind. Leading-zero constraint makes the match unambiguous: df values never start with 0, citation superscripts never start with 0. `0,5` (single-digit after comma) is intentionally skipped — it's ambiguous between European decimal and range syntax.

**How to detect (next time):** When a normalization rule's exclusion is overly conservative, don't relax the original rule's lookbehind/lookahead — add a narrower follow-up step with stronger guards. Sequence matters: original first (protects the dangerous case), narrower follow-up second (recovers the false-negative).

## 2026-05-15 · USER DIRECTIVE — subagent parallelization + general-not-PDF-specific fixes

**What:** During the autonomous APA-first docpluck-iterate run the user gave two standing directives:
1. **Use subagents to optimize the whole process whenever possible** — re-statement of the 2026-05-14 directive (it had slipped: the orchestrator parallelized gold extraction but did broad-read reading, diagnostics, and per-paper verification serially inline).
2. **Every fix must be general** — serve all future PDFs, never a local quick-fix tuned to one PDF that could create issues for others. Any change must benefit the tool overall.

**Why:** docpluck is a meta-science tool over arbitrary academic PDFs across 9 publishers. (1) Iteration work is naturally parallel per-paper; serial inline work is slow and burns orchestrator context. (2) A fix keyed to one paper's quirk is brittle, doesn't generalize, and risks silent regressions elsewhere.

**Fix (encoded durably):** CLAUDE.md "Critical hard rules" gains the general-fix bullet. docpluck-iterate SKILL.md: Subagent-parallelization section upgraded to a MANDATE with a per-cycle self-check; Phase 4 discipline #2 = general-fix rule; hard rules 16 (general fix) + 17 (subagents); Verification Checklist gains both checks. Memories `feedback_use_subagents_aggressively` + `feedback_general_fixes_not_pdf_specific`.

**How to detect (next time):** Before any batch of 2+ independent units (renders, golds, verifications, broad-reads, diagnostics) — fan out to parallel subagents. Before shipping any fix — confirm it is keyed on a structural signature, not paper identity, and the 26-paper baseline confirms no regression.

## 2026-05-15 · Cycle 2 — a test can encode the bug; cross-channel glyph coverage

**What:** Fixing normalize.py's S0 step (math-italic Greek was transliterated to ASCII Latin — `𝜂`→`n`) surfaced two process lessons. (1) `test_normalization.py::TestS0_SMP::test_math_italic_greek_eta` literally asserted `"n" in result  # eta maps to 'n'` — the test encoded the corruption as expected behavior, so the correct fix turned it red. (2) The same corruption appeared in three channels — body text (normalize S0), table cells (Camelot, bypasses S0), and figure/table captions (bypass both) — so an S0-only fix was incomplete.

**Why:** A test written against buggy output silently protects the bug. And a normalization defect rooted in glyph handling surfaces in every channel that carries text, not just the body.

**How to detect (next time):** When a fix targets a normalize/extract step, grep that step's existing tests FIRST — a test may be asserting the very behavior you're correcting; update it in the same cycle. And when a glyph/encoding defect is found, enumerate every channel that emits text (body, table cells, captions, raw_text, structured JSON) and confirm the fix — ideally a shared helper — covers all of them (Phase 0.8 cross-output check).

## 2026-05-16 · Cycle 7 — `<`-as-backslash glyph corruption (v2.4.39)

**What:** pdftotext maps the `<` comparison-operator glyph to a literal backslash on certain fonts. `efendic_2022_affect` rendered every `p < .001` as `p \ .001`, every table p-value cell `<.001` as `\.001`, and the legacy Wiley DOI `13:1<1::AID-BDM333` as `13:1\1::` — 24 occurrences. A new member of the same glyph-corruption family as math-italic-Greek (v2.4.34), `(cid:0)`-minus (v2.4.36), and `2`-for-minus (v2.4.38).

**Fix:** `normalize.py::recover_corrupted_lt_operator` — a backslash glued (optional single space) to a digit or a `.`-prefixed decimal is unambiguously a corrupted `<`. A literal backslash is never a legitimate prose character in extracted academic-PDF text and the renderer adds no markdown escapes, so the signature is safe. Wired into all three text channels from the start (W0c body step / `cell_cleaning._html_escape` / `render_pdf_to_markdown` post-process).

**How to detect (next time):** When a render shows a literal backslash, grep `\\s?\.?\d` — any backslash adjacent to a numeral is a corrupted `<`. Diagnose the channel by grepping the raw `pdftotext` output and the Camelot cell text separately (the corruption is in the pdftotext font layer). Glyph fixes ALWAYS need all three channels — body / Camelot cells / render post-process — via one shared helper.

**Pytest pre-existing-failure triage:** a broad pytest returning N failures must be triaged before fixing — `git stash` (working tree back to the last release), re-run the same N node-ids, and confirm identical failures. If identical, they are pre-existing (the cycle introduced none); classify each as real-bug / test-fixture-drift / env-flag. Cycle 7's 15 failures were all test-fixture drift (snapshot regen), zero introduced.

## 2026-05-16 · Cycle 8 — disambiguate a corrupted token via a co-reported invariant-bound quantity (v2.4.40)

**What:** efendic's `2`-for-U+2212 minus corruption left bracket-less point estimates corrupt (`20.26` for `−0.26`) after the v2.4.38 bracketed-CI fix. A standalone `2X.XX` is locally ambiguous — it could be a literal mean of twenty-something. The fix (`normalize.py::recover_minus_via_ci_pairing`, W0d) pairs each `2X.XX` token with the confidence interval reported in the SAME record (`<tr>` table row or text line) and recovers it only when the de-corrupted `−X.XX` lands inside the CI while the literal `2X.XX` does not.

**Why:** A point estimate always lies inside its own reported CI — a structural invariant of statistics, not a heuristic. So the CI co-located with the estimate resolves the ambiguity with zero false-positive risk: a genuine literal (e.g. mean age `23.45` with CI `[22.1, 24.8]`) is *consistent* with its bracket, so the recovery rule does not fire. The only mis-fire path — literal outside its bracket while the negative is inside — is a stats record whose estimate is not in its CI, which never occurs.

**How to detect (next time):** When a corrupted token is locally ambiguous, do NOT reach for paper-identity or domain heuristics ("a change score is small"). Look for a co-reported quantity bound to the token by a mathematical invariant — estimate∈CI, probability∈[0,1], SD≥0, percentages summing to 100 — and use that invariant as the discriminator. If no such co-reported quantity exists (e.g. a standalone `Mchange = 2X.XX` with only an SE, or a contrast-coding footnote), the token is genuinely unrecoverable from the text channel — escalate to the layout channel, do not guess.

## 2026-05-16 · Cycle 9 — a too-strict heading regex demotes headings; reproduce before trusting the cost estimate (v2.4.41)

**What:** Numbered subsection headings (`5.1. Participants`, `5.3.3. Choice deferral`, `6.1.1. Replication: ...`) rendered as plain body text. The TRIAGE listed this G5 defect as C2 ("loosen section-detection thresholds"). Reproducing at HEAD showed the actual cause was a single regex: `render.py::_NUMBERED_SUBSECTION_HEADING_RE` had `\d+(\.\d+){1,3}\s+` — `\s+` immediately after the digits — so a number with a **trailing dot** (`5.1.`) never matched. A one-character `\.?` plus a `:` in the title char class fixed ~78 headings across 4 papers.

**Why:** The Cambridge/JDM and Elsevier journals number subsections `N.N.` *with* a trailing dot. The original regex was written for the `N.N ` (no-dot) style and silently rejected the dotted style — demoting every dotted subsection heading to body text.

**How to detect (next time):** When a TRIAGE item is costed C2/C3 ("loosen thresholds", "needs design"), still reproduce the defect at HEAD and inspect the *exact* failing input before trusting the estimate — the real fix is often one regex tweak, not an algorithm rework. For heading-detection regexes specifically: enumerate the real-world numbering typography (`N.`, `N.N`, `N.N.`, `N.N.N.`, with/without trailing dot, colons in titles) and test the regex against all of them; a heading regex that only accepts one style silently demotes every other style.

## 2026-05-16 · Cycle 10 — line-leading ISSN is a bulletproof strip anchor; check where an existing pattern anchors (v2.4.42)

**What:** The Elsevier page-1 footer (corresponding-author e-mail line + ISSN/front-matter/copyright line) was spliced into the Introduction body by pdftotext's page-boundary extraction. Two new W0 watermark patterns strip them. The pre-existing Issue-H copyright pattern (`^\s*[©Ó]\d{4}…All rights reserved`) did NOT catch the Elsevier line because that line starts with the journal ISSN (`0022-1031/© 2021 …`), not with `©`.

**Why:** An anchored strip pattern only catches the variant whose leading token it anchors on. The Elsevier ISSN/copyright line and the bare `© 2021 …` copyright line are the same logical artifact with different leading tokens — one pattern cannot cover both.

**How to detect (next time):** Before assuming an existing strip/watermark pattern covers a newly-found variant, read WHERE it anchors (`^\s*[©Ó]` anchors on the copyright glyph). If the new variant has a different leading token, it needs its own pattern. For publisher-footer lines, the journal ISSN `\d{4}-\d{3}[\dX]/` at line-start is a near-perfect anchor (no body prose or reference begins with an ISSN-slash) — pair it with a publisher/`rights reserved` keyword guard so a coincidental `NNNN-NNNN/` year range cannot match. For a metadata line that pdftotext wraps across multiple lines (a long multi-author e-mail list), do NOT use a single-line strip — match only the single-line (singular) form, or the strip will leave orphan continuation lines.

## 2026-05-16 · USER DIRECTIVE — ground-truth generation is delegated to article-finder, never self-generated

**What:** ArticleFinder's audit found docpluck-iterate (and escicheck-iterate) each carried a PRIVATE AI-gold-extraction prompt instead of using the shared `~/.claude/skills/article-finder/gold-generation.md` protocol. The same paper extracted by two divergent prompts produced two different `reading` golds. User directive: docpluck skills must use article-finder for ALL ground truth, never do extraction independently.

**Why:** One paper has exactly one ground truth. Multiple producers each with their own prompt = a fork, not ground truth — the same failure mode as canonical-key fragmentation. The fix is structural: one producer (`article-finder`), one protocol (`gold-generation.md`), one gold per paper. On a cache miss, consumers invoke `article-finder generate-gold <pdf>`.

**How to detect (next time):** If a docpluck skill (or any consumer skill) contains an extraction-prompt template, or dispatches a subagent to "read the PDF and produce a gold" — that is a fork. Ground-truth GENERATION belongs to article-finder alone; consumer skills only OBTAIN (`ai-gold.py check`/`get`) and CONSUME (verifier comparison) golds. A consumer-side verifier that compares the tool's output against the shared gold is fine — that is not generating ground truth. If the shared gold view lacks detail a consumer needs, enrich `gold-generation.md` (coordinated with article-finder), never fork a private prompt.

## 2026-05-16 · Cycle 11 — a demoted heading is wedged in prose, not floating in whitespace (v2.4.43)

**What:** Promoting single-level numbered headings (`2. Omission neglect` → `## 2.`). The first implementation gated candidates on blank-line isolation (blank before AND after). It promoted nothing — because a demoted section heading sits directly BETWEEN two body paragraphs (prose on the line above and the line below, no blank separation). The blank-isolation check rejected every real target.

**Why:** When the section partitioner fails to recognise a heading, it leaves the heading text on its own line but does NOT blank-separate it from the surrounding section body. So a demoted heading looks like: `<last line of prev section>` / `2. Omission neglect` / `<first line of this section>`.

**How to detect (next time):** Never gate heading-detection/promotion on blank-line isolation — demoted headings are wedged in prose. Use a different discriminator: for a numbered heading, "not adjacent to a sibling `N.` line" distinguishes a heading-before-section-body from a list-item-in-a-list. For single-level numbered promotion specifically, layer multiple independent gates (document-numbering-range, number-uniqueness, list-adjacency, terminal-punctuation, lowercase-run) so an enumerated list is rejected by several of them at once — defense in depth keeps a wide-false-positive-surface fix safe.

## 2026-05-16 · Cycle 12 — don't add a normalize step that duplicates an existing one; localize the defect channel first (v2.4.44)

**What:** Latin typographic ligatures (`ﬀ ﬁ ﬂ ﬃ ﬄ ﬅ ﬆ`, U+FB00-FB06) rendered verbatim — `conﬁdent`, `inﬂuence` — in 35 corpus `.md` files. The first cycle-12 attempt added a new `decompose_ligatures` helper and called it EARLY in `normalize_text`, not noticing `normalize_text` already had an `S3_ligature_expansion` step (FB00-FB04). The early call consumed every ligature before S3 ran, so S3 tracked `ligatures_expanded = 0` and `test_report_tracks_changes` broke. Worse, the body channel was never the problem: a channel check showed all 35 papers' ligatures sat in table cells / figure-table captions / `unstructured-table` fences — channels that bypass `normalize_text` entirely. The rework removed the duplicate call, unified S3 to call the shared helper (full FB00-FB06 block via an explicit ASCII table — NFKC of `ﬅ` yields a non-ASCII long-s), and kept the genuinely-new `cell_cleaning` + render-post-process calls.

**Why:** Two failure modes compounded. (1) A new normalize helper added without grepping the existing `normalize_text` S-steps duplicated S3 and, placed before it, starved it. (2) The cycle was scoped from a symptom ("35 papers show ligatures") without localizing WHICH channel was at fault — the body channel was already correct.

**How to detect (next time):** Before adding any glyph/encoding helper to `normalize.py`, grep the existing `S0`-`S9` / `W0*` steps for one already handling that character class — extend/unify it rather than adding a parallel path, and never insert a new step *before* an existing one that consumes the same input. Before scoping a glyph cycle, localize the defect: grep the offending glyph's lines in a recent render and confirm whether they sit in `<td>`/`<th>`/`*Table N*`/```unstructured-table``` (table/caption/fence channels — bypass `normalize_text`) or in body prose (the S-step channel).

## 2026-05-16 · Cycle 13 — a heuristic guard's value depends on the false-positive surface, which differs per call site (v2.4.45)

**What:** `render.py`'s two numbered-heading promoters shared a `max_lc_run >= 5` "long lowercase-word run" prose guard. It demoted legitimate descriptive headings — jdm_.2023.16 had 19 multi-level numbered subsection headings rendered as body text, with lowercase-runs up to 12 (`3.3.2.1. The quality of planning on the previous trial moderates the effect of reflection`). The fix removed the guard ENTIRELY from `_promote_numbered_subsection_headings` but KEPT it (raised 5→8) in `_promote_numbered_section_headings`.

**Why:** A lowercase-word-run count genuinely cannot distinguish a descriptive section heading from prose — both have many lowercase words. What makes a line a heading is the *number shape* + capital-start + no-terminal-punctuation + single short line. For **multi-level** dotted numbering (`N.N[.N…]`) that signature is decisive — a prose line almost never begins with a multi-level dotted number — so the lc-run guard was pure harm. For **single-level** `N.` numbering the signature is weak (a `2.` line collides with an enumerated-list item), so a prose guard there still adds value as defense-in-depth. Same guard, opposite verdicts, because the false-positive surface differs between the two call sites.

**How to detect (next time):** When a heuristic guard rejects legitimate inputs, do not just retune its threshold — ask whether the guard discriminates at all at that call site. Reproduce at HEAD and measure the metric's spread on real positives (here: heading lowercase-runs ran 0-12, overlapping prose entirely → no threshold works). If a guard can't separate the classes, remove it where the *other* gates already suffice and keep it only where they don't. When a guard is removed, grep its tests — a contract test (`test_render.py::test_promote_rejects_prose_with_long_lowercase_run`) was asserting the removed behavior and had to be updated in the same cycle.

## 2026-05-16 · Cycle G5c-1 — a render-layer fold can only fix the immediately-adjacent case; resist generalizing it into partitioner work (v2.4.46)

**What:** pdftotext splits a numbered subsection heading `5.4. Discussion` into a bare `5.4.` line + a separate `Discussion` line; the section partitioner promotes the lone word to a generic `## Discussion` and strands the number. New render post-processor `_fold_orphan_multilevel_numerals_into_headings` (the multi-level analogue of the existing arabic/roman orphan folders) folds `5.4.`⏎`## Discussion` → `### 5.4. Discussion`. In the target paper jdm_m.2022.2 there are 6 such orphan numbers but only 1 (`5.4.`) is foldable — the other 5 are followed by a figure block or by body prose (the title word was consumed elsewhere by the partitioner), so there is no heading to fold into. The cycle fixed exactly the 1 foldable case and left the other 5 for G5c-2 (partitioner split-heading rejoin).

**Why:** The structural signature a render-layer fold can act on is "orphan number + blank-line-only adjacency to a heading." When the partitioner has already consumed the title word elsewhere, the heading does not exist at that position — no render post-processor can recover it; that needs partitioner-level work. Folding `5.3.` into the `### Figure 1` that happens to sit below it (the nearest heading) would emit `### 5.3. Figure 1` — actively wrong. Two guards encode this: the fold target excludes `### Figure N`/`### Table N` (library-emitted structural markers) and already-numbered headings, and only blank-line-only adjacency counts.

**How to detect (next time):** When a TRIAGE item lists N instances of a defect in one paper, reproduce ALL N at HEAD before scoping — they may not share a fixable shape. Here 1/6 was a render-layer fold and 5/6 were partitioner work; the cycle-14 investigation had already split G5c into G5c-1 (render) + G5c-2 (partitioner). A fix that "only handles 1 of 6" is correct when the other 5 are a genuinely different defect class — do not stretch a render-layer regex to chase cases that have no anchor for it.

## 2026-05-16 · Cycle FIG-1 — figure-caption overflow is a reliable over-absorption signal (v2.4.47)

**What:** pdftotext welds a figure's following body prose onto its caption with a single `\n` (no `\n\n` paragraph break), so `_extract_caption_text`'s paragraph-walk can't stop and absorbs prose to the 800-char hard cap; the old 400-char cap then cut the caption mid-word with `…`. New `_trim_overflowing_figure_caption` walks an overflowing figure caption back to its last real sentence terminator (abbreviations + author initials skipped; terminator must sit past the `Figure N.` label so the caption isn't collapsed to its label). Figures only — tables keep `_trim_table_caption_at_cell_region`.

**Why:** A corpus scan of all 17 APA papers showed *every* figure caption >400 chars was over-absorbed body prose and every legitimate caption was ≤360 chars. So `len(caption) > 400` is itself a sound structural discriminator — no content heuristic needed. The walk-back deliberately takes the *last* terminator in the window (over-keep) rather than the first (which would risk cutting a legitimate multi-sentence caption short = text loss); for a caption, residual prose beats lost text.

**How to detect (next time):** When designing a length-gated trim, scan the whole corpus for the metric's spread first (here: clean captions 36-360 chars, over-absorbed ones all >390) — if the classes don't overlap, the length threshold alone is the discriminator and no fragile content heuristic is needed. When an existing trimmer (`_trim_caption_at_body_prose_boundary`) misses cases because its opener regex is too narrow, add a structural backstop *after* it (gated on a sentence boundary) rather than endlessly extending the opener list. Glyph/caption helpers: a contract test that exercises an "unreachable" path can still catch a real latent regex bug (`(?=\s)` vs `(?=\s|$)` for end-of-string terminators).

## 2026-05-16 · Cycle FIG-2 — read the raw text: the caption-end \n\n usually exists; fix the walk, not a trimmer (v2.4.48)

**What:** Figure captions absorbed body prose because `_extract_caption_text`'s paragraph-walk only stopped at a `\n\n` when the preceding text ended with `.!?`. APA 7 figure titles are period-less Title-Case phrases (`The Interaction Between … Non-Manipulated Attribute`), and significance legends (`*** p < .001`) also end without a period — so the walk sailed past the `\n\n` that legitimately ends them. New `_caption_is_complete_without_terminator` recognizes both period-less complete-caption shapes and stops the walk there.

**Why:** When FIG-1's residuals looked like "the 400-char walk-back over-keeps," the instinct was to strengthen a downstream trimmer. Reading the RAW pdftotext output showed the `\n\n` boundary was already there — the walk just didn't honor a period-less caption end. Fixing the walk's stop condition is one localized change; chasing it with regex trimmers downstream would have been brittle and partial.

**How to detect (next time):** When a figure/table caption over-absorbs, FIRST read the raw `extract_pdf` text around the caption (`raw.find(anchor)`) and locate the `\n\n`. If a `\n\n` already separates the caption from the body prose, the bug is in the paragraph-walk's stop condition — fix it there, do not add a post-hoc trimmer. Two regression traps when adding a "complete caption" detector: (1) the repeated PMC running header `Author Manuscript Author Manuscript` reads as a 4-word Title-Case title — strip leading `(Author Manuscript)+` first; (2) `cap.label` is title-case but pdftotext may emit the label ALL-CAPS (`FIGURE 15.`) — strip the label with a case-INsensitive regex, never `startswith(cap.label)`. Run the test files that exercise the SAME code path (here the IEEE-bearing `test_figure_caption_trim` / `test_chart_data_trim`) FIRST — they caught the PMC regression in 30s, before the 12-minute broad suite.

## 2026-05-16 · Cycle FIG-3a — a corpus scan of the boundary signature enumerates the guard set, not just the defect (v2.4.49)

**What:** Figure captions absorbed trailing body prose welded on at a real `. ` sentence boundary with no `\n\n` break. The general signature: a figure caption's own sentences always start capitalized, so a `. ` followed by a lowercase-initial word is absorbed body prose. `_trim_caption_at_body_prose_boundary` gained that boundary rule, guarded against caption-NOTE labels (`Note. t-values …`) and significance-legend tails (`ns p>.05, ∗ p<.05 …`).

**Why:** The TRIAGE named only 2 captions (chandrashekar Fig 4/5). A scan of all 18 APA papers for *every* `. `-then-lowercase boundary found 5 genuine + 2 legitimate lowercase continuations on OTHER papers (efendic's figure note, korbmacher's significance legend) that a naive rule would have silently destroyed. The scan enumerated the guard set.

**How to detect next time:** Before designing any caption/heading boundary heuristic, scan the whole corpus for the boundary signature and classify every hit as genuine-defect vs legit-continuation. The legit-continuation hits ARE the guard list. Two figure-caption-specific traps: APA PDFs use U+2217 `∗` (asterisk operator) not ASCII `*` in significance legends; and a label word (`Note`/`Source`) needs guarding on the word BEFORE the period, distinct from the same word as a tail-opener.

## 2026-05-16 · Cycle FIG-3b — m.start() of a `^\s*`-anchored regex is not the token position (v2.4.50)

**What:** A figure/table caption can be anchored to a body-text *reference* ("…in Figure 10.") that line-wraps to a line start, rather than the real caption. `extract_pdf_structured`'s dedup kept the first-in-document anchor per `(kind, number)`, which is often the reference. New `caption_anchor_is_in_text_reference` lets the dedup prefer the real caption.

**Why:** `FIGURE_CAPTION_RE`/`TABLE_CAPTION_RE` start with `^\s*`; the `\s*` absorbs blank lines, so `CaptionMatch.char_start` (= `m.start()`) sits ABOVE the real `Figure N` token. A first cut of the discriminator read the line at `char_start` and mis-classified a real caption (its "previous line" was actually the end of the paragraph two lines up).

**How to detect next time:** Any logic that inspects the line/paragraph context of a `CaptionMatch` must first advance past the regex-absorbed whitespace to the real token (`while raw[i] in " \t\r\n": i += 1`). Make caption-anchor heuristics a dedup TIE-BREAK (consulted only on 2+ anchors, fall back to old behavior) so a mis-classification is a no-op, never a dropped figure. Corpus-scan every changed case before shipping — the scan caught this bug pre-release.

## 2026-05-16 · Cycle FIG-3c — an equality-matching render pass must run after all glyph-normalization passes (v2.4.51)

**What:** A figure caption renders twice — inline in body prose + as the `### Figure N` block. New render post-processor `_suppress_inline_duplicate_figure_captions` drops the inline copy, but ONLY when the block caption fully covers it (no text-loss).

**Why:** First placement (early in the post-processor chain) was a silent no-op: the block caption still had a `ﬂ` ligature (`reﬂection`) while the body line was already decomposed (`reflection`) — `decompose_ligatures` runs late. The two spans were byte-unequal, so the equality check never fired.

**How to detect next time:** A render post-processor that compares two text spans for equality/prefix must run DOWNSTREAM of every pass that normalizes glyphs in either span (`decompose_ligatures`, `destyle_math_alphanumeric`, `recover_corrupted_minus_signs`, …). Diagnostic: if a pass is a no-op in the chain but works when applied standalone to the final output, a later pass is mutating the text it matches on — bisect the passes between. When the fix removes body text, scope it to the provably-safe subset (here: block caption ⊇ inline run) and queue the rest.

## 2026-05-16 · Cycle FIG-4 — a measured threshold is a snapshot; key the guard on the structural invariant (v2.4.52)

**What:** The FIG-1 figure-caption overflow trim treated any caption >400 chars as over-absorbed body prose. efendic Figure 1 is a legit ~498-char caption (label + a long `Note.`). `_extract_caption_text` now tracks whether the paragraph-walk stopped at a real `\n\n` break (complete caption — keep whole) or ran to the 800-char cap (runaway — trim).

**Why:** FIG-1 measured "no legit caption >360 chars" across 17 papers and baked `len > 400 ⇒ over-absorbed` into code + a test. The next paper exceeded it. The length was a proxy for the real signal: did pdftotext's own paragraph break bound the caption?

**How to detect next time:** When a fix keys on a threshold measured from a corpus sample, treat the threshold as provisional and design the guard on the structural invariant it approximates. Also: when fixing a bug makes a *pre-existing* test go red, check whether that test encoded the old buggy contract — FIG-1's `len > 400` corpus-invariant test was green only because the bug was silently truncating the counterexample.

## 2026-05-17 · Cycle HALLUC-HEAD-1 — carve the controlled-vocabulary slice out of a grab-bag defect (v2.4.53)

**What:** The CRediT role `Methodology` collides with the Method/Methodology section keyword, so the partitioner promotes it to a `## Methodology` heading inside the contributor-roles block. New `_demote_credit_role_headings` demotes a `## <CRediT-role>` heading when ≥3 other CRediT role tokens sit in the ±10-line window.

**Why:** HALLUC-HEAD as a whole is an open-ended grab-bag (`## Conclusion`, `## Supplementary Material`, …) with a broad false-positive surface. The CRediT sub-case is governed by a closed, standardized 14-term vocabulary — that makes it precisely detectable and safe to ship as its own narrow cycle.

**How to detect next time:** When a defect class is partly governed by a controlled vocabulary (CRediT roles, ISO codes, a journal's fixed section set), split that slice into its own cycle — it ships safely while the open-ended remainder waits. Disambiguate an ambiguous token by neighborhood density (≥3 nearby vocabulary terms = inside the block), not by the token alone. Normalize the vocabulary for publisher punctuation variants (dash styles, `&` vs `and`).

## Harness `extract.py` skips on source-sha1, not docpluck version (caught 2026-05-17, run 9 cycle 1, v2.4.54)

**What:** `scripts/harness/extract.py`'s idempotency skip fires when `status == "ok" AND source_sha1 unchanged AND docpluck_version is truthy` — it does NOT compare the recorded `docpluck_version` to the running service's version. So after a library code change, a plain `python -m scripts.harness.extract` SKIPS every document (the PDF/DOCX bytes never change) and the Tier-D gate then diffs stale pre-change output against the baseline — a green gate that proves nothing.

**Why:** the harness is the per-cycle regression gate. Without `--force` after a code change it silently verifies the OLD library.

**Fix / how to use it:**
1. Always pass `--force` to `scripts.harness.extract` after any library change.
2. A signature-gated no-op fix (a helper that early-returns when its trigger glyph/pattern is absent) is *provably* byte-identical on unaffected docs — so `--force --only <affected-docs>` is a sound per-cycle gate; run one full whole-corpus `--force` sweep before release as the corpus-wide backstop. (A full whole-corpus academic-level extract is ~70 min on this machine — per-cycle full extracts do not fit a normal iterate budget.)
3. Never run the harness `extract` and the broad `pytest` concurrently — CPU contention starves the FastAPI service and produces false `extraction` timeouts (3 docs timed out this way in run 9 cycle 1, surfacing as phantom `extraction` pass→fail "regressions").

**Possible harness improvement (queued):** make the `extract.py` skip compare `docpluck_version` to the live `/health` version so a plain `extract` re-does docs whose extracting build is stale — then `--force` is only needed to override a *same-version* re-extract.

## A "defensive" render choice that drops a structural marker is usually wrong (caught 2026-05-17, run 9 cycle 2, v2.4.55)

**What:** `render.py`'s in-section caption-only-table branch skipped the `### Table N` heading (added v2.4.2, reasoning a bare heading "falsely promises structured content" when no grid was extracted). That hid the table from the rendered heading outline AND from the harness Tier-D `table_parity` check — and was inconsistent with the appendix leftover-table path, which emitted `### {label}` for the identical caption-only case. 15 corpus documents failed `table_parity` for this one reason.

**Why:** omitting a structural marker to avoid "over-promising" instead loses the artifact entirely from every structural view. The honest output is the marker plus the available content (here: heading + caption), not no marker.

**How to detect:** when a render branch deliberately omits a structural marker (`### `, `<table>`, a label), grep for a SIBLING branch handling a similar input — if the sibling emits the marker, the omission is an inconsistency, not a feature. And ask: does omitting it lose the artifact from a downstream structural view (a count/parity check, a heading outline)? If yes, emit the marker.

## A glyph destroyed to U+FFFD by BOTH pdftotext and pdfplumber needs document-structural recovery (caught 2026-05-18, run-9 cycle 4, v2.4.57)

**What:** `plos_med_1` typesets `≥`/`≤` with the TeX `cmsy10` math-symbol font. pdftotext AND pdfplumber both fail to decode those glyphs — each emits a bare U+FFFD. Unlike the PUA-glyph cycles (1/3), where the codepoint survives and pdfplumber's per-char font+geometry disambiguates it, here zero glyph identity survives EITHER engine, so the layout channel cannot recover it.

**Why / Fix:** recovery must come from document structure, not the glyph. New `normalize.py::recover_fffd_comparison_operators` (step S5b): Rule 1 — a corrupted `[FFFD]N` contrasted with a clean `<N`/`>N` of the SAME number N is a mathematical set-partition, so the corrupted operator is the complement (`<`↔`≥`, `>`↔`≤`) with zero false-positive risk; a regex backreference enforces the same-number constraint. Rule 2 — a lone `[FFFD]N` is recovered only when Rule 1 fired and every recovery agreed on one operator (one PDF == one font == one corruption shape).

**How to detect (next time):** when a render shows a raw `�` (U+FFFD) adjacent to a digit, check pdftotext AND the pdfplumber layout channel — if BOTH dropped the glyph, per-occurrence recovery is impossible; look for a co-located structural invariant (a complement partition, an estimate∈CI pair, a doc-level consensus) and recover from that. Never guess a bare FFFD that has no structural anchor — leave it for quality scoring (the S5a policy).

## `render_pdf_to_markdown(_sectioned=…)` silently bypasses its own `preserve_math_glyphs=True` (caught 2026-05-18, run-9 cycle 4)

**What:** the docpluck app's `/analyze` handler (`PDFextractor/service/app/main.py:786`) computes `doc = extract_sections(file_bytes=content)` once — with the default `preserve_math_glyphs=False` — for the `sections` view, then reuses it as `_sectioned=doc` in `render_pdf_to_markdown(content, normalization_level=level, _structured=…, _sectioned=doc)`. `render_pdf_to_markdown` normally calls `extract_sections(…, preserve_math_glyphs=True)` itself; the `_sectioned=` optimization arg makes it consume the caller's pre-computed document verbatim and SKIP that internal call. Result: the app's user-facing rendered view transliterates `≥`→`>=`, `χ`→`chi2`, `β`→`beta` — exactly the G2-class corruption the `preserve_math_glyphs` work removed from `render_pdf_to_markdown` itself. The library render is correct; the app's API misuse re-introduces the defect.

**Why:** `render_pdf_to_markdown`'s `_sectioned=` / `_structured=` args are a performance optimization (skip a duplicate Camelot + `extract_sections` pass, ~30s→~1s). But `_sectioned` carries the normalization mode baked in — passing a `preserve_math_glyphs=False` document silently downgrades the render, with no warning.

**How to detect:** any caller of `render_pdf_to_markdown` passing `_sectioned=` MUST have built that document with `preserve_math_glyphs=True`. Grep for `render_pdf_to_markdown(` calls with a `_sectioned=` arg; trace the sectioned doc to its `extract_sections(…)` call and confirm `preserve_math_glyphs=True`. Output symptom: the rendered view shows `>=`/`<=`/`chi2`/`beta` where the source PDF prints `≥`/`≤`/`χ²`/`β`. A Tier1-vs-Tier2 byte diff (direct `render_pdf_to_markdown` vs the app `/analyze` rendered view) surfaces it; the harness Tier-D `glyph` check does NOT (ASCII `>=` is not a flagged glyph). Documented as `tmp/known-tier-deltas.md` Delta 3.

## docpluckapp service test suite is outside the iterate loop — drift accumulates undetected (caught 2026-05-18, run 9 cycle 5)

**What:** Cycle 5 was the first cycle to touch app code (`PDFextractor/service/`) and run `PDFextractor/service/tests/`. That suite had 6 dormant issues: 5 test-fixture drift — `sectioning_version` hardcoded `"1.0.0"` vs live `1.2.2` (drifted across ~2 minor bumps); two SMP-recovery tests asserting the Xpdf-era `pdftotext_default+pdfplumber_recovery` mechanism that poppler pdftotext makes dormant (poppler emits SMP codepoints, not U+FFFD, so the U+FFFD-keyed recovery legitimately does not fire and normalize S0 destyles them); `test_all_styles_have_content` failing on an empty `test-pdfs/docx/` folder — PLUS 1 real library bug (`test_normalization_idempotent`: `normalize_text` leaves broken words on a single pass).

**Why:** The iterate loop runs the docpluck LIBRARY pytest + the harness; it never runs the app's own service test suite. So app-side test drift and app-surfaced library bugs are invisible between app-touching cycles.

**How to detect / fix:** When a cycle touches `PDFextractor/service/` code, run `cd PDFextractor/service && python -m pytest tests/` and triage failures per the 3-bucket rule (real bug / test drift / env). Run it periodically (~every 5 cycles) even with no app change — the runtime (pdftotext version, fixture folders) drifts independently. A hardcoded version-string assertion (`x_version == "1.2.3"`) is always latent drift — assert against the imported live constant. A test that asserts a *mechanism* (which engine ran) rather than the *outcome* (clean text) is environment-fragile — assert the invariant.

**Also (call-site enumeration):** when a handoff names ONE call site to fix, grep for ALL call sites of that function. Cycle 5's handoff named `main.py:786`; `extract_sections(file_bytes=content)` was also at `main.py:506` (`/sections` endpoint) with the same defect. A general fix covers every call site, not just the named one.

## The harness `text_loss` 8-word-window proxy false-positives on reflowed table/stimulus regions (caught 2026-05-19, run 9 cycle 6)

**What:** `scripts/harness/checks.py::check_text_loss` declares a source paragraph "lost" if no 8-contiguous-word run of it survives into `rendered.md`. For a TABLE or stimulus grid, pdftotext linearizes the cells column-major and the renderer emits them row-major (`<table>`) or reflows them into prose — every word survives, but word ORDER changes, so no 8-word window matches → false `text_loss=fail`. 7 of the 8 run-9 Tier-D `text_loss` fails were this artifact (ding-feldman stimulus box, korbmacher table footnote, li-feldman/mayiwar linearized problem-design tables, wong-feldman clean `<table>`, xiao-monin supplementary TOC). Only plos-med-1 was real loss.

**Why / Fix:** the `text_loss` check's job is "did the text survive", not "is table word-order preserved" (table quality is `table_parity` + Tier-A). The cycle-6 fix adds a **reflow exemption**: when no 8-word window survives, if the paragraph's word-coverage ≥ 0.90 (near-total survival) AND a contiguous run ≥ 3 words is intact (not pure scatter), it is a reflowed region — not loss. Calibrated against the one real-loss counterexample: 16 artifact paragraphs all ≥ 0.94 coverage + run ≥ 3; plos-med-1 SAE Table 5 (13 rows genuinely dropped) is 0.83 + run 2. The exemption can only flip fail→pass on already-failing docs (0 regression risk on the passing corpus) and is recorded as `reflowed_exempt` in the matrix for auditability.

**How to detect / decide:** before treating a `text_loss=fail` as real loss, run a word-coverage probe over the saved `verify_out/` raw.txt vs rendered.md — near-100% coverage + a 3+-word run means "right words, reordered" (a reflowed grid), not loss. Do NOT loosen the check blindly: adjudicate every flagged paragraph, confirm the discriminator separates the artifacts from the genuine loss with margin, and key the exemption on a structural signature (coverage + run), never on paper identity.

**Also (`_fingerprint` glyph consistency):** the harness `_fingerprint` now transliterates Greek letters to spelled ASCII names (`χ`→`chi`) so a raw-vs-rendered glyph/ASCII-name divergence cannot create a spurious text_loss mismatch.

## `normalize_text` non-idempotence is systemic — three root-cause buckets in the normalize pipeline (caught 2026-05-20, run 9 cycle 7)

**What:** Calling `normalize_text` twice on its own output produced different results on 85 of 180 corpus docs (≈47%). The handoff scoped it as a one-line fix; reality is structural. Three buckets:

- **JOIN (54 docs).** Line-join `re.sub` steps like `S8` `([a-z,;])\n([a-z])` → `\1 \2` consume *both* boundary characters in each match — so a run of N adjacent joinable lines halves per pass, never fully joining in one call. Pass-1 of `a\nb\nc\nd` becomes `a b\nc d`; pass-2 finishes it. Production (single pass) ships paragraphs with half their pdftotext line-breaks still mid-sentence.
- **STRIP (24 docs).** Position/cluster-gated strips fire only on pass 2 — a real banner is pushed past the 30-line H0 header zone by un-cleaned front-matter noise on raw, then P0/P1/S9/A1/A7/R3 shift it up so pass 2's H0 catches it. Same pattern in P0 ("Author affiliations and article information are listed at the end of this article" on 12 JAMA papers) and S9 (4-digit page-number cluster detection on bjps_8).
- **CHARSUB (7 docs).** Destructive char-substitution on re-application: `recover_minus_via_ci_pairing`'s `_CORRUPT_NEG_TOKEN_RE` lookbehind `(?<![\d.])` allows a `-` immediately before the `2`, so the step re-fires on an already-negative `-2.68` → `--.68`. Production (one pass) is fine; a fixed-point loop or any reprocessing would corrupt.

**Why / Fix:**
- **Cycle 7 fixed two STRIP/JOIN sub-cases** — S7a `_rejoin_space_broken_compounds` now strips ALL whitespace in the match (`re.sub(r"\s+", "", m.group(0))`), so a curated compound rejoins regardless of separator (space, tab, newline); H0r re-applies `_strip_document_header_banners` to a fixed point at the END of the pipeline, on stabilized line positions.
- **Cycles 8/9/10 take the buckets.** Cycle 8: convert line-join `re.sub`s to non-consuming lookahead form (`([a-z,;])\n(?=[a-z])` → `\1 `) so a chained run converges in one pass. Cycle 9: apply the H0r "re-strip on stable positions" pattern to P0 and S9. Cycle 10: guard the destructive minus-recovery (tighten the lookbehind to `(?<![\d.\-])`).

**How to detect / decide:** an idempotency scan (`normalize_text(normalize_text(raw)) != normalize_text(raw)`) is the gate. The corpus-wide test `tests/test_normalize_idempotent_real_pdf.py::test_normalize_idempotent_corpus` is a strided-sample ratchet; lower `_IDEMPOTENCY_RATCHET` each idempotency cycle. Per "leave nothing behind", `normalize_text` non-idempotence is a real production defect (the single production pass ships paragraphs with half-joined line-breaks and un-stripped banners), not just an artifact of an artificial double-call. **Anti-pattern caught:** a fixed-point pipeline loop would seem elegant but a destructive step (D) makes it loop-CORRUPT — fix the destructive step BEFORE introducing any whole-pipeline convergence.

**Also (test-infra):** `tests/conftest.py::PDF_PATHS["docpluck"]` was pointing at `~/Dropbox/Vibe/PDFextractor` while the repo lives at `~/Dropbox/Vibe/MetaScienceTools/PDFextractor`. Three real-PDF tests had been silently skipping. Always derive sibling-repo paths from `__file__` so they survive a tree move. Hard-coding `~/Dropbox/Vibe/...` was the root cause; fixed by `_SIBLINGS = os.path.dirname(os.path.dirname(_HERE))`.

## `re.sub` line-join patterns consume the boundary char — chained adjacencies need N passes to fully converge (caught 2026-05-20, run 9 cycle 8)

**What:** `re.sub(r"([a-z,;])\n([a-z])", r"\1 \2", t)` (the S8 line-break join) consumes *both* the trailing char of line A *and* the leading char of line B in every match, then resumes scanning past them. For a run of N consecutive joinable adjacencies (`a\nb\nc\nd`), only every-other adjacency joins per call: `a\nb\nc\nd` → `a b\nc d` (only 2 of 3 boundaries fixed). Pass 2 fixes the rest. Production single-pass output ships paragraphs with half their pdftotext line-wraps still mid-sentence. The same trap exists in S7 (`[a-z]-\n[a-z]`), in every A1 stat-line-repair pattern, in A7 DOI rejoin, and in R3 reference-continuation join.

**Why / Fix:** convert the trailing group to a non-consuming **lookahead** — the second group is matched but not captured/consumed, so `re.sub` resumes scanning AT the boundary char rather than past it. A chained run merges in a single pass.

- `re.sub(r"([a-z,;])\n([a-z])", r"\1 \2", t)` → `re.sub(r"([a-z,;])\n(?=[a-zα-ω])", r"\1 ", t)`. Trace: `a\nb\nc\nd` → match `a\n` (lookahead `b`) → `a `, resume at `b`; match `b\n` (lookahead `c`) → `b `, resume at `c`; match `c\n` (lookahead `d`) → `c `; result `a b c d` in one pass.
- Extend the lookahead class to include lowercase Greek (`α-ω` = U+03B1–U+03C9) so a `,\nσ²(ξ)` boundary joins on pass 1 — fixing the S8-runs-before-A5 ordering gap (A5 transliterates `σ`→`sigma` later in the pipeline; pre-fix the Greek-initial line escaped S8 and only pass 2 caught it).

**Also (architectural — line-removal steps re-expose join boundaries):** S9's repeated-line / page-number strip operates as `lines = [l for l in lines if l.strip() not in repeated]; "\n".join(lines)`. When an intermediate line is dropped, the two surrounding kept lines become adjacent with a SINGLE `\n` between them. If those neighbours are body prose, the join creates a fresh `[a-z,;]\n[a-z]` boundary that S7/S8/A1 already ran past. The H0r pattern from cycle 7 generalizes: re-apply the line-join steps at the END of the pipeline, after all line-removal steps, on stabilized line positions. The new `LateJoin_line_break_rejoin` block does this.

**How to detect:** an idempotency scan post-fix. The remaining residuals (currently 36/180) are mostly S9 4-digit page-number cluster strips that fire on pass 2 only — same family as the H0 issue, cycle 9 handles them. **Anti-pattern caught:** an instinct to "just run normalize twice" (a fixed-point loop) would seem elegant but the destructive `recover_minus_via_ci_pairing` step (cycle 10) would loop-corrupt `-2.68` → `--.68` → `---.68`. Fix per-step root causes; don't wrap the whole pipeline in a converge-loop until every step is provably re-application-safe.

## Railway Metal builder disk exhaustion has TWO distinct failure modes — only one is Dockerfile-fixable (caught 2026-05-20, run 9 cycle 8 deploy)

**What:** The v2.4.59 deploy hit two consecutive Railway build failures on the same `production-builderv3-us-west1-s3s1` Metal builder. The first failed at `[2/6] RUN apt-get update && apt-get install ...` with `E: You don't have enough free space in /var/cache/apt/archives/`. After we split the apt install into 3 chunks with `apt-get clean` between (docpluckapp commit `ea69192`), the next two retries failed at step 0 — `[internal] load build definition from service/Dockerfile` — with `ResourceExhausted: failed to create lease: write /var/lib/buildkit/runc-overlayfs/containerdmeta.db: no space left on device`. The Dockerfile fix was never even read.

**Why:** Two different filesystems are involved.
1. `/var/cache/apt/archives/` is INSIDE the build container's writable layer. When `apt-get install` pulls 130 packages totalling ~105 MB before the install + cleanup, the writable layer fills. **This is Dockerfile-fixable.** Splitting the install caps peak archive size to whichever single chunk is largest (e.g. ghostscript ≈ 70 MB).
2. `/var/lib/buildkit/runc-overlayfs/containerdmeta.db` is on the BUILDER NODE's host filesystem, owned by the buildkit daemon. It tracks every project's build leases, snapshots, and image cache. When this fills, the daemon can't even allocate a lease to read the user-supplied Dockerfile. **This is NOT Dockerfile-fixable.** The only recovery is for Railway to clean / rotate the builder node, or for the service to be scheduled onto a different builder (which `railway redeploy` does not force — three consecutive redeploys landed on the same broken builder).

**Fix (mode 1, apt cache):**
```Dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils git \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* \
    && apt-get update \
    && apt-get install -y --no-install-recommends ghostscript \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* \
    && apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
```

**Fix (mode 2, builder node):** wait + retry, or contact Railway support. No code change can help — the buildkit daemon is below the Dockerfile abstraction. Continue local work in the interim (local FastAPI service runs the working-tree library; verification harness gates against local, not prod).

**How to detect / discriminate:**
1. After a `verify-railway-deploy.yml` failure, ALWAYS fetch the FAILED deployment's build logs (not the linked-service default logs which show the last SUCCESS): `railway deployment list --json | jq -r '.[0].id'` then `railway logs --build --lines 800 <full-uuid>`. The `--build` flag is critical.
2. Search the tail for either `/var/cache/apt/archives/` (mode 1 — Dockerfile-fix the apt-get) OR `/var/lib/buildkit/runc-overlayfs/` (mode 2 — Railway infra, stop Dockerfile changes).
3. If mode 2: do NOT push more Dockerfile fixes. They will keep failing on the same builder.

**Anti-pattern caught:** ignoring the verify-railway-deploy workflow's failure as "lag" and just waiting for prod to converge. The 8-min poll was already exhausted; longer waits did NOT help because the build itself never finished. Always pull the deployment status (`railway deployment list --json`) BEFORE deciding "lag vs failure" — the verify workflow only polls `/health`, it can't tell building/crashed/deployed-old apart.

## Anchored ^...$ line-strips need a late re-apply if any earlier step joins lines (caught 2026-05-21, run 9 cycle 9)

**What:** `_strip_page_footer_lines` (P0) drops lines matching anchored `^...$` patterns. Several patterns target known boilerplate lines (JAMA's "Author affiliations and article information are listed at the end of this article."). pdftotext sometimes emits a single conceptual line as TWO rows (`...are\nlisted at the end of this article.`). P0's anchored regex cannot match the split form. S7/S8/LateJoin join the rows on the same pass, but P0 has already run by then — so a second `normalize_text` pass is the only way the joined line gets stripped, making the function non-idempotent and (worse) shipping the boilerplate in production single-pass output.

**Why / Fix:** add a "P0r" block at end of pipeline, after LateJoin and H0r, that re-applies `_strip_page_footer_lines` to a fixed point on the now-stabilized line positions. The early P0 is retained for performance (most P0 lines are already single-row from pdftotext). P0 is idempotent on its own output, so the fixed-point loop converges in 1-2 iterations. Same shape as cycle 7's H0r and cycle 8's LateJoin.

**Generalization — the "late re-apply" pattern (collected, 3 cycles in):** any anchored `^...$` line-strip whose patterns target SINGLE-LINE forms is eligible for a late re-apply if (and only if):
1. **The step is idempotent on its own output** — re-applying it to already-stripped text is a no-op. Strips with simple "remove matching lines" semantics satisfy this; transformations that produce new strippable lines (cascades) do NOT.
2. **The step depends on stabilized line positions that LATER steps create** — pdftotext line-wraps that S7/S8 join, S9's repeated-line removal exposing new neighbors, etc.

The pattern does NOT apply to:
- **Destructive char-substitutions** on re-application (CHARSUB family — `recover_minus_via_ci_pairing` would loop-corrupt `−2.68 → −−.68`).
- **Steps that consume their neighbors** (paragraph-level joins, footnote-extraction).
- **Steps whose patterns depend on stale line positions** (line-N-of-document checks).

**How to detect:** after every "STRIP" cycle that adds a new anchored `^...$` pattern, run `normalize_text(normalize_text(raw))` on a corpus sample and look for any line stripped by pass 2 but not pass 1. If found, candidates for late re-apply. Conversely, look for lines KEPT by pass 1 but stripped by pass 2 where the stripped value is legitimate content (e.g. `7182` sample-size in chandrashekar 2020) — those are FALSE POSITIVES, NOT late-re-apply candidates; they require step-tightening, not propagation. **Discriminator question:** "would I be happy if production's single-pass output ALSO stripped this line?" If yes → late re-apply. If no → tighten the step that strips on pass 2.

**Anti-pattern caught:** the cycle-8 handoff lumped JAMA-affil-sentinel and chandrashekar-7182 into one "STRIP bucket" with one prescription ("apply H0r pattern"). HEAD reproduction showed they are OPPOSITE-direction defects — JAMA wants pass-2-strip in pass-1 (legitimate sentinel), chandrashekar wants pass-2 to STOP stripping (table N values). Splitting them into cycle 9 + 9b instead of one combined cycle avoided shipping a text-loss bug. Always reproduce at HEAD and confirm directionality before coding.

## Non-idempotent normalize_text — bisect via NormalizationReport._track + classify into JOIN / STRIP / CHARSUB (cycle 15, 2026-05-22)

**What:** Run 9 closed at 0/180 non-idempotent after 9 shipped cycles (85 → 0). Cycle 15 cleared the final 4 long-tail papers + 1 latent pre-existing 2-column-bibliography regression in one bundled commit (5 distinct mechanisms, each independently revertible).

**Why:** Non-idempotence is the *canary* for the entire normalization pipeline. A `normalize(raw) != normalize(normalize(raw))` divergence almost always indicates one of three structural defects, each of which corrupts output silently in single-pass production:

| Bucket | Mechanism | Cycle-15 example |
|---|---|---|
| **JOIN** | A line-join regex fires only after an earlier strip removes intervening noise | `(OR\|CI\|RR\|HR)\n\n\d` joined only on pass 2 because S9 hadn't stripped the column header between `CI` and `2.046***` yet on pass 1 |
| **STRIP** | A repeat/cluster-gated strip fires only when an earlier pass's residue puts content into the gated shape | S9 figure-axis tick label `1000` survived pass 1 because `_is_in_numeric_block` rejected the labeled `S<= 10000` neighbor; pass 2 had same shape → same strip — but the *real* defect was that the neighbor SHOULD have qualified |
| **CHARSUB** | A char-substitution leaves an orphaned combining mark on an ASCII tail that NFC composes on pass 2 | A5 `σ→sigma` orphaned U+0302 on `a`; pass-1 left decomposed, pass-2 NFC composed to `â` |

**Investigation recipe (proven across cycles 7-15):**

```python
from docpluck.normalize import normalize_text, NormalizationLevel, NormalizationReport
n1, _ = normalize_text(raw, NormalizationLevel.academic)
orig = NormalizationReport._track
events = []
def cap(self, name, before, after, key=None):
    if SIGNATURE in before and SIGNATURE not in after:
        events.append((name, 'REMOVED'))
    if SIGNATURE not in before and SIGNATURE in after:
        events.append((name, 'ADDED'))
    return orig(self, name, before, after, key)
NormalizationReport._track = cap
n2, _ = normalize_text(n1, NormalizationLevel.academic)
NormalizationReport._track = orig
print(events)
```

Run it once with the strip signature (e.g. the disappearing line) and once with the inverse signature (e.g. the appearing joined-line). The (step, REMOVED/ADDED) tuple identifies the responsible step. Cost: ~30s per paper. Saved ~2-3 hours across cycle 15.

## Iterate-loop spine substrate — audit findings (2026-05-23 origin commit)

**What:** Built `~/.claude/skills/_shared/iterate-loop/` as a hard-gated discipline for `<prefix>-iterate` skills (rules I1–I8 enforced by `iterate-gate.sh`, exit 1 on violation). Origin was the 2026-05-23 ip_feldman defect cluster — run 9 shipped 15 cycles on the idempotency proxy while the canary paper kept rendering with affiliation-leak, hallucinated `## Supplemental Materials` headings mid-Method, and Table 3 caption mid-prose.

**Why this is in lessons.md and not memory:** the bugs below were found during the substrate's own first audit. Documenting them here so future sessions (mine or another agent's) don't re-introduce them when retrofitting other `<prefix>-iterate` skills (citationguard, escicheck, 2rmarkdown, future scimeto).

**Bug 1 (CRITICAL, fixed in same commit): heredoc variable interpolation breaks on JSON containing quotes / backslashes.**

The first `iterate-gate.sh` shipped with `get()` and `DIGEST_OK` helpers that did `json.loads('''$DIGEST''')` inside an unquoted `<<PY` heredoc. Bash performed variable expansion BEFORE feeding the script to Python — meaning `$DIGEST` was inlined as a Python literal. If a paper title contained a quote, backslash, or `'''` sequence, the resulting Python source was malformed. Even with json.dumps's normal escaping, this is a footgun waiting on the wrong input.

**Detection:** the first `--close` run had a SyntaxError ("expression expected after dictionary key and ':'") buried in stderr while the gate still printed its FAIL line — masking the bug behind correct-looking output.

**Fix:** stash `$DIGEST` in a temp file via `mktemp` + `trap 'rm -f' EXIT`; helpers read the file path, not inline JSON. Always use quoted heredocs (`<<'PY'`) and pass dynamic data via env vars or file paths. See `iterate-gate.sh` `get()` / `DIGEST_OK` blocks for the corrected pattern.

**General rule for skill-substrate scripts:** any time you write `<<PY` (unquoted) and reference `$VARIABLE` inside the Python body, you have this bug. Use `<<'PY'` plus env vars (`FOO=value "$PY" - <<'PY'\nimport os\nfoo = os.environ['FOO']`).

**Bug 2 (MEDIUM, fixed): self-referential gate-skip detection was missing.**

Original spine: rule I1 fires if `phase_5d_runs[cycle=N]` is empty. But the agent could skip calling `iterate-gate.sh --cycle N` entirely — and then there'd be no log entry, no heartbeat, no signal that the skill ran any cycles at all. Detection deferred to the next preflight reading `effectiveness.jsonl` and noticing zero entries for the run — too slow.

**Fix:** added **I8 gate-was-actually-called** (in `core.md`). The gate now appends to `cycle_gate_runs[]` in run-meta on every `--cycle` invocation (via `record_gate_run` helper). At `--close`, I8 checks `{1..current_cycle} - {called cycles}` and fails the run-close if any cycle was skipped. Validated: setting `current_cycle=3` + gate-runs for cycles 1+3 → I8 fires: `cycles [2] never invoked iterate-gate.sh --cycle (the agent skipped the gate)`.

**Bug 3 (MEDIUM, documented): I3 doc-vs-code mismatch.**

`core.md` originally said "I3 fires if `cycle_status[N] == PASS` AND verdict != PASS." But the gate-script implementation fires unconditionally on any FAIL/STALE verdict in `--cycle` mode (regardless of `cycle_status`). The code is stricter, which is correct for the failure mode we're defending against (the agent forgetting to set cycle_status while still emitting cycle artifacts) — but the doc was misleading. **Doc updated to match the code** with an explicit "this is intentionally stricter than the literal reading" note.

**General rule:** when the doc and the script disagree, the script wins; align the doc.

**Bug 4 (LOW, documented): STALE_GOLD detection is not automated by the gate.**

The gate trusts the agent to compute `gold_age_days` and set `verdict: "STALE_GOLD"` when appropriate. If the agent forgets, a stale gold is silently treated as fresh. The gate has no independent check — it can't, without knowing the gold cache path schema and SHA semantics for every project. **The agent's Phase 5d step must compute age from the gold file's mtime (or its `stored_at` field in `<gold>.meta.json`) and set the verdict accordingly.** Documented in `core.md` paragraph "BLOCKED-NEEDS-GOLD" and reinforced in `docpluck-iterate/SKILL.md` "Recording during the cycle" subsection.

A future improvement: a project-specific helper (`<project>/.claude/skills/_project/check-gold-age.sh`) that the gate calls in `--cycle` mode to independently compute age. Not implemented yet.

**Bug 5 (LOW, documented): canary `key` field is the storage stem, not the canonical DOI.**

Memory `feedback_gold_canonical_key` says all golds should be registered under their DOI-stem key (`10.1177__01461672251234567`). But many existing golds in `~/ArticleRepository/ai_gold/` use bare project stems (`ip_feldman_2025_pspb`) — they were created by `docpluck-iterate` BEFORE the 2026-05-16 directive that moved gold generation to `article-finder`. The canary file matches papers by `stem`, not DOI, to work with the legacy state.

**Migration path (queued, not done):** for each canary paper without a DOI-key gold, run `article-finder generate-gold <pdf>` to register under the canonical DOI key, then update canary.json's `key` field to the DOI. The gate's coverage check then continues to match by `paper_stem`, which is logged in the gold's meta either way.

**Bug 6 (LOW): canary rotation is deterministic by cycle integer, which works for any starting cycle but has a subtle property.**

Rotation picks `pool[(N mod L) : (N mod L) + rotation_size]` wrapping. Over `ceil(L / rotation_size)` consecutive cycles, every pool member is covered. For docpluck (pool L=5, rotation_size=2), the cycle-coverage cycle is 3 cycles long. **Implication:** if a defect class is only exercised by one pool member, it gets AI-verified every ~3 cycles, not every cycle. The canary fixed-3 is the "every cycle" set; the rotating pool is the "every-few-cycles" set. Be deliberate about which set each defect class lives in.

**Bug 7 (LOW): preflight.md schema example and core.md schema example diverged slightly.**

`preflight.md` listed `blocked_reason` in `phase_5d_runs`; `core.md` did not. Reconciled — both now list it. **General rule:** whenever the spine substrate has schema documented in two places, write a small alignment-check (`diff <(extract-schema preflight.md) <(extract-schema core.md)`) and run it on substrate-touching commits.

**Bug 8 (LOW, observed but not fixed): codex prerequisite asserted in docpluck reference but absent from canonical protocol.**

`docpluck-iterate/references/ai-full-doc-verify.md` line 71 claimed `gold-generation.md` required the `codex` CLI for a cross-model audit. The actual `~/.claude/skills/article-finder/gold-generation.md` uses two independent `general-purpose` Claude subagents — no codex anywhere. The line was wrong / outdated. Fixed in the same commit; also saved as user memory `feedback_no_codex_in_gold_audit` (codex tokens are limited; gold must use Claude subagents).

**General rule:** when a consumer skill asserts a prerequisite for a protocol it doesn't own, verify against the protocol's canonical source — don't trust the consumer's claim.

**Bug 9 (LOW): redundant spine-load documentation between SKILL.md and preflight.md.**

`docpluck-iterate/SKILL.md` step 4 explicitly says "Load the iterate-loop spine — read core.md." `_shared/preflight.md` step 7.5 says the same thing for any `-iterate` / `-fix` skill. Not strictly a bug (defense in depth) but a doc-rot risk — if the call sequence changes, both files need updating. **Convention going forward:** preflight.md is the authoritative source for spine-load procedure; per-skill SKILL.md references it ("see preflight.md step 7.5") rather than restating.

**How these were detected:** self-audit after the initial substrate landed and validated on docpluck. Triggered by the user's request to "look for other inconsistencies and logical bugs." The lesson: substrate code that gates everyone else's discipline must be audited at the same rigor as the code it gates. A foolproof gate that has a heredoc bug is not foolproof.

**The classification then dictates the fix shape:**

- **JOIN-bucket pass-2-only** → add a LateJoin cross-paragraph variant (`\s*\n\s*\n\s*` form) AFTER the strip pass, with a STAT-VALUE-shaped lookahead to avoid colliding with prose-leading-digit forms (bibliography `\d+\.\s+[A-Z]`, ordered lists, etc.).
- **STRIP-bucket false-strip of legitimate content** → tighten the gate (numeric-block widening, year-range exclusion, caption-shape detection).
- **STRIP-bucket true boilerplate that survived early pass** → add a late re-strip (cycles 7 H0r, 9 P0r, 13 P1r).
- **CHARSUB-bucket pass-2-only** → tighten the substitution OR add a final fixed-point pass (NFC, recover-minus). NFC is idempotent by construction, so a final NFC pass at end of pipeline is the safest fix when the drift is a combining-mark orphan.

**Real-PDF regression test is MANDATORY** — synthetic-text contract tests catch the helper but not the surrounding-context shape that actually triggers the bug in production. Every cycle-15 fix has a `*_real_pdf` regression test in `tests/test_normalize_idempotent_real_pdf.py`.

**Bundling N distinct mechanisms in one cycle is OK when each is independently revertible** — the discipline rule "one class of defect per cycle" exists to prevent un-revertible co-fixes. When each fix is a contiguous block touching a different code path with its own test, bundling halves the release/deploy cost vs. N separate cycles. Cycle 14 packaged 3 fixes; cycle 15 packaged 5. Both shipped clean.


## 2026-06-07 — finding-key identity must be line-number-invariant; deferred half-fixes resurface
- A canary-audit `finding_key` that embeds a line number is brittle: any normalize/render change that adds or removes a line shifts every downstream finding's line number, so `--gate-new-only` re-opens KNOWN deferred findings as NEW and falsely blocks the commit. Identity must be severity + verbatim excerpt (the document text is render-stable). Fixed in `_shared/iterate-loop/canary_findings.py::_norm_location`.
- The Sonnet canary auditor needs an `allowed_omissions` list (front-matter masthead, publication-history dates, running headers) or it flags docpluck's by-design strips as TEXT-LOSS and forces SKIP_CANARY. Mirror the in-session verifier's allowed-omissions list. Wired via `canary.json::verification_protocol.allowed_omissions` → payload → `audit-subagent-prompt.md`.
- A docstring that says "a separate pass can rejoin/fix this later" is a latent finding, not a note. `_demote_continuation_promoted_headings` deferred its rejoin in cycle 3; it surfaced as canary finding #2 in cycle 5. Finish the fix when you write it.
- The per-commit canary hook on a paper with a LARGE open deferred surface + single-audit non-determinism will keep requiring SKIP_CANARY until that surface is fully baselined or fixed. Don't read SKIP_CANARY as "gate is broken" — read it as "this canary has known multi-session debt." Surface it; use `--full` (double-audit union) to baseline more completely.

## 2026-06-07 — O5 reference reading-order inversion + a broken WIP that silently disabled column-correction
- **A handoff item lumped into a "won't-fix" class can be a real, different-class bug.** scimeto's O5 ("chen refs stranded before the References header") was tagged "docpluck won't-fix" by association with the A–D pdftotext-glyph classes. It was actually a *reading-order* defect docpluck owns (pdftotext inverts a banded page's two reference columns). Always re-derive layer-of-origin per item; don't inherit a sibling's disposition.
- **`except Exception: pass` around an optional pipeline stage hides a hard syntax error.** A prior session left `extract_columns.py` with an IndentationError + a call to an undefined `_detect_2col_midline_gutter` in the working tree. Because `extract.py` wraps the column-correction call in a bare `except Exception: pass` ("signal-only, never block extraction"), the module simply failed to import on every flagged page → column-correction was silently OFF corpus-wide, with no error surfaced. When you see a broad `except: pass` around a feature, test that the feature actually still runs — don't assume "no error" means "working." (Companion to `feedback_no_silent_optional_deps`.)
- **The safe way to ship a reading-order change (which char-ratio/Jaccard gates are BLIND to): a word-preservation guard.** Accept a geometric re-extraction only if it preserves the page's substantial-word multiset (alphabetic tokens len≥2) — a pure reorder can't drop or fabricate text (rules 0a/0b), and the corpus char-ratio gate (blind to order) still confirms no content change. Confine the new path behind an explicit flag so the legacy path stays byte-identical, and verify the *trigger* fires on a tiny, hand-checked subset (2 of 101 papers here) before trusting it.

## Gold↔PDF SHA integrity gating is mandatory when reusing sibling-skill golds (2026-06-08 untested sweep)

**What:** A discovery sweep over previously-untested papers reused article-finder `reading` golds produced by sibling skills (escicheck-iterate, citationguard). 10/15 candidates had a cache-vs-gold PDF MISMATCH: `cache-check <doi>` returns docpluck's version-of-record PDF, but the gold was generated from a DIFFERENT copy (an ESCIcheck `…print-nosupp.pdf` preprint). Verifying the rendered VOR against a preprint gold manufactures false TEXT-LOSS/HALLUCINATION findings.

**How to detect:** before trusting any verdict that reuses an existing gold, compare `sha256(cache-check PDF)` vs the gold's `reading.meta.json::source_pdf_sha256`. Only verify SHA-matched pairs; for mismatches, regenerate the gold from the cached PDF via `article-finder generate-gold`, or skip. Surfaced an article-finder provenance gap (one DOI → two PDF copies; cache serves one, gold linked to the other) — flag to the AF owner.

**Also:** for a surgically-scoped normalize change, a FOREGROUND blast-radius test subset (Camelot-disabled, 10-min cap) completes reliably (235 pass / 5:39) where the full bg pytest suite + 26-paper verify_corpus both get suspended ~14 min in (machine bg-task limit, `feedback_long_runs_die_on_this_machine`).

## The column-splice word-preservation guard must be UNCONDITIONAL and check the page-JOIN (2026-06-08 v2.4.82)

**What:** The v2.4.80 word-preservation guard (accept a column re-extraction only if it preserves the page's substantial-word multiset) was applied ONLY to the O5 inversion pages — every OTHER flagged page used "accept any non-empty re-extraction." That accept-any path was **shipping word corruptions in the default** on 5/26 baseline papers: pdftotext column-crop (`-x -W`) cuts a word straddling the crop-x, producing `jama_open_1` `adults`→`adu`, `ieee_access_3` `using`→`us`, `amc_1` `management`→`mana`+`agement`. SEPARATELY, even guarded pages glued at the SEAM: `extract_page_text_columns` returns page text stripped of its trailing `\f`, so the splice glued a corrected page's last word onto the next page's first word (`results`+`https`→`resultshttps`; running-header `J`→`fromj`). The per-page guard passed because each page was word-correct *in isolation*.

**Fixes (both in `splice_column_corrected_pages`):** (1) word-preservation is now UNCONDITIONAL — every corrected page must be a pure reorder; a rejected page keeps its word-correct original (even if still column-mixed). (2) Re-attach the original page's trailing newline+`\f` separator so no word glues across the page boundary. Renamed the old `word_preserve_pages` param → `gutter_fallback_pages` (it now governs ONLY the gutter-strip detector; word-preservation is universal).

**How to detect (make this a permanent gate):** `_word_multiset(extract_pdf(b)[0]) == _word_multiset(raw_pdftotext(b))` for every corpus PDF, under `DOCPLUCK_COLUMN_CORRECT_GENERAL` both off and on. The multiset (alphabetic tokens len≥2) is invariant under reorder, so it cleanly separates a safe reorder from a split/glue/loss — and unlike char-ratio/Jaccard it is reorder-blind-PROOF. This caught all 7 corrupted papers in ~8 min (extract-only). 2 committed snapshots (`jama_lattice`, `ieee_figure_heavy`) were STORING the corruption — before regenerating a drifted snapshot, verify the new output against raw-multiset AND check whether the OLD snapshot was itself wrong.

**Trade-off accepted:** rule 0a/0b (word integrity) outranks reading-order de-interleave. R4's `jama_open_1` abstract de-interleave was built on the splitting crop; it now reverts to word-correct-but-column-mixed (proper de-interleave of a full-width-title page needs the Step-2 per-band crop). `test_r4_*` revised to assert word-integrity, not the corrupting de-interleave.

## pdftotext can SPLIT a furniture line across two rows — strip each fragment, not just the composite (2026-06-08 v2.4.83)

**What:** The bare `J. Chen et al.` running header leaked ×20 on chen_2021_jesp (×10 `I. Ziano et al.` on ziano_2021_joep) even though v2.4.81 added the Elsevier `<Author> et al. / <Journal> <Vol> (<Year>) <ArtNo>` footer shape. Root cause: pdftotext SPLIT the full running header across two lines — `J. Chen et al.` on one, `Journal of Experimental Social Psychology 96 (2021) 104154` on the next. The v2.4.81 shape matched the *composite* (and the journal-only half via its optional author prefix), so the journal half was stripped — but the bare author half was its own line matching no shape.

**Lesson:** when a furniture strip half-works, check whether pdftotext fragmented the furniture line; each fragment needs its own shape entry, all gated by the shared ≥3-standalone-repetition guard (`_detect_recurring_running_headers`). New `_AUTHOR_ETAL_INITIAL` (`Initial. Surname et al.`, 1-4 initials incl. hyphenated `M.-J.`, optional particle, trailing `et al.`). It is distinct from an in-text citation (never a standalone whole line) and an APA reference entry (`Surname, Initial.` — comma after surname, inverse order).

**No-regression gate for a new strip shape = the corpus-wide false-positive sweep:** run `_detect_recurring_running_headers` over all 26 baseline papers; assert the new shape adds ONLY genuine running headers (chen ×20, ziano ×10; zero body/table-cell false positives). char-ratio/Jaccard is blind to a repeated short header — chen leaked 20× through the 26-baseline undetected for releases.

## Baked CID-font glyph misreads are a source-PDF artifact, NOT a docpluck bug — confirm with a 3-way diff (2026-06-08)

**What:** `M_age 59.3` rendered as `39.3` on collabra.77859. The PDF VISUALLY shows `59.3`, but the embedded text codepoint is baked as `3` — **both pdftotext AND pdfplumber extract `39.3`**. This is the `Västfjäll→Vastfall` class, but a DIGIT in a statistic (silent stat corruption — the most dangerous form for meta-science).

**How to diagnose:** 3-way check — pdftotext vs pdfplumber vs a visual/AI read of the PDF. When both deterministic extractors agree on the wrong value and only the visual disagrees, the codepoint is baked wrong and NO text-channel logic can fix it (recovery needs OCR / multimodal-glyph-consensus, a new subsystem). User decision 2026-06-08: **document as a known limitation, do not scope an OCR subsystem.** Consumer guidance: downstream stat-checkers (CitationGuard) must cross-verify digits against CrossRef/visual — docpluck cannot guarantee a digit matches the visual glyph when the publisher baked the wrong codepoint.

## RC-1 Step 2 — per-band column re-extraction; the word-preservation guard is the safety (2026-06-15, v2.4.90)

**What:** the dominant two-column-interleave defect (Method/Results/Discussion scrambled) on table-bearing pages that Step 1 (`extract_page_text_columns`, whole-page) cannot reach — its bilateral y-row gate + full-height gutter strip reject any page with a full-width band crossing the centre (confirmed: `DOCPLUCK_COLUMN_CORRECT_GENERAL=1` was byte-near-identical on the failing papers). **Step 2** (`extract_page_text_banded`, `docpluck/extract_columns.py`) segments a page into horizontal y-bands, column-corrects prose bands, keeps full-width (table/banner/title) bands intact; applied as a **fallback inside `splice_column_corrected_pages`** only when whole-page returns "", under the SAME word-preservation guard. Ship-dark behind `DOCPLUCK_COLUMN_CORRECT_BANDED` (default OFF → flag-OFF byte-identical, 26/26 baseline unchanged). AI-verified ON_BETTER on chan_feldman + chandrashekar (0 text-loss/halluc/regression).

**The load-bearing lesson:** the word-preservation guard (substantial-word multiset of the re-extraction == original page) makes ANY segmentation heuristic SAFE — a bad reorder is rejected, the page kept as-is — so optimize segmentation for COVERAGE, not for never-being-wrong. Validate with a corpus word-multiset scan (flag-OFF vs flag-ON whole-doc multiset MUST be identical, `lost=0 gained=0`) BEFORE AI-verify. Three hazards the guard caught: (1) full-width title lines column-split mid-word → a row is 2-col only if the strip `[gx±4pt]` is glyph-free, not merely "no word spans gx"; (2) band cuts bisecting tall title glyphs → merge vertically-overlapping bands to full-width; (3) per-row both-sides is conservative but halves guard-rejections vs gutter-clear-only on hard pages (6 vs 12 of 71) — keep it, layer banded as a fallback so clean 2-col pages use the proven whole-page path. Remaining before default-flip: band-cut clips (6/71, guard-rejected), title+sidebar pages — see `docs/superpowers/specs/2026-06-08-rc1-region-aware-column-architecture.md` "Step 2 — remaining work". Shared card: `band-reextraction-lean-on-word-preservation-guard`.

## Dropped-glyph recovery splits into layout-recoverable vs pixel-only — probe per-instance before designing (2026-06-15, v2.4.89 W0h)

**What:** A glyph that **pdftotext drops entirely** (emits nothing) is NOT one class but two, and a per-*instance* 3-way diff tells them apart:
1. **Layout-recoverable** — pdfplumber still sees the glyph (as an unmapped `(cid:N)` in a symbol font); the text channel lost it, the layout channel kept it. → Recover from the layout channel. `ar_apa_j_jesp_2009_12_011`: 3 of 4 negative betas (`-.022 / -.88 / -.428`) carry their U+2212 as `(cid:2)` in font `AdvP4C4E74`. `normalize.recover_dropped_minus_via_layout` (W0h) re-inserts the minus in the `<stat> = <minus><coef>` operator slot.
2. **Pixel-only** — pdfplumber ALSO drops it (absent from chars/lines/rects/curves AND pdfminer's raw LTChar/LTImage layer); the minus is painted pixels only — same OCR floor as the baked-glyph lesson above. `ar_apa` `β = -.245`: unrecoverable in text+layout. **User decision 2026-06-15: ship the layout-recoverable subset, document the pixel-only residual, do NOT build an OCR tier.**

**Trap:** "the layout channel recovers what pdftotext drops" is true only for sub-case 1. Probe the SPECIFIC failing instances (geometry: is there a char/line/rect immediately left of the number?) before assuming a layout fix is complete — feasibility here was 3/4, and a recovery that silently fixes 3 of 4 sign-flips is a product call (false-confidence), surfaced to the user.

**Plumbing gotcha (cost a detour):** the section/render path calls `normalize_text` WITHOUT `layout=` (`sections/__init__.py`), so F0 and every layout-gated pass is OFF there by design (text-channel-only contract). A layout-aware fix must thread a **dedicated** param (`dropped_minus_layout`, `render → extract_sections → normalize_text`) — reusing the `layout=` gate would also switch F0 on and risk broad regressions. The detector must cluster chars into lines by **y-overlap**, never `round(top)` (a minus sits ~0.4pt off its digits' baseline and rounds into a different bucket, orphaning it).

## On resume, `git status` BEFORE editing source — a concurrent session can co-edit the same files (2026-06-16)

**What:** A `/docpluck-iterate` resume opened on the RC-1 Step 2 handoff. The system-prompt git snapshot said "(clean)", so I went straight to implementing Step 2 (`extract_page_text_bands` + helpers in `extract_columns.py`). But a SECOND Claude session was concurrently implementing the SAME feature (`extract_page_text_banded` + splice/extract.py wiring + `DOCPLUCK_COLUMN_CORRECT_BANDED` flag). Two `Edit`/`Write` "File has been modified since read" events fired on files I hadn't changed; `extract.py` got an mtime I never wrote; 18 `claude.exe` procs were live. The other session committed first (`git add` swept MY uncommitted duplicate into the **v2.4.90 release commit `1325d14`** → orphaned dead code shipped to the tag + prod, inert/uncalled but wrong). Resolution: confirmed the duplicate was uncalled (distinct names, no shadowing), removed my whole block, 69 column-path tests green, committed the removal.

**Lessons:** (1) **The system-prompt git snapshot is from conversation START and goes stale within the session** — on any resume, run a fresh `git status` + `git log --oneline -5` BEFORE the first source edit. (2) **"File has been modified since read" on a file YOU didn't touch = STOP and check for a concurrent editor** (`git diff HEAD`, file mtimes, `tasklist | grep claude`), don't just re-read-and-retry. (3) When two agents share a working tree, whoever commits first sweeps the other's uncommitted changes into THEIR commit — so a concurrent edit is not just a merge risk, it can silently ship your half-done work in someone else's release. (4) When you discover the collision, **surface it to the user** (they know if two sessions are intentional) rather than racing or unilaterally reverting (reverting is itself a write that can clobber the other session's in-flight work).

## Text-channel heading promotion can't use line-WIDTH to gate — earlier render steps join wrapped lines (2026-06-17)

**What:** Resuming docpluck-iterate on the cycle-2 canary FAILs, user chose "headings first." Root-caused the JESP/Elsevier single-column subsection demotion: labels like "Overview", "Practice instructions", "Self-control assessment" are emitted by pdftotext on their own line with NO blank padding on EITHER side (glued between the prior subsection's body and their own body), so every existing promoter — all of which require `blank_before AND blank_after` — skips them. A minimal relaxation of the `blank_before` gate in `_promote_isolated_titlecase_subsection_headings` (admit no-blank-before when the prior line is a sentence-terminated PROSE line, i.e. a clean paragraph boundary, not a mid-sentence column-wrap) **fixes ar_apa perfectly** (+`### Overview` / `### Practice instructions` / `### Self-control assessment`, 0 removed). BUT it over-promotes **5 two-column table-cell / measures-list labels on ip_feldman** (`### Others ratings`, `### Address order effects`, `### Prevalence Estimation Error: …`) — the G5d hallucinated-heading blocker. Reverted; no release.

**The trap (durable):** The obvious discriminator — "real single-column heading is followed by full-page-width body (~60-90 char lines); a narrow two-column table cell is surrounded by ~30-char lines" — **WORKS on RAW pdftotext text but is USELESS at the promoter**, because earlier render-pipeline steps JOIN wrapped lines into long paragraphs before `_promote_isolated_titlecase_subsection_headings` runs. Measured: "Others ratings" body max line width is **36 chars raw → 112 chars in-pipeline**; "Address order effects" 32 → 80. A body-width gate computed inside the promoter therefore admits everything and does nothing.

**Lessons:** (1) Any heading promote/demote heuristic that needs LINE-WIDTH or LINE-WRAP structure must be computed from the **raw pdftotext output (before line-joining)** and threaded into the promoter as a precomputed signal (e.g. a document-level `is_single_column` flag from median raw body-line width ≥ ~62, or per-region width), NOT recomputed inside the render-pipeline promoter where the signal is already destroyed. (2) The safe general fix for this defect class is to **scope the no-blank-padding relaxation to single-column documents** (computed from raw text or the layout channel) — two-column subsection headings are already handled by the blank-isolation / chain paths, so single-column-gating both fixes JESP/Elsevier AND prevents the two-column table-cell over-promotion. (3) Always verify a promotion change against the **G5d canary (ip_feldman) with a deterministic heading-count delta** before trusting it — `diff <(grep -E '^#{1,4} ' before) <(grep -E '^#{1,4} ' after)` instantly shows added/removed headings per paper; ar_apa gaining exactly 3 and ip_feldman gaining 5 was the whole story in one command.

## Single-column gate via raw-text wide-line fraction RESOLVES the JESP glued-heading blocker — and AI-verify catches a new single-column false promotion (2026-06-17 v2.4.91)

**What:** Implemented the precisely-scoped next step from the (same-day) blocked entry above. `_raw_text_is_single_column(raw_text)` = fraction of non-blank RAW-pdftotext lines wider than 65 chars ≥ 0.25, threaded into `_promote_isolated_titlecase_subsection_headings(text, *, is_single_column)`; the hard `blank_before` reject is relaxed ONLY when single-column AND `_prev_paragraph_is_sentence_terminated`. Result: `ar_apa_j_jesp_2009_12_011` gains exactly `### Overview` / `### Practice instructions` / `### Self-control assessment` (AI-verified vs the article-finder reading gold: `new_headings_are_real=true`), two-column `ip_feldman_2025_pspb` byte-identical (G5d trap avoided), 26-baseline 26/26.

**Why `frac>65` and NOT median or interleave-pages:** The corpus measurement (all 26 baseline papers) showed median misclassifies single-column table-heavy papers (plos_med median 48 but genuinely single-column), and the column-interleave page count is useless — the genuine single-column target ar_apa has 4/5 pages flagged by `_detect_column_interleave_pages` (short reference/table lines trip it). `frac>65` is the physical invariant: a two-column layout *cannot* emit many >65-char lines (each column wraps at ~30-48), so it stays 0.06–0.24; single-column body prose wraps full-width → 0.28–0.58. The gap (0.235→0.280) is clean and corpus-wide.

**The AI-verify catch (why Phase-5d is non-negotiable):** the single-column relaxation ALSO promoted `### Anesthesiologists; CI, confidence interval; DSMB,` on plos_med_1 — an abbreviation-glossary line, a NEW hallucinated heading (absent at HEAD, confirmed by a stash+render heading-delta). A deterministic heading-delta scan of the 15 single-column papers had NOT flagged it as wrong (it was a real heading-count delta); only the Sonnet AI-verify against the gold identified it as a HALLUCINATION. Fix: extend `_is_single_col_relaxation_fragment` to reject any candidate containing an internal `;` or ending in `,` (a heading never does; an abbreviation/clause list always does). After the guard, plos_med net +0, all legitimate headings retained.

**How to detect next time:** (1) For any layout-dependent render heuristic, measure the discriminator across the WHOLE baseline corpus before fixing the threshold — don't tune to make one paper pass (median would have). (2) A heading-count *delta* is necessary but NOT sufficient evidence a promotion is correct — a +1 delta can be a hallucination; the AI-gold verify is what distinguishes a real subsection from a promoted glossary/table-cell line. Always AI-verify every single-column paper whose heading count changes, not just the target. (3) Heading false-positive shapes recur per call-site: bracket furniture, leading-preposition wraps, dangling-connector tails, and `;`/trailing-`,` list fragments are the standing reject set for any *relaxed* promoter.

## 2026-06-18 · v2.4.92 · Affiliation lines must never be promoted to subsection headings (G5d) + canary-audit clobbers phase_5d_runs

**What (fix):** `_promote_isolated_titlecase_subsection_headings` now consults `_looks_like_affiliation_line` and refuses to promote any academic-affiliation line to a `### ` heading. Signature (general, never paper identity): a unit-phrase head (`Department/School/Faculty/Division/Institute/Centre/Center/Laboratory/College/University of <Cap>`) OR a proper-noun phrase ending in `University/College/Institute/Hospital/Polytechnic` (optional trailing `(ACRONYM)`). Guard runs BEFORE the chain-promotion bypass so it holds on every path. Fixes canary `chandrashekar_2023_mp`'s `### Department of Philosophy, Lake Forest College`.

**Why it slipped past the masthead strip:** `_strip_frontmatter_masthead_block` only cleans the H1 → first-`##` zone. Column-interleave serialised chandrashekar's two-column title block out of order, dropping the second affiliation right AFTER `## Abstract` — past the zone. The strip can't reach it, and the short Title-Case shape then matched the heading promoter. The guard is the correct independent backstop: an affiliation is masthead furniture regardless of where interleave scattered it, so it is never a section heading. Demoting (not stripping) is the minimal fix — the affiliation text is preserved as body; its body-text presence is a separate, lower-severity pre-existing metadata-leak (masthead strip can't reach past `##`), queued separately.

**Anchored to zero-collateral evidence (the discipline for any heading-promotion change):** before shipping, (1) scan EVERY real heading in the AI-gold corpus against the new reject regex — here 47 golds / 2226 headings → 0 false positives; (2) deterministic corpus render-diff with the guard live vs monkeypatch-bypassed over the canary + a cross-publisher sample → only the target paper changed (the one heading), all others byte-identical. End-anchor the institution keyword (`X University$`) rather than match it mid-line — broadening to trailing tokens would FP on plausible headings like "The College Years". MIT / "Imperial College London" (keyword mid-line) are intentionally NOT matched (documented limitation; worst case is a missed demotion, never a mangled heading).

**Process trap — the pre-commit canary-audit hook overwrites `phase_5d_runs`:** `~/.claude/skills/_shared/iterate-loop/canary-audit.sh` (run by the pre-commit hook) writes its own regression-only verdicts into the shared run-meta `phase_5d_runs`, replacing manually-recorded AI-verify entries. Its "PASS-for-gate" means *no NEW regression* (ledger open=0), NOT *paper matches gold*. After ANY commit, re-read `phase_5d_runs` and re-record the truthful per-paper AI-verify verdicts before running `iterate-gate.sh --cycle N` — otherwise a genuinely-FAIL corpus (pre-existing tables) reads as PASS and I3 wrongly stays green. The two verdict semantics (regression-gate vs verdict-on-truth) must never be conflated.

## 2026-06-18 · cycle 3 · Caption-follows heading guard ATTEMPTED + REVERTED (no release) — instrument promoter INPUT + full-corpus gate is non-negotiable

**Outcome: NO ship.** Tried to demote maier_2023_collabra `### Identifiable victim` (a Figure 2 panel label promoted to a heading). Two render-layer signals attempted, both failed; reverted to v2.4.92 HEAD. The "cell/condition-label promoted to heading" class is confirmed entangled with table-content-as-prose and is NOT cleanly fixable at the render layer.

**Attempt 1 (lowercase-continuation) MISSED — instrument the promoter INPUT, not the final .md.** A render heuristic inside `_promote_isolated_titlecase_subsection_headings` sees the PROMOTER-INPUT text, whose line adjacency DIFFERS from the final rendered .md (later passes relocate figure captions / splice tables). I first built "next line starts lowercase → demote" from the FINAL output (bad heading followed by lowercase continuation) — but at promoter-input the next line is the capital-F figure caption, so it caught nothing. **To find a render-pass guard's real trigger, monkeypatch-wrap the function and print (prev, candidate, next) from the text IT receives; never infer from the final .md.**

**Attempt 2 (caption-follows: demote if next line is a `Figure N`/`Table N` caption) OVER-REACHED — the full-corpus gate caught it.** It caught the target, and a bounded 11-paper diff showed only maier changing (looked clean). The FULL 48-paper guard-live-vs-bypassed diff then demoted 4 LEGITIMATE headings that simply precede a table/figure: xiao "Materials and manipulations"/"Confirmatory analysis"/"Choice set", amd_2 "Descriptive Statistics", sci_rep_1 "Essential characteristics…"/"The association between DASH and BMD", ieee "DoS". A heading whose section contains a table is common; no text-only signal separates it from a figure panel label. **A bounded sample gives false confidence — ALWAYS run the guard-live-vs-bypassed render-diff over the WHOLE corpus before trusting a heading-promotion change (rule 19). The FP pattern lives in the long tail.**

**Re-scope note (heterogeneous defect class):** the "cell/condition-label promoted to heading" class is NOT one bug — 5 of 6 instances (ip_feldman "Reasons for change", chandrashekar "IV2: No-default"/"Participation rate", maier "Without joint condition [S1]"/"Target article") are table/supplementary content dumped into the prose stream and belong with the table-extraction cluster; the 6th (caption-adjacent panel label) has no clean render-layer signal either. Fold the whole class into the table-extraction work; do not chase it with a render guard.

## 2026-06-20 · docpluckapp (frontend, NOT the library) · daily-digest cron "Daily dispatch failed" = transient Neon, not a logic bug → withDbRetry

**What (fix):** `api/cron/daily-digest` intermittently logged "Daily dispatch failed" (one-error admin digest email). Ground truth came from prod `system_logs.context.errorStack` (the logger persists `errorName`/`errorMessage`/`errorStack`; queried read-only via the Neon `DATABASE_URL` in `PDFextractor/frontend/.env.local`): two failed runs (06-17, 06-18) were transient **Neon serverless** errors — `terminating connection due to administrator command` (connection recycled on scale-to-zero) and a control-plane HTTP 500 tagged `"neon:retryable":true` — thrown at DIFFERENT queries, with adjacent days succeeding. NOT a logic bug: both unattended crons fire ~15 sequential neon-http calls at 03:00/09:00 UTC against likely-cold compute and the driver does no retries, so one blip aborts the whole run (and Vercel Cron does not re-run failed crons). Fix: new `frontend/src/lib/db-retry.ts` (`withDbRetry`/`isRetryableDbError` — 3 attempts, 250/500ms backoff, retries ONLY transient/connection-class signatures, never app errors) wrapping every DB call in `notifications/dispatch.ts` + `admin/blob-cleanup/route.ts` + the in-band `sendEmail` (safe to replay — `email_events` ON CONFLICT de-dupes). Regression test `frontend/src/lib/db-retry.test.ts` via `node --test` (Node 26 strips TS natively → zero new deps; first frontend unit test + `npm test` script; excluded from `next build` via tsconfig). Shipped commit `ea86e85`; post-deploy `?dryRun=1` smoke = HTTP 200 + clean DispatchResult.

**How to detect next time:** (1) The admin digest aggregates the PREVIOUS 24h, so a "1 error" email naming `api/cron/daily-digest` is usually the prior day's transient blip, not a live outage — before theorizing, query `system_logs` for the real `errorName`/`errorStack` (it's `NeonDbError`, often `neon:retryable:true`). (2) ANY unattended Vercel cron doing a burst of neon-http queries needs `withDbRetry`: Neon scale-to-zero WILL recycle a connection mid-run and there is no driver-level retry. (3) `next build` here does NOT run eslint (Next 16 — see card `nextjs-16-build-does-not-run-eslint`), so a red `npm run lint` does not block deploy; keep the lint gate green separately for `/ship`.

## RC-T table prose-contamination has TWO independent paths — fix BOTH (2026-06-22, v2.4.96 + v2.4.97)

**What:** Camelot-absorbed body prose reaches the rendered `.md` through TWO separate table channels, and fixing one leaves the other dumping prose (same shape as the glyph-3-channels trap). (1) The STRUCTURED `<table>` (cells>0) when Camelot folds prose into a `<th>` — fixed v2.4.96 (RC-T Option A) in `render.py::_strip_phantom_camelot_tables`. (2) The UNSTRUCTURED raw_text fallback (cells=0) via `extract_structured._extract_table_body_text` — fixed v2.4.97 (RC-T Layer-2): a Note-anchor trims prose after a table's `Note:` footnote, and a degenerate-prose guard suppresses an all-prose fallback.

**How to detect:** after ANY table-prose fix, render an affected paper and grep BOTH `<table>…</table>` blocks AND ```unstructured-table``` fenced blocks for body prose. A fix that only cleans `<table>` leaves the raw_text fallback swallowing Results/Discussion prose (chan_feldman T9 was a verbatim duplicate of `## Discussion` until v2.4.97).

**FP-safety (the discriminator that survives the hypotheses trap):** legit degraded tables ALSO wrap sentences (hypotheses "a There is a positive association…"), so "is it a wrapped sentence?" is NOT usable. Key on the LEADING token: real cells start with a header/label/number/single-letter item marker; only a region-overshoot-into-prose block starts with a lowercase multi-letter continuation word. NEVER key on bbox-size (landscape tables are tall too). The `Note:` footnote is the table-END anchor (academic-table invariant).

**Combined-ship note:** v2.4.97 combined this with a concurrent session's DP-2/DP-5 flatten fixes (one working tree, two Claude sessions). Stage EXPLICIT paths only (never `git add -A`); detect the parallel stream's version bump via `git diff __init__.py`; compose because the streams touch disjoint files. See [[release-version-collision-with-parallel-uncommitted-stream]].
