# Moved to infra layer - re-export for backwards compatibility
from simulator.infra.metrics import ErrorCategory, MetricsCollector

__all__ = ['ErrorCategory', 'MetricsCollector']