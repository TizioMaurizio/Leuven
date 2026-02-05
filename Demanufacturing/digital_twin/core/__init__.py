# core/__init__.py
"""
Core Digital Twin Engine.

ARCHITECTURAL CONSTRAINT:
This module MUST NEVER import from mock_hardware/.
All state updates come via MQTT subscription only.
"""

from .twin_engine import TwinEngine
from .state_store import StateStore

__all__ = ["TwinEngine", "StateStore"]
