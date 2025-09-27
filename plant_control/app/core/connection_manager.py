from datetime import datetime
import time
from typing import Any, Dict, List, Optional
import asyncio

from plant_control.app.config import ConfigManager
from plant_control.app.models.connection_manager import ConnectionMetrics, ConnectionState, ModbusOperation
from plant_control.app.models.plc_config import PLCConfig
from plant_control.app.utilities.telemetry import logger
from plant_control.app.core.plc_connection import PLCConnection


class ConnectionManager:
    """Global connection manager for all PLCs with improved error handling and logging"""
    
    def __init__(self):
        self.plc_connections: Dict[str, PLCConnection] = {}
        self.is_initialized = False
        self.config_manager = None
    
    async def initialize(self, plc_configs: List[PLCConfig], config_manager: ConfigManager):
        """Initialize all PLC connections with comprehensive error reporting"""
        logger.info("Initializing connection manager", extra={
            "component": "connection_manager",
            "plc_count": len(plc_configs)
        })
        
        self.config_manager = config_manager
        
        # Initialize connections concurrently
        initialization_tasks = []
        for config in plc_configs:
            plc_connection = PLCConnection(config)
            self.plc_connections[config.plc_id] = plc_connection
            initialization_tasks.append(self._initialize_plc_connection(plc_connection))
        
        results = await asyncio.gather(*initialization_tasks, return_exceptions=True)
        
        # Report initialization results
        successful_count = 0
        for i, result in enumerate(results):
            plc_id = plc_configs[i].plc_id
            if isinstance(result, Exception):
                logger.error("PLC initialization failed", extra={
                    "component": "connection_manager",
                    "plc_id": plc_id,
                    "error": str(result)
                })
            else:
                successful_count += 1
                logger.debug("PLC initialized successfully", extra={
                    "component": "connection_manager",
                    "plc_id": plc_id
                })
        
        self.is_initialized = True
        
        logger.info("Connection manager initialization complete", extra={
            "component": "connection_manager",
            "total_plcs": len(plc_configs),
            "successful_plcs": successful_count,
            "failed_plcs": len(plc_configs) - successful_count
        })
    
    async def shutdown(self):
        """Shutdown all connections with proper error handling"""
        logger.info("Shutting down connection manager", extra={
            "component": "connection_manager",
            "plc_count": len(self.plc_connections)
        })
        
        shutdown_tasks = [
            self._shutdown_plc_connection(plc_id, connection) 
            for plc_id, connection in self.plc_connections.items()
        ]
        
        results = await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        # Report shutdown results
        for i, (plc_id, result) in enumerate(zip(self.plc_connections.keys(), results)):
            if isinstance(result, Exception):
                logger.warning("PLC shutdown error", extra={
                    "component": "connection_manager",
                    "plc_id": plc_id,
                    "error": str(result)
                })
        
        self.is_initialized = False
        logger.info("Connection manager shutdown complete", extra={
            "component": "connection_manager"
        })

    async def execute_operation(self, plc_id: str, operation: ModbusOperation) -> Any:
        """Execute operation with improved error context and logging"""
        start_time = time.time()
        operation_type = getattr(operation, 'operation_type', 'unknown')
        
        logger.debug("Operation execution started", extra={
            "component": "connection_manager",
            "plc_id": plc_id,
            "operation_type": operation_type,
            "address": operation.address,
            "original_address": operation.original_address
        })
        
        try:
            self._validate_operation_request(plc_id, operation)
            
            # Execute the operation
            result = await self.plc_connections[plc_id].execute_operation(operation)
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.debug("Operation execution completed", extra={
                "component": "connection_manager",
                "plc_id": plc_id,
                "operation_type": operation_type,
                "duration_ms": duration_ms,
                "success": True
            })
            
            return result
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("Operation execution failed", extra={
                "component": "connection_manager",
                "plc_id": plc_id,
                "operation_type": operation_type,
                "duration_ms": duration_ms,
                "error": str(e)
            })
            
            # Re-raise with consistent error message format
            raise Exception(f"Failed to execute {operation_type} on PLC {plc_id}: {e}") from e

    def get_connection_status(self, plc_id: Optional[str] = None) -> Dict[str, Any]:
        """Get connection status with better error handling"""
        logger.debug("Getting connection status", extra={
            "component": "connection_manager",
            "plc_id": plc_id or "all"
        })
        
        try:
            if plc_id:
                if plc_id not in self.plc_connections:
                    raise ValueError(f"PLC {plc_id} not found")
                return self._get_plc_status(self.plc_connections[plc_id])
            
            return {
                plc_id: self._get_plc_status(connection)
                for plc_id, connection in self.plc_connections.items()
            }
        except Exception as e:
            logger.error("Failed to get connection status", extra={
                "component": "connection_manager",
                "plc_id": plc_id,
                "error": str(e)
            })
            raise
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        logger.debug("Getting health status", extra={
            "component": "connection_manager"
        })
        
        total_plcs = len(self.plc_connections)
        connected_plcs = sum(
            1 for conn in self.plc_connections.values() 
            if conn.state == ConnectionState.CONNECTED
        )
        
        health_status = self._determine_overall_health(connected_plcs, total_plcs)
        
        result = {
            'status': health_status,
            'total_plcs': total_plcs,
            'connected_plcs': connected_plcs,
            'disconnected_plcs': total_plcs - connected_plcs,
            'timestamp': datetime.now().isoformat(),
            'plc_status': {
                plc_id: {
                    'state': conn.state.value,
                    'circuit_breaker': conn.circuit_breaker.state.value
                }
                for plc_id, conn in self.plc_connections.items()
            }
        }
        
        logger.debug("Health status retrieved", extra={
            "component": "connection_manager",
            "overall_status": health_status,
            "connected_count": connected_plcs,
            "total_count": total_plcs
        })
        
        return result

    # Private helper methods for better code organization
    
    async def _initialize_plc_connection(self, plc_connection: PLCConnection):
        """Initialize single PLC connection with error handling"""
        try:
            await plc_connection.initialize()
        except Exception as e:
            logger.error("PLC connection initialization failed", extra={
                "component": "connection_manager",
                "plc_id": plc_connection.config.plc_id,
                "error": str(e)
            })
            raise
    
    async def _shutdown_plc_connection(self, plc_id: str, connection: PLCConnection):
        """Shutdown single PLC connection with error handling"""
        try:
            await connection.shutdown()
        except Exception as e:
            logger.warning("PLC connection shutdown error", extra={
                "component": "connection_manager",
                "plc_id": plc_id,
                "error": str(e)
            })
            raise
    
    def _validate_operation_request(self, plc_id: str, operation: ModbusOperation):
        """Validate operation request parameters"""
        if not plc_id or not operation:
            raise ValueError("PLC ID and operation are required")
            
        if plc_id not in self.plc_connections:
            available_plcs = list(self.plc_connections.keys())
            logger.error("PLC not found", extra={
                "component": "connection_manager",
                "requested_plc": plc_id,
                "available_plcs": available_plcs
            })
            raise ValueError(f"No connection found for PLC {plc_id}")
    
    def _get_plc_status(self, connection: PLCConnection) -> Dict[str, Any]:
        """Get detailed status for single PLC"""
        metrics = connection.metrics
        uptime = self._calculate_uptime(metrics.connection_uptime_start)
        
        return {
            'plc_id': connection.config.plc_id,
            'state': connection.state.value,
            'circuit_breaker_state': connection.circuit_breaker.state.value,
            'host': connection.config.host,
            'port': connection.config.port,
            'metrics': {
                'total_requests': metrics.total_requests,
                'successful_requests': metrics.successful_requests,
                'failed_requests': metrics.failed_requests,
                'success_rate': self._calculate_success_rate(metrics),
                'avg_response_time': metrics.avg_response_time,
                'uptime_seconds': uptime,
                'last_successful_connection': metrics.last_successful_connection.isoformat() if metrics.last_successful_connection else None,
                'last_error': metrics.last_error,
                'last_error_time': metrics.last_error_time.isoformat() if metrics.last_error_time else None
            }
        }
    
    def _calculate_uptime(self, uptime_start: Optional[datetime]) -> Optional[float]:
        """Calculate connection uptime in seconds"""
        if uptime_start:
            return (datetime.now() - uptime_start).total_seconds()
        return None
    
    def _calculate_success_rate(self, metrics: ConnectionMetrics) -> float:
        """Calculate success rate percentage"""
        if metrics.total_requests > 0:
            return (metrics.successful_requests / metrics.total_requests) * 100
        return 0.0
    
    def _determine_overall_health(self, connected_plcs: int, total_plcs: int) -> str:
        """Determine overall system health status"""
        if connected_plcs == total_plcs:
            return 'healthy'
        elif connected_plcs > 0:
            return 'degraded'
        else:
            return 'unhealthy'


# Global connection manager instance
connection_manager = ConnectionManager()

# Production API functions - unchanged for compatibility
async def initialize_connections(plc_configs: List[PLCConfig], config_manager: ConfigManager):
    """Initialize global connection manager with multi-vendor support"""
    await connection_manager.initialize(plc_configs, config_manager)

async def shutdown_connections():
    """Shutdown global connection manager"""
    await connection_manager.shutdown()

def get_connection_status(plc_id: Optional[str] = None) -> Dict[str, Any]:
    """Get connection status"""
    return connection_manager.get_connection_status(plc_id)

async def get_health_status() -> Dict[str, Any]:
    """Get health status"""
    return await connection_manager.get_health_status()
