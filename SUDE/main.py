#!/usr/bin/env python3
"""
main.py – Entry point for the SUDE Laptop Pilot DES.

Usage
-----
  python main.py                   # visual (Pygame) mode
  python main.py --headless        # headless mode (fast, exports files)
  python main.py --seed 123        # custom seed
  python main.py --config cfg.json # custom config
  python main.py --end 14400       # simulate 4 hours
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# ── ensure project root is on path ──
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sim.core import Simulator, EventType
from sim.model import World
from sim.process import create_process_logic
from outputs.metrics import MetricsCollector


def load_config(path: str | None) -> dict:
    if path is None:
        path = os.path.join(ROOT, "config", "default.json")
    with open(path) as f:
        return json.load(f)


def build_sim(cfg: dict, seed: int | None = None) -> Simulator:
    """Construct and wire up a ready-to-run simulator."""
    if seed is None:
        seed = cfg.get("seed", 42)
    sim = Simulator(seed=seed)
    sim.world = World(cfg)
    sim.metrics = MetricsCollector()
    sim._process_logic = create_process_logic()

    # Schedule first arrival
    sim.schedule(0.0, EventType.ARRIVAL, laptop_id=-1)
    return sim


# ── headless run ─────────────────────────────────────────────────────────

def run_headless(cfg: dict, seed: int, end_time: float,
                 output_dir: str) -> None:
    sim = build_sim(cfg, seed)
    t0 = time.monotonic()

    snapshot_interval = 60.0  # sim-seconds
    next_snap = snapshot_interval

    print(f"[headless] seed={seed}  end={end_time:.0f}s "
          f"({end_time/3600:.1f}h)  mode={cfg.get('mode','?')}")

    sim.run_until(end_time)

    # take final snapshot
    sim.metrics.snapshot(sim.now, sim.world)

    elapsed = time.monotonic() - t0
    m = sim.metrics
    print(f"[headless] done in {elapsed:.2f}s wall")
    print(f"  arrivals      {m.total_arrivals}")
    print(f"  departures    {m.total_departures}")
    print(f"  throughput    {m.throughput_per_hour:.1f} /h")
    print(f"  retrieval %   {m.retrieval_ratio:.1%}")
    print(f"  auto success  {m.automation_success_ratio:.1%}")
    print(f"  DB size       {sim.world.db.size()}")
    print(f"  avg cycle     {m.avg_cycle_time:.1f}s")
    print(f"  p95 cycle     {m.p95_cycle_time:.1f}s")

    os.makedirs(output_dir, exist_ok=True)
    m.export_summary(
        os.path.join(output_dir, "run_summary.json"),
        cfg, seed, sim.now,
    )
    m.export_laptop_traces(
        os.path.join(output_dir, "laptop_traces.csv"),
        sim.world,
    )
    m.export_time_series(
        os.path.join(output_dir, "time_series.csv"),
    )
    print(f"  outputs →  {output_dir}/")


# ── visual run ───────────────────────────────────────────────────────────

def run_visual(cfg: dict, seed: int) -> None:
    try:
        import pygame  # noqa: F401
    except ImportError:
        print("ERROR: pygame is not installed. "
              "Install it with:  pip install pygame")
        sys.exit(1)

    from viz.pygame_view import PygameView

    sim = build_sim(cfg, seed)
    view = PygameView(cfg, sim.world, sim.metrics)
    sim.add_state_change_listener(view.on_sim_event)

    print(f"[visual] seed={seed}  mode={cfg.get('mode','?')}  "
          f"speed=×{view.sim_speed:.0f}")
    print("  Space=pause  +/-=speed  S=step  R=reset  Esc=quit")

    view.run_loop(sim)

    # export on exit
    out = os.path.join(ROOT, "outputs", "results")
    os.makedirs(out, exist_ok=True)
    sim.metrics.snapshot(sim.now, sim.world)
    sim.metrics.export_summary(
        os.path.join(out, "run_summary.json"), cfg, seed, sim.now)
    sim.metrics.export_laptop_traces(
        os.path.join(out, "laptop_traces.csv"), sim.world)
    sim.metrics.export_time_series(
        os.path.join(out, "time_series.csv"))
    print(f"  outputs →  {out}/")


# ── CLI ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SUDE Laptop Pilot – Discrete Event Simulation")
    parser.add_argument("--headless", action="store_true",
                        help="Run without visualization")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed (overrides config)")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to config JSON")
    parser.add_argument("--end", type=float, default=None,
                        help="Simulation end time in seconds")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory for results")
    args = parser.parse_args()

    cfg = load_config(args.config)
    seed = args.seed if args.seed is not None else cfg.get("seed", 42)
    end_time = args.end if args.end is not None else cfg.get("sim_end_time", 28800)

    if args.headless:
        out_dir = args.output or os.path.join(ROOT, "outputs", "results")
        run_headless(cfg, seed, end_time, out_dir)
    else:
        run_visual(cfg, seed)


if __name__ == "__main__":
    main()
