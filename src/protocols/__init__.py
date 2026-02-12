"""
Protocol abstraction layer for RTMP Virtual Camera.

Provides unified interface for different streaming protocols (RTMP, SRT, WebRTC).
"""
from src.protocols.base import ProtocolAdapter
from src.protocols.factory import ProtocolFactory

__all__ = ['ProtocolAdapter', 'ProtocolFactory']
