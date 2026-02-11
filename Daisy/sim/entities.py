"""
sim/entities.py – Core data structures: Device, EventRecord, EventBus,
OutputStreams.
"""

from __future__ import annotations

import collections
import csv
import io
import json
import threading
from dataclasses import dataclass, field
from typing import Any, Deque


# ---------------------------------------------------------------------------
# EventRecord – a single log entry on a device trace
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class EventRecord:
    t: float
    event: str
    station: str
    extra: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"t": self.t, "event": self.event, "station": self.station}
        if self.extra:
            d["extra"] = self.extra
        return d


# ---------------------------------------------------------------------------
# Device – the entity token flowing through the pipeline
# ---------------------------------------------------------------------------

@dataclass
class Device:
    device_id: int
    arrival_time: float
    model_class: str = "supported"          # "supported" | "unknown"
    damage_state: str = "normal"            # "normal" | "damaged"
    battery_state: str = "normal"           # "normal" | "swollen" | "missing"
    trace: list[EventRecord] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    outputs: dict[str, float | int] = field(default_factory=dict)

    # -- convenience --------------------------------------------------------

    def mark(self, event_name: str, station: str, t: float,
             extra: dict[str, Any] | None = None) -> EventRecord:
        """Append an event to the device trace and return the record."""
        rec = EventRecord(t=t, event=event_name, station=station, extra=extra)
        self.trace.append(rec)
        return rec

    @property
    def cycle_time(self) -> float | None:
        """Total time from arrival to dispatch (None if not yet dispatched)."""
        dispatch = [r for r in self.trace if r.event == "DISPATCHED"]
        if dispatch:
            return dispatch[-1].t - self.arrival_time
        return None


# ---------------------------------------------------------------------------
# EventBus – fan-out of dict events to listeners
# ---------------------------------------------------------------------------

class EventBus:
    """Simple publish-subscribe bus.

    Listeners register via ``subscribe(callback)``.  The simulation calls
    ``emit(event_dict)`` for every state change; each listener receives the
    dict synchronously (single-thread model).

    An internal deque keeps the last *maxlen* events for the Pygame consumer.
    """

    def __init__(self, maxlen: int = 50_000):
        self._listeners: list[Any] = []
        self.queue: Deque[dict[str, Any]] = collections.deque(maxlen=maxlen)
        self._lock = threading.Lock()  # safe if someone opts for threads

    def subscribe(self, callback) -> None:
        self._listeners.append(callback)

    def emit(self, event: dict[str, Any]) -> None:
        with self._lock:
            self.queue.append(event)
        for cb in self._listeners:
            cb(event)


# ---------------------------------------------------------------------------
# Helper factories for event dicts (used by station code)
# ---------------------------------------------------------------------------

def ev(env, device: Device, event: str, station: str, *,
       extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a standard event dict and mark it on the device."""
    device.mark(event, station, env.now, extra)
    d: dict[str, Any] = {
        "t": env.now,
        "device_id": device.device_id,
        "event": event,
        "station": station,
        "model_class": device.model_class,
        "damage_state": device.damage_state,
        "battery_state": device.battery_state,
        "exceptions": list(device.exceptions),
    }
    if extra:
        d["extra"] = extra
    return d


def qput(env, device: Device, queue_name: str) -> dict[str, Any]:
    return {
        "t": env.now,
        "device_id": device.device_id,
        "event": "Q_PUT",
        "station": queue_name,
    }


def qget(env, device: Device, queue_name: str) -> dict[str, Any]:
    return {
        "t": env.now,
        "device_id": device.device_id,
        "event": "Q_GET",
        "station": queue_name,
    }


# ---------------------------------------------------------------------------
# OutputStreams – aggregate output counters per fraction
# ---------------------------------------------------------------------------

class OutputStreams:
    """Accumulate per-fraction counters across all dispatched devices."""

    FRACTIONS = ("batteries", "logic_boards", "housings",
                 "modules_magnets", "mixed_fines")

    def __init__(self):
        self.totals: dict[str, float] = {f: 0.0 for f in self.FRACTIONS}
        self.device_count: int = 0

    def record(self, device: Device) -> None:
        self.device_count += 1
        for frac in self.FRACTIONS:
            self.totals[frac] += device.outputs.get(frac, 0.0)

    def summary(self) -> dict[str, Any]:
        return {
            "devices_processed": self.device_count,
            "fraction_totals": dict(self.totals),
        }
