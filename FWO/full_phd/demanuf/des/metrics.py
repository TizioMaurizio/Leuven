"""Metrics collection and computation for DES runs.

Captures the HoDeSU-Bench metrics (PAPER_1 §V-F):
  - Correctness: safety violations, blocked-event attempts, deadlocks
  - Adaptation: plan invalidations, feasibility changes, escalations
  - Performance: throughput, cycle time, utilisation
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RunMetrics:
    """Accumulator for a single simulation run."""

    # ── Correctness ─────────────────────────
    safety_violations: int = 0
    forbidden_event_attempts: int = 0
    deadlocks: int = 0

    # ── Adaptation ──────────────────────────
    plan_invalidations: int = 0
    feasibility_changes: int = 0
    escalations: int = 0
    inspection_count: int = 0

    # ── Performance ─────────────────────────
    products_completed: int = 0
    total_time_in_system: float = 0.0
    blocked_ticks: int = 0

    # ── Station utilisation tracking ────────
    station_busy_time: Dict[str, float] = field(default_factory=dict)

    # ── Raw events for tracing ──────────────
    event_log: List[Dict[str, Any]] = field(default_factory=list)

    # ── Derived ─────────────────────────────
    @property
    def throughput(self) -> float:
        if not self.event_log:
            return 0.0
        end_time = self.event_log[-1].get("time", 1.0)
        return self.products_completed / max(end_time, 1e-9)

    @property
    def avg_cycle_time(self) -> float:
        if self.products_completed == 0:
            return 0.0
        return self.total_time_in_system / self.products_completed

    def log_event(
        self,
        time: float,
        event_type: str,
        product_uid: Optional[int] = None,
        station: Optional[str] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "time": round(time, 6),
            "event": event_type,
        }
        if product_uid is not None:
            entry["product"] = product_uid
        if station is not None:
            entry["station"] = station
        entry.update(extra)
        self.event_log.append(entry)
        return entry

    def summary(self) -> Dict[str, Any]:
        return {
            "products_completed": self.products_completed,
            "throughput": round(self.throughput, 6),
            "avg_cycle_time": round(self.avg_cycle_time, 4),
            "safety_violations": self.safety_violations,
            "forbidden_event_attempts": self.forbidden_event_attempts,
            "deadlocks": self.deadlocks,
            "escalations": self.escalations,
            "inspection_count": self.inspection_count,
            "blocked_ticks": self.blocked_ticks,
            "plan_invalidations": self.plan_invalidations,
            "feasibility_changes": self.feasibility_changes,
            "station_busy_time": {
                k: round(v, 4) for k, v in self.station_busy_time.items()
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.summary(), indent=2)
