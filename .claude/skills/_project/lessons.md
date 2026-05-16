
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
