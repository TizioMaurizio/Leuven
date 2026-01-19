"""
Metrics collection and reporting for Manufacturing Loop Simulator.

Provides KPI calculation for the closed-loop system:
- Throughput (cycles per time unit)
- Station utilization
- Blocking time
- WIP levels
- Cycle time distribution

Adapted from: MetricsCollector (DIGITAU/HarbourSim)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, TYPE_CHECKING
import csv
from datetime import datetime
import statistics

if TYPE_CHECKING:
    from manufacturing_loop_sim.sim.engine import ClosedLoopSimulation


@dataclass
class SimulationMetrics:
    """Collected metrics from a closed-loop simulation run."""
    
    # General
    simulation_duration: float = 0.0
    seed: int = 0
    num_pallets: int = 0
    
    # Throughput
    total_cycles: int = 0
    throughput_per_second: float = 0.0
    throughput_per_minute: float = 0.0
    
    # Cycle time
    avg_cycle_time: float = 0.0
    min_cycle_time: float = 0.0
    max_cycle_time: float = 0.0
    std_cycle_time: float = 0.0
    
    # Station 1 metrics
    s1_pallets_processed: int = 0
    s1_utilization: float = 0.0
    s1_blocking_ratio: float = 0.0
    s1_total_processing_time: float = 0.0
    s1_total_blocked_time: float = 0.0
    
    # Station 2 metrics
    s2_pallets_processed: int = 0
    s2_utilization: float = 0.0
    s2_blocking_ratio: float = 0.0
    s2_total_processing_time: float = 0.0
    s2_total_blocked_time: float = 0.0
    
    # Conveyor metrics
    conveyor_1_avg_occupancy: float = 0.0
    conveyor_1_max_occupancy: int = 0
    conveyor_2_avg_occupancy: float = 0.0
    conveyor_2_max_occupancy: int = 0
    
    # System-level
    total_blocking_time: float = 0.0
    avg_wip: float = 0.0
    system_efficiency: float = 0.0  # Actual throughput / theoretical max


class MetricsCollector:
    """Collects and calculates metrics from a simulation."""
    
    def __init__(self, sim: "ClosedLoopSimulation"):
        self.sim = sim
    
    def collect(self) -> SimulationMetrics:
        """Collect all metrics from the current simulation state."""
        metrics = SimulationMetrics()
        
        # General
        metrics.simulation_duration = self.sim.env.now
        metrics.seed = self.sim._seed
        metrics.num_pallets = len(self.sim.pallets)
        
        # Throughput
        metrics.total_cycles = sum(p.total_cycles for p in self.sim.pallets)
        if metrics.simulation_duration > 0:
            metrics.throughput_per_second = metrics.total_cycles / metrics.simulation_duration
            metrics.throughput_per_minute = metrics.throughput_per_second * 60
        
        # Cycle times from completed cycles
        all_cycle_times = []
        for pallet in self.sim.pallets:
            for cycle in pallet.completed_cycles:
                if cycle.cycle_time is not None:
                    all_cycle_times.append(cycle.cycle_time)
        
        if all_cycle_times:
            metrics.avg_cycle_time = statistics.mean(all_cycle_times)
            metrics.min_cycle_time = min(all_cycle_times)
            metrics.max_cycle_time = max(all_cycle_times)
            if len(all_cycle_times) > 1:
                metrics.std_cycle_time = statistics.stdev(all_cycle_times)
        
        # Station 1 metrics
        s1 = self.sim.station_1
        # Update final times
        s1.set_state(s1.state, self.sim.env.now)
        
        metrics.s1_pallets_processed = s1.pallets_processed
        metrics.s1_utilization = s1.utilization
        metrics.s1_blocking_ratio = s1.blocking_ratio
        metrics.s1_total_processing_time = s1.total_processing_time
        metrics.s1_total_blocked_time = s1.total_blocked_time
        
        # Station 2 metrics
        s2 = self.sim.station_2
        s2.set_state(s2.state, self.sim.env.now)
        
        metrics.s2_pallets_processed = s2.pallets_processed
        metrics.s2_utilization = s2.utilization
        metrics.s2_blocking_ratio = s2.blocking_ratio
        metrics.s2_total_processing_time = s2.total_processing_time
        metrics.s2_total_blocked_time = s2.total_blocked_time
        
        # Conveyor metrics
        c1 = self.sim.conveyor_1
        c2 = self.sim.conveyor_2
        
        metrics.conveyor_1_avg_occupancy = c1.avg_occupancy
        if c1.occupancy_history:
            metrics.conveyor_1_max_occupancy = max(count for _, count in c1.occupancy_history)
        
        metrics.conveyor_2_avg_occupancy = c2.avg_occupancy
        if c2.occupancy_history:
            metrics.conveyor_2_max_occupancy = max(count for _, count in c2.occupancy_history)
        
        # System-level
        metrics.total_blocking_time = metrics.s1_total_blocked_time + metrics.s2_total_blocked_time
        metrics.avg_wip = metrics.num_pallets  # All pallets always in system
        
        # System efficiency: compare to theoretical max throughput
        # Theoretical max = min(1/avg_s1_time, 1/avg_s2_time)
        avg_s1_time = (self.sim.config.s1_time_min + self.sim.config.s1_time_mode + self.sim.config.s1_time_max) / 3
        avg_s2_time = (self.sim.config.s2_time_min + self.sim.config.s2_time_mode + self.sim.config.s2_time_max) / 3
        theoretical_max = min(1/avg_s1_time, 1/avg_s2_time)
        
        if theoretical_max > 0:
            metrics.system_efficiency = metrics.throughput_per_second / theoretical_max
        
        return metrics
    
    def print_summary(self, metrics: SimulationMetrics = None):
        """Print a formatted summary of metrics."""
        if metrics is None:
            metrics = self.collect()
        
        print("\n" + "=" * 65)
        print("CLOSED-LOOP MANUFACTURING SYSTEM - SIMULATION RESULTS")
        print("=" * 65)
        
        print(f"\nSimulation Duration: {metrics.simulation_duration:.1f} seconds")
        print(f"Random Seed: {metrics.seed}")
        print(f"Number of Pallets: {metrics.num_pallets}")
        
        print("\n--- THROUGHPUT ---")
        print(f"Total Cycles Completed: {metrics.total_cycles}")
        print(f"Throughput: {metrics.throughput_per_second:.4f} cycles/second")
        print(f"Throughput: {metrics.throughput_per_minute:.2f} cycles/minute")
        
        print("\n--- CYCLE TIME ---")
        print(f"Average Cycle Time: {metrics.avg_cycle_time:.2f} seconds")
        print(f"Min Cycle Time: {metrics.min_cycle_time:.2f} seconds")
        print(f"Max Cycle Time: {metrics.max_cycle_time:.2f} seconds")
        print(f"Std Dev Cycle Time: {metrics.std_cycle_time:.2f} seconds")
        
        print("\n--- STATION S1 ---")
        print(f"Pallets Processed: {metrics.s1_pallets_processed}")
        print(f"Utilization: {metrics.s1_utilization * 100:.1f}%")
        print(f"Blocking Ratio: {metrics.s1_blocking_ratio:.2f}")
        print(f"Total Processing Time: {metrics.s1_total_processing_time:.1f}s")
        print(f"Total Blocked Time: {metrics.s1_total_blocked_time:.1f}s")
        
        print("\n--- STATION S2 ---")
        print(f"Pallets Processed: {metrics.s2_pallets_processed}")
        print(f"Utilization: {metrics.s2_utilization * 100:.1f}%")
        print(f"Blocking Ratio: {metrics.s2_blocking_ratio:.2f}")
        print(f"Total Processing Time: {metrics.s2_total_processing_time:.1f}s")
        print(f"Total Blocked Time: {metrics.s2_total_blocked_time:.1f}s")
        
        print("\n--- CONVEYOR BUFFERS ---")
        print(f"Conveyor S1→S2 Avg Occupancy: {metrics.conveyor_1_avg_occupancy * 100:.1f}%")
        print(f"Conveyor S1→S2 Max Count: {metrics.conveyor_1_max_occupancy}")
        print(f"Conveyor S2→S1 Avg Occupancy: {metrics.conveyor_2_avg_occupancy * 100:.1f}%")
        print(f"Conveyor S2→S1 Max Count: {metrics.conveyor_2_max_occupancy}")
        
        print("\n--- SYSTEM PERFORMANCE ---")
        print(f"Total Blocking Time: {metrics.total_blocking_time:.1f}s")
        print(f"System Efficiency: {metrics.system_efficiency * 100:.1f}%")
        
        print("\n" + "=" * 65)
    
    def export_csv(self, filename: str, metrics: SimulationMetrics = None):
        """Export metrics to CSV file."""
        if metrics is None:
            metrics = self.collect()
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "simulation_duration": metrics.simulation_duration,
            "seed": metrics.seed,
            "num_pallets": metrics.num_pallets,
            "total_cycles": metrics.total_cycles,
            "throughput_per_second": metrics.throughput_per_second,
            "throughput_per_minute": metrics.throughput_per_minute,
            "avg_cycle_time": metrics.avg_cycle_time,
            "min_cycle_time": metrics.min_cycle_time,
            "max_cycle_time": metrics.max_cycle_time,
            "std_cycle_time": metrics.std_cycle_time,
            "s1_pallets_processed": metrics.s1_pallets_processed,
            "s1_utilization": metrics.s1_utilization,
            "s1_blocking_ratio": metrics.s1_blocking_ratio,
            "s2_pallets_processed": metrics.s2_pallets_processed,
            "s2_utilization": metrics.s2_utilization,
            "s2_blocking_ratio": metrics.s2_blocking_ratio,
            "conveyor_1_avg_occupancy": metrics.conveyor_1_avg_occupancy,
            "conveyor_2_avg_occupancy": metrics.conveyor_2_avg_occupancy,
            "total_blocking_time": metrics.total_blocking_time,
            "system_efficiency": metrics.system_efficiency,
        }
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            writer.writeheader()
            writer.writerow(data)
        
        print(f"Results exported to {filename}")
