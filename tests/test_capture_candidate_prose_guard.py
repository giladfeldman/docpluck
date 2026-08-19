"""A paragraph of Discussion must not win a caption on SHAPE alone (v2.4.134).

``extract_structured._pick_better_table`` arbitrates a caption's region-driven and
auto-detected candidates on structural shape — column count, then populated-cell
count — and never asked whether either grid is plausibly a table at all. So when
Camelot's legacy auto-detect happened to structure a Discussion paragraph as a 4x2
grid and the token pairing attached ``Table 7``'s caption to it, that grid replaced
the raw_text channel's gold-exact 3x5 descriptives, and the rendered ``### Table 7``
carried its caption and ZERO data values.

``whitespace.grid_is_body_prose`` is the one content-plausibility question that is
safe to ask of ANY capture path. It is deliberately far narrower than
``_whitespace_grid_is_clean``: widening that whole gate to the auto-detect path was
tried on 2026-08-04 and rejected because it discarded legitimate-but-imperfect
auto-detect grids. Prose dominance is the sub-test a real table passes and a
paragraph cannot.

Real-DOI evidence: ``maier_2023_collabra`` Table 7, "Perceived Impact (Extension):
Descriptives" — pinned end-to-end by ``tests/test_maier_t7_content_plausibility.py``.
The tests here pin the PREDICATE, so a future edit to its thresholds shows up as a
named failure rather than as one paper quietly changing.

ON "WATCHED FAILING FIRST": these tests call the predicate DIRECTLY, so stubbing it
out would fail them tautologically and prove nothing. The reproduction against unfixed
code lives where it means something — ``tests/test_maier_t7_content_plausibility.py``,
which was `xfail(strict)` against the real pipeline and XPASSed the moment this guard
landed. What THESE tests are for is the opposite risk: the `TestAccepted` cases must
pass in both arms, and they are the guard against the predicate becoming over-eager
and deleting real tables. Verified 2026-08-19 that all four hold at the shipped
threshold.
"""

from __future__ import annotations

from docpluck.tables import Cell
from docpluck.tables.whitespace import grid_is_body_prose


def _grid(rows: list[list[str]]) -> list[Cell]:
    return [
        {"r": r, "c": c, "rowspan": 1, "colspan": 1, "text": text,
         "is_header": False, "bbox": (0.0, 0.0, 0.0, 0.0)}
        for r, row in enumerate(rows)
        for c, text in enumerate(row)
    ]


# The grid that actually shipped as maier Table 7, cell for cell.
_MAIER_T7_PROSE = _grid([
    ["Following  the  analyses  conducted  in  Study  1  of  Small", ""],
    ["4", ""],
    ["et  al.  (2007),  we  carried  out  a  2  (Explicit  Learning)  x  2",
     "Learning Main Effects and Interaction (with Joint"],
    ["(Identifiability) two-way ANOVA (i.e., cells Identifiable-Ex-",
     "Condition) [Extension]"],
])


class TestRejected:
    def test_the_maier_table7_prose_grid_is_rejected(self):
        assert grid_is_body_prose(_MAIER_T7_PROSE)

    def test_a_wholly_prose_grid_is_rejected(self):
        assert grid_is_body_prose(_grid([
            ["participants were asked to recall a hurting experience that"],
            ["they were highly empathetic to the person who had hurt them"],
            ["and then described the interpersonal injury they received"],
        ]))

    def test_one_prose_row_in_three_is_enough_without_a_header(self):
        """The threshold is one third — the same ratio the whitespace guard uses."""
        assert grid_is_body_prose(_grid([
            ["and then we carried out a two-way ANOVA on the pooled sample", ""],
            ["3.47", "1.23"],
            ["having established that the manipulation worked as intended", ""],
        ]))

    def test_prose_beside_data_does_NOT_count(self):
        """Corrected 2026-08-19 — this test used to assert the opposite.

        It was written against the over-broad rule and encoded it: a grid whose three
        rows carry real numbers is NOT body prose, however much prose sits beside
        them. Asserting otherwise is what destroyed `10.48550/arxiv.2406.11713`
        Table 1's FID values. A test that pins an over-broad guard is the guard's
        strongest defender, which is why it is corrected here rather than deleted.
        """
        assert not grid_is_body_prose(_grid([
            ["3.47", "and then the participants were asked to recall a hurt"],
            ["2.91", "1.37"],
            ["2.94", "1.35"],
        ]))


class TestAccepted:
    """These must pass in BOTH arms. A predicate that also rejects them is worse
    than the defect: it would delete real tables instead of a paragraph."""

    def test_a_descriptives_table_is_not_prose(self):
        assert not grid_is_body_prose(_grid([
            ["", "Identifiable", "Explicit", "Joint", "Total"],
            ["Explicit learning intervention", "3.47 [1.23] (170)", "2.91 [1.37] (159)",
             "2.94 [1.35] (173)", "3.11 [1.34] (502)"],
            ["No explicit learning intervention", "3.31 [1.25] (165)", "2.99 [1.34] (176)",
             "3.11 [1.42] (161)", "3.14 [1.34] (502)"],
        ]))

    def test_a_categorical_design_table_is_not_prose(self):
        """Short labels, no numbers — a real table the numeric gates already spare."""
        assert not grid_is_body_prose(_grid([
            ["Design facet", "Replication study"],
            ["IV operationalization", "Same"],
            ["DV operationalization", "Same"],
            ["Population", "Different"],
        ]))

    def test_a_long_but_short_worded_note_row_is_not_prose(self):
        """One wordy row in five is under the third — a legitimate footnote stays."""
        assert not grid_is_body_prose(_grid([
            ["Variable", "M", "SD"],
            ["Apology", "5.63", "2.84"],
            ["Empathy", "13.22", "5.95"],
            ["Forgiving", "16.82", "6.73"],
            ["Note: scores ranged from 2 to 10 across all measured conditions", "", ""],
        ]))

    def test_an_empty_grid_is_not_prose(self):
        assert not grid_is_body_prose([])

    def test_a_header_row_vetoes_the_verdict(self):
        """A real table with one absorbed prose line is still a real table.

        `_trim_trailing_prose_rows` is what removes the absorbed line; condemning
        the whole grid for it would throw away the data above.
        """
        assert not grid_is_body_prose(_grid([
            ["Condition", "M", "SD"],
            ["Explicit", "3.47", "1.23"],
            ["we carried out a two-way ANOVA on the pooled sample", "", ""],
        ]))

    def test_the_amc_qualitative_review_table_is_not_prose(self):
        """10.5465/amc.2022.0006 Table 4 — the false positive that the veto closes.

        A 33x4 synthesis table whose every data cell is a sentence-length phrase.
        Prose dominance alone condemned all 70 cells and 2,008 characters of it.
        """
        assert not grid_is_body_prose(_grid([
            ["Recommendations for Future Research", "", "", ""],
            ["Criteria", "Synthesis and Evaluation", "Recommendations", ""],
            ["Definitions and", "1", "Evolution of dimensionality to",
             "Develop and validate taxonomies of CSR initiatives"],
            ["operationalizations", "", "include more discretionary",
             "characteristics, CSR beneficiaries, and specific"],
            ["aspects", "", "implicated by various types of CSR initiatives", ""],
        ]))


class TestHeaderVetoCannotBeBoughtWithOneShortCell:
    """A header NAMES COLUMNS, so it needs at least two of them.

    Found independently by BOTH pre-release reviewers on 2026-08-19 and reproduced
    before fixing: `_is_header_like_row` returns True for a single short non-numeric
    cell, so prepending one row containing the word `Overview` to an otherwise
    unambiguous Discussion paragraph flipped `grid_is_body_prose` from True to False
    and waved the entire grid through. Column-splitting a paragraph routinely leaves
    ONE stray short cell in some row — that is how maier Table 7's footnote-digit
    row `4` arose — so this was not a corner case.

    Watched failing first by removing the `_HEADER_MIN_NAMED_COLUMNS` check:
    `test_one_short_cell_does_not_veto` went red.
    """

    _PROSE = [
        ["Following the analyses conducted in Study 1 of Small et al we", ""],
        ["carried out a two way ANOVA on the pooled sample of participants", ""],
        ["and found that the interaction was not significant in either study", ""],
    ]

    def test_the_paragraph_alone_is_prose(self):
        """Premise guard: if this stopped being prose the tests below prove nothing."""
        assert grid_is_body_prose(_grid(self._PROSE))

    def test_one_short_cell_does_not_veto(self):
        assert grid_is_body_prose(_grid([["Overview", ""]] + self._PROSE))

    def test_a_row_naming_two_columns_still_vetoes(self):
        """The control: a real header must keep its power to spare a real table."""
        assert not grid_is_body_prose(
            _grid([["Criteria", "Recommendations"]] + self._PROSE)
        )

    def test_the_amc_header_still_vetoes(self):
        """10.5465/amc.2022.0006 Table 4's real header names three columns."""
        assert not grid_is_body_prose(_grid([
            ["Criteria", "Synthesis and Evaluation", "Recommendations", ""],
            ["Definitions and", "1", "Evolution of dimensionality to",
             "Develop and validate taxonomies of CSR initiatives"],
            ["operationalizations", "", "include more discretionary",
             "characteristics, CSR beneficiaries, and specific"],
            ["aspects", "", "implicated by various types of CSR initiatives", ""],
        ]))


class TestAGridCarryingRealDataIsNeverProse:
    """The guard stops a paragraph with NO table data. It is not a cleanliness test.

    Found by re-running `tools/diag/table_capture_guard_diff.py` on the tree AFTER
    the reviewers' round — which is exactly why the gate is re-run on the FINAL tree
    and not the reviewed one. `10.48550/arxiv.2406.11713` Table 1 is a 12x7 grid whose
    first rows are absorbed Discussion prose and whose later rows are the real table:

        Dataset | Scale factor f | Ouput size | FID
        CIFAR-10 | 2 | 16 x 16 x 4 | 1.32

    Prose dominance alone condemned all 27 cells, and the raw_text fallback carried
    61 of the 511 characters — the published FID values were simply gone. A grid
    carrying real data is never body prose, however much prose it also absorbed.

    Watched failing first (2026-08-19) by removing the `_MIN_CLEAN_DATA_ROWS` check:
    `test_the_arxiv_mixed_grid_is_spared` went red.
    """

    _ARXIV_T1 = [
        ["for each dataset. All models were trained until convergence,"],
        ["defined as the point where there was no further substantial"],
        ["improvement in FID."],
        ["5. Experiments"],
        ["We first present a detailed description of the experimental"],
        ["Dataset", "Scale factor f", "Ouput size", "FID"],
        ["tal", "settings, dataset,", "and evaluation metrics used in Sec-"],
        ["CIFAR-10", "2", "16 x 16 x 4", "1.32"],
        ["CelebA-HQ", "4", "64 x 64 x 4", "2.13"],
    ]

    def test_the_arxiv_mixed_grid_is_spared(self):
        assert not grid_is_body_prose(_grid(self._ARXIV_T1))

    def test_maier_table7_is_still_prose_with_its_stray_digit(self):
        """The control that keeps the rule honest.

        maier Table 7's grid carries ONE clean-data cell — the stray footnote digit
        `4` — so a "any number at all spares it" rule would have undone defect #3.
        `_MIN_CLEAN_DATA_ROWS` is 2, and it is reused from `_whitespace_grid_is_clean`
        rather than restated.
        """
        assert grid_is_body_prose(_MAIER_T7_PROSE)

    def test_a_paragraph_with_no_numbers_is_still_prose(self):
        assert grid_is_body_prose(_grid([
            ["participants were asked to recall a hurting experience that"],
            ["they were highly empathetic to the person who had hurt them"],
            ["and then described the interpersonal injury they received"],
        ]))
