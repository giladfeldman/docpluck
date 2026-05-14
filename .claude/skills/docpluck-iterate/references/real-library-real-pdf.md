# Test the real library against real PDFs, never simulated proxies

> Loaded on demand from SKILL.md Phase 5. This is the recurring trap; read every cycle.

## The trap

Every cycle, the cheap, fast, satisfying-feeling instinct is to write a regression test like this:

```python
def test_synthesize_intro_keywords_cut_at_first_paragraph_break():
    text = (
        "Pre.\n\n"
        f"ABSTRACT\n{abstract_body}\n\n"
        f"KEYWORDS {keyword_line}\n\n"
        f"{intro_p1}\n\n"
        f"{intro_p2}\n\n"
        "Results\n\nresults body."
    )
    # ... assert split is correct
```

That test gives you GREEN. It runs in 0.3 seconds. It "covers" the bug.

It is **inadequate** as the regression test for this fix.

## Why it's inadequate (the failure mode it doesn't cover)

The xiao_2021_crsp KEYWORDS overshoot bug (v2.4.15) was caused by a 2-column PDF layout where pdftotext serialized the LEFT column (ABSTRACT, KEYWORDS, first intro paragraphs) followed by the RIGHT column (sidebar metadata: "Supplemental data for this article...", "Department of Psychology, University of"). The synthesis function then cut the KEYWORDS span at the first `\n\n` past 800 chars — which landed two intro paragraphs INTO keywords, leaving the synthesized Introduction starting on right-column metadata.

A synthetic test that builds `text = "...KEYWORDS short_line\n\nintro_p1\n\nintro_p2..."` exercises the helper's branch behavior but NOT the bug surface. The actual bug needed:

1. A two-column PDF layout (left/right serialization)
2. pdftotext's actual reading-order quirks  
3. The exact whitespace patterns pdftotext emits (single vs double `\n`)
4. The interaction between F0 footnote stripping, S5 minus-sign normalization, S9 page-number stripping, and `_synthesize_introduction_if_bloated_front_matter`
5. The downstream renderer's behavior on the resulting section spans

Synthesized text has NONE of those. It tests a contract (the helper's branch logic) — not the bug.

## The required pattern

For every cycle that fixes a real-paper defect, ship TWO classes of test:

### Contract test (the synthetic helper test — useful but not the gate)

```python
def test_synthesize_intro_keywords_cut_at_first_paragraph_break():
    # synthetic text exercising the branch behavior
    ...
```

Useful for: pinning the helper's contract; fast feedback during iteration; catching obvious regressions in the helper's branching.

### Real-PDF regression test (the actual gate)

```python
def test_xiao_keywords_intro_boundary_real_pdf():
    """Regression test for v2.4.15: xiao_2021_crsp had KEYWORDS overshoot
    pulling 2 intro paragraphs into the KEYWORDS section.

    Runs the FULL library (extract_pdf → normalize → sections) against the
    actual PDF and asserts the section boundaries are correct.
    """
    pdf_path = Path(__file__).parent / "fixtures" / "real_pdfs" / "xiao_2021_crsp.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"fixture not present: {pdf_path}")  # gracefully skip in CI without fixtures

    pdf_bytes = pdf_path.read_bytes()
    from docpluck.render import render_pdf_to_markdown
    md = render_pdf_to_markdown(pdf_bytes)

    # The KEYWORDS section should contain only the keyword line, NOT intro paragraphs
    kw_start = md.index("## KEYWORDS")
    intro_start = md.index("## Introduction")
    kw_body = md[kw_start:intro_start]

    assert "Decoy effect; decision reversibility; regret" in kw_body
    assert "Human choice behaviors are susceptible" not in kw_body, (
        "KEYWORDS section should NOT contain the first intro paragraph "
        "(v2.4.15 regression — was absorbing intro paragraphs due to 800-char cut)"
    )

    # The Introduction should begin with the first real intro paragraph
    intro_body = md[intro_start:intro_start + 500]
    assert "Human choice behaviors are susceptible" in intro_body, (
        "Introduction should begin with first intro paragraph"
    )
```

This is the **actual gate**. It exercises the full library pipeline on the actual PDF. It catches:

- The two-column-layout serialization
- pdftotext's real whitespace output
- The interaction between normalize / sections / render
- The bug surface, not just a synthetic contract

## Operational details

### Fixtures
- Real PDFs live in `../PDFextractor/test-pdfs/<style>/<paper>.pdf` (NOT in the library repo — per memory `feedback_no_pdfs_in_repo`, PDFs must be gitignored).
- Regression tests resolve fixtures via `Path(__file__).parent / "fixtures" / "real_pdfs" / "<paper>.pdf"` with a `pytest.skip` fallback if the fixture isn't present (so the test suite passes on CI without the corpus).
- The test resolves via the same path-resolution logic as `tests/test_extract_pdf_structured.py::_resolve_fixture` (which uses `tests/fixtures/structured/MANIFEST.json`). Mirror that pattern.

### Naming
- Real-PDF regression tests have `_real_pdf` suffix in the function name: `test_xiao_keywords_intro_boundary_real_pdf`.
- Synthetic contract tests do NOT — they have descriptive names: `test_synthesize_intro_keywords_cut_at_first_paragraph_break`.
- This naming makes it grep-discoverable: `pytest -k "real_pdf"` runs the real-PDF gate; `pytest -k "not real_pdf"` runs only fast contract tests.

### What goes in a real-PDF test
- Always import the PUBLIC library entry point (`render_pdf_to_markdown`, `extract_pdf_structured`, `extract_sections`). Never test internal helpers via a real PDF — that's a contract test domain.
- Assert on USER-VISIBLE properties: section boundaries, text presence in named sections, table cells, figure captions. Not internal state.
- One real-PDF test per defect class. Don't sprawl.

### Speed
- A real-PDF test takes 0.5–8 seconds depending on PDF size + whether it touches Camelot.
- Mark slow Camelot-bearing tests with `@pytest.mark.slow` and skip in the fast-iteration pytest invocation (`-m "not slow"`), but include in Phase 5b (broad pytest) and Phase 5c (baseline).

## Detection (during code review)

Before merging a cycle, grep the cycle's tests for these red flags:

| Red flag | Required action |
|----------|-----------------|
| Test body builds `text = "..." + "..."` with section names | Add a `_real_pdf` counterpart |
| Test body uses `<paper>.pdf` fixture but only checks `len(md) > 0` | Tighten assertions to USER-VISIBLE properties |
| Test imports `docpluck.sections.core._synthesize_*` (private helper) | OK as a contract test; ALSO need a `_real_pdf` test using public API |
| No new test added but a bug was claimed fixed | BLOCK — spine R2 will catch this in postflight |

The cycle's `tests_added` array in run-meta should ideally show BOTH a contract test path AND a real-PDF test path. One of each.

## When real-PDF testing is genuinely impossible

Rare. Document explicitly in the LEARNINGS entry:

```
### Edge Cases
- Bug only reproduces on a specific Adobe-rendered PDF (closed-access journal X).
  Cannot ship the PDF with the test fixtures (license). Mitigated by:
  (a) reproducing the pdftotext output as a fixture text file under
      tests/fixtures/text_snapshots/<paper>.txt
  (b) test runs against the text snapshot, not synthesized text
  (c) the text snapshot is committed (it's just text, no copyright issue)
```

This is still better than synthesized text — it's the ACTUAL pdftotext output, just not the actual PDF. Use this fallback only when the PDF cannot be staged in the test fixtures.

## Composition with the three-tier chain

- Real-PDF Tier 1 test verifies the library standalone.
- Phase 5.5 Tier 2 verifies the service serves the same output.
- Phase 7c Tier 3 verifies prod serves the same output.

Each tier exercises the same library code against the same PDF and must produce the same result. The real-PDF test is the foundation; the parity chain extends its assertion across deployment surfaces.
