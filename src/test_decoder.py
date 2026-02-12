"""
Unit tests for FrameDecoder with protocol abstraction.

Tests the updated FrameDecoder that works with ProtocolAdapter instead
of directly managing FFmpeg processes.
"""
import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
import subprocess
import io

from src.decoder import FrameDecoder


class TestFrameDecoderWithProtocolAdapter:
    """Test FrameDecoder integration with protocol adapters."""
    
    def test_decoder_accepts_protocol_adapter(self):
        """FrameDecoder should accept a protocol adapter with get_stdout()."""
        # Create mock protocol adapter
        mock_adapter = Mock()
        mock_proc = Mock(spec=subprocess.Popen)
        mock_proc.stdout = io.BytesIO(b'\x00' * (1280 * 720 * 3))  # One frame
        mock_proc.stderr = io.BytesIO(b'')
        mock_adapter.get_stdout.return_value = mock_proc
        
        # Create decoder
        decoder = FrameDecoder(width=1280, height=720)
        
        # Should start without error
        decoder.start(mock_adapter)
        assert decoder._running
        
        # Clean up
        decoder.stop()
        assert not decoder._running
    
    def test_decoder_rejects_adapter_without_get_stdout(self):
        """FrameDecoder should reject adapters without get_stdout() method."""
        # Create mock adapter without get_stdout
        mock_adapter = Mock(spec=[])
        
        decoder = FrameDecoder()
        
        with pytest.raises(RuntimeError, match="does not provide get_stdout"):
            decoder.start(mock_adapter)
    
    def test_decoder_rejects_adapter_with_no_stdout(self):
        """FrameDecoder should reject adapters that return None from get_stdout()."""
        mock_adapter = Mock()
        mock_adapter.get_stdout.return_value = None
        
        decoder = FrameDecoder()
        
        with pytest.raises(RuntimeError, match="not started or does not provide stdout"):
            decoder.start(mock_adapter)
    
    def test_decoder_tracks_frame_count(self):
        """FrameDecoder should track the number of frames decoded."""
        decoder = FrameDecoder(width=10, height=10)
        
        # Initially zero
        assert decoder.frame_count == 0
        assert decoder.error_count == 0
    
    def test_decoder_tracks_error_count(self):
        """FrameDecoder should track decode errors."""
        decoder = FrameDecoder(width=10, height=10)
        
        # Initially zero
        assert decoder.error_count == 0
    
    def test_decoder_calls_on_frame_callback(self):
        """FrameDecoder should invoke on_frame callback when frame is decoded."""
        frame_callback = Mock()
        decoder = FrameDecoder(width=10, height=10, on_frame=frame_callback)
        
        # Create mock adapter with one frame of data
        mock_adapter = Mock()
        mock_proc = Mock(spec=subprocess.Popen)
        frame_data = np.zeros((10, 10, 3), dtype=np.uint8).tobytes()
        mock_proc.stdout = io.BytesIO(frame_data)
        mock_proc.stderr = io.BytesIO(b'')
        mock_adapter.get_stdout.return_value = mock_proc
        
        decoder.start(mock_adapter)
        
        # Give thread time to read frame
        import time
        time.sleep(0.1)
        
        decoder.stop()
        
        # Callback should have been called
        assert frame_callback.called
    
    def test_decoder_calls_on_error_callback(self):
        """FrameDecoder should invoke on_error callback on decode errors."""
        error_callback = Mock()
        decoder = FrameDecoder(width=10, height=10, on_error=error_callback)
        
        # Create mock adapter with incomplete frame data (will cause error)
        mock_adapter = Mock()
        mock_proc = Mock(spec=subprocess.Popen)
        # Only half the expected bytes
        mock_proc.stdout = io.BytesIO(b'\x00' * 150)  # Expected: 10*10*3=300
        mock_proc.stderr = io.BytesIO(b'')
        mock_adapter.get_stdout.return_value = mock_proc
        
        decoder.start(mock_adapter)
        
        # Give thread time to encounter error
        import time
        time.sleep(0.1)
        
        decoder.stop()
        
        # Error callback should have been called
        assert error_callback.called
        assert decoder.error_count > 0
    
    def test_decoder_latest_frame_property(self):
        """FrameDecoder should provide access to latest decoded frame."""
        decoder = FrameDecoder(width=10, height=10)
        
        # Initially None
        assert decoder.latest_frame is None
    
    def test_decoder_stop_is_idempotent(self):
        """Calling stop() multiple times should be safe."""
        decoder = FrameDecoder()
        
        # Should not raise error
        decoder.stop()
        decoder.stop()
        decoder.stop()


class TestFrameDecoderWithRTMPAdapter:
    """Integration tests with actual RTMP adapter (requires FFmpeg)."""
    
    @pytest.mark.integration
    def test_decoder_works_with_rtmp_adapter(self):
        """FrameDecoder should work with RTMPAdapter."""
        # This is an integration test that would require actual FFmpeg
        # and network setup. Marked as integration test to skip in unit tests.
        pytest.skip("Integration test - requires FFmpeg and network setup")


class TestFrameDecoderGracefulDegradation:
    """Test graceful degradation on poor network conditions."""
    
    def test_decoder_continues_on_short_read(self):
        """FrameDecoder should continue operating after short reads."""
        error_callback = Mock()
        frame_callback = Mock()
        decoder = FrameDecoder(width=10, height=10, 
                              on_error=error_callback,
                              on_frame=frame_callback)
        
        # Create mock adapter with short read followed by valid frame
        mock_adapter = Mock()
        mock_proc = Mock(spec=subprocess.Popen)
        
        # First read: short (error), second read: valid frame, third: empty (end)
        frame_data = np.zeros((10, 10, 3), dtype=np.uint8).tobytes()
        short_data = b'\x00' * 150  # Only half the expected bytes
        
        mock_proc.stdout = io.BytesIO(short_data + frame_data)
        mock_proc.stderr = io.BytesIO(b'')
        mock_adapter.get_stdout.return_value = mock_proc
        
        decoder.start(mock_adapter)
        
        # Give thread time to process
        import time
        time.sleep(0.2)
        
        decoder.stop()
        
        # Should have logged error but continued
        assert error_callback.called
        assert decoder.error_count > 0
        # Should have successfully decoded the valid frame after the error
        assert decoder.frame_count > 0
        assert frame_callback.called
    
    def test_decoder_preserves_last_frame_on_error(self):
        """FrameDecoder should keep last valid frame when errors occur."""
        decoder = FrameDecoder(width=10, height=10)
        
        # Create mock adapter with valid frame followed by short read
        mock_adapter = Mock()
        mock_proc = Mock(spec=subprocess.Popen)
        
        # First: valid frame, second: short read (error)
        frame_data = np.ones((10, 10, 3), dtype=np.uint8).tobytes()
        short_data = b'\x00' * 50
        
        mock_proc.stdout = io.BytesIO(frame_data + short_data)
        mock_proc.stderr = io.BytesIO(b'')
        mock_adapter.get_stdout.return_value = mock_proc
        
        decoder.start(mock_adapter)
        
        # Give thread time to process
        import time
        time.sleep(0.2)
        
        # Should have the valid frame stored
        assert decoder.latest_frame is not None
        assert decoder.frame_count == 1
        
        # Store reference to last frame before stopping
        last_frame = decoder.latest_frame
        assert last_frame is not None
        
        decoder.stop()
        
        # Verify the frame was preserved during the error (before stop)
        # Note: stop() clears the frame, which is expected behavior
    
    def test_decoder_continues_on_exception(self):
        """FrameDecoder should continue operating after exceptions."""
        error_callback = Mock()
        decoder = FrameDecoder(width=10, height=10, on_error=error_callback)
        
        # Create mock adapter that will raise exception then provide data
        mock_adapter = Mock()
        mock_proc = Mock(spec=subprocess.Popen)
        
        # Create a mock stdout that raises exception on first read
        class ExceptionThenDataStream:
            def __init__(self):
                self.call_count = 0
                self.frame_data = np.zeros((10, 10, 3), dtype=np.uint8).tobytes()
            
            def read(self, size):
                self.call_count += 1
                if self.call_count == 1:
                    raise IOError("Simulated network error")
                elif self.call_count == 2:
                    return self.frame_data
                else:
                    return b''  # End of stream
        
        mock_proc.stdout = ExceptionThenDataStream()
        mock_proc.stderr = io.BytesIO(b'')
        mock_adapter.get_stdout.return_value = mock_proc
        
        decoder.start(mock_adapter)
        
        # Give thread time to process
        import time
        time.sleep(0.2)
        
        decoder.stop()
        
        # Should have logged error
        assert error_callback.called
        assert decoder.error_count > 0
        # Should have successfully decoded frame after exception
        assert decoder.frame_count > 0
    
    def test_decoder_handles_stderr_errors_gracefully(self):
        """FrameDecoder should continue monitoring stderr after errors."""
        error_callback = Mock()
        decoder = FrameDecoder(width=10, height=10, on_error=error_callback)
        
        # Create mock adapter with error messages in stderr
        mock_adapter = Mock()
        mock_proc = Mock(spec=subprocess.Popen)
        
        frame_data = np.zeros((10, 10, 3), dtype=np.uint8).tobytes()
        mock_proc.stdout = io.BytesIO(frame_data)
        
        # Stderr with error messages
        stderr_data = b'Error: corrupted frame\nWarning: packet loss\n'
        mock_proc.stderr = io.BytesIO(stderr_data)
        mock_adapter.get_stdout.return_value = mock_proc
        
        decoder.start(mock_adapter)
        
        # Give thread time to process
        import time
        time.sleep(0.2)
        
        decoder.stop()
        
        # Should have detected and logged errors
        assert error_callback.called
        assert decoder.error_count > 0
        # Should still have decoded the frame
        assert decoder.frame_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
