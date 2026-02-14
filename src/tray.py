"""
System-tray application controller.

Provides a simple tray icon with:
  - Start / Stop streaming (toggle)
  - Copy access URL
  - Show QR code
  - Exit
"""

import threading
import logging
import socket
import io

from PIL import Image, ImageDraw
import pystray
import qrcode

from src.connection_manager import ConnectionState, ConnectionHealth

log = logging.getLogger(__name__)


def _create_icon_image(size: int = 64, streaming: bool = False) -> Image.Image:
    """Programmatically create a simple tray icon (no external .ico needed)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Circle background
    bg_color = (108, 92, 231) if not streaming else (0, 206, 201)
    draw.ellipse([(2, 2), (size - 2, size - 2)], fill=bg_color)
    # Camera-lens circle
    r = size // 5
    cx, cy = size // 2, size // 2
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(255, 255, 255, 220))
    sr = r // 2
    draw.ellipse([(cx - sr, cy - sr), (cx + sr, cy + sr)], fill=bg_color)
    return img


def _create_state_icon(
    size: int = 64,
    state: ConnectionState = ConnectionState.DISCONNECTED,
    health: ConnectionHealth = ConnectionHealth.CRITICAL,
) -> Image.Image:
    """
    Create tray icon based on connection state and health.

    Icon colors:
    - DISCONNECTED: Gray
    - CONNECTING: Yellow
    - CONNECTED (excellent/good): Green
    - CONNECTED (poor/critical): Yellow with warning
    - RECONNECTING: Orange

    Parameters
    ----------
    size : int
        Icon size in pixels
    state : ConnectionState
        Current connection state
    health : ConnectionHealth
        Current connection health (used when CONNECTED)

    Returns
    -------
    Image.Image
        PIL Image for the tray icon
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Determine background color based on state and health
    if state == ConnectionState.DISCONNECTED:
        bg_color = (128, 128, 128)  # Gray
    elif state == ConnectionState.CONNECTING:
        bg_color = (255, 193, 7)  # Yellow
    elif state == ConnectionState.RECONNECTING:
        bg_color = (255, 152, 0)  # Orange
    elif state == ConnectionState.CONNECTED:
        # Green for excellent/good, yellow for poor/critical
        if health in (ConnectionHealth.EXCELLENT, ConnectionHealth.GOOD):
            bg_color = (76, 175, 80)  # Green
        else:
            bg_color = (255, 193, 7)  # Yellow (warning)
    else:
        bg_color = (128, 128, 128)  # Default gray

    # Circle background
    draw.ellipse([(2, 2), (size - 2, size - 2)], fill=bg_color)

    # Camera-lens circle
    r = size // 5
    cx, cy = size // 2, size // 2
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(255, 255, 255, 220))
    sr = r // 2
    draw.ellipse([(cx - sr, cy - sr), (cx + sr, cy + sr)], fill=bg_color)

    # Add warning indicator for poor health when connected
    if state == ConnectionState.CONNECTED and health in (
        ConnectionHealth.POOR,
        ConnectionHealth.CRITICAL,
    ):
        # Small warning badge in bottom-right corner
        badge_size = size // 4
        badge_x = size - badge_size - 2
        badge_y = size - badge_size - 2
        # Warning triangle
        points = [
            (badge_x + badge_size // 2, badge_y),  # Top
            (badge_x, badge_y + badge_size),  # Bottom-left
            (badge_x + badge_size, badge_y + badge_size),  # Bottom-right
        ]
        draw.polygon(points, fill=(255, 87, 34))  # Orange warning
        # Exclamation mark
        draw.line(
            [
                (badge_x + badge_size // 2, badge_y + badge_size // 4),
                (badge_x + badge_size // 2, badge_y + badge_size // 2),
            ],
            fill=(255, 255, 255),
            width=2,
        )
        draw.ellipse(
            [
                (badge_x + badge_size // 2 - 1, badge_y + badge_size * 3 // 4 - 1),
                (badge_x + badge_size // 2 + 1, badge_y + badge_size * 3 // 4 + 1),
            ],
            fill=(255, 255, 255),
        )

    return img


class TrayApp:
    """System tray icon for controlling the virtual camera pipeline."""

    def __init__(
        self,
        on_start=None,
        on_stop=None,
        on_exit=None,
        on_settings=None,
        on_view_logs=None,
        on_protocol_change=None,
    ):
        """
        Parameters
        ----------
        on_start : callable
            Called when user clicks "Start Streaming".
        on_stop : callable
            Called when user clicks "Stop Streaming".
        on_exit : callable
            Called when user clicks "Exit".
        on_settings : callable
            Called when user clicks "Settings...".
        on_view_logs : callable
            Called when user clicks "View Logs/Diagnostics...".
        on_protocol_change : callable
            Called when user selects a different protocol from menu.
        """
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_exit = on_exit
        self._on_settings = on_settings
        self._on_view_logs = on_view_logs
        self._on_protocol_change = on_protocol_change
        self._streaming = False
        self._access_urls: list[str] = []
        self._icon: pystray.Icon | None = None
        self._current_protocol = "RTMP"

        # Connection state tracking
        self._connection_state = ConnectionState.DISCONNECTED
        self._connection_health = ConnectionHealth.CRITICAL

    # ── public API ───────────────────────────────────────

    def set_streaming(self, state: bool) -> None:
        self._streaming = state
        if self._icon:
            self._icon.icon = _create_icon_image(streaming=state)
            self._icon.update_menu()

    def set_access_urls(self, urls: list[str]) -> None:
        self._access_urls = urls
        if self._icon:
            self._update_all()

    def update_connection_state(self, state: ConnectionState) -> None:
        """
        Update tray icon based on connection state.

        Parameters
        ----------
        state : ConnectionState
            New connection state (DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING)
        """
        self._connection_state = state
        if self._icon:
            self._update_all()
            log.info(f"Tray icon updated for state: {state.value}")

    def update_connection_health(self, health: ConnectionHealth) -> None:
        """
        Update tray icon indicator for connection health.

        Parameters
        ----------
        health : ConnectionHealth
            New connection health (EXCELLENT, GOOD, POOR, CRITICAL)
        """
        self._connection_health = health
        if self._icon:
            self._update_all()
            # No need to update menu for health changes
            log.info(f"Tray icon updated for health: {health.value}")

    def _update_all(self) -> None:
        """Update icon, title (tooltip), and menu."""
        if not self._icon:
            return

        # Update Icon
        self._icon.icon = _create_state_icon(
            state=self._connection_state, health=self._connection_health
        )

        # Update Tooltip (title)
        state_str = self._connection_state.value.capitalize()
        health_str = (
            f" (Health: {self._connection_health.value.capitalize()})"
            if self._connection_state == ConnectionState.CONNECTED
            else ""
        )
        self._icon.title = f"Local Virtual Camera - {state_str}{health_str}"

        # Update Menu
        self._icon.menu = self._create_menu()
        self._icon.update_menu()

    def set_protocol(self, protocol: str) -> None:
        self._current_protocol = protocol
        if self._icon:
            self._update_all()

    def _create_menu(self) -> pystray.Menu:
        """Create the tray menu dynamically based on current state."""
        state_info = f"Status: {self._connection_state.value.capitalize()}"
        if self._connection_state == ConnectionState.CONNECTED:
            state_info += f" ({self._connection_health.value.capitalize()})"

        start_label = "Stop Streaming" if self._streaming else "Start Streaming"

        # Protocol submenu
        def create_protocol_menu():
            def select_rtmp(item):
                if self._on_protocol_change:
                    self._on_protocol_change("RTMP")

            def select_srt(item):
                if self._on_protocol_change:
                    self._on_protocol_change("SRT")

            def select_webrtc(item):
                if self._on_protocol_change:
                    self._on_protocol_change("WebRTC")

            rtmp_check = " [x]" if self._current_protocol == "RTMP" else ""
            srt_check = " [x]" if self._current_protocol == "SRT" else ""
            webrtc_check = " [x]" if self._current_protocol == "WebRTC" else ""

            return pystray.Menu(
                pystray.MenuItem(f"RTMP{rtmp_check}", select_rtmp),
                pystray.MenuItem(f"SRT{srt_check}", select_srt),
                pystray.MenuItem(f"WebRTC{webrtc_check}", select_webrtc),
            )

        menu = pystray.Menu(
            pystray.MenuItem(state_info, lambda _: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(start_label, self._toggle, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings...", self._show_settings),
            pystray.MenuItem("View Logs...", self._show_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._exit),
        )

        return menu

    def run(self) -> None:
        """Run the tray icon (blocking — call from the main thread)."""
        self._icon = pystray.Icon(
            name="LocalVirtualCamera",
            title="Local Virtual Camera",
            icon=_create_state_icon(
                state=self._connection_state, health=self._connection_health
            ),
            menu=self._create_menu(),
        )
        self._icon.run()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    # ── callbacks ────────────────────────────────────────

    def _toggle(self, icon, item):
        if self._streaming:
            if self._on_stop:
                self._on_stop()
        else:
            if self._on_start:
                self._on_start()

    def _copy_url(self, icon, item):
        url = self._access_urls[0] if self._access_urls else "—"
        self._copy_to_clipboard(url)

    def _copy_specific_url(self, url: str):
        self._copy_to_clipboard(url)

    def _copy_to_clipboard(self, text: str):
        try:
            import subprocess

            subprocess.Popen(
                ["clip.exe"],
                stdin=subprocess.PIPE,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            ).communicate(text.encode("utf-8"))
            log.info("Copied to clipboard: %s", text)
        except Exception:
            log.warning("Could not copy to clipboard")

    def _show_qr(self, icon, item):
        if not self._access_urls:
            return
        url = self._access_urls[0]
        threading.Thread(target=self._display_qr, args=(url,), daemon=True).start()

    def _show_settings(self, icon, item):
        if self._on_settings:
            # Run settings in a thread to avoid blocking the tray icon
            threading.Thread(target=self._on_settings, daemon=True).start()
        else:
            log.info("Settings callback not set")

    def _show_logs(self, icon, item):
        if self._on_view_logs:
            # Run in a thread to avoid blocking the tray icon
            threading.Thread(target=self._on_view_logs, daemon=True).start()
        else:
            log.info("View logs callback not set")

    def _exit(self, icon, item):
        icon.stop()
        if self._on_exit:
            self._on_exit()

    # ── notifications ─────────────────────────────────────

    def show_notification(
        self, title: str, message: str, is_error: bool = False
    ) -> None:
        """Show a Windows toast notification."""
        try:
            from win10toast import ToastNotifier

            toaster = ToastNotifier()
            toaster.show_toast(
                title=title,
                msg=message,
                duration=3,
                icon_path=None,
                threaded=False,
            )
            log.info(f"Notification shown: {title} - {message}")
        except ImportError:
            log.debug("win10toast not available, skipping notification")
        except Exception:
            log.exception("Failed to show notification")

    # ── QR display ───────────────────────────────────────

    @staticmethod
    def _display_qr(url: str) -> None:
        """Show QR code in a simple Tk window."""
        try:
            import tkinter as tk
            from PIL import ImageTk

            qr = qrcode.QRCode(box_size=8, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="white", back_color="#16161e")
            qr_img = qr_img.convert("RGB")

            root = tk.Tk()
            root.title("Scan to Connect")
            root.configure(bg="#16161e")
            root.resizable(False, False)

            tk_img = ImageTk.PhotoImage(qr_img)
            lbl_img = tk.Label(root, image=tk_img, bg="#16161e")
            lbl_img.pack(padx=10, pady=(10, 4))

            lbl_url = tk.Label(
                root,
                text=url,
                fg="#8888a0",
                bg="#16161e",
                font=("Segoe UI", 10),
            )
            lbl_url.pack(pady=(0, 10))

            # Centre on screen
            root.update_idletasks()
            w, h = root.winfo_width(), root.winfo_height()
            x = (root.winfo_screenwidth() - w) // 2
            y = (root.winfo_screenheight() - h) // 2
            root.geometry(f"+{x}+{y}")
            root.attributes("-topmost", True)
            root.mainloop()
        except Exception:
            log.exception("Failed to display QR code window")
