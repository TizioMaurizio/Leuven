"""
Event Bus abstraction for holon communication.

Provides a simple pub/sub mechanism for holons to exchange messages
and for the orchestrator to broadcast guidance signals.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Any, Optional, Set
from enum import Enum, auto
import logging


class EventType(Enum):
    """Types of events that can flow through the system."""
    # Product events
    PRODUCT_ARRIVED = auto()
    PRODUCT_INSPECTION_REQUEST = auto()
    PRODUCT_INSPECTION_COMPLETE = auto()
    PRODUCT_DISASSEMBLY_REQUEST = auto()
    PRODUCT_DISASSEMBLY_COMPLETE = auto()
    PRODUCT_CLASSIFICATION_COMPLETE = auto()
    PRODUCT_ROUTING_DECISION = auto()
    PRODUCT_EXITED = auto()
    
    # Resource events
    RESOURCE_AVAILABLE = auto()
    RESOURCE_BUSY = auto()
    RESOURCE_FAILURE = auto()
    RESOURCE_DEGRADED = auto()
    RESOURCE_RECOVERED = auto()
    RESOURCE_TASK_ACCEPTED = auto()
    RESOURCE_TASK_REJECTED = auto()
    
    # Transport events
    TRANSPORT_REQUEST = auto()
    TRANSPORT_STARTED = auto()
    TRANSPORT_COMPLETE = auto()
    TRANSPORT_BLOCKED = auto()
    
    # System events
    SYSTEM_STATE_UPDATE = auto()
    SYSTEM_BOTTLENECK_DETECTED = auto()
    SYSTEM_DEADLOCK_DETECTED = auto()
    SYSTEM_THROUGHPUT_UPDATE = auto()
    
    # Orchestrator guidance
    GUIDANCE_PRIORITY_CHANGE = auto()
    GUIDANCE_POLICY_MODULATION = auto()
    GUIDANCE_REROUTE_SUGGESTION = auto()
    GUIDANCE_DISASSEMBLY_DEPTH = auto()
    GUIDANCE_STRATEGY_CHANGE = auto()


@dataclass
class Event:
    """
    An event that flows through the event bus.
    
    Attributes:
        event_type: The type/category of event
        source_id: ID of the holon that emitted the event
        target_id: Optional target holon ID (None for broadcast)
        timestamp: Simulation time when event was created
        payload: Event-specific data dictionary
        priority: Event priority (higher = more urgent)
    """
    event_type: EventType
    source_id: str
    timestamp: float
    payload: Dict[str, Any] = field(default_factory=dict)
    target_id: Optional[str] = None
    priority: int = 0
    
    def __lt__(self, other):
        """For priority queue ordering."""
        return self.priority > other.priority  # Higher priority first


class EventBus:
    """
    Central event bus for holon communication.
    
    Provides pub/sub pattern with support for:
    - Type-based subscriptions
    - Target-specific delivery
    - Broadcast messages
    - Event history for debugging
    """
    
    def __init__(self, max_history: int = 1000):
        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = {}
        self._holon_handlers: Dict[str, Callable[[Event], None]] = {}
        self._event_history: List[Event] = []
        self._max_history = max_history
        self._paused = False
        self._pending_events: List[Event] = []
        self.logger = logging.getLogger("event_bus")
        
        # Statistics
        self.events_published = 0
        self.events_delivered = 0
    
    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """
        Subscribe to events of a specific type.
        
        Args:
            event_type: Type of events to receive
            handler: Callback function to handle events
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def subscribe_all(self, handler: Callable[[Event], None], 
                      event_types: List[EventType] = None) -> None:
        """Subscribe to multiple event types at once."""
        types = event_types or list(EventType)
        for et in types:
            self.subscribe(et, handler)
    
    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Remove a subscription."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h != handler
            ]
    
    def register_holon(self, holon_id: str, handler: Callable[[Event], None]) -> None:
        """
        Register a holon's direct message handler.
        
        Args:
            holon_id: Unique ID of the holon
            handler: Handler for direct messages to this holon
        """
        self._holon_handlers[holon_id] = handler
    
    def unregister_holon(self, holon_id: str) -> None:
        """Unregister a holon."""
        if holon_id in self._holon_handlers:
            del self._holon_handlers[holon_id]
    
    def publish(self, event: Event) -> None:
        """
        Publish an event to the bus.
        
        Args:
            event: Event to publish
        """
        self.events_published += 1
        
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history // 2:]
        
        if self._paused:
            self._pending_events.append(event)
            return
        
        self._deliver_event(event)
    
    def _deliver_event(self, event: Event) -> None:
        """Deliver an event to subscribers."""
        # Direct delivery to target holon
        if event.target_id and event.target_id in self._holon_handlers:
            try:
                self._holon_handlers[event.target_id](event)
                self.events_delivered += 1
            except Exception as e:
                self.logger.error(f"Error delivering event to {event.target_id}: {e}")
        
        # Broadcast to type subscribers
        if event.event_type in self._subscribers:
            for handler in self._subscribers[event.event_type]:
                try:
                    handler(event)
                    self.events_delivered += 1
                except Exception as e:
                    self.logger.error(f"Error in event handler: {e}")
    
    def pause(self) -> None:
        """Pause event delivery (for batch processing)."""
        self._paused = True
    
    def resume(self) -> None:
        """Resume event delivery and process pending events."""
        self._paused = False
        for event in self._pending_events:
            self._deliver_event(event)
        self._pending_events.clear()
    
    def get_recent_events(self, n: int = 50, 
                          event_type: EventType = None) -> List[Event]:
        """Get recent events, optionally filtered by type."""
        events = self._event_history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-n:]
    
    def get_events_in_window(self, start_time: float, 
                             end_time: float) -> List[Event]:
        """Get events within a time window."""
        return [e for e in self._event_history 
                if start_time <= e.timestamp <= end_time]
    
    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bus statistics."""
        event_counts = {}
        for event in self._event_history:
            et = event.event_type.name
            event_counts[et] = event_counts.get(et, 0) + 1
        
        return {
            "total_published": self.events_published,
            "total_delivered": self.events_delivered,
            "history_size": len(self._event_history),
            "subscribers": {et.name: len(handlers) 
                          for et, handlers in self._subscribers.items()},
            "registered_holons": len(self._holon_handlers),
            "event_counts": event_counts
        }
