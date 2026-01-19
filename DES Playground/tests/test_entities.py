"""
Tests for simulation entities.
"""

import pytest
from harbour_sim.sim.entities import (
    Container, ContainerState, Ship, ShipState, Truck, TruckState
)


class TestContainer:
    """Tests for Container entity."""
    
    def test_container_creation(self):
        """Test basic container creation."""
        container = Container(id=1, ship_id=100, created_time=0.0)
        
        assert container.id == 1
        assert container.ship_id == 100
        assert container.state == ContainerState.CREATED
        assert container.created_time == 0.0
        assert container.yard_position is None
    
    def test_container_state_transitions(self):
        """Test container state transitions."""
        container = Container(id=1, ship_id=100, created_time=0.0)
        
        # CREATED -> UNLOADING
        container.transition_to(ContainerState.UNLOADING, 10.0)
        assert container.state == ContainerState.UNLOADING
        assert container.unload_start_time == 10.0
        
        # UNLOADING -> IN_YARD
        container.transition_to(ContainerState.IN_YARD, 15.0)
        assert container.state == ContainerState.IN_YARD
        assert container.yard_arrival_time == 15.0
        
        # IN_YARD -> READY_FOR_PICKUP
        container.transition_to(ContainerState.READY_FOR_PICKUP, 20.0)
        assert container.state == ContainerState.READY_FOR_PICKUP
        assert container.pickup_request_time == 20.0
        
        # READY_FOR_PICKUP -> EXITED
        container.transition_to(ContainerState.EXITED, 25.0)
        assert container.state == ContainerState.EXITED
        assert container.exit_time == 25.0
    
    def test_container_dwell_time(self):
        """Test dwell time calculation."""
        container = Container(id=1, ship_id=100, created_time=0.0)
        
        # No dwell time before yard entry
        assert container.dwell_time is None
        
        container.transition_to(ContainerState.IN_YARD, 10.0)
        assert container.dwell_time is None  # Not exited yet
        
        container.transition_to(ContainerState.EXITED, 30.0)
        assert container.dwell_time == 20.0  # 30 - 10
    
    def test_container_total_time(self):
        """Test total time calculation."""
        container = Container(id=1, ship_id=100, created_time=5.0)
        
        assert container.total_time is None
        
        container.transition_to(ContainerState.EXITED, 50.0)
        assert container.total_time == 45.0  # 50 - 5


class TestShip:
    """Tests for Ship entity."""
    
    def test_ship_creation(self):
        """Test ship creation with containers."""
        ship = Ship(id=1, num_containers=10, arrival_time=0.0)
        
        assert ship.id == 1
        assert ship.num_containers == 10
        assert len(ship.containers) == 10
        assert ship.state == ShipState.ARRIVING
        assert ship.berth_id is None
    
    def test_ship_containers_remaining(self):
        """Test counting remaining containers."""
        ship = Ship(id=1, num_containers=5, arrival_time=0.0)
        
        assert ship.containers_remaining == 5
        
        # Unload one container
        ship.containers[0].transition_to(ContainerState.IN_YARD, 10.0)
        assert ship.containers_remaining == 4
        
        # Unload all
        for c in ship.containers:
            c.transition_to(ContainerState.IN_YARD, 10.0)
        assert ship.containers_remaining == 0
        assert ship.is_empty is True
    
    def test_ship_turnaround_time(self):
        """Test turnaround time calculation."""
        ship = Ship(id=1, num_containers=5, arrival_time=10.0)
        
        assert ship.turnaround_time is None
        
        ship.departure_time = 100.0
        assert ship.turnaround_time == 90.0


class TestTruck:
    """Tests for Truck entity."""
    
    def test_truck_creation(self):
        """Test basic truck creation."""
        truck = Truck(id=1, arrival_time=0.0)
        
        assert truck.id == 1
        assert truck.state == TruckState.ARRIVING
        assert truck.container is None
    
    def test_truck_wait_time(self):
        """Test wait time calculation."""
        truck = Truck(id=1, arrival_time=10.0)
        
        assert truck.wait_time is None
        
        truck.load_start_time = 25.0
        assert truck.wait_time == 15.0  # 25 - 10
    
    def test_truck_total_time(self):
        """Test total time calculation."""
        truck = Truck(id=1, arrival_time=5.0)
        
        assert truck.total_time is None
        
        truck.departure_time = 35.0
        assert truck.total_time == 30.0  # 35 - 5
