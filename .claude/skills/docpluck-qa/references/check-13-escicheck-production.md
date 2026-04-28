# 13. ESCIcheck 10-PDF Verification — Production Webapp (CRITICAL)

_Extracted from [../SKILL.md](../SKILL.md). Full procedure lives here._


Tests the full production stack end-to-end. Requires a valid API key from the live app.

```bash
python -c "
import os, re, json, requests

API_KEY = os.environ.get('DOCPLUCK_API_KEY', '')
if not API_KEY:
    print('SKIP: set DOCPLUCK_API_KEY env var to run production check')
    exit(0)

ESCI_DIR = r'C:\Users\filin\Dropbox\Vibe\ESCIcheck\testpdfs\Coded already'
pdfs = sorted(os.listdir(ESCI_DIR))[:10]

results = []
for fname in pdfs:
    path = os.path.join(ESCI_DIR, fname)
    with open(path, 'rb') as f:
        content = f.read()
    try:
        r = requests.post(
            'https://docpluck.vercel.app/api/extract?normalize=academic&quality=true',
            files={'file': (fname, content, 'application/pdf')},
            headers={'Authorization': f'Bearer {API_KEY}'},
            timeout=120
        )
        if r.status_code != 200:
            results.append({'file': fname[:50], 'status': 'FAIL', 'error': f'HTTP {r.status_code}'})
            continue
        d = r.json()
        pvalues = re.findall(r'[pP]\s*[<=>]\s*\.?\d+', d.get('text',''))
        results.append({
            'file': fname[:50],
            'status': 'PASS' if d.get('quality',{}).get('score',0) >= 60 and len(pvalues) >= 5 else 'FAIL',
            'chars': d.get('metadata',{}).get('chars',0),
            'quality': d.get('quality',{}).get('score',0),
            'pvalues': len(pvalues),
            'cached': d.get('metadata',{}).get('cached', False),
        })
    except Exception as e:
        results.append({'file': fname[:50], 'status': 'FAIL', 'error': str(e)})

for r in results:
    if 'error' in r:
        print(f\"FAIL | {r['file']} | {r['error']}\")
    else:
        cached_note = ' [cached]' if r.get('cached') else ''
        print(f\"{r['status']} | {r['file']} | {r['chars']:,}ch | q={r['quality']} | p={r['pvalues']}{cached_note}\")

passed = sum(1 for r in results if r.get('status') == 'PASS')
print(f'Production: {passed}/{len(results)} passed')
"
```

**AI verification criteria** — same as Check 5, plus:
- [ ] Auth accepted (not 401/403)
- [ ] Cache working on re-run (second run shows `[cached]`)

---

---

