"""
viz/anim.py – Token animation helpers.

Each laptop in the visual gets an ``AnimToken`` that smoothly
interpolates between station positions on-screen.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Tuple

Pos = Tuple[float, float]

# ── state → station mapping ──────────────────────────────────────────────

_STATE_TO_STATION: dict[str, str] = {
    "S0_ARRIVAL":               "ARRIVAL",
    "S1_IMAGING_WAIT":          "IMAGING",
    "S1_IMAGING":               "IMAGING",
    "S2_RETRIEVAL_WAIT":        "RETRIEVAL",
    "S2_RETRIEVAL":             "RETRIEVAL",
    "S3_LOOKUP":                "LOOKUP",
    "S4_AUTOMATION_WAIT":       "AUTOMATION",
    "S4_AUTOMATION":            "AUTOMATION",
    "S5_HANDOVER_WAIT":         "HANDOVER",
    "S5_HANDOVER":              "HANDOVER",
    "S6_MANUAL_NEW_WAIT":       "MANUAL",
    "S6_MANUAL_NEW":            "MANUAL",
    "S7_MANUAL_FALLBACK_WAIT":  "MANUAL",
    "S7_MANUAL_FALLBACK":       "MANUAL",
    "S8_LOGGING":               "LOGGING",
    "DEPARTED":                 "EXIT",
}


def station_for_state(state: str) -> str:
    return _STATE_TO_STATION.get(state, "ARRIVAL")


# ── AnimToken ────────────────────────────────────────────────────────────

@dataclass
class AnimToken:
    laptop_id: int
    current_pos: Pos = (0.0, 0.0)
    target_pos: Pos = (0.0, 0.0)
    move_start_wall: float = 0.0
    move_duration: float = 0.4   # seconds wall-clock
    station: str = "ARRIVAL"
    state: str = "S0_ARRIVAL"
    color: Tuple[int, int, int] = (60, 160, 255)  # default blue
    _departed: bool = False

    def start_move(self, target: Pos, station: str, state: str,
                   duration: float = 0.4) -> None:
        self.current_pos = self.interpolated_pos()  # freeze current
        self.target_pos = target
        self.move_start_wall = time.monotonic()
        self.move_duration = duration
        self.station = station
        self.state = state
        self._update_color()

    def interpolated_pos(self) -> Pos:
        if self.move_duration <= 0:
            return self.target_pos
        elapsed = time.monotonic() - self.move_start_wall
        t = min(elapsed / self.move_duration, 1.0)
        # ease-in-out
        t = t * t * (3 - 2 * t)
        x = self.current_pos[0] + (self.target_pos[0] - self.current_pos[0]) * t
        y = self.current_pos[1] + (self.target_pos[1] - self.current_pos[1]) * t
        return (x, y)

    @property
    def is_moving(self) -> bool:
        return (time.monotonic() - self.move_start_wall) < self.move_duration

    @property
    def departed(self) -> bool:
        return self._departed

    def mark_departed(self) -> None:
        self._departed = True

    def _update_color(self) -> None:
        _COLORS = {
            "ARRIVAL":    (120, 120, 120),
            "IMAGING":    (60,  160, 255),
            "RETRIEVAL":  (60,  200, 200),
            "LOOKUP":     (100, 220, 100),
            "AUTOMATION": (255, 180, 0),
            "HANDOVER":   (180, 100, 255),
            "MANUAL":     (255, 80,  80),
            "ONBOARDING": (255, 140, 180),
            "LOGGING":    (200, 200, 60),
            "EXIT":       (80,  80,  80),
        }
        self.color = _COLORS.get(self.station, (200, 200, 200))


# ── AnimManager ──────────────────────────────────────────────────────────

class AnimManager:
    """Manages all laptop tokens and their movement animations."""

    def __init__(self, station_positions: dict[str, Pos],
                 token_move_duration_ms: float = 400) -> None:
        self.station_positions = station_positions
        self.move_duration = token_move_duration_ms / 1000.0
        self.tokens: dict[int, AnimToken] = {}
        self._max_visible = 120  # cap tokens shown

    def on_state_change(self, laptop_id: int, new_state: str) -> None:
        station = station_for_state(new_state)
        pos = self.station_positions.get(station, (0, 0))
        # centre offset with jitter so tokens don't overlap perfectly
        import random as _rng
        jx = _rng.randint(-18, 18)
        jy = _rng.randint(-12, 12)
        target = (pos[0] + 65 + jx, pos[1] + 30 + jy)

        if laptop_id not in self.tokens:
            tok = AnimToken(laptop_id=laptop_id,
                            current_pos=target, target_pos=target,
                            station=station, state=new_state)
            tok._update_color()
            self.tokens[laptop_id] = tok
        else:
            tok = self.tokens[laptop_id]
            tok.start_move(target, station, new_state, self.move_duration)

        if new_state == "DEPARTED":
            tok.mark_departed()

    def cleanup_departed(self, keep_recent: int = 5) -> None:
        """Remove old departed tokens to keep rendering fast."""
        departed = [lid for lid, t in self.tokens.items() if t.departed]
        if len(departed) > keep_recent:
            for lid in departed[:-keep_recent]:
                del self.tokens[lid]

    @property
    def active_tokens(self) -> list[AnimToken]:
        return [t for t in self.tokens.values() if not t.departed]
