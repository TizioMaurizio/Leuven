"""Scenario generator — structural uncertainty regimes.

Generates product streams and exception events according to
the HoDeSU-Bench knobs (PAPER_1 §V-D).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..config import UncertaintyRegime, REGIME_LOW, REGIME_MEDIUM, REGIME_HIGH
from .model import CellState, LatentCondition, Product


# ── Scenario ──────────────────────────────────────────────────────────
@dataclass
class Scenario:
    """Encapsulates a scenario: regime + seed → reproducible product stream."""

    regime: UncertaintyRegime
    seed: int

    def make_rng(self) -> random.Random:
        return random.Random(self.seed)


def generate_product_stream(
    scenario: Scenario,
    state: CellState,
    count: int,
) -> List[Product]:
    """Pre-generate *count* products using the scenario regime & seed."""
    rng = scenario.make_rng()
    products = []
    time = 0.0
    for _ in range(count):
        p = state.create_product(rng, scenario.regime, arrival_time=time)
        products.append(p)
        time += max(0.5, rng.gauss(scenario.regime.arrival_interval, 2.0))
    return products


# ── Named regime presets ──────────────────────────────────────────────
NAMED_REGIMES: Dict[str, UncertaintyRegime] = {
    "low": REGIME_LOW,
    "medium": REGIME_MEDIUM,
    "high": REGIME_HIGH,
}


def get_regime(name: str) -> UncertaintyRegime:
    """Return a named regime or raise KeyError."""
    return NAMED_REGIMES[name]
