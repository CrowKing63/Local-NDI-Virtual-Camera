"""
Example usage of StreamingPipeline with ConnectionManager integration.

This example demonstrates how to use the StreamingPipeline class to create
a complete streaming solution with automatic reconnection and health monitoring.

Requirements: 1.1, 1.4, 1.6
"""
import asyncio
import logging
from src.streaming_pipeline import StreamingPipeline
from src.protocols.rtmp import RTMPAdapter
from src.decoder import FrameDecoder
from src.connection_manager import ConnectionState, ConnectionHealth

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)


def on_state_change(state: ConnectionState):
    """Handle connection state changes."""
    log.info(f"Connection state changed to: {state.value}")
    
    if state == ConnectionState.CONNECTED:
        print("✓ Stream connected!")
    elif state == ConnectionState.DISCONNECTED:
        print("✗ Stream disconnected")
    elif state == ConnectionState.RECONNECTING:
        print("⟳ Attempting to reconnect...")


def on_health_change(health: ConnectionHealth):
    """Handle connection health changes."""
    log.info(f"Connection health changed to: {health.value}")
    
    if health == ConnectionHealth.EXCELLENT:
        print("✓ Connection quality: Excellent (>28 fps)")
    elif health == ConnectionHealth.GOOD:
        print("✓ Connection quality: Good (20-28 fps)")
    elif health == ConnectionHealth.POOR:
        print("⚠ Connection quality: Poor (10-20 fps)")
    elif health == ConnectionHealth.CRITICAL:
        print("✗ Connection quality: Critical (<10 fps)")


def on_frame(frame):
    """Handle decoded frames."""
    # This is called for every decoded frame
    # You can process the frame here (e.g., send to virtual camera)
    pass


async def main():
    """Main example function."""
    print("=" * 60)
    print("StreamingPipeline Example")
    print("=" * 60)
    print()
    
    # Create protocol adapter (RTMP in this example)
    protocol_adapter = RTMPAdapter(
        width=1280,
        height=720,
    )
    
    # Create frame decoder with buffer size of 3 for smoother playback
    frame_decoder = FrameDecoder(
        width=1280,
        height=720,
        buffer_size=3,  # Store last 3 frames for smoother playback
        on_frame=on_frame,
    )
    
    # Create streaming pipeline with connection management
    pipeline = StreamingPipeline(
        protocol_adapter=protocol_adapter,
        frame_decoder=frame_decoder,
        on_state_change=on_state_change,
        on_health_change=on_health_change,
    )
    
    try:
        # Start the pipeline
        print("Starting streaming pipeline...")
        await pipeline.start(port=2935, path="live/stream")
        
        # Get connection URLs
        urls = pipeline.protocol_adapter.get_connection_urls(['192.168.1.100'])
        print(f"\nConnect your streaming app to:")
        for url in urls:
            print(f"  {url}")
        print()
        
        # Get connection instructions
        instructions = pipeline.protocol_adapter.get_connection_instructions()
        print(f"Instructions:\n{instructions}\n")
        
        # Access connection manager for status
        print(f"Current state: {pipeline.connection_manager.current_state.value}")
        print(f"Current health: {pipeline.connection_manager.current_health.value}")
        print()
        
        # Keep running
        print("Pipeline running. Press Ctrl+C to stop...")
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping pipeline...")
    finally:
        # Stop the pipeline
        await pipeline.stop()
        print("Pipeline stopped.")


if __name__ == "__main__":
    asyncio.run(main())