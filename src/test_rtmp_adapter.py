"""
Unit tests for RTMPAdapter.

Tests the RTMP protocol adapter implementation, including connection URL
generation, connection state tracking, and FFmpeg process management.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
import subprocess

from src.protocols.rtmp import RTMPAdapter


class TestRTMPAdapter:
    """Test suite for RTMPAdapter class."""
    
    def test_initialization(self):
        """Test RTMPAdapter initializes with correct defaults."""
        adapter = RTMPAdapter()
        
        assert adapter.is_connected is False
        assert adapter._port is None
        assert adapter._path is None
        assert adapter._proc is None
    
    def test_initialization_with_callbacks(self):
        """Test RTMPAdapter initializes with callbacks."""
        on_connect = Mock()
        on_disconnect = Mock()
        
        adapter = RTMPAdapter(
            on_connect=on_connect,
            on_disconnect=on_disconnect
        )
        
        assert adapter._on_connect is on_connect
        assert adapter._on_disconnect is on_disconnect
    
    def test_get_connection_urls_not_started(self):
        """Test get_connection_urls returns empty list when not started."""
        adapter = RTMPAdapter()
        
        urls = adapter.get_connection_urls(["192.168.1.100", "127.0.0.1"])
        
        assert urls == []
    
    def test_get_connection_urls_single_ip(self):
        """Test get_connection_urls with single IP address."""
        adapter = RTMPAdapter()
        adapter._port = 2935
        adapter._path = "live/stream"
        
        urls = adapter.get_connection_urls(["192.168.1.100"])
        
        assert len(urls) == 1
        assert urls[0] == "rtmp://192.168.1.100:2935/live/stream"
    
    def test_get_connection_urls_multiple_ips(self):
        """Test get_connection_urls with multiple IP addresses."""
        adapter = RTMPAdapter()
        adapter._port = 2935
        adapter._path = "live/stream"
        
        urls = adapter.get_connection_urls([
            "192.168.1.100",
            "10.0.0.5",
            "127.0.0.1"
        ])
        
        assert len(urls) == 3
        assert "rtmp://192.168.1.100:2935/live/stream" in urls
        assert "rtmp://10.0.0.5:2935/live/stream" in urls
        assert "rtmp://127.0.0.1:2935/live/stream" in urls
    
    def test_get_connection_urls_custom_port(self):
        """Test get_connection_urls with custom port."""
        adapter = RTMPAdapter()
        adapter._port = 3000
        adapter._path = "custom/path"
        
        urls = adapter.get_connection_urls(["192.168.1.100"])
        
        assert urls[0] == "rtmp://192.168.1.100:3000/custom/path"
    
    def test_get_connection_instructions(self):
        """Test get_connection_instructions returns proper instructions."""
        adapter = RTMPAdapter()
        
        instructions = adapter.get_connection_instructions()
        
        assert "PRISM Live Studio" in instructions
        assert "Larix Broadcaster" in instructions
        assert "RTMP" in instructions
    
    def test_is_connected_initial_state(self):
        """Test is_connected property returns False initially."""
        adapter = RTMPAdapter()
        
        assert adapter.is_connected is False
    
    @pytest.mark.asyncio
    async def test_start_without_ffmpeg(self):
        """Test start raises RuntimeError when FFmpeg is not found."""
        adapter = RTMPAdapter()
        
        with patch('src.protocols.rtmp.config.FFMPEG_BIN', None):
            with pytest.raises(RuntimeError, match="ffmpeg not found"):
                await adapter.start(port=2935, path="live/stream")
    
    @pytest.mark.asyncio
    async def test_start_creates_process(self):
        """Test start creates FFmpeg subprocess with correct arguments."""
        adapter = RTMPAdapter()
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        
        with patch('src.protocols.rtmp.config.FFMPEG_BIN', '/usr/bin/ffmpeg'):
            with patch('subprocess.Popen', return_value=mock_proc) as mock_popen:
                await adapter.start(port=2935, path="live/stream")
                
                # Verify Popen was called
                assert mock_popen.called
                call_args = mock_popen.call_args
                cmd = call_args[0][0]
                
                # Verify key FFmpeg arguments
                assert '/usr/bin/ffmpeg' in cmd
                assert '-rtmp_listen' in cmd
                assert '1' in cmd
                assert 'rtmp://0.0.0.0:2935/live/stream' in cmd
                assert '-f' in cmd
                assert 'rawvideo' in cmd
                assert '-pix_fmt' in cmd
                assert 'rgb24' in cmd
                
                # Verify port and path were stored
                assert adapter._port == 2935
                assert adapter._path == "live/stream"
                assert adapter._proc is mock_proc
    
    @pytest.mark.asyncio
    async def test_start_uses_default_path(self):
        """Test start uses default path from config when path is empty."""
        adapter = RTMPAdapter()
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        
        with patch('src.protocols.rtmp.config.FFMPEG_BIN', '/usr/bin/ffmpeg'):
            with patch('src.protocols.rtmp.config.RTMP_PATH', 'default/path'):
                with patch('subprocess.Popen', return_value=mock_proc):
                    await adapter.start(port=2935, path="")
                    
                    assert adapter._path == "default/path"
    
    @pytest.mark.asyncio
    async def test_start_already_started(self):
        """Test start does nothing when already started."""
        adapter = RTMPAdapter()
        mock_proc = MagicMock()
        adapter._proc = mock_proc
        
        with patch('src.protocols.rtmp.config.FFMPEG_BIN', '/usr/bin/ffmpeg'):
            with patch('subprocess.Popen') as mock_popen:
                await adapter.start(port=2935, path="live/stream")
                
                # Popen should not be called again
                assert not mock_popen.called
    
    @pytest.mark.asyncio
    async def test_stop_terminates_process(self):
        """Test stop terminates FFmpeg process."""
        adapter = RTMPAdapter()
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.wait = MagicMock()
        adapter._proc = mock_proc
        
        await adapter.stop()
        
        # Verify process was terminated
        assert mock_proc.stdin.close.called
        assert mock_proc.terminate.called
        assert mock_proc.wait.called
        assert adapter._proc is None
    
    @pytest.mark.asyncio
    async def test_stop_kills_process_on_timeout(self):
        """Test stop kills process if terminate times out."""
        adapter = RTMPAdapter()
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.wait = MagicMock(side_effect=[
            subprocess.TimeoutExpired(cmd='ffmpeg', timeout=3),
            None  # Second wait after kill succeeds
        ])
        adapter._proc = mock_proc
        
        await adapter.stop()
        
        # Verify process was killed after timeout
        assert mock_proc.kill.called
        assert adapter._proc is None
    
    @pytest.mark.asyncio
    async def test_stop_calls_disconnect_callback(self):
        """Test stop calls on_disconnect callback if connected."""
        on_disconnect = Mock()
        adapter = RTMPAdapter(on_disconnect=on_disconnect)
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        adapter._proc = mock_proc
        adapter._connected = True
        
        await adapter.stop()
        
        # Verify disconnect callback was called
        assert on_disconnect.called
        assert adapter._connected is False
    
    @pytest.mark.asyncio
    async def test_stop_no_callback_when_not_connected(self):
        """Test stop doesn't call on_disconnect if not connected."""
        on_disconnect = Mock()
        adapter = RTMPAdapter(on_disconnect=on_disconnect)
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        adapter._proc = mock_proc
        adapter._connected = False
        
        await adapter.stop()
        
        # Verify disconnect callback was not called
        assert not on_disconnect.called
    
    @pytest.mark.asyncio
    async def test_stop_when_not_started(self):
        """Test stop does nothing when adapter not started."""
        adapter = RTMPAdapter()
        
        # Should not raise any errors
        await adapter.stop()
        
        assert adapter._proc is None
    
    def test_get_stdout_returns_process(self):
        """Test get_stdout returns FFmpeg process."""
        adapter = RTMPAdapter()
        mock_proc = MagicMock()
        adapter._proc = mock_proc
        
        result = adapter.get_stdout()
        
        assert result is mock_proc
    
    def test_get_stdout_returns_none_when_not_started(self):
        """Test get_stdout returns None when not started."""
        adapter = RTMPAdapter()
        
        result = adapter.get_stdout()
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_backward_compatibility_port_2935(self):
        """Test adapter uses default RTMP port 2935 for backward compatibility."""
        adapter = RTMPAdapter()
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        
        with patch('src.protocols.rtmp.config.FFMPEG_BIN', '/usr/bin/ffmpeg'):
            with patch('subprocess.Popen', return_value=mock_proc) as mock_popen:
                await adapter.start(port=2935, path="live/stream")
                
                call_args = mock_popen.call_args
                cmd = call_args[0][0]
                
                # Verify port 2935 is in the command
                assert 'rtmp://0.0.0.0:2935/live/stream' in cmd
    
    @pytest.mark.asyncio
    async def test_multiple_connection_attempts(self):
        """Test adapter handles multiple start attempts gracefully."""
        adapter = RTMPAdapter()
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        
        with patch('src.protocols.rtmp.config.FFMPEG_BIN', '/usr/bin/ffmpeg'):
            with patch('subprocess.Popen', return_value=mock_proc) as mock_popen:
                # First start
                await adapter.start(port=2935, path="live/stream")
                assert mock_popen.call_count == 1
                
                # Second start should not create new process
                await adapter.start(port=2935, path="live/stream")
                assert mock_popen.call_count == 1  # Still 1


class TestRTMPAdapterBackwardCompatibility:
    """Test backward compatibility with existing RTMP implementation."""
    
    def test_default_rtmp_port_2935(self):
        """Test adapter maintains default RTMP port 2935 (Requirement 10.1)."""
        from src import config
        
        # Verify default port is 2935 for backward compatibility
        assert config.RTMP_PORT == 2935
    
    def test_default_rtmp_path(self):
        """Test adapter maintains default RTMP path (Requirement 10.1)."""
        from src import config
        
        # Verify default path structure is maintained
        assert config.RTMP_PATH == "live/stream"
    
    @pytest.mark.asyncio
    async def test_adapter_uses_config_defaults(self):
        """Test adapter uses config defaults for backward compatibility."""
        from src import config
        adapter = RTMPAdapter()
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        
        with patch('src.protocols.rtmp.config.FFMPEG_BIN', '/usr/bin/ffmpeg'):
            with patch('subprocess.Popen', return_value=mock_proc) as mock_popen:
                # Start with default config values
                await adapter.start(port=config.RTMP_PORT, path="")
                
                # Verify it uses config defaults
                assert adapter._port == 2935
                assert adapter._path == config.RTMP_PATH
    
    def test_connection_url_format_matches_existing(self):
        """Test connection URL format matches existing implementation."""
        adapter = RTMPAdapter()
        adapter._port = 2935
        adapter._path = "live/stream"
        
        urls = adapter.get_connection_urls(["192.168.1.100"])
        
        # Verify URL format matches existing implementation
        # Format: rtmp://{ip}:{port}/{path}
        assert urls[0] == "rtmp://192.168.1.100:2935/live/stream"
        assert urls[0].startswith("rtmp://")
        assert ":2935/" in urls[0]
    
    def test_instructions_mention_prism_live_studio(self):
        """Test instructions mention PRISM Live Studio for compatibility."""
        adapter = RTMPAdapter()
        
        instructions = adapter.get_connection_instructions()
        
        # Verify PRISM Live Studio is mentioned (existing app compatibility)
        assert "PRISM Live Studio" in instructions
    
    @pytest.mark.asyncio
    async def test_ffmpeg_command_structure_compatible(self):
        """Test FFmpeg command structure is compatible with existing implementation."""
        adapter = RTMPAdapter()
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        
        with patch('src.protocols.rtmp.config.FFMPEG_BIN', '/usr/bin/ffmpeg'):
            with patch('subprocess.Popen', return_value=mock_proc) as mock_popen:
                await adapter.start(port=2935, path="live/stream")
                
                call_args = mock_popen.call_args
                cmd = call_args[0][0]
                
                # Verify key arguments match existing implementation
                assert '-rtmp_listen' in cmd
                assert '1' in cmd
                assert '-f' in cmd
                assert 'rawvideo' in cmd
                assert '-pix_fmt' in cmd
                assert 'rgb24' in cmd
                assert '-flags' in cmd
                assert 'low_delay' in cmd
                assert '-fflags' in cmd
                assert 'nobuffer' in cmd
                assert 'pipe:1' in cmd


class TestRTMPAdapterRequirements:
    """Test RTMPAdapter against specific requirements."""
    
    def test_requirement_3_1_prism_compatibility(self):
        """Test RTMP maintains compatibility with PRISM Live Studio (Req 3.1)."""
        adapter = RTMPAdapter()
        
        instructions = adapter.get_connection_instructions()
        
        # Verify PRISM Live Studio is explicitly mentioned
        assert "PRISM Live Studio" in instructions
    
    def test_requirement_3_2_configurable_port(self):
        """Test RTMP supports configurable port (Req 3.2)."""
        adapter = RTMPAdapter()
        
        # Test with various port numbers
        for port in [2935, 3000, 8080, 9000]:
            adapter._port = port
            adapter._path = "live/stream"
            
            urls = adapter.get_connection_urls(["192.168.1.100"])
            
            # Verify port is in the URL
            assert f":{port}/" in urls[0]
    
    @pytest.mark.asyncio
    async def test_requirement_3_4_multiple_connection_attempts(self):
        """Test RTMP handles multiple connection attempts gracefully (Req 3.4)."""
        adapter = RTMPAdapter()
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        
        with patch('src.protocols.rtmp.config.FFMPEG_BIN', '/usr/bin/ffmpeg'):
            with patch('subprocess.Popen', return_value=mock_proc):
                # First connection attempt
                await adapter.start(port=2935, path="live/stream")
                first_proc = adapter._proc
                
                # Stop
                await adapter.stop()
                
                # Second connection attempt
                await adapter.start(port=2935, path="live/stream")
                
                # Should work without requiring restart
                assert adapter._proc is not None
    
    def test_requirement_3_5_correct_url_display(self):
        """Test RTMP displays correct connection URLs (Req 3.5)."""
        adapter = RTMPAdapter()
        adapter._port = 2935
        adapter._path = "live/stream"
        
        test_ips = ["192.168.1.100", "10.0.0.5", "127.0.0.1"]
        urls = adapter.get_connection_urls(test_ips)
        
        # Verify each IP has a corresponding URL
        assert len(urls) == len(test_ips)
        
        # Verify each URL is correctly formatted
        for ip, url in zip(test_ips, urls):
            assert url == f"rtmp://{ip}:2935/live/stream"
    
    def test_requirement_10_1_backward_compatible_port(self):
        """Test RTMP maintains same default port structure (Req 10.1)."""
        from src import config
        
        # Default port should be 2935
        assert config.RTMP_PORT == 2935
        
        # Adapter should use this default
        adapter = RTMPAdapter()
        adapter._port = config.RTMP_PORT
        adapter._path = config.RTMP_PATH
        
        urls = adapter.get_connection_urls(["192.168.1.100"])
        assert "2935" in urls[0]
