"""
main.py – Daisy iPhone Disassembly DES – unified entry point.

Usage
-----
    python main.py                        # headless single run (default config)
    python main.py --viz                  # single run with Pygame visualisation
    python main.py --batch                # batch run (all scenarios × 5 reps)
    python main.py --batch --scenarios base high_arrivals --reps 10
    python main.py --replay runs/run_001/events.csv
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Daisy iPhone Disassembly – Discrete-Event Simulation",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--viz", action="store_true",
                      help="Run with Pygame visualisation")
    mode.add_argument("--batch", action="store_true",
                      help="Run batch experiment (all/selected scenarios)")
    mode.add_argument("--replay", type=str, default=None,
                      help="Replay an events.csv in Pygame")

    parser.add_argument("--scenarios", nargs="*", default=None,
                        help="Scenario names for batch mode")
    parser.add_argument("--reps", type=int, default=5,
                        help="Replications per scenario (batch mode)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Override random seed")
    parser.add_argument("--speed", type=float, default=None,
                        help="Speed multiplier for viz/replay")
    parser.add_argument("--config", type=str, default=None,
                        help="Override YAML config file")

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Replay mode
    # ------------------------------------------------------------------
    if args.replay:
        from viz.replay import replay
        from config.loader import load_config
        cfg = load_config(overrides=args.config) if args.config else load_config()
        replay(args.replay, cfg=cfg, speed=args.speed or 10.0)
        return

    # ------------------------------------------------------------------
    # Batch mode
    # ------------------------------------------------------------------
    if args.batch:
        from experiments.batch import run_batch, write_summary
        import pathlib
        print(f"Daisy DES batch runner\n{'='*40}")
        rows = run_batch(
            scenario_names=args.scenarios,
            reps=args.reps,
            base_seed=args.seed or 42,
        )
        write_summary(rows)
        return

    # ------------------------------------------------------------------
    # Viz mode
    # ------------------------------------------------------------------
    if args.viz:
        from config.loader import load_config
        from viz.pygame_app import run_viz

        overrides = {}
        if args.speed is not None:
            overrides["viz"] = {"speed_multiplier": args.speed}
        if args.seed is not None:
            overrides["sim"] = {"random_seed": args.seed}

        cfg = load_config(overrides=args.config) if args.config else load_config()
        # Apply CLI overrides
        if args.speed is not None:
            cfg.viz.speed_multiplier = args.speed
        if args.seed is not None:
            cfg.sim.random_seed = args.seed

        run_viz(cfg=cfg)
        return

    # ------------------------------------------------------------------
    # Default: headless single run
    # ------------------------------------------------------------------
    from sim.run import run_simulation

    result = run_simulation(
        config_path=args.config,
        seed=args.seed,
        viz_enabled=False,
    )

    print(f"\n{'='*50}")
    print(f"  Daisy DES – Run Complete")
    print(f"{'='*50}")
    print(f"  Run ID:       {result.run_id}")
    print(f"  Seed:         {result.seed}")
    print(f"  Sim time:     {result.sim_time:,.0f} s")
    print(f"  Throughput:   {result.throughput} devices dispatched")
    print(f"  Rejected:     {result.rejected} devices (unknown model)")

    if result.cycle_times:
        import numpy as np
        ct = result.cycle_times
        print(f"  Cycle time:   mean={np.mean(ct):.1f}s  "
              f"median={np.median(ct):.1f}s  "
              f"min={min(ct):.1f}s  max={max(ct):.1f}s")
    else:
        print(f"  Cycle time:   N/A (no devices completed)")

    print(f"\n  Output fractions:")
    for frac, val in result.outputs_summary["fraction_totals"].items():
        print(f"    {frac:20s}: {val:.1f}")

    print(f"\n  Artefacts:    {result.output_dir}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
