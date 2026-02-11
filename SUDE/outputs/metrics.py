"""
outputs/metrics.py – Incremental statistics, histograms, and export.

``MetricsCollector`` accumulates data during the run and can export
a JSON summary and CSV traces.
"""

from __future__ import annotations

import csv
import json
import os
import statistics
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sim.model import Laptop, World


@dataclass
class MetricsCollector:
    """Collects simulation-wide and per-laptop metrics."""

    # counters
    total_arrivals: int = 0
    total_departures: int = 0
    recognized_count: int = 0
    retrieval_attempts: int = 0
    automation_success_count: int = 0
    automation_attempts: int = 0
    onboarding_count: int = 0

    # time-series snapshots (sampled periodically)
    ts_times: list[float] = field(default_factory=list)
    ts_wip: list[int] = field(default_factory=list)
    ts_db_size: list[int] = field(default_factory=list)
    ts_queue_camera: list[int] = field(default_factory=list)
    ts_queue_retrieval: list[int] = field(default_factory=list)
    ts_queue_robot: list[int] = field(default_factory=list)
    ts_queue_operator: list[int] = field(default_factory=list)

    # per-laptop cycle times
    cycle_times: list[float] = field(default_factory=list)

    # departures over time (for throughput)
    departure_times: list[float] = field(default_factory=list)

    # DB size over time
    db_size_log: list[tuple[float, int]] = field(default_factory=list)

    # recognition ratio over time (rolling window)
    _retrieval_log: list[tuple[float, bool]] = field(default_factory=list)

    # ── recording ────────────────────────────────────────────────────────

    def record_arrival(self, t: float) -> None:
        self.total_arrivals += 1

    def record_departure(self, t: float, laptop: "Laptop") -> None:
        self.total_departures += 1
        ct = laptop.cycle_time
        if ct > 0:
            self.cycle_times.append(ct)
        self.departure_times.append(t)

    def record_retrieval(self, t: float, recognized: bool) -> None:
        self.retrieval_attempts += 1
        if recognized:
            self.recognized_count += 1
        self._retrieval_log.append((t, recognized))

    def record_automation(self, t: float, success: bool) -> None:
        self.automation_attempts += 1
        if success:
            self.automation_success_count += 1

    def record_onboarding(self, t: float, db_size: int) -> None:
        self.onboarding_count += 1
        self.db_size_log.append((t, db_size))

    def snapshot(self, t: float, world: "World") -> None:
        """Take a periodic snapshot of queue lengths and WIP."""
        self.ts_times.append(t)
        wip = sum(
            1 for lp in world.laptops.values()
            if lp.state not in ("DEPARTED",)
        )
        self.ts_wip.append(wip)
        self.ts_db_size.append(world.db.size())
        self.ts_queue_camera.append(world.resources["camera"].queue_length)
        self.ts_queue_retrieval.append(world.resources["retrieval"].queue_length)
        self.ts_queue_robot.append(world.resources["robot"].queue_length)
        self.ts_queue_operator.append(world.resources["operator"].queue_length)

    # ── computed ─────────────────────────────────────────────────────────

    @property
    def throughput_per_hour(self) -> float:
        if not self.departure_times:
            return 0.0
        span = self.departure_times[-1] - (self.departure_times[0] if len(self.departure_times) > 1 else 0)
        if span <= 0:
            return 0.0
        return self.total_departures / (span / 3600.0)

    @property
    def retrieval_ratio(self) -> float:
        if self.retrieval_attempts == 0:
            return 0.0
        return self.recognized_count / self.retrieval_attempts

    @property
    def automation_success_ratio(self) -> float:
        if self.automation_attempts == 0:
            return 0.0
        return self.automation_success_count / self.automation_attempts

    @property
    def avg_cycle_time(self) -> float:
        return statistics.mean(self.cycle_times) if self.cycle_times else 0.0

    @property
    def p50_cycle_time(self) -> float:
        return statistics.median(self.cycle_times) if self.cycle_times else 0.0

    @property
    def p95_cycle_time(self) -> float:
        if not self.cycle_times:
            return 0.0
        s = sorted(self.cycle_times)
        idx = int(0.95 * len(s))
        return s[min(idx, len(s) - 1)]

    def current_wip(self, world: "World") -> int:
        return sum(
            1 for lp in world.laptops.values()
            if lp.state not in ("DEPARTED",)
        )

    # ── rolling retrieval ratio (last N) ─────────────────────────────────

    def rolling_retrieval_ratio(self, n: int = 50) -> float:
        if not self._retrieval_log:
            return 0.0
        window = self._retrieval_log[-n:]
        return sum(1 for _, r in window if r) / len(window)

    # ── export ───────────────────────────────────────────────────────────

    def summary_dict(self, cfg: dict, seed: int, sim_time: float) -> dict:
        return {
            "seed": seed,
            "sim_time": sim_time,
            "config": cfg,
            "total_arrivals": self.total_arrivals,
            "total_departures": self.total_departures,
            "throughput_per_hour": round(self.throughput_per_hour, 2),
            "retrieval_ratio": round(self.retrieval_ratio, 4),
            "automation_success_ratio": round(self.automation_success_ratio, 4),
            "avg_cycle_time": round(self.avg_cycle_time, 2),
            "p50_cycle_time": round(self.p50_cycle_time, 2),
            "p95_cycle_time": round(self.p95_cycle_time, 2),
            "onboarding_count": self.onboarding_count,
        }

    def export_summary(self, path: str, cfg: dict, seed: int,
                       sim_time: float) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.summary_dict(cfg, seed, sim_time), f, indent=2)

    def export_laptop_traces(self, path: str, world: "World") -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "laptop_id", "true_model_id", "recognized", "auto_success",
                "new_model", "new_model_registered", "t_arrival",
                "t_departure", "cycle_time", "state_history",
            ])
            for laptop in sorted(world.laptops.values(), key=lambda l: l.id):
                history_str = " | ".join(
                    f"{si.state}[{si.t_start:.1f}-{si.t_end:.1f}]"
                    for si in laptop.history
                )
                writer.writerow([
                    laptop.id,
                    laptop.true_model_id,
                    laptop.flags.get("recognized", ""),
                    laptop.flags.get("auto_success", ""),
                    laptop.flags.get("new_model", ""),
                    laptop.flags.get("new_model_registered", ""),
                    f"{laptop.t_arrival:.2f}",
                    f"{laptop.t_departure:.2f}" if laptop.t_departure >= 0 else "",
                    f"{laptop.cycle_time:.2f}" if laptop.cycle_time >= 0 else "",
                    history_str,
                ])

    def export_time_series(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "sim_time", "wip", "db_size",
                "q_camera", "q_retrieval", "q_robot", "q_operator",
            ])
            for i, t in enumerate(self.ts_times):
                writer.writerow([
                    f"{t:.1f}",
                    self.ts_wip[i],
                    self.ts_db_size[i],
                    self.ts_queue_camera[i],
                    self.ts_queue_retrieval[i],
                    self.ts_queue_robot[i],
                    self.ts_queue_operator[i],
                ])
