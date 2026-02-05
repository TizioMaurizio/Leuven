"""
LLM-like Cognitive Orchestrator for holonic demanufacturing control.

This orchestrator acts as a meta-cognitive layer that:
- Periodically reads system state snapshots
- Analyzes long-horizon tradeoffs with global awareness
- Produces guidance signals to modulate holon behavior

IMPORTANT: This does NOT directly schedule tasks. It changes policy 
parameters and broadcasts recommendations that holons can follow.

The default implementation uses rule-based heuristics that mimic
the reasoning an LLM might perform. A clean interface is provided
to swap with real LLM calls in the future.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from enum import Enum, auto
import statistics
import logging


class StrategyType(Enum):
    """High-level orchestration strategies."""
    BALANCED = auto()           # Normal operation, balanced priorities
    DEEP_DISASSEMBLY = auto()   # Maximize value extraction
    EARLY_RECYCLE = auto()      # Clear queues quickly, accept lower recovery
    CLEAR_BOTTLENECK = auto()   # Focus on resolving specific bottleneck
    HIGH_VALUE_PRIORITY = auto() # Rush high-value items through
    RECOVERY_MODE = auto()      # After failure, stabilize operations
    SURGE_HANDLING = auto()     # Handle arrival surges


@dataclass
class GuidanceSignal:
    """
    A guidance signal from the orchestrator to holons.
    
    These are recommendations, not commands. Holons may or may not follow.
    """
    signal_type: str
    timestamp: float
    priority: float = 1.0
    parameters: Dict[str, Any] = field(default_factory=dict)
    target_holons: List[str] = field(default_factory=list)  # Empty = broadcast
    reason: str = ""
    expires: Optional[float] = None  # Auto-expire after this time
    
    def is_expired(self, current_time: float) -> bool:
        """Check if signal has expired."""
        if self.expires is None:
            return False
        return current_time > self.expires


@dataclass
class OrchestratorConfig:
    """Configuration for the cognitive orchestrator."""
    # Update frequency
    update_interval: float = 30.0  # Seconds of simulated time between updates
    
    # Thresholds
    high_value_threshold: float = 50.0
    bottleneck_queue_threshold: float = 0.7
    throughput_drop_threshold: float = 0.3
    wip_high_threshold: int = 50
    wip_low_threshold: int = 10
    uncertainty_high_threshold: float = 0.6
    
    # Strategy parameters
    max_priority_boost: float = 2.0
    min_priority_reduction: float = 0.5
    strategy_hold_time: float = 60.0  # Minimum time to hold a strategy
    
    # Fault response
    recovery_duration: float = 120.0  # Time to stay in recovery mode
    
    # Whether to enable the orchestrator
    enabled: bool = True


class OrchestratorBrain(ABC):
    """
    Abstract base for orchestrator decision logic.
    
    Can be implemented as:
    - Rule-based heuristics (RuleBasedBrain)
    - LLM-powered reasoning (future LLMBrain)
    """
    
    @abstractmethod
    def analyze_state(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze system state and return analysis results.
        
        Args:
            context: System state context from SystemHolon
        
        Returns:
            Analysis dict with identified issues and opportunities
        """
        pass
    
    @abstractmethod
    def decide_strategy(self, analysis: Dict[str, Any],
                       current_strategy: StrategyType) -> StrategyType:
        """
        Decide which high-level strategy to pursue.
        
        Args:
            analysis: Results from analyze_state
            current_strategy: Current active strategy
        
        Returns:
            New or continued strategy
        """
        pass
    
    @abstractmethod
    def generate_guidance(self, analysis: Dict[str, Any],
                         strategy: StrategyType,
                         timestamp: float) -> List[GuidanceSignal]:
        """
        Generate specific guidance signals for holons.
        
        Args:
            analysis: Results from analyze_state
            strategy: Current strategy
            timestamp: Current simulation time
        
        Returns:
            List of guidance signals
        """
        pass


class RuleBasedBrain(OrchestratorBrain):
    """
    Rule-based implementation of orchestrator reasoning.
    
    Uses heuristics that mimic what an LLM might reason about:
    - If queues are building up -> prioritize throughput
    - If failures occur -> reroute and recover
    - If high-value items waiting -> prioritize them
    - etc.
    """
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.logger = logging.getLogger("orchestrator.brain")
    
    def analyze_state(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze system state and identify issues/opportunities."""
        analysis = {
            "issues": [],
            "opportunities": [],
            "metrics": {},
            "recommendations": []
        }
        
        # Analyze system health
        health = context.get("system_health", 1.0)
        if health < 0.7:
            analysis["issues"].append({
                "type": "low_system_health",
                "severity": "high" if health < 0.5 else "medium",
                "value": health
            })
        
        # Analyze failed resources
        failed = context.get("failed_resources", 0)
        if failed > 0:
            analysis["issues"].append({
                "type": "resource_failures",
                "severity": "critical",
                "count": failed
            })
        
        # Analyze bottlenecks
        for bottleneck in context.get("bottlenecks", []):
            analysis["issues"].append({
                "type": "bottleneck",
                "location": bottleneck.get("location"),
                "bottleneck_type": bottleneck.get("type"),
                "severity": bottleneck.get("severity", "medium")
            })
        
        # Analyze WIP levels
        wip = context.get("wip_level", 0)
        analysis["metrics"]["wip_level"] = wip
        if wip > self.config.wip_high_threshold:
            analysis["issues"].append({
                "type": "high_wip",
                "severity": "medium",
                "value": wip
            })
        elif wip < self.config.wip_low_threshold:
            analysis["opportunities"].append({
                "type": "capacity_available",
                "value": self.config.wip_high_threshold - wip
            })
        
        # Analyze throughput trend
        trend = context.get("throughput_trend", "stable")
        analysis["metrics"]["throughput_trend"] = trend
        if trend == "decreasing":
            analysis["issues"].append({
                "type": "throughput_declining",
                "severity": "high"
            })
        
        # Analyze high-value products
        high_value = context.get("high_value_products", 0)
        analysis["metrics"]["high_value_products"] = high_value
        if high_value > 3:
            analysis["opportunities"].append({
                "type": "high_value_items_present",
                "count": high_value
            })
        
        # Analyze uncertainty levels
        avg_uncertainty = context.get("avg_uncertainty", 0)
        analysis["metrics"]["avg_uncertainty"] = avg_uncertainty
        if avg_uncertainty > self.config.uncertainty_high_threshold:
            analysis["recommendations"].append({
                "action": "increase_inspection_depth",
                "reason": "High uncertainty in product population"
            })
        
        # Analyze queue distribution
        products_by_stage = context.get("products_by_stage", {})
        analysis["metrics"]["stage_distribution"] = products_by_stage
        
        # Identify stage with most items (potential bottleneck indicator)
        if products_by_stage:
            max_stage = max(products_by_stage.items(), key=lambda x: x[1])
            if max_stage[1] > 10:
                analysis["issues"].append({
                    "type": "stage_congestion",
                    "stage": max_stage[0],
                    "count": max_stage[1],
                    "severity": "medium"
                })
        
        # Analyze blocked transports
        blocked = context.get("blocked_transports", 0)
        if blocked > 0:
            analysis["issues"].append({
                "type": "transport_congestion",
                "severity": "medium" if blocked < 2 else "high",
                "count": blocked
            })
        
        return analysis
    
    def decide_strategy(self, analysis: Dict[str, Any],
                       current_strategy: StrategyType) -> StrategyType:
        """Decide high-level strategy based on analysis."""
        issues = analysis.get("issues", [])
        opportunities = analysis.get("opportunities", [])
        
        # Priority 1: Critical issues override everything
        critical_issues = [i for i in issues if i.get("severity") == "critical"]
        if critical_issues:
            # Check for failures
            if any(i["type"] == "resource_failures" for i in critical_issues):
                return StrategyType.RECOVERY_MODE
        
        # Priority 2: High severity issues
        high_issues = [i for i in issues if i.get("severity") == "high"]
        if high_issues:
            # Throughput declining -> need to clear bottlenecks
            if any(i["type"] == "throughput_declining" for i in high_issues):
                return StrategyType.CLEAR_BOTTLENECK
            
            # System health low
            if any(i["type"] == "low_system_health" for i in high_issues):
                return StrategyType.RECOVERY_MODE
        
        # Priority 3: Opportunities
        if opportunities:
            # High value items present -> prioritize them
            high_value_opp = [o for o in opportunities 
                            if o["type"] == "high_value_items_present"]
            if high_value_opp and high_value_opp[0].get("count", 0) > 2:
                return StrategyType.HIGH_VALUE_PRIORITY
            
            # Capacity available -> can do deeper disassembly
            capacity_opp = [o for o in opportunities 
                          if o["type"] == "capacity_available"]
            if capacity_opp:
                return StrategyType.DEEP_DISASSEMBLY
        
        # Priority 4: Medium issues
        medium_issues = [i for i in issues if i.get("severity") == "medium"]
        if medium_issues:
            # High WIP -> need to clear through faster
            if any(i["type"] == "high_wip" for i in medium_issues):
                return StrategyType.EARLY_RECYCLE
            
            # Stage congestion -> clear bottleneck
            if any(i["type"] == "stage_congestion" for i in medium_issues):
                return StrategyType.CLEAR_BOTTLENECK
        
        # Default: balanced operation
        return StrategyType.BALANCED
    
    def generate_guidance(self, analysis: Dict[str, Any],
                         strategy: StrategyType,
                         timestamp: float) -> List[GuidanceSignal]:
        """Generate specific guidance signals."""
        signals = []
        
        # Strategy-specific guidance
        if strategy == StrategyType.DEEP_DISASSEMBLY:
            signals.append(GuidanceSignal(
                signal_type="disassembly_depth",
                timestamp=timestamp,
                parameters={"depth": "deep"},
                reason="Capacity available for thorough value extraction",
                expires=timestamp + self.config.strategy_hold_time
            ))
            signals.append(GuidanceSignal(
                signal_type="priority_adjustment",
                timestamp=timestamp,
                parameters={
                    "route_multipliers": {"reuse": 1.5, "remanufacture": 1.2}
                },
                reason="Prioritize high-recovery routes"
            ))
        
        elif strategy == StrategyType.EARLY_RECYCLE:
            signals.append(GuidanceSignal(
                signal_type="disassembly_depth",
                timestamp=timestamp,
                parameters={"depth": "shallow"},
                reason="High WIP - prioritize throughput over recovery",
                expires=timestamp + self.config.strategy_hold_time
            ))
            signals.append(GuidanceSignal(
                signal_type="routing_bias",
                timestamp=timestamp,
                parameters={"bias": "recycle", "threshold_adjust": -0.1},
                reason="Lower routing thresholds to clear queues"
            ))
        
        elif strategy == StrategyType.CLEAR_BOTTLENECK:
            # Find the bottleneck location
            bottlenecks = [i for i in analysis.get("issues", []) 
                         if i["type"] == "bottleneck"]
            if bottlenecks:
                signals.append(GuidanceSignal(
                    signal_type="reroute_suggestion",
                    timestamp=timestamp,
                    parameters={
                        "avoid_resources": [b["location"] for b in bottlenecks],
                        "prefer_alternative": True
                    },
                    reason=f"Clearing bottleneck at {bottlenecks[0].get('location')}"
                ))
            
            # Also reduce incoming priority to bottleneck
            signals.append(GuidanceSignal(
                signal_type="flow_control",
                timestamp=timestamp,
                parameters={"reduce_inflow": 0.7},
                reason="Reduce pressure on bottleneck"
            ))
        
        elif strategy == StrategyType.HIGH_VALUE_PRIORITY:
            signals.append(GuidanceSignal(
                signal_type="priority_adjustment",
                timestamp=timestamp,
                parameters={
                    "value_threshold": self.config.high_value_threshold,
                    "boost_factor": self.config.max_priority_boost
                },
                reason="Rush high-value items through system"
            ))
            signals.append(GuidanceSignal(
                signal_type="disassembly_depth",
                timestamp=timestamp,
                parameters={"depth": "deep", "for_high_value": True},
                reason="Maximize recovery from high-value items"
            ))
        
        elif strategy == StrategyType.RECOVERY_MODE:
            signals.append(GuidanceSignal(
                signal_type="system_mode",
                timestamp=timestamp,
                parameters={"mode": "recovery"},
                reason="System recovering from failure"
            ))
            signals.append(GuidanceSignal(
                signal_type="reroute_suggestion",
                timestamp=timestamp,
                parameters={
                    "use_alternative_resources": True,
                    "reduce_load": 0.5
                },
                reason="Redistribute load away from failed resources"
            ))
            signals.append(GuidanceSignal(
                signal_type="disassembly_depth",
                timestamp=timestamp,
                parameters={"depth": "standard"},
                reason="Maintain standard operations during recovery"
            ))
        
        elif strategy == StrategyType.SURGE_HANDLING:
            signals.append(GuidanceSignal(
                signal_type="flow_control",
                timestamp=timestamp,
                parameters={"buffer_mode": "absorb"},
                reason="Absorbing arrival surge in buffers"
            ))
            signals.append(GuidanceSignal(
                signal_type="disassembly_depth",
                timestamp=timestamp,
                parameters={"depth": "shallow"},
                reason="Reduce processing time during surge"
            ))
        
        else:  # BALANCED
            signals.append(GuidanceSignal(
                signal_type="system_mode",
                timestamp=timestamp,
                parameters={"mode": "balanced"},
                reason="Normal balanced operation"
            ))
        
        # Add general recommendations from analysis
        for rec in analysis.get("recommendations", []):
            signals.append(GuidanceSignal(
                signal_type="recommendation",
                timestamp=timestamp,
                parameters=rec,
                reason=rec.get("reason", "Analysis recommendation")
            ))
        
        return signals


class CognitiveOrchestrator:
    """
    Main orchestrator class that coordinates cognitive control.
    
    This is the entry point for orchestrated holonic control.
    It periodically reads system state and generates guidance.
    """
    
    def __init__(self, config: OrchestratorConfig = None,
                brain: OrchestratorBrain = None):
        self.config = config or OrchestratorConfig()
        self.brain = brain or RuleBasedBrain(self.config)
        self.logger = logging.getLogger("orchestrator")
        
        # State
        self.current_strategy = StrategyType.BALANCED
        self.strategy_start_time: float = 0.0
        self.active_signals: List[GuidanceSignal] = []
        
        # History
        self.strategy_history: List[tuple] = []  # (timestamp, strategy)
        self.guidance_history: List[GuidanceSignal] = []
        
        # Metrics
        self.updates_count = 0
        self.strategy_changes = 0
        
        # Callbacks
        self._on_strategy_change: Optional[Callable] = None
        self._on_guidance: Optional[Callable] = None
    
    @property
    def is_enabled(self) -> bool:
        """Check if orchestrator is enabled."""
        return self.config.enabled
    
    def update(self, context: Dict[str, Any], 
               current_time: float) -> Dict[str, Any]:
        """
        Perform orchestrator update cycle.
        
        Args:
            context: System state context from SystemHolon
            current_time: Current simulation time
        
        Returns:
            Guidance dict to apply to system
        """
        if not self.is_enabled:
            return {"strategy": "disabled", "signals": []}
        
        self.updates_count += 1
        
        # Analyze state
        analysis = self.brain.analyze_state(context)
        
        # Decide strategy (with hysteresis)
        time_in_strategy = current_time - self.strategy_start_time
        if time_in_strategy >= self.config.strategy_hold_time:
            new_strategy = self.brain.decide_strategy(analysis, self.current_strategy)
            if new_strategy != self.current_strategy:
                self._change_strategy(new_strategy, current_time)
        
        # Generate guidance signals
        signals = self.brain.generate_guidance(
            analysis, self.current_strategy, current_time
        )
        
        # Expire old signals
        self._expire_signals(current_time)
        
        # Store new signals
        self.active_signals.extend(signals)
        self.guidance_history.extend(signals)
        
        # Trigger callback
        if self._on_guidance and signals:
            self._on_guidance(signals)
        
        # Build guidance dict for application
        guidance = self._build_guidance_dict(signals, current_time)
        guidance["strategy"] = self.current_strategy.name
        guidance["analysis_summary"] = {
            "issues_count": len(analysis.get("issues", [])),
            "opportunities_count": len(analysis.get("opportunities", [])),
            "metrics": analysis.get("metrics", {})
        }
        
        return guidance
    
    def _change_strategy(self, new_strategy: StrategyType, 
                        current_time: float) -> None:
        """Change to a new strategy."""
        old_strategy = self.current_strategy
        self.current_strategy = new_strategy
        self.strategy_start_time = current_time
        self.strategy_changes += 1
        
        self.strategy_history.append((current_time, new_strategy))
        
        self.logger.info(f"Strategy change: {old_strategy.name} -> {new_strategy.name}")
        
        if self._on_strategy_change:
            self._on_strategy_change(old_strategy, new_strategy, current_time)
    
    def _expire_signals(self, current_time: float) -> None:
        """Remove expired signals."""
        self.active_signals = [
            s for s in self.active_signals 
            if not s.is_expired(current_time)
        ]
    
    def _build_guidance_dict(self, signals: List[GuidanceSignal],
                            current_time: float) -> Dict[str, Any]:
        """Build a guidance dictionary from signals."""
        guidance = {
            "signals": signals,
            "timestamp": current_time
        }
        
        # Extract specific guidance types
        for signal in signals:
            if signal.signal_type == "priority_adjustment":
                guidance.setdefault("priority_adjustments", {}).update(
                    signal.parameters
                )
            elif signal.signal_type == "disassembly_depth":
                guidance["disassembly_depth"] = signal.parameters.get("depth")
            elif signal.signal_type == "reroute_suggestion":
                guidance["reroute"] = signal.parameters
            elif signal.signal_type == "routing_bias":
                guidance["routing_bias"] = signal.parameters
            elif signal.signal_type == "flow_control":
                guidance["flow_control"] = signal.parameters
            elif signal.signal_type == "system_mode":
                guidance["system_mode"] = signal.parameters.get("mode")
        
        return guidance
    
    def get_active_signals_summary(self) -> List[Dict[str, Any]]:
        """Get summary of active signals for display."""
        return [
            {
                "type": s.signal_type,
                "reason": s.reason,
                "priority": s.priority
            }
            for s in sorted(self.active_signals, 
                          key=lambda x: x.priority, reverse=True)[:5]
        ]
    
    def get_state_for_display(self) -> Dict[str, Any]:
        """Get orchestrator state for visualization."""
        return {
            "enabled": self.is_enabled,
            "strategy": self.current_strategy.name,
            "active_signals_count": len(self.active_signals),
            "top_signals": self.get_active_signals_summary()[:3],
            "updates_count": self.updates_count,
            "strategy_changes": self.strategy_changes
        }
    
    def force_strategy(self, strategy: StrategyType, 
                      current_time: float) -> None:
        """Force a specific strategy (for testing/manual override)."""
        self._change_strategy(strategy, current_time)
    
    def disable(self) -> None:
        """Disable the orchestrator."""
        self.config.enabled = False
        self.active_signals.clear()
    
    def enable(self) -> None:
        """Enable the orchestrator."""
        self.config.enabled = True


# Factory function for creating orchestrator with LLM brain (future)
def create_llm_orchestrator(api_key: str = None, 
                           model: str = "gpt-4") -> CognitiveOrchestrator:
    """
    Create an orchestrator with LLM-powered reasoning.
    
    PLACEHOLDER: This would instantiate an LLMBrain that makes
    actual API calls. For now, falls back to rule-based.
    """
    config = OrchestratorConfig()
    # In future: brain = LLMBrain(api_key, model, config)
    brain = RuleBasedBrain(config)  # Fallback
    return CognitiveOrchestrator(config, brain)
