# Implementation Plan: RTMP Virtual Camera Improvements

## Overview

This implementation plan breaks down the RTMP Virtual Camera improvements into incremental coding tasks. The approach prioritizes connection stability first, then configuration management, protocol flexibility, installer framework, and finally UI enhancements. Each task builds on previous work and includes testing sub-tasks to validate functionality early.

## Tasks

- [x] 1. Implement connection state management
  - [x] 1.1 Create ConnectionState and ConnectionHealth enums
    - Define enums in new `src/connection_manager.py` file
    - _Requirements: 1.1, 1.2, 1.6, 1.7_
  
  - [x] 1.2 Implement ConnectionManager class with state tracking
    - Implement state machine for connection states (disconnected, connecting, connected, reconnecting)
    - Add callbacks for state and health changes
    - Implement frame reception monitoring for health tracking
    - _Requirements: 1.1, 1.2, 1.6, 1.7, 6.1, 6.2, 6.3_
  
  - [ ]* 1.3 Write property test for connection state transitions
    - **Property 2: UI state reflects connection state**
    - **Validates: Requirements 1.2, 1.6, 1.7, 6.1, 6.2, 6.3, 6.4**
  
  - [x] 1.4 Implement automatic reconnection logic with exponential backoff
    - Add reconnection attempt counter and backoff calculation (1s, 2s, 4s, 8s, 16s, 30s max)
    - Implement max retry limit (10 attempts)
    - Add timer-based reconnection triggering
    - _Requirements: 1.1, 1.5_
  
  - [ ]* 1.5 Write property test for automatic reconnection
    - **Property 1: Automatic reconnection on disconnection**
    - **Validates: Requirements 1.1**
  
  - [x] 1.6 Implement connection health monitoring
    - Track frame reception timestamps
    - Calculate health based on frame rate (excellent: >28fps, good: 20-28fps, poor: 10-20fps, critical: <10fps)
    - Trigger health change callbacks
    - _Requirements: 1.7, 6.6_
  
  - [ ]* 1.7 Write property test for connection health indicator
    - **Property 5: Connection health indicator**
    - **Validates: Requirements 6.6**

- [ ] 2. Implement configuration management system
  - [x] 2.1 Create configuration data models
    - Define AppConfig dataclass with all settings (protocol, ports, reconnection settings, video settings)
    - Implement to_dict() and from_dict() methods for JSON serialization
    - Create ConfigurationManager class in new `src/config_manager.py` file
    - _Requirements: 7.1, 7.2, 7.5_
  
  - [x] 2.2 Implement configuration persistence
    - Implement load() method to read from AppData directory
    - Implement save() method to write to AppData directory
    - Handle missing configuration file (return defaults)
    - _Requirements: 7.1, 7.2, 7.5_
  
  - [ ]* 2.3 Write property test for configuration round-trip
    - **Property 24: Configuration persistence round-trip**
    - **Validates: Requirements 7.1, 7.2**
  
  - [x] 2.4 Implement configuration validation
    - Validate port numbers (1024-65535 range)
    - Validate enum values for protocol type
    - Validate positive integers for dimensions and FPS
    - Return validation errors with descriptive messages
    - _Requirements: 7.3, 7.4_
  
  - [ ]* 2.5 Write property test for port validation
    - **Property 25: Port validation and persistence**
    - **Validates: Requirements 7.3**
  
  - [x] 2.6 Implement configuration error recovery
    - Handle corrupted JSON files
    - Fall back to defaults on validation failure
    - Log configuration errors
    - _Requirements: 7.4_
  
  - [ ]* 2.7 Write property test for configuration error recovery
    - **Property 26: Configuration error recovery**
    - **Validates: Requirements 7.4**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement protocol abstraction layer
  - [x] 4.1 Create protocol adapter interfaces
    - Define ProtocolType enum (RTMP, SRT, WEBRTC)
    - Create abstract ProtocolAdapter base class in new `src/protocols/base.py`
    - Define interface methods: start(), stop(), get_connection_urls(), get_connection_instructions(), is_connected property
    - _Requirements: 3.1, 4.1, 5.1_
  
  - [x] 4.2 Implement RTMPAdapter
    - Refactor existing RTMP server code into RTMPAdapter class in `src/protocols/rtmp.py`
    - Implement all ProtocolAdapter interface methods
    - Maintain backward compatibility with existing RTMP functionality
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 10.1_
  
  - [ ]* 4.3 Write property test for RTMP port configurability
    - **Property 11: RTMP port configurability**
    - **Validates: Requirements 3.2**
  
  - [ ]* 4.4 Write property test for RTMP URL correctness
    - **Property 14: Correct RTMP URL display**
    - **Validates: Requirements 3.5**
  
  - [x] 4.5 Implement SRTAdapter
    - Create SRTAdapter class in `src/protocols/srt.py`
    - Use FFmpeg with SRT protocol support (`-protocol srt`)
    - Implement SRT-specific connection URL format (`srt://{ip}:{port}`)
    - Default port: 9000
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  
  - [ ]* 4.6 Write property test for SRT protocol support
    - **Property 15: SRT protocol support**
    - **Validates: Requirements 4.1, 4.2**
  
  - [x] 4.7 Implement WebRTCAdapter with mDNS
    - Create WebRTCAdapter class in `src/protocols/webrtc.py`
    - Integrate aiortc library for WebRTC signaling
    - Integrate zeroconf library for mDNS advertisement
    - Advertise service as `_rtmp-vcam._tcp.local.`
    - Implement peer-to-peer connection establishment
    - _Requirements: 5.1, 5.2, 5.4, 5.5_
  
  - [ ]* 4.8 Write property test for WebRTC mDNS advertisement
    - **Property 19: WebRTC mDNS advertisement**
    - **Validates: Requirements 5.1**
  
  - [x] 4.9 Implement ProtocolFactory
    - Create factory class in `src/protocols/factory.py`
    - Implement create_adapter() method to instantiate correct adapter based on ProtocolType
    - _Requirements: 3.1, 4.1, 5.1_
  
  - [ ]* 4.10 Write property test for protocol switching
    - **Property 18: Protocol switching**
    - **Validates: Requirements 4.6, 5.6**

- [ ] 5. Integrate connection manager with protocol adapters
  - [x] 5.1 Update FrameDecoder to work with protocol abstraction
    - Modify FrameDecoder to accept ProtocolAdapter instead of direct FFmpeg command
    - Update frame reading logic to handle different protocol sources
    - Add error callback for decode failures
    - _Requirements: 3.3, 4.2, 5.3_
  
  - [x] 5.2 Wire ConnectionManager with protocol adapters
    - Connect protocol adapter callbacks (on_connect, on_disconnect) to ConnectionManager
    - Connect FrameDecoder frame callback to ConnectionManager.report_frame_received()
    - Implement reconnection trigger to restart protocol adapter
    - _Requirements: 1.1, 1.4, 1.6_
  
  - [ ]* 5.3 Write property test for frame persistence during interruption
    - **Property 4: Frame persistence during interruption**
    - **Validates: Requirements 1.4**
  
  - [x] 5.4 Implement graceful degradation on poor network
    - Modify FrameDecoder to continue on decode errors
    - Display last valid frame when new frames fail to decode
    - Log errors but don't crash
    - _Requirements: 1.3, 8.4_
  
  - [ ]* 5.5 Write property test for graceful degradation
    - **Property 3: Graceful degradation on poor network**
    - **Validates: Requirements 1.3**
  
  - [ ]* 5.6 Write property test for decoder error recovery
    - **Property 31: Decoder error recovery**
    - **Validates: Requirements 8.4**

- [ ] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Enhance system tray UI with connection status
  - [x] 7.1 Update TrayApp to display connection state icons
    - Add icon assets for different states (gray, yellow, green, orange)
    - Implement update_connection_state() method to change icon based on ConnectionState
    - Implement update_connection_health() method to add health indicators
    - _Requirements: 6.1, 6.2, 6.3, 6.6_
  
  - [ ] 7.2 Implement connection status tooltip
    - Add tooltip showing current state, health, protocol, and uptime
    - Update tooltip on state/health changes
    - _Requirements: 6.4_
  
  - [ ] 7.3 Enhance tray menu with connection information
    - Add status line showing current state and health
    - Display connection URLs in menu
    - Add protocol selection submenu (RTMP, SRT, WebRTC)
    - _Requirements: 6.5, 4.6, 5.6_
  
  - [ ] 7.4 Implement error notification system
    - Add show_notification() method for system notifications
    - Add show_error() method for error dialogs
    - Implement notification levels (info, warning, error)
    - _Requirements: 1.5, 8.1, 8.2, 8.3, 8.7_
  
  - [ ]* 7.5 Write unit tests for tray UI state updates
    - Test icon changes for each connection state
    - Test tooltip content updates
    - Test menu structure and items
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [ ] 7.6 Add settings dialog for configuration
    - Create settings window with protocol selection, port configuration, and reconnection settings
    - Wire settings changes to ConfigurationManager
    - Validate settings before applying
    - _Requirements: 4.6, 5.6, 7.3_
  
  - [ ] 7.7 Add log viewer and diagnostic export
    - Implement "View Logs" menu option to display recent log entries
    - Implement "Export Diagnostics" menu option to save diagnostic info to file
    - Create DiagnosticInfo data model with system information
    - _Requirements: 8.5, 8.6_
  
  - [ ]* 7.8 Write property test for diagnostic functionality
    - **Property 32: Diagnostic functionality**
    - **Validates: Requirements 8.5, 8.6**

- [ ] 8. Implement enhanced error handling
  - [ ] 8.1 Add specific error messages for FFmpeg failures
    - Detect FFmpeg missing or invalid on startup
    - Display specific error message with download link
    - _Requirements: 8.1_
  
  - [ ]* 8.2 Write property test for FFmpeg error messaging
    - **Property 28: FFmpeg error messaging**
    - **Validates: Requirements 8.1**
  
  - [ ] 8.3 Add specific error messages for driver failures
    - Detect Unity Capture driver missing on startup
    - Display specific error message with installation instructions
    - _Requirements: 8.2_
  
  - [ ]* 8.4 Write property test for driver error messaging
    - **Property 29: Driver error messaging**
    - **Validates: Requirements 8.2**
  
  - [ ] 8.5 Add specific error messages for port conflicts
    - Detect port binding failures
    - Display which port is in use and suggest alternatives
    - _Requirements: 8.3_
  
  - [ ]* 8.6 Write property test for port conflict error messaging
    - **Property 30: Port conflict error messaging**
    - **Validates: Requirements 8.3**
  
  - [ ] 8.7 Implement critical error notification
    - Detect critical errors (FFmpeg crash, driver failure, port conflict)
    - Display notification with actionable next steps
    - _Requirements: 8.7_
  
  - [ ]* 8.8 Write property test for critical error notification
    - **Property 33: Critical error notification**
    - **Validates: Requirements 8.7**

- [ ] 9. Update main application to use new components
  - [ ] 9.1 Refactor Application class to use ConnectionManager
    - Replace direct state tracking with ConnectionManager
    - Wire ConnectionManager callbacks to TrayApp updates
    - _Requirements: 1.1, 1.2, 1.6, 1.7_
  
  - [ ] 9.2 Refactor Application class to use ConfigurationManager
    - Load configuration on startup
    - Apply configuration to protocol adapters and decoder
    - Save configuration on changes
    - _Requirements: 7.1, 7.2_
  
  - [ ] 9.3 Refactor Application class to use ProtocolFactory
    - Create protocol adapter based on configuration
    - Support protocol switching at runtime
    - Update URLs and instructions when protocol changes
    - _Requirements: 3.1, 4.1, 5.1, 4.6, 5.6_
  
  - [ ] 9.4 Implement backward compatibility checks
    - Ensure default ports match previous version (RTMP: 2935, HTTP: 8000)
    - Preserve existing menu structure and operations
    - _Requirements: 10.1, 10.2, 10.5_
  
  - [ ]* 9.5 Write property test for default port preservation
    - **Property 36: Default port preservation**
    - **Validates: Requirements 10.1, 10.2**

- [ ] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Implement installer framework
  - [ ] 11.1 Create DependencyManager class
    - Implement check_ffmpeg() to detect FFmpeg installation
    - Implement check_unity_capture() to detect driver installation
    - Create new `src/installer/dependency_manager.py` file
    - _Requirements: 2.1, 2.2, 2.3_
  
  - [ ] 11.2 Implement FFmpeg installation
    - Bundle FFmpeg executable with installer (or download from official source)
    - Implement install_ffmpeg() to copy/extract FFmpeg to application directory
    - Verify FFmpeg installation after completion
    - _Requirements: 2.2_
  
  - [ ]* 11.3 Write property test for complete dependency installation
    - **Property 6: Complete dependency installation**
    - **Validates: Requirements 2.1, 2.2, 2.3**
  
  - [ ] 11.4 Implement Unity Capture driver installation
    - Bundle Unity Capture driver installer
    - Implement install_unity_capture() to run driver installer silently
    - Verify driver installation after completion
    - _Requirements: 2.3_
  
  - [ ] 11.5 Implement firewall configuration
    - Implement configure_firewall() to create Windows Firewall rules
    - Use netsh command or Windows Firewall API
    - Create rules for RTMP (2935), SRT (9000), HTTP (8000) ports
    - _Requirements: 2.4_
  
  - [ ]* 11.6 Write property test for firewall configuration
    - **Property 7: Firewall configuration**
    - **Validates: Requirements 2.4**
  
  - [ ] 11.7 Implement privilege escalation
    - Check for administrator privileges on installer startup
    - Request elevation with clear explanation if needed
    - Use Windows UAC prompt
    - _Requirements: 2.5_
  
  - [ ]* 11.8 Write property test for privilege escalation
    - **Property 8: Privilege escalation**
    - **Validates: Requirements 2.5**
  
  - [ ] 11.9 Implement installation error handling
    - Catch installation failures for each dependency
    - Display clear error messages with recovery instructions
    - Log detailed error information
    - _Requirements: 2.7_
  
  - [ ]* 11.10 Write property test for installation error handling
    - **Property 9: Installation error handling**
    - **Validates: Requirements 2.7**
  
  - [ ] 11.11 Implement clean uninstallation
    - Implement remove_firewall_rules() to clean up firewall rules
    - Create uninstaller script to remove all components
    - Verify all artifacts are removed
    - _Requirements: 2.8_
  
  - [ ]* 11.12 Write property test for clean uninstallation
    - **Property 10: Clean uninstallation**
    - **Validates: Requirements 2.8**

- [ ] 12. Create installer package
  - [ ] 12.1 Create NSIS or Inno Setup installer script
    - Define installer metadata (name, version, publisher)
    - Specify installation directory (Program Files)
    - Include all application files and dependencies
    - _Requirements: 2.1, 2.2, 2.3_
  
  - [ ] 12.2 Integrate DependencyManager into installer
    - Call DependencyManager methods during installation
    - Handle installation failures gracefully
    - Display progress to user
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  
  - [ ] 12.3 Add first-run experience
    - Launch application after installation
    - Display welcome dialog with quick start instructions
    - Show connection URLs and QR code
    - _Requirements: 2.6_
  
  - [ ] 12.4 Implement upgrade path
    - Detect existing installation
    - Preserve user configuration during upgrade
    - Update only changed files
    - _Requirements: 10.3_
  
  - [ ]* 12.5 Write property test for settings preservation on upgrade
    - **Property 37: Settings preservation on upgrade**
    - **Validates: Requirements 10.3**

- [ ] 13. Update HTTP info server for protocol flexibility
  - [ ] 13.1 Update HTTP server to display protocol-specific instructions
    - Modify index page to show instructions based on active protocol
    - Display RTMP, SRT, or WebRTC connection information
    - _Requirements: 3.5, 4.5, 5.5_
  
  - [ ] 13.2 Add QR code generation for WebRTC
    - Generate QR code containing WebRTC connection URL
    - Display QR code on HTTP info page when WebRTC is active
    - _Requirements: 5.5_
  
  - [ ]* 13.3 Write property test for SRT UI correctness
    - **Property 16: SRT UI correctness**
    - **Validates: Requirements 4.3, 4.5**
  
  - [ ]* 13.4 Write property test for WebRTC connection aids
    - **Property 22: WebRTC connection aids**
    - **Validates: Requirements 5.5**

- [ ] 14. Final integration and testing
  - [ ] 14.1 Integration test: Fresh installation to streaming
    - Test complete flow from installer to first stream
    - Verify all dependencies installed correctly
    - Verify streaming works with RTMP
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1_
  
  - [ ] 14.2 Integration test: Network interruption and reconnection
    - Simulate network disconnection during streaming
    - Verify automatic reconnection attempts
    - Verify video resumes after reconnection
    - _Requirements: 1.1, 1.4, 1.6_
  
  - [ ] 14.3 Integration test: Protocol switching
    - Start streaming with RTMP
    - Switch to SRT protocol
    - Verify URLs update and new protocol works
    - Switch to WebRTC and verify
    - _Requirements: 4.6, 5.6_
  
  - [ ] 14.4 Integration test: Configuration persistence
    - Change protocol and port settings
    - Restart application
    - Verify settings are restored
    - _Requirements: 7.1, 7.2_
  
  - [ ] 14.5 Performance test: Latency measurement
    - Measure end-to-end latency for RTMP (target: <200ms)
    - Measure end-to-end latency for SRT (target: <150ms)
    - Measure end-to-end latency for WebRTC (target: <200ms)
    - _Requirements: 3.3, 4.2, 5.3_
  
  - [ ]* 14.6 Write property test for RTMP latency requirement
    - **Property 12: RTMP latency requirement**
    - **Validates: Requirements 3.3**
  
  - [ ]* 14.7 Write property test for SRT latency requirement
    - **Property 15: SRT protocol support** (includes latency)
    - **Validates: Requirements 4.2**
  
  - [ ]* 14.8 Write property test for WebRTC latency requirement
    - **Property 21: WebRTC latency requirement**
    - **Validates: Requirements 5.3**

- [ ] 15. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at major milestones
- Property tests validate universal correctness properties across all inputs
- Unit tests validate specific examples and edge cases
- Integration tests verify end-to-end functionality
- Performance tests measure latency requirements
