# io/__init__.py
"""
I/O Layer for Digital Twin.

ARCHITECTURAL CONSTRAINT:
This module MUST NEVER import from mock_hardware/.
MQTTObserver subscribes to MQTT topics but never publishes commands.
Communication is strictly unidirectional: mock hardware → MQTT → digital twin
"""

from .mqtt_observer import MQTTObserver
from .mediator_api import MediatorAPI

__all__ = ["MQTTObserver", "MediatorAPI"]
