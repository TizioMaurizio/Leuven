"""
Metrics collection and reporting for DIGITAU Demanufacturing Simulator.

Provides KPI calculation, summary printing, and CSV export for:
- Throughput per exit category (REUSE, REMANUFACTURE, RECYCLE)
- Average product dwell time
- Station utilization
- WIP levels
- Value recovered

CONCEPT MAPPING (from HarbourSim):
- Ship metrics → Batch metrics
- Container metrics → Product metrics
- Crane metrics → Station metrics
- Truck metrics → Exit vehicle metrics
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, TYPE_CHECKING
import csv
from datetime import datetime

if TYPE_CHECKING:
    from demanufacturing_sim.sim.engine import DemanufacturingSimulation
    from demanufacturing_sim.sim.entities import Product, ProductBatch, ExitVehicle


@dataclass
class SimulationMetrics:
    """
    Collected metrics from a demanufacturing simulation run.
    """
    
    # General
    simulation_duration: float = 0.0
    seed: int = 0
    
    # Batch metrics
    total_batches: int = 0
    batches_completed: int = 0
    avg_batch_turnaround_time: float = 0.0
    
    # Product metrics
    total_products: int = 0
    products_processed: int = 0
    products_exited: int = 0
    avg_product_dwell_time: float = 0.0
    min_product_dwell_time: float = 0.0
    max_product_dwell_time: float = 0.0
    avg_total_time: float = 0.0
    avg_processing_time: float = 0.0
    
    # Exit category metrics
    reuse_count: int = 0
    remanufacture_count: int = 0
    recycle_count: int = 0
    reuse_percentage: float = 0.0
    remanufacture_percentage: float = 0.0
    recycle_percentage: float = 0.0
    
    # Quality metrics
    avg_initial_quality: float = 0.0
    avg_final_quality: float = 0.0
    quality_degradation: float = 0.0
    
    # Station utilization
    inspection_utilization: float = 0.0
    dismantling_utilization: float = 0.0
    testing_utilization: float = 0.0
    avg_station_utilization: float = 0.0
    
    # Buffer metrics
    avg_buffer_occupancy: float = 0.0
    max_buffer_occupancy: float = 0.0
    peak_buffer_count: int = 0
    
    # Exit vehicle metrics
    total_vehicles: int = 0
    vehicles_served: int = 0
    vehicles_gave_up: int = 0
    avg_vehicle_wait_time: float = 0.0
    
    # Throughput
    throughput_products_per_hour: float = 0.0
    throughput_reuse_per_hour: float = 0.0
    throughput_remanufacture_per_hour: float = 0.0
    throughput_recycle_per_hour: float = 0.0
    
    # Value metrics
    total_value_recovered: float = 0.0
    value_per_product: float = 0.0
    value_recovery_rate: float = 0.0


class MetricsCollector:
    """
    Collects and calculates metrics from a simulation.
    """
    
    def __init__(self, sim: "DemanufacturingSimulation"):
        self.sim = sim
    
    def collect(self) -> SimulationMetrics:
        """Collect all metrics from the current simulation state."""
        metrics = SimulationMetrics()
        
        # General
        metrics.simulation_duration = self.sim.env.now
        metrics.seed = self.sim._seed
        
        # === Batch metrics ===
        batches = self.sim.batches
        metrics.total_batches = len(batches)
        
        from demanufacturing_sim.sim.entities import BatchState
        completed_batches = [b for b in batches if b.state == BatchState.DEPARTED]
        metrics.batches_completed = len(completed_batches)
        
        if completed_batches:
            turnaround_times = [b.turnaround_time for b in completed_batches if b.turnaround_time]
            if turnaround_times:
                metrics.avg_batch_turnaround_time = sum(turnaround_times) / len(turnaround_times)
        
        # === Product metrics ===
        products = self.sim.all_products
        metrics.total_products = len(products)
        
        from demanufacturing_sim.sim.entities import ProductState, ExitDecision
        
        metrics.products_processed = sum(
            1 for p in products
            if p.state not in (ProductState.CREATED, ProductState.AWAITING_INSPECTION)
        )
        
        exited = [p for p in products if p.state == ProductState.EXITED]
        metrics.products_exited = len(exited)
        
        if exited:
            dwell_times = [p.dwell_time for p in exited if p.dwell_time is not None]
            if dwell_times:
                metrics.avg_product_dwell_time = sum(dwell_times) / len(dwell_times)
                metrics.min_product_dwell_time = min(dwell_times)
                metrics.max_product_dwell_time = max(dwell_times)
            
            total_times = [p.total_time for p in exited if p.total_time is not None]
            if total_times:
                metrics.avg_total_time = sum(total_times) / len(total_times)
            
            processing_times = [p.processing_time for p in exited if p.processing_time is not None]
            if processing_times:
                metrics.avg_processing_time = sum(processing_times) / len(processing_times)
        
        # === Exit category metrics ===
        metrics.reuse_count = self.sim.reuse_count
        metrics.remanufacture_count = self.sim.remanufacture_count
        metrics.recycle_count = self.sim.recycle_count
        
        total_exited = metrics.products_exited
        if total_exited > 0:
            metrics.reuse_percentage = metrics.reuse_count / total_exited * 100
            metrics.remanufacture_percentage = metrics.remanufacture_count / total_exited * 100
            metrics.recycle_percentage = metrics.recycle_count / total_exited * 100
        
        # === Quality metrics ===
        products_with_dpp = [p for p in products if p.dpp is not None]
        if products_with_dpp:
            initial_quals = [p.dpp.initial_quality for p in products_with_dpp]
            final_quals = [p.dpp.current_quality for p in products_with_dpp]
            
            metrics.avg_initial_quality = sum(initial_quals) / len(initial_quals)
            metrics.avg_final_quality = sum(final_quals) / len(final_quals)
            metrics.quality_degradation = metrics.avg_initial_quality - metrics.avg_final_quality
        
        # === Station utilization ===
        metrics.inspection_utilization = self.sim.inspection_stations.utilization
        metrics.dismantling_utilization = self.sim.dismantling_stations.utilization
        metrics.testing_utilization = self.sim.testing_stations.utilization
        
        utils = [metrics.inspection_utilization, metrics.dismantling_utilization, metrics.testing_utilization]
        metrics.avg_station_utilization = sum(utils) / len(utils) if utils else 0.0
        
        # === Buffer metrics ===
        buffer = self.sim.buffer
        if buffer.occupancy_history:
            occupancies = [count / buffer.capacity for _, count in buffer.occupancy_history]
            counts = [count for _, count in buffer.occupancy_history]
            
            metrics.avg_buffer_occupancy = sum(occupancies) / len(occupancies)
            metrics.max_buffer_occupancy = max(occupancies) if occupancies else 0.0
            metrics.peak_buffer_count = max(counts) if counts else 0
        
        # === Exit vehicle metrics ===
        vehicles = self.sim.exit_vehicles
        metrics.total_vehicles = len(vehicles)
        
        from demanufacturing_sim.sim.entities import ExitVehicleState
        
        served = [v for v in vehicles if v.departure_time is not None and v.product is not None]
        metrics.vehicles_served = len(served)
        
        gave_up = [v for v in vehicles if v.departure_time is not None and v.product is None]
        metrics.vehicles_gave_up = len(gave_up)
        
        if served:
            wait_times = [v.wait_time for v in served if v.wait_time is not None]
            if wait_times:
                metrics.avg_vehicle_wait_time = sum(wait_times) / len(wait_times)
        
        # === Throughput ===
        if metrics.simulation_duration > 0:
            hours = metrics.simulation_duration / 60.0
            metrics.throughput_products_per_hour = metrics.products_exited / hours
            metrics.throughput_reuse_per_hour = metrics.reuse_count / hours
            metrics.throughput_remanufacture_per_hour = metrics.remanufacture_count / hours
            metrics.throughput_recycle_per_hour = metrics.recycle_count / hours
        
        # === Value metrics ===
        config = self.sim.config
        metrics.total_value_recovered = (
            metrics.reuse_count * config.value_per_reuse +
            metrics.remanufacture_count * config.value_per_remanufacture +
            metrics.recycle_count * config.value_per_recycle
        )
        
        if metrics.products_exited > 0:
            metrics.value_per_product = metrics.total_value_recovered / metrics.products_exited
        
        # Maximum possible value (if all were reused)
        max_value = metrics.products_exited * config.value_per_reuse
        if max_value > 0:
            metrics.value_recovery_rate = metrics.total_value_recovered / max_value * 100
        
        return metrics
    
    def print_summary(self, metrics: SimulationMetrics = None):
        """Print a formatted summary of metrics."""
        if metrics is None:
            metrics = self.collect()
        
        print("\n" + "=" * 60)
        print("DIGITAU DEMANUFACTURING SIMULATION RESULTS")
        print("=" * 60)
        
        print(f"\nSimulation Duration: {metrics.simulation_duration:.1f} minutes")
        print(f"Random Seed: {metrics.seed}")
        
        print("\n--- BATCH METRICS ---")
        print(f"Total Batches Arrived: {metrics.total_batches}")
        print(f"Batches Completed: {metrics.batches_completed}")
        print(f"Avg Batch Turnaround: {metrics.avg_batch_turnaround_time:.1f} min")
        
        print("\n--- PRODUCT METRICS ---")
        print(f"Total Products: {metrics.total_products}")
        print(f"Products Processed: {metrics.products_processed}")
        print(f"Products Exited: {metrics.products_exited}")
        print(f"Avg Dwell Time: {metrics.avg_product_dwell_time:.1f} min")
        print(f"Avg Total Time: {metrics.avg_total_time:.1f} min")
        print(f"Avg Processing Time: {metrics.avg_processing_time:.1f} min")
        
        print("\n--- EXIT DECISIONS ---")
        print(f"Reuse: {metrics.reuse_count} ({metrics.reuse_percentage:.1f}%)")
        print(f"Remanufacture: {metrics.remanufacture_count} ({metrics.remanufacture_percentage:.1f}%)")
        print(f"Recycle: {metrics.recycle_count} ({metrics.recycle_percentage:.1f}%)")
        
        print("\n--- QUALITY METRICS ---")
        print(f"Avg Initial Quality: {metrics.avg_initial_quality:.3f}")
        print(f"Avg Final Quality: {metrics.avg_final_quality:.3f}")
        print(f"Quality Degradation: {metrics.quality_degradation:.3f}")
        
        print("\n--- STATION UTILIZATION ---")
        print(f"Inspection: {metrics.inspection_utilization * 100:.1f}%")
        print(f"Dismantling: {metrics.dismantling_utilization * 100:.1f}%")
        print(f"Testing: {metrics.testing_utilization * 100:.1f}%")
        print(f"Average: {metrics.avg_station_utilization * 100:.1f}%")
        
        print("\n--- BUFFER METRICS ---")
        print(f"Avg Occupancy: {metrics.avg_buffer_occupancy * 100:.1f}%")
        print(f"Max Occupancy: {metrics.max_buffer_occupancy * 100:.1f}%")
        print(f"Peak Count: {metrics.peak_buffer_count}")
        
        print("\n--- EXIT VEHICLE METRICS ---")
        print(f"Total Vehicles: {metrics.total_vehicles}")
        print(f"Vehicles Served: {metrics.vehicles_served}")
        print(f"Vehicles Gave Up: {metrics.vehicles_gave_up}")
        print(f"Avg Wait Time: {metrics.avg_vehicle_wait_time:.1f} min")
        
        print("\n--- THROUGHPUT ---")
        print(f"Products/Hour: {metrics.throughput_products_per_hour:.1f}")
        print(f"Reuse/Hour: {metrics.throughput_reuse_per_hour:.1f}")
        print(f"Remanufacture/Hour: {metrics.throughput_remanufacture_per_hour:.1f}")
        print(f"Recycle/Hour: {metrics.throughput_recycle_per_hour:.1f}")
        
        print("\n--- VALUE METRICS ---")
        print(f"Total Value Recovered: ${metrics.total_value_recovered:.2f}")
        print(f"Value per Product: ${metrics.value_per_product:.2f}")
        print(f"Value Recovery Rate: {metrics.value_recovery_rate:.1f}%")
        
        print("\n" + "=" * 60)
    
    def export_csv(self, filename: str, metrics: SimulationMetrics = None):
        """Export metrics to CSV file."""
        if metrics is None:
            metrics = self.collect()
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "simulation_duration": metrics.simulation_duration,
            "seed": metrics.seed,
            "total_batches": metrics.total_batches,
            "batches_completed": metrics.batches_completed,
            "total_products": metrics.total_products,
            "products_processed": metrics.products_processed,
            "products_exited": metrics.products_exited,
            "reuse_count": metrics.reuse_count,
            "remanufacture_count": metrics.remanufacture_count,
            "recycle_count": metrics.recycle_count,
            "reuse_percentage": metrics.reuse_percentage,
            "remanufacture_percentage": metrics.remanufacture_percentage,
            "recycle_percentage": metrics.recycle_percentage,
            "avg_dwell_time": metrics.avg_product_dwell_time,
            "avg_total_time": metrics.avg_total_time,
            "avg_processing_time": metrics.avg_processing_time,
            "avg_initial_quality": metrics.avg_initial_quality,
            "avg_final_quality": metrics.avg_final_quality,
            "inspection_utilization": metrics.inspection_utilization,
            "dismantling_utilization": metrics.dismantling_utilization,
            "testing_utilization": metrics.testing_utilization,
            "avg_buffer_occupancy": metrics.avg_buffer_occupancy,
            "throughput_per_hour": metrics.throughput_products_per_hour,
            "total_value_recovered": metrics.total_value_recovered,
            "value_per_product": metrics.value_per_product,
            "value_recovery_rate": metrics.value_recovery_rate,
        }
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            writer.writeheader()
            writer.writerow(data)
        
        print(f"Results exported to {filename}")
