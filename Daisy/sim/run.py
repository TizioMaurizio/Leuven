"""
sim/run.py – Single-run entry point.

Usage
-----
    from sim.run import run_simulation
    results = run_simulation()                       # defaults
    results = run_simulation(overrides={"S3": {"p_battery_issue": {"value": 0.15}}})
    results = run_simulation(config_path="experiments/high_jam.yaml")
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any

import numpy as np
import simpy

from config.loader import load_config
from sim.entities import EventBus
from sim.system import build_system, SystemContext
from sim.monitor import Monitor


@dataclass
class RunResult:
    """Outcome of one simulation run."""
    run_id: str
    seed: int
    sim_time: float
    throughput: int
    rejected: int
    cycle_times: list[float]
    outputs_summary: dict[str, Any]
    output_dir: pathlib.Path | None
    ctx: SystemContext  # for post-hoc inspection


def run_simulation(
    config_path: str | pathlib.Path | None = None,
    overrides: dict | None = None,
    *,
    seed: int | None = None,
    run_id: str | None = None,
    viz_enabled: bool | None = None,
) -> RunResult:
    """Execute one complete simulation run and return results.

    Parameters
    ----------
    config_path : path, optional
        Override YAML file to merge on top of defaults.
    overrides : dict, optional
        Override dict to merge on top of defaults (applied after config_path).
    seed : int, optional
        Override the random seed in config.
    run_id : str, optional
        Override the run_id in config.
    viz_enabled : bool, optional
        If given, overrides ``viz.enabled`` in config.
    """
    # -- Configuration -------------------------------------------------------
    ovr = {}
    if config_path is not None:
        cfg = load_config(overrides=config_path)
    else:
        cfg = load_config()

    # Apply dict overrides on top
    if overrides:
        cfg = load_config(overrides=overrides)

    # If both file + dict overrides requested, layer them
    if config_path is not None and overrides is not None:
        from config.loader import _deep_merge, load_config as _lc, Cfg
        import yaml
        with open(pathlib.Path(__file__).parent.parent / "config" / "defaults.yaml") as f:
            base = yaml.safe_load(f)
        with open(config_path) as f:
            file_ovr = yaml.safe_load(f) or {}
        merged = _deep_merge(base, file_ovr)
        merged = _deep_merge(merged, overrides)
        cfg = Cfg(merged)

    if seed is not None:
        cfg.sim.random_seed = seed
    if run_id is not None:
        cfg.sim.run_id = run_id
    if viz_enabled is not None:
        cfg.viz.enabled = viz_enabled

    # -- RNG -----------------------------------------------------------------
    rng = np.random.default_rng(cfg.sim.random_seed)

    # -- Build ---------------------------------------------------------------
    env = simpy.Environment()
    bus = EventBus()
    ctx = build_system(env, cfg, bus, rng)

    # -- Monitor -------------------------------------------------------------
    monitor = Monitor(ctx)
    monitor.start_sampler()

    # -- Run -----------------------------------------------------------------
    env.run(until=cfg.sim.time_horizon)

    # -- Collect results -----------------------------------------------------
    monitor.flush()

    completed_devices = list(ctx.completed.items)
    cycle_times = [d.cycle_time for d in completed_devices
                   if d.cycle_time is not None]

    return RunResult(
        run_id=cfg.sim.run_id,
        seed=cfg.sim.random_seed,
        sim_time=env.now,
        throughput=len(completed_devices),
        rejected=len(ctx.reject.items),
        cycle_times=cycle_times,
        outputs_summary=ctx.outputs.summary(),
        output_dir=monitor.output_dir,
        ctx=ctx,
    )
