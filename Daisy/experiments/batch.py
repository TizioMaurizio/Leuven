"""
experiments/batch.py – Multi-run batch runner with aggregation.

Runs every (or selected) scenario × N replications, collects KPIs, and
writes a summary CSV.

Usage
-----
    python -m experiments.batch                     # all scenarios, 5 reps
    python -m experiments.batch --scenarios base high_arrivals --reps 10
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import time
from typing import Any

import numpy as np

from experiments.scenarios import get_scenario, list_scenarios
from sim.run import run_simulation, RunResult


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_batch(
    scenario_names: list[str] | None = None,
    reps: int = 5,
    base_seed: int = 42,
    output_dir: str | pathlib.Path = "runs",
) -> list[dict[str, Any]]:
    """Run multiple scenarios × replications and return a list of KPI rows."""

    if scenario_names is None:
        scenario_names = list_scenarios()

    output_dir = pathlib.Path(output_dir)
    rows: list[dict[str, Any]] = []

    for sc_name in scenario_names:
        overrides = get_scenario(sc_name)
        for rep in range(reps):
            seed = base_seed + rep
            run_id = f"{sc_name}_rep{rep:03d}"

            # Merge output dir into overrides
            ovr = {**overrides}
            ovr.setdefault("monitor", {})["output_dir"] = str(output_dir)

            print(f"  ▸ {run_id} (seed={seed}) …", end=" ", flush=True)
            t0 = time.perf_counter()

            result: RunResult = run_simulation(
                overrides=ovr,
                seed=seed,
                run_id=run_id,
                viz_enabled=False,
            )

            elapsed = time.perf_counter() - t0
            ct = result.cycle_times
            row: dict[str, Any] = {
                "scenario": sc_name,
                "rep": rep,
                "seed": seed,
                "run_id": run_id,
                "throughput": result.throughput,
                "rejected": result.rejected,
                "ct_mean": float(np.mean(ct)) if ct else None,
                "ct_median": float(np.median(ct)) if ct else None,
                "ct_min": float(min(ct)) if ct else None,
                "ct_max": float(max(ct)) if ct else None,
                "ct_std": float(np.std(ct)) if ct else None,
                "devices_processed": result.outputs_summary["devices_processed"],
                "wall_time_s": round(elapsed, 2),
            }
            # Add fraction totals
            for frac, val in result.outputs_summary["fraction_totals"].items():
                row[f"out_{frac}"] = val

            rows.append(row)
            print(f"done ({result.throughput} dispatched, {elapsed:.1f}s)")

    return rows


def write_summary(rows: list[dict[str, Any]],
                  path: str | pathlib.Path = "runs/batch_summary.csv") -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    cols = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"\n  ✓ Summary written to {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Daisy DES batch runner")
    parser.add_argument("--scenarios", nargs="*", default=None,
                        help="Scenario names to run (default: all)")
    parser.add_argument("--reps", type=int, default=5,
                        help="Replications per scenario")
    parser.add_argument("--base-seed", type=int, default=42)
    parser.add_argument("--output-dir", default="runs")
    args = parser.parse_args()

    print(f"Daisy DES batch – {len(args.scenarios or list_scenarios())} scenarios × {args.reps} reps\n")
    rows = run_batch(
        scenario_names=args.scenarios,
        reps=args.reps,
        base_seed=args.base_seed,
        output_dir=args.output_dir,
    )
    write_summary(rows, path=pathlib.Path(args.output_dir) / "batch_summary.csv")


if __name__ == "__main__":
    main()
