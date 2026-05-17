"""docpluck verification harness.

A regression-safe, automated extraction-and-inspection harness. It drives the
*local app* (the FastAPI extraction service the deployed product uses), saves
every output view for every normalization level, and runs deterministic
whole-corpus regression checks against a committed verdict baseline.

Built 2026-05-17 after a post-mortem found the prior loop verified the library
in isolation (never the app), per-cycle/per-target only (no corpus-wide
regression backcheck), against snapshot baselines that could themselves be
broken. See ``docs/ITERATION_VERIFICATION_LESSONS.md``.

Modules:
- ``corpus``  — discover corpus documents (PDF/DOCX/HTML) → committed manifest.
- ``extract`` — drive the local app ``/analyze`` per document × level, save views.
- ``checks``  — Tier-D deterministic checks → verdict matrix + regression diff.
"""

__all__ = ["corpus", "extract", "checks"]
