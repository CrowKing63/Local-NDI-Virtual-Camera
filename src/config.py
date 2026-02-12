"""
Configuration constants for Local Virtual Camera.
"""
import os
import sys
import logging

import shutil

# ── Dependency Check ─────────────────────────────────────
def _find_ffmpeg() -> str | None:
    """Find ffmpeg executable in PATH or common locations."""
    # Check PATH first
    path = shutil.which("ffmpeg")
    if path:
        return path
    
    # Check common locations
    common_paths = [
        "ffmpeg.exe",  # Current directory
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ffmpeg.exe"), # Project root
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        os.path.expanduser(r"~\ffmpeg\bin\ffmpeg.exe"),
        os.path.expanduser(r"~\AppData\Local\Programs\ffmpeg\bin\ffmpeg.exe"),
    ]
    for p in common_paths:
        if os.path.isfile(p):
            return os.path.abspath(p)
    return None

FFMPEG_BIN = _find_ffmpeg()

# ── Network Settings ─────────────────────────────────────
RTMP_PORT = 2935
RTMP_PATH = "live/stream"
HTTP_PORT = 8000
ALLOWED_ORIGINS = None

# ── Video ────────────────────────────────────────────────
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FPS = 30

# ── Paths ────────────────────────────────────────────────
def _app_data_dir() -> str:
    """Return a writable directory for app-generated files (certs, logs)."""
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    d = os.path.join(base, "LocalVirtualCamera")
    os.makedirs(d, exist_ok=True)
    return d

APP_DATA_DIR = _app_data_dir()
APP_DATA_DIR = _app_data_dir()
# CERT_DIR removed as we no longer use SSL

# ── Logging ──────────────────────────────────────────────
LOG_LEVEL = logging.INFO      # Changed from WARNING to see connection logs
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_FILE = os.path.join(APP_DATA_DIR, "app.log")

# ── Resource helpers (for PyInstaller bundle) ────────────
def resource_path(relative: str) -> str:
    """Resolve a path that works both in dev and inside a PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative)
