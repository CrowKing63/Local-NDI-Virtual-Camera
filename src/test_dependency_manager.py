import pytest
import shutil
from unittest.mock import MagicMock, patch
from src.installer.dependency_manager import DependencyManager

@pytest.fixture
def dep_mgr():
    return DependencyManager(ffmpeg_bin="ffmpeg")

def test_check_ffmpeg_found(dep_mgr):
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            success, msg = dep_mgr.check_ffmpeg()
            assert success is True
            assert "found" in msg.lower()

def test_check_ffmpeg_not_found(dep_mgr):
    with patch("shutil.which", return_value=None):
        success, msg = dep_mgr.check_ffmpeg()
        assert success is False
        assert "not found" in msg.lower()

def test_check_unity_capture_not_windows(dep_mgr):
    with patch("os.name", "posix"):
        success, msg = dep_mgr.check_unity_capture()
        assert success is False
        assert "only supported on Windows" in msg

def test_check_unity_capture_found(dep_mgr):
    with patch("os.name", "nt"):
        with patch("shutil.which", return_value="ffmpeg"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stderr="DirectShow video devices\n[dshow @ 0x...] \"Unity Video Capture\"")
                success, msg = dep_mgr.check_unity_capture()
                assert success is True
                assert "found" in msg.lower()
