"""
H.264 → raw RGB frame decoder using ffmpeg subprocess pipe.

Receives H.264 NAL units, feeds them to a persistent ffmpeg process,
and reads decoded raw RGB24 frames from stdout.

Only the *latest* decoded frame is kept (no queuing → no latency build-up).

Updated to work with protocol abstraction layer - accepts any ProtocolAdapter
(RTMP, SRT, WebRTC) instead of being hardcoded to RTMP.
"""
import subprocess
import threading
import shutil
import logging
import numpy as np
from typing import Optional, Callable

from . import config

log = logging.getLogger(__name__)


class FrameDecoder:
    """
    Persistent ffmpeg-based H.264 → RGB24 decoder.
    
    Works with any ProtocolAdapter to decode video frames from different
    streaming protocols (RTMP, SRT, WebRTC).
    """

    def __init__(
        self,
        width: int = config.FRAME_WIDTH,
        height: int = config.FRAME_HEIGHT,
        on_frame: Optional[Callable[[np.ndarray], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize frame decoder.
        
        Parameters
        ----------
        width : int
            Frame width for decoding
        height : int
            Frame height for decoding
        on_frame : callable, optional
            Callback invoked when a frame is successfully decoded.
            Receives the decoded frame as a numpy array.
        on_error : callable, optional
            Callback invoked when a decode error occurs.
            Receives the error message as a string.
        """
        self.width = width
        self.height = height
        self._frame_bytes = width * height * 3  # RGB24
        self._on_frame = on_frame
        self._on_error = on_error
        self._protocol_adapter = None
        self._reader_thread: threading.Thread | None = None
        self._error_thread: threading.Thread | None = None
        self._latest_frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._frame_count = 0
        self._error_count = 0

    # ── lifecycle ────────────────────────────────────────

    def start(self, protocol_adapter) -> None:
        """
        Start decoding from protocol adapter.
        
        Parameters
        ----------
        protocol_adapter : ProtocolAdapter
            The protocol adapter providing the video stream.
            Must have a get_stdout() method that returns a subprocess.Popen
            with stdout containing raw RGB24 frames.
        
        Raises
        ------
        RuntimeError
            If the protocol adapter is not started or doesn't provide stdout
        """
        if self._running:
            log.warning("FrameDecoder already running")
            return

        self._protocol_adapter = protocol_adapter
        
        # Get the FFmpeg process from the protocol adapter
        # Protocol adapters that use FFmpeg should provide get_stdout() method
        if not hasattr(protocol_adapter, 'get_stdout'):
            raise RuntimeError(
                f"Protocol adapter {type(protocol_adapter).__name__} does not "
                "provide get_stdout() method for frame reading"
            )
        
        proc = protocol_adapter.get_stdout()
        if proc is None or proc.stdout is None:
            raise RuntimeError(
                "Protocol adapter not started or does not provide stdout"
            )
        
        log.info("Starting frame decoder with %s", type(protocol_adapter).__name__)
        self._running = True

        # Background thread that continuously reads decoded frames
        self._reader_thread = threading.Thread(
            target=self._read_frames, daemon=True, name="ffmpeg-reader"
        )
        self._reader_thread.start()

        # Error logging thread for ffmpeg
        self._error_thread = threading.Thread(
            target=self._read_errors, daemon=True, name="ffmpeg-errors"
        )
        self._error_thread.start()

    def stop(self) -> None:
        """Stop decoding and clean up."""
        self._running = False
        self._protocol_adapter = None
        
        # Wait for threads to finish
        if self._reader_thread is not None and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2)
            self._reader_thread = None
        
        if self._error_thread is not None and self._error_thread.is_alive():
            self._error_thread.join(timeout=2)
            self._error_thread = None
        
        with self._lock:
            self._latest_frame = None
        
        log.info("Frame decoder stopped (decoded %d frames, %d errors)", 
                 self._frame_count, self._error_count)

    # ── data in / out ────────────────────────────────────

    def feed(self, data: bytes) -> None:
        """
        Deprecated in protocol adapter mode.
        Protocol adapters handle data ingestion over network.
        """
        pass

    @property
    def latest_frame(self) -> np.ndarray | None:
        """Return the most recently decoded frame (or None)."""
        with self._lock:
            return self._latest_frame
    
    @property
    def frame_count(self) -> int:
        """Get total frames decoded since start."""
        return self._frame_count
    
    @property
    def error_count(self) -> int:
        """Get total decode errors since start."""
        return self._error_count

    # ── internal ─────────────────────────────────────────

    def _read_frames(self) -> None:
        """
        Continuously read raw frames from protocol adapter's stdout.
        
        Reads decoded RGB24 frames and stores the latest one. Handles
        decode errors gracefully by logging and continuing. On poor network
        conditions, continues displaying the last valid frame.
        """
        if self._protocol_adapter is None:
            log.error("No protocol adapter set")
            return
        
        proc = self._protocol_adapter.get_stdout()
        if proc is None or proc.stdout is None:
            log.error("Protocol adapter stdout not available")
            return
        
        log.debug("Frame reader thread started")
        
        while self._running:
            try:
                raw = proc.stdout.read(self._frame_bytes)
                
                if len(raw) == 0:
                    # End of stream - exit gracefully
                    if self._running:
                        log.info("End of stream reached")
                    break
                
                if len(raw) != self._frame_bytes:
                    # Short read - log error but continue with last valid frame
                    if self._running:
                        error_msg = f"Short read from decoder: expected {self._frame_bytes} bytes, got {len(raw)}"
                        log.warning(error_msg)
                        self._error_count += 1
                        if self._on_error:
                            self._on_error(error_msg)
                        # Continue loop instead of breaking - graceful degradation
                        continue
                
                # Successfully read a frame
                frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                    (self.height, self.width, 3)
                )
                
                with self._lock:
                    self._latest_frame = frame
                    self._frame_count += 1
                
                # Notify callback if provided
                if self._on_frame:
                    self._on_frame(frame)
                    
            except Exception as e:
                if self._running:
                    error_msg = f"Error reading frame: {e}"
                    log.error(error_msg)
                    self._error_count += 1
                    if self._on_error:
                        self._on_error(error_msg)
                    # Continue loop instead of breaking - graceful degradation
                    # Last valid frame will continue to be displayed
                    continue
        
        log.debug("Frame reader thread exiting")

    def _read_errors(self) -> None:
        """
        Read and log ffmpeg stderr from protocol adapter.
        
        Monitors stderr for decode errors and other issues, invoking
        the error callback when problems are detected. Continues monitoring
        even after errors to support graceful degradation.
        """
        if self._protocol_adapter is None:
            return
        
        proc = self._protocol_adapter.get_stdout()
        if proc is None or proc.stderr is None:
            return
        
        log.debug("Error reader thread started")
        
        while self._running:
            try:
                line = proc.stderr.readline()
                if not line:
                    break
                
                line_str = line.decode('utf-8', errors='ignore').strip()
                
                # Check for error indicators
                if any(keyword in line_str.lower() for keyword in [
                    'error', 'failed', 'invalid', 'corrupt'
                ]):
                    log.error("FFmpeg error: %s", line_str)
                    self._error_count += 1
                    if self._on_error:
                        self._on_error(f"Decode error: {line_str}")
                    # Continue monitoring - don't crash on errors
                elif 'warning' in line_str.lower():
                    log.warning("FFmpeg warning: %s", line_str)
                else:
                    log.debug("FFmpeg: %s", line_str)
                    
            except Exception as e:
                if self._running:
                    log.error("Error reading stderr: %s", e)
                    # Continue monitoring even after exceptions
                    continue
        
        log.debug("Error reader thread exiting")
