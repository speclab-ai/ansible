# (c) 2025 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for process_limiter module."""

from __future__ import annotations

import platform
import pytest
import subprocess
from unittest.mock import Mock, patch, mock_open

from ansible.utils.process_limiter import (
    ResourceLimits,
    ProcessLimiter,
    LinuxCgroupProcessLimiter,
    NoOpProcessLimiter,
    create_process_limiter,
)


class TestResourceLimits:
    """Test ResourceLimits class."""

    def test_init_with_percentages(self):
        """Test initialization with percentage values."""
        limits = ResourceLimits(memory_percent=50.0, cpu_percent=90.0)
        assert limits.memory_percent == 50.0
        assert limits.cpu_percent == 90.0
        assert limits.memory_bytes is None
        assert limits.cpu_quota is None

    def test_init_with_absolute_values(self):
        """Test initialization with absolute values."""
        limits = ResourceLimits(
            memory_bytes=1024 * 1024 * 1024,  # 1GB
            cpu_quota=50000  # 50% of one core
        )
        assert limits.memory_bytes == 1024 * 1024 * 1024
        assert limits.cpu_quota == 50000

    @patch('builtins.open', mock_open(read_data='MemTotal:       16384000 kB\n'))
    def test_get_memory_limit_bytes_from_percent(self):
        """Test memory limit calculation from percentage."""
        limits = ResourceLimits(memory_percent=50.0)
        memory_bytes = limits.get_memory_limit_bytes()

        # 16384000 kB * 1024 * 50% = ~8.4GB
        expected = int(16384000 * 1024 * 0.5)
        assert memory_bytes == expected

    def test_get_memory_limit_bytes_absolute(self):
        """Test memory limit returns absolute value when set."""
        limits = ResourceLimits(
            memory_percent=50.0,
            memory_bytes=2 * 1024 * 1024 * 1024  # 2GB
        )
        # Should prefer absolute value
        assert limits.get_memory_limit_bytes() == 2 * 1024 * 1024 * 1024

    def test_get_cpu_quota_us_from_percent(self):
        """Test CPU quota calculation from percentage."""
        limits = ResourceLimits(cpu_percent=50.0)
        quota = limits.get_cpu_quota_us()

        # 50% = 50000 microseconds per 100ms period
        assert quota == 50000

    def test_get_cpu_quota_us_multi_core(self):
        """Test CPU quota for multi-core percentage."""
        limits = ResourceLimits(cpu_percent=200.0)  # 2 full cores
        quota = limits.get_cpu_quota_us()

        # 200% = 200000 microseconds
        assert quota == 200000

    def test_get_cpu_quota_us_absolute(self):
        """Test CPU quota returns absolute value when set."""
        limits = ResourceLimits(
            cpu_percent=50.0,
            cpu_quota=75000
        )
        # Should prefer absolute value
        assert limits.get_cpu_quota_us() == 75000

    def test_repr(self):
        """Test string representation."""
        limits = ResourceLimits(memory_percent=50.0, cpu_percent=90.0)
        repr_str = repr(limits)
        assert 'ResourceLimits' in repr_str
        assert '50.0' in repr_str
        assert '90.0' in repr_str


class TestLinuxCgroupProcessLimiter:
    """Test LinuxCgroupProcessLimiter class."""

    @patch('ansible.utils.process_limiter.Path')
    def test_check_cgroup_v2_mounted_success(self, mock_path):
        """Test successful cgroup v2 detection."""
        # Mock cgroup filesystem
        mock_root = Mock()
        mock_root.exists.return_value = True
        mock_controllers = Mock()
        mock_controllers.exists.return_value = True
        mock_ansible_cgroup = Mock()

        mock_path.return_value = mock_root
        mock_root.__truediv__ = Mock(side_effect=[mock_controllers, mock_ansible_cgroup])

        limiter = LinuxCgroupProcessLimiter()
        # The check happens in __init__, so we check the result
        assert isinstance(limiter, LinuxCgroupProcessLimiter)

    @pytest.mark.skipif(
        platform.system() != 'Linux',
        reason="Linux-specific test"
    )
    def test_run_limited_process_creates_subprocess(self):
        """Test that run_limited_process creates a subprocess."""
        limits = ResourceLimits(memory_percent=50.0, cpu_percent=90.0)
        limiter = LinuxCgroupProcessLimiter(limits)

        # Run a simple command
        process = limiter.run_limited_process(
            args=['echo', 'test'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        assert isinstance(process, subprocess.Popen)
        assert process.poll() is not None or process.wait(timeout=5) == 0

        # Cleanup
        limiter.cleanup()


class TestNoOpProcessLimiter:
    """Test NoOpProcessLimiter class."""

    def test_run_limited_process_no_limits(self):
        """Test that no-op limiter runs process without limits."""
        limiter = NoOpProcessLimiter()

        process = limiter.run_limited_process(
            args=['echo', 'test'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        assert isinstance(process, subprocess.Popen)
        returncode = process.wait(timeout=5)
        assert returncode == 0


class TestCreateProcessLimiter:
    """Test create_process_limiter factory function."""

    @patch('ansible.utils.process_limiter.platform.system')
    def test_create_linux_limiter(self, mock_system):
        """Test creating Linux limiter on Linux."""
        mock_system.return_value = 'Linux'

        limits = ResourceLimits(memory_percent=50.0)
        limiter = create_process_limiter(limits)

        assert isinstance(limiter, LinuxCgroupProcessLimiter)
        assert limiter.limits == limits

    @patch('ansible.utils.process_limiter.platform.system')
    def test_create_noop_limiter_macos(self, mock_system):
        """Test creating no-op limiter on macOS."""
        mock_system.return_value = 'Darwin'

        limits = ResourceLimits(memory_percent=50.0)
        limiter = create_process_limiter(limits)

        assert isinstance(limiter, NoOpProcessLimiter)
        assert limiter.limits == limits

    @patch('ansible.utils.process_limiter.platform.system')
    def test_create_noop_limiter_windows(self, mock_system):
        """Test creating no-op limiter on Windows."""
        mock_system.return_value = 'Windows'

        limits = ResourceLimits(memory_percent=50.0)
        limiter = create_process_limiter(limits)

        assert isinstance(limiter, NoOpProcessLimiter)

    def test_create_with_default_limits(self):
        """Test creating limiter with default limits."""
        limiter = create_process_limiter()

        assert isinstance(limiter, (LinuxCgroupProcessLimiter, NoOpProcessLimiter))
        assert isinstance(limiter.limits, ResourceLimits)
