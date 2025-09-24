from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from pydantic import BaseModel, Field
from typing import Any, List, Dict, Optional
from contextlib import asynccontextmanager
import uvicorn
import time

# Import your modules
from app.core.tag_service import (
    TagService, TagServiceError, ConfigurationError, ValidationError, 
    AddressResolutionError, EncodingError, ConnectionError,
    TagReadResult, TagWriteResult, BulkReadResponse, BulkWriteResponse,
    ReadStatus, WriteStatus
)
from app.config import config_manager
from app.core.connection_manager import connection_manager
from app.utilities.telemetry import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    try:
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
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down PLC connections...")
        # await connection_manager.shutdown()  # if you have cleanup logic

app = FastAPI(title="PLC Tag API", version="1.0.0", lifespan=lifespan)

# Pydantic models for requests and responses
class WriteTagRequest(BaseModel):
    data: Any = Field(..., description="Data to write to the tag")

class BulkReadRequest(BaseModel):
    tag_names: List[str] = Field(..., description="List of tag names to read", min_items=1)

class BulkWriteRequest(BaseModel):
    tag_data: Dict[str, Any] = Field(..., description="Dictionary mapping tag names to values")

# Response Models
class TagReadResponse(BaseModel):
    plc_id: str
    tag_name: str
    status: str
    data: Optional[Any] = None
    registers: Optional[List[Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: float

class TagWriteResponse(BaseModel):
    plc_id: str
    tag_name: str
    status: str
    data: Optional[Any] = None
    result: Optional[Any] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: float

class BulkReadResponseModel(BaseModel):
    plc_id: str
    summary: Dict[str, int]  # total_requested, successful, failed
    overall_status: str  # "success", "partial_success", "failed"
    results: List[TagReadResponse]
    timestamp: float

class BulkWriteResponseModel(BaseModel):
    plc_id: str
    summary: Dict[str, int]  # total_requested, successful, failed
    overall_status: str  # "success", "partial_success", "failed"
    results: List[TagWriteResponse]
    timestamp: float

class HealthResponse(BaseModel):
    status: str
    timestamp: float

class RootResponse(BaseModel):
    message: str
    version: str

class ErrorDetail(BaseModel):
    error_type: str
    message: str
    plc_id: Optional[str] = None
    tag_name: Optional[str] = None
    address: Optional[int] = None
    timestamp: float

class ErrorResponse(BaseModel):
    detail: ErrorDetail

# Initialize PLC handler instance after startup
plc_handler = None  # Will be initialized during lifespan startup


# Custom exception handlers
@app.exception_handler(TagServiceError)
async def tag_service_exception_handler(request: Request, exc: TagServiceError):
    """Handle custom TagService exceptions with appropriate HTTP status codes"""
    
    # Map exception types to HTTP status codes
    status_code_map = {
        ConfigurationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        ValidationError: status.HTTP_400_BAD_REQUEST,
        AddressResolutionError: status.HTTP_404_NOT_FOUND,
        EncodingError: status.HTTP_422_UNPROCESSABLE_ENTITY,
        ConnectionError: status.HTTP_503_SERVICE_UNAVAILABLE,
        TagServiceError: status.HTTP_500_INTERNAL_SERVER_ERROR,  # Generic fallback
    }
    
    status_code = status_code_map.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    error_detail = ErrorDetail(
        error_type=type(exc).__name__,
        message=str(exc),
        plc_id=getattr(exc, 'plc_id', None),
        tag_name=getattr(exc, 'tag_name', None),
        address=getattr(exc, 'address', None),
        timestamp=time.time()
    )
    
    logger.error(f"TagService error: {error_detail.error_type} - {error_detail.message}", extra={
        "error_type": error_detail.error_type,
        "plc_id": error_detail.plc_id,
        "tag_name": error_detail.tag_name,
        "address": error_detail.address,
        "status_code": status_code
    })
    
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(detail=error_detail).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions gracefully"""
    error_detail = ErrorDetail(
        error_type="InternalServerError",
        message="An unexpected error occurred",
        timestamp=time.time()
    )
    
    logger.error(f"Unexpected error: {str(exc)}", extra={
        "error": str(exc),
        "request_path": request.url.path,
        "request_method": request.method
    }, exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(detail=error_detail).dict()
    )


# Helper function to convert TagReadResult to API response
def _convert_read_result_to_response(result: TagReadResult, plc_id: str) -> TagReadResponse:
    """Convert internal TagReadResult to API response format"""
    return TagReadResponse(
        plc_id=plc_id,
        tag_name=result.tag_name,
        status=result.status.value,
        data=result.data,
        registers=result.registers,
        error_type=result.error_type,
        error_message=result.error_message,
        timestamp=result.timestamp
    )

# Helper function to convert TagWriteResult to API response
def _convert_write_result_to_response(result: TagWriteResult, plc_id: str) -> TagWriteResponse:
    """Convert internal TagWriteResult to API response format"""
    return TagWriteResponse(
        plc_id=plc_id,
        tag_name=result.tag_name,
        status=result.status.value,
        data=result.data,
        result=result.result,
        error_type=result.error_type,
        error_message=result.error_message,
        timestamp=result.timestamp
    )


@app.get("/plc/{plc_id}/tag/{tag_name}", response_model=TagReadResponse)
async def read_tag_endpoint(plc_id: str, tag_name: str) -> TagReadResponse:
    """
    Read data from a PLC tag.
    
    Args:
        plc_id: The PLC identifier
        tag_name: The name of the tag to read
        
    Returns:
        JSON object containing the tag data and metadata or error information
        
    Note:
        This endpoint always returns 200 OK, but the response includes a status field
        indicating whether the operation was successful or failed, along with error details.
    """
    if not plc_handler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is initializing, please try again later"
        )
    
    start_time = time.time()
    context = {"plc_id": plc_id, "tag_name": tag_name, "operation": "read_tag_api"}
    
    try:
        # Call the tag service - it now returns TagReadResult always
        result = await plc_handler.read_tag(plc_id, tag_name)
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"Tag read API completed with status: {result.status.value}", extra={
            **context, "duration_ms": duration_ms, "status": result.status.value
        })
        
        return _convert_read_result_to_response(result, plc_id)
        
    except Exception as e:
        # This should rarely happen now since TagService handles its own errors
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Unexpected error in read tag API: {str(e)}", extra={
            **context, "error": str(e), "duration_ms": duration_ms
        })
        # Return error response instead of raising exception
        return TagReadResponse(
            plc_id=plc_id,
            tag_name=tag_name,
            status="error",
            error_type="UnknownError",
            error_message=f"Internal server error: {str(e)}",
            timestamp=time.time()
        )


@app.post("/plc/{plc_id}/tag/{tag_name}", response_model=TagWriteResponse)
async def write_tag_endpoint(plc_id: str, tag_name: str, request: WriteTagRequest) -> TagWriteResponse:
    """
    Write data to a PLC tag.
    
    Args:
        plc_id: The PLC identifier
        tag_name: The name of the tag to write
        request: Request body containing the data to write
        
    Returns:
        JSON object with operation details or error information
        
    Note:
        This endpoint always returns 200 OK, but the response includes a status field
        indicating whether the operation was successful or failed, along with error details.
    """
    if not plc_handler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is initializing, please try again later"
        )
    
    start_time = time.time()
    context = {
        "plc_id": plc_id, 
        "tag_name": tag_name, 
        "data": request.data,
        "operation": "write_tag_api"
    }
    
    try:
        # Call the tag service - it now returns TagWriteResult always
        result = await plc_handler.write_tag(plc_id, tag_name, request.data)
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"Tag write API completed with status: {result.status.value}", extra={
            **context, "duration_ms": duration_ms, "status": result.status.value
        })
        
        return _convert_write_result_to_response(result, plc_id)
        
    except Exception as e:
        # This should rarely happen now since TagService handles its own errors
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Unexpected error in write tag API: {str(e)}", extra={
            **context, "error": str(e), "duration_ms": duration_ms
        })
        # Return error response instead of raising exception
        return TagWriteResponse(
            plc_id=plc_id,
            tag_name=tag_name,
            status="error",
            data=request.data,
            error_type="UnknownError",
            error_message=f"Internal server error: {str(e)}",
            timestamp=time.time()
        )


@app.post("/plc/{plc_id}/tags/read", response_model=BulkReadResponseModel)
async def read_multiple_tags_endpoint(plc_id: str, request: BulkReadRequest) -> BulkReadResponseModel:
    """
    Read multiple tags from a PLC concurrently.
    
    Args:
        plc_id: The PLC identifier
        request: Request body containing list of tag names to read
        
    Returns:
        JSON object containing results for all tag reads, including both successful and failed operations
        
    Response includes:
        - summary: counts of total requested, successful, and failed reads
        - overall_status: "success" (all succeeded), "partial_success" (mixed), or "failed" (all failed)  
        - results: detailed results for each tag including data or error information
        
    Note:
        This endpoint uses different status codes based on results:
        - 200: Complete success or complete failure (check overall_status)
        - 207: Partial success (some tags succeeded, some failed)
    """
    if not plc_handler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is initializing, please try again later"
        )
    
    start_time = time.time()
    context = {
        "plc_id": plc_id, 
        "tag_count": len(request.tag_names),
        "operation": "read_multiple_tags_api"
    }
    
    # Log the request (without full tag list for brevity)
    logger.info(f"Bulk read request for {len(request.tag_names)} tags from PLC {plc_id}")
    logger.debug(f"Bulk read tag names: {request.tag_names[:10]}{'...' if len(request.tag_names) > 10 else ''}")
    
    try:
        # Call the tag service - it always returns BulkReadResponse
        bulk_result = await plc_handler.read_multiple_tags(plc_id, request.tag_names)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Convert internal result format to API response format
        api_results = []
        for result in bulk_result.results:
            api_result = _convert_read_result_to_response(result, plc_id)
            api_results.append(api_result)
        
        # Determine HTTP status code based on results
        if bulk_result.overall_status == "success":
            response_status = status.HTTP_200_OK
        elif bulk_result.overall_status == "partial_success":
            response_status = status.HTTP_207_MULTI_STATUS  # Some succeeded, some failed
        else:  # "failed"
            response_status = status.HTTP_200_OK  # Still return 200, but with error details in response
        
        logger.info(f"Bulk read API completed", extra={
            **context, 
            "successful_count": bulk_result.successful_count,
            "failed_count": bulk_result.failed_count,
            "overall_status": bulk_result.overall_status,
            "duration_ms": duration_ms
        })
        
        response_data = BulkReadResponseModel(
            plc_id=bulk_result.plc_id,
            summary={
                "total_requested": bulk_result.total_requested,
                "successful": bulk_result.successful_count,
                "failed": bulk_result.failed_count
            },
            overall_status=bulk_result.overall_status,
            results=api_results,
            timestamp=bulk_result.timestamp
        )
        
        # Return with appropriate status code
        return JSONResponse(
            content=response_data.dict(),
            status_code=response_status
        )
        
    except Exception as e:
        # This should rarely happen now since TagService handles its own errors
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Unexpected error in bulk read API: {str(e)}", extra={
            **context, "error": str(e), "duration_ms": duration_ms
        })
        
        # Return error response for all requested tags
        error_results = []
        for tag_name in request.tag_names:
            error_result = TagReadResponse(
                plc_id=plc_id,
                tag_name=tag_name,
                status="error",
                error_type="UnknownError",
                error_message=f"Internal server error: {str(e)}",
                timestamp=time.time()
            )
            error_results.append(error_result)
        
        return BulkReadResponseModel(
            plc_id=plc_id,
            summary={
                "total_requested": len(request.tag_names),
                "successful": 0,
                "failed": len(request.tag_names)
            },
            overall_status="failed",
            results=error_results,
            timestamp=time.time()
        )


@app.post("/plc/{plc_id}/tags/write", response_model=BulkWriteResponseModel)
async def write_multiple_tags_endpoint(plc_id: str, request: BulkWriteRequest) -> BulkWriteResponseModel:
    """
    Write multiple tags to a PLC concurrently.
    
    Args:
        plc_id: The PLC identifier
        request: Request body containing dictionary of tag names to values
        
    Returns:
        JSON object containing results for all tag writes, including both successful and failed operations
        
    Response includes:
        - summary: counts of total requested, successful, and failed writes
        - overall_status: "success" (all succeeded), "partial_success" (mixed), or "failed" (all failed)  
        - results: detailed results for each tag including success confirmation or error information
        
    Note:
        This endpoint uses different status codes based on results:
        - 200: Complete success or complete failure (check overall_status)
        - 207: Partial success (some tags succeeded, some failed)
    """
    if not plc_handler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is initializing, please try again later"
        )
    
    start_time = time.time()
    context = {
        "plc_id": plc_id, 
        "tag_count": len(request.tag_data),
        "operation": "write_multiple_tags_api"
    }
    
    logger.info(f"Bulk write request for {len(request.tag_data)} tags to PLC {plc_id}")
    
    try:
        # Call the tag service - it always returns BulkWriteResponse
        bulk_result = await plc_handler.write_multiple_tags(plc_id, request.tag_data)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Convert internal result format to API response format
        api_results = []
        for result in bulk_result.results:
            api_result = _convert_write_result_to_response(result, plc_id)
            api_results.append(api_result)
        
        # Determine HTTP status code based on results
        if bulk_result.overall_status == "success":
            response_status = status.HTTP_200_OK
        elif bulk_result.overall_status == "partial_success":
            response_status = status.HTTP_207_MULTI_STATUS  # Some succeeded, some failed
        else:  # "failed"
            response_status = status.HTTP_200_OK  # Still return 200, but with error details in response
        
        logger.info(f"Bulk write API completed", extra={
            **context, 
            "successful_count": bulk_result.successful_count,
            "failed_count": bulk_result.failed_count,
            "overall_status": bulk_result.overall_status,
            "duration_ms": duration_ms
        })
        
        response_data = BulkWriteResponseModel(
            plc_id=bulk_result.plc_id,
            summary={
                "total_requested": bulk_result.total_requested,
                "successful": bulk_result.successful_count,
                "failed": bulk_result.failed_count
            },
            overall_status=bulk_result.overall_status,
            results=api_results,
            timestamp=bulk_result.timestamp
        )
        
        # Return with appropriate status code
        return JSONResponse(
            content=response_data.dict(),
            status_code=response_status
        )
        
    except Exception as e:
        # This should rarely happen now since TagService handles its own errors
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Unexpected error in bulk write API: {str(e)}", extra={
            **context, "error": str(e), "duration_ms": duration_ms
        })
        
        # Return error response for all requested tags
        error_results = []
        for tag_name, data in request.tag_data.items():
            error_result = TagWriteResponse(
                plc_id=plc_id,
                tag_name=tag_name,
                status="error",
                data=data,
                error_type="UnknownError",
                error_message=f"Internal server error: {str(e)}",
                timestamp=time.time()
            )
            error_results.append(error_result)
        
        return BulkWriteResponseModel(
            plc_id=plc_id,
            summary={
                "total_requested": len(request.tag_data),
                "successful": 0,
                "failed": len(request.tag_data)
            },
            overall_status="failed",
            results=error_results,
            timestamp=time.time()
        )


@app.get("/", response_model=RootResponse)
async def root() -> RootResponse:
    """Root endpoint with API information"""
    return RootResponse(message="PLC Tag API is running", version="1.0.0")


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint that verifies service readiness
    
    Returns:
        JSON object with health status and timestamp
    """
    try:
        # Check if the service is properly initialized
        if not plc_handler:
            logger.warning("Health check failed: Service not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service is initializing"
            )
        
        # Could add additional health checks here (e.g., database connectivity, PLC connections)
        # For now, just verify the handler exists
        
        return HealthResponse(status="healthy", timestamp=time.time())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed"
        ) from e


# Additional endpoint for debugging/monitoring (optional)
@app.get("/status")
async def status_endpoint():
    """
    Detailed status endpoint for monitoring and debugging
    """
    try:
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


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
