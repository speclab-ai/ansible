"""Contextual logging utilities for distributed system simulation.

This module provides logging helpers that automatically include request context
and machine-aware timestamps in log messages.

Extracted from duplicated _get_log_prefix() methods in GatewayNode and DataNode.
"""

import simpy
from typing import Optional
import logging

from simulator.infra.machine import Machine
from simulator.infra.request_context import RequestContext


class ContextLogger:
    """Logger that automatically includes request context and timestamps.

    Provides structured logging with:
    - Machine-aware timestamps (includes clock skew)
    - Component identification
    - Optional request ID tracking

    Extracted from GatewayNode:46-49 and DataNode:51-54.
    """

    def __init__(self, component_id: str, machine: Machine, env: simpy.Environment):
        """Initialize the context logger.

        Args:
            component_id: Identifier for the component (e.g., "GatewayNode gateway-1")
            machine: The machine this component runs on (for timestamp)
            env: SimPy environment (for current time)
        """
        self.component_id = component_id
        self.machine = machine
        self.env = env
        self._logger = logging.getLogger(__name__)

    def _get_prefix(self, request_context: Optional[RequestContext] = None) -> str:
        """Get formatted log prefix with timestamp and optional request ID.

        Exact same logic as existing _get_log_prefix() methods.

        Args:
            request_context: Optional request context for request ID

        Returns:
            Formatted log prefix string
        """
        timestamp = self.machine.get_current_time(self.env.now)
        base = f"[{timestamp:.4f}] {self.component_id}"
        if request_context and request_context.request_id:
            return f"{base} [ReqID: {request_context.request_id}]"
        return base

    def info(self, msg: str, request_context: Optional[RequestContext] = None):
        """Log an info message with context.

        Args:
            msg: The message to log
            request_context: Optional request context
        """
        prefix = self._get_prefix(request_context)
        self._logger.info(f"{prefix} {msg}")

    def warning(self, msg: str, request_context: Optional[RequestContext] = None):
        """Log a warning message with context.

        Args:
            msg: The message to log
            request_context: Optional request context
        """
        prefix = self._get_prefix(request_context)
        self._logger.warning(f"{prefix} {msg}")

    def error(self, msg: str, request_context: Optional[RequestContext] = None):
        """Log an error message with context.

        Args:
            msg: The message to log
            request_context: Optional request context
        """
        prefix = self._get_prefix(request_context)
        self._logger.error(f"{prefix} {msg}")

    def debug(self, msg: str, request_context: Optional[RequestContext] = None):
        """Log a debug message with context.

        Args:
            msg: The message to log
            request_context: Optional request context
        """
        prefix = self._get_prefix(request_context)
        self._logger.debug(f"{prefix} {msg}")
