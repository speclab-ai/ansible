#!/usr/bin/env python3
# (c) 2025 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Example usage of LSP server with resource limits.

This example demonstrates how to use the LSP server executor with
configurable memory and CPU limits.
"""

import sys
import os
import logging

# Add lib to path for standalone execution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from ansible.utils.lsp_server import create_lsp_server
from ansible.utils.process_limiter import ResourceLimits
from ansible.config.resource_limits_config import ResourceLimitsConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def example_with_default_config():
    """Example: Start LSP server with default configuration."""
    logger.info("=" * 60)
    logger.info("Example 1: LSP Server with Default Configuration")
    logger.info("=" * 60)

    # This will use default values (50% memory, 90% CPU)
    # In a real editor, you would load config from the editor's main config file

    server = create_lsp_server(
        command=['python', '-c', 'import time; time.sleep(10)'],  # Mock LSP server
    )

    try:
        server.start()
        logger.info(f"Server running with PID: {server.get_pid()}")
        logger.info("Server will run for 10 seconds...")

        # In a real application, you would send LSP protocol messages here
        # For this example, we just wait
        import time
        time.sleep(2)

        logger.info(f"Server still running: {server.is_running()}")

    finally:
        server.stop()
        logger.info("Server stopped")


def example_with_custom_limits():
    """Example: Start LSP server with custom resource limits."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: LSP Server with Custom Limits")
    logger.info("=" * 60)

    # Define custom limits: 25% memory, 50% CPU
    custom_limits = ResourceLimits(
        memory_percent=25.0,
        cpu_percent=50.0,
    )

    from ansible.utils.lsp_server import LSPServer

    server = LSPServer(
        command=['python', '-c', 'import time; time.sleep(5)'],
        limits=custom_limits,
    )

    try:
        server.start()
        logger.info(f"Server running with PID: {server.get_pid()}")
        logger.info(f"Custom limits applied: {custom_limits}")

        import time
        time.sleep(2)

    finally:
        server.stop()
        logger.info("Server stopped")


def example_with_context_manager():
    """Example: Using context manager for automatic cleanup."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 3: Using Context Manager")
    logger.info("=" * 60)

    # Context manager automatically starts and stops the server
    with create_lsp_server(['python', '-c', 'import time; time.sleep(5)']) as server:
        logger.info(f"Server running with PID: {server.get_pid()}")

        import time
        time.sleep(2)

        logger.info(f"Server is running: {server.is_running()}")

    # Server is automatically stopped when exiting the context
    logger.info("Server automatically stopped by context manager")


def example_with_editor_config():
    """Example: Load configuration from editor's main config file."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 4: Using Editor Configuration")
    logger.info("=" * 60)

    # Simulate loading config from editor's main config file
    # In a real editor, this would be loaded from JSON/YAML/TOML config
    editor_config = {
        'process_limits': {
            'lsp_server': {
                'memory_percent': 40.0,
                'cpu_percent': 80.0,
                'enabled': True,
            }
        }
    }

    config = ResourceLimitsConfig(editor_config)
    logger.info(f"Loaded config from editor: {config}")

    server = create_lsp_server(
        command=['python', '-c', 'import time; time.sleep(5)'],
        config=config
    )

    try:
        server.start()
        logger.info(f"Server running with config limits: {server.limits}")

        import time
        time.sleep(2)

    finally:
        server.stop()
        logger.info("Server stopped")


def example_platform_check():
    """Example: Check platform support for resource limiting."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 5: Platform Support Check")
    logger.info("=" * 60)

    import platform
    from ansible.utils.process_limiter import create_process_limiter

    system = platform.system()
    logger.info(f"Platform: {system}")

    limiter = create_process_limiter(ResourceLimits(memory_percent=50, cpu_percent=90))
    logger.info(f"Process Limiter Type: {type(limiter).__name__}")

    if system == 'Linux':
        logger.info("✓ Resource limiting is fully supported on Linux (using cgroups)")
    else:
        logger.info("⚠ Resource limiting is not yet implemented for this platform")
        logger.info("  TODO: Implement for macOS, Windows, BSD")


if __name__ == '__main__':
    logger.info("LSP Server Resource Limiting Examples")
    logger.info("=" * 60)

    try:
        # Run all examples
        example_platform_check()
        example_with_default_config()
        example_with_custom_limits()
        example_with_context_manager()
        example_with_editor_config()

        logger.info("\n" + "=" * 60)
        logger.info("All examples completed successfully!")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.info("\nExamples interrupted by user")
    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)
        sys.exit(1)
