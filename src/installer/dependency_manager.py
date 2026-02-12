"""
Dependency management for RTMP Virtual Camera.

Checks for required external dependencies:
1. FFmpeg (ffmpeg.exe) - required for decoding and streaming.
2. Unity Capture - virtual camera driver.
"""
import logging
import shutil
import subprocess
import os

log = logging.getLogger(__name__)


class DependencyManager:
    """Checks and manages external dependencies."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin

    def check_ffmpeg(self) -> tuple[bool, str]:
        """
        Check if FFmpeg is available.
        
        Returns
        -------
        (bool, str) : (Success, Status Message)
        """
        path = shutil.which(self.ffmpeg_bin)
        if path:
            try:
                # Try running ffmpeg -version to ensure it's functional
                subprocess.run(
                    [path, "-version"], 
                    capture_output=True, 
                    check=True,
                    creationflags=0x08000000 # CREATE_NO_WINDOW
                )
                return True, f"FFmpeg found at {path}"
            except Exception as e:
                return False, f"FFmpeg found but failed to run: {e}"
        
        return False, "FFmpeg (ffmpeg.exe) not found in PATH or configured location."

    def check_unity_capture(self) -> tuple[bool, str]:
        """
        Check if Unity Capture driver is installed and visible.
        Only applicable on Windows.
        
        Returns
        -------
        (bool, str) : (Success, Status Message)
        """
        if os.name != "nt":
            return False, "Unity Capture is only supported on Windows."

        try:
            # We check for the presence of the device in FFmpeg's dshow list
            # Note: This requires FFmpeg to be working.
            ffmpeg_path = shutil.which(self.ffmpeg_bin)
            if not ffmpeg_path:
                return False, "Cannot check for Unity Capture without FFmpeg."

            result = subprocess.run(
                [ffmpeg_path, "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                capture_output=True,
                text=True,
                creationflags=0x08000000 # CREATE_NO_WINDOW
            )
            
            # The output of -list_devices goes to stderr in FFmpeg
            output = result.stderr
            if "Unity Video Capture" in output or "Unity Capture" in output:
                return True, "Unity Capture driver found."
            
            return False, "Unity Capture driver not found in DirectShow devices."

        except Exception as e:
            return False, f"Error checking for Unity Capture: {e}"

    def get_status(self) -> dict[str, tuple[bool, str]]:
        """Return a dictionary of all dependency statuses."""
        return {
            "ffmpeg": self.check_ffmpeg(),
            "unity_capture": self.check_unity_capture()
        }
