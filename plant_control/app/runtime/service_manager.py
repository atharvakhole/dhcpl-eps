import asyncio
from typing import Any, Optional
from plant_control.app.core.tag_service import TagService
from plant_control.app.schemas.tag_service import TagReadResult, TagWriteResult

class ServiceManager:
    _instance: Optional['ServiceManager'] = None
    _tag_service: Optional[TagService] = None  # FIXED: removed asterisks, added underscore
    _loop: Optional[asyncio.AbstractEventLoop] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def set_services(self, tag_service: TagService, loop: asyncio.AbstractEventLoop):
        """Called by ServiceRuntime after initialization"""
        self._tag_service = tag_service
        self._loop = loop
    
    def clear_services(self):
        """Called by ServiceRuntime during shutdown"""
        self._tag_service = None
        self._loop = None
    
    def read_tag(self, plc_id: str, tag_name: str, timeout: float = 10.0) -> TagReadResult:
        """Synchronous wrapper for tag reading"""
        if not self._tag_service or not self._loop:
            raise RuntimeError("Services not initialized. Make sure ServiceRuntime is started.")
        
        try:
            if self._loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self._tag_service.read_tag(plc_id, tag_name), 
                    self._loop
                )
                return future.result(timeout=timeout)
            else:
                return asyncio.run(
                    asyncio.wait_for(
                        self._tag_service.read_tag(plc_id, tag_name), 
                        timeout=timeout
                    )
                )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Tag read operation timed out after {timeout} seconds")
        except Exception as e:
            raise RuntimeError(f"Tag read failed: {str(e)}") from e
    
    def write_tag(self, plc_id: str, tag_name: str, data: Any, timeout: float = 10.0) -> TagWriteResult:
        """Synchronous wrapper for tag writing"""
        if not self._tag_service or not self._loop:
            raise RuntimeError("Services not initialized. Make sure ServiceRuntime is started.")
        
        try:
            if self._loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self._tag_service.write_tag(plc_id, tag_name, data), 
                    self._loop
                )
                return future.result(timeout=timeout)
            else:
                return asyncio.run(
                    asyncio.wait_for(
                        self._tag_service.write_tag(plc_id, tag_name, data), 
                        timeout=timeout
                    )
                )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Tag write operation timed out after {timeout} seconds")
        except Exception as e:
            raise RuntimeError(f"Tag write failed: {str(e)}") from e

# Global instance
service_manager = ServiceManager()
