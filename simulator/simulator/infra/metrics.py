"""Metrics collection for distributed system simulation.

This module provides generic metrics collection capabilities for tracking
system behavior, errors, and performance.

Moved from models/metrics.py as it's generic enough for any distributed system.

Phase 3 enhancements: Added latency aggregation with percentiles and histograms.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
import statistics


class ErrorCategory(str, Enum):
    """Categories for classifying errors in the simulation.

    Moved from models/metrics.py:4-9.
    """
    APPLICATION_ERROR = "Application Error"
    INFRASTRUCTURE_ERROR = "Infrastructure Error"
    CONSISTENCY_ERROR = "Consistency Error"
    STORAGE_ERROR = "Storage Error"
    UNKNOWN_ERROR = "Unknown Error"


class MetricsCollector:
    """Collects metrics about system behavior and performance.

    Tracks redirects, request routing accuracy, failure reasons, and latency statistics.

    Moved from models/metrics.py:11-30.
    Phase 3: Added latency aggregation capabilities.
    """

    def __init__(self):
        self.total_redirects = 0
        self.leader_requests_correct_node = 0
        self.leader_requests_wrong_node = 0
        self.failure_reasons: Dict[ErrorCategory, Dict[str, int]] = {
            category: {} for category in ErrorCategory
        }
        # Phase 3: Latency tracking
        self.latencies: Dict[str, List[float]] = {}  # operation_name -> list of latencies

    def increment_redirects(self):
        self.total_redirects += 1

    def increment_correct_leader_requests(self):
        self.leader_requests_correct_node += 1

    def increment_wrong_leader_requests(self):
        self.leader_requests_wrong_node += 1

    def increment_failure_reason(self, category: ErrorCategory, reason: str):
        self.failure_reasons[category][reason] = self.failure_reasons[category].get(reason, 0) + 1

    # Phase 3: Latency aggregation methods

    def record_latency(self, operation: str, latency: float):
        """Record a latency measurement for an operation.

        Args:
            operation: Name of the operation (e.g., "request_processing", "disk_write")
            latency: Latency in seconds
        """
        if operation not in self.latencies:
            self.latencies[operation] = []
        self.latencies[operation].append(latency)

    def get_latency_stats(self, operation: str) -> Optional[Dict[str, float]]:
        """Get latency statistics for an operation.

        Args:
            operation: Name of the operation

        Returns:
            Dictionary with mean, median, p50, p95, p99, min, max, or None if no data
        """
        if operation not in self.latencies or not self.latencies[operation]:
            return None

        latencies = sorted(self.latencies[operation])
        count = len(latencies)

        return {
            "count": count,
            "mean": statistics.mean(latencies),
            "median": statistics.median(latencies),
            "p50": self._percentile(latencies, 50),
            "p95": self._percentile(latencies, 95),
            "p99": self._percentile(latencies, 99),
            "min": min(latencies),
            "max": max(latencies),
            "stddev": statistics.stdev(latencies) if count > 1 else 0.0
        }

    def get_all_latency_stats(self) -> Dict[str, Dict[str, float]]:
        """Get latency statistics for all operations.

        Returns:
            Dictionary mapping operation names to their statistics
        """
        result = {}
        for operation in self.latencies:
            if self.latencies[operation]:
                stats = self.get_latency_stats(operation)
                if stats is not None:
                    result[operation] = stats
        return result

    def get_histogram(
        self,
        operation: str,
        num_buckets: int = 10
    ) -> Optional[Dict[str, Any]]:
        """Get a histogram of latencies for an operation.

        Args:
            operation: Name of the operation
            num_buckets: Number of histogram buckets (default: 10)

        Returns:
            Dictionary with bucket_edges and counts, or None if no data
        """
        if operation not in self.latencies or not self.latencies[operation]:
            return None

        latencies = sorted(self.latencies[operation])
        min_lat = min(latencies)
        max_lat = max(latencies)

        # Create bucket edges
        bucket_width = (max_lat - min_lat) / num_buckets
        bucket_edges = [min_lat + i * bucket_width for i in range(num_buckets + 1)]

        # Count values in each bucket
        counts = [0] * num_buckets
        for latency in latencies:
            bucket_idx = min(int((latency - min_lat) / bucket_width), num_buckets - 1)
            counts[bucket_idx] += 1

        return {
            "bucket_edges": bucket_edges,
            "counts": counts,
            "num_buckets": num_buckets
        }

    @staticmethod
    def _percentile(sorted_data: List[float], percentile: float) -> float:
        """Calculate percentile from sorted data.

        Args:
            sorted_data: Sorted list of values
            percentile: Percentile to calculate (0-100)

        Returns:
            Value at the given percentile
        """
        if not sorted_data:
            return 0.0

        k = (len(sorted_data) - 1) * (percentile / 100.0)
        f = int(k)
        c = f + 1

        if c >= len(sorted_data):
            return sorted_data[-1]

        # Linear interpolation between floor and ceiling
        d0 = sorted_data[f] * (c - k)
        d1 = sorted_data[c] * (k - f)
        return d0 + d1
