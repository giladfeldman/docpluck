"""Does repairing a cell at CONSTRUCTION change which rows and tables survive?

v2.4.133 moved the glyph repairs (`cell_cleaning.clean_cell_text`) from the HTML
escaper to cell CONSTRUCTION, so `cells[].text`, `flatten` and `raw_text` finally
agree with the rendered `<table>`. That was a data-integrity fix and it is right.

**It also silently changed what the STRUCTURAL GATES see.** On the region path,
`camelot_extract._camelot_table_to_dict` hands its freshly-built `cells` to
`whitespace._trim_trailing_prose_rows` and `whitespace._whitespace_grid_is_clean`
— and those cells are now repaired. `whitespace_cells` / `char_whitespace_cells`
do the same through `whitespace._cell_text`. Three predicates change direction:

    _row_is_prose        the W0i class prints `×` as `3`. Raw `Direction 3 attr`
                         carries a digit -> `_STAT_TOKEN_RE` matches -> NOT prose.
                         Repaired `Direction × attr` has no digit and 3 word
                         tokens -> IS prose. Three such rows in a row form a
                         `_PROSE_RUN_MIN` run and `_trim_trailing_prose_rows`
                         cuts from the first one to the END of the grid.
                         DIRECTION: DELETION.
    _cell_is_garbled     `(cid:0)`-before-digit is recovered as a minus, so the
                         `_UNMAPPED_GLYPH_RE` condemnation no longer fires.
                         DIRECTION: ACCEPTANCE.
    _cell_is_clean_data  repaired `<.001` matches `_CLEAN_DATA_ALLOWED_RE`;
                         raw `\\.001` (the `<`-as-backslash class) does not.
                         DIRECTION: ACCEPTANCE.

Two independent reviewers split on this on 2026-08-15 — one "unmeasured but
plausibly desirable, ship", the other "real published table content vanishes
with zero trace, do not ship". Per the project rule, a reproduction decides. The
deletion mechanism reproduces on a constructed grid (4 rows -> 0), which proves
what the CODE does and never that the SHAPE OCCURS. This scan supplies the
missing half: the real denominator, from real papers.

METHOD. Each paper is extracted TWICE in one process:

    arm A   the shipped code (cells repaired at construction)
    arm B   `clean_cell_text` monkeypatched to the identity function at BOTH
            construction sites (`camelot_extract`, `whitespace`), which restores
            the exact pre-v2.4.133 gate INPUT

and the two are compared on the only thing the gates control — how many tables
survived and how many rows each kept. Cell TEXT necessarily differs between the
arms (that is the fix, not the finding), so text is not compared.

    rows_lost       a table present in both arms that keeps FEWER rows under
                    repair. This is the deletion direction. Any non-zero count
                    here is a release-stopper.
    tables_lost     a table present in arm B and absent in arm A.
    tables_gained   a table present in arm A and absent in arm B — the
                    acceptance direction, i.e. grids the repair rescued.
    rows_gained     a shared table that keeps MORE rows under repair.

Exits non-zero when anything was LOST, so it can gate a release. Gains are
reported but never fail the run: this project's rule is DELETE FURNITURE, NEVER
DATA, and a recovered table is not a defect.

Camelot is the capture engine on both arms and has a documented cumulative-load
flake, so a difference on a SINGLE paper is a hypothesis, not a finding — re-run
that paper alone (`--only <key>`) before believing it.

Usage:
    python tools/diag/repair_gate_guard_diff.py                # 26-paper baseline
    python tools/diag/repair_gate_guard_diff.py --sample 60    # wider denominator
    python tools/diag/repair_gate_guard_diff.py --only maier   # one paper
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _corpus import baseline_corpus, coverage_line, sampled_corpus  # noqa: E402
from _language import detect_language  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _table_shapes(pdf_bytes: bytes) -> tuple[dict[str, int], dict[tuple[str, int, int], str]]:
    """``({table_id: row_count}, {(table_id, r, c): cell_text})`` for one extraction.

    Shapes are keyed on the table's own id (``camelot_t3`` / ``region_t1``) so a
    table that VANISHES between the arms is distinguishable from one that merely
    shrank — a set difference on ids, not a count comparison that nets them out.

    The cell texts are returned for ONE purpose: to prove the instrument is
    looking at something. A four-way zero on the gate columns would otherwise be
    unreadable — "the repair changed no gate outcome" and "the repair never fired
    on this corpus" produce the identical output, and this project has been
    burned three times by reading the second as the first. Counting the cells
    whose TEXT differs between the arms separates them.
    """
    from docpluck.extract_structured import extract_pdf_structured

    result = extract_pdf_structured(pdf_bytes)
    _last_text[0] = result.get("text") or ""
    shapes: dict[str, int] = {}
    texts: dict[tuple[str, int, int], str] = {}
    for t in result.get("tables") or ():
        tid = str(t.get("id") or "")
        if not tid:
            continue
        cells = t.get("cells") or ()
        shapes[tid] = len({c["r"] for c in cells}) if cells else 0
        for c in cells:
            texts[(tid, c["r"], c["c"])] = c.get("text") or ""
    return shapes, texts


# The extracted text of the most recent :func:`_table_shapes` call, so the
# ENGLISH-ONLY scope filter can run on text we already paid to extract rather
# than extracting a second time.
_last_text = [""]


class _NoRepair:
    """Patch `clean_cell_text` to identity everywhere it is REACHED from.

    Two modules, deliberately. `cell_cleaning.repair_cells` (the emission step
    for both capture paths) and `cell_cleaning._html_escape` resolve the symbol
    through `cell_cleaning`'s globals; `whitespace._repaired_view` (the gates'
    validity view) resolves it through `whitespace`'s. Patching one leaves the
    other repairing, which would measure a composition that has never shipped —
    exactly the "wired in two of three channels" defect this project keeps
    hitting. Verified by `CELLS REPAIRED`: if a patch site were missed, arm B
    would still repair and that counter would read 0.
    """

    def __enter__(self):
        from docpluck.tables import cell_cleaning, whitespace

        self._mods = (cell_cleaning, whitespace)
        self._saved = [m.clean_cell_text for m in self._mods]
        for m in self._mods:
            m.clean_cell_text = lambda s: (s or "")
        return self

    def __exit__(self, *_exc):
        for m, fn in zip(self._mods, self._saved):
            m.clean_cell_text = fn
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=0,
                    help="sample N papers from the shared repository instead of "
                         "the 26-paper render baseline")
    ap.add_argument("--only", default="", help="substring filter on the paper key")
    ap.add_argument("--limit", type=int, default=0, help="stop after N papers")
    args = ap.parse_args()

    corpus = sampled_corpus(args.sample) if args.sample else baseline_corpus()
    if args.only:
        corpus = [(k, p) for k, p in corpus if args.only.lower() in k.lower()]
    if args.limit:
        corpus = corpus[: args.limit]

    print(coverage_line())
    print(f"comparing {len(corpus)} paper(s): repaired-at-construction vs raw\n")

    scanned = 0
    skipped_non_english: list[str] = []
    errors: list[tuple[str, str]] = []
    rows_lost = tables_lost = rows_gained = tables_gained = 0
    cells_repaired = papers_with_repair = 0
    losers: list[str] = []

    for key, path in corpus:
        try:
            pdf_bytes = path.read_bytes()
        except OSError as exc:
            errors.append((key, str(exc)))
            continue
        try:
            after, after_text = _table_shapes(pdf_bytes)
            with _NoRepair():
                before, before_text = _table_shapes(pdf_bytes)
        except Exception as exc:  # noqa: BLE001 — a scan must not die on one paper
            errors.append((key, f"{type(exc).__name__}: {exc}"[:160]))
            continue
        # ENGLISH ONLY — the scope rule. A non-English paper cannot teach us
        # anything about an English-article gate, and including it would inflate
        # the denominator with documents docpluck does not serve. Reported, never
        # dropped silently.
        lang, _counts = detect_language(_last_text[0])
        if lang != "english":
            skipped_non_english.append(f"{key} [{lang}]")
            continue
        scanned += 1

        gone = sorted(set(before) - set(after))
        new = sorted(set(after) - set(before))
        shrank = sorted(t for t in set(before) & set(after) if after[t] < before[t])
        grew = sorted(t for t in set(before) & set(after) if after[t] > before[t])

        tables_lost += len(gone)
        tables_gained += len(new)
        rows_lost += sum(before[t] - after[t] for t in shrank)
        rows_gained += sum(after[t] - before[t] for t in grew)

        # THE INSTRUMENT'S OWN KNOWN POSITIVE. Cells present in both arms whose
        # text differs are cells the repair actually rewrote on THIS paper. If
        # this is 0 corpus-wide, every zero above is a statement about the scan,
        # not about the library, and must be reported as unbounded.
        repaired_cells = sum(
            1 for k in set(before_text) & set(after_text)
            if before_text[k] != after_text[k]
        )
        cells_repaired += repaired_cells
        if repaired_cells:
            papers_with_repair += 1

        if gone or shrank:
            losers.append(key)
            print(f"-- {key}  LOST")
            for t in gone:
                print(f"     table {t} vanished ({before[t]} rows -> absent)")
            for t in shrank:
                print(f"     table {t} {before[t]} -> {after[t]} rows")
        if new or grew:
            print(f"++ {key}  gained")
            for t in new:
                print(f"     table {t} recovered ({after[t]} rows)")
            for t in grew:
                print(f"     table {t} {before[t]} -> {after[t]} rows")

    print("\n" + "=" * 72)
    print(f"PAPERS SCANNED       {scanned}")
    print(f"TABLES LOST          {tables_lost}")
    print(f"ROWS LOST            {rows_lost}")
    print(f"TABLES GAINED        {tables_gained}")
    print(f"ROWS GAINED          {rows_gained}")
    print(f"CELLS REPAIRED       {cells_repaired} in {papers_with_repair} paper(s)"
          "   <- the instrument's known positive")
    if losers:
        print(f"PAPERS LOSING        {len(losers)}: {', '.join(losers)}")
    if skipped_non_english:
        print(f"SKIPPED non-English  {len(skipped_non_english)}: "
              f"{', '.join(skipped_non_english[:6])}")
    if errors:
        print(f"ERRORS               {len(errors)}")
        for key, msg in errors[:8]:
            print(f"     {key}: {msg}")
    if scanned == 0:
        print("\nNO PAPER WAS SCANNED — this is an INSTRUMENT result, not a clean "
              "one. Do not read the zeros above as evidence.")
        return 2
    if cells_repaired == 0:
        print("\nTHE REPAIR NEVER FIRED on this corpus, so the gate columns above "
              "are UNBOUNDED, not clean. Re-run against a paper known to carry a "
              "repairable class (efendic_2022_affect, ar_apa_j_jesp_2009_12_011) "
              "before reading any zero as evidence.")
        return 2
    return 1 if (rows_lost or tables_lost) else 0


if __name__ == "__main__":
    raise SystemExit(main())
