"""Simulation runner — wires DES engine + model + supervisor + policy.

This module orchestrates a full simulation run:
  1. Initialise cell state with stations
  2. Generate product arrivals
  3. On each arrival / event, consult supervisor → policy → execute
  4. Collect metrics
  5. Write event log + metrics
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .engine import DESEngine
from .metrics import RunMetrics
from .model import (
    CellState,
    EventType,
    Product,
    ProductPhase,
    Station,
    StationStatus,
)
from .scenarios import Scenario
from .supervisor import Supervisor
from ..holons.baseline import BaselinePolicy
from ..holons.protocol import CoordinationPolicy
from ..config import PROCESSING_TIMES, STATION_NAMES, UncertaintyRegime


class SimulationRunner:
    """Runs one episode of the demanufacturing DES."""

    def __init__(
        self,
        seed: int = 42,
        regime: Optional[UncertaintyRegime] = None,
        policy: Optional[CoordinationPolicy] = None,
        max_steps: Optional[int] = None,
        max_products: int = 30,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.seed = seed
        self.regime = regime or UncertaintyRegime()
        self.policy = policy or BaselinePolicy()
        self.max_steps = max_steps
        self.max_products = max_products
        self.callback = callback  # called for every logged event

        self.rng = random.Random(seed)
        self.engine = DESEngine()
        self.supervisor = Supervisor()
        self.metrics = RunMetrics()
        self.state = CellState()

        self._products_arrived = 0
        self._init_stations()

    # ── Initialisation ────────────────────────────────────────────
    def _init_stations(self) -> None:
        for name in STATION_NAMES:
            self.state.stations[name] = Station(name=name)

    # ── Public API ────────────────────────────────────────────────
    def run(self) -> RunMetrics:
        """Run the full simulation and return collected metrics."""
        # Schedule first product arrival
        self._schedule_arrival()

        self.engine.run(max_steps=self.max_steps)
        return self.metrics

    def step(self) -> Optional[Dict[str, Any]]:
        """Execute a single DES step.  Returns the logged event dict or None."""
        evt = self.engine.step()
        if evt is None:
            return None
        # The callback-based event logging happens inside event handlers
        # Return the latest log entry if any
        if self.metrics.event_log:
            return self.metrics.event_log[-1]
        return None

    def reset(self) -> None:
        """Reset the simulation to initial conditions with the same seed."""
        self.rng = random.Random(self.seed)
        self.engine.reset()
        self.metrics = RunMetrics()
        self.state = CellState()
        self._products_arrived = 0
        self._init_stations()
        self._schedule_arrival()

    # ── Event handlers ────────────────────────────────────────────
    def _schedule_arrival(self) -> None:
        if self._products_arrived >= self.max_products:
            return
        delay = max(0.5, self.rng.gauss(self.regime.arrival_interval, 2.0))
        self.engine.schedule(delay, self._on_arrival)

    def _on_arrival(self, engine: DESEngine, scheduled_event: Any) -> None:
        product = self.state.create_product(
            self.rng, self.regime, arrival_time=engine.now
        )
        self._products_arrived += 1
        self._log(engine.now, EventType.PRODUCT_ARRIVE, product.uid)

        # Route: always go to inspection first
        self._try_start_inspection(engine, product)

        # Schedule next arrival
        self._schedule_arrival()

    def _try_start_inspection(self, engine: DESEngine, product: Product) -> None:
        station = self.state.stations["inspection"]
        if station.is_available():
            station.status = StationStatus.BUSY
            station.current_product = product.uid
            product.phase = ProductPhase.INSPECTION
            self._log(engine.now, EventType.START_INSPECTION, product.uid, "inspection")

            proc_time = self._proc_time("inspection")
            engine.schedule(proc_time, self._on_finish_inspection, product_uid=product.uid)
        else:
            station.queue.append(product.uid)
            self._log(engine.now, "queued_inspection", product.uid, "inspection")

    def _on_finish_inspection(self, engine: DESEngine, scheduled_event: Any) -> None:
        uid = scheduled_event.payload["product_uid"]
        product = self.state.products[uid]
        station = self.state.stations["inspection"]

        # Reveal latent conditions (with sensor noise)
        product.inspected = True
        product.inspection_count += 1
        self.metrics.inspection_count += 1

        # Observation model: reveal truth with possible false negatives
        product.observed["stripped_screw"] = product.latent.stripped_screw
        product.observed["stuck_adhesive"] = product.latent.stuck_adhesive
        product.observed["missing_component"] = product.latent.missing_component
        # Battery risk: sensor may miss it (false negative)
        if product.latent.battery_risk:
            product.observed["battery_risk"] = (
                self.rng.random() >= self.regime.sensor_false_negative
            )
        else:
            product.observed["battery_risk"] = False

        product.phase = ProductPhase.WAITING
        station.status = StationStatus.IDLE
        station.current_product = None

        self._log(
            engine.now,
            EventType.FINISH_INSPECTION,
            uid,
            "inspection",
            observed=product.observed,
        )

        # Record feasibility changes
        if product.observed.get("stripped_screw") or product.observed.get("stuck_adhesive"):
            self.metrics.feasibility_changes += 1

        # Route product
        self._route_product(engine, product)

        # Serve queue
        self._serve_queue(engine, "inspection")

    def _route_product(self, engine: DESEngine, product: Product) -> None:
        """Consult supervisor + policy to decide next action."""
        enabled = self.supervisor.enabled_set(product, self.state)
        if not enabled:
            self.metrics.blocked_ticks += 1
            # Try re-queuing for inspection or escalate
            self._escalate(engine, product)
            return

        chosen = self.policy.decide(product.uid, self.state, enabled)
        if chosen is None:
            self.metrics.blocked_ticks += 1
            self._escalate(engine, product)
            return

        # Verify through gate
        if not self.supervisor.is_safe(chosen, product, self.state):
            self.metrics.forbidden_event_attempts += 1
            self._log(engine.now, "forbidden_attempt", product.uid, detail=str(chosen))
            self._escalate(engine, product)
            return

        # Execute chosen event
        self._execute(engine, chosen, product)

    def _execute(self, engine: DESEngine, event: EventType, product: Product) -> None:
        if event == EventType.START_HAZARD_HANDLING:
            self._start_station(engine, product, "hazard_handling",
                                ProductPhase.HAZARD_HANDLING,
                                self._on_finish_hazard)
        elif event == EventType.START_ROBOT_DISASSEMBLY:
            self._start_station(engine, product, "robot_disassembly",
                                ProductPhase.ROBOT_DISASSEMBLY,
                                self._on_finish_robot)
        elif event == EventType.START_MANUAL_DISASSEMBLY:
            self._start_station(engine, product, "manual_disassembly",
                                ProductPhase.MANUAL_DISASSEMBLY,
                                self._on_finish_manual)
        elif event == EventType.START_INSPECTION:
            self._try_start_inspection(engine, product)
        elif event == EventType.REQUEST_INSPECTION:
            self._try_start_inspection(engine, product)
        elif event == EventType.ESCALATE:
            self._escalate(engine, product)
        else:
            # Finish events are clock-driven, not directly executed here
            pass

    def _start_station(
        self,
        engine: DESEngine,
        product: Product,
        station_name: str,
        phase: ProductPhase,
        finish_callback: Callable,
    ) -> None:
        station = self.state.stations[station_name]
        if not station.is_available():
            station.queue.append(product.uid)
            self._log(engine.now, f"queued_{station_name}", product.uid, station_name)
            return

        station.status = StationStatus.BUSY
        station.current_product = product.uid
        product.phase = phase
        self._log(engine.now, f"start_{station_name}", product.uid, station_name)

        # Check for station failure
        if self.rng.random() < self.regime.station_failure_prob:
            engine.schedule(0.1, self._on_station_failure,
                            station_name=station_name, product_uid=product.uid)
            return

        proc_time = self._proc_time(station_name)
        engine.schedule(proc_time, finish_callback, product_uid=product.uid)

    def _on_finish_hazard(self, engine: DESEngine, scheduled_event: Any) -> None:
        uid = scheduled_event.payload["product_uid"]
        product = self.state.products[uid]
        station = self.state.stations["hazard_handling"]

        product.hazard_cleared = True
        product.phase = ProductPhase.WAITING
        self._release_station(station)
        self._log(engine.now, EventType.FINISH_HAZARD_HANDLING, uid, "hazard_handling")

        self._route_product(engine, product)
        self._serve_queue(engine, "hazard_handling")

    def _on_finish_robot(self, engine: DESEngine, scheduled_event: Any) -> None:
        uid = scheduled_event.payload["product_uid"]
        product = self.state.products[uid]
        station = self.state.stations["robot_disassembly"]

        # Exception: discover stripped screw mid-disassembly
        if product.latent.stripped_screw and not product.observed.get("stripped_screw"):
            product.observed["stripped_screw"] = True
            self.metrics.feasibility_changes += 1
            self.metrics.plan_invalidations += 1
            self._log(engine.now, EventType.EXCEPTION_STRIPPED_SCREW, uid, "robot_disassembly")
            product.phase = ProductPhase.WAITING
            self._release_station(station)
            self._route_product(engine, product)
            self._serve_queue(engine, "robot_disassembly")
            return

        # Success
        product.phase = ProductPhase.WAITING
        self._release_station(station)
        self._log(engine.now, EventType.FINISH_ROBOT_DISASSEMBLY, uid, "robot_disassembly")

        self._complete_product(engine, product)
        self._serve_queue(engine, "robot_disassembly")

    def _on_finish_manual(self, engine: DESEngine, scheduled_event: Any) -> None:
        uid = scheduled_event.payload["product_uid"]
        product = self.state.products[uid]
        station = self.state.stations["manual_disassembly"]

        # Manual can handle stripped screws but stuck adhesive may cause issue
        if product.latent.stuck_adhesive and not product.observed.get("stuck_adhesive"):
            product.observed["stuck_adhesive"] = True
            self.metrics.feasibility_changes += 1
            self.metrics.plan_invalidations += 1
            self._log(engine.now, EventType.EXCEPTION_STUCK_ADHESIVE, uid, "manual_disassembly")
            # Continue anyway — manual worker adapts (with extra time)
            extra = self._proc_time("manual_disassembly") * 0.5
            self.engine.schedule(extra, self._on_finish_manual_recovery, product_uid=uid)
            return

        product.phase = ProductPhase.WAITING
        self._release_station(station)
        self._log(engine.now, EventType.FINISH_MANUAL_DISASSEMBLY, uid, "manual_disassembly")

        self._complete_product(engine, product)
        self._serve_queue(engine, "manual_disassembly")

    def _on_finish_manual_recovery(self, engine: DESEngine, scheduled_event: Any) -> None:
        uid = scheduled_event.payload["product_uid"]
        product = self.state.products[uid]
        station = self.state.stations["manual_disassembly"]

        product.phase = ProductPhase.WAITING
        self._release_station(station)
        self._log(engine.now, "finish_manual_recovery", uid, "manual_disassembly")

        self._complete_product(engine, product)
        self._serve_queue(engine, "manual_disassembly")

    def _on_station_failure(self, engine: DESEngine, scheduled_event: Any) -> None:
        station_name = scheduled_event.payload["station_name"]
        uid = scheduled_event.payload["product_uid"]
        station = self.state.stations[station_name]
        product = self.state.products[uid]

        station.status = StationStatus.FAILED
        self._log(engine.now, EventType.STATION_FAILURE, uid, station_name)

        # Schedule repair
        repair_time = self.rng.uniform(5.0, 15.0)
        engine.schedule(repair_time, self._on_station_repair,
                        station_name=station_name, product_uid=uid)

    def _on_station_repair(self, engine: DESEngine, scheduled_event: Any) -> None:
        station_name = scheduled_event.payload["station_name"]
        uid = scheduled_event.payload["product_uid"]
        station = self.state.stations[station_name]
        product = self.state.products[uid]

        station.status = StationStatus.IDLE
        station.current_product = None
        product.phase = ProductPhase.WAITING
        self._log(engine.now, EventType.STATION_REPAIR, uid, station_name)

        # Re-route product
        self._route_product(engine, product)
        self._serve_queue(engine, station_name)

    def _complete_product(self, engine: DESEngine, product: Product) -> None:
        """Mark product as complete and record metrics."""
        product.phase = ProductPhase.COMPLETE
        product.completion_time = engine.now
        self.state.completed_products.append(product.uid)
        self.metrics.products_completed += 1
        cycle_time = engine.now - product.arrival_time
        self.metrics.total_time_in_system += cycle_time
        self._log(engine.now, EventType.PRODUCT_COMPLETE, product.uid,
                  cycle_time=round(cycle_time, 4))

    def _escalate(self, engine: DESEngine, product: Product) -> None:
        product.phase = ProductPhase.ESCALATED
        product.escalated = True
        self.state.escalated_products.append(product.uid)
        self.metrics.escalations += 1
        self._log(engine.now, EventType.ESCALATE, product.uid)

    # ── Helpers ───────────────────────────────────────────────────
    def _release_station(self, station: Station) -> None:
        station.status = StationStatus.IDLE
        station.current_product = None

    def _serve_queue(self, engine: DESEngine, station_name: str) -> None:
        """If station has queued products, start next one."""
        station = self.state.stations[station_name]
        if station.queue and station.is_available():
            uid = station.queue.pop(0)
            product = self.state.products.get(uid)
            if product and product.phase in (ProductPhase.WAITING, ProductPhase.INSPECTION):
                if station_name == "inspection":
                    self._try_start_inspection(engine, product)
                else:
                    self._route_product(engine, product)

    def _proc_time(self, station_name: str) -> float:
        mean, std = PROCESSING_TIMES.get(station_name, (5.0, 1.0))
        return max(0.1, self.rng.gauss(mean, std))

    def _log(
        self,
        time: float,
        event_type: Any,
        product_uid: Optional[int] = None,
        station: Optional[str] = None,
        **extra: Any,
    ) -> None:
        et = event_type.value if hasattr(event_type, "value") else str(event_type)
        entry = self.metrics.log_event(time, et, product_uid, station, **extra)
        if self.callback:
            self.callback(entry)

    # ── Persistence ───────────────────────────────────────────────
    def write_results(self, run_dir: str | Path) -> None:
        """Write events.jsonl and metrics.json to *run_dir*."""
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)

        events_path = run_dir / "events.jsonl"
        with open(events_path, "w") as f:
            for entry in self.metrics.event_log:
                f.write(json.dumps(entry) + "\n")

        metrics_path = run_dir / "metrics.json"
        with open(metrics_path, "w") as f:
            f.write(self.metrics.to_json())
