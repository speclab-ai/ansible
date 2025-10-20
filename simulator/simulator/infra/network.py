import simpy
import random
from typing import Dict, List, Tuple, Optional, Set
from pydantic import BaseModel

from simulator.infra.request_context import RequestContext
from simulator.models.api import Request, Response

import logging
logger = logging.getLogger(__name__)


class Message(BaseModel):
    """Base message class for component communication.

    Moved from models/internal.py to infra as it's a generic concept.
    """
    sender_id: str
    receiver_id: str
    payload: BaseModel
    timestamp: float


class NetworkMessage(Message):
    """Network message with latency and delivery tracking.

    Extends Message with network-specific attributes for simulation.
    Moved from models/internal.py:54-57 to infra/network.py.

    Phase 5: Added size field for bandwidth modeling.
    """
    latency: float = 0.0
    dropped: bool = False
    request_context: Optional[RequestContext] = None
    size: float = 100.0  # Message size in bytes (Phase 5)


class NetworkLink(BaseModel):
    """Represents a network link with bandwidth and packet rate limits.

    Phase 5: Network resource modeling for realistic congestion simulation.
    """
    link_id: str
    bandwidth_limit: float = 125_000_000  # 125 MB/s (1 Gbps) default
    packet_rate_limit: float = 10_000  # 10k packets/sec default
    queue_depth_limit: int = 1000  # Max queued messages

    # Internal tracking
    _bandwidth_window: List[Tuple[float, float]] = []  # (timestamp, bytes)
    _packet_window: List[float] = []  # timestamps
    _window_duration: float = 1.0  # 1 second window

    class Config:
        arbitrary_types_allowed = True

    def can_send(self, current_time: float, message_size: float) -> bool:
        """Check if message can be sent within limits.

        Args:
            current_time: Current simulation time
            message_size: Size of message in bytes

        Returns:
            True if both bandwidth and packet rate allow sending
        """
        self._clean_windows(current_time)

        # Check packet rate
        if len(self._packet_window) >= self.packet_rate_limit:
            return False

        # Check bandwidth
        current_bandwidth = sum(size for _, size in self._bandwidth_window)
        if current_bandwidth + message_size > self.bandwidth_limit * self._window_duration:
            return False

        return True

    def record_transmission(self, timestamp: float, message_size: float):
        """Record a message transmission.

        Args:
            timestamp: When the message was sent
            message_size: Size of the message in bytes
        """
        self._packet_window.append(timestamp)
        self._bandwidth_window.append((timestamp, message_size))

    def _clean_windows(self, current_time: float):
        """Remove old entries from tracking windows.

        Args:
            current_time: Current simulation time
        """
        cutoff_time = current_time - self._window_duration

        # Clean packet window
        while self._packet_window and self._packet_window[0] < cutoff_time:
            self._packet_window.pop(0)

        # Clean bandwidth window
        while self._bandwidth_window and self._bandwidth_window[0][0] < cutoff_time:
            self._bandwidth_window.pop(0)

    def get_bandwidth_utilization(self, current_time: float) -> float:
        """Get current bandwidth utilization percentage.

        Args:
            current_time: Current simulation time

        Returns:
            Utilization percentage (0-100)
        """
        self._clean_windows(current_time)
        current_bandwidth = sum(size for _, size in self._bandwidth_window)
        max_bandwidth = self.bandwidth_limit * self._window_duration
        return (current_bandwidth / max_bandwidth) * 100 if max_bandwidth > 0 else 0

    def get_packet_rate_utilization(self, current_time: float) -> float:
        """Get current packet rate utilization percentage.

        Args:
            current_time: Current simulation time

        Returns:
            Utilization percentage (0-100)
        """
        self._clean_windows(current_time)
        return (len(self._packet_window) / self.packet_rate_limit) * 100


class Network:
    def __init__(self, env: simpy.Environment, latency_mean: float = 0.05, latency_std: float = 0.01, drop_rate: float = 0.0):
        self.env = env
        self.latency_mean = latency_mean  # Mean latency in seconds
        self.latency_std = latency_std    # Standard deviation of latency
        self.drop_rate = drop_rate        # Probability of dropping a message
        self.nodes: Dict[str, simpy.Store] = {}
        self.request_timings: Dict[str, List[Tuple[float, str, str]]] = {}
        self._failed_links: Set[Tuple[str, str]] = set() # Stores (sender_id, receiver_id) for failed links
        self._failed_azs: Set[str] = set() # Stores az_id for failed AZs
        self._node_az_map: Dict[str, str] = {}

        # Phase 5: Network bandwidth modeling
        self._links: Dict[Tuple[str, str], NetworkLink] = {}  # (sender, receiver) -> link
        self.enable_bandwidth_limits: bool = False  # Opt-in for bandwidth modeling

    def register_node(self, node_id: str, az_id: Optional[str] = None):
        self.nodes[node_id] = simpy.Store(self.env)
        if az_id:
            self._node_az_map[node_id] = az_id
        self.nodes[node_id] = simpy.Store(self.env)

    def unregister_node(self, node_id: str):
        if node_id in self.nodes:
            del self.nodes[node_id]

    def _record_event(self, request_id: str, event_type: str, node_id: str):
        if request_id not in self.request_timings:
            self.request_timings[request_id] = []
        self.request_timings[request_id].append((self.env.now, event_type, node_id))

    def _calculate_latency(self) -> float:
        # Simulate a normal distribution for latency, ensuring it's non-negative
        latency = random.gauss(self.latency_mean, self.latency_std)
        return max(0.001, latency)  # Minimum latency of 1ms

    # Phase 5: Message sizing and bandwidth management

    def _calculate_message_size(self, payload: BaseModel) -> float:
        """Calculate message size based on payload type.

        Estimates message size including headers and payload data.

        Args:
            payload: Message payload

        Returns:
            Estimated message size in bytes
        """
        # Try to get specific sizes for known types
        payload_type = type(payload).__name__

        # Base overhead (headers, metadata)
        base_size = 100.0

        # Estimate based on payload type
        if hasattr(payload, 'key') and hasattr(payload, 'value'):
            # Requests/responses with key-value data (PutRequest, GetResponse, etc.)
            key_size = len(str(payload.key).encode('utf-8')) if hasattr(payload, 'key') else 0
            value_size = len(str(payload.value).encode('utf-8')) if hasattr(payload, 'value') else 0
            return base_size + key_size + value_size
        elif hasattr(payload, 'key'):
            # Requests with only key (GetRequest, DeleteRequest)
            key_size = len(str(payload.key).encode('utf-8'))
            return base_size + key_size
        else:
            # Control plane messages, responses without data
            return base_size

    def _get_or_create_link(self, sender_id: str, receiver_id: str) -> NetworkLink:
        """Get or create a network link between two nodes.

        Args:
            sender_id: Source node ID
            receiver_id: Destination node ID

        Returns:
            NetworkLink instance for this connection
        """
        link_key = (sender_id, receiver_id)

        if link_key not in self._links:
            # Create a new link with default parameters
            self._links[link_key] = NetworkLink(
                link_id=f"{sender_id}->{receiver_id}",
                bandwidth_limit=125_000_000,  # 1 Gbps
                packet_rate_limit=10_000
            )

        return self._links[link_key]

    def send_message(self, message: NetworkMessage):
        # Check for link failure
        if (message.sender_id, message.receiver_id) in self._failed_links:
            logger.info(f"[{self.env.now:.4f}] Network: Message from {message.sender_id} to {message.receiver_id} dropped due to link failure.")
            message.dropped = True
            if message.request_context:
                self._record_event(message.request_context.request_id, "dropped_link_failure", message.sender_id)
            return

        # Check for AZ network failure
        sender_az = self._node_az_map.get(message.sender_id)
        receiver_az = self._node_az_map.get(message.receiver_id)

        if sender_az and sender_az in self._failed_azs:
            logger.info(f"[{self.env.now:.4f}] Network: Message from {message.sender_id} to {message.receiver_id} dropped due to sender AZ ({sender_az}) network failure.")
            message.dropped = True
            if message.request_context:
                self._record_event(message.request_context.request_id, "dropped_sender_az_failure", message.sender_id)
            return

        if receiver_az and receiver_az in self._failed_azs:
            logger.info(f"[{self.env.now:.4f}] Network: Message from {message.sender_id} to {message.receiver_id} dropped due to receiver AZ ({receiver_az}) network failure.")
            message.dropped = True
            if message.request_context:
                self._record_event(message.request_context.request_id, "dropped_receiver_az_failure", message.sender_id)
            return

        if message.receiver_id not in self.nodes:
            logger.info(f"[{self.env.now:.4f}] Network: Receiver {message.receiver_id} not registered. Message dropped.")
            if message.request_context:
                self._record_event(message.request_context.request_id, "dropped_unregistered", message.sender_id)
            return

        if random.random() < self.drop_rate:
            logger.info(f"[{self.env.now:.4f}] Network: Message from {message.sender_id} to {message.receiver_id} dropped.")
            message.dropped = True
            if message.request_context:
                self._record_event(message.request_context.request_id, "dropped_random", message.sender_id)
            return

        # Phase 5: Calculate message size
        message.size = self._calculate_message_size(message.payload)

        # Phase 5: Check bandwidth limits if enabled
        if self.enable_bandwidth_limits:
            link = self._get_or_create_link(message.sender_id, message.receiver_id)

            # Check if we can send (bandwidth/packet rate limits)
            if not link.can_send(self.env.now, message.size):
                # For now, drop the message due to congestion
                # Future: could implement queuing
                logger.warning(
                    f"[{self.env.now:.4f}] Network: Message from {message.sender_id} to {message.receiver_id} "
                    f"dropped due to network congestion (bandwidth or packet rate limit exceeded)"
                )
                message.dropped = True
                if message.request_context:
                    self._record_event(message.request_context.request_id, "dropped_congestion", message.sender_id)
                return

            # Record transmission for bandwidth tracking
            link.record_transmission(self.env.now, message.size)

        latency = self._calculate_latency()

        # Phase 5: Add transmission delay based on bandwidth
        if self.enable_bandwidth_limits:
            link = self._get_or_create_link(message.sender_id, message.receiver_id)
            transmission_delay = message.size / link.bandwidth_limit
            latency += transmission_delay

        message.latency = latency

        if isinstance(message.payload, (Request, Response)):
            message.request_context = RequestContext(request_id=message.payload.request_id)
        
        if message.request_context:
            self._record_event(message.request_context.request_id, "sent", message.sender_id)

        self.env.process(self._deliver_message(message, latency))

    def _deliver_message(self, message: NetworkMessage, delay: float):
        yield self.env.timeout(delay)
        if message.receiver_id in self.nodes:
            if message.request_context:
                self._record_event(message.request_context.request_id, "received", message.receiver_id)

            # Deep copy the message to simulate serialization/deserialization over the network
            # In a real network, objects are serialized to bytes and deserialized on the other end,
            # creating new object instances. We simulate this with a deep copy.
            delivered_message = message.model_copy(deep=True)

            yield self.nodes[message.receiver_id].put(delivered_message)
        else:
            logger.info(f"[{self.env.now:.4f}] Network: Receiver {message.receiver_id} unregistered during delivery. Message dropped.")
            if message.request_context:
                self._record_event(message.request_context.request_id, "dropped_unregistered_delivery", message.receiver_id)

    def get_inbox(self, node_id: str) -> simpy.Store:
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not registered with the network.")
        return self.nodes[node_id]

    def get_request_timings(self, request_id: str) -> Optional[List[Tuple[float, str, str]]]:
        return self.request_timings.get(request_id)

    def set_network_conditions(self, latency_mean: Optional[float] = None, latency_std: Optional[float] = None, drop_rate: Optional[float] = None):
        if latency_mean is not None:
            self.latency_mean = latency_mean
        if latency_std is not None:
            self.latency_std = latency_std
        if drop_rate is not None:
            self.drop_rate = drop_rate
        logger.info(f"[{self.env.now:.4f}] Network conditions updated: mean_latency={self.latency_mean:.4f}, std_latency={self.latency_std:.4f}, drop_rate={self.drop_rate:.2f}")

    def fail_link(self, sender_id: str, receiver_id: str):
        self._failed_links.add((sender_id, receiver_id))
        logger.info(f"[{self.env.now:.4f}] Network: Link failed between {sender_id} and {receiver_id}")

    def recover_link(self, sender_id: str, receiver_id: str):
        if (sender_id, receiver_id) in self._failed_links:
            self._failed_links.remove((sender_id, receiver_id))
            logger.info(f"[{self.env.now:.4f}] Network: Link recovered between {sender_id} and {receiver_id}")

    def fail_az_network(self, az_id: str):
        self._failed_azs.add(az_id)
        logger.info(f"[{self.env.now:.4f}] Network: AZ network failed for {az_id}")

    def recover_az_network(self, az_id: str):
        if az_id in self._failed_azs:
            self._failed_azs.remove(az_id)
            logger.info(f"[{self.env.now:.4f}] Network: AZ network recovered for {az_id}")