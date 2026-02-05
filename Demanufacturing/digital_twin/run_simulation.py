#!/usr/bin/env python3
"""
run_simulation.py

One-command execution entry point for the holonic demanufacturing simulation.

Usage:
    python run_simulation.py

Timing Model:
    - Mock hardware runs in real wall-clock time
    - TwinEngine uses SimPy simulation time
    - Main loop advances SimPy in small increments to keep pace with MQTT events

Architecture:
    Mock Hardware (simulated physical holons)
            │
            │  MQTT messages: holon/{holon_id}/delta
            ▼
    MQTT Broker (Mosquitto, local subprocess)
            │
            ▼
    Digital Twin Core
      ├─ TwinEngine (SimPy-based state evolution)
      ├─ MQTTObserver (state ingestion)
      ├─ MediatorAPI (what-if queries)
      └─ Visualization (read-only)

ARCHITECTURAL CONSTRAINTS:
    - Mock hardware publishes only
    - Digital twin subscribes only  
    - No shared memory, no direct imports across layers
"""

import sys
import time
import signal
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mock_hardware.mqtt_broker import EmbeddedBroker
from mock_hardware.mock_factory import MockFactory
from mock_hardware.mock_robot import MockRobot
from mock_hardware.mock_operator import MockOperator
from core.twin_engine import TwinEngine
from io_layer.mqtt_observer import MQTTObserver
from io_layer.mediator_api import MediatorAPI
from viz.schematic_view import SchematicView


class SimulationRunner:
    """
    Orchestrates the complete simulation environment.
    
    Manages lifecycle of:
    - MQTT broker subprocess
    - Mock hardware components (factory, robots, operators)
    - Digital twin core
    - Visualization
    """
    
    def __init__(
        self,
        mqtt_port: int = 1883,
        api_port: int = 5000,
        spawn_interval: float = 8.0,
        enable_viz: bool = True,
        max_devices: int = 1,
    ):
        self.mqtt_port = mqtt_port
        self.api_port = api_port
        self.spawn_interval = spawn_interval
        self.enable_viz = enable_viz
        
        # Components (initialized in start())
        self.broker = None
        self.twin = None
        self.mqtt_obs = None
        self.api = None
        self.viz = None
        self.factory = None
        self.robots = []
        self.operator = None
        
        self._running = False
        self.max_devices = max(1, int(max_devices))
    
    def start(self):
        """Start all simulation components."""
        print("\n" + "="*60)
        print("  HOLONIC DEMANUFACTURING SIMULATION")
        print("="*60 + "\n")
        
        # 1. Start MQTT broker
        print("[1/7] Starting MQTT broker...")
        self.broker = EmbeddedBroker(port=self.mqtt_port)
        if not self.broker.start():
            print("\n❌ Aborting: MQTT broker required.")
            print("   Install Mosquitto: https://mosquitto.org/download/")
            return False
        
        # Broker may have selected an available port; update runner's mqtt_port
        try:
            self.mqtt_port = int(self.broker.port)
        except Exception:
            pass

        # Small delay for broker to be ready
        time.sleep(0.2)
        
        # 2. Initialize digital twin
        print("[2/7] Initializing digital twin engine...")
        self.twin = TwinEngine()
        
        # 3. Start MQTT observer
        print("[3/7] Starting MQTT observer...")
        self.mqtt_obs = MQTTObserver(self.twin, broker_port=self.mqtt_port)
        if not self.mqtt_obs.start():
            print("\n❌ Aborting: MQTT observer could not connect to broker.")
            self.broker.stop()
            return False
        
        # 4. Start mediator API
        print("[4/7] Starting mediator API...")
        self.api = MediatorAPI(self.twin)
        self.api.start(port=self.api_port)
        
        # 5. Start visualization (optional)
        if self.enable_viz:
            print("[5/7] Starting visualization...")
            self.viz = SchematicView(self.twin)
            self.viz.start()
        else:
            print("[5/7] Visualization disabled")
        
        # 6. Start mock factory
        print("[6/7] Starting mock factory...")
        self.factory = MockFactory(broker_port=self.mqtt_port, max_devices=self.max_devices)
        self.factory.start(spawn_interval_sec=self.spawn_interval)
        
        # 7. Start mock robots and operators
        print("[7/7] Starting mock resources...")
        
        # Create robots with different profiles
        self.robots = [
            MockRobot("arm_01", broker_port=self.mqtt_port, profile="standard"),
            MockRobot("arm_02", broker_port=self.mqtt_port, profile="precision"),
        ]
        for robot in self.robots:
            robot.start()
        
        # Create operator
        self.operator = MockOperator("op_01", broker_port=self.mqtt_port, profile="experienced")
        self.operator.start()
        
        self._running = True
        
        print("\n" + "="*60)
        print("  🚀 SIMULATION RUNNING")
        print("="*60)
        print(f"\n  📊 Mediator API: http://localhost:{self.api_port}")
        print(f"  📡 MQTT Broker: localhost:{self.mqtt_port}")
        print("\n  Press Ctrl+C to stop\n")
        
        return True
    
    def run_loop(self):
        """Main simulation loop."""
        try:
            while self._running:
                # Get speed multiplier from visualization if enabled
                speed = 1.0
                if self.viz:
                    speed = self.viz.speed_multiplier
                
                # Advance SimPy time in small increments
                # Scale SimPy advancement with speed so simulated time progresses faster
                sim_advance = 1.0 * speed
                self.twin.env.run(until=self.twin.env.now + sim_advance)

                # Propagate time scaling to mock hardware so their sleeps are scaled
                if self.factory:
                    try:
                        self.factory.time_scale = speed
                    except Exception:
                        pass
                for robot in self.robots:
                    try:
                        robot.time_scale = speed
                    except Exception:
                        pass
                if self.operator:
                    try:
                        self.operator.time_scale = speed
                    except Exception:
                        pass
                
                # Adjust sleep time based on speed multiplier
                # Higher speed = shorter sleep = faster simulation
                sleep_time = 0.1 / speed
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Shutdown requested...")
    
    def stop(self):
        """Stop all simulation components."""
        self._running = False
        
        print("\n[Stopping components...]")
        
        if self.factory:
            self.factory.stop()
        
        for robot in self.robots:
            robot.stop()
        
        if self.operator:
            self.operator.stop()
        
        if self.viz:
            self.viz.stop()
        
        if self.api:
            self.api.stop()
        
        if self.mqtt_obs:
            self.mqtt_obs.stop()
        
        if self.broker:
            self.broker.stop()
        
        # Print final statistics
        if self.twin:
            print("\n" + "="*60)
            print("  FINAL STATISTICS")
            print("="*60)
            stats = self.twin.get_statistics()
            print(f"\n  Runtime: {stats['runtime_seconds']:.1f}s")
            print(f"  Total deltas processed: {stats['delta_count']}")
            print(f"  Deltas/second: {stats['deltas_per_second']:.2f}")
            print(f"\n  Products created: {stats['product_count']}")
            print(f"  Robots: {stats['robot_count']}")
            print(f"  Operators: {stats['operator_count']}")
            
            if stats.get('product_states'):
                print("\n  Product state breakdown:")
                for state, count in stats['product_states'].items():
                    print(f"    {state}: {count}")
        
        print("\n✅ Simulation stopped cleanly.\n")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Holonic Demanufacturing Simulation Runner"
    )
    parser.add_argument(
        "--mqtt-port", type=int, default=1883,
        help="MQTT broker port (default: 1883)"
    )
    parser.add_argument(
        "--api-port", type=int, default=5000,
        help="Mediator API port (default: 5000)"
    )
    parser.add_argument(
        "--spawn-interval", type=float, default=8.0,
        help="Product spawn interval in seconds (default: 8.0)"
    )
    parser.add_argument(
        "--max-devices", type=int, default=10,
        help="Maximum concurrent devices allowed in the simulation (default: 10)"
    )
    parser.add_argument(
        "--no-viz", action="store_true",
        help="Disable Pygame visualization"
    )
    
    args = parser.parse_args()
    
    runner = SimulationRunner(
        mqtt_port=args.mqtt_port,
        api_port=args.api_port,
        spawn_interval=args.spawn_interval,
        enable_viz=not args.no_viz
    )
    
    # Handle signals for graceful shutdown
    def signal_handler(sig, frame):
        runner.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if runner.start():
        runner.run_loop()
        runner.stop()
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
