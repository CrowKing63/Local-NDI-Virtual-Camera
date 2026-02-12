"""
Tests for system tray application controller.
"""
import pytest
from PIL import Image

from src.tray import TrayApp, _create_state_icon
from src.connection_manager import ConnectionState, ConnectionHealth


class TestIconCreation:
    """Test icon creation for different states and health levels."""
    
    def test_disconnected_icon(self):
        """Test icon creation for disconnected state."""
        icon = _create_state_icon(state=ConnectionState.DISCONNECTED)
        assert isinstance(icon, Image.Image)
        assert icon.size == (64, 64)
    
    def test_connecting_icon(self):
        """Test icon creation for connecting state."""
        icon = _create_state_icon(state=ConnectionState.CONNECTING)
        assert isinstance(icon, Image.Image)
        assert icon.size == (64, 64)
    
    def test_connected_excellent_icon(self):
        """Test icon creation for connected state with excellent health."""
        icon = _create_state_icon(
            state=ConnectionState.CONNECTED,
            health=ConnectionHealth.EXCELLENT
        )
        assert isinstance(icon, Image.Image)
        assert icon.size == (64, 64)
    
    def test_connected_good_icon(self):
        """Test icon creation for connected state with good health."""
        icon = _create_state_icon(
            state=ConnectionState.CONNECTED,
            health=ConnectionHealth.GOOD
        )
        assert isinstance(icon, Image.Image)
        assert icon.size == (64, 64)
    
    def test_connected_poor_icon(self):
        """Test icon creation for connected state with poor health."""
        icon = _create_state_icon(
            state=ConnectionState.CONNECTED,
            health=ConnectionHealth.POOR
        )
        assert isinstance(icon, Image.Image)
        assert icon.size == (64, 64)
    
    def test_connected_critical_icon(self):
        """Test icon creation for connected state with critical health."""
        icon = _create_state_icon(
            state=ConnectionState.CONNECTED,
            health=ConnectionHealth.CRITICAL
        )
        assert isinstance(icon, Image.Image)
        assert icon.size == (64, 64)
    
    def test_reconnecting_icon(self):
        """Test icon creation for reconnecting state."""
        icon = _create_state_icon(state=ConnectionState.RECONNECTING)
        assert isinstance(icon, Image.Image)
        assert icon.size == (64, 64)
    
    def test_custom_size_icon(self):
        """Test icon creation with custom size."""
        icon = _create_state_icon(size=128, state=ConnectionState.CONNECTED)
        assert isinstance(icon, Image.Image)
        assert icon.size == (128, 128)


class TestTrayApp:
    """Test TrayApp state management."""
    
    def test_initial_state(self):
        """Test TrayApp initializes with disconnected state."""
        app = TrayApp()
        assert app._connection_state == ConnectionState.DISCONNECTED
        assert app._connection_health == ConnectionHealth.CRITICAL
    
    def test_update_connection_state(self):
        """Test updating connection state."""
        app = TrayApp()
        
        # Update to connecting
        app.update_connection_state(ConnectionState.CONNECTING)
        assert app._connection_state == ConnectionState.CONNECTING
        
        # Update to connected
        app.update_connection_state(ConnectionState.CONNECTED)
        assert app._connection_state == ConnectionState.CONNECTED
        
        # Update to reconnecting
        app.update_connection_state(ConnectionState.RECONNECTING)
        assert app._connection_state == ConnectionState.RECONNECTING
        
        # Update to disconnected
        app.update_connection_state(ConnectionState.DISCONNECTED)
        assert app._connection_state == ConnectionState.DISCONNECTED
    
    def test_update_connection_health(self):
        """Test updating connection health."""
        app = TrayApp()
        
        # Update to excellent
        app.update_connection_health(ConnectionHealth.EXCELLENT)
        assert app._connection_health == ConnectionHealth.EXCELLENT
        
        # Update to good
        app.update_connection_health(ConnectionHealth.GOOD)
        assert app._connection_health == ConnectionHealth.GOOD
        
        # Update to poor
        app.update_connection_health(ConnectionHealth.POOR)
        assert app._connection_health == ConnectionHealth.POOR
        
        # Update to critical
        app.update_connection_health(ConnectionHealth.CRITICAL)
        assert app._connection_health == ConnectionHealth.CRITICAL
    
    def test_state_and_health_interaction(self):
        """Test that state and health can be updated independently."""
        app = TrayApp()
        
        # Set connected state with excellent health
        app.update_connection_state(ConnectionState.CONNECTED)
        app.update_connection_health(ConnectionHealth.EXCELLENT)
        assert app._connection_state == ConnectionState.CONNECTED
        assert app._connection_health == ConnectionHealth.EXCELLENT
        
        # Change health while maintaining state
        app.update_connection_health(ConnectionHealth.POOR)
        assert app._connection_state == ConnectionState.CONNECTED
        assert app._connection_health == ConnectionHealth.POOR
        
        # Change state while maintaining health
        app.update_connection_state(ConnectionState.RECONNECTING)
        assert app._connection_state == ConnectionState.RECONNECTING
        assert app._connection_health == ConnectionHealth.POOR
