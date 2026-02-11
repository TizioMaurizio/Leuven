"""
sim/stations.py – SimPy process functions for every station and
exception handler in the Daisy pipeline.

Each function is a SimPy generator that loops forever, pulling devices
from its input Store, processing them (with resource contention), and
pushing them to the next Store.

Naming convention follows the spec:
  S0  Arrival/Batching
  S1  Infeed + Scan/Identify
  S2  Module 1  (fixture + display separation)
  S3  Module 2  (−80 °C cooling + battery removal)
  E2  Manual battery handling
  S4  Module 3  (punch-out screws/modules)
  E3  Jam clear / manual intervention
  S5  Module 4  (rotating scrape + screen + human sorting)
  S6  Pack / Label / Dispatch
"""

from __future__ import annotations

from typing import Any

import simpy

from sim.dists import sample, sample_int, bernoulli, sample_outputs
from sim.entities import Device, EventBus, OutputStreams, ev, qput, qget

import numpy as np


# ======================================================================
# S0 – Arrivals (bin arrivals)
# ======================================================================

def arrivals(env: simpy.Environment, cfg: Any, Q0: simpy.Store,
             bus: EventBus, rng: np.random.Generator) -> Any:
    """Generate devices in bins and place them into Q0."""
    device_id = 0
    while env.now < cfg.sim.time_horizon:
        yield env.timeout(sample(cfg.arrival.bin_interarrival, rng))
        n = sample_int(cfg.arrival.bin_size, rng)
        for _ in range(n):
            d = Device(device_id=device_id, arrival_time=env.now)
            bus.emit(ev(env, d, "ARRIVAL_BIN", "S0"))
            yield Q0.put(d)
            bus.emit(qput(env, d, "Q0"))
            device_id += 1


# ======================================================================
# S1 – Infeed + Scan / Identify
# ======================================================================

def s1_identify(env: simpy.Environment, cfg: Any,
                Q0: simpy.Store, Q1: simpy.Store, reject: simpy.Store,
                res: Any, bus: EventBus, rng: np.random.Generator) -> Any:
    while True:
        d: Device = yield Q0.get()
        bus.emit(qget(env, d, "Q0"))

        # Human feeds device
        with res.op_feed.request(priority=1) as req:
            yield req
            yield env.timeout(sample(cfg.S1.feed_time, rng))

        # Scanner identifies
        with res.scanner.request(priority=1) as req:
            yield req
            bus.emit(ev(env, d, "IDENTIFY_START", "S1"))
            yield env.timeout(sample(cfg.S1.scan_time, rng))
            bus.emit(ev(env, d, "IDENTIFY_END", "S1"))

        # Exception: unknown model → reject
        if bernoulli(cfg.S1.p_unknown_model, rng):
            d.model_class = "unknown"
            bus.emit(ev(env, d, "UNKNOWN_MODEL", "S1"))
            yield reject.put(d)
            continue

        d.model_class = "supported"
        yield Q1.put(d)
        bus.emit(qput(env, d, "Q1"))


# ======================================================================
# S2 – Module 1: Fixture + Display separation
# ======================================================================

def s2_module1(env: simpy.Environment, cfg: Any,
               Q1: simpy.Store, Q2: simpy.Store,
               res: Any, bus: EventBus, rng: np.random.Generator) -> Any:
    while True:
        d: Device = yield Q1.get()
        bus.emit(qget(env, d, "Q1"))

        with res.m1_fixture.request(priority=1) as req:
            yield req
            bus.emit(ev(env, d, "M1_START", "S2"))
            yield env.timeout(sample(cfg.S2.m1_time, rng))
            bus.emit(ev(env, d, "M1_END", "S2"))

        yield Q2.put(d)
        bus.emit(qput(env, d, "Q2"))


# ======================================================================
# S3 – Module 2: −80 °C cooling + battery removal
# ======================================================================

def s3_module2(env: simpy.Environment, cfg: Any,
               Q2: simpy.Store, Q3: simpy.Store, batt_exc: simpy.Store,
               res: Any, bus: EventBus, rng: np.random.Generator) -> Any:
    while True:
        d: Device = yield Q2.get()
        bus.emit(qget(env, d, "Q2"))

        with res.m2_cooling_slot.request(priority=1) as req:
            yield req
            bus.emit(ev(env, d, "M2_START", "S3", extra={"cooling": "-80C"}))
            yield env.timeout(sample(cfg.S3.cool_remove_time, rng))

            if bernoulli(cfg.S3.p_battery_issue, rng):
                d.battery_state = "issue"
                d.exceptions.append("battery_issue")
                bus.emit(ev(env, d, "BATTERY_ISSUE", "S3"))
                yield batt_exc.put(d)
                continue

            bus.emit(ev(env, d, "M2_END", "S3"))

        yield Q3.put(d)
        bus.emit(qput(env, d, "Q3"))


# ======================================================================
# E2 – Manual battery handling (human monitors / retrieves batteries)
# ======================================================================

def e2_manual_battery(env: simpy.Environment, cfg: Any,
                      batt_exc: simpy.Store, Q3: simpy.Store,
                      res: Any, bus: EventBus,
                      rng: np.random.Generator) -> Any:
    while True:
        d: Device = yield batt_exc.get()

        with res.op_battery_monitor.request(priority=0) as req:
            yield req
            bus.emit(ev(env, d, "MANUAL_BATT_START", "E2"))
            yield env.timeout(sample(cfg.E2.manual_battery_time, rng))
            bus.emit(ev(env, d, "MANUAL_BATT_END", "E2"))

        yield Q3.put(d)
        bus.emit(qput(env, d, "Q3"))


# ======================================================================
# S4 – Module 3: Punch-out screws / modules
# ======================================================================

def s4_module3(env: simpy.Environment, cfg: Any,
               Q3: simpy.Store, Q4: simpy.Store, jam_exc: simpy.Store,
               res: Any, bus: EventBus, rng: np.random.Generator) -> Any:
    while True:
        d: Device = yield Q3.get()
        bus.emit(qget(env, d, "Q3"))

        with res.m3_punch.request(priority=1) as req:
            yield req
            bus.emit(ev(env, d, "M3_START", "S4"))
            yield env.timeout(sample(cfg.S4.punch_time, rng))

            if bernoulli(cfg.S4.p_jam, rng):
                d.exceptions.append("jam")
                bus.emit(ev(env, d, "JAM", "S4"))
                yield jam_exc.put(d)
                continue

            bus.emit(ev(env, d, "M3_END", "S4"))

        yield Q4.put(d)
        bus.emit(qput(env, d, "Q4"))


# ======================================================================
# E3 – Jam clear + retry policy
# ======================================================================

def e3_clear_jam(env: simpy.Environment, cfg: Any,
                 jam_exc: simpy.Store, Q3: simpy.Store, Q4: simpy.Store,
                 res: Any, bus: EventBus, rng: np.random.Generator) -> Any:
    while True:
        d: Device = yield jam_exc.get()

        with res.op_maint.request(priority=0) as req:
            yield req
            bus.emit(ev(env, d, "JAM_CLEAR_START", "E3"))
            yield env.timeout(sample(cfg.E3.clear_time, rng))
            bus.emit(ev(env, d, "JAM_CLEAR_END", "E3"))

        policy = getattr(cfg.E3, "retry_policy", "retry_S4")
        if policy == "retry_S4":
            yield Q3.put(d)
            bus.emit(qput(env, d, "Q3"))
        else:  # retry_after_clear → skip S4
            yield Q4.put(d)
            bus.emit(qput(env, d, "Q4"))


# ======================================================================
# S5 – Module 4: Rotating scrape + screen + human sorting
# ======================================================================

def s5_module4(env: simpy.Environment, cfg: Any,
               Q4: simpy.Store, Q5: simpy.Store,
               outputs: OutputStreams,
               res: Any, bus: EventBus, rng: np.random.Generator) -> Any:
    while True:
        d: Device = yield Q4.get()
        bus.emit(qget(env, d, "Q4"))

        # Need both the machine and the human sorter
        req_m = res.m4_module.request(priority=1)
        req_s = res.op_sort.request(priority=1)
        yield req_m & req_s

        bus.emit(ev(env, d, "M4_START", "S5"))
        yield env.timeout(sample(cfg.S5.m4_time, rng))
        bus.emit(ev(env, d, "M4_END", "S5"))

        res.m4_module.release(req_m)
        res.op_sort.release(req_s)

        # Generate output fractions
        d.outputs = sample_outputs(cfg.outputs, d, rng)
        outputs.record(d)

        yield Q5.put(d)
        bus.emit(qput(env, d, "Q5"))


# ======================================================================
# S6 – Pack / Label / Dispatch
# ======================================================================

def s6_pack_dispatch(env: simpy.Environment, cfg: Any,
                     Q5: simpy.Store, completed: simpy.Store,
                     res: Any, bus: EventBus,
                     rng: np.random.Generator) -> Any:
    while True:
        d: Device = yield Q5.get()
        bus.emit(qget(env, d, "Q5"))

        with res.op_pack.request(priority=1) as req:
            yield req
            bus.emit(ev(env, d, "PACK_START", "S6"))
            yield env.timeout(sample(cfg.S6.pack_time, rng))
            bus.emit(ev(env, d, "PACK_END", "S6"))

        bus.emit(ev(env, d, "DISPATCHED", "S6",
                     extra={"outputs": d.outputs}))
        yield completed.put(d)
