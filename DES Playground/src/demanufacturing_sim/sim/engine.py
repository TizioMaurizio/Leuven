"""
Main simulation engine for DIGITAU Demanufacturing Simulator.

Orchestrates all SimPy processes including product batch arrivals,
multi-stage processing (inspection, dismantling, testing), buffer
management, and exit vehicle departures.

CONCEPT MAPPING (from HarbourSim):
- ship_arrival_process → batch_arrival_process
- ship_process → batch_process
- unload_ship_process → unload_batch_process
- truck_arrival_process → exit_vehicle_arrival_process
- truck_process → exit_vehicle_process

NEW ADDITIONS:
- Multi-stage processing pipeline
- Quality predictions and updates
- Exit decision making
- Digital Product Passport updates
"""

import simpy
import random
import threading
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
import logging

from demanufacturing_sim.config import SimConfig
from demanufacturing_sim.sim.entities import (
    Product, ProductState, ExitDecision,
    ProductBatch, BatchState,
    ExitVehicle, ExitVehicleState
)
from demanufacturing_sim.sim.resources import (
    StationManager, StationType, StationState,
    Buffer, Operator, ExitGateManager, DockManager
)
from demanufacturing_sim.sim.policies import PolicyManager


@dataclass
class SimulationState:
    """
    Thread-safe snapshot of simulation state for visualization.
    """
    time: float = 0.0
    batches: List[ProductBatch] = field(default_factory=list)
    batches_at_dock: Dict[int, ProductBatch] = field(default_factory=dict)
    exit_vehicles: List[ExitVehicle] = field(default_factory=list)
    active_vehicles: List[ExitVehicle] = field(default_factory=list)
    buffer_state: List[List[List[Product]]] = field(default_factory=list)
    
    # Station states
    inspection_states: List[Dict[str, Any]] = field(default_factory=list)
    dismantling_states: List[Dict[str, Any]] = field(default_factory=list)
    testing_states: List[Dict[str, Any]] = field(default_factory=list)
    
    dock_positions: List[Dict[str, float]] = field(default_factory=list)
    
    # Metrics snapshot
    products_processed: int = 0
    products_exited: int = 0
    buffer_occupancy: float = 0.0
    
    # Exit category counts
    reuse_count: int = 0
    remanufacture_count: int = 0
    recycle_count: int = 0
    
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def update(self, **kwargs):
        """Thread-safe update of state."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
    
    def copy(self) -> "SimulationState":
        """Create a copy for reading."""
        with self._lock:
            return SimulationState(
                time=self.time,
                batches=list(self.batches),
                batches_at_dock=dict(self.batches_at_dock),
                exit_vehicles=list(self.exit_vehicles),
                active_vehicles=list(self.active_vehicles),
                buffer_state=self.buffer_state,
                inspection_states=list(self.inspection_states),
                dismantling_states=list(self.dismantling_states),
                testing_states=list(self.testing_states),
                dock_positions=list(self.dock_positions),
                products_processed=self.products_processed,
                products_exited=self.products_exited,
                buffer_occupancy=self.buffer_occupancy,
                reuse_count=self.reuse_count,
                remanufacture_count=self.remanufacture_count,
                recycle_count=self.recycle_count,
            )


@dataclass
class EventLog:
    """Simple event log for debugging."""
    entries: List[Dict[str, Any]] = field(default_factory=list)
    enabled: bool = True
    max_entries: int = 10000
    
    def log(self, time: float, entity_type: str, entity_id: int, action: str, details: str = ""):
        if not self.enabled:
            return
        
        entry = {
            "time": time,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "details": details
        }
        
        self.entries.append(entry)
        
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries // 2:]
    
    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        return self.entries[-n:]


class DemanufacturingSimulation:
    """
    Main simulation class for the demanufacturing digital twin.
    
    Uses SimPy as the core event engine and maintains state snapshots
    for visualization.
    """
    
    def __init__(
        self,
        config: SimConfig = None,
        policies: PolicyManager = None,
        seed: int = None
    ):
        """Initialize the simulation."""
        self.config = config or SimConfig()
        self.policies = policies or PolicyManager.default()
        
        # Random number generator
        self._seed = seed if seed is not None else self.config.seed
        self.rng = random.Random(self._seed)
        
        # Logging
        self.logger = logging.getLogger("demanufacturing_sim")
        
        # SimPy environment
        self.env = simpy.Environment()
        
        # Resources
        self.docks = DockManager(self.env, self.config.num_receiving_docks)
        
        # Processing stations (multi-stage)
        self.inspection_stations = StationManager(
            self.env, StationType.INSPECTION, self.config.num_inspection_stations
        )
        self.dismantling_stations = StationManager(
            self.env, StationType.DISMANTLING, self.config.num_dismantling_stations
        )
        self.testing_stations = StationManager(
            self.env, StationType.TESTING, self.config.num_testing_stations
        )
        
        # Buffer
        self.buffer = Buffer(
            self.env,
            self.config.buffer_width,
            self.config.buffer_height,
            self.config.buffer_max_stack
        )
        
        # Operators
        self.operators = Operator(self.env, self.config.num_operators)
        
        # Exit gates
        self.exit_gates = ExitGateManager(
            self.env,
            self.config.num_reuse_gates,
            self.config.num_remanufacture_gates,
            self.config.num_recycle_gates
        )
        
        # Entity tracking
        self.batches: List[ProductBatch] = []
        self.exit_vehicles: List[ExitVehicle] = []
        self.all_products: List[Product] = []
        
        # Counters
        self._batch_counter = 0
        self._vehicle_counter = 0
        self._product_counter = 0
        
        # Exit counters
        self.reuse_count = 0
        self.remanufacture_count = 0
        self.recycle_count = 0
        
        # State for visualization
        self.state = SimulationState()
        self._update_state_callback: Optional[Callable] = None
        
        # Event logging
        self.event_log = EventLog(enabled=self.config.log_events)
        
        # Running flags
        self._running = False
        self._stop_requested = False
    
    def _random_exponential(self, mean: float) -> float:
        return self.rng.expovariate(1.0 / mean)
    
    def _random_triangular(self, low: float, mode: float, high: float) -> float:
        return self.rng.triangular(low, high, mode)
    
    def _random_int_range(self, low: int, high: int) -> int:
        return self.rng.randint(low, high)
    
    def _random_gauss(self, mean: float, std: float) -> float:
        return self.rng.gauss(mean, std)
    
    def _update_state(self):
        """Update the shared state snapshot for visualization."""
        
        def station_to_dict(station):
            return {
                "id": station.id,
                "state": station.state.name,
                "position_x": station.position_x,
                "position_y": station.position_y,
                "has_product": station.current_product is not None,
                "product_color": station.current_product.color if station.current_product else None,
                "products_processed": station.products_processed
            }
        
        inspection_states = [station_to_dict(s) for s in self.inspection_stations.stations]
        dismantling_states = [station_to_dict(s) for s in self.dismantling_stations.stations]
        testing_states = [station_to_dict(s) for s in self.testing_stations.stations]
        
        dock_positions = [
            {"id": d.id, "position_x": d.position_x, "position_y": d.position_y, 
             "is_occupied": d.is_occupied}
            for d in self.docks.docks
        ]
        
        batches_at_dock = {}
        for batch in self.batches:
            if batch.dock_id is not None and batch.state in (BatchState.AT_DOCK, BatchState.UNLOADING):
                batches_at_dock[batch.dock_id] = batch
        
        active_vehicles = [v for v in self.exit_vehicles if v.state != ExitVehicleState.DEPARTED]
        
        self.state.update(
            time=self.env.now,
            batches=list(self.batches),
            batches_at_dock=batches_at_dock,
            exit_vehicles=list(self.exit_vehicles),
            active_vehicles=active_vehicles,
            buffer_state=self.buffer.get_state_snapshot(),
            inspection_states=inspection_states,
            dismantling_states=dismantling_states,
            testing_states=testing_states,
            dock_positions=dock_positions,
            products_processed=sum(1 for p in self.all_products
                                   if p.state not in (ProductState.CREATED, ProductState.AWAITING_INSPECTION)),
            products_exited=sum(1 for p in self.all_products if p.state == ProductState.EXITED),
            buffer_occupancy=self.buffer.occupancy,
            reuse_count=self.reuse_count,
            remanufacture_count=self.remanufacture_count,
            recycle_count=self.recycle_count,
        )
        
        if self._update_state_callback:
            self._update_state_callback(self.state)
    
    def set_state_callback(self, callback: Callable):
        self._update_state_callback = callback
    
    # === BATCH ARRIVAL PROCESSES ===
    
    def batch_arrival_process(self):
        """Process that generates product batch arrivals."""
        while not self._stop_requested:
            interarrival = self._random_exponential(self.config.batch_interarrival_mean)
            yield self.env.timeout(interarrival)
            
            if self._stop_requested:
                break
            
            self._batch_counter += 1
            num_products = self._random_int_range(
                self.config.products_per_batch_min,
                self.config.products_per_batch_max
            )
            
            batch = ProductBatch(
                id=self._batch_counter,
                num_products=num_products,
                arrival_time=self.env.now
            )
            
            # Initialize products with quality from DPP
            for product in batch.products:
                initial_quality = self._random_gauss(
                    self.config.initial_quality_mean,
                    self.config.initial_quality_std
                )
                initial_quality = max(0.0, min(1.0, initial_quality))
                product.dpp.initial_quality = initial_quality
                product.dpp.current_quality = initial_quality
                product.dpp.arrival_time = self.env.now
                
                # Initial prediction
                self._make_prediction(product)
                product.update_color_from_decision(self.config)
            
            self.all_products.extend(batch.products)
            self.batches.append(batch)
            
            self.event_log.log(
                self.env.now, "Batch", batch.id, "ARRIVED",
                f"products={num_products}"
            )
            
            self.env.process(self.batch_process(batch))
            self._update_state()
    
    def batch_process(self, batch: ProductBatch):
        """Process for a single batch from arrival to departure."""
        batch.state = BatchState.WAITING_DOCK
        
        with self.docks.resource.request() as dock_req:
            yield dock_req
            
            if self._stop_requested:
                return
            
            dock = self.docks.get_available_dock()
            if dock is None:
                self.logger.warning(f"No dock available for batch {batch.id}")
                return
            
            dock.receive_batch(batch)
            batch.dock_id = dock.id
            batch.dock_time = self.env.now
            batch.state = BatchState.AT_DOCK
            
            self.event_log.log(self.env.now, "Batch", batch.id, "DOCKED", f"dock={dock.id}")
            self._update_state()
            
            batch.state = BatchState.UNLOADING
            yield self.env.process(self.unload_batch_process(batch, dock))
            
            if self._stop_requested:
                return
            
            batch.unload_complete_time = self.env.now
            batch.state = BatchState.EMPTY
            
            self.event_log.log(
                self.env.now, "Batch", batch.id, "UNLOAD_COMPLETE",
                f"duration={batch.unload_complete_time - batch.dock_time:.1f}"
            )
            
            dock.release_batch()
            batch.dock_id = None
            
            yield self.env.timeout(1.0)
            
            batch.state = BatchState.DEPARTED
            batch.departure_time = self.env.now
            self._update_state()
    
    def unload_batch_process(self, batch: ProductBatch, dock):
        """Unload all products from a batch and start their processing."""
        products_to_process = [p for p in batch.products if p.state == ProductState.CREATED]
        
        for product in products_to_process:
            if self._stop_requested:
                break
            
            # Brief unload time per product
            yield self.env.timeout(0.5)
            
            # Start product processing pipeline
            self.env.process(self.product_process(product))
            self._update_state()
    
    # === PRODUCT PROCESSING PIPELINE ===
    
    def product_process(self, product: Product):
        """
        Main process for a product through the multi-stage pipeline.
        
        INSPECTION → DISMANTLING → TESTING → BUFFER → EXIT
        """
        # Stage 1: Inspection
        product.transition_to(ProductState.AWAITING_INSPECTION, self.env.now)
        yield self.env.process(self._process_at_station(
            product, self.inspection_stations, "inspection"
        ))
        
        if self._stop_requested:
            return
        
        # Stage 2: Dismantling
        product.transition_to(ProductState.AWAITING_DISMANTLING, self.env.now)
        
        # Check routing policy for skip
        next_stage = self.policies.routing_policy.get_next_stage(product)
        if next_stage == "dismantling":
            yield self.env.process(self._process_at_station(
                product, self.dismantling_stations, "dismantling"
            ))
        
        if self._stop_requested:
            return
        
        # Stage 3: Testing
        product.transition_to(ProductState.AWAITING_TESTING, self.env.now)
        
        next_stage = self.policies.routing_policy.get_next_stage(product)
        if next_stage == "testing":
            yield self.env.process(self._process_at_station(
                product, self.testing_stations, "testing"
            ))
        
        if self._stop_requested:
            return
        
        # Make exit decision
        decision = self.policies.exit_decision_policy.make_decision(product, self.config)
        product.set_exit_decision(decision, self.env.now)
        product.update_color_from_decision(self.config)
        
        # Calculate estimated value
        if decision == ExitDecision.REUSE:
            product.dpp.estimated_value = self.config.value_per_reuse
        elif decision == ExitDecision.REMANUFACTURE:
            product.dpp.estimated_value = self.config.value_per_remanufacture
        else:
            product.dpp.estimated_value = self.config.value_per_recycle
        
        # Place in buffer
        with self.operators.resource.request() as op_req:
            yield op_req
            
            move_time = self._random_triangular(
                self.config.operator_move_time_min,
                self.config.operator_move_time_mode,
                self.config.operator_move_time_max
            )
            yield self.env.timeout(move_time)
            
            slot = self.policies.buffer_policy.select_slot(self.buffer, product)
            if slot is not None:
                self.buffer.place_product(product, slot)
                self.event_log.log(
                    self.env.now, "Product", product.id, "IN_BUFFER",
                    f"decision={decision.name}, slot=({slot.x},{slot.y})"
                )
            else:
                self.event_log.log(
                    self.env.now, "Product", product.id, "BUFFER_FULL", ""
                )
        
        self._update_state()
    
    def _process_at_station(self, product: Product, station_mgr: StationManager, stage: str):
        """Process a product at a station of the given type."""
        with station_mgr.resource.request() as req:
            yield req
            
            if self._stop_requested:
                return
            
            station = station_mgr.get_available_station()
            if station is None:
                yield self.env.timeout(0.1)
                return
            
            station.set_state(StationState.PROCESSING, self.env.now)
            station.current_product = product
            
            # Set product state
            if stage == "inspection":
                product.transition_to(ProductState.INSPECTING, self.env.now)
                time_min = self.config.inspection_time_min
                time_mode = self.config.inspection_time_mode
                time_max = self.config.inspection_time_max
            elif stage == "dismantling":
                product.transition_to(ProductState.DISMANTLING, self.env.now)
                time_min = self.config.dismantling_time_min
                time_mode = self.config.dismantling_time_mode
                time_max = self.config.dismantling_time_max
            else:  # testing
                product.transition_to(ProductState.TESTING, self.env.now)
                time_min = self.config.testing_time_min
                time_mode = self.config.testing_time_mode
                time_max = self.config.testing_time_max
            
            self._update_state()
            
            # Processing time
            process_time = self._random_triangular(time_min, time_mode, time_max)
            yield self.env.timeout(process_time)
            
            if self._stop_requested:
                return
            
            # Update quality (slight degradation during processing)
            if product.dpp:
                new_quality = product.dpp.current_quality - self.config.quality_degradation_per_stage
                product.dpp.update_quality(new_quality, self.env.now, f"{stage}_complete")
                
                # Update prediction after each stage
                self._make_prediction(product)
                product.update_color_from_decision(self.config)
            
            # Record in DPP
            if product.dpp:
                product.dpp.record_event(f"{stage}_complete", self.env.now, {
                    "station_id": station.id,
                    "duration": process_time
                })
            
            station.current_product = None
            station.products_processed += 1
            station.set_state(StationState.IDLE, self.env.now)
            
            self.event_log.log(
                self.env.now, "Product", product.id, f"{stage.upper()}_COMPLETE",
                f"station={station.id}, quality={product.quality:.2f}"
            )
            
            self._update_state()
    
    def _make_prediction(self, product: Product):
        """Make quality and decision predictions for a product."""
        if product.dpp is None:
            return
        
        actual = product.dpp.current_quality
        
        # Add noise to prediction
        noise = self._random_gauss(0, self.config.prediction_noise)
        predicted = actual * self.config.prediction_accuracy + (1 - self.config.prediction_accuracy) * 0.5 + noise
        predicted = max(0.0, min(1.0, predicted))
        
        # Predict decision
        if predicted >= self.config.quality_reuse_threshold:
            pred_decision = ExitDecision.REUSE
        elif predicted >= self.config.quality_remanufacture_threshold:
            pred_decision = ExitDecision.REMANUFACTURE
        else:
            pred_decision = ExitDecision.RECYCLE
        
        confidence = self.config.prediction_accuracy
        product.dpp.set_prediction(predicted, pred_decision, confidence, self.env.now)
    
    # === EXIT VEHICLE PROCESSES ===
    
    def exit_vehicle_arrival_process(self, destination: ExitDecision):
        """Process that generates exit vehicle arrivals for a destination."""
        if destination == ExitDecision.REUSE:
            interarrival = self.config.reuse_vehicle_interarrival
        elif destination == ExitDecision.REMANUFACTURE:
            interarrival = self.config.remanufacture_vehicle_interarrival
        else:
            interarrival = self.config.recycle_vehicle_interarrival
        
        while not self._stop_requested:
            wait = self._random_exponential(interarrival)
            yield self.env.timeout(wait)
            
            if self._stop_requested:
                break
            
            self._vehicle_counter += 1
            vehicle = ExitVehicle(
                id=self._vehicle_counter,
                destination=destination,
                arrival_time=self.env.now
            )
            
            self.exit_vehicles.append(vehicle)
            self.event_log.log(
                self.env.now, "Vehicle", vehicle.id, "ARRIVED",
                f"destination={destination.name}"
            )
            
            self.env.process(self.exit_vehicle_process(vehicle))
            self._update_state()
    
    def exit_vehicle_process(self, vehicle: ExitVehicle):
        """Process for an exit vehicle from arrival to departure."""
        vehicle.state = ExitVehicleState.WAITING_GATE
        
        resource = self.exit_gates.get_resource(vehicle.destination)
        
        with resource.request() as gate_req:
            yield gate_req
            
            if self._stop_requested:
                return
            
            vehicle.state = ExitVehicleState.AT_GATE
            vehicle.gate_time = self.env.now
            self._update_state()
            
            # Wait for product
            vehicle.state = ExitVehicleState.WAITING_PRODUCT
            product = None
            
            max_wait = 60.0
            wait_start = self.env.now
            
            while product is None and not self._stop_requested:
                product = self.buffer.get_product_by_decision(vehicle.destination)
                
                if product is None:
                    if self.env.now - wait_start > max_wait:
                        self.event_log.log(
                            self.env.now, "Vehicle", vehicle.id, "GAVE_UP",
                            "No product available"
                        )
                        vehicle.state = ExitVehicleState.DEPARTING
                        yield self.env.timeout(0.5)
                        vehicle.state = ExitVehicleState.DEPARTED
                        vehicle.departure_time = self.env.now
                        self._update_state()
                        return
                    
                    yield self.env.timeout(1.0)
                    self._update_state()
            
            if product is None or self._stop_requested:
                return
            
            product.transition_to(ProductState.AWAITING_EXIT, self.env.now)
            vehicle.product = product
            
            # Loading
            vehicle.state = ExitVehicleState.LOADING
            vehicle.load_start_time = self.env.now
            product.transition_to(ProductState.LOADING_EXIT, self.env.now)
            
            with self.operators.resource.request() as op_req:
                yield op_req
                
                if self._stop_requested:
                    return
                
                self.buffer.remove_product(product)
                
                load_time = self._random_triangular(
                    self.config.exit_load_time_min,
                    self.config.exit_load_time_mode,
                    self.config.exit_load_time_max
                )
                
                self._update_state()
                yield self.env.timeout(load_time)
            
            if self._stop_requested:
                return
            
            product.transition_to(ProductState.EXITED, self.env.now)
            
            # Update exit counters
            if vehicle.destination == ExitDecision.REUSE:
                self.reuse_count += 1
                product.dpp.actual_value = self.config.value_per_reuse
            elif vehicle.destination == ExitDecision.REMANUFACTURE:
                self.remanufacture_count += 1
                product.dpp.actual_value = self.config.value_per_remanufacture
            else:
                self.recycle_count += 1
                product.dpp.actual_value = self.config.value_per_recycle
            
            # Depart
            vehicle.state = ExitVehicleState.DEPARTING
            self.exit_gates.total_processed += 1
            
            yield self.env.timeout(0.5)
            
            vehicle.state = ExitVehicleState.DEPARTED
            vehicle.departure_time = self.env.now
            
            self.event_log.log(
                self.env.now, "Vehicle", vehicle.id, "DEPARTED",
                f"product={product.id}, decision={vehicle.destination.name}"
            )
            
            self._update_state()
    
    # === MONITORING ===
    
    def monitor_process(self, interval: float = 5.0):
        """Periodic monitoring process for bottleneck analysis."""
        while not self._stop_requested:
            yield self.env.timeout(interval)
            
            now = self.env.now
            buffer_total = self.buffer.total_products()
            insp_busy = self.inspection_stations.busy_count()
            dism_busy = self.dismantling_stations.busy_count()
            test_busy = self.testing_stations.busy_count()
            op_busy = self.operators.busy_count()
            gate_queue = self.exit_gates.queue_length()
            
            if self.config.log_events:
                print(f"[{now:6.1f}] BUFFER={buffer_total}/{self.buffer.capacity} | "
                      f"INSP={insp_busy}/{len(self.inspection_stations.stations)} | "
                      f"DISM={dism_busy}/{len(self.dismantling_stations.stations)} | "
                      f"TEST={test_busy}/{len(self.testing_stations.stations)} | "
                      f"OPS={op_busy}/{self.operators.num_operators} | "
                      f"EXIT_Q={gate_queue} | "
                      f"R/M/C={self.reuse_count}/{self.remanufacture_count}/{self.recycle_count}")
    
    # === SIMULATION CONTROL ===
    
    def initialize(self):
        """Initialize simulation processes without running."""
        if self._running:
            return
        
        self._running = True
        self._stop_requested = False
        
        # Start main processes
        self.env.process(self.batch_arrival_process())
        self.env.process(self.exit_vehicle_arrival_process(ExitDecision.REUSE))
        self.env.process(self.exit_vehicle_arrival_process(ExitDecision.REMANUFACTURE))
        self.env.process(self.exit_vehicle_arrival_process(ExitDecision.RECYCLE))
        self.env.process(self.monitor_process(interval=5.0))
    
    def run(self, duration: float = None, step_callback: Callable = None):
        """Run the simulation."""
        duration = duration or self.config.duration
        
        # Initialize if not already done
        if not self._running:
            self.initialize()
        
        step_size = 0.1
        
        while self.env.now < duration and not self._stop_requested:
            try:
                self.env.run(until=min(self.env.now + step_size, duration))
                self._update_state()
                
                if step_callback:
                    step_callback(self.env.now, self.state)
                    
            except simpy.core.EmptySchedule:
                break
        
        self._running = False
        self._update_state()
    
    def step(self, delta: float = 1.0):
        """Advance simulation by delta time units."""
        target = self.env.now + delta
        self.env.run(until=target)
        self._update_state()
    
    def get_state(self) -> SimulationState:
        """Get current simulation state for visualization."""
        self._update_state()
        return self.state.copy()
    
    def stop(self):
        """Request simulation stop."""
        self._stop_requested = True
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def current_time(self) -> float:
        return self.env.now
