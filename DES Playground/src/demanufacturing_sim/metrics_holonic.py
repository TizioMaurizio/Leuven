"""
Enhanced metrics collection for Holonic Demanufacturing Simulation.

Extends the base MetricsCollector with resilience and holonic-specific metrics:
- Throughput degradation under faults
- Recovery time analysis
- Holon coordination efficiency
- Uncertainty impact analysis
- Orchestrator effectiveness
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, TYPE_CHECKING
import csv
from datetime import datetime

from demanufacturing_sim.metrics import SimulationMetrics, MetricsCollector

if TYPE_CHECKING:
    from demanufacturing_sim.sim.holonic_engine import HolonicDemanufacturingSimulation


@dataclass
class ResilienceMetrics:
    """Metrics for evaluating system resilience under faults."""
    
    # Fault statistics
    fault_scenario: str = "none"
    total_faults_triggered: int = 0
    total_fault_duration: float = 0.0
    
    # Throughput resilience
    baseline_throughput: float = 0.0
    min_throughput_during_fault: float = 0.0
    throughput_degradation_percent: float = 0.0
    throughput_stability: float = 1.0  # 0-1, higher = more stable
    
    # Recovery metrics
    avg_recovery_time: float = 0.0
    max_recovery_time: float = 0.0
    
    # Value flow stability
    value_flow_variance: float = 0.0
    value_flow_stability: float = 1.0


@dataclass
class HolonicMetrics:
    """Metrics specific to holonic multi-agent control."""
    
    # Holon activity
    total_product_holons_created: int = 0
    avg_active_product_holons: float = 0.0
    total_resource_holons: int = 0
    total_transport_holons: int = 0
    
    # Coordination efficiency
    avg_negotiation_rounds: float = 0.0
    task_assignment_success_rate: float = 1.0
    
    # Uncertainty handling
    avg_observation_uncertainty: float = 0.0
    avg_structural_uncertainty: float = 0.0
    uncertainty_impact_on_routing: float = 0.0  # Correlation between uncertainty and routing changes
    
    # Resource health
    avg_resource_health: float = 1.0
    min_resource_health: float = 1.0
    resource_failure_count: int = 0
    avg_repair_time: float = 0.0


@dataclass
class OrchestratorMetrics:
    """Metrics for cognitive orchestrator performance."""
    
    # Activity
    orchestrator_enabled: bool = False
    total_guidance_signals_emitted: int = 0
    unique_strategies_used: int = 0
    strategy_switches: int = 0
    
    # Strategy breakdown
    time_in_balanced: float = 0.0
    time_in_deep_disassembly: float = 0.0
    time_in_early_recycle: float = 0.0
    time_in_clear_bottleneck: float = 0.0
    time_in_high_value_priority: float = 0.0
    time_in_recovery_mode: float = 0.0
    time_in_surge_handling: float = 0.0
    
    # Effectiveness
    bottleneck_detection_count: int = 0
    bottleneck_resolution_success: float = 0.0  # Percentage resolved
    avg_time_to_bottleneck_resolution: float = 0.0


@dataclass
class EnhancedSimulationMetrics(SimulationMetrics):
    """Extended metrics including resilience and holonic information."""
    
    # Control mode
    control_mode: str = "base"
    
    # Resilience
    resilience: ResilienceMetrics = field(default_factory=ResilienceMetrics)
    
    # Holonic
    holonic: HolonicMetrics = field(default_factory=HolonicMetrics)
    
    # Orchestrator
    orchestrator: OrchestratorMetrics = field(default_factory=OrchestratorMetrics)


class EnhancedMetricsCollector(MetricsCollector):
    """
    Extended metrics collector for holonic simulation.
    """
    
    def __init__(self, sim: "HolonicDemanufacturingSimulation"):
        super().__init__(sim)
        self.holonic_sim = sim
    
    def collect_enhanced(self) -> EnhancedSimulationMetrics:
        """Collect all metrics including resilience and holonic."""
        # Get base metrics
        base_metrics = self.collect()
        
        # Create enhanced metrics
        enhanced = EnhancedSimulationMetrics()
        
        # Copy base metrics
        for field_name in SimulationMetrics.__dataclass_fields__:
            setattr(enhanced, field_name, getattr(base_metrics, field_name))
        
        # Determine control mode
        enhanced.control_mode = self.holonic_sim.control_mode
        
        # Collect resilience metrics
        enhanced.resilience = self._collect_resilience_metrics()
        
        # Collect holonic metrics
        enhanced.holonic = self._collect_holonic_metrics()
        
        # Collect orchestrator metrics
        enhanced.orchestrator = self._collect_orchestrator_metrics()
        
        return enhanced
    
    def _collect_resilience_metrics(self) -> ResilienceMetrics:
        """Collect resilience-related metrics."""
        metrics = ResilienceMetrics()
        
        # Fault statistics
        metrics.fault_scenario = self.holonic_sim.fault_scenario_name
        
        fault_stats = self.holonic_sim.fault_injector.get_statistics()
        metrics.total_faults_triggered = fault_stats.get("total_faults_triggered", 0)
        metrics.total_fault_duration = fault_stats.get("total_fault_duration", 0.0)
        
        # Throughput resilience
        throughput_history = self.holonic_sim.throughput_history
        if len(throughput_history) > 5:
            throughputs = [t[1] for t in throughput_history]
            
            # Baseline = first 20% of simulation
            baseline_end = max(1, len(throughputs) // 5)
            baseline_throughputs = throughputs[:baseline_end]
            if baseline_throughputs:
                metrics.baseline_throughput = sum(baseline_throughputs) / len(baseline_throughputs)
            
            # Min throughput (excluding zeros at start)
            non_zero = [t for t in throughputs if t > 0]
            if non_zero:
                metrics.min_throughput_during_fault = min(non_zero)
            
            # Throughput degradation
            if metrics.baseline_throughput > 0:
                metrics.throughput_degradation_percent = (
                    (metrics.baseline_throughput - metrics.min_throughput_during_fault) 
                    / metrics.baseline_throughput * 100
                )
            
            # Stability (inverse of coefficient of variation)
            mean_tp = sum(throughputs) / len(throughputs) if throughputs else 0
            if mean_tp > 0:
                variance = sum((t - mean_tp) ** 2 for t in throughputs) / len(throughputs)
                std = variance ** 0.5
                cv = std / mean_tp if mean_tp > 0 else 0
                metrics.throughput_stability = 1.0 / (1.0 + cv)
        
        # Recovery metrics
        recovery_times = self.holonic_sim.fault_recovery_times
        if recovery_times:
            metrics.avg_recovery_time = sum(recovery_times) / len(recovery_times)
            metrics.max_recovery_time = max(recovery_times)
        
        return metrics
    
    def _collect_holonic_metrics(self) -> HolonicMetrics:
        """Collect holonic multi-agent metrics."""
        metrics = HolonicMetrics()
        
        holon_manager = self.holonic_sim.holon_manager
        
        # Holon counts
        metrics.total_product_holons_created = len(holon_manager.product_holons) + len(self.holonic_sim.all_products)
        metrics.total_resource_holons = len(holon_manager.resource_holons)
        metrics.total_transport_holons = len(holon_manager.transport_holons)
        
        # Current active product holons
        metrics.avg_active_product_holons = len(holon_manager.product_holons)
        
        # Uncertainty metrics from product holons
        product_holons = list(holon_manager.product_holons.values())
        if product_holons:
            obs_uncertainties = [h.observation_uncertainty for h in product_holons]
            struct_uncertainties = [h.structural_uncertainty for h in product_holons]
            
            metrics.avg_observation_uncertainty = sum(obs_uncertainties) / len(obs_uncertainties)
            metrics.avg_structural_uncertainty = sum(struct_uncertainties) / len(struct_uncertainties)
        
        # Resource health metrics
        resource_holons = list(holon_manager.resource_holons.values())
        if resource_holons:
            healths = [h.health_percentage for h in resource_holons]
            metrics.avg_resource_health = sum(healths) / len(healths)
            metrics.min_resource_health = min(healths)
            
            metrics.resource_failure_count = sum(
                1 for h in resource_holons 
                if h.health_state.name == "FAILED"
            )
        
        return metrics
    
    def _collect_orchestrator_metrics(self) -> OrchestratorMetrics:
        """Collect orchestrator performance metrics."""
        metrics = OrchestratorMetrics()
        
        orchestrator = self.holonic_sim.orchestrator
        
        metrics.orchestrator_enabled = orchestrator.is_enabled
        
        if orchestrator.is_enabled:
            # Signal history
            signals = orchestrator.guidance_history
            metrics.total_guidance_signals_emitted = len(signals)
            
            # Strategy tracking
            strategy_times = orchestrator.strategy_time_tracking
            metrics.time_in_balanced = strategy_times.get("BALANCED", 0.0)
            metrics.time_in_deep_disassembly = strategy_times.get("DEEP_DISASSEMBLY", 0.0)
            metrics.time_in_early_recycle = strategy_times.get("EARLY_RECYCLE", 0.0)
            metrics.time_in_clear_bottleneck = strategy_times.get("CLEAR_BOTTLENECK", 0.0)
            metrics.time_in_high_value_priority = strategy_times.get("HIGH_VALUE_PRIORITY", 0.0)
            metrics.time_in_recovery_mode = strategy_times.get("RECOVERY_MODE", 0.0)
            metrics.time_in_surge_handling = strategy_times.get("SURGE_HANDLING", 0.0)
            
            # Count unique strategies used
            metrics.unique_strategies_used = sum(1 for t in strategy_times.values() if t > 0)
            
            # Strategy switches
            metrics.strategy_switches = orchestrator.strategy_switch_count
        
        return metrics
    
    def print_enhanced_summary(self, metrics: EnhancedSimulationMetrics = None):
        """Print enhanced summary including resilience metrics."""
        if metrics is None:
            metrics = self.collect_enhanced()
        
        # Print base summary
        self.print_summary(metrics)
        
        # Print enhanced sections
        print("\n--- CONTROL MODE ---")
        print(f"Mode: {metrics.control_mode.upper()}")
        
        # Resilience
        r = metrics.resilience
        print("\n--- RESILIENCE METRICS ---")
        print(f"Fault Scenario: {r.fault_scenario}")
        print(f"Total Faults Triggered: {r.total_faults_triggered}")
        print(f"Total Fault Duration: {r.total_fault_duration:.1f} min")
        print(f"Baseline Throughput: {r.baseline_throughput:.2f} products/hr")
        print(f"Min Throughput During Fault: {r.min_throughput_during_fault:.2f} products/hr")
        print(f"Throughput Degradation: {r.throughput_degradation_percent:.1f}%")
        print(f"Throughput Stability: {r.throughput_stability:.3f}")
        print(f"Avg Recovery Time: {r.avg_recovery_time:.1f} min")
        
        # Holonic
        h = metrics.holonic
        print("\n--- HOLONIC METRICS ---")
        print(f"Product Holons Created: {h.total_product_holons_created}")
        print(f"Resource Holons: {h.total_resource_holons}")
        print(f"Transport Holons: {h.total_transport_holons}")
        print(f"Avg Observation Uncertainty: {h.avg_observation_uncertainty:.3f}")
        print(f"Avg Structural Uncertainty: {h.avg_structural_uncertainty:.3f}")
        print(f"Avg Resource Health: {h.avg_resource_health:.1f}%")
        print(f"Min Resource Health: {h.min_resource_health:.1f}%")
        print(f"Resource Failures: {h.resource_failure_count}")
        
        # Orchestrator
        o = metrics.orchestrator
        if o.orchestrator_enabled:
            print("\n--- ORCHESTRATOR METRICS ---")
            print(f"Guidance Signals Emitted: {o.total_guidance_signals_emitted}")
            print(f"Unique Strategies Used: {o.unique_strategies_used}")
            print(f"Strategy Switches: {o.strategy_switches}")
            print("Strategy Time Distribution:")
            print(f"  Balanced: {o.time_in_balanced:.1f} min")
            print(f"  Deep Disassembly: {o.time_in_deep_disassembly:.1f} min")
            print(f"  Early Recycle: {o.time_in_early_recycle:.1f} min")
            print(f"  Clear Bottleneck: {o.time_in_clear_bottleneck:.1f} min")
            print(f"  High Value Priority: {o.time_in_high_value_priority:.1f} min")
            print(f"  Recovery Mode: {o.time_in_recovery_mode:.1f} min")
            print(f"  Surge Handling: {o.time_in_surge_handling:.1f} min")
        
        print("\n" + "=" * 60)
    
    def export_enhanced_csv(self, filename: str, metrics: EnhancedSimulationMetrics = None):
        """Export enhanced metrics to CSV."""
        if metrics is None:
            metrics = self.collect_enhanced()
        
        # Flatten all metrics into a single dict
        data = {
            "timestamp": datetime.now().isoformat(),
            "simulation_duration": metrics.simulation_duration,
            "control_mode": metrics.control_mode,
            "seed": metrics.seed,
            
            # Base metrics
            "total_products": metrics.total_products,
            "products_exited": metrics.products_exited,
            "reuse_count": metrics.reuse_count,
            "remanufacture_count": metrics.remanufacture_count,
            "recycle_count": metrics.recycle_count,
            "throughput_per_hour": metrics.throughput_products_per_hour,
            "total_value_recovered": metrics.total_value_recovered,
            "avg_station_utilization": metrics.avg_station_utilization,
            
            # Resilience metrics
            "fault_scenario": metrics.resilience.fault_scenario,
            "total_faults_triggered": metrics.resilience.total_faults_triggered,
            "throughput_degradation_percent": metrics.resilience.throughput_degradation_percent,
            "throughput_stability": metrics.resilience.throughput_stability,
            "avg_recovery_time": metrics.resilience.avg_recovery_time,
            
            # Holonic metrics
            "product_holons_created": metrics.holonic.total_product_holons_created,
            "resource_holons": metrics.holonic.total_resource_holons,
            "avg_observation_uncertainty": metrics.holonic.avg_observation_uncertainty,
            "avg_resource_health": metrics.holonic.avg_resource_health,
            "resource_failure_count": metrics.holonic.resource_failure_count,
            
            # Orchestrator metrics
            "orchestrator_enabled": metrics.orchestrator.orchestrator_enabled,
            "guidance_signals_emitted": metrics.orchestrator.total_guidance_signals_emitted,
            "strategy_switches": metrics.orchestrator.strategy_switches,
        }
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            writer.writeheader()
            writer.writerow(data)
        
        print(f"Enhanced results exported to {filename}")
