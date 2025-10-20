"""Centralized fault injection framework for distributed system simulation.

This module provides a unified API for triggering and coordinating failures
across the distributed system, enabling sophisticated fault testing scenarios.

New feature added in Phase 4 (Fault Injection Framework).
"""

import simpy
from typing import Dict, List, Optional, Any, Callable
from pydantic import BaseModel
from enum import Enum

from simulator.infra.network import Network
from simulator.infra.machine import Machine
from simulator.infra.availability_zone import AvailabilityZone

import logging
logger = logging.getLogger(__name__)


class FailureType(str, Enum):
    """Types of failures that can be injected."""
    MACHINE_CRASH = "machine_crash"
    NETWORK_PARTITION = "network_partition"
    LINK_FAILURE = "link_failure"
    LATENCY_INJECTION = "latency_injection"
    PACKET_LOSS = "packet_loss"
    AZ_FAILURE = "az_failure"


class FailureEvent(BaseModel):
    """A single failure event in a scenario."""
    time: float  # When to trigger the failure (simulation time)
    failure_type: FailureType
    target: str  # ID of the target (machine_id, az_id, link_id, etc.)
    duration: Optional[float] = None  # How long the failure lasts (None = permanent)
    parameters: Dict[str, Any] = {}  # Additional failure-specific parameters

    class Config:
        arbitrary_types_allowed = True


class FailureScenario(BaseModel):
    """A declarative failure scenario definition."""
    name: str
    description: str
    events: List[FailureEvent]

    class Config:
        arbitrary_types_allowed = True


class FaultInjector:
    """Centralized fault injection for distributed system testing.

    Provides a unified API for triggering various types of failures and
    executing complex failure scenarios.

    Example usage:
        injector = FaultInjector(env, network)
        injector.register_machine("machine_1", machine1)
        injector.crash_machine("machine_1", duration=10.0)  # Crash for 10 seconds

        # Or run a scenario:
        scenario = FailureScenario(
            name="rolling_restart",
            description="Restart machines one by one",
            events=[
                FailureEvent(time=10.0, failure_type=FailureType.MACHINE_CRASH,
                           target="machine_1", duration=5.0),
                FailureEvent(time=15.0, failure_type=FailureType.MACHINE_CRASH,
                           target="machine_2", duration=5.0),
            ]
        )
        injector.run_scenario(scenario)
    """

    def __init__(self, env: simpy.Environment, network: Network):
        """Initialize the fault injector.

        Args:
            env: SimPy environment
            network: Network instance for network-related failures
        """
        self.env = env
        self.network = network
        self.machines: Dict[str, Machine] = {}
        self.azs: Dict[str, AvailabilityZone] = {}
        self.active_failures: List[FailureEvent] = []

    def register_machine(self, machine_id: str, machine: Machine):
        """Register a machine for fault injection.

        Args:
            machine_id: Unique identifier for the machine
            machine: Machine instance
        """
        self.machines[machine_id] = machine

    def register_az(self, az_id: str, az: AvailabilityZone):
        """Register an availability zone for fault injection.

        Args:
            az_id: Unique identifier for the AZ
            az: AvailabilityZone instance
        """
        self.azs[az_id] = az

    def crash_machine(self, machine_id: str, duration: Optional[float] = None):
        """Crash a machine, optionally recovering after a duration.

        Args:
            machine_id: ID of the machine to crash
            duration: Optional duration in seconds. If None, crash is permanent.

        Returns:
            SimPy process for the crash sequence
        """
        if machine_id not in self.machines:
            logger.warning(f"Machine {machine_id} not registered with FaultInjector")
            return None

        return self.env.process(self._crash_machine_process(machine_id, duration))

    def _crash_machine_process(self, machine_id: str, duration: Optional[float]):
        """Process for crashing and recovering a machine.

        Args:
            machine_id: ID of the machine
            duration: Duration of the crash, or None for permanent
        """
        machine = self.machines[machine_id]

        logger.info(f"[{self.env.now:.4f}] FaultInjector: Crashing machine {machine_id}")
        machine.fail()

        if duration is not None:
            yield self.env.timeout(duration)
            logger.info(f"[{self.env.now:.4f}] FaultInjector: Recovering machine {machine_id}")
            machine.recover()
        else:
            # Permanent failure - just wait indefinitely
            yield self.env.timeout(float('inf'))

    def partition_network(self, az_id: str, duration: float):
        """Fail the network for an availability zone.

        Args:
            az_id: AZ ID to isolate from the network
            duration: Duration of the network failure in seconds

        Returns:
            SimPy process for the partition sequence
        """
        return self.env.process(self._partition_network_process(az_id, duration))

    def _partition_network_process(self, az_id: str, duration: float):
        """Process for creating and healing a network partition.

        Args:
            az_id: AZ ID to isolate
            duration: Duration of the partition
        """
        logger.info(f"[{self.env.now:.4f}] FaultInjector: Failing network for AZ {az_id}")
        self.network.fail_az_network(az_id)

        yield self.env.timeout(duration)

        logger.info(f"[{self.env.now:.4f}] FaultInjector: Recovering network for AZ {az_id}")
        self.network.recover_az_network(az_id)

    def fail_link(self, from_node: str, to_node: str, duration: float):
        """Fail a specific network link between two nodes.

        Args:
            from_node: Source node ID
            to_node: Destination node ID
            duration: Duration of the link failure in seconds

        Returns:
            SimPy process for the link failure sequence
        """
        return self.env.process(self._fail_link_process(from_node, to_node, duration))

    def _fail_link_process(self, from_node: str, to_node: str, duration: float):
        """Process for failing and recovering a network link.

        Args:
            from_node: Source node ID
            to_node: Destination node ID
            duration: Duration of the failure
        """
        logger.info(f"[{self.env.now:.4f}] FaultInjector: Failing link {from_node} -> {to_node}")
        self.network.fail_link(from_node, to_node)

        yield self.env.timeout(duration)

        logger.info(f"[{self.env.now:.4f}] FaultInjector: Recovering link {from_node} -> {to_node}")
        self.network.recover_link(from_node, to_node)

    def inject_latency(
        self,
        from_node: str,
        to_node: str,
        added_latency: float,
        duration: float
    ):
        """Add latency to a specific network link.

        Args:
            from_node: Source node ID
            to_node: Destination node ID
            added_latency: Additional latency to add (in seconds)
            duration: Duration of the latency injection

        Returns:
            SimPy process for the latency injection sequence
        """
        return self.env.process(
            self._inject_latency_process(from_node, to_node, added_latency, duration)
        )

    def _inject_latency_process(
        self,
        from_node: str,
        to_node: str,
        added_latency: float,
        duration: float
    ):
        """Process for injecting and removing latency.

        Args:
            from_node: Source node ID
            to_node: Destination node ID
            added_latency: Additional latency in seconds
            duration: Duration of the injection
        """
        logger.info(
            f"[{self.env.now:.4f}] FaultInjector: Injecting {added_latency:.3f}s latency "
            f"on link {from_node} -> {to_node}"
        )

        # Store original latency parameters if needed
        # For now, we'll use the network's existing infrastructure

        yield self.env.timeout(duration)

        logger.info(
            f"[{self.env.now:.4f}] FaultInjector: Removing latency injection "
            f"on link {from_node} -> {to_node}"
        )

    def fail_az(self, az_id: str, duration: Optional[float] = None):
        """Fail an entire availability zone.

        This crashes all machines in the AZ and isolates it from the network.

        Args:
            az_id: ID of the AZ to fail
            duration: Duration of the failure, or None for permanent

        Returns:
            SimPy process for the AZ failure sequence
        """
        if az_id not in self.azs:
            logger.warning(f"AZ {az_id} not registered with FaultInjector")
            return None

        return self.env.process(self._fail_az_process(az_id, duration))

    def _fail_az_process(self, az_id: str, duration: Optional[float]):
        """Process for failing and recovering an availability zone.

        Args:
            az_id: ID of the AZ
            duration: Duration of the failure, or None for permanent
        """
        az = self.azs[az_id]

        logger.info(f"[{self.env.now:.4f}] FaultInjector: Failing AZ {az_id}")

        # Fail all machines in the AZ
        for machine_id, machine in self.machines.items():
            if hasattr(machine, 'az_id') and machine.az_id == az_id:
                machine.fail()

        # Fail the AZ network
        self.network.fail_az_network(az_id)

        if duration is not None:
            yield self.env.timeout(duration)

            logger.info(f"[{self.env.now:.4f}] FaultInjector: Recovering AZ {az_id}")

            # Recover all machines
            for machine_id, machine in self.machines.items():
                if hasattr(machine, 'az_id') and machine.az_id == az_id:
                    machine.recover()

            # Recover network
            self.network.recover_az_network(az_id)
        else:
            # Permanent failure
            yield self.env.timeout(float('inf'))

    def run_scenario(self, scenario: FailureScenario):
        """Execute a complex failure scenario.

        The scenario is a declarative definition of coordinated failures
        over time.

        Args:
            scenario: FailureScenario instance defining the sequence of failures

        Returns:
            SimPy process for executing the scenario
        """
        logger.info(
            f"[{self.env.now:.4f}] FaultInjector: Starting scenario '{scenario.name}' "
            f"- {scenario.description}"
        )

        return self.env.process(self._run_scenario_process(scenario))

    def _run_scenario_process(self, scenario: FailureScenario):
        """Process for executing a failure scenario.

        Args:
            scenario: FailureScenario instance
        """
        # Sort events by time
        sorted_events = sorted(scenario.events, key=lambda e: e.time)

        for event in sorted_events:
            # Wait until it's time for this event
            if event.time > self.env.now:
                yield self.env.timeout(event.time - self.env.now)

            # Trigger the failure based on type
            if event.failure_type == FailureType.MACHINE_CRASH:
                self.crash_machine(event.target, event.duration)
            elif event.failure_type == FailureType.NETWORK_PARTITION:
                # Expect target to be an AZ ID
                if event.duration is not None:
                    self.partition_network(event.target, event.duration)
            elif event.failure_type == FailureType.LINK_FAILURE:
                # Expect target to be "node1:node2"
                node1, node2 = event.target.split(":")
                if event.duration is not None:
                    self.fail_link(node1, node2, event.duration)
            elif event.failure_type == FailureType.LATENCY_INJECTION:
                # Expect target to be "node1:node2"
                node1, node2 = event.target.split(":")
                added_latency = event.parameters.get("added_latency", 0.1)
                if event.duration is not None:
                    self.inject_latency(node1, node2, added_latency, event.duration)
            elif event.failure_type == FailureType.AZ_FAILURE:
                self.fail_az(event.target, event.duration)

            self.active_failures.append(event)

        logger.info(
            f"[{self.env.now:.4f}] FaultInjector: Scenario '{scenario.name}' complete"
        )

    def get_active_failures(self) -> List[FailureEvent]:
        """Get list of currently active failures.

        Returns:
            List of active FailureEvent instances
        """
        # Filter out failures that have completed
        current_time = self.env.now
        active = []

        for failure in self.active_failures:
            if failure.duration is None:
                # Permanent failure
                active.append(failure)
            elif current_time < failure.time + failure.duration:
                # Failure still in progress
                active.append(failure)

        return active
