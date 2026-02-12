"""
Unit tests for WebRTC Protocol Adapter.

Tests the WebRTCAdapter implementation including mDNS advertisement,
signaling server, and peer connection management.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import json

# Mock the optional dependencies before importing
import sys
sys.modules['aiortc'] = MagicMock()
sys.modules['aiortc.contrib'] = MagicMock()
sys.modules['aiortc.contrib.media'] = MagicMock()
sys.modules['zeroconf'] = MagicMock()

from src.protocols.webrtc import WebRTCAdapter, WebRTCConfig, AIORTC_AVAILABLE, ZEROCONF_AVAILABLE


class TestWebRTCConfig:
    """Test WebRTCConfig dataclass."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = WebRTCConfig()
        assert config.service_name == "RTMP Virtual Camera"
        assert config.service_type == "_rtmp-vcam._tcp.local."
        assert config.signaling_port == 8080
        assert config.stun_servers == ["stun:stun.l.google.com:19302"]
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = WebRTCConfig(
            service_name="Test Camera",
            service_type="_test._tcp.local.",
            signaling_port=9090,
            stun_servers=["stun:stun.example.com:3478"]
        )
        assert config.service_name == "Test Camera"
        assert config.service_type == "_test._tcp.local."
        assert config.signaling_port == 9090
        assert config.stun_servers == ["stun:stun.example.com:3478"]


class TestWebRTCAdapter:
    """Test WebRTCAdapter class."""
    
    @pytest.fixture
    def adapter(self):
        """Create a WebRTC adapter for testing."""
        # Mock the availability checks
        with patch('src.protocols.webrtc.AIORTC_AVAILABLE', True), \
             patch('src.protocols.webrtc.ZEROCONF_AVAILABLE', True):
            on_connect = Mock()
            on_disconnect = Mock()
            adapter = WebRTCAdapter(
                on_connect=on_connect,
                on_disconnect=on_disconnect,
                width=1280,
                height=720
            )
            return adapter
    
    def test_initialization(self, adapter):
        """Test adapter initialization."""
        assert adapter._width == 1280
        assert adapter._height == 720
        assert adapter._on_connect is not None
        assert adapter._on_disconnect is not None
        assert adapter._config.service_name == "RTMP Virtual Camera"
        assert adapter._peer_connections == {}
        assert adapter._connected is False
    
    def test_initialization_without_aiortc(self):
        """Test initialization fails without aiortc."""
        with patch('src.protocols.webrtc.AIORTC_AVAILABLE', False):
            with pytest.raises(RuntimeError, match="aiortc library not found"):
                WebRTCAdapter()
    
    def test_initialization_without_zeroconf(self):
        """Test initialization fails without zeroconf."""
        with patch('src.protocols.webrtc.AIORTC_AVAILABLE', True), \
             patch('src.protocols.webrtc.ZEROCONF_AVAILABLE', False):
            with pytest.raises(RuntimeError, match="zeroconf library not found"):
                WebRTCAdapter()
    
    @pytest.mark.asyncio
    async def test_start(self, adapter):
        """Test starting the WebRTC adapter."""
        with patch.object(asyncio, 'start_server', new_callable=AsyncMock) as mock_server, \
             patch.object(adapter, '_start_mdns', new_callable=AsyncMock) as mock_mdns:
            
            mock_server.return_value = Mock()
            
            await adapter.start(port=8080)
            
            assert adapter._port == 8080
            assert adapter._config.signaling_port == 8080
            mock_server.assert_called_once()
            mock_mdns.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_already_started(self, adapter):
        """Test starting adapter when already started."""
        adapter._signaling_server = Mock()
        
        await adapter.start(port=8080)
        
        # Should return early without error
        assert adapter._signaling_server is not None
    
    @pytest.mark.asyncio
    async def test_start_mdns_failure(self, adapter):
        """Test starting adapter when mDNS fails."""
        with patch.object(asyncio, 'start_server', new_callable=AsyncMock) as mock_server, \
             patch.object(adapter, '_start_mdns', new_callable=AsyncMock) as mock_mdns:
            
            mock_server.return_value = Mock()
            mock_mdns.side_effect = Exception("mDNS failed")
            
            # Should not raise, just log warning
            await adapter.start(port=8080)
            
            assert adapter._signaling_server is not None
    
    @pytest.mark.asyncio
    async def test_stop(self, adapter):
        """Test stopping the WebRTC adapter."""
        # Set up adapter state
        mock_server = Mock()
        mock_server.close = Mock()
        mock_server.wait_closed = AsyncMock()
        adapter._signaling_server = mock_server
        
        mock_pc = Mock()
        mock_pc.close = AsyncMock()
        adapter._peer_connections['peer1'] = mock_pc
        adapter._connected = True
        
        with patch.object(adapter, '_stop_mdns', new_callable=AsyncMock) as mock_stop_mdns:
            await adapter.stop()
            
            # Verify cleanup
            mock_pc.close.assert_called_once()
            assert adapter._peer_connections == {}
            mock_server.close.assert_called_once()
            mock_stop_mdns.assert_called_once()
            adapter._on_disconnect.assert_called_once()
            assert adapter._signaling_server is None
    
    def test_get_connection_urls(self, adapter):
        """Test getting connection URLs."""
        adapter._port = 8080
        
        urls = adapter.get_connection_urls(['192.168.1.100', '10.0.0.5'])
        
        assert len(urls) == 2
        assert 'http://192.168.1.100:8080/webrtc' in urls
        assert 'http://10.0.0.5:8080/webrtc' in urls
    
    def test_get_connection_urls_not_started(self, adapter):
        """Test getting connection URLs when not started."""
        urls = adapter.get_connection_urls(['192.168.1.100'])
        assert urls == []
    
    def test_get_connection_instructions(self, adapter):
        """Test getting connection instructions."""
        instructions = adapter.get_connection_instructions()
        
        assert 'WebRTC' in instructions
        assert 'mDNS' in instructions
        assert 'RTMP Virtual Camera' in instructions
        assert 'automatic' in instructions.lower()
    
    def test_is_connected(self, adapter):
        """Test connection status property."""
        assert adapter.is_connected is False
        
        adapter._connected = True
        assert adapter.is_connected is True
    
    def test_get_local_ips(self, adapter):
        """Test getting local IP addresses."""
        with patch('socket.gethostname', return_value='testhost'), \
             patch('socket.getaddrinfo', return_value=[
                 (None, None, None, None, ('192.168.1.100', 0)),
                 (None, None, None, None, ('127.0.0.1', 0)),  # Should be filtered
                 (None, None, None, None, ('10.0.0.5', 0)),
                 (None, None, None, None, ('::1', 0)),  # IPv6, should be filtered
             ]):
            
            ips = adapter._get_local_ips()
            
            assert '192.168.1.100' in ips
            assert '10.0.0.5' in ips
            assert '127.0.0.1' not in ips
            assert '::1' not in ips
    
    @pytest.mark.asyncio
    async def test_start_mdns(self, adapter):
        """Test starting mDNS advertisement."""
        with patch.object(adapter, '_get_local_ips', return_value=['192.168.1.100']), \
             patch('src.protocols.webrtc.Zeroconf') as mock_zeroconf_class, \
             patch('src.protocols.webrtc.ServiceInfo') as mock_service_info_class, \
             patch('socket.inet_aton', return_value=b'\xc0\xa8\x01\x64'):
            
            mock_zeroconf = Mock()
            mock_zeroconf_class.return_value = mock_zeroconf
            mock_service_info = Mock()
            mock_service_info_class.return_value = mock_service_info
            
            adapter._config.signaling_port = 8080
            
            await adapter._start_mdns()
            
            # Verify service info created correctly
            mock_service_info_class.assert_called_once()
            call_args = mock_service_info_class.call_args
            assert call_args[0][0] == "_rtmp-vcam._tcp.local."
            assert call_args[1]['port'] == 8080
            
            # Verify service registered
            assert adapter._zeroconf is not None
            assert adapter._service_info is not None
    
    @pytest.mark.asyncio
    async def test_start_mdns_no_ips(self, adapter):
        """Test starting mDNS with no local IPs."""
        with patch.object(adapter, '_get_local_ips', return_value=[]):
            with pytest.raises(RuntimeError, match="No local IP addresses found"):
                await adapter._start_mdns()
    
    @pytest.mark.asyncio
    async def test_stop_mdns(self, adapter):
        """Test stopping mDNS advertisement."""
        mock_zeroconf = Mock()
        mock_service_info = Mock()
        adapter._zeroconf = mock_zeroconf
        adapter._service_info = mock_service_info
        
        await adapter._stop_mdns()
        
        # Verify cleanup
        assert adapter._zeroconf is None
        assert adapter._service_info is None
    
    @pytest.mark.asyncio
    async def test_handle_offer(self, adapter):
        """Test handling WebRTC offer."""
        # Mock RTCPeerConnection
        mock_pc = Mock()
        mock_pc.connectionState = "new"
        mock_pc.setRemoteDescription = AsyncMock()
        mock_pc.createAnswer = AsyncMock(return_value=Mock(type='answer', sdp='test_sdp'))
        mock_pc.setLocalDescription = AsyncMock()
        mock_pc.localDescription = Mock(type='answer', sdp='test_answer_sdp')
        mock_pc.on = lambda event: lambda func: func  # Simple event handler mock
        
        with patch('src.protocols.webrtc.RTCPeerConnection', return_value=mock_pc), \
             patch('src.protocols.webrtc.RTCSessionDescription') as mock_sdp:
            
            message = {
                'type': 'offer',
                'sdp': 'test_offer_sdp'
            }
            
            response = await adapter._handle_offer('peer1', message)
            
            assert response['type'] == 'answer'
            assert response['sdp'] == 'test_answer_sdp'
            assert 'peer1' in adapter._peer_connections
    
    @pytest.mark.asyncio
    async def test_handle_offer_error(self, adapter):
        """Test handling WebRTC offer with error."""
        with patch('src.protocols.webrtc.RTCPeerConnection', side_effect=Exception("Connection failed")):
            message = {
                'type': 'offer',
                'sdp': 'test_offer_sdp'
            }
            
            response = await adapter._handle_offer('peer1', message)
            
            assert response['type'] == 'error'
            assert 'Connection failed' in response['message']


class TestWebRTCAdapterIntegration:
    """Integration tests for WebRTC adapter."""
    
    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test complete adapter lifecycle."""
        with patch('src.protocols.webrtc.AIORTC_AVAILABLE', True), \
             patch('src.protocols.webrtc.ZEROCONF_AVAILABLE', True), \
             patch.object(asyncio, 'start_server', new_callable=AsyncMock) as mock_server, \
             patch('src.protocols.webrtc.Zeroconf'), \
             patch('src.protocols.webrtc.ServiceInfo'), \
             patch('socket.inet_aton', return_value=b'\xc0\xa8\x01\x64'):
            
            mock_server.return_value = Mock(
                close=Mock(),
                wait_closed=AsyncMock()
            )
            
            on_connect = Mock()
            on_disconnect = Mock()
            
            adapter = WebRTCAdapter(
                on_connect=on_connect,
                on_disconnect=on_disconnect
            )
            
            # Mock _get_local_ips to return test IP
            with patch.object(adapter, '_get_local_ips', return_value=['192.168.1.100']):
                # Start adapter
                await adapter.start(port=8080)
                assert adapter._port == 8080
                assert not adapter.is_connected
                
                # Get URLs
                urls = adapter.get_connection_urls(['192.168.1.100'])
                assert len(urls) == 1
                assert 'http://192.168.1.100:8080/webrtc' in urls
                
                # Stop adapter
                await adapter.stop()
                assert adapter._signaling_server is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
