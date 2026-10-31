"""What does ``render._suppress_grid_copied_line_blocks`` remove, paper by paper?

One render per paper. The pass is wrapped: its input and output are compared,
and every removed body line is printed with the table it was attributed to, so
each removal can be read (and checked against the page) rather than counted.
A removed line that is NOT found in the rendered output afterwards (anywhere,
after the same folding the pass uses) is flagged ``NOT-IN-OUTPUT``: that would be
text lost from the document, not a duplicate removed.

    python tools/diag/grid_copy_suppression_diff.py [--limit N | --sample N] [--workers 4]
"""

from __future__ import annotations

import argparse
import difflib
import html
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.diag._corpus import baseline_corpus, coverage_line, sampled_corpus  # noqa: E402

_MARK = re.compile(r"table-text-duplicate: (\d+) lines of Table (\S+?)'s")


def _run(item):
    key, path = item
    import warnings
    warnings.filterwarnings("ignore")
    import docpluck.render as R
    seen: list[tuple[str, str]] = []
    orig = R._suppress_grid_copied_line_blocks

    def hooked(text):
        out = orig(text)
        seen.append((text, out))
        return out

    R._suppress_grid_copied_line_blocks = hooked
    try:
        md = R.render_pdf_to_markdown(Path(path).read_bytes())
    except Exception as exc:  # a crash is reported, never a silent zero
        return key, [f"  ERROR {type(exc).__name__}: {exc}"], 0
    finally:
        R._suppress_grid_copied_line_blocks = orig
    md = md if isinstance(md, str) else md[0]
    if not seen:
        return key, ["  ERROR pass never ran"], 0
    before, after = seen[-1]
    if before == after:
        return key, [], 0
    # Tags off BEFORE unescaping: an unescaped "<4.67 ..." would read as a tag.
    hay = re.sub(r"\s+", " ", R._copy_norm(html.unescape(re.sub(r"<[^>]+>", " ", md))))
    lines: list[str] = []
    lost = 0
    a, b = before.split("\n"), after.split("\n")
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        marks = [m for m in b[j1:j2] if "table-text-duplicate" in m]
        label = ",".join(f"T{m.group(2)}x{m.group(1)}" for m in map(_MARK.search, marks) if m)
        lines.append(f"  -- block {label or '?'}")
        for ln in a[i1:i2]:
            if not ln.strip():
                continue
            # A caption line's "Table N." prefix is the structured block's heading.
            norm = R._COPY_LEADING_LABEL_RE.sub("", R._copy_norm(ln))
            flag = "" if norm in hay else "  NOT-IN-OUTPUT"
            lost += bool(flag)
            # A sentence-shaped line is the one class that could be body prose a
            # capture ran into; each one is listed for reading against the page.
            words = re.findall(r"[A-Za-z][A-Za-z'-]*", ln)
            if len(words) >= 8 and sum(w.islower() for w in words) >= 0.7 * len(words):
                flag += "  PROSE-LIKE"
            lines.append(f"     - {ln[:160]}{flag}")
    return key, lines, lost


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--sample", type=int, default=None)
    args = ap.parse_args()
    corpus = sampled_corpus(args.sample) if args.sample else baseline_corpus(args.limit)
    print(coverage_line())
    n_fired = n_lost = n_err = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for key, lines, lost in ex.map(_run, [(k, str(p)) for k, p in corpus]):
            if lines:
                if any("ERROR" in ln for ln in lines):
                    n_err += 1
                else:
                    n_fired += 1
                print(key)
                for ln in lines:
                    print(ln)
            n_lost += lost
            sys.stdout.flush()
    print(f"papers={len(corpus)} fired={n_fired} errors={n_err} lines_not_in_output={n_lost}")
    print("Every PROSE-LIKE line must be read against the page before this pass ships.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
