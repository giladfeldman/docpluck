"""Tier-A — AI-gold deep-inspection driver for the docpluck verification harness.

Tier-D (``checks.py``) catches mechanical, deterministic defects corpus-wide
and cheaply. Tier-A catches the *semantic* defects Tier-D cannot — a glyph that
is a valid codepoint but the wrong letter (``ξ`` where the paper has ``ηp²``),
a paragraph under the wrong heading, a table spliced into prose, a caption
welded to a column header. Ground truth is the article-finder AI-multimodal
gold (the ``reading`` view); docpluck never generates ground truth itself
(rule 18).

This module does NOT call an LLM. It is the *driver*:

- ``prepare`` — selects which (document × level) cells to AI-verify this cycle
  (the tiered policy: changed docs + every open Tier-D fail + a rotating
  slice), pairs each with its gold + saved harness outputs, and writes
  ``verify_out/inspect_jobs.json``.
- The orchestrator (docpluck-iterate / -qa) dispatches one verifier agent per
  job, using ``VERIFIER_PROMPT.md``. Each agent writes
  ``verify_out/<doc>/<level>/ai_verdict.json``.
- ``collect`` — aggregates those verdicts back into the matrix.

Gold keys: a document maps to a canonical ai-gold key via
``gold_keys.json`` (committed; populated by ``--discover`` and by A6 gold
generation). A document with no gold is reported ``gold_blocked`` — never
silently passed.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from . import checks, corpus

_REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = _REPO_ROOT / "verify_out"
JOBS_PATH = OUT_ROOT / "inspect_jobs.json"
GOLD_KEYS_PATH = Path(__file__).with_name("gold_keys.json")
AI_GOLD = Path.home() / ".claude" / "skills" / "article-finder" / "ai-gold.py"

ROTATING_SLICE = 10  # docs rotated through AI-verify when nothing else selects them


# --------------------------------------------------------------------------
# gold key resolution
# --------------------------------------------------------------------------
def load_gold_keys() -> dict[str, str]:
    if GOLD_KEYS_PATH.is_file():
        return json.loads(GOLD_KEYS_PATH.read_text(encoding="utf-8"))
    return {}


def _ai_gold(*args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(
            [sys.executable, str(AI_GOLD), *args],
            capture_output=True, text=True, timeout=60,
        )
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def gold_reading_path(doc: dict, gold_keys: dict[str, str]) -> Path | None:
    """Absolute path to the document's AI-gold ``reading`` view, or None."""
    key = gold_keys.get(doc["id"])
    if not key:
        return None
    rc, _ = _ai_gold("check", key, "--view", "reading")
    if rc != 0:
        return None
    rc, out = _ai_gold("get", key, "--view", "reading")
    if rc != 0 or not out:
        return None
    p = Path(out.splitlines()[-1].strip())
    return p if p.is_file() else None


# --------------------------------------------------------------------------
# job selection — the tiered policy
# --------------------------------------------------------------------------
def _rotating(docs: list[dict], n: int) -> list[dict]:
    """A deterministic rotating slice keyed on the day, so coverage advances
    without re-picking the same docs every cycle."""
    day = _dt.date.today().toordinal()
    if not docs:
        return []
    start = (day * n) % len(docs)
    return [docs[(start + i) % len(docs)] for i in range(min(n, len(docs)))]


def select_jobs(
    docs: list[dict],
    levels: list[str],
    affected_ids: set[str],
    matrix: dict,
) -> list[dict]:
    """Tiered selection: affected docs + every open Tier-D fail + rotating slice."""
    by_id = {d["id"]: d for d in docs}
    selected: dict[str, dict] = {}

    # 1. cycle-affected documents
    for did in affected_ids:
        if did in by_id:
            selected[did] = by_id[did]
    # 2. every document with an open Tier-D failure
    for did, lvls in matrix.items():
        if did not in by_id:
            continue
        for _lv, cks in lvls.items():
            if any(c.get("verdict") == "fail" for c in cks.values()):
                selected[did] = by_id[did]
                break
    # 3. a rotating slice for steady coverage
    for d in _rotating([d for d in docs if d["id"] not in selected], ROTATING_SLICE):
        selected[d["id"]] = d

    gold_keys = load_gold_keys()
    jobs: list[dict] = []
    for doc in selected.values():
        gold = gold_reading_path(doc, gold_keys)
        for level in levels:
            out_dir = OUT_ROOT / doc["id"] / level
            if not (out_dir / "_meta.json").is_file():
                continue  # not extracted
            views = {
                v: str(out_dir / fn)
                for v, fn in (
                    ("rendered", "rendered.md"),
                    ("raw", "raw.txt"),
                    ("normalized", "normalized.txt"),
                    ("tables", "tables.json"),
                    ("sections", "sections.json"),
                )
                if (out_dir / fn).is_file()
            }
            jobs.append(
                {
                    "doc_id": doc["id"],
                    "level": level,
                    "format": doc["format"],
                    "gold_reading": str(gold) if gold else None,
                    "status": "ready" if gold else "gold_blocked",
                    "outputs": views,
                    "verdict_path": str(out_dir / "ai_verdict.json"),
                }
            )
    return jobs


# --------------------------------------------------------------------------
# verdict collection
# --------------------------------------------------------------------------
def collect() -> dict:
    """Merge every ai_verdict.json into a {doc: {level: verdict}} summary."""
    summary: dict = {}
    for vp in OUT_ROOT.glob("*/*/ai_verdict.json"):
        try:
            verdict = json.loads(vp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        doc_id, level = vp.parts[-3], vp.parts[-2]
        summary.setdefault(doc_id, {})[level] = verdict
    fails = [
        (d, l) for d, lv in summary.items() for l, v in lv.items()
        if v.get("verdict") == "fail"
    ]
    return {"summary": summary, "fail_count": len(fails), "fails": sorted(fails)}


def main() -> int:
    ap = argparse.ArgumentParser(description="docpluck harness — Tier-A AI-gold driver")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_prep = sub.add_parser("prepare", help="write inspect_jobs.json")
    p_prep.add_argument("--levels", nargs="+", default=["academic"])
    p_prep.add_argument("--affected", nargs="*", default=[], help="cycle-affected doc ids")
    sub.add_parser("collect", help="aggregate ai_verdict.json files")
    p_disc = sub.add_parser("discover", help="best-effort doc->gold-key resolution")
    p_disc.add_argument("--write", action="store_true")
    args = ap.parse_args()

    manifest = corpus.load_manifest()
    docs = manifest["documents"]

    if args.cmd == "prepare":
        matrix = (
            json.loads(checks.MATRIX_PATH.read_text(encoding="utf-8"))
            if checks.MATRIX_PATH.is_file()
            else {}
        )
        jobs = select_jobs(docs, args.levels, set(args.affected), matrix)
        OUT_ROOT.mkdir(exist_ok=True)
        JOBS_PATH.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")
        ready = sum(1 for j in jobs if j["status"] == "ready")
        blocked = sum(1 for j in jobs if j["status"] == "gold_blocked")
        print(f"{len(jobs)} jobs -> {JOBS_PATH}  ({ready} ready, {blocked} gold_blocked)")
        return 0

    if args.cmd == "collect":
        result = collect()
        print(f"AI verdicts: {len(result['summary'])} docs, {result['fail_count']} fails")
        for d, l in result["fails"]:
            print(f"  AI-FAIL {d} / {l}")
        return 1 if result["fail_count"] else 0

    if args.cmd == "discover":
        keys = load_gold_keys()
        found = 0
        for doc in docs:
            if doc["id"] in keys:
                continue
            rc, out = _ai_gold("resolve", Path(doc["rel_path"]).stem)
            if rc == 0 and out and "__" in out.splitlines()[-1]:
                keys[doc["id"]] = out.splitlines()[-1].strip()
                found += 1
        print(f"resolved {found} new gold keys ({len(keys)} total)")
        if args.write:
            GOLD_KEYS_PATH.write_text(
                json.dumps(keys, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            print(f"wrote {GOLD_KEYS_PATH}")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
