"""
2D visualization renderer for DIGITAU Demanufacturing Simulator.

Uses pygame to render a top-down view of the factory including:
- Receiving docks for incoming product batches
- Processing stations (inspection, dismantling, testing)
- Buffer/WIP storage area with product stacks
- Exit gates for REUSE, REMANUFACTURE, RECYCLE paths
- Products color-coded by predicted/actual exit decision

CONCEPT MAPPING (from HarbourSim):
- Water area → Receiving area (incoming products)
- Quay → Station area
- Ships → Product batches
- Cranes → Processing stations
- Yard → Buffer/WIP storage
- Road → Exit area
- Trucks → Exit vehicles
"""

import pygame
import math
import threading
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass

from demanufacturing_sim.config import SimConfig
from demanufacturing_sim.sim.engine import SimulationState
from demanufacturing_sim.sim.entities import BatchState, ExitVehicleState, ProductState, ExitDecision


@dataclass
class RenderConfig:
    """Configuration for rendering dimensions and positions."""
    
    # Window
    width: int = 1400
    height: int = 900
    
    # Layout zones (y coordinates) - Factory layout
    receiving_top: int = 0
    receiving_height: int = 120
    stations_top: int = 120
    stations_height: int = 180
    buffer_top: int = 300
    buffer_height: int = 350
    exit_top: int = 650
    exit_height: int = 110
    info_top: int = 760
    info_height: int = 140
    
    # Margins
    margin_left: int = 50
    margin_right: int = 50
    
    # Sizes
    batch_width: int = 80
    batch_height: int = 40
    station_width: int = 60
    station_height: int = 50
    product_width: int = 18
    product_height: int = 14
    vehicle_width: int = 35
    vehicle_height: int = 25
    
    # Buffer grid
    buffer_cell_width: int = 28
    buffer_cell_height: int = 22
    buffer_margin_left: int = 80
    buffer_margin_top: int = 20


class FactoryRenderer:
    """
    Pygame-based 2D renderer for the demanufacturing simulation.
    
    Renders a factory layout with processing stations, buffer storage,
    and exit gates for different product destinations.
    """
    
    def __init__(
        self,
        config: SimConfig,
        render_config: RenderConfig = None
    ):
        """Initialize the renderer."""
        self.config = config
        self.render_config = render_config or RenderConfig(
            width=config.window_width,
            height=config.window_height
        )
        
        self._calc_buffer_layout()
        
        # Pygame setup
        self._initialized = False
        self.screen = None
        self.clock = None
        self.font = None
        self.small_font = None
        self.large_font = None
        # Fullscreen flag (can be set on initialize)
        self.fullscreen = False
        
        # State
        self._current_state: Optional[SimulationState] = None
        self._running = False
        
        # Animation
        self._animation_offset = 0
    
    def _calc_buffer_layout(self):
        """Calculate buffer grid layout based on configuration."""
        rc = self.render_config
        
        buffer_width = rc.width - rc.margin_left - rc.margin_right - rc.buffer_margin_left
        buffer_height = rc.buffer_height - rc.buffer_margin_top * 2
        
        self.buffer_cell_w = min(
            rc.buffer_cell_width,
            buffer_width // max(self.config.buffer_width, 1)
        )
        self.buffer_cell_h = min(
            rc.buffer_cell_height,
            buffer_height // max(self.config.buffer_height, 1)
        )
        
        self.buffer_origin_x = rc.margin_left + rc.buffer_margin_left
        self.buffer_origin_y = rc.buffer_top + rc.buffer_margin_top
    
    def initialize(self):
        """Initialize pygame and create window."""
        if self._initialized:
            return
        pygame.init()
        pygame.display.set_caption("DIGITAU - Battery De/Remanufacturing Digital Twin")

        rc = self.render_config
        # If fullscreen requested, query current display resolution
        if getattr(self, 'fullscreen', False):
            info = pygame.display.Info()
            display_w, display_h = info.current_w, info.current_h
            try:
                # Use FULLSCREEN mode with native display resolution
                self.screen = pygame.display.set_mode((display_w, display_h), pygame.FULLSCREEN)
                # Update render_config to the new resolution for layout calculations
                rc.width = display_w
                rc.height = display_h
            except Exception:
                # Fallback to windowed mode if fullscreen fails
                self.screen = pygame.display.set_mode((rc.width, rc.height))
        else:
            self.screen = pygame.display.set_mode((rc.width, rc.height))

        self.clock = pygame.time.Clock()
        
        self.font = pygame.font.SysFont("Arial", 14)
        self.small_font = pygame.font.SysFont("Arial", 10)
        self.large_font = pygame.font.SysFont("Arial", 24, bold=True)
        self.title_font = pygame.font.SysFont("Arial", 18, bold=True)
        
        self._initialized = True
    
    def close(self):
        """Close pygame window."""
        if self._initialized:
            pygame.quit()
            self._initialized = False

    def show_popup(self, title: str, message: str, timeout_seconds: int = 10):
        """Show a modal popup overlay with `title` and `message`.

        Waits for any key press or mouse click, or for `timeout_seconds` to elapse.
        Returns True if the popup was dismissed by user, False if window was closed.
        """
        # Do not reinitialize here; assume renderer is already initialized and
        # a final frame has been drawn. Use the current screen surface size
        # so the overlay matches the actual display (important for fullscreen).
        if not self._initialized or not self.screen:
            # If somehow not initialized, fall back to initialization.
            try:
                self.initialize()
            except Exception:
                pass

        start = pygame.time.get_ticks()
        clock = pygame.time.Clock()
        dismissed = False

        # Snapshot the current screen so we can restore it each frame and
        # draw the translucent overlay on top. This ensures the popup appears
        # as an overlay of the last drawn frame even if the main loop cleared
        # or updated the display before we entered the popup.
        try:
            background = self.screen.copy()
            screen_w, screen_h = background.get_size()
        except Exception:
            background = pygame.Surface((self.render_config.width, self.render_config.height))
            screen_w, screen_h = self.render_config.width, self.render_config.height

        # Create translucent overlay using per-pixel alpha
        overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        overlay.fill((10, 10, 10, 180))  # RGBA with alpha for translucency

        # Prepare text
        title_surf = self.large_font.render(title, True, (255, 255, 255))
        msg_surf = self.font.render(message, True, (220, 220, 220))
        hint_surf = self.small_font.render("Press any key or click to close (or wait)...", True, (180, 180, 180))

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    dismissed = True
                    break

            # Restore the last frame and draw overlay and text on top
            try:
                self.screen.blit(background, (0, 0))
            except Exception:
                pass
            self.screen.blit(overlay, (0, 0))

            # Center popup box
            box_w = min(800, self.render_config.width - 200)
            box_h = 180
            box_x = (self.render_config.width - box_w) // 2
            box_y = (self.render_config.height - box_h) // 2

            pygame.draw.rect(self.screen, (40, 45, 55), pygame.Rect(box_x, box_y, box_w, box_h))
            pygame.draw.rect(self.screen, (100, 120, 140), pygame.Rect(box_x, box_y, box_w, box_h), 2)

            # Title and message
            title_rect = title_surf.get_rect(center=(self.render_config.width // 2, box_y + 35))
            self.screen.blit(title_surf, title_rect)

            msg_rect = msg_surf.get_rect(center=(self.render_config.width // 2, box_y + 80))
            self.screen.blit(msg_surf, msg_rect)

            hint_rect = hint_surf.get_rect(center=(self.render_config.width // 2, box_y + 130))
            self.screen.blit(hint_surf, hint_rect)

            pygame.display.flip()

            if dismissed:
                return True

            # Timeout
            now = pygame.time.get_ticks()
            if (now - start) >= timeout_seconds * 1000:
                return True

            clock.tick(30)
    
    def update_state(self, state: SimulationState):
        """Update the state to render."""
        self._current_state = state
    
    def render(self) -> bool:
        """Render the current state."""
        if not self._initialized:
            self.initialize()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
        
        self.screen.fill(self.config.color_background)
        
        self._draw_receiving_area()
        self._draw_stations()
        self._draw_buffer()
        self._draw_exit_area()
        self._draw_info_panel()
        
        pygame.display.flip()
        
        self._animation_offset = (self._animation_offset + 1) % 100
        
        return True
    
    def tick(self, fps: int = 30):
        """Limit frame rate."""
        if self.clock:
            self.clock.tick(fps)
    
    def _draw_receiving_area(self):
        """Draw receiving dock area for incoming batches."""
        rc = self.render_config
        
        # Background
        recv_rect = pygame.Rect(0, rc.receiving_top, rc.width, rc.receiving_height)
        pygame.draw.rect(self.screen, (180, 200, 220), recv_rect)
        
        # Title
        label = self.title_font.render("RECEIVING AREA", True, (60, 80, 100))
        self.screen.blit(label, (rc.margin_left, rc.receiving_top + 5))
        
        # Draw docks
        if self._current_state and self._current_state.dock_positions:
            dock_spacing = (rc.width - rc.margin_left - rc.margin_right) // (len(self._current_state.dock_positions) + 1)
            
            for i, dock in enumerate(self._current_state.dock_positions):
                x = rc.margin_left + dock_spacing * (i + 1)
                y = rc.receiving_top + 35
                
                # Dock platform
                color = (100, 180, 100) if not dock["is_occupied"] else (180, 140, 100)
                pygame.draw.rect(
                    self.screen, color,
                    pygame.Rect(x - 50, y, 100, 25)
                )
                pygame.draw.rect(
                    self.screen, (80, 80, 80),
                    pygame.Rect(x - 50, y, 100, 25), 2
                )
                
                label = self.small_font.render(f"Dock {dock['id'] + 1}", True, (255, 255, 255))
                self.screen.blit(label, (x - 18, y + 6))
        
        # Draw batches at docks
        if self._current_state:
            for dock_id, batch in self._current_state.batches_at_dock.items():
                dock_spacing = (rc.width - rc.margin_left - rc.margin_right) // (len(self._current_state.dock_positions) + 1)
                x = rc.margin_left + dock_spacing * (dock_id + 1)
                y = rc.receiving_top + 70
                
                # Batch container
                batch_rect = pygame.Rect(
                    x - rc.batch_width // 2, y,
                    rc.batch_width, rc.batch_height
                )
                pygame.draw.rect(self.screen, (120, 100, 80), batch_rect)
                pygame.draw.rect(self.screen, (80, 60, 40), batch_rect, 2)
                
                # Products remaining indicator
                remaining = batch.products_remaining
                label = self.small_font.render(f"Batch {batch.id} ({remaining})", True, (255, 255, 255))
                self.screen.blit(label, (x - 30, y + 12))
    
    def _draw_stations(self):
        """Draw processing stations."""
        rc = self.render_config
        
        # Background
        station_rect = pygame.Rect(0, rc.stations_top, rc.width, rc.stations_height)
        pygame.draw.rect(self.screen, (210, 210, 220), station_rect)
        
        # Section dividers and labels
        section_width = (rc.width - rc.margin_left - rc.margin_right) // 3
        
        sections = [
            ("INSPECTION", self.config.color_station_inspection, 
             self._current_state.inspection_states if self._current_state else []),
            ("DISMANTLING", self.config.color_station_dismantling,
             self._current_state.dismantling_states if self._current_state else []),
            ("TESTING", self.config.color_station_testing,
             self._current_state.testing_states if self._current_state else [])
        ]
        
        for i, (name, color, stations) in enumerate(sections):
            section_x = rc.margin_left + i * section_width
            
            # Section label
            label = self.title_font.render(name, True, (60, 60, 80))
            self.screen.blit(label, (section_x + 10, rc.stations_top + 5))
            
            # Section border
            pygame.draw.line(
                self.screen, (150, 150, 160),
                (section_x + section_width, rc.stations_top),
                (section_x + section_width, rc.stations_top + rc.stations_height), 1
            )
            
            # Draw stations
            if stations:
                spacing = section_width // (len(stations) + 1)
                for j, station in enumerate(stations):
                    sx = section_x + spacing * (j + 1)
                    sy = rc.stations_top + 50
                    
                    self._draw_station(sx, sy, station, color)
    
    def _draw_station(self, x: int, y: int, station: Dict, base_color: Tuple[int, int, int]):
        """Draw a single processing station."""
        rc = self.render_config
        
        # Station body
        station_rect = pygame.Rect(
            x - rc.station_width // 2, y,
            rc.station_width, rc.station_height
        )
        
        # Color based on state
        if station["state"] == "PROCESSING":
            color = (min(base_color[0] + 40, 255), 
                     min(base_color[1] + 40, 255), 
                     min(base_color[2] + 40, 255))
        else:
            color = base_color
        
        pygame.draw.rect(self.screen, color, station_rect)
        pygame.draw.rect(self.screen, (60, 60, 60), station_rect, 2)
        
        # Station ID
        label = self.font.render(f"S{station['id'] + 1}", True, (255, 255, 255))
        label_rect = label.get_rect(center=(x, y + 15))
        self.screen.blit(label, label_rect)
        
        # Status indicator
        if station["state"] == "PROCESSING":
            pygame.draw.circle(self.screen, (50, 255, 50), (x, y + rc.station_height - 10), 5)
        else:
            pygame.draw.circle(self.screen, (150, 150, 150), (x, y + rc.station_height - 10), 5)
        
        # Product being processed
        if station["has_product"] and station["product_color"]:
            product_rect = pygame.Rect(
                x - rc.product_width // 2, y + rc.station_height + 5,
                rc.product_width, rc.product_height
            )
            pygame.draw.rect(self.screen, station["product_color"], product_rect)
            pygame.draw.rect(self.screen, (40, 40, 40), product_rect, 1)
        
        # Processed count
        count_label = self.small_font.render(f"{station['products_processed']}", True, (80, 80, 80))
        self.screen.blit(count_label, (x - 5, y + rc.station_height + 22))
    
    def _draw_buffer(self):
        """Draw buffer/WIP storage area."""
        rc = self.render_config
        
        # Background
        buffer_bg = pygame.Rect(
            rc.margin_left, rc.buffer_top,
            rc.width - rc.margin_left - rc.margin_right,
            rc.buffer_height
        )
        pygame.draw.rect(self.screen, self.config.color_buffer, buffer_bg)
        pygame.draw.rect(self.screen, (150, 150, 140), buffer_bg, 2)
        
        # Title
        label = self.title_font.render("BUFFER / WIP STORAGE", True, (60, 60, 50))
        self.screen.blit(label, (rc.margin_left + 10, rc.buffer_top + 5))
        
        # Region labels for exit decisions
        region_width = self.config.buffer_width * self.buffer_cell_w // 3
        regions = [
            ("REUSE", self.config.color_product_reuse),
            ("REMANUFACTURE", self.config.color_product_remanufacture),
            ("RECYCLE", self.config.color_product_recycle)
        ]
        
        for i, (name, color) in enumerate(regions):
            rx = self.buffer_origin_x + i * region_width
            # Region indicator bar
            pygame.draw.rect(
                self.screen, color,
                pygame.Rect(rx, rc.buffer_top + 28, region_width - 5, 4)
            )
            label = self.small_font.render(name, True, (80, 80, 70))
            self.screen.blit(label, (rx + 5, rc.buffer_top + 34))
        
        # Grid lines
        for x in range(self.config.buffer_width + 1):
            px = self.buffer_origin_x + x * self.buffer_cell_w
            pygame.draw.line(
                self.screen, (180, 180, 170),
                (px, self.buffer_origin_y + 20),
                (px, self.buffer_origin_y + self.config.buffer_height * self.buffer_cell_h + 20),
                1
            )
        
        for y in range(self.config.buffer_height + 1):
            py = self.buffer_origin_y + y * self.buffer_cell_h + 20
            pygame.draw.line(
                self.screen, (180, 180, 170),
                (self.buffer_origin_x, py),
                (self.buffer_origin_x + self.config.buffer_width * self.buffer_cell_w, py),
                1
            )
        
        # Draw products
        if self._current_state and self._current_state.buffer_state:
            for x, col in enumerate(self._current_state.buffer_state):
                for y, stack in enumerate(col):
                    if stack:
                        self._draw_product_stack(x, y, stack)
    
    def _draw_product_stack(self, x: int, y: int, stack: List):
        """Draw a stack of products at buffer position."""
        if not stack:
            return
        
        px = self.buffer_origin_x + x * self.buffer_cell_w + 2
        py = self.buffer_origin_y + y * self.buffer_cell_h + 22
        
        for i, product in enumerate(stack):
            offset = i * 3
            
            product_rect = pygame.Rect(
                px - offset, py - offset,
                self.buffer_cell_w - 4, self.buffer_cell_h - 4
            )
            
            color = product.color if hasattr(product, 'color') else (150, 150, 150)
            pygame.draw.rect(self.screen, color, product_rect)
            pygame.draw.rect(self.screen, (40, 40, 40), product_rect, 1)
        
        if len(stack) > 1:
            label = self.small_font.render(str(len(stack)), True, (255, 255, 255))
            label_rect = label.get_rect(center=(px + self.buffer_cell_w // 2, py + self.buffer_cell_h // 2))
            self.screen.blit(label, label_rect)
    
    def _draw_exit_area(self):
        """Draw exit gates for different destinations."""
        rc = self.render_config
        
        # Background
        exit_rect = pygame.Rect(0, rc.exit_top, rc.width, rc.exit_height)
        pygame.draw.rect(self.screen, (100, 100, 110), exit_rect)
        
        # Title
        label = self.title_font.render("EXIT AREA", True, (200, 200, 210))
        self.screen.blit(label, (rc.margin_left, rc.exit_top + 5))
        
        # Lane markings
        for x in range(0, rc.width, 40):
            pygame.draw.rect(
                self.screen, (180, 180, 150),
                pygame.Rect(x, rc.exit_top + rc.exit_height // 2 - 2, 20, 4)
            )
        
        # Exit gates by category
        gates = [
            ("REUSE", self.config.color_product_reuse, self.config.num_reuse_gates),
            ("REMANUFACTURE", self.config.color_product_remanufacture, self.config.num_remanufacture_gates),
            ("RECYCLE", self.config.color_product_recycle, self.config.num_recycle_gates)
        ]
        
        total_gates = sum(g[2] for g in gates)
        gate_spacing = (rc.width - rc.margin_left - rc.margin_right) // (total_gates + 1)
        gate_idx = 0
        
        for name, color, count in gates:
            for i in range(count):
                gate_idx += 1
                gx = rc.margin_left + gate_spacing * gate_idx
                gy = rc.exit_top + 25
                
                # Gate structure
                pygame.draw.rect(
                    self.screen, color,
                    pygame.Rect(gx - 30, gy, 60, 30)
                )
                pygame.draw.rect(
                    self.screen, (60, 60, 60),
                    pygame.Rect(gx - 30, gy, 60, 30), 2
                )
                
                # Gate label
                gate_label = self.small_font.render(name[:3], True, (255, 255, 255))
                self.screen.blit(gate_label, (gx - 12, gy + 8))
        
        # Draw vehicles
        self._draw_vehicles()
    
    def _draw_vehicles(self):
        """Draw exit vehicles."""
        if not self._current_state:
            return
        
        rc = self.render_config
        
        waiting_by_dest = {
            ExitDecision.REUSE: 0,
            ExitDecision.REMANUFACTURE: 0,
            ExitDecision.RECYCLE: 0
        }
        
        for vehicle in self._current_state.active_vehicles:
            dest = vehicle.destination
            state = vehicle.state
            
            if state == ExitVehicleState.ARRIVING or state == ExitVehicleState.WAITING_GATE:
                # Vehicles in queue
                x = rc.margin_left + 50 + waiting_by_dest[dest] * 45
                y = rc.exit_top + rc.exit_height - 35
                waiting_by_dest[dest] += 1
                
            elif state in (ExitVehicleState.AT_GATE, ExitVehicleState.WAITING_PRODUCT, 
                          ExitVehicleState.LOADING):
                # Vehicles at gate
                gates = [
                    (ExitDecision.REUSE, self.config.num_reuse_gates),
                    (ExitDecision.REMANUFACTURE, self.config.num_remanufacture_gates),
                    (ExitDecision.RECYCLE, self.config.num_recycle_gates)
                ]
                total_gates = sum(g[1] for g in gates)
                gate_spacing = (rc.width - rc.margin_left - rc.margin_right) // (total_gates + 1)
                
                gate_offset = 0
                for d, count in gates:
                    if d == dest:
                        break
                    gate_offset += count
                
                x = rc.margin_left + gate_spacing * (gate_offset + 1)
                y = rc.exit_top + 60
                
            elif state == ExitVehicleState.DEPARTING:
                x = rc.width - rc.margin_right - 80
                y = rc.exit_top + rc.exit_height - 35
                
            else:
                continue
            
            self._draw_vehicle(x, y, vehicle)
    
    def _draw_vehicle(self, x: int, y: int, vehicle):
        """Draw a single exit vehicle."""
        rc = self.render_config
        
        # Get color based on destination
        if vehicle.destination == ExitDecision.REUSE:
            color = self.config.color_product_reuse
        elif vehicle.destination == ExitDecision.REMANUFACTURE:
            color = self.config.color_product_remanufacture
        else:
            color = self.config.color_product_recycle
        
        # Darken for vehicle body
        body_color = (max(0, color[0] - 50), max(0, color[1] - 50), max(0, color[2] - 50))
        
        # Vehicle cab
        cab_rect = pygame.Rect(x, y, rc.vehicle_width // 2, rc.vehicle_height)
        pygame.draw.rect(self.screen, body_color, cab_rect)
        pygame.draw.rect(self.screen, (30, 30, 30), cab_rect, 1)
        
        # Vehicle bed
        bed_rect = pygame.Rect(
            x + rc.vehicle_width // 2, y + 4,
            rc.vehicle_width // 2 + 8, rc.vehicle_height - 8
        )
        pygame.draw.rect(self.screen, (120, 120, 120), bed_rect)
        pygame.draw.rect(self.screen, (60, 60, 60), bed_rect, 1)
        
        # Product on vehicle
        if vehicle.product is not None and vehicle.state in (ExitVehicleState.LOADING, ExitVehicleState.DEPARTING):
            product_rect = pygame.Rect(
                x + rc.vehicle_width // 2 + 2, y + 2,
                rc.vehicle_width // 2 + 4, rc.vehicle_height - 6
            )
            pygame.draw.rect(self.screen, vehicle.product.color, product_rect)
        
        # Wheels
        wheel_y = y + rc.vehicle_height - 3
        pygame.draw.circle(self.screen, (30, 30, 30), (x + 6, wheel_y), 4)
        pygame.draw.circle(self.screen, (30, 30, 30), (x + rc.vehicle_width - 6, wheel_y), 4)
        
        # Vehicle ID
        label = self.small_font.render(f"V{vehicle.id}", True, (200, 200, 200))
        self.screen.blit(label, (x + 2, y + 2))
    
    def _draw_info_panel(self):
        """Draw information panel with metrics."""
        rc = self.render_config
        
        # Panel background
        panel_rect = pygame.Rect(0, rc.info_top, rc.width, rc.info_height)
        pygame.draw.rect(self.screen, (40, 45, 55), panel_rect)
        
        if not self._current_state:
            return
        
        state = self._current_state
        
        # Title
        title = self.large_font.render("DIGITAU - Digital Twin Dashboard", True, (220, 220, 230))
        self.screen.blit(title, (rc.margin_left, rc.info_top + 10))
        
        # Time
        time_str = f"Time: {state.time:.1f} min"
        time_label = self.font.render(time_str, True, (180, 180, 190))
        self.screen.blit(time_label, (rc.width - 150, rc.info_top + 15))
        
        # Metrics columns
        col_x = [rc.margin_left, rc.margin_left + 250, rc.margin_left + 500, rc.margin_left + 750]
        row_y = rc.info_top + 45
        
        # Column 1: Processing
        metrics1 = [
            f"Products Processed: {state.products_processed}",
            f"Products Exited: {state.products_exited}",
            f"Buffer Occupancy: {state.buffer_occupancy * 100:.1f}%"
        ]
        
        for i, text in enumerate(metrics1):
            label = self.font.render(text, True, (180, 180, 190))
            self.screen.blit(label, (col_x[0], row_y + i * 22))
        
        # Column 2: Exit categories
        metrics2 = [
            ("Reuse:", state.reuse_count, self.config.color_product_reuse),
            ("Remanufacture:", state.remanufacture_count, self.config.color_product_remanufacture),
            ("Recycle:", state.recycle_count, self.config.color_product_recycle)
        ]
        
        for i, (label_text, count, color) in enumerate(metrics2):
            label = self.font.render(f"{label_text} {count}", True, color)
            self.screen.blit(label, (col_x[1], row_y + i * 22))
        
        # Column 3: Throughput
        total_exited = state.reuse_count + state.remanufacture_count + state.recycle_count
        if state.time > 0:
            throughput = total_exited / (state.time / 60)
        else:
            throughput = 0
        
        # Value recovered
        value = (state.reuse_count * self.config.value_per_reuse +
                 state.remanufacture_count * self.config.value_per_remanufacture +
                 state.recycle_count * self.config.value_per_recycle)
        
        metrics3 = [
            f"Throughput: {throughput:.1f} products/hr",
            f"Value Recovered: ${value:.0f}",
            f"Active Batches: {len(state.batches_at_dock)}"
        ]
        
        for i, text in enumerate(metrics3):
            label = self.font.render(text, True, (180, 180, 190))
            self.screen.blit(label, (col_x[2], row_y + i * 22))
        
        # Column 4: Active vehicles
        active_count = len(state.active_vehicles)
        metrics4 = [
            f"Active Vehicles: {active_count}",
            f"Total Batches: {len(state.batches)}",
            "Press ESC to exit"
        ]
        
        for i, text in enumerate(metrics4):
            label = self.font.render(text, True, (180, 180, 190))
            self.screen.blit(label, (col_x[3], row_y + i * 22))
