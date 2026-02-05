"""
mock_hardware/mock_factory.py

Simulates a factory that periodically spawns heterogeneous electronic devices.

ARCHITECTURAL CONSTRAINT:
- This module MUST NOT import from core/, io/, or viz/
- Communication is strictly via MQTT publishing to holon/{holon_id}/delta
- Never coordinates directly with robots or operators

Message Contract:
    Topic: holon/{holon_id}/delta
    Payload: {
        "holon_id": "string",
        "device_type": "string",
        "patches": { "<dotted_path>": <json_value> }
    }
"""

import paho.mqtt.client as mqtt
import json
import time
import random
from threading import Thread, Lock
from typing import Optional


class MockFactory:
    """
    Simulates inbound product arrivals with uncertainty metadata.
    
    Spawns heterogeneous electronic devices (laptops, smartphones) with
    explicit uncertainty values that affect downstream disassembly success.
    """

    # Device profiles define inherent complexity and risk characteristics
    DEVICE_PROFILES = {
        "laptop_dell_xps": {
            "fastener_variety": 0.7,
            "battery_risk": 0.2,
            "avg_disassembly_steps": 8,
        },
        "laptop_lenovo_thinkpad": {
            "fastener_variety": 0.4,
            "battery_risk": 0.1,
            "avg_disassembly_steps": 6,
        },
        "smartphone_iphone": {
            "fastener_variety": 0.9,
            "battery_risk": 0.6,
            "avg_disassembly_steps": 12,
        },
        "smartphone_samsung": {
            "fastener_variety": 0.8,
            "battery_risk": 0.5,
            "avg_disassembly_steps": 10,
        },
        "tablet_ipad": {
            "fastener_variety": 0.85,
            "battery_risk": 0.55,
            "avg_disassembly_steps": 9,
        },
        "laptop_hp_elitebook": {
            "fastener_variety": 0.5,
            "battery_risk": 0.15,
            "avg_disassembly_steps": 7,
        },
    }

    def __init__(self, broker_host: str = "localhost", broker_port: int = 1883, time_scale: float = 1.0, max_devices: int = 10):
        """
        Initialize the mock factory.
        
        Args:
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client(client_id="mock_factory")
        self.client.connect(broker_host, broker_port)
        self.running = False
        self._thread: Optional[Thread] = None
        self._spawn_counter = 1
        # Time scaling for accelerated playback
        self.time_scale = max(0.0001, float(time_scale))
        # Limit concurrent active devices
        self.max_devices = max(1, int(max_devices))
        self._active_products: Dict[str, str] = {}
        self._lock = Lock()

    def start(self, spawn_interval_sec: float = 10.0):
        """
        Start spawning devices at regular intervals.
        
        Args:
            spawn_interval_sec: Base interval between spawns (with ±20% jitter)
        """
        self.running = True
        # Start MQTT loop so we can observe holon state and count active devices
        try:
            self.client.subscribe("holon/+/delta")
            self.client.on_message = self._on_message
            self.client.loop_start()
        except Exception:
            pass

        self._thread = Thread(
            target=self._spawn_loop,
            args=(spawn_interval_sec,),
            daemon=True,
            name="MockFactory-SpawnLoop"
        )
        self._thread.start()
        print(f"🏭 Factory started (interval: ~{spawn_interval_sec}s)")

    def stop(self):
        """Stop the factory spawn loop."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self.client.disconnect()
        print("🏭 Factory stopped")

    def spawn_device(self, device_type: Optional[str] = None) -> str:
        """
        Manually spawn a single device.
        
        Args:
            device_type: Specific device type, or None for random selection
            
        Returns:
            The holon_id of the spawned device
        """
        if device_type is None:
            device_type = random.choice(list(self.DEVICE_PROFILES.keys()))
        
        profile = self.DEVICE_PROFILES.get(device_type, self.DEVICE_PROFILES["laptop_dell_xps"])
        
        # Generate unique holon ID
        device_prefix = device_type.split("_")[1] if "_" in device_type else device_type
        holon_id = f"{device_prefix}_{self._spawn_counter:03d}"
        self._spawn_counter += 1

        # Calculate initial uncertainty based on device profile
        fastener_uncertainty = round(
            profile["fastener_variety"] * random.uniform(0.5, 1.0), 2
        )
        battery_uncertainty = round(
            profile["battery_risk"] * random.uniform(0.3, 1.0), 2
        )
        
        # Initial confidence inversely related to complexity
        base_confidence = 1.0 - (profile["fastener_variety"] * 0.3)
        initial_confidence = round(base_confidence * random.uniform(0.7, 1.0), 2)

        payload = {
            "holon_id": holon_id,
            "device_type": device_type,
            "patches": {
                "disassembly_step": 0,
                "total_steps": profile["avg_disassembly_steps"],
                "confidence": initial_confidence,
                "state": "ARRIVED",
                "uncertainty_map.fastener_type": fastener_uncertainty,
                "uncertainty_map.battery_condition": battery_uncertainty,
                "uncertainty_map.component_fragility": round(random.uniform(0.2, 0.6), 2),
            },
        }

        topic = f"holon/{holon_id}/delta"
        self.client.publish(topic, json.dumps(payload))
        print(f"🏭 Factory spawned {holon_id} ({device_type})")
        
        return holon_id

    def _spawn_loop(self, interval: float):
        """Internal loop that spawns devices at regular intervals."""
        while self.running:
            # Add jitter to avoid synchronized behavior
            actual_interval = interval * random.uniform(0.8, 1.2)
            # Scale sleep by time_scale so the factory can be accelerated
            time.sleep(max(0.0, actual_interval / self.time_scale))

            if not self.running:
                break

            # Check active product count and only spawn if under limit
            with self._lock:
                active_count = sum(1 for s in self._active_products.values() if s not in ("COMPLETED", "SCRAPPED"))

            if active_count < self.max_devices:
                self.spawn_device()
            else:
                # Skip spawning until space frees up
                continue

    def _on_message(self, client, userdata, msg):
        """Observe holon state changes to track active product count."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return

        holon_id = payload.get("holon_id")
        patches = payload.get("patches", {})
        if not holon_id or not patches:
            return

        state = patches.get("state")
        with self._lock:
            if state in ("ARRIVED", "IN_PROGRESS", "FAILED_ATTEMPT", "REQUIRES_SPECIALIST"):
                # mark or update
                self._active_products[holon_id] = state
            elif state in ("COMPLETED", "SCRAPPED"):
                # remove or mark completed
                self._active_products[holon_id] = state
