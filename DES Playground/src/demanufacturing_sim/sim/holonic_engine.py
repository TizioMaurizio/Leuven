"""
Enhanced Simulation Engine with Holonic Control for DIGITAU.

This module extends the base DemanufacturingSimulation to support:
- Holonic multi-agent control architecture
- Cognitive orchestration layer
- Fault injection and uncertainty modeling
- Switchable control modes (holonic vs orchestrated)
"""

import simpy
import random
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
import threading

from demanufacturing_sim.config import SimConfig
from demanufacturing_sim.sim.engine import DemanufacturingSimulation, SimulationState
from demanufacturing_sim.sim.entities import Product, ProductState, ExitDecision
from demanufacturing_sim.sim.resources import StationState

from demanufacturing_sim.agents.holon_manager import HolonManager, HolonManagerConfig
from demanufacturing_sim.agents.product_holon import DisassemblyIntent
from demanufacturing_sim.orchestrator.llm_orchestrator import (
    CognitiveOrchestrator, OrchestratorConfig, StrategyType
)
from demanufacturing_sim.sim.fault_injection import FaultInjector, FaultScenario
from demanufacturing_sim.policies.orchestrated_modulation import OrchestratedPolicyManager
from demanufacturing_sim.policies.holonic_negotiation import NegotiationManager


class ControlMode:
    """Control mode constants."""
    HOLONIC = "holonic"
    ORCHESTRATED = "orchestrated"


@dataclass
class EnhancedSimulationState(SimulationState):
    """Extended simulation state with holonic and orchestrator info."""
    # Holonic state
    active_product_holons: int = 0
    resource_health_states: Dict[str, str] = field(default_factory=dict)
    transport_states: Dict[str, str] = field(default_factory=dict)
    
    # Orchestrator state
    orchestrator_enabled: bool = False
    current_strategy: str = "BALANCED"
    active_guidance_signals: List[Dict[str, Any]] = field(default_factory=list)
    
    # Fault state
    active_faults: List[Dict[str, Any]] = field(default_factory=list)
    fault_scenario: str = "none"
    
    # Enhanced metrics
    avg_uncertainty: float = 0.0
    high_value_products: int = 0
    system_health: float = 1.0
    throughput_trend: str = "stable"


class HolonicDemanufacturingSimulation(DemanufacturingSimulation):
    """
    Enhanced simulation with holonic control and cognitive orchestration.
    
    Extends the base simulation to support:
    - Two control architectures (holonic, orchestrated)
    - Multi-agent decision making
    - Fault injection and resilience testing
    - Enhanced metrics and visualization state
    """
    
    def __init__(
        self,
        config: SimConfig = None,
        control_mode: str = ControlMode.HOLONIC,
        fault_scenario: str = "none",
        seed: int = None
    ):
        """
        Initialize the holonic simulation.
        
        Args:
            config: Simulation configuration
            control_mode: "holonic" or "orchestrated"
            fault_scenario: Name of fault scenario to use
            seed: Random seed for reproducibility
        """
        # Initialize base simulation
        super().__init__(config, seed=seed)
        
        self.control_mode = control_mode
        self.fault_scenario_name = fault_scenario
        
        # Holon manager
        holon_config = HolonManagerConfig(
            num_agvs=4,
            observation_noise=0.15,
            mtbf_base=480.0,
            mttr_base=30.0
        )
        self.holon_manager = HolonManager(holon_config, seed=self._seed)
        self.holon_manager.initialize_factory_layout(self.config)
        
        # Create resource holons
        self.holon_manager.create_resource_holons(
            self.inspection_stations.stations,
            self.dismantling_stations.stations,
            self.testing_stations.stations
        )
        self.holon_manager.create_transport_holons()
        
        # Policy managers
        self.negotiation_manager = NegotiationManager()
        self.policy_manager = OrchestratedPolicyManager()
        
        # Cognitive orchestrator (only active in orchestrated mode)
        orchestrator_config = OrchestratorConfig(
            update_interval=30.0,
            enabled=(control_mode == ControlMode.ORCHESTRATED)
        )
        self.orchestrator = CognitiveOrchestrator(orchestrator_config)
        
        # Fault injector
        self.fault_injector = FaultInjector(seed=self._seed)
        if fault_scenario != "none":
            scenario = FaultInjector.create_scenario(fault_scenario)
            self.fault_injector.set_scenario(scenario)
        
        # Enhanced state
        self.enhanced_state = EnhancedSimulationState()
        
        # Orchestrator update tracking
        self._last_orchestrator_update = 0.0
        
        # Resilience metrics
        self.throughput_history: List[tuple] = []
        self.fault_recovery_times: List[float] = []
        self._pre_fault_throughput: Optional[float] = None
    
    def set_control_mode(self, mode: str) -> None:
        """
        Switch control mode at runtime.
        
        Args:
            mode: "holonic" or "orchestrated"
        """
        self.control_mode = mode
        self.orchestrator.config.enabled = (mode == ControlMode.ORCHESTRATED)
        
        if mode == ControlMode.HOLONIC:
            # Reset policy manager to defaults
            self.policy_manager.reset_to_defaults()
    
    def _update_state(self):
        """Enhanced state update including holonic info."""
        # Call parent update
        super()._update_state()
        
        # Update enhanced state
        self.enhanced_state.time = self.env.now
        self.enhanced_state.active_product_holons = len(self.holon_manager.product_holons)
        
        # Resource health states
        self.enhanced_state.resource_health_states = {
            holon.id: holon.health_state.name
            for holon in self.holon_manager.resource_holons.values()
        }
        
        # Transport states
        self.enhanced_state.transport_states = {
            holon.id: holon.state.name
            for holon in self.holon_manager.transport_holons.values()
        }
        
        # Orchestrator state
        self.enhanced_state.orchestrator_enabled = self.orchestrator.is_enabled
        self.enhanced_state.current_strategy = self.orchestrator.current_strategy.name
        self.enhanced_state.active_guidance_signals = self.orchestrator.get_active_signals_summary()
        
        # Fault state
        self.enhanced_state.active_faults = self.fault_injector.get_active_faults()
        self.enhanced_state.fault_scenario = self.fault_scenario_name
        
        # Compute enhanced metrics from system holon
        if self.holon_manager.product_holons:
            uncertainties = [
                h.uncertainty_factor 
                for h in self.holon_manager.product_holons.values()
            ]
            self.enhanced_state.avg_uncertainty = sum(uncertainties) / len(uncertainties)
            
            self.enhanced_state.high_value_products = sum(
                1 for h in self.holon_manager.product_holons.values()
                if h.predicted_value > 50.0
            )
        
        # System health from system holon
        context = self.holon_manager.system_holon.get_orchestrator_context()
        self.enhanced_state.system_health = context.get("system_health", 1.0)
        self.enhanced_state.throughput_trend = context.get("throughput_trend", "stable")
        
        # Copy to main state for visualization
        self.state.update(
            time=self.enhanced_state.time,
            products_processed=sum(1 for p in self.all_products
                                   if p.state not in (ProductState.CREATED, ProductState.AWAITING_INSPECTION)),
            products_exited=sum(1 for p in self.all_products if p.state == ProductState.EXITED),
            buffer_occupancy=self.buffer.occupancy,
            reuse_count=self.reuse_count,
            remanufacture_count=self.remanufacture_count,
            recycle_count=self.recycle_count,
        )
    
    def batch_arrival_process(self):
        """Enhanced batch arrival with fault-affected rates."""
        while not self._stop_requested:
            # Get base interarrival time
            base_interarrival = self.config.batch_interarrival_mean
            
            # Apply fault modifier
            rate_multiplier = self.fault_injector.arrival_rate_multiplier
            if rate_multiplier > 1.0:
                # Surge: reduce interarrival time
                interarrival = base_interarrival / rate_multiplier
            else:
                interarrival = base_interarrival
            
            wait = self._random_exponential(interarrival)
            yield self.env.timeout(wait)
            
            if self._stop_requested:
                break
            
            self._batch_counter += 1
            num_products = self._random_int_range(
                self.config.products_per_batch_min,
                self.config.products_per_batch_max
            )
            
            # Create batch (reuse parent logic)
            from demanufacturing_sim.sim.entities import ProductBatch
            batch = ProductBatch(
                id=self._batch_counter,
                num_products=num_products,
                arrival_time=self.env.now
            )
            
            # Initialize products with quality affected by faults
            quality_modifier = self.fault_injector.quality_modifier
            
            for product in batch.products:
                initial_quality = self._random_gauss(
                    self.config.initial_quality_mean + quality_modifier,
                    self.config.initial_quality_std
                )
                initial_quality = max(0.0, min(1.0, initial_quality))
                product.dpp.initial_quality = initial_quality
                product.dpp.current_quality = initial_quality
                product.dpp.arrival_time = self.env.now
                
                self._make_prediction(product)
                product.update_color_from_decision(self.config)
                
                # Create product holon
                self.holon_manager.create_product_holon(product, self.env.now)
            
            self.all_products.extend(batch.products)
            self.batches.append(batch)
            
            self.event_log.log(
                self.env.now, "Batch", batch.id, "ARRIVED",
                f"products={num_products}"
            )
            
            self.env.process(self.batch_process(batch))
            self._update_state()
    
    def product_process(self, product: Product):
        """
        Enhanced product processing with holonic control.
        
        Uses holonic negotiation for resource assignment and
        orchestrator guidance for policy modulation.
        """
        product_holon = self.holon_manager.get_product_holon(product.id)
        
        # Stage 1: Inspection
        product.transition_to(ProductState.AWAITING_INSPECTION, self.env.now)
        if product_holon:
            product_holon.current_stage = "awaiting_inspection"
        
        yield self.env.process(self._process_at_station_holonic(
            product, self.inspection_stations, "inspection"
        ))
        
        if self._stop_requested:
            return
        
        # Process inspection results
        if product_holon:
            results = self.holon_manager.process_inspection_result(
                product.id, self.env.now
            )
            # Update product color based on holon prediction
            if results.get("suggested_route"):
                route_to_decision = {
                    "reuse": ExitDecision.REUSE,
                    "remanufacture": ExitDecision.REMANUFACTURE,
                    "recycle": ExitDecision.RECYCLE,
                    "disposal": ExitDecision.RECYCLE
                }
                if results["suggested_route"] in route_to_decision:
                    product.dpp.predicted_decision = route_to_decision[results["suggested_route"]]
                    product.update_color_from_decision(self.config)
        
        # Stage 2: Dismantling
        product.transition_to(ProductState.AWAITING_DISMANTLING, self.env.now)
        if product_holon:
            product_holon.current_stage = "awaiting_disassembly"
        
        # Check routing policy for skip
        next_stage = self.policies.routing_policy.get_next_stage(product)
        
        # Get disassembly depth from policy manager
        if product_holon:
            depth = self.policy_manager.get_disassembly_depth(
                product_holon.predicted_value,
                product_holon.uncertainty_factor
            )
            if depth == "none":
                next_stage = "testing"  # Skip disassembly
        
        if next_stage == "dismantling":
            yield self.env.process(self._process_at_station_holonic(
                product, self.dismantling_stations, "dismantling"
            ))
            
            # Process disassembly results
            if product_holon:
                self.holon_manager.process_disassembly_result(
                    product.id, self.env.now
                )
        
        if self._stop_requested:
            return
        
        # Stage 3: Testing
        product.transition_to(ProductState.AWAITING_TESTING, self.env.now)
        if product_holon:
            product_holon.current_stage = "awaiting_testing"
        
        next_stage = self.policies.routing_policy.get_next_stage(product)
        if next_stage == "testing":
            yield self.env.process(self._process_at_station_holonic(
                product, self.testing_stations, "testing"
            ))
        
        if self._stop_requested:
            return
        
        # Make exit decision using policy thresholds
        thresholds = self.policy_manager.get_routing_thresholds()
        
        if product.dpp.current_quality >= thresholds["reuse"]:
            decision = ExitDecision.REUSE
        elif product.dpp.current_quality >= thresholds["remanufacture"]:
            decision = ExitDecision.REMANUFACTURE
        else:
            decision = ExitDecision.RECYCLE
        
        product.set_exit_decision(decision, self.env.now)
        product.update_color_from_decision(self.config)
        
        if product_holon:
            product_holon.chosen_route = decision.name.lower()
            product_holon.current_stage = "routed"
        
        # Calculate value
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
                if product_holon:
                    product_holon.current_stage = "in_buffer"
                self.event_log.log(
                    self.env.now, "Product", product.id, "IN_BUFFER",
                    f"decision={decision.name}, slot=({slot.x},{slot.y})"
                )
            else:
                self.event_log.log(
                    self.env.now, "Product", product.id, "BUFFER_FULL", ""
                )
        
        self._update_state()
    
    def _process_at_station_holonic(self, product: Product, 
                                   station_mgr, stage: str):
        """Process at station using holonic negotiation."""
        product_holon = self.holon_manager.get_product_holon(product.id)
        
        # Check for resource failure via fault injection
        for holon in self.holon_manager.resource_holons.values():
            if stage in holon.resource_type.name.lower():
                if self.fault_injector.is_resource_failed(holon.id):
                    holon.health_state = holon.health_state.__class__.FAILED
                    holon.accepts_tasks = False
                else:
                    # Apply degradation
                    degradation = self.fault_injector.get_resource_degradation(holon.id)
                    holon.health_percentage = min(holon.health_percentage, degradation)
        
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
            
            if product_holon:
                product_holon.current_stage = stage
                product_holon.current_station_id = f"resource_{stage}_{station.id}"
            
            self._update_state()
            
            # Processing time with fault modifiers
            base_time = self._random_triangular(time_min, time_mode, time_max)
            
            # Apply processing speed from faults and policy
            speed_factor = self.policy_manager.get_processing_speed_factor()
            fault_factor = self.fault_injector.processing_time_multiplier
            
            process_time = base_time * fault_factor / speed_factor
            yield self.env.timeout(process_time)
            
            if self._stop_requested:
                return
            
            # Update quality (with observation noise from faults)
            if product.dpp:
                noise_mult = self.fault_injector.observation_noise_multiplier
                degradation = self.config.quality_degradation_per_stage
                
                new_quality = product.dpp.current_quality - degradation
                # Add observation noise for inspection
                if stage == "inspection":
                    noise = self._random_gauss(0, 0.05 * noise_mult)
                    new_quality += noise
                
                product.dpp.update_quality(
                    max(0.0, min(1.0, new_quality)), 
                    self.env.now, 
                    f"{stage}_complete"
                )
                
                self._make_prediction(product)
                product.update_color_from_decision(self.config)
            
            station.current_product = None
            station.products_processed += 1
            station.set_state(StationState.IDLE, self.env.now)
            
            self.event_log.log(
                self.env.now, "Product", product.id, f"{stage.upper()}_COMPLETE",
                f"station={station.id}, quality={product.quality:.2f}"
            )
            
            self._update_state()
    
    def orchestrator_process(self):
        """Process that periodically updates orchestrator."""
        while not self._stop_requested:
            yield self.env.timeout(self.orchestrator.config.update_interval)
            
            if not self.orchestrator.is_enabled:
                continue
            
            # Get system context
            context = self.holon_manager.update_system_state(self.env.now)
            
            # Update orchestrator
            guidance = self.orchestrator.update(context, self.env.now)
            
            # Apply guidance
            self.policy_manager.apply_guidance(guidance, self.env.now)
            
            self._update_state()
    
    def fault_monitor_process(self):
        """Process that monitors and applies faults."""
        while not self._stop_requested:
            yield self.env.timeout(1.0)  # Check every minute
            
            # Update fault injector
            actions = self.fault_injector.update(self.env.now)
            
            # Apply fault actions
            for action in actions:
                self._apply_fault_action(action)
            
            # Track throughput for resilience metrics
            current_throughput = self._calculate_current_throughput()
            self.throughput_history.append((self.env.now, current_throughput))
    
    def _apply_fault_action(self, action: Dict[str, Any]) -> None:
        """Apply a fault action to the simulation."""
        if action["action"] == "start_fault":
            fault_type = action["fault_type"]
            target = action["target"]
            
            if fault_type == "RESOURCE_FAILURE":
                # Find and fail the resource holon
                holon = self.holon_manager.resource_holons.get(target)
                if holon:
                    holon.trigger_failure(
                        self.env.now,
                        severity="major",
                        cause=action.get("parameters", {}).get("failure_type", "random")
                    )
                    self._pre_fault_throughput = self._calculate_current_throughput()
            
            elif fault_type == "RESOURCE_DEGRADATION":
                holon = self.holon_manager.resource_holons.get(target)
                if holon:
                    reduction = action.get("parameters", {}).get("capacity_reduction", 0.5)
                    holon.health_percentage *= (1.0 - reduction * action["severity"])
            
            elif fault_type == "TRANSPORT_BLOCK":
                holon = self.holon_manager.transport_holons.get(target)
                if holon:
                    holon.set_blocked(self.env.now, "fault_injection")
            
            self.event_log.log(
                self.env.now, "Fault", 0, "STARTED",
                f"{fault_type} at {target}"
            )
        
        elif action["action"] == "end_fault":
            fault_type = action["fault_type"]
            target = action["target"]
            
            if fault_type == "RESOURCE_FAILURE":
                holon = self.holon_manager.resource_holons.get(target)
                if holon:
                    holon.repair(self.env.now)
                    
                    # Calculate recovery time
                    if self._pre_fault_throughput:
                        current = self._calculate_current_throughput()
                        recovery_ratio = current / self._pre_fault_throughput if self._pre_fault_throughput > 0 else 1.0
                        # Will be updated as system recovers
            
            elif fault_type == "TRANSPORT_BLOCK":
                holon = self.holon_manager.transport_holons.get(target)
                if holon:
                    holon.clear_blocked(self.env.now)
            
            self.event_log.log(
                self.env.now, "Fault", 0, "ENDED",
                f"{fault_type} at {target}"
            )
    
    def _calculate_current_throughput(self) -> float:
        """Calculate current throughput rate."""
        total_exited = self.reuse_count + self.remanufacture_count + self.recycle_count
        if self.env.now > 0:
            return total_exited / (self.env.now / 60.0)  # Per hour
        return 0.0
    
    def initialize(self):
        """Initialize simulation with holonic processes."""
        if self._running:
            return
        
        self._running = True
        self._stop_requested = False
        
        # Start base processes
        self.env.process(self.batch_arrival_process())
        self.env.process(self.exit_vehicle_arrival_process(ExitDecision.REUSE))
        self.env.process(self.exit_vehicle_arrival_process(ExitDecision.REMANUFACTURE))
        self.env.process(self.exit_vehicle_arrival_process(ExitDecision.RECYCLE))
        self.env.process(self.monitor_process(interval=5.0))
        
        # Start holonic processes
        if self.control_mode == ControlMode.ORCHESTRATED:
            self.env.process(self.orchestrator_process())
        
        # Start fault monitoring
        self.env.process(self.fault_monitor_process())
    
    def get_enhanced_state(self) -> EnhancedSimulationState:
        """Get enhanced state for visualization."""
        self._update_state()
        return self.enhanced_state
    
    def get_resilience_metrics(self) -> Dict[str, Any]:
        """Calculate and return resilience metrics."""
        metrics = {}
        
        # Throughput analysis
        if len(self.throughput_history) > 10:
            throughputs = [t[1] for t in self.throughput_history]
            
            # Average throughput
            metrics["avg_throughput"] = sum(throughputs) / len(throughputs)
            
            # Throughput variance (stability)
            if len(throughputs) > 1:
                mean = metrics["avg_throughput"]
                variance = sum((t - mean) ** 2 for t in throughputs) / len(throughputs)
                metrics["throughput_variance"] = variance
                metrics["throughput_stability"] = 1.0 / (1.0 + variance) if variance > 0 else 1.0
            
            # Throughput degradation under faults
            if self.fault_injector.total_faults_triggered > 0:
                # Compare pre-fault to during-fault throughput
                pre_fault_avg = sum(throughputs[:len(throughputs)//3]) / (len(throughputs)//3) if throughputs else 0
                during_fault_avg = sum(throughputs[len(throughputs)//3:]) / (len(throughputs)*2//3) if throughputs else 0
                
                if pre_fault_avg > 0:
                    metrics["throughput_degradation"] = 1.0 - (during_fault_avg / pre_fault_avg)
                else:
                    metrics["throughput_degradation"] = 0.0
        
        # Fault statistics
        fault_stats = self.fault_injector.get_statistics()
        metrics["faults_triggered"] = fault_stats["total_faults_triggered"]
        metrics["total_fault_duration"] = fault_stats["total_fault_duration"]
        
        # Recovery time (simplified)
        if self.fault_recovery_times:
            metrics["avg_recovery_time"] = sum(self.fault_recovery_times) / len(self.fault_recovery_times)
        
        # System health over time
        metrics["final_system_health"] = self.enhanced_state.system_health
        
        return metrics
