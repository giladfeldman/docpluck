"""DOCX table extraction: `extract_docx_structured` (v2.4.139).

WHAT THIS CLOSES. `extract_pdf_structured` is PDF-only, so `tables[]` and
`flattened_rows[]` were empty for every DOCX and a consumer that verifies
statistics from table rows received nothing for that whole input format --
while a DOCX *states* its table grid exactly, in `w:tbl`. The paper's numbers
were sitting in the file, fully structured, and docpluck was throwing them away.

ENGINE CHOICE IS MEASURED, NOT ASSUMED: `docs/BENCHMARKS_docx_engines_2026-09.md`
scores five candidates over 16 English DOCX (5,091 truth cells, 3,908 of them
statistic-bearing) with a two-sided metric. mammoth wins at statistic-cell recall
1.0000 / 0 fabrications, and is the only candidate that adds no dependency.

These tests were written against a tree with no `extract_docx_structured` at all
and watched RED first (they failed at import). A test authored after the fix that
merely re-asserts current behaviour proves nothing.
"""

from __future__ import annotations

import io
import json
import os
import re
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("mammoth", reason="mammoth not installed (pip install docpluck[docx])")
pytest.importorskip("bs4", reason="beautifulsoup4 not installed (pip install docpluck[html])")
pytest.importorskip("docx", reason="python-docx not installed (dev dependency)")

from docx import Document  # noqa: E402
from docx.shared import Pt  # noqa: E402

from docpluck import (  # noqa: E402
    extract_docx_structured,
    extract_pdf_structured,
    flatten_tables_for_paper,
)


# ── Fixture builders ────────────────────────────────────────────────────────
#
# Synthetic DOCX here, real DOCX in the custody-corpus tests at the bottom.
# A synthetic fixture can only confirm the model it was built from, so it pins
# BEHAVIOUR (does the value reach the consumer?) while the real corpus pins
# PREVALENCE (does this shape occur, and how often?).


def _docx_with_stats_table() -> bytes:
    """A statistics table using the header vocabulary real DOCX actually use.

    THE HEADERS HERE ARE NOT INVENTED. An earlier draft of this fixture headed
    the test-statistic column `t(48)`, which fails to classify -- and the
    tempting fix was to add a `t_with_df` role to `tables/flatten.py` beside the
    existing `F_with_df`. Measured first, over every real DOCX available (55
    documents with table cells): **`t(df)` occurs 0 times, `chi2(df)` 0 times,
    `F(a,b)` once.** The real vocabulary is bare and already classified -- `p`
    (118 cells), `df` (38), `F` (35), `N` (30), `SD` (24), `SE` (23), `t` (17),
    `M` (13), `d` (13), `95% CI` (16).

    So the defect was the FIXTURE, not the library, and adding the rule would
    have been pure false-positive surface justified by a string this file made
    up -- the exact shape of the retired A3d rule (CLAUDE.md: case studies come
    from real papers; measure the denominator separately from the shape).

    Regenerate the counts with `tools/diag/docx_tool_benchmark.py`'s corpus and
    a header census before touching `_ROLE_PATTERNS` on this evidence.
    """
    d = Document()
    d.add_paragraph("Results")
    d.add_paragraph("Table 1. Descriptive statistics and test results by condition.")
    t = d.add_table(rows=3, cols=6)
    hdr = ["Condition", "M", "SD", "t", "df", "p"]
    for c, text in enumerate(hdr):
        t.cell(0, c).text = text
    for r, row in enumerate(
        [["Treatment", "4.21", "1.12", "3.45", "48", ".001"],
         ["Control", "3.42", "0.89", "1.02", "48", ".312"]],
        start=1,
    ):
        for c, text in enumerate(row):
            t.cell(r, c).text = text
    d.add_paragraph("Note. N = 50 per condition. Cohen's d = 0.79.")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _docx_with_merged_header() -> bytes:
    """A two-row header where the first column spans both rows.

    This is the shape that broke the benchmark's own adapter: ignore `rowspan`
    and the second header row slides left, so every value lands under the wrong
    statistic's name. `tables/flatten.py` binds values to headers by position,
    so a shift here is not cosmetic -- it publishes a t-statistic labelled `p`.
    """
    d = Document()
    d.add_paragraph("Table 2. Effect sizes by group.")
    t = d.add_table(rows=3, cols=3)
    t.cell(0, 0).merge(t.cell(1, 0))
    t.cell(0, 0).text = "Group"
    t.cell(0, 1).merge(t.cell(0, 2))
    t.cell(0, 1).text = "Effect"
    t.cell(1, 1).text = "d"
    t.cell(1, 2).text = "95% CI"
    t.cell(2, 0).text = "Younger"
    t.cell(2, 1).text = "0.42"
    t.cell(2, 2).text = "[0.18, 0.66]"
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _docx_with_cell(text: str) -> bytes:
    d = Document()
    d.add_paragraph("Table 1. One value.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "Estimate"
    t.cell(0, 1).text = "CI"
    t.cell(1, 0).text = "beta"
    t.cell(1, 1).text = text
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _docx_with_stacked_cell() -> bytes:
    """A cell holding two values as separate paragraphs.

    The benchmark's ground-truth reader fused exactly this shape into `.556.390`
    -- a number nobody printed. The library must not repeat it.
    """
    d = Document()
    d.add_paragraph("Table 1. Stacked.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "Variable"
    t.cell(0, 1).text = "Loadings"
    t.cell(1, 0).text = "Item 1"
    cell = t.cell(1, 1)
    cell.text = ".556"
    cell.add_paragraph(".390")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _with_tracked_deletion(docx_bytes: bytes) -> bytes:
    """Rewrite one run into a `w:del` deletion, keeping the document valid."""
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        parts = {n: z.read(n) for n in z.namelist()}
        infos = {i.filename: i for i in z.infolist()}
    xml = parts["word/document.xml"].decode("utf-8")
    xml = xml.replace(
        "<w:t>3.45</w:t>",
        "<w:t>3.45</w:t></w:r>"
        '<w:del w:id="9001" w:author="a" w:date="2026-09-04T00:00:00Z">'
        '<w:r><w:delText>9.99</w:delText></w:r></w:del><w:r>',
        1,
    )
    parts["word/document.xml"] = xml.encode("utf-8")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
        for name in parts:
            zo.writestr(infos[name], parts[name])
    return out.getvalue()


# ── The contract shape: additive, never renamed ─────────────────────────────


class TestResultShapeIsAdditive:
    """The DOCX result must be the SAME StructuredResult the PDF path returns.

    A consumer reading `result["tables"]` / `flattened_rows` must not need a
    second code path, and no existing field may be renamed. A rename that
    silently empties every downstream consumer is the most expensive defect this
    library has shipped, and it turned no test red anywhere.
    """

    def test_docx_result_has_exactly_the_pdf_result_keys(self):
        docx_keys = set(extract_docx_structured(_docx_with_stats_table()))
        pdf_keys = set(extract_pdf_structured(b"%PDF-1.4 not really a pdf"))
        assert docx_keys == pdf_keys, (
            "the DOCX StructuredResult drifted from the PDF one; a consumer "
            f"would need two code paths. only-docx={docx_keys - pdf_keys} "
            f"only-pdf={pdf_keys - docx_keys}"
        )

    def test_table_carries_every_declared_table_field(self):
        from docpluck.tables import Table

        res = extract_docx_structured(_docx_with_stats_table())
        assert res["tables"], "no table extracted from a document with one table"
        declared = set(Table.__annotations__)
        got = set(res["tables"][0])
        assert declared <= got, f"Table fields missing from the DOCX path: {declared - got}"

    def test_method_names_the_engine_that_actually_ran(self):
        res = extract_docx_structured(_docx_with_stats_table())
        assert "mammoth" in res["method"], (
            f"method={res['method']!r} does not name the engine; an unlabelled "
            "engine is the 'no pretending' violation"
        )


# ── The point of the whole exercise: statistics reach the consumer ──────────


class TestStatisticsReachTheConsumer:
    def test_cells_carry_the_published_values(self):
        res = extract_docx_structured(_docx_with_stats_table())
        texts = {c["text"] for t in res["tables"] for c in t["cells"]}
        for value in ("4.21", "1.12", "3.45", ".001", "3.42", "0.89"):
            assert value in texts, f"{value!r} was printed in the table and is not in cells"

    def test_flatten_binds_each_value_to_its_column_header(self):
        """`flatten_tables_for_paper` is the contract downstream verifiers read."""
        res = extract_docx_structured(_docx_with_stats_table())
        rows = flatten_tables_for_paper(res["tables"])
        assert rows, "a 5-column statistics table produced no FlattenedRow"
        treatment = [r for r in rows if r["row_label"] == "Treatment"]
        assert treatment, f"no row labelled 'Treatment'; got {[r['row_label'] for r in rows]}"
        fields = treatment[0]["fields"]
        assert fields.get("M") == 4.21, f"M not bound: {fields}"
        assert fields.get("SD") == 1.12, f"SD not bound: {fields}"
        assert fields.get("t") == 3.45, f"t not bound: {fields}"
        assert fields.get("df") == 48, f"df not bound: {fields}"
        assert fields.get("p") == 0.001, f"p not bound: {fields}"

    def test_caption_and_label_are_recovered_from_the_paragraph_above(self):
        res = extract_docx_structured(_docx_with_stats_table())
        t = res["tables"][0]
        assert t["label"] == "Table 1", f"label={t['label']!r}"
        assert t["caption"] and "Descriptive statistics" in t["caption"], (
            f"caption={t['caption']!r} -- flatten reads caption vocabulary to type "
            "an unlabelled effect column, so losing it loses effect-size typing"
        )

    def test_html_is_emitted_for_a_structured_table(self):
        res = extract_docx_structured(_docx_with_stats_table())
        html = res["tables"][0]["html"]
        assert html and "<table>" in html


class TestCaptionRecovery:
    """Captions are not decoration: `flatten_table` reads caption + footnote
    vocabulary to type an unlabelled estimate column. A missing caption loses
    effect-size typing; a WRONG one types a statistic the table never reported,
    so the negative controls below matter more than the recall.

    Measured over the 87 tables of 13 real DOCX: matching only the PDF path's
    `Table \\d+` shape recovered **16.1%**. Supplementary labels (`Table S1`) and
    APA 7's two-paragraph label/title form account for nearly all the rest;
    handling both, with the double-assignment fixed, gives **67.8%**.
    """

    def _docx_caption(self, before: list[str], after: list[str]) -> bytes:
        d = Document()
        for p in before:
            d.add_paragraph(p)
        t = d.add_table(rows=2, cols=2)
        t.cell(0, 0).text = "Group"
        t.cell(0, 1).text = "d"
        t.cell(1, 0).text = "A"
        t.cell(1, 1).text = "0.42"
        for p in after:
            d.add_paragraph(p)
        buf = io.BytesIO()
        d.save(buf)
        return buf.getvalue()

    def test_supplementary_label_is_recovered(self):
        """`Table S1` is not `Table \\d+`, and DOCX is the format supplementary
        material is submitted in."""
        res = extract_docx_structured(
            self._docx_caption(["Table S1. Baseline characteristics."], [])
        )
        assert res["tables"][0]["label"] == "Table S1"

    def test_apa_two_paragraph_label_and_title_are_joined(self):
        res = extract_docx_structured(
            self._docx_caption(["Table 3", "Effect sizes by condition"], [])
        )
        t = res["tables"][0]
        assert t["label"] == "Table 3"
        assert "Effect sizes by condition" in (t["caption"] or ""), f"{t['caption']!r}"

    def test_a_caption_below_the_table_is_recovered(self):
        res = extract_docx_structured(
            self._docx_caption(["Some prose about the study."],
                               ["Table 4. Results by arm."])
        )
        assert res["tables"][0]["label"] == "Table 4"

    def test_a_paragraph_that_merely_refers_to_a_table_is_not_its_caption(self):
        """NEGATIVE CONTROL. Proximity must never promote body prose."""
        res = extract_docx_structured(
            self._docx_caption(["The effect was robust, as shown in Table 2 below."], [])
        )
        t = res["tables"][0]
        assert t["label"] is None and t["caption"] is None, (
            f"a body reference became a caption: {t['caption']!r}. It would then "
            "be fed to flatten's effect-type vocabulary."
        )

    def test_one_caption_paragraph_is_not_claimed_by_two_tables(self):
        """NEGATIVE CONTROL. A caption between two tables was claimed by the
        table above it (as its 'next') AND the one below it (as its 'previous'),
        so 3 real documents emitted one label on two grids -- a consumer joining
        on `label` would merge two unrelated tables."""
        d = Document()
        for i, label in enumerate(("Table 1. First.", "Table 2. Second."), start=1):
            d.add_paragraph(label)
            t = d.add_table(rows=2, cols=2)
            t.cell(0, 0).text = "Group"
            t.cell(0, 1).text = "d"
            t.cell(1, 0).text = f"A{i}"
            t.cell(1, 1).text = f"0.4{i}"
        buf = io.BytesIO()
        d.save(buf)
        labels = [t["label"] for t in extract_docx_structured(buf.getvalue())["tables"]]
        assert len(labels) == len(set(labels)), f"a label was assigned twice: {labels}"
        assert labels == ["Table 1", "Table 2"], labels


class TestMergedHeadersDoNotShiftColumns:
    def test_two_row_header_with_a_row_span_keeps_its_columns(self):
        res = extract_docx_structured(_docx_with_merged_header())
        cells = res["tables"][0]["cells"]
        grid: dict[tuple[int, int], str] = {(c["r"], c["c"]): c["text"] for c in cells}
        assert grid.get((1, 1)) == "d", (
            f"the sub-header slid: row1 = {[grid.get((1, i)) for i in range(3)]}. "
            "flatten binds by position, so this labels an effect size with the "
            "wrong statistic's name"
        )
        assert grid.get((1, 2)) == "95% CI"

    def test_the_value_row_still_lines_up_under_its_header(self):
        res = extract_docx_structured(_docx_with_merged_header())
        rows = flatten_tables_for_paper(res["tables"])
        assert rows, "merged-header table produced no rows"
        assert rows[0]["fields"].get("d") == 0.42, (
            f"d not bound under a merged header: {rows[0]['fields']}"
        )


class TestCellTextIsNotFusedOrInvented:
    def test_two_paragraphs_in_one_cell_do_not_fuse_into_a_new_number(self):
        res = extract_docx_structured(_docx_with_stacked_cell())
        texts = {c["text"] for t in res["tables"] for c in t["cells"]}
        assert ".556.390" not in texts, (
            "two stacked values fused into a number the paper never printed -- "
            "the same class `_linearize_omml` exists to prevent"
        )
        joined = " ".join(texts)
        assert ".556" in joined and ".390" in joined

    def test_unicode_minus_is_folded_to_ascii(self):
        """CLAUDE.md hard rule 4 / LESSONS L-004. Measured: 78 occurrences of
        U+2212 in the table cells of 2 of 13 real DOCX in the corpus."""
        res = extract_docx_structured(_docx_with_cell("−0.42"))
        texts = {c["text"] for t in res["tables"] for c in t["cells"]}
        assert "-0.42" in texts, f"U+2212 not folded: {texts}"

    def test_a_pdf_glyph_repair_never_fires_on_a_docx(self):
        """docpluck EXTRACTS, it does not FIX THE PAPER.

        `[20.45, 20.06]` in a PDF is a corrupted `[-0.45, -0.06]`, because a
        broken font mapped U+2212 to `2`. A DOCX carries real Unicode: there is
        no such font layer, so the same string is a value the authors actually
        typed and it must pass through verbatim. Measured over the corpus:
        **0 occurrences of `(cid:N)` or NUL in any DOCX table cell**, so the PDF
        recovery chain could only ever misfire here.
        """
        res = extract_docx_structured(_docx_with_cell("[20.45, 20.06]"))
        texts = {c["text"] for t in res["tables"] for c in t["cells"]}
        assert "[20.45, 20.06]" in texts, (
            f"a PDF glyph repair rewrote a DOCX cell: {texts}. That fabricates a "
            "minus sign the document does not contain."
        )
        assert "[-0.45, -0.06]" not in texts

    def test_deleted_tracked_change_text_is_not_resurrected(self):
        """Emitting `w:delText` is not recovery, it is resurrecting a retraction."""
        res = extract_docx_structured(_with_tracked_deletion(_docx_with_stats_table()))
        texts = {c["text"] for t in res["tables"] for c in t["cells"]}
        assert not any("9.99" in t for t in texts), (
            f"author-deleted text reached the consumer as live data: {texts}"
        )
        assert any("3.45" in t for t in texts), (
            "the surviving value was dropped along with the deletion"
        )


class TestFieldsWithNoDocxMeaningAreHonest:
    """A DOCX has no page model and no page geometry. Say so; never invent one."""

    def test_geometry_absence_is_named_not_silent(self):
        t = extract_docx_structured(_docx_with_stats_table())["tables"][0]
        assert t["cell_geometry"] and "docx" in t["cell_geometry"], (
            f"cell_geometry={t['cell_geometry']!r} -- a zero bbox with no stated "
            "reason is indistinguishable from real geometry that happens to be zero"
        )
        assert all(c["bbox"] == (0.0, 0.0, 0.0, 0.0) for c in t["cells"])

    def test_capture_quality_is_none_because_nothing_was_captured(self):
        t = extract_docx_structured(_docx_with_stats_table())["tables"][0]
        for field in ("confidence", "accuracy", "whitespace", "camelot_flavor"):
            assert t[field] is None, (
                f"{field}={t[field]!r}: a DOCX table is STATED, not inferred, so "
                "there is no capture-quality signal to report. Emitting a number "
                "here would invent a confidence."
            )

    def test_page_is_zero_because_docx_has_no_pages(self):
        t = extract_docx_structured(_docx_with_stats_table())["tables"][0]
        assert t["page"] == 0, (
            f"page={t['page']!r}: OOXML has no page model -- pagination is decided "
            "by the renderer -- so any positive page number is fabricated."
        )

    def test_rendering_names_markup_rather_than_a_capture_heuristic(self):
        t = extract_docx_structured(_docx_with_stats_table())["tables"][0]
        assert t["rendering"] == "markup", (
            f"rendering={t['rendering']!r} claims a PDF capture path ran. "
            "Reusing 'lattice' here would be an unlabelled engine substitution."
        )


class TestDegradesWithoutLying:
    def test_a_document_with_no_tables_returns_an_empty_list_not_an_error(self):
        d = Document()
        d.add_paragraph("No tables here, just prose with t(10) = 2.1, p = .04.")
        buf = io.BytesIO()
        d.save(buf)
        res = extract_docx_structured(buf.getvalue())
        assert res["tables"] == []
        assert "t(10) = 2.1" in res["text"]

    def test_a_malformed_docx_reports_the_failure_rather_than_an_empty_success(self):
        with pytest.raises(Exception):
            extract_docx_structured(b"not a zip at all")


# ── Real documents: the synthetic fixtures cannot establish prevalence ──────


def _custody_docx() -> list[tuple[str, Path]]:
    repo = Path(
        os.environ.get("ARTICLE_REPOSITORY")
        or (Path(os.environ.get("VIBE_ROOT") or (Path.home() / "Vibe")) / "ArticleRepository")
    )
    index = repo / "index.json"
    if not index.exists():
        return []
    try:
        data = json.loads(index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for key, entry in data.items():
        if not isinstance(entry, dict):
            continue
        fn = str(entry.get("filename") or "")
        if not fn.lower().endswith(".docx"):
            continue
        p = repo / "fulltext" / fn
        if p.exists():
            out.append((key, p))
    return sorted(out)


@pytest.mark.skipif(not _custody_docx(), reason="no DOCX resolvable through article-finder")
def test_real_docx_statistic_cells_survive_to_the_flattened_rows():
    """Every statistic-bearing cell of a real paper must reach a consumer.

    Scored against the OOXML itself -- the DOCX states its own grid, so this is
    the primary source and not a second run of the extractor under test.
    """
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    import xml.etree.ElementTree as ET

    checked = 0
    for key, path in _custody_docx():
        b = path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            if "word/document.xml" not in z.namelist():
                continue
            root = ET.fromstring(z.read("word/document.xml"))
        # Values the document states inside a table, read independently.
        stated: set[str] = set()
        for tbl in root.iter(f"{W}tbl"):
            if len(tbl.findall(f"{W}tr")) < 2:
                continue
            for tc in tbl.iter(f"{W}tc"):
                for p in tc.iter(f"{W}p"):
                    txt = "".join(
                        n.text or "" for n in p.iter(f"{W}t")
                    ).strip()
                    if re.fullmatch(r"[-−]?\d+\.\d+", txt):
                        stated.add(txt.replace("−", "-"))
        if len(stated) < 20:
            continue
        res = extract_docx_structured(b)
        got = {
            c["text"].replace("−", "-")
            for t in res["tables"]
            for c in t["cells"]
        }
        missing = stated - got
        assert len(missing) / len(stated) < 0.02, (
            f"{key}: {len(missing)}/{len(stated)} stated table numbers did not "
            f"reach cells; e.g. {sorted(missing)[:8]}"
        )
        checked += 1
        if checked >= 4:
            break
    assert checked, (
        "no custody DOCX had >=20 decimal table values -- this assertion ran "
        "against nothing, which is a false green, not a pass"
    )
