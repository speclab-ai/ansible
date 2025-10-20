# Ansible Core Simulator

A comprehensive, in-process Python simulation of Ansible's core architecture and components. This simulator mirrors the real Ansible codebase structure and provides all major user-facing APIs.

## Architecture

The simulator faithfully reproduces Ansible's architecture as documented in the official Ansible development guide:

### Core Components

1. **ControlNode** (`control_node.py`)
   - Simulates the Ansible control machine
   - Provides all user-facing CLI APIs
   - Orchestrates playbook execution
   - Manages inventory

2. **ManagedHost** (`managed_host.py`)
   - Simulates remote managed hosts
   - SSH server simulation
   - File system, packages, and services
   - Module execution environment

3. **PlaybookExecutor** (`control_node.py`)
   - Orchestrates playbook execution
   - Iterates through plays
   - Aggregates statistics

4. **TaskQueueManager** (`strategy.py`)
   - Manages worker process pool
   - Coordinates task distribution
   - Tracks execution statistics

5. **WorkerProcess** (`executor.py`)
   - Simulates forked worker processes
   - Executes individual tasks
   - Returns results to main process

6. **TaskExecutor** (`executor.py`)
   - Executes tasks on hosts
   - Handles loops, conditionals
   - Processes module results

7. **PlayIterator** (`executor.py`)
   - State machine for task iteration
   - Manages per-host execution state
   - Handles setup, tasks, handlers

8. **Strategy Plugins** (`strategy.py`)
   - **Linear**: Lockstep execution (default)
   - **Free**: Independent host execution

9. **Connection Plugins** (`plugins.py`)
   - **SSH**: Simulated SSH connection
   - **Local**: Local execution

10. **Action Plugins** (`plugins.py`)
    - Bridge between tasks and modules
    - Handle file transfers, templating
    - Module execution

## Simulated User-Facing APIs

All major Ansible CLI tools are simulated:

### ansible-playbook

Run playbooks against inventory:

```python
from ansible_simulator.components.control_node import ControlNode
from ansible_simulator.shared.models import Playbook, Play, Task

# Create playbook
playbook = Playbook(plays=[
    Play(
        name="Configure web servers",
        hosts="webservers",
        tasks=[
            Task(name="Install nginx", action="apt", args={"name": "nginx"}),
            Task(name="Start nginx", action="service", args={"name": "nginx", "state": "started"})
        ]
    )
])

# Execute
stats = yield from control_node.ansible_playbook(playbook)
```

### ansible (ad-hoc commands)

Execute single modules across hosts:

```python
# Ping all hosts
stats = yield from control_node.ansible(
    pattern="all",
    module_name="ping"
)

# Run command on webservers
stats = yield from control_node.ansible(
    pattern="webservers",
    module_name="command",
    module_args={"_raw_params": "uptime"}
)
```

### ansible-inventory

List and query inventory:

```python
inventory_info = control_node.ansible_inventory(pattern="all")
# Returns: {"hosts": [...], "groups": [...], "host_vars": {...}}
```

### ansible-vault (simulated)

Encryption/decryption operations:

```python
encrypted = control_node.ansible_vault_encrypt("secret_data")
decrypted = control_node.ansible_vault_decrypt(encrypted)
```

### ansible-galaxy (simulated)

Collection and role management:

```python
control_node.ansible_galaxy_install("community.general")
control_node.ansible_galaxy_init("my_role")
```

### ansible-config (simulated)

Configuration management:

```python
config = control_node.ansible_config_dump()
# Returns configuration dictionary
```

## Simulated Modules

The following Ansible modules are simulated:

- **setup**: Gather system facts
- **ping**: Test connectivity
- **command/shell**: Execute commands
- **copy**: Copy files to remote hosts
- **file**: Manage files and directories
- **apt/yum**: Package management
- **service/systemd**: Service management
- **user**: User management
- **template**: Deploy templated files
- **git**: Git repository operations

Each module simulates realistic behavior including:
- Execution time
- Changed/unchanged states
- Return codes and output
- Side effects on host state

## Running the Simulation

### Basic Usage

```bash
cd simulator
python -m ansible_simulator.simulation
```

### Configuration Options

```bash
python -m ansible_simulator.simulation \
    --duration 120 \          # Simulation duration (seconds)
    --num-hosts 12 \          # Number of managed hosts
    --num-azs 3 \             # Number of availability zones
    --forks 5 \               # Ansible parallel forks
    --network-latency 0.02    # Network latency (seconds)
```

## Example Simulations

### 1. Web Server Deployment

```python
playbook = Playbook(plays=[
    Play(
        name="Deploy web application",
        hosts="webservers",
        strategy="linear",
        tasks=[
            Task(name="Install dependencies", action="apt",
                 args={"name": "nginx", "state": "present"}),
            Task(name="Copy application", action="copy",
                 args={"src": "/app", "dest": "/var/www/app"}),
            Task(name="Start nginx", action="service",
                 args={"name": "nginx", "state": "started"})
        ]
    )
])
```

### 2. Ad-hoc System Check

```python
# Check disk space on all hosts
yield from control_node.ansible(
    pattern="all",
    module_name="command",
    module_args={"_raw_params": "df -h"}
)
```

### 3. Multi-Play Playbook

```python
playbook = Playbook(plays=[
    Play(name="Setup webservers", hosts="webservers", tasks=[...]),
    Play(name="Setup databases", hosts="databases", tasks=[...]),
    Play(name="Configure load balancers", hosts="loadbalancers", tasks=[...])
])
```

## Execution Flow

The simulation follows Ansible's actual execution flow:

1. **Playbook Loading**
   - PlaybookExecutor loads playbook
   - Iterates through plays

2. **Play Execution**
   - TaskQueueManager created for each play
   - Strategy plugin loaded (linear/free)

3. **Task Distribution**
   - PlayIterator determines next tasks
   - Tasks queued to worker pool
   - Workers limited by fork count

4. **Task Execution**
   - WorkerProcess spawned for each task/host
   - TaskExecutor runs task
   - Action plugin loads and executes
   - Connection established (SSH)
   - Module executed on remote host
   - Results returned

5. **Result Processing**
   - Results collected from workers
   - Statistics updated
   - Host states advanced
   - Handlers notified

6. **Strategy-Specific Behavior**
   - **Linear**: All hosts complete task N before task N+1
   - **Free**: Hosts proceed independently

## Network Simulation

The simulator uses SimPy discrete event simulation with realistic networking:

- **Network latency**: Configurable mean and standard deviation
- **SSH connection**: Simulated handshake and authentication
- **Module transfer**: Simulated file transfer time
- **Message passing**: All communication via network messages

## Performance Metrics

The simulation tracks comprehensive metrics:

### Playbook Stats
- Total plays executed
- Total tasks executed
- Tasks OK/changed/failed/skipped
- Execution duration

### Play Stats
- Per-play task counts
- Per-host results
- Handler notifications

### Host Stats
- SSH sessions established
- Commands executed
- Packages installed
- Services managed
- Files created/modified

## Architecture Alignment

This simulator closely mirrors the real Ansible codebase:

| Real Ansible | Simulator |
|-------------|-----------|
| `lib/ansible/cli/playbook.py` | `ControlNode.ansible_playbook()` |
| `lib/ansible/executor/playbook_executor.py` | `PlaybookExecutor` |
| `lib/ansible/executor/task_queue_manager.py` | `TaskQueueManager` |
| `lib/ansible/executor/task_executor.py` | `TaskExecutor` |
| `lib/ansible/executor/process/worker.py` | `WorkerProcess` |
| `lib/ansible/executor/play_iterator.py` | `PlayIterator` |
| `lib/ansible/plugins/strategy/linear.py` | `LinearStrategy` |
| `lib/ansible/plugins/strategy/free.py` | `FreeStrategy` |
| `lib/ansible/plugins/connection/ssh.py` | `SSHConnection` |
| `lib/ansible/plugins/action/*.py` | `ActionPlugin` subclasses |

## Extending the Simulator

### Adding New Modules

Add module implementation to `managed_host.py`:

```python
def _module_mymodule(self, args: Dict[str, Any]) -> ModuleResponse:
    """Custom module implementation."""
    # Module logic here
    return ModuleResponse(
        changed=True,
        msg="Module executed"
    )
```

### Adding New Strategy

Create new strategy in `strategy.py`:

```python
class MyStrategy(StrategyBase):
    def run(self):
        # Strategy implementation
        pass
```

### Adding New Connection Plugin

Create connection plugin in `plugins.py`:

```python
class MyConnection(Connection):
    def connect(self):
        # Connection logic
        pass

    def execute_module(self, module_name, module_args):
        # Execution logic
        pass
```

## Use Cases

This simulator is useful for:

1. **Understanding Ansible Architecture**: Study how Ansible components interact
2. **Performance Analysis**: Analyze execution patterns and bottlenecks
3. **Strategy Comparison**: Compare linear vs free strategies
4. **Network Impact**: Study effect of network latency on execution
5. **Scale Testing**: Simulate large deployments
6. **Education**: Learn Ansible internals in a controlled environment
7. **Development**: Test new features before implementing in real Ansible

## Design Principles

1. **Architectural Fidelity**: Mirrors real Ansible component structure
2. **API Completeness**: All major user-facing APIs simulated
3. **Realistic Behavior**: Execution flow matches actual Ansible
4. **Instrumentation**: Comprehensive metrics and logging
5. **Extensibility**: Easy to add new modules, strategies, connections
6. **Performance**: In-process simulation for fast iteration

## Limitations

As a simulation, some aspects are simplified:

- Jinja2 templating is simplified
- Conditionals use basic evaluation
- No actual SSH/network communication
- File system is in-memory
- Module implementations are simplified
- No actual package installation

However, the execution flow, component architecture, and API surface are faithful to real Ansible.
