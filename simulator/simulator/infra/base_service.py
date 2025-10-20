"""Base service class for distributed system components.

This module provides a base class that encapsulates common patterns for services
in a distributed system simulation, including crash/recovery behavior and message
listening loops.

Extracted from existing patterns in GatewayNode and DataNode components.
"""

import simpy
from typing import Optional
from abc import abstractmethod
from pydantic import BaseModel

from simulator.infra.network import Network, NetworkMessage
from simulator.infra.machine import Machine

import logging
logger = logging.getLogger(__name__)


class BaseService(BaseModel):
    """Base class for all simulation services.

    Provides common functionality for:
    - Crash/recovery lifecycle management
    - Message listening loops
    - Machine failure callbacks

    Subclasses must implement:
    - _handle_message(msg: NetworkMessage) - Process received messages
    """

    id: str
    env: simpy.Environment
    network: Network
    machine: Machine
    is_crashed: bool = False
    _listen_process: Optional[simpy.Process] = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        """Initialize the base service.

        Registers callbacks with the underlying machine and starts the
        message listening process.
        """
        super().__init__(**data)
        self.network.register_node(self.id)
        self.machine.register_callbacks(self._on_machine_fail, self._on_machine_recover)
        self._listen_process = self.env.process(self._listen_for_messages())

    def crash(self):
        """Crash this service.

        Sets is_crashed flag and interrupts the message listening process.
        Extracted from GatewayNode:63-67 and DataNode:90-96.
        """
        logger.info(f"[{self.machine.get_current_time(self.env.now):.4f}] {self.__class__.__name__} {self.id} is crashing.")
        self.is_crashed = True
        if self._listen_process and self._listen_process.is_alive:
            self._listen_process.interrupt()

    def recover(self):
        """Recover this service.

        Clears is_crashed flag and restarts the message listening process.
        Extracted from GatewayNode:69-73 and DataNode:98-104.
        """
        logger.info(f"[{self.machine.get_current_time(self.env.now):.4f}] {self.__class__.__name__} {self.id} is recovering.")
        self.is_crashed = False
        if not self._listen_process or not self._listen_process.is_alive:
            self._listen_process = self.env.process(self._listen_for_messages())

    def _listen_for_messages(self):
        """Base message listening loop.

        Continuously receives messages from the network and dispatches them
        to _handle_message(). Waits when crashed, handles interrupts gracefully.

        Extracted from GatewayNode:75-91 and DataNode (similar pattern).
        """
        while True:
            if self.is_crashed:
                yield self.env.timeout(1)  # Wait if crashed
                continue
            try:
                msg: NetworkMessage = yield self.network.get_inbox(self.id).get()
            except simpy.Interrupt:
                logger.info(f"[{self.machine.get_current_time(self.env.now):.4f}] {self.__class__.__name__} {self.id} _listen_for_messages interrupted.")
                continue

            # Dispatch to subclass handler
            self._handle_message(msg)

    @abstractmethod
    def _handle_message(self, msg: NetworkMessage):
        """Handle a received message.

        Subclasses must implement this method to define how messages are processed.

        Args:
            msg: The received network message
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement _handle_message()")

    def _on_machine_fail(self, machine_id: str):
        """Callback invoked when the underlying machine fails.

        Default implementation crashes the service. Subclasses can override
        to add additional behavior (e.g., unregister from load balancer).

        Extracted from GatewayNode:51-55 and DataNode:56-71.

        Args:
            machine_id: The ID of the failed machine
        """
        logger.info(f"[{self.machine.get_current_time(self.env.now):.4f}] {self.__class__.__name__} {self.id}: Underlying machine {machine_id} failed.")
        self.crash()

    def _on_machine_recover(self, machine_id: str):
        """Callback invoked when the underlying machine recovers.

        Default implementation recovers the service. Subclasses can override
        to add additional behavior (e.g., re-register with load balancer).

        Extracted from GatewayNode:57-61 and DataNode:73-88.

        Args:
            machine_id: The ID of the recovered machine
        """
        logger.info(f"[{self.machine.get_current_time(self.env.now):.4f}] {self.__class__.__name__} {self.id}: Underlying machine {machine_id} recovered.")
        self.recover()

    # Phase 5: Resource consumption helpers

    def consume_cpu(self, amount: float, operation: str):
        """Consume CPU resources from the underlying machine.

        This is a generator that should be yielded from:
            yield from self.consume_cpu(amount, operation)

        Args:
            amount: Amount of CPU units to consume
            operation: Description of the operation (for logging/debugging)

        Yields:
            SimPy events for resource allocation and processing time
        """
        yield from self.machine.consume_cpu(self.env, amount, operation)
