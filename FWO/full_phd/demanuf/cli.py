"""Command-line interface for the demanuf package.

Usage:
    python -m demanuf.cli simulate --seed 1 --steps 200
    python -m demanuf.cli simulate --seed 1 --steps 50 --regime high
    python -m demanuf.cli eval --ablations A0 A4 --seeds 3 --steps 50
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .config import UncertaintyRegime
from .des.scenarios import NAMED_REGIMES
from .des.simulation import SimulationRunner


def cmd_simulate(args: argparse.Namespace) -> None:
    """Run a DES simulation and write results."""
    regime = NAMED_REGIMES.get(args.regime, UncertaintyRegime())

    runner = SimulationRunner(
        seed=args.seed,
        regime=regime,
        max_steps=args.steps,
        max_products=args.products,
    )

    t0 = time.perf_counter()
    metrics = runner.run()
    elapsed = time.perf_counter() - t0

    # Determine output dir
    run_id = f"seed{args.seed}_steps{args.steps}_{args.regime}"
    run_dir = Path(args.output) / run_id
    runner.write_results(run_dir)

    print(f"Simulation complete in {elapsed:.3f}s")
    print(f"  Products completed: {metrics.products_completed}")
    print(f"  Escalations:        {metrics.escalations}")
    print(f"  Safety violations:  {metrics.safety_violations}")
    print(f"  Throughput:         {metrics.throughput:.4f} products/time-unit")
    print(f"  Avg cycle time:     {metrics.avg_cycle_time:.2f}")
    print(f"  Events logged:      {len(metrics.event_log)}")
    print(f"  Results written to: {run_dir}")


def cmd_eval(args: argparse.Namespace) -> None:
    """Run ablation evaluation and write report."""
    from .eval.ablation import run_ablation, ABLATION_IDS
    from .eval.report import write_report, generate_report

    ablation_ids = args.ablations or ABLATION_IDS
    seeds = list(range(args.seeds))
    regime = NAMED_REGIMES.get(args.regime, UncertaintyRegime())

    print(f"Running ablation study: {ablation_ids}")
    print(f"  Seeds: {args.seeds}, Steps: {args.steps}, Products: {args.products}")

    t0 = time.perf_counter()
    results_dict = run_ablation(
        ablation_ids=ablation_ids,
        seeds=seeds,
        regime=regime,
        regime_name=args.regime,
        max_steps=args.steps,
        max_products=args.products,
    )
    elapsed = time.perf_counter() - t0

    # Flatten results
    all_results = []
    for aid, abl in results_dict.items():
        all_results.extend(abl.runs)
        print(f"  {aid}: {abl.n_runs} runs")

    out_dir = write_report(all_results, args.output)
    print(f"\nDone in {elapsed:.2f}s — {len(all_results)} total runs")
    print(f"Results written to: {out_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="demanuf",
        description="Holonic Demanufacturing Coordination Architecture",
    )
    sub = parser.add_subparsers(dest="command")

    sim = sub.add_parser("simulate", help="Run a DES simulation")
    sim.add_argument("--seed", type=int, default=42, help="Random seed")
    sim.add_argument("--steps", type=int, default=200, help="Max simulation steps")
    sim.add_argument("--products", type=int, default=30, help="Max products to generate")
    sim.add_argument("--regime", type=str, default="medium",
                     choices=list(NAMED_REGIMES.keys()),
                     help="Uncertainty regime preset")
    sim.add_argument("--output", type=str, default="data/runs",
                     help="Output directory for run results")

    # ── eval subcommand ───────────────────────────────────────
    ev = sub.add_parser("eval", help="Run ablation evaluation study")
    ev.add_argument("--ablations", nargs="*", default=None,
                    help="Ablation IDs to run (default: A0-A4)")
    ev.add_argument("--seeds", type=int, default=5,
                    help="Number of seeds (0..N-1)")
    ev.add_argument("--steps", type=int, default=200, help="Max simulation steps")
    ev.add_argument("--products", type=int, default=30, help="Max products")
    ev.add_argument("--regime", type=str, default="medium",
                    choices=list(NAMED_REGIMES.keys()),
                    help="Uncertainty regime preset")
    ev.add_argument("--output", type=str, default="data/eval",
                    help="Output directory for eval results")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "simulate":
        cmd_simulate(args)
    elif args.command == "eval":
        cmd_eval(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
