"""
mock_hardware/mock_operator.py

Simulates human operators with cognitive load dynamics.

ARCHITECTURAL CONSTRAINT:
- This module MUST NOT import from core/, io/, or viz/
- Publishes cognitive state to holon/{operator_id}/delta
- Models realistic cognitive load fluctuations

Behavioral Model:
- Cognitive load drifts over time with bounded random walk
- State transitions between AVAILABLE, BUSY, OVERLOADED
- Can optionally process products that robots cannot handle
"""

import paho.mqtt.client as mqtt
import json
import time
import random
from threading import Thread, Lock
from typing import Optional, Dict, Any
from enum import Enum


class OperatorState(Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OVERLOADED = "OVERLOADED"
    ON_BREAK = "ON_BREAK"


class MockOperator:
    """
    Simulates a human operator with cognitive load dynamics.
    
    Models realistic cognitive fatigue, recovery, and state transitions
    based on workload and time-on-task factors.
    """

    # Operator skill profiles
    OPERATOR_PROFILES = {
        "novice": {
            "base_load": 0.4,
            "load_sensitivity": 1.2,
            "recovery_rate": 0.03,
            "overload_threshold": 0.65,
        },
        "experienced": {
            "base_load": 0.25,
            "load_sensitivity": 0.8,
            "recovery_rate": 0.05,
            "overload_threshold": 0.75,
        },
        "expert": {
            "base_load": 0.2,
            "load_sensitivity": 0.6,
            "recovery_rate": 0.07,
            "overload_threshold": 0.85,
        },
    }

    def __init__(
        self,
        operator_id: str,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        profile: str = "experienced",
        time_scale: float = 1.0,
    ):
        """
        Initialize the mock operator.
        
        Args:
            operator_id: Unique identifier for this operator
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
            profile: Operator skill profile (novice, experienced, expert)
        """
        self.op_id = operator_id
        self.profile = self.OPERATOR_PROFILES.get(profile, self.OPERATOR_PROFILES["experienced"])
        
        self.client = mqtt.Client(client_id=f"mock_{operator_id}")
        self.client.connect(broker_host, broker_port)
        
        # Subscribe to observe failed robot operations (optional intervention)
        self.client.subscribe("holon/+/delta")
        self.client.on_message = self._on_message
        
        # Cognitive state
        self.cognitive_load = self.profile["base_load"]
        self.state = OperatorState.AVAILABLE
        self.time_on_task = 0.0
        self.tasks_completed = 0
        
        # Work queue for interventions
        self.intervention_queue: list = []
        self._lock = Lock()
        
        self.running = False
        self._thread: Optional[Thread] = None
        # Time scaling for accelerated playback
        self.time_scale = max(0.0001, float(time_scale))

    def start(self):
        """Start the operator simulation loop."""
        self.running = True
        self.client.loop_start()
        self._thread = Thread(
            target=self._loop,
            daemon=True,
            name=f"MockOperator-{self.op_id}"
        )
        self._thread.start()
        print(f"👷 Operator {self.op_id} on shift")

    def stop(self):
        """Stop the operator simulation."""
        self.running = False
        self.client.loop_stop()
        if self._thread:
            self._thread.join(timeout=2.0)
        self.client.disconnect()
        print(f"👷 Operator {self.op_id} off shift")

    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages (observe for intervention opportunities)."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError:
            return

        holon_id = payload.get("holon_id")
        patches = payload.get("patches", {})
        
        # Skip our own messages
        if holon_id == self.op_id:
            return

        # Check if this is a failed operation that needs human intervention
        if patches.get("state") == "FAILED_ATTEMPT":
            # Queue all failed attempts for potential intervention, with failure_count
            failure_count = int(patches.get("failure_count", 1))
            with self._lock:
                # Avoid duplicate entries
                exists = any(h == holon_id for (h, _) in self.intervention_queue)
                if not exists:
                    self.intervention_queue.append((holon_id, failure_count))
                    uncertainty = patches.get("uncertainty_map.fastener_type", 0)
                    print(f"👷 {self.op_id} queued intervention for {holon_id} (uncertainty: {uncertainty:.2f}, failures: {failure_count})")

    def _loop(self):
        """Main simulation loop for cognitive load dynamics."""
        update_interval = 1.0  # Check very frequently for immediate intervention
        
        while self.running:
            # Update cognitive dynamics
            self._update_cognitive_state()
            
            # Check for intervention work - process multiple if queue is building up
            self._check_intervention()
            
            # Publish current state
            self._publish_state()
            
            # Track time on task (scaled)
            self.time_on_task += update_interval
            
            time.sleep(max(0.0, update_interval / self.time_scale))

    def _update_cognitive_state(self):
        """Update cognitive load based on various factors."""
        with self._lock:
            # Base drift (random walk)
            drift = random.uniform(-0.05, 0.08) * self.profile["load_sensitivity"]
            
            # Time-on-task fatigue factor
            fatigue_factor = min(0.2, self.time_on_task / 3600.0 * 0.1)
            
            # Queue pressure
            queue_pressure = len(self.intervention_queue) * 0.05
            
            # Recovery when idle
            if self.state == OperatorState.AVAILABLE and not self.intervention_queue:
                recovery = -self.profile["recovery_rate"]
            else:
                recovery = 0

            # Update cognitive load
            self.cognitive_load = max(0.1, min(0.95,
                self.cognitive_load + drift + fatigue_factor + queue_pressure + recovery
            ))

            # Update state based on cognitive load
            if self.cognitive_load >= self.profile["overload_threshold"]:
                self.state = OperatorState.OVERLOADED
            elif self.cognitive_load >= self.profile["overload_threshold"] - 0.15:
                self.state = OperatorState.BUSY
            else:
                self.state = OperatorState.AVAILABLE

    def _check_intervention(self):
        """Process intervention queue if operator can work."""
        # Only block on OVERLOADED - BUSY operators can still process queue
        if self.state == OperatorState.OVERLOADED:
            return  # Cannot take new work when overloaded

        # Process ALL high-priority items (at/above retry_limit) immediately
        items_to_process = []
        with self._lock:
            if self.intervention_queue:
                # Sort by failure_count descending (highest priority first)
                sorted_queue = sorted(self.intervention_queue, key=lambda x: x[1], reverse=True)
                # Process up to 3 items per loop, prioritizing critical failures (failure_count >= 2)
                for holon_id, failure_count in sorted_queue[:3]:
                    items_to_process.append(holon_id)
                    self.intervention_queue.remove((holon_id, failure_count))

        for holon_id in items_to_process:
            self._perform_intervention(holon_id)
            # Brief pause between interventions
            time.sleep(max(0.0, 0.5 / self.time_scale))

    def _perform_intervention(self, holon_id: str):
        """Perform human intervention on a problematic product."""
        # Human intervention increases cognitive load
        with self._lock:
            self.cognitive_load = min(0.95, self.cognitive_load + 0.10)
            self.state = OperatorState.BUSY

        # Simulate work time (very fast to clear backlog quickly)
        work_time = random.uniform(1.0, 2.0)
        time.sleep(max(0.0, work_time / self.time_scale))

        # Humans have very high success rate - nearly always resolve failures
        success_prob = 0.98  # Very high success to ensure stuck items are resolved
        
        if random.random() < success_prob:
            # Successful intervention - clear operated_by so robots can claim it again
            payload = {
                "holon_id": holon_id,
                "patches": {
                    "state": "IN_PROGRESS",
                    "confidence": round(random.uniform(0.7, 0.9), 2),
                    "uncertainty_map.fastener_type": round(random.uniform(0.2, 0.4), 2),
                    "uncertainty_map.battery_condition": round(random.uniform(0.2, 0.4), 2),
                    "last_operation": "HUMAN_INTERVENTION",
                    "operated_by": None,  # Clear so robots can claim
                    "failure_count": 0,
                },
            }
            self.client.publish(f"holon/{holon_id}/delta", json.dumps(payload))
            print(f"👷 {self.op_id} successfully resolved {holon_id}")
            
            with self._lock:
                self.tasks_completed += 1
        else:
            # Still having trouble
            payload = {
                "holon_id": holon_id,
                "patches": {
                    "state": "REQUIRES_SPECIALIST",
                    "confidence": round(random.uniform(0.3, 0.5), 2),
                    "last_operation": "HUMAN_INTERVENTION_FAILED",
                    "operated_by": self.op_id,
                },
            }
            self.client.publish(f"holon/{holon_id}/delta", json.dumps(payload))
            print(f"👷 {self.op_id} escalated {holon_id} to specialist")

    def _publish_state(self):
        """Publish current operator state to MQTT."""
        payload = {
            "holon_id": self.op_id,
            "patches": {
                "cognitive_load": round(self.cognitive_load, 2),
                "state": self.state.value,
                "time_on_task_minutes": round(self.time_on_task / 60.0, 1),
                "tasks_completed": self.tasks_completed,
                "queue_depth": len(self.intervention_queue),
            },
        }

        self.client.publish(f"holon/{self.op_id}/delta", json.dumps(payload))
