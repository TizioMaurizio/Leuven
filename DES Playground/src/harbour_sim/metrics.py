"""
Metrics collection and reporting for HarbourSim.

Provides KPI calculation, summary printing, and CSV export.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, TYPE_CHECKING
import csv
from datetime import datetime

if TYPE_CHECKING:
    from harbour_sim.sim.engine import HarbourSimulation
    from harbour_sim.sim.entities import Container, Ship, Truck


@dataclass
class SimulationMetrics:
    """
    Collected metrics from a simulation run.
    
    Contains KPIs for throughput, utilization, wait times, etc.
    """
    
    # General
    simulation_duration: float = 0.0
    seed: int = 0
    
    # Ship metrics
    total_ships: int = 0
    ships_completed: int = 0
    avg_ship_turnaround_time: float = 0.0
    min_ship_turnaround_time: float = 0.0
    max_ship_turnaround_time: float = 0.0
    
    # Container metrics
    total_containers: int = 0
    containers_unloaded: int = 0
    containers_delivered: int = 0
    avg_container_dwell_time: float = 0.0
    min_container_dwell_time: float = 0.0
    max_container_dwell_time: float = 0.0
    
    # Crane metrics
    crane_utilization: float = 0.0
    total_crane_unloads: int = 0
    
    # Yard metrics
    avg_yard_occupancy: float = 0.0
    max_yard_occupancy: float = 0.0
    peak_yard_count: int = 0
    
    # Truck metrics
    total_trucks: int = 0
    trucks_served: int = 0
    trucks_gave_up: int = 0
    avg_truck_wait_time: float = 0.0
    min_truck_wait_time: float = 0.0
    max_truck_wait_time: float = 0.0
    avg_truck_total_time: float = 0.0
    
    # Throughput
    throughput_containers_per_hour: float = 0.0
    throughput_trucks_per_hour: float = 0.0


class MetricsCollector:
    """
    Collects and calculates metrics from a simulation.
    """
    
    def __init__(self, sim: "HarbourSimulation"):
        """
        Initialize collector with simulation reference.
        
        Args:
            sim: The simulation to collect metrics from
        """
        self.sim = sim
    
    def collect(self) -> SimulationMetrics:
        """
        Collect all metrics from the current simulation state.
        
        Returns:
            SimulationMetrics with all KPIs calculated.
        """
        metrics = SimulationMetrics()
        
        # General
        metrics.simulation_duration = self.sim.env.now
        metrics.seed = self.sim._seed
        
        # === Ship metrics ===
        ships = self.sim.ships
        metrics.total_ships = len(ships)
        
        completed_ships = [s for s in ships if s.departure_time is not None]
        metrics.ships_completed = len(completed_ships)
        
        if completed_ships:
            turnaround_times = [s.turnaround_time for s in completed_ships if s.turnaround_time]
            if turnaround_times:
                metrics.avg_ship_turnaround_time = sum(turnaround_times) / len(turnaround_times)
                metrics.min_ship_turnaround_time = min(turnaround_times)
                metrics.max_ship_turnaround_time = max(turnaround_times)
        
        # === Container metrics ===
        containers = self.sim.all_containers
        metrics.total_containers = len(containers)
        
        from harbour_sim.sim.entities import ContainerState
        
        metrics.containers_unloaded = sum(
            1 for c in containers 
            if c.state not in (ContainerState.CREATED, ContainerState.UNLOADING)
        )
        
        metrics.containers_delivered = sum(
            1 for c in containers 
            if c.state == ContainerState.EXITED
        )
        
        # Dwell times (for delivered containers)
        delivered = [c for c in containers if c.state == ContainerState.EXITED]
        if delivered:
            dwell_times = [c.dwell_time for c in delivered if c.dwell_time is not None]
            if dwell_times:
                metrics.avg_container_dwell_time = sum(dwell_times) / len(dwell_times)
                metrics.min_container_dwell_time = min(dwell_times)
                metrics.max_container_dwell_time = max(dwell_times)
        
        # === Crane metrics ===
        cranes = self.sim.cranes.cranes
        metrics.total_crane_unloads = sum(c.containers_unloaded for c in cranes)
        
        if metrics.simulation_duration > 0 and cranes:
            total_busy = sum(c.busy_time for c in cranes)
            max_possible = len(cranes) * metrics.simulation_duration
            metrics.crane_utilization = total_busy / max_possible if max_possible > 0 else 0.0
        
        # === Yard metrics ===
        yard = self.sim.yard
        
        if yard.occupancy_history:
            occupancies = [count / yard.capacity for _, count in yard.occupancy_history]
            counts = [count for _, count in yard.occupancy_history]
            
            metrics.avg_yard_occupancy = sum(occupancies) / len(occupancies)
            metrics.max_yard_occupancy = max(occupancies) if occupancies else 0.0
            metrics.peak_yard_count = max(counts) if counts else 0
        
        # === Truck metrics ===
        trucks = self.sim.trucks
        metrics.total_trucks = len(trucks)
        
        from harbour_sim.sim.entities import TruckState
        
        served_trucks = [t for t in trucks if t.departure_time is not None and t.container is not None]
        metrics.trucks_served = len(served_trucks)
        
        gave_up_trucks = [t for t in trucks if t.departure_time is not None and t.container is None]
        metrics.trucks_gave_up = len(gave_up_trucks)
        
        if served_trucks:
            wait_times = [t.wait_time for t in served_trucks if t.wait_time is not None]
            if wait_times:
                metrics.avg_truck_wait_time = sum(wait_times) / len(wait_times)
                metrics.min_truck_wait_time = min(wait_times)
                metrics.max_truck_wait_time = max(wait_times)
            
            total_times = [t.total_time for t in served_trucks if t.total_time is not None]
            if total_times:
                metrics.avg_truck_total_time = sum(total_times) / len(total_times)
        
        # === Throughput ===
        if metrics.simulation_duration > 0:
            hours = metrics.simulation_duration / 60.0
            metrics.throughput_containers_per_hour = metrics.containers_delivered / hours
            metrics.throughput_trucks_per_hour = metrics.trucks_served / hours
        
        return metrics
    
    def print_summary(self, metrics: SimulationMetrics = None):
        """
        Print a formatted summary of metrics.
        
        Args:
            metrics: Pre-collected metrics (collects if None)
        """
        if metrics is None:
            metrics = self.collect()
        
        print("\n" + "=" * 60)
        print("HARBOUR SIMULATION RESULTS")
        print("=" * 60)
        
        print(f"\nSimulation Duration: {metrics.simulation_duration:.1f} minutes")
        print(f"Random Seed: {metrics.seed}")
        
        print("\n--- SHIP METRICS ---")
        print(f"Total Ships Arrived: {metrics.total_ships}")
        print(f"Ships Completed: {metrics.ships_completed}")
        print(f"Avg Turnaround Time: {metrics.avg_ship_turnaround_time:.1f} min")
        print(f"Min/Max Turnaround: {metrics.min_ship_turnaround_time:.1f} / {metrics.max_ship_turnaround_time:.1f} min")
        
        print("\n--- CONTAINER METRICS ---")
        print(f"Total Containers: {metrics.total_containers}")
        print(f"Containers Unloaded: {metrics.containers_unloaded}")
        print(f"Containers Delivered: {metrics.containers_delivered}")
        print(f"Avg Dwell Time: {metrics.avg_container_dwell_time:.1f} min")
        print(f"Min/Max Dwell: {metrics.min_container_dwell_time:.1f} / {metrics.max_container_dwell_time:.1f} min")
        
        print("\n--- CRANE METRICS ---")
        print(f"Total Unload Operations: {metrics.total_crane_unloads}")
        print(f"Crane Utilization: {metrics.crane_utilization * 100:.1f}%")
        
        print("\n--- YARD METRICS ---")
        print(f"Avg Yard Occupancy: {metrics.avg_yard_occupancy * 100:.1f}%")
        print(f"Max Yard Occupancy: {metrics.max_yard_occupancy * 100:.1f}%")
        print(f"Peak Container Count: {metrics.peak_yard_count}")
        
        print("\n--- TRUCK METRICS ---")
        print(f"Total Trucks Arrived: {metrics.total_trucks}")
        print(f"Trucks Served: {metrics.trucks_served}")
        print(f"Trucks Left Without Container: {metrics.trucks_gave_up}")
        print(f"Avg Wait Time: {metrics.avg_truck_wait_time:.1f} min")
        print(f"Min/Max Wait: {metrics.min_truck_wait_time:.1f} / {metrics.max_truck_wait_time:.1f} min")
        print(f"Avg Total Time in System: {metrics.avg_truck_total_time:.1f} min")
        
        print("\n--- THROUGHPUT ---")
        print(f"Containers/Hour: {metrics.throughput_containers_per_hour:.1f}")
        print(f"Trucks/Hour: {metrics.throughput_trucks_per_hour:.1f}")
        
        print("\n" + "=" * 60)
    
    def export_csv(self, filepath: str, metrics: SimulationMetrics = None):
        """
        Export metrics to CSV file.
        
        Args:
            filepath: Output file path
            metrics: Pre-collected metrics (collects if None)
        """
        if metrics is None:
            metrics = self.collect()
        
        # Convert metrics to dict
        data = {
            "timestamp": datetime.now().isoformat(),
            "simulation_duration": metrics.simulation_duration,
            "seed": metrics.seed,
            "total_ships": metrics.total_ships,
            "ships_completed": metrics.ships_completed,
            "avg_ship_turnaround_time": metrics.avg_ship_turnaround_time,
            "total_containers": metrics.total_containers,
            "containers_unloaded": metrics.containers_unloaded,
            "containers_delivered": metrics.containers_delivered,
            "avg_container_dwell_time": metrics.avg_container_dwell_time,
            "crane_utilization": metrics.crane_utilization,
            "total_crane_unloads": metrics.total_crane_unloads,
            "avg_yard_occupancy": metrics.avg_yard_occupancy,
            "max_yard_occupancy": metrics.max_yard_occupancy,
            "peak_yard_count": metrics.peak_yard_count,
            "total_trucks": metrics.total_trucks,
            "trucks_served": metrics.trucks_served,
            "trucks_gave_up": metrics.trucks_gave_up,
            "avg_truck_wait_time": metrics.avg_truck_wait_time,
            "throughput_containers_per_hour": metrics.throughput_containers_per_hour,
            "throughput_trucks_per_hour": metrics.throughput_trucks_per_hour,
        }
        
        # Check if file exists to determine if we need headers
        import os
        file_exists = os.path.exists(filepath)
        
        with open(filepath, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow(data)
        
        print(f"Results exported to {filepath}")
    
    def get_time_series_data(self) -> Dict[str, List]:
        """
        Get time series data for plotting.
        
        Returns:
            Dictionary with time series for various metrics.
        """
        yard = self.sim.yard
        
        times = []
        occupancies = []
        
        for t, count in yard.occupancy_history:
            times.append(t)
            occupancies.append(count / yard.capacity if yard.capacity > 0 else 0)
        
        return {
            "time": times,
            "yard_occupancy": occupancies,
        }
