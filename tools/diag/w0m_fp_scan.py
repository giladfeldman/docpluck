"""W0m corpus FP scan: which papers have layout-proven beta coefficients?

For every corpus PDF, compute _layout_beta_coefficients(layout) — the count of
'b' chars in a math-symbol font (AdvPSMP*) sitting immediately before '=' on
their visual line. Papers with count 0 are byte-untouched by W0m (the recovery
is layout-gated). For papers with count > 0, ALSO count the `b = <coef>` text
slots so we can see how many flips would fire, and print the flip contexts for
gold-verification. ar_apa is the expected target (5).
"""
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.extract import extract_pdf
from docpluck.extract_layout import extract_pdf_layout
from docpluck.normalize import _layout_beta_coefficients, _BETA_COEF_SLOT_RE

CORPUS = os.path.expanduser(r"~/Vibe/MetaScienceTools/PDFextractor/test-pdfs")
pdfs = sorted(glob.glob(os.path.join(CORPUS, "**", "*.pdf"), recursive=True))
print(f"scanning {len(pdfs)} corpus PDFs for W0m layout-beta signals...\n", flush=True)

hits = []
scanned = 0
for p in pdfs:
    stem = os.path.splitext(os.path.basename(p))[0]
    try:
        with open(p, "rb") as fh:
            data = fh.read()
        layout = extract_pdf_layout(data)
    except Exception as exc:
        print(f"  SKIP {stem}: {exc}", flush=True)
        continue
    scanned += 1
    n = _layout_beta_coefficients(layout)
    if n == 0:
        continue
    # Paper is W0m-affected: show the text-channel slots that would flip.
    res = extract_pdf(data)
    raw = res[0] if isinstance(res, tuple) else res
    slots = [m.group(0) for m in _BETA_COEF_SLOT_RE.finditer(raw)]
    hits.append((stem, n, len(slots)))
    print(f"  HIT {stem}: layout-beta count={n}, text 'b = <coef>' slots={len(slots)}", flush=True)
    for s in slots[:8]:
        print(f"      slot: {s!r}", flush=True)

print(f"\nscanned {scanned} PDFs. W0m-affected papers: {len(hits)} -> {[(h[0], h[1]) for h in hits]}")
print("RESULT:", "TARGET-ONLY ✓" if all("ar_apa" in h[0] for h in hits) else "REVIEW NON-TARGET HITS ABOVE")
