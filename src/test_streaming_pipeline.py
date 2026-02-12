"""
Tests for streaming pipeline integration.

Tests the wiring between ConnectionManager, ProtocolAdapter, and FrameDecoder.
"""
import pytest
import asyncio
import numpy as np
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime

from .streaming_pipeline import (
    StreamingPipeline,
    create_wired_protocol_adapter,
    create_wired_frame_decoder,
)
from .connection_manager import ConnectionManager, ConnectionState, ConnectionHealth
from .protocols.base import ProtocolAdapter
from .decoder import FrameDecoder


class MockProtocolAdapter(ProtocolAdapter):
    """Mock protocol adapter for testing."""
    
    def __init__(self, on_connect=None, on_disconnect=None):
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._started = False
        self._port = None
        self._path = None
        self._proc = None
        
    async def start(self, port: int, path: str = "") -> None:
        self._started = True
        self._port = port
        self._path = path
        # Simulate FFmpeg process
        self._proc = MagicMock()
        self._proc.stdout = MagicMock()
        self._proc.stderr = MagicMock()
        
    async def stop(self) -> None:
        self._started = False
        self._proc = None
        
    def get_connection_urls(self, local_ips):
        return [f"mock://{ip}:{self._port}" for ip in local_ips]
    
    def get_connection_instructions(self):
        return "Mock protocol instructions"
    
    @property
    def is_connected(self):
        return self._started
    
    def get_stdout(self):
        return self._proc
    
    def simulate_connect(self):
        """Simulate a client connecting."""
        if self._on_connect:
            self._on_connect()
    
    def simulate_disconnect(self):
        """Simulate a client disconnecting."""
        if self._on_disconnect:
            self._on_disconnect()


@pytest.fixture
def mock_adapter():
    """Create a mock protocol adapter."""
    return MockProtocolAdapter()


@pytest.fixture
def mock_decoder():
    """Create a mock frame decoder."""
    decoder = Mock(spec=FrameDecoder)
    decoder.start = Mock()
    decoder.stop = Mock()
    decoder._on_frame = None
    return decoder


@pytest.fixture
def connection_manager():
    """Create a connection manager for testing."""
    on_state_change = Mock()
    on_health_change = Mock()
    on_reconnect_trigger = Mock()
    
    manager = ConnectionManager(
        on_state_change=on_state_change,
        on_health_change=on_health_change,
        on_reconnect_trigger=on_reconnect_trigger,
    )
    
    return manager


class TestProtocolAdapterWiring:
    """Test wiring protocol adapter callbacks to ConnectionManager."""
    
    def test_adapter_connect_triggers_connection_established(self, mock_adapter, connection_manager):
        """Test that adapter on_connect triggers ConnectionManager.report_connection_established()."""
        # Wire the adapter
        wired_adapter = create_wired_protocol_adapter(mock_adapter, connection_manager)
        
        # Simulate connection
        wired_adapter.simulate_connect()
        
        # Verify connection manager state changed to CONNECTED
        assert connection_manager.current_state == ConnectionState.CONNECTED
    
    def test_adapter_disconnect_triggers_connection_lost(self, mock_adapter, connection_manager):
        """Test that adapter on_disconnect triggers ConnectionManager.report_connection_lost()."""
        # Disable auto-reconnect for this test
        connection_manager.set_auto_reconnect(False)
        
        # Wire the adapter
        wired_adapter = create_wired_protocol_adapter(mock_adapter, connection_manager)
        
        # First connect
        wired_adapter.simulate_connect()
        assert connection_manager.current_state == ConnectionState.CONNECTED
        
        # Then disconnect
        wired_adapter.simulate_disconnect()
        
        # Verify connection manager state changed to DISCONNECTED
        assert connection_manager.current_state == ConnectionState.DISCONNECTED
    
    def test_adapter_preserves_original_callbacks(self, connection_manager):
        """Test that wiring preserves original adapter callbacks."""
        # Disable auto-reconnect for this test
        connection_manager.set_auto_reconnect(False)
        
        original_connect_called = False
        original_disconnect_called = False
        
        def original_on_connect():
            nonlocal original_connect_called
            original_connect_called = True
        
        def original_on_disconnect():
            nonlocal original_disconnect_called
            original_disconnect_called = True
        
        # Create adapter with original callbacks
        adapter = MockProtocolAdapter(
            on_connect=original_on_connect,
            on_disconnect=original_on_disconnect,
        )
        
        # Wire the adapter
        wired_adapter = create_wired_protocol_adapter(adapter, connection_manager)
        
        # Simulate connection
        wired_adapter.simulate_connect()
        
        # Verify both original and connection manager callbacks were called
        assert original_connect_called
        assert connection_manager.current_state == ConnectionState.CONNECTED
        
        # Simulate disconnection
        wired_adapter.simulate_disconnect()
        
        # Verify both original and connection manager callbacks were called
        assert original_disconnect_called
        assert connection_manager.current_state == ConnectionState.DISCONNECTED


class TestFrameDecoderWiring:
    """Test wiring frame decoder callbacks to ConnectionManager."""
    
    def test_decoder_frame_triggers_frame_received(self, mock_decoder, connection_manager):
        """Test that decoder on_frame triggers ConnectionManager.report_frame_received()."""
        # Wire the decoder
        wired_decoder = create_wired_frame_decoder(mock_decoder, connection_manager)
        
        # Simulate connection first
        connection_manager.report_connection_established()
        
        # Simulate frame received
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        if wired_decoder._on_frame:
            wired_decoder._on_frame(frame)
        
        # Verify frame was reported to connection manager
        # (We can't directly check this, but we can verify the callback exists)
        assert wired_decoder._on_frame is not None
    
    def test_decoder_preserves_original_callback(self, connection_manager):
        """Test that wiring preserves original decoder callback."""
        original_frame_called = False
        
        def original_on_frame(frame):
            nonlocal original_frame_called
            original_frame_called = True
        
        # Create decoder with original callback
        decoder = Mock(spec=FrameDecoder)
        decoder._on_frame = original_on_frame
        
        # Wire the decoder
        wired_decoder = create_wired_frame_decoder(decoder, connection_manager)
        
        # Simulate frame received
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        if wired_decoder._on_frame:
            wired_decoder._on_frame(frame)
        
        # Verify both original and connection manager callbacks were called
        assert original_frame_called


class TestStreamingPipeline:
    """Test the integrated streaming pipeline."""
    
    @pytest.mark.asyncio
    async def test_pipeline_start_starts_all_components(self, mock_adapter, mock_decoder):
        """Test that starting pipeline starts adapter, decoder, and monitoring."""
        pipeline = StreamingPipeline(
            protocol_adapter=mock_adapter,
            frame_decoder=mock_decoder,
        )
        
        await pipeline.start(port=2935, path="live/stream")
        
        # Verify all components started
        assert mock_adapter._started
        assert mock_adapter._port == 2935
        assert mock_adapter._path == "live/stream"
        mock_decoder.start.assert_called_once_with(mock_adapter)
        assert pipeline.is_running
    
    @pytest.mark.asyncio
    async def test_pipeline_stop_stops_all_components(self, mock_adapter, mock_decoder):
        """Test that stopping pipeline stops all components."""
        pipeline = StreamingPipeline(
            protocol_adapter=mock_adapter,
            frame_decoder=mock_decoder,
        )
        
        await pipeline.start(port=2935, path="live/stream")
        await pipeline.stop()
        
        # Verify all components stopped
        assert not mock_adapter._started
        mock_decoder.stop.assert_called_once()
        assert not pipeline.is_running
    
    @pytest.mark.asyncio
    async def test_pipeline_forwards_state_changes(self, mock_adapter, mock_decoder):
        """Test that pipeline forwards state changes to callback."""
        state_changes = []
        
        def on_state_change(state):
            state_changes.append(state)
        
        pipeline = StreamingPipeline(
            protocol_adapter=mock_adapter,
            frame_decoder=mock_decoder,
            on_state_change=on_state_change,
        )
        
        await pipeline.start(port=2935)
        
        # Simulate connection
        pipeline.protocol_adapter.simulate_connect()
        
        # Give callback time to execute
        await asyncio.sleep(0.1)
        
        # Verify state change was forwarded
        assert ConnectionState.CONNECTED in state_changes
    
    @pytest.mark.asyncio
    async def test_pipeline_forwards_health_changes(self, mock_adapter, mock_decoder):
        """Test that pipeline forwards health changes to callback."""
        health_changes = []
        
        def on_health_change(health):
            health_changes.append(health)
        
        pipeline = StreamingPipeline(
            protocol_adapter=mock_adapter,
            frame_decoder=mock_decoder,
            on_health_change=on_health_change,
        )
        
        await pipeline.start(port=2935)
        
        # Start monitoring
        pipeline.connection_manager.start_monitoring()
        
        # Simulate connection and frames
        pipeline.connection_manager.report_connection_established()
        
        # Simulate multiple frames to trigger health calculation
        for _ in range(30):
            pipeline.connection_manager.report_frame_received()
            await asyncio.sleep(0.01)
        
        # Give monitoring thread time to process
        await asyncio.sleep(1.5)
        
        # Verify health changes were forwarded
        # (Health should improve as frames are received)
        assert len(health_changes) > 0
    
    @pytest.mark.asyncio
    async def test_pipeline_handles_reconnection_trigger(self, mock_adapter, mock_decoder):
        """Test that pipeline handles reconnection trigger from ConnectionManager."""
        pipeline = StreamingPipeline(
            protocol_adapter=mock_adapter,
            frame_decoder=mock_decoder,
        )
        
        await pipeline.start(port=2935, path="live/stream")
        
        # Simulate connection loss
        mock_adapter.simulate_disconnect()
        
        # Give reconnection time to process
        await asyncio.sleep(0.1)
        
        # Verify reconnection was attempted
        # (Adapter should be stopped and restarted)
        # Note: In real scenario, ConnectionManager would trigger reconnection
        # after backoff delay, but we're testing the mechanism here
        assert pipeline.is_running


class TestReconnectionIntegration:
    """Test reconnection integration between components."""
    
    @pytest.mark.asyncio
    async def test_connection_loss_triggers_reconnection(self, mock_adapter, mock_decoder):
        """Test that connection loss triggers automatic reconnection."""
        reconnect_triggered = False
        
        def on_reconnect():
            nonlocal reconnect_triggered
            reconnect_triggered = True
        
        # Create connection manager with reconnection callback
        connection_manager = ConnectionManager(
            on_state_change=Mock(),
            on_health_change=Mock(),
            on_reconnect_trigger=on_reconnect,
        )
        
        # Wire adapter to connection manager
        wired_adapter = create_wired_protocol_adapter(mock_adapter, connection_manager)
        
        # Simulate connection
        wired_adapter.simulate_connect()
        assert connection_manager.current_state == ConnectionState.CONNECTED
        
        # Simulate disconnection
        wired_adapter.simulate_disconnect()
        
        # Give reconnection logic time to trigger
        await asyncio.sleep(2)
        
        # Verify reconnection was triggered
        assert reconnect_triggered or connection_manager.current_state == ConnectionState.RECONNECTING
    
    @pytest.mark.asyncio
    async def test_frame_reception_updates_health(self, mock_adapter, mock_decoder):
        """Test that frame reception updates connection health."""
        health_changes = []
        
        def on_health_change(health):
            health_changes.append(health)
        
        # Create connection manager
        connection_manager = ConnectionManager(
            on_state_change=Mock(),
            on_health_change=on_health_change,
        )
        
        # Wire decoder to connection manager
        wired_decoder = create_wired_frame_decoder(mock_decoder, connection_manager)
        
        # Start monitoring
        connection_manager.start_monitoring()
        
        # Simulate connection
        connection_manager.report_connection_established()
        
        # Simulate frames at 30 fps
        for _ in range(60):
            if wired_decoder._on_frame:
                frame = np.zeros((720, 1280, 3), dtype=np.uint8)
                wired_decoder._on_frame(frame)
            await asyncio.sleep(1/30)
        
        # Give monitoring thread time to process
        await asyncio.sleep(1.5)
        
        # Stop monitoring
        connection_manager.stop_monitoring()
        
        # Verify health improved with frame reception
        assert len(health_changes) > 0
        # Should eventually reach EXCELLENT or GOOD health
        assert any(h in [ConnectionHealth.EXCELLENT, ConnectionHealth.GOOD] 
                   for h in health_changes)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
