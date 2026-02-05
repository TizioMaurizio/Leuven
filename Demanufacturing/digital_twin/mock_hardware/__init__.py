# mock_hardware/__init__.py
"""
Mock Hardware Layer for Holonic Electronics Demanufacturing Simulation.

ARCHITECTURAL CONSTRAINT:
This module simulates physical hardware (robots, operators, products).
It MUST only communicate via MQTT publishing.
It MUST NEVER import from core/, io/, or viz/.
"""

from .mqtt_broker import EmbeddedBroker
from .mock_factory import MockFactory
from .mock_robot import MockRobot
from .mock_operator import MockOperator

__all__ = ["EmbeddedBroker", "MockFactory", "MockRobot", "MockOperator"]
