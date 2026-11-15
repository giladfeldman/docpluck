"""Build the consumer-contract probe PDF (synthetic; every number is invented).

Built on demand, never committed: the repo keeps no PDFs (`*.pdf` is ignored),
so a committed-only fixture could not run on a clone. ``invariant=1`` makes the
bytes reproducible, so the test can pin their hash.
"""
from __future__ import annotations

import io


def build_contract_structure_pdf() -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ss = getSampleStyleSheet()
    body = ss["Normal"]
    head = ss["Heading1"]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, invariant=1, title="docpluck boundary contract: structure probe",
                            author="contract fixture", leftMargin=64.8, rightMargin=64.8)

    def grid(rows):
        t = Table(rows, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        return t

    story = [
        Paragraph("A Structure Probe for the Docpluck Boundary Contract", ss["Title"]),
        Paragraph("<b>Abstract.</b> This document is a synthetic contract fixture, not a paper. It exists so a "
                  "consumer can pin the field set docpluck returns for a known input. It reports a "
                  "within-subjects design (N = 100) with two tables so that table detection and "
                  "flattened-row typing are both exercised.", body),
        Spacer(1, 8),
        Paragraph("Method", head),
        Paragraph("One hundred participants (N = 100) completed a reaction-time task under two conditions "
                  "across three time points. Alpha was set at .05.", body),
        Spacer(1, 8),
        Paragraph("Results", head),
        Paragraph("A repeated-measures analysis of variance was conducted. Table 1 reports the omnibus "
                  "effects and Table 2 reports the planned contrasts.", body),
        Spacer(1, 6),
        Paragraph("Table 1. Analysis of variance results.", body),
        grid([["Effect", "F", "df1", "df2", "p"],
              ["Condition (main effect)", "5.20", "1", "98", ".025"],
              ["Time (main effect)", "12.50", "2", "196", "<.001"],
              ["Condition x Time", "0.45", "2", "196", ".64"]]),
        Spacer(1, 10),
        Paragraph("Table 2. Planned contrasts.", body),
        grid([["Contrast", "t", "df", "p", "d"],
              ["Sleep vs Control", "2.41", "98", ".018", "0.15"],
              ["Sleep vs Nap", "-3.07", "98", ".003", "-0.31"]]),
        Spacer(1, 10),
        Paragraph("The main effect of condition was reliable, F(1, 98) = 5.20, p = .025. The planned "
                  "contrast was also reliable, t(98) = 2.41, p = .018, d = 0.15, 95% CI [0.04, 0.26], "
                  "r = .24.", body),
        Spacer(1, 8),
        Paragraph("Discussion", head),
        Paragraph("Nothing here is a finding. Every number is fabricated for the purpose of pinning an "
                  "extraction contract.", body),
    ]
    doc.build(story)
    return buf.getvalue()
