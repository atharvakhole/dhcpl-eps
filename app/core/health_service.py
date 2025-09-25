from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
import time
from datetime import datetime

from app.core.connection_manager import connection_manager
from app.utilities.telemetry import logger


# Enums for health states
class ServiceHealth(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class ComponentStatus(Enum):
    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"


# Structured Response Classes
@dataclass
class ComponentHealth:
    name: str
    status: ComponentStatus
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None

@dataclass 
class PLCHealth:
    plc_id: str
    status: ComponentStatus
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

@dataclass
class SystemHealth:
    overall_status: ServiceHealth
    service_uptime_seconds: float
    total_plcs: int
    healthy_plcs: int
    degraded_plcs: int
    unhealthy_plcs: int
    components: List[ComponentHealth]
    timestamp: float

@dataclass
class SystemDiagnostics:
    system_health: SystemHealth
    plc_details: List[PLCHealth]
    performance_summary: Dict[str, Any]
    timestamp: float

@dataclass
class PerformanceMetrics:
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    avg_response_time_ms: float
    requests_per_minute: float
    timestamp: float


class HealthService:
    """
    Service for health checks and system diagnostics
    
    Provides structured health information by leveraging the connection manager's
    health check capabilities and system monitoring.
    """
    
    def __init__(self):
        self.service_start_time = time.time()
        self.last_health_check = None
        
        logger.debug("Health service initialized", extra={
            "component": "health_service",
            "service_start_time": self.service_start_time
        })
    
    async def get_service_health(self) -> SystemHealth:
        """
        Get overall service health status
        
        Returns:
            SystemHealth with overall status and component breakdown
        """
        start_time = time.time()
        timestamp = start_time
        
        logger.debug("Checking service health", extra={
            "component": "health_service",
            "operation": "get_service_health"
        })
        
        try:
            # Get connection manager health
            connection_health = await connection_manager.get_health_status()
            
            # Analyze PLC health
            plc_status_counts = self._analyze_plc_health(connection_health.get('plc_status', {}))
            
            # Determine overall service health
            overall_status = self._determine_overall_service_health(
                connection_health['status'], 
                plc_status_counts
            )
            
            # Build component health list
            components = await self._build_component_health_list(connection_health)
            
            service_uptime = time.time() - self.service_start_time
            
            health = SystemHealth(
                overall_status=overall_status,
                service_uptime_seconds=service_uptime,
                total_plcs=connection_health['total_plcs'],
                healthy_plcs=plc_status_counts['healthy'],
                degraded_plcs=plc_status_counts['degraded'], 
                unhealthy_plcs=plc_status_counts['unhealthy'],
                components=components,
                timestamp=timestamp
            )
            
            self.last_health_check = timestamp
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.debug("Service health check completed", extra={
                "component": "health_service",
                "overall_status": overall_status.value,
                "duration_ms": duration_ms
            })
            
            return health
            
        except Exception as e:
            logger.error("Service health check failed", extra={
                "component": "health_service",
                "error": str(e)
            })
            
            # Return degraded health on error
            return SystemHealth(
                overall_status=ServiceHealth.DEGRADED,
                service_uptime_seconds=time.time() - self.service_start_time,
                total_plcs=0,
                healthy_plcs=0,
                degraded_plcs=0,
                unhealthy_plcs=0,
                components=[ComponentHealth(
                    name="health_check",
                    status=ComponentStatus.DOWN,
                    message=f"Health check failed: {str(e)}",
                    timestamp=timestamp
                )],
                timestamp=timestamp
            )
    
    async def get_system_diagnostics(self) -> SystemDiagnostics:
        """
        Get comprehensive system diagnostics
        
        Returns:
            SystemDiagnostics with detailed health, PLC status, and performance data
        """
        start_time = time.time()
        timestamp = start_time
        
        logger.debug("Getting system diagnostics", extra={
            "component": "health_service",
            "operation": "get_system_diagnostics"
        })
        
        try:
            # Get system health
            system_health = await self.get_service_health()
            
            # Get detailed PLC information
            plc_details = await self._get_detailed_plc_health()
            
            # Calculate performance summary
            performance_summary = self._calculate_performance_summary(plc_details)
            
            diagnostics = SystemDiagnostics(
                system_health=system_health,
                plc_details=plc_details,
                performance_summary=performance_summary,
                timestamp=timestamp
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.debug("System diagnostics completed", extra={
                "component": "health_service",
                "plc_count": len(plc_details),
                "duration_ms": duration_ms
            })
            
            return diagnostics
            
        except Exception as e:
            logger.error("System diagnostics failed", extra={
                "component": "health_service", 
                "error": str(e)
            })
            raise
    
    async def get_plc_health(self, plc_id: str) -> PLCHealth:
        """
        Get health status for a specific PLC
        
        Args:
            plc_id: PLC identifier
            
        Returns:
            PLCHealth with detailed status for the specified PLC
        """
        logger.debug("Getting PLC health", extra={
            "component": "health_service",
            "plc_id": plc_id,
            "operation": "get_plc_health"
        })
        
        try:
            plc_status = connection_manager.get_connection_status(plc_id)
            return self._convert_to_plc_health(plc_status)
            
        except Exception as e:
            logger.error("PLC health check failed", extra={
                "component": "health_service",
                "plc_id": plc_id,
                "error": str(e)
            })
            
            # Return unhealthy status on error
            return PLCHealth(
                plc_id=plc_id,
                status=ComponentStatus.DOWN,
                state="error",
                circuit_breaker_state="unknown", 
                host="unknown",
                port=0,
                last_error=str(e),
                timestamp=time.time()
            )
    
    async def get_performance_metrics(self) -> PerformanceMetrics:
        """
        Get aggregated performance metrics across all PLCs
        
        Returns:
            PerformanceMetrics with system-wide performance data
        """
        logger.debug("Getting performance metrics", extra={
            "component": "health_service",
            "operation": "get_performance_metrics"
        })
        
        try:
            plc_details = await self._get_detailed_plc_health()
            
            total_requests = sum(plc.success_rate for plc in plc_details if plc.success_rate)
            successful_requests = sum(
                int(plc.success_rate / 100 * total_requests) for plc in plc_details 
                if plc.success_rate
            )
            failed_requests = total_requests - successful_requests
            
            avg_response_time = sum(
                plc.response_time_ms for plc in plc_details 
                if plc.response_time_ms
            ) / len([plc for plc in plc_details if plc.response_time_ms]) if plc_details else 0
            
            # Estimate requests per minute based on recent activity
            requests_per_minute = self._estimate_requests_per_minute(plc_details)
            
            return PerformanceMetrics(
                total_requests=int(total_requests),
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                success_rate=successful_requests / total_requests * 100 if total_requests > 0 else 0,
                avg_response_time_ms=avg_response_time,
                requests_per_minute=requests_per_minute,
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error("Performance metrics calculation failed", extra={
                "component": "health_service",
                "error": str(e)
            })
            
            # Return empty metrics on error
            return PerformanceMetrics(
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                success_rate=0.0,
                avg_response_time_ms=0.0,
                requests_per_minute=0.0,
                timestamp=time.time()
            )
    
    def is_service_ready(self) -> bool:
        """
        Check if service is ready to handle requests
        
        Returns:
            bool: True if service is ready
        """
        try:
            # Service is ready if connection manager is initialized
            ready = connection_manager.is_initialized
            
            logger.debug("Service readiness check", extra={
                "component": "health_service",
                "ready": ready,
                "connection_manager_initialized": connection_manager.is_initialized
            })
            
            return ready
            
        except Exception as e:
            logger.error("Service readiness check failed", extra={
                "component": "health_service",
                "error": str(e)
            })
            return False
    
    def is_service_live(self) -> bool:
        """
        Check if service is alive (basic liveness check)
        
        Returns:
            bool: True if service is alive
        """
        try:
            # Service is live if health service is functioning
            # This is a simple check that the service can respond
            current_time = time.time()
            uptime = current_time - self.service_start_time
            
            logger.debug("Service liveness check", extra={
                "component": "health_service", 
                "uptime_seconds": uptime,
                "alive": True
            })
            
            return True
            
        except Exception as e:
            logger.error("Service liveness check failed", extra={
                "component": "health_service",
                "error": str(e)
            })
            return False
    
    # Private helper methods
    
    def _analyze_plc_health(self, plc_status: Dict[str, Any]) -> Dict[str, int]:
        """Analyze PLC health and categorize by status"""
        counts = {"healthy": 0, "degraded": 0, "unhealthy": 0}
        
        for plc_id, status in plc_status.items():
            state = status.get('state', 'unknown')
            circuit_state = status.get('circuit_breaker', 'unknown')
            
            if state == 'connected' and circuit_state == 'connected':
                counts["healthy"] += 1
            elif state == 'connected' and circuit_state == 'circuit_open':
                counts["degraded"] += 1
            else:
                counts["unhealthy"] += 1
        
        logger.debug("PLC health analysis", extra={
            "component": "health_service",
            "healthy_count": counts["healthy"],
            "degraded_count": counts["degraded"], 
            "unhealthy_count": counts["unhealthy"]
        })
        
        return counts
    
    def _determine_overall_service_health(self, connection_health: str, plc_counts: Dict[str, int]) -> ServiceHealth:
        """Determine overall service health based on component health"""
        total_plcs = sum(plc_counts.values())
        
        if total_plcs == 0:
            return ServiceHealth.UNHEALTHY
        
        healthy_ratio = plc_counts["healthy"] / total_plcs
        
        if healthy_ratio >= 1.0:
            return ServiceHealth.HEALTHY
        elif healthy_ratio >= 0.5:
            return ServiceHealth.DEGRADED
        else:
            return ServiceHealth.UNHEALTHY
    
    async def _build_component_health_list(self, connection_health: Dict[str, Any]) -> List[ComponentHealth]:
        """Build list of component health statuses"""
        components = []
        
        # Connection Manager component
        connection_status = ComponentStatus.UP if connection_health['status'] != 'unhealthy' else ComponentStatus.DOWN
        components.append(ComponentHealth(
            name="connection_manager",
            status=connection_status,
            message=f"Managing {connection_health['total_plcs']} PLCs",
            details={
                "connected_plcs": connection_health['connected_plcs'],
                "total_plcs": connection_health['total_plcs']
            },
            timestamp=time.time()
        ))
        
        # Add individual PLC components
        for plc_id, status in connection_health.get('plc_status', {}).items():
            plc_status = self._determine_plc_component_status(status)
            components.append(ComponentHealth(
                name=f"plc_{plc_id}",
                status=plc_status,
                message=f"State: {status.get('state', 'unknown')}",
                details=status,
                timestamp=time.time()
            ))
        
        return components
    
    def _determine_plc_component_status(self, status: Dict[str, Any]) -> ComponentStatus:
        """Determine component status for individual PLC"""
        state = status.get('state', 'unknown')
        circuit_state = status.get('circuit_breaker', 'unknown')
        
        if state == 'connected' and circuit_state == 'connected':
            return ComponentStatus.UP
        elif state == 'connected':
            return ComponentStatus.DEGRADED
        else:
            return ComponentStatus.DOWN
    
    async def _get_detailed_plc_health(self) -> List[PLCHealth]:
        """Get detailed health information for all PLCs"""
        try:
            all_plc_status = connection_manager.get_connection_status()
            return [
                self._convert_to_plc_health(plc_status) 
                for plc_status in all_plc_status.values()
            ]
        except Exception as e:
            logger.error("Failed to get detailed PLC health", extra={
                "component": "health_service",
                "error": str(e)
            })
            return []
    
    def _convert_to_plc_health(self, plc_status: Dict[str, Any]) -> PLCHealth:
        """Convert connection manager status to PLCHealth object"""
        metrics = plc_status.get('metrics', {})
        
        # Determine PLC health status
        state = plc_status.get('state', 'unknown')
        circuit_state = plc_status.get('circuit_breaker_state', 'unknown')
        
        if state == 'connected' and circuit_state == 'connected':
            status = ComponentStatus.UP
        elif state == 'connected':
            status = ComponentStatus.DEGRADED
        else:
            status = ComponentStatus.DOWN
        
        return PLCHealth(
            plc_id=plc_status['plc_id'],
            status=status,
            state=state,
            circuit_breaker_state=circuit_state,
            host=plc_status['host'],
            port=plc_status['port'],
            response_time_ms=metrics.get('avg_response_time', 0) * 1000 if metrics.get('avg_response_time') else None,
            success_rate=metrics.get('success_rate', 0.0),
            uptime_seconds=metrics.get('uptime_seconds'),
            last_error=metrics.get('last_error'),
            last_error_time=metrics.get('last_error_time'),
            timestamp=time.time()
        )
    
    def _calculate_performance_summary(self, plc_details: List[PLCHealth]) -> Dict[str, Any]:
        """Calculate performance summary from PLC details"""
        if not plc_details:
            return {
                "avg_success_rate": 0.0,
                "avg_response_time_ms": 0.0,
                "total_uptime_hours": 0.0,
                "plc_count": 0
            }
        
        avg_success_rate = sum(plc.success_rate for plc in plc_details) / len(plc_details)
        
        response_times = [plc.response_time_ms for plc in plc_details if plc.response_time_ms is not None]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
        
        uptimes = [plc.uptime_seconds for plc in plc_details if plc.uptime_seconds is not None]
        total_uptime_hours = sum(uptimes) / 3600 if uptimes else 0.0
        
        return {
            "avg_success_rate": round(avg_success_rate, 2),
            "avg_response_time_ms": round(avg_response_time, 2),
            "total_uptime_hours": round(total_uptime_hours, 2),
            "plc_count": len(plc_details)
        }
    
    def _estimate_requests_per_minute(self, plc_details: List[PLCHealth]) -> float:
        """Estimate requests per minute based on recent activity"""
        # This is a simplified estimation - in production you might want to track this more precisely
        if not plc_details:
            return 0.0
        
        # Simple heuristic based on response times and uptime
        active_plcs = len([plc for plc in plc_details if plc.status == ComponentStatus.UP])
        
        # Estimate based on typical bulk read patterns
        estimated_rpm = active_plcs * 60.0  # Assume 1 request per second per active PLC
        
        return estimated_rpm
