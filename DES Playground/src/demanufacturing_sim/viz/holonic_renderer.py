"""
Enhanced 2D visualization renderer for Holonic Demanufacturing Simulation.

Extends the base FactoryRenderer to support:
- Circular factory layout (U-shaped flow)
- Orchestrator overlay panel showing strategy and guidance
- Product coloring by destination intent
- Station health state visualization
- Transport holon tracking
- Fault indicators
"""

import pygame
import math
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field

from demanufacturing_sim.config import SimConfig
from demanufacturing_sim.viz.renderer import FactoryRenderer, RenderConfig
from demanufacturing_sim.sim.entities import ExitDecision


@dataclass
class HolonicRenderConfig(RenderConfig):
    """Extended render config for holonic visualization."""
    
    # Window (wider for orchestrator panel)
    width: int = 1600
    height: int = 950
    
    # Main factory area (left side)
    factory_width: int = 1150
    
    # Orchestrator panel (right side)
    orchestrator_panel_left: int = 1160
    orchestrator_panel_width: int = 430
    
    # Circular layout zones (y coordinates)
    inbound_top: int = 0
    inbound_height: int = 150
    inspection_top: int = 150
    inspection_height: int = 120
    disassembly_top: int = 270
    disassembly_height: int = 180
    classification_top: int = 450
    classification_height: int = 100
    exit_lanes_top: int = 550
    exit_lanes_height: int = 200
    transport_height: int = 100
    
    # Colors for health states
    health_healthy: Tuple[int, int, int] = (50, 200, 100)
    health_degraded: Tuple[int, int, int] = (255, 180, 50)
    health_critical: Tuple[int, int, int] = (255, 100, 50)
    health_failed: Tuple[int, int, int] = (200, 50, 50)
    
    # Orchestrator colors
    orchestrator_bg: Tuple[int, int, int] = (35, 40, 50)
    orchestrator_highlight: Tuple[int, int, int] = (60, 80, 120)
    guidance_signal_color: Tuple[int, int, int] = (100, 180, 255)


class HolonicFactoryRenderer(FactoryRenderer):
    """
    Enhanced renderer with circular factory layout and orchestrator overlay.
    
    Layout:
    - Left: Inbound arrivals + inspection zone
    - Middle: Disassembly cells with queues
    - Right: Classification + exit split into 4 lanes
    - Side panel: Orchestrator status and guidance signals
    """
    
    def __init__(
        self,
        config: SimConfig,
        render_config: HolonicRenderConfig = None
    ):
        """Initialize holonic renderer."""
        if render_config is None:
            render_config = HolonicRenderConfig()
        
        super().__init__(config, render_config)
        self.holonic_config = render_config
        
        # Enhanced state tracking
        self._enhanced_state = None
        self._holon_positions: Dict[str, Tuple[int, int]] = {}
        
        # Animation
        self._pulse_phase = 0
        self._transport_animation = 0
        # Fullscreen passthrough
        self.fullscreen = False
    
    def update_enhanced_state(self, state):
        """Update with enhanced holonic state."""
        self._enhanced_state = state
        self.update_state(state)
    
    def render(self) -> bool:
        """Render with circular layout and orchestrator panel."""
        if not self._initialized:
            self.initialize()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
        
        self.screen.fill(self.config.color_background)
        
        # Draw main factory area (left side)
        self._draw_inbound_zone()
        self._draw_inspection_zone()
        self._draw_disassembly_zone()
        self._draw_classification_zone()
        self._draw_exit_lanes()
        self._draw_transport_layer()
        
        # Draw orchestrator panel (right side)
        self._draw_orchestrator_panel()
        
        # Draw info bar at bottom
        self._draw_compact_info_bar()
        
        pygame.display.flip()
        
        # Update animations
        self._pulse_phase = (self._pulse_phase + 0.1) % (2 * math.pi)
        self._transport_animation = (self._transport_animation + 2) % 100
        
        return True
    
    def _draw_inbound_zone(self):
        """Draw inbound arrivals area (top-left)."""
        hc = self.holonic_config
        
        # Background
        zone_rect = pygame.Rect(0, hc.inbound_top, hc.factory_width, hc.inbound_height)
        pygame.draw.rect(self.screen, (180, 200, 220), zone_rect)
        
        # Flow arrow (U-shape indicator)
        arrow_points = [
            (50, 80), (150, 80), (150, 120), (170, 100), (150, 80)
        ]
        pygame.draw.lines(self.screen, (100, 130, 160), False, arrow_points, 3)
        
        # Title
        title = self.title_font.render("INBOUND ARRIVALS", True, (60, 80, 100))
        self.screen.blit(title, (20, 10))
        
        # Dock visualization
        dock_width = 120
        dock_spacing = 150
        
        if self._current_state and self._current_state.dock_positions:
            for i, dock in enumerate(self._current_state.dock_positions[:3]):
                x = 80 + i * dock_spacing
                y = 50
                
                # Dock platform
                color = (100, 180, 100) if not dock["is_occupied"] else (180, 140, 100)
                pygame.draw.rect(self.screen, color, pygame.Rect(x, y, dock_width, 35))
                pygame.draw.rect(self.screen, (80, 80, 80), pygame.Rect(x, y, dock_width, 35), 2)
                
                # Dock label
                label = self.font.render(f"Dock {dock['id'] + 1}", True, (255, 255, 255))
                self.screen.blit(label, (x + 35, y + 10))
        
        # Draw active batches
        if self._current_state and self._current_state.batches_at_dock:
            for dock_id, batch in self._current_state.batches_at_dock.items():
                x = 80 + dock_id * dock_spacing + 20
                y = 95
                
                # Batch container
                batch_rect = pygame.Rect(x, y, 80, 40)
                pygame.draw.rect(self.screen, (120, 100, 80), batch_rect)
                pygame.draw.rect(self.screen, (80, 60, 40), batch_rect, 2)
                
                # Products indicator
                remaining = batch.products_remaining
                label = self.small_font.render(f"Batch {batch.id} ({remaining})", True, (255, 255, 255))
                self.screen.blit(label, (x + 5, y + 12))
    
    def _draw_inspection_zone(self):
        """Draw inspection zone (after inbound)."""
        hc = self.holonic_config
        
        # Background
        zone_rect = pygame.Rect(0, hc.inspection_top, hc.factory_width, hc.inspection_height)
        pygame.draw.rect(self.screen, (200, 210, 220), zone_rect)
        
        # Title
        title = self.title_font.render("INSPECTION ZONE", True, (60, 70, 90))
        self.screen.blit(title, (20, hc.inspection_top + 5))
        
        # Draw inspection stations with health indicators
        stations = self._current_state.inspection_states if self._current_state else []
        self._draw_station_row(
            stations, 
            hc.inspection_top + 35, 
            self.config.color_station_inspection,
            "INSPECTION",
            max_stations=4
        )
    
    def _draw_disassembly_zone(self):
        """Draw disassembly zone (middle, multiple cells)."""
        hc = self.holonic_config
        
        # Background with gradient effect
        zone_rect = pygame.Rect(0, hc.disassembly_top, hc.factory_width, hc.disassembly_height)
        pygame.draw.rect(self.screen, (210, 215, 225), zone_rect)
        
        # Title
        title = self.title_font.render("DISASSEMBLY CELLS", True, (60, 70, 90))
        self.screen.blit(title, (20, hc.disassembly_top + 5))
        
        # Draw disassembly stations as cells with queues
        stations = self._current_state.dismantling_states if self._current_state else []
        
        cell_width = 180
        cell_height = 120
        cell_margin = 30
        
        for i, station in enumerate(stations[:5]):
            x = 50 + i * (cell_width + cell_margin)
            y = hc.disassembly_top + 40
            
            # Cell background
            cell_rect = pygame.Rect(x, y, cell_width, cell_height)
            
            # Get health state for this station
            health_color = self._get_health_color(f"resource_dismantling_{station['id']}")
            
            pygame.draw.rect(self.screen, (240, 240, 245), cell_rect)
            pygame.draw.rect(self.screen, health_color, cell_rect, 3)
            
            # Cell label
            label = self.font.render(f"Cell {station['id'] + 1}", True, (60, 60, 80))
            self.screen.blit(label, (x + 10, y + 5))
            
            # Station within cell
            self._draw_station_with_health(
                x + cell_width // 2, y + 50,
                station, self.config.color_station_dismantling
            )
            
            # Queue indicator
            queue_width = 60
            queue_rect = pygame.Rect(x + 10, y + cell_height - 30, queue_width, 20)
            pygame.draw.rect(self.screen, (180, 180, 190), queue_rect)
            pygame.draw.rect(self.screen, (120, 120, 130), queue_rect, 1)
            
            queue_label = self.small_font.render("Queue", True, (100, 100, 110))
            self.screen.blit(queue_label, (x + 12, y + cell_height - 27))
    
    def _draw_classification_zone(self):
        """Draw classification and testing zone."""
        hc = self.holonic_config
        
        # Background
        zone_rect = pygame.Rect(0, hc.classification_top, hc.factory_width, hc.classification_height)
        pygame.draw.rect(self.screen, (200, 205, 215), zone_rect)
        
        # Title
        title = self.title_font.render("CLASSIFICATION & TESTING", True, (60, 70, 90))
        self.screen.blit(title, (20, hc.classification_top + 5))
        
        # Draw testing stations
        stations = self._current_state.testing_states if self._current_state else []
        self._draw_station_row(
            stations,
            hc.classification_top + 35,
            self.config.color_station_testing,
            "TESTING",
            max_stations=4
        )
        
        # Decision split indicator
        split_x = hc.factory_width - 200
        pygame.draw.polygon(
            self.screen, (150, 160, 180),
            [
                (split_x, hc.classification_top + 50),
                (split_x + 60, hc.classification_top + 30),
                (split_x + 60, hc.classification_top + 70)
            ]
        )
        
        # Split labels
        labels = ["REUSE", "REMAN", "RECYCLE", "DISPOSE"]
        colors = [
            self.config.color_product_reuse,
            self.config.color_product_remanufacture,
            self.config.color_product_recycle,
            (150, 100, 100)
        ]
        
        for i, (label, color) in enumerate(zip(labels, colors)):
            y_offset = hc.classification_top + 25 + i * 20
            pygame.draw.rect(self.screen, color, pygame.Rect(split_x + 70, y_offset, 80, 15))
            text = self.small_font.render(label, True, (255, 255, 255))
            self.screen.blit(text, (split_x + 80, y_offset + 2))
    
    def _draw_exit_lanes(self):
        """Draw 4 exit lanes for different destinations."""
        hc = self.holonic_config
        
        # Background
        zone_rect = pygame.Rect(0, hc.exit_lanes_top, hc.factory_width, hc.exit_lanes_height)
        pygame.draw.rect(self.screen, (90, 95, 110), zone_rect)
        
        # Title
        title = self.title_font.render("EXIT LANES", True, (200, 200, 210))
        self.screen.blit(title, (20, hc.exit_lanes_top + 5))
        
        # Define lanes
        lanes = [
            ("REUSE", self.config.color_product_reuse, self._current_state.reuse_count if self._current_state else 0),
            ("REMANUFACTURE", self.config.color_product_remanufacture, self._current_state.remanufacture_count if self._current_state else 0),
            ("RECYCLE", self.config.color_product_recycle, self._current_state.recycle_count if self._current_state else 0),
            ("DISPOSAL", (150, 100, 100), 0)  # Track separately if needed
        ]
        
        lane_width = (hc.factory_width - 100) // 4
        
        for i, (name, color, count) in enumerate(lanes):
            x = 50 + i * lane_width
            y = hc.exit_lanes_top + 35
            
            # Lane background
            lane_rect = pygame.Rect(x, y, lane_width - 20, hc.exit_lanes_height - 50)
            pygame.draw.rect(self.screen, (70, 75, 90), lane_rect)
            pygame.draw.rect(self.screen, color, lane_rect, 3)
            
            # Lane header
            header_rect = pygame.Rect(x, y, lane_width - 20, 30)
            pygame.draw.rect(self.screen, color, header_rect)
            
            # Lane label
            label = self.font.render(name, True, (255, 255, 255))
            self.screen.blit(label, (x + 10, y + 7))
            
            # Count display
            count_label = self.large_font.render(str(count), True, (255, 255, 255))
            count_rect = count_label.get_rect(center=(x + (lane_width - 20) // 2, y + 80))
            self.screen.blit(count_label, count_rect)
            
            # Gate icons at bottom
            gate_y = y + hc.exit_lanes_height - 80
            pygame.draw.rect(self.screen, (60, 65, 80), pygame.Rect(x + 20, gate_y, lane_width - 60, 30))
            gate_label = self.small_font.render("Gate", True, (180, 180, 190))
            self.screen.blit(gate_label, (x + 50, gate_y + 8))
        
        # Draw vehicles
        self._draw_vehicles_in_lanes()
    
    def _draw_transport_layer(self):
        """Draw AGV transport layer at bottom of factory."""
        hc = self.holonic_config
        
        # Transport track
        track_y = hc.exit_lanes_top + hc.exit_lanes_height - 20
        pygame.draw.rect(self.screen, (60, 65, 75), pygame.Rect(30, track_y, hc.factory_width - 60, 15))
        
        # Track markings
        for x in range(40, hc.factory_width - 40, 30):
            pygame.draw.rect(self.screen, (100, 105, 115), pygame.Rect(x, track_y + 6, 15, 3))
        
        # Draw AGV holons
        if self._enhanced_state and hasattr(self._enhanced_state, 'transport_states'):
            for i, (holon_id, state) in enumerate(self._enhanced_state.transport_states.items()):
                # Animate AGV position
                agv_x = 60 + (self._transport_animation + i * 200) % (hc.factory_width - 120)
                agv_y = track_y - 10
                
                # AGV body
                agv_color = (80, 150, 200) if state == "IDLE" else (200, 150, 80)
                pygame.draw.rect(self.screen, agv_color, pygame.Rect(agv_x, agv_y, 40, 20))
                pygame.draw.rect(self.screen, (40, 40, 40), pygame.Rect(agv_x, agv_y, 40, 20), 2)
                
                # AGV label
                label = self.small_font.render(f"AGV{i+1}", True, (255, 255, 255))
                self.screen.blit(label, (agv_x + 5, agv_y + 4))
    
    def _draw_orchestrator_panel(self):
        """Draw orchestrator status and guidance panel."""
        hc = self.holonic_config
        
        # Panel background
        panel_rect = pygame.Rect(hc.orchestrator_panel_left, 0, hc.orchestrator_panel_width, hc.height - 100)
        pygame.draw.rect(self.screen, hc.orchestrator_bg, panel_rect)
        pygame.draw.rect(self.screen, (80, 90, 110), panel_rect, 2)
        
        y = 15
        
        # Title
        title = self.large_font.render("ORCHESTRATOR", True, (200, 210, 230))
        title_rect = title.get_rect(centerx=hc.orchestrator_panel_left + hc.orchestrator_panel_width // 2)
        title_rect.y = y
        self.screen.blit(title, title_rect)
        y += 40
        
        # Status indicator
        if self._enhanced_state:
            enabled = self._enhanced_state.orchestrator_enabled
            status_color = (50, 200, 100) if enabled else (150, 150, 160)
            status_text = "ACTIVE" if enabled else "STANDBY"
            
            pygame.draw.circle(self.screen, status_color, 
                             (hc.orchestrator_panel_left + 25, y + 8), 8)
            
            status_label = self.font.render(f"Status: {status_text}", True, (180, 190, 200))
            self.screen.blit(status_label, (hc.orchestrator_panel_left + 45, y))
            y += 35
            
            # Current strategy
            strategy = self._enhanced_state.current_strategy
            strategy_color = self._get_strategy_color(strategy)
            
            pygame.draw.rect(self.screen, hc.orchestrator_highlight, 
                           pygame.Rect(hc.orchestrator_panel_left + 10, y, hc.orchestrator_panel_width - 20, 50))
            
            strat_label = self.font.render("Current Strategy:", True, (150, 160, 180))
            self.screen.blit(strat_label, (hc.orchestrator_panel_left + 20, y + 5))
            
            strat_value = self.title_font.render(strategy, True, strategy_color)
            self.screen.blit(strat_value, (hc.orchestrator_panel_left + 20, y + 25))
            y += 65
            
            # Active guidance signals
            signals = self._enhanced_state.active_guidance_signals[:3]  # Top 3
            
            signal_label = self.font.render("Active Guidance Signals:", True, (150, 160, 180))
            self.screen.blit(signal_label, (hc.orchestrator_panel_left + 15, y))
            y += 25
            
            for signal in signals:
                # Signal box
                signal_rect = pygame.Rect(hc.orchestrator_panel_left + 15, y, 
                                        hc.orchestrator_panel_width - 30, 55)
                pygame.draw.rect(self.screen, (50, 55, 70), signal_rect)
                pygame.draw.rect(self.screen, hc.guidance_signal_color, signal_rect, 2)
                
                # Signal content
                target = signal.get("target", "system")[:20]
                action = signal.get("action", "unknown")[:25]
                strength = signal.get("strength", 0)
                
                target_text = self.small_font.render(f"Target: {target}", True, (180, 190, 200))
                self.screen.blit(target_text, (hc.orchestrator_panel_left + 22, y + 5))
                
                action_text = self.small_font.render(f"Action: {action}", True, (140, 200, 255))
                self.screen.blit(action_text, (hc.orchestrator_panel_left + 22, y + 22))
                
                # Strength bar
                bar_width = int((hc.orchestrator_panel_width - 60) * strength)
                pygame.draw.rect(self.screen, (80, 150, 200), 
                               pygame.Rect(hc.orchestrator_panel_left + 22, y + 40, bar_width, 8))
                
                y += 65
            
            if not signals:
                no_signal = self.small_font.render("No active signals", True, (120, 130, 140))
                self.screen.blit(no_signal, (hc.orchestrator_panel_left + 20, y))
                y += 30
            
            y += 10
            
            # System metrics
            pygame.draw.line(self.screen, (80, 90, 110), 
                           (hc.orchestrator_panel_left + 10, y),
                           (hc.orchestrator_panel_left + hc.orchestrator_panel_width - 10, y), 1)
            y += 15
            
            metrics_label = self.font.render("System Metrics:", True, (150, 160, 180))
            self.screen.blit(metrics_label, (hc.orchestrator_panel_left + 15, y))
            y += 25
            
            # Health gauge
            health = self._enhanced_state.system_health
            health_color = self._health_to_color(health)
            
            pygame.draw.rect(self.screen, (50, 55, 65), 
                           pygame.Rect(hc.orchestrator_panel_left + 20, y, 200, 20))
            pygame.draw.rect(self.screen, health_color,
                           pygame.Rect(hc.orchestrator_panel_left + 20, y, int(200 * health), 20))
            
            health_text = self.small_font.render(f"System Health: {health*100:.0f}%", True, (200, 210, 220))
            self.screen.blit(health_text, (hc.orchestrator_panel_left + 230, y + 3))
            y += 35
            
            # Throughput trend
            trend = self._enhanced_state.throughput_trend
            trend_color = (50, 200, 100) if trend == "increasing" else (
                (255, 180, 50) if trend == "stable" else (255, 100, 50)
            )
            trend_text = self.small_font.render(f"Throughput: {trend.upper()}", True, trend_color)
            self.screen.blit(trend_text, (hc.orchestrator_panel_left + 20, y))
            y += 25
            
            # Uncertainty level
            uncertainty = self._enhanced_state.avg_uncertainty
            unc_text = self.small_font.render(f"Avg Uncertainty: {uncertainty:.2f}", True, (180, 190, 200))
            self.screen.blit(unc_text, (hc.orchestrator_panel_left + 20, y))
            y += 25
            
            # Active holons
            active_holons = self._enhanced_state.active_product_holons
            holon_text = self.small_font.render(f"Active Product Holons: {active_holons}", True, (180, 190, 200))
            self.screen.blit(holon_text, (hc.orchestrator_panel_left + 20, y))
            y += 35
            
            # Fault status
            pygame.draw.line(self.screen, (80, 90, 110),
                           (hc.orchestrator_panel_left + 10, y),
                           (hc.orchestrator_panel_left + hc.orchestrator_panel_width - 10, y), 1)
            y += 15
            
            fault_label = self.font.render("Fault Status:", True, (150, 160, 180))
            self.screen.blit(fault_label, (hc.orchestrator_panel_left + 15, y))
            y += 25
            
            scenario = self._enhanced_state.fault_scenario
            scenario_color = (200, 100, 100) if scenario != "none" else (150, 200, 150)
            scenario_text = self.small_font.render(f"Scenario: {scenario}", True, scenario_color)
            self.screen.blit(scenario_text, (hc.orchestrator_panel_left + 20, y))
            y += 20
            
            active_faults = self._enhanced_state.active_faults
            if active_faults:
                fault_count = self.small_font.render(f"Active Faults: {len(active_faults)}", True, (255, 150, 100))
                self.screen.blit(fault_count, (hc.orchestrator_panel_left + 20, y))
                y += 20
                
                # List first few faults
                for fault in active_faults[:2]:
                    fault_type = fault.get("type", "unknown")[:15]
                    fault_target = fault.get("target", "")[:10]
                    fault_text = self.small_font.render(f"  • {fault_type} @ {fault_target}", True, (255, 180, 150))
                    self.screen.blit(fault_text, (hc.orchestrator_panel_left + 20, y))
                    y += 18
            else:
                no_fault = self.small_font.render("No active faults", True, (150, 200, 150))
                self.screen.blit(no_fault, (hc.orchestrator_panel_left + 20, y))
    
    def _draw_compact_info_bar(self):
        """Draw compact info bar at bottom."""
        hc = self.holonic_config
        
        # Bar background
        bar_rect = pygame.Rect(0, hc.height - 100, hc.width, 100)
        pygame.draw.rect(self.screen, (40, 45, 55), bar_rect)
        
        if not self._current_state:
            return
        
        state = self._current_state
        
        # Title
        title = self.large_font.render("DIGITAU - Holonic Demanufacturing Twin", True, (220, 220, 230))
        self.screen.blit(title, (20, hc.height - 90))
        
        # Time
        time_str = f"Time: {state.time:.1f} min"
        time_label = self.font.render(time_str, True, (180, 180, 190))
        self.screen.blit(time_label, (400, hc.height - 85))
        
        # Control mode
        mode = "ORCHESTRATED" if (self._enhanced_state and self._enhanced_state.orchestrator_enabled) else "HOLONIC"
        mode_color = (100, 180, 255) if mode == "ORCHESTRATED" else (180, 255, 100)
        mode_label = self.font.render(f"Mode: {mode}", True, mode_color)
        self.screen.blit(mode_label, (550, hc.height - 85))
        
        # Metrics row
        y = hc.height - 55
        col_positions = [20, 200, 400, 600, 800, 1000, 1200]
        
        metrics = [
            f"Processed: {state.products_processed}",
            f"Exited: {state.products_exited}",
            f"Buffer: {state.buffer_occupancy * 100:.0f}%"
        ]
        
        for i, text in enumerate(metrics[:len(col_positions)]):
            label = self.font.render(text, True, (180, 180, 190))
            self.screen.blit(label, (col_positions[i], y))
        
        # Exit counts with colors
        exits = [
            ("Reuse:", state.reuse_count, self.config.color_product_reuse),
            ("Reman:", state.remanufacture_count, self.config.color_product_remanufacture),
            ("Recycle:", state.recycle_count, self.config.color_product_recycle)
        ]
        
        x = col_positions[3]
        for label_text, count, color in exits:
            text = f"{label_text} {count}"
            label = self.font.render(text, True, color)
            self.screen.blit(label, (x, y))
            x += 120
        
        # Throughput and value
        total_exited = state.reuse_count + state.remanufacture_count + state.recycle_count
        throughput = total_exited / (state.time / 60) if state.time > 0 else 0
        value = (state.reuse_count * self.config.value_per_reuse +
                 state.remanufacture_count * self.config.value_per_remanufacture +
                 state.recycle_count * self.config.value_per_recycle)
        
        tp_label = self.font.render(f"Throughput: {throughput:.1f}/hr", True, (180, 180, 190))
        self.screen.blit(tp_label, (col_positions[5] if len(col_positions) > 5 else 1000, y))
        
        val_label = self.font.render(f"Value: ${value:.0f}", True, (180, 255, 180))
        self.screen.blit(val_label, (col_positions[6] if len(col_positions) > 6 else 1200, y))
        
        # ESC instruction
        esc_label = self.small_font.render("Press ESC to exit", True, (120, 120, 130))
        self.screen.blit(esc_label, (hc.width - 120, hc.height - 25))
    
    def _draw_station_row(self, stations: List[Dict], y: int, base_color: Tuple[int, int, int],
                         station_type: str, max_stations: int = 4):
        """Draw a row of stations with health indicators."""
        hc = self.holonic_config
        
        if not stations:
            return
        
        station_spacing = (hc.factory_width - 100) // (min(len(stations), max_stations) + 1)
        
        for i, station in enumerate(stations[:max_stations]):
            x = 80 + station_spacing * (i + 1)
            self._draw_station_with_health(x, y, station, base_color)
    
    def _draw_station_with_health(self, x: int, y: int, station: Dict, 
                                  base_color: Tuple[int, int, int]):
        """Draw a station with health state indicator."""
        rc = self.render_config
        
        # Get health color
        station_key = f"resource_{station.get('type', 'unknown')}_{station['id']}"
        health_color = self._get_health_color(station_key)
        
        # Station body
        station_rect = pygame.Rect(x - 35, y, 70, 55)
        
        # Color based on state
        if station["state"] == "PROCESSING":
            color = (min(base_color[0] + 40, 255),
                     min(base_color[1] + 40, 255),
                     min(base_color[2] + 40, 255))
            # Processing pulse
            pulse = int(math.sin(self._pulse_phase) * 10 + 10)
            pygame.draw.rect(self.screen, (255, 255, 200, 100), 
                           pygame.Rect(x - 35 - pulse//2, y - pulse//2, 70 + pulse, 55 + pulse), 2)
        else:
            color = base_color
        
        pygame.draw.rect(self.screen, color, station_rect)
        pygame.draw.rect(self.screen, (60, 60, 60), station_rect, 2)
        
        # Health indicator strip at top
        pygame.draw.rect(self.screen, health_color, pygame.Rect(x - 35, y, 70, 5))
        
        # Station ID
        label = self.font.render(f"S{station['id'] + 1}", True, (255, 255, 255))
        label_rect = label.get_rect(center=(x, y + 20))
        self.screen.blit(label, label_rect)
        
        # Status indicator
        status_color = (50, 255, 50) if station["state"] == "PROCESSING" else (150, 150, 150)
        pygame.draw.circle(self.screen, status_color, (x, y + 40), 5)
        
        # Product being processed
        if station.get("has_product") and station.get("product_color"):
            product_rect = pygame.Rect(x - 12, y + 55, 24, 16)
            pygame.draw.rect(self.screen, station["product_color"], product_rect)
            pygame.draw.rect(self.screen, (40, 40, 40), product_rect, 1)
    
    def _draw_vehicles_in_lanes(self):
        """Draw vehicles in exit lanes."""
        if not self._current_state:
            return
        
        hc = self.holonic_config
        lane_width = (hc.factory_width - 100) // 4
        
        # Group vehicles by destination
        vehicles_by_dest = {
            ExitDecision.REUSE: [],
            ExitDecision.REMANUFACTURE: [],
            ExitDecision.RECYCLE: []
        }
        
        for vehicle in self._current_state.active_vehicles:
            if vehicle.destination in vehicles_by_dest:
                vehicles_by_dest[vehicle.destination].append(vehicle)
        
        lane_indices = {
            ExitDecision.REUSE: 0,
            ExitDecision.REMANUFACTURE: 1,
            ExitDecision.RECYCLE: 2
        }
        
        for dest, vehicles in vehicles_by_dest.items():
            lane_idx = lane_indices.get(dest, 3)
            lane_x = 50 + lane_idx * lane_width
            
            for i, vehicle in enumerate(vehicles[:3]):  # Max 3 visible per lane
                vx = lane_x + 30 + i * 45
                vy = hc.exit_lanes_top + 120
                
                # Vehicle body
                if dest == ExitDecision.REUSE:
                    color = self.config.color_product_reuse
                elif dest == ExitDecision.REMANUFACTURE:
                    color = self.config.color_product_remanufacture
                else:
                    color = self.config.color_product_recycle
                
                body_color = (max(0, color[0] - 50), max(0, color[1] - 50), max(0, color[2] - 50))
                pygame.draw.rect(self.screen, body_color, pygame.Rect(vx, vy, 35, 20))
                pygame.draw.rect(self.screen, (30, 30, 30), pygame.Rect(vx, vy, 35, 20), 1)
                
                # Vehicle ID
                label = self.small_font.render(f"V{vehicle.id}", True, (200, 200, 200))
                self.screen.blit(label, (vx + 8, vy + 4))
    
    def _get_health_color(self, holon_id: str) -> Tuple[int, int, int]:
        """Get color based on resource holon health state."""
        hc = self.holonic_config
        
        if not self._enhanced_state or not hasattr(self._enhanced_state, 'resource_health_states'):
            return hc.health_healthy
        
        health_state = self._enhanced_state.resource_health_states.get(holon_id, "HEALTHY")
        
        if health_state == "HEALTHY":
            return hc.health_healthy
        elif health_state == "DEGRADED":
            return hc.health_degraded
        elif health_state == "CRITICAL":
            return hc.health_critical
        elif health_state == "FAILED":
            return hc.health_failed
        else:
            return hc.health_healthy
    
    def _get_strategy_color(self, strategy: str) -> Tuple[int, int, int]:
        """Get color for orchestrator strategy."""
        strategy_colors = {
            "BALANCED": (100, 180, 100),
            "DEEP_DISASSEMBLY": (100, 150, 255),
            "EARLY_RECYCLE": (255, 180, 100),
            "CLEAR_BOTTLENECK": (255, 100, 100),
            "HIGH_VALUE_PRIORITY": (200, 150, 255),
            "RECOVERY_MODE": (255, 150, 150),
            "SURGE_HANDLING": (255, 200, 100)
        }
        return strategy_colors.get(strategy, (150, 150, 150))
    
    def _health_to_color(self, health: float) -> Tuple[int, int, int]:
        """Convert health value (0-1) to color."""
        if health > 0.8:
            return (50, 200, 100)
        elif health > 0.5:
            return (255, 200, 50)
        elif health > 0.2:
            return (255, 150, 50)
        else:
            return (255, 80, 80)
