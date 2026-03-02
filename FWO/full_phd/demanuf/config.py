"""Global configuration constants and defaults."""

from dataclasses import dataclass, field
from typing import Dict, Any

# ---------------------------------------------------------------------------
# Default simulation parameters
# ---------------------------------------------------------------------------

DEFAULT_SEED = 42
DEFAULT_STEPS = 200

# Station names (order matters for layout)
STATION_NAMES = [
    "intake",
    "inspection",
    "robot_disassembly",
    "manual_disassembly",
    "hazard_handling",
    "output",
]

# Processing-time distributions (mean, std) per station in time-units
PROCESSING_TIMES: Dict[str, tuple] = {
    "intake": (2.0, 0.5),
    "inspection": (5.0, 1.0),
    "robot_disassembly": (10.0, 2.0),
    "manual_disassembly": (15.0, 3.0),
    "hazard_handling": (8.0, 1.5),
    "output": (1.0, 0.2),
}

# ---------------------------------------------------------------------------
# Uncertainty-regime defaults (HoDeSU-Bench knobs)
# ---------------------------------------------------------------------------

@dataclass
class UncertaintyRegime:
    """Parameterised uncertainty regime (HoDeSU-Bench §V-D)."""

    # Probability that a fastener is stripped (disables 'unscrew')
    stripped_screw_prob: float = 0.10
    # Probability that adhesive is stuck (disables non-destructive removal)
    stuck_adhesive_prob: float = 0.08
    # Probability of missing component / variant mismatch
    missing_component_prob: float = 0.05
    # Probability of battery swelling (enables hazard gating)
    battery_risk_prob: float = 0.12
    # Observation noise: probability of a false-negative on battery-risk sensor
    sensor_false_negative: float = 0.05
    # Resource unreliability: probability of station failure per task
    station_failure_prob: float = 0.03
    # Product arrival interval (mean time between arrivals)
    arrival_interval: float = 12.0

    def as_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)


# Convenience presets
REGIME_LOW = UncertaintyRegime(
    stripped_screw_prob=0.03,
    stuck_adhesive_prob=0.02,
    missing_component_prob=0.01,
    battery_risk_prob=0.05,
    sensor_false_negative=0.02,
    station_failure_prob=0.01,
)

REGIME_MEDIUM = UncertaintyRegime()  # defaults

REGIME_HIGH = UncertaintyRegime(
    stripped_screw_prob=0.25,
    stuck_adhesive_prob=0.20,
    missing_component_prob=0.15,
    battery_risk_prob=0.30,
    sensor_false_negative=0.15,
    station_failure_prob=0.10,
)
