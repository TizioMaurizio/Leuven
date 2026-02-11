"""
experiments/scenarios.py – Pre-defined scenario overrides for the Daisy DES.

Each scenario is a plain dict that gets deep-merged over defaults.yaml.
All values are ASSUMPTIONS for what-if analysis.
"""

from __future__ import annotations

from typing import Any

SCENARIOS: dict[str, dict[str, Any]] = {
    # ── 1. Base case (no changes) ───────────────────────────────────────
    "base": {},

    # ── 2. Increased arrivals (lower bin interarrival) ──────────────────
    "high_arrivals": {
        "arrival": {
            "bin_interarrival": {"dist": "triangular", "min": 30, "mode": 90, "max": 300},
        },
    },

    # ── 3. Reduced cooling capacity ────────────────────────────────────
    "low_cooling_cap": {
        "resources": {
            "m2_cooling_slot": {"capacity": 1},
        },
        "S3": {
            "cool_remove_time": {"dist": "triangular", "min": 40, "mode": 120, "max": 360},
        },
    },

    # ── 4. Reduced sorting labour ──────────────────────────────────────
    "low_sort_labor": {
        "resources": {
            "op_sort": {"capacity": 1},
        },
        "S5": {
            "m4_time": {"dist": "triangular", "min": 30, "mode": 90, "max": 300},
        },
    },

    # ── 5. Higher battery-issue rate ───────────────────────────────────
    "high_battery_issue": {
        "S3": {
            "p_battery_issue": {"value": 0.15, "range": [0.0, 0.3]},
        },
    },

    # ── 6. Higher jam rate + compare retry policies ────────────────────
    "high_jam_retry_s4": {
        "S4": {
            "p_jam": {"value": 0.10, "range": [0.0, 0.2]},
        },
        "E3": {
            "retry_policy": "retry_S4",
        },
    },
    "high_jam_after_clear": {
        "S4": {
            "p_jam": {"value": 0.10, "range": [0.0, 0.2]},
        },
        "E3": {
            "retry_policy": "retry_after_clear",
        },
    },

    # ── 7. Higher unknown-model rate ───────────────────────────────────
    "high_unknown_model": {
        "S1": {
            "p_unknown_model": {"value": 0.15, "range": [0.0, 0.2]},
        },
    },

    # ── 8. Buffer stress test (small Q2/Q3/Q4) ────────────────────────
    "small_buffers": {
        "buffers": {
            "Q2": {"capacity": 10},
            "Q3": {"capacity": 10},
            "Q4": {"capacity": 10},
        },
    },

    # ── 9. Exception preemption off (high-priority disabled) ───────────
    # (This scenario is identical config; the difference is handled in
    #  station code by toggling priority values.  Included here as a
    #  scenario stub for documentation / batch runner.)
    "no_preemption": {},
}


def get_scenario(name: str) -> dict[str, Any]:
    """Return the override dict for a named scenario (KeyError if unknown)."""
    return SCENARIOS[name]


def list_scenarios() -> list[str]:
    return list(SCENARIOS.keys())
