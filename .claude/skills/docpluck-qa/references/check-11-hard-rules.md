# 11. Hard Rules Verification

_Extracted from [../SKILL.md](../SKILL.md). Full procedure lives here._

```bash
cd C:\Users\filin\Dropbox\Vibe\MetaScienceTools\PDFextractor\service && python -c "
import re

# Rule 1: No -layout flag in pdftotext calls (check library)
import docpluck.extract as ext_mod
import inspect
source = inspect.getsource(ext_mod)
calls = re.findall(r'subprocess\.run\(\s*\[.*?\]', source, re.DOTALL)
for call in calls:
    assert '-layout' not in call, f'BLOCKER: -layout in {call}'
print('Rule 1 (no -layout): PASS')

# Rule 2: No AGPL imports in library or service
import docpluck.normalize as norm_mod, docpluck.quality as qual_mod
for name, mod in [('normalize', norm_mod), ('quality', qual_mod), ('extract', ext_mod)]:
    src = inspect.getsource(mod)
    assert 'pymupdf4llm' not in src, f'AGPL import in {name}'
    assert 'column_boxes' not in src, f'AGPL method in {name}'
with open('app/main.py') as f:
    main_src = f.read()
assert 'pymupdf4llm' not in main_src, 'AGPL import in main.py'
print('Rule 2 (no AGPL): PASS')

# Rule 3: U+2212 normalization exists in library (check file bytes to avoid encoding issues)
import docpluck.normalize as _nm_mod
with open(_nm_mod.__file__, 'rb') as _f:
    _norm_bytes = _f.read()
assert b'\xe2\x88\x92' in _norm_bytes, 'U+2212 normalization missing'  # U+2212 as UTF-8 bytes
print('Rule 3 (U+2212 norm): PASS')

# Rule 4: Library version is internally consistent (__init__.py == pyproject.toml).
# (Do NOT freeze a literal version here — it rots. This checks the two in-repo
#  sources agree; the cross-repo app-pin sync is qa check 11b, see note below.)
import docpluck, re, pathlib
init_ver = docpluck.__version__
pyproject = (pathlib.Path(docpluck.__file__).resolve().parent.parent / 'pyproject.toml').read_text(encoding='utf-8')
proj_ver = re.search(r'(?m)^version\s*=\s*.(\d+\.\d+\.\d+)', pyproject).group(1)
assert init_ver == proj_ver, f'Version mismatch: __init__={init_ver} pyproject={proj_ver}'
print(f'Rule 4 (version consistency, __init__==pyproject=={init_ver}): PASS')
"
```

> **Cross-repo pin sync** (the app's `@v<VERSION>` pin == the library's latest released tag) is a *separate* gate — qa check **11b** and the review hard rule, both via `python scripts/check_app_pin_sync.py` (reads docpluckapp `origin/master`). Rule 4 above only checks the library's *internal* version consistency (`__init__.py` == `pyproject.toml`).

---

