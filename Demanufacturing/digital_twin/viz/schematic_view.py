"""
viz/schematic_view.py

Pygame-based schematic visualization for the digital twin.

ARCHITECTURAL CONSTRAINT:
This module MUST NEVER import from mock_hardware/.
Visualization is read-only and diagnostic only.
"""

import pygame
import threading
from typing import Optional, Dict, Tuple, Any
from datetime import datetime

from core.twin_engine import TwinEngine
from holons.product_holon import ProductState


# Color palette
COLORS = {
    "background": (30, 30, 40),
    "text": (220, 220, 220),
    "text_dim": (120, 120, 130),
    "grid": (50, 50, 60),
    "panel": (45, 45, 55),
    "panel_border": (70, 70, 80),
    
    # Product states
    "ARRIVED": (100, 180, 255),       # Blue
    "IN_PROGRESS": (255, 200, 50),    # Yellow
    "FAILED_ATTEMPT": (255, 100, 100), # Red
    "REQUIRES_SPECIALIST": (255, 80, 180),  # Pink
    "COMPLETED": (100, 220, 100),     # Green
    "SCRAPPED": (100, 100, 100),      # Gray
    
    # Resources
    "robot_available": (100, 200, 150),
    "robot_busy": (255, 180, 80),
    "operator_available": (120, 180, 255),
    "operator_overloaded": (255, 100, 120),
    
    # UI
    "uncertainty_high": (255, 80, 80),
    "uncertainty_mid": (255, 200, 80),
    "uncertainty_low": (100, 200, 100),
}


class SchematicView:
    """
    Pygame-based schematic visualization.
    
    Displays:
    - Product holons with state colors and progress
    - Resource holons (robots, operators) with status
    - Real-time statistics and uncertainty metrics
    
    ARCHITECTURAL CONSTRAINT:
    - Read-only access to twin state
    - Never modifies twin state
    - Never imports from mock_hardware/
    """
    
    def __init__(
        self,
        twin: TwinEngine,
        width: int = 1200,
        height: int = 800,
        title: str = "Holonic Demanufacturing Digital Twin"
    ):
        """
        Initialize the visualization.
        
        Args:
            twin: TwinEngine to visualize
            width: Window width
            height: Window height
            title: Window title
        """
        self.twin = twin
        self.width = width
        self.height = height
        self.title = title
        
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._screen = None
        self._font = None
        self._font_small = None
        self._clock = None
        
        # Speed control
        self.speed_multiplier = 1.0
        self._speed_options = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0, 512.0]
        self._speed_index = 2  # Default to 1.0x
        self._button_rects = {}
        
        # Activity log
        self._activity_log = []
        self._max_log_entries = 15
    
    def start(self):
        """Start the visualization in a background thread."""
        self._running = True
        
        # Subscribe to twin state changes for activity log
        self.twin.add_observer(self._on_state_change)
        
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="SchematicView"
        )
        self._thread.start()
        print("✓ Visualization started")
    
    def stop(self):
        """Stop the visualization."""
        self._running = False
        
        # Unsubscribe from twin observations
        self.twin.remove_observer(self._on_state_change)
        
        if self._thread:
            self._thread.join(timeout=2.0)
        print("✓ Visualization stopped")
    
    def _run(self):
        """Main visualization loop (runs in background thread)."""
        pygame.init()
        self._screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(self.title)
        
        self._font = pygame.font.SysFont("Consolas", 14)
        self._font_small = pygame.font.SysFont("Consolas", 11)
        self._font_large = pygame.font.SysFont("Consolas", 18, bold=True)
        self._clock = pygame.time.Clock()
        
        while self._running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                    break
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_mouse_click(event.pos)
            
            # Clear screen
            self._screen.fill(COLORS["background"])
            
            # Draw components
            self._draw_header()
            self._draw_speed_controls()
            self._draw_products_panel()
            self._draw_resources_panel()
            self._draw_activity_log_panel()
            self._draw_statistics_panel()
            
            # Update display
            pygame.display.flip()
            self._clock.tick(30)  # 30 FPS
        
        pygame.quit()
    
    def _on_state_change(self, holon_id: str, patches: Dict[str, any]):
        """Handle state change notifications from the twin engine."""
        from datetime import datetime
        
        # Generate activity messages based on patches
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Check for significant state changes
        if "state" in patches:
            state = patches["state"]
            if state == "ARRIVED":
                self._add_log_entry(timestamp, f"📦 {holon_id} arrived", "info")
            elif state == "IN_PROGRESS":
                operator = patches.get("operated_by", "?")
                self._add_log_entry(timestamp, f"🔧 {operator} working on {holon_id}", "work")
            elif state == "COMPLETED":
                self._add_log_entry(timestamp, f"✅ {holon_id} completed", "success")
            elif state == "FAILED_ATTEMPT":
                self._add_log_entry(timestamp, f"⚠️  {holon_id} operation failed", "warning")
            elif state == "REQUIRES_SPECIALIST":
                self._add_log_entry(timestamp, f"🆘 {holon_id} needs specialist", "error")
        
        # Check for operation results
        if "last_operation" in patches:
            op = patches["last_operation"]
            operator = patches.get("operated_by", "?")
            if op == "SUCCESS":
                step = patches.get("disassembly_step", "?")
                self._add_log_entry(timestamp, f"✓ {operator} step {step} on {holon_id}", "success")
            elif op == "FAILURE":
                self._add_log_entry(timestamp, f"✗ {operator} failed on {holon_id}", "warning")
            elif op == "HUMAN_INTERVENTION":
                self._add_log_entry(timestamp, f"👷 {operator} resolved {holon_id}", "success")
        
        # Check for cognitive load warnings
        if "cognitive_load" in patches:
            load = patches["cognitive_load"]
            if load > 0.8:
                self._add_log_entry(timestamp, f"⚡ {holon_id} overloaded ({load:.0%})", "warning")
    
    def _add_log_entry(self, timestamp: str, message: str, level: str):
        """Add an entry to the activity log."""
        self._activity_log.append({
            "timestamp": timestamp,
            "message": message,
            "level": level
        })
        # Keep only the most recent entries
        if len(self._activity_log) > self._max_log_entries:
            self._activity_log.pop(0)
    
    def _handle_mouse_click(self, pos: Tuple[int, int]):
        """Handle mouse click events for UI buttons."""
        x, y = pos
        
        # Check speed control buttons
        if "speed_slower" in self._button_rects:
            rect = self._button_rects["speed_slower"]
            if rect.collidepoint(x, y):
                self._speed_index = max(0, self._speed_index - 1)
                self.speed_multiplier = self._speed_options[self._speed_index]
                print(f"⏱️  Speed: {self.speed_multiplier}x")
        
        if "speed_faster" in self._button_rects:
            rect = self._button_rects["speed_faster"]
            if rect.collidepoint(x, y):
                self._speed_index = min(len(self._speed_options) - 1, self._speed_index + 1)
                self.speed_multiplier = self._speed_options[self._speed_index]
                print(f"⏱️  Speed: {self.speed_multiplier}x")
    
    def _draw_speed_controls(self):
        """Draw speed control buttons."""
        # Panel position (top right area)
        panel_x = self.width - 220
        panel_y = 15
        
        # Speed label
        speed_text = f"Speed: {self.speed_multiplier}x"
        speed_surf = self._font.render(speed_text, True, COLORS["text"])
        self._screen.blit(speed_surf, (panel_x, panel_y))
        
        # Slower button
        button_x = panel_x + 100
        button_y = panel_y - 2
        button_w = 50
        button_h = 24
        
        slower_rect = pygame.Rect(button_x, button_y, button_w, button_h)
        self._button_rects["speed_slower"] = slower_rect
        
        # Button background
        button_color = COLORS["panel"] if self._speed_index > 0 else (30, 30, 35)
        pygame.draw.rect(self._screen, button_color, slower_rect, border_radius=4)
        pygame.draw.rect(self._screen, COLORS["panel_border"], slower_rect, width=1, border_radius=4)
        
        # Button text
        slower_text = self._font_small.render("<<", True, COLORS["text"] if self._speed_index > 0 else COLORS["text_dim"])
        text_rect = slower_text.get_rect(center=slower_rect.center)
        self._screen.blit(slower_text, text_rect)
        
        # Faster button
        button_x += button_w + 5
        faster_rect = pygame.Rect(button_x, button_y, button_w, button_h)
        self._button_rects["speed_faster"] = faster_rect
        
        # Button background
        button_color = COLORS["panel"] if self._speed_index < len(self._speed_options) - 1 else (30, 30, 35)
        pygame.draw.rect(self._screen, button_color, faster_rect, border_radius=4)
        pygame.draw.rect(self._screen, COLORS["panel_border"], faster_rect, width=1, border_radius=4)
        
        # Button text
        faster_text = self._font_small.render(">>", True, COLORS["text"] if self._speed_index < len(self._speed_options) - 1 else COLORS["text_dim"])
        text_rect = faster_text.get_rect(center=faster_rect.center)
        self._screen.blit(faster_text, text_rect)
    
    def _draw_header(self):
        """Draw the header bar."""
        # Title
        title_surf = self._font_large.render(
            "Holonic Demanufacturing Digital Twin",
            True, COLORS["text"]
        )
        self._screen.blit(title_surf, (20, 15))
        
        # Timestamp
        time_str = datetime.now().strftime("%H:%M:%S")
        time_surf = self._font.render(f"Time: {time_str}", True, COLORS["text_dim"])
        self._screen.blit(time_surf, (self.width - 120, 18))
        
        # Separator line
        pygame.draw.line(
            self._screen, COLORS["panel_border"],
            (10, 50), (self.width - 10, 50), 2
        )
    
    def _draw_products_panel(self):
        """Draw the products panel."""
        panel_x = 20
        panel_y = 70
        panel_w = 750
        panel_h = 350
        
        # Panel background
        pygame.draw.rect(
            self._screen, COLORS["panel"],
            (panel_x, panel_y, panel_w, panel_h),
            border_radius=5
        )
        pygame.draw.rect(
            self._screen, COLORS["panel_border"],
            (panel_x, panel_y, panel_w, panel_h),
            width=1, border_radius=5
        )
        
        # Title
        title_surf = self._font.render("Products", True, COLORS["text"])
        self._screen.blit(title_surf, (panel_x + 10, panel_y + 8))
        
        # Products grid
        products = self.twin.get_all_products()
        card_w = 170
        card_h = 70
        cols = 4
        start_x = panel_x + 15
        start_y = panel_y + 35
        
        for i, product in enumerate(products[:16]):  # Show max 16 products
            row = i // cols
            col = i % cols
            x = start_x + col * (card_w + 10)
            y = start_y + row * (card_h + 10)
            
            self._draw_product_card(product, x, y, card_w, card_h)
    
    def _draw_product_card(self, product, x, y, w, h):
        """Draw a single product card."""
        # State color
        state_color = COLORS.get(product.state.value, COLORS["text_dim"])
        
        # Card background
        pygame.draw.rect(
            self._screen, (40, 40, 50),
            (x, y, w, h),
            border_radius=4
        )
        
        # State indicator
        pygame.draw.rect(
            self._screen, state_color,
            (x, y, 5, h),
            border_top_left_radius=4,
            border_bottom_left_radius=4
        )
        
        # Holon ID
        id_surf = self._font_small.render(
            product.holon_id[:15], True, COLORS["text"]
        )
        self._screen.blit(id_surf, (x + 10, y + 5))
        
        # State
        state_surf = self._font_small.render(
            product.state.value[:12], True, state_color
        )
        self._screen.blit(state_surf, (x + 10, y + 20))
        
        # Show operator if being worked on
        if product.operated_by:
            op_surf = self._font_small.render(
                f"by {product.operated_by}", True, COLORS["text_dim"]
            )
            self._screen.blit(op_surf, (x + 100, y + 20))
        
        # Progress bar
        progress = product.progress_percent / 100.0
        bar_w = w - 20
        bar_h = 6
        bar_x = x + 10
        bar_y = y + 38
        
        pygame.draw.rect(
            self._screen, (60, 60, 70),
            (bar_x, bar_y, bar_w, bar_h),
            border_radius=3
        )
        pygame.draw.rect(
            self._screen, state_color,
            (bar_x, bar_y, int(bar_w * progress), bar_h),
            border_radius=3
        )
        
        # Progress percentage text
        if product.disassembly_step > 0:
            prog_text = f"{product.disassembly_step}/{product.total_steps}"
            prog_surf = self._font_small.render(prog_text, True, COLORS["text_dim"])
            self._screen.blit(prog_surf, (x + 10, y + 48))
        
        # Uncertainty indicator
        uncertainty = product.uncertainty_map.max_uncertainty()
        if uncertainty > 0.7:
            u_color = COLORS["uncertainty_high"]
        elif uncertainty > 0.4:
            u_color = COLORS["uncertainty_mid"]
        else:
            u_color = COLORS["uncertainty_low"]
        
        u_surf = self._font_small.render(
            f"U:{uncertainty:.1f}", True, u_color
        )
        self._screen.blit(u_surf, (x + 90, y + h - 18))
        
        # Confidence
        conf_surf = self._font_small.render(
            f"C:{product.confidence:.1f}", True, COLORS["text_dim"]
        )
        self._screen.blit(conf_surf, (x + 130, y + h - 18))
    
    def _draw_resources_panel(self):
        """Draw the resources panel."""
        panel_x = 20
        panel_y = 440
        panel_w = 750
        panel_h = 150
        
        # Panel background
        pygame.draw.rect(
            self._screen, COLORS["panel"],
            (panel_x, panel_y, panel_w, panel_h),
            border_radius=5
        )
        pygame.draw.rect(
            self._screen, COLORS["panel_border"],
            (panel_x, panel_y, panel_w, panel_h),
            width=1, border_radius=5
        )
        
        # Title
        title_surf = self._font.render("Resources", True, COLORS["text"])
        self._screen.blit(title_surf, (panel_x + 10, panel_y + 8))
        
        # Robots
        robots = self.twin.get_all_robots()
        x = panel_x + 20
        y = panel_y + 40
        
        for robot in robots[:4]:
            self._draw_robot_card(robot, x, y)
            x += 180
        
        # Operators
        operators = self.twin.get_all_operators()
        x = panel_x + 20
        y = panel_y + 100
        
        for operator in operators[:4]:
            self._draw_operator_card(operator, x, y)
            x += 180
    
    def _draw_activity_log_panel(self):
        """Draw the activity log panel."""
        panel_x = 20
        panel_y = 610
        panel_w = 750
        panel_h = 170
        
        # Panel background
        pygame.draw.rect(
            self._screen, COLORS["panel"],
            (panel_x, panel_y, panel_w, panel_h),
            border_radius=5
        )
        pygame.draw.rect(
            self._screen, COLORS["panel_border"],
            (panel_x, panel_y, panel_w, panel_h),
            width=1, border_radius=5
        )
        
        # Title
        title_surf = self._font.render("Activity Log", True, COLORS["text"])
        self._screen.blit(title_surf, (panel_x + 10, panel_y + 8))
        
        # Log entries
        y = panel_y + 35
        line_height = 18
        
        # Color mapping for log levels
        level_colors = {
            "info": COLORS["text_dim"],
            "work": COLORS["text"],
            "success": COLORS["COMPLETED"],
            "warning": COLORS["FAILED_ATTEMPT"],
            "error": COLORS["REQUIRES_SPECIALIST"],
        }
        
        # Draw most recent entries (bottom to top)
        visible_entries = self._activity_log[-8:]  # Show last 8 entries
        for entry in visible_entries:
            color = level_colors.get(entry["level"], COLORS["text"])
            
            # Timestamp
            time_surf = self._font_small.render(entry["timestamp"], True, COLORS["text_dim"])
            self._screen.blit(time_surf, (panel_x + 15, y))
            
            # Message
            msg_surf = self._font_small.render(entry["message"], True, color)
            self._screen.blit(msg_surf, (panel_x + 75, y))
            
            y += line_height
    
    def _draw_robot_card(self, robot, x, y):
        """Draw a robot status card."""
        # Determine color based on state
        if robot.state.value == "AVAILABLE":
            color = COLORS["robot_available"]
        else:
            color = COLORS["robot_busy"]
        
        # Robot icon (simple representation)
        pygame.draw.rect(self._screen, color, (x, y, 50, 50), border_radius=5)
        
        # Robot arm symbol
        pygame.draw.line(self._screen, (30, 30, 40), (x + 25, y + 10), (x + 25, y + 30), 3)
        pygame.draw.line(self._screen, (30, 30, 40), (x + 25, y + 30), (x + 40, y + 25), 3)
        
        # ID and status
        id_surf = self._font_small.render(robot.holon_id, True, COLORS["text"])
        self._screen.blit(id_surf, (x + 55, y + 5))
        
        state_surf = self._font_small.render(robot.state.value, True, color)
        self._screen.blit(state_surf, (x + 55, y + 20))
        
        # Show assigned product if working
        if robot.assigned_product:
            prod_surf = self._font_small.render(
                f"→ {robot.assigned_product[:8]}", True, COLORS["text_dim"]
            )
            self._screen.blit(prod_surf, (x + 55, y + 35))
        else:
            fatigue_surf = self._font_small.render(
                f"Fatigue: {robot.fatigue:.0%}", True, COLORS["text_dim"]
            )
            self._screen.blit(fatigue_surf, (x + 55, y + 35))
    
    def _draw_operator_card(self, operator, x, y):
        """Draw an operator status card."""
        # Determine color based on cognitive load
        if operator.is_overloaded:
            color = COLORS["operator_overloaded"]
        else:
            color = COLORS["operator_available"]
        
        # Operator icon (simple person shape)
        pygame.draw.circle(self._screen, color, (x + 25, y + 15), 12)
        pygame.draw.rect(self._screen, color, (x + 15, y + 28, 20, 25), border_radius=3)
        
        # ID and status
        id_surf = self._font_small.render(operator.holon_id, True, COLORS["text"])
        self._screen.blit(id_surf, (x + 55, y + 5))
        
        state_surf = self._font_small.render(operator.state.value, True, color)
        self._screen.blit(state_surf, (x + 55, y + 20))
        
        load_surf = self._font_small.render(
            f"Load: {operator.cognitive_load:.0%}", True, COLORS["text_dim"]
        )
        self._screen.blit(load_surf, (x + 55, y + 35))
    
    def _draw_statistics_panel(self):
        """Draw the statistics panel."""
        panel_x = 790
        panel_y = 70
        panel_w = 390
        panel_h = 710
        
        # Panel background
        pygame.draw.rect(
            self._screen, COLORS["panel"],
            (panel_x, panel_y, panel_w, panel_h),
            border_radius=5
        )
        pygame.draw.rect(
            self._screen, COLORS["panel_border"],
            (panel_x, panel_y, panel_w, panel_h),
            width=1, border_radius=5
        )
        
        # Title
        title_surf = self._font.render("Statistics", True, COLORS["text"])
        self._screen.blit(title_surf, (panel_x + 10, panel_y + 8))
        
        # Get statistics
        stats = self.twin.get_statistics()
        
        y = panel_y + 40
        line_height = 22
        
        # General stats
        self._draw_stat_line("SimPy Time:", f"{stats['simpy_time']:.1f}s", panel_x + 15, y)
        y += line_height
        self._draw_stat_line("Runtime:", f"{stats['runtime_seconds']:.0f}s", panel_x + 15, y)
        y += line_height
        self._draw_stat_line("Deltas Received:", str(stats['delta_count']), panel_x + 15, y)
        y += line_height
        self._draw_stat_line("Deltas/sec:", f"{stats['deltas_per_second']:.1f}", panel_x + 15, y)
        y += line_height * 1.5
        
        # Holon counts
        self._draw_stat_line("Products:", str(stats['product_count']), panel_x + 15, y)
        y += line_height
        self._draw_stat_line("Robots:", str(stats['robot_count']), panel_x + 15, y)
        y += line_height
        self._draw_stat_line("Operators:", str(stats['operator_count']), panel_x + 15, y)
        y += line_height * 1.5
        
        # Product states breakdown
        states_title = self._font_small.render("Product States:", True, COLORS["text"])
        self._screen.blit(states_title, (panel_x + 15, y))
        y += line_height
        
        for state_name, count in stats.get('product_states', {}).items():
            color = COLORS.get(state_name, COLORS["text_dim"])
            self._draw_stat_line(f"  {state_name}:", str(count), panel_x + 15, y, color)
            y += line_height
        
        # Legend
        y = panel_y + panel_h - 120
        legend_title = self._font_small.render("Legend:", True, COLORS["text"])
        self._screen.blit(legend_title, (panel_x + 15, y))
        y += line_height
        
        for state in ["ARRIVED", "IN_PROGRESS", "COMPLETED", "FAILED_ATTEMPT"]:
            color = COLORS.get(state, COLORS["text_dim"])
            pygame.draw.rect(self._screen, color, (panel_x + 20, y + 3, 12, 12))
            label = self._font_small.render(state, True, COLORS["text_dim"])
            self._screen.blit(label, (panel_x + 38, y))
            y += line_height
    
    def _draw_stat_line(self, label: str, value: str, x: int, y: int, color=None):
        """Draw a statistics line."""
        label_surf = self._font_small.render(label, True, COLORS["text_dim"])
        self._screen.blit(label_surf, (x, y))
        
        value_surf = self._font_small.render(value, True, color or COLORS["text"])
        self._screen.blit(value_surf, (x + 150, y))
