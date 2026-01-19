"""
Entity definitions for the DIGITAU demanufacturing simulation.

Contains dataclasses for Product (with Digital Product Passport),
ProductBatch, and ExitVehicle entities with lifecycle management.

CONCEPT MAPPING (from HarbourSim):
- Container → Product with Digital Product Passport (DPP)
- Ship → ProductBatch (incoming end-of-life product stream)
- Truck → ExitVehicle (carries products to final destinations)
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Tuple, List, Dict, Any
import random
from datetime import datetime


class ProductState(Enum):
    """
    Lifecycle states for a product in the demanufacturing system.
    
    ARRIVAL → INSPECTION → DISMANTLING → TESTING → DECISION → EXIT
    """
    CREATED = auto()          # In incoming batch, not yet processed
    AWAITING_INSPECTION = auto()  # Waiting at inspection queue
    INSPECTING = auto()       # Being inspected
    AWAITING_DISMANTLING = auto()  # Waiting at dismantling queue
    DISMANTLING = auto()      # Being dismantled
    AWAITING_TESTING = auto()  # Waiting at testing queue
    TESTING = auto()          # Being tested
    IN_BUFFER = auto()        # Stored in buffer/WIP area
    AWAITING_EXIT = auto()    # Decision made, waiting for exit vehicle
    LOADING_EXIT = auto()     # Being loaded onto exit vehicle
    EXITED = auto()           # Left the system


class ExitDecision(Enum):
    """
    Exit decision for a product based on quality/condition.
    
    Determined by quality thresholds in configuration.
    """
    UNDECIDED = auto()    # Decision not yet made
    REUSE = auto()        # High quality → direct reuse
    REMANUFACTURE = auto()  # Medium quality → remanufacture
    RECYCLE = auto()      # Low quality → recycle materials


@dataclass
class DigitalProductPassport:
    """
    Digital Product Passport (DPP) - attached to each product.
    
    Contains all lifecycle data, quality assessments, and predictions.
    Updated at each processing stage.
    
    This is a key concept for Industry 4.0 and circular economy tracking.
    """
    product_id: int
    
    # Product metadata
    product_type: str = "battery"
    manufacturer: str = "unknown"
    manufacture_date: Optional[str] = None
    serial_number: str = ""
    
    # Quality and condition
    initial_quality: float = 0.5  # 0.0 to 1.0
    current_quality: float = 0.5
    predicted_quality: float = 0.5
    
    # State predictions
    predicted_decision: ExitDecision = ExitDecision.UNDECIDED
    prediction_confidence: float = 0.0
    
    # Processing history
    processing_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Timestamps
    arrival_time: Optional[float] = None
    inspection_time: Optional[float] = None
    dismantling_time: Optional[float] = None
    testing_time: Optional[float] = None
    decision_time: Optional[float] = None
    exit_time: Optional[float] = None
    
    # Test results
    test_results: Dict[str, Any] = field(default_factory=dict)
    
    # Value tracking
    estimated_value: float = 0.0
    actual_value: float = 0.0
    
    def record_event(self, event_type: str, timestamp: float, details: Dict[str, Any] = None):
        """Record a processing event in the passport."""
        entry = {
            "event": event_type,
            "timestamp": timestamp,
            "details": details or {}
        }
        self.processing_history.append(entry)
    
    def update_quality(self, new_quality: float, timestamp: float, reason: str = ""):
        """Update quality score and record the change."""
        old_quality = self.current_quality
        self.current_quality = max(0.0, min(1.0, new_quality))
        self.record_event("quality_update", timestamp, {
            "old_quality": old_quality,
            "new_quality": self.current_quality,
            "reason": reason
        })
    
    def set_prediction(self, predicted_quality: float, predicted_decision: ExitDecision, 
                       confidence: float, timestamp: float):
        """Set quality and decision predictions."""
        self.predicted_quality = predicted_quality
        self.predicted_decision = predicted_decision
        self.prediction_confidence = confidence
        self.record_event("prediction_made", timestamp, {
            "predicted_quality": predicted_quality,
            "predicted_decision": predicted_decision.name,
            "confidence": confidence
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Export passport to dictionary format."""
        return {
            "product_id": self.product_id,
            "product_type": self.product_type,
            "manufacturer": self.manufacturer,
            "serial_number": self.serial_number,
            "initial_quality": self.initial_quality,
            "current_quality": self.current_quality,
            "predicted_quality": self.predicted_quality,
            "predicted_decision": self.predicted_decision.name,
            "prediction_confidence": self.prediction_confidence,
            "estimated_value": self.estimated_value,
            "processing_history": self.processing_history,
            "test_results": self.test_results
        }


@dataclass
class Product:
    """
    A product entity (e.g., battery) flowing through the demanufacturing system.
    
    Mapped from: Container in HarbourSim
    
    Attributes:
        id: Unique product identifier
        batch_id: ID of the batch this product arrived in
        state: Current lifecycle state
        dpp: Digital Product Passport with full lifecycle data
        exit_decision: Final routing decision
        buffer_position: (x, y, z) position in buffer if stored
        color: RGB color for visualization (based on predicted decision)
    """
    id: int
    batch_id: int
    state: ProductState = ProductState.CREATED
    exit_decision: ExitDecision = ExitDecision.UNDECIDED
    
    # Digital Product Passport
    dpp: DigitalProductPassport = field(default=None)
    
    # Timestamps
    created_time: float = 0.0
    inspection_start_time: Optional[float] = None
    inspection_end_time: Optional[float] = None
    dismantling_start_time: Optional[float] = None
    dismantling_end_time: Optional[float] = None
    testing_start_time: Optional[float] = None
    testing_end_time: Optional[float] = None
    buffer_arrival_time: Optional[float] = None
    exit_request_time: Optional[float] = None
    exit_time: Optional[float] = None
    
    # Position in buffer
    buffer_position: Optional[Tuple[int, int, int]] = None  # (x, y, stack_level)
    
    # Visual color (determined by predicted decision)
    color: Tuple[int, int, int] = field(default_factory=lambda: (150, 150, 150))
    
    def __post_init__(self):
        """Initialize DPP if not provided."""
        if self.dpp is None:
            # Generate random initial quality
            initial_quality = random.gauss(0.5, 0.2)
            initial_quality = max(0.0, min(1.0, initial_quality))
            
            self.dpp = DigitalProductPassport(
                product_id=self.id,
                serial_number=f"PRD-{self.id:06d}",
                initial_quality=initial_quality,
                current_quality=initial_quality,
                predicted_quality=initial_quality,
                arrival_time=self.created_time
            )
    
    @property
    def quality(self) -> float:
        """Current quality score from DPP."""
        return self.dpp.current_quality if self.dpp else 0.5
    
    @property
    def predicted_quality(self) -> float:
        """Predicted quality from DPP."""
        return self.dpp.predicted_quality if self.dpp else 0.5
    
    @property
    def dwell_time(self) -> Optional[float]:
        """Time product spent in buffer (if exited)."""
        if self.buffer_arrival_time is not None and self.exit_time is not None:
            return self.exit_time - self.buffer_arrival_time
        return None
    
    @property
    def total_time(self) -> Optional[float]:
        """Total time from creation to exit."""
        if self.exit_time is not None:
            return self.exit_time - self.created_time
        return None
    
    @property
    def processing_time(self) -> Optional[float]:
        """Total active processing time (inspection + dismantling + testing)."""
        total = 0.0
        if self.inspection_start_time and self.inspection_end_time:
            total += self.inspection_end_time - self.inspection_start_time
        if self.dismantling_start_time and self.dismantling_end_time:
            total += self.dismantling_end_time - self.dismantling_start_time
        if self.testing_start_time and self.testing_end_time:
            total += self.testing_end_time - self.testing_start_time
        return total if total > 0 else None
    
    def transition_to(self, new_state: ProductState, time: float) -> None:
        """
        Transition product to a new state with timestamp recording.
        
        Args:
            new_state: The target state
            time: Current simulation time
        """
        self.state = new_state
        
        if new_state == ProductState.INSPECTING:
            self.inspection_start_time = time
        elif new_state == ProductState.AWAITING_DISMANTLING:
            self.inspection_end_time = time
        elif new_state == ProductState.DISMANTLING:
            self.dismantling_start_time = time
        elif new_state == ProductState.AWAITING_TESTING:
            self.dismantling_end_time = time
        elif new_state == ProductState.TESTING:
            self.testing_start_time = time
        elif new_state == ProductState.IN_BUFFER:
            self.testing_end_time = time
            self.buffer_arrival_time = time
        elif new_state == ProductState.AWAITING_EXIT:
            self.exit_request_time = time
        elif new_state == ProductState.EXITED:
            self.exit_time = time
            if self.dpp:
                self.dpp.exit_time = time
    
    def set_exit_decision(self, decision: ExitDecision, time: float):
        """Set the exit routing decision."""
        self.exit_decision = decision
        if self.dpp:
            self.dpp.record_event("exit_decision", time, {"decision": decision.name})
    
    def update_color_from_decision(self, config):
        """Update visualization color based on predicted/actual decision."""
        decision = self.exit_decision if self.exit_decision != ExitDecision.UNDECIDED else \
                   (self.dpp.predicted_decision if self.dpp else ExitDecision.UNDECIDED)
        
        if decision == ExitDecision.REUSE:
            self.color = config.color_product_reuse
        elif decision == ExitDecision.REMANUFACTURE:
            self.color = config.color_product_remanufacture
        elif decision == ExitDecision.RECYCLE:
            self.color = config.color_product_recycle
        else:
            self.color = config.color_product_unknown


class BatchState(Enum):
    """States for a product batch."""
    ARRIVING = auto()        # Approaching facility
    WAITING_DOCK = auto()    # Waiting for receiving dock
    AT_DOCK = auto()         # At receiving dock
    UNLOADING = auto()       # Products being unloaded
    EMPTY = auto()           # All products unloaded
    DEPARTED = auto()        # Batch carrier departed


@dataclass
class ProductBatch:
    """
    A batch of end-of-life products arriving for processing.
    
    Mapped from: Ship in HarbourSim
    
    Attributes:
        id: Unique batch identifier
        num_products: Total products in this batch
        products: List of Product objects in this batch
        state: Current batch state
        source: Origin of the batch (e.g., collection center)
    """
    id: int
    num_products: int
    products: List[Product] = field(default_factory=list)
    state: BatchState = BatchState.ARRIVING
    source: str = "collection_center"
    
    # Timestamps
    arrival_time: float = 0.0
    dock_time: Optional[float] = None
    unload_complete_time: Optional[float] = None
    departure_time: Optional[float] = None
    
    # Dock assignment
    dock_id: Optional[int] = None
    
    # Visualization
    visual_x: float = 0.0
    visual_y: float = 0.0
    
    def __post_init__(self):
        """Initialize products if not provided."""
        if not self.products:
            self.products = [
                Product(
                    id=self.id * 10000 + i,
                    batch_id=self.id,
                    created_time=self.arrival_time
                )
                for i in range(self.num_products)
            ]
    
    @property
    def turnaround_time(self) -> Optional[float]:
        """Total time from arrival to departure."""
        if self.departure_time is not None:
            return self.departure_time - self.arrival_time
        return None
    
    @property
    def products_remaining(self) -> int:
        """Number of products still in batch (not unloaded)."""
        return sum(
            1 for p in self.products
            if p.state == ProductState.CREATED
        )
    
    @property
    def is_empty(self) -> bool:
        """Check if all products have been unloaded."""
        return self.products_remaining == 0


class ExitVehicleState(Enum):
    """States for an exit vehicle."""
    ARRIVING = auto()        # Approaching gate
    WAITING_GATE = auto()    # Waiting at gate
    AT_GATE = auto()         # At gate, ready for loading
    WAITING_PRODUCT = auto() # Waiting for product
    LOADING = auto()         # Product being loaded
    DEPARTING = auto()       # Leaving
    DEPARTED = auto()        # Left the system


@dataclass
class ExitVehicle:
    """
    A vehicle for transporting processed products to final destinations.
    
    Mapped from: Truck in HarbourSim
    
    Each vehicle is assigned to a specific exit category (REUSE/REMANUFACTURE/RECYCLE).
    
    Attributes:
        id: Unique vehicle identifier
        destination: Which exit path (REUSE, REMANUFACTURE, RECYCLE)
        state: Current vehicle state
        product: The product being carried (if any)
    """
    id: int
    destination: ExitDecision = ExitDecision.UNDECIDED
    state: ExitVehicleState = ExitVehicleState.ARRIVING
    
    # Timestamps
    arrival_time: float = 0.0
    gate_time: Optional[float] = None
    load_start_time: Optional[float] = None
    departure_time: Optional[float] = None
    
    # Cargo
    product: Optional[Product] = None
    
    # Assignment
    gate_id: Optional[int] = None
    
    # Visualization
    visual_x: float = 0.0
    visual_y: float = 0.0
    
    @property
    def wait_time(self) -> Optional[float]:
        """Time spent waiting (arrival to load start)."""
        if self.load_start_time is not None:
            return self.load_start_time - self.arrival_time
        return None
    
    @property
    def total_time(self) -> Optional[float]:
        """Total time in system."""
        if self.departure_time is not None:
            return self.departure_time - self.arrival_time
        return None
