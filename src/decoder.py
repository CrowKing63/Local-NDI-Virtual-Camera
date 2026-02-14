"""
H.264 → raw RGB frame decoder using ffmpeg subprocess pipe.

Receives H.264 NAL units, feeds them to a persistent ffmpeg process,
and reads decoded raw RGB24 frames from stdout.

Only the *latest* decoded frame is kept (no queuing → no latency build-up).
This implementation now supports an optional circular buffer to store a
small number of recent frames for smoother playback during network
interruption.

Updated to work with protocol abstraction layer - accepts any ProtocolAdapter
(RTMP, SRT, WebRTC) instead of being hardcoded to RTMP.
"""

import subprocess
import threading
import shutil
import logging
import numpy as np
from typing import Optional, Callable, List
from collections import deque

from . import config

log = logging.getLogger(__name__)


class FrameDecoder:
    """
    Persistent ffmpeg-based H.264 → RGB24 decoder.

    Works with any ProtocolAdapter to decode video frames from different
    streaming protocols (RTMP, SRT, WebRTC).

    This class manages a background thread that continuously reads decoded
    frames from a FFmpeg subprocess and stores only the latest frame to
    minimize latency. It handles graceful degradation when network conditions
    are poor by continuing to display the last valid frame.

    Key features:
    - Protocol-agnostic: works with RTMP, SRT, and WebRTC adapters
    - Thread-safe: uses locks for concurrent access to frame data
    - Error handling: monitors both stdout and stderr for issues
    - Callback support: notifies when frames are decoded or errors occur
    - Optional circular buffer: store a small number of recent frames
    """

    def __init__(
        self,
        width: int = config.FRAME_WIDTH,
        height: int = config.FRAME_HEIGHT,
        buffer_size: int = 1,
        on_frame: Optional[Callable[[np.ndarray], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize frame decoder.

        Parameters
        ----------
        width : int
            Frame width for decoding in pixels
        height : int
            Frame height for decoding in pixels
        buffer_size : int, default 1
            Number of recent frames to keep in a circular buffer.
            A value of 1 keeps only the latest frame.
        on_frame : callable, optional
            Callback invoked when a frame is successfully decoded.
            Receives the decoded frame as a numpy array.
        on_error : callable, optional
            Callback invoked when a decode error occurs.
            Receives the error message as a string.

        Returns
        -------
        None
        """
        self.width = width
        self.height = height
        self._frame_bytes = width * height * 3  # RGB24
        self._buffer_size = buffer_size
        self._frame_buffer: deque[np.ndarray] = deque(maxlen=buffer_size)
        self._on_frame = on_frame
        self._on_error = on_error
        self._protocol_adapter = None
        self._is_webrtc = False
        self._reader_thread: threading.Thread | None = None
        self._error_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._running = False
        self._frame_count = 0
        self._error_count = 0
        self._last_frame_time = 0.0

    def clear_buffer(self) -> None:
        """Clear the frame buffer to free memory."""
        with self._lock:
            self._frame_buffer.clear()
        log.debug("Frame buffer cleared")

    # ── lifecycle ────────────────────────────────────────

    def start(self, protocol_adapter) -> None:
        """
        Start decoding from protocol adapter.

        Parameters
        ----------
        protocol_adapter : ProtocolAdapter
            The protocol adapter providing the video stream.
            Must have a get_stdout() method that returns a subprocess.Popen
            with stdout containing raw RGB24 frames, OR a get_frame()
            method for WebRTC.

        Raises
        ------
        RuntimeError
            If the protocol adapter is not started or doesn't provide stdout/get_frame

        Returns
        -------
        None
        """
        if self._running:
            log.warning("FrameDecoder already running")
            return

        self._protocol_adapter = protocol_adapter
        self._is_webrtc = False

        # Check if adapter has get_frame method (WebRTC)
        if hasattr(protocol_adapter, "get_frame"):
            self._is_webrtc = True
            log.info("Starting frame decoder in WebRTC mode")
            self._running = True

            self._reader_thread = threading.Thread(
                target=self._read_frames_webrtc, daemon=True, name="webrtc-reader"
            )
            self._reader_thread.start()
            return

        # Check for FFmpeg-based adapters (RTMP, SRT)
        if not hasattr(protocol_adapter, "get_stdout"):
            raise RuntimeError(
                f"Protocol adapter {type(protocol_adapter).__name__} does not "
                "provide get_stdout() or get_frame() method for frame reading"
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
        """
        Stop decoding and clean up.

        This method stops the background threads, releases resources,
        and resets the decoder state. It waits for threads to finish
        gracefully before returning.
        """
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
            self._frame_buffer.clear()

        log.info(
            "Frame decoder stopped (decoded %d frames, %d errors)",
            self._frame_count,
            self._error_count,
        )

    # ── data in / out ────────────────────────────────────

    def feed(self, data: bytes) -> None:
        """
        Deprecated in protocol adapter mode.
        Protocol adapters handle data ingestion over network.

        This method is kept for backward compatibility but does nothing
        when using protocol adapters. Data ingestion is handled by the
        protocol adapter itself over the network connection.
        """
        pass

    @property
    def latest_frame(self) -> np.ndarray | None:
        """
        Return the most recently decoded frame (or None).

        This property provides thread-safe access to the latest decoded
        frame. If no frame has been decoded yet or the decoder has stopped,
        it returns None.

        Returns
        -------
        np.ndarray | None
            The latest decoded RGB frame, or None if no frame is available.
        """
        with self._lock:
            return self._frame_buffer[-1] if self._frame_buffer else None

    @property
    def frame_count(self) -> int:
        """
        Get total frames decoded since start.

        This property returns the cumulative count of successfully decoded
        frames since the decoder was started. It's useful for monitoring
        decoding performance and detecting issues.

        Returns
        -------
        int
            Total number of frames decoded successfully.
        """
        return self._frame_count

    @property
    def error_count(self) -> int:
        """
        Get total decode errors since start.

        This property returns the cumulative count of decode errors that
        have occurred since the decoder was started. It helps monitor the
        quality of the incoming stream and network conditions.

        Returns
        -------
        int
            Total number of decode errors encountered.
        """
        return self._error_count

    # ── internal ─────────────────────────────────────────

    def _read_frames(self) -> None:
        """
        Continuously read raw frames from protocol adapter's stdout.

        This method runs in a background thread and continuously reads
        decoded RGB24 frames from the protocol adapter's stdout. It stores
        only the latest frame to minimize memory usage and latency.

        The method handles various error conditions gracefully:
        - Short reads: logs warning and continues with last valid frame
        - End of stream: exits gracefully
        - Network errors: logs error and continues with last valid frame

        On poor network conditions, this implementation ensures that the
        application continues to display the last valid frame rather than
        showing black frames or crashing.

        Returns
        -------
        None
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
                    self._frame_buffer.append(frame)
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

    def _read_frames_webrtc(self) -> None:
        """Read frames from WebRTC adapter using get_frame() method."""
        if self._protocol_adapter is None:
            log.error("No protocol adapter set")
            return

        if not hasattr(self._protocol_adapter, "get_frame"):
            log.error("Protocol adapter does not have get_frame method")
            return

        log.debug("WebRTC frame reader thread started")

        while self._running:
            try:
                frame = self._protocol_adapter.get_frame()

                if frame is None:
                    import time

                    time.sleep(0.001)
                    continue

                with self._lock:
                    self._frame_buffer.append(frame)
                    self._frame_count += 1

                if self._on_frame:
                    self._on_frame(frame)

            except Exception as e:
                if self._running:
                    error_msg = f"Error reading WebRTC frame: {e}"
                    log.error(error_msg)
                    self._error_count += 1
                    if self._on_error:
                        self._on_error(error_msg)
                    continue

        log.debug("WebRTC frame reader thread exiting")

    def _read_errors(self) -> None:
        """
        Read and log ffmpeg stderr from protocol adapter.

        This method runs in a background thread and continuously monitors
        the protocol adapter's stderr for any issues. It looks for error
        indicators like 'error', 'failed', 'invalid', 'corrupt' and invokes
        the error callback when problems are detected.

        The method continues monitoring ffmpeg stderr for errors and warnings.
        It reads lines from stderr, logs them, and triggers the error callback
        for error messages. Non-error lines are logged at debug level.
        """
        if self._protocol_adapter is None:
            log.error("No protocol adapter set for error reading")
            return

        if self._is_webrtc:
            log.debug("WebRTC mode - no stderr to read")
            return

        proc = self._protocol_adapter.get_stdout()
        if proc is None or proc.stderr is None:
            log.error("Protocol adapter stderr not available")
            return

        while self._running:
            try:
                line = proc.stderr.readline()
                if not line:
                    break

                line_str = line.decode("utf-8", errors="ignore").strip()

                # Check for error indicators
                if any(
                    keyword in line_str.lower()
                    for keyword in ["error", "failed", "invalid", "corrupt"]
                ):
                    log.error("FFmpeg error: %s", line_str)
                    self._error_count += 1
                    if self._on_error:
                        self._on_error(f"Decode error: {line_str}")
                    # Continue monitoring - don't crash on errors
                elif "warning" in line_str.lower():
                    log.warning("FFmpeg warning: %s", line_str)
                else:
                    log.debug("FFmpeg: %s", line_str)

            except Exception as e:
                if self._running:
                    log.error("Error reading stderr: %s", e)
                    # Continue monitoring even after exceptions
                    continue

        log.debug("Error reader thread exiting")
