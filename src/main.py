"""
Local Virtual Camera — main entry point.

Wires together:
  TrayApp (UI) ↔ StreamServer (network) ↔ FrameDecoder (video) ↔ VirtualCameraOutput

Usage:
    python -m src.main          # development
    LocalVirtualCamera.exe      # packaged
"""

import asyncio
import threading
import logging
import sys
import os

from . import config
from .server import StreamServer
from .decoder import FrameDecoder
from .virtual_camera import VirtualCameraOutput
from .tray import TrayApp
from .config_manager import ConfigurationManager, AppConfig, ProtocolType
from .connection_manager import ConnectionManager, ConnectionState, ConnectionHealth
from .protocols.factory import ProtocolFactory
from .settings_dialog import SettingsDialog
from .log_viewer import LogViewer

log = logging.getLogger("localvcam")


class Application:
    """Top-level orchestrator."""

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None

        # setup logging to file
        self._setup_logging()

        # Configuration
        self._config_mgr = ConfigurationManager()
        self._config: AppConfig = self._config_mgr.load()

        # Components
        self._decoder = FrameDecoder(
            width=self._config.frame_width,
            height=self._config.frame_height,
            on_frame=self._on_frame_decoded,
        )
        self._vcam = VirtualCameraOutput()
        self._protocol_factory = ProtocolFactory()
        self._protocol_adapter = None

        # Connection management
        self._conn_mgr = ConnectionManager(
            on_state_change=self._on_connection_state_change,
            on_health_change=self._on_connection_health_change,
            on_reconnect_trigger=self._on_reconnect_trigger,
        )

        self._server = StreamServer(
            on_connect=self._on_sender_connect,
            on_disconnect=self._on_sender_disconnect,
        )

        self._tray = TrayApp(
            on_start=self._start_streaming,
            on_stop=self._stop_streaming,
            on_exit=self._exit,
            on_settings=self._show_settings,
            on_view_logs=self._show_logs,
            on_protocol_change=self._on_protocol_change,
        )
        self._streaming = False

    # ── public ───────────────────────────────────────────

    def run(self) -> None:
        """Start the application (blocks on the tray icon main loop)."""
        self._setup_logging()
        log.info("Local Virtual Camera starting …")

        # 0. Dependency Checks
        from .installer.dependency_manager import DependencyManager

        dep_mgr = DependencyManager(ffmpeg_bin=config.FFMPEG_BIN or "ffmpeg")
        ffmpeg_ok, ffmpeg_msg = dep_mgr.check_ffmpeg()
        vcam_ok, vcam_msg = dep_mgr.check_unity_capture()

        if not ffmpeg_ok:
            log.error("FFmpeg check failed: %s", ffmpeg_msg)
            # We still show the tray icon but notify the user
        if not vcam_ok:
            log.warning("Unity Capture check failed: %s", vcam_msg)

        # Asyncio loop in a background thread
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._run_loop, daemon=True, name="asyncio-loop"
        )
        self._loop_thread.start()

        # pystray blocks on the main thread
        try:
            # Show initial notification if dependencies are missing
            if self._tray:
                if not ffmpeg_ok:
                    threading.Timer(
                        2.0,
                        lambda: self._tray.show_notification(
                            "FFmpeg Missing", ffmpeg_msg, is_error=True
                        ),
                    ).start()
                elif not vcam_ok:
                    threading.Timer(
                        2.0,
                        lambda: self._tray.show_notification(
                            "Virtual Camera Driver Missing", vcam_msg, is_error=True
                        ),
                    ).start()

            self._tray.run()
        except Exception as e:
            log.exception("Tray application crashed")
            print(f"CRITICAL ERROR: Tray app crashed: {e}")
            sys.exit(1)

    # ── tray callbacks ───────────────────────────────────

    async def _on_frame_decoded(self, frame) -> None:
        """Callback from decoder when a frame is successfully decoded."""
        self._conn_mgr.report_frame_received()

    def _start_streaming(self) -> None:
        if self._streaming:
            return
        log.info("Starting streaming pipeline (%s mode) …", self._config.protocol.value)

        # 1. Create Protocol Adapter
        try:
            self._protocol_adapter = self._protocol_factory.create_adapter(
                self._config.protocol,
                on_connect=self._on_sender_connect,
                on_disconnect=self._on_sender_disconnect,
                width=self._config.frame_width,
                height=self._config.frame_height,
            )
        except Exception as e:
            log.exception("Failed to create protocol adapter")
            self._tray.show_notification(
                "Error", f"Failed to create protocol adapter: {e}", is_error=True
            )
            return

        # 2. Start Adapter (async)
        port = (
            self._config.rtmp_port
            if self._config.protocol == ProtocolType.RTMP
            else self._config.srt_port
        )
        future = asyncio.run_coroutine_threadsafe(
            self._protocol_adapter.start(port=port), self._loop
        )
        try:
            future.result(timeout=10)
        except Exception as e:
            log.error("Protocol adapter failed to start: %s", e)
            self._tray.show_notification(
                f"Failed to start {self._config.protocol.value} server: {e}", "Error"
            )
            return

        # 3. Start Decoder
        try:
            self._decoder.start(self._protocol_adapter)
        except Exception as e:
            log.error("Decoder failed: %s", e)
            self._tray.show_notification(
                "Error", f"Decoder failed (FFmpeg missing?): {e}", is_error=True
            )
            asyncio.run_coroutine_threadsafe(self._protocol_adapter.stop(), self._loop)
            return

        # 4. Start Virtual Camera
        vcam_success = False
        try:
            self._vcam.start(frame_source=lambda: self._decoder.latest_frame)
            vcam_success = True
        except Exception as e:
            log.error("Virtual camera failed to start: %s", e)
            # Continue anyway, server still works

        # 5. Start Info Server (async)
        self._server.set_protocol_adapter(self._protocol_adapter)
        self._server.set_http_port(self._config.http_port)
        future = asyncio.run_coroutine_threadsafe(self._server.start(), self._loop)
        try:
            future.result(timeout=10)
        except Exception as e:
            log.error("Info server failed to start: %s", e)
            # This is not critical for streaming itself

        # 6. Start Connection Monitoring
        self._conn_mgr.start_monitoring()
        self._conn_mgr.set_auto_reconnect(self._config.auto_reconnect)

        self._streaming = True
        self._tray.set_access_urls(
            self._protocol_adapter.get_connection_urls(self._server._local_ips)
        )
        self._tray.set_streaming(True)
        self._tray.update_connection_state(
            ConnectionState.DISCONNECTED
        )  # Initial state

        log.info("Pipeline ready. Protocol: %s", self._config.protocol.value)

    def _stop_streaming(self) -> None:
        if not self._streaming:
            return
        log.info("Stopping streaming pipeline …")

        # Stop monitoring
        self._conn_mgr.stop_monitoring()

        # Stop server
        asyncio.run_coroutine_threadsafe(self._server.stop(), self._loop)

        # Stop virtual camera
        self._vcam.stop()

        # Stop decoder
        self._decoder.stop()

        # Stop adapter
        if self._protocol_adapter:
            asyncio.run_coroutine_threadsafe(self._protocol_adapter.stop(), self._loop)
            self._protocol_adapter = None

        self._streaming = False
        self._tray.set_streaming(False)
        self._tray.update_connection_state(ConnectionState.DISCONNECTED)
        log.info("Pipeline stopped")

    def _exit(self) -> None:
        log.info("Exiting …")
        self._stop_streaming()

        # Shut down asyncio loop
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._loop_thread:
            self._loop_thread.join(timeout=3)

        log.info("Goodbye")

    # ── connection callbacks ──────────────────────────────

    def _on_connection_state_change(self, state: ConnectionState) -> None:
        """Callback from connection manager when state changes."""
        log.info("Connection state changed: %s", state.value)
        self._tray.update_connection_state(state)

        # If we just connected, update total URLs (might have changed based on adapter)
        if state == ConnectionState.CONNECTED and self._protocol_adapter:
            self._tray.set_access_urls(
                self._protocol_adapter.get_connection_urls(self._server._local_ips)
            )

    def _on_connection_health_change(self, health: ConnectionHealth) -> None:
        """Callback from connection manager when health changes."""
        self._tray.update_connection_health(health)

    def _on_reconnect_trigger(self) -> None:
        """Callback from connection manager when reconnection is needed."""
        log.info("Automatic reconnection triggered")
        # Reuse existing stop/start logic but don't stop the whole pipeline if possible
        # For simplicity in this version, we restart the adapter and decoder
        if self._streaming:
            # Run in loop thread
            asyncio.run_coroutine_threadsafe(self._restart_adapter(), self._loop)

    async def _restart_adapter(self) -> None:
        """Helper to restart the protocol adapter during reconnection."""
        if not self._protocol_adapter:
            return

        log.info("Restarting protocol adapter …")
        await self._protocol_adapter.stop()

        port = (
            self._config.rtmp_port
            if self._config.protocol == ProtocolType.RTMP
            else self._config.srt_port
        )
        try:
            await self._protocol_adapter.start(port=port)
            # Re-start decoder with the same adapter instance (which now has a new process)
            self._decoder.stop()
            self._decoder.start(self._protocol_adapter)
        except Exception as e:
            log.error("Failed to restart adapter: %s", e)

    # ── data callbacks ───────────────────────────────────

    def _on_sender_connect(self) -> None:
        log.info("Sender connected — stream active")
        self._conn_mgr.report_connection_established()

    def _on_sender_disconnect(self) -> None:
        log.info("Sender disconnected — waiting for reconnection")
        self._conn_mgr.report_connection_lost()

    # ── settings ─────────────────────────────────────────

    def _show_settings(self) -> None:
        """Show the settings dialog and handle results."""
        log.info("Opening settings dialog …")

        def on_save(new_config: AppConfig):
            log.info("Settings saved. Applying changes …")
            # 1. Update config
            self._config = new_config
            self._config_mgr.save(new_config)

            # 2. Update components that can be updated live
            self._conn_mgr.set_auto_reconnect(new_config.auto_reconnect)

            # 3. If streaming, some changes require restart
            if self._streaming:
                self._tray.show_notification(
                    "Settings Updated",
                    "Settings saved. Restart streaming to apply protocol or port changes.",
                )

        dialog = SettingsDialog(self._config, on_save=on_save)
        dialog.show()

    def _show_logs(self) -> None:
        """Show the log viewer dialog."""
        log.info("Opening log viewer …")
        viewer = LogViewer(log_file=config.LOG_FILE)
        viewer.show()

    def _on_protocol_change(self, protocol: str) -> None:
        """Handle protocol change from tray menu."""
        try:
            protocol_enum = ProtocolType(protocol.upper())
        except ValueError:
            log.error(f"Invalid protocol: {protocol}")
            return

        log.info(f"Protocol changed to {protocol}")
        self._config.protocol = protocol_enum
        self._config_mgr.save(self._config)

        self._tray.set_protocol(protocol)

        if self._streaming:
            self._tray.show_notification(
                "Protocol Changed",
                f"Switched to {protocol}. Restart streaming to apply.",
                is_error=False,
            )
        else:
            self._tray.show_notification(
                "Protocol Selected",
                f"{protocol} will be used on next stream start.",
                is_error=False,
            )

    # ── internal ─────────────────────────────────────────

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    @staticmethod
    def _setup_logging() -> None:
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(config.LOG_FORMAT))

        # Create file handler
        file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(config.LOG_FORMAT))

        # Configure root logger
        root = logging.getLogger()
        if not root.handlers:  # Avoid duplicates
            root.setLevel(config.LOG_LEVEL)
            root.addHandler(console_handler)
            root.addHandler(file_handler)


def main():
    app = Application()
    app.run()


if __name__ == "__main__":
    main()
