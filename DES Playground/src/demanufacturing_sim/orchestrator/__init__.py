"""
Cognitive Orchestration Layer for DIGITAU Demanufacturing Simulator.

This module implements an LLM-like meta-layer that:
- Reads aggregated digital-twin state snapshots periodically
- Produces guidance signals that modulate holon decisions
- Does NOT directly schedule tasks, but changes policy knobs

The orchestrator can be:
1. Rule-based heuristics (default)
2. Pluggable with real LLM calls (future extension)
"""

from demanufacturing_sim.orchestrator.llm_orchestrator import (
    CognitiveOrchestrator,
    OrchestratorConfig,
    GuidanceSignal,
    StrategyType
)

__all__ = [
    'CognitiveOrchestrator',
    'OrchestratorConfig',
    'GuidanceSignal',
    'StrategyType'
]
