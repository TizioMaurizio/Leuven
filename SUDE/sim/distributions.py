"""
sim/distributions.py – Sampling utilities for the DES.

Every distribution is a callable ``(rng: random.Random) -> float``.
The :func:`make_dist` factory builds one from a JSON config dict.
"""

from __future__ import annotations

import math
import random
from typing import Callable

DistFn = Callable[[random.Random], float]


# ── factories ────────────────────────────────────────────────────────────

def constant(value: float) -> DistFn:
    """Always returns *value*."""
    def _sample(_rng: random.Random) -> float:
        return value
    return _sample


def normal(mu: float, sigma: float) -> DistFn:
    """Clamped-at-zero normal."""
    def _sample(rng: random.Random) -> float:
        return max(0.0, rng.gauss(mu, sigma))
    return _sample


def lognormal(mu: float, sigma: float) -> DistFn:
    """Log-normal (mu/sigma of underlying normal)."""
    def _sample(rng: random.Random) -> float:
        return math.exp(rng.gauss(mu, sigma))
    return _sample


def triangular(low: float, mode: float, high: float) -> DistFn:
    def _sample(rng: random.Random) -> float:
        return rng.triangular(low, high, mode)
    return _sample


def exponential(lambd: float) -> DistFn:
    """Exponential with rate *lambd* (mean = 1/lambd)."""
    def _sample(rng: random.Random) -> float:
        return rng.expovariate(lambd)
    return _sample


def uniform(low: float, high: float) -> DistFn:
    def _sample(rng: random.Random) -> float:
        return rng.uniform(low, high)
    return _sample


# ── config-driven builder ───────────────────────────────────────────────

_BUILDERS = {
    "constant":   lambda d: constant(d["value"]),
    "normal":     lambda d: normal(d["mu"], d["sigma"]),
    "lognormal":  lambda d: lognormal(d["mu"], d["sigma"]),
    "triangular": lambda d: triangular(d["low"], d["mode"], d["high"]),
    "exponential": lambda d: exponential(d["lambda"]),
    "uniform":    lambda d: uniform(d["low"], d["high"]),
}


def make_dist(cfg: dict) -> DistFn:
    """Build a sampler from a configuration dict like
    ``{"type": "triangular", "low": 20, "mode": 30, "high": 45}``."""
    kind = cfg["type"]
    builder = _BUILDERS.get(kind)
    if builder is None:
        raise ValueError(f"Unknown distribution type: {kind!r}")
    return builder(cfg)
