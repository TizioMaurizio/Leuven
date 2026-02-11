# ctpn_raise_sim.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple, Optional
import heapq
import itertools
import random

Time = float


# ---------------------------
# Core CTPN data structures
# ---------------------------

@dataclass(order=True)
class Event:
    time: Time
    seq: int
    kind: str = field(compare=False)     # "inject" | "complete" | "scan"
    payload: Any = field(compare=False)


@dataclass(frozen=True)
class Token:
    value: Any
    t_available: Time = 0.0             # when token becomes consumable


@dataclass
class Place:
    name: str
    tokens: List[Token] = field(default_factory=list)

    def put(self, tok: Token) -> None:
        self.tokens.append(tok)

    def take(self, now: Time, predicate: Callable[[Token], bool], count: int) -> Optional[List[Token]]:
        """Remove and return 'count' tokens that are available at 'now' and satisfy predicate."""
        idxs: List[int] = []
        for i, t in enumerate(self.tokens):
            if t.t_available <= now and predicate(t):
                idxs.append(i)
                if len(idxs) == count:
                    break
        if len(idxs) < count:
            return None

        taken: List[Token] = []
        for i in reversed(idxs):
            taken.append(self.tokens.pop(i))
        taken.reverse()
        return taken


@dataclass
class ResourcePool:
    name: str
    capacity: int
    in_use: int = 0
    busy_time: float = 0.0
    last_t: float = 0.0

    def update(self, now: float) -> None:
        dt = now - self.last_t
        if dt > 0:
            self.busy_time += dt * self.in_use
            self.last_t = now

    def can_acquire(self, k: int = 1) -> bool:
        return self.in_use + k <= self.capacity

    def acquire(self, now: float, k: int = 1) -> bool:
        self.update(now)
        if not self.can_acquire(k):
            return False
        self.in_use += k
        return True

    def release(self, now: float, k: int = 1) -> None:
        self.update(now)
        self.in_use -= k
        if self.in_use < 0:
            raise RuntimeError(f"Resource {self.name} underflow")


@dataclass
class Transition:
    name: str
    # (place_name, predicate, count)
    inputs: List[Tuple[str, Callable[[Token], bool], int]]
    # binding -> bool
    guard: Callable[[Dict[str, Any]], bool]
    # binding -> seconds
    delay: Callable[[Dict[str, Any]], float]
    # (place_name, producer(binding)->list[Token])
    outputs: List[Tuple[str, Callable[[Dict[str, Any]], List[Token]]]]
    # resource_name -> units
    resources: Dict[str, int] = field(default_factory=dict)
    # higher fires first
    priority: int = 0


class CTPNSim:
    def __init__(self, places: Dict[str, Place], transitions: List[Transition], resources: Dict[str, ResourcePool]):
        self.places = places
        self.transitions = sorted(transitions, key=lambda t: (-t.priority, t.name))
        self.resources = resources

        self.now: float = 0.0
        self.events: List[Event] = []
        self._seq = itertools.count()

    def schedule(self, t: float, kind: str, payload: Any) -> None:
        heapq.heappush(self.events, Event(t, next(self._seq), kind, payload))

    def inject(self, t: float, place: str, token_value: Any) -> None:
        self.schedule(t, "inject", (place, token_value))

    def _resources_ok(self, tr: Transition) -> bool:
        return all(self.resources[r].can_acquire(k) for r, k in tr.resources.items())

    def _try_fire(self, tr: Transition) -> bool:
        if not self._resources_ok(tr):
            return False

        taken: Dict[str, List[Token]] = {}
        for place_name, pred, cnt in tr.inputs:
            got = self.places[place_name].take(self.now, pred, cnt)
            if got is None:
                # rollback
                for pn, toks in taken.items():
                    self.places[pn].tokens = toks + self.places[pn].tokens
                return False
            taken[place_name] = got

        binding: Dict[str, Any] = {"t_start": self.now, "consumed": taken}

        if not tr.guard(binding):
            for pn, toks in taken.items():
                self.places[pn].tokens = toks + self.places[pn].tokens
            return False

        for r, k in tr.resources.items():
            if not self.resources[r].acquire(self.now, k):
                # rollback (rare if _resources_ok is true, but keep it safe)
                for pn, toks in taken.items():
                    self.places[pn].tokens = toks + self.places[pn].tokens
                for rr, kk in tr.resources.items():
                    if rr == r:
                        break
                    self.resources[rr].release(self.now, kk)
                return False

        dt = float(tr.delay(binding))
        t_done = self.now + dt
        binding["dt"] = dt
        binding["t_done"] = t_done
        self.schedule(t_done, "complete", (tr, binding))
        return True

    def run(self, until: float) -> "CTPNSim":
        self.schedule(0.0, "scan", None)

        while self.events:
            ev = heapq.heappop(self.events)

            if ev.time > until:
                for rp in self.resources.values():
                    rp.update(until)
                self.now = until
                break

            self.now = ev.time
            for rp in self.resources.values():
                rp.update(self.now)

            if ev.kind == "inject":
                place, val = ev.payload
                self.places[place].put(Token(val, t_available=self.now))
                self.schedule(self.now, "scan", None)

            elif ev.kind == "complete":
                tr, binding = ev.payload
                for r, k in tr.resources.items():
                    self.resources[r].release(self.now, k)
                for place_name, producer in tr.outputs:
                    for tok in producer(binding):
                        self.places[place_name].put(tok)
                self.schedule(self.now, "scan", None)

            elif ev.kind == "scan":
                progressed = True
                safety = 0
                while progressed and safety < 1000:
                    safety += 1
                    progressed = False
                    for tr in self.transitions:
                        if self._try_fire(tr):
                            progressed = True
                            break

            else:
                raise ValueError(ev.kind)

        return self


# ---------------------------
# A RAISE-like CTPN model
# ---------------------------

def build_raise_ctpn(
    seed: int = 1,
    horizon_s: float = 3600.0,
    mean_interarrival_s: float = 20.0,  # input rate (deterministic here)
    p_iphone: float = 0.35,
    cut_time_s: float = 30.0,
    vision_pick_s: float = 2.5,
    flip_s: float = 4.0,
    cooling_s: float = 30.0,
    hammer_s: float = 1.0,
    cooling_capacity: int = 4,
) -> CTPNSim:
    random.seed(seed)

    places = {n: Place(n) for n in [
        "collection", "cutting_in", "post_cut_parts",
        "low_value", "high_value", "to_flip", "to_cool",
        "cooled", "battery_out", "finished"
    ]}

    resources = {
        "saw":    ResourcePool("saw", 1),
        "ur5":    ResourcePool("ur5", 1),
        "cooler": ResourcePool("cooler", cooling_capacity),  # parallel capacity
        "hammer": ResourcePool("hammer", 1),
    }

    is_phone = lambda tok: tok.value.get("type") == "phone"
    is_part  = lambda tok: tok.value.get("type") == "part"
    ptype_in = lambda S: (lambda tok: is_part(tok) and tok.value.get("ptype") in S)
    ptype_eq = lambda s: (lambda tok: is_part(tok) and tok.value.get("ptype") == s)

    # (1) Transfer phone to cutting buffer
    t_transfer = Transition(
        "transfer_to_cutting",
        inputs=[("collection", is_phone, 1)],
        guard=lambda b: True,
        delay=lambda b: 1.0,
        outputs=[("cutting_in", lambda b: [Token(b["consumed"]["collection"][0].value, b["t_done"])])],
        priority=10,
    )

    # (2) Cutting: phone -> parts (layer-level)
    def cut_producer(b):
        phone = b["consumed"]["cutting_in"][0].value
        pid, kind = phone["id"], phone["kind"]

        parts = []
        if kind == "iPhone":
            parts += [
                {"type": "part", "phone_id": pid, "ptype": "iphone_case", "battery_target": True},
                {"type": "part", "phone_id": pid, "ptype": "middle",     "battery_target": False},
            ]
        else:
            parts += [
                {"type": "part", "phone_id": pid, "ptype": "normal_case","battery_target": False},
                {"type": "part", "phone_id": pid, "ptype": "middle",     "battery_target": True},
            ]
        parts += [
            {"type": "part", "phone_id": pid, "ptype": "screen", "battery_target": False},
            {"type": "part", "phone_id": pid, "ptype": "film",   "battery_target": False},
        ]
        return [Token(p, b["t_done"]) for p in parts]

    t_cut = Transition(
        "perform_cut",
        inputs=[("cutting_in", is_phone, 1)],
        guard=lambda b: True,
        delay=lambda b: cut_time_s,
        outputs=[("post_cut_parts", cut_producer)],
        resources={"saw": 1},
        priority=9,
    )

    # (3) Robot sorting: low value
    t_sort_low = Transition(
        "robot_sort_low",
        inputs=[("post_cut_parts", ptype_in({"normal_case", "screen", "film"}), 1)],
        guard=lambda b: True,
        delay=lambda b: vision_pick_s,
        outputs=[("low_value", lambda b: [Token(b["consumed"]["post_cut_parts"][0].value, b["t_done"])])],
        resources={"ur5": 1},
        priority=8,
    )

    # (4) Robot sorting: high value
    t_sort_high = Transition(
        "robot_sort_high",
        inputs=[("post_cut_parts", ptype_in({"middle", "iphone_case"}), 1)],
        guard=lambda b: True,
        delay=lambda b: vision_pick_s,
        outputs=[("high_value", lambda b: [Token(b["consumed"]["post_cut_parts"][0].value, b["t_done"])])],
        resources={"ur5": 1},
        priority=8,
    )

    # (5) Route iphone_case to flip (if not flipped)
    def needs_flip(tok: Token) -> bool:
        v = tok.value
        return is_part(tok) and v["ptype"] == "iphone_case" and not v.get("flipped", False)

    t_route_flip = Transition(
        "route_to_flip",
        inputs=[("high_value", needs_flip, 1)],
        guard=lambda b: True,
        delay=lambda b: 0.0,
        outputs=[("to_flip", lambda b: [Token(b["consumed"]["high_value"][0].value, b["t_done"])])],
        priority=7,
    )

    t_flip = Transition(
        "flip_iphone_case",
        inputs=[("to_flip", ptype_eq("iphone_case"), 1)],
        guard=lambda b: True,
        delay=lambda b: flip_s,
        outputs=[("high_value", lambda b: [Token({**b["consumed"]["to_flip"][0].value, "flipped": True}, b["t_done"])])],
        resources={"ur5": 1},
        priority=6,
    )

    # (6) Route battery targets to cooling
    def battery_target_ready(tok: Token) -> bool:
        if not is_part(tok):
            return False
        v = tok.value
        if not v.get("battery_target", False):
            return False
        if v["ptype"] == "iphone_case" and not v.get("flipped", False):
            return False
        return True

    t_to_cool = Transition(
        "route_to_cool",
        inputs=[("high_value", battery_target_ready, 1)],
        guard=lambda b: True,
        delay=lambda b: 0.0,
        outputs=[("to_cool", lambda b: [Token(b["consumed"]["high_value"][0].value, b["t_done"])])],
        priority=5,
    )

    # (7) Cooling (parallel capacity)
    t_cool = Transition(
        "cooling",
        inputs=[("to_cool", is_part, 1)],
        guard=lambda b: True,
        delay=lambda b: cooling_s,
        outputs=[("cooled", lambda b: [Token({**b["consumed"]["to_cool"][0].value, "cooled": True}, b["t_done"])])],
        resources={"cooler": 1},
        priority=4,
    )

    # (8) Hammer: cooled part -> battery + remainder
    def hammer_out(b):
        part = b["consumed"]["cooled"][0].value
        pid = part["phone_id"]
        return [
            Token({"type": "battery", "phone_id": pid}, b["t_done"]),
            Token({**part, "battery_removed": True}, b["t_done"]),
        ]

    t_hammer = Transition(
        "hammer",
        inputs=[("cooled", is_part, 1)],
        guard=lambda b: True,
        delay=lambda b: hammer_s,
        outputs=[("battery_out", hammer_out)],
        resources={"hammer": 1},
        priority=3,
    )

    # (9) Mark phone done once battery_removed remainder exists
    t_finish = Transition(
        "finish_phone",
        inputs=[("battery_out", lambda tok: tok.value.get("battery_removed", False), 1)],
        guard=lambda b: True,
        delay=lambda b: 0.0,
        outputs=[("finished", lambda b: [Token({"type": "done", "phone_id": b["consumed"]["battery_out"][0].value["phone_id"]}, b["t_done"])])],
        priority=1,
    )

    sim = CTPNSim(
        places=places,
        transitions=[t_transfer, t_cut, t_sort_low, t_sort_high, t_route_flip, t_flip, t_to_cool, t_cool, t_hammer, t_finish],
        resources=resources,
    )

    # Arrivals (deterministic). Swap this for exponential if you want Poisson arrivals.
    t = 0.0
    phone_id = 0
    while t <= horizon_s:
        kind = "iPhone" if random.random() < p_iphone else "Android"
        sim.inject(t, "collection", {"type": "phone", "id": phone_id, "kind": kind})
        phone_id += 1
        t += mean_interarrival_s

    return sim


def summarize(sim: CTPNSim, horizon_s: float) -> None:
    done = len(sim.places["finished"].tokens)
    throughput_per_h = done / (horizon_s / 3600.0)

    print(f"Done phones: {done}")
    print(f"Throughput:  {throughput_per_h:.1f} phones/hour")

    for r in sim.resources.values():
        util = r.busy_time / (r.capacity * horizon_s) if r.capacity > 0 else 0.0
        print(f"Util {r.name:>6}: {util*100:5.1f}%  (capacity={r.capacity})")

    print("End WIP (tokens):", {p: len(sim.places[p].tokens) for p in sim.places})


if __name__ == "__main__":
    H = 3600.0
    sim = build_raise_ctpn(
        seed=2,
        horizon_s=H,
        mean_interarrival_s=20.0,   # try 10.0 to “flood” the line
        cooling_capacity=4,         # try 1..8
    )
    sim.run(H)
    summarize(sim, H)
