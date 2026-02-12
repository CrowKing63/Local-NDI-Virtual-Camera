# Requirements Document

## Introduction

This document specifies requirements for improving the Local RTMP Virtual Camera application, which receives RTMP streams from Vision Pro/iOS devices and outputs them as a virtual webcam on Windows. The improvements focus on three key areas: connection stability, setup simplification, and protocol flexibility.

The current system uses FFmpeg as an RTMP server (port 2935), decodes H.264 streams to RGB24 frames, and outputs to Unity Capture virtual camera driver via pyvirtualcam. A system tray UI provides control, and an HTTP server (port 8000) displays connection information.

## Glossary

- **RTMP_Server**: The FFmpeg process that listens for incoming RTMP streams on port 2935
- **Virtual_Camera_Output**: The pyvirtualcam component that sends frames to Unity Capture driver
- **Frame_Decoder**: The FFmpeg subprocess that decodes H.264 to RGB24 frames
- **System_Tray_UI**: The pystray-based user interface in the Windows system tray
- **HTTP_Info_Server**: The aiohttp server on port 8000 that displays connection information
- **Streaming_Pipeline**: The complete data flow from RTMP input through decoder to virtual camera output
- **SRT_Protocol**: Secure Reliable Transport protocol for low-latency video streaming
- **WebRTC_Protocol**: Web Real-Time Communication protocol for peer-to-peer streaming
- **mDNS**: Multicast DNS for zero-configuration network service discovery
- **Installer**: The setup package that installs the application and all dependencies
- **Connection_State**: The current status of the streaming connection (disconnected, connecting, connected, reconnecting)
- **iOS_Sender**: The iOS/Vision Pro device running PRISM Live Studio or similar RTMP app
- **Network_Interruption**: Temporary loss of network connectivity between sender and receiver
- **Firewall_Rule**: Windows Firewall configuration allowing network traffic on specific ports
- **Dependency**: External software required for the application (FFmpeg, Unity Capture driver)

## Requirements

### Requirement 1: Connection Stability

**User Story:** As a user, I want the virtual camera to automatically recover from network interruptions, so that I don't have to manually restart streaming when my connection drops briefly.

#### Acceptance Criteria

1. WHEN the RTMP stream disconnects unexpectedly, THEN the RTMP_Server SHALL attempt to reconnect automatically
2. WHEN reconnection attempts are in progress, THEN the System_Tray_UI SHALL display the current Connection_State
3. WHEN the network connection is poor, THEN the Streaming_Pipeline SHALL continue operating with degraded quality rather than failing completely
4. WHEN the RTMP_Server detects a Network_Interruption, THEN the Virtual_Camera_Output SHALL display the last valid frame until reconnection succeeds
5. WHEN reconnection fails after maximum retry attempts, THEN the System_Tray_UI SHALL notify the user and provide a manual restart option
6. WHEN the stream reconnects successfully, THEN the System_Tray_UI SHALL update the Connection_State to connected
7. WHEN connection quality degrades, THEN the System_Tray_UI SHALL display a visual indicator of connection health

### Requirement 2: Setup Simplification

**User Story:** As a new user, I want a one-click installer that handles all dependencies, so that I can start using the virtual camera without manual configuration steps.

#### Acceptance Criteria

1. WHEN the user runs the Installer, THEN the Installer SHALL detect and install all missing Dependencies without user intervention
2. WHEN the Installer needs to install FFmpeg, THEN the Installer SHALL either bundle FFmpeg or download it automatically from a trusted source
3. WHEN the Installer installs the Unity Capture driver, THEN the Installer SHALL handle driver installation without requiring separate manual steps
4. WHEN the Installer needs to configure Windows Firewall, THEN the Installer SHALL create Firewall_Rules for required ports automatically
5. WHEN the Installer requires administrator privileges, THEN the Installer SHALL request elevation with a clear explanation
6. WHEN installation completes successfully, THEN the Installer SHALL launch the application and display first-run instructions
7. WHEN installation fails, THEN the Installer SHALL provide clear error messages and recovery instructions
8. WHEN the user uninstalls the application, THEN the Installer SHALL remove all installed Dependencies and Firewall_Rules

### Requirement 3: Protocol Flexibility - RTMP Core

**User Story:** As a user, I want RTMP to remain the primary protocol with excellent compatibility, so that I can use existing iOS apps without changes.

#### Acceptance Criteria

1. THE RTMP_Server SHALL maintain full compatibility with PRISM Live Studio and Larix Broadcaster
2. THE RTMP_Server SHALL support standard RTMP protocol on configurable port (default 2935)
3. WHEN an iOS_Sender connects via RTMP, THEN the Frame_Decoder SHALL decode H.264 streams with latency under 200ms
4. THE RTMP_Server SHALL handle multiple connection attempts gracefully without requiring restart
5. WHEN RTMP streaming is active, THEN the HTTP_Info_Server SHALL display the correct RTMP URL for the iOS_Sender

### Requirement 4: Protocol Flexibility - SRT Support

**User Story:** As an advanced user, I want SRT protocol support as an alternative to RTMP, so that I can achieve lower latency and better error recovery on challenging networks.

#### Acceptance Criteria

1. WHERE SRT protocol is selected, THE Streaming_Pipeline SHALL accept SRT streams as an alternative to RTMP
2. WHERE SRT protocol is selected, THE Frame_Decoder SHALL decode incoming SRT streams with latency under 150ms
3. WHERE SRT protocol is selected, THE System_Tray_UI SHALL display SRT connection URLs instead of RTMP URLs
4. WHEN network packet loss occurs, THE SRT_Protocol SHALL recover lost packets automatically
5. WHERE SRT protocol is selected, THE HTTP_Info_Server SHALL provide SRT-specific connection instructions
6. THE System_Tray_UI SHALL allow users to switch between RTMP and SRT protocols through settings

### Requirement 5: Protocol Flexibility - WebRTC with mDNS

**User Story:** As a user, I want zero-configuration local discovery via WebRTC with mDNS, so that my iOS device can find the virtual camera automatically without entering IP addresses.

#### Acceptance Criteria

1. WHERE WebRTC protocol is selected, THE Streaming_Pipeline SHALL advertise itself via mDNS on the local network
2. WHERE WebRTC protocol is selected, THE Streaming_Pipeline SHALL establish peer-to-peer connections without manual IP configuration
3. WHERE WebRTC protocol is selected, THE Frame_Decoder SHALL decode WebRTC video streams with latency under 200ms
4. WHEN an iOS_Sender discovers the service via mDNS, THEN the Streaming_Pipeline SHALL establish a WebRTC connection automatically
5. WHERE WebRTC protocol is selected, THE HTTP_Info_Server SHALL provide a QR code or link for easy iOS connection
6. THE System_Tray_UI SHALL allow users to enable or disable WebRTC protocol through settings
7. WHEN WebRTC connection fails, THEN the System_Tray_UI SHALL fall back to displaying manual RTMP connection instructions

### Requirement 6: Connection Status Visibility

**User Story:** As a user, I want clear visual indicators of connection status in the system tray, so that I always know whether my virtual camera is working correctly.

#### Acceptance Criteria

1. WHEN the Streaming_Pipeline is disconnected, THEN the System_Tray_UI SHALL display a gray or inactive icon
2. WHEN the Streaming_Pipeline is connecting or reconnecting, THEN the System_Tray_UI SHALL display an animated or yellow icon
3. WHEN the Streaming_Pipeline is connected and streaming, THEN the System_Tray_UI SHALL display a green or active icon
4. WHEN the user hovers over the tray icon, THEN the System_Tray_UI SHALL show a tooltip with current Connection_State details
5. WHEN the user clicks the tray icon, THEN the System_Tray_UI SHALL display a menu with connection status and available actions
6. WHEN connection quality is poor, THEN the System_Tray_UI SHALL display a warning indicator without disconnecting

### Requirement 7: Configuration Persistence

**User Story:** As a user, I want my protocol and connection preferences to be saved, so that I don't have to reconfigure settings every time I start the application.

#### Acceptance Criteria

1. WHEN the user selects a protocol preference, THEN the System_Tray_UI SHALL persist the selection to disk
2. WHEN the application starts, THEN the System_Tray_UI SHALL load and apply the saved protocol preference
3. WHEN the user changes port numbers, THEN the System_Tray_UI SHALL validate and persist the new port configuration
4. WHEN configuration is invalid or corrupted, THEN the System_Tray_UI SHALL fall back to default settings and notify the user
5. THE System_Tray_UI SHALL store configuration in a standard Windows location (AppData)

### Requirement 8: Error Handling and Diagnostics

**User Story:** As a user, I want clear error messages and diagnostic information when problems occur, so that I can troubleshoot issues or report bugs effectively.

#### Acceptance Criteria

1. WHEN FFmpeg fails to start, THEN the System_Tray_UI SHALL display a specific error message indicating FFmpeg is missing or invalid
2. WHEN the Virtual_Camera_Output fails to initialize, THEN the System_Tray_UI SHALL display a specific error message about the Unity Capture driver
3. WHEN port binding fails, THEN the System_Tray_UI SHALL display which port is in use and suggest alternatives
4. WHEN the Frame_Decoder encounters corrupted data, THEN the Frame_Decoder SHALL log the error and continue processing subsequent frames
5. THE System_Tray_UI SHALL provide a menu option to view recent logs
6. THE System_Tray_UI SHALL provide a menu option to export diagnostic information for bug reports
7. WHEN a critical error occurs, THEN the System_Tray_UI SHALL display a notification with actionable next steps

### Requirement 9: Performance and Resource Management

**User Story:** As a user, I want the virtual camera to use system resources efficiently, so that it doesn't impact other applications or drain my battery.

#### Acceptance Criteria

1. WHEN no stream is active, THEN the Streaming_Pipeline SHALL use minimal CPU and memory resources
2. WHEN streaming is active, THEN the Frame_Decoder SHALL use hardware acceleration where available
3. WHEN the Virtual_Camera_Output has no active consumers, THEN the Streaming_Pipeline SHALL reduce processing to save resources
4. THE Frame_Decoder SHALL maintain frame rate at 30 FPS under normal network conditions
5. THE Streaming_Pipeline SHALL limit memory usage to prevent system instability
6. WHEN system resources are constrained, THEN the Frame_Decoder SHALL reduce quality gracefully rather than dropping frames completely

### Requirement 10: Backward Compatibility

**User Story:** As an existing user, I want the improved version to work with my current setup, so that I don't lose functionality when upgrading.

#### Acceptance Criteria

1. THE RTMP_Server SHALL maintain the same default port (2935) and path structure as the current version
2. THE HTTP_Info_Server SHALL maintain the same default port (8000) as the current version
3. WHEN upgrading from a previous version, THEN the Installer SHALL preserve user settings where possible
4. THE Virtual_Camera_Output SHALL continue to work with existing applications that use Unity Capture driver
5. THE System_Tray_UI SHALL maintain familiar menu structure and basic operations from the current version
