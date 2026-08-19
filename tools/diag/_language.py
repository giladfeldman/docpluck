"""Language detection for the diagnostic scans. ENGLISH-ONLY is a hard scope.

Moved here 2026-08-14 from `english_only_locale_scan.py`, whose own subject —
the document-level numeric-locale question — was deleted in v2.4.129 when the
owner set the scope to **English papers in US numeric convention, European
numbers passed through unconverted**. That scan's headline finding
("396 English articles -> 0 European-locale") is now known to have measured the
INSTRUMENT rather than the corpus, so the tool retired with the feature; the
language detector it carried is still needed by every other scan and lives here.

ONE CONCEPT, ONE TABLE: every diagnostic imports this. A scan carrying its own
copy of the language filter would drift from the others and report numbers about
a different population than it claims.
"""

from __future__ import annotations

import re

STOPWORDS = {
    "english": r"\b(the|and|of|in|that|with|were|was|for|this|are|from|between)\b",
    "portuguese": r"\b(dos|das|para|com|não|uma|foi|foram|entre|sobre|pelo|pela)\b",
    "spanish": r"\b(los|las|para|con|una|fueron|entre|sobre|por|del|que|más)\b",
    "turkish": r"\b(ve|bir|için|olarak|ile|olan|göre|arasında|değil|daha)\b",
    "french": r"\b(les|des|une|pour|avec|dans|sont|été|entre|cette|plus)\b",
    "german": r"\b(und|der|die|das|für|mit|nicht|eine|wurden|zwischen|über)\b",
    # Slavic / Nordic / Dutch / Italian added 2026-08-13. A corpus pass showed
    # this hole sat EXACTLY where European decimals live: the only
    # English-language journals found using comma decimals are Polish and
    # Croatian. Swedish text was detected as ENGLISH (its function words share
    # little with the Romance/Germanic sets above, so English won by default),
    # and Polish/Croatian fell to "unknown" and were silently dropped from the
    # denominator. A language detector blind to the languages the question is
    # about is the same defect class as a corpus that cannot see its own gap.
    "polish": r"\b(oraz|jest|przez|ktore|badania|wyniki|zostalo|dla|sie)\b",
    "croatian": r"\b(su|kako|te|njihov|istrazivanje|rezultate|koje|provedeno)\b",
    "czech": r"\b(jsou|byly|mezi|ktere|nebo|tato|vysledky|studie)\b",
    "swedish": r"\b(och|att|som|inte|har|den|det|mellan|studien|genomfordes)\b",
    "norwegian": r"\b(og|av|som|ikke|har|den|det|mellom|studien)\b",
    "danish": r"\b(og|af|som|ikke|har|den|det|mellem|undersogelsen)\b",
    "dutch": r"\b(van|het|een|voor|niet|werden|tussen|deze|onderzoek)\b",
    "italian": r"\b(che|per|con|del|della|sono|stati|tra|questo|risultati)\b",
}
_COMPILED = {k: re.compile(v, re.IGNORECASE) for k, v in STOPWORDS.items()}


def detect_language(text: str) -> tuple[str, dict[str, int]]:
    """Return (language, per-language hit counts).

    A paper counts as English only when English function words are the clear
    plurality AND outnumber the runner-up by 3x. A bilingual SciELO article —
    English abstract over a Portuguese body — fails that test and is excluded,
    which is exactly what we want: its two halves follow different numeric
    conventions, so it can teach us nothing reliable about either.
    """
    counts = {k: len(rx.findall(text)) for k, rx in _COMPILED.items()}
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    top, top_n = ranked[0]
    runner_n = ranked[1][1] if len(ranked) > 1 else 0
    if top_n == 0:
        return "unknown", counts
    if top != "english":
        return top, counts
    if runner_n and top_n < 3 * runner_n:
        return "mixed/bilingual", counts
    return "english", counts
