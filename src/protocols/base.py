"""
Base protocol adapter interface for streaming protocols.

Defines the abstract interface that all protocol adapters (RTMP, SRT, WebRTC)
must implement to provide a unified streaming interface.
"""
from abc import ABC, abstractmethod
from typing import List


class ProtocolAdapter(ABC):
    """
    Abstract base class for streaming protocol adapters.
    
    All protocol implementations (RTMP, SRT, WebRTC) must inherit from this
    class and implement the required interface methods.
    """
    
    @abstractmethod
    async def start(self, port: int, path: str = "") -> None:
        """
        Start listening for incoming streams.
        
        Parameters
        ----------
        port : int
            Port number to listen on
        path : str, optional
            Stream path (used by RTMP, may be empty for other protocols)
        
        Raises
        ------
        RuntimeError
            If the protocol adapter fails to start
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """
        Stop listening and clean up resources.
        
        Should gracefully shut down any active connections and release
        all resources (ports, processes, etc.).
        """
        pass
    
    @abstractmethod
    def get_connection_urls(self, local_ips: List[str]) -> List[str]:
        """
        Return connection URLs for iOS sender.
        
        Parameters
        ----------
        local_ips : List[str]
            List of local IP addresses to include in URLs
        
        Returns
        -------
        List[str]
            List of connection URLs formatted for the specific protocol
            (e.g., "rtmp://192.168.1.100:2935/live/stream")
        """
        pass
    
    @abstractmethod
    def get_connection_instructions(self) -> str:
        """
        Return human-readable connection instructions.
        
        Returns
        -------
        str
            Instructions for connecting to this protocol adapter from
            an iOS device or streaming application
        """
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if a sender is currently connected.
        
        Returns
        -------
        bool
            True if a streaming client is currently connected and sending data,
            False otherwise
        """
        pass
