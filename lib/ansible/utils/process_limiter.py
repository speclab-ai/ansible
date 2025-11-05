# (c) 2025 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Process resource limiter using OS-specific mechanisms.

This module provides infrastructure for running external processes with
limited memory and CPU caps. On Linux, it uses cgroups v2 for resource
control. On other platforms, TODOs are left for future implementation.
"""

from __future__ import annotations

import os
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
import shutil
import logging

logger = logging.getLogger(__name__)


class ResourceLimits:
    """Container for resource limit configuration."""

    def __init__(
        self,
        memory_percent: Optional[float] = None,
        cpu_percent: Optional[float] = None,
        memory_bytes: Optional[int] = None,
        cpu_quota: Optional[int] = None,
    ):
        """Initialize resource limits.

        Args:
            memory_percent: Percentage of total system memory (0-100)
            cpu_percent: Percentage of total CPU (0-100, can exceed 100 for multi-core)
            memory_bytes: Absolute memory limit in bytes (overrides memory_percent)
            cpu_quota: Absolute CPU quota in microseconds per 100ms period
        """
        self.memory_percent = memory_percent
        self.cpu_percent = cpu_percent
        self.memory_bytes = memory_bytes
        self.cpu_quota = cpu_quota

    def get_memory_limit_bytes(self) -> Optional[int]:
        """Calculate actual memory limit in bytes."""
        if self.memory_bytes is not None:
            return self.memory_bytes

        if self.memory_percent is not None:
            try:
                # Get total system memory
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            # MemTotal is in kB
                            total_kb = int(line.split()[1])
                            total_bytes = total_kb * 1024
                            return int(total_bytes * (self.memory_percent / 100.0))
            except (IOError, ValueError, IndexError):
                logger.warning("Failed to read system memory from /proc/meminfo")

        return None

    def get_cpu_quota_us(self) -> Optional[int]:
        """Calculate CPU quota in microseconds per 100ms period."""
        if self.cpu_quota is not None:
            return self.cpu_quota

        if self.cpu_percent is not None:
            # CPU quota is in microseconds per period (100ms = 100000us)
            # For example, 50% of one core = 50000us, 200% (2 cores) = 200000us
            return int(self.cpu_percent * 1000)

        return None

    def __repr__(self) -> str:
        return (f"ResourceLimits(memory_percent={self.memory_percent}, "
                f"cpu_percent={self.cpu_percent}, "
                f"memory_bytes={self.memory_bytes}, "
                f"cpu_quota={self.cpu_quota})")


class ProcessLimiter:
    """Abstract base for process resource limiting."""

    def __init__(self, limits: Optional[ResourceLimits] = None):
        """Initialize process limiter.

        Args:
            limits: Resource limits to apply
        """
        self.limits = limits or ResourceLimits()

    def run_limited_process(
        self,
        args: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        stdin=None,
        stdout=None,
        stderr=None,
    ) -> subprocess.Popen:
        """Run a process with resource limits applied.

        Args:
            args: Command and arguments as list
            cwd: Working directory
            env: Environment variables
            stdin: Standard input
            stdout: Standard output
            stderr: Standard error

        Returns:
            subprocess.Popen object
        """
        raise NotImplementedError("Subclasses must implement run_limited_process")


class LinuxCgroupProcessLimiter(ProcessLimiter):
    """Linux-specific process limiter using cgroups v2.

    This implementation creates a temporary cgroup for each process,
    applies memory and CPU limits, and cleans up when done.
    """

    def __init__(self, limits: Optional[ResourceLimits] = None):
        super().__init__(limits)
        self._cgroup_path: Optional[Path] = None
        self._cgroup_mounted = self._check_cgroup_v2_mounted()

    def _check_cgroup_v2_mounted(self) -> bool:
        """Check if cgroup v2 is mounted and accessible."""
        try:
            cgroup_root = Path('/sys/fs/cgroup')
            if not cgroup_root.exists():
                return False

            # Check if it's cgroup v2 by looking for cgroup.controllers
            controllers_file = cgroup_root / 'cgroup.controllers'
            if not controllers_file.exists():
                logger.warning("cgroup v2 not detected at /sys/fs/cgroup")
                return False

            # Check if we have write access (needed to create child cgroups)
            # We'll check the ansible subdirectory or create it
            ansible_cgroup = cgroup_root / 'ansible'
            try:
                ansible_cgroup.mkdir(exist_ok=True)
                return True
            except PermissionError:
                logger.warning("No permission to create cgroups under /sys/fs/cgroup")
                return False

        except Exception as e:
            logger.warning(f"Failed to check cgroup v2: {e}")
            return False

    def _create_cgroup(self) -> Optional[Path]:
        """Create a temporary cgroup for process isolation."""
        if not self._cgroup_mounted:
            return None

        try:
            # Create a unique cgroup under /sys/fs/cgroup/ansible/
            cgroup_root = Path('/sys/fs/cgroup/ansible')
            cgroup_root.mkdir(exist_ok=True)

            # Use a temporary name
            import uuid
            cgroup_name = f"process_{uuid.uuid4().hex[:16]}"
            cgroup_path = cgroup_root / cgroup_name
            cgroup_path.mkdir()

            logger.debug(f"Created cgroup: {cgroup_path}")
            return cgroup_path

        except Exception as e:
            logger.warning(f"Failed to create cgroup: {e}")
            return None

    def _apply_limits(self, cgroup_path: Path) -> None:
        """Apply resource limits to a cgroup."""
        try:
            # Apply memory limit
            memory_limit = self.limits.get_memory_limit_bytes()
            if memory_limit is not None:
                memory_max_file = cgroup_path / 'memory.max'
                memory_max_file.write_text(str(memory_limit))
                logger.debug(f"Applied memory limit: {memory_limit} bytes")

            # Apply CPU limit
            cpu_quota = self.limits.get_cpu_quota_us()
            if cpu_quota is not None:
                cpu_max_file = cgroup_path / 'cpu.max'
                # Format: "quota period" where period is typically 100000 (100ms)
                cpu_max_file.write_text(f"{cpu_quota} 100000")
                logger.debug(f"Applied CPU quota: {cpu_quota}us per 100ms")

        except Exception as e:
            logger.warning(f"Failed to apply cgroup limits: {e}")

    def _add_process_to_cgroup(self, cgroup_path: Path, pid: int) -> None:
        """Add a process to a cgroup."""
        try:
            cgroup_procs = cgroup_path / 'cgroup.procs'
            cgroup_procs.write_text(str(pid))
            logger.debug(f"Added process {pid} to cgroup {cgroup_path}")
        except Exception as e:
            logger.warning(f"Failed to add process to cgroup: {e}")

    def _cleanup_cgroup(self, cgroup_path: Path) -> None:
        """Clean up a cgroup after process exits."""
        try:
            if cgroup_path and cgroup_path.exists():
                # Wait briefly for all processes to exit
                import time
                for _ in range(10):
                    try:
                        cgroup_path.rmdir()
                        logger.debug(f"Cleaned up cgroup: {cgroup_path}")
                        break
                    except OSError:
                        # Cgroup may still have processes, wait a bit
                        time.sleep(0.1)
                else:
                    logger.warning(f"Failed to remove cgroup {cgroup_path} after 10 retries")
        except Exception as e:
            logger.warning(f"Failed to cleanup cgroup: {e}")

    def run_limited_process(
        self,
        args: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        stdin=None,
        stdout=None,
        stderr=None,
    ) -> subprocess.Popen:
        """Run a process with cgroup resource limits."""

        # Create cgroup if possible
        cgroup_path = self._create_cgroup()

        if cgroup_path:
            self._apply_limits(cgroup_path)

        # Start the process
        process = subprocess.Popen(
            args,
            cwd=cwd,
            env=env,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
        )

        # Add process to cgroup
        if cgroup_path:
            self._add_process_to_cgroup(cgroup_path, process.pid)
            # Store cgroup path for later cleanup
            self._cgroup_path = cgroup_path

        return process

    def cleanup(self) -> None:
        """Clean up resources after process exits."""
        if self._cgroup_path:
            self._cleanup_cgroup(self._cgroup_path)
            self._cgroup_path = None


class NoOpProcessLimiter(ProcessLimiter):
    """No-op process limiter for unsupported platforms.

    This is used on non-Linux platforms where resource limiting
    is not yet implemented.
    """

    def run_limited_process(
        self,
        args: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        stdin=None,
        stdout=None,
        stderr=None,
    ) -> subprocess.Popen:
        """Run a process without resource limits.

        TODO: Implement resource limiting for non-Linux platforms:
        - macOS: Use launchd or setrlimit
        - Windows: Use Job Objects
        - BSD: Use rctl or setrlimit
        """
        logger.info("Resource limiting not implemented for this platform")

        return subprocess.Popen(
            args,
            cwd=cwd,
            env=env,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
        )


def create_process_limiter(limits: Optional[ResourceLimits] = None) -> ProcessLimiter:
    """Factory function to create appropriate process limiter for the platform.

    Args:
        limits: Resource limits to apply

    Returns:
        Platform-specific ProcessLimiter instance
    """
    system = platform.system()

    if system == 'Linux':
        return LinuxCgroupProcessLimiter(limits)
    else:
        # TODO: Implement for other platforms
        logger.warning(f"Process limiting not implemented for {system}, using no-op limiter")
        return NoOpProcessLimiter(limits)
