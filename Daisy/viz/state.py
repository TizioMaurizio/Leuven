"""
viz/state.py – Visual state model consumed by the Pygame renderer.

Maintains the current visual representation of the simulation:
- Token positions and states
- Queue lengths
- Resource utilization
- Counters and KPIs

Updated by ``viz.binding`` which consumes EventBus events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import time


# ---------------------------------------------------------------------------
# Token – visual representation of one device
# ---------------------------------------------------------------------------

@dataclass
class Token:
    device_id: int
    location: str = "S0"           # current station or queue name
    status: str = "normal"         # normal | exception | unknown | dispatched
    exception_type: str | None = None
    # Animation
    x: float = 0.0
    y: float = 0.0
    target_x: float = 0.0
    target_y: float = 0.0
    move_start: float = 0.0       # wall-clock ms when movement started
    move_duration: float = 200.0  # ms


# ---------------------------------------------------------------------------
# VisualState – central mutable state for the renderer
# ---------------------------------------------------------------------------

class VisualState:
    """Holds everything the scene renderer needs to draw one frame."""

    def __init__(self):
        # Tokens keyed by device_id
        self.tokens: dict[int, Token] = {}

        # Queue lengths (for bar / count display)
        self.queue_lengths: dict[str, int] = {
            f"Q{i}": 0 for i in range(6)
        }

        # Resource utilization 0..1
        self.utilization: dict[str, float] = {}

        # Station occupancy (set of device_ids currently *inside* a station)
        self.station_devices: dict[str, set[int]] = {
            s: set() for s in ("S1", "S2", "S3", "S4", "S5", "S6", "E2", "E3")
        }

        # Counters
        self.completed_count: int = 0
        self.rejected_count: int = 0
        self.total_arrived: int = 0

        # Output fractions
        self.output_totals: dict[str, float] = {
            "batteries": 0.0, "logic_boards": 0.0, "housings": 0.0,
            "modules_magnets": 0.0, "mixed_fines": 0.0,
        }

        # Sim clock
        self.sim_time: float = 0.0

        # Throughput time-series (for rolling plot)
        self.throughput_history: list[tuple[float, int]] = []  # (t, cumulative)
        self.wip_history: list[tuple[float, int]] = []         # (t, total_wip)

    def get_or_create_token(self, device_id: int) -> Token:
        if device_id not in self.tokens:
            self.tokens[device_id] = Token(device_id=device_id)
        return self.tokens[device_id]

    def total_wip(self) -> int:
        return sum(self.queue_lengths.values())
