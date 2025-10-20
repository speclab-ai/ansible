"""Request tracing for distributed system simulation.

This module provides enhanced observability through request lifecycle tracing,
enabling detailed latency analysis and performance debugging.

New feature added in Phase 3 (Enhanced Observability).
"""

import simpy
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel


class TraceEvent(BaseModel):
    """A single event in a request's lifecycle."""
    timestamp: float
    operation: str
    component_id: str
    metadata: Dict[str, Any] = {}

    class Config:
        arbitrary_types_allowed = True


class Tracer:
    """Records timestamped events for request lifecycle analysis.

    Enables detailed tracking of request flow through the distributed system,
    calculating latencies between operations and identifying bottlenecks.

    Example usage:
        tracer = Tracer(env)
        tracer.record_event(request_id, "client_send", "client_1")
        tracer.record_event(request_id, "gateway_receive", "gateway_1")
        latency = tracer.get_latency(request_id, "client_send", "gateway_receive")
    """

    def __init__(self, env: simpy.Environment):
        """Initialize the tracer.

        Args:
            env: SimPy environment for timestamp management
        """
        self.env = env
        # Maps request_id -> list of trace events
        self.traces: Dict[str, List[TraceEvent]] = {}

    def record_event(
        self,
        request_id: str,
        operation: str,
        component_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a timestamped event for a request.

        Args:
            request_id: Unique identifier for the request
            operation: Name of the operation (e.g., "client_send", "gateway_receive")
            component_id: ID of the component performing the operation
            metadata: Optional additional data about the event
        """
        if request_id not in self.traces:
            self.traces[request_id] = []

        event = TraceEvent(
            timestamp=self.env.now,
            operation=operation,
            component_id=component_id,
            metadata=metadata or {}
        )
        self.traces[request_id].append(event)

    def get_trace(self, request_id: str) -> List[TraceEvent]:
        """Get all trace events for a request.

        Args:
            request_id: Unique identifier for the request

        Returns:
            List of trace events in chronological order
        """
        return self.traces.get(request_id, [])

    def get_latency(
        self,
        request_id: str,
        start_operation: str,
        end_operation: str
    ) -> Optional[float]:
        """Calculate latency between two operations in a request's lifecycle.

        Args:
            request_id: Unique identifier for the request
            start_operation: Name of the starting operation
            end_operation: Name of the ending operation

        Returns:
            Latency in seconds, or None if operations not found
        """
        events = self.traces.get(request_id, [])

        start_time = None
        end_time = None

        for event in events:
            if event.operation == start_operation and start_time is None:
                start_time = event.timestamp
            if event.operation == end_operation:
                end_time = event.timestamp

        if start_time is not None and end_time is not None:
            return end_time - start_time

        return None

    def get_all_latencies(
        self,
        start_operation: str,
        end_operation: str
    ) -> List[float]:
        """Get latencies for all requests between two operations.

        Useful for calculating aggregate statistics (avg, p99, etc.).

        Args:
            start_operation: Name of the starting operation
            end_operation: Name of the ending operation

        Returns:
            List of latencies in seconds
        """
        latencies = []

        for request_id in self.traces:
            latency = self.get_latency(request_id, start_operation, end_operation)
            if latency is not None:
                latencies.append(latency)

        return latencies

    def get_operation_count(self, operation: str) -> int:
        """Count how many times an operation occurred across all requests.

        Args:
            operation: Name of the operation

        Returns:
            Count of occurrences
        """
        count = 0
        for events in self.traces.values():
            count += sum(1 for event in events if event.operation == operation)
        return count

    def clear_request(self, request_id: str):
        """Clear trace data for a completed request to save memory.

        Args:
            request_id: Unique identifier for the request
        """
        if request_id in self.traces:
            del self.traces[request_id]

    def get_request_summary(self, request_id: str) -> Dict[str, Any]:
        """Get a summary of a request's journey through the system.

        Args:
            request_id: Unique identifier for the request

        Returns:
            Dictionary with request lifecycle information
        """
        events = self.traces.get(request_id, [])

        if not events:
            return {"request_id": request_id, "found": False}

        return {
            "request_id": request_id,
            "found": True,
            "start_time": events[0].timestamp,
            "end_time": events[-1].timestamp,
            "total_latency": events[-1].timestamp - events[0].timestamp,
            "num_events": len(events),
            "operations": [event.operation for event in events],
            "components": list(set(event.component_id for event in events))
        }
