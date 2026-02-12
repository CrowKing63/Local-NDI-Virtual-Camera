"""
Unit tests for SRT Protocol Adapter.

Tests the SRTAdapter implementation to ensure it correctly implements the
ProtocolAdapter interface and provides SRT-specific functionality.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from src.protocols.srt import SRTAdapter


class TestSRTAdapter:
    """Test suite for SRTAdapter class."""
    
    def test_init(self):
        """Test SRTAdapter initialization."""
        on_connect = Mock()
        on_disconnect = Mock()
        
        adapter = SRTAdapter(
            on_connect=on_connect,
            on_disconnect=on_disconnect,
            width=1920,
            height=1080,
        )
        
        assert adapter._on_connect is on_connect
        assert adapter._on_disconnect is on_disconnect
        assert adapter._width == 1920
        assert adapter._height == 1080
        assert adapter._port is None
        assert adapter._proc is None
        assert adapter._connected is False
        assert adapter._monitor_task is None
    
    def test_init_defaults(self):
        """Test SRTAdapter initialization with default parameters."""
        adapter = SRTAdapter()
        
        assert adapter._on_connect is None
        assert adapter._on_disconnect is None
        assert adapter._width == 1280  # Default from config
        assert adapter._height == 720  # Default from config
    
    @pytest.mark.asyncio
    async def test_start_no_ffmpeg(self):
        """Test start() raises error when FFmpeg is not found."""
        adapter = SRTAdapter()
        
        with patch('src.protocols.srt.config.FFMPEG_BIN', None):
            with pytest.raises(RuntimeError, match="ffmpeg not found"):
                await adapter.start(port=9000)
    
    @pytest.mark.asyncio
    async def test_start_success(self):
        """Test successful start of SRT server."""
        adapter = SRTAdapter()
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        
        with patch('src.protocols.srt.config.FFMPEG_BIN', '/usr/bin/ffmpeg'):
            with patch('src.protocols.srt.subprocess.Popen', return_value=mock_proc):
                with patch('src.protocols.srt.asyncio.create_task') as mock_create_task:
                    await adapter.start(port=9000)
        
        assert adapter._port == 9000
        assert adapter._proc is mock_proc
        mock_create_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_already_started(self):
        """Test start() when adapter is already running."""
        adapter = SRTAdapter()
        adapter._proc = MagicMock()  # Simulate already running
        
        with patch('src.protocols.srt.config.FFMPEG_BIN', '/usr/bin/ffmpeg'):
            with patch('src.protocols.srt.subprocess.Popen') as mock_popen:
                await adapter.start(port=9000)
        
        # Should not create new process
        mock_popen.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_start_command_format(self):
        """Test that start() builds correct FFmpeg command for SRT."""
        adapter = SRTAdapter(width=1920, height=1080)
        mock_proc = MagicMock()
        
        with patch('src.protocols.srt.config.FFMPEG_BIN', '/usr/bin/ffmpeg'):
            with patch('src.protocols.srt.subprocess.Popen', return_value=mock_proc) as mock_popen:
                with patch('src.protocols.srt.asyncio.create_task'):
                    await adapter.start(port=9000)
        
        # Verify FFmpeg command
        call_args = mock_popen.call_args[0][0]
        assert call_args[0] == '/usr/bin/ffmpeg'
        assert 'srt://0.0.0.0:9000?mode=listener' in call_args
        assert '-f' in call_args
        assert 'rawvideo' in call_args
        assert '-pix_fmt' in call_args
        assert 'rgb24' in call_args
        assert '-s' in call_args
        assert '1920x1080' in call_args
        assert 'pipe:1' in call_args
    
    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stop() cleans up resources."""
        adapter = SRTAdapter()
        
        # Setup mock process and task
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()
        adapter._proc = mock_proc
        
        # Create an async mock task
        async def mock_coro():
            pass
        
        mock_task = asyncio.create_task(mock_coro())
        adapter._monitor_task = mock_task
        adapter._connected = True
        
        on_disconnect = Mock()
        adapter._on_disconnect = on_disconnect
        
        await adapter.stop()
        
        # Verify cleanup
        mock_proc.stdin.close.assert_called_once()
        mock_proc.terminate.assert_called_once()
        assert adapter._proc is None
        assert adapter._monitor_task is None
        assert adapter._connected is False
        on_disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_force_kill(self):
        """Test stop() force kills process if terminate times out."""
        import subprocess as sp
        
        adapter = SRTAdapter()
        
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock(side_effect=[
            sp.TimeoutExpired(cmd='ffmpeg', timeout=3),  # First wait times out
            None  # Second wait (after kill) succeeds
        ])
        mock_proc.kill = MagicMock()
        adapter._proc = mock_proc
        
        await adapter.stop()
        
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()
    
    def test_get_connection_urls(self):
        """Test get_connection_urls() returns correct SRT URLs."""
        adapter = SRTAdapter()
        adapter._port = 9000
        
        local_ips = ["192.168.1.100", "10.0.0.50"]
        urls = adapter.get_connection_urls(local_ips)
        
        assert len(urls) == 2
        assert urls[0] == "srt://192.168.1.100:9000"
        assert urls[1] == "srt://10.0.0.50:9000"
    
    def test_get_connection_urls_not_started(self):
        """Test get_connection_urls() returns empty list when not started."""
        adapter = SRTAdapter()
        
        urls = adapter.get_connection_urls(["192.168.1.100"])
        
        assert urls == []
    
    def test_get_connection_instructions(self):
        """Test get_connection_instructions() returns SRT-specific instructions."""
        adapter = SRTAdapter()
        
        instructions = adapter.get_connection_instructions()
        
        assert "SRT" in instructions
        assert "lower latency" in instructions
        assert "<150ms" in instructions
        assert "error recovery" in instructions
    
    def test_is_connected_property(self):
        """Test is_connected property."""
        adapter = SRTAdapter()
        
        assert adapter.is_connected is False
        
        adapter._connected = True
        assert adapter.is_connected is True
    
    def test_get_stdout(self):
        """Test get_stdout() returns FFmpeg process."""
        adapter = SRTAdapter()
        
        assert adapter.get_stdout() is None
        
        mock_proc = MagicMock()
        adapter._proc = mock_proc
        
        assert adapter.get_stdout() is mock_proc
    
    @pytest.mark.asyncio
    async def test_monitor_connection_detects_connect(self):
        """Test _monitor_connection() detects client connection."""
        adapter = SRTAdapter()
        on_connect = Mock()
        adapter._on_connect = on_connect
        
        # Mock stderr with connection message
        mock_stderr = MagicMock()
        mock_stderr.readline = Mock(side_effect=[
            b"SRT CONNECTED\n",
            b"",  # EOF
        ])
        
        mock_proc = MagicMock()
        mock_proc.stderr = mock_stderr
        adapter._proc = mock_proc
        
        await adapter._monitor_connection()
        
        assert adapter._connected is False  # Reset on EOF
        on_connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitor_connection_detects_stream(self):
        """Test _monitor_connection() detects connection via stream info."""
        adapter = SRTAdapter()
        on_connect = Mock()
        adapter._on_connect = on_connect
        
        # Mock stderr with stream detection
        mock_stderr = MagicMock()
        mock_stderr.readline = Mock(side_effect=[
            b"Stream #0:0: Video: h264\n",
            b"",  # EOF
        ])
        
        mock_proc = MagicMock()
        mock_proc.stderr = mock_stderr
        adapter._proc = mock_proc
        
        await adapter._monitor_connection()
        
        on_connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitor_connection_detects_disconnect(self):
        """Test _monitor_connection() detects client disconnection."""
        adapter = SRTAdapter()
        adapter._connected = True
        on_disconnect = Mock()
        adapter._on_disconnect = on_disconnect
        
        # Mock stderr with disconnection message
        mock_stderr = MagicMock()
        mock_stderr.readline = Mock(side_effect=[
            b"connection closed\n",
            b"",  # EOF
        ])
        
        mock_proc = MagicMock()
        mock_proc.stderr = mock_stderr
        adapter._proc = mock_proc
        
        await adapter._monitor_connection()
        
        assert adapter._connected is False
        on_disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitor_connection_handles_eof(self):
        """Test _monitor_connection() handles EOF gracefully."""
        adapter = SRTAdapter()
        adapter._connected = True
        on_disconnect = Mock()
        adapter._on_disconnect = on_disconnect
        
        # Mock stderr with immediate EOF
        mock_stderr = MagicMock()
        mock_stderr.readline = Mock(return_value=b"")
        
        mock_proc = MagicMock()
        mock_proc.stderr = mock_stderr
        adapter._proc = mock_proc
        
        await adapter._monitor_connection()
        
        assert adapter._connected is False
        on_disconnect.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
