"""
Control Node Component for Ansible Simulator.

The control node is where Ansible runs and provides all user-facing APIs:
- ansible-playbook: Run playbooks
- ansible: Run ad-hoc commands
- ansible-inventory: Manage inventory
- ansible-vault: Encryption (simulated)
- ansible-galaxy: Collection/role management (simulated)
- ansible-config: Configuration management (simulated)
"""

import simpy
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from simulator.infra.base_service import BaseService
from simulator.infra.network import Network, NetworkMessage
from simulator.infra.machine import Machine

from ansible_simulator.shared.models import (
    Playbook, Play, Task, Inventory, PlaybookStats, PlayStats,
    AdhocCommandRequest, AdhocCommandResponse,
    PlaybookRunRequest, PlaybookRunResponse,
    InventoryListRequest, InventoryListResponse,
    TaskResult
)
from ansible_simulator.components.strategy import TaskQueueManager

import logging
logger = logging.getLogger(__name__)


class PlaybookExecutor(BaseModel):
    """
    Playbook Executor.

    Orchestrates execution of playbooks, iterating through plays
    and delegating to TaskQueueManager.

    Mirrors lib/ansible/executor/playbook_executor.py
    """
    env: simpy.Environment
    network: Network
    playbook: Playbook
    inventory: Inventory
    extra_vars: Dict[str, Any] = Field(default_factory=dict)
    forks: int = 5

    class Config:
        arbitrary_types_allowed = True

    def run(self):
        """
        Execute the playbook.

        Flow:
        1. Load playbook
        2. For each play:
           a. Create TaskQueueManager
           b. Run play with appropriate strategy
           c. Collect stats
        3. Aggregate results
        """
        logger.info(f"[{self.env.now:.4f}] PlaybookExecutor: Starting playbook execution")

        start_time = self.env.now

        # Initialize stats
        stats = PlaybookStats()
        stats.total_plays = len(self.playbook.plays)

        # Execute each play
        for play in self.playbook.plays:
            logger.info(f"[{self.env.now:.4f}] PlaybookExecutor: Running play '{play.name}'")

            # Apply extra vars to play
            play_vars = dict(play.vars)
            play_vars.update(self.extra_vars)
            play.vars = play_vars

            # Create TaskQueueManager
            tqm = TaskQueueManager(
                env=self.env,
                network=self.network,
                inventory=self.inventory,
                forks=self.forks
            )

            # Run play with strategy
            play_stats = yield from tqm.run_play(play, strategy_name=play.strategy)

            # Add to overall stats
            stats.play_stats.append(play_stats)
            stats.total_tasks += play_stats.total_tasks

        # Calculate duration
        stats.duration = self.env.now - start_time

        # Build host summary
        for play_stat in stats.play_stats:
            # Simplified host summary aggregation
            pass

        logger.info(
            f"[{self.env.now:.4f}] PlaybookExecutor: Playbook completed - "
            f"plays={stats.total_plays}, tasks={stats.total_tasks}, duration={stats.duration:.3f}s"
        )

        return stats


class ControlNode(BaseService):
    """
    Ansible Control Node.

    The main Ansible control machine that provides all user-facing APIs
    and orchestrates playbook/command execution across managed hosts.

    This component simulates:
    - ansible-playbook CLI
    - ansible CLI (ad-hoc commands)
    - ansible-inventory CLI
    - ansible-vault CLI (simulated)
    - ansible-galaxy CLI (simulated)
    - ansible-config CLI (simulated)
    """

    # Inventory
    inventory: Inventory = Field(default_factory=Inventory)

    # Configuration
    forks: int = 5
    gathering: str = "implicit"  # implicit, explicit, smart

    # Stats tracking
    playbook_runs: int = 0
    adhoc_commands: int = 0
    total_tasks_executed: int = 0

    def __init__(self, **data):
        """Initialize the control node."""
        # Initialize BaseModel (skip BaseService functionality since
        # control node doesn't listen for messages in the same way)
        super().__init__(**data)
        self.network.register_node(self.id)

    def _handle_message(self, msg: NetworkMessage):
        """Handle incoming API requests."""
        if isinstance(msg.payload, PlaybookRunRequest):
            self.env.process(self._handle_playbook_run(msg))
        elif isinstance(msg.payload, AdhocCommandRequest):
            self.env.process(self._handle_adhoc_command(msg))
        elif isinstance(msg.payload, InventoryListRequest):
            self._handle_inventory_list(msg)

    # ========================================================================
    # ansible-playbook API
    # ========================================================================

    def _handle_playbook_run(self, msg: NetworkMessage):
        """Handle playbook run request."""
        assert isinstance(msg.payload, PlaybookRunRequest), \
            f"Expected PlaybookRunRequest, got {type(msg.payload)}"
        request: PlaybookRunRequest = msg.payload

        logger.info(
            f"[{self.env.now:.4f}] ControlNode: Running playbook "
            f"(request_id={request.request_id})"
        )

        self.playbook_runs += 1

        try:
            # Use provided inventory or default
            inventory = request.inventory or self.inventory

            # Create playbook executor
            executor = PlaybookExecutor(
                env=self.env,
                network=self.network,
                playbook=request.playbook,
                inventory=inventory,
                extra_vars=request.extra_vars,
                forks=request.forks
            )

            # Run playbook
            stats = yield from executor.run()

            self.total_tasks_executed += stats.total_tasks

            # Send response
            response = PlaybookRunResponse(
                request_id=request.request_id,
                stats=stats,
                success=True
            )

        except Exception as e:
            logger.error(f"[{self.env.now:.4f}] ControlNode: Playbook execution failed: {e}")
            response = PlaybookRunResponse(
                request_id=request.request_id,
                stats=PlaybookStats(),
                success=False,
                error=str(e)
            )

        # Send response
        response_msg = NetworkMessage(
            sender_id=self.id,
            receiver_id=msg.sender_id,
            payload=response,
            timestamp=self.env.now
        )
        self.network.send_message(response_msg)

    def ansible_playbook(self, playbook: Playbook, inventory: Optional[Inventory] = None,
                        extra_vars: Optional[Dict[str, Any]] = None, forks: int = 5):
        """
        ansible-playbook API.

        Run a playbook against the inventory.

        Args:
            playbook: Playbook to execute
            inventory: Inventory to use (defaults to control node inventory)
            extra_vars: Extra variables to pass
            forks: Number of parallel forks

        Returns:
            Generator that yields PlaybookStats
        """
        logger.info(f"[{self.env.now:.4f}] ControlNode: ansible-playbook invoked")

        executor = PlaybookExecutor(
            env=self.env,
            network=self.network,
            playbook=playbook,
            inventory=inventory or self.inventory,
            extra_vars=extra_vars or {},
            forks=forks
        )

        stats = yield from executor.run()
        self.playbook_runs += 1
        self.total_tasks_executed += stats.total_tasks

        return stats

    # ========================================================================
    # ansible (ad-hoc) API
    # ========================================================================

    def _handle_adhoc_command(self, msg: NetworkMessage):
        """Handle ad-hoc command request."""
        assert isinstance(msg.payload, AdhocCommandRequest), \
            f"Expected AdhocCommandRequest, got {type(msg.payload)}"
        request: AdhocCommandRequest = msg.payload

        logger.info(
            f"[{self.env.now:.4f}] ControlNode: Running ad-hoc command "
            f"{request.module_name} on pattern '{request.pattern}'"
        )

        self.adhoc_commands += 1

        # Convert ad-hoc command to a single-task playbook
        task = Task(
            name=f"Ad-hoc: {request.module_name}",
            action=request.module_name,
            args=request.module_args,
            become=request.become,
            become_user=request.become_user
        )

        play = Play(
            name="Ad-hoc command",
            hosts=request.pattern,
            gather_facts=False,
            tasks=[task]
        )

        playbook = Playbook(plays=[play])

        # Execute
        executor = PlaybookExecutor(
            env=self.env,
            network=self.network,
            playbook=playbook,
            inventory=self.inventory,
            forks=request.forks
        )

        stats = yield from executor.run()

        # Build response
        response = AdhocCommandResponse(
            request_id=request.request_id,
            stats={
                "ok": stats.play_stats[0].tasks_ok if stats.play_stats else 0,
                "changed": stats.play_stats[0].tasks_changed if stats.play_stats else 0,
                "failed": stats.play_stats[0].tasks_failed if stats.play_stats else 0,
                "skipped": stats.play_stats[0].tasks_skipped if stats.play_stats else 0
            }
        )

        # Send response
        response_msg = NetworkMessage(
            sender_id=self.id,
            receiver_id=msg.sender_id,
            payload=response,
            timestamp=self.env.now
        )
        self.network.send_message(response_msg)

    def ansible(self, pattern: str, module_name: str, module_args: Optional[Dict[str, Any]] = None,
                forks: int = 5, become: bool = False):
        """
        ansible (ad-hoc command) API.

        Execute a single module on hosts matching the pattern.

        Args:
            pattern: Host pattern (e.g., "all", "webservers")
            module_name: Module to execute
            module_args: Module arguments
            forks: Number of parallel forks
            become: Use privilege escalation

        Returns:
            Generator that yields PlaybookStats
        """
        logger.info(f"[{self.env.now:.4f}] ControlNode: ansible {pattern} -m {module_name}")

        # Convert to playbook
        task = Task(
            name=f"Ad-hoc: {module_name}",
            action=module_name,
            args=module_args or {},
            become=become
        )

        play = Play(
            name="Ad-hoc command",
            hosts=pattern,
            gather_facts=False,
            tasks=[task]
        )

        playbook = Playbook(plays=[play])

        # Execute
        stats = yield from self.ansible_playbook(playbook, forks=forks)
        self.adhoc_commands += 1

        return stats

    # ========================================================================
    # ansible-inventory API
    # ========================================================================

    def _handle_inventory_list(self, msg: NetworkMessage):
        """Handle inventory list request."""
        assert isinstance(msg.payload, InventoryListRequest), \
            f"Expected InventoryListRequest, got {type(msg.payload)}"
        request: InventoryListRequest = msg.payload

        logger.info(f"[{self.env.now:.4f}] ControlNode: Listing inventory for pattern '{request.pattern}'")

        # Get hosts
        hosts = self.inventory.get_hosts(request.pattern)

        # Build response
        response = InventoryListResponse(
            request_id=request.request_id,
            hosts=[h.name for h in hosts],
            groups=list(self.inventory.groups.keys()),
            host_vars={h.name: h.vars for h in hosts}
        )

        # Send response
        response_msg = NetworkMessage(
            sender_id=self.id,
            receiver_id=msg.sender_id,
            payload=response,
            timestamp=self.env.now
        )
        self.network.send_message(response_msg)

    def ansible_inventory(self, pattern: str = "all") -> Dict[str, Any]:
        """
        ansible-inventory API.

        List inventory hosts and groups.

        Args:
            pattern: Host pattern to list

        Returns:
            Dictionary with inventory information
        """
        logger.info(f"[{self.env.now:.4f}] ControlNode: ansible-inventory --list")

        hosts = self.inventory.get_hosts(pattern)

        return {
            "hosts": [h.name for h in hosts],
            "groups": list(self.inventory.groups.keys()),
            "host_vars": {h.name: h.vars for h in hosts}
        }

    # ========================================================================
    # ansible-vault API (Simulated)
    # ========================================================================

    def ansible_vault_encrypt(self, data: str, vault_id: str = "default") -> str:
        """
        ansible-vault encrypt API (simulated).

        Args:
            data: Data to encrypt
            vault_id: Vault ID

        Returns:
            Simulated encrypted data
        """
        logger.info(f"[{self.env.now:.4f}] ControlNode: ansible-vault encrypt")
        return f"$ANSIBLE_VAULT;1.1;AES256\n{data[:20]}...encrypted..."

    def ansible_vault_decrypt(self, encrypted_data: str) -> str:
        """
        ansible-vault decrypt API (simulated).

        Args:
            encrypted_data: Encrypted data

        Returns:
            Simulated decrypted data
        """
        logger.info(f"[{self.env.now:.4f}] ControlNode: ansible-vault decrypt")
        return "decrypted_data"

    # ========================================================================
    # ansible-galaxy API (Simulated)
    # ========================================================================

    def ansible_galaxy_install(self, collection_name: str) -> bool:
        """
        ansible-galaxy collection install API (simulated).

        Args:
            collection_name: Collection to install

        Returns:
            Success status
        """
        logger.info(f"[{self.env.now:.4f}] ControlNode: ansible-galaxy collection install {collection_name}")
        return True

    def ansible_galaxy_init(self, role_name: str) -> bool:
        """
        ansible-galaxy role init API (simulated).

        Args:
            role_name: Role name to create

        Returns:
            Success status
        """
        logger.info(f"[{self.env.now:.4f}] ControlNode: ansible-galaxy role init {role_name}")
        return True

    # ========================================================================
    # ansible-config API (Simulated)
    # ========================================================================

    def ansible_config_dump(self) -> Dict[str, Any]:
        """
        ansible-config dump API (simulated).

        Returns:
            Configuration dictionary
        """
        logger.info(f"[{self.env.now:.4f}] ControlNode: ansible-config dump")
        return {
            "DEFAULT_FORKS": self.forks,
            "DEFAULT_GATHERING": self.gathering,
            "DEFAULT_HOST_LIST": ["inventory"],
            "DEFAULT_MODULE_NAME": "command",
            "DEFAULT_TIMEOUT": 10,
        }

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def add_host(self, host_name: str, groups: Optional[List[str]] = None,
                 vars: Optional[Dict[str, Any]] = None):
        """Add a host to the inventory."""
        from ansible_simulator.shared.models import Host

        host = Host(
            name=host_name,
            groups=groups or [],
            vars=vars or {}
        )
        self.inventory.add_host(host)

        logger.info(f"[{self.env.now:.4f}] ControlNode: Added host {host_name} to inventory")

    def add_group(self, group_name: str, hosts: Optional[List[str]] = None,
                  vars: Optional[Dict[str, Any]] = None):
        """Add a group to the inventory."""
        from ansible_simulator.shared.models import Group

        group = Group(
            name=group_name,
            hosts=hosts or [],
            vars=vars or {}
        )
        self.inventory.add_group(group)

        logger.info(f"[{self.env.now:.4f}] ControlNode: Added group {group_name} to inventory")

    def get_stats(self) -> Dict[str, Any]:
        """Get control node statistics."""
        return {
            "playbook_runs": self.playbook_runs,
            "adhoc_commands": self.adhoc_commands,
            "total_tasks_executed": self.total_tasks_executed,
            "inventory_hosts": len(self.inventory.hosts),
            "inventory_groups": len(self.inventory.groups)
        }
