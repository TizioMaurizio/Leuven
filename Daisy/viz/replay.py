"""
viz/replay.py – Replay a recorded events.csv without running SimPy.

Reads the CSV log line-by-line and feeds events into the same VisualState +
SceneRenderer, replaying token movements deterministically.

Usage
-----
    python -m viz.replay runs/run_001/events.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from typing import Any

import pygame

from config.loader import load_config, Cfg
from viz.state import VisualState
from viz.scene import SceneRenderer
from viz import binding


def replay(events_csv: str, cfg: Cfg | None = None, speed: float = 10.0) -> None:
    """Replay an events CSV in Pygame."""

    if cfg is None:
        cfg = load_config()

    viz_cfg = cfg.viz

    # -- Load events --------------------------------------------------------
    with open(events_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        events: list[dict[str, Any]] = []
        for row in reader:
            evt: dict[str, Any] = {
                "t": float(row["t"]) if row.get("t") else 0.0,
                "device_id": int(row["device_id"]) if row.get("device_id") else None,
                "event": row.get("event", ""),
                "station": row.get("station", ""),
                "model_class": row.get("model_class", ""),
                "damage_state": row.get("damage_state", ""),
                "battery_state": row.get("battery_state", ""),
                "exceptions": json.loads(row.get("exceptions", "[]")),
                "extra": json.loads(row.get("extra_json", "{}")),
            }
            events.append(evt)

    if not events:
        print("No events found in", events_csv)
        return

    print(f"[replay] Loaded {len(events)} events, t=[{events[0]['t']:.0f}, {events[-1]['t']:.0f}]")

    # -- Pygame init --------------------------------------------------------
    pygame.init()
    width = getattr(viz_cfg, "window_width", 1400)
    height = getattr(viz_cfg, "window_height", 700)
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Daisy DES – Replay")
    clock = pygame.time.Clock()
    fps = viz_cfg.fps

    # -- Visual state -------------------------------------------------------
    vs = VisualState()
    binding.init_positions(cfg)
    renderer = SceneRenderer(cfg)
    move_dur = viz_cfg.token.move_duration_ms

    paused = False
    sim_time = 0.0
    event_idx = 0
    base_dt = viz_cfg.base_sim_dt
    running = True

    while running:
        for pg_event in pygame.event.get():
            if pg_event.type == pygame.QUIT:
                running = False
            elif pg_event.type == pygame.KEYDOWN:
                if pg_event.key == pygame.K_SPACE:
                    paused = not paused
                elif pg_event.key == pygame.K_UP:
                    speed = min(speed * 2, 10000)
                elif pg_event.key == pygame.K_DOWN:
                    speed = max(speed / 2, 1)

        # Advance sim_time
        if not paused:
            sim_time += base_dt * speed

        # Feed events up to sim_time
        fed = 0
        while event_idx < len(events) and events[event_idx]["t"] <= sim_time and fed < 2000:
            binding.consume_event(events[event_idx], vs, move_dur)
            event_idx += 1
            fed += 1

        # Render
        renderer.draw(screen, vs, paused, speed)
        renderer.draw_outputs(screen, vs)
        pygame.display.flip()
        clock.tick(fps)

    pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay Daisy DES events")
    parser.add_argument("events_csv", help="Path to events.csv")
    parser.add_argument("--speed", type=float, default=10.0)
    args = parser.parse_args()
    replay(args.events_csv, speed=args.speed)


if __name__ == "__main__":
    main()
