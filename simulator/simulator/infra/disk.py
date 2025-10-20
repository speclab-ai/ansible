"""Disk resource modeling for distributed system simulation.

This module provides realistic disk constraints including capacity, throughput,
and IOPS limits for accurate storage system simulation.

New feature added in Phase 5 (Resource Modeling).
"""

import simpy
from typing import List, Tuple, Optional
from pydantic import BaseModel

import logging
logger = logging.getLogger(__name__)


class DiskFullError(Exception):
    """Raised when disk capacity is exhausted."""
    pass


class DiskResource(BaseModel):
    """Represents a disk with capacity and performance limits.

    Models three key disk constraints:
    1. Capacity - Total bytes available
    2. Throughput - Bytes per second (read/write bandwidth)
    3. IOPS - Operations per second (I/O operations)

    Example usage:
        disk = DiskResource(
            capacity=1_000_000_000,  # 1 GB
            throughput_limit=100_000_000,  # 100 MB/s
            read_iops_limit=1000,
            write_iops_limit=500
        )

        # Write data
        yield from disk.write(env, data_size=1024)

        # Read data
        yield from disk.read(env, data_size=1024)
    """

    capacity: float  # Total bytes
    used: float = 0.0  # Current usage in bytes
    throughput_limit: float = 100_000_000  # 100 MB/s default
    read_iops_limit: float = 1000  # ops/sec
    write_iops_limit: float = 500  # ops/sec

    # Internal tracking windows (not part of initialization)
    _throughput_window: List[Tuple[float, float]] = []  # (timestamp, bytes)
    _read_iops_window: List[float] = []  # timestamps of read operations
    _write_iops_window: List[float] = []  # timestamps of write operations
    _window_duration: float = 1.0  # 1 second window for rate limiting

    class Config:
        arbitrary_types_allowed = True

    def write(self, env: simpy.Environment, data_size: float):
        """Write data to disk, respecting capacity, throughput, and IOPS limits.

        This is a generator that should be yielded from:
            yield from disk.write(env, data_size)

        Args:
            env: SimPy environment
            data_size: Size of data to write in bytes

        Raises:
            DiskFullError: If disk capacity would be exceeded

        Yields:
            SimPy events for waiting on resources and I/O completion
        """
        # Check capacity
        if self.used + data_size > self.capacity:
            raise DiskFullError(
                f"Disk full: {self.used}/{self.capacity} bytes used, "
                f"cannot write {data_size} bytes"
            )

        # Wait for write IOPS availability
        yield from self._wait_for_write_iops(env)

        # Wait for throughput availability
        yield from self._wait_for_throughput(env, data_size)

        # Perform write (simulate latency based on throughput)
        write_latency = data_size / self.throughput_limit
        yield env.timeout(write_latency)

        # Update disk usage
        self.used += data_size
        self._record_throughput(env.now, data_size)

    def read(self, env: simpy.Environment, data_size: float):
        """Read data from disk, respecting throughput and IOPS limits.

        This is a generator that should be yielded from:
            yield from disk.read(env, data_size)

        Args:
            env: SimPy environment
            data_size: Size of data to read in bytes

        Yields:
            SimPy events for waiting on resources and I/O completion
        """
        # Wait for read IOPS availability
        yield from self._wait_for_read_iops(env)

        # Wait for throughput availability
        yield from self._wait_for_throughput(env, data_size)

        # Perform read (simulate latency based on throughput)
        read_latency = data_size / self.throughput_limit
        yield env.timeout(read_latency)

        self._record_throughput(env.now, data_size)

    def delete(self, data_size: float):
        """Delete data from disk, freeing up capacity.

        This is synchronous (no I/O delay) as it just updates metadata.

        Args:
            data_size: Size of data to free in bytes
        """
        self.used = max(0, self.used - data_size)

    def _wait_for_write_iops(self, env: simpy.Environment):
        """Wait until write IOPS capacity is available.

        Args:
            env: SimPy environment

        Yields:
            SimPy timeout events while waiting for IOPS availability
        """
        while True:
            # Clean old entries from window
            self._clean_window(env.now, self._write_iops_window)

            # Check if we can perform the operation
            if len(self._write_iops_window) < self.write_iops_limit:
                # Record this operation
                self._write_iops_window.append(env.now)
                return
            else:
                # Wait a bit and try again
                yield env.timeout(0.001)  # 1ms

    def _wait_for_read_iops(self, env: simpy.Environment):
        """Wait until read IOPS capacity is available.

        Args:
            env: SimPy environment

        Yields:
            SimPy timeout events while waiting for IOPS availability
        """
        while True:
            # Clean old entries from window
            self._clean_window(env.now, self._read_iops_window)

            # Check if we can perform the operation
            if len(self._read_iops_window) < self.read_iops_limit:
                # Record this operation
                self._read_iops_window.append(env.now)
                return
            else:
                # Wait a bit and try again
                yield env.timeout(0.001)  # 1ms

    def _wait_for_throughput(self, env: simpy.Environment, data_size: float):
        """Wait until throughput capacity is available.

        Args:
            env: SimPy environment
            data_size: Size of data for this operation

        Yields:
            SimPy timeout events while waiting for throughput availability
        """
        while True:
            # Clean old entries from window
            self._clean_throughput_window(env.now)

            # Calculate current throughput usage
            current_throughput = sum(size for _, size in self._throughput_window)

            # Check if we have capacity for this operation
            if current_throughput + data_size <= self.throughput_limit * self._window_duration:
                return
            else:
                # Wait a bit and try again
                yield env.timeout(0.001)  # 1ms

    def _record_throughput(self, timestamp: float, data_size: float):
        """Record a throughput operation.

        Args:
            timestamp: When the operation occurred
            data_size: Size of the operation in bytes
        """
        self._throughput_window.append((timestamp, data_size))

    def _clean_window(self, current_time: float, window: List[float]):
        """Remove old entries from a timestamp window.

        Args:
            current_time: Current simulation time
            window: List of timestamps to clean
        """
        cutoff_time = current_time - self._window_duration
        # Remove entries older than the window
        while window and window[0] < cutoff_time:
            window.pop(0)

    def _clean_throughput_window(self, current_time: float):
        """Remove old entries from the throughput window.

        Args:
            current_time: Current simulation time
        """
        cutoff_time = current_time - self._window_duration
        # Remove entries older than the window
        while self._throughput_window and self._throughput_window[0][0] < cutoff_time:
            self._throughput_window.pop(0)

    def get_utilization(self) -> float:
        """Get current disk capacity utilization as a percentage.

        Returns:
            Utilization percentage (0-100)
        """
        return (self.used / self.capacity) * 100 if self.capacity > 0 else 0

    def get_available_capacity(self) -> float:
        """Get remaining disk capacity.

        Returns:
            Available bytes
        """
        return self.capacity - self.used

    def get_write_iops_utilization(self, current_time: float) -> float:
        """Get current write IOPS utilization as a percentage.

        Args:
            current_time: Current simulation time

        Returns:
            Utilization percentage (0-100)
        """
        self._clean_window(current_time, self._write_iops_window)
        return (len(self._write_iops_window) / self.write_iops_limit) * 100

    def get_read_iops_utilization(self, current_time: float) -> float:
        """Get current read IOPS utilization as a percentage.

        Args:
            current_time: Current simulation time

        Returns:
            Utilization percentage (0-100)
        """
        self._clean_window(current_time, self._read_iops_window)
        return (len(self._read_iops_window) / self.read_iops_limit) * 100

    def get_throughput_utilization(self, current_time: float) -> float:
        """Get current throughput utilization as a percentage.

        Args:
            current_time: Current simulation time

        Returns:
            Utilization percentage (0-100)
        """
        self._clean_throughput_window(current_time)
        current_throughput = sum(size for _, size in self._throughput_window)
        max_throughput = self.throughput_limit * self._window_duration
        return (current_throughput / max_throughput) * 100 if max_throughput > 0 else 0
