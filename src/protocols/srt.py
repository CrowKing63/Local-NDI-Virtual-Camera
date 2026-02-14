"""
SRT Protocol Adapter.

Implements the ProtocolAdapter interface for SRT (Secure Reliable Transport)
streaming using FFmpeg with SRT protocol support. SRT provides lower latency
and better error recovery than RTMP, making it ideal for challenging network
conditions.

Integration Notes
-----------------
This adapter uses FFmpeg's SRT protocol support to accept incoming SRT streams.
Key differences from RTMP:

- Uses SRT protocol URL format: srt://{ip}:{port}
- Default port: 9000 (different from RTMP's 2935)
- No path component in URL (unlike RTMP)
- Requires FFmpeg compiled with libsrt support
- Provides automatic packet recovery for network packet loss

The adapter implements the same ProtocolAdapter interface as RTMPAdapter,
allowing seamless protocol switching in the application.
"""

import asyncio
import subprocess
import logging
from typing import List, Callable, Optional

from .base import ProtocolAdapter
from .. import config

log = logging.getLogger(__name__)


class SRTAdapter(ProtocolAdapter):
    """
    SRT protocol implementation using FFmpeg with SRT support.

    This adapter starts an FFmpeg process in SRT listener mode, which accepts
    incoming SRT streams from iOS devices or streaming applications and outputs
    decoded RGB24 frames.

    SRT provides lower latency (target <150ms) and better error recovery
    compared to RTMP, making it suitable for challenging network conditions.
    """

    def __init__(
        self,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        width: int = config.FRAME_WIDTH,
        height: int = config.FRAME_HEIGHT,
    ):
        """
        Initialize SRT adapter.

        Parameters
        ----------
        on_connect : callable, optional
            Callback invoked when a client connects
        on_disconnect : callable, optional
            Callback invoked when a client disconnects
        width : int
            Frame width for decoding (default from config)
        height : int
            Frame height for decoding (default from config)
        """
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._width = width
        self._height = height
        self._port: Optional[int] = None
        self._proc: Optional[subprocess.Popen] = None
        self._connected = False
        self._monitor_task: Optional[asyncio.Task] = None

    async def start(self, port: int, path: str = "") -> None:
        """
        Start the SRT server listening for incoming streams.

        Parameters
        ----------
        port : int
            Port number to listen on (typically 9000)
        path : str, optional
            Not used for SRT protocol (included for interface compatibility)

        Raises
        ------
        RuntimeError
            If FFmpeg is not found or fails to start
        """
        if self._proc is not None:
            log.warning("SRT adapter already started")
            return

        if config.FFMPEG_BIN is None:
            raise RuntimeError(
                "FFmpeg not found.\n\n"
                "Please install FFmpeg with SRT support:\n"
                "1. Download from https://ffmpeg.org/download.html\n"
                "2. Ensure FFmpeg is compiled with libsrt\n"
                "3. Add to PATH, or run: python src/setup_ffmpeg.py"
            )

        self._port = port

        # Build FFmpeg command for SRT server
        # Uses srt:// protocol with ?mode=listener to create an SRT server
        cmd = [
            config.FFMPEG_BIN,
            "-loglevel",
            "info",
            "-i",
            f"srt://0.0.0.0:{self._port}?mode=listener",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{self._width}x{self._height}",
            "-flags",
            "low_delay",
            "-fflags",
            "nobuffer",
            "-an",
            "-sn",  # No audio, no subtitles
            "pipe:1",  # Output to stdout
        ]

        log.info("Starting SRT server on srt://0.0.0.0:%d", self._port)
        log.debug("FFmpeg command: %s", " ".join(cmd))

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if hasattr(subprocess, "CREATE_NO_WINDOW")
                    else 0
                ),
            )
        except Exception as e:
            raise RuntimeError(f"Failed to start FFmpeg SRT server: {e}")

        # Start monitoring FFmpeg stderr for connection events
        self._monitor_task = asyncio.create_task(self._monitor_connection())

        log.info("SRT adapter started successfully")

    async def stop(self) -> None:
        """
        Stop the SRT server and clean up resources.

        Gracefully terminates the FFmpeg process and cancels monitoring tasks.
        """
        log.info("Stopping SRT adapter")

        # Cancel monitoring task
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        # Terminate FFmpeg process
        if self._proc is not None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
            except Exception:
                pass

            try:
                self._proc.terminate()
                # Wait for graceful shutdown
                try:
                    self._proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate
                    self._proc.kill()
                    self._proc.wait()
            except Exception as e:
                log.warning("Error terminating FFmpeg process: %s", e)

            self._proc = None

        # Reset connection state
        if self._connected:
            self._connected = False
            if self._on_disconnect:
                self._on_disconnect()

        log.info("SRT adapter stopped")

    def get_connection_urls(self, local_ips: List[str]) -> List[str]:
        """
        Return SRT connection URLs for streaming clients.

        Parameters
        ----------
        local_ips : List[str]
            List of local IP addresses

        Returns
        -------
        List[str]
            SRT URLs in format: srt://{ip}:{port}
        """
        if self._port is None:
            return []

        urls = []
        for ip in local_ips:
            urls.append(f"srt://{ip}:{self._port}")
        return urls

    def get_connection_instructions(self) -> str:
        """
        Return human-readable connection instructions for SRT.

        Returns
        -------
        str
            Instructions for connecting via SRT from streaming applications
        """
        return (
            "Use an SRT-compatible streaming application (e.g., Larix Broadcaster, OBS).\n"
            "Select 'SRT' protocol and enter one of the SRT URLs shown above.\n"
            "SRT provides lower latency (<150ms) and better error recovery than RTMP,\n"
            "making it ideal for challenging network conditions."
        )

    @property
    def is_connected(self) -> bool:
        """
        Check if a sender is currently connected.

        Returns
        -------
        bool
            True if an SRT client is connected and streaming
        """
        return self._connected

    def get_stdout(self) -> Optional[subprocess.Popen]:
        """
        Get the FFmpeg process for frame reading.

        This method provides access to the FFmpeg process stdout for
        reading decoded frames. This maintains compatibility with the
        existing FrameDecoder implementation.

        Returns
        -------
        subprocess.Popen or None
            The FFmpeg process, or None if not started
        """
        return self._proc

    async def _monitor_connection(self) -> None:
        """
        Monitor FFmpeg stderr for connection events.

        Watches FFmpeg's stderr output to detect when clients connect or
        disconnect, and triggers the appropriate callbacks.
        """
        if self._proc is None or self._proc.stderr is None:
            return

        log.debug("Starting connection monitoring")

        try:
            # Read stderr in a non-blocking way
            loop = asyncio.get_event_loop()

            while True:
                # Read line from stderr
                line = await loop.run_in_executor(None, self._proc.stderr.readline)

                if not line:
                    # EOF - process terminated
                    log.debug("FFmpeg stderr closed")
                    if self._connected:
                        self._connected = False
                        if self._on_disconnect:
                            self._on_disconnect()
                    break

                # Decode and log the line
                line_str = line.decode("utf-8", errors="ignore").strip()

                # Check for connection indicators in FFmpeg output
                # SRT connection messages may include "SRT", "caller", "connected"
                if any(
                    keyword in line_str
                    for keyword in [
                        "SRT CONNECTED",
                        "caller connected",
                        "accepted connection",
                    ]
                ):
                    if not self._connected:
                        log.info("SRT client connected")
                        self._connected = True
                        if self._on_connect:
                            self._on_connect()

                # Also detect connection by looking for stream info
                # FFmpeg logs stream information when it starts receiving data
                elif "Stream #0:" in line_str and not self._connected:
                    log.info("SRT client connected (stream detected)")
                    self._connected = True
                    if self._on_connect:
                        self._on_connect()

                # Check for disconnection indicators
                elif any(
                    keyword in line_str.lower()
                    for keyword in [
                        "connection closed",
                        "eof",
                        "broken pipe",
                        "disconnected",
                        "connection lost",
                    ]
                ):
                    if self._connected:
                        log.info("SRT client disconnected")
                        self._connected = False
                        if self._on_disconnect:
                            self._on_disconnect()

                # Log FFmpeg messages at appropriate level
                if "error" in line_str.lower():
                    log.error("FFmpeg: %s", line_str)
                elif "warning" in line_str.lower():
                    log.warning("FFmpeg: %s", line_str)
                else:
                    log.debug("FFmpeg: %s", line_str)

        except asyncio.CancelledError:
            log.debug("Connection monitoring cancelled")
            raise
        except Exception as e:
            log.error("Error monitoring connection: %s", e)
