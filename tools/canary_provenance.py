"""Input-feed provenance helpers for the docpluck-iterate canary (rec R-0003).

Cross-project lesson transfer (CitationGuard => docpluck): the verification
substrate (the PDF rendered for audit) must be byte-equal to the canonical
production input feed BEFORE scoring. docpluck already scores render-vs-AI-gold
(never vs a deterministic extractor -- CLAUDE.md hard rule), so the residual
gap is INPUT provenance: a render of a drifted PDF scored against a gold made
from the original PDF is the same "wrong substrate" bug class that gave
CitationGuard a misleading whole-run score.

canary.json pins each canary paper's expected input-PDF sha256
(`expected_pdf_sha`). `render_for_audit.py` and
`tests/test_canary_provenance.py` use these helpers to enforce byte-equality.
Un-pinned keys are NOT enforced, so the guard is purely additive.
"""
from __future__ import annotations

import json
from typing import Optional, Tuple


def load_expected_sha(canary_path: str, key: str) -> Optional[str]:
    """Return the pinned expected_pdf_sha for ``key`` from canary.json, or None.

    Searches both ``canary.fixed[]`` and ``canary.rotating_pool[]``. Returns
    None when the key is absent or carries no pin (un-pinned keys are a no-op).
    """
    try:
        with open(canary_path, encoding="utf-8") as f:
            canary = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    block = canary.get("canary", {}) or {}
    papers = (block.get("fixed", []) or []) + (block.get("rotating_pool", []) or [])
    for paper in papers:
        if paper.get("key") == key:
            return paper.get("expected_pdf_sha") or None
    return None


def check_provenance(
    key: str, actual_sha: str, expected_sha: Optional[str]
) -> Tuple[bool, str]:
    """Verify a located PDF's sha matches its pinned canonical input sha.

    Returns ``(ok, message)``. When ``expected_sha`` is falsy the check is a
    no-op (``(True, "")``) so un-pinned keys keep current behaviour. On a
    mismatch returns ``(False, <self-diagnosing message naming key + shas>)``.
    """
    if not expected_sha:
        return True, ""
    if actual_sha == expected_sha:
        return True, ""
    msg = (
        f"INPUT-FEED PROVENANCE MISMATCH for {key}: located PDF "
        f"sha256={actual_sha} does not match the pinned "
        f"expected_pdf_sha={expected_sha}. The verification substrate is NOT "
        "byte-equal to the canonical production input feed; refusing to "
        "render/score a divergent input (rec R-0003). Re-onboard the canonical "
        "PDF, or update the pin in canary.json if the input legitimately changed."
    )
    return False, msg
