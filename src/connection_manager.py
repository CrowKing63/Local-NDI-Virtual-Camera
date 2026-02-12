"""
Connection state management for RTMP Virtual Camera.

Monitors connection health, manages reconnection attempts, and tracks connection state.
"""
import logging
from enum import Enum
from typing import Callable, Optional
from datetime import datetime
import threading
import time

log = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


class ConnectionHealth(Enum):
    """Connection health enumeration based on frame rate."""
    EXCELLENT = "excellent"  # >28 fps
    GOOD = "good"            # 20-28 fps
    POOR = "poor"            # 10-20 fps
    CRITICAL = "critical"    # <10 fps



class ConnectionManager:
    """
    Manages connection state, health monitoring, and automatic reconnection.
    
    Implements a state machine for connection states and monitors frame reception
    to track connection health.
    """
    
    # Reconnection configuration
    MAX_RECONNECT_ATTEMPTS = 10
    BACKOFF_SEQUENCE = [1, 2, 4, 8, 16, 30]  # seconds, max 30s
    
    def __init__(
        self,
        on_state_change: Callable[[ConnectionState], None],
        on_health_change: Callable[[ConnectionHealth], None],
        on_reconnect_trigger: Optional[Callable[[], None]] = None
    ):
        """
        Initialize connection manager with callbacks for state changes.
        
        Parameters
        ----------
        on_state_change : callable
            Called when connection state changes with new ConnectionState
        on_health_change : callable
            Called when connection health changes with new ConnectionHealth
        on_reconnect_trigger : callable, optional
            Called when automatic reconnection should be triggered
        """
        self._on_state_change = on_state_change
        self._on_health_change = on_health_change
        self._on_reconnect_trigger = on_reconnect_trigger
        
        # State tracking
        self._state = ConnectionState.DISCONNECTED
        self._health = ConnectionHealth.CRITICAL
        self._lock = threading.Lock()
        
        # Frame monitoring
        self._last_frame_time: Optional[datetime] = None
        self._frame_count = 0
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Reconnection tracking
        self._reconnect_attempts = 0
        self._reconnect_thread: Optional[threading.Thread] = None
        self._auto_reconnect_enabled = True
        
    @property
    def current_state(self) -> ConnectionState:
        """Get current connection state."""
        with self._lock:
            return self._state
    
    @property
    def current_health(self) -> ConnectionHealth:
        """Get current connection health."""
        with self._lock:
            return self._health
    
    def start_monitoring(self) -> None:
        """Begin monitoring connection health."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="connection-monitor"
        )
        self._monitor_thread.start()
        log.info("Connection monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop monitoring connection health."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=3)
            self._monitor_thread = None
        log.info("Connection monitoring stopped")
    
    def report_connection_established(self) -> None:
        """Called by protocol adapter when connection succeeds."""
        with self._lock:
            old_state = self._state
            self._state = ConnectionState.CONNECTED
            # Reset reconnection counter on successful connection
            self._reconnect_attempts = 0
            
        if old_state != ConnectionState.CONNECTED:
            log.info("Connection established")
            self._on_state_change(ConnectionState.CONNECTED)
    
    def report_connection_lost(self) -> None:
        """Called by protocol adapter when connection drops."""
        with self._lock:
            old_state = self._state
            self._state = ConnectionState.DISCONNECTED
            self._last_frame_time = None
            should_reconnect = self._auto_reconnect_enabled
            
        if old_state != ConnectionState.DISCONNECTED:
            log.info("Connection lost")
            self._on_state_change(ConnectionState.DISCONNECTED)
            
            # Trigger automatic reconnection if enabled
            if should_reconnect:
                self._start_reconnection()
    
    def report_frame_received(self) -> None:
        """Called by decoder when frame is successfully decoded."""
        with self._lock:
            self._last_frame_time = datetime.now()
            self._frame_count += 1
    
    def trigger_reconnect(self) -> None:
        """Manually trigger reconnection attempt."""
        with self._lock:
            old_state = self._state
            self._state = ConnectionState.RECONNECTING
            
        if old_state != ConnectionState.RECONNECTING:
            log.info("Reconnection triggered manually")
            self._on_state_change(ConnectionState.RECONNECTING)
            
        # Start reconnection process
        self._start_reconnection()
    
    def set_auto_reconnect(self, enabled: bool) -> None:
        """Enable or disable automatic reconnection."""
        with self._lock:
            self._auto_reconnect_enabled = enabled
        log.info(f"Auto-reconnect {'enabled' if enabled else 'disabled'}")
    
    def _start_reconnection(self) -> None:
        """Start the reconnection process in a background thread."""
        # Don't start multiple reconnection threads
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return
        
        self._reconnect_thread = threading.Thread(
            target=self._reconnection_loop,
            daemon=True,
            name="reconnection"
        )
        self._reconnect_thread.start()
    
    def _reconnection_loop(self) -> None:
        """Background thread that handles reconnection with exponential backoff."""
        while self._reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
            with self._lock:
                # Check if we're still disconnected
                if self._state == ConnectionState.CONNECTED:
                    log.info("Connection restored, stopping reconnection attempts")
                    return
                
                self._reconnect_attempts += 1
                attempt = self._reconnect_attempts
                
                # Calculate backoff delay
                backoff_index = min(attempt - 1, len(self.BACKOFF_SEQUENCE) - 1)
                delay = self.BACKOFF_SEQUENCE[backoff_index]
                
                # Update state to reconnecting
                old_state = self._state
                self._state = ConnectionState.RECONNECTING
            
            # Notify state change outside lock
            if old_state != ConnectionState.RECONNECTING:
                self._on_state_change(ConnectionState.RECONNECTING)
            
            log.info(f"Reconnection attempt {attempt}/{self.MAX_RECONNECT_ATTEMPTS} in {delay}s")
            
            # Wait for backoff delay
            time.sleep(delay)
            
            # Trigger reconnection callback if provided
            if self._on_reconnect_trigger:
                try:
                    self._on_reconnect_trigger()
                except Exception as e:
                    log.error(f"Reconnection trigger failed: {e}")
        
        # Max attempts reached
        with self._lock:
            self._state = ConnectionState.DISCONNECTED
        
        log.warning(f"Max reconnection attempts ({self.MAX_RECONNECT_ATTEMPTS}) reached")
        self._on_state_change(ConnectionState.DISCONNECTED)
    
    def _monitor_loop(self) -> None:
        """Background thread that monitors connection health based on frame rate."""
        # Track frames over a sliding window for accurate FPS calculation
        frame_timestamps = []
        window_size = 30  # Track last 30 frames for FPS calculation
        
        while self._monitoring:
            time.sleep(1.0)  # Check every second
            
            with self._lock:
                if self._state != ConnectionState.CONNECTED:
                    # Only monitor health when connected
                    # Reset health to critical when not connected
                    if self._health != ConnectionHealth.CRITICAL:
                        old_health = self._health
                        self._health = ConnectionHealth.CRITICAL
                    else:
                        old_health = self._health
                    continue
                
                if self._last_frame_time is None:
                    # No frames received yet
                    new_health = ConnectionHealth.CRITICAL
                    old_health = self._health
                    self._health = new_health
                else:
                    # Track frame reception timestamps
                    current_time = datetime.now()
                    elapsed_since_last = (current_time - self._last_frame_time).total_seconds()
                    
                    # Add timestamp to window if frame was recent
                    if elapsed_since_last < 2.0:  # Frame within last 2 seconds
                        frame_timestamps.append(self._last_frame_time)
                        # Keep only recent frames in window
                        cutoff_time = current_time.timestamp() - 2.0
                        frame_timestamps = [
                            ts for ts in frame_timestamps 
                            if ts.timestamp() > cutoff_time
                        ]
                        # Limit window size
                        if len(frame_timestamps) > window_size:
                            frame_timestamps = frame_timestamps[-window_size:]
                    
                    # Calculate FPS based on frame timestamps
                    if len(frame_timestamps) >= 2:
                        # Calculate FPS from timestamp window
                        time_span = (frame_timestamps[-1] - frame_timestamps[0]).total_seconds()
                        if time_span > 0:
                            fps = (len(frame_timestamps) - 1) / time_span
                        else:
                            fps = 30.0  # Default assumption
                    elif elapsed_since_last < 1.0:
                        # Recent frame but not enough history, assume good
                        fps = 30.0
                    else:
                        # No recent frames
                        fps = 1.0 / elapsed_since_last if elapsed_since_last > 0 else 0
                    
                    # Determine health based on FPS thresholds
                    # excellent: >28fps, good: 20-28fps, poor: 10-20fps, critical: <10fps
                    if fps > 28:
                        new_health = ConnectionHealth.EXCELLENT
                    elif fps >= 20:
                        new_health = ConnectionHealth.GOOD
                    elif fps >= 10:
                        new_health = ConnectionHealth.POOR
                    else:
                        new_health = ConnectionHealth.CRITICAL
                    
                    old_health = self._health
                    self._health = new_health
            
            # Trigger callback outside lock if health changed
            if old_health != new_health:
                log.info(f"Connection health changed: {old_health.value} -> {new_health.value} (fps: {fps:.1f})")
                self._on_health_change(new_health)
