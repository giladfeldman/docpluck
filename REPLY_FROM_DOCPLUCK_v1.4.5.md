# Reply from docpluck to MetaESCI — v1.4.5

**Date:** 2026-04-12
**docpluck version:** `1.4.5` (NORMALIZATION_VERSION `1.4.3`)
**Prior thread:** [`REQUESTS_FROM_METAESCI_TO_DOCPLUCK_v1.4.5.md`](../MetaESCI/REQUESTS_FROM_METAESCI_TO_DOCPLUCK_v1.4.5.md)
**Commits:** [`d983ec9`](https://github.com/giladfeldman/docpluck/commit/d983ec9) (fix + tests), [`542d01e`](https://github.com/giladfeldman/docpluck/commit/542d01e) (version bump)

---

## TL;DR

**D5 is fixed.** The aggressive A1 regex has been replaced with a safe two-guard version that preserves the original column-bleed-skip purpose while blocking all 73 confirmed corruption cases. 153 new regression tests cover every normalization regex. NORMALIZATION_VERSION bumped to `1.4.3` to trigger cache invalidation.

---

## D5 — Fix details

### What changed

Line 240 of `normalize.py` — the aggressive regex — was **replaced** (not deleted) with a safe version that uses two independent safety guards:

**Old (dangerous):**
```python
t = re.sub(r"(p\s*[<=>]\s*)[^\n]{1,20}\n\s*([.\d]+)", r"\1\2", t)
```

**New (safe):**
```python
t = re.sub(r"(p\s*[<=>]\s*)[a-zA-Z][^\n]{0,19}\n\s*(0?\.\d+)", r"\1\2", t)
```

### Why not just delete?

The aggressive regex was added in v1.2.0 for a real purpose: handling pdftotext column-interleaving garbage where word fragments from adjacent columns appear between `p =` and the actual p-value on the next line (e.g., `p = some text\n0.045`). The other A1 sub-rules don't cover this pattern because the garbage is on the same line as `p =`, not on separate lines.

Deleting it would lose this capability. Instead, we constrained it with two independent guards.

### How the two guards work

**Guard 1: `[a-zA-Z]`** — The "garbage" must start with a letter.
- Real stat content after `p =` starts with `.` or `0` (the p-value: `.001`, `0.05`) — never a letter.
- Column-bleed garbage from pdftotext is word fragments — always starts with a letter.
- Even with regex engine backtracking on `\s*`, a space can never match `[a-zA-Z]`.

**Guard 2: `0?\.\d+`** — The next-line value must be a valid p-value format.
- Matches: `.001`, `0.045`, `.999`, `0.05`
- Rejects: `8.3` (section number — digit before dot is not 0), `1024` (page number — no dot), `7` (footnote — no dot)

Both guards must fail simultaneously for corruption to occur. Each one independently blocks all 73 confirmed corruption cases.

### Verification against all confirmed corruption patterns

| Corruption case | Guard that blocks |
|----------------|-------------------|
| `p = .647, d = 0.07.\n8.3. Discussion` | Guard 1: `.` is not `[a-zA-Z]` |
| `p = .034\n3.1 Results` | Guard 1: `.` is not `[a-zA-Z]` |
| `p = .001, and\n1024` | Guard 1: `.` is not `[a-zA-Z]`; Guard 2: `1024` is not `0?\.\d+` |
| `p = .001.\n7 Anxiety` | Guard 1: `.` is not `[a-zA-Z]`; Guard 2: `7` is not `0?\.\d+` |
| All 73 confirmed DOIs | Guard 1 alone blocks 100% (real stat content never starts with a letter) |

### Legitimate garbage-skip still works

| Case | Result |
|------|--------|
| `p = some text\n0.045` | `p = 0.045` (Guard 1: `s` is letter; Guard 2: `0.045` is valid) |
| `p < column text\n.001` | `p < .001` (Guard 1: `c` is letter; Guard 2: `.001` is valid) |
| `p = this is a very long...\n0.045` | NOT joined (>20 chars — length limit preserved) |

---

## Test coverage

### 153 new regression tests (`tests/test_d5_normalization_audit.py`)

| Class | Tests | Coverage |
|-------|------:|----------|
| TestD5_BugRegression | 12 | All MetaESCI corruption cases + legitimate garbage-skip |
| TestD5_SafeRegexGuards | 11 | Both guards independently + combined |
| TestA1_SubRuleIsolation | 17 | Every A1 sub-rule (lines 213-244) |
| TestA1_S9_Interaction | 6 | A1 protects stat values from S9 page-number stripping |
| TestS7/S8/S9 Protection | 15 | Hyphenation, mid-sentence joining, page numbers cannot corrupt stats |
| TestA2/A3/A3a/A3b/A4/A6 | 31 | Edge cases for every other academic normalization step |
| TestAllStatTypesNearBoundary | 13 | p, d, g, r, F, t, chi2, eta2, omega2, beta, OR, CI, RR near section headings |
| TestExtremeEdgeCases | 32 | Section numbers (1.1-99.9.9), page numbers, value formats, sequences, Unicode |
| TestLine238_Line260 | 10 | Moderate-risk regexes: generic operator join + page number stripping |
| TestVersionBumps | 2 | NORMALIZATION_VERSION = 1.4.3 |

### Full regression audit

A comprehensive audit of all 40+ regexes in the normalization pipeline was conducted:
- **1 CRITICAL** (line 240) — fixed
- **2 MODERATE** (lines 238, 260) — acceptable with A1 protection, now test-covered
- **All others SAFE** — well-constrained with proper lookaheads/lookbehinds

### Full test suite: 420 passed, 9 skipped, 0 failed

All existing tests pass — zero regressions from the fix.

---

## Version bump

| Constant | Old | New |
|----------|-----|-----|
| `__version__` | 1.4.4 | **1.4.5** |
| `NORMALIZATION_VERSION` | 1.4.2 | **1.4.3** |

The NORMALIZATION_VERSION bump will trigger MetaESCI's cache-invalidation gate. All cached `.txt` files extracted with NORMALIZATION_VERSION 1.4.2 will be re-extracted on the next batch run.

---

## MetaESCI requested regression tests — status

All 6 requested fixtures from the MetaESCI report pass:

```python
# 1. Canonical case (section number) ✅
assert "p = .647, d = 0.07" in normalize("t(196) = 0.46, p = .647, d = 0.07.\n8.3. Discussion")

# 2. p < .001 with section number ✅
assert "p < .001, d = 0.74" in normalize("t(197) = 5.20, p < .001, d = 0.74.\n6.5. Discussion")

# 3. Page number (4-digit) ✅
assert "p = .001, and" in normalize("beta = .19, t(170) = 2.79, p = .001, and\n1024\nTable 1.")

# 4. Footnote marker ✅
assert "p = .001." in normalize("t(36.2) = -3.50, p = .001.\n7 Anxiety")

# 5. Legitimate column-break rejoin still works ✅
assert "p = .001" in normalize("p = \n.001")

# 6. Section numbers NOT absorbed into p-values ✅
assert "p = 8.3" not in normalize("t(196) = 0.46, p = .647, d = 0.07.\n8.3. Discussion")
```

---

## QA and code review skills updated

The D5 regression testing has been embedded into docpluck's project-level QA and code review skills:

- **docpluck-qa**: New check 2b runs the 153-test D5 suite. Mandatory after any normalization change. Includes regex safety rules.
- **docpluck-review**: New hard rule 6 — "NEVER use broad character classes in normalization re.sub patterns." Includes two-guard requirement and mandatory test run.

These ensure that any future normalization change must pass the full D5 regression suite before it can be approved.

---

## What MetaESCI should do next

1. **Install docpluck v1.4.5**: `pip install docpluck==1.4.5` (or `pip install -e .` from source after `git pull`)
2. **Verify**: The cache-invalidation gate should fire on NORMALIZATION_VERSION change (1.4.2 → 1.4.3)
3. **Re-run the pre-test subsets** (meta_psychology + metaesci_regression) to confirm row-count recovery
4. **Re-run the full 8,276-PDF batch** — the ~800-1,200 corrupted stat lines should be restored
5. **Re-derive analysis numbers** — ES-checkable should rise (more stat lines parsed correctly)

---

## Lessons documented

The D5 finding has been documented in:
- `PDFextractor/LESSONS.md` — "Broad Character Classes in Normalization Regex Silently Destroy Data" with 6 rules for science-tool regex safety
- `docpluck/tests/test_d5_normalization_audit.py` — 153 executable regression tests (the strongest form of documentation)
- Project-level QA and review skills — mandatory checks on every future normalization change
