from datetime import datetime
import time
from typing import Any, Dict, List, Optional

from pymodbus.exceptions import ConnectionException, ModbusException
from ...app.config import ConfigManager
from ...app.models.connection_manager import ConnectionMetrics, ConnectionState, ModbusOperation
from ...app.models.plc_config import PLCConfig
from pymodbus.client import AsyncModbusTcpClient
from contextlib import asynccontextmanager
import asyncio

from ...app.utilities.telemetry import logger

# Constants for better maintainability
DEFAULT_CONNECTION_TIMEOUT = 10.0
DEFAULT_RETRY_BASE_DELAY = 2.0
DEFAULT_OPERATION_BASE_DELAY = 0.1
HEALTH_CHECK_REGISTER = 0
HEALTH_CHECK_COUNT = 1


class CircuitBreaker:
    """Circuit breaker for PLC connection protection"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = ConnectionState.CONNECTED
    
    def record_success(self):
        """Record successful operation and potentially close circuit"""
        self.failure_count = 0
        if self.state == ConnectionState.CIRCUIT_OPEN:
            self.state = ConnectionState.CONNECTED
            logger.info("Circuit breaker recovered", extra={
                "component": "circuit_breaker",
                "action": "circuit_closed",
                "previous_failure_count": self.failure_count
            })
    
    def record_failure(self):
        """Record failed operation and potentially open circuit"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        logger.debug("Circuit breaker failure recorded", extra={
            "component": "circuit_breaker", 
            "failure_count": self.failure_count,
            "threshold": self.failure_threshold
        })
        
        if self.failure_count >= self.failure_threshold:
            self.state = ConnectionState.CIRCUIT_OPEN
            logger.warning("Circuit breaker opened due to failures", extra={
                "component": "circuit_breaker",
                "failure_count": self.failure_count,
                "threshold": self.failure_threshold,
                "timeout_seconds": self.timeout
            })
    
    def can_attempt(self) -> bool:
        """Check if connection attempts are allowed"""
        if self.state != ConnectionState.CIRCUIT_OPEN:
            return True
        
        if self.last_failure_time is None:
            return True
        
        if self._is_timeout_expired():
            logger.info("Circuit breaker timeout expired", extra={
                "component": "circuit_breaker",
                "action": "attempting_reconnection",
                "timeout_seconds": self.timeout
            })
            return True
        
        return False
    
    def _is_timeout_expired(self) -> bool:
        """Check if circuit breaker timeout has expired"""
        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() > self.timeout


class PLCConnection:
    """Manages connection pool and operations for a single PLC"""
    
    def __init__(self, config: PLCConfig):
        self.config = config
        self.clients: List[AsyncModbusTcpClient] = []
        self.available_clients = asyncio.Queue()
        self.metrics = ConnectionMetrics()
        self.circuit_breaker = CircuitBreaker(
            config.circuit_breaker_threshold, 
            config.circuit_breaker_timeout
        )
        self.state = ConnectionState.DISCONNECTED
        self.health_check_task = None
        self.operation_lock = asyncio.Lock()
        
        logger.debug("PLC connection initialized", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id,
            "host": self.config.host,
            "port": self.config.port,
            "max_connections": self.config.max_concurrent_connections
        })
        
    async def initialize(self):
        """Initialize connection pool with proper error handling"""
        logger.info("Initializing connection pool", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id,
            "pool_size": self.config.max_concurrent_connections
        })
        
        try:
            await self._create_connection_pool()
            await self._start_health_monitoring()
            
            logger.info("Connection pool ready", extra={
                "component": "plc_connection",
                "plc_id": self.config.plc_id,
                "pool_size": len(self.clients)
            })
            
        except Exception as e:
            logger.error("Failed to initialize connection pool", extra={
                "component": "plc_connection",
                "plc_id": self.config.plc_id,
                "error": str(e)
            })
            raise
    
    async def shutdown(self):
        """Shutdown all connections cleanly"""
        logger.info("Shutting down PLC connection", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id
        })
        
        await self._stop_health_monitoring()
        await self._close_all_clients()
        
        self.state = ConnectionState.DISCONNECTED
        logger.debug("PLC connection shutdown complete", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id
        })
    
    @asynccontextmanager
    async def get_client(self):
        """Get connection from pool with automatic management"""
        if not self.circuit_breaker.can_attempt():
            error_msg = f"Circuit breaker open for {self.config.plc_id}"
            logger.warning("Connection attempt blocked by circuit breaker", extra={
                "component": "plc_connection",
                "plc_id": self.config.plc_id,
                "circuit_state": self.circuit_breaker.state.value
            })
            raise ConnectionException(error_msg)
        
        client = None
        try:
            client = await self._acquire_client()
            await self._ensure_client_connected(client)
            
            logger.debug("Client acquired from pool", extra={
                "component": "plc_connection",
                "plc_id": self.config.plc_id,
                "client_connected": client.connected
            })
            
            yield client
            
        except Exception as e:
            logger.error("Client acquisition failed", extra={
                "component": "plc_connection", 
                "plc_id": self.config.plc_id,
                "error": str(e)
            })
            self.circuit_breaker.record_failure()
            raise
        finally:
            await self._release_client(client)
    
    async def execute_operation(self, operation: ModbusOperation) -> Any:
        """Execute Modbus operation with comprehensive monitoring"""
        start_time = time.time()
        self.metrics.total_requests += 1
        
        logger.debug("Executing operation", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id,
            "operation_type": operation.operation_type,
            "address": operation.address,
            "original_address": operation.original_address
        })
        
        try:
            async with self.operation_lock:
                result = await self._execute_with_retry(operation)
            
            self._record_successful_operation(start_time)
            return result
            
        except Exception as e:
            self._record_failed_operation(start_time, str(e))
            raise
    
    # Private methods for better organization
    
    async def _create_connection_pool(self):
        """Create the initial connection pool"""
        for i in range(self.config.max_concurrent_connections):
            client = AsyncModbusTcpClient(
                host=self.config.host,
                port=self.config.port,
                timeout=self.config.timeout
            )
            self.clients.append(client)
            await self.available_clients.put(client)
            
            logger.debug("Client added to pool", extra={
                "component": "plc_connection",
                "plc_id": self.config.plc_id,
                "client_index": i,
                "pool_size": len(self.clients)
            })
    
    async def _start_health_monitoring(self):
        """Start background health check task"""
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        logger.debug("Health monitoring started", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id,
            "check_interval": self.config.health_check_interval
        })
    
    async def _stop_health_monitoring(self):
        """Stop background health check task"""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
            
            logger.debug("Health monitoring stopped", extra={
                "component": "plc_connection",
                "plc_id": self.config.plc_id
            })
    
    async def _close_all_clients(self):
        """Close all client connections"""
        for i, client in enumerate(self.clients):
            try:
                if client.connected:
                    client.close()
                    logger.debug("Client connection closed", extra={
                        "component": "plc_connection",
                        "plc_id": self.config.plc_id,
                        "client_index": i
                    })
            except Exception as e:
                logger.warning("Error closing client connection", extra={
                    "component": "plc_connection",
                    "plc_id": self.config.plc_id,
                    "client_index": i,
                    "error": str(e)
                })
    
    async def _acquire_client(self):
        """Acquire a client from the connection pool"""
        try:
            return await asyncio.wait_for(
                self.available_clients.get(), 
                timeout=DEFAULT_CONNECTION_TIMEOUT
            )
        except asyncio.TimeoutError:
            error_msg = f"No available connections for {self.config.plc_id}"
            logger.error("Connection pool exhausted", extra={
                "component": "plc_connection",
                "plc_id": self.config.plc_id,
                "pool_size": len(self.clients),
                "timeout": DEFAULT_CONNECTION_TIMEOUT
            })
            raise ConnectionException(error_msg)
    
    async def _ensure_client_connected(self, client: AsyncModbusTcpClient):
        """Ensure client is connected, reconnect if necessary"""
        if not client.connected:
            logger.debug("Client not connected, attempting connection", extra={
                "component": "plc_connection",
                "plc_id": self.config.plc_id
            })
            await self._connect_client(client)
    
    async def _release_client(self, client):
        """Return client to the connection pool"""
        if client is not None:
            await self.available_clients.put(client)
            logger.debug("Client returned to pool", extra={
                "component": "plc_connection",
                "plc_id": self.config.plc_id
            })
    
    async def _connect_client(self, client: AsyncModbusTcpClient):
        """Connect client with exponential backoff retry"""
        for attempt in range(self.config.retries):
            try:
                logger.debug("Attempting client connection", extra={
                    "component": "plc_connection",
                    "plc_id": self.config.plc_id,
                    "attempt": attempt + 1,
                    "max_retries": self.config.retries
                })
                
                await client.connect()
                
                if client.connected:
                    self._record_successful_connection()
                    return
                    
            except Exception as e:
                logger.warning("Connection attempt failed", extra={
                    "component": "plc_connection",
                    "plc_id": self.config.plc_id,
                    "attempt": attempt + 1,
                    "error": str(e)
                })
                
                if attempt < self.config.retries - 1:
                    delay = DEFAULT_RETRY_BASE_DELAY ** attempt
                    await asyncio.sleep(delay)
        
        self._record_failed_connection()
        raise ConnectionException(
            f"Failed to connect to {self.config.plc_id} after {self.config.retries} attempts"
        )
    
    def _record_successful_connection(self):
        """Record metrics for successful connection"""
        self.state = ConnectionState.CONNECTED
        self.metrics.last_successful_connection = datetime.now()
        if self.metrics.connection_uptime_start is None:
            self.metrics.connection_uptime_start = datetime.now()
        self.circuit_breaker.record_success()
        
        logger.debug("Connection established successfully", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id,
            "timestamp": self.metrics.last_successful_connection.isoformat()
        })
    
    def _record_failed_connection(self):
        """Record metrics for failed connection"""
        self.state = ConnectionState.ERROR
        self.circuit_breaker.record_failure()
        
        logger.error("Connection establishment failed", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id,
            "state": self.state.value
        })
    
    async def _health_check_loop(self):
        """Background health monitoring with structured logging"""
        logger.debug("Health check loop started", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id
        })
        
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_check()
            except asyncio.CancelledError:
                logger.debug("Health check loop cancelled", extra={
                    "component": "plc_connection",
                    "plc_id": self.config.plc_id
                })
                break
            except Exception as e:
                logger.error("Health check loop error", extra={
                    "component": "plc_connection",
                    "plc_id": self.config.plc_id,
                    "error": str(e)
                })
    
    async def _perform_health_check(self):
        """Execute health check operation"""
        try:
            async with self.get_client() as client:
                start_time = time.time()
                result = await client.read_holding_registers(
                    HEALTH_CHECK_REGISTER, 
                    HEALTH_CHECK_COUNT, 
                    self.config.unit_id
                )
                response_time = time.time() - start_time
                
                if not result.isError():
                    self._record_health_check_success(response_time)
                else:
                    self._record_health_check_failure(f"Modbus error: {result}")
        
        except Exception as e:
            self._record_health_check_failure(str(e))
    
    def _record_health_check_success(self, response_time: float):
        """Record successful health check"""
        self.metrics.response_times.append(response_time)
        self._update_avg_response_time()
        
        logger.debug("Health check successful", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id,
            "response_time": round(response_time, 3),
            "avg_response_time": round(self.metrics.avg_response_time, 3)
        })
    
    def _record_health_check_failure(self, error_message: str):
        """Record failed health check"""
        self.metrics.last_error = error_message
        self.metrics.last_error_time = datetime.now()
        self.circuit_breaker.record_failure()
        
        logger.debug("Health check failed", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id,
            "error": error_message
        })
    
    def _update_avg_response_time(self):
        """Update average response time metric"""
        if self.metrics.response_times:
            self.metrics.avg_response_time = sum(self.metrics.response_times) / len(self.metrics.response_times)
    
    def _record_successful_operation(self, start_time: float):
        """Record metrics for successful operation"""
        response_time = time.time() - start_time
        self.metrics.response_times.append(response_time)
        self._update_avg_response_time()
        self.metrics.successful_requests += 1
        self.circuit_breaker.record_success()
        
        logger.debug("Operation completed successfully", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id,
            "response_time": round(response_time, 3),
            "success_count": self.metrics.successful_requests
        })
    
    def _record_failed_operation(self, start_time: float, error_message: str):
        """Record metrics for failed operation"""
        self.metrics.failed_requests += 1
        self.metrics.last_error = error_message
        self.metrics.last_error_time = datetime.now()
        self.circuit_breaker.record_failure()
        
        logger.error("Operation failed", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id,
            "error": error_message,
            "failed_count": self.metrics.failed_requests,
            "total_requests": self.metrics.total_requests
        })
    
    async def _execute_with_retry(self, operation: ModbusOperation) -> Any:
        """Execute operation with retry logic - modbus protocol operations unchanged"""
        last_exception = None
        
        logger.debug("Starting operation with retry", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id,
            "operation_type": operation.operation_type,
            "max_retries": operation.max_retries
        })
        
        for attempt in range(operation.max_retries + 1):
            try:
                async with self.get_client() as client:
                    result = await self._execute_modbus_operation(client, operation)
                    
                    logger.debug("Operation attempt succeeded", extra={
                        "component": "plc_connection",
                        "plc_id": self.config.plc_id,
                        "operation_type": operation.operation_type,
                        "attempt": attempt + 1
                    })
                    
                    return result
            
            except Exception as e:
                last_exception = e
                
                if attempt < operation.max_retries:
                    delay = (DEFAULT_OPERATION_BASE_DELAY * (2 ** attempt))
                    
                    logger.warning("Operation attempt failed, retrying", extra={
                        "component": "plc_connection",
                        "plc_id": self.config.plc_id,
                        "operation_type": operation.operation_type,
                        "attempt": attempt + 1,
                        "max_retries": operation.max_retries,
                        "retry_delay": delay,
                        "error": str(e)
                    })
                    
                    await asyncio.sleep(delay)
                else:
                    logger.error("Operation failed after all retries", extra={
                        "component": "plc_connection",
                        "plc_id": self.config.plc_id,
                        "operation_type": operation.operation_type,
                        "total_attempts": attempt + 1,
                        "final_error": str(e)
                    })
        
        raise last_exception
    
    async def _execute_modbus_operation(self, client: AsyncModbusTcpClient, operation: ModbusOperation) -> Any:
        """Execute specific modbus operation - kept unchanged for stability"""
        unit_id = operation.unit_id or self.config.unit_id
        
        logger.debug("Executing modbus operation", extra={
            "component": "plc_connection",
            "plc_id": self.config.plc_id,
            "operation_type": operation.operation_type,
            "address": operation.address,
            "unit_id": unit_id
        })
        
        # Read operations
        if operation.operation_type == 'read_holding':
            result = await client.read_holding_registers(
                operation.address, operation.count, unit_id
            )
            if result.isError():
                raise ModbusException(f"Modbus error reading holding register {operation.original_address} (PDU {operation.address}): {result}")
            return result.registers
        
        elif operation.operation_type == 'read_input':
            result = await client.read_input_registers(
                operation.address, operation.count, unit_id
            )
            if result.isError():
                raise ModbusException(f"Modbus error reading input register {operation.original_address} (PDU {operation.address}): {result}")
            return result.registers
        
        elif operation.operation_type == 'read_coil':
            result = await client.read_coils(
                operation.address, operation.count, unit_id
            )
            if result.isError():
                raise ModbusException(f"Modbus error reading coil {operation.original_address} (PDU {operation.address}): {result}")
            return result.bits
        
        elif operation.operation_type == 'read_discrete':
            result = await client.read_discrete_inputs(
                operation.address, operation.count, unit_id
            )
            if result.isError():
                raise ModbusException(f"Modbus error reading discrete input {operation.original_address} (PDU {operation.address}): {result}")
            return result.bits
        
        # Write operations
        elif operation.operation_type == 'write_register':
            result = await client.write_register(
                operation.address, operation.values, unit_id
            )
            if result.isError():
                raise ModbusException(f"Modbus error writing register {operation.original_address} (PDU {operation.address}): {result}")
            return True
        
        elif operation.operation_type == 'write_registers':
            result = await client.write_registers(
                operation.address, operation.values, unit_id
            )
            if result.isError():
                raise ModbusException(f"Modbus error writing registers {operation.original_address} (PDU {operation.address}): {result}")
            return True
        
        elif operation.operation_type == 'write_coil':
            result = await client.write_coil(
                operation.address, operation.values, unit_id
            )
            if result.isError():
                raise ModbusException(f"Modbus error writing coil {operation.original_address} (PDU {operation.address}): {result}")
            return True
        
        elif operation.operation_type == 'write_coils':
            result = await client.write_coils(
                operation.address, operation.values, unit_id
            )
            if result.isError():
                raise ModbusException(f"Modbus error writing coils {operation.original_address} (PDU {operation.address}): {result}")
            return True
        
        else:
            raise ValueError(f"Unknown operation type: {operation.operation_type}")


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
