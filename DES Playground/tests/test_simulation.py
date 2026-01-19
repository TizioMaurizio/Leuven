"""
Tests for the simulation engine.
"""

import pytest
from harbour_sim.config import SimConfig
from harbour_sim.sim.engine import HarbourSimulation
from harbour_sim.sim.entities import ContainerState, ShipState, TruckState


class TestHarbourSimulation:
    """Tests for HarbourSimulation."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return SimConfig(
            seed=42,
            duration=100.0,  # Short duration for tests
            num_berths=2,
            num_quay_cranes=2,
            yard_width=5,
            yard_height=3,
            yard_max_stack_height=2,
            ship_interarrival_mean=30.0,
            truck_interarrival_mean=10.0,
            num_truck_gates=1,
            log_events=False,  # Disable logging for tests
        )
    
    def test_simulation_creation(self, config):
        """Test simulation initialization."""
        sim = HarbourSimulation(config=config, seed=42)
        
        assert sim.env is not None
        assert len(sim.cranes.cranes) == 2
        assert sim.berths.num_berths == 2
        assert sim.yard.width == 5
        assert sim.yard.height == 3
    
    def test_simulation_deterministic(self, config):
        """Test that same seed produces same results."""
        # Run first simulation
        sim1 = HarbourSimulation(config=config, seed=12345)
        sim1.run(duration=50.0)
        ships1 = len(sim1.ships)
        containers1 = len(sim1.all_containers)
        
        # Run second simulation with same seed
        sim2 = HarbourSimulation(config=config, seed=12345)
        sim2.run(duration=50.0)
        ships2 = len(sim2.ships)
        containers2 = len(sim2.all_containers)
        
        assert ships1 == ships2
        assert containers1 == containers2
    
    def test_simulation_runs(self, config):
        """Test that simulation runs without errors."""
        sim = HarbourSimulation(config=config)
        
        sim.run(duration=50.0)
        
        # Check some basic outcomes
        assert sim.env.now >= 50.0
        assert len(sim.ships) > 0  # At least one ship should arrive
    
    def test_container_state_validity(self, config):
        """Test that container states are valid."""
        sim = HarbourSimulation(config=config)
        sim.run(duration=100.0)
        
        for container in sim.all_containers:
            # All containers should have valid states
            assert container.state in ContainerState
            
            # Check state-dependent invariants
            if container.state == ContainerState.IN_YARD:
                assert container.yard_arrival_time is not None
            
            if container.state == ContainerState.EXITED:
                assert container.exit_time is not None
    
    def test_yard_capacity_not_exceeded(self, config):
        """Test that yard capacity is never exceeded."""
        sim = HarbourSimulation(config=config)
        
        max_count = 0
        
        def check_callback(time, state):
            nonlocal max_count
            count = sim.yard.container_count
            max_count = max(max_count, count)
            assert count <= sim.yard.capacity
        
        sim.run(duration=100.0, step_callback=check_callback)
        
        # Also verify final state
        assert sim.yard.container_count <= sim.yard.capacity
    
    def test_simulation_stop(self, config):
        """Test that simulation can be stopped."""
        sim = HarbourSimulation(config=config)
        
        # Start processes
        sim.env.process(sim.ship_arrival_process())
        sim.env.process(sim.truck_arrival_process())
        
        # Run for a bit
        sim.env.run(until=10.0)
        
        # Stop
        sim.stop()
        
        assert sim._stop_requested is True


class TestSimulationMetrics:
    """Tests for metric collection."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return SimConfig(
            seed=42,
            duration=200.0,
            num_berths=2,
            num_quay_cranes=3,
            ship_interarrival_mean=40.0,
            truck_interarrival_mean=5.0,
            log_events=False,
        )
    
    def test_metrics_collection(self, config):
        """Test that metrics are collected correctly."""
        from harbour_sim.metrics import MetricsCollector
        
        sim = HarbourSimulation(config=config)
        sim.run(duration=200.0)
        
        collector = MetricsCollector(sim)
        metrics = collector.collect()
        
        # Basic sanity checks
        assert metrics.simulation_duration == pytest.approx(200.0, abs=1.0)
        assert metrics.total_ships >= 0
        assert metrics.total_containers >= 0
        assert metrics.total_trucks >= 0
        assert 0.0 <= metrics.crane_utilization <= 1.0
        assert 0.0 <= metrics.avg_yard_occupancy <= 1.0
    
    def test_throughput_calculation(self, config):
        """Test throughput calculations."""
        from harbour_sim.metrics import MetricsCollector
        
        sim = HarbourSimulation(config=config)
        sim.run(duration=200.0)
        
        collector = MetricsCollector(sim)
        metrics = collector.collect()
        
        # Throughput should be non-negative
        assert metrics.throughput_containers_per_hour >= 0
        assert metrics.throughput_trucks_per_hour >= 0
        
        # If containers were delivered, throughput should be positive
        if metrics.containers_delivered > 0:
            assert metrics.throughput_containers_per_hour > 0
