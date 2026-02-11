"""
sim/dists.py – Distribution samplers driven by config objects.

Every config node that describes a random variable has a ``dist`` key.
``sample(cfg_node, rng)`` dispatches to the correct distribution.

``bernoulli(cfg_node, rng)`` is a convenience for probability parameters
that have a ``value`` key (returning True with probability ``value``).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Main sampler
# ---------------------------------------------------------------------------

def sample(cfg_node: Any, rng: np.random.Generator | None = None) -> float:
    """Draw one sample from the distribution described in *cfg_node*.

    If the config node is just a plain number it is returned as-is
    (constant / deterministic).
    """
    if rng is None:
        rng = np.random.default_rng()

    # Plain scalar → deterministic
    if isinstance(cfg_node, (int, float)):
        return float(cfg_node)

    # Attribute-access wrapper (Cfg) – grab the dist field
    dist = getattr(cfg_node, "dist", None)
    if dist is None:
        # Might be a constant node with just "value"
        val = getattr(cfg_node, "value", None)
        if val is not None:
            return float(val)
        raise ValueError(f"Cannot sample from config node: {cfg_node}")

    if dist == "triangular":
        lo = float(cfg_node.min)
        mode = float(cfg_node.mode)
        hi = float(cfg_node.max)
        return float(rng.triangular(lo, mode, hi))

    if dist == "triangular_int":
        lo = float(cfg_node.min)
        mode = float(cfg_node.mode)
        hi = float(cfg_node.max)
        return int(round(rng.triangular(lo, mode, hi)))

    if dist == "exponential":
        rate = float(cfg_node.rate)
        return float(rng.exponential(1.0 / rate))

    if dist == "constant":
        return float(cfg_node.value)

    if dist == "bernoulli":
        p = float(cfg_node.p)
        return 1.0 if rng.random() < p else 0.0

    raise ValueError(f"Unknown distribution type: {dist}")


def sample_int(cfg_node: Any, rng: np.random.Generator | None = None) -> int:
    """Sample and round to the nearest integer (≥ 1)."""
    return max(1, int(round(sample(cfg_node, rng))))


# ---------------------------------------------------------------------------
# Bernoulli helper (for exception probabilities)
# ---------------------------------------------------------------------------

def bernoulli(cfg_node: Any, rng: np.random.Generator | None = None) -> bool:
    """Return True with probability ``cfg_node.value``."""
    if rng is None:
        rng = np.random.default_rng()
    p = float(getattr(cfg_node, "value", cfg_node))
    return bool(rng.random() < p)


# ---------------------------------------------------------------------------
# Output profile sampler
# ---------------------------------------------------------------------------

def sample_outputs(
    outputs_cfg: Any, device: Any, rng: np.random.Generator | None = None,
) -> dict[str, float]:
    """Generate per-fraction output quantities for one device."""
    if rng is None:
        rng = np.random.default_rng()

    profile = outputs_cfg.profile
    result: dict[str, float] = {}
    for frac in ("batteries", "logic_boards", "housings",
                 "modules_magnets", "mixed_fines"):
        node = getattr(profile, frac, None)
        if node is None:
            result[frac] = 0.0
        else:
            result[frac] = sample(node, rng)
    return result
