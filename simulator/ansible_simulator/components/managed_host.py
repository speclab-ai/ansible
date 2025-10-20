"""
Managed Host Component.

Simulates a remote host that Ansible manages, including:
- SSH server simulation
- File system simulation
- Process execution
- Package management state
- Service state
"""

import simpy
import random
from typing import Dict, List, Optional, Any, Set
from pydantic import BaseModel, Field

from simulator.infra.base_service import BaseService
from simulator.infra.network import Network, NetworkMessage
from simulator.infra.machine import Machine

from ansible_simulator.shared.models import (
    ModuleResponse, ConnectionInfo, Host
)

import logging
logger = logging.getLogger(__name__)


class FileSystemEntry(BaseModel):
    """Represents a file or directory on the host."""
    path: str
    is_dir: bool = False
    content: str = ""
    owner: str = "root"
    group: str = "root"
    mode: str = "0644"
    exists: bool = True


class PackageInfo(BaseModel):
    """Represents an installed package."""
    name: str
    version: str
    state: str = "present"  # present, absent, latest


class ServiceInfo(BaseModel):
    """Represents a system service."""
    name: str
    state: str = "stopped"  # started, stopped
    enabled: bool = False


class SSHConnectionRequest(BaseModel):
    """Request to establish SSH connection."""
    request_id: str
    connection_info: ConnectionInfo


class SSHConnectionResponse(BaseModel):
    """Response to SSH connection request."""
    request_id: str
    success: bool
    session_id: Optional[str] = None
    error: Optional[str] = None


class ModuleExecutionRequest(BaseModel):
    """Request to execute a module on the host."""
    request_id: str
    session_id: str
    module_name: str
    module_args: Dict[str, Any]
    become: bool = False
    become_user: Optional[str] = None


class ManagedHost(BaseService):
    """
    Simulates a managed host in the Ansible infrastructure.

    This component represents a remote server that Ansible manages,
    including its SSH server, file system, packages, and services.
    """

    # Host configuration
    host_info: Host

    # SSH state
    ssh_enabled: bool = True
    active_sessions: Dict[str, ConnectionInfo] = Field(default_factory=dict)
    session_counter: int = 0

    # File system simulation
    filesystem: Dict[str, FileSystemEntry] = Field(default_factory=dict)

    # Package management
    installed_packages: Dict[str, PackageInfo] = Field(default_factory=dict)
    available_packages: Dict[str, str] = Field(default_factory=dict)  # name -> latest version

    # Service management
    services: Dict[str, ServiceInfo] = Field(default_factory=dict)

    # System facts (gathered by setup module)
    facts: Dict[str, Any] = Field(default_factory=dict)

    # Execution tracking
    command_history: List[str] = Field(default_factory=list)

    def __init__(self, **data):
        """Initialize the managed host."""
        super().__init__(**data)
        self._initialize_host()

    def _initialize_host(self):
        """Initialize host with default state."""
        # Set up basic filesystem
        self.filesystem["/"] = FileSystemEntry(path="/", is_dir=True)
        self.filesystem["/etc"] = FileSystemEntry(path="/etc", is_dir=True)
        self.filesystem["/tmp"] = FileSystemEntry(path="/tmp", is_dir=True, mode="1777")
        self.filesystem["/home"] = FileSystemEntry(path="/home", is_dir=True)
        self.filesystem["/var"] = FileSystemEntry(path="/var", is_dir=True)

        # Set up some common packages
        self.available_packages = {
            "nginx": "1.18.0",
            "apache2": "2.4.41",
            "postgresql": "12.5",
            "mysql-server": "8.0.23",
            "docker": "20.10.5",
            "git": "2.25.1",
            "python3": "3.8.10",
        }

        # Set up some common services
        for service_name in ["nginx", "apache2", "postgresql", "mysql", "docker", "ssh"]:
            self.services[service_name] = ServiceInfo(name=service_name, state="stopped")

        # SSH is always running
        self.services["ssh"].state = "started"
        self.services["ssh"].enabled = True

        # Generate system facts
        self.facts = {
            "ansible_distribution": "Ubuntu",
            "ansible_distribution_version": "20.04",
            "ansible_os_family": "Debian",
            "ansible_architecture": "x86_64",
            "ansible_processor_cores": 4,
            "ansible_memtotal_mb": 8192,
            "ansible_hostname": self.host_info.name,
            "ansible_fqdn": f"{self.host_info.name}.example.com",
            "ansible_default_ipv4": {
                "address": self.host_info.ansible_host or "192.168.1.100"
            }
        }

    def _handle_message(self, msg: NetworkMessage):
        """Handle incoming messages."""
        if isinstance(msg.payload, SSHConnectionRequest):
            self._handle_ssh_connection(msg)
        elif isinstance(msg.payload, ModuleExecutionRequest):
            self.env.process(self._handle_module_execution(msg))

    def _handle_ssh_connection(self, msg: NetworkMessage):
        """Handle SSH connection request."""
        assert isinstance(msg.payload, SSHConnectionRequest), \
            f"Expected SSHConnectionRequest, got {type(msg.payload)}"
        request: SSHConnectionRequest = msg.payload

        if not self.ssh_enabled or not self.services["ssh"].state == "started":
            response = SSHConnectionResponse(
                request_id=request.request_id,
                success=False,
                error="SSH service not available"
            )
        else:
            # Simulate authentication delay
            self.session_counter += 1
            session_id = f"session_{self.id}_{self.session_counter}"
            self.active_sessions[session_id] = request.connection_info

            logger.info(f"[{self.env.now:.4f}] {self.id}: SSH connection established (session {session_id})")

            response = SSHConnectionResponse(
                request_id=request.request_id,
                success=True,
                session_id=session_id
            )

        # Send response
        response_msg = NetworkMessage(
            sender_id=self.id,
            receiver_id=msg.sender_id,
            payload=response,
            timestamp=self.env.now
        )
        self.network.send_message(response_msg)

    def _handle_module_execution(self, msg: NetworkMessage):
        """Handle module execution request."""
        assert isinstance(msg.payload, ModuleExecutionRequest), \
            f"Expected ModuleExecutionRequest, got {type(msg.payload)}"
        request: ModuleExecutionRequest = msg.payload

        # Verify session
        if request.session_id not in self.active_sessions:
            response = ModuleResponse(
                failed=True,
                msg="Invalid session ID"
            )
        else:
            # Simulate module transfer time
            yield self.env.timeout(random.uniform(0.01, 0.03))

            # Execute the module
            module_name = request.module_name
            if module_name == "setup":
                response = self._module_setup(request.module_args)
            elif module_name == "ping":
                response = self._module_ping(request.module_args)
            elif module_name == "command" or module_name == "shell":
                response = yield from self._module_command(request.module_args)
            elif module_name == "copy":
                response = self._module_copy(request.module_args)
            elif module_name == "file":
                response = self._module_file(request.module_args)
            elif module_name == "apt" or module_name == "yum":
                response = yield from self._module_package(request.module_args)
            elif module_name == "service" or module_name == "systemd":
                response = self._module_service(request.module_args)
            elif module_name == "user":
                response = self._module_user(request.module_args)
            elif module_name == "template":
                response = self._module_template(request.module_args)
            elif module_name == "git":
                response = yield from self._module_git(request.module_args)
            else:
                response = ModuleResponse(
                    failed=True,
                    msg=f"Module '{module_name}' not implemented in simulation"
                )

        # Send response
        response_msg = NetworkMessage(
            sender_id=self.id,
            receiver_id=msg.sender_id,
            payload=response,
            timestamp=self.env.now
        )
        self.network.send_message(response_msg)

    # ========================================================================
    # Module Implementations
    # ========================================================================

    def _module_setup(self, args: Dict[str, Any]) -> ModuleResponse:
        """Gather facts about the system."""
        logger.info(f"[{self.env.now:.4f}] {self.id}: Gathering facts")
        return ModuleResponse(
            changed=False,
            ansible_facts=self.facts
        )

    def _module_ping(self, args: Dict[str, Any]) -> ModuleResponse:
        """Test connectivity."""
        logger.info(f"[{self.env.now:.4f}] {self.id}: Ping")
        return ModuleResponse(
            changed=False,
            msg="pong"
        )

    def _module_command(self, args: Dict[str, Any]):
        """Execute a command."""
        cmd = args.get("_raw_params") or args.get("cmd", "")
        logger.info(f"[{self.env.now:.4f}] {self.id}: Executing command: {cmd}")

        # Simulate command execution time
        yield self.env.timeout(random.uniform(0.05, 0.2))

        self.command_history.append(cmd)

        # Simulate some common commands
        stdout = ""
        rc = 0

        if "echo" in cmd:
            stdout = cmd.replace("echo ", "").strip()
        elif "ls" in cmd:
            stdout = "file1.txt\nfile2.txt\ndir1"
        elif "pwd" in cmd:
            stdout = "/home/user"
        elif "whoami" in cmd:
            stdout = "root"
        elif "date" in cmd:
            stdout = f"Simulation time: {self.env.now:.2f}s"
        else:
            stdout = f"Executed: {cmd}"

        return ModuleResponse(
            changed=True,
            rc=rc,
            stdout=stdout,
            msg=f"Command executed: {cmd}"
        )

    def _module_copy(self, args: Dict[str, Any]) -> ModuleResponse:
        """Copy a file to the host."""
        src = args.get("src", "")
        dest = args.get("dest", "")
        content = args.get("content", "")

        logger.info(f"[{self.env.now:.4f}] {self.id}: Copying to {dest}")

        # Check if file already exists
        changed = False
        if dest not in self.filesystem or self.filesystem[dest].content != content:
            changed = True

        # Create or update file
        self.filesystem[dest] = FileSystemEntry(
            path=dest,
            is_dir=False,
            content=content or f"Content from {src}",
            owner=args.get("owner", "root"),
            group=args.get("group", "root"),
            mode=args.get("mode", "0644")
        )

        return ModuleResponse(
            changed=changed,
            msg=f"File copied to {dest}"
        )

    def _module_file(self, args: Dict[str, Any]) -> ModuleResponse:
        """Manage files and directories."""
        path = args.get("path", "")
        state = args.get("state", "file")  # file, directory, absent, link

        logger.info(f"[{self.env.now:.4f}] {self.id}: File module - {path} state={state}")

        changed = False

        if state == "directory":
            if path not in self.filesystem or not self.filesystem[path].is_dir:
                self.filesystem[path] = FileSystemEntry(
                    path=path,
                    is_dir=True,
                    owner=args.get("owner", "root"),
                    mode=args.get("mode", "0755")
                )
                changed = True
        elif state == "absent":
            if path in self.filesystem:
                del self.filesystem[path]
                changed = True
        elif state == "touch":
            if path not in self.filesystem:
                self.filesystem[path] = FileSystemEntry(path=path)
                changed = True

        return ModuleResponse(
            changed=changed,
            msg=f"File state '{state}' applied to {path}"
        )

    def _module_package(self, args: Dict[str, Any]):
        """Install/remove packages."""
        name = args.get("name", "")
        state = args.get("state", "present")  # present, absent, latest

        logger.info(f"[{self.env.now:.4f}] {self.id}: Package {name} state={state}")

        # Simulate package installation time
        yield self.env.timeout(random.uniform(0.5, 2.0))

        changed = False

        if state == "present" or state == "latest":
            if name not in self.installed_packages:
                if name in self.available_packages:
                    self.installed_packages[name] = PackageInfo(
                        name=name,
                        version=self.available_packages[name],
                        state="present"
                    )
                    changed = True
                else:
                    return ModuleResponse(
                        failed=True,
                        msg=f"Package '{name}' not found in repositories"
                    )
        elif state == "absent":
            if name in self.installed_packages:
                del self.installed_packages[name]
                changed = True

        return ModuleResponse(
            changed=changed,
            msg=f"Package {name} is {state}"
        )

    def _module_service(self, args: Dict[str, Any]) -> ModuleResponse:
        """Manage services."""
        name = args.get("name", "")
        state = args.get("state")  # started, stopped, restarted
        enabled = args.get("enabled")  # True/False

        logger.info(f"[{self.env.now:.4f}] {self.id}: Service {name} state={state} enabled={enabled}")

        if name not in self.services:
            self.services[name] = ServiceInfo(name=name)

        changed = False
        service = self.services[name]

        if state:
            if state in ["started", "restarted"] and service.state != "started":
                service.state = "started"
                changed = True
            elif state == "stopped" and service.state != "stopped":
                service.state = "stopped"
                changed = True
            elif state == "restarted":
                changed = True

        if enabled is not None and service.enabled != enabled:
            service.enabled = enabled
            changed = True

        return ModuleResponse(
            changed=changed,
            msg=f"Service {name} is {service.state}"
        )

    def _module_user(self, args: Dict[str, Any]) -> ModuleResponse:
        """Manage users (simplified)."""
        name = args.get("name", "")
        state = args.get("state", "present")

        logger.info(f"[{self.env.now:.4f}] {self.id}: User {name} state={state}")

        # Simplified - just track in facts
        changed = False
        users_key = "ansible_users"
        if users_key not in self.facts:
            self.facts[users_key] = []

        if state == "present" and name not in self.facts[users_key]:
            self.facts[users_key].append(name)
            changed = True
        elif state == "absent" and name in self.facts[users_key]:
            self.facts[users_key].remove(name)
            changed = True

        return ModuleResponse(
            changed=changed,
            msg=f"User {name} is {state}"
        )

    def _module_template(self, args: Dict[str, Any]) -> ModuleResponse:
        """Deploy a templated file (simplified)."""
        dest = args.get("dest", "")
        src = args.get("src", "")

        logger.info(f"[{self.env.now:.4f}] {self.id}: Template {src} to {dest}")

        # Simplified - treat like copy with variable substitution
        content = f"Templated content from {src} at {self.env.now}"

        changed = dest not in self.filesystem or self.filesystem[dest].content != content

        self.filesystem[dest] = FileSystemEntry(
            path=dest,
            content=content
        )

        return ModuleResponse(
            changed=changed,
            msg=f"Template deployed to {dest}"
        )

    def _module_git(self, args: Dict[str, Any]):
        """Clone/update git repository."""
        repo = args.get("repo", "")
        dest = args.get("dest", "")
        version = args.get("version", "HEAD")

        logger.info(f"[{self.env.now:.4f}] {self.id}: Git clone {repo} to {dest}")

        # Simulate git clone time
        yield self.env.timeout(random.uniform(0.5, 1.5))

        changed = dest not in self.filesystem

        # Create directory with git metadata
        self.filesystem[dest] = FileSystemEntry(
            path=dest,
            is_dir=True,
            content=f"Git repo: {repo}@{version}"
        )

        return ModuleResponse(
            changed=changed,
            msg=f"Repository cloned to {dest}",
            results={"before": None if changed else version, "after": version}
        )
