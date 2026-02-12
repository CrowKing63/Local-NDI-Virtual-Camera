# Design Document: RTMP Virtual Camera Improvements

## Overview

This design enhances the Local RTMP Virtual Camera application with three major improvements: connection stability through automatic reconnection, simplified setup via a comprehensive installer, and protocol flexibility with SRT and WebRTC support alongside RTMP.

The architecture maintains the existing pipeline structure (RTMP Server → Frame Decoder → Virtual Camera Output) while adding:
- Connection state management with automatic reconnection logic
- Protocol abstraction layer supporting RTMP, SRT, and WebRTC
- Installer framework with dependency management
- Enhanced UI with connection status indicators
- Configuration persistence system

The design prioritizes backward compatibility, maintaining existing RTMP functionality while adding new capabilities as opt-in features.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      System Tray UI                         │
│  (Connection Status, Protocol Selection, Settings)          │
└────────────┬────────────────────────────────────────────────┘
             │
             ├──────────────────────────────────────────────┐
             │                                              │
┌────────────▼──────────┐                    ┌──────────────▼─────────┐
│  Connection Manager   │                    │  Configuration Manager │
│  - State tracking     │                    │  - Load/save settings  │
│  - Reconnection logic │                    │  - Validation          │
│  - Health monitoring  │                    │  - Defaults            │
└────────────┬──────────┘                    └────────────────────────┘
             │
┌────────────▼──────────────────────────────────────────────┐
│              Protocol Abstraction Layer                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐        │
│  │   RTMP   │  │   SRT    │  │  WebRTC + mDNS   │        │
│  │ Adapter  │  │ Adapter  │  │     Adapter      │        │
│  └──────────┘  └──────────┘  └──────────────────┘        │
└────────────┬──────────────────────────────────────────────┘
             │
┌────────────▼──────────┐
│    Frame Decoder      │
│  (FFmpeg subprocess)  │
└────────────┬──────────┘
             │
┌────────────▼──────────┐
│ Virtual Camera Output │
│   (pyvirtualcam)      │
└───────────────────────┘
```

### Component Interactions

1. **System Tray UI** receives user input and displays connection status
2. **Configuration Manager** persists and loads user preferences
3. **Connection Manager** monitors connection health and triggers reconnection
4. **Protocol Abstraction Layer** provides unified interface for different streaming protocols
5. **Frame Decoder** receives frames from active protocol adapter
6. **Virtual Camera Output** sends decoded frames to Unity Capture driver

### State Machine for Connection Management

```
┌─────────────┐
│ Disconnected│
└──────┬──────┘
       │ start_streaming()
       ▼
┌─────────────┐
│ Connecting  │
└──────┬──────┘
       │ connection_established
       ▼
┌─────────────┐     network_interruption
│  Connected  ├──────────────────────┐
└──────┬──────┘                      │
       │ stop_streaming()            ▼
       │                      ┌──────────────┐
       │                      │ Reconnecting │
       │                      └──────┬───────┘
       │                             │ reconnect_success
       │                             └──────────┐
       ▼                                        │
┌─────────────┐                                 │
│ Disconnected│◄────────────────────────────────┘
└─────────────┘     max_retries_exceeded
```

## Components and Interfaces

### 1. Connection Manager

**Responsibility:** Monitor connection health, manage reconnection attempts, and track connection state.

**Interface:**
```python
class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"

class ConnectionHealth(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    POOR = "poor"
    CRITICAL = "critical"

class ConnectionManager:
    def __init__(self, 
                 on_state_change: Callable[[ConnectionState], None],
                 on_health_change: Callable[[ConnectionHealth], None]):
        """Initialize connection manager with callbacks for state changes."""
        pass
    
    def start_monitoring(self) -> None:
        """Begin monitoring connection health."""
        pass
    
    def stop_monitoring(self) -> None:
        """Stop monitoring connection health."""
        pass
    
    def report_connection_established(self) -> None:
        """Called by protocol adapter when connection succeeds."""
        pass
    
    def report_connection_lost(self) -> None:
        """Called by protocol adapter when connection drops."""
        pass
    
    def report_frame_received(self) -> None:
        """Called by decoder when frame is successfully decoded."""
        pass
    
    def trigger_reconnect(self) -> None:
        """Manually trigger reconnection attempt."""
        pass
    
    @property
    def current_state(self) -> ConnectionState:
        """Get current connection state."""
        pass
    
    @property
    def current_health(self) -> ConnectionHealth:
        """Get current connection health."""
        pass
```

**Reconnection Logic:**
- Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (max)
- Maximum retry attempts: 10
- Reset retry count on successful connection
- Health monitoring based on frame reception rate

### 2. Protocol Abstraction Layer

**Responsibility:** Provide unified interface for different streaming protocols (RTMP, SRT, WebRTC).

**Interface:**
```python
class ProtocolType(Enum):
    RTMP = "rtmp"
    SRT = "srt"
    WEBRTC = "webrtc"

class ProtocolAdapter(ABC):
    @abstractmethod
    async def start(self, port: int, path: str) -> None:
        """Start listening for incoming streams."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop listening and clean up resources."""
        pass
    
    @abstractmethod
    def get_connection_urls(self, local_ips: List[str]) -> List[str]:
        """Return connection URLs for iOS sender."""
        pass
    
    @abstractmethod
    def get_connection_instructions(self) -> str:
        """Return human-readable connection instructions."""
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if a sender is currently connected."""
        pass

class RTMPAdapter(ProtocolAdapter):
    """RTMP protocol implementation using FFmpeg."""
    pass

class SRTAdapter(ProtocolAdapter):
    """SRT protocol implementation using FFmpeg with SRT support."""
    pass

class WebRTCAdapter(ProtocolAdapter):
    """WebRTC protocol implementation with mDNS discovery."""
    pass

class ProtocolFactory:
    @staticmethod
    def create_adapter(protocol_type: ProtocolType,
                      on_connect: Callable[[], None],
                      on_disconnect: Callable[[], None]) -> ProtocolAdapter:
        """Factory method to create appropriate protocol adapter."""
        pass
```

**Protocol-Specific Details:**

**RTMP Adapter:**
- Uses existing FFmpeg RTMP server implementation
- Default port: 2935
- Path: /live/stream
- Connection URL format: `rtmp://{ip}:{port}/{path}`

**SRT Adapter:**
- Uses FFmpeg with SRT protocol support
- Default port: 9000
- Connection URL format: `srt://{ip}:{port}`
- Requires FFmpeg compiled with libsrt

**WebRTC Adapter:**
- Uses aiortc library for WebRTC signaling
- Uses zeroconf library for mDNS advertisement
- Service name: `_rtmp-vcam._tcp.local.`
- Provides web interface for connection establishment
- Fallback to manual connection if mDNS fails

### 3. Configuration Manager

**Responsibility:** Load, validate, save, and provide access to user configuration.

**Interface:**
```python
@dataclass
class AppConfig:
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

class ConfigurationManager:
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize with optional custom config path."""
        pass
    
    def load(self) -> AppConfig:
        """Load configuration from disk, return defaults if not found."""
        pass
    
    def save(self, config: AppConfig) -> None:
        """Save configuration to disk."""
        pass
    
    def validate(self, config: AppConfig) -> Tuple[bool, Optional[str]]:
        """Validate configuration, return (is_valid, error_message)."""
        pass
    
    def reset_to_defaults(self) -> AppConfig:
        """Reset configuration to default values."""
        pass
```

**Configuration Storage:**
- Location: `%APPDATA%\LocalVirtualCamera\config.json`
- Format: JSON
- Validation: Port ranges (1024-65535), enum values, positive integers

### 4. Enhanced System Tray UI

**Responsibility:** Display connection status, provide user controls, show notifications.

**Interface:**
```python
class TrayApp:
    def __init__(self,
                 on_start: Callable[[], None],
                 on_stop: Callable[[], None],
                 on_protocol_change: Callable[[ProtocolType], None],
                 on_settings: Callable[[], None],
                 on_exit: Callable[[], None]):
        """Initialize tray app with callbacks."""
        pass
    
    def run(self) -> None:
        """Start the tray icon (blocks on main thread)."""
        pass
    
    def update_connection_state(self, state: ConnectionState) -> None:
        """Update tray icon based on connection state."""
        pass
    
    def update_connection_health(self, health: ConnectionHealth) -> None:
        """Update tray icon indicator for connection health."""
        pass
    
    def set_connection_urls(self, urls: List[str]) -> None:
        """Update displayed connection URLs."""
        pass
    
    def show_notification(self, title: str, message: str, 
                         level: NotificationLevel) -> None:
        """Display system notification."""
        pass
    
    def show_error(self, error: str, details: Optional[str] = None) -> None:
        """Display error message with optional details."""
        pass
```

**Icon States:**
- Disconnected: Gray camera icon
- Connecting: Yellow camera icon with animation
- Connected (excellent): Green camera icon
- Connected (poor): Yellow camera icon with warning badge
- Reconnecting: Orange camera icon with animation

**Menu Structure:**
```
Local Virtual Camera
├── Status: Connected (Excellent)
├── Connection URLs
│   └── rtmp://192.168.1.100:2935/live/stream
├── ───────────────
├── Start Streaming
├── Stop Streaming
├── ───────────────
├── Protocol
│   ├── ● RTMP (Default)
│   ├── ○ SRT
│   └── ○ WebRTC + mDNS
├── Settings
├── View Logs
├── Export Diagnostics
├── ───────────────
└── Exit
```

### 5. Installer Framework

**Responsibility:** Install application, dependencies, and configure system.

**Components:**

**Installer Script (NSIS or Inno Setup):**
```
[Setup]
AppName=Local RTMP Virtual Camera
AppVersion=2.0
DefaultDirName={autopf}\LocalVirtualCamera
PrivilegesRequired=admin
```

**Dependency Manager:**
```python
class DependencyManager:
    def check_ffmpeg(self) -> bool:
        """Check if FFmpeg is installed and accessible."""
        pass
    
    def install_ffmpeg(self) -> bool:
        """Install bundled FFmpeg or download from official source."""
        pass
    
    def check_unity_capture(self) -> bool:
        """Check if Unity Capture driver is installed."""
        pass
    
    def install_unity_capture(self) -> bool:
        """Install Unity Capture driver."""
        pass
    
    def configure_firewall(self, ports: List[int]) -> bool:
        """Create Windows Firewall rules for required ports."""
        pass
    
    def remove_firewall_rules(self) -> bool:
        """Remove firewall rules during uninstall."""
        pass
```

**Installation Steps:**
1. Check for administrator privileges, request elevation if needed
2. Install application files to Program Files
3. Check for FFmpeg, install if missing (bundled or download)
4. Check for Unity Capture driver, install if missing
5. Create firewall rules for RTMP (2935), SRT (9000), HTTP (8000)
6. Create start menu shortcuts
7. Optionally launch application
8. Display first-run instructions

**FFmpeg Bundling Strategy:**
- Bundle FFmpeg executable (ffmpeg.exe) with installer (~100MB)
- Alternative: Download from official FFmpeg builds during installation
- Verify FFmpeg signature/checksum for security
- Place in application directory, add to PATH

### 6. Enhanced Frame Decoder

**Responsibility:** Decode video frames from protocol adapter, handle errors gracefully.

**Interface:**
```python
class FrameDecoder:
    def __init__(self,
                 width: int,
                 height: int,
                 on_frame: Callable[[np.ndarray], None],
                 on_error: Callable[[str], None]):
        """Initialize decoder with frame callback."""
        pass
    
    def start(self, protocol_adapter: ProtocolAdapter) -> None:
        """Start decoding from protocol adapter."""
        pass
    
    def stop(self) -> None:
        """Stop decoding and clean up."""
        pass
    
    @property
    def latest_frame(self) -> Optional[np.ndarray]:
        """Get most recent decoded frame."""
        pass
    
    @property
    def frame_count(self) -> int:
        """Get total frames decoded since start."""
        pass
    
    @property
    def error_count(self) -> int:
        """Get total decode errors since start."""
        pass
```

**Error Handling:**
- Log decode errors but continue processing
- Track error rate for health monitoring
- Display last valid frame on temporary errors
- Notify connection manager of persistent errors

## Data Models

### Configuration Data Model

```python
@dataclass
class AppConfig:
    """Application configuration."""
    protocol: ProtocolType
    rtmp_port: int
    srt_port: int
    webrtc_enabled: bool
    http_port: int
    auto_reconnect: bool
    max_reconnect_attempts: int
    frame_width: int
    frame_height: int
    fps: int
    
    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        pass
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AppConfig':
        """Deserialize from dictionary."""
        pass
```

### Connection State Data Model

```python
@dataclass
class ConnectionInfo:
    """Current connection information."""
    state: ConnectionState
    health: ConnectionHealth
    protocol: ProtocolType
    connected_since: Optional[datetime]
    last_frame_time: Optional[datetime]
    total_frames: int
    dropped_frames: int
    reconnect_attempts: int
    
    def to_dict(self) -> dict:
        """Serialize for diagnostics export."""
        pass
```

### Diagnostic Data Model

```python
@dataclass
class DiagnosticInfo:
    """System diagnostic information."""
    app_version: str
    os_version: str
    python_version: str
    ffmpeg_version: Optional[str]
    unity_capture_installed: bool
    config: AppConfig
    connection: ConnectionInfo
    recent_logs: List[str]
    
    def to_json(self) -> str:
        """Export as JSON for bug reports."""
        pass
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Connection Stability Properties

Property 1: Automatic reconnection on disconnection
*For any* unexpected stream disconnection, the system should automatically trigger reconnection attempts with exponential backoff
**Validates: Requirements 1.1**

Property 2: UI state reflects connection state
*For any* connection state change (disconnected, connecting, connected, reconnecting), the system tray UI should display the corresponding visual indicator (gray, yellow/animated, green, orange/animated) and tooltip information
**Validates: Requirements 1.2, 1.6, 1.7, 6.1, 6.2, 6.3, 6.4**

Property 3: Graceful degradation on poor network
*For any* network quality degradation, the streaming pipeline should continue operating with reduced quality rather than failing completely
**Validates: Requirements 1.3**

Property 4: Frame persistence during interruption
*For any* network interruption, the virtual camera output should continue displaying the last valid frame until reconnection succeeds or streaming stops
**Validates: Requirements 1.4**

Property 5: Connection health indicator
*For any* connection quality level (excellent, good, poor, critical), the system tray UI should display the appropriate health indicator without disconnecting unless critical
**Validates: Requirements 6.6**

### Installer Properties

Property 6: Complete dependency installation
*For any* missing dependency (FFmpeg, Unity Capture driver), the installer should detect and install it without user intervention
**Validates: Requirements 2.1, 2.2, 2.3**

Property 7: Firewall configuration
*For any* required port (RTMP, SRT, HTTP), the installer should create Windows Firewall rules automatically during installation
**Validates: Requirements 2.4**

Property 8: Privilege escalation
*For any* installation requiring administrator privileges, the installer should request elevation with a clear explanation before proceeding
**Validates: Requirements 2.5**

Property 9: Installation error handling
*For any* installation failure, the installer should provide a clear error message and recovery instructions
**Validates: Requirements 2.7**

Property 10: Clean uninstallation
*For any* installed component (application, dependencies, firewall rules), the uninstaller should remove all artifacts, returning the system to pre-installation state
**Validates: Requirements 2.8**

### Protocol Support Properties

Property 11: RTMP port configurability
*For any* valid port number (1024-65535), the RTMP server should accept connections on the configured port
**Validates: Requirements 3.2**

Property 12: RTMP latency requirement
*For any* RTMP stream from an iOS sender, the frame decoder should decode H.264 frames with end-to-end latency under 200ms under normal network conditions
**Validates: Requirements 3.3**

Property 13: Multiple connection attempts
*For any* sequence of connection attempts (connect, disconnect, reconnect), the RTMP server should handle them gracefully without requiring restart
**Validates: Requirements 3.4**

Property 14: Correct RTMP URL display
*For any* active RTMP streaming session, the HTTP info server should display connection URLs that match the actual server configuration (IP addresses and port)
**Validates: Requirements 3.5**

Property 15: SRT protocol support
*For any* SRT stream when SRT protocol is selected, the streaming pipeline should accept and decode the stream with latency under 150ms
**Validates: Requirements 4.1, 4.2**

Property 16: SRT UI correctness
*For any* SRT protocol selection, the system tray UI and HTTP info server should display SRT-specific connection URLs and instructions instead of RTMP
**Validates: Requirements 4.3, 4.5**

Property 17: SRT packet recovery
*For any* network packet loss event during SRT streaming, the SRT protocol should automatically recover lost packets without stream interruption
**Validates: Requirements 4.4**

Property 18: Protocol switching
*For any* protocol selection change (RTMP ↔ SRT ↔ WebRTC), the system tray UI should apply the new protocol and update all displayed information accordingly
**Validates: Requirements 4.6, 5.6**

Property 19: WebRTC mDNS advertisement
*For any* WebRTC protocol selection, the streaming pipeline should advertise itself via mDNS on the local network with the correct service name
**Validates: Requirements 5.1**

Property 20: WebRTC zero-config connection
*For any* WebRTC protocol selection, the streaming pipeline should establish peer-to-peer connections without requiring manual IP address configuration
**Validates: Requirements 5.2, 5.4**

Property 21: WebRTC latency requirement
*For any* WebRTC stream, the frame decoder should decode video frames with end-to-end latency under 200ms under normal network conditions
**Validates: Requirements 5.3**

Property 22: WebRTC connection aids
*For any* WebRTC protocol selection, the HTTP info server should provide a QR code or connection link for easy iOS device connection
**Validates: Requirements 5.5**

Property 23: WebRTC fallback
*For any* WebRTC connection failure, the system tray UI should display fallback instructions for manual RTMP connection
**Validates: Requirements 5.7**

### Configuration Properties

Property 24: Configuration persistence round-trip
*For any* valid configuration change (protocol selection, port numbers), saving then loading the configuration should restore the exact same settings
**Validates: Requirements 7.1, 7.2**

Property 25: Port validation and persistence
*For any* port number change, the system should validate the port is in the valid range (1024-65535) before persisting, and reject invalid values
**Validates: Requirements 7.3**

Property 26: Configuration error recovery
*For any* invalid or corrupted configuration file, the system should fall back to default settings, notify the user, and continue operating
**Validates: Requirements 7.4**

Property 27: Configuration file location
*For any* configuration save operation, the configuration file should be stored in the Windows AppData directory at the expected path
**Validates: Requirements 7.5**

### Error Handling Properties

Property 28: FFmpeg error messaging
*For any* FFmpeg startup failure, the system tray UI should display a specific error message indicating FFmpeg is missing or invalid
**Validates: Requirements 8.1**

Property 29: Driver error messaging
*For any* Unity Capture driver initialization failure, the system tray UI should display a specific error message about the driver
**Validates: Requirements 8.2**

Property 30: Port conflict error messaging
*For any* port binding failure, the system tray UI should display which port is in use and suggest alternative ports
**Validates: Requirements 8.3**

Property 31: Decoder error recovery
*For any* corrupted frame data, the frame decoder should log the error and continue processing subsequent frames without crashing
**Validates: Requirements 8.4**

Property 32: Diagnostic functionality
*For any* user request, the system tray UI should provide menu options to view recent logs and export diagnostic information
**Validates: Requirements 8.5, 8.6**

Property 33: Critical error notification
*For any* critical error (FFmpeg crash, driver failure, port conflict), the system tray UI should display a notification with actionable next steps
**Validates: Requirements 8.7**

### Performance Properties

Property 34: Hardware acceleration usage
*For any* streaming session when hardware acceleration is available, the frame decoder should enable and use hardware acceleration for decoding
**Validates: Requirements 9.2**

Property 35: Frame rate maintenance
*For any* streaming session under normal network conditions, the frame decoder should maintain a frame rate of 30 FPS (±2 FPS tolerance)
**Validates: Requirements 9.4**

### Backward Compatibility Properties

Property 36: Default port preservation
*For any* fresh installation or configuration reset, the system should use the same default ports as the previous version (RTMP: 2935, HTTP: 8000)
**Validates: Requirements 10.1, 10.2**

Property 37: Settings preservation on upgrade
*For any* upgrade from a previous version, the installer should preserve existing user settings (protocol, ports, preferences) where possible
**Validates: Requirements 10.3**

## Error Handling

### Error Categories

**1. Dependency Errors**
- FFmpeg not found or invalid
- Unity Capture driver not installed
- Python dependencies missing

**Strategy:**
- Check dependencies on startup
- Display specific error messages with installation instructions
- Provide links to download pages
- Soft-fail for non-critical components (e.g., virtual camera can fail but network server continues)

**2. Network Errors**
- Port already in use
- Firewall blocking connections
- Network interface unavailable

**Strategy:**
- Attempt to bind to alternative ports if default is unavailable
- Provide clear error messages indicating which port is blocked
- Suggest firewall configuration steps
- Display all available network interfaces

**3. Connection Errors**
- Stream disconnection
- Decode errors
- Protocol negotiation failures

**Strategy:**
- Automatic reconnection with exponential backoff
- Display last valid frame during interruption
- Log errors for diagnostics
- Notify user after max retry attempts

**4. Configuration Errors**
- Invalid configuration file
- Corrupted settings
- Invalid port numbers

**Strategy:**
- Validate all configuration values on load
- Fall back to defaults for invalid values
- Notify user of configuration issues
- Provide configuration reset option

### Error Recovery Patterns

**Transient Errors:**
- Retry with exponential backoff
- Maximum retry attempts: 10
- Backoff sequence: 1s, 2s, 4s, 8s, 16s, 30s (max)

**Permanent Errors:**
- Display error notification
- Provide manual recovery options
- Log detailed error information
- Offer diagnostic export

**Graceful Degradation:**
- Continue operation with reduced functionality
- Display warnings but don't block usage
- Example: Virtual camera fails but network server continues for testing

## Testing Strategy

### Dual Testing Approach

This feature requires both unit testing and property-based testing for comprehensive coverage:

**Unit Tests:** Focus on specific examples, edge cases, and integration points
- Specific connection scenarios (first connection, reconnection after 5 attempts)
- Edge cases (port 1024, port 65535, invalid port 0)
- Error conditions (FFmpeg missing, driver not installed)
- Integration between components (connection manager → tray UI updates)

**Property Tests:** Verify universal properties across all inputs
- Connection state transitions for any disconnection event
- Configuration round-trip for any valid settings
- Protocol switching for any protocol combination
- Error recovery for any corrupted frame data

### Property-Based Testing Configuration

**Library:** Use `hypothesis` for Python property-based testing

**Test Configuration:**
- Minimum 100 iterations per property test (due to randomization)
- Each property test must reference its design document property
- Tag format: `# Feature: rtmp-vcam-improvements, Property {number}: {property_text}`

**Example Property Test Structure:**
```python
from hypothesis import given, strategies as st
import pytest

# Feature: rtmp-vcam-improvements, Property 24: Configuration persistence round-trip
@given(
    protocol=st.sampled_from([ProtocolType.RTMP, ProtocolType.SRT, ProtocolType.WEBRTC]),
    rtmp_port=st.integers(min_value=1024, max_value=65535),
    srt_port=st.integers(min_value=1024, max_value=65535),
    http_port=st.integers(min_value=1024, max_value=65535),
)
def test_config_round_trip(protocol, rtmp_port, srt_port, http_port):
    """For any valid configuration, saving then loading should restore exact settings."""
    config = AppConfig(
        protocol=protocol,
        rtmp_port=rtmp_port,
        srt_port=srt_port,
        http_port=http_port,
    )
    
    config_manager = ConfigurationManager()
    config_manager.save(config)
    loaded_config = config_manager.load()
    
    assert loaded_config == config
```

### Test Coverage Requirements

**Connection Manager:**
- Unit tests: Specific reconnection scenarios, state transitions
- Property tests: State consistency, reconnection behavior for any disconnection

**Protocol Adapters:**
- Unit tests: RTMP connection with PRISM Live Studio format
- Property tests: URL generation for any IP/port combination

**Configuration Manager:**
- Unit tests: Default values, specific invalid configurations
- Property tests: Round-trip for any valid configuration, fallback for any invalid configuration

**Installer:**
- Unit tests: Specific dependency installation scenarios
- Property tests: Complete installation for any missing dependency combination

**System Tray UI:**
- Unit tests: Specific menu interactions, icon state changes
- Property tests: UI state reflects connection state for any state change

### Integration Testing

**End-to-End Scenarios:**
1. Fresh installation → Start streaming → Connect from iOS → Verify video output
2. Disconnect network → Verify reconnection → Verify video resumes
3. Switch protocols → Verify new protocol works → Verify URLs update
4. Save configuration → Restart application → Verify settings restored
5. Simulate errors → Verify error messages → Verify recovery options

**Performance Testing:**
- Measure latency for RTMP, SRT, WebRTC protocols
- Verify frame rate maintenance under various network conditions
- Monitor resource usage (CPU, memory) during streaming

**Compatibility Testing:**
- Test with PRISM Live Studio on iOS
- Test with Larix Broadcaster on iOS
- Test with various Windows applications (Zoom, OBS, Teams)
- Test on Windows 10 and Windows 11

### Mocking Strategy

**External Dependencies:**
- Mock FFmpeg subprocess for unit tests
- Mock Unity Capture driver for unit tests
- Mock network interfaces for protocol adapter tests
- Mock file system for configuration tests

**Integration Points:**
- Use real FFmpeg for integration tests
- Use real network sockets for protocol tests
- Use real file system for installer tests
