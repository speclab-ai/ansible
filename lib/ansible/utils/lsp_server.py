# (c) 2025 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""LSP (Language Server Protocol) server executor with resource limits.

This module provides functionality to spawn and manage LSP servers
with configurable memory and CPU limits.
"""

from __future__ import annotations

import subprocess
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from ansible.utils.process_limiter import (
    ResourceLimits,
    ProcessLimiter,
    create_process_limiter,
)
from ansible.config.resource_limits_config import ResourceLimitsConfig

logger = logging.getLogger(__name__)


class LSPServer:
    """Manages an LSP server process with resource limits."""

    def __init__(
        self,
        command: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        limits: Optional[ResourceLimits] = None,
        config: Optional[ResourceLimitsConfig] = None,
    ):
        """Initialize LSP server.

        Args:
            command: Command and arguments to start the LSP server
            cwd: Working directory for the server
            env: Environment variables for the server
            limits: Resource limits to apply (overrides config)
            config: Configuration object (used if limits not provided)
        """
        self.command = command
        self.cwd = cwd
        self.env = env
        self.process: Optional[subprocess.Popen] = None
        self.limiter: Optional[ProcessLimiter] = None

        # Determine resource limits
        if limits is None:
            # Load from config
            if config is None:
                config = ResourceLimitsConfig.load_config()

            lsp_config = config.get_lsp_limits()
            if lsp_config.get('enabled', True):
                limits = ResourceLimits(
                    memory_percent=lsp_config.get('memory_percent'),
                    cpu_percent=lsp_config.get('cpu_percent'),
                )
            else:
                # Limits disabled in config
                limits = None

        self.limits = limits

    def start(self) -> subprocess.Popen:
        """Start the LSP server with resource limits.

        Returns:
            subprocess.Popen object for the server process

        Raises:
            RuntimeError: If server is already running
            subprocess.SubprocessError: If server fails to start
        """
        if self.process is not None and self.process.poll() is None:
            raise RuntimeError("LSP server is already running")

        logger.info(f"Starting LSP server: {' '.join(self.command)}")

        if self.limits:
            logger.info(f"Applying resource limits: {self.limits}")
            # Create process limiter
            self.limiter = create_process_limiter(self.limits)

            # Start process with limits
            self.process = self.limiter.run_limited_process(
                args=self.command,
                cwd=self.cwd,
                env=self.env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        else:
            logger.info("Starting LSP server without resource limits")
            # Start process without limits
            self.process = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                env=self.env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        logger.info(f"LSP server started with PID: {self.process.pid}")
        return self.process

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the LSP server gracefully.

        Args:
            timeout: Time to wait for graceful shutdown before killing
        """
        if self.process is None:
            return

        logger.info(f"Stopping LSP server (PID: {self.process.pid})")

        try:
            # Try graceful shutdown first
            self.process.terminate()
            try:
                self.process.wait(timeout=timeout)
                logger.info("LSP server stopped gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't stop
                logger.warning("LSP server did not stop gracefully, forcing kill")
                self.process.kill()
                self.process.wait()
                logger.info("LSP server killed")
        except Exception as e:
            logger.error(f"Error stopping LSP server: {e}")
        finally:
            # Clean up limiter resources
            if self.limiter and hasattr(self.limiter, 'cleanup'):
                self.limiter.cleanup()
            self.process = None
            self.limiter = None

    def is_running(self) -> bool:
        """Check if the LSP server is still running.

        Returns:
            True if server is running, False otherwise
        """
        return self.process is not None and self.process.poll() is None

    def get_pid(self) -> Optional[int]:
        """Get the process ID of the running server.

        Returns:
            PID if server is running, None otherwise
        """
        return self.process.pid if self.process else None

    def communicate(
        self,
        input_data: Optional[bytes] = None,
        timeout: Optional[float] = None,
    ) -> tuple[bytes, bytes]:
        """Communicate with the LSP server.

        Args:
            input_data: Data to send to stdin
            timeout: Timeout for communication

        Returns:
            Tuple of (stdout, stderr)

        Raises:
            RuntimeError: If server is not running
            subprocess.TimeoutExpired: If timeout is exceeded
        """
        if not self.is_running():
            raise RuntimeError("LSP server is not running")

        return self.process.communicate(input=input_data, timeout=timeout)

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False

    def __del__(self):
        """Cleanup on deletion."""
        if self.is_running():
            self.stop()


def create_lsp_server(
    command: List[str],
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    config_path: Optional[str] = None,
) -> LSPServer:
    """Factory function to create an LSP server with configuration.

    Args:
        command: Command and arguments to start the LSP server
        cwd: Working directory for the server
        env: Environment variables for the server
        config_path: Optional path to configuration file

    Returns:
        LSPServer instance
    """
    config = ResourceLimitsConfig.load_config(config_path)
    return LSPServer(command=command, cwd=cwd, env=env, config=config)


# Example usage
if __name__ == '__main__':
    # Configure logging for example
    logging.basicConfig(level=logging.INFO)

    # Example: Start a Python LSP server with default limits
    # This would typically be pylsp or pyright
    server = create_lsp_server(['python', '-m', 'pylsp'])

    try:
        server.start()
        print(f"LSP server running with PID: {server.get_pid()}")

        # Server is now running and can be used for LSP communication
        # In real usage, you would send LSP protocol messages here

        import time
        time.sleep(5)  # Keep server running for demo

    finally:
        server.stop()
        print("LSP server stopped")
