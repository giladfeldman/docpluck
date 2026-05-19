"""Tier-D — deterministic whole-corpus regression gate.

Runs fast, AI-free checks over the harness's saved outputs and emits a verdict
matrix. A *committed baseline* matrix is diffed every run: any cell that was
PASS and is now FAIL is a **regression** and fails the gate. This is the
"a fix is never done forever" backcheck the prior loop lacked.

The matrix stores *verdicts*, never output snapshots — so a baseline that
records a known FAIL cannot mask anything (a FAIL stays a FAIL; only a new
PASS→FAIL transition blocks). Contrast ``scripts/verify_corpus.py``, which
compared against frozen output .md files and silently passed broken output
that matched a broken baseline.

Checks per (document × level):
- ``extraction``   — the harness extraction succeeded and produced its views.
- ``text_loss``    — every substantive source paragraph survives to the
                     user-facing view (#1 rule: never lose text).
- ``table_parity`` — every structured table in tables.json renders as a
                     ``<table>`` in rendered.md; ``### Table`` count matches
                     (PDF only).
- ``glyph``        — no U+FFFD and no Mathematical-Alphanumeric / PUA
                     font-corruption glyphs in the user-facing view.

Semantic correctness ("ξ should be ηp²", wrong-section placement) is NOT a
Tier-D job — that is Tier-A (AI-gold inspection). Tier-D catches the
mechanical, deterministic, regression-prone failures cheaply, corpus-wide,
every cycle.

Usage::

    python -m scripts.harness.checks                    # build matrix, diff baseline
    python -m scripts.harness.checks --update-baseline  # accept current as baseline
    python -m scripts.harness.checks --only <doc_id>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

from . import corpus

_REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = _REPO_ROOT / "verify_out"
MATRIX_PATH = OUT_ROOT / "matrix.json"
BASELINE_PATH = Path(__file__).with_name("baseline_matrix.json")

# --- tunable thresholds (calibrated against the baseline run) ----------------
MIN_PARA_WORDS = 12     # a source paragraph this long is "substantive" body prose
MATCH_WINDOW = 8        # a contiguous N-word run must survive for the para to count
RUNNING_REPEAT = 3      # a paragraph signature recurring >= N times is a per-page
                        # running element (watermark / header) — legitimately
                        # stripped, exempt from text-loss.
# A flagged paragraph whose words almost entirely survive (>= REFLOW_COVERAGE)
# WITH a contiguous run of >= REFLOW_MIN_RUN words intact — but no full
# MATCH_WINDOW run — is a table / stimulus region that pdftotext linearized
# column-major and the renderer reflowed (into a <table> or into prose). The
# text survived; only word order changed. The MATCH_WINDOW proxy assumes prose
# word order, so a reflowed grid trips it — but that is not text loss.
# Calibrated 2026-05-19: across 7 papers, 16 reflowed paragraphs all sit at
# >= 0.94 coverage + run >= 3; the one genuine loss (plos-med-1 SAE Table 5)
# is 0.83 + run 2.
REFLOW_COVERAGE = 0.90
REFLOW_MIN_RUN = 3
# Mathematical Alphanumeric Symbols block — font-corruption when in body text
# (pdftotext mis-decodes e.g. ηp² as U+1D709 MATHEMATICAL ITALIC SMALL XI).
_MATH_ALNUM = (0x1D400, 0x1D7FF)
_PUA = (0xE000, 0xF8FF)


# --------------------------------------------------------------------------
# tokenisation
# --------------------------------------------------------------------------
# Greek letters carry no [a-z] projection, and pdftotext vs the renderer may
# disagree on glyph-vs-ASCII-name (χ ↔ "chi"). Transliterating every Greek
# letter to its spelled name on every fingerprinted string keeps raw and
# rendered comparable regardless of which representation each side emitted.
# Names are space-padded so adjacent letters/digits never glue into one token.
_GREEK_TO_ASCII = {
    "α": " alpha ", "β": " beta ", "γ": " gamma ",
    "δ": " delta ", "ε": " epsilon ", "ζ": " zeta ",
    "η": " eta ", "θ": " theta ", "ι": " iota ",
    "κ": " kappa ", "λ": " lambda ", "μ": " mu ",
    "ν": " nu ", "ξ": " xi ", "ο": " omicron ",
    "π": " pi ", "ρ": " rho ", "ς": " sigma ",
    "σ": " sigma ", "τ": " tau ", "υ": " upsilon ",
    "φ": " phi ", "χ": " chi ", "ψ": " psi ",
    "ω": " omega ",
}


def _fingerprint(text: str) -> list[str]:
    """Lowercased alphabetic-word sequence — the glyph/whitespace-tolerant
    projection used for text-loss matching. Digits and symbols are dropped
    (they are exactly what legitimate normalization rewrites); a trailing
    hyphen line-break is rejoined first; Greek letters are transliterated to
    their spelled names so a glyph/ASCII-name divergence cannot create a
    spurious mismatch."""
    text = text.replace("­", "")              # soft hyphen
    text = re.sub(r"-\s*\n\s*", "", text)          # hard hyphen line-break rejoin
    text = text.lower()
    text = "".join(_GREEK_TO_ASCII.get(c, c) for c in text)
    norm = unicodedata.normalize("NFKD", text)
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    return re.findall(r"[a-z]{3,}", norm)


def _paragraphs(text: str) -> list[str]:
    chunks = re.split(r"\n\s*\n", text)
    return [c.strip() for c in chunks if c.strip()]


# Front-matter affiliation / corresponding-author blocks are metadata, not body
# prose; the renderer relocates author names and drops the contact apparatus.
# A paragraph carrying these markers, near the document start, is exempt from
# text-loss (it is not lost body text).
_META_MARKERS = (
    "corresponding author",
    "e-mail address",
    "email address",
    "conflict of interest",
    "competing interests",
    "author contributions",
    "data accessibility",
    "supplementary material",
)


def _is_frontmatter_metadata(text: str, position_ratio: float) -> bool:
    low = text.lower()
    if any(m in low for m in _META_MARKERS):
        return True
    # affiliation block: department/school/faculty + university, in the first
    # fifth of the document.
    if position_ratio < 0.2 and "universit" in low and re.search(
        r"\b(department|school|faculty|institute)\b", low
    ):
        return True
    if position_ratio < 0.2 and "@" in text and re.search(r"\S+@\S+", text):
        return True
    return False


# Publisher / legal / masthead boilerplate. A paragraph carrying any of these
# is journal apparatus the renderer strips on purpose — not body prose, not
# text loss. (Calibrated 2026-05-17 against the full-corpus baseline run.)
_BOILERPLATE_MARKERS = (
    "terms and conditions", "all rights reserved", "rights reserved",
    "university press", "article reuse guidelines", "reuse guidelines",
    "author manuscript", "final edited form", "available in pmc",
    "creative commons", "sagepub", "tandfonline", "doi.org", "https",
    "issn", "published under the license", "published by", "the author(s)",
    "downloaded from", "journalinformation", "journalcode",
)

# Common English function words — body prose runs ~25-45% function words; a
# linearized table region / stimulus list runs near 0%.
_FUNCTION_WORDS = frozenset(
    "the a an and or but of to in on at by for with from as is are was were "
    "be been being this that these those it its his her their our we they "
    "i you he she not no nor so if then than when while which who whom whose "
    "what where how why all any each more most some such only own same can "
    "will would should could may might must do does did have has had between "
    "into through during before after above below up down out over under "
    "again further once here there".split()
)


def _is_nonbody_paragraph(text: str) -> bool:
    """True if a 'missing' paragraph is publisher boilerplate or a linearized
    table/list region — neither is lost body prose. Table CONTENT correctness
    is the job of ``table_parity`` + Tier-A, not the text-loss check."""
    low = text.lower()
    if any(m in low for m in _BOILERPLATE_MARKERS):
        return True
    words = re.findall(r"[a-z']+", low)
    if len(words) < 6:
        return True
    # table caption ("Table 3. Comparison of ...") flattened into the run
    if words[0] == "table":
        return True
    fn_ratio = sum(w in _FUNCTION_WORDS for w in words) / len(words)
    if fn_ratio < 0.15:
        return True  # near-zero function words → table cells / stimulus list
    if len(set(words)) / len(words) < 0.6:
        return True  # repetition → repeated column headers / grid cells / lists
    return False


# --------------------------------------------------------------------------
# individual checks — each returns {"verdict": "pass|fail|skip", ...}
# --------------------------------------------------------------------------
def check_extraction(meta: dict, out_dir: Path) -> dict:
    if meta.get("status") != "ok":
        return {"verdict": "fail", "reason": meta.get("status"), "detail": meta.get("error", "")}
    return {"verdict": "pass", "views": meta.get("views", [])}


def check_text_loss(out_dir: Path, fmt: str) -> dict:
    raw_p = out_dir / "raw.txt"
    target_p = out_dir / ("rendered.md" if fmt == "pdf" else "normalized.txt")
    if not raw_p.is_file() or not target_p.is_file():
        return {"verdict": "skip", "reason": "raw or target view missing"}
    raw = raw_p.read_text(encoding="utf-8", errors="replace")
    target_fp = _fingerprint(target_p.read_text(encoding="utf-8", errors="replace"))
    target_windows = {
        tuple(target_fp[i : i + MATCH_WINDOW]) for i in range(len(target_fp) - MATCH_WINDOW + 1)
    }
    target_word_set = set(target_fp)
    target_runs = {
        tuple(target_fp[i : i + REFLOW_MIN_RUN])
        for i in range(len(target_fp) - REFLOW_MIN_RUN + 1)
    }
    paras = _paragraphs(raw)
    para_fps = [_fingerprint(p) for p in paras]
    # A run of N words that recurs across the document is a per-page running
    # element (download watermark, journal masthead). Build the set of such
    # n-grams; a paragraph mostly covered by them is legitimately stripped.
    gram_counts: dict[tuple, int] = {}
    for fp in para_fps:
        for i in range(len(fp) - MATCH_WINDOW + 1):
            g = tuple(fp[i : i + MATCH_WINDOW])
            gram_counts[g] = gram_counts.get(g, 0) + 1
    running = {g for g, n in gram_counts.items() if n >= RUNNING_REPEAT}
    missing: list[str] = []
    checked = 0
    reflowed = 0
    n_paras = len(paras)
    for idx, (para, fp) in enumerate(zip(paras, para_fps)):
        if len(fp) < MIN_PARA_WORDS:
            continue  # headers / page numbers — legitimately reflowed
        grams = [tuple(fp[i : i + MATCH_WINDOW]) for i in range(len(fp) - MATCH_WINDOW + 1)]
        if grams and sum(g in running for g in grams) / len(grams) >= 0.5:
            continue  # per-page running element — legitimately stripped
        if _is_frontmatter_metadata(para, idx / max(1, n_paras)):
            continue  # affiliation / contact apparatus — not body prose
        checked += 1
        survived = any(g in target_windows for g in grams)
        if not survived:
            # A missing paragraph is real text-loss only if it is body prose.
            # Publisher boilerplate and linearized table/list regions are not.
            if _is_nonbody_paragraph(para):
                continue
            # Right words, reordered: near-total word survival plus an intact
            # contiguous run is a linearized table / stimulus region the
            # renderer reflowed — not text loss (see REFLOW_* above).
            coverage = sum(w in target_word_set for w in fp) / len(fp)
            has_run = any(
                tuple(fp[i : i + REFLOW_MIN_RUN]) in target_runs
                for i in range(len(fp) - REFLOW_MIN_RUN + 1)
            )
            if coverage >= REFLOW_COVERAGE and has_run:
                reflowed += 1
                continue
            missing.append(" ".join(fp[:18]))
    if missing:
        return {
            "verdict": "fail",
            "checked_paragraphs": checked,
            "reflowed_exempt": reflowed,
            "missing_count": len(missing),
            "missing_samples": missing[:8],
        }
    return {"verdict": "pass", "checked_paragraphs": checked, "reflowed_exempt": reflowed}


def check_table_parity(out_dir: Path, fmt: str) -> dict:
    if fmt != "pdf":
        return {"verdict": "skip", "reason": "non-pdf"}
    tables_p = out_dir / "tables.json"
    rendered_p = out_dir / "rendered.md"
    if not tables_p.is_file() or not rendered_p.is_file():
        return {"verdict": "skip", "reason": "tables.json or rendered.md missing"}
    tables = json.loads(tables_p.read_text(encoding="utf-8")).get("tables", [])
    rendered = rendered_p.read_text(encoding="utf-8", errors="replace")
    n_json = len(tables)
    n_headings = len(re.findall(r"^#{2,4}\s+Table\b", rendered, re.M))
    n_html = rendered.count("<table")
    n_structured = sum(1 for t in tables if t.get("kind") == "structured" and t.get("html"))
    problems: list[str] = []
    if n_headings != n_json:
        problems.append(f"### Table headings={n_headings} but tables.json has {n_json}")
    if n_html < n_structured:
        problems.append(f"<table> count={n_html} but {n_structured} structured tables in json")
    if problems:
        return {
            "verdict": "fail",
            "tables_json": n_json,
            "table_headings": n_headings,
            "html_tables": n_html,
            "structured": n_structured,
            "problems": problems,
        }
    return {"verdict": "pass", "tables_json": n_json, "html_tables": n_html}


def check_glyph(out_dir: Path, fmt: str) -> dict:
    target_p = out_dir / ("rendered.md" if fmt == "pdf" else "normalized.txt")
    if not target_p.is_file():
        return {"verdict": "skip", "reason": "target view missing"}
    text = target_p.read_text(encoding="utf-8", errors="replace")
    replacement = text.count("�")
    math_alnum = sum(1 for c in text if _MATH_ALNUM[0] <= ord(c) <= _MATH_ALNUM[1])
    pua = sum(1 for c in text if _PUA[0] <= ord(c) <= _PUA[1])
    bad = replacement + math_alnum + pua
    if bad:
        return {
            "verdict": "fail",
            "replacement_char": replacement,
            "math_alphanumeric": math_alnum,
            "private_use": pua,
        }
    return {"verdict": "pass"}


CHECKS = ("extraction", "text_loss", "table_parity", "glyph")


def run_cell(doc: dict, level: str) -> dict | None:
    """All checks for one (document × level). None if the cell was never extracted."""
    out_dir = OUT_ROOT / doc["id"] / level
    meta_p = out_dir / "_meta.json"
    if not meta_p.is_file():
        return None
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    fmt = doc["format"]
    extraction = check_extraction(meta, out_dir)
    if extraction["verdict"] == "fail":
        # extraction failed — downstream checks cannot run
        return {c: ({"verdict": "skip", "reason": "extraction failed"}) for c in CHECKS} | {
            "extraction": extraction
        }
    return {
        "extraction": extraction,
        "text_loss": check_text_loss(out_dir, fmt),
        "table_parity": check_table_parity(out_dir, fmt),
        "glyph": check_glyph(out_dir, fmt),
    }


# --------------------------------------------------------------------------
# matrix + regression diff
# --------------------------------------------------------------------------
def build_matrix(docs: list[dict], levels: list[str]) -> dict:
    matrix: dict = {}
    for doc in docs:
        for level in levels:
            cell = run_cell(doc, level)
            if cell is not None:
                matrix.setdefault(doc["id"], {})[level] = cell
    return matrix


def _verdicts(matrix: dict) -> dict[tuple[str, str, str], str]:
    """Flatten to {(doc, level, check): verdict}."""
    flat: dict[tuple[str, str, str], str] = {}
    for doc_id, levels in matrix.items():
        for level, checks in levels.items():
            for check, result in checks.items():
                flat[(doc_id, level, check)] = result["verdict"]
    return flat


def diff_baseline(matrix: dict) -> dict:
    baseline = (
        json.loads(BASELINE_PATH.read_text(encoding="utf-8")) if BASELINE_PATH.is_file() else {}
    )
    cur = _verdicts(matrix)
    base = _verdicts(baseline)
    regressions, new_fails, fixed, still_failing = [], [], [], []
    for key, verdict in cur.items():
        prior = base.get(key)
        if verdict == "fail" and prior == "pass":
            regressions.append(key)
        elif verdict == "fail" and prior is None:
            new_fails.append(key)
        elif verdict == "fail":
            still_failing.append(key)
        elif verdict == "pass" and prior == "fail":
            fixed.append(key)
    return {
        "regressions": sorted(regressions),
        "new_fails": sorted(new_fails),
        "fixed": sorted(fixed),
        "still_failing": sorted(still_failing),
        "has_baseline": bool(baseline),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="docpluck harness — Tier-D regression gate")
    ap.add_argument("--levels", nargs="+", default=["none", "standard", "academic"])
    ap.add_argument("--only", nargs="+", help="specific doc ids")
    ap.add_argument("--update-baseline", action="store_true",
                    help="write the current matrix as the committed baseline")
    args = ap.parse_args()

    manifest = corpus.load_manifest()
    docs = manifest["documents"]
    if args.only:
        wanted = set(args.only)
        docs = [d for d in docs if d["id"] in wanted]

    matrix = build_matrix(docs, args.levels)
    OUT_ROOT.mkdir(exist_ok=True)
    MATRIX_PATH.write_text(json.dumps(matrix, indent=2, ensure_ascii=False), encoding="utf-8")

    flat = _verdicts(matrix)
    cells = len({(d, l) for d, l, _ in flat})
    fails = sum(1 for v in flat.values() if v == "fail")
    print(f"matrix: {len(matrix)} docs, {cells} (doc x level) cells, {len(flat)} check-results")
    print(f"  pass={sum(1 for v in flat.values() if v=='pass')} "
          f"fail={fails} skip={sum(1 for v in flat.values() if v=='skip')}")

    if args.update_baseline:
        BASELINE_PATH.write_text(json.dumps(matrix, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"baseline updated -> {BASELINE_PATH}")
        return 0

    diff = diff_baseline(matrix)
    if not diff["has_baseline"]:
        print("no baseline yet — run with --update-baseline once the corpus is verified clean")
        return 0
    print(f"\nvs baseline: {len(diff['regressions'])} REGRESSIONS, "
          f"{len(diff['new_fails'])} new fails, {len(diff['fixed'])} fixed, "
          f"{len(diff['still_failing'])} still failing")
    for d, l, c in diff["regressions"]:
        print(f"  REGRESSION  {d} / {l} / {c}")
    for d, l, c in diff["new_fails"]:
        print(f"  NEW FAIL    {d} / {l} / {c}")
    for d, l, c in diff["fixed"][:20]:
        print(f"  fixed       {d} / {l} / {c}")
    # The gate fails on a regression OR a new fail (an uncovered defect).
    return 1 if (diff["regressions"] or diff["new_fails"]) else 0


if __name__ == "__main__":
    sys.exit(main())
