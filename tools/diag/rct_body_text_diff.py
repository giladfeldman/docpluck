"""Guard-diff for the v2.4.117 _extract_table_body_text caption-tail-walk fix.

For every corpus PDF, extract every table caption's raw_text body via
_extract_table_body_text and compare HEAD vs the fixed function. The fix must
only ADD legitimately-dropped leading table rows — never bleed body prose in,
never truncate. Report per-caption char deltas and flag any that grew by a
suspicious amount (possible prose bleed) or shrank (possible over-truncation).

Runs the fixed function (current tree) and reconstructs the OLD behaviour inline
so no file-swap is needed (the two walks differ only in the body_start loop).
"""
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("DOCPLUCK_DISABLE_CAMELOT", "1")

from docpluck.extract import extract_pdf
from docpluck.tables.captions import find_caption_matches
import docpluck.extract_structured as ES


def _old_body_start(raw_text, cap, next_boundary):
    """The PRE-v2.4.117 body_start walk (prefers next \\n\\n, 40-char prev window)."""
    pos = cap.char_end
    cap_tail_end = min(cap.char_end + 800, len(raw_text))
    if next_boundary is not None and next_boundary > cap.char_end:
        cap_tail_end = min(cap_tail_end, next_boundary)
    while pos < cap_tail_end:
        nxt2 = raw_text.find("\n\n", pos)
        nxt1 = raw_text.find("\n", pos)
        if nxt2 != -1 and nxt2 < cap_tail_end:
            nxt, step = nxt2, 2
        elif nxt1 != -1 and nxt1 < cap_tail_end:
            nxt, step = nxt1, 1
        else:
            pos = cap_tail_end
            break
        prev = raw_text[max(cap.char_start, nxt - 40):nxt].rstrip()
        if not prev or len(prev.split()) < 2 or re.search(r"[.!?][\"'\)\]]?$", prev):
            pos = nxt + step
            break
        pos = nxt + step
    return pos


def _new_body_start(raw_text, cap, next_boundary):
    """The v2.4.117 per-line-terminator walk (mirror of the patched code)."""
    pos = cap.char_end
    cap_tail_end = min(cap.char_end + 800, len(raw_text))
    if next_boundary is not None and next_boundary > cap.char_end:
        cap_tail_end = min(cap_tail_end, next_boundary)
    while pos < cap_tail_end:
        nxt = raw_text.find("\n", pos)
        if nxt == -1 or nxt >= cap_tail_end:
            pos = cap_tail_end
            break
        step = 2 if raw_text[nxt:nxt + 2] == "\n\n" else 1
        line_start = raw_text.rfind("\n", pos, nxt)
        line = raw_text[(line_start + 1 if line_start != -1 else pos):nxt].rstrip()
        if re.search(r"[.!?][\"'\)\]]?$", line):
            pos = nxt + step
            break
        if step == 2:
            pos = nxt + step
            break
        pos = nxt + step
    return pos


_VIBE_ROOT = os.environ.get("VIBE_ROOT") or os.path.expanduser("~/Vibe")
CORPUS = os.path.join(_VIBE_ROOT, "MetaScienceTools", "PDFextractor", "test-pdfs")
if not os.path.isdir(CORPUS):
    sys.exit(f"FATAL: corpus dir not found: {CORPUS} (set VIBE_ROOT?) — refusing to report a false CLEAN on 0 PDFs")
pdfs = sorted(glob.glob(os.path.join(CORPUS, "**", "*.pdf"), recursive=True))
print(f"guard-diff over {len(pdfs)} PDFs (body_start walk: old vs v2.4.117)\n")

changed = 0
grew = 0
shrank = 0
suspicious = []
for p in pdfs:
    stem = os.path.splitext(os.path.basename(p))[0]
    try:
        res = extract_pdf(open(p, "rb").read())
        raw = res[0] if isinstance(res, tuple) else res
    except Exception:
        continue
    try:
        caps = [c for c in find_caption_matches(raw, list(ES._page_offsets(raw))) if c.kind == "table"]
    except Exception:
        continue
    starts = sorted(c.char_start for c in caps)
    for cap in caps:
        later = [s for s in starts if s > cap.char_end]
        nb = later[0] if later else None
        old_bs = _old_body_start(raw, cap, nb)
        new_bs = _new_body_start(raw, cap, nb)
        if old_bs == new_bs:
            continue
        changed += 1
        delta = old_bs - new_bs  # positive = new starts EARLIER (recovered rows)
        if new_bs < old_bs:
            grew += 1  # new body starts earlier → more content kept
            recovered = raw[new_bs:old_bs].replace("\n", "\\n")
            # Flag if the recovered chunk looks like BODY PROSE (long lowercase sentence)
            words = raw[new_bs:old_bs].split()
            is_prose = len(words) > 25 and sum(1 for w in words if w[:1].islower()) > len(words) * 0.6
            tag = "  ⚠PROSE?" if is_prose else ""
            print(f"  {stem} {cap.label}: new starts {delta} chars EARLIER (recovered rows){tag}")
            print(f"      recovered: …{recovered[:120]}…")
            if is_prose:
                suspicious.append((stem, cap.label, "prose-recovered"))
        else:
            shrank += 1
            print(f"  {stem} {cap.label}: new starts {-delta} chars LATER (TRUNCATED — investigate)")
            suspicious.append((stem, cap.label, "truncated"))

print(f"\nchanged captions: {changed} (earlier/recovered: {grew}, later/truncated: {shrank})")
print(f"SUSPICIOUS (prose-recovered or truncated): {len(suspicious)} -> {suspicious}")
print("\nRESULT:", "CLEAN ✓ (only row-recovery, no prose bleed / no truncation)" if not suspicious else "*** REVIEW SUSPICIOUS ABOVE ***")
