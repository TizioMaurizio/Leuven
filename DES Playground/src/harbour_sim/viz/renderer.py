"""
2D visualization renderer for HarbourSim.

Uses pygame to render a top-down view of the harbour including:
- Water, quay, and yard areas
- Ships at berths
- Quay cranes with movement and cargo
- Container yard with stacks
- Trucks arriving, loading, and departing
"""

import pygame
import math
import threading
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass

from harbour_sim.config import SimConfig
from harbour_sim.sim.engine import SimulationState
from harbour_sim.sim.entities import ShipState, TruckState, ContainerState


@dataclass
class RenderConfig:
    """Configuration for rendering dimensions and positions."""
    
    # Window
    width: int = 1400
    height: int = 900
    
    # Layout zones (y coordinates)
    water_top: int = 0
    water_height: int = 200
    quay_top: int = 200
    quay_height: int = 60
    yard_top: int = 260
    yard_height: int = 400
    road_top: int = 660
    road_height: int = 100
    info_top: int = 760
    info_height: int = 140
    
    # Margins
    margin_left: int = 50
    margin_right: int = 50
    
    # Sizes
    ship_width: int = 120
    ship_height: int = 40
    crane_width: int = 30
    crane_height: int = 80
    container_width: int = 20
    container_height: int = 12
    truck_width: int = 40
    truck_height: int = 25
    
    # Yard grid
    yard_cell_width: int = 24
    yard_cell_height: int = 18
    yard_margin_left: int = 100
    yard_margin_top: int = 20


class HarbourRenderer:
    """
    Pygame-based 2D renderer for the harbour simulation.
    
    Reads state from a SimulationState object and renders the
    current harbour configuration.
    """
    
    def __init__(
        self,
        config: SimConfig,
        render_config: RenderConfig = None
    ):
        """
        Initialize the renderer.
        
        Args:
            config: Simulation configuration
            render_config: Rendering configuration
        """
        self.config = config
        self.render_config = render_config or RenderConfig(
            width=config.window_width,
            height=config.window_height
        )
        
        # Calculate yard grid dimensions
        self._calc_yard_layout()
        
        # Pygame setup
        self._initialized = False
        self.screen = None
        self.clock = None
        self.font = None
        self.small_font = None
        self.large_font = None
        
        # State
        self._current_state: Optional[SimulationState] = None
        self._running = False
        
        # Animation
        self._animation_offset = 0
    
    def _calc_yard_layout(self):
        """Calculate yard grid layout based on configuration."""
        rc = self.render_config
        
        # Available space for yard
        yard_width = rc.width - rc.margin_left - rc.margin_right - rc.yard_margin_left
        yard_height = rc.yard_height - rc.yard_margin_top * 2
        
        # Calculate cell sizes to fit
        self.yard_cell_w = min(
            rc.yard_cell_width,
            yard_width // max(self.config.yard_width, 1)
        )
        self.yard_cell_h = min(
            rc.yard_cell_height,
            yard_height // max(self.config.yard_height, 1)
        )
        
        # Yard origin
        self.yard_origin_x = rc.margin_left + rc.yard_margin_left
        self.yard_origin_y = rc.yard_top + rc.yard_margin_top
    
    def initialize(self):
        """Initialize pygame and create window."""
        if self._initialized:
            return
        
        pygame.init()
        pygame.display.set_caption("HarbourSim - Container Harbour Simulation")
        
        rc = self.render_config
        self.screen = pygame.display.set_mode((rc.width, rc.height))
        self.clock = pygame.time.Clock()
        
        # Fonts
        self.font = pygame.font.SysFont("Arial", 14)
        self.small_font = pygame.font.SysFont("Arial", 10)
        self.large_font = pygame.font.SysFont("Arial", 24, bold=True)
        
        self._initialized = True
    
    def close(self):
        """Close pygame window."""
        if self._initialized:
            pygame.quit()
            self._initialized = False
    
    def update_state(self, state: SimulationState):
        """
        Update the state to render.
        
        Args:
            state: Current simulation state snapshot
        """
        self._current_state = state
    
    def render(self) -> bool:
        """
        Render the current state.
        
        Returns:
            False if window was closed, True otherwise.
        """
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
        self.screen.fill((255, 255, 255))
        
        # Draw layers
        self._draw_background()
        self._draw_water()
        self._draw_quay()
        self._draw_ships()
        self._draw_cranes()
        self._draw_yard()
        self._draw_road()
        self._draw_trucks()
        self._draw_info_panel()
        
        # Update display
        pygame.display.flip()
        
        # Animation
        self._animation_offset = (self._animation_offset + 1) % 100
        
        return True
    
    def tick(self, fps: int = 30):
        """Limit frame rate."""
        if self.clock:
            self.clock.tick(fps)
    
    def _draw_background(self):
        """Draw background."""
        self.screen.fill((240, 240, 240))
    
    def _draw_water(self):
        """Draw water area."""
        rc = self.render_config
        
        # Water base
        water_rect = pygame.Rect(0, rc.water_top, rc.width, rc.water_height)
        pygame.draw.rect(self.screen, self.config.color_water, water_rect)
        
        # Animated waves
        wave_color = (80, 180, 235)
        for i in range(0, rc.width, 40):
            offset = math.sin((i + self._animation_offset * 2) * 0.05) * 5
            y = rc.water_top + rc.water_height // 2 + offset
            pygame.draw.circle(self.screen, wave_color, (int(i), int(y)), 3)
    
    def _draw_quay(self):
        """Draw quay/dock area."""
        rc = self.render_config
        
        # Quay base
        quay_rect = pygame.Rect(0, rc.quay_top, rc.width, rc.quay_height)
        pygame.draw.rect(self.screen, self.config.color_quay, quay_rect)
        
        # Quay edge (darker line)
        pygame.draw.line(
            self.screen, (80, 80, 80),
            (0, rc.quay_top), (rc.width, rc.quay_top), 3
        )
        
        # Berth markers
        if self._current_state and self._current_state.berth_positions:
            for berth in self._current_state.berth_positions:
                x = self._berth_to_screen_x(berth["position_x"])
                
                # Berth marking
                color = (100, 200, 100) if not berth["is_occupied"] else (200, 100, 100)
                pygame.draw.rect(
                    self.screen, color,
                    pygame.Rect(x - 60, rc.quay_top + 5, 120, 10)
                )
                
                # Label
                label = self.small_font.render(f"Berth {berth['id'] + 1}", True, (255, 255, 255))
                self.screen.blit(label, (x - 25, rc.quay_top + 8))
    
    def _draw_ships(self):
        """Draw ships at berths."""
        if not self._current_state:
            return
        
        rc = self.render_config
        
        for berth_id, ship in self._current_state.ships_at_berth.items():
            # Get berth position
            berth = None
            for b in self._current_state.berth_positions:
                if b["id"] == berth_id:
                    berth = b
                    break
            
            if berth is None:
                continue
            
            x = self._berth_to_screen_x(berth["position_x"])
            y = rc.water_top + rc.water_height - rc.ship_height - 20
            
            # Ship body
            ship_rect = pygame.Rect(
                x - rc.ship_width // 2,
                y,
                rc.ship_width,
                rc.ship_height
            )
            pygame.draw.rect(self.screen, self.config.color_ship, ship_rect)
            pygame.draw.rect(self.screen, (60, 40, 30), ship_rect, 2)
            
            # Ship bow (triangular)
            bow_points = [
                (x + rc.ship_width // 2, y + rc.ship_height // 2),
                (x + rc.ship_width // 2 + 20, y + rc.ship_height // 4),
                (x + rc.ship_width // 2 + 20, y + 3 * rc.ship_height // 4),
            ]
            pygame.draw.polygon(self.screen, self.config.color_ship, bow_points)
            
            # Containers on ship (remaining)
            remaining = ship.containers_remaining
            if remaining > 0:
                stack_count = min(remaining // 5 + 1, 8)
                for i in range(stack_count):
                    cx = x - rc.ship_width // 2 + 10 + i * 12
                    cy = y + 5
                    pygame.draw.rect(
                        self.screen,
                        (100, 150, 200),
                        pygame.Rect(cx, cy, 10, 8)
                    )
            
            # Ship label
            label = self.small_font.render(
                f"Ship {ship.id} ({remaining})",
                True, (255, 255, 255)
            )
            self.screen.blit(label, (x - 30, y + 12))
    
    def _draw_cranes(self):
        """Draw quay cranes."""
        if not self._current_state:
            return
        
        rc = self.render_config
        
        for crane_data in self._current_state.crane_states:
            # Calculate crane position
            if crane_data["berth_id"] is not None:
                # Find berth position
                x = None
                for b in self._current_state.berth_positions:
                    if b["id"] == crane_data["berth_id"]:
                        x = self._berth_to_screen_x(b["position_x"])
                        break
                if x is None:
                    x = rc.margin_left + crane_data["id"] * 150
            else:
                # Default position based on crane ID
                x = rc.margin_left + 50 + crane_data["id"] * 150
            
            y = rc.quay_top
            
            # Crane base (rail)
            pygame.draw.rect(
                self.screen, (100, 100, 100),
                pygame.Rect(x - 5, rc.quay_top - 5, 10, rc.quay_height + 10)
            )
            
            # Crane tower
            tower_rect = pygame.Rect(
                x - rc.crane_width // 2,
                y - rc.crane_height + 20,
                rc.crane_width,
                rc.crane_height
            )
            pygame.draw.rect(self.screen, self.config.color_crane, tower_rect)
            pygame.draw.rect(self.screen, (200, 160, 0), tower_rect, 2)
            
            # Crane boom (horizontal arm)
            boom_y = y - rc.crane_height + 25
            pygame.draw.line(
                self.screen, self.config.color_crane,
                (x - 50, boom_y), (x + 70, boom_y), 6
            )
            
            # Spreader (if carrying container)
            if crane_data["has_container"]:
                spreader_y = boom_y + 20
                
                # Cable
                pygame.draw.line(
                    self.screen, (50, 50, 50),
                    (x + 20, boom_y), (x + 20, spreader_y), 2
                )
                
                # Container
                container_color = crane_data.get("container_color", (100, 150, 200))
                pygame.draw.rect(
                    self.screen, container_color,
                    pygame.Rect(x + 5, spreader_y, 30, 15)
                )
            
            # State indicator
            state = crane_data["state"]
            state_colors = {
                "IDLE": (100, 200, 100),
                "MOVING": (200, 200, 100),
                "PICKING": (200, 100, 100),
                "DROPPING": (100, 100, 200),
            }
            indicator_color = state_colors.get(state, (150, 150, 150))
            pygame.draw.circle(self.screen, indicator_color, (x, y - rc.crane_height + 10), 6)
            
            # Crane ID
            label = self.small_font.render(f"C{crane_data['id'] + 1}", True, (0, 0, 0))
            self.screen.blit(label, (x - 8, y + 5))
    
    def _draw_yard(self):
        """Draw container yard with stacks."""
        rc = self.render_config
        
        # Yard background
        yard_rect = pygame.Rect(
            rc.margin_left,
            rc.yard_top,
            rc.width - rc.margin_left - rc.margin_right,
            rc.yard_height
        )
        pygame.draw.rect(self.screen, self.config.color_yard, yard_rect)
        pygame.draw.rect(self.screen, (150, 150, 130), yard_rect, 2)
        
        # Grid lines
        for x in range(self.config.yard_width + 1):
            px = self.yard_origin_x + x * self.yard_cell_w
            pygame.draw.line(
                self.screen, (180, 180, 160),
                (px, self.yard_origin_y),
                (px, self.yard_origin_y + self.config.yard_height * self.yard_cell_h),
                1
            )
        
        for y in range(self.config.yard_height + 1):
            py = self.yard_origin_y + y * self.yard_cell_h
            pygame.draw.line(
                self.screen, (180, 180, 160),
                (self.yard_origin_x, py),
                (self.yard_origin_x + self.config.yard_width * self.yard_cell_w, py),
                1
            )
        
        # Draw containers
        if self._current_state and self._current_state.yard_state:
            for x, col in enumerate(self._current_state.yard_state):
                for y, stack in enumerate(col):
                    if stack:
                        self._draw_container_stack(x, y, stack)
        
        # Yard labels
        label = self.font.render("CONTAINER YARD", True, (80, 80, 60))
        self.screen.blit(label, (rc.margin_left + 10, rc.yard_top + 5))
        
        # Row/column labels
        for x in range(self.config.yard_width):
            if x % 5 == 0:
                px = self.yard_origin_x + x * self.yard_cell_w + 2
                label = self.small_font.render(str(x), True, (100, 100, 80))
                self.screen.blit(label, (px, rc.yard_top + rc.yard_height - 15))
    
    def _draw_container_stack(self, x: int, y: int, stack: List):
        """Draw a stack of containers at yard position."""
        if not stack:
            return
        
        px = self.yard_origin_x + x * self.yard_cell_w + 2
        py = self.yard_origin_y + y * self.yard_cell_h
        
        # Draw each container in stack (bottom to top, visually stacked)
        for i, container in enumerate(stack):
            # Offset each container slightly for 3D effect
            offset = i * 3
            
            container_rect = pygame.Rect(
                px - offset,
                py - offset,
                self.yard_cell_w - 4,
                self.yard_cell_h - 4
            )
            
            # Use container color
            color = container.color if hasattr(container, 'color') else (100, 150, 200)
            pygame.draw.rect(self.screen, color, container_rect)
            pygame.draw.rect(self.screen, (50, 50, 50), container_rect, 1)
        
        # Stack height label
        if len(stack) > 1:
            label = self.small_font.render(str(len(stack)), True, (255, 255, 255))
            label_rect = label.get_rect(center=(px + self.yard_cell_w // 2, py + self.yard_cell_h // 2))
            self.screen.blit(label, label_rect)
    
    def _draw_road(self):
        """Draw truck road and gate area."""
        rc = self.render_config
        
        # Road background
        road_rect = pygame.Rect(0, rc.road_top, rc.width, rc.road_height)
        pygame.draw.rect(self.screen, self.config.color_road, road_rect)
        
        # Lane markings
        for x in range(0, rc.width, 40):
            pygame.draw.rect(
                self.screen, (255, 255, 200),
                pygame.Rect(x, rc.road_top + rc.road_height // 2 - 2, 20, 4)
            )
        
        # Gate buildings
        for i in range(self.config.num_truck_gates):
            gate_x = rc.margin_left + 200 + i * 200
            
            # Gate structure
            pygame.draw.rect(
                self.screen, (150, 100, 50),
                pygame.Rect(gate_x - 30, rc.road_top + 10, 60, 30)
            )
            
            # Gate label
            label = self.small_font.render(f"Gate {i + 1}", True, (255, 255, 255))
            self.screen.blit(label, (gate_x - 20, rc.road_top + 18))
        
        # Pickup area label
        label = self.font.render("TRUCK PICKUP AREA", True, (200, 200, 200))
        self.screen.blit(label, (rc.margin_left + 10, rc.road_top + 5))
    
    def _draw_trucks(self):
        """Draw trucks."""
        if not self._current_state:
            return
        
        rc = self.render_config
        
        # Count trucks by state for positioning
        waiting_count = 0
        loading_count = 0
        
        for truck in self._current_state.active_trucks:
            state = truck.state
            
            if state == TruckState.ARRIVING or state == TruckState.WAITING_GATE:
                # Trucks in queue (left side)
                x = rc.margin_left + 50 + waiting_count * 50
                y = rc.road_top + rc.road_height - 40
                waiting_count += 1
                
            elif state in (TruckState.AT_GATE, TruckState.WAITING_CONTAINER, TruckState.LOADING):
                # Trucks at gate/loading
                gate_idx = truck.gate_id if truck.gate_id is not None else loading_count % self.config.num_truck_gates
                x = rc.margin_left + 200 + gate_idx * 200
                y = rc.road_top + 50
                loading_count += 1
                
            elif state == TruckState.DEPARTING:
                # Departing trucks (right side)
                x = rc.width - rc.margin_right - 100
                y = rc.road_top + rc.road_height - 40
                
            else:
                continue
            
            # Draw truck
            self._draw_truck(x, y, truck)
    
    def _draw_truck(self, x: int, y: int, truck):
        """Draw a single truck."""
        rc = self.render_config
        
        # Truck cab
        cab_rect = pygame.Rect(x, y, rc.truck_width // 2, rc.truck_height)
        pygame.draw.rect(self.screen, self.config.color_truck, cab_rect)
        pygame.draw.rect(self.screen, (30, 30, 30), cab_rect, 1)
        
        # Truck bed
        bed_rect = pygame.Rect(
            x + rc.truck_width // 2,
            y + 5,
            rc.truck_width // 2 + 10,
            rc.truck_height - 10
        )
        pygame.draw.rect(self.screen, (100, 100, 100), bed_rect)
        pygame.draw.rect(self.screen, (50, 50, 50), bed_rect, 1)
        
        # Container on truck (if loaded)
        if truck.container is not None and truck.state in (TruckState.LOADING, TruckState.DEPARTING):
            container_rect = pygame.Rect(
                x + rc.truck_width // 2 + 2,
                y + 2,
                rc.truck_width // 2 + 6,
                rc.truck_height - 8
            )
            color = truck.container.color if hasattr(truck.container, 'color') else (100, 150, 200)
            pygame.draw.rect(self.screen, color, container_rect)
        
        # Wheels
        wheel_y = y + rc.truck_height - 3
        pygame.draw.circle(self.screen, (30, 30, 30), (x + 8, wheel_y), 5)
        pygame.draw.circle(self.screen, (30, 30, 30), (x + rc.truck_width - 8, wheel_y), 5)
        
        # Truck ID
        label = self.small_font.render(f"T{truck.id}", True, (200, 200, 200))
        self.screen.blit(label, (x + 2, y + 2))
    
    def _draw_info_panel(self):
        """Draw information panel with metrics."""
        rc = self.render_config
        
        # Panel background
        panel_rect = pygame.Rect(0, rc.info_top, rc.width, rc.info_height)
        pygame.draw.rect(self.screen, (50, 50, 60), panel_rect)
        
        if not self._current_state:
            return
        
        state = self._current_state
        
        # Title
        title = self.large_font.render("HARBOUR SIMULATION", True, (255, 255, 255))
        self.screen.blit(title, (20, rc.info_top + 10))
        
        # Time
        time_text = self.font.render(
            f"Time: {state.time:.1f} min",
            True, (200, 200, 200)
        )
        self.screen.blit(time_text, (20, rc.info_top + 45))
        
        # Metrics columns
        col1_x = 200
        col2_x = 450
        col3_x = 700
        col4_x = 950
        
        y = rc.info_top + 20
        line_h = 22
        
        # Column 1: Ships
        self._draw_metric(col1_x, y, "Ships", len(state.ships))
        self._draw_metric(col1_x, y + line_h, "At Berth", len(state.ships_at_berth))
        
        # Column 2: Containers
        self._draw_metric(col2_x, y, "Unloaded", state.containers_unloaded)
        self._draw_metric(col2_x, y + line_h, "Delivered", state.containers_delivered)
        
        # Column 3: Yard
        self._draw_metric(col3_x, y, "Yard Occ.", f"{state.yard_occupancy * 100:.1f}%")
        
        # Calculate containers in yard
        yard_count = 0
        if state.yard_state:
            for col in state.yard_state:
                for stack in col:
                    yard_count += len(stack)
        self._draw_metric(col3_x, y + line_h, "In Yard", yard_count)
        
        # Column 4: Trucks
        self._draw_metric(col4_x, y, "Trucks", len(state.active_trucks))
        
        # Crane status bar
        self._draw_crane_status_bar(rc.info_top + 80)
        
        # Instructions
        instructions = self.small_font.render(
            "Press ESC to exit",
            True, (150, 150, 150)
        )
        self.screen.blit(instructions, (rc.width - 120, rc.info_top + rc.info_height - 20))
    
    def _draw_metric(self, x: int, y: int, label: str, value):
        """Draw a metric label and value."""
        label_text = self.font.render(f"{label}:", True, (180, 180, 180))
        self.screen.blit(label_text, (x, y))
        
        value_text = self.font.render(str(value), True, (255, 255, 255))
        self.screen.blit(value_text, (x + 100, y))
    
    def _draw_crane_status_bar(self, y: int):
        """Draw crane status indicators."""
        if not self._current_state:
            return
        
        x = 200
        label = self.font.render("Cranes:", True, (180, 180, 180))
        self.screen.blit(label, (x, y))
        
        x += 80
        for crane in self._current_state.crane_states:
            state = crane["state"]
            state_colors = {
                "IDLE": (100, 200, 100),
                "MOVING": (200, 200, 100),
                "PICKING": (200, 100, 100),
                "DROPPING": (100, 100, 200),
            }
            color = state_colors.get(state, (150, 150, 150))
            
            pygame.draw.rect(self.screen, color, pygame.Rect(x, y + 2, 30, 16))
            
            crane_label = self.small_font.render(f"C{crane['id'] + 1}", True, (0, 0, 0))
            self.screen.blit(crane_label, (x + 5, y + 3))
            
            x += 40
    
    def _berth_to_screen_x(self, berth_x: float) -> int:
        """Convert berth x coordinate to screen x."""
        rc = self.render_config
        usable_width = rc.width - rc.margin_left - rc.margin_right
        
        # Berth positions are normalized 0-100 in BerthManager
        return int(rc.margin_left + (berth_x / 100.0) * usable_width)
