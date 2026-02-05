"""
io_layer/mqtt_observer.py

MQTT subscription layer for the digital twin.

ARCHITECTURAL CONSTRAINT:
This module MUST NEVER import from mock_hardware/.
It ONLY subscribes to topics - never publishes commands back to hardware.
Communication is strictly unidirectional: mock hardware 1210 MQTT 1210 digital twin
"""

import paho.mqtt.client as mqtt
import json
from typing import Optional, Callable, List
import threading

from core.twin_engine import TwinEngine


class MQTTObserver:
    """
    Observes MQTT messages and feeds them to the digital twin.
    
    ARCHITECTURAL CONSTRAINT:
    - Subscribes to holon/+/delta topics
    - Never publishes commands back to mock hardware
    - This is the ONLY ingestion point for external state updates
    """
    
    def __init__(
        self,
        twin: TwinEngine,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        client_id: str = "digital_twin_observer"
    ):
        """
        Initialize the MQTT observer.
        
        Args:
            twin: TwinEngine to forward deltas to
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
            client_id: MQTT client identifier
        """
        self.twin = twin
        self.broker_host = broker_host
        self.broker_port = broker_port
        
        self.client = mqtt.Client(client_id=client_id)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        self._connected = False
        self._message_count = 0
        self._error_count = 0
        self._lock = threading.Lock()
        
        # Optional message interceptors for debugging
        self._interceptors: List[Callable[[str, dict], None]] = []
    
    def start(self):
        """Start the MQTT observer."""
        # Try connecting with retry/backoff to handle broker startup latency
        max_attempts = 15
        for attempt in range(1, max_attempts + 1):
            try:
                self.client.connect(self.broker_host, self.broker_port)
                self.client.loop_start()
                print(f"✓ MQTT observer connecting to {self.broker_host}:{self.broker_port}")
                return True
            except Exception as e:
                # ConnectionRefusedError is common if broker isn't ready yet
                print(f"⚠️ MQTT observer connect attempt {attempt}/{max_attempts} failed: {e}")
                time_to_wait = 0.2 * attempt
                try:
                    import time as _t
                    _t.sleep(time_to_wait)
                except Exception:
                    pass
                continue

        print(f"❌ MQTT observer failed to connect after {max_attempts} attempts")
        return False
    
    def stop(self):
        """Stop the MQTT observer."""
        self.client.loop_stop()
        self.client.disconnect()
        print("✓ MQTT observer stopped")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        if rc == 0:
            self._connected = True
            # Subscribe to all holon delta topics
            client.subscribe("holon/+/delta", qos=1)
            print("✓ MQTT observer subscribed to holon/+/delta")
        else:
            print(f"❌ MQTT connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection."""
        self._connected = False
        if rc != 0:
            print(f"⚠️ MQTT observer disconnected unexpectedly (rc={rc})")
    
    def _on_message(self, client, userdata, msg):
        """
        Handle incoming MQTT messages.
        
        Parses the message and forwards to TwinEngine.
        """
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError as e:
            with self._lock:
                self._error_count += 1
            print(f"⚠️ Invalid JSON on {msg.topic}: {e}")
            return
        except UnicodeDecodeError as e:
            with self._lock:
                self._error_count += 1
            print(f"⚠️ Invalid encoding on {msg.topic}: {e}")
            return
        
        # Validate message structure
        if "holon_id" not in payload:
            with self._lock:
                self._error_count += 1
            return
        
        with self._lock:
            self._message_count += 1
        
        # Call interceptors for debugging/logging
        for interceptor in self._interceptors:
            try:
                interceptor(msg.topic, payload)
            except Exception:
                pass
        
        # Forward to twin engine
        try:
            self.twin.apply_delta(payload)
        except Exception as e:
            with self._lock:
                self._error_count += 1
            print(f"⚠️ Error applying delta: {e}")
    
    def add_interceptor(self, callback: Callable[[str, dict], None]):
        """
        Add a message interceptor for debugging.
        
        Args:
            callback: Function called with (topic, payload) for each message
        """
        self._interceptors.append(callback)
    
    def remove_interceptor(self, callback: Callable[[str, dict], None]):
        """Remove a message interceptor."""
        if callback in self._interceptors:
            self._interceptors.remove(callback)
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self._connected
    
    def get_statistics(self) -> dict:
        """Get observer statistics."""
        with self._lock:
            return {
                "connected": self._connected,
                "broker": f"{self.broker_host}:{self.broker_port}",
                "messages_received": self._message_count,
                "errors": self._error_count,
                "error_rate": round(
                    self._error_count / max(1, self._message_count) * 100, 2
                ),
            }
