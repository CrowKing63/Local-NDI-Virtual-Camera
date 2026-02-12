"""
Unit tests for ProtocolFactory.

Tests the factory method for creating protocol adapters based on ProtocolType.
"""
import pytest
from src.protocols.factory import ProtocolFactory
from src.protocols.rtmp import RTMPAdapter
from src.protocols.srt import SRTAdapter
from src.protocols.webrtc import WebRTCAdapter
from src.config_manager import ProtocolType


def test_create_rtmp_adapter():
    """Test creating an RTMP adapter."""
    adapter = ProtocolFactory.create_adapter(ProtocolType.RTMP)
    
    assert isinstance(adapter, RTMPAdapter)
    assert adapter is not None


def test_create_srt_adapter():
    """Test creating an SRT adapter."""
    adapter = ProtocolFactory.create_adapter(ProtocolType.SRT)
    
    assert isinstance(adapter, SRTAdapter)
    assert adapter is not None


def test_create_webrtc_adapter():
    """Test creating a WebRTC adapter."""
    # WebRTC adapter may raise RuntimeError if dependencies are missing
    try:
        adapter = ProtocolFactory.create_adapter(ProtocolType.WEBRTC)
        assert isinstance(adapter, WebRTCAdapter)
        assert adapter is not None
    except RuntimeError as e:
        # Expected if aiortc or zeroconf not installed
        assert "aiortc" in str(e) or "zeroconf" in str(e)
        pytest.skip(f"WebRTC dependencies not available: {e}")


def test_create_adapter_with_callbacks():
    """Test creating an adapter with connect/disconnect callbacks."""
    connect_called = []
    disconnect_called = []
    
    def on_connect():
        connect_called.append(True)
    
    def on_disconnect():
        disconnect_called.append(True)
    
    adapter = ProtocolFactory.create_adapter(
        ProtocolType.RTMP,
        on_connect=on_connect,
        on_disconnect=on_disconnect
    )
    
    assert isinstance(adapter, RTMPAdapter)
    assert adapter._on_connect is on_connect
    assert adapter._on_disconnect is on_disconnect


def test_create_adapter_with_dimensions():
    """Test creating an adapter with custom frame dimensions."""
    adapter = ProtocolFactory.create_adapter(
        ProtocolType.RTMP,
        width=1920,
        height=1080
    )
    
    assert isinstance(adapter, RTMPAdapter)
    assert adapter._width == 1920
    assert adapter._height == 1080


def test_create_adapter_invalid_protocol():
    """Test that invalid protocol type raises ValueError."""
    # Create an invalid enum-like value
    class FakeProtocol:
        value = "invalid"
    
    with pytest.raises(ValueError) as exc_info:
        ProtocolFactory.create_adapter(FakeProtocol())  # type: ignore
    
    assert "Unknown protocol type" in str(exc_info.value)


def test_create_all_protocol_types():
    """Test creating adapters for all valid protocol types."""
    protocols = [ProtocolType.RTMP, ProtocolType.SRT, ProtocolType.WEBRTC]
    expected_types = [RTMPAdapter, SRTAdapter, WebRTCAdapter]
    
    for protocol, expected_type in zip(protocols, expected_types):
        try:
            adapter = ProtocolFactory.create_adapter(protocol)
            assert isinstance(adapter, expected_type)
        except RuntimeError as e:
            # WebRTC may fail if dependencies missing
            if protocol == ProtocolType.WEBRTC:
                pytest.skip(f"WebRTC dependencies not available: {e}")
            else:
                raise


def test_factory_is_stateless():
    """Test that factory can create multiple adapters independently."""
    adapter1 = ProtocolFactory.create_adapter(ProtocolType.RTMP)
    adapter2 = ProtocolFactory.create_adapter(ProtocolType.RTMP)
    
    # Should create different instances
    assert adapter1 is not adapter2
    assert isinstance(adapter1, RTMPAdapter)
    assert isinstance(adapter2, RTMPAdapter)


def test_adapter_interface_compliance():
    """Test that created adapters implement the ProtocolAdapter interface."""
    from src.protocols.base import ProtocolAdapter
    
    adapter = ProtocolFactory.create_adapter(ProtocolType.RTMP)
    
    # Check that adapter implements required interface methods
    assert isinstance(adapter, ProtocolAdapter)
    assert hasattr(adapter, 'start')
    assert hasattr(adapter, 'stop')
    assert hasattr(adapter, 'get_connection_urls')
    assert hasattr(adapter, 'get_connection_instructions')
    assert hasattr(adapter, 'is_connected')
