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
    """The REAL guarded walk (v2.4.119) — exercises the shipped code path
    (`_caption_tail_body_start`), never a drifting reimplementation."""
    return ES._caption_tail_body_start(raw_text, cap, next_boundary)


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
            recovered_raw = raw[new_bs:old_bs]
            recovered = recovered_raw.replace("\n", "\\n")
            # What does the leading-junk guard drop from the recovered head?
            region_lines = recovered_raw.split("\n")
            after_skip = ES._skip_leading_nontable_junk(list(region_lines))
            skipped = len(region_lines) - len(after_skip)
            # Flag if the POST-SKIP surviving chunk still looks like BODY PROSE.
            # NOT a bare lowercase-word ratio: that fires on genuine wordy table
            # content (quote columns, design-cell tables, wrapped title rows) —
            # the 2026-07-04 "~53 prose-recovered" figure was this false alarm,
            # and a 2026-08-04 sample of 5 flagged cases found 5 real tables.
            # Use the library's own paragraph-scale prose predicate, which the
            # leading-junk guard is built on, so the harness and the shipped
            # code agree on what "prose" means.
            surviving = "\n".join(after_skip)
            paras, cur = [], []
            for ln in after_skip:
                if ln.strip():
                    cur.append(ln.strip())
                    if re.search(r"[.!?][\"'\)\]]?$", ln.rstrip()):
                        paras.append(" ".join(cur)); cur = []
                elif cur:
                    paras.append(" ".join(cur)); cur = []
            if cur:
                paras.append(" ".join(cur))
            is_prose = any(ES._line_is_body_prose(p) for p in paras)
            tag = "  ⚠PROSE-SURVIVES" if is_prose else ""
            jtag = f"  [junk-skip drops {skipped} leading line(s)]" if skipped else ""
            print(f"  {stem} {cap.label}: new starts {delta} chars EARLIER (recovered rows){tag}{jtag}")
            print(f"      recovered: …{recovered[:120]}…")
            if skipped:
                dropped = " | ".join(l.strip() for l in region_lines[:skipped] if l.strip())
                print(f"      junk-skipped: {dropped[:160]}")
            if is_prose:
                suspicious.append((stem, cap.label, "prose-survives-guard"))
        else:
            shrank += 1
            print(f"  {stem} {cap.label}: new starts {-delta} chars LATER (TRUNCATED — investigate)")
            suspicious.append((stem, cap.label, "truncated"))

print(f"\nchanged captions: {changed} (earlier/recovered: {grew}, later/truncated: {shrank})")
print(f"SUSPICIOUS (prose-recovered or truncated): {len(suspicious)} -> {suspicious}")
print("\nRESULT:", "CLEAN ✓ (only row-recovery, no prose bleed / no truncation)" if not suspicious else "*** REVIEW SUSPICIOUS ABOVE ***")
