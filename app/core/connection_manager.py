"""
Plant Control API - Connection Management Layer
Robust ModbusTCP connection management with pooling, health monitoring, and fault tolerance
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
import json
from datetime import datetime, timedelta
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException
from collections import deque

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional Redis import with compatibility handling
REDIS_AVAILABLE = False
redis_client_class = None

try:
    # Try the newer redis package first (compatible with Python 3.11+)
    import redis.asyncio as redis
    redis_client_class = redis.Redis
    REDIS_AVAILABLE = True
    logger.debug("Using redis.asyncio for caching")
except ImportError:
    try:
        # Fallback to aioredis for older environments
        import aioredis
        redis_client_class = aioredis.Redis
        REDIS_AVAILABLE = True
        logger.debug("Using aioredis for caching")
    except (ImportError, TypeError) as e:
        logger.info("Redis not available - running without cache. Install 'redis' package for caching support.")
        REDIS_AVAILABLE = False

class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    CIRCUIT_OPEN = "circuit_open"

class Priority(Enum):
    EMERGENCY = 1
    CRITICAL = 2
    NORMAL = 3
    BACKGROUND = 4

@dataclass
class PLCConfig:
    """Configuration for a single PLC"""
    plc_id: str
    host: str
    port: int = 502
    unit_id: int = 1
    timeout: float = 3.0
    retries: int = 3
    description: str = ""
    vendor: str = ""
    model: str = ""
    max_concurrent_connections: int = 5
    health_check_interval: int = 30  # seconds
    circuit_breaker_threshold: int = 5  # failures before opening circuit
    circuit_breaker_timeout: int = 60  # seconds before trying to close circuit

@dataclass
class ConnectionMetrics:
    """Metrics for connection monitoring"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    last_successful_connection: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    connection_uptime_start: Optional[datetime] = None
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))

class CircuitBreaker:
    """Circuit breaker pattern implementation for PLC connections"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = ConnectionState.CONNECTED
    
    def record_success(self):
        """Record a successful operation"""
        self.failure_count = 0
        if self.state == ConnectionState.CIRCUIT_OPEN:
            self.state = ConnectionState.CONNECTED
            logger.info("Circuit breaker closed - connection recovered")
    
    def record_failure(self):
        """Record a failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = ConnectionState.CIRCUIT_OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def can_attempt(self) -> bool:
        """Check if we can attempt a connection"""
        if self.state != ConnectionState.CIRCUIT_OPEN:
            return True
        
        if self.last_failure_time is None:
            return True
        
        time_since_failure = datetime.now() - self.last_failure_time
        if time_since_failure.total_seconds() > self.timeout:
            logger.info("Circuit breaker timeout expired, attempting to reconnect")
            return True
        
        return False

def convert_modbus_address(address):
    """Convert extended Modbus address to base address and register type"""
    if 0x40000 <= address <= 0x4FFFF:  # Holding registers 40001-49999
        return address - 0x40000, "holding_register"
    elif 0x30000 <= address <= 0x3FFFF:  # Input registers 30001-39999
        return address - 0x30000, "input_register"
    elif 0x10000 <= address <= 0x1FFFF:  # Discrete inputs 10001-19999
        return address - 0x10000, "discrete_input"
    elif 0x0000 <= address <= 0x0FFFF:   # Coils 00001-09999
        return address, "coil"
    else:
        # Default: treat as holding register with direct address
        return address, "holding_register"

@dataclass
class ModbusOperation:
    """Represents a Modbus operation request"""
    operation_type: str  # 'read_holding', 'write_register', 'write_registers'
    address: int
    count: Optional[int] = None
    values: Optional[Union[int, List[int]]] = None
    unit_id: Optional[int] = None
    priority: Priority = Priority.NORMAL
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3

class PLCConnection:
    """Manages a single PLC connection with pooling and health monitoring"""
    
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
        
    async def initialize(self):
        """Initialize connection pool"""
        logger.info(f"Initializing connection pool for {self.config.plc_id}")
        
        for i in range(self.config.max_concurrent_connections):
            client = AsyncModbusTcpClient(
                host=self.config.host,
                port=self.config.port,
                timeout=self.config.timeout
            )
            self.clients.append(client)
            await self.available_clients.put(client)
        
        # Start health monitoring
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info(f"Connection pool initialized for {self.config.plc_id} with {len(self.clients)} connections")
    
    async def shutdown(self):
        """Shutdown all connections"""
        logger.info(f"Shutting down connections for {self.config.plc_id}")
        
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        
        for client in self.clients:
            try:
                if client.connected:
                    client.close()
            except Exception as e:
                logger.warning(f"Error closing client connection: {e}")
        
        self.state = ConnectionState.DISCONNECTED
    
    @asynccontextmanager
    async def get_client(self):
        """Get an available client from the pool"""
        if not self.circuit_breaker.can_attempt():
            raise ConnectionException(f"Circuit breaker open for {self.config.plc_id}")
        
        client = None
        try:
            # Wait for available client with timeout
            client = await asyncio.wait_for(
                self.available_clients.get(), 
                timeout=10.0
            )
            
            # Ensure client is connected
            if not client.connected:
                await self._connect_client(client)
            
            yield client
            
        except asyncio.TimeoutError:
            raise ConnectionException(f"No available connections for {self.config.plc_id}")
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
        finally:
            # Return client to pool
            if client is not None:
                await self.available_clients.put(client)
    
    async def _connect_client(self, client: AsyncModbusTcpClient):
        """Connect a single client with retry logic"""
        for attempt in range(self.config.retries):
            try:
                await client.connect()
                if client.connected:
                    self.state = ConnectionState.CONNECTED
                    self.metrics.last_successful_connection = datetime.now()
                    if self.metrics.connection_uptime_start is None:
                        self.metrics.connection_uptime_start = datetime.now()
                    self.circuit_breaker.record_success()
                    return
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed for {self.config.plc_id}: {e}")
                if attempt < self.config.retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        self.state = ConnectionState.ERROR
        self.circuit_breaker.record_failure()
        raise ConnectionException(f"Failed to connect to {self.config.plc_id} after {self.config.retries} attempts")
    
    async def _health_check_loop(self):
        """Continuous health monitoring"""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error for {self.config.plc_id}: {e}")
    
    async def _perform_health_check(self):
        """Perform health check by reading a test register"""
        try:
            async with self.get_client() as client:
                # Try to read first holding register as health check
                start_time = time.time()
                result = await client.read_holding_registers(0, 1, self.config.unit_id)
                response_time = time.time() - start_time
                
                if not result.isError():
                    self.metrics.response_times.append(response_time)
                    self._update_avg_response_time()
                    logger.debug(f"Health check OK for {self.config.plc_id}: {response_time:.3f}s")
                else:
                    logger.warning(f"Health check failed for {self.config.plc_id}: {result}")
                    self.circuit_breaker.record_failure()
        
        except Exception as e:
            logger.debug(f"Health check exception for {self.config.plc_id}: {e}")
            self.metrics.last_error = str(e)
            self.metrics.last_error_time = datetime.now()
            self.circuit_breaker.record_failure()
    
    def _update_avg_response_time(self):
        """Update average response time from recent measurements"""
        if self.metrics.response_times:
            self.metrics.avg_response_time = sum(self.metrics.response_times) / len(self.metrics.response_times)
    
    async def execute_operation(self, operation: ModbusOperation) -> Any:
        """Execute a Modbus operation with error handling and metrics"""
        start_time = time.time()
        self.metrics.total_requests += 1
        
        try:
            async with self.operation_lock:
                result = await self._execute_with_retry(operation)
            
            response_time = time.time() - start_time
            self.metrics.response_times.append(response_time)
            self._update_avg_response_time()
            self.metrics.successful_requests += 1
            self.circuit_breaker.record_success()
            
            return result
            
        except Exception as e:
            self.metrics.failed_requests += 1
            self.metrics.last_error = str(e)
            self.metrics.last_error_time = datetime.now()
            self.circuit_breaker.record_failure()
            raise
    
    async def _execute_with_retry(self, operation: ModbusOperation) -> Any:
        """Execute operation with retry logic"""
        last_exception = None
        
        for attempt in range(operation.max_retries + 1):
            try:
                async with self.get_client() as client:
                    unit_id = operation.unit_id or self.config.unit_id
                    
                    if operation.operation_type == 'read_holding':
                        result = await client.read_holding_registers(
                            operation.address, 
                            operation.count, 
                            unit_id
                        )
                        if result.isError():
                            raise ModbusException(f"Modbus error: {result}")
                        return result.registers
                    
                    elif operation.operation_type == 'write_register':
                        result = await client.write_register(
                            operation.address, 
                            operation.values, 
                            unit_id
                        )
                        if result.isError():
                            raise ModbusException(f"Modbus error: {result}")
                        return True
                    
                    elif operation.operation_type == 'write_registers':
                        result = await client.write_registers(
                            operation.address, 
                            operation.values, 
                            unit_id
                        )
                        if result.isError():
                            raise ModbusException(f"Modbus error: {result}")
                        return True
                    
                    else:
                        raise ValueError(f"Unknown operation type: {operation.operation_type}")
            
            except Exception as e:
                last_exception = e
                if attempt < operation.max_retries:
                    wait_time = (2 ** attempt) * 0.1  # Exponential backoff starting at 100ms
                    logger.warning(f"Operation attempt {attempt + 1} failed for {self.config.plc_id}, retrying in {wait_time:.1f}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Operation failed after {attempt + 1} attempts for {self.config.plc_id}: {e}")
        
        raise last_exception

class ConnectionManager:
    """Main connection manager orchestrating all PLC connections"""
    
    def __init__(self):
        self.plc_connections: Dict[str, PLCConnection] = {}
        self.is_initialized = False
        self.redis_client = None
    
    async def initialize(self, plc_configs: List[PLCConfig], redis_url: Optional[str] = None):
        """Initialize all PLC connections"""
        logger.info("Initializing Connection Manager")
        
        # Initialize Redis for caching (optional)
        if redis_url and REDIS_AVAILABLE:
            try:
                if 'redis.asyncio' in str(redis_client_class):
                    # Using redis.asyncio
                    self.redis_client = redis_client_class.from_url(redis_url)
                    await self.redis_client.ping()
                else:
                    # Using aioredis
                    self.redis_client = await redis_client_class.from_url(redis_url)
                logger.info("Redis connection established")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Continuing without cache.")
                self.redis_client = None
        elif redis_url and not REDIS_AVAILABLE:
            logger.warning("Redis URL provided but redis package not available. Install with: pip install redis")
        else:
            logger.info("Redis not configured, running without cache")
        
        # Initialize PLC connections
        initialization_tasks = []
        for config in plc_configs:
            plc_connection = PLCConnection(config)
            self.plc_connections[config.plc_id] = plc_connection
            initialization_tasks.append(plc_connection.initialize())
        
        # Initialize all connections concurrently
        results = await asyncio.gather(*initialization_tasks, return_exceptions=True)
        
        # Log any initialization failures
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to initialize PLC {plc_configs[i].plc_id}: {result}")
        
        self.is_initialized = True
        logger.info(f"Connection Manager initialized with {len(self.plc_connections)} PLCs")
    
    async def shutdown(self):
        """Shutdown all connections"""
        logger.info("Shutting down Connection Manager")
        
        shutdown_tasks = []
        for plc_connection in self.plc_connections.values():
            shutdown_tasks.append(plc_connection.shutdown())
        
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        if self.redis_client:
            try:
                if hasattr(self.redis_client, 'aclose'):
                    await self.redis_client.aclose()
                elif hasattr(self.redis_client, 'close'):
                    await self.redis_client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")
        
        self.is_initialized = False
        logger.info("Connection Manager shutdown complete")
    
    def _validate_plc_id(self, plc_id: str):
        """Validate PLC ID exists"""
        if not self.is_initialized:
            raise RuntimeError("Connection Manager not initialized")
        
        if plc_id not in self.plc_connections:
            raise ValueError(f"Unknown PLC ID: {plc_id}")
    
    async def read_registers(self, plc_id: str, start_address: int, count: int, unit_id: Optional[int] = None) -> List[int]:
        """Read multiple holding registers"""
        self._validate_plc_id(plc_id)
        
        operation = ModbusOperation(
            operation_type='read_holding',
            address=start_address,
            count=count,
            unit_id=unit_id
        )
        
        return await self.plc_connections[plc_id].execute_operation(operation)
    
    async def read_register(self, plc_id: str, address: int, unit_id: Optional[int] = None) -> int:
        """Read a single holding register"""
        result = await self.read_registers(plc_id, address, 1, unit_id)
        return result[0] if result else None
    async def write_register(self, plc_id: str, address: int, value: int, unit_id: Optional[int] = None) -> bool:
        """Write a single holding register"""
        self._validate_plc_id(plc_id)
        
        operation = ModbusOperation(
            operation_type='write_register',
            address=address,
            values=value,
            unit_id=unit_id
        )
        
        return await self.plc_connections[plc_id].execute_operation(operation)
    
    async def write_registers(self, plc_id: str, start_address: int, values: List[int], unit_id: Optional[int] = None) -> bool:
        """Write multiple holding registers"""
        self._validate_plc_id(plc_id)
        
        operation = ModbusOperation(
            operation_type='write_registers',
            address=start_address,
            values=values,
            unit_id=unit_id
        )
        
        return await self.plc_connections[plc_id].execute_operation(operation)
    
    def get_connection_status(self, plc_id: Optional[str] = None) -> Dict[str, Any]:
        """Get connection status for one or all PLCs"""
        if plc_id:
            self._validate_plc_id(plc_id)
            return self._get_plc_status(self.plc_connections[plc_id])
        
        return {
            plc_id: self._get_plc_status(connection)
            for plc_id, connection in self.plc_connections.items()
        }
    
    def _get_plc_status(self, connection: PLCConnection) -> Dict[str, Any]:
        """Get status information for a single PLC connection"""
        metrics = connection.metrics
        uptime = None
        if metrics.connection_uptime_start:
            uptime = (datetime.now() - metrics.connection_uptime_start).total_seconds()
        
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
                'success_rate': (metrics.successful_requests / metrics.total_requests * 100) if metrics.total_requests > 0 else 0,
                'avg_response_time': metrics.avg_response_time,
                'uptime_seconds': uptime,
                'last_successful_connection': metrics.last_successful_connection.isoformat() if metrics.last_successful_connection else None,
                'last_error': metrics.last_error,
                'last_error_time': metrics.last_error_time.isoformat() if metrics.last_error_time else None
            }
        }
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        total_plcs = len(self.plc_connections)
        connected_plcs = sum(1 for conn in self.plc_connections.values() if conn.state == ConnectionState.CONNECTED)
        
        return {
            'status': 'healthy' if connected_plcs == total_plcs else 'degraded' if connected_plcs > 0 else 'unhealthy',
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

# Global connection manager instance
connection_manager = ConnectionManager()

# Convenience functions for external use
async def initialize_connections(plc_configs: List[PLCConfig], redis_url: Optional[str] = None):
    """Initialize the global connection manager"""
    await connection_manager.initialize(plc_configs, redis_url)

async def shutdown_connections():
    """Shutdown the global connection manager"""
    await connection_manager.shutdown()

async def read_register(plc_id: str, address: int, unit_id: Optional[int] = None) -> int:
    """Read a single register"""
    return await connection_manager.read_register(plc_id, address, unit_id)

async def write_register(plc_id: str, address: int, value: int, unit_id: Optional[int] = None) -> bool:
    """Write a single register"""
    return await connection_manager.write_register(plc_id, address, value, unit_id)

async def read_registers(plc_id: str, start_address: int, count: int, unit_id: Optional[int] = None) -> List[int]:
    """Read multiple registers"""
    return await connection_manager.read_registers(plc_id, start_address, count, unit_id)

async def write_registers(plc_id: str, start_address: int, values: List[int], unit_id: Optional[int] = None) -> bool:
    """Write multiple registers"""
    return await connection_manager.write_registers(plc_id, start_address, values, unit_id)

def get_connection_status(plc_id: Optional[str] = None) -> Dict[str, Any]:
    """Get connection status"""
    return connection_manager.get_connection_status(plc_id)

async def get_health_status() -> Dict[str, Any]:
    """Get health status"""
    return await connection_manager.get_health_status()
