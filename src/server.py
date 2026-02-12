"""
HTTP Metadata Server.

- Serves a simple info page with RTMP streaming instructions.
- Provides a /health diagnostic endpoint.
- No longer handles video frames directly (now handled by FFmpeg RTMP listener).
"""
import asyncio
import socket
import logging
import os

import aiohttp
from aiohttp import web

from . import config

log = logging.getLogger(__name__)


class StreamServer:
    """HTTP server providing connection info for streaming."""

    def __init__(self, on_data=None, on_connect=None, on_disconnect=None):
        """
        Parameters
        ----------
        on_data : callable(bytes) or None
            Called with raw H.264 NAL-unit payload for each received chunk.
        on_connect : callable() or None
            Called when a sender client connects.
        on_disconnect : callable() or None
            Called when the sender client disconnects.
        """
        self._on_data = on_data
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._local_ips: list[str] = []
        self._protocol_adapter = None
        self._http_port = config.HTTP_PORT

    def set_protocol_adapter(self, adapter):
        """Set the active protocol adapter to display correct info."""
        self._protocol_adapter = adapter

    def set_http_port(self, port: int):
        """Update the HTTP port (requires restart)."""
        self._http_port = port

    # ── lifecycle ────────────────────────────────────────

    async def start(self) -> None:
        log.info("Server start initiated (Protocol Flexible Mode)")
        
        self._local_ips = self._get_local_ips()
        log.info("Local IPs resolved: %s", self._local_ips)
 
        app = web.Application()
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/qr", self._handle_qr)
        self._app = app
 
        runner = web.AppRunner(app, access_log=log)
        await runner.setup()
        self._runner = runner
 
        site = web.TCPSite(
            runner, "0.0.0.0", self._http_port
        )
        await site.start()
        log.info("Site started on port %d (HTTP)", self._http_port)
        self._site = site

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
        self._site = None
        self._runner = None
        self._app = None
        log.info("Server stopped")

    # ── handlers ─────────────────────────────────────────

    async def _handle_index(self, request: web.Request) -> web.Response:
        """Serve a simple info page with dynamic instructions."""
        if not self._protocol_adapter:
            return web.Response(text="Server ready, but no protocol adapter active.", content_type="text/plain")

        urls = self._protocol_adapter.get_connection_urls(self._local_ips)
        instructions = self._protocol_adapter.get_connection_instructions().replace("\n", "<br>")
        
        url_html = "".join([f"<div class='url-box'><code>{url}</code></div>" for url in urls])
        
        # QR Code part
        qr_html = ""
        if urls:
            qr_html = f"""
            <div style="margin-top: 20px;">
                <p style="color:#8888a0; font-size:12px;">Scan to connect (Primary URL):</p>
                <img src="/qr?url={urls[0]}" style="border: 10px solid white; border-radius: 8px; width: 200px; height: 200px;">
            </div>
            """

        html = f"""
        <html>
        <head>
            <title>Local Virtual Camera</title>
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; text-align: center; padding-top: 50px; background: #0d0d12; color: #e0e0e8; }}
                .container {{ border: 1px solid #23232e; display: inline-block; padding: 30px; border-radius: 14px; background: #16161e; max-width: 500px; }}
                h1 {{ color: #6c5ce7; margin-bottom: 20px; }}
                .url-box {{ background: #0d0d12; padding: 12px; border-radius: 8px; margin: 10px 0; text-align: left; word-break: break-all; }}
                code {{ color: #00cec9; }}
                .instructions {{ font-size: 14px; color: #8888a0; margin: 20px 0; line-height: 1.6; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 Server Ready</h1>
                <div class="instructions">{instructions}</div>
                <p style="color:#8888a0; font-size:12px; text-align: left; margin-bottom: 5px;">Connection URLs:</p>
                {url_html}
                {qr_html}
            </div>
        </body>
        </html>
        """
        return web.Response(text=html, content_type="text/html")

    async def _handle_qr(self, request: web.Request) -> web.Response:
        """Generate and serve a QR code image."""
        url = request.query.get("url")
        if not url:
            return web.Response(status=400, text="Missing url parameter")
            
        import qrcode
        import io
        
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return web.Response(body=img_byte_arr.getvalue(), content_type="image/png")

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Diagnostic endpoint."""
        info = {
            "status": "ok",
            "protocol": type(self._protocol_adapter).__name__ if self._protocol_adapter else None,
            "ips": self._local_ips,
            "http_port": self._http_port,
            "ffmpeg": config.FFMPEG_BIN,
        }
        return web.json_response(info)


    # ── helpers ──────────────────────────────────────────

    @staticmethod
    def _get_local_ips() -> list[str]:
        """Return all local IPv4 addresses, prioritized: primary, then others, then localhost."""
        import socket
        ips: list[str] = []
        
        # Try to find primary interface IP
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                primary = s.getsockname()[0]
                if primary and not primary.startswith("127."):
                    ips.append(primary)
        except Exception:
            pass

        # Add other interfaces
        try:
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                addr = info[4][0]
                if addr not in ips and not addr.startswith("127."):
                    ips.append(addr)
        except Exception:
            pass
            
        # Always include localhost at the end
        if "127.0.0.1" not in ips:
            ips.append("127.0.0.1")
            
        return ips

