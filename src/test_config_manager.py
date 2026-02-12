"""
Unit tests for configuration management.

Tests AppConfig serialization and ConfigurationManager functionality.
"""
import json
import pytest
import tempfile
from pathlib import Path

from src.config_manager import AppConfig, ConfigurationManager, ProtocolType


class TestAppConfig:
    """Test AppConfig dataclass serialization."""
    
    def test_default_values(self):
        """Test that default configuration has expected values."""
        config = AppConfig()
        
        assert config.protocol == ProtocolType.RTMP
        assert config.rtmp_port == 2935
        assert config.srt_port == 9000
        assert config.webrtc_enabled is False
        assert config.http_port == 8000
        assert config.auto_reconnect is True
        assert config.max_reconnect_attempts == 10
        assert config.frame_width == 1280
        assert config.frame_height == 720
        assert config.fps == 30
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        config = AppConfig(
            protocol=ProtocolType.SRT,
            rtmp_port=3000,
            srt_port=9001,
            http_port=8080,
        )
        
        data = config.to_dict()
        
        assert data['protocol'] == 'srt'
        assert data['rtmp_port'] == 3000
        assert data['srt_port'] == 9001
        assert data['http_port'] == 8080
        assert isinstance(data, dict)
    
    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            'protocol': 'webrtc',
            'rtmp_port': 2936,
            'srt_port': 9002,
            'webrtc_enabled': True,
            'http_port': 8001,
            'auto_reconnect': False,
            'max_reconnect_attempts': 5,
            'frame_width': 1920,
            'frame_height': 1080,
            'fps': 60,
        }
        
        config = AppConfig.from_dict(data)
        
        assert config.protocol == ProtocolType.WEBRTC
        assert config.rtmp_port == 2936
        assert config.srt_port == 9002
        assert config.webrtc_enabled is True
        assert config.http_port == 8001
        assert config.auto_reconnect is False
        assert config.max_reconnect_attempts == 5
        assert config.frame_width == 1920
        assert config.frame_height == 1080
        assert config.fps == 60
    
    def test_from_dict_with_missing_fields(self):
        """Test deserialization with missing fields uses defaults."""
        data = {'protocol': 'rtmp'}
        
        config = AppConfig.from_dict(data)
        
        assert config.protocol == ProtocolType.RTMP
        assert config.rtmp_port == 2935  # default
        assert config.http_port == 8000  # default
    
    def test_from_dict_with_invalid_protocol(self):
        """Test deserialization with invalid protocol falls back to RTMP."""
        data = {'protocol': 'invalid_protocol'}
        
        config = AppConfig.from_dict(data)
        
        assert config.protocol == ProtocolType.RTMP
    
    def test_round_trip_serialization(self):
        """Test that to_dict() and from_dict() are inverses."""
        original = AppConfig(
            protocol=ProtocolType.SRT,
            rtmp_port=3000,
            srt_port=9001,
            webrtc_enabled=True,
            http_port=8080,
            auto_reconnect=False,
            max_reconnect_attempts=15,
            frame_width=1920,
            frame_height=1080,
            fps=60,
        )
        
        data = original.to_dict()
        restored = AppConfig.from_dict(data)
        
        assert restored == original


class TestConfigurationManager:
    """Test ConfigurationManager functionality."""
    
    def test_load_nonexistent_file_returns_defaults(self):
        """Test loading from nonexistent file returns default configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'nonexistent.json'
            manager = ConfigurationManager(config_path)
            
            config = manager.load()
            
            assert config == AppConfig()
    
    def test_save_and_load(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config.json'
            manager = ConfigurationManager(config_path)
            
            # Create custom configuration
            original = AppConfig(
                protocol=ProtocolType.SRT,
                rtmp_port=3000,
                srt_port=9001,
                http_port=8080,
            )
            
            # Save configuration
            manager.save(original)
            
            # Load configuration
            loaded = manager.load()
            
            assert loaded == original
    
    def test_save_creates_directory(self):
        """Test that save creates parent directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'subdir' / 'config.json'
            manager = ConfigurationManager(config_path)
            
            config = AppConfig()
            manager.save(config)
            
            assert config_path.exists()
            assert config_path.parent.exists()
    
    def test_load_corrupted_file_returns_defaults(self):
        """Test loading corrupted JSON file returns defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config.json'
            
            # Write corrupted JSON
            with open(config_path, 'w') as f:
                f.write('{ invalid json }')
            
            manager = ConfigurationManager(config_path)
            config = manager.load()
            
            assert config == AppConfig()
    
    def test_validate_valid_config(self):
        """Test validation of valid configuration."""
        manager = ConfigurationManager()
        config = AppConfig()
        
        is_valid, error_msg = manager.validate(config)
        
        assert is_valid is True
        assert error_msg is None
    
    def test_validate_invalid_rtmp_port(self):
        """Test validation rejects invalid RTMP port."""
        manager = ConfigurationManager()
        
        # Port too low
        config = AppConfig(rtmp_port=1023)
        is_valid, error_msg = manager.validate(config)
        assert is_valid is False
        assert 'RTMP port' in error_msg
        
        # Port too high
        config = AppConfig(rtmp_port=65536)
        is_valid, error_msg = manager.validate(config)
        assert is_valid is False
        assert 'RTMP port' in error_msg
    
    def test_validate_invalid_srt_port(self):
        """Test validation rejects invalid SRT port."""
        manager = ConfigurationManager()
        
        config = AppConfig(srt_port=100)
        is_valid, error_msg = manager.validate(config)
        
        assert is_valid is False
        assert 'SRT port' in error_msg
    
    def test_validate_invalid_http_port(self):
        """Test validation rejects invalid HTTP port."""
        manager = ConfigurationManager()
        
        config = AppConfig(http_port=70000)
        is_valid, error_msg = manager.validate(config)
        
        assert is_valid is False
        assert 'HTTP port' in error_msg
    
    def test_validate_edge_case_ports(self):
        """Test validation accepts edge case valid ports."""
        manager = ConfigurationManager()
        
        # Minimum valid port
        config = AppConfig(rtmp_port=1024, srt_port=1024, http_port=1024)
        is_valid, error_msg = manager.validate(config)
        assert is_valid is True
        
        # Maximum valid port
        config = AppConfig(rtmp_port=65535, srt_port=65535, http_port=65535)
        is_valid, error_msg = manager.validate(config)
        assert is_valid is True
    
    def test_validate_negative_max_reconnect_attempts(self):
        """Test validation rejects negative max reconnect attempts."""
        manager = ConfigurationManager()
        
        config = AppConfig(max_reconnect_attempts=0)
        is_valid, error_msg = manager.validate(config)
        
        assert is_valid is False
        assert 'reconnect attempts' in error_msg
    
    def test_validate_negative_dimensions(self):
        """Test validation rejects negative frame dimensions."""
        manager = ConfigurationManager()
        
        config = AppConfig(frame_width=0)
        is_valid, error_msg = manager.validate(config)
        assert is_valid is False
        assert 'width' in error_msg
        
        config = AppConfig(frame_height=-1)
        is_valid, error_msg = manager.validate(config)
        assert is_valid is False
        assert 'height' in error_msg
    
    def test_validate_negative_fps(self):
        """Test validation rejects negative FPS."""
        manager = ConfigurationManager()
        
        config = AppConfig(fps=0)
        is_valid, error_msg = manager.validate(config)
        
        assert is_valid is False
        assert 'FPS' in error_msg
    
    def test_save_invalid_config_raises_error(self):
        """Test that saving invalid configuration raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config.json'
            manager = ConfigurationManager(config_path)
            
            invalid_config = AppConfig(rtmp_port=100)  # Invalid port
            
            with pytest.raises(ValueError, match='invalid configuration'):
                manager.save(invalid_config)
    
    def test_load_invalid_config_returns_defaults(self):
        """Test loading invalid configuration returns defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config.json'
            
            # Write invalid configuration
            with open(config_path, 'w') as f:
                json.dump({'rtmp_port': 100}, f)  # Invalid port
            
            manager = ConfigurationManager(config_path)
            config = manager.load()
            
            assert config == AppConfig()
    
    def test_reset_to_defaults(self):
        """Test resetting configuration to defaults."""
        manager = ConfigurationManager()
        
        config = manager.reset_to_defaults()
        
        assert config == AppConfig()
    
    def test_default_config_path(self):
        """Test that default config path uses APPDATA."""
        manager = ConfigurationManager()
        
        assert 'LocalVirtualCamera' in str(manager._config_path)
        assert 'config.json' in str(manager._config_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
