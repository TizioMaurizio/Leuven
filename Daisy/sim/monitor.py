"""
sim/monitor.py – Logging, time-series sampling, and run-metadata export.

The ``Monitor`` class subscribes to the ``EventBus`` and writes:

1. **events.csv** – append-only CSV of every event.
2. **samples.csv** – periodic time-series snapshots (queue lengths,
   resource utilisation, completed count).
3. **metadata.json** – config snapshot + KPI summary at end of run.

A SimPy process (``periodic_sampler``) is started by the ``Monitor``
itself and appends rows to the samples buffer.
"""

from __future__ import annotations

import csv
import io
import json
import os
import pathlib
from typing import Any

import simpy
import numpy as np

from sim.entities import EventBus, OutputStreams
from sim.system import SystemContext


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------

class Monitor:
    """Central logging / monitoring facade for one simulation run."""

    # CSV column order
    EVENT_COLS = (
        "run_id", "seed", "t", "device_id", "station", "event",
        "model_class", "damage_state", "battery_state",
        "exceptions", "extra_json",
    )

    SAMPLE_COLS = (
        "run_id", "t",
        "Q0", "Q1", "Q2", "Q3", "Q4", "Q5",
        "completed",
        "op_feed_util", "scanner_util", "m1_fixture_util",
        "m2_cooling_slot_util", "op_battery_monitor_util",
        "m3_punch_util", "op_maint_util",
        "m4_module_util", "op_sort_util", "op_pack_util",
    )

    def __init__(self, ctx: SystemContext):
        self.ctx = ctx
        self.cfg = ctx.cfg
        self.bus = ctx.bus
        self.run_id = ctx.cfg.sim.run_id
        self.seed = ctx.cfg.sim.random_seed

        mon_cfg = ctx.cfg.monitor
        self.sample_period: float = mon_cfg.sample_period
        self.output_dir = pathlib.Path(mon_cfg.output_dir) / self.run_id
        self.log_events = mon_cfg.log_events_csv
        self.log_samples = mon_cfg.log_samples_csv
        self.write_meta = mon_cfg.write_metadata_json

        # In-memory buffers (flushed at end or periodically)
        self._event_rows: list[dict[str, Any]] = []
        self._sample_rows: list[dict[str, Any]] = []

        # Subscribe to event bus
        if self.log_events:
            self.bus.subscribe(self._on_event)

    # -- event callback -----------------------------------------------------

    def _on_event(self, evt: dict[str, Any]) -> None:
        row = {
            "run_id": self.run_id,
            "seed": self.seed,
            "t": evt.get("t"),
            "device_id": evt.get("device_id"),
            "station": evt.get("station"),
            "event": evt.get("event"),
            "model_class": evt.get("model_class", ""),
            "damage_state": evt.get("damage_state", ""),
            "battery_state": evt.get("battery_state", ""),
            "exceptions": json.dumps(evt.get("exceptions", [])),
            "extra_json": json.dumps(evt.get("extra", {})),
        }
        self._event_rows.append(row)

    # -- periodic sampler (SimPy process) -----------------------------------

    def start_sampler(self) -> simpy.Process:
        """Launch the periodic sampler process inside the simulation."""
        return self.ctx.env.process(self._sampler_proc())

    def _sampler_proc(self):
        env = self.ctx.env
        while True:
            yield env.timeout(self.sample_period)
            self._take_sample()

    def _take_sample(self) -> None:
        ctx = self.ctx
        row: dict[str, Any] = {
            "run_id": self.run_id,
            "t": ctx.env.now,
        }
        for qname in ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5"):
            store = ctx.queues[qname]
            row[qname] = len(store.items)
        row["completed"] = len(ctx.completed.items)

        util = ctx.resources.utilization_snapshot()
        for rname, info in util.items():
            cap = info["capacity"]
            row[f"{rname}_util"] = info["in_use"] / cap if cap > 0 else 0.0

        self._sample_rows.append(row)

    # -- get live snapshot (for viz) ----------------------------------------

    def live_snapshot(self) -> dict[str, Any]:
        """Return current state for the Pygame visualisation."""
        ctx = self.ctx
        snap: dict[str, Any] = {"t": ctx.env.now}
        for qname in ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5"):
            snap[qname] = len(ctx.queues[qname].items)
        snap["completed"] = len(ctx.completed.items)
        snap["rejected"] = len(ctx.reject.items)
        snap["util"] = ctx.resources.utilization_snapshot()
        snap["outputs"] = ctx.outputs.summary()
        return snap

    # -- flush to disk ------------------------------------------------------

    def flush(self) -> None:
        """Write all buffered data to disk."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if self.log_events and self._event_rows:
            self._write_csv(self.output_dir / "events.csv",
                            self.EVENT_COLS, self._event_rows)

        if self.log_samples and self._sample_rows:
            self._write_csv(self.output_dir / "samples.csv",
                            self.SAMPLE_COLS, self._sample_rows)

        if self.write_meta:
            self._write_metadata()

    def _write_csv(self, path: pathlib.Path,
                   columns: tuple[str, ...],
                   rows: list[dict[str, Any]]) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def _write_metadata(self) -> None:
        ctx = self.ctx
        # Compute KPIs from completed devices
        completed_devices = list(ctx.completed.items)
        cycle_times = [d.cycle_time for d in completed_devices
                       if d.cycle_time is not None]

        meta: dict[str, Any] = {
            "run_id": self.run_id,
            "seed": self.seed,
            "time_horizon": ctx.cfg.sim.time_horizon,
            "sim_time_reached": ctx.env.now,
            "config": ctx.cfg.to_dict(),
            "kpis": {
                "throughput": len(completed_devices),
                "rejected": len(ctx.reject.items),
                "cycle_time": {
                    "count": len(cycle_times),
                    "mean": float(np.mean(cycle_times)) if cycle_times else None,
                    "median": float(np.median(cycle_times)) if cycle_times else None,
                    "min": float(min(cycle_times)) if cycle_times else None,
                    "max": float(max(cycle_times)) if cycle_times else None,
                    "std": float(np.std(cycle_times)) if cycle_times else None,
                },
                "outputs": ctx.outputs.summary(),
                "final_wip": {
                    qname: len(ctx.queues[qname].items)
                    for qname in ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5")
                },
            },
        }

        path = self.output_dir / "metadata.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, default=str)
