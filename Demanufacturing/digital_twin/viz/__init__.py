# viz/__init__.py
"""
Visualization module for the digital twin.

ARCHITECTURAL CONSTRAINT:
This module MUST NEVER import from mock_hardware/.
Visualization is read-only and diagnostic only.
"""

from .schematic_view import SchematicView

__all__ = ["SchematicView"]
