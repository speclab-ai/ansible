# (c) 2025 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for lsp_server module."""

from __future__ import annotations

import subprocess
import pytest
from unittest.mock import Mock, patch, MagicMock

from ansible.utils.lsp_server import LSPServer, create_lsp_server
from ansible.utils.process_limiter import ResourceLimits
from ansible.config.resource_limits_config import ResourceLimitsConfig


class TestLSPServer:
    """Test LSPServer class."""

    def test_init_with_limits(self):
        """Test initialization with resource limits."""
        limits = ResourceLimits(memory_percent=30.0, cpu_percent=60.0)
        server = LSPServer(command=['test'], limits=limits)

        assert server.command == ['test']
        assert server.limits == limits
        assert server.process is None

    def test_init_with_config(self):
        """Test initialization with configuration."""
        config = ResourceLimitsConfig({
            'process_limits': {
                'lsp_server': {
                    'memory_percent': 25.0,
                    'cpu_percent': 55.0,
                    'enabled': True,
                }
            }
        })

        server = LSPServer(command=['test'], config=config)

        assert server.limits is not None
        assert server.limits.memory_percent == 25.0
        assert server.limits.cpu_percent == 55.0

    def test_init_with_disabled_limits(self):
        """Test initialization with limits disabled in config."""
        config = ResourceLimitsConfig({
            'process_limits': {
                'lsp_server': {
                    'enabled': False,
                }
            }
        })

        server = LSPServer(command=['test'], config=config)

        assert server.limits is None

    @patch('ansible.utils.lsp_server.subprocess.Popen')
    def test_start_without_limits(self, mock_popen):
        """Test starting server without resource limits."""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        server = LSPServer(command=['test'], limits=None)
        result = server.start()

        assert result == mock_process
        assert server.process == mock_process
        mock_popen.assert_called_once()

    @patch('ansible.utils.lsp_server.create_process_limiter')
    def test_start_with_limits(self, mock_create_limiter):
        """Test starting server with resource limits."""
        limits = ResourceLimits(memory_percent=30.0)

        mock_process = Mock()
        mock_process.pid = 12345
        mock_limiter = Mock()
        mock_limiter.run_limited_process.return_value = mock_process
        mock_create_limiter.return_value = mock_limiter

        server = LSPServer(command=['test'], limits=limits)
        result = server.start()

        assert result == mock_process
        assert server.process == mock_process
        assert server.limiter == mock_limiter
        mock_create_limiter.assert_called_once_with(limits)
        mock_limiter.run_limited_process.assert_called_once()

    def test_start_already_running_raises_error(self):
        """Test starting already running server raises error."""
        with patch('ansible.utils.lsp_server.subprocess.Popen'):
            server = LSPServer(command=['test'], limits=None)
            server.start()

            with pytest.raises(RuntimeError, match="already running"):
                server.start()

    def test_stop_graceful(self):
        """Test graceful stop."""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.wait.return_value = 0

        server = LSPServer(command=['test'], limits=None)
        server.process = mock_process

        server.stop()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
        assert server.process is None

    def test_stop_force_kill(self):
        """Test force kill when graceful stop fails."""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = [subprocess.TimeoutExpired('cmd', 5), None]

        server = LSPServer(command=['test'], limits=None)
        server.process = mock_process

        server.stop()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert server.process is None

    def test_stop_with_limiter_cleanup(self):
        """Test stop cleans up limiter resources."""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_limiter = Mock()
        mock_limiter.cleanup = Mock()

        server = LSPServer(command=['test'], limits=None)
        server.process = mock_process
        server.limiter = mock_limiter

        server.stop()

        mock_limiter.cleanup.assert_called_once()
        assert server.limiter is None

    def test_is_running_true(self):
        """Test is_running returns True when process is running."""
        mock_process = Mock()
        mock_process.poll.return_value = None

        server = LSPServer(command=['test'], limits=None)
        server.process = mock_process

        assert server.is_running() is True

    def test_is_running_false(self):
        """Test is_running returns False when process is not running."""
        mock_process = Mock()
        mock_process.poll.return_value = 0

        server = LSPServer(command=['test'], limits=None)
        server.process = mock_process

        assert server.is_running() is False

    def test_is_running_no_process(self):
        """Test is_running returns False when no process."""
        server = LSPServer(command=['test'], limits=None)
        assert server.is_running() is False

    def test_get_pid(self):
        """Test getting process PID."""
        mock_process = Mock()
        mock_process.pid = 12345

        server = LSPServer(command=['test'], limits=None)
        server.process = mock_process

        assert server.get_pid() == 12345

    def test_get_pid_no_process(self):
        """Test getting PID when no process."""
        server = LSPServer(command=['test'], limits=None)
        assert server.get_pid() is None

    def test_communicate(self):
        """Test communicating with server."""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.communicate.return_value = (b'stdout', b'stderr')

        server = LSPServer(command=['test'], limits=None)
        server.process = mock_process

        stdout, stderr = server.communicate(b'test input')

        assert stdout == b'stdout'
        assert stderr == b'stderr'
        mock_process.communicate.assert_called_once_with(
            input=b'test input',
            timeout=None
        )

    def test_communicate_not_running_raises_error(self):
        """Test communicate raises error when server not running."""
        server = LSPServer(command=['test'], limits=None)

        with pytest.raises(RuntimeError, match="not running"):
            server.communicate()

    def test_context_manager(self):
        """Test using server as context manager."""
        with patch('ansible.utils.lsp_server.subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = 0
            mock_popen.return_value = mock_process

            with LSPServer(command=['test'], limits=None) as server:
                assert server.process is not None

            # Process should be stopped after exiting context
            mock_process.terminate.assert_called()


class TestCreateLSPServer:
    """Test create_lsp_server factory function."""

    def test_create_with_default_config(self):
        """Test creating server with default configuration."""
        server = create_lsp_server(['test'])

        assert isinstance(server, LSPServer)
        assert server.command == ['test']
        # Should use default limits
        assert server.limits is not None

    def test_create_with_custom_config(self):
        """Test creating server with custom config."""
        config = ResourceLimitsConfig({
            'process_limits': {
                'lsp_server': {
                    'memory_percent': 30.0,
                    'cpu_percent': 70.0,
                    'enabled': True,
                }
            }
        })

        server = create_lsp_server(['test'], config=config)

        assert isinstance(server, LSPServer)
        assert server.limits.memory_percent == 30.0
        assert server.limits.cpu_percent == 70.0

    def test_create_with_cwd_and_env(self):
        """Test creating server with working directory and environment."""
        env = {'VAR': 'value'}
        server = create_lsp_server(['test'], cwd='/tmp', env=env)

        assert server.cwd == '/tmp'
        assert server.env == env
