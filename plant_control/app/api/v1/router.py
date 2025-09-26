from fastapi import APIRouter, HTTPException, status
import time

from plant_control.app.utilities.telemetry import logger

from plant_control.app.schemas.common import RootResponse
from plant_control.app.api.v1.procedures import router as procedures_router
from plant_control.app.api.v1.registers import router as registers_router
from plant_control.app.monitoring.health_check import router as health_router

# Create main API router
api_router = APIRouter(prefix="/api/v1")

# Include sub-routers
api_router.include_router(procedures_router)
api_router.include_router(registers_router)
api_router.include_router(health_router)


@api_router.get("", response_model=RootResponse)
async def v1_root() -> RootResponse:
    """Root endpoint with API information"""
    return RootResponse(message="Plant Control API v1 is running", version="1.0.0")


# Add root endpoint at application level (not under /api/v1)
root_router = APIRouter()

@root_router.get("/", response_model=RootResponse)
async def root() -> RootResponse:
    """Root endpoint with API information"""
    return RootResponse(message="Plant Control API is running", version="1.0.0")


@root_router.get("/status")
async def status_endpoint():
    """
    Detailed status endpoint for monitoring and debugging
    """
    try:
        from plant_control.app.main import plc_handler
        
        status_info = {
            "service_status": "running" if plc_handler else "initializing",
            "timestamp": time.time(),
            "version": "1.0.0",
            "endpoints": {
                "single_read": "/plc/{plc_id}/tag/{tag_name}",
                "single_write": "/plc/{plc_id}/tag/{tag_name}",
                "bulk_read": "/plc/{plc_id}/tags/read",
                "bulk_write": "/plc/{plc_id}/tags/write"
            }
        }
        
        # Could add more detailed status information here
        if plc_handler:
            # Add PLC connection status, configuration info, etc.
            status_info["plc_handler"] = "initialized"
        
        return status_info
        
    except Exception as e:
        logger.error(f"Status endpoint failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve status"
        ) from e


# Export combined router
combined_router = APIRouter()
combined_router.include_router(root_router)
combined_router.include_router(api_router)
