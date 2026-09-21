"""Losing layout in the RENDER channel must be recorded, not shrugged off.

Why this file exists (2026-09-21). `render.py` materialises its own LayoutDoc
and the handler was:

    except Exception:
        layout_doc = None

with no record of any kind. Losing layout here disables every layout-gated step
downstream AT ONCE -- cell geometry, the title rescue, the layout-proven glyph
repairs -- and the render still returns a complete-looking `.md`.

This channel specifically, and that is the point. `render_pdf_to_markdown` is
the one that produces the document a user reads, and this file's own history
says the uninstrumented channel is where the losses hide, because
instrumentation is what attracts an audit (L-032: two published-statistics
deletions found in `render.py` only after someone thought to look at the channel
that had no counters, while `normalize.py`'s numeric rules got measured across
297 papers *because* they populated `changes_made`). `RenderReport` gained a
`fallbacks` field in v2.4.134 for exactly this reason -- and the layout
materialisation a few lines above it still reported nothing into it.
"""

import pytest

from docpluck.render import RenderReport, render_pdf_to_markdown
from docpluck.testing import require_corpus_pdf

# A two-column paper with tables and figures, so layout is genuinely used
# downstream rather than merely fetched.
_PAPER = "apa/chan_feldman_2025_cogemo.pdf"


@pytest.fixture(scope="module")
def paper_bytes() -> bytes:
    # require_, not corpus_pdf: a paper this gate claims to test and cannot read
    # is a FAILURE, never a skip.
    return require_corpus_pdf(_PAPER).read_bytes()


def test_the_render_channel_gets_its_layout_on_the_default_path(paper_bytes):
    """Layout is available during a real render, and nothing says otherwise."""
    report = RenderReport()
    md = render_pdf_to_markdown(paper_bytes, report=report)
    assert md.strip(), "render produced nothing"
    assert "render_layout_unavailable" not in report.fallbacks, (
        "the render channel could not obtain layout on a healthy path, so every "
        "layout-gated step below it silently did not run. "
        f"fallbacks={report.fallbacks}"
    )


def test_a_lost_layout_is_recorded_rather_than_shrugged_off(paper_bytes, monkeypatch):
    """Two-sided control: break it, and require the report to say so.

    Without this arm the assertion above could pass while the failure mode
    stayed invisible -- and a vacuous gate is worse than none, because it is
    counted.
    """
    import docpluck.extract_layout as el

    real = el.extract_pdf_layout

    def _boom(*a, **kw):
        # Only the render channel's own whole-document materialisation. Other
        # callers (extraction's page-subset splice, the structured path) must
        # keep working, or this control would be testing a different loss.
        import sys

        if sys._getframe(1).f_code.co_name == "_render_pdf_to_markdown":
            raise RuntimeError("injected: layout unavailable")
        return real(*a, **kw)

    monkeypatch.setattr(el, "extract_pdf_layout", _boom)

    report = RenderReport()
    md = render_pdf_to_markdown(paper_bytes, report=report)

    assert "render_layout_unavailable" in report.fallbacks, (
        "the render channel lost layout and the report is silent about it; a "
        "consumer cannot tell this .md from one rendered with full layout. "
        f"fallbacks={report.fallbacks}"
    )
    # The render must still SUCCEED -- degrading is the correct behaviour here,
    # and this gate is about saying so, not about turning a degradation into a
    # crash.
    assert md.strip(), "render must still produce output without layout"
