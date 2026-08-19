"""Does the render post-process chain DELETE published content?

The numeric rules in `normalize.py` were audited exhaustively on 2026-08-14 —
every one classified NOTATION vs REPAIR, every firing site counted across 297
English papers. **The same question was never asked of the render channel**,
and the render channel is the one that reaches the user.

`render_pdf_to_markdown()` chains 54 `md = fn(md)` calls and returns a bare
`str`. There is no report object, so a step that deletes a line deletes it with
ZERO telemetry: no count, no key in `changes_made`, nothing a consumer could
read. `A3a` at least reports a (mislabelled) count; this channel reports
nothing at all.

Six of the 54 steps can remove content rather than transform it:

    _dedupe_h2_sections
    _suppress_orphan_table_cell_text
    _strip_phantom_camelot_tables                    docstring: "intentionally LOSSY"
    _suppress_inline_duplicate_figure_captions
    _suppress_inline_duplicate_table_captions
    _strip_running_header_lines_in_unstructured_table_fences

The specific hazard that motivated this scan, verified against the source on
2026-08-14: `_is_orphan_cell_paragraph` (`render.py:4499`) has **no numeric
guard**. It rejects prose by stopword density and sentence shape. A statistical
table cell has neither. So `M = 4.52`, `SD = 1.13`, `N = 245`, `t(87) = 2.01`,
`p < .001` and `95% CI [0.12, 0.44]` are all classified `orphan=True`, and
`_suppress_orphan_table_cell_text` drops a run of 2+ of them after a `Table N.`
caption — which is EXACTLY the shape a genuine unrecovered table leaves behind
when Camelot fails on it. Worse, the run does not stop at prose: an English
sentence carrying fewer than 3 of the 20 stopwords is itself `orphan=True`, so
adjacent real prose is swept out with the cells.

METHOD, and why it is shaped this way.

**The hazard above was demonstrated with a CONSTRUCTED string, which proves
what the CODE does and never that the SHAPE OCCURS.** The 2026-08-13 directive
is explicit that a rule, a guard or a case must be justified by a shape observed
in a real document, cited by DOI. So this scan harvests from REAL PAPERS: it
renders each corpus paper twice — once stopping before the post-process chain,
once through the public entry point — and diffs the two.

It does NOT re-implement the chain. Re-implementing it would create a second
definition that drifts from the first (the "one concept, one table" rule), and
a drifted copy would measure itself rather than production. Instead the scan
calls `_render_sections_to_markdown` for the BEFORE and the real public
`render_pdf_to_markdown` for the AFTER, sharing the extraction work between
them so the only difference is the chain.

FOLDING OUT WHAT DOCPLUCK IS ENTITLED TO DO. A gate that cries wolf gets
ignored — the identifier scan went from 127 false defects to 1 real one once it
stopped flagging legitimate changes. Many of the 54 steps legitimately REWRITE a
line containing digits (`recover_corrupted_minus_signs` turns `20.5` into
`-0.5`; the heading promoters prepend `## `). Those are transformations, not
deletions. So a deleted line is only reported when difflib finds no replacement
line for it, and its digits do not survive anywhere in the after-text near the
same position.

ENGLISH ONLY, exclusions printed. See `docs/SCOPE.md`.

Run:  python tools/diag/render_deletion_scan.py [--sample N] [--seed S] [--limit N]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _corpus  # noqa: E402
from _language import detect_language  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from docpluck.extract_layout import extract_pdf_layout  # noqa: E402
from docpluck.extract_structured import extract_pdf_structured  # noqa: E402
from docpluck.normalize import NormalizationLevel  # noqa: E402
from docpluck.render import (  # noqa: E402
    _render_sections_to_markdown,
    removed_lines,
    render_pdf_to_markdown,
)
from docpluck.sections import extract_sections  # noqa: E402

# A token that carries a measurement. Deliberately narrow: a bare integer is
# often furniture (a page number, a year, a heading index), while a decimal, a
# signed value, a percentage or a bracketed interval is almost always a
# reported quantity.
_NUMERIC_TOKEN_RE = re.compile(r"[-+−]?\d+(?:[.,]\d+)+|[-+−]?\.\d+")

# A line worth reporting when it disappears: it carries at least one numeric
# token AND is not obvious page furniture.
#
# A BARE DOI LINE is masthead furniture, not a measurement. It is an identifier,
# and an identifier is not a published quantity — the `10.1177/…` digits are not
# a number anyone reports. Added 2026-08-15 after `_strip_frontmatter_masthead_
# block` correctly removing `10.1177/01461672251327169` was the last remaining
# "deletion" on the corpus. Deliberately anchored to a line that is NOTHING BUT a
# DOI (optionally with a `doi:`/`https://doi.org/` prefix): a DOI inside a
# sentence, or on a line with anything else, still counts — a reference entry
# must never be dismissed as furniture.
_FURNITURE_RE = re.compile(
    r"^(?:page\s+\d+|\d+\s*$|figure\s+\d+\s*$|table\s+\d+\s*$"
    r"|(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?10\.\d{4,9}/\S+\s*$)",
    re.IGNORECASE,
)


def _digits(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


def _numeric_tokens(s: str) -> list[str]:
    return _NUMERIC_TOKEN_RE.findall(s)


def _is_reportable(line: str) -> bool:
    stripped = line.strip()
    if not stripped or _FURNITURE_RE.match(stripped):
        return False
    return bool(_numeric_tokens(stripped))


def _render_both(pdf_bytes: bytes) -> tuple[str, str]:
    """Return (before_chain, after_chain) markdown for one PDF.

    The extraction work is done ONCE and handed to `render_pdf_to_markdown`
    through its `_structured` / `_sectioned` / `_layout_doc` parameters, so the
    two strings differ ONLY by the 54-step post-process chain. Reproducing the
    chain here would be a second implementation of it; calling the real entry
    point is the only way the measurement describes production.
    """
    try:
        layout_doc = extract_pdf_layout(pdf_bytes)
    except Exception:
        layout_doc = None

    structured = extract_pdf_structured(pdf_bytes, _layout_doc=layout_doc)
    if structured["text"].startswith("ERROR:"):
        raise RuntimeError(structured["text"][:200])

    sectioned = extract_sections(
        pdf_bytes,
        source_format="pdf",
        preserve_math_glyphs=True,
        normalization_level=NormalizationLevel.academic,
        _dropped_minus_layout=layout_doc,
    )

    from docpluck import __version__ as _dp_ver

    before = _render_sections_to_markdown(
        sectioned,
        structured["tables"],
        structured["figures"],
        flatten_tables_inline=False,
        docpluck_version=_dp_ver,
    )
    after = render_pdf_to_markdown(
        pdf_bytes,
        normalization_level=NormalizationLevel.academic,
        flatten_tables_inline=False,
        _structured=structured,
        _sectioned=sectioned,
        _layout_doc=layout_doc,
    )
    return before, after


def _deleted_lines(before: str, after: str) -> list[str]:
    """Reportable lines a SINGLE chain step removed.

    **The removal decision itself lives in `docpluck.render.removed_lines`**, so
    production telemetry (`RenderReport._track`) and this gate cannot disagree
    about what "removed" means. They DID disagree once: an early `_track` asked
    only whether the old line was a substring of some output line, and reported
    55 deleted statistics on `efendic_2022` where this scan correctly reported
    none — every one of them `recover_corrupted_minus_signs` rewriting
    `[20.21, 0.04]` to `[-0.21, 0.04]`. One concept, one table (L-024).

    This wrapper adds only the scan's own reporting filter: a line is worth
    printing when it carries a numeric token and is not page furniture.

    **This must be applied per step, never across the whole 54-step chain.**
    A first version of this scan diffed the pre-chain markdown against the
    final output and reported a deleted sentence in
    `10.1017/s0007123424000024` ("For example, Guiso et al. (2019) find that
    import exposure boosts populism..."). Checked against the code, no step had
    removed it: later steps had REFLOWED the line, so difflib saw a `delete`
    plus an unrelated `insert`, and the digit-survival guard failed because the
    line's concatenated digit signature no longer appeared contiguously. The
    finding was an artefact of the instrument. Kept in this docstring because a
    scan that cries wolf gets ignored, and because it is the reason the
    measurement is per-step.

    Within one step, difflib's `replace` opcode marks a line the step rewrote —
    a transformation docpluck is entitled to make. Only `delete` opcodes, where
    the step put nothing in the line's place, are counted.
    """
    return [
        ln for ln in removed_lines(before, after) if _is_reportable(ln)
    ]


def _chain_step_names() -> list[str]:
    """The post-process step names, READ FROM `render_pdf_to_markdown`'s source.

    Deriving the list from the source keeps ONE definition of the chain. A
    hand-maintained copy here would be a second definition that drifts from
    production, and a drifted copy measures itself rather than the shipped
    pipeline ("one concept, one table").

    ⚠ **THIS FUNCTION ONCE MEASURED NOTHING, AND SAID SO IN THE VOICE OF A PASS.**
    It used to match `^\\s*md = (\\w+)\\(`, which was correct while the chain was
    written `md = fn(md)`. v2.4.130 rewrote every call as
    `md = _step(_report, "name", fn, md)` — so the pattern returned exactly
    `['_render_sections_to_markdown', '_step', '_rescue_title_from_layout']`,
    and the instrumenting wrapper then bailed on `_step` because its first
    positional argument is the REPORT, never a `str`. Zero of the 53 deleting
    steps were wrapped, and the gate reported "26/26 papers, 0 deletions".

    That is this project's own 2026-08-15 rule — *a zero is a claim about the
    INSTRUMENT until you prove otherwise* — broken by the gate written to
    enforce it, in the same release. The docstring above boasted that deriving
    from source prevents a drifted copy; the drift happened in the deriving.
    Found 2026-08-15 by an independent review (Fable 5) and reproduced.

    The names now come from the `_step` call's own string literal, which is the
    single place the chain names itself.
    """
    import inspect

    import docpluck.render as R

    # Read the IMPLEMENTATION, not the public name. v2.4.134 made
    # `render_pdf_to_markdown` a thin wrapper (it holds the telemetry scope) and
    # moved the chain into `_render_pdf_to_markdown`; scraping the wrapper found
    # zero `_step` calls and this guard correctly refused to run — which is the
    # guard working, and is exactly the defect it was written for one release
    # earlier. Falling back to the public name keeps it working if the two are
    # ever merged again.
    impl = getattr(R, "_render_pdf_to_markdown", None) or R.render_pdf_to_markdown
    src = inspect.getsource(impl)
    names = re.findall(r"""_step\(\s*_report\s*,\s*["']([^"']+)["']""", src)
    seen: list[str] = []
    for n in names:
        if n not in seen:
            seen.append(n)
    if not seen:
        raise SystemExit(
            "FATAL: no `_step(_report, \"name\", …)` calls found in "
            "render_pdf_to_markdown. The chain's call shape changed and this "
            "scan can no longer see it. A scan that instruments nothing reports "
            "a clean corpus — fix the pattern, do not ship the zero."
        )
    return seen


def _instrument(record: dict[str, list[str]]):
    """Intercept `_step` so every chain step reports the lines IT removed.

    Wrapping `_step` — rather than 53 module attributes — means the measurement
    sees exactly what production runs, gets the step's name from the same
    literal the report uses, and cannot go stale when a step is added or
    renamed. It also picks up steps that are not module-level attributes.
    """
    import docpluck.render as R

    original = R._step

    def wrapped(report, name: str, fn, md: str, *a, **k):
        out = original(report, name, fn, md, *a, **k)
        if isinstance(md, str) and isinstance(out, str) and out != md:
            lost = _deleted_lines(md, out)
            if lost:
                record.setdefault(name, []).extend(lost)
        return out

    R._step = wrapped
    return {"_step": original}


def _uninstrument(originals: dict[str, object]) -> None:
    import docpluck.render as R

    for name, fn in originals.items():
        setattr(R, name, fn)


def main() -> int:
    # The corpus is full of glyphs a Windows cp1252 console cannot encode, and
    # a scan that dies mid-report on an encoding error looks exactly like a
    # scan that found nothing.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - older/redirected streams
        pass

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=0, help="random N papers")
    ap.add_argument("--seed", type=int, default=20260814)
    ap.add_argument("--limit", type=int, default=0, help="first N of the baseline corpus")
    ap.add_argument("--show", type=int, default=8, help="max deleted lines shown per paper")
    args = ap.parse_args()

    if args.sample:
        corpus = _corpus.sampled_corpus(args.sample, seed=args.seed)
    else:
        corpus = _corpus.baseline_corpus(limit=args.limit or None)

    print(_corpus.coverage_line())
    print(f"SCANNING {len(corpus)} papers for render-chain content deletion\n")

    total_deleted = 0
    papers_hit = 0
    skipped_non_english: list[str] = []
    errors: list[tuple[str, str]] = []
    token_counter: Counter[str] = Counter()
    step_counter: Counter[str] = Counter()

    for key, pdf_path in corpus:
        if pdf_path is None or not pdf_path.exists():
            errors.append((key, "pdf not resolved"))
            continue
        per_step: dict[str, list[str]] = {}
        originals = _instrument(per_step)
        try:
            pdf_bytes = pdf_path.read_bytes()
            before, _after = _render_both(pdf_bytes)
        except Exception as exc:  # noqa: BLE001 - a scan must not stop on one paper
            errors.append((key, f"{type(exc).__name__}: {exc}"[:160]))
            continue
        finally:
            _uninstrument(originals)

        lang, _counts = detect_language(before)
        if lang != "english":
            skipped_non_english.append(f"{key} [{lang}]")
            continue

        deleted = [(step, line) for step, lines in per_step.items() for line in lines]
        if not deleted:
            continue

        papers_hit += 1
        total_deleted += len(deleted)
        for step, line in deleted:
            token_counter.update(_numeric_tokens(line))
            step_counter[step] += 1

        print(f"-- {key}  ({len(deleted)} numeric line(s) deleted)")
        for step, line in deleted[: args.show]:
            print(f"     [{step}] {line[:140]}")
        if len(deleted) > args.show:
            print(f"     ... {len(deleted) - args.show} more")
        print()

    print("=" * 72)
    print(f"PAPERS SCANNED          {len(corpus) - len(skipped_non_english) - len(errors)}")
    print(f"PAPERS LOSING CONTENT   {papers_hit}")
    print(f"NUMERIC LINES DELETED   {total_deleted}")
    print(f"DISTINCT TOKENS LOST    {len(token_counter)}")
    if step_counter:
        print("\nBY STEP (which post-processor removed the line):")
        for step, n in step_counter.most_common():
            print(f"    {n:5d}  {step}")
    if skipped_non_english:
        print(f"SKIPPED (non-English)   {len(skipped_non_english)}: {', '.join(skipped_non_english[:6])}")
    if errors:
        print(f"ERRORS                  {len(errors)}")
        for key, msg in errors[:8]:
            print(f"     {key}: {msg}")

    # Exit non-zero when the chain deleted published numbers, so this can gate.
    return 1 if total_deleted else 0


if __name__ == "__main__":
    raise SystemExit(main())
