"""
Quality Scoring
================
From Scimeto's _check_text_quality() + MetaESCI's artifact detection.
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

# TYPOGRAPHIC DAMAGE THE WORD COUNT CANNOT SEE. A paper can read as
# fluent English while its statistics are broken: the common-word ratio does not
# move when only operators and symbols are lost. Two signals, both read off the
# text without interpreting any value:
#
# * a C0 control character left in the text: a glyph the font gave no Unicode.
#   normalize strips the furniture controls and keeps these (it counts them as
#   `residual_control_chars`): 404 in the math of the manifest's ieee-access-9,
#   `f emales\x01males` in nat-comms-3.
# * a test statistic with its degrees of freedom and a number but NO operator
#   between them, on one line: `F(1, 350) 5 27.7`, where the font draws `=` and
#   its character map says `5` (10.5465/amj.2016.1196: 3 of its 3 statistics).
#   Pure text: the W0s repair needs the layout and cannot run here.
_C0_RE = re.compile(r"[\x00-\x08\x0b\x0e-\x1f]")
_STAT_HEAD = r"(?<![A-Za-z])(?:t|F|r|z|\u03c72|\u03c7\u00b2|chi2)[ \t]*\([ \t]*\d[\d., \t]*\)[ \t]*"
_STAT_NO_OPERATOR_RE = re.compile(_STAT_HEAD + r"(?:[\x00-\x08\x0b\x0e-\x1f][ \t]*)?(?=[-\u2212]?\.?\d)")
_STAT_WITH_OPERATOR_RE = re.compile(_STAT_HEAD + r"[=<>\u2264\u2265]")


def compute_quality_score(text: str) -> dict:
    """Compute extraction quality metrics.

    Garble detection (as of 1.3.1) requires BOTH a low common-word ratio AND
    at least one independent corruption signal:
      - replacement chars (U+FFFD)
      - suspiciously high non-ASCII ratio (> 20%)
      - many remaining ligatures (>= 20, implies unprocessed text)
      - very short text (< 500 chars, cannot confidently evaluate)
      - (2.4.154) a C0 control character left in the text (a glyph with no
        Unicode)

    It also reports, in ``details``, statistics printed with no operator
    (``F(1, 350) 5 27.7``) and sets ``statistics_damaged`` when they are not a
    small minority (>= 1 in 4 of the statistics); that costs 30 points, since a
    paper can read as fluent English while its statistics are unusable.

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
    control_chars = len(_C0_RE.findall(text))
    stats_no_op = len(_STAT_NO_OPERATOR_RE.findall(text))
    stats_with_op = len(_STAT_WITH_OPERATOR_RE.findall(text))
    has_corruption_signal = (
        garbled_chars > 0
        or non_ascii_ratio > 0.20
        or ligatures >= 20
        or control_chars > 0
    )
    # Damaged statistics: operator-less statistics that are not a small minority
    # of the paper's statistics -- a footnote marker after a df can mimic one
    # (1 of 64 in the manifest's korbmacher_2022_kruger render).
    statistics_damaged = stats_no_op >= 1 and stats_no_op * 4 >= stats_no_op + stats_with_op
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
    score -= min(10, control_chars // 10)
    if statistics_damaged:
        score -= 30
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
            "residual_control_chars": control_chars,
            "statistics_without_operator": stats_no_op,
            "statistics_with_operator": stats_with_op,
            "statistics_damaged": statistics_damaged,
        },
    }
