"""
Quality Scoring
================
From CitationGuard's _check_text_quality() + MetaESCI's artifact detection.
"""

import re

COMMON_WORDS = {
    "the", "and", "for", "that", "with", "this", "from", "are", "was",
    "were", "have", "has", "been", "not", "but", "which", "their", "can",
    "will", "one", "all", "would", "there", "what", "about", "when",
    "study", "research", "results", "data", "analysis", "method",
    "effect", "between", "significant", "participants", "table", "figure",
    "than", "more", "also", "these", "other", "our", "such", "how",
    "each", "after", "both", "most", "only", "over", "may", "into",
}

LIGATURE_CHARS = set("\ufb00\ufb01\ufb02\ufb03\ufb04\ufb05\ufb06")


def compute_quality_score(text: str) -> dict:
    """Compute extraction quality metrics.

    Garble detection (as of 1.3.1) requires BOTH a low common-word ratio AND
    at least one independent corruption signal:
      - replacement chars (U+FFFD)
      - suspiciously high non-ASCII ratio (> 20%)
      - many remaining ligatures (>= 20, implies unprocessed text)
      - very short text (< 500 chars, cannot confidently evaluate)

    This avoids flagging legitimate non-prose documents (reviewer
    acknowledgment lists, name indices, reference-only files) as garbled.
    Real extraction failures still trip at least one corruption signal.
    """
    words = text.lower().split()[:2000]
    common_count = sum(1 for w in words if w in COMMON_WORDS)
    common_ratio = common_count / len(words) if words else 0.0

    ligatures = sum(1 for c in text if c in LIGATURE_CHARS)
    garbled_chars = text.count("\ufffd")
    non_ascii = sum(1 for c in text if ord(c) > 127)
    non_ascii_ratio = non_ascii / len(text) if text else 0.0

    # A legitimate non-prose document (reviewer ack, name index) has a low
    # common_word_ratio but zero corruption signals. Real garbled text almost
    # always has at least one.
    has_corruption_signal = (
        garbled_chars > 0
        or non_ascii_ratio > 0.20
        or ligatures >= 20
    )
    is_short = len(text) < 500

    # Composite score
    score = 100
    if common_ratio < 0.02 and (has_corruption_signal or is_short):
        score -= 50  # garbled text with independent evidence
    elif common_ratio < 0.02:
        # Low common-word ratio but no corruption signal — likely non-prose
        # content (name lists, reference dumps). Small penalty, not a flag.
        score -= 10
    elif common_ratio < 0.05:
        score -= 20  # possibly garbled
    score -= min(20, ligatures // 10)
    score -= min(10, garbled_chars)
    score = max(0, score)

    if score >= 80:
        confidence = "high"
    elif score >= 50:
        confidence = "medium"
    else:
        confidence = "low"

    # `garbled` remains True only when the low ratio is corroborated by
    # independent evidence. Downstream consumers can still check
    # `common_word_ratio` directly if they want the looser signal.
    garbled_flag = common_ratio < 0.02 and (has_corruption_signal or is_short)

    return {
        "score": score,
        "common_word_ratio": round(common_ratio, 4),
        "garbled": garbled_flag,
        "confidence": confidence,
        "details": {
            "ligatures_remaining": ligatures,
            "garbled_chars": garbled_chars,
            "non_ascii_ratio": round(non_ascii_ratio, 4),
            "has_corruption_signal": has_corruption_signal,
        },
    }
