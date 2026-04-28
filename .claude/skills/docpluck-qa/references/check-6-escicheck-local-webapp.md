# 6. ESCIcheck 10-PDF Verification — Local Webapp (CRITICAL)

_Extracted from [../SKILL.md](../SKILL.md). Full procedure lives here._


Requires local service running on port 6117 AND frontend on port 6116. Test via the API endpoint.

First start the service (if not running):
```bash
cd C:\Users\filin\Dropbox\Vibe\PDFextractor\service && uvicorn app.main:app --port 6117 --reload &
```

Then run:
```bash
python -c "
import os, re, json, requests

ESCI_DIR = r'C:\Users\filin\Dropbox\Vibe\ESCIcheck\testpdfs\Coded already'
pdfs = sorted(os.listdir(ESCI_DIR))[:10]

# Test via the Python service directly (bypasses auth)
results = []
for fname in pdfs:
    path = os.path.join(ESCI_DIR, fname)
    with open(path, 'rb') as f:
        content = f.read()
    try:
        r = requests.post(
            'http://localhost:6117/extract?normalize=academic&quality=true',
            files={'file': (fname, content, 'application/pdf')},
            timeout=120
        )
        if r.status_code != 200:
            results.append({'file': fname[:50], 'status': 'FAIL', 'error': f'HTTP {r.status_code}: {r.text[:100]}'})
            continue
        d = r.json()
        pvalues = re.findall(r'[pP]\s*[<=>]\s*\.?\d+', d['text'])
        results.append({
            'file': fname[:50],
            'status': 'PASS' if d['quality']['score'] >= 60 and len(pvalues) >= 5 else 'FAIL',
            'chars': d['metadata']['chars'],
            'engine': d['metadata']['engine'],
            'quality': d['quality']['score'],
            'pvalues': len(pvalues),
            'time_ms': d['metadata']['extraction_time_ms'],
        })
    except Exception as e:
        results.append({'file': fname[:50], 'status': 'FAIL', 'error': str(e)})

for r in results:
    if 'error' in r:
        print(f\"FAIL | {r['file']} | {r['error']}\")
    else:
        print(f\"{r['status']} | {r['file']} | {r['chars']:,}ch | q={r['quality']} | p={r['pvalues']} | {r['time_ms']}ms\")

passed = sum(1 for r in results if r.get('status') == 'PASS')
print(f'Service: {passed}/{len(results)} passed')
"
```

**AI verification criteria** — same as Check 5 plus:
- [ ] HTTP 200 for all 10 PDFs
- [ ] `time_ms` < 30,000 (no timeout)
- [ ] `engine` field present

---

