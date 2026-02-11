"""
viz/scene.py – Pygame scene layout and drawing.

Renders stations, queues, tokens, utilization bars, counters,
and a simple rolling throughput plot.
"""

from __future__ import annotations

import math
import time
from typing import Any

import pygame

from viz.state import VisualState, Token


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

COL_BG          = (30,  30,  38)
COL_STATION     = (60,  90, 140)
COL_STATION_EXC = (140, 60,  60)
COL_QUEUE       = (50,  70,  90)
COL_TOKEN_NORM  = (100, 220, 160)
COL_TOKEN_EXC   = (240, 100,  80)
COL_TOKEN_UNK   = (200, 200,  60)
COL_TOKEN_DONE  = (80,  140, 220)
COL_TEXT         = (220, 220, 220)
COL_TEXT_DIM     = (140, 140, 140)
COL_BAR_BG      = (50,  50,  60)
COL_BAR_FILL    = (80, 180, 120)
COL_PLOT_LINE   = (100, 200, 255)
COL_ARROW       = (100, 100, 120)
COL_WHITE       = (255, 255, 255)

STATION_W, STATION_H = 160, 70
QUEUE_W, QUEUE_H     = 140, 40

# Station labels / descriptions
STATION_LABELS: dict[str, str] = {
    "S1": "S1 Infeed+Scan",
    "S2": "S2 Fixture+Display",
    "S3": "S3 -80°C Battery",
    "S4": "S4 Punch-out",
    "S5": "S5 Scrape+Sort",
    "S6": "S6 Pack/Dispatch",
    "E2": "E2 Manual Batt.",
    "E3": "E3 Jam Clear",
}


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _token_colour(tok: Token) -> tuple[int, int, int]:
    if tok.status == "exception":
        return COL_TOKEN_EXC
    if tok.status == "unknown":
        return COL_TOKEN_UNK
    if tok.status == "dispatched":
        return COL_TOKEN_DONE
    return COL_TOKEN_NORM


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * min(max(t, 0.0), 1.0)


def _animate_token(tok: Token, now_ms: float) -> tuple[float, float]:
    """Return interpolated (x, y) for the token."""
    if tok.move_duration <= 0:
        return tok.target_x, tok.target_y
    progress = (now_ms - tok.move_start) / tok.move_duration
    if progress >= 1.0:
        tok.x = tok.target_x
        tok.y = tok.target_y
        return tok.x, tok.y
    return _lerp(tok.x, tok.target_x, progress), _lerp(tok.y, tok.target_y, progress)


# ---------------------------------------------------------------------------
# Scene renderer
# ---------------------------------------------------------------------------

class SceneRenderer:
    """Stateless renderer – draws one frame from a VisualState."""

    def __init__(self, cfg: Any):
        self.cfg = cfg
        viz = cfg.viz
        self.token_radius: int = viz.token.radius
        self.move_dur: float = viz.token.move_duration_ms

        # Precompute positions from config
        self.station_pos: dict[str, tuple[int, int]] = {}
        self.queue_pos: dict[str, tuple[int, int]] = {}

        for name, pos in viz.layout.station_positions.__dict__.items():
            self.station_pos[name] = (int(pos[0]), int(pos[1]))
        for name, pos in viz.layout.queue_positions.__dict__.items():
            self.queue_pos[name] = (int(pos[0]), int(pos[1]))

        # Fonts (initialised on first draw, after pygame.init)
        self._font: pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None
        self._font_lg: pygame.font.Font | None = None

    def _init_fonts(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("consolas", 14)
            self._font_sm = pygame.font.SysFont("consolas", 11)
            self._font_lg = pygame.font.SysFont("consolas", 18)

    # ----- main draw -------------------------------------------------------

    def draw(self, surface: pygame.Surface, vs: VisualState,
             paused: bool, speed: float) -> None:
        self._init_fonts()
        surface.fill(COL_BG)
        now_ms = time.monotonic() * 1000

        self._draw_arrows(surface)
        self._draw_queues(surface, vs)
        self._draw_stations(surface, vs)
        self._draw_tokens(surface, vs, now_ms)
        self._draw_hud(surface, vs, paused, speed)
        self._draw_util_bars(surface, vs)
        self._draw_throughput_plot(surface, vs)

    # ----- arrows between stations -----------------------------------------

    def _draw_arrows(self, surface: pygame.Surface) -> None:
        order = ["S1", "S2", "S3", "S4", "S5", "S6"]
        for i in range(len(order) - 1):
            a = self.station_pos.get(order[i])
            b = self.station_pos.get(order[i + 1])
            if a and b:
                ax = a[0] + STATION_W // 2 + 10
                bx = b[0] - STATION_W // 2 - 10
                y = a[1]
                pygame.draw.line(surface, COL_ARROW, (ax, y), (bx, y), 2)
                # arrowhead
                pygame.draw.polygon(surface, COL_ARROW,
                                    [(bx, y), (bx - 8, y - 5), (bx - 8, y + 5)])

        # Exception arrows S3→E2 and S4→E3
        for src, exc in [("S3", "E2"), ("S4", "E3")]:
            a = self.station_pos.get(src)
            b = self.station_pos.get(exc)
            if a and b:
                pygame.draw.line(surface, COL_TOKEN_EXC,
                                 (a[0], a[1] + STATION_H // 2),
                                 (b[0], b[1] - STATION_H // 2), 1)

    # ----- queues ----------------------------------------------------------

    def _draw_queues(self, surface: pygame.Surface, vs: VisualState) -> None:
        font = self._font_sm
        for qname, (qx, qy) in self.queue_pos.items():
            rect = pygame.Rect(qx - QUEUE_W // 2, qy - QUEUE_H // 2,
                               QUEUE_W, QUEUE_H)
            pygame.draw.rect(surface, COL_QUEUE, rect, border_radius=4)
            pygame.draw.rect(surface, COL_TEXT_DIM, rect, 1, border_radius=4)

            length = vs.queue_lengths.get(qname, 0)
            label = font.render(f"{qname}: {length}", True, COL_TEXT)
            surface.blit(label, (qx - label.get_width() // 2,
                                 qy - label.get_height() // 2))

    # ----- stations --------------------------------------------------------

    def _draw_stations(self, surface: pygame.Surface, vs: VisualState) -> None:
        font = self._font
        for sname, (sx, sy) in self.station_pos.items():
            is_exc = sname in ("E2", "E3")
            col = COL_STATION_EXC if is_exc else COL_STATION

            # Highlight if occupied
            n_devices = len(vs.station_devices.get(sname, set()))
            if n_devices > 0:
                col = tuple(min(c + 40, 255) for c in col)

            rect = pygame.Rect(sx - STATION_W // 2, sy - STATION_H // 2,
                               STATION_W, STATION_H)
            pygame.draw.rect(surface, col, rect, border_radius=6)
            pygame.draw.rect(surface, COL_TEXT_DIM, rect, 1, border_radius=6)

            label_text = STATION_LABELS.get(sname, sname)
            label = font.render(label_text, True, COL_WHITE)
            surface.blit(label, (sx - label.get_width() // 2,
                                 sy - label.get_height() // 2 - 8))

            count_label = font.render(f"({n_devices} in)", True, COL_TEXT_DIM)
            surface.blit(count_label, (sx - count_label.get_width() // 2,
                                       sy + 8))

    # ----- tokens (animated) -----------------------------------------------

    def _draw_tokens(self, surface: pygame.Surface, vs: VisualState,
                     now_ms: float) -> None:
        # Only draw tokens that are not yet dispatched (or recently dispatched)
        for tok in vs.tokens.values():
            if tok.status == "dispatched":
                # Fade out after dispatch – skip drawing after a while
                continue
            x, y = _animate_token(tok, now_ms)
            col = _token_colour(tok)
            pygame.draw.circle(surface, col, (int(x), int(y)), self.token_radius)

    # ----- HUD (top bar) ---------------------------------------------------

    def _draw_hud(self, surface: pygame.Surface, vs: VisualState,
                  paused: bool, speed: float) -> None:
        font = self._font_lg
        y = 12
        parts = [
            f"t={vs.sim_time:,.0f}s",
            f"Arrived={vs.total_arrived}",
            f"Dispatched={vs.completed_count}",
            f"Rejected={vs.rejected_count}",
            f"WIP={vs.total_wip()}",
            f"Speed={speed:.0f}x",
        ]
        if paused:
            parts.append("▌▌ PAUSED")
        text = "  │  ".join(parts)
        label = font.render(text, True, COL_TEXT)
        surface.blit(label, (20, y))

        # Controls hint
        hint = self._font_sm.render(
            "Space=Pause  R=Reset  ↑↓=Speed  S=Save", True, COL_TEXT_DIM)
        surface.blit(hint, (20, y + 26))

    # ----- utilization bars ------------------------------------------------

    def _draw_util_bars(self, surface: pygame.Surface, vs: VisualState) -> None:
        font = self._font_sm
        x0 = 20
        y0 = surface.get_height() - 160
        bar_w, bar_h = 110, 12
        spacing = 15

        resources = [
            "op_feed", "scanner", "m1_fixture", "m2_cooling_slot",
            "op_battery_monitor", "m3_punch", "op_maint",
            "m4_module", "op_sort", "op_pack",
        ]

        label = self._font.render("Resource Utilization", True, COL_TEXT)
        surface.blit(label, (x0, y0 - 20))

        for i, rname in enumerate(resources):
            y = y0 + i * spacing
            u = vs.utilization.get(rname, 0.0)

            # Background
            bg_rect = pygame.Rect(x0 + 130, y, bar_w, bar_h)
            pygame.draw.rect(surface, COL_BAR_BG, bg_rect, border_radius=2)

            # Fill
            fill_w = int(bar_w * min(u, 1.0))
            if fill_w > 0:
                fill_rect = pygame.Rect(x0 + 130, y, fill_w, bar_h)
                col = COL_BAR_FILL if u < 0.85 else COL_TOKEN_EXC
                pygame.draw.rect(surface, col, fill_rect, border_radius=2)

            # Label
            lbl = font.render(f"{rname}", True, COL_TEXT_DIM)
            surface.blit(lbl, (x0, y))
            pct = font.render(f"{u * 100:.0f}%", True, COL_TEXT)
            surface.blit(pct, (x0 + 130 + bar_w + 6, y))

    # ----- throughput rolling plot -----------------------------------------

    def _draw_throughput_plot(self, surface: pygame.Surface,
                             vs: VisualState) -> None:
        font = self._font_sm
        plot_x = surface.get_width() - 360
        plot_y = surface.get_height() - 160
        plot_w, plot_h = 330, 130

        # Background
        rect = pygame.Rect(plot_x, plot_y, plot_w, plot_h)
        pygame.draw.rect(surface, COL_BAR_BG, rect, border_radius=4)

        label = self._font.render("Throughput over time", True, COL_TEXT)
        surface.blit(label, (plot_x + 8, plot_y - 20))

        history = vs.throughput_history
        if len(history) < 2:
            return

        t_min = history[0][0]
        t_max = max(history[-1][0], t_min + 1)
        v_max = max(h[1] for h in history) or 1

        points = []
        for t, v in history:
            px = plot_x + 10 + int((t - t_min) / (t_max - t_min) * (plot_w - 20))
            py = plot_y + plot_h - 10 - int(v / v_max * (plot_h - 20))
            points.append((px, py))

        if len(points) >= 2:
            pygame.draw.lines(surface, COL_PLOT_LINE, False, points, 2)

        # Axis labels
        tl = font.render(f"0", True, COL_TEXT_DIM)
        surface.blit(tl, (plot_x + 4, plot_y + plot_h - 14))
        tr = font.render(f"{t_max:.0f}s", True, COL_TEXT_DIM)
        surface.blit(tr, (plot_x + plot_w - 50, plot_y + plot_h - 14))
        tv = font.render(f"{v_max}", True, COL_TEXT_DIM)
        surface.blit(tv, (plot_x + 4, plot_y + 4))

    # ----- output fractions panel ------------------------------------------

    def draw_outputs(self, surface: pygame.Surface, vs: VisualState) -> None:
        """Draw output fraction counters (called from main draw)."""
        font = self._font_sm
        x0 = surface.get_width() - 360
        y0 = surface.get_height() - 310

        label = self._font.render("Output Fractions", True, COL_TEXT)
        surface.blit(label, (x0, y0 - 20))

        for i, (frac, val) in enumerate(vs.output_totals.items()):
            y = y0 + i * 16
            lbl = font.render(f"{frac}: {val:.1f}", True, COL_TEXT_DIM)
            surface.blit(lbl, (x0, y))
