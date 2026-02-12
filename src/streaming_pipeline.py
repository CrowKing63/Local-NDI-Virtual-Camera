"""
Streaming Pipeline Integration.

Wires together ConnectionManager, ProtocolAdapter, and FrameDecoder to create
a complete streaming pipeline with automatic reconnection and health monitoring.

This module provides the integration layer that connects:
- Protocol adapter callbacks → ConnectionManager state tracking
- FrameDecoder frame callback → ConnectionManager health monitoring
- ConnectionManager reconnection trigger → Protocol adapter restart

Requirements: 1.1, 1.4, 1.6
"""
import asyncio
import logging
from typing import Optional, Callable
from enum import Enum

from .connection_manager import ConnectionManager, ConnectionState, ConnectionHealth
from .protocols.base import ProtocolAdapter
from .decoder import FrameDecoder

log = logging.getLogger(__name__)


class StreamingPipeline:
    """
    Integrated streaming pipeline with connection management.
    
    This class wires together the ConnectionManager, ProtocolAdapter, and
    FrameDecoder to provide a complete streaming solution with automatic
    reconnection and health monitoring.
    
    The pipeline handles:
    - Starting/stopping the protocol adapter and decoder
    - Connecting protocol events to connection manager
    - Connecting frame events to connection manager
    - Triggering reconnection when connection is lost
    """
    
    def __init__(
        self,
        protocol_adapter: ProtocolAdapter,
        frame_decoder: FrameDecoder,
        on_state_change: Optional[Callable[[ConnectionState], None]] = None,
        on_health_change: Optional[Callable[[ConnectionHealth], None]] = None,
    ):
        """
        Initialize streaming pipeline.
        
        Parameters
        ----------
        protocol_adapter : ProtocolAdapter
            The protocol adapter (RTMP, SRT, or WebRTC) to use for streaming
        frame_decoder : FrameDecoder
            The frame decoder to decode video frames
        on_state_change : callable, optional
            Callback invoked when connection state changes
        on_health_change : callable, optional
            Callback invoked when connection health changes
        """
        self._on_state_change = on_state_change
        self._on_health_change = on_health_change
        
        # Connection manager with wired callbacks
        self._connection_manager = ConnectionManager(
            on_state_change=self._handle_state_change,
            on_health_change=self._handle_health_change,
            on_reconnect_trigger=self._handle_reconnect_trigger,
        )
        
        # Wire protocol adapter and frame decoder to connection manager
        self._protocol_adapter = create_wired_protocol_adapter(
            protocol_adapter, self._connection_manager
        )
        self._frame_decoder = create_wired_frame_decoder(
            frame_decoder, self._connection_manager
        )
        
        # Pipeline state
        self._port: Optional[int] = None
        self._path: Optional[str] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
    @property
    def connection_manager(self) -> ConnectionManager:
        """Get the connection manager instance."""
        return self._connection_manager
    
    @property
    def protocol_adapter(self) -> ProtocolAdapter:
        """Get the protocol adapter instance."""
        return self._protocol_adapter
    
    @property
    def frame_decoder(self) -> FrameDecoder:
        """Get the frame decoder instance."""
        return self._frame_decoder
    
    @property
    def is_running(self) -> bool:
        """Check if the pipeline is running."""
        return self._running
    
    async def start(self, port: int, path: str = "") -> None:
        """
        Start the streaming pipeline.
        
        This starts the protocol adapter, frame decoder, and connection
        monitoring in the correct order.
        
        Parameters
        ----------
        port : int
            Port number for the protocol adapter
        path : str, optional
            Stream path (for RTMP protocol)
        
        Raises
        ------
        RuntimeError
            If the pipeline is already running or fails to start
        """
        if self._running:
            log.warning("Streaming pipeline already running")
            return
        
        self._port = port
        self._path = path
        self._loop = asyncio.get_event_loop()
        
        log.info("Starting streaming pipeline with %s", 
                 type(self._protocol_adapter).__name__)
        
        try:
            # Start protocol adapter with connection callbacks
            await self._protocol_adapter.start(port, path)
            
            # Start frame decoder with frame callback
            self._frame_decoder.start(self._protocol_adapter)
            
            # Start connection monitoring
            self._connection_manager.start_monitoring()
            
            self._running = True
            log.info("Streaming pipeline started successfully")
            
        except Exception as e:
            log.error("Failed to start streaming pipeline: %s", e)
            # Clean up on failure
            await self._cleanup()
            raise RuntimeError(f"Failed to start streaming pipeline: {e}")
    
    async def stop(self) -> None:
        """
        Stop the streaming pipeline.
        
        This stops the connection monitoring, frame decoder, and protocol
        adapter in the correct order.
        """
        if not self._running:
            log.warning("Streaming pipeline not running")
            return
        
        log.info("Stopping streaming pipeline")
        
        await self._cleanup()
        
        self._running = False
        log.info("Streaming pipeline stopped")
    
    async def _cleanup(self) -> None:
        """Clean up pipeline resources."""
        # Stop connection monitoring
        self._connection_manager.stop_monitoring()
        
        # Stop frame decoder
        self._frame_decoder.stop()
        
        # Stop protocol adapter
        try:
            await self._protocol_adapter.stop()
        except Exception as e:
            log.warning("Error stopping protocol adapter: %s", e)
    
    def _handle_state_change(self, state: ConnectionState) -> None:
        """
        Handle connection state changes from ConnectionManager.
        
        This is called by ConnectionManager when the connection state changes.
        It forwards the event to the user-provided callback.
        
        Parameters
        ----------
        state : ConnectionState
            The new connection state
        """
        log.info("Connection state changed: %s", state.value)
        
        if self._on_state_change:
            self._on_state_change(state)
    
    def _handle_health_change(self, health: ConnectionHealth) -> None:
        """
        Handle connection health changes from ConnectionManager.
        
        This is called by ConnectionManager when the connection health changes.
        It forwards the event to the user-provided callback.
        
        Parameters
        ----------
        health : ConnectionHealth
            The new connection health
        """
        log.info("Connection health changed: %s", health.value)
        
        if self._on_health_change:
            self._on_health_change(health)
    
    def _handle_reconnect_trigger(self) -> None:
        """
        Handle reconnection trigger from ConnectionManager.
        
        This is called by ConnectionManager when automatic reconnection should
        be attempted. It restarts the protocol adapter and frame decoder.
        
        Requirements: 1.1, 1.4
        """
        log.info("Reconnection triggered by ConnectionManager")
        
        if not self._running:
            log.warning("Cannot reconnect: pipeline not running")
            return
        
        if self._loop is None:
            log.error("Cannot reconnect: no event loop")
            return
        
        # Schedule reconnection in the event loop
        asyncio.run_coroutine_threadsafe(
            self._perform_reconnection(),
            self._loop
        )
    
    async def _perform_reconnection(self) -> None:
        """
        Perform the actual reconnection.
        
        This stops and restarts the protocol adapter and frame decoder.
        If successful, ConnectionManager will be notified via the on_connect
        callback.
        """
        log.info("Performing reconnection...")
        
        try:
            # Stop current adapter and decoder
            self._frame_decoder.stop()
            await self._protocol_adapter.stop()
            
            # Small delay before restarting
            await asyncio.sleep(0.5)
            
            # Restart adapter and decoder
            await self._protocol_adapter.start(self._port, self._path)
            self._frame_decoder.start(self._protocol_adapter)
            
            log.info("Reconnection completed successfully")
            
        except Exception as e:
            log.error("Reconnection failed: %s", e)
            # ConnectionManager will continue retry attempts


def create_wired_protocol_adapter(
    adapter: ProtocolAdapter,
    connection_manager: ConnectionManager,
) -> ProtocolAdapter:
    """
    Wire a protocol adapter to a connection manager.
    
    This is a helper function that creates a new protocol adapter instance
    with callbacks wired to the connection manager.
    
    Parameters
    ----------
    adapter : ProtocolAdapter
        The protocol adapter to wire (should be newly created, not started)
    connection_manager : ConnectionManager
        The connection manager to wire to
    
    Returns
    -------
    ProtocolAdapter
        The same adapter instance with callbacks wired
    
    Note
    ----
    This function modifies the adapter's callbacks. The adapter should not
    have been started yet.
    """
    # Store original callbacks if they exist
    original_on_connect = getattr(adapter, '_on_connect', None)
    original_on_disconnect = getattr(adapter, '_on_disconnect', None)
    
    # Create wrapper callbacks that call both original and connection manager
    def on_connect_wrapper():
        connection_manager.report_connection_established()
        if original_on_connect:
            original_on_connect()
    
    def on_disconnect_wrapper():
        connection_manager.report_connection_lost()
        if original_on_disconnect:
            original_on_disconnect()
    
    # Wire the callbacks
    adapter._on_connect = on_connect_wrapper
    adapter._on_disconnect = on_disconnect_wrapper
    
    return adapter


def create_wired_frame_decoder(
    decoder: FrameDecoder,
    connection_manager: ConnectionManager,
) -> FrameDecoder:
    """
    Wire a frame decoder to a connection manager.
    
    This is a helper function that creates a new frame decoder instance
    with callbacks wired to the connection manager.
    
    Parameters
    ----------
    decoder : FrameDecoder
        The frame decoder to wire (should be newly created, not started)
    connection_manager : ConnectionManager
        The connection manager to wire to
    
    Returns
    -------
    FrameDecoder
        The same decoder instance with callbacks wired
    
    Note
    ----
    This function modifies the decoder's callbacks. The decoder should not
    have been started yet.
    """
    # Store original callback if it exists
    original_on_frame = getattr(decoder, '_on_frame', None)
    
    # Create wrapper callback that calls both original and connection manager
    def on_frame_wrapper(frame):
        connection_manager.report_frame_received()
        if original_on_frame:
            original_on_frame(frame)
    
    # Wire the callback
    decoder._on_frame = on_frame_wrapper
    
    return decoder
