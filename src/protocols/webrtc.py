"""
WebRTC Protocol Adapter with mDNS Discovery.

Implements the ProtocolAdapter interface for WebRTC streaming with zero-
configuration local network discovery via mDNS. This adapter uses aiortc
for WebRTC signaling and zeroconf for mDNS service advertisement.

Integration Notes
-----------------
This adapter provides peer-to-peer WebRTC connections with automatic service
discovery:

- Uses aiortc library for WebRTC peer connections
- Uses zeroconf library for mDNS advertisement
- Service name: _rtmp-vcam._tcp.local.
- No manual IP address configuration required
- Provides web interface for connection establishment
- Falls back to manual connection if mDNS fails

The adapter implements the same ProtocolAdapter interface as RTMPAdapter and
SRTAdapter, allowing seamless protocol switching in the application.
"""

import asyncio
import json
import logging
import socket
import threading
import queue
from typing import List, Callable, Optional, Dict, Any
from dataclasses import dataclass

try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
    from aiortc.contrib.media import MediaRelay

    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False
    RTCPeerConnection = None  # type: ignore
    RTCSessionDescription = None  # type: ignore
    VideoStreamTrack = None  # type: ignore
    MediaRelay = None  # type: ignore

try:
    from zeroconf import ServiceInfo, Zeroconf

    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False
    ServiceInfo = None  # type: ignore
    Zeroconf = None  # type: ignore

from .base import ProtocolAdapter
from .. import config

log = logging.getLogger(__name__)


@dataclass
class WebRTCConfig:
    """Configuration for WebRTC adapter."""

    service_name: str = "RTMP Virtual Camera"
    service_type: str = "_rtmp-vcam._tcp.local."
    signaling_port: int = 8080
    stun_servers: List[str] = None

    def __post_init__(self):
        if self.stun_servers is None:
            self.stun_servers = ["stun:stun.l.google.com:19302"]


class WebRTCAdapter(ProtocolAdapter):
    """
    WebRTC protocol implementation with mDNS discovery.

    This adapter provides peer-to-peer WebRTC connections with automatic
    service discovery via mDNS. iOS devices can discover the service
    automatically without manual IP address entry.

    The adapter uses aiortc for WebRTC signaling and zeroconf for mDNS
    advertisement. It provides a signaling server for connection establishment
    and manages peer connections.
    """

    def __init__(
        self,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        width: int = config.FRAME_WIDTH,
        height: int = config.FRAME_HEIGHT,
    ):
        """
        Initialize WebRTC adapter.

        Parameters
        ----------
        on_connect : callable, optional
            Callback invoked when a peer connects
        on_disconnect : callable, optional
            Callback invoked when a peer disconnects
        width : int
            Frame width for video (default from config)
        height : int
            Frame height for video (default from config)

        Raises
        ------
        RuntimeError
            If aiortc or zeroconf libraries are not installed
        """
        if not AIORTC_AVAILABLE:
            raise RuntimeError(
                "aiortc library not found. Install with: pip install aiortc\n"
                "WebRTC protocol requires aiortc for peer connections."
            )

        if not ZEROCONF_AVAILABLE:
            raise RuntimeError(
                "zeroconf library not found. Install with: pip install zeroconf\n"
                "WebRTC protocol requires zeroconf for mDNS discovery."
            )

        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._width = width
        self._height = height
        self._config = WebRTCConfig()

        # WebRTC state
        self._peer_connections: Dict[str, RTCPeerConnection] = {}
        self._connected = False
        self._relay = MediaRelay()

        # mDNS state
        self._zeroconf: Optional[Zeroconf] = None
        self._service_info: Optional[ServiceInfo] = None

        # Signaling server state
        self._signaling_server: Optional[asyncio.Server] = None
        self._port: Optional[int] = None

        # Frame queue for WebRTC video tracks
        self._frame_queue: queue.Queue = queue.Queue(maxsize=2)
        self._video_track = None
        self._running = True

    async def start(self, port: int, path: str = "") -> None:
        """
        Start the WebRTC adapter with mDNS advertisement.

        This starts a signaling server for WebRTC connection establishment
        and advertises the service via mDNS for automatic discovery.

        Parameters
        ----------
        port : int
            Port number for signaling server (typically 8080)
        path : str, optional
            Not used for WebRTC protocol (included for interface compatibility)

        Raises
        ------
        RuntimeError
            If the adapter fails to start
        """
        if self._signaling_server is not None:
            log.warning("WebRTC adapter already started")
            return

        self._port = port
        self._config.signaling_port = port

        # Start signaling server
        try:
            self._signaling_server = await asyncio.start_server(
                self._handle_signaling_connection, "0.0.0.0", port
            )
            log.info("WebRTC signaling server started on port %d", port)
        except Exception as e:
            raise RuntimeError(f"Failed to start WebRTC signaling server: {e}")

        # Start mDNS advertisement
        try:
            await self._start_mdns()
            log.info("mDNS service advertisement started")
        except Exception as e:
            log.warning("Failed to start mDNS advertisement: %s", e)
            log.warning("WebRTC will work but won't be discoverable via mDNS")

        log.info("WebRTC adapter started successfully")

    async def stop(self) -> None:
        """
        Stop the WebRTC adapter and clean up resources.

        Closes all peer connections, stops the signaling server, and
        unregisters the mDNS service.
        """
        log.info("Stopping WebRTC adapter")

        self._running = False

        # Close all peer connections
        for peer_id, pc in list(self._peer_connections.items()):
            try:
                await pc.close()
            except Exception as e:
                log.warning("Error closing peer connection %s: %s", peer_id, e)
        self._peer_connections.clear()

        # Stop signaling server
        if self._signaling_server is not None:
            self._signaling_server.close()
            await self._signaling_server.wait_closed()
            self._signaling_server = None

        # Stop mDNS advertisement
        await self._stop_mdns()

        # Reset connection state
        if self._connected:
            self._connected = False
            if self._on_disconnect:
                self._on_disconnect()

        log.info("WebRTC adapter stopped")

    def get_connection_urls(self, local_ips: List[str]) -> List[str]:
        """
        Return WebRTC connection URLs.

        Parameters
        ----------
        local_ips : List[str]
            List of local IP addresses

        Returns
        -------
        List[str]
            WebRTC signaling URLs in format: http://{ip}:{port}/webrtc
        """
        if self._port is None:
            return []

        urls = []
        for ip in local_ips:
            urls.append(f"http://{ip}:{self._port}/webrtc")
        return urls

    def get_connection_instructions(self) -> str:
        """
        Return human-readable connection instructions for WebRTC.

        Returns
        -------
        str
            Instructions for connecting via WebRTC with mDNS discovery
        """
        return (
            "WebRTC with mDNS Discovery:\n"
            "1. Your iOS device should automatically discover this service\n"
            "2. Look for 'RTMP Virtual Camera' in your streaming app\n"
            "3. Or scan the QR code on the web interface\n"
            "4. WebRTC provides low latency (<200ms) peer-to-peer streaming\n"
            "\n"
            "If automatic discovery fails, use the manual connection URL above."
        )

    @property
    def is_connected(self) -> bool:
        """
        Check if a peer is currently connected.

        Returns
        -------
        bool
            True if at least one WebRTC peer is connected
        """
        return self._connected

    async def _start_mdns(self) -> None:
        """
        Start mDNS service advertisement.

        Advertises the WebRTC signaling service on the local network
        using mDNS (Bonjour/Avahi) for zero-configuration discovery.
        """
        # Get local IP addresses
        local_ips = self._get_local_ips()
        if not local_ips:
            raise RuntimeError("No local IP addresses found for mDNS advertisement")

        # Use first non-loopback IP
        local_ip = local_ips[0]

        # Create service info
        service_name = f"{self._config.service_name}.{self._config.service_type}"

        # Convert IP to bytes
        ip_bytes = socket.inet_aton(local_ip)

        self._service_info = ServiceInfo(
            self._config.service_type,
            service_name,
            addresses=[ip_bytes],
            port=self._config.signaling_port,
            properties={
                "version": "1.0",
                "protocol": "webrtc",
                "path": "/webrtc",
            },
        )

        # Register service
        self._zeroconf = Zeroconf()
        await asyncio.get_event_loop().run_in_executor(
            None, self._zeroconf.register_service, self._service_info
        )

        log.info(
            "mDNS service registered: %s at %s:%d",
            service_name,
            local_ip,
            self._config.signaling_port,
        )

    async def _stop_mdns(self) -> None:
        """
        Stop mDNS service advertisement.

        Unregisters the mDNS service and cleans up resources.
        """
        if self._zeroconf is not None and self._service_info is not None:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._zeroconf.unregister_service, self._service_info
                )
                self._zeroconf.close()
                log.info("mDNS service unregistered")
            except Exception as e:
                log.warning("Error unregistering mDNS service: %s", e)
            finally:
                self._zeroconf = None
                self._service_info = None

    async def _handle_signaling_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """
        Handle incoming signaling connection.

        This implements a simple signaling protocol for WebRTC connection
        establishment. Clients send SDP offers and receive SDP answers.

        Parameters
        ----------
        reader : asyncio.StreamReader
            Stream reader for incoming data
        writer : asyncio.StreamWriter
            Stream writer for outgoing data
        """
        peer_addr = writer.get_extra_info("peername")
        peer_id = f"{peer_addr[0]}:{peer_addr[1]}"
        log.info("Signaling connection from %s", peer_id)

        try:
            # Read signaling message
            data = await reader.read(8192)
            if not data:
                return

            message = json.loads(data.decode("utf-8"))
            message_type = message.get("type")

            if message_type == "offer":
                # Handle WebRTC offer
                response = await self._handle_offer(peer_id, message)
                writer.write(json.dumps(response).encode("utf-8"))
                await writer.drain()
            else:
                log.warning("Unknown signaling message type: %s", message_type)

        except json.JSONDecodeError as e:
            log.error("Invalid JSON in signaling message: %s", e)
        except Exception as e:
            log.error("Error handling signaling connection: %s", e)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_offer(
        self, peer_id: str, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle WebRTC offer and create answer.

        Parameters
        ----------
        peer_id : str
            Unique identifier for the peer
        message : dict
            Signaling message containing SDP offer

        Returns
        -------
        dict
            Signaling response containing SDP answer
        """
        try:
            # Create peer connection
            pc = RTCPeerConnection(
                configuration={"iceServers": [{"urls": self._config.stun_servers}]}
            )

            # Store peer connection
            self._peer_connections[peer_id] = pc

            # Set up event handlers
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                log.info("Peer %s connection state: %s", peer_id, pc.connectionState)

                if pc.connectionState == "connected":
                    if not self._connected:
                        self._connected = True
                        if self._on_connect:
                            self._on_connect()

                elif pc.connectionState in ["failed", "closed"]:
                    if peer_id in self._peer_connections:
                        del self._peer_connections[peer_id]

                    if not self._peer_connections and self._connected:
                        self._connected = False
                        if self._on_disconnect:
                            self._on_disconnect()

            @pc.on("track")
            async def on_track(track):
                log.info("Received %s track from peer %s", track.kind, peer_id)

                if track.kind == "video":
                    self._video_track = track
                    log.info("Video track received, starting frame relay")
                    asyncio.create_task(self._relay_video_track(track))

            # Set remote description (offer)
            offer = RTCSessionDescription(sdp=message["sdp"], type=message["type"])
            await pc.setRemoteDescription(offer)

            # Create answer
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)

            # Return answer
            return {"type": pc.localDescription.type, "sdp": pc.localDescription.sdp}

        except Exception as e:
            log.error("Error handling WebRTC offer: %s", e)
            return {"type": "error", "message": str(e)}

    def _get_local_ips(self) -> List[str]:
        """
        Get local IP addresses for mDNS advertisement.

        Returns
        -------
        List[str]
            List of local IP addresses (excluding loopback)
        """
        ips = []
        try:
            # Get hostname
            hostname = socket.gethostname()

            # Get all addresses for hostname
            addr_info = socket.getaddrinfo(hostname, None)

            for info in addr_info:
                ip = info[4][0]
                # Filter out loopback and IPv6
                if not ip.startswith("127.") and ":" not in ip:
                    if ip not in ips:
                        ips.append(ip)

        except Exception as e:
            log.warning("Error getting local IPs: %s", e)

        return ips

    async def _relay_video_track(self, track) -> None:
        """Relay video frames from WebRTC track to frame queue."""
        try:
            while self._running:
                try:
                    async for frame in track:
                        if frame is not None:
                            try:
                                if hasattr(frame, "to_ndarray"):
                                    img = frame.to_ndarray()
                                else:
                                    continue

                                if img is not None and img.size > 0:
                                    if len(img.shape) == 3 and img.shape[2] == 3:
                                        img = img[:, :, ::-1]

                                    try:
                                        self._frame_queue.put_nowait(img)
                                    except queue.Full:
                                        try:
                                            self._frame_queue.get_nowait()
                                            self._frame_queue.put_nowait(img)
                                        except queue.Empty:
                                            pass
                            except Exception as e:
                                log.debug(f"Frame processing error: {e}")
                                continue
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log.debug(f"Track read error: {e}")
                    await asyncio.sleep(0.01)
        except Exception as e:
            log.error(f"Video relay error: {e}")

    def get_frame(self):
        """Get the latest video frame from WebRTC stream."""
        try:
            return self._frame_queue.get_nowait()
        except queue.Empty:
            return None

    def get_stdout(self):
        """Return None for WebRTC (uses get_frame instead)."""
        return None
