# holons/__init__.py
"""
Holon dataclasses for the digital twin.

Holons represent autonomous entities in the demanufacturing system:
- Product holons (devices being disassembled)
- Resource holons (robots, operators)
- Process holons (disassembly operations)
"""

from .product_holon import ProductHolon
from .resource_holon import ResourceHolon, RobotHolon, OperatorHolon
from .uncertainty import UncertaintyMap

__all__ = [
    "ProductHolon",
    "ResourceHolon", 
    "RobotHolon",
    "OperatorHolon",
    "UncertaintyMap",
]
