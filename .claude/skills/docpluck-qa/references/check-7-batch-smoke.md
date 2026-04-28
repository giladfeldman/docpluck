# 7. Batch Extraction Smoke Test (test-pdfs/)

_Extracted from [../SKILL.md](../SKILL.md). Full procedure lives here._

```bash
cd C:\Users\filin\Dropbox\Vibe\PDFextractor\service && python -c "
import os
from docpluck import extract_pdf
base = '../test-pdfs'
if os.path.exists(base):
    failures = []
    count = 0
    for root, dirs, files in os.walk(base):
        for f in files:
            if f.endswith('.pdf'):
                count += 1
                with open(os.path.join(root, f), 'rb') as fh:
                    content = fh.read()
                try:
                    text, method = extract_pdf(content)
                    if text.startswith('ERROR:') or len(text) < 100:
                        failures.append(f'{f}: {text[:80] if text.startswith(\"ERROR:\") else len(text)+\" chars\"}')
                except Exception as e:
                    failures.append(f'{f}: {e}')
    if failures:
        print(f'Batch: FAIL ({len(failures)}/{count})')
        for f in failures: print(f'  {f}')
    else:
        print(f'Batch: PASS ({count}/{count} PDFs)')
else:
    print('Batch: SKIP (no test-pdfs/ directory)')
"
```

---

