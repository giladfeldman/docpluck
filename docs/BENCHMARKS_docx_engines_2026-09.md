# DOCX table engines, measured — 2026-09-04

A dated **record of one measurement**, not a live claim. Regenerate with the command in
§7 before quoting any number here.

docpluck extracts DOCX as text + sections only. `extract_pdf_structured` is PDF-only, so
`tables[]` and `flattened_rows[]` are empty for every DOCX, and any consumer that
verifies statistics from table rows receives nothing for that entire input format. This
page answers the question that has to be settled before that gap is closed: **which
engine should read DOCX tables?**

`docs/DESIGN.md` §11 already answers a *different* question. It chose mammoth in 2026-05
for **body text**, on soft-break fidelity, and it has never been re-asked about
**tables**. The two are not the same question and the prose was not evidence either way.

## 1. Candidates

| candidate | what it is | licence |
|---|---|---|
| **mammoth** 1.12.0 | DOCX → HTML; the engine docpluck already ships | BSD-2 |
| **python-docx** 1.2.0 | OOXML object model; already a dev dependency | MIT |
| **docx2python** 3.7.1 | DOCX → nested lists of runs | MIT |
| **pandoc** 3.10 | universal document converter, native `Table` AST | GPL-2.0-or-later (external binary) |
| **Word/LibreOffice → PDF → the existing PDF path** | reuse the shipped Camelot pipeline | n/a |
| docling | ML document converter | MIT — **not benchmarked**, see §6 |

## 2. What was measured, and against what

**Ground truth is the OOXML itself.** A PDF must be rasterized and read because its
table structure is *inferred*; a DOCX **states** its grid (`w:tbl` / `w:tr` / `w:tc`,
with `w:gridSpan`). The truth grid is therefore parsed straight from
`word/document.xml` by an independent reader in the harness that shares no code with any
candidate. No candidate adjudicates its own defect.

**The measurement is two-sided.** A one-sided one cannot fail:

- **positive** — `cell_recall` / `stat_recall`: the truth cells, and the
  statistic-bearing truth cells, a candidate reproduces at the right `(row, column)`.
- **negative** — `fabricated`: numeric tokens a candidate places in a table cell that
  occur in **no** truth cell of that document. An engine that emitted the document twice
  would score 1.0 on the positive side; this is the side that catches invention.
- **control** — the harness checks its own instrument first, both ways, before scoring
  any engine: a flat `w:tbl` scan must not see more multi-row tables than the structured
  reader, and a value absent by construction must not appear. A document whose control
  fails is **excluded from the totals**, not averaged in.

**Corpus**: 16 English DOCX resolved through the article repository by canonical key —
**5,091 truth cells, 3,908 of them statistic-bearing**, across journal manuscripts
(Taylor & Francis, PeerJ, BMC, Hogrefe templates) and open deposits. Three non-English
DOCX in the repository are **excluded and named** by the harness: docpluck's scope is
English-language articles, and evidence from a bilingual or German document does not
transfer.

## 3. Results

Pooled over cells, not averaged over documents — a mean of per-document ratios lets a
4-cell table outvote an 868-cell one.

| engine | cell recall | **stat recall** | fabricated | errors | corpus wall-clock |
|---|---|---|---|---|---|
| **pandoc** | 1.0000 | **1.0000** | 0 | 0 | ~7.9 s |
| **mammoth** | 0.9998 | **1.0000** | 0 | 0 | ~7.2 s |
| docx2python | 0.9966 | 0.9942 | 1 | 0 | ~10.2 s |
| python-docx | 0.9917 | 0.9893 | 0 | 0 | **~0.9 s** |
| Word → PDF → PDF path | 0.0077 | 0.0072 | 1 | 11 | ~126 s (5 docs) |

The pooled column hides the finding that decides the ranking. **Read the per-document
minimum, not the average.**

### python-docx loses whole tables, silently

`Document.tables` returns only `w:tbl` elements that are **direct children of
`w:body`**. On `10.1080/00221309.2023.2275304` — a Taylor & Francis manuscript template
— both tables sit inside `w:sdt` content controls, and python-docx reports **0 tables**
on a document that has 2, with no error and no warning. Its cell recall on that document
is **0.0** while every other engine scores 1.0.

**Prevalence, measured rather than assumed** (the harness's own census over every real
DOCX available, including two manuscript corpora): **2 of 55 documents (3.6%)** place at
least one table inside a content control. Small, and it is not a tail case — content
controls are what journal *manuscript templates* use, which is precisely the DOCX shape
this work exists to serve. A 3.6% silent total loss of a paper's tables is the deletion
class this project ranks worst: it does not announce itself.

That is disqualifying on its own. python-docx is also 8× faster than anything else here,
which is worth nothing when the output is silently empty.

### docx2python cannot tell a table from a paragraph

`DocxContent` exposes `body` / `body_pars` / `body_runs` and **no table accessor**
(checked against the installed 3.7.1). In `body`, a real table and a run of ordinary
paragraphs have the *same shape*, so the caller must guess. Any guess loses something:
the harness's minimum honest filter ("some row has ≥2 cells") drops a legitimate 19×1
single-column table on `10.5281/zenodo.15196164`, and without it the title block and a
trailing note of another paper are scored as tables. It also leaks raw markup into cell
text with `html=False` — `<span style=font-family:Symbol>&#x00B4;</span>` where the cell
holds a `×`.

### The PDF conversion route fails on two independent counts

1. **It cannot run where it would have to.** The service image is `python:3.12-slim` with
   poppler, Ghostscript and OpenCV. Neither Word nor LibreOffice is installed, and
   LibreOffice is a ~400 MB addition to a build that has **already disk-exhausted once**
   on its apt archives. Word COM is Windows-only and cannot be deployed at all.
2. **Even given the conversion, it does not work.** Five documents were converted with
   real Microsoft Word 16.0 and fed to the shipped PDF pipeline: **cell recall 0.0077**.
   Two lost every table; the 26-table paper yielded 7 tables and 2.7% of cells. Camelot
   re-infers from pixels a grid the DOCX had stated exactly — throwing away the
   information and then guessing at it. It is also ~500× slower (61 s for a 2-table
   paper).

### What mammoth actually loses

One cell in 5,091, and it is not a statistic: a row **label** rendered
`Computerized tests[CANTAB]` instead of `Computerized tests [CANTAB]` — a space dropped
at a run boundary. **Statistic-cell recall is 1.0000 with zero fabrications.**

## 4. Decision — mammoth

| | why |
|---|---|
| **correctness where it counts** | statistic-cell recall **1.0000**, fabrications **0** |
| **cost** | already a declared dependency of `docpluck[docx]` **and** already installed in the service image — the DOCX table path adds **no new dependency and no deploy risk** |
| **vs. pandoc** | pandoc's advantage is **one non-statistical cell in 5,091**. It costs a ~100 MB external binary in an image that has already failed a build on disk, plus a GPL binary in the dependency story of an MIT library. A rewrite must earn its cost; a 0.0002 cell-recall gain does not. |
| **vs. python-docx** | disqualified: silent total table loss on 3.6% of real documents |
| **vs. docx2python** | must guess what is a table; leaks markup into cells |
| **vs. PDF conversion** | not installable on the service, and 0.0077 recall when it does run |

**Verified equal-best, not merely adequate.** If pandoc had won on statistic recall the
answer would be different; it did not, so the incumbent wins on cost with no correctness
concession.

## 5. What this measurement does NOT establish

- **Cell text fidelity beyond exact match.** Recall is scored on exact `(row, column,
  text)` agreement, so an engine and the truth reader could share a wrong convention. The
  Greek/superscript conventions of `docs/SYMBOL_CONTRACT.md` are checked by the symbol
  contract tests, not here.
- **Tracked changes.** The truth reader excludes `w:delText`, so an engine emitting
  deleted text would be caught as fabrication. No engine did on this corpus — but only 5
  of the 55 censused documents carry `w:del` at all, and none of those 5 are in the
  scored 16. **Unmeasured for the engines**; the DOCX path passes `--track-changes` /
  equivalent explicitly rather than relying on a default.
- **Multi-column body text.** Out of scope for this run, which measures tables.
- **Rotated, nested, and split-across-page tables.** OOXML has no page model, so the
  page-boundary failures of the PDF path cannot occur; nested tables were normalised away
  by both the reader and the adapters rather than scored.

## 6. Why docling was not benchmarked

`docling-slim[standard]` is MIT with 8 direct runtime dependencies, so licence and
footprint do not rule it out. It was excluded because the winner already scores 1.0000 on
statistic recall with zero new dependencies: there is no headroom for an ML converter to
recover, and adding a model-bearing dependency to buy nothing fails the same cost test
pandoc fails. **Not a claim that docling would score badly — it is untested here.**

## 7. Regenerating this

```bash
python tools/diag/docx_tool_benchmark.py --json bench.json --pdf-dir <dir of *.word.pdf>
```

Exits non-zero if any document's control fails. `--pdf-dir` is optional; without it the
conversion route reports "no converted pdf available" rather than a score, which is the
honest answer on a machine that cannot convert.

### Three instrument defects this design caught, in its own reader

Recorded because each one would have produced a **confident wrong ranking**, and all
three were found by the negative side rather than by inspection:

1. **The truth reader missed `w:sdt`**, reported 0 tables where the document has 2, and
   scored three correct engines as fabricating 37 numbers that were the paper's real
   descriptives. The control passed *vacuously* because an empty truth grid was treated
   as fine. Fixed both: the reader descends content controls, and the control now
   compares against an independent flat `w:tbl` scan.
2. **The truth reader fused multi-paragraph cells** — a cell stacking `.556` and `.390`
   became `.556.390`, a number nobody printed, **in the ground truth**. The same defect
   class `_linearize_omml` exists to prevent, committed by the instrument built to detect
   it.
3. **The mammoth and pandoc adapters ignored `rowspan`**, sliding a two-row header two
   columns left so `Males` / `Females` / `Range` landed under the wrong statistics. This
   read as an engine defect and was an adapter defect — mammoth emits both `colspan` and
   `rowspan` correctly. Uncorrected, it would have cost mammoth the comparison.
