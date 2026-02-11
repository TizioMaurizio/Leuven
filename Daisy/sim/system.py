"""
sim/system.py – Wire together Stores, Resources, and station processes
to build the complete Daisy DES model.

``build_system(env, cfg, bus, rng)`` returns a ``SystemContext`` containing
all stores, resources, output streams, and the list of SimPy processes so
that the caller can simply ``env.run()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import simpy

from sim.entities import EventBus, OutputStreams
from sim import stations


# ---------------------------------------------------------------------------
# Resource bundle  (attribute-access for station code)
# ---------------------------------------------------------------------------

class Resources:
    """Namespace holding every ``PriorityResource`` used in the model."""

    def __init__(self, env: simpy.Environment, cfg: Any):
        res_cfg = cfg.resources
        self.op_feed = simpy.PriorityResource(env, capacity=res_cfg.op_feed.capacity)
        self.scanner = simpy.PriorityResource(env, capacity=res_cfg.scanner.capacity)
        self.m1_fixture = simpy.PriorityResource(env, capacity=res_cfg.m1_fixture.capacity)
        self.m2_cooling_slot = simpy.PriorityResource(env, capacity=res_cfg.m2_cooling_slot.capacity)
        self.op_battery_monitor = simpy.PriorityResource(env, capacity=res_cfg.op_battery_monitor.capacity)
        self.m3_punch = simpy.PriorityResource(env, capacity=res_cfg.m3_punch.capacity)
        self.op_maint = simpy.PriorityResource(env, capacity=res_cfg.op_maint.capacity)
        self.m4_module = simpy.PriorityResource(env, capacity=res_cfg.m4_module.capacity)
        self.op_sort = simpy.PriorityResource(env, capacity=res_cfg.op_sort.capacity)
        self.op_pack = simpy.PriorityResource(env, capacity=res_cfg.op_pack.capacity)

    def utilization_snapshot(self) -> dict[str, dict[str, int]]:
        """Return {resource_name: {in_use, capacity}} for monitoring."""
        snap: dict[str, dict[str, int]] = {}
        for name in ("op_feed", "scanner", "m1_fixture", "m2_cooling_slot",
                      "op_battery_monitor", "m3_punch", "op_maint",
                      "m4_module", "op_sort", "op_pack"):
            r: simpy.PriorityResource = getattr(self, name)
            snap[name] = {"in_use": r.count, "capacity": r.capacity}
        return snap


# ---------------------------------------------------------------------------
# System context – everything the caller needs
# ---------------------------------------------------------------------------

@dataclass
class SystemContext:
    env: simpy.Environment
    cfg: Any
    bus: EventBus
    rng: np.random.Generator
    resources: Resources
    outputs: OutputStreams
    queues: dict[str, simpy.Store]
    reject: simpy.Store
    completed: simpy.Store
    batt_exc: simpy.Store
    jam_exc: simpy.Store
    processes: list[simpy.Process] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_system(env: simpy.Environment, cfg: Any,
                 bus: EventBus, rng: np.random.Generator) -> SystemContext:
    """Instantiate all stores, resources, and processes; return a SystemContext."""

    # -- Queues (finite-capacity Stores) ------------------------------------
    buf = cfg.buffers
    queues: dict[str, simpy.Store] = {
        f"Q{i}": simpy.Store(env, capacity=getattr(buf, f"Q{i}").capacity)
        for i in range(6)
    }
    Q0, Q1, Q2, Q3, Q4, Q5 = (queues[f"Q{i}"] for i in range(6))

    # -- Exception + terminal stores ----------------------------------------
    reject = simpy.Store(env)       # unknown-model rejects
    completed = simpy.Store(env)    # fully processed
    batt_exc = simpy.Store(env)     # battery exception
    jam_exc = simpy.Store(env)      # jam exception

    # -- Resources -----------------------------------------------------------
    res = Resources(env, cfg)

    # -- Outputs -------------------------------------------------------------
    outputs = OutputStreams()

    # -- Processes -----------------------------------------------------------
    procs = [
        env.process(stations.arrivals(env, cfg, Q0, bus, rng)),
        env.process(stations.s1_identify(env, cfg, Q0, Q1, reject, res, bus, rng)),
        env.process(stations.s2_module1(env, cfg, Q1, Q2, res, bus, rng)),
        env.process(stations.s3_module2(env, cfg, Q2, Q3, batt_exc, res, bus, rng)),
        env.process(stations.e2_manual_battery(env, cfg, batt_exc, Q3, res, bus, rng)),
        env.process(stations.s4_module3(env, cfg, Q3, Q4, jam_exc, res, bus, rng)),
        env.process(stations.e3_clear_jam(env, cfg, jam_exc, Q3, Q4, res, bus, rng)),
        env.process(stations.s5_module4(env, cfg, Q4, Q5, outputs, res, bus, rng)),
        env.process(stations.s6_pack_dispatch(env, cfg, Q5, completed, res, bus, rng)),
    ]

    return SystemContext(
        env=env, cfg=cfg, bus=bus, rng=rng,
        resources=res, outputs=outputs,
        queues=queues, reject=reject, completed=completed,
        batt_exc=batt_exc, jam_exc=jam_exc,
        processes=procs,
    )
