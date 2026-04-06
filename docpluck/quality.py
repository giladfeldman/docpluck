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

LIGATURE_CHARS = set("\ufb00\ufb01\ufb02\ufb03\ufb04")


def compute_quality_score(text: str) -> dict:
    """Compute extraction quality metrics."""
    words = text.lower().split()[:2000]
    common_count = sum(1 for w in words if w in COMMON_WORDS)
    common_ratio = common_count / len(words) if words else 0.0

    ligatures = sum(1 for c in text if c in LIGATURE_CHARS)
    garbled = text.count("\ufffd")
    non_ascii = sum(1 for c in text if ord(c) > 127)
    non_ascii_ratio = non_ascii / len(text) if text else 0.0

    # Composite score
    score = 100
    if common_ratio < 0.02:
        score -= 50  # garbled text
    elif common_ratio < 0.05:
        score -= 20  # possibly garbled
    score -= min(20, ligatures // 10)
    score -= min(10, garbled)
    score = max(0, score)

    if score >= 80:
        confidence = "high"
    elif score >= 50:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "score": score,
        "common_word_ratio": round(common_ratio, 4),
        "garbled": common_ratio < 0.02,
        "confidence": confidence,
        "details": {
            "ligatures_remaining": ligatures,
            "garbled_chars": garbled,
            "non_ascii_ratio": round(non_ascii_ratio, 4),
        },
    }
