import asyncio
import threading
import time
from typing import Any, Optional
from plant_control.app.core.tag_service import TagService
from plant_control.app.schemas.tag_service import TagReadResult, TagWriteResult

class ServiceManager:
    _instance: Optional['ServiceManager'] = None
    _tag_service: Optional[TagService] = None
    _loop: Optional[asyncio.AbstractEventLoop] = None
    _service_thread: Optional[threading.Thread] = None
    _runtime: Optional['ServiceRuntime'] = None
    _ready_event: Optional[threading.Event] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def start_background_service(self, runtime, max_wait_time: float = 30.0):
        """Start the service runtime in a background thread"""
        if self._service_thread and self._service_thread.is_alive():
            raise RuntimeError("Background service is already running")
        
        self._runtime = runtime
        self._ready_event = threading.Event()
        
        def run_service():
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            
            try:
                # Start the runtime
                loop.run_until_complete(runtime.start())
                
                # Set services for sync access
                self._tag_service = runtime.tag_service
                
                # Signal that we're ready
                self._ready_event.set()
                
                print("Background service started and ready!")
                
                # Keep the loop running
                loop.run_forever()
                
            except Exception as e:
                print(f"Error in background service: {e}")
                import traceback
                traceback.print_exc()
            finally:
                print("Background service shutting down...")
                if hasattr(runtime, 'stop'):
                    loop.run_until_complete(runtime.stop())
                loop.close()
        
        # Start the background thread
        self._service_thread = threading.Thread(target=run_service, daemon=True)
        self._service_thread.start()
        
        # Wait for service to be ready
        if not self._ready_event.wait(timeout=max_wait_time):
            raise TimeoutError(f"Background service failed to start within {max_wait_time} seconds")
        
        print("ServiceManager: Background service is ready for use!")
    
    def stop_background_service(self):
        """Stop the background service"""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        if self._service_thread:
            self._service_thread.join(timeout=10.0)
        
        self._tag_service = None
        self._loop = None
        self._service_thread = None
        self._runtime = None
        self._ready_event = None
        print("Background service stopped.")
    
    def set_services(self, tag_service: TagService, loop: asyncio.AbstractEventLoop):
        """Called by ServiceRuntime after initialization (not used in background mode)"""
        self._tag_service = tag_service
        self._loop = loop
    
    def clear_services(self):
        """Called by ServiceRuntime during shutdown (not used in background mode)"""
        self._tag_service = None
        self._loop = None
    
    def read_tag(self, plc_id: str, tag_name: str, timeout: float = 10.0) -> TagReadResult:
        """Synchronous wrapper for tag reading"""
        if not self._tag_service or not self._loop:
            raise RuntimeError("Background service not started. Call start_background_service() first.")
        
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._tag_service.read_tag(plc_id, tag_name), 
                self._loop
            )
            return future.result(timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Tag read operation timed out after {timeout} seconds")
        except Exception as e:
            raise RuntimeError(f"Tag read failed: {str(e)}") from e
    
    def write_tag(self, plc_id: str, tag_name: str, data: Any, timeout: float = 10.0) -> TagWriteResult:
        """Synchronous wrapper for tag writing"""
        if not self._tag_service or not self._loop:
            raise RuntimeError("Background service not started. Call start_background_service() first.")
        
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._tag_service.write_tag(plc_id, tag_name, data), 
                self._loop
            )
            return future.result(timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Tag write operation timed out after {timeout} seconds")
        except Exception as e:
            raise RuntimeError(f"Tag write failed: {str(e)}") from e

# Global instance
service_manager = ServiceManager()
