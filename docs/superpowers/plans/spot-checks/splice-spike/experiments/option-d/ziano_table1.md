### Table 1

*Descriptive and omnibus inferential statistics, across original studies and replications.*

**Note: Camelot detected this as ONE table (52×14). The landscape page contains two side-by-side sub-tables ("Paying to know" and "Choice under risk"). Camelot merged them into a single wide extraction with "/" placeholders where the left sub-table had no data for a given study. The markdown below represents the raw Camelot output. A post-processing step would be needed to cleanly split and render the two sub-tables separately.**

---

#### Raw Camelot extraction (merged, 52 rows × 14 columns)

| Study | N | Choice | Win | Loss | Uncertain / Inferential Statistics | ES [95% CI] | N | Choice | Win | Loss | Uncertain | Inferential Statistics | ES [95% CI] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| *Paying to know →* | | | | | | | *Choice under risk →* | | | | | | |
| Tversky & Shafir, 1992, original (within-subject) | / | / | / | / | / | / | 98 | Accept (%) | 68 (69%) | 58 (59%) | 35 (34%) | | |
| | / | / | / | / | / | / | | Reject (%) | 30 (31%) | 40 (41%) | 63 (66%) | | |
| Tversky & Shafir, 1992, original (between-subject) | 199 | Buy (%) | 36 (54%) | 38 (57%) | 21 (32%) χ²(4)=19.02, p<.001 | Cramer's V = 0.218 [0.137, 0.317] | 213 | Accept (%) | | 49 (69%)¹ | 40 (57%)¹ | χ²(2)=13.89, p<.001 | Cramer's V = 0.255 [0.144, 0.394] |
| | | Not buy (%) | 11 (16%) | 8 (12%) | 4 (7%) | | | Reject (%) | | 22 (31%)¹ | 31 (43%)¹ | | |
| | | Pay $5 (%) | 20 (30%) | 21 (31%) | 41 (61%) | | | | | | | | |
| Tversky & Shafir, 1992, modified gambles (between-subject) | / | / | / | / | / | / | 171 | Accept (%) | 42 (73%)¹ | 39 (69%)¹ | 43 (75%)¹ | χ²(2)=0.76, p=.68 | Cramer's V = 0.067 [−0.108, 0.218] |
| | / | / | / | / | / | / | | Reject (%) | 15 (27%)¹ | 18 (31%)¹ | 14 (25%)¹ | | |
| Kühberger et al., 2001, exp. 1 (between-subject) | / | / | / | / | / | / | 177 | Accept (%) | (60%)² | (47%)² | (47%)² | ... | ... |
| | / | / | / | / | / | / | | Reject (%) | (40%)² | (53%)² | (53%)² | ... | ... |
| Kühberger et al., 2001, exp. 2 (between-subject) | / | / | / | / | / | / | 184 | Accept (%) | (83%)² | (70%)² | (62%)² | ... | ... |
| | / | / | / | / | / | / | | Reject (%) | (17%)² | (30%)² | (38%)² | ... | ... |
| Kühberger et al., 2001, exp. 3 (within-subject) | / | / | / | / | / | / | 35 | Accept (%) | 28 (80%)¹ | 13 (37%)¹ | 15 (43%)¹ | ... | ... |
| | / | / | / | / | / | / | | Reject (%) | 7 (20%)¹ | 22 (63%)¹ | 20 (57%)¹ | ... | ... |
| Kühberger et al., 2001, exp. 4 (between-subject) | / | / | / | / | / | / | 97 | Accept (%) | (68%)² | (32%)² | (38%)² | ... | ... |
| | / | / | / | / | / | / | | Reject (%) | (32%)² | (68%)² | (62%)² | ... | ... |
| Lambdin & Burdsal, 2007 (within-subject) | / | / | / | / | / | / | 55 | Accept (%) | 35 (64%) | 26 (47%) | 21 (38%) | ... | ... |
| | / | / | / | / | / | / | | Reject (%) | 20 (36%) | 31 (53%) | 34 (62%) | ... | ... |
| Present work (within-subject) | 445 | Buy (%) | 256 (58%) | 127 (29%) | 99 (22%) | † | 445 | Accept (%) | 164 (37%) | 187 (42%) | 165 (37%) | | † |

*Camelot accuracy: 99.2, flavor: stream*

---

**Extraction quality notes:**

- "/" cells in the "Paying to know" columns for most studies = Camelot correctly captured the empty region from the PDF (those studies only had "Choice under risk" data).
- Multi-line cells (e.g. study names split across 3 rows like "Tversky & Shafir, 1992," / "original (within-" / "subject)") were **not** merged by Camelot — they appear as separate rows with the continuation rows having only the hanging text. This is a structural problem requiring post-processing.
- "(cid:0)" artifact appeared in one cell for a negative-sign character that wasn't properly encoded in the PDF font.
- The two sub-tables were **not** separated; Camelot treated the landscape page as one 14-column table.
- Edge_tol tuning (50, 100, 200, 500) produced identical results — the page geometry is unambiguous.
