"""
RTMP Protocol Adapter.

Implements the ProtocolAdapter interface for RTMP streaming using FFmpeg's
built-in RTMP server functionality. This adapter wraps the existing FFmpeg
RTMP server implementation and provides a unified interface.

Integration Notes
-----------------
This adapter refactors the existing RTMP server code from decoder.py into
a protocol adapter that implements the ProtocolAdapter interface. It maintains
full backward compatibility with the existing implementation:

- Uses the same FFmpeg command structure with -rtmp_listen
- Maintains default port 2935 and path "live/stream"
- Compatible with PRISM Live Studio and Larix Broadcaster
- Provides get_stdout() method for compatibility with existing FrameDecoder

The adapter can be used as a drop-in replacement for the existing RTMP
implementation while providing the benefits of the protocol abstraction layer.
"""

import asyncio
import subprocess
import logging
from typing import List, Callable, Optional

from .base import ProtocolAdapter
from .. import config

log = logging.getLogger(__name__)


class RTMPAdapter(ProtocolAdapter):
    """
    RTMP protocol implementation using FFmpeg's RTMP server.

    This adapter starts an FFmpeg process in RTMP listen mode, which accepts
    incoming RTMP streams from iOS devices (e.g., PRISM Live Studio, Larix
    Broadcaster) and outputs decoded RGB24 frames.

    The adapter maintains backward compatibility with the existing RTMP
    implementation while providing the ProtocolAdapter interface.
    """

    def __init__(
        self,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        width: int = config.FRAME_WIDTH,
        height: int = config.FRAME_HEIGHT,
    ):
        """
        Initialize RTMP adapter.

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
        self._path: Optional[str] = None
        self._proc: Optional[subprocess.Popen] = None
        self._connected = False
        self._monitor_task: Optional[asyncio.Task] = None

    async def start(self, port: int, path: str = "") -> None:
        """
        Start the RTMP server listening for incoming streams.

        Parameters
        ----------
        port : int
            Port number to listen on (typically 2935)
        path : str, optional
            RTMP stream path (e.g., "live/stream")

        Raises
        ------
        RuntimeError
            If FFmpeg is not found or fails to start
        """
        if self._proc is not None:
            log.warning("RTMP adapter already started")
            return

        if config.FFMPEG_BIN is None:
            raise RuntimeError(
                "FFmpeg not found.\n\n"
                "Please install FFmpeg:\n"
                "1. Download from https://ffmpeg.org/download.html\n"
                "2. Add to PATH, or\n"
                "3. Run: python src/setup_ffmpeg.py"
            )

        self._port = port
        self._path = path or config.RTMP_PATH

        # Build FFmpeg command for RTMP server
        # Uses ?listen=1 URL parameter — avoids FFmpeg 7.x listen_timeout=-1000 bug
        cmd = [
            config.FFMPEG_BIN,
            "-loglevel",
            "info",
            "-i",
            f"rtmp://0.0.0.0:{self._port}/{self._path}?listen=1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{self._width}x{self._height}",
            "-r",
            str(config.FPS),
            "-flags",
            "low_delay",
            "-fflags",
            "nobuffer",
            "-an",
            "-sn",  # No audio, no subtitles
            "pipe:1",  # Output to stdout
        ]

        log.info("Starting RTMP server on rtmp://0.0.0.0:%d/%s", self._port, self._path)
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
            raise RuntimeError(f"Failed to start FFmpeg RTMP server: {e}")

        # Start monitoring FFmpeg stderr for connection events
        self._monitor_task = asyncio.create_task(self._monitor_connection())

        log.info("RTMP adapter started successfully")

    async def stop(self) -> None:
        """
        Stop the RTMP server and clean up resources.

        Gracefully terminates the FFmpeg process and cancels monitoring tasks.
        """
        log.info("Stopping RTMP adapter")

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

        log.info("RTMP adapter stopped")

    def get_connection_urls(self, local_ips: List[str]) -> List[str]:
        """
        Return RTMP connection URLs for iOS sender.

        Parameters
        ----------
        local_ips : List[str]
            List of local IP addresses

        Returns
        -------
        List[str]
            RTMP URLs in format: rtmp://{ip}:{port}/{path}
        """
        if self._port is None or self._path is None:
            return []

        urls = []
        for ip in local_ips:
            urls.append(f"rtmp://{ip}:{self._port}/{self._path}")
        return urls

    def get_connection_instructions(self) -> str:
        """
        Return human-readable connection instructions for RTMP.

        Returns
        -------
        str
            Instructions for connecting via RTMP from iOS apps
        """
        return (
            "Use PRISM Live Studio or Larix Broadcaster on your iOS device.\n"
            "Select 'Custom RTMP' and enter one of the RTMP URLs shown above.\n"
            "RTMP provides reliable, high-quality streaming with broad compatibility."
        )

    @property
    def is_connected(self) -> bool:
        """
        Check if a sender is currently connected.

        Returns
        -------
        bool
            True if an RTMP client is connected and streaming
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
                # FFmpeg logs "Handshake performed" when RTMP client connects
                if "Handshake performed" in line_str or "connect" in line_str.lower():
                    if not self._connected:
                        log.info("RTMP client connected")
                        self._connected = True
                        if self._on_connect:
                            self._on_connect()

                # Check for disconnection indicators
                # FFmpeg logs various messages when client disconnects
                elif any(
                    keyword in line_str.lower()
                    for keyword in [
                        "connection closed",
                        "eof",
                        "broken pipe",
                        "disconnected",
                    ]
                ):
                    if self._connected:
                        log.info("RTMP client disconnected")
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
