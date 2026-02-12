"""
Unit tests for protocol adapter base interface.

Tests the abstract ProtocolAdapter interface definition and ensures
it can be properly subclassed.
"""
import pytest
from typing import List
from src.protocols.base import ProtocolAdapter


class MockProtocolAdapter(ProtocolAdapter):
    """Mock implementation of ProtocolAdapter for testing."""
    
    def __init__(self):
        self._connected = False
        self._port = None
        self._path = None
    
    async def start(self, port: int, path: str = "") -> None:
        """Start the mock adapter."""
        self._port = port
        self._path = path
        self._connected = True
    
    async def stop(self) -> None:
        """Stop the mock adapter."""
        self._connected = False
        self._port = None
        self._path = None
    
    def get_connection_urls(self, local_ips: List[str]) -> List[str]:
        """Return mock connection URLs."""
        if self._port is None:
            return []
        return [f"mock://{ip}:{self._port}{self._path}" for ip in local_ips]
    
    def get_connection_instructions(self) -> str:
        """Return mock instructions."""
        return "Connect using mock protocol"
    
    @property
    def is_connected(self) -> bool:
        """Return connection status."""
        return self._connected


def test_protocol_adapter_is_abstract():
    """Test that ProtocolAdapter cannot be instantiated directly."""
    with pytest.raises(TypeError):
        ProtocolAdapter()


@pytest.mark.asyncio
async def test_mock_adapter_implements_interface():
    """Test that MockProtocolAdapter properly implements the interface."""
    adapter = MockProtocolAdapter()
    
    # Initially not connected
    assert not adapter.is_connected
    
    # Start the adapter
    await adapter.start(port=2935, path="/live/stream")
    assert adapter.is_connected
    
    # Get connection URLs
    urls = adapter.get_connection_urls(["192.168.1.100", "10.0.0.5"])
    assert len(urls) == 2
    assert "mock://192.168.1.100:2935/live/stream" in urls
    assert "mock://10.0.0.5:2935/live/stream" in urls
    
    # Get instructions
    instructions = adapter.get_connection_instructions()
    assert isinstance(instructions, str)
    assert len(instructions) > 0
    
    # Stop the adapter
    await adapter.stop()
    assert not adapter.is_connected


@pytest.mark.asyncio
async def test_adapter_start_with_default_path():
    """Test that adapter can start with default empty path."""
    adapter = MockProtocolAdapter()
    
    await adapter.start(port=9000)
    assert adapter.is_connected
    
    urls = adapter.get_connection_urls(["192.168.1.100"])
    assert urls == ["mock://192.168.1.100:9000"]


def test_adapter_get_urls_before_start():
    """Test that get_connection_urls returns empty list before start."""
    adapter = MockProtocolAdapter()
    urls = adapter.get_connection_urls(["192.168.1.100"])
    assert urls == []


@pytest.mark.asyncio
async def test_adapter_multiple_start_stop_cycles():
    """Test that adapter can be started and stopped multiple times."""
    adapter = MockProtocolAdapter()
    
    # First cycle
    await adapter.start(port=2935, path="/stream1")
    assert adapter.is_connected
    await adapter.stop()
    assert not adapter.is_connected
    
    # Second cycle with different parameters
    await adapter.start(port=9000, path="/stream2")
    assert adapter.is_connected
    urls = adapter.get_connection_urls(["192.168.1.100"])
    assert "mock://192.168.1.100:9000/stream2" in urls
    await adapter.stop()
    assert not adapter.is_connected
