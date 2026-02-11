"""
sim/model.py – Domain entities and resources.

* ``Laptop`` – the flowing entity with state & history.
* ``InstructionDB`` – the growing knowledge base.
* ``Resource`` – a capacity-limited station with FIFO queue.
* ``Recognizer`` – stochastic model-matching helper.
* ``World`` – aggregate root that owns everything.
"""

from __future__ import annotations

import json
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sim.distributions import DistFn, make_dist, exponential


# ── Laptop ───────────────────────────────────────────────────────────────

@dataclass
class StateInterval:
    state: str
    t_start: float
    t_end: float = -1.0


@dataclass
class Laptop:
    id: int
    true_model_id: int
    state: str = "S0_ARRIVAL"
    history: list[StateInterval] = field(default_factory=list)
    flags: dict = field(default_factory=lambda: {
        "recognized": False,
        "auto_success": False,
        "new_model": False,
        "new_model_registered": False,
    })
    t_arrival: float = 0.0
    t_departure: float = -1.0

    # helpers
    def enter_state(self, state: str, t: float) -> None:
        if self.history and self.history[-1].t_end < 0:
            self.history[-1].t_end = t
        self.state = state
        self.history.append(StateInterval(state=state, t_start=t))

    def finish_state(self, t: float) -> None:
        if self.history and self.history[-1].t_end < 0:
            self.history[-1].t_end = t

    @property
    def cycle_time(self) -> float:
        if self.t_departure < 0:
            return -1.0
        return self.t_departure - self.t_arrival


# ── InstructionDB ────────────────────────────────────────────────────────

@dataclass
class InstructionPackage:
    screw_coords_quality: float = 1.0  # placeholder


class InstructionDB:
    def __init__(self) -> None:
        self.known_models: dict[int, InstructionPackage] = {}
        self._registration_log: list[tuple[float, int]] = []  # (sim_time, model_id)

    def is_known(self, model_id: int) -> bool:
        return model_id in self.known_models

    def register(self, model_id: int, pkg: InstructionPackage | None = None,
                 t: float = 0.0) -> None:
        if model_id not in self.known_models:
            self.known_models[model_id] = pkg or InstructionPackage()
            self._registration_log.append((t, model_id))

    def size(self) -> int:
        return len(self.known_models)

    def seed_models(self, count: int) -> None:
        """Pre-populate the DB with *count* known models (ids 0..count-1)."""
        for i in range(count):
            self.register(i, InstructionPackage(screw_coords_quality=0.9))


# ── Recognizer ───────────────────────────────────────────────────────────

class Recognizer:
    """Stochastic model recognition with learning."""

    def __init__(self, p_known: float = 0.97, p_unknown_false: float = 0.03):
        self.p_known = p_known
        self.p_unknown_false = p_unknown_false

    def match(self, model_id: int, db: InstructionDB,
              rng: random.Random) -> bool:
        if db.is_known(model_id):
            return rng.random() < self.p_known
        else:
            return rng.random() < self.p_unknown_false


# ── Resource ─────────────────────────────────────────────────────────────

@dataclass
class ResourceRequest:
    laptop_id: int
    on_granted: Callable  # (sim, laptop_id) -> None
    t_requested: float = 0.0


class Resource:
    """Capacity-limited resource with FIFO queue."""

    def __init__(self, name: str, capacity: int = 1):
        self.name = name
        self.capacity = capacity
        self.busy: int = 0
        self.queue: deque[ResourceRequest] = deque()
        self._serving: set[int] = set()  # laptop ids currently using
        # stats
        self.total_busy_time: float = 0.0
        self._last_busy_change: float = 0.0
        self._busy_integral: float = 0.0

    def request(self, laptop_id: int, now: float,
                on_granted: Callable) -> bool:
        """Try to acquire.  Returns True if granted immediately."""
        if self.busy < self.capacity:
            self.busy += 1
            self._serving.add(laptop_id)
            self._record_busy(now)
            on_granted(laptop_id)
            return True
        else:
            self.queue.append(ResourceRequest(
                laptop_id=laptop_id, on_granted=on_granted, t_requested=now))
            return False

    def release(self, laptop_id: int, now: float) -> Optional[ResourceRequest]:
        """Release and serve next in queue if any.  Returns that request or
        None."""
        if laptop_id in self._serving:
            self._serving.discard(laptop_id)
            self.busy -= 1
            self._record_busy(now)
        if self.queue and self.busy < self.capacity:
            req = self.queue.popleft()
            self.busy += 1
            self._serving.add(req.laptop_id)
            self._record_busy(now)
            return req
        return None

    @property
    def queue_length(self) -> int:
        return len(self.queue)

    @property
    def utilization(self) -> float:
        if self._last_busy_change <= 0:
            return 0.0
        return self._busy_integral / self._last_busy_change

    def _record_busy(self, now: float) -> None:
        dt = now - self._last_busy_change
        if dt > 0:
            self._busy_integral += self.busy * dt
        self._last_busy_change = now

    @property
    def is_idle(self) -> bool:
        return self.busy == 0


# ── World ────────────────────────────────────────────────────────────────

class World:
    """Aggregate root: holds entities, resources, config, distributions."""

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.db = InstructionDB()
        self.db.seed_models(cfg.get("initial_known_models", 5))

        cap = cfg.get("capacities", {})
        self.resources: dict[str, Resource] = {
            "camera":    Resource("Camera",    cap.get("camera_count", 1)),
            "retrieval": Resource("Retrieval", cap.get("retrieval_engines", 1)),
            "robot":     Resource("RobotCell", cap.get("robot_cells", 1)),
            "operator":  Resource("Operator",  cap.get("operator_count", 2)),
        }

        self.laptops: dict[int, Laptop] = {}
        self._next_laptop_id: int = 0

        # recogniser
        probs = cfg.get("probabilities", {})
        self.recognizer = Recognizer(
            p_known=probs.get("p_known_recognition", 0.97),
            p_unknown_false=probs.get("p_unknown_false_match", 0.03),
        )

        # distributions (callable samplers)
        dists_cfg = cfg.get("distributions", {})
        self.dist: dict[str, DistFn] = {}
        for name, dcfg in dists_cfg.items():
            self.dist[name] = make_dist(dcfg)
        # inter-arrival time
        lam = cfg.get("arrival_rate_per_min", 0.5) / 60.0  # per second
        self.dist["inter_arrival"] = exponential(lam)

        # mode
        self.mode: str = cfg.get("mode", "waterjet")

        # model-id generation
        self.target_unique = cfg.get("target_unique_models", 50)
        self.zipf_s = cfg.get("zipf_s", 1.2)
        self.p_novel_base = cfg.get("p_novel_model_base", 0.30)
        self._novel_counter = self.db.size()  # next novel id

    # -- laptop factory ----------------------------------------------------

    def create_laptop(self, t: float, rng: random.Random) -> Laptop:
        lid = self._next_laptop_id
        self._next_laptop_id += 1
        model_id = self._pick_model_id(rng)
        laptop = Laptop(id=lid, true_model_id=model_id, t_arrival=t)
        laptop.enter_state("S0_ARRIVAL", t)
        self.laptops[lid] = laptop
        return laptop

    def _pick_model_id(self, rng: random.Random) -> int:
        """Zipf over known + chance of novel model."""
        coverage = min(1.0, self.db.size() / max(1, self.target_unique))
        p_novel = self.p_novel_base * (1.0 - coverage)
        if rng.random() < p_novel:
            mid = self._novel_counter
            self._novel_counter += 1
            return mid
        # Zipf over known ids
        n = max(self.db.size(), 1)
        weights = [1.0 / (k ** self.zipf_s) for k in range(1, n + 1)]
        chosen_index = rng.choices(range(n), weights=weights, k=1)[0]
        return list(self.known_model_ids)[chosen_index] if self.known_model_ids else 0

    @property
    def known_model_ids(self) -> set[int]:
        return set(self.db.known_models.keys())

    def reset(self, cfg: dict | None = None) -> None:
        if cfg:
            self.__init__(cfg)  # type: ignore[misc]
        else:
            self.__init__(self.cfg)  # type: ignore[misc]
