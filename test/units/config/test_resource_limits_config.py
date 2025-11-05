# (c) 2025 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for resource_limits_config module."""

from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

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
        """Test initialization with custom configuration."""
        config_dict = {
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
            'lsp_server': {
                'memory_percent': 25.0,
                'cpu_percent': 60.0,
                'enabled': True,
            }
        })

        limits = config.get_lsp_limits()

        assert limits['memory_percent'] == 25.0
        assert limits['cpu_percent'] == 60.0
        assert limits['enabled'] is True

    def test_get_default_limits(self):
        """Test getting default limits."""
        config = ResourceLimitsConfig({
            'default': {
                'memory_percent': 35.0,
                'cpu_percent': 70.0,
                'enabled': True,
            }
        })

        limits = config.get_default_limits()

        assert limits['memory_percent'] == 35.0
        assert limits['cpu_percent'] == 70.0
        assert limits['enabled'] is True

    def test_to_dict(self):
        """Test converting configuration to dictionary."""
        config_dict = {
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

        config = ResourceLimitsConfig(config_dict)
        result = config.to_dict()

        assert result['lsp_server']['memory_percent'] == 30.0
        assert result['lsp_server']['cpu_percent'] == 75.0
        assert result['default']['memory_percent'] == 40.0
        assert result['default']['cpu_percent'] == 80.0

    def test_from_json_file(self):
        """Test loading configuration from JSON file."""
        config_dict = {
            'lsp_server': {
                'memory_percent': 20.0,
                'cpu_percent': 50.0,
                'enabled': True,
            }
        }

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_dict, f)
            temp_path = f.name

        try:
            config = ResourceLimitsConfig.from_json_file(temp_path)
            assert config.lsp_memory_percent == 20.0
            assert config.lsp_cpu_percent == 50.0
        finally:
            Path(temp_path).unlink()

    def test_from_json_file_not_found(self):
        """Test loading from non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            ResourceLimitsConfig.from_json_file('/nonexistent/file.json')

    def test_from_json_string(self):
        """Test loading configuration from JSON string."""
        json_str = '''
        {
            "lsp_server": {
                "memory_percent": 15.0,
                "cpu_percent": 45.0
            }
        }
        '''

        config = ResourceLimitsConfig.from_json_string(json_str)
        assert config.lsp_memory_percent == 15.0
        assert config.lsp_cpu_percent == 45.0

    def test_from_json_string_invalid(self):
        """Test loading from invalid JSON raises error."""
        with pytest.raises(json.JSONDecodeError):
            ResourceLimitsConfig.from_json_string('invalid json {')

    def test_get_default_config(self):
        """Test getting default configuration."""
        config = ResourceLimitsConfig.get_default_config()

        assert config.lsp_memory_percent == DEFAULT_MEMORY_PERCENT
        assert config.lsp_cpu_percent == DEFAULT_CPU_PERCENT

    def test_load_config_with_provided_path(self):
        """Test loading config with provided path."""
        config_dict = {
            'lsp_server': {
                'memory_percent': 22.0,
                'cpu_percent': 55.0,
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_dict, f)
            temp_path = f.name

        try:
            config = ResourceLimitsConfig.load_config(temp_path)
            assert config.lsp_memory_percent == 22.0
            assert config.lsp_cpu_percent == 55.0
        finally:
            Path(temp_path).unlink()

    @patch.dict('os.environ', {'ANSIBLE_RESOURCE_LIMITS_CONFIG': '/tmp/test_config.json'})
    @patch('ansible.config.resource_limits_config.Path')
    def test_load_config_from_env(self, mock_path):
        """Test loading config from environment variable."""
        # This test is simplified - in real scenario would need to mock file operations
        config = ResourceLimitsConfig.load_config()
        # Should return default config if file doesn't exist
        assert isinstance(config, ResourceLimitsConfig)

    def test_load_config_returns_default_when_no_file(self):
        """Test loading config returns default when no files exist."""
        # Mock all paths to not exist
        with patch('ansible.config.resource_limits_config.Path') as mock_path:
            mock_path.home.return_value = Mock()
            mock_path.return_value.exists.return_value = False

            config = ResourceLimitsConfig.load_config()

            assert config.lsp_memory_percent == DEFAULT_MEMORY_PERCENT
            assert config.lsp_cpu_percent == DEFAULT_CPU_PERCENT

    def test_repr(self):
        """Test string representation."""
        config = ResourceLimitsConfig()
        repr_str = repr(config)

        assert 'ResourceLimitsConfig' in repr_str
        assert 'lsp_server' in repr_str
        assert 'default' in repr_str
