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
        
        # Initialize the tag service and health service
        global plc_handler, health_service
        plc_handler = TagService()
        health_service = HealthService()  # Already initialized globally, but ensure it's ready
        
        logger.info("All services initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down services...")
        await connection_manager.shutdown()

app = FastAPI(title="PLC Tag API", version="1.0.0", lifespan=lifespan)


from app.core.health_service import (
    HealthService, SystemHealth, SystemDiagnostics, PLCHealth, 
    PerformanceMetrics, ServiceHealth, ComponentStatus
)

# Initialize health service globally
health_service = HealthService()

# Updated Pydantic models for API responses
class ComponentHealthResponse(BaseModel):
    name: str
    status: str
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None

class PLCHealthResponse(BaseModel):
    plc_id: str
    status: str
    state: str
    circuit_breaker_state: str
    host: str
    port: int
    response_time_ms: Optional[float] = None
    success_rate: float = 0.0
    uptime_seconds: Optional[float] = None
    last_error: Optional[str] = None
    last_error_time: Optional[str] = None
    timestamp: Optional[float] = None

class SystemHealthResponse(BaseModel):
    overall_status: str
    service_uptime_seconds: float
    total_plcs: int
    healthy_plcs: int
    degraded_plcs: int  
    unhealthy_plcs: int
    components: List[ComponentHealthResponse]
    timestamp: float

class SystemDiagnosticsResponse(BaseModel):
    system_health: SystemHealthResponse
    plc_details: List[PLCHealthResponse]
    performance_summary: Dict[str, Any]
    timestamp: float

class PerformanceMetricsResponse(BaseModel):
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    avg_response_time_ms: float
    requests_per_minute: float
    timestamp: float

class ReadinessResponse(BaseModel):
    status: str
    ready: bool
    message: str
    timestamp: float

class LivenessResponse(BaseModel):
    status: str
    alive: bool
    uptime_seconds: float
    timestamp: float

# Helper function to convert health service responses to API models
def _convert_system_health_to_response(health: SystemHealth) -> SystemHealthResponse:
    """Convert SystemHealth to API response model"""
    return SystemHealthResponse(
        overall_status=health.overall_status.value,
        service_uptime_seconds=health.service_uptime_seconds,
        total_plcs=health.total_plcs,
        healthy_plcs=health.healthy_plcs,
        degraded_plcs=health.degraded_plcs,
        unhealthy_plcs=health.unhealthy_plcs,
        components=[
            ComponentHealthResponse(
                name=comp.name,
                status=comp.status.value,
                message=comp.message,
                details=comp.details,
                timestamp=comp.timestamp
            ) for comp in health.components
        ],
        timestamp=health.timestamp
    )

def _convert_plc_health_to_response(plc_health: PLCHealth) -> PLCHealthResponse:
    """Convert PLCHealth to API response model"""
    return PLCHealthResponse(
        plc_id=plc_health.plc_id,
        status=plc_health.status.value,
        state=plc_health.state,
        circuit_breaker_state=plc_health.circuit_breaker_state,
        host=plc_health.host,
        port=plc_health.port,
        response_time_ms=plc_health.response_time_ms,
        success_rate=plc_health.success_rate,
        uptime_seconds=plc_health.uptime_seconds,
        last_error=plc_health.last_error,
        last_error_time=plc_health.last_error_time,
        timestamp=plc_health.timestamp
    )

# Updated health check endpoints

@app.get("/api/v1/health", response_model=SystemHealthResponse)
async def health_check() -> SystemHealthResponse:
    """
    Comprehensive health check endpoint
    
    Provides overall system health including:
    - Service status and uptime
    - PLC connection health
    - Component status breakdown
    - Summary statistics
    
    Returns:
        SystemHealthResponse with detailed health information
    """
    start_time = time.time()
    
    try:
        logger.debug("Health check requested", extra={
            "component": "api",
            "endpoint": "health_check"
        })
        
        # Get comprehensive health from health service
        system_health = await health_service.get_service_health()
        
        # Convert to API response format
        response = _convert_system_health_to_response(system_health)
        
        # Determine HTTP status code based on health
        if system_health.overall_status == ServiceHealth.HEALTHY:
            status_code = status.HTTP_200_OK
        elif system_health.overall_status == ServiceHealth.DEGRADED:
            status_code = status.HTTP_200_OK  # Still operational
        else:  # UNHEALTHY
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info("Health check completed", extra={
            "component": "api",
            "endpoint": "health_check",
            "overall_status": system_health.overall_status.value,
            "duration_ms": duration_ms
        })
        
        return JSONResponse(
            content=response.dict(),
            status_code=status_code
        )
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error("Health check failed", extra={
            "component": "api",
            "endpoint": "health_check", 
            "error": str(e),
            "duration_ms": duration_ms
        })
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )

@app.get("/api/v1/health/ready", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    """
    Kubernetes-style readiness probe
    
    Indicates whether the service is ready to accept traffic.
    - Returns 200 if ready to handle requests
    - Returns 503 if not ready (initializing or degraded)
    
    Returns:
        ReadinessResponse with readiness status
    """
    try:
        ready = health_service.is_service_ready()
        
        logger.debug("Readiness check", extra={
            "component": "api",
            "endpoint": "readiness_check",
            "ready": ready
        })
        
        if ready:
            return ReadinessResponse(
                status="ready",
                ready=True,
                message="Service is ready to accept requests",
                timestamp=time.time()
            )
        else:
            return JSONResponse(
                content=ReadinessResponse(
                    status="not_ready",
                    ready=False,
                    message="Service is initializing or not ready",
                    timestamp=time.time()
                ).dict(),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
            
    except Exception as e:
        logger.error("Readiness check failed", extra={
            "component": "api",
            "endpoint": "readiness_check",
            "error": str(e)
        })
        
        return JSONResponse(
            content=ReadinessResponse(
                status="error",
                ready=False, 
                message=f"Readiness check failed: {str(e)}",
                timestamp=time.time()
            ).dict(),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

@app.get("/api/v1/health/live", response_model=LivenessResponse)
async def liveness_check() -> LivenessResponse:
    """
    Kubernetes-style liveness probe
    
    Indicates whether the service is alive and functioning.
    - Returns 200 if service is alive
    - Returns 500 if service is dead (should be restarted)
    
    Returns:
        LivenessResponse with liveness status
    """
    try:
        alive = health_service.is_service_live()
        service_uptime = time.time() - health_service.service_start_time
        
        logger.debug("Liveness check", extra={
            "component": "api", 
            "endpoint": "liveness_check",
            "alive": alive,
            "uptime_seconds": service_uptime
        })
        
        if alive:
            return LivenessResponse(
                status="alive",
                alive=True,
                uptime_seconds=service_uptime,
                timestamp=time.time()
            )
        else:
            return JSONResponse(
                content=LivenessResponse(
                    status="dead",
                    alive=False,
                    uptime_seconds=service_uptime,
                    timestamp=time.time()
                ).dict(),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        logger.error("Liveness check failed", extra={
            "component": "api",
            "endpoint": "liveness_check", 
            "error": str(e)
        })
        
        return JSONResponse(
            content=LivenessResponse(
                status="error",
                alive=False,
                uptime_seconds=0.0,
                timestamp=time.time()
            ).dict(),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app.get("/api/v1/diagnostics", response_model=SystemDiagnosticsResponse)
async def system_diagnostics() -> SystemDiagnosticsResponse:
    """
    Comprehensive system diagnostics
    
    Provides detailed system information including:
    - Complete system health breakdown
    - Detailed PLC status for each connection
    - Performance metrics and statistics
    - Historical data and trends
    
    Returns:
        SystemDiagnosticsResponse with comprehensive diagnostic data
    """
    start_time = time.time()
    
    try:
        logger.debug("System diagnostics requested", extra={
            "component": "api",
            "endpoint": "system_diagnostics"
        })
        
        # Get comprehensive diagnostics
        diagnostics = await health_service.get_system_diagnostics()
        
        # Convert to API response format
        response = SystemDiagnosticsResponse(
            system_health=_convert_system_health_to_response(diagnostics.system_health),
            plc_details=[
                _convert_plc_health_to_response(plc) for plc in diagnostics.plc_details
            ],
            performance_summary=diagnostics.performance_summary,
            timestamp=diagnostics.timestamp
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info("System diagnostics completed", extra={
            "component": "api",
            "endpoint": "system_diagnostics",
            "plc_count": len(diagnostics.plc_details),
            "duration_ms": duration_ms
        })
        
        return response
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error("System diagnostics failed", extra={
            "component": "api",
            "endpoint": "system_diagnostics",
            "error": str(e),
            "duration_ms": duration_ms
        })
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"System diagnostics failed: {str(e)}"
        )

@app.get("/api/v1/health/plc/{plc_id}", response_model=PLCHealthResponse)
async def plc_health_check(plc_id: str) -> PLCHealthResponse:
    """
    Get health status for specific PLC
    
    Args:
        plc_id: PLC identifier
        
    Returns:
        PLCHealthResponse with detailed PLC health information
    """
    start_time = time.time()
    
    try:
        logger.debug("PLC health check requested", extra={
            "component": "api",
            "endpoint": "plc_health_check",
            "plc_id": plc_id
        })
        
        # Get PLC health from health service
        plc_health = await health_service.get_plc_health(plc_id)
        
        # Convert to API response format
        response = _convert_plc_health_to_response(plc_health)
        
        # Determine status code based on PLC health
        if plc_health.status == ComponentStatus.UP:
            status_code = status.HTTP_200_OK
        elif plc_health.status == ComponentStatus.DEGRADED:
            status_code = status.HTTP_200_OK  # Still functional
        else:  # DOWN
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug("PLC health check completed", extra={
            "component": "api",
            "endpoint": "plc_health_check",
            "plc_id": plc_id,
            "plc_status": plc_health.status.value,
            "duration_ms": duration_ms
        })
        
        return JSONResponse(
            content=response.dict(),
            status_code=status_code
        )
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error("PLC health check failed", extra={
            "component": "api",
            "endpoint": "plc_health_check",
            "plc_id": plc_id,
            "error": str(e),
            "duration_ms": duration_ms
        })
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "not found" in str(e).lower() else status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PLC health check failed: {str(e)}"
        )

@app.get("/api/v1/metrics/performance", response_model=PerformanceMetricsResponse)
async def performance_metrics() -> PerformanceMetricsResponse:
    """
    Get system performance metrics
    
    Provides aggregated performance data including:
    - Request success rates
    - Average response times  
    - Request throughput
    - System-wide statistics
    
    Returns:
        PerformanceMetricsResponse with performance data
    """
    start_time = time.time()
    
    try:
        logger.debug("Performance metrics requested", extra={
            "component": "api",
            "endpoint": "performance_metrics"
        })
        
        # Get performance metrics from health service
        metrics = await health_service.get_performance_metrics()
        
        # Convert to API response format  
        response = PerformanceMetricsResponse(
            total_requests=metrics.total_requests,
            successful_requests=metrics.successful_requests,
            failed_requests=metrics.failed_requests,
            success_rate=metrics.success_rate,
            avg_response_time_ms=metrics.avg_response_time_ms,
            requests_per_minute=metrics.requests_per_minute,
            timestamp=metrics.timestamp
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug("Performance metrics completed", extra={
            "component": "api",
            "endpoint": "performance_metrics",
            "success_rate": metrics.success_rate,
            "avg_response_time_ms": metrics.avg_response_time_ms,
            "duration_ms": duration_ms
        })
        
        return response
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error("Performance metrics failed", extra={
            "component": "api", 
            "endpoint": "performance_metrics",
            "error": str(e),
            "duration_ms": duration_ms
        })
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Performance metrics failed: {str(e)}"
        )

# Optional: Lightweight health check for load balancers
@app.get("/health")
async def simple_health_check():
    """
    Simple health check for load balancers
    
    Returns basic OK status without detailed diagnostics.
    Useful for load balancer health checks that need fast response.
    """
    try:
        ready = health_service.is_service_ready()
        alive = health_service.is_service_live()
        
        if ready and alive:
            return {"status": "ok", "timestamp": time.time()}
        else:
            return JSONResponse(
                content={"status": "not_ready", "timestamp": time.time()},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
            
    except Exception as e:
        return JSONResponse(
            content={"status": "error", "error": str(e), "timestamp": time.time()},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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

@app.post("/api/v1/registers/bulk-read/{plc_id}", response_model=BulkReadResponseModel)
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


@app.post("/api/v1/registers/bulk-write/{plc_id}", response_model=BulkWriteResponseModel)
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


@app.get("/api/v1/registers/read/{plc_id}/{tag_name}", response_model=TagReadResponse)
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


@app.post("/api/v1/registers/write/{plc_id}/{tag_name}", response_model=TagWriteResponse)
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



@app.get("/", response_model=RootResponse)
async def root() -> RootResponse:
    """Root endpoint with API information"""
    return RootResponse(message="Plant Control API is running", version="1.0.0")

@app.get("/api/v1", response_model=RootResponse)
async def v1_root() -> RootResponse:
    """Root endpoint with API information"""
    return RootResponse(message="Plant Control API v1 is running", version="1.0.0")


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
