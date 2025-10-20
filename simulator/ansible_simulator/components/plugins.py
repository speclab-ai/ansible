"""
Plugin Components for Ansible Simulator.

Includes:
- Connection Plugins (SSH, Local)
- Action Plugins
- Module execution logic
"""

import simpy
import random
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from simulator.infra.network import Network, NetworkMessage

from ansible_simulator.shared.models import (
    Task, ModuleResponse, ConnectionInfo
)
from ansible_simulator.components.managed_host import (
    SSHConnectionRequest, SSHConnectionResponse,
    ModuleExecutionRequest
)

import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Connection Plugins
# ============================================================================

class Connection(BaseModel):
    """Base class for connection plugins."""
    env: simpy.Environment
    network: Network
    connection_info: ConnectionInfo
    session_id: Optional[str] = None
    is_connected: bool = False

    class Config:
        arbitrary_types_allowed = True

    def connect(self):
        """Establish connection to remote host."""
        raise NotImplementedError()

    def execute_module(self, module_name: str, module_args: Dict[str, Any]):
        """Execute a module on the remote host."""
        raise NotImplementedError()

    def close(self):
        """Close the connection."""
        self.is_connected = False
        logger.info(f"[{self.env.now:.4f}] Connection to {self.connection_info.host} closed")


class SSHConnection(Connection):
    """
    SSH Connection Plugin.

    Simulates SSH connection to a managed host.
    """
    control_node_id: str = "control_node"

    def connect(self):
        """Establish SSH connection."""
        logger.info(f"[{self.env.now:.4f}] SSHConnection: Connecting to {self.connection_info.host}")

        # Create connection request
        request_id = f"ssh_conn_{self.env.now}_{random.randint(1000, 9999)}"
        request = SSHConnectionRequest(
            request_id=request_id,
            connection_info=self.connection_info
        )

        # Send to managed host
        msg = NetworkMessage(
            sender_id=self.control_node_id,
            receiver_id=self.connection_info.host,
            payload=request,
            timestamp=self.env.now
        )
        self.network.send_message(msg)

        # Wait for response
        inbox = self.network.get_inbox(self.control_node_id)

        # Simulate connection establishment time
        yield self.env.timeout(random.uniform(0.05, 0.15))

        try:
            response_msg: NetworkMessage = yield inbox.get()
            assert isinstance(response_msg.payload, SSHConnectionResponse), \
                f"Expected SSHConnectionResponse, got {type(response_msg.payload)}"
            response: SSHConnectionResponse = response_msg.payload

            if response.success:
                self.session_id = response.session_id
                self.is_connected = True
                logger.info(f"[{self.env.now:.4f}] SSHConnection: Connected to {self.connection_info.host}")
            else:
                logger.error(f"[{self.env.now:.4f}] SSHConnection: Failed to connect: {response.error}")
                raise ConnectionError(response.error)

        except simpy.Interrupt:
            logger.warning(f"[{self.env.now:.4f}] SSHConnection: Connection interrupted")
            raise

    def execute_module(self, module_name: str, module_args: Dict[str, Any]):
        """Execute a module via SSH."""
        if not self.is_connected:
            raise ConnectionError("Not connected")

        logger.info(f"[{self.env.now:.4f}] SSHConnection: Executing {module_name} on {self.connection_info.host}")

        # Create module execution request
        request_id = f"module_exec_{self.env.now}_{random.randint(1000, 9999)}"
        request = ModuleExecutionRequest(
            request_id=request_id,
            session_id=self.session_id,
            module_name=module_name,
            module_args=module_args,
            become=self.connection_info.become,
            become_user=self.connection_info.become_user
        )

        # Send to managed host
        msg = NetworkMessage(
            sender_id=self.control_node_id,
            receiver_id=self.connection_info.host,
            payload=request,
            timestamp=self.env.now
        )
        self.network.send_message(msg)

        # Wait for response
        inbox = self.network.get_inbox(self.control_node_id)

        try:
            response_msg: NetworkMessage = yield inbox.get()
            assert isinstance(response_msg.payload, ModuleResponse), \
                f"Expected ModuleResponse, got {type(response_msg.payload)}"
            module_response: ModuleResponse = response_msg.payload

            logger.info(
                f"[{self.env.now:.4f}] SSHConnection: Module {module_name} "
                f"{'failed' if module_response.failed else 'succeeded'} on {self.connection_info.host}"
            )

            return module_response

        except simpy.Interrupt:
            logger.warning(f"[{self.env.now:.4f}] SSHConnection: Module execution interrupted")
            raise


class LocalConnection(Connection):
    """
    Local Connection Plugin.

    Executes modules on the control node itself.
    """

    def connect(self):
        """Local connection is always available."""
        logger.info(f"[{self.env.now:.4f}] LocalConnection: Using local connection")
        self.is_connected = True
        yield self.env.timeout(0.001)  # Minimal delay

    def execute_module(self, module_name: str, module_args: Dict[str, Any]):
        """Execute a module locally."""
        logger.info(f"[{self.env.now:.4f}] LocalConnection: Executing {module_name} locally")

        # Simulate local execution
        yield self.env.timeout(random.uniform(0.01, 0.05))

        # Return simplified response for local execution
        return ModuleResponse(
            changed=False,
            msg=f"Local execution of {module_name}"
        )


# ============================================================================
# Action Plugins
# ============================================================================

class ActionPlugin(BaseModel):
    """
    Base Action Plugin.

    Action plugins bridge tasks to module execution, handling:
    - Connection establishment
    - Variable templating
    - File transfers
    - Module execution
    """
    env: simpy.Environment
    network: Network
    task: Task
    host_name: str
    connection_info: ConnectionInfo
    task_vars: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    def run(self):
        """Execute the action."""
        raise NotImplementedError()


class NormalActionPlugin(ActionPlugin):
    """
    Default action plugin for most modules.

    Establishes connection and executes the module.
    """

    def run(self):
        """Run the action."""
        logger.info(f"[{self.env.now:.4f}] ActionPlugin: Running task '{self.task.name}' on {self.host_name}")

        # Create connection
        connection: Connection
        if self.connection_info.connection_type == "local":
            connection = LocalConnection(
                env=self.env,
                network=self.network,
                connection_info=self.connection_info
            )
        else:
            connection = SSHConnection(
                env=self.env,
                network=self.network,
                connection_info=self.connection_info
            )

        # Establish connection
        yield from connection.connect()

        # Execute module
        result = yield from connection.execute_module(
            module_name=self.task.action,
            module_args=self.task.args
        )

        # Close connection
        connection.close()

        return result


class SetupActionPlugin(ActionPlugin):
    """
    Setup action plugin for fact gathering.

    Special handling for the setup module.
    """

    def run(self):
        """Run setup/fact gathering."""
        logger.info(f"[{self.env.now:.4f}] SetupAction: Gathering facts from {self.host_name}")

        # Create SSH connection
        connection = SSHConnection(
            env=self.env,
            network=self.network,
            connection_info=self.connection_info
        )

        # Connect
        yield from connection.connect()

        # Execute setup module
        result = yield from connection.execute_module(
            module_name="setup",
            module_args={}
        )

        connection.close()

        return result


class CopyActionPlugin(ActionPlugin):
    """
    Copy action plugin.

    Handles file transfer before executing copy module.
    """

    def run(self):
        """Run copy action with file transfer."""
        logger.info(f"[{self.env.now:.4f}] CopyAction: Copying file to {self.host_name}")

        # Simulate file transfer time
        src = self.task.args.get("src", "")
        content = self.task.args.get("content", "")

        if src:
            # Simulate reading source file and transferring
            file_size = random.uniform(100, 10000)  # bytes
            transfer_time = file_size / 1000000  # Assume 1MB/s
            yield self.env.timeout(transfer_time)

        # Create connection and execute
        connection = SSHConnection(
            env=self.env,
            network=self.network,
            connection_info=self.connection_info
        )

        yield from connection.connect()

        result = yield from connection.execute_module(
            module_name="copy",
            module_args=self.task.args
        )

        connection.close()

        return result


class TemplateActionPlugin(ActionPlugin):
    """
    Template action plugin.

    Handles Jinja2 templating and file transfer.
    """

    def run(self):
        """Run template action."""
        logger.info(f"[{self.env.now:.4f}] TemplateAction: Deploying template to {self.host_name}")

        # Simulate template rendering
        yield self.env.timeout(random.uniform(0.01, 0.05))

        # Simulate file transfer
        yield self.env.timeout(random.uniform(0.01, 0.05))

        # Create connection and execute
        connection = SSHConnection(
            env=self.env,
            network=self.network,
            connection_info=self.connection_info
        )

        yield from connection.connect()

        result = yield from connection.execute_module(
            module_name="template",
            module_args=self.task.args
        )

        connection.close()

        return result


# ============================================================================
# Action Plugin Loader
# ============================================================================

def get_action_plugin(
    env: simpy.Environment,
    network: Network,
    task: Task,
    host_name: str,
    connection_info: ConnectionInfo,
    task_vars: Dict[str, Any]
) -> ActionPlugin:
    """
    Get the appropriate action plugin for a task.

    Args:
        env: SimPy environment
        network: Network instance
        task: Task to execute
        host_name: Target host name
        connection_info: Connection information
        task_vars: Task variables

    Returns:
        ActionPlugin instance
    """
    action_name = task.action

    # Map modules to action plugins
    action_map = {
        "setup": SetupActionPlugin,
        "copy": CopyActionPlugin,
        "template": TemplateActionPlugin,
    }

    plugin_class = action_map.get(action_name, NormalActionPlugin)

    return plugin_class(
        env=env,
        network=network,
        task=task,
        host_name=host_name,
        connection_info=connection_info,
        task_vars=task_vars
    )
