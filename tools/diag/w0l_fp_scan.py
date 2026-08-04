"""Wide corpus FP scan for W0l (recover_times_design_notation +
recover_times_wrapped_interaction).

Runs the two W0l handlers over the RAW pdftotext text of many corpus PDFs and
reports any paper where they change the text — the recovery must fire ONLY where
a genuine corrupted '×' exists. efendic is the intended target; anything else is
a false positive to investigate. (Running on raw pdftotext text is the harshest
FP test: it sees every '3' the paper contains, before any other normalize step.)
"""
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.extract import extract_pdf
from docpluck.normalize import (
    recover_times_design_notation,
    recover_times_wrapped_interaction,
)

_VIBE_ROOT = os.environ.get("VIBE_ROOT") or os.path.expanduser("~/Vibe")
CORPUS = os.path.join(_VIBE_ROOT, "MetaScienceTools", "PDFextractor", "test-pdfs")
if not os.path.isdir(CORPUS):
    sys.exit(f"FATAL: corpus dir not found: {CORPUS} (set VIBE_ROOT?) — refusing to report a false CLEAN on 0 PDFs")
pdfs = sorted(glob.glob(os.path.join(CORPUS, "**", "*.pdf"), recursive=True))
print(f"scanning {len(pdfs)} corpus PDFs for W0l false positives...\n")

fp_papers = []
efendic_hit = False
scanned = 0
for p in pdfs:
    stem = os.path.splitext(os.path.basename(p))[0]
    try:
        with open(p, "rb") as fh:
            res = extract_pdf(fh.read())
        # extract_pdf returns (text, metadata) — take the text channel.
        raw = res[0] if isinstance(res, tuple) else res
    except Exception as exc:
        print(f"  SKIP {stem}: {exc}")
        continue
    scanned += 1
    d1 = recover_times_design_notation(raw)
    d2 = recover_times_wrapped_interaction(d1)
    if d2 != raw:
        # Show what changed (the char positions where '3' became '×').
        changes = sum(1 for a, b in zip(raw, d2) if a != b)
        is_efendic = "efendic" in stem.lower()
        if is_efendic:
            efendic_hit = True
        tag = "TARGET" if is_efendic else "*** FALSE POSITIVE ***"
        fp_papers.append((stem, changes, is_efendic))
        print(f"  {tag}: {stem} ({changes} char(s) changed)")
        # Print the changed contexts for inspection
        for i, (a, b) in enumerate(zip(raw, d2)):
            if a != b:
                ctx = d2[max(0, i - 45): i + 45].replace("\n", "\\n")
                print(f"      …{ctx}…")

print(f"\nscanned {scanned} PDFs.")
non_target_fps = [s for s, _, isef in fp_papers if not isef]
print(f"efendic recovered: {efendic_hit}")
print(f"NON-TARGET false positives: {len(non_target_fps)} -> {non_target_fps}")
print("\nRESULT:", "CLEAN ✓" if not non_target_fps else "*** FALSE POSITIVES ABOVE ***")
