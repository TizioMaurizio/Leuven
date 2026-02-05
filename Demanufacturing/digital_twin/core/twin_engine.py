"""
core/twin_engine.py

SimPy-based digital twin engine for holonic demanufacturing.

ARCHITECTURAL CONSTRAINT:
This module MUST NEVER import from mock_hardware/.
All state updates come via MQTT subscription only.
Communication is strictly unidirectional: mock hardware → MQTT → digital twin
"""

import simpy
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
import threading

from .state_store import StateStore
from holons.product_holon import ProductHolon, ProductState
from holons.resource_holon import ResourceHolon, RobotHolon, OperatorHolon, ResourceState


class TwinEngine:
    """
    SimPy-based digital twin engine.
    
    Maintains synchronized state of all holons based on MQTT updates.
    Provides what-if query capabilities for cognitive mediation.
    
    ARCHITECTURAL CONSTRAINT:
    - Never imports from mock_hardware/
    - Never sends commands back to mock hardware
    - State updates come only through apply_delta() called by MQTTObserver
    """
    
    def __init__(self, db_path: str = ":memory:"):
        """
        Initialize the twin engine.
        
        Args:
            db_path: Path to SQLite database for persistence
        """
        # SimPy environment for discrete event simulation
        self.env = simpy.Environment()
        
        # State storage
        self.store = StateStore(db_path)
        
        # In-memory holon cache for fast access
        self._products: Dict[str, ProductHolon] = {}
        self._robots: Dict[str, RobotHolon] = {}
        self._operators: Dict[str, OperatorHolon] = {}
        
        # Observers for state changes
        self._observers: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics
        self._delta_count = 0
        self._start_time = datetime.now()
    
    def apply_delta(self, payload: Dict[str, Any]):
        """
        Apply a delta update from MQTT.
        
        This is the ONLY entry point for state changes.
        Called by MQTTObserver when messages arrive on holon/+/delta topics.
        
        Args:
            payload: Message payload with holon_id and patches
        """
        holon_id = payload.get("holon_id")
        patches = payload.get("patches", {})
        device_type = payload.get("device_type")
        
        if not holon_id or not patches:
            return
        
        with self._lock:
            self._delta_count += 1
            
            # Determine holon type and apply patches
            if self._is_operator_id(holon_id):
                self._apply_operator_delta(holon_id, patches)
            elif self._is_robot_id(holon_id):
                self._apply_robot_delta(holon_id, patches)
            else:
                self._apply_product_delta(holon_id, patches, device_type)
            
            # Record to history
            self.store.record_patches(holon_id, patches)
            
            # Notify observers
            self._notify_observers(holon_id, patches)
    
    def _is_operator_id(self, holon_id: str) -> bool:
        """Check if holon_id refers to an operator."""
        return holon_id.startswith("op_") or holon_id in self._operators
    
    def _is_robot_id(self, holon_id: str) -> bool:
        """Check if holon_id refers to a robot."""
        return holon_id.startswith("arm_") or holon_id in self._robots
    
    def _apply_product_delta(
        self, 
        holon_id: str, 
        patches: Dict[str, Any],
        device_type: Optional[str] = None
    ):
        """Apply patches to a product holon."""
        if holon_id not in self._products:
            # Create new product holon
            self._products[holon_id] = ProductHolon(
                holon_id=holon_id,
                device_type=device_type or "unknown",
            )
        
        product = self._products[holon_id]
        product.apply_patches(patches)
        
        # Persist to store
        self.store.upsert_holon(holon_id, "product", product.to_dict())
    
    def _apply_robot_delta(self, holon_id: str, patches: Dict[str, Any]):
        """Apply patches to a robot holon."""
        if holon_id not in self._robots:
            self._robots[holon_id] = RobotHolon(holon_id=holon_id)
        
        robot = self._robots[holon_id]
        robot.apply_patches(patches)
        
        self.store.upsert_holon(holon_id, "robot", robot.to_dict())
    
    def _apply_operator_delta(self, holon_id: str, patches: Dict[str, Any]):
        """Apply patches to an operator holon."""
        if holon_id not in self._operators:
            self._operators[holon_id] = OperatorHolon(holon_id=holon_id)
        
        operator = self._operators[holon_id]
        operator.apply_patches(patches)
        
        self.store.upsert_holon(holon_id, "operator", operator.to_dict())
    
    def add_observer(self, callback: Callable[[str, Dict[str, Any]], None]):
        """
        Add an observer for state changes.
        
        Args:
            callback: Function called with (holon_id, patches) on each update
        """
        with self._lock:
            self._observers.append(callback)
    
    def remove_observer(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Remove a state change observer."""
        with self._lock:
            if callback in self._observers:
                self._observers.remove(callback)
    
    def _notify_observers(self, holon_id: str, patches: Dict[str, Any]):
        """Notify all observers of a state change."""
        for observer in self._observers:
            try:
                observer(holon_id, patches)
            except Exception as e:
                print(f"Observer error: {e}")
    
    # ==================== Query Interface ====================
    
    def get_product(self, holon_id: str) -> Optional[ProductHolon]:
        """Get a product holon by ID."""
        with self._lock:
            return self._products.get(holon_id)
    
    def get_all_products(self) -> List[ProductHolon]:
        """Get all product holons."""
        with self._lock:
            return list(self._products.values())
    
    def get_robot(self, holon_id: str) -> Optional[RobotHolon]:
        """Get a robot holon by ID."""
        with self._lock:
            return self._robots.get(holon_id)
    
    def get_all_robots(self) -> List[RobotHolon]:
        """Get all robot holons."""
        with self._lock:
            return list(self._robots.values())
    
    def get_operator(self, holon_id: str) -> Optional[OperatorHolon]:
        """Get an operator holon by ID."""
        with self._lock:
            return self._operators.get(holon_id)
    
    def get_all_operators(self) -> List[OperatorHolon]:
        """Get all operator holons."""
        with self._lock:
            return list(self._operators.values())
    
    def get_products_by_state(self, state: ProductState) -> List[ProductHolon]:
        """Get all products in a specific state."""
        with self._lock:
            return [p for p in self._products.values() if p.state == state]
    
    def get_products_needing_intervention(self) -> List[ProductHolon]:
        """Get products that need human intervention."""
        with self._lock:
            return [p for p in self._products.values() if p.needs_intervention]
    
    # ==================== What-If Queries ====================
    
    def what_if_assign_product(
        self, 
        product_id: str, 
        resource_id: str
    ) -> Dict[str, Any]:
        """
        Simulate assigning a product to a resource.
        
        Returns predicted outcomes without modifying actual state.
        Used by cognitive mediator for decision support.
        
        Args:
            product_id: Product holon to assign
            resource_id: Resource (robot/operator) to assign to
            
        Returns:
            Prediction dictionary with success probability and reasoning
        """
        with self._lock:
            product = self._products.get(product_id)
            robot = self._robots.get(resource_id)
            operator = self._operators.get(resource_id)
            
            if not product:
                return {"error": f"Product {product_id} not found"}
            
            resource = robot or operator
            if not resource:
                return {"error": f"Resource {resource_id} not found"}
            
            # Calculate predicted success probability
            uncertainty = product.uncertainty_map.max_uncertainty()
            
            if robot:
                # Robot assignment
                base_skill = 0.7  # Default robot skill
                fatigue_penalty = robot.fatigue * 0.2
                success_prob = max(0.2, base_skill - uncertainty * 0.5 - fatigue_penalty)
                
                return {
                    "product_id": product_id,
                    "resource_id": resource_id,
                    "resource_type": "robot",
                    "predicted_success_probability": round(success_prob, 2),
                    "uncertainty_level": round(uncertainty, 2),
                    "robot_fatigue": round(robot.fatigue, 2),
                    "recommendation": "proceed" if success_prob > 0.6 else "consider_human",
                    "reasoning": self._generate_reasoning(success_prob, uncertainty, "robot"),
                }
            else:
                # Operator assignment
                cognitive_capacity = 1.0 - operator.cognitive_load
                success_prob = min(0.95, 0.8 + cognitive_capacity * 0.15 - uncertainty * 0.2)
                
                return {
                    "product_id": product_id,
                    "resource_id": resource_id,
                    "resource_type": "operator",
                    "predicted_success_probability": round(success_prob, 2),
                    "uncertainty_level": round(uncertainty, 2),
                    "cognitive_load": round(operator.cognitive_load, 2),
                    "recommendation": "proceed" if operator.cognitive_load < 0.7 else "wait",
                    "reasoning": self._generate_reasoning(success_prob, uncertainty, "operator"),
                }
    
    def _generate_reasoning(
        self, 
        success_prob: float, 
        uncertainty: float, 
        resource_type: str
    ) -> str:
        """Generate human-readable reasoning for what-if query."""
        reasons = []
        
        if uncertainty > 0.7:
            reasons.append("High uncertainty in product state")
        elif uncertainty > 0.4:
            reasons.append("Moderate uncertainty present")
        else:
            reasons.append("Low uncertainty, good conditions")
        
        if success_prob > 0.7:
            reasons.append(f"Good predicted success rate ({success_prob:.0%})")
        elif success_prob > 0.5:
            reasons.append(f"Marginal success rate ({success_prob:.0%})")
        else:
            reasons.append(f"Low success rate ({success_prob:.0%}), intervention recommended")
        
        return "; ".join(reasons)
    
    # ==================== Statistics ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get twin engine statistics."""
        with self._lock:
            runtime = (datetime.now() - self._start_time).total_seconds()
            
            product_states = {}
            for product in self._products.values():
                state_name = product.state.value
                product_states[state_name] = product_states.get(state_name, 0) + 1
            
            return {
                "runtime_seconds": round(runtime, 1),
                "simpy_time": self.env.now,
                "delta_count": self._delta_count,
                "deltas_per_second": round(self._delta_count / max(1, runtime), 2),
                "product_count": len(self._products),
                "robot_count": len(self._robots),
                "operator_count": len(self._operators),
                "product_states": product_states,
                "store_stats": self.store.get_statistics(),
            }
    
    def get_state_snapshot(self) -> Dict[str, Any]:
        """Get a complete snapshot of current twin state."""
        with self._lock:
            return {
                "timestamp": datetime.now().isoformat(),
                "simpy_time": self.env.now,
                "products": [p.to_dict() for p in self._products.values()],
                "robots": [r.to_dict() for r in self._robots.values()],
                "operators": [o.to_dict() for o in self._operators.values()],
            }
