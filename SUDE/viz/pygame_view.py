"""
viz/pygame_view.py – Pygame-based visualization of the SUDE DES.

Renders:
* station boxes with labels, busy/idle indicators, queue counts
* animated laptop tokens moving between stations
* real-time metrics panel
* keyboard controls (pause, speed, step, reset)

The view is **decoupled** from the simulation core: it receives
state-change messages via ``AnimManager`` and reads metrics from
``MetricsCollector``.
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING, Optional

try:
    import pygame
    import pygame.freetype
except ImportError:
    pygame = None  # headless mode OK

from viz.anim import AnimManager, station_for_state

if TYPE_CHECKING:
    from sim.core import Simulator, Event
    from sim.model import World
    from outputs.metrics import MetricsCollector


# ── Colour palette ───────────────────────────────────────────────────────

_BG       = (24,  26,  32)
_PANEL_BG = (34,  38,  48)
_STATION_IDLE  = (50, 58, 72)
_STATION_BUSY  = (70, 110, 160)
_STATION_BORDER = (90, 100, 120)
_TEXT     = (220, 225, 235)
_DIM_TEXT = (140, 145, 155)
_ACCENT   = (80, 200, 255)
_GREEN    = (80, 220, 120)
_RED      = (255, 90, 90)
_YELLOW   = (255, 200, 60)

# ── Station labels ───────────────────────────────────────────────────────

_STATION_LABELS = {
    "ARRIVAL":    "S0  Arrival",
    "IMAGING":    "S1  Imaging",
    "RETRIEVAL":  "S2  Retrieval",
    "LOOKUP":     "S3  Lookup / DB",
    "AUTOMATION": "S4  Robot Cell",
    "HANDOVER":   "S5  Handover",
    "MANUAL":     "S6/S7 Manual",
    "LOGGING":    "S8  Logging",
    "EXIT":       "Exit",
}

# ── Flow arrows (from → to) ─────────────────────────────────────────────

_FLOW_EDGES = [
    ("ARRIVAL",   "IMAGING"),
    ("IMAGING",   "RETRIEVAL"),
    ("RETRIEVAL", "LOOKUP"),
    ("RETRIEVAL", "MANUAL"),
    ("LOOKUP",    "AUTOMATION"),
    ("AUTOMATION","HANDOVER"),
    ("AUTOMATION","MANUAL"),
    ("HANDOVER",  "LOGGING"),
    ("MANUAL",    "LOGGING"),
    ("LOGGING",   "EXIT"),
]


class PygameView:
    """Main visualization class."""

    def __init__(self, cfg: dict, world: "World",
                 metrics: "MetricsCollector") -> None:
        if pygame is None:
            raise RuntimeError("pygame is not installed")

        self.cfg = cfg
        self.world = world
        self.metrics = metrics

        viz = cfg.get("visualization", {})
        self.width = viz.get("screen_width", 1400)
        self.height = viz.get("screen_height", 800)
        self.fps = viz.get("fps", 60)
        self.sim_speed = viz.get("default_sim_speed", 20.0)
        self.token_radius = viz.get("token_radius", 12)

        raw_positions = viz.get("station_positions", {})
        self.station_positions = {
            k: tuple(v) for k, v in raw_positions.items()
        }
        sw, sh = viz.get("station_size", [130, 60])
        self.station_size = (sw, sh)

        self.anim = AnimManager(
            self.station_positions,
            viz.get("token_move_duration_ms", 400),
        )

        # state
        self.paused = False
        self.running = True
        self.sim_time_target = 0.0

        # camera state (pan & zoom)
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.zoom = 1.0
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_start_cam_x = 0.0
        self.drag_start_cam_y = 0.0

        # pygame init
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("SUDE Laptop Pilot – DES Visualization")
        self.clock = pygame.time.Clock()

        # fonts
        self.font_sm = pygame.font.SysFont("Consolas", 13)
        self.font_md = pygame.font.SysFont("Consolas", 15)
        self.font_lg = pygame.font.SysFont("Consolas", 18, bold=True)
        self.font_title = pygame.font.SysFont("Consolas", 22, bold=True)

    # ── sim ↔ viz coupling ───────────────────────────────────────────────

    def on_sim_event(self, sim: "Simulator", ev: "Event") -> None:
        """Callback registered on the simulator."""
        laptop = sim.world.laptops.get(ev.laptop_id)
        if laptop is not None:
            self.anim.on_state_change(laptop.id, laptop.state)

    def run_loop(self, sim: "Simulator") -> None:
        """Main render + sim-advance loop at wall-clock FPS."""
        last_wall = time.monotonic()
        snapshot_interval = 30.0  # sim-seconds between metric snapshots
        next_snapshot = snapshot_interval

        while self.running:
            dt_wall = time.monotonic() - last_wall
            last_wall = time.monotonic()

            # ── handle input ──
            self._handle_events(sim)

            # ── advance simulation ──
            if not self.paused:
                self.sim_time_target += dt_wall * self.sim_speed
                while sim.queue and sim.queue.peek() is not None:
                    nxt = sim.queue.peek()
                    if nxt.time > self.sim_time_target:
                        break
                    sim.step_next_event()

                    # periodic snapshot
                    if sim.now >= next_snapshot:
                        self.metrics.snapshot(sim.now, sim.world)
                        next_snapshot = sim.now + snapshot_interval

                sim.now = self.sim_time_target

            # ── cleanup old tokens ──
            self.anim.cleanup_departed(keep_recent=3)

            # ── render ──
            self._render(sim)

            self.clock.tick(self.fps)

        pygame.quit()

    # ── input ────────────────────────────────────────────────────────────

    def _handle_events(self, sim: "Simulator") -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    self.sim_speed = min(self.sim_speed * 1.5, 5000)
                elif event.key == pygame.K_MINUS:
                    self.sim_speed = max(self.sim_speed / 1.5, 0.5)
                elif event.key == pygame.K_s and self.paused:
                    sim.step_next_event()
                elif event.key == pygame.K_r:
                    mods = pygame.key.get_mods()
                    if mods & pygame.KMOD_SHIFT:
                        import random
                        new_seed = random.randint(0, 999999)
                        self._reset(sim, new_seed)
                    else:
                        self._reset(sim, sim.seed)
                elif event.key == pygame.K_ESCAPE:
                    self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 2:  # middle mouse button
                    self.dragging = True
                    self.drag_start_x, self.drag_start_y = event.pos
                    self.drag_start_cam_x = self.camera_x
                    self.drag_start_cam_y = self.camera_y
                elif event.button == 4:  # scroll up (zoom in)
                    mouse_x, mouse_y = event.pos
                    self._zoom_at(mouse_x, mouse_y, 1.1)
                elif event.button == 5:  # scroll down (zoom out)
                    mouse_x, mouse_y = event.pos
                    self._zoom_at(mouse_x, mouse_y, 0.9)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 2:  # middle mouse button
                    self.dragging = False
            elif event.type == pygame.MOUSEMOTION:
                if self.dragging:
                    mouse_x, mouse_y = event.pos
                    dx = mouse_x - self.drag_start_x
                    dy = mouse_y - self.drag_start_y
                    self.camera_x = self.drag_start_cam_x + dx
                    self.camera_y = self.drag_start_cam_y + dy

    def _zoom_at(self, mouse_x: int, mouse_y: int, factor: float) -> None:
        """Zoom in/out centered at mouse position."""
        # Clamp zoom
        new_zoom = self.zoom * factor
        new_zoom = max(0.3, min(new_zoom, 3.0))
        
        # Adjust camera to keep mouse point fixed
        # World point = (screen - camera) / zoom
        # We want: (mouse - camera_new) / zoom_new = (mouse - camera_old) / zoom_old
        # So: camera_new = mouse - (mouse - camera_old) * (zoom_new / zoom_old)
        ratio = new_zoom / self.zoom
        self.camera_x = mouse_x - (mouse_x - self.camera_x) * ratio
        self.camera_y = mouse_y - (mouse_y - self.camera_y) * ratio
        self.zoom = new_zoom

    def _reset(self, sim: "Simulator", seed: int) -> None:
        from sim.model import World
        from sim.process import create_process_logic
        from outputs.metrics import MetricsCollector

        sim.reset(seed)
        sim.world = World(self.cfg)
        sim.metrics = MetricsCollector()
        sim._process_logic = create_process_logic()
        self.world = sim.world
        self.metrics = sim.metrics
        self.anim = AnimManager(
            self.station_positions,
            self.cfg.get("visualization", {}).get("token_move_duration_ms", 400),
        )
        sim.add_state_change_listener(self.on_sim_event)
        # seed first arrival
        from sim.core import EventType
        sim.schedule(0.0, EventType.ARRIVAL, laptop_id=-1)
        self.sim_time_target = 0.0
        self.paused = False
        # reset camera
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.zoom = 1.0

    # ── coordinate transforms ────────────────────────────────────────────

    def _world_to_screen(self, x: float, y: float) -> tuple[int, int]:
        """Transform world coordinates to screen coordinates with camera."""
        sx = int(x * self.zoom + self.camera_x)
        sy = int(y * self.zoom + self.camera_y)
        return (sx, sy)

    def _transform_rect(self, x: float, y: float, w: float, h: float) -> pygame.Rect:
        """Transform a rectangle from world to screen space."""
        sx, sy = self._world_to_screen(x, y)
        sw = int(w * self.zoom)
        sh = int(h * self.zoom)
        return pygame.Rect(sx, sy, sw, sh)

    # ── rendering ────────────────────────────────────────────────────────

    def _render(self, sim: "Simulator") -> None:
        self.screen.fill(_BG)

        self._draw_flow_arrows()
        self._draw_stations()
        self._draw_tokens()
        self._draw_metrics_panel(sim)
        self._draw_controls_help()

        pygame.display.flip()

    # ── stations ─────────────────────────────────────────────────────────

    def _draw_stations(self) -> None:
        sw, sh = self.station_size
        for station, pos in self.station_positions.items():
            x, y = pos[0], pos[1]
            rect = self._transform_rect(x, y, sw, sh)

            # busy?
            res = self._resource_for_station(station)
            is_busy = res is not None and not res.is_idle
            bg = _STATION_BUSY if is_busy else _STATION_IDLE
            pygame.draw.rect(self.screen, bg, rect, border_radius=max(1, int(6 * self.zoom)))
            pygame.draw.rect(self.screen, _STATION_BORDER, rect, width=max(1, int(2 * self.zoom)),
                             border_radius=max(1, int(6 * self.zoom)))

            # label (scale font or skip if too small)
            if self.zoom > 0.4:
                label = _STATION_LABELS.get(station, station)
                surf = self.font_sm.render(label, True, _TEXT)
                sx, sy = self._world_to_screen(x + 5, y + 4)
                self.screen.blit(surf, (sx, sy))

            # queue count
            q_len = self._queue_length(station)
            if q_len > 0 and self.zoom > 0.4:
                q_surf = self.font_sm.render(f"Q:{q_len}", True, _YELLOW)
                sx, sy = self._world_to_screen(x + sw - 40, y + sh - 18)
                self.screen.blit(q_surf, (sx, sy))

            # busy indicator dot
            if res is not None:
                dot_color = _GREEN if res.is_idle else _RED
                dot_x, dot_y = self._world_to_screen(x + sw - 10, y + 12)
                dot_r = max(2, int(5 * self.zoom))
                pygame.draw.circle(self.screen, dot_color, (dot_x, dot_y), dot_r)

    def _resource_for_station(self, station: str):
        mapping = {
            "IMAGING":    "camera",
            "RETRIEVAL":  "retrieval",
            "AUTOMATION": "robot",
            "HANDOVER":   "operator",
            "MANUAL":     "operator",
        }
        key = mapping.get(station)
        if key:
            return self.world.resources.get(key)
        return None

    def _queue_length(self, station: str) -> int:
        res = self._resource_for_station(station)
        return res.queue_length if res else 0

    # ── flow arrows ──────────────────────────────────────────────────────

    def _draw_flow_arrows(self) -> None:
        sw, sh = self.station_size
        for src, dst in _FLOW_EDGES:
            sp = self.station_positions.get(src)
            dp = self.station_positions.get(dst)
            if sp and dp:
                sx_w = sp[0] + sw
                sy_w = sp[1] + sh / 2
                dx_w = dp[0]
                dy_w = dp[1] + sh / 2
                
                sx, sy = self._world_to_screen(sx_w, sy_w)
                dx, dy = self._world_to_screen(dx_w, dy_w)
                
                line_width = max(1, int(2 * self.zoom))
                pygame.draw.line(self.screen, (60, 65, 80),
                                 (sx, sy), (dx, dy), line_width)
                # arrowhead
                import math
                angle = math.atan2(dy - sy, dx - sx)
                alen = max(4, int(8 * self.zoom))
                for sign in (1, -1):
                    ax = dx - alen * math.cos(angle - sign * 0.4)
                    ay = dy - alen * math.sin(angle - sign * 0.4)
                    pygame.draw.line(self.screen, (60, 65, 80),
                                     (dx, dy), (int(ax), int(ay)), line_width)

    # ── tokens ───────────────────────────────────────────────────────────

    def _draw_tokens(self) -> None:
        r = max(2, int(self.token_radius * self.zoom))
        for tok in self.anim.tokens.values():
            if tok.departed and not tok.is_moving:
                continue
            pos = tok.interpolated_pos()
            x, y = self._world_to_screen(pos[0], pos[1])
            pygame.draw.circle(self.screen, tok.color, (x, y), r)
            pygame.draw.circle(self.screen, (255, 255, 255), (x, y), r, 1)
            # id text (only if zoom is reasonable)
            if self.zoom > 0.5:
                id_surf = self.font_sm.render(str(tok.laptop_id), True,
                                              (255, 255, 255))
                tw, th = id_surf.get_size()
                self.screen.blit(id_surf, (x - tw // 2, y - th // 2))

    # ── metrics panel ────────────────────────────────────────────────────

    def _draw_metrics_panel(self, sim: "Simulator") -> None:
        panel_w = 320
        panel_h = self.height
        px = self.width - panel_w
        panel_rect = pygame.Rect(px, 0, panel_w, panel_h)
        pygame.draw.rect(self.screen, _PANEL_BG, panel_rect)
        pygame.draw.line(self.screen, _STATION_BORDER,
                         (px, 0), (px, panel_h), 2)

        x = px + 12
        y = 14

        # title
        title = self.font_title.render("SUDE DES  Metrics", True, _ACCENT)
        self.screen.blit(title, (x, y)); y += 32

        m = self.metrics
        lines = [
            ("Sim time",          f"{sim.now:,.0f} s  ({sim.now/3600:.1f} h)"),
            ("Seed",              str(sim.seed)),
            ("Speed",             f"×{self.sim_speed:.1f}"
                                  + ("  ⏸ PAUSED" if self.paused else "")),
            "",
            ("Arrivals",          str(m.total_arrivals)),
            ("Departures",        str(m.total_departures)),
            ("Throughput",        f"{m.throughput_per_hour:.1f}  /h"),
            ("WIP",               str(m.current_wip(self.world))),
            "",
            ("Retrieval ratio",   f"{m.retrieval_ratio:.1%}"),
            ("Auto success",      f"{m.automation_success_ratio:.1%}"),
            ("DB size",           str(self.world.db.size())),
            ("Onboardings",       str(m.onboarding_count)),
            "",
            ("Avg cycle time",    f"{m.avg_cycle_time:.1f} s"),
            ("p50 cycle time",    f"{m.p50_cycle_time:.1f} s"),
            ("p95 cycle time",    f"{m.p95_cycle_time:.1f} s"),
        ]

        # resource utilisation
        lines.append("")
        lines.append(("── Resources ──", ""))
        for rname, res in self.world.resources.items():
            util = res.utilization
            lines.append((
                f"  {res.name}",
                f"{res.busy}/{res.capacity}  util {util:.0%}  Q:{res.queue_length}"
            ))

        for item in lines:
            if item == "":
                y += 8
                continue
            label, value = item
            if value == "":
                lbl = self.font_md.render(label, True, _ACCENT)
                self.screen.blit(lbl, (x, y))
            else:
                lbl = self.font_sm.render(label, True, _DIM_TEXT)
                val = self.font_sm.render(value, True, _TEXT)
                self.screen.blit(lbl, (x, y))
                self.screen.blit(val, (x + 155, y))
            y += 19

        # sparkline: retrieval ratio over time
        y += 12
        self._draw_sparkline(
            x, y, panel_w - 24,
            [r for _, r in m._retrieval_log[-200:]],
            label="Recognition (last 200)",
            bool_mode=True,
        )

    def _draw_sparkline(self, x: int, y: int, w: int,
                        data: list, label: str = "",
                        bool_mode: bool = False) -> None:
        if not data:
            return
        lbl = self.font_sm.render(label, True, _DIM_TEXT)
        self.screen.blit(lbl, (x, y))
        y += 16
        h = 30
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, (40, 44, 55), rect)

        if bool_mode:
            # rolling window bar chart
            bucket_size = max(1, len(data) // w)
            bx = x
            for i in range(0, len(data), bucket_size):
                bucket = data[i:i + bucket_size]
                ratio = sum(1 for v in bucket if v) / max(len(bucket), 1)
                bar_h = int(ratio * h)
                color = _GREEN if ratio > 0.7 else (_YELLOW if ratio > 0.4 else _RED)
                pygame.draw.line(self.screen, color,
                                 (bx, y + h), (bx, y + h - bar_h), 1)
                bx += 1
                if bx >= x + w:
                    break

    # ── controls help ────────────────────────────────────────────────────

    def _draw_controls_help(self) -> None:
        lines = [
            "Space: pause/resume",
            "+/-: speed",
            "S: step (paused)",
            "Mouse wheel: zoom",
            "Middle click + drag: pan",
            "R: reset / Shift+R: new seed",
            "Esc: quit",
        ]
        y = self.height - len(lines) * 16 - 8
        x = 10
        for line in lines:
            surf = self.font_sm.render(line, True, _DIM_TEXT)
            self.screen.blit(surf, (x, y))
            y += 16
