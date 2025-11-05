# (c) 2025 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for resource_limits_config module."""

from __future__ import annotations

from ansible.config.resource_limits_config import (
    ResourceLimitsConfig,
    DEFAULT_MEMORY_PERCENT,
    DEFAULT_CPU_PERCENT,
)


class TestResourceLimitsConfig:
    """Test ResourceLimitsConfig class."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        config = ResourceLimitsConfig()

        assert config.lsp_memory_percent == DEFAULT_MEMORY_PERCENT
        assert config.lsp_cpu_percent == DEFAULT_CPU_PERCENT
        assert config.lsp_enabled is True
        assert config.default_memory_percent == DEFAULT_MEMORY_PERCENT
        assert config.default_cpu_percent == DEFAULT_CPU_PERCENT
        assert config.default_enabled is True

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration from editor config."""
        config_dict = {
            'process_limits': {
                'lsp_server': {
                    'memory_percent': 30.0,
                    'cpu_percent': 75.0,
                    'enabled': False,
                },
                'default': {
                    'memory_percent': 40.0,
                    'cpu_percent': 80.0,
                    'enabled': False,
                }
            }
        }

        config = ResourceLimitsConfig(config_dict)

        assert config.lsp_memory_percent == 30.0
        assert config.lsp_cpu_percent == 75.0
        assert config.lsp_enabled is False
        assert config.default_memory_percent == 40.0
        assert config.default_cpu_percent == 80.0
        assert config.default_enabled is False

    def test_get_lsp_limits(self):
        """Test getting LSP server limits."""
        config = ResourceLimitsConfig({
            'process_limits': {
                'lsp_server': {
                    'memory_percent': 25.0,
                    'cpu_percent': 60.0,
                    'enabled': True,
                }
            }
        })

        limits = config.get_lsp_limits()

        assert limits['memory_percent'] == 25.0
        assert limits['cpu_percent'] == 60.0
        assert limits['enabled'] is True

    def test_get_default_limits(self):
        """Test getting default limits."""
        config = ResourceLimitsConfig({
            'process_limits': {
                'default': {
                    'memory_percent': 35.0,
                    'cpu_percent': 70.0,
                    'enabled': True,
                }
            }
        })

        limits = config.get_default_limits()

        assert limits['memory_percent'] == 35.0
        assert limits['cpu_percent'] == 70.0
        assert limits['enabled'] is True

    def test_to_dict(self):
        """Test converting configuration to dictionary."""
        config_dict = {
            'process_limits': {
                'lsp_server': {
                    'memory_percent': 30.0,
                    'cpu_percent': 75.0,
                    'enabled': False,
                },
                'default': {
                    'memory_percent': 40.0,
                    'cpu_percent': 80.0,
                    'enabled': False,
                }
            }
        }

        config = ResourceLimitsConfig(config_dict)
        result = config.to_dict()

        assert result['lsp_server']['memory_percent'] == 30.0
        assert result['lsp_server']['cpu_percent'] == 75.0
        assert result['default']['memory_percent'] == 40.0
        assert result['default']['cpu_percent'] == 80.0

    def test_get_default_config(self):
        """Test getting default configuration."""
        config = ResourceLimitsConfig.get_default_config()

        assert config.lsp_memory_percent == DEFAULT_MEMORY_PERCENT
        assert config.lsp_cpu_percent == DEFAULT_CPU_PERCENT

    def test_repr(self):
        """Test string representation."""
        config = ResourceLimitsConfig()
        repr_str = repr(config)

        assert 'ResourceLimitsConfig' in repr_str
        assert 'lsp_server' in repr_str
        assert 'default' in repr_str
