"""
Configuration management for RTMP Virtual Camera.

Handles loading, saving, validating, and providing access to user configuration.
"""
import json
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple
import os

log = logging.getLogger(__name__)


class ProtocolType(Enum):
    """Supported streaming protocol types."""
    RTMP = "rtmp"
    SRT = "srt"
    WEBRTC = "webrtc"


@dataclass
class AppConfig:
    """
    Application configuration data model.
    
    Attributes
    ----------
    protocol : ProtocolType
        Selected streaming protocol (RTMP, SRT, or WebRTC)
    rtmp_port : int
        Port number for RTMP server (default: 2935)
    srt_port : int
        Port number for SRT server (default: 9000)
    webrtc_enabled : bool
        Whether WebRTC protocol is enabled
    http_port : int
        Port number for HTTP info server (default: 8000)
    auto_reconnect : bool
        Whether automatic reconnection is enabled
    max_reconnect_attempts : int
        Maximum number of reconnection attempts (default: 10)
    frame_width : int
        Video frame width in pixels (default: 1280)
    frame_height : int
        Video frame height in pixels (default: 720)
    fps : int
        Target frames per second (default: 30)
    """
    protocol: ProtocolType = ProtocolType.RTMP
    rtmp_port: int = 2935
    srt_port: int = 9000
    webrtc_enabled: bool = False
    http_port: int = 8000
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 10
    frame_width: int = 1280
    frame_height: int = 720
    fps: int = 30
    
    def to_dict(self) -> dict:
        """
        Serialize configuration to dictionary for JSON storage.
        
        Returns
        -------
        dict
            Dictionary representation with enum values converted to strings
        """
        data = asdict(self)
        # Convert enum to string value
        data['protocol'] = self.protocol.value
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AppConfig':
        """
        Deserialize configuration from dictionary.
        
        Parameters
        ----------
        data : dict
            Dictionary containing configuration values
        
        Returns
        -------
        AppConfig
            Configuration instance with values from dictionary
        
        Raises
        ------
        ValueError
            If protocol value is invalid
        """
        # Convert protocol string to enum
        protocol_str = data.get('protocol', 'rtmp')
        try:
            protocol = ProtocolType(protocol_str)
        except ValueError:
            log.warning(f"Invalid protocol '{protocol_str}', defaulting to RTMP")
            protocol = ProtocolType.RTMP
        
        return cls(
            protocol=protocol,
            rtmp_port=data.get('rtmp_port', 2935),
            srt_port=data.get('srt_port', 9000),
            webrtc_enabled=data.get('webrtc_enabled', False),
            http_port=data.get('http_port', 8000),
            auto_reconnect=data.get('auto_reconnect', True),
            max_reconnect_attempts=data.get('max_reconnect_attempts', 10),
            frame_width=data.get('frame_width', 1280),
            frame_height=data.get('frame_height', 720),
            fps=data.get('fps', 30),
        )


class ConfigurationManager:
    """
    Manages application configuration persistence and validation.
    
    Handles loading configuration from disk, saving changes, validating
    settings, and providing default values.
    """
    
    # Default configuration location: %APPDATA%/LocalVirtualCamera/config.json
    DEFAULT_CONFIG_DIR = Path(os.getenv('APPDATA', '')) / 'LocalVirtualCamera'
    DEFAULT_CONFIG_FILE = 'config.json'
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager with optional custom config path.
        
        Parameters
        ----------
        config_path : Path, optional
            Custom path to configuration file. If None, uses default location
            in %APPDATA%/LocalVirtualCamera/config.json
        """
        if config_path is None:
            self._config_path = self.DEFAULT_CONFIG_DIR / self.DEFAULT_CONFIG_FILE
        else:
            self._config_path = Path(config_path)
        
        log.info(f"Configuration path: {self._config_path}")
    
    def load(self) -> AppConfig:
        """
        Load configuration from disk, return defaults if not found.
        
        Returns
        -------
        AppConfig
            Loaded configuration or default configuration if file doesn't exist
            or is invalid
        """
        if not self._config_path.exists():
            log.info("Configuration file not found, using defaults")
            return AppConfig()
        
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            config = AppConfig.from_dict(data)
            
            # Validate loaded configuration
            is_valid, error_msg = self.validate(config)
            if not is_valid:
                log.warning(f"Loaded configuration is invalid: {error_msg}")
                log.warning("Falling back to default configuration")
                return AppConfig()
            
            log.info("Configuration loaded successfully")
            return config
            
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse configuration file: {e}")
            log.info("Falling back to default configuration")
            return AppConfig()
        except Exception as e:
            log.error(f"Failed to load configuration: {e}")
            log.info("Falling back to default configuration")
            return AppConfig()
    
    def save(self, config: AppConfig) -> None:
        """
        Save configuration to disk.
        
        Parameters
        ----------
        config : AppConfig
            Configuration to save
        
        Raises
        ------
        IOError
            If unable to write configuration file
        """
        # Validate before saving
        is_valid, error_msg = self.validate(config)
        if not is_valid:
            raise ValueError(f"Cannot save invalid configuration: {error_msg}")
        
        # Ensure directory exists
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            data = config.to_dict()
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            log.info("Configuration saved successfully")
            
        except Exception as e:
            log.error(f"Failed to save configuration: {e}")
            raise IOError(f"Failed to save configuration: {e}")
    
    def validate(self, config: AppConfig) -> Tuple[bool, Optional[str]]:
        """
        Validate configuration, return (is_valid, error_message).
        
        Parameters
        ----------
        config : AppConfig
            Configuration to validate
        
        Returns
        -------
        tuple[bool, Optional[str]]
            (True, None) if valid, (False, error_message) if invalid
        """
        # Validate port numbers (1024-65535)
        if not (1024 <= config.rtmp_port <= 65535):
            return False, f"RTMP port {config.rtmp_port} out of valid range (1024-65535)"
        
        if not (1024 <= config.srt_port <= 65535):
            return False, f"SRT port {config.srt_port} out of valid range (1024-65535)"
        
        if not (1024 <= config.http_port <= 65535):
            return False, f"HTTP port {config.http_port} out of valid range (1024-65535)"
        
        # Validate protocol type
        if not isinstance(config.protocol, ProtocolType):
            return False, f"Invalid protocol type: {config.protocol}"
        
        # Validate positive integers
        if config.max_reconnect_attempts <= 0:
            return False, f"Max reconnect attempts must be positive: {config.max_reconnect_attempts}"
        
        if config.frame_width <= 0:
            return False, f"Frame width must be positive: {config.frame_width}"
        
        if config.frame_height <= 0:
            return False, f"Frame height must be positive: {config.frame_height}"
        
        if config.fps <= 0:
            return False, f"FPS must be positive: {config.fps}"
        
        # All validations passed
        return True, None
    
    def reset_to_defaults(self) -> AppConfig:
        """
        Reset configuration to default values.
        
        Returns
        -------
        AppConfig
            New configuration instance with default values
        """
        log.info("Resetting configuration to defaults")
        return AppConfig()
