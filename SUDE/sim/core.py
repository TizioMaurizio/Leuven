"""
sim/core.py – Discrete-event simulation engine.

Provides:
* ``Event`` – a lightweight timestamped event.
* ``EventQueue`` – min-heap priority queue of events.
* ``Simulator`` – the main loop that pops events, advances the clock,
  and dispatches to a ``ProcessLogic`` handler.
"""

from __future__ import annotations

import heapq
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


# ── Event types ──────────────────────────────────────────────────────────

class EventType(Enum):
    ARRIVAL           = auto()
    IMAGING_START     = auto()
    IMAGING_DONE      = auto()
    RETRIEVAL_START   = auto()
    RETRIEVAL_DONE    = auto()
    LOOKUP_START      = auto()
    LOOKUP_DONE       = auto()
    AUTOMATION_START  = auto()
    AUTOMATION_DONE   = auto()
    HANDOVER_START    = auto()
    HANDOVER_DONE     = auto()
    MANUAL_START      = auto()
    MANUAL_DONE       = auto()
    ONBOARDING_DONE   = auto()
    LOGGING_START     = auto()
    LOGGING_DONE      = auto()
    DEPARTURE         = auto()
    # internal
    RESOURCE_GRANTED  = auto()
    END_SIM           = auto()


# ── Event ────────────────────────────────────────────────────────────────

_event_counter = 0  # global tiebreaker so heapq never compares payloads


@dataclass(order=False)
class Event:
    time: float
    event_type: EventType
    laptop_id: int
    payload: dict = field(default_factory=dict)
    _seq: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        global _event_counter
        _event_counter += 1
        self._seq = _event_counter

    # heap ordering: by time, then by insertion order
    def __lt__(self, other: Event) -> bool:  # type: ignore[override]
        if self.time != other.time:
            return self.time < other.time
        return self._seq < other._seq


# ── EventQueue ───────────────────────────────────────────────────────────

class EventQueue:
    """Min-heap priority queue of :class:`Event` objects."""

    def __init__(self) -> None:
        self._heap: list[Event] = []

    def push(self, event: Event) -> None:
        heapq.heappush(self._heap, event)

    def pop(self) -> Event:
        return heapq.heappop(self._heap)

    def peek(self) -> Optional[Event]:
        return self._heap[0] if self._heap else None

    def __len__(self) -> int:
        return len(self._heap)

    def __bool__(self) -> bool:
        return bool(self._heap)

    def clear(self) -> None:
        self._heap.clear()


# ── Simulator ────────────────────────────────────────────────────────────

StateChangeCallback = Callable[["Simulator", "Event"], None]


class Simulator:
    """Core DES engine.

    Attributes
    ----------
    now : float
        Current simulation clock.
    queue : EventQueue
        Pending future events.
    rng : random.Random
        Seeded RNG for reproducibility.
    world : object
        Reference to the ``World`` aggregate (set externally).
    metrics : object
        Reference to ``MetricsCollector`` (set externally).
    """

    def __init__(self, seed: int = 42) -> None:
        self.now: float = 0.0
        self.queue = EventQueue()
        self.seed = seed
        self.rng = random.Random(seed)
        self.world: Any = None
        self.metrics: Any = None
        self._process_logic: Any = None  # set by World
        self._state_change_listeners: list[StateChangeCallback] = []
        self._running = True

    # -- scheduling --------------------------------------------------------

    def schedule(
        self,
        t: float,
        event_type: EventType,
        laptop_id: int,
        payload: dict | None = None,
    ) -> Event:
        """Schedule an event at absolute sim-time *t*."""
        ev = Event(time=t, event_type=event_type, laptop_id=laptop_id,
                   payload=payload or {})
        self.queue.push(ev)
        return ev

    def schedule_in(
        self,
        dt: float,
        event_type: EventType,
        laptop_id: int,
        payload: dict | None = None,
    ) -> Event:
        """Schedule an event *dt* time-units from now."""
        return self.schedule(self.now + dt, event_type, laptop_id, payload)

    # -- execution ---------------------------------------------------------

    def step_next_event(self) -> Optional[Event]:
        """Pop and process the next event. Returns the event or ``None``."""
        if not self.queue:
            return None
        ev = self.queue.pop()
        self.now = ev.time
        if self._process_logic is not None:
            self._process_logic.on_event(self, ev)
        # notify listeners (visualization)
        for cb in self._state_change_listeners:
            cb(self, ev)
        return ev

    def run_until(self, t_end: float) -> None:
        """Process all events up to *t_end*."""
        while self.queue and self._running:
            nxt = self.queue.peek()
            if nxt is None or nxt.time > t_end:
                break
            self.step_next_event()
        self.now = t_end

    def run_all(self) -> None:
        """Drain the entire event queue."""
        while self.queue and self._running:
            self.step_next_event()

    def stop(self) -> None:
        self._running = False

    # -- listeners ---------------------------------------------------------

    def add_state_change_listener(self, cb: StateChangeCallback) -> None:
        self._state_change_listeners.append(cb)

    # -- reset -------------------------------------------------------------

    def reset(self, seed: int | None = None) -> None:
        """Reset the simulator to time 0 with a fresh queue and RNG."""
        self.now = 0.0
        self.queue.clear()
        self._running = True
        if seed is not None:
            self.seed = seed
        self.rng = random.Random(self.seed)
        global _event_counter
        _event_counter = 0
