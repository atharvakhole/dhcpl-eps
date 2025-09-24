from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, List, Tuple
from contextlib import asynccontextmanager
import uvicorn
import logging
import time
import asyncio

# Import your modules
from app.core.tag_service import TagService
from app.config import config_manager
from app.core.connection_manager import connection_manager

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    logger.info("Initializing PLC connections...")
    plc_configs = config_manager.load_plc_configs()
    register_maps = config_manager.load_register_maps()
    await connection_manager.initialize(plc_configs, config_manager)
    
    # Initialize the tag service
    global plc_handler
    plc_handler = TagService()
    
    logger.info("PLC connections initialized successfully")
    
    yield
    
    # Shutdown (if needed)
    logger.info("Shutting down PLC connections...")
    # await connection_manager.shutdown()  # if you have cleanup logic

app = FastAPI(title="PLC Tag API", version="1.0.0", lifespan=lifespan)

# Pydantic model for write requests
class WriteTagRequest(BaseModel):
    data: Any

# Initialize PLC handler instance after startup
plc_handler = None  # Will be initialized during lifespan startup

@app.get("/plc/{plc_id}/tag/{tag_name}")
async def read_tag_endpoint(plc_id: str, tag_name: str) -> Tuple[Any, List[Any]]:
    """
    Read data from a PLC tag.
    
    Args:
        plc_id: The PLC identifier
        tag_name: The name of the tag to read
        
    Returns:
        List containing the tag data
    """
    start_time = time.time()
    try:
        result, registers = await plc_handler.read_tag(plc_id, tag_name)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Tag read API completed", extra={
            "operation": "read_tag_api",
            "plc_id": plc_id,
            "tag_name": tag_name,
            "duration_ms": duration_ms
        })
        return result, registers
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Tag read API failed: {e}", extra={
            "operation": "read_tag_api",
            "plc_id": plc_id,
            "tag_name": tag_name,
            "error": str(e),
            "duration_ms": duration_ms
        })
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read tag '{tag_name}' from PLC '{plc_id}': {str(e)}"
        )

@app.post("/plc/{plc_id}/tag/{tag_name}")
async def write_tag_endpoint(plc_id: str, tag_name: str, request: WriteTagRequest):
    """
    Write data to a PLC tag.
    
    Args:
        plc_id: The PLC identifier
        tag_name: The name of the tag to write
        request: Request body containing the data to write
        
    Returns:
        Success message with operation details
    """
    start_time = time.time()
    try:
        result = await plc_handler.write_tag(plc_id, tag_name, request.data)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Tag write API completed", extra={
            "operation": "write_tag_api",
            "plc_id": plc_id,
            "tag_name": tag_name,
            "data": request.data,
            "duration_ms": duration_ms
        })
        return {
            "message": "Tag write successful",
            "plc_id": plc_id,
            "tag_name": tag_name,
            "data": request.data,
            "result": result
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Tag write API failed: {e}", extra={
            "operation": "write_tag_api",
            "plc_id": plc_id,
            "tag_name": tag_name,
            "data": request.data,
            "error": str(e),
            "duration_ms": duration_ms
        })
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write tag '{tag_name}' to PLC '{plc_id}': {str(e)}"
        )

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "PLC Tag API is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
