from datetime import datetime
import time
from typing import Any, List
from contextlib import asynccontextmanager
import asyncio

from pymodbus.exceptions import ConnectionException, ModbusException
from pymodbus.client import AsyncModbusTcpClient

from plant_control.app.models.connection_manager import ConnectionMetrics, ConnectionState, ModbusOperation
from plant_control.app.models.plc_config import PLCConfig
from plant_control.app.utilities.telemetry import logger
from plant_control.app.core.circuit_breaker import CircuitBreaker

# Constants for better maintainability
DEFAULT_CONNECTION_TIMEOUT = 10.0
DEFAULT_RETRY_BASE_DELAY = 2.0
DEFAULT_OPERATION_BASE_DELAY = 0.1
HEALTH_CHECK_REGISTER = 0
HEALTH_CHECK_COUNT = 1


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
        unit_id = self.config.unit_id or 1
        
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
