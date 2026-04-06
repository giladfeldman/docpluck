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
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NormalizationLevel(str, Enum):
    none = "none"
    standard = "standard"
    academic = "academic"


NORMALIZATION_VERSION = "1.1.0"


@dataclass
class NormalizationReport:
    level: str
    version: str = NORMALIZATION_VERSION
    steps_applied: list[str] = field(default_factory=list)
    changes_made: dict[str, int] = field(default_factory=dict)

    def _track(self, step_code: str, before: str, after: str, metric_name: str):
        self.steps_applied.append(step_code)
        diff = len(before) - len(after)
        if diff != 0:
            self.changes_made[metric_name] = abs(diff)

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "version": self.version,
            "steps_applied": self.steps_applied,
            "changes_made": self.changes_made,
        }


def normalize_text(text: str, level: NormalizationLevel) -> tuple[str, NormalizationReport]:
    """Apply normalization pipeline at the specified level."""
    if level == NormalizationLevel.none:
        return text, NormalizationReport(level="none")

    report = NormalizationReport(level=level.value)
    t = text

    # ── Standard steps (S1-S9) ──────────────────────────────────────────

    # S0: SMP Mathematical Italic -> ASCII
    before = t
    # Math italic capitals A-Z: U+1D434 - U+1D44D
    for i, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        t = t.replace(chr(0x1D434 + i), letter)
    # Math italic small a-z: U+1D44E - U+1D467
    for i, letter in enumerate("abcdefghijklmnopqrstuvwxyz"):
        t = t.replace(chr(0x1D44E + i), letter)
    # Math italic Greek
    _greek = {
        0x1D6E2: "A", 0x1D6E4: "G", 0x1D6E5: "D", 0x1D6F4: "S",
        0x1D6F7: "Ph", 0x1D6F8: "Ch", 0x1D6F9: "Ps", 0x1D6FA: "O",
        0x1D6FC: "a", 0x1D6FD: "b", 0x1D6FE: "g", 0x1D6FF: "d",
        0x1D700: "e", 0x1D701: "z", 0x1D702: "n", 0x1D703: "th",
        0x1D707: "m", 0x1D70B: "pi", 0x1D70C: "r", 0x1D70E: "s",
        0x1D711: "ph", 0x1D712: "ch", 0x1D713: "ps",
    }
    for cp, repl in _greek.items():
        t = t.replace(chr(cp), repl)
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

    # S3: Ligature expansion
    before = t
    t = t.replace("\ufb00", "ff")
    t = t.replace("\ufb01", "fi")
    t = t.replace("\ufb02", "fl")
    t = t.replace("\ufb03", "ffi")
    t = t.replace("\ufb04", "ffl")
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

    # S6: Whitespace and invisible character normalization
    before = t
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

    # S7: Hyphenation repair
    before = t
    t = re.sub(r"([a-z])-\n([a-z])", r"\1\2", t)
    report._track("S7_hyphenation_repair", before, t, "hyphenations_repaired")

    # S8: Mid-sentence line break joining
    before = t
    t = re.sub(r"([a-z,;])\n([a-z])", r"\1 \2", t)
    report._track("S8_line_break_joining", before, t, "line_breaks_joined")

    # For academic level: join stat line breaks BEFORE stripping page numbers,
    # because standalone numbers like "484" on their own line might be stat values
    # that got split from "p =\n484". S9 would strip them as page numbers.
    if level == NormalizationLevel.academic:
        before = t
        t = re.sub(r"([pP])\s*\n\s*([=<>])", r"\1 \2", t)   # p\n< → p <
        t = re.sub(r"([pP]\s*[=<>])\s*\n\s*(\d)", r"\1 \2", t)
        t = re.sub(r"(OR|CI|RR)\s*\n\s*(\d)", r"\1 \2", t)
        t = re.sub(r"(95\s*%)\s*\n\s*(CI)", r"\1 \2", t)
        t = re.sub(r"([=<>])\s*\n\s*([-\d.])", r"\1 \2", t)
        report._track("A1_stat_linebreak_repair", before, t, "stats_repaired")

    # S9: Header/footer removal
    before = t
    lines = t.split("\n")
    line_counts: dict[str, int] = {}
    for line in lines:
        stripped = line.strip()
        if 15 <= len(stripped) <= 120:
            line_counts[stripped] = line_counts.get(stripped, 0) + 1
    repeated = {line for line, count in line_counts.items() if count >= 5}
    if repeated:
        lines = [l for l in lines if l.strip() not in repeated]
        t = "\n".join(lines)
    # Strip standalone page numbers
    t = re.sub(r"^\s*\d{1,3}\s*$", "", t, flags=re.MULTILINE)
    report._track("S9_header_footer_removal", before, t, "headers_removed")

    # Limit consecutive newlines
    t = re.sub(r"\n{3,}", "\n\n", t)

    # ── Academic steps (A2-A5) ─────────────────────────────────────────
    # Note: A1 already ran above (before S9) to prevent number stripping

    if level == NormalizationLevel.academic:

        # A2: Dropped decimal repair (p > 1.0 -> p = 0.xxx)
        before = t

        def _fix_dropped_decimal(m):
            val = float(m.group(2))
            if val > 1.0 and val < 1000:
                return f"{m.group(1)}.{m.group(2)}"
            return m.group(0)

        # Fix p-values and effect sizes with dropped leading "0."
        t = re.sub(r"([pP]\s*[=]\s*)(\d{2,3})(?=\s|[,;)\]]|$)", _fix_dropped_decimal, t)
        t = re.sub(r"(\b[dDgG]\s*[=]\s*)(\d{2,3})(?=\s|[,;)\.]|$)", _fix_dropped_decimal, t)
        report._track("A2_dropped_decimal_repair", before, t, "decimals_fixed")

        # A3: Decimal comma normalization (European locale)
        before = t
        t = re.sub(r"(\d),(\d{1,3})(?=\s|[;)\]]|$)", r"\1.\2", t)
        report._track("A3_decimal_comma_normalization", before, t, "decimal_commas_fixed")

        # A4: CI delimiter harmonization
        before = t
        t = re.sub(r"\[(\s*[-\d.]+)\s*;\s*([-\d.]+\s*)\]", r"[\1, \2]", t)
        report._track("A4_ci_delimiter_harmonization", before, t, "ci_delimiters_fixed")

        # A5: Math symbol and Greek letter normalization
        before = t
        t = t.replace("\u00D7", "x")     # multiplication sign
        t = t.replace("\u2264", "<=")     # less-than-or-equal
        t = t.replace("\u2265", ">=")     # greater-than-or-equal
        t = t.replace("\u2260", "!=")     # not-equal

        # Greek statistical letters → ASCII (for downstream regex matching)
        # Order matters: multi-char sequences before single chars
        t = t.replace("\u03B7\u00B2", "eta2")    # η² → eta2
        t = t.replace("\u03B7\u00B2", "eta2")    # η² variant
        t = t.replace("\u03C7\u00B2", "chi2")    # χ² → chi2
        t = t.replace("\u03C9\u00B2", "omega2")  # ω² → omega2
        t = re.sub(r"\u03B7\s*2", "eta2", t)     # η 2 → eta2 (space variant)
        t = re.sub(r"\u03C7\s*2", "chi2", t)     # χ 2 → chi2
        t = re.sub(r"\u03C9\s*2", "omega2", t)   # ω 2 → omega2
        t = t.replace("\u03B7", "eta")            # η → eta
        t = t.replace("\u03C7", "chi")            # χ → chi
        t = t.replace("\u03C9", "omega")          # ω → omega
        t = t.replace("\u03B1", "alpha")          # α → alpha
        t = t.replace("\u03B2", "beta")           # β → beta
        t = t.replace("\u03B4", "delta")          # δ → delta
        t = t.replace("\u03C3", "sigma")          # σ → sigma
        t = t.replace("\u03C6", "phi")            # φ → phi
        t = t.replace("\u03BC", "mu")             # μ → mu

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

        # Subscript digits → regular digits
        t = t.replace("\u2080", "0")   # ₀
        t = t.replace("\u2081", "1")   # ₁
        t = t.replace("\u2082", "2")   # ₂
        t = t.replace("\u2083", "3")   # ₃
        t = t.replace("\u2084", "4")   # ₄
        t = t.replace("\u2085", "5")   # ₅
        t = t.replace("\u2086", "6")   # ₆
        t = t.replace("\u2087", "7")   # ₇
        t = t.replace("\u2088", "8")   # ₈
        t = t.replace("\u2089", "9")   # ₉

        report._track("A5_math_symbol_normalization", before, t, "math_symbols_normalized")

        # A6: Footnote marker removal after statistical values
        # "p < .001¹" → "p < .001", "95% CI [0.1, 0.5]²" → "95% CI [0.1, 0.5]"
        # Only remove isolated superscript/subscript digits that follow stat-adjacent chars
        # Note: A5 already converted ² → 2, so we look for isolated digits after ] ) or stat values
        # This catches remaining Unicode superscripts that A5 missed
        before = t
        t = re.sub(
            r"([\d\]\)])[\u00B9\u00B2\u00B3\u2070\u2074-\u2079\u2080-\u2089](?=\s|[,;.\)]|$)",
            r"\1", t
        )
        report._track("A6_footnote_removal", before, t, "footnotes_removed")

    return t.strip(), report
