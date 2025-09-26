from pydantic import BaseModel
from typing import Any, List, Dict, Optional


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
