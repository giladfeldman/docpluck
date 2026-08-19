"""
Normalization Pipeline
=======================
Consolidated from ESCIcheck, MetaESCI, Scimeto/CitationGuard, MetaMisCitations.
Each step is documented, versioned, and independently toggleable.

Levels:
  none     - Raw extracted text, no modifications
  standard - General-purpose cleanup safe for any use
  academic - Standard + academic-specific statistical expression repair
"""

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from enum import Enum

from .telemetry import fallback_scope, record_fallback


class NormalizationLevel(str, Enum):
    none = "none"
    standard = "standard"
    academic = "academic"


NORMALIZATION_VERSION = "1.9.56"  # v1.9.56 (v2.4.134): THE EVIDENCE EACH REPAIR RESTS ON IS NOW DECLARED, AND ONE RULE STOPPED FABRICATING A SECOND MINUS SIGN. (1) `_ALREADY_SIGNED` is a ONE-CHARACTER lookbehind, so it refused `-0.38` and ACCEPTED `- 0.38`: on a DETACHED sign W0g read a bare-positive estimate, proved it negative from the CI, and emitted `d = - -0.38` - a double-signed effect size no paper printed. The comment above `_SIGNED_DASHES` records that `-2.68 -> --.68` already happened once and that "the fix then covered the one dash form in front of us"; it covered the ATTACHED form. Caught by the idempotency corpus gate, not by reading the rule. (2) W0q: `recover_dropped_minus_ci_upper_in_text` existed ONLY in the table channel, so a CI written in a results SENTENCE never met it - confirmed against the rasterized page of 10.1016/j.jesp.2021.104154 p13, which prints `d = -0.38, 95% CI [-0.58, -0.18]` while pdftotext detaches every minus. 3 brackets in 1 of 26 baseline papers, and the containment arithmetic repaired 0 of them (it had grabbed `S.D = 1.43` as the "estimate"). (3) That rule now splits TYPOGRAPHIC from INFERENTIAL: a DETACHED DASH is a glyph the renderer emitted and the comma proves it is a sign rather than a range separator, so group 5 - captured since the rule was written and never read (register O5) - finally decides. The containment arm is KEPT because chan_feldman_2025_cogemo Table 9 row 2bii has no dash and only the arithmetic recovers its published -0.33, but it is now DECLARED via `ci_upper_minus_inferred_from_containment`. (4) O10: `_recover_estimate_column_via_ci_column` treated any negative bound as proof of the 2-for-minus corruption - including bounds `recover_corrupted_minus_signs` had manufactured one line earlier. It now fires only on a bracket THIS pass actually repaired. (5) O8: W0j signature B is labelled INFERENTIAL in the code and records every firing; W0p records its positional pairing. (6) `NormalizationReport.fallbacks` - every `record_fallback` inside normalization was outside `extract_pdf_structured`'s window and therefore write-only, INCLUDING the ambiguous-pairing refusals added in v2.4.133 to make W0h/W0m observable. # v1.9.55 (v2.4.133): THE LAYOUT-GATED REPAIRS STOP ASSIGNING THEIR EVIDENCE POSITIONALLY. W0h/W0m proved "N glyphs of shape X are corrupt" in pdfplumber's stream and then rewrote the first N matching tokens in pdftotext's stream, document-wide with no page key - so a glyph proven on page 7 licensed flipping a token on page 2. REPRODUCED, not reasoned about: with a decoy `q = .428` prepended to the W0h source paper (ar_apa_j_jesp_2009_12_011), the old code flipped the DECOY and left the genuine coefficient corrupt - one number fabricated, one missed. Each evidence site now carries its own page and its own layout line text, and pairing REFUSES (recording `w0h_ambiguous_pairing_refused`) when the context cannot separate candidates, because pass-through is reversible for the consumer and a rewrite is not. Page-INDEX scoping was measured and rejected: by the time W0h runs the text holds 7 form feeds for a 12-page document, so aligning text page k to layout page k is an off-by-k that produces a confidently WRONG pairing rather than an empty one. W0m was the worse of the two - it counted beta glyphs and flipped the first N `b = <anything>` WITHOUT requiring the coefficient to match, so a beta proven on one page could relabel a genuine unstandardized `b` (a different statistic) elsewhere; the coefficient is now part of the identity. See tests/test_w0h_pairing_is_identity_based.py and docs/OVERHAUL_REGISTER.md G5. # v1.9.54 (v2.4.130): THE SEPARATION OF DUTIES, EXECUTED. Three rules that repaired the PAPER rather than canonicalising NOTATION are DELETED, together with the guard that existed only to serve them. A2 (dropped-decimal repair, `p = 38.` -> `p = .38.`) had NO CITED PAPER anywhere in its code; asked for one, BOTH of its firing sites across 297 English papers turned out to be the paper's own error, rasterized: 10.1177/0146167210380928 p13 prints `B = -0.28, SE = 0.31, p = 38.` and 10.1016/j.jesp.2016.11.001 p7 prints `t(186) = 3.90, p = 001`, each with correctly-dotted numbers on the same line. W0n (`p < 05` -> `p < .05`) is deleted in BOTH channels because its premise is false: the SAME shape has OPPOSITE OWNERS in two real English papers - 10.1016/j.jesp.2009.12.011 p3 PRINTS `p < 05` (the author dropped it; advance 2.00pt vs 3.90pt at a dotted site on the same page, no rect/curve/line in the gap) while 10.1177/0956797613482946 p6 PRINTS `p < .05` and our OCR text layer lost it. A calibrated layout-advance gate (0.51 vs 0.99) was built and REFUTED: Dong p6 is a SCAN whose char boxes come from an OCR engine, so the gate manufactures its own evidence for the exact case it exists to catch. Under irreducible ambiguity the default is PASS-THROUGH, because pass-through is reversible for the consumer and a repair is not. A3a (thousands strip) is deleted because ITS PURPOSE EVAPORATED: its own comment said it strips "so A3 sees the already-clean integer and leaves it alone", and A3 was deleted in v2.4.129. It also produced 1000x errors - 10.1177/0956797620935584 Table S2 p24 prints a Satterthwaite df of `185,178` (fractional by construction, i.e. 185.178) and we delivered `185178`; the collision is STRUCTURAL, since its discriminator is satisfied by construction for any comma-locale number with a 3-digit integer part and 3-decimal precision. It made the library answer one input THREE ways (standard preserved, academic+preserve_math_glyphs counted-but-preserved, academic stripped), and ITS TELEMETRY SAID THE OPPOSITE OF WHAT IT DID: step `A3a_thousands_separator_protect`, metric key `thousands_separators_preserved`, operation `.replace(",", "")` - a false all-clear, which is worse than silence because silence invites a check. ALSO IN THIS RELEASE, the biggest finding of the audit and one that indicts its own framing: THE RENDER CHANNEL DELETES PUBLISHED STATISTICS. The numeric rules were audited exhaustively; the same question was never asked of render.py, which is the channel that reaches the user. Measured on the baseline corpus, 10.1017/s1930297500009189 lost an ENTIRE published-results sentence (two correlations, a Hotelling's t, three p-values, two confidence intervals) to `_suppress_inline_duplicate_table_captions`, and 10.1001/jamanetworkopen.2023.48333 lost a hazard ratio `1.31 (1.20-1.44)` to `_strip_phantom_camelot_tables` - with NO count, NO key in changes_made and NO log line, because render_pdf_to_markdown() chained 54 `md = fn(md)` calls and returned a bare str. Fixed: `_carries_statistical_content` guards every deleting step (delete FURNITURE, never DATA, all-or-nothing per run), and an opt-in `RenderReport` gives the channel telemetry for the first time. See docs/SCOPE.md, LESSONS.md L-032, and tests/test_render_never_deletes_published_statistics.py.


# ── Mathematical Alphanumeric Symbols de-styling (shared, v2.4.34) ──────────
# The SMP block U+1D400-U+1D7FF holds styled (italic / bold / bold-italic /
# script / fraktur / double-struck / sans-serif / sans-bold / monospace)
# Latin letters, Greek letters and digits. Every codepoint in it is a
# compatibility character whose NFKC decomposition is its plain base form:
# 𝐴->A, 𝜂->η, 𝛽->β, 𝟎->0. Greek MUST stay Greek — mapping it to ASCII Latin
# (the pre-v2.4.34 bug: 𝜂->"n", 𝛽->"b") silently corrupts statistical
# symbols (η² rendered as "n2"). CLAUDE.md hard rule 4: only U+2212->hyphen
# is a sanctioned Unicode->ASCII conversion. Shared by normalize_text's S0
# step (text/body channel) and tables/cell_cleaning (layout channel) so math
# styling is stripped consistently across every output view.
_MATH_ALNUM_RE = re.compile(r"[\U0001D400-\U0001D7FF]")


def destyle_math_alphanumeric(text: str) -> str:
    """Strip Mathematical-Alphanumeric styling to the plain base letter/digit.

    NFKC-normalises each U+1D400-U+1D7FF codepoint (Greek stays Greek, Latin
    stays Latin, digits stay digits). No-op when the text holds no such char.
    """
    if not text or not _MATH_ALNUM_RE.search(text):
        return text
    return _MATH_ALNUM_RE.sub(
        lambda m: unicodedata.normalize("NFKC", m.group()), text
    )


# ── Request 9 (Scimeto, 2026-04-27): Reference-list normalization ──────────
# Three artifact classes that survive S0–A6 and silently corrupt bibliographies:
#   W0 — Publisher-overlay watermarks glued mid-line (Royal Society "Downloaded
#        from..." overlay, Wiley/Elsevier "Provided by..." stamps, etc.)
#   R2 — Page-number digits that pdftotext glued between two body words inside
#        a reference (e.g. "psychological 41 science." in ref 17).
#   R3 — Continuation lines from a wrapped reference that didn't get rejoined,
#        so the journal/volume tail looks like an orphan paragraph.
#   A7 — DOIs broken across a line ("doi:10.\n1007/s10683-...").
# Pretest (51-PDF corpus): W0 fires on RSOS-family PDFs; R2 catches the silent
# corruption case; R3 fixes 1–142 continuations per PDF; A7 fixes long DOIs.

_WATERMARK_PATTERNS = [
    # 2026-05-09: relaxed to allow optional intermediate phrase between the
    # URL and the "on <date>" tail.  Collabra Psychology renders the watermark
    # as "Downloaded from <url> by guest on <date>"; the previous pattern
    # required `<url> on <date>` with nothing in between and missed it on
    # every Collabra paper.
    re.compile(
        # v2.3.0: extended the "by <phrase>" tail from `\w+` (one word, fits
        # "by guest") to any non-newline-bounded phrase, so it catches
        # institutional download stamps like
        #   "Downloaded from <url> by University of Innsbruck (Universitat
        #    Innsbruck) user on 16 March 2026"
        # found on every page of ar_royal_society_rsos_140072 (verified by
        # ``scripts/verify_corpus.py``). The trailing "on <day> <month>
        # <year>" anchor prevents runaway captures into body prose.
        r"Downloaded\s+from\s+https?://[^\s]+(?:\s+by\s+[^\n]+?)?"
        r"\s+on\s+\d{1,2}\s+\w+\s+\d{4}",
        re.IGNORECASE,
    ),
    # v2.4.74 (jama-open-1 RUNNING_HEADER_LEAK fix, 2026-05-25): JAMA-style
    # watermark variant — domain without scheme, MM/DD/YYYY date format.
    #   "Downloaded from jamanetwork.com by Medizinisch-Biologische
    #    Fachbibliothek user on 03/18/2026"
    # The previous pattern required `https?://` prefix and `DD Month YYYY`
    # date format, missing every JAMA Open paper. Structural signature
    # (per CLAUDE.md hard rule 16): "Downloaded from <bare-domain>...
    # user on <numeric date>". The trailing date format is the disambiguator
    # (no body prose ends with `\d{1,2}/\d{1,2}/\d{4}`).
    re.compile(
        r"Downloaded\s+from\s+[\w.-]+\.\w{2,}(?:\s+by\s+[^\n]+?)?"
        r"\s+on\s+\d{1,2}/\d{1,2}/\d{4}",
        re.IGNORECASE,
    ),
    re.compile(r"Provided\s+by\s+[\w\s.,&-]+\s+on\s+\d{4}-\d{2}-\d{2}", re.IGNORECASE),
    re.compile(r"This\s+article\s+is\s+protected\s+by\s+copyright\.[^\n]*", re.IGNORECASE),
    # RSOS running-footer artifact glued onto body text:
    # "41royalsocietypublishing.org/journal/rsos R. Soc. Open Sci. 12: 250979"
    # The leading page number is BOUNDED (ReDoS fix, 2026-08-04). As an unbounded
    # `\d+` it started a match attempt at every digit of a long numeric run and then
    # failed — quadratic. It cost 3.165s of normalize_text's 3.7s on a 20k-digit input
    # and was the reason normalize_text still scaled ~4-5x per doubling AFTER the
    # _CI_UPPER_DROPPED_RE fix. Bounded, it is ~1370x faster (4.53s -> 0.0033s) and
    # matches both real footer forms identically ("41royalsociety…" glued, and
    # "12 royalsociety…" spaced) — a page number is never more than 6 digits.
    # Guarded by tests/test_ci_upper_dropped_redos.py.
    re.compile(r"\d{1,6}\s*royalsocietypublishing\.org/journal/\w+\s+R\.\s*Soc\.\s*Open\s*Sci\.\s*\d+:\s*\d+"),
    # Issue H — Publisher copyright stamp on its own line. Format:
    #   "© 2009 Elsevier Inc. All rights reserved."
    #   "Ó 2009 Elsevier Inc. All rights reserved."  (pdftotext sometimes flattens © → Ó)
    #   "© 2020 Springer Nature Limited. All rights reserved."
    #   "© 2021 The Author(s). Published by Wiley..."  (do NOT match — no "rights reserved")
    # We anchor to start-of-line and require ALL of: © or Ó, a 4-digit year,
    # then "All rights reserved" (case-insensitive). The intervening publisher
    # name is bounded to a single line. Trailing period optional. Also strip
    # the trailing newline so we don't leave a blank line behind.
    re.compile(
        r"(?im)^\s*[©Ó]\s*\d{4}[^\n]*?All\s+rights\s+reserved\.?\s*\n?",
    ),
    # Issue K (cycle 10, D4) — Elsevier page-1 ISSN / front-matter / copyright
    # line. pdftotext extracts it at the page-1 footer and downstream
    # paragraph-rejoin splices it into the Introduction body. Formats:
    #   "0022-1031/$ - see front matter Ó 2009 Elsevier Inc. All rights reserved."
    #   "0022-1031/© 2021 Elsevier Inc. All rights reserved."
    # The Issue-H pattern above only fires when the line STARTS with ©/Ó;
    # these lines start with the journal ISSN. The line-leading ISSN
    # `NNNN-NNNX/` is the anchor — academic body prose and references never
    # begin with it — and we additionally require an Elsevier/front-matter/
    # rights-reserved keyword so a coincidental digit run can never match.
    re.compile(
        r"(?im)^\s*\d{4}-\d{3}[\dX]/[^\n]*?"
        r"(?:see\s+front\s+matter|Elsevier|All\s+rights\s+reserved)[^\n]*\n?",
    ),
    # Issue L (cycle 10, D4) — Elsevier single-author corresponding-author
    # e-mail footer line, e.g. "E-mail address: muraven@albany.edu". This is
    # page-1 footer metadata that pdftotext splices mid-Introduction. Only
    # the SINGULAR "E-mail address:" form is matched — it is a single short
    # line (one corresponding author). The plural "E-mail addresses:" form is
    # a long multi-author list that pdftotext wraps across several lines, so
    # it is intentionally left alone (a one-line strip would shred it).
    re.compile(
        r"(?im)^\s*E-mail\s+address:\s*\S*@\S+[^\n]*\n?",
    ),
    # Issue I — Two-column running header that pdftotext extracts at page
    # boundaries.  Format:
    #   "M. Muraven / Journal of Experimental Social Psychology 46 (2010) 465-468"
    #   "J. Smith / Cognitive Psychology 12 (2020) 100-120"
    # Anchored to its own line; recognized by the trailing "<vol> (<year>) <pages>"
    # signature.  We require at least one initial-then-surname before the slash
    # and one Capitalized word after.  The page range may use a hyphen or en-dash.
    re.compile(
        r"(?m)^\s*[A-Z]\.\s*(?:[A-Z]\.\s*)?[A-Z][\w'\-]+"
        r"(?:\s*(?:and|&|,)\s*[A-Z]\.\s*(?:[A-Z]\.\s*)?[A-Z][\w'\-]+)*"
        r"\s*/\s*"
        r"[A-Z][^/\n]{2,80}?"
        r"\s+\d+\s*\(\d{4}\)\s+\d+\s*[-–]\s*\d+\s*\n?",
    ),
    # 2026-05-09: Author-equal-contribution footnote line.
    # Collabra/IRSP and other open-access journals print a footnote at the
    # bottom of page 1 of the form:
    #   "a Surname, Surname, ... are equal-contribution first authors b email@..."
    # pdftotext extracts this in reading order, often interleaved between
    # the abstract and the introduction body.  The pattern requires:
    #   - leading lowercase letter + space (footnote marker "a ")
    #   - a list of capitalized surnames (3+ tokens, comma-separated)
    #   - the literal phrase "equal" + "contribution" OR "equal contribution"
    #     OR "joint first authors" anywhere in the line
    # The "equal contribution" phrase is the discriminator that distinguishes
    # this from genuine prose body lines that happen to start with a lowercase
    # letter (rare but possible).
    re.compile(
        r"(?m)^\s*[a-z]\s+"
        r"(?:[A-Z][\w-]+,\s+(?:and\s+)?){2,15}"
        r"[A-Z][\w-]+"
        r"\s+(?:are\s+)?(?:equal[ -]?contribution|joint\s+first\s+author)"
        r"[^\n]*\n?",
    ),
    # Issue J — Creative Commons / open-access license footer sentences that
    # publishers append to abstract paragraphs.  These are NOT abstract content;
    # they're licensing metadata.  Examples:
    #   "Copyright: © 2022. The authors license this article under the terms of
    #    the Creative Commons Attribution 3.0 License."
    #   "The authors license this article under the terms of the Creative
    #    Commons Attribution 4.0 International License."
    # The match starts at the optional "Copyright:..." prefix or at "The authors
    # license...", and runs to the first "License" closer.  We use lazy
    # `[^\n]*?` because the license version may contain a period ("4.0", "3.0")
    # that a `[^\n.]` class would reject.
    re.compile(
        r"(?:Copyright[: ]\s*[©Ó]?\s*\d{4}\.?\s+)?"
        r"The authors? licen[cs]e this article under the terms of the\s+"
        r"Creative\s+Commons[^\n]*?License\.?",
    ),
    # v2.4.37 (D4): Cambridge University Press per-page running footer.
    # pdftotext emits "https://doi.org/10.1017/<id> Published online by
    # Cambridge University Press" once per page; downstream paragraph-rejoin
    # then splices it MID-SENTENCE into body prose ("...individuals usually
    # fail to <footer> notice the absence..."). Not line-anchored — matches
    # whether the footer stands alone or is glued inline (pdftotext version
    # skew, memory feedback_pdftotext_version_skew). "Published online by
    # Cambridge University Press" is unambiguous platform boilerplate (book
    # citations read "Cambridge: Cambridge University Press"). Generic across
    # every Cambridge UP journal.
    re.compile(
        r"(?:https?://doi\.org/\S+\s+)?"
        r"Published\s+online\s+by\s+Cambridge\s+University\s+Press",
        re.IGNORECASE,
    ),
    # v2.4.37 (D4): Cambridge / JDM open-access licence boilerplate sentence.
    # The copyright block "© The Author(s), <year>. Published by Cambridge
    # University Press on behalf of ... European Association for Decision
    # Making. This is an Open Access article, distributed under the terms of
    # the Creative Commons Attribution licence (...), which permits ...
    # properly cited." gets serialized into the Introduction body. The "© ..."
    # head is caught by the page-footer strip; this removes the trailing
    # open-access sentence (with any dangling "...Association for Decision
    # Making." lead-in). [\s\S] spans the pdftotext line wrap inside it.
    re.compile(
        # Optional bare "Association for Decision Making." lead-in (the tail
        # of the publisher name, left behind when the "© ... European" head
        # is stripped by the page-footer pass). Literal only — must NOT reach
        # backward across legitimate body prose.
        r"(?:Association for Decision Making\.\s*)?"
        r"This is an Open Access article,[\s\S]{0,60}?"
        r"distributed under the terms of the\s+Creative\s+Commons"
        r"[\s\S]{0,240}?properly cited\.",
        re.IGNORECASE,
    ),
]

_REFS_HEADER = re.compile(
    r"^\s*(References?|Bibliography|Works\s+Cited|Literature\s+Cited)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_REFS_END = re.compile(
    r"\n\s*(Acknowledg|Funding|Author\s+contribution|Supplementary|Appendix|"
    r"Conflict\s+of\s+interest|Competing\s+interest|Notes|Data\s+availability|"
    r"Ethics\s+statement|Author's?\s+(note|disclosure))\b",
    re.IGNORECASE,
)
_REF_START_VANCOUVER = re.compile(r"^\d{1,3}\.\s+[A-Z]")
_REF_START_IEEE = re.compile(r"^\[\d+\]\s+[A-Z]")
# Harvard / Cambridge name-year reference entry start (D1, citationguard-iterate
# 2026-06-12): "Surname A and Surname B (2020) …", "Surname A et al. (2020) …",
# "Surname A, Surname B and Surname C (2019) …". Distinct from APA, which puts a
# comma immediately after surname-1 ("Surname, A.") — the Harvard form has NO
# comma between surname and initials, so _REF_START_APA never matched it and R3
# collapsed the whole bibliography onto one line (British Journal of Political
# Science bjps_1: 109 entries joined into a single paragraph). The structural
# signature is an author block — Surname + 1–3 bare initials, optionally chained
# with " and "/"&"/comma — terminated by a parenthesised 4-digit year. The
# parenthesised year is the strong anchor that keeps mid-entry wrap lines
# ("American Journal of\nPolitical Science 64, 904-20.") from matching.
# Initials: 1-4 groups, each 1-3 capitals, optionally hyphenated ("H-G", "Z-C")
# and optionally period-terminated; groups may be spaced ("R J") or glued ("DH").
_HARVARD_INITIALS = r"(?:\s+[A-Z]{1,3}(?:-[A-Z]{1,3})?\.?){1,4}"
# Surname: Title-case word (Latin-Extended so "Häusermann", "Öhman" qualify),
# optionally hyphenated ("Huntington-Klein") and optionally a second word for
# compound surnames ("Santos Silva", "El Soufi"), with leading lowercase
# particles ("van der", "de la") permitted.
# Letter ranges span ASCII + Latin-1 Supplement + Latin Extended-A/B (U+0100-
# U+024F) so Eastern-European / Turkish surnames ("Häusermann", "Tuğal", "Öhman")
# qualify. First letter is an uppercase-ish Latin letter; the rest may be any
# Latin letter or apostrophe.
_HARVARD_NAME_WORD = (
    r"[A-ZÀ-ÞĀ-ɏ][A-Za-zÀ-ÿĀ-ɏ'’]+(?:-[A-ZÀ-ÞĀ-ɏ][A-Za-zÀ-ÿĀ-ɏ'’]+)?"
)
_HARVARD_SURNAME = (
    # Leading particles, capitalised or not ("van der", "de la", "Van der Brug",
    # "De Vries") — the first particle is often title-cased at an entry start.
    r"(?:(?:[Vv]an|[Vv]on|[Dd]e|[Dd]er|[Dd]en|[Dd]i|[Dd]el|[Dd]ella|[Dd]u"
    r"|[Ll]a|[Ll]e|[Ee]l|[Dd]os|[Dd]a)\s+){0,2}"
    + _HARVARD_NAME_WORD
    + r"(?:\s+" + _HARVARD_NAME_WORD + r")?"
)
_HARVARD_AUTHOR = _HARVARD_SURNAME + _HARVARD_INITIALS
_REF_START_HARVARD = re.compile(
    r"^" + _HARVARD_AUTHOR +
    r"(?:"
    r",?\s+et\s+al\.?"                          #   "et al." / "Surname K, et al."
    r"|,?\s+(?:and|&)\s+" + _HARVARD_AUTHOR +   # " and Surname I"
    r"|,\s+" + _HARVARD_AUTHOR +                # ", Surname I"
    r")*"
    r"(?:\s+\((?:eds?|editors?)\.?\))?"         # optional "(eds)" / "(ed.)" marker
    r"\s+\((?:1[89]|20)\d{2}[a-z]?\)",         # (Year) optional letter suffix
    re.UNICODE,
)
# APA reference entry start: "Surname, A.", "Surname, A. B.". Reuses the shared
# surname block so accented ("Yücel, M."), particle ("de Kovel, C."), and
# compound ("Karlsson Linnér, R.") surnames are recognised — the previous
# ASCII-only `[A-Z][a-z]+` form silently merged those entries into the preceding
# reference (surfaced on nat_comms_5 / nathumbeh_2 during the D1 broad-read;
# same root-cause class as D1). The comma-then-initial is the APA discriminator
# (Harvard has no comma after the surname).
_REF_START_APA = re.compile(r"^" + _HARVARD_SURNAME + r",\s+[A-Z]\.", re.UNICODE)


def _find_references_spans(text: str) -> list[tuple[int, int]]:
    """Return all (start, end) spans for References / Bibliography sections.

    A header qualifies only if followed within 5k chars by ≥3 ref-like
    patterns — guards against false positives from in-text "References"
    mentions or section-heading repetitions. Returns spans in document
    order. Multiple bibliographies (main + supplementary) all qualify and
    are returned separately, each ending at the next non-bibliography
    section heading.
    """
    spans: list[tuple[int, int]] = []
    for m in _REFS_HEADER.finditer(text):
        start = m.end()
        window = text[start:start + 5000]
        ref_starts = (
            len(re.findall(r"\b\d{1,3}\.\s+[A-Z]", window))
            + len(re.findall(r"\n\[\d+\]\s+[A-Z]", window))
            + len(re.findall(r"\n" + _HARVARD_SURNAME + r",\s+[A-Z]\.", window))
            # Harvard name-year entries (D1): "\nSurname A(?: and …| et al.)? (YYYY)".
            # Without this a pure-Harvard bibliography (no comma after surname,
            # no numbered/IEEE entries) would score 0 ref-starts and the span
            # would go undetected, so R3 would never run to keep entries split.
            + len(re.findall(
                r"\n" + _HARVARD_AUTHOR +
                r"(?:\s+et\s+al\.?|,?\s+(?:and|&)\s+" + _HARVARD_AUTHOR +
                r")*\s+\((?:1[89]|20)\d{2}[a-z]?\)",
                window,
            ))
        )
        if ref_starts >= 3:
            end_m = _REFS_END.search(text, start)
            end = end_m.start() if end_m else len(text)
            # Skip if this span overlaps the previous span (next-header
            # qualifying within an already-claimed bibliography region).
            if spans and start < spans[-1][1]:
                continue
            spans.append((start, end))
    return spans


def _body_size(layout) -> float:
    """Return the most common font size by character count in the body zone.

    Excludes spans in the top 5% and bottom 15% of each page to avoid
    headers and footnotes skewing the result.
    """
    from collections import Counter
    counter: Counter[float] = Counter()
    for page in layout.pages:
        h = page.height
        y_lo = h * 0.15   # exclude bottom 15% (footnote zone)
        y_hi = h * 0.95   # exclude top 5% (running header zone)
        for span in page.spans:
            if span.y0 < y_lo or span.y0 > y_hi:
                continue
            counter[round(span.font_size, 1)] += len(span.text)
    if not counter:
        return 11.0
    return max(counter.items(), key=lambda kv: kv[1])[0]


def _body_y_band(page, body_size: float) -> tuple[float, float]:
    """Return (y_min, y_max) of the body-text band on this page."""
    body_spans = [s for s in page.spans if abs(s.font_size - body_size) <= 1.0]
    if not body_spans:
        return 0.0, page.height
    y_min = min(s.y0 for s in body_spans)
    y_max = max(s.y1 for s in body_spans)
    return y_min, y_max


def _detect_repeating_lines(layout, *, position: str) -> set[str]:
    """Return text lines that appear at the top (or bottom) of >=50% of pages."""
    if len(layout.pages) < 2:
        return set()
    counts: dict[str, int] = {}
    for page in layout.pages:
        if not page.spans:
            continue
        y_sorted = sorted(page.spans, key=lambda s: s.y0)
        if position == "top":
            candidates = [y_sorted[-1].text.strip()] if y_sorted else []
        else:
            candidates = [y_sorted[0].text.strip()] if y_sorted else []
        for c in candidates:
            if c:
                counts[c] = counts.get(c, 0) + 1
    threshold = len(layout.pages) // 2 + 1
    return {line for line, n in counts.items() if n >= threshold}


def _f0_strip_running_and_footnotes(
    raw_text: str, layout, table_regions: list[dict] | None = None,
) -> tuple[str, list[tuple[int, int]], list[str]]:
    """Strip running headers/footers and footnotes from the text-channel body.

    The body stays sourced from ``raw_text`` (the pdftotext text channel); the
    layout channel is used only to *identify* which lines are running
    headers/footers/footnotes, which are then removed from ``raw_text`` (headers
    and footers dropped; footnotes moved to a ``\\n\\f\\f\\n`` appendix). This is
    the L-001/L-007 text-channel/layout-channel split — the body is never
    rebuilt from ``span.text``, which previously caused the v2.4.86 word-gluing
    and two-column interleaving regressions.

    Returns ``(post_strip_text_with_appendix, footnote_spans_in_raw_text,
    footnote_texts)``. ``footnote_texts`` is parallel to the spans list —
    ``footnote_texts[i]`` is the raw_text slice for ``footnote_spans[i]``.
    """
    from .extract_layout import LayoutDoc

    if not isinstance(layout, LayoutDoc) or not layout.pages:
        return raw_text, [], []

    body_size = _body_size(layout)

    # Pre-index table regions by 1-indexed page number for fast lookup.
    regions_by_page: dict[int, list[tuple[float, float, float, float]]] = {}
    if table_regions:
        for r in table_regions:
            page = int(r.get("page", 0))
            bbox = r.get("bbox")
            if page < 1 or not bbox or len(bbox) != 4:
                continue
            regions_by_page.setdefault(page, []).append(tuple(bbox))  # type: ignore[arg-type]

    def _span_in_table_region(span_y0: float, span_y1: float, span_x0: float,
                              span_x1: float, page_1based: int) -> bool:
        for rx0, rtop, rx1, rbot in regions_by_page.get(page_1based, ()):
            # Span y-range overlaps region y-range AND x-range overlaps region x-range.
            if span_y1 < rtop or span_y0 > rbot:
                continue
            if span_x1 < rx0 or span_x0 > rx1:
                continue
            return True
        return False

    # ── Classify spans → build strip-key SETS (do NOT rebuild body) ─────────
    # L-001 / L-007: the body MUST stay sourced from the text channel
    # (``raw_text`` = pdftotext), which already has correct column reading-order
    # AND correct inter-word spacing. Earlier this step rebuilt the whole body
    # from ``span.text``, which is what made both the v2.4.86 word-gluing
    # (spaces dropped on tight-kerned PDFs) and the residual two-column
    # interleaving (y-only span grouping merges left+right columns) possible.
    # The layout channel is used here ONLY to *identify* which lines are running
    # headers / footers / footnotes; those lines are then stripped from the
    # pdftotext body. Sourcing the body from pdftotext lifts the held-out PMC
    # token-F1 mean from ~0.745 (span rebuild) to ~0.77 (pdftotext + F0 strip),
    # on par with raw pdftotext — see an internal handoff doc (2026-06-13) and L-007.
    def _key(s: str) -> str:
        return " ".join(s.split())

    # A strip-key must be distinctive enough that a coincidental body line can't
    # collide with it under content matching: skip pure-numeric and very short
    # keys. Standalone page numbers / short banners are handled downstream by
    # P0 / P0r / R2 and are absent from the JATS body anyway, so excluding them
    # here costs nothing and removes the only realistic false-strip vector.
    def _usable(k: str) -> bool:
        return len(k) >= 4 and not k.isdigit()

    repeating_header_lines = _detect_repeating_lines(layout, position="top")
    repeating_footer_lines = _detect_repeating_lines(layout, position="bottom")

    header_footer_keys: set[str] = set()
    footnote_keys: set[str] = set()

    for page in layout.pages:
        body_y_min, body_y_max = _body_y_band(page, body_size)
        for span in page.spans:
            line_text = span.text.strip()
            if not line_text:
                continue

            is_header = (
                line_text in repeating_header_lines
                or span.y0 > body_y_max + 30
            )
            is_footer = (
                line_text in repeating_footer_lines
                and span.y0 < body_y_min - 30
            )
            is_footnote = (
                span.y0 < body_y_min - 30
                and span.font_size < body_size * 0.92
                and not is_footer
                and not _span_in_table_region(
                    span.y0, span.y1, span.x0, span.x1, page.page_index + 1,
                )
            )

            k = _key(line_text)
            if not _usable(k):
                continue
            if is_header or is_footer:
                header_footer_keys.add(k)
            elif is_footnote:
                footnote_keys.add(k)

    # A header key that is also classified as a footnote elsewhere is dropped as
    # a header (never moved to the appendix, never kept as body).
    footnote_keys -= header_footer_keys

    # ── Strip identified lines FROM the pdftotext body, preserving its order ──
    # Treat BOTH "\n" and "\f" (the pdftotext page separator, emitted bare with
    # no surrounding newline) as line boundaries, so a page-boundary line is not
    # glued to the next page's running header. We split keeping the separators so
    # byte offsets into raw_text stay exact for the footnote spans — str.split()
    # / str.splitlines() would lose that exactness and also over-split on Unicode
    # separators.
    out_parts: list[str] = []
    footnote_chunks: list[str] = []
    footnote_raw_spans: list[tuple[int, int]] = []
    footnote_raw_texts: list[str] = []  # parallel to footnote_raw_spans

    segments = re.split(r"([\n\f])", raw_text)  # [content, sep, content, sep, ..., content]
    offset = 0
    for idx in range(0, len(segments), 2):
        content = segments[idx]
        sep = segments[idx + 1] if idx + 1 < len(segments) else ""
        consumed = len(content) + len(sep)
        stripped = content.strip()
        k = _key(stripped)
        if k and _usable(k) and k in header_footer_keys:
            offset += consumed
            continue
        if k and _usable(k) and k in footnote_keys:
            # Record exact (start, end) so report.footnote_texts[i] equals
            # raw_text[start:end] (the spans/texts arrays stay parallel).
            lead = len(content) - len(content.lstrip())
            start = offset + lead
            end = start + len(stripped)
            footnote_raw_spans.append((start, end))
            footnote_raw_texts.append(stripped)
            footnote_chunks.append(stripped)
            offset += consumed
            continue
        out_parts.append(content + sep)
        offset += consumed

    body = "".join(out_parts)
    if footnote_chunks:
        appendix = "\n\f\f\n" + "\n\n".join(footnote_chunks)
    else:
        appendix = ""
    return body + appendix, footnote_raw_spans, footnote_raw_texts


def _detect_recurring_page_numbers(raw_text: str) -> set[int]:
    """Return integers that appeared as standalone-line page numbers ≥2 times.

    Threshold ≥2 (not ≥3) — short articles only repeat the page header on a
    handful of pages, so we'd miss real artifacts (e.g. RSOS p.41 in
    Li&Feldman appears only twice as standalone). Combined with the lowercase-
    surround guard in R2, ≥2 is safe.
    """
    counts: dict[int, int] = {}
    for line in raw_text.split("\n"):
        s = line.strip()
        # ASCII-only digit check: `str.isdigit()` matches Unicode superscripts
        # (², ³) which would crash int() — guard with isascii() first.
        if 1 <= len(s) <= 3 and s.isascii() and s.isdigit():
            n = int(s)
            if 1 <= n <= 999:
                counts[n] = counts.get(n, 0) + 1
    return {n for n, c in counts.items() if c >= 2}


# v2.4.17 (NORMALIZATION_VERSION 1.8.5): R2 noun-exception list.
#
# R2 strips inline digits in references span when the digit value also appears
# as a standalone line elsewhere in the doc (treated as a page-number leak).
# BUT some PDFs have many standalone-digit lines that aren't page numbers
# (table cell values, footnote markers, etc.) — those falsely contaminate
# the candidate set.
#
# Confirmed at v2.4.16: amle_1 has "20" as a standalone line 4+ times (Yes/No
# table cell values), causing R2 to strip "20" from the legitimate reference
# title "The first 20 years of Organizational Research Methods" → "The first
# years of …". Same for "40" in "The Journal of Management's first 40 years"
# → "first years".
#
# Fix: a negative-lookahead exception list. If the digit is followed by a
# whitespace-then-noun-class word (years, days, hours, percent, participants,
# people, etc.), the digit is part of a body phrase, NOT a page-number leak —
# do not strip.
_R2_BODY_NOUN_PATTERN = re.compile(
    r"(?:years?|days?|months?|weeks?|hours?|minutes?|seconds?|"
    r"percent|cents?|dollars?|pounds?|kilograms?|kg|grams?|cm|mm|m|km|"
    r"miles?|inches?|feet|points?|times?|samples?|individuals?|"
    r"participants?|subjects?|respondents?|cases?|trials?|studies?|"
    r"articles?|papers?|books?|chapters?|sources?|authors?|"
    r"countries?|nations?|institutions?|universities?|firms?|"
    r"companies?|organizations?|teams?|groups?|hospitals?|schools?|"
    r"records?|entries?|observations?|measurements?|events?|incidents?|"
    r"people|persons?|adults?|children|students?|patients?|workers?|"
    r"employees?|managers?|leaders?|followers?|users?|members?|"
    r"votes?|comments?|ratings?|reviews?|posts?|tweets?|messages?|"
    r"items?|conditions?|variables?|categories?|topics?|themes?|"
    r"instruments?|measures?|scales?|factors?|dimensions?|domains?|"
    r"experiments?|datasets?|samples?|tasks?|stimuli|questions?)\b",
    re.IGNORECASE,
)

# v2.4.84 (NORMALIZATION_VERSION 1.9.31): R2 quantifier-head pre-context guard.
#
# The body-noun allowlist above is necessarily incomplete — it can never
# enumerate every countable noun a reference title might quantify ("3
# instruments", "5 trajectories", "12 heuristics", …). The amle_1 fix
# (v2.4.17) added nouns one at a time; the plos_med_1 "Clinimetric properties
# of 3 instruments" → "… of instruments" drop (filed by citationguard-iterate
# 2026-06-10, same class as the earlier Mayiwar case) is the same whack-a-mole
# recurring.
#
# A genuine page-number leak and a legitimate quantifier are distinguished by
# the word IMMEDIATELY PRECEDING the digit, not the noun after it:
#   * quantifier — the digit heads a noun phrase, so it follows a CLOSED-CLASS
#     function word (article / preposition / determiner): "of 3 instruments",
#     "the 5 factors", "first 20 years", "only 3 studies".
#   * page leak — the digit interrupts a content phrase, so it follows a
#     CONTENT word (adjective / noun): "psychological 41 science",
#     "recovery 12 in a population".
# Function words are a finite closed class, so keying on them generalizes where
# the open-ended noun list cannot. This guard is purely ADDITIVE — it only
# ever PRESERVES a digit (returns True), never strips one — so it cannot make
# R2 strip anything it did not already strip (no false-positive page numbers
# newly retained beyond the safe direction). Per docpluck's correctness
# asymmetry, silently deleting a digit from a scientific reference title (rule
# 0a, NO TEXT MAY DISAPPEAR) is far worse than leaving a stray page number, so
# biasing toward preserve at a quantifier head is the correct trade.
_R2_QUANTIFIER_HEAD_WORDS = frozenset(
    {
        # articles
        "a", "an", "the",
        # prepositions
        "of", "in", "on", "at", "to", "for", "with", "by", "from", "as",
        "into", "than", "between", "among", "amongst", "through", "during",
        "after", "before", "over", "under", "about", "across", "per",
        "within", "upon", "against", "toward", "towards", "around",
        # conjunctions
        "and", "or", "nor", "but",
        # determiners / quantifier-context heads
        "all", "both", "these", "those", "some", "any", "each", "every",
        "first", "last", "next", "only", "total", "following", "remaining",
        "top", "approximately", "nearly", "least", "most", "up", "least",
        "another", "additional", "further", "respective", "successive",
    }
)
# Trailing-word extractor: the alphabetic word ending right before ``match_pos``
# (the optional trailing hyphen lets "well-3" style hyphenations still resolve
# to the final segment, which is what matters for the function-word lookup).
_R2_PRECEDING_WORD = re.compile(r"([A-Za-z]+)[\s ]*$")


def _r2_is_body_phrase(digit_str: str, refs_text: str, match_pos: int) -> bool:
    """Return True if the digit at ``match_pos`` is part of a body phrase
    (e.g. "20 years", "1,675 participants", "of 3 instruments") and should
    NOT be stripped by R2 (the page-number scrub).

    Two complementary, both-conservative signals — either one preserves:

    1. **Following body-noun** — the 60-char window AFTER the digit contains a
       known body-noun keyword (years, participants, instruments, …). Handles
       "20 years", "1,675 participants".
    2. **Preceding quantifier head** — the word IMMEDIATELY BEFORE the digit is
       a closed-class function word (article / preposition / determiner), so
       the digit heads a quantified noun phrase ("of 3 instruments", "the 5
       factors") rather than interrupting a content phrase. Generalizes beyond
       the finite noun list. See ``_R2_QUANTIFIER_HEAD_WORDS``.

    A genuine page-number leak ("psychological 41 science", "recovery 12 in a
    population") fails BOTH checks — the noun after isn't in the list and the
    word before is a content word — so it is still stripped.
    """
    # (1) Following body-noun. Window starts after the digit + at least one space.
    window_start = match_pos + len(digit_str)
    window = refs_text[window_start:window_start + 60]
    if _R2_BODY_NOUN_PATTERN.search(window):
        return True

    # (2) Preceding quantifier head (closed-class function word).
    m = _R2_PRECEDING_WORD.search(refs_text[:match_pos])
    if m and m.group(1).lower() in _R2_QUANTIFIER_HEAD_WORDS:
        return True

    return False


def _looks_like_ref_start(line: str) -> bool:
    return bool(
        _REF_START_VANCOUVER.match(line)
        or _REF_START_IEEE.match(line)
        or _REF_START_APA.match(line)
        or _REF_START_HARVARD.match(line)
    )


_BARE_REF_NUM_RE = re.compile(r"^(\d{1,3})\.\s*$")


def _pair_two_column_bibliography(refs_text: str) -> str:
    """Pair a column of bare `N.` lines with the column of entry lines that
    follows it. Used when pdftotext streams a 2-column bibliography as
    "all numbers first, then all entries" — the canonical Royal Society
    layout that broke Li&Feldman 2025 RSOS.

    Conservative: only acts when (a) the refs span begins with ≥3 bare
    `\\d+\\.` lines, (b) their numeric sequence is monotonic and starts at
    1 or 2 (no big gaps), (c) at least the same count of entry-shaped
    lines (start with capital letter or `[` for IEEE) follows after a
    blank-line break. If any precondition fails, return the input
    unchanged — R3's normal continuation join handles the standard
    single-column case.
    """
    lines = refs_text.split("\n")
    # Skip leading blanks / "References" header line.
    start = 0
    while start < len(lines) and not _BARE_REF_NUM_RE.match(lines[start].strip()):
        start += 1
        if start > 5:
            # not a leading bare-number column
            return refs_text
    if start >= len(lines):
        return refs_text
    # Collect the run of bare numbered lines.
    nums: list[tuple[int, int]] = []  # (line index, ref number)
    i = start
    while i < len(lines):
        m = _BARE_REF_NUM_RE.match(lines[i].strip())
        if not m:
            break
        nums.append((i, int(m.group(1))))
        i += 1
    if len(nums) < 3:
        return refs_text
    # Monotonic + small step (1 or 2) and starts ≤ 2.
    if nums[0][1] > 2:
        return refs_text
    for (_, a), (_, b) in zip(nums, nums[1:]):
        if not (1 <= b - a <= 2):
            return refs_text
    # Skip the blank-line gap.
    end_of_nums = nums[-1][0] + 1
    j = end_of_nums
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j == end_of_nums:
        # No blank-line gap separates the two columns — likely not the
        # two-column form.
        return refs_text
    # Collect the run of entry-shaped lines (start with capital letter or
    # `[` for IEEE), at least one per number.
    entries: list[int] = []
    k = j
    while k < len(lines) and len(entries) < len(nums):
        s = lines[k].strip()
        if not s:
            break
        if s[0].isupper() or s.startswith("["):
            entries.append(k)
        else:
            # continuation of previous entry — append to it
            if entries:
                lines[entries[-1]] = lines[entries[-1]].rstrip() + " " + s
                lines[k] = ""
            else:
                # entry column did not start with a capital — bail.
                return refs_text
        k += 1
    if len(entries) < len(nums):
        # Not enough entries to pair — bail.
        return refs_text
    # Pair: prepend `N. ` to each entry, blank out the bare-number lines.
    for (num_idx, num), entry_idx in zip(nums, entries):
        lines[entry_idx] = f"{num}. {lines[entry_idx].lstrip()}"
        lines[num_idx] = ""
    return "\n".join(lines)


# ── H0 / T0 / P0 / H1 : document-shape strips (NORMALIZATION_VERSION 1.8.0) ──
# Ported from an internal design doc
# (iter-20, iter-25, iter-26, iter-27). These run BEFORE the unicode/whitespace
# steps so the line-level regexes match raw pdftotext output.

# H0: explicit publisher / journal / repository banner lines that appear in the
# document header zone. A line is dropped ONLY if it matches an explicit
# pattern — anything else (titles, authors, affiliations, unknown text) stays.
_HEADER_BANNER_PATTERNS: list[re.Pattern[str]] = [
    # Bare URL line (publisher landing page).
    re.compile(r"^(?:https?://)?(?:www\.)?\S+\.(?:com|org|edu|gov|net|fr|uk|jp|cn|de|ch|nl)(?:/\S*)?$"),
    # NCBI / HHS / PMC manuscript banner (3-line block).
    re.compile(r"^HHS Public Access$"),
    re.compile(r"^Author manuscript$"),
    re.compile(r"^Published in final edited form as:.*$"),
    # Royal Society Open Science masthead.
    re.compile(r"^Cite this article:.*$"),
    re.compile(r"^Subject (?:Category|Areas):.*$"),
    re.compile(r"^Author for correspondence:.*$"),
    re.compile(r"^Received:\s+\d{1,2}\s+\w+\s+\d{4}.*$"),
    re.compile(r"^Accepted:\s+\d{1,2}\s+\w+\s+\d{4}.*$"),
    # Elsevier / ScienceDirect masthead.
    re.compile(r"^Contents lists available at\s+\S+.*$"),
    re.compile(r"^journal homepage:.*$", re.IGNORECASE),
    # Tandfonline / Taylor & Francis masthead.
    re.compile(r"^ISSN:\s*\S+.*$"),
    re.compile(r"^To cite this article:.*$"),
    re.compile(r"^To link to this article:.*$"),
    re.compile(r"^View supplementary material.*$"),
    re.compile(r"^Full Terms.*Conditions of access.*$"),
    # arXiv preprint banner.
    re.compile(r"^arXiv:\d+\.\d+(?:v\d+)?\s+\[[\w\.-]+\]\s+\d{1,2}\s+\w+\s+\d{4}\s*$"),
    # Article-type / category single-word labels.
    re.compile(r"^Article$"),
    re.compile(r"^ARTICLE$"),
    re.compile(r"^Research$"),
    re.compile(r"^Empirical Research Paper$"),
    re.compile(r"^Original (?:Investigation|Article|Research)(?:\s*\|\s*.+)?$"),
    re.compile(r"^Article\s+type[:.]\s*.*$", re.IGNORECASE),
    # AOM "r Academy of Management ..." masthead.
    re.compile(r"^r\s+Academy of Management\s+\S.*\d{4},.*$"),
    # SAGE / generic journal volume + page-range banner.
    re.compile(
        r"^[A-Z][A-Za-z &\-‐-―]{4,60}\s+\d{4},\s+Vol\.\s+\d+(?:\(\d+\))?[\s,].+$"
    ),
    # Chicago / Demography / similar: "Journal Name. YYYY Month DD; Vol(Iss): pages. doi:..."
    re.compile(
        r"^[A-Z][A-Za-z &]{3,40}\.\s+\d{4}.*\d+[:;].+doi:.*$"
    ),
    # SAGE / Cambridge / generic: "British Journal of Political Science (YYYY), Vol, pages doi:..."
    re.compile(
        r"^[A-Z][A-Za-z &]{4,60}\s+\(\d{4}\),\s+\d+,\s+\d+.{0,200}$"
    ),
    # Mangled DOI lines from publishers that overlay two PDF text runs.
    # v2.4.8: removed `^` anchor — PSPB / SAGE banners place the corrupted
    # DOI mid-line after the journal name, so the whole line is publisher
    # banner gibberish; "Dhtt" only appears in this specific corruption.
    re.compile(r".*Dhtt[Oo]ps[Ii]://.*$"),
    # Manuscript-ID gibberish like "1253268 ASRXXX10.1177/00031224241253268..."
    re.compile(r"^\d{6,}\s+[A-Z]{2,}[A-Z0-9]*\d+\.\d{4,}/.+$"),
    # §B-new-5 (NORMALIZATION_VERSION 1.9.23, 2026-05-23): SAGE/journal-ID
    # welded-banner concatenation. pdftotext serialises the journal banner,
    # DOI, journal name, and running header as ONE line because they share
    # a y-position. Shape: 2+ uppercase letters + optional digit prefix +
    # `10.dddd/` DOI prefix + DOI digit suffix + journal name + author-
    # pair, all glued together. Canonical: `PSPXXX10.1177/01461672251327169
    # Personality and Social Psychology BulletinIp and Feldman`. NO
    # whitespace separators (distinguishes from the `^\d{6,}\s+[A-Z]{2,}…`
    # masthead above which has whitespace). The line is suppressed
    # entirely — the welded banner is publisher furniture and the real
    # title sits below it.
    re.compile(r"^[A-Z]{2,}\d*10\.\d{4,}/\d{6,}[A-Z][a-z].*$"),
    # Generic journal-citation banner with DOI suffix.
    re.compile(r"^[A-Z][A-Za-z\-]+,\s+\d{4},\s+vol(?:ume)?\s+\d+.*https?://doi\.org/.*$", re.IGNORECASE),
    # ScienceDirect issue line: "Journal Name 96 (2021) 104154 Contents lists..."
    re.compile(r"^[A-Z][A-Za-z &]+\s+\d+\s+\(\d{4}\)\s+\d+(?:\s+Contents.*)?$"),
    # Standalone Digital Object Identifier line.
    re.compile(r"^Digital Object Identifier\s+10\.\d+/.+$"),
    # B3 (2026-05-22): bare "DOI: 10.xxxx/..." header-zone banner.
    # The brjpsych_1 masthead is "DOI: 10.1111/bjop.12757" on its own
    # line. P0 has a sibling lowercase-``doi:`` pattern for in-body
    # footers; H0 needs the case-insensitive variant here so the
    # header-zone strip happens in the SAME pass as the bare-URL strip
    # below it — otherwise H0's 30-line cap will catch a later
    # wileyonlinelibrary.com line in pass 2 only (after pass 1's P0
    # strip shifted lines up), breaking idempotence.
    re.compile(r"^DOI:?\s+10\.\d{3,5}/\S+\s*$", re.IGNORECASE),
    # Curated bare journal-name lines (small-font running banner above title).
    re.compile(r"^Journal of Economic Psychology$"),
    re.compile(r"^Cognition and Emotion$"),
    re.compile(
        r"^Journal of Experimental Social Psychology"
        r"(?:\s+\d+(?:\s*\(\d{4}\))?\s+\d+[‐-―\-]\d+)?$"
    ),
    # Judgment and Decision Making cite-line banner.
    re.compile(
        r"^[A-Z][A-Za-z]+(?:\s+[A-Za-z]+){1,8},\s+"
        r"Vol\.\s+\d+,\s+No\.\s+\d+,\s+\w+\s+\d{4},\s+pp\.\s+\d+[‐-―\-]\d+\s*$"
    ),
    # Oxford-journals: "Social Forces, 2025, 104, 224–249".
    re.compile(
        r"^[A-Z][A-Za-z]+(?:\s+[A-Za-z]+){0,3},\s+\d{4},\s+\d+,\s+\d+[‐-―\-]\d+\s*$"
    ),
    # Oxford-journals supplementary doi banner.
    re.compile(r"^https?://doi\.org/\S+\s+Advance access.*$"),
]


def _strip_document_header_banners(text: str) -> str:
    """H0: drop publisher/journal/repo banner lines in the document header zone.

    Header zone = everything before the first ``##`` heading, capped at the
    first 30 lines. (In the library pipeline ``##`` headings have not been
    added yet, so the 30-line cap is what applies.) Lines are dropped only on
    explicit pattern match; title / author / affiliation lines (which never
    match any banner pattern) are preserved verbatim.
    """
    if not text:
        return text
    lines = text.split("\n")
    header_end = len(lines)
    cap = min(len(lines), 30)
    for idx in range(cap):
        if lines[idx].lstrip().startswith("##"):
            header_end = idx
            break
    else:
        header_end = cap

    out_lines: list[str] = []
    dropped_any = False
    for idx, line in enumerate(lines):
        if idx < header_end:
            stripped = line.strip()
            if stripped and any(
                p.match(stripped) for p in _HEADER_BANNER_PATTERNS
            ):
                dropped_any = True
                continue
        out_lines.append(line)

    if not dropped_any:
        return text

    cleaned = "\n".join(out_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if cleaned.startswith("\n"):
        cleaned = cleaned.lstrip("\n")
    return cleaned


# T0: TOC dot-leader strip — Nature Supplementary PDFs render their TOC with
# runs of ``___`` (pdftotext's encoding of dot-leader filler characters).
_TOC_DOT_LEADER_RE = re.compile(r"_{3,}")
_PURE_TOC_LEADER_RE = re.compile(r"^\s*_{3,}\s*\d{0,4}\s*$")
_TOC_HEADING_RE = re.compile(
    r"^\s*(?:Table\s+of\s+Contents|List\s+of\s+(?:Supplementary\s+)?(?:Figures?|Tables?))\s*$",
    re.IGNORECASE,
)


def _strip_toc_dot_leader_block(text: str) -> str:
    """T0: drop TOC paragraphs with dot-leader page-number trails.

    Scope is limited to the first ~100 lines of the document (TOCs live near
    the top). Drops paragraphs that contain ``_{3,}`` runs or explicit TOC
    label lines. Also drops a ``## Heading`` whose immediate next paragraph is
    a TOC dot-leader paragraph (misparsed TOC entry promoted to a false
    heading) — this second rule fires only when section-detection has already
    introduced headings, which in the library pipeline happens later, so it
    is effectively a no-op here. Kept for parity with the spike behavior in
    case ``normalize_text`` is ever called on already-rendered markdown.
    """
    if not text:
        return text
    head_zone = text[:8000]
    if "_" not in head_zone and not re.search(
        r"\b(?:Table\s+of\s+Contents|List\s+of\s+(?:Supplementary\s+)?(?:Figures?|Tables?))\b",
        head_zone,
        re.IGNORECASE,
    ):
        return text
    parts = re.split(r"(\n\n+)", text)
    n = len(parts)

    cum_lines = 0
    last_para_idx_in_zone = -1
    for i in range(0, n, 2):
        if cum_lines >= 100:
            break
        last_para_idx_in_zone = i
        cum_lines += parts[i].count("\n") + 1
        if i + 1 < n:
            cum_lines += parts[i + 1].count("\n")

    drop_idx: set[int] = set()
    for i in range(0, last_para_idx_in_zone + 1, 2):
        para = parts[i]
        para_s = para.strip()
        if not para_s:
            continue
        is_toc = (
            _TOC_DOT_LEADER_RE.search(para)
            or _TOC_HEADING_RE.match(para_s)
        )
        if is_toc:
            drop_idx.add(i)
            if i >= 2 and parts[i - 2].strip().startswith("## "):
                drop_idx.add(i - 2)

    if not drop_idx:
        return text

    kept: list[str] = []
    for i in range(0, n, 2):
        if i in drop_idx:
            continue
        kept.append(parts[i])

    while kept and not kept[0].strip():
        kept.pop(0)
    cleaned = "\n\n".join(kept)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# P0: page-footer / running-header LINES anywhere in the document. Curated
# patterns only — each must match a single COMPLETE line.
_PAGE_FOOTER_LINE_PATTERNS: list[re.Pattern[str]] = [
    # Bare page number: "Page 1", "Page 27".
    re.compile(r"^Page\s+\d+\s*$"),
    # Page-N-of-M with date prefix: "October 27, 2023 1/13".
    re.compile(
        r"^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*20\d{2}\s+\d+/\d+\s*$"
    ),
    # v2.4.74 (jama-open-1 RUNNING_HEADER_LEAK fix, 2026-05-25): bare date
    # line as page-footer ("October 27, 2023" alone on its own line). JAMA
    # Open paginates with the publication date repeated at the foot of every
    # page. Structural signature: a complete-line, full-month-name + day +
    # comma + 4-digit year, NOTHING ELSE. Distinguished from the legitimate
    # "Published: October 27, 2023. doi:10.1001/..." metadata line (which
    # has the "Published:" prefix and DOI suffix and survives this strip).
    re.compile(
        r"^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*20\d{2}\s*$"
    ),
    # Bare "(continued)" page-break marker.
    re.compile(r"^\([Cc]ontinued\)\s*$"),
    # Affiliation footnote markers like "aETH Zurich".
    re.compile(r"^[a-z][A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s*$"),
    # "Corresponding Author:" lines.
    re.compile(r"^Corresponding\s+[Aa]uthor[s]?:.*$"),
    # "Author for correspondence:" Royal Society style.
    re.compile(r"^Author\s+for\s+correspondence:.*$", re.IGNORECASE),
    # Email/phone metadata lines.
    re.compile(r"^E-?mail(?:s)?:\s*\S+@.+$", re.IGNORECASE),
    re.compile(r"^Tel(?:\.|ephone)?:\s*\S.*$", re.IGNORECASE),
    re.compile(r"^Fax:\s*\S.*$", re.IGNORECASE),
    # Bare email line (one or more emails separated by whitespace/punct).
    re.compile(
        r"^[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,6}(?:[\s,;]+[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,6})*\s*$"
    ),
    # JAMA running header line.
    re.compile(
        r"^JAMA\s+Network\s+Open\.\s+20\d{2};\d+\(\d+\):e\d+\.\s*doi:10\.\d+/.+$"
    ),
    # 2026-05-26 (Cluster E, ip_feldman + chan_feldman): Sage / PSPB
    # publisher front-matter boilerplate. "Article reuse guidelines:"
    # appears alone on its own line as part of the publisher furniture
    # block. Tight enough to be P0-globally-safe (this phrase doesn't
    # appear in legitimate body prose). Unlike the other Cluster E
    # patterns (article-ID + article-type code, both reverted because
    # they exposed a wrapped-title duplicate), this one is safe to keep:
    # the label is a leaf node in the masthead block, not the load-
    # bearing separator the others turned out to be.
    re.compile(r"^Article\s+reuse\s+guidelines:?\s*$", re.IGNORECASE),
    # JAMA category banner.
    re.compile(r"^JAMA\s+Network\s+Open\s+\|\s+\S.*$"),
    # Compound license + citation footer.
    re.compile(
        r"^Open\s+Access\.\s+This is an open access article.*doi:10\.\d+/.+$"
    ),
    # Standalone copyright line "© 20YY ...".
    re.compile(r"^©\s*20\d{2}\b.*$"),
    re.compile(r"^\(c\)\s*20\d{2}\b.*$", re.IGNORECASE),
    # JAMA sidebar pointer.
    re.compile(
        r"^Author affiliations and article information are listed at the end of (?:this article|the article)\.?\s*$"
    ),
    # JAMA visual-abstract sidebar.
    re.compile(r"^\+\s*Visual Abstract.*Supplemental content\s*$"),
    re.compile(r"^\+\s*Supplemental content\s*$"),
    # Compound copyright-footer.
    re.compile(
        r"^Received:\s+[\w ,]+\d{4}\.\s+(?:Revised:.*Accepted:.*"
        r"|Accepted:.*)\s*©.*$"
    ),
    # Parenthesized cite-line: "(Received DD Month YYYY; revised...)".
    re.compile(
        r"^\(Received\s+\d{1,2}\s+\w+\s+\d{4};\s+(?:revised|accepted).*\)\s*$",
        re.IGNORECASE,
    ),
    # Standalone open-access license footers.
    re.compile(
        r"^©\s+The Author\(s\)[,\s]+\d{4}\..*Cambridge University Press.*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^©\s+The Author\(s\)[,\s]+\d{4}\..*Published by .*$",
        re.IGNORECASE,
    ),
    re.compile(r"^This is an open access article distributed under.*$", re.IGNORECASE),
    # PMC supplementary-material footer.
    re.compile(
        r"^ELECTRONIC SUPPLEMENTARY MATERIAL\b.*$",
        re.IGNORECASE,
    ),
    # Running-header lines with "| <page>" or "<page> Author et al.".
    re.compile(r"^\S(?:[^|\n]{2,80})\|\s*\d{1,4}\s*$"),
    re.compile(r"^\d{1,4}\s+[A-ZÀ-ÿ][^\n]{1,60}\s+et al\.?\s*$"),
    # v2.4.6: "Q. XIAO ET AL." style running header — surname journal abbrev
    # used by CRSP, JESP, and many other 2-column journals. Accepts:
    #   "Q. XIAO ET AL."         single initial + surname
    #   "Q.M. XIAO ET AL."       two initials with internal period
    #   "Q. M. XIAO ET AL"       two initials with space (no trailing dot)
    # All-caps surname required (lowercase letters appear in regular prose
    # like "Most participants in the experimental condition were …").
    re.compile(
        r"^[A-Z]\.(?:\s*[A-Z]\.?)?\s+[A-Z]{2,}\s+ET\s+AL\.?\s*$"
    ),
    # v2.4.23 (NORMALIZATION_VERSION 1.8.8): prod-pdftotext-skew patterns.
    # Xpdf 4.00 (local Win) and poppler 25.03 (Railway Linux) emit
    # different line-break placements. P0 line patterns only match
    # COMPLETE single lines (anchored `^…$`). Prod's poppler often splits
    # what Xpdf serializes as a single line into multiple lines, so the
    # previous P0 patterns miss the strip on prod. Surfaced by v2.4.16
    # Phase 8 Tier 3 byte-diff (xiao_2021_crsp T2 vs T3 had +4897 bytes
    # of front-matter junk retained on prod).
    #
    # Strategy: add patterns for the specific front-matter junk lines
    # that prod's poppler emits as standalone lines (where Xpdf merged
    # them into longer banner lines). Conservative — each pattern matches
    # a complete line on its own.
    re.compile(r"^Submit your article to this journal\s*$", re.IGNORECASE),
    re.compile(r"^ARTICLE HISTORY\s*$"),
    re.compile(r"^Published online:?\s+\d{1,2}\s+\w+\s+\d{4}\.?\s*$", re.IGNORECASE),
    re.compile(r"^View related articles?\s*$", re.IGNORECASE),
    re.compile(r"^View Crossmark data\s*$", re.IGNORECASE),
    re.compile(r"^Citing articles?:\s+\d+\s+View citing articles?\s*$", re.IGNORECASE),
    re.compile(r"^Full Terms\s+&?\s+Conditions of access and use\.?\s*$", re.IGNORECASE),
    # Bare "Received DD Month YYYY" line (T&F masthead split by poppler)
    re.compile(r"^Received\s+\d{1,2}\s+\w+\s+\d{4}\s*$"),
    re.compile(r"^Accepted\s+\d{1,2}\s+\w+\s+\d{4}\s*$"),
    re.compile(r"^Revised\s+\d{1,2}\s+\w+\s+\d{4}\s*$"),

    # v2.4.19: same-surname two-author running header:
    #   "Kim and Kim" (Yeun Joon Kim & Junha Kim — amj_1, 14 occurrences)
    #   "Smith and Smith" / "Lee and Lee" (any X-and-X co-author pattern)
    # Anchored on `(\w+) and (?:that same word)` — distinct from prose
    # "John and Mary" (different names). Conservative: same surname only.
    re.compile(r"^(?P<surname>[A-Z][a-z]+) and (?P=surname)\s*$"),
    # v2.4.19: bare month-name page marker (AOM, ASA, T&F volume headers):
    #   "April" (amj_1: AOM April 2020 issue, 14 occurrences)
    #   "March" / "October" / etc.
    # Page-marker month names appear ALONE on a line as the issue indicator.
    # Body prose never uses a month name alone on a line.
    re.compile(
        r"^(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s*$"
    ),
    # v2.4.16: bare uppercase running header with lowercase "et al." tail:
    #   "RECKELL et al."
    #   "SMITH et al"
    #   "VAN DER WAL et al."   (preceded by space-separated prefix tokens)
    # Distinct from the variants above (which require initials prefix or
    # all-caps ET AL). Appears as its own paragraph in IEEE / 2-column
    # journals between Abstract and Introduction and at every page break.
    # Globally safe: an all-caps surname + lowercase et al. on a line by
    # itself is unambiguously a running header — in-paragraph citations
    # never appear without parens / year.
    re.compile(
        r"^[A-Z]{2,}(?:\s+[A-Z]{2,}){0,3}\s+et\s+al\.?\s*$"
    ),
    # v2.4.114: Title-Case (mixed-case) surname running header —
    #   "Efendić et al."   (Sage SPPS, at every page break; the line comes in
    #                       as "\fEfendić et al." but `.strip()` removes the \f)
    #   "van der Wal et al." / "García Márquez et al." (particles + accents)
    # The all-caps pattern above misses these because the surname is Title-Case.
    # A Title-Case "Surname et al." can be an inline citation, so this is safe
    # ONLY because it matches the COMPLETE line ("^…$") with NOTHING after
    # "et al." — an in-text citation always carries a "(YEAR)" or continues the
    # sentence ("…by Efendić et al., 2022, this holds"; "Efendić et al. (2022)
    # found…"), never a bare "Surname et al." alone on its own line. Surname
    # chars include Latin-1 + Latin Extended-A (ć/ń/ø/š/ž…); up to 3 tokens with
    # nobiliary particles (van/der/de/…). FP-validated: 14-case battery (6 strip,
    # 8 keep incl. every inline-citation shape) + corpus scan.
    re.compile(
        r"^(?:(?:van|von|der|den|de|di|da|le|la|el|bin|ibn|dos|das|du)\s+)*"
        r"[A-ZÀ-ÖØ-ÞĀ-ſ][A-Za-zÀ-ÖØ-öø-ÿĀ-ſ'’\-]+"
        r"(?:\s+(?:(?:van|von|der|den|de|di|da|le|la|el|bin|ibn|dos|das|du)\s+)*"
        r"[A-ZÀ-ÖØ-ÞĀ-ſ][A-Za-zÀ-ÖØ-öø-ÿĀ-ſ'’\-]+){0,2}"
        r"\s+et\s+al\.?\s*$"
    ),
    # v2.4.16: Taylor & Francis "Supplemental data for this article …"
    # sidebar boilerplate. Exact-phrase pattern — safe globally.
    re.compile(
        r"^Supplemental\s+data\s+for\s+this\s+article\s+can\s+be\s+"
        r"accessed\s+(?:here|online|via)\.?\s*$",
        re.IGNORECASE,
    ),
    # v2.4.16: truncated affiliation that ends at "University of" with no
    # place name on the same line. Distinct from the full form
    # "Department of X, University of Y" (P0 already strips that via the
    # earlier pattern on line ~651) because of the trailing ``$`` after
    # "University of" — nothing follows on the line.
    re.compile(
        r"^Department\s+of\s+[A-Z][A-Za-z]+"
        r"(?:\s+and\s+[A-Z][A-Za-z\s]+?)?,\s*University\s+of\s*$"
    ),
    # v2.4.6: contact-line footer used by Taylor & Francis (CRSP, etc.):
    #   "CONTACT Gilad Feldman gfeldman@hku.hk; giladfel@gmail.com …"
    # The `CONTACT` keyword + name + email is distinctive enough to anchor
    # safely. Optional trailing affiliation / region tokens.
    re.compile(
        r"^CONTACT\s+[A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+)+\s+\S+@\S+.*$"
    ),
    # 2026-08-05 (run 6, cycle 1 — xiao_2021_crsp): the WRAPPED form of the
    # T&F contact footer. The v2.4.6 pattern above requires `CONTACT`, the
    # name AND the email on ONE line; when the source PDF column-wraps the
    # correspondence block, pdftotext serialises it across several lines:
    #
    #   CONTACT Gilad Feldman            <- opener, no email  (LEAKED)
    #   gfeldman@hku.hk; giladfel@gmail.com   <- dropped by the email pattern
    #   Hong Kong, Hong Kong SAR         <- region tail       (LEAKED)
    #   Supplemental data for this article can be accessed here.  <- dropped
    #   © 2021 European Association of Social Psychology          <- dropped
    #
    # so 4 of 6 lines were already stripped and the opener + region tail
    # survived — landing INSIDE a body sentence ("The target and the /
    # CONTACT Gilad Feldman / … / competitor form a core choice set").
    #
    # Keyed on the structural signature (line-initial all-caps `CONTACT`
    # followed ONLY by a personal name), not on paper identity. Ordinary
    # prose does not begin a line with the bare token `CONTACT` + a name:
    # the sentence form is "Contact" (title case) and the nav/heading forms
    # ("CONTACT US", "CONTACT INFORMATION", "CONTACT Details Below") are
    # excluded by requiring Titlecase-or-initial name words and by the
    # _CONTACT_NON_NAME_WORDS veto applied in `_strip_page_footer_lines`.
    # Accepts O’Brien / Mary-Jane / McDonald / José Álvarez and single
    # middle initials ("John R. Smith").
    #
    # NOTE: the wrapped form is NOT a member of this list — it lives in
    # `_WRAPPED_CONTACT_OPENER` and is applied by `_strip_page_footer_lines`
    # ahead of this list, because it needs two things a plain list entry
    # cannot express: the `_CONTACT_NON_NAME_WORDS` veto (so "CONTACT Details
    # Below" is kept) and the region-tail continuation state. Putting it in
    # the list would let the generic any()-match drop the vetoed lines first.
    # v2.4.6: prefixed author-contribution / corresponding-author footnotes
    # used by Collabra, eLife, PLOS, etc.:
    #   "a Contributed equally, joint first author"
    #   "b Contributed equally, joint first author"
    #   "c Corresponding Author: <name>, <affiliation>"
    # v2.4.81 (untested-corpus sweep): Collabra emits the lowercase
    # "a Corresponding author: <affiliation>; <email>" form (lowercase "author")
    # and the combined "a Shared first author b Corresponding author: …" line —
    # both leaked into the body on collabra.37122 / collabra.77859. Make "author"
    # case-insensitive and add the shared/joint-first-author footnote openers.
    re.compile(
        r"^[a-z]\s+(?:Contributed\s+equally|Corresponding\s+[Aa]uthor"
        r"|Shared\s+first\s+author|Joint\s+first\s+author)\b.*$"
    ),
    # v2.4.6: standalone affiliation lines that recur on bottom of every
    # page in 2-column journals — "Department of <field>, University of
    # <place>, <region>".
    re.compile(
        r"^Department\s+of\s+[A-Z][A-Za-z]+(?:\s+and\s+[A-Z][A-Za-z]+)?,\s+"
        r"University\s+of\s+[A-Z][A-Za-z]+(?:\s+Kong)?,\s+.{2,80}$"
    ),
    # 2026-05-25 (Cluster C, ip_feldman finding #1): bare-university and
    # name-led affiliation shapes that pdftotext emits when the front-matter
    # block is column-wrapped.  The above pattern (v2.4.6) requires "Department
    # of X" prefix; PSPB's ip_feldman_2025_pspb has two other publisher-
    # furniture shapes:
    #
    #   (1) "University of <Place>, <City>, <Region>"
    #       — Hong Kong-style: "University of Hong Kong, Pok Fu Lam, Hong Kong SAR"
    #   (2) "<Name>, Department of <Field>, University of <Place>, <City>, <Region>."
    #       — corresponding-author paragraph leading with the name.
    #
    # Both are publisher-furniture (running header / corresponding-author),
    # not body prose.  Anchored on the affiliation core ("University of …"
    # + comma + place) so legitimate body sentences that mention a university
    # never match (body uses "the University of …" or "<U> researchers" —
    # neither starts the line bare-cap or ends with "City, Region").
    re.compile(
        r"^University\s+of\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?,\s+"
        r"[A-Z][A-Za-z]+(?:\s+[A-Z][\w\-]+)*,\s+[A-Z][\w\s]{1,40}\.?$"
    ),
    re.compile(
        r"^[A-Z][\w\-]+(?:\s+[A-Z][\w\-]+){0,3},\s+"
        r"Department\s+of\s+[A-Z][A-Za-z]+(?:\s+and\s+[A-Z][A-Za-z]+)?,\s+"
        r"University\s+of\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?,\s+"
        r".{2,80}\.?$"
    ),
    # v2.4.7: journal-footer URLs and volume markers that recur on every
    # page in Nature / Sci Rep / Royal Society OA journals — pdftotext
    # extracts them as standalone lines that leak into body prose.
    re.compile(r"^rsos\.royalsocietypublishing\.org\s*$"),
    re.compile(r"^www\.nature\.com/(?:naturecommunications|scientificreports)\s*$"),
    re.compile(r"^Vol\.:\(\d{10,}\)\s*$"),  # "Vol.:(0123456789)" Springer marker
    # v2.4.7: standalone ORCID URL lines.
    re.compile(r"^https?://orcid\.org/\d{4}-\d{4}-\d{4}-[0-9X]{4}\s*$"),
    # v2.4.8: Academy of Management copyright footer (recurs on every AOM
    # journal — AMC, AMD, AMJ, AMLE, AMP, Annals; 9 papers in corpus).
    re.compile(
        r"^Copyright\s+of\s+the\s+Academy\s+of\s+Management,.*rights\s+reserved\.?.*$",
        re.IGNORECASE,
    ),
    # v2.4.8: ARTICLE HISTORY title + date block (chan_feldman + xiao).
    # The block leaks as a single pdftotext line in T&F two-column layouts.
    re.compile(
        r"^ARTICLE\s+HISTORY\s+Received\s+\d{1,2}\s+\w+\s+\d{4}"
        r"(?:\s+Revised\s+\d{1,2}\s+\w+\s+\d{4})?"
        r"\s+Accepted\s+\d{1,2}\s+\w+\s+\d{4}\s*$"
    ),
    # v2.4.8: Standalone "Open Access" line that BMC / PMC journals stamp
    # at the top of each page. Bare two-word marker — anchored to top of
    # line, requires nothing else.
    re.compile(r"^Open\s+Access\s*$"),
    # v2.4.8: Elsevier (JESP, JEP) compound footer with DOI + dates +
    # copyright + "All rights reserved." on a single line. Distinctive
    # enough to anchor on `Received\s+\d{1,2}\s+\w+\s+\d{4};` near the
    # start.
    re.compile(
        r"^(?:https?://doi\.org/\S+\s+)?Received\s+\d{1,2}\s+\w+\s+\d{4};"
        r".*(?:©|All\s+rights\s+reserved\.?).*$"
    ),
    # B3 / D4 (2026-05-22): PLOS-template "a1111111111" page watermark.
    # PLOS journals stamp a row of ``a1111111111`` (one ``a`` followed by 8+
    # ``1`` digits) as a positional watermark on every page; pdftotext emits
    # it as a standalone line that leaks into body prose. No legitimate body
    # text matches this shape — anchored on the full literal.
    re.compile(r"^a1{8,}\s*$"),
    # B3 / D4 (2026-05-22): bare ``doi:`` or ``https?://doi.org/...`` footer
    # line standing alone on its own line. The DOI is part of the journal
    # footer template, not body content. ``doi:`` lower-case form (Wiley,
    # JAMA, Elsevier) and the URL form (PLOS, Frontiers, Springer) both
    # leak. Distinct from in-text DOI mentions which never appear alone.
    re.compile(r"^doi:\s*10\.\d{3,5}/\S+\s*$", re.IGNORECASE),
    re.compile(r"^https?://(?:dx\.)?doi\.org/10\.\d{3,5}/\S+\s*$", re.IGNORECASE),
    # B3 / D4 (2026-05-22): plural "E-mail addresses:" sidebar followed by
    # one or more comma/semicolon-joined emails. The existing
    # ``^E-?mail(?:s)?:\s*\S+@.+$`` matches the singular form
    # "E-mail: foo@bar"; this adds the plural form
    # "E-mail addresses: foo@bar, baz@qux".
    re.compile(
        r"^E-?mail\s+addresses?:\s*\S+@\S+(?:[\s,;]+\S+@\S+)*\s*$",
        re.IGNORECASE,
    ),
    # B3 / D4 (2026-05-22): publication-history line "Received DD Mon YYYY;
    # Accepted DD Mon YYYY[; Published DD Mon YYYY]" — semicolon-joined
    # dates as the masthead template. Distinct from the
    # ``^Received\s+\d{1,2}\s+\w+\s+\d{4}\s*$`` standalone-Received line
    # already above; this catches the chained form.
    re.compile(
        r"^Received[:]?\s+\d{1,2}\s+\w+\s+\d{4}\s*[;,]\s*"
        r"Accepted[:]?\s+\d{1,2}\s+\w+\s+\d{4}"
        r"(?:\s*[;,]\s*Published[:]?\s+\d{1,2}\s+\w+\s+\d{4})?\s*\.?\s*$",
        re.IGNORECASE,
    ),
    # v2.4.79: US-format publication-history line "Received Month DD, YYYY;
    # revision accepted Month DD, YYYY" (Sage / APA journals — PSPB,
    # ip_feldman). Distinct from the European "Received DD Month YYYY;
    # Accepted ..." forms above: this uses "Month DD, YYYY" order with a
    # comma, and the phrase "revision accepted" (not bare "Accepted"). The
    # date sub-pattern accepts either order (US "Month DD, YYYY" or European
    # "DD Month YYYY"); the "revision accepted" token plus a trailing year
    # makes this unmistakably journal boilerplate, never body prose.
    re.compile(
        r"^Received\s+(?:\w+\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+\w+\.?\s+\d{4})"
        r"\s*;\s*revision\s+accepted\s+"
        r"(?:\w+\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+\w+\.?\s+\d{4})\s*\.?\s*$",
        re.IGNORECASE,
    ),
    # B3 / D4 (2026-05-22): bare "N / M" or "N/M" page-furniture marker
    # (Frontiers, F1000, eLife render "3 / 14" on every page). Anchored to
    # 1-3 digit / 1-3 digit only — never matches in-text fractions like
    # "1/2" inside sentence prose because prose lines have other tokens.
    re.compile(r"^\d{1,3}\s*/\s*\d{1,3}\s*$"),
    # B3 / D4 (2026-05-22): standalone "Competing interests" / "Conflict of
    # interest" sidebar HEADER line (not the section heading itself —
    # standalone fragments mid-body, leaked from sidebar serialisation).
    # Must end with sentence terminator OR colon to distinguish from a
    # real heading the partitioner should consume.
    re.compile(
        r"^(?:Competing\s+[Ii]nterests?|Conflicts?\s+of\s+[Ii]nterest)"
        r"\s*[:.]\s*(?:None|The\s+author(?:s)?\s+declare).*$",
    ),
    # B3 / D4 (2026-05-22): "Abbreviations:" inline glossary sidebar that
    # leaks mid-page (PLOS / BMJ). Distinct from a "## Abbreviations"
    # section heading — this matches a line that starts with "Abbreviations:"
    # AND has content after the colon (the inline expansion list).
    re.compile(r"^Abbreviations:\s+\S.+$"),
]


# v2.4.8: garbled OCR headers — "ACK NOW L EDGEM EN TS", "DATA AVA IL A
# BILIT Y STATEM ENT" etc. (brjpsych_1 + similar). The pdftotext extraction
# collapses letter-spaced display text by inserting spaces between groups
# of letters; the resulting line is unintelligible but has a distinctive
# signature: ≥4 capital-letter clusters separated by single spaces, total
# alpha characters ≥ 12.
_GARBLED_OCR_HEADER_RE = re.compile(
    r"^(?:[A-Z]{1,4}\s+){3,}[A-Z]{1,4}(?:\s+[A-Z]{1,4}){0,8}\s*$"
)


def _rejoin_garbled_ocr_headers(text: str) -> str:
    """Re-knit letter-spaced display-typography headers.

    pdftotext renders display-typography acknowledgments / data-availability
    headers (where the PDF uses letter-spacing for emphasis) as:

        ACK NOW L EDGEM EN TS

    which is unparseable as either prose or a heading. This pass detects
    such lines (≥ 4 capital-letter clusters separated by single spaces) and
    collapses them by removing the spaces, recovering ``ACKNOWLEDGMENTS``.

    Conservative trigger: the entire line must consist of all-caps token
    groups separated by single spaces, with each token ≤ 4 chars and ≥ 4
    tokens. Real all-caps headings like ``CONCLUSIONS AND RELEVANCE`` have
    longer tokens (≥ 5 chars) and pass through unchanged.
    """
    if not text:
        return text
    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) < 12:
            continue
        if not _GARBLED_OCR_HEADER_RE.match(stripped):
            continue
        # Compact: remove all whitespace between caps.
        compact = re.sub(r"\s+", "", stripped)
        if len(compact) < 8:
            continue
        # Preserve leading whitespace; replace rest.
        lead = line[: len(line) - len(line.lstrip())]
        lines[i] = lead + compact
    return "\n".join(lines)


# v2.4.33 (NORMALIZATION_VERSION 1.9.1): lowercase letter-spaced display
# labels. Elsevier-family journals (e.g. JESP 2009-era FlashReports) letter-
# space the front-matter box labels "article info" and "abstract" for
# typographic emphasis. pdftotext serializes each as a run of single
# lowercase characters separated by single spaces, one label per line:
#       a r t i c l e
#       i n f o
#       a b s t r a c t
# The all-caps sibling _rejoin_garbled_ocr_headers does not fire (its regex
# requires capital-letter clusters). Left uncollapsed, "a b s t r a c t" is
# never recognised by the section taxonomy, so the Abstract section heading
# is lost on every paper with this typography. This pass collapses such
# lines; the recovered "abstract" then resolves through the normal section
# taxonomy ({"abstract"} -> SectionLabel.abstract) exactly like a paper that
# printed the label without letter-spacing.
_LETTERSPACED_LABEL_RE = re.compile(r"^(?:[a-z] ){3,}[a-z]$")


def _rejoin_letterspaced_lowercase_labels(text: str) -> str:
    """H0b: collapse lowercase letter-spaced display labels (Elsevier).

    Sibling of _rejoin_garbled_ocr_headers (which handles the all-caps
    variant at render time); this lowercase variant must run pre-sectioning
    so a recovered "abstract" label can be promoted to the Abstract heading.

    Conservative trigger: the ENTIRE line must be >=4 single lowercase
    letters separated by single spaces, and the collapsed form must contain
    a vowel (rejects spaced-out consonant runs / variable lists).
    """
    if not text:
        return text
    lines = text.split("\n")
    changed = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or not _LETTERSPACED_LABEL_RE.match(stripped):
            continue
        compact = stripped.replace(" ", "")
        if not any(v in compact for v in "aeiou"):
            continue
        lead = line[: len(line) - len(line.lstrip())]
        lines[i] = lead + compact
        changed = True
    return "\n".join(lines) if changed else text


# Cycle 9b (v2.4.61) / 14 (v2.4.66) — context discriminator used by S9
# Pattern A to protect table sample-size values from being stripped as
# page numbers. Cycle 14 added `<>=%` so lines like `<.001` (p-value),
# `S<= 10000`, `>= 0.05` are detected as table-cell content, not prose.
_NUMERIC_ONLY_LINE_RE = re.compile(r"^[\d\s.,()+\-*∗;:<>=%]+$")

# Cycle 15 (v2.4.67) — extends numeric-block detection to LABELED numeric
# lines like `S<= 10000`, `M = 5.2`, `N = 200`, `t = -1.4`. These are
# table-cell or figure-axis content that pdftotext emits with a 1-4-char
# stat-variable prefix. Without this signature the line above a stripped
# 4-digit value (e.g. `1000` in nat-comms-2 figure axis below `S<= 10000`)
# fails the _is_in_numeric_block check and the value is stripped as a page
# number → real text loss.
_LABELED_NUMERIC_LINE_RE = re.compile(
    r"^[A-Za-zβμσπτλωαδ²]{1,4}\s*[<=>≤≥]+\s*[\d.,()+\-*∗;:<>=%\s]+$"
)

# Cycle 15 (v2.4.67) — parenthesized year / year-range. Used by S9 to
# protect table source-attribution captions (`(2003-2023)`, `(2024)`)
# from being false-stripped as running-header boilerplate.
_LINE_HAS_YEAR_PARENS_RE = re.compile(r"\((?:19|20)\d{2}(?:\s*[-–]\s*(?:19|20)\d{2})?\)")


def _is_numeric_only_line(line: str) -> bool:
    """True if the (stripped) line contains only digits + common stat-table
    punctuation (decimal point, comma, parens, asterisks/sig-stars, minus,
    plus, semicolon, colon, whitespace) AND has at least one digit. Used as
    a "this line is a table cell, not prose" signal."""
    s = line.strip()
    if not s:
        return False
    if not _NUMERIC_ONLY_LINE_RE.match(s):
        return False
    return any(c.isdigit() for c in s)


def _is_in_numeric_block(lines: list[str], idx: int) -> bool:
    """True if the line at ``idx`` sits in a vertical block of numeric-only
    (or labeled-numeric) lines — its nearest non-blank neighbor above OR
    below is itself numeric-only or labeled-numeric. Used by S9 to
    distinguish per-page markers (isolated in prose) from table cells or
    figure-axis values (in a column of other numeric values).

    Cycle 15 (v2.4.67): accept labeled-numeric neighbors (e.g. `S<= 10000`,
    `M = 5.2`) — these are stat-variable comparisons that pdftotext emits
    above/below figure-axis values, and treating them as prose caused
    figure tick labels to be stripped as page numbers (nat-comms-2 `1000`).
    """
    for direction in (-1, +1):
        i = idx + direction
        while 0 <= i < len(lines) and not lines[i].strip():
            i += direction
        if 0 <= i < len(lines):
            neighbor = lines[i].strip()
            if _is_numeric_only_line(neighbor):
                return True
            if _LABELED_NUMERIC_LINE_RE.match(neighbor) and any(
                c.isdigit() for c in neighbor
            ):
                return True
    return False


# 2026-08-05 (run 6, cycle 1): words that follow a line-initial `CONTACT` in
# navigation / heading furniture rather than in a correspondence footer. The
# wrapped-CONTACT pattern above matches "CONTACT <Titlecase> <Titlecase>",
# which "CONTACT Details Below" / "CONTACT Author Details" / "CONTACT Support
# Team" also satisfy. Vetoing on the WORD (not on the paper) keeps the strip
# keyed to a personal name.
_CONTACT_NON_NAME_WORDS = re.compile(
    r"\b(?:Details?|Information|Info|Us|Page|Form|Address|Below|Here"
    r"|Author|Authors|Editor|Team|Support|Details)\b",
    re.IGNORECASE,
)

# The wrapped-CONTACT opener, identified so the region-tail sweep below can
# find it without re-matching every pattern in the list.
_WRAPPED_CONTACT_OPENER = re.compile(
    r"^CONTACT\s+"
    r"(?:[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ][\w'’\-]*|[A-ZÀ-ÖØ-Þ]\.?)"
    r"(?:[\s'’\-]+(?:[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ][\w'’\-]*|[A-ZÀ-ÖØ-Þ]\.?)){1,3}"
    r"\s*$"
)

# The orphaned "<City>, <Region>" tail that follows a wrapped correspondence
# opener once the email / affiliation lines have been dropped. Deliberately
# NOT keyed on place names — a bare "Hong Kong, Hong Kong SAR" is a plausible
# prose fragment, so this only fires on a line ADJACENT to a dropped
# wrapped-CONTACT opener (see `_strip_page_footer_lines`). Comma-separated
# Titlecase place tokens, no sentence punctuation, short.
_CONTACT_REGION_TAIL = re.compile(
    r"^[A-ZÀ-ÖØ-Þ][\w'’\-]*(?:\s+[A-ZÀ-ÖØ-Þ]?[\w'’\-]+){0,3}"
    r",\s*[A-ZÀ-ÖØ-Þ][\w'’\-]*(?:\s+[\w'’\-]+){0,3}\.?\s*$"
)


def _strip_page_footer_lines(text: str) -> str:
    """P0: drop page-footer / running-header lines anywhere in the document.

    Curated patterns only. Line is dropped on explicit match; everything else
    is preserved. CHEAP variant of F1 — does not stitch sentence halves that
    spanned the page break, just removes the junk between them.

    2026-08-05 (run 6, cycle 1): additionally sweeps the orphaned region tail
    that follows a WRAPPED contact opener. The tail is only removed when it
    is adjacent (allowing already-dropped lines in between) to a
    wrapped-CONTACT opener this same pass removed — never on its own shape,
    because "<City>, <Region>" is an ordinary prose fragment.
    """
    if not text:
        return text
    out_lines: list[str] = []
    dropped_any = False
    # True while walking the run of furniture lines that begins at a wrapped
    # CONTACT opener; reset by the first line that is kept.
    in_wrapped_contact = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and _WRAPPED_CONTACT_OPENER.match(stripped):
            if _CONTACT_NON_NAME_WORDS.search(stripped):
                # nav / heading furniture, not a correspondence footer
                in_wrapped_contact = False
                out_lines.append(line)
                continue
            dropped_any = True
            in_wrapped_contact = True
            continue
        if stripped and any(
            p.match(stripped) for p in _PAGE_FOOTER_LINE_PATTERNS
        ):
            dropped_any = True
            continue
        if in_wrapped_contact:
            if not stripped:
                # blank line inside the block — keep scanning, don't emit
                continue
            if _CONTACT_REGION_TAIL.match(stripped):
                dropped_any = True
                continue
            # first real line after the block: the block is over
            in_wrapped_contact = False
        out_lines.append(line)
    if not dropped_any:
        return text
    cleaned = "\n".join(out_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# ── P0r (v2.4.70 / NORMALIZATION_VERSION 1.9.22) ────────────────────────
# Repetition-driven running-header / page-footer strip.
#
# `_strip_page_footer_lines` (P0 above) handles publisher-specific patterns
# we've curated by hand. But there's a long tail of running-header / page-
# footer shapes that aren't worth a hand-curated pattern each, yet share a
# common structural signature: a short line that repeats ≥3 times across
# the pdftotext serialization, AND looks like a journal banner / author-
# pair running head / DOI-and-date page footer (NOT like body prose, NOT
# like a table cell).
#
# Established 2026-05-23 cycle 2 after the end-to-end iterate-loop test
# surfaced these specific defects on the docpluck canary:
#
# - ip_feldman_2025_pspb: "Ip and Feldman" running header appearing
#   7 times standalone PLUS welded into a Discussion sentence at
#   line 2612 ("Ip and Feldman events (Srivastava et al., 2009) yet
#   are less able …") and into a LeBel et al. reference at line 2699.
#   Also "Personality and Social Psychology Bulletin 00(0)" footer
#   (issue-proof placeholder) repeating 8 times.
# - plos_med_1: "PLOS Medicine | https://doi.org/10.1371/journal.pmed.1004323
#   December 28, 2023" footer × 16 + "PLOS MEDICINE" banner × 15.
# - chan_feldman_2025_cogemo: "COGNITION AND EMOTION" banner × 12 +
#   "C. F. CHAN AND G. FELDMAN" running header × 11, including injection
#   INTO Table 2 thead cell at line 261 and Table 5 thead at line 596.
#
# The structural signatures (see `_looks_like_running_header_or_footer`):
#   A. All-caps multi-word journal banner ("PLOS MEDICINE", "COGNITION
#      AND EMOTION", "JAMA NETWORK OPEN") — ≥2 ASCII-uppercase words.
#   B. All-caps author-pair with initials and AND — "C. F. CHAN AND G.
#      FELDMAN" (and the page-numbered variant "1234 C. F. …").
#   C. Mixed-case bare author-pair — "Ip and Feldman", "Smith & Jones".
#   D. Journal name + `|` separator + DOI URL + date — the PLOS footer.
#   E. Journal name + issue-proof placeholder `NN(N)` / `00(0)` — the
#      PSPB pre-print/proof header.
#
# Critical safeguards:
#   1. The line MUST repeat ≥3 times standalone (the de-facto guard
#      against false-positive on body prose or table cells — neither
#      repeats this often, while running headers/footers always do).
#   2. The line must match one of the 5 content shapes — bare repetition
#      alone is not enough (table cells can repeat 4+ times: "0/4 (0.0%)",
#      "PSA", "<.001"; these must NOT be stripped).
#   3. When a body line STARTS with a detected running-header string
#      followed by space/period/comma, the running-header prefix is
#      stripped (the welded-into-sentence variant — but ONLY when the
#      header itself was independently detected via ≥3 standalone
#      repetitions, so a real surname sentence ("Smith and Jones (2009)
#      showed …") is not at risk unless the doc actually contains a
#      "Smith and Jones" running header.

# Author-pair patterns (recognised as ≥3-standalone candidates):
_AUTHOR_PAIR_ALL_CAPS_AND = re.compile(
    r"^(?:\d{1,4}\s+)?"                        # optional leading page number
    r"(?:[A-Z]\.\s*)*[A-Z]{2,}"                # author1: optional initials + ALL-CAPS surname
    r"(?:\s+[A-Z]\.)*"                          # optional trailing initial(s) of author1
    r"\s+AND\s+"
    r"(?:[A-Z]\.\s*)*[A-Z]{2,}"                # author2: same shape
    r"(?:\s+[A-Z]\.)*"
    r"\s*$"
)
_AUTHOR_PAIR_MIXED_CASE_AND = re.compile(
    r"^[A-Z][a-z]{1,25}"                       # author1 surname (Title-case)
    r"(?:\s+and\s+|\s+&\s+)"
    r"[A-Z][a-z]{1,25}"                        # author2 surname
    r"\s*$"
)
# Journal-DOI-date page footer (e.g. "PLOS Medicine | https://doi.org/... <date>").
# 2026-05-25 fix: pdftotext column-wraps the date suffix on PLOS Medicine layouts —
# the actual rendered line is `PLOS Medicine | https://doi.org/<doi> Dec` (3-letter
# month only, day+year wrapped to next line).  Original regex required a complete
# `<month> <day>, <year>` tail and missed the wrapped form on every plos_med_1 page
# (test_plos_med_1_no_fence_footer was failing at HEAD).  Relaxed so the date suffix
# is OPTIONAL — the journal+pipe+DOI structure alone is publisher-furniture and
# can't appear in body prose.  Conservative because (a) the `^.{3,60}\|` anchor +
# DOI URL is a tight typographic signature, (b) the 3-60 char journal-name length
# range excludes long body sentences, (c) DOI URLs in body prose appear in
# `(<URL>)` parentheses or as full sentences, never at the start of a line with
# a pipe separator.
_JOURNAL_DOI_DATE_FOOTER = re.compile(
    r"^.{3,60}\|\s*https?://doi\.org/\S+"
    r"(?:\s+\S+(?:\s+\d{1,2},?\s*\d{4})?)?"
    r"\s*$"
)
# Companion: orphan date-tail line ("Dec 28, 2023" / "December 28, 2023" /
# "28, 2023") that appears AFTER a journal-DOI footer line when pdftotext
# wrapped the date.  Matches only when paragraph-isolated (the surrounding
# stripper checks the prev/next context).
_JOURNAL_DATE_TAIL_ORPHAN = re.compile(
    r"^(?:\d{1,2}\s*,\s*\d{4}"
    r"|[A-Z][a-z]{2,8}\s+\d{1,2}\s*,\s*\d{4})\s*$"
)
# Journal banner / journal + issue-proof placeholder:
_JOURNAL_PROOF_HEADER = re.compile(
    r"^[A-Z][A-Za-z][A-Za-z &\-]{4,60}\s+\d{1,3}\(\d{1,3}\)\s*$"
)
# v2.4.81 (2026-06-08 untested-corpus sweep): Elsevier / ScienceDirect running
# footer — "<Journal Name> <Vol> (<Year>) <ArticleNo>", e.g.
# "Journal of Experimental Social Psychology 96 (2021) 104154" (leaked ×20 on
# j.jesp.2021.104154). Also the author-prefixed variant
# "<Author> et al. / <Journal> <Vol> (<Year>) <ArtNo>". Distinct from a
# reference-list entry: the journal name spans only [A-Za-z&-:' ] (no comma /
# period), so it cannot match the comma-separated author list of a citation;
# and the "(YYYY)" parenthetical sits AFTER the volume (footer form) rather than
# after the authors (APA reference form). Paired with the ≥3-repetition guard in
# _detect_recurring_running_headers, this only ever fires on the page footer.
_ELSEVIER_JOURNAL_VOL_FOOTER = re.compile(
    r"^(?:.{2,45}\s+/\s+)?"                       # optional "<author> et al. / " prefix
    r"[A-Z][A-Za-z][A-Za-z&\-:' ]{5,70}"          # journal name (title-case words)
    r"\s+\d{1,4}\s+\(\d{4}\)\s+"                   # volume + (year)
    r"(?:\d{1,7}|\d{1,5}\s*[–-]\s*\d{1,5})"   # article number OR page range
    r"\s*$"
)
# v2.4.81: Nature-family running footer — "<Journal Name> | (<Year>)<Vol>:<ArtNo>",
# e.g. "Nature Communications | (2023)14:8487" (leaked ×15 on s41467). The
# existing _JOURNAL_DOI_DATE_FOOTER requires "| https://doi.org/..."; this is the
# pipe-issue variant with no DOI URL. Tight signature: journal + pipe + a
# "(YYYY)NN:NNNN" issue token that body prose never produces.
_JOURNAL_PIPE_ISSUE_FOOTER = re.compile(
    r"^[A-Z][A-Za-z][A-Za-z&\-:' ]{1,50}"         # journal name
    r"\s*\|\s*"                                    # pipe separator
    r"\(\d{4}\)\d{1,4}:\d{1,7}"                    # (year)vol:artno
    r"(?:\s*\|\s*\S.*)?"                            # optional trailing " | <doi/extra>"
    r"\s*$"
)
# v2.4.83 (2026-06-08): bare author running-header — "<Initials> <Surname> et al.",
# e.g. "J. Chen et al." (leaked ×13 standalone on j.jesp.2021.104154). Elsevier's
# full running header "J. Chen et al. / <Journal> <Vol> (<Year>) <ArtNo>" is split
# by pdftotext across two lines; _ELSEVIER_JOURNAL_VOL_FOOTER strips the journal
# half, leaving the bare author half as its own line. This is unambiguously page
# furniture, NOT body text, given the ≥3-standalone-repetition guard in
# _detect_recurring_running_headers: an in-text citation is never a standalone
# WHOLE line, and an APA reference entry is "Surname, Initial." (comma after the
# surname) — the inverse of this "Initial. Surname" order. Requiring a LEADING
# initial + a trailing "et al." with nothing else on the line keeps it tight.
_AUTHOR_ETAL_INITIAL = re.compile(
    r"^(?:[A-Z]\.[-\s]*){1,4}"                    # leading initials: "J. " / "J. K. " / "M.-J. "
    r"(?:(?:van|von|de|der|den|di|del|della|du|la|le|el|bin|ben|da|dos)\s+){0,2}"  # optional surname particles
    r"[A-ZÀ-Þ][\w'’\-]+"                          # Title-Case surname (Latin-Extended, hyphen/apostrophe)
    r"\s+et\s+al\.?\s*$",                          # "et al." (optional period), end of line
    re.UNICODE,
)


# D2 (citationguard-iterate 2026-06-12): single-word / short category-label
# running headers. Nature-family and many journals print the article-type label
# ("Article", "Review", "Letter", "Matters Arising", …) at the top of every page.
# H0 already curates these in _HEADER_BANNER_PATTERNS, but H0 only fires in the
# document-header zone (first 30 lines); when the label recurs mid-document — e.g.
# inside the References section at a page break — it survives and gets welded into
# an entry ("…EAE based on\n\n\x0cArticle histology…" orphaned ref 34's year on
# nat_comms_2). Stripping it here is gated by the ≥3-standalone-repetition guard in
# _detect_recurring_running_headers, so a one-off body occurrence is never touched.
# Scoped to genuine publisher article-type furniture; bare common words ("Research",
# "Comment") are excluded to avoid colliding with section-heading body lines.
_CATEGORY_LABEL_HEADER = re.compile(
    r"^(?:"
    r"Article|ARTICLE|Articles"
    r"|Review|Reviews|REVIEW"
    r"|Letter|Letters|LETTER"
    r"|Resource|Resources"
    r"|Analysis|Perspective|Perspectives"
    r"|Correspondence|Editorial"
    r"|Brief\s+Communication|Matters\s+Arising"
    r"|Original\s+(?:Investigation|Article|Research)"
    r"|Research\s+(?:Article|Paper|Letter|Report)"
    r")$"
)


def _is_all_caps_journal_banner(line: str) -> bool:
    """All-caps multi-word journal banner: e.g. ``PLOS MEDICINE``,
    ``COGNITION AND EMOTION``, ``JAMA NETWORK OPEN``.

    Rules:
    - Length ≥ 7 chars (PSA, ECG etc. with 1-3 letters are excluded — too
      common as table cell labels).
    - Contains a space (≥2 words; AND / & count as words).
    - Letters are ASCII A-Z only; allow spaces, ``&``, ``-``, ``.``.
    - At least one alphabetic character.
    - No digits, no commas, no parentheses (excludes table column headers
      like ``OR [95% CI]`` and ``PSA, N=98``).
    """
    if len(line) < 7:
        return False
    if " " not in line:
        return False
    if not any(c.isalpha() for c in line):
        return False
    for c in line:
        if c.isalpha():
            if not ("A" <= c <= "Z"):
                return False
        elif c not in " &-.":
            return False
    # Reject if there are only 1 alphabetic words (avoid "PSA  " etc.)
    words = [w for w in line.split() if w]
    if len(words) < 2:
        return False
    return True


def _looks_like_running_header_or_footer(line: str) -> bool:
    """Return True if the line shape matches one of the P0r running-header /
    page-footer signatures.

    Used as a content guard on top of the ≥3-standalone-repetition guard.
    Together they keep the strip from touching table cells (which repeat
    but don't match these shapes) and body prose (which neither repeats
    nor matches).
    """
    if not line or len(line) > 100:
        return False
    if _CATEGORY_LABEL_HEADER.match(line):
        return True
    if _is_all_caps_journal_banner(line):
        return True
    if _AUTHOR_PAIR_ALL_CAPS_AND.match(line):
        return True
    if _AUTHOR_PAIR_MIXED_CASE_AND.match(line):
        return True
    if _JOURNAL_DOI_DATE_FOOTER.match(line):
        return True
    if _JOURNAL_PROOF_HEADER.match(line):
        return True
    if _ELSEVIER_JOURNAL_VOL_FOOTER.match(line):
        return True
    if _JOURNAL_PIPE_ISSUE_FOOTER.match(line):
        return True
    if _AUTHOR_ETAL_INITIAL.match(line):
        return True
    return False


def _detect_recurring_running_headers(text: str) -> set[str]:
    """Identify lines that (a) repeat ≥3 times standalone AND (b) match a
    running-header / page-footer shape (per ``_looks_like_running_header
    _or_footer``). Returns the set of header strings to strip."""
    counts: dict[str, int] = {}
    for line in text.split("\n"):
        s = line.strip()
        if 3 <= len(s) <= 100:
            counts[s] = counts.get(s, 0) + 1
    return {
        line for line, n in counts.items()
        if n >= 3 and _looks_like_running_header_or_footer(line)
    }


def _strip_recurring_running_headers(text: str) -> str:
    """P0r: drop running-header / page-footer lines that repeat ≥3 times
    AND match one of the 5 shape patterns. Also strip them as a LEADING
    prefix on body lines (the welded-into-sentence variant)."""
    if not text:
        return text
    headers = _detect_recurring_running_headers(text)
    if not headers:
        return text
    # Sort by length descending so longer headers are matched first when
    # prefix-stripping (avoids "Smith" matching before "Smith and Jones").
    headers_by_len = sorted(headers, key=len, reverse=True)
    out_lines: list[str] = []
    for line in text.split("\n"):
        s = line.strip()
        if s in headers:
            continue  # standalone occurrence — drop
        # Welded case: the body line begins with the running header followed
        # by whitespace or punctuation. Strip the prefix so the body sentence
        # survives without the header injection.
        stripped = line
        for h in headers_by_len:
            # Match if line.lstrip() starts with h + (space|.|,) at the
            # word boundary. We compare on the lstripped form to ignore
            # leading whitespace that pdftotext may have inserted.
            ls = stripped.lstrip()
            if ls == h:
                stripped = ""
                break
            if (
                ls.startswith(h + " ")
                or ls.startswith(h + ".")
                or ls.startswith(h + ",")
            ):
                # Preserve the indent prefix, strip the welded header.
                indent = stripped[: len(stripped) - len(ls)]
                rest = ls[len(h):].lstrip(" .,")
                stripped = indent + rest
                break
            # 2026-05-25 wrapup: truncated-prefix case (R4 column-aware
            # extraction sometimes crops a page footer mid-token, leaving
            # e.g. ``PLOS Medicine | https://doi.org/10.1371/journal.pmed.
            # 1004323 Dec`` instead of the canonical ``... December 28, 2023``
            # form). The truncated form appears once, the full form ≥3 times,
            # so P0r's repetition detector catches the full but lets the
            # truncated survive. Strip when the line is a prefix of a known
            # header AND is at least 30 chars (avoids false positives on
            # short shared prefixes).
            if len(ls) >= 30 and h.startswith(ls):
                stripped = ""
                break
        out_lines.append(stripped)
    cleaned = "\n".join(out_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# ── P1 (v2.4.16 / NORMALIZATION_VERSION 1.8.4) ──────────────────────────
# Front-matter metadata-leak paragraph strip.
#
# pdftotext's reading-order serialization linearizes a two-column article by
# emitting the article's left-column (Abstract → Introduction body) and then
# the right-column / inter-column metadata (corresponding-author block,
# acknowledgments footnote, supplemental-data sidebar, "A previous version
# of this article was presented…" note, IEEE/CC license blob, running
# headers like "RECKELL et al."). Those metadata fragments end up as
# standalone single-line paragraphs INLINED between body paragraphs of the
# Introduction — visible to a human reader but invisible to char-ratio /
# Jaccard verifiers (the tokens are present, just in the wrong section).
#
# Confirmed leak instances at v2.4.15 (broad-read 2026-05-13):
#   xiao_2021_crsp (APA / T&F): "Supplemental data for this article…",
#       "Department of Psychology, University of" (truncated affiliation).
#   amj_1 (AOM):                "We wish to thank our editor Jill Perry-Smith
#       and three anonymous reviewers… Correspondence concerning this article
#       should be addressed to…" (one long pdftotext-serialized line).
#   amle_1 (AOM):               "We thank Steven Charlier… reviewers for
#       offering highly constructive feedback…", "A previous version of this
#       article was presented at the Management Education and Development…".
#   ieee_access_2 (IEEE):       "This work is licensed under a Creative
#       Commons Attribution 4.0 License… CONFLICT OF INTEREST…",
#       "RECKELL et al." (bare running header).
#
# Strategy: paragraph-level strip (\n\n-bounded) with two safety gates:
#   1. Pattern must match the START of the paragraph — anchored, not
#      free-floating.
#   2. Position gate: paragraph must begin in the first ``max(8000,
#      len(text) // 6)`` characters of the document. This protects the
#      legitimate Acknowledgments / Funding / Affiliations sections that
#      live at the end (e.g. xiao's `## Acknowledgments / We thank Siu Kit
#      Yeung…` at ~25% of doc, amle_1's affiliations block at ~90%).
#
# Two pattern groups:
#   - ``_FRONTMATTER_LEAK_PARA_PATTERNS`` — multi-sentence acknowledgments
#     / previous-version / license blocks. Anchored on a distinctive
#     opening phrase. The pattern allows the paragraph to be of any length
#     up to ``_FRONTMATTER_LEAK_MAX_PARA_CHARS``.
#   - ``_FRONTMATTER_LEAK_LINE_PATTERNS`` — short single-line orphan
#     fragments (running headers, truncated affiliations, supplemental-
#     data sidebars). These are ultra-specific patterns that match a full
#     bounded line.
_FRONTMATTER_LEAK_MAX_PARA_CHARS = 1500

_FRONTMATTER_LEAK_PARA_PATTERNS: list[re.Pattern[str]] = [
    # Acknowledgments footnote serialized as a paragraph:
    #   "We wish to thank our editor Jill Perry-Smith and three anonymous
    #    reviewers for their insightful and constructive feedback. We also
    #    thank Angelo DeNisi, Matthew Feinberg…"
    # Anchor: starts with "We thank" or "We wish to thank" AND the
    # paragraph contains at least one of (reviewers|editor|feedback|
    # comments|suggestions|insights|helpful) within the first 300 chars.
    # The keyword guard rejects body prose that legitimately starts with
    # "We thank participants for…".
    re.compile(
        r"^We\s+(?:wish\s+to\s+)?thank\s+[A-Z].{0,300}?\b"
        r"(?:reviewers?|editor|feedback|comments?|suggestions?|insights?|helpful)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    # "A previous version of this article was presented/published at…"
    # (AOM, T&F, Sage — anywhere a conference / proceedings note leaks).
    re.compile(
        r"^A\s+previous\s+version\s+of\s+this\s+article\s+was\s+"
        r"(?:presented|published)\b",
        re.IGNORECASE,
    ),
    # IEEE / Creative Commons license block. The full block typically chains
    # "This work is licensed under… Corresponding author: <name>… CONFLICT
    # OF INTEREST…". Anchoring on the opening is enough.
    re.compile(
        r"^This\s+work\s+is\s+licensed\s+under\s+(?:a\s+|the\s+)?"
        r"Creative\s+Commons\b",
        re.IGNORECASE,
    ),
    # APA-style standalone corresponding-author paragraph (when not already
    # caught by P0's "CONTACT <name>" single-line rule because the
    # serialization put it on its own bounded paragraph rather than a one-
    # line "Corresponding Author:" header).
    re.compile(
        r"^Correspondence\s+concerning\s+this\s+article\s+should\s+be\s+"
        r"addressed\s+to\b",
        re.IGNORECASE,
    ),
    # 2026-05-25 (Cluster C, ip_feldman finding #1): name-led corresponding-
    # author paragraph emitted by Sage / PSPB style when pdftotext serialises
    # the front-matter into a body-zone paragraph.  Shape:
    #   "<First> <Last>, Department of <Field>, University of <Place>,
    #    <City>, <Region>."
    # Spans multiple wrapped lines (\s+ matches the embedded `\n`).
    # Position-gated to front-matter (first 8000 chars), so legitimate
    # late-doc author-bio paragraphs are preserved.  Anchored on the
    # Name-comma + "Department of" + "University of" + comma-comma tail —
    # not by name identity, by furniture shape.
    re.compile(
        r"^[A-Z][\w\-]+(?:\s+[A-Z][\w\-]+){0,3},\s+"
        r"Department\s+of\s+[A-Z][A-Za-z]+(?:\s+(?:and|of)\s+[A-Z][A-Za-z]+)?,\s+"
        r"University\s+of\s+[A-Z][\w\s]+,\s+[A-Z][\w\s]+,\s+[A-Z][\w\s]+\.?\s*$",
        re.DOTALL,
    ),
]

# Note: the three "globally safe" LINE patterns originally drafted here
# (Supplemental-data sidebar, truncated affiliation, bare uppercase running
# header) were promoted into P0's ``_PAGE_FOOTER_LINE_PATTERNS`` in
# v2.4.16 once it became clear that the running-header variant recurs at
# every page break (e.g. ieee_access_2 emits ``RECKELL et al.`` between
# Abstract / Introduction AND again at ~18% of the doc, past P1's position
# gate). P0 is the correct home for those patterns — they have zero
# false-positive risk in the body. P1 keeps only the multi-sentence
# paragraph-level patterns that DO carry false-positive risk in the late
# Acknowledgments section and need the position gate.
#
# 2026-05-26 (Cluster C-bis, ip_feldman finding #1 wrap-tail residual):
# pdftotext sometimes serialises a corresponding-author paragraph across
# multiple wrapped lines because the source PDF column wraps after a
# Place-Region phrase. Example from PSPB / Sage layout:
#     line N:    "Gilad Feldman, Department of Psychology, University of Hong Kong, Pok"
#     line N+1:  "Fu Lam, Hong Kong SAR."
# The Cluster C name-led pattern in ``_FRONTMATTER_LEAK_PARA_PATTERNS``
# matches the first line (anchored on "Department of" + "University of"
# furniture), but the wrap-tail second line survives because no line-level
# pattern matched it — line-by-line iteration in
# ``_strip_frontmatter_metadata_leaks`` can't see across the line boundary.
#
# This pattern matches the orphan wrap-tail shape: 1-3 title-case place
# tokens separated by commas, optionally with an all-caps region code (SAR,
# USA, U.K.) or a state-code + zip (MA 02138), ending in a period. The
# leading ``(?=.{1,60}$)`` lookahead bounds the whole line to 60 chars so
# legitimate body sentences that happen to end with a Place, Region phrase
# (typically much longer than 60 chars) are not absorbed.
#
# Position-gated to front-matter (first 8000 chars) by the outer strip
# function — citations in References and figure captions in body are
# preserved.
_ORPHAN_AFFIL_WRAP_TAIL = re.compile(
    r"^"
    r"(?=.{1,60}$)"                                   # whole line ≤ 60 chars
    r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}"             # first place token: 1-3 title-case words
    r",\s+"                                            # comma + space
    r"(?:"
        r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\s+[A-Z]{2,5}"   # title-case + all-caps region (Hong Kong SAR)
        r"|"
        r"[A-Z]{2,5}(?:\s+\d{4,5}(?:-\d{4})?)?"               # all-caps + optional zip (CA, MA 02138)
        r"|"
        r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}"                 # title-case only (Atlanta, Georgia)
    r")"
    r"\.\s*$"                                          # required period
)

# 2026-06-06 (Cluster E re-land after cycle 4 revert): the article-ID +
# article-type-code patterns were drafted in run 11 cycle 4 and reverted
# because their landing exposed a wrapped-title-duplicate previously
# absorbed by those very metadata lines (pdftotext serialises the title
# twice on PSPB layouts). Re-landed here because: (a) Cluster A-ter
# (render.py _is_subsection_chain_member + `# ` H1 reject prev-check)
# now structurally rejects the wrapped-title-duplicate's promotion to
# `### `, removing the side-effect that motivated the revert; and (b)
# the canary smoke at HEAD 31fb646 confirms the leak is the #1 finding
# on ip_feldman (METADATA-LEAK @ lines 1-17). Per LEAVE NOTHING BEHIND,
# leaving a known-fix-shape reverted in code is itself a defect.
#
# Pattern safety:
# - `_ARTICLE_TYPE_CODE` requires a hyphenated suffix-with-year
#   (`research-article2025`); single-token body words like `editorial2020`
#   are explicitly NOT matched (regression-tested).
# - `_BARE_ARTICLE_ID` is position-gated to the front-matter zone by the
#   existing _strip_frontmatter_metadata_leaks (first 8000 chars). A
#   standalone 6–8 digit line in body prose is genuinely rare and is
#   preserved by the position gate; in front-matter it is always a
#   publisher article ID (last segment of DOI repeated alone).
_ARTICLE_TYPE_CODE = re.compile(
    r"^(?:research|review|opinion|original|brief|invited|short|case|"
    r"editorial|letter|commentary|perspective|practice|empirical|"
    r"systematic-review|meta-analysis)-(?:article|report|review|"
    r"communication|note|paper|study)\d{4}\s*$",
    re.IGNORECASE,
)
_BARE_ARTICLE_ID = re.compile(r"^\d{6,8}\s*$")

_FRONTMATTER_LEAK_LINE_PATTERNS: list[re.Pattern[str]] = [
    _ORPHAN_AFFIL_WRAP_TAIL,
    _ARTICLE_TYPE_CODE,
    _BARE_ARTICLE_ID,
]


def _strip_frontmatter_metadata_leaks(text: str) -> str:
    """P1: strip orphan front-matter metadata lines.

    Targets standalone single-line paragraphs that pdftotext serializes
    mid-Introduction via right-column reading order:
      - acknowledgments footnote on one long line ("We wish to thank …
        reviewers …")
      - "A previous version of this article was presented at …" note
      - IEEE / Creative Commons license blob
      - "Correspondence concerning this article should be addressed to …"
      - "Supplemental data for this article can be accessed here."
      - Truncated affiliation ending at "University of" (no place name)
      - Bare "RECKELL et al." style running header

    Operates at the LINE level (not paragraph level) because pdftotext often
    emits the leak with only a single ``\\n`` separator from the body
    paragraph above it — the paragraph-level (``\\n\\n``-bounded) view
    would absorb the leak into the body paragraph and miss it.

    Position-gated to the first ``max(8000, len(text) // 6)`` characters of
    the document so the legitimate Acknowledgments / Funding /
    Affiliations sections at the END are preserved unchanged.

    Cross-paper coverage (confirmed at v2.4.15): xiao_2021_crsp, amj_1,
    amle_1, ieee_access_2. See LESSONS / NORMALIZATION_VERSION 1.8.4
    history for the discovery context.
    """
    if not text or len(text) < 200:
        return text

    cutoff = max(8000, len(text) // 6)
    # Snap the cutoff to a line boundary so we don't bisect a line.
    nl = text.rfind("\n", 0, cutoff)
    split = (nl + 1) if nl != -1 else cutoff
    front, back = text[:split], text[split:]

    out_lines: list[str] = []
    dropped = False
    for line in front.split("\n"):
        stripped = line.strip()
        if not stripped:
            out_lines.append(line)
            continue
        if len(stripped) > _FRONTMATTER_LEAK_MAX_PARA_CHARS:
            out_lines.append(line)
            continue
        matched = (
            any(p.match(stripped) for p in _FRONTMATTER_LEAK_LINE_PATTERNS)
            or any(p.match(stripped) for p in _FRONTMATTER_LEAK_PARA_PATTERNS)
        )
        if matched:
            dropped = True
            continue
        out_lines.append(line)

    if not dropped:
        return text

    cleaned = "\n".join(out_lines) + back
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# v2.4.20 (NORMALIZATION_VERSION 1.8.7): rejoin pdftotext-space-broken
# compound words.
#
# Soft-hyphenation artifact: PDFs use Unicode soft-hyphen (U+00AD) or
# letter-spacing for line-break-aware hyphenation. pdftotext removes the
# soft-hyphen but leaves a single SPACE between the two halves. Example:
# the word "experiments" in xiao_2021_crsp's abstract renders as
# "experi ments" — visible as a typo to a human reader and breaks every
# downstream NLP / search / citation-extraction tool that relies on word
# tokens.
#
# Note: S7 (hyphenation repair) handles `\\nword-\\nword2` → `\\nwordword2`
# but ONLY when the hyphen is still present (the line-break-then-hyphen
# pattern). pdftotext's space-broken form has no hyphen — different bug,
# different fix.
#
# Strategy: curated list of (prefix, suffix-set) pairs where the joined
# form is unambiguously a single English word. The pairs were sourced
# from xiao_2021_crsp Phase 5d AI verify (2026-05-14): experi/ments,
# addi/tion, discre/pancies, con/ducted, con/cerning, con/fined,
# presenta/tion, ques/tionnaires, experi/ences. Expanded with sibling
# pairs in the same morphological family.
#
# Conservative: every (prefix, suffix) listed produces a single valid
# English word when joined. Rejecting body context: the patterns require
# both halves to be lowercase and at word boundaries. Phrases like
# "they were experi ments" → "they were experiments" — the surrounding
# context is fine.
_DEHYPHEN_REJOIN_PAIRS: list[tuple[str, str]] = [
    (r"experi",  r"(?:ments?|mental|mentally|ences?|enced|mentation)"),
    (r"addi",    r"(?:tions?|tionally|tive|tives)"),
    (r"discre",  r"(?:pancy|pancies|tion|tionary)"),
    (r"con",     r"(?:cerning|ducted|ducting|fined|firmed|sequently|"
                 r"sistent|sistently|cluded|sists|sisted|siderable|"
                 r"siderably|trolled|trolling|fronted|fronting|firmation)"),
    (r"ques",    r"(?:tion|tions|tionnaire|tionnaires|tioned|tioning)"),
    (r"presenta", r"(?:tion|tions|tional)"),
    (r"discus",  r"(?:sion|sions|sed)"),
    (r"informa", r"(?:tion|tions|tive|tional)"),
    (r"differ",  r"(?:ence|ences|ent|ently|ential|entiate|entiated)"),
    (r"repli",   r"(?:cation|cations|cate|cates|cated|cating)"),
    (r"refer",   r"(?:ence|ences|ential|enced|encing)"),
    (r"identi",  r"(?:fied|fies|fy|fication)"),
    (r"specifi", r"(?:cation|cations|cally|ed)"),
    (r"reliabi", r"(?:lity|lities)"),
    (r"genera",  r"(?:tion|tions|lly|lize|lized|lization)"),
    (r"explana", r"(?:tion|tions|tory)"),
    (r"transla", r"(?:tion|tions|ted|ting)"),
    (r"observa", r"(?:tion|tions|tional)"),
    (r"opera",   r"(?:tion|tions|tional|tionalize|tionalized)"),
    (r"varia",   r"(?:tion|tions|ble|bles|bility)"),
    (r"correla", r"(?:tion|tions|ted|ting|tional)"),
    (r"applica", r"(?:tion|tions|ble|bility)"),
    (r"interpre", r"(?:tation|tations|t|ted|ting|tive)"),
]

_DEHYPHEN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(rf"\b{p}\s+{s}\b")
    for p, s in _DEHYPHEN_REJOIN_PAIRS
]


def _rejoin_space_broken_compounds(text: str) -> str:
    """S7a: rejoin pdftotext-broken compound words.

    Applies the curated (prefix, suffix) regex list. Each pattern is
    ``\\bprefix\\s+suffix\\b`` — the ``\\s+`` separator matches a space, a
    tab, OR a newline, because pdftotext breaks these compounds two ways:
    ``experi ments`` (soft hyphen dropped, a space left) and
    ``repli\\ncations`` (line-wrapped — no hyphen, or a soft hyphen that S6
    has already stripped). The whole separating run is removed, so the
    compound rejoins regardless of separator. Stripping only the literal
    space (the pre-v2.4.58 behavior) left newline-separated compounds
    un-joined until a second pipeline pass — that broke idempotency, since
    S8 converts the mid-word newline to a space only AFTER this step runs.
    Idempotent and pipeline-order-independent.
    """
    if not text:
        return text
    for pat in _DEHYPHEN_PATTERNS:
        text = pat.sub(lambda m: re.sub(r"\s+", "", m.group(0)), text)
    return text


_NUMBERED_HEADING_ORPHAN_RE = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,3}\.?)\s*$")


def _rejoin_split_numbered_headings(text: str) -> str:
    """B5 / G5c-2 (2026-05-22): rejoin a numbered section heading whose
    leading ``N.N.`` number got linearised onto its own line by pdftotext.

    Pattern (jdm_m.2022.2: 5 cases):
        ``2.1.``           <- bare number, no body content
        (blank line(s))
        ``Methods``        <- canonical section keyword

    pdftotext column-linearisation can split ``2.1. Methods`` onto two
    lines. The section partitioner then drops the orphan ``2.1.`` line
    (it's not a recognised heading on its own) and the ``Methods`` line
    is correctly promoted, but the numeric prefix is permanently lost
    from the heading text.

    Conservative: a candidate orphan is rejoined ONLY when the next
    non-blank line lies within 3 lines, is ≤80 chars, and maps to a
    canonical SectionLabel via ``lookup_canonical_label``. Prose words
    that happen to capitalise (``Although``, ``However``) never resolve
    to a canonical label so they are safe.

    No-op when the next line is itself another orphan number, when the
    orphan is at end of text, or when the heading doesn't resolve.
    """
    # Lazy import avoids the normalize → sections → normalize import cycle
    # (sections/__init__.py imports normalize_text from this module).
    from .sections.taxonomy import lookup_canonical_label

    lines = text.split("\n")
    out: list[str] = []
    n = len(lines)
    i = 0
    while i < n:
        m = _NUMBERED_HEADING_ORPHAN_RE.match(lines[i])
        if m:
            # Find next non-blank line within a 3-line lookahead.
            j = i + 1
            blanks: list[int] = []
            while j < n and not lines[j].strip():
                blanks.append(j)
                j += 1
            if (
                j < n
                and j - i <= 3
                and 1 <= len(lines[j].strip()) <= 80
                # Don't consume two stacked orphans — the second might be
                # the real heading number for a SUBSEQUENT line.
                and not _NUMBERED_HEADING_ORPHAN_RE.match(lines[j])
                and lookup_canonical_label(lines[j].strip()) is not None
            ):
                num = m.group(1)
                # Ensure trailing dot so the combined form is the
                # conventional ``N.N. Heading`` shape.
                if not num.endswith("."):
                    num = num + "."
                out.append(f"{num} {lines[j].strip()}")
                # Skip the blanks between and the consumed heading line.
                i = j + 1
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def _fix_hyphenated_line_breaks(text: str) -> str:
    """H1: join lines split mid-word at a hyphen by pdftotext column wrap.

    Conservative: always keeps the hyphen, only removes the newline. Both
    real compounds (``Meta-\\nProcesses`` → ``Meta-Processes``) and line-wrap
    artifacts (``socio-\\neconomic`` → ``socio-economic``) end up as valid
    hyphenated forms.

    Skips ``<table>`` blocks, fenced code, markdown headings, hyphens after
    non-alpha characters (date ranges), and continuation lines starting with
    non-alpha (markers, brackets).
    """
    lines = text.split("\n")
    in_table = False
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        ls = line.strip()
        if ls.startswith("```"):
            in_fence = not in_fence
            i += 1
            continue
        if not in_fence:
            if "<table" in ls:
                in_table = True
            if "</table>" in ls:
                in_table = False
                i += 1
                continue
        if in_fence or in_table:
            i += 1
            continue
        if ls.startswith("#"):
            i += 1
            continue
        if (
            i + 1 < len(lines)
            and len(line) >= 3
            and line.endswith("-")
            and line[-2].isalpha()
        ):
            next_line = lines[i + 1]
            ns = next_line.strip()
            if ns and ns[0].isalpha():
                lines[i] = line + ns
                del lines[i + 1]
                continue
        i += 1
    return "\n".join(lines)


# ── document-level numeric locale (decision D5, v2.4.128) ───────────────
#
# `N = 1,234` is 1234 in an English paper and 1.234 in a German one, and the two
# conventions are MUTUALLY EXCLUSIVE within one article — so one unambiguous
# token anywhere in a document settles how every ambiguous token in it should be
# read. That is a document-level fact, and docpluck is the only layer that still
# holds it.
#
# WHY WE PUBLISH IT: our own normalization INVERTS this evidence. Measured on a
# real document, before and after `academic`:
#
#     RAW       ->  decisive_eu   (6 European markers, 0 US)
#     DELIVERED ->  decisive_us   (0 European, 6 US)      the verdict FLIPS
#
# Academic normalization turns every `d = 0,80` into `d = 0.80`, so the
# delivered text looks decisively US *by construction*. A consumer running this
# same inference on our output — which is exactly what effectcheck's
# `infer_numeric_locale` does — cannot recover the fact. It is not merely
# inconvenient to recompute downstream; it is impossible. So we compute it while
# the evidence exists and hand it over.
#
# The marker patterns are ported from effectcheck's implementation, whose
# exclusions are themselves already debugged. Three details are load-bearing:
#
#   * markers are OPERATOR-GUARDED. A bare `0,1` also matches coded variables,
#     version numbers, ratios and lists (it misfires on 5 of 10 realistic
#     strings).
#   * `\d,\d{1,2}` is NOT evidence. Tight CI separators (`[0.57,0.73]`) produced
#     a false CONFLICT on a real article whose six "European" signals were all
#     CI commas.
#   * a PLAIN space is EXCLUDED from the full-notation separator class, which
#     admits only `.`, U+00A0, U+202F and `'`. In English journals a space
#     between digit groups separates two numbers far more often than it groups
#     one, and `403,669 107,081` was read as a single European number and
#     flipped a whole document. Codex's 2026-08-13 review flagged this class as
#     admitting a plain space; checked against the source, it does not, and the
#     finding was REFUTED — it was the review DOCUMENT that had transcribed the
#     no-break spaces as ordinary ones. Spelled with explicit escapes below so
#     the distinction can never again be lost to a copy-paste.
_LOCALE_OP = r"[=<>≤≥]\s*"
_LOCALE_GROUP_SEP = "[.  ']"

_LOCALE_EUROPEAN_MARKERS = {
    "F1_full_notation": r"\d" + _LOCALE_GROUP_SEP + r"\d{3},\d",
    "E2_leading_comma": _LOCALE_OP + r",\d{2,}",
    "E3_zero_comma": _LOCALE_OP + r"0,\d",
    # E4 carries its bracket guard IN THE PATTERN as of v2.4.129. It used to
    # live in `infer_numeric_locale`'s body, which recorded an
    # `E4_bracketed_excluded` count — and when that function was deleted the
    # guard went with it, silently, leaving the raw marker voting European on
    # an ML tensor shape `(70,64472)` again. A guard that lives in the CALLER
    # is lost the moment the caller changes; a guard in the pattern cannot be.
    # (Reproduced 2026-08-14 by the very test written to pin this vocabulary.)
    "E4_four_decimals": r"(?<![(\[])\d{1,3},\d{4,}",
    "E5_sci_notation": r"\d,\d+[eE][-+]?\d",
}
_LOCALE_US_MARKERS = {
    "F2_full_notation": r"\d,\d{3}\.\d",
    "U2_leading_dot": _LOCALE_OP + r"\.\d{2,}",
    "U3_zero_dot": _LOCALE_OP + r"0\.\d",
    "U4_two_groups": r"\d,\d{3},\d{3}",
}

# E4 fires on machine-learning TENSOR SHAPES: `(70,64472)` is a matrix
# dimension, not a four-decimal European value. This produced the ONLY
# "conflict" verdict in a 101-paper corpus scan, on an IEEE paper that is
# plainly US-convention — i.e. the single disagreement in the whole measurement
# was an artifact of this one pattern. A bracket-delimited pair is never a
# decimal, so bracketed E4 hits are excluded from the evidence count.
# Publishing a WRONG locale is worse than publishing none, because a field
# creates confidence a missing field does not.
_LOCALE_E4_BRACKETED = re.compile(r"[(\[]\s*\d+,\d{4,}\s*[)\]]")

# Below this, a verdict is reportable but must not GATE any text change. One
# marker in a long document is a fact about one token, not about the document;
# `us=0, eu=1` yields `decisive_eu` on a single possibly-spurious hit.
# ── The locale MARKER VOCABULARY is retained; the VERDICT is not ──────────
#
# v2.4.129 DELETED the document-level numeric-locale feature: `NumericLocale`,
# `infer_numeric_locale()`, `LOCALE_MIN_GATING_CONFIDENCE`, `is_gating`, and
# `NormalizationReport.numeric_locale`. The tables above survive it deliberately.
#
# WHY THE VERDICT WENT (user directive 2026-08-14). docpluck's scope is English
# papers in **US** numeric convention. We do not know how to handle European
# numbers, and we no longer pretend to: they pass through unconverted. A
# document-level verdict was the wrong shape for that world, and it was worse
# than useless — it was CONFIDENTLY WRONG on the one real case ever found:
#
#     10.1177/0956797620935584 Table S2 — ~130 comma-decimal cells in an
#     English paper — scored verdict='decisive_us', european_markers=0,
#     us_markers=61, confidence=1.0.
#
# Every European marker here is OPERATOR-GATED (`_LOCALE_OP`), and a flattened
# table cell has no operator, so the instrument cannot see the exact place
# European decimals actually appear. The measurement that justified the feature
# — "396 English articles -> 0 European-locale" — therefore described the
# INSTRUMENT, not the corpus. It also gated nothing: `is_gating` had zero
# non-test call sites for its whole life.
#
# WHY THE TABLES STAYED — and this is a DELIBERATE, DOCUMENTED exception to the
# "no dead code" rule, not an oversight:
#
#   1. They carry hard-won false-positive resistance. Each exclusion below was
#      paid for by a real corpus regression — ML tensor shapes, bracket-delimited
#      pairs, CI commas, and the plain-space case that read `403,669 107,081` as
#      one European number and flipped a whole document. An independent reviewer's
#      throwaway detector, written fresh on 2026-08-14, immediately reproduced the
#      RGB-triple false positive these guards already solve.
#   2. They are the intended vocabulary for the **local-window** locale guard —
#      "does THIS table use comma decimals?" — which is the identified remedy for
#      A3a's 1000x error class. Deleting and rebuilding them later means
#      rediscovering the same bugs.
#
# **They are NOT WIRED and must not be wired to a document-level verdict again.**
# Anything built on them is line- or table-scoped. Pinned by
# `tests/test_numeric_locale_markers.py`, which exists so this vocabulary is
# tested rather than merely retained.


@dataclass
class NormalizationReport:
    level: str
    version: str = NORMALIZATION_VERSION
    steps_applied: list[str] = field(default_factory=list)
    steps_changed: list[str] = field(default_factory=list)
    changes_made: dict[str, int] = field(default_factory=dict)
    footnote_spans: tuple[tuple[int, int], ...] = ()  # pre-strip char offsets
    # v2.4.83: the captured footnote strings, parallel to footnote_spans
    # (footnote_texts[i] == raw_text[footnote_spans[i][0]:footnote_spans[i][1]]).
    # A first-class surface so consumers don't have to slice char offsets or
    # parse the \n\f\f\n appendix out of the body. Empty when F0 doesn't run
    # (no layout) or no footnotes were detected.
    footnote_texts: tuple[str, ...] = ()
    page_offsets: tuple[int, ...] = ()                 # post-strip body page offsets
    # §A R4 / B6 (NORMALIZATION_VERSION 1.9.23, 2026-05-23): 1-indexed page
    # numbers where pdftotext's two-column reading-order serialisation
    # appears to have interleaved between columns. Surfaced as a signal for
    # downstream consumers (a follow-up cycle will re-extract these pages
    # via a column-aware path; this cycle lands the detector + flag).
    column_interleave_pages: tuple[int, ...] = ()
    # Fallback paths that fired during THIS normalization — `{}` when nothing
    # unusual happened.
    #
    # **This field exists because the previous release's telemetry fix stopped
    # one layer short.** v2.4.133 made `record_fallback` reach a consumer
    # through `StructuredResult["fallbacks"]` — but `normalize_text` runs AFTER
    # `extract_pdf_structured` has returned, so every event recorded HERE fell
    # outside that window and stayed write-only. That included
    # `w0h_ambiguous_pairing_refused` / `w0m_ambiguous_pairing_refused`, the
    # counters the same release added to make W0h/W0m's new REFUSAL mode
    # observable: the refusal was the whole point of the Risk-A fix, and it
    # shipped with no witness. A repair that declines to fire and tells nobody
    # is indistinguishable from a document that never needed it.
    fallbacks: dict[str, int] = field(default_factory=dict)
    # The same events with the specific instance that fired them — for a refusal,
    # the coefficient the layout proved but the text could not place.
    fallback_details: dict[str, dict[str, int]] = field(default_factory=dict)

    def _track(self, step_code: str, before: str, after: str, metric_name: str):
        # ``steps_applied`` records every step that ran (kept for backward
        # compatibility with tests and diagnostics that want to see the full
        # pipeline order). ``steps_changed`` records only steps that actually
        # modified the text — this is the field diagnostics should prefer
        # when they want to know what the pipeline *did* on a given input.
        # See MetaESCI request D7.2.
        self.steps_applied.append(step_code)
        if before != after:
            self.steps_changed.append(step_code)
            diff = len(before) - len(after)
            if diff != 0:
                self.changes_made[metric_name] = abs(diff)

    def to_dict(self) -> dict:
        """JSON-ready view of the whole report, field-for-field.

        Derived from ``asdict`` rather than a hand-written key list on
        purpose. The hand-written version silently dropped
        ``column_interleave_pages`` — a populated field
        (:func:`_detect_column_interleave_pages`) that ``extract_columns``
        documents as the canonical source of the column-interleave signal — so
        every consumer reading the serialized report saw a complete-looking
        object with that signal missing. See ``batch.ExtractionReport.to_dict``
        for the same defect in its sibling class, fixed in the same release
        (v2.4.126).

        Tuple fields are converted to lists so the Python-side shape matches
        what a JSON round-trip produces.
        """
        d = asdict(self)
        d["footnote_spans"] = [list(s) for s in self.footnote_spans]
        d["footnote_texts"] = list(self.footnote_texts)
        d["page_offsets"] = list(self.page_offsets)
        d["column_interleave_pages"] = list(self.column_interleave_pages)
        return d


# v2.4.38 (NORMALIZATION_VERSION 1.9.4): recover U+2212 minus signs that
# pdftotext maps to the digit '2' on certain fonts (e.g. efendic_2022 — every
# confidence interval reads "[20.92, 20.30]" for "[−0.92, −0.30]", every
# "r = 2.74" for "r = −.74"). Two self-gating, context-safe signatures:
#   Rule 1 — a bracketed numeric pair "[A, B]" DESCENDING as written (A > B,
#   impossible for a CI / range) that becomes a valid ASCENDING interval once
#   the leading '2' of a decimal-bearing bound is read as '−'. Integer-only
#   brackets (citation lists like "[25, 3]") never convert.
#   Rule 2 — "r = 2.<digits>": a Pearson r cannot exceed 1, so any
#   "r = 2.something" is a corrupted "r = −.something".
# An ascending CI or a plausible correlation is never touched.
_BRACKET_PAIR_RE = re.compile(r"\[\s*(-?\d*\.?\d+)\s*,\s*(-?\d*\.?\d+)\s*\]")
_CORRUPT_R_RE = re.compile(r"(\br\s*(?:\(\s*\d+\s*\)\s*)?=\s*)2(\.\d+)")


def recover_corrupted_minus_signs(text: str) -> str:
    """W0b: recover pdftotext '2'-for-U+2212 minus-sign corruption."""
    if not text:
        return text

    def _conv(tok: str) -> str:
        # A '2'-prefixed decimal token reads as a negative: 20.92 -> -0.92.
        if tok.startswith("2") and "." in tok:
            return "-" + tok[1:]
        return tok

    def _fix_bracket(m: "re.Match[str]") -> str:
        a_str, b_str = m.group(1), m.group(2)
        try:
            a, b = float(a_str), float(b_str)
        except ValueError:
            return m.group(0)
        if a <= b:
            return m.group(0)  # ascending — genuine interval, leave it
        a2_str, b2_str = _conv(a_str), _conv(b_str)
        if a2_str == a_str and b2_str == b_str:
            return m.group(0)  # nothing convertible (e.g. integer bracket)
        try:
            if float(a2_str) <= float(b2_str):
                return f"[{a2_str}, {b2_str}]"
        except ValueError:
            pass
        return m.group(0)

    # WHICH brackets THIS call actually repaired. Passed downstream so the
    # estimate-column recovery cannot treat a bound it just manufactured as
    # independent proof of corruption — register O10.
    repaired: set[str] = set()

    def _fix_bracket_tracking(m: "re.Match[str]") -> str:
        out = _fix_bracket(m)
        if out != m.group(0):
            repaired.add(out.strip())
        return out

    t = _BRACKET_PAIR_RE.sub(_fix_bracket_tracking, text)
    t = _CORRUPT_R_RE.sub(r"\1-\2", t)
    t = _recover_estimate_column_via_ci_column(t, repaired_brackets=repaired)
    return t


# W0b-est (v2.4.119): a raw_text table fallback linearizes each COLUMN as its
# own run of lines — estimates, then SEs, then CIs, then p-values — so an
# estimate and its CI are separated by the whole SE run. W0d's CI-pairing
# proximity window cannot span that gap, so in efendic Table 3 the CI column
# recovers (`[-1.58, -1.10]`) while the estimate column keeps its corruption
# (`21.34`, truly `-1.34`). This was invisible before v2.4.119 because the
# caption-tail walk was dropping these leading rows entirely.
#
# The pairing is POSITIONAL and only fires on the unambiguous signature: a run
# of bare numeric estimate lines and a later run of CI lines of the SAME
# length, where the CI run is already recovered-negative (proof this table
# carries the `2`-for-minus corruption). Estimate i is then checked against
# CI i: it is rewritten only when the corrupt reading (`2X.XX` → `-X.XX`) lands
# INSIDE that CI while the literal reading does not — the same containment
# invariant W0d uses, just resolved by column index instead of proximity.
_BARE_NUM_LINE_RE = re.compile(r"^\s*(-?\d+\.\d+)\s*$")


def _recover_estimate_column_via_ci_column(
    text: str, *, repaired_brackets: "set[str] | None" = None
) -> str:
    """Recover a `2`-for-minus ESTIMATE column by pairing it positionally with
    its already-recovered CI column. See the block comment above.

    ``repaired_brackets`` are the bracket strings the CALLER just rewrote in this
    same pass, and **this argument is what stops the evidence being circular**
    (register O10). The ``recovered_negative`` gate below is meant to establish
    *"this table demonstrably carries the 2-for-minus corruption"*, and it was
    computed as ``lo < 0 or hi < 0`` — which is true of most psychology tables,
    and, worse, was true of the very bounds ``recover_corrupted_minus_signs`` had
    manufactured one line earlier. A rewrite became its own proof.

    The gate now fires only on a bracket THIS pass actually repaired, which is
    the only bound carrying real evidence of the corruption. Passing ``None``
    keeps the old self-proving behaviour and exists solely for tests that call
    this helper directly; production always passes the set.
    """
    if "[" not in text:
        return text
    lines = text.split("\n")
    n = len(lines)

    def _runs(pred) -> list[tuple[int, int]]:
        out, i = [], 0
        while i < n:
            if not pred(lines[i]):
                i += 1
                continue
            j = i
            while j < n and pred(lines[j]):
                j += 1
            out.append((i, j))
            i = j
        return out

    num_runs = [r for r in _runs(lambda s: bool(_BARE_NUM_LINE_RE.match(s))) if r[1] - r[0] >= 3]
    ci_runs = [r for r in _runs(lambda s: bool(_CI_LINE_RE.match(s))) if r[1] - r[0] >= 3]
    if not num_runs or not ci_runs:
        return text

    for ci_start, ci_end in ci_runs:
        length = ci_end - ci_start
        cis: list[tuple[float, float]] = []
        recovered_negative = False
        for k in range(ci_start, ci_end):
            m = _CI_LINE_RE.match(lines[k])
            assert m is not None
            lo, hi = float(m.group(1)), float(m.group(2))
            if lo < 0 or hi < 0:
                if repaired_brackets is None:
                    recovered_negative = True
                elif any(b in lines[k] for b in repaired_brackets):
                    recovered_negative = True
            cis.append((min(lo, hi), max(lo, hi)))
        if not recovered_negative:
            continue
        # Find the numeric run holding the estimate column. pdftotext emits no
        # blank line between adjacent numeric columns, so the estimate and SE
        # columns arrive as ONE run of k*length lines (efendic Table 3: 18
        # lines = 9 estimates + 9 SEs). Accept a run that is an exact multiple
        # of the CI-run length and take its FIRST block: in a stats table the
        # estimate column precedes SE/df/etc., and the CI describes the
        # estimate. The containment test below still gates every rewrite, so a
        # mis-split simply recovers nothing.
        cand = [
            r for r in num_runs
            if r[1] <= ci_start and (r[1] - r[0]) % length == 0
        ]
        if not cand:
            continue
        est_start = cand[-1][0]
        for idx in range(length):
            k = est_start + idx
            m = _BARE_NUM_LINE_RE.match(lines[k])
            assert m is not None
            tok = m.group(1)
            mm = _CORRUPT_NEG_BOUND_RE.match(tok)
            if not mm:
                continue
            frac = mm.group(1)
            fixed = "-" + ("0" + frac if frac.startswith(".") else frac)
            lo, hi = cis[idx]
            try:
                literal_in = lo <= float(tok) <= hi
                fixed_in = lo <= float(fixed) <= hi
            except ValueError:
                continue
            if fixed_in and not literal_in:
                lines[k] = lines[k].replace(tok, fixed)
    return "\n".join(lines)


# Shared shapes for the column-structure minus recoveries (W0b-est).
_CI_LINE_RE = re.compile(r"^\s*\[\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\]\s*$")
# The corrupt shape: `2` glued to a single-digit-integer decimal (20.09 -> -0.09).
_CORRUPT_NEG_BOUND_RE = re.compile(r"^2(\d?\.\d+)$")

# v2.4.39 (NORMALIZATION_VERSION 1.9.5): recover the '<' comparison operator
# that pdftotext maps to a backslash '\' on certain fonts (e.g. efendic_2022 —
# every "p < .001" reads "p \ .001", every table p-value cell "<.001" reads
# "\.001", the legacy Wiley DOI "13:1<1::AID-…" reads "13:1\1::AID-…"). A
# literal backslash never legitimately occurs glued to a numeral in extracted
# academic-PDF text — '\' is not a prose character and the renderer adds no
# markdown escapes — so a backslash immediately followed (optional single
# space) by a digit or a '.'-prefixed decimal is unambiguously a corrupted
# '<'. The space, if any, is preserved so "p \ .05" -> "p < .05".
_CORRUPT_LT_RE = re.compile(r"\\(\s?)(?=\.?\d)")


def recover_corrupted_lt_operator(text: str) -> str:
    """W0c: recover pdftotext '<'-as-backslash glyph corruption."""
    if not text or "\\" not in text:
        return text
    return _CORRUPT_LT_RE.sub(r"<\1", text)


# ── W0o: '<'-as-'b' glyph corruption (v2.4.130, 2026-08-14) ─────────────────
#
# RASTER-VERIFIED, and it is OURS. `10.1016/j.jesp.2016.11.001` page 4 PRINTS
# `p < 0.001` in `BFDKFC+AdvTT94c8263f.I` — the same broken-ToUnicode AdvTT
# family behind W0n's Dong case — and pdftotext yields `p b 0.001`. The page is
# correct and our extraction is not, so this is docpluck's to fix under the ONE
# EXCEPTION to the separation-of-duties directive: a defect our own pipeline
# introduced, where the source is intact underneath.
#
# WHY IT WAS NOT FIXED BEFORE. The 2026-08-14 handoff recorded "that one is
# ours (`W0c` owns it) and stays." **That is false.** `recover_corrupted_lt_operator`
# above recovers `<`-as-BACKSLASH only; nothing anywhere handled `<`-as-`b`. The
# claim was copied forward unverified and read as settled — L-027 in miniature.
#
# WHY THE SIGNATURE IS THE OPERATOR SLOT, not "a `b` near a number". Unlike a
# backslash — which never legitimately touches a numeral in extracted academic
# text — **`b` is a real statistical symbol**, the unstandardized regression
# coefficient. The SAME paper carries 17 legitimate uses (`b = 2.73`,
# `b = -3.26`, `b = 4.98`). So the discriminator is structural: a statistic
# ALWAYS has an operator between its symbol and its value, and `b` is NEVER an
# operator. A bare `b` sitting in that slot therefore cannot be a coefficient —
# a coefficient would carry its own `=`.
#
# MEASURED before shipping (`tools/diag/b_for_lt_scan.py`):
#     31 hits in 10.1016/j.jesp.2016.11.001 — every one a real `p < 0.001`
#      0 hits across the 26-paper baseline corpus       (no false positives)
#     17 legitimate `b` uses in the affected paper       (all untouched)
# Note the affected paper is NOT in the baseline corpus, so "0 in 26" describes
# the absence of FALSE POSITIVES, never the absence of the shape — a denominator
# that excludes the known case cannot speak to prevalence.
#
# RE-MEASURED 2026-08-15 on a proper denominator — 200 papers sampled from the
# 9,825-PDF article repository — and the rule is FAR more load-bearing than the
# single-paper justification suggested:
#
#     181 firing sites across 21 of 200 papers  (10.5% of the sample)
#     every one of them an Elsevier/JESP paper (10.1016/j.jesp.*)
#
# This is not a one-paper quirk; it is a SYSTEMATIC failure of one publisher's
# font pipeline. Sample sites, each sitting immediately after a completed test
# statistic, so the reading is unambiguous:
#
#     t(76) = - 2.01, p b .05          F(1.74,134.13) = 59.24, p b .001
#     Wald = 19.17, p b .001           means differ at p b .05.
#
# In the SAME sentences `B = - .30` and `beta = .25` extract correctly, so only
# the `<` glyph is affected. Verified by RASTERIZING two independent papers:
# `10.1016/j.jesp.2016.11.001` p4 and `10.1016/j.jesp.2015.09.003` p3 both PRINT
# `p < .001`. Fonts on both are the AdvTT family (`AdvTT94c8263f.I`).
#
# A rule justified from ONE document turning up in 10% of a random sample is a
# reminder that the single-paper standard establishes the SHAPE IS REAL; it says
# nothing about prevalence. Measure the denominator separately.
#
# CONSUMER IMPACT: 31 published p-values that no `p\s*<` regex could match, in
# one paper. Silent coverage loss, not a visible corruption.
#
# Only `<` is recovered. `>` is not attempted: no corpus evidence shows which
# glyph that font maps `>` to, and inventing one would be the hypothetical this
# project forbids.
_STAT_SYMBOL_FOR_B = r"(?:[pPtFrRzZdgQ]|chi2|eta2|BF|OR|RR|HR|SE|SD|CI|F\([^)]*\))"
_CORRUPT_LT_AS_B_RE = re.compile(
    r"(\b" + _STAT_SYMBOL_FOR_B + r"\s)b(\s(?=[-+]?\.?\d))"
)


def recover_lt_as_b_operator(text: str) -> str:
    """W0o: recover the '<' operator that some AdvTT fonts extract as 'b'.

    `p b 0.001` -> `p < 0.001`. Fires only when the `b` occupies a statistic's
    OPERATOR SLOT, which a coefficient `b` never does.
    """
    if not text or " b " not in text:
        return text
    return _CORRUPT_LT_AS_B_RE.sub(r"\1<\2", text)


# v2.4.103 (NORMALIZATION_VERSION 1.9.38): recover the '×' MULTIPLICATION SIGN
# that pdftotext/pdfminer map to the digit '3' on certain fonts (e.g.
# efendic_2022 — every interaction-term predictor name reads "Direction 3
# manipulated attribute" for "Direction × manipulated attribute", "PMA 3
# direction" for "PMA × direction", across all four regression tables). Same
# broken-ToUnicode font family as the '2'-for-minus (W0b/W0d) and '<'-as-
# backslash (W0c) corruptions on this PDF (AdvPS… subset fonts, `pdffonts`
# uni:no).
#
# UNLIKE the minus/'<' recoveries, a bare '3' between two words is AMBIGUOUS in
# free prose — "Table 3 summarizes", "see Figure 3 and", "osf.io/pg3ae" all
# contain a genuine '3' flanked by letters. So this recovery is SCOPED TO TABLE
# CELLS ONLY (wired into cell_cleaning._html_escape, never normalize_text or the
# whole-markdown render post-process). A Camelot table PREDICTOR cell that reads
# "Direction 3 manipulated attribute" is unambiguously the interaction term
# "Direction × manipulated attribute" — a table predictor cell never contains a
# sentence-boundary or a URL. The signature: a '3' (with optional single spaces)
# flanked on BOTH sides by an alphabetic character, inside a cell that is
# predominantly a label/predictor name (carries a ≥3-letter word), AND not
# immediately preceded by a reference/enumeration word (Study/Model/Wave/Phase/
# Item/Table/Figure/Panel/Step/Level/Sample/Experiment) which would make "… 3 …"
# a genuine ordinal. A corpus scan of 12 non-efendic papers found ZERO table
# cells matching this signature that were not corrupted interaction terms.
# A line-break separator that a wrapped interaction term may carry between its
# operands: the cell-merge placeholder (``\x00…\x00``, e.g. ``\x00BR\x00``), a
# literal ``<br>``, or a newline. A 3-way interaction "A × B × C" can wrap as
# "A 3 B<br>3 C", so the '3' after the break is still a corrupted '×'.
_TIMES_BREAK = r"(?:\x00[^\x00]*\x00|<br\s*/?>|\n)"
# The corrupted '×': a '3' flanked on each side by an alphabetic char, with
# whitespace OR a wrap-break on AT LEAST ONE immediate side. The whitespace/break
# requirement is what separates an interaction operator ("Direction 3 manipulated",
# "PMA 3direction") from a GLUED alphanumeric label that legitimately contains a 3
# — hypothesis labels "H3a"/"H3b", model codes "M3", "x3y" — which are fully glued
# with no separating space and must never be touched. Two alternatives: break/space
# BEFORE the 3, or break/space AFTER it.
_TIMES_GLYPH_RE = re.compile(
    r"(?<=[A-Za-z])(" + _TIMES_BREAK + r"?[ \t]+|" + _TIMES_BREAK + r")3([ \t]*)(?=[A-Za-z])"
    r"|"
    r"(?<=[A-Za-z])([ \t]*)3(" + _TIMES_BREAK + r"?[ \t]+)(?=[A-Za-z])"
)
# Words that make a following "3" a genuine ordinal/reference, not a corrupted ×.
_TIMES_REFERENCE_WORD_RE = re.compile(
    r"\b(?:Study|Studies|Model|Models|Wave|Phase|Item|Items|Table|Tables|Figure|"
    r"Figures|Fig|Panel|Step|Steps|Level|Sample|Samples|Experiment|Experiments|"
    r"Section|Appendix|Chapter|Part|Day|Time|Trial|Trials|Version|Group|Grade|"
    r"Cluster|Factor|Class|Type|Site|Cohort|Session|Block|Set|Round|Question|"
    r"Condition|Column|Row|Line|Page|Wave)\s*$",
    re.IGNORECASE,
)
# RANGE grammar (v2.4.122). A '3' that is a bound of a range is a real number,
# never an interaction operator: "scores ranged from 3 to 15", "aged from 3 to
# 12 years". The pre-existing reference-word list above cannot catch this — it
# enumerates NOUNS ("Model 3"), while a range is a GRAMMATICAL FRAME around the
# digit: a `from`/`between` opener before it and a `to`/`and` closer after it.
# Keying on the frame (not on a word list) is what makes this general: it holds
# for any range in any table note, in any publisher's papers.
#
# Found 2026-08-04 by the cycle-1 canary audit: chan_feldman's Table-2 note
# "Avoidance behaviour scores ranged from 3 to 15" rendered as "from × to 15" —
# the library DELETED a published scale bound. `from` sat where a predictor name
# would, and `to` after it, so W0i's letter-space-3-space-letter signature
# matched exactly.
_TIMES_RANGE_OPENER_RE = re.compile(r"\b(?:from|between)\s*$", re.IGNORECASE)
_TIMES_RANGE_CLOSER_RE = re.compile(r"^\s*(?:to|and|through|until)\b", re.IGNORECASE)


def _times_is_range_bound(before: str, after: str) -> bool:
    """True when the '3' sits inside range grammar (``from 3 to``/``between 3 and``).

    Requires BOTH halves of the frame. A lone `to` after the digit is not enough
    ("Attitude 3 to risk" would be a wrapped predictor), and a lone `from` is
    not enough either — only the complete construction is unambiguous.
    """
    return bool(_TIMES_RANGE_OPENER_RE.search(before) and _TIMES_RANGE_CLOSER_RE.match(after))


def recover_times_interaction_glyph(cell: str) -> str:
    """W0i: recover pdftotext '×'-as-'3' glyph corruption in a TABLE CELL.

    Operates on a single Camelot table-cell string. A '3' flanked by letters on
    both sides — inside a predictor/label cell, not preceded by a reference word
    — is a corrupted interaction '×'. NOT safe for free prose; call only from the
    table-cell pipeline (cell_cleaning._html_escape). See the module comment at
    ``_TIMES_GLYPH_RE`` for the full signature and why this is table-scoped.
    """
    if not cell or "3" not in cell:
        return cell
    # Only fire in a cell that carries a variable/predictor name (a ≥3-letter
    # alphabetic word). A purely-numeric stat cell ("0.34", "1.23") never has a
    # letter on both sides of a 3, but this also skips a short-code cell early.
    if not re.search(r"[A-Za-z]{3,}", cell):
        return cell

    def _sub(m: "re.Match[str]") -> str:
        # Guard: a reference/enumeration word immediately before the 3 makes it a
        # genuine ordinal ("Model 3 predictor" stays; the ordinal is not an ×).
        before = cell[: m.start()]
        if _TIMES_REFERENCE_WORD_RE.search(before):
            return m.group(0)
        # Guard: a range bound is a real number ("ranged from 3 to 15"), not an
        # interaction operator. The match spans the separators around the digit,
        # so the text after it starts at m.end().
        if _times_is_range_bound(before, cell[m.end():]):
            return m.group(0)
        # Two regex alternatives (break/space before the 3, or after it); each
        # captures its own (left, right) whitespace groups. Preserve whatever the
        # source had, defaulting the empty side to a single space so an
        # interaction term reads "A × B" regardless of how it wrapped/glued.
        if m.group(1) is not None:  # first alternative (separator before)
            left, right = m.group(1), m.group(2)
        else:  # second alternative (separator after)
            left, right = m.group(3), m.group(4)
        left = left if left else " "
        right = right if right else " "
        return f"{left}×{right}"

    return _TIMES_GLYPH_RE.sub(_sub, cell)


# ── W0k: '×'-as-'3' in body PROSE / flattened caption ──────────────────────
# (NORMALIZATION_VERSION 1.9.41, 2026-07-04). W0i recovers the '×'-as-'3' glyph
# in TABLE CELLS only — it is deliberately NOT prose-safe ("Table 3 summarizes",
# "osf.io/pg3ae", "3 studies"). But efendic_2022_affect carries the SAME glyph in
# its BODY PROSE and in a flattened italic table-caption run of interaction terms,
# which the table-cell scope never sees:
#   "the three-way interaction (Direction 3 Manipulated Attribute 3 CMA)"
#   "*… Direction 3 manipulated attribute PMA 3direction PMA 3 manipulated …*"
# The '3' is the single most dangerous glyph to touch in prose (a genuine ordinal
# / count), so W0k fires ONLY under a MUCH tighter signature than W0i (ALL hold):
#   1. the line mentions "interaction" OR carries ≥2 `Word 3 Word` candidate pairs
#      (an interaction-term run);
#   2. the '3' is NOT preceded by a reference/enumeration word
#      (Table/Model/Study/Figure/Wave/Step/Time/Level/…) — a genuine ordinal;
#   3. the right flank is NOT a plural COUNT noun ("3 studies"/"3 groups"/
#      "3 conditions" — `_TIMES_COUNT_NOUNS`);
#   4. at least ONE flank is Title-Case or an all-caps ACRONYM — a predictor name
#      (Direction, Manipulated Attribute, CMA, PMA). "ran 3 studies" / "and 3
#      groups" have all-lowercase flanks and are rejected.
# FP-validated 2026-07-04: a 12-case adversarial battery (incl. "We ran 3 studies
# with 3 conditions each", "interaction between age and 3 groups", "Table 3
# summarizes", "Study 3", "osf.io/pg3ae") changes nothing; a wide render scan is
# run before ship (the maier `H3a`→`H × a` near-miss is why). Wired into channel 1
# (normalize_text) AND channel 3 (render post-process), like W0j.
_TIMES_PROSE_PAIR_RE = re.compile(
    r"(?<![\w.])([A-Za-z]{2,})(\s*)3(\s*)([A-Za-z]{2,})(?![\w.])"
)
_TIMES_REFERENCE_WORDS = (
    "table", "model", "study", "studies", "figure", "fig", "wave", "step",
    "steps", "level", "time", "phase", "experiment", "section", "note", "item",
    "day", "week", "year", "sample", "panel", "appendix", "footnote", "chapter",
    "part", "round", "trial", "block", "session", "cluster", "factor",
    "hypothesis", "question", "grade", "class", "group", "cohort", "version",
    "column", "row", "equation", "hypotheses", "day", "phase", "wave",
)
_TIMES_REFERENCE_WORDS_SET = frozenset(_TIMES_REFERENCE_WORDS)
_TIMES_REFERENCE_WORD_PROSE_RE = re.compile(
    r"\b(?:" + "|".join(_TIMES_REFERENCE_WORDS) + r")\s*$",
    re.IGNORECASE,
)
_TIMES_COUNT_NOUNS = frozenset({
    "studies", "study", "groups", "group", "conditions", "condition", "items",
    "item", "trials", "trial", "levels", "level", "waves", "wave", "factors",
    "factor", "participants", "measures", "measure", "samples", "sample",
    "tasks", "task", "sessions", "session", "blocks", "block", "times",
    "categories", "types", "type", "phases", "phase", "steps", "step",
    "models", "questions", "scales", "domains", "dimensions", "subgroups",
    "waves", "cohorts", "columns", "rows", "sites", "countries", "raters",
})


def _times_flank_is_predictor(word: str) -> bool:
    bare = re.sub(r"^[\(\[\{]+|[\)\]\},:;.]+$", "", word)
    return bool(bare) and bare[0].isalpha() and bare[0].isupper()


def recover_times_interaction_glyph_in_prose(text: str) -> str:
    """W0k: recover '×'-as-'3' glyph corruption in body-prose / flattened-caption
    interaction terms that the TABLE-CELL-scoped W0i cannot reach. Tight
    signature (see the block comment above) — the `3` is the most dangerous glyph
    to touch in prose, so ALL of interaction-context + non-reference + non-count +
    ≥1-predictor-flank must hold."""
    if not text or "3" not in text:
        return text
    out = []
    for line in text.split("\n"):
        cands = list(_TIMES_PROSE_PAIR_RE.finditer(line))
        # A SINGLE pair qualifies when BOTH flanks are predictor names (Title-Case/
        # acronym) — a very strong interaction signal ("… Direction 3 Manipulated
        # Attribute" caption tail). Otherwise require "interaction" OR ≥2 pairs.
        _both_pred_single = (
            len(cands) == 1
            and _times_flank_is_predictor(cands[0].group(1))
            and _times_flank_is_predictor(cands[0].group(4))
        )
        if not cands or (
            "interaction" not in line.lower()
            and len(cands) < 2
            and not _both_pred_single
        ):
            out.append(line)
            continue

        def _sub(m: "re.Match[str]", *, allow_lc: bool) -> str:
            before = line[: m.start()]
            left, right = m.group(1), m.group(4)
            # Reference-word ordinal guard: the `3` is a genuine ordinal when a
            # reference word precedes it — either as the LEFT FLANK itself
            # ("Model 3", "Study 3", "Wave 3") or immediately before the flank
            # ("see Model 3"). Both are checked (the left-flank check is the one
            # that was missing — "Model 3 Relationship" wrongly recovered).
            if left.lower() in _TIMES_REFERENCE_WORDS_SET:
                return m.group(0)
            if _TIMES_REFERENCE_WORD_PROSE_RE.search(before):
                return m.group(0)
            if right.lower().rstrip(".,;:)") in _TIMES_COUNT_NOUNS:
                return m.group(0)
            # A predictor flank (Title-Case / acronym) is required — UNLESS this
            # line already resolved a `×` between predictor words (a confirmed
            # interaction-term RUN, e.g. a flattened caption "Direction ×
            # manipulated attribute PMA × direction PMA × direction 3
            # manipulated…"), in which case a remaining lowercase-lowercase pair
            # in the SAME run is also an interaction term. The count-noun guard
            # above still blocks a genuine "… in 3 studies" in such a line.
            if not (allow_lc or _times_flank_is_predictor(left) or _times_flank_is_predictor(right)):
                return m.group(0)
            left_sp = m.group(2) if m.group(2) else " "
            right_sp = m.group(3) if m.group(3) else " "
            return f"{left}{left_sp}×{right_sp}{right}"

        # Pass 1 strict (≥1 predictor flank). If it resolved a `×`, the line is a
        # confirmed interaction-term run — Pass 2 relaxes the predictor-flank rule
        # for remaining lowercase-lowercase pairs (count guard still applies).
        line2 = _TIMES_PROSE_PAIR_RE.sub(lambda m: _sub(m, allow_lc=False), line)
        if "×" in line2 and "×" not in line:
            line2 = _TIMES_PROSE_PAIR_RE.sub(lambda m: _sub(m, allow_lc=True), line2)
        out.append(line2)
    return "\n".join(out)


# ── W0l: the two '×'-as-'3' prose SHAPES W0k's single-line word-pair regex ────
# cannot reach (NORMALIZATION_VERSION 1.9.43, 2026-07-04). Same broken-ToUnicode
# AdvPS… font as W0i/W0k (the `×` glyph decodes as `3`). Both were the residual
# efendic_2022_affect findings left open after v2.4.112 (W0k), documented in
# an internal findings doc (2026-07-03).
#
#   A · FACTORIAL DESIGN NOTATION — `<digit> (…) 3 <digit> (…) [3 <digit> (…)]`
#       "2 (Between-subject factor--Direction: …) 3 2 (Between-subject factor--
#        Manipulated Attribute: …) 3 3 (Within-subject factor--…) mixed-subject
#        design"  ->  each `) 3 <digit> (` boundary's `3` is a corrupted `×`
#        (the trailing digit is the real factor SIZE, e.g. `× 2`, `× 3`).
#       W0k's `Word 3 Word` regex needs LETTER flanks; here the `3` sits between
#       a `)` and a `<digit> (`, so W0k never sees it. The `3`-as-`×` here is the
#       single most dangerous prose glyph (a genuine paren-flanked count), so it
#       fires ONLY when the boundary is tied to a genuine factor parenthetical —
#       EITHER (a) an immediately-adjacent parenthetical names a factor type
#       (between-/within-/mixed-subjects, repeated-measures), OR (b) BOTH sides
#       are factor-SIZE parens (a bare digit right before the `(`: `2 (`, `3 (` —
#       never `f(x)`, `(range 1)`, `(from level 3)`) AND the chain is closed
#       immediately by a `factorial|…-subjects|design` tail. A generic
#       `(min 1) 3 2 (max 5)` / a formula `f(x) 3 2 (y)` / `(from level 3) 3 2
#       (see note)` is left ALONE (neither branch matches).
#
#   B · LINE-WRAPPED INTERACTION TERM — a physical line ending `<Pred> 3` whose
#       NEXT line begins with a predictor word, inside an interaction context:
#       "the three-way interaction (Direction 3\nManipulated Attribute × CMA)"
#        ->  "… (Direction × Manipulated Attribute × CMA)".
#       The line wrap splits the `<Pred> × <Pred>` pair across two physical lines,
#       so W0k's per-line regex can't pair them. Fires ONLY when: the tail flank
#       is Title-Case, the next line's head flank is Title-Case, "interaction" is
#       in the two-line window, and the head is not a plural count noun.
#
# FP-validated 2026-07-04 (tmp/proto_times_residuals.py): a 16-case battery — a
# range recode `(min 1) 3 2 (max 5)`, a formula `f(x) 3 2 (y)`, `(from level 3)
# 3 2 (see note)`, `Scores (bin 1) 3 5 (bin 9) … design later`, `Model 3\n…`,
# `we ran 3\nstudies`, `interaction between condition and 3\ngroups`, an
# already-correct `2 (Sex) × 2 (Cond)` (idempotency) — changes NOTHING, while
# both efendic shapes recover fully. A wide corpus render scan runs before ship.
# Wired into channel 1 (normalize_text) AND channel 3 (render post-process),
# like W0j/W0k (glyph-fixes-need-all-three-text-channels).
_TIMES_FACTOR_KW_RE = re.compile(
    r"between[- ]?subjects?|within[- ]?subjects?|mixed[- ]?subjects?|"
    r"between[- ]?groups?|within[- ]?groups?|repeated[- ]?measures",
    re.IGNORECASE,
)
_TIMES_DESIGN_BOUNDARY_RE = re.compile(r"\)\s*3\s+\d\s*\(")
_TIMES_DIGIT_PAREN_OPEN_RE = re.compile(r"(?<![\w.])\d\s*\($")
_TIMES_DESIGN_TAIL_RE = re.compile(
    r"^\s*(?:mixed[- ]?subjects?|between[- ]?subjects?|within[- ]?subjects?|"
    r"factorial|repeated[- ]?measures)?\s*(?:factorial\s+)?design\b",
    re.IGNORECASE,
)
_TIMES_WRAP_TAIL_RE = re.compile(r"(?<![\w.])([A-Z][A-Za-z]+)(\s*)3\s*$")
_TIMES_WRAP_HEAD_RE = re.compile(r"^\s*([A-Za-z]{2,})")


def _times_paren_span_before(s: str, close_idx: int) -> str:
    """Text of the parenthetical whose ')' is at close_idx (scan back to the
    matching '('; factor descriptions carry no nested parens)."""
    depth = 0
    for k in range(close_idx, -1, -1):
        if s[k] == ")":
            depth += 1
        elif s[k] == "(":
            depth -= 1
            if depth == 0:
                return s[k: close_idx + 1]
    return ""


def _times_paren_span_after(s: str, open_idx: int) -> str:
    """Text of the parenthetical whose '(' is at open_idx."""
    depth = 0
    for k in range(open_idx, len(s)):
        if s[k] == "(":
            depth += 1
        elif s[k] == ")":
            depth -= 1
            if depth == 0:
                return s[open_idx: k + 1]
    return ""


def recover_times_design_notation(text: str) -> str:
    """W0l-A: recover '×'-as-'3' in factorial-design notation `<digit>(…) 3
    <digit>(…)`. See the block comment above for the two firing branches (an
    adjacent factor-type parenthetical, or a factor-size chain closed by a
    design tail). Matches paragraph-wise on a newline-flattened copy so a factor
    parenthetical that wraps physical lines is one span (newline→space is 1:1,
    so char offsets remap directly)."""
    if "3" not in text or ")" not in text:
        return text
    paras = re.split(r"(\n\s*\n)", text)
    out = []
    for chunk in paras:
        if "3" not in chunk or ")" not in chunk:
            out.append(chunk)
            continue
        flat = chunk.replace("\n", " ")
        flip: list[int] = []
        for m in _TIMES_DESIGN_BOUNDARY_RE.finditer(flat):
            three_off = flat.find("3", m.start(), m.end())
            close_idx = flat.rfind(")", m.start(), three_off)
            open_idx = flat.find("(", three_off, m.end())
            left_paren = _times_paren_span_before(flat, close_idx) if close_idx >= 0 else ""
            right_paren = _times_paren_span_after(flat, open_idx) if open_idx >= 0 else ""
            fire = bool(
                _TIMES_FACTOR_KW_RE.search(left_paren)
                or _TIMES_FACTOR_KW_RE.search(right_paren)
            )
            if not fire and left_paren and right_paren:
                lp_start = flat.rfind(left_paren, 0, close_idx + 1)
                rp_end = open_idx + len(right_paren)
                left_is_size = bool(_TIMES_DIGIT_PAREN_OPEN_RE.search(flat[: lp_start + 1]))
                right_is_size = bool(re.search(r"(?<![\w.])\d\s*$", flat[:open_idx]))
                tail_ok = bool(_TIMES_DESIGN_TAIL_RE.match(flat[rp_end:]))
                fire = left_is_size and right_is_size and tail_ok
            if fire:
                flip.append(three_off)
        if not flip:
            out.append(chunk)
            continue
        chars = list(chunk)  # offsets identical to flat (newline→space 1:1)
        for off in flip:
            if off < len(chars) and chars[off] == "3":
                chars[off] = "×"
        out.append("".join(chars))
    return "".join(out)


def _times_wrap_head_is_count(head: str) -> bool:
    return head.lower().rstrip(".,;:)") in _TIMES_COUNT_NOUNS


def recover_times_wrapped_interaction(text: str) -> str:
    """W0l-B: recover '×'-as-'3' in a line-wrapped interaction term — a physical
    line ending `<PredWord> 3` whose next non-empty line begins with a predictor
    word, inside an "interaction" context. Joins the trailing `3` → `×`. See the
    block comment above for the guards."""
    if "3" not in text:
        return text
    lines = text.split("\n")
    for i in range(len(lines) - 1):
        m_tail = _TIMES_WRAP_TAIL_RE.search(lines[i])
        if not m_tail:
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            continue
        m_head = _TIMES_WRAP_HEAD_RE.match(lines[j])
        if not m_head:
            continue
        left, head = m_tail.group(1), m_head.group(1)
        if not (_times_flank_is_predictor(left) and _times_flank_is_predictor(head)):
            continue
        # Reference-word ordinal guard (same as W0k's _sub): a tail like
        # "FIGURE 3" / "Table 3" / "Model 3" is a genuine ordinal — a figure /
        # table / model NUMBER — not a corrupted interaction `×`, even when the
        # next line starts Title-Case and "interaction" is in the window (a
        # figure/table caption routinely reads "Table 3\nMain-effects and
        # interactions"). Reject when the tail flank is a reference word.
        if left.lower() in _TIMES_REFERENCE_WORDS_SET:
            continue
        if "interaction" not in (lines[i] + " " + lines[j]).lower():
            continue
        if _times_wrap_head_is_count(head):
            continue
        sp = m_tail.group(2) if m_tail.group(2) else " "
        lines[i] = lines[i][: m_tail.start()] + f"{left}{sp}×"
    return "\n".join(lines)


# W0n WAS HERE AND IS DELETED (v2.4.130, 2026-08-14).
#
# It restored a dropped decimal point in a p-value significance threshold
# (`p < 05` -> `p < .05`), on the theory that a DOTLESS leading-zero-free
# threshold after a p-comparator "is provably corrupt" because APA writes
# `.05`.
#
# THE PREMISE WAS FALSE, and the disproof is the strongest single result of the
# 2026-08-14 audit: **the same text shape has OPPOSITE OWNERS in two real
# English papers.** Both verdicts reached by RASTERIZING the page — never by
# asking an extractor, because "pdftotext cannot see it" is not "it is not
# there".
#
#   10.1016/j.jesp.2009.12.011 p3   PRINTS  `t(87) = 2.01, p < 05`   NO DOT
#       The AUTHOR dropped the period. 6 of the 7 `p <` sites on that page
#       carry the dot; the `<`-to-digit advance is 2.00pt where a dotted site
#       on the same page measures 3.90pt; there is NO rect/curve/line object
#       in the gap, so no vector-painted dot; the page is natively typeset
#       with no images. W0n was LAUNDERING a published typo.
#
#   10.1177/0956797613482946 p6     PRINTS  `F(2, 93) = 5.69, p < .05`  DOT
#       Ours: page 6 is a SCAN with an OCR text layer in base-14 fonts, and
#       the same pass renders `F(2, 93)` as `K2, 93)` and Greek eta-squared-p
#       as `^p'`. The dot was lost by our extraction.
#
# A LAYOUT GATE TO SEPARATE THEM WAS BUILT AND REFUTED. Calibrated on
# advance-width ratio (0.51 dotless vs 0.99 dotted) it looked decisive, and it
# is worthless: Dong's char boxes come from an OCR ENGINE rather than the
# typesetter, so the gate manufactures its own evidence for exactly the case it
# exists to catch. It is broken independently by justified-text stretch, by
# mixed styles on one page, by pages with no healthy site to calibrate against,
# and by the fact that pdfplumber's `x0`/`x1` are glyph BOUNDING BOXES rather
# than advances.
#
# So the ambiguity is irreducible from the text, and irreducible from the
# layout. **Under irreducible ambiguity the default is PASS-THROUGH**, because
# pass-through is reversible for the consumer and a repair is not: the source
# token stays intact and the consumer can still decide, which it could not once
# we had already rewritten it. Directive 2026-08-13 — docpluck extracts and
# normalizes what is PRINTED; flagging a suspected author error is ESCImate's
# and Scimeto's role, because they have the UI and the mandate for it.
#
# STATED CONSEQUENCE, not hidden: where the dot really was ours to restore
# (Dong), the consumer now receives `p < 05` and must decide for itself. That
# is a coverage change, it was measured before the decision, and it was
# accepted by the owner of every consumer on 2026-08-14.
#
# Pinned by tests/test_p_threshold_decimal_real_pdf.py, re-fixtured rather than
# deleted so both papers keep carrying their evidence.
# See docs/SCOPE.md and LESSONS.md L-031 trap 1.

# v2.4.40 (NORMALIZATION_VERSION 1.9.6): recover standalone '2'-for-U+2212
# minus corruption on point-estimate tokens/cells that the bracket-pair rule
# (recover_corrupted_minus_signs) cannot reach because they carry no bracket
# of their own. The discriminator is a structural invariant of statistics,
# not a heuristic: a point estimate ALWAYS lies inside its own reported
# confidence interval. So when a token reads "2X.XX" and the SAME record (a
# table row <tr>…</tr>, or a single text line) carries a CI bracket [lo, hi]
# such that the de-corrupted value -X.XX falls inside [lo, hi] while the
# literal 2X.XX falls outside, the token is unambiguously a corrupted
# negative. A genuine literal 2X.XX is never "recovered": that would require
# a stats record whose estimate sits outside the CI it is paired with — which
# does not occur. efendic_2022 Tables 2-5 every negative B-coefficient cell +
# the Mposterior mediation estimates are recovered this way; the bracketed
# CIs themselves are already handled upstream by recover_corrupted_minus_signs.
_CI_PAIR_BRACKET_RE = re.compile(r"\[\s*(-?\d*\.?\d+)\s*,\s*(-?\d*\.?\d+)\s*\]")
# A corrupted negative point estimate: a leading '2' (the mis-mapped minus)
# glued to a small decimal of the form D.DD — one integer digit, then the
# fraction. Not preceded by a digit/dot (so we never match inside 120.26),
# AND not preceded by a literal minus (so we never re-recover an already-
# recovered `-2.68`, which would yield `--.68`). Cycle 10 (v2.4.62) — the
# missing `-` in the lookbehind was the cause of `normalize_text` non-
# idempotence on ip-feldman 2025 (the value first recovers correctly as
# `-2.68`, then pass 2 re-fires and corrupts it to `--.68`).
# ── the shared "this token is ALREADY signed" guard (v2.4.128) ───────────
#
# Three sibling W0 patterns each need to refuse a token that already carries a
# sign, and each had written the guard out separately:
#
#     _CORRUPT_NEG_TOKEN_RE   (?<![\d.\-])     hyphen-minus only
#     _PROSE_CODING_NEG_RE    (?<![\d.\-−])    hyphen-minus + U+2212
#     _BARE_POS_TOKEN_RE      (?<![\d.\-])     hyphen-minus only
#
# One guard, three spellings, written at three different times — and the drift
# was a WRONG NUMBER in the production path, not a tidiness issue:
#
#     'B = <U+2212>20.09, 95% CI [-0.21, 0.04]'  ->  'B = --0.09, ...'
#
# W0d runs at the `recover_minus_via_ci_pairing` call below, and S5 does not
# fold U+2212 to ASCII until much later in `normalize_text`, so W0d sees the raw
# glyph. The estimate's minus sailed past a hyphen-only guard and the recovery
# signed the number a SECOND time. `--0.09` is not merely wrong, it is
# unparseable by every consumer. The comment above records that the ASCII case
# already caused exactly this (`-2.68` -> `--.68`, a non-idempotence bug in
# v2.4.62); the fix then covered the one dash form in front of us.
#
# The set is the dash forms scientific typography actually uses AS A SIGN.
# U+2014 EM DASH is deliberately absent: it is sentence punctuation, never a
# numeric sign, so a digit run after one is a candidate like any other. That is
# a decision with a reason rather than an omission.
_SIGNED_DASHES = "\\-\u2010\u2011\u2012\u2013\u2212\ufe63\uff0d"
_ALREADY_SIGNED = rf"(?<![\d.{_SIGNED_DASHES}])"

# ...AND THE SIGN MAY BE DETACHED. `_ALREADY_SIGNED` is a ONE-CHARACTER
# lookbehind, so it refuses `-0.38` and accepts `- 0.38`, where the character
# before the token is a space. On a detached sign W0g therefore read a
# bare-positive estimate, proved it negative from the CI, and emitted
# `d = - -0.38` — a double-signed effect size no paper printed.
#
# The comment above records that `-2.68 -> --.68` already happened once
# (v2.4.62) and that "the fix then covered the one dash form in front of us".
# It covered the ATTACHED form; this is the DETACHED one, and pdftotext produces
# it routinely on the fonts that motivated these rules at all — confirmed on
# `10.1016/j.jesp.2021.104154` p13, whose printed `d = −0.38, 95% CI
# [−0.58, −0.18]` arrives with every minus separated from its digit.
#
# A function rather than a wider lookbehind because Python requires fixed-width
# lookbehinds, and the gap is an unbounded whitespace run (it can be a line
# wrap). Applied at the decision point, where the whole preceding text is in
# hand.
_TRAILING_SIGN_RE = re.compile(rf"[{_SIGNED_DASHES}]\s*$")


def _already_carries_a_sign(text_before: str) -> bool:
    """True when the token starting at the end of ``text_before`` is already
    signed — including a sign DETACHED from it by spaces or a line break."""
    return bool(_TRAILING_SIGN_RE.search(text_before))

_CORRUPT_NEG_TOKEN_RE = re.compile(_ALREADY_SIGNED + r"2(\d?\.\d+)\b")
_TABLE_ROW_RE = re.compile(r"<tr\b.*?</tr>", re.DOTALL | re.IGNORECASE)


# Cycle 11 (v2.4.63) / 12 (v2.4.64) — proximity gate for the CI-pairing recovery.
#
# In stat reporting a BARE bracket `[lo, hi]` attaches to the IMMEDIATELY-
# preceding point estimate; a LABELED bracket `CI = [lo, hi]` or
# `95% CI [lo, hi]` can attach to ANY earlier point estimate on the same
# row (the SD/SE/df-pair tokens in between are descriptive of the same
# estimate). The cycle 11 proximity gate treated both as needing strict
# adjacency, which broke efendic's body-line recovery
#   `Mposterior = 20.54, SD=0.04, CI = [-0.61, -0.47]`
# where `, SD=` falsely tripped the "new stat label" sentence-break check.
#
# Cycle 12 fix: discriminate LABELED vs BARE brackets.
#   - LABELED bracket (`CI =`/`95% CI`/`CI:` immediately precedes `[`):
#     pairs with any candidate token in its record (the old wide rule).
#   - BARE bracket: pairs ONLY with candidates within 30 chars + no
#     sentence break (period/semicolon + space — NOT comma + new label,
#     because stat-row labels are comma-separated by convention).
#
# This keeps the majumder fix (bare bracket far from `2.01`) AND
# preserves efendic-style labeled CIs that pair across SD/SE annotations.
_CI_PAIR_MAX_GAP = 30
# Bare-bracket sentence break: only period/semicolon + space.  A comma is
# NOT a break because stat rows are comma-separated.  The majumder false-
# positive is now caught by the per-bracket proximity check (the bare
# bracket sits ~50 chars after `2.01` — beyond _CI_PAIR_MAX_GAP).
_SENTENCE_BREAK_RE = re.compile(r"[.;]\s")
# A bracket is "labeled" when prefixed by `CI`, `95 % CI`, or similar
# directly before the opening `[`. Allow optional whitespace and an `=` /
# `:` between the label and the bracket.
_CI_LABEL_PREFIX_RE = re.compile(r"(?:\bCI|\b\d+\s*%\s*CI)\s*[=:]?\s*$", re.IGNORECASE)
# Cycle 13 (v2.4.65) — even a LABELED CI cannot reach back ACROSS an
# independent-test-statistic label. The discriminator: between the
# candidate token and the labeled bracket, allow ONLY variance-family
# labels (SD, SE, M, Mdn, Var, CI, 95% CI itself, %), reject anything
# that introduces a NEW estimate (t, F, p, d, g, η, χ, r, R², β, OR, RR,
# HR, B, Z, Q).
#
# Why: `Mposterior = 20.54, SD=0.04, CI = [-0.61, -0.47]` (efendic) has
# only SD between the candidate and the CI — same estimate, paired OK.
# `M = 5.37, SD = 2.01, t(1827) = 1.83, p tukey = .067, d = 0.09, 95% CI
# [-0.006, 0.18]` (majumder) has t, p, d — three independent estimates —
# between `2.01` and the CI; the CI is for `d`, not `2.01`. Reject.
_INDEPENDENT_STAT_BETWEEN_RE = re.compile(
    r"(?:^|[,;\s])\s*"
    r"(?:t|F|d|g|R|R²|β|γ|B|OR|RR|HR|H|Q|Z|f|n|η|χ|η²|χ²|r|"
    r"p\s+tukey|p\s+holm|p\s+bonf(?:erroni)?|p\s+adj|"
    r"\bp(?:\s*[=<>]))"
    r"\s*[=(\(]",
)


def _recover_minus_in_record(record: str) -> str:
    """Recover '2X.XX' tokens in a single record (a table row or a text line)
    by pairing each with a CI bracket present in the same record."""
    # v2.4.102: an HTML table ROW is column-structured — each statistic sits in
    # its own <td> cell and the CI column pairs with the estimate column of the
    # SAME row by table geometry, not by prose adjacency. Camelot emits each
    # <td> on its own line, so a B-column estimate and its CI cell are separated
    # by the intervening SE cell (`</td>\n <td>-0.06</td>\n <td>`), which pushes
    # the char-gap well past the 30-char BARE-bracket cap (efendic: 37 chars) —
    # the recovery fired in the DISABLE_CAMELOT unstructured-table channel but
    # silently missed every negative B-coefficient in the Camelot HTML-table
    # channel (the production default). Inside a table row we therefore treat a
    # bare bracket with the SAME relaxed proximity as a labeled bracket: pair
    # across intervening cells UNLESS an independent-stat label intervenes
    # (_INDEPENDENT_STAT_BETWEEN_RE still guards it). A prose text line (no <td>)
    # keeps the strict 30-char cap, so the majumder false-positive stays blocked.
    is_html_table_row = "<td" in record or "<th" in record
    # Each entry: (lo, hi, (bs, be), is_labeled). `is_labeled` is True when
    # the bracket is prefixed by `CI`/`95% CI`/etc. — see cycle 12 notes
    # at _CI_LABEL_PREFIX_RE.
    brackets: list[tuple[float, float, tuple[int, int], bool]] = []
    for m in _CI_PAIR_BRACKET_RE.finditer(record):
        try:
            lo, hi = float(m.group(1)), float(m.group(2))
        except ValueError:
            continue
        if lo > hi:
            continue  # not a well-formed interval
        # Look back ≤8 chars for a `CI` / `95 % CI` label.
        bs, be = m.span()
        prefix = record[max(0, bs - 8): bs]
        is_labeled = bool(_CI_LABEL_PREFIX_RE.search(prefix))
        brackets.append((lo, hi, (bs, be), is_labeled))
    if not brackets:
        return record

    def _sub(m: "re.Match[str]") -> str:
        # Never touch a token that lies inside a bracket span (a CI bound).
        for _lo, _hi, (bs, be), _lab in brackets:
            if bs <= m.start() < be:
                return m.group(0)
        # Never sign a value that is ALREADY signed, even when the sign is
        # DETACHED from its digits by whitespace or a line wrap. See
        # `_already_carries_a_sign` — the one-character lookbehind cannot see
        # past the space, and a detached sign is exactly what the fonts these
        # rules exist for produce.
        if _already_carries_a_sign(record[: m.start()]):
            return m.group(0)
        frac = m.group(1)
        try:
            literal = float("2" + frac)
            recovered = float("-" + frac)
        except ValueError:
            return m.group(0)
        # Cycle 12: pick the NEAREST bracket whose pairing rules accept this
        # token. LABELED brackets accept any candidate in the record (legacy
        # wide rule — efendic body line `Mposterior = 20.54, SD=0.04,
        # CI = [-0.61, -0.47]` is the canonical case). BARE brackets only
        # accept the immediately-preceding stat (within 30 chars, no
        # sentence break) — this is what blocks the majumder false-positive
        # `M = 5.37, SD = 2.01, t = ..., d = 0.09 [-1.86, 0.04]`.
        token_end = m.end()
        nearest = None
        nearest_dist = None
        for lo, hi, (bs, be), is_labeled in brackets:
            if bs < token_end:
                continue
            gap = bs - token_end
            intervening = record[token_end:bs]
            # A bracket never pairs back ACROSS an independent test statistic —
            # the CI belongs to the estimate in the cell/token immediately
            # before it, not to an earlier one. This guard applies to EVERY
            # bracket kind. (v2.4.102: previously only labeled brackets ran it,
            # so a bare bracket within 30 chars but separated by another stat —
            # `M = 5.37, SD = 2.01, t(1827)=1.83, d = 0.09 [-1.86, 0.04]`, where
            # the CI is `d`'s — wrongly recovered `SD = 2.01` to `-.01`. The
            # gap check alone missed it because that variant is only 25 chars.)
            if _INDEPENDENT_STAT_BETWEEN_RE.search(intervening):
                continue
            if is_labeled or is_html_table_row:
                # Labeled bracket, OR any bracket inside an HTML table row:
                # relaxed proximity. For a labeled bracket the `CI`/`95% CI`
                # label gates the pairing to the variance-family (SD/SE/M/CI/%)
                # of the SAME estimate; for a table row the column structure
                # does the same job (the estimate column pairs with the CI
                # column of the same row, across the intervening SE cell). The
                # independent-stat guard above already rejects a new estimate.
                pass
            else:
                # Prose bare bracket: keep the strict distance cap on top of the
                # independent-stat guard (belt-and-suspenders for prose).
                if gap > _CI_PAIR_MAX_GAP:
                    continue
                if _SENTENCE_BREAK_RE.search(intervening):
                    continue
            if nearest_dist is None or gap < nearest_dist:
                nearest = (lo, hi)
                nearest_dist = gap
        if nearest is None:
            return m.group(0)
        lo, hi = nearest
        # v2.4.123: a CI whose LOWER bound is >= 0 is an entirely non-negative
        # interval. The containment invariant "the recovered (negative) reading
        # falls inside the CI while the literal does not" is then satisfied only
        # by the degenerate `-.00 ∈ [.00, .09]` case — the flipped value clips
        # the interval's zero edge — which is evidence of a MIS-PAIRING, not of
        # corruption: a genuinely negative estimate cannot have a wholly
        # non-negative CI.
        #
        # maier_2023_collabra Table 9 is the canonical failure. The row is
        # `Target article | 1, 114 | 2.00 | .16 | N/A | .02 | [.00, .09]` — an
        # F-statistic, its p, its partial eta-squared, and the CI OF THE
        # ETA-SQUARED. W0d paired F=2.00 with the eta² CI and rendered
        # **F = -.00**, which is impossible: F is a ratio of sums of squares and
        # is non-negative by construction. Both text channels confirm the source
        # reads 2.00, so the library manufactured the sign.
        #
        # Rejecting the pairing (rather than adding an F-specific rule) is the
        # general form: it keys on the ARITHMETIC of the interval, so it holds
        # for every non-negative statistic that can sit beside a non-negative CI
        # (F, chi-square, R², eta², odds ratios, variance components) without
        # enumerating them — and it cannot disarm a real recovery, because a
        # genuinely negative estimate always has a CI that admits negatives.
        if lo >= 0:
            return m.group(0)
        in_recovered = (lo - 0.005) <= recovered <= (hi + 0.005)
        in_literal = (lo - 0.005) <= literal <= (hi + 0.005)
        if in_recovered and not in_literal:
            return "-" + frac
        return m.group(0)

    return _CORRUPT_NEG_TOKEN_RE.sub(_sub, record)


def recover_minus_via_ci_pairing(text: str) -> str:
    """W0d: recover standalone '2'-for-minus corruption via point-estimate ∈ CI.

    Operates on whole records — a ``<tr>…</tr>`` table row, or a single text
    line — so a corrupted ``2X.XX`` point estimate can be checked against the
    confidence interval reported alongside it. See the module comment above
    ``_CI_PAIR_BRACKET_RE`` for the invariant this relies on.
    """
    if not text or "2" not in text:
        return text
    text = _TABLE_ROW_RE.sub(lambda m: _recover_minus_in_record(m.group(0)), text)
    out = []
    for line in text.split("\n"):
        if "[" in line and "2" in line:
            out.append(_recover_minus_in_record(line))
        else:
            out.append(line)
    return "\n".join(out)


# ── W0j: '2'-for-U+2212 minus in BODY PROSE that carries NO bracket CI ──────
# (NORMALIZATION_VERSION 1.9.40, 2026-07-03). W0b/W0d recover the '2'-for-minus
# glyph when a bracketed CI is present to pair against (or inside a <tr>). Two
# PROSE shapes carry the same corruption with NO bracket, so they slip every
# existing recovery — found on efendic_2022_affect by an independent canary
# audit (the A1/A2 table-cell fixes had left the body-prose channel corrupt;
# `glyph-fixes-need-all-three-text-channels`):
#
#   A · contrast-coding note:
#       "direction: 20.5 = low, + 0.5 = high"  ->  "-0.5 = low, +0.5 = high"
#     A ±k contrast code always names BOTH signs. The "+ 0.5 = <word>" twin on
#     the SAME line is the disambiguator: a "2X.X = <word>" whose |X.X| twin is
#     also present as "+ X.X = <word>" is the NEGATIVE arm, i.e. the leading 2 is
#     a corrupted minus. Without the +twin the token is left ALONE (a bare
#     "20.5 = ..." could be a genuine value).
#
#   B · change/difference M-statistic:
#       "Mchange = 20.14"  ->  "Mchange = -0.14"
#     This CANNOT key on magnitude — a corrupted "-0.14" and a genuine mean age
#     "20.14" have identical digits. The ONLY safe disambiguator is the
#     SUBSCRIPT: a change / difference / posterior-effect statistic is small and
#     legitimately negative; a bare M / Mage is a raw mean (~20 for age) and must
#     NEVER be flipped. So B fires ONLY when the M carries a difference-type
#     subscript (change/diff/difference/posterior/delta/gain/shift).
#
# FP-validated 2026-07-03: a 6-case adversarial battery (incl. "mean age of
# M = 20.14 years", "20.5% women", ordinary "1 = control, 2 = treatment",
# "M = 2.84") changes NOTHING; a 20-paper rendered-corpus scan fires ONLY on
# efendic (the target). Wired into channel 1 (normalize_text) AND channel 3
# (render_pdf_to_markdown post-process) per the 3-channel glyph discipline.
_PROSE_CODING_NEG_RE = re.compile(
    _ALREADY_SIGNED + r"2(\d\.\d+)(\s*=\s*)([A-Za-z])"
)
_PROSE_CODING_TWIN_RE = re.compile(r"\+\s*(\d\.\d+)\s*=\s*[A-Za-z]")
_PROSE_MSTAT_CHANGE_RE = re.compile(
    r"(\bM(?:change|diff|difference|posterior|delta|gain|shift)\s*=\s*)2(\d\.\d+)",
    re.IGNORECASE,
)


def recover_prose_two_for_minus(text: str) -> str:
    """W0j: recover '2'-for-U+2212 minus in body-prose contrast-coding notes and
    change/difference M-statistics that carry no bracket CI to pair against.

    See the block comment above for the two structural signatures and the
    disambiguators (the ``+ X.X = <word>`` contrast twin for the coding note; the
    difference-type subscript for the M-statistic). Both are line-local and tight
    enough that a 6-case FP battery + 20-paper corpus scan showed zero false
    positives — only the efendic target changed.
    """
    if not text or "2" not in text:
        return text
    out = []
    for line in text.split("\n"):
        # Signature A: only when a "+ X.X = <word>" contrast twin is on the line.
        twins = {m.group(1) for m in _PROSE_CODING_TWIN_RE.finditer(line)}
        if twins:
            def _repl_a(m: "re.Match[str]") -> str:
                # Same detached-sign guard as W0d/W0g. `- 20.5 = low` is already
                # signed; signing it again emits `- -0.5`.
                if _already_carries_a_sign(line[: m.start()]):
                    return m.group(0)
                if m.group(1) in twins:
                    return "-" + m.group(1) + m.group(2) + m.group(3)
                return m.group(0)
            line = _PROSE_CODING_NEG_RE.sub(_repl_a, line)
        # Signature B: difference-type M-statistic.
        #
        # EVIDENCE CLASS: **INFERENTIAL** — the ruling register O8 asked for, and
        # it is recorded here rather than only in a doc, because a ruling that
        # lives in prose is a claim about the code and not a property of it.
        #
        # Signature A is inferential too but self-corroborating: the `+ X.X =
        # <word>` twin ON THE SAME LINE is a second token the renderer emitted,
        # and a ±k contrast code always names both arms. B has no such witness.
        # It decides from the variable NAME (`Mchange`), and a name is not
        # something the renderer put on the page — `20.14` is not grammatically
        # impossible in that slot, merely implausible for a difference score.
        # That is exactly the judgement docpluck assigns to consumers, who hold
        # the parsed statistic and a UI to flag it.
        #
        # KEPT, narrowly, and DECLARED. Retiring it moves work onto consumers who
        # have not been told yet, and the owner alone may make that call. What it
        # must not do is fire silently, which is what it did until v2.4.134.
        def _repl_b(m: "re.Match[str]") -> str:
            record_fallback("w0j_mstat_sign_inferred_from_variable_name",
                            detail=m.group(0)[:40])
            return m.group(1) + "-" + m.group(2)

        line = _PROSE_MSTAT_CHANGE_RE.sub(_repl_b, line)
        out.append(line)
    return "\n".join(out)


# §A R5 / B7 (NORMALIZATION_VERSION 1.9.23, 2026-05-23): recover the DROPPED
# minus-sign class — distinct from W0d's '2'-for-U+2212 corruption. Here
# pdftotext emits no glyph at all for the leading U+2212, so a coefficient
# `b = -.022` reaches us as `b = .022`. The sign-flip is silent and breaks
# every downstream statistical interpretation.
#
# The recovery uses the SAME structural invariant W0d uses (a point estimate
# lies inside its own CI), applied differently: the candidate token here is a
# bare positive `.NNN` or `D.NNN` — NOT prefixed by '2'. We can only flip the
# sign when a CI bracket on the same row mathematically REQUIRES it: the
# bracket DOES contain the recovered negative AND DOES NOT contain the literal
# positive. A bracket that contains both (e.g. `[-0.05, 0.10]` paired with
# `0.022`) is ambiguous → no flip. A bracket that contains only the positive
# is also a no-flip (the literal value is consistent).
#
# Conservative gates (mandatory; no general "bare beta might be negative"
# warner — that would fire on thousands of legitimate positive betas):
#   1. Token shape: leading `\.` or `\d\.` decimal (≤2 leading digits) on a
#      word boundary, not already preceded by `-` / digit / dot. Excludes
#      "1.23" / "0.05" / "(1.5%)" etc.
#   2. A CI bracket [lo, hi] exists in the same record AND lo < 0 (we never
#      flip on a strictly-positive bracket — that would be a false-positive
#      on legitimate positive coefficients reported alongside positive CIs).
#   3. The recovered negative falls inside [lo, hi] AND the literal positive
#      falls strictly OUTSIDE [lo, hi] (the same record-internal sign-flip
#      proof W0d relies on).
_BARE_POS_TOKEN_RE = re.compile(_ALREADY_SIGNED + r"(\d?\.\d+)\b")
# A signed-negative numeric value: a real minus (ASCII '-' or U+2212) glued to a
# decimal. Used by the A3 guard below to detect that the point estimate the CI
# belongs to ALREADY sits between the candidate token and the CI — meaning the
# candidate is a later (variance / SE) column that must not be flipped.
_SIGNED_NEG_NUM_RE = re.compile(r"[-−]\d*\.\d+")


def _recover_dropped_minus_in_record(record: str) -> str:
    """Recover bare positive decimal tokens whose paired CI bracket proves
    the published value is negative (the minus glyph was dropped pre-emit).

    Conservative: only fires when the CI bracket [lo, hi] has lo < 0 AND the
    recovered -X.XX is inside the bracket AND the literal X.XX is outside.
    """
    if "[" not in record:
        return record
    brackets: list[tuple[float, float, tuple[int, int], bool]] = []
    for m in _CI_PAIR_BRACKET_RE.finditer(record):
        try:
            lo, hi = float(m.group(1)), float(m.group(2))
        except ValueError:
            continue
        if lo > hi or lo >= 0:
            # Only intervals that span negative space are safe: a strictly-
            # positive bracket cannot prove a sign-flip without ambiguity.
            continue
        bs, be = m.span()
        prefix = record[max(0, bs - 8): bs]
        is_labeled = bool(_CI_LABEL_PREFIX_RE.search(prefix))
        brackets.append((lo, hi, (bs, be), is_labeled))
    if not brackets:
        return record

    def _sub(m: "re.Match[str]") -> str:
        # Never touch a token that lies inside any bracket span (CI bound).
        for _lo, _hi, (bs, be), _lab in brackets:
            if bs <= m.start() < be:
                return m.group(0)
        # Never sign a value that is ALREADY signed, even when pdftotext left
        # the sign detached from its digits. See `_already_carries_a_sign`.
        if _already_carries_a_sign(record[: m.start()]):
            return m.group(0)
        frac_with_lead = m.group(1)
        try:
            literal = float(frac_with_lead)
            recovered = -literal
        except ValueError:
            return m.group(0)
        if literal <= 0:
            return m.group(0)
        token_end = m.end()
        # Pick the NEAREST applicable bracket using the same labeled/bare
        # rules as W0d (so we don't over-attach across sentences or
        # independent-stat labels).
        nearest = None
        nearest_dist = None
        for lo, hi, (bs, be), is_labeled in brackets:
            if bs < token_end:
                continue
            gap = bs - token_end
            intervening = record[token_end:bs]
            if is_labeled:
                if _INDEPENDENT_STAT_BETWEEN_RE.search(intervening):
                    continue
            else:
                if gap > _CI_PAIR_MAX_GAP:
                    continue
                if _SENTENCE_BREAK_RE.search(intervening):
                    continue
            if nearest_dist is None or gap < nearest_dist:
                nearest = (lo, hi, bs)
                nearest_dist = gap
        if nearest is None:
            return m.group(0)
        lo, hi, nb_start = nearest
        # A3 guard (v2.4.104): do NOT flip a bare-positive token when a point
        # estimate the CI belongs to ALREADY appears — as a real negative —
        # EARLIER in the row than this token. In the standard "B | SE | CI"
        # table row the CI describes the B estimate; once B is recovered
        # (`-0.09`), the SE cell (`0.06`) is a LATER numeric column, and a
        # standard error legitimately falls OUTSIDE the estimate's CI (SE is not
        # bounded by [lo, hi]) — so in_recovered/in_literal would wrongly flip
        # the SE to `-0.06`. A standard error / SD is non-negative and is a
        # different column from the estimate the CI pairs with. If a
        # signed-negative number precedes this token (that negative is the
        # paired estimate, this token is a subsequent variance column), never
        # flip it. Only fires inside a structured table row, where the
        # column order B→SE→CI is the invariant; a prose line (no <td>) keeps the
        # original behavior so a genuinely-first dropped-minus estimate still
        # recovers.
        before_token = record[:m.start()]
        if ("<td" in record) and _SIGNED_NEG_NUM_RE.search(before_token):
            return m.group(0)
        in_recovered = (lo - 0.005) <= recovered <= (hi + 0.005)
        in_literal = (lo - 0.005) <= literal <= (hi + 0.005)
        # Strict requirement: recovered IN bracket, literal OUT. A bracket
        # containing both (ambiguous) is a no-flip.
        if in_recovered and not in_literal:
            return "-" + frac_with_lead
        return m.group(0)

    return _BARE_POS_TOKEN_RE.sub(_sub, record)


def recover_dropped_minus_via_ci_pairing(text: str) -> str:
    """W0g (R5 / B7): recover bare positive decimal tokens whose CI proves
    them negative (dropped-minus class). Distinct from ``recover_minus_via_ci_pairing``
    (W0d), which handles the '2'-for-U+2212 corruption class."""
    if not text or "[" not in text:
        return text
    text = _TABLE_ROW_RE.sub(
        lambda m: _recover_dropped_minus_in_record(m.group(0)), text
    )
    out = []
    for line in text.split("\n"):
        if "[" in line:
            out.append(_recover_dropped_minus_in_record(line))
        else:
            out.append(line)
    return "\n".join(out)


# §A R5 / B7 (NORMALIZATION_VERSION 1.9.35, 2026-06-15): recover the DROPPED
# minus class that W0g's CI-pairing CANNOT reach -- a coefficient reported with
# only a t/p value and NO confidence interval (`b = -.022, t(87) = .17`).
# pdftotext drops the U+2212 glyph entirely on tight-kerned PDFs that draw the
# minus in a dedicated symbol font; W0g needs a CI bracket to prove the sign, so
# a bare `b = .022` with no CI is left silently sign-flipped (the sign-flip
# inverts the statistical conclusion -- a catastrophic class for a meta-science
# tool). This pass reads the minus directly from the LAYOUT channel
# (pdfplumber), where the dropped glyph survives as an unmapped `(cid:N)`
# symbol-font character touching the coefficient.
#
# Structural signature (general -- NOT keyed on any paper/font identity):
#   In the layout, an UNMAPPED `(cid:N)` glyph that (a) immediately precedes a
#   coefficient token `.NNN` / `D.NNN` with a near-zero x-gap, AND (b) whose
#   nearest non-space neighbour to the LEFT is `=` (the operator slot of a
#   `<stat> = <minus><coef>` assignment). The same coefficient appears in the
#   pdftotext TEXT without a leading minus. We then flip exactly the text
#   coefficients the layout proves negative -- never one the layout did not flag.
#
# The `=`-anchor pins the glyph to the point-estimate operator slot: a `(cid:N)`
# between two numbers (`5.2 ± 0.3`) or after a digit is never matched, so a
# dropped `±` / `≈` / footnote-dagger can never be mistaken for a sign.
#
# LIMITATION (documented; see ar_apa_j_jesp_2009_12_011 beta -.245): a minus
# drawn as painted pixels -- absent from pdftotext AND pdfplumber
# chars/lines/rects/curves AND pdfminer's raw layer -- cannot be recovered from
# text or layout. That is an OCR-tier problem, outside docpluck's MIT
# text+layout architecture. W0h recovers the layout-visible subset and leaves a
# pixel-only minus untouched rather than guessing. See TODO.md R5 Path 1.
_CID_GLYPH_RE = re.compile(r"^\(cid:\d+\)$")
_LAYOUT_COEF_SHAPE_RE = re.compile(r"^\d?\.\d+$")  # .NNN or D.NNN


def _layout_line_text(line) -> str:
    """Reconstruct a layout line as readable text, inserting spaces at gaps.

    pdfplumber's char stream carries NO space characters — a space is an
    absence of glyphs — so joining chars directly yields
    ``"Thedatawasanalyzedusinga4"``. That glues every word together, and the
    context matcher downstream compares WORD tokens against pdftotext's spaced
    text, where nothing would ever match. A gap wider than a fraction of the
    glyph size is a word boundary.
    """
    out: list[str] = []
    prev = None
    for d in line:
        t = str(d.get("text") or "")
        if prev is not None:
            gap = float(d.get("x0") or 0.0) - float(prev.get("x1") or 0.0)
            if gap > 0.28 * max(float(prev.get("size") or 0.0), 1.0):
                out.append(" ")
        out.append(t)
        prev = d
    return "".join(out).strip()


def _layout_negative_coefficient_sites(layout) -> list[dict]:
    """Every coefficient the layout proves negative, WITH the evidence's own
    location and surrounding line text.

    ## Why this replaced a bare ``{coef: count}`` (Risk A / register C1, F7f)

    The layout channel is **pdfplumber's** character stream; the substitution
    happens in **pdftotext's** text. Until v2.4.133 the bridge between them was
    a bare count: *"the layout found 2 negative `.022`s, so flip the first 2
    textual `= .022`s, left to right, ANYWHERE in the document."* The counts
    carried no page key and the rewrite ran over the whole document, so
    **a glyph proven on page 7 licensed flipping the first matching token on
    page 2** — fabricating a minus on a statistic that was never corrupt.

    That is the same class as the v2.4.131 OMML regression (a repair that emits
    a WRONG value rather than no value), sitting inside the rules everyone
    treats as safely typographic because they are gated on real glyph evidence.
    The evidence WAS real; the *assignment* of it to a token was positional.

    ## Why not page-scoping

    Page-index scoping looks like the obvious fix and does not work here:
    measured on `10.1177/19485506211056761`, by the time W0h runs the text
    carries **7 form feeds for a 12-page document** — earlier normalization
    steps consume them — so aligning text page *k* to layout page *k* is an
    off-by-k that produces a CONFIDENTLY WRONG pairing rather than an empty
    one. Anchoring on the evidence's own line text needs no page alignment.

    Returns one dict per proven site::

        {"num": ".022", "page": 5, "line": "b = .022, t(87) = .17"}
    """
    from .extract_layout import LayoutDoc  # local import (layout is optional)

    sites: list[dict] = []
    if not isinstance(layout, LayoutDoc):
        return sites
    for page_index, page in enumerate(layout.pages):
        chars = page.chars
        if not chars:
            continue
        for c in chars:
            if not _CID_GLYPH_RE.match(str(c.get("text") or "")):
                continue
            size = float(c.get("size") or 0.0) or 10.0
            ctop = float(c.get("top") or 0.0)
            cbot = float(c.get("bottom") or 0.0)
            # Visual line = chars whose y-range overlaps this glyph's. A minus
            # glyph sits ~0.4pt off its digits' baseline, so exact-`top`
            # bucketing orphans it (.88's cid at 352.7 vs digits at 352.3) —
            # y-overlap is robust to that vertical offset.
            line = [
                d for d in chars
                if float(d.get("bottom") or 0.0) > ctop + 0.5
                and float(d.get("top") or 0.0) < cbot - 0.5
            ]
            line.sort(key=lambda d: float(d.get("x0") or 0.0))
            try:
                i = next(k for k, d in enumerate(line) if d is c)
            except StopIteration:
                continue
            if i + 1 >= len(line):
                continue
            # (a) immediately followed by a coefficient (near-zero x-gap).
            nxt = line[i + 1]
            gap = float(nxt.get("x0") or 0.0) - float(c.get("x1") or 0.0)
            if gap > 0.30 * size:
                continue
            num = ""
            j = i + 1
            while j < len(line):
                t = str(line[j].get("text") or "")
                if len(t) == 1 and t in "0123456789.":
                    num += t
                    j += 1
                else:
                    break
            if not _LAYOUT_COEF_SHAPE_RE.match(num):
                continue
            # (b) nearest non-space neighbour to the LEFT is `=`.
            left = None
            k = i - 1
            while k >= 0:
                lt = str(line[k].get("text") or "").strip()
                if lt:
                    left = lt
                    break
                k -= 1
            if left != "=":
                continue
            # The evidence's OWN line, as the layout channel sees it. This is
            # what makes the later pairing identity-based instead of ordinal.
            sites.append({
                "num": num,
                "page": page_index,
                "line": _layout_line_text(line),
            })
    return sites


def _layout_negative_coefficients(layout) -> dict[str, int]:
    """Backward-compatible count view of :func:`_layout_negative_coefficient_sites`.

    Kept because the counts are still the right shape for telemetry and for
    tests that only assert "the layout proved N negatives". The REPAIR no
    longer uses this — a count cannot say *which* token it licenses.
    """
    counts: dict[str, int] = {}
    for site in _layout_negative_coefficient_sites(layout):
        counts[site["num"]] = counts.get(site["num"], 0) + 1
    return counts


def _layout_superscript_fusions(layout) -> list[tuple[str, str]]:
    """Find `(fused, base, marker)` runs the LAYOUT proves are superscripts.

    Returns `[(fused_token, repaired_token), ...]` in reading order.

    A footnote marker is typographically a superscript, but pdftotext renders a
    positioned glyph as an ordinary digit — the paper that motivated this
    (`10.1525/collabra.34606`) contains ZERO Unicode superscript codepoints, so
    the text channel has nothing to key on. Font size plus baseline are the only
    evidence, and they live here.
    """
    out: list[tuple[str, str]] = []
    for page in getattr(layout, "pages", ()) or ():
        chars = [c for c in (getattr(page, "chars", ()) or ())
                 if c.get("upright", True)]
        i = 0
        while i < len(chars):
            # a base run: digits (and separators) at one size, on one baseline
            j = i
            while (j < len(chars)
                   and chars[j]["text"] in "0123456789,."
                   and abs(chars[j]["size"] - chars[i]["size"]) < 0.01
                   and abs(chars[j]["top"] - chars[i]["top"]) < 0.01):
                j += 1
            if j == i or not any(c["text"].isdigit() for c in chars[i:j]):
                i += 1
                continue
            base_size, base_top = chars[i]["size"], chars[i]["top"]
            # a marker run: digits, SMALLER and RAISED, immediately after
            k = j
            while (k < len(chars)
                   and chars[k]["text"].isdigit()
                   and chars[k]["size"] < base_size * 0.9
                   and chars[k]["top"] < base_top - 0.5):
                k += 1
            if k > j:
                base = "".join(c["text"] for c in chars[i:j])
                marker = "".join(c["text"] for c in chars[j:k])
                out.append((base + marker, base + "^" + marker))
                i = k
                continue
            i = j
    return out


def recover_superscript_via_layout(text: str, layout) -> str:
    """W0p: never fuse a typographically-superscript digit into the number.

    `N = 2,5801` is the sample size 2,580 carrying footnote marker 1. Fused, it
    reads as 25,801 AND it matches the numeric-locale rule's European marker
    `\\d,\\d{4,}`, so a footnote marker manufactures a false locale signal — that
    accounted for one of only two `conflict` verdicts across 396 English papers.

    Caret notation rather than deletion, because decision D4 forbids deleting
    superscript digits from body text: geometry cannot distinguish a footnote
    marker from a real exponent (`×10⁹/L`), and deleting the wrong one loses nine
    orders of magnitude. `2,580^1` is lossless, keeps both readings recoverable,
    and is the same form A5 already produces for a Unicode superscript after a
    digit — one rule, two evidence sources.

    Conservative correlation, as W0h and W0m do: rewrite at most as many text
    sites as the layout counted, left to right.
    """
    if not text or layout is None:
        return text
    for fused, repaired in _layout_superscript_fusions(layout):
        n = text.count(fused)
        if not n:
            record_fallback("w0p_no_text_match_for_layout_evidence", detail=fused)
            continue
        if n > 1:
            # POSITIONAL PAIRING, DECLARED. `replace(..., 1)` assigns the layout's
            # evidence to the FIRST textual occurrence — the same class W0h/W0m
            # were converted away from this release, because a glyph proven on
            # one page licensed rewriting a token anywhere in the paper.
            #
            # Not converted here, and the reason is a measurement rather than a
            # judgement: W0p's key is a WHOLE FUSED TOKEN (`2,5801`), not a bare
            # coefficient, so collisions are far rarer than W0h's; and the repair
            # is LOSSLESS — `2,580^1` keeps both readings recoverable, so a
            # mis-placed caret is visible and reversible where a fabricated minus
            # is neither. Recording the ambiguity is what turns "rare" from an
            # assumption into a number; convert it the day this counter is
            # non-zero on real papers.
            record_fallback("w0p_ambiguous_positional_pairing", detail=f"{fused}x{n}")
        text = text.replace(fused, repaired, 1)
    return text


def recover_dropped_minus_via_layout(text: str, layout) -> str:
    """W0h (R5 / B7): recover dropped-minus coefficients that carry NO CI, using
    the layout channel's surviving ``(cid:N)`` minus glyph. Conservative: only
    flips coefficients the layout proves negative, only in the ``= <coef>``
    assignment slot, and only as many times as the layout found them. See the
    module comment above for the structural signature + the OCR-only limitation.
    """
    if not text or layout is None:
        return text
    sites = _layout_negative_coefficient_sites(layout)
    if not sites:
        return text

    edits: list[tuple[int, int, str]] = []
    claimed: set[int] = set()

    # AN "EXHAUSTIVE MATCH" SHORTCUT WAS WRITTEN HERE AND THEN REMOVED, ON A
    # MEASUREMENT. A post-fix review observed that when the layout proves k>1
    # sites all reading the same `num` and the text holds exactly k candidates,
    # the counts force a bijection — every candidate is provably corrupt, so
    # refusing all k (which is what the code below does on a context tie) is
    # provably wrong. The argument is sound. The shape is not observed:
    # `tools/diag/w0h_pairing_prevalence_scan.py` over **60 sampled papers plus
    # the W0h source paper (2026-08-15)** found 3 sites, **0 of which had more
    # than one textual candidate at all** — so the ambiguous branch never
    # executes, let alone its exhaustive special case.
    #
    # A rewrite must earn its evidentiary cost, and a rule with no observed
    # input is false-positive surface for no benefit (the A3d precedent). The
    # missed repair is a PASS-THROUGH — the paper's own token, which a consumer
    # can still challenge — so declining to add the branch costs nothing that
    # matters. Re-open it the day the scan reports a non-zero R1a count.
    def _candidates_for(num: str) -> list:
        # `(?<=[\w\s])` ties the `=` to a label/space (excludes `<=` `>=` `==`);
        # `(?![\d.])` stops a partial match of a longer number.
        pat = re.compile(r"(?<=[\w\s])(=\s{0,3})(" + re.escape(num) + r")(?![\d.])")
        return list(pat.finditer(text))

    for site in sites:
        num = site["num"]
        candidates = [m for m in _candidates_for(num) if m.start() not in claimed]
        if not candidates:
            record_fallback("w0h_no_text_match_for_layout_evidence", detail=num)
            continue
        if len(candidates) == 1:
            # Unambiguous: exactly one place this evidence can belong. This is
            # the overwhelmingly common case, and behaviour is unchanged from
            # the pre-v2.4.133 count-based rewrite.
            chosen = candidates[0]
        else:
            chosen = _best_context_match(candidates, text, site["line"], num)
            if chosen is None:
                # AMBIGUOUS — two or more textual tokens could be the one the
                # layout proved, and the line context does not separate them.
                # REFUSE. Passing through leaves a value the consumer can still
                # challenge; guessing fabricates a minus on a statistic that
                # may never have been corrupt, and nothing downstream can tell.
                record_fallback("w0h_ambiguous_pairing_refused", detail=num)
                continue
        claimed.add(chosen.start())
        edits.append((chosen.start(), chosen.end(),
                      chosen.group(1) + "-" + chosen.group(2)))

    # Apply right-to-left so earlier offsets stay valid.
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


# An unmapped-glyph marker in a layout line. It is an ARTEFACT of the very
# corruption W0h/W0m are repairing, never content, and it exists in the LAYOUT
# channel only — pdftotext drops the glyph entirely, so the text window can
# never contain it.
_CID_MARKER_RE = re.compile(r"\(cid:\d+\)")


def _context_tokens(s: str) -> set[str]:
    """Alphanumeric tokens of a context window, lowercased.

    Compared as a SET because the two channels do not agree on spacing or
    reading order — pdfplumber's line and pdftotext's line are the same words,
    not the same string.

    ``(cid:N)`` markers are stripped FIRST, and that is not cosmetic. The layout
    line around a proven site reads ``…control,b=(cid:2).428,t(44)=`` — so ``cid``
    entered the wanted-token set, and no text window can ever contain it because
    pdftotext dropped the glyph. Every candidate therefore lost the same fraction
    of the score, and on a sparse line that was enough to push the best candidate
    under the 0.12 corroboration floor and force a REFUSAL — the repair declining
    to fire because of a token that is evidence of the corruption itself. The
    marker's glyph id is stripped with it: ``12`` in ``(cid:12)`` is an internal
    font index, not a word, and would survive the ``len > 1`` filter.
    """
    s = _CID_MARKER_RE.sub(" ", s)
    return {t for t in re.findall(r"[A-Za-z0-9.]+", s.lower()) if len(t) > 1}


def _best_context_match(candidates, text: str, layout_line: str, num: str):
    """Pick the textual match whose surroundings match the layout's own line.

    Returns the single best candidate, or ``None`` when the evidence does not
    separate them — in which case the caller MUST refuse rather than guess.

    ## Why the bar is SEPARATION, not a high absolute score

    A layout "line" is a band of constant *y*, and academic papers are set in
    two columns — so on a two-column page the reconstructed line splices text
    from BOTH columns, while pdftotext emits them in reading order. Measured on
    the W0h source paper (`ar_apa_j_jesp_2009_12_011`), the layout line around
    the proven `.428` is

        "F(1,88)=7.49, p<.01. Most importantly, participants in some
         control,b=(cid:2).428,t(44)="

    of which only `control`, `44` and `3.14` are actually adjacent to the token
    in reading order. The CORRECT match therefore scores 0.231 and a planted
    decoy scores 0.000. Demanding a high absolute score would refuse the very
    case this exists to resolve; demanding a decisive *gap* answers the only
    question being asked — *which of these candidates is the one the layout
    proved?* — and still refuses a genuine tie.

    Substring containment rather than set equality, because the channels split
    words differently: the layout's `control` lives inside pdftotext's
    `selfcontrol`.
    """
    want = _context_tokens(layout_line) - {num.lower()}
    if not want:
        return None
    scored: list[tuple[float, object]] = []
    for m in candidates:
        window = text[max(0, m.start() - 70): m.end() + 70].lower()
        hits = sum(1 for tok in want if tok in window)
        scored.append((hits / len(want), m))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    best, runner_up = scored[0][0], (scored[1][0] if len(scored) > 1 else 0.0)
    # Some real corroboration, AND a decisive lead over the next candidate.
    # A tie means the context did not discriminate, which is a refusal, not a
    # coin-flip: the whole point is to stop assigning evidence positionally.
    if best < 0.12 or best < 2.0 * runner_up + 0.08:
        return None
    return scored[0][1]


# ── W0m (§A / GLYPH): recover a standardized-coefficient 'β' that pdftotext ───
# rendered as a plain ASCII 'b', using the layout channel's surviving font tag
# (NORMALIZATION_VERSION 1.9.44, 2026-07-04). On tight-kerned PDFs that draw the
# Greek β in a math-symbol PostScript font with no ToUnicode CMap (ar_apa: font
# `MIICOL+AdvPSMP10`), pdftotext maps the glyph to the visually-similar ASCII
# `b`. So a regression paragraph reads `b = -.022` where the source shows
# `β = −.022` (ar_apa Supplemental analyses: all five standardized β's). This is
# NOT a text-only fix: `b` (unstandardized coefficient) is a LEGITIMATE distinct
# statistic, so a blind `b = ` → `β = ` rewrite would corrupt papers that report
# a genuine `b`. The DISCRIMINATOR is the layout channel: the corrupted symbol
# is a `b` char whose FONT is a math-symbol PostScript subset (`AdvPSMP…` — the
# "Math Publisher" family that also mis-draws the `×`/`<`/minus glyphs, W0i/W0c),
# distinct from the body serif font (`AdvGulliv`), AND it sits in the coefficient
# operator slot (immediately before `=`). A genuine body `b` uses the body font;
# a word-internal `b` (`bleat…`) or a figure label (`b0`, ArialMT) is not
# followed by `=`. Same layout-correlation mechanism as W0h (dropped-minus).
# Only flips as many `b = ` occurrences as the layout proves are β — never more.
_BETA_SYMBOL_FONT_RE = re.compile(r"AdvPSMP", re.IGNORECASE)


def _layout_beta_coefficient_sites(layout) -> list[dict]:
    """Every 'b' the layout proves is a math-symbol-font β in the ``b = <coef>``
    slot, WITH the coefficient it governs and its own line text.

    Same Risk A fix as :func:`_layout_negative_coefficient_sites`, and W0m was
    the worse of the two: it counted β glyphs and then flipped the first N
    ``b = <anything>`` occurrences in the document, **without even requiring
    the coefficient to match**. So a β proven on one page could promote a
    genuine unstandardized `b` on another — and `b` is a real, distinct
    statistic, which is exactly why this rule is layout-gated in the first
    place. The coefficient value is now part of the identity.
    """
    from .extract_layout import LayoutDoc  # local import (layout is optional)

    sites: list[dict] = []
    if not isinstance(layout, LayoutDoc):
        return sites
    for page_index, page in enumerate(layout.pages):
        chars = page.chars
        if not chars:
            continue
        for c in chars:
            if (c.get("text") or "") != "b":
                continue
            if not _BETA_SYMBOL_FONT_RE.search(str(c.get("fontname") or "")):
                continue
            # The 'b' must sit immediately before an '=' on its visual line — the
            # coefficient operator slot (β = …). y-overlap line clustering, as in
            # _layout_negative_coefficients (a symbol glyph can be off-baseline).
            ctop = float(c.get("top") or 0.0)
            cbot = float(c.get("bottom") or 0.0)
            line = [
                d for d in chars
                if float(d.get("bottom") or 0.0) > ctop + 0.5
                and float(d.get("top") or 0.0) < cbot - 0.5
            ]
            line.sort(key=lambda d: float(d.get("x0") or 0.0))
            try:
                i = next(k for k, d in enumerate(line) if d is c)
            except StopIteration:
                continue
            # nearest non-space neighbour to the RIGHT is `=`.
            right = None
            k = i + 1
            while k < len(line):
                rt = str(line[k].get("text") or "").strip()
                if rt:
                    right = rt
                    break
                k += 1
            if right != "=":
                continue
            # The coefficient this β governs — part of the site's identity, so
            # the evidence cannot be spent on an unrelated `b = ` elsewhere.
            coef = ""
            j = k + 1
            while j < len(line):
                t = str(line[j].get("text") or "")
                # Skip a leading sign before the digits start. The sign is
                # often the very `(cid:N)` unmapped-minus glyph W0h recovers —
                # missing that case left `coef` empty on every dropped-minus
                # beta, which is precisely the paper this rule was built on.
                if not coef and (t in "-−" or _CID_GLYPH_RE.match(t)):
                    j += 1
                    continue
                if len(t) == 1 and t in "0123456789.":
                    coef += t
                    j += 1
                elif not t.strip() and not coef:
                    j += 1
                else:
                    break
            sites.append({
                "coef": coef,
                "page": page_index,
                "line": _layout_line_text(line),
            })
    return sites


def _layout_beta_coefficients(layout) -> int:
    """Backward-compatible count view of :func:`_layout_beta_coefficient_sites`."""
    return len(_layout_beta_coefficient_sites(layout))


# A `b = ` coefficient operator slot: a standalone `b` (word-boundary before,
# excludes `Rb`/`sub`), then `=` (not `<=`/`>=`/`==`), then a signed decimal
# coefficient. The `b` is the mis-rendered β. Captures (1) the `= <coef>` tail so
# the flip preserves spacing/sign exactly, replacing only the leading `b`.
_BETA_COEF_SLOT_RE = re.compile(
    r"(?<![\w.])b(\s*=\s*[-−]?\s?\.?\d*\.\d+)"
)


def recover_beta_via_layout(text: str, layout) -> str:
    """W0m: promote a standardized-coefficient 'b' back to 'β' when the layout
    channel proves the glyph was a math-symbol-font β in the ``b = <coef>`` slot.
    Conservative — flips only as many `b = <coef>` occurrences as the layout
    counted, left to right. See the module comment above for the signature and
    the reason a text-only rewrite is unsafe (genuine `b` coefficients exist)."""
    if not text or layout is None or "b" not in text:
        return text
    sites = _layout_beta_coefficient_sites(layout)
    if not sites:
        return text

    all_matches = list(_BETA_COEF_SLOT_RE.finditer(text))
    if not all_matches:
        return text

    def _digits(s: str) -> str:
        return "".join(ch for ch in s if ch in "0123456789.")

    edits: list[tuple[int, int, str]] = []
    claimed: set[int] = set()
    for site in sites:
        pool = [m for m in all_matches if m.start() not in claimed]
        # IDENTITY FIRST: the coefficient the layout saw must be the coefficient
        # in the text. Only fall back to the whole pool when the layout could
        # not read a coefficient at all (it stays empty on a line break).
        if site["coef"]:
            exact = [m for m in pool if _digits(m.group(1)) == site["coef"]]
            pool = exact or []
        if not pool:
            record_fallback("w0m_no_text_match_for_layout_evidence",
                            detail=site["coef"] or "?")
            continue
        if len(pool) == 1:
            chosen = pool[0]
        else:
            chosen = _best_context_match(pool, text, site["line"], site["coef"])
            if chosen is None:
                # `b` is a LEGITIMATE distinct statistic (an unstandardized
                # coefficient). Promoting the wrong one silently relabels a real
                # published number as a different quantity.
                record_fallback("w0m_ambiguous_pairing_refused",
                                detail=site["coef"] or "?")
                continue
        claimed.add(chosen.start())
        edits.append((chosen.start(), chosen.end(), "β" + chosen.group(1)))

    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


# §A R5 / B7 (NORMALIZATION_VERSION 1.9.36, 2026-06-30): recover a CI UPPER
# bound whose leading minus pdftotext/Camelot DROPPED (or detached into a stray
# en-dash). W0g (CI-pairing) and W0h (layout) repair a *coefficient* proven
# negative by its CI bracket — but they TRUST the bracket, so a minus dropped
# from the bracket's OWN upper bound is invisible to them. On tight-kerned PDFs
# that draw U+2212 in a symbol font, the upper bound's minus can be dropped while
# the lower bound keeps its minus, so a negative interval [-0.78, -0.66] is
# extracted as [-0.78, 0.67] — a sign flip that inverts the interval
# (chan_feldman_2025_cogemo Table 8, rows 2bi/2bii). This reaches the rendered
# .md through the table channels (the structured-table flatten sidecar AND the
# `<table>` HTML cell), so the recovery is a SHARED helper keyed on the numeric
# structural signature, applied in flatten (separate estimate/CI columns) and in
# cell_cleaning._html_escape (same-cell estimate+CI).
#
# Structural signature (general — NOT keyed on any paper/font identity): the
# row's point estimate is negative, the parsed CI straddles zero with a negative
# lower bound and a positive upper bound (lo < 0 < hi), AND negating the upper
# bound yields an interval that is valid for this estimate — monotonic
# (lo < -hi) and containing the estimate (lo <= est <= -hi) — AND that brackets
# the estimate far more plausibly than the as-parsed interval (the estimate sits
# in the OUTER half of the as-parsed interval but the INNER half of the flipped
# one, measured by distance from each interval's mid-point). This is the same
# estimate-containment invariant docpluck already uses for hyphen-glued CIs
# (flatten._resolve_hyphen_ci), promoted to the dropped-upper-bound case.
#
# Self-guarding against a LEGITIMATE zero-straddling null CI (e.g.
# d = -0.02, 95% CI [-0.19, 0.15] — a real null result in this same paper): a
# genuine zero-straddling interval has its estimate close enough to zero that
# negating the positive bound would EXCLUDE the estimate (-0.02 not in
# [-0.19, -0.15]), so the post-flip containment test fails and the bound is left
# untouched. Only an estimate far enough negative that the negated bound still
# contains it — the hallmark of a dropped minus on a one-sided negative
# interval — is corrected.
def recover_dropped_minus_ci_upper(
    estimate: float, lo: float, hi: float
) -> "float | None":
    """Return the corrected (negative) CI upper bound when ``hi`` lost its minus,
    else ``None``. See the module comment above for the structural signature and
    the self-guard against a legitimate zero-straddling CI."""
    if not (estimate < 0 and lo < 0 < hi):
        return None
    flipped_hi = -hi
    if not (lo < flipped_hi and lo <= estimate <= flipped_hi):
        return None
    parsed_half = (hi - lo) / 2.0
    flipped_half = (flipped_hi - lo) / 2.0
    if parsed_half <= 0 or flipped_half <= 0:
        return None
    parsed_offcentre = abs(estimate - (lo + hi) / 2.0) / parsed_half
    flipped_offcentre = abs(estimate - (lo + flipped_hi) / 2.0) / flipped_half
    if parsed_offcentre > 0.5 and flipped_offcentre < 0.5:
        return flipped_hi
    return None


# A self-contained "<signed estimate> … [<lo>, <hi>]" cell/clause: a leading
# signed point estimate (optionally `r = .73` / `−.32`, the bare APA decimal
# form), then — after any decoration (`***`, `<br>`, spaces) — the FIRST
# bracketed CI. The upper bound is split into a DETACHED dash run (en/em/hyphen
# separated from the digit by space — the `[−0.78,  –  0.67]` corruption), an
# ATTACHED sign glued to the digit (a genuine `−0.67`), and the magnitude. A
# bare magnitude with no attached sign (`[−0.52,  0.33]`) is the fully-dropped
# case. Sign chars accept ASCII hyphen AND U+2212. Groups: (1) est sign,
# (2) est magnitude, (3) whole bracket, (4) lo text, (5) detached dash run,
# (6) attached hi sign, (7) hi magnitude.
_CI_SIGN = r"[-−]"
_CI_DASH = r"[-−–—]"
# ReDoS fix, 2026-08-04. The decimal atom was `\d*\.\d+`, whose UNBOUNDED integer part
# is quadratic on a long digit run: at each of ~n start positions `\d*` consumes the
# whole remaining run and then backtracks one digit at a time hunting for a `.`. On the
# 10k-digit input of tests/test_edge_cases.py::test_regex_no_catastrophic_backtracking a
# single pass cost 0.49s (2.27s at 20k, ~4.6x per doubling) — which is what made that
# test fail intermittently, a real complexity defect rather than the load sensitivity it
# had been recorded as.
#
# Bounding the INTEGER part is what fixes it (1.68s -> 0.006s at n=20000, ~270x): the
# decoration gap and possessive quantifiers were both measured and are NOT the driver
# (bounding the gap alone left it at 1.6s; a bare `\d*\.\d+` in isolation costs MORE
# than the whole pattern). 20 integer digits is far beyond any real statistic, and the
# atom matches every real form identically (`0.72`, `.67`, `12.5`, `100.25`).
# Guarded by tests/test_ci_upper_dropped_redos.py.
_CI_DEC = r"\d{0,20}\.\d+"
_CI_UPPER_DROPPED_RE = re.compile(
    r"(?:[A-Za-z]+\s*=\s*)?(" + _CI_SIGN + r"?)\s*(" + _CI_DEC + r")"  # signed estimate
    r"[^\[\]\n]*?"                                              # decoration
    r"(\[\s*(" + _CI_SIGN + r"?\s*" + _CI_DEC + r")\s*,"        # [ lo ,
    r"\s*(" + _CI_DASH + r"\s+)?"                               # detached dash?
    r"(" + _CI_SIGN + r"?)(" + _CI_DEC + r")\s*\])"             # attached-sign hi ]
)


def recover_dropped_minus_ci_upper_in_text(text: str) -> str:
    """Recover a dropped/detached minus on a CI UPPER bound inside a self-
    contained ``<estimate> … [lo, hi]`` cell or clause (the table-cell and
    raw-text surfaces). For each estimate-anchored bracket, the estimate-
    containment invariant (``recover_dropped_minus_ci_upper``) decides whether
    the positive upper bound is a dropped-minus victim; on a flip the bracket is
    re-emitted with a single ASCII-hyphen minus on the upper bound (and any
    stray detached dash collapsed), leaving the lower bound and all surrounding
    text untouched. A bound that ALREADY carries an attached minus is parsed as
    negative, so the invariant's ``lo < 0 < hi`` gate leaves it alone (no churn
    on correct rows). No-op when no estimate-anchored bracket is present.

    ## Which EVIDENCE each rewrite rests on — and why both are now declared

    The project's evidence-axis rule splits repairs into TYPOGRAPHIC (something
    the renderer emitted) and INFERENTIAL (what the number ought to be), and
    assigns inferential judgement to consumers. This function was doing both and
    saying neither, so the two are now separated and each is RECORDED:

    * **TYPOGRAPHIC** — the bracket carries a DETACHED DASH before its upper
      bound (``[−0.78,  –  0.67]``). The dash is a glyph the renderer put on the
      page; what used to be inferential was its *reading*, and the COMMA settles
      that: in ``[lo, – hi]`` the comma already occupies the separator role, so
      the dash cannot be a range separator and can only be a sign that lost its
      kerning. (Both independent reviewers reached this argument separately on
      2026-08-15.) ``_CI_UPPER_DROPPED_RE`` requires that comma, so the gate
      inherits the condition rather than assuming it. Group 5 CAPTURED this dash
      all along and nothing ever read it — register O5.
    * **INFERENTIAL** — no dash, nothing on the page to point at, and only the
      estimate-containment arithmetic says the bound lost a minus.

    **The inferential arm is KEPT, deliberately, and this is not a re-derivation
    of the doctrine.** Retiring it was proposed and then refuted against the
    primary source: `chan_feldman_2025_cogemo` Table 9 row 2bii extracts as
    ``[−0.52,  0.33]`` with NO dash and no font signal, and the arithmetic is the
    only mechanism that recovers its published ``−0.33``. Deleting it would drop
    a repair with a real-DOI justification. The doctrine's stated REASON for
    assigning inferential calls to consumers is that *docpluck has no channel
    through which to relay that it guessed* — and that premise changed in this
    release: `NormalizationReport.fallbacks` now reaches them. So the guess is
    declared instead of hidden, and the retirement stays an owner decision with a
    measurement attached rather than a plan author's call.
    """
    if not text or "[" not in text:
        return text

    def _fold(s: str) -> str:
        return (s or "").replace("−", "-").replace(" ", "")

    def _sub(m: "re.Match[str]") -> str:
        attached_sign = m.group(6) or ""
        # An attached minus (no intervening space) is a genuine sign → parse the
        # upper bound as negative so the invariant skips it. A DETACHED dash
        # (group 5) is treated as a dropped/garbled minus, NOT a present sign:
        # the magnitude is parsed positive and the invariant adjudicates.
        detached_dash = bool(m.group(5))
        hi_signed = ("-" if attached_sign in ("-", "−") else "") + m.group(7)
        try:
            est = float(_fold(m.group(1) + m.group(2)))
            lo = float(_fold(m.group(4)))
            hi = float(hi_signed)
        except ValueError:
            return m.group(0)
        if detached_dash and lo < 0 < hi and lo < -hi:
            # Typographic: reattach the dash the renderer emitted. The
            # monotonicity check (`lo < -hi`) is a well-formedness test on the
            # RESULT, not estimate arithmetic — it refuses to produce a bracket
            # that runs backwards, which would be a new defect rather than a
            # repair.
            fixed_hi = -hi
            record_fallback("ci_upper_minus_reattached_from_detached_dash",
                            detail=f"{m.group(3)}")
        else:
            fixed_hi = recover_dropped_minus_ci_upper(est, lo, hi)
            if fixed_hi is None:
                return m.group(0)
            # INFERENTIAL — declared, so a consumer can find every one of these
            # and re-check it against the paper. Nothing the renderer emitted
            # supports this rewrite; only the containment arithmetic does.
            record_fallback("ci_upper_minus_inferred_from_containment",
                            detail=f"{m.group(3)}")
        # Preserve the lower bound's original glyph (e.g. U+2212) verbatim,
        # stripping only interior spaces, so a corrected row's lo still matches
        # the sibling rows' display; emit the upper bound with a single minus
        # using the SAME minus glyph the lower bound uses (U+2212 if the lo is
        # U+2212-signed, else ASCII hyphen — keeps the bracket visually uniform).
        lo_txt = re.sub(r"\s+", "", m.group(4))
        minus = "−" if lo_txt.startswith("−") else "-"
        new_bracket = f"[{lo_txt}, {minus}{m.group(7)}]"
        return m.group(0).replace(m.group(3), new_bracket, 1)

    return _CI_UPPER_DROPPED_RE.sub(_sub, text)


# v2.4.44 (NORMALIZATION_VERSION 1.9.8): decompose Latin typographic
# ligatures (ﬀ ﬁ ﬂ ﬃ ﬄ ﬅ ﬆ, U+FB00-FB06). pdftotext preserves these
# presentation-form glyphs verbatim, so words render as "conﬁdent" /
# "inﬂuence" — broken for search, word matching, and any downstream NLP.
# An explicit ASCII table is used (not a scoped NFKC pass): NFKC of U+FB05
# yields "ſt" with a non-ASCII LONG S, and meta-science output must stay
# ASCII. This is the SINGLE shared helper for all THREE text channels — the
# S3 body step (normalize_text, below), table-cell cleaning, and the render
# post-process. Table cells and figure/table captions bypass normalize_text
# entirely, so a body-only fix leaves them showing raw ligature glyphs.
_LIGATURE_MAP = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl",
    "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st",
}
_LIGATURE_RE = re.compile("[ﬀ-ﬆ]")


# Greek transliteration comes from THE canonical table (`docpluck.symbols`), so
# this module and `extract.py`'s SMP fallback cannot drift apart again — they
# had, on 9 of 9 shared letters, and the same chi-square left as `chi2` or `ch2`
# depending only on which extraction path ran.
from .symbols import (  # noqa: E402
    GREEK_TO_ASCII,
    GREEK_UPPER_AMBIGUOUS_TO_ASCII,
)

_GREEK_TRANSLATION = {ord(k): v for k, v in GREEK_TO_ASCII.items()}

# Standalone-token guard for the Latin-lookalike capitals — see the A5 comment.
_GREEK_AMBIGUOUS_UPPER_RE = re.compile(
    r"(?<![^\W\d_]|[-‐-―_.])["
    + "".join(GREEK_UPPER_AMBIGUOUS_TO_ASCII)
    + r"](?![^\W\d_]|[-‐-―_.])"
)


# A5 SUBSCRIPT LETTERS (v2.4.128, decision D6a) — the completion of a table that
# already mapped subscript DIGITS.
#
# A5 flattens the typographic forms publishers use into the ASCII downstream
# consumers parse. It did that for U+2080-U+2089 and stopped, so the subscript
# LETTER blocks passed through untouched and the most common effect size in
# psychology left as a mixed ASCII/Unicode token: `eta2` + a live U+209A. Nothing
# errors — effectcheck's fixed `(?:eta2p|eta_p2|...)` alternation simply misses
# it, and the row degrades from PASS (checked, .04) to OK (nothing was checked).
#
# Keyed on the BLOCK, not on the letters we happened to see in a corpus: the
# same "what is not on this list?" question that produced the A3/A3a defects in
# v2.4.127. U+1D66-U+1D6A are GREEK subscripts and take the Greek ASCII spelling
# A5 already uses for the base letters — a subscript beta is not the letter 'b',
# and renaming it would silently change which statistic the token names.
# A5 EXPONENT GUARD (v2.4.128) — a superscript run after a DIGIT is never fused.
#
# A5 flattens superscript digits to ASCII so downstream regexes can match
# `eta2`/`chi2`. After a LETTER that is exactly right: `η²` is one symbol whose
# flat spelling is `eta2`. After a DIGIT it is an EXPONENT, and flattening fuses
# it into the mantissa:
#
#     'leucocyte count (×10⁹/L)'   ->   'x109/L'      nine orders of magnitude
#     '∼5×10⁶ possible'            ->   '5x106'
#     'p < .001¹'                  ->   '.0011'       a different p-value
#
# `docs/FINDINGS_2026-08-13` examined these exact tokens when rejecting decision
# D4's "delete citation superscripts" option — "deleting the 9 loses nine orders
# of magnitude" — and the reasoning was right. But it measured a PROPOSED rule
# while this SHIPPED one was already doing equivalent damage to the same tokens.
# The hazard was named; the existing behaviour was never tested against it.
#
# Caret notation rather than "leave the glyph": it is flat ASCII, unambiguous,
# and already what the consumer produces internally — effectcheck's normalizer
# folds Unicode superscripts to carets before its extraction regexes run.
#
# STATED RESIDUAL: `N = 42³` may be a footnote marker rather than 42-cubed, and
# the text channel cannot decide. `42^3` keeps both readings recoverable where
# `423` destroys them — the same principle A3 applies to an ambiguous comma.
_SUPERSCRIPT_TO_ASCII = {
    0x2070: "0", 0x00B9: "1", 0x00B2: "2", 0x00B3: "3", 0x2074: "4",
    0x2075: "5", 0x2076: "6", 0x2077: "7", 0x2078: "8", 0x2079: "9",
    0x207A: "+", 0x207B: "-",
}
_SUPERSCRIPT_EXPONENT_RE = re.compile(
    r"(?<=\d)([⁰¹²³⁴-⁹⁺⁻]+)"
)


def _superscript_run_to_caret(m: "re.Match[str]") -> str:
    return "^" + m.group(1).translate(_SUPERSCRIPT_TO_ASCII)


# THE NUMERIC-TUPLE GUARD WAS HERE AND IS DELETED (v2.4.130, 2026-08-14).
#
# `_NUMERIC_RUN_RE`, `_THOUSANDS_GROUPED_RE`, `_NUMERIC_RUN_WINDOW`,
# `_in_numeric_tuple`, `_VALUE_END_MARKERS` and `_a3c_leading_zero_sub` all
# existed to stop A3a and A3c from mangling a comma-separated integer run. Both
# of those rules are now deleted, so the guard has nothing left to guard and is
# removed with them rather than left standing as dead code the next reader
# re-enables (the A3d precedent).
#
# THE KNOWLEDGE IT CARRIED, kept because the corpus sites are real and were
# expensive to find. Every one of these is now preserved by DEFAULT, because
# nothing rewrites a comma-separated integer run any more:
#
#     10.1177/0146167210380928 p13   a reference-list URL
#       'http://content.time.com/time/specials/article/0,9171,1848755,00.html'
#       A3c read `0,9171` as a leading-zero decimal and emitted a URL that 404s.
#     collabra.320                   an RGB stimulus specification
#       'purple (128,0,128), orange (255,165,0)'
#       A3a fused `255,165` into `255165` and A3c read `0,128` as a decimal —
#       two rules destroying one construct, so a replication built from this
#       text would show participants different colours.
#     nat_comms_2                    an interquartile range beside a median
#       '148 (52,272)' fused to '148 (52272)', one fictional number, while the
#       adjacent row '8 (4,14)' survived: one table, two spellings.
#     an ISBN comma form  978,0,306,40615,7   and an ML tensor shape.
#
# The lesson the guard taught, which outlives it: telling a tuple from a
# thousands-grouped number needs a POSITIVE signature (a grouped NUMBER has
# every group after the first exactly three digits), never an exclusion list —
# an enumeration is never complete, and that incompleteness is this module's
# recurring failure mode. Retained in
# tests/test_numeric_tuple_and_terminator.py as pass-through assertions.
# A run of subscript characters, with the word character it attaches to.
# Built from the canonical table so it cannot drift from what A5 maps.
_SUBSCRIPT_RUN_RE = re.compile(
    r"(?P<lead>\w)?(?P<run>[" + "".join(
        __import__("docpluck.symbols", fromlist=["x"]).SUBSCRIPT_TO_ASCII
    ) + r"]+)"
)


def _subscript_run_to_ascii(m: "re.Match[str]") -> str:
    """A subscript RUN becomes `_` + its ASCII, joined to what precedes it.

    One underscore per run, not per character, so `BF01` reads `BF_01`. The
    underscore is inserted only when the run follows a word character — there is
    nothing to separate otherwise.
    """
    from .symbols import SUBSCRIPT_TO_ASCII

    body = "".join(SUBSCRIPT_TO_ASCII.get(c, c) for c in m.group("run"))
    return (m.group("lead") + "_" + body) if m.group("lead") else body


_SUBSCRIPT_LETTER_MAP = {
    # Latin subscripts, U+2090-U+209C (complete block)
    0x2090: "a", 0x2091: "e", 0x2092: "o", 0x2093: "x",
    0x2094: "e",   # SCHWA — 'e' is its conventional ASCII transliteration
    0x2095: "h", 0x2096: "k", 0x2097: "l", 0x2098: "m",
    0x2099: "n", 0x209A: "p", 0x209B: "s", 0x209C: "t",
    # Phonetic Latin subscripts, U+1D62-U+1D65
    0x1D62: "i", 0x1D63: "r", 0x1D64: "u", 0x1D65: "v",
    # Greek subscripts, U+1D66-U+1D6A — spelled out, as A5 spells their bases
    0x1D66: "beta", 0x1D67: "gamma", 0x1D68: "rho",
    0x1D69: "phi", 0x1D6A: "chi",
}


def decompose_ligatures(text: str) -> str:
    """Decompose Latin typographic ligatures (U+FB00-FB06) to ASCII."""
    if not text:
        return text
    return _LIGATURE_RE.sub(lambda m: _LIGATURE_MAP[m.group(0)], text)


# ── PUA glyph recovery — Adobe Symbol font (shared, v2.4.54) ───────────────
# Some PDF/DOCX producers embed the Adobe "Symbol" font with no ToUnicode
# CMap, so pdftotext / mammoth surface each glyph as a Private-Use-Area
# codepoint U+F000+<symbol-byte> — β reads as U+F062, χ as U+F063, • as
# U+F0B7 (e.g. efendic-style "χ²(1) = 0.34" arriving as a raw  2(1)).
# A PUA codepoint is never a legitimate character in extracted academic text
# — it carries no Unicode identity, it is purely a font-encoding artifact —
# so mapping the Adobe Symbol StandardEncoding (a fixed, decades-stable
# standard) back to real Unicode is a zero-false-positive, fully general
# recovery keyed on the structural signature "codepoint in the Symbol-font
# PUA block U+F020-F0FF". Greek stays Greek (CLAUDE.md hard rule 4 — the A5
# step transliterates β→"beta" for ASCII-form callers; the rendered .md keeps
# β). SHARED by all three text channels: normalize_text's W0e step (body),
# tables/cell_cleaning (Camelot layout channel) and the render post-process
# (caption / fenced-table / raw-text surfaces), so no Symbol-PUA glyph
# reaches any output view. The lowercase-Greek block follows the Symbol
# typist mnemonic — key 'b'→β, 'c'→χ, 'd'→δ, 'h'→η, 'm'→μ, 'p'→π, 's'→σ …
_SYMBOL_BYTE_TO_CHAR: dict[int, str] = {
    # ASCII-shared punctuation + digits (Symbol shares these positions)
    0x20: " ", 0x21: "!", 0x23: "#", 0x25: "%", 0x26: "&", 0x28: "(",
    0x29: ")", 0x2B: "+", 0x2C: ",", 0x2E: ".", 0x2F: "/",
    0x30: "0", 0x31: "1", 0x32: "2", 0x33: "3", 0x34: "4",
    0x35: "5", 0x36: "6", 0x37: "7", 0x38: "8", 0x39: "9",
    0x3A: ":", 0x3B: ";", 0x3C: "<", 0x3D: "=", 0x3E: ">", 0x3F: "?",
    0x5B: "[", 0x5D: "]", 0x5F: "_", 0x7B: "{", 0x7C: "|", 0x7D: "}",
    # uppercase Greek (0x41-0x5A)
    0x41: "Α", 0x42: "Β", 0x43: "Χ", 0x44: "Δ", 0x45: "Ε", 0x46: "Φ",
    0x47: "Γ", 0x48: "Η", 0x49: "Ι", 0x4A: "ϑ", 0x4B: "Κ", 0x4C: "Λ",
    0x4D: "Μ", 0x4E: "Ν", 0x4F: "Ο", 0x50: "Π", 0x51: "Θ", 0x52: "Ρ",
    0x53: "Σ", 0x54: "Τ", 0x55: "Υ", 0x56: "ς", 0x57: "Ω", 0x58: "Ξ",
    0x59: "Ψ", 0x5A: "Ζ",
    # lowercase Greek (0x61-0x7A)
    0x61: "α", 0x62: "β", 0x63: "χ", 0x64: "δ", 0x65: "ε", 0x66: "φ",
    0x67: "γ", 0x68: "η", 0x69: "ι", 0x6A: "ϕ", 0x6B: "κ", 0x6C: "λ",
    0x6D: "μ", 0x6E: "ν", 0x6F: "ο", 0x70: "π", 0x71: "θ", 0x72: "ρ",
    0x73: "σ", 0x74: "τ", 0x75: "υ", 0x76: "ϖ", 0x77: "ω", 0x78: "ξ",
    0x79: "ψ", 0x7A: "ζ",
    # math operators / relations
    0x22: "∀", 0x24: "∃", 0x27: "∋", 0x2A: "∗", 0x2D: "−",
    0x40: "≅", 0x5C: "∴", 0x5E: "⊥", 0x60: "‾", 0x7E: "∼",
    0xA1: "ϒ", 0xA2: "′", 0xA3: "≤", 0xA4: "⁄", 0xA5: "∞", 0xA6: "ƒ",
    0xA7: "♣", 0xA8: "♦", 0xA9: "♥", 0xAA: "♠",
    0xAB: "↔", 0xAC: "←", 0xAD: "↑", 0xAE: "→", 0xAF: "↓",
    0xB0: "°", 0xB1: "±", 0xB2: "″", 0xB3: "≥", 0xB4: "×", 0xB5: "∝",
    0xB6: "∂", 0xB7: "•", 0xB8: "÷", 0xB9: "≠", 0xBA: "≡", 0xBB: "≈",
    0xBC: "…", 0xBF: "↵",
    0xC0: "ℵ", 0xC1: "ℑ", 0xC2: "ℜ", 0xC3: "℘", 0xC4: "⊗", 0xC5: "⊕",
    0xC6: "∅", 0xC7: "∩", 0xC8: "∪", 0xC9: "⊃", 0xCA: "⊇", 0xCB: "⊄",
    0xCC: "⊂", 0xCD: "⊆", 0xCE: "∈", 0xCF: "∉",
    0xD0: "∠", 0xD1: "∇", 0xD2: "®", 0xD3: "©", 0xD4: "™", 0xD5: "∏",
    0xD6: "√", 0xD7: "⋅", 0xD8: "¬", 0xD9: "∧", 0xDA: "∨", 0xDB: "⇔",
    0xDC: "⇐", 0xDD: "⇑", 0xDE: "⇒", 0xDF: "⇓", 0xE0: "◊",
    0xE2: "®", 0xE3: "©", 0xE4: "™", 0xE5: "∑",
    # extensible bracket / paren / brace / integral pieces
    0xE1: "⟨", 0xE6: "⎛", 0xE7: "⎜", 0xE8: "⎝", 0xE9: "⎡", 0xEA: "⎢",
    0xEB: "⎣", 0xEC: "⎧", 0xED: "⎨", 0xEE: "⎩", 0xEF: "⎪", 0xF1: "⟩",
    0xF2: "∫", 0xF3: "⌠", 0xF5: "⌡", 0xF6: "⎞", 0xF7: "⎟", 0xF8: "⎠",
    0xF9: "⎤", 0xFA: "⎥", 0xFB: "⎦", 0xFC: "⎫", 0xFD: "⎬", 0xFE: "⎭",
}
_SYMBOL_PUA_MAP: dict[str, str] = {
    chr(0xF000 + _b): _c for _b, _c in _SYMBOL_BYTE_TO_CHAR.items()
}
# CMEX10 / Computer-Modern extensible square-bracket pieces. pdftotext and
# pdfplumber both surface these as U+F8EE-F8FB PUA codepoints (font
# *+CMEX10, the TeX math-extension font); glyph geometry confirms the
# assignment -- the left column F8EE/F8EF/F8F0 are the upper-corner /
# extension / lower-corner of a tall left square bracket, F8F9/F8FA/F8FB
# the right -- so they map to the Unicode Miscellaneous-Technical
# bracket-piece block U+23A1-U+23A6.
_SYMBOL_PUA_MAP.update({
    chr(0xF8EE): chr(0x23A1), chr(0xF8EF): chr(0x23A2), chr(0xF8F0): chr(0x23A3),
    chr(0xF8F9): chr(0x23A4), chr(0xF8FA): chr(0x23A5), chr(0xF8FB): chr(0x23A6),
})
# Symbol-font PUA block U+F020-F0FF plus the CMEX extensible-bracket pieces.
_SYMBOL_PUA_RE = re.compile(
    "[" + chr(0xF020) + "-" + chr(0xF0FF) + chr(0xF8EE) + "-" + chr(0xF8FB) + "]"
)


def recover_pua_glyphs(text: str) -> str:
    """Recover Adobe-Symbol-font glyphs surfaced as Private-Use codepoints.

    pdftotext / mammoth emit a Symbol-font glyph that has no ToUnicode CMap as
    ``U+F000 + <symbol-byte>`` (β→U+F062, χ→U+F063, •→U+F0B7). Each is mapped
    back to real Unicode via the fixed Adobe Symbol StandardEncoding. A PUA
    codepoint at an unassigned Symbol position — or outside the Symbol block —
    is left untouched, never guessed. No-op when the text holds no
    Symbol-block PUA codepoint.
    """
    if not text or not _SYMBOL_PUA_RE.search(text):
        return text
    return _SYMBOL_PUA_RE.sub(
        lambda m: _SYMBOL_PUA_MAP.get(m.group(0), m.group(0)), text
    )


# v2.4.57 (NORMALIZATION_VERSION 1.9.11): recover the cmsy10 (TeX Computer
# Modern math-symbol font) >= / <= comparison glyphs that pdftotext AND
# pdfplumber both destroy to U+FFFD on tightly-kerned PDFs. The glyph identity
# is gone from BOTH engines, so the layout channel cannot recover it --
# recovery is context-based. Sibling of S5a (FFFD->eta).
#
# Rule 1 -- complement pairing: a corrupted "<FFFD>N" contrasted with a clean
# "<N" / ">N" of the SAME number N is a set-partition (every value is either
# <N or >=N, resp. >N or <=N). The same-number constraint is enforced by a
# regex backreference, so a non-matching pair simply does not match. The
# separator class excludes digits/newlines/FFFD so the two operands stay in
# one clause. (?!\d) anchors the trailing number so "<20...[FFFD]200" cannot
# match a prefix.
_FFFD_OP_THEN_RE = re.compile(
    r"([<>])(\s*)(\d+)([^\d�\n]{0,18}?)�(\s*)\3(?!\d)"
)
_FFFD_RE_THEN_OP = re.compile(
    r"�(\s*)(\d+)([^\d�\n]{0,18}?)([<>])(\s*)\2(?!\d)"
)
# Rule 2 -- a lone "<FFFD>N": FFFD token-initial (not glued to a letter or
# digit -- a comparison operator is always set off by space/paren/slash/line
# start, never welded to a word or another number) immediately before a digit.
_FFFD_LONE_RE = re.compile(r"(?<![A-Za-z0-9])�(\s*\d)")
_FFFD_COMPLEMENT = {"<": "≥", ">": "≤"}


def recover_fffd_comparison_operators(text: str) -> str:
    """Recover cmsy10 >= / <= glyphs that pdftotext destroyed to U+FFFD.

    Rule 1 -- complement pairing (airtight): a corrupted ``<FFFD>N`` in a
    partition contrast with a clean ``<N`` / ``>N`` of the same number N is the
    set-complement (``<`` -> ``>=``, ``>`` -> ``<=``). Zero false-positive
    risk -- a partition like ``(<20/[FFFD]20 mm)`` is complementary by
    construction.

    Rule 2 -- document consensus: a lone ``<FFFD>N`` with no local complement
    is recovered only when Rule 1 has already fired in this document AND every
    recovery agreed on one operator. One PDF == one font == one corruption
    shape, so an airtight unanimous mapping generalises to a lone occurrence.
    If Rule-1 recoveries disagree, or none fired, a lone FFFD is left alone for
    the caller's quality scoring to flag (the S5a policy for prose FFFD).

    No-op when the text holds no U+FFFD.
    """
    if not text or "�" not in text:
        return text

    def _op_then(m: "re.Match[str]") -> str:
        op, ws1, num, sep, ws2 = m.groups()
        return f"{op}{ws1}{num}{sep}{_FFFD_COMPLEMENT[op]}{ws2}{num}"

    def _re_then(m: "re.Match[str]") -> str:
        ws1, num, sep, op, ws2 = m.groups()
        return f"{_FFFD_COMPLEMENT[op]}{ws1}{num}{sep}{op}{ws2}{num}"

    before = text
    text = _FFFD_OP_THEN_RE.sub(_op_then, text)
    text = _FFFD_RE_THEN_OP.sub(_re_then, text)
    # Rule 2 fires only on a unanimous, evidence-based consensus.
    #
    # Evidence is Rule-1 recoveries made in THIS call, plus — for the channel-3
    # pass over assembled markdown (v2.4.119) — operators ALREADY present in the
    # text. In channel 3 the body prose has been through channel 1, so its
    # Rule-1 pairs are already resolved to real `≥`/`≤` and no corrupted pair
    # remains for Rule 1 to fire on; the surviving FFFDs sit in table raw_text /
    # caption blocks that bypassed normalize_text. Counting the document's
    # existing operators recovers that evidence without weakening the gate:
    # unanimity is still required (a document mixing `≥` and `≤` yields no
    # consensus and lone FFFDs are left for quality scoring), and a document
    # with no operator evidence at all still recovers nothing.
    n_ge = text.count("≥") - before.count("≥")
    n_le = text.count("≤") - before.count("≤")
    if n_ge == 0 and n_le == 0:
        n_ge, n_le = before.count("≥"), before.count("≤")
    if n_ge > 0 and n_le == 0:
        text = _FFFD_LONE_RE.sub(lambda m: "≥" + m.group(1), text)
    elif n_le > 0 and n_ge == 0:
        text = _FFFD_LONE_RE.sub(lambda m: "≤" + m.group(1), text)
    return text


def normalize_text(
    text: str,
    level: NormalizationLevel,
    *,
    layout=None,
    table_regions: list[dict] | None = None,
    preserve_math_glyphs: bool = False,
    dropped_minus_layout=None,
) -> tuple[str, NormalizationReport]:
    """Apply the normalization pipeline, and report what it silently did.

    Thin wrapper over :func:`_normalize_text` that holds a
    :class:`telemetry.fallback_scope` open across the whole pipeline and attaches
    the result to ``report.fallbacks`` / ``report.fallback_details``. Without it
    every `record_fallback` inside normalization — including W0h/W0m's
    ambiguous-pairing REFUSALS — is write-only, because this function runs after
    ``extract_pdf_structured`` has already returned its own telemetry.

    See :func:`_normalize_text` for the arguments.
    """
    with fallback_scope() as fb:
        out, report = _normalize_text(
            text,
            level,
            layout=layout,
            table_regions=table_regions,
            preserve_math_glyphs=preserve_math_glyphs,
            dropped_minus_layout=dropped_minus_layout,
        )
    report.fallbacks = dict(fb.counters)
    report.fallback_details = fb.details
    return out, report


def _normalize_text(
    text: str,
    level: NormalizationLevel,
    *,
    layout=None,
    table_regions: list[dict] | None = None,
    preserve_math_glyphs: bool = False,
    dropped_minus_layout=None,
) -> tuple[str, NormalizationReport]:
    """Apply normalization pipeline at the specified level.

    When `layout` is provided (a docpluck.extract_layout.LayoutDoc), the
    F0 step strips footnotes/running-headers/footers using PDF layout info
    and populates report.footnote_spans + report.page_offsets.

    When `table_regions` (a list of ``{"page": int, "bbox": (x0, top, x1, bottom)}``)
    is provided alongside `layout`, F0 will not strip lines whose y-range falls
    inside any table region — preserving table footnotes (e.g. ``Note. *p < .05.``)
    that would otherwise be misclassified as page footnotes.

    When `preserve_math_glyphs=True` (default False), the A5 step that
    transliterates Greek letters (β→"beta", δ→"delta", η²→"eta2", etc.) and
    math operators (×→"x", ≥→">=", ²→"2", ₀→"0", etc.) is SKIPPED. This is
    the correct setting for the rendered-markdown user output: every glyph
    that appears in the source PDF is preserved verbatim in the .md (subject
    only to U+2212→hyphen per CLAUDE.md L004 — the single documented
    Unicode→ASCII conversion). Default False preserves backward-compatible
    behavior for callers that depend on ASCII-form stat tokens (D5 audit
    suite, statistical pattern matching). Established 2026-05-14 from the
    Phase-5d AI-gold audit (TRIAGE_2026-05-14_phase_5d_gold_audit.md G2/G7/G12/G21).

    When `dropped_minus_layout` is provided (a LayoutDoc), the W0h step recovers
    dropped-minus coefficients that have NO confidence interval (so W0g cannot
    reach them) by reading the surviving `(cid:N)` minus glyph from the layout
    channel. It is a SEPARATE param from `layout` on purpose: the section
    pipeline runs the text channel only (F0 stays off), so we thread just this
    one targeted layout signal through without enabling the full F0 strip.
    """
    if level == NormalizationLevel.none:
        report = NormalizationReport(level="none")
        if layout is not None:
            report.page_offsets = layout.page_offsets
        return text, report

    report = NormalizationReport(level=level.value)
    if layout is not None:
        report.page_offsets = layout.page_offsets
    t = text

    # ── NFC composition (Cycle 15c, G15 — combining-char split fix) ───
    # pdftotext sometimes emits author names with combining accents in NFD
    # decomposed form ("Förster", "Potočnik") or with a stray space
    # between base and combining mark ("Fö rster" → "Fö rster").
    # NFC composition recombines them into precomposed code points (Förster,
    # Potočnik). Safe to run at the top of the pipeline because all downstream
    # regex patterns operate on precomposed glyphs.
    import unicodedata
    # First squash any space between a base letter and an immediately-following
    # combining diacritic (the "Fö rster" → "Förster" case observed in amj_1
    # v2.4.28 audit). This relies on pdftotext's specific corruption pattern.
    t = re.sub(r"([A-Za-z])\s+([̀-ͯ])", r"\1\2", t)
    # Then NFC-compose to merge base+combining into precomposed (Fö → Förster
    # only works if Fö is precomposed; NFC handles the Potočnik case).
    t = unicodedata.normalize("NFC", t)

    # Snapshot raw page-number set before any mutation — R2 needs lines that
    # match `^\s*\d+\s*$` in the original extraction.
    _raw_page_numbers = _detect_recurring_page_numbers(text)

    # ── F0: Layout-aware running-header/footer + footnote strip ─────────
    # Requires a LayoutDoc from extract_pdf_layout. When present, strips
    # repeating running headers/footers and moves footnotes to an appendix
    # section after "\n\f\f\n". Populates report.footnote_spans +
    # report.footnote_texts (the captured footnote strings, parallel).
    if layout is not None:
        t, footnote_spans, footnote_texts = _f0_strip_running_and_footnotes(
            t, layout, table_regions=table_regions
        )
        report.footnote_spans = tuple(footnote_spans)
        report.footnote_texts = tuple(footnote_texts)
        report.steps_applied.append("F0")
        if footnote_spans:
            report.steps_changed.append("F0")

    # ── H0: document-header banner-line strip (NORMALIZATION_VERSION 1.8.0) ─
    # Note: H1 (hyphen-broken-word rejoin) is NOT applied here — the library's
    # S7 step below already removes column-wrap hyphens. H1 lives in
    # docpluck/render.py, where it runs on already-rendered markdown to
    # re-knit real compound words (e.g. Meta-Processes) split across caption
    # line wraps after S7 has handled the common case.
    before = t
    t = _strip_document_header_banners(t)
    report._track("H0_header_banner_strip", before, t, "header_banners_stripped")

    # ── T0: TOC dot-leader paragraph strip (NORMALIZATION_VERSION 1.8.0) ────
    before = t
    t = _strip_toc_dot_leader_block(t)
    report._track("T0_toc_dot_leader_strip", before, t, "toc_paragraphs_stripped")

    # ── P0: page-footer / running-header line strip (NORMALIZATION_VERSION 1.8.0) ─
    before = t
    t = _strip_page_footer_lines(t)
    report._track("P0_page_footer_strip", before, t, "page_footer_lines_stripped")

    # ── P0r: repetition-driven running-header strip (NORMALIZATION_VERSION 1.9.22) ─
    # Strips short lines that repeat ≥3 times AND match one of the 5
    # running-header / page-footer shape signatures (all-caps banner,
    # all-caps author-pair-AND, mixed-case author-pair-and, journal-DOI-
    # date footer, journal+issue-proof header). Also strips them as a
    # leading prefix on welded body lines. See _strip_recurring_running_
    # headers docstring for the 2026-05-23 cycle-2 origin.
    before = t
    t = _strip_recurring_running_headers(t)
    report._track("P0r_recurring_running_header_strip", before, t, "recurring_running_headers_stripped")

    # ── P1: front-matter metadata-leak paragraph strip (NORMALIZATION_VERSION 1.8.4) ─
    # Drops orphan acknowledgments / license / "previous version" / supplemental
    # -data / truncated-affiliation / bare-running-header paragraphs that
    # pdftotext serializes mid-Introduction via right-column reading order.
    # Position-gated to the first ~16% of the document so the legitimate
    # Acknowledgments / Funding / Affiliations sections at the END are
    # preserved. See _strip_frontmatter_metadata_leaks docstring for the
    # cross-publisher pattern coverage.
    before = t
    t = _strip_frontmatter_metadata_leaks(t)
    report._track("P1_frontmatter_metadata_leak_strip", before, t, "frontmatter_leaks_stripped")

    # ── H0b: lowercase letter-spaced display-label collapse (NORMALIZATION_VERSION 1.9.1) ─
    # Elsevier letter-spaced "a r t i c l e / i n f o / a b s t r a c t" box
    # labels. Runs pre-sectioning so the recovered "abstract" heads its section.
    before = t
    t = _rejoin_letterspaced_lowercase_labels(t)
    report._track("H0b_letterspaced_label_collapse", before, t, "letterspaced_labels_collapsed")

    # ── W0: Publisher-overlay watermark stripping (Request 9) ──────────
    # Runs BEFORE S0 so mid-line watermarks don't leak into body text via
    # downstream whitespace collapse. Patterns are precise (URL+date or
    # known publisher templates) — no false-positive risk on prose.
    before = t
    for _wp in _WATERMARK_PATTERNS:
        t = _wp.sub("", t)
    report._track("W0_watermark_strip", before, t, "watermarks_stripped")

    # ── W0b: recover '2'-for-U+2212 minus-sign corruption ──────────────
    before = t
    t = recover_corrupted_minus_signs(t)
    report._track("W0b_minus_sign_recovery", before, t, "minus_signs_recovered")

    # ── W0c: recover '<'-as-backslash glyph corruption ─────────────────
    before = t
    t = recover_corrupted_lt_operator(t)
    report._track("W0c_lt_operator_recovery", before, t, "lt_operators_recovered")

    # ── W0o: recover '<'-as-'b' glyph corruption (AdvTT family) ────────
    # Same class as W0c, different glyph. Raster-verified on
    # 10.1016/j.jesp.2016.11.001 p4, which PRINTS `p < 0.001` and extracts as
    # `p b 0.001` — 31 sites in that one paper, every one a p-value no
    # consumer's `p\s*<` regex could match. Gated on the OPERATOR SLOT because
    # `b` is a real coefficient symbol (17 legitimate uses in the same paper).
    before = t
    t = recover_lt_as_b_operator(t)
    report._track("W0o_lt_as_b_recovery", before, t, "lt_operators_recovered")

    # ── W0d: recover standalone '2'-for-minus via point-estimate ∈ CI ──
    before = t
    t = recover_minus_via_ci_pairing(t)
    report._track("W0d_minus_ci_pairing", before, t, "minus_signs_recovered")

    # ── W0j: recover '2'-for-minus in body-prose contrast-coding notes and
    # change/difference M-statistics that carry no bracket CI (efendic, 2026-07-03).
    before = t
    t = recover_prose_two_for_minus(t)
    report._track("W0j_prose_minus_recovery", before, t, "minus_signs_recovered")

    # ── W0k: recover '×'-as-'3' in body-prose / flattened-caption interaction
    # terms that the table-cell-scoped W0i cannot reach (efendic, 2026-07-04).
    before = t
    t = recover_times_interaction_glyph_in_prose(t)
    report._track("W0k_prose_times_recovery", before, t, "times_glyphs_recovered")

    # ── W0l: recover the two residual '×'-as-'3' prose shapes W0k's single-line
    # word-pair regex cannot reach — factorial-design notation `<digit>(…) 3
    # <digit>(…)` and a line-wrapped interaction term `<Pred> 3\n<Pred>`
    # (efendic residuals, 2026-07-04).
    before = t
    t = recover_times_design_notation(t)
    t = recover_times_wrapped_interaction(t)
    report._track("W0l_prose_times_residuals", before, t, "times_glyphs_recovered")

    # ── W0n's CALL SITE WAS HERE AND IS DELETED (v2.4.130, 2026-08-14).
    # `p < 05` now passes through as printed. The rule's premise — that a
    # dotless threshold is "provably corrupt" — was disproved by two real
    # papers whose identical text shape has OPPOSITE owners. Full reasoning at
    # the deleted definition above; pinned by
    # tests/test_p_threshold_decimal_real_pdf.py.

    # ── W0g (§A R5 / B7, 2026-05-23): recover DROPPED minus signs via CI ──
    # Distinct corruption class from W0d: pdftotext emits no glyph at all for
    # the leading U+2212 on certain fonts, so `b = -.022` reaches us as
    # `b = .022`. Only fires when a same-record CI bracket mathematically
    # PROVES the sign-flip (negative-bound bracket contains -X.XX but not X.XX).
    before = t
    t = recover_dropped_minus_via_ci_pairing(t)
    report._track("W0g_dropped_minus_ci_pairing", before, t, "dropped_minus_signs_recovered")

    # ── W0q: reattach a DETACHED minus on a CI upper bound in BODY PROSE ──
    # AUDIT EVERY CHANNEL. `recover_dropped_minus_ci_upper_in_text` existed only
    # in `cell_cleaning.clean_cell_text`, i.e. the TABLE channel — so a CI
    # written in a RESULTS SENTENCE never met it. Found by measuring O5's
    # blast radius and then confirmed against the primary source
    # (`10.1016/j.jesp.2021.104154`, rasterized p13): the page prints
    #
    #     t(399) = -3.79, p < .001, d = -0.38, 95% CI [-0.58, -0.18]
    #
    # and pdftotext delivers `[- 0.58,\n- 0.18]` — both minus signs detached
    # from their digits. Three such brackets in that paper, in body prose, and
    # the table channel could never reach any of them. A consumer whose CI
    # pattern requires the sign adjacent to the digit reads the upper bound as
    # POSITIVE, inverting a published interval.
    #
    # The repair is typographic: the dash is on the page, and the comma proves
    # it is a sign rather than a range separator. Measured over the 26-paper
    # baseline: fires on 3 brackets in 1 paper, and the estimate-containment
    # arithmetic repaired 0 of the 3 (it had grabbed `S.D = 1.43` as the
    # "estimate" and the containment test failed on an unrelated number).
    before = t
    t = recover_dropped_minus_ci_upper_in_text(t)
    report._track("W0q_ci_upper_detached_minus", before, t, "dropped_minus_signs_recovered")

    # ── W0h (§A R5 / B7, 2026-06-15): recover DROPPED minus via LAYOUT ──
    # The residual W0g cannot reach: a coefficient with only a t/p value and NO
    # CI (`b = -.022, t(87) = .17`). Reads the surviving `(cid:N)` minus glyph
    # from the layout channel in the `<stat> = <minus><coef>` slot. Gated on the
    # dedicated `dropped_minus_layout` param so F0 stays off in the section path.
    if dropped_minus_layout is not None:
        before = t
        t = recover_dropped_minus_via_layout(t, dropped_minus_layout)
        report._track("W0h_dropped_minus_layout", before, t, "dropped_minus_signs_recovered")

        # ── W0m (§A / GLYPH, 2026-07-04): recover a standardized β rendered as a
        # plain 'b'. Uses the SAME layout channel as W0h: the corrupted symbol is
        # a `b` in a math-symbol font (`AdvPSMP…`) in the `b = <coef>` slot, which
        # a genuine `b` coefficient never is. ar_apa Supplemental analyses: all
        # five `β = …` betas surfaced as `b = …`. Gated on the layout param so
        # the section path (no layout) is a no-op.
        before = t
        t = recover_beta_via_layout(t, dropped_minus_layout)
        report._track("W0m_beta_via_layout", before, t, "beta_glyphs_recovered")

        # ── W0p (2026-08-13): a typographic SUPERSCRIPT digit, fused ────────
        # `N = 2,5801` is the sample size 2,580 carrying footnote marker 1.
        # pdftotext renders a positioned glyph as an ordinary digit — the paper
        # this was proven on contains ZERO Unicode superscript codepoints — so
        # A5's exponent guard, which keys on the CODEPOINT, cannot see it. Only
        # font size + baseline prove it, and they live in the layout channel.
        #
        # Two injuries, both silent: the sample size reads as 25,801, and the
        # fused token matches the numeric-locale European marker `\d,\d{4,}`, so
        # a footnote marker MANUFACTURES a false locale signal (it produced one
        # of only two `conflict` verdicts across 396 English papers).
        #
        # This capability was validated and documented in August 2026 and then
        # wired into nothing — recorded as "signal validated, not yet wired".
        # That is the defect class this release exists to close: a capability
        # nothing invokes is indistinguishable from one never built.
        before = t
        t = recover_superscript_via_layout(t, dropped_minus_layout)
        report._track("W0p_superscript_layout", before, t, "superscript_markers_split")

    # ── W0e: recover Adobe-Symbol-font glyphs surfaced as PUA codepoints ─
    # pdftotext/mammoth emit a Symbol-font glyph with no ToUnicode CMap as a
    # U+F0xx Private-Use codepoint (β→U+F062, χ→U+F063, •→U+F0B7). The fixed
    # Adobe Symbol StandardEncoding maps each back to real Unicode. No-op on
    # text with no Symbol-block PUA codepoint.
    before = t
    t = recover_pua_glyphs(t)
    report._track("W0e_pua_glyph_recovery", before, t, "pua_glyphs_recovered")

    # ── Standard steps (S1-S9) ──────────────────────────────────────────

    # S0: Mathematical Alphanumeric Symbols (U+1D400-U+1D7FF) de-styling.
    # NFKC strips the math styling to the plain base letter/digit; Greek
    # stays Greek (see destyle_math_alphanumeric). Replaces pre-v2.4.34
    # hand-rolled loops that were (a) incomplete — only italic Latin + a
    # partial italic-Greek dict, so bold / sans / script variants and
    # ι/κ/λ/ν/ξ/τ/υ/ω leaked through — and (b) mapped math-italic Greek to
    # ASCII Latin (𝜂->"n", 𝛽->"b"), corrupting statistical symbols.
    before = t
    t = destyle_math_alphanumeric(t)
    if t != before:
        report._track("S0_smp_to_ascii", before, t, "smp_chars_converted")

    # S1: Encoding validation
    before = t
    t = t.replace("\x00", "")
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    if t != before:
        report._track("S1_encoding_validation", before, t, "encoding_fixes")
    else:
        report.steps_applied.append("S1_encoding_validation")

    # S2: Accent recombination
    before = t
    _accent_maps = {
        "\u00B4": {"a": "\u00e1", "e": "\u00e9", "i": "\u00ed", "o": "\u00f3", "u": "\u00fa",
                    "A": "\u00c1", "E": "\u00c9", "I": "\u00cd", "O": "\u00d3", "U": "\u00da"},
        "\u02C6": {"a": "\u00e2", "e": "\u00ea", "i": "\u00ee", "o": "\u00f4", "u": "\u00fb"},
        "\u00A8": {"a": "\u00e4", "e": "\u00eb", "i": "\u00ef", "o": "\u00f6", "u": "\u00fc"},
        "\u0060": {"a": "\u00e0", "e": "\u00e8", "i": "\u00ec", "o": "\u00f2", "u": "\u00f9"},
    }
    for accent, mapping in _accent_maps.items():
        for vowel, combined in mapping.items():
            t = t.replace(vowel + accent, combined)
            t = t.replace(accent + vowel, combined)
    report._track("S2_accent_recombination", before, t, "accents_recombined")

    # S3: Ligature expansion \u2014 body channel. Calls the shared
    # decompose_ligatures helper (full U+FB00-FB06 block, incl. \ufb05/\ufb06\u2192st) so the
    # body, table-cell, and render-post-process channels stay in lockstep.
    before = t
    t = decompose_ligatures(t)
    report._track("S3_ligature_expansion", before, t, "ligatures_expanded")

    # S4: Quote normalization
    before = t
    t = re.sub(r"[\u201C\u201D\u201E\u201F\u2033\u2036]", '"', t)
    t = re.sub(r"[\u2018\u2019\u201A\u201B\u2032\u2035]", "'", t)
    report._track("S4_quote_normalization", before, t, "quotes_normalized")

    # S5: Dash and minus normalization
    before = t
    t = t.replace("\u2212", "-")   # Unicode MINUS SIGN (critical for stats)
    t = t.replace("\u2013", "-")   # en-dash
    t = t.replace("\u2014", "--")  # em-dash
    t = t.replace("\u2010", "-")   # Unicode hyphen
    t = t.replace("\u2011", "-")   # non-breaking hyphen
    report._track("S5_dash_normalization", before, t, "dashes_normalized")

    # S5a: Context-aware U+FFFD -> eta recovery (ESCImate Request 1.2)
    # pdftotext occasionally emits U+FFFD in place of Greek eta. The pdfplumber
    # SMP fallback catches most; this is second-line defense when both engines
    # drop the character. CONTEXT-AWARE — only rewrites U+FFFD when followed by
    # a statistical "eta-squared" pattern (eta^2 = .NNN). Generic encoding-fail
    # FFFDs in prose are left alone for the caller's quality scoring to flag.
    before = t
    _fffd_before = t.count("\ufffd")
    # Core pattern: FFFD followed by (optional space) (superscript-2 or digit 2) = number
    t = re.sub(
        r"\ufffd(\s*(?:\u00B2|2)\s*=\s*-?\.?\d)",
        r"eta\1",
        t,
    )
    # Partial-eta subscript variant: FFFD_p^2 = .04
    t = re.sub(
        r"\ufffd(_?p\u00B2\s*=\s*-?\.?\d)",
        r"eta\1",
        t,
    )
    _fffd_after = t.count("\ufffd")
    _fffd_recovered = _fffd_before - _fffd_after
    report.steps_applied.append("S5a_fffd_context_recovery")
    if _fffd_recovered > 0:
        report.changes_made["fffd_context_recovered"] = _fffd_recovered
        report.steps_changed.append("S5a_fffd_context_recovery")

    # S5b: Context-aware U+FFFD -> comparison-operator (>= / <=) recovery.
    # pdftotext AND pdfplumber destroy the cmsy10 (TeX Computer Modern
    # math-symbol font) >= / <= glyphs to U+FFFD on tightly-kerned PDFs -- the
    # layout channel cannot recover it (the glyph identity is gone from both
    # engines), so recover_fffd_comparison_operators rebuilds it from context:
    # airtight complement pairing ("<N" partitioned against "[FFFD]N"), then a
    # document-consensus rule for a lone "[FFFD]N". Sibling of S5a.
    before = t
    _fffd_cmp_before = t.count("�")
    t = recover_fffd_comparison_operators(t)
    _fffd_cmp_recovered = _fffd_cmp_before - t.count("�")
    report.steps_applied.append("S5b_fffd_comparison_recovery")
    if _fffd_cmp_recovered > 0:
        report.changes_made["fffd_comparison_recovered"] = _fffd_cmp_recovered
        report.steps_changed.append("S5b_fffd_comparison_recovery")

    # S6: Whitespace and invisible character normalization
    before = t
    # 2026-06-06 (citationguard text-extraction handoff, Defect 1): a SOFT
    # HYPHEN (U+00AD) immediately before a line break is ALWAYS a
    # discretionary extraction hyphen splitting one word across the wrap
    # (relation\u00AD\nship). Join the fragments (drop U+00AD AND the
    # newline) BEFORE the bare strip below; otherwise the bare strip
    # leaves relation\nship, which reflows to "relation ship" (a space-
    # broken word) ~1/3 of the time. Gated on a following letter so a
    # U+00AD before a blank line / punctuation never collapses a
    # paragraph boundary. Unlike U+002D (real hyphen, ambiguous - handled
    # by S7 with its own guard), U+00AD is unambiguous and always
    # removable. Recovers com/mitment, pro/motion, altru/ism,
    # relation/ship on chan_feldman_2025_cogemo (was: 6 space-broken
    # words surviving to rendered output).
    t = re.sub(r"\u00AD[ \t]*\r?\n[ \t]*(?=[A-Za-z])", "", t)
    t = t.replace("\u00AD", "")    # soft hyphen (invisible, breaks search — 14/50 test PDFs)
    t = t.replace("\u00A0", " ")   # NBSP
    t = t.replace("\u2002", " ")   # en space
    t = t.replace("\u2003", " ")   # em space
    t = t.replace("\u2004", " ")   # three-per-em space
    t = t.replace("\u2005", " ")   # four-per-em space
    t = t.replace("\u2006", " ")   # six-per-em space
    t = t.replace("\u2007", " ")   # figure space
    t = t.replace("\u2008", " ")   # punctuation space
    t = t.replace("\u2009", " ")   # thin space
    t = t.replace("\u200A", " ")   # hair space
    t = t.replace("\u200B", "")    # zero-width space
    t = t.replace("\u200C", "")    # zero-width non-joiner
    t = t.replace("\u200D", "")    # zero-width joiner
    # 2026-08-05 (run 7, xiao_2021_crsp canary): BIDI FORMAT marks. The list
    # above stripped U+200B/C/D and U+FEFF below, but skipped U+200E/U+200F \u2014
    # an omission in a sequence, not a decision. An invisible LRM survived into
    # rendered output right after a citation's closing paren
    # (`Kausel (2013)\u200E`), which breaks STRING EQUALITY and SEARCH for every
    # downstream consumer \u2014 a citation checker comparing `(2013)` sees a
    # mismatch it cannot see on screen. Same rationale as the U+00AD strip
    # above ("invisible, breaks search"). Measured blast radius: 2 occurrences
    # in 1 of 101 corpus PDFs, so this is a correctness fix, not a hot path.
    t = t.replace("\u200E", "")    # left-to-right mark
    t = t.replace("\u200F", "")    # right-to-left mark
    t = t.replace("\u2060", "")    # word joiner (zero-width no-break)
    t = t.replace("\u202F", " ")   # narrow no-break space
    t = t.replace("\u205F", " ")   # medium mathematical space
    t = t.replace("\u3000", " ")   # ideographic space
    t = t.replace("\uFEFF", "")    # BOM / zero-width no-break space
    # Full-width ASCII → ASCII (U+FF01-FF5E → U+0021-007E)
    chars = list(t)
    for i, c in enumerate(chars):
        cp = ord(c)
        if 0xFF01 <= cp <= 0xFF5E:
            chars[i] = chr(cp - 0xFEE0)
    t = "".join(chars)
    t = re.sub(r"[ \t]{2,}", " ", t)
    report._track("S6_whitespace_normalization", before, t, "whitespace_normalized")

    # S7: Hyphenation repair. The trailing letter is matched as a lookahead so a
    # run of consecutive `word-\nword-\nword` breaks all join in one pass — a
    # `re.sub` of `(g1)-\n(g2)` consumes g2 and resumes after it, missing the
    # `g2-\ng3` join (an N-break chain takes N passes to fully repair, breaking
    # normalize_text idempotency).
    before = t
    t = re.sub(r"([a-z])-\n(?=[a-z])", r"\1", t)
    report._track("S7_hyphenation_repair", before, t, "hyphenations_repaired")

    # S7a (v2.4.20, NORMALIZATION_VERSION 1.8.7): space-broken-compound
    # rejoin. See _rejoin_space_broken_compounds docstring + the pair
    # list defined above for the curated cases (experi/ments,
    # con/ducted, presenta/tion, ques/tionnaires, etc.).
    before = t
    t = _rejoin_space_broken_compounds(t)
    report._track("S7a_space_broken_compound_rejoin", before, t,
                  "space_broken_compounds_rejoined")

    # S8: Mid-sentence line break joining. Two fixes packaged here, both
    # idempotency-driven:
    # 1) Trailing char is a lookahead (not a captured group) so a run of N
    #    consecutive joinable lines fully merges in one pass — `re.sub(g1\ng2)`
    #    used to consume g2 and resume past it, missing every other adjacency
    #    in a chained run (an N-line paragraph needed log2(N)+1 passes).
    # 2) The trailing class includes lowercase Greek (U+03B1-03C9). pdftotext
    #    surfaces Greek letters as their actual Unicode glyph; the A5 academic
    #    step transliterates them to ASCII names (`σ`→`sigma`) LATER in the
    #    pipeline. So a `,\nσ²(ξ)` line break used to escape S8 on pass 1
    #    (Greek not in `[a-z]`), A5 then turned it into `,\nsigma2(xi)`, and
    #    only the NEXT normalize pass joined it — breaking idempotency.
    before = t
    t = re.sub(r"([a-z,;])\n(?=[a-zα-ω])", r"\1 ", t)
    report._track("S8_line_break_joining", before, t, "line_breaks_joined")

    # For academic level: join stat line breaks BEFORE stripping page numbers,
    # because standalone numbers like "484" on their own line might be stat values
    # that got split from "p =\n484". S9 would strip them as page numbers.
    if level == NormalizationLevel.academic:
        before = t
        # Basic stat line break: `p\n<`, `p\n=`, `p\n>` → `p <` etc.
        t = re.sub(r"([pP])\s*\n\s*([=<>])", r"\1 \2", t)

        # A1-extended (2026-04-11, v1.3.1): column-bleed BETWEEN `p` and the
        # operator. Pattern observed in PSPB papers: `p\n\n01\n\n01\n\n= .28`
        # where "01", "11" etc. are short column-bleed fragments on their own
        # lines. Must run before the simple `p =\n digit` rule below, otherwise
        # the first fragment gets interpreted as the value.
        t = re.sub(
            r"([pP])\s*\n(?:\s*\d{1,3}\s*\n){1,4}\s*([<=>])",
            r"\1 \2",
            t,
        )
        # Same pattern with column-bleed BETWEEN operator and value:
        # `p =\n01\n11\n.28` → `p = .28`. Must run before the simple
        # `p =\n digit` rule below to avoid eating the first fragment.
        t = re.sub(
            r"([pP]\s*[<=>])\s*\n(?:\s*\d{1,3}\s*\n){1,4}\s*([-.\d])",
            r"\1 \2",
            t,
        )

        # Simple: p =\n digit → p = digit (must run AFTER column-bleed rules)
        t = re.sub(r"([pP]\s*[=<>])\s*\n\s*(\d)", r"\1 \2", t)
        t = re.sub(r"(OR|CI|RR)\s*\n\s*(\d)", r"\1 \2", t)
        t = re.sub(r"(95\s*%)\s*\n\s*(CI)", r"\1 \2", t)
        t = re.sub(r"([=<>])\s*\n\s*([-\d.])", r"\1 \2", t)
        # Column-boundary garbage: skip letter-starting text (1-20 chars) between
        # p= and a valid p-value on the next line.  Two independent safety guards:
        # Guard 1 — garbage must start with [a-zA-Z] (real stat content starts with
        #   digits/dots, column-bleed garbage starts with word fragments).
        # Guard 2 — next-line value must match 0?\.\d+ (valid p-value format;
        #   rejects section numbers like 8.3, page numbers like 1024, footnotes).
        # See MetaESCI D5 audit (2026-04-12): old [^\n]{1,20} ate real p-values.
        t = re.sub(r"(p\s*[<=>]\s*)[a-zA-Z][^\n]{0,19}\n\s*(0?\.\d+)", r"\1\2", t)
        # Rejoin test stat → p-value across line break: "t(23) = 2.34,\n p < .001"
        t = re.sub(r"([,;])\s*\n\s*(p\s*[<=>])", r"\1 \2", t)
        # Rejoin effect size → CI across line break: "d = 0.45,\n 95% CI"
        t = re.sub(r"([,;])\s*\n\s*(\d+%\s*CI)", r"\1 \2", t)
        report._track("A1_stat_linebreak_repair", before, t, "stats_repaired")

    # S9: Header/footer removal
    before = t
    lines = t.split("\n")
    line_counts: dict[str, int] = {}
    line_positions: dict[str, list[int]] = {}
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if 15 <= len(stripped) <= 120:
            line_counts[stripped] = line_counts.get(stripped, 0) + 1
            line_positions.setdefault(stripped, []).append(idx)
    # Cycle 14 (v2.4.66) — minimum-gap discriminator.
    # A repeated line that appears ≥5 times is a candidate header/footer.
    # The old rule stripped every candidate; this false-positives on
    # TABLE ROW LABELS that repeat across columns of a regression table
    # (socius-3 `Intend vs. Later` ×5, majumder `eta2p = .001, ⸸` ×9,
    # collabra-rnr `Identifiability` ×5, social-forces-1 `Emotional
    # neglect` ×5 — all cluster within a small region).
    #
    # The MINIMUM GAP between consecutive occurrences cleanly separates
    # the two classes:
    #   - Table labels cluster in adjacent rows → min_gap ≤ 14 (range
    #     3-14 across 4 corpus cases).
    #   - Running headers appear once per page → min_gap ≥ 25 (range
    #     25-100 across multiple corpus papers).
    # Threshold at min_gap ≥ 20 separates the two with margin on both
    # sides. The range-coverage approach was abandoned because doc length
    # is too variable — short docs can have running-header range only
    # 65-72% (below the natural 90% mark seen in long docs), causing
    # idempotence drift when pass 2 has a shorter input.
    repeated: set[str] = set()
    for s, count in line_counts.items():
        if count < 5:
            continue
        positions = line_positions[s]
        gaps = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
        if not gaps:
            continue
        # Two paths qualify a repeated line as a header/footer:
        #   - min_gap ≥ 20: cleanly-spaced running header (one per page).
        #   - count ≥ 20: super-frequently-repeated watermark / sidebar /
        #     PMC-style "Author Manuscript" boilerplate that repeats multiple
        #     times per page (consecutive occurrences yield min_gap = 1).
        # Both forms are publisher boilerplate, never body content.
        if min(gaps) >= 20 or count >= 20:
            # Cycle 15 (v2.4.67) — caption/citation guard. Some table
            # source-attribution captions are repeated once per table and
            # land in the same min_gap≥20 distribution as a running header,
            # but they are LEGITIMATE body content (the data-source caption
            # under each table, e.g. socius-4 `Source: Authors' calculation,
            # American Time Use Survey (2003-2023).` ×13). Caption text has
            # a structural signature page-footer boilerplate never has:
            # natural-prose density with rich punctuation. Two cheap and
            # generally-applicable discriminators:
            #   (a) parenthesized 4-digit year or year-range, e.g.
            #       `(2003-2023)`, `(2024)` — citation/data-source marker.
            #   (b) ≥6 spaces (≥7 words) AND ends with sentence-ending
            #       punctuation — caption-style prose.
            # Page-footer boilerplate is shorter and either lacks `.` or has
            # no parenthesized year. Both checks are content-shape, not
            # paper-specific.
            if _LINE_HAS_YEAR_PARENS_RE.search(s):
                continue
            if s.count(" ") >= 6 and s.rstrip().endswith((".", "!", "?")):
                continue
            repeated.add(s)
    if repeated:
        lines = [l for l in lines if l.strip() not in repeated]
        t = "\n".join(lines)
    # Strip standalone page numbers — 1-3 digit unconditionally.
    t = re.sub(r"^\s*\d{1,3}\s*$", "", t, flags=re.MULTILINE)
    # v2.4.3/v2.4.5: 4-digit page numbers (continuous-pagination journals like
    # PSPB where volume runs page numbers into the 1000s, e.g.
    # ``efendic_2022_affect`` with pages 1174-1185). Two patterns fire:
    #
    #   (A) RECURRING (v2.4.3) — same value appears ≥3 times. Catches PDFs
    #       where every page repeats the same volume number on its own line
    #       (rare for true page numbers, but happens for volume markers).
    #
    #   (B) SEQUENTIAL (v2.4.5) — ≥3 distinct standalone 4-digit values in
    #       the doc AND they cluster within a 50-page range (max - min ≤ 50)
    #       AND the average per-page gap is small (mean diff ≤ 3). This is
    #       the canonical continuous-pagination signature: page numbers
    #       monotonically increasing across the article. The conservative
    #       gates protect table cells (where 4-digit values would have
    #       larger spreads and irregular gaps).
    four_digit_counts: dict[str, int] = {}
    for ln in t.split("\n"):
        s = ln.strip()
        if len(s) == 4 and s.isascii() and s.isdigit() and 1000 <= int(s) <= 9999:
            four_digit_counts[s] = four_digit_counts.get(s, 0) + 1

    # Pattern A: same value recurs ≥3 times.
    # Cycle 14 (v2.4.66) — exclude citation-year range (1900-2100). A
    # 4-digit value that repeats ≥3 times is most-often a citation year
    # ("House, R. J. 1971" cited in multiple table rows or the references
    # section), not a page number. Page numbers in the citation-year
    # range are extremely rare; corrupting a citation year by stripping
    # it is common and harmful (amle-1 had `1971` stripped under the old
    # rule).
    strip_set: set[str] = {
        s for s, c in four_digit_counts.items()
        if c >= 3 and not (1900 <= int(s) <= 2100)
    }

    # Pattern B: ≥3 distinct values clustered tightly together.
    #
    # v2.4.11: scan for the densest sub-cluster instead of computing global
    # spread. chan_feldman_2025_cogemo has page numbers 1228-1249 (21 values,
    # tight) PLUS year mentions like 1997 and 2023 in inline citations. The
    # old check `spread = max - min` saw the global span 1228-2023 (795
    # chars) and rejected the cluster outright. Now we slide a 50-window
    # across the sorted values, find the run with ≥3 values + mean diff ≤3,
    # and strip those.
    if len(four_digit_counts) >= 3:
        values = sorted(int(s) for s in four_digit_counts.keys())
        # Greedy clustering: walk sorted values, extend a cluster while the
        # next value is within 5 of the previous one. Pick the longest run
        # with ≥3 values that spans ≤50 and mean-diff ≤3.
        clusters: list[list[int]] = [[values[0]]]
        for v in values[1:]:
            if v - clusters[-1][-1] <= 5:
                clusters[-1].append(v)
            else:
                clusters.append([v])
        for cluster in clusters:
            if len(cluster) < 3:
                continue
            spread = cluster[-1] - cluster[0]
            if spread > 50:
                continue
            diffs = [cluster[i + 1] - cluster[i] for i in range(len(cluster) - 1)]
            mean_diff = sum(diffs) / len(diffs)
            if mean_diff <= 3.0:
                strip_set.update(str(v) for v in cluster)

    # Cycle 9b (v2.4.61 / NORMALIZATION_VERSION 1.9.15) — per-occurrence
    # gating to protect table sample-size values.
    #
    # The previous "strip every occurrence in strip_set" rule was a corpus-
    # level false-positive: A3 (academic level) strips thousands-separator
    # commas in N contexts (`Observations: 7,182` → `Observations: 7182`),
    # and pdftotext sometimes lands the bare N on its own line (right-aligned
    # in a regression table). chandrashekar 2020 has 4 regression columns
    # citing the SAME N=7182 → 4 standalone `7182` lines → Pattern A flags
    # `7182` as a page number → all 4 get stripped on pass 2 (pass 1 hasn't
    # seen A3 yet, so the line still reads `7,182` and S9 doesn't flag it;
    # this is what causes the non-idempotence). Stripping table N is real
    # production text loss.
    #
    # Discriminator: a per-page marker (page number / volume number) sits
    # ISOLATED — surrounded by prose, blank lines, or section headings. A
    # table cell value sits in a VERTICAL BLOCK of other numeric values
    # (other table cells in the same column). So: keep the line if EITHER
    # its nearest non-blank neighbor above OR below is numeric-only.
    if strip_set:
        lines = t.split("\n")
        new_lines: list[str] = []
        for idx, ln in enumerate(lines):
            if ln.strip() not in strip_set:
                new_lines.append(ln)
                continue
            if _is_in_numeric_block(lines, idx):
                # Table-like context: keep. (Cycle 9b — clears chandrashekar
                # `7182`, aiyer `1118`/`1265`, and ~7 sibling regression-
                # table papers from the non-idempotent set.)
                new_lines.append(ln)
            else:
                new_lines.append("")
        t = "\n".join(new_lines)
    report._track("S9_header_footer_removal", before, t, "headers_removed")

    # Limit consecutive newlines
    t = re.sub(r"\n{3,}", "\n\n", t)

    # ── D5 numeric-locale inference: DELETED in v2.4.129 ───────────────
    #
    # A document-level verdict used to be computed here and published on the
    # report. It is gone, with its whole apparatus. The short version: it gated
    # nothing, it was never released, and it was confidently WRONG on the one
    # real case ever found — an English paper whose ~130-cell comma-decimal
    # table scored `european_markers=0` because every marker it recognised
    # requires an operator and a table cell has none.
    #
    # docpluck assumes English papers in US numeric convention and passes
    # European numbers through unconverted. See `docs/SCOPE.md` and the marker
    # tables above, which survive as the vocabulary for a future LINE- or
    # TABLE-scoped guard — never for another document-level verdict.

    # ── Academic steps (A2-A5) ─────────────────────────────────────────
    # Note: A1 already ran above (before S9) to prevent number stripping

    if level == NormalizationLevel.academic:

        # A2 AND A3a WERE HERE AND ARE DELETED (v2.4.130, 2026-08-14).
        #
        # A2 restored a decimal point it believed the PDF had lost
        # (`p = 38.` -> `p = .38.`); A3a stripped thousands separators from
        # integers (`N = 1,182` -> `N = 1182`). They are deleted for DIFFERENT
        # reasons, recorded separately below so neither argument is used to
        # justify the other.
        #
        # ── A2 — it repaired the PAPER, which is not ours to repair ─────────
        #
        # Directive 2026-08-13: docpluck extracts and normalizes what is
        # PRINTED. A defect docpluck's own pipeline introduced is docpluck's to
        # fix; a defect the AUTHOR or the JOURNAL printed is not, because
        # docpluck has no channel through which to announce a repair, so a
        # silent one LAUNDERS a real error into a meta-science pipeline: the
        # consumer then validates a number the paper never printed, and the
        # author never learns.
        #
        # A2 had NO CITED PAPER anywhere in its code. Asked for one, both of
        # its firing sites in 297 English papers turned out to be the paper's
        # own error, confirmed by RASTERIZING the page rather than by asking an
        # extractor:
        #
        #   10.1177/0146167210380928 p13   prints `B = -0.28, SE = 0.31, p = 38.`
        #   10.1016/j.jesp.2016.11.001 p7  prints `t(186) = 3.90, p = 001, d = 0.6`
        #
        # In BOTH, correctly-dotted numbers sit on the same line — `0.28`/`0.31`
        # and `3.90`/`$4.00` — so the text layer did not drop anything. The
        # author did. A2 was rewriting a published typo into a plausible
        # statistic, 2 sites out of 2.
        #
        # THE DECIDING EVIDENCE, and why no gate can save this rule: the SAME
        # text shape has OPPOSITE OWNERS in two real English papers.
        # `10.1016/j.jesp.2009.12.011` p3 prints `p < 05` with no dot (the
        # author's error) while `10.1177/0956797613482946` p6 prints `p < .05`
        # and our OCR text layer lost it (ours). A layout-advance gate to
        # separate them was built and REFUTED — the second paper is a SCAN
        # whose char boxes come from an OCR engine rather than the typesetter,
        # so the gate manufactures its own evidence for exactly the case it
        # exists to catch. Under irreducible ambiguity the default is
        # PASS-THROUGH, because pass-through is reversible for the consumer and
        # a repair is not. The same reasoning retires W0n (see its own block).
        #
        # ── A3a — its purpose evaporated, and it produced 1000x errors ──────
        #
        # A3a existed to pre-empt A3. Its own comment said so: "This step
        # strips commas from ONLY the matched integer token in sample-size
        # contexts, SO A3 SEES THE ALREADY-CLEAN INTEGER AND LEAVES IT ALONE",
        # and "Runs in academic level because A3 itself is academic-only; in
        # standard level the commas are preserved by default (no A3 to corrupt
        # them)." A3 was deleted in v2.4.129. The rule was left standing with
        # nothing left to protect against, and what remained was not protection
        # but a default rewrite that DELETES a separator the paper printed.
        #
        # It also made the library answer one question three ways, which is the
        # "one concept, one table" failure (L-024). For `N = 1,182`:
        #     standard level                     ->  `1,182`   preserved
        #     academic + preserve_math_glyphs    ->  `1,182`   counted, not stripped
        #     academic, default                  ->  `1182`    stripped
        # A library that converts one input three ways has no contract at all.
        #
        # THE HARM, measured and rasterized twice independently:
        #   10.1177/0956797620935584  Battal et al., Psych Sci, Table S2 p24
        #     'df- satterthwaite' PRINTS  185,178   31,836   188,193
        #     we delivered                185178    31836    188193
        #     t-ratios         PRINT      -1,966    -7,799
        #     we delivered                -1966     -7799
        # A Satterthwaite df is FRACTIONAL by construction. The collision is
        # STRUCTURAL, not a tail case: A3a's discriminator ("every group after
        # the first is exactly 3 digits") is satisfied BY CONSTRUCTION for any
        # comma-locale number with a 3-digit integer part and 3-decimal
        # precision, so an affected table collides on EVERY qualifying row.
        # This class has already produced wrong published numbers downstream —
        # a consumer recorded `U = 55,890` read as `55.89`, publishing a
        # rank-biserial of 0.99938 where the truth is 0.38275.
        #
        # THE COUNTER-EVIDENCE, stated rather than buried: 137 A3a firing sites
        # read individually across 65 papers are 137/137 unambiguous US counts.
        # A3a was right almost always. That does not save it, because being
        # right is only a defence of a rewrite that is NEEDED, and once A3
        # was gone nothing needed it. `1,000` is not a problem; it is clearly
        # one thousand. Rewriting it to `1000` repairs nothing and REMOVES the
        # evidence a consumer would need to notice a European table — which is
        # precisely the evidence the future line-scoped locale guard requires.
        #
        # ITS TELEMETRY SAID THE OPPOSITE OF WHAT IT DID. The step was named
        # `A3a_thousands_separator_protect` and its metric key was
        # `thousands_separators_preserved`, while the operation was
        # `.replace(",", "")`. A consumer reading `changes_made` saw
        # "thousands_separators_preserved: 3" and would reasonably conclude
        # nothing had been lost. That is worse than no instrumentation: silence
        # invites a check, a false all-clear forecloses one.
        #
        # ── STATED CONSEQUENCE, not hidden ──────────────────────────────────
        #
        # Both are BREAKING output changes. `p = 38.` and `p < 05` now reach
        # the consumer as printed, and `N = 1,182` keeps its separator. This
        # MOVES WORK ONTO THE CONSUMER and can cost them coverage rather than
        # producing a loud failure: ESCImate's `pat_CI3` does not match
        # `[-0.60, -0,26]`, so an interval SILENTLY VANISHES from their record
        # instead of misparsing. That cost is real, was measured before the
        # decision, and was accepted by the owner of every consumer on
        # 2026-08-14, who directed that we ship the correct behaviour and
        # notify consumers to adapt afterwards.
        #
        # Pinned by tests/test_a2_does_not_repair_the_paper.py and
        # tests/test_a3a_thousands_separators_pass_through.py.
        # See docs/SCOPE.md and LESSONS.md L-026, L-029, L-031.

        # A3: Decimal comma normalization (European locale)
        #
        # Leading lookbehind (?<![a-zA-Z,0-9\[\(]) prevents four classes of
        # false positive:
        #
        # 1. Author affiliation superscripts — "Braunstein1,3" or "Wagner1,3,4"
        #    where the 1/3/4 are citation markers, not decimals. The letter
        #    before "1" (Braunstein) and the comma before "3" (Wagner middle)
        #    block those matches. Cross-ported from effectcheck/R/parse.R:189.
        #
        # 2. Multi-value CI content — "[0.45,0.89]" where A4 later fixes the
        #    comma-separated pair. The digit before the comma (4) would
        #    otherwise let A3 corrupt "5,089" -> "5.089" because the trailing
        #    "]" matches the lookahead. Excluding digits from the lookbehind
        #    blocks this.
        #
        # 3. Existing well-formed decimal lists like "0.5,0.8,1.2" where A3
        #    should leave the commas alone (they're separators, not decimals).
        #
        # 4. Statistical df brackets — "F[2,42]", "F(2,42)", "t(1,197)" where
        #    pdftotext produces the tight-no-space df form. Without excluding
        #    "[" and "(" from the lookbehind, A3 corrupts "F[2,42]=13.689"
        #    into "F[2.42]=13.689", which effectcheck's parser then fails to
        #    match. Regression discovered via MetaESCI D2 lost-source repro
        #    (10.15626/mp.2019.1723, 2026-04-11). The A3a step above handles
        #    N=/df= thousands separators before A3 runs, so excluding "(" here
        #    does not affect that path.
        #
        # The trailing lookahead keeps the original restrictive character set
        # (\s | ; ) ] | $). Broadening it to [^0-9a-zA-Z] caused A4 ordering
        # regressions historically.
        #
        # v2.4.17 (NORMALIZATION_VERSION 1.8.5): minor extension — add
        # `\.(?!\d)` to the lookahead so sentence-ending decimals like
        # "d = 0,87." get normalized to "d = 0.87." Same pattern A2 already
        # uses safely (line 1466 ``_A2_LOOKAHEAD``). The `(?!\d)` guard
        # blocks the thousands-separated-decimal case "1,234.567" — that
        # still doesn't match because the next char after the comma group
        # is `.` followed by a digit. Validated against the existing A3 +
        # A4 regression suite.
        # ── v2.4.127: A3 now converts ONLY in the VALUE POSITION ─────────────
        #
        # The lookbehind above is an enumeration of what may not precede the
        # number, and an enumeration is never complete. Measured on the
        # 101-PDF corpus, the shipped rule fired 29 times across 13 papers and
        # ~27 of those were not decimals at all — every one of them a shape the
        # lookbehind does not list:
        #
        #   'compared with controls.7,8 However'  -> 'controls.7.8 However'
        #        a Vancouver citation superscript run: the digits follow a
        #        SENTENCE PERIOD, which the lookbehind allows
        #   'up to ~25%6,28.'                     -> '...%6.28.'   (after '%')
        #   'Erik. T. Frank 1,2 , Lucie Kesner 3' -> 'Frank 1.2 ,'
        #        an affiliation run: only its INTERIOR is comma-preceded, so
        #        the first element was protected by nothing
        #   'Experiments 1,2 showed'              -> 'Experiments 1.2 showed'
        #   flattened ANOVA table cells '9,57'    -> '9.57'  (a df pair)
        #
        # The only two genuine European decimals in the whole corpus are
        # leading-zero hazard ratios ('0,92', '0,77'), which A3c converts on
        # its own. So the rule was ~2 right and ~27 wrong.
        #
        # The replacement discriminator is STRUCTURAL and positive rather than
        # a growing list of exclusions: an operator immediately before the
        # number proves the token is a VALUE. It is the same key ESCImate's
        # shared spec uses for its D1b rule ("the guard is the value position,
        # not the locale"), so both implementations now agree on the principle
        # rather than on a regex.
        #
        # Digit bounds carry the rest of the discrimination:
        #   - 1-2 digits AFTER the comma. A thousands group is EXACTLY three
        #     by construction, so this rule can never collide with A3a.
        #     STATED LIMIT (adversarial review, 2026-08-12, reproduced): the
        #     3-digit case is not merely "left ambiguous" — A3a has already
        #     RESOLVED it toward thousands and removed the comma, so
        #     `HR = 1,234` reaches the consumer as `1234` and a continental
        #     1.234 is unrecoverable downstream. That is the shared spec's
        #     agreed T1 default (it is the right default for English APA
        #     text, and `N = 1,182` needs it), but the consumer cannot
        #     "record that a value was resolved under ambiguity" if the
        #     evidence is gone. Raised with ESCImate rather than changed
        #     unilaterally: flipping it would alter every English paper.
        #   - 1-4 digits BEFORE it, so `M = 12,34` and `t = 1234,56` convert.
        #     The old rule required exactly one and silently missed both
        #     (ESCImate conformance case `decimal-two-integer-digits`).
        # The lookahead now admits a LIST comma — the divergence ESCImate
        # filed on 2026-08-09, where `t(28) = 2,21, d = 0,45` left `2,21`
        # unconverted and a parser read 2. Admitting `,` is safe ONLY under
        # the operator gate: measured over the corpus, admitting it without
        # the gate would have converted 52 citation/affiliation superscript
        # runs across 16 of 101 papers and zero real decimals, and an
        # adversarial pass then broke the narrower "comma + space" variant too
        # ('Studies 1,2, and 3 replicated' -> 'Studies 1.2, and 3').
        #
        # The admitted list comma carries `(?!\d)`: a list comma in prose is
        # followed by a space, a digit-run separator by a digit. Without it the
        # rule fired on an `=`-coded categorical enumeration — `Group = 1,2,3`
        # -> `Group = 1.2,3` — which is a value POSITION but not a value
        # (adversarial review, 2026-08-12; reproduced, then pinned).
        #
        # ACCEPTED, STATED COSTS — three, all measured, none hidden:
        #   1. A European decimal with no operator is left VERBATIM. That is
        #      "prose" in the common case ("The score was 123,4 on that
        #      scale") but the class is broader: a bare TABLE CELL has no
        #      operator either, so a flattened `Estimate | 1,23` column is not
        #      converted. Zero instances in the 101-PDF corpus, which contains
        #      no continental tables — an absence, not a proof.
        #   2. The operator does not prove "value" for a coding declaration:
        #      `Sex = 0,1 (0 = male, 1 = female)` still becomes `0.1`. Same
        #      shape as a real `d = 0,5`; undecidable without vocabulary.
        #      Pre-existing, unchanged, and stated rather than implied.
        #   3. Preserving an ambiguous token is NOT the same as getting it
        #      wrong: the source form is intact and both readings remain
        #      recoverable, where a fused pair is irreversible. Resolving it
        #      needs document-level locale evidence — the consumer's layer in
        #      the agreed split (ESCImate SPEC "Residual ambiguity").
        # `tools/diag/a3_comma_lookahead_scan.py`.
        # A3 and A3c WERE HERE AND ARE DELETED (v2.4.129, 2026-08-14).
        #
        # A3 converted an operator-gated European decimal comma
        # (`d = 0,45` -> `d = 0.45`); A3c converted a leading-zero decimal
        # (`(0,003)` -> `(0.003)`). Together with A3d, deleted earlier the same
        # day, they were docpluck's entire EU->US conversion apparatus.
        #
        # USER DIRECTIVE, 2026-08-14 — this is scope, not tuning:
        #
        #   docpluck's focus is ENGLISH papers in US locale formatting. We do
        #   not know how to handle EU numbers or conversions, and those are
        #   PASSED AS-IS. All "fixes" converting EU to US are stopped.
        #
        # The measurements that produced that directive, over 297 English
        # papers from the custodian (`tools/diag/repair_site_scan.py`):
        #
        #   A3   9 sites / 2 papers, and NOT ONE CORRECT.
        #        8 corrupted mathematical constraints in 10.1515/bpasts-2016-0057
        #          `|S| >= 2,`      ->  `|S| >= 2.2,`
        #        1 laundered an author's error in 10.1371/journal.pone.0285114
        #          `M = 26,21, SD = 28.88`  ->  `M = 26.21, ...`
        #   A3c  1 site / 297 papers, and it was a URL:
        #        10.1177/0146167210380928 p13
        #          `article/0,9171,1848755,00.html` -> `0.9171,...`  (404s)
        #
        # And where a comma decimal IS genuine — 10.1177/0956797620935584
        # Table S2, ~130 cells — the values are bare table cells with no
        # operator, so A3 could never see them anyway. The rules were not
        # merely risky; they were not doing the job they existed for, while
        # reliably damaging text that was correct.
        #
        # STATED CONSEQUENCE, not hidden: a European decimal now reaches the
        # consumer VERBATIM. That is a coverage change, and it is recoverable —
        # the source token is intact, so the consumer can decide for itself,
        # which it could not once we had already converted.
        #
        # Pinned by tests/test_european_numbers_pass_through.py.
        # See docs/SCOPE.md.


        # A3d WAS HERE AND IS DELETED (v2.4.129, 2026-08-14).
        #
        # It converted `p = ,025` -> `p = .025`, the "continental" spelling of an
        # APA leading-zero-free value (ESCImate shared spec rule D1b).
        #
        # Its entire justification was the string `p = ,025`, and that string was
        # never observed in a document. It came from a consumer's spec, was copied
        # into a reply doc, then a handoff, then the CHANGELOG, then
        # `docs/NORMALIZATION.md`, then into this file — acquiring the appearance
        # of consensus at every hop while remaining ONE UNCHECKED STRING. It was
        # recorded as "reproduced against unfixed code", which is true and
        # irrelevant: running a constructed string through the pipeline proves
        # what the CODE does, never that the SHAPE OCCURS.
        #
        # Measured over real English-language articles from the custodian:
        #     0 sites / 0 papers in 297 English papers   (repair_site_scan, 08-14)
        #     0 sites / 0 papers in a prior 600-paper hunt          (08-13)
        #
        # A rule with no observed input is pure false-positive surface for no
        # measured benefit. Deleting it cannot cost a consumer coverage, because
        # it never fired. The divergence from spec rule D1b is deliberate and is
        # reported outbound; if a real article — DOI and page — is ever found
        # printing this shape, the rule comes back with that citation attached.
        #
        # Pinned by tests/test_a3d_deleted_leading_comma_passes_through.py, which
        # asserts the shape passes through AND that no step named A3d is tracked:
        # a rule left in place "disabled" is dead code the next reader re-enables.
        #
        # Directive 2026-08-13: a rule must point at a real paper.
        # Repetition is not verification.

        # A3b: Statistical df-bracket harmonization (MetaESCI D2, 2026-04-11)
        #
        # Some PDFs encode F/t/chi2 degrees-of-freedom with square brackets
        # instead of parentheses — e.g. pdftotext produces "F[2,42]= 13.689"
        # from 10.15626/mp.2019.1723 where the paper visually uses parens.
        # effectcheck's parse.R only matches `F\s*\(`, so these rows are
        # silently dropped. Convert the bracket form to canonical parens
        # when the bracket follows a short stat identifier AND is followed
        # by `=` (the assignment to a numeric value). The `=` lookahead is
        # the load-bearing constraint — it blocks false positives on
        # `ref[1,2]`, `fig[1,2]`, `eq[1,2]` which look structurally
        # identical but are citation/figure/equation references, not stats.
        before = t
        t = re.sub(
            r"(\b[A-Za-z][A-Za-z0-9]{0,3})\[(\s*\d+(?:\.\d+)?\s*,\s*\d+(?:\.\d+)?\s*)\](?=\s*=)",
            r"\1(\2)",
            t,
        )
        report._track("A3b_stat_bracket_to_paren", before, t, "stat_brackets_fixed")

        # A4: CI delimiter harmonization
        before = t
        # A4a: middle-period → comma inside CI-shaped brackets/parens (ESCIcheck
        # 2026-05-24 D2: `[0.25.0.54]` → `[0.25, 0.54]`). Some PDFs render the
        # CI comma glyph as a period (font substitution or pdftotext mapping),
        # which downstream parsers cannot disambiguate from a decimal-continuation
        # and so they drop the CI entirely.
        #
        # v2.4.129 — NOW REQUIRES CONFIDENCE-INTERVAL CONTEXT. The old guard was
        # "each side must be `\d+\.\d+`", justified as blocking a section ref
        # like `[1.2.3]` where the trailing token has no decimal. That is true
        # for THREE components and false for FOUR, which have a decimal on both
        # sides and sail straight through:
        #
        #   10.3389/fpsyg.2023.1214699 (Frontiers, English)
        #     '...regarding the semantic annotation (3.2.2.1)' -> '(3.2, 2.1)'
        #     '...and the quantification (3.2.2.2) of lexemes' -> '(3.2, 2.2)'
        #
        # This is worse than an ordinary corruption: it FABRICATES a statistic
        # that is not in the paper, and `(3.2, 2.1)` has its bounds in DESCENDING
        # order — the shape of a *reversed confidence interval*, which is one of
        # the exact defect classes our consumers are being asked to detect. We
        # would be manufacturing the defect the downstream tool exists to catch.
        # Found by `tools/diag/non_statistic_corpus_scan.py` on its first run.
        #
        # The remedy is POSITIVE rather than another exclusion, because an
        # enumeration of what must not match is never complete — that is this
        # module's entire defect history. The rule is named for the confidence
        # interval; if nothing establishes that the bracket IS one, it does not
        # fire. Where the evidence is absent we pass through, leaving the source
        # intact and both readings recoverable.
        #
        # MEASURED, and recorded so a later pass can go further: over 148
        # English papers from the custodian this arm matched **0 times** in
        # either bracket form (`tools/diag/repair_site_scan.py` companion probe),
        # while its false-positive shape occurred twice in a 60-paper sample. Its
        # original justification cites no DOI. On that evidence it is a DELETE
        # candidate like A3d; it is GUARDED rather than deleted here only because
        # proving the target never occurs needs a wider hunt than this run made.
        # The context that proves it IS an interval, in the two forms real papers
        # actually use. Both come from real sources, neither is invented:
        #
        #   (a) the words        '95% CI (0.25.0.54) overlapped zero'
        #   (b) the ESTIMATE     'd=0.39[0.25.0.54]'   collabra_57785 abstract,
        #                        the shape A4a was originally built for — note it
        #                        carries NO 'CI' text at all, which is why an
        #                        earlier draft of this guard requiring the words
        #                        broke the rule's own evidenced target.
        #
        # (b) requires the preceding token to be a DECIMAL (`\d+\.\d+`), not any
        # digit: an estimate has a decimal point, whereas the prose that precedes
        # a section reference ends in a word ('annotation', 'section', 'see') or
        # a bare integer ('in Experiment 2'). That is what separates
        # `d=0.39[0.25.0.54]` from `the semantic annotation (3.2.2.1)`.
        _A4A_INTERVAL_CONTEXT = re.compile(
            r"(?:\bCI\b|\bC\.I\.|confidence\s+interval)[^\[\(]{0,24}$"
            r"|\d+\.\d+\s*$",
            re.IGNORECASE,
        )

        def _a4a_middle_period(m: "re.Match[str]", open_ch: str, close_ch: str) -> str:
            if not _A4A_INTERVAL_CONTEXT.search(m.string[:m.start()]):
                return m.group(0)
            return f"{open_ch}{m.group(1)}, {m.group(2)}{close_ch}"

        t = re.sub(
            r"\[(\s*[-+]?\d+\.\d+)\s*\.\s*([-+]?\d+\.\d+\s*)\]",
            lambda m: _a4a_middle_period(m, "[", "]"),
            t,
        )
        t = re.sub(
            r"\((\s*[-+]?\d+\.\d+)\s*\.\s*([-+]?\d+\.\d+\s*)\)",
            lambda m: _a4a_middle_period(m, "(", ")"),
            t,
        )
        # Semicolons → commas inside square brackets and parens
        t = re.sub(r"\[(\s*[-+]?\d*\.?\d+)\s*;\s*([-+]?\d*\.?\d+\s*)\]", r"[\1, \2]", t)
        t = re.sub(r"\((\s*[-+]?\d*\.?\d+)\s*;\s*([-+]?\d*\.?\d+\s*)\)", r"(\1, \2)", t)
        # Curly braces → square brackets
        t = re.sub(r"\{\s*([-+]?\d*\.?\d+)\s*[,;]\s*([-+]?\d*\.?\d+)\s*\}", r"[\1, \2]", t)
        # Normalize spacing inside brackets and parens.
        #
        # v2.4.129: at least ONE side must carry a DECIMAL POINT. Without that,
        # this arm asserted "the comma is a separator" on a token where, under
        # the 2026-08-14 scope directive, docpluck has no basis for the claim:
        #
        #     '(0,003)'  ->  '(0, 003)'     a European p-value rendered as a
        #                                   two-element pair — a reading the
        #                                   paper never printed
        #     '[0,05]'   ->  '[0, 05]'
        #
        # Found immediately after A3/A3c were deleted: with the converters gone,
        # `(0,003)` reaches this arm intact and it invents the separator reading
        # that A3c used to invent the decimal reading. **The same defect wearing
        # the other hat**, which is worth stating — removing a rule can expose a
        # sibling that was previously masked by it.
        #
        # A real CI carries decimals on its bounds (`[7.77,31.28]`), so requiring
        # one is a positive signature rather than another exclusion. Spacing is
        # cosmetic; asserting a reading is not, and only the second needs
        # evidence.
        _A4_SPACING_NEEDS_A_DECIMAL = r"(?=[^]\)]*\.\d)"
        t = re.sub(r"\[" + _A4_SPACING_NEEDS_A_DECIMAL +
                   r"\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\]", r"[\1, \2]", t)
        t = re.sub(r"\(" + _A4_SPACING_NEEDS_A_DECIMAL +
                   r"\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)", r"(\1, \2)", t)
        report._track("A4_ci_delimiter_harmonization", before, t, "ci_delimiters_fixed")

        # A5: Math symbol and Greek letter normalization
        # When preserve_math_glyphs=True (render path), this block is SKIPPED
        # so the rendered .md preserves source glyphs (\u03B2, \u03B4, \u03C7\u00B2, \u03B7\u00B2, \u00B2, \u2080, etc.)
        # exactly as printed. Default False preserves backward-compatible
        # behavior for stat-extraction callers (D5 audit, regex matching).
        # See CLAUDE.md ground-truth rule + memory feedback_ground_truth_is_ai_not_pdftotext.
        before = t
        if preserve_math_glyphs:
            # Skip A5 entirely \u2014 preserve source glyphs.
            report._track("A5_skipped_preserve_math_glyphs", before, t, "preserved")
        else:
            # U+00D7 -> `*`, not the letter `x` (contract v2.0). The letter
            # collides with a variable named x: `2 x 3 design` and `x10^9`
            # are indistinguishable from an expression involving x. `*` is
            # unambiguous in the operand position; a significance star is
            # positionally distinct (it TRAILS a value, never sits between
            # two operands).
            t = t.replace("×", "*")     # multiplication sign
            t = t.replace("\u2264", "<=")     # less-than-or-equal
            t = t.replace("\u2265", ">=")     # greater-than-or-equal
            t = t.replace("\u2260", "!=")     # not-equal

            # Greek -> ASCII, from THE canonical table in `docpluck.symbols`.
            #
            # This block used to be a hand-written chain of ten .replace()
            # calls, and `extract.py`'s SMP fallback carried a SECOND,
            # DIFFERENT chain. They disagreed on 9 of 9 shared letters, so the
            # same chi-square left as `chi2` or `ch2` depending purely on
            # which extraction path ran -- and a consumer matching `chi2(`
            # silently never checked the test on one of them. Both paths now
            # read `docpluck.symbols`, which is published to consumers via
            # `symbol_contract()`.
            #
            # Composite forms first: eta + superscript-2 must become `eta2`,
            # and the space variant likewise, before bare letters are mapped.
            t = t.replace("η²", "eta2")
            t = t.replace("χ²", "chi2")
            t = t.replace("ω²", "omega2")
            t = re.sub(r"η\s*2", "eta2", t)
            t = re.sub(r"χ\s*2", "chi2", t)
            t = re.sub(r"ω\s*2", "omega2", t)
            t = t.translate(_GREEK_TRANSLATION)

            # Uppercase Greek VISUALLY IDENTICAL to a Latin capital is mapped
            # ONLY as a standalone token. A broken font encoding emitting
            # Greek Alpha for a Latin A inside a word would otherwise turn
            # `ANOVA` into `AlphaNOVA` -- corrupting prose to fix a symbol.
            # Standalone, the codepoint is the only evidence there is, and it
            # says Greek: an author who meant `A` would have typed `A`.
            t = _GREEK_AMBIGUOUS_UPPER_RE.sub(
                lambda m: GREEK_UPPER_AMBIGUOUS_TO_ASCII[m.group(0)], t
            )

            # EXPONENT GUARD, before any superscript is flattened: a run that
            # directly follows an ASCII digit is an exponent, not a symbol
            # suffix, and flattening would FUSE it into the mantissa
            # (`×10⁹/L` -> `x109/L`). Caret notation instead — see
            # _SUPERSCRIPT_EXPONENT_RE for the full argument. Must run BEFORE
            # the per-character replaces below, which destroy the distinction.
            t = _SUPERSCRIPT_EXPONENT_RE.sub(_superscript_run_to_caret, t)

            # Superscript digits → regular digits (² → 2, ³ → 3, etc.)
            t = t.replace("\u00B2", "2")   # ²
            t = t.replace("\u00B3", "3")   # ³
            t = t.replace("\u00B9", "1")   # ¹
            t = t.replace("\u2070", "0")   # ⁰
            t = t.replace("\u2074", "4")   # ⁴
            t = t.replace("\u2075", "5")   # ⁵
            t = t.replace("\u2076", "6")   # ⁶
            t = t.replace("\u2077", "7")   # ⁷
            t = t.replace("\u2078", "8")   # ⁸
            t = t.replace("\u2079", "9")   # ⁹

            # SUBSCRIPTS -> `_` + ASCII, as a RUN (contract v2.0).
            #
            # Contract v1.0 fused a subscript into the token before it, which
            # produced tokens that read as something else entirely:
            #
            #     eta-squared-partial  ->  'eta2p'   the p collides with p-value
            #     M-sub-p              ->  'Mp'      or a variable named Mp?
            #     M-sub-beta           ->  'Mbeta'   reads as one word
            #
            # `_` is the universal plain-text subscript convention and makes the
            # boundary explicit, so a real variable named `Mp` stays distinct
            # from M-sub-p. It applies as ONE rule to every subscript rather
            # than a per-symbol special case, and effectcheck's own alternation
            # already carries underscore forms (`eta_p2`, `eta_p^2`), so the
            # shape is one consumers expect.
            #
            # RUN-based, so `BF01` takes a single underscore (`BF_01`) rather
            # than one per character. The underscore is only inserted when the
            # run actually follows a word character — a subscript with nothing
            # to attach to is just transliterated.
            t = _SUBSCRIPT_RUN_RE.sub(_subscript_run_to_ascii, t)

            report._track("A5_math_symbol_normalization", before, t, "math_symbols_normalized")

        # A6: Footnote marker removal after a CLOSING BRACKET only.
        #
        #     "95% CI [0.1, 0.5]²" -> "95% CI [0.1, 0.5]"   a footnote marker
        #     "the value 10⁹"      -> UNCHANGED             an EXPONENT
        #
        # -- THE DEFECT THIS FIXES (v2.4.133), and why it survived --
        #
        # The left context used to be `[\d\]\)]`, under the comment "A5 already
        # converted ² -> 2, so we look for isolated digits after ] ) or stat
        # values." THAT PREMISE IS FALSE WHENEVER `preserve_math_glyphs=True`,
        # because A5 is SKIPPED in that mode -- the step trace literally records
        # `A5_skipped_preserve_math_glyphs`. A6 then met the raw superscript
        # codepoints A5 would have turned into carets and DELETED them, on the
        # one path whose whole contract is not to touch glyphs:
        #
        #     normalize_text("the value 10⁹", academic, preserve_math_glyphs=True)
        #         -> "the value 10"        A BILLION-FOLD ERROR
        #     normalize_text("N = 42³",      academic, preserve_math_glyphs=True)
        #         -> "N = 42"
        #
        # ...and it was booked as `footnotes_removed: 1`, so the telemetry
        # asserted a footnote had been stripped while a published exponent was
        # destroyed. This is the exact loss `W0p`'s own docstring warns about --
        # "deleting the wrong one loses nine orders of magnitude" -- committed by
        # a different step in the same file. Note the inversion: a REAL footnote
        # marker after a word ("Smith et al.¹") never matched at all, so the
        # rule spared the case it was written for and deleted the case it was
        # warned about.
        #
        # -- WHY THE LEFT CONTEXT IS NOW BRACKETS ONLY --
        #
        # After a DIGIT, a superscript digit is ambiguous between an exponent
        # and a footnote marker, and the codepoint alone cannot separate them --
        # which is precisely why `W0p` exists and reads font size and baseline.
        # A6 has no typographic evidence at all, so under "if you cannot point
        # at something the renderer emitted, pass through" it must not decide.
        # After `]` or `)` the ambiguity is gone: nothing exponentiates a closing
        # bracket, so the slot is grammatically impossible for an exponent --
        # the one form of evidence this rule can legitimately claim.
        #
        # Cost: `p < .001¹` keeps its marker, a visible and recoverable
        # cosmetic residue. `10⁹ -> 10` is an unrecoverable error in a published
        # number. Not a close call. Nothing is lost on the
        # `preserve_math_glyphs=False` path, where A5 has already rewritten every
        # superscript to caret form before A6 runs.
        before = t
        t = re.sub(
            r"([\]\)])[\u00B9\u00B2\u00B3\u2070\u2074-\u2079\u2080-\u2089](?=\s|[,;.\)]|$)",
            r"\1", t
        )
        report._track("A6_footnote_removal", before, t, "footnotes_removed")

        # ── A7: DOI cross-line repair (Request 9, document-wide) ─────────
        # pdftotext sometimes wraps long DOIs across a line, e.g.
        # "(doi:10.\n1007/s10683-020-09663-x)". Rejoin them. The `doi:` prefix
        # in the lookbehind chain is load-bearing — without it the rule
        # would damage decimals at line ends in normal prose.
        before = t
        t = re.sub(r"(doi:\s*\S*?\d)\.\s*\n\s*(\d)", r"\1.\2", t, flags=re.IGNORECASE)
        report._track("A7_doi_rejoin", before, t, "doi_rejoined")

        # ── R2 + R3: References-section repairs (Request 9) ──────────────
        # R2 scrubs page-number digits glued mid-reference (silent corruption
        # of titles). R3 joins continuation lines so each reference is on a
        # single logical line. Bounded to detected references spans; iterate
        # right-to-left so prior span offsets remain valid after edits.
        _refs_spans = _find_references_spans(t)
        r2_count_total = 0
        r3_joins_total = 0
        for r_start, r_end in reversed(_refs_spans):
            refs_text = t[r_start:r_end]

            # R3 page-break stitch (D2, citationguard-iterate 2026-06-12): inside
            # a bibliography a form-feed (page break) NEVER coincides with a
            # paragraph boundary — entries are delimited by ref-starts, not blank
            # lines. When an entry straddles a page break, pdftotext emits
            # "…based on\n\n\x0cArticle\nhistology…(2008)." — the blank line +
            # form feed split the entry, so R3's normal continuation join (which
            # resets on a blank line) leaves the tail (and its year) detached,
            # orphaning nat_comms_2 ref 34's "(2008)". Collapse each form-feed
            # junction (and the blank line(s) around it) to a single newline so
            # the tail rejoins the head as an ordinary continuation. The running-
            # header label on the new page ("Article") is stripped upstream by
            # P0r (_CATEGORY_LABEL_HEADER); any that survives is handled by the
            # continuation join, but the year is recovered regardless.
            refs_text = re.sub(r"[ \t]*\n[ \t\n]*\f[ \t]*", "\n", refs_text)
            refs_text = refs_text.replace("\f", "\n")

            # R3 pre-pass (Cycle 15 v2.4.67): two-column bibliography
            # pairing. pdftotext renders some 2-column bibliographies by
            # streaming the entire NUMBER column first, then the entire
            # ENTRY column. The result looks like
            #     References
            #     1.
            #     2.
            #     ...
            #     16.
            #
            #     Thaler RH. 1999 ...
            #     Zhang CY, Sussman AB. 2018 ...
            #     ...
            # R3's continuation-join would smash `1.\n2.\n3.\n...` into one
            # line and detach the entries entirely (Li&Feldman 2025 RSOS).
            # Detect a leading run of bare `\d+\.` lines that form a
            # sequential 1..N or 1..N-with-gaps sequence followed by the
            # same number of entry-shaped lines, and pair them up before
            # the continuation pass runs.
            refs_text = _pair_two_column_bibliography(refs_text)

            # R3 first: continuation join must run before R2 because R2's
            # lowercase-surround guard relies on the page-number being
            # surrounded by content from the SAME logical line.
            before_r3 = refs_text
            lines = refs_text.split("\n")
            joined: list[str] = []
            # Index in ``joined`` of the entry currently being built. Unlike the
            # previous ``joined[-1]`` check, this survives blank lines: within a
            # bibliography a blank line is a page-break artifact (entries are
            # single-newline separated), so a continuation line that follows a
            # blank still belongs to the entry above it. This rejoins entries
            # split across a page break — e.g. nat_comms_2 ref 34, whose
            # "(2008)" year sat past the page-break blank after the running
            # header was stripped (D2). Entry boundaries are still established
            # solely by _looks_like_ref_start, so genuinely separate entries do
            # not merge.
            cur_entry = -1
            saw_blank = False
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    joined.append("")
                    saw_blank = True
                    continue
                is_start = _looks_like_ref_start(stripped)
                bridged = False
                if cur_entry >= 0 and not is_start:
                    if saw_blank:
                        # Crossing a blank line: only bridge when the current
                        # entry is syntactically INCOMPLETE (does not end with
                        # sentence-terminal punctuation). A page-break split
                        # leaves the head mid-clause ("…EAE based on"), so the
                        # tail rejoins; a COMPLETED entry ("…46, 215-39.")
                        # followed by a blank is the end of the list, and the
                        # next block ("Cite this article: …") is post-reference
                        # trailer that must NOT be absorbed.
                        prev = joined[cur_entry].rstrip()
                        if prev and prev[-1] not in ".?!":
                            joined[cur_entry] = prev + " " + stripped
                            bridged = True
                    else:
                        joined[cur_entry] = (
                            joined[cur_entry].rstrip() + " " + stripped
                        )
                        bridged = True
                if not bridged:
                    joined.append(stripped)
                    cur_entry = len(joined) - 1
                saw_blank = False
            refs_text = "\n".join(joined)
            r3_joins_total += before_r3.count("\n") - refs_text.count("\n")

            # R2: scrub orphan page-number digits that appear surrounded by
            # lowercase letters (so we don't touch volume numbers, page
            # ranges with hyphens, or year boundaries).
            #
            # v2.4.17 (NORMALIZATION_VERSION 1.8.5): body-noun exception
            # list. Some PDFs (e.g. amle_1) have many standalone-digit lines
            # that are table cell values, NOT page numbers — those falsely
            # contaminate ``_raw_page_numbers``. Guard against false-positive
            # strips on legitimate body phrases like "first 20 years",
            # "1,675 participants", "3,000 hours" by checking the 30-char
            # window after the matched digit for a body-noun keyword
            # (years/days/participants/etc.). If a body noun follows, the
            # digit is part of prose — leave it alone. See
            # ``_R2_BODY_NOUN_PATTERN`` and ``_r2_is_body_phrase``.
            for pg in _raw_page_numbers:
                pat = re.compile(r"(?<=[a-z])(\s+)" + re.escape(str(pg)) + r"(\s+)(?=[a-z])")
                # Use a sub-callable so we can inspect each match individually
                # and skip body-phrase contexts (see ``_r2_is_body_phrase`` —
                # v2.4.17 guard against false-positive strips on legitimate
                # body phrases like "first 20 years"). Track strip count
                # explicitly because ``subn`` counts both preserved and
                # stripped matches.
                pg_str = str(pg)
                _r2_strip_count = [0]
                _captured_refs = refs_text  # closure: read original text
                def _r2_repl(m, _pg=pg_str, _refs=_captured_refs, _c=_r2_strip_count):
                    if _r2_is_body_phrase(_pg, _refs, m.start() + len(m.group(1))):
                        return m.group(0)  # preserve — body phrase
                    _c[0] += 1
                    return " "
                refs_text = pat.sub(_r2_repl, refs_text)
                r2_count_total += _r2_strip_count[0]

            t = t[:r_start] + refs_text + t[r_end:]

        report.steps_applied.append("R2_inline_pgnum_scrub")
        if r2_count_total > 0:
            report.changes_made["inline_pgnum_scrubbed"] = r2_count_total
            report.steps_changed.append("R2_inline_pgnum_scrub")

        report.steps_applied.append("R3_continuation_join")
        if r3_joins_total > 0:
            report.changes_made["ref_continuations_joined"] = r3_joins_total
            report.steps_changed.append("R3_continuation_join")

    # ── Late line-join re-application on stabilized line positions ──────
    # S9 strips repeated header/footer lines via ``"\n".join`` over a filtered
    # list — when an intermediate line is dropped, the two surrounding lines
    # become adjacent with a single `\n` between them. If those neighbours are
    # body prose, stats, or hyphenated word parts, the join produces a fresh
    # line-break boundary that S7/S8/A1 already ran past. R2/R3 reference
    # continuation joins can also shift line positions late. Same idempotency
    # pattern as H0r: re-apply the line-join patterns now, on the stabilized
    # line positions, so a second normalize pass finds nothing to do.
    # (run 9 cycle 8 — JOIN bucket.)
    before = t
    # S7r: hyphenation
    t = re.sub(r"([a-z])-\n(?=[a-z])", r"\1", t)
    # S8r: general prose line-break (Greek-aware as in S8)
    t = re.sub(r"([a-z,;])\n(?=[a-zα-ω])", r"\1 ", t)
    if level == NormalizationLevel.academic:
        # A1r: re-apply the stat line-break patterns (same as the A1 block
        # above, in lookahead form so a chained run converges in one pass).
        # The whitespace-around-newline class is `[ \t]*` (horizontal only),
        # NOT `\s*` — `\s*` would match `\n` too and so cross a `\n\n`
        # paragraph break. After S9 strips column-bleed fragments (e.g. the
        # `01\n02\n03\n04\n05` between `p` and `= .05`), the residue is
        # `p\n\n= .05`, a paragraph break — the test_column_bleed
        # _too_many_fragments_ignored contract requires that be LEFT alone.
        # Single-line-removal by S9 / R3 leaves a *single* `\n` between
        # neighbours (`"\n".join` of a filtered list), which is exactly what
        # the strict `[ \t]*\n[ \t]*` boundary matches and joins.
        t = re.sub(r"([pP])[ \t]*\n[ \t]*(?=[=<>])", r"\1 ", t)
        t = re.sub(r"([pP]\s*[=<>])[ \t]*\n[ \t]*(?=\d)", r"\1 ", t)
        t = re.sub(r"(OR|CI|RR)[ \t]*\n[ \t]*(?=\d)", r"\1 ", t)
        t = re.sub(r"(95\s*%)[ \t]*\n[ \t]*(?=CI)", r"\1 ", t)
        t = re.sub(r"([=<>])[ \t]*\n[ \t]*(?=[-\d.])", r"\1 ", t)
        t = re.sub(r"([,;])[ \t]*\n[ \t]*(?=p\s*[<=>])", r"\1 ", t)
        t = re.sub(r"([,;])[ \t]*\n[ \t]*(?=\d+%\s*CI)", r"\1 ", t)
        # Cycle 12 (v2.4.64) — cross-paragraph stat-continuation join.
        # A1 (which uses `\s*` and so crosses paragraph breaks) runs BEFORE
        # S9 strips header/footer lines. So a stat row like
        #   `r(1798) = -0.27,\n\n472\n\nJournal of Decision Making, ...\n\n95% CI [-0.31, ...]`
        # has so much intervening junk that A1's lookahead fails on pass 1;
        # only after S9 strips the junk (producing `,\n\n95% CI`) can the
        # join happen, and that's pass 2. The two patterns below are the
        # paragraph-crossing variants of the comma-to-stat-continuation
        # patterns above — restricted to the high-confidence prefixes
        # `\d+% CI` and `p [<=>]` because no real paragraph STARTS with
        # those tokens (test_column_bleed_too_many_fragments_ignored is
        # unaffected — its input has no leading `,`/`;`).
        # Clears korbmacher (2 papers) from the non-idempotent set.
        t = re.sub(r"([,;])\s*\n\s*\n\s*(?=\d+%\s*CI)", r"\1 ", t)
        t = re.sub(r"([,;])\s*\n\s*\n\s*(?=p\s*[<=>])", r"\1 ", t)
        # Cycle 13 (v2.4.65) — same shape, applied to `=/<>` → digit/dot
        # continuations. li-feldman-fox has `p =\n\n\x0cFox et al. (2005)...
        # \n\n38\n\n.25, OR = .96, 95%CI [.90, 1.03])` where A1's
        # `([=<>])\s*\n\s*([-\d.])` pattern fails on pass 1 (the journal-
        # header text isn't `\s`); S9 strips the header + page number,
        # leaving `p =\n\n.25` — but A1 is over. Pass 2 joins on the
        # cleaned form. The lookahead `(?=[-\d.])` is the load-bearing
        # constraint — real paragraphs rarely START with a leading dot
        # or `-digit`.
        t = re.sub(r"([=<>])\s*\n\s*\n\s*(?=[-.]?\d)", r"\1 ", t)
        # Cycle 15 (v2.4.67) — cross-paragraph variant of the
        # (OR|CI|RR) → digit A1r join. Same JOIN-after-STRIP pattern as
        # cycles 12/13: A1 (single-newline form) runs BEFORE S9 strips
        # column headers / footer noise between the stat label and its
        # value, so a `Mortality Hazard Ratio\n\n95% CI\n\n2.046***`
        # block fails to join in pass 1; S9 then strips the intervening
        # boilerplate, leaving `CI\n\n2.046***`, which A1 has already
        # missed. Pass 2's A1 catches it — that is the non-idempotence.
        # Clears demography-5 (Hazard-Ratio + Odds-Ratio tables) and any
        # sibling paper whose CI/OR/RR/HR cell sits one paragraph above
        # its numeric value. The `(?=\d)` lookahead is the load-bearing
        # constraint — real paragraphs rarely START with a digit.
        # The lookahead requires a STATISTICAL-VALUE-shaped token (decimal
        # `\d+\.\d`, multi-digit `\d{2,}`, or digit followed by operator/
        # delimiter `\d[-*<>=,]`) — NOT a bare `\d+\.\s+[A-Z]` which is a
        # bibliography-reference-number signature (`2. Thaler RH. 1999 ...`).
        # Excluding the bibliography form prevents this join from collapsing
        # the references-section reference numbers onto a header line when
        # an earlier line ends with `CI`/`OR`/`RR`/`HR` (e.g. Cochran et al.
        # in-text mentions of CIs preceding the bibliography start).
        t = re.sub(
            r"(OR|CI|RR|HR)\s*\n\s*\n\s*(?=\d+(?:\.\d|\d|[-*<>=,]))",
            r"\1 ",
            t,
        )
    report._track("LateJoin_line_break_rejoin", before, t, "late_line_joins")

    # ── H0r: header-banner re-strip on stabilized line positions ─────────
    # The early H0 (top of the pipeline) scans only the first 30 lines of
    # RAW pdftotext output. Un-cleaned front-matter noise can push a real
    # banner line (e.g. a bare publisher/DOI URL) past that 30-line cap, so
    # H0 misses it on the first pass. P0/P1/S9/A1/A7/R3 then strip that
    # noise and shift lines up — the banner lands inside the header zone
    # only AFTER the pipeline has run. Re-running H0 here, to a fixed point
    # on the final line positions, makes normalize_text idempotent: a second
    # normalize pass finds the header already clean. (run 9 cycle 7 — fixes
    # the test_normalization_idempotent regression.)
    before = t
    while True:
        _restripped = _strip_document_header_banners(t)
        if _restripped == t:
            break
        t = _restripped
    report._track("H0r_header_banner_restrip", before, t, "header_banners_restripped")

    # ── Final blank-line collapse ────────────────────────────────────────
    # S9 enforces `re.sub(r"\n{3,}", "\n\n", t)` once near the top of the
    # pipeline. Later steps that REMOVE non-blank content can leave blank
    # gaps that S9's earlier collapse no longer reaches:
    #
    #   - R3 (refs-section continuation join) walks the refs span line by
    #     line. A bare form-feed `\x0c` (pdftotext page-break) between two
    #     blank lines becomes `"".strip() == ""` and is preserved as a blank
    #     entry; R3 outputs three consecutive blank entries surrounded by
    #     `"\n".join(...)` — `\n\n\n\n`. Pass 1 leaves this; pass 2's S9
    #     collapses it, producing the bibliography-shift non-idempotence
    #     (cycle 12 — 5 papers: chan-etal, horsham, lee-feldman,
    #     li-feldman-mental, + 1 incidental).
    #   - Same pattern for any late strip step that empties a line without
    #     re-collapsing.
    #
    # Add the collapse here so the function is idempotent regardless of
    # which late step produced the blank-line run.
    t = re.sub(r"\n{3,}", "\n\n", t)

    # ── P1r: front-matter metadata-leak re-strip on stabilized lines ─────
    # Same shape as H0r and P0r. P1's `_strip_frontmatter_metadata_leaks`
    # matches an acknowledgment-style line by ANCHORED prefix + a keyword
    # check within the first 300 chars (e.g. `^We\s+thank...reviewers|
    # editor|feedback|comments|suggestions|insights|helpful`). pdftotext
    # often line-wraps the acknowledgment before the keyword fires (e.g.
    # `We thank the target article's authors - Prof. Craig Fox and Prof.
    # Rebecca Ratner, for being very` — the raw line stops before
    # `helpful`). S7/S8 join the continuation; the joined line now contains
    # the keyword, but P1 has already run by then. Pass 2's P1 catches the
    # joined form and strips — non-idempotence + a missed production strip.
    #
    # Re-running here on the post-LateJoin line positions catches every
    # form (the original short line where the keyword was already in
    # window, AND the post-join long line where it's only in window after
    # the join).
    #
    # Cycle 13 (v2.4.65) — clears li-feldman-fox + amp-1 + annals-2 +
    # xiao-poc-epley (4 acknowledgment-block papers) from the
    # non-idempotent set.
    before = t
    while True:
        _restripped = _strip_frontmatter_metadata_leaks(t)
        if _restripped == t:
            break
        t = _restripped
    report._track("P1r_frontmatter_leak_restrip", before, t, "frontmatter_leaks_restripped")

    # ── P0r: page-footer-line re-strip on stabilized line positions ──────
    # Same shape as H0r, applied to P0's anchored ^...$ patterns. P0 runs
    # near the top of the pipeline, where some P0-targeted lines are still
    # SPLIT across two pdftotext rows (e.g. JAMA's
    # `Author affiliations and article information are\nlisted at the end
    # of this article.` — the `^...$` anchors fail because the line is two
    # rows). S7/S8 + the LateJoin block above merge the rows into a single
    # line, but P0 has already run by then. P0r re-applies P0 on the joined
    # line positions and catches the now-single-line forms.
    #
    # Idempotent by construction: _strip_page_footer_lines is a no-op when
    # no pattern matches, so the fixed-point loop converges in 1-2 passes.
    # (run 9 cycle 9 — clears the 10 JAMA `jama_open_*` papers from the
    # 40-paper non-idempotent set; same H0r-pattern generalized.)
    before = t
    while True:
        _restripped = _strip_page_footer_lines(t)
        if _restripped == t:
            break
        t = _restripped
    report._track("P0r_page_footer_restrip", before, t, "page_footer_lines_restripped")

    # ── G5c-2: rejoin pdftotext-split numbered section headings ─────────
    # B5 (2026-05-22): ``N.N.\n\n<CanonicalKeyword>`` is a single split
    # heading the partitioner would otherwise consume as two artefacts
    # (the orphan number is dropped, the keyword line is promoted, the
    # numeric prefix is lost). Runs LAST in academic — after every other
    # rejoin has settled — so the lookup_canonical_label gate is judged
    # against fully-normalized text. Gated on canonical-label resolution
    # so prose words can never trigger.
    before = t
    t = _rejoin_split_numbered_headings(t)
    report._track(
        "G5c2_split_numbered_heading_rejoin",
        before,
        t,
        "split_numbered_headings_rejoined",
    )

    # ── Final NFC composition (Cycle 15 v2.4.67) ─────────────────────────
    # The early NFC at the top of normalize composes only the decomposed
    # forms present in raw pdftotext (NFD authors like `Förster`). Later
    # A5 Greek-letter transliteration (`σ` → `sigma`) can SHIFT an
    # immediately-following combining mark from its Greek base onto the
    # last ASCII letter of the transliteration — `σ̂` becomes `sigma` +
    # U+0302 (combining circumflex), which now combines with the trailing
    # `a` of `sigma` and DOES have a precomposed form (`â`, U+00E2). NFC
    # leaves it alone on pass 1 (composition is byte-by-byte and the
    # combining mark wasn't there at NFC time); pass 2 sees the shifted
    # mark and composes it → non-idempotence (ieee-access-7 `sigmâ` math
    # block). NFC is idempotent by definition, so a final pass here is a
    # safe fixed-point. Generally protective against any future transliteration step that leaves an orphan combining mark on an ASCII tail.
    t = unicodedata.normalize("NFC", t)

    # §A R4 / B6 (NORMALIZATION_VERSION 1.9.23, 2026-05-23): detect pages
    # where pdftotext's two-column reading-order serialisation appears to
    # have interleaved between columns. Surface as a signal in the report
    # (no text rewrite this cycle — the column-aware re-extraction is the
    # follow-up architectural work flagged in the
    # 2026-05-23-residual handoff §A R4 / CLAUDE.md "study pdfplumber's
    # column algorithm and re-implement as a conditional fallback").
    try:
        if report.page_offsets and len(report.page_offsets) >= 1:
            report.column_interleave_pages = _detect_column_interleave_pages(
                t, report.page_offsets
            )
    except Exception:
        # Detector is signal-only; never block the pipeline if it fails.
        report.column_interleave_pages = ()

    return t.strip(), report


# §A R4 / B6 column-interleave detection. Structural signature: within a
# single page's body text, a "topic-flip" rate that exceeds a calibration
# threshold — i.e. consecutive sentences whose subject domains alternate in
# a way that cannot occur in coherent prose. Operationally cheap proxy:
# count line-pairs where a line ends mid-sentence (no terminator) and the
# next line starts with a Title-Case word AND the gap is short enough that
# pdftotext would emit them together if columns flowed correctly. A
# legitimately wrapped two-column page has ≤2 such pairs; an interleaved
# page typically shows ≥6.

_INTERLEAVE_FLIP_THRESHOLD = 6
_NO_TERMINATOR_RE = re.compile(r"[^.?!:;\"'\)\]\}]\s*$")
_TITLE_CASE_START_RE = re.compile(r"^[A-Z][a-z]+\b")


def _detect_column_interleave_pages(
    text: str, page_offsets: tuple[int, ...]
) -> tuple[int, ...]:
    """Identify 1-indexed pages whose body text exhibits a column-interleave
    structural signature.

    Two complementary signatures (a page is flagged if EITHER fires):

    **Signature A — sentence-flip count.** A `flip` is a line that ends
    WITHOUT a sentence terminator AND whose next non-blank body line starts
    with a Title-Case word. In coherent prose, sentence-wraps end either
    with a hyphen / continuation word OR are followed by a lowercase word;
    column-interleaved pages show ≥6 such flips per page.

    **Signature B — short-line density (v2.4.76, jama-open-1 D4 closure).**
    Column-interleaved pages also exhibit unusually short average line
    lengths because the columns get serialised line-by-line. A substantial-
    content page (≥40 non-blank lines) whose average non-blank line length
    is ≤45 characters is almost certainly column-fragmented — real prose
    on a single-column page averages 70-100+ chars per line. JAMA Open's
    abstract page exhibits this without firing Signature A (the structured-
    abstract labels and Key Points sidebar both produce period-terminated
    sentences that escape the no-terminator+Title-Case flip test).

    Returns a tuple of 1-indexed page numbers exceeding either threshold.
    Empty tuple when no detection is possible.
    """
    if not text or not page_offsets or len(page_offsets) < 1:
        return ()
    offsets = list(page_offsets) + [len(text)]
    flipped: list[int] = []
    for p_idx in range(len(page_offsets)):
        start = offsets[p_idx]
        end = offsets[p_idx + 1]
        page_text = text[start:end]
        if not page_text.strip():
            continue
        lines = page_text.split("\n")
        flips = 0
        for k in range(len(lines) - 1):
            cur = lines[k].rstrip()
            nxt = lines[k + 1].lstrip()
            if not cur or not nxt:
                continue
            # Skip lines that look like headings / tables / list markers /
            # markdown fences — these legitimately reset case.
            if cur.startswith(("#", "*", "<", ">", "|", "`", "-", "+")):
                continue
            if nxt.startswith(("#", "*", "<", ">", "|", "`", "-", "+")):
                continue
            if not _NO_TERMINATOR_RE.search(cur):
                continue
            if not _TITLE_CASE_START_RE.match(nxt):
                continue
            # Skip continuation-word tails (those are legitimate soft-wrap
            # and don't indicate column-interleave).
            last_word_m = re.search(r"(\b[A-Za-z]+)\s*$", cur)
            if last_word_m:
                lw = last_word_m.group(1).lower()
                # A small set of continuation words that legitimately precede
                # Title-Case proper nouns (citations, equation names, …).
                if lw in {
                    "the", "of", "in", "to", "for", "with", "on", "at",
                    "by", "from", "as", "and", "or", "via", "than", "into",
                }:
                    continue
            flips += 1
        if flips >= _INTERLEAVE_FLIP_THRESHOLD:
            flipped.append(p_idx + 1)
            continue
        # Signature B: bimodal-line-length distribution (v2.4.76, jama-open-1
        # D4). A page with a substantial body (≥30 non-blank, non-markup
        # lines) where ≥30% of lines are SHORT (<40 chars) AND ≥30% are
        # LONG (>70 chars) is structurally bimodal — the canonical fingerprint
        # of column-interleaved text where the narrower sidebar column
        # produces short fragments and the main column produces long lines.
        # Coherent single-column prose has a unimodal distribution (mostly
        # long lines, <20% short).
        body_lines = [
            ln.rstrip() for ln in lines
            if ln.strip() and not ln.lstrip().startswith(("#", "*", ">", "|", "`", "<"))
        ]
        if len(body_lines) >= 30:
            short_count = sum(1 for ln in body_lines if len(ln) < 40)
            long_count = sum(1 for ln in body_lines if len(ln) > 70)
            short_frac = short_count / len(body_lines)
            long_frac = long_count / len(body_lines)
            if short_frac >= 0.30 and long_frac >= 0.30:
                flipped.append(p_idx + 1)
    return tuple(flipped)
