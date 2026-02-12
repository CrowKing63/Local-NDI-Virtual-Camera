"""
Virtual camera bridge: sends decoded frames to a pyvirtualcam device.

Runs in its own thread, polling the FrameDecoder for the latest frame
and writing it to the virtual webcam at the configured FPS.
"""
import threading
import time
import logging

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import config

log = logging.getLogger(__name__)

# Optional import — keeps the app importable even if pyvirtualcam isn't
# installed yet (useful for tests).
try:
    import pyvirtualcam
except ImportError:
    pyvirtualcam = None  # type: ignore[assignment]


def _make_standby_frame(
    width: int = config.FRAME_WIDTH,
    height: int = config.FRAME_HEIGHT,
    text: str = "Waiting for connection …",
) -> np.ndarray:
    """Generate a placeholder frame shown when no stream is active."""
    img = Image.new("RGB", (width, height), color=(24, 24, 32))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (width - tw) // 2
    y = (height - th) // 2
    draw.text((x, y), text, fill=(180, 180, 200), font=font)
    return np.array(img)


class VirtualCameraOutput:
    """Bridges decoded frames → system virtual webcam."""

    def __init__(
        self,
        width: int = config.FRAME_WIDTH,
        height: int = config.FRAME_HEIGHT,
        fps: int = config.FPS,
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self._thread: threading.Thread | None = None
        self._running = False
        self._frame_source = None  # callable returning np.ndarray | None
        self._standby = _make_standby_frame(width, height)

    def start(self, frame_source) -> None:
        """
        Start writing frames to the virtual camera.

        Parameters
        ----------
        frame_source : callable
            A zero-arg callable that returns the latest numpy RGB frame
            (or None if no frame is available).
        """
        if pyvirtualcam is None:
            raise RuntimeError(
                "pyvirtualcam is not installed. "
                "Run: pip install pyvirtualcam"
            )
        if self._running:
            return
        self._frame_source = frame_source
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="vcam-output"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        log.debug("Virtual camera output stopped")

    def _loop(self) -> None:
        interval = 1.0 / self.fps
        cam = None
        
        # Try backends in order: UnityCapture (standalone), then OBS (if running)
        backends = ['unitycapture', 'obs']
        
        # Try backends in order: UnityCapture (standalone), then OBS
        # For OBS, pyvirtualcam connects to the 'OBS Virtual Camera' device.
        # This requires OBS to be running and 'Start Virtual Camera' to be active?
        # Actually, pyvirtualcam's 'obs' backend *updates* the virtual camera.
        # But if the user is running OBS 28+, pyvirtualcam might need to use 'unitycapture'
        # or we rely on the user to have installed the legacy obs-virtualcam?
        #
        # Current strategy: 
        # 1. UnityCapture (preferred, if installed)
        # 2. OBS (fallback, but might fail if OBS 28+ internal changes block it)
        
        backends = ['unitycapture', 'obs']
        
        for backend in backends:
            try:
                cam = pyvirtualcam.Camera(
                    width=self.width,
                    height=self.height,
                    fps=self.fps,
                    backend=backend,
                    print_fps=False,
                )
                log.info(f"Virtual camera started using backend: {backend} ({cam.device})")
                break
            except Exception as e:
                log.warning(f"Backend '{backend}' failed: {e}")
        
        if cam is None:
            log.error(
                "Failed to initialize any virtual camera.\n"
                "  - UnityCapture: Ensure driver is installed via setup_driver.py (or manually).\n"
                "  - OBS: Ensure OBS is installed. (Note: OBS 28+ might need legacy plugin?)\n"
            )
            self._running = False
            return

        try:
            with cam:
                while self._running:
                    t0 = time.monotonic()
                    frame = self._frame_source() if self._frame_source else None
                    if frame is None:
                        frame = self._standby
                    # pyvirtualcam expects RGB uint8
                    cam.send(frame)
                    cam.sleep_until_next_frame()
                    elapsed = time.monotonic() - t0
                    sleep_remaining = interval - elapsed
                    if sleep_remaining > 0:
                        time.sleep(sleep_remaining)
        except Exception:
            log.exception("Virtual camera loop crashed")
        finally:
            log.debug("Virtual camera loop exited")
