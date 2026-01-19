"""
2D visualization renderer for the closed-loop manufacturing system.

Shows a top-down factory layout with:
- Two processing stations (S1, S2)
- Conveyors between stations
- Pallets moving through the system
- Station states (idle/processing/blocked)
- Real-time WIP and throughput metrics

Adapted from: FactoryRenderer (DIGITAU) / HarbourRenderer (HarbourSim)
"""

import pygame
import math
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass

from manufacturing_loop_sim.config import SimConfig
from manufacturing_loop_sim.sim.engine import SimulationState


@dataclass
class RenderConfig:
    """Layout configuration for rendering."""
    width: int = 1200
    height: int = 700
    
    # Margins
    margin: int = 40
    
    # Station dimensions
    station_width: int = 120
    station_height: int = 100
    
    # Conveyor dimensions
    conveyor_width: int = 400
    conveyor_height: int = 50
    
    # Pallet dimensions
    pallet_size: int = 24
    
    # Info panel
    info_height: int = 120


class LoopRenderer:
    """
    Pygame-based 2D renderer for the closed-loop manufacturing system.
    
    Renders a simple top-down view showing stations, conveyors, and
    pallets moving through the system.
    """
    
    def __init__(self, config: SimConfig, render_config: RenderConfig = None):
        """Initialize the renderer."""
        self.config = config
        self.render_config = render_config or RenderConfig(
            width=config.window_width,
            height=config.window_height
        )
        
        # Pygame setup
        self._initialized = False
        self.screen = None
        self.clock = None
        self.font = None
        self.small_font = None
        self.large_font = None
        
        # Current state
        self._current_state: Optional[SimulationState] = None
        
        # Animation
        self._animation_frame = 0
    
    def initialize(self):
        """Initialize pygame and create window."""
        if self._initialized:
            return
        
        pygame.init()
        pygame.display.set_caption("Manufacturing Loop Simulator - Two-Station Closed Loop")
        
        rc = self.render_config
        self.screen = pygame.display.set_mode((rc.width, rc.height))
        self.clock = pygame.time.Clock()
        
        self.font = pygame.font.SysFont("Arial", 14)
        self.small_font = pygame.font.SysFont("Arial", 11)
        self.large_font = pygame.font.SysFont("Arial", 24, bold=True)
        self.title_font = pygame.font.SysFont("Arial", 16, bold=True)
        
        self._initialized = True
    
    def close(self):
        """Close pygame window."""
        if self._initialized:
            pygame.quit()
            self._initialized = False
    
    def update_state(self, state: SimulationState):
        """Update the state to render."""
        self._current_state = state
    
    def render(self) -> bool:
        """Render the current state. Returns False if window closed."""
        if not self._initialized:
            self.initialize()
        
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
        
        # Clear screen
        self.screen.fill(self.config.color_background)
        
        # Draw components
        self._draw_title()
        self._draw_conveyors()
        self._draw_stations()
        self._draw_pallets()
        self._draw_info_panel()
        
        pygame.display.flip()
        
        self._animation_frame += 1
        
        return True
    
    def tick(self, fps: int = 30):
        """Limit frame rate."""
        if self.clock:
            self.clock.tick(fps)
    
    def _draw_title(self):
        """Draw title and time."""
        time = self._current_state.time if self._current_state else 0.0
        
        title = self.large_font.render("Two-Station Closed-Loop Manufacturing System", True, 
                                       self.config.color_text)
        self.screen.blit(title, (self.render_config.margin, 10))
        
        time_text = self.font.render(f"Time: {time:.1f}s", True, self.config.color_text)
        self.screen.blit(time_text, (self.render_config.width - 120, 15))
    
    def _draw_conveyors(self):
        """Draw conveyor buffers."""
        rc = self.render_config
        state = self._current_state
        
        # Calculate positions
        center_x = rc.width // 2
        center_y = (rc.height - rc.info_height) // 2 + 20
        
        # Conveyor 1: S1 → S2 (top)
        c1_y = center_y - 80
        c1_rect = pygame.Rect(
            center_x - rc.conveyor_width // 2,
            c1_y,
            rc.conveyor_width,
            rc.conveyor_height
        )
        
        c1_color = self.config.color_conveyor
        if state and state.conveyor_1.get("is_full", False):
            c1_color = self.config.color_conveyor_full
        
        pygame.draw.rect(self.screen, c1_color, c1_rect)
        pygame.draw.rect(self.screen, (100, 100, 110), c1_rect, 2)
        
        # Arrow indicating direction
        arrow_y = c1_y + rc.conveyor_height // 2
        for ax in range(center_x - 180, center_x + 180, 80):
            pygame.draw.polygon(self.screen, (120, 120, 130), [
                (ax, arrow_y - 8),
                (ax + 20, arrow_y),
                (ax, arrow_y + 8)
            ])
        
        # Label
        c1_count = state.conveyor_1.get("count", 0) if state else 0
        c1_cap = state.conveyor_1.get("capacity", 8) if state else 8
        label = self.font.render(f"Conveyor S1→S2: {c1_count}/{c1_cap}", True, self.config.color_text)
        self.screen.blit(label, (c1_rect.centerx - 70, c1_rect.bottom + 5))
        
        # Conveyor 2: S2 → S1 (bottom)
        c2_y = center_y + 80
        c2_rect = pygame.Rect(
            center_x - rc.conveyor_width // 2,
            c2_y,
            rc.conveyor_width,
            rc.conveyor_height
        )
        
        c2_color = self.config.color_conveyor
        if state and state.conveyor_2.get("is_full", False):
            c2_color = self.config.color_conveyor_full
        
        pygame.draw.rect(self.screen, c2_color, c2_rect)
        pygame.draw.rect(self.screen, (100, 100, 110), c2_rect, 2)
        
        # Arrow indicating direction (reversed)
        arrow_y = c2_y + rc.conveyor_height // 2
        for ax in range(center_x + 180, center_x - 180, -80):
            pygame.draw.polygon(self.screen, (120, 120, 130), [
                (ax, arrow_y - 8),
                (ax - 20, arrow_y),
                (ax, arrow_y + 8)
            ])
        
        # Label
        c2_count = state.conveyor_2.get("count", 0) if state else 0
        c2_cap = state.conveyor_2.get("capacity", 8) if state else 8
        label = self.font.render(f"Conveyor S2→S1: {c2_count}/{c2_cap}", True, self.config.color_text)
        self.screen.blit(label, (c2_rect.centerx - 70, c2_rect.bottom + 5))
    
    def _draw_stations(self):
        """Draw processing stations."""
        rc = self.render_config
        state = self._current_state
        
        center_x = rc.width // 2
        center_y = (rc.height - rc.info_height) // 2 + 20
        
        # Station 1 (left)
        s1_x = center_x - rc.conveyor_width // 2 - rc.station_width - 30
        s1_y = center_y - rc.station_height // 2
        self._draw_station(s1_x, s1_y, "S1", state.station_1 if state else {})
        
        # Station 2 (right)
        s2_x = center_x + rc.conveyor_width // 2 + 30
        s2_y = center_y - rc.station_height // 2
        self._draw_station(s2_x, s2_y, "S2", state.station_2 if state else {})
    
    def _draw_station(self, x: int, y: int, name: str, station_state: Dict):
        """Draw a single station."""
        rc = self.render_config
        
        # Determine color based on state
        state_name = station_state.get("state", "IDLE")
        if state_name == "PROCESSING":
            color = self.config.color_station_busy
        elif state_name == "BLOCKED":
            color = self.config.color_station_blocked
        elif state_name == "DEGRADED":
            color = self.config.color_station_degraded
        else:
            color = self.config.color_station_idle
        
        # Station body
        station_rect = pygame.Rect(x, y, rc.station_width, rc.station_height)
        pygame.draw.rect(self.screen, color, station_rect)
        pygame.draw.rect(self.screen, (60, 60, 70), station_rect, 3)
        
        # Station name
        name_text = self.large_font.render(name, True, (255, 255, 255))
        name_rect = name_text.get_rect(center=(x + rc.station_width // 2, y + 30))
        self.screen.blit(name_text, name_rect)
        
        # State indicator
        state_text = self.small_font.render(state_name, True, (255, 255, 255))
        state_rect = state_text.get_rect(center=(x + rc.station_width // 2, y + 55))
        self.screen.blit(state_text, state_rect)
        
        # Pallet indicator
        has_pallet = station_state.get("has_pallet", False)
        pallet_id = station_state.get("pallet_id", None)
        if has_pallet and pallet_id:
            pallet_text = self.small_font.render(f"P{pallet_id}", True, (255, 255, 255))
            self.screen.blit(pallet_text, (x + rc.station_width // 2 - 10, y + 75))
        
        # Queue indicator
        queue_len = station_state.get("queue_length", 0)
        if queue_len > 0:
            queue_text = self.small_font.render(f"Queue: {queue_len}", True, self.config.color_text)
            self.screen.blit(queue_text, (x, y - 20))
        
        # Stats
        processed = station_state.get("pallets_processed", 0)
        util_text = self.small_font.render(f"Processed: {processed}", True, self.config.color_text)
        self.screen.blit(util_text, (x, y + rc.station_height + 5))
    
    def _draw_pallets(self):
        """Draw all pallets at their current positions."""
        if not self._current_state:
            return
        
        rc = self.render_config
        center_x = rc.width // 2
        center_y = (rc.height - rc.info_height) // 2 + 20
        
        for pallet_data in self._current_state.pallets:
            self._draw_pallet(pallet_data, center_x, center_y)
    
    def _draw_pallet(self, pallet_data: Dict, center_x: int, center_y: int):
        """Draw a single pallet."""
        rc = self.render_config
        
        # Get visual position (normalized 0-1)
        vx = pallet_data.get("visual_x", 0.5)
        vy = pallet_data.get("visual_y", 0.5)
        
        # Convert to screen coordinates
        # Map x: 0.08-0.92 to screen width
        # Map y: 0.35-0.65 to relevant area
        work_width = rc.width - 2 * rc.margin
        work_height = rc.height - rc.info_height - 100
        
        x = int(rc.margin + vx * work_width)
        y = int(60 + vy * work_height)
        
        # Determine color
        is_processing = pallet_data.get("is_processing", False)
        is_blocked = pallet_data.get("is_blocked", False)
        
        if is_processing:
            color = self.config.color_pallet_processing
        elif is_blocked:
            color = self.config.color_station_blocked
        else:
            color = self.config.color_pallet
        
        # Draw pallet as rounded rectangle
        pallet_rect = pygame.Rect(
            x - rc.pallet_size // 2,
            y - rc.pallet_size // 2,
            rc.pallet_size,
            rc.pallet_size
        )
        pygame.draw.rect(self.screen, color, pallet_rect, border_radius=4)
        pygame.draw.rect(self.screen, (40, 40, 50), pallet_rect, 2, border_radius=4)
        
        # Pallet ID
        pallet_id = pallet_data.get("id", "?")
        id_text = self.small_font.render(str(pallet_id), True, (255, 255, 255))
        id_rect = id_text.get_rect(center=(x, y))
        self.screen.blit(id_text, id_rect)
    
    def _draw_info_panel(self):
        """Draw the information panel at the bottom."""
        rc = self.render_config
        state = self._current_state
        
        # Panel background
        panel_y = rc.height - rc.info_height
        panel_rect = pygame.Rect(0, panel_y, rc.width, rc.info_height)
        pygame.draw.rect(self.screen, (230, 235, 240), panel_rect)
        pygame.draw.line(self.screen, (180, 180, 190), 
                        (0, panel_y), (rc.width, panel_y), 2)
        
        # Title
        title = self.title_font.render("System Metrics", True, self.config.color_text)
        self.screen.blit(title, (rc.margin, panel_y + 10))
        
        if not state:
            return
        
        # Metrics columns
        col1_x = rc.margin
        col2_x = rc.width // 4
        col3_x = rc.width // 2
        col4_x = 3 * rc.width // 4
        row1_y = panel_y + 40
        row2_y = panel_y + 65
        row3_y = panel_y + 90
        
        # Column 1: Time & Cycles
        self.screen.blit(
            self.font.render(f"Simulation Time: {state.time:.1f}s", True, self.config.color_text),
            (col1_x, row1_y)
        )
        self.screen.blit(
            self.font.render(f"Total Cycles: {state.total_cycles}", True, self.config.color_text),
            (col1_x, row2_y)
        )
        throughput = state.total_cycles / state.time if state.time > 0 else 0
        self.screen.blit(
            self.font.render(f"Throughput: {throughput:.3f}/s", True, self.config.color_text),
            (col1_x, row3_y)
        )
        
        # Column 2: Station 1
        s1 = state.station_1
        self.screen.blit(
            self.title_font.render("Station S1", True, self.config.color_text),
            (col2_x, row1_y)
        )
        self.screen.blit(
            self.font.render(f"State: {s1.get('state', 'N/A')}", True, self.config.color_text),
            (col2_x, row2_y)
        )
        self.screen.blit(
            self.font.render(f"Processed: {s1.get('pallets_processed', 0)}", True, self.config.color_text),
            (col2_x, row3_y)
        )
        
        # Column 3: Station 2
        s2 = state.station_2
        self.screen.blit(
            self.title_font.render("Station S2", True, self.config.color_text),
            (col3_x, row1_y)
        )
        self.screen.blit(
            self.font.render(f"State: {s2.get('state', 'N/A')}", True, self.config.color_text),
            (col3_x, row2_y)
        )
        self.screen.blit(
            self.font.render(f"Processed: {s2.get('pallets_processed', 0)}", True, self.config.color_text),
            (col3_x, row3_y)
        )
        
        # Column 4: WIP
        self.screen.blit(
            self.title_font.render("Work in Progress", True, self.config.color_text),
            (col4_x, row1_y)
        )
        self.screen.blit(
            self.font.render(f"Conv S1→S2: {state.wip_conveyor_1}", True, self.config.color_text),
            (col4_x, row2_y)
        )
        self.screen.blit(
            self.font.render(f"Conv S2→S1: {state.wip_conveyor_2}", True, self.config.color_text),
            (col4_x, row3_y)
        )
