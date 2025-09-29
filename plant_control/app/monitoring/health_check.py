from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
import time

from plant_control.app.utilities.telemetry import logger

from plant_control.app.schemas.health import (
    SystemHealthResponse,
    SystemDiagnosticsResponse,
    PLCHealthResponse,
    PerformanceMetricsResponse,
    ReadinessResponse,
    LivenessResponse
)
from plant_control.app.dependencies import get_health_service
from plant_control.app.utilities.converters import (
    convert_system_health_to_response,
    convert_plc_health_to_response
)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=SystemHealthResponse)
async def health_check(health_service=get_health_service) -> SystemHealthResponse:
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
        response = convert_system_health_to_response(system_health)
        
        # Determine HTTP status code based on health
        if system_health.overall_status.value == "HEALTHY":
            status_code = status.HTTP_200_OK
        elif system_health.overall_status.value == "DEGRADED":
            status_code = status.HTTP_200_OK  # Still operational
        else:  # UNHEALTHY
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug("Health check completed", extra={
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


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check(health_service=get_health_service) -> ReadinessResponse:
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


@router.get("/health/live", response_model=LivenessResponse)
async def liveness_check(health_service=get_health_service) -> LivenessResponse:
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


@router.get("/diagnostics", response_model=SystemDiagnosticsResponse)
async def system_diagnostics(health_service=get_health_service) -> SystemDiagnosticsResponse:
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
            system_health=convert_system_health_to_response(diagnostics.system_health),
            plc_details=[
                convert_plc_health_to_response(plc) for plc in diagnostics.plc_details
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


@router.get("/health/plc/{plc_id}", response_model=PLCHealthResponse)
async def plc_health_check(plc_id: str, health_service=get_health_service) -> PLCHealthResponse:
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
        response = convert_plc_health_to_response(plc_health)
        
        # Determine status code based on PLC health
        if plc_health.status.value == "UP":
            status_code = status.HTTP_200_OK
        elif plc_health.status.value == "DEGRADED":
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


@router.get("/metrics/performance", response_model=PerformanceMetricsResponse)
async def performance_metrics(health_service=get_health_service) -> PerformanceMetricsResponse:
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
@router.get("/health/simple")
async def simple_health_check(health_service=get_health_service):
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
