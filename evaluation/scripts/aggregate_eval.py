"""Aggregate `evaluation/results/<ts>/*.jsonl` into a Markdown report.

Usage:
    python evaluation/scripts/aggregate_eval.py --run latest
    python evaluation/scripts/aggregate_eval.py --run 20260503-203011
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "evaluation" / "results"


def _load_runs(run_id: str) -> dict[str, list[dict]]:
    if run_id == "latest":
        runs = sorted([p for p in RESULTS.glob("*-*") if p.is_dir()])
        if not runs:
            raise SystemExit("No result runs found.")
        run_dir = runs[-1]
    else:
        run_dir = RESULTS / run_id
    out: dict[str, list[dict]] = {}
    for f in run_dir.glob("*.jsonl"):
        out[f.stem] = [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    return out, run_dir  # type: ignore[return-value]


def _percentiles(values: list[float], pcts: list[float]) -> list[float]:
    if not values:
        return [0.0] * len(pcts)
    s = sorted(values)
    out = []
    for p in pcts:
        if len(s) == 1:
            out.append(s[0])
            continue
        k = (len(s) - 1) * p
        lo = int(k)
        hi = min(lo + 1, len(s) - 1)
        out.append(s[lo] + (s[hi] - s[lo]) * (k - lo))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()
    by_dataset, run_dir = _load_runs(args.run)

    lines: list[str] = [f"# Evaluation report — {run_dir.name}", ""]
    for ds, rows in by_dataset.items():
        lines.append(f"## {ds} ({len(rows)} samples)")
        ok = [r for r in rows if r.get("status") == "done"]
        lat = [r["latency_ms"] for r in rows if isinstance(r.get("latency_ms"), int)]
        cost = [r.get("cost_usd", 0.0) for r in rows]
        p50, p95, p99 = _percentiles([float(x) for x in lat], [0.5, 0.95, 0.99])
        success = (len(ok) / len(rows) * 100) if rows else 0.0
        lines += [
            f"- Success rate: **{success:.1f}%**",
            f"- Latency P50/P95/P99: {p50:.0f} / {p95:.0f} / {p99:.0f} ms",
            f"- Mean cost: ${statistics.mean(cost):.5f}" if cost else "",
        ]

        # Per-sample judge averages
        scores: dict[str, list[float]] = {}
        for r in rows:
            j = r.get("judge") or {}
            if not isinstance(j, dict):
                continue
            for k, v in j.items():
                if isinstance(v, (int, float)):
                    scores.setdefault(k, []).append(float(v))
        if scores:
            lines.append("")
            lines.append("| Metric | Mean |")
            lines.append("|---|---|")
            for k, v in sorted(scores.items()):
                lines.append(f"| {k} | {statistics.mean(v):.2f} |")
        lines.append("")

    out_path = run_dir / "report.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(out_path)
    print("---")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
