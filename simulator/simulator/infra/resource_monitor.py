"""Resource monitoring for distributed system simulation.

This module provides comprehensive resource utilization tracking across
machines, disks, and network links for capacity planning and performance analysis.

New feature added in Phase 5 (Resource Modeling).
"""

import simpy
from typing import Any, Dict, List, Tuple, Optional
from pydantic import BaseModel

from simulator.infra.machine import Machine
from simulator.infra.network import Network, NetworkLink

import logging
logger = logging.getLogger(__name__)


class ResourceSample(BaseModel):
    """A single resource utilization sample."""
    timestamp: float
    machine_id: str
    cpu_utilization: float = 0.0  # Percentage (0-100)
    cpu_available: float = 0.0  # Available CPU units
    disk_utilization: float = 0.0  # Percentage (0-100)
    disk_available: float = 0.0  # Available bytes
    disk_write_iops_utilization: float = 0.0  # Percentage (0-100)
    disk_read_iops_utilization: float = 0.0  # Percentage (0-100)
    disk_throughput_utilization: float = 0.0  # Percentage (0-100)

    class Config:
        arbitrary_types_allowed = True


class NetworkLinkSample(BaseModel):
    """A single network link utilization sample."""
    timestamp: float
    link_id: str
    sender_id: str
    receiver_id: str
    bandwidth_utilization: float = 0.0  # Percentage (0-100)
    packet_rate_utilization: float = 0.0  # Percentage (0-100)

    class Config:
        arbitrary_types_allowed = True


class ResourceMonitor:
    """Monitors resource utilization across the distributed system.

    Tracks CPU, disk, and network utilization over time for capacity
    planning, performance debugging, and bottleneck identification.

    Example usage:
        monitor = ResourceMonitor(env)
        monitor.register_machine("machine1", machine1)

        # Sample periodically
        def sample_loop():
            while True:
                monitor.sample_all()
                yield env.timeout(1.0)  # Sample every second
        env.process(sample_loop())

        # Get statistics
        cpu_series = monitor.get_time_series("cpu_utilization", "machine1")
        avg_cpu = monitor.get_average("cpu_utilization", "machine1")
    """

    def __init__(self, env: simpy.Environment):
        """Initialize the resource monitor.

        Args:
            env: SimPy environment
        """
        self.env = env
        self.machines: Dict[str, Machine] = {}
        self.network: Optional[Network] = None
        self.samples: List[ResourceSample] = []
        self.link_samples: List[NetworkLinkSample] = []

    def register_machine(self, machine_id: str, machine: Machine):
        """Register a machine for monitoring.

        Args:
            machine_id: Unique identifier for the machine
            machine: Machine instance to monitor
        """
        self.machines[machine_id] = machine
        logger.info(f"ResourceMonitor: Registered machine {machine_id}")

    def register_network(self, network: Network):
        """Register the network for link monitoring.

        Args:
            network: Network instance to monitor
        """
        self.network = network
        logger.info("ResourceMonitor: Registered network")

    def sample_machine(self, machine_id: str) -> Optional[ResourceSample]:
        """Sample current resource usage of a machine.

        Args:
            machine_id: Machine to sample

        Returns:
            ResourceSample instance, or None if machine not registered
        """
        if machine_id not in self.machines:
            return None

        machine = self.machines[machine_id]

        sample = ResourceSample(
            timestamp=self.env.now,
            machine_id=machine_id,
            cpu_utilization=machine.get_cpu_utilization(),
            cpu_available=machine.get_available_cpu(),
        )

        # Sample disk if available
        if machine.disk:
            sample.disk_utilization = machine.disk.get_utilization()
            sample.disk_available = machine.disk.get_available_capacity()
            sample.disk_write_iops_utilization = machine.disk.get_write_iops_utilization(self.env.now)
            sample.disk_read_iops_utilization = machine.disk.get_read_iops_utilization(self.env.now)
            sample.disk_throughput_utilization = machine.disk.get_throughput_utilization(self.env.now)

        self.samples.append(sample)
        return sample

    def sample_network_links(self) -> List[NetworkLinkSample]:
        """Sample all network links.

        Returns:
            List of NetworkLinkSample instances
        """
        if not self.network:
            return []

        link_samples = []

        for (sender_id, receiver_id), link in self.network._links.items():
            sample = NetworkLinkSample(
                timestamp=self.env.now,
                link_id=link.link_id,
                sender_id=sender_id,
                receiver_id=receiver_id,
                bandwidth_utilization=link.get_bandwidth_utilization(self.env.now),
                packet_rate_utilization=link.get_packet_rate_utilization(self.env.now)
            )
            link_samples.append(sample)
            self.link_samples.append(sample)

        return link_samples

    def sample_all(self):
        """Sample all registered machines and network links."""
        for machine_id in self.machines:
            self.sample_machine(machine_id)

        if self.network:
            self.sample_network_links()

    def get_time_series(
        self,
        metric: str,
        machine_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Tuple[float, float]]:
        """Get time series data for a specific metric.

        Args:
            metric: Name of the metric (e.g., "cpu_utilization", "disk_utilization")
            machine_id: Machine to query
            start_time: Optional start time filter
            end_time: Optional end time filter

        Returns:
            List of (timestamp, value) tuples
        """
        result = []

        for sample in self.samples:
            if sample.machine_id != machine_id:
                continue

            if start_time is not None and sample.timestamp < start_time:
                continue

            if end_time is not None and sample.timestamp > end_time:
                continue

            if hasattr(sample, metric):
                result.append((sample.timestamp, getattr(sample, metric)))

        return result

    def get_link_time_series(
        self,
        metric: str,
        sender_id: str,
        receiver_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Tuple[float, float]]:
        """Get time series data for a network link metric.

        Args:
            metric: Name of the metric (e.g., "bandwidth_utilization")
            sender_id: Source node
            receiver_id: Destination node
            start_time: Optional start time filter
            end_time: Optional end time filter

        Returns:
            List of (timestamp, value) tuples
        """
        result = []

        for sample in self.link_samples:
            if sample.sender_id != sender_id or sample.receiver_id != receiver_id:
                continue

            if start_time is not None and sample.timestamp < start_time:
                continue

            if end_time is not None and sample.timestamp > end_time:
                continue

            if hasattr(sample, metric):
                result.append((sample.timestamp, getattr(sample, metric)))

        return result

    def get_average(
        self,
        metric: str,
        machine_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> Optional[float]:
        """Get average value of a metric over time.

        Args:
            metric: Name of the metric
            machine_id: Machine to query
            start_time: Optional start time filter
            end_time: Optional end time filter

        Returns:
            Average value, or None if no data
        """
        time_series = self.get_time_series(metric, machine_id, start_time, end_time)

        if not time_series:
            return None

        return sum(value for _, value in time_series) / len(time_series)

    def get_max(
        self,
        metric: str,
        machine_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> Optional[float]:
        """Get maximum value of a metric over time.

        Args:
            metric: Name of the metric
            machine_id: Machine to query
            start_time: Optional start time filter
            end_time: Optional end time filter

        Returns:
            Maximum value, or None if no data
        """
        time_series = self.get_time_series(metric, machine_id, start_time, end_time)

        if not time_series:
            return None

        return max(value for _, value in time_series)

    def get_summary(self, machine_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of resource usage for a machine.

        Args:
            machine_id: Machine to summarize

        Returns:
            Dictionary with average, max values for all metrics
        """
        if machine_id not in self.machines:
            return None

        return {
            "machine_id": machine_id,
            "cpu": {
                "avg_utilization": self.get_average("cpu_utilization", machine_id),
                "max_utilization": self.get_max("cpu_utilization", machine_id),
            },
            "disk": {
                "avg_utilization": self.get_average("disk_utilization", machine_id),
                "max_utilization": self.get_max("disk_utilization", machine_id),
                "avg_write_iops_util": self.get_average("disk_write_iops_utilization", machine_id),
                "avg_read_iops_util": self.get_average("disk_read_iops_utilization", machine_id),
                "avg_throughput_util": self.get_average("disk_throughput_utilization", machine_id),
            },
            "sample_count": len([s for s in self.samples if s.machine_id == machine_id])
        }

    def get_all_summaries(self) -> Dict[str, Dict[str, Any]]:
        """Get summaries for all registered machines.

        Returns:
            Dictionary mapping machine_id to summary
        """
        summaries = {}

        for machine_id in self.machines:
            summary = self.get_summary(machine_id)
            if summary:
                summaries[machine_id] = summary

        return summaries

    def clear_samples(self, before_time: Optional[float] = None):
        """Clear old samples to save memory.

        Args:
            before_time: Clear samples before this time. If None, clear all.
        """
        if before_time is None:
            self.samples.clear()
            self.link_samples.clear()
            logger.info("ResourceMonitor: Cleared all samples")
        else:
            self.samples = [s for s in self.samples if s.timestamp >= before_time]
            self.link_samples = [s for s in self.link_samples if s.timestamp >= before_time]
            logger.info(f"ResourceMonitor: Cleared samples before {before_time}")
