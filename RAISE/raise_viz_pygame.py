#!/usr/bin/env python3
"""
raise_viz_pygame.py – Pygame-based visualizer for the RAISE CTPN simulation.

Renders a Colored Timed Petri Net (CTPN) simulation of the RAISE
demanufacturing system (Robot-Assisted Selective disassembly and Sorting
for End-of-Life phones) at station-level granularity.

===========================================================================
HOW TO USE
===========================================================================

1) **Event-log replay mode** (preferred):
   Your simulator writes a JSON array of event dicts, then:

       python raise_viz_pygame.py --log events.json [--speed 2.0] [--no-anim]

   Each event dict follows this schema:

       {
         "t":          float,           # simulation time (seconds)
         "kind":       str,             # "inject"|"move"|"fire_start"|"fire_end"|"resource"
         "transition": str | null,      # transition name (optional)
         "src":        str | null,      # source place/station
         "dst":        str | null,      # destination place/station
         "token_id":   str | int | null,# unique per-token id
         "token":      dict | null,     # colored-token payload (see schema below)
         "resources":  dict | null,     # {"saw": 1, "ur5": 0, ...}
         "note":       str | null       # e.g. "flip", "low conf"
       }

2) **Live callback mode** (in-process):
   Import and call directly:

       from raise_viz_pygame import RaiseVisualizer
       viz = RaiseVisualizer()
       viz.on_event(event_dict)   # feed events one-by-one

3) **Demo mode** (no arguments):
   A synthetic event log is generated and replayed automatically:

       python raise_viz_pygame.py

===========================================================================
TOKEN SCHEMA
===========================================================================
token["type"]  ∈ {"phone", "part", "battery", "done"}
token["phone_id"]: int/str
token["kind"]  ∈ {"iPhone", "Android", "Unknown"}    (phone tokens)

For part tokens:
  token["ptype"] ∈ {"iphone_case", "middle", "normal_case",
                     "screen", "film", "unknown"}
  token["battery_target"]: bool
  token["flipped"]: bool
  token["cooled"]: bool
  token["battery_removed"]: bool
token["conf"]:  float in [0,1]       (vision confidence)
token["t_available"]: float           (locked-until time)

===========================================================================
EXTENDING
===========================================================================
- Add stations → append to STATIONS list and EDGES list.
- Add aliases  → add entries in ALIASES dict.
- Change resource-transition mapping → edit TRANSITION_RESOURCES dict.
- All coordinates/sizes/colors are in the CONFIG dict at the top.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    import pygame
    from pygame import gfxdraw
except ImportError:
    print("ERROR: pygame is required.  Install with:  pip install pygame")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════
#  CONFIGURATION — tweak positions, sizes, colours, etc. here
# ═══════════════════════════════════════════════════════════════════════════

CONFIG: Dict[str, Any] = {
    # Window
    "win_w": 1920,
    "win_h": 1080,
    "bg_color": (24, 26, 32),
    "fps": 60,

    # Station boxes
    "station_w": 130,
    "station_h": 64,
    "station_corner_r": 8,
    "station_font_size": 13,
    "station_label_color": (220, 220, 230),

    # Tokens
    "token_radius": 10,
    "token_font_size": 9,
    "max_visible_tokens": 12,       # per station, show "+N" for overflow

    # Arrows
    "arrow_color": (100, 110, 130),
    "arrow_head_size": 8,
    "arrow_width": 2,

    # Resource panel
    "res_panel_x": 30,
    "res_panel_y": 750,
    "res_bar_w": 180,
    "res_bar_h": 18,
    "res_font_size": 14,

    # HUD / top bar
    "hud_font_size": 16,
    "hud_color": (200, 210, 230),

    # Animation
    "anim_duration_base": 0.35,     # seconds wall-time at 1× speed
    "anim_min_duration": 0.05,

    # Annotation font
    "anno_font_size": 10,
    "anno_color": (140, 150, 170),

    # Scale factor (multiplies all station positions)
    "scale": 1.0,
}

# ─── Station positions (x, y) at scale=1.0 ────────────────────────────────
# Positions are centre-of-box.  Adjust freely.

_X0, _Y0 = 80, 100       # top-left origin offset
_DX, _DY = 160, 110      # spacing between columns / rows

STATION_POSITIONS: Dict[str, Tuple[int, int]] = {
    # ── Row A: feed → cutting → stacking ──
    "collection_unit":             (_X0 + 0 * _DX, _Y0),
    "transfer_to_cutting":         (_X0 + 1 * _DX, _Y0),
    "cut_conveyor_stage1":         (_X0 + 2 * _DX, _Y0),
    "fixture_clamped":             (_X0 + 3 * _DX, _Y0),
    "cut_sawpair_A":               (_X0 + 4 * _DX, _Y0),
    "transfer_between_sawpairs":   (_X0 + 5 * _DX, _Y0),
    "cut_sawpair_B":               (_X0 + 6 * _DX, _Y0),
    "cut_complete":                (_X0 + 7 * _DX, _Y0),
    "stacked_face_down":           (_X0 + 8 * _DX, _Y0),

    # ── Row B: vision + sorting ──
    "vision_scan":                 (_X0 + 3 * _DX, _Y0 + _DY),
    "robot_sorting":               (_X0 + 5 * _DX, _Y0 + _DY),
    "low_value_bin":               (_X0 + 7 * _DX, _Y0 + _DY),
    "high_value_buffer":           (_X0 + 5 * _DX, _Y0 + 2 * _DY),

    # ── Vision uncertainty ──
    "vision_uncertain":            (_X0 + 3 * _DX, _Y0 + 2 * _DY),
    "rescan_queue":                (_X0 + 2 * _DX, _Y0 + 2 * _DY),
    "manual_review":               (_X0 + 1 * _DX, _Y0 + 2 * _DY),

    # ── Side loop: flip ──
    "to_flip":                     (_X0 + 7 * _DX, _Y0 + 2 * _DY),
    "flip_station":                (_X0 + 8 * _DX, _Y0 + 2 * _DY),
    "flipped_buffer":              (_X0 + 8 * _DX, _Y0 + 3 * _DY),

    # ── Bottom: battery removal ──
    "to_cool":                     (_X0 + 1 * _DX, _Y0 + 4 * _DY),
    "cooling_chamber":             (_X0 + 3 * _DX, _Y0 + 4 * _DY),
    "cooled_buffer":               (_X0 + 5 * _DX, _Y0 + 4 * _DY),
    "hammer_station":              (_X0 + 7 * _DX, _Y0 + 4 * _DY),
    "battery_bin":                 (_X0 + 8 * _DX, _Y0 + 5 * _DY),
    "remainder_bin":               (_X0 + 9 * _DX, _Y0 + 4 * _DY),
    "finished":                    (_X0 + 10 * _DX, _Y0 + 4 * _DY),
}

# ─── Directed edges (src, dst) ────────────────────────────────────────────
EDGES: List[Tuple[str, str]] = [
    # Feed → cutting
    ("collection_unit", "transfer_to_cutting"),
    ("transfer_to_cutting", "cut_conveyor_stage1"),
    ("cut_conveyor_stage1", "fixture_clamped"),
    ("fixture_clamped", "cut_sawpair_A"),
    ("cut_sawpair_A", "transfer_between_sawpairs"),
    ("transfer_between_sawpairs", "cut_sawpair_B"),
    ("cut_sawpair_B", "cut_complete"),
    ("cut_complete", "stacked_face_down"),
    # Sorting
    ("stacked_face_down", "vision_scan"),
    ("vision_scan", "robot_sorting"),
    ("robot_sorting", "low_value_bin"),
    ("robot_sorting", "high_value_buffer"),
    # Vision uncertainty
    ("vision_scan", "vision_uncertain"),
    ("vision_uncertain", "rescan_queue"),
    ("rescan_queue", "vision_scan"),
    ("vision_uncertain", "manual_review"),
    # Flip loop
    ("high_value_buffer", "to_flip"),
    ("to_flip", "flip_station"),
    ("flip_station", "flipped_buffer"),
    ("flipped_buffer", "high_value_buffer"),
    # Battery removal
    ("high_value_buffer", "to_cool"),
    ("to_cool", "cooling_chamber"),
    ("cooling_chamber", "cooled_buffer"),
    ("cooled_buffer", "hammer_station"),
    ("hammer_station", "battery_bin"),
    ("hammer_station", "remainder_bin"),
    ("remainder_bin", "finished"),
]

# ─── Station label annotations (static info shown near station) ────────
STATION_ANNOTATIONS: Dict[str, str] = {
    "cut_sawpair_A": "2 mm edge offset\ndepth control",
    "cut_sawpair_B": "2 mm edge offset\ndepth control",
    "cooling_chamber": "chiller −80 °C air\nadhesive weakens\nbelow −17.78 °C",
}

# ─── Station alias mapping ────────────────────────────────────────────────
# Maps simple names from the simulator (RAISE.py) to the granular place names
# used in the visualizer.  Extend as needed.
ALIASES: Dict[str, str] = {
    # Feed / transfer
    "collection":       "collection_unit",
    "arrival":          "collection_unit",
    "input":            "collection_unit",
    "cutting_in":       "cut_conveyor_stage1",
    # Post-cut
    "post_cut_parts":   "stacked_face_down",
    "post_cut":         "stacked_face_down",
    # Sorting bins
    "low_value":        "low_value_bin",
    "high_value":       "high_value_buffer",
    # Flip
    "to_flip":          "to_flip",
    "flip":             "flip_station",
    # Cooling / battery
    "to_cool":          "to_cool",
    "cooled":           "cooled_buffer",
    "battery_out":      "battery_bin",
    "battery":          "battery_bin",
    "remainder":        "remainder_bin",
    "finished":         "finished",
    "done":             "finished",
}

# ─── Transition → resource mapping (used when events lack "resources") ─────
TRANSITION_RESOURCES: Dict[str, str] = {
    "perform_cut":         "saw",
    "cut_sawpair_A":       "saw",
    "cut_sawpair_B":       "saw",
    "robot_sort_low":      "ur5",
    "robot_sort_high":     "ur5",
    "robot_sorting":       "ur5",
    "flip_iphone_case":    "ur5",
    "flip":                "ur5",
    "cooling":             "cooler",
    "hammer":              "hammer",
    "hammer_separation":   "hammer",
}

# ─── Token colour palette ──────────────────────────────────────────────────
TOKEN_TYPE_COLORS: Dict[str, Tuple[int, int, int]] = {
    "phone":   (60, 160, 255),
    "battery": (255, 200, 50),
    "done":    (100, 220, 100),
}

TOKEN_PTYPE_COLORS: Dict[str, Tuple[int, int, int]] = {
    "iphone_case":  (220, 120, 255),
    "middle":       (255, 140, 80),
    "normal_case":  (130, 180, 220),
    "screen":       (100, 220, 200),
    "film":         (180, 180, 180),
    "unknown":      (200, 60, 60),
}

PTYPE_ABBREV: Dict[str, str] = {
    "iphone_case":  "IC",
    "middle":       "M",
    "normal_case":  "NC",
    "screen":       "S",
    "film":         "F",
    "unknown":      "?",
}

# Station fill colours by category
STATION_CATEGORY_COLORS: Dict[str, Tuple[int, int, int]] = {
    "feed":     (40, 55, 75),
    "cut":      (55, 45, 70),
    "sort":     (40, 65, 60),
    "flip":     (65, 55, 45),
    "cool":     (35, 55, 80),
    "end":      (50, 60, 50),
    "uncertain": (70, 40, 40),
}

_STATION_CATEGORY: Dict[str, str] = {}
for _s in ("collection_unit", "transfer_to_cutting"):
    _STATION_CATEGORY[_s] = "feed"
for _s in ("cut_conveyor_stage1", "fixture_clamped", "cut_sawpair_A",
           "transfer_between_sawpairs", "cut_sawpair_B", "cut_complete",
           "stacked_face_down"):
    _STATION_CATEGORY[_s] = "cut"
for _s in ("vision_scan", "robot_sorting", "low_value_bin", "high_value_buffer"):
    _STATION_CATEGORY[_s] = "sort"
for _s in ("vision_uncertain", "rescan_queue", "manual_review"):
    _STATION_CATEGORY[_s] = "uncertain"
for _s in ("to_flip", "flip_station", "flipped_buffer"):
    _STATION_CATEGORY[_s] = "flip"
for _s in ("to_cool", "cooling_chamber", "cooled_buffer", "hammer_station",
           "battery_bin", "remainder_bin"):
    _STATION_CATEGORY[_s] = "cool"
for _s in ("finished",):
    _STATION_CATEGORY[_s] = "end"

# Playback speed presets (cycle with UP/DOWN)
SPEED_PRESETS: List[float] = [0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0]

# ═══════════════════════════════════════════════════════════════════════════
#  HELPER: resolve station alias
# ═══════════════════════════════════════════════════════════════════════════

def resolve_station(name: Optional[str]) -> Optional[str]:
    """Map a simulator place name to the canonical visualizer station name."""
    if name is None:
        return None
    if name in STATION_POSITIONS:
        return name
    return ALIASES.get(name, name)


# ═══════════════════════════════════════════════════════════════════════════
#  DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TokenState:
    """Represents a single token in the CTPN."""
    token_id: Any                     # unique id
    data: Dict[str, Any]              # the coloured payload
    station: Optional[str] = None     # current station (None if in-flight)

    # -- rendering helpers --
    x: float = 0.0
    y: float = 0.0


@dataclass
class AnimatingToken:
    """A token currently moving between stations."""
    token_state: TokenState
    src: Tuple[float, float]
    dst: Tuple[float, float]
    start_wall: float
    duration: float
    done: bool = False


# ═══════════════════════════════════════════════════════════════════════════
#  StationView
# ═══════════════════════════════════════════════════════════════════════════

class StationView:
    """Visual representation of one place/station."""

    def __init__(self, name: str, cx: float, cy: float, scale: float = 1.0):
        self.name = name
        self.cx = cx * scale
        self.cy = cy * scale
        self.w = CONFIG["station_w"] * scale
        self.h = CONFIG["station_h"] * scale
        self.tokens: List[TokenState] = []
        self.category = _STATION_CATEGORY.get(name, "feed")
        self.fill_color = STATION_CATEGORY_COLORS.get(self.category, (50, 50, 60))
        self.annotation = STATION_ANNOTATIONS.get(name)
        self.compact_label = False

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.cx - self.w / 2), int(self.cy - self.h / 2),
            int(self.w), int(self.h)
        )

    @property
    def top_centre(self) -> Tuple[float, float]:
        return (self.cx, self.cy - self.h / 2)

    @property
    def bottom_centre(self) -> Tuple[float, float]:
        return (self.cx, self.cy + self.h / 2)

    @property
    def left_centre(self) -> Tuple[float, float]:
        return (self.cx - self.w / 2, self.cy)

    @property
    def right_centre(self) -> Tuple[float, float]:
        return (self.cx + self.w / 2, self.cy)

    # ── Token layout inside station ──
    def layout_tokens(self) -> None:
        """Assign (x, y) to each token for compact grid display."""
        r = CONFIG["token_radius"]
        margin = 4
        cols = max(1, int((self.w - margin * 2) / (r * 2 + 2)))
        for i, tok in enumerate(self.tokens):
            if i >= CONFIG["max_visible_tokens"]:
                break
            col = i % cols
            row = i // cols
            tok.x = self.cx - self.w / 2 + margin + r + col * (r * 2 + 2)
            tok.y = self.cy + 2 + row * (r * 2 + 2)

    def draw(self, surf: pygame.Surface, fonts: Dict[str, pygame.font.Font]) -> None:
        """Draw the station box, label, tokens, annotations."""
        r = CONFIG["station_corner_r"]
        rect = self.rect

        # Filled rounded rect
        _draw_rounded_rect(surf, rect, self.fill_color, r)
        # Border
        _draw_rounded_rect(surf, rect, _brighten(self.fill_color, 40), r, width=1)

        # Label
        label = self._label_text()
        lbl_surf = fonts["station"].render(label, True, CONFIG["station_label_color"])
        lbl_rect = lbl_surf.get_rect(midtop=(int(self.cx), rect.top + 3))
        surf.blit(lbl_surf, lbl_rect)

        # Token count badge
        n = len(self.tokens)
        if n > 0:
            badge = fonts["small"].render(str(n), True, (255, 255, 255))
            badge_bg = pygame.Rect(rect.right - 20, rect.top + 2, 18, 14)
            pygame.draw.rect(surf, (80, 100, 140), badge_bg, border_radius=4)
            surf.blit(badge, badge.get_rect(center=badge_bg.center))

        # Draw tokens inside the box
        self.layout_tokens()
        max_vis = CONFIG["max_visible_tokens"]
        for i, tok in enumerate(self.tokens[:max_vis]):
            _draw_token(surf, tok, fonts)
        if n > max_vis:
            extra_txt = fonts["small"].render(f"+{n - max_vis}", True, (200, 200, 200))
            surf.blit(extra_txt, (rect.right - 30, rect.bottom - 14))

        # Static annotations (e.g. cutting depth note)
        if self.annotation:
            lines = self.annotation.split("\n")
            for li, line in enumerate(lines):
                ann_surf = fonts["anno"].render(line, True, CONFIG["anno_color"])
                surf.blit(ann_surf, (rect.left, rect.bottom + 2 + li * 12))

    def _label_text(self) -> str:
        if self.compact_label:
            parts = self.name.split("_")
            return "".join(p[0].upper() for p in parts if p)
        return self.name.replace("_", " ")


# ═══════════════════════════════════════════════════════════════════════════
#  ResourcePanel
# ═══════════════════════════════════════════════════════════════════════════

class ResourcePanel:
    """Draws resource-pool utilisation bars."""

    def __init__(self, resources: Dict[str, int]):
        """resources = {name: capacity}"""
        self.resources = {name: {"capacity": cap, "in_use": 0}
                          for name, cap in resources.items()}

    def update(self, res_dict: Dict[str, int]) -> None:
        """Update in_use counts from event data."""
        for name, val in res_dict.items():
            if name in self.resources:
                self.resources[name]["in_use"] = val

    def infer_fire(self, transition: str, started: bool) -> None:
        """If no explicit resource data, infer from transition name."""
        res_name = TRANSITION_RESOURCES.get(transition)
        if res_name and res_name in self.resources:
            r = self.resources[res_name]
            if started:
                r["in_use"] = min(r["in_use"] + 1, r["capacity"])
            else:
                r["in_use"] = max(r["in_use"] - 1, 0)

    def draw(self, surf: pygame.Surface, fonts: Dict[str, pygame.font.Font]) -> None:
        x = CONFIG["res_panel_x"]
        y = CONFIG["res_panel_y"]
        bw = CONFIG["res_bar_w"]
        bh = CONFIG["res_bar_h"]

        title = fonts["hud"].render("Resources", True, (200, 210, 230))
        surf.blit(title, (x, y - 24))

        for i, (name, info) in enumerate(self.resources.items()):
            cap = info["capacity"]
            use = info["in_use"]
            frac = use / cap if cap > 0 else 0
            yy = y + i * (bh + 10)

            # Label
            label = fonts["res"].render(f"{name} ({use}/{cap})", True, (190, 200, 210))
            surf.blit(label, (x, yy))

            # Background bar
            bar_rect = pygame.Rect(x, yy + 16, bw, bh)
            pygame.draw.rect(surf, (50, 55, 65), bar_rect, border_radius=4)

            # Fill bar
            if frac > 0:
                fill_w = max(4, int(bw * frac))
                fill_rect = pygame.Rect(x, yy + 16, fill_w, bh)
                color = _utilization_color(frac)
                pygame.draw.rect(surf, color, fill_rect, border_radius=4)

            # Border
            pygame.draw.rect(surf, (80, 90, 100), bar_rect, width=1, border_radius=4)


# ═══════════════════════════════════════════════════════════════════════════
#  Animator
# ═══════════════════════════════════════════════════════════════════════════

class Animator:
    """Manages token-movement animations."""

    def __init__(self):
        self.active: List[AnimatingToken] = []

    def add(self, tok_state: TokenState, src: Tuple[float, float],
            dst: Tuple[float, float], duration: float) -> None:
        anim = AnimatingToken(
            token_state=tok_state,
            src=src, dst=dst,
            start_wall=time.monotonic(),
            duration=max(duration, CONFIG["anim_min_duration"]),
        )
        self.active.append(anim)

    def update(self) -> List[TokenState]:
        """Advance all animations; return list of tokens that finished."""
        now = time.monotonic()
        finished: List[TokenState] = []
        still_active: List[AnimatingToken] = []
        for anim in self.active:
            elapsed = now - anim.start_wall
            t = min(1.0, elapsed / anim.duration) if anim.duration > 0 else 1.0
            # Ease-in-out cubic
            t_smooth = t * t * (3 - 2 * t)
            anim.token_state.x = anim.src[0] + (anim.dst[0] - anim.src[0]) * t_smooth
            anim.token_state.y = anim.src[1] + (anim.dst[1] - anim.src[1]) * t_smooth
            if t >= 1.0:
                anim.done = True
                finished.append(anim.token_state)
            else:
                still_active.append(anim)
        self.active = still_active
        return finished

    def draw(self, surf: pygame.Surface, fonts: Dict[str, pygame.font.Font]) -> None:
        for anim in self.active:
            _draw_token(surf, anim.token_state, fonts, highlight=True)

    def clear(self) -> None:
        self.active.clear()

    @property
    def busy(self) -> bool:
        return len(self.active) > 0


# ═══════════════════════════════════════════════════════════════════════════
#  EventReplayer
# ═══════════════════════════════════════════════════════════════════════════

class EventReplayer:
    """Replays a list of events against the station/resource state."""

    def __init__(
        self,
        events: List[Dict[str, Any]],
        stations: Dict[str, StationView],
        resources: ResourcePanel,
        animator: Animator,
        anim_enabled: bool = True,
        playback_speed: float = 1.0,
    ):
        self.events = sorted(events, key=lambda e: (e.get("t", 0), e.get("kind", "")))
        self.idx = 0
        self.stations = stations
        self.resources = resources
        self.animator = animator
        self.anim_enabled = anim_enabled
        self.playback_speed = playback_speed

        self.sim_time: float = 0.0          # current simulation time
        self.paused: bool = False
        self._wall_start: float = time.monotonic()
        self._sim_start: float = self.events[0]["t"] if self.events else 0.0
        self._pause_wall: Optional[float] = None
        self._wall_offset: float = 0.0      # accumulated pause time

        # Token registry
        self._tokens: Dict[Any, TokenState] = {}
        self._next_token_id = 0

    # ── public API ──

    def restart(self) -> None:
        """Reset playback to the beginning."""
        self.idx = 0
        self.sim_time = self._sim_start
        self._wall_start = time.monotonic()
        self._wall_offset = 0.0
        self._pause_wall = None
        self.paused = False
        self._tokens.clear()
        self.animator.clear()
        for s in self.stations.values():
            s.tokens.clear()

    def toggle_pause(self) -> None:
        if self.paused:
            if self._pause_wall is not None:
                self._wall_offset += time.monotonic() - self._pause_wall
            self._pause_wall = None
            self.paused = False
        else:
            self._pause_wall = time.monotonic()
            self.paused = True

    def step_forward(self) -> None:
        """Advance by one event (used when paused)."""
        if self.idx < len(self.events):
            self._apply_event(self.events[self.idx])
            self.idx += 1

    def step_backward(self) -> None:
        """Step back one event by replaying from start up to idx-1."""
        if self.idx <= 0:
            return
        target = self.idx - 1
        self.restart()
        for i in range(target):
            self._apply_event(self.events[i], animate=False)
        self.idx = target
        if target > 0:
            self.sim_time = self.events[target - 1].get("t", 0.0)

    def tick(self) -> None:
        """Called every frame.  Advance sim_time and apply due events."""
        if self.paused:
            return

        wall_now = time.monotonic()
        wall_elapsed = wall_now - self._wall_start - self._wall_offset
        self.sim_time = self._sim_start + wall_elapsed * self.playback_speed

        # Apply all events up to sim_time
        while self.idx < len(self.events):
            ev = self.events[self.idx]
            if ev.get("t", 0.0) <= self.sim_time:
                self._apply_event(ev)
                self.idx += 1
            else:
                break

    @property
    def progress(self) -> float:
        if not self.events:
            return 1.0
        return self.idx / len(self.events)

    @property
    def done(self) -> bool:
        return self.idx >= len(self.events) and not self.animator.busy

    # ── internal ──

    def _get_or_create_token(self, ev: Dict[str, Any]) -> TokenState:
        tid = ev.get("token_id")
        if tid is None:
            tid = f"_auto_{self._next_token_id}"
            self._next_token_id += 1
        if tid not in self._tokens:
            data = ev.get("token") or {}
            self._tokens[tid] = TokenState(token_id=tid, data=data)
        else:
            # Update data if new payload is provided
            new_data = ev.get("token")
            if new_data:
                self._tokens[tid].data.update(new_data)
        return self._tokens[tid]

    def _apply_event(self, ev: Dict[str, Any], animate: bool = True) -> None:
        kind = ev.get("kind", "")
        self.sim_time = max(self.sim_time, ev.get("t", 0.0))

        if kind == "inject":
            tok = self._get_or_create_token(ev)
            dst_name = resolve_station(ev.get("dst") or ev.get("src"))
            if dst_name and dst_name in self.stations:
                self._place_token(tok, dst_name)

        elif kind == "move":
            tok = self._get_or_create_token(ev)
            src_name = resolve_station(ev.get("src"))
            dst_name = resolve_station(ev.get("dst"))
            if src_name and src_name in self.stations:
                self._remove_token_from_station(tok, src_name)
            if dst_name and dst_name in self.stations:
                if animate and self.anim_enabled and src_name and src_name in self.stations:
                    src_view = self.stations[src_name]
                    dst_view = self.stations[dst_name]
                    dur = CONFIG["anim_duration_base"] / max(0.25, self.playback_speed)
                    tok.x, tok.y = src_view.cx, src_view.cy
                    self.animator.add(
                        tok,
                        src=(src_view.cx, src_view.cy),
                        dst=(dst_view.cx, dst_view.cy),
                        duration=dur,
                    )
                    # Token will be placed after animation completes
                    tok.station = dst_name  # pre-assign for lookup
                    # Defer actual placement to animator completion
                    self.stations[dst_name].tokens.append(tok)
                else:
                    self._place_token(tok, dst_name)

        elif kind == "fire_start":
            tr = ev.get("transition", "")
            self.resources.infer_fire(tr, started=True)

        elif kind == "fire_end":
            tr = ev.get("transition", "")
            self.resources.infer_fire(tr, started=False)

        elif kind == "resource":
            res = ev.get("resources")
            if res:
                self.resources.update(res)

        # Update resources snapshot if present regardless of kind
        res = ev.get("resources")
        if res:
            self.resources.update(res)

    def _place_token(self, tok: TokenState, station_name: str) -> None:
        self._remove_token_from_all(tok)
        tok.station = station_name
        st = self.stations[station_name]
        if tok not in st.tokens:
            st.tokens.append(tok)

    def _remove_token_from_station(self, tok: TokenState, station_name: str) -> None:
        st = self.stations.get(station_name)
        if st and tok in st.tokens:
            st.tokens.remove(tok)

    def _remove_token_from_all(self, tok: TokenState) -> None:
        for st in self.stations.values():
            if tok in st.tokens:
                st.tokens.remove(tok)


# ═══════════════════════════════════════════════════════════════════════════
#  RaiseVisualizer  (main facade; also supports live callback mode)
# ═══════════════════════════════════════════════════════════════════════════

class RaiseVisualizer:
    """
    High-level facade.

    Usage – callback mode:
        viz = RaiseVisualizer()
        viz.on_event({"t": 0.0, "kind": "inject", "dst": "collection",
                      "token_id": 0, "token": {"type": "phone", ...}})
        viz.run()   # opens Pygame window

    Usage – log replay mode (CLI):
        python raise_viz_pygame.py --log events.json
    """

    def __init__(
        self,
        events: Optional[List[Dict[str, Any]]] = None,
        playback_speed: float = 1.0,
        anim_enabled: bool = True,
        scale: float = 1.0,
    ):
        self.scale = scale * CONFIG["scale"]
        self.anim_enabled = anim_enabled
        self.playback_speed = playback_speed
        self._speed_idx = SPEED_PRESETS.index(1.0) if 1.0 in SPEED_PRESETS else 2

        # Find closest preset
        for i, sp in enumerate(SPEED_PRESETS):
            if abs(sp - playback_speed) < 0.01:
                self._speed_idx = i
                break

        # Build stations
        self.stations: Dict[str, StationView] = {}
        for name, (px, py) in STATION_POSITIONS.items():
            self.stations[name] = StationView(name, px, py, self.scale)

        # Resources
        self.resource_panel = ResourcePanel({
            "saw": 1, "ur5": 1, "cooler": 4, "hammer": 1,
        })

        # Animator
        self.animator = Animator()

        # Replayer (may be created later in callback mode)
        self._events_buffer: List[Dict[str, Any]] = events or []
        self.replayer: Optional[EventReplayer] = None
        if events:
            self.replayer = EventReplayer(
                events, self.stations, self.resource_panel,
                self.animator, anim_enabled, playback_speed,
            )

        # Pygame state
        self._screen: Optional[pygame.Surface] = None
        self._fonts: Dict[str, pygame.font.Font] = {}
        self._running = False

    # ── callback mode ──

    def on_event(self, event: Dict[str, Any]) -> None:
        """Feed a single event (live callback mode)."""
        self._events_buffer.append(event)
        # If replayer already exists, apply immediately
        if self.replayer:
            self.replayer._apply_event(event)

    # ── main loop ──

    def run(self) -> None:
        """Open window and run the visualisation loop."""
        pygame.init()
        info = pygame.display.Info()
        w = min(CONFIG["win_w"], info.current_w - 40)
        h = min(CONFIG["win_h"], info.current_h - 80)
        self._screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
        pygame.display.set_caption("RAISE CTPN Visualizer")
        self._init_fonts()

        if self.replayer is None and self._events_buffer:
            self.replayer = EventReplayer(
                self._events_buffer, self.stations, self.resource_panel,
                self.animator, self.anim_enabled, self.playback_speed,
            )

        clock = pygame.time.Clock()
        self._running = True

        while self._running:
            dt_ms = clock.tick(CONFIG["fps"])
            self._handle_events()
            if self.replayer:
                self.replayer.tick()

            # Finish completed animations → place tokens
            self.animator.update()

            self._draw()
            pygame.display.flip()

        pygame.quit()

    # ── pygame events ──

    def _handle_events(self) -> None:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self._running = False
            elif ev.type == pygame.KEYDOWN:
                self._on_key(ev.key)
            elif ev.type == pygame.VIDEORESIZE:
                self._screen = pygame.display.set_mode(
                    (ev.w, ev.h), pygame.RESIZABLE
                )

    def _on_key(self, key: int) -> None:
        rp = self.replayer
        if key == pygame.K_ESCAPE:
            self._running = False
        elif key == pygame.K_SPACE and rp:
            rp.toggle_pause()
        elif key == pygame.K_UP:
            self._change_speed(+1)
        elif key == pygame.K_DOWN:
            self._change_speed(-1)
        elif key == pygame.K_RIGHT and rp and rp.paused:
            rp.step_forward()
        elif key == pygame.K_LEFT and rp and rp.paused:
            rp.step_backward()
        elif key == pygame.K_a:
            self.anim_enabled = not self.anim_enabled
            if rp:
                rp.anim_enabled = self.anim_enabled
        elif key == pygame.K_r and rp:
            rp.restart()
        elif key == pygame.K_l:
            for st in self.stations.values():
                st.compact_label = not st.compact_label

    def _change_speed(self, direction: int) -> None:
        self._speed_idx = max(0, min(len(SPEED_PRESETS) - 1,
                                     self._speed_idx + direction))
        new_speed = SPEED_PRESETS[self._speed_idx]
        self.playback_speed = new_speed
        if self.replayer:
            # Adjust wall reference so sim_time stays continuous
            rp = self.replayer
            if not rp.paused:
                wall_now = time.monotonic()
                wall_elapsed = wall_now - rp._wall_start - rp._wall_offset
                sim_now = rp._sim_start + wall_elapsed * rp.playback_speed
                rp.playback_speed = new_speed
                rp._wall_start = wall_now
                rp._wall_offset = 0.0
                rp._sim_start = sim_now
            else:
                rp.playback_speed = new_speed

    # ── drawing ──

    def _draw(self) -> None:
        surf = self._screen
        if surf is None:
            return
        surf.fill(CONFIG["bg_color"])

        # Edges (arrows)
        self._draw_edges(surf)

        # Stations
        for st in self.stations.values():
            st.draw(surf, self._fonts)

        # Animating tokens
        self.animator.draw(surf, self._fonts)

        # Resources
        self.resource_panel.draw(surf, self._fonts)

        # Cooling capacity label
        cool_st = self.stations.get("cooling_chamber")
        if cool_st:
            cap = self.resource_panel.resources.get("cooler", {}).get("capacity", 4)
            use = self.resource_panel.resources.get("cooler", {}).get("in_use", 0)
            cap_txt = self._fonts["anno"].render(
                f"cooler capacity = {cap}  ({use} in use)", True, (160, 200, 220)
            )
            surf.blit(cap_txt, (int(cool_st.cx - cool_st.w / 2),
                                int(cool_st.cy + cool_st.h / 2 + 38)))

        # HUD
        self._draw_hud(surf)

    def _draw_edges(self, surf: pygame.Surface) -> None:
        for src_name, dst_name in EDGES:
            src_st = self.stations.get(src_name)
            dst_st = self.stations.get(dst_name)
            if not src_st or not dst_st:
                continue
            # Pick best connection points
            sx, sy = self._edge_exit(src_st, dst_st)
            ex, ey = self._edge_entry(dst_st, src_st)
            _draw_arrow(surf, (sx, sy), (ex, ey),
                        CONFIG["arrow_color"], CONFIG["arrow_width"],
                        CONFIG["arrow_head_size"])

    @staticmethod
    def _edge_exit(src: StationView, dst: StationView) -> Tuple[float, float]:
        dx = dst.cx - src.cx
        dy = dst.cy - src.cy
        if abs(dx) > abs(dy):
            return src.right_centre if dx > 0 else src.left_centre
        else:
            return src.bottom_centre if dy > 0 else src.top_centre

    @staticmethod
    def _edge_entry(dst: StationView, src: StationView) -> Tuple[float, float]:
        dx = src.cx - dst.cx
        dy = src.cy - dst.cy
        if abs(dx) > abs(dy):
            return dst.right_centre if dx > 0 else dst.left_centre
        else:
            return dst.bottom_centre if dy > 0 else dst.top_centre

    def _draw_hud(self, surf: pygame.Surface) -> None:
        rp = self.replayer
        y = 8
        hfont = self._fonts["hud"]
        sw = surf.get_width()

        # Simulation time
        t_val = rp.sim_time if rp else 0.0
        time_str = f"Sim t = {t_val:8.1f} s"
        surf.blit(hfont.render(time_str, True, CONFIG["hud_color"]), (10, y))

        # Speed
        speed_str = f"Speed: {self.playback_speed:.2f}×"
        surf.blit(hfont.render(speed_str, True, CONFIG["hud_color"]), (250, y))

        # Paused
        if rp and rp.paused:
            surf.blit(hfont.render("⏸  PAUSED", True, (255, 200, 80)), (420, y))
        else:
            surf.blit(hfont.render("▶  PLAYING", True, (120, 220, 140)), (420, y))

        # Anim
        anim_lbl = "Anim: ON" if self.anim_enabled else "Anim: OFF"
        surf.blit(hfont.render(anim_lbl, True, CONFIG["hud_color"]), (600, y))

        # Progress
        if rp:
            pct = rp.progress * 100
            prog_str = f"Events: {rp.idx}/{len(rp.events)}  ({pct:.0f}%)"
            surf.blit(hfont.render(prog_str, True, CONFIG["hud_color"]), (750, y))

        # Controls hint
        hint = "SPACE:pause  ↑↓:speed  ←→:step  A:anim  R:restart  L:labels  ESC:quit"
        hint_surf = self._fonts["small"].render(hint, True, (100, 110, 130))
        surf.blit(hint_surf, (10, y + 22))

        # Progress bar
        if rp:
            bar_y = y + 42
            bar_w = sw - 20
            bar_h = 4
            pygame.draw.rect(surf, (50, 55, 65), (10, bar_y, bar_w, bar_h), border_radius=2)
            fill_w = max(1, int(bar_w * rp.progress))
            pygame.draw.rect(surf, (80, 160, 255), (10, bar_y, fill_w, bar_h), border_radius=2)

    def _init_fonts(self) -> None:
        self._fonts = {
            "station": pygame.font.SysFont("consolas,monospace", CONFIG["station_font_size"]),
            "token":   pygame.font.SysFont("consolas,monospace", CONFIG["token_font_size"]),
            "small":   pygame.font.SysFont("consolas,monospace", 10),
            "hud":     pygame.font.SysFont("segoeui,arial", CONFIG["hud_font_size"]),
            "res":     pygame.font.SysFont("consolas,monospace", CONFIG["res_font_size"]),
            "anno":    pygame.font.SysFont("consolas,monospace", CONFIG["anno_font_size"]),
        }


# ═══════════════════════════════════════════════════════════════════════════
#  Drawing helpers
# ═══════════════════════════════════════════════════════════════════════════

def _draw_rounded_rect(
    surf: pygame.Surface, rect: pygame.Rect,
    color: Tuple[int, int, int], radius: int, width: int = 0
) -> None:
    """Draw a rounded rectangle (filled or outline)."""
    pygame.draw.rect(surf, color, rect, width=width, border_radius=radius)


def _brighten(color: Tuple[int, int, int], amount: int) -> Tuple[int, int, int]:
    return tuple(min(255, c + amount) for c in color)  # type: ignore[return-value]


def _utilization_color(frac: float) -> Tuple[int, int, int]:
    """Green → yellow → red as utilisation goes 0→1."""
    if frac < 0.5:
        t = frac * 2
        return (int(80 + 175 * t), int(200 - 80 * t), 80)
    else:
        t = (frac - 0.5) * 2
        return (int(255), int(120 - 120 * t), int(80 - 60 * t))


def _draw_arrow(
    surf: pygame.Surface,
    start: Tuple[float, float], end: Tuple[float, float],
    color: Tuple[int, int, int], width: int, head_size: int,
) -> None:
    """Draw a line with an arrowhead."""
    sx, sy = start
    ex, ey = end
    pygame.draw.line(surf, color, (int(sx), int(sy)), (int(ex), int(ey)), width)
    # Arrowhead
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy)
    if length < 1:
        return
    dx /= length
    dy /= length
    # Two arrowhead lines
    perp_x, perp_y = -dy, dx
    ax1 = ex - head_size * dx + head_size * 0.5 * perp_x
    ay1 = ey - head_size * dy + head_size * 0.5 * perp_y
    ax2 = ex - head_size * dx - head_size * 0.5 * perp_x
    ay2 = ey - head_size * dy - head_size * 0.5 * perp_y
    pygame.draw.polygon(surf, color, [
        (int(ex), int(ey)), (int(ax1), int(ay1)), (int(ax2), int(ay2))
    ])


def _draw_token(
    surf: pygame.Surface, tok: TokenState,
    fonts: Dict[str, pygame.font.Font],
    highlight: bool = False,
) -> None:
    """Render a single token circle with badges."""
    r = CONFIG["token_radius"]
    ix, iy = int(tok.x), int(tok.y)
    data = tok.data or {}
    ttype = data.get("type", "phone")
    ptype = data.get("ptype", "")

    # Determine colour
    if ttype == "part" and ptype in TOKEN_PTYPE_COLORS:
        color = TOKEN_PTYPE_COLORS[ptype]
    else:
        color = TOKEN_TYPE_COLORS.get(ttype, (160, 160, 160))

    # Glow for animating tokens
    if highlight:
        glow = tuple(min(255, c + 60) for c in color)
        pygame.draw.circle(surf, glow, (ix, iy), r + 3)

    # Main circle
    pygame.draw.circle(surf, color, (ix, iy), r)
    pygame.draw.circle(surf, _brighten(color, 50), (ix, iy), r, 1)

    # Inner label (ptype abbreviation or type initial)
    if ttype == "part":
        label = PTYPE_ABBREV.get(ptype, "?")
    elif ttype == "phone":
        kind = data.get("kind", "")
        label = "iP" if kind == "iPhone" else ("A" if kind == "Android" else "Ph")
    elif ttype == "battery":
        label = "B"
    elif ttype == "done":
        label = "✓"
    else:
        label = "?"

    lbl_surf = fonts["token"].render(label, True, (255, 255, 255))
    surf.blit(lbl_surf, lbl_surf.get_rect(center=(ix, iy)))

    # Badges (top-right quadrant, stacked)
    badge_x = ix + r + 1
    badge_y = iy - r - 1
    badges: List[str] = []
    if data.get("flipped"):
        badges.append("↻")
    if data.get("cooled"):
        badges.append("❄")
    if data.get("battery_removed"):
        badges.append("✓B")

    conf = data.get("conf")
    if conf is not None:
        badges.append(f"{conf:.2f}")

    for bi, badge_text in enumerate(badges):
        bs = fonts["token"].render(badge_text, True, (255, 240, 180))
        surf.blit(bs, (badge_x, badge_y + bi * 10))

    # Confidence bar (if present and low)
    if conf is not None and conf < 0.8:
        bar_w = int(r * 2 * conf)
        bar_rect = pygame.Rect(ix - r, iy + r + 2, bar_w, 3)
        pygame.draw.rect(surf, (255, 80, 80), bar_rect)


# ═══════════════════════════════════════════════════════════════════════════
#  DEMO: synthetic event log for testing
# ═══════════════════════════════════════════════════════════════════════════

def generate_demo_events(
    n_phones: int = 8,
    p_iphone: float = 0.35,
    interarrival: float = 20.0,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Generate a synthetic event log matching the RAISE process.

    This exercises every station in the visualizer, including the cutting
    sub-steps, sorting, flipping, cooling, and hammer separation.
    """
    import random as _rng
    _rng.seed(seed)

    events: List[Dict[str, Any]] = []
    t = 0.0
    token_id_counter = 0

    def _eid() -> int:
        nonlocal token_id_counter
        token_id_counter += 1
        return token_id_counter

    for phone_idx in range(n_phones):
        kind = "iPhone" if _rng.random() < p_iphone else "Android"
        phone_tok = {
            "type": "phone",
            "phone_id": phone_idx,
            "kind": kind,
        }
        pid = _eid()

        # 1. Inject into collection_unit
        events.append({"t": t, "kind": "inject", "dst": "collection_unit",
                        "token_id": pid, "token": dict(phone_tok)})

        # 2. Move through cutting sub-stages
        cutting_stages = [
            "collection_unit", "transfer_to_cutting", "cut_conveyor_stage1",
            "fixture_clamped", "cut_sawpair_A", "transfer_between_sawpairs",
            "cut_sawpair_B", "cut_complete", "stacked_face_down",
        ]
        ct = t + 1.0
        for i in range(len(cutting_stages) - 1):
            src = cutting_stages[i]
            dst = cutting_stages[i + 1]
            dur = 3.0 if "sawpair" in dst else 1.0
            events.append({"t": ct, "kind": "move", "src": src, "dst": dst,
                            "token_id": pid, "token": dict(phone_tok)})
            # Resource events for saw
            if "sawpair" in dst:
                events.append({"t": ct, "kind": "fire_start",
                                "transition": dst, "resources": {"saw": 1}})
                events.append({"t": ct + dur, "kind": "fire_end",
                                "transition": dst, "resources": {"saw": 0}})
            ct += dur

        # At stacked_face_down, phone splits into parts
        cut_done_t = ct

        # Generate parts
        if kind == "iPhone":
            parts = [
                {"type": "part", "phone_id": phone_idx, "ptype": "iphone_case",
                 "battery_target": True, "conf": round(_rng.uniform(0.7, 0.99), 2)},
                {"type": "part", "phone_id": phone_idx, "ptype": "middle",
                 "battery_target": False, "conf": round(_rng.uniform(0.8, 0.99), 2)},
            ]
        else:
            parts = [
                {"type": "part", "phone_id": phone_idx, "ptype": "normal_case",
                 "battery_target": False, "conf": round(_rng.uniform(0.75, 0.99), 2)},
                {"type": "part", "phone_id": phone_idx, "ptype": "middle",
                 "battery_target": True, "conf": round(_rng.uniform(0.85, 0.99), 2)},
            ]
        parts += [
            {"type": "part", "phone_id": phone_idx, "ptype": "screen",
             "battery_target": False, "conf": round(_rng.uniform(0.8, 0.99), 2)},
            {"type": "part", "phone_id": phone_idx, "ptype": "film",
             "battery_target": False, "conf": round(_rng.uniform(0.6, 0.99), 2)},
        ]

        pt = cut_done_t + 0.5
        for part in parts:
            part_id = _eid()

            # 3. Vision scan
            events.append({"t": pt, "kind": "move",
                            "src": "stacked_face_down", "dst": "vision_scan",
                            "token_id": part_id, "token": dict(part)})
            pt += 1.5

            # Check confidence – uncertain?
            conf = part.get("conf", 1.0)
            if conf < 0.8:
                events.append({"t": pt, "kind": "move",
                                "src": "vision_scan", "dst": "vision_uncertain",
                                "token_id": part_id, "token": dict(part),
                                "note": "low conf"})
                pt += 2.0
                # Rescan
                events.append({"t": pt, "kind": "move",
                                "src": "vision_uncertain", "dst": "rescan_queue",
                                "token_id": part_id, "token": dict(part)})
                pt += 1.0
                part["conf"] = round(_rng.uniform(0.82, 0.99), 2)
                events.append({"t": pt, "kind": "move",
                                "src": "rescan_queue", "dst": "vision_scan",
                                "token_id": part_id, "token": dict(part)})
                pt += 1.0

            # 4. Robot sorting
            events.append({"t": pt, "kind": "move",
                            "src": "vision_scan", "dst": "robot_sorting",
                            "token_id": part_id, "token": dict(part)})
            events.append({"t": pt, "kind": "fire_start",
                            "transition": "robot_sorting",
                            "resources": {"ur5": 1}})
            pt += 2.5
            events.append({"t": pt, "kind": "fire_end",
                            "transition": "robot_sorting",
                            "resources": {"ur5": 0}})

            ptype = part["ptype"]
            is_high = ptype in ("middle", "iphone_case")
            sort_dst = "high_value_buffer" if is_high else "low_value_bin"
            events.append({"t": pt, "kind": "move",
                            "src": "robot_sorting", "dst": sort_dst,
                            "token_id": part_id, "token": dict(part)})
            pt += 0.5

            if not is_high:
                continue   # low-value → done

            # 5. iPhone case → flip loop
            if ptype == "iphone_case":
                events.append({"t": pt, "kind": "move",
                                "src": "high_value_buffer", "dst": "to_flip",
                                "token_id": part_id, "token": dict(part)})
                pt += 0.5
                events.append({"t": pt, "kind": "move",
                                "src": "to_flip", "dst": "flip_station",
                                "token_id": part_id, "token": dict(part)})
                events.append({"t": pt, "kind": "fire_start",
                                "transition": "flip", "resources": {"ur5": 1}})
                pt += 4.0
                part["flipped"] = True
                events.append({"t": pt, "kind": "fire_end",
                                "transition": "flip", "resources": {"ur5": 0}})
                events.append({"t": pt, "kind": "move",
                                "src": "flip_station", "dst": "flipped_buffer",
                                "token_id": part_id, "token": dict(part)})
                pt += 0.5
                events.append({"t": pt, "kind": "move",
                                "src": "flipped_buffer", "dst": "high_value_buffer",
                                "token_id": part_id, "token": dict(part)})
                pt += 0.5

            # 6. Route battery targets to cooling
            if part.get("battery_target"):
                events.append({"t": pt, "kind": "move",
                                "src": "high_value_buffer", "dst": "to_cool",
                                "token_id": part_id, "token": dict(part)})
                pt += 0.5
                events.append({"t": pt, "kind": "move",
                                "src": "to_cool", "dst": "cooling_chamber",
                                "token_id": part_id, "token": dict(part)})
                events.append({"t": pt, "kind": "fire_start",
                                "transition": "cooling",
                                "resources": {"cooler": 1}})
                pt += 30.0
                part["cooled"] = True
                events.append({"t": pt, "kind": "fire_end",
                                "transition": "cooling",
                                "resources": {"cooler": 0}})
                events.append({"t": pt, "kind": "move",
                                "src": "cooling_chamber", "dst": "cooled_buffer",
                                "token_id": part_id, "token": dict(part)})
                pt += 0.5

                # 7. Hammer
                events.append({"t": pt, "kind": "move",
                                "src": "cooled_buffer", "dst": "hammer_station",
                                "token_id": part_id, "token": dict(part)})
                events.append({"t": pt, "kind": "fire_start",
                                "transition": "hammer",
                                "resources": {"hammer": 1}})
                pt += 1.0
                part["battery_removed"] = True
                events.append({"t": pt, "kind": "fire_end",
                                "transition": "hammer",
                                "resources": {"hammer": 0}})

                # Battery token
                bat_id = _eid()
                bat_tok = {"type": "battery", "phone_id": phone_idx}
                events.append({"t": pt, "kind": "move",
                                "src": "hammer_station", "dst": "battery_bin",
                                "token_id": bat_id, "token": bat_tok})

                # Remainder
                events.append({"t": pt + 0.1, "kind": "move",
                                "src": "hammer_station", "dst": "remainder_bin",
                                "token_id": part_id, "token": dict(part)})
                pt += 0.5

                # Finished
                done_id = _eid()
                done_tok = {"type": "done", "phone_id": phone_idx}
                events.append({"t": pt, "kind": "move",
                                "src": "remainder_bin", "dst": "finished",
                                "token_id": done_id, "token": done_tok})

        t += interarrival

    # Sort by time
    events.sort(key=lambda e: e["t"])
    return events


# ═══════════════════════════════════════════════════════════════════════════
#  CLI entry-point
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAISE CTPN Visualizer — Pygame-based replay of "
                    "demanufacturing simulation events."
    )
    parser.add_argument("--log", type=str, default=None,
                        help="Path to JSON event-log file.")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Initial playback speed multiplier (default 1.0).")
    parser.add_argument("--no-anim", action="store_true",
                        help="Disable token movement animations.")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="Scale factor for station positions (default 1.0).")
    args = parser.parse_args()

    if args.log:
        with open(args.log, "r") as f:
            events = json.load(f)
        print(f"Loaded {len(events)} events from {args.log}")
    else:
        print("No --log provided; generating demo event log …")
        events = generate_demo_events()
        print(f"Generated {len(events)} demo events for 8 phones.")

    viz = RaiseVisualizer(
        events=events,
        playback_speed=args.speed,
        anim_enabled=not args.no_anim,
        scale=args.scale,
    )
    viz.run()


if __name__ == "__main__":
    main()
