"""Sum per-model token usage from a Claude Code session jsonl transcript.

Reads the transcript line-by-line, picks out `type == "assistant"` records,
buckets their usage by model family (opus / sonnet / haiku / other), and
returns a dict suitable for writing into `tmp/pretest_results_arm<X>.json`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_FAMILIES = ("opus", "sonnet", "haiku", "other")
_FIELDS = ("input_tokens", "output_tokens",
           "cache_read_input_tokens", "cache_creation_input_tokens")


def _empty_bucket() -> dict[str, int]:
    return {f: 0 for f in _FIELDS}


def _family_of(model: str) -> str:
    m = model.lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    if "haiku" in m:
        return "haiku"
    return "other"


def sum_tokens_by_model(transcript: Path) -> dict[str, dict[str, int]]:
    """Sum token usage from a Claude Code session jsonl, grouped by model family."""
    totals: dict[str, dict[str, int]] = {fam: _empty_bucket() for fam in _FAMILIES}
    if not transcript.exists() or transcript.stat().st_size == 0:
        return totals

    with transcript.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "assistant":
                continue
            msg = rec.get("message") or {}
            usage = msg.get("usage") or {}
            model = msg.get("model") or ""
            fam = _family_of(model)
            for field in _FIELDS:
                val = usage.get(field)
                if isinstance(val, int):
                    totals[fam][field] += val
    return totals


def equivalent_api_cost_usd(totals: dict[str, dict[str, int]]) -> float:
    """Compute equivalent API cost using public per-million rates.

    NOT what the user pays on Max — this is the efficiency unit for the pre-test.
    Opus 4.7: $15 in / $75 out per M.  Haiku 4.5: $1 in / $5 out per M.
    Sonnet 4.6: $3 in / $15 out per M (priced for completeness).
    """
    rates = {
        "opus":   (15.0, 75.0),
        "sonnet": (3.0,  15.0),
        "haiku":  (1.0,  5.0),
        "other":  (0.0,  0.0),
    }
    cost = 0.0
    for fam, (in_rate, out_rate) in rates.items():
        bucket = totals.get(fam, {})
        cost += bucket.get("input_tokens", 0) / 1_000_000.0 * in_rate
        cost += bucket.get("output_tokens", 0) / 1_000_000.0 * out_rate
    return round(cost, 4)


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("transcript", type=Path, help="Path to session jsonl")
    p.add_argument("--out", type=Path, required=True, help="Where to write JSON results")
    p.add_argument("--arm", choices=["A", "B"], required=True)
    p.add_argument("--start-sha", required=True)
    p.add_argument("--end-sha", required=True)
    p.add_argument("--wall-minutes", type=float, required=True)
    p.add_argument("--cycles", type=int, required=True)
    p.add_argument("--passed", nargs="*", default=[], help="paper stems that PASSed")
    p.add_argument("--failed", nargs="*", default=[], help="paper stems that FAILed")
    p.add_argument("--stop-reason", choices=["goal", "time", "cycles"], required=True)
    p.add_argument("--diff-lines", type=int, required=True)
    p.add_argument("--regression-26", required=True,
                   help="PASS, FAIL, or '<n> regressions'")
    args = p.parse_args()

    totals = sum_tokens_by_model(args.transcript)
    payload = {
        "arm": args.arm,
        "start_sha": args.start_sha,
        "end_sha": args.end_sha,
        "cycles_run": args.cycles,
        "papers_passed": args.passed,
        "papers_failed": args.failed,
        "tokens": totals,
        "wall_time_minutes": args.wall_minutes,
        "api_equivalent_cost_usd": equivalent_api_cost_usd(totals),
        "stop_reason": args.stop_reason,
        "diff_lines_changed": args.diff_lines,
        "regression_baseline_26_paper": args.regression_26,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
