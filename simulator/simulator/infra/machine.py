from typing import Callable, Optional
from pydantic import BaseModel
import simpy

from simulator.infra.disk import DiskResource

import logging
logger = logging.getLogger(__name__)


class Machine(BaseModel):
    """Machine abstraction with resource constraints.

    Models physical machine with:
    - Failure/recovery lifecycle
    - Clock skew simulation
    - CPU capacity (Phase 5)
    - Optional disk resource (Phase 5)
    """

    id: str
    az: str
    is_up: bool = True
    _on_fail_callback: Optional[Callable[[str], None]] = None
    _on_recover_callback: Optional[Callable[[str], None]] = None
    current_skew: float = 0.0  # Current clock skew in seconds

    # Phase 5: Resource modeling
    cpu_capacity: float = 100.0  # CPU units (normalized cores * clock speed)
    _cpu_container: Optional[simpy.Container] = None  # SimPy container for CPU allocation
    disk: Optional[DiskResource] = None  # Optional disk resource

    class Config:
        arbitrary_types_allowed = True

    def register_callbacks(self, on_fail: Callable[[str], None], on_recover: Callable[[str], None]):
        self._on_fail_callback = on_fail
        self._on_recover_callback = on_recover

    def fail(self):
        if self.is_up:
            self.is_up = False
            logger.info(f"Machine {self.id} in AZ {self.az} failed.")
            if self._on_fail_callback:
                self._on_fail_callback(self.id)

    def recover(self):
        if not self.is_up:
            self.is_up = True
            logger.info(f"Machine {self.id} in AZ {self.az} recovered.")
            if self._on_recover_callback:
                self._on_recover_callback(self.id)

    def introduce_skew(self, amount: float):
        self.current_skew = amount
        logger.info(f"Machine {self.id} in AZ {self.az}: Clock skewed by {amount:.4f}s.")

    def remove_skew(self):
        self.current_skew = 0.0
        logger.info(f"Machine {self.id} in AZ {self.az}: Clock skew removed.")

    def get_current_time(self, env_now: float) -> float:
        return env_now + self.current_skew

    # Phase 5: CPU resource management

    def init_cpu_container(self, env: simpy.Environment):
        """Initialize the CPU resource container.

        Must be called with a SimPy environment to enable CPU resource modeling.

        Args:
            env: SimPy environment
        """
        if self._cpu_container is None:
            self._cpu_container = simpy.Container(env, capacity=self.cpu_capacity, init=self.cpu_capacity)
            logger.info(f"Machine {self.id}: Initialized CPU container with capacity {self.cpu_capacity}")

    def consume_cpu(self, env: simpy.Environment, amount: float, operation: str):
        """Consume CPU resources for an operation.

        This is a generator that should be yielded from:
            yield from machine.consume_cpu(env, amount, operation)

        Args:
            env: SimPy environment
            amount: Amount of CPU units to consume
            operation: Description of the operation (for logging)

        Yields:
            SimPy events for resource allocation and processing time
        """
        if self._cpu_container is None:
            # CPU modeling not enabled, just simulate processing time
            processing_time = amount / self.cpu_capacity
            yield env.timeout(processing_time)
            return

        # Request CPU resources
        yield self._cpu_container.get(amount)

        # Simulate processing time based on CPU amount
        processing_time = amount / self.cpu_capacity
        yield env.timeout(processing_time)

        # Release CPU resources
        yield self._cpu_container.put(amount)

    def get_cpu_utilization(self) -> float:
        """Get current CPU utilization as a percentage.

        Returns:
            CPU utilization percentage (0-100), or 0 if CPU modeling not enabled
        """
        if self._cpu_container is None:
            return 0.0

        available = self._cpu_container.level
        used = self.cpu_capacity - available
        return (used / self.cpu_capacity) * 100 if self.cpu_capacity > 0 else 0

    def get_available_cpu(self) -> float:
        """Get available CPU units.

        Returns:
            Available CPU units, or full capacity if CPU modeling not enabled
        """
        if self._cpu_container is None:
            return self.cpu_capacity

        return self._cpu_container.level