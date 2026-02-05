"""
mock_hardware/mock_robot.py

Simulates robotic disassembly arms with uncertainty-driven success probability.

ARCHITECTURAL CONSTRAINT:
- This module MUST NOT import from core/, io/, or viz/
- Subscribes to holon/+/delta to observe product state
- Publishes results to holon/{holon_id}/delta
- Never reads digital twin state directly

Behavioral Model:
- Claims products with disassembly_step == 0
- Derives success probability from published uncertainty
- Publishes success (step increment) or failure (increased uncertainty)
"""

import paho.mqtt.client as mqtt
import json
import time
import random
from threading import Thread, Lock
from typing import Optional, Dict, Any
from copy import deepcopy


class MockRobot:
    """
    Simulates a robotic disassembly arm.
    
    The robot observes incoming products via MQTT, claims unassigned ones,
    and attempts disassembly with success probability inversely proportional
    to the product's uncertainty metrics.
    """

    # Robot capability profiles
    ROBOT_PROFILES = {
        "standard": {
            "base_skill": 0.7,
            "work_time_range": (3.0, 6.0),
            "fatigue_rate": 0.01,
        },
        "precision": {
            "base_skill": 0.85,
            "work_time_range": (4.0, 8.0),
            "fatigue_rate": 0.005,
        },
        "fast": {
            "base_skill": 0.6,
            "work_time_range": (2.0, 4.0),
            "fatigue_rate": 0.02,
        },
    }

    def __init__(
        self,
        robot_id: str,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        profile: str = "standard",
        time_scale: float = 1.0,
    ):
        """
        Initialize the mock robot.
        
        Args:
            robot_id: Unique identifier for this robot
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
            profile: Robot capability profile (standard, precision, fast)
        """
        self.robot_id = robot_id
        self.profile = self.ROBOT_PROFILES.get(profile, self.ROBOT_PROFILES["standard"])
        
        self.client = mqtt.Client(client_id=f"mock_{robot_id}")
        self.client.connect(broker_host, broker_port)
        self.client.subscribe("holon/+/delta")
        self.client.on_message = self._on_message

        self.assigned_product: Optional[str] = None
        self.latest_state: Dict[str, Dict[str, Any]] = {}
        self.running = False
        self._lock = Lock()
        self._thread: Optional[Thread] = None
        
        # Candidates for claiming (to be processed by work loop with backoff)
        self._claim_candidates: set = set()
        
        # Dynamic state
        self.fatigue = 0.0
        self.operations_count = 0
        # Time scaling for accelerated playback (1.0 == real time)
        self.time_scale = max(0.0001, float(time_scale))

    def start(self):
        """Start the robot's work loop."""
        self.running = True
        self.client.loop_start()
        self._thread = Thread(
            target=self._work_loop,
            daemon=True,
            name=f"MockRobot-{self.robot_id}"
        )
        self._thread.start()
        print(f"🤖 Robot {self.robot_id} online")

    def stop(self):
        """Stop the robot."""
        self.running = False
        self.client.loop_stop()
        if self._thread:
            self._thread.join(timeout=2.0)
        self.client.disconnect()
        print(f"🤖 Robot {self.robot_id} offline")

    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError:
            return

        holon_id = payload.get("holon_id")
        patches = payload.get("patches", {})
        
        if not holon_id:
            return

        # Ignore operator or other robot messages entirely (they are not products)
        if holon_id.startswith("op_") or holon_id.startswith("arm_"):
            return

        # Only consider messages that contain product-related keys.
        relevant_keys = ("disassembly_step", "state", "operated_by", "failure_count")
        if not any(k in patches for k in relevant_keys):
            return

        # Concise debug of incoming relevant product patches to trace lifecycle
        # key_snapshot = {k: v for k, v in patches.items() if k in relevant_keys}
        # if key_snapshot:
        #     print(f"🔔 {self.robot_id} received {key_snapshot} for {holon_id}")

        with self._lock:
            # Capture previous view for debug
            # prev = deepcopy(self.latest_state.get(holon_id, {}))
            # Update our local view of the holon state
            if holon_id not in self.latest_state:
                self.latest_state[holon_id] = {}
            self.latest_state[holon_id].update(patches)

            # Log any changes to key lifecycle fields (disabled for cleaner output)
            # for k in ("disassembly_step", "state", "operated_by", "failure_count"):
            #     old = prev.get(k)
            #     new = self.latest_state[holon_id].get(k)
            #     if old != new:
            #         print(f"ℹ️ {self.robot_id} {holon_id}: {k} {old} -> {new}")

            # Claim product if we're idle and it's available for work
            if self.assigned_product is None:
                # Use the stored/latest state (not only incoming patch) to decide
                step = self.latest_state[holon_id].get("disassembly_step")
                state = self.latest_state[holon_id].get("state")
                total_steps = self.latest_state[holon_id].get("total_steps", 999)
                operated_by = self.latest_state[holon_id].get("operated_by")
                failure_count = int(self.latest_state[holon_id].get("failure_count", 0))
                
                # Only claim if:
                # 1. State is workable (ARRIVED, IN_PROGRESS, or FAILED_ATTEMPT for retry)
                # 2. Not already being worked by another robot (unless failed)
                # 3. Not yet completed
                is_unassigned = operated_by is None or operated_by == self.robot_id
                is_new_arrival = state == "ARRIVED"
                is_failed_and_free = state == "FAILED_ATTEMPT" and operated_by is None
                
                # Don't let robots repeatedly retry a product that has failed many times;
                # after `retry_limit` failures, defer to operator.
                retry_limit = 2
                claimable = (
                    state in ["ARRIVED", "IN_PROGRESS", "FAILED_ATTEMPT"] and
                    step is not None and 
                    step < total_steps and
                    (is_unassigned or is_new_arrival or is_failed_and_free) and
                    failure_count < retry_limit
                )
                
                if claimable:
                    # Add to claim candidates; work loop will handle with backoff
                    self._claim_candidates.add(holon_id)
                else:
                    # Helpful debug when robots skip claiming
                    if failure_count >= retry_limit:
                        print(f"🤖 {self.robot_id} skipping {holon_id}: reached retry_limit (failures={failure_count})")
                    elif operated_by is not None:
                        print(f"🤖 {self.robot_id} skipping {holon_id}: operated_by={operated_by}")
                    elif step is None:
                        print(f"🤖 {self.robot_id} skipping {holon_id}: no step info")

    def _work_loop(self):
        """Main work loop for the robot."""
        while self.running:
            product_to_work = None
            
            with self._lock:
                if self.assigned_product:
                    product_to_work = self.assigned_product

            # If idle, attempt to claim a candidate with randomized backoff
            if product_to_work is None:
                candidate = None
                with self._lock:
                    if self._claim_candidates:
                        candidate = next(iter(self._claim_candidates))
                        self._claim_candidates.discard(candidate)
                if candidate:
                    self._attempt_claim(candidate)

            # Re-check assigned_product after potential claim
            with self._lock:
                if self.assigned_product:
                    product_to_work = self.assigned_product

            if product_to_work:
                should_continue = self._perform_disassembly(product_to_work)
                
                # Only unassign if work is complete or requires intervention
                if not should_continue:
                    with self._lock:
                        self.assigned_product = None
                    
            # Idle sleep scaled by time_scale
            time.sleep(max(0.0, 1.0 / self.time_scale))

    def _attempt_claim(self, holon_id: str):
        """
        Attempt to claim a product with randomized backoff to avoid race conditions.
        """
        # Random backoff to stagger claims (50-200ms scaled by time_scale)
        backoff = random.uniform(0.05, 0.2) / self.time_scale
        time.sleep(backoff)

        with self._lock:
            # Re-check conditions after backoff
            if self.assigned_product is not None:
                return  # Already working on something else
            info = self.latest_state.get(holon_id, {})
            operated_by = info.get("operated_by")
            state = info.get("state")
            step = info.get("disassembly_step")
            total_steps = info.get("total_steps", 999)
            failure_count = int(info.get("failure_count", 0))

            # Conditions to proceed with claim
            still_free = operated_by is None
            still_workable = state in ["ARRIVED", "IN_PROGRESS", "FAILED_ATTEMPT"]
            not_complete = step is not None and step < total_steps
            under_retry_limit = failure_count < 2

            if still_free and still_workable and not_complete and under_retry_limit:
                # Publish claim
                claim_payload = {
                    "holon_id": holon_id,
                    "patches": {
                        "operated_by": self.robot_id,
                        "state": "IN_PROGRESS",
                    },
                }
                try:
                    self.client.publish(f"holon/{holon_id}/delta", json.dumps(claim_payload))
                except Exception:
                    pass
                self.assigned_product = holon_id
                print(f"🤖 {self.robot_id} assigned to {holon_id}")

    def _perform_disassembly(self, holon_id: str) -> bool:
        """
        Attempt a disassembly operation on the assigned product.
        
        Success probability is derived from:
        - Robot's base skill level
        - Product's uncertainty metrics
        - Accumulated fatigue
        
        Returns:
            True if robot should continue working on this product, False otherwise
        """
        with self._lock:
            patches = self.latest_state.get(holon_id, {})
            # Verify we still own this product; another robot may have claimed it
            operated_by = patches.get("operated_by")
            if operated_by is not None and operated_by != self.robot_id:
                # Lost ownership; abort
                return False
            state = patches.get("state")
            if state == "COMPLETED":
                # Already done
                return False
        
        # Extract uncertainty metrics
        fastener_u = patches.get("uncertainty_map.fastener_type", 0.5)
        battery_u = patches.get("uncertainty_map.battery_condition", 0.5)
        fragility_u = patches.get("uncertainty_map.component_fragility", 0.3)
        current_step = patches.get("disassembly_step", 0)
        total_steps = patches.get("total_steps", 8)
        
        # Calculate combined uncertainty
        uncertainty = max(fastener_u, battery_u) * 0.6 + fragility_u * 0.4
        
        # Calculate success probability
        base_skill = self.profile["base_skill"]
        fatigue_penalty = self.fatigue * 0.2
        success_prob = max(0.2, min(0.95, base_skill - uncertainty * 0.5 - fatigue_penalty))

        # Simulate work time (scaled)
        work_time = random.uniform(*self.profile["work_time_range"])
        time.sleep(max(0.0, work_time / self.time_scale))

        # Attempt operation
        if random.random() < success_prob:
            completed = self._publish_success(holon_id, current_step, total_steps, fastener_u, battery_u)
            # Update fatigue
            self.fatigue = min(0.5, self.fatigue + self.profile["fatigue_rate"])
            self.operations_count += 1
            return not completed  # Continue if not completed
        else:
            self._publish_failure(holon_id, fastener_u, battery_u)
            # Update fatigue
            self.fatigue = min(0.5, self.fatigue + self.profile["fatigue_rate"])
            self.operations_count += 1
            return False  # Stop on failure - needs intervention

    def _publish_success(
        self, 
        holon_id: str, 
        current_step: int, 
        total_steps: int,
        fastener_u: float,
        battery_u: float
    ) -> bool:
        """Publish a successful disassembly step.
        
        Returns:
            True if product is completed, False otherwise
        """
        new_step = current_step + 1
        
        # Reduce uncertainty after successful operation
        new_fastener_u = round(max(0.1, fastener_u - random.uniform(0.05, 0.15)), 2)
        new_battery_u = round(max(0.1, battery_u - random.uniform(0.03, 0.1)), 2)
        
        # Determine state
        if new_step >= total_steps:
            state = "COMPLETED"
        else:
            state = "IN_PROGRESS"

        payload = {
            "holon_id": holon_id,
            "patches": {
                "disassembly_step": new_step,
                "state": state,
                "confidence": round(min(1.0, 0.7 + random.uniform(0.0, 0.2)), 2),
                "uncertainty_map.fastener_type": new_fastener_u,
                "uncertainty_map.battery_condition": new_battery_u,
                "last_operation": "SUCCESS",
                "failure_count": 0,
                "operated_by": self.robot_id,
            },
        }

        self.client.publish(f"holon/{holon_id}/delta", json.dumps(payload))
        
        if state == "COMPLETED":
            print(f"✅ {self.robot_id} COMPLETED {holon_id}")
            return True
        else:
            print(f"✅ {self.robot_id} step {new_step}/{total_steps} on {holon_id}")
            return False

    def _publish_failure(self, holon_id: str, fastener_u: float, battery_u: float):
        """Publish a failed disassembly attempt."""
        # Increase uncertainty after failure
        new_fastener_u = round(min(1.0, fastener_u + random.uniform(0.1, 0.25)), 2)
        new_battery_u = round(min(1.0, battery_u + random.uniform(0.05, 0.15)), 2)

        # Increment failure_count for this holon so operator can prioritize
        prev_failures = int(self.latest_state.get(holon_id, {}).get("failure_count", 0))
        new_failure_count = prev_failures + 1

        payload = {
            "holon_id": holon_id,
            "patches": {
                "confidence": round(max(0.1, 0.4 - random.uniform(0.1, 0.2)), 2),
                "uncertainty_map.fastener_type": new_fastener_u,
                "uncertainty_map.battery_condition": new_battery_u,
                "state": "FAILED_ATTEMPT",
                "last_operation": "FAILURE",
                "operated_by": None,  # Clear so others can claim/help
                "failure_count": new_failure_count,
            },
        }

        self.client.publish(f"holon/{holon_id}/delta", json.dumps(payload))
        print(f"⚠️ {self.robot_id} failed on {holon_id} (uncertainty: {new_fastener_u:.2f}) retries={new_failure_count}")
