"""
Protocol Factory for creating protocol adapters.

Provides a factory method to instantiate the appropriate protocol adapter
(RTMP, SRT, or WebRTC) based on the ProtocolType enum. This decouples the
caller from needing to know the specific adapter classes.
"""
import logging
from typing import Callable, Optional

from .base import ProtocolAdapter
from .rtmp import RTMPAdapter
from .srt import SRTAdapter
from .webrtc import WebRTCAdapter
from ..config_manager import ProtocolType

log = logging.getLogger(__name__)


class ProtocolFactory:
    """
    Factory class for creating protocol adapters.
    
    Provides a clean interface for instantiating the correct protocol adapter
    based on the ProtocolType enum without requiring the caller to know about
    specific adapter classes.
    """
    
    @staticmethod
    def create_adapter(
        protocol_type: ProtocolType,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        width: int = 1280,
        height: int = 720,
    ) -> ProtocolAdapter:
        """
        Factory method to create appropriate protocol adapter.
        
        Parameters
        ----------
        protocol_type : ProtocolType
            The type of protocol adapter to create (RTMP, SRT, or WEBRTC)
        on_connect : callable, optional
            Callback invoked when a client connects
        on_disconnect : callable, optional
            Callback invoked when a client disconnects
        width : int, optional
            Frame width for video decoding (default: 1280)
        height : int, optional
            Frame height for video decoding (default: 720)
        
        Returns
        -------
        ProtocolAdapter
            An instance of the appropriate protocol adapter
        
        Raises
        ------
        ValueError
            If protocol_type is not a valid ProtocolType enum value
        
        Examples
        --------
        >>> factory = ProtocolFactory()
        >>> adapter = factory.create_adapter(
        ...     ProtocolType.RTMP,
        ...     on_connect=lambda: print("Connected"),
        ...     on_disconnect=lambda: print("Disconnected")
        ... )
        >>> # adapter is now an RTMPAdapter instance
        """
        log.info(f"Creating protocol adapter for {protocol_type.value}")
        
        if protocol_type == ProtocolType.RTMP:
            return RTMPAdapter(
                on_connect=on_connect,
                on_disconnect=on_disconnect,
                width=width,
                height=height,
            )
        
        elif protocol_type == ProtocolType.SRT:
            return SRTAdapter(
                on_connect=on_connect,
                on_disconnect=on_disconnect,
                width=width,
                height=height,
            )
        
        elif protocol_type == ProtocolType.WEBRTC:
            return WebRTCAdapter(
                on_connect=on_connect,
                on_disconnect=on_disconnect,
                width=width,
                height=height,
            )
        
        else:
            raise ValueError(
                f"Unknown protocol type: {protocol_type}. "
                f"Valid types are: {', '.join([p.value for p in ProtocolType])}"
            )
