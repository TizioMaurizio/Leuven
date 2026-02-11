"""
viz/pygame_app.py – Main Pygame loop that steps SimPy and renders frames.

The Pygame loop **owns the main thread**.  On each frame it:
  1. Handles input (pause, reset, speed changes).
  2. Advances SimPy by ``sim_dt * speed_multiplier`` seconds.
  3. Drains pending events from the EventBus deque → updates VisualState.
  4. Draws the scene.

This keeps everything single-threaded and deterministic.
"""

from __future__ import annotations

import sys
import time
from typing import Any

import numpy as np
import pygame
import simpy

from config.loader import load_config, Cfg
from sim.entities import EventBus
from sim.system import build_system, SystemContext
from sim.monitor import Monitor
from viz.state import VisualState
from viz.scene import SceneRenderer
from viz import binding


# ---------------------------------------------------------------------------
# Main visualisation entry point
# ---------------------------------------------------------------------------

def run_viz(
    cfg: Cfg | None = None,
    overrides: dict | None = None,
) -> None:
    """Launch the Pygame visualisation with an embedded SimPy simulation."""

    if cfg is None:
        cfg = load_config(overrides=overrides)

    viz_cfg = cfg.viz

    # -- Pygame init --------------------------------------------------------
    pygame.init()
    width = getattr(viz_cfg, "window_width", 1400)
    height = getattr(viz_cfg, "window_height", 700)
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Daisy DES – Pygame Visualisation")
    clock = pygame.time.Clock()
    fps = viz_cfg.fps

    # -- Sim init -----------------------------------------------------------
    rng = np.random.default_rng(cfg.sim.random_seed)
    env = simpy.Environment()
    bus = EventBus()
    ctx = build_system(env, cfg, bus, rng)
    monitor = Monitor(ctx)
    monitor.start_sampler()

    # -- Visual state -------------------------------------------------------
    vs = VisualState()
    binding.init_positions(cfg)

    renderer = SceneRenderer(cfg)
    move_dur = viz_cfg.token.move_duration_ms

    # -- Loop state ---------------------------------------------------------
    paused = False
    speed = viz_cfg.speed_multiplier
    base_dt = viz_cfg.base_sim_dt
    horizon = cfg.sim.time_horizon
    running = True

    while running:
        # 1. Input ----------------------------------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    paused = not paused

                elif event.key == pygame.K_r:
                    # Reset simulation
                    rng = np.random.default_rng(cfg.sim.random_seed)
                    env = simpy.Environment()
                    bus = EventBus()
                    ctx = build_system(env, cfg, bus, rng)
                    monitor = Monitor(ctx)
                    monitor.start_sampler()
                    vs = VisualState()
                    binding.init_positions(cfg)

                elif event.key == pygame.K_UP:
                    speed = min(speed * 2, 10000)

                elif event.key == pygame.K_DOWN:
                    speed = max(speed / 2, 1)

                elif event.key == pygame.K_s:
                    monitor.flush()
                    print(f"[viz] Saved run artefacts to {monitor.output_dir}")

        # 2. Step simulation ------------------------------------------------
        if not paused and env.now < horizon:
            step = base_dt * speed
            target = min(env.now + step, horizon)
            try:
                env.run(until=target)
            except simpy.core.EmptySchedule:
                pass

        # 3. Consume events → update visual state --------------------------
        binding.consume_pending(vs, bus.queue,
                                max_per_frame=2000,
                                move_duration_ms=move_dur)

        # Update utilisation from monitor snapshot
        snap = monitor.live_snapshot()
        for rname, info in snap.get("util", {}).items():
            cap = info["capacity"]
            vs.utilization[rname] = info["in_use"] / cap if cap > 0 else 0.0

        # 4. Render ---------------------------------------------------------
        renderer.draw(screen, vs, paused, speed)
        renderer.draw_outputs(screen, vs)
        pygame.display.flip()
        clock.tick(fps)

    # -- Cleanup ------------------------------------------------------------
    monitor.flush()
    pygame.quit()
