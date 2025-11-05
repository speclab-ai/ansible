# Process Resource Limits

This document describes the infrastructure for running external processes with limited memory and CPU caps.

## Overview

The process resource limiting infrastructure allows spawning external processes (such as LSP servers) with configurable memory and CPU limits. This helps prevent runaway processes from consuming excessive system resources.

## Platform Support

### Linux (Fully Supported)
On Linux, resource limits are implemented using **cgroups v2**. This provides accurate and enforceable limits for:
- Memory usage (via `memory.max`)
- CPU quota (via `cpu.max`)

Requirements:
- Linux kernel with cgroup v2 support (4.5+)
- cgroup v2 mounted at `/sys/fs/cgroup`
- Write permissions to create child cgroups

### Other Platforms (TODO)

Resource limiting is not yet implemented for:
- **macOS**: TODO - Use `launchd` or `setrlimit`
- **Windows**: TODO - Use Job Objects
- **BSD**: TODO - Use `rctl` or `setrlimit`

On these platforms, processes will run without resource limits (no-op limiter).

## Architecture

The implementation consists of three main components:

### 1. Process Limiter (`lib/ansible/utils/process_limiter.py`)

Core infrastructure for process resource limiting:

- **`ResourceLimits`**: Configuration class for resource limits
  - `memory_percent`: Percentage of total system memory (0-100)
  - `cpu_percent`: Percentage of total CPU (0-100+, can exceed 100 for multi-core)
  - `memory_bytes`: Absolute memory limit in bytes (alternative to percentage)
  - `cpu_quota`: Absolute CPU quota in microseconds per 100ms period

- **`ProcessLimiter`**: Abstract base class for platform-specific limiters

- **`LinuxCgroupProcessLimiter`**: Linux implementation using cgroups v2
  - Creates temporary cgroups for each process
  - Applies memory and CPU limits
  - Automatic cleanup when process exits

- **`NoOpProcessLimiter`**: Fallback for unsupported platforms
  - Runs processes without limits
  - Logs warnings about missing implementation

- **`create_process_limiter()`**: Factory function that returns the appropriate limiter for the current platform

### 2. Configuration (`lib/ansible/config/resource_limits_config.py`)

Configuration management for resource limits:

- **`ResourceLimitsConfig`**: Main configuration class
  - Accepts configuration dictionary from editor's main config
  - Provides default values (50% memory, 90% CPU)
  - Integrates with editor's configuration system

### 3. LSP Server Executor (`lib/ansible/utils/lsp_server.py`)

High-level interface for running LSP servers with resource limits:

- **`LSPServer`**: Manages LSP server lifecycle
  - Starts server with resource limits
  - Handles graceful shutdown
  - Provides communication interface
  - Context manager support

- **`create_lsp_server()`**: Factory function for easy LSP server creation

## Configuration

### Editor Configuration

Configuration should be part of the editor's main configuration file. The expected structure is:

```json
{
  "process_limits": {
    "lsp_server": {
      "enabled": true,
      "memory_percent": 50.0,
      "cpu_percent": 90.0
    },
    "default": {
      "enabled": true,
      "memory_percent": 50.0,
      "cpu_percent": 90.0
    }
  }
}
```

The editor should load this configuration and pass it to `ResourceLimitsConfig` when creating LSP servers.

### Default Values

If no configuration is provided, the following defaults are used:

- **Memory**: 50% of total system memory
- **CPU**: 90% of total CPU capacity

### Understanding the Limits

**Memory Percent**:
- On a system with 16GB RAM, 50% = 8GB limit per process
- On a system with 32GB RAM, 50% = 16GB limit per process

**CPU Percent**:
- On a 4-core system, 90% = 3.6 cores available
- Values can exceed 100% on multi-core systems
  - 200% = 2 full cores
  - 400% = 4 full cores

## Usage Examples

### Example 1: Basic LSP Server with Default Config

```python
from ansible.utils.lsp_server import create_lsp_server

# Create and start server with default limits (50% memory, 90% CPU)
server = create_lsp_server(['pylsp'])
server.start()

# Use the server...
# Send LSP protocol messages via server.process.stdin/stdout

# Stop when done
server.stop()
```

### Example 2: LSP Server with Editor Configuration

```python
from ansible.utils.lsp_server import create_lsp_server
from ansible.config.resource_limits_config import ResourceLimitsConfig

# Load configuration from editor's main config
editor_config = {
    'process_limits': {
        'lsp_server': {
            'memory_percent': 40.0,
            'cpu_percent': 80.0,
            'enabled': True
        }
    }
}

config = ResourceLimitsConfig(editor_config)
server = create_lsp_server(['pylsp'], config=config)
server.start()
# ...
server.stop()
```

### Example 3: LSP Server with Context Manager

```python
from ansible.utils.lsp_server import create_lsp_server

# Automatically handles start/stop
with create_lsp_server(['pylsp']) as server:
    # Server is running
    print(f"PID: {server.get_pid()}")
    # Use the server...

# Server automatically stopped
```

### Example 4: Custom Resource Limits

```python
from ansible.utils.lsp_server import LSPServer
from ansible.utils.process_limiter import ResourceLimits

# Define custom limits: 25% memory, 50% CPU
limits = ResourceLimits(memory_percent=25.0, cpu_percent=50.0)

server = LSPServer(command=['pylsp'], limits=limits)
server.start()
# ...
server.stop()
```

### Example 5: Absolute Memory Limit

```python
from ansible.utils.process_limiter import ResourceLimits

# Limit to exactly 2GB of memory
limits = ResourceLimits(memory_bytes=2 * 1024 * 1024 * 1024)
```

### Example 6: Direct Process Limiting

```python
from ansible.utils.process_limiter import create_process_limiter, ResourceLimits

# Create limiter with custom limits
limits = ResourceLimits(memory_percent=30.0, cpu_percent=50.0)
limiter = create_process_limiter(limits)

# Run any process with limits
process = limiter.run_limited_process(
    args=['python', 'my_script.py'],
    cwd='/path/to/workdir',
)

# Wait for completion
process.wait()

# Cleanup
if hasattr(limiter, 'cleanup'):
    limiter.cleanup()
```

## Testing

Run the example script to see the functionality in action:

```bash
cd /home/user/ansible
python examples/lsp_server_example.py
```

This will demonstrate:
- Platform support detection
- Configuration loading
- LSP server lifecycle management
- Custom resource limits
- Context manager usage

## Implementation Details

### Linux Cgroups v2

On Linux, the implementation:

1. Creates a parent cgroup at `/sys/fs/cgroup/ansible/`
2. For each process, creates a child cgroup with unique name
3. Writes resource limits to cgroup control files:
   - `memory.max`: Maximum memory in bytes
   - `cpu.max`: CPU quota in microseconds per period
4. Adds the process PID to `cgroup.procs`
5. Automatically cleans up the cgroup when process exits

**Note**: Requires appropriate permissions to create cgroups. On some systems, you may need to:
- Run with elevated privileges, or
- Configure systemd to allow user cgroups, or
- Use systemd-run to create cgroups

### Error Handling

The implementation gracefully degrades when:
- cgroups v2 is not available
- Insufficient permissions to create cgroups
- Platform doesn't support resource limiting

In these cases, processes run without limits, and warnings are logged.

## Future Work

### Non-Linux Platform Support

**macOS**:
- Option 1: Use `launchd` with resource limits
- Option 2: Use `setrlimit()` (less reliable for memory)
- Option 3: Use `vm_protect()` for memory regions

**Windows**:
- Use Job Objects API
- `CreateJobObject()`, `SetInformationJobObject()`
- `JOBOBJECT_EXTENDED_LIMIT_INFORMATION`

**BSD**:
- Use `rctl` (resource limits) on FreeBSD
- Use `setrlimit()` as fallback

### Additional Features

- [ ] Disk I/O limits (Linux: `io.max`)
- [ ] Network bandwidth limits (Linux: cgroup net_cls + tc)
- [ ] Process count limits (Linux: `pids.max`)
- [ ] Per-user resource pools
- [ ] Resource usage monitoring and reporting
- [ ] Automatic limit adjustment based on system load

## References

- [Linux cgroups v2 documentation](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
- [LSP Specification](https://microsoft.github.io/language-server-protocol/)
- [Python subprocess module](https://docs.python.org/3/library/subprocess.html)

## License

Copyright (c) 2025 Ansible Project
GNU General Public License v3.0+
