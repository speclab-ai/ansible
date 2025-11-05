# (c) 2025 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Configuration management for process resource limits.

This module provides configuration loading and default values for
process resource limits used by LSP servers and other external processes.
"""

from __future__ import annotations

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


# Default resource limits
DEFAULT_MEMORY_PERCENT = 50.0  # 50% of total memory
DEFAULT_CPU_PERCENT = 90.0     # 90% of total CPU


class ResourceLimitsConfig:
    """Configuration for process resource limits.

    This configuration is typically loaded from the editor's main configuration
    file and passed to this class rather than being loaded from separate files.
    """

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """Initialize configuration.

        Args:
            config_dict: Dictionary with configuration values from editor config.
                        Expected structure:
                        {
                            'process_limits': {
                                'lsp_server': {
                                    'memory_percent': 50.0,
                                    'cpu_percent': 90.0,
                                    'enabled': True
                                },
                                'default': {
                                    'memory_percent': 50.0,
                                    'cpu_percent': 90.0,
                                    'enabled': True
                                }
                            }
                        }
        """
        config_dict = config_dict or {}

        # Extract process_limits section from editor config
        process_limits = config_dict.get('process_limits', {})

        # LSP server limits
        lsp_config = process_limits.get('lsp_server', {})
        self.lsp_memory_percent = lsp_config.get('memory_percent', DEFAULT_MEMORY_PERCENT)
        self.lsp_cpu_percent = lsp_config.get('cpu_percent', DEFAULT_CPU_PERCENT)
        self.lsp_enabled = lsp_config.get('enabled', True)

        # Default limits for other processes
        default_config = process_limits.get('default', {})
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
    def get_default_config(cls) -> 'ResourceLimitsConfig':
        """Get default configuration.

        Returns a configuration with default values (50% memory, 90% CPU).
        """
        return cls()

    def __repr__(self) -> str:
        return f"ResourceLimitsConfig({self.to_dict()})"
