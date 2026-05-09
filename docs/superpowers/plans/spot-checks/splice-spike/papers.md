# Splice Spike — Chosen Papers

Five PDFs from `PDFextractor/test-pdfs/apa/`, picked to span the layout
variations the splice algorithm must handle.

| # | Filename | Layout condition | Why this paper |
|---|---|---|---|
| 1 | korbmacher_2022_kruger.pdf | clean single-column APA | Single-column JDM journal (page width 612pt, all line-starts cluster at x≈90); Table 1 on p. 7 is a 4×8 stats matrix of comparative ability estimates with significance stars — a compact but representative APA stats table. |
| 2 | efendic_2022_affect.pdf | two-column journal | Two-column SPPS journal (line-starts split at x≈43 and x≈309 on a 603pt page); contains five mixed-effects regression tables (Tables 1–5 across pp. 2–8), giving multiple inline-table splice targets within a narrow two-column flow. |
| 3 | chandrashekar_2023_mp.pdf | multi-table page | Page 10 contains Tables 7, 8, 9, and 10 consecutively on a single page: two logistic-regression tables (7 & 8), one effect-size comparison table (9), and one signal/directionality summary table (10) — four distinct table objects for pdfplumber to detect and splice in sequence. |
| 4 | ziano_2021_joep.pdf | table at page boundary | Table 1 spans landscape pages 2–3 (page 3 begins with "Table 1 (continued)"); the table also has two side-by-side column groups ("Paying to know" / "Choice under risk"), each with sub-columns (Win / Loss / Uncertain / Inferential Statistics / ES [95% CI]) — a multi-level header on a landscape-format multi-page table. |
| 5 | ip_feldman_2025_pspb.pdf | structurally-complex table | Page 13 contains Table 8 (a 11×11 correlation matrix) where the PDF text stream runs in reverse-rotated order — pdftotext emits words backwards (e.g. "elbaT", "serusaeM") indicating the table is physically rotated 90° on the page. This is the most extreme pdftotext-mangling scenario in the corpus. |

If condition 5 was not satisfied by any APA folder paper, this is noted
and the spike's coverage of that condition is acknowledged as untested.

---

## Inspection notes

Papers inspected directly (via pdfplumber geometry analysis and text extraction):

- **efendic_2022_affect.pdf** — inspected pp. 1–12; confirmed two-column SPPS layout (x-position clusters at ~43 and ~309); Tables 1–5 identified with reference lines.
- **chen_2021_jesp.pdf** — inspected pp. 1–15; also two-column JESP layout; not chosen because efendic better matches the SPPS benchmark cited in handoffs, and chen's page 10 (landscape table) overlaps with condition 4.
- **korbmacher_2022_kruger.pdf** — inspected pp. 1–10; confirmed single-column JDM layout (line-starts cluster only at x≈90); Table 1 on p. 7 confirmed as a 4-column × 8-row stats table.
- **chandrashekar_2023_mp.pdf** — scanned all 55 pages for table-title lines; page 10 confirmed as having four consecutive table headings (Table7 / Table8 / Table9 / Table10) with full statistical content on one page.
- **ziano_2021_joep.pdf** — inspected pp. 2–5; confirmed landscape page dimensions (743 × 544 pt); Table 1 spans pp. 2–3 with explicit "(continued)" heading; multi-level column headers confirmed.
- **ip_feldman_2025_pspb.pdf** — inspected pp. 3, 4, 6, 7, 13–15; confirmed rotated text on p. 13 (words appear reversed in pdftotext output); confirmed page-boundary tables at pp. 3–4 top (Table 1 / Table 2 headers at line 1).

Papers trusted from prior handoff recommendations without deep inspection:
- None. All five chosen papers were verified by direct text/geometry extraction.

## Why the plan's condition-1 recommendation was substituted

The plan recommended `efendic_2022_affect.pdf` for condition 1 ("clean single-column APA"). Inspection shows efendic is a **two-column** SPPS journal (Social Psychological and Personality Science), not single-column. It was reassigned to condition 2. `korbmacher_2022_kruger.pdf` (JDM, Judgment and Decision Making) is a verified single-column paper and was substituted for condition 1. The plan's recommendation for condition 2 (`chen_2021_jesp.pdf`) was not needed once efendic filled that slot.
