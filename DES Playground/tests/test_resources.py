"""
Tests for simulation resources.
"""

import pytest
import simpy
from harbour_sim.sim.resources import (
    Yard, YardSlot, QuayCraneManager, BerthManager, TruckGate
)
from harbour_sim.sim.entities import Container, ContainerState


class TestYardSlot:
    """Tests for YardSlot."""
    
    def test_slot_creation(self):
        """Test basic slot creation."""
        slot = YardSlot(x=0, y=0, max_height=4)
        
        assert slot.x == 0
        assert slot.y == 0
        assert slot.max_height == 4
        assert slot.height == 0
        assert slot.is_empty is True
        assert slot.is_full is False
    
    def test_add_container(self):
        """Test adding containers to slot."""
        slot = YardSlot(x=1, y=2, max_height=3)
        container = Container(id=1, ship_id=1)
        
        assert slot.add_container(container) is True
        assert slot.height == 1
        assert container.yard_position == (1, 2, 0)
        assert slot.is_empty is False
    
    def test_slot_full(self):
        """Test slot capacity limit."""
        slot = YardSlot(x=0, y=0, max_height=2)
        
        c1 = Container(id=1, ship_id=1)
        c2 = Container(id=2, ship_id=1)
        c3 = Container(id=3, ship_id=1)
        
        assert slot.add_container(c1) is True
        assert slot.add_container(c2) is True
        assert slot.is_full is True
        assert slot.add_container(c3) is False  # Should fail
        assert slot.height == 2
    
    def test_remove_container(self):
        """Test removing containers from slot."""
        slot = YardSlot(x=0, y=0, max_height=4)
        c1 = Container(id=1, ship_id=1)
        c2 = Container(id=2, ship_id=1)
        
        slot.add_container(c1)
        slot.add_container(c2)
        
        removed = slot.remove_top_container()
        assert removed == c2
        assert slot.height == 1
        
        removed = slot.remove_top_container()
        assert removed == c1
        assert slot.is_empty is True
        
        removed = slot.remove_top_container()
        assert removed is None


class TestYard:
    """Tests for Yard."""
    
    def test_yard_creation(self):
        """Test yard creation."""
        env = simpy.Environment()
        yard = Yard(env, width=5, height=3, max_stack_height=4)
        
        assert yard.width == 5
        assert yard.height == 3
        assert yard.capacity == 60  # 5 * 3 * 4
        assert yard.container_count == 0
        assert yard.occupancy == 0.0
    
    def test_place_container(self):
        """Test placing containers in yard."""
        env = simpy.Environment()
        yard = Yard(env, width=3, height=2, max_stack_height=2)
        
        c = Container(id=1, ship_id=1)
        assert yard.place_container(c) is True
        assert yard.container_count == 1
        assert c.state == ContainerState.IN_YARD
    
    def test_find_available_slot(self):
        """Test finding available slots."""
        env = simpy.Environment()
        yard = Yard(env, width=2, height=2, max_stack_height=1)
        
        # Fill up first few slots
        for i in range(3):
            c = Container(id=i, ship_id=1)
            slot = yard.find_available_slot()
            assert slot is not None
            yard.place_container(c, slot)
        
        # One slot left
        slot = yard.find_available_slot()
        assert slot is not None
        
        c = Container(id=99, ship_id=1)
        yard.place_container(c, slot)
        
        # Yard full
        slot = yard.find_available_slot()
        assert slot is None
    
    def test_get_accessible_container(self):
        """Test getting accessible (top) containers."""
        env = simpy.Environment()
        yard = Yard(env, width=2, height=1, max_stack_height=2)
        
        # No containers
        assert yard.get_accessible_container() is None
        
        # Add containers to different slots for FIFO test
        c1 = Container(id=1, ship_id=1, created_time=0.0)
        c2 = Container(id=2, ship_id=1, created_time=1.0)
        
        # Place in different slots so both are accessible
        slot0 = yard.grid[0][0]
        slot1 = yard.grid[1][0]
        
        # Use direct add to avoid env.now being called
        slot0.add_container(c1)
        yard._containers_in_yard.add(c1.id)
        c1.state = ContainerState.IN_YARD
        c1.yard_arrival_time = 5.0  # Later arrival
        
        slot1.add_container(c2)
        yard._containers_in_yard.add(c2.id)
        c2.state = ContainerState.IN_YARD
        c2.yard_arrival_time = 1.0  # Earlier arrival
        
        # Should get c2 first (FIFO - arrived earlier with time 1.0)
        accessible = yard.get_accessible_container()
        assert accessible.id == c2.id  # c2 arrived earlier (time=1.0 < 5.0)
    
    def test_remove_container(self):
        """Test removing containers from yard."""
        env = simpy.Environment()
        yard = Yard(env, width=2, height=1, max_stack_height=2)
        
        c1 = Container(id=1, ship_id=1)
        c2 = Container(id=2, ship_id=1)
        
        slot = yard.grid[0][0]
        yard.place_container(c1, slot)
        yard.place_container(c2, slot)
        
        # Can only remove top container
        assert yard.remove_container(c1) is False  # Not on top
        assert yard.remove_container(c2) is True
        assert yard.container_count == 1
        
        assert yard.remove_container(c1) is True
        assert yard.container_count == 0
    
    def test_negative_capacity_invariant(self):
        """Test that yard count never goes negative."""
        env = simpy.Environment()
        yard = Yard(env, width=2, height=2, max_stack_height=2)
        
        c = Container(id=1, ship_id=1)
        yard.place_container(c)
        yard.remove_container(c)
        
        # Try to remove again
        yard.remove_container(c)  # Should be no-op
        
        assert yard.container_count >= 0


class TestBerthManager:
    """Tests for BerthManager."""
    
    def test_berth_manager_creation(self):
        """Test berth manager creation."""
        env = simpy.Environment()
        manager = BerthManager(env, num_berths=3)
        
        assert manager.num_berths == 3
        assert len(manager.berths) == 3
    
    def test_get_available_berth(self):
        """Test getting available berths."""
        env = simpy.Environment()
        manager = BerthManager(env, num_berths=2)
        
        # Both available
        berth = manager.get_available_berth()
        assert berth is not None
        
        # Occupy first
        class MockShip:
            pass
        
        berth.dock_ship(MockShip())
        
        # Still one available
        berth2 = manager.get_available_berth()
        assert berth2 is not None
        assert berth2 != berth
        
        berth2.dock_ship(MockShip())
        
        # None available
        berth3 = manager.get_available_berth()
        assert berth3 is None


class TestQuayCraneManager:
    """Tests for QuayCraneManager."""
    
    def test_crane_manager_creation(self):
        """Test crane manager creation."""
        env = simpy.Environment()
        manager = QuayCraneManager(env, num_cranes=4)
        
        assert len(manager.cranes) == 4
        assert manager.resource.capacity == 4
    
    def test_utilization_calculation(self):
        """Test utilization calculation."""
        env = simpy.Environment()
        manager = QuayCraneManager(env, num_cranes=2)
        
        # Initially zero
        assert manager.utilization == 0.0
