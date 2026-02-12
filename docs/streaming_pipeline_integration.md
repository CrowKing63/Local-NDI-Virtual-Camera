# Streaming Pipeline Integration

## Overview

Task 5.2 has been completed, implementing the integration between `ConnectionManager`, protocol adapters (RTMP, SRT, WebRTC), and `FrameDecoder`. This creates a complete streaming pipeline with automatic reconnection and health monitoring.

## What Was Implemented

### 1. StreamingPipeline Class (`src/streaming_pipeline.py`)

A high-level integration class that wires together all components:

- **Automatic Wiring**: Automatically connects protocol adapter callbacks and frame decoder callbacks to ConnectionManager
- **Lifecycle Management**: Handles starting/stopping all components in the correct order
- **Reconnection Logic**: Implements reconnection trigger that restarts protocol adapter and decoder
- **State Forwarding**: Forwards connection state and health changes to user callbacks

**Key Features:**
- Starts protocol adapter, frame decoder, and connection monitoring
- Wires `on_connect` → `ConnectionManager.report_connection_established()`
- Wires `on_disconnect` → `ConnectionManager.report_connection_lost()`
- Wires `on_frame` → `ConnectionManager.report_frame_received()`
- Implements reconnection trigger to restart protocol adapter

### 2. Helper Functions

Two helper functions for manual wiring when needed:

- `create_wired_protocol_adapter()`: Wires a protocol adapter to ConnectionManager
- `create_wired_frame_decoder()`: Wires a frame decoder to ConnectionManager

These preserve original callbacks while adding ConnectionManager integration.

### 3. Comprehensive Tests (`src/test_streaming_pipeline.py`)

Complete test suite covering:

**Protocol Adapter Wiring:**
- Connection events trigger ConnectionManager state changes
- Disconnection events trigger ConnectionManager state changes
- Original callbacks are preserved

**Frame Decoder Wiring:**
- Frame events trigger ConnectionManager health monitoring
- Original callbacks are preserved

**Pipeline Integration:**
- Starting pipeline starts all components
- Stopping pipeline stops all components
- State changes are forwarded to callbacks
- Health changes are forwarded to callbacks
- Reconnection trigger restarts components

**Reconnection Integration:**
- Connection loss triggers automatic reconnection
- Frame reception updates connection health

### 4. Example Usage (`src/example_streaming_pipeline.py`)

A complete example demonstrating:
- Creating protocol adapter and frame decoder
- Creating StreamingPipeline with callbacks
- Starting and stopping the pipeline
- Handling state and health changes

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    StreamingPipeline                        │
│  - Lifecycle management                                     │
│  - Component wiring                                         │
│  - Reconnection handling                                    │
└────────────┬────────────────────────────────────────────────┘
             │
             ├──────────────────────────────────────────────┐
             │                                              │
┌────────────▼──────────┐                    ┌──────────────▼─────────┐
│  ConnectionManager    │                    │  ProtocolAdapter       │
│  - State tracking     │◄───on_connect──────┤  (RTMP/SRT/WebRTC)    │
│  - Health monitoring  │◄───on_disconnect───┤                        │
│  - Reconnection logic │────reconnect───────►│                        │
└────────────┬──────────┘                    └────────────────────────┘
             │                                              │
             │                                              │
             │                                    ┌─────────▼──────────┐
             │                                    │   FrameDecoder     │
             │◄───────on_frame────────────────────┤                    │
             │                                    └────────────────────┘
             │
             ▼
    State & Health Callbacks
```

## Usage Example

```python
from src.streaming_pipeline import StreamingPipeline
from src.protocols.rtmp import RTMPAdapter
from src.decoder import FrameDecoder

# Create components
protocol_adapter = RTMPAdapter(width=1280, height=720)
frame_decoder = FrameDecoder(width=1280, height=720)

# Create pipeline with callbacks
pipeline = StreamingPipeline(
    protocol_adapter=protocol_adapter,
    frame_decoder=frame_decoder,
    on_state_change=lambda state: print(f"State: {state.value}"),
    on_health_change=lambda health: print(f"Health: {health.value}"),
)

# Start pipeline
await pipeline.start(port=2935, path="live/stream")

# Pipeline is now running with automatic reconnection
# and health monitoring enabled

# Stop pipeline
await pipeline.stop()
```

## Requirements Satisfied

This implementation satisfies the following requirements:

- **Requirement 1.1**: Automatic reconnection on disconnection
  - Protocol adapter disconnection triggers ConnectionManager reconnection logic
  - Reconnection trigger restarts protocol adapter and decoder

- **Requirement 1.4**: Frame persistence during interruption
  - FrameDecoder continues to provide last valid frame
  - ConnectionManager tracks frame reception for health monitoring

- **Requirement 1.6**: Connection state visibility
  - State changes are forwarded to callbacks
  - Health changes are forwarded to callbacks
  - UI can display current state and health

## Testing

All tests pass successfully:

```
src/test_streaming_pipeline.py::TestProtocolAdapterWiring::test_adapter_connect_triggers_connection_established PASSED
src/test_streaming_pipeline.py::TestProtocolAdapterWiring::test_adapter_disconnect_triggers_connection_lost PASSED
src/test_streaming_pipeline.py::TestProtocolAdapterWiring::test_adapter_preserves_original_callbacks PASSED
src/test_streaming_pipeline.py::TestFrameDecoderWiring::test_decoder_frame_triggers_frame_received PASSED
src/test_streaming_pipeline.py::TestFrameDecoderWiring::test_decoder_preserves_original_callback PASSED
src/test_streaming_pipeline.py::TestStreamingPipeline::test_pipeline_start_starts_all_components PASSED
src/test_streaming_pipeline.py::TestStreamingPipeline::test_pipeline_stop_stops_all_components PASSED
src/test_streaming_pipeline.py::TestStreamingPipeline::test_pipeline_forwards_state_changes PASSED
src/test_streaming_pipeline.py::TestStreamingPipeline::test_pipeline_forwards_health_changes PASSED
src/test_streaming_pipeline.py::TestStreamingPipeline::test_pipeline_handles_reconnection_trigger PASSED
src/test_streaming_pipeline.py::TestReconnectionIntegration::test_connection_loss_triggers_reconnection PASSED
src/test_streaming_pipeline.py::TestReconnectionIntegration::test_frame_reception_updates_health PASSED

12 passed in 9.18s
```

## Next Steps

The StreamingPipeline is now ready to be integrated into the main application (`src/main.py`). The next task (5.3 or later) should update the Application class to use StreamingPipeline instead of managing components separately.

## Files Created/Modified

**Created:**
- `src/streaming_pipeline.py` - Main integration module
- `src/test_streaming_pipeline.py` - Comprehensive test suite
- `src/example_streaming_pipeline.py` - Usage example
- `docs/streaming_pipeline_integration.md` - This documentation

**Modified:**
- `.kiro/specs/rtmp-vcam-improvements/tasks.md` - Marked task 5.2 as completed

## Notes

- The StreamingPipeline automatically wires callbacks, so users don't need to manually connect components
- Auto-reconnect is enabled by default but can be disabled via `ConnectionManager.set_auto_reconnect(False)`
- The pipeline preserves any original callbacks that were set on the adapter or decoder
- All existing protocol adapter tests continue to pass, ensuring backward compatibility
