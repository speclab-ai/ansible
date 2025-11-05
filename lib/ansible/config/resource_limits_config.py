# (c) 2025 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Configuration management for process resource limits.

This module provides configuration loading and default values for
process resource limits used by LSP servers and other external processes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


# Default resource limits
DEFAULT_MEMORY_PERCENT = 50.0  # 50% of total memory
DEFAULT_CPU_PERCENT = 90.0     # 90% of total CPU


class ResourceLimitsConfig:
    """Configuration for process resource limits."""

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """Initialize configuration.

        Args:
            config_dict: Dictionary with configuration values
        """
        config_dict = config_dict or {}

        # LSP server limits
        lsp_config = config_dict.get('lsp_server', {})
        self.lsp_memory_percent = lsp_config.get('memory_percent', DEFAULT_MEMORY_PERCENT)
        self.lsp_cpu_percent = lsp_config.get('cpu_percent', DEFAULT_CPU_PERCENT)
        self.lsp_enabled = lsp_config.get('enabled', True)

        # Default limits for other processes
        default_config = config_dict.get('default', {})
        self.default_memory_percent = default_config.get('memory_percent', DEFAULT_MEMORY_PERCENT)
        self.default_cpu_percent = default_config.get('cpu_percent', DEFAULT_CPU_PERCENT)
        self.default_enabled = default_config.get('enabled', True)

    def get_lsp_limits(self) -> Dict[str, Any]:
        """Get LSP server resource limits configuration."""
        return {
            'memory_percent': self.lsp_memory_percent,
            'cpu_percent': self.lsp_cpu_percent,
            'enabled': self.lsp_enabled,
        }

    def get_default_limits(self) -> Dict[str, Any]:
        """Get default resource limits configuration."""
        return {
            'memory_percent': self.default_memory_percent,
            'cpu_percent': self.default_cpu_percent,
            'enabled': self.default_enabled,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'lsp_server': self.get_lsp_limits(),
            'default': self.get_default_limits(),
        }

    @classmethod
    def from_json_file(cls, file_path: str) -> 'ResourceLimitsConfig':
        """Load configuration from JSON file.

        Args:
            file_path: Path to JSON configuration file

        Returns:
            ResourceLimitsConfig instance

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
        """
        with open(file_path, 'r') as f:
            config_dict = json.load(f)
        return cls(config_dict)

    @classmethod
    def from_json_string(cls, json_str: str) -> 'ResourceLimitsConfig':
        """Load configuration from JSON string.

        Args:
            json_str: JSON string with configuration

        Returns:
            ResourceLimitsConfig instance

        Raises:
            json.JSONDecodeError: If string is not valid JSON
        """
        config_dict = json.loads(json_str)
        return cls(config_dict)

    @classmethod
    def get_default_config(cls) -> 'ResourceLimitsConfig':
        """Get default configuration."""
        return cls()

    @classmethod
    def load_config(cls, config_path: Optional[str] = None) -> 'ResourceLimitsConfig':
        """Load configuration from file or return default.

        Args:
            config_path: Optional path to configuration file.
                        If None, looks for default locations:
                        - $ANSIBLE_RESOURCE_LIMITS_CONFIG
                        - ~/.ansible/resource_limits.json
                        - /etc/ansible/resource_limits.json

        Returns:
            ResourceLimitsConfig instance
        """
        # Try provided path first
        if config_path:
            try:
                return cls.from_json_file(config_path)
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")

        # Try environment variable
        env_config = os.environ.get('ANSIBLE_RESOURCE_LIMITS_CONFIG')
        if env_config:
            try:
                return cls.from_json_file(env_config)
            except Exception as e:
                logger.warning(f"Failed to load config from env {env_config}: {e}")

        # Try user config
        user_config = Path.home() / '.ansible' / 'resource_limits.json'
        if user_config.exists():
            try:
                return cls.from_json_file(str(user_config))
            except Exception as e:
                logger.warning(f"Failed to load user config {user_config}: {e}")

        # Try system config
        system_config = Path('/etc/ansible/resource_limits.json')
        if system_config.exists():
            try:
                return cls.from_json_file(str(system_config))
            except Exception as e:
                logger.warning(f"Failed to load system config {system_config}: {e}")

        # Return default configuration
        logger.info("Using default resource limits configuration")
        return cls.get_default_config()

    def __repr__(self) -> str:
        return f"ResourceLimitsConfig({self.to_dict()})"
