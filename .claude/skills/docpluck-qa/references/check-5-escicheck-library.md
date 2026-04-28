# 5. ESCIcheck 10-PDF Verification — Library (CRITICAL)

_Extracted from [../SKILL.md](../SKILL.md). Full procedure lives here._


This check verifies the `docpluck` library works correctly on real APA psychology papers from the ESCIcheck corpus. You (the AI) must verify each output qualitatively.

```bash
python -c "
import os, re, sys
from docpluck import extract_pdf, normalize_text, NormalizationLevel, compute_quality_score

ESCI_DIR = r'C:\Users\filin\Dropbox\Vibe\ESCIcheck\testpdfs\Coded already'
pdfs = sorted(os.listdir(ESCI_DIR))[:10]  # First 10 alphabetically

results = []
for fname in pdfs:
    path = os.path.join(ESCI_DIR, fname)
    with open(path, 'rb') as f:
        content = f.read()
    text, method = extract_pdf(content)
    if text.startswith('ERROR:'):
        results.append({'file': fname, 'status': 'FAIL', 'error': text})
        continue
    normalized, report = normalize_text(text, NormalizationLevel.academic)
    quality = compute_quality_score(normalized)
    # Extract p-values as a basic sanity check
    pvalues = re.findall(r'[pP]\s*[<=>]\s*\.?\d+', normalized)
    # Also catch agreement/reliability stats (CCC, ICC, kappa, r =) for papers that don't use p-values
    other_stats = re.findall(r'(?:CCC|ICC|kappa|chi2|r)\s*[=<>]\s*[.0-9]+', normalized)
    has_stats = len(pvalues) >= 5 or len(other_stats) >= 3
    results.append({
        'file': fname[:60],
        'chars': len(normalized),
        'method': method,
        'quality': quality['score'],
        'garbled': quality['garbled'],
        'pvalues_found': len(pvalues),
        'other_stats': len(other_stats),
        'steps': len(report.steps_applied),
        'sample': normalized[500:900].replace('\n', ' ').strip(),
        'has_stats': has_stats,
    })

for r in results:
    if 'error' in r:
        print(f'FAIL {r[\"file\"]}: {r[\"error\"]}')
    else:
        status = 'FAIL' if r['garbled'] or r['chars'] < 5000 or not r['has_stats'] else 'PASS'
        print(f'{status} | {r[\"chars\"]:,}ch | q={r[\"quality\"]} | p={r[\"pvalues_found\"]} | other={r[\"other_stats\"]} | {r[\"method\"]}')
        print(f'  FILE: {r[\"file\"]}')
        print(f'  SAMPLE: ...{r[\"sample\"]}...')
        print()
"
```

**AI verification criteria** — for each PDF you must confirm:
- [ ] `chars` ≥ 5,000 (real content extracted, not empty)
- [ ] `quality` score ≥ 60 (not garbled)
- [ ] `garbled` = False
- [ ] `pvalues_found` ≥ 5 (statistical paper has findable stats)
- [ ] `method` = `pdftotext_default` (normal extraction, no SMP issues)
- [ ] `sample` text is coherent English academic prose (not jumbled)
- [ ] No obvious column interleaving in sample (words from two columns not merged)

If any PDF fails criteria: investigate and fix before proceeding.

---

