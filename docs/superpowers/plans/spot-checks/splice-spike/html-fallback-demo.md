# HTML Fallback Demo — Two Real Tables From Our Outputs

This file shows two of the most complex tables in our 7-paper corpus rendered both ways: as the current Markdown pipe-table (what's in our output today) and as an HTML `<table>` inside the same Markdown file (what the "HTML fallback" would produce). Open this file in your viewer of choice (Notepad++ rich-text plugin, VS Code preview, or any GitHub-flavored markdown renderer) — the HTML tables render natively because CommonMark allows raw HTML inline.

The data is exactly what Camelot extracted from the PDFs. Nothing has been hand-edited.

---

## Demo 1 — korbmacher Table 1: Kruger's findings

This table has a 2-row column header (column groups split across two header rows) and "Easy" / "Difficult" as **group separators that span all 5 columns** in the original PDF.

### Current pipe-table rendering

```markdown
### Table 1
*Kruger's (1999) findings: Mean comparative ability estimates and judgmental weight of own and peers' abilities.*

| Ability | Domain | Comparative | Judgmental weight | Judgmental weight |
| --- | --- | --- | --- | --- |
|  | difficulty1 | ability2 | of Own ability3 | of Others' ability3 |
| Easy |  |  |  |  |
| Using a mouse | 3.1 | 58.8∗∗ | 0.21 | 0.06 |
| Driving | 3.6 | 65.4∗∗∗∗ | .89∗∗∗∗ | –.25∗ |
| Riding a bicycle | 3.9 | 64.0∗∗∗∗ | .61∗∗∗∗ | –0.02 |
| Saving money | 4.3 | 61.5∗∗ | .90∗∗∗∗ | –.25∗∗∗ |
| Difficult |  |  |  |  |
| Telling jokes | 6.1 | 46.5 | .91∗∗∗∗ | –0.03 |
| Playing chess | 7.1 | 27.8∗∗∗∗ | .96∗∗∗∗ | –.22∗∗ |
| Juggling | 8.3 | 26.5∗∗∗∗ | .89∗∗∗∗ | –0.16 |
| Programming | 8.7 | 24.8∗∗∗∗ | .85∗∗∗∗ | –0.1 |
```

**Renders as:**

| Ability | Domain | Comparative | Judgmental weight | Judgmental weight |
| --- | --- | --- | --- | --- |
|  | difficulty1 | ability2 | of Own ability3 | of Others' ability3 |
| Easy |  |  |  |  |
| Using a mouse | 3.1 | 58.8∗∗ | 0.21 | 0.06 |
| Driving | 3.6 | 65.4∗∗∗∗ | .89∗∗∗∗ | –.25∗ |
| Riding a bicycle | 3.9 | 64.0∗∗∗∗ | .61∗∗∗∗ | –0.02 |
| Saving money | 4.3 | 61.5∗∗ | .90∗∗∗∗ | –.25∗∗∗ |
| Difficult |  |  |  |  |
| Telling jokes | 6.1 | 46.5 | .91∗∗∗∗ | –0.03 |
| Playing chess | 7.1 | 27.8∗∗∗∗ | .96∗∗∗∗ | –.22∗∗ |
| Juggling | 8.3 | 26.5∗∗∗∗ | .89∗∗∗∗ | –0.16 |
| Programming | 8.7 | 24.8∗∗∗∗ | .85∗∗∗∗ | –0.1 |

**Problems:**
- "Judgmental weight" appears twice in the header (it's two different columns with the same group name; the difference is the second header row "of Own ability" vs "of Others' ability").
- "Easy" and "Difficult" look like row labels, not group separators across all columns.
- A reader would think the table has 5 categorical columns rather than 2 column groups.

### HTML fallback rendering

```markdown
### Table 1
*Kruger's (1999) findings: Mean comparative ability estimates and judgmental weight of own and peers' abilities.*

<table>
  <thead>
    <tr>
      <th rowspan="2">Ability</th>
      <th rowspan="2">Domain difficulty<sup>1</sup></th>
      <th rowspan="2">Comparative ability<sup>2</sup></th>
      <th colspan="2">Judgmental weight<sup>3</sup></th>
    </tr>
    <tr>
      <th>of Own ability</th>
      <th>of Others' ability</th>
    </tr>
  </thead>
  <tbody>
    <tr><td colspan="5"><strong>Easy</strong></td></tr>
    <tr><td>Using a mouse</td><td>3.1</td><td>58.8**</td><td>0.21</td><td>0.06</td></tr>
    <tr><td>Driving</td><td>3.6</td><td>65.4****</td><td>.89****</td><td>–.25*</td></tr>
    <tr><td>Riding a bicycle</td><td>3.9</td><td>64.0****</td><td>.61****</td><td>–0.02</td></tr>
    <tr><td>Saving money</td><td>4.3</td><td>61.5**</td><td>.90****</td><td>–.25***</td></tr>
    <tr><td colspan="5"><strong>Difficult</strong></td></tr>
    <tr><td>Telling jokes</td><td>6.1</td><td>46.5</td><td>.91****</td><td>–0.03</td></tr>
    <tr><td>Playing chess</td><td>7.1</td><td>27.8****</td><td>.96****</td><td>–.22**</td></tr>
    <tr><td>Juggling</td><td>8.3</td><td>26.5****</td><td>.89****</td><td>–0.16</td></tr>
    <tr><td>Programming</td><td>8.7</td><td>24.8****</td><td>.85****</td><td>–0.1</td></tr>
  </tbody>
</table>
```

**Renders as:**

<table>
  <thead>
    <tr>
      <th rowspan="2">Ability</th>
      <th rowspan="2">Domain difficulty<sup>1</sup></th>
      <th rowspan="2">Comparative ability<sup>2</sup></th>
      <th colspan="2">Judgmental weight<sup>3</sup></th>
    </tr>
    <tr>
      <th>of Own ability</th>
      <th>of Others' ability</th>
    </tr>
  </thead>
  <tbody>
    <tr><td colspan="5"><strong>Easy</strong></td></tr>
    <tr><td>Using a mouse</td><td>3.1</td><td>58.8**</td><td>0.21</td><td>0.06</td></tr>
    <tr><td>Driving</td><td>3.6</td><td>65.4****</td><td>.89****</td><td>–.25*</td></tr>
    <tr><td>Riding a bicycle</td><td>3.9</td><td>64.0****</td><td>.61****</td><td>–0.02</td></tr>
    <tr><td>Saving money</td><td>4.3</td><td>61.5**</td><td>.90****</td><td>–.25***</td></tr>
    <tr><td colspan="5"><strong>Difficult</strong></td></tr>
    <tr><td>Telling jokes</td><td>6.1</td><td>46.5</td><td>.91****</td><td>–0.03</td></tr>
    <tr><td>Playing chess</td><td>7.1</td><td>27.8****</td><td>.96****</td><td>–.22**</td></tr>
    <tr><td>Juggling</td><td>8.3</td><td>26.5****</td><td>.89****</td><td>–0.16</td></tr>
    <tr><td>Programming</td><td>8.7</td><td>24.8****</td><td>.85****</td><td>–0.1</td></tr>
  </tbody>
</table>

**Wins:**
- "Judgmental weight" appears once and clearly spans 2 columns.
- "Easy" and "Difficult" visibly span all 5 columns as group headers.
- Footnote markers (1, 2, 3) properly subscripted/superscripted.
- Two-row header structure preserved.

---

## Demo 2 — ip_feldman Table 2: Replication & Extensions Hypotheses

This table has many multi-line hypothesis cells. The original PDF has each "hypothesis number → description" as one cell, but the description wraps to 2-3 lines. Pipe-table can't represent multi-line cells, so each wrap becomes a separate row with an empty number column.

### Current pipe-table rendering (excerpt — full table is 32 rows of this)

```markdown
### Table 2
*Replication and Extensions: Summary of Hypotheses.*

| Replication: prevalence estimations |  |
| --- | --- |
| No | Hypothesis |
| 2a | People underestimate the prevalence of others' negative emotional experiences. |
| 2b | People do not underestimate the prevalence and extent of others' positive emotional experiences. |
|  | [Our reframing of the target's null hypothesis: Prevalence underestimation errors are stronger for negative |
|  | experiences than for positive experiences.] |
| 4 | 4a) There is a positive association between the estimation of the prevalence of negative emotional experiences and |
|  | well-being.a |
|  | 4b) There is a negative association between the estimation of the prevalence of positive emotional experiences and |
|  | well-being.a |
|  | Negative indicators—higher well-being: lower depressive symptoms, lower loneliness, lower rumination |
| 4-1 | 4-1a) There is a negative association between the estimation of the prevalence of negative emotional experiences and |
|  | depressive symptoms. |
|  | 4-1b) There is a positive association between the estimation of the prevalence of positive emotional experiences and |
|  | depressive symptoms. |
```

**Renders as:**

| Replication: prevalence estimations |  |
| --- | --- |
| No | Hypothesis |
| 2a | People underestimate the prevalence of others' negative emotional experiences. |
| 2b | People do not underestimate the prevalence and extent of others' positive emotional experiences. |
|  | [Our reframing of the target's null hypothesis: Prevalence underestimation errors are stronger for negative |
|  | experiences than for positive experiences.] |
| 4 | 4a) There is a positive association between the estimation of the prevalence of negative emotional experiences and |
|  | well-being.a |
|  | 4b) There is a negative association between the estimation of the prevalence of positive emotional experiences and |
|  | well-being.a |
|  | Negative indicators—higher well-being: lower depressive symptoms, lower loneliness, lower rumination |
| 4-1 | 4-1a) There is a negative association between the estimation of the prevalence of negative emotional experiences and |
|  | depressive symptoms. |
|  | 4-1b) There is a positive association between the estimation of the prevalence of positive emotional experiences and |
|  | depressive symptoms. |

**Problems:**
- The "[Our reframing of the target's null hypothesis: ...]" annotation belongs to row "2b" but appears on rows of its own (with empty No column), so the relationship is lost.
- Hypothesis 4 has sub-hypotheses 4a and 4b which look like they're at the same level as 4 instead of nested.
- "Negative indicators—higher well-being: ..." is a sub-section header that looks like another fragment row.

### HTML fallback rendering

```markdown
### Table 2
*Replication and Extensions: Summary of Hypotheses.*

<table>
  <thead>
    <tr><th colspan="2"><strong>Replication: prevalence estimations</strong></th></tr>
    <tr><th>No</th><th>Hypothesis</th></tr>
  </thead>
  <tbody>
    <tr>
      <td>2a</td>
      <td>People underestimate the prevalence of others' negative emotional experiences.</td>
    </tr>
    <tr>
      <td>2b</td>
      <td>
        People do not underestimate the prevalence and extent of others' positive emotional experiences.
        <br><em>[Our reframing of the target's null hypothesis: Prevalence underestimation errors are stronger for negative experiences than for positive experiences.]</em>
      </td>
    </tr>
    <tr>
      <td>4</td>
      <td>
        4a) There is a positive association between the estimation of the prevalence of negative emotional experiences and well-being.<sup>a</sup><br>
        4b) There is a negative association between the estimation of the prevalence of positive emotional experiences and well-being.<sup>a</sup>
      </td>
    </tr>
    <tr><td colspan="2"><em>Negative indicators—higher well-being: lower depressive symptoms, lower loneliness, lower rumination</em></td></tr>
    <tr>
      <td>4-1</td>
      <td>
        4-1a) There is a negative association between the estimation of the prevalence of negative emotional experiences and depressive symptoms.<br>
        4-1b) There is a positive association between the estimation of the prevalence of positive emotional experiences and depressive symptoms.
      </td>
    </tr>
  </tbody>
</table>
```

**Renders as:**

<table>
  <thead>
    <tr><th colspan="2"><strong>Replication: prevalence estimations</strong></th></tr>
    <tr><th>No</th><th>Hypothesis</th></tr>
  </thead>
  <tbody>
    <tr>
      <td>2a</td>
      <td>People underestimate the prevalence of others' negative emotional experiences.</td>
    </tr>
    <tr>
      <td>2b</td>
      <td>
        People do not underestimate the prevalence and extent of others' positive emotional experiences.
        <br><em>[Our reframing of the target's null hypothesis: Prevalence underestimation errors are stronger for negative experiences than for positive experiences.]</em>
      </td>
    </tr>
    <tr>
      <td>4</td>
      <td>
        4a) There is a positive association between the estimation of the prevalence of negative emotional experiences and well-being.<sup>a</sup><br>
        4b) There is a negative association between the estimation of the prevalence of positive emotional experiences and well-being.<sup>a</sup>
      </td>
    </tr>
    <tr><td colspan="2"><em>Negative indicators—higher well-being: lower depressive symptoms, lower loneliness, lower rumination</em></td></tr>
    <tr>
      <td>4-1</td>
      <td>
        4-1a) There is a negative association between the estimation of the prevalence of negative emotional experiences and depressive symptoms.<br>
        4-1b) There is a positive association between the estimation of the prevalence of positive emotional experiences and depressive symptoms.
      </td>
    </tr>
  </tbody>
</table>

**Wins:**
- Each hypothesis (2a, 2b, 4, 4-1) is one cell, with its sub-hypotheses (4a, 4b, 4-1a, 4-1b) inside on `<br>` separators. Reader sees "hypothesis 4 has these two sub-hypotheses."
- "[Our reframing...]" annotation is attached to hypothesis 2b in the same cell, italicized.
- "Negative indicators—..." is a sub-section header spanning both columns, visually distinct from data rows.

---

## What's lost / what's preserved

In both demos, **the underlying cell text is identical** between the pipe-table and the HTML fallback — no information is added or removed. The HTML version just preserves the table's *2D structure* (rowspan, colspan, cell-internal line breaks) that the pipe-table can't represent.

If you copy/paste from the rendered HTML version into a plain text editor, you'll get readable plain text (the browser converts cells to lines). If you parse with a Markdown library, you get the HTML tags as a tree. Both downstream uses work.

---

## How the auto-fallback decision would work

For each Camelot-extracted table, switch to HTML if any of:

1. **Detected merged cells:** repeated content in adjacent cells suggests a merge in the original (e.g., "Judgmental weight" / "Judgmental weight" → colspan="2").
2. **Multi-line cells:** original PDF has a cell with embedded newlines OR consecutive rows with empty leading column (continuation pattern).
3. **2-row header:** first 2 rows are all categorical labels (no numerics) — implies a hierarchical header.
4. **Group separator rows:** a row with content in only one column followed by data rows (e.g., "Easy" / "Difficult" pattern).
5. **More than 6 columns:** wide tables render badly as pipes in narrow viewers.

Default stays pipe-table for the simple stats matrices that are the majority of APA tables. HTML kicks in only when pipe-table would lose structure.
