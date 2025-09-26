from plant_control.app.core.tag_service import TagReadResult, TagWriteResult
from plant_control.app.core.health_service import SystemHealth, PLCHealth, ComponentStatus

from plant_control.app.schemas.register import TagReadResponse, TagWriteResponse
from plant_control.app.schemas.health import SystemHealthResponse, PLCHealthResponse, ComponentHealthResponse


def convert_read_result_to_response(result: TagReadResult, plc_id: str) -> TagReadResponse:
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


def convert_write_result_to_response(result: TagWriteResult, plc_id: str) -> TagWriteResponse:
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


def convert_system_health_to_response(health: SystemHealth) -> SystemHealthResponse:
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


def convert_plc_health_to_response(plc_health: PLCHealth) -> PLCHealthResponse:
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
