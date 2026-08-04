"""Wide corpus FP scan for W0n (recover_p_threshold_dropped_decimal).

Runs the W0n handler over the RAW pdftotext text of every corpus PDF and
reports any paper where it changes the text — the recovery must fire ONLY
where a genuine dotless p-threshold exists. ar_apa_j_jesp_2009_12_011 is the
intended target; anything else is a false positive to investigate. (Raw
pdftotext text is the harshest FP test: it sees every `p < digits` shape the
paper contains, before any other normalize step.)
"""
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.extract import extract_pdf
from docpluck.normalize import recover_p_threshold_dropped_decimal

_VIBE_ROOT = os.environ.get("VIBE_ROOT") or os.path.expanduser("~/Vibe")
CORPUS = os.path.join(_VIBE_ROOT, "MetaScienceTools", "PDFextractor", "test-pdfs")
if not os.path.isdir(CORPUS):
    sys.exit(f"FATAL: corpus dir not found: {CORPUS} (set VIBE_ROOT?) — refusing to report a false CLEAN on 0 PDFs")
pdfs = sorted(glob.glob(os.path.join(CORPUS, "**", "*.pdf"), recursive=True))
if not pdfs:
    sys.exit("FATAL: 0 PDFs in corpus — refusing to report a false CLEAN")
print(f"scanning {len(pdfs)} corpus PDFs for W0n false positives...\n")

TARGET_STEM = "ar_apa_j_jesp_2009_12_011"
fp_papers = []
target_hit = False
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
    d = recover_p_threshold_dropped_decimal(raw)
    if d != raw:
        is_target = stem == TARGET_STEM
        if is_target:
            target_hit = True
        tag = "TARGET" if is_target else "*** FALSE POSITIVE ***"
        # d is raw with '.' chars inserted — count insertions via length delta.
        n_ins = len(d) - len(raw)
        fp_papers.append((stem, n_ins, is_target))
        print(f"  {tag}: {stem} ({n_ins} decimal point(s) inserted)")
        # Print each insertion context for inspection.
        i = j = 0
        while i < len(raw) and j < len(d):
            if raw[i] == d[j]:
                i += 1
                j += 1
                continue
            ctx = d[max(0, j - 55): j + 45].replace("\n", "\\n")
            print(f"      …{ctx}…")
            j += 1  # skip the inserted '.'

print(f"\nscanned {scanned} PDFs.")
non_target_fps = [s for s, _, ist in fp_papers if not ist]
print(f"target ({TARGET_STEM}) recovered: {target_hit}")
print(f"NON-TARGET false positives: {len(non_target_fps)} -> {non_target_fps}")
print("\nRESULT:", "CLEAN ✓" if not non_target_fps else "*** FALSE POSITIVES ABOVE ***")
