import pytest
import asyncio
from src.connection_manager import ConnectionManager, ConnectionState, ConnectionHealth

@pytest.fixture
def conn_mgr():
    return ConnectionManager(
        on_state_change=lambda s: None,
        on_health_change=lambda h: None
    )

def test_initial_state(conn_mgr):
    assert conn_mgr.current_state == ConnectionState.DISCONNECTED
    # Note: Initial health is CRITICAL in this version until first frame
    assert conn_mgr.current_health == ConnectionHealth.CRITICAL

def test_state_transitions(conn_mgr):
    last_state = None
    def on_change(s):
        nonlocal last_state
        last_state = s
    
    conn_mgr._on_state_change = on_change
    
    conn_mgr.report_connection_established()
    assert conn_mgr.current_state == ConnectionState.CONNECTED
    assert last_state == ConnectionState.CONNECTED
    
    conn_mgr.report_connection_lost()
    assert conn_mgr.current_state == ConnectionState.RECONNECTING
    assert last_state == ConnectionState.RECONNECTING

def test_health_monitoring_basics(conn_mgr):
    conn_mgr.report_connection_established()
    assert conn_mgr.current_state == ConnectionState.CONNECTED
    
    assert conn_mgr._last_frame_time is None
    conn_mgr.report_frame_received()
    assert conn_mgr._last_frame_time is not None
