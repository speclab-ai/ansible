"""
Shared models for Ansible simulator.

These models represent the core data structures used throughout Ansible:
- Inventory (hosts, groups, variables)
- Playbooks (plays, tasks, blocks, roles)
- Execution results
- Module arguments
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from enum import Enum


# ============================================================================
# Inventory Models
# ============================================================================

class Host(BaseModel):
    """Represents a managed host in the inventory."""
    name: str
    vars: Dict[str, Any] = Field(default_factory=dict)
    groups: List[str] = Field(default_factory=list)

    # Connection parameters
    ansible_host: Optional[str] = None  # Actual hostname/IP
    ansible_port: int = 22
    ansible_user: Optional[str] = None
    ansible_connection: str = "ssh"  # ssh, local, etc.

    # Runtime state
    is_reachable: bool = True
    gathered_facts: Dict[str, Any] = Field(default_factory=dict)


class Group(BaseModel):
    """Represents a host group in the inventory."""
    name: str
    hosts: List[str] = Field(default_factory=list)
    children: List[str] = Field(default_factory=list)  # Child groups
    vars: Dict[str, Any] = Field(default_factory=dict)


class Inventory(BaseModel):
    """Ansible inventory containing hosts and groups."""
    hosts: Dict[str, Host] = Field(default_factory=dict)
    groups: Dict[str, Group] = Field(default_factory=dict)

    def get_hosts(self, pattern: str = "all") -> List[Host]:
        """Get hosts matching a pattern."""
        if pattern == "all":
            return list(self.hosts.values())
        elif pattern in self.groups:
            group = self.groups[pattern]
            result = []
            for host_name in group.hosts:
                if host_name in self.hosts:
                    result.append(self.hosts[host_name])
            return result
        elif pattern in self.hosts:
            return [self.hosts[pattern]]
        else:
            # Simple pattern matching
            return [h for h in self.hosts.values() if pattern in h.name]

    def add_host(self, host: Host):
        """Add a host to the inventory."""
        self.hosts[host.name] = host

    def add_group(self, group: Group):
        """Add a group to the inventory."""
        self.groups[group.name] = group


# ============================================================================
# Task and Playbook Models
# ============================================================================

class ModuleArgs(BaseModel):
    """Arguments passed to a module."""
    args: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"  # Allow arbitrary fields


class Task(BaseModel):
    """Represents a single task in a playbook."""
    name: str
    action: str  # Module name (e.g., "apt", "copy", "shell")
    args: Dict[str, Any] = Field(default_factory=dict)

    # Task modifiers
    when: Optional[str] = None  # Conditional expression
    loop: Optional[List[Any]] = None
    register_var: Optional[str] = Field(default=None, alias="register")  # Variable to register result
    changed_when: Optional[str] = None
    failed_when: Optional[str] = None
    ignore_errors: bool = False
    become: Optional[bool] = None
    become_user: Optional[str] = None
    delegate_to: Optional[str] = None
    run_once: bool = False

    # Task metadata
    tags: List[str] = Field(default_factory=list)
    notify: List[str] = Field(default_factory=list)  # Handlers to notify

    # Internal
    task_id: str = ""

    class Config:
        populate_by_name = True  # Allow both 'register' and 'register_var'


class Block(BaseModel):
    """Represents a block of tasks (with rescue/always)."""
    name: Optional[str] = None
    tasks: List[Task] = Field(default_factory=list)
    rescue: List[Task] = Field(default_factory=list)
    always: List[Task] = Field(default_factory=list)

    when: Optional[str] = None


class Role(BaseModel):
    """Represents an Ansible role."""
    name: str
    vars: Dict[str, Any] = Field(default_factory=dict)
    tasks: List[Task] = Field(default_factory=list)
    handlers: List[Task] = Field(default_factory=list)
    defaults: Dict[str, Any] = Field(default_factory=dict)


class Play(BaseModel):
    """Represents a play in a playbook."""
    name: str
    hosts: str  # Host pattern

    # Variables
    vars: Dict[str, Any] = Field(default_factory=dict)
    vars_files: List[str] = Field(default_factory=list)

    # Execution settings
    gather_facts: bool = True
    serial: Union[int, str] = "all"  # Batching
    strategy: str = "linear"  # linear, free, debug

    # Task sections
    pre_tasks: List[Task] = Field(default_factory=list)
    roles: List[Union[str, Role]] = Field(default_factory=list)
    tasks: List[Union[Task, Block]] = Field(default_factory=list)
    post_tasks: List[Task] = Field(default_factory=list)
    handlers: List[Task] = Field(default_factory=list)

    # Error handling
    max_fail_percentage: float = 0.0
    any_errors_fatal: bool = False

    # Connection settings
    remote_user: Optional[str] = None
    become: Optional[bool] = None
    become_user: Optional[str] = None
    become_method: Optional[str] = None


class Playbook(BaseModel):
    """Represents an Ansible playbook."""
    plays: List[Play] = Field(default_factory=list)
    name: Optional[str] = None


# ============================================================================
# Execution State Models
# ============================================================================

class TaskState(str, Enum):
    """States a task can be in during execution."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskResult(BaseModel):
    """Result of task execution on a host."""
    task_name: str
    host_name: str
    state: TaskState = TaskState.PENDING

    # Result data
    changed: bool = False
    failed: bool = False
    skipped: bool = False
    msg: str = ""
    rc: Optional[int] = None  # Return code
    stdout: str = ""
    stderr: str = ""

    # Timing
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0

    # Module output
    ansible_facts: Dict[str, Any] = Field(default_factory=dict)
    results: Dict[str, Any] = Field(default_factory=dict)

    # Loop results
    loop_results: List[Dict[str, Any]] = Field(default_factory=list)


class PlayStats(BaseModel):
    """Statistics for a play execution."""
    play_name: str
    total_hosts: int = 0
    total_tasks: int = 0
    hosts_ok: int = 0
    hosts_changed: int = 0
    hosts_unreachable: int = 0
    hosts_failed: int = 0
    hosts_skipped: int = 0
    tasks_ok: int = 0
    tasks_changed: int = 0
    tasks_failed: int = 0
    tasks_skipped: int = 0
    duration: float = 0.0


class PlaybookStats(BaseModel):
    """Overall statistics for playbook execution."""
    total_plays: int = 0
    total_tasks: int = 0
    total_hosts: int = 0
    play_stats: List[PlayStats] = Field(default_factory=list)
    duration: float = 0.0

    # Per-host summary
    host_summary: Dict[str, Dict[str, int]] = Field(default_factory=dict)


# ============================================================================
# Module and Action Models
# ============================================================================

class ModuleResponse(BaseModel):
    """Response from a module execution."""
    changed: bool = False
    failed: bool = False
    msg: str = ""
    rc: int = 0
    stdout: str = ""
    stderr: str = ""
    ansible_facts: Dict[str, Any] = Field(default_factory=dict)
    results: Dict[str, Any] = Field(default_factory=dict)


class ConnectionInfo(BaseModel):
    """Information about a connection to a host."""
    host: str
    port: int = 22
    user: str = "root"
    connection_type: str = "ssh"
    become: bool = False
    become_user: Optional[str] = None
    become_method: str = "sudo"


# ============================================================================
# API Request/Response Models
# ============================================================================

class AdhocCommandRequest(BaseModel):
    """Request for ansible ad-hoc command execution."""
    request_id: str
    pattern: str  # Host pattern
    module_name: str
    module_args: Dict[str, Any] = Field(default_factory=dict)
    forks: int = 5
    become: bool = False
    become_user: Optional[str] = None


class AdhocCommandResponse(BaseModel):
    """Response from ansible ad-hoc command."""
    request_id: str
    results: Dict[str, TaskResult] = Field(default_factory=dict)
    stats: Dict[str, int] = Field(default_factory=dict)


class PlaybookRunRequest(BaseModel):
    """Request to run a playbook."""
    request_id: str
    playbook: Playbook
    inventory: Optional[Inventory] = None
    extra_vars: Dict[str, Any] = Field(default_factory=dict)
    forks: int = 5
    limit: Optional[str] = None  # Limit to specific hosts
    tags: List[str] = Field(default_factory=list)
    skip_tags: List[str] = Field(default_factory=list)


class PlaybookRunResponse(BaseModel):
    """Response from playbook execution."""
    request_id: str
    stats: PlaybookStats
    success: bool = True
    error: Optional[str] = None


class InventoryListRequest(BaseModel):
    """Request to list inventory."""
    request_id: str
    pattern: str = "all"


class InventoryListResponse(BaseModel):
    """Response with inventory information."""
    request_id: str
    hosts: List[str] = Field(default_factory=list)
    groups: List[str] = Field(default_factory=list)
    host_vars: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
